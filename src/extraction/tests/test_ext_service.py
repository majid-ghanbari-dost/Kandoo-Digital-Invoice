"""Extraction service tests — the AS-01 middle step: verified Document →
ExtractionInput → engine → validated durable fields (SPEC-WP31-EXT §2–§5)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from extraction.engine import ExtractionEngineError  # noqa: E402

from capture import CaptureService  # noqa: E402

from ext_helpers import (  # noqa: E402
    ExtractionStack,
    StubEngine,
    PAGE_TEXTS,
)
from extraction import (  # noqa: E402
    ExtractedField,
    ExtractionAlreadyExists,
    ExtractionCompleted,
    ExtractionEngineContractViolation,
    ExtractionEngineFailed,
    ExtractionEngineNotRegistered,
    ExtractionSourceIntegrityFailure,
    ExtractionSourceRefused,
    ExtractionStorageUnavailable,
    Provenance,
    ReferenceDelimitedEngine,
    SourceSpan,
)

FP = "a" * 64


def _registered_stack(stack: ExtractionStack, engine) -> ExtractionStack:
    stack.extraction._engines[engine.engine_id] = engine
    return stack


def test_happy_path_extract_completes_with_traceability_and_verbatim_fields(stack):
    capture_id = stack.capture.ingest(
        CaptureService.aggregate(PAGE_TEXTS), source_label="svc").capture_id
    built = stack.recon.reconstruct(capture_id)
    document_id = built.document.document_id

    outcome = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(outcome, ExtractionCompleted), outcome
    record, fields = outcome.extraction, outcome.fields

    # full traceability to Document AND Capture (AC-3.1.1)
    assert record.document_id == document_id
    assert record.capture_id == capture_id
    assert record.capture_s1 == built.document.capture_s1
    assert record.capture_s1_algorithm_id == "sha256-v1"
    assert record.page_count == 3 and record.field_count == 6
    assert [f.field_seq for f in fields] == list(range(6))

    # verbatim span binding (AC-3.1.3) — every value is the decoded span of its page
    pages = {p.page_index: p for p in stack.recon.read_document(document_id).pages}
    for f in fields:
        page = pages[f.span.page_index]
        assert f.span.page_fingerprint == page.page_fingerprint
        assert bytes(page.content)[f.span.byte_start:f.span.byte_end].decode(
            f.value_encoding) == f.value_verbatim
        assert f.provenance is Provenance.EXTRACTED
    assert fields[0].field_name == "invoice.number"      # verbatim, untransformed
    assert fields[0].value_verbatim == "INV-2024-001"


def test_reextract_same_triple_is_idempotent_already_exists_never_second_record(stack):
    document_id = stack.build_document()
    first = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(first, ExtractionCompleted)
    replay = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(replay, ExtractionAlreadyExists), replay
    assert replay.extraction_id == first.extraction.extraction_id
    assert replay.document_id == document_id
    assert replay.engine_id == "reference-delimited-v1"
    assert stack.extraction.extraction_ids_for_document(document_id) == \
        (first.extraction.extraction_id,)


def test_second_engine_same_document_yields_a_separate_record_engine_agnostic(stack):
    document_id = stack.build_document()
    first = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(first, ExtractionCompleted)
    stub = StubEngine(engine_id="stub-alt-v1", fields=[])
    page0 = stack.recon_store.get_pages(document_id)[0]
    real_fp = page0.page_fingerprint
    span_value = bytes(page0.content)[0:5].decode("utf-8")     # verbatim per contract C4
    stub._fields = [ExtractedField(0, "stub.field", span_value, "utf-8",
                                   Provenance.EXTRACTED, SourceSpan(0, 0, 5, real_fp))]
    _registered_stack(stack, stub)
    second = stack.extraction.extract(document_id, "stub-alt-v1")
    assert isinstance(second, ExtractionCompleted), second
    assert second.extraction.extraction_id != first.extraction.extraction_id
    assert second.extraction.engine_id == "stub-alt-v1"
    assert [f.field_name for f in second.fields] == ["stub.field"]
    assert stack.extraction.extraction_ids_for_document(document_id) == (
        first.extraction.extraction_id, second.extraction.extraction_id)


def test_unknown_engine_is_explicit_and_persists_nothing(stack):
    document_id = stack.build_document()
    outcome = stack.extraction.extract(document_id, "no-such-engine")
    assert isinstance(outcome, ExtractionEngineNotRegistered), outcome
    assert outcome.engine_id == "no-such-engine"
    assert stack.extraction.extraction_ids_for_document(document_id) == ()


def test_source_refused_for_unknown_document(stack):
    outcome = stack.extraction.extract("no-such-document", "reference-delimited-v1")
    assert isinstance(outcome, ExtractionSourceRefused), outcome
    assert outcome.document_id is None


def test_source_integrity_failure_on_tampered_document_persists_nothing(stack):
    document_id = stack.build_document()
    page = stack.recon_store.get_pages(document_id)[0]
    stack.recon_store._conn.execute(
        "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = ?",
        (b"tampered=1\n", document_id, page.page_index))
    outcome = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(outcome, ExtractionSourceIntegrityFailure), outcome
    assert outcome.document_id == document_id
    assert stack.extraction.extraction_ids_for_document(document_id) == ()


def test_engine_failure_surfaces_explicitly_and_persists_nothing(stack):
    document_id = stack.build_document(parts=[b"name=\xff\xfe\x90\n"])
    outcome = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(outcome, ExtractionEngineFailed), outcome
    assert outcome.engine_id == "reference-delimited-v1"
    assert "UTF-8" in outcome.detail
    assert stack.extraction.extraction_ids_for_document(document_id) == ()


def test_unexpected_engine_exception_is_surfed_explicitly(stack):
    document_id = stack.build_document()
    boom = StubEngine(engine_id="boom-v1",
                      error=RuntimeError("engine blew up"))
    _registered_stack(stack, boom)
    outcome = stack.extraction.extract(document_id, "boom-v1")
    assert isinstance(outcome, ExtractionEngineFailed), outcome
    assert "engine blew up" in outcome.detail
    assert stack.extraction.extraction_ids_for_document(document_id) == ()


@pytest.mark.parametrize("builder,detail_part", [
    # (a) span out of bounds
    (lambda fp: [ExtractedField(0, "x", "v", "utf-8", Provenance.EXTRACTED,
                                SourceSpan(0, 0, 999, fp))], "out of bounds"),
    # (b) span fingerprint does not match the claimed page
    (lambda fp: [ExtractedField(0, "x", "v", "utf-8", Provenance.EXTRACTED,
                                SourceSpan(0, 0, 1, "b" * 64))], "page_fingerprint"),
    # (c) non-EXTRACTED provenance (DERIVED is never an engine output — D-01)
    (lambda fp: [ExtractedField(0, "x", "v", "utf-8", Provenance.DERIVED,
                                SourceSpan(0, 0, 1, fp))], "EXTRACTED"),
    # (d) value is not the verbatim decoding of its span (transformation attempt — P4 land)
    (lambda fp: [ExtractedField(0, "x", "TRANSFORMED", "utf-8", Provenance.EXTRACTED,
                                SourceSpan(0, 0, 1, fp))], "verbatim"),
    # (e) page_index out of range
    (lambda fp: [ExtractedField(0, "x", "v", "utf-8", Provenance.EXTRACTED,
                                SourceSpan(7, 0, 1, fp))], "out of range"),
    # (f) empty field_name
    (lambda fp: [ExtractedField(0, "", "v", "utf-8", Provenance.EXTRACTED,
                                SourceSpan(0, 0, 1, fp))], "field_name"),
])
def test_engine_contract_violations_fail_closed_before_persistence(
        stack, builder, detail_part):
    document_id = stack.build_document()
    real_fp = stack.recon_store.get_pages(document_id)[0].page_fingerprint
    stub = StubEngine(engine_id="violating-v1", fields=builder(real_fp))
    _registered_stack(stack, stub)
    outcome = stack.extraction.extract(document_id, "violating-v1")
    assert isinstance(outcome, ExtractionEngineContractViolation), outcome
    assert detail_part in outcome.detail
    assert outcome.engine_id == "violating-v1"
    assert stack.extraction.extraction_ids_for_document(document_id) == ()


def test_engine_output_must_not_reference_pages_it_was_not_given(stack):
    document_id = stack.build_document()
    # a valid-shaped field whose span fingerprint belongs to ANOTHER document's page
    forged = [ExtractedField(0, "x", "v", "utf-8", Provenance.EXTRACTED,
                             SourceSpan(0, 0, 1, "c" * 64))]
    stub = StubEngine(engine_id="cross-doc-v1", fields=forged)
    _registered_stack(stack, stub)
    outcome = stack.extraction.extract(document_id, "cross-doc-v1")
    assert isinstance(outcome, ExtractionEngineContractViolation), outcome
    assert "page_fingerprint" in outcome.detail


def test_empty_extraction_result_is_explicit_and_valid(stack):
    document_id = stack.build_document(parts=[b"no key sign here\njust text\n"])
    outcome = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(outcome, ExtractionCompleted), outcome
    assert outcome.extraction.field_count == 0 and outcome.fields == ()
    read = stack.extraction.read_extraction(outcome.extraction.extraction_id)
    assert read.extraction.field_count == 0 and read.fields == ()


def test_service_takes_no_capture_access_and_no_raw_artifact_path(stack):
    """Rule 8 structural guard: the service is wired ONLY to the verified read —
    no capture service, no derive_pages, no raw-artifact re-interpretation."""
    import inspect
    from extraction import ExtractionService as Svc
    params = inspect.signature(Svc.__init__).parameters
    assert list(params) == ["self", "store", "reconstruction", "engines", "s1"]
    src = inspect.getsource(Svc)
    assert "read_document" in src                      # the only sanctioned input path
    assert "read_evidence" not in src                  # capture-layer path forbidden
    assert "derive_pages" not in src                   # parallel re-derivation forbidden
