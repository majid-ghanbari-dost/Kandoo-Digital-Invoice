"""Kandoo Deterministic Customer Linking Layer — WP-9.1 MVP (the Customer
Linkage domain, per the frozen D-06 decision).

The layer consumes ONLY the WP-6.2 verified read
(`CanonicalAssemblyService.read_assembled_invoice`) — consumed, never
bypassed, never triggered — and the explicit Customer Identity register, and
produces the durable, immutable, auditable deterministic link: a declared
customer reference on an issued Canonical Invoice whose declared identifier
byte-matches EXACTLY ONE registered customer identity under the declared
kind. Zero matches stay UNRESOLVED (durable, auditable); ambiguity remains
ambiguity.

D-06/DEF3 — NO AUTO-CREATE, STRUCTURALLY (OD-CL2): the register's ONLY
write path is the explicit registration API (no capture/invoice parameter);
the link ladder's ONLY write is the append-only link row. There is NO code
path from a capture or an invoice to a customer row. A capture containing
customer-looking data can only attempt a deterministic link against
customers that already exist — it can never create one.

Boundary (normative): NO fuzzy/semantic/AI/best-match matching of ANY kind
(the ONLY rule is the exact definitive-identifier rule), NO barcode
semantics, NO customer merge/dedup/enrichment (DEF3/D-06 — PO territory),
NO canonicalization or document-identity decisions (P6.1/P7.1), NO product
matching (WP-8.1), NO REVIEW operations, NO invoice mutation (P6.2 rows are
immutable; the OD-A9 assembly-time absence stands — this layer's register
is additive), NO upstream execution, NO identifier minting beyond
bookkeeping uuids (AST-proven), and it never stores a pipeline VALUE
(pointer discipline).

Persistence: separate SQLite file (customer-linking.db), synchronous=FULL,
atomic single-row commit, immutable history (no UPDATE / no DELETE),
deterministic sha256-v1 fingerprints via the project S1 service,
Verify-on-Read, tamper detection, restart safety, idempotent behavior.
"""
from .model import (
    LINK_OUTCOME_LINKED,
    LINK_OUTCOME_UNRESOLVED,
    DURABLE_LINK_OUTCOMES,
    UNRESOLVED_NO_CUSTOMER_IDENTITY,
    DURABLE_UNRESOLVED_REASONS,
    PROVENANCE_EXTRACTED,
    PROVENANCE_DERIVED,
    PROVENANCES,
    REFUSE_DECLARATION_MALFORMED,
    REFUSE_FIELD_NOT_FOUND,
    REFUSE_FIELD_AMBIGUOUS,
    NOTE_VERIFY_FAILED,
    utc_now_iso,
    CustomerIdentityRecord,
    CustomerLinkRecord,
    CustomerLinkingLayerError,
    CustomerIdentityNotFound,
    CustomerIdentityDuplicate,
    LinkNotFound,
    LinkDuplicate,
    CustomerLinkingPersistenceUnavailable,
    CustomerIdentityRegistered,
    CustomerIdentityReplay,
    CustomerRegistrationRefused,
    CustomerStorageUnavailable,
    CustomerLinked,
    CustomerLinkUnresolved,
    CustomerLinkReplay,
    CustomerLinkRequestRefused,
    CustomerLinkInputIntegrityFailure,
    CustomerLinkStorageUnavailable,
    CustomerLinkReadSuccess,
    CustomerReadSuccess,
    CustomerLinkReadIntegrityFailure,
    CustomerLinkReadRefused,
    CustomerLinkReadVerificationUnavailable,
    CustomerReadIntegrityFailure,
    CustomerReadRefused,
    CustomerReadVerificationUnavailable,
)
from .store import (
    CustomerLinkingStore,
    canonical_customer_identity_bytes,
    canonical_link_bytes,
)
from .service import CustomerLinkingService

__all__ = [
    # vocabularies
    "LINK_OUTCOME_LINKED", "LINK_OUTCOME_UNRESOLVED",
    "DURABLE_LINK_OUTCOMES", "UNRESOLVED_NO_CUSTOMER_IDENTITY",
    "DURABLE_UNRESOLVED_REASONS",
    "PROVENANCE_EXTRACTED", "PROVENANCE_DERIVED", "PROVENANCES",
    "REFUSE_DECLARATION_MALFORMED", "REFUSE_FIELD_NOT_FOUND",
    "REFUSE_FIELD_AMBIGUOUS", "NOTE_VERIFY_FAILED", "utc_now_iso",
    # records
    "CustomerIdentityRecord", "CustomerLinkRecord",
    # exceptions
    "CustomerLinkingLayerError", "CustomerIdentityNotFound",
    "CustomerIdentityDuplicate", "LinkNotFound", "LinkDuplicate",
    "CustomerLinkingPersistenceUnavailable",
    # registration outcomes
    "CustomerIdentityRegistered", "CustomerIdentityReplay",
    "CustomerRegistrationRefused", "CustomerStorageUnavailable",
    # link outcomes
    "CustomerLinked", "CustomerLinkUnresolved", "CustomerLinkReplay",
    "CustomerLinkRequestRefused", "CustomerLinkInputIntegrityFailure",
    "CustomerLinkStorageUnavailable",
    # read outcomes
    "CustomerLinkReadSuccess", "CustomerReadSuccess",
    "CustomerLinkReadIntegrityFailure", "CustomerLinkReadRefused",
    "CustomerLinkReadVerificationUnavailable",
    "CustomerReadIntegrityFailure", "CustomerReadRefused",
    "CustomerReadVerificationUnavailable",
    # persistence
    "CustomerLinkingStore", "canonical_customer_identity_bytes",
    "canonical_link_bytes",
    # service
    "CustomerLinkingService",
]
