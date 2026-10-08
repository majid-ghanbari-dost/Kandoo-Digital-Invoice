"""Durable Derivation Store — WP-4.2 MVP implementation.

Binding basis: SPEC-WP42-DER §9 over the frozen WP-1.1/WP-2.1/WP-3.1/WP-4.1 store
pattern (same governance, new layer — upstream stores are NOT modified; layer boundary).

Delegated implementation details declared here per D-09 (OD-D1..OD-D7):
  OD-D1 storage mechanism : Python stdlib sqlite3, one SEPARATE embedded local DB file
                            (durable, local, zero network dependency); synchronous=FULL;
                            idempotent schema at initialization; isolation_level=None →
                            explicit BEGIN IMMEDIATE / COMMIT.
  OD-D2 atomic commit     : record + input-ref rows are written in ONE transaction —
                            either the complete derivation record exists or nothing
                            exists (zero residue by construction).
  OD-D3 INV-D-1:1         : at most one record per (normalization_id, formula_id,
                            formula_version) — in-transaction uniqueness check + UNIQUE
                            index backstop. A different formula or version is a
                            DIFFERENT record.
  OD-D4 ids/clock         : derivation_id = uuid4 hex; single layer clock
                            (model.utc_now_iso).
  OD-D5 integrity anchor  : record_fingerprint = sha256-v1 (reused capture S1
                            capability) over the canonical serialization of the record
                            scalars + all input-ref rows in input_slot order — verified
                            on every read (VOR).
  OD-D6 storage gates     : SQL CHECKs — output_provenance = 'DERIVED' ONLY (D-01:
                            UNRESOLVED can never be stored in this layer);
                            input_count >= 1; input rows input_slot >= 0 / field_seq
                            >= 0; plus defensive Python-side commit refusal.
  OD-D7 no update/delete  : derivation records are immutable once committed; no UPDATE
                            or DELETE path exists in this store.

The store never interprets content semantics — it persists the engine's exact result
verbatim. Input VALUES are never stored here (pointer pattern, SPEC §6).
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import List, Optional, Sequence, Tuple

from capture import S1ComputationFailure, S1Service

from .model import (
    DerivationDuplicate,
    DerivationInputRef,
    DerivationNotFound,
    DerivationPersistenceUnavailable,
    DerivationRecord,
    OUTPUT_PROVENANCE_DERIVED,
    utc_now_iso,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS derivation_records (
    derivation_id                     TEXT PRIMARY KEY,
    normalization_id                  TEXT NOT NULL,
    extraction_id                     TEXT NOT NULL,
    document_id                       TEXT NOT NULL,
    capture_id                        TEXT NOT NULL,
    capture_s1                        TEXT NOT NULL,
    capture_s1_algorithm_id           TEXT NOT NULL,
    ruleset_id                        TEXT NOT NULL,
    ruleset_version                   TEXT NOT NULL,
    formula_id                        TEXT NOT NULL,
    formula_version                   TEXT NOT NULL,
    formula_fingerprint               TEXT NOT NULL,
    formula_fingerprint_algorithm_id  TEXT NOT NULL,
    output_field_name                 TEXT NOT NULL,
    output_provenance                 TEXT NOT NULL CHECK (output_provenance = 'DERIVED'),
    output_value                      TEXT NOT NULL,
    input_count                       INTEGER NOT NULL CHECK (input_count >= 1),
    created_at                        TEXT NOT NULL,
    record_fingerprint                TEXT NOT NULL,
    fingerprint_algorithm_id          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS derivation_inputs (
    derivation_id             TEXT NOT NULL REFERENCES derivation_records(derivation_id),
    input_slot                INTEGER NOT NULL CHECK (input_slot >= 0),
    slot_name                 TEXT NOT NULL,
    field_name                TEXT NOT NULL,
    source_normalization_id   TEXT NOT NULL,
    field_seq                 INTEGER NOT NULL CHECK (field_seq >= 0),
    source_extraction_id      TEXT NOT NULL,
    PRIMARY KEY (derivation_id, input_slot)
);

-- OD-D3: INV-D-1:1 storage-level backstop — at most one derivation per triple,
-- enforced by SQLite itself, under any concurrency, on any path.
CREATE UNIQUE INDEX IF NOT EXISTS uq_derivation_normalization_formula
    ON derivation_records (normalization_id, formula_id, formula_version);

-- normalization-scoped enumeration (traceability consumer: Canonicalization Gate later)
CREATE INDEX IF NOT EXISTS ix_derivation_normalization
    ON derivation_records (normalization_id);
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


def canonical_derivation_bytes(record: DerivationRecord,
                               inputs: Sequence[DerivationInputRef]) -> bytes:
    """Canonical serialization fingerprinted by OD-D5 (deterministic, total).

    Order is fixed: record scalars, then input refs in input_slot order. The same
    (record, inputs) ALWAYS yields the same byte sequence — the verified read
    recomputes exactly this over the durable rows.
    """
    parts: List[bytes] = [
        _chunk(record.derivation_id),
        _chunk(record.normalization_id),
        _chunk(record.extraction_id),
        _chunk(record.document_id),
        _chunk(record.capture_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.ruleset_id),
        _chunk(record.ruleset_version),
        _chunk(record.formula_id),
        _chunk(record.formula_version),
        _chunk(record.formula_fingerprint),
        _chunk(record.formula_fingerprint_algorithm_id),
        _chunk(record.output_field_name),
        _chunk(record.output_provenance),
        _chunk(record.output_value),
        _chunk(record.input_count),
        _chunk(record.created_at),
    ]
    for ref in inputs:
        parts += [
            _chunk(ref.input_slot),
            _chunk(ref.slot_name),
            _chunk(ref.field_name),
            _chunk(ref.source_normalization_id),
            _chunk(ref.field_seq),
            _chunk(ref.source_extraction_id),
        ]
    return b"".join(parts)


def _record_from_row(row: sqlite3.Row) -> DerivationRecord:
    return DerivationRecord(
        derivation_id=row["derivation_id"],
        normalization_id=row["normalization_id"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        ruleset_id=row["ruleset_id"],
        ruleset_version=row["ruleset_version"],
        formula_id=row["formula_id"],
        formula_version=row["formula_version"],
        formula_fingerprint=row["formula_fingerprint"],
        formula_fingerprint_algorithm_id=row["formula_fingerprint_algorithm_id"],
        output_field_name=row["output_field_name"],
        output_provenance=row["output_provenance"],
        output_value=row["output_value"],
        input_count=row["input_count"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _input_from_row(row: sqlite3.Row) -> DerivationInputRef:
    return DerivationInputRef(
        input_slot=row["input_slot"],
        slot_name=row["slot_name"],
        field_name=row["field_name"],
        source_normalization_id=row["source_normalization_id"],
        field_seq=row["field_seq"],
        source_extraction_id=row["source_extraction_id"],
    )


class DerivationStore:
    """Durable local store for derivation records + input pointer rows.

    Owns: atomic record+inputs commit, INV-D-1:1 uniqueness mechanics, fingerprint
    anchoring, deterministic retrieval (inputs by input_slot, ids per normalization),
    verified-read raw access. Nothing else — no interpretation, no update, no delete.
    """

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        self._conn = sqlite3.connect(self._db_path, timeout=30, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-D1: durability over speed
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "DerivationStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- write path (single atomic transaction — OD-D2) ----------------------

    def commit_derivation(
        self,
        normalization_id: str,
        extraction_id: str,
        document_id: str,
        capture_id: str,
        capture_s1: str,
        capture_s1_algorithm_id: str,
        ruleset_id: str,
        ruleset_version: str,
        formula_id: str,
        formula_version: str,
        formula_fingerprint: str,
        formula_fingerprint_algorithm_id: str,
        output_field_name: str,
        output_value: str,
        inputs: Sequence[DerivationInputRef],
    ) -> DerivationRecord:
        """Commit record + input refs atomically. Raises:
          DerivationDuplicate              — INV-D-1:1 triple already present
          DerivationPersistenceUnavailable — nothing recordable (txn rolled back)
        """
        if not inputs:
            # Defense in depth on top of the SQL CHECKs (OD-D6): a derivation without
            # consumed inputs can never exist.
            raise DerivationPersistenceUnavailable(
                "commit refused: a derivation must consume at least one declared input")
        for ref in inputs:
            if (ref.source_normalization_id != normalization_id
                    or ref.source_extraction_id != extraction_id):
                raise DerivationPersistenceUnavailable(
                    "commit refused: input pointers must stay inside the source "
                    "normalization record (no cross-record/cross-document inputs)")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_by_triple_in_txn(normalization_id, formula_id,
                                                       formula_version)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise DerivationDuplicate(existing)
                derivation_id = uuid.uuid4().hex
                created_at = utc_now_iso()
                draft = DerivationRecord(
                    derivation_id=derivation_id,
                    normalization_id=normalization_id,
                    extraction_id=extraction_id,
                    document_id=document_id,
                    capture_id=capture_id,
                    capture_s1=capture_s1,
                    capture_s1_algorithm_id=capture_s1_algorithm_id,
                    ruleset_id=ruleset_id,
                    ruleset_version=ruleset_version,
                    formula_id=formula_id,
                    formula_version=formula_version,
                    formula_fingerprint=formula_fingerprint,
                    formula_fingerprint_algorithm_id=formula_fingerprint_algorithm_id,
                    output_field_name=output_field_name,
                    output_provenance=OUTPUT_PROVENANCE_DERIVED,
                    output_value=output_value,
                    input_count=len(inputs),
                    created_at=created_at,
                    record_fingerprint="",            # anchored below
                    fingerprint_algorithm_id="",
                )
                try:
                    fp = self._s1.compute(canonical_derivation_bytes(draft, inputs))
                except S1ComputationFailure as exc:
                    self._conn.execute("ROLLBACK")
                    raise DerivationPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = DerivationRecord(
                    **{**draft.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    """INSERT INTO derivation_records (
                           derivation_id, normalization_id, extraction_id, document_id,
                           capture_id, capture_s1, capture_s1_algorithm_id,
                           ruleset_id, ruleset_version, formula_id, formula_version,
                           formula_fingerprint, formula_fingerprint_algorithm_id,
                           output_field_name, output_provenance, output_value,
                           input_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (final.derivation_id, final.normalization_id, final.extraction_id,
                     final.document_id, final.capture_id, final.capture_s1,
                     final.capture_s1_algorithm_id, final.ruleset_id,
                     final.ruleset_version, final.formula_id, final.formula_version,
                     final.formula_fingerprint, final.formula_fingerprint_algorithm_id,
                     final.output_field_name, final.output_provenance,
                     final.output_value, final.input_count, final.created_at,
                     final.record_fingerprint, final.fingerprint_algorithm_id))
                self._conn.executemany(
                    """INSERT INTO derivation_inputs (
                           derivation_id, input_slot, slot_name, field_name,
                           source_normalization_id, field_seq, source_extraction_id)
                       VALUES (?,?,?,?,?,?,?)""",
                    [(final.derivation_id, ref.input_slot, ref.slot_name,
                      ref.field_name, ref.source_normalization_id, ref.field_seq,
                      ref.source_extraction_id) for ref in inputs])
                self._conn.execute("COMMIT")
                return final
            except DerivationDuplicate:
                raise                                  # already rolled back above
            except Exception:
                # Any other failure inside the txn → nothing persisted (OD-D2 atomicity).
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except DerivationDuplicate:
            raise
        except sqlite3.Error as exc:
            raise DerivationPersistenceUnavailable(f"commit failed: {exc}") from exc

    # -- read path (raw, verified-read-orchestrated) -------------------------

    def get_record(self, derivation_id: str) -> DerivationRecord:
        row = self._conn.execute(
            "SELECT * FROM derivation_records WHERE derivation_id = ?",
            (derivation_id,)).fetchone()
        if row is None:
            raise DerivationNotFound(derivation_id)
        return _record_from_row(row)

    def get_inputs(self, derivation_id: str) -> List[DerivationInputRef]:
        rows = self._conn.execute(
            "SELECT * FROM derivation_inputs WHERE derivation_id = ? "
            "ORDER BY input_slot", (derivation_id,)).fetchall()
        return [_input_from_row(r) for r in rows]

    def find_by_triple(self, normalization_id: str, formula_id: str,
                       formula_version: str) -> Optional[str]:
        """INV-D-1:1 lookup — the derivation_id for an exact triple, else None."""
        return self._find_by_triple_in_txn(normalization_id, formula_id, formula_version)

    def _find_by_triple_in_txn(self, normalization_id: str, formula_id: str,
                               formula_version: str) -> Optional[str]:
        row = self._conn.execute(
            """SELECT derivation_id FROM derivation_records
               WHERE normalization_id = ? AND formula_id = ? AND formula_version = ?""",
            (normalization_id, formula_id, formula_version)).fetchone()
        return None if row is None else row["derivation_id"]

    def find_for_normalization(self, normalization_id: str) -> List[str]:
        """All derivation_ids for a normalization — deterministic order."""
        rows = self._conn.execute(
            """SELECT derivation_id FROM derivation_records
               WHERE normalization_id = ? ORDER BY created_at, derivation_id""",
            (normalization_id,)).fetchall()
        return [r["derivation_id"] for r in rows]
