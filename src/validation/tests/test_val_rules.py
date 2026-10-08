"""Rule Registry behavior tests — WP-5.1 (SPEC-WP51-VAL §3).

A rule is DATA: fail-closed registration validation, deterministic fingerprints,
version coexistence, injected D-08 parameters (no hardcoded values), and no
arbitrary code anywhere in the registry path.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1Service

from validation import (
    RuleExprOp,
    RuleInput,
    RuleSlotRef,
    ValidationRule,
    ValidationRuleError,
    ValidationRuleRegistry,
    ReferenceValidationRulesV1,
    canonical_rule_bytes,
    rule_fingerprint,
)

from val_helpers import (
    R_CONSIST,
    R_PRESENT,
    R_ROUNDED,
    R_TOLERANCE,
    presence_rule,
    quotient_rule,
    reference_rules,
    sub_expression_rule,
    swapped_rule,
)


def make_rule(**kwargs):
    base = dict(
        rule_id="test-rule", rule_version="1", rule_kind="R1",
        rule_type="exact-consistency",
        inputs=(
            RuleInput(slot_name="target", field_name="total.gross", origin="derived"),
            RuleInput(slot_name="net", field_name="total.net", origin="normalized"),
        ),
        target_slot="target",
        expression=RuleSlotRef("net"),
    )
    base.update(kwargs)
    return ValidationRule(**base)


def registration_error(rule):
    """Assert the declaration is refused at REGISTRATION (the only gate)."""
    if isinstance(rule, dict):
        with pytest.raises(ValidationRuleError):
            ValidationRuleRegistry(rule, S1Service())
        return
    with pytest.raises(ValidationRuleError):
        ValidationRuleRegistry({(rule.rule_id, rule.rule_version): rule},
                               S1Service())


def registers_cleanly(rule):
    registry = ValidationRuleRegistry({(rule.rule_id, rule.rule_version): rule},
                                      S1Service())
    assert (rule.rule_id, rule.rule_version) in registry


class TestRegistrationRefusals:
    def test_wellformed_rule_registers(self):
        registers_cleanly(make_rule())

    def test_only_declaration_instances_registrable(self):
        registration_error({("x", "1"): "not-a-rule"})

    def test_registry_key_must_match_declaration(self):
        with pytest.raises(ValidationRuleError):
            ValidationRuleRegistry({("other", "1"): make_rule()}, S1Service())

    def test_registry_keys_must_be_pairs(self):
        registration_error({"solo": make_rule()})

    @pytest.mark.parametrize("field", ["rule_id", "rule_version", "rule_kind",
                                       "rule_type"])
    def test_empty_identity_fields_refused(self, field):
        registration_error(make_rule(**{field: ""}))

    def test_undeclared_kind_refused(self):
        registration_error(make_rule(rule_kind="R3"))

    def test_type_not_declared_for_kind_refused(self):
        registration_error(make_rule(rule_type="rounded-equality",
                                     rounding_precision=2,
                                     rounding_mode="HALF_UP"))
        registration_error(make_rule(rule_kind="R2", rule_type="presence"))

    def test_r1_cannot_carry_tolerance_or_rounding(self):
        registration_error(make_rule(tolerance="0.01"))
        registration_error(make_rule(rounding_precision=2))
        registration_error(make_rule(rounding_mode="HALF_UP"))

    def test_duplicate_slot_names_refused(self):
        registration_error(make_rule(inputs=(
            RuleInput(slot_name="a", field_name="total.net", origin="normalized"),
            RuleInput(slot_name="a", field_name="tax.amount", origin="normalized"),
        )))

    def test_undeclared_origin_refused(self):
        registration_error(make_rule(inputs=(RuleInput(
            slot_name="a", field_name="f", origin="canonical"),)))

    def test_dangling_expression_leaf_refused(self):
        registration_error(make_rule(expression=RuleSlotRef("ghost")))

    @pytest.mark.parametrize("payload", [42, "net", 3.14, lambda v: v, None])
    def test_non_declaration_expression_payloads_refused(self, payload):
        registration_error(make_rule(expression=payload))

    def test_literal_inside_op_tree_refused(self):
        registration_error(make_rule(expression=RuleExprOp(
            "ADD", (RuleSlotRef("net"), 2))))

    def test_callable_inside_op_tree_refused(self):
        registration_error(make_rule(expression=RuleExprOp(
            "ADD", (RuleSlotRef("net"), lambda v: v))))

    def test_undeclared_op_refused(self):
        registration_error(make_rule(expression=RuleExprOp(
            "POW", (RuleSlotRef("net"), RuleSlotRef("net")))))

    def test_div_arity_must_be_exactly_two(self):
        registration_error(make_rule(expression=RuleExprOp(
            "DIV", (RuleSlotRef("net"),))))

    def test_add_arity_needs_two(self):
        registration_error(make_rule(expression=RuleExprOp(
            "ADD", (RuleSlotRef("net"),))))

    def test_unused_declared_slot_refused(self):
        registration_error(make_rule(inputs=(
            RuleInput(slot_name="target", field_name="total.gross",
                      origin="derived"),
            RuleInput(slot_name="net", field_name="total.net", origin="normalized"),
            RuleInput(slot_name="tax", field_name="tax.amount",
                      origin="normalized"),
        )))                                         # tax declared but never compared

    def test_comparison_requires_target_slot(self):
        registration_error(make_rule(target_slot=None))

    def test_target_slot_must_be_declared(self):
        registration_error(make_rule(target_slot="ghost"))

    def test_presence_must_not_carry_expression_or_target(self):
        registration_error(make_rule(rule_type="presence", target_slot="target"))
        registration_error(make_rule(rule_type="presence",
                                     expression=RuleSlotRef("net")))

    def test_tolerance_must_be_injected_and_canonical_non_negative(self):
        registration_error(make_rule(rule_kind="R2",
                                     rule_type="tolerated-equality"))
        for bad in ["", "abc", "-0.01", "1e-3", ".5", "0.1.0"]:
            registration_error(make_rule(rule_kind="R2",
                                         rule_type="tolerated-equality",
                                         tolerance=bad))
        registers_cleanly(make_rule(rule_kind="R2", rule_type="tolerated-equality",
                                    tolerance="0"))   # zero tolerance is declarable

    def test_rounded_requires_injected_precision_and_whitelisted_mode(self):
        registration_error(make_rule(rule_kind="R2",
                                     rule_type="rounded-equality"))
        for bad_precision in [-1, "2", 2.0, True]:
            registration_error(make_rule(rule_kind="R2",
                                         rule_type="rounded-equality",
                                         rounding_precision=bad_precision,
                                         rounding_mode="HALF_UP"))
        for bad_mode in ["HALF_DOWN", "ROUND_UP", "half_up", ""]:
            registration_error(make_rule(rule_kind="R2",
                                         rule_type="rounded-equality",
                                         rounding_precision=2,
                                         rounding_mode=bad_mode))

    def test_tolerance_and_rounding_are_mutually_exclusive(self):
        registration_error(make_rule(rule_kind="R2", rule_type="tolerated-equality",
                                     tolerance="0.01", rounding_precision=2,
                                     rounding_mode="HALF_UP"))

    def test_div_inside_r2_rule_registers(self):
        """DIV is declarable inside R2 expressions (the rounded type is its only
        exact consumer); the engine's handling is behavior-tested separately."""
        registers_cleanly(quotient_rule())


