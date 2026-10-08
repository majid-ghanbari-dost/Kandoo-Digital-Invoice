"""WP-10.1 lifecycle-act tests (SPEC §5): the transition matrix, terminal
discipline, replay semantics, supersede verification, NOTHING automatic."""
import pytest

from digital_invoice import (
    LifecycleAdvanced,
    LifecycleReplay,
    LifecycleRequestRefused,
    REFUSE_NO_DIGITAL_INVOICE,
    REFUSE_REPLACEMENT_NOT_ISSUED,
    REFUSE_SUPERSEDE_CONFLICT,
    REFUSE_SUPERSEDE_SELF,
    REFUSE_TRANSITION_UNAVAILABLE,
    STATE_DRAFT,
    STATE_EXTRACTED,
    STATE_ISSUED,
    STATE_REVOKED,
    STATE_SUPERSEDED,
    STATE_VALIDATED,
    is_legal_transition,
    predecessor_of,
    expected_outgoing,
    project_current_state,
)

from di_helpers import unique_di_pages


def _to_issued(stack, invoice_id, note=""):
    stack.open_ok(invoice_id)
    stack.advance_ok(invoice_id, "mark_extracted", note)
    stack.advance_ok(invoice_id, "mark_validated", note)
    stack.advance_ok(invoice_id, "issue", note)


