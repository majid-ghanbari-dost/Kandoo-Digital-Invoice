"""WP-4.2 derivation-service tests — happy path, INV-D-1:1 replay, version-keyed
distinct derivations, the full DEFERRED refusal matrix, fail-closed source handling,
engine independence (SPEC-WP42-DER §5/§8)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from deriv_helpers import (                    # noqa: E402
    PAGE_AMBIGUOUS,
    PAGE_DEFERRED_INPUT,
    PAGE_EU,
    PAGE_MISSING,
    PAGE_OK,
    PAGE_OK_ALT,
    PAGE_OUTPUT_PRESENT,
    PAGE_REJECTED_INPUT,
    PAGE_TEXTY,
    PAGE_TEXTY_RULESET,
    doubled_formula,
    net_minus_tax_formula,
    quotient_formula,
)
from derivation import (                       # noqa: E402
    DerivationAlreadyExists,
    DerivationCompleted,
    DerivationDeferred,
    DerivationFormulaNotRegistered,
    DerivationSourceRefused,
    OUTPUT_PROVENANCE_DERIVED,
    REASON_INPUT_AMBIGUOUS,
    REASON_INPUT_MISSING,
    REASON_NON_EXACT_RESULT,
    REASON_OUTPUT_PRESENT,
    ReferenceDerivationFormulasV1,
)

REF = "kandoo-der-total-gross-from-net-tax"


class TestHappyPath:
    def test_successful_exact_derivation_mvp_example(self, stack):
        outcome, _ = stack.derive_ok(PAGE_OK)
        rec = outcome.record
        assert rec.output_provenance == OUTPUT_PROVENANCE_DERIVED == "DERIVED"
        assert rec.output_field_name == "total.gross"
        assert rec.output_value == "1080"          # 1000.00 + 80, exact minimal expansion
        assert rec.formula_id == REF and rec.formula_version == "1"
        assert rec.input_count == 2 and len(outcome.inputs) == 2
        assert rec.normalization_id and rec.extraction_id and rec.document_id
        assert rec.capture_s1 and rec.capture_s1_algorithm_id == "sha256-v1"
        assert rec.record_fingerprint and rec.fingerprint_algorithm_id == "sha256-v1"

    def test_derived_value_differs_from_any_read_field_value_relayed(self, stack):
        # the output must be computed, not copied: no input carries "1080"
        outcome, _ = stack.derive_ok(PAGE_OK)
        assert outcome.record.output_value == "1080"
        assert {ref.field_name for ref in outcome.inputs} == {"total.net", "tax.amount"}

    def test_european_grouping_inputs_derive_exactly(self, stack):
        outcome, _ = stack.derive_ok(PAGE_EU)       # 1234.56 + 196,80
        assert outcome.record.output_value == "1431.36"

    def test_input_pointers_target_the_exact_normalized_fields(self, stack):
        outcome, _ = stack.derive_ok(PAGE_OK)
        by_name = {ref.field_name: ref for ref in outcome.inputs}
        assert by_name["total.net"].slot_name == "net"
        assert by_name["total.net"].input_slot == 0
        assert by_name["tax.amount"].slot_name == "tax"
        assert by_name["tax.amount"].input_slot == 1
        assert {ref.field_seq for ref in outcome.inputs} == {1, 2}   # invoice.number is seq 0
        assert all(ref.source_normalization_id == outcome.record.normalization_id
                   for ref in outcome.inputs)

    def test_formula_fingerprint_from_registry_is_stored(self, stack):
        outcome, _ = stack.derive_ok(PAGE_OK)
        expected = stack.registry.fingerprint_of(REF, "1")
        assert outcome.record.formula_fingerprint == expected
        assert outcome.record.formula_fingerprint_algorithm_id == "sha256-v1"


class TestIdempotency:
    def test_replay_is_explicit_alreadyexists_never_second_record(self, stack):
        first, norm_id = stack.derive_ok(PAGE_OK)
        replay = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(replay, DerivationAlreadyExists)
        assert replay.derivation_id == first.record.derivation_id
        assert stack.deriv.derivations_for_normalization(norm_id) == \
            (first.record.derivation_id,)

    def test_different_formula_version_is_a_distinct_derivation(self, make_stack):
        s = make_stack(extra_formulas=(doubled_formula(),))
        try:
            first, norm_id = s.derive_ok(PAGE_OK)                       # v1
            second = s.deriv.derive(norm_id, REF, "2")                  # v2
            assert isinstance(second, DerivationCompleted)
            assert second.record.derivation_id != first.record.derivation_id
            assert second.record.formula_version == "2"
            assert second.record.output_value == first.record.output_value
            assert len(s.deriv.derivations_for_normalization(norm_id)) == 2
        finally:
            s.close()

    def test_two_different_formulas_coexist(self, make_stack):
        s = make_stack(extra_formulas=(net_minus_tax_formula(),))
        try:
            _, norm_id = s.build_extract_normalize(PAGE_OK)   # total.net + tax.amount
            d1 = s.deriv.derive(norm_id, REF, "1")
            d2 = s.deriv.derive(norm_id, "test-net-minus-tax", "1")
            assert isinstance(d1, DerivationCompleted) and isinstance(d2, DerivationCompleted)
            assert d1.record.derivation_id != d2.record.derivation_id
            assert d1.record.output_value == "1080"           # ADD
            assert d2.record.output_value == "920"            # SUB — same inputs
        finally:
            s.close()


class TestDeferredRefusals:
    def test_missing_input_is_explicit_and_persists_nothing(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_MISSING)
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        assert outcome.reason_code == REASON_INPUT_MISSING
        assert "tax.amount" in outcome.detail
        assert stack.deriv.derivations_for_normalization(norm_id) == ()

    def test_ambiguous_input_is_refused_no_association_decision(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_AMBIGUOUS)
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        assert outcome.reason_code == REASON_INPUT_AMBIGUOUS
        assert "Canonicalization Gate" in outcome.detail
        assert stack.deriv.derivations_for_normalization(norm_id) == ()

    def test_deferred_normalized_input_never_feeds_arithmetic(self, stack):
        # tax.amount=12,3 → DEFERRED by WP-4.1 grammar — the slot must refuse, not guess
        _, norm_id = stack.build_extract_normalize(PAGE_DEFERRED_INPUT)
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        assert outcome.reason_code == REASON_INPUT_MISSING
        assert "never feeds arithmetic" in outcome.detail
        assert stack.deriv.derivations_for_normalization(norm_id) == ()

    def test_rejected_input_never_feeds_arithmetic(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_REJECTED_INPUT)
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        assert outcome.reason_code == REASON_INPUT_MISSING

    def test_text_kind_value_is_refused_never_parsed_leniently(self, make_stack):
        # a ruleset that normalizes total.net as TEXT keeps "1,234.56" verbatim →
        # NORMALIZED but outside the canonical decimal grammar → defensive refusal
        from normalization import ReferenceNormalizationRulesV1
        s = make_stack(norm_rulesets={
            "kandoo-norm-v1": ReferenceNormalizationRulesV1(),
            "norm-texty-v1": ReferenceNormalizationRulesV1(
                ruleset_id="norm-texty-v1",
                kind_profile={"total.net": "text", "tax.amount": "text"}),
        })
        try:
            _, norm_id = s.build_extract_normalize(PAGE_TEXTY_RULESET,
                                                   ruleset_id="norm-texty-v1")
            read = s.norm.read_normalization(norm_id)
            field = next(f for f in read.fields if f.source_field_name == "total.net")
            assert field.status.value == "NORMALIZED"          # text kind → NORMALIZED
            assert field.normalized_value == "1,234.56"        # non-canonical decimal
            outcome = s.deriv.derive(norm_id,
                                     "kandoo-der-total-gross-from-net-tax", "1")
            assert isinstance(outcome, DerivationDeferred)
            assert outcome.reason_code == REASON_INPUT_MISSING
            assert "canonical decimal grammar" in outcome.detail
            assert s.deriv.derivations_for_normalization(norm_id) == ()
        finally:
            s.close()

    def test_output_present_gate_refuses_shadowing(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OUTPUT_PRESENT)
        outcome = stack.deriv.derive(norm_id, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        assert outcome.reason_code == REASON_OUTPUT_PRESENT
        assert stack.deriv.derivations_for_normalization(norm_id) == ()

    def test_non_exact_division_is_deferred_never_rounded(self, make_stack):
        s = make_stack(extra_formulas=(quotient_formula(),))
        try:
            _, norm_id = s.build_extract_normalize([b"a=100.0\nb=3\n"])   # 33.3̄
            outcome = s.deriv.derive(norm_id, "test-neutral-quotient", "1")
            assert isinstance(outcome, DerivationDeferred)
            assert outcome.reason_code == REASON_NON_EXACT_RESULT
            assert s.deriv.derivations_for_normalization(norm_id) == ()
        finally:
            s.close()

    def test_exact_division_executes_and_is_exact(self, make_stack):
        s = make_stack(extra_formulas=(quotient_formula(),))
        try:
            _, norm_id = s.build_extract_normalize([b"a=100.0\nb=4\n"])
            outcome = s.deriv.derive(norm_id, "test-neutral-quotient", "1")
            assert isinstance(outcome, DerivationCompleted)
            assert outcome.record.output_value == "25"
        finally:
            s.close()

    def test_deferred_outcome_leaves_source_records_untouched(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_MISSING)
        before = stack.norm.read_normalization(norm_id)
        stack.deriv.derive(norm_id, REF, "1")
        after = stack.norm.read_normalization(norm_id)
        assert isinstance(after, type(before))
        assert [(f.field_seq, f.status.value, f.normalized_value)
                for f in after.fields] == \
            [(f.field_seq, f.status.value, f.normalized_value) for f in before.fields]


class TestFormulaRegistration:
    def test_unregistered_formula_is_explicit_and_persists_nothing(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        outcome = stack.deriv.derive(norm_id, "no-such-formula", "1")
        assert isinstance(outcome, DerivationFormulaNotRegistered)
        assert outcome.formula_id == "no-such-formula"
        assert stack.deriv.derivations_for_normalization(norm_id) == ()

    def test_unregistered_version_is_explicit(self, stack):
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        outcome = stack.deriv.derive(norm_id, REF, "99")
        assert isinstance(outcome, DerivationFormulaNotRegistered)
        assert outcome.formula_version == "99"

    def test_pipeline_cannot_derive_without_a_declared_formula(self, stack):
        # nothing in the mechanism invents formulas: only registry declarations execute
        _, norm_id = stack.build_extract_normalize(PAGE_OK)
        for ghost in ("unit_amount", "unit-amount", "kandoo-der-unit-amount"):
            outcome = stack.deriv.derive(norm_id, ghost, "1")
            assert isinstance(outcome, DerivationFormulaNotRegistered), ghost


class TestSourceHandling:
    def test_unknown_normalization_is_refused(self, stack):
        outcome = stack.deriv.derive("ghost-normalization-id", REF, "1")
        assert isinstance(outcome, DerivationSourceRefused)
        assert outcome.normalization_id is None or outcome.detail

    def test_unbound_extraction_is_refused_fail_closed(self, make_stack):
        from extraction import ExtractionCompleted
        s = make_stack()
        try:
            document_id = s.build_document(PAGE_OK)
            done = s.extraction.extract(document_id, "reference-delimited-v1")
            assert isinstance(done, ExtractionCompleted)
            # NO binder.bind_extraction here — no evidence binding exists
            normed = s.norm.normalize(done.extraction.extraction_id, "kandoo-norm-v1")
            from normalization import NormalizationCompleted
            assert isinstance(normed, NormalizationCompleted)
            outcome = s.deriv.derive(normed.record.normalization_id, REF, "1")
            assert isinstance(outcome, DerivationSourceRefused)
            assert "binding" in outcome.detail
            assert s.deriv.derivations_for_normalization(
                normed.record.normalization_id) == ()
        finally:
            s.close()

    def test_input_resolution_never_crosses_normalization_records(self, stack):
        # doc B holds total.net but no tax.amount; doc A holds both. Deriving on B must
        # refuse input-missing — it must NEVER borrow the sibling record's field.
        _, norm_a = stack.build_extract_normalize(PAGE_OK)
        _, norm_b = stack.build_extract_normalize(PAGE_MISSING, label="deriv-doc-b")
        assert norm_a != norm_b
        outcome = stack.deriv.derive(norm_b, REF, "1")
        assert isinstance(outcome, DerivationDeferred)
        assert outcome.reason_code == REASON_INPUT_MISSING
        # ...and A is unaffected
        assert isinstance(stack.deriv.derive(norm_a, REF, "1"), DerivationCompleted)


class TestEngineIndependence:
    def test_identical_inputs_derive_identically_from_any_engine(self, stack):
        # PAGE_OK_ALT has different bytes (D-03: distinct capture) but identical
        # NORMALIZED content — the derivation must be engine/content-scoped only
        _, norm_ref = stack.build_extract_normalize(
            PAGE_OK, engine_id="reference-delimited-v1", label="engine-ref")
        _, norm_alt = stack.build_extract_normalize(
            PAGE_OK_ALT, engine_id="alt-der-engine-v1", label="engine-alt")
        d_ref = stack.deriv.derive(norm_ref, REF, "1")
        d_alt = stack.deriv.derive(norm_alt, REF, "1")
        assert isinstance(d_ref, DerivationCompleted) and isinstance(d_alt, DerivationCompleted)
        assert d_ref.record.output_value == d_alt.record.output_value == "1080"
        assert d_ref.record.derivation_id != d_alt.record.derivation_id
        assert d_ref.record.formula_fingerprint == d_alt.record.formula_fingerprint
        # the engine scalars are relayed, never interpreted
        assert d_ref.record.extraction_id != d_alt.record.extraction_id
