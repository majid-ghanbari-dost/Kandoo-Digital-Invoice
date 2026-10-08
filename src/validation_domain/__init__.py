"""Kandoo Validation Domain Layer — WP-5.2 MVP implementation (Validation State
Machine + REVIEW Queue).

Normative basis (the ONLY authorities for this code):
  SPEC-WP52-VSM  Validation State Machine + REVIEW Queue Contract v1.0-MVP
                 (inline per TM/PO implementation dispatch 2026-10-07) over
                 REG-WPR Phase Index P5
  AS-03 (the Validation State Machine is transferred VERBATIM from the frozen
        source vocabulary — no state redefined, renamed, or added) | AD-04 (the
        Validation output model includes REVIEW and REJECT; field-level
        UNRESOLVED can take the Invoice to REVIEW; CL-1 — no paraphrase) | D-01
        (resolution order EXTRACTED → DERIVED → UNRESOLVED; UNRESOLVED is created
        HERE — field-level, reason/status-bearing, traceable, never auto-resolved
        — the ONLY layer allowed to create it) | D-03 (conflicting/incomplete →
        REVIEW) | D-08 (unresolved mismatch → REVIEW) | D-09 (delegated details
        declared: OD-S1..OD-S14) | AD-02 (Validation domain boundary) | AS-01
        flow position: P3 → P4.1 → P4.2 → P5.1 → **[this layer]** →
        Canonicalization Gate → ...

Implemented MVP flow (per the implementation dispatch):
  verified P5.1 validation records (the R1/R2 engine's durable verdicts — the
  ONLY rule-outcome path) + verified normalization read (frozen WP-4.1 — the
  ONLY NORMALIZED fact path) + fingerprint-checked rule declarations (frozen
  WP-5.1 registry) → completeness gate (declared keys == evaluated set) →
  field-level D-01 projection (RESOLVED with relayed origin/pointers |
  UNRESOLVED with the frozen d01-no-valid-method reason) → deterministic
  transition function (declared priority T1..T5) → frozen vocabulary state
  (VALID | INVALID | DEFERRED | UNRESOLVED) + disposition (CLEAR | REVIEW |
  REJECT) → atomic durable DomainStateRecord + validation pointer rows + field
  projection rows + REVIEW queue item (iff REVIEW) → verified reads (VOR) +
  append-only hash-chained REVIEW lifecycle (ANNOTATE | CLOSE; status derived
  from history; CLOSE terminal) + whole-chain traceability walk (domain state →
  P5.1 whole-chain sub-walks → normalization → extraction → binding →
  Document/Page/span → Capture S1).

Boundary: NO canonical field mapping, NO line grouping/association discovery, NO
product/customer/invoice-identity matching, NO semantic/fuzzy matching, NO
business rules, NO tax/currency/date logic, NO cross-document anything, NO
validation/derivation/normalization execution, NO automatic semantic resolution
of any kind, NO Canonicalization Gate logic (P6), NO Canonical Invoice/Sale/
Digital Invoice creation, NO history overwrite (no UPDATE/DELETE — the queue
lifecycle is append-only). Every outcome is explicit and exhaustive; a silent
result does not exist in this layer.
"""
from .model import (
    DOMAIN_STATE_VALID,
    DOMAIN_STATE_INVALID,
    DOMAIN_STATE_DEFERRED,
    DOMAIN_STATE_UNRESOLVED,
    DOMAIN_STATES,
    DISPOSITION_CLEAR,
    DISPOSITION_REVIEW,
    DISPOSITION_REJECT,
    DISPOSITIONS,
    REASON_DECISIVE_INVALID,
    REASON_D08_MISMATCH_REVIEW,
    REASON_D01_UNRESOLVED_REVIEW,
    REASON_VALIDATION_DEFERRED_REVIEW,
    REASON_ALL_RULES_VALID,
    DECISIVE_INVALID_REASONS,
    TOLERANCE_INVALID_REASONS,
    PROJECTION_RESOLVED,
    PROJECTION_UNRESOLVED,
    PROJECTION_STATUSES,
    ORIGIN_RELAY_NORMALIZED,
    ORIGIN_RELAY_DERIVED,
    UNRESOLVED_REASON_D01,
    EVENT_ANNOTATE,
    EVENT_CLOSE,
    EVENT_TYPES,
    REVIEW_STATUS_OPEN,
    REVIEW_STATUS_CLOSED,
    NOTE_VERIFY_FAILED,
    NOTE_VERIFICATION_UNAVAILABLE,
    StateValidationRef,
    FieldProjectionRow,
    DomainStateRecord,
    ReviewQueueItem,
    ReviewQueueEvent,
    ValidationDomainError,
    DomainStateNotFound,
    DomainStateDuplicate,
    DomainStatePersistenceUnavailable,
    DomainStateProjected,
    DomainStateAlreadyExists,
    DomainStateSourceIntegrityFailure,
    DomainStateSourceRefused,
    DomainStateSourceUnavailable,
    DomainStateStorageUnavailable,
    DomainStateReadSuccess,
    DomainStateReadIntegrityFailure,
    DomainStateReadRefused,
    DomainStateReadVerificationUnavailable,
    ReviewItemReadSuccess,
    ReviewItemReadIntegrityFailure,
    ReviewItemReadRefused,
    ReviewItemReadVerificationUnavailable,
    ReviewEventAppended,
    ReviewEventRefused,
    ReviewEventUnavailable,
    DomainStateTraceSuccess,
    DomainStateTraceIntegrityFailure,
    DomainStateTraceRefused,
    DomainStateTraceVerificationUnavailable,
    utc_now_iso,
)
from .machine import (
    canonical_ruleset_bytes,
    ruleset_fingerprint,
    project_fields,
    derive_state,
    build_state_record,
)
from .store import (
    ValidationDomainStore,
    canonical_state_bytes,
    canonical_item_bytes,
    canonical_event_bytes,
)
from .service import ValidationDomainService

