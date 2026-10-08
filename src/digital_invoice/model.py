"""Digital Invoice Lifecycle domain model — WP-10.1 MVP.

Binding basis: SPEC-WP101-DILIFE (all sections; OD-DI-A..K delegated details
declared in model.py / store.py / service.py).

Vocabulary discipline (AS-03/AD-04/CL-1 — verbatim, no paraphrase, no
invention):
  - The lifecycle states are the PO-dispatch frozen vocabulary VERBATIM:
    DRAFT | EXTRACTED | VALIDATED | ISSUED | REVOKED | SUPERSEDED. No state
    is added, renamed, or aliased (AS-03 — no state invention at WP level).
  - The event (act) vocabulary is this WP's delegated act vocabulary
    (OD-DI-C): MARK_EXTRACTED | MARK_VALIDATED | ISSUE | REVOKE | SUPERSEDE
    — act names, not states.
  - Origins are the frozen dispatch set VERBATIM (quoted from the verified
    P6.2 record): KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE.
  - invoice_id is the D-02 Canonical Identity, Kandoo-issued at the P6.1
    Gate and consumed by P6.2 — consumed VERBATIM here. No identifier is
    minted in this layer (uuid4 hex is bookkeeping only — AST-proven).

This module is dataclasses + vocabularies + the transition matrix + the
pure state projection + exceptions + explicit outcome types ONLY — no I/O,
no persistence, no clock, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Frozen vocabularies (verbatim — see module docstring)
# ---------------------------------------------------------------------------

ORIGIN_KANDOO_SALE = "KANDOO_SALE"
ORIGIN_HOLOO_CAPTURE = "HOLOO_CAPTURE"
ORIGIN_OTHER_POS_CAPTURE = "OTHER_POS_CAPTURE"
ORIGINS = (ORIGIN_KANDOO_SALE, ORIGIN_HOLOO_CAPTURE, ORIGIN_OTHER_POS_CAPTURE)

# The frozen lifecycle states (PO dispatch — AS-03 verbatim transfer).
STATE_DRAFT = "DRAFT"
STATE_EXTRACTED = "EXTRACTED"
STATE_VALIDATED = "VALIDATED"
STATE_ISSUED = "ISSUED"
STATE_REVOKED = "REVOKED"
STATE_SUPERSEDED = "SUPERSEDED"
LIFECYCLE_STATES = (STATE_DRAFT, STATE_EXTRACTED, STATE_VALIDATED,
                    STATE_ISSUED, STATE_REVOKED, STATE_SUPERSEDED)
TERMINAL_STATES = (STATE_REVOKED, STATE_SUPERSEDED)

# The delegated lifecycle act vocabulary (OD-DI-C — event types, not states).
EVENT_MARK_EXTRACTED = "MARK_EXTRACTED"
EVENT_MARK_VALIDATED = "MARK_VALIDATED"
EVENT_ISSUE = "ISSUE"
EVENT_REVOKE = "REVOKE"
EVENT_SUPERSEDE = "SUPERSEDE"
EVENT_TYPES = (EVENT_MARK_EXTRACTED, EVENT_MARK_VALIDATED, EVENT_ISSUE,
               EVENT_REVOKE, EVENT_SUPERSEDE)

# Stable reason codes (SPEC §4/§5 — every refusal/explicit state anchored)
REFUSE_NO_DIGITAL_INVOICE = "no-digital-invoice"
REFUSE_TRANSITION_UNAVAILABLE = "lifecycle-transition-unavailable"
REFUSE_MALFORMED = "declaration-malformed"
REFUSE_SUPERSEDE_CONFLICT = "supersede-replacement-conflict"
REFUSE_SUPERSEDE_SELF = "supersede-target-is-self"
REFUSE_REPLACEMENT_NOT_ISSUED = "supersede-replacement-not-issued"

# Verify-on-Read failure note (same vocabulary as the other layers)
NOTE_VERIFY_FAILED = "verify FAILED"


def utc_now_iso() -> str:
    """Single layer clock (OD-DI4) — UTC ISO-8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# The transition matrix (SPEC §5.2 — OD-DI-D) + the pure state projection
