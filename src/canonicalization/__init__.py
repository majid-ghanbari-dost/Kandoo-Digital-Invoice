"""Kandoo Canonicalization Gate Layer — WP-6.1 MVP implementation (the first
real boundary of data entering the Canonical Invoice domain).

The gate consumes VERIFIED P5.2 domain-state records (SPEC-WP52-VSM — the
frozen vocabulary VALID | INVALID | DEFERRED | UNRESOLVED + REVIEW/REJECT
dispositions per AD-04), re-verifies their complete upstream provenance chain
through the P5.2 whole-chain walk (down to Capture S1), resolves the External
Document Identity strictly per D-02 (S2 exact triad → DETERMINISTIC, otherwise
explicitly CAPTURE_SCOPED), applies the D-03 idempotency/duplicate decision
table, and — only when every frozen condition holds — creates the durable,
immutable, provenance-anchored Canonical Invoice admission record. Everything
else fails closed into the frozen routing vocabulary.

Gate decisions (dispatch §14 paths VERBATIM):
    ACCEPTED | REJECTED | REVIEW | ALREADY_CANONICALIZED
Origins (dispatch §7 set VERBATIM):
    KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE
Identity classes (D-02 VERBATIM):
    DETERMINISTIC | CAPTURE_SCOPED

Boundary (normative): this layer performs NO semantic resolution, NO fuzzy /
heuristic / AI matching, NO product or customer matching, NO tax or currency
interpretation, NO inventory / Sale / KPI / Customer mutation, NO upstream
execution, and NO Canonical Assembly (WP-6.2 owns assembly + the formal
invoice_id issuance workflow). It never creates UNRESOLVED (D-01 — P5.2 is the
only legal creator); unresolved inputs route REVIEW.

Persistence: separate SQLite file, synchronous=FULL, atomic commit, immutable
history (no UPDATE / no DELETE), deterministic sha256-v1 fingerprints,
Verify-on-Read, tamper detection, restart safety, idempotent behavior.
"""
from .model import (
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    DECISION_REVIEW,
    DECISION_ALREADY_CANONICALIZED,
    DECISIONS,
    ORIGIN_KANDOO_SALE,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    ORIGINS,
    CAPTURE_PIPELINE_ORIGINS,
    IDENTITY_CLASS_DETERMINISTIC,
    IDENTITY_CLASS_CAPTURE_SCOPED,
    IDENTITY_CLASSES,
    IDENTITY_SOURCE_S2,
    IDENTITY_SOURCES,
    ROLE_INVOICE_NUMBER,
    ROLE_INVOICE_DATE,
    ROLE_INVOICE_TOTAL,
    IDENTITY_ROLES,
    REASON_UPSTREAM_DECISIVE_INVALID,
    REASON_D03_DEFINITE_DUPLICATE,
    REASON_D02_CAPTURE_REPLAY,
    REASON_ALL_FROZEN_CONDITIONS_MET,
    RELAYED_REVIEW_REASONS,
    REASON_D03_INCOMPLETE_IDENTITY,
    REASON_D03_CONFLICTING_IDENTITY,
    REASON_D03_UNDETERMINED_IDENTITY,
    GATE_REVIEW_REASONS,
    GATE_REJECT_REASONS,
    DECISION_REASONS,
    EVENT_ANNOTATE,
    EVENT_CLOSE,
    EVENT_TYPES,
    REVIEW_STATUS_OPEN,
    REVIEW_STATUS_CLOSED,
    NOTE_VERIFY_FAILED,
    REFUSE_ORIGIN_UNKNOWN,
    REFUSE_ORIGIN_NATIVE_FLOW,
    REFUSE_BINDING_MALFORMED,
    utc_now_iso,
    RoleResolution,
    IdentityResolution,
    GateDecisionRecord,
    CanonicalInvoiceRecord,
    CanonicalIdentityPointer,
    GateReviewItem,
    GateReviewEvent,
    CanonicalizationLayerError,
    GateDecisionNotFound,
    GateDecisionDuplicate,
    CanonicalInvoiceNotFound,
    GateReviewItemNotFound,
    CanonicalizationPersistenceUnavailable,
    CanonicalizationAccepted,
    CanonicalizationRejected,
    CanonicalizationRoutedToReview,
    CanonicalizationAlreadyCanonicalized,
    CanonicalizationAlreadyDecided,
    CanonicalizationInputIntegrityFailure,
    CanonicalizationRequestRefused,
    CanonicalizationStorageUnavailable,
    GateDecisionReadSuccess,
    GateDecisionReadIntegrityFailure,
    GateDecisionReadRefused,
    GateDecisionReadVerificationUnavailable,
    CanonicalInvoiceReadSuccess,
    CanonicalInvoiceReadIntegrityFailure,
    CanonicalInvoiceReadRefused,
    CanonicalInvoiceReadVerificationUnavailable,
    GateReviewItemReadSuccess,
    GateReviewItemReadIntegrityFailure,
    GateReviewItemReadRefused,
    GateReviewItemReadVerificationUnavailable,
    GateEventAppended,
    GateEventRefused,
    GateEventUnavailable,
    CanonicalInvoiceTraceSuccess,
    CanonicalInvoiceTraceIntegrityFailure,
    CanonicalInvoiceTraceRefused,
    CanonicalInvoiceTraceVerificationUnavailable,
)
from .identity import resolve_identity, validate_binding
from .gate import GateRoute, route_decision, validate_route, state_summary
from .store import (
    CanonicalizationGateStore,
    canonical_decision_bytes,
    canonical_invoice_bytes,
    canonical_item_bytes,
    canonical_event_bytes,
)
from .service import CanonicalizationGateService

