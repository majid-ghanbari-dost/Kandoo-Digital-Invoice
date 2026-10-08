"""Deterministic Customer Linking domain model — WP-9.1 MVP implementation.

Binding basis: SPEC-WP91-CUSTLINK (all sections; OD-CL1..CL8 declared across
store.py / service.py).

Vocabulary discipline (AS-03/AS-04/AD-04/CL-1 + SPEC §5 — verbatim, no
paraphrase, no invention):
  - The link outcome vocabulary (OD-CL7, delegated per D-09): the DURABLE
    outcome is LINKED | UNRESOLVED. This is a Customer Linkage domain fact —
    NOT a validation state and NOT a canonicalization state; no synonym of
    any frozen word is introduced. "UNRESOLVED" here is the D-06-conformant
    absence of a deterministic link (ambiguity remains ambiguity), never a
    P5 UNRESOLVED field value (which this layer never creates, reads, or
    resolves).
  - Provenance labels are D-01's vocabulary VERBATIM: EXTRACTED | DERIVED —
    relayed from the verified P6.2 canonical field, never decided here.
  - Identifier kinds/values are DECLARED opaque strings (OD-CL3): stored and
    compared verbatim; NO enumeration, NO barcode semantics, NO format
    grammar, NO checksum, NO normalization.
  - invoice_id is the D-02 Canonical Identity issued at P6.1 — consumed
    VERBATIM (no identifier is minted in this layer).
  - D-06 (normative, structurally enforced — OD-CL2): NO outcome of this
    domain ever creates a customer. The register's ONLY write path is the
    explicit registration API; the link ladder's ONLY write is the
    append-only link row.

Pointer discipline (OD-CL6 / OD-IR-J precedent): the durable link row
carries declarations, pointers and counts — NEVER the invoice's identifier
value. The value lives in the verified P6.2 canonical field (re-joined live
on every read) and in the customer register's own registered content.

This module is dataclasses + vocabularies + exceptions + explicit outcome
types ONLY — no I/O, no persistence, no clock, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Vocabularies (declared per D-09 — see module docstring)
# ---------------------------------------------------------------------------

LINK_OUTCOME_LINKED = "LINKED"
LINK_OUTCOME_UNRESOLVED = "UNRESOLVED"

# Storage CHECK mirror (§5): the durable outcome vocabulary is exactly these
# two; there is no creation/enrichment/merge surface of any kind.
DURABLE_LINK_OUTCOMES = (LINK_OUTCOME_LINKED, LINK_OUTCOME_UNRESOLVED)

UNRESOLVED_NO_CUSTOMER_IDENTITY = "no-customer-identity"

# The only UNRESOLVED reason reachable in this WP (storage CHECK pins it —
# any future reason requires a contract change; fail-closed by design).
DURABLE_UNRESOLVED_REASONS = (UNRESOLVED_NO_CUSTOMER_IDENTITY,)

PROVENANCE_EXTRACTED = "EXTRACTED"
PROVENANCE_DERIVED = "DERIVED"
PROVENANCES = (PROVENANCE_EXTRACTED, PROVENANCE_DERIVED)

# Stable request-refusal codes (§3/§4 — zero durable residue)
REFUSE_DECLARATION_MALFORMED = "declaration-malformed"
REFUSE_FIELD_NOT_FOUND = "declared-field-not-found"
REFUSE_FIELD_AMBIGUOUS = "declared-field-ambiguous"

# Verify-on-Read failure note (same vocabulary as the other layers)
NOTE_VERIFY_FAILED = "verify FAILED"


def utc_now_iso() -> str:
    """Single layer clock (OD-CL1) — UTC ISO-8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Durable records — exact field sets (structurally enforced by boundary tests)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CustomerIdentityRecord:
    """One registered customer identity (OD-CL2) — the minimal
    Customer-domain register surface required by D-06's "link to an
    EXISTING Customer". Created ONLY by the explicit registration API
    (which carries no capture/invoice parameter — no capture-derived
    customer creation is possible, DEF3). Immutable once committed.
    identifier_kind / identifier_value are stored VERBATIM (OD-CL3)."""
    customer_identity_id: str
    identifier_kind: str
    identifier_value: str
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class CustomerLinkRecord:
    """Durable deterministic-link fact for ONE declared customer reference on
    ONE issued Canonical Invoice (INV-CL-1:1 per
    (invoice_id, declared_field_name, identifier_kind) — UNIQUE backstop).

    All invoice semantics ride the LINKED P6.2 verified read (invoice_id):
    this record copies the anchor pointers for self-description and
    cross-store verification — it decides nothing and stores NO identifier
    value (OD-CL6). Immutable once committed. Content determinism is
    separated from bookkeeping: link_id / created_at are bookkeeping; the
    link fact is a pure function of the invoice's verified content and the
    customer register at first-link time (OD-CL4)."""
    link_id: str
    invoice_id: str                      # the linked P6.2 issued invoice
    capture_s1: str                      # copied anchor (cross-checked on read)
    capture_s1_algorithm_id: str
    declared_field_name: str
    canonical_seq: int                   # pointer into the verified field
                                         # inventory (stable, gap-free)
    provenance: str                      # D-01 label of the resolved field
    identifier_kind: str
    link_outcome: str                    # LINKED | UNRESOLVED (storage CHECK)
    customer_identity_id: str            # '' iff UNRESOLVED
    unresolved_reason: str               # '' iff LINKED; stable code
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class CustomerLinkingLayerError(Exception):
    """Base class for the customer-linking layer."""


