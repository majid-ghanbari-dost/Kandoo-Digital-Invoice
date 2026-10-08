"""Canonicalization Gate domain model — WP-6.1 MVP implementation.

Binding basis: SPEC-WP61-CANGATE (all sections; OD-G1..OD-G10 delegated details
declared in identity.py / gate.py / store.py / service.py).

Vocabulary discipline (AS-03/AD-04/CL-1 — verbatim, no paraphrase, no
invention):
  - Gate decisions are the dispatch §14 paths VERBATIM:
    ACCEPTED | REJECTED | REVIEW | ALREADY_CANONICALIZED.
    UNRESOLVED is NOT a gate decision — the D-01 field-level label is created
    ONLY in P5.2; unresolved inputs route REVIEW (D-01).
  - Origins are the dispatch §7 set VERBATIM:
    KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE. No other origin exists.
  - Identity classes are D-02's concepts VERBATIM:
    DETERMINISTIC | CAPTURE_SCOPED.
  - Identity source: S2_EXTRACTED_VERIFIED (D-02's second deterministic path;
    the adapter-document-id path is RESERVED per OD-G5 — no producer exists).

This module is dataclasses + vocabularies + exceptions + explicit outcome
types ONLY — no I/O, no persistence, no clock, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Frozen vocabularies (verbatim — see module docstring)
# ---------------------------------------------------------------------------

DECISION_ACCEPTED = "ACCEPTED"
DECISION_REJECTED = "REJECTED"
DECISION_REVIEW = "REVIEW"
DECISION_ALREADY_CANONICALIZED = "ALREADY_CANONICALIZED"
DECISIONS = (DECISION_ACCEPTED, DECISION_REJECTED, DECISION_REVIEW,
             DECISION_ALREADY_CANONICALIZED)

ORIGIN_KANDOO_SALE = "KANDOO_SALE"
ORIGIN_HOLOO_CAPTURE = "HOLOO_CAPTURE"
ORIGIN_OTHER_POS_CAPTURE = "OTHER_POS_CAPTURE"
ORIGINS = (ORIGIN_KANDOO_SALE, ORIGIN_HOLOO_CAPTURE, ORIGIN_OTHER_POS_CAPTURE)
# OD-G6: the native flow (AS-02) has no capture pipeline and no P5.2 state;
# a KANDOO_SALE origin on a P5.2-sourced request is refused (fail-closed).
CAPTURE_PIPELINE_ORIGINS = (ORIGIN_HOLOO_CAPTURE, ORIGIN_OTHER_POS_CAPTURE)

IDENTITY_CLASS_DETERMINISTIC = "DETERMINISTIC"
IDENTITY_CLASS_CAPTURE_SCOPED = "CAPTURE_SCOPED"
IDENTITY_CLASSES = (IDENTITY_CLASS_DETERMINISTIC,
                    IDENTITY_CLASS_CAPTURE_SCOPED)
IDENTITY_CLASS_UNROUTED = ""          # non-VALID routes never reach identity

IDENTITY_SOURCE_S2 = "S2_EXTRACTED_VERIFIED"
IDENTITY_SOURCES = (IDENTITY_SOURCE_S2,)

# D-02 identity roles — the frozen S2 triad (invoice number + date + total)
ROLE_INVOICE_NUMBER = "INVOICE_NUMBER"
ROLE_INVOICE_DATE = "INVOICE_DATE"
ROLE_INVOICE_TOTAL = "INVOICE_TOTAL"
IDENTITY_ROLES = (ROLE_INVOICE_NUMBER, ROLE_INVOICE_DATE, ROLE_INVOICE_TOTAL)

# Stable decision_reason codes (SPEC §4 — every route anchored)
REASON_UPSTREAM_DECISIVE_INVALID = "upstream-decisive-invalid"
REASON_D03_DEFINITE_DUPLICATE = "d03-definite-document-duplicate"
REASON_D02_CAPTURE_REPLAY = "d02-capture-idempotent-replay"
REASON_ALL_FROZEN_CONDITIONS_MET = "all-frozen-conditions-met"
# G2 relayed reasons — the P5.2 state_reason codes, relayed VERBATIM
RELAYED_REVIEW_REASONS = ("d08-mismatch-review", "d01-unresolved-review",
                          "validation-deferred-review")
# G3 identity-uncertainty reasons (D-03: ناقص / متعارض / ambiguity → REVIEW)
REASON_D03_INCOMPLETE_IDENTITY = "d03-incomplete-document-identity"
REASON_D03_CONFLICTING_IDENTITY = "d03-conflicting-document-identity"
REASON_D03_UNDETERMINED_IDENTITY = "d03-document-identity-undetermined"
GATE_REVIEW_REASONS = (REASON_D03_INCOMPLETE_IDENTITY,
                       REASON_D03_CONFLICTING_IDENTITY,
                       REASON_D03_UNDETERMINED_IDENTITY) + \
                      RELAYED_REVIEW_REASONS
GATE_REJECT_REASONS = (REASON_UPSTREAM_DECISIVE_INVALID,
                       REASON_D03_DEFINITE_DUPLICATE)
DECISION_REASONS = GATE_REVIEW_REASONS + GATE_REJECT_REASONS + \
                   (REASON_D02_CAPTURE_REPLAY, REASON_ALL_FROZEN_CONDITIONS_MET)

# Review lifecycle vocabulary (identical mechanics to the P5.2 queue)
EVENT_ANNOTATE = "ANNOTATE"
EVENT_CLOSE = "CLOSE"
EVENT_TYPES = (EVENT_ANNOTATE, EVENT_CLOSE)
REVIEW_STATUS_OPEN = "OPEN"
REVIEW_STATUS_CLOSED = "CLOSED"

# Verify-on-Read failure note (same vocabulary as the other layers)
NOTE_VERIFY_FAILED = "verify FAILED"
NOTE_VERIFICATION_UNAVAILABLE = (
    "verification unavailable — Issue Report required"
)

# Refusal reason codes (request-level, never durable decisions)
REFUSE_ORIGIN_UNKNOWN = "origin-outside-frozen-vocabulary"
REFUSE_ORIGIN_NATIVE_FLOW = "origin-native-flow-not-consumable-here"
REFUSE_BINDING_MALFORMED = "binding-malformed"


def utc_now_iso() -> str:
    """Single layer clock (OD-C4) — UTC ISO-8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Durable records — exact field sets (structurally enforced by boundary tests)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateDecisionRecord:
    """Durable gate decision — the auditable outcome for ONE P5.2 domain state.

    Content determinism is separated from identity: uuid4 decision_id /
    created_at are bookkeeping scalars; the decision CONTENT is a pure function
    of (the verified P5.2 state content, the verified normalization content,
    the declared request) — INV-D-1:1 makes the identity unique so no mutable
    duplicate can drift (SPEC §8 OD-C3)."""
    decision_id: str
    domain_state_id: str
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    declared_origin: str                 # frozen origins only (storage CHECK)
    decision: str                        # ACCEPTED|REJECTED|REVIEW|ALREADY_CANONICALIZED
    decision_reason: str                 # stable code (SPEC §4)
    decision_detail: str                 # audit trail (metadata, never values)
    identity_class: str                  # ''|DETERMINISTIC|CAPTURE_SCOPED
    identity_source: str                 # ''|S2_EXTRACTED_VERIFIED
    identity_fingerprint: str            # '' when identity was not resolved
    canonical_invoice_id: Optional[str]  # set iff ACCEPTED (storage CHECK)
    upstream_review_id: Optional[str]    # P5.2 queue item reference (G2)
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class CanonicalInvoiceRecord:
    """Durable Canonical Invoice ADMISSION record (SPEC §6) — the first real
    boundary of data entering the Canonical Invoice domain.

    Source-independent (D-04): origin enum + upstream POINTERS only — no
    source-schema columns, no raw pipeline values (the S2 tuple rides as its
    deterministic fingerprint; pointer rows re-join values via verified
    reads). Immutable once committed (OD-C7). Full canonical field/line
    assembly and the formal invoice_id issuance workflow are WP-6.2 (OD-G8)."""
    canonical_invoice_id: str
    decision_id: str
    domain_state_id: str
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    origin: str                          # frozen origins only (storage CHECK)
    identity_class: str                  # DETERMINISTIC only (storage CHECK)
    identity_source: str                 # S2_EXTRACTED_VERIFIED
    identity_fingerprint: str
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class CanonicalIdentityPointer:
    """One identity-role pointer row (SPEC §5 I5 / §9) — NO raw values."""
    canonical_invoice_id: str
    role: str                            # INVOICE_NUMBER|INVOICE_DATE|INVOICE_TOTAL
    source_field_name: str               # the declared binding, verbatim
    normalization_id: str
    field_seq: int


