"""WP-7.2 reprint-flow tests — first sighting → reprint recognition
(verbatim, zero new rows), drift refusal propagation, restart durability,
reprints of duplicate and CAPTURE_SCOPED captures, tamper fail-closed
(SPEC §4 F2/F4/F5/F6, §5; D-02/D-03)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from df_helpers import (  # noqa: E402
    BINDING,
    IdentityReadSuccess,
    IdentityReplay,
    IdentityRequestRefused,
    FlowDuplicateRecognized,
    FlowIdentityEstablished,
    FlowInputIntegrityFailure,
    FlowReadIntegrityFailure,
    FlowReadSuccess,
    FlowReprintRecognized,
    FlowRequestRefused,
    FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
    FLOW_OUTCOME_IDENTITY_ESTABLISHED,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    absent_total_role_pages,
    ambiguous_number_pages,
    third_order_pages,
    twin_pages,
    unique_ir_pages,
)

REFUSAL_DRIFT = "replay-declaration-drift"


# ---------------------------------------------------------------------------
# F2 → F4: the first sighting establishes; every re-presentation recognizes
# ---------------------------------------------------------------------------

def test_first_sighting_commits_exactly_one_identity_established(stack):
    outcome, _ = stack.establish(label="df-reprint-a1")
    assert isinstance(outcome, FlowIdentityEstablished)
    assert outcome.disposition.flow_outcome \
        == FLOW_OUTCOME_IDENTITY_ESTABLISHED
    assert outcome.disposition.original_resolution_id == ""
    assert outcome.disposition.duplicate_observation_id == ""
    assert outcome.disposition.resolution_id \
        == outcome.record.resolution_id
    assert outcome.disposition.identity_scope == outcome.record.identity_scope
    assert len(stack.flow_store.list_dispositions()) == 1
    assert len(stack.identity_store.list_resolutions()) == 1


def test_reprint_returns_the_disposition_verbatim_with_zero_new_rows(stack):
    outcome, _ = stack.establish(label="df-reprint-a2")
    dispositions_before = len(stack.flow_store.list_dispositions())
    resolutions_before = len(stack.identity_store.list_resolutions())
    observations_before = _observations(stack)

    reprint = stack.flows.handle(_state_of(stack, outcome),
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(reprint, FlowReprintRecognized)
    assert reprint.disposition == outcome.disposition
    assert reprint.record == outcome.record
    assert reprint.role_rows == outcome.role_rows
    assert reprint.observation is None
    assert len(stack.flow_store.list_dispositions()) == dispositions_before
    assert len(stack.identity_store.list_resolutions()) \
        == resolutions_before
    assert _observations(stack) == observations_before


def test_reprint_via_a_reprojected_state_is_still_recognized(stack):
    """A re-projection creates a NEW domain_state_id over the SAME
    capture_s1 — the S1 key still drives the recognition (WP-7.1 Case A
    discipline consumed at flow level)."""
    outcome, nid = stack.establish(label="df-reprint-a3")
    assert nid is not None
    reprint = stack.handle_nid(nid)
    assert isinstance(reprint, FlowReprintRecognized)
    assert reprint.disposition == outcome.disposition


def test_reprint_after_restart_is_recognized_from_durable_state(make_stack):
    stack = make_stack()
    outcome, _ = stack.establish(label="df-reprint-a4")
    state_id = _state_of(stack, outcome)
    disposition_id = outcome.disposition.disposition_id
    stack.close()

    reopened = make_stack()
    try:
        reprint = reopened.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE,
                                        BINDING)
        assert isinstance(reprint, FlowReprintRecognized)
        assert reprint.disposition.disposition_id == disposition_id
        assert len(reopened.flow_store.list_dispositions()) == 1
    finally:
        reopened.close()


def _state_of(stack, outcome):
    """The domain_state_id of the established capture — re-derivable from
    the durable record chain (the state record is unique per projection)."""
    return outcome.record.domain_state_id


def _observations(stack):
    import sqlite3
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM identity_duplicate_observations"
        ).fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Reprint discipline — drift refusal, tamper fail-closed
# ---------------------------------------------------------------------------

def test_reprint_with_drifted_declaration_is_refused_verbatim(stack):
    outcome, _ = stack.establish(label="df-reprint-drift")
    before = len(stack.flow_store.list_dispositions())
    reprint = stack.flows.handle(_state_of(stack, outcome),
                                 ORIGIN_HOLOO_CAPTURE,
                                 {**BINDING, "INVOICE_DATE": "invoice.date",
                                  "INVOICE_NUMBER": "invoice.number",
                                  "INVOICE_TOTAL": "total.net"})
    # same binding content → same declaration fingerprint → reprint, not
    # drift; the drift needs a genuinely DIFFERENT declaration
    assert isinstance(reprint, FlowReprintRecognized)
    assert len(stack.flow_store.list_dispositions()) == before

    drifted = stack.flows.handle(_state_of(stack, outcome),
                                 ORIGIN_HOLOO_CAPTURE,
                                 {**BINDING, "INVOICE_TOTAL": "tax.amount"})
    assert isinstance(drifted, FlowRequestRefused)
    assert REFUSAL_DRIFT in drifted.detail
    assert len(stack.flow_store.list_dispositions()) == before


def test_reprint_with_drifted_origin_is_refused(stack):
    outcome, _ = stack.establish(label="df-reprint-origin")
    reprint = stack.flows.handle(_state_of(stack, outcome),
                                 ORIGIN_OTHER_POS_CAPTURE, BINDING)
    assert isinstance(reprint, FlowRequestRefused)
    assert REFUSAL_DRIFT in reprint.detail


def test_reprint_of_a_tampered_disposition_fails_closed(stack, make_stack):
    stack0 = make_stack()
    outcome, _ = stack0.establish(label="df-reprint-tamper")
    state_id = _state_of(stack0, outcome)
    stack0.close()

    reopened = make_stack()
    try:
        import sqlite3
        conn = sqlite3.connect(str(reopened.flows_db))
        try:
            conn.execute(
                "UPDATE flow_dispositions SET document_id = 'forged' "
                "WHERE 1=1")   # direct SQL — no UPDATE path exists in code
            conn.commit()
        finally:
            conn.close()
        outcome2 = reopened.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE,
                                         BINDING)
        # the identity layer replays, but the flow read must verify the
        # disposition → the tampered row is refused, never recognized
        assert isinstance(outcome2, FlowInputIntegrityFailure)
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# Reprints across capture shapes — duplicate captures, CAPTURE_SCOPED
# ---------------------------------------------------------------------------

def test_reprint_of_a_duplicate_capture_returns_duplicate_disposition(stack):
    first, _ = stack.establish(label="df-reprint-dup1")
    assert isinstance(first, FlowIdentityEstablished)
    fingerprint = first.record.identity_fingerprint

    twin = stack.handle_new(parts=twin_pages(),
                            label="df-reprint-dup1-twin")
    assert isinstance(twin, FlowDuplicateRecognized)
    assert twin.disposition.flow_outcome \
        == FLOW_OUTCOME_DUPLICATE_RECOGNIZED
    assert twin.disposition.original_resolution_id \
        == first.record.resolution_id

    # re-present the twin → reprint recognition of ITS duplicate disposition
    reprint = stack.flows.handle(twin.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(reprint, FlowReprintRecognized)
    assert reprint.disposition == twin.disposition
    assert reprint.disposition.flow_outcome \
        == FLOW_OUTCOME_DUPLICATE_RECOGNIZED
    assert reprint.observation is not None
    assert len(stack.flow_store.list_dispositions()) == 2
    assert first.record.identity_fingerprint == fingerprint


def test_reprint_of_a_capture_scoped_capture_is_established_not_duplicate(
        stack):
    """A CAPTURE_SCOPED capture (ambiguous number) is IDENTITY_ESTABLISHED
    with NO document identity — its reprint is the same capture-scoped
    disposition, never a duplicate recognition (D-03)."""
    first = stack.handle_new(parts=ambiguous_number_pages(),
                             label="df-reprint-cs1")
    assert isinstance(first, FlowIdentityEstablished)
    assert first.record.identity_scope == "CAPTURE_SCOPED"
    assert first.disposition.identity_fingerprint == ""

    state_id = first.record.domain_state_id
    reprint = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(reprint, FlowReprintRecognized)
    assert reprint.disposition == first.disposition
    assert reprint.disposition.flow_outcome \
        == FLOW_OUTCOME_IDENTITY_ESTABLISHED


def test_third_capture_of_same_document_still_points_at_one_original(stack):
    first, _ = stack.establish(label="df-reprint-3rd")
    twin = stack.handle_new(parts=twin_pages(),
                            label="df-reprint-3rd-twin")
    third = stack.handle_new(parts=third_order_pages(),
                             label="df-reprint-3rd-third")
    assert isinstance(third, FlowDuplicateRecognized)
    assert third.disposition.original_resolution_id \
        == first.record.resolution_id
    assert twin.disposition.original_resolution_id \
        == first.record.resolution_id
    assert len(stack.flow_store.list_dispositions()) == 3
