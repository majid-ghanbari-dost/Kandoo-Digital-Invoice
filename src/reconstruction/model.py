"""Reconstruction-layer domain model — WP-2.1 MVP implementation.

Binding basis:
  SPEC-WP21-RC   Reconstruction Contract v1.0-MVP (produced inline per TM dispatch 2026-10-01)
  D-02/D-03/D-09 frozen decisions; AS-01 external-flow sequence
  WP-1.1 frozen components (capture) — the ONLY upstream dependency

Boundary (normative): Reconstruction turns a verified Capture Artifact into a durable,
ordered Document/Page structure consumable by Extraction. The model below contains NO
field capable of holding an extracted or interpreted value — pages carry verbatim byte
slices plus fingerprints only (AC-2.1.3, structural no-extraction boundary).

Every outcome type is explicit; a silent result does not exist in this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Enumerations — the WP-1.1 lifecycle pattern, bound to documents
# ---------------------------------------------------------------------------

class DocumentState(str, Enum):
    """SPEC-WP21-RC §4: ACTIVE | COMPLETED | FAILED_INCOMPLETE (both terminals)."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED_INCOMPLETE = "FAILED_INCOMPLETE"


class DocumentIntegrity(str, Enum):
    """UNVERIFIED is transient-only (pre-first-verification) — VOR analog."""
    UNVERIFIED = "UNVERIFIED"
    VALID = "VALID"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Settlement-note vocabulary (D-1/D-2 analogs; recovery causes) — explicit, no guessing
# ---------------------------------------------------------------------------

NOTE_PAGE_PERSIST_FAILED = "page persist failed"
NOTE_PAGES_INCOMPLETE = "pages missing/incomplete"
NOTE_PAGE_CONTENT_MISSING = "page content missing/unreadable"
NOTE_VERIFY_FAILED = "verify FAILED"
NOTE_VERIFICATION_UNAVAILABLE = "verification unavailable (no verdict computable)"
NOTE_UNIQUENESS_CONFLICT = (
    "uniqueness conflict: a COMPLETED document for the same capture_id exists"
)
NOTE_PERSISTENCE_INCOMPLETE = "persistence incomplete"

# Read-outcome reason codes (coarse, no content interpretation)
READ_REASON_PAGE_MISMATCH = "page content mismatch"
READ_REASON_DOC_MISMATCH = "document fingerprint mismatch"
READ_REASON_PAGE_UNREADABLE = "page content unreadable/missing"

# UAC-analog outcomes (INV-R-1:1 completion primitive)
UAC_GRANTED = "UAC_GRANTED"
UAC_UNIQUENESS_CONFLICT = "UAC_UNIQUENESS_CONFLICT"


# ---------------------------------------------------------------------------
# Single layer clock (one clock per layer — WP-1.1 OD-8 pattern)
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with explicit timezone — reconstruction-layer clock."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Records — exact field sets (structurally enforced by the no-extraction test)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    capture_id: str                      # traceability link (Contract v1.1 §5 reservation)
    capture_s1: str                      # capture identity value, verbatim (D-02)
    capture_s1_algorithm_id: str
    created_at: str
    document_state: DocumentState
    integrity_status: DocumentIntegrity
    integrity_verified_at: Optional[str]
    page_count: Optional[int]            # finalized at page persist
    document_fingerprint: Optional[str]  # sha256 over canonical reassembly of ordered pages
    fingerprint_algorithm_id: Optional[str]
    settlement_note: Optional[str]       # mandatory on FAILED_INCOMPLETE; empty on COMPLETED


@dataclass(frozen=True)
class PageRecord:
    """Full page row (store-internal; content included)."""
    document_id: str
    page_index: int                      # 0-based, contiguous — THE deterministic order
    page_ref: str                        # opaque "recon-page:v1:<uuid>"
    content: bytes
    byte_len: int
    page_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class PageView:
    """Extraction-facing page projection — raw bytes + structure, nothing else."""
    page_index: int
    content: bytes
    byte_len: int
    page_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class ReconstructionLayerError(Exception):
    """Base class for all explicit reconstruction-layer failures."""


