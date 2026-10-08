"""Durable Local Capture Store — T-1.1.2 implementation.

Binding basis: DES-WP11-T112-STORE v0.2 (FINAL APPROVED) over Contract v1.1.

Delegated implementation details declared here per D-09 (each satisfies its OD constraint):
  OD-1 storage mechanism : Python stdlib sqlite3, one embedded local DB file — durable,
                           local, zero network-service dependency (Store G-4); schema is
                           created idempotently at store initialization.
  OD-2 artifact_ref      : opaque string "capture-content:v1:<uuid4hex>"; bytes live in the
                           artifact_content table; byte-exact retrieval; no update/delete
                           path exists (Store I-1/I-5).
  OD-3 capture_id        : uuid4 hex — unique within the Capture layer.
  OD-4 durability        : SQLite journaling with synchronous=FULL; R-2 (write-ahead
                           completion) additionally enforced by the completion gate.
  OD-5 UAC mechanism     : BEGIN IMMEDIATE write transaction (atomic decision point, P1)
                           + uniqueness check inside the same transaction (P2) + explicit
                           loser outcome (P3) + fail-closed on storage errors (P4) + the
                           single completion primitive shared by ingest and recovery (P5)
                           + opaque byte-value comparison within equal s1_algorithm_id (P6).
                           A partial UNIQUE index is the storage-level backstop (INV-S10).
  OD-6 duplicate-attempt logging : NOT implemented in the MVP (optional per §16).
  OD-7 verification timing/caching: R-V1 every-read verification, no caching (VOR §4).
  OD-8 clock             : single layer clock (model.utc_now_iso) — implemented once.
  OD-9 ACTIVE enumeration: partial index on capture_state='ACTIVE' — complete enumeration.

The store treats (s1, s1_algorithm_id) as opaque byte values and never interprets S1
semantically (P6; Store §9). It never auto-skips, auto-merges, or auto-rejects at the
idempotency-decision level — that decision belongs to the ingest orchestration (S1 §6).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Tuple
from uuid import uuid4

from .model import (
    FORMAT_HINT_UNKNOWN,
    NOTE_CONTENT_PERSIST_FAILED,
    SOURCE_LABEL_UNDECLARED,
    CaptureLayerError,
    CaptureRecord,
    CaptureState,
    CompletionGateUnmet,
    ContentMissing,
    IllegalFieldWrite,
    IllegalTransition,
    IntegrityStatus,
    ExplicitPersistenceFailure,
    RecordCreationFailed,
    RecordNotFound,
    StorageUnavailable,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
    utc_now_iso,
)

_CONTENT_REF_PREFIX = "capture-content:v1:"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS capture_records (
    capture_id             TEXT PRIMARY KEY,
    s1                     TEXT,
    s1_algorithm_id        TEXT,
    artifact_ref           TEXT,
    created_at             TEXT NOT NULL,
    capture_state          TEXT NOT NULL
        CHECK (capture_state IN ('ACTIVE', 'COMPLETED', 'FAILED_INCOMPLETE')),
    integrity_status       TEXT NOT NULL
        CHECK (integrity_status IN ('UNVERIFIED', 'VALID', 'FAILED')),
    integrity_verified_at  TEXT,
    received_at            TEXT NOT NULL,
    source_label           TEXT NOT NULL,
    artifact_format_hint   TEXT NOT NULL,
    capture_entry_metadata TEXT NOT NULL,
    artifact_size_bytes    INTEGER,
    settlement_note        TEXT,
    -- INV-C1: COMPLETED carries the full identity/evidence field set.
    -- (integrity_status on COMPLETED evolves VALID ⇄ FAILED by later verifications,
    --  §7 r4 / VOR §5 — the VALID-at-transition gate lives in complete_record().)
    CHECK (capture_state <> 'COMPLETED' OR (
        s1 IS NOT NULL AND s1_algorithm_id IS NOT NULL AND artifact_ref IS NOT NULL
        AND artifact_size_bytes IS NOT NULL)),
    -- v1.1-C2 / INV-C9: FAILED_INCOMPLETE is settled explicitly, integrity FAILED pinned
    CHECK (capture_state <> 'FAILED_INCOMPLETE' OR (
        settlement_note IS NOT NULL AND integrity_status = 'FAILED')),
    -- Contract §5 F-15: settlement_note is meaningless on COMPLETED and stays empty
    CHECK (capture_state <> 'COMPLETED' OR settlement_note IS NULL),
    -- Store §10 / §7 r1 completion gate: a COMPLETED record is never UNVERIFIED
    CHECK (NOT (capture_state = 'COMPLETED' AND integrity_status = 'UNVERIFIED'))
);

CREATE TABLE IF NOT EXISTS artifact_content (
    content_ref TEXT PRIMARY KEY,
    content     BLOB NOT NULL
);

-- INV-C3 / INV-S10 storage-level backstop: at most one COMPLETED record per
-- (s1, s1_algorithm_id) — enforced by SQLite itself, under any concurrency, on any path.
CREATE UNIQUE INDEX IF NOT EXISTS uq_completed_s1
    ON capture_records (s1, s1_algorithm_id) WHERE capture_state = 'COMPLETED';

-- OD-9: complete ACTIVE enumeration (§11 r1)
CREATE INDEX IF NOT EXISTS ix_active_records
    ON capture_records (capture_id) WHERE capture_state = 'ACTIVE';
"""


