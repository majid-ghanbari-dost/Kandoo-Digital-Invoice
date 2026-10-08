"""Product Exact Match durable store — WP-8.1 MVP implementation.

Binding basis: SPEC-WP81-PMATCH §5/§7 (OD-PM1..PM6). The project store
pattern, unchanged: stdlib sqlite3, ONE separate embedded DB file
(`product-candidate.db`), synchronous=FULL, idempotent schema, explicit
BEGIN IMMEDIATE / COMMIT, atomic single-row commit (zero residue on any
failure), immutable rows (no UPDATE / no DELETE — AST-proven), sha256-v1
record fingerprints computed through the project S1 service (no hashlib in
this layer — OD-PM1), Verify-on-Read support via canonical bytes, SQL CHECK
gates + defensive Python-side refusals mirroring every CHECK, UNIQUE
backstops — catalog: (identifier_kind, identifier_value) definitiveness
(OD-PM5); matches: (invoice_id, declared_field_name, identifier_kind)
INV-PM-1:1 (OD-PM4) — restart-safe.

The store knows NOTHING about matching semantics: it persists what the
service derived from the P6.2 verified read and enforces the §5/§7 shapes.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from capture import S1ComputationFailure, S1Service

from .model import (
    DURABLE_MATCH_OUTCOMES,
    DURABLE_UNRESOLVED_REASONS,
    PROVENANCES,
    CatalogIdentityDuplicate,
    CatalogIdentityNotFound,
    CatalogIdentityRecord,
    MatchDuplicate,
    MatchNotFound,
    ProductCandidatePersistenceUnavailable,
    ProductMatchRecord,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_identities (
    catalog_identity_id       TEXT PRIMARY KEY,
    identifier_kind           TEXT NOT NULL,
    identifier_value          TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    record_fingerprint        TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL,
    -- OD-PM3: identifiers are stored verbatim and non-empty
    CHECK (length(identifier_kind) > 0),
    CHECK (length(identifier_value) > 0)
);

"""

_SCHEMA += """
CREATE TABLE IF NOT EXISTS product_matches (
    match_id                  TEXT PRIMARY KEY,
    invoice_id                TEXT NOT NULL,
    capture_s1                TEXT NOT NULL,
    capture_s1_algorithm_id   TEXT NOT NULL,
    declared_field_name       TEXT NOT NULL,
    canonical_seq             INTEGER NOT NULL,
    provenance                TEXT NOT NULL,
    identifier_kind           TEXT NOT NULL,
    match_outcome             TEXT NOT NULL,
    catalog_identity_id       TEXT NOT NULL,
    unresolved_reason         TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    record_fingerprint        TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL,
    -- OD-PM7: exactly two durable outcomes; no candidate/approval surface
    CHECK (match_outcome IN ('EXACT_MATCHED', 'UNRESOLVED')),
    -- OD-PM6: provenance is the D-01 vocabulary relayed verbatim
    CHECK (provenance IN ('EXTRACTED', 'DERIVED')),
    -- OD-PM6: the pointer is a non-negative assembly-order position
    CHECK (canonical_seq >= 0),
    -- OD-PM4/§5: outcome shape gates (both directions, fail-closed)
    CHECK (match_outcome != 'EXACT_MATCHED'
           OR (length(catalog_identity_id) > 0
               AND unresolved_reason = '')),
    CHECK (match_outcome != 'UNRESOLVED'
           OR (catalog_identity_id = ''
               AND unresolved_reason IN ('no-catalog-identity'))),
    -- non-empty required scalars
    CHECK (length(match_id) > 0),
    CHECK (length(invoice_id) > 0),
    CHECK (length(capture_s1) > 0),
    CHECK (length(capture_s1_algorithm_id) > 0),
    CHECK (length(declared_field_name) > 0),
    CHECK (length(identifier_kind) > 0),
    CHECK (length(created_at) > 0)
);

"""

