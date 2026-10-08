"""Derivation-layer domain model — WP-4.2 MVP implementation.

Binding basis:
  SPEC-WP42-DER  DERIVED Provenance & Exact Derivation Mechanism Contract v1.0-MVP
                 (produced inline per TM/PO implementation dispatch 2026-10-06)
  REG-WPR §WP-4.2 (rescoped scope of record, PO-approved 2026-10-05)
  D-01 (DERIVED is the ONLY label producible here; UNRESOLVED is owned by P5 and is
       never created, assigned, inferred, or resolved in this layer) | D-08 (no
       rounding — R2 belongs to WP-5.1) | D-09 (delegated details declared in
       store.py/formulas.py/arithmetic.py) | AS-01 flow position
  SPEC-WP41-NORM §2 analog: the verified normalization read is the ONLY sanctioned
  value input path — this layer never reads any store in parallel and never re-reads
  raw artifacts. Evidence-bearing-ness comes from the frozen WP-3.2 verified binding
  read (read-only).

Boundary (normative): this mechanism turns NORMALIZED values into DERIVED values via a
DECLARED, versioned, fingerprinted formula with EXACT arithmetic. It performs NO
line grouping or association discovery, NO semantic/fuzzy matching, NO tax/business
interpretation, NO rounding, NO currency conversion, NO date arithmetic, NO
cross-document derivation, NO general unit_amount computation, NO creation or
resolution of UNRESOLVED, and never silently "fixes" anything — a formula that cannot
execute exactly yields an explicit DEFERRED refusal with a reason code and nothing
else (SPEC §5: NOT_DERIVABLE is a derivation-layer mechanism outcome; DEFERRED ≠
UNRESOLVED).

Every outcome type is explicit; a silent result does not exist in this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Output provenance label (D-01 verbatim — this layer produces DERIVED only)
# ---------------------------------------------------------------------------

OUTPUT_PROVENANCE_DERIVED = "DERIVED"

# ---------------------------------------------------------------------------
# Refusal reason codes (stable, coarse — SPEC §5; NOT_DERIVABLE / mechanism DEFERRED)
# ---------------------------------------------------------------------------

REASON_INPUT_MISSING = "input-missing"        # a declared slot resolved to zero NORMALIZED fields
REASON_INPUT_AMBIGUOUS = "input-ambiguous"    # a declared slot resolved to >1 NORMALIZED fields
REASON_OUTPUT_PRESENT = "output-present"      # output field name already carried by the source record
REASON_NON_EXACT_RESULT = "non-exact-result"  # exact result not a terminating decimal — never rounded

NOTE_VERIFY_FAILED = "verify FAILED"
NOTE_VERIFICATION_UNAVAILABLE = "verification unavailable (no verdict computable)"


def utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with explicit timezone — derivation-layer clock (OD-D4)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Records — exact field sets (structurally enforced by the boundary test)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DerivationInputRef:
    """One durable input POINTER — never a value (SPEC §6 pointer pattern).

    (slot_name, field_name) restate the formula declaration slot that produced this
    row; (source_normalization_id, field_seq, source_extraction_id) point at the exact
    NORMALIZED field consumed. The consumed VALUE lives only in the fingerprint-anchored
    normalization store and is re-joined through verified reads.
    """
    input_slot: int                      # 0-based declaration order of the slot
    slot_name: str                       # declared slot name (e.g. "net")
    field_name: str                      # engine-vocabulary field (e.g. "total.net")
    source_normalization_id: str         # pointer → normalization record (== record's)
    field_seq: int                       # pointer → the exact normalized field
    source_extraction_id: str            # pointer → the owning extraction record


@dataclass(frozen=True)
class DerivationRecord:
    """Durable derivation record — one exact DERIVED value with its full derivation key.

    output_provenance is always 'DERIVED' (D-01; storage CHECK — UNRESOLVED can never
    be stored here). formula_fingerprint pins the exact declared formula version used.
    record_fingerprint anchors record scalars + input-ref rows (sha256-v1), verified
    on every read (VOR).
    """
    derivation_id: str
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    ruleset_id: str
    ruleset_version: str
    formula_id: str
    formula_version: str
    formula_fingerprint: str
    formula_fingerprint_algorithm_id: str
    output_field_name: str
    output_provenance: str               # constant 'DERIVED' (OD-D6 storage gate)
    output_value: str                    # exact canonical decimal string (SPEC §4)
    input_count: int
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class DerivationLayerError(Exception):
    """Base class for all explicit derivation-layer failures."""


class DerivationFormulaError(DerivationLayerError):
    """A formula declaration is malformed (bad op, dangling leaf, arity violation,
    shadowing output name, non-declaration payload, …). Raised at REGISTRATION time —
    a malformed formula can never enter the registry, therefore never execute."""


class DerivationNotFound(DerivationLayerError):
    """The referenced derivation_id does not exist in the store."""


class DerivationDuplicate(DerivationLayerError):
    """INV-D-1:1 — a derivation for (normalization_id, formula_id, formula_version)
    already exists. Raised inside the atomic commit; the service surfaces it as an
    explicit AlreadyExists outcome carrying the existing derivation_id."""

    def __init__(self, derivation_id: str) -> None:
        super().__init__(f"derivation already exists: {derivation_id}")
        self.derivation_id = derivation_id


class DerivationPersistenceUnavailable(DerivationLayerError):
    """D-2 analog: no record durably committed (atomic txn rolled back — zero residue,
    by construction). Never a silent partial write."""


# ---------------------------------------------------------------------------
# Derive outcomes (exhaustive — SPEC §8; consumed from verified normalizations only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DerivationCompleted:
    """Verified normalization + declared formula → exact DERIVED value, durably
    committed (one txn)."""
    record: DerivationRecord
    inputs: tuple


@dataclass(frozen=True)
class DerivationAlreadyExists:
    """INV-D-1:1 replay: the same (normalization_id, formula_id, formula_version) was
    already derived. Explicit, never a silent no-op; no second record is created."""
    derivation_id: str
    normalization_id: str
    formula_id: str
    formula_version: str


@dataclass(frozen=True)
class DerivationFormulaNotRegistered:
    """The requested (formula_id, formula_version) is not in the registry — explicit."""
    normalization_id: str
    formula_id: str
    formula_version: str


@dataclass(frozen=True)
class DerivationDeferred:
    """NOT_DERIVABLE — mechanism-level refusal (SPEC §5). The formula could not execute
    exactly under the declared gates; NO value is produced, nothing is persisted,
    nothing is inferred. This is NOT UNRESOLVED (UNRESOLVED is P5 territory) and it
    never mutates any upstream status or record."""
    normalization_id: str
    formula_id: str
    formula_version: str
    reason_code: str
    detail: str


@dataclass(frozen=True)
class DerivationSourceIntegrityFailure:
    """The source failed its verified read (VOR FAILED) — normalization record or its
    WP-3.2 evidence binding. Nothing derived, nothing persisted."""
    normalization_id: str
    reason: str


@dataclass(frozen=True)
class DerivationSourceRefused:
    """Source explicitly refused (unknown normalization id / no healthy binding for the
    source extraction) — nothing derived."""
    normalization_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DerivationSourceUnavailable:
    """Source verification could not execute (no verdict computable) — nothing derived,
    Issue-Report surfaced."""
    normalization_id: str
    issue_report: str


@dataclass(frozen=True)
class DerivationStorageUnavailable:
    """D-2 analog: nothing recordable — nothing persisted, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Read outcomes (VOR pattern — exhaustive; no silent broken read exists)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DerivationReadSuccess:
    """Stored record + input refs delivered ONLY together with the same-read VALID
    verdict."""
    record: DerivationRecord
    inputs: tuple
    verified_at: str


