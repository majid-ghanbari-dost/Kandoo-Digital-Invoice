"""WP-11.1 holoo_spike — normal read path, discovery, extraction,
determinism (SPEC §12: normal/read path, duplicate/replay, determinism)."""
import json

import pytest

from holoo_spike import (
    MAPPED_OK,
    HolooSpikeReport,
    build_report,
)


def test_report_is_produced_with_correct_shape(source_db, declared_mapping, s1):
    report = build_report(source_db, declared_mapping,
                          source_label="synthetic-holoo-fixture", s1=s1)
    assert isinstance(report, HolooSpikeReport)
    assert report.spec_id == "SPEC-WP111-HDS"
    assert report.spec_version == "1.0-MVP"
    assert report.source_label == "synthetic-holoo-fixture"
    assert report.source_size_bytes == source_db.stat().st_size
    assert report.source_sha256_at_open == report.source_sha256_at_close
    assert len(report.source_sha256_at_open) == 64
    assert report.s1_algorithm_id == "sha256-v1"
    assert report.query_only_readback == 1
    assert report.read_only_uri.endswith("?mode=ro")


def test_schema_discovery_sorted_and_complete(source_db, declared_mapping, s1):
    report = build_report(source_db, declared_mapping,
                          source_label="synthetic", s1=s1)
    names = [t.name for t in report.discovered_tables]
    assert names == sorted(names)
    assert names == ["Archive Notes", "Customers", "InvoiceHead",
                     "InvoiceRows", "Products"]
    # internal sqlite_% objects are counted, never mapped (OD-HS-I)
    assert report.discovered_table_count == 5
    assert report.discovered_internal_object_count >= 1  # sqlite_autoindex_*
    head = next(t for t in report.discovered_tables if t.name == "InvoiceHead")
    cols = [n for n, _ in head.columns]
    assert cols == ["CustomerRef", "InvoiceDate", "InvoiceID", "InvoiceNo",
                    "Note", "TotalAmount"]


def test_all_declared_selections_map_ok(source_db, declared_mapping, s1):
    report = build_report(source_db, declared_mapping,
                          source_label="synthetic", s1=s1)
    statuses = {v["name"]: v["status"] for v in report.mapping_validations}
    assert set(statuses.values()) == {MAPPED_OK}
    assert {e["name"] for e in report.extractions} == set(statuses)


def test_extraction_values_verbatim_and_typed(source_db, declared_mapping, s1):
    report = build_report(source_db, declared_mapping,
                          source_label="synthetic", s1=s1)
    by_name = {e["name"]: e for e in report.extractions}

    heads = by_name["invoice_headers"]
    assert heads["source_row_count"] == 4
    assert heads["extracted_row_count"] == 4
    assert heads["truncated"] is False
    # unicode verbatim + NULL as ["N", None] (SPEC §9)
    row11 = heads["rows"][1]
    assert row11[1] == ["T", "INV-1404-0011"]
    assert row11[5] == ["T", "ضرب‌الاجل فوری"]
    row13 = heads["rows"][3]
    assert row13[3] == ["N", None]

    lines = by_name["invoice_lines"]
    assert lines["source_row_count"] == 7
    # REAL -> ["F", hex string] — exact, byte-stable (SPEC §9)
    assert lines["rows"][0][4] == ["F", (125000.5).hex()]

    products = by_name["products"]
    preview = dict(zip(products["columns"], products["rows"][0]))["Preview"]
    assert preview == ["B", "AP8Q"]  # base64 of x'00FF10'

    notes = by_name["archive_notes"]
    assert notes["rows"][0][1] == ["T", 'quote " inside ']
    assert notes["rows"][1][1] == ["T", "it's a note"]


def test_determinism_two_runs_byte_identical(source_db, declared_mapping, s1):
    a = build_report(source_db, declared_mapping,
                     source_label="synthetic", s1=s1).to_json_bytes()
    b = build_report(source_db, declared_mapping,
                     source_label="synthetic", s1=s1).to_json_bytes()
    assert a == b


def test_report_json_is_canonical_and_parsable(source_db, declared_mapping, s1):
    raw = build_report(source_db, declared_mapping,
                       source_label="synthetic", s1=s1).to_json_bytes()
    text = raw.decode("utf-8")
    assert text.endswith("\n")
    parsed = json.loads(text)
    # sort_keys evidence: top-level keys appear in sorted order
    keys = list(parsed.keys())
    assert keys == sorted(keys)
    assert parsed["spec_id"] == "SPEC-WP111-HDS"


def test_sql_audit_records_every_statement_verbatim(source_db,
                                                    declared_mapping, s1):
    report = build_report(source_db, declared_mapping,
                          source_label="synthetic", s1=s1)
    # 1 query_only + 1 table_list + 5 tables×(table_info) + per-selection
    # (table_info for validation + COUNT + projection) — all recorded
    assert report.sql_statements_used[0] == "PRAGMA query_only"
    assert "PRAGMA table_list" in report.sql_statements_used
    projections = [s for s in report.sql_statements_used
                   if s.startswith("SELECT ") and "COUNT" not in s]
    assert len(projections) == 5
    assert all(s.startswith("SELECT ") for s in report.sql_statements_used
               if s.startswith("SELECT"))
    # identifier quoting is always present
    assert '"InvoiceHead"' in projections[0]
    assert '"Archive Notes"' in report.sql_statements_used[-1] or any(
        '"Archive Notes"' in s for s in projections)


def test_order_by_gives_deterministic_row_order(source_db, declared_mapping,
                                                s1):
    report = build_report(source_db, declared_mapping,
                          source_label="synthetic", s1=s1)
    lines = next(e for e in report.extractions if e["name"] == "invoice_lines")
    row_ids = [row[0][1] for row in lines["rows"]]
    assert row_ids == sorted(row_ids) == [100, 101, 102, 103, 104, 105, 106]


def test_mapping_selections_are_declared_not_discovered(source_db, s1):
    """The mapping connects intent to schema — a subset mapping is fine and
    discovers nothing by itself (SPEC §2.7: no guessed schema)."""
    from holoo_spike import ROLE_CUSTOMER, HolooSelection
    subset = [HolooSelection(
        name="only_customers", role=ROLE_CUSTOMER, table="Customers",
        columns=("CustomerID", "CustomerName"), order_by=("CustomerID",))]
    report = build_report(source_db, subset,
                          source_label="synthetic", s1=s1)
    assert len(report.extractions) == 1
    assert report.extractions[0]["source_row_count"] == 3
    # discovery still reports the WHOLE schema — but nothing is extracted
    # beyond the declaration
    assert report.discovered_table_count == 5


def test_empty_selection_list_is_refused(source_db, s1):
    from holoo_spike import MappingRefused
    with pytest.raises(MappingRefused):
        build_report(source_db, [], source_label="x", s1=s1)
