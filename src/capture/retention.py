"""Retention Evaluation Gate — WP-1.3 mechanics-only implementation.

Binding basis: SPEC-WP13-RETR v1.0-MVP (§2, §5, §6) over the frozen WP-1.1 layer
(Contract v1.1 | Store Design v0.2 | S1 Design v1.0 | VOR Design v1.0).

WHAT THIS MODULE IS
    A pure evaluator that turns (a) a durable Capture Record and (b) an INJECTED
    retention policy into an explicit, typed retention decision. It answers exactly
    two questions: "is this record a retention candidate under the policy given to
    me?" and "may a purge be executed?". It writes nothing and reads nothing.

WHAT THIS MODULE IS NOT (normative)
    DEF4 (Capture Artifact Retention / Privacy) has NO ratified policy VALUES.
    Therefore:
      - this module contains NO retention duration, NO TTL, NO privacy marking,
        NO sharing rule and NO purge-authorization scheme of its own;
      - every policy-bearing value must arrive from the caller. There is no
        default, and no fallback value exists anywhere in this module;
      - a missing/blank policy value is a typed REFUSAL, never a guess
        (Contract §14 "no guessed values" extended to the retention boundary);
      - the purge path is GATE-ONLY by construction: unauthorized purge requests
        are refused, eligible candidates are reported, and NO physical deletion
        is performed or even implemented here.

Determinism (AC-1.3.4)
    No clock is used. The evaluation instant is an explicit parameter
    (``evaluation_time``); the same (record, policy, evaluation_time) triple always
    yields a byte-identical decision. This module never calls ``datetime.now``,
    ``time.time`` or any OS clock (structurally proven by the WP-1.3 AST probe).

Delegated implementation details (declared per D-09, in SPEC-WP13-RETR §10):
    OD-RT-A  duration arithmetic on ISO-8601 text only; both operands must be
             tz-aware or the input is refused (no timezone guessing).
    OD-RT-B  the policy object validates itself at construction; partial policies
             cannot exist (no "half-configured TTL" state is representable).
    OD-RT-C  the purge gate closure is a constant, not a policy value: it is not
             configurable at runtime, and no fabricated authorization object can
             open it. Re-opening it is a DEF4 PO decision, never a code change
             inside a WP.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Optional

from .s1 import S1_ALGORITHM_ID

# ---------------------------------------------------------------------------
# Fixed vocabulary (SPEC-WP13-RETR §3) — the only outcomes this gate can produce
# ---------------------------------------------------------------------------

RETENTION_OUTCOME_ELIGIBLE = "ELIGIBLE_CANDIDATE"
RETENTION_OUTCOME_NOT_ELIGIBLE = "NOT_ELIGIBLE"
RETENTION_OUTCOME_POLICY_UNDECLARED = "POLICY_UNDECLARED"
RETENTION_OUTCOME_STATE_REFUSED = "STATE_REFUSED"
RETENTION_OUTCOME_INTEGRITY_DEFERRED = "INTEGRITY_DEFERRED"
RETENTION_OUTCOME_DATA_ANOMALY = "DATA_ANOMALY"
RETENTION_OUTCOME_PURGE_GATE_BLOCKED = "PURGE_GATE_BLOCKED"

RETENTION_OUTCOMES = frozenset({
    RETENTION_OUTCOME_ELIGIBLE,
    RETENTION_OUTCOME_NOT_ELIGIBLE,
    RETENTION_OUTCOME_POLICY_UNDECLARED,
    RETENTION_OUTCOME_STATE_REFUSED,
    RETENTION_OUTCOME_INTEGRITY_DEFERRED,
    RETENTION_OUTCOME_DATA_ANOMALY,
    RETENTION_OUTCOME_PURGE_GATE_BLOCKED,
})

# The explicit DEF4 marker (mission requirement: "Explicit DEF4-pending labels").
# Every decision carries it so no downstream consumer can mistake a candidate for
# an authorized action.
DEF4_PENDING_LABEL = "DEF4-PENDING"

# Basis of age measurement — a MECHANICS enumeration, not a policy value: it names
# which of the record's two existing frozen timestamps is used. Which one a policy
# actually selects is a DEF4 decision supplied by the caller.
RETENTION_BASIS_CREATED_AT = "created_at"
RETENTION_BASIS_RECEIVED_AT = "received_at"
RETENTION_BASES = frozenset({RETENTION_BASIS_CREATED_AT, RETENTION_BASIS_RECEIVED_AT})

PURGE_GATE_REASON_DEF4 = (
    "physical purge is not executable: no PO-ratified retention/privacy policy "
    "exists (DEF4-PENDING) — gate-only interpretation per SPEC-WP13-RETR §6"
)

# OD-RT-C: the gate is closed by construction. This is NOT a policy value — it is
# the registered absence of one. Nothing in the layer may read it as "configurable".
PURGE_EXECUTION_ALLOWED = False

# Explicit marker for "the caller did not supply this policy field".
POLICY_VALUE_UNSPECIFIED = "__UNSPECIFIED__"


# ---------------------------------------------------------------------------
# Exceptions — every refusal is explicit and typed (no silent path)
# ---------------------------------------------------------------------------

class RetentionLayerError(Exception):
    """Base class for all explicit WP-1.3 retention refusals."""


class RetentionPolicyIncomplete(RetentionLayerError):
    """OD-RT-B: a policy-bearing field was left unspecified. Nothing is evaluated."""

    def __init__(self, missing: tuple, detail: str = "") -> None:
        super().__init__(detail or f"retention policy fields left unspecified: {sorted(missing)}")
        self.missing = tuple(sorted(missing))


class RetentionIllegalInput(RetentionLayerError):
    """A structural input (not a record, an unknown basis, a bad key) was refused."""


# ---------------------------------------------------------------------------
# The injected policy — shape only, no values (DEF4 boundary)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetentionPolicy:
    """A retention policy SUPPLIED BY THE CALLER. Every field is mandatory and has
    NO default (OD-RT-B): a partially specified policy is not representable, so a
    missing value cannot silently become a "0 days"/"keep forever"/"delete now"
    behaviour.

    Fields
      policy_id            — opaque label for the policy under evaluation
      basis                — which frozen timestamp age is measured from (RETENTION_BASES)
      cutoff_seconds       — the retention window, in seconds, as an injected value.
                             None/unspecified → refusal. This module never proposes one.
      privacy_marking      — the injected privacy classification label (never guessed;
                             absence → refusal, because candidate reporting is a
                             policy-bearing act per DEF4)
      candidate_reporting  — whether candidate reporting is permitted by the policy
                             (bool, explicitly supplied; no default)
    """
    policy_id: Optional[str] = None
    basis: Optional[str] = None
    cutoff_seconds: Optional[int] = None
    privacy_marking: Optional[str] = None
    candidate_reporting: Optional[bool] = None

    REQUIRED_FIELDS = (
        "policy_id", "basis", "cutoff_seconds", "privacy_marking", "candidate_reporting",
    )

    def __post_init__(self) -> None:
        missing = []
        for name in self.REQUIRED_FIELDS:
            value = getattr(self, name)
            if value is None or value == POLICY_VALUE_UNSPECIFIED:
                missing.append(name)
        if missing:
            raise RetentionPolicyIncomplete(tuple(missing))
        if self.basis not in RETENTION_BASES:
            raise RetentionIllegalInput(
                f"policy basis {self.basis!r} is outside {sorted(RETENTION_BASES)}")
        if not isinstance(self.cutoff_seconds, int) or isinstance(self.cutoff_seconds, bool):
            raise RetentionIllegalInput("policy cutoff_seconds must be an injected integer")
        if self.cutoff_seconds < 0:
            raise RetentionIllegalInput("policy cutoff_seconds must not be negative")
        if not isinstance(self.candidate_reporting, bool):
            raise RetentionIllegalInput("policy candidate_reporting must be an explicit bool")
        if not isinstance(self.policy_id, str) or not self.policy_id:
            raise RetentionIllegalInput("policy_id must be a non-empty opaque label")
        if not isinstance(self.privacy_marking, str) or not self.privacy_marking:
            raise RetentionIllegalInput("privacy_marking must be an explicit injected label")

    # -- introspection used by the AC tests ---------------------------------

    @classmethod
    def unsupplied(cls) -> "RetentionPolicy":
        """The canonical 'no values' construction — always refused (OD-RT-B)."""
        return cls()

    @classmethod
    def defaultless_field_names(cls) -> tuple:
        """Field names carrying no non-None dataclass default (asserted by tests)."""
        import inspect
        sig = inspect.signature(cls)
        return tuple(
            name for name, p in sig.parameters.items()
            if p.default is None or p.default == POLICY_VALUE_UNSPECIFIED
        )

    def to_canonical_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


# ---------------------------------------------------------------------------
# Decisions — exhaustive, explicit, typed
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetentionDecision:
    """Common carrier for every evaluation result. ``detail`` is a coarse, structural
    reason string; no artifact content and no downstream/canonical datum ever appears
    (INV-C7/INV-C8 preserved at this boundary)."""
    outcome: str
    capture_id: Optional[str]
    policy_id: Optional[str]
    evaluation_time: Optional[str]
    policy_status_label: str = DEF4_PENDING_LABEL
    age_seconds: Optional[int] = None
    remaining_seconds: Optional[int] = None
    detail: Optional[str] = None

    def to_canonical_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "capture_id": self.capture_id,
            "policy_id": self.policy_id,
            "evaluation_time": self.evaluation_time,
            "policy_status_label": self.policy_status_label,
            "age_seconds": self.age_seconds,
            "remaining_seconds": self.remaining_seconds,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PurgeGateDecision:
    """The ONLY answer a purge request can ever receive from this layer (gate-only)."""
    outcome: str                 # always PURGE_GATE_BLOCKED
    executed: bool               # always False
    rows_affected: int           # always 0
    reason: str
    capture_id: Optional[str] = None
    policy_id: Optional[str] = None
    policy_status_label: str = DEF4_PENDING_LABEL

    def to_canonical_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "executed": self.executed,
            "rows_affected": self.rows_affected,
            "reason": self.reason,
            "capture_id": self.capture_id,
            "policy_id": self.policy_id,
            "policy_status_label": self.policy_status_label,
        }


# ---------------------------------------------------------------------------
# Timestamp mechanics (OD-RT-A)
# ---------------------------------------------------------------------------

def parse_aware_iso(text: str) -> datetime:
    """Parse an ISO-8601 instant that carries an explicit offset.

    Naive text is REFUSED, never assumed to be UTC — assuming an offset would be
    inventing a value (Contract §14 discipline).
    """
    if not isinstance(text, str) or not text.strip():
        raise RetentionIllegalInput("timestamp must be a non-empty ISO-8601 string")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RetentionIllegalInput(f"unparseable ISO-8601 timestamp: {exc}") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise RetentionIllegalInput(
            "timestamp carries no explicit UTC offset — refusing to guess a timezone")
    return moment


def is_aware_iso(text: str) -> bool:
    try:
        parse_aware_iso(text)
    except RetentionIllegalInput:
        return False
    return True


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_retention(record, *, policy=None, evaluation_time=None) -> RetentionDecision:
    """Evaluate one Capture Record against an injected policy at an injected instant.

    Fail-closed ordering (each step can only REFUSE, never repair):
      R1 policy absent / incomplete      → POLICY_UNDECLARED
      R2 evaluation instant absent/bad   → DATA_ANOMALY (a clock is never read here)
      R3 record not COMPLETED            → STATE_REFUSED  (recovery owns unresolved state)
      R4 COMPLETED but integrity FAILED  → INTEGRITY_DEFERRED (evidence conflict → review)
      R4b foreign s1_algorithm_id        → INTEGRITY_DEFERRED (untrusted fingerprint
                                            binding → review; never a candidate — §2.8)
      R5 basis timestamp unparseable     → DATA_ANOMALY
      otherwise                          → ELIGIBLE_CANDIDATE | NOT_ELIGIBLE
    """
    capture_id = getattr(record, "capture_id", None)

    if not isinstance(policy, RetentionPolicy):
        return RetentionDecision(
            outcome=RETENTION_OUTCOME_POLICY_UNDECLARED,
            capture_id=capture_id,
            policy_id=getattr(policy, "policy_id", None),
            evaluation_time=evaluation_time,
            detail="no retention policy was injected; DEF4 has no ratified values "
                   "and this layer invents none — nothing is evaluated",
        )

    if evaluation_time is None:
        return RetentionDecision(
            outcome=RETENTION_OUTCOME_DATA_ANOMALY,
            capture_id=capture_id,
            policy_id=policy.policy_id,
            evaluation_time=None,
            detail="evaluation_time is mandatory: this module owns no clock, so an "
                   "elapsed-time verdict cannot be produced from wall-clock state",
        )

    state = getattr(record, "capture_state", None)
    state_value = getattr(state, "value", state)
    if state_value != "COMPLETED":
        return RetentionDecision(
            outcome=RETENTION_OUTCOME_STATE_REFUSED,
            capture_id=capture_id,
            policy_id=policy.policy_id,
            evaluation_time=evaluation_time,
            detail=f"retention evaluation serves COMPLETED records only "
                   f"(record state={state_value!r}); unresolved residue is settled by "
                   f"recovery, never by a retention decision",
        )

    integrity = getattr(record, "integrity_status", None)
    integrity_value = getattr(integrity, "value", integrity)
    if integrity_value == "FAILED":
        return RetentionDecision(
            outcome=RETENTION_OUTCOME_INTEGRITY_DEFERRED,
            capture_id=capture_id,
            policy_id=policy.policy_id,
            evaluation_time=evaluation_time,
            detail="integrity_status=FAILED on a COMPLETED record is an evidence "
                   "conflict: it is surfaced for review, not converted into a "
                   "retention candidate (REVIEW beats guessing)",
        )

    # Contract §2.8: a fingerprint algorithm foreign to the frozen binding is the
    # NO-VERDICT class — no trustworthy age/eligibility verdict can rest on such a
    # record, so it is deferred to review and can never become a candidate.
    algorithm_id = getattr(record, "s1_algorithm_id", None)
    if algorithm_id is not None and algorithm_id != S1_ALGORITHM_ID:
        return RetentionDecision(
            outcome=RETENTION_OUTCOME_INTEGRITY_DEFERRED,
            capture_id=capture_id,
            policy_id=policy.policy_id,
            evaluation_time=evaluation_time,
            detail=f"s1_algorithm_id={algorithm_id!r} is foreign to the frozen "
                   f"{S1_ALGORITHM_ID} binding: no verdict is computed for it and it "
                   f"is deferred to review instead of becoming a retention candidate "
                   f"(REVIEW beats guessing, Contract §2.8)",
        )

    basis_text = getattr(record, policy.basis, None)
    try:
        basis_moment = parse_aware_iso(basis_text)
        moment_now = parse_aware_iso(evaluation_time)
    except RetentionIllegalInput as exc:
        return RetentionDecision(
            outcome=RETENTION_OUTCOME_DATA_ANOMALY,
            capture_id=capture_id,
            policy_id=policy.policy_id,
            evaluation_time=evaluation_time,
            detail=f"timestamp mechanics refused the input: {exc}",
        )

    age_seconds = int((moment_now - basis_moment).total_seconds())
    cutoff = policy.cutoff_seconds

    if age_seconds < 0:
        return RetentionDecision(
            outcome=RETENTION_OUTCOME_DATA_ANOMALY,
            capture_id=capture_id,
            policy_id=policy.policy_id,
            evaluation_time=evaluation_time,
            detail=f"evaluation_time precedes the record's own {policy.basis} "
                   f"(age={age_seconds}s): a negative age is an anomaly, never a "
                   f"verdict of 'old enough'",
        )

    if age_seconds >= cutoff:
        if not policy.candidate_reporting:
            return RetentionDecision(
                outcome=RETENTION_OUTCOME_NOT_ELIGIBLE,
                capture_id=capture_id,
                policy_id=policy.policy_id,
                evaluation_time=evaluation_time,
                age_seconds=age_seconds,
                remaining_seconds=0,
                detail=f"age {age_seconds}s meets the injected cutoff {cutoff}s but the "
                       f"policy does not permit candidate reporting; no candidate is "
                       f"produced",
            )
        return RetentionDecision(
            outcome=RETENTION_OUTCOME_ELIGIBLE,
            capture_id=capture_id,
            policy_id=policy.policy_id,
            evaluation_time=evaluation_time,
            age_seconds=age_seconds,
            remaining_seconds=0,
            detail=f"eligible retention CANDIDATE under injected policy "
                   f"(age={age_seconds}s ≥ cutoff={cutoff}s); reporting a candidate is "
                   f"not executing anything",
        )

    return RetentionDecision(
        outcome=RETENTION_OUTCOME_NOT_ELIGIBLE,
        capture_id=capture_id,
        policy_id=policy.policy_id,
        evaluation_time=evaluation_time,
        age_seconds=age_seconds,
        remaining_seconds=cutoff - age_seconds,
        detail=f"within the injected retention window (age={age_seconds}s < cutoff={cutoff}s)",
    )


# ---------------------------------------------------------------------------
# Purge — gate-only (no deletion exists, anywhere in this module)
# ---------------------------------------------------------------------------

def request_purge(capture_id: Optional[str] = None, *, policy=None, authorization=None) -> PurgeGateDecision:
    """The purge request entry point. It can only ever return a BLOCKED decision.

    There is deliberately no companion "execute" function: the WP-1.3 deliverable is
    the gate + candidate reporting, and physical deletion stays blocked until a PO
    policy exists for DEF4. A caller cannot open the gate by supplying an
    authorization object — ``authorization`` is recorded as refused, never trusted,
    because no PO-ratified issuer exists to verify it against (OD-RT-C).
    """
    policy_id = getattr(policy, "policy_id", None)
    detail = PURGE_GATE_REASON_DEF4
    if authorization is not None:
        detail = (
            f"{PURGE_GATE_REASON_DEF4}; the supplied authorization object cannot be "
            f"verified because no PO-ratified authorization scheme exists — an "
            f"unverifiable credential is refused, never accepted"
        )
    return PurgeGateDecision(
        outcome=RETENTION_OUTCOME_PURGE_GATE_BLOCKED,
        executed=False,
        rows_affected=0,
        reason=detail,
        capture_id=capture_id,
        policy_id=policy_id,
    )
