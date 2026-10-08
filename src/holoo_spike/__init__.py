"""holoo_spike — WP-11.1 Holoo DB Spike (READ-ONLY).

Binding basis: SPEC-WP111-HDS v1.0-MVP over REG-WPR Phase Index P11 + FROZEN
D-04 + Mission dispatch «HOLOO INTEGRATION — READ-ONLY SPIKE» (2026-10-08).

A spike instrument, not a pipeline stage: the ONLY output is a deterministic,
provenance-preserving report (D-04: the spike only reports). Read-only is
enforced as a ladder (SPEC §6): engine `mode=ro` (L1), `PRAGMA query_only`
(L2), a runtime SQL read-guard (L3), structural AST probes (L4), and L5
byte-level source-equality proofs. Nothing extracted here ever enters the
Kandoo domain; enrichment/adapters are WP-11.2 territory (PO decision space).
"""
from __future__ import annotations

from .model import (
    DEFAULT_MAX_ROWS,
    MAPPED_OK,
    MAPPING_REFUSED,
    ROLES,
    ROLE_CUSTOMER,
    ROLE_INVOICE_HEADER,
    ROLE_INVOICE_LINES,
    ROLE_OTHER,
    ROLE_PRODUCT,
    SPEC_ID,
    SPEC_VERSION,
    DiscoveredTable,
    HolooSelection,
    HolooSourceNotSqlite,
    HolooSourceUnavailable,
    HolooSpikeFailure,
    HolooSpikeReport,
    MappingRefused,
    ReadOnlyViolation,
    encode_value,
)
from .service import build_report
from .store import (
    assert_read_only_sql,
    open_source,
    quote_identifier,
    read_only_uri,
)

__all__ = [
    "DEFAULT_MAX_ROWS",
    "MAPPED_OK",
    "MAPPING_REFUSED",
    "ROLES",
    "ROLE_CUSTOMER",
    "ROLE_INVOICE_HEADER",
    "ROLE_INVOICE_LINES",
    "ROLE_OTHER",
    "ROLE_PRODUCT",
    "SPEC_ID",
    "SPEC_VERSION",
    "DiscoveredTable",
    "HolooSelection",
    "HolooSourceNotSqlite",
    "HolooSourceUnavailable",
    "HolooSpikeFailure",
    "HolooSpikeReport",
    "MappingRefused",
    "ReadOnlyViolation",
    "encode_value",
    "build_report",
    "assert_read_only_sql",
    "open_source",
    "quote_identifier",
    "read_only_uri",
]
