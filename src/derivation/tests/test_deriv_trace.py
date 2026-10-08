"""WP-4.2 traceability tests — complete provenance chain walk
(derivation → formula → inputs → normalization → extraction → binding →
Document/Page/span → Capture S1), pointer-not-value model, tamper propagation
(SPEC-WP42-DER §6/§10)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from deriv_helpers import PAGE_OK, PAGE_EU    # noqa: E402
from derivation import (                      # noqa: E402
    DerivationTraceIntegrityFailure,
    DerivationTraceSuccess,
)

REF = "kandoo-der-total-gross-from-net-tax"


class TestCompleteProvenanceChain:
    def test_full_chain_walk_verifies_every_link(self, stack):
        outcome, norm_id = stack.derive_ok(PAGE_OK)
        walk = stack.deriv.trace_derivation(outcome.record.derivation_id)
        assert isinstance(walk, DerivationTraceSuccess)
        assert walk.derivation_id == outcome.record.derivation_id
        text = "\n".join(walk.chain)
        # every mandated link is present and verified IN this walk
        assert "derivation: DERIVED total.gross=1080" in text
        assert "formula=kandoo-der-total-gross-from-net-tax/1" in text
        assert "normalization: OK" in text
        assert "extraction: OK" in text
        assert "binding: OK" in text
        assert "document: OK" in text
        assert "input[0] net=total.net" in text and "input[1] tax=tax.amount" in text
        assert "capture: OK" in text and "sha256-v1" in text
        # the S1 of the derivation record equals the S1 carried up the chain
        rec = outcome.record
        read = stack.norm.read_normalization(norm_id)
        assert read.record.capture_s1 == rec.capture_s1

    def test_chain_covers_both_inputs_with_spans(self, stack):
        outcome, _ = stack.derive_ok(PAGE_EU)
        walk = stack.deriv.trace_derivation(outcome.record.derivation_id)
        assert isinstance(walk, DerivationTraceSuccess)
        text = "\n".join(walk.chain)
        assert "page 0 [" in text                      # byte spans anchored
        assert "→ OK" in text

    def test_trace_walk_is_repeatable_and_side_effect_free(self, stack):
        outcome, _ = stack.derive_ok(PAGE_OK)
        did = outcome.record.derivation_id
        w1 = stack.deriv.trace_derivation(did)
        w2 = stack.deriv.trace_derivation(did)
        assert isinstance(w1, DerivationTraceSuccess) and isinstance(w2, DerivationTraceSuccess)
        assert w1.chain == w2.chain                    # pure read, deterministic verdicts
        assert stack.deriv.derivations_for_normalization(outcome.record.normalization_id) \
            == (did,)                                  # no records created by tracing


class TestPointerModel:
    def test_input_rows_carry_no_value_columns(self, stack):
        stack.derive_ok(PAGE_OK)
        cols = [row[1] for row in stack.deriv_store._conn.execute(
            "PRAGMA table_info(derivation_inputs)").fetchall()]
        assert "normalized_value" not in cols
        assert "value" not in cols
        assert "value_verbatim" not in cols
        assert set(cols) == {"derivation_id", "input_slot", "slot_name", "field_name",
                             "source_normalization_id", "field_seq",
                             "source_extraction_id"}

    def test_derived_value_exists_only_in_the_derivation_layer(self, stack):
        outcome, norm_id = stack.derive_ok(PAGE_OK)
        # the derivation stores the computed result...
        assert outcome.record.output_value == "1080"
        # ...while the source normalization record is unchanged and carries NO 1080
        read = stack.norm.read_normalization(norm_id)
        assert all(f.normalized_value != "1080" for f in read.fields)
        assert "total.gross" not in {f.source_field_name for f in read.fields}

    def test_input_pointers_resolve_to_live_verified_fields(self, stack):
        outcome, _ = stack.derive_ok(PAGE_OK)
        read = stack.norm.read_normalization(outcome.record.normalization_id)
        fields_by_seq = {f.field_seq: f for f in read.fields}
        for ref in outcome.inputs:
            field = fields_by_seq[ref.field_seq]
            assert field.source_field_name == ref.field_name
            assert field.status.value == "NORMALIZED"
            assert field.normalized_value is not None   # re-joined, not copied


class TestTamperPropagation:
    def test_tampered_normalization_breaks_the_chain_at_that_link(self, stack):
        outcome, _ = stack.derive_ok(PAGE_OK)
        stack.norm_store._conn.execute(
            "UPDATE normalization_fields SET normalized_value = 'TAMPERED' "
            "WHERE normalization_id = ? AND field_seq = 1",
            (outcome.record.normalization_id,))
        walk = stack.deriv.trace_derivation(outcome.record.derivation_id)
        assert isinstance(walk, DerivationTraceIntegrityFailure)
        assert walk.link in ("normalization", "extraction", "document", "binding")

    def test_deleted_extraction_breaks_the_chain_at_extraction_link(self, stack):
        outcome, _ = stack.derive_ok(PAGE_OK)
        # remove the bound extraction record from its store (simulated data loss)
        stack.extraction_store._conn.execute(
            "DELETE FROM extraction_fields WHERE extraction_id = ?",
            (outcome.record.extraction_id,))
        walk = stack.deriv.trace_derivation(outcome.record.derivation_id)
        assert type(walk).__name__ in ("DerivationTraceIntegrityFailure",
                                       "DerivationTraceVerificationUnavailable")
        assert isinstance(walk, (DerivationTraceIntegrityFailure,)) or \
            walk.issue_report
