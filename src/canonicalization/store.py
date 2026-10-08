"""Durable Canonicalization Gate store — WP-6.1 MVP implementation.

Binding basis: SPEC-WP61-CANGATE §8 (OD-C1..OD-C7 delegated details declared
here). Same store pattern as P1–P5.2: stdlib sqlite3, ONE separate embedded DB
file, synchronous=FULL, idempotent schema, explicit BEGIN IMMEDIATE / COMMIT,
atomic multi-record commit, in-transaction uniqueness checks + UNIQUE index
backstops, sha256-v1 fingerprints over canonical byte serializations,
append-only hash-chained review events, Verify-on-Read raw access.

NO UPDATE and NO DELETE path exists in this store (OD-C7; AST-proven by the
boundary tests). Nothing is interpreted here — no identity decision, no
semantic resolution, no matching: only deterministic persistence mechanics.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional, Sequence

from capture import S1ComputationFailure, S1Service

from .model import (
    DECISION_ACCEPTED,
    DECISIONS,
    DECISION_REVIEW,
    EVENT_TYPES,
    GATE_REJECT_REASONS,
    GATE_REVIEW_REASONS,
    IDENTITY_CLASSES,
    IDENTITY_CLASS_DETERMINISTIC,
    IDENTITY_SOURCES,
    ORIGINS,
    REASON_ALL_FROZEN_CONDITIONS_MET,
    REASON_D02_CAPTURE_REPLAY,
    CanonicalIdentityPointer,
    CanonicalInvoiceNotFound,
    CanonicalInvoiceRecord,
    CanonicalizationPersistenceUnavailable,
    GateDecisionDuplicate,
    GateDecisionNotFound,
    GateDecisionRecord,
    GateReviewEvent,
    GateReviewItem,
    GateReviewItemNotFound,
    RELAYED_REVIEW_REASONS,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gate_decisions (
    decision_id                TEXT PRIMARY KEY,
    domain_state_id            TEXT NOT NULL,
    normalization_id           TEXT NOT NULL,
    extraction_id              TEXT NOT NULL,
    document_id                TEXT NOT NULL,
    capture_id                 TEXT NOT NULL,
    capture_s1                 TEXT NOT NULL,
    capture_s1_algorithm_id    TEXT NOT NULL,
    declared_origin            TEXT NOT NULL
                               CHECK (declared_origin IN
                                      ('KANDOO_SALE','HOLOO_CAPTURE',
                                       'OTHER_POS_CAPTURE')),
    decision                   TEXT NOT NULL
                               CHECK (decision IN
                                      ('ACCEPTED','REJECTED','REVIEW',
                                       'ALREADY_CANONICALIZED')),
    decision_reason            TEXT NOT NULL,
    decision_detail            TEXT NOT NULL,
    identity_class             TEXT NOT NULL
                               CHECK (identity_class IN
                                      ('','DETERMINISTIC','CAPTURE_SCOPED')),
    identity_source            TEXT NOT NULL
                               CHECK (identity_source IN
                                      ('','S2_EXTRACTED_VERIFIED')),
    identity_fingerprint       TEXT NOT NULL,
    canonical_invoice_id       TEXT,
    upstream_review_id         TEXT,
    created_at                 TEXT NOT NULL,
    record_fingerprint         TEXT NOT NULL,
    fingerprint_algorithm_id   TEXT NOT NULL,
    -- OD-C6: decision ↔ canonical-invoice linkage consistency
    CHECK ((decision = 'ACCEPTED' AND canonical_invoice_id IS NOT NULL)
        OR (decision != 'ACCEPTED' AND canonical_invoice_id IS NULL)),
    CHECK (decision != 'REVIEW'
           OR decision_reason IN ('d08-mismatch-review',
                                  'd01-unresolved-review',
                                  'validation-deferred-review',
                                  'd03-incomplete-document-identity',
                                  'd03-conflicting-document-identity',
                                  'd03-document-identity-undetermined')),
    CHECK (decision != 'REJECTED'
           OR decision_reason IN ('upstream-decisive-invalid',
                                  'd03-definite-document-duplicate')),
    CHECK (decision != 'ALREADY_CANONICALIZED'
           OR decision_reason = 'd02-capture-idempotent-replay'),
    CHECK (decision != 'ACCEPTED'
           OR decision_reason = 'all-frozen-conditions-met'),
    CHECK (identity_class != '' OR identity_fingerprint = '')
);

-- OD-C3: INV-D-1:1 storage-level backstop — at most ONE gate decision per
-- P5.2 domain state (a replay returns the existing decision, never re-decides)
CREATE UNIQUE INDEX IF NOT EXISTS uq_gate_decision_state
    ON gate_decisions (domain_state_id);

CREATE TABLE IF NOT EXISTS canonical_invoices (
    canonical_invoice_id       TEXT PRIMARY KEY,
    decision_id                TEXT NOT NULL REFERENCES
                               gate_decisions(decision_id),
    domain_state_id            TEXT NOT NULL,
    normalization_id           TEXT NOT NULL,
    extraction_id              TEXT NOT NULL,
    document_id                TEXT NOT NULL,
    capture_id                 TEXT NOT NULL,
    capture_s1                 TEXT NOT NULL,
    capture_s1_algorithm_id    TEXT NOT NULL,
    origin                     TEXT NOT NULL
                               CHECK (origin IN
                                      ('KANDOO_SALE','HOLOO_CAPTURE',
                                       'OTHER_POS_CAPTURE')),
    identity_class             TEXT NOT NULL
                               CHECK (identity_class = 'DETERMINISTIC'),
    identity_source            TEXT NOT NULL
                               CHECK (identity_source =
                                      'S2_EXTRACTED_VERIFIED'),
    identity_fingerprint       TEXT NOT NULL,
    created_at                 TEXT NOT NULL,
    record_fingerprint         TEXT NOT NULL,
    fingerprint_algorithm_id   TEXT NOT NULL
);

-- OD-C3: INV-CI-1:1 — exactly one canonical invoice per ACCEPTED decision
CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_invoice_decision
    ON canonical_invoices (decision_id);
-- OD-C3: capture-level idempotency backstop (D-02: S1 = the capture-level
-- idempotency key — one capture artifact, one canonical invoice, ever)
CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_invoice_capture
    ON canonical_invoices (capture_s1);
-- OD-C3: document-level duplicate backstop behind the G5 exact check (D-03)
CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_invoice_identity
    ON canonical_invoices (identity_fingerprint);

CREATE TABLE IF NOT EXISTS canonical_identity_pointers (
    canonical_invoice_id   TEXT NOT NULL REFERENCES
                           canonical_invoices(canonical_invoice_id),
    role                   TEXT NOT NULL
                           CHECK (role IN ('INVOICE_NUMBER','INVOICE_DATE',
                                           'INVOICE_TOTAL')),
    source_field_name      TEXT NOT NULL,
    normalization_id       TEXT NOT NULL,
    field_seq              INTEGER NOT NULL,
    PRIMARY KEY (canonical_invoice_id, role)
);

CREATE TABLE IF NOT EXISTS gate_review_items (
    review_id             TEXT PRIMARY KEY,
    decision_id           TEXT NOT NULL REFERENCES gate_decisions(decision_id),
    domain_state_id       TEXT NOT NULL,
    normalization_id      TEXT NOT NULL,
    extraction_id         TEXT NOT NULL,
    document_id           TEXT NOT NULL,
    capture_id            TEXT NOT NULL,
    capture_s1            TEXT NOT NULL,
    review_reason         TEXT NOT NULL,
    review_detail         TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    item_fingerprint      TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL
);

-- OD-C3: INV-GR-1:1 — exactly one gate REVIEW item per REVIEW decision
CREATE UNIQUE INDEX IF NOT EXISTS uq_gate_review_decision
    ON gate_review_items (decision_id);

CREATE TABLE IF NOT EXISTS gate_review_events (
    event_id                TEXT NOT NULL UNIQUE,
    review_id               TEXT NOT NULL REFERENCES
                            gate_review_items(review_id),
    event_seq               INTEGER NOT NULL CHECK (event_seq >= 0),
    event_type              TEXT NOT NULL CHECK (event_type IN
                            ('ANNOTATE','CLOSE')),
    event_note              TEXT NOT NULL,
    event_actor             TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    prev_event_fingerprint  TEXT NOT NULL,
    event_fingerprint       TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL,
    PRIMARY KEY (review_id, event_seq)
);

-- OD-C6: at most ONE CLOSE per gate review item (terminal — storage backstop)
CREATE UNIQUE INDEX IF NOT EXISTS uq_gate_review_single_close
    ON gate_review_events (review_id) WHERE event_type = 'CLOSE';
"""


