"""WP-11.1 holoo_spike — READ-ONLY enforcement ladder (SPEC §6/§12).

L1 engine refusal through the production connection factory; L2 query_only
evidence; L3 guard refusals for every mutating statement class; L4 structural
AST probes + import allowlist + contamination sweep; vocabulary sweep."""
import ast
import sqlite3
import sys
from pathlib import Path

import pytest

from holoo_spike import (
    ROLE_CUSTOMER,
    ROLE_OTHER,
    HolooSelection,
    MappingRefused,
    ReadOnlyViolation,
    assert_read_only_sql,
    build_report,
    open_source,
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent      # holoo_spike/


def _package_files():
    return sorted(PACKAGE_ROOT.glob("*.py"))


# ---------------------------------------------------------------------------
# L1 — the ENGINE refuses writes through the production factory connection
# ---------------------------------------------------------------------------


def test_engine_refuses_insert_update_delete_create(source_db, declared_mapping,
                                                    s1):
    # the factory is the SAME one the service uses — not a test-only shortcut
    report = build_report(source_db, declared_mapping,
                          source_label="synthetic", s1=s1)  # sanity: spike works
    assert report.query_only_readback == 1
    conn = open_source(source_db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('INSERT INTO "Customers" VALUES (9, \'x\', NULL)')
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('UPDATE "Customers" SET Phone = \'x\' WHERE CustomerID = 1')
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('DELETE FROM "Customers" WHERE CustomerID = 1')
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('CREATE TABLE "t_evil" (id INTEGER)')
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('DROP TABLE "Customers"')
        # note: PRAGMA set-forms like writable_schema/journal_mode are refused
        # at L3 (the guard) — some are connection-flags or no-ops at the
        # engine level, so they are NOT engine-refusal evidence.
    finally:
        conn.close()


def test_query_only_readback_is_one(source_db):
    conn = open_source(source_db)
    try:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# L3 — the runtime guard refuses every mutating statement class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sql", [
    "INSERT INTO t VALUES (1)",
    "UPDATE t SET a = 1",
    "DELETE FROM t",
    "DROP TABLE t",
    "CREATE TABLE t (id INTEGER)",
    "ALTER TABLE t ADD COLUMN c TEXT",
    "REPLACE INTO t VALUES (1)",
    "VACUUM",
    "ATTACH DATABASE 'x' AS y",
    "DETACH DATABASE y",
    "REINDEX t",
    "PRAGMA journal_mode = DELETE",
    "PRAGMA writable_schema = ON",
    "PRAGMA integrity_check(1); PRAGMA table_list;",
    "SELECT 1; DROP TABLE t",
    "-- sneaky\nDELETE FROM t",
    "/* sneaky */ DELETE FROM t",
    "SELECT * FROM t; DROP TABLE t;",
    "SELECT load_extension('x')",
    "SELECT writefile('x', x'00')",
    "PRAGMA database_list; DROP TABLE t",
    "EXPLAIN DELETE FROM t",
    "WITH x AS (SELECT 1) SELECT * FROM x",
    "",
    "   ",
])
def test_guard_refuses_mutating_or_malformed_sql(sql):
    with pytest.raises(ReadOnlyViolation):
        assert_read_only_sql(sql)


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM t",
    'SELECT "a", "b c" FROM "t x" ORDER BY "a" LIMIT 5',
    "PRAGMA table_list",
    'PRAGMA table_info("t")',
    "PRAGMA query_only",
    "PRAGMA data_version",
    "PRAGMA integrity_check",
    "SELECT 1",                      # trailing form without semicolon
    "SELECT COUNT(*) FROM t;",       # single trailing semicolon allowed
])
def test_guard_allows_known_read_statements(sql):
    assert_read_only_sql(sql)


def test_guard_refusal_is_recorded_not_silent(source_db):
    """A refused statement never reaches the engine — service surfaces it."""
    conn = open_source(source_db)
    audit = []
    try:
        with pytest.raises(ReadOnlyViolation):
            from holoo_spike.store import execute_read_only
            execute_read_only(conn, "DELETE FROM \"Customers\"", audit)
        assert audit == []          # refused BEFORE the audit entry — verbatim
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# L4 — structural AST probes over the production package
# ---------------------------------------------------------------------------


