"""Kandoo Identity Resolution Layer — WP-7.1 MVP implementation (the durable,
operational identity foundation for documents entering the canonical
pipeline).

The service consumes VERIFIED P5.2 domain-state records (whole-chain
provenance re-verified down to Capture S1, consumed never bypassed) and
resolves identity strictly per the frozen D-02/D-03 model:

  S1             — the Capture Identity: capture_s1 anchors every record and
                   drives the replay recognition (one capture artifact, ONE
                   durable resolution, ever — no second identity).
  S2             — the External Document Identity, established ONLY when the
                   frozen triad (invoice number + date + total) is fully
                   extracted AND verified — via the P6.1 primitive consumed
                   VERBATIM (no new formula, no fork).
  CAPTURE_SCOPED — the explicit no-S2 outcome: incomplete, conflicting,
                   undetermined, or a state that is not VALID/CLEAR. Never a
                   license to guess; candidate evidence is preserved for the
                   Gate/review concern; UNRESOLVED is never created here.

Definite duplicates (D-03) are detected by exact fingerprint equality across
DIFFERENT captures and recorded as append-only observations referencing the
original resolution — one document identity, made auditable, never merged
away. No fuzzy / heuristic / similarity / AI matching exists (AST-proven).

Boundary (normative): this layer performs NO canonicalization decision (the
P6.1 Gate remains the sole authority), NO Canonical Assembly, NO invoice_id
minting (P6.1/P6.2 own the Canonical Identity), NO product/customer matching,
NO semantic resolution of ANY kind, NO upstream execution, and NO mutation of
any frozen layer P1–P6.2 (purely additive WP).

Persistence: separate SQLite file, synchronous=FULL, atomic commit, immutable
records (no UPDATE / no DELETE), deterministic sha256-v1 fingerprints,
Verify-on-Read, tamper detection, restart safety, UNIQUE backstops
(INV-IR-S1:1 — one resolution per capture; INV-IR-DUP:1 — one observation per
resolution).
"""
from .model import (
    IDENTITY_SCOPE_S2,
    IDENTITY_SCOPE_CAPTURE_SCOPED,
    IDENTITY_SCOPES,
    IDENTITY_SOURCE_S2,
    IDENTITY_SOURCES,
    ROLE_INVOICE_NUMBER,
    ROLE_INVOICE_DATE,
    ROLE_INVOICE_TOTAL,
    IDENTITY_ROLES,
    ORIGIN_KANDOO_SALE,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    ORIGINS,
    CAPTURE_PIPELINE_ORIGINS,
    SCOPE_REASON_D03_INCOMPLETE,
    SCOPE_REASON_D03_CONFLICTING,
    SCOPE_REASON_D03_UNDETERMINED,
    SCOPE_REASON_S2_NOT_ATTEMPTED,
    CAPTURE_SCOPED_REASONS,
    REFUSE_ORIGIN_UNKNOWN,
    REFUSE_ORIGIN_NATIVE_FLOW,
    REFUSE_BINDING_MALFORMED,
    REFUSE_REPLAY_DECLARATION_DRIFT,
    REFUSE_NO_SUCH_STATE,
    NOTE_VERIFY_FAILED,
    STATE_VALID,
    DISPOSITION_CLEAR,
    utc_now_iso,
    parse_field_seqs,
    serialize_field_seqs,
    IdentityResolutionRecord,
    IdentityRoleCandidateRow,
    IdentityDuplicateObservation,
    RoleCandidateSpec,
    IdentityScopeDecision,
    IdentityLayerError,
    ResolutionNotFound,
    ResolutionDuplicate,
    IdentityPersistenceUnavailable,
    IdentityResolutionRecorded,
    IdentityDefiniteDuplicate,
    IdentityReplay,
    IdentityRequestRefused,
    IdentityInputIntegrityFailure,
    IdentityStorageUnavailable,
    IdentityReadSuccess,
    IdentityReadIntegrityFailure,
    IdentityReadRefused,
    IdentityReadVerificationUnavailable,
)
from .resolver import (
    resolve_document_identity,
    validate_declared_origin,
    binding_declaration_bytes,
    binding_declaration_fingerprint,
)
from .store import (
    IdentityResolutionStore,
    canonical_resolution_bytes,
    canonical_observation_bytes,
)
from .service import IdentityResolutionService

__all__ = [
    # vocabularies
    "IDENTITY_SCOPE_S2", "IDENTITY_SCOPE_CAPTURE_SCOPED", "IDENTITY_SCOPES",
    "IDENTITY_SOURCE_S2", "IDENTITY_SOURCES",
    "ROLE_INVOICE_NUMBER", "ROLE_INVOICE_DATE", "ROLE_INVOICE_TOTAL",
    "IDENTITY_ROLES",
    "ORIGIN_KANDOO_SALE", "ORIGIN_HOLOO_CAPTURE", "ORIGIN_OTHER_POS_CAPTURE",
    "ORIGINS", "CAPTURE_PIPELINE_ORIGINS",
    "SCOPE_REASON_D03_INCOMPLETE", "SCOPE_REASON_D03_CONFLICTING",
    "SCOPE_REASON_D03_UNDETERMINED", "SCOPE_REASON_S2_NOT_ATTEMPTED",
    "CAPTURE_SCOPED_REASONS",
    "REFUSE_ORIGIN_UNKNOWN", "REFUSE_ORIGIN_NATIVE_FLOW",
    "REFUSE_BINDING_MALFORMED", "REFUSE_REPLAY_DECLARATION_DRIFT",
    "REFUSE_NO_SUCH_STATE",
    "NOTE_VERIFY_FAILED", "STATE_VALID", "DISPOSITION_CLEAR",
    "utc_now_iso", "parse_field_seqs", "serialize_field_seqs",
    # records
    "IdentityResolutionRecord", "IdentityRoleCandidateRow",
    "IdentityDuplicateObservation", "RoleCandidateSpec",
    "IdentityScopeDecision",
    # exceptions
    "IdentityLayerError", "ResolutionNotFound", "ResolutionDuplicate",
    "IdentityPersistenceUnavailable",
    # resolve outcomes
    "IdentityResolutionRecorded", "IdentityDefiniteDuplicate",
    "IdentityReplay", "IdentityRequestRefused",
    "IdentityInputIntegrityFailure", "IdentityStorageUnavailable",
    # read outcomes
    "IdentityReadSuccess", "IdentityReadIntegrityFailure",
    "IdentityReadRefused", "IdentityReadVerificationUnavailable",
    # pure engines
    "resolve_document_identity", "validate_declared_origin",
    "binding_declaration_bytes", "binding_declaration_fingerprint",
    # persistence
    "IdentityResolutionStore",
    "canonical_resolution_bytes", "canonical_observation_bytes",
    # service
    "IdentityResolutionService",
]
