"""Durable Validation-Domain Store — WP-5.2 MVP implementation.

Binding basis: SPEC-WP52-VSM §9 over the frozen WP-1.1/WP-2.1/WP-3.1/WP-4.1/
WP-4.2/WP-5.1 store pattern (same governance, new layer — upstream stores are
NOT modified; layer boundary).

Delegated implementation details declared here per D-09 (OD-S1..OD-S7, OD-S13):
  OD-S1 storage mechanism : Python stdlib sqlite3, one SEPARATE embedded local DB
                            file; synchronous=FULL; idempotent schema at
                            initialization; isolation_level=None → explicit
                            BEGIN IMMEDIATE / COMMIT.
  OD-S2 atomic commit     : state record + validation refs + field projections +
                            review item (if REVIEW) are written in ONE
                            transaction — either the complete projection exists
                            or nothing exists (zero residue by construction).
                            Events commit in their own single-purpose
                            transactions.
  OD-S3 invariants        : INV-S-1:1 — at most one state record per
                            (normalization_id, ruleset_fingerprint); INV-R-1:1 —
                            at most one REVIEW item per domain_state_id;
                            in-transaction checks + UNIQUE index backstops.
  OD-S4 ids/clock         : domain_state_id / review_id / event_id = uuid4 hex;
                            clock owned by the service layer.
  OD-S5 integrity anchors : record_fingerprint over record scalars + validation
                            refs (ord order) + field projections (field_name
                            order); item_fingerprint over item scalars;
                            event_fingerprint over event scalars + the previous
                            event fingerprint (per-item hash chain, OD-S13);
                            all verified inside every read (VOR).
  OD-S6 storage gates     : SQL CHECKs — domain_state IN (VALID, INVALID,
                            DEFERRED, UNRESOLVED); disposition IN (CLEAR,
                            REVIEW, REJECT); VALID → CLEAR; UNRESOLVED/DEFERRED
                            → REVIEW; field-projection shape per status;
                            event_type IN (ANNOTATE, CLOSE); partial UNIQUE
                            index: at most one CLOSE per review item; defensive
                            Python-side commit refusal.
  OD-S7 no update/delete  : every row is immutable once committed; no UPDATE or
                            DELETE path exists in this store; the queue
                            lifecycle is append-only event history with derived
                            status.

The store never interprets content semantics — it persists the machine's exact
projection verbatim. Pipeline VALUES are never stored here (pointer pattern,
SPEC §6).
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import List, Optional, Sequence, Tuple

from capture import S1ComputationFailure, S1Service

from .model import (
    DISPOSITION_CLEAR,
    DISPOSITION_REJECT,
    DISPOSITION_REVIEW,
    DOMAIN_STATE_DEFERRED,
    DOMAIN_STATE_INVALID,
    DOMAIN_STATE_UNRESOLVED,
    DOMAIN_STATE_VALID,
    DOMAIN_STATES,
    DISPOSITIONS,
    EVENT_TYPES,
    PROJECTION_STATUSES,
    UNRESOLVED_REASON_D01,
    DomainStateDuplicate,
    DomainStateNotFound,
    DomainStatePersistenceUnavailable,
    DomainStateRecord,
    FieldProjectionRow,
    ReviewQueueEvent,
    ReviewQueueItem,
    StateValidationRef,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS domain_state_records (
    domain_state_id                  TEXT PRIMARY KEY,
    normalization_id                 TEXT NOT NULL,
    extraction_id                    TEXT NOT NULL,
    document_id                      TEXT NOT NULL,
    capture_id                       TEXT NOT NULL,
    capture_s1                       TEXT NOT NULL,
    capture_s1_algorithm_id          TEXT NOT NULL,
    ruleset_id                       TEXT NOT NULL,
    ruleset_version                  TEXT NOT NULL,
    ruleset_fingerprint              TEXT NOT NULL,
    ruleset_fingerprint_algorithm_id TEXT NOT NULL,
    domain_state                     TEXT NOT NULL
                                     CHECK (domain_state IN
                                            ('VALID','INVALID','DEFERRED',
                                             'UNRESOLVED')),
    disposition                      TEXT NOT NULL
                                     CHECK (disposition IN
                                            ('CLEAR','REVIEW','REJECT')),
    state_reason                     TEXT NOT NULL,
    state_detail                     TEXT NOT NULL,
    rule_count                       INTEGER NOT NULL CHECK (rule_count >= 0),
    valid_count                      INTEGER NOT NULL CHECK (valid_count >= 0),
    invalid_count                    INTEGER NOT NULL CHECK (invalid_count >= 0),
    deferred_count                   INTEGER NOT NULL CHECK (deferred_count >= 0),
    unresolved_count                 INTEGER NOT NULL CHECK (unresolved_count >= 0),
    created_at                       TEXT NOT NULL,
    record_fingerprint               TEXT NOT NULL,
    fingerprint_algorithm_id         TEXT NOT NULL,
    -- OD-S6: frozen state ↔ disposition consistency
    CHECK (domain_state != 'VALID' OR disposition = 'CLEAR'),
    CHECK (domain_state != 'UNRESOLVED' OR disposition = 'REVIEW'),
    CHECK (domain_state != 'DEFERRED' OR disposition = 'REVIEW')
);

CREATE TABLE IF NOT EXISTS domain_state_validations (
    domain_state_id     TEXT NOT NULL REFERENCES domain_state_records(domain_state_id),
    ord_slot            INTEGER NOT NULL CHECK (ord_slot >= 0),
    validation_id       TEXT NOT NULL,
    rule_id             TEXT NOT NULL,
    rule_version        TEXT NOT NULL,
    rule_kind           TEXT NOT NULL CHECK (rule_kind IN ('R1','R2')),
    rule_fingerprint    TEXT NOT NULL,
    outcome             TEXT NOT NULL CHECK (outcome IN ('VALID','INVALID','DEFERRED')),
    outcome_reason      TEXT NOT NULL,
    PRIMARY KEY (domain_state_id, ord_slot)
);

CREATE TABLE IF NOT EXISTS domain_state_fields (
    domain_state_id          TEXT NOT NULL REFERENCES domain_state_records(domain_state_id),
    field_name               TEXT NOT NULL,
    projection_status        TEXT NOT NULL
                             CHECK (projection_status IN ('RESOLVED','UNRESOLVED')),
    origin_relayed           TEXT CHECK (origin_relayed IS NULL
                                         OR origin_relayed IN ('NORMALIZED','DERIVED')),
    candidate_count          INTEGER NOT NULL CHECK (candidate_count >= 0),
    source_normalization_id  TEXT NOT NULL,
    source_extraction_id     TEXT NOT NULL,
    source_field_seq         INTEGER,
    source_derivation_id     TEXT,
    unresolved_reason        TEXT,
    detail                   TEXT NOT NULL,
    PRIMARY KEY (domain_state_id, field_name),
    -- OD-S6: RESOLVED rows carry an origin and exactly one pointer kind
    CHECK ((projection_status = 'RESOLVED'
            AND origin_relayed IS NOT NULL
            AND candidate_count >= 1
            AND unresolved_reason IS NULL
            AND ((origin_relayed = 'NORMALIZED' AND source_field_seq IS NOT NULL
                  AND source_derivation_id IS NULL)
              OR (origin_relayed = 'DERIVED' AND source_field_seq IS NULL
                  AND source_derivation_id IS NOT NULL)))
        OR (projection_status = 'UNRESOLVED'
            AND origin_relayed IS NULL
            AND candidate_count = 0
            AND source_field_seq IS NULL
            AND source_derivation_id IS NULL
            AND unresolved_reason = 'd01-no-valid-method'))
);

CREATE TABLE IF NOT EXISTS review_queue_items (
    review_id             TEXT PRIMARY KEY,
    domain_state_id       TEXT NOT NULL REFERENCES domain_state_records(domain_state_id),
    normalization_id      TEXT NOT NULL,
    extraction_id         TEXT NOT NULL,
    document_id           TEXT NOT NULL,
    capture_id            TEXT NOT NULL,
    capture_s1            TEXT NOT NULL,
    ruleset_id            TEXT NOT NULL,
    ruleset_version       TEXT NOT NULL,
    ruleset_fingerprint   TEXT NOT NULL,
    domain_state          TEXT NOT NULL,
    review_reason         TEXT NOT NULL,
    review_detail         TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    item_fingerprint      TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL
);

-- OD-S3: INV-R-1:1 storage-level backstop — one REVIEW item per state record
CREATE UNIQUE INDEX IF NOT EXISTS uq_review_item_state
    ON review_queue_items (domain_state_id);

-- OD-S3: INV-S-1:1 storage-level backstop — one projection per (normalization,
-- ruleset fingerprint)
CREATE UNIQUE INDEX IF NOT EXISTS uq_domain_state_normalization_ruleset
    ON domain_state_records (normalization_id, ruleset_fingerprint);

CREATE TABLE IF NOT EXISTS review_queue_events (
    event_id                TEXT NOT NULL UNIQUE,
    review_id               TEXT NOT NULL REFERENCES review_queue_items(review_id),
    event_seq               INTEGER NOT NULL CHECK (event_seq >= 0),
    event_type              TEXT NOT NULL CHECK (event_type IN ('ANNOTATE','CLOSE')),
    event_note              TEXT NOT NULL,
    event_actor             TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    prev_event_fingerprint  TEXT NOT NULL,
    event_fingerprint       TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL,
    PRIMARY KEY (review_id, event_seq)
);

-- OD-S6: at most ONE CLOSE per review item (terminal — storage backstop)
CREATE UNIQUE INDEX IF NOT EXISTS uq_review_single_close
    ON review_queue_events (review_id) WHERE event_type = 'CLOSE';
"""


