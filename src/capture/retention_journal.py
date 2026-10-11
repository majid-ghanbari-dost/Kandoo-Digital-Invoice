"""Retention Decision Journal — WP-1.3 mechanics-only durable log.

Binding basis: SPEC-WP13-RETR v1.0-MVP (§7) over the frozen WP-1.1 capture layer and
the WP-2.2 evidence-chain idiom (which is NOT imported — no frozen file is touched
and no cross-layer coupling is introduced).

WHAT IT IS
    A durable, append-only, tamper-evident log of retention DECISIONS and purge-request
    REFUSALS. It records structural facts only — ids, opaque labels, coarse outcome
    codes, injected instants, counts. No artifact content, no downstream/canonical
    datum, no Sale/Inventory/Customer semantics (INV-C7/INV-C8 preserved).

STRONGER-THAN-INHERITED PROPERTY (OD-RT-D)
    The log keeps its head anchor in an APPEND-ONLY anchor table — one anchor row per
    record, never an upsert. Consequently this store contains NO UPDATE statement and
    NO DELETE statement of any kind, and a deleted head anchor is detected exactly like
    a deleted log row. This is a property of the new module only; the frozen
    reconstruction anchor keeps its own (correct, tested) upsert design untouched.

WHY A BROKEN CHAIN BLOCKS AN APPEND (AC-1.3.2)
    Before appending, the tail is re-verified (anchor agreement + tail fingerprint +
    chain link). If the log was truncated or rewritten, the append is REFUSED with a
    typed refusal and nothing is written: the journal never silently extends a broken
    history. Repairing a broken journal is an operator/Issue-Report matter, not a
    write-path convenience.

IDEMPOTENCY (AC-1.3.3)
    Each decision carries a ``decision_key`` = sha256-v1 over the canonical decision
    bytes. A duplicate append returns the existing entry instead of writing a second
    row (UNIQUE index backstop, same UAC spirit as the frozen store, decided inside the
    same write transaction). This is idempotency OF JOURNAL ENTRIES — it is never a
    document-level deduplication and is never consulted for identity reasons
    (D-03 boundary: no new document-level idempotency definition is introduced).

Crash semantics (AC-1.3.3 / AC-1.3.4)
    The append commits the row and its anchor in ONE transaction, so a crash inside
    the append leaves ZERO residue by construction and no ACTIVE/pending state exists
    to sweep at startup (the frozen extraction-store pattern OD-X2). ``recovery_status()``
    reports this explicitly instead of assuming it.

Test seam: the two durable steps are isolated as ``_insert_entry`` / ``_write_anchor``
so tests can inject a failure at each persistence boundary without any production
fault-injection flag (project idiom: monkeypatch at the test boundary).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .retention import (
    DEF4_PENDING_LABEL,
    RETENTION_OUTCOME_ELIGIBLE,
    RETENTION_OUTCOME_INTEGRITY_DEFERRED,
    RETENTION_OUTCOME_NOT_ELIGIBLE,
    RETENTION_OUTCOME_POLICY_UNDECLARED,
    RETENTION_OUTCOME_PURGE_GATE_BLOCKED,
    RETENTION_OUTCOME_STATE_REFUSED,
    RetentionLayerError,
)
from .s1 import S1Service
from .model import utc_now_iso

# ---------------------------------------------------------------------------
# Constants + fixed vocabulary (OD-RT-D/E)
# ---------------------------------------------------------------------------

GENESIS_HASH = "0" * 64
_JOURNAL_DOMAIN = b"retention-journal:v1\n"
_CHAIN_DOMAIN = b"retention-journal-chain:v1\n"
_FINGERPRINT_ALGORITHM_ID = "sha256-v1"   # the frozen algorithm binding (D-02 / S1)

JV_POLICY_UNDECLARED = RETENTION_OUTCOME_POLICY_UNDECLARED
JV_ELIGIBLE = RETENTION_OUTCOME_ELIGIBLE
JV_NOT_ELIGIBLE = RETENTION_OUTCOME_NOT_ELIGIBLE
JV_STATE_REFUSED = RETENTION_OUTCOME_STATE_REFUSED
JV_INTEGRITY_DEFERRED = RETENTION_OUTCOME_INTEGRITY_DEFERRED
JV_PURGE_GATE_BLOCKED = RETENTION_OUTCOME_PURGE_GATE_BLOCKED

_JOURNAL_VOCABULARY = frozenset({
    JV_POLICY_UNDECLARED, JV_ELIGIBLE, JV_NOT_ELIGIBLE, JV_STATE_REFUSED,
    JV_INTEGRITY_DEFERRED, JV_PURGE_GATE_BLOCKED,
})

# Structural payload keys per outcome (the no-content boundary, AC-1.3.4).
_ALLOWED_PAYLOAD_KEYS = {
    JV_ELIGIBLE: frozenset({"age_seconds", "cutoff_seconds", "privacy_marking",
                            "policy_status_label"}),
    JV_NOT_ELIGIBLE: frozenset({"age_seconds", "cutoff_seconds", "remaining_seconds",
                                 "policy_status_label"}),
    JV_POLICY_UNDECLARED: frozenset({"policy_status_label"}),
    JV_STATE_REFUSED: frozenset({"capture_state", "policy_status_label"}),
    JV_INTEGRITY_DEFERRED: frozenset({"integrity_status", "policy_status_label"}),
    JV_PURGE_GATE_BLOCKED: frozenset({"executed", "rows_affected",
                                      "authorization_supplied", "policy_status_label"}),
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class JournalError(RetentionLayerError):
    """Base class for journal refusals."""


class JournalIllegalEntry(JournalError):
    """Outcome outside the fixed vocabulary, or a payload key that is not allowed."""


class JournalChainBroken(JournalError):
    """AC-1.3.2: the existing log failed verification — the append was refused."""

    def __init__(self, first_failure_seq: Optional[int], detail: str = "") -> None:
        super().__init__(detail or f"retention journal chain is broken at seq {first_failure_seq}")
        self.first_failure_seq = first_failure_seq


class JournalDuplicateDecision(JournalError):
    """Idempotent refusal: this exact decision is already durable (nothing written)."""

    def __init__(self, seq: int, record_hash: str, decision_key: str) -> None:
        super().__init__(f"duplicate decision already durable at seq {seq}")
        self.seq = seq
        self.record_hash = record_hash
        self.decision_key = decision_key


class JournalEntryNotFound(JournalError):
    """No journal row at the requested seq."""


class JournalTamperWithheld(JournalError):
    """Verified read detected a fingerprint/chain/anchor defect — the entry is
    WITHHELD; a silently broken read does not exist in this store."""

    def __init__(self, seq: Optional[int], reason: str) -> None:
        super().__init__(f"journal read withheld at seq {seq}: {reason}")
        self.seq = seq
        self.reason = reason


class JournalStorageUnavailable(JournalError):
    """The durable write/read could not be executed (fail-closed, never partial)."""


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JournalAppended:
    seq: int
    record_hash: str
    record_fingerprint: str
    decision_key: str


@dataclass(frozen=True)
class JournalEntry:
    seq: int
    capture_id: Optional[str]
    policy_id: Optional[str]
    outcome: str
    evaluation_time: Optional[str]
    created_at: str
    payload: dict
    record_fingerprint: str
    prev_record_hash: str
    record_hash: str
    policy_status_label: str = DEF4_PENDING_LABEL


@dataclass(frozen=True)
class JournalChainReport:
    """Explicit chain verification result — 'ok' is computed, never assumed."""
    ok: bool
    record_count: int
    first_failure_seq: Optional[int] = None
    reason: Optional[str] = None
    issues: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class JournalRecoveryStatus:
    """Startup recovery view of the journal: residue + chain agreement."""
    residue_rows: int
    chain_ok: bool
    complete: bool
    detail: str


# ---------------------------------------------------------------------------
# Schema (append-only: no UPDATE, no DELETE statement exists)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retention_decisions (
    seq                      INTEGER PRIMARY KEY,
    capture_id               TEXT,
    policy_id                TEXT,
    outcome                  TEXT NOT NULL
        CHECK (outcome IN ('POLICY_UNDECLARED', 'ELIGIBLE_CANDIDATE', 'NOT_ELIGIBLE',
                           'STATE_REFUSED', 'INTEGRITY_DEFERRED', 'PURGE_GATE_BLOCKED')),
    evaluation_time          TEXT,
    created_at               TEXT NOT NULL,
    payload                  TEXT NOT NULL,
    policy_status_label      TEXT NOT NULL DEFAULT 'DEF4-PENDING',
    fingerprint_algorithm_id TEXT NOT NULL,
    record_fingerprint       TEXT NOT NULL,
    prev_record_hash         TEXT NOT NULL,
    record_hash              TEXT NOT NULL UNIQUE,
    decision_key             TEXT NOT NULL UNIQUE
);

-- Append-only head anchor: exactly one anchor row per log row (OD-RT-D).
CREATE TABLE IF NOT EXISTS retention_journal_anchor (
    anchor_seq INTEGER PRIMARY KEY,
    last_hash  TEXT NOT NULL
);
"""


