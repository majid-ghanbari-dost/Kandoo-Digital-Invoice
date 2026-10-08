"""WP-6.1 gate decision-table tests — deterministic routing of verified P5.2
states onto the dispatch §14 paths (SPEC §4; dispatch axes 1–4, 24).

Covers: VALID/CLEAR acceptance; INVALID decisive rejection (G1); INVALID
tolerance REVIEW (G2, D-08 relayed verbatim); DEFERRED handling (G2);
UNRESOLVED handling (G2, D-01); replay G0 (AlreadyDecided); route priority;
upstream review referencing (OD-G9 — never duplicated); decision vocabulary
exactness.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cg_helpers import (  # noqa: E402
    BINDING,
    decisive_invalid_state,
    deferred_state,
    tolerance_invalid_state,
    unresolved_state,
)
from canonicalization import (  # noqa: E402
    DECISIONS,
    ORIGIN_HOLOO_CAPTURE,
    REASON_ALL_FROZEN_CONDITIONS_MET,
    REASON_D02_CAPTURE_REPLAY,
    REASON_UPSTREAM_DECISIVE_INVALID,
    CanonicalizationAccepted,
    CanonicalizationAlreadyDecided,
    CanonicalizationRejected,
    CanonicalizationRoutedToReview,
    CanonicalizationRequestRefused,
)


def test_valid_clear_is_accepted(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    assert outcome.decision.decision == "ACCEPTED"
    assert outcome.decision.decision_reason == REASON_ALL_FROZEN_CONDITIONS_MET


def test_invalid_decisive_is_rejected(stack):
    _, projection = decisive_invalid_state(stack)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRejected), outcome
    assert outcome.decision.decision_reason == REASON_UPSTREAM_DECISIVE_INVALID
    # the upstream decisive reason is relayed in the audit detail
    assert "decisive-invalid" in outcome.decision.decision_detail


def test_invalid_tolerance_routes_review_with_verbatim_reason(stack):
    _, projection = tolerance_invalid_state(stack)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    # the P5.2 state_reason is relayed VERBATIM (CL-1 — no paraphrase)
    assert outcome.decision.decision_reason == "d08-mismatch-review"
    assert outcome.decision.decision_reason == projection.record.state_reason


def test_deferred_routes_review_with_verbatim_reason(stack):
    _, projection = deferred_state(stack)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision_reason == "validation-deferred-review"
    assert outcome.decision.decision_reason == projection.record.state_reason


def test_unresolved_routes_review_with_verbatim_reason(stack):
    _, projection = unresolved_state(stack)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision_reason == "d01-unresolved-review"
    assert outcome.decision.decision_reason == projection.record.state_reason
    # the gate NEVER creates UNRESOLVED itself — the decision vocabulary
    # carries no such kind (D-01: P5.2 is the only legal creator)
    assert "UNRESOLVED" not in DECISIONS


def test_g2_references_upstream_review_without_duplicating(stack):
    _, projection = unresolved_state(stack)
    assert projection.review_item is not None
    upstream_id = projection.review_item.review_id
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    # the gate decision REFERENCES the P5.2 item (OD-G9)...
    assert outcome.decision.upstream_review_id == upstream_id
    assert upstream_id in outcome.decision.decision_detail
    # ...and the gate queue holds exactly ONE item for THIS decision — the
    # upstream queue is untouched (no duplication, no cross-layer writes)
    assert len(stack.gate.list_gate_review_items()) == 1
    assert len(stack.vsm.list_review_items()) == 1


def test_replay_returns_existing_decision_verbatim(stack):
    _, projection = stack.build_valid_identity_state()
    first = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(first, CanonicalizationAccepted), first
    replay = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(replay, CanonicalizationAlreadyDecided), replay
    assert replay.decision.decision_id == first.decision.decision_id
    assert replay.decision.record_fingerprint == \
        first.decision.record_fingerprint
    # a replay never creates rows
    assert len(stack.gate.decisions()) == 1


def test_replay_of_rejected_decision_is_idempotent(stack):
    _, projection = decisive_invalid_state(stack)
    first = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(first, CanonicalizationRejected), first
    replay = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(replay, CanonicalizationAlreadyDecided), replay
    assert replay.decision.decision == "REJECTED"
    assert len(stack.gate.decisions()) == 1


def test_replay_of_review_decision_is_idempotent(stack):
    _, projection = tolerance_invalid_state(stack)
    first = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(first, CanonicalizationRoutedToReview), first
    replay = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(replay, CanonicalizationAlreadyDecided), replay
    assert len(stack.gate.list_gate_review_items()) == 1


def test_g1_priority_over_identity(stack):
    """A decisive-invalid state NEVER reaches identity resolution — G1 fires
    even with a well-formed binding declared."""
    _, projection = decisive_invalid_state(stack)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationRejected), outcome
    assert outcome.decision.identity_class == ""
    assert outcome.decision.identity_fingerprint == ""


def test_g2_priority_over_identity(stack):
    """Upstream-held uncertainty routes G2 regardless of any binding."""
    _, projection = deferred_state(stack)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.identity_class == ""


def test_decision_vocabulary_is_exact(stack):
    """Only the dispatch §14 decision kinds exist in the durable store."""
    _, valid = stack.build_valid_identity_state()
    stack.gate.canonicalize(valid.record.domain_state_id,
                            ORIGIN_HOLOO_CAPTURE, BINDING)
    _, invalid = decisive_invalid_state(stack)
    stack.gate.canonicalize(invalid.record.domain_state_id,
                            ORIGIN_HOLOO_CAPTURE)
    _, defer = deferred_state(stack)
    stack.gate.canonicalize(defer.record.domain_state_id,
                            ORIGIN_HOLOO_CAPTURE)
    kinds = {d.decision for d in stack.gate.decisions()}
    assert kinds <= set(DECISIONS)
    assert kinds == {"ACCEPTED", "REJECTED", "REVIEW"}


def test_accepted_decision_links_exactly_one_invoice(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    read = stack.gate.read_gate_decision(outcome.decision.decision_id)
    assert type(read).__name__ == "GateDecisionReadSuccess", read
    assert read.canonical_invoice is not None
    assert read.canonical_invoice.canonical_invoice_id == \
        outcome.decision.canonical_invoice_id
    # rejected/review decisions carry no invoice
    _, invalid = decisive_invalid_state(stack)
    rejected = stack.gate.canonicalize(invalid.record.domain_state_id,
                                       ORIGIN_HOLOO_CAPTURE)
    assert isinstance(rejected, CanonicalizationRejected), rejected
    rread = stack.gate.read_gate_decision(rejected.decision.decision_id)
    assert type(rread).__name__ == "GateDecisionReadSuccess", rread
    assert rread.canonical_invoice is None


def test_replay_check_requires_verified_input(stack):
    """A tampered upstream state refuses BEFORE the replay check — a broken
    record never returns an existing decision as if it were fresh (fail-closed
    ordering: V1/V2 precede G0)."""
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    state_id = projection.record.domain_state_id
    # tamper the P5.2 state row directly (bypassing all layers)
    import sqlite3
    conn = sqlite3.connect(str(stack.vsm_db))
    try:
        conn.execute("UPDATE domain_state_records SET state_reason = 'forged'"
                     " WHERE domain_state_id = ?", (state_id,))
        conn.commit()
    finally:
        conn.close()
    replay = stack.gate.canonicalize(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert type(replay).__name__ == "CanonicalizationInputIntegrityFailure", \
        replay


def test_unknown_state_is_refused(stack):
    outcome = stack.gate.canonicalize("no-such-state",
                                      ORIGIN_HOLOO_CAPTURE, BINDING)
    assert type(outcome).__name__ == "CanonicalizationRequestRefused", outcome


def test_unprojected_normalization_is_refused_via_state_path(stack):
    """The gate refuses a state id that never existed — it never fabricates a
    decision from partial facts."""
    outcome = stack.gate.canonicalize("", ORIGIN_HOLOO_CAPTURE)
    assert type(outcome).__name__ == "CanonicalizationRequestRefused", outcome


def test_review_item_details_carry_the_route_reason(stack):
    _, projection = tolerance_invalid_state(stack)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.review_item.review_reason == "d08-mismatch-review"
    read = stack.gate.read_gate_review_item(outcome.review_item.review_id)
    assert type(read).__name__ == "GateReviewItemReadSuccess", read
    assert read.status == "OPEN"
