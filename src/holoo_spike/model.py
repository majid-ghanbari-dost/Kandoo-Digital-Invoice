"""Holoo DB Spike domain model — WP-11.1 READ-ONLY MVP implementation.

Binding basis: SPEC-WP111-HDS v1.0-MVP §3/§5/§9/§10/§11/§13.

This package is a spike instrument, not a pipeline stage (D-04: the spike
only reports). It owns NO domain semantics: the §3 role vocabulary is a set
of report labels declared by the operator; nothing here is a Sale, a
Customer, a Canonical value, or any kind of truth. The report is the only
output and it never enters the Kandoo domain (SPEC §2.6).
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

SPEC_ID = "SPEC-WP111-HDS"
SPEC_VERSION = "1.0-MVP"

# ---------------------------------------------------------------------------
# Vocabulary — SPEC §3 (report-only labels; no domain semantics)
# ---------------------------------------------------------------------------

ROLE_INVOICE_HEADER = "INVOICE_CANDIDATE_HEADER"
ROLE_INVOICE_LINES = "INVOICE_CANDIDATE_LINES"
ROLE_CUSTOMER = "CUSTOMER_CANDIDATE"
ROLE_PRODUCT = "PRODUCT_CANDIDATE"
ROLE_OTHER = "OTHER"

ROLES: Tuple[str, ...] = (
    ROLE_INVOICE_HEADER,
    ROLE_INVOICE_LINES,
    ROLE_CUSTOMER,
    ROLE_PRODUCT,
    ROLE_OTHER,
)

MAPPED_OK = "MAPPED_OK"
MAPPING_REFUSED = "MAPPING_REFUSED"

DEFAULT_MAX_ROWS = 5000  # OD-HS-F

# ---------------------------------------------------------------------------
# Failures — SPEC §11 (fail-closed, honest; nothing swallowed)
# ---------------------------------------------------------------------------


class HolooSpikeFailure(Exception):
    """Base class — every spike failure is explicit and typed."""


class HolooSourceUnavailable(HolooSpikeFailure):
    """Source path missing / directory / unreadable — no report produced."""


class HolooSourceNotSqlite(HolooSpikeFailure):
    """File exists but is not a SQLite database — no report produced."""


class MappingRefused(HolooSpikeFailure):
    """Mapping-level defect (e.g. duplicate selection names) — whole request
    refused, mirroring the project UAC discipline."""


class ReadOnlyViolation(HolooSpikeFailure):
    """A mutating statement was refused by the guard, or the source bytes
    changed between open and close — the read-only ladder refuses to emit a
    clean-looking report over a mutated source."""


# ---------------------------------------------------------------------------
# Declared mapping — SPEC §5
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HolooSelection:
    """One operator-declared inspection intent (fail-closed validation later)."""
    name: str
    role: str
    table: str
    columns: Tuple[str, ...]
    order_by: Tuple[str, ...]
    max_rows: int = DEFAULT_MAX_ROWS

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(
                f"unknown selection role: {self.role!r} (declared set only)")
        if not self.name or not self.table:
            raise ValueError("selection name and table are required")
        if not self.columns:
            raise ValueError(
                f"selection {self.name!r}: at least one column required")
        if not self.order_by:
            raise ValueError(
                f"selection {self.name!r}: order_by is required for "
                "deterministic extraction")
        if self.max_rows < 1:
            raise ValueError(
                f"selection {self.name!r}: max_rows must be >= 1")


# ---------------------------------------------------------------------------
# Discovered schema — SPEC §7
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveredTable:
    name: str
    columns: Tuple[Tuple[str, str], ...]  # ((name, declared_type), ...) sorted


# ---------------------------------------------------------------------------
# Report — SPEC §10 (the ONLY output; deterministic; no wall-clock time)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HolooSpikeReport:
    spec_id: str
    spec_version: str
    source_label: str
    source_size_bytes: int
    source_sha256_at_open: str
    source_sha256_at_close: str
    s1_algorithm_id: str
    sqlite_version: str
    read_only_uri: str
    query_only_readback: int
    discovered_table_count: int
    discovered_internal_object_count: int
    discovered_tables: Tuple[DiscoveredTable, ...]
    mapping_validations: Tuple[Dict[str, str], ...]
    extractions: Tuple[Dict[str, Any], ...]
    sql_statements_used: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic plain-dict projection (sorted keys at serialization)."""
        return {
            "spec_id": self.spec_id,
            "spec_version": self.spec_version,
            "source_label": self.source_label,
            "source_size_bytes": self.source_size_bytes,
            "source_sha256_at_open": self.source_sha256_at_open,
            "source_sha256_at_close": self.source_sha256_at_close,
            "s1_algorithm_id": self.s1_algorithm_id,
            "sqlite_version": self.sqlite_version,
            "read_only_uri": self.read_only_uri,
            "query_only_readback": self.query_only_readback,
            "discovered_table_count": self.discovered_table_count,
            "discovered_internal_object_count":
                self.discovered_internal_object_count,
            "discovered_tables": [
                {"name": t.name,
                 "columns": [{"name": n, "declared_type": ty}
                             for n, ty in t.columns]}
                for t in self.discovered_tables
            ],
            "mapping_validations": [dict(v) for v in self.mapping_validations],
            "extractions": [dict(e) for e in self.extractions],
            "sql_statements_used": list(self.sql_statements_used),
        }

    def to_json_bytes(self) -> bytes:
        """SPEC §10 — canonical JSON: sort_keys, ensure_ascii=False, indent=2,
        trailing newline. Pure function; the package never writes to disk
        (OD-HS-J)."""
        import json
        return (json.dumps(self.to_dict(), sort_keys=True,
                           ensure_ascii=False, indent=2) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Deterministic value encoding — SPEC §9 (byte-stable across runs)
# ---------------------------------------------------------------------------


def encode_value(value: Any) -> List[Any]:
    """SQLite storage class -> tagged pair. No coercion, no inference."""
    if value is None:
        return ["N", None]
    if isinstance(value, int):
        return ["I", value]          # full precision — never through float
    if isinstance(value, float):
        return ["F", value.hex()]    # exact bit-level value, byte-stable
    if isinstance(value, str):
        return ["T", value]          # unicode verbatim
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ["B", base64.b64encode(bytes(value)).decode("ascii")]
    raise ReadOnlyViolation(
        f"refusing unexpected value type {type(value).__name__} "
        "(fail-closed — no guessing)")
