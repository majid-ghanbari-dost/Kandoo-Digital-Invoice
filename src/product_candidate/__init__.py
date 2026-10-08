"""Kandoo Product Exact Match Layer — WP-8.1 MVP (the Product Candidate
domain's Exact Match, per the frozen D-05 four-part Product Matching
contract).

The layer consumes ONLY the WP-6.2 verified read
(`CanonicalAssemblyService.read_assembled_invoice`) — consumed, never
bypassed, never triggered — and the explicit Catalog Identity register, and
produces the durable, immutable, auditable D-05 `Exact Match` output: a
declared product reference on an issued Canonical Invoice whose declared
identifier byte-matches EXACTLY ONE registered catalog identity under the
declared kind. Zero matches stay UNRESOLVED (durable, auditable); ambiguity
remains ambiguity.

Boundary (normative): this layer performs NO candidate generation, NO
candidate approval, NO confidence scoring, NO fuzzy/semantic/AI/heuristic
matching of ANY kind, NO barcode semantics (identifier kinds/values are
DECLARED opaque strings — verbatim, no grammar, no checksum, no
normalization), NO capture-derived catalog mutation (registration is the
only catalog path and carries no capture/invoice parameter), NO
canonicalization or identity decisions, NO customer anything (WP-9.1), NO
REVIEW operations, NO invoice mutation, NO upstream execution, NO identifier
minting beyond bookkeeping uuids (AST-proven), and it never stores a
pipeline VALUE (pointer discipline — the identifier value lives in the
verified P6.2 read and in the catalog's own registered content).

Persistence: separate SQLite file (product-candidate.db), synchronous=FULL,
atomic single-row commit, immutable history (no UPDATE / no DELETE),
deterministic sha256-v1 fingerprints via the project S1 service,
Verify-on-Read, tamper detection, restart safety, idempotent behavior.
"""
from .model import (
    MATCH_OUTCOME_EXACT_MATCHED,
    MATCH_OUTCOME_UNRESOLVED,
    DURABLE_MATCH_OUTCOMES,
    UNRESOLVED_NO_CATALOG_IDENTITY,
    DURABLE_UNRESOLVED_REASONS,
    PROVENANCE_EXTRACTED,
    PROVENANCE_DERIVED,
    PROVENANCES,
    REFUSE_DECLARATION_MALFORMED,
    REFUSE_FIELD_NOT_FOUND,
    REFUSE_FIELD_AMBIGUOUS,
    NOTE_VERIFY_FAILED,
    utc_now_iso,
    CatalogIdentityRecord,
    ProductMatchRecord,
    ProductCandidateLayerError,
    CatalogIdentityNotFound,
    CatalogIdentityDuplicate,
    MatchNotFound,
    MatchDuplicate,
    ProductCandidatePersistenceUnavailable,
    CatalogIdentityRegistered,
    CatalogIdentityReplay,
    CatalogRegistrationRefused,
    CatalogStorageUnavailable,
    ProductExactMatched,
    ProductReferenceUnresolved,
    ProductMatchReplay,
    ProductMatchRequestRefused,
    ProductMatchInputIntegrityFailure,
    ProductMatchStorageUnavailable,
    ProductMatchReadSuccess,
    CatalogReadSuccess,
    ProductMatchReadIntegrityFailure,
    ProductMatchReadRefused,
    ProductMatchReadVerificationUnavailable,
    CatalogReadIntegrityFailure,
    CatalogReadRefused,
    CatalogReadVerificationUnavailable,
)
from .store import (
    ProductCandidateStore,
    canonical_catalog_identity_bytes,
    canonical_match_bytes,
)
from .service import ProductCandidateService

__all__ = [
    # vocabularies
    "MATCH_OUTCOME_EXACT_MATCHED", "MATCH_OUTCOME_UNRESOLVED",
    "DURABLE_MATCH_OUTCOMES", "UNRESOLVED_NO_CATALOG_IDENTITY",
    "DURABLE_UNRESOLVED_REASONS",
    "PROVENANCE_EXTRACTED", "PROVENANCE_DERIVED", "PROVENANCES",
    "REFUSE_DECLARATION_MALFORMED", "REFUSE_FIELD_NOT_FOUND",
    "REFUSE_FIELD_AMBIGUOUS", "NOTE_VERIFY_FAILED", "utc_now_iso",
    # records
    "CatalogIdentityRecord", "ProductMatchRecord",
    # exceptions
    "ProductCandidateLayerError", "CatalogIdentityNotFound",
    "CatalogIdentityDuplicate", "MatchNotFound", "MatchDuplicate",
    "ProductCandidatePersistenceUnavailable",
    # registration outcomes
    "CatalogIdentityRegistered", "CatalogIdentityReplay",
    "CatalogRegistrationRefused", "CatalogStorageUnavailable",
    # match outcomes
    "ProductExactMatched", "ProductReferenceUnresolved",
    "ProductMatchReplay", "ProductMatchRequestRefused",
    "ProductMatchInputIntegrityFailure", "ProductMatchStorageUnavailable",
    # read outcomes
    "ProductMatchReadSuccess", "CatalogReadSuccess",
    "ProductMatchReadIntegrityFailure", "ProductMatchReadRefused",
    "ProductMatchReadVerificationUnavailable",
    "CatalogReadIntegrityFailure", "CatalogReadRefused",
    "CatalogReadVerificationUnavailable",
    # persistence
    "ProductCandidateStore", "canonical_catalog_identity_bytes",
    "canonical_match_bytes",
    # service
    "ProductCandidateService",
]
