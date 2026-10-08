"""Reprint & Duplicate Flows domain model — WP-7.2 MVP implementation.

Binding basis: SPEC-WP72-DUPFLOW (all sections; OD-DF1..DF7 and
OD-DF-A..J declared across store.py / service.py).

Vocabulary discipline (AS-03/AD-04/CL-1 + SPEC §5 — verbatim, no paraphrase,
no invention):
  - The flow layer introduces NO identity scope and NO state name. The
    identity scopes S2 | CAPTURE_SCOPED appear ONLY as the linked WP-7.1
    resolution's own frozen fields (copied for self-description,
    cross-checked on every read — the flow layer never decides them).
  - Flow vocabulary (OD-DF-B, delegated per D-09): the DURABLE flow outcome
    is IDENTITY_ESTABLISHED | DUPLICATE_RECOGNIZED; REPRINT_RECOGNIZED is a
    call outcome ONLY and is never storable. These are flow facts, not
    identity states — no synonym of any frozen word.
  - Origins: the frozen set KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE
    (validated by WP-7.1 — copied here only for the durable anchor).
  - UNRESOLVED is never created or referenced here (D-01); no REVIEW item
    is created, read, closed, or annotated (OD-DF-J); no invoice_id exists
    in this layer (OD-DF-I — P6.1/P6.2 own the Canonical Identity).

This module is dataclasses + vocabularies + exceptions + explicit outcome
types ONLY — no I/O, no persistence, no clock, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Frozen vocabularies referenced (never redefined — see module docstring)
# ---------------------------------------------------------------------------

FLOW_OUTCOME_IDENTITY_ESTABLISHED = "IDENTITY_ESTABLISHED"
FLOW_OUTCOME_DUPLICATE_RECOGNIZED = "DUPLICATE_RECOGNIZED"
FLOW_OUTCOME_REPRINT_RECOGNIZED = "REPRINT_RECOGNIZED"   # call outcome ONLY

# Storage CHECK mirrors (§7): the durable outcome vocabulary is exactly the
# two commit-time outcomes; the reprint recognition is never durable.
DURABLE_FLOW_OUTCOMES = (FLOW_OUTCOME_IDENTITY_ESTABLISHED,
                         FLOW_OUTCOME_DUPLICATE_RECOGNIZED)

# Identity scopes — the LINKED resolution's own frozen vocabulary (§5); the
# flow layer never decides a scope, it copies and cross-checks it.
IDENTITY_SCOPE_S2 = "S2"
IDENTITY_SCOPE_CAPTURE_SCOPED = "CAPTURE_SCOPED"
LINKED_IDENTITY_SCOPES = (IDENTITY_SCOPE_S2, IDENTITY_SCOPE_CAPTURE_SCOPED)

ORIGIN_KANDOO_SALE = "KANDOO_SALE"
ORIGIN_HOLOO_CAPTURE = "HOLOO_CAPTURE"
ORIGIN_OTHER_POS_CAPTURE = "OTHER_POS_CAPTURE"
ORIGINS = (ORIGIN_KANDOO_SALE, ORIGIN_HOLOO_CAPTURE,
           ORIGIN_OTHER_POS_CAPTURE)


def utc_now_iso() -> str:
    """Single layer clock (OD-DF4) — UTC ISO-8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Durable record — exact field set (structurally enforced by boundary tests)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FlowDispositionRecord:
    """Durable flow disposition — THE operational flow fact for ONE capture
    artifact (INV-DF-1:1: at most one per capture_s1, ever).

    All identity semantics ride the LINKED WP-7.1 resolution (resolution_id):
    this record copies the anchor pointers and the linked scope/fingerprint
    for self-description and cross-store verification — it decides nothing.
    Immutable once committed. Content determinism is separated from
    bookkeeping: disposition_id / created_at are bookkeeping; the flow fact
    is a pure function of the linked durable identity facts (OD-DF-E)."""
    disposition_id: str
    capture_s1: str                      # UNIQUE — INV-DF-1:1
    capture_s1_algorithm_id: str
    capture_id: str
    document_id: str
    resolution_id: str                   # the linked WP-7.1 resolution
    original_resolution_id: str          # '' iff IDENTITY_ESTABLISHED
    duplicate_observation_id: str        # '' iff IDENTITY_ESTABLISHED
    declared_origin: str                 # frozen origins only (storage CHECK)
    flow_outcome: str                    # IDENTITY_ESTABLISHED |
                                         # DUPLICATE_RECOGNIZED (storage CHECK;
                                         # REPRINT_RECOGNIZED never storable)
    identity_scope: str                  # linked resolution's scope (copied)
    identity_fingerprint: str            # linked resolution's fingerprint (''
                                         # iff CAPTURE_SCOPED)
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class FlowLayerError(Exception):
    """Base class for the duplicate-flows layer."""


class DispositionNotFound(FlowLayerError):
    pass


class DispositionDuplicate(FlowLayerError):
    """INV-DF-1:1 hit inside the commit transaction (in-txn check or UNIQUE
    backstop) — the existing disposition wins, never a second flow fact."""
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class FlowPersistenceUnavailable(FlowLayerError):
    pass


# ---------------------------------------------------------------------------
# Explicit outcome types — handle() (SPEC §4, exhaustive, never silent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FlowIdentityEstablished:
    """A NEW resolution was recorded (F2) and its IDENTITY_ESTABLISHED
    disposition committed — the capture's first durable flow fact."""
    disposition: FlowDispositionRecord
    record: object                       # IdentityResolutionRecord (linked)
    role_rows: tuple


@dataclass(frozen=True)
class FlowDuplicateRecognized:
    """The capture's new resolution is a D-03 definite duplicate (F3): the
    DUPLICATE_RECOGNIZED disposition points at the deterministic original
    and the WP-7.1 observation — ONE document identity, never a second."""
    disposition: FlowDispositionRecord
    record: object                       # the later capture's resolution
    original_resolution: object          # the original (re-verified on read)
    observation: object                  # IdentityDuplicateObservation
    role_rows: tuple


@dataclass(frozen=True)
class FlowReprintRecognized:
    """Reprint recognition (F4/F5/F6): the capture was already dispositioned
    — the existing disposition returned VERBATIM, read-only, after its full
    verified read; ZERO new rows."""
    disposition: FlowDispositionRecord
    record: object                       # the (replayed) linked resolution
    role_rows: tuple
    observation: Optional[object]
    verified_at: str


@dataclass(frozen=True)
class FlowRequestRefused:
    """WP-7.1 request-level refusal propagated VERBATIM (F1) — zero durable
    residue (OD-DF-G: never reformulated, never converted)."""
    domain_state_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class FlowInputIntegrityFailure:
    """WP-7.1 verified-read/provenance failure propagated (F1), or a linked
    identity fact that failed verification during a flow commit path —
    fail closed, zero durable residue."""
    domain_state_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class FlowStorageUnavailable:
    """Flow persistence failure — the transaction rolled back, zero
    residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — verified reads (SPEC §6)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FlowReadSuccess:
    """Verified flow read: the disposition verified (own VOR + structural
    gates) AND every linked identity fact re-verified through the WP-7.1
    verified reads (resolution; original + observation iff duplicate)."""
    disposition: FlowDispositionRecord
    record: object                       # the linked IdentityResolutionRecord
    role_rows: tuple
    observation: Optional[object]
    original_resolution: Optional[object]
    verified_at: str


@dataclass(frozen=True)
class FlowReadIntegrityFailure:
    disposition_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class FlowReadRefused:
    disposition_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class FlowReadVerificationUnavailable:
    disposition_id: Optional[str]
    issue_report: str
