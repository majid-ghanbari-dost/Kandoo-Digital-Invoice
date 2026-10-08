"""End-to-end behavior tests — WP-5.2 (SPEC-WP52-VSM §13).

The full frozen pipeline plus the domain layer, under one composition:
Capture → Reconstruction → Extraction → Evidence Binding → Normalization →
Derivation → R1/R2 Validation → Domain State Machine + REVIEW Queue →
whole-chain trace → REVIEW lifecycle → restart → tamper → frozen-layer sweep.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import ValidationCompleted  # noqa: E402
from validation_domain import (  # noqa: E402
    DomainStateReadSuccess,
    DomainStateTraceSuccess,
    ReviewEventAppended,
    REVIEW_STATUS_CLOSED,
    ReviewItemReadSuccess,
)

from vsm_helpers import (  # noqa: E402
    PAGE_MISSING_TAX,
    PAGE_OK,
    R_TOLERANCE,
)

REF_KEYS_FULL = [("kandoo-val-total-net-present", "1"),
                 ("kandoo-val-total-gross-consistency", "1"),
                 ("kandoo-val-total-gross-tolerance", "1"),
                 ("kandoo-val-total-gross-rounded", "1")]


def test_full_pipeline_valid_clear_no_review(make_stack):
    """Happy path: four green rule outcomes → VALID/CLEAR, no REVIEW item,
    whole chain machine-checkable to Capture S1."""
    stack = make_stack()
    try:
        nid = stack.build_derived(PAGE_OK, label="e2e-valid")
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS_FULL,
                                  ruleset_id="kandoo-vsm-e2e-valid")
        assert projected.record.domain_state == "VALID"
        assert projected.record.disposition == "CLEAR"
        assert projected.review_item is None
        assert stack.vsm.list_review_items() == ()

        walk = stack.vsm.trace_domain_state(projected.record.domain_state_id)
        assert isinstance(walk, DomainStateTraceSuccess)
        assert any(link.startswith("capture: OK") for link in walk.chain)
    finally:
        stack.close()


def test_full_pipeline_unresolved_review_lifecycle_restart(make_stack):
    """Uncertainty path: missing values → UNRESOLVED/REVIEW → durable item →
    annotate → close (terminal) → restart re-verifies everything."""
    stack = make_stack()
    try:
        nid = stack.build_normalization(PAGE_MISSING_TAX, label="e2e-unres")
        outcome = stack.val.validate(nid, R_TOLERANCE, "1")
        assert isinstance(outcome, ValidationCompleted)
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-e2e-unres")
        record, item = projected.record, projected.review_item
        assert record.domain_state == "UNRESOLVED"
        assert record.disposition == "REVIEW"
        assert item is not None
        review_id = item.review_id

        annotated = stack.vsm.append_review_event(
            review_id, "ANNOTATE", "inspection scheduled", "op-42")
        assert isinstance(annotated, ReviewEventAppended)
        closed = stack.vsm.append_review_event(
            review_id, "CLOSE", "handled downstream", "supervisor")
        assert isinstance(closed, ReviewEventAppended)

        state_id = record.domain_state_id
    finally:
        stack.close()

    reopened = make_stack()
    try:
        state_read = reopened.vsm.read_domain_state(state_id)
        assert type(state_read).__name__ == "DomainStateReadSuccess"
        assert state_read.review_status == REVIEW_STATUS_CLOSED
        item_read = reopened.vsm.read_review_item(review_id)
        assert type(item_read).__name__ == "ReviewItemReadSuccess"
        assert len(item_read.events) == 2
        walk = reopened.vsm.trace_domain_state(state_id)
        assert isinstance(walk, DomainStateTraceSuccess)
    finally:
        reopened.close()


def test_tamper_caught_after_restart(make_stack, stack):
    """Fingerprint tamper detection survives restarts: content withheld, queue
    frozen fail-closed."""
    stack2 = stack
    nid = stack2.build_normalization(PAGE_MISSING_TAX, label="e2e-tamper")
    stack2.val.validate(nid, R_TOLERANCE, "1")
    projected = stack2.project(nid, [(R_TOLERANCE, "1")],
                               ruleset_id="kandoo-vsm-e2e-tamper")
    state_id = projected.record.domain_state_id
    review_id = projected.review_item.review_id
    stack2.close()

    import sqlite3
    reopened = make_stack()
    try:
        # in-place tamper (no API path exists for UPDATE/DELETE — by design)
        conn = sqlite3.connect(str(reopened.vsm_db))
        try:
            conn.execute("UPDATE domain_state_records SET state_detail = 'x' "
                         "WHERE domain_state_id = ?", (state_id,))
            conn.commit()
        finally:
            conn.close()
        read = reopened.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadIntegrityFailure"
        refused = reopened.vsm.append_review_event(review_id, "ANNOTATE",
                                                   "note", "op")
        assert type(refused).__name__ == "ReviewEventRefused"
    finally:
        reopened.close()