_SCHEMA += """
CREATE UNIQUE INDEX IF NOT EXISTS idx_ci_kind_value
    ON catalog_identities(identifier_kind, identifier_value);
"""

_SCHEMA += """
CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_declaration
    ON product_matches(invoice_id, declared_field_name, identifier_kind);
"""


def canonical_catalog_identity_bytes(record: CatalogIdentityRecord) -> bytes:
    """Deterministic serialization of the catalog identity scalars — the VOR
    anchor payload (OD-PM1). Field order is fixed by the dataclass; no
    mapping iteration anywhere."""
    parts = [
        b"catalog-identity-v1",
        record.catalog_identity_id.encode("utf-8"),
        record.identifier_kind.encode("utf-8"),
        record.identifier_value.encode("utf-8"),
        record.created_at.encode("utf-8"),
    ]
    return b"\x1f".join(parts)


def canonical_match_bytes(record: ProductMatchRecord) -> bytes:
    """Deterministic serialization of the match scalars — the VOR anchor
    payload (OD-PM1). Field order is fixed by the dataclass; no mapping
    iteration anywhere."""
    parts = [
        b"product-match-v1",
        record.match_id.encode("utf-8"),
        record.invoice_id.encode("utf-8"),
        record.capture_s1.encode("utf-8"),
        record.capture_s1_algorithm_id.encode("utf-8"),
        record.declared_field_name.encode("utf-8"),
        str(record.canonical_seq).encode("utf-8"),
        record.provenance.encode("utf-8"),
        record.identifier_kind.encode("utf-8"),
        record.match_outcome.encode("utf-8"),
        record.catalog_identity_id.encode("utf-8"),
        record.unresolved_reason.encode("utf-8"),
        record.created_at.encode("utf-8"),
    ]
    return b"\x1f".join(parts)


