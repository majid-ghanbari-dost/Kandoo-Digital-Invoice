"""WP-6.1 idempotency / atomicity / durability tests (SPEC §8 OD-C2/OD-C3;
dispatch axes 13–15).

Covers: same-state replay (AlreadyDecided); same-capture re-projection →
ALREADY_CANONICALIZED (D-02 S1 key); different-capture same-S2 → definite
duplicate REJECTION (D-03); no duplicate canonical invoices ever; atomic
commit with zero residue on forced failure; UNIQUE backstops under direct
insertion attempts; restart durability + re-verification.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cg_helpers import (  # noqa: E402
    BINDING,
    PAGE_IDENTITY_OK,
    PAGE_IDENTITY_TWIN,
    PAGE_IDENTITY_TWIN3,
    unique_identity_pages,
)
from canonicalization import (  # noqa: E402
    ORIGIN_HOLOO_CAPTURE,
    CanonicalizationAccepted,
    CanonicalizationAlreadyCanonicalized,
    CanonicalizationAlreadyDecided,
    CanonicalizationRejected,
    CanonicalizationRoutedToReview,
)


def test_same_capture_reprojection_routes_already_canonicalized(stack):
    """D-02: S1 is THE capture-level idempotency key. A re-projected state
    (new ruleset → new domain_state_id) over the SAME capture never yields a
    second canonical invoice — the replay is durable and explicit."""
    nid, p1 = stack.build_valid_identity_state(ruleset_id="cg-rules-a")
    o1 = stack.gate.canonicalize(p1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o1, CanonicalizationAccepted), o1
    # build a SECOND state over the SAME normalization (same capture S1) —
    # a different ruleset identity, so P5.2 legitimately creates a new record
    projection2 = stack.project(nid, keys=[
        ("kandoo-val-total-net-present", "1"),
        ("kandoo-val-total-gross-consistency", "1"),
        ("kandoo-val-total-gross-tolerance", "1"),
        ("kandoo-val-total-gross-rounded", "1")],
        ruleset_id="cg-rules-b", ruleset_version="2")
    o2 = stack.gate.canonicalize(projection2.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o2, CanonicalizationAlreadyCanonicalized), o2
    assert o2.existing_canonical_invoice.canonical_invoice_id == \
        o1.canonical_invoice.canonical_invoice_id
    assert o2.decision.decision == "ALREADY_CANONICALIZED"
    assert o2.decision.decision_reason == "d02-capture-idempotent-replay"
    # exactly ONE canonical invoice exists for this capture
    assert len(stack.gate.canonical_invoices()) == 1


def test_different_capture_same_s2_is_definite_duplicate(stack):
    """D-03: S2 complete + exact → definite document-level duplicate — a
    decisive REJECTION (not uncertainty), and no second invoice."""
    _, p1 = stack.build_valid_identity_state(parts=PAGE_IDENTITY_OK)
    o1 = stack.gate.canonicalize(p1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o1, CanonicalizationAccepted), o1
    # PAGE_IDENTITY_TWIN: same identity values, different byte order →
    # different capture S1, identical S2 tuple
    nid2, p2 = stack.build_valid_identity_state(parts=PAGE_IDENTITY_TWIN)
    assert p2.record.capture_s1 != p1.record.capture_s1
    o2 = stack.gate.canonicalize(p2.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o2, CanonicalizationRejected), o2
    assert o2.decision.decision_reason == "d03-definite-document-duplicate"
    assert len(stack.gate.canonical_invoices()) == 1


def test_document_duplicate_decision_is_durable_and_replayable(stack):
    _, p1 = stack.build_valid_identity_state(parts=PAGE_IDENTITY_OK)
    stack.gate.canonicalize(p1.record.domain_state_id,
                            ORIGIN_HOLOO_CAPTURE, BINDING)
    _, p2 = stack.build_valid_identity_state(parts=PAGE_IDENTITY_TWIN)
    first = stack.gate.canonicalize(p2.record.domain_state_id,
                                    ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(first, CanonicalizationRejected), first
    replay = stack.gate.canonicalize(p2.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(replay, CanonicalizationAlreadyDecided), replay
    assert len(stack.gate.decisions()) == 2     # accepted + duplicate-reject
    assert len(stack.gate.canonical_invoices()) == 1


def test_three_captures_one_document_exactly_one_invoice(stack):
    """One real-world document captured three times (distinct captures, same
    S2) → exactly one canonical invoice, two durable duplicate rejections."""
    _, p1 = stack.build_valid_identity_state(parts=PAGE_IDENTITY_OK)
    a = stack.gate.canonicalize(p1.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(a, CanonicalizationAccepted), a
    for twin_pages in (PAGE_IDENTITY_TWIN, PAGE_IDENTITY_TWIN3):
        _, pn = stack.build_valid_identity_state(parts=twin_pages)
        on = stack.gate.canonicalize(pn.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(on, CanonicalizationRejected), on
        assert on.decision.decision_reason == "d03-definite-document-duplicate"
    assert len(stack.gate.canonical_invoices()) == 1
    assert len(stack.gate.decisions()) == 3


def test_atomicity_forced_failure_leaves_zero_residue(stack, monkeypatch):
    """OD-C2: the admission is ONE transaction — a failure anywhere inside
    leaves no decision, no invoice, no pointer, no review item."""
    _, projection = stack.build_valid_identity_state()
    # break the fingerprint capability AFTER verification, BEFORE commit
    from capture import S1ComputationFailure

    real_compute = stack.gate_store._s1.compute

    def exploding_compute(payload):
        raise S1ComputationFailure("forced failure for atomicity test")

    monkeypatch.setattr(stack.gate_store._s1, "compute", exploding_compute)
    outcome = stack.gate.canonicalize(projection.record.domain_state_id,
                                      ORIGIN_HOLOO_CAPTURE, BINDING)
    monkeypatch.setattr(stack.gate_store._s1, "compute", real_compute)
    assert type(outcome).__name__ == "CanonicalizationStorageUnavailable", \
        outcome
    # zero residue — nothing was recordable
    assert len(stack.gate.decisions()) == 0
    assert len(stack.gate.canonical_invoices()) == 0
    assert len(stack.gate.list_gate_review_items()) == 0
    import sqlite3
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        for table in ("gate_decisions", "canonical_invoices",
                      "canonical_identity_pointers", "gate_review_items"):
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert n == 0, table
    finally:
        conn.close()


def test_unique_backstop_blocks_direct_capture_duplicate(stack):
    """The capture-level UNIQUE index backs the G4 check — even a direct SQL
    insert cannot mint a second canonical invoice for one capture."""
    _, p1 = stack.build_valid_identity_state()
    o1 = stack.gate.canonicalize(p1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o1, CanonicalizationAccepted), o1
    import sqlite3
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO canonical_invoices (
                       canonical_invoice_id, decision_id, domain_state_id,
                       normalization_id, extraction_id, document_id,
                       capture_id, capture_s1, capture_s1_algorithm_id,
                       origin, identity_class, identity_source,
                       identity_fingerprint, created_at, record_fingerprint,
                       fingerprint_algorithm_id)
                   VALUES ('fake-id','fake-decision','x','x','x','x','x',
                           ?, 'sha256-v1', 'HOLOO_CAPTURE', 'DETERMINISTIC',
                           'S2_EXTRACTED_VERIFIED', 'fp-x', '2026-01-01',
                           'fp', 'sha256-v1')""",
                (o1.canonical_invoice.capture_s1,))
    finally:
        conn.close()