class TestFingerprintAndVersions:
    def test_same_declaration_same_fingerprint(self):
        s1 = S1Service()
        assert rule_fingerprint(make_rule(), s1) == rule_fingerprint(make_rule(), s1)

    def test_fingerprint_is_sha256_v1(self):
        fp, algorithm = rule_fingerprint(make_rule(), S1Service())
        assert algorithm == "sha256-v1" and len(fp) == 64

    def test_fingerprint_sensitivity(self):
        s1 = S1Service()
        base = rule_fingerprint(make_rule(), s1)[0]
        assert rule_fingerprint(make_rule(rule_version="2"), s1)[0] != base
        assert rule_fingerprint(make_rule(expression=RuleExprOp(
            "ADD", (RuleSlotRef("net"), RuleSlotRef("net")))), s1)[0] != base
        assert rule_fingerprint(make_rule(rule_kind="R2",
                                          rule_type="tolerated-equality",
                                          tolerance="0.01"), s1)[0] != base
        assert rule_fingerprint(make_rule(rule_kind="R2",
                                          rule_type="tolerated-equality",
                                          tolerance="0.02"), s1)[0] != base
        assert rule_fingerprint(make_rule(rule_kind="R2",
                                          rule_type="rounded-equality",
                                          rounding_precision=3,
                                          rounding_mode="HALF_UP"), s1)[0] != base

    def test_canonical_bytes_deterministic_and_sensitive(self):
        assert canonical_rule_bytes(make_rule()) == canonical_rule_bytes(make_rule())
        assert canonical_rule_bytes(make_rule()) != \
            canonical_rule_bytes(make_rule(rule_id="test-rule-other"))

    def test_fingerprint_determinism_across_instances(self):
        s1 = S1Service()
        # registry-built fingerprints and direct fingerprints agree
        registry = ValidationRuleRegistry({("test-rule", "1"): make_rule()}, s1)
        assert registry.fingerprint_of("test-rule", "1") == \
            rule_fingerprint(make_rule(), s1)[0]

    def test_version_coexistence_in_registry(self):
        registry = ValidationRuleRegistry(
            {("test-rule", "1"): make_rule(),
             ("test-rule", "2"): make_rule(rule_version="2")}, S1Service())
        assert ("test-rule", "1") in registry and ("test-rule", "2") in registry
        assert registry.keys() == (("test-rule", "1"), ("test-rule", "2"))
        assert registry.fingerprint_of("test-rule", "1") != \
            registry.fingerprint_of("test-rule", "2")


