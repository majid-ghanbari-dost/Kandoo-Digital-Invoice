"""Durable Validation Store — WP-5.1 MVP implementation.

Binding basis: SPEC-WP51-VAL §9 over the frozen WP-1.1/WP-2.1/WP-3.1/WP-4.1/WP-4.2
store pattern (same governance, new layer — upstream stores are NOT modified; layer
boundary).

Delegated implementation details declared here per D-09 (OD-V1..OD-V7):
  OD-V1 storage mechanism : Python stdlib sqlite3, one SEPARATE embedded local DB
                            file (durable, local, zero network dependency);
                            synchronous=FULL; idempotent schema at initialization;
                            isolation_level=None → explicit BEGIN IMMEDIATE / COMMIT.
  OD-V2 atomic commit     : validation record + input-ref rows are written in ONE
                            transaction — either the complete record exists or
                            nothing exists (zero residue by construction).
  OD-V3 INV-V-1:1         : at most one record per (normalization_id, rule_id,
                            rule_version) — in-transaction uniqueness check + UNIQUE
                            index backstop. A different rule version is a DIFFERENT
                            record.
  OD-V4 ids/clock         : validation_id = uuid4 hex; single layer clock
                            (model.utc_now_iso).
  OD-V5 integrity anchor  : record_fingerprint = sha256-v1 (reused capture S1
                            capability) over the canonical serialization of the record
                            scalars (rounding fields included) + all input-ref rows in
                            input_slot order — verified on every read (VOR).
  OD-V6 storage gates     : SQL CHECKs — outcome IN ('VALID','INVALID','DEFERRED')
                            (UNRESOLVED can never be stored in this layer);
                            rule_kind IN ('R1','R2'); rounding fields all-NULL iff
                            rounding_applied = 0 and all-NOT-NULL iff = 1;
                            rule_kind = 'R1' → rounding_applied = 0 (R1 can never
                            round); input-row origin/pointer consistency; defensive
                            Python-side commit refusal.
  OD-V7 no update/delete  : validation records are immutable once committed; no
                            UPDATE or DELETE path exists in this store.

The store never interprets content semantics — it persists the engine's exact verdict
verbatim. Input VALUES are never stored here (pointer pattern, SPEC §6).
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import List, Optional, Sequence, Tuple

from capture import S1ComputationFailure, S1Service

from .model import (
    OUTCOME_DEFERRED,
    OUTCOME_INVALID,
    OUTCOME_VALID,
    VALUE_ORIGIN_DERIVED,
    VALUE_ORIGIN_NORMALIZED,
    ValidationDuplicate,
    ValidationInputRef,
    ValidationNotFound,
    ValidationPersistenceUnavailable,
    ValidationRecord,
    utc_now_iso,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS validation_records (
    validation_id                     TEXT PRIMARY KEY,
    normalization_id                  TEXT NOT NULL,
    extraction_id                     TEXT NOT NULL,
    document_id                       TEXT NOT NULL,
    capture_id                        TEXT NOT NULL,
    capture_s1                        TEXT NOT NULL,
    capture_s1_algorithm_id           TEXT NOT NULL,
    ruleset_id                        TEXT NOT NULL,
    ruleset_version                   TEXT NOT NULL,
    rule_id                           TEXT NOT NULL,
    rule_version                      TEXT NOT NULL,
    rule_kind                         TEXT NOT NULL CHECK (rule_kind IN ('R1','R2')),
    rule_type                         TEXT NOT NULL,
    rule_fingerprint                  TEXT NOT NULL,
    rule_fingerprint_algorithm_id     TEXT NOT NULL,
    outcome                           TEXT NOT NULL
                                      CHECK (outcome IN ('VALID','INVALID','DEFERRED')),
    outcome_reason                    TEXT NOT NULL,
    outcome_detail                    TEXT NOT NULL,
    rounding_applied                  INTEGER NOT NULL CHECK (rounding_applied IN (0,1)),
    rounding_precision                INTEGER,
    rounding_mode                     TEXT,
    rounding_input_value              TEXT,
    rounding_output_value             TEXT,
    input_count                       INTEGER NOT NULL CHECK (input_count >= 0),
    created_at                        TEXT NOT NULL,
    record_fingerprint                TEXT NOT NULL,
    fingerprint_algorithm_id          TEXT NOT NULL,
    -- OD-V6: rounding fields all-NULL iff rounding_applied = 0, all-set iff = 1
    CHECK ((rounding_applied = 0 AND rounding_precision IS NULL
            AND rounding_mode IS NULL AND rounding_input_value IS NULL
            AND rounding_output_value IS NULL)
        OR (rounding_applied = 1 AND rounding_precision IS NOT NULL
            AND rounding_mode IS NOT NULL AND rounding_input_value IS NOT NULL
            AND rounding_output_value IS NOT NULL)),
    -- OD-V6: R1 can never round (parametric rounding is R2-only, D-08)
    CHECK (rule_kind != 'R1' OR rounding_applied = 0)
);

CREATE TABLE IF NOT EXISTS validation_inputs (
    validation_id             TEXT NOT NULL REFERENCES validation_records(validation_id),
    input_slot                INTEGER NOT NULL CHECK (input_slot >= 0),
    slot_name                 TEXT NOT NULL,
    field_name                TEXT NOT NULL,
    value_origin              TEXT NOT NULL
                              CHECK (value_origin IN ('NORMALIZED','DERIVED')),
    source_normalization_id   TEXT NOT NULL,
    source_extraction_id      TEXT NOT NULL,
    source_field_seq          INTEGER,
    source_derivation_id      TEXT,
    PRIMARY KEY (validation_id, input_slot),
    -- OD-V6: pointer-shape consistency per origin
    CHECK ((value_origin = 'NORMALIZED' AND source_field_seq IS NOT NULL
            AND source_derivation_id IS NULL)
        OR (value_origin = 'DERIVED' AND source_field_seq IS NULL
            AND source_derivation_id IS NOT NULL))
);

-- OD-V3: INV-V-1:1 storage-level backstop — at most one validation per triple,
-- enforced by SQLite itself, under any concurrency, on any path.
CREATE UNIQUE INDEX IF NOT EXISTS uq_validation_normalization_rule
    ON validation_records (normalization_id, rule_id, rule_version);

-- normalization-scoped enumeration (consumer: WP-5.2 Validation State Machine later)
CREATE INDEX IF NOT EXISTS ix_validation_normalization
    ON validation_records (normalization_id);
"""