def canonical_json_text(payload: dict) -> str:
    """Canonical JSON (sorted keys, compact separators) — the exact bytes anchored."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _record_bytes(seq, capture_id, policy_id, outcome, evaluation_time, created_at,
                  payload_text, prev_hash) -> bytes:
    """Domain-separated canonical bytes behind record_fingerprint."""
    def enc(value) -> bytes:
        if value is None:
            return b"\x00"
        return str(value).encode("utf-8")
    return _JOURNAL_DOMAIN + b"\n".join([
        enc(seq), enc(capture_id), enc(policy_id), enc(outcome),
        enc(evaluation_time), enc(created_at), payload_text.encode("utf-8"), enc(prev_hash),
    ])


def _chain_bytes(prev_hash: str, fingerprint: str) -> bytes:
    return _CHAIN_DOMAIN + prev_hash.encode("ascii") + b"\n" + fingerprint.encode("ascii")


class RetentionJournal:
    """The durable retention decision journal (the only write path is an append)."""

    def __init__(self, db_path, s1: Optional[S1Service] = None) -> None:
        self.db_path = str(db_path)
        self._s1 = s1 or S1Service()
        try:
            self._conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA busy_timeout = 30000")
            self._conn.execute("PRAGMA synchronous = FULL")
            self._conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise JournalStorageUnavailable(f"journal store could not be opened: {exc}") from exc

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "RetentionJournal":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- internal persistence steps (the test seam — monkeypatch targets) ----

    def _insert_entry(self, *, seq, capture_id, policy_id, outcome, evaluation_time,
                      created_at, payload_text, fingerprint, prev_hash, record_hash,
                      decision_key) -> int:
        cursor = self._conn.execute(
            """INSERT INTO retention_decisions (
                   seq, capture_id, policy_id, outcome, evaluation_time, created_at,
                   payload, policy_status_label, fingerprint_algorithm_id,
                   record_fingerprint, prev_record_hash, record_hash, decision_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (seq, capture_id, policy_id, outcome, evaluation_time, created_at,
             payload_text, DEF4_PENDING_LABEL, self._s1.algorithm_id, fingerprint,
             prev_hash, record_hash, decision_key),
        )
        return int(cursor.lastrowid)

    def _write_anchor(self, seq: int, record_hash: str) -> None:
        self._conn.execute(
            "INSERT INTO retention_journal_anchor (anchor_seq, last_hash) VALUES (?, ?)",
            (seq, record_hash),
        )

    def _safe_rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    # -- pre-append / pre-read integrity ------------------------------------

    def _tail_row(self) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM retention_decisions ORDER BY seq DESC LIMIT 1").fetchone()

    def _anchor_agrees_with_log(self) -> Tuple[bool, Optional[int], Optional[str]]:
        """Anchor↔log agreement, both directions: truncation AND anchor deletion."""
        log_count = self._conn.execute(
            "SELECT COUNT(*) AS n, MAX(seq) AS m FROM retention_decisions").fetchone()
        anchor = self._conn.execute(
            "SELECT anchor_seq, last_hash FROM retention_journal_anchor "
            "ORDER BY anchor_seq DESC LIMIT 1").fetchone()
        anchor_count = self._conn.execute(
            "SELECT COUNT(*) AS n FROM retention_journal_anchor").fetchone()["n"]
        if log_count["n"] == 0:
            if anchor_count:
                return False, None, "anchor rows exist while the log is empty"
            return True, None, None
        if anchor is None:
            return False, None, "head anchor missing while decisions exist"
        if anchor["anchor_seq"] != log_count["m"] or anchor_count != log_count["n"]:
            # the failure position is where the ANCHOR claims history exists and the log
            # no longer agrees — i.e. the first seq a reader would be missing
            return False, anchor["anchor_seq"], (
                f"journal log truncated or anchor rewritten: anchor covers "
                f"{anchor_count} row(s) up to seq {anchor['anchor_seq']}, log holds "
                f"{log_count['n']} row(s) up to seq {log_count['m']}")
        tail = self._tail_row()
        if tail is None or tail["record_hash"] != anchor["last_hash"]:
            return False, anchor["anchor_seq"], "head anchor does not match the log tail hash"
        return True, None, None

    def _verify_prefix(self, upto_seq: Optional[int] = None
                       ) -> Tuple[bool, Optional[int], Optional[str]]:
        """Re-verify every fingerprint and every chain link (seq ≤ upto_seq)."""
        if upto_seq is None:
            rows = self._conn.execute(
                "SELECT * FROM retention_decisions ORDER BY seq").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM retention_decisions WHERE seq <= ? ORDER BY seq",
                (upto_seq,)).fetchall()
        prev_hash = GENESIS_HASH
        prev_seq = 0
        for row in rows:
            if row["seq"] != prev_seq + 1:
                return False, row["seq"], f"sequence gap before seq {row['seq']}"
            if row["prev_record_hash"] != prev_hash:
                return False, row["seq"], "prev_record_hash does not chain to the previous record"
            expected_fp = self._s1.compute(_record_bytes(
                row["seq"], row["capture_id"], row["policy_id"], row["outcome"],
                row["evaluation_time"], row["created_at"], row["payload"],
                row["prev_record_hash"])).s1
            if row["record_fingerprint"] != expected_fp:
                return False, row["seq"], "record_fingerprint does not match the stored bytes"
            if row["record_hash"] != self._s1.compute(
                    _chain_bytes(row["prev_record_hash"], row["record_fingerprint"])).s1:
                return False, row["seq"], "record_hash does not match (fingerprint re-anchored)"
            if row["fingerprint_algorithm_id"] != _FINGERPRINT_ALGORITHM_ID:
                return False, row["seq"], (
                    f"unexpected fingerprint algorithm id {row['fingerprint_algorithm_id']!r} "
                    f"(no verdict is computed for a foreign id — S1 §8 F2 discipline)")
            prev_hash = row["record_hash"]
            prev_seq = row["seq"]
        return True, None, None

    # -- the ONLY write path -------------------------------------------------

    def append_decision(self, *, capture_id: Optional[str], policy_id: Optional[str],
                        outcome: str, evaluation_time: Optional[str] = None,
                        payload: Optional[dict] = None) -> JournalAppended:
        """Append one decision record. One atomic transaction; either fully durable
        or nothing at all. Refused (nothing written) when:
          * the outcome is outside the fixed vocabulary / a payload key is not allowed
          * the existing log fails verification (AC-1.3.2 — no silent extension)
          * the identical decision is already durable (AC-1.3.3 — idempotent refusal)
        """
        if outcome not in _JOURNAL_VOCABULARY:
            raise JournalIllegalEntry(
                f"outcome {outcome!r} is outside the fixed journal vocabulary")
        payload = dict(payload or {})
        unexpected = set(map(str, payload.keys())) - _ALLOWED_PAYLOAD_KEYS[outcome]
        if unexpected:
            raise JournalIllegalEntry(
                f"payload keys {sorted(unexpected)} are not allowed for {outcome}")
        payload_text = canonical_json_text(payload)
        created_at = utc_now_iso()          # the single capture-layer clock (OD-RT-G)

        decision_key = self._s1.compute(_record_bytes(
            0, capture_id, policy_id, outcome, evaluation_time, "", payload_text,
            "decision-key")).s1

        try:
            self._conn.execute("BEGIN IMMEDIATE")

            ok, failure_seq, reason = self._anchor_agrees_with_log()
            if not ok:
                self._safe_rollback()
                raise JournalChainBroken(failure_seq, f"append refused: {reason}")
            ok, failure_seq, reason = self._verify_prefix()
            if not ok:
                self._safe_rollback()
                raise JournalChainBroken(
                    failure_seq, f"append refused: chain verification failed — {reason}")

            existing = self._conn.execute(
                "SELECT seq, record_hash FROM retention_decisions WHERE decision_key = ?",
                (decision_key,)).fetchone()
            if existing is not None:
                self._safe_rollback()
                raise JournalDuplicateDecision(
                    int(existing["seq"]), existing["record_hash"], decision_key)

            tail = self._tail_row()
            prev_seq = int(tail["seq"]) if tail is not None else 0
            prev_hash = tail["record_hash"] if tail is not None else GENESIS_HASH
            seq = prev_seq + 1

            fingerprint = self._s1.compute(_record_bytes(
                seq, capture_id, policy_id, outcome, evaluation_time, created_at,
                payload_text, prev_hash)).s1
            record_hash = self._s1.compute(_chain_bytes(prev_hash, fingerprint)).s1

            written_seq = self._insert_entry(
                seq=seq, capture_id=capture_id, policy_id=policy_id, outcome=outcome,
                evaluation_time=evaluation_time, created_at=created_at,
                payload_text=payload_text, fingerprint=fingerprint, prev_hash=prev_hash,
                record_hash=record_hash, decision_key=decision_key)
            if written_seq != seq:            # seq coherence guard (frozen-store pattern)
                self._safe_rollback()
                raise JournalStorageUnavailable("seq anomaly; nothing appended")
            self._write_anchor(seq, record_hash)
            self._conn.execute("COMMIT")
            return JournalAppended(seq, record_hash, fingerprint, decision_key)
        except (JournalIllegalEntry, JournalChainBroken, JournalDuplicateDecision):
            self._safe_rollback()
            raise
        except sqlite3.IntegrityError as exc:
            self._safe_rollback()
            # UNIQUE backstop: decision_key / record_hash collisions are explicit
            # refusals — never a crash and never a second row.
            if "retention_decisions.decision_key" in str(exc) or "decision_key" in str(exc):
                raise JournalDuplicateDecision(-1, "", decision_key) from exc
            raise JournalStorageUnavailable(f"journal append rejected by a UNIQUE backstop: {exc}") from exc
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise JournalStorageUnavailable(f"journal append failed (nothing durable): {exc}") from exc
        except Exception:
            # An unforeseen defect must never leave an open write transaction behind:
            # the append is rolled back and the original error is re-raised unchanged
            # (zero residue holds for unknown failure classes, not only for storage ones).
            self._safe_rollback()
            raise

    # -- verified read (VOR pattern applied to the journal) -------------------

    def read_entry(self, seq: int) -> JournalEntry:
        """Read one entry, re-verifying the whole prefix up to it. A defect withholds
        the entry explicitly (JournalTamperWithheld) — never a silent broken read."""
        ok, failure_seq, reason = self._anchor_agrees_with_log()
        if not ok:
            raise JournalTamperWithheld(seq, f"anchor/log disagreement: {reason}")
        ok, failure_seq, reason = self._verify_prefix(upto_seq=seq)
        if not ok:
            raise JournalTamperWithheld(seq, f"{reason} (first failure at seq {failure_seq})")
        row = self._conn.execute(
            "SELECT * FROM retention_decisions WHERE seq = ?", (seq,)).fetchone()
        if row is None:
            raise JournalEntryNotFound(f"no journal entry at seq {seq}")
        return _entry_from_row(row)

    def enumerate_entries(self) -> List[JournalEntry]:
        """Verified enumeration of the whole log (any single defect withholds all)."""
        ok, failure_seq, reason = self._anchor_agrees_with_log()
        if not ok:
            raise JournalTamperWithheld(None, f"anchor/log disagreement: {reason}")
        ok, failure_seq, reason = self._verify_prefix()
        if not ok:
            raise JournalTamperWithheld(
                None, f"{reason} (first failure at seq {failure_seq})")
        rows = self._conn.execute("SELECT * FROM retention_decisions ORDER BY seq").fetchall()
        return [_entry_from_row(r) for r in rows]

    def latest_seq(self) -> int:
        tail = self._tail_row()
        return int(tail["seq"]) if tail is not None else 0

    def verify_chain(self) -> JournalChainReport:
        """Full-log audit report — the answer a reviewer can act on."""
        ok, failure_seq, reason = self._anchor_agrees_with_log()
        issues: List[str] = []
        if not ok:
            issues.append(reason or "anchor disagreement")
            count = self._conn.execute(
                "SELECT COUNT(*) AS n FROM retention_decisions").fetchone()["n"]
            return JournalChainReport(False, int(count), failure_seq, reason, issues)
        ok2, seq2, reason2 = self._verify_prefix()
        count = self._conn.execute(
            "SELECT COUNT(*) AS n FROM retention_decisions").fetchone()["n"]
        if not ok2:
            return JournalChainReport(False, int(count), seq2, reason2, [reason2 or "chain defect"])
        return JournalChainReport(True, int(count), None, None, [])

    def recovery_status(self) -> JournalRecoveryStatus:
        """Startup recovery view. There is deliberately NO unresolved state in this
        store (single-transaction commit → zero residue by construction), so recovery
        is a verification, not a sweep. It is still computed, never assumed."""
        residue = self._conn.execute(
            "SELECT COUNT(*) AS n FROM retention_decisions WHERE created_at IS NULL").fetchone()["n"]
        report = self.verify_chain()
        complete = int(residue) == 0 and report.ok
        detail = (
            f"residue_rows={int(residue)} (no pending state exists by construction), "
            f"chain_ok={report.ok}, records={report.record_count}"
            + (f", first_failure_seq={report.first_failure_seq}, reason={report.reason}"
               if not report.ok else "")
        )
        return JournalRecoveryStatus(int(residue), report.ok, complete, detail)


def _entry_from_row(row: sqlite3.Row) -> JournalEntry:
    return JournalEntry(
        seq=int(row["seq"]),
        capture_id=row["capture_id"],
        policy_id=row["policy_id"],
        outcome=row["outcome"],
        evaluation_time=row["evaluation_time"],
        created_at=row["created_at"],
        payload=json.loads(row["payload"]),
        record_fingerprint=row["record_fingerprint"],
        prev_record_hash=row["prev_record_hash"],
        record_hash=row["record_hash"],
        policy_status_label=row["policy_status_label"],
    )
