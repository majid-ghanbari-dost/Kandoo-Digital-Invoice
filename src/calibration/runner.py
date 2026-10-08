"""Calibration run service — WP-12.2 (SPEC-WP122-CAL §4/§5/§6/§7/§8).

The measured path (M1..M9) executes the FROZEN pipeline verbatim inside the
isolated workspace and records observations. It decides nothing: the report
carries counts; WP-12.3 (PO/G4) is the only ratification surface.

Determinism: every recorded value is a pure function of (corpus content,
declared configuration). Two fresh workspaces produce byte-identical report
JSON. No wall-clock, no uuid bookkeeping values, no paths in the report.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from capture import (
    CaptureService,
    IngestCompleted,
    IngestDuplicateAtCapture,
    S1Service,
)
from extraction import BindingCompleted, ExtractionCompleted
from normalization import (
    NormalizationCompleted,
    NormalizationReadSuccess,
    ReferenceNormalizationRulesV1,
)
from reconstruction import ReconstructCompleted
from validation import ReferenceValidationRulesV1
from validation_domain import DomainStateProjected
from canonicalization import (
    CanonicalizationAccepted,
    CanonicalizationAlreadyCanonicalized,
    CanonicalizationRejected,
    CanonicalizationRoutedToReview,
)
from corpus import (
    LABEL_KIND_ABSENT,
    LABEL_KIND_VALUE,
    CorpusReadSuccess,
)

from .model import (
    CLASS_MATCH,
    CLASS_MISSING,
    CLASS_MISMATCH,
    CLASS_UNEXPECTED_PRESENT,
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    DECISION_REVIEW,
    FieldObservation,
    EntryObservation,
    CandidateResult,
    CalibrationInputRefused,
    CalibrationReport,
    CalibrationRunRefused,
    RunConfig,
)
from .stack import CalibrationStack

_RUN_SCHEMA = """
CREATE TABLE IF NOT EXISTS calibration_runs (
    corpus_version_id TEXT PRIMARY KEY
);
"""


class CalibrationRunService:
    """One calibration run per workspace; report-only output."""

    def __init__(self, workspace: Path, s1: S1Service) -> None:
        if not isinstance(s1, S1Service):
            raise CalibrationInputRefused(
                "calibration requires the capture S1Service — no second hash")
        self._workspace = Path(workspace)
        self._s1 = s1

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, corpus_read: CorpusReadSuccess, config: RunConfig) \
            -> CalibrationReport:
        self._validate_config(config)
        self._verify_corpus(corpus_read, config)
        self._claim_workspace(config)

        entries = corpus_read.entries
        observations: List[EntryObservation] = []
        field_counts: Dict[str, Dict[str, int]] = {}
        gate_counts: Dict[str, int] = {}
        rule_counts: Dict[str, Dict[str, int]] = {}

        with CalibrationStack(
                self._workspace, self._s1,
                reference_rules=self._reference_rules(
                    config, config.tolerance),
                norm_ruleset=ReferenceNormalizationRulesV1()) as stack:
            for entry in entries:
                observation = self._measure_entry(stack, config, entry)
                observations.append(observation)
                self._aggregate(observation, field_counts, gate_counts,
                                rule_counts)

        candidate_results = self._sweep(config, entries)
        return CalibrationReport(
            config=config,
            corpus_entry_count=len(entries),
            entry_observations=tuple(observations),
            field_counts=field_counts,
            gate_counts=gate_counts,
            reference_rule_counts=rule_counts,
            candidate_results=tuple(candidate_results),
        )

    # ------------------------------------------------------------------
    # Pre-flight (SPEC §8 — refusals before any pipeline work)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_config(config: RunConfig) -> None:
        if not isinstance(config.corpus_version_id, str) \
                or not config.corpus_version_id:
            raise CalibrationInputRefused("corpus_version_id must be a non-empty string")
        if not config.candidate_tolerances:
            raise CalibrationInputRefused(
                "candidate_tolerances must be a non-empty declared tuple")
        for candidate in config.candidate_tolerances:
            if not isinstance(candidate, str) or not candidate:
                raise CalibrationInputRefused(
                    f"candidate tolerance must be a non-empty string, got "
                    f"{candidate!r}")
            try:
                value = float(candidate)
            except ValueError:
                raise CalibrationInputRefused(
                    f"candidate tolerance not a decimal string: {candidate!r}")
            if value < 0:
                raise CalibrationInputRefused(
                    f"candidate tolerance must be >= 0: {candidate!r}")
        if not isinstance(config.tolerance, str) or not config.tolerance:
            raise CalibrationInputRefused("tolerance must be a declared string")
        # only the declared reference engine/ruleset exist in this WP
        if config.engine_id != "reference-delimited-v1":
            raise CalibrationInputRefused(
                f"undeclared engine_id: {config.engine_id!r}")
        if config.norm_ruleset_id != "kandoo-norm-v1":
            raise CalibrationInputRefused(
                f"undeclared norm ruleset: {config.norm_ruleset_id!r}")

    @staticmethod
    def _verify_corpus(corpus_read, config: RunConfig) -> None:
        if not isinstance(corpus_read, CorpusReadSuccess):
            raise CalibrationRunRefused(
                "run requires a VERIFIED corpus read (CorpusReadSuccess)")
        if corpus_read.manifest.corpus_version_id \
                != config.corpus_version_id:
            raise CalibrationRunRefused(
                "corpus read does not match the configured corpus address")

    def _claim_workspace(self, config: RunConfig) -> None:
        """ONE run per workspace (SPEC §2.8/OD-CR-E) — a used workspace is a
        typed refusal; the claim itself is durable."""
        self._workspace.mkdir(parents=True, exist_ok=True)
        manifest_conn = sqlite3.connect(str(self._workspace / "run-manifest.db"))
        try:
            manifest_conn.executescript(_RUN_SCHEMA)
            existing = manifest_conn.execute(
                "SELECT corpus_version_id FROM calibration_runs").fetchall()
            if existing:
                raise CalibrationRunRefused(
                    f"workspace already holds a calibration run "
                    f"({existing[0][0][:16]}…) — a fresh workspace is required")
            manifest_conn.execute(
                "INSERT INTO calibration_runs (corpus_version_id) VALUES (?)",
                (config.corpus_version_id,))
            manifest_conn.commit()
        finally:
            manifest_conn.close()

    # ------------------------------------------------------------------
    # The measured path (SPEC §4)
    # ------------------------------------------------------------------

    def _measure_entry(self, stack: CalibrationStack, config: RunConfig,
                       entry) -> EntryObservation:
        ordinal = entry.ordinal
        stage = "capture"

        # M1 capture
        content = CaptureService.aggregate(tuple(entry.parts))
        ingest = stack.capture.ingest(content, source_label="calibration")
        if isinstance(ingest, IngestDuplicateAtCapture):
            capture_id = ingest.existing_capture_id
        elif isinstance(ingest, IngestCompleted):
            capture_id = ingest.capture_id
        else:
            return EntryObservation(
                ordinal=ordinal, stage_reached=stage, gate_decision=None,
                gate_reason=type(ingest).__name__,
                reference_outcomes=(), field_observations=())
        stage = "reconstruct"

        # M2 reconstruct
        built = stack.recon.reconstruct(capture_id)
        if not isinstance(built, ReconstructCompleted):
            return self._halt(ordinal, stage, built)
        document_id = built.document.document_id
        stage = "extract"

        # M3 extract
        extracted = stack.extraction.extract(document_id, config.engine_id)
        if not isinstance(extracted, ExtractionCompleted):
            return self._halt(ordinal, stage, extracted)
        extraction_id = extracted.extraction.extraction_id
        stage = "bind"

        # M4 evidence binding
        bound = stack.binder.bind_extraction(extraction_id)
        if not isinstance(bound, BindingCompleted):
            return self._halt(ordinal, stage, bound)
        stage = "normalize"

        # M5 normalize
        normed = stack.norm.normalize(extraction_id, config.norm_ruleset_id)
        if not isinstance(normed, NormalizationCompleted):
            return self._halt(ordinal, stage, normed)
        normalization_id = normed.record.normalization_id
        field_observations = self._observe_fields(stack, config, normalization_id,
                                                  entry.labels)
        stage = "derive"

        # M6 derive (deferred/unresolved derivation is an observation, not
        # an error — D-01/D-08 territory)
        derived = stack.deriv.derive(normalization_id, config.formula_id,
                                     config.formula_version)
        if type(derived).__name__ not in ("DerivationCompleted",
                                          "DerivationDeferred"):
            return EntryObservation(
                ordinal=ordinal, stage_reached=stage, gate_decision=None,
                gate_reason=type(derived).__name__,
                reference_outcomes=(), field_observations=field_observations)
        stage = "validate"

        # M7 the four declared reference rules
        reference_outcomes: List[Tuple[str, str, Optional[str]]] = []
        projection_ready = True
        for rule_id, rule_version in self._reference_keys(config):
            outcome = stack.val.validate(normalization_id, rule_id, rule_version)
            record = getattr(outcome, "record", None)
            if record is None:
                projection_ready = False
                reference_outcomes.append(
                    (rule_id, type(outcome).__name__, None))
                continue
            reference_outcomes.append(
                (rule_id, record.outcome, record.outcome_reason))
        if not projection_ready:
            return EntryObservation(
                ordinal=ordinal, stage_reached=stage, gate_decision=None,
                gate_reason="validation-not-completed",
                reference_outcomes=tuple(reference_outcomes),
                field_observations=field_observations)
        stage = "project"

        # M8 domain projection
        projected = stack.vsm.project_domain_state(
            normalization_id, config.vsm_ruleset_id, config.vsm_ruleset_version,
            list(self._reference_keys(config)))
        if not isinstance(projected, DomainStateProjected):
            return self._halt_with_fields(
                ordinal, stage, projected, reference_outcomes,
                field_observations)
        domain_state_id = projected.record.domain_state_id
        stage = "gate"

        # M9 the frozen gate
        decided = stack.gate.canonicalize(
            domain_state_id, config.origin, config.binding_dict())
        if isinstance(decided, (CanonicalizationAccepted,
                                CanonicalizationAlreadyCanonicalized)):
            decision, reason = DECISION_ACCEPTED, None
        elif isinstance(decided, CanonicalizationRoutedToReview):
            decision, reason = DECISION_REVIEW, decided.decision.decision_reason
        elif isinstance(decided, CanonicalizationRejected):
            decision, reason = DECISION_REJECTED, decided.decision.decision_reason
        else:
            return EntryObservation(
                ordinal=ordinal, stage_reached=stage, gate_decision=None,
                gate_reason=type(decided).__name__,
                reference_outcomes=tuple(reference_outcomes),
                field_observations=field_observations)
        return EntryObservation(
            ordinal=ordinal, stage_reached=stage, gate_decision=decision,
            gate_reason=reason, reference_outcomes=tuple(reference_outcomes),
            field_observations=field_observations)

    @staticmethod
    def _reference_keys(config: RunConfig) -> Tuple[Tuple[str, str], ...]:
        return tuple((rule_id, "1") for rule_id in
                     ("kandoo-val-total-net-present",
                      "kandoo-val-total-gross-consistency",
                      "kandoo-val-total-gross-tolerance",
                      "kandoo-val-total-gross-rounded"))

    @staticmethod
    def _reference_rules(config: RunConfig, tolerance: str) -> dict:
        return dict(ReferenceValidationRulesV1(
            tolerance=tolerance, precision=config.precision,
            mode=config.mode))

    def _halt(self, ordinal: int, stage: str, outcome) -> EntryObservation:
        return EntryObservation(
            ordinal=ordinal, stage_reached=stage, gate_decision=None,
            gate_reason=type(outcome).__name__, reference_outcomes=(),
            field_observations=())

    def _halt_with_fields(self, ordinal: int, stage: str, outcome,
                          reference_outcomes, field_observations) \
            -> EntryObservation:
        return EntryObservation(
            ordinal=ordinal, stage_reached=stage, gate_decision=None,
            gate_reason=type(outcome).__name__,
            reference_outcomes=reference_outcomes,
            field_observations=field_observations)

    # ------------------------------------------------------------------
    # Field observations (SPEC §5)
    # ------------------------------------------------------------------

    def _observe_fields(self, stack: CalibrationStack, config: RunConfig,
                        normalization_id: str, labels) \
            -> Tuple[FieldObservation, ...]:
        read = stack.norm.read_normalization(normalization_id)
        if not isinstance(read, NormalizationReadSuccess):
            return tuple(FieldObservation(
                field_name=label.field_name, label_kind=label.kind,
                classification=CLASS_MISSING, observed_status=None,
                observed_value=None) for label in labels)
        by_field: Dict[str, list] = {}
        for normalized in read.fields:
            by_field.setdefault(normalized.source_field_name, []).append(
                normalized)
        observations: List[FieldObservation] = []
        for label in labels:
            rows = by_field.get(label.field_name, [])
            if label.kind == LABEL_KIND_ABSENT:
                classification = CLASS_MATCH if not rows \
                    else CLASS_UNEXPECTED_PRESENT
                observations.append(FieldObservation(
                    field_name=label.field_name, label_kind=label.kind,
                    classification=classification,
                    observed_status=rows[0].status.value if rows else None,
                    observed_value=rows[0].normalized_value if rows else None))
                continue
            # VALUE label
            normalized_rows = [r for r in rows
                               if r.status.value == "NORMALIZED"]
            if not rows:
                classification = CLASS_MISSING
                observed_status, observed_value = None, None
            elif len(normalized_rows) == 1 and \
                    normalized_rows[0].normalized_value == label.expected_value:
                classification = CLASS_MATCH
                observed_status = normalized_rows[0].status.value
                observed_value = normalized_rows[0].normalized_value
            elif normalized_rows:
                classification = CLASS_MISMATCH
                observed_status = normalized_rows[0].status.value
                observed_value = normalized_rows[0].normalized_value
            else:
                classification = CLASS_MISMATCH
                observed_status = rows[0].status.value
                observed_value = None
            observations.append(FieldObservation(
                field_name=label.field_name, label_kind=label.kind,
                classification=classification,
                observed_status=observed_status,
                observed_value=observed_value))
        return tuple(observations)

    # ------------------------------------------------------------------
    # Aggregation (counts only — SPEC §1/§5)
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate(observation: EntryObservation, field_counts,
                   gate_counts, rule_counts) -> None:
        for fo in observation.field_observations:
            per_field = field_counts.setdefault(fo.field_name, {})
            per_field[fo.classification] = per_field.get(fo.classification, 0) + 1
        if observation.gate_decision is not None:
            gate_counts[observation.gate_decision] = \
                gate_counts.get(observation.gate_decision, 0) + 1
        else:
            key = f"NOT_REACHED:{observation.stage_reached}"
            gate_counts[key] = gate_counts.get(key, 0) + 1
        for rule_id, outcome, _reason in observation.reference_outcomes:
            per_rule = rule_counts.setdefault(rule_id, {})
            per_rule[outcome] = per_rule.get(outcome, 0) + 1

    # ------------------------------------------------------------------
    # The D-08 tolerance-candidate sweep (SPEC §6)
    # ------------------------------------------------------------------

    def _sweep(self, config: RunConfig, entries) -> List[CandidateResult]:
        from validation import (
            RuleExprOp,
            RuleInput,
            RuleSlotRef,
            ValidationRule,
        )

        results: List[CandidateResult] = []
        for index, candidate in enumerate(config.candidate_tolerances):
            sub_workspace = self._workspace / f"candidate-{index}"
            agreement_rule = ValidationRule(
                rule_id=config.agreement_rule_id,
                rule_version="1",
                rule_kind="R2",
                rule_type="tolerated-equality",
                inputs=(
                    RuleInput(slot_name="target",
                              field_name="total.gross",
                              origin="normalized"),
                    RuleInput(slot_name="net",
                              field_name="total.net",
                              origin="normalized"),
                    RuleInput(slot_name="tax",
                              field_name="tax.amount",
                              origin="normalized"),
                ),
                target_slot="target",
                expression=RuleExprOp("ADD", (RuleSlotRef("net"),
                                              RuleSlotRef("tax"))),
                tolerance=candidate,
            )
            rules = self._reference_rules(config, candidate)
            rules[(agreement_rule.rule_id, agreement_rule.rule_version)] = \
                agreement_rule
            evaluated = within = beyond = not_evaluable = 0
            with CalibrationStack(
                    sub_workspace, self._s1, reference_rules=rules,
                    norm_ruleset=ReferenceNormalizationRulesV1()) as stack:
                for entry in entries:
                    outcome = self._sweep_one(stack, config, entry,
                                              config.agreement_rule_id)
                    if outcome is None:
                        not_evaluable += 1
                    elif outcome == "VALID":
                        evaluated += 1
                        within += 1
                    elif outcome == "INVALID":
                        evaluated += 1
                        beyond += 1
                    else:
                        not_evaluable += 1
            results.append(CandidateResult(
                tolerance=candidate, evaluated=evaluated,
                within_tolerance=within, beyond_tolerance=beyond,
                not_evaluable=not_evaluable))
        return results

    def _sweep_one(self, stack: CalibrationStack, config: RunConfig,
                   entry, agreement_rule_id: str) -> Optional[str]:
        """The candidate path: capture → … → derive, then the declared
        agreement rule at THIS candidate's tolerance. Returns the raw
        outcome (VALID/INVALID/other) or None when the entry's path broke
        before validation."""
        content = CaptureService.aggregate(tuple(entry.parts))
        ingest = stack.capture.ingest(content, source_label="calibration")
        if isinstance(ingest, IngestDuplicateAtCapture):
            capture_id = ingest.existing_capture_id
        elif isinstance(ingest, IngestCompleted):
            capture_id = ingest.capture_id
        else:
            return None
        built = stack.recon.reconstruct(capture_id)
        if not isinstance(built, ReconstructCompleted):
            return None
        extracted = stack.extraction.extract(
            built.document.document_id, config.engine_id)
        if not isinstance(extracted, ExtractionCompleted):
            return None
        bound = stack.binder.bind_extraction(
            extracted.extraction.extraction_id)
        if not isinstance(bound, BindingCompleted):
            return None
        normed = stack.norm.normalize(extracted.extraction.extraction_id,
                                      config.norm_ruleset_id)
        if not isinstance(normed, NormalizationCompleted):
            return None
        normalization_id = normed.record.normalization_id
        derived = stack.deriv.derive(normalization_id, config.formula_id,
                                     config.formula_version)
        if type(derived).__name__ not in ("DerivationCompleted",
                                          "DerivationDeferred"):
            return None
        outcome = stack.val.validate(normalization_id, agreement_rule_id, "1")
        record = getattr(outcome, "record", None)
        if record is None:
            return None
        return record.outcome
