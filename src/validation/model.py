"""Validation-layer domain model — WP-5.1 MVP implementation.

Binding basis:
  SPEC-WP51-VAL  R1/R2 Validation Engine Contract v1.0-MVP (produced inline per
                 TM/PO implementation dispatch 2026-10-07)
  REG-WPR Phase Index P5 (WP-5.1 R1/R2 Engine) + PO dispatch 2026-10-07
  D-01 (UNRESOLVED is owned by the P5 domain layer — this engine never creates,
       assigns, infers, or resolves it) | D-08 (R2 rounding/tolerance parametric,
       no fixed value; unresolved mismatch → REVIEW path downstream) | D-09
       (delegated details declared in rules.py/rounding.py/store.py) | AD-02
       (Validation domain boundary) | AD-04 + AS-03 (Validation State Machine and
       its verbatim frozen vocabulary are WP-5.2 — this layer defines NO invoice
       states) | AS-01 (pipeline position: P3 → P4.1 → P4.2 → P5.1).
  SPEC-WP42-DER §2 analog: verified reads are the ONLY sanctioned input paths —
  NORMALIZED values via frozen WP-4.1, DERIVED values via the WP-4.2 service;
  this layer never reads any store in parallel and never re-reads raw artifacts.

Boundary (normative): this engine applies DECLARED, versioned, fingerprinted R1/R2
rules to pipeline values and produces VERDICTS. It performs NO canonical field
mapping, NO line grouping or association discovery, NO product/customer/identity
matching, NO semantic/fuzzy matching, NO business-rule inference, NO tax-rate/
discount/markup/currency logic, NO date arithmetic, NO cross-document validation,
NO creation or resolution of UNRESOLVED, and NO value production — the only
"output-like" data is the rounding audit record inside an R2 result, which is an
audit artifact of the comparison, never a pipeline value. A rule that cannot decide
yields an explicit durable DEFERRED with a stable reason code (DEFERRED ≠
UNRESOLVED). Every outcome type is explicit; a silent result does not exist here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Rule kinds and outcomes (SPEC §3/§5 — explicit, exhaustive)
# ---------------------------------------------------------------------------

RULE_KIND_R1 = "R1"   # structural / consistency rules (no tolerance, no rounding)
RULE_KIND_R2 = "R2"   # parametric / rounding rules (D-08)

OUTCOME_VALID = "VALID"          # declared rule holds under exact evaluation
OUTCOME_INVALID = "INVALID"      # decidable comparison failed — rule violated
OUTCOME_DEFERRED = "DEFERRED"    # insufficient information to decide (durable
                                 # non-decision; DEFERRED ≠ UNRESOLVED — the
                                 # UNRESOLVED domain label is never produced here)

VALUE_ORIGIN_NORMALIZED = "NORMALIZED"   # input resolved from WP-4.1 fields
VALUE_ORIGIN_DERIVED = "DERIVED"         # input resolved from WP-4.2 records

# Reason codes (stable, coarse — SPEC §5)
REASON_EXACT_MATCH = "exact-match"
REASON_WITHIN_TOLERANCE = "within-tolerance"
REASON_ROUNDED_MATCH = "rounded-match"
REASON_ABSENT = "absent"
REASON_PRESENT_NOT_USABLE = "present-not-usable"
REASON_MISMATCH = "mismatch"
REASON_MISMATCH_BEYOND_TOLERANCE = "mismatch-beyond-tolerance"
REASON_MISMATCH_AFTER_ROUNDING = "mismatch-after-rounding"
REASON_INSUFFICIENT_INPUT = "insufficient-input"
REASON_AMBIGUOUS_INPUT = "ambiguous-input"
REASON_NON_EXACT_INTERMEDIATE = "non-exact-intermediate"

NOTE_VERIFY_FAILED = "verify FAILED"
NOTE_VERIFICATION_UNAVAILABLE = "verification unavailable (no verdict computable)"


def utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with explicit timezone — validation-layer clock (OD-V4)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Records — exact field sets (structurally enforced by the boundary test)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationInputRef:
    """One durable input POINTER — never a value (SPEC §6 pointer pattern).

    NORMALIZED inputs point at (source_normalization_id, source_field_seq) inside
    the WP-4.1 store; DERIVED inputs point at source_derivation_id — the WP-4.2
    record whose own provenance chain stays intact and is re-joined through
    verified reads (§10). Consumed VALUES live only in the fingerprint-anchored
    upstream stores.
    """
    input_slot: int                      # 0-based declaration order of the slot
    slot_name: str                       # declared slot name (e.g. "target")
    field_name: str                      # engine-vocabulary field (e.g. "total.gross")
    value_origin: str                    # 'NORMALIZED' | 'DERIVED' (storage CHECK)
    source_normalization_id: str         # pointer → the scope normalization record
    source_extraction_id: str            # pointer → the owning extraction record
    source_field_seq: Optional[int]      # pointer → normalized field (NORMALIZED only)
    source_derivation_id: Optional[str]  # pointer → derivation record (DERIVED only)


@dataclass(frozen=True)
class ValidationRecord:
    """Durable validation record — one declared rule's verdict over one validation
    scope, with its full provenance anchors.

    outcome is one of VALID | INVALID | DEFERRED (storage CHECK — UNRESOLVED can
    never be stored here). rule_fingerprint pins the exact declared rule version
    used. Rounding fields are populated iff rounding_applied = 1 (R2
    rounded-equality only — R1 can never round; storage CHECK). record_fingerprint
    anchors record scalars + input-ref rows (sha256-v1), verified on every read.
    """
    validation_id: str
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    ruleset_id: str
    ruleset_version: str
    rule_id: str
    rule_version: str
    rule_kind: str                       # 'R1' | 'R2' (storage CHECK)
    rule_type: str                       # declared rule type (SPEC §3)
    rule_fingerprint: str
    rule_fingerprint_algorithm_id: str
    outcome: str                         # 'VALID' | 'INVALID' | 'DEFERRED' (CHECK)
    outcome_reason: str                  # stable coarse reason (SPEC §5)
    outcome_detail: str
    rounding_applied: int                # 0 | 1 (storage CHECK)
    rounding_precision: Optional[int]    # populated iff rounding_applied = 1
    rounding_mode: Optional[str]         # populated iff rounding_applied = 1
    rounding_input_value: Optional[str]  # exact expression value before rounding
    rounding_output_value: Optional[str] # rounded comparison value (AUDIT artifact —
                                         # never a pipeline value)
    input_count: int
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class ValidationLayerError(Exception):
    """Base class for all explicit validation-layer failures."""


class ValidationRuleError(ValidationLayerError):
    """A rule declaration is malformed (bad kind/type pairing, dangling slot leaf,
    non-canonical tolerance, unknown rounding mode, literal/callable payload, …).
    Raised at REGISTRATION time — a malformed rule can never enter the registry,
    therefore never execute."""


class ValidationNotFound(ValidationLayerError):
    """The referenced validation_id does not exist in the store."""


class ValidationDuplicate(ValidationLayerError):
    """INV-V-1:1 — a validation for (normalization_id, rule_id, rule_version)
    already exists. Raised inside the atomic commit; the service surfaces it as an
    explicit AlreadyExists outcome carrying the existing validation_id."""

    def __init__(self, validation_id: str) -> None:
        super().__init__(f"validation already exists: {validation_id}")
        self.validation_id = validation_id


class ValidationPersistenceUnavailable(ValidationLayerError):
    """D-2 analog: no record durably committed (atomic txn rolled back — zero
    residue, by construction). Never a silent partial write."""


# ---------------------------------------------------------------------------
# Validate outcomes (exhaustive — SPEC §8; consumed from verified sources only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationCompleted:
    """Verified sources + declared rule → explicit verdict, durably committed
    (one txn)."""
    record: ValidationRecord
    inputs: tuple


@dataclass(frozen=True)
class ValidationAlreadyExists:
    """INV-V-1:1 replay: the same (normalization_id, rule_id, rule_version) was
    already validated. Explicit, never a silent no-op; no second record is created.
    Re-evaluation after pipeline state changed uses a NEW rule_version (§7)."""
    validation_id: str
    normalization_id: str
    rule_id: str
    rule_version: str


@dataclass(frozen=True)
class ValidationRuleNotRegistered:
    """The requested (rule_id, rule_version) is not in the registry — explicit."""
    normalization_id: str
    rule_id: str
    rule_version: str


@dataclass(frozen=True)
class ValidationSourceIntegrityFailure:
    """A source failed its verified read (VOR FAILED) — normalization record, its
    WP-3.2 evidence binding, or a referenced WP-4.2 derivation record. Nothing
    validated."""
    normalization_id: str
    reason: str


@dataclass(frozen=True)
class ValidationSourceRefused:
    """Source explicitly refused (unknown normalization id / no healthy binding for
    the source extraction) — nothing validated."""
    normalization_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class ValidationSourceUnavailable:
    """Source verification could not execute (no verdict computable) — nothing
    validated, Issue-Report surfaced."""
    normalization_id: str
    issue_report: str


@dataclass(frozen=True)
class ValidationStorageUnavailable:
    """D-2 analog: nothing recordable — nothing persisted, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Read outcomes (VOR pattern — exhaustive; no silent broken read exists)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationReadSuccess:
    """Stored record + input refs delivered ONLY together with the same-read VALID
    verdict."""
    record: ValidationRecord
    inputs: tuple
    verified_at: str