@dataclass(frozen=True)
class GateReviewItem:
    """Durable gate REVIEW item — holds canonicalization-stage uncertainty
    (SPEC §7). NEVER a semantic resolver."""
    review_id: str
    decision_id: str
    domain_state_id: str
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    review_reason: str
    review_detail: str
    created_at: str
    item_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class GateReviewEvent:
    """Append-only, hash-chained lifecycle event (SPEC §7)."""
    event_id: str
    review_id: str
    event_seq: int
    event_type: str                      # ANNOTATE|CLOSE
    event_note: str
    event_actor: str
    created_at: str
    prev_event_fingerprint: str
    event_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Identity resolution result (pure — identity.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoleResolution:
    """Per-role candidate metadata — declarations and counts, never values."""
    role: str
    source_field_name: str
    candidate_count: int
    field_seqs: Tuple[int, ...]          # NORMALIZED rows observed (order-stable)


@dataclass(frozen=True)
class IdentityResolution:
    """The pure identity-resolution outcome (SPEC §5)."""
    identity_class: str                  # DETERMINISTIC|CAPTURE_SCOPED
    identity_source: str                 # ''|S2_EXTRACTED_VERIFIED
    identity_fingerprint: str            # '' unless DETERMINISTIC
    reason: str                          # '' | one of the G3 reason codes
    role_resolutions: Tuple[RoleResolution, ...]
    pointer_specs: Tuple[Dict[str, object], ...]   # role → {field_name, field_seq}


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class CanonicalizationLayerError(Exception):
    """Base class for the canonicalization layer."""


class GateDecisionNotFound(CanonicalizationLayerError):
    pass


class GateDecisionDuplicate(CanonicalizationLayerError):
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class CanonicalInvoiceNotFound(CanonicalizationLayerError):
    pass


class GateReviewItemNotFound(CanonicalizationLayerError):
    pass


class CanonicalizationPersistenceUnavailable(CanonicalizationLayerError):
    pass


# ---------------------------------------------------------------------------
# Explicit outcome types — canonicalize() (SPEC §8, exhaustive, never silent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CanonicalizationAccepted:
    decision: GateDecisionRecord
    canonical_invoice: CanonicalInvoiceRecord
    identity_pointers: Tuple[CanonicalIdentityPointer, ...]


@dataclass(frozen=True)
class CanonicalizationRejected:
    decision: GateDecisionRecord


@dataclass(frozen=True)
class CanonicalizationRoutedToReview:
    decision: GateDecisionRecord
    review_item: GateReviewItem


@dataclass(frozen=True)
class CanonicalizationAlreadyCanonicalized:
    decision: GateDecisionRecord
    existing_canonical_invoice: CanonicalInvoiceRecord


@dataclass(frozen=True)
class CanonicalizationAlreadyDecided:
    decision: GateDecisionRecord         # the pre-existing decision, verbatim


@dataclass(frozen=True)
class CanonicalizationInputIntegrityFailure:
    domain_state_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class CanonicalizationRequestRefused:
    domain_state_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class CanonicalizationStorageUnavailable:
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — reads / events / trace (SPEC §8)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateDecisionReadSuccess:
    record: GateDecisionRecord
    canonical_invoice: Optional[CanonicalInvoiceRecord]
    identity_pointers: Tuple[CanonicalIdentityPointer, ...]
    review_item: Optional[GateReviewItem]
    review_status: Optional[str]
    verified_at: str


@dataclass(frozen=True)
class GateDecisionReadIntegrityFailure:
    decision_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class GateDecisionReadRefused:
    decision_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class GateDecisionReadVerificationUnavailable:
    decision_id: Optional[str]
    issue_report: str


@dataclass(frozen=True)
class CanonicalInvoiceReadSuccess:
    record: CanonicalInvoiceRecord
    identity_pointers: Tuple[CanonicalIdentityPointer, ...]
    decision: GateDecisionRecord
    verified_at: str


@dataclass(frozen=True)
class CanonicalInvoiceReadIntegrityFailure:
    canonical_invoice_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class CanonicalInvoiceReadRefused:
    canonical_invoice_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class CanonicalInvoiceReadVerificationUnavailable:
    canonical_invoice_id: Optional[str]
    issue_report: str


@dataclass(frozen=True)
class GateReviewItemReadSuccess:
    item: GateReviewItem
    events: Tuple[GateReviewEvent, ...]
    status: str
    verified_at: str


@dataclass(frozen=True)
class GateReviewItemReadIntegrityFailure:
    review_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class GateReviewItemReadRefused:
    review_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class GateReviewItemReadVerificationUnavailable:
    review_id: Optional[str]
    issue_report: str


@dataclass(frozen=True)
class GateEventAppended:
    event: GateReviewEvent
    status: str


@dataclass(frozen=True)
class GateEventRefused:
    review_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class GateEventUnavailable:
    review_id: Optional[str]
    issue_report: str


@dataclass(frozen=True)
class CanonicalInvoiceTraceSuccess:
    canonical_invoice_id: str
    chain: Tuple[str, ...]               # ordered coarse link verdicts
    verified_at: str


@dataclass(frozen=True)
class CanonicalInvoiceTraceIntegrityFailure:
    canonical_invoice_id: str
    link: str                            # canonical_invoice|gate_decision|domain_state|identity_pointers
    reason: str


@dataclass(frozen=True)
class CanonicalInvoiceTraceRefused:
    canonical_invoice_id: str
    detail: str


@dataclass(frozen=True)
class CanonicalInvoiceTraceVerificationUnavailable:
    canonical_invoice_id: str
    issue_report: str
