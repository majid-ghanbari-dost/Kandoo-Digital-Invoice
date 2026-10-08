"""Kandoo Reprint & Duplicate Flows Layer — WP-7.2 MVP implementation (the
operational flow layer over WP-7.1's durable identity resolutions).

Every capture artifact that reaches the identity layer gets exactly ONE
durable flow disposition (INV-DF-1:1): the auditable, immutable fact of its
identity journey. The two registered flows:

  Reprint flow  — the SAME capture presented again: WP-7.1's replay
                  recognition (R0) consumed VERBATIM; the existing
                  disposition returns verbatim, read-only; ZERO new rows.
                  A drifted declaration is refused exactly as WP-7.1
                  refuses it (replay-declaration-drift — propagated).
  Duplicate flow — a DIFFERENT capture resolving to the SAME exact S2
                  fingerprint (D-03 definite duplicate): the disposition
                  points at the deterministic original and the WP-7.1
                  observation — ONE document identity, operationally
                  addressable through the durable duplicate register
                  (duplicates_of), never merged, never suppressed.
  First sighting — IDENTITY_ESTABLISHED (S2 established or CAPTURE_SCOPED):
                  a CAPTURE_SCOPED capture is never a duplicate and never
                  guessed into one (D-03: only capture-level deduplication
                  is guaranteed).

Boundary (normative): this layer contains NO identity logic (WP-7.1's
resolve is the ONLY identity engine — consumed, never bypassed), NO
canonicalization decision (P6.1 remains the sole authority —
ACCEPTED/REJECTED/REVIEW/ALREADY_CANONICALIZED are never decided or
annotated here), NO Canonical Assembly / invoice_id handling (P6.2), NO
REVIEW queue operations, NO product/customer matching, NO semantic
resolution of ANY kind, NO upstream execution, and NO change to any frozen
layer P1–P7.1 (purely additive WP). Reprints are recognized read-only — no
event log, no counter, no mutable field (D-03's "one identity, ever"
mirrored at flow level).

Persistence: separate SQLite file (`duplicate-flows.db`), synchronous=FULL,
atomic single-row commit, immutable records (no UPDATE / no DELETE),
deterministic sha256-v1 fingerprints via the project S1 service,
Verify-on-Read with linked re-verification of every WP-7.1 identity fact,
SQL CHECK + UNIQUE gates, tamper detection, restart safety.
"""
from .model import (
    FLOW_OUTCOME_IDENTITY_ESTABLISHED,
    FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
    FLOW_OUTCOME_REPRINT_RECOGNIZED,
    DURABLE_FLOW_OUTCOMES,
    IDENTITY_SCOPE_S2,
    IDENTITY_SCOPE_CAPTURE_SCOPED,
    LINKED_IDENTITY_SCOPES,
    ORIGIN_KANDOO_SALE,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    ORIGINS,
    utc_now_iso,
    FlowDispositionRecord,
    FlowLayerError,
    DispositionNotFound,
    DispositionDuplicate,
    FlowPersistenceUnavailable,
    FlowIdentityEstablished,
    FlowDuplicateRecognized,
    FlowReprintRecognized,
    FlowRequestRefused,
    FlowInputIntegrityFailure,
    FlowStorageUnavailable,
    FlowReadSuccess,
    FlowReadIntegrityFailure,
    FlowReadRefused,
    FlowReadVerificationUnavailable,
)
from .store import (
    FlowDispositionStore,
    canonical_disposition_bytes,
)
from .service import DuplicateFlowService

__all__ = [
    # vocabularies
    "FLOW_OUTCOME_IDENTITY_ESTABLISHED",
    "FLOW_OUTCOME_DUPLICATE_RECOGNIZED",
    "FLOW_OUTCOME_REPRINT_RECOGNIZED",
    "DURABLE_FLOW_OUTCOMES",
    "IDENTITY_SCOPE_S2", "IDENTITY_SCOPE_CAPTURE_SCOPED",
    "LINKED_IDENTITY_SCOPES",
    "ORIGIN_KANDOO_SALE", "ORIGIN_HOLOO_CAPTURE", "ORIGIN_OTHER_POS_CAPTURE",
    "ORIGINS",
    "utc_now_iso",
    # records
    "FlowDispositionRecord",
    # exceptions
    "FlowLayerError", "DispositionNotFound", "DispositionDuplicate",
    "FlowPersistenceUnavailable",
    # handle outcomes
    "FlowIdentityEstablished", "FlowDuplicateRecognized",
    "FlowReprintRecognized", "FlowRequestRefused",
    "FlowInputIntegrityFailure", "FlowStorageUnavailable",
    # read outcomes
    "FlowReadSuccess", "FlowReadIntegrityFailure", "FlowReadRefused",
    "FlowReadVerificationUnavailable",
    # persistence
    "FlowDispositionStore", "canonical_disposition_bytes",
    # service
    "DuplicateFlowService",
]
