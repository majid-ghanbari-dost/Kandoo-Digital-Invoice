"""Startup recovery for Reconstruction — SPEC-WP21-RC §4/§8 (WP-1.1 §11 pattern)
+ evidence emission (WP-2.2 — non-intrusive, optional; SPEC-WP22-REC).

On startup, enumerate every ACTIVE document leftover and settle it to exactly one
terminal state — idempotently, with every settlement explicit and retained:

  scan:   D ← all documents with document_state = ACTIVE
  for each D (order-independent; results are per-document):
    a. durable page set present, page_count consistent, indices contiguous 0..n-1
       → else FAILED_INCOMPLETE + "pages missing/incomplete"
    b. per-page verification + canonical reassembly verification against the stored
       anchors (document-internal only — the capture layer owns its own recovery, §8)
       → any FAILED verdict: record FAILED + "verify FAILED"
       → any NO-VERDICT: conservative FAILED_INCOMPLETE + "verification unavailable"
         + Issue-Report (never COMPLETED without an executed valid verification)
    c. all VALID → record the VALID verdict, then transition D to COMPLETED through
       the SAME UAC primitive used by reconstruct (no side path); uniqueness-conflict
       losers settle FAILED_INCOMPLETE with the uniqueness note
  post:  recovery is complete iff ZERO documents remain ACTIVE; if storage
         unavailability prevents settlement writes, recovery is NOT complete.

No half-built document is ever presented as valid (AC-2.1.5).

Evidence (WP-2.2, OD-E5): when an EvidenceStore is wired in, every settlement emits a
RECOVERY_SETTLED event (final_state + settlement_note + framing-derived page spans when
determinable from durable state). Evidence failure NEVER affects recovery completeness
or any settlement; it surfaces in report.issues — never silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .evidence import EV_RECOVERY_SETTLED, EvidenceUnavailable, spans_from_durable
from .model import (
    NOTE_PAGES_INCOMPLETE,
    NOTE_UNIQUENESS_CONFLICT,
    NOTE_VERIFICATION_UNAVAILABLE,
    NOTE_VERIFY_FAILED,
    DocumentNotFound,
    StorageUnavailable,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
    utc_now_iso,
)
from .pages import reassemble
from .store import ReconstructionStore


@dataclass
class ReconstructionRecoveryReport:
    """Explicit recovery outcome — zero-ACTIVE is evaluated, never assumed."""
    settled_completed: List[str] = field(default_factory=list)
    settled_failed: List[Tuple[str, str]] = field(default_factory=list)   # (document_id, note)
    remaining_active: int = 0
    complete: bool = False
    error: Optional[str] = None
    issues: List[str] = field(default_factory=list)                       # Issue-Report surfacing


def run_reconstruction_recovery(store: ReconstructionStore, s1, evidence=None) -> ReconstructionRecoveryReport:
    """Scan + settle all ACTIVE document leftovers (idempotent: re-running changes nothing).
    `s1` = the reused capture S1Service compute capability. No retry/re-fetch, ever.
    `evidence` = optional EvidenceStore (WP-2.2); failures surface in report.issues only."""
    report = ReconstructionRecoveryReport()
    try:
        leftovers = store.enumerate_active()
    except StorageUnavailable as exc:
        report.error = f"startup scan failed (storage unavailable): {exc}"
        report.complete = False
        return report

    for record in leftovers:
        try:
            _settle_leftover(store, s1, record, report, evidence)
        except StorageUnavailable as exc:
            # Settlement writes are not durably recordable → recovery is NOT complete;
            # the unresolved document is never presented as valid.
            report.error = f"recovery interrupted by storage unavailability: {exc}"
            break
        except (DocumentNotFound, ValueError) as exc:   # defensive: concurrent anomaly
            report.issues.append(f"document {record.document_id}: settlement anomaly: {exc}")

    try:
        report.remaining_active = len(store.enumerate_active())
    except StorageUnavailable as exc:
        report.error = report.error or f"post-scan enumeration failed: {exc}"
        report.remaining_active = -1

    # Recovery is complete if and only if zero ACTIVE documents remain.
    report.complete = report.error is None and report.remaining_active == 0
    return report


def _settle_leftover(store: ReconstructionStore, s1, record, report: ReconstructionRecoveryReport,
                     evidence=None) -> None:
    """Settle one ACTIVE leftover to exactly one terminal state (steps a/b/c)."""
    document_id = record.document_id

    # (a) structural completeness of the durable page set
    if record.page_count is None or not record.document_fingerprint \
            or not record.fingerprint_algorithm_id:
        _settle(store, document_id, NOTE_PAGES_INCOMPLETE, report)
        _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                           NOTE_PAGES_INCOMPLETE, None, None, report)
        return
    try:
        pages = store.get_pages(document_id)
    except DocumentNotFound:                            # pragma: no cover - defensive
        _settle(store, document_id, NOTE_PAGES_INCOMPLETE, report)
        _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                           NOTE_PAGES_INCOMPLETE, None, None, report)
        return
    if len(pages) != record.page_count or [p.page_index for p in pages] != list(range(record.page_count)):
        _settle(store, document_id, NOTE_PAGES_INCOMPLETE, report)
        _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                           NOTE_PAGES_INCOMPLETE, None, None, report)
        return

    # (b) document-internal verification (per page, then canonical reassembly)
    for page in pages:
        verdict = s1.verify(page.content, page.page_fingerprint,
                            page.fingerprint_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            report.issues.append(
                f"document {document_id}: page {page.page_index} verification unavailable "
                f"at recovery ({verdict.reason or 'capability failure'})")
            _settle(store, document_id, NOTE_VERIFICATION_UNAVAILABLE, report)
            _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                               NOTE_VERIFICATION_UNAVAILABLE, None, None, report)
            return
        if verdict.outcome == "FAILED":
            store.record_verification(document_id, "FAILED", utc_now_iso())
            _settle(store, document_id, NOTE_VERIFY_FAILED, report)
            _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                               NOTE_VERIFY_FAILED, None, None, report)
            return

    canonical = reassemble(page.content for page in pages)
    doc_verdict = s1.verify(canonical, record.document_fingerprint,
                            record.fingerprint_algorithm_id)
    if doc_verdict.outcome == "NO_VERDICT":
        report.issues.append(
            f"document {document_id}: verification unavailable at recovery "
            f"({doc_verdict.reason or 'capability failure'})")
        _settle(store, document_id, NOTE_VERIFICATION_UNAVAILABLE, report)
        _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                           NOTE_VERIFICATION_UNAVAILABLE, None, None, report)
        return
    if doc_verdict.outcome == "FAILED":
        store.record_verification(document_id, "FAILED", utc_now_iso())
        _settle(store, document_id, NOTE_VERIFY_FAILED, report)
        _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                           NOTE_VERIFY_FAILED, None, None, report)
        return

    # (c) VALID → completion through the store's UAC primitive (INV-R-1:1 atomic check).
    store.record_verification(document_id, "VALID", utc_now_iso())
    result = store.complete_document(document_id)
    if result == UAC_GRANTED:
        report.settled_completed.append(document_id)
        # OD-E4: spans derive from durable state; the frozen tiling gate makes the
        # canonical reassembly byte-identical to the artifact iff aggregate-format.
        aggregate_format = record.document_fingerprint == record.capture_s1
        spans = spans_from_durable([p.byte_len for p in pages], aggregate_format)
        _record_settlement(evidence, store, document_id, "COMPLETED", None, pages, spans, report)
    elif result == UAC_UNIQUENESS_CONFLICT:
        _settle(store, document_id, NOTE_UNIQUENESS_CONFLICT, report)
        _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                           NOTE_UNIQUENESS_CONFLICT, None, None, report)
    else:  # pragma: no cover - exhaustive by construction
        report.issues.append(f"document {document_id}: unknown UAC outcome {result!r}")
        _settle(store, document_id, NOTE_VERIFY_FAILED, report)
        _record_settlement(evidence, store, document_id, "FAILED_INCOMPLETE",
                           NOTE_VERIFY_FAILED, None, None, report)


def _settle(store: ReconstructionStore, document_id: str, note: str,
            report: ReconstructionRecoveryReport) -> None:
    store.settle_failed(document_id, note)
    report.settled_failed.append((document_id, note))


def _record_settlement(evidence, store: ReconstructionStore, document_id: str,
                       final_state: str, note, pages, spans, report: ReconstructionRecoveryReport) -> None:
    """Emit one RECOVERY_SETTLED evidence event (structural only); failures surface in
    report.issues and never affect recovery completeness (OD-E5)."""
    if evidence is None:
        return
    try:
        capture_id = store.get_document(document_id).capture_id
        payload = {
            "final_state": final_state,
            "settlement_note": note,
            "page_spans": None if spans is None else [
                {"page_index": p.page_index, "byte_start": s[0], "byte_end": s[1]}
                for p, s in zip(pages, spans)
            ],
        }
        outcome = evidence.append(document_id, capture_id, EV_RECOVERY_SETTLED, payload)
        if isinstance(outcome, EvidenceUnavailable):
            report.issues.append(
                f"evidence write unavailable for {document_id} settlement: {outcome.detail}")
    except Exception as exc:                            # defensive: evidence stays auxiliary
        report.issues.append(f"evidence recording anomaly for {document_id}: {exc}")