def test_full_happy_path_draft_to_issued(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-life-1")
    stack.open_ok(invoice_id)
    e1 = stack.advance_ok(invoice_id, "mark_extracted")
    assert isinstance(e1, LifecycleAdvanced)
    assert e1.event.event_type == "MARK_EXTRACTED"
    assert (e1.event.from_state, e1.event.to_state) == (STATE_DRAFT,
                                                        STATE_EXTRACTED)
    assert e1.current_state == STATE_EXTRACTED
    e2 = stack.advance_ok(invoice_id, "mark_validated")
    assert e2.current_state == STATE_VALIDATED
    e3 = stack.advance_ok(invoice_id, "issue")
    assert isinstance(e3, LifecycleAdvanced)
    assert e3.current_state == STATE_ISSUED
    assert e3.event.event_type == "ISSUE"
    read = stack.read_ok(invoice_id)
    assert read.current_state == STATE_ISSUED
    assert len(read.events) == 3                       # no genesis event
    assert [e.event_seq for e in read.events] == [0, 1, 2]   # gap-free
    assert [e.from_state for e in read.events] == \
        [STATE_DRAFT, STATE_EXTRACTED, STATE_VALIDATED]  # chain closure


def test_revoke_from_issued_terminal(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-life-2")
    _to_issued(stack, invoice_id)
    outcome = stack.advance_ok(invoice_id, "revoke")
    assert isinstance(outcome, LifecycleAdvanced)
    assert outcome.current_state == STATE_REVOKED
    read = stack.read_ok(invoice_id)
    assert read.current_state == STATE_REVOKED
    # terminal: nothing follows — the target-state act replays (§5.3 A3),
    # every OTHER act is refused (terminal discipline)
    replay = stack.di.revoke(invoice_id)
    assert isinstance(replay, LifecycleReplay), replay
    before = len(stack.di.lifecycle_events())
    for act in ("mark_extracted", "mark_validated", "issue"):
        refused = getattr(stack.di, act)(invoice_id)
        assert isinstance(refused, LifecycleRequestRefused), (act, refused)
        assert "terminal" in refused.detail
    assert len(stack.di.lifecycle_events()) == before  # zero residue


def test_supersede_from_issued_terminal_with_verified_pointer(stack):
    _, source = stack.assemble_di_invoice(label="di-life-3a")
    _, replacement = stack.assemble_di_invoice(parts=unique_di_pages(),
                                               label="di-life-3b")
    _to_issued(stack, source)
    _to_issued(stack, replacement)
    outcome = stack.advance_ok(source, "supersede", replacement)
    assert isinstance(outcome, LifecycleAdvanced)
    assert outcome.current_state == STATE_SUPERSEDED
    assert outcome.event.replacement_invoice_id == replacement
    read = stack.read_ok(source)
    assert read.current_state == STATE_SUPERSEDED
    # the replacement remains ISSUED (its own lifecycle untouched)
    assert stack.read_ok(replacement).current_state == STATE_ISSUED
    # terminal: nothing follows on the source
    refused = stack.di.supersede(source, replacement)
    assert isinstance(refused, LifecycleReplay)        # exact-state replay


def test_supersede_refuses_unknown_replacement(stack):
    _, source = stack.assemble_di_invoice(label="di-life-4")
    _to_issued(stack, source)
    refused = stack.di.supersede(source, "no-such-replacement")
    assert isinstance(refused, LifecycleRequestRefused), refused
    assert REFUSE_REPLACEMENT_NOT_ISSUED in refused.detail
    assert len(stack.di.lifecycle_events()) == 3       # zero residue


def test_supersede_refuses_replacement_not_issued(stack):
    _, source = stack.assemble_di_invoice(label="di-life-5a")
    _, draft_repl = stack.assemble_di_invoice(parts=unique_di_pages(),
                                              label="di-life-5b")
    _to_issued(stack, source)
    stack.open_ok(draft_repl)                          # DRAFT replacement
    refused = stack.di.supersede(source, draft_repl)
    assert isinstance(refused, LifecycleRequestRefused), refused
    assert REFUSE_REPLACEMENT_NOT_ISSUED in refused.detail
    # VALIDATED replacement too
    stack.advance_ok(draft_repl, "mark_extracted")
    stack.advance_ok(draft_repl, "mark_validated")
    refused2 = stack.di.supersede(source, draft_repl)
    assert isinstance(refused2, LifecycleRequestRefused), refused2
    assert REFUSE_REPLACEMENT_NOT_ISSUED in refused2.detail
    assert len(stack.di.lifecycle_events()) == 5       # zero residue


def test_supersede_refuses_self(stack):
    _, source = stack.assemble_di_invoice(label="di-life-6")
    _to_issued(stack, source)
    refused = stack.di.supersede(source, source)
    assert isinstance(refused, LifecycleRequestRefused), refused
    assert REFUSE_SUPERSEDE_SELF in refused.detail


def test_supersede_replay_requires_byte_match_replacement(stack):
    _, source = stack.assemble_di_invoice(label="di-life-7a")
    _, repl_a = stack.assemble_di_invoice(parts=unique_di_pages(),
                                          label="di-life-7b")
    _, repl_b = stack.assemble_di_invoice(parts=unique_di_pages(),
                                          label="di-life-7c")
    _to_issued(stack, source)
    _to_issued(stack, repl_a)
    _to_issued(stack, repl_b)
    stack.advance_ok(source, "supersede", repl_a)
    replay = stack.di.supersede(source, repl_a)
    assert isinstance(replay, LifecycleReplay), replay  # byte-match replay
    conflict = stack.di.supersede(source, repl_b)
    assert isinstance(conflict, LifecycleRequestRefused), conflict
    assert REFUSE_SUPERSEDE_CONFLICT in conflict.detail


def test_supersede_cycle_structurally_impossible(stack):
    """a→b then b→a is impossible: the replacement must be ISSUED and a
    superseded source is never ISSUED again (terminal discipline)."""
    _, a = stack.assemble_di_invoice(label="di-life-8a")
    _, b = stack.assemble_di_invoice(parts=unique_di_pages(),
                                     label="di-life-8b")
    _to_issued(stack, a)
    _to_issued(stack, b)
    stack.advance_ok(a, "supersede", b)                # a SUPERSEDED by b
    refused = stack.di.supersede(b, a)                 # b wants to point at a
    assert isinstance(refused, LifecycleRequestRefused), refused
    assert REFUSE_REPLACEMENT_NOT_ISSUED in refused.detail
    assert stack.read_ok(b).current_state == STATE_ISSUED
    assert stack.read_ok(a).current_state == STATE_SUPERSEDED


def test_every_skip_and_backward_transition_refused_zero_residue(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-life-9")
    stack.open_ok(invoice_id)
    events_before = len(stack.di.lifecycle_events())
    # skips from DRAFT
    for act in ("mark_validated", "issue", "revoke", "supersede"):
        kwargs = {"reason_note": ""} if act != "supersede" else {}
        if act == "supersede":
            continue
        refused = getattr(stack.di, act)(invoice_id)
        assert isinstance(refused, LifecycleRequestRefused), (act, refused)
        assert REFUSE_TRANSITION_UNAVAILABLE in refused.detail
    stack.advance_ok(invoice_id, "mark_extracted")
    # at the target state the same act is a REPLAY (§5.3 A3 — zero rows);
    # genuine backward movement does not exist in the matrix at all
    replay = stack.di.mark_extracted(invoice_id)
    assert isinstance(replay, LifecycleReplay), replay
    for act in ("issue", "revoke"):
        refused = getattr(stack.di, act)(invoice_id)
        assert isinstance(refused, LifecycleRequestRefused), (act, refused)
        assert REFUSE_TRANSITION_UNAVAILABLE in refused.detail
    stack.advance_ok(invoice_id, "mark_validated")
    stack.advance_ok(invoice_id, "issue")
    # backward attempts from ISSUED
    for act in ("mark_extracted", "mark_validated"):
        refused = getattr(stack.di, act)(invoice_id)
        assert isinstance(refused, LifecycleRequestRefused), (act, refused)
    assert len(stack.di.lifecycle_events()) == events_before + 3


def test_revoke_and_supersede_mutually_exclusive(stack):
    _, inv1 = stack.assemble_di_invoice(label="di-life-10a")
    _, inv2 = stack.assemble_di_invoice(parts=unique_di_pages(),
                                        label="di-life-10b")
    _to_issued(stack, inv1)
    _to_issued(stack, inv2)
    stack.advance_ok(inv1, "revoke")                   # inv1 → REVOKED
    refused = stack.di.supersede(inv1, inv2)           # terminal discipline
    assert isinstance(refused, LifecycleRequestRefused), refused
    assert "terminal" in refused.detail
    # supersede of inv2 POINTING at the revoked inv1 → the replacement is
    # not ISSUED (§5.4 act-time precondition — also the cycle guard)
    refused2 = stack.di.supersede(inv2, inv1)
    assert isinstance(refused2, LifecycleRequestRefused), refused2
    assert REFUSE_REPLACEMENT_NOT_ISSUED in refused2.detail
    assert stack.read_ok(inv2).current_state == STATE_ISSUED
    assert stack.read_ok(inv1).current_state == STATE_REVOKED


def test_replay_semantics_zero_new_rows_at_every_state(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-life-11")
    stack.open_ok(invoice_id)
    counts = []
    for act in ("mark_extracted", "mark_extracted", "mark_validated",
                "mark_validated", "issue", "issue"):
        outcome = getattr(stack.di, act)(invoice_id)
        assert isinstance(outcome, (LifecycleAdvanced, LifecycleReplay)), \
            outcome
        counts.append(len(stack.di.lifecycle_events()))
    assert counts == [1, 1, 2, 2, 3, 3]                # replay = zero rows
    read = stack.read_ok(invoice_id)
    assert read.current_state == STATE_ISSUED


def test_act_on_unknown_digital_invoice_refused(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-life-12")
    # invoice exists but has NO digital invoice
    for act in ("mark_extracted", "mark_validated", "issue", "revoke"):
        refused = getattr(stack.di, act)(invoice_id)
        assert isinstance(refused, LifecycleRequestRefused), (act, refused)
        assert REFUSE_NO_DIGITAL_INVOICE in refused.detail
    refused = stack.di.supersede(invoice_id, "anything")
    assert isinstance(refused, LifecycleRequestRefused), refused
    assert len(stack.di.lifecycle_events()) == 0       # zero residue


def test_reason_note_recorded_verbatim(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-life-13")
    stack.open_ok(invoice_id)
    note = "approved by finance — ref #٤٢; whitespace  preserved "
    outcome = stack.advance_ok(invoice_id, "mark_extracted", note)
    assert outcome.event.reason_note == note           # verbatim, no trim
    read = stack.read_ok(invoice_id)
    assert read.events[0].reason_note == note


def test_projection_is_pure_function_of_events(stack):
    """project_current_state is a pure fold — no clock/env influence."""
    assert project_current_state(()) == STATE_DRAFT
    _, invoice_id = stack.assemble_di_invoice(label="di-life-14")
    stack.open_ok(invoice_id)
    read = stack.read_ok(invoice_id)
    assert project_current_state(read.events) == STATE_DRAFT
    stack.advance_ok(invoice_id, "mark_extracted")
    read = stack.read_ok(invoice_id)
    assert project_current_state(read.events) == STATE_EXTRACTED
    # the pure helpers agree with the matrix
    assert predecessor_of(STATE_ISSUED) == STATE_VALIDATED
    assert predecessor_of(STATE_DRAFT) is None
    assert expected_outgoing(STATE_REVOKED) is None
    assert expected_outgoing(STATE_ISSUED) == ("SUPERSEDE", STATE_SUPERSEDED)
    assert is_legal_transition("ISSUE", "VALIDATED", "ISSUED")
    assert not is_legal_transition("ISSUE", "DRAFT", "ISSUED")
    assert not is_legal_transition("MARK_EXTRACTED", "ISSUED", "DRAFT")


def test_supersede_chain_a_b_c_auditable(stack):
    _, a = stack.assemble_di_invoice(label="di-life-15a")
    _, b = stack.assemble_di_invoice(parts=unique_di_pages(),
                                     label="di-life-15b")
    _, c = stack.assemble_di_invoice(parts=unique_di_pages(),
                                     label="di-life-15c")
    _to_issued(stack, a)
    _to_issued(stack, b)
    _to_issued(stack, c)
    stack.advance_ok(a, "supersede", b)
    stack.advance_ok(b, "supersede", c)
    assert stack.read_ok(a).current_state == STATE_SUPERSEDED
    assert stack.read_ok(b).current_state == STATE_SUPERSEDED
    assert stack.read_ok(c).current_state == STATE_ISSUED
    # two sources may point at the same replacement (explicit recorded acts)
    _, d = stack.assemble_di_invoice(parts=unique_di_pages(),
                                     label="di-life-15d")
    _to_issued(stack, d)
    stack.advance_ok(c, "supersede", d)                # c SUPERSEDED by d
    assert stack.read_ok(c).current_state == STATE_SUPERSEDED
    assert stack.read_ok(d).current_state == STATE_ISSUED