# ---------------------------------------------------------------------------

# (event_type, from_state, to_state) — exactly five legal transitions; each
# state has exactly one legal predecessor; terminal states have no outgoing
# transition. The DB CHECKs encode this matrix; the service mirrors it.
TRANSITIONS: Tuple[Tuple[str, str, str], ...] = (
    (EVENT_MARK_EXTRACTED, STATE_DRAFT, STATE_EXTRACTED),
    (EVENT_MARK_VALIDATED, STATE_EXTRACTED, STATE_VALIDATED),
    (EVENT_ISSUE, STATE_VALIDATED, STATE_ISSUED),
    (EVENT_REVOKE, STATE_ISSUED, STATE_REVOKED),
    (EVENT_SUPERSEDE, STATE_ISSUED, STATE_SUPERSEDED),
)

_LEGAL = set(TRANSITIONS)
_PREDECESSOR = {to: frm for _, frm, to in TRANSITIONS}
_OUTGOING = {frm: (evt, to) for evt, frm, to in TRANSITIONS}


def is_legal_transition(event_type: str, from_state: str,
                        to_state: str) -> bool:
    """True iff (event_type, from_state, to_state) is inside the matrix."""
    return (event_type, from_state, to_state) in _LEGAL


def predecessor_of(state: str) -> Optional[str]:
    """The unique legal predecessor of a non-DRAFT state (None for DRAFT /
    unreachable inputs)."""
    return _PREDECESSOR.get(state)


def expected_outgoing(state: str) -> Optional[Tuple[str, str]]:
    """The unique (event_type, to_state) leaving a non-terminal state
    (None for terminal states / unreachable inputs)."""
    return _OUTGOING.get(state)


def project_current_state(events: Tuple["LifecycleEventRecord", ...]) -> str:
    """The current lifecycle state as a PURE function of the event chain
    (SPEC §5.5): DRAFT with zero events; otherwise the last event's
    to_state in per-invoice seq order. The caller (store/service) guarantees
    the chain is integrity-checked BEFORE projection is served."""
    if not events:
        return STATE_DRAFT
    return max(events, key=lambda e: e.event_seq).to_state


# ---------------------------------------------------------------------------
# Durable records — exact field sets (structurally enforced by boundary tests)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DigitalInvoiceRecord:
    """The immutable creation row (SPEC §7; INV-DI-1:1 — at most ONE per
    invoice_id). invoice_id is the D-02 Canonical Identity consumed
    verbatim; the anchor set is self-description copied from the verified
    P6.2 record and cross-checked on every read (OD-DI-J — NO canonical
    value is ever copied)."""
    digital_invoice_id: str              # uuid4 hex — bookkeeping
    invoice_id: str                      # UNIQUE backstop of INV-DI-1:1
    capture_s1: str
    capture_s1_algorithm_id: str
    capture_id: str
    document_id: str
    origin: str                          # frozen origins only (storage CHECK)
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class LifecycleEventRecord:
    """One immutable lifecycle event (SPEC §5/§7) — an explicit verified act,
    append-only, per-invoice seq ascending. State movement rides (from, to)
    inside the §5.2 matrix."""
    event_id: str                        # uuid4 hex — bookkeeping
    digital_invoice_id: str
    invoice_id: str                      # copied for direct query (gated)
    event_seq: int                       # per-invoice, gap-free ascending
    event_type: str                      # delegated act vocabulary (CHECK)
    from_state: str                      # lifecycle vocabulary (CHECK)
    to_state: str                        # lifecycle vocabulary (CHECK)
    replacement_invoice_id: str          # SUPERSEDE only ('' otherwise)
    reason_note: str                     # declared opaque, '' when absent
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class DigitalInvoiceLayerError(Exception):
    """Base class for the digital-invoice layer."""


class DigitalInvoiceNotFound(DigitalInvoiceLayerError):
    pass


