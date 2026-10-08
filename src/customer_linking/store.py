"""Deterministic Customer Linking durable store — WP-9.1 MVP implementation.

Binding basis: SPEC-WP91-CUSTLINK §5/§7 (OD-CL1..CL6). The project store
pattern, unchanged: stdlib sqlite3, ONE separate embedded DB file
(`customer-linking.db`), synchronous=FULL, idempotent schema, explicit
BEGIN IMMEDIATE / COMMIT, atomic single-row commit (zero residue on any
failure), immutable rows (no UPDATE / no DELETE — AST-proven), sha256-v1
record fingerprints computed through the project S1 service (no hashlib in
this layer — OD-CL1), Verify-on-Read support via canonical bytes, SQL CHECK
gates + defensive Python-side refusals mirroring every CHECK, UNIQUE
backstops — customers: (identifier_kind, identifier_value) definitiveness
(OD-CL5); links: (invoice_id, declared_field_name, identifier_kind)
INV-CL-1:1 (OD-CL4) — restart-safe.

The store knows NOTHING about linking semantics: it persists what the
service derived from the P6.2 verified read and enforces the §5/§7 shapes.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from capture import S1ComputationFailure, S1Service

from .model import (
    DURABLE_LINK_OUTCOMES,
    DURABLE_UNRESOLVED_REASONS,
    PROVENANCES,
    CustomerIdentityDuplicate,
    CustomerIdentityNotFound,
    CustomerIdentityRecord,
    CustomerLinkingPersistenceUnavailable,
    CustomerLinkRecord,
    LinkDuplicate,
    LinkNotFound,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customer_identities (
    customer_identity_id      TEXT PRIMARY KEY,
    identifier_kind           TEXT NOT NULL,
    identifier_value          TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    record_fingerprint        TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL,
    -- OD-CL3: identifiers are stored verbatim and non-empty
    CHECK (length(identifier_kind) > 0),
    CHECK (length(identifier_value) > 0)
);

"""

_SCHEMA += """
CREATE TABLE IF NOT EXISTS customer_links (
    link_id                   TEXT PRIMARY KEY,
    invoice_id                TEXT NOT NULL,
    capture_s1                TEXT NOT NULL,
    capture_s1_algorithm_id   TEXT NOT NULL,
    declared_field_name       TEXT NOT NULL,
    canonical_seq             INTEGER NOT NULL,
    provenance                TEXT NOT NULL,
    identifier_kind           TEXT NOT NULL,
    link_outcome              TEXT NOT NULL,
    customer_identity_id      TEXT NOT NULL,
    unresolved_reason         TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    record_fingerprint        TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL,
    -- OD-CL7: exactly two durable outcomes; no creation/merge surface
    CHECK (link_outcome IN ('LINKED', 'UNRESOLVED')),
    -- OD-CL6: provenance is the D-01 vocabulary relayed verbatim
    CHECK (provenance IN ('EXTRACTED', 'DERIVED')),
    -- OD-CL6: the pointer is a non-negative assembly-order position
    CHECK (canonical_seq >= 0),
    -- OD-CL4/§5: outcome shape gates (both directions, fail-closed)
    CHECK (link_outcome != 'LINKED'
           OR (length(customer_identity_id) > 0
               AND unresolved_reason = '')),
    CHECK (link_outcome != 'UNRESOLVED'
           OR (customer_identity_id = ''
               AND unresolved_reason IN ('no-customer-identity'))),
    -- non-empty required scalars
    CHECK (length(link_id) > 0),
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
    ON customer_identities(identifier_kind, identifier_value);
"""

_SCHEMA += """
CREATE UNIQUE INDEX IF NOT EXISTS idx_cl_declaration
    ON customer_links(invoice_id, declared_field_name, identifier_kind);
"""


def canonical_customer_identity_bytes(record: CustomerIdentityRecord) -> bytes:
    """Deterministic serialization of the customer identity scalars — the
    VOR anchor payload (OD-CL1). Field order is fixed by the dataclass; no
    mapping iteration anywhere."""
    parts = [
        b"customer-identity-v1",
        record.customer_identity_id.encode("utf-8"),
        record.identifier_kind.encode("utf-8"),
        record.identifier_value.encode("utf-8"),
        record.created_at.encode("utf-8"),
    ]
    return b"\x1f".join(parts)


def canonical_link_bytes(record: CustomerLinkRecord) -> bytes:
    """Deterministic serialization of the link scalars — the VOR anchor
    payload (OD-CL1). Field order is fixed by the dataclass; no mapping
    iteration anywhere."""
    parts = [
        b"customer-link-v1",
        record.link_id.encode("utf-8"),
        record.invoice_id.encode("utf-8"),
        record.capture_s1.encode("utf-8"),
        record.capture_s1_algorithm_id.encode("utf-8"),
        record.declared_field_name.encode("utf-8"),
        str(record.canonical_seq).encode("utf-8"),
        record.provenance.encode("utf-8"),
        record.identifier_kind.encode("utf-8"),
        record.link_outcome.encode("utf-8"),
        record.customer_identity_id.encode("utf-8"),
        record.unresolved_reason.encode("utf-8"),
        record.created_at.encode("utf-8"),
    ]
    return b"\x1f".join(parts)


