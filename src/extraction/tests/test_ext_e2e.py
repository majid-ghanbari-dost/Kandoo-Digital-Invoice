"""Extraction E2E tests — full AS-01 middle path across restart + the P3/P4 boundary
sweep (AC-3.1.1..AC-3.1.6 integration view)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from capture import CaptureService  # noqa: E402

from ext_helpers import ExtractionStack, PAGE_TEXTS, StubEngine  # noqa: E402
from extraction import (  # noqa: E402
    ExtractedField,
    ExtractionAlreadyExists,
    ExtractionCompleted,
    ExtractionEngineFailed,
    ExtractionEngineNotRegistered,
    ExtractionReadIntegrityFailure,
    ExtractionReadSuccess,
    ExtractionSourceRefused,
    Provenance,
    ReferenceDelimitedEngine,
    SourceSpan,
)


def test_full_extraction_mvp_journey_across_restart(stack, make_stack):
    # 1) Capture → Reconstruction → COMPLETED document
    capture_id = stack.capture.ingest(
        CaptureService.aggregate(PAGE_TEXTS), source_label="e2e").capture_id
    built = stack.recon.reconstruct(capture_id)
    document_id = built.document.document_id

    # 2) Document/Page → Extraction-ready input → Extracted structured data
    outcome = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(outcome, ExtractionCompleted), outcome
    extraction_id = outcome.extraction.extraction_id
    assert outcome.extraction.capture_s1 == built.document.capture_s1

    # 3) span fidelity — every extracted value slices the SOURCE artifact byte-exactly
    source = CaptureService.aggregate(PAGE_TEXTS)
    spans = stack.recon_store.get_pages(document_id)
    for field in outcome.fields:
        page = spans[field.span.page_index]
        page_bytes = bytes(page.content)
        assert page_bytes[field.span.byte_start:field.span.byte_end].decode(
            field.value_encoding) == field.value_verbatim

    # 4) INV-X-1:1 replay + engine agnosticism (second engine = separate record)
    assert isinstance(stack.extraction.extract(document_id, "reference-delimited-v1"),
                      ExtractionAlreadyExists)
    stack.extraction._engines["stub-alt-v1"] = StubEngine(engine_id="stub-alt-v1", fields=[
        ExtractedField(0, "alt.field",
                       bytes(spans[0].content)[0:3].decode("utf-8"), "utf-8",
                       Provenance.EXTRACTED,
                       SourceSpan(0, 0, 3, spans[0].page_fingerprint))])
    second = stack.extraction.extract(document_id, "stub-alt-v1")
    assert isinstance(second, ExtractionCompleted), second
    ids = stack.extraction.extraction_ids_for_document(document_id)
    assert ids == (extraction_id, second.extraction.extraction_id)

    # 5) restart — everything durable, verified reads stay VALID
    stack.close()
    stack2 = make_stack()
    try:
        for extraction_id_i in ids:
            read = stack2.extraction.read_extraction(extraction_id_i)
            assert isinstance(read, ExtractionReadSuccess), read

        # 6) explicit failure paths — never silent
        assert isinstance(stack2.extraction.extract(document_id, "ghost-engine"),
                          ExtractionEngineNotRegistered)
        bin_doc = stack2.recon.reconstruct(stack2.capture.ingest(
            CaptureService.aggregate([b"x=\xff\xfe"]), source_label="e2e-bin").capture_id)
        bin_document_id = bin_doc.document.document_id
        assert isinstance(stack2.extraction.extract(bin_document_id,
                                                    "reference-delimited-v1"),
                          ExtractionEngineFailed)
        assert isinstance(stack2.extraction.extract("missing-doc",
                                                    "reference-delimited-v1"),
                          ExtractionSourceRefused)

        # 7) tamper an extracted value → verified read fails explicitly (VOR)
        stack2.extraction_store._conn.execute(
            "UPDATE extraction_fields SET value_verbatim = 'MUTATED' "
            "WHERE extraction_id = ?", (extraction_id,))
        broken = stack2.extraction.read_extraction(extraction_id)
        assert isinstance(broken, ExtractionReadIntegrityFailure), broken
        healthy = stack2.extraction.read_extraction(second.extraction.extraction_id)
        assert isinstance(healthy, ExtractionReadSuccess), healthy
    finally:
        stack2.close()


def test_structural_boundary_no_normalization_canonical_or_validation_datum(stack):
    """P3/P4 boundary (AC-3.1.6): the extraction layer's model, store, and stored rows
    carry NO normalization/canonicalization/validation/invoice datum; provenance is
    EXTRACTED-only (D-01 vocabulary reserved, DERIVED/UNRESOLVED never stored here)."""
    document_id = stack.build_document()
    outcome = stack.extraction.extract(document_id, "reference-delimited-v1")
    assert isinstance(outcome, ExtractionCompleted), outcome

    # exact model field sets — nothing extra, nothing normalized/canonical
    from extraction import model as ext_model
    from extraction import store as ext_store
    assert set(ExtractedField.__dataclass_fields__) == {
        "field_seq", "field_name", "value_verbatim", "value_encoding", "provenance",
        "span"}
    assert set(ext_model.SourceSpan.__dataclass_fields__) == {
        "page_index", "byte_start", "byte_end", "page_fingerprint"}
    assert set(ext_model.ExtractionRecord.__dataclass_fields__) == {
        "extraction_id", "document_id", "capture_id", "capture_s1",
        "capture_s1_algorithm_id", "engine_id", "engine_schema_version", "page_count",
        "field_count", "created_at", "record_fingerprint", "fingerprint_algorithm_id"}
    assert set(ext_model.ExtractionInput.__dataclass_fields__) == {
        "document_id", "capture_id", "capture_s1", "capture_s1_algorithm_id",
        "page_count", "pages"}

    # exact store columns — schema carries no downstream datum
    for table, expected in {
        "extraction_records": {
            "extraction_id", "document_id", "capture_id", "capture_s1",
            "capture_s1_algorithm_id", "engine_id", "engine_schema_version",
            "page_count", "field_count", "created_at", "record_fingerprint",
            "fingerprint_algorithm_id"},
        "extraction_fields": {
            "extraction_id", "field_seq", "field_name", "value_verbatim",
            "value_encoding", "provenance", "page_index", "byte_start", "byte_end",
            "page_fingerprint"},
    }.items():
        cols = {r["name"] for r in stack.extraction_store._conn.execute(
            f"PRAGMA table_info({table})").fetchall()}
        assert cols == expected, (table, cols)

    # stored rows: provenance EXTRACTED-only; values verbatim-equal to their spans
    rows = stack.extraction_store._conn.execute(
        "SELECT provenance, COUNT(*) FROM extraction_fields GROUP BY provenance"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("EXTRACTED", outcome.extraction.field_count)]
    # every stored value still decodes byte-exactly from its span (no transformation)
    read = stack.extraction.read_extraction(outcome.extraction.extraction_id)
    assert isinstance(read, ExtractionReadSuccess), read
    pages = {p.page_index: p for p in stack.recon.read_document(document_id).pages}
    for field in read.fields:
        page = pages[field.span.page_index]
        assert bytes(page.content)[field.span.byte_start:field.span.byte_end].decode(
            field.value_encoding) == field.value_verbatim
        assert field.provenance is Provenance.EXTRACTED