def test_unique_backstop_blocks_direct_identity_duplicate(stack):
    _, p1 = stack.build_valid_identity_state()
    o1 = stack.gate.canonicalize(p1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o1, CanonicalizationAccepted), o1
    import sqlite3
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO canonical_invoices (
                       canonical_invoice_id, decision_id, domain_state_id,
                       normalization_id, extraction_id, document_id,
                       capture_id, capture_s1, capture_s1_algorithm_id,
                       origin, identity_class, identity_source,
                       identity_fingerprint, created_at, record_fingerprint,
                       fingerprint_algorithm_id)
                   VALUES ('fake-id-2','fake-decision-2','x','x','x','x','x',
                           'other-capture-s1', 'sha256-v1', 'HOLOO_CAPTURE',
                           'DETERMINISTIC', 'S2_EXTRACTED_VERIFIED', ?,
                           '2026-01-01', 'fp', 'sha256-v1')""",
                (o1.canonical_invoice.identity_fingerprint,))
    finally:
        conn.close()


def test_restart_durability_reopens_and_reverifies(make_stack):
    """OD-C1: synchronous=FULL + committed rows survive a full process
    restart; every read re-verifies; the gate refuses nothing and invents
    nothing after reopen."""
    s1_stack = make_stack()
    try:
        _, projection = s1_stack.build_valid_identity_state()
        outcome = s1_stack.gate.canonicalize(
            projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, CanonicalizationAccepted), outcome
        invoice_id = outcome.canonical_invoice.canonical_invoice_id
        decision_id = outcome.decision.decision_id
        review_before = len(s1_stack.gate.list_gate_review_items())
    finally:
        s1_stack.close()
    # "restart": fresh stack over the same DB files
    s2_stack = make_stack()
    try:
        read = s2_stack.gate.read_canonical_invoice(invoice_id)
        assert type(read).__name__ == "CanonicalInvoiceReadSuccess", read
        dread = s2_stack.gate.read_gate_decision(decision_id)
        assert type(dread).__name__ == "GateDecisionReadSuccess", dread
        trace = s2_stack.gate.trace_canonical_invoice(invoice_id)
        assert type(trace).__name__ == "CanonicalInvoiceTraceSuccess", trace
        # idempotent replay after restart
        replay = s2_stack.gate.canonicalize(
            outcome.decision.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(replay, CanonicalizationAlreadyDecided), replay
        assert len(s2_stack.gate.canonical_invoices()) == 1
        assert len(s2_stack.gate.list_gate_review_items()) == review_before
    finally:
        s2_stack.close()


def test_unresolved_review_survives_restart(make_stack):
    """A gate REVIEW item (canonicalization uncertainty) survives restart with
    its OPEN status derived from the append-only history."""
    from cg_helpers import unique_identity_pages
    s1_stack = make_stack()
    try:
        nid, projection = s1_stack.build_valid_identity_state(
            parts=[b"invoice.number=INV-RST-1\ninvoice.date=2026-10-07\n"
                   b"total.net=500.00\ntax.amount=40\n"])
        outcome = s1_stack.gate.canonicalize(
            projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
        assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
        review_id = outcome.review_item.review_id
    finally:
        s1_stack.close()
    s2_stack = make_stack()
    try:
        read = s2_stack.gate.read_gate_review_item(review_id)
        assert type(read).__name__ == "GateReviewItemReadSuccess", read
        assert read.status == "OPEN"
        assert len(read.events) == 0
    finally:
        s2_stack.close()
