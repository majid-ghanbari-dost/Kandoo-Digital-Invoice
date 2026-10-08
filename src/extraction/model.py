"""Extraction-layer domain model — WP-3.1 MVP implementation.

Binding basis:
  SPEC-WP31-EXT   Extraction Contract v1.0-MVP (produced inline per TM dispatch 2026-10-01)
  D-01 (provenance vocabulary EXTRACTED | DERIVED | UNRESOLVED) | D-02/D-03 untouched |
  D-09 (no OCR/VLM/engine selection — replaceable abstraction) | AS-01 flow position
  WP-2.1 §7 boundary: Extraction receives `DocumentReadSuccess` — ordered raw page bytes +
  indices + fingerprints + capture linkage — NOTHING else. This layer never re-reads raw
  capture artifacts and never re-derives pages in parallel (the verified read is the only
  sanctioned input path).

Boundary (normative): Extraction turns a VERIFIED Document/Page into extracted structured
data. The model below performs NO normalization, NO canonicalization, NO validation-policy,
NO S2/identity resolution, NO document-level dedup (D-03): values are stored VERBATIM as the
engine found them, each bound to the exact source position (page_index + byte span +
page_fingerprint) it came from. Normalization (P4) owns every value transformation; until
then nothing here may transform a value.

Every outcome type is explicit; a silent result does not exist in this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple

from reconstruction import PageView   # frozen WP-2.1 projection — the sanctioned input shape


# ---------------------------------------------------------------------------
# Provenance — D-01 §2.A vocabulary verbatim: EXTRACTED → DERIVED → UNRESOLVED.
# This layer produces EXTRACTED only; DERIVED is WP-4.2 territory; UNRESOLVED is owned
# by the P4/P5 resolution order. The enum is declared here so the provenance MODEL
# exists from P3 onward (D-01: provenance must distinguish at least EXTRACTED | DERIVED).
# ---------------------------------------------------------------------------

class Provenance(str, Enum):
    EXTRACTED = "EXTRACTED"
    DERIVED = "DERIVED"
    UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# Single layer clock (one clock per layer — WP-1.1 OD-8 pattern)
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with explicit timezone — extraction-layer clock."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Read-path reason codes (coarse, no content interpretation)
# ---------------------------------------------------------------------------

NOTE_VERIFY_FAILED = "verify FAILED"
NOTE_VERIFICATION_UNAVAILABLE = "verification unavailable (no verdict computable)"


# ---------------------------------------------------------------------------
# Records — exact field sets (structurally enforced by the boundary test)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceSpan:
    """Exact source position of one extracted value inside ONE durable page.

    (page_index, byte_start, byte_end) index the page's verbatim bytes; page_fingerprint
    anchors the page content the span refers to (copied verbatim from the PageView the
    engine consumed). byte_start/byte_end are byte offsets, end-exclusive.
    """
    page_index: int
    byte_start: int
    byte_end: int
    page_fingerprint: str


@dataclass(frozen=True)
class ExtractedField:
    """One extracted value — verbatim, positioned, provenance-labeled.

    value_verbatim is the value EXACTLY as found in the source bytes (no trimming, no
    case-folding, no numeric parsing, no encoding translation beyond the engine-declared
    value_encoding). The pipeline enforces: strict-decoding the span bytes with
    value_encoding reproduces value_verbatim byte-for-byte.
    """
    field_seq: int                       # pipeline-assigned position (deterministic order)
    field_name: str                      # engine-declared field key (engine's vocabulary)
    value_verbatim: str
    value_encoding: str
    provenance: Provenance
    span: SourceSpan


@dataclass(frozen=True)
class ExtractionRecord:
    """Durable extraction record — full traceability to Document AND Capture (AC-3.1.1).

    capture_id / capture_s1 are copied verbatim from the DocumentReadSuccess that fed the
    run; page_count mirrors the document's page count at extraction time.
    """
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    engine_id: str
    engine_schema_version: str
    page_count: int
    field_count: int
    created_at: str
    record_fingerprint: str              # sha256-v1 over the canonical record+fields bytes
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class ExtractionInput:
    """Extraction-ready input — the explicit intermediate projection (AS-01 middle step).

    Built ONLY from a same-read-VALID DocumentReadSuccess; carries the document/capture
    traceability plus the ordered PageViews. Engines receive the pages (content +
    structure) — never the linkage (they have no use for it and must stay content-scoped).
    """
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    page_count: int
    pages: Tuple[PageView, ...]          # ordered by page_index (verified read guarantee)


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class ExtractionLayerError(Exception):
    """Base class for all explicit extraction-layer failures."""


class ExtractionNotFound(ExtractionLayerError):
    """The referenced extraction_id does not exist in the store."""


class ExtractionDuplicate(ExtractionLayerError):
    """INV-X-1:1 — a record for (document_id, engine_id, engine_schema_version) already
    exists. Raised inside the atomic commit; the service surfaces it as an explicit
    AlreadyExists outcome carrying the existing extraction_id."""

    def __init__(self, extraction_id: str) -> None:
        super().__init__(f"extraction already exists: {extraction_id}")
        self.extraction_id = extraction_id


class ExtractionPersistenceUnavailable(ExtractionLayerError):
    """D-2 analog: no record durably committed (atomic txn rolled back — zero residue,
    by construction; no recovery sweep needed). Never a silent partial write."""


# ---------------------------------------------------------------------------
# Extract outcomes (exhaustive — consumed from verified documents only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractionCompleted:
    """Verified document → engine → validated fields, durably committed (one atomic txn)."""
    extraction: ExtractionRecord
    fields: Tuple[ExtractedField, ...]


@dataclass(frozen=True)
class ExtractionAlreadyExists:
    """INV-X-1:1 replay: the same (document_id, engine_id, engine_schema_version) was
    already extracted. Explicit, never a silent no-op; no second record is created."""
    extraction_id: str
    document_id: str
    engine_id: str
    engine_schema_version: str


@dataclass(frozen=True)
class ExtractionSourceIntegrityFailure:
    """The source document failed its verified read (VOR FAILED) — nothing extracted."""
    document_id: str
    reason: str


@dataclass(frozen=True)
class ExtractionSourceRefused:
    """Source is non-COMPLETED or unknown (VOR ReadRefused) — nothing extracted."""
    document_id: Optional[str]
    document_state: Optional[str]
    detail: str


@dataclass(frozen=True)
class ExtractionSourceUnavailable:
    """Source verification could not execute (O-4) — nothing extracted, issue surfaced."""
    document_id: str
    issue_report: str


@dataclass(frozen=True)
class ExtractionEngineNotRegistered:
    """The requested engine_id is not in the pipeline's engine registry — explicit."""
    document_id: str
    engine_id: str


