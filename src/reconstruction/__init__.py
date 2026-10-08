"""Kandoo Reconstruction Layer — WP-2.1 MVP implementation + WP-2.2 evidence.

Normative basis (the ONLY authorities for this code):
  SPEC-WP21-RC   Reconstruction Contract v1.0-MVP (inline per TM dispatch 2026-10-01)
  SPEC-WP22-REC  Reconstruction Evidence Contract v1.0-MVP (WP-2.2 — inline per TM
                 dispatch 2026-10-01: direct real build, no separate design phase)
  D-02 / D-03 / D-09  frozen decisions; AS-01 external-flow sequence
  WP-1.1 frozen capture components — the only upstream dependency (verified read + S1)

Implemented MVP flow (per the implementation dispatches):
  COMPLETED Capture → verified read → mechanical page derivation → durable Document
  with ordered Pages → INV-R-1:1 completion → verified document read, plus the mandated
  failure/recovery behavior — and (WP-2.2) a durable, tamper-evident, structural
  evidence log binding every document/page to its capture source.

Boundary: NO OCR/VLM, NO extraction, NO normalization, NO S2/document-level dedup,
NO canonical datum. Pages carry verbatim byte slices + fingerprints only; evidence
carries structural facts only (ids/fingerprints/offsets/reason codes/timestamps).
"""
from .model import (
    NOTE_PAGE_PERSIST_FAILED,
    NOTE_PAGES_INCOMPLETE,
    NOTE_PAGE_CONTENT_MISSING,
    NOTE_PERSISTENCE_INCOMPLETE,
    NOTE_UNIQUENESS_CONFLICT,
    NOTE_VERIFICATION_UNAVAILABLE,
    NOTE_VERIFY_FAILED,
    READ_REASON_DOC_MISMATCH,
    READ_REASON_PAGE_MISMATCH,
    READ_REASON_PAGE_UNREADABLE,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
    ReconstructionLayerError,
    DocumentRecord,
    DocumentState,
    DocumentIntegrity,
    PageRecord,
    PageView,
    DocumentCreationFailed,
    DocumentNotFound,
    IllegalTransition,
    IllegalFieldWrite,
    CompletionGateUnmet,
    PageContentMissing,
    StorageUnavailable,
    ExplicitPersistenceFailure,
    ReconstructCompleted,
    ReconstructAlreadyExists,
    ReconstructSourceIntegrityFailure,
    ReconstructSourceRefused,
    ReconstructSourceUnavailable,
    ReconstructSettledFailure,
    ReconstructUniquenessConflict,
    ReconstructStorageUnavailable,
    DocumentReadSuccess,
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadVerificationUnavailable,
    utc_now_iso,
)
from .evidence import (
    DERIVATION_ID,
    EV_DOCUMENT_COMPLETED,
    EV_DOCUMENT_SETTLED_FAILED,
    EV_RECOVERY_SETTLED,
    EV_VERIFIED_READ,
    GENESIS_HASH,
    EvidenceEvent,
    EvidenceAppended,
    EvidenceUnavailable,
    EvidenceReadSuccess,
    EvidenceReadIntegrityFailure,
    EvidenceReadRefused,
    EvidenceReadVerificationUnavailable,
    ChainVerificationReport,
    EvidenceLayerError,
    EvidenceStorageUnavailable,
    EvidenceIllegalEvent,
    EvidenceStore,
    spans_from_durable,
)
from .pages import derive_pages, reassemble
from .store import ReconstructionStore
from .service import ReconstructionService
from .recovery import ReconstructionRecoveryReport, run_reconstruction_recovery

__all__ = [
    # model
    "DocumentState", "DocumentIntegrity", "DocumentRecord", "PageRecord", "PageView",
    "utc_now_iso",
    "NOTE_PAGE_PERSIST_FAILED", "NOTE_PAGES_INCOMPLETE", "NOTE_PAGE_CONTENT_MISSING",
    "NOTE_PERSISTENCE_INCOMPLETE", "NOTE_UNIQUENESS_CONFLICT",
    "NOTE_VERIFICATION_UNAVAILABLE", "NOTE_VERIFY_FAILED",
    "READ_REASON_PAGE_MISMATCH", "READ_REASON_DOC_MISMATCH", "READ_REASON_PAGE_UNREADABLE",
    "ReconstructionLayerError", "DocumentCreationFailed", "DocumentNotFound",
    "IllegalTransition", "IllegalFieldWrite", "CompletionGateUnmet", "PageContentMissing",
    "StorageUnavailable", "ExplicitPersistenceFailure",
    "UAC_GRANTED", "UAC_UNIQUENESS_CONFLICT",
    "ReconstructCompleted", "ReconstructAlreadyExists", "ReconstructSourceIntegrityFailure",
    "ReconstructSourceRefused", "ReconstructSourceUnavailable", "ReconstructSettledFailure",
    "ReconstructUniquenessConflict", "ReconstructStorageUnavailable",
    "DocumentReadSuccess", "DocumentReadIntegrityFailure", "DocumentReadRefused",
    "DocumentReadVerificationUnavailable",
    # evidence (WP-2.2)
    "EV_DOCUMENT_COMPLETED", "EV_DOCUMENT_SETTLED_FAILED", "EV_VERIFIED_READ",
    "EV_RECOVERY_SETTLED", "DERIVATION_ID", "GENESIS_HASH",
    "EvidenceEvent", "EvidenceAppended", "EvidenceUnavailable",
    "EvidenceReadSuccess", "EvidenceReadIntegrityFailure", "EvidenceReadRefused",
    "EvidenceReadVerificationUnavailable", "ChainVerificationReport",
    "EvidenceLayerError", "EvidenceStorageUnavailable", "EvidenceIllegalEvent",
    "EvidenceStore", "spans_from_durable",
    # pages / store / service / recovery
    "derive_pages", "reassemble", "ReconstructionStore", "ReconstructionService",
    "ReconstructionRecoveryReport", "run_reconstruction_recovery",
]
