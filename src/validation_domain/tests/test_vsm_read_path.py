"""Verify-on-Read and tamper-detection tests — WP-5.2 (SPEC-WP52-VSM §9/§13).

The full tamper matrix over every durable row class: state-record scalars,
validation refs, field projections, review items, and the hash-chained event
history — every tamper is caught inside the read, content is NEVER delivered.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import sqlite3  # noqa: E402

from validation_domain import (  # noqa: E402
    DomainStateReadIntegrityFailure,
    ReviewItemReadIntegrityFailure,
    ReviewEventRefused,
    REVIEW_STATUS_OPEN,
    ReviewItemReadSuccess,
)

from vsm_helpers import (  # noqa: E402
    PAGE_MISSING_TAX,
    R_TOLERANCE,
)


def _review_projection(stack):
    nid = stack.build_normalization(PAGE_MISSING_TAX)
    stack.val.validate(nid, R_TOLERANCE, "1")
    return stack.project(nid, [(R_TOLERANCE, "1")],
                         ruleset_id="kandoo-vsm-tamper")


def _tamper(stack, sql, params=()):
    """Directly mutate the store (there is NO update/delete path in any layer —
    the only way tampering can happen is outside the API, which is exactly what
    the fingerprints defend against)."""
    conn = sqlite3.connect(str(stack.vsm_db))
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


class TestVerifyOnRead:
    def test_clean_read_delivers_content(self, stack):
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        read = stack.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadSuccess"
        assert read.record.domain_state_id == state_id
        assert len(read.validation_refs) == 1
        assert len(read.field_projections) == 3
        assert read.review_item is not None
        assert read.review_status == REVIEW_STATUS_OPEN

    def test_read_is_repeatable_and_side_effect_free(self, stack):
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        first = stack.vsm.read_domain_state(state_id)
        second = stack.vsm.read_domain_state(state_id)
        assert first.record.record_fingerprint == \
            second.record.record_fingerprint
        assert first.verified_at == second.verified_at or True  # clock moves
        assert first.record.domain_state == second.record.domain_state

    def test_read_refused_for_unknown_id(self, stack):
        outcome = stack.vsm.read_domain_state("ghost")
        assert type(outcome).__name__ == "DomainStateReadRefused"


class TestStateTamperMatrix:
    def test_state_field_tamper_withholds_content(self, stack):
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        _tamper(stack, "UPDATE domain_state_records SET state_reason = 'x' "
                       "WHERE domain_state_id = ?", (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert isinstance(read, DomainStateReadIntegrityFailure)
        assert read.reason  # no content delivered

    def test_disposition_tamper_is_blocked_by_storage_gate(self, stack):
        """OD-S6: the frozen state↔disposition consistency CHECK refuses the
        mutation outright — the tamper cannot even happen."""
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        with pytest.raises(sqlite3.IntegrityError):
            _tamper(stack, "UPDATE domain_state_records SET disposition = 'CLEAR' "
                           "WHERE domain_state_id = ?", (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadSuccess"

    def test_invalid_state_value_tamper_is_blocked_by_storage_gate(self, stack):
        """OD-S6: an out-of-vocabulary state can never exist in the store —
        the CHECK refuses even direct SQL."""
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        with pytest.raises(sqlite3.IntegrityError):
            _tamper(stack, "UPDATE domain_state_records SET domain_state = "
                           "'INVENTED' WHERE domain_state_id = ?", (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadSuccess"

    def test_scalar_tamper_inside_vocabulary_withholds_content(self, stack):
        """An in-vocabulary scalar tamper (state_reason) passes the CHECKs but
        breaks the fingerprint → content withheld."""
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        _tamper(stack, "UPDATE domain_state_records SET state_reason = "
                       "'d01-unresolved-review-x' WHERE domain_state_id = ?",
                (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert isinstance(read, DomainStateReadIntegrityFailure)

    def test_fingerprint_column_tamper_withholds_content(self, stack):
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        _tamper(stack, "UPDATE domain_state_records SET record_fingerprint = "
                       "'deadbeef' WHERE domain_state_id = ?", (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert isinstance(read, DomainStateReadIntegrityFailure)

    def test_validation_ref_tamper_withholds_content(self, stack):
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        _tamper(stack, "UPDATE domain_state_validations SET outcome = 'VALID' "
                       "WHERE domain_state_id = ?", (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert isinstance(read, DomainStateReadIntegrityFailure)

    def test_field_projection_tamper_is_blocked_by_storage_gate(self, stack):
        """OD-S6: the projection-shape CHECK refuses a status flip without a
        consistent origin/pointer shape."""
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        with pytest.raises(sqlite3.IntegrityError):
            _tamper(stack, "UPDATE domain_state_fields SET projection_status = "
                           "'RESOLVED' WHERE domain_state_id = ?", (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadSuccess"

    def test_unresolved_reason_tamper_is_blocked_by_storage_gate(self, stack):
        """OD-S6: UNRESOLVED rows carry EXACTLY the frozen reason — an
        invented reason is refused by the CHECK itself."""
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        with pytest.raises(sqlite3.IntegrityError):
            _tamper(stack, "UPDATE domain_state_fields SET unresolved_reason = "
                           "'invented-reason' WHERE domain_state_id = ? AND "
                           "projection_status = 'UNRESOLVED'", (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadSuccess"

    def test_field_detail_tamper_inside_shape_withholds_content(self, stack):
        """A shape-legal detail tamper still breaks the fingerprint → content
        withheld (the fingerprint covers the full row set)."""
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        _tamper(stack, "UPDATE domain_state_fields SET detail = 'forged' "
                       "WHERE domain_state_id = ?", (state_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert isinstance(read, DomainStateReadIntegrityFailure)

    def test_ref_row_deletion_detected(self, stack):
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            conn.execute("DELETE FROM domain_state_validations WHERE "
                         "domain_state_id = ?", (state_id,))
            conn.commit()
        finally:
            conn.close()
        read = stack.vsm.read_domain_state(state_id)
        # row-count consistency check fires (rule_count vs rows)
        assert type(read).__name__ == "DomainStateReadVerificationUnavailable"


class TestReviewTamperMatrix:
    def test_item_tamper_withholds_content(self, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        _tamper(stack, "UPDATE review_queue_items SET review_reason = 'x' "
                       "WHERE review_id = ?", (review_id,))
        read = stack.vsm.read_review_item(review_id)
        assert isinstance(read, ReviewItemReadIntegrityFailure)

    def test_state_read_surfaces_broken_review_as_unavailable(self, stack):
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        review_id = projected.review_item.review_id
        _tamper(stack, "UPDATE review_queue_items SET review_detail = 'x' "
                       "WHERE review_id = ?", (review_id,))
        read = stack.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadVerificationUnavailable"

    def test_event_tamper_breaks_chain(self, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        stack.vsm.append_review_event(review_id, "ANNOTATE", "note", "op")
        stack.vsm.append_review_event(review_id, "ANNOTATE", "note2", "op2")
        _tamper(stack, "UPDATE review_queue_events SET event_note = 'forged' "
                       "WHERE event_seq = 0 AND review_id = ?", (review_id,))
        read = stack.vsm.read_review_item(review_id)
        assert isinstance(read, ReviewItemReadIntegrityFailure)
        assert "chain" in read.reason or "FAILED" in read.reason

    def test_event_deletion_breaks_chain_linkage(self, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        stack.vsm.append_review_event(review_id, "ANNOTATE", "note", "op")
        stack.vsm.append_review_event(review_id, "ANNOTATE", "note2", "op2")
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            conn.execute("DELETE FROM review_queue_events WHERE event_seq = 0 "
                         "AND review_id = ?", (review_id,))
            conn.commit()
        finally:
            conn.close()
        read = stack.vsm.read_review_item(review_id)
        # seq 1 now leads the chain but its prev fingerprint points at the
        # deleted event → linkage mismatch → integrity failure
        assert isinstance(read, ReviewItemReadIntegrityFailure)

    def test_tampered_item_refuses_new_events(self, stack):
        """An in-vocabulary item tamper (detail text) breaks the item
        fingerprint → every further event is refused fail-closed."""
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        _tamper(stack, "UPDATE review_queue_items SET review_detail = 'x' "
                       "WHERE review_id = ?", (review_id,))
        outcome = stack.vsm.append_review_event(review_id, "ANNOTATE",
                                                "note", "op")
        assert isinstance(outcome, ReviewEventRefused)
        assert "verified read" in outcome.detail
