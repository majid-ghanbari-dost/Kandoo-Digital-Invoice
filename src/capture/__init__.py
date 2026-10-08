"""Kandoo Capture Layer — WP-1.1 MVP implementation.

Frozen normative basis (the ONLY authorities for this code):
  SPEC-WP11-CRC       Capture Record Contract v1.1 (FINAL FREEZE APPROVED)
  DES-WP11-T112-STORE Durable Local Capture Store Design v0.2 (FINAL APPROVED)
  DES-WP11-T113-S1    S1 Fingerprint & Capture-Level Idempotency Design v1.0 (FINAL APPROVED)
  DES-WP11-T114-VOR   Verify-on-Read / Integrity Verification Design v1.0 (FINAL APPROVED / FROZEN)

Implemented MVP flow (per the implementation dispatch):
  Artifact → Durable Local Store → S1 → Capture-level Idempotency → Verification
  → COMPLETED → Verified Read, plus the mandated failure/recovery behavior.

No downstream / canonical / external-document datum exists in any output (D-02, INV-C7).
"""
from .model import (
    FORMAT_HINT_UNKNOWN,
    NOTE_CONTENT_MISSING,
    NOTE_CONTENT_PERSIST_FAILED,
    NOTE_PERSISTENCE_INCOMPLETE,
    NOTE_S1_COMPUTATION_FAILED,
    NOTE_S1_MISSING,
    NOTE_UNIQUENESS_CONFLICT,
    NOTE_VERIFICATION_UNAVAILABLE,
    NOTE_VERIFY_FAILED,
    READ_REASON_MISMATCH,
    READ_REASON_UNREADABLE,
    SOURCE_LABEL_UNDECLARED,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
    CaptureLayerError,
    CaptureRecord,
    CaptureState,
    CompletionGateUnmet,
    ContentMissing,
    ExplicitPersistenceFailure,
    IllegalFieldWrite,
    IllegalTransition,
    IngestCompleted,
    IngestDuplicateAtCapture,
    IngestIntegrityFailureHit,
    IngestSettledFailure,
    IngestStorageUnavailable,
    IngestUniquenessConflict,
    IntegrityStatus,
    ReadIntegrityFailure,
    ReadRefused,
    ReadSuccess,
    ReadVerificationUnavailable,
    RecordCreationFailed,
    RecordNotFound,
    S1ComputationFailure,
    StorageUnavailable,
    utc_now_iso,
)
from .s1 import S1_ALGORITHM_ID, S1Service, S1Value, Verdict
from .store import CaptureStore
from .service import CaptureService
from .recovery import RecoveryReport, run_startup_recovery

__all__ = [
    # model
    "CaptureState", "IntegrityStatus", "CaptureRecord", "utc_now_iso",
    "SOURCE_LABEL_UNDECLARED", "FORMAT_HINT_UNKNOWN",
    "NOTE_S1_COMPUTATION_FAILED", "NOTE_CONTENT_PERSIST_FAILED", "NOTE_S1_MISSING",
    "NOTE_CONTENT_MISSING", "NOTE_VERIFY_FAILED", "NOTE_PERSISTENCE_INCOMPLETE",
    "NOTE_UNIQUENESS_CONFLICT", "NOTE_VERIFICATION_UNAVAILABLE",
    "READ_REASON_MISMATCH", "READ_REASON_UNREADABLE",
    "CaptureLayerError", "RecordCreationFailed", "RecordNotFound", "IllegalTransition",
    "IllegalFieldWrite", "CompletionGateUnmet", "ContentMissing", "StorageUnavailable",
    "S1ComputationFailure", "ExplicitPersistenceFailure",
    "UAC_GRANTED", "UAC_UNIQUENESS_CONFLICT",
    "IngestCompleted", "IngestDuplicateAtCapture", "IngestIntegrityFailureHit",
    "IngestSettledFailure", "IngestUniquenessConflict", "IngestStorageUnavailable",
    "ReadSuccess", "ReadIntegrityFailure", "ReadRefused", "ReadVerificationUnavailable",
    # s1
    "S1_ALGORITHM_ID", "S1Service", "S1Value", "Verdict",
    # store / service / recovery
    "CaptureStore", "CaptureService", "RecoveryReport", "run_startup_recovery",
]
