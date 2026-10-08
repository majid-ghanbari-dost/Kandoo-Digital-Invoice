"""Verified read path (VOR) tests — tamper detection, explicit outcomes, no silent reads.

Behavior tests: a tampered durable row never delivers content; every outcome is explicit;
integrity failures carry no normalized values.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest                                                   # noqa: E402

from normalization import (                                     # noqa: E402
    NormalizationCompleted,
    NormalizationReadIntegrityFailure,
    NormalizationReadRefused,
    NormalizationReadSuccess,
    NormalizationReadVerificationUnavailable,
)


def _normalize_one(stack):
    extraction_id = stack.build_and_extract()
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted), done
    return done.record.normalization_id


def test_healthy_verified_read_delivers_record_and_fields(stack):
    nid = _normalize_one(stack)
    read = stack.norm.read_normalization(nid)
    assert isinstance(read, NormalizationReadSuccess)
    assert len(read.fields) == read.record.field_count
    assert read.verified_at


def test_tampered_normalized_value_fails_explicitly_and_never_delivers(stack):
    nid = _normalize_one(stack)
    stack.norm_store._conn.execute(
        "UPDATE normalization_fields SET normalized_value = '999.99' "
        "WHERE normalization_id = ? AND field_seq = 0", (nid,))
    read = stack.norm.read_normalization(nid)
    assert isinstance(read, NormalizationReadIntegrityFailure)
    assert not hasattr(read, "fields")                  # broken content withheld
    assert read.reason


def test_tampered_record_scalar_fails_explicitly(stack):
    nid = _normalize_one(stack)
    stack.norm_store._conn.execute(
        "UPDATE normalization_records SET normalized_count = normalized_count + 1 "
        "WHERE normalization_id = ?", (nid,))
    read = stack.norm.read_normalization(nid)
    assert isinstance(read, NormalizationReadIntegrityFailure)


def test_tampered_status_without_value_fails_storage_gates_or_read(stack):
    nid = _normalize_one(stack)
    # flip a NORMALIZED row to DEFERRED while keeping its value → violates the CHECK gate
    import pytest
    with pytest.raises(Exception):
        stack.norm_store._conn.execute(
            "UPDATE normalization_fields SET status = 'DEFERRED' "
            "WHERE normalization_id = ? AND field_seq = 0", (nid,))


def test_deleted_field_row_is_detected_explicitly(stack):
    nid = _normalize_one(stack)
    stack.norm_store._conn.execute(
        "DELETE FROM normalization_fields WHERE normalization_id = ? AND field_seq = 0",
        (nid,))
    read = stack.norm.read_normalization(nid)
    assert isinstance(read, NormalizationReadVerificationUnavailable)
    assert stack.norm.issue_reports(), "issue surfaced — never a silent short read"


def test_unknown_normalization_id_is_refused(stack):
    read = stack.norm.read_normalization("no-such-id")
    assert isinstance(read, NormalizationReadRefused)


def test_unverifiable_fingerprint_algorithm_gives_no_verdict(stack):
    nid = _normalize_one(stack)
    stack.norm_store._conn.execute(
        "UPDATE normalization_records SET fingerprint_algorithm_id = 'unknown-alg' "
        "WHERE normalization_id = ?", (nid,))
    read = stack.norm.read_normalization(nid)
    assert isinstance(read, NormalizationReadVerificationUnavailable)
    assert stack.norm.issue_reports()