def _chunk(value) -> bytes:
    """Deterministic length-prefixed encoding of one canonical element (same
    encoding as every other layer)."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bool):                          # guard: bool before int
        raise TypeError("bool is not a canonical element")
    elif isinstance(value, int):
        raw = str(value).encode("ascii")
    else:
        raise TypeError(f"unsupported canonical element: {type(value)!r}")
    return len(raw).to_bytes(8, "big") + raw


def canonical_decision_bytes(record: GateDecisionRecord) -> bytes:
    """Canonical serialization fingerprinted by OD-C5 (decision scalars)."""
    return b"".join([
        _chunk(record.decision_id),
        _chunk(record.domain_state_id),
        _chunk(record.normalization_id),
        _chunk(record.extraction_id),
        _chunk(record.document_id),
        _chunk(record.capture_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.declared_origin),
        _chunk(record.decision),
        _chunk(record.decision_reason),
        _chunk(record.decision_detail),
        _chunk(record.identity_class),
        _chunk(record.identity_source),
        _chunk(record.identity_fingerprint),
        _chunk(record.canonical_invoice_id
               if record.canonical_invoice_id is not None else ""),
        _chunk(record.upstream_review_id
               if record.upstream_review_id is not None else ""),
        _chunk(record.created_at),
    ])


def canonical_invoice_bytes(record: CanonicalInvoiceRecord,
                            pointers: Sequence[CanonicalIdentityPointer]) \
        -> bytes:
    """Canonical serialization fingerprinted by OD-C5 (invoice scalars + the
    identity pointer rows in role order)."""
    parts: List[bytes] = [
        _chunk(record.canonical_invoice_id),
        _chunk(record.decision_id),
        _chunk(record.domain_state_id),
        _chunk(record.normalization_id),
        _chunk(record.extraction_id),
        _chunk(record.document_id),
        _chunk(record.capture_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.origin),
        _chunk(record.identity_class),
        _chunk(record.identity_source),
        _chunk(record.identity_fingerprint),
        _chunk(record.created_at),
    ]
    for p in pointers:
        parts += [
            _chunk(p.canonical_invoice_id),
            _chunk(p.role),
            _chunk(p.source_field_name),
            _chunk(p.normalization_id),
            _chunk(p.field_seq),
        ]
    return b"".join(parts)


def canonical_item_bytes(item: GateReviewItem) -> bytes:
    """Canonical serialization fingerprinted by OD-C5 (item scalars)."""
    return b"".join([
        _chunk(item.review_id),
        _chunk(item.decision_id),
        _chunk(item.domain_state_id),
        _chunk(item.normalization_id),
        _chunk(item.extraction_id),
        _chunk(item.document_id),
        _chunk(item.capture_id),
        _chunk(item.capture_s1),
        _chunk(item.review_reason),
        _chunk(item.review_detail),
        _chunk(item.created_at),
    ])


def canonical_event_bytes(event: GateReviewEvent) -> bytes:
    """Canonical serialization fingerprinted by OD-C5 (event scalars + the
    chain link — history tamper-evident as a chain, not just per row)."""
    return b"".join([
        _chunk(event.event_id),
        _chunk(event.review_id),
        _chunk(event.event_seq),
        _chunk(event.event_type),
        _chunk(event.event_note),
        _chunk(event.event_actor),
        _chunk(event.created_at),
        _chunk(event.prev_event_fingerprint),
    ])


def _decision_from_row(row: sqlite3.Row) -> GateDecisionRecord:
    return GateDecisionRecord(
        decision_id=row["decision_id"],
        domain_state_id=row["domain_state_id"],
        normalization_id=row["normalization_id"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        declared_origin=row["declared_origin"],
        decision=row["decision"],
        decision_reason=row["decision_reason"],
        decision_detail=row["decision_detail"],
        identity_class=row["identity_class"],
        identity_source=row["identity_source"],
        identity_fingerprint=row["identity_fingerprint"],
        canonical_invoice_id=row["canonical_invoice_id"],
        upstream_review_id=row["upstream_review_id"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _invoice_from_row(row: sqlite3.Row) -> CanonicalInvoiceRecord:
    return CanonicalInvoiceRecord(
        canonical_invoice_id=row["canonical_invoice_id"],
        decision_id=row["decision_id"],
        domain_state_id=row["domain_state_id"],
        normalization_id=row["normalization_id"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        origin=row["origin"],
        identity_class=row["identity_class"],
        identity_source=row["identity_source"],
        identity_fingerprint=row["identity_fingerprint"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _pointer_from_row(row: sqlite3.Row) -> CanonicalIdentityPointer:
    return CanonicalIdentityPointer(
        canonical_invoice_id=row["canonical_invoice_id"],
        role=row["role"],
        source_field_name=row["source_field_name"],
        normalization_id=row["normalization_id"],
        field_seq=row["field_seq"],
    )


def _item_from_row(row: sqlite3.Row) -> GateReviewItem:
    return GateReviewItem(
        review_id=row["review_id"],
        decision_id=row["decision_id"],
        domain_state_id=row["domain_state_id"],
        normalization_id=row["normalization_id"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        review_reason=row["review_reason"],
        review_detail=row["review_detail"],
        created_at=row["created_at"],
        item_fingerprint=row["item_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _event_from_row(row: sqlite3.Row) -> GateReviewEvent:
    return GateReviewEvent(
        event_id=row["event_id"],
        review_id=row["review_id"],
        event_seq=row["event_seq"],
        event_type=row["event_type"],
        event_note=row["event_note"],
        event_actor=row["event_actor"],
        created_at=row["created_at"],
        prev_event_fingerprint=row["prev_event_fingerprint"],
        event_fingerprint=row["event_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


class CanonicalizationGateStore:
    """Durable local store for gate decisions + canonical invoices + identity
    pointers + gate REVIEW items + append-only events.

    Owns: atomic admission commit (OD-C2), INV-D-1:1 / INV-CI-1:1 /
    INV-GR-1:1 + capture/document idempotency backstops (OD-C3), fingerprint
    anchoring (OD-C5), deterministic retrieval, event append with hash-chain
    tail management, verified-read raw access. Nothing else — no identity
    decision, no interpretation, no update, no delete.
    """

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        self._conn = sqlite3.connect(self._db_path, timeout=30,
                                     isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-C1: durability
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "CanonicalizationGateStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- write path: atomic admission commit (OD-C2) ------------------------

    def commit_decision(self, record: GateDecisionRecord,
                        invoice: Optional[CanonicalInvoiceRecord],
                        pointers: Sequence[CanonicalIdentityPointer],
                        review_item: Optional[GateReviewItem]) \
            -> GateDecisionRecord:
        """Commit the decision + (iff ACCEPTED) the canonical invoice with its
        identity pointers + (iff REVIEW) the gate review item — atomically.

        Raises:
          GateDecisionDuplicate             — INV-D-1:1 already present
          CanonicalizationPersistenceUnavailable — nothing recordable (txn
                                              rolled back, zero residue)
        """
        if record.decision not in DECISIONS:
            raise CanonicalizationPersistenceUnavailable(
                f"commit refused: decision {record.decision!r} is outside the "
                f"declared vocabulary")
        if record.declared_origin not in ORIGINS:
            raise CanonicalizationPersistenceUnavailable(
                f"commit refused: declared_origin "
                f"{record.declared_origin!r} is outside the frozen origin "
                f"vocabulary")
        if record.identity_class not in ("",) + IDENTITY_CLASSES:
            raise CanonicalizationPersistenceUnavailable(
                f"commit refused: identity_class {record.identity_class!r} is "
                f"outside the declared vocabulary")
        if (record.decision == DECISION_ACCEPTED) != \
                (invoice is not None):
            raise CanonicalizationPersistenceUnavailable(
                "commit refused: exactly one canonical invoice rides an "
                "ACCEPTED decision; no other decision creates one (INV-CI-1:1)")
        if invoice is not None:
            if invoice.identity_class != IDENTITY_CLASS_DETERMINISTIC:
                raise CanonicalizationPersistenceUnavailable(
                    "commit refused: an admission without a DETERMINISTIC "
                    "identity is unreachable (G3 routes REVIEW)")
            if len(pointers) != 3:
                raise CanonicalizationPersistenceUnavailable(
                    "commit refused: an admission carries exactly three "
                    "identity pointer rows (the frozen D-02 roles)")
        if (record.decision == DECISION_REVIEW) != (review_item is not None):
            raise CanonicalizationPersistenceUnavailable(
                "commit refused: exactly one REVIEW item rides a REVIEW "
                "decision; no other decision creates one (INV-GR-1:1)")
        if review_item is not None \
                and record.decision_reason not in GATE_REVIEW_REASONS:
            raise CanonicalizationPersistenceUnavailable(
                f"commit refused: review reason "
                f"{record.decision_reason!r} is outside the declared "
                f"vocabulary")
        if record.decision in ("REJECTED",) \
                and record.decision_reason not in GATE_REJECT_REASONS:
            raise CanonicalizationPersistenceUnavailable(
                f"commit refused: rejection reason "
                f"{record.decision_reason!r} is outside the declared "
                f"vocabulary")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_decision_by_state_in_txn(
                    record.domain_state_id)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise GateDecisionDuplicate(existing.decision_id)
                # OD-C3 backstops behind the service-level checks — a race can
                # only ever reach these as the single writer (BEGIN IMMEDIATE)
                if invoice is not None:
                    if self._capture_canonicalized_in_txn(invoice.capture_s1):
                        self._conn.execute("ROLLBACK")
                        raise CanonicalizationPersistenceUnavailable(
                            "commit refused: a canonical invoice already "
                            "exists for this capture_s1 (D-02 S1 idempotency)")
                    if self._identity_canonicalized_in_txn(
                            invoice.identity_fingerprint):
                        self._conn.execute("ROLLBACK")
                        raise CanonicalizationPersistenceUnavailable(
                            "commit refused: a canonical invoice already "
                            "exists with this identity fingerprint (D-03 S2 "
                            "duplicate)")
                try:
                    dfp = self._s1.compute(canonical_decision_bytes(record))
                except S1ComputationFailure as exc:
                    raise CanonicalizationPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final_decision = GateDecisionRecord(
                    **{**record.__dict__,
                       "record_fingerprint": dfp.s1,
                       "fingerprint_algorithm_id": dfp.s1_algorithm_id})
                final_invoice: Optional[CanonicalInvoiceRecord] = None
                if invoice is not None:
                    try:
                        ifp = self._s1.compute(
                            canonical_invoice_bytes(invoice, pointers))
                    except S1ComputationFailure as exc:
                        raise CanonicalizationPersistenceUnavailable(
                            f"fingerprint capability failure: {exc}") from exc
                    final_invoice = CanonicalInvoiceRecord(
                        **{**invoice.__dict__,
                           "record_fingerprint": ifp.s1,
                           "fingerprint_algorithm_id": ifp.s1_algorithm_id})
                self._insert_decision(final_decision)
                if final_invoice is not None:
                    self._insert_invoice(final_invoice)
                    self._insert_pointers(final_invoice.canonical_invoice_id,
                                          pointers)
                if review_item is not None:
                    try:
                        ifp = self._s1.compute(canonical_item_bytes(review_item))
                    except S1ComputationFailure as exc:
                        raise CanonicalizationPersistenceUnavailable(
                            f"fingerprint capability failure: {exc}") from exc
                    final_item = GateReviewItem(
                        **{**review_item.__dict__,
                           "item_fingerprint": ifp.s1,
                           "fingerprint_algorithm_id": ifp.s1_algorithm_id})
                    self._insert_review_item(final_item)
                self._conn.execute("COMMIT")
                return final_decision
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except sqlite3.Error as exc:
            raise CanonicalizationPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _insert_decision(self, record: GateDecisionRecord) -> None:
        self._conn.execute(
            """INSERT INTO gate_decisions (
                   decision_id, domain_state_id, normalization_id,
                   extraction_id, document_id, capture_id, capture_s1,
                   capture_s1_algorithm_id, declared_origin, decision,
                   decision_reason, decision_detail, identity_class,
                   identity_source, identity_fingerprint, canonical_invoice_id,
                   upstream_review_id, created_at, record_fingerprint,
                   fingerprint_algorithm_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record.decision_id, record.domain_state_id,
             record.normalization_id, record.extraction_id,
             record.document_id, record.capture_id, record.capture_s1,
             record.capture_s1_algorithm_id, record.declared_origin,
             record.decision, record.decision_reason, record.decision_detail,
             record.identity_class, record.identity_source,
             record.identity_fingerprint, record.canonical_invoice_id,
             record.upstream_review_id, record.created_at,
             record.record_fingerprint, record.fingerprint_algorithm_id))

    def _insert_invoice(self, record: CanonicalInvoiceRecord) -> None:
        self._conn.execute(
            """INSERT INTO canonical_invoices (
                   canonical_invoice_id, decision_id, domain_state_id,
                   normalization_id, extraction_id, document_id, capture_id,
                   capture_s1, capture_s1_algorithm_id, origin,
                   identity_class, identity_source, identity_fingerprint,
                   created_at, record_fingerprint, fingerprint_algorithm_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record.canonical_invoice_id, record.decision_id,
             record.domain_state_id, record.normalization_id,
             record.extraction_id, record.document_id, record.capture_id,
             record.capture_s1, record.capture_s1_algorithm_id, record.origin,
             record.identity_class, record.identity_source,
             record.identity_fingerprint, record.created_at,
             record.record_fingerprint, record.fingerprint_algorithm_id))

    def _insert_pointers(self, canonical_invoice_id: str,
                         pointers: Sequence[CanonicalIdentityPointer]) -> None:
        self._conn.executemany(
            """INSERT INTO canonical_identity_pointers (
                   canonical_invoice_id, role, source_field_name,
                   normalization_id, field_seq)
               VALUES (?,?,?,?,?)""",
            [(canonical_invoice_id, p.role, p.source_field_name,
              p.normalization_id, p.field_seq) for p in pointers])

    def _insert_review_item(self, item: GateReviewItem) -> None:
        self._conn.execute(
            """INSERT INTO gate_review_items (
                   review_id, decision_id, domain_state_id, normalization_id,
                   extraction_id, document_id, capture_id, capture_s1,
                   review_reason, review_detail, created_at,
                   item_fingerprint, fingerprint_algorithm_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (item.review_id, item.decision_id, item.domain_state_id,
             item.normalization_id, item.extraction_id, item.document_id,
             item.capture_id, item.capture_s1, item.review_reason,
             item.review_detail, item.created_at, item.item_fingerprint,
             item.fingerprint_algorithm_id))

    # -- write path: append-only review events ------------------------------

    def append_event(self, event: GateReviewEvent) -> GateReviewEvent:
        """Append ONE lifecycle event with hash-chain anchoring (single-purpose
        transaction — the event history is append-only, never rewritten)."""
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                try:
                    efp = self._s1.compute(canonical_event_bytes(event))
                except S1ComputationFailure as exc:
                    raise CanonicalizationPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = GateReviewEvent(
                    **{**event.__dict__,
                       "event_fingerprint": efp.s1,
                       "fingerprint_algorithm_id": efp.s1_algorithm_id})
                self._conn.execute(
                    """INSERT INTO gate_review_events (
                           event_id, review_id, event_seq, event_type,
                           event_note, event_actor, created_at,
                           prev_event_fingerprint, event_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (final.event_id, final.review_id, final.event_seq,
                     final.event_type, final.event_note, final.event_actor,
                     final.created_at, final.prev_event_fingerprint,
                     final.event_fingerprint, final.fingerprint_algorithm_id))
                self._conn.execute("COMMIT")
                return final
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except sqlite3.Error as exc:
            raise CanonicalizationPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    # -- read path: deterministic retrieval + verified-read raw access ------

    def get_decision(self, decision_id: str) -> GateDecisionRecord:
        row = self._conn.execute(
            "SELECT * FROM gate_decisions WHERE decision_id = ?",
            (decision_id,)).fetchone()
        if row is None:
            raise GateDecisionNotFound(decision_id)
        return _decision_from_row(row)

    def find_decision_by_state(self, domain_state_id: str) \
            -> Optional[GateDecisionRecord]:
        return self._find_decision_by_state_in_txn(domain_state_id)

    def _find_decision_by_state_in_txn(self, domain_state_id: str) \
            -> Optional[GateDecisionRecord]:
        row = self._conn.execute(
            "SELECT * FROM gate_decisions WHERE domain_state_id = ?",
            (domain_state_id,)).fetchone()
        return _decision_from_row(row) if row is not None else None

    def get_invoice(self, canonical_invoice_id: str) \
            -> CanonicalInvoiceRecord:
        row = self._conn.execute(
            "SELECT * FROM canonical_invoices WHERE canonical_invoice_id = ?",
            (canonical_invoice_id,)).fetchone()
        if row is None:
            raise CanonicalInvoiceNotFound(canonical_invoice_id)
        return _invoice_from_row(row)

    def get_invoice_by_decision(self, decision_id: str) \
            -> Optional[CanonicalInvoiceRecord]:
        row = self._conn.execute(
            "SELECT * FROM canonical_invoices WHERE decision_id = ?",
            (decision_id,)).fetchone()
        return _invoice_from_row(row) if row is not None else None

    def get_invoice_by_capture(self, capture_s1: str) \
            -> Optional[CanonicalInvoiceRecord]:
        row = self._conn.execute(
            "SELECT * FROM canonical_invoices WHERE capture_s1 = ?",
            (capture_s1,)).fetchone()
        return _invoice_from_row(row) if row is not None else None

    def get_invoice_by_identity(self, identity_fingerprint: str) \
            -> Optional[CanonicalInvoiceRecord]:
        row = self._conn.execute(
            "SELECT * FROM canonical_invoices WHERE identity_fingerprint = ?",
            (identity_fingerprint,)).fetchone()
        return _invoice_from_row(row) if row is not None else None

    def _capture_canonicalized_in_txn(self, capture_s1: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM canonical_invoices WHERE capture_s1 = ?",
            (capture_s1,)).fetchone() is not None

    def _identity_canonicalized_in_txn(self, identity_fingerprint: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM canonical_invoices WHERE identity_fingerprint = ?",
            (identity_fingerprint,)).fetchone() is not None

    def get_pointers(self, canonical_invoice_id: str) \
            -> List[CanonicalIdentityPointer]:
        rows = self._conn.execute(
            """SELECT * FROM canonical_identity_pointers
               WHERE canonical_invoice_id = ? ORDER BY
               CASE role WHEN 'INVOICE_NUMBER' THEN 0
                         WHEN 'INVOICE_DATE' THEN 1
                         ELSE 2 END""",
            (canonical_invoice_id,)).fetchall()
        return [_pointer_from_row(r) for r in rows]

    def get_review_item_by_decision(self, decision_id: str) \
            -> Optional[GateReviewItem]:
        row = self._conn.execute(
            "SELECT * FROM gate_review_items WHERE decision_id = ?",
            (decision_id,)).fetchone()
        return _item_from_row(row) if row is not None else None

    def get_item_by_review_id(self, review_id: str) -> GateReviewItem:
        row = self._conn.execute(
            "SELECT * FROM gate_review_items WHERE review_id = ?",
            (review_id,)).fetchone()
        if row is None:
            raise GateReviewItemNotFound(review_id)
        return _item_from_row(row)

    def list_review_items(self) -> List[GateReviewItem]:
        rows = self._conn.execute(
            "SELECT * FROM gate_review_items ORDER BY created_at, review_id")\
            .fetchall()
        return [_item_from_row(r) for r in rows]

    def list_decisions(self) -> List[GateDecisionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM gate_decisions ORDER BY created_at, decision_id")\
            .fetchall()
        return [_decision_from_row(r) for r in rows]

    def get_events(self, review_id: str) -> List[GateReviewEvent]:
        rows = self._conn.execute(
            """SELECT * FROM gate_review_events WHERE review_id = ?
               ORDER BY event_seq""",
            (review_id,)).fetchall()
        return [_event_from_row(r) for r in rows]

    def has_close_event(self, review_id: str) -> bool:
        return self._conn.execute(
            """SELECT 1 FROM gate_review_events WHERE review_id = ?
               AND event_type = 'CLOSE'""",
            (review_id,)).fetchone() is not None

    def chain_tail(self, review_id: str) -> Optional[str]:
        row = self._conn.execute(
            """SELECT event_fingerprint FROM gate_review_events
               WHERE review_id = ? ORDER BY event_seq DESC LIMIT 1""",
            (review_id,)).fetchone()
        return row["event_fingerprint"] if row is not None else None
