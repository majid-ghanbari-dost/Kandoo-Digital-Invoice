"""Reconstruction service — build + verified read (T-2.1.3 scope) + evidence emission
(WP-2.2 — non-intrusive, optional; SPEC-WP22-REC).

Binding basis: SPEC-WP21-RC §1–§7; AS-01 (Capture → Reconstruction → Extraction);
D-02/D-03 untouched (no S2, no document-level dedup — the only uniqueness here is the
INV-R-1:1 capture→document binding of AC-2.1.1).

  reconstruct(capture_id)  = verified capture read (VOR path, WP-1.1 service) → mechanical
                             page derivation (pages.derive_pages) → record-first ACTIVE
                             document → verbatim page persist with per-page fingerprints →
                             first verification over the DURABLE bytes → INV-R-1:1
                             completion through the store's UAC primitive.
  read_document(document_id) = VOR-pattern verified read: every-read verification (no
                             caching), restricted verdict write BEFORE the outcome, content
                             delivered only on the same-read VALID verdict.

Evidence (WP-2.2, OD-E5): when an EvidenceStore is wired in, terminal outcomes emit
structural evidence events (document-scoped only). Recording is NON-INTRUSIVE: it never
alters an outcome, never delivers/blocks content, and every evidence failure surfaces
through issue_reports() — never silently. With evidence=None the behavior is exactly
the frozen WP-2.1 behavior.

The service owns orchestration only; every durable effect goes through the store; every
fingerprint computation goes through the reused capture S1 capability (sha256-v1).
No extracted/interpreted datum is produced anywhere — pages are verbatim byte slices.
"""
from __future__ import annotations

from typing import List, Optional

from capture import (
    ReadIntegrityFailure,
    ReadRefused,
    ReadSuccess,
    ReadVerificationUnavailable,
    CaptureService,
    S1Service,
)

from .model import (
    NOTE_PAGES_INCOMPLETE,
    NOTE_PERSISTENCE_INCOMPLETE,
    NOTE_UNIQUENESS_CONFLICT,
    NOTE_VERIFICATION_UNAVAILABLE,
    NOTE_VERIFY_FAILED,
    READ_REASON_DOC_MISMATCH,
    READ_REASON_PAGE_MISMATCH,
    DocumentCreationFailed,
    DocumentIntegrity,
    DocumentNotFound,
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadSuccess,
    DocumentReadVerificationUnavailable,
    DocumentState,
    ExplicitPersistenceFailure,
    PageView,
    ReconstructAlreadyExists,
    ReconstructCompleted,
    ReconstructSettledFailure,
    ReconstructSourceIntegrityFailure,
    ReconstructSourceRefused,
    ReconstructSourceUnavailable,
    ReconstructStorageUnavailable,
    ReconstructUniquenessConflict,
    StorageUnavailable,
    UAC_GRANTED,
    utc_now_iso,
)
from .evidence import (
    DERIVATION_ID,
    EV_DOCUMENT_COMPLETED,
    EV_DOCUMENT_SETTLED_FAILED,
    EV_VERIFIED_READ,
    EvidenceUnavailable,
    spans_from_durable,
)
from .pages import derive_pages, reassemble
from .store import ReconstructionStore


