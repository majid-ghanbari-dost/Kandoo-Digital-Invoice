"""Holoo DB Spike service — WP-11.1 MVP orchestration.

Binding basis: SPEC-WP111-HDS §1/§5/§6/§8/§10/§11/§13.

The service is the ONLY entry point (`build_report`) and the report is the
ONLY output (D-04: the spike only reports). Flow:

  1. hash the source bytes (capture S1 service — OD-HS-D)      [L5 at_open]
  2. open the source via the read-only-by-construction factory (L1/L2)
  3. read `PRAGMA query_only` back as enforcement evidence
  4. discover the schema (whitelisted read PRAGMAs, sorted)
  5. validate each declared selection against the schema (fail-closed §5)
  6. extract valid selections (exactly two guard-passed statements each)
  7. close; re-hash the source                                  [L5 at_close]
  8. refuse the report on ANY hash mismatch (ReadOnlyViolation)
  9. assemble the deterministic report (no wall-clock time — OD-HS-E)

No value extracted here is stored, projected, canonicalized, or linked:
`HolooSpikeReport` is an in-memory human-facing finding sheet (OD-HS-J).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Sequence

from capture import S1ComputationFailure, S1Service

from . import store
from .model import (
    DiscoveredTable,
    HolooSourceNotSqlite,
    HolooSpikeFailure,
    HolooSourceUnavailable,
    HolooSpikeReport,
    MAPPED_OK,
    MAPPING_REFUSED,
    MappingRefused,
    ReadOnlyViolation,
    SPEC_ID,
    SPEC_VERSION,
    encode_value,
)
from .model import HolooSelection  # noqa: F401  (re-exported typing)


def _sha256_file(path: Path, s1: S1Service) -> str:
    """Whole-file sha256-v1 through the project S1 capability (OD-HS-D)."""
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise HolooSourceUnavailable(f"source unreadable: {exc}") from exc
    try:
        return s1.compute(content).s1
    except S1ComputationFailure as exc:
        raise HolooSpikeFailure(f"source hashing failed: {exc}") from exc


def _validate_selection(selection: HolooSelection,
                        discovered: Sequence[str],
                        conn: sqlite3.Connection,
                        audit: List[str]) -> str | None:
    """SPEC §5 — returns None when MAPPED_OK, else the refusal reason."""
    if selection.table not in discovered:
        return (f"table {selection.table!r} not found in discovered schema "
                f"(discovered: {discovered})")
    actual = set(store.table_column_names(conn, selection.table, audit))
    missing_cols = [c for c in selection.columns if c not in actual]
    missing_order = [c for c in selection.order_by if c not in actual]
    if missing_cols:
        return (f"columns not found in {selection.table!r}: "
                f"{sorted(missing_cols)}")
    if missing_order:
        return (f"order_by columns not found in {selection.table!r}: "
                f"{sorted(missing_order)}")
    return None


def build_report(source_path: Path,
                 selections: Sequence[HolooSelection],
                 source_label: str,
                 s1: S1Service) -> HolooSpikeReport:
    """Execute the READ-ONLY spike and return the report (the only output)."""
    if not selections:
        raise MappingRefused("mapping is empty — nothing declared to inspect")
    names = [sel.name for sel in selections]
    if len(set(names)) != len(names):
        duplicates = sorted({n for n in names if names.count(n) > 1})
        raise MappingRefused(f"duplicate selection names: {duplicates}")

    source_path = Path(source_path)
    sha_open = _sha256_file(source_path, s1)
    size_bytes = source_path.stat().st_size

    conn = store.open_source(source_path)
    audit: List[str] = []
    try:
        # enforcement evidence (L2 read-back)
        qo_rows = store.execute_read_only(conn, "PRAGMA query_only", audit)
        query_only_readback = int(qo_rows[0][0])
        if query_only_readback != 1:
            raise ReadOnlyViolation(
                "query_only readback is not 1 — refusing to proceed")

        table_names, internal_count = store.discover_tables(conn, audit)
        discovered_tables: List[DiscoveredTable] = []
        for tname in table_names:
            cols = store.discover_columns(conn, tname, audit)
            discovered_tables.append(DiscoveredTable(name=tname, columns=cols))

        validations: List[dict] = []
        extractions: List[dict] = []
        for selection in selections:
            reason = _validate_selection(selection, table_names, conn, audit)
            if reason is not None:
                validations.append({
                    "name": selection.name,
                    "role": selection.role,
                    "table": selection.table,
                    "status": MAPPING_REFUSED,
                    "reason": reason,
                })
                continue
            validations.append({
                "name": selection.name,
                "role": selection.role,
                "table": selection.table,
                "status": MAPPED_OK,
                "reason": "",
            })
            source_row_count = store.count_rows(
                conn, selection.table, audit)
            raw_rows = store.project_rows(
                conn, selection.table, selection.columns,
                selection.order_by, selection.max_rows, audit)
            extracted = [
                [encode_value(v) for v in row] for row in raw_rows
            ]
            extractions.append({
                "name": selection.name,
                "role": selection.role,
                "table": selection.table,
                "columns": list(selection.columns),
                "order_by": list(selection.order_by),
                "source_row_count": source_row_count,
                "extracted_row_count": len(extracted),
                "truncated": source_row_count > len(extracted),
                "rows": extracted,
            })
    finally:
        conn.close()

    sha_close = _sha256_file(source_path, s1)
    if sha_close != sha_open:
        raise ReadOnlyViolation(
            "source hash changed between open and close — report refused "
            f"(at_open={sha_open}, at_close={sha_close})")

    return HolooSpikeReport(
        spec_id=SPEC_ID,
        spec_version=SPEC_VERSION,
        source_label=source_label,
        source_size_bytes=size_bytes,
        source_sha256_at_open=sha_open,
        source_sha256_at_close=sha_close,
        s1_algorithm_id=s1.algorithm_id,
        sqlite_version=sqlite3.sqlite_version,
        read_only_uri=store.read_only_uri(source_path),
        query_only_readback=query_only_readback,
        discovered_table_count=len(discovered_tables),
        discovered_internal_object_count=internal_count,
        discovered_tables=tuple(sorted(
            discovered_tables, key=lambda t: t.name)),
        mapping_validations=tuple(sorted(
            validations, key=lambda v: v["name"])),
        extractions=tuple(sorted(extractions, key=lambda e: e["name"])),
        sql_statements_used=tuple(audit),
    )