class DocumentCreationFailed(ReconstructionLayerError):
    """Record-creation persist failure — nothing persisted, no residue."""


class DocumentNotFound(ReconstructionLayerError):
    """The referenced document_id does not exist in the store."""


class IllegalTransition(ReconstructionLayerError):
    """A lifecycle-illegal operation was demanded (store-enforced)."""


class IllegalFieldWrite(ReconstructionLayerError):
    """A write outside the mutability rules was demanded (store-enforced)."""


class CompletionGateUnmet(ReconstructionLayerError):
    """Completion preconditions not satisfied (fail-closed)."""


class PageContentMissing(ReconstructionLayerError):
    """Durable page content is missing / not readable."""


class StorageUnavailable(ReconstructionLayerError):
    """D-2 class: no verdict durably recordable (residue settles at recovery)."""


class ExplicitPersistenceFailure(ReconstructionLayerError):
    """D-1 class: definitive persist error, already settled synchronously."""

    def __init__(self, document_id: Optional[str], settlement_note: str, detail: str = "") -> None:
        super().__init__(detail or f"definitive persistence failure; settled synchronously: {settlement_note}")
        self.document_id = document_id
        self.settlement_note = settlement_note


# ---------------------------------------------------------------------------
# Reconstruct outcomes (exhaustive — consumed from verified captures only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReconstructCompleted:
    """Document built from a verified capture and completed through the UAC primitive."""
    document: DocumentRecord


@dataclass(frozen=True)
class ReconstructAlreadyExists:
    """A COMPLETED document for this capture already exists (INV-R-1:1) — explicit,
    never a silent no-op; no second document."""
    document_id: str
    capture_id: str


@dataclass(frozen=True)
class ReconstructSourceIntegrityFailure:
    """The source capture failed its verified read (VOR FAILED) — nothing created."""
    capture_id: str
    reason: str


@dataclass(frozen=True)
class ReconstructSourceRefused:
    """Source is non-COMPLETED or unknown (VOR ReadRefused) — nothing created."""
    capture_id: Optional[str]
    capture_state: Optional[str]         # capture-layer process state — Provable-Data-legal
    detail: str


@dataclass(frozen=True)
class ReconstructSourceUnavailable:
    """Source verification could not execute (O-4) — nothing created, issue surfaced."""
    capture_id: str
    issue_report: str


@dataclass(frozen=True)
class ReconstructSettledFailure:
    """D-1 synchronous settlement to FAILED_INCOMPLETE (+ note); evidence retained."""
    document_id: Optional[str]
    settlement_note: str
    detail: str


@dataclass(frozen=True)
class ReconstructUniquenessConflict:
    """This construction lost the atomic INV-R-1:1 decision; settled FAILED_INCOMPLETE
    with the uniqueness-conflict note (explicit loser — P3 pattern)."""
    document_id: str
    settlement_note: str


@dataclass(frozen=True)
class ReconstructStorageUnavailable:
    """D-2: no verdict durably recordable — ACTIVE residue; startup recovery settles."""
    detail: str


# ---------------------------------------------------------------------------
# Read outcomes (VOR pattern — exhaustive; no silent broken read exists)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentReadSuccess:
    """Ordered pages delivered ONLY together with the same-read VALID verdict."""
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    page_count: int
    pages: Tuple[PageView, ...]          # ordered by page_index
    verified_at: str                     # the F-08-analog value written in this read


@dataclass(frozen=True)
class DocumentReadIntegrityFailure:
    """Definitive FAILED verdict + coarse reason; content is NEVER carried."""
    document_id: str
    reason: str
    verified_at: str


@dataclass(frozen=True)
class DocumentReadRefused:
    """Non-COMPLETED target / unknown id — no content, no verdict, no state change."""
    document_id: Optional[str]
    document_state: Optional[str]
    detail: str


@dataclass(frozen=True)
class DocumentReadVerificationUnavailable:
    """No verdict computable — no integrity write, no content, Issue-Report surfacing."""
    document_id: str
    issue_report: str
