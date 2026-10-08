"""Durability, atomicity, and immutability tests — WP-5.2 (SPEC-WP52-VSM
§9/§13).

Restart recovery, zero-residue atomic commits, UNIQUE backstops (INV-S-1:1 /
INV-R-1:1), append-only history (no UPDATE/DELETE anywhere in the API), and the
event-hash-chain tail enforcement.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation_domain import (  # noqa: E402
    DomainStateDuplicate,
    DomainStatePersistenceUnavailable,
    DomainStateReadSuccess,
    REVIEW_STATUS_CLOSED,
    REVIEW_STATUS_OPEN,
    ReviewEventAppended,
    ReviewItemReadSuccess,
)

from vsm_helpers import (  # noqa: E402
    PAGE_MISSING_TAX,
    R_TOLERANCE,
)


def _review_projection(stack, ruleset_id="kandoo-vsm-dur"):
    nid = stack.build_normalization(PAGE_MISSING_TAX)
    stack.val.validate(nid, R_TOLERANCE, "1")
    return stack.project(nid, [(R_TOLERANCE, "1")], ruleset_id=ruleset_id)


class TestRestartRecovery:
    def test_state_projection_survives_restart_and_reverifies(self, make_stack,
                                                              stack):
        projected = _review_projection(stack)
        state_id = projected.record.domain_state_id
        review_id = projected.review_item.review_id
        stack.close()

        reopened = make_stack()
        try:
            read = reopened.vsm.read_domain_state(state_id)
            assert type(read).__name__ == "DomainStateReadSuccess"
            assert read.record.domain_state == "UNRESOLVED"
            assert read.record.disposition == "REVIEW"
            assert len(read.validation_refs) == 1
            assert len(read.field_projections) == 3
            assert read.review_item.review_id == review_id
            assert read.review_status == REVIEW_STATUS_OPEN
        finally:
            reopened.close()

    def test_closed_queue_survives_restart(self, make_stack, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        stack.vsm.append_review_event(review_id, "ANNOTATE", "pending", "op")
        stack.vsm.append_review_event(review_id, "CLOSE", "handled", "sup")
        stack.close()

        reopened = make_stack()
        try:
            read = reopened.vsm.read_review_item(review_id)
            assert type(read).__name__ == "ReviewItemReadSuccess"
            assert read.status == REVIEW_STATUS_CLOSED
            # terminality survives restart
            refused = reopened.vsm.append_review_event(
                review_id, "ANNOTATE", "late", "op")
            assert type(refused).__name__ == "ReviewEventRefused"
        finally:
            reopened.close()

    def test_replay_after_restart_returns_existing(self, make_stack, stack):
        projected = _review_projection(stack)
        stack.close()
        reopened = make_stack()
        try:
            replay = reopened.vsm.project_domain_state(
                projected.record.normalization_id, "kandoo-vsm-dur", "1",
                [(R_TOLERANCE, "1")])
            assert type(replay).__name__ == "DomainStateAlreadyExists"
        finally:
            reopened.close()


class TestAtomicCommit:
    def test_zero_residue_when_commit_refused(self, make_stack):
        """A refusal inside the commit (duplicate) leaves ZERO rows behind —
        the pre-existing projection is untouched."""
        projected = _review_projection(stack := make_stack())
        try:
            state_id = projected.record.domain_state_id
            import sqlite3
            before = sqlite3.connect(str(stack.vsm_db))
            counts_before = {
                table: before.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("domain_state_records", "domain_state_validations",
                              "domain_state_fields", "review_queue_items")
            }
            before.close()
            # in-transaction duplicate path (the store raises before any write)
            record = projected.record
            with pytest.raises(DomainStateDuplicate):
                stack.vsm_store.commit_projection(
                    record, projected.validation_refs,
                    projected.field_projections, projected.review_item)
            after = sqlite3.connect(str(stack.vsm_db))
            counts_after = {
                table: after.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in counts_before
            }
            after.close()
            assert counts_before == counts_after
        finally:
            stack.close()

    def test_commit_refuses_review_item_without_review_disposition(self, stack):
        """Python-side gate (OD-S6 defensive refusal): a VALID projection can
        never carry a REVIEW item."""
        from vsm_helpers import PAGE_OK
        from validation_domain import ReviewQueueItem
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS_FULL)
        forged_item = ReviewQueueItem(
            review_id="forged", domain_state_id=projected.record.domain_state_id,
            normalization_id=projected.record.normalization_id,
            extraction_id=projected.record.extraction_id,
            document_id=projected.record.document_id,
            capture_id=projected.record.capture_id,
            capture_s1=projected.record.capture_s1,
            ruleset_id=projected.record.ruleset_id,
            ruleset_version=projected.record.ruleset_version,
            ruleset_fingerprint=projected.record.ruleset_fingerprint,
            domain_state="VALID", review_reason="all-rules-valid",
            review_detail="d", created_at="2026-10-07T00:00:00+00:00",
            item_fingerprint="", fingerprint_algorithm_id="")
        with pytest.raises(DomainStatePersistenceUnavailable):
            stack.vsm_store.commit_projection(
                projected.record, projected.validation_refs,
                projected.field_projections, forged_item)

    def test_commit_refuses_unresolved_disposition_mismatch(self, stack):
        from vsm_helpers import PAGE_MISSING_TAX
        from validation_domain.model import DomainStateRecord as _R
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-gate2")
        forged = _R(**{**projected.record.__dict__,
                       "domain_state_id": "fresh-id",
                       "disposition": "REJECT"})
        with pytest.raises(DomainStatePersistenceUnavailable):
            stack.vsm_store.commit_projection(
                forged, (), (), None)


class TestUniquenessBackstops:
    def test_unique_index_backstops_state_projection(self, stack):
        projected = _review_projection(stack)
        import sqlite3
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO domain_state_records (domain_state_id, "
                    "normalization_id, extraction_id, document_id, capture_id, "
                    "capture_s1, capture_s1_algorithm_id, ruleset_id, "
                    "ruleset_version, ruleset_fingerprint, "
                    "ruleset_fingerprint_algorithm_id, domain_state, "
                    "disposition, state_reason, state_detail, rule_count, "
                    "valid_count, invalid_count, deferred_count, "
                    "unresolved_count, created_at, record_fingerprint, "
                    "fingerprint_algorithm_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("second-id", projected.record.normalization_id,
                     projected.record.extraction_id, projected.record.document_id,
                     projected.record.capture_id, projected.record.capture_s1,
                     "sha256-v1", "rs", "9", projected.record.ruleset_fingerprint,
                     "sha256-v1", "UNRESOLVED", "REVIEW", "r", "d", 1, 0, 0, 0,
                     2, "2026-10-07T00:00:00+00:00", "fp", "sha256-v1"))
        finally:
            conn.close()

    def test_unique_index_backstops_review_item(self, stack):
        projected = _review_projection(stack)
        import sqlite3
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO review_queue_items (review_id, "
                    "domain_state_id, normalization_id, extraction_id, "
                    "document_id, capture_id, capture_s1, ruleset_id, "
                    "ruleset_version, ruleset_fingerprint, domain_state, "
                    "review_reason, review_detail, created_at, "
                    "item_fingerprint, fingerprint_algorithm_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("second-review", projected.record.domain_state_id,
                     projected.record.normalization_id,
                     projected.record.extraction_id,
                     projected.record.document_id, projected.record.capture_id,
                     projected.record.capture_s1, "rs", "1", "rfp",
                     "UNRESOLVED", "r", "d", "2026-10-07T00:00:00+00:00",
                     "fp", "sha256-v1"))
        finally:
            conn.close()

    def test_unique_index_backstops_single_close(self, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        first = stack.vsm.append_review_event(review_id, "CLOSE", "done", "sup")
        assert isinstance(first, ReviewEventAppended)
        second = stack.vsm.append_review_event(review_id, "CLOSE", "again",
                                               "sup")
        assert type(second).__name__ == "ReviewEventRefused"


REF_KEYS_FULL = [("kandoo-val-total-net-present", "1"),
                 ("kandoo-val-total-gross-consistency", "1"),
                 ("kandoo-val-total-gross-tolerance", "1"),
                 ("kandoo-val-total-gross-rounded", "1")]


class TestAppendOnlyHistory:
    def test_store_has_no_update_or_delete_path(self):
        """Structural proof (AST): no SQL string constant in the store module
        starts with UPDATE or DELETE — inserts are the only write path."""
        import ast
        from pathlib import Path
        store_path = Path(__file__).resolve().parent.parent / "store.py"
        tree = ast.parse(store_path.read_text(encoding="utf-8"))
        forbidden = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value.strip().upper()
                if text.startswith("UPDATE ") or text.startswith("DELETE "):
                    forbidden.append(node.value[:60])
        assert not forbidden, f"UPDATE/DELETE SQL found: {forbidden}"

    def test_service_has_no_update_or_delete_path(self):
        """Same structural proof for the service module."""
        import ast
        from pathlib import Path
        service_path = Path(__file__).resolve().parent.parent / "service.py"
        tree = ast.parse(service_path.read_text(encoding="utf-8"))
        forbidden = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value.strip().upper()
                if text.startswith("UPDATE ") or text.startswith("DELETE "):
                    forbidden.append(node.value[:60])
        assert not forbidden, f"UPDATE/DELETE SQL found: {forbidden}"

    def test_event_seq_is_contiguous_and_append_only(self, stack):
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        for i in range(3):
            outcome = stack.vsm.append_review_event(
                review_id, "ANNOTATE", f"note-{i}", f"op-{i}")
            assert isinstance(outcome, ReviewEventAppended)
            assert outcome.event.event_seq == i
        read = stack.vsm.read_review_item(review_id)
        assert [e.event_seq for e in read.events] == [0, 1, 2]
        assert [e.event_note for e in read.events] == \
            ["note-0", "note-1", "note-2"]

    def test_event_chain_tail_enforced_on_append(self, stack):
        """Every appended event must link to the CURRENT chain tail — enforced
        by construction (the service reads the tail inside the append path)."""
        projected = _review_projection(stack)
        review_id = projected.review_item.review_id
        e0 = stack.vsm.append_review_event(review_id, "ANNOTATE", "n0", "a")
        e1 = stack.vsm.append_review_event(review_id, "CLOSE", "n1", "b")
        assert e1.event.prev_event_fingerprint == e0.event.event_fingerprint
        read = stack.vsm.read_review_item(review_id)
        assert read.status == REVIEW_STATUS_CLOSED
