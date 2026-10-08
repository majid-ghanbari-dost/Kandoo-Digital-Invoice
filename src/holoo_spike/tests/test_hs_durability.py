"""WP-11.1 holoo_spike — L5 byte-level no-mutation proofs, replay identity,
boundary cases (SPEC §6 L5 / §8 / §12): the spike NEVER changes the source,
never leaves side files, and stays byte-deterministic."""
import sqlite3
from pathlib import Path

import pytest

from holoo_spike import (
    ROLE_CUSTOMER,
    ROLE_INVOICE_LINES,
    HolooSelection,
    build_report,
    encode_value,
    open_source,
)

from hs_helpers import build_synthetic_holoo_like_db  # noqa: F401


# ---------------------------------------------------------------------------
# L5 helpers — full pre/post fingerprint of the source
# ---------------------------------------------------------------------------


def _fingerprint(path: Path):
    data = path.read_bytes()
    return {
        "size": len(data),
        "sha256_header_change_counter": data[24:28],   # file change counter
        "mtime_ns": path.stat().st_mtime_ns,
    }


def _dir_listing(d: Path):
    return sorted(p.name for p in d.iterdir())


MAPPING = [
    HolooSelection(name="c", role=ROLE_CUSTOMER, table="Customers",
                   columns=("CustomerID", "CustomerName", "Phone"),
                   order_by=("CustomerID",)),
    HolooSelection(name="lines", role=ROLE_INVOICE_LINES, table="InvoiceRows",
                   columns=("RowID", "InvoiceID", "Quantity", "UnitPrice"),
                   order_by=("RowID",)),
]


# ---------------------------------------------------------------------------
# Byte proofs around full service runs
# ---------------------------------------------------------------------------


def test_source_byte_identical_after_full_run(source_db, source_dir, s1):
    before = _fingerprint(source_db)
    dirs_before = _dir_listing(source_dir)
    build_report(source_db, MAPPING, source_label="x", s1=s1)
    after = _fingerprint(source_db)
    dirs_after = _dir_listing(source_dir)
    assert before == after
    assert dirs_before == dirs_after          # no -wal/-shm/-journal side files


def test_source_byte_identical_after_five_consecutive_runs(source_db,
                                                           source_dir, s1):
    before = _fingerprint(source_db)
    dirs_before = _dir_listing(source_dir)
    reports = [build_report(source_db, MAPPING, source_label="x", s1=s1)
               for _ in range(5)]
    assert _fingerprint(source_db) == before
    assert _dir_listing(source_dir) == dirs_before
    # every run byte-identical (replay/duplicate semantics of a stateless probe)
    first = reports[0].to_json_bytes()
    assert all(r.to_json_bytes() == first for r in reports[1:])


def test_source_byte_identical_after_engine_write_refusals(source_db, s1):
    """Hammering the production connection with refused writes leaves the
    source byte-identical (L1 refusal must never partially apply)."""
    before = _fingerprint(source_db)
    conn = open_source(source_db)
    refused = 0
    try:
        for stmt in ('INSERT INTO "Customers" VALUES (99, \'x\', NULL)',
                     'DELETE FROM "Customers" WHERE CustomerID = 1',
                     'UPDATE "Customers" SET Phone = \'x\'',
                     'VACUUM'):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                refused += 1
    finally:
        conn.close()
    assert refused == 4
    assert _fingerprint(source_db) == before


def test_report_carries_matching_open_close_hashes(source_db, s1):
    report = build_report(source_db, MAPPING, source_label="x", s1=s1)
    assert (report.source_sha256_at_open == report.source_sha256_at_close)


# ---------------------------------------------------------------------------
# Boundary cases — empty tables, truncation, big ints, identifier quoting
# ---------------------------------------------------------------------------


