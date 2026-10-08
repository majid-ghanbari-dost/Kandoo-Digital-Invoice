"""Durable Extraction Store — WP-3.1 MVP implementation.

Binding basis: SPEC-WP31-EXT v1.0-MVP over the frozen WP-1.1/WP-2.1 store pattern
(same governance, new layer — capture & reconstruction stores are NOT modified;
AD-02 layer boundary).

Delegated implementation details declared here per D-09:
  OD-X1 storage mechanism : Python stdlib sqlite3, one SEPARATE embedded local DB file
                            (durable, local, zero network dependency); synchronous=FULL;
                            idempotent schema at initialization; isolation_level=None →
                            explicit BEGIN IMMEDIATE / COMMIT.
  OD-X2 atomic commit     : record + fields are written in ONE transaction — either the
                            complete extraction record exists or nothing exists. There is
                            NO ACTIVE/residue state by construction, so this layer needs
                            no startup recovery sweep (stronger than record-first for a
                            layer whose output is a single atomic datum).
  OD-X3 INV-X-1:1         : at most one record per (document_id, engine_id,
                            engine_schema_version) — in-transaction uniqueness check +
                            UNIQUE index backstop (uq_extraction_doc_engine). A different
                            engine or schema version is a DIFFERENT record (engine
                            agnosticism is preserved; no engine ranking exists here).
  OD-X4 ids               : extraction_id = uuid4 hex.
  OD-X5 integrity anchor  : record_fingerprint = sha256-v1 (reused capture S1 capability)
                            over the canonical serialization of the record scalars + all
                            field rows in field_seq order — verified on every read (VOR
                            pattern; tamper-evident extraction output).
  OD-X6 provenance gate   : storage-level CHECK — this layer can only store
                            provenance='EXTRACTED' (D-01 vocabulary; DERIVED/UNRESOLVED
                            are upstream/downstream owned, never engine outputs).
  OD-X7 clock             : single extraction-layer clock (model.utc_now_iso).
  OD-X8 no update/delete  : extraction records are immutable once committed; no UPDATE or
                            DELETE path exists in this store.

The store stores extracted values verbatim and never interprets content semantics.
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import List, Optional, Sequence, Tuple

from capture import S1ComputationFailure, S1Service

from .model import (
    ExtractedField,
    ExtractionDuplicate,
    ExtractionNotFound,
    ExtractionPersistenceUnavailable,
    ExtractionRecord,
    Provenance,
    SourceSpan,
    utc_now_iso,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS extraction_records (
    extraction_id            TEXT PRIMARY KEY,
    document_id              TEXT NOT NULL,
    capture_id               TEXT NOT NULL,
    capture_s1               TEXT NOT NULL,
    capture_s1_algorithm_id  TEXT NOT NULL,
    engine_id                TEXT NOT NULL,
    engine_schema_version    TEXT NOT NULL,
    page_count               INTEGER NOT NULL CHECK (page_count >= 0),
    field_count              INTEGER NOT NULL CHECK (field_count >= 0),
    created_at               TEXT NOT NULL,
    record_fingerprint       TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extraction_fields (
    extraction_id     TEXT NOT NULL REFERENCES extraction_records(extraction_id),
    field_seq         INTEGER NOT NULL CHECK (field_seq >= 0),
    field_name        TEXT NOT NULL,
    value_verbatim    TEXT NOT NULL,
    value_encoding    TEXT NOT NULL,
    provenance        TEXT NOT NULL CHECK (provenance = 'EXTRACTED'),
    page_index        INTEGER NOT NULL CHECK (page_index >= 0),
    byte_start        INTEGER NOT NULL CHECK (byte_start >= 0),
    byte_end          INTEGER NOT NULL CHECK (byte_end >= byte_start),
    page_fingerprint  TEXT NOT NULL,
    PRIMARY KEY (extraction_id, field_seq)
);

-- OD-X3: INV-X-1:1 storage-level backstop — at most one record per triple,
-- enforced by SQLite itself, under any concurrency, on any path.
CREATE UNIQUE INDEX IF NOT EXISTS uq_extraction_doc_engine
    ON extraction_records (document_id, engine_id, engine_schema_version);

-- document-scoped enumeration (traceability consumer: WP-3.2 evidence binding)
CREATE INDEX IF NOT EXISTS ix_extraction_document
    ON extraction_records (document_id);
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


def canonical_extraction_bytes(record: ExtractionRecord,
                               fields: Sequence[ExtractedField]) -> bytes:
    """Canonical serialization fingerprinted by OD-X5 (deterministic, total).

    Order is fixed: record scalars, then fields in field_seq order with their spans.
    The same (record, fields) ALWAYS yields the same byte sequence — the verified read
    recomputes exactly this over the durable rows.
    """
    parts: List[bytes] = [
        _chunk(record.extraction_id),
        _chunk(record.document_id),
        _chunk(record.capture_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.engine_id),
        _chunk(record.engine_schema_version),
        _chunk(record.page_count),
        _chunk(record.field_count),
        _chunk(record.created_at),
    ]
    for f in fields:
        parts += [
            _chunk(f.field_seq),
            _chunk(f.field_name),
            _chunk(f.value_verbatim),
            _chunk(f.value_encoding),
            _chunk(f.provenance.value),
            _chunk(f.span.page_index),
            _chunk(f.span.byte_start),
            _chunk(f.span.byte_end),
            _chunk(f.span.page_fingerprint),
        ]
    return b"".join(parts)


def _record_from_row(row: sqlite3.Row) -> ExtractionRecord:
    return ExtractionRecord(
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        engine_id=row["engine_id"],
        engine_schema_version=row["engine_schema_version"],
        page_count=row["page_count"],
        field_count=row["field_count"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _field_from_row(row: sqlite3.Row) -> ExtractedField:
    return ExtractedField(
        field_seq=row["field_seq"],
        field_name=row["field_name"],
        value_verbatim=row["value_verbatim"],
        value_encoding=row["value_encoding"],
        provenance=Provenance(row["provenance"]),
        span=SourceSpan(
            page_index=row["page_index"],
            byte_start=row["byte_start"],
            byte_end=row["byte_end"],
            page_fingerprint=row["page_fingerprint"],
        ),
    )


class ExtractionStore:
    """Durable local store for extraction records + verbatim positioned fields.

    Owns: atomic record+fields commit, INV-X-1:1 uniqueness mechanics, fingerprint
    anchoring, deterministic retrieval (fields by field_seq, ids per document),
    verified-read raw access. Nothing else — no interpretation, no update, no delete.
    """

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        self._conn = sqlite3.connect(self._db_path, timeout=30.0, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-X1: durability over speed
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "ExtractionStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- write path (single atomic transaction — OD-X2) ---------------------

    def commit_extraction(
        self,
        document_id: str,
        capture_id: str,
        capture_s1: str,
        capture_s1_algorithm_id: str,
        engine_id: str,
        engine_schema_version: str,
        page_count: int,
        fields: Sequence[ExtractedField],
    ) -> ExtractionRecord:
        """Commit record + fields atomically. Raises:
          ExtractionDuplicate                — INV-X-1:1 triple already present
          ExtractionPersistenceUnavailable   — nothing recordable (txn rolled back)
        """
        if any(f.provenance != Provenance.EXTRACTED for f in fields):
            # Defense in depth on top of the SQL CHECK — a non-EXTRACTED provenance can
            # never enter this store (OD-X6).
            raise ExtractionPersistenceUnavailable(
                "commit refused: non-EXTRACTED provenance is not an engine output")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_by_triple_in_txn(document_id, engine_id,
                                                       engine_schema_version)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise ExtractionDuplicate(existing)
                extraction_id = uuid.uuid4().hex
                created_at = utc_now_iso()
                draft = ExtractionRecord(
                    extraction_id=extraction_id,
                    document_id=document_id,
                    capture_id=capture_id,
                    capture_s1=capture_s1,
                    capture_s1_algorithm_id=capture_s1_algorithm_id,
                    engine_id=engine_id,
                    engine_schema_version=engine_schema_version,
                    page_count=page_count,
                    field_count=len(fields),
                    created_at=created_at,
                    record_fingerprint="",            # anchored below
                    fingerprint_algorithm_id="",
                )
                try:
                    fp = self._s1.compute(canonical_extraction_bytes(draft, fields))
                except S1ComputationFailure as exc:
                    self._conn.execute("ROLLBACK")
                    raise ExtractionPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = ExtractionRecord(
                    **{**draft.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    """INSERT INTO extraction_records (
                           extraction_id, document_id, capture_id, capture_s1,
                           capture_s1_algorithm_id, engine_id, engine_schema_version,
                           page_count, field_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (final.extraction_id, final.document_id, final.capture_id,
                     final.capture_s1, final.capture_s1_algorithm_id, final.engine_id,
                     final.engine_schema_version, final.page_count, final.field_count,
                     final.created_at, final.record_fingerprint,
                     final.fingerprint_algorithm_id))
                self._conn.executemany(
                    """INSERT INTO extraction_fields (
                           extraction_id, field_seq, field_name, value_verbatim,
                           value_encoding, provenance, page_index, byte_start, byte_end,
                           page_fingerprint)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    [(final.extraction_id, f.field_seq, f.field_name, f.value_verbatim,
                      f.value_encoding, f.provenance.value, f.span.page_index,
                      f.span.byte_start, f.span.byte_end, f.span.page_fingerprint)
                     for f in fields])
                self._conn.execute("COMMIT")
                return final
            except ExtractionDuplicate:
                raise                                  # already rolled back above
            except Exception:
                # Any other failure inside the txn → nothing persisted (OD-X2 atomicity).
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except ExtractionDuplicate:
            raise
        except sqlite3.Error as exc:
            raise ExtractionPersistenceUnavailable(f"commit failed: {exc}") from exc

    # -- read path (raw, verified-read-orchestrated) -------------------------

    def get_record(self, extraction_id: str) -> ExtractionRecord:
        row = self._conn.execute(
            "SELECT * FROM extraction_records WHERE extraction_id = ?",
            (extraction_id,)).fetchone()
        if row is None:
            raise ExtractionNotFound(extraction_id)
        return _record_from_row(row)

    def get_fields(self, extraction_id: str) -> List[ExtractedField]:
        rows = self._conn.execute(
            "SELECT * FROM extraction_fields WHERE extraction_id = ? ORDER BY field_seq",
            (extraction_id,)).fetchall()
        return [_field_from_row(r) for r in rows]

    def find_by_triple(self, document_id: str, engine_id: str,
                       engine_schema_version: str) -> Optional[str]:
        """INV-X-1:1 lookup — the extraction_id for an exact triple, else None."""
        return self._find_by_triple_in_txn(document_id, engine_id, engine_schema_version)

    def _find_by_triple_in_txn(self, document_id: str, engine_id: str,
                               engine_schema_version: str) -> Optional[str]:
        row = self._conn.execute(
            """SELECT extraction_id FROM extraction_records
               WHERE document_id = ? AND engine_id = ? AND engine_schema_version = ?""",
            (document_id, engine_id, engine_schema_version)).fetchone()
        return None if row is None else row["extraction_id"]

    def find_for_document(self, document_id: str) -> List[str]:
        """All extraction_ids for a document — deterministic order (created_at, id)."""
        rows = self._conn.execute(
            """SELECT extraction_id FROM extraction_records WHERE document_id = ?
               ORDER BY created_at, extraction_id""",
            (document_id,)).fetchall()
        return [r["extraction_id"] for r in rows]
