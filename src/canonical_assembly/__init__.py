"""Kandoo Canonical Assembly + invoice_id Issuance Layer — WP-6.2 MVP (the
real Canonical Invoice, built from P6.1 ACCEPTED admissions).

The assembly consumes ONLY the P6.1 Canonical Invoice admission record of an
ACCEPTED gate decision — through the P6.1 verified read + the P6.1 whole-chain
trace (consumed, never bypassed) — and builds the durable, immutable,
provenance-anchored Canonical Invoice: canonical header anchors (the frozen
D-02 identity roles), the canonical field inventory (verified values VERBATIM
with D-01 provenance labels EXTRACTED | DERIVED relayed), declared canonical
line items (quantities / unit prices / totals — a DECLARED structure, never
discovered), and the formally issued invoice_id = the Kandoo-issued
canonical_invoice_id consumed VERBATIM (OD-A1; D-02 third identity; OD-G8).

Boundary (normative): this layer performs NO canonicalization decision, NO
identity resolution, NO fuzzy/heuristic/AI matching, NO product or customer
matching, NO tax/currency/accounting interpretation, NO arithmetic across
fields, NO inventory / Sale / KPI / Customer mutation, NO upstream execution,
NO identifier minting (no uuid/random exists in this package — AST-proven),
and it NEVER creates UNRESOLVED (D-01 — P5 territory). For REVIEW /
REJECTED / ALREADY_CANONICALIZED gate decisions no invoice is ever created.

Persistence: separate SQLite file, synchronous=FULL, atomic commit, immutable
history (no UPDATE / no DELETE), deterministic sha256-v1 fingerprints,
Verify-on-Read, tamper detection, restart safety, idempotent behavior.
"""
from .model import (
    ORIGIN_KANDOO_SALE,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    ORIGINS,
    PROVENANCE_EXTRACTED,
    PROVENANCE_DERIVED,
    PROVENANCES,
    ROLE_INVOICE_NUMBER,
    ROLE_INVOICE_DATE,
    ROLE_INVOICE_TOTAL,
    HEADER_ROLES,
    ROLE_LINE_QUANTITY,
    ROLE_LINE_UNIT_PRICE,
    ROLE_LINE_TOTAL,
    LINE_ROLES,
    ABSENT_REASON_UPSTREAM,
    REJECT_EMPTY_LINE,
    REJECT_DECLARED_FIELD_AMBIGUOUS,
    REJECT_DECLARATION_MALFORMED,
    REJECT_DECLARATION_CONFLICT,
    REFUSE_NO_ADMISSION,
    CUSTOMER_REF_REASON,
    NOTE_VERIFY_FAILED,
    utc_now_iso,
    IssuedCanonicalInvoiceRecord,
    CanonicalHeaderAnchor,
    CanonicalFieldEntry,
    CanonicalLineField,
    CanonicalLineRecord,
    RejectedLine,
    CanonicalAssemblyLayerError,
    IssuedInvoiceNotFound,
    IssuedInvoiceDuplicate,
    CanonicalAssemblyPersistenceUnavailable,
    AssemblyCompleted,
    AssemblyAlreadyAssembled,
    AssemblyInputIntegrityFailure,
    AssemblyRequestRefused,
    AssemblyStorageUnavailable,
    AssemblyReadSuccess,
    AssemblyReadIntegrityFailure,
    AssemblyReadRefused,
    AssemblyReadVerificationUnavailable,
    AssemblyTraceSuccess,
    AssemblyTraceIntegrityFailure,
    AssemblyTraceRefused,
    AssemblyTraceVerificationUnavailable,
)
from .assembly import (
    validate_line_binding,
    declaration_bytes,
    resolve_declared_field,
    assemble_fields,
    assemble_header_anchors,
    identity_anchor_payload,
    assemble_lines,
)
from .store import (
    CanonicalAssemblyStore,
    canonical_invoice_bytes,
)
from .service import CanonicalAssemblyService

__all__ = [
    # vocabularies
    "ORIGIN_KANDOO_SALE", "ORIGIN_HOLOO_CAPTURE", "ORIGIN_OTHER_POS_CAPTURE",
    "ORIGINS",
    "PROVENANCE_EXTRACTED", "PROVENANCE_DERIVED", "PROVENANCES",
    "ROLE_INVOICE_NUMBER", "ROLE_INVOICE_DATE", "ROLE_INVOICE_TOTAL",
    "HEADER_ROLES",
    "ROLE_LINE_QUANTITY", "ROLE_LINE_UNIT_PRICE", "ROLE_LINE_TOTAL",
    "LINE_ROLES",
    "ABSENT_REASON_UPSTREAM", "REJECT_EMPTY_LINE",
    "REJECT_DECLARED_FIELD_AMBIGUOUS", "REJECT_DECLARATION_MALFORMED",
    "REJECT_DECLARATION_CONFLICT", "REFUSE_NO_ADMISSION",
    "CUSTOMER_REF_REASON", "NOTE_VERIFY_FAILED",
    "utc_now_iso",
    # records
    "IssuedCanonicalInvoiceRecord", "CanonicalHeaderAnchor",
    "CanonicalFieldEntry", "CanonicalLineField", "CanonicalLineRecord",
    "RejectedLine",
    # exceptions
    "CanonicalAssemblyLayerError", "IssuedInvoiceNotFound",
    "IssuedInvoiceDuplicate", "CanonicalAssemblyPersistenceUnavailable",
    # assemble outcomes
    "AssemblyCompleted", "AssemblyAlreadyAssembled",
    "AssemblyInputIntegrityFailure", "AssemblyRequestRefused",
    "AssemblyStorageUnavailable",
    # read outcomes
    "AssemblyReadSuccess", "AssemblyReadIntegrityFailure",
    "AssemblyReadRefused", "AssemblyReadVerificationUnavailable",
    "AssemblyTraceSuccess", "AssemblyTraceIntegrityFailure",
    "AssemblyTraceRefused", "AssemblyTraceVerificationUnavailable",
    # pure engine
    "validate_line_binding", "declaration_bytes", "resolve_declared_field",
    "assemble_fields", "assemble_header_anchors", "identity_anchor_payload",
    "assemble_lines",
    # persistence
    "CanonicalAssemblyStore", "canonical_invoice_bytes",
    # service
    "CanonicalAssemblyService",
]
