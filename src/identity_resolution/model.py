"""Identity Resolution domain model — WP-7.1 MVP implementation.

Binding basis: SPEC-WP71-IDRES (all sections; OD-IR1..IR7 and OD-IR-A..J
delegated details declared across resolver.py / store.py / service.py).

Vocabulary discipline (AS-03/AD-04/CL-1 + dispatch §15 — verbatim, no
paraphrase, no invention):
  - Identity scopes are D-02's model VERBATIM: the S1 Capture Identity is the
    capture_s1 leg of every record (plus the R0 replay behavior); the
    document-identity outcome is S2 | CAPTURE_SCOPED. No fourth scope, no
    synonym status (OD-IR-H).
  - Identity source: S2_EXTRACTED_VERIFIED (D-02's second deterministic path;
    the adapter-document-id path stays RESERVED per P6.1 OD-G5).
  - Roles: the frozen D-02 triad INVOICE_NUMBER | INVOICE_DATE | INVOICE_TOTAL.
  - Origins: the frozen set KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE.
  - UNRESOLVED is NEVER created here (D-01 — P5.2 is its only legal creator);
    ambiguity is preserved as candidate evidence for the Gate/review concern.
  - No invoice_id exists in this layer (D-02 third identity — P6.1/P6.2 own
    issuance; OD-IR-I).

This module is dataclasses + vocabularies + exceptions + explicit outcome
types ONLY — no I/O, no persistence, no clock, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Frozen vocabularies (verbatim — see module docstring)
# ---------------------------------------------------------------------------

IDENTITY_SCOPE_S2 = "S2"
IDENTITY_SCOPE_CAPTURE_SCOPED = "CAPTURE_SCOPED"
IDENTITY_SCOPES = (IDENTITY_SCOPE_S2, IDENTITY_SCOPE_CAPTURE_SCOPED)

IDENTITY_SOURCE_S2 = "S2_EXTRACTED_VERIFIED"          # reused from D-02/P6.1
IDENTITY_SOURCES = ("", IDENTITY_SOURCE_S2)

ROLE_INVOICE_NUMBER = "INVOICE_NUMBER"
ROLE_INVOICE_DATE = "INVOICE_DATE"
ROLE_INVOICE_TOTAL = "INVOICE_TOTAL"
IDENTITY_ROLES = (ROLE_INVOICE_NUMBER, ROLE_INVOICE_DATE, ROLE_INVOICE_TOTAL)

ORIGIN_KANDOO_SALE = "KANDOO_SALE"
ORIGIN_HOLOO_CAPTURE = "HOLOO_CAPTURE"
ORIGIN_OTHER_POS_CAPTURE = "OTHER_POS_CAPTURE"
ORIGINS = (ORIGIN_KANDOO_SALE, ORIGIN_HOLOO_CAPTURE, ORIGIN_OTHER_POS_CAPTURE)
# AS-02: the native flow has no capture pipeline and no P5.2 state; a
# KANDOO_SALE origin on a P5.2-sourced request is refused (fail-closed).
CAPTURE_PIPELINE_ORIGINS = (ORIGIN_HOLOO_CAPTURE, ORIGIN_OTHER_POS_CAPTURE)

# Stable scope_reason codes — the three P6.1 D-03 codes reused VERBATIM
# (OD-IR-D) plus exactly one new code for the R1b route (OD-IR-C).
SCOPE_REASON_D03_INCOMPLETE = "d03-incomplete-document-identity"
SCOPE_REASON_D03_CONFLICTING = "d03-conflicting-document-identity"
SCOPE_REASON_D03_UNDETERMINED = "d03-document-identity-undetermined"
SCOPE_REASON_S2_NOT_ATTEMPTED = "s2-not-attempted-state-not-valid"
CAPTURE_SCOPED_REASONS = (SCOPE_REASON_D03_INCOMPLETE,
                          SCOPE_REASON_D03_CONFLICTING,
                          SCOPE_REASON_D03_UNDETERMINED,
                          SCOPE_REASON_S2_NOT_ATTEMPTED)

# Refusal reason codes (request-level, never durable decisions)
REFUSE_ORIGIN_UNKNOWN = "origin-outside-frozen-vocabulary"
REFUSE_ORIGIN_NATIVE_FLOW = "origin-native-flow-not-consumable-here"
REFUSE_BINDING_MALFORMED = "binding-malformed"
REFUSE_REPLAY_DECLARATION_DRIFT = "replay-declaration-drift"
REFUSE_NO_SUCH_STATE = "no-such-domain-state-record"

# Verify-on-Read failure note (same vocabulary as the other layers)
NOTE_VERIFY_FAILED = "verify FAILED"

# P5.2 state that gates the S2 attempt (OD-G3 verbatim — VALID/CLEAR only)
STATE_VALID = "VALID"
DISPOSITION_CLEAR = "CLEAR"


def utc_now_iso() -> str:
    """Single layer clock (OD-IR4) — UTC ISO-8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Durable records — exact field sets (structurally enforced by boundary tests)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IdentityResolutionRecord:
    """Durable identity resolution — the operational identity fact for ONE
    capture artifact (INV-IR-S1:1: at most one per capture_s1, ever).

    All three D-02 identities are explicit: the Capture Identity (capture_s1),
    the External Document Identity (identity_scope S2|CAPTURE_SCOPED + the
    fingerprint when S2), and NO Canonical Identity (invoice_id is never
    minted, stored, or referenced here — OD-IR-I). Immutable once committed.
    Content determinism is separated from identity: resolution_id / created_at
    are bookkeeping; the identity fingerprint is a pure function of the
    verified inputs + the declared request."""
    resolution_id: str
    capture_s1: str                      # S1 — the capture-level idempotency key
    capture_s1_algorithm_id: str
    capture_id: str
    document_id: str
    extraction_id: str
    normalization_id: str
    domain_state_id: str                 # the verified anchor set (SPEC §9)
    declared_origin: str                 # frozen origins only (storage CHECK)
    binding_declaration_fingerprint: str  # '' = no declaration (OD-IR-B)
    identity_scope: str                  # S2 | CAPTURE_SCOPED (storage CHECK)
    identity_source: str                 # '' | S2_EXTRACTED_VERIFIED
    identity_fingerprint: str            # '' iff CAPTURE_SCOPED (storage CHECK)
    scope_reason: str                    # '' iff S2; stable code otherwise
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class IdentityRoleCandidateRow:
    """One role's candidate evidence — declarations and counts, NEVER values
    (pointer discipline; OD-IR-J). field_seqs is the ascending tuple of
    NORMALIZED field_seq candidates observed in the verified read."""
    resolution_id: str
    role: str                            # frozen D-02 roles only (storage CHECK)
    source_field_name: str
    candidate_count: int                 # 0 | 1 | >=2 (storage CHECK >= 0)
    field_seqs: Tuple[int, ...]
    resolved_field_seq: Optional[int]    # set iff scope S2 (candidate_count=1)


