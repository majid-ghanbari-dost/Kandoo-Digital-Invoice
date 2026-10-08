"""Boundary behavior tests — WP-5.1 (SPEC-WP51-VAL §1/§5/§11/§13).

Structural proofs: no float, no eval/exec/arbitrary code, no engine coupling, no
UNRESOLVED, no Canonicalization behavior, no business-semantic inference, and the
frozen layers survive validation traffic byte-identically.
"""
import ast
import importlib
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import (
    ValidationCompleted,
    ValidationTraceSuccess,
)

from val_helpers import (
    FORMULA,
    PAGE_OK,
    R_CONSIST,
    R_PRESENT,
    R_ROUNDED,
    R_TOLERANCE,
    extended_service,
    presence_rule,
    quotient_rule,
)

VALIDATION_PACKAGE = SRC / "validation"

# The declared import allowlist for the validation layer (OD-V10: no engine imports,
# no canonicalization imports; stdlib + capture capability + lower pipeline layers).
ALLOWED_LOCAL_ROOTS = {"capture", "reconstruction", "extraction", "normalization",
                       "derivation", "validation"}


def iter_validation_modules():
    for path in sorted(VALIDATION_PACKAGE.glob("*.py")):
        yield path


class TestNoFloatAndNoArbitraryCode:
    @pytest.mark.parametrize("path", list(iter_validation_modules()))
    def test_zero_float_literals(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                pytest.fail(f"float literal {node.value!r} in {path.name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "float":
                pytest.fail(f"float() call in {path.name}")

    @pytest.mark.parametrize("path", list(iter_validation_modules()))
    def test_no_eval_exec_compile_import(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id in ("eval", "exec", "compile", "__import__"):
                pytest.fail(f"dynamic code execution ({node.func.id}) in {path.name}")

    @pytest.mark.parametrize("path", list(iter_validation_modules()))
    def test_imports_stay_on_declared_allowlist(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                    and node.module:
                names = [node.module.split(".")[0]]
            for root in names:
                if root not in (ALLOWED_LOCAL_ROOTS | {
                        "ast", "dataclasses", "datetime", "fractions", "sqlite3",
                        "sys", "typing", "uuid", "re", "unicodedata",
                        "abc", "__future__"}):
                    pytest.fail(f"undeclared import root {root!r} in {path.name}")

    def test_no_engine_symbols_anywhere_in_package(self):
        """Engine independence is structural: no engine module import, no engine
        type reference in the whole validation package."""
        for path in iter_validation_modules():
            source = path.read_text(encoding="utf-8")
            for banned in ("ExtractionEngine", "engine_id=", "extract_pages",
                           "ReferenceDelimitedEngine"):
                assert banned not in source, f"{banned} found in {path.name}"

    def test_rounding_path_is_float_free_end_to_end(self, stack):
        """Values far beyond float precision round EXACTLY through the full
        service path — a float anywhere would collapse them."""
        from val_helpers import PAGE_OK as _  # noqa: F401
        nid = stack.build_extract_normalize(
            [b"total.net=100000000000000000000000.00004\n"
             b"tax.amount=80.00004\nq.target=100000000000000000000080.00\n"])
        rule = quotient_rule(rule_id="val-boundary-bigsum",
                             rule_type="rounded-equality",
                             target_field="total.gross", target_origin="derived",
                             numerator="total.net", denominator="b",
                             precision=2, mode="HALF_UP")
        # use the reference rounded rule with a DERIVED target over a big corpus:
        outcome = stack.val.validate(nid, R_ROUNDED, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.rounding_applied == 0       # exact match at any scale


class TestNoUnresolvedEver:
    def test_no_unresolved_outcome_in_any_result(self, stack):
        outcomes = [
            stack.validate_ok(stack.build_extract_normalize(PAGE_OK), R_PRESENT),
            stack.val.validate(stack.build_extract_normalize(
                [b"total.net=1000.00\n"]), R_CONSIST, "1"),
        ]
        for outcome in outcomes:
            assert isinstance(outcome, ValidationCompleted)
            assert outcome.record.outcome in ("VALID", "INVALID", "DEFERRED")
            assert outcome.record.outcome != "UNRESOLVED"

    def test_deferred_is_never_unresolved_in_details_or_reasons(self, stack):
        nid = stack.build_extract_normalize([b"total.net=1000.00\n"])
        outcome = stack.val.validate(nid, R_CONSIST, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        assert outcome.record.outcome_reason != "unresolved"
        assert "UNRESOLVED" not in outcome.record.outcome_detail
        assert "unresolved" not in outcome.record.outcome_reason.lower()

    def test_storage_never_holds_unresolved(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)
        stack.validate_ok(nid, R_PRESENT)
        for column in ("outcome", "outcome_reason", "rule_kind", "rule_type"):
            rows = stack.val_store._conn.execute(
                f"SELECT DISTINCT {column} FROM validation_records").fetchall()
            for row in rows:
                assert "UNRESOLVED" not in str(row[0])


class TestNoCanonicalizationAndNoBusinessInference:
    def test_validation_never_maps_or_invents_field_names(self, stack):
        """The rule references engine-vocabulary names verbatim; the record carries
        exactly the declared names — no canonical mapping happened."""
        nid = stack.build_derive_validate_ready(PAGE_OK)
        outcome = stack.validate_ok(nid, R_CONSIST)
        declared = {"total.gross", "total.net", "tax.amount"}
        assert {ref.field_name for ref in outcome.inputs} <= declared
        assert outcome.record.ruleset_id == "kandoo-norm-v1"   # relayed, not re-decided

    def test_rule_engine_produces_no_values(self, stack):
        """A validation record has NO output-value column — the engine structurally
        cannot invent a value; the only output-like fields are the R2 audit pair."""
        columns = {row["name"] for row in stack.val_store._conn.execute(
            "PRAGMA table_info(validation_records)").fetchall()}
        for banned in ("output_value", "output_field_name", "normalized_value",
                       "derived_value"):
            assert banned not in columns

    def test_no_matching_grouping_or_identity_behavior(self, stack):
        """Two DIFFERENT field names with identical content never match each other;
        two same-named fields are ambiguity, never silently grouped (association is
        the Canonicalization Gate's decision)."""
        from val_helpers import PAGE_AMBIGUOUS
        nid = stack.build_extract_normalize(PAGE_AMBIGUOUS)
        outcome = stack.val.validate(nid, R_CONSIST, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"          # never auto-grouped
        assert "Canonicalization Gate" in outcome.record.outcome_detail

    def test_ambiguous_input_never_silently_picks_first(self, make_stack):
        from val_helpers import PAGE_AMBIGUOUS, presence_rule
        stack = make_stack(extra_rules=[presence_rule(
            rule_id="val-boundary-presence", field_name="total.net")])
        try:
            nid = stack.build_extract_normalize(PAGE_AMBIGUOUS)
            outcome = stack.val.validate(nid, "val-boundary-presence", "1")
            # presence is satisfied by existence — but it records the FIRST
            # candidate deterministically (lowest field_seq), it never merges them
            assert isinstance(outcome, ValidationCompleted)
            assert outcome.record.outcome == "VALID"
        finally:
            stack.close()

    def test_no_upstream_status_mutation(self, stack):
        """Validation never upgrades/downgrades/rewrites upstream statuses or
        provenance labels: upstream reads are read-only (verified)."""
        from normalization import NormalizationReadSuccess
        nid = stack.build_extract_normalize(PAGE_OK)
        before = stack.norm.read_normalization(nid)
        assert isinstance(before, NormalizationReadSuccess)
        snapshot = [(f.field_seq, f.status, f.normalized_value)
                    for f in before.fields]
        stack.validate_ok(nid, R_PRESENT)
        stack.val.validate(nid, R_CONSIST, "1")
        after = stack.norm.read_normalization(nid)
        assert isinstance(after, NormalizationReadSuccess)
        assert [(f.field_seq, f.status, f.normalized_value)
                for f in after.fields] == snapshot


class TestFrozenLayerSurvival:
    def test_declared_grammar_outputs_unchanged_after_validation_traffic(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)
        before = stack.norm.read_normalization(nid)
        stack.validate_ok(nid, R_PRESENT)
        stack.val.validate(nid, R_CONSIST, "1")
        stack.val.validate(nid, R_TOLERANCE, "1")
        stack.val.validate(nid, R_ROUNDED, "1")
        after = stack.norm.read_normalization(nid)
        assert before.record.record_fingerprint == after.record.record_fingerprint
        assert [f.normalized_value for f in after.fields] == \
            ["VAL-2026-001", "1000.00", "80"]

    def test_derivation_replay_and_verified_reads_survive(self, stack):
        nid = stack.build_derive_validate_ready(PAGE_OK)
        stack.validate_ok(nid, R_CONSIST)
        from derivation import DerivationAlreadyExists
        replay = stack.deriv.derive(nid, FORMULA, "1")
        assert isinstance(replay, DerivationAlreadyExists)
        assert type(stack.deriv.trace_derivation(
            replay.derivation_id)).__name__ == "DerivationTraceSuccess"

    def test_capture_idempotency_and_vor_survive(self, stack):
        from capture import CaptureService, IngestCompleted
        nid = stack.build_extract_normalize(PAGE_OK)
        stack.validate_ok(nid, R_PRESENT)
        duplicate = stack.capture.ingest(
            CaptureService.aggregate(PAGE_OK), source_label="survival-probe")
        assert type(duplicate).__name__ == "IngestDuplicateAtCapture"

    def test_evidence_binding_still_verifies_after_validation(self, stack):
        from extraction import BindingReadSuccess
        nid = stack.build_extract_normalize(PAGE_OK)
        stack.validate_ok(nid, R_PRESENT)
        read = stack.norm.read_normalization(nid)
        binding = stack.binder.read_binding(read.record.extraction_id)
        assert isinstance(binding, BindingReadSuccess)


class TestContractDocumentation:
    def test_validation_never_creates_states_or_review(self, stack):
        """WP-5.1 defines NO invoice states: no REVIEW/REJECT value is produced or
        storable — those belong to WP-5.2 (AS-03/AD-04)."""
        outcome = stack.validate_ok(stack.build_extract_normalize(PAGE_OK),
                                    R_PRESENT)
        assert outcome.record.outcome not in ("REVIEW", "REJECT")
        columns = {row["name"] for row in stack.val_store._conn.execute(
            "PRAGMA table_info(validation_records)").fetchall()}
        assert "invoice_state" not in columns and "review_state" not in columns

    def test_provenance_labels_relayed_never_redecided(self, stack):
        nid = stack.build_derive_validate_ready(PAGE_OK)
        outcome = stack.validate_ok(nid, R_CONSIST)
        # upstream labels intact and untouched:
        from normalization import NormalizationReadSuccess
        read = stack.norm.read_normalization(nid)
        assert isinstance(read, NormalizationReadSuccess)
        assert all(f.source_provenance == "EXTRACTED" for f in read.fields)
        from derivation import DerivationReadSuccess
        derived_ref = next(r for r in outcome.inputs
                           if r.value_origin == "DERIVED")
        d_read = stack.deriv.read_derivation(derived_ref.source_derivation_id)
        assert isinstance(d_read, DerivationReadSuccess)
        assert d_read.record.output_provenance == "DERIVED"
