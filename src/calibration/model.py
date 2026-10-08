"""Calibration run model — WP-12.2 (SPEC-WP122-CAL §3/§5/§6/§7).

Measurements only. The report carries COUNTS and declared-configuration
echoes — never verdicts, never rates, never threshold comparisons. The
report is a pure function of (corpus content, declared configuration):
no wall-clock, no uuid bookkeeping values, no paths, no environment.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Declared run configuration (SPEC §3)
# ---------------------------------------------------------------------------

ORIGIN_HOLOO_CAPTURE = "HOLOO_CAPTURE"
ENGINE_REFERENCE = "reference-delimited-v1"
NORM_RULESET = "kandoo-norm-v1"
VSM_RULESET = "kandoo-vsm-rules"
VSM_RULESET_VERSION = "1"
FORMULA_ID = "kandoo-der-total-gross-from-net-tax"
FORMULA_VERSION = "1"
AGREEMENT_RULE_ID = "kandoo-cal-declared-gross-agreement"
SOURCE_LABEL = "calibration"

# The D-02 identity role → source-field binding (declared, echoed verbatim).
IDENTITY_BINDING = {
    "INVOICE_NUMBER": "invoice.number",
    "INVOICE_DATE": "invoice.date",
    "INVOICE_TOTAL": "total.net",
}

# The declared reference ruleset id/version keys are the registry's own
# (rule_id, version) pairs — the four frozen reference rules.
REFERENCE_RULE_IDS = (
    "kandoo-val-total-net-present",
    "kandoo-val-total-gross-consistency",
    "kandoo-val-total-gross-tolerance",
    "kandoo-val-total-gross-rounded",
)

# Gate decision vocabulary (frozen, relayed verbatim)
DECISION_ACCEPTED = "ACCEPTED"
DECISION_REVIEW = "REVIEW"
DECISION_REJECTED = "REJECTED"

# Field-observation vocabulary (SPEC §5)
CLASS_MATCH = "MATCH"
CLASS_MISMATCH = "MISMATCH"
CLASS_MISSING = "MISSING"
CLASS_UNEXPECTED_PRESENT = "UNEXPECTED_PRESENT"
CLASSIFICATIONS = (CLASS_MATCH, CLASS_MISMATCH, CLASS_MISSING,
                   CLASS_UNEXPECTED_PRESENT)


@dataclass(frozen=True)
class RunConfig:
    """The declared run configuration — echoed verbatim in the report."""
    corpus_version_id: str
    origin: str = ORIGIN_HOLOO_CAPTURE
    engine_id: str = ENGINE_REFERENCE
    norm_ruleset_id: str = NORM_RULESET
    vsm_ruleset_id: str = VSM_RULESET
    vsm_ruleset_version: str = VSM_RULESET_VERSION
    formula_id: str = FORMULA_ID
    formula_version: str = FORMULA_VERSION
    tolerance: str = "0.02"          # D-08 declared placeholder — injected,
    precision: int = 2               # never hardcoded in the frozen engine
    mode: str = "HALF_UP"            # (echoed here, ratified nowhere)
    candidate_tolerances: Tuple[str, ...] = ("0.00", "0.01", "0.02")
    identity_binding: Tuple[Tuple[str, str], ...] = tuple(
        sorted(IDENTITY_BINDING.items()))
    agreement_rule_id: str = AGREEMENT_RULE_ID

    def binding_dict(self) -> Dict[str, str]:
        return dict(self.identity_binding)


class CalibrationInputRefused(Exception):
    """Declared run inputs are malformed — nothing runs."""


class CalibrationRunRefused(Exception):
    """The run cannot start (used workspace / unverifiable corpus)."""


# ---------------------------------------------------------------------------
# Observations (per entry — SPEC §4/§5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldObservation:
    """One label's classification against the verified normalization read."""
    field_name: str
    label_kind: str                  # VALUE | ABSENT
    classification: str              # CLASS_* vocabulary
    observed_status: Optional[str]   # NORMALIZED | DEFERRED | REJECTED | None
    observed_value: Optional[str]    # only for a present NORMALIZED row


