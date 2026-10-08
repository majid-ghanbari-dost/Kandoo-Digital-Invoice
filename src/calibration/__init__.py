"""kandoo.src.calibration — WP-12.2 Calibration Runs (P12 Pilot layer).

Runs the FROZEN pipeline over a verified WP-12.1 corpus inside an isolated
workspace and emits ONE deterministic calibration report (measurements
only). Ratifies nothing (WP-12.3 is PO/G4); touches nothing outside its
workspace; consumes the frozen services verbatim, never modifies them.
"""
from .model import (  # noqa: F401
    AGREEMENT_RULE_ID,
    CLASSIFICATIONS,
    CLASS_MATCH,
    CLASS_MISSING,
    CLASS_MISMATCH,
    CLASS_UNEXPECTED_PRESENT,
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    DECISION_REVIEW,
    ENGINE_REFERENCE,
    FORMULA_ID,
    FORMULA_VERSION,
    IDENTITY_BINDING,
    NORM_RULESET,
    ORIGIN_HOLOO_CAPTURE,
    REFERENCE_RULE_IDS,
    SOURCE_LABEL,
    VSM_RULESET,
    VSM_RULESET_VERSION,
    CalibrationInputRefused,
    CalibrationReport,
    CalibrationRunRefused,
    CandidateResult,
    EntryObservation,
    FieldObservation,
    RunConfig,
)
from .stack import CalibrationStack  # noqa: F401
from .runner import CalibrationRunService  # noqa: F401

__all__ = [
    "AGREEMENT_RULE_ID",
    "CalibrationInputRefused",
    "CalibrationReport",
    "CalibrationRunRefused",
    "CalibrationRunService",
    "CalibrationStack",
    "CandidateResult",
    "CLASSIFICATIONS",
    "CLASS_MATCH",
    "CLASS_MISSING",
    "CLASS_MISMATCH",
    "CLASS_UNEXPECTED_PRESENT",
    "DECISION_ACCEPTED",
    "DECISION_REJECTED",
    "DECISION_REVIEW",
    "ENGINE_REFERENCE",
    "EntryObservation",
    "FieldObservation",
    "FORMULA_ID",
    "FORMULA_VERSION",
    "IDENTITY_BINDING",
    "NORM_RULESET",
    "ORIGIN_HOLOO_CAPTURE",
    "REFERENCE_RULE_IDS",
    "RunConfig",
    "SOURCE_LABEL",
    "VSM_RULESET",
    "VSM_RULESET_VERSION",
]
