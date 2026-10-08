"""Startup recovery — Contract §11 over Store §5 (minimal initial recovery behavior).

This module realizes the recovery role the frozen documents mandate (Task T-1.1.5's
"Initial Recovery Behavior"): on startup, enumerate every ACTIVE leftover and settle it
to exactly one terminal state — idempotently, without any external re-fetch (§11 r5),
with every settlement explicit and retained (INV-C9).

Store §5 algorithm (restated as implemented):
  scan:        R ← all records with capture_state = ACTIVE
  for each R (order-independent; results are per-record):
    a. content ← read(artifact_ref) if present
    b. if content readable ∧ s1 attached ∧ verify(content, s1, s1_algorithm_id) = VALID
          ∧ uniqueness precondition holds (checked atomically inside the UAC primitive)
          → record the VALID verdict, then transition R to COMPLETED through the SAME
            UAC primitive used by ingest (P5 — no side path)
    c. else → transition R to FAILED_INCOMPLETE + settlement_note (cause-specific) +
              integrity_status = FAILED pinned at settlement (v1.1-C2)
  post:        recovery is complete iff ZERO records remain ACTIVE (INV-C6 / INV-S6);
               if storage unavailability prevents settlement writes, recovery is NOT
               reported complete (Store §6.1 point 4) — the error is surfaced instead.

No verdict is recorded without an executed verification; when verification cannot yield
a verdict (unknown id / capability failure), the only contract-legal ending is the
conservative FAILED_INCOMPLETE — never COMPLETED (Store §5 note; S1 §8 F2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .model import (
    NOTE_CONTENT_MISSING,
    NOTE_S1_MISSING,
    NOTE_UNIQUENESS_CONFLICT,
    NOTE_VERIFICATION_UNAVAILABLE,
    NOTE_VERIFY_FAILED,
    ContentMissing,
    RecordNotFound,
    StorageUnavailable,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
    utc_now_iso,
)
from .s1 import S1Service
from .store import CaptureStore


@dataclass
class RecoveryReport:
    """Explicit recovery outcome — INV-C6 is evaluated, never assumed."""
    settled_completed: List[str] = field(default_factory=list)
    settled_failed: List[Tuple[str, str]] = field(default_factory=list)   # (capture_id, note)
    remaining_active: int = 0
    complete: bool = False
    error: Optional[str] = None
    issues: List[str] = field(default_factory=list)                       # Issue-Report surfacing


def run_startup_recovery(store: CaptureStore, s1: S1Service) -> RecoveryReport:
    """Scan + settle all ACTIVE leftovers (idempotent: re-running changes nothing,
    §11 r4). No retry/re-fetch toward external sources, ever."""
    report = RecoveryReport()
    try:
        leftovers = store.enumerate_active()
    except StorageUnavailable as exc:
        report.error = f"startup scan failed (storage unavailable): {exc}"
        report.complete = False
        return report

    for record in leftovers:
        try:
            _settle_leftover(store, s1, record, report)
        except StorageUnavailable as exc:
            # §6.1 point 4: settlement writes are not durably recordable → recovery is
            # NOT complete; the unresolved record is never presented as valid (INV-C9).
            report.error = f"recovery interrupted by storage unavailability: {exc}"
            break
        except (RecordNotFound, ValueError) as exc:   # defensive: concurrent anomaly
            report.issues.append(f"capture {record.capture_id}: settlement anomaly: {exc}")

    try:
        report.remaining_active = len(store.enumerate_active())
    except StorageUnavailable as exc:
        report.error = report.error or f"post-scan enumeration failed: {exc}"
        report.remaining_active = -1

    # INV-C6: recovery processing is complete if and only if zero ACTIVE records remain.
    report.complete = report.error is None and report.remaining_active == 0
    return report


def _settle_leftover(store: CaptureStore, s1: S1Service, record, report: RecoveryReport) -> None:
    """Settle one ACTIVE leftover to exactly one terminal state (Store §5 a/b/c)."""

    # (a) content presence / readability
    if record.artifact_ref is None:
        # W2 residue: record-first created, content never durably persisted.
        _settle(store, record.capture_id, NOTE_CONTENT_MISSING, report)
        return

    # Identity precondition: without the attached S1 pair nothing can be proven (W3).
    if not record.s1 or not record.s1_algorithm_id:
        _settle(store, record.capture_id, NOTE_S1_MISSING, report)
        return

    try:
        content = store.get_content(record.artifact_ref)
    except ContentMissing:
        _settle(store, record.capture_id, NOTE_CONTENT_MISSING, report)
        return

    # (b) verification with the record's OWN s1_algorithm_id (INV-V4 analog at V-2)
    verdict = s1.verify(content, record.s1, record.s1_algorithm_id)

    if verdict.outcome == "NO_VERDICT":
        # S1 §8 F2: no verdict computable (version skew / capability failure) →
        # conservative settlement + Issue-Report surfacing; no integrity write (INV-V8).
        report.issues.append(
            f"capture {record.capture_id}: verification unavailable at recovery "
            f"({verdict.reason or 'capability failure'})")
        _settle(store, record.capture_id, NOTE_VERIFICATION_UNAVAILABLE, report)
        return

    if verdict.outcome == "FAILED":
        # A verification WAS executed and computed FAILED → record the truthful verdict
        # (restricted writer), then settle with the pinned FAILED + cause note.
        store.record_verification(record.capture_id, "FAILED", utc_now_iso())
        _settle(store, record.capture_id, NOTE_VERIFY_FAILED, report)
        return

    # VALID → completion through the store's UAC primitive (uniqueness precondition is
    # checked atomically inside it — P1/P2/P5; uniqueness-conflict losers settle per P3).
    store.record_verification(record.capture_id, "VALID", utc_now_iso())
    outcome = store.complete_record(record.capture_id)
    if outcome == UAC_GRANTED:
        report.settled_completed.append(record.capture_id)
    elif outcome == UAC_UNIQUENESS_CONFLICT:
        _settle(store, record.capture_id, NOTE_UNIQUENESS_CONFLICT, report)
    else:  # pragma: no cover - exhaustive by construction
        report.issues.append(f"capture {record.capture_id}: unknown UAC outcome {outcome!r}")
        _settle(store, record.capture_id, NOTE_VERIFY_FAILED, report)


def _settle(store: CaptureStore, capture_id: str, note: str, report: RecoveryReport) -> None:
    store.settle_failed(capture_id, note)
    report.settled_failed.append((capture_id, note))
