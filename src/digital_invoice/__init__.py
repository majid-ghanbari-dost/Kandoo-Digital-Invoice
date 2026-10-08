"""Kandoo Digital Invoice Lifecycle Layer — WP-10.1 MVP (the Digital Invoice
domain, per the frozen AS-03 state-machine specification and the PO mission
dispatch "DIGITAL INVOICE LIFECYCLE — P10").

The layer consumes ONLY the WP-6.2 public surface
(`CanonicalAssemblyService.read_assembled_invoice` +
`CanonicalAssemblyService.trace_assembled_invoice`) — consumed, never
bypassed, never triggered — and attaches ONE durable, append-only,
tamper-evident lifecycle register to each issued Canonical Invoice
(INV-DI-1:1). The frozen lifecycle vocabulary is transferred VERBATIM:

    DRAFT → EXTRACTED → VALIDATED → ISSUED → REVOKED | SUPERSEDED

Every state movement is an EXPLICIT act (mark_extracted / mark_validated /
issue / revoke / supersede) verified against the LIVE P6.2 chain at act
time; the current state is a pure projection of the event chain. NOTHING is
automatic — no automatic issuance, revocation, supersession, or any
content-driven or time-driven transition.

Boundary (normative): NO state outside the frozen six (AS-03 — no state
invention/renaming at WP level; the delegated act vocabulary MARK_EXTRACTED |
MARK_VALIDATED | ISSUE | REVOKE | SUPERSEDE records transitions, it does not
name states), NO backward/skip/terminal-exit transition (DB CHECK-enforced
matrix), NO canonicalization or identity decisions (P6.1/P6.2 own them — the
invoice_id is the D-02 Canonical Identity consumed verbatim; no identifier
is minted here), NO native Sale/Invoice path (AS-02 chain remains
upstream-owned; DEF1 — external capture never creates a Sale), NO customer
semantics (WP-9.1/D-06), NO product semantics (WP-8.1), NO REVIEW operations
(P5.2/P6.1 own their queues), NO presentation/rendering/delivery-channel
surface (WP-10.2 / DEF5 — PO-deferred), NO inventory effect (AD-03), NO
canonical value ever stored (pointer discipline — content is re-read LIVE
through the P6.2 verified read), NO upstream execution, NO identifier
minting beyond bookkeeping uuids (AST-proven).

Persistence: separate SQLite file (digital-invoice.db), synchronous=FULL,
atomic single-row commit, immutable history (no UPDATE / no DELETE),
deterministic sha256-v1 fingerprints via the project S1 service,
Verify-on-Read, tamper detection, restart safety, idempotent behavior.
"""
from .model import (
    ORIGIN_KANDOO_SALE,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    ORIGINS,
    STATE_DRAFT,
    STATE_EXTRACTED,
    STATE_VALIDATED,
    STATE_ISSUED,
    STATE_REVOKED,
    STATE_SUPERSEDED,
    LIFECYCLE_STATES,
    TERMINAL_STATES,
    EVENT_MARK_EXTRACTED,
    EVENT_MARK_VALIDATED,
    EVENT_ISSUE,
    EVENT_REVOKE,
    EVENT_SUPERSEDE,
    EVENT_TYPES,
    TRANSITIONS,
    REFUSE_NO_DIGITAL_INVOICE,
    REFUSE_TRANSITION_UNAVAILABLE,
    REFUSE_MALFORMED,
    REFUSE_SUPERSEDE_CONFLICT,
    REFUSE_SUPERSEDE_SELF,
    REFUSE_REPLACEMENT_NOT_ISSUED,
    NOTE_VERIFY_FAILED,
    is_legal_transition,
    predecessor_of,
    expected_outgoing,
    project_current_state,
    utc_now_iso,
    DigitalInvoiceRecord,
    LifecycleEventRecord,
    DigitalInvoiceLayerError,
    DigitalInvoiceNotFound,
    DigitalInvoiceDuplicate,
    LifecycleEventDuplicate,
    DigitalInvoicePersistenceUnavailable,
    DigitalInvoiceOpened,
    DigitalInvoiceOpenReplay,
    DigitalInvoiceRequestRefused,
    DigitalInvoiceInputIntegrityFailure,
    DigitalInvoiceStorageUnavailable,
    LifecycleAdvanced,
    LifecycleReplay,
    LifecycleRequestRefused,
    LifecycleInputIntegrityFailure,
    LifecycleStorageUnavailable,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceReadIntegrityFailure,
    DigitalInvoiceReadRefused,
    DigitalInvoiceReadVerificationUnavailable,
    DigitalInvoiceTraceSuccess,
    DigitalInvoiceTraceIntegrityFailure,
    DigitalInvoiceTraceRefused,
    DigitalInvoiceTraceVerificationUnavailable,
)
from .store import (
    DigitalInvoiceStore,
    canonical_digital_invoice_bytes,
    canonical_event_bytes,
)
from .service import DigitalInvoiceLifecycleService

__all__ = [
    # frozen vocabularies
    "ORIGIN_KANDOO_SALE", "ORIGIN_HOLOO_CAPTURE", "ORIGIN_OTHER_POS_CAPTURE",
    "ORIGINS",
    "STATE_DRAFT", "STATE_EXTRACTED", "STATE_VALIDATED", "STATE_ISSUED",
    "STATE_REVOKED", "STATE_SUPERSEDED", "LIFECYCLE_STATES",
    "TERMINAL_STATES",
    "EVENT_MARK_EXTRACTED", "EVENT_MARK_VALIDATED", "EVENT_ISSUE",
    "EVENT_REVOKE", "EVENT_SUPERSEDE", "EVENT_TYPES", "TRANSITIONS",
    "REFUSE_NO_DIGITAL_INVOICE", "REFUSE_TRANSITION_UNAVAILABLE",
    "REFUSE_MALFORMED", "REFUSE_SUPERSEDE_CONFLICT", "REFUSE_SUPERSEDE_SELF",
    "REFUSE_REPLACEMENT_NOT_ISSUED", "NOTE_VERIFY_FAILED", "utc_now_iso",
    # matrix helpers (pure functions)
    "is_legal_transition", "predecessor_of", "expected_outgoing",
    "project_current_state",
    # records
    "DigitalInvoiceRecord", "LifecycleEventRecord",
    # exceptions
    "DigitalInvoiceLayerError", "DigitalInvoiceNotFound",
    "DigitalInvoiceDuplicate", "LifecycleEventDuplicate",
    "DigitalInvoicePersistenceUnavailable",
    # open outcomes
    "DigitalInvoiceOpened", "DigitalInvoiceOpenReplay",
    "DigitalInvoiceRequestRefused", "DigitalInvoiceInputIntegrityFailure",
    "DigitalInvoiceStorageUnavailable",
    # lifecycle-act outcomes
    "LifecycleAdvanced", "LifecycleReplay", "LifecycleRequestRefused",
    "LifecycleInputIntegrityFailure", "LifecycleStorageUnavailable",
    # read outcomes
    "DigitalInvoiceReadSuccess", "DigitalInvoiceReadIntegrityFailure",
    "DigitalInvoiceReadRefused", "DigitalInvoiceReadVerificationUnavailable",
    # trace outcomes
    "DigitalInvoiceTraceSuccess", "DigitalInvoiceTraceIntegrityFailure",
    "DigitalInvoiceTraceRefused", "DigitalInvoiceTraceVerificationUnavailable",
    # persistence
    "DigitalInvoiceStore", "canonical_digital_invoice_bytes",
    "canonical_event_bytes",
    # service
    "DigitalInvoiceLifecycleService",
]
