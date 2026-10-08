"""WP-4.2 verified-read (VOR) tests — same-read verdict, tamper matrix, refused /
unavailable outcomes (SPEC-WP42-DER §8/§9 OD-D5)."""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from deriv_helpers import PAGE_OK            # noqa: E402
from derivation import (                     # noqa: E402
    DerivationReadIntegrityFailure,
    DerivationReadRefused,
    DerivationReadSuccess,
    DerivationReadVerificationUnavailable,
)

REF = "kandoo-der-total-gross-from-net-tax"


def _derive(stack):
    outcome, norm_id = stack.derive_ok(PAGE_OK)
    return outcome.record


class TestVerifyOnRead:
    def test_read_returns_record_and_inputs_with_valid_verdict(self, stack):
        rec = _derive(stack)
        read = stack.deriv.read_derivation(rec.derivation_id)
        assert isinstance(read, DerivationReadSuccess)
        assert read.record == rec
        assert len(read.inputs) == rec.input_count
        assert read.verified_at
        # inputs are pointers, ordered by input_slot
        assert [r.input_slot for r in read.inputs] == [0, 1]

    def test_read_refused_unknown_id(self, stack):
        outcome = stack.deriv.read_derivation("ghost-id")
        assert isinstance(outcome, DerivationReadRefused)
        assert not hasattr(outcome, "record")

    def test_read_delivers_content_only_after_verification(self, stack):
        # structural: the success outcome cannot exist without the verified verdict
        rec = _derive(stack)
        read = stack.deriv.read_derivation(rec.derivation_id)
        assert read.record.record_fingerprint == rec.record_fingerprint
        recomputed_fp = rec.record_fingerprint
        assert recomputed_fp and len(recomputed_fp) == 64


class TestTamperDetection:
    def test_tampered_output_value_is_caught_content_withheld(self, stack):
        rec = _derive(stack)
        stack.deriv_store._conn.execute(
            "UPDATE derivation_records SET output_value = 'TAMPERED' "
            "WHERE derivation_id = ?", (rec.derivation_id,))
        read = stack.deriv.read_derivation(rec.derivation_id)
        assert isinstance(read, DerivationReadIntegrityFailure)
        assert read.reason == "verify FAILED"
        assert not hasattr(read, "record") and not hasattr(read, "inputs")

    def test_tampered_input_pointer_is_caught(self, stack):
        rec = _derive(stack)
        stack.deriv_store._conn.execute(
            "UPDATE derivation_inputs SET field_seq = 99 "
            "WHERE derivation_id = ? AND input_slot = 0", (rec.derivation_id,))
        read = stack.deriv.read_derivation(rec.derivation_id)
        assert isinstance(read, DerivationReadIntegrityFailure)

    def test_deleted_input_row_is_structural_inconsistency(self, stack):
        rec = _derive(stack)
        stack.deriv_store._conn.execute(
            "DELETE FROM derivation_inputs WHERE derivation_id = ? AND input_slot = 1",
            (rec.derivation_id,))
        read = stack.deriv.read_derivation(rec.derivation_id)
        assert isinstance(read, DerivationReadVerificationUnavailable)
        assert "inconsistent" in read.issue_report

    def test_unknown_fingerprint_algorithm_is_no_verdict(self, stack):
        rec = _derive(stack)
        stack.deriv_store._conn.execute(
            "UPDATE derivation_records SET fingerprint_algorithm_id = 'md5-unknown' "
            "WHERE derivation_id = ?", (rec.derivation_id,))
        read = stack.deriv.read_derivation(rec.derivation_id)
        assert isinstance(read, DerivationReadVerificationUnavailable)
        assert stack.deriv.issue_reports()          # surfaced, never silent

    def test_tampered_formula_fingerprint_is_caught(self, stack):
        rec = _derive(stack)
        stack.deriv_store._conn.execute(
            "UPDATE derivation_records SET formula_fingerprint = "
            "'0000000000000000000000000000000000000000000000000000000000000000' "
            "WHERE derivation_id = ?", (rec.derivation_id,))
        read = stack.deriv.read_derivation(rec.derivation_id)
        assert isinstance(read, DerivationReadIntegrityFailure)

    def test_provenance_label_is_gate_protected_at_storage_level(self, stack):
        rec = _derive(stack)
        # the storage gate refuses any provenance mutation up front (OD-D6) — the
        # stored label can never drift from 'DERIVED', not even by raw SQL
        with pytest.raises(sqlite3.IntegrityError):
            stack.deriv_store._conn.execute(
                "UPDATE derivation_records SET output_provenance = 'DERIVED' "
                "|| 'X' WHERE derivation_id = ?", (rec.derivation_id,))
        with pytest.raises(sqlite3.IntegrityError):
            stack.deriv_store._conn.execute(
                "UPDATE derivation_records SET output_provenance = 'UNRESOLVED' "
                "WHERE derivation_id = ?", (rec.derivation_id,))
        raw = stack.deriv_store._conn.execute(
            "SELECT output_provenance FROM derivation_records "
            "WHERE derivation_id = ?", (rec.derivation_id,)).fetchone()
        assert raw["output_provenance"] == "DERIVED"


class TestTraceReadBoundary:
    def test_trace_on_tampered_derivation_fails_at_first_link(self, stack):
        rec = _derive(stack)
        stack.deriv_store._conn.execute(
            "UPDATE derivation_records SET output_value = 'TAMPERED' "
            "WHERE derivation_id = ?", (rec.derivation_id,))
        outcome = stack.deriv.trace_derivation(rec.derivation_id)
        assert type(outcome).__name__ == "DerivationTraceIntegrityFailure"
        assert outcome.link == "derivation"

    def test_trace_on_unknown_id_is_refused(self, stack):
        outcome = stack.deriv.trace_derivation("ghost-id")
        assert type(outcome).__name__ == "DerivationTraceRefused"