@dataclass(frozen=True)
class ValidationReadIntegrityFailure:
    """Definitive FAILED verdict (stored bytes no longer match the committed
    fingerprint); the stored (broken) content is NEVER delivered."""
    validation_id: str
    reason: str
    verified_at: str


@dataclass(frozen=True)
class ValidationReadRefused:
    """Unknown validation_id — nothing delivered, no verdict, no state change."""
    validation_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class ValidationReadVerificationUnavailable:
    """No verdict computable (e.g. unknown fingerprint algorithm id / structural
    inconsistency) — no content, Issue-Report surfacing."""
    validation_id: str
    issue_report: str


# ---------------------------------------------------------------------------
# Trace outcomes (provenance walk — every link re-verified inside one call, §10)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationTraceSuccess:
    """The full chain held under verified reads in THIS walk — pointers only, no
    source values copied forward."""
    validation_id: str
    chain: tuple                        # ordered coarse link summaries (strings)


@dataclass(frozen=True)
class ValidationTraceIntegrityFailure:
    """The named link of the chain failed its verified read during the walk."""
    validation_id: str
    link: str    # validation|normalization|derivation|extraction|binding|document
    reason: str


@dataclass(frozen=True)
class ValidationTraceRefused:
    """A chain link refused (missing record) — the chain cannot be walked."""
    validation_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class ValidationTraceVerificationUnavailable:
    """A chain link could not be verified (no verdict computable) — Issue-Report."""
    validation_id: str
    issue_report: str
