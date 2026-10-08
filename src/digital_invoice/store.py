"""Digital Invoice Lifecycle durable store — WP-10.1 MVP implementation.

Binding basis: SPEC-WP101-DILIFE §7/§8 (OD-DI1..DI7). The project store
pattern, unchanged: stdlib sqlite3, ONE separate embedded DB file
(`digital-invoice.db`), synchronous=FULL, idempotent schema, explicit
BEGIN IMMEDIATE / COMMIT, atomic single-row commit (zero residue on any
failure), immutable rows (no UPDATE / no DELETE — AST-proven), sha256-v1
record fingerprints computed through the project S1 service (no hashlib in
this layer — OD-DI5), Verify-on-Read support via canonical bytes, SQL CHECK
gates + defensive Python-side refusals mirroring every CHECK (OD-DI6),
UNIQUE(invoice_id) as the INV-DI-1:1 backstop and UNIQUE(digital_invoice_id,
event_seq) as the per-invoice sequence backstop (OD-DI3), restart-safe.

The §5.2 transition matrix is encoded AT THE DATABASE LEVEL: every
(event_type, from_state, to_state) CHECK pair is a row of SPEC §5.2 — an
illegal state movement cannot persist even through direct SQL (the matrix
tests prove the CHECK refusals). The store knows NOTHING about upstream
semantics: it persists what the service derived from the P6.2 verified read
and the explicit lifecycle acts, and enforces the §7 shapes.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from capture import S1ComputationFailure, S1Service

from .model import (
    EVENT_ISSUE,
    EVENT_MARK_EXTRACTED,
    EVENT_MARK_VALIDATED,
    EVENT_REVOKE,
    EVENT_SUPERSEDE,
    LIFECYCLE_STATES,
    ORIGINS,
    STATE_DRAFT,
    STATE_EXTRACTED,
    STATE_ISSUED,
    STATE_REVOKED,
    STATE_SUPERSEDED,
    STATE_VALIDATED,
    DigitalInvoiceDuplicate,
    DigitalInvoiceNotFound,
    DigitalInvoicePersistenceUnavailable,
    DigitalInvoiceRecord,
    LifecycleEventDuplicate,
    LifecycleEventRecord,
    is_legal_transition,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS digital_invoices (
    digital_invoice_id        TEXT PRIMARY KEY,
    invoice_id                TEXT NOT NULL UNIQUE,
    capture_s1                TEXT NOT NULL,
    capture_s1_algorithm_id   TEXT NOT NULL,
    capture_id                TEXT NOT NULL,
    document_id               TEXT NOT NULL,
    origin                    TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    record_fingerprint        TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL,
    -- OD-DI6: frozen origin vocabulary (quoted from the verified P6.2 row)
    CHECK (origin IN ('KANDOO_SALE', 'HOLOO_CAPTURE', 'OTHER_POS_CAPTURE'))
);

"""

_SCHEMA += """
CREATE TABLE IF NOT EXISTS digital_invoice_events (
    event_id                  TEXT NOT NULL UNIQUE,
    digital_invoice_id        TEXT NOT NULL,
    invoice_id                TEXT NOT NULL,
    event_seq                 INTEGER NOT NULL CHECK (event_seq >= 0),
    event_type                TEXT NOT NULL,
    from_state                TEXT NOT NULL,
    to_state                  TEXT NOT NULL,
    replacement_invoice_id    TEXT NOT NULL,
    reason_note               TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    record_fingerprint        TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL,
    -- OD-DI6: the lifecycle vocabularies (states verbatim per AS-03; acts
    -- per OD-DI-C)
    CHECK (event_type IN ('MARK_EXTRACTED', 'MARK_VALIDATED', 'ISSUE',
                          'REVOKE', 'SUPERSEDE')),
    CHECK (from_state IN ('DRAFT', 'EXTRACTED', 'VALIDATED', 'ISSUED',
                          'REVOKED', 'SUPERSEDED')),
    CHECK (to_state IN ('DRAFT', 'EXTRACTED', 'VALIDATED', 'ISSUED',
                        'REVOKED', 'SUPERSEDED')),
    -- SPEC §5.2 matrix at the DB level: exactly the five legal transitions
    -- (IF event_type = X THEN the exact (from, to) pair — any other state
    -- movement, including every skip/backward/terminal-exit, cannot persist)
    CHECK (event_type != 'MARK_EXTRACTED'
           OR (from_state = 'DRAFT' AND to_state = 'EXTRACTED')),
    CHECK (event_type != 'MARK_VALIDATED'
           OR (from_state = 'EXTRACTED' AND to_state = 'VALIDATED')),
    CHECK (event_type != 'ISSUE'
           OR (from_state = 'VALIDATED' AND to_state = 'ISSUED')),
    CHECK (event_type != 'REVOKE'
           OR (from_state = 'ISSUED' AND to_state = 'REVOKED')),
    CHECK (event_type != 'SUPERSEDE'
           OR (from_state = 'ISSUED' AND to_state = 'SUPERSEDED')),
    -- shape gates: SUPERSEDE ⇔ replacement pointer; no event may FOLLOW a
    -- terminal state (terminal discipline — no legal from_state is terminal)
    CHECK (event_type = 'SUPERSEDE'
           OR replacement_invoice_id = ''),
    CHECK (event_type != 'SUPERSEDE'
           OR replacement_invoice_id != ''),
    CHECK (from_state NOT IN ('REVOKED', 'SUPERSEDED')),
    CHECK (from_state != 'DRAFT'
           OR event_type = 'MARK_EXTRACTED')
)
"""