@dataclass(frozen=True)
class IdentityDuplicateObservation:
    """Durable D-03 definite-duplicate fact (append-only, INV-IR-DUP:1): the
    LATER capture's resolution points at the ORIGINAL resolution — one
    document identity, made auditable, never merged away."""
    observation_id: str
    resolution_id: str                   # the later capture's resolution
    original_resolution_id: str
    identity_fingerprint: str
    original_capture_s1: str
    duplicate_capture_s1: str            # != original (storage CHECK)
    created_at: str
    observation_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Pure resolver outcome (resolver.py — wraps the reused P6.1 primitive)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoleCandidateSpec:
    """Per-role candidate metadata produced by the pure resolver — counts and
    pointers only, never values."""
    role: str
    source_field_name: str
    candidate_count: int
    field_seqs: Tuple[int, ...]
    resolved_field_seq: Optional[int]


@dataclass(frozen=True)
class IdentityScopeDecision:
    """The pure identity-resolution outcome (SPEC §4/§5): the document-
    identity scope with its evidence. identity_fingerprint is non-empty iff
    scope is S2."""
    identity_scope: str                  # S2 | CAPTURE_SCOPED
    identity_source: str                 # '' | S2_EXTRACTED_VERIFIED
    identity_fingerprint: str            # '' iff CAPTURE_SCOPED
    scope_reason: str                    # '' iff S2
    role_specs: Tuple[RoleCandidateSpec, ...]


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class IdentityLayerError(Exception):
    """Base class for the identity-resolution layer."""