def _customer_from_row(row: sqlite3.Row) -> CustomerIdentityRecord:
    return CustomerIdentityRecord(
        customer_identity_id=row["customer_identity_id"],
        identifier_kind=row["identifier_kind"],
        identifier_value=row["identifier_value"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _link_from_row(row: sqlite3.Row) -> CustomerLinkRecord:
    return CustomerLinkRecord(
        link_id=row["link_id"],
        invoice_id=row["invoice_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        declared_field_name=row["declared_field_name"],
        canonical_seq=row["canonical_seq"],
        provenance=row["provenance"],
        identifier_kind=row["identifier_kind"],
        link_outcome=row["link_outcome"],
        customer_identity_id=row["customer_identity_id"],
        unresolved_reason=row["unresolved_reason"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


class CustomerLinkingStore:
    """Durable, immutable customer-identity + customer-link store
    (OD-CL1..CL6)."""

    def __init__(self, db_path, s1: S1Service) -> None:
        self._s1 = s1
        try:
            self._conn = sqlite3.connect(str(db_path), isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise CustomerLinkingPersistenceUnavailable(
                f"store unavailable: {exc}") from exc

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "CustomerLinkingStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Customer commits (single row — atomic by construction, OD-CL2)
    # ------------------------------------------------------------------

    def commit_customer_identity(self, record: CustomerIdentityRecord) \
            -> CustomerIdentityRecord:
        """Commit ONE customer identity. Raises:
          CustomerIdentityDuplicate        — UNIQUE definitiveness backstop
          CustomerLinkingPersistenceUnavailable — nothing recordable
        """
        self._validate_customer_shape(record)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_customer_in_txn(
                    record.identifier_kind, record.identifier_value)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise CustomerIdentityDuplicate(
                        existing.customer_identity_id)
                try:
                    fp = self._s1.compute(
                        canonical_customer_identity_bytes(record))
                except S1ComputationFailure as exc:
                    raise CustomerLinkingPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = CustomerIdentityRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    "INSERT INTO customer_identities ("
                    "customer_identity_id, identifier_kind, "
                    "identifier_value, created_at, record_fingerprint, "
                    "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?)",
                    (final.customer_identity_id, final.identifier_kind,
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
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _validate_customer_shape(self, record: CustomerIdentityRecord) \
            -> None:
        """Defensive Python-side refusals mirroring every SQL CHECK."""
        if not record.identifier_kind or not record.identifier_value:
            raise CustomerLinkingPersistenceUnavailable(
                "commit refused: customer identifiers must be non-empty "
                "(OD-CL3 — declared verbatim, no defaults)")
        for field in ("customer_identity_id", "created_at"):
            if not getattr(record, field):
                raise CustomerLinkingPersistenceUnavailable(
                    f"commit refused: empty required field {field!r}")

    # ------------------------------------------------------------------
    # Link commits (single row — atomic by construction, OD-CL4)
    # ------------------------------------------------------------------

    def commit_link(self, record: CustomerLinkRecord) -> CustomerLinkRecord:
        """Commit ONE link outcome. Raises:
          LinkDuplicate                    — INV-CL-1:1 already present
          CustomerLinkingPersistenceUnavailable — nothing recordable
        """
        self._validate_link_shape(record)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_link_in_txn(
                    record.invoice_id, record.declared_field_name,
                    record.identifier_kind)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise LinkDuplicate(existing.link_id)
                try:
                    fp = self._s1.compute(canonical_link_bytes(record))
                except S1ComputationFailure as exc:
                    raise CustomerLinkingPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = CustomerLinkRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    "INSERT INTO customer_links ("
                    "link_id, invoice_id, capture_s1, "
                    "capture_s1_algorithm_id, declared_field_name, "
                    "canonical_seq, provenance, identifier_kind, "
                    "link_outcome, customer_identity_id, "
                    "unresolved_reason, created_at, record_fingerprint, "
                    "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?,"
                    "?,?,?,?,?)",
                    (final.link_id, final.invoice_id, final.capture_s1,
                     final.capture_s1_algorithm_id, final.declared_field_name,
                     final.canonical_seq, final.provenance,
                     final.identifier_kind, final.link_outcome,
                     final.customer_identity_id, final.unresolved_reason,
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
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _validate_link_shape(self, record: CustomerLinkRecord) -> None:
        """Defensive Python-side refusals mirroring every SQL CHECK (§7)."""
        if record.link_outcome not in DURABLE_LINK_OUTCOMES:
            raise CustomerLinkingPersistenceUnavailable(
                f"commit refused: link_outcome {record.link_outcome!r} is "
                "not a durable outcome (no creation/merge surface exists — "
                "OD-CL7)")
        if record.provenance not in PROVENANCES:
            raise CustomerLinkingPersistenceUnavailable(
                f"commit refused: provenance {record.provenance!r} is "
                "outside the D-01 vocabulary")
        if record.link_outcome == "LINKED":
            if not record.customer_identity_id or record.unresolved_reason:
                raise CustomerLinkingPersistenceUnavailable(
                    "commit refused: LINKED without the customer identity "
                    "reference or with an unresolved reason")
        else:
            if record.customer_identity_id:
                raise CustomerLinkingPersistenceUnavailable(
                    "commit refused: UNRESOLVED with a customer identity "
                    "reference")
            if record.unresolved_reason not in DURABLE_UNRESOLVED_REASONS:
                raise CustomerLinkingPersistenceUnavailable(
                    f"commit refused: unresolved_reason "
                    f"{record.unresolved_reason!r} is not a stable durable "
                    "reason")
        if record.canonical_seq < 0:
            raise CustomerLinkingPersistenceUnavailable(
                "commit refused: negative canonical_seq pointer")
        for field in ("link_id", "invoice_id", "capture_s1",
                      "capture_s1_algorithm_id", "declared_field_name",
                      "identifier_kind", "created_at"):
            if not getattr(record, field):
                raise CustomerLinkingPersistenceUnavailable(
                    f"commit refused: empty required field {field!r}")

    # ------------------------------------------------------------------
    # Customer reads (raw rows — verified views live in the service, §6)
    # ------------------------------------------------------------------

    def get_customer_identity(self, customer_identity_id: str) \
            -> CustomerIdentityRecord:
        try:
            row = self._conn.execute(
                "SELECT * FROM customer_identities "
                "WHERE customer_identity_id = ?",
                (customer_identity_id,)).fetchone()
        except sqlite3.Error as exc:
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        if row is None:
            raise CustomerIdentityNotFound(customer_identity_id)
        return _customer_from_row(row)

    def find_customer_identity(self, identifier_kind: str,
                               identifier_value: str) \
            -> List[CustomerIdentityRecord]:
        """The exact customer lookup (L5) — byte-exact under the declared
        kind. Returns ALL rows (0, 1, or — corruption — more); the counting
        decision lives in the service (OD-CL5)."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM customer_identities "
                "WHERE identifier_kind = ? AND identifier_value = ? "
                "ORDER BY created_at, customer_identity_id",
                (identifier_kind, identifier_value)).fetchall()
        except sqlite3.Error as exc:
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_customer_from_row(row) for row in rows]

    def _find_customer_in_txn(self, identifier_kind: str,
                              identifier_value: str) \
            -> Optional[CustomerIdentityRecord]:
        row = self._conn.execute(
            "SELECT * FROM customer_identities "
            "WHERE identifier_kind = ? AND identifier_value = ?",
            (identifier_kind, identifier_value)).fetchone()
        return _customer_from_row(row) if row is not None else None

    def list_customers(self) -> List[CustomerIdentityRecord]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM customer_identities "
                "ORDER BY created_at, customer_identity_id").fetchall()
        except sqlite3.Error as exc:
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_customer_from_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Link reads (raw rows — verified views live in the service, §6)
    # ------------------------------------------------------------------

    def get_link(self, link_id: str) -> CustomerLinkRecord:
        try:
            row = self._conn.execute(
                "SELECT * FROM customer_links WHERE link_id = ?",
                (link_id,)).fetchone()
        except sqlite3.Error as exc:
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        if row is None:
            raise LinkNotFound(link_id)
        return _link_from_row(row)

    def find_link_by_declaration(self, invoice_id: str,
                                 declared_field_name: str,
                                 identifier_kind: str) \
            -> Optional[CustomerLinkRecord]:
        try:
            row = self._conn.execute(
                "SELECT * FROM customer_links "
                "WHERE invoice_id = ? AND declared_field_name = ? "
                "AND identifier_kind = ?",
                (invoice_id, declared_field_name,
                 identifier_kind)).fetchone()
        except sqlite3.Error as exc:
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return _link_from_row(row) if row is not None else None

    def _find_link_in_txn(self, invoice_id: str, declared_field_name: str,
                          identifier_kind: str) \
            -> Optional[CustomerLinkRecord]:
        row = self._conn.execute(
            "SELECT * FROM customer_links "
            "WHERE invoice_id = ? AND declared_field_name = ? "
            "AND identifier_kind = ?",
            (invoice_id, declared_field_name, identifier_kind)).fetchone()
        return _link_from_row(row) if row is not None else None

    def find_links_by_invoice(self, invoice_id: str) \
            -> List[CustomerLinkRecord]:
        """The durable link register for one invoice (§6 listing
        discipline): every committed link row anchored to that invoice —
        raw records; consumers verify through the service read paths."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM customer_links WHERE invoice_id = ? "
                "ORDER BY created_at, link_id",
                (invoice_id,)).fetchall()
        except sqlite3.Error as exc:
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_link_from_row(row) for row in rows]

    def list_links(self) -> List[CustomerLinkRecord]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM customer_links "
                "ORDER BY created_at, link_id").fetchall()
        except sqlite3.Error as exc:
            raise CustomerLinkingPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_link_from_row(row) for row in rows]