@dataclass(frozen=True)
class _Row:
    """Internal raw row access inside transactions (state as text)."""
    capture_id: str
    s1: Optional[str]
    s1_algorithm_id: Optional[str]
    artifact_ref: Optional[str]
    created_at: str
    capture_state: str
    integrity_status: str
    integrity_verified_at: Optional[str]
    received_at: str
    source_label: str
    artifact_format_hint: str
    capture_entry_metadata: str
    artifact_size_bytes: Optional[int]
    settlement_note: Optional[str]


def _record_from_row(row: sqlite3.Row) -> CaptureRecord:
    return CaptureRecord(
        capture_id=row["capture_id"],
        s1=row["s1"],
        s1_algorithm_id=row["s1_algorithm_id"],
        artifact_ref=row["artifact_ref"],
        created_at=row["created_at"],
        capture_state=CaptureState(row["capture_state"]),
        integrity_status=IntegrityStatus(row["integrity_status"]),
        integrity_verified_at=row["integrity_verified_at"],
        received_at=row["received_at"],
        source_label=row["source_label"],
        artifact_format_hint=row["artifact_format_hint"],
        capture_entry_metadata=row["capture_entry_metadata"],
        artifact_size_bytes=row["artifact_size_bytes"],
        settlement_note=row["settlement_note"],
    )


