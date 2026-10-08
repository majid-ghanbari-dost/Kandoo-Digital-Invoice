"""Reconstruction Evidence — WP-2.2 MVP implementation (durable, tamper-evident, structural).

Binding basis:
  SPEC-WP22-REC  Reconstruction Evidence Contract v1.0-MVP (produced inline per TM
                 dispatch 2026-10-01 — no separate design/review phase)
  D-02 / D-03 / D-09  frozen decisions; AS-01 external-flow sequence
  WP-2.1 frozen components (Document/Page store + service + recovery) — the ONLY
  upstream dependency inside the reconstruction layer; WP-1.1 capture layer untouched.

Boundary (normative): Evidence records ONLY structural, factual data about the
Reconstruction lifecycle — ids, fingerprints, source byte ranges, coarse reason codes,
timestamps, counts. NO artifact/page content and NO extracted/interpreted datum ever
enters an evidence record (AC-2.2.4, structurally enforced by fixed payload builders).

What this layer adds (and nothing else):
  1. An append-only, durable evidence event log in its OWN SQLite DB file.
  2. Per-record integrity anchor: record_fingerprint (reused capture S1 capability,
     sha256-v1) over the canonical record bytes.
  3. Tamper evidence: a global hash chain (prev_record_hash → record_hash, genesis
     "0"*64) so deletion / insertion / reordering / field mutation is detected.
  4. Verified evidence read (VOR pattern): an evidence read re-verifies every record
     fingerprint and every chain link up to the document's last record; a tampered
     chain fails explicitly — never a silent broken evidence read (AC-2.2.3).
  5. Page → source binding: DOCUMENT_COMPLETED evidence carries, for every page, the
     byte range it occupies in the SOURCE capture artifact (page_index → byte_start/
     byte_end) + the page fingerprint (AC-2.2.2) — the structural data WP-3.2
     (Extraction Evidence Binding) will consume.

Delegated implementation details declared here per D-09:
  OD-E1 storage  : Python stdlib sqlite3, one SEPARATE embedded local DB file
                   (durable, local, zero network dependency); synchronous=FULL;
                   isolation_level=None → explicit BEGIN IMMEDIATE / COMMIT;
                   append-only — no UPDATE/DELETE path exists in code or API.
  OD-E2 events   : fixed vocabulary DOCUMENT_COMPLETED | DOCUMENT_SETTLED_FAILED |
                   VERIFIED_READ | RECOVERY_SETTLED (document-scoped only; source-side
                   attempt outcomes with no created document are deferred, §10).
  OD-E3 chain    : record_hash = sha256("recon-evidence-chain:v1" + prev_record_hash +
                   record_fingerprint); genesis prev = 64 × "0"; appends serialized by
                   BEGIN IMMEDIATE so the chain is exact under concurrency.
  OD-E4 spans    : page spans are derived deterministically from DURABLE state only
                   (never from in-memory computation): aggregate-format artifacts
                   (document_fingerprint == capture_s1 — proven byte-identical by the
                   frozen tiling gate) → 8-byte framing offsets; fallback single-page
                   documents → one span covering the whole artifact. Rule implemented
                   once in spans_from_durable() and shared by build and recovery paths.
  OD-E5 recorder : evidence recording is NON-INTRUSIVE — an evidence write failure
                   NEVER changes a Reconstruction outcome; every failure surfaces via
                   the existing Issue-Report surfaces (service.issue_reports() /
                   recovery report.issues), never silently (AC-2.2.5).
  OD-E6 clock    : reuses the single reconstruction-layer clock (model.utc_now_iso) —
                   no second clock is introduced.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from capture import S1Service

from .model import utc_now_iso


# ---------------------------------------------------------------------------
# Event vocabulary (fixed — OD-E2) + constants
# ---------------------------------------------------------------------------

EV_DOCUMENT_COMPLETED = "DOCUMENT_COMPLETED"
EV_DOCUMENT_SETTLED_FAILED = "DOCUMENT_SETTLED_FAILED"
EV_VERIFIED_READ = "VERIFIED_READ"
EV_RECOVERY_SETTLED = "RECOVERY_SETTLED"

_EVENT_VOCABULARY = frozenset({
    EV_DOCUMENT_COMPLETED, EV_DOCUMENT_SETTLED_FAILED, EV_VERIFIED_READ, EV_RECOVERY_SETTLED,
})

DERIVATION_ID = "recon-derivation:framing-v1"   # the frozen WP-2.1 derivation rule id
GENESIS_HASH = "0" * 64

# Allowed payload keys per event type (structural no-content boundary — AC-2.2.4).
_ALLOWED_PAYLOAD_KEYS = {
    EV_DOCUMENT_COMPLETED: frozenset({
        "capture_s1", "page_count", "document_fingerprint", "fingerprint_algorithm_id",
        "derivation_id", "page_spans",
    }),
    EV_DOCUMENT_SETTLED_FAILED: frozenset({"settlement_note"}),
    EV_VERIFIED_READ: frozenset({"verdict", "reason", "state"}),
    EV_RECOVERY_SETTLED: frozenset({"final_state", "settlement_note", "page_spans"}),
}


def canonical_payload_text(payload: dict) -> str:
    """Canonical JSON text (sorted keys, compact separators, ASCII) — the exact bytes
    whose fingerprint is anchored. Payload builders pass only structural values."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Page → source byte-range derivation from DURABLE state (OD-E4 — single source)
