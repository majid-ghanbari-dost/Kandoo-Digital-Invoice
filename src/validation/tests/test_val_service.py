"""Validation service behavior tests — WP-5.1 (SPEC-WP51-VAL §4/§5/§8).

Real pipeline data end-to-end: R1 presence/exact-consistency, R2 tolerated/rounded,
the DEFERRED matrix, replay/refusals, version separation, engine independence,
and the D-08 rounding audit record.
"""
import sys
from pathlib import Path
from fractions import Fraction

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import (
    RuleExprOp,
    RuleInput,
    RuleSlotRef,
    ValidationAlreadyExists,
    ValidationCompleted,
    ValidationRule,
    round_exact,
    to_fixed_decimal_string,
    REASON_ABSENT,
    REASON_AMBIGUOUS_INPUT,
    REASON_EXACT_MATCH,
    REASON_INSUFFICIENT_INPUT,
    REASON_MISMATCH,
    REASON_MISMATCH_AFTER_ROUNDING,
    REASON_MISMATCH_BEYOND_TOLERANCE,
    REASON_NON_EXACT_INTERMEDIATE,
    REASON_PRESENT_NOT_USABLE,
    REASON_ROUNDED_MATCH,
    REASON_WITHIN_TOLERANCE,
)
from derivation import (
    DerivationCompleted,
    DerivationFormula,
    DerivationFormulaRegistry,
    FormulaInput,
    FormulaInputRef,
    FormulaOp,
    ReferenceDerivationFormulasV1,
)
from capture import S1Service

from val_helpers import (
    AltEngine,
    FORMULA,
    PAGE_ABSENT_FIELD,
    PAGE_AMBIGUOUS,
    PAGE_DEFERRED_INPUT,
    PAGE_EU,
    PAGE_MISSING_TAX,
    PAGE_OK,
    PAGE_OK_ALT,
    PAGE_REJECTED_INPUT,
    R_CONSIST,
    R_PRESENT,
    R_ROUNDED,
    R_TOLERANCE,
    TOLERANCE,
    extended_service,
    presence_rule,
    quotient_rule,
    reference_rules,
    sub_expression_rule,
    swapped_rule,
)


