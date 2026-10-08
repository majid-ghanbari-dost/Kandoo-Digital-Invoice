"""Extraction store tests — durability, INV-X-1:1, ordering, provenance gate,
deterministic retrieval (SPEC-WP31-EXT §4; OD-X1..OD-X8)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import sqlite3  # noqa: E402

import pytest  # noqa: E402

from capture import S1Service  # noqa: E402

from ext_helpers import ExtractionStack, PAGE_TEXTS  # noqa: E402
from extraction import (  # noqa: E402
    ExtractedField,
    ExtractionDuplicate,
    ExtractionPersistenceUnavailable,
    ExtractionStore,
    Provenance,
    ReferenceDelimitedEngine,
    SourceSpan,
)

S1 = S1Service()


def _field(seq, name="f", value="v", page=0, start=0, end=1, fp="a" * 64):
    return ExtractedField(
        field_seq=seq, field_name=name, value_verbatim=value, value_encoding="utf-8",
        provenance=Provenance.EXTRACTED,
        span=SourceSpan(page_index=page, byte_start=start, byte_end=end,
                        page_fingerprint=fp))


def test_commit_and_get_roundtrip_carries_full_traceability(tmp_path):
    store = ExtractionStore(tmp_path / "extraction.db", S1)
    fields = [_field(0, "invoice.number", "INV-1", 0, 15, 21, "b" * 64),
              _field(1, "total", "9.99", 1, 3, 7, "c" * 64)]
    record = store.commit_extraction(
        document_id="doc-1", capture_id="cap-1", capture_s1="s1-value",
        capture_s1_algorithm_id="sha256-v1", engine_id="reference-delimited-v1",
        engine_schema_version="1", page_count=2, fields=fields)
    got = store.get_record(record.extraction_id)
    assert got == record
    assert (got.document_id, got.capture_id, got.capture_s1,
            got.capture_s1_algorithm_id) == ("doc-1", "cap-1", "s1-value", "sha256-v1")
    assert (got.engine_id, got.engine_schema_version, got.page_count,
            got.field_count) == ("reference-delimited-v1", "1", 2, 2)
    assert got.record_fingerprint and got.fingerprint_algorithm_id == "sha256-v1"
    rows = store.get_fields(record.extraction_id)
    assert rows == fields
    store.close()


def test_records_are_durable_across_restart(tmp_path):
    db = tmp_path / "extraction.db"
    store = ExtractionStore(db, S1)
    record = store.commit_extraction(
        document_id="doc-1", capture_id="cap-1", capture_s1="s1", capture_s1_algorithm_id="sha256-v1",
        engine_id="e1", engine_schema_version="1", page_count=1,
        fields=[_field(0, "a", "x", 0, 0, 1, "d" * 64)])
    store.close()
    reopened = ExtractionStore(db, S1)
    assert reopened.get_record(record.extraction_id) == record
    assert reopened.get_fields(record.extraction_id) == [_field(0, "a", "x", 0, 0, 1, "d" * 64)]
    reopened.close()


def test_inv_x11_same_triple_commit_raises_duplicate_with_index_backstop(tmp_path):
    store = ExtractionStore(tmp_path / "extraction.db", S1)
    kwargs = dict(document_id="doc-1", capture_id="cap-1", capture_s1="s1",
                  capture_s1_algorithm_id="sha256-v1", engine_id="e1",
                  engine_schema_version="1", page_count=1)
    first = store.commit_extraction(fields=[_field(0)], **kwargs)
    with pytest.raises(ExtractionDuplicate) as excinfo:
        store.commit_extraction(fields=[_field(0, "other")], **kwargs)
    assert excinfo.value.extraction_id == first.extraction_id
    # storage-level backstop exists and is UNIQUE on the triple
    indexes = store._conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' "
        "AND tbl_name='extraction_records'").fetchall()
    assert any("uq_extraction_doc_engine" == r["name"] for r in indexes)
    assert any("UNIQUE" in (r["sql"] or "").upper() and
               "engine_schema_version" in (r["sql"] or "")
               for r in indexes if r["name"] == "uq_extraction_doc_engine")
    store.close()


def test_different_engine_or_schema_version_is_a_separate_record(tmp_path):
    store = ExtractionStore(tmp_path / "extraction.db", S1)
    base = dict(document_id="doc-1", capture_id="cap-1", capture_s1="s1",
                capture_s1_algorithm_id="sha256-v1", page_count=1,
                fields=[_field(0)])
    r1 = store.commit_extraction(engine_id="e1", engine_schema_version="1", **base)
    r2 = store.commit_extraction(engine_id="e2", engine_schema_version="1", **base)
    r3 = store.commit_extraction(engine_id="e1", engine_schema_version="2", **base)
    assert len({r1.extraction_id, r2.extraction_id, r3.extraction_id}) == 3
    ids = store.find_for_document("doc-1")
    assert sorted(ids) == sorted([r1.extraction_id, r2.extraction_id, r3.extraction_id])
    store.close()


def test_fields_are_retrieved_ordered_by_field_seq(tmp_path):
    store = ExtractionStore(tmp_path / "extraction.db", S1)
    shuffled = [_field(2, "c"), _field(0, "a"), _field(1, "b")]
    record = store.commit_extraction(
        document_id="doc-1", capture_id="cap-1", capture_s1="s1",
        capture_s1_algorithm_id="sha256-v1", engine_id="e1",
        engine_schema_version="1", page_count=1, fields=shuffled)
    assert [f.field_seq for f in store.get_fields(record.extraction_id)] == [0, 1, 2]
    store.close()


def test_storage_level_provenance_gate_blocks_non_extracted(tmp_path):
    store = ExtractionStore(tmp_path / "extraction.db", S1)
    record = store.commit_extraction(
        document_id="doc-1", capture_id="cap-1", capture_s1="s1",
        capture_s1_algorithm_id="sha256-v1", engine_id="e1",
        engine_schema_version="1", page_count=1, fields=[_field(0)])
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "INSERT INTO extraction_fields VALUES (?,?,?,?,?,?,?,?,?,?)",
            (record.extraction_id, 9, "x", "y", "utf-8", "DERIVED", 0, 0, 1, "e" * 64))
    store.close()


def test_commit_refuses_non_extracted_provenance_defensively(tmp_path):
    store = ExtractionStore(tmp_path / "extraction.db", S1)
    bad = ExtractedField(
        field_seq=0, field_name="x", value_verbatim="y", value_encoding="utf-8",
        provenance=Provenance.DERIVED,
        span=SourceSpan(0, 0, 1, "f" * 64))
    with pytest.raises(ExtractionPersistenceUnavailable):
        store.commit_extraction(
            document_id="doc-1", capture_id="cap-1", capture_s1="s1",
            capture_s1_algorithm_id="sha256-v1", engine_id="e1",
            engine_schema_version="1", page_count=1, fields=[bad])
    assert store.find_for_document("doc-1") == []
    store.close()


def test_find_by_triple_and_document_enumeration_are_deterministic(tmp_path):
    store = ExtractionStore(tmp_path / "extraction.db", S1)
    assert store.find_by_triple("nope", "e1", "1") is None
    assert store.find_for_document("nope") == []
    base = dict(capture_id="cap-1", capture_s1="s1",
                capture_s1_algorithm_id="sha256-v1", page_count=1,
                fields=[_field(0)])
    r1 = store.commit_extraction(document_id="doc-1", engine_id="e1",
                                 engine_schema_version="1", **base)
    r2 = store.commit_extraction(document_id="doc-1", engine_id="e2",
                                 engine_schema_version="1", **base)
    assert store.find_by_triple("doc-1", "e1", "1") == r1.extraction_id
    assert store.find_by_triple("doc-1", "e2", "1") == r2.extraction_id
    assert store.find_for_document("doc-1") == [r1.extraction_id, r2.extraction_id]
    assert store.find_for_document("doc-1") == store.find_for_document("doc-1")
    store.close()