__all__ = [
    # vocabulary
    "DOMAIN_STATE_VALID", "DOMAIN_STATE_INVALID", "DOMAIN_STATE_DEFERRED",
    "DOMAIN_STATE_UNRESOLVED", "DOMAIN_STATES",
    "DISPOSITION_CLEAR", "DISPOSITION_REVIEW", "DISPOSITION_REJECT",
    "DISPOSITIONS",
    "REASON_DECISIVE_INVALID", "REASON_D08_MISMATCH_REVIEW",
    "REASON_D01_UNRESOLVED_REVIEW", "REASON_VALIDATION_DEFERRED_REVIEW",
    "REASON_ALL_RULES_VALID",
    "DECISIVE_INVALID_REASONS", "TOLERANCE_INVALID_REASONS",
    "PROJECTION_RESOLVED", "PROJECTION_UNRESOLVED", "PROJECTION_STATUSES",
    "ORIGIN_RELAY_NORMALIZED", "ORIGIN_RELAY_DERIVED", "UNRESOLVED_REASON_D01",
    "EVENT_ANNOTATE", "EVENT_CLOSE", "EVENT_TYPES",
    "REVIEW_STATUS_OPEN", "REVIEW_STATUS_CLOSED",
    "NOTE_VERIFY_FAILED", "NOTE_VERIFICATION_UNAVAILABLE",
    # records
    "StateValidationRef", "FieldProjectionRow", "DomainStateRecord",
    "ReviewQueueItem", "ReviewQueueEvent",
    # exceptions
    "ValidationDomainError", "DomainStateNotFound", "DomainStateDuplicate",
    "DomainStatePersistenceUnavailable",
    # projection outcomes
    "DomainStateProjected", "DomainStateAlreadyExists",
    "DomainStateSourceIntegrityFailure", "DomainStateSourceRefused",
    "DomainStateSourceUnavailable", "DomainStateStorageUnavailable",
    # read outcomes
    "DomainStateReadSuccess", "DomainStateReadIntegrityFailure",
    "DomainStateReadRefused", "DomainStateReadVerificationUnavailable",
    "ReviewItemReadSuccess", "ReviewItemReadIntegrityFailure",
    "ReviewItemReadRefused", "ReviewItemReadVerificationUnavailable",
    # event outcomes
    "ReviewEventAppended", "ReviewEventRefused", "ReviewEventUnavailable",
    # trace outcomes
    "DomainStateTraceSuccess", "DomainStateTraceIntegrityFailure",
    "DomainStateTraceRefused", "DomainStateTraceVerificationUnavailable",
    # machine
    "canonical_ruleset_bytes", "ruleset_fingerprint", "project_fields",
    "derive_state", "build_state_record",
    # store
    "ValidationDomainStore", "canonical_state_bytes", "canonical_item_bytes",
    "canonical_event_bytes",
    # service
    "ValidationDomainService", "utc_now_iso",
]