class CustomerIdentityNotFound(CustomerLinkingLayerError):
    pass


class CustomerIdentityDuplicate(CustomerLinkingLayerError):
    """The UNIQUE (identifier_kind, identifier_value) backstop hit inside the
    commit transaction — the existing customer identity wins, never a second
    row for a definitive identifier."""
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class LinkNotFound(CustomerLinkingLayerError):
    pass


class LinkDuplicate(CustomerLinkingLayerError):
    """INV-CL-1:1 hit inside the commit transaction (in-txn check or UNIQUE
    backstop) — the existing link outcome wins, never a second fact."""
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class CustomerLinkingPersistenceUnavailable(CustomerLinkingLayerError):
    pass


# ---------------------------------------------------------------------------
# Explicit outcome types — register_customer_identity (SPEC §3, exhaustive)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CustomerIdentityRegistered:
    """A NEW customer identity was registered (first sighting)."""
    customer_identity: CustomerIdentityRecord


@dataclass(frozen=True)
class CustomerIdentityReplay:
    """Idempotent re-registration of the same (kind, value): the existing
    customer identity returned VERBATIM — no new rows (OD-CL2)."""
    customer_identity: CustomerIdentityRecord


@dataclass(frozen=True)
class CustomerRegistrationRefused:
    """Request-level refusal with ZERO durable residue (§3: empty kind or
    value)."""
    detail: str


@dataclass(frozen=True)
class CustomerStorageUnavailable:
    """Customer-register persistence failure — the transaction rolled back,
    zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — link() (SPEC §4, exhaustive, never silent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CustomerLinked:
    """The declared reference byte-matched EXACTLY ONE registered customer
    identity under the declared kind (L5) — the D-06 deterministic link to
    an EXISTING customer, committed durably."""
    record: CustomerLinkRecord
    invoice_read: object                 # AssemblyReadSuccess (linked)
    customer_identity: CustomerIdentityRecord


@dataclass(frozen=True)
class CustomerLinkUnresolved:
    """NO registered customer identity exists for the declared identifier
    (L5) — a durable, auditable UNRESOLVED fact. NO customer is created
    (D-06/DEF3 — structural); ambiguity remains ambiguity (OD-CL7)."""
    record: CustomerLinkRecord
    invoice_read: object                 # AssemblyReadSuccess (linked)
    reason: str


@dataclass(frozen=True)
class CustomerLinkReplay:
    """The declared reference was already linked (L4/L6): the existing
    outcome returned VERBATIM after its full verified read — ZERO new rows;
    replay never re-decides (OD-CL4)."""
    record: CustomerLinkRecord
    invoice_read: object                 # AssemblyReadSuccess (linked)
    customer_identity: Optional[object]  # set iff LINKED
    verified_at: str


@dataclass(frozen=True)
class CustomerLinkRequestRefused:
    """Request-level refusal (L2/L3) with ZERO durable residue: malformed
    declaration, declared field not found, or declared field ambiguous
    (never auto-resolution)."""
    invoice_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class CustomerLinkInputIntegrityFailure:
    """Fail-closed input verification (L1): the linked P6.2 read refused /
    failed / unverifiable (propagated verbatim), or the customer lookup
    observed an impossible ≥2 state (store corruption — never a link
    decision, OD-CL5). Zero durable residue."""
    invoice_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class CustomerLinkStorageUnavailable:
    """Link persistence failure — the transaction rolled back, zero
    residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — verified reads (SPEC §6)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CustomerLinkReadSuccess:
    """Verified link read: the link row verified (own VOR), the linked
    invoice re-verified through the P6.2 verified read with the pointer
    re-joined, and — iff LINKED — the linked customer identity re-verified
    with the link RE-PROVEN LIVE (byte-identity of the invoice's canonical
    value and the registered identifier value)."""
    record: CustomerLinkRecord
    invoice_read: object                 # AssemblyReadSuccess (re-verified)
    customer_identity: Optional[object]  # re-verified iff LINKED
    verified_at: str


@dataclass(frozen=True)
class CustomerReadSuccess:
    """Verified customer identity read (own VOR)."""
    customer_identity: CustomerIdentityRecord
    verified_at: str


@dataclass(frozen=True)
class CustomerLinkReadIntegrityFailure:
    link_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class CustomerLinkReadRefused:
    link_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class CustomerLinkReadVerificationUnavailable:
    link_id: Optional[str]
    issue_report: str


@dataclass(frozen=True)
class CustomerReadIntegrityFailure:
    customer_identity_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class CustomerReadRefused:
    customer_identity_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class CustomerReadVerificationUnavailable:
    customer_identity_id: Optional[str]
    issue_report: str