class CaptureStore:
    """Durable local store for Capture Records + artifact bytes (T-1.1.2 scope).

    Owns: record durability, artifact durability, record↔artifact atomic binding,
    §7 transition mechanics, §6.1 deterministic settlement, UAC enforcement,
    COMPLETED-restricted lookup support, ACTIVE enumeration support, restricted
    verification-outcome writes, and the completion gate. Nothing else.
    """

    def __init__(self, db_path) -> None:
        self._db_path = str(db_path)
        # isolation_level=None → explicit transaction control (BEGIN IMMEDIATE / COMMIT).
        self._conn = sqlite3.connect(self._db_path, timeout=30.0, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-4: durability over speed
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "CaptureStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- internal helpers ----------------------------------------------------

    def _safe_rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _fetch_raw(self, capture_id: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM capture_records WHERE capture_id = ?", (capture_id,)
        ).fetchone()

    # ------------------------------------------------------------------
    # Store §3 Step 0 — record-first (R-1)
    # ------------------------------------------------------------------

    def create_active(
        self,
        received_at: str,
        source_label: Optional[str] = None,
        artifact_format_hint: Optional[str] = None,
        capture_entry_metadata: Optional[dict] = None,
    ) -> CaptureRecord:
        """Create the ACTIVE record BEFORE any content persist (R-1). F-10/F-11 fall back
        to the explicit unknown values — guessing is forbidden (§14 r6/r7)."""
        capture_id = uuid4().hex                              # OD-3
        created_at = utc_now_iso()                            # F-05 (store clock)
        label = source_label if source_label else SOURCE_LABEL_UNDECLARED
        hint = artifact_format_hint if artifact_format_hint else FORMAT_HINT_UNKNOWN
        metadata_json = json.dumps(capture_entry_metadata or {}, ensure_ascii=False)  # F-12 verbatim
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                """INSERT INTO capture_records (
                       capture_id, s1, s1_algorithm_id, artifact_ref, created_at,
                       capture_state, integrity_status, integrity_verified_at, received_at,
                       source_label, artifact_format_hint, capture_entry_metadata,
                       artifact_size_bytes, settlement_note)
                   VALUES (?, NULL, NULL, NULL, ?, 'ACTIVE', 'UNVERIFIED', NULL, ?, ?, ?, ?, NULL, NULL)""",
                (capture_id, created_at, received_at, label, hint, metadata_json),
            )
            self._conn.execute("COMMIT")
        except sqlite3.Error as exc:
            self._safe_rollback()
            # Store F2: nothing persisted; explicit failure at the store boundary; no residue.
            raise RecordCreationFailed(f"record creation failed (nothing persisted): {exc}") from exc
        return self.get_record(capture_id)

    # ------------------------------------------------------------------
    # Store §3 Step 1 — byte-exact content persist (R-2 precondition)
    # ------------------------------------------------------------------

    def persist_content(self, capture_id: str, content: bytes) -> None:
        """Persist the artifact bytes exactly as delivered + finalize F-13, atomically with
        the artifact_ref binding. ACTIVE-only, one-time (immutable binding thereafter).
        Definitive persist error → §6.1 D-1 synchronous settlement, then explicit raise."""
        content_ref = _CONTENT_REF_PREFIX + uuid4().hex        # OD-2 (opaque)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_raw(capture_id)
            if row is None:
                raise RecordNotFound(f"no such capture record: {capture_id}")
            if row["capture_state"] != CaptureState.ACTIVE.value:
                raise IllegalTransition(
                    f"content persist requires ACTIVE; record is {row['capture_state']}")
            if row["artifact_ref"] is not None:
                # I-2/I-3: the artifact binding is one-time; rewrite paths do not exist.
                raise IllegalFieldWrite("artifact content already persisted (binding is immutable)")
            self._conn.execute(
                "INSERT INTO artifact_content (content_ref, content) VALUES (?, ?)",
                (content_ref, sqlite3.Binary(bytes(content))),
            )
            self._conn.execute(
                "UPDATE capture_records SET artifact_ref = ?, artifact_size_bytes = ? WHERE capture_id = ?",
                (content_ref, len(content), capture_id),
            )
            self._conn.execute("COMMIT")
        except CaptureLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            # §6.1 D-1: definitive persist error returned to the live store → synchronous
            # settlement inside the same ingest attempt; never left ACTIVE by this class.
            try:
                self.settle_failed(capture_id, NOTE_CONTENT_PERSIST_FAILED)
            except CaptureLayerError as settle_exc:
                raise StorageUnavailable(
                    f"content persist failed and the D-1 settlement write also failed "
                    f"(D-2 residue; startup recovery will settle): {settle_exc}") from settle_exc
            raise ExplicitPersistenceFailure(
                capture_id, NOTE_CONTENT_PERSIST_FAILED,
                f"content persist failed; settled FAILED_INCOMPLETE synchronously: {exc}") from exc

    # ------------------------------------------------------------------
    # Store §3 Step 2 — immutable S1 attach (F-02/F-03)
    # ------------------------------------------------------------------

    def attach_s1(self, capture_id: str, s1: str, s1_algorithm_id: str) -> None:
        """One-time immutable attach of the S1 pair (§6 class 1 after attach). ACTIVE-only."""
        if not s1 or not s1_algorithm_id:
            raise IllegalFieldWrite("s1 and s1_algorithm_id must be non-empty (INV-C1)")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_raw(capture_id)
            if row is None:
                raise RecordNotFound(f"no such capture record: {capture_id}")
            if row["capture_state"] != CaptureState.ACTIVE.value:
                raise IllegalTransition(
                    f"s1 attach requires ACTIVE; record is {row['capture_state']}")
            if row["s1"] is not None or row["s1_algorithm_id"] is not None:
                raise IllegalFieldWrite("s1 already attached (immutable after attach, F-02/F-03)")
            self._conn.execute(
                "UPDATE capture_records SET s1 = ?, s1_algorithm_id = ? WHERE capture_id = ?",
                (s1, s1_algorithm_id, capture_id),
            )
            self._conn.execute("COMMIT")
        except CaptureLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise StorageUnavailable(f"s1 attach failed (D-2 residue): {exc}") from exc

    # ------------------------------------------------------------------
    # Restricted verification-outcome writer (§6 class 3 — the ONLY writer of F-07/F-08)
    # ------------------------------------------------------------------

    def record_verification(self, capture_id: str, verdict: str, verified_at: str) -> None:
        """Record an executed verification result (F-07 = verdict, F-08 = verified_at).
        verdict must be VALID | FAILED — UNVERIFIED is never a verification result.
        FAILED_INCOMPLETE records are rejected: their FAILED is pinned at settlement
        (§10 r5, v1.1-C2) and no later verification may change it (Store §10)."""
        if verdict not in ("VALID", "FAILED"):
            raise IllegalFieldWrite(
                f"illegal verification verdict {verdict!r}: only VALID | FAILED are writable "
                f"(UNVERIFIED exists only as the pre-first-verification state)")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_raw(capture_id)
            if row is None:
                raise RecordNotFound(f"no such capture record: {capture_id}")
            if row["capture_state"] == CaptureState.FAILED_INCOMPLETE.value:
                raise IllegalTransition(
                    "integrity fields of a settled FAILED_INCOMPLETE record are pinned "
                    "(§10 r5 / v1.1-C2) — verification may not rewrite them")
            self._conn.execute(
                "UPDATE capture_records SET integrity_status = ?, integrity_verified_at = ? "
                "WHERE capture_id = ?",
                (verdict, verified_at, capture_id),
            )
            self._conn.execute("COMMIT")
        except CaptureLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise StorageUnavailable(f"verification-outcome write failed (D-2 residue): {exc}") from exc

    # ------------------------------------------------------------------
    # Store §9.1 — the Uniqueness-Atomic Completion primitive (Steps 4 / §5 step b)
    # ------------------------------------------------------------------

    def complete_record(self, capture_id: str) -> str:
        """ACTIVE → COMPLETED, uniqueness-atomically (UAC P1–P6; INV-S10).

        Completion gate (§7 r1 / R-2, fail-closed): content durable (artifact_ref + F-13
        present) AND s1 attached AND first verification VALID — otherwise no grant.

        Returns UAC_GRANTED or UAC_UNIQUENESS_CONFLICT (explicit loser outcome, P3 — the
        record is left untouched; settlement is the caller's directive per §7 r2).
        This is the ONLY completion path in the layer (P5): ingest Step 4 and recovery
        §5 step b both execute through it."""
        try:
            self._conn.execute("BEGIN IMMEDIATE")              # P1: atomic decision point
            row = self._fetch_raw(capture_id)
            if row is None:
                raise RecordNotFound(f"no such capture record: {capture_id}")
            if row["capture_state"] != CaptureState.ACTIVE.value:
                raise IllegalTransition(
                    f"completion requires ACTIVE; record is {row['capture_state']} (terminal "
                    f"states never change — §7 r3/r5)")
            if row["artifact_ref"] is None or row["artifact_size_bytes"] is None:
                raise CompletionGateUnmet("content not durable (R-2 write-ahead completion)")
            if not row["s1"] or not row["s1_algorithm_id"]:
                raise CompletionGateUnmet("s1 not attached (INV-C1)")
            if row["integrity_status"] != IntegrityStatus.VALID.value:
                raise CompletionGateUnmet(
                    f"first verification not VALID (integrity_status={row['integrity_status']})")
            # P2/P6: uniqueness decision INSIDE the same transaction; opaque byte-value
            # equality within the equal s1_algorithm_id — no semantic interpretation.
            dup = self._conn.execute(
                """SELECT capture_id FROM capture_records
                   WHERE s1 = ? AND s1_algorithm_id = ?
                     AND capture_state = 'COMPLETED' AND capture_id <> ?""",
                (row["s1"], row["s1_algorithm_id"], capture_id),
            ).fetchone()
            if dup is not None:
                self._safe_rollback()
                return UAC_UNIQUENESS_CONFLICT                 # P3: explicit loser
            self._conn.execute(
                "UPDATE capture_records SET capture_state = 'COMPLETED' WHERE capture_id = ?",
                (capture_id,),
            )
            self._conn.execute("COMMIT")
            return UAC_GRANTED
        except sqlite3.IntegrityError:
            # Backstop: the partial unique index fired — an explicit conflict, never a crash.
            self._safe_rollback()
            return UAC_UNIQUENESS_CONFLICT
        except CaptureLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise StorageUnavailable(                          # P4: fail-closed
                f"completion could not execute (never granted tentatively): {exc}") from exc

    # ------------------------------------------------------------------
    # Settlement — ACTIVE → FAILED_INCOMPLETE (§7 r2; v1.1-C2 pin; INV-C9)
    # ------------------------------------------------------------------

    def settle_failed(self, capture_id: str, settlement_note: str) -> None:
        """Settle an ACTIVE leftover to FAILED_INCOMPLETE with a mandatory settlement_note
        and integrity_status = FAILED pinned at the settlement moment. One atomic txn.
        Terminal: re-settlement of any non-ACTIVE record is rejected (§7 r3/r5)."""
        if not settlement_note:
            raise IllegalFieldWrite("settlement_note is mandatory (INV-C9)")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_raw(capture_id)
            if row is None:
                raise RecordNotFound(f"no such capture record: {capture_id}")
            if row["capture_state"] != CaptureState.ACTIVE.value:
                raise IllegalTransition(
                    f"settlement requires ACTIVE; record is {row['capture_state']} "
                    f"(terminal states never change)")
            self._conn.execute(
                """UPDATE capture_records
                   SET capture_state = 'FAILED_INCOMPLETE', integrity_status = 'FAILED',
                       settlement_note = ?
                   WHERE capture_id = ?""",
                (settlement_note, capture_id),
            )
            self._conn.execute("COMMIT")
        except CaptureLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise StorageUnavailable(f"settlement write failed (D-2 residue): {exc}") from exc

    # ------------------------------------------------------------------
    # Read capabilities (Store §1 item 6)
    # ------------------------------------------------------------------

    def get_record(self, capture_id: str) -> CaptureRecord:
        row = self._fetch_raw(capture_id)
        if row is None:
            raise RecordNotFound(f"no such capture record: {capture_id}")
        return _record_from_row(row)

    def get_content(self, artifact_ref: Optional[str]) -> bytes:
        """Byte-exact content read via artifact_ref (the verification input; Store §10)."""
        if not artifact_ref:
            raise ContentMissing("record carries no artifact reference")
        row = self._conn.execute(
            "SELECT content FROM artifact_content WHERE content_ref = ?", (artifact_ref,)
        ).fetchone()
        if row is None:
            raise ContentMissing(f"no durable content for artifact_ref: {artifact_ref}")
        return bytes(row["content"])

    def find_completed(self, s1: str, s1_algorithm_id: str) -> List[CaptureRecord]:
        """Lookup capability RESTRICTED to capture_state = COMPLETED (Contract §9 step 2).
        ACTIVE and FAILED_INCOMPLETE records never match (S1 INV-F4). Deterministic order
        (AC-T113-2). The store returns results; the caller decides what they mean."""
        rows = self._conn.execute(
            """SELECT * FROM capture_records
               WHERE s1 = ? AND s1_algorithm_id = ? AND capture_state = 'COMPLETED'
               ORDER BY capture_id""",
            (s1, s1_algorithm_id),
        ).fetchall()
        return [_record_from_row(r) for r in rows]

    def enumerate_active(self) -> List[CaptureRecord]:
        """Complete enumeration of ACTIVE leftovers (§11 r1; OD-9)."""
        rows = self._conn.execute(
            "SELECT * FROM capture_records WHERE capture_state = 'ACTIVE' ORDER BY created_at, capture_id"
        ).fetchall()
        return [_record_from_row(r) for r in rows]

    def count_by_key(self, s1: str, s1_algorithm_id: str) -> Tuple[int, int]:
        """Test/inspection helper: (count of COMPLETED, count of all) for one opaque key.
        Used by acceptance tests for INV-C3 verification; not a consumer capability."""
        completed = self._conn.execute(
            """SELECT COUNT(*) AS n FROM capture_records
               WHERE s1 = ? AND s1_algorithm_id = ? AND capture_state = 'COMPLETED'""",
            (s1, s1_algorithm_id),
        ).fetchone()["n"]
        total = self._conn.execute(
            "SELECT COUNT(*) AS n FROM capture_records WHERE s1 = ? AND s1_algorithm_id = ?",
            (s1, s1_algorithm_id),
        ).fetchone()["n"]
        return completed, total