def canonical_digital_invoice_bytes(record: DigitalInvoiceRecord) -> bytes:
    """Deterministic serialization of the creation-row scalars — the VOR
    anchor payload (OD-DI5). Field order is fixed by the dataclass; no
    mapping iteration anywhere."""
    parts = [
        b"digital-invoice-v1",
        record.digital_invoice_id.encode("utf-8"),
        record.invoice_id.encode("utf-8"),
        record.capture_s1.encode("utf-8"),
        record.capture_s1_algorithm_id.encode("utf-8"),
        record.capture_id.encode("utf-8"),
        record.document_id.encode("utf-8"),
        record.origin.encode("utf-8"),
        record.created_at.encode("utf-8"),
    ]
    return b"\x1f".join(parts)


def canonical_event_bytes(record: LifecycleEventRecord) -> bytes:
    """Deterministic serialization of the event-row scalars — the VOR
    anchor payload (OD-DI5)."""
    parts = [
        b"digital-invoice-event-v1",
        record.event_id.encode("utf-8"),
        record.digital_invoice_id.encode("utf-8"),
        record.invoice_id.encode("utf-8"),
        str(record.event_seq).encode("ascii"),
        record.event_type.encode("utf-8"),
        record.from_state.encode("utf-8"),
        record.to_state.encode("utf-8"),
        record.replacement_invoice_id.encode("utf-8"),
        record.reason_note.encode("utf-8"),
        record.created_at.encode("utf-8"),
    ]
    return b"\x1f".join(parts)


