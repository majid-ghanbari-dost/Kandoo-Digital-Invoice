"""Kandoo Derivation Layer — WP-4.2 MVP implementation (DERIVED Provenance & Exact
Derivation Mechanism).

Normative basis (the ONLY authorities for this code):
  SPEC-WP42-DER  Derivation Contract v1.0-MVP (inline per TM/PO implementation
                 dispatch 2026-10-06) over REG-WPR §WP-4.2 (rescoped scope of record)
  D-01 (DERIVED produced verbatim — the ONLY label this layer can produce; UNRESOLVED
       is owned by P5 and is never created/assigned/inferred/resolved here) |
  D-08 (no rounding — a non-exact result is refused, never rounded; R2 is WP-5.1) |
  D-09 (delegated details declared: OD-D1..OD-D10) | AS-01 flow position:
  ... → Extraction → Normalization → **[this mechanism]** → Canonicalization Gate → ...

Implemented MVP flow (per the implementation dispatch):
  verified NormalizationReadSuccess (frozen WP-4.1, the ONLY value path) + healthy
  WP-3.2 evidence binding (frozen verified read, read-only) + a DECLARED versioned
  formula (data, never code) → declared-slot singleton resolution → EXACT rational
  arithmetic over canonical decimal strings (no float, no rounding; non-terminating
  DIV refuses) → atomic durable DerivationRecord + input POINTER rows → verified
  derivation read (VOR) + whole-chain traceability walk (derivation → normalization →
  extraction → binding → Document/Page/span → Capture S1).

Boundary: NO line grouping / association discovery, NO semantic/fuzzy matching, NO
tax/business interpretation, NO rounding, NO currency conversion, NO date arithmetic,
NO cross-document derivation, NO general unit_amount computation, NO canonical field
mapping, NO Sale/Invoice/Digital Invoice creation, NO Inventory/KPI mutation, NO
UNRESOLVED. Every refusal is explicit and exhaustive (DerivationDeferred with a
declared reason code — NOT_DERIVABLE, never a value, never persisted, never
UNRESOLVED); a silent result does not exist in this layer.
"""
from .model import (
    OUTPUT_PROVENANCE_DERIVED,
    REASON_INPUT_MISSING,
    REASON_INPUT_AMBIGUOUS,
    REASON_OUTPUT_PRESENT,
    REASON_NON_EXACT_RESULT,
    NOTE_VERIFY_FAILED,
    NOTE_VERIFICATION_UNAVAILABLE,
    DerivationInputRef,
    DerivationRecord,
    DerivationLayerError,
    DerivationFormulaError,
    DerivationNotFound,
    DerivationDuplicate,
    DerivationPersistenceUnavailable,
    DerivationCompleted,
    DerivationAlreadyExists,
    DerivationFormulaNotRegistered,
    DerivationDeferred,
    DerivationSourceIntegrityFailure,
    DerivationSourceRefused,
    DerivationSourceUnavailable,
    DerivationStorageUnavailable,
    DerivationReadSuccess,
    DerivationReadIntegrityFailure,
    DerivationReadRefused,
    DerivationReadVerificationUnavailable,
    DerivationTraceSuccess,
    DerivationTraceIntegrityFailure,
    DerivationTraceRefused,
    DerivationTraceVerificationUnavailable,
    utc_now_iso,
)
from .arithmetic import OPS, NonExactResult, parse_canonical_decimal, evaluate, \
    is_terminating_decimal, to_exact_decimal_string
from .formulas import (
    FormulaInput,
    FormulaInputRef,
    FormulaOp,
    DerivationFormula,
    canonical_formula_bytes,
    formula_fingerprint,
    DerivationFormulaRegistry,
    ReferenceDerivationFormulasV1,
)
from .store import DerivationStore, canonical_derivation_bytes
from .service import DerivationService

__all__ = [
    # model — vocabulary
    "OUTPUT_PROVENANCE_DERIVED",
    "REASON_INPUT_MISSING", "REASON_INPUT_AMBIGUOUS", "REASON_OUTPUT_PRESENT",
    "REASON_NON_EXACT_RESULT",
    "NOTE_VERIFY_FAILED", "NOTE_VERIFICATION_UNAVAILABLE",
    # model — records
    "DerivationInputRef", "DerivationRecord",
    # model — exceptions
    "DerivationLayerError", "DerivationFormulaError", "DerivationNotFound",
    "DerivationDuplicate", "DerivationPersistenceUnavailable",
    # model — derive outcomes
    "DerivationCompleted", "DerivationAlreadyExists", "DerivationFormulaNotRegistered",
    "DerivationDeferred", "DerivationSourceIntegrityFailure", "DerivationSourceRefused",
    "DerivationSourceUnavailable", "DerivationStorageUnavailable",
    # model — read outcomes
    "DerivationReadSuccess", "DerivationReadIntegrityFailure", "DerivationReadRefused",
    "DerivationReadVerificationUnavailable",
    # model — trace outcomes
    "DerivationTraceSuccess", "DerivationTraceIntegrityFailure",
    "DerivationTraceRefused", "DerivationTraceVerificationUnavailable",
    "utc_now_iso",
    # arithmetic
    "OPS", "NonExactResult", "parse_canonical_decimal", "evaluate",
    "is_terminating_decimal", "to_exact_decimal_string",
    # formulas
    "FormulaInput", "FormulaInputRef", "FormulaOp", "DerivationFormula",
    "canonical_formula_bytes", "formula_fingerprint", "DerivationFormulaRegistry",
    "ReferenceDerivationFormulasV1",
    # store
    "DerivationStore", "canonical_derivation_bytes",
    # service
    "DerivationService",
]