class DigitalInvoiceDuplicate(DigitalInvoiceLayerError):
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class LifecycleEventDuplicate(DigitalInvoiceLayerError):
    def __init__(self, digital_invoice_id: str, event_seq: int) -> None:
        super().__init__(f"{digital_invoice_id}#{event_seq}")
        self.digital_invoice_id = digital_invoice_id
        self.event_seq = event_seq


class DigitalInvoicePersistenceUnavailable(DigitalInvoiceLayerError):
    pass


# ---------------------------------------------------------------------------
# Explicit outcome types — open (SPEC §4, exhaustive, never silent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DigitalInvoiceOpened:
    """The Digital Invoice was opened for the issued Canonical Invoice
    (state DRAFT by construction)."""
    record: DigitalInvoiceRecord
    invoice_read: object                 # the verified P6.2 read (consumed)
    verified_at: str


@dataclass(frozen=True)
class DigitalInvoiceOpenReplay:
    """Idempotent replay (O3/O4): the existing Digital Invoice returned
    verbatim after its own full verified read; ZERO new rows (D-03)."""
    record: DigitalInvoiceRecord
    current_state: str
    invoice_read: object
    verified_at: str


@dataclass(frozen=True)
class DigitalInvoiceRequestRefused:
    """Request-level refusal with ZERO durable residue (SPEC §3/§4 O1)."""
    invoice_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DigitalInvoiceInputIntegrityFailure:
    """Fail-closed input verification (SPEC §4 O1/O2 — the P6.2 read/trace
    ladder or a live act-time verification failed)."""
    invoice_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class DigitalInvoiceStorageUnavailable:
    """Nothing recordable — the transaction rolled back, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — lifecycle acts (SPEC §5, exhaustive, never silent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LifecycleAdvanced:
    """The transition was recorded (ONE new event row); the new current
    state is the event's to_state."""
    event: LifecycleEventRecord
    record: DigitalInvoiceRecord
    current_state: str
    invoice_read: object
    verified_at: str


@dataclass(frozen=True)
class LifecycleReplay:
    """Idempotent replay: the projected state already equals the target —
    the durable fact returns verbatim, ZERO new rows (D-03). For SUPERSEDE
    the declared replacement must byte-match the recorded one (OD-DI-H)."""
    record: DigitalInvoiceRecord
    current_state: str
    events: Tuple[LifecycleEventRecord, ...]
    invoice_read: object
    verified_at: str


@dataclass(frozen=True)
class LifecycleRequestRefused:
    """Act-level refusal with ZERO durable residue: unknown Digital Invoice,
    transition unavailable from the current state (skip/backward/terminal-
    exit), malformed declaration, supersede replacement verification
    failures (SPEC §5.3/§5.4)."""
    invoice_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class LifecycleInputIntegrityFailure:
    """Fail-closed act-time verification: the own rows, the event chain, or
    the linked P6.2 chain failed verification — no act on unverified facts."""
    invoice_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class LifecycleStorageUnavailable:
    """Nothing recordable — the transaction rolled back, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — reads / trace (SPEC §6)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DigitalInvoiceReadSuccess:
    record: DigitalInvoiceRecord
    current_state: str
    events: Tuple[LifecycleEventRecord, ...]
    invoice_read: object                 # the re-verified P6.2 read
    verified_at: str


@dataclass(frozen=True)
class DigitalInvoiceReadIntegrityFailure:
    digital_invoice_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class DigitalInvoiceReadRefused:
    digital_invoice_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DigitalInvoiceReadVerificationUnavailable:
    digital_invoice_id: Optional[str]
    issue_report: str


@dataclass(frozen=True)
class DigitalInvoiceTraceSuccess:
    invoice_id: str
    digital_invoice_id: str
    current_state: str
    chain: Tuple[str, ...]               # ordered coarse link verdicts
    verified_at: str


@dataclass(frozen=True)
class DigitalInvoiceTraceIntegrityFailure:
    invoice_id: str
    link: str                            # digital_invoice|canonical_invoice|…
    reason: str


@dataclass(frozen=True)
class DigitalInvoiceTraceRefused:
    invoice_id: str
    detail: str


@dataclass(frozen=True)
class DigitalInvoiceTraceVerificationUnavailable:
    invoice_id: str
    issue_report: str