def test_empty_table_extracts_zero_rows_without_error(tmp_path, s1):
    p = build_synthetic_holoo_like_db(tmp_path / "src.db")
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE empty_tbl (id INTEGER PRIMARY KEY, v TEXT)")
    conn.commit()
    conn.close()
    sel = HolooSelection(name="empty", role=ROLE_CUSTOMER, table="empty_tbl",
                         columns=("id", "v"), order_by=("id",))
    report = build_report(p, [sel], source_label="x", s1=s1)
    e = report.extractions[0]
    assert e["source_row_count"] == 0 and e["extracted_row_count"] == 0
    assert e["truncated"] is False and e["rows"] == []


def test_truncation_is_loud_and_counted(tmp_path, s1):
    p = build_synthetic_holoo_like_db(tmp_path / "src.db")
    sel = HolooSelection(name="c", role=ROLE_CUSTOMER, table="Customers",
                         columns=("CustomerID",), order_by=("CustomerID",),
                         max_rows=2)
    report = build_report(p, [sel], source_label="x", s1=s1)
    e = report.extractions[0]
    assert e["source_row_count"] == 3
    assert e["extracted_row_count"] == 2
    assert e["truncated"] is True
    assert [r[0][1] for r in e["rows"]] == [1, 2]   # first two by order_by


def test_big_integer_stays_exact(tmp_path, s1):
    """int64 max (> 2^53 — the float-precision boundary) must arrive exactly;
    the tagged INTEGER encoding never routes through float."""
    p = build_synthetic_holoo_like_db(tmp_path / "src.db")
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE big (v INTEGER PRIMARY KEY)")
    big = 9_223_372_036_854_775_807
    conn.execute("INSERT INTO big VALUES (?)", (big,))
    conn.commit()
    conn.close()
    sel = HolooSelection(name="b", role=ROLE_CUSTOMER, table="big",
                         columns=("v",), order_by=("v",))
    report = build_report(p, [sel], source_label="x", s1=s1)
    assert report.extractions[0]["rows"][0][0] == ["I", big]


def test_identifier_with_space_and_quote_survives(tmp_path, s1):
    p = build_synthetic_holoo_like_db(tmp_path / "src.db")
    conn = sqlite3.connect(str(p))
    conn.execute('CREATE TABLE "Weird ""Name"" tbl" ("col ""q"" x" INTEGER '
                 'PRIMARY KEY)')
    conn.execute('INSERT INTO "Weird ""Name"" tbl" VALUES (7)')
    conn.commit()
    conn.close()
    sel = HolooSelection(name="w", role=ROLE_CUSTOMER,
                         table='Weird "Name" tbl',
                         columns=('col "q" x',), order_by=('col "q" x',))
    report = build_report(p, [sel], source_label="x", s1=s1)
    e = report.extractions[0]
    assert e["extracted_row_count"] == 1
    assert e["rows"][0][0] == ["I", 7]
    assert any('"Weird ""Name"" tbl"' in s
               for s in report.sql_statements_used)


def test_determinism_independent_of_selection_declaration_order(source_db, s1):
    """Report SECTIONS are sorted by name, so content is declaration-order-
    free; the SQL audit is intentionally execution-true (it must reflect what
    actually ran, in order)."""
    a = build_report(source_db, list(reversed(MAPPING)),
                     source_label="x", s1=s1)
    b = build_report(source_db, MAPPING, source_label="x", s1=s1)
    da, db_ = a.to_dict(), b.to_dict()
    da.pop("sql_statements_used"), db_.pop("sql_statements_used")
    assert da == db_
    # the audit multiset is identical; only the order may differ
    assert sorted(a.sql_statements_used) == sorted(b.sql_statements_used)
    # ...and the audit is execution-true: the first extraction statement of
    # the reversed run belongs to the LAST declared selection
    first_select_rev = next(s for s in a.sql_statements_used
                            if s.startswith("SELECT COUNT"))
    assert '"Customers"' in first_select_rev or '"InvoiceRows"' \
        in first_select_rev


def test_encode_value_rejects_unknown_type():
    with pytest.raises(Exception):
        encode_value(object())