class TestReferenceRegistry:
    def test_ships_exactly_four_declared_rules(self):
        registry = ValidationRuleRegistry(reference_rules(), S1Service())
        assert registry.keys() == (
            (R_CONSIST, "1"),
            (R_ROUNDED, "1"),
            (R_TOLERANCE, "1"),
            (R_PRESENT, "1"),
        )

    def test_r2_parameters_are_constructor_injected_not_hardcoded(self):
        """D-08: the reference factory cannot be called without its calibration
        parameters — no fixed value ships inside the engine."""
        with pytest.raises(TypeError):                 # parameters are REQUIRED
            ReferenceValidationRulesV1()
        with pytest.raises(TypeError):
            ReferenceValidationRulesV1(tolerance="0.01", precision=2)
        a = reference_rules(tolerance="0.01", precision=3, mode="HALF_EVEN")
        b = reference_rules(tolerance="0.02", precision=2, mode="HALF_UP")
        tol_a = a[(R_TOLERANCE, "1")]
        tol_b = b[(R_TOLERANCE, "1")]
        assert tol_a.tolerance == "0.01" and tol_b.tolerance == "0.02"
        assert tol_a.rounding_precision is None        # tolerated rule never rounds
        rounded_a = a[(R_ROUNDED, "1")]
        rounded_b = b[(R_ROUNDED, "1")]
        assert rounded_a.rounding_precision == 3
        assert rounded_a.rounding_mode == "HALF_EVEN"
        assert rounded_b.rounding_precision == 2
        assert rounded_b.rounding_mode == "HALF_UP"

    def test_declared_rule_shapes(self):
        rules = reference_rules()
        present = rules[(R_PRESENT, "1")]
        assert present.rule_kind == "R1" and present.rule_type == "presence"
        assert present.expression is None and present.target_slot is None
        consist = rules[(R_CONSIST, "1")]
        assert consist.rule_kind == "R1" \
            and consist.rule_type == "exact-consistency"
        assert consist.target_slot == "target"
        names = [(s.field_name, s.origin) for s in consist.inputs]
        assert ("total.gross", "derived") in names
        assert ("total.net", "normalized") in names
        assert ("tax.amount", "normalized") in names

    def test_probe_rules_register_cleanly(self):
        registry = ValidationRuleRegistry(
            {**(reference_rules()),
             (sub_expression_rule().rule_id, "1"): sub_expression_rule(),
             (presence_rule().rule_id, "1"): presence_rule(),
             (quotient_rule().rule_id, "1"): quotient_rule()}, S1Service())
        assert len(registry.keys()) == 7

    def test_version_two_of_reference_consistency_registers(self):
        registry = ValidationRuleRegistry(
            {**(reference_rules()),
             (swapped_rule().rule_id, swapped_rule().rule_version): swapped_rule()},
            S1Service())
        assert (R_CONSIST, "1") in registry and (R_CONSIST, "2") in registry
