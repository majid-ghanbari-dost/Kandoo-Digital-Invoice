"""REVIEW queue tests — WP-5.2 (SPEC-WP52-VSM §5/§9/§13).

The queue as a REAL mechanism: durable, idempotent (INV-R-1:1), duplicate-
controlled, reason- and provenance-carrying, append-only hash-chained lifecycle
with derived status, CLOSE terminal — never a semantic resolver.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation_domain import (  # noqa: E402
    DISPOSITION_REVIEW,
    DOMAIN_STATE_INVALID,
    DOMAIN_STATE_UNRESOLVED,
    EVENT_ANNOTATE,
    EVENT_CLOSE,
    REASON_D01_UNRESOLVED_REVIEW,
    REASON_D08_MISMATCH_REVIEW,
    REASON_VALIDATION_DEFERRED_REVIEW,
    REVIEW_STATUS_CLOSED,
    REVIEW_STATUS_OPEN,
    ReviewEventAppended,
    ReviewEventRefused,
    ReviewItemReadRefused,
    ReviewItemReadSuccess,
)

from vsm_helpers import (  # noqa: E402
    PAGE_ALT_OK,
    PAGE_MISSING_TAX,
    PAGE_OK,
    PAGE_QUOT,
    R_TOLERANCE,
    exact_probe_rule,
    nonexact_probe_rule,
    tolerance_probe_rule,
)


def _review_projection(stack, ruleset_id="kandoo-vsm-review"):
    nid = stack.build_normalization(PAGE_MISSING_TAX)
    stack.val.validate(nid, R_TOLERANCE, "1")
    return stack.project(nid, [(R_TOLERANCE, "1")], ruleset_id=ruleset_id)


class TestReviewCreation:
    def test_review_disposition_creates_exactly_one_item(self, stack):
        projected = _review_projection(stack)
        assert projected.record.disposition == DISPOSITION_REVIEW
        assert projected.review_item is not None
        item = projected.review_item
        assert item.domain_state_id == projected.record.domain_state_id
        assert item.normalization_id == projected.record.normalization_id
        assert item.domain_state == DOMAIN_STATE_UNRESOLVED
        assert item.review_reason == REASON_D01_UNRESOLVED_REVIEW
        assert len(stack.vsm.list_review_items()) == 1

    def test_item_carries_provenance_anchors(self, stack):
        projected = _review_projection(stack)
        item = projected.review_item
        assert item.extraction_id == projected.record.extraction_id
        assert item.document_id == projected.record.document_id
        assert item.capture_id == projected.record.capture_id
        assert item.capture_s1 == projected.record.capture_s1
        assert item.ruleset_fingerprint == \
            projected.record.ruleset_fingerprint

    def test_reasons_are_route_specific(self, stack):
        # D-08 mismatch route
        nid = stack.build_derived(PAGE_OK)
        tol = tolerance_probe_rule()
        stack.val.validate(nid, tol.rule_id, "1")
        p1 = stack.project(nid, [(tol.rule_id, "1")],
                           ruleset_id="kandoo-vsm-r-d08")
        assert p1.review_item.review_reason == REASON_D08_MISMATCH_REVIEW
        # deferred route
        nid2 = stack.build_normalization(PAGE_QUOT)
        nex = nonexact_probe_rule()
        stack.val.validate(nid2, nex.rule_id, "1")
        p2 = stack.project(nid2, [(nex.rule_id, "1")],
                           ruleset_id="kandoo-vsm-r-def")
        assert p2.review_item.review_reason == \
            REASON_VALIDATION_DEFERRED_REVIEW
        # decisive REJECT creates NO item
        nid3 = stack.build_derived(PAGE_ALT_OK)     # different bytes (D-03)
        dec = exact_probe_rule()
        stack.val.validate(nid3, dec.rule_id, "1")
        p3 = stack.project(nid3, [(dec.rule_id, "1")],
                           ruleset_id="kandoo-vsm-r-rej")
        assert p3.record.disposition == "REJECT"
        assert p3.review_item is None

    def test_clear_disposition_creates_no_item(self, stack):
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, stack.__dict__.get("REF_KEYS") or
                                  [("kandoo-val-total-net-present", "1"),
                                   ("kandoo-val-total-gross-consistency", "1"),
                                   ("kandoo-val-total-gross-tolerance", "1"),
                                   ("kandoo-val-total-gross-rounded", "1")])
        assert projected.record.disposition == "CLEAR"
        assert projected.review_item is None
        assert len(stack.vsm.list_review_items()) == 0


class TestReviewIdempotencyAndDuplicates:
    def test_replay_returns_same_item_no_duplicate(self, stack):
        projected = _review_projection(stack)
        replay = stack.vsm.project_domain_state(
            projected.record.normalization_id, "kandoo-vsm-review", "1",
            [(R_TOLERANCE, "1")])
        assert type(replay).__name__ == "DomainStateAlreadyExists"
        assert len(stack.vsm.list_review_items()) == 1

    def test_new_ruleset_version_creates_distinct_state_and_item(self, stack):
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        p1 = stack.project(nid, [(R_TOLERANCE, "1")],
                           ruleset_id="kandoo-vsm-review", ruleset_version="1")
        p2 = stack.project(nid, [(R_TOLERANCE, "1")],
                           ruleset_id="kandoo-vsm-review", ruleset_version="2")
        assert p1.record.domain_state_id != p2.record.domain_state_id
        assert p1.review_item.review_id != p2.review_item.review_id
        assert len(stack.vsm.list_review_items()) == 2

    def test_two_uncertainties_two_items_deterministic_order(self, stack):
        _review_projection(stack, ruleset_id="kandoo-vsm-review-a")
        nid2 = stack.build_normalization(PAGE_QUOT, label="vsm-test-2")
        nex = nonexact_probe_rule()
        stack.val.validate(nid2, nex.rule_id, "1")
        stack.project(nid2, [(nex.rule_id, "1")],
                      ruleset_id="kandoo-vsm-review-b")
        ids = stack.vsm.list_review_items()
        assert len(ids) == 2
        read_a = stack.vsm.read_review_item(ids[0])
        read_b = stack.vsm.read_review_item(ids[1])
        assert type(read_a).__name__ == "ReviewItemReadSuccess"
        assert type(read_b).__name__ == "ReviewItemReadSuccess"
        assert read_a.status == REVIEW_STATUS_OPEN
        assert read_b.status == REVIEW_STATUS_OPEN


class TestReviewLifecycle:
    def test_annotate_appends_and_status_stays_open(self, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        outcome = stack.vsm.append_review_event(
            review_id, EVENT_ANNOTATE, "operator inspection pending", "op-7")
        assert isinstance(outcome, ReviewEventAppended)
        assert outcome.status == REVIEW_STATUS_OPEN
        assert outcome.event.event_seq == 0
        read = stack.vsm.read_review_item(review_id)
        assert type(read).__name__ == "ReviewItemReadSuccess"
        assert read.status == REVIEW_STATUS_OPEN
        assert len(read.events) == 1
        assert read.events[0].event_actor == "op-7"

    def test_close_is_terminal_and_status_derives_closed(self, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        closed = stack.vsm.append_review_event(
            review_id, EVENT_CLOSE, "resolved by external process", "supervisor")
        assert isinstance(closed, ReviewEventAppended)
        assert closed.status == REVIEW_STATUS_CLOSED
        read = stack.vsm.read_review_item(review_id)
        assert read.status == REVIEW_STATUS_CLOSED
        # terminality: every further event is refused
        again = stack.vsm.append_review_event(
            review_id, EVENT_CLOSE, "second close", "supervisor")
        assert isinstance(again, ReviewEventRefused)
        assert "terminal" in again.detail
        note = stack.vsm.append_review_event(
            review_id, EVENT_ANNOTATE, "post-close note", "op-7")
        assert isinstance(note, ReviewEventRefused)

    def test_unknown_event_type_is_refused(self, stack):
        projected = _review_projection(stack)
        outcome = stack.vsm.append_review_event(
            projected.review_item.review_id, "RESOLVE", "auto-resolve", "bot")
        assert isinstance(outcome, ReviewEventRefused)
        assert "unknown event type" in outcome.detail

    def test_event_requires_actor_and_known_item(self, stack):
        projected = _review_projection(stack)
        no_actor = stack.vsm.append_review_event(
            projected.review_item.review_id, EVENT_ANNOTATE, "note", "")
        assert isinstance(no_actor, ReviewEventRefused)
        unknown = stack.vsm.append_review_event(
            "no-such-review", EVENT_ANNOTATE, "note", "op")
        assert isinstance(unknown, ReviewEventRefused)
        missing = stack.vsm.read_review_item("no-such-review")
        assert isinstance(missing, ReviewItemReadRefused)

    def test_event_chain_is_hash_linked(self, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        e0 = stack.vsm.append_review_event(review_id, EVENT_ANNOTATE,
                                           "first", "op-1")
        e1 = stack.vsm.append_review_event(review_id, EVENT_ANNOTATE,
                                           "second", "op-2")
        assert isinstance(e0, ReviewEventAppended)
        assert isinstance(e1, ReviewEventAppended)
        assert e0.event.event_seq == 0
        assert e1.event.event_seq == 1
        assert e0.event.prev_event_fingerprint == ""
        assert e1.event.prev_event_fingerprint == e0.event.event_fingerprint
        read = stack.vsm.read_review_item(review_id)
        assert len(read.events) == 2


class TestReviewPersistence:
    def test_queue_survives_restart_with_derived_status(self, make_stack,
                                                        stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        stack.vsm.append_review_event(review_id, EVENT_ANNOTATE, "note", "op")
        stack.vsm.append_review_event(review_id, EVENT_CLOSE, "done", "sup")
        state_id = projected.record.domain_state_id
        stack.close()

        reopened = make_stack()
        try:
            read = reopened.vsm.read_review_item(review_id)
            assert type(read).__name__ == "ReviewItemReadSuccess"
            assert read.status == REVIEW_STATUS_CLOSED
            assert len(read.events) == 2
            state_read = reopened.vsm.read_domain_state(state_id)
            assert type(state_read).__name__ == "DomainStateReadSuccess"
            assert state_read.review_status == REVIEW_STATUS_CLOSED
            assert reopened.vsm.list_review_items() == (review_id,)
        finally:
            reopened.close()

    def test_review_item_read_refused_for_unknown_id(self, stack):
        outcome = stack.vsm.read_review_item("missing-id")
        assert isinstance(outcome, ReviewItemReadRefused)
