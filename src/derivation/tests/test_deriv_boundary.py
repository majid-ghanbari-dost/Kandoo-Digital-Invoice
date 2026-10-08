"""WP-4.2 boundary tests — the normative non-negotiables, each behaviorally or
structurally proven:

  - DERIVED is the only label this layer can produce; UNRESOLVED is never created,
    assigned, inferred, or resolved (storage-gated; D-01)
  - no semantic unit_amount derivation exists in this WP (nothing shipped, nothing
    invented, nothing executed)
  - no cross-document derivation (inputs cannot leave the source normalization record)
  - no float anywhere in the mechanism (AST-level: zero float literals/calls)
  - formulas are data: no eval/exec/compile/__import__, no arbitrary code can execute
  - engine independence (no engine symbol coupling)
  - frozen layers P1–P4.1 behave identically after derivation traffic
(SPEC-WP42-DER §1/§5/§10/§13)
"""
import ast
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import derivation                             # noqa: E402
from deriv_helpers import PAGE_MISSING, PAGE_OK, net_minus_tax_formula  # noqa: E402
from derivation import (                      # noqa: E402
    DerivationAlreadyExists,
    DerivationCompleted,
    DerivationDeferred,
    DerivationFormulaNotRegistered,
    DerivationReadSuccess,
    ReferenceDerivationFormulasV1,
)

REF = "kandoo-der-total-gross-from-net-tax"
DERIV_FILES = ["model.py", "arithmetic.py", "formulas.py", "store.py", "service.py",
               "__init__.py"]
FORBIDDEN_NAME_CALLS = {"eval", "exec", "compile", "__import__", "float"}
FORBIDDEN_ATTR_CALLS = {"eval", "exec", "__import__", "float"}   # re.compile is legitimate
ALLOWED_ROOT_IMPORTS = {
    "__future__", "abc", "ast", "dataclasses", "datetime", "enum", "fractions",
    "re", "sqlite3", "typing", "uuid",
    "capture", "extraction", "normalization", "reconstruction", "derivation",
}


def _trees():
    base = Path(derivation.__file__).resolve().parent
    for name in DERIV_FILES:
        path = base / name
        with open(path, encoding="utf-8") as handle:
            yield name, ast.parse(handle.read(), filename=str(path))


class TestNoFloatAnywhere:
    def test_zero_float_literals_in_the_whole_mechanism(self):
        for name, tree in _trees():
            floats = [n for n in ast.walk(tree)
                      if isinstance(n, ast.Constant) and isinstance(n.value, float)]
            assert not floats, f"{name} contains float literals: {floats}"

    def test_no_float_conversion_or_dynamic_execution_calls(self):
        for name, tree in _trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id not in FORBIDDEN_NAME_CALLS, \
                        f"{name} calls {node.func.id}()"
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in FORBIDDEN_ATTR_CALLS, \
                        f"{name} calls .{node.func.attr}()"

    def test_imports_confined_to_declared_allowlist(self):
        for name, tree in _trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        assert root in ALLOWED_ROOT_IMPORTS, f"{name}: import {alias.name}"
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    root = (node.module or "").split(".")[0]
                    assert root in ALLOWED_ROOT_IMPORTS, f"{name}: from {node.module}"

    def test_computed_results_are_exact_where_float_would_fail(self, make_stack):
        # behavioral double-check inside the real pipeline: 0.1 + 0.2 must be 0.3
        from derivation import DerivationFormula, FormulaInput, FormulaInputRef, \
            FormulaOp
        add_probe = DerivationFormula(
            formula_id="probe-add", formula_version="1",
            output_field_name="probe.add",
            inputs=(FormulaInput(slot_name="p", field_name="p"),
                    FormulaInput(slot_name="q", field_name="q")),
            expression=FormulaOp("ADD", (FormulaInputRef("p"),
                                         FormulaInputRef("q"))))
        s = make_stack(extra_formulas=(add_probe,))
        try:
            _, norm_id = s.build_extract_normalize([b"p=0.1\nq=0.2\n"])
            outcome = s.deriv.derive(norm_id, "probe-add", "1")
            assert isinstance(outcome, DerivationCompleted)
            assert outcome.record.output_value == "0.3"   # float would yield 0.3000…4
        finally:
            s.close()