@dataclass(frozen=True)
class EntryObservation:
    """One corpus entry's measured path (deterministic scalars only — no
    uuid bookkeeping, no timestamps, no paths)."""
    ordinal: int
    stage_reached: str               # capture|reconstruct|...|gate
    gate_decision: Optional[str]     # ACCEPTED|REVIEW|REJECTED|None
    gate_reason: Optional[str]
    reference_outcomes: Tuple[Tuple[str, str, Optional[str]], ...]
    # (rule_id, outcome, outcome_reason) in declared reference order
    field_observations: Tuple[FieldObservation, ...]


@dataclass(frozen=True)
class CandidateResult:
    """One D-08 candidate's honest counts (SPEC §6)."""
    tolerance: str
    evaluated: int
    within_tolerance: int
    beyond_tolerance: int
    not_evaluable: int


# ---------------------------------------------------------------------------
# The report (SPEC §7 — the run's ONLY output)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationReport:
    """Deterministic calibration report — counts and echoes, nothing else."""
    config: RunConfig
    corpus_entry_count: int
    entry_observations: Tuple[EntryObservation, ...]
    field_counts: Dict[str, Dict[str, int]]   # field_name → classification → n
    gate_counts: Dict[str, int]               # decision → n
    reference_rule_counts: Dict[str, Dict[str, int]]  # rule_id → outcome → n
    candidate_results: Tuple[CandidateResult, ...]
    unverified_details: Tuple[str, ...] = field(default=())

    def to_dict(self) -> Dict[str, object]:
        """Canonical structure — sorted keys at serialization time."""
        return {
            "report": "kandoo-calibration-report-v1",
            "config": {
                "corpus_version_id": self.config.corpus_version_id,
                "origin": self.config.origin,
                "engine_id": self.config.engine_id,
                "norm_ruleset_id": self.config.norm_ruleset_id,
                "vsm_ruleset_id": self.config.vsm_ruleset_id,
                "vsm_ruleset_version": self.config.vsm_ruleset_version,
                "formula_id": self.config.formula_id,
                "formula_version": self.config.formula_version,
                "declared_reference_parameters": {
                    "tolerance": self.config.tolerance,
                    "precision": self.config.precision,
                    "mode": self.config.mode,
                },
                "candidate_tolerances": list(self.config.candidate_tolerances),
                "identity_binding": [
                    {"role": role, "source_field": name}
                    for role, name in self.config.identity_binding],
                "agreement_rule_id": self.config.agreement_rule_id,
            },
            "corpus_entry_count": self.corpus_entry_count,
            "entry_observations": [
                {
                    "ordinal": obs.ordinal,
                    "stage_reached": obs.stage_reached,
                    "gate_decision": obs.gate_decision,
                    "gate_reason": obs.gate_reason,
                    "reference_outcomes": [
                        {"rule_id": rule_id, "outcome": outcome,
                         "outcome_reason": reason}
                        for rule_id, outcome, reason in obs.reference_outcomes],
                    "field_observations": [
                        {"field_name": fo.field_name,
                         "label_kind": fo.label_kind,
                         "classification": fo.classification,
                         "observed_status": fo.observed_status,
                         "observed_value": fo.observed_value}
                        for fo in obs.field_observations],
                }
                for obs in self.entry_observations],
            "field_counts": {
                name: dict(sorted(counts.items()))
                for name, counts in sorted(self.field_counts.items())},
            "gate_counts": dict(sorted(self.gate_counts.items())),
            "reference_rule_counts": {
                rule_id: dict(sorted(counts.items()))
                for rule_id, counts in sorted(
                    self.reference_rule_counts.items())},
            "tolerance_candidate_results": [
                {"tolerance": c.tolerance, "evaluated": c.evaluated,
                 "within_tolerance": c.within_tolerance,
                 "beyond_tolerance": c.beyond_tolerance,
                 "not_evaluable": c.not_evaluable}
                for c in self.candidate_results],
        }

    def to_json_bytes(self) -> bytes:
        """Deterministic canonical JSON (sorted keys, stable separators)."""
        return json.dumps(self.to_dict(), sort_keys=True,
                          separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")
