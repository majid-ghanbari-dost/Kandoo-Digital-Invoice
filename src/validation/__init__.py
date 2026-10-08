"""Kandoo Validation Layer — WP-5.1 MVP implementation (R1/R2 Validation Engine).

Normative basis (the ONLY authorities for this code):
  SPEC-WP51-VAL  R1/R2 Validation Engine Contract v1.0-MVP (inline per TM/PO
                 implementation dispatch 2026-10-07) over REG-WPR Phase Index P5
  D-01 (UNRESOLVED is owned by the P5 domain layer and is never created, assigned,
       inferred, or resolved here) | D-08 (R2 tolerance/rounding parametric and
       injected — no fixed values; explicit rounding only, float never exists) |
       D-09 (delegated details declared: OD-V1..OD-V11) | AD-02 (Validation domain
       boundary) | AD-04 + AS-03 (Validation State Machine = WP-5.2 with the
       verbatim Frozen Canonical Invoice v1 vocabulary — this engine defines NO
       invoice states) | AS-01 flow position: P3 → P4.1 → P4.2 → **[this engine]**
       → Canonicalization Gate → ...

Implemented MVP flow (per the implementation dispatch):
  verified NormalizationReadSuccess (frozen WP-4.1, the ONLY NORMALIZED value path)
  + verified derivation reads (WP-4.2 service, the ONLY DERIVED value path) + healthy
  WP-3.2 evidence binding (fail-closed gate) + a DECLARED versioned fingerprinted
  R1/R2 rule (data, never code) → declared-slot resolution → explicit rule verdict
  (VALID | INVALID | DEFERRED — durable; UNRESOLVED structurally impossible) →
  atomic durable ValidationRecord + input POINTER rows → verified validation read
  (VOR) + whole-chain traceability walk (validation → rule → inputs → [WP-4.2
  sub-chain for DERIVED inputs] → normalization → extraction → binding →
  Document/Page/span → Capture S1).

Boundary: NO canonical field mapping, NO line grouping/association discovery, NO
product/customer/invoice-identity matching, NO semantic/fuzzy matching, NO business
rules, NO tax-rate/discount/markup/currency logic, NO date arithmetic, NO
cross-document validation, NO value production (the R2 rounding record is an audit
artifact of the comparison, never a pipeline value), NO creation or resolution of
UNRESOLVED, NO Validation State Machine (WP-5.2). Every outcome is explicit and
exhaustive; a silent result does not exist in this layer.
"""
from .model import (
    RULE_KIND_R1,
    RULE_KIND_R2,
    OUTCOME_VALID,
    OUTCOME_INVALID,
    OUTCOME_DEFERRED,
    VALUE_ORIGIN_NORMALIZED,
    VALUE_ORIGIN_DERIVED,
    REASON_EXACT_MATCH,
    REASON_WITHIN_TOLERANCE,
    REASON_ROUNDED_MATCH,
    REASON_ABSENT,
    REASON_PRESENT_NOT_USABLE,
    REASON_MISMATCH,
    REASON_MISMATCH_BEYOND_TOLERANCE,
    REASON_MISMATCH_AFTER_ROUNDING,
    REASON_INSUFFICIENT_INPUT,
    REASON_AMBIGUOUS_INPUT,
    REASON_NON_EXACT_INTERMEDIATE,
    NOTE_VERIFY_FAILED,
    NOTE_VERIFICATION_UNAVAILABLE,
    ValidationInputRef,
    ValidationRecord,
    ValidationLayerError,
    ValidationRuleError,
    ValidationNotFound,
    ValidationDuplicate,
    ValidationPersistenceUnavailable,
    ValidationCompleted,
    ValidationAlreadyExists,
    ValidationRuleNotRegistered,
    ValidationSourceIntegrityFailure,
    ValidationSourceRefused,
    ValidationSourceUnavailable,
    ValidationStorageUnavailable,
    ValidationReadSuccess,
    ValidationReadIntegrityFailure,
    ValidationReadRefused,
    ValidationReadVerificationUnavailable,
    ValidationTraceSuccess,
    ValidationTraceIntegrityFailure,
    ValidationTraceRefused,
    ValidationTraceVerificationUnavailable,
    utc_now_iso,
)
from .rounding import (
    ROUNDING_MODES,
    RoundingModeError,
    exact_value_string,
    round_exact,
    to_fixed_decimal_string,
)
from .rules import (
    RuleInput,
    RuleSlotRef,
    RuleExprOp,
    ValidationRule,
    ValidationRuleRegistry,
    ReferenceValidationRulesV1,
    canonical_rule_bytes,
    rule_fingerprint,
)
from .store import ValidationStore, canonical_validation_bytes
from .service import ValidationService

__all__ = [
    "RULE_KIND_R1", "RULE_KIND_R2",
    "OUTCOME_VALID", "OUTCOME_INVALID", "OUTCOME_DEFERRED",
    "VALUE_ORIGIN_NORMALIZED", "VALUE_ORIGIN_DERIVED",
    "REASON_EXACT_MATCH", "REASON_WITHIN_TOLERANCE", "REASON_ROUNDED_MATCH",
    "REASON_ABSENT", "REASON_PRESENT_NOT_USABLE", "REASON_MISMATCH",
    "REASON_MISMATCH_BEYOND_TOLERANCE", "REASON_MISMATCH_AFTER_ROUNDING",
    "REASON_INSUFFICIENT_INPUT", "REASON_AMBIGUOUS_INPUT",
    "REASON_NON_EXACT_INTERMEDIATE",
    "NOTE_VERIFY_FAILED", "NOTE_VERIFICATION_UNAVAILABLE",
    "ValidationInputRef", "ValidationRecord",
    "ValidationLayerError", "ValidationRuleError", "ValidationNotFound",
    "ValidationDuplicate", "ValidationPersistenceUnavailable",
    "ValidationCompleted", "ValidationAlreadyExists",
    "ValidationRuleNotRegistered",
    "ValidationSourceIntegrityFailure", "ValidationSourceRefused",
    "ValidationSourceUnavailable", "ValidationStorageUnavailable",
    "ValidationReadSuccess", "ValidationReadIntegrityFailure",
    "ValidationReadRefused", "ValidationReadVerificationUnavailable",
    "ValidationTraceSuccess", "ValidationTraceIntegrityFailure",
    "ValidationTraceRefused", "ValidationTraceVerificationUnavailable",
    "utc_now_iso",
    "ROUNDING_MODES", "RoundingModeError", "round_exact",
    "to_fixed_decimal_string", "exact_value_string",
    "RuleInput", "RuleSlotRef", "RuleExprOp", "ValidationRule",
    "ValidationRuleRegistry", "ReferenceValidationRulesV1",
    "canonical_rule_bytes", "rule_fingerprint",
    "ValidationStore", "canonical_validation_bytes",
    "ValidationService",
]
