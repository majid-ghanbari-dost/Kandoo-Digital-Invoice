"""End-to-end behavior tests — WP-5.1 (SPEC-WP51-VAL §13).

The full frozen pipeline plus validation, under one composition: Capture →
Reconstruction → Extraction → Evidence Binding → Normalization → Derivation →
R1/R2 Validation → whole-chain trace → restart → tamper.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import (
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
    R_TOLERANCE,
)
from derivation import DerivationCompleted


PAGES_FULL = [
    b"invoice.number=E2E-2026-051\ntotal.net=2500.00\ntax.amount=200.00\n",
    b"seller.name=Kandoo GmbH\nseller.city=Tehran\n",
]


def test_full_pipeline_r1_and_r2_all_green(make_stack):
    from capture import CaptureService
    from extraction import BindingCompleted, ExtractionCompleted
    from normalization import NormalizationCompleted
    from reconstruction import ReconstructCompleted
    stack = make_stack()
    try:
        capture_id = stack.capture.ingest(
            CaptureService.aggregate(PAGES_FULL), source_label="e2e-val").capture_id
        built = stack.recon.reconstruct(capture_id)
        assert isinstance(built, ReconstructCompleted)
        done = stack.extraction.extract(built.document.document_id,
                                        "reference-delimited-v1")
        assert type(done).__name__ == "ExtractionCompleted"
        bound = stack.binder.bind_extraction(done.extraction.extraction_id)
        assert type(bound).__name__ == "BindingCompleted"
        normed = stack.norm.normalize(done.extraction.extraction_id,
                                      "kandoo-norm-v1")
        assert type(normed).__name__ == "NormalizationCompleted"
        nid = normed.record.normalization_id
        derived = stack.deriv.derive(nid, FORMULA, "1")
        assert isinstance(derived, DerivationCompleted)
        assert derived.record.output_value == "2700"

        results = {}
        for rule in (R_PRESENT, R_CONSIST, R_TOLERANCE, R_ROUNDED):
            outcome = stack.val.validate(nid, rule, "1")
            assert isinstance(outcome, ValidationCompleted), outcome
            results[rule] = outcome.record
        assert all(r.outcome == "VALID" for r in results.values())
        assert results[R_TOLERANCE].outcome_reason == "exact-match"
        assert results[R_ROUNDED].rounding_applied == 0

        # every record traces to Capture S1 through its own whole chain
        for record in results.values():
            walk = stack.val.trace_validation(record.validation_id)
            assert isinstance(walk, ValidationTraceSuccess)
        assert len(stack.val.validations_for_normalization(nid)) == 4
    finally:
        stack.close()


def test_e2e_restart_reverify_and_idempotent_replay(make_stack):
    stack = make_stack()
    try:
        nid = stack.build_derive_validate_ready(PAGES_FULL)
        outcome = stack.validate_ok(nid, R_CONSIST)
        validation_id = outcome.record.validation_id
    finally:
        stack.close()

    reopened = make_stack()
    try:
        read = reopened.val.read_validation(validation_id)
        assert isinstance(read, ValidationReadSuccess)
        assert read.record.outcome == "VALID"
        walk = reopened.val.trace_validation(validation_id)
        assert isinstance(walk, ValidationTraceSuccess)
        replay = reopened.val.validate(nid, R_CONSIST, "1")
        assert type(replay).__name__ == "ValidationAlreadyExists"
    finally:
        reopened.close()


def test_e2e_tamper_after_restart_withholds_content(make_stack):
    stack = make_stack()
    try:
        nid = stack.build_derive_validate_ready(PAGES_FULL)
        outcome = stack.validate_ok(nid, R_CONSIST)
        validation_id = outcome.record.validation_id
    finally:
        stack.close()

    reopened = make_stack()
    try:
        reopened.val_store._conn.execute(
            "UPDATE validation_records SET outcome_reason = 'TAMPERED' "
            "WHERE validation_id = ?", (validation_id,))
        from validation import ValidationReadIntegrityFailure
        broken = reopened.val.read_validation(validation_id)
        assert isinstance(broken, ValidationReadIntegrityFailure)
        assert not hasattr(broken, "record")
    finally:
        reopened.close()


def test_e2e_multiple_documents_isolated_scopes(make_stack):
    """Two documents derive and validate independently — no cross-document
    leakage of values or verdicts (single-scope boundary)."""
    stack = make_stack()
    try:
        nid_a = stack.build_derive_validate_ready(
            [b"total.net=100.00\ntax.amount=8\n"], label="e2e-doc-a")
        nid_b = stack.build_derive_validate_ready(
            [b"total.net=200.00\ntax.amount=16\n"], label="e2e-doc-b")
        a = stack.validate_ok(nid_a, R_CONSIST)
        b = stack.validate_ok(nid_b, R_CONSIST)
        assert a.record.outcome == b.record.outcome == "VALID"
        assert a.record.validation_id != b.record.validation_id
        assert a.record.normalization_id == nid_a
        assert b.record.normalization_id == nid_b
        refs_a = {r.source_normalization_id for r in a.inputs}
        refs_b = {r.source_normalization_id for r in b.inputs}
        assert refs_a == {nid_a} and refs_b == {nid_b}
    finally:
        stack.close()