class ResolutionNotFound(IdentityLayerError):
    pass


class ResolutionDuplicate(IdentityLayerError):
    """INV-IR-S1:1 hit inside the commit transaction (in-txn check or UNIQUE
    backstop) — the existing resolution wins, never a second identity."""
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class IdentityPersistenceUnavailable(IdentityLayerError):
    pass


# ---------------------------------------------------------------------------
# Explicit outcome types — resolve() (SPEC §4/§8, exhaustive, never silent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IdentityResolutionRecorded:
    """A NEW durable resolution was committed (R1+R3, no duplicate)."""
    record: IdentityResolutionRecord
    role_rows: Tuple[IdentityRoleCandidateRow, ...]
    observation: Optional[IdentityDuplicateObservation]


@dataclass(frozen=True)
class IdentityDefiniteDuplicate:
    """A NEW durable resolution was committed for a capture whose exact S2
    identity already exists from a DIFFERENT capture (R2) — the D-03 definite
    duplicate fact rides the same atomic commit."""
    record: IdentityResolutionRecord
    original_resolution: IdentityResolutionRecord
    observation: IdentityDuplicateObservation
    role_rows: Tuple[IdentityRoleCandidateRow, ...]


@dataclass(frozen=True)
class IdentityReplay:
    """S1 replay recognition (R0): the existing resolution returned VERBATIM,
    read-only — one identity, one durable resolution, zero duplicates."""
    record: IdentityResolutionRecord
    role_rows: Tuple[IdentityRoleCandidateRow, ...]
    observation: Optional[IdentityDuplicateObservation]
    verified_at: str


@dataclass(frozen=True)
class IdentityRequestRefused:
    """Request-level refusal (unknown state, bad origin, malformed binding,
    replay declaration drift) — zero durable residue."""
    domain_state_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class IdentityInputIntegrityFailure:
    """Verified-read or provenance failure (V1/V2, tampered existing row) —
    fail closed, zero durable residue."""
    domain_state_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class IdentityStorageUnavailable:
    """Persistence failure — the transaction rolled back, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — verified reads (SPEC §8)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IdentityReadSuccess:
    record: IdentityResolutionRecord
    role_rows: Tuple[IdentityRoleCandidateRow, ...]
    observation: Optional[IdentityDuplicateObservation]
    verified_at: str


@dataclass(frozen=True)
class IdentityReadIntegrityFailure:
    resolution_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class IdentityReadRefused:
    resolution_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class IdentityReadVerificationUnavailable:
    resolution_id: Optional[str]
    issue_report: str


def parse_field_seqs(raw: str) -> Tuple[int, ...]:
    """Parse the deterministic field_seqs serialization (ascending ints,
    comma-joined; '' = none). Storage-format logic kept beside the model so
    store and reader share one definition."""
    if raw == "":
        return ()
    try:
        seqs = tuple(int(part) for part in raw.split(","))
    except ValueError as exc:
        raise IdentityPersistenceUnavailable(
            f"corrupt field_seqs serialization: {raw!r}") from exc
    if list(seqs) != sorted(seqs):
        raise IdentityPersistenceUnavailable(
            f"field_seqs not ascending: {raw!r}")
    return seqs


def serialize_field_seqs(seqs) -> str:
    """Deterministic ascending comma-joined serialization of candidate
    field_seqs (never dependent on iteration order of any mapping)."""
    return ",".join(str(s) for s in sorted(seqs))
