"""Durable Canonical Assembly store — WP-6.2 MVP implementation.

Binding basis: SPEC-WP62-CANASM §8 (OD-C1..OD-C7 delegated details declared
here). Same store pattern as P1–P6.1: stdlib sqlite3, ONE separate embedded DB
file, synchronous=FULL, idempotent schema, explicit BEGIN IMMEDIATE / COMMIT,
atomic multi-record commit, in-transaction uniqueness checks + UNIQUE index
backstops, sha256-v1 fingerprints over canonical byte serializations,
Verify-on-Read raw access.

NO UPDATE and NO DELETE path exists in this store (OD-C7; AST-proven by the
boundary tests). Nothing is interpreted here — no identity decision, no
canonical mapping, no arithmetic: only deterministic persistence mechanics.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional, Sequence

from capture import S1ComputationFailure, S1Service

from .model import (
    CUSTOMER_REF_REASON,
    HEADER_ROLES,
    LINE_ROLES,
    ORIGINS,
    PROVENANCES,
    CanonicalFieldEntry,
    CanonicalHeaderAnchor,
    CanonicalLineField,
    CanonicalLineRecord,
    CanonicalAssemblyPersistenceUnavailable,
    IssuedCanonicalInvoiceRecord,
    IssuedInvoiceDuplicate,
    IssuedInvoiceNotFound,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS canonical_invoices (
    invoice_id                 TEXT PRIMARY KEY,
    admission_decision_id      TEXT NOT NULL,
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
    identity_class             TEXT NOT NULL,
    identity_source            TEXT NOT NULL,
    identity_fingerprint       TEXT NOT NULL,
    customer_reference         TEXT,
    customer_reference_reason  TEXT NOT NULL,
    declaration_fingerprint    TEXT NOT NULL,
    field_count                INTEGER NOT NULL CHECK (field_count >= 0),
    line_count                 INTEGER NOT NULL CHECK (line_count >= 0),
    created_at                 TEXT NOT NULL,
    record_fingerprint         TEXT NOT NULL,
    fingerprint_algorithm_id   TEXT NOT NULL
);

-- OD-C3: INV-AI-1:1 storage backstop — at most ONE issued invoice per P6.1
-- admission decision (a replay returns the existing invoice, never duplicates)
CREATE UNIQUE INDEX IF NOT EXISTS uq_issued_invoice_admission
    ON canonical_invoices (admission_decision_id);
-- OD-C3: document-level backstop behind the D-02/D-03 identity (the same
-- Kandoo-issued identity can never be issued twice)
CREATE UNIQUE INDEX IF NOT EXISTS uq_issued_invoice_identity
    ON canonical_invoices (identity_fingerprint);

CREATE TABLE IF NOT EXISTS canonical_header_anchors (
    invoice_id             TEXT NOT NULL REFERENCES
                           canonical_invoices(invoice_id),
    role                   TEXT NOT NULL
                           CHECK (role IN ('INVOICE_NUMBER','INVOICE_DATE',
                                           'INVOICE_TOTAL')),
    canonical_value        TEXT NOT NULL,
    source_field_name      TEXT NOT NULL,
    normalization_id       TEXT NOT NULL,
    field_seq              INTEGER NOT NULL,
    PRIMARY KEY (invoice_id, role)
);

CREATE TABLE IF NOT EXISTS canonical_fields (
    invoice_id             TEXT NOT NULL REFERENCES
                           canonical_invoices(invoice_id),
    canonical_seq          INTEGER NOT NULL CHECK (canonical_seq >= 0),
    provenance             TEXT NOT NULL
                           CHECK (provenance IN ('EXTRACTED','DERIVED')),
    field_name             TEXT NOT NULL,
    canonical_value        TEXT NOT NULL,
    source_normalization_id TEXT NOT NULL,
    source_field_seq       INTEGER,
    source_derivation_id   TEXT NOT NULL,
    -- OD-C6: pointer consistency per D-01 provenance vocabulary
    CHECK ((provenance = 'EXTRACTED'
            AND source_normalization_id != ''
            AND source_field_seq IS NOT NULL
            AND source_derivation_id = '')
        OR (provenance = 'DERIVED'
            AND source_normalization_id = ''
            AND source_field_seq IS NULL
            AND source_derivation_id != '')),
    PRIMARY KEY (invoice_id, canonical_seq)
);

CREATE TABLE IF NOT EXISTS canonical_lines (
    invoice_id             TEXT NOT NULL REFERENCES
                           canonical_invoices(invoice_id),
    line_seq               INTEGER NOT NULL CHECK (line_seq >= 0),
    PRIMARY KEY (invoice_id, line_seq)
);

CREATE TABLE IF NOT EXISTS canonical_line_fields (
    invoice_id             TEXT NOT NULL REFERENCES
                           canonical_invoices(invoice_id),
    line_seq               INTEGER NOT NULL CHECK (line_seq >= 0),
    role                   TEXT NOT NULL
                           CHECK (role IN ('LINE_QUANTITY',
                                           'LINE_UNIT_PRICE',
                                           'LINE_TOTAL')),
    present                INTEGER NOT NULL CHECK (present IN (0,1)),
    canonical_value        TEXT,
    source_field_name      TEXT NOT NULL,
    normalization_id       TEXT NOT NULL,
    field_seq              INTEGER,
    -- OD-C6: an absent role never carries a value or a pointer
    CHECK ((present = 1  AND canonical_value IS NOT NULL
            AND source_field_name != '' AND normalization_id != ''
            AND field_seq IS NOT NULL)
        OR (present = 0 AND canonical_value IS NULL
            AND source_field_name = '' AND normalization_id = ''
            AND field_seq IS NULL)),
    PRIMARY KEY (invoice_id, line_seq, role)
);
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


def canonical_invoice_bytes(record: IssuedCanonicalInvoiceRecord,
                            anchors: Sequence[CanonicalHeaderAnchor],
                            fields: Sequence[CanonicalFieldEntry],
                            lines: Sequence[CanonicalLineRecord],
                            line_fields: Sequence[CanonicalLineField]) -> bytes:
    """Canonical serialization fingerprinted by OD-C5: invoice scalars +
    header anchors (role order) + canonical fields (canonical_seq order) +
    lines (line order) + line fields (line/role order)."""
    parts: List[bytes] = [
        _chunk(record.invoice_id),
        _chunk(record.admission_decision_id),
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
        _chunk(record.customer_reference
               if record.customer_reference is not None else ""),
        _chunk(record.customer_reference_reason),
        _chunk(record.declaration_fingerprint),
        _chunk(record.field_count),
        _chunk(record.line_count),
        _chunk(record.created_at),
    ]
    for a in sorted(anchors, key=lambda x: HEADER_ROLES.index(x.role)):
        parts += [_chunk(a.role), _chunk(a.canonical_value),
                  _chunk(a.source_field_name), _chunk(a.normalization_id),
                  _chunk(a.field_seq)]
    for f in sorted(fields, key=lambda x: x.canonical_seq):
        parts += [_chunk(f.canonical_seq), _chunk(f.provenance),
                  _chunk(f.field_name), _chunk(f.canonical_value),
                  _chunk(f.source_normalization_id),
                  _chunk(f.source_field_seq
                         if f.source_field_seq is not None else -1),
                  _chunk(f.source_derivation_id)]
    for l in sorted(lines, key=lambda x: x.line_seq):
        parts += [_chunk(l.line_seq)]
    for lf in sorted(line_fields,
                     key=lambda x: (x.line_seq, LINE_ROLES.index(x.role))):
        parts += [_chunk(lf.line_seq), _chunk(lf.role), _chunk(lf.present),
                  _chunk(lf.canonical_value if lf.present else ""),
                  _chunk(lf.source_field_name), _chunk(lf.normalization_id),
                  _chunk(lf.field_seq if lf.field_seq is not None else -1)]
    return b"".join(parts)


def _invoice_from_row(row: sqlite3.Row) -> IssuedCanonicalInvoiceRecord:
    return IssuedCanonicalInvoiceRecord(
        invoice_id=row["invoice_id"],
        admission_decision_id=row["admission_decision_id"],
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
        customer_reference=row["customer_reference"],
        customer_reference_reason=row["customer_reference_reason"],
        declaration_fingerprint=row["declaration_fingerprint"],
        field_count=row["field_count"],
        line_count=row["line_count"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _anchor_from_row(row: sqlite3.Row) -> CanonicalHeaderAnchor:
    return CanonicalHeaderAnchor(
        invoice_id=row["invoice_id"],
        role=row["role"],
        canonical_value=row["canonical_value"],
        source_field_name=row["source_field_name"],
        normalization_id=row["normalization_id"],
        field_seq=row["field_seq"],
    )


def _field_from_row(row: sqlite3.Row) -> CanonicalFieldEntry:
    return CanonicalFieldEntry(
        invoice_id=row["invoice_id"],
        canonical_seq=row["canonical_seq"],
        provenance=row["provenance"],
        field_name=row["field_name"],
        canonical_value=row["canonical_value"],
        source_normalization_id=row["source_normalization_id"],
        source_field_seq=row["source_field_seq"],
        source_derivation_id=row["source_derivation_id"],
    )


def _line_from_row(row: sqlite3.Row) -> CanonicalLineRecord:
    return CanonicalLineRecord(
        invoice_id=row["invoice_id"],
        line_seq=row["line_seq"],
    )


def _line_field_from_row(row: sqlite3.Row) -> CanonicalLineField:
    return CanonicalLineField(
        invoice_id=row["invoice_id"],
        line_seq=row["line_seq"],
        role=row["role"],
        present=row["present"],
        canonical_value=row["canonical_value"],
        source_field_name=row["source_field_name"],
        normalization_id=row["normalization_id"],
        field_seq=row["field_seq"],
    )


class CanonicalAssemblyStore:
    """Durable local store for issued Canonical Invoices + header anchors +
    canonical fields + lines + line fields.

    Owns: atomic assembly/issuance commit (OD-C2), INV-AI-1:1 + identity
    backstops (OD-C3), fingerprint anchoring (OD-C5), deterministic retrieval,
    verified-read raw access. Nothing else — no assembly decision, no
    interpretation, no update, no delete.
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

    def __enter__(self) -> "CanonicalAssemblyStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- write path: atomic assembly/issuance commit (OD-C2) ----------------

    def commit_invoice(self, record: IssuedCanonicalInvoiceRecord,
                       anchors: Sequence[CanonicalHeaderAnchor],
                       fields: Sequence[CanonicalFieldEntry],
                       lines: Sequence[CanonicalLineRecord],
                       line_fields: Sequence[CanonicalLineField]) \
            -> IssuedCanonicalInvoiceRecord:
        """Commit the issued invoice with its header anchors, canonical
        fields, lines and line fields — atomically (assembly + issuance are
        ONE transaction; no half-assembled state can persist).

        Raises:
          IssuedInvoiceDuplicate            — INV-AI-1:1 already present
          CanonicalAssemblyPersistenceUnavailable — nothing recordable (txn
                                              rolled back, zero residue)
        """
        if record.origin not in ORIGINS:
            raise CanonicalAssemblyPersistenceUnavailable(
                f"commit refused: origin {record.origin!r} is outside the "
                f"frozen origin vocabulary")
        if record.customer_reference is not None:
            raise CanonicalAssemblyPersistenceUnavailable(
                "commit refused: a canonical customer reference is never "
                "created in this WP (D-06 / OD-A9)")
        if len(anchors) != 3:
            raise CanonicalAssemblyPersistenceUnavailable(
                "commit refused: an issued invoice carries exactly three "
                "header anchors (the frozen D-02 roles)")
        if record.field_count != len(fields):
            raise CanonicalAssemblyPersistenceUnavailable(
                "commit refused: field_count does not match the assembled "
                "field inventory (OD-C3)")
        if record.line_count != len(lines):
            raise CanonicalAssemblyPersistenceUnavailable(
                "commit refused: line_count does not match the assembled "
                "lines (OD-C3)")
        if any(f.provenance not in PROVENANCES for f in fields):
            raise CanonicalAssemblyPersistenceUnavailable(
                "commit refused: canonical field provenance outside the "
                "D-01 vocabulary")
        if any(lf.role not in LINE_ROLES for lf in line_fields):
            raise CanonicalAssemblyPersistenceUnavailable(
                "commit refused: line field role outside the declared "
                "vocabulary")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_invoice_by_admission_in_txn(
                    record.admission_decision_id)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise IssuedInvoiceDuplicate(existing.invoice_id)
                # OD-C3 backstop behind the service-level check — a race can
                # only ever reach these as the single writer (BEGIN IMMEDIATE)
                identity_existing = self._conn.execute(
                    "SELECT invoice_id FROM canonical_invoices "
                    "WHERE identity_fingerprint = ?",
                    (record.identity_fingerprint,)).fetchone()
                if identity_existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise IssuedInvoiceDuplicate(
                        identity_existing["invoice_id"])
                try:
                    fp = self._s1.compute(canonical_invoice_bytes(
                        record, anchors, fields, lines, line_fields))
                except S1ComputationFailure as exc:
                    raise CanonicalAssemblyPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = IssuedCanonicalInvoiceRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._insert_invoice(final)
                self._insert_anchors(anchors)
                self._insert_fields(fields)
                self._insert_lines(lines)
                self._insert_line_fields(line_fields)
                self._conn.execute("COMMIT")
                return final
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except sqlite3.Error as exc:
            raise CanonicalAssemblyPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _insert_invoice(self, record: IssuedCanonicalInvoiceRecord) -> None:
        self._conn.execute(
            """INSERT INTO canonical_invoices (
                   invoice_id, admission_decision_id, domain_state_id,
                   normalization_id, extraction_id, document_id, capture_id,
                   capture_s1, capture_s1_algorithm_id, origin,
                   identity_class, identity_source, identity_fingerprint,
                   customer_reference, customer_reference_reason,
                   declaration_fingerprint, field_count, line_count,
                   created_at, record_fingerprint, fingerprint_algorithm_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record.invoice_id, record.admission_decision_id,
             record.domain_state_id, record.normalization_id,
             record.extraction_id, record.document_id, record.capture_id,
             record.capture_s1, record.capture_s1_algorithm_id,
             record.origin, record.identity_class, record.identity_source,
             record.identity_fingerprint, record.customer_reference,
             record.customer_reference_reason,
             record.declaration_fingerprint, record.field_count,
             record.line_count, record.created_at,
             record.record_fingerprint, record.fingerprint_algorithm_id))

    def _insert_anchors(self, anchors: Sequence[CanonicalHeaderAnchor]) -> None:
        self._conn.executemany(
            """INSERT INTO canonical_header_anchors (
                   invoice_id, role, canonical_value, source_field_name,
                   normalization_id, field_seq)
               VALUES (?,?,?,?,?,?)""",
            [(a.invoice_id, a.role, a.canonical_value, a.source_field_name,
              a.normalization_id, a.field_seq) for a in anchors])

    def _insert_fields(self, fields: Sequence[CanonicalFieldEntry]) -> None:
        self._conn.executemany(
            """INSERT INTO canonical_fields (
                   invoice_id, canonical_seq, provenance, field_name,
                   canonical_value, source_normalization_id,
                   source_field_seq, source_derivation_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            [(f.invoice_id, f.canonical_seq, f.provenance, f.field_name,
              f.canonical_value, f.source_normalization_id,
              f.source_field_seq, f.source_derivation_id) for f in fields])

    def _insert_lines(self, lines: Sequence[CanonicalLineRecord]) -> None:
        self._conn.executemany(
            """INSERT INTO canonical_lines (invoice_id, line_seq)
               VALUES (?,?)""",
            [(l.invoice_id, l.line_seq) for l in lines])

    def _insert_line_fields(
            self, line_fields: Sequence[CanonicalLineField]) -> None:
        self._conn.executemany(
            """INSERT INTO canonical_line_fields (
                   invoice_id, line_seq, role, present, canonical_value,
                   source_field_name, normalization_id, field_seq)
               VALUES (?,?,?,?,?,?,?,?)""",
            [(lf.invoice_id, lf.line_seq, lf.role, lf.present,
              lf.canonical_value, lf.source_field_name,
              lf.normalization_id, lf.field_seq) for lf in line_fields])

    # -- read path: deterministic retrieval + verified-read raw access ------

    def get_invoice(self, invoice_id: str) -> IssuedCanonicalInvoiceRecord:
        row = self._conn.execute(
            "SELECT * FROM canonical_invoices WHERE invoice_id = ?",
            (invoice_id,)).fetchone()
        if row is None:
            raise IssuedInvoiceNotFound(invoice_id)
        return _invoice_from_row(row)

    def find_invoice_by_admission(self, admission_decision_id: str) \
            -> Optional[IssuedCanonicalInvoiceRecord]:
        return self._find_invoice_by_admission_in_txn(admission_decision_id)

    def _find_invoice_by_admission_in_txn(self, admission_decision_id: str) \
            -> Optional[IssuedCanonicalInvoiceRecord]:
        row = self._conn.execute(
            "SELECT * FROM canonical_invoices WHERE admission_decision_id = ?",
            (admission_decision_id,)).fetchone()
        return _invoice_from_row(row) if row is not None else None

    def get_anchors(self, invoice_id: str) -> List[CanonicalHeaderAnchor]:
        rows = self._conn.execute(
            """SELECT * FROM canonical_header_anchors WHERE invoice_id = ?
               ORDER BY CASE role WHEN 'INVOICE_NUMBER' THEN 0
                                  WHEN 'INVOICE_DATE' THEN 1
                                  ELSE 2 END""",
            (invoice_id,)).fetchall()
        return [_anchor_from_row(r) for r in rows]

    def get_fields(self, invoice_id: str) -> List[CanonicalFieldEntry]:
        rows = self._conn.execute(
            """SELECT * FROM canonical_fields WHERE invoice_id = ?
               ORDER BY canonical_seq""",
            (invoice_id,)).fetchall()
        return [_field_from_row(r) for r in rows]

    def get_lines(self, invoice_id: str) -> List[CanonicalLineRecord]:
        rows = self._conn.execute(
            """SELECT * FROM canonical_lines WHERE invoice_id = ?
               ORDER BY line_seq""",
            (invoice_id,)).fetchall()
        return [_line_from_row(r) for r in rows]

    def get_line_fields(self, invoice_id: str) -> List[CanonicalLineField]:
        rows = self._conn.execute(
            """SELECT * FROM canonical_line_fields WHERE invoice_id = ?
               ORDER BY line_seq,
               CASE role WHEN 'LINE_QUANTITY' THEN 0
                         WHEN 'LINE_UNIT_PRICE' THEN 1
                         ELSE 2 END""",
            (invoice_id,)).fetchall()
        return [_line_field_from_row(r) for r in rows]

    def list_invoices(self) -> List[IssuedCanonicalInvoiceRecord]:
        rows = self._conn.execute(
            "SELECT * FROM canonical_invoices ORDER BY created_at, "
            "invoice_id").fetchall()
        return [_invoice_from_row(r) for r in rows]
