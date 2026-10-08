"""Service-level tests — orchestration, INV-N-1:1, source outcomes, engine independence.

Behavior tests: total positional mapping, explicit outcomes on every path, zero residue
on refusal, provenance preservation, and determinism of the whole pipeline.
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
    NormalizationRulesetNotRegistered,
    NormalizationSourceIntegrityFailure,
    NormalizationSourceRefused,
    NormalizationSourceUnavailable,
    NormalizationStatus,
    NormalizationStorageUnavailable,
    ReferenceNormalizationRulesV1,
)


def test_happy_path_total_mapping_with_statuses_and_counts(stack):
    extraction_id = stack.build_and_extract()
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted), done
    rec, fields = done.record, done.fields

    ext_read = stack.extraction.read_extraction(extraction_id)
    assert len(fields) == len(ext_read.fields) == rec.field_count      # TOTAL mapping
    for n_f, e_f in zip(fields, ext_read.fields):
        assert n_f.field_seq == e_f.field_seq                          # positional
        assert n_f.source_field_name == e_f.field_name                 # relayed, not mapped
        assert n_f.source_provenance == "EXTRACTED"                    # D-01 relayed

    assert (rec.normalized_count + rec.deferred_count + rec.rejected_count
            == rec.field_count)
    by_status = {f.status for f in fields}
    assert NormalizationStatus.NORMALIZED in by_status
    assert NormalizationStatus.DEFERRED in by_status        # "12,345" quantity → ambiguous
    # traceability copied from the verified extraction record
    assert rec.extraction_id == extraction_id
    assert rec.document_id == ext_read.extraction.document_id
    assert rec.capture_id == ext_read.extraction.capture_id
    assert rec.capture_s1 == ext_read.extraction.capture_s1
    assert rec.ruleset_id == "kandoo-norm-v1" and rec.ruleset_version == "1"


def test_missing_field_is_never_invented(stack):
    parts = [b"seller.name=Solo GmbH\n"]                   # exactly one field
    extraction_id = stack.build_and_extract(parts)
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)
    assert len(done.fields) == 1 and done.record.field_count == 1
    assert done.fields[0].source_field_name == "seller.name"


def test_whitespace_only_field_surfaces_as_deferred_in_pipeline(stack):
    parts = [b"notes=   \n"]
    extraction_id = stack.build_and_extract(parts)
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)
    f = done.fields[0]
    assert f.status is NormalizationStatus.DEFERRED
    assert f.reason_code == "empty-value"
    assert done.record.deferred_count == 1


def test_inv_n11_replay_is_explicit_and_never_second_record(stack):
    extraction_id = stack.build_and_extract()
    first = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(first, NormalizationCompleted)
    replay = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(replay, NormalizationAlreadyExists)
    assert replay.normalization_id == first.record.normalization_id
    assert stack.norm_store.find_for_extraction(extraction_id) == \
        [first.record.normalization_id]                    # exactly one record


def test_different_ruleset_version_is_a_separate_record(stack):
    from normalization import ReferenceNormalizationRulesV1
    stack.norm._rulesets["kandoo-norm-v2"] = \
        ReferenceNormalizationRulesV1(ruleset_id="kandoo-norm-v2", ruleset_version="2")
    extraction_id = stack.build_and_extract()
    first = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    second = stack.norm.normalize(extraction_id, "kandoo-norm-v2")
    assert isinstance(first, NormalizationCompleted) and isinstance(second, NormalizationCompleted)
    assert first.record.normalization_id != second.record.normalization_id
    # same content → same normalized values (rule determinism across versions)
    for a, b in zip(first.fields, second.fields):
        assert a.normalized_value == b.normalized_value


def test_unknown_ruleset_is_explicit_and_persists_nothing(stack):
    extraction_id = stack.build_and_extract()
    out = stack.norm.normalize(extraction_id, "no-such-ruleset")
    assert isinstance(out, NormalizationRulesetNotRegistered)
    assert out.extraction_id == extraction_id
    assert stack.norm_store.find_for_extraction(extraction_id) == []   # zero residue


def test_unknown_extraction_is_refused(stack):
    out = stack.norm.normalize("no-such-extraction", "kandoo-norm-v1")
    assert isinstance(out, NormalizationSourceRefused)


def test_tampered_extraction_fails_closed_and_persists_nothing(stack):
    extraction_id = stack.build_and_extract()
    stack.extraction_store._conn.execute(
        "UPDATE extraction_fields SET value_verbatim = 'TAMPERED' "
        "WHERE extraction_id = ? AND field_seq = 0", (extraction_id,))
    out = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(out, NormalizationSourceIntegrityFailure)
    assert stack.norm_store.find_for_extraction(extraction_id) == []   # zero residue


def test_deleted_extraction_record_is_refused(stack):
    extraction_id = stack.build_and_extract()
    stack.extraction_store._conn.execute(
        "DELETE FROM extraction_fields WHERE extraction_id = ?", (extraction_id,))
    stack.extraction_store._conn.execute(
        "DELETE FROM extraction_records WHERE extraction_id = ?", (extraction_id,))
    out = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(out, NormalizationSourceRefused)


def test_normalization_is_engine_independent(stack):
    """The SAME content extracted by TWO different engines normalizes to the SAME values —
    the normalized representation depends on content + ruleset, never on the engine."""
    extraction_a = stack.build_and_extract(engine_id="reference-delimited-v1")
    document_id = stack.extraction.read_extraction(extraction_a).extraction.document_id
    done_b = stack.extraction.extract(document_id, "stub-alt-v1")
    extraction_b = done_b.extraction.extraction_id

    na = stack.norm.normalize(extraction_a, "kandoo-norm-v1")
    nb = stack.norm.normalize(extraction_b, "kandoo-norm-v1")
    assert isinstance(na, NormalizationCompleted) and isinstance(nb, NormalizationCompleted)
    assert len(na.fields) == len(nb.fields)
    for fa, fb in zip(na.fields, nb.fields):
        assert (fa.source_field_name, fa.status, fa.normalized_value) == \
               (fb.source_field_name, fb.status, fb.normalized_value)


def test_normalized_content_determinism_same_content_two_ruleset_registrations(stack):
    """Content determinism is independent of record identity: the same verified extraction
    normalized under TWO registered ruleset identities with the same declared grammar
    yields IDENTICAL normalized values (identity differs; content does not — SPEC §6).
    (Two captures of byte-identical content are impossible by frozen D-03 — same S1 is
    the same capture — so the same-document/two-rulesets path is the honest probe.)"""
    from normalization import ReferenceNormalizationRulesV1
    stack.norm._rulesets["kandoo-norm-v1-copy"] = \
        ReferenceNormalizationRulesV1(ruleset_id="kandoo-norm-v1-copy",
                                      ruleset_version="1")
    parts = [b"total.gross=129.90\ninvoice.date=2026-10-01\n"]
    extraction_id = stack.build_and_extract(parts)
    n1 = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    n2 = stack.norm.normalize(extraction_id, "kandoo-norm-v1-copy")
    assert isinstance(n1, NormalizationCompleted) and isinstance(n2, NormalizationCompleted)
    assert n1.record.normalization_id != n2.record.normalization_id    # separate records
    for a, b in zip(n1.fields, n2.fields):
        assert a.normalized_value == b.normalized_value                # identical content
        assert a.status == b.status and a.rules_applied == b.rules_applied


def test_issue_report_surface_exists_for_unavailable_source(stack):
    extraction_id = stack.build_and_extract()
    # force a NO_VERDICT path: unknown fingerprint algorithm id on the extraction record
    stack.extraction_store._conn.execute(
        "UPDATE extraction_records SET fingerprint_algorithm_id = 'unknown-alg' "
        "WHERE extraction_id = ?", (extraction_id,))
    out = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(out, NormalizationSourceUnavailable)
    assert stack.norm.issue_reports(), "issue report must be surfaced, never silent"
