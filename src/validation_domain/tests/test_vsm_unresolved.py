"""UNRESOLVED creation tests — WP-5.2 (SPEC-WP52-VSM §4/§13).

UNRESOLVED is created HERE (the only layer allowed to), strictly per the D-01
resolution order and meaning: field-level, reason/status-bearing, provenance-
preserving, traceable, never auto-resolved, never applied to ambiguous slots
(D-01 meaning preserved verbatim — ambiguous ≠ no-valid-method).
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import ValidationCompleted  # noqa: E402
from validation_domain import (  # noqa: E402
    DOMAIN_STATE_UNRESOLVED,
    UNRESOLVED_REASON_D01,
)

from vsm_helpers import (  # noqa: E402
    PAGE_DEFERRED_INPUT,
    PAGE_MISSING_TAX,
    PAGE_OK,
    R_TOLERANCE,
)


class TestUnresolvedCreation:
    def test_d01_order_exhaustion_creates_field_level_unresolved(self, stack):
        """PAGE_MISSING_TAX: tax.amount absent entirely, total.gross never
        derived — both declared fields exhaust the D-01 order → UNRESOLVED
        rows; total.net resolves (step 1)."""
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        outcome = stack.val.validate(nid, R_TOLERANCE, "1")
        assert isinstance(outcome, ValidationCompleted)
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-unres")
        record = projected.record
        assert record.domain_state == DOMAIN_STATE_UNRESOLVED
        assert record.unresolved_count == 2
        fields = {row.field_name: row for row in projected.field_projections}
        assert fields["total.net"].projection_status == "RESOLVED"
        assert fields["tax.amount"].projection_status == "UNRESOLVED"
        assert fields["tax.amount"].unresolved_reason == UNRESOLVED_REASON_D01
        assert fields["total.gross"].projection_status == "UNRESOLVED"
        assert fields["total.gross"].unresolved_reason == UNRESOLVED_REASON_D01

    def test_unresolved_row_shape_is_field_level(self, stack):
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-unres")
        row = next(r for r in projected.field_projections
                   if r.field_name == "tax.amount")
        assert row.projection_status == "UNRESOLVED"
        assert row.origin_relayed is None
        assert row.candidate_count == 0
        assert row.source_field_seq is None
        assert row.source_derivation_id is None
        assert row.unresolved_reason == UNRESOLVED_REASON_D01
        assert row.source_normalization_id == nid
        assert "never auto-resolved" in row.detail

    def test_present_but_not_normalized_field_is_unresolved(self, stack):
        """tax.amount=1.2.3 → P4.1 DEFERRED status: no usable EXTRACTED value,
        no DERIVED value → D-01 exhausted (the classic case)."""
        nid = stack.build_normalization(PAGE_DEFERRED_INPUT)
        outcome = stack.val.validate(nid, R_TOLERANCE, "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome == "DEFERRED"
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-unres2")
        fields = {row.field_name: row for row in projected.field_projections}
        assert fields["tax.amount"].projection_status == "UNRESOLVED"
        assert "DEFERRED" in fields["tax.amount"].detail   # upstream status noted
        assert fields["total.net"].projection_status == "RESOLVED"
        assert projected.record.domain_state == DOMAIN_STATE_UNRESOLVED

    def test_resolved_rows_relay_origin_and_pointers(self, stack):
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, stack.REF_KEYS
                                  if hasattr(stack, "REF_KEYS") else
                                  [("kandoo-val-total-net-present", "1"),
                                   ("kandoo-val-total-gross-consistency", "1"),
                                   ("kandoo-val-total-gross-tolerance", "1"),
                                   ("kandoo-val-total-gross-rounded", "1")])
        fields = {row.field_name: row for row in projected.field_projections}
        assert fields["total.net"].origin_relayed == "NORMALIZED"
        assert fields["total.net"].source_field_seq is not None
        assert fields["total.net"].source_derivation_id is None
        assert fields["total.gross"].origin_relayed == "DERIVED"
        assert fields["total.gross"].source_derivation_id is not None
        assert fields["total.gross"].source_field_seq is None
        assert fields["tax.amount"].origin_relayed == "NORMALIZED"

    def test_unresolved_never_created_for_resolved_field(self, stack):
        """A field with a usable value is NEVER labeled UNRESOLVED — even when
        the rule referencing it deferred for non-value reasons."""
        nid = stack.build_derived(PAGE_OK)
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-unres3")
        fields = {row.field_name: row for row in projected.field_projections}
        assert all(row.projection_status == "RESOLVED"
                   for row in fields.values())
        assert projected.record.unresolved_count == 0

    def test_unresolved_is_durable_and_traceable(self, stack):
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-unres4")
        state_id = projected.record.domain_state_id
        read = stack.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadSuccess"
        unresolved = [r for r in read.field_projections
                      if r.projection_status == "UNRESOLVED"]
        assert len(unresolved) == 2
        for row in unresolved:
            assert row.unresolved_reason == UNRESOLVED_REASON_D01
            assert row.source_normalization_id == nid
        walk = stack.vsm.trace_domain_state(state_id)
        assert type(walk).__name__ == "DomainStateTraceSuccess"
        assert any("capture" in link for link in walk.chain)


class TestUnresolvedMeaningPreserved:
    def test_ambiguous_slots_are_never_unresolved(self, stack):
        """OD-S10: ambiguous ≠ UNRESOLVED — methods exist (2 candidates), so the
        D-01 label is NOT applied; the field projects RESOLVED with the
        candidate count; the ambiguity routes via DEFERRED/REVIEW."""
        from vsm_helpers import PAGE_AMBIGUOUS
        nid = stack.build_normalization(PAGE_AMBIGUOUS)
        outcome = stack.val.validate(nid, "vsm-probe-tolerance-ambiguous", "1")
        assert isinstance(outcome, ValidationCompleted)
        assert outcome.record.outcome_reason == "ambiguous-input"
        projected = stack.project(nid, [("vsm-probe-tolerance-ambiguous", "1")],
                                  ruleset_id="kandoo-vsm-amb-unres")
        fields = {row.field_name: row for row in projected.field_projections}
        assert all(row.projection_status == "RESOLVED"
                   for row in fields.values())
        assert fields["total.net"].candidate_count == 2
        assert projected.record.unresolved_count == 0
        assert projected.record.domain_state == "DEFERRED"

    def test_unresolved_rows_never_auto_resolve(self, stack):
        """Re-reading an UNRESOLVED projection never mutates it — the D-01
        terminal label stays until a NEW ruleset version is projected."""
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-unres5")
        before = [(r.field_name, r.projection_status, r.unresolved_reason)
                  for r in projected.field_projections]
        reread = stack.vsm.read_domain_state(projected.record.domain_state_id)
        after = [(r.field_name, r.projection_status, r.unresolved_reason)
                 for r in reread.field_projections]
        assert before == after
        replay = stack.vsm.project_domain_state(nid, "kandoo-vsm-unres5", "1",
                                                [(R_TOLERANCE, "1")])
        assert type(replay).__name__ == "DomainStateAlreadyExists"
