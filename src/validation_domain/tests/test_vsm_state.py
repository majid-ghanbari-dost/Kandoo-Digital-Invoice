"""State-machine mapping tests — WP-5.2 (SPEC-WP52-VSM §3/§13).

Every transition route of the declared priority table (T1..T5), the verbatim
frozen vocabulary, transition validity, and invalid-transition rejection — all
over REAL P5.1 records produced by the real frozen pipeline.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import ValidationCompleted  # noqa: E402
from validation_domain import (  # noqa: E402
    DISPOSITION_CLEAR,
    DISPOSITION_REJECT,
    DISPOSITION_REVIEW,
    DOMAIN_STATES,
    DOMAIN_STATE_DEFERRED,
    DOMAIN_STATE_INVALID,
    DOMAIN_STATE_UNRESOLVED,
    DOMAIN_STATE_VALID,
    REASON_ALL_RULES_VALID,
    REASON_D01_UNRESOLVED_REVIEW,
    REASON_D08_MISMATCH_REVIEW,
    REASON_DECISIVE_INVALID,
    REASON_VALIDATION_DEFERRED_REVIEW,
    DomainStateAlreadyExists,
    DomainStateSourceRefused,
)

from vsm_helpers import (  # noqa: E402
    PAGE_ABSENT_FIELD,
    PAGE_AMBIGUOUS,
    PAGE_MISSING_TAX,
    PAGE_OK,
    PAGE_QUOT,
    R_CONSIST,
    R_PRESENT,
    R_ROUNDED,
    R_TOLERANCE,
    REF_KEYS,
    exact_match_rule,
    exact_probe_rule,
    nonexact_probe_rule,
    rounded_probe_rule,
    tolerance_probe_rule,
)


class TestValidMapping:
    def test_all_rules_valid_maps_to_valid_clear(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS)
        record = projected.record
        assert record.domain_state == DOMAIN_STATE_VALID
        assert record.disposition == DISPOSITION_CLEAR
        assert record.state_reason == REASON_ALL_RULES_VALID
        assert record.rule_count == 4
        assert record.valid_count == 4
        assert record.invalid_count == 0
        assert record.deferred_count == 0
        assert record.unresolved_count == 0
        assert projected.review_item is None

    def test_valid_detail_lists_every_rule_outcome(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS)
        for rule in (R_PRESENT, R_CONSIST, R_TOLERANCE, R_ROUNDED):
            assert f"{rule}/1 → VALID" in projected.record.state_detail
        assert "Canonicalization Gate" in projected.record.state_detail

    def test_single_rule_valid_ruleset_maps_valid(self, stack):
        nid = stack.build_derived()
        stack.val.validate(nid, R_PRESENT, "1")     # ONLY this rule evaluated
        projected = stack.project(nid, [(R_PRESENT, "1")],
                                  ruleset_id="kandoo-vsm-presence-only")
        assert projected.record.domain_state == DOMAIN_STATE_VALID
        assert projected.record.rule_count == 1


class TestInvalidMapping:
    def test_decisive_invalid_maps_to_invalid_reject(self, stack):
        nid = stack.build_derived(PAGE_OK)
        probe = exact_probe_rule()
        outcome = stack.val.validate(nid, probe.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "INVALID"
        assert outcome.record.outcome_reason == "mismatch"
        projected = stack.project(nid, [(probe.rule_id, "1")],
                                  ruleset_id="kandoo-vsm-probe")
        assert projected.record.domain_state == DOMAIN_STATE_INVALID
        assert projected.record.disposition == DISPOSITION_REJECT
        assert projected.record.state_reason == REASON_DECISIVE_INVALID
        assert projected.review_item is None

    def test_presence_absent_maps_to_invalid_reject(self, stack):
        nid = stack.build_normalization(PAGE_ABSENT_FIELD)
        outcome = stack.val.validate(nid, R_PRESENT, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome_reason == "absent"
        projected = stack.project(nid, [(R_PRESENT, "1")],
                                  ruleset_id="kandoo-vsm-presence-only")
        assert projected.record.domain_state == DOMAIN_STATE_INVALID
        assert projected.record.disposition == DISPOSITION_REJECT
        assert projected.record.state_reason == REASON_DECISIVE_INVALID

    def test_decisive_beats_tolerance_and_deferred(self, stack):
        """Priority T1 > T2/T4: decisive INVALID wins over co-occurring
        tolerance-INVALID and DEFERRED (OD-S8 declared order)."""
        nid = stack.build_derived(PAGE_OK)
        decisive = exact_probe_rule()                     # INVALID(mismatch)
        d = stack.val.validate(nid, decisive.rule_id, "1")
        assert isinstance(d, ValidationCompleted)
        assert d.record.outcome_reason == "mismatch"
        tolerance = tolerance_probe_rule()                # beyond-tolerance
        t = stack.val.validate(nid, tolerance.rule_id, "1")
        assert isinstance(t, ValidationCompleted)
        assert t.record.outcome_reason == "mismatch-beyond-tolerance"
        absent = stack.val.validate(nid, "vsm-probe-tolerance-absent", "1")
        assert isinstance(absent, ValidationCompleted)
        assert absent.record.outcome == "DEFERRED"        # insufficient-input
        projected = stack.project(
            nid, [(decisive.rule_id, "1"), (tolerance.rule_id, "1"),
                  ("vsm-probe-tolerance-absent", "1")],
            ruleset_id="kandoo-vsm-mixed")
        assert projected.record.domain_state == DOMAIN_STATE_INVALID
        assert projected.record.disposition == DISPOSITION_REJECT
        assert projected.record.state_reason == REASON_DECISIVE_INVALID

    def test_nonmatching_twin_probe_is_honest(self, stack):
        """The matching twin of the mismatch probe must be VALID — the state
        machine consumes honest verdicts, never rubber-stamps."""
        nid = stack.build_derived()
        probe = exact_match_rule()
        outcome = stack.val.validate(nid, probe.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "VALID"
        projected = stack.project(nid, [(probe.rule_id, "1")],
                                  ruleset_id="kandoo-vsm-twin")
        assert projected.record.domain_state == DOMAIN_STATE_VALID


class TestToleranceInvalidMapping:
    def test_beyond_tolerance_maps_to_invalid_review(self, stack):
        """T2 (D-08): mismatch-beyond-tolerance routes REVIEW — the frozen D-08
        path, implemented here where it belongs."""
        nid = stack.build_derived()
        probe = tolerance_probe_rule()
        outcome = stack.val.validate(nid, probe.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome_reason == "mismatch-beyond-tolerance"
        projected = stack.project(nid, [(probe.rule_id, "1")],
                                  ruleset_id="kandoo-vsm-probe-tol")
        assert projected.record.domain_state == DOMAIN_STATE_INVALID
        assert projected.record.disposition == DISPOSITION_REVIEW
        assert projected.record.state_reason == REASON_D08_MISMATCH_REVIEW
        assert projected.review_item is not None

    def test_mismatch_after_rounding_maps_to_invalid_review(self, stack):
        nid = stack.build_derived()
        probe = rounded_probe_rule()
        outcome = stack.val.validate(nid, probe.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome_reason == "mismatch-after-rounding"
        projected = stack.project(nid, [(probe.rule_id, "1")],
                                  ruleset_id="kandoo-vsm-probe-rnd")
        assert projected.record.domain_state == DOMAIN_STATE_INVALID
        assert projected.record.disposition == DISPOSITION_REVIEW
        assert projected.record.state_reason == REASON_D08_MISMATCH_REVIEW


class TestDeferredMapping:
    def test_nonexact_intermediate_maps_to_deferred_review(self, stack):
        nid = stack.build_normalization(PAGE_QUOT)
        probe = nonexact_probe_rule()
        outcome = stack.val.validate(nid, probe.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        assert outcome.record.outcome_reason == "non-exact-intermediate"
        projected = stack.project(nid, [(probe.rule_id, "1")],
                                  ruleset_id="kandoo-vsm-probe-nex")
        assert projected.record.domain_state == DOMAIN_STATE_DEFERRED
        assert projected.record.disposition == DISPOSITION_REVIEW
        assert projected.record.state_reason == REASON_VALIDATION_DEFERRED_REVIEW
        assert projected.record.deferred_count == 1
        assert projected.review_item is not None

    def test_ambiguous_input_maps_to_deferred_review(self, stack):
        """Ambiguity is canonicalization uncertainty (T4): the comparison defers
        on ≥2 candidates; the field itself projects RESOLVED (D-01 meaning
        preserved — methods exist) with the candidate count recorded; the state
        is DEFERRED/REVIEW with the Gate named."""
        nid = stack.build_normalization(PAGE_AMBIGUOUS)
        probe_id = "vsm-probe-tolerance-ambiguous"
        outcome = stack.val.validate(nid, probe_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        assert outcome.record.outcome_reason == "ambiguous-input"
        projected = stack.project(nid, [(probe_id, "1")],
                                  ruleset_id="kandoo-vsm-amb")
        assert projected.record.domain_state == DOMAIN_STATE_DEFERRED
        assert projected.record.disposition == DISPOSITION_REVIEW
        assert projected.record.state_reason == REASON_VALIDATION_DEFERRED_REVIEW
        assert "Canonicalization Gate" in projected.record.state_detail
        fields = {row.field_name: row for row in projected.field_projections}
        assert fields["total.net"].projection_status == "RESOLVED"
        assert fields["total.net"].candidate_count == 2
        assert projected.record.unresolved_count == 0

    def test_insufficient_input_with_no_unresolved_conflict_maps_deferred(
            self, stack):
        """DEFERRED with every declared field RESOLVED stays DEFERRED (T4) —
        the non-exact case: values exist, only the expression is undecidable."""
        nid = stack.build_normalization(PAGE_QUOT)
        probe = nonexact_probe_rule()
        stack.val.validate(nid, probe.rule_id, "1")
        projected = stack.project(nid, [(probe.rule_id, "1")],
                                  ruleset_id="kandoo-vsm-probe-nex")
        fields = {row.field_name: row for row in projected.field_projections}
        assert all(row.projection_status == "RESOLVED"
                   for row in fields.values())
        assert projected.record.domain_state == DOMAIN_STATE_DEFERRED


class TestVocabulary:
    def test_frozen_vocabulary_is_exactly_the_dispatched_distinction(self):
        assert DOMAIN_STATES == ("VALID", "INVALID", "DEFERRED", "UNRESOLVED")
        from validation_domain import DISPOSITIONS
        assert DISPOSITIONS == ("CLEAR", "REVIEW", "REJECT")

    def test_every_projected_state_is_inside_the_frozen_vocabulary(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS)
        assert projected.record.domain_state in DOMAIN_STATES
        assert projected.record.disposition in ("CLEAR", "REVIEW", "REJECT")

    def test_state_disposition_pairs_are_frozen_consistent(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        valid = stack.project(nid, REF_KEYS).record
        assert (valid.domain_state, valid.disposition) == ("VALID", "CLEAR")

        nid2 = stack.build_normalization(PAGE_ABSENT_FIELD)
        stack.val.validate(nid2, R_PRESENT, "1")
        invalid = stack.project(nid2, [(R_PRESENT, "1")],
                                ruleset_id="kandoo-vsm-p2").record
        assert (invalid.domain_state, invalid.disposition) == ("INVALID", "REJECT")

        nid3 = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid3, R_TOLERANCE, "1")
        unresolved = stack.project(nid3, [(R_TOLERANCE, "1")],
                                   ruleset_id="kandoo-vsm-p3").record
        assert (unresolved.domain_state,
                unresolved.disposition) == ("UNRESOLVED", "REVIEW")

        nid4 = stack.build_normalization(PAGE_QUOT)
        probe = nonexact_probe_rule()
        stack.val.validate(nid4, probe.rule_id, "1")
        deferred = stack.project(nid4, [(probe.rule_id, "1")],
                                 ruleset_id="kandoo-vsm-p4").record
        assert (deferred.domain_state,
                deferred.disposition) == ("DEFERRED", "REVIEW")


class TestTransitionRejections:
    def test_incomplete_evaluation_is_refused(self, stack):
        """Missing keys refuse: 1 rule evaluated, full ruleset declared."""
        nid = stack.build_derived()
        stack.val.validate(nid, R_PRESENT, "1")     # only ONE rule evaluated
        outcome = stack.vsm.project_domain_state(
            nid, "kandoo-vsm-partial", "1", list(REF_KEYS))
        assert isinstance(outcome, DomainStateSourceRefused)
        assert "declared but not evaluated" in outcome.detail

    def test_extra_records_are_refused(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        probe = exact_probe_rule()
        outcome = stack.val.validate(nid, probe.rule_id, "1")
        assert isinstance(outcome, ValidationCompleted)
        result = stack.vsm.project_domain_state(nid, "kandoo-vsm-ref", "1",
                                                list(REF_KEYS))
        assert isinstance(result, DomainStateSourceRefused)
        assert "evaluated but not declared" in result.detail

    def test_empty_ruleset_is_refused(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        outcome = stack.vsm.project_domain_state(nid, "kandoo-vsm-empty", "1", [])
        assert isinstance(outcome, DomainStateSourceRefused)
        assert "empty ruleset" in outcome.detail

    def test_duplicate_keys_are_refused(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        outcome = stack.vsm.project_domain_state(
            nid, "kandoo-vsm-dup", "1", [(R_PRESENT, "1"), (R_PRESENT, "1")])
        assert isinstance(outcome, DomainStateSourceRefused)
        assert "exactly once" in outcome.detail

    def test_projection_without_any_validation_record_is_refused(self, stack):
        nid = stack.build_normalization(PAGE_OK)
        outcome = stack.vsm.project_domain_state(
            nid, "kandoo-vsm-never", "1", [(R_PRESENT, "1")])
        assert isinstance(outcome, DomainStateSourceRefused)
        assert "never triggers validation" in outcome.detail

    def test_unknown_normalization_is_refused(self, stack):
        outcome = stack.vsm.project_domain_state(
            "no-such-normalization", "kandoo-vsm-x", "1", [(R_PRESENT, "1")])
        assert isinstance(outcome, DomainStateSourceRefused)

    def test_replay_returns_existing_not_a_second_record(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        first = stack.project(nid, REF_KEYS)
        replay = stack.vsm.project_domain_state(nid, "kandoo-vsm-rules", "1",
                                                list(REF_KEYS))
        assert isinstance(replay, DomainStateAlreadyExists)
        assert replay.domain_state_id == first.record.domain_state_id
        assert len(stack.vsm.domain_states_for_normalization(nid)) == 1
