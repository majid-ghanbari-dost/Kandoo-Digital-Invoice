"""Validation-domain-layer model — WP-5.2 MVP implementation.

Binding basis:
  SPEC-WP52-VSM  Validation State Machine + REVIEW Queue Contract v1.0-MVP
                 (produced inline per TM/PO implementation dispatch 2026-10-07)
  REG-WPR Phase Index P5 (WP-5.2) + PO dispatch 2026-10-07
  AS-03 (the Validation State Machine vocabulary is transferred VERBATIM from the
        frozen source; no state is redefined, renamed, or added here) | AD-04
        (the Validation output model includes REVIEW and REJECT; field-level
        UNRESOLVED can take the Invoice to REVIEW; CL-1 — no paraphrase) | D-01
        (value resolution order EXTRACTED → DERIVED → UNRESOLVED; this is the P5
        domain layer where UNRESOLVED is finally created — strictly inside the
        frozen vocabulary and meaning) | D-03 (incomplete/conflicting → REVIEW) |
        D-08 (unresolved mismatch → REVIEW) | D-09 (delegated details declared in
        machine.py/store.py/service.py) | AD-02 (Validation domain boundary) |
        AS-01 (pipeline position: P3 → P4.1 → P4.2 → P5.1 → **[this layer]** →
        Canonicalization Gate → ...).
  SPEC-WP51-VAL analog: verified reads are the ONLY sanctioned input paths —
  P5.1 rule outcomes via the validation service's VOR read, NORMALIZED field
  facts via the frozen WP-4.1 read, rule declarations via the frozen WP-5.1
  registry. This layer never reads stores in parallel and never re-reads raw
  artifacts.

Boundary (normative): this layer is a deterministic STATE MACHINE plus a durable
REVIEW QUEUE. It performs NO canonical field mapping, NO line grouping or
association discovery, NO product/customer/invoice-identity matching, NO
semantic/fuzzy matching, NO business-rule inference, NO tax/currency/date logic,
NO cross-document anything, NO validation/derivation/normalization execution, NO
automatic semantic resolution of any kind, NO Canonicalization Gate logic (P6),
and NO Canonical Invoice/Sale/Digital Invoice creation. UNRESOLVED is created
HERE — field-level only, per the D-01 order, never auto-resolved. Every outcome
is explicit and exhaustive; a silent result does not exist in this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Frozen vocabulary (SPEC §3 — VERBATIM; no extra states exist in this layer)
# ---------------------------------------------------------------------------

DOMAIN_STATE_VALID = "VALID"            # all declared rules hold; no UNRESOLVED
DOMAIN_STATE_INVALID = "INVALID"        # at least one decidable rule violation
DOMAIN_STATE_DEFERRED = "DEFERRED"      # validation uncertainty (rule could not
                                        # decide)
DOMAIN_STATE_UNRESOLVED = "UNRESOLVED"  # field-level D-01 order exhausted —
                                        # created HERE (the only layer allowed to)

DOMAIN_STATES = (DOMAIN_STATE_VALID, DOMAIN_STATE_INVALID, DOMAIN_STATE_DEFERRED,
                 DOMAIN_STATE_UNRESOLVED)

DISPOSITION_CLEAR = "CLEAR"      # explicit empty routing — mechanism marker, not
                                 # a Canonical Invoice state
DISPOSITION_REVIEW = "REVIEW"    # routed to the REVIEW queue (AD-04)
DISPOSITION_REJECT = "REJECT"    # decisive non-recoverable invalidity (AD-04)

DISPOSITIONS = (DISPOSITION_CLEAR, DISPOSITION_REVIEW, DISPOSITION_REJECT)

# Stable state_reason codes (SPEC §3 — one per transition route)
REASON_DECISIVE_INVALID = "decisive-invalid"                # T1
REASON_D08_MISMATCH_REVIEW = "d08-mismatch-review"          # T2 (D-08)
REASON_D01_UNRESOLVED_REVIEW = "d01-unresolved-review"      # T3 (D-01/AD-04)
REASON_VALIDATION_DEFERRED_REVIEW = "validation-deferred-review"   # T4
REASON_ALL_RULES_VALID = "all-rules-valid"                  # T5

# P5.1 outcome reasons routed by each transition (SPEC-WP51-VAL §5 vocabulary,
# consumed verbatim — never re-decided here)
DECISIVE_INVALID_REASONS = ("absent", "present-not-usable", "mismatch")
TOLERANCE_INVALID_REASONS = ("mismatch-beyond-tolerance", "mismatch-after-rounding")

# Field projection vocabulary (SPEC §4)
PROJECTION_RESOLVED = "RESOLVED"
PROJECTION_UNRESOLVED = "UNRESOLVED"
PROJECTION_STATUSES = (PROJECTION_RESOLVED, PROJECTION_UNRESOLVED)

ORIGIN_RELAY_NORMALIZED = "NORMALIZED"   # EXTRACTED-bearing usable value (D-01 step 1)
ORIGIN_RELAY_DERIVED = "DERIVED"         # derived value (D-01 step 2)

UNRESOLVED_REASON_D01 = "d01-no-valid-method"   # the ONLY unresolved reason —
                                                # D-01 order exhausted

# REVIEW queue event vocabulary (SPEC §5 — minimal, append-only lifecycle)
EVENT_ANNOTATE = "ANNOTATE"
EVENT_CLOSE = "CLOSE"
EVENT_TYPES = (EVENT_ANNOTATE, EVENT_CLOSE)

# Derived review status (reduced deterministically from the append-only history)
REVIEW_STATUS_OPEN = "OPEN"
REVIEW_STATUS_CLOSED = "CLOSED"

NOTE_VERIFY_FAILED = "verify FAILED"
NOTE_VERIFICATION_UNAVAILABLE = "verification unavailable (no verdict computable)"


def utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with explicit timezone — validation-domain clock
    (OD-S4)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Records — exact field sets (structurally enforced by the boundary test)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StateValidationRef:
    """One durable pointer to the P5.1 validation record consumed by the
    projection (declared order). Outcomes are relayed verbatim — never re-decided."""
    domain_state_id: str
    ord_slot: int                  # 0-based declared ruleset order
    validation_id: str             # pointer → the WP-5.1 record
    rule_id: str
    rule_version: str
    rule_kind: str                 # relayed ('R1' | 'R2')
    rule_fingerprint: str          # relayed anchor of the exact rule version
    outcome: str                   # relayed ('VALID' | 'INVALID' | 'DEFERRED')
    outcome_reason: str            # relayed stable reason (SPEC-WP51-VAL §5)


@dataclass(frozen=True)
class FieldProjectionRow:
    """One durable field-level D-01 projection row (SPEC §4).

    RESOLVED rows relay the value origin and keep the pointer chain intact
    (NORMALIZED → field_seq, DERIVED → derivation_id). UNRESOLVED rows are the
    frozen D-01 terminal label — field-level, reason-bearing, anchored at the
    scope record, never auto-resolved.
    """
    domain_state_id: str
    field_name: str                      # engine-vocabulary field (declared by
                                         # the ruleset — never invented here)
    projection_status: str               # 'RESOLVED' | 'UNRESOLVED' (storage CHECK)
    origin_relayed: Optional[str]        # 'NORMALIZED' | 'DERIVED' | None
    candidate_count: int                 # ≥ 1 for RESOLVED; 0 for UNRESOLVED
    source_normalization_id: str         # scope anchor (always present)
    source_extraction_id: str            # scope anchor (always present)
    source_field_seq: Optional[int]      # NORMALIZED pointer (RESOLVED only)
    source_derivation_id: Optional[str]  # DERIVED pointer (RESOLVED only)
    unresolved_reason: Optional[str]     # 'd01-no-valid-method' (UNRESOLVED only)
    detail: str


@dataclass(frozen=True)
class DomainStateRecord:
    """Durable domain state record — the projection of one COMPLETE declared
    ruleset evaluation over one normalization record.

    domain_state ∈ VALID | INVALID | DEFERRED | UNRESOLVED (verbatim frozen
    vocabulary; storage CHECK). disposition ∈ CLEAR | REVIEW | REJECT (AD-04
    output model + the explicit empty-routing marker; storage CHECKs pin the
    state↔disposition consistency). record_fingerprint anchors record scalars +
    validation refs + field projections (sha256-v1), verified on every read.
    """
    domain_state_id: str
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    ruleset_id: str
    ruleset_version: str
    ruleset_fingerprint: str
    ruleset_fingerprint_algorithm_id: str
    domain_state: str                    # frozen vocabulary (storage CHECK)
    disposition: str                     # CLEAR | REVIEW | REJECT (storage CHECK)
    state_reason: str                    # stable route code (SPEC §3)
    state_detail: str
    rule_count: int
    valid_count: int
    invalid_count: int
    deferred_count: int
    unresolved_count: int                # field-level UNRESOLVED row count
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class ReviewQueueItem:
    """Durable REVIEW queue item — validation/canonicalization uncertainty held
    for downstream handling (SPEC §5). The item is immutable; its status lives in
    the append-only event history and is derived on every read."""
    review_id: str
    domain_state_id: str
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    ruleset_id: str
    ruleset_version: str
    ruleset_fingerprint: str
    domain_state: str                    # the projected state at creation
    review_reason: str                   # stable route code (SPEC §5)
    review_detail: str
    created_at: str
    item_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class ReviewQueueEvent:
    """One append-only, hash-chained lifecycle event (SPEC §5/OD-S13).

    event_type ∈ {ANNOTATE, CLOSE} (storage CHECK); at most one CLOSE per item
    (terminal — partial UNIQUE backstop + in-transaction check). The chain
    (prev_event_fingerprint) makes the history tamper-evident as a sequence."""
    event_id: str
    review_id: str
    event_seq: int                       # contiguous from 0 per item
    event_type: str                      # 'ANNOTATE' | 'CLOSE' (storage CHECK)
    event_note: str
    event_actor: str                     # opaque — recorded, never interpreted
    created_at: str
    prev_event_fingerprint: str          # hash-chain link ("" for seq 0)
    event_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class ValidationDomainError(Exception):
    """Base class for all explicit validation-domain-layer failures."""


class DomainStateNotFound(ValidationDomainError):
    """The referenced domain_state_id / review_id does not exist in the store."""


class DomainStateDuplicate(ValidationDomainError):
    """INV-S-1:1 — a projection for (normalization_id, ruleset_fingerprint)
    already exists. Raised inside the atomic commit; the service surfaces it as
    an explicit AlreadyExists outcome carrying the existing domain_state_id."""

    def __init__(self, domain_state_id: str) -> None:
        super().__init__(f"domain state already exists: {domain_state_id}")
        self.domain_state_id = domain_state_id


class DomainStatePersistenceUnavailable(ValidationDomainError):
    """No record durably committed (atomic txn rolled back — zero residue, by
    construction). Never a silent partial write."""


# ---------------------------------------------------------------------------
# Projection outcomes (exhaustive — SPEC §8; consumed from verified sources only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DomainStateProjected:
    """Verified P5.1 evaluation + declared ruleset → explicit domain state,
    durably committed (one txn). review_item is present iff disposition = REVIEW."""
    record: DomainStateRecord
    validation_refs: tuple
    field_projections: tuple
    review_item: Optional[ReviewQueueItem]


@dataclass(frozen=True)
class DomainStateAlreadyExists:
    """INV-S-1:1 replay: the same (normalization_id, ruleset_fingerprint) was
    already projected. Explicit, never a silent no-op; no second record is
    created. Re-projection after pipeline state changed uses a NEW
    ruleset_version (SPEC §7)."""
    domain_state_id: str
    normalization_id: str
    ruleset_id: str
    ruleset_version: str


@dataclass(frozen=True)
class DomainStateSourceIntegrityFailure:
    """A source failed its verified read or fingerprint check — a P5.1 record, a
    rule declaration (registry fingerprint ≠ record fingerprint), or the
    normalization record. Nothing projected."""
    normalization_id: str
    reason: str


@dataclass(frozen=True)
class DomainStateSourceRefused:
    """Source explicitly refused (unknown normalization / no P5.1 records /
    incomplete or extra evaluation vs the declared keys) — nothing projected."""
    normalization_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DomainStateSourceUnavailable:
    """Source verification could not execute (no state computable) — nothing
    projected, Issue-Report surfaced."""
    normalization_id: str
    issue_report: str


@dataclass(frozen=True)
class DomainStateStorageUnavailable:
    """Nothing recordable — nothing persisted, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Read outcomes (VOR pattern — exhaustive; no silent broken read exists)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DomainStateReadSuccess:
    """Stored projection + refs + field rows delivered ONLY together with the
    same-read VALID verdict."""
    record: DomainStateRecord
    validation_refs: tuple
    field_projections: tuple
    review_item: Optional[ReviewQueueItem]
    review_status: Optional[str]         # derived from the event history
    verified_at: str


