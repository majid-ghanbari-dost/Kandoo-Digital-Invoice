"""Kandoo Normalization Layer — WP-4.1 MVP implementation.

Normative basis (the ONLY authorities for this code):
  SPEC-WP41-NORM  Normalization Contract v1.0-MVP (inline per TM dispatch 2026-10-01)
  D-01 provenance vocabulary relayed verbatim | D-02/D-03 untouched | D-09 governance freeze
  AS-01 flow position: ... → Extraction → **Normalization** → Canonicalization Gate → ...
  WP-1.1 / WP-2.1 / WP-3.1 frozen components — the only upstream dependencies (the verified
  extraction read is the only input path); no store is accessed in parallel.

Implemented MVP flow (per the implementation dispatch):
  verified ExtractionReadSuccess → registered ruleset (replaceable abstraction; reference
  ruleset included for MVP executability) → deterministic per-field application (TOTAL
  positional mapping, explicit NORMALIZED/DEFERRED/REJECTED statuses) → atomic durable
  NormalizationRecord + fields → verified normalization read, plus the mandated
  explicit-outcome behavior on every failure path.

Boundary: NO canonical field mapping, NO product/customer/invoice identity, NO fuzzy or
semantic matching, NO business rules, NO currency invention/conversion, NO DERIVED
computation (WP-4.2), NO OCR/VLM (D-09). Values are standardized by a DECLARED grammar
only; anything outside it gets an explicit DEFERRED/REJECTED status with a reason code.
Every normalized field stays traceable to its source extracted field (extraction_id +
field_seq) and — through WP-3.2 Evidence Binding — to Document/Page/span/Capture S1.
"""
from .model import (
    REASON_CONTROL_CHARACTER,
    REASON_EMPTY_VALUE,
    REASON_NOT_IN_DECLARED_GRAMMAR,
    NOTE_VERIFY_FAILED,
    NOTE_VERIFICATION_UNAVAILABLE,
    NormalizationStatus,
    NormalizedField,
    NormalizationRecord,
    NormalizationLayerError,
    NormalizationNotFound,
    NormalizationDuplicate,
    NormalizationPersistenceUnavailable,
    NormalizationCompleted,
    NormalizationAlreadyExists,
    NormalizationSourceIntegrityFailure,
    NormalizationSourceRefused,
    NormalizationSourceUnavailable,
    NormalizationRulesetNotRegistered,
    NormalizationStorageUnavailable,
    NormalizationReadSuccess,
    NormalizationReadIntegrityFailure,
    NormalizationReadRefused,
    NormalizationReadVerificationUnavailable,
    utc_now_iso,
)
from .rules import (
    RULE_NFC,
    RULE_TRIM,
    RULE_NUMBER,
    RULE_DATE,
    NormalizationRuleSet,
    ReferenceNormalizationRulesV1,
)
from .store import NormalizationStore, canonical_normalization_bytes
from .service import NormalizationService

__all__ = [
    # model
    "NormalizationStatus", "NormalizedField", "NormalizationRecord",
    "REASON_EMPTY_VALUE", "REASON_NOT_IN_DECLARED_GRAMMAR", "REASON_CONTROL_CHARACTER",
    "NOTE_VERIFY_FAILED", "NOTE_VERIFICATION_UNAVAILABLE",
    "NormalizationLayerError", "NormalizationNotFound", "NormalizationDuplicate",
    "NormalizationPersistenceUnavailable",
    "NormalizationCompleted", "NormalizationAlreadyExists",
    "NormalizationSourceIntegrityFailure", "NormalizationSourceRefused",
    "NormalizationSourceUnavailable", "NormalizationRulesetNotRegistered",
    "NormalizationStorageUnavailable",
    "NormalizationReadSuccess", "NormalizationReadIntegrityFailure",
    "NormalizationReadRefused", "NormalizationReadVerificationUnavailable",
    "utc_now_iso",
    # ruleset seam + reference ruleset
    "RULE_NFC", "RULE_TRIM", "RULE_NUMBER", "RULE_DATE",
    "NormalizationRuleSet", "ReferenceNormalizationRulesV1",
    # store / service
    "NormalizationStore", "canonical_normalization_bytes", "NormalizationService",
]