@dataclass(frozen=True)
class ExtractionEngineFailed:
    """The engine reported its own explicit failure (e.g. undecodable content) or raised
    unexpectedly — surfaced, never swallowed; nothing persisted."""
    document_id: str
    engine_id: str
    detail: str


@dataclass(frozen=True)
class ExtractionEngineContractViolation:
    """Engine output violated the engine contract: field not EXTRACTED-labeled, span out
    of bounds, span not matching the claimed page's fingerprint, value not verbatim-equal
    to its span, or malformed field shape. Fail-closed BEFORE persistence."""
    document_id: str
    engine_id: str
    detail: str


@dataclass(frozen=True)
class ExtractionStorageUnavailable:
    """D-2 analog: no record durably recordable — nothing persisted, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Read outcomes (VOR pattern — exhaustive; no silent broken read exists)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractionReadSuccess:
    """Stored record + fields delivered ONLY together with the same-read VALID verdict."""
    extraction: ExtractionRecord
    fields: Tuple[ExtractedField, ...]
    verified_at: str


@dataclass(frozen=True)
class ExtractionReadIntegrityFailure:
    """Definitive FAILED verdict (stored bytes no longer match the committed fingerprint)
    + coarse reason; the stored (broken) content is NEVER delivered."""
    extraction_id: str
    reason: str
    verified_at: str


@dataclass(frozen=True)
class ExtractionReadRefused:
    """Unknown extraction_id — nothing delivered, no verdict, no state change."""
    extraction_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class ExtractionReadVerificationUnavailable:
    """No verdict computable (e.g. unknown fingerprint algorithm id) — no content,
    Issue-Report surfacing."""
    extraction_id: str
    issue_report: str