def _catalog_from_row(row: sqlite3.Row) -> CatalogIdentityRecord:
    return CatalogIdentityRecord(
        catalog_identity_id=row["catalog_identity_id"],
        identifier_kind=row["identifier_kind"],
        identifier_value=row["identifier_value"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _match_from_row(row: sqlite3.Row) -> ProductMatchRecord:
    return ProductMatchRecord(
        match_id=row["match_id"],
        invoice_id=row["invoice_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        declared_field_name=row["declared_field_name"],
        canonical_seq=row["canonical_seq"],
        provenance=row["provenance"],
        identifier_kind=row["identifier_kind"],
        match_outcome=row["match_outcome"],
        catalog_identity_id=row["catalog_identity_id"],
        unresolved_reason=row["unresolved_reason"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


class ProductCandidateStore:
    """Durable, immutable catalog-identity + product-match store
    (OD-PM1..PM6)."""

    def __init__(self, db_path, s1: S1Service) -> None:
        self._s1 = s1
        try:
            self._conn = sqlite3.connect(str(db_path), isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise ProductCandidatePersistenceUnavailable(
                f"store unavailable: {exc}") from exc

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "ProductCandidateStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Catalog commits (single row — atomic by construction, OD-PM2)
    # ------------------------------------------------------------------

    def commit_catalog_identity(self, record: CatalogIdentityRecord) \
            -> CatalogIdentityRecord:
        """Commit ONE catalog identity. Raises:
          CatalogIdentityDuplicate         — UNIQUE definitiveness backstop
          ProductCandidatePersistenceUnavailable — nothing recordable
        """
        self._validate_catalog_shape(record)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_catalog_in_txn(
                    record.identifier_kind, record.identifier_value)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise CatalogIdentityDuplicate(
                        existing.catalog_identity_id)
                try:
                    fp = self._s1.compute(
                        canonical_catalog_identity_bytes(record))
                except S1ComputationFailure as exc:
                    raise ProductCandidatePersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = CatalogIdentityRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    "INSERT INTO catalog_identities ("
                    "catalog_identity_id, identifier_kind, identifier_value,"
                    " created_at, record_fingerprint, "
                    "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?)",
                    (final.catalog_identity_id, final.identifier_kind,
                     final.identifier_value, final.created_at,
                     final.record_fingerprint,
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
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _validate_catalog_shape(self, record: CatalogIdentityRecord) -> None:
        """Defensive Python-side refusals mirroring every SQL CHECK."""
        if not record.identifier_kind or not record.identifier_value:
            raise ProductCandidatePersistenceUnavailable(
                "commit refused: catalog identifiers must be non-empty "
                "(OD-PM3 — declared verbatim, no defaults)")
        for field in ("catalog_identity_id", "created_at"):
            if not getattr(record, field):
                raise ProductCandidatePersistenceUnavailable(
                    f"commit refused: empty required field {field!r}")

    # ------------------------------------------------------------------
    # Match commits (single row — atomic by construction, OD-PM4)
    # ------------------------------------------------------------------

    def commit_match(self, record: ProductMatchRecord) -> ProductMatchRecord:
        """Commit ONE match outcome. Raises:
          MatchDuplicate                   — INV-PM-1:1 already present
          ProductCandidatePersistenceUnavailable — nothing recordable
        """
        self._validate_match_shape(record)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_match_in_txn(
                    record.invoice_id, record.declared_field_name,
                    record.identifier_kind)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise MatchDuplicate(existing.match_id)
                try:
                    fp = self._s1.compute(canonical_match_bytes(record))
                except S1ComputationFailure as exc:
                    raise ProductCandidatePersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = ProductMatchRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    "INSERT INTO product_matches ("
                    "match_id, invoice_id, capture_s1, "
                    "capture_s1_algorithm_id, declared_field_name, "
                    "canonical_seq, provenance, identifier_kind, "
                    "match_outcome, catalog_identity_id, unresolved_reason,"
                    " created_at, record_fingerprint, "
                    "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?,"
                    "?,?,?,?,?)",
                    (final.match_id, final.invoice_id, final.capture_s1,
                     final.capture_s1_algorithm_id, final.declared_field_name,
                     final.canonical_seq, final.provenance,
                     final.identifier_kind, final.match_outcome,
                     final.catalog_identity_id, final.unresolved_reason,
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
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _validate_match_shape(self, record: ProductMatchRecord) -> None:
        """Defensive Python-side refusals mirroring every SQL CHECK (§7)."""
        if record.match_outcome not in DURABLE_MATCH_OUTCOMES:
            raise ProductCandidatePersistenceUnavailable(
                f"commit refused: match_outcome {record.match_outcome!r} is "
                "not a durable outcome (no candidate/approval surface "
                "exists — OD-PM7)")
        if record.provenance not in PROVENANCES:
            raise ProductCandidatePersistenceUnavailable(
                f"commit refused: provenance {record.provenance!r} is "
                "outside the D-01 vocabulary")
        if record.match_outcome == "EXACT_MATCHED":
            if not record.catalog_identity_id or record.unresolved_reason:
                raise ProductCandidatePersistenceUnavailable(
                    "commit refused: EXACT_MATCHED without the catalog "
                    "identity reference or with an unresolved reason")
        else:
            if record.catalog_identity_id:
                raise ProductCandidatePersistenceUnavailable(
                    "commit refused: UNRESOLVED with a catalog identity "
                    "reference")
            if record.unresolved_reason not in DURABLE_UNRESOLVED_REASONS:
                raise ProductCandidatePersistenceUnavailable(
                    f"commit refused: unresolved_reason "
                    f"{record.unresolved_reason!r} is not a stable durable "
                    "reason")
        if record.canonical_seq < 0:
            raise ProductCandidatePersistenceUnavailable(
                "commit refused: negative canonical_seq pointer")
        for field in ("match_id", "invoice_id", "capture_s1",
                      "capture_s1_algorithm_id", "declared_field_name",
                      "identifier_kind", "created_at"):
            if not getattr(record, field):
                raise ProductCandidatePersistenceUnavailable(
                    f"commit refused: empty required field {field!r}")

    # ------------------------------------------------------------------
    # Catalog reads (raw rows — verified views live in the service, §6)
    # ------------------------------------------------------------------

    def get_catalog_identity(self, catalog_identity_id: str) \
            -> CatalogIdentityRecord:
        try:
            row = self._conn.execute(
                "SELECT * FROM catalog_identities "
                "WHERE catalog_identity_id = ?",
                (catalog_identity_id,)).fetchone()
        except sqlite3.Error as exc:
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        if row is None:
            raise CatalogIdentityNotFound(catalog_identity_id)
        return _catalog_from_row(row)

    def find_catalog_identity(self, identifier_kind: str,
                              identifier_value: str) \
            -> List[CatalogIdentityRecord]:
        """The exact catalog lookup (M5) — byte-exact under the declared
        kind. Returns ALL rows (0, 1, or — corruption — more); the counting
        decision lives in the service (OD-PM5)."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM catalog_identities "
                "WHERE identifier_kind = ? AND identifier_value = ? "
                "ORDER BY created_at, catalog_identity_id",
                (identifier_kind, identifier_value)).fetchall()
        except sqlite3.Error as exc:
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_catalog_from_row(row) for row in rows]

    def _find_catalog_in_txn(self, identifier_kind: str,
                             identifier_value: str) \
            -> Optional[CatalogIdentityRecord]:
        row = self._conn.execute(
            "SELECT * FROM catalog_identities "
            "WHERE identifier_kind = ? AND identifier_value = ?",
            (identifier_kind, identifier_value)).fetchone()
        return _catalog_from_row(row) if row is not None else None

    def list_catalog(self) -> List[CatalogIdentityRecord]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM catalog_identities "
                "ORDER BY created_at, catalog_identity_id").fetchall()
        except sqlite3.Error as exc:
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_catalog_from_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Match reads (raw rows — verified views live in the service, §6)
    # ------------------------------------------------------------------

    def get_match(self, match_id: str) -> ProductMatchRecord:
        try:
            row = self._conn.execute(
                "SELECT * FROM product_matches WHERE match_id = ?",
                (match_id,)).fetchone()
        except sqlite3.Error as exc:
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        if row is None:
            raise MatchNotFound(match_id)
        return _match_from_row(row)

    def find_match_by_declaration(self, invoice_id: str,
                                  declared_field_name: str,
                                  identifier_kind: str) \
            -> Optional[ProductMatchRecord]:
        try:
            row = self._conn.execute(
                "SELECT * FROM product_matches "
                "WHERE invoice_id = ? AND declared_field_name = ? "
                "AND identifier_kind = ?",
                (invoice_id, declared_field_name,
                 identifier_kind)).fetchone()
        except sqlite3.Error as exc:
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return _match_from_row(row) if row is not None else None

    def _find_match_in_txn(self, invoice_id: str, declared_field_name: str,
                           identifier_kind: str) \
            -> Optional[ProductMatchRecord]:
        row = self._conn.execute(
            "SELECT * FROM product_matches "
            "WHERE invoice_id = ? AND declared_field_name = ? "
            "AND identifier_kind = ?",
            (invoice_id, declared_field_name, identifier_kind)).fetchone()
        return _match_from_row(row) if row is not None else None

    def find_matches_by_invoice(self, invoice_id: str) \
            -> List[ProductMatchRecord]:
        """The durable match register for one invoice (§6 listing
        discipline): every committed match row anchored to that invoice —
        raw records; consumers verify through the service read paths."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM product_matches WHERE invoice_id = ? "
                "ORDER BY created_at, match_id",
                (invoice_id,)).fetchall()
        except sqlite3.Error as exc:
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_match_from_row(row) for row in rows]

    def list_matches(self) -> List[ProductMatchRecord]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM product_matches "
                "ORDER BY created_at, match_id").fetchall()
        except sqlite3.Error as exc:
            raise ProductCandidatePersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_match_from_row(row) for row in rows]