def _chunk(value) -> bytes:
    """Deterministic length-prefixed encoding of one canonical element (same
    encoding as the other layers)."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bool):                          # guard: bool before int
        raise TypeError("bool is not a canonical element")
    elif isinstance(value, int):
        raw = str(value).encode("ascii")
    else:
        raise TypeError(f"unsupported canonical element: {type(value)!r}")
    return len(raw).to_bytes(8, "big") + raw


def canonical_state_bytes(record: DomainStateRecord,
                          refs: Sequence[StateValidationRef],
                          fields: Sequence[FieldProjectionRow]) -> bytes:
    """Canonical serialization fingerprinted by OD-S5 (deterministic, total).

    Order is fixed: record scalars, then validation refs in ord_slot order, then
    field projections in field_name order. The same (record, refs, fields) ALWAYS
    yields the same byte sequence — the verified read recomputes exactly this
    over the durable rows.
    """
    parts: List[bytes] = [
        _chunk(record.domain_state_id),
        _chunk(record.normalization_id),
        _chunk(record.extraction_id),
        _chunk(record.document_id),
        _chunk(record.capture_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.ruleset_id),
        _chunk(record.ruleset_version),
        _chunk(record.ruleset_fingerprint),
        _chunk(record.ruleset_fingerprint_algorithm_id),
        _chunk(record.domain_state),
        _chunk(record.disposition),
        _chunk(record.state_reason),
        _chunk(record.state_detail),
        _chunk(record.rule_count),
        _chunk(record.valid_count),
        _chunk(record.invalid_count),
        _chunk(record.deferred_count),
        _chunk(record.unresolved_count),
        _chunk(record.created_at),
    ]
    for ref in refs:
        parts += [
            _chunk(ref.domain_state_id),
            _chunk(ref.ord_slot),
            _chunk(ref.validation_id),
            _chunk(ref.rule_id),
            _chunk(ref.rule_version),
            _chunk(ref.rule_kind),
            _chunk(ref.rule_fingerprint),
            _chunk(ref.outcome),
            _chunk(ref.outcome_reason),
        ]
    for row in fields:
        parts += [
            _chunk(row.domain_state_id),
            _chunk(row.field_name),
            _chunk(row.projection_status),
            _chunk(row.origin_relayed if row.origin_relayed is not None else ""),
            _chunk(row.candidate_count),
            _chunk(row.source_normalization_id),
            _chunk(row.source_extraction_id),
            _chunk(row.source_field_seq if row.source_field_seq is not None else -1),
            _chunk(row.source_derivation_id
                   if row.source_derivation_id is not None else ""),
            _chunk(row.unresolved_reason if row.unresolved_reason is not None
                   else ""),
            _chunk(row.detail),
        ]
    return b"".join(parts)


def canonical_item_bytes(item: ReviewQueueItem) -> bytes:
    """Canonical serialization fingerprinted by OD-S5 (item scalars)."""
    return b"".join([
        _chunk(item.review_id),
        _chunk(item.domain_state_id),
        _chunk(item.normalization_id),
        _chunk(item.extraction_id),
        _chunk(item.document_id),
        _chunk(item.capture_id),
        _chunk(item.capture_s1),
        _chunk(item.ruleset_id),
        _chunk(item.ruleset_version),
        _chunk(item.ruleset_fingerprint),
        _chunk(item.domain_state),
        _chunk(item.review_reason),
        _chunk(item.review_detail),
        _chunk(item.created_at),
    ])


def canonical_event_bytes(event: ReviewQueueEvent) -> bytes:
    """Canonical serialization fingerprinted by OD-S5/OD-S13 (event scalars +
    the chain link)."""
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


def _state_from_row(row: sqlite3.Row) -> DomainStateRecord:
    return DomainStateRecord(
        domain_state_id=row["domain_state_id"],
        normalization_id=row["normalization_id"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        ruleset_id=row["ruleset_id"],
        ruleset_version=row["ruleset_version"],
        ruleset_fingerprint=row["ruleset_fingerprint"],
        ruleset_fingerprint_algorithm_id=row["ruleset_fingerprint_algorithm_id"],
        domain_state=row["domain_state"],
        disposition=row["disposition"],
        state_reason=row["state_reason"],
        state_detail=row["state_detail"],
        rule_count=row["rule_count"],
        valid_count=row["valid_count"],
        invalid_count=row["invalid_count"],
        deferred_count=row["deferred_count"],
        unresolved_count=row["unresolved_count"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _ref_from_row(row: sqlite3.Row) -> StateValidationRef:
    return StateValidationRef(
        domain_state_id=row["domain_state_id"],
        ord_slot=row["ord_slot"],
        validation_id=row["validation_id"],
        rule_id=row["rule_id"],
        rule_version=row["rule_version"],
        rule_kind=row["rule_kind"],
        rule_fingerprint=row["rule_fingerprint"],
        outcome=row["outcome"],
        outcome_reason=row["outcome_reason"],
    )


def _field_from_row(row: sqlite3.Row) -> FieldProjectionRow:
    return FieldProjectionRow(
        domain_state_id=row["domain_state_id"],
        field_name=row["field_name"],
        projection_status=row["projection_status"],
        origin_relayed=row["origin_relayed"],
        candidate_count=row["candidate_count"],
        source_normalization_id=row["source_normalization_id"],
        source_extraction_id=row["source_extraction_id"],
        source_field_seq=row["source_field_seq"],
        source_derivation_id=row["source_derivation_id"],
        unresolved_reason=row["unresolved_reason"],
        detail=row["detail"],
    )


def _item_from_row(row: sqlite3.Row) -> ReviewQueueItem:
    return ReviewQueueItem(
        review_id=row["review_id"],
        domain_state_id=row["domain_state_id"],
        normalization_id=row["normalization_id"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        ruleset_id=row["ruleset_id"],
        ruleset_version=row["ruleset_version"],
        ruleset_fingerprint=row["ruleset_fingerprint"],
        domain_state=row["domain_state"],
        review_reason=row["review_reason"],
        review_detail=row["review_detail"],
        created_at=row["created_at"],
        item_fingerprint=row["item_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _event_from_row(row: sqlite3.Row) -> ReviewQueueEvent:
    return ReviewQueueEvent(
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


class ValidationDomainStore:
    """Durable local store for domain state records + validation refs + field
    projections + REVIEW queue items + append-only events.

    Owns: atomic projection commit, INV-S-1:1 / INV-R-1:1 uniqueness mechanics,
    fingerprint anchoring, deterministic retrieval, event append with hash-chain
    tail management, verified-read raw access. Nothing else — no interpretation,
    no update, no delete.
    """

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        self._conn = sqlite3.connect(self._db_path, timeout=30,
                                     isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-S1: durability over speed
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "ValidationDomainStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- write path: atomic projection commit (OD-S2) ------------------------

    def commit_projection(self, record: DomainStateRecord,
                          refs: Sequence[StateValidationRef],
                          fields: Sequence[FieldProjectionRow],
                          review_item: Optional[ReviewQueueItem]) -> DomainStateRecord:
        """Commit state record + refs + field projections + review item (if any)
        atomically. Raises:
          DomainStateDuplicate              — INV-S-1:1 already present
          DomainStatePersistenceUnavailable — nothing recordable (txn rolled back)
        """
        if record.domain_state not in DOMAIN_STATES:
            raise DomainStatePersistenceUnavailable(
                f"commit refused: domain_state {record.domain_state!r} is outside "
                f"the frozen vocabulary")
        if record.disposition not in DISPOSITIONS:
            raise DomainStatePersistenceUnavailable(
                f"commit refused: disposition {record.disposition!r} is outside "
                f"the declared disposition vocabulary")
        if record.domain_state == DOMAIN_STATE_VALID \
                and record.disposition != DISPOSITION_CLEAR:
            raise DomainStatePersistenceUnavailable(
                "commit refused: VALID must carry CLEAR (frozen state↔disposition "
                "consistency)")
        if record.domain_state in (DOMAIN_STATE_UNRESOLVED, DOMAIN_STATE_DEFERRED) \
                and record.disposition != DISPOSITION_REVIEW:
            raise DomainStatePersistenceUnavailable(
                "commit refused: UNRESOLVED/DEFERRED must carry REVIEW (D-01/AD-04)")
        if review_item is not None and record.disposition != DISPOSITION_REVIEW:
            raise DomainStatePersistenceUnavailable(
                "commit refused: a REVIEW item exists without a REVIEW disposition")
        if review_item is None and record.disposition == DISPOSITION_REVIEW:
            raise DomainStatePersistenceUnavailable(
                "commit refused: REVIEW disposition without a REVIEW item")
        for row in fields:
            if row.projection_status == "UNRESOLVED" \
                    and row.unresolved_reason != UNRESOLVED_REASON_D01:
                raise DomainStatePersistenceUnavailable(
                    "commit refused: UNRESOLVED rows carry exactly the frozen "
                    "d01-no-valid-method reason")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_by_pair_in_txn(record.normalization_id,
                                                     record.ruleset_fingerprint)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise DomainStateDuplicate(existing)
                try:
                    fp = self._s1.compute(canonical_state_bytes(record, refs,
                                                                fields))
                except S1ComputationFailure as exc:
                    self._conn.execute("ROLLBACK")
                    raise DomainStatePersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = DomainStateRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    """INSERT INTO domain_state_records (
                           domain_state_id, normalization_id, extraction_id,
                           document_id, capture_id, capture_s1,
                           capture_s1_algorithm_id, ruleset_id, ruleset_version,
                           ruleset_fingerprint, ruleset_fingerprint_algorithm_id,
                           domain_state, disposition, state_reason, state_detail,
                           rule_count, valid_count, invalid_count, deferred_count,
                           unresolved_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (final.domain_state_id, final.normalization_id,
                     final.extraction_id, final.document_id, final.capture_id,
                     final.capture_s1, final.capture_s1_algorithm_id,
                     final.ruleset_id, final.ruleset_version,
                     final.ruleset_fingerprint,
                     final.ruleset_fingerprint_algorithm_id, final.domain_state,
                     final.disposition, final.state_reason, final.state_detail,
                     final.rule_count, final.valid_count, final.invalid_count,
                     final.deferred_count, final.unresolved_count,
                     final.created_at, final.record_fingerprint,
                     final.fingerprint_algorithm_id))
                self._conn.executemany(
                    """INSERT INTO domain_state_validations (
                           domain_state_id, ord_slot, validation_id, rule_id,
                           rule_version, rule_kind, rule_fingerprint, outcome,
                           outcome_reason)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    [(final.domain_state_id, ref.ord_slot, ref.validation_id,
                      ref.rule_id, ref.rule_version, ref.rule_kind,
                      ref.rule_fingerprint, ref.outcome, ref.outcome_reason)
                     for ref in refs])
                self._conn.executemany(
                    """INSERT INTO domain_state_fields (
                           domain_state_id, field_name, projection_status,
                           origin_relayed, candidate_count,
                           source_normalization_id, source_extraction_id,
                           source_field_seq, source_derivation_id,
                           unresolved_reason, detail)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [(final.domain_state_id, row.field_name,
                      row.projection_status, row.origin_relayed,
                      row.candidate_count, row.source_normalization_id,
                      row.source_extraction_id, row.source_field_seq,
                      row.source_derivation_id, row.unresolved_reason,
                      row.detail) for row in fields])
                if review_item is not None:
                    try:
                        ifp = self._s1.compute(canonical_item_bytes(review_item))
                    except S1ComputationFailure as exc:
                        raise DomainStatePersistenceUnavailable(
                            f"fingerprint capability failure: {exc}") from exc
                    item_final = ReviewQueueItem(
                        **{**review_item.__dict__,
                           "item_fingerprint": ifp.s1,
                           "fingerprint_algorithm_id": ifp.s1_algorithm_id})
                    self._conn.execute(
                        """INSERT INTO review_queue_items (
                               review_id, domain_state_id, normalization_id,
                               extraction_id, document_id, capture_id, capture_s1,
                               ruleset_id, ruleset_version, ruleset_fingerprint,
                               domain_state, review_reason, review_detail,
                               created_at, item_fingerprint,
                               fingerprint_algorithm_id)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (item_final.review_id, item_final.domain_state_id,
                         item_final.normalization_id, item_final.extraction_id,
                         item_final.document_id, item_final.capture_id,
                         item_final.capture_s1, item_final.ruleset_id,
                         item_final.ruleset_version,
                         item_final.ruleset_fingerprint, item_final.domain_state,
                         item_final.review_reason, item_final.review_detail,
                         item_final.created_at, item_final.item_fingerprint,
                         item_final.fingerprint_algorithm_id))
                self._conn.execute("COMMIT")
                return final
            except DomainStateDuplicate:
                raise                                  # already rolled back above
            except Exception:
                # Any other failure inside the txn → nothing persisted (OD-S2).
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except DomainStateDuplicate:
            raise
        except sqlite3.Error as exc:
            raise DomainStatePersistenceUnavailable(f"commit failed: {exc}") from exc

    # -- write path: append-only event (OD-S7/OD-S13) -------------------------

    def append_event(self, event: ReviewQueueEvent) -> ReviewQueueEvent:
        """Append one lifecycle event (single-purpose txn). The caller has
        already verified the item, the chain tail, and terminality. Raises:
          DomainStatePersistenceUnavailable — nothing appended (txn rolled back)
        """
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                try:
                    efp = self._s1.compute(canonical_event_bytes(event))
                except S1ComputationFailure as exc:
                    self._conn.execute("ROLLBACK")
                    raise DomainStatePersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = ReviewQueueEvent(
                    **{**event.__dict__,
                       "event_fingerprint": efp.s1,
                       "fingerprint_algorithm_id": efp.s1_algorithm_id})
                self._conn.execute(
                    """INSERT INTO review_queue_events (
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
            raise DomainStatePersistenceUnavailable(f"event append failed: {exc}") \
                from exc

    # -- read path (raw, verified-read-orchestrated) -------------------------

    def get_record(self, domain_state_id: str) -> DomainStateRecord:
        row = self._conn.execute(
            "SELECT * FROM domain_state_records WHERE domain_state_id = ?",
            (domain_state_id,)).fetchone()
        if row is None:
            raise DomainStateNotFound(domain_state_id)
        return _state_from_row(row)

    def get_refs(self, domain_state_id: str) -> List[StateValidationRef]:
        rows = self._conn.execute(
            "SELECT * FROM domain_state_validations WHERE domain_state_id = ? "
            "ORDER BY ord_slot", (domain_state_id,)).fetchall()
        return [_ref_from_row(r) for r in rows]

    def get_fields(self, domain_state_id: str) -> List[FieldProjectionRow]:
        rows = self._conn.execute(
            "SELECT * FROM domain_state_fields WHERE domain_state_id = ? "
            "ORDER BY field_name", (domain_state_id,)).fetchall()
        return [_field_from_row(r) for r in rows]

    def get_review_item(self, domain_state_id: str) -> Optional[ReviewQueueItem]:
        row = self._conn.execute(
            "SELECT * FROM review_queue_items WHERE domain_state_id = ?",
            (domain_state_id,)).fetchone()
        return None if row is None else _item_from_row(row)

    def get_item_by_review_id(self, review_id: str) -> ReviewQueueItem:
        row = self._conn.execute(
            "SELECT * FROM review_queue_items WHERE review_id = ?",
            (review_id,)).fetchone()
        if row is None:
            raise DomainStateNotFound(review_id)
        return _item_from_row(row)

    def get_events(self, review_id: str) -> List[ReviewQueueEvent]:
        rows = self._conn.execute(
            "SELECT * FROM review_queue_events WHERE review_id = ? "
            "ORDER BY event_seq", (review_id,)).fetchall()
        return [_event_from_row(r) for r in rows]

    def chain_tail(self, review_id: str) -> Optional[str]:
        """The last event fingerprint of the item's chain (None if empty)."""
        row = self._conn.execute(
            """SELECT event_fingerprint FROM review_queue_events
               WHERE review_id = ? ORDER BY event_seq DESC LIMIT 1""",
            (review_id,)).fetchone()
        return None if row is None else row["event_fingerprint"]

    def has_close_event(self, review_id: str) -> bool:
        row = self._conn.execute(
            """SELECT 1 FROM review_queue_events
               WHERE review_id = ? AND event_type = 'CLOSE' LIMIT 1""",
            (review_id,)).fetchone()
        return row is not None

    def find_by_pair(self, normalization_id: str,
                     ruleset_fingerprint: str) -> Optional[str]:
        """INV-S-1:1 lookup — the domain_state_id for an exact pair, else None."""
        return self._find_by_pair_in_txn(normalization_id, ruleset_fingerprint)

    def _find_by_pair_in_txn(self, normalization_id: str,
                             ruleset_fingerprint: str) -> Optional[str]:
        row = self._conn.execute(
            """SELECT domain_state_id FROM domain_state_records
               WHERE normalization_id = ? AND ruleset_fingerprint = ?""",
            (normalization_id, ruleset_fingerprint)).fetchone()
        return None if row is None else row["domain_state_id"]

    def states_for_normalization(self, normalization_id: str) -> List[str]:
        """All domain_state_ids for a normalization — deterministic order."""
        rows = self._conn.execute(
            """SELECT domain_state_id FROM domain_state_records
               WHERE normalization_id = ? ORDER BY created_at, domain_state_id""",
            (normalization_id,)).fetchall()
        return [r["domain_state_id"] for r in rows]

    def list_review_ids(self) -> List[str]:
        """All review item ids — deterministic order (creation order)."""
        rows = self._conn.execute(
            "SELECT review_id FROM review_queue_items "
            "ORDER BY created_at, review_id").fetchall()
        return [r["review_id"] for r in rows]