@dataclass(frozen=True)
class DomainStateReadIntegrityFailure:
    """Definitive FAILED verdict (stored bytes no longer match the committed
    fingerprint); the stored (broken) content is NEVER delivered."""
    domain_state_id: str
    reason: str
    verified_at: str


@dataclass(frozen=True)
class DomainStateReadRefused:
    """Unknown domain_state_id — nothing delivered, no verdict, no state change."""
    domain_state_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DomainStateReadVerificationUnavailable:
    """No verdict computable (structural inconsistency) — no content,
    Issue-Report surfacing."""
    domain_state_id: str
    issue_report: str


@dataclass(frozen=True)
class ReviewItemReadSuccess:
    """Review item + full event history + derived status, delivered ONLY together
    with the same-read VALID verdict over item and events."""
    item: ReviewQueueItem
    events: tuple
    status: str                          # OPEN | CLOSED (derived — SPEC §5)
    verified_at: str


@dataclass(frozen=True)
class ReviewItemReadIntegrityFailure:
    """Item or any event failed verification — content NEVER delivered."""
    review_id: str
    reason: str
    verified_at: str


@dataclass(frozen=True)
class ReviewItemReadRefused:
    """Unknown review_id — nothing delivered."""
    review_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class ReviewItemReadVerificationUnavailable:
    """No verdict computable — Issue-Report surfacing."""
    review_id: str
    issue_report: str


