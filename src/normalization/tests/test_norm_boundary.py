"""Structural boundary tests — exact field sets, no canonicalization/business datum,
engine independence, and non-intrusion into the frozen layers (SPEC §1/§5/§9).

Behavior tests: the normalized model carries ONLY the declared structure; no canonical
field names, no identity datum, no raw artifacts/image data; the frozen layers keep
verifying after normalization traffic.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import dataclasses                                              # noqa: E402
import sqlite3                                                  # noqa: E402

from extraction import BindingCompleted, BindingReadSuccess     # noqa: E402
from normalization import (                                     # noqa: E402
    NormalizationCompleted,
    NormalizationReadSuccess,
    NormalizationStatus,
)

# The EXACT declared field sets (SPEC §5) — any addition fails this test.
NORMALIZED_FIELD_FIELDS = {
    "field_seq", "source_field_name", "source_provenance", "status",
    "normalized_value", "rules_applied", "reason_code",
}
NORMALIZATION_RECORD_FIELDS = {
    "normalization_id", "extraction_id", "document_id", "capture_id", "capture_s1",
    "capture_s1_algorithm_id", "engine_id", "engine_schema_version", "ruleset_id",
    "ruleset_version", "field_count", "normalized_count", "deferred_count",
    "rejected_count", "created_at", "record_fingerprint", "fingerprint_algorithm_id",
}

FORBIDDEN_DATUM = ("canonical", "product", "customer", "invoice_id", "sale",
                   "tax_rate", "fuzzy", "match_score")


def test_normalized_field_field_set_is_exact():
    names = {f.name for f in dataclasses.fields(__import__(
        "normalization", fromlist=["NormalizedField"]).NormalizedField)}
    assert names == NORMALIZED_FIELD_FIELDS, names


def test_normalization_record_field_set_is_exact():
    names = {f.name for f in dataclasses.fields(__import__(
        "normalization", fromlist=["NormalizationRecord"]).NormalizationRecord)}
    assert names == NORMALIZATION_RECORD_FIELDS, names


def test_store_schema_carries_no_canonical_or_business_columns(stack):
    cols = []
    for table in ("normalization_records", "normalization_fields"):
        rows = stack.norm_store._conn.execute(f"PRAGMA table_info({table})").fetchall()
        cols += [r["name"] for r in rows]
    for forbidden in FORBIDDEN_DATUM:
        assert not any(forbidden in c.lower() for c in cols), (forbidden, cols)


def test_no_span_or_content_duplication_in_normalized_model(stack):
    """Traceability is by pointer (extraction_id + field_seq) — spans/bytes/pages are
    NOT copied (WP-3.2 binding already anchors them; no artifact/image duplication)."""
    extraction_id = stack.build_and_extract()
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)
    for f in done.fields:
        d = dataclasses.asdict(f)
        assert not any(k in d for k in ("span", "byte_start", "byte_end",
                                        "page_fingerprint", "content", "image"))
        assert f.source_provenance == "EXTRACTED"


def test_storage_provenance_gate_blocks_non_extracted_rows(stack):
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        stack.norm_store._conn.execute(
            """INSERT INTO normalization_fields (normalization_id, field_seq,
                   source_field_name, source_provenance, status, normalized_value,
                   rules_applied, reason_code)
               VALUES ('ghost', 0, 'x', 'DERIVED', 'NORMALIZED', '5', 'nfc,trim', NULL)""")


def test_normalization_leaves_all_frozen_layers_verified(stack):
    """Full provenance chain still intact after normalization traffic (§7 of the dispatch:
    evidence linkage preservation)."""
    from extraction import ExtractionEvidenceBinder  # noqa: F401  (import sanity only)
    extraction_id = stack.build_and_extract()
    bound = stack.binder.bind_extraction(extraction_id)
    assert isinstance(bound, BindingCompleted)
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)

    # 1) binding read still VERIFIES (WP-3.2 guarantees not weakened)
    br = stack.binder.read_binding(extraction_id)
    assert isinstance(br, BindingReadSuccess)
    # 2) extraction read still VERIFIES
    er = stack.extraction.read_extraction(extraction_id)
    assert er.extraction.extraction_id == extraction_id
    # 3) normalized read VERIFIES and its pointer resolves into the extraction
    nr = stack.norm.read_normalization(done.record.normalization_id)
    assert isinstance(nr, NormalizationReadSuccess)
    ext_fields = {f.field_seq: f for f in er.fields}
    for nf in nr.fields:
        assert nf.field_seq in ext_fields
        assert nf.source_field_name == ext_fields[nf.field_seq].field_name


def test_status_vocabulary_is_exactly_the_declared_three():
    assert {s.value for s in NormalizationStatus} == {"NORMALIZED", "DEFERRED", "REJECTED"}
