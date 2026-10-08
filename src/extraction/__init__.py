"""Kandoo Extraction Layer — WP-3.1 MVP implementation.

Normative basis (the ONLY authorities for this code):
  SPEC-WP31-EXT   Extraction Contract v1.0-MVP (inline per TM dispatch 2026-10-01)
  D-01 provenance vocabulary | D-02/D-03 untouched | D-09 governance freeze
  AS-01 flow position: Capture → Reconstruction → **Extraction** → (P4+ untouched)
  WP-1.1 / WP-2.1 frozen components — the only upstream dependencies (S1 + verified
  document read); the reconstruction store is NEVER accessed directly and capture
  artifacts are NEVER re-read in parallel.

Implemented MVP flow (per the implementation dispatch):
  verified DocumentReadSuccess → ExtractionInput (extraction-ready projection) →
  registered engine (replaceable abstraction; reference engine included for MVP
  executability) → engine-contract validation (verbatim spans, EXTRACTED provenance) →
  atomic durable ExtractionRecord + positioned fields → verified extraction read,
  plus the mandated explicit-outcome behavior on every failure path.

Boundary: NO OCR/VLM selection (D-09 — engine seam only), NO normalization, NO
canonicalization, NO validation policy, NO S2/identity resolution, NO document-level
dedup (field sequences are never deduplicated). Values are verbatim; every field is
bound to page_index + byte span + page_fingerprint; capture/reconstruction are untouched.

WP-3.2 — Extraction Evidence Binding (additive; zero change to WP-3.1 behavior):
  verified extraction record → durable, tamper-evident Extraction Evidence Binding →
  per-field provable traceability to Document/Page + source span + Capture + the WP-2.2
  reconstruction evidence (consumed strictly read-only). See SPEC-WP32-EVB.
"""
from .model import (
    NOTE_VERIFY_FAILED,
    NOTE_VERIFICATION_UNAVAILABLE,
    Provenance,
    SourceSpan,
    ExtractedField,
    ExtractionRecord,
    ExtractionInput,
    ExtractionLayerError,
    ExtractionNotFound,
    ExtractionDuplicate,
    ExtractionPersistenceUnavailable,
    ExtractionCompleted,
    ExtractionAlreadyExists,
    ExtractionSourceIntegrityFailure,
    ExtractionSourceRefused,
    ExtractionSourceUnavailable,
    ExtractionEngineNotRegistered,
    ExtractionEngineFailed,
    ExtractionEngineContractViolation,
    ExtractionStorageUnavailable,
    ExtractionReadSuccess,
    ExtractionReadIntegrityFailure,
    ExtractionReadRefused,
    ExtractionReadVerificationUnavailable,
    utc_now_iso,
)
from .engine import ExtractionEngine, ExtractionEngineError, ReferenceDelimitedEngine
from .store import ExtractionStore, canonical_extraction_bytes
from .service import ExtractionService
from .binding_model import (
    BindingLink,
    BindingFieldEntry,
    ExtractionBindingRecord,
    BindingRef,
    BindingLayerError,
    BindingNotFound,
    BindingDuplicate,
    BindingPersistenceUnavailable,
    BindingCompleted,
    BindingAlreadyExists,
    BindingSourceIntegrityFailure,
    BindingSourceRefused,
    BindingSourceUnavailable,
    BindingStorageUnavailable,
    BindingReadSuccess,
    BindingReadIntegrityFailure,
    BindingReadRefused,
    BindingReadVerificationUnavailable,
    BindingChainReport,
)
from .binding import ExtractionBindingStore, ExtractionEvidenceBinder, canonical_binding_bytes

__all__ = [
    # model
    "Provenance", "SourceSpan", "ExtractedField", "ExtractionRecord", "ExtractionInput",
    "utc_now_iso", "NOTE_VERIFY_FAILED", "NOTE_VERIFICATION_UNAVAILABLE",
    "ExtractionLayerError", "ExtractionNotFound", "ExtractionDuplicate",
    "ExtractionPersistenceUnavailable",
    "ExtractionCompleted", "ExtractionAlreadyExists",
    "ExtractionSourceIntegrityFailure", "ExtractionSourceRefused",
    "ExtractionSourceUnavailable", "ExtractionEngineNotRegistered",
    "ExtractionEngineFailed", "ExtractionEngineContractViolation",
    "ExtractionStorageUnavailable",
    "ExtractionReadSuccess", "ExtractionReadIntegrityFailure",
    "ExtractionReadRefused", "ExtractionReadVerificationUnavailable",
    # engine abstraction + reference engine
    "ExtractionEngine", "ExtractionEngineError", "ReferenceDelimitedEngine",
    # store / service
    "ExtractionStore", "canonical_extraction_bytes", "ExtractionService",
    # evidence binding (WP-3.2)
    "BindingLink", "BindingFieldEntry", "ExtractionBindingRecord", "BindingRef",
    "BindingLayerError", "BindingNotFound", "BindingDuplicate",
    "BindingPersistenceUnavailable",
    "BindingCompleted", "BindingAlreadyExists",
    "BindingSourceIntegrityFailure", "BindingSourceRefused", "BindingSourceUnavailable",
    "BindingStorageUnavailable",
    "BindingReadSuccess", "BindingReadIntegrityFailure", "BindingReadRefused",
    "BindingReadVerificationUnavailable", "BindingChainReport",
    "ExtractionBindingStore", "ExtractionEvidenceBinder", "canonical_binding_bytes",
]