# ---------------------------------------------------------------------------
# Event outcomes (exhaustive)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewEventAppended:
    """Event durably appended (hash-chained); status re-derived from history."""
    event: ReviewQueueEvent
    status: str


@dataclass(frozen=True)
class ReviewEventRefused:
    """Event refused (unknown item / unknown type / already CLOSED / chain-verify
    failure) — nothing appended, no state change."""
    review_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class ReviewEventUnavailable:
    """Append could not execute — nothing appended, Issue-Report surfaced."""
    review_id: str
    issue_report: str


# ---------------------------------------------------------------------------
# Trace outcomes (provenance walk — every link re-verified inside one call, §10)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DomainStateTraceSuccess:
    """The full chain held under verified reads in THIS walk — pointers only, no
    source values copied forward."""
    domain_state_id: str
    chain: tuple                         # ordered coarse link summaries (strings)


@dataclass(frozen=True)
class DomainStateTraceIntegrityFailure:
    """The named link of the chain failed its verified read during the walk."""
    domain_state_id: str
    link: str    # domain_state|validation|normalization|extraction|binding|document|capture
    reason: str


@dataclass(frozen=True)
class DomainStateTraceRefused:
    """A chain link refused (missing record) — the chain cannot be walked."""
    domain_state_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DomainStateTraceVerificationUnavailable:
    """A chain link could not be verified (no verdict computable) — Issue-Report."""
    domain_state_id: str
    issue_report: str