# ---------------------------------------------------------------------------

_AGG_HEADER = 8   # bytes — frozen by CaptureService.aggregate (v1.1-C3)


def spans_from_durable(page_byte_lens: Sequence[int], aggregate_format: bool) -> Optional[List[Tuple[int, int]]]:
    """Deterministic byte ranges of the ordered pages inside the SOURCE capture artifact.

    aggregate_format=True  → the artifact is the framing join of the pages byte-exactly
    (document_fingerprint == capture_s1; guaranteed by the frozen tiling gate), so the
    spans are the mechanical framing offsets: 8-byte header before each part.
    aggregate_format=False → the fallback single-page rule applied: the one page holds
    the whole artifact → one span (0, byte_len).

    Returns None when the durable state cannot support the rule (empty page set, or a
    non-aggregate document with more than one page) — honest absence, never a guess.
    """
    lens = [int(x) for x in page_byte_lens]
    if not lens:
        return None
    if aggregate_format:
        spans: List[Tuple[int, int]] = []
        pos = _AGG_HEADER                       # first part starts after its 8-byte header
        for length in lens:
            spans.append((pos, pos + length))
            pos += length + _AGG_HEADER         # next part after its own 8-byte header
        return spans
    if len(lens) == 1:                          # fallback: the page IS the artifact
        return [(0, lens[0])]
    return None


# ---------------------------------------------------------------------------
# Records / outcomes — every result explicit, never silent
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceEvent:
    """One durable evidence record (payload parsed for consumers; content-free)."""
    seq: int
    document_id: str
    capture_id: str
    event_type: str
    payload: dict
    created_at: str
    fingerprint_algorithm_id: str
    record_fingerprint: str
    record_hash: str


@dataclass(frozen=True)
class EvidenceAppended:
    """Durable append confirmed."""
    seq: int
    record_hash: str


@dataclass(frozen=True)
class EvidenceUnavailable:
    """D-2 analog for evidence: the append is NOT durably recorded (caller surfaces an
    issue; layer behavior unchanged). Never raised into the reconstruction flow."""
    detail: str


@dataclass(frozen=True)
class EvidenceReadSuccess:
    """Verified evidence chain for one document — every record and every chain link up
    to the document's last record re-verified in THIS read (VOR on evidence)."""
    document_id: str
    events: Tuple[EvidenceEvent, ...]           # ordered by seq
    verified_up_to_seq: int


@dataclass(frozen=True)
class EvidenceReadIntegrityFailure:
    """Tamper detected — coarse position only; records are NEVER delivered on this
    outcome (no silent broken evidence read, AC-2.2.3)."""
    document_id: str
    reason: str
    failure_seq: Optional[int]


@dataclass(frozen=True)
class EvidenceReadRefused:
    """No evidence exists for the requested document_id (e.g. a document_id that never
    produced evidence, or an unknown id) — no fabrication."""
    document_id: str
    detail: str


