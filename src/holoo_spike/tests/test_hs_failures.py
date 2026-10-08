"""WP-11.1 holoo_spike — fail-closed inputs (SPEC §11/§12): unavailable
source, non-SQLite source, invalid mappings, refusal honesty."""
import pytest

from holoo_spike import (
    MAPPING_REFUSED,
    ROLE_CUSTOMER,
    ROLE_OTHER,
    HolooSelection,
    HolooSourceNotSqlite,
    HolooSourceUnavailable,
    build_report,
)


def _one(name="c", table="Customers", columns=("CustomerID",),
         order_by=("CustomerID",)):
    return HolooSelection(name=name, role=ROLE_CUSTOMER, table=table,
                          columns=columns, order_by=order_by)


# ---------------------------------------------------------------------------
# Unavailable / malformed sources — hard failures, NO report
# ---------------------------------------------------------------------------


def test_missing_file_is_hard_failure(tmp_path, s1):
    with pytest.raises(HolooSourceUnavailable):
        build_report(tmp_path / "missing.db", [_one()],
                     source_label="x", s1=s1)


def test_directory_source_is_hard_failure(tmp_path, s1):
    with pytest.raises(HolooSourceUnavailable):
        build_report(tmp_path, [_one()], source_label="x", s1=s1)


def test_non_sqlite_bytes_are_hard_failure(tmp_path, s1):
    bogus = tmp_path / "bogus.db"
    bogus.write_bytes(b"this is definitely not a sqlite database" * 10)
    with pytest.raises(HolooSourceNotSqlite):
        build_report(bogus, [_one()], source_label="x", s1=s1)


def test_empty_file_is_hard_failure(tmp_path, s1):
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    with pytest.raises(HolooSourceNotSqlite):
        build_report(empty, [_one()], source_label="x", s1=s1)


def test_sqlite_file_without_declared_tables_records_refusals(tmp_path, s1):
    """A valid SQLite file that simply does not match the declared mapping is
    an honest FINDING in the report — refusals recorded, zero fabricated rows,
    source untouched."""
    import sqlite3
    other = tmp_path / "unrelated.db"
    conn = sqlite3.connect(str(other))
    conn.execute("CREATE TABLE totally_unrelated (a INTEGER)")
    conn.commit()
    conn.close()
    report = build_report(other, [_one(), _one(name="p", table="Products")],
                          source_label="x", s1=s1)
    assert report.discovered_tables[0].name == "totally_unrelated"
    statuses = {v["name"]: v for v in report.mapping_validations}
    assert statuses["c"]["status"] == MAPPING_REFUSED
    assert "not found in discovered schema" in statuses["c"]["reason"]
    assert "totally_unrelated" in statuses["c"]["reason"]
    assert report.extractions == ()
    assert report.source_sha256_at_open == report.source_sha256_at_close


# ---------------------------------------------------------------------------
# Invalid mappings — per-selection refusal with precise reasons
# ---------------------------------------------------------------------------


def test_unknown_table_is_refused_with_discovered_list(source_db, s1):
    report = build_report(source_db, [_one(table="Not_A_Table")],
                          source_label="x", s1=s1)
    v = report.mapping_validations[0]
    assert v["status"] == MAPPING_REFUSED
    assert "'Not_A_Table'" in v["reason"]


def test_unknown_column_is_refused(source_db, s1):
    report = build_report(
        source_db,
        [_one(columns=("CustomerID", "NoSuchCol"))],
        source_label="x", s1=s1)
    v = report.mapping_validations[0]
    assert v["status"] == MAPPING_REFUSED
    assert "NoSuchCol" in v["reason"]
    assert report.extractions == ()


def test_missing_order_by_refused_at_construction():
    with pytest.raises(ValueError):
        HolooSelection(name="c", role=ROLE_CUSTOMER, table="Customers",
                       columns=("CustomerID",), order_by=())


def test_order_by_unknown_column_refused(source_db, s1):
    report = build_report(
        source_db,
        [_one(order_by=("NoSuchCol",))],
        source_label="x", s1=s1)
    v = report.mapping_validations[0]
    assert v["status"] == MAPPING_REFUSED
    assert "order_by" in v["reason"]


def test_case_is_not_guessed(source_db, s1):
    """SQLite identifiers are case-insensitive to the ENGINE, but the mapping
    is validated verbatim against discovered names — no silent case-folding
    (SPEC §2.7 fail-closed discipline)."""
    report = build_report(source_db, [_one(table="customers")],
                          source_label="x", s1=s1)
    v = report.mapping_validations[0]
    assert v["status"] == MAPPING_REFUSED
    assert "customers" in v["reason"]


def test_refused_selections_contribute_no_rows_and_others_continue(
        source_db, s1):
    sels = [
        _one(name="bad", table="Ghost"),
        _one(name="good"),
        HolooSelection(name="other", role=ROLE_OTHER, table="Products",
                       columns=("ProductCode", "Nope"),
                       order_by=("ProductCode",)),
    ]
    report = build_report(source_db, sels, source_label="x", s1=s1)
    names = {v["name"]: v["status"] for v in report.mapping_validations}
    assert names == {"bad": MAPPING_REFUSED, "good": "MAPPED_OK",
                     "other": MAPPING_REFUSED}
    assert [e["name"] for e in report.extractions] == ["good"]
    assert report.extractions[0]["source_row_count"] == 3