__all__ = [
    # vocabularies
    "DECISION_ACCEPTED", "DECISION_REJECTED", "DECISION_REVIEW",
    "DECISION_ALREADY_CANONICALIZED", "DECISIONS",
    "ORIGIN_KANDOO_SALE", "ORIGIN_HOLOO_CAPTURE", "ORIGIN_OTHER_POS_CAPTURE",
    "ORIGINS", "CAPTURE_PIPELINE_ORIGINS",
    "IDENTITY_CLASS_DETERMINISTIC", "IDENTITY_CLASS_CAPTURE_SCOPED",
    "IDENTITY_CLASSES", "IDENTITY_SOURCE_S2", "IDENTITY_SOURCES",
    "ROLE_INVOICE_NUMBER", "ROLE_INVOICE_DATE", "ROLE_INVOICE_TOTAL",
    "IDENTITY_ROLES",
    "REASON_UPSTREAM_DECISIVE_INVALID", "REASON_D03_DEFINITE_DUPLICATE",
    "REASON_D02_CAPTURE_REPLAY", "REASON_ALL_FROZEN_CONDITIONS_MET",
    "RELAYED_REVIEW_REASONS", "REASON_D03_INCOMPLETE_IDENTITY",
    "REASON_D03_CONFLICTING_IDENTITY", "REASON_D03_UNDETERMINED_IDENTITY",
    "GATE_REVIEW_REASONS", "GATE_REJECT_REASONS", "DECISION_REASONS",
    "EVENT_ANNOTATE", "EVENT_CLOSE", "EVENT_TYPES",
    "REVIEW_STATUS_OPEN", "REVIEW_STATUS_CLOSED",
    "NOTE_VERIFY_FAILED",
    "REFUSE_ORIGIN_UNKNOWN", "REFUSE_ORIGIN_NATIVE_FLOW",
    "REFUSE_BINDING_MALFORMED",
    "utc_now_iso",
    # records
    "RoleResolution", "IdentityResolution",
    "GateDecisionRecord", "CanonicalInvoiceRecord",
    "CanonicalIdentityPointer", "GateReviewItem", "GateReviewEvent",
    # exceptions
    "CanonicalizationLayerError", "GateDecisionNotFound",
    "GateDecisionDuplicate", "CanonicalInvoiceNotFound",
    "GateReviewItemNotFound", "CanonicalizationPersistenceUnavailable",
    # canonicalize outcomes
    "CanonicalizationAccepted", "CanonicalizationRejected",
    "CanonicalizationRoutedToReview", "CanonicalizationAlreadyCanonicalized",
    "CanonicalizationAlreadyDecided", "CanonicalizationInputIntegrityFailure",
    "CanonicalizationRequestRefused", "CanonicalizationStorageUnavailable",
    # read outcomes
    "GateDecisionReadSuccess", "GateDecisionReadIntegrityFailure",
    "GateDecisionReadRefused", "GateDecisionReadVerificationUnavailable",
    "CanonicalInvoiceReadSuccess", "CanonicalInvoiceReadIntegrityFailure",
    "CanonicalInvoiceReadRefused", "CanonicalInvoiceReadVerificationUnavailable",
    "GateReviewItemReadSuccess", "GateReviewItemReadIntegrityFailure",
    "GateReviewItemReadRefused", "GateReviewItemReadVerificationUnavailable",
    "GateEventAppended", "GateEventRefused", "GateEventUnavailable",
    "CanonicalInvoiceTraceSuccess", "CanonicalInvoiceTraceIntegrityFailure",
    "CanonicalInvoiceTraceRefused", "CanonicalInvoiceTraceVerificationUnavailable",
    # pure engines
    "resolve_identity", "validate_binding",
    "GateRoute", "route_decision", "validate_route", "state_summary",
    # persistence
    "CanonicalizationGateStore",
    "canonical_decision_bytes", "canonical_invoice_bytes",
    "canonical_item_bytes", "canonical_event_bytes",
    # service
    "CanonicalizationGateService",
]