@dataclass(frozen=True)
class DerivationReadIntegrityFailure:
    """Definitive FAILED verdict (stored bytes no longer match the committed
    fingerprint); the stored (broken) content is NEVER delivered."""
    derivation_id: str
    reason: str
    verified_at: str


@dataclass(frozen=True)
class DerivationReadRefused:
    """Unknown derivation_id — nothing delivered, no verdict, no state change."""
    derivation_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DerivationReadVerificationUnavailable:
    """No verdict computable (e.g. unknown fingerprint algorithm id / structural
    inconsistency) — no content, Issue-Report surfacing."""
    derivation_id: str
    issue_report: str


# ---------------------------------------------------------------------------
# Trace outcomes (provenance walk — every link re-verified inside one call, SPEC §10)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DerivationTraceSuccess:
    """The full chain held under verified reads in THIS walk — pointers only, no
    source values copied forward."""
    derivation_id: str
    chain: tuple                        # ordered coarse link summaries (strings)


@dataclass(frozen=True)
class DerivationTraceIntegrityFailure:
    """The named link of the chain failed its verified read during the walk."""
    derivation_id: str
    link: str                           # derivation|normalization|extraction|binding|document
    reason: str


@dataclass(frozen=True)
class DerivationTraceRefused:
    """A chain link refused (missing record) — the chain cannot be walked."""
    derivation_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class DerivationTraceVerificationUnavailable:
    """A chain link could not be verified (no verdict computable) — Issue-Report."""
    derivation_id: str
    issue_report: str
