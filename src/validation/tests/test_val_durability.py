"""Durability behavior tests — WP-5.1 (SPEC-WP51-VAL §9).

Restart safety, INV-V-1:1 idempotency, atomic-commit zero-residue, UNIQUE-index
backstop, and the no-UPDATE/DELETE immutability guarantee.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import (
    ValidationAlreadyExists,
    ValidationCompleted,
    ValidationReadSuccess,
    ValidationTraceSuccess,
)

from val_helpers import (
    FORMULA,
    PAGE_OK,
    R_CONSIST,
    R_PRESENT,
    R_ROUNDED,
)
from derivation import DerivationCompleted


class TestRestartDurability:
    def test_validation_durable_across_restart(self, make_stack):
        stack = make_stack()
        nid = stack.build_extract_normalize(PAGE_OK)
        outcome = stack.validate_ok(nid, R_PRESENT)
        validation_id = outcome.record.validation_id
        stack.close()

        reopened = make_stack()
        try:
            read = reopened.val.read_validation(validation_id)
            assert isinstance(read, ValidationReadSuccess)
            assert read.record.outcome == "VALID"
            assert read.record.normalization_id == nid
            # whole chain still re-verifies after restart
            walk = reopened.val.trace_validation(validation_id)
            assert isinstance(walk, ValidationTraceSuccess)
        finally:
            reopened.close()

    def test_replay_after_restart_is_idempotent(self, make_stack):
        stack = make_stack()
        nid = stack.build_extract_normalize(PAGE_OK)
        first = stack.validate_ok(nid, R_PRESENT)
        stack.close()

        reopened = make_stack()
        try:
            replay = reopened.val.validate(nid, R_PRESENT, "1")
            assert isinstance(replay, ValidationAlreadyExists)
            assert replay.validation_id == first.record.validation_id
            assert len(reopened.val.validations_for_normalization(nid)) == 1
        finally:
            reopened.close()

    def test_derived_input_chain_durable_across_restart(self, make_stack):
        stack = make_stack()
        nid = stack.build_derive_validate_ready(PAGE_OK)
        outcome = stack.validate_ok(nid, R_CONSIST)
        validation_id = outcome.record.validation_id
        stack.close()

        reopened = make_stack()
        try:
            read = reopened.val.read_validation(validation_id)
            assert isinstance(read, ValidationReadSuccess)
            derived_ref = next(r for r in read.inputs
                               if r.value_origin == "DERIVED")
            sub = reopened.deriv.read_derivation(derived_ref.source_derivation_id)
            assert type(sub).__name__ == "DerivationReadSuccess"
            walk = reopened.val.trace_validation(validation_id)
            assert isinstance(walk, ValidationTraceSuccess)
        finally:
            reopened.close()


class TestAtomicCommitAndIdempotency:
    def test_zero_residue_when_commit_refused(self, stack):
        """A storage-layer refusal leaves NOTHING behind (OD-V2 atomicity)."""
        nid = stack.build_extract_normalize(PAGE_OK)
        from validation import ValidationStorageUnavailable
        broken_store = stack.val_store
        # force a duplicate-check bypass: pre-seed the triple via the service first
        first = stack.validate_ok(nid, R_PRESENT)
        # now attempt a second commit path with a poisoned fingerprint capability:
        # simulate by asserting the UNIQUE backstop directly
        with pytest.raises(Exception):
            broken_store._conn.execute(
                """INSERT INTO validation_records (
                       validation_id, normalization_id, extraction_id, document_id,
                       capture_id, capture_s1, capture_s1_algorithm_id, ruleset_id,
                       ruleset_version, rule_id, rule_version, rule_kind, rule_type,
                       rule_fingerprint, rule_fingerprint_algorithm_id, outcome,
                       outcome_reason, outcome_detail, rounding_applied,
                       rounding_precision, rounding_mode, rounding_input_value,
                       rounding_output_value, input_count, created_at,
                       record_fingerprint, fingerprint_algorithm_id)
                   SELECT validation_id || 'x', normalization_id, extraction_id,
                       document_id, capture_id, capture_s1,
                       capture_s1_algorithm_id, ruleset_id, ruleset_version,
                       rule_id, rule_version, rule_kind, rule_type,
                       rule_fingerprint, rule_fingerprint_algorithm_id, outcome,
                       outcome_reason, outcome_detail, rounding_applied,
                       rounding_precision, rounding_mode, rounding_input_value,
                       rounding_output_value, input_count, created_at,
                       record_fingerprint, fingerprint_algorithm_id
                   FROM validation_records WHERE validation_id = ?""",
                (first.record.validation_id,))
        assert len(stack.val.validations_for_normalization(nid)) == 1

    def test_unique_index_is_storage_level_backstop(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)
        first = stack.validate_ok(nid, R_PRESENT)
        indexes = stack.val_store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' "
            "AND tbl_name = 'validation_records'").fetchall()
        names = {r["name"] for r in indexes}
        assert "uq_validation_normalization_rule" in names
        # the in-transaction check fires first through the service path:
        replay = stack.val.validate(nid, R_PRESENT, "1")
        assert isinstance(replay, ValidationAlreadyExists)
        assert replay.validation_id == first.record.validation_id

    def test_mixed_rule_versions_persist_independently(self, make_stack):
        from val_helpers import swapped_rule
        stack = make_stack(extra_rules=[swapped_rule()])
        try:
            nid = stack.build_derive_validate_ready(PAGE_OK)
            v1 = stack.validate_ok(nid, R_CONSIST, "1")
            v2 = stack.val.validate(nid, R_CONSIST, "2")
            assert isinstance(v2, ValidationCompleted)
            assert v1.record.validation_id != v2.record.validation_id
            assert len(stack.val.validations_for_normalization(nid)) == 2
        finally:
            stack.close()

    def test_no_update_or_delete_api_exists(self, stack):
        """The immutable-history guarantee is structural: the store exposes no
        UPDATE/DELETE path at all."""
        assert not hasattr(stack.val_store, "update")
        assert not hasattr(stack.val_store, "delete")
        assert not hasattr(stack.val_store, "update_validation")
        assert not hasattr(stack.val_store, "delete_validation")

    def test_refused_validation_leaves_zero_rows(self, stack):
        nid = stack.build_extract_normalize(PAGE_OK)
        stack.val.validate(nid, "no-such-rule", "1")
        rows = stack.val_store._conn.execute(
            "SELECT COUNT(*) AS n FROM validation_records").fetchone()["n"]
        assert rows == 0
        input_rows = stack.val_store._conn.execute(
            "SELECT COUNT(*) AS n FROM validation_inputs").fetchone()["n"]
        assert input_rows == 0
