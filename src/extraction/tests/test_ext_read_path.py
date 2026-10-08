"""Verified extraction read tests — VOR pattern on extraction records (SPEC-WP31-EXT §6):
tampered record/field → explicit integrity failure, stored content NEVER delivered."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from ext_helpers import ExtractionStack  # noqa: E402
from extraction import (  # noqa: E402
    ExtractionCompleted,
    ExtractionReadIntegrityFailure,
    ExtractionReadRefused,
    ExtractionReadSuccess,
    ExtractionReadVerificationUnavailable,
)


def _completed(stack):
    document_id = stack.build_document()
    outcome = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(outcome, ExtractionCompleted), outcome
    return document_id, outcome.extraction.extraction_id


def test_healthy_read_delivers_record_and_fields_with_fresh_verdict(stack):
    _, extraction_id = _completed(stack)
    read = stack.extraction.read_extraction(extraction_id)
    assert isinstance(read, ExtractionReadSuccess), read
    assert read.extraction.extraction_id == extraction_id
    assert len(read.fields) == 6
    assert read.verified_at                       # same-read verdict timestamp
    # structural: refusals/failures never carry content
    for outcome_type in (ExtractionReadRefused, ExtractionReadIntegrityFailure,
                         ExtractionReadVerificationUnavailable):
        assert "fields" not in outcome_type.__dataclass_fields__


def test_tampered_field_value_fails_explicitly_and_never_delivers(stack):
    document_id, extraction_id = _completed(stack)
    stack.extraction_store._conn.execute(
        "UPDATE extraction_fields SET value_verbatim = 'INV-TAMPERED' "
        "WHERE extraction_id = ? AND field_seq = 0", (extraction_id,))
    read = stack.extraction.read_extraction(extraction_id)
    assert isinstance(read, ExtractionReadIntegrityFailure), read
    assert read.extraction_id == extraction_id
    assert read.reason == "verify FAILED"
    assert not hasattr(read, "fields")            # broken content is never delivered


def test_tampered_record_scalar_fails_explicitly(stack):
    _, extraction_id = _completed(stack)
    stack.extraction_store._conn.execute(
        "UPDATE extraction_records SET capture_s1 = 'forged-s1' "
        "WHERE extraction_id = ?", (extraction_id,))
    read = stack.extraction.read_extraction(extraction_id)
    assert isinstance(read, ExtractionReadIntegrityFailure), read


def test_deleted_field_row_is_detected_explicitly(stack):
    _, extraction_id = _completed(stack)
    stack.extraction_store._conn.execute(
        "DELETE FROM extraction_fields WHERE extraction_id = ? AND field_seq = 5",
        (extraction_id,))
    read = stack.extraction.read_extraction(extraction_id)
    assert isinstance(read, ExtractionReadVerificationUnavailable), read
    assert "inconsistent" in read.issue_report
    assert stack.extraction.issue_reports()       # Issue-Report surfaced, not silent


def test_unknown_extraction_id_is_refused(stack):
    read = stack.extraction.read_extraction("no-such-extraction")
    assert isinstance(read, ExtractionReadRefused), read
    assert read.extraction_id is None
