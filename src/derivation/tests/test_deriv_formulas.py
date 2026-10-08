"""WP-4.2 formula-registry tests — declarative data (never code), fail-closed
validation, deterministic fingerprints, version coexistence, shipped-registry content
(SPEC-WP42-DER §3)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1Service                                 # noqa: E402
from derivation.formulas import (                             # noqa: E402
    DerivationFormula,
    FormulaInput,
    FormulaInputRef,
    FormulaOp,
    canonical_formula_bytes,
    formula_fingerprint,
)
from derivation.model import DerivationFormulaError           # noqa: E402
from derivation import ReferenceDerivationFormulasV1          # noqa: E402

from deriv_helpers import doubled_formula, quotient_formula   # noqa: E402

S1 = S1Service()


def _ok_formula(**overrides):
    base = dict(
        formula_id="f.test", formula_version="1", output_field_name="out.field",
        inputs=(FormulaInput(slot_name="a", field_name="in.a"),
                FormulaInput(slot_name="b", field_name="in.b")),
        expression=FormulaOp("ADD", (FormulaInputRef("a"), FormulaInputRef("b"))),
    )
    base.update(overrides)
    return DerivationFormula(**base)


class TestDeclarationValidation:
    def test_well_formed_declaration_is_accepted(self):
        canonical_formula_bytes(_ok_formula())          # must not raise
        formula_fingerprint(_ok_formula(), S1)

    def test_non_declaration_payload_is_refused(self):
        class Fake:
            pass
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(Fake())

    def test_undeclared_op_is_refused_at_registration(self):
        bad = _ok_formula(expression=FormulaOp("POW", (FormulaInputRef("a"),
                                                      FormulaInputRef("b"))))
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(bad)

    def test_dangling_leaf_is_refused(self):
        bad = _ok_formula(expression=FormulaOp("ADD", (FormulaInputRef("a"),
                                                      FormulaInputRef("ghost"))))
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(bad)

    def test_unused_declared_slot_is_refused(self):
        bad = _ok_formula(expression=FormulaOp("ADD", (FormulaInputRef("a"),
                                                      FormulaInputRef("a"))))
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(bad)

    def test_div_arity_is_exactly_two(self):
        bad = _ok_formula(expression=FormulaOp("DIV", (FormulaInputRef("a"),
                                                      FormulaInputRef("b"),
                                                      FormulaInputRef("a"))))
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(bad)

    def test_low_arity_add_is_refused(self):
        bad = _ok_formula(expression=FormulaOp("ADD", (FormulaInputRef("a"),)))
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(bad)

    def test_shadowing_output_name_is_refused_by_construction(self):
        bad = _ok_formula(output_field_name="in.a")     # output == an input field
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(bad)

    def test_literal_or_callable_leaves_are_refused_no_code_can_enter(self):
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(_ok_formula(
                expression=FormulaOp("ADD", (FormulaInputRef("a"), 42))))
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(_ok_formula(
                expression=FormulaOp("ADD", (FormulaInputRef("a"), lambda v: v))))
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(_ok_formula(
                expression=FormulaOp("ADD", (FormulaInputRef("a"), "b"))))

    def test_duplicate_slot_names_and_empty_names_are_refused(self):
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(_ok_formula(
                inputs=(FormulaInput(slot_name="a", field_name="in.a"),
                        FormulaInput(slot_name="a", field_name="in.b"))))
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(_ok_formula(
                inputs=(FormulaInput(slot_name="a", field_name=""),)))

    def test_non_formula_object_is_refused(self):
        with pytest.raises(DerivationFormulaError):
            canonical_formula_bytes(object())


class TestFingerprintDeterminism:
    def test_identical_declarations_have_identical_fingerprints(self):
        fp1, alg1 = formula_fingerprint(_ok_formula(), S1)
        fp2, alg2 = formula_fingerprint(_ok_formula(), S1)
        assert fp1 == fp2 and alg1 == alg2 == "sha256-v1"

    def test_any_declaration_change_changes_the_fingerprint(self):
        base, _ = formula_fingerprint(_ok_formula(), S1)
        variants = [
            _ok_formula(formula_version="2"),
            _ok_formula(output_field_name="out.other"),
            _ok_formula(inputs=(FormulaInput(slot_name="a", field_name="in.x"),
                                FormulaInput(slot_name="b", field_name="in.b"))),
            _ok_formula(expression=FormulaOp("ADD", (FormulaInputRef("b"),
                                                     FormulaInputRef("a")))),
        ]
        for variant in variants:
            fp, _ = formula_fingerprint(variant, S1)
            assert fp != base

    def test_canonical_bytes_are_pure(self):
        f = _ok_formula()
        assert canonical_formula_bytes(f) == canonical_formula_bytes(f)


class TestRegistry:
    def test_versions_of_one_formula_coexist_as_distinct_keys(self):
        from derivation import DerivationFormulaRegistry
        reg = DerivationFormulaRegistry(
            {("f.test", "1"): _ok_formula(), ("f.test", "2"): _ok_formula(
                formula_version="2")}, S1)
        assert ("f.test", "1") in reg and ("f.test", "2") in reg
        assert len(reg.keys()) == 2

    def test_registry_refuses_key_declaration_mismatch(self):
        from derivation import DerivationFormulaRegistry
        with pytest.raises(DerivationFormulaError):
            DerivationFormulaRegistry({("f.other", "1"): _ok_formula()}, S1)

    def test_registry_refuses_malformed_declarations(self):
        from derivation import DerivationFormulaRegistry
        with pytest.raises(DerivationFormulaError):
            DerivationFormulaRegistry(
                {("f.bad", "1"): _ok_formula(expression=FormulaOp(
                    "ADD", (FormulaInputRef("a"), 42)))}, S1)


class TestReferenceRegistryContent:
    def test_ships_exactly_the_declared_mvp_formula(self):
        reg = ReferenceDerivationFormulasV1()
        assert set(reg) == {("kandoo-der-total-gross-from-net-tax", "1")}
        f = reg[("kandoo-der-total-gross-from-net-tax", "1")]
        assert f.output_field_name == "total.gross"
        assert {slot.field_name for slot in f.inputs} == {"total.net", "tax.amount"}

    def test_no_unit_amount_formula_is_shipped(self):
        reg = ReferenceDerivationFormulasV1()
        for _, formula in reg.items():
            assert "unit" not in formula.formula_id
            assert formula.output_field_name != "unit_amount"
            assert formula.output_field_name != "unit_amount" \
                and "quantity" not in {s.field_name for s in formula.inputs}
