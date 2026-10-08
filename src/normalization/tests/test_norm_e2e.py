"""End-to-end WP-4.1 tests — Capture → Reconstruction → Extraction → Binding →
Normalization across restart, with the full machine-checkable provenance walk.

Behavior tests: the normalized output is usable as input to the future Canonicalization
boundary WITHOUT performing canonicalization, and every normalized value walks back to
its source span through the frozen verified reads.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest                                                   # noqa: E402

from capture import CaptureService                              # noqa: E402
from extraction import (                                        # noqa: E402
    BindingReadSuccess,
    ExtractionCompleted,
)
from normalization import (                                     # noqa: E402
    NormalizationAlreadyExists,
    NormalizationCompleted,
    NormalizationReadSuccess,
    NormalizationStatus,
    ReferenceNormalizationRulesV1,
)


def test_full_pipeline_journey_across_restart(make_stack, stack):
    # 1. capture → reconstruct → extract → bind (frozen path)
    extraction_id = stack.build_and_extract()
    bound = stack.binder.bind_extraction(extraction_id)
    nid_done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(nid_done, NormalizationCompleted)
    nid = nid_done.record.normalization_id
    snapshot = [(f.field_seq, f.status.value, f.normalized_value, f.reason_code)
                for f in nid_done.fields]
    stack.close()

    # 2. full restart — every layer reopens from durable storage
    stack = make_stack()
    try:
        nr = stack.norm.read_normalization(nid)
        assert isinstance(nr, NormalizationReadSuccess)
        got = [(f.field_seq, f.status.value, f.normalized_value, f.reason_code)
               for f in nr.fields]
        assert got == snapshot                                  # durable + byte-stable
        br = stack.binder.read_binding(extraction_id)
        assert isinstance(br, BindingReadSuccess)               # binding intact
        # 3. replay after restart → explicit AlreadyExists (idempotency)
        replay = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
        assert isinstance(replay, NormalizationAlreadyExists)
        assert replay.normalization_id == nid
    finally:
        stack.close()


def test_machine_checkable_provenance_walk_normalized_to_capture(stack):
    """normalized field → extraction field → WP-3.2 binding entry → page slice decode
    == value_verbatim → rule re-application reproduces normalized_value; capture_s1
    equality closes the walk to Capture (SPEC §5 traceability)."""
    parts = [b"total.gross=1.234,56\ninvoice.date=2026-10-01\n",
             b"seller.name=Kandoo GmbH\n"]
    extraction_id = stack.build_and_extract(parts)
    bound = stack.binder.bind_extraction(extraction_id)
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)

    ext_read = stack.extraction.read_extraction(extraction_id)
    doc_read = stack.recon.read_document(ext_read.extraction.document_id)
    assert doc_read.capture_s1 == ext_read.extraction.capture_s1
    ext_fields = {f.field_seq: f for f in ext_read.fields}
    ruleset = ReferenceNormalizationRulesV1()

    for nf, entry in zip(done.fields, bound.entries):
        ef = ext_fields[nf.field_seq]
        assert nf.source_field_name == ef.field_name
        # re-applying the declared ruleset to the VERBATIM source reproduces the output
        again = ruleset.normalize_field(ef)
        assert (again.status, again.normalized_value) == (nf.status, nf.normalized_value)
        # the entry's page slice decodes to the verbatim value (span fidelity through P3)
        page = doc_read.pages[entry.page_index]
        slice_value = bytes(page.content)[entry.byte_start:entry.byte_end].decode("utf-8")
        assert slice_value == ef.value_verbatim


def test_normalized_output_is_canonicalization_ready_without_canonicalizing(stack):
    """The downstream boundary receives: stable values + statuses + source pointers +
    upstream linkage — everything EXCEPT canonical identity decisions (non-goal §1)."""
    extraction_id = stack.build_and_extract()
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    rec = done.record
    # engine-independent upstream identification for the Canonicalization Gate:
    assert rec.extraction_id and rec.document_id and rec.capture_id and rec.capture_s1
    assert rec.ruleset_id == "kandoo-norm-v1" and rec.ruleset_version == "1"
    # per-field: name + status + value + pointer + rule version — no product/customer datum
    for f in done.fields:
        assert f.source_field_name and f.status in set(NormalizationStatus)
        assert (f.normalized_value is not None) == (f.status is NormalizationStatus.NORMALIZED)
        assert f.source_provenance == "EXTRACTED"
    # enumeration is deterministic for downstream consumption
    assert stack.norm.normalization_ids_for_extraction(extraction_id) == \
        (rec.normalization_id,)


def test_status_matrix_end_to_end_on_rich_corpus(stack):
    """One pipeline run exercises NORMALIZED (text/number/date), DEFERRED (whitespace-only
    + ambiguous number) — statuses surface explicitly, counts reconcile."""
    extraction_id = stack.build_and_extract()      # PAGE_TEXTS corpus from helpers
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    rec, fields = done.record, done.fields
    by_name = {f.source_field_name: f for f in fields}

    assert by_name["invoice.number"].status is NormalizationStatus.NORMALIZED
    assert by_name["invoice.number"].normalized_value == "INV-2024-001"
    assert by_name["invoice.date"].normalized_value == "2026-10-01"
    assert by_name["total.gross"].normalized_value == "1234.56"
    assert by_name["seller.name"].normalized_value == "Café GmbH"     # NFC applied
    assert by_name["quantity"].status is NormalizationStatus.DEFERRED  # "12,345" ambiguous
    assert by_name["notes"].status is NormalizationStatus.DEFERRED     # whitespace-only
    assert rec.normalized_count == sum(
        1 for f in fields if f.status is NormalizationStatus.NORMALIZED)
    assert rec.deferred_count == sum(
        1 for f in fields if f.status is NormalizationStatus.DEFERRED)
    assert rec.rejected_count == sum(
        1 for f in fields if f.status is NormalizationStatus.REJECTED)
    assert (rec.normalized_count + rec.deferred_count + rec.rejected_count
            == rec.field_count)
