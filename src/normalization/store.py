"""Durable Normalization Store — WP-4.1 MVP implementation.

Binding basis: SPEC-WP41-NORM §7 over the frozen WP-1.1/WP-2.1/WP-3.1 store pattern
(same governance, new layer — upstream stores are NOT modified; AD-02 layer boundary).

Delegated implementation details declared here per D-09 (OD-N1..OD-N7):
  OD-N1 storage mechanism : Python stdlib sqlite3, one SEPARATE embedded local DB file
                            (durable, local, zero network dependency); synchronous=FULL;
                            idempotent schema at initialization; isolation_level=None →
                            explicit BEGIN IMMEDIATE / COMMIT.
  OD-N2 atomic commit     : record + fields are written in ONE transaction — either the
                            complete normalization record exists or nothing exists (zero
                            residue by construction; no recovery sweep needed).
  OD-N3 INV-N-1:1         : at most one record per (extraction_id, ruleset_id,
                            ruleset_version) — in-transaction uniqueness check + UNIQUE
                            index backstop. A different ruleset or version is a DIFFERENT
                            record (rule extensibility without rewriting history).
  OD-N4 ids/clock         : normalization_id = uuid4 hex; single layer clock (model.utc_now_iso).
  OD-N5 integrity anchor  : record_fingerprint = sha256-v1 (reused capture S1 capability)
                            over the canonical serialization of the record scalars + all
                            field rows in field_seq order — verified on every read (VOR).
  OD-N6 storage gates     : SQL CHECKs — provenance relayed EXTRACTED-only; status
                            vocabulary; normalized_value NULL iff status ≠ NORMALIZED;
                            reason_code NULL iff status = NORMALIZED; plus defensive
                            Python-side commit refusal.
  OD-N7 no update/delete  : normalization records are immutable once committed; no UPDATE
                            or DELETE path exists in this store.

The store never interprets content semantics — it persists the ruleset's output verbatim.
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import List, Optional, Sequence, Tuple

from capture import S1ComputationFailure, S1Service

from .model import (
    NormalizationDuplicate,
    NormalizedField,
    NormalizationNotFound,
    NormalizationPersistenceUnavailable,
    NormalizationRecord,
    NormalizationStatus,
    utc_now_iso,
)

_SCHEmA = """
CREATE TABLE IF NOT EXISTS normalization_records (
    normalization_id         TEXT PRIMARY KEY,
    extraction_id            TEXT NOT NULL,
    document_id              TEXT NOT NULL,
    capture_id               TEXT NOT NULL,
    capture_s1               TEXT NOT NULL,
    capture_s1_algorithm_id  TEXT NOT NULL,
    engine_id                TEXT NOT NULL,
    engine_schema_version    TEXT NOT NULL,
    ruleset_id               TEXT NOT NULL,
    ruleset_version          TEXT NOT NULL,
    field_count              INTEGER NOT NULL CHECK (field_count >= 0),
    normalized_count         INTEGER NOT NULL CHECK (normalized_count >= 0),
    deferred_count           INTEGER NOT NULL CHECK (deferred_count >= 0),
    rejected_count           INTEGER NOT NULL CHECK (rejected_count >= 0),
    created_at               TEXT NOT NULL,
    record_fingerprint       TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS normalization_fields (
    normalization_id    TEXT NOT NULL REFERENCES normalization_records(normalization_id),
    field_seq           INTEGER NOT NULL CHECK (field_seq >= 0),
    source_field_name   TEXT NOT NULL,
    source_provenance   TEXT NOT NULL CHECK (source_provenance = 'EXTRACTED'),
    status              TEXT NOT NULL CHECK (status IN ('NORMALIZED','DEFERRED','REJECTED')),
    normalized_value    TEXT,
    rules_applied       TEXT NOT NULL,
    reason_code         TEXT,
    PRIMARY KEY (normalization_id, field_seq),
    -- OD-N6: value/reason presence is bound to the status (no misleading half-states)
    CHECK ((status = 'NORMALIZED' AND normalized_value IS NOT NULL AND reason_code IS NULL)
        OR (status IN ('DEFERRED','REJECTED') AND normalized_value IS NULL
            AND reason_code IS NOT NULL))
);

-- OD-N3: INV-N-1:1 storage-level backstop — at most one record per triple,
-- enforced by SQLite itself, under any concurrency, on any path.
CREATE UNIQUE INDEX IF NOT EXISTS uq_normalization_extraction_ruleset
    ON normalization_records (extraction_id, ruleset_id, ruleset_version);

-- extraction-scoped enumeration (traceability consumer: Canonicalization Gate later)
CREATE INDEX IF NOT EXISTS ix_normalization_extraction
    ON normalization_records (extraction_id);
"""


def _chunk(value) -> bytes:
    """Deterministic length-prefixed encoding of one canonical element."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bool):                          # guard: bool before int
        raise TypeError("bool is not a canonical element")
    elif isinstance(value, int):
        raw = str(value).encode("ascii")
    else:
        raise TypeError(f"unsupported canonical element: {type(value)!r}")
    return len(raw).to_bytes(8, "big") + raw


def canonical_normalization_bytes(record: NormalizationRecord,
                                  fields: Sequence[NormalizedField]) -> bytes:
    """Canonical serialization fingerprinted by OD-N5 (deterministic, total).

    Order is fixed: record scalars, then fields in field_seq order. Absent optional
    values serialize as the empty string — the status column carries the distinction.
    The same (record, fields) ALWAYS yields the same byte sequence — the verified read
    recomputes exactly this over the durable rows.
    """
    parts: List[bytes] = [
        _chunk(record.normalization_id),
        _chunk(record.extraction_id),
        _chunk(record.document_id),
        _chunk(record.capture_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.engine_id),
        _chunk(record.engine_schema_version),
        _chunk(record.ruleset_id),
        _chunk(record.ruleset_version),
        _chunk(record.field_count),
        _chunk(record.normalized_count),
        _chunk(record.deferred_count),
        _chunk(record.rejected_count),
        _chunk(record.created_at),
    ]
    for f in fields:
        parts += [
            _chunk(f.field_seq),
            _chunk(f.source_field_name),
            _chunk(f.source_provenance),
            _chunk(f.status.value),
            _chunk(f.normalized_value if f.normalized_value is not None else ""),
            _chunk(f.rules_applied),
            _chunk(f.reason_code if f.reason_code is not None else ""),
        ]
    return b"".join(parts)


def _record_from_row(row: sqlite3.Row) -> NormalizationRecord:
    return NormalizationRecord(
        normalization_id=row["normalization_id"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        engine_id=row["engine_id"],
        engine_schema_version=row["engine_schema_version"],
        ruleset_id=row["ruleset_id"],
        ruleset_version=row["ruleset_version"],
        field_count=row["field_count"],
        normalized_count=row["normalized_count"],
        deferred_count=row["deferred_count"],
        rejected_count=row["rejected_count"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _field_from_row(row: sqlite3.Row) -> NormalizedField:
    return NormalizedField(
        field_seq=row["field_seq"],
        source_field_name=row["source_field_name"],
        source_provenance=row["source_provenance"],
        status=NormalizationStatus(row["status"]),
        normalized_value=row["normalized_value"],
        rules_applied=row["rules_applied"],
        reason_code=row["reason_code"],
    )


class NormalizationStore:
    """Durable local store for normalization records + normalized fields.

    Owns: atomic record+fields commit, INV-N-1:1 uniqueness mechanics, fingerprint
    anchoring, deterministic retrieval (fields by field_seq, ids per extraction),
    verified-read raw access. Nothing else — no interpretation, no update, no delete.
    """

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        self._conn = sqlite3.connect(self._db_path, timeout=30.0, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-N1: durability over speed
        self._conn.executescript(_SCHEmA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "NormalizationStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- write path (single atomic transaction — OD-N2) ---------------------

    def commit_normalization(
        self,
        extraction_id: str,
        document_id: str,
        capture_id: str,
        capture_s1: str,
        capture_s1_algorithm_id: str,
        engine_id: str,
        engine_schema_version: str,
        ruleset_id: str,
        ruleset_version: str,
        fields: Sequence[NormalizedField],
    ) -> NormalizationRecord:
        """Commit record + fields atomically. Raises:
          NormalizationDuplicate              — INV-N-1:1 triple already present
          NormalizationPersistenceUnavailable — nothing recordable (txn rolled back)
        """
        counts = self._counts(fields)
        if counts is None:
            # Defense in depth on top of the SQL CHECKs (OD-N6).
            raise NormalizationPersistenceUnavailable(
                "commit refused: field rows violate the status/value/reason gates")
        normalized_count, deferred_count, rejected_count = counts
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_by_triple_in_txn(extraction_id, ruleset_id,
                                                       ruleset_version)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise NormalizationDuplicate(existing)
                normalization_id = uuid.uuid4().hex
                created_at = utc_now_iso()
                draft = NormalizationRecord(
                    normalization_id=normalization_id,
                    extraction_id=extraction_id,
                    document_id=document_id,
                    capture_id=capture_id,
                    capture_s1=capture_s1,
                    capture_s1_algorithm_id=capture_s1_algorithm_id,
                    engine_id=engine_id,
                    engine_schema_version=engine_schema_version,
                    ruleset_id=ruleset_id,
                    ruleset_version=ruleset_version,
                    field_count=len(fields),
                    normalized_count=normalized_count,
                    deferred_count=deferred_count,
                    rejected_count=rejected_count,
                    created_at=created_at,
                    record_fingerprint="",            # anchored below
                    fingerprint_algorithm_id="",
                )
                try:
                    fp = self._s1.compute(canonical_normalization_bytes(draft, fields))
                except S1ComputationFailure as exc:
                    self._conn.execute("ROLLBACK")
                    raise NormalizationPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = NormalizationRecord(
                    **{**draft.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    """INSERT INTO normalization_records (
                           normalization_id, extraction_id, document_id, capture_id,
                           capture_s1, capture_s1_algorithm_id, engine_id,
                           engine_schema_version, ruleset_id, ruleset_version,
                           field_count, normalized_count, deferred_count,
                           rejected_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (final.normalization_id, final.extraction_id, final.document_id,
                     final.capture_id, final.capture_s1, final.capture_s1_algorithm_id,
                     final.engine_id, final.engine_schema_version, final.ruleset_id,
                     final.ruleset_version, final.field_count, final.normalized_count,
                     final.deferred_count, final.rejected_count, final.created_at,
                     final.record_fingerprint, final.fingerprint_algorithm_id))
                self._conn.executemany(
                    """INSERT INTO normalization_fields (
                           normalization_id, field_seq, source_field_name,
                           source_provenance, status, normalized_value, rules_applied,
                           reason_code)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    [(final.normalization_id, f.field_seq, f.source_field_name,
                      f.source_provenance, f.status.value, f.normalized_value,
                      f.rules_applied, f.reason_code)
                     for f in fields])
                self._conn.execute("COMMIT")
                return final
            except NormalizationDuplicate:
                raise                                  # already rolled back above
            except Exception:
                # Any other failure inside the txn → nothing persisted (OD-N2 atomicity).
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except NormalizationDuplicate:
            raise
        except sqlite3.Error as exc:
            raise NormalizationPersistenceUnavailable(f"commit failed: {exc}") from exc

    # -- read path (raw, verified-read-orchestrated) -------------------------

    def get_record(self, normalization_id: str) -> NormalizationRecord:
        row = self._conn.execute(
            "SELECT * FROM normalization_records WHERE normalization_id = ?",
            (normalization_id,)).fetchone()
        if row is None:
            raise NormalizationNotFound(normalization_id)
        return _record_from_row(row)

    def get_fields(self, normalization_id: str) -> List[NormalizedField]:
        rows = self._conn.execute(
            "SELECT * FROM normalization_fields WHERE normalization_id = ? "
            "ORDER BY field_seq", (normalization_id,)).fetchall()
        return [_field_from_row(r) for r in rows]

    def find_by_triple(self, extraction_id: str, ruleset_id: str,
                       ruleset_version: str) -> Optional[str]:
        """INV-N-1:1 lookup — the normalization_id for an exact triple, else None."""
        return self._find_by_triple_in_txn(extraction_id, ruleset_id, ruleset_version)

    def _find_by_triple_in_txn(self, extraction_id: str, ruleset_id: str,
                               ruleset_version: str) -> Optional[str]:
        row = self._conn.execute(
            """SELECT normalization_id FROM normalization_records
               WHERE extraction_id = ? AND ruleset_id = ? AND ruleset_version = ?""",
            (extraction_id, ruleset_id, ruleset_version)).fetchone()
        return None if row is None else row["normalization_id"]

    def find_for_extraction(self, extraction_id: str) -> List[str]:
        """All normalization_ids for an extraction — deterministic order (created_at, id)."""
        rows = self._conn.execute(
            """SELECT normalization_id FROM normalization_records
               WHERE extraction_id = ? ORDER BY created_at, normalization_id""",
            (extraction_id,)).fetchall()
        return [r["normalization_id"] for r in rows]

    # -- internal ------------------------------------------------------------

    @staticmethod
    def _counts(fields: Sequence[NormalizedField]) -> Optional[Tuple[int, int, int]]:
        """(normalized, deferred, rejected) — or None if any row violates OD-N6 gates."""
        normalized = deferred = rejected = 0
        for f in fields:
            if f.source_provenance != "EXTRACTED":
                return None
            value_ok = f.normalized_value is not None
            reason_ok = f.reason_code is not None
            if f.status == NormalizationStatus.NORMALIZED:
                if not value_ok or reason_ok or not f.rules_applied:
                    return None
                normalized += 1
            elif f.status in (NormalizationStatus.DEFERRED, NormalizationStatus.REJECTED):
                if value_ok or not reason_ok or f.rules_applied != "":
                    return None
                if f.status == NormalizationStatus.DEFERRED:
                    deferred += 1
                else:
                    rejected += 1
            else:
                return None
        return normalized, deferred, rejected