@dataclass(frozen=True)
class EvidenceReadVerificationUnavailable:
    """Verification could not execute (storage failure) — Issue-Report surfacing."""
    document_id: str
    issue_report: str


@dataclass(frozen=True)
class ChainVerificationReport:
    """Whole-log audit result (verify_chain)."""
    valid: bool
    records: int
    last_seq: Optional[int]
    failure_seq: Optional[int] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Exceptions — construction failures surface explicitly
# ---------------------------------------------------------------------------

class EvidenceLayerError(Exception):
    """Base class for explicit evidence-layer failures."""


class EvidenceStorageUnavailable(EvidenceLayerError):
    """The evidence store could not be opened (D-2 class at composition time)."""


class EvidenceIllegalEvent(EvidenceLayerError):
    """An append demanded an event type outside the fixed vocabulary (defect signal)."""


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reconstruction_evidence (
    seq                      INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id              TEXT NOT NULL,
    capture_id               TEXT NOT NULL,
    event_type               TEXT NOT NULL
        CHECK (event_type IN ('DOCUMENT_COMPLETED', 'DOCUMENT_SETTLED_FAILED',
                              'VERIFIED_READ', 'RECOVERY_SETTLED')),
    payload                  TEXT NOT NULL,
    created_at               TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL,
    record_fingerprint       TEXT NOT NULL,
    prev_record_hash         TEXT NOT NULL,
    record_hash              TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS ix_evidence_document
    ON reconstruction_evidence (document_id, seq);

-- Log-head anchor (tamper evidence for TRUNCATION): written inside the SAME append
-- transaction as the new tail record. A deleted tail row (or a deleted head) leaves
-- this anchor disagreeing with the log — detected explicitly on every verified read
-- and by verify_chain(). Without it, a pure tail deletion would be undetectable.
CREATE TABLE IF NOT EXISTS evidence_head (
    id        INTEGER PRIMARY KEY CHECK (id = 1),
    last_seq  INTEGER NOT NULL,
    last_hash TEXT NOT NULL
);
"""


def _canonical_record_bytes(seq: int, document_id: str, capture_id: str, event_type: str,
                            payload_text: str, created_at: str, prev_hash: str) -> bytes:
    """The exact bytes anchored by record_fingerprint (domain-separated canonical form)."""
    return b"recon-evidence:v1\n" + b"\n".join([
        str(seq).encode("ascii"),
        document_id.encode("utf-8"),
        capture_id.encode("utf-8"),
        event_type.encode("utf-8"),
        payload_text.encode("utf-8"),
        created_at.encode("utf-8"),
        prev_hash.encode("ascii"),
    ])


def _chain_bytes(prev_hash: str, record_fingerprint: str) -> bytes:
    """The exact bytes anchored by record_hash — binds each record to its predecessor."""
    return b"recon-evidence-chain:v1\n" + prev_hash.encode("ascii") + b"\n" \
        + record_fingerprint.encode("ascii")


class EvidenceStore:
    """Append-only durable evidence log for the Reconstruction layer (WP-2.2 scope).

    Owns: vocabulary-checked structural event appends, per-record fingerprinting via
    the reused capture S1 capability, the global tamper-evident hash chain, verified
    per-document evidence reads, and the whole-log audit. Nothing else — no update
    path, no delete path, no content field anywhere.
    """

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        try:
            self._conn = sqlite3.connect(self._db_path, timeout=30.0, isolation_level=None)
        except sqlite3.Error as exc:
            raise EvidenceStorageUnavailable(f"evidence store could not be opened: {exc}") from exc
        try:
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA busy_timeout = 30000")
            self._conn.execute("PRAGMA synchronous = FULL")   # OD-E1: durability over speed
            self._conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            self.close()
            raise EvidenceStorageUnavailable(f"evidence schema could not be initialized: {exc}") from exc

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "EvidenceStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _safe_rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Append — the ONLY write path (append-only; OD-E1/OD-E3)
    # ------------------------------------------------------------------

    def append(self, document_id: str, capture_id: str, event_type: str, payload: dict):
        """Append one structural evidence event. Returns EvidenceAppended on durable
        success or EvidenceUnavailable when the write is not durably recordable —
        it never raises into the reconstruction flow (OD-E5)."""
        if event_type not in _EVENT_VOCABULARY:
            raise EvidenceIllegalEvent(f"event type {event_type!r} is outside the fixed vocabulary")
        unexpected = set(map(str, payload.keys())) - _ALLOWED_PAYLOAD_KEYS[event_type]
        if unexpected:
            raise EvidenceIllegalEvent(
                f"payload keys {sorted(unexpected)} are not allowed for {event_type}")
        payload_text = canonical_payload_text(payload)
        created_at = utc_now_iso()                     # OD-E6: the single layer clock
        try:
            self._conn.execute("BEGIN IMMEDIATE")      # serializes chain tail reads+writes
            row = self._conn.execute(
                "SELECT seq, record_hash FROM reconstruction_evidence ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            prev_seq = row["seq"] if row is not None else 0
            prev_hash = row["record_hash"] if row is not None else GENESIS_HASH
            seq = prev_seq + 1
            fingerprint = self._s1.compute(_canonical_record_bytes(
                seq, document_id, capture_id, event_type, payload_text, created_at, prev_hash,
            )).s1
            record_hash = self._s1.compute(_chain_bytes(prev_hash, fingerprint)).s1
            cursor = self._conn.execute(
                """INSERT INTO reconstruction_evidence (
                       document_id, capture_id, event_type, payload, created_at,
                       fingerprint_algorithm_id, record_fingerprint, prev_record_hash, record_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document_id, capture_id, event_type, payload_text, created_at,
                 self._s1.algorithm_id, fingerprint, prev_hash, record_hash),
            )
            if cursor.lastrowid != seq:                # seq/fingerprint coherence guard
                self._safe_rollback()
                return EvidenceUnavailable("evidence seq anomaly; nothing appended")
            self._conn.execute(
                """INSERT INTO evidence_head (id, last_seq, last_hash) VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET last_seq = excluded.last_seq,
                                                 last_hash = excluded.last_hash""",
                (seq, record_hash),
            )
            self._conn.execute("COMMIT")
            return EvidenceAppended(seq, record_hash)
        except sqlite3.Error as exc:
            self._safe_rollback()
            return EvidenceUnavailable(f"evidence append failed (D-2 analog): {exc}")

    # ------------------------------------------------------------------
    # Chain verification core (shared by read + audit)
    # ------------------------------------------------------------------

    def _head_agrees_with_log(self) -> Tuple[bool, Optional[int], Optional[str]]:
        """Truncation guard: the head anchor must match the actual log tail.
        An empty log (no rows, no head) is the only valid anchor-free state."""
        head = self._conn.execute(
            "SELECT last_seq, last_hash FROM evidence_head WHERE id = 1"
        ).fetchone()
        stats = self._conn.execute(
            "SELECT COUNT(*) AS n, MAX(seq) AS m FROM reconstruction_evidence"
        ).fetchone()
        if head is None:
            if stats["n"]:
                return False, None, "head anchor missing while evidence records exist"
            return True, None, None                        # valid empty log
        if head["last_seq"] != stats["m"]:
            return False, head["last_seq"], (
                f"evidence log truncated or forged: head anchor says last_seq="
                f"{head['last_seq']} but the log's highest seq is {stats['m']}")
        tail = self._conn.execute(
            "SELECT record_hash FROM reconstruction_evidence WHERE seq = ?",
            (head["last_seq"],),
        ).fetchone()
        if tail is None or tail["record_hash"] != head["last_hash"]:
            return False, head["last_seq"], "head anchor does not match the log tail record"
        return True, None, None

    def _verify_chain_prefix(self, upto_seq: Optional[int]) -> Tuple[bool, Optional[int], Optional[str], list]:
        """Re-verify every record fingerprint and every chain link for seq ≤ upto_seq.
        Returns (ok, failure_seq, reason, rows)."""
        if upto_seq is None:
            rows = self._conn.execute(
                "SELECT * FROM reconstruction_evidence ORDER BY seq").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM reconstruction_evidence WHERE seq <= ? ORDER BY seq",
                (upto_seq,),
            ).fetchall()
        prev_hash = GENESIS_HASH
        prev_seq = 0
        for row in rows:
            if row["seq"] != prev_seq + 1:
                return False, row["seq"], f"sequence gap before seq {row['seq']}", []
            expected_fp = self._s1.compute(_canonical_record_bytes(
                row["seq"], row["document_id"], row["capture_id"], row["event_type"],
                row["payload"], row["created_at"], row["prev_record_hash"],
            )).s1
            if expected_fp != row["record_fingerprint"]:
                return False, row["seq"], f"record fingerprint mismatch at seq {row['seq']}", []
            if row["prev_record_hash"] != prev_hash:
                return False, row["seq"], f"chain link broken at seq {row['seq']}", []
            expected_hash = self._s1.compute(_chain_bytes(prev_hash, row["record_fingerprint"])).s1
            if expected_hash != row["record_hash"]:
                return False, row["seq"], f"record hash mismatch at seq {row['seq']}", []
            prev_hash = row["record_hash"]
            prev_seq = row["seq"]
        return True, None, None, rows

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> EvidenceEvent:
        return EvidenceEvent(
            seq=row["seq"],
            document_id=row["document_id"],
            capture_id=row["capture_id"],
            event_type=row["event_type"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
            fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
            record_fingerprint=row["record_fingerprint"],
            record_hash=row["record_hash"],
        )

    # ------------------------------------------------------------------
    # Verified evidence read — VOR pattern on the evidence log (AC-2.2.3)
    # ------------------------------------------------------------------

    def read_document_evidence(self, document_id: str):
        """Read the evidence chain of one document, re-verifying every record and every
        chain link from genesis up to the document's last record, inside THIS read.

        Outcomes (exhaustive): EvidenceReadSuccess | EvidenceReadIntegrityFailure
        (records never delivered) | EvidenceReadRefused (no evidence for this id) |
        EvidenceReadVerificationUnavailable (verification could not execute)."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM reconstruction_evidence WHERE document_id = ? ORDER BY seq",
                (document_id,),
            ).fetchall()
            if not rows:
                return EvidenceReadRefused(
                    document_id, "no evidence records exist for this document_id")
            ok, failure_seq, reason = self._head_agrees_with_log()
            if not ok:
                return EvidenceReadIntegrityFailure(document_id, reason or "head anchor mismatch", failure_seq)
            max_seq = rows[-1]["seq"]
            ok, failure_seq, reason, _ = self._verify_chain_prefix(max_seq)
            if not ok:
                return EvidenceReadIntegrityFailure(document_id, reason or "chain broken", failure_seq)
            return EvidenceReadSuccess(
                document_id=document_id,
                events=tuple(self._event_from_row(r) for r in rows),
                verified_up_to_seq=max_seq,
            )
        except sqlite3.Error as exc:
            return EvidenceReadVerificationUnavailable(
                document_id, f"evidence read could not execute: {exc}")

    # ------------------------------------------------------------------
    # Whole-log audit (tests, smoke, operators)
    # ------------------------------------------------------------------

    def verify_chain(self) -> ChainVerificationReport:
        """Verify every record and every chain link over the whole log (incl. the
        truncation guard against the head anchor)."""
        try:
            ok, failure_seq, reason = self._head_agrees_with_log()
            if not ok:
                stats = self._conn.execute(
                    "SELECT COUNT(*) AS n, MAX(seq) AS m FROM reconstruction_evidence").fetchone()
                return ChainVerificationReport(
                    valid=False, records=stats["n"], last_seq=stats["m"],
                    failure_seq=failure_seq, reason=reason,
                )
            ok, failure_seq, reason, rows = self._verify_chain_prefix(None)
            last_seq = rows[-1]["seq"] if rows else None
            return ChainVerificationReport(
                valid=ok, records=len(rows), last_seq=last_seq,
                failure_seq=failure_seq, reason=reason,
            )
        except sqlite3.Error as exc:
            return ChainVerificationReport(
                valid=False, records=0, last_seq=None,
                failure_seq=None, reason=f"chain audit could not execute: {exc}",
            )
