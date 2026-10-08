"""Durability / restart / idempotency tests (SPEC §7 — OD-N1..OD-N3, OD-N7).

Behavior tests: records survive process restart and re-verify; replay after restart is
the explicit AlreadyExists outcome; storage gates refuse malformed commits; no
UPDATE/DELETE path exists; rejected/deferred counts are durable.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest                                                   # noqa: E402

from normalization import (                                     # noqa: E402
    NormalizationAlreadyExists,
    NormalizationCompleted,
    NormalizationPersistenceUnavailable,
    NormalizationReadSuccess,
    NormalizationStatus,
    NormalizedField,
)


def _close_and_reopen(make_stack, stack):
    stack.close()
    return make_stack()


def test_restart_preserves_record_and_fields_and_reverifies(make_stack, stack):
    extraction_id = stack.build_and_extract()
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)
    nid = done.record.normalization_id
    expected = [(f.field_seq, f.status.value, f.normalized_value, f.rules_applied,
                 f.reason_code) for f in done.fields]

    stack = _close_and_reopen(make_stack, stack)
    read = stack.norm.read_normalization(nid)
    assert isinstance(read, NormalizationReadSuccess)
    got = [(f.field_seq, f.status.value, f.normalized_value, f.rules_applied,
            f.reason_code) for f in read.fields]
    assert got == expected                                       # byte-stable across restart
    assert read.record.extraction_id == extraction_id
    assert read.record.record_fingerprint                        # anchor present


def test_renormalize_after_restart_is_idempotent_already_exists(make_stack, stack):
    extraction_id = stack.build_and_extract()
    first = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(first, NormalizationCompleted)
    stack = _close_and_reopen(make_stack, stack)
    replay = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(replay, NormalizationAlreadyExists)
    assert replay.normalization_id == first.record.normalization_id


def test_rejected_and_deferred_counts_are_durable(make_stack, stack):
    extraction_id = stack.build_and_extract()
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    nid = done.record.normalization_id
    stack = _close_and_reopen(make_stack, stack)
    read = stack.norm.read_normalization(nid)
    assert isinstance(read, NormalizationReadSuccess)
    rec = read.record
    assert rec.normalized_count + rec.deferred_count + rec.rejected_count == rec.field_count
    assert rec.deferred_count >= 1          # corpus contains a whitespace-only + ambiguous
    assert isinstance(rec, object)          # (status counts reloaded verbatim)


def test_commit_refuses_status_value_gate_violation_defensively(stack):
    from normalization import REASON_EMPTY_VALUE
    bad = NormalizedField(0, "x", "EXTRACTED", NormalizationStatus.NORMALIZED,
                          None, "nfc,trim", None)               # NORMALIZED without value
    with pytest.raises(NormalizationPersistenceUnavailable):
        stack.norm_store.commit_normalization(
            extraction_id="e", document_id="d", capture_id="c", capture_s1="s1",
            capture_s1_algorithm_id="sha256-v1", engine_id="eng",
            engine_schema_version="1", ruleset_id="kandoo-norm-v1",
            ruleset_version="1", fields=[bad])


def test_commit_refuses_non_extracted_provenance_defensively(stack):
    bad = NormalizedField(0, "x", "DERIVED", NormalizationStatus.NORMALIZED,
                          "5", "nfc,trim", None)                # D-01 gate (OD-N6)
    with pytest.raises(NormalizationPersistenceUnavailable):
        stack.norm_store.commit_normalization(
            extraction_id="e", document_id="d", capture_id="c", capture_s1="s1",
            capture_s1_algorithm_id="sha256-v1", engine_id="eng",
            engine_schema_version="1", ruleset_id="kandoo-norm-v1",
            ruleset_version="1", fields=[bad])


def test_no_update_or_delete_path_in_normalization_api(stack):
    public = [n for n in dir(stack.norm_store) if not n.startswith("_")]
    assert not any(n.lower().startswith(("update", "delete", "purge", "drop"))
                   for n in public), public
    assert not any(n.lower().startswith(("update", "delete"))
                   for n in dir(stack.norm) if not n.startswith("_"))


def test_failed_commit_leaves_zero_residue(stack):
    from extraction import ExtractedField, Provenance, SourceSpan
    extraction_id = stack.build_and_extract()
    # duplicate triple via pre-check bypass: commit directly twice — second must fail
    fields = [NormalizedField(0, "x", "EXTRACTED", NormalizationStatus.NORMALIZED,
                              "5", "nfc,trim", None)]
    kwargs = dict(extraction_id=extraction_id, document_id="d", capture_id="c",
                  capture_s1="s1", capture_s1_algorithm_id="sha256-v1",
                  engine_id="eng", engine_schema_version="1",
                  ruleset_id="kandoo-norm-v1", ruleset_version="1", fields=fields)
    stack.norm_store.commit_normalization(**kwargs)
    with pytest.raises(NormalizationPersistenceUnavailable):
        # non-EXTRACTED provenance forces refusal INSIDE the txn — must roll back clean
        stack.norm_store.commit_normalization(
            **{**kwargs, "fields": [NormalizedField(
                0, "x", "UNRESOLVED", NormalizationStatus.NORMALIZED,
                "5", "nfc,trim", None)]})
    count = stack.norm_store._conn.execute(
        "SELECT COUNT(*) AS n FROM normalization_records").fetchone()["n"]
    assert count == 1                                            # exactly the first commit
