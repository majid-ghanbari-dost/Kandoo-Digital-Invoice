"""Holoo DB Spike read-only source layer — WP-11.1 MVP implementation.

Binding basis: SPEC-WP111-HDS §2/§4/§6/§7/§8/§13 (OD-HS-A..E, H, I).

READ-ONLY BY CONSTRUCTION. The only connection factory in this package opens
the source through a SQLite `mode=ro` URI (L1 — the engine itself refuses
writes), sets `PRAGMA query_only = ON` (L2), and every service-issued
statement additionally passes a conservative token-level read guard (L3).
There is no write path in this module: no INSERT/UPDATE/DELETE/DDL strings
exist anywhere in it (L4 AST probes prove that structurally), and the L5
byte-level proofs live in the test suite.

The store knows NOTHING about Holoo semantics: it discovers schemas, validates
nothing, decides nothing — it executes guard-passed read statements and
returns plain rows. All meaning is assembled by the service into the report.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, List, Sequence, Tuple
from urllib.parse import quote

from .model import (
    HolooSourceNotSqlite,
    HolooSourceUnavailable,
    ReadOnlyViolation,
)

# OD-HS-C — PRAGMA whitelist, READ forms only (no `=` set form is ever legal
# here; `PRAGMA query_only` read-back is evidence, the SET happened once at
# open as a literal in `_open_connection` below).
_READ_PRAGMAS = frozenset({
    "table_list", "table_info", "index_list", "index_info",
    "foreign_key_list", "database_list", "page_count", "page_size",
    "encoding", "schema_version", "data_version", "user_version",
    "quick_check", "integrity_check", "compile_options", "query_only",
})

# Whole-word ban list inside SELECT statements (L3) — conservative: anything
# not explicitly allowed is refused.
_SELECT_BANNED_TOKENS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
    "VACUUM", "ATTACH", "DETACH", "REINDEX", "INTO", "PRAGMA", "WITH",
    "WRITABLE_SCHEMA", "LOAD_EXTENSION", "READFILE", "WRITEFILE",
})

_SQLITE_INTERNAL_PREFIX = "sqlite_"

_MAX_IDENTIFIER_LEN = 256  # OD-HS-H


# ---------------------------------------------------------------------------
# Identifier safety — SPEC §8 / OD-HS-H
# ---------------------------------------------------------------------------


def quote_identifier(identifier: str) -> str:
    """Double-quote an identifier with internal quote doubling. The identifier
    is never interpolated raw."""
    if not isinstance(identifier, str) or not identifier:
        raise ReadOnlyViolation("identifier must be a non-empty string")
    if "\x00" in identifier:
        raise ReadOnlyViolation("identifier contains NUL — refused")
    if len(identifier) > _MAX_IDENTIFIER_LEN:
        raise ReadOnlyViolation(
            f"identifier exceeds {_MAX_IDENTIFIER_LEN} chars — refused")
    return '"' + identifier.replace('"', '""') + '"'


# ---------------------------------------------------------------------------
# Runtime SQL read-guard — SPEC §6 L3 (fail-closed; allowlist discipline)
# ---------------------------------------------------------------------------


def _tokens(sql: str) -> List[str]:
    """Uppercase word tokens (letters/digits/underscore runs). Comments were
    already refused by the caller, so tokenization is unambiguous here."""
    word = []
    words = []
    for ch in sql:
        if ch.isalnum() or ch == "_":
            word.append(ch)
        else:
            if word:
                words.append("".join(word).upper())
                word = []
    if word:
        words.append("".join(word).upper())
    return words


def assert_read_only_sql(sql: str) -> None:
    """L3 guard. Raises ReadOnlyViolation unless the statement is a single
    SELECT or a whitelisted read-only PRAGMA (OD-HS-C)."""
    if not isinstance(sql, str) or not sql.strip():
        raise ReadOnlyViolation("empty SQL refused")
    stripped = sql.strip()
    if "--" in stripped or "/*" in stripped:
        raise ReadOnlyViolation("SQL comments refused (spike SQL never needs them)")
    # single statement only — one optional trailing semicolon
    body = stripped[:-1].rstrip() if stripped.endswith(";") else stripped
    if ";" in body:
        raise ReadOnlyViolation("multi-statement SQL refused")
    upper = body.upper()
    words = _tokens(body)
    first = words[0] if words else ""
    if first == "SELECT":
        if first == "SELECT" and "PRAGMA" in words:
            raise ReadOnlyViolation("PRAGMA inside SELECT refused")
        for tok in words:
            if tok in _SELECT_BANNED_TOKENS:
                raise ReadOnlyViolation(
                    f"banned token {tok!r} in SELECT — refused")
        if "=" in body or "(" == body[-1]:
            # `(` as last char means an unclosed call — malformed; the `=`
            # check rejects assignment-shaped text; SELECT itself never needs it
            raise ReadOnlyViolation("malformed SELECT refused")
        return
    if first == "PRAGMA":
        # only `PRAGMA <name>` or `PRAGMA <name>(<arg>)` — read forms
        if "=" in upper:
            raise ReadOnlyViolation("PRAGMA set-form refused")
        if upper.startswith("PRAGMA WRITABLE_SCHEMA"):
            raise ReadOnlyViolation("writable_schema refused")
        name = words[1].lower() if len(words) > 1 else ""
        if name not in _READ_PRAGMAS:
            raise ReadOnlyViolation(
                f"PRAGMA {name!r} not in the read whitelist — refused")
        return
    raise ReadOnlyViolation(
        f"statement must start with SELECT or a read-only PRAGMA "
        f"(got {first!r}) — refused")


# ---------------------------------------------------------------------------
# Connection factory — SPEC §6 L1/L2 (OD-HS-B)
# ---------------------------------------------------------------------------


def read_only_uri(path: Path) -> str:
    """mode=ro URI — the engine-level read-only enforcement (L1)."""
    return "file:" + quote(str(path.resolve().as_posix()), safe="/") + "?mode=ro"


def _open_connection(path: Path) -> sqlite3.Connection:
    uri = read_only_uri(path)
    try:
        conn = sqlite3.connect(uri, uri=True, isolation_level=None)
    except sqlite3.Error as exc:
        raise HolooSourceUnavailable(f"cannot open source: {exc}") from exc
    # L2 — one literal set-form at open; the guard never sees set-forms.
    conn.execute("PRAGMA query_only = ON")
    return conn


def open_source(path: Path) -> sqlite3.Connection:
    """THE production connection factory (service + no-mutation proof tests
    share it). Read-only by construction; raises HolooSourceUnavailable for
    missing/directory sources before the engine is ever involved."""
    if not path.exists():
        raise HolooSourceUnavailable(f"source does not exist: {path}")
    if path.is_dir():
        raise HolooSourceUnavailable(f"source is a directory: {path}")
    try:
        with open(path, "rb") as fh:
            header = fh.read(16)
    except OSError as exc:
        raise HolooSourceUnavailable(f"source unreadable: {exc}") from exc
    if not header.startswith(b"SQLite format 3\x00"):
        raise HolooSourceNotSqlite("source is not a SQLite database file")
    return _open_connection(path)


# ---------------------------------------------------------------------------
# Read execution — every statement guard-passed and recorded (SPEC §6/§8)
# ---------------------------------------------------------------------------


def execute_read_only(conn: sqlite3.Connection, sql: str,
                      audit: List[str]) -> List[Tuple[Any, ...]]:
    """Guard (L3) -> execute -> fetch all. The statement is appended to the
    audit list VERBATIM before execution (full auditability)."""
    assert_read_only_sql(sql)
    audit.append(sql)
    try:
        cur = conn.execute(sql)
        rows = cur.fetchall()
    except sqlite3.Error as exc:
        # engine-level refusal (L1/L2) or a genuinely bad statement —
        # surfaced honestly either way
        raise ReadOnlyViolation(f"source refused statement: {exc}") from exc
    return rows


# ---------------------------------------------------------------------------
# Introspection — SPEC §7 (whitelisted read PRAGMAs only; sorted output)
# ---------------------------------------------------------------------------


def discover_tables(conn: sqlite3.Connection,
                    audit: List[str]) -> Tuple[List[str], int]:
    """Returns (sorted user-table names, internal sqlite_% object count)."""
    rows = execute_read_only(conn, "PRAGMA table_list", audit)
    user_names: List[str] = []
    internal_count = 0
    for row in rows:
        # table_list: schema, name, type, ncol, wr, strict
        name = row[1]
        obj_type = row[2]
        if name.startswith(_SQLITE_INTERNAL_PREFIX):
            internal_count += 1
            continue
        if obj_type == "table":
            user_names.append(name)
    return sorted(user_names), internal_count


def discover_columns(conn: sqlite3.Connection, table: str,
                     audit: List[str]) -> Tuple[Tuple[str, str], ...]:
    """table_info projection: ((name, declared_type), ...) sorted by name."""
    sql = "PRAGMA table_info(" + quote_identifier(table) + ")"
    rows = execute_read_only(conn, sql, audit)
    cols = ((str(row[1]), "" if row[2] is None else str(row[2]))
            for row in rows)
    return tuple(sorted(cols))


def table_column_names(conn: sqlite3.Connection, table: str,
                       audit: List[str]) -> List[str]:
    rows = execute_read_only(
        conn, "PRAGMA table_info(" + quote_identifier(table) + ")", audit)
    return [str(row[1]) for row in rows]


# ---------------------------------------------------------------------------
# Extraction — SPEC §8 (exactly two guard-passed statements per selection)
# ---------------------------------------------------------------------------


def count_rows(conn: sqlite3.Connection, table: str,
               audit: List[str]) -> int:
    sql = ("SELECT COUNT(*) FROM " + quote_identifier(table))
    rows = execute_read_only(conn, sql, audit)
    return int(rows[0][0])


def project_rows(conn: sqlite3.Connection, table: str,
                 columns: Sequence[str], order_by: Sequence[str],
                 max_rows: int, audit: List[str]) -> List[Tuple[Any, ...]]:
    col_sql = ", ".join(quote_identifier(c) for c in columns)
    order_sql = ", ".join(quote_identifier(c) for c in order_by)
    sql = (f"SELECT {col_sql} FROM {quote_identifier(table)} "
           f"ORDER BY {order_sql} LIMIT {int(max_rows)}")
    return execute_read_only(conn, sql, audit)