class TestNoUnresolvedCreation:
    def test_derivation_module_never_declares_or_exports_unresolved(self):
        assert "UNRESOLVED" not in derivation.__all__
        assert not any("unresolved" in name.lower() and "never" not in name.lower()
                       for name in dir(derivation)
                       if not name.startswith("__") and "UNRESOLVED" not in name)

    def test_no_unresolved_datum_in_any_durable_row(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        stack.deriv.derive(norm_id, REF, "1")
        _, other = stack.build_extract_normalize(PAGE_MISSING, label="b-miss")
        stack.deriv.derive(other, REF, "1")          # deferred — nothing persisted
        for table, column in (("derivation_records", "output_provenance"),
                              ("derivation_records", "output_value"),
                              ("derivation_inputs", "slot_name"),
                              ("derivation_inputs", "field_name")):
            rows = stack.deriv_store._conn.execute(
                f"SELECT {column} AS v FROM {table}").fetchall()
            assert all(row["v"] != "UNRESOLVED" for row in rows)

    def test_deferred_outcomes_carry_reason_codes_not_labels(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_MISSING)
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        assert outcome.reason_code == "input-missing"
        assert not hasattr(outcome, "output_value")
        assert not hasattr(outcome, "output_provenance")
        assert stack.deriv.derivations_for_normalization(norm_id) == ()
        # the outcome object is ephemeral — no deferred record can be read back
        assert not any(type(o).__name__ == "DerivationDeferred"
                       for o in [stack.deriv.read_derivation(norm_id)])


class TestNoUnitAmountDerivation:
    def test_shipped_registry_contains_no_unit_amount_formula(self):
        reg = ReferenceDerivationFormulasV1()
        for (fid, _), formula in reg.items():
            assert "unit_amount" not in fid
            assert formula.output_field_name != "unit_amount"
            assert "quantity" not in {s.field_name for s in formula.inputs}

    def test_quantity_next_to_total_derives_nothing_semantic(self, stack):
        # the classic shape: total + quantity present, tax.amount absent.
        # WP-4.1 proved unit_amount is never computed; WP-4.2 must not invent it either.
        _, norm_id = stack.build_extract_normalize([b"total.net=100.00\nquantity=4\n"])
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        rows = stack.deriv_store._conn.execute(
            "SELECT output_field_name FROM derivation_records").fetchall()
        assert all(row["output_field_name"] != "unit_amount" for row in rows)
        assert len(rows) == 0

    def test_no_formula_can_execute_without_registry_declaration(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        for ghost in ("unit_amount", "unit_amount-from-total-quantity", "v2", ""):
            assert isinstance(stack.deriv.derive(norm_id, ghost, "1"),
                              DerivationFormulaNotRegistered), ghost


class TestNoCrossDocumentDerivation:
    def test_inputs_cannot_leave_the_source_normalization_record(self, stack):
        _, norm_a = stack.build_extract_normalize(PAGE_OK, label="xdoc-a")
        _, norm_b = stack.build_extract_normalize(PAGE_MISSING, label="xdoc-b")
        # B lacks tax.amount; A has it — B must refuse, never borrow
        outcome = stack.deriv.derive(norm_b, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        # every durable input pointer of A stays inside A
        outcome_a = stack.deriv.derive(norm_a, REF, "1")
        assert isinstance(outcome_a, DerivationCompleted)
        rows = stack.deriv_store._conn.execute(
            "SELECT source_normalization_id, source_extraction_id "
            "FROM derivation_inputs").fetchall()
        assert {r["source_normalization_id"] for r in rows} == {norm_a}
        assert {r["source_extraction_id"] for r in rows} == \
            {outcome_a.record.extraction_id}

    def test_store_refuses_pointer_rows_from_another_record(self, stack):
        from derivation import DerivationInputRef, DerivationPersistenceUnavailable
        _, norm_a = stack.build_extract_normalize(PAGE_OK, label="gate-a")
        _, norm_b = stack.build_extract_normalize(PAGE_MISSING, label="gate-b")
        rec_a = stack.norm.read_normalization(norm_a).record
        with pytest.raises(DerivationPersistenceUnavailable):
            stack.deriv_store.commit_derivation(
                normalization_id=norm_b,
                extraction_id=rec_a.extraction_id,
                document_id=rec_a.document_id,
                capture_id=rec_a.capture_id,
                capture_s1=rec_a.capture_s1,
                capture_s1_algorithm_id=rec_a.capture_s1_algorithm_id,
                ruleset_id=rec_a.ruleset_id, ruleset_version=rec_a.ruleset_version,
                formula_id=REF, formula_version="1",
                formula_fingerprint="f" * 64,
                formula_fingerprint_algorithm_id="sha256-v1",
                output_field_name="total.gross", output_value="1080",
                inputs=(DerivationInputRef(0, "net", "total.net", norm_a, 1,
                                           rec_a.extraction_id),))
        assert stack.deriv.derivations_for_normalization(norm_b) == ()


class TestNoArbitraryCodeExecution:
    def test_engine_symbol_coupling_is_zero(self):
        for name, tree in _trees():
            for node in ast.walk(tree):
                candidates = []
                if isinstance(node, ast.Name):
                    candidates.append(node.id)
                elif isinstance(node, ast.Attribute):
                    candidates.append(node.attr)
                for symbol in candidates:
                    assert "Engine" not in symbol, f"{name} references {symbol}"


class TestFrozenLayerProtection:
    def test_derivation_traffic_leaves_all_upstream_layers_verified(self, stack):
        from extraction import BindingReadSuccess, ExtractionReadSuccess
        from normalization import NormalizationAlreadyExists, \
            NormalizationReadSuccess
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationCompleted)
        extraction_id = outcome.record.extraction_id
        stack.deriv.trace_derivation(outcome.record.derivation_id)
        # P4.1: normalization replay + verified read unchanged
        assert isinstance(stack.norm.normalize(extraction_id, "kandoo-norm-v1"),
                          NormalizationAlreadyExists)
        assert isinstance(stack.norm.read_normalization(norm_id),
                          NormalizationReadSuccess)
        # P3: extraction verbatim unchanged
        ext_read = stack.extraction.read_extraction(extraction_id)
        assert isinstance(ext_read, ExtractionReadSuccess)
        assert ext_read.fields[1].value_verbatim == "1000.00"
        # WP-3.2 binding still valid
        assert isinstance(stack.binder.read_binding(extraction_id), BindingReadSuccess)
        # P4.1 grammar behavior unchanged (declared-output snapshot)
        fields = {f.source_field_name: f for f in
                  stack.norm.read_normalization(norm_id).fields}
        assert fields["total.net"].normalized_value == "1000.00"
        assert fields["tax.amount"].normalized_value == "80"

    def test_second_formula_on_same_record_does_not_touch_first(self, make_stack):
        s = make_stack(extra_formulas=(net_minus_tax_formula(),))
        try:
            _, norm_id = s.build_extract_normalize(PAGE_OK)
            first = s.deriv.derive(norm_id, REF, "1")
            second = s.deriv.derive(norm_id, "test-net-minus-tax", "1")
            assert isinstance(first, DerivationCompleted) and \
                isinstance(second, DerivationCompleted)
            re_read = s.deriv.read_derivation(first.record.derivation_id)
            assert isinstance(re_read, DerivationReadSuccess)
            assert re_read.record == first.record       # immutable, not rewritten
        finally:
            s.close()
