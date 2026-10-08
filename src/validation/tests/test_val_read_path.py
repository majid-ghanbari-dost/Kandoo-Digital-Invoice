"""Verified-read (VOR) behavior tests — WP-5.1 (SPEC-WP51-VAL §8/§9).

Verify-on-Read, tamper detection, storage gates, and the structural guarantee
that broken content is NEVER delivered.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import (
    ValidationReadIntegrityFailure,
    ValidationReadRefused,
    ValidationReadSuccess,
    ValidationReadVerificationUnavailable,
)

from val_helpers import (
    PAGE_MISSING_TAX,
    PAGE_OK,
    R_CONSIST,
    R_PRESENT,
)


def make_validation(stack, parts=None, rule_id=R_PRESENT, version="1"):
    nid = stack.build_extract_normalize(parts or PAGE_OK)
    outcome = stack.val.validate(nid, rule_id, version)
    assert type(outcome).__name__ == "ValidationCompleted", outcome
    return outcome, nid


class TestVerifyOnRead:
    def test_healthy_read_delivers_content_with_fresh_verdict(self, stack):
        outcome, _ = make_validation(stack)
        read = stack.val.read_validation(outcome.record.validation_id)
        assert isinstance(read, ValidationReadSuccess)
        assert read.record.record_fingerprint == outcome.record.record_fingerprint
        assert read.verified_at is not None
        assert len(read.inputs) == read.record.input_count

    def test_read_is_repeatable_and_side_effect_free(self, stack):
        outcome, _ = make_validation(stack)
        first = stack.val.read_validation(outcome.record.validation_id)
        second = stack.val.read_validation(outcome.record.validation_id)
        assert isinstance(first, ValidationReadSuccess)
        assert isinstance(second, ValidationReadSuccess)
        assert first.record == second.record

    def test_unknown_validation_id_refused(self, stack):
        read = stack.val.read_validation("no-such-id")
        assert isinstance(read, ValidationReadRefused)
        assert not hasattr(read, "record")

    def test_no_content_without_same_read_verdict_is_structural(self, stack):
        """Every content-carrying read outcome carries the verdict fields; refusal
        outcomes carry NO record attribute at all."""
        outcome, _ = make_validation(stack)
        stack.val_store._conn.execute(
            "UPDATE validation_records SET outcome_reason = 'X' WHERE validation_id = ?",
            (outcome.record.validation_id,))
        broken = stack.val.read_validation(outcome.record.validation_id)
        assert isinstance(broken, ValidationReadIntegrityFailure)
        assert not hasattr(broken, "record")
        assert not hasattr(broken, "inputs")


class TestTamperDetection:
    def test_outcome_tamper_caught_content_withheld(self, stack):
        outcome, _ = make_validation(stack)
        stack.val_store._conn.execute(
            "UPDATE validation_records SET outcome = 'INVALID' "
            "WHERE validation_id = ?", (outcome.record.validation_id,))
        broken = stack.val.read_validation(outcome.record.validation_id)
        assert isinstance(broken, ValidationReadIntegrityFailure)

    def test_rounding_audit_tamper_caught(self, make_stack):
        from val_helpers import PAGE_OK, R_ROUNDED, quotient_rule
        stack = make_stack(extra_rules=[quotient_rule(
            rule_id="val-tamper-quotient", target_field="q.target",
            target_origin="normalized", numerator="total.net", denominator="b",
            precision=2, mode="HALF_UP")])
        try:
            nid = stack.build_extract_normalize(
                [b"total.net=1000.00\nb=3\nq.target=333.33\n"])
            outcome = stack.val.validate(nid, "val-tamper-quotient", "1")
            assert type(outcome).__name__ == "ValidationCompleted"
            assert outcome.record.rounding_applied == 1
            stack.val_store._conn.execute(
                "UPDATE validation_records SET rounding_output_value = '0.01' "
                "WHERE validation_id = ?", (outcome.record.validation_id,))
            broken = stack.val.read_validation(outcome.record.validation_id)
            assert isinstance(broken, ValidationReadIntegrityFailure)
            assert not hasattr(broken, "record")
        finally:
            stack.close()

    def test_rule_fingerprint_tamper_caught(self, stack):
        outcome, _ = make_validation(stack)
        stack.val_store._conn.execute(
            "UPDATE validation_records SET rule_fingerprint = ? "
            "WHERE validation_id = ?", ("f" * 64, outcome.record.validation_id))
        broken = stack.val.read_validation(outcome.record.validation_id)
        assert isinstance(broken, ValidationReadIntegrityFailure)

    def test_input_pointer_tamper_caught(self, stack):
        outcome, _ = make_validation(stack)
        stack.val_store._conn.execute(
            "UPDATE validation_inputs SET source_field_seq = 99 "
            "WHERE validation_id = ?", (outcome.record.validation_id,))
        broken = stack.val.read_validation(outcome.record.validation_id)
        assert isinstance(broken, ValidationReadIntegrityFailure)

    def test_row_deletion_detected_as_unavailable(self, stack):
        outcome, _ = make_validation(stack)
        stack.val_store._conn.execute(
            "DELETE FROM validation_records WHERE validation_id = ?",
            (outcome.record.validation_id,))
        read = stack.val.read_validation(outcome.record.validation_id)
        assert isinstance(read, ValidationReadRefused)   # gone = refused, not invented


class TestStorageGates:
    def test_unresolved_outcome_is_structurally_impossible(self, stack):
        """UNRESOLVED (D-01: owned by the P5 domain layer) can never be stored —
        the SQL CHECK refuses it even against raw INSERT attempts."""
        outcome, nid = make_validation(stack)
        with pytest.raises(Exception):
            stack.val_store._conn.execute(
                """INSERT INTO validation_records (
                       validation_id, normalization_id, extraction_id, document_id,
                       capture_id, capture_s1, capture_s1_algorithm_id, ruleset_id,
                       ruleset_version, rule_id, rule_version, rule_kind, rule_type,
                       rule_fingerprint, rule_fingerprint_algorithm_id, outcome,
                       outcome_reason, outcome_detail, rounding_applied,
                       rounding_precision, rounding_mode, rounding_input_value,
                       rounding_output_value, input_count, created_at,
                       record_fingerprint, fingerprint_algorithm_id)
                   SELECT validation_id, normalization_id, extraction_id, document_id,
                       capture_id, capture_s1, capture_s1_algorithm_id, ruleset_id,
                       ruleset_version, rule_id, rule_version, rule_kind, rule_type,
                       rule_fingerprint, rule_fingerprint_algorithm_id, 'UNRESOLVED',
                       outcome_reason, outcome_detail, rounding_applied,
                       rounding_precision, rounding_mode, rounding_input_value,
                       rounding_output_value, input_count, created_at,
                       record_fingerprint, fingerprint_algorithm_id
                   FROM validation_records WHERE validation_id = ?""",
                (outcome.record.validation_id,))

    def test_r1_record_with_rounding_is_structurally_impossible(self, stack):
        outcome, _ = make_validation(stack)
        with pytest.raises(Exception):
            stack.val_store._conn.execute(
                "UPDATE validation_records SET rounding_applied = 1, "
                "rounding_precision = 2, rounding_mode = 'HALF_UP', "
                "rounding_input_value = '1', rounding_output_value = '1.00' "
                "WHERE validation_id = ?", (outcome.record.validation_id,))

    def test_partial_rounding_record_is_structurally_impossible(self, make_stack):
        from val_helpers import PAGE_OK, R_ROUNDED
        stack = make_stack()
        try:
            nid = stack.build_derive_validate_ready(PAGE_OK)
            # a rounded-MATCH record carries the full audit record
            outcome = stack.val.validate(nid, R_ROUNDED, "1")
            assert type(outcome).__name__ == "ValidationCompleted"
            # tamper rounding fields into a partial state via a raw copy with
            # rounding_applied=1 but NULL output — the CHECK refuses
            with pytest.raises(Exception):
                stack.val_store._conn.execute(
                    """INSERT INTO validation_records (
                           validation_id, normalization_id, extraction_id,
                           document_id, capture_id, capture_s1,
                           capture_s1_algorithm_id, ruleset_id, ruleset_version,
                           rule_id, rule_version, rule_kind, rule_type,
                           rule_fingerprint, rule_fingerprint_algorithm_id,
                           outcome, outcome_reason, outcome_detail,
                           rounding_applied, rounding_precision, rounding_mode,
                           rounding_input_value, rounding_output_value,
                           input_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id)
                       SELECT validation_id || 'x', normalization_id, extraction_id,
                           document_id, capture_id, capture_s1,
                           capture_s1_algorithm_id, ruleset_id, ruleset_version,
                           rule_id, rule_version, rule_kind, rule_type,
                           rule_fingerprint, rule_fingerprint_algorithm_id,
                           outcome, outcome_reason, outcome_detail,
                           1, rounding_precision, rounding_mode,
                           rounding_input_value, NULL,
                           input_count, created_at, record_fingerprint,
                           fingerprint_algorithm_id
                       FROM validation_records WHERE validation_id = ?""",
                    (outcome.record.validation_id,))
        finally:
            stack.close()

    def test_bad_rule_kind_is_structurally_impossible(self, stack):
        outcome, _ = make_validation(stack)
        with pytest.raises(Exception):
            stack.val_store._conn.execute(
                "UPDATE validation_records SET rule_kind = 'R3' "
                "WHERE validation_id = ?", (outcome.record.validation_id,))

    def test_vocabulary_sweep_over_durable_rows(self, stack):
        make_validation(stack)                                   # VALID
        nid2 = stack.build_extract_normalize(PAGE_MISSING_TAX)   # different content
        stack.val.validate(nid2, R_CONSIST, "1")                 # DEFERRED
        rows = stack.val_store._conn.execute(
            "SELECT outcome, COUNT(*) AS n FROM validation_records "
            "GROUP BY outcome").fetchall()
        assert {r["outcome"] for r in rows} <= {"VALID", "INVALID", "DEFERRED"}
        assert not stack.val_store._conn.execute(
            "SELECT COUNT(*) AS n FROM validation_records "
            "WHERE outcome = 'UNRESOLVED'").fetchone()["n"]