def tolerated_probe(rule_id, target_field="q.target", target_origin="normalized",
                    tolerance=TOLERANCE):
    """|ADD(total.net, tax.amount) − target| ≤ tolerance over declared origins."""
    return ValidationRule(
        rule_id=rule_id, rule_version="1", rule_kind="R2",
        rule_type="tolerated-equality",
        inputs=(
            RuleInput(slot_name="target", field_name=target_field,
                      origin=target_origin),
            RuleInput(slot_name="net", field_name="total.net", origin="normalized"),
            RuleInput(slot_name="tax", field_name="tax.amount", origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("ADD", (RuleSlotRef("net"), RuleSlotRef("tax"))),
        tolerance=tolerance,
    )


def rounded_probe(rule_id, target_field="q.target", target_origin="normalized",
                  precision=2, mode="HALF_UP"):
    """ROUND(ADD(total.net, tax.amount), precision, mode) == target."""
    return ValidationRule(
        rule_id=rule_id, rule_version="1", rule_kind="R2",
        rule_type="rounded-equality",
        inputs=(
            RuleInput(slot_name="target", field_name=target_field,
                      origin=target_origin),
            RuleInput(slot_name="net", field_name="total.net", origin="normalized"),
            RuleInput(slot_name="tax", field_name="tax.amount", origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("ADD", (RuleSlotRef("net"), RuleSlotRef("tax"))),
        rounding_precision=precision,
        rounding_mode=mode,
    )


class TestR1Presence:
    def test_present_normalized_field_is_valid(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)
        outcome = stack.validate_ok(nid, R_PRESENT)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_EXACT_MATCH
        assert outcome.record.rule_kind == "R1"
        assert outcome.record.rounding_applied == 0
        assert outcome.record.input_count == 1
        ref = outcome.inputs[0]
        assert ref.value_origin == "NORMALIZED"
        assert ref.field_name == "total.net"
        assert ref.source_normalization_id == nid
        assert ref.source_derivation_id is None
        assert ref.source_field_seq is not None

    def test_absent_field_is_invalid(self, make_stack):
        probe = presence_rule(field_name="total.net")
        stack = make_stack(extra_rules=[probe])
        try:
            nid = stack.build_extract_normalize(PAGE_ABSENT_FIELD)
            outcome = stack.val.validate(nid, probe.rule_id, "1")
            assert isinstance(outcome, ValidationCompleted)
            assert outcome.record.outcome == "INVALID"
            assert outcome.record.outcome_reason == REASON_ABSENT
            assert outcome.record.input_count == 0
        finally:
            stack.close()

    def test_present_but_deferred_field_is_invalid_with_status_detail(self,
                                                                      make_stack):
        probe = presence_rule(field_name="tax.amount")
        stack = make_stack(extra_rules=[probe])
        try:
            nid = stack.build_extract_normalize(PAGE_DEFERRED_INPUT)
            outcome = stack.val.validate(nid, probe.rule_id, "1")
            assert isinstance(outcome, ValidationCompleted)
            assert outcome.record.outcome == "INVALID"
            assert outcome.record.outcome_reason == REASON_PRESENT_NOT_USABLE
            assert "DEFERRED" in outcome.record.outcome_detail
            assert outcome.record.input_count == 0
        finally:
            stack.close()

    def test_present_but_rejected_field_is_invalid_with_status_detail(self,
                                                                      make_stack):
        probe = presence_rule(field_name="tax.amount")
        stack = make_stack(extra_rules=[probe])
        try:
            nid = stack.build_extract_normalize(PAGE_REJECTED_INPUT)
            outcome = stack.val.validate(nid, probe.rule_id, "1")
            assert isinstance(outcome, ValidationCompleted)
            assert outcome.record.outcome == "INVALID"
            assert outcome.record.outcome_reason == REASON_PRESENT_NOT_USABLE
            assert "REJECTED" in outcome.record.outcome_detail
        finally:
            stack.close()

    def test_presence_of_derived_origin(self, stack):
        nid = stack.build_derive_validate_ready(PAGE_OK)
        probe = presence_rule(field_name="total.gross", origin="derived")
        service = extended_service(stack, probe)
        outcome = service.validate(nid, probe.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "VALID"
        ref = outcome.inputs[0]
        assert ref.value_origin == "DERIVED"
        assert ref.source_derivation_id is not None
        assert ref.source_field_seq is None

    def test_presence_of_derived_origin_without_derivation_is_invalid(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)   # derivation NOT run
        probe = presence_rule(field_name="total.gross", origin="derived")
        service = extended_service(stack, probe)
        outcome = service.validate(nid, probe.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "INVALID"
        assert outcome.record.outcome_reason == REASON_ABSENT
        assert "never triggers derivation" in outcome.record.outcome_detail


class TestR1ExactConsistency:
    def test_derived_input_matches_expression_exactly(self, stack):
        nid = stack.build_derive_validate_ready(PAGE_OK)   # 1000.00 + 80 → 1080
        outcome = stack.validate_ok(nid, R_CONSIST)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_EXACT_MATCH
        origins = {ref.value_origin for ref in outcome.inputs}
        assert origins == {"NORMALIZED", "DERIVED"}
        derived_ref = next(r for r in outcome.inputs if r.value_origin == "DERIVED")
        assert derived_ref.field_name == "total.gross"
        assert derived_ref.source_derivation_id is not None

    def test_european_grouping_inputs_consistent(self, stack):
        nid = stack.build_extract_normalize(PAGE_EU)       # 1234.56 + 196.80
        derived = stack.deriv.derive(nid, FORMULA, "1")
        assert isinstance(derived, DerivationCompleted)
        outcome = stack.validate_ok(nid, R_CONSIST)
        assert outcome.record.outcome == "VALID"
        assert "1431.36" in outcome.record.outcome_detail

    def test_genuine_mismatch_is_invalid_never_rubber_stamped(self, make_stack):
        stack = make_stack(extra_rules=[sub_expression_rule()])
        try:
            nid = stack.build_derive_validate_ready(PAGE_OK)   # total.gross = 1080
            outcome = stack.val.validate(nid, "test-consistency-sub-probe", "1")
            assert isinstance(outcome, ValidationCompleted)
            assert outcome.record.outcome == "INVALID"
            assert outcome.record.outcome_reason == REASON_MISMATCH
            assert "1080" in outcome.record.outcome_detail
            assert "920" in outcome.record.outcome_detail
        finally:
            stack.close()

    def test_missing_derived_input_is_deferred(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)       # derivation NOT run
        outcome = stack.val.validate(nid, R_CONSIST, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        assert outcome.record.outcome_reason == REASON_INSUFFICIENT_INPUT
        assert "no derivation record produces this field" in \
            outcome.record.outcome_detail
        # resolved normalized slots stay as audit-visible partial evidence
        assert outcome.record.input_count == 2
        assert {ref.field_name for ref in outcome.inputs} == \
            {"total.net", "tax.amount"}

    def test_missing_normalized_input_is_deferred(self, stack):
        nid = stack.build_extract_normalize(PAGE_MISSING_TAX)  # no tax.amount
        outcome = stack.val.validate(nid, R_CONSIST, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        assert outcome.record.outcome_reason == REASON_INSUFFICIENT_INPUT
        assert "no such field" in outcome.record.outcome_detail

    def test_deferred_status_input_is_insufficient_never_used(self, stack):
        nid = stack.build_extract_normalize(PAGE_DEFERRED_INPUT)
        outcome = stack.val.validate(nid, R_CONSIST, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        assert "none is NORMALIZED" in outcome.record.outcome_detail

    def test_rejected_status_input_is_insufficient_never_used(self, stack):
        nid = stack.build_extract_normalize(PAGE_REJECTED_INPUT)
        outcome = stack.val.validate(nid, R_CONSIST, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"

    def test_ambiguous_normalized_input_is_deferred_not_resolved(self, stack):
        nid = stack.build_extract_normalize(PAGE_AMBIGUOUS)  # two total.net fields
        outcome = stack.val.validate(nid, R_CONSIST, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        assert outcome.record.outcome_reason == REASON_AMBIGUOUS_INPUT
        assert "Canonicalization Gate" in outcome.record.outcome_detail

    def test_ambiguous_derived_input_is_deferred(self, make_stack):
        """Two formula versions producing the same output field → ambiguity, never
        a silent pick (association belongs to the Canonicalization Gate)."""
        second = DerivationFormula(
            formula_id=FORMULA, formula_version="2",
            output_field_name="total.gross",
            inputs=(FormulaInput(slot_name="tax", field_name="tax.amount"),
                    FormulaInput(slot_name="net", field_name="total.net")),
            expression=FormulaOp("ADD", (FormulaInputRef("tax"),
                                         FormulaInputRef("net"))),
        )
        stack = make_stack(formulas={**ReferenceDerivationFormulasV1(),
                                     (second.formula_id,
                                      second.formula_version): second})
        try:
            nid = stack.build_extract_normalize(PAGE_OK)
            assert isinstance(stack.deriv.derive(nid, FORMULA, "1"),
                              DerivationCompleted)
            assert isinstance(stack.deriv.derive(nid, FORMULA, "2"),
                              DerivationCompleted)
            outcome = stack.val.validate(nid, R_CONSIST, "1")
            assert isinstance(outcome, ValidationCompleted)
            assert outcome.record.outcome == "DEFERRED"
            assert outcome.record.outcome_reason == REASON_AMBIGUOUS_INPUT
            assert "2 derivation records" in outcome.record.outcome_detail
        finally:
            stack.close()

    def test_non_exact_intermediate_deferred_never_implicitly_rounded(self, stack):
        """DIV inside an R2 tolerated (exact-context) expression with a
        non-terminating quotient → DEFERRED, never rounded into validity."""
        nid = stack.build_extract_normalize(
            [b"total.net=1000.00\ntax.amount=80\nb=3\n"])
        derived = stack.deriv.derive(nid, FORMULA, "1")
        assert isinstance(derived, DerivationCompleted)
        rule = quotient_rule(rule_id="test-quotient-tolerated",
                             rule_type="tolerated-equality",
                             target_field="total.gross", target_origin="derived",
                             numerator="total.net", denominator="b",
                             tolerance="0.01")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        assert outcome.record.outcome_reason == REASON_NON_EXACT_INTERMEDIATE
        assert "never rounds implicitly" in outcome.record.outcome_detail


class TestR2ToleratedEquality:
    def test_exact_match_keeps_exact_value_no_tolerance_consumed(self, stack):
        nid = stack.build_derive_validate_ready(PAGE_OK)
        outcome = stack.validate_ok(nid, R_TOLERANCE)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_EXACT_MATCH
        assert "tolerance not consumed" in outcome.record.outcome_detail
        assert outcome.record.rounding_applied == 0

    def test_within_tolerance_is_valid_with_both_values_in_detail(self, stack):
        nid = stack.build_extract_normalize(
            [b"total.net=1000.00\ntax.amount=80\nq.target=1079.99\n"])
        rule = tolerated_probe("test-tolerated-probe")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_WITHIN_TOLERANCE
        assert "0.01" in outcome.record.outcome_detail   # |1080 − 1079.99|
        assert TOLERANCE in outcome.record.outcome_detail
        assert outcome.record.rounding_applied == 0      # tolerance ≠ rounding

    def test_beyond_tolerance_is_invalid_feeds_review_downstream(self, stack):
        nid = stack.build_extract_normalize(
            [b"total.net=1000.00\ntax.amount=80\nq.target=999.00\n"])
        rule = tolerated_probe("test-tolerated-beyond")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "INVALID"
        assert outcome.record.outcome_reason == REASON_MISMATCH_BEYOND_TOLERANCE
        assert "REVIEW path downstream per D-08" in outcome.record.outcome_detail

    def test_tolerance_boundary_is_inclusive(self, stack):
        """diff == tolerance exactly → still within (≤ is the declared semantics)."""
        nid = stack.build_extract_normalize(
            [b"total.net=1000.00\ntax.amount=80\nq.target=1079.98\n"])
        rule = tolerated_probe("test-tolerated-edge")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_WITHIN_TOLERANCE

    def test_zero_tolerance_reduces_to_exact_comparison(self, stack):
        nid = stack.build_derive_validate_ready(PAGE_OK)
        rule = tolerated_probe("test-tolerated-zero", target_field="total.gross",
                               target_origin="derived", tolerance="0")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_EXACT_MATCH

    def test_tolerance_parameter_is_versioned_in_the_fingerprint(self, stack):
        """The same rule identity with a different injected tolerance is a
        DIFFERENT declaration (distinct fingerprint → distinct record)."""
        nid = stack.build_derive_validate_ready(PAGE_OK)
        tight = tolerated_probe("test-tol-param", tolerance="0")
        loose = ValidationRule(
            **{**tight.__dict__, "rule_version": "2", "tolerance": "5"})
        service = extended_service(stack, tight, loose)
        v1 = service.validate(nid, tight.rule_id, "1")
        v2 = service.validate(nid, loose.rule_id, "2")
        assert isinstance(v1, ValidationCompleted)
        assert isinstance(v2, ValidationCompleted)
        assert v1.record.rule_fingerprint != v2.record.rule_fingerprint


class TestR2RoundedEquality:
    def test_exact_match_preserves_exact_value_rounding_not_applied(self, stack):
        nid = stack.build_derive_validate_ready(PAGE_OK)
        outcome = stack.validate_ok(nid, R_ROUNDED)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_EXACT_MATCH
        assert outcome.record.rounding_applied == 0
        assert outcome.record.rounding_precision is None
        assert outcome.record.rounding_mode is None
        assert outcome.record.rounding_input_value is None
        assert outcome.record.rounding_output_value is None

    def test_rounding_applied_when_exact_match_fails_audit_record_reproducible(
            self, stack):
        nid = stack.build_extract_normalize(
            [b"total.net=1000.00\ntax.amount=80.0004\nq.target=1080.00\n"])
        rule = rounded_probe("test-rounded-sum")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_ROUNDED_MATCH
        assert outcome.record.rounding_applied == 1
        assert outcome.record.rounding_precision == 2
        assert outcome.record.rounding_mode == "HALF_UP"
        assert outcome.record.rounding_input_value == "1080.0004"
        assert outcome.record.rounding_output_value == "1080.00"
        # reproducible: recomputing the declared rounding yields the same output
        assert to_fixed_decimal_string(
            round_exact(Fraction("1080.0004"), 2, "HALF_UP"), 2) == \
            outcome.record.rounding_output_value

    def test_mismatch_after_rounding_is_invalid_with_audit_record(self, stack):
        nid = stack.build_extract_normalize(
            [b"total.net=1000.00\ntax.amount=80.0004\nq.target=999.99\n"])
        rule = rounded_probe("test-rounded-mismatch")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "INVALID"
        assert outcome.record.outcome_reason == REASON_MISMATCH_AFTER_ROUNDING
        assert outcome.record.rounding_applied == 1
        assert outcome.record.rounding_output_value == "1080.00"

    def test_non_terminating_expression_rounds_explicitly_and_reproducibly(
            self, stack):
        """The declared R2 rounded type is the ONLY place a non-exact intermediate
        is acceptable — rounded explicitly at declared (precision, mode), never
        implicitly."""
        nid = stack.build_extract_normalize(
            [b"total.net=1000.00\nb=3\nq.target=333.33\n"])
        rule = quotient_rule(rule_id="test-quotient-rounded",
                             target_field="q.target", target_origin="normalized",
                             numerator="total.net", denominator="b",
                             precision=2, mode="HALF_UP")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "VALID"
        assert outcome.record.outcome_reason == REASON_ROUNDED_MATCH
        assert outcome.record.rounding_applied == 1
        assert outcome.record.rounding_input_value == "1000/3"  # exact rational
        # audit record is reproducible: the recorded input reproduces the output
        assert to_fixed_decimal_string(
            round_exact(Fraction("1000/3"), 2, "HALF_UP"), 2) == \
            outcome.record.rounding_output_value
        assert outcome.record.rounding_output_value == "333.33"

    def test_mode_is_declared_and_visible_half_up_vs_half_even(self, make_stack):
        """666.65 / 2 = 333.325 — an exact tie at precision 2: HALF_UP rounds away
        (→ 333.33 == target), HALF_EVEN rounds to even (→ 333.32 ≠ target). The
        declared mode is the ONLY difference — visible in both audit records."""
        up = quotient_rule(rule_id="test-mode-half-up", target_field="q.target",
                           target_origin="normalized", numerator="total.net",
                           denominator="b", precision=2, mode="HALF_UP")
        even = quotient_rule(rule_id="test-mode-half-even", target_field="q.target",
                             target_origin="normalized", numerator="total.net",
                             denominator="b", precision=2, mode="HALF_EVEN")
        stack = make_stack(extra_rules=[up, even])
        try:
            nid = stack.build_extract_normalize(
                [b"total.net=666.65\nb=2\nq.target=333.33\n"])
            v_up = stack.val.validate(nid, up.rule_id, "1")
            v_even = stack.val.validate(nid, even.rule_id, "1")
            assert isinstance(v_up, ValidationCompleted)
            assert isinstance(v_even, ValidationCompleted)
            assert v_up.record.outcome == "VALID"
            assert v_up.record.outcome_reason == REASON_ROUNDED_MATCH
            assert v_up.record.rounding_mode == "HALF_UP"
            assert v_up.record.rounding_input_value == "333.325"
            assert v_up.record.rounding_output_value == "333.33"
            assert v_even.record.outcome == "INVALID"
            assert v_even.record.outcome_reason == REASON_MISMATCH_AFTER_ROUNDING
            assert v_even.record.rounding_mode == "HALF_EVEN"
            assert v_even.record.rounding_output_value == "333.32"
        finally:
            stack.close()

    def test_precision_is_explicit_in_the_audit_output(self, stack):
        nid = stack.build_extract_normalize(
            [b"total.net=1000.00\ntax.amount=80.00004\nq.target=1080.0000\n"])
        rule = rounded_probe("test-rounded-precision", precision=4, mode="HALF_UP")
        service = extended_service(stack, rule)
        outcome = service.validate(nid, rule.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.rounding_precision == 4
        assert outcome.record.rounding_output_value == "1080.0000"
        assert outcome.record.outcome_reason == REASON_ROUNDED_MATCH


class TestReplayAndRefusals:
    def test_replay_returns_existing_record_explicitly(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)
        first = stack.validate_ok(nid, R_PRESENT)
        replay = stack.val.validate(nid, R_PRESENT, "1")
        assert isinstance(replay, ValidationAlreadyExists)
        assert replay.validation_id == first.record.validation_id
        assert stack.val.validations_for_normalization(nid) == \
            (first.record.validation_id,)

    def test_unknown_rule_refused_explicitly(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)
        outcome = stack.val.validate(nid, "no-such-rule", "1")
        assert type(outcome).__name__ == "ValidationRuleNotRegistered"

    def test_unknown_normalization_refused_explicitly(self, stack):
        from validation import ValidationSourceRefused
        outcome = stack.val.validate("no-such-normalization", R_PRESENT, "1")
        assert isinstance(outcome, ValidationSourceRefused)

    def test_unbound_extraction_refused_fail_closed(self, stack):
        from validation import ValidationSourceRefused
        document_id = stack.build_document(PAGE_OK)
        done = stack.extraction.extract(document_id, "reference-delimited-v1")
        extraction_id = done.extraction.extraction_id
        normed = stack.norm.normalize(extraction_id, "kandoo-norm-v1")   # NO binding
        outcome = stack.val.validate(normed.record.normalization_id, R_PRESENT, "1")
        assert isinstance(outcome, ValidationSourceRefused)
        assert "evidence binding" in outcome.detail

    def test_no_residue_after_failed_validation_attempt(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)
        stack.val.validate(nid, "no-such-rule", "1")
        assert stack.val.validations_for_normalization(nid) == ()


class TestVersionSeparationAndDeterminism:
    def test_rule_versions_are_distinct_durable_records(self, make_stack):
        stack = make_stack(extra_rules=[swapped_rule()])
        try:
            nid = stack.build_derive_validate_ready(PAGE_OK)
            v1 = stack.validate_ok(nid, R_CONSIST, "1")
            v2 = stack.val.validate(nid, R_CONSIST, "2")
            assert isinstance(v2, ValidationCompleted)
            assert v2.record.rule_version == "2"
            assert v2.record.validation_id != v1.record.validation_id
            assert v2.record.rule_fingerprint != v1.record.rule_fingerprint
            assert sorted(stack.val.validations_for_normalization(nid)) == sorted(
                [v1.record.validation_id, v2.record.validation_id])
        finally:
            stack.close()

    def test_identical_content_validates_identically_across_captures(self, stack):
        """D-03: reordered bytes are distinct captures; the validation CONTENT
        (outcome, reason, fingerprint) is identical — determinism axis."""
        nid_a = stack.build_extract_normalize(PAGE_OK, label="val-det-a")
        nid_b = stack.build_extract_normalize(PAGE_OK_ALT, label="val-det-b")
        for nid in (nid_a, nid_b):
            assert isinstance(stack.deriv.derive(nid, FORMULA, "1"),
                              DerivationCompleted)
        a = stack.validate_ok(nid_a, R_CONSIST)
        b = stack.validate_ok(nid_b, R_CONSIST)
        assert a.record.outcome == b.record.outcome == "VALID"
        assert a.record.outcome_reason == b.record.outcome_reason
        assert a.record.rule_fingerprint == b.record.rule_fingerprint
        assert a.record.rounding_applied == b.record.rounding_applied

    def test_revalidation_after_state_change_needs_new_version(self, stack):
        """A DEFERRED validation is immutable history: after the derivation runs,
        the same triple replays; the declared re-evaluation path is a new
        rule_version (no UPDATE/DELETE anywhere)."""
        nid = stack.build_extract_normalize(PAGE_OK)
        deferred = stack.val.validate(nid, R_CONSIST, "1")
        assert isinstance(deferred, ValidationCompleted)
        assert deferred.record.outcome == "DEFERRED"
        assert isinstance(stack.deriv.derive(nid, FORMULA, "1"),
                          DerivationCompleted)
        replay = stack.val.validate(nid, R_CONSIST, "1")
        assert type(replay).__name__ == "ValidationAlreadyExists"
        assert replay.validation_id == deferred.record.validation_id
        service = extended_service(stack, swapped_rule())
        v2 = service.validate(nid, R_CONSIST, "2")
        assert isinstance(v2, ValidationCompleted)
        assert v2.record.outcome == "VALID"            # new version, fresh verdict


class TestEngineIndependence:
    def test_alt_engine_output_validates_identically(self, make_stack):
        """Two engines over two distinct captures (reordered bytes, D-03) whose
        NORMALIZED content is identical → identical validation content. The
        validation layer imports no engine; only the seam differs."""
        from extraction import ReferenceDelimitedEngine
        stack = make_stack(engines={
            "reference-delimited-v1": ReferenceDelimitedEngine(),
            "alt-val-engine-v1": AltEngine()})
        try:
            nid_ref = stack.build_extract_normalize(PAGE_OK, label="val-eng-ref")
            nid_alt = stack.build_extract_normalize(PAGE_OK_ALT, engine_id=\
                "alt-val-engine-v1", label="val-eng-alt")
            for nid in (nid_ref, nid_alt):
                assert isinstance(stack.deriv.derive(nid, FORMULA, "1"),
                                  DerivationCompleted)
            outcome_ref = stack.validate_ok(nid_ref, R_CONSIST)
            outcome_alt = stack.validate_ok(nid_alt, R_CONSIST)
            assert outcome_ref.record.outcome == "VALID"
            assert outcome_alt.record.outcome == "VALID"
            assert outcome_alt.record.outcome_reason == \
                outcome_ref.record.outcome_reason
            assert outcome_alt.record.rule_fingerprint == \
                outcome_ref.record.rule_fingerprint
            assert outcome_alt.record.outcome_detail == \
                outcome_ref.record.outcome_detail
        finally:
            stack.close()