def _invoice_from_row(row: sqlite3.Row) -> DigitalInvoiceRecord:
    return DigitalInvoiceRecord(
        digital_invoice_id=row["digital_invoice_id"],
        invoice_id=row["invoice_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        capture_id=row["capture_id"],
        document_id=row["document_id"],
        origin=row["origin"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _event_from_row(row: sqlite3.Row) -> LifecycleEventRecord:
    return LifecycleEventRecord(
        event_id=row["event_id"],
        digital_invoice_id=row["digital_invoice_id"],
        invoice_id=row["invoice_id"],
        event_seq=row["event_seq"],
        event_type=row["event_type"],
        from_state=row["from_state"],
        to_state=row["to_state"],
        replacement_invoice_id=row["replacement_invoice_id"],
        reason_note=row["reason_note"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


class DigitalInvoiceStore:
    """Durable, append-only digital-invoice lifecycle store (OD-DI1..DI7)."""

    def __init__(self, db_path, s1: S1Service) -> None:
        self._s1 = s1
        try:
            self._conn = sqlite3.connect(str(db_path), isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_di_invoice_id "
                "ON digital_invoices(invoice_id)")
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_die_seq "
                "ON digital_invoice_events(digital_invoice_id, event_seq)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_die_invoice "
                "ON digital_invoice_events(invoice_id)")
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"store unavailable: {exc}") from exc

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "DigitalInvoiceStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Commits (single row — atomic by construction, OD-DI2)
    # ------------------------------------------------------------------

    def commit_digital_invoice(self, record: DigitalInvoiceRecord) \
            -> DigitalInvoiceRecord:
        """Commit ONE creation row (state DRAFT by construction). Raises:
          DigitalInvoiceDuplicate            — INV-DI-1:1 already present
          DigitalInvoicePersistenceUnavailable — nothing recordable (txn
                                               rolled back, zero residue)
        """
        self._validate_invoice_commit_shape(record)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_invoice_in_txn(record.invoice_id)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise DigitalInvoiceDuplicate(existing.digital_invoice_id)
                try:
                    fp = self._s1.compute(
                        canonical_digital_invoice_bytes(record))
                except S1ComputationFailure as exc:
                    raise DigitalInvoicePersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = DigitalInvoiceRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    "INSERT INTO digital_invoices ("
                    "digital_invoice_id, invoice_id, capture_s1, "
                    "capture_s1_algorithm_id, capture_id, document_id, "
                    "origin, created_at, record_fingerprint, "
                    "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (final.digital_invoice_id, final.invoice_id,
                     final.capture_s1, final.capture_s1_algorithm_id,
                     final.capture_id, final.document_id, final.origin,
                     final.created_at, final.record_fingerprint,
                     final.fingerprint_algorithm_id))
                self._conn.execute("COMMIT")
                return final
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def commit_event(self, record: LifecycleEventRecord) \
            -> LifecycleEventRecord:
        """Commit ONE lifecycle event as a compare-and-swap append (the
        in-transaction guard re-reads the chain: the caller's event_seq must
        be exactly the current chain length AND the chain's live projected
        state must still equal the event's from_state — a stale-state append
        can never persist). Raises:
          LifecycleEventDuplicate            — concurrent act won (stale seq
                                               or moved state)
          DigitalInvoicePersistenceUnavailable — nothing recordable
        """
        self._validate_event_commit_shape(record)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                rows = self._conn.execute(
                    "SELECT to_state FROM digital_invoice_events "
                    "WHERE digital_invoice_id = ? ORDER BY event_seq",
                    (record.digital_invoice_id,)).fetchall()
                if record.event_seq != len(rows):
                    self._conn.execute("ROLLBACK")
                    raise LifecycleEventDuplicate(record.digital_invoice_id,
                                                  record.event_seq)
                current = rows[-1]["to_state"] if rows else STATE_DRAFT
                if current != record.from_state:
                    self._conn.execute("ROLLBACK")
                    raise LifecycleEventDuplicate(record.digital_invoice_id,
                                                  record.event_seq)
                try:
                    fp = self._s1.compute(canonical_event_bytes(record))
                except S1ComputationFailure as exc:
                    raise DigitalInvoicePersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = LifecycleEventRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    "INSERT INTO digital_invoice_events ("
                    "event_id, digital_invoice_id, invoice_id, event_seq, "
                    "event_type, from_state, to_state, "
                    "replacement_invoice_id, reason_note, created_at, "
                    "record_fingerprint, fingerprint_algorithm_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (final.event_id, final.digital_invoice_id,
                     final.invoice_id, final.event_seq, final.event_type,
                     final.from_state, final.to_state,
                     final.replacement_invoice_id, final.reason_note,
                     final.created_at, final.record_fingerprint,
                     final.fingerprint_algorithm_id))
                self._conn.execute("COMMIT")
                return final
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _validate_invoice_commit_shape(self, record: DigitalInvoiceRecord) \
            -> None:
        """Defensive Python-side refusals mirroring every SQL CHECK (OD-DI6)
        — a malformed commit never reaches the transaction."""
        if record.origin not in ORIGINS:
            raise DigitalInvoicePersistenceUnavailable(
                f"commit refused: origin {record.origin!r} is outside the "
                "frozen origin vocabulary")
        for field in ("digital_invoice_id", "invoice_id", "capture_s1",
                      "capture_s1_algorithm_id", "capture_id", "document_id",
                      "created_at"):
            if not getattr(record, field):
                raise DigitalInvoicePersistenceUnavailable(
                    f"commit refused: empty required field {field!r}")

    def _validate_event_commit_shape(self, record: LifecycleEventRecord) \
            -> None:
        """Defensive Python-side refusals mirroring every SQL CHECK (OD-DI6):
        the §5.2 matrix, the terminal discipline, and the SUPERSEDE shape."""
        if not is_legal_transition(record.event_type, record.from_state,
                                   record.to_state):
            raise DigitalInvoicePersistenceUnavailable(
                "commit refused: "
                f"({record.event_type}, {record.from_state}, "
                f"{record.to_state}) is outside the frozen transition "
                "matrix (SPEC §5.2)")
        if record.event_type == EVENT_SUPERSEDE:
            if not record.replacement_invoice_id:
                raise DigitalInvoicePersistenceUnavailable(
                    "commit refused: SUPERSEDE without the replacement "
                    "pointer")
        else:
            if record.replacement_invoice_id:
                raise DigitalInvoicePersistenceUnavailable(
                    "commit refused: non-SUPERSEDE event with a replacement "
                    "pointer")
        if not isinstance(record.reason_note, str):
            raise DigitalInvoicePersistenceUnavailable(
                "commit refused: reason_note must be a string (declared "
                "opaque — recorded verbatim)")
        for field in ("event_id", "digital_invoice_id", "invoice_id",
                      "created_at"):
            if not getattr(record, field):
                raise DigitalInvoicePersistenceUnavailable(
                    f"commit refused: empty required field {field!r}")
        if record.event_seq < 0:
            raise DigitalInvoicePersistenceUnavailable(
                "commit refused: event_seq must be >= 0")

    # ------------------------------------------------------------------
    # Reads (raw rows — verified views live in the service, SPEC §6)
    # ------------------------------------------------------------------

    def get_invoice(self, digital_invoice_id: str) -> DigitalInvoiceRecord:
        try:
            row = self._conn.execute(
                "SELECT * FROM digital_invoices WHERE digital_invoice_id = ?",
                (digital_invoice_id,)).fetchone()
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        if row is None:
            raise DigitalInvoiceNotFound(digital_invoice_id)
        return _invoice_from_row(row)

    def find_invoice(self, invoice_id: str) -> Optional[DigitalInvoiceRecord]:
        try:
            row = self._conn.execute(
                "SELECT * FROM digital_invoices WHERE invoice_id = ?",
                (invoice_id,)).fetchone()
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return _invoice_from_row(row) if row is not None else None

    def _find_invoice_in_txn(self, invoice_id: str) \
            -> Optional[DigitalInvoiceRecord]:
        row = self._conn.execute(
            "SELECT * FROM digital_invoices WHERE invoice_id = ?",
            (invoice_id,)).fetchone()
        return _invoice_from_row(row) if row is not None else None

    def next_event_seq(self, digital_invoice_id: str) -> int:
        """The next per-invoice sequence number (max+1; 0 when empty). The
        caller computes it inside its own act; the UNIQUE(digital_invoice_id,
        event_seq) backstop decides any concurrency race (OD-DI3)."""
        try:
            row = self._conn.execute(
                "SELECT MAX(event_seq) FROM digital_invoice_events "
                "WHERE digital_invoice_id = ?",
                (digital_invoice_id,)).fetchone()
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return 0 if row is None or row[0] is None else int(row[0]) + 1

    def events_of(self, digital_invoice_id: str) \
            -> List[LifecycleEventRecord]:
        """The event chain in per-invoice seq order (raw rows)."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM digital_invoice_events "
                "WHERE digital_invoice_id = ? ORDER BY event_seq",
                (digital_invoice_id,)).fetchall()
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_event_from_row(row) for row in rows]

    def find_events_by_invoice(self, invoice_id: str) \
            -> List[LifecycleEventRecord]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM digital_invoice_events "
                "WHERE invoice_id = ? ORDER BY event_seq",
                (invoice_id,)).fetchall()
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_event_from_row(row) for row in rows]

    def find_replacements_of(self, replacement_invoice_id: str) \
            -> List[LifecycleEventRecord]:
        """Every committed SUPERSEDE event pointing at a replacement (raw
        rows; the pointer is never interpreted here)."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM digital_invoice_events "
                "WHERE event_type = ? AND replacement_invoice_id = ? "
                "ORDER BY created_at, event_id",
                (EVENT_SUPERSEDE, replacement_invoice_id)).fetchall()
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_event_from_row(row) for row in rows]

    def list_invoices(self) -> List[DigitalInvoiceRecord]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM digital_invoices "
                "ORDER BY created_at, digital_invoice_id").fetchall()
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_invoice_from_row(row) for row in rows]

    def list_events(self) -> List[LifecycleEventRecord]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM digital_invoice_events "
                "ORDER BY created_at, event_id").fetchall()
        except sqlite3.Error as exc:
            raise DigitalInvoicePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_event_from_row(row) for row in rows]