def _chunk(value) -> bytes:
    """Deterministic length-prefixed encoding of one canonical element (same encoding
    as the other layers)."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bool):                          # guard: bool before int
        raise TypeError("bool is not a canonical element")
    elif isinstance(value, int):
        raw = str(value).encode("ascii")
    else:
        raise TypeError(f"unsupported canonical element: {type(value)!r}")
    return len(raw).to_bytes(8, "big") + raw


def canonical_validation_bytes(record: ValidationRecord,
                               inputs: Sequence[ValidationInputRef]) -> bytes:
    """Canonical serialization fingerprinted by OD-V5 (deterministic, total).

    Order is fixed: record scalars (rounding fields included), then input refs in
    input_slot order. The same (record, inputs) ALWAYS yields the same byte sequence
    — the verified read recomputes exactly this over the durable rows.
    """
    parts: List[bytes] = [
        _chunk(record.validation_id),
        _chunk(record.normalization_id),
        _chunk(record.extraction_id),
        _chunk(record.document_id),
        _chunk(record.capture_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.ruleset_id),
        _chunk(record.ruleset_version),
        _chunk(record.rule_id),
        _chunk(record.rule_version),
        _chunk(record.rule_kind),
        _chunk(record.rule_type),
        _chunk(record.rule_fingerprint),
        _chunk(record.rule_fingerprint_algorithm_id),
        _chunk(record.outcome),
        _chunk(record.outcome_reason),
        _chunk(record.outcome_detail),
        _chunk(record.rounding_applied),
        _chunk(record.rounding_precision if record.rounding_precision is not None
               else -1),
        _chunk(record.rounding_mode if record.rounding_mode is not None else ""),
        _chunk(record.rounding_input_value
               if record.rounding_input_value is not None else ""),
        _chunk(record.rounding_output_value
               if record.rounding_output_value is not None else ""),
        _chunk(record.input_count),
        _chunk(record.created_at),
    ]
    for ref in inputs:
        parts += [
            _chunk(ref.input_slot),
            _chunk(ref.slot_name),
            _chunk(ref.field_name),
            _chunk(ref.value_origin),
            _chunk(ref.source_normalization_id),
            _chunk(ref.source_extraction_id),
            _chunk(ref.source_field_seq if ref.source_field_seq is not None else -1),
            _chunk(ref.source_derivation_id
                   if ref.source_derivation_id is not None else ""),
        ]
    return b"".join(parts)


def _record_from_row(row: sqlite3.Row) -> ValidationRecord:
    return ValidationRecord(
        validation_id=row["validation_id"],
        normalization_id=row["normalization_id"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        ruleset_id=row["ruleset_id"],
        ruleset_version=row["ruleset_version"],
        rule_id=row["rule_id"],
        rule_version=row["rule_version"],
        rule_kind=row["rule_kind"],
        rule_type=row["rule_type"],
        rule_fingerprint=row["rule_fingerprint"],
        rule_fingerprint_algorithm_id=row["rule_fingerprint_algorithm_id"],
        outcome=row["outcome"],
        outcome_reason=row["outcome_reason"],
        outcome_detail=row["outcome_detail"],
        rounding_applied=row["rounding_applied"],
        rounding_precision=row["rounding_precision"],
        rounding_mode=row["rounding_mode"],
        rounding_input_value=row["rounding_input_value"],
        rounding_output_value=row["rounding_output_value"],
        input_count=row["input_count"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _input_from_row(row: sqlite3.Row) -> ValidationInputRef:
    return ValidationInputRef(
        input_slot=row["input_slot"],
        slot_name=row["slot_name"],
        field_name=row["field_name"],
        value_origin=row["value_origin"],
        source_normalization_id=row["source_normalization_id"],
        source_extraction_id=row["source_extraction_id"],
        source_field_seq=row["source_field_seq"],
        source_derivation_id=row["source_derivation_id"],
    )


class ValidationStore:
    """Durable local store for validation records + input pointer rows.

    Owns: atomic record+inputs commit, INV-V-1:1 uniqueness mechanics, fingerprint
    anchoring, deterministic retrieval (inputs by input_slot, ids per normalization),
    verified-read raw access. Nothing else — no interpretation, no update, no delete.
    """

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        self._conn = sqlite3.connect(self._db_path, timeout=30, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-V1: durability over speed
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "ValidationStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- write path (single atomic transaction — OD-V2) ----------------------

    def commit_validation(
        self,
        normalization_id: str,
        extraction_id: str,
        document_id: str,
        capture_id: str,
        capture_s1: str,
        capture_s1_algorithm_id: str,
        ruleset_id: str,
        ruleset_version: str,
        rule_id: str,
        rule_version: str,
        rule_kind: str,
        rule_type: str,
        rule_fingerprint: str,
        rule_fingerprint_algorithm_id: str,
        outcome: str,
        outcome_reason: str,
        outcome_detail: str,
        rounding_applied: int,
        rounding_precision: Optional[int],
        rounding_mode: Optional[str],
        rounding_input_value: Optional[str],
        rounding_output_value: Optional[str],
        inputs: Sequence[ValidationInputRef],
    ) -> ValidationRecord:
        """Commit record + input refs atomically. Raises:
          ValidationDuplicate              — INV-V-1:1 triple already present
          ValidationPersistenceUnavailable — nothing recordable (txn rolled back)
        """
        if outcome not in (OUTCOME_VALID, OUTCOME_INVALID, OUTCOME_DEFERRED):
            raise ValidationPersistenceUnavailable(
                f"commit refused: outcome {outcome!r} is outside the declared "
                f"validation vocabulary (UNRESOLVED can never be stored here)")
        for ref in inputs:
            if (ref.source_normalization_id != normalization_id
                    or ref.source_extraction_id != extraction_id):
                raise ValidationPersistenceUnavailable(
                    "commit refused: input pointers must stay inside the source "
                    "normalization record (no cross-record/cross-document inputs)")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_by_triple_in_txn(normalization_id, rule_id,
                                                       rule_version)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise ValidationDuplicate(existing)
                validation_id = uuid.uuid4().hex
                created_at = utc_now_iso()
                draft = ValidationRecord(
                    validation_id=validation_id,
                    normalization_id=normalization_id,
                    extraction_id=extraction_id,
                    document_id=document_id,
                    capture_id=capture_id,
                    capture_s1=capture_s1,
                    capture_s1_algorithm_id=capture_s1_algorithm_id,
                    ruleset_id=ruleset_id,
                    ruleset_version=ruleset_version,
                    rule_id=rule_id,
                    rule_version=rule_version,
                    rule_kind=rule_kind,
                    rule_type=rule_type,
                    rule_fingerprint=rule_fingerprint,
                    rule_fingerprint_algorithm_id=rule_fingerprint_algorithm_id,
                    outcome=outcome,
                    outcome_reason=outcome_reason,
                    outcome_detail=outcome_detail,
                    rounding_applied=rounding_applied,
                    rounding_precision=rounding_precision,
                    rounding_mode=rounding_mode,
                    rounding_input_value=rounding_input_value,
                    rounding_output_value=rounding_output_value,
                    input_count=len(inputs),
                    created_at=created_at,
                    record_fingerprint="",            # anchored below
                    fingerprint_algorithm_id="",
                )
                try:
                    fp = self._s1.compute(canonical_validation_bytes(draft, inputs))
                except S1ComputationFailure as exc:
                    self._conn.execute("ROLLBACK")
                    raise ValidationPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = ValidationRecord(
                    **{**draft.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    """INSERT INTO validation_records (
                           validation_id, normalization_id, extraction_id,
                           document_id, capture_id, capture_s1,
                           capture_s1_algorithm_id, ruleset_id, ruleset_version,
                           rule_id, rule_version, rule_kind, rule_type,
                           rule_fingerprint, rule_fingerprint_algorithm_id,
                           outcome, outcome_reason, outcome_detail,
                           rounding_applied, rounding_precision, rounding_mode,
                           rounding_input_value, rounding_output_value,
                           input_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (final.validation_id, final.normalization_id,
                     final.extraction_id, final.document_id, final.capture_id,
                     final.capture_s1, final.capture_s1_algorithm_id,
                     final.ruleset_id, final.ruleset_version, final.rule_id,
                     final.rule_version, final.rule_kind, final.rule_type,
                     final.rule_fingerprint, final.rule_fingerprint_algorithm_id,
                     final.outcome, final.outcome_reason, final.outcome_detail,
                     final.rounding_applied, final.rounding_precision,
                     final.rounding_mode, final.rounding_input_value,
                     final.rounding_output_value, final.input_count,
                     final.created_at, final.record_fingerprint,
                     final.fingerprint_algorithm_id))
                self._conn.executemany(
                    """INSERT INTO validation_inputs (
                           validation_id, input_slot, slot_name, field_name,
                           value_origin, source_normalization_id,
                           source_extraction_id, source_field_seq,
                           source_derivation_id)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    [(final.validation_id, ref.input_slot, ref.slot_name,
                      ref.field_name, ref.value_origin,
                      ref.source_normalization_id, ref.source_extraction_id,
                      ref.source_field_seq, ref.source_derivation_id)
                     for ref in inputs])
                self._conn.execute("COMMIT")
                return final
            except ValidationDuplicate:
                raise                                  # already rolled back above
            except Exception:
                # Any other failure inside the txn → nothing persisted (OD-V2 atomicity).
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except ValidationDuplicate:
            raise
        except sqlite3.Error as exc:
            raise ValidationPersistenceUnavailable(f"commit failed: {exc}") from exc

    # -- read path (raw, verified-read-orchestrated) -------------------------

    def get_record(self, validation_id: str) -> ValidationRecord:
        row = self._conn.execute(
            "SELECT * FROM validation_records WHERE validation_id = ?",
            (validation_id,)).fetchone()
        if row is None:
            raise ValidationNotFound(validation_id)
        return _record_from_row(row)

    def get_inputs(self, validation_id: str) -> List[ValidationInputRef]:
        rows = self._conn.execute(
            "SELECT * FROM validation_inputs WHERE validation_id = ? "
            "ORDER BY input_slot", (validation_id,)).fetchall()
        return [_input_from_row(r) for r in rows]

    def find_by_triple(self, normalization_id: str, rule_id: str,
                       rule_version: str) -> Optional[str]:
        """INV-V-1:1 lookup — the validation_id for an exact triple, else None."""
        return self._find_by_triple_in_txn(normalization_id, rule_id, rule_version)

    def _find_by_triple_in_txn(self, normalization_id: str, rule_id: str,
                               rule_version: str) -> Optional[str]:
        row = self._conn.execute(
            """SELECT validation_id FROM validation_records
               WHERE normalization_id = ? AND rule_id = ? AND rule_version = ?""",
            (normalization_id, rule_id, rule_version)).fetchone()
        return None if row is None else row["validation_id"]

    def find_for_normalization(self, normalization_id: str) -> List[str]:
        """All validation_ids for a normalization — deterministic order."""
        rows = self._conn.execute(
            """SELECT validation_id FROM validation_records
               WHERE normalization_id = ? ORDER BY created_at, validation_id""",
            (normalization_id,)).fetchall()
        return [r["validation_id"] for r in rows]
