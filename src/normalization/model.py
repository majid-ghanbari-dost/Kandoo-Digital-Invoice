"""Normalization-layer domain model — WP-4.1 MVP implementation.

Binding basis:
  SPEC-WP41-NORM  Normalization Contract v1.0-MVP (produced inline per TM dispatch 2026-10-01)
  D-01 (provenance vocabulary EXTRACTED | DERIVED | UNRESOLVED — relayed verbatim, never
       re-decided here) | D-02/D-03 untouched | D-09 (no engine selection; ruleset is a seam) |
  AS-01 flow position: Extraction → **Normalization** → Canonicalization Gate.
  SPEC-WP31-EXT §2 analog: the verified extraction read is the ONLY sanctioned input path —
  this layer never reads extraction/document/capture stores in parallel.

Boundary (normative): Normalization turns verified extracted values into deterministic,
structurally stable data for the future Canonicalization Gate. It performs NO canonical
field mapping, NO product/customer/invoice identity, NO fuzzy/semantic matching, NO
business rules, NO currency invention/conversion, NO DERIVED computation (WP-4.2), NO
unit_amount calculation from other fields, NO semantic arithmetic between fields, NO
inference of missing business values, and never silently "fixes" a value — anything
outside the declared grammar gets an explicit per-field DEFERRED/REJECTED status with a
reason code (SPEC §4.1/§4.2: DEFERRED is a normalization-layer outcome; DEFERRED ≠
UNRESOLVED — UNRESOLVED is never created, assigned, inferred, or resolved here).

Every outcome type is explicit; a silent result does not exist in this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

# ---------------------------------------------------------------------------
# Per-field status vocabulary (SPEC §4 — explicit, exhaustive)
# ---------------------------------------------------------------------------

class NormalizationStatus(str, Enum):
    NORMALIZED = "NORMALIZED"      # declared grammar applied → normalized_value present
    DEFERRED = "DEFERRED"          # normalization-layer outcome (SPEC §4.1): value outside
                                   # the declared grammar — no interpretation, nothing
                                   # invented, passed forward. DEFERRED ≠ UNRESOLVED
                                   # (UNRESOLVED is a later domain/validation concept and
                                   # is never created/assigned/inferred/resolved here).
    REJECTED = "REJECTED"          # structural corruption marker (control characters)


# Reason codes (stable, coarse — no content interpretation)
REASON_EMPTY_VALUE = "empty-value"
REASON_NOT_IN_DECLARED_GRAMMAR = "not-in-declared-grammar"
REASON_CONTROL_CHARACTER = "control-character"

NOTE_VERIFY_FAILED = "verify FAILED"
NOTE_VERIFICATION_UNAVAILABLE = "verification unavailable (no verdict computable)"


def utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with explicit timezone — normalization-layer clock (OD-N4)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Records — exact field sets (structurally enforced by the boundary test)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizedField:
    """One normalized field — TOTAL positional mapping of its source extracted field.

    (extraction_id is carried by the record; field_seq mirrors the source field_seq.)
    source_provenance relays the D-01 label of the source field verbatim — this layer
    never produces DERIVED/UNRESOLVED. normalized_value is present iff status is
    NORMALIZED; reason_code is present iff status is not NORMALIZED (OD-N6 gates).
    """
    field_seq: int                       # mirrors source field_seq (deterministic order)
    source_field_name: str               # engine vocabulary, relayed (no canonical mapping)
    source_provenance: str               # 'EXTRACTED' (relayed verbatim; storage CHECK)
    status: NormalizationStatus
    normalized_value: Optional[str]      # canonical value; NULL unless NORMALIZED
    rules_applied: str                   # e.g. "nfc,trim,number-canonical"; "" if not NORMALIZED
    reason_code: Optional[str]           # stable reason; NULL iff NORMALIZED


@dataclass(frozen=True)
class NormalizationRecord:
    """Durable normalization record — full traceability to Extraction (and, through it,
    Document AND Capture). Content-determinism is separated from identity: the uuid4
    normalization_id / created_at are bookkeeping scalars; the normalized CONTENT is a pure
    function of (source extraction content, ruleset_id, ruleset_version) — INV-N-1:1 makes
    the identity unique so no mutable duplicate can drift (SPEC §6)."""
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    engine_id: str
    engine_schema_version: str
    ruleset_id: str
    ruleset_version: str
    field_count: int
    normalized_count: int
    deferred_count: int
    rejected_count: int
    created_at: str
    record_fingerprint: str              # sha256-v1 over the canonical record+fields bytes
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class NormalizationLayerError(Exception):
    """Base class for all explicit normalization-layer failures."""


class NormalizationNotFound(NormalizationLayerError):
    """The referenced normalization_id does not exist in the store."""


class NormalizationDuplicate(NormalizationLayerError):
    """INV-N-1:1 — a record for (extraction_id, ruleset_id, ruleset_version) already
    exists. Raised inside the atomic commit; the service surfaces it as an explicit
    AlreadyExists outcome carrying the existing normalization_id."""

    def __init__(self, normalization_id: str) -> None:
        super().__init__(f"normalization already exists: {normalization_id}")
        self.normalization_id = normalization_id


class NormalizationPersistenceUnavailable(NormalizationLayerError):
    """D-2 analog: no record durably committed (atomic txn rolled back — zero residue,
    by construction). Never a silent partial write."""


# ---------------------------------------------------------------------------
# Normalize outcomes (exhaustive — consumed from verified extractions only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizationCompleted:
    """Verified extraction → ruleset → normalized fields, durably committed (one txn)."""
    record: NormalizationRecord
    fields: tuple


@dataclass(frozen=True)
class NormalizationAlreadyExists:
    """INV-N-1:1 replay: the same (extraction_id, ruleset_id, ruleset_version) was already
    normalized. Explicit, never a silent no-op; no second record is created."""
    normalization_id: str
    extraction_id: str
    ruleset_id: str
    ruleset_version: str


@dataclass(frozen=True)
class NormalizationSourceIntegrityFailure:
    """The source extraction failed its verified read (VOR FAILED) — nothing normalized."""
    extraction_id: str
    reason: str


@dataclass(frozen=True)
class NormalizationSourceRefused:
    """Source extraction is unknown (VOR ReadRefused) — nothing normalized."""
    extraction_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class NormalizationSourceUnavailable:
    """Source verification could not execute (no verdict computable) — nothing normalized,
    Issue-Report surfaced."""
    extraction_id: str
    issue_report: str


@dataclass(frozen=True)
class NormalizationRulesetNotRegistered:
    """The requested ruleset_id is not in the service's ruleset registry — explicit."""
    extraction_id: str
    ruleset_id: str


@dataclass(frozen=True)
class NormalizationStorageUnavailable:
    """D-2 analog: nothing recordable — nothing persisted, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Read outcomes (VOR pattern — exhaustive; no silent broken read exists)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizationReadSuccess:
    """Stored record + fields delivered ONLY together with the same-read VALID verdict."""
    record: NormalizationRecord
    fields: tuple
    verified_at: str


@dataclass(frozen=True)
class NormalizationReadIntegrityFailure:
    """Definitive FAILED verdict (stored bytes no longer match the committed fingerprint)
    + coarse reason; the stored (broken) content is NEVER delivered."""
    normalization_id: str
    reason: str
    verified_at: str


@dataclass(frozen=True)
class NormalizationReadRefused:
    """Unknown normalization_id — nothing delivered, no verdict, no state change."""
    normalization_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class NormalizationReadVerificationUnavailable:
    """No verdict computable (e.g. unknown fingerprint algorithm id) — no content,
    Issue-Report surfacing."""
    normalization_id: str
    issue_report: str