def test_no_mutating_keyword_in_any_string_constant():
    """Every SQL-looking string constant in the package is a READ statement.
    Bare banned tokens as standalone constants are the ban list itself and
    are skipped (definitional literals)."""
    sql_keywords = ("SELECT", "PRAGMA", "INSERT", "UPDATE", "DELETE", "DROP",
                    "ALTER", "CREATE", "REPLACE", "VACUUM", "ATTACH",
                    "DETACH", "REINDEX", "EXPLAIN")
    banned = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "VACUUM",
              "ATTACH", "DETACH", "REINDEX", "WRITABLE_SCHEMA",
              "LOAD_EXTENSION", "READFILE", "WRITEFILE", "EXPLAIN")
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if not value.strip():
                    continue                       # empty string
                if value in banned or value in sql_keywords:
                    continue                       # ban-list literals
                if value == "PRAGMA WRITABLE_SCHEMA":
                    # the guard's own refusal check — a ban definition,
                    # never an executed statement (store.py L3)
                    continue
                first = value.upper().split()[0].strip(".,()[];:*\"'")
                if first not in sql_keywords:
                    continue                       # not SQL — prose/docstring
                tokens = [t.strip(".,()[];:*\"'") for t in
                          value.upper().split()]
                for b in banned:
                    assert b not in tokens, (path.name, b, value[:80])
                # additionally: no string constant may BEGIN with a mutation
                assert first in ("SELECT", "PRAGMA"), \
                    (path.name, first, value[:80])


def test_no_commit_executescript_executemany_calls():
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("commit", "executescript",
                                              "executemany"), \
                    (path.name, node.func.attr)


def test_no_eval_exec_hashlib_random_urandom():
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id not in ("eval", "exec"), path.name
                if isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in ("urandom", "token_bytes"), \
                        path.name
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in getattr(node, "names", [])]
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                for name in names:
                    assert "hashlib" not in name and "random" not in name, \
                        (path.name, name)


def test_import_allowlist_stdlib_and_capture_only():
    stdlib = set(sys.stdlib_module_names)
    allowed_local = {"holoo_spike", "capture"}      # own package + S1 layer
    for path in _package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root in stdlib or root in allowed_local, \
                        (path.name, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue                        # relative import inside package
                if node.module:
                    root = node.module.split(".")[0]
                    assert root in stdlib or root in allowed_local, \
                        (path.name, node.module)


def test_production_package_never_imports_the_fixture_builder():
    """OD-HS-K direction of dependency: tests → production only. The INSERT-
    bearing fixture builder must be unreachable from the package."""
    for path in _package_files():
        source = path.read_text(encoding="utf-8")
        assert "hs_helpers" not in source, path.name
        assert "build_synthetic_holoo_like_db" not in source, path.name


def test_read_only_literals_present():
    """L1/L2 evidence literals exist exactly where they must."""
    store_src = (PACKAGE_ROOT / "store.py").read_text(encoding="utf-8")
    assert "mode=ro" in store_src
    assert "PRAGMA query_only = ON" in store_src
    service_src = (PACKAGE_ROOT / "service.py").read_text(encoding="utf-8")
    assert "mode=ro" not in service_src      # single factory owns the URI


# ---------------------------------------------------------------------------
# Vocabulary sweep — SPEC §3 roles are the ONLY roles; no domain semantics
# ---------------------------------------------------------------------------


def test_role_vocabulary_is_exactly_the_declared_five():
    from holoo_spike import ROLES
    assert set(ROLES) == {
        "INVOICE_CANDIDATE_HEADER", "INVOICE_CANDIDATE_LINES",
        "CUSTOMER_CANDIDATE", "PRODUCT_CANDIDATE", "OTHER"}


def test_unknown_role_is_refused_at_construction():
    with pytest.raises(ValueError):
        HolooSelection(name="x", role="SALE", table="t",
                       columns=("a",), order_by=("a",))


def test_no_domain_semantics_in_public_surface():
    import holoo_spike as hs
    banned = ("SALE", "CANONICAL", "REVIEW", "REJECT", "UNRESOLVED",
              "INVENTORY", "ISSUE", "FUZZY", "CONFIDENCE")
    exported = set(hs.__all__)
    for name in exported:
        for b in banned:
            assert b not in name.upper(), name


def test_selection_objects_carry_no_behavior_beyond_declaration():
    sel = HolooSelection(name="c", role=ROLE_CUSTOMER, table="Customers",
                         columns=("CustomerID",), order_by=("CustomerID",))
    public = {n for n in dir(sel) if not n.startswith("_")}
    assert public == {"name", "role", "table", "columns", "order_by",
                      "max_rows"}


# ---------------------------------------------------------------------------
# Duplicate mapping names — mapping-level defect refuses the whole request
# ---------------------------------------------------------------------------


def test_duplicate_selection_names_refuse_whole_request(source_db, s1):
    sels = [
        HolooSelection(name="dup", role=ROLE_CUSTOMER, table="Customers",
                       columns=("CustomerID",), order_by=("CustomerID",)),
        HolooSelection(name="dup", role=ROLE_OTHER, table="Products",
                       columns=("ProductCode",), order_by=("ProductCode",)),
    ]
    with pytest.raises(MappingRefused):
        build_report(source_db, sels, source_label="x", s1=s1)