class ReconstructionService:
    """The reconstruction entry point: verified capture → Document/Page → verified read."""

    def __init__(self, store: ReconstructionStore, capture: CaptureService, s1: S1Service,
                 evidence=None) -> None:
        self._store = store
        self._capture = capture
        self._s1 = s1
        self._evidence = evidence     # optional EvidenceStore (WP-2.2); None = frozen WP-2.1 shape
        self._issues: list = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Build — verified capture → durable Document (SPEC-WP21-RC §2–§6)
    # ------------------------------------------------------------------

    def reconstruct(self, capture_id: str) -> object:
        """Build one durable Document from a COMPLETED, integrity-VALID capture.

        Outcome is exactly one explicit type — never silent:
          ReconstructCompleted | ReconstructAlreadyExists (INV-R-1:1, no second document) |
          ReconstructSourceIntegrityFailure | ReconstructSourceRefused |
          ReconstructSourceUnavailable (nothing created — source-side outcomes) |
          ReconstructSettledFailure (D-1) | ReconstructUniquenessConflict (UAC loser) |
          ReconstructStorageUnavailable (D-2 residue; startup recovery settles).
        """
        outcome = self._reconstruct(capture_id)
        self._record_reconstruct_outcome(capture_id, outcome)   # evidence; never alters the outcome
        return outcome

    def _reconstruct(self, capture_id: str) -> object:
        # Step 0: INV-R-1:1 — an existing COMPLETED document for this capture is returned
        # explicitly; no second document is ever created (UAC still backstops races).
        existing = self._store.find_completed_for_capture(capture_id)
        if existing is not None:
            return ReconstructAlreadyExists(existing.document_id, capture_id)

        # Step 1: verified source read — the ONLY sanctioned path into capture content
        # (VOR: verdict computed inside the read; FAILED never delivers content).
        read = self._capture.read_evidence(capture_id)
        if isinstance(read, ReadIntegrityFailure):
            return ReconstructSourceIntegrityFailure(capture_id, read.reason)
        if isinstance(read, ReadRefused):
            return ReconstructSourceRefused(read.capture_id, read.capture_state, read.detail)
        if isinstance(read, ReadVerificationUnavailable):
            return ReconstructSourceUnavailable(capture_id, read.issue_report)
        assert isinstance(read, ReadSuccess)          # exhaustive by construction
        artifact: bytes = read.content

        # Step 2: mechanical page derivation (content-blind; deterministic; tiling).
        parts = derive_pages(artifact)

        # Step 3: integrity anchors — per-page fingerprints + document fingerprint over
        # the canonical reassembly (uniform frozen framing; OD-R2/OD-R4).
        page_fps: List[tuple] = []
        for part in parts:
            fp = self._s1.compute(part)               # sha256-v1, deterministic
            page_fps.append((part, fp.s1, fp.s1_algorithm_id))
        canonical = reassemble(parts)
        doc_fp = self._s1.compute(canonical)
        # Defense-in-depth tiling gate: a total parse re-assembles byte-exactly; a
        # single-page fallback tiles trivially. Failure here = derivation defect →
        # fail-closed BEFORE anything is persisted.
        if len(parts) > 1 and canonical != artifact:
            return ReconstructSettledFailure(
                None, NOTE_PERSISTENCE_INCOMPLETE,
                "derivation defect: canonical reassembly does not tile the artifact")

        # Step 4: record-first (R-1 analog) — ACTIVE document with full traceability.
        try:
            record = self._store.create_active_document(
                capture_id=capture_id,
                capture_s1=read.s1,
                capture_s1_algorithm_id=read.s1_algorithm_id,
                document_fingerprint=doc_fp.s1,
                fingerprint_algorithm_id=doc_fp.s1_algorithm_id,
            )
        except DocumentCreationFailed as exc:
            return ReconstructSettledFailure(None, NOTE_PERSISTENCE_INCOMPLETE, str(exc))

        # Step 5: verbatim page persist (one atomic txn; D-1 analog on definitive error).
        try:
            self._store.persist_pages(record.document_id, page_fps)
        except ExplicitPersistenceFailure as exc:
            return ReconstructSettledFailure(exc.document_id, exc.settlement_note, str(exc))
        except StorageUnavailable as exc:
            return ReconstructStorageUnavailable(str(exc))

        # Step 6: first verification over the DURABLE bytes (re-read from the store —
        # not the in-memory slices; V-1 analog).
        verdict_note = self._verify_document_internals(record.document_id)
        if verdict_note is not None:                  # settled synchronously inside
            return ReconstructSettledFailure(record.document_id, verdict_note,
                                             "first verification failed document internals")

        # Step 7: completion through the store's UAC primitive (the only completion path).
        outcome = self._store.complete_document(record.document_id)
        if outcome == UAC_GRANTED:
            return ReconstructCompleted(self._store.get_document(record.document_id))
        # UAC_UNIQUENESS_CONFLICT: settle THIS construction FAILED_INCOMPLETE (P3 loser).
        self._store.settle_failed(record.document_id, NOTE_UNIQUENESS_CONFLICT)
        return ReconstructUniquenessConflict(record.document_id, NOTE_UNIQUENESS_CONFLICT)

    # ------------------------------------------------------------------
    # Verified read — VOR pattern bound to documents (SPEC-WP21-RC §6)
    # ------------------------------------------------------------------

    def read_document(self, document_id: str) -> object:
        """Read a document with a definitive integrity verdict computed INSIDE the read.
        Every outcome explicit: DocumentReadSuccess (ordered pages + VALID) |
        DocumentReadIntegrityFailure (FAILED + coarse reason, NEVER content) |
        DocumentReadRefused (non-COMPLETED / unknown id) |
        DocumentReadVerificationUnavailable (no verdict computable; Issue-Report).
        The restricted integrity write always completes BEFORE the outcome is returned.
        No lifecycle transition is ever performed here."""
        outcome = self._read_document(document_id)
        self._record_read_outcome(outcome)                      # evidence; never alters the outcome
        return outcome

    def _read_document(self, document_id: str) -> object:
        try:
            record = self._store.get_document(document_id)
        except DocumentNotFound:
            return DocumentReadRefused(None, None, "no such document")

        if record.document_state != DocumentState.COMPLETED:
            # ACTIVE is unresolved, FAILED_INCOMPLETE is pinned terminal — no content,
            # no verdict, no state change (VOR scope rule analog).
            return DocumentReadRefused(record.document_id, record.document_state.value,
                                       "document read serves COMPLETED documents only")

        if (record.integrity_status == DocumentIntegrity.UNVERIFIED
                or not record.document_fingerprint
                or not record.fingerprint_algorithm_id):
            # Unreachable per the completion gate — a store-defect condition: explicit
            # read failure + Issue-Report surfacing; never a verdict, never content.
            issue = ("store defect: COMPLETED document violates the completion gate "
                     "(UNVERIFIED or missing fingerprint anchor)")
            self._issues.append(f"document {record.document_id}: {issue}")
            return DocumentReadVerificationUnavailable(record.document_id,
                                                       issue + " — Issue Report required")

        try:
            pages = self._store.get_pages(record.document_id)
        except DocumentNotFound:                       # pragma: no cover - defensive
            return DocumentReadRefused(record.document_id, None, "document vanished mid-read")

        if record.page_count is None or len(pages) != record.page_count:
            issue = (f"store defect: durable page set inconsistent "
                     f"(page_count={record.page_count}, rows={len(pages)})")
            self._issues.append(f"document {record.document_id}: {issue}")
            return DocumentReadVerificationUnavailable(record.document_id,
                                                       issue + " — Issue Report required")

        # Per-page verification (same-read; unknown algorithm id → NO_VERDICT path).
        for page in pages:
            verdict = self._s1.verify(page.content, page.page_fingerprint,
                                      page.fingerprint_algorithm_id)
            if verdict.outcome == "NO_VERDICT":
                issue = (f"page {page.page_index} verification unavailable: "
                         f"{verdict.reason or 'capability failure'}")
                self._issues.append(f"document {record.document_id}: {issue}")
                return DocumentReadVerificationUnavailable(record.document_id,
                                                           issue + " — Issue Report required")
            if verdict.outcome == "FAILED":
                verified_at = utc_now_iso()
                self._store.record_verification(record.document_id, "FAILED", verified_at)
                return DocumentReadIntegrityFailure(record.document_id,
                                                    READ_REASON_PAGE_MISMATCH, verified_at)

        # Document-level verification: canonical reassembly of the ordered pages.
        canonical = reassemble(page.content for page in pages)
        doc_verdict = self._s1.verify(canonical, record.document_fingerprint,
                                      record.fingerprint_algorithm_id)
        if doc_verdict.outcome == "NO_VERDICT":
            issue = (f"document verification unavailable: "
                     f"{doc_verdict.reason or 'capability failure'}")
            self._issues.append(f"document {record.document_id}: {issue}")
            return DocumentReadVerificationUnavailable(record.document_id,
                                                       issue + " — Issue Report required")
        verified_at = utc_now_iso()
        # Restricted write BEFORE the outcome (INV-V3 analog) — truthful latest result.
        self._store.record_verification(record.document_id, doc_verdict.outcome, verified_at)
        if doc_verdict.outcome == "FAILED":
            return DocumentReadIntegrityFailure(record.document_id,
                                                READ_REASON_DOC_MISMATCH, verified_at)

        return DocumentReadSuccess(
            document_id=record.document_id,
            capture_id=record.capture_id,
            capture_s1=record.capture_s1,
            capture_s1_algorithm_id=record.capture_s1_algorithm_id,
            page_count=record.page_count,
            pages=tuple(PageView(page_index=p.page_index, content=p.content,
                                 byte_len=p.byte_len, page_fingerprint=p.page_fingerprint,
                                 fingerprint_algorithm_id=p.fingerprint_algorithm_id)
                        for p in pages),
            verified_at=verified_at,
        )

    # ------------------------------------------------------------------
    # Evidence emission (WP-2.2 — non-intrusive recorder; OD-E5)
    # ------------------------------------------------------------------

    def _record_evidence(self, event_type: str, document_id: str, capture_id: str,
                         payload: dict) -> None:
        """Append one evidence event; every failure surfaces via issue_reports() and
        NEVER propagates into the reconstruction flow (AC-2.2.5)."""
        if self._evidence is None:
            return
        try:
            outcome = self._evidence.append(document_id, capture_id, event_type, payload)
        except Exception as exc:                    # defensive: evidence must not alter behavior
            self._issues.append(f"evidence append anomaly: {exc}")
            return
        if isinstance(outcome, EvidenceUnavailable):
            self._issues.append(
                f"evidence write unavailable (reconstruction unaffected): {outcome.detail}")

    def _capture_id_of(self, document_id: str) -> Optional[str]:
        """Durable capture_id of a document (evidence binding); None if unreadable."""
        try:
            return self._store.get_document(document_id).capture_id
        except Exception:                           # evidence stays auxiliary — never fatal
            return None

    def _completed_payload(self, document_id: str) -> Optional[dict]:
        """Structural DOCUMENT_COMPLETED payload derived from DURABLE state only
        (OD-E4): fingerprints + framing-derived source byte spans + page fingerprints.
        Content is never included (AC-2.2.4)."""
        try:
            record = self._store.get_document(document_id)
            pages = self._store.get_pages(document_id)
        except Exception as exc:
            self._issues.append(f"evidence payload unavailable for {document_id}: {exc}")
            return None
        if (record.page_count is None or not record.document_fingerprint
                or not record.fingerprint_algorithm_id or len(pages) != record.page_count):
            self._issues.append(
                f"evidence payload skipped for {document_id}: durable state incomplete")
            return None
        # OD-E4 format discriminator: the frozen tiling gate makes the canonical
        # reassembly byte-identical to the source artifact iff it was aggregate-format.
        aggregate_format = record.document_fingerprint == record.capture_s1
        spans = spans_from_durable([p.byte_len for p in pages], aggregate_format)
        if spans is None:
            self._issues.append(
                f"evidence spans unavailable for {document_id} "
                f"(aggregate_format={aggregate_format}, pages={len(pages)})")
        return {
            "capture_s1": record.capture_s1,
            "page_count": record.page_count,
            "document_fingerprint": record.document_fingerprint,
            "fingerprint_algorithm_id": record.fingerprint_algorithm_id,
            "derivation_id": DERIVATION_ID,
            "page_spans": None if spans is None else [
                {"page_index": p.page_index, "byte_start": s[0], "byte_end": s[1],
                 "page_fingerprint": p.page_fingerprint}
                for p, s in zip(pages, spans)
            ],
        }

    def _record_reconstruct_outcome(self, capture_id: str, outcome: object) -> None:
        """Emit document-scoped evidence for terminal reconstruct outcomes. Source-side
        outcomes (nothing created) and AlreadyExists are attempt-level audit items —
        deferred (contract §10); they never fabricate a document-scoped event."""
        if self._evidence is None:
            return
        try:
            if isinstance(outcome, ReconstructCompleted):
                payload = self._completed_payload(outcome.document.document_id)
                if payload is not None:
                    self._record_evidence(EV_DOCUMENT_COMPLETED,
                                          outcome.document.document_id, capture_id, payload)
            elif isinstance(outcome, (ReconstructSettledFailure, ReconstructUniquenessConflict)):
                if outcome.document_id:
                    self._record_evidence(
                        EV_DOCUMENT_SETTLED_FAILED, outcome.document_id, capture_id,
                        {"settlement_note": outcome.settlement_note})
        except Exception as exc:                    # defensive: evidence must not alter behavior
            self._issues.append(f"evidence recording anomaly: {exc}")

    def _record_read_outcome(self, outcome: object) -> None:
        """Emit VERIFIED_READ evidence for document reads. Unknown-id refusals (no
        document) produce no event — evidence is document-scoped, never fabricated."""
        if self._evidence is None:
            return
        try:
            if isinstance(outcome, DocumentReadSuccess):
                self._record_evidence(EV_VERIFIED_READ, outcome.document_id,
                                      outcome.capture_id, {"verdict": "VALID"})
            elif isinstance(outcome, DocumentReadIntegrityFailure):
                capture_id = self._capture_id_of(outcome.document_id)
                if capture_id is not None:
                    self._record_evidence(EV_VERIFIED_READ, outcome.document_id, capture_id,
                                          {"verdict": "FAILED", "reason": outcome.reason})
            elif isinstance(outcome, DocumentReadRefused):
                if outcome.document_id is not None:     # existing but non-COMPLETED
                    capture_id = self._capture_id_of(outcome.document_id)
                    if capture_id is not None:
                        self._record_evidence(
                            EV_VERIFIED_READ, outcome.document_id, capture_id,
                            {"verdict": "REFUSED", "state": outcome.document_state})
            elif isinstance(outcome, DocumentReadVerificationUnavailable):
                capture_id = self._capture_id_of(outcome.document_id)
                if capture_id is not None:
                    self._record_evidence(EV_VERIFIED_READ, outcome.document_id,
                                          capture_id, {"verdict": "NO_VERDICT"})
        except Exception as exc:                    # defensive: evidence must not alter behavior
            self._issues.append(f"evidence recording anomaly: {exc}")

    # ------------------------------------------------------------------
    # Internal verification helper (shared shape with recovery)
    # ------------------------------------------------------------------

    def _verify_document_internals(self, document_id: str) -> Optional[str]:
        """Verify durable pages + reassembly against the stored anchors (V-1 analog).

        Returns None iff everything verified VALID and the verdict was recorded; any
        other ending settles the document synchronously (D-1) and returns the note.
        """
        try:
            record = self._store.get_document(document_id)
            pages = self._store.get_pages(document_id)
        except DocumentNotFound as exc:                # pragma: no cover - defensive
            self._issues.append(f"document {document_id}: vanished during verification")
            self._settle_quietly(document_id, NOTE_PAGES_INCOMPLETE)
            return f"internal error: {exc}"

        if record.page_count is None or not record.document_fingerprint \
                or not record.fingerprint_algorithm_id \
                or len(pages) != record.page_count:
            self._store.settle_failed(document_id, NOTE_PAGES_INCOMPLETE)
            return NOTE_PAGES_INCOMPLETE

        for page in pages:
            verdict = self._s1.verify(page.content, page.page_fingerprint,
                                      page.fingerprint_algorithm_id)
            if verdict.outcome == "NO_VERDICT":
                self._issues.append(
                    f"document {document_id}: page {page.page_index} verification "
                    f"unavailable ({verdict.reason or 'capability failure'})")
                self._store.settle_failed(document_id, NOTE_VERIFICATION_UNAVAILABLE)
                return NOTE_VERIFICATION_UNAVAILABLE
            if verdict.outcome == "FAILED":
                self._store.record_verification(document_id, "FAILED", utc_now_iso())
                self._store.settle_failed(document_id, NOTE_VERIFY_FAILED)
                return NOTE_VERIFY_FAILED

        canonical = reassemble(page.content for page in pages)
        doc_verdict = self._s1.verify(canonical, record.document_fingerprint,
                                      record.fingerprint_algorithm_id)
        if doc_verdict.outcome == "NO_VERDICT":
            self._issues.append(
                f"document {document_id}: verification unavailable "
                f"({doc_verdict.reason or 'capability failure'})")
            self._store.settle_failed(document_id, NOTE_VERIFICATION_UNAVAILABLE)
            return NOTE_VERIFICATION_UNAVAILABLE
        if doc_verdict.outcome == "FAILED":
            self._store.record_verification(document_id, "FAILED", utc_now_iso())
            self._store.settle_failed(document_id, NOTE_VERIFY_FAILED)
            return NOTE_VERIFY_FAILED

        self._store.record_verification(document_id, "VALID", utc_now_iso())
        return None

    def _settle_quietly(self, document_id: str, note: str) -> None:
        try:
            self._store.settle_failed(document_id, note)
        except Exception:                              # pragma: no cover - defensive
            pass

    # ------------------------------------------------------------------
    # Issue-report surface (minimal MVP hook, VOR §2 analog)
    # ------------------------------------------------------------------

    def issue_reports(self) -> list:
        """Accumulated Issue-Report items surfaced by this service instance."""
        return list(self._issues)
