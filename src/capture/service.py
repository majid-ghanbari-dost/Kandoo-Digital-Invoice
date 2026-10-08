"""Capture-layer orchestration — composition of the frozen designs.

  ingest     = S1 Design §6 (three-branch idempotency decision, R-S1-1 single handoff)
               over Store §3 Steps 0–4 + §6.1 D-1 deterministic settlement;
  read path  = VOR Design §3–§7 (V-3 wiring, R-V1 every-read verification, restricted
               F-07/F-08 write BEFORE the outcome, read outcome contract).

The service owns orchestration only. Every durable effect goes through the store
(T-1.1.2 capabilities); every S1 computation goes through the S1 capability (T-1.1.3).
No responsibility is taken from either — and none of the read outcomes carries any
external-document, canonical, or downstream datum (D-02, INV-C7, INV-V7).
"""
from __future__ import annotations

from typing import Iterable, Optional

from .model import (
    FORMAT_HINT_UNKNOWN,
    NOTE_CONTENT_MISSING,
    NOTE_PERSISTENCE_INCOMPLETE,
    NOTE_S1_COMPUTATION_FAILED,
    NOTE_UNIQUENESS_CONFLICT,
    NOTE_VERIFICATION_UNAVAILABLE,
    NOTE_VERIFY_FAILED,
    READ_REASON_MISMATCH,
    READ_REASON_UNREADABLE,
    CaptureLayerError,
    CaptureState,
    ContentMissing,
    ExplicitPersistenceFailure,
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
    StorageUnavailable,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
    utc_now_iso,
)
from .s1 import S1Service, S1ComputationFailure
from .store import CaptureStore

# Mechanical byte-level classification only (F-11) — magic-prefix table, no interpretation.
_MAGIC_PREFIXES = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
    (b"PK\x03\x04", "application/zip"),
    (b"\x1f\x8b", "application/gzip"),
)


class CaptureService:
    """The capture entry point + ingest orchestration + evidence read path (MVP)."""

    def __init__(self, store: CaptureStore, s1: S1Service) -> None:
        self._store = store
        self._s1 = s1
        self._issues: list = []   # VOR §2 "surfaced defects" — operator-facing, in-memory

    # ------------------------------------------------------------------
    # Capture entry point — aggregation (Contract §4 r5, v1.1-C3: determinism binds HERE)
    # ------------------------------------------------------------------

    @staticmethod
    def aggregate(parts: Iterable[bytes]) -> bytes:
        """Deterministic multi-file aggregation: 8-byte big-endian length-prefixed
        concatenation in list order. Same ordered content set → same byte sequence →
        same S1 under the same s1_algorithm_id (v1.1-C3). No names/timestamps embedded."""
        out = bytearray()
        for part in parts:
            data = bytes(part)
            out += len(data).to_bytes(8, "big")
            out += data
        return bytes(out)

    @staticmethod
    def sniff_format_hint(content: bytes) -> str:
        """Mechanical, byte-level only (F-11); undeterminable → UNKNOWN (§14 r7)."""
        for magic, hint in _MAGIC_PREFIXES:
            if content.startswith(magic):
                return hint
        return FORMAT_HINT_UNKNOWN

    # ------------------------------------------------------------------
    # Ingest — S1 §6 mandatory procedure (the sequential case)
    # ------------------------------------------------------------------

    def ingest(
        self,
        content: bytes,
        *,
        received_at: Optional[str] = None,
        source_label: Optional[str] = None,
        capture_entry_metadata: Optional[dict] = None,
        artifact_format_hint: Optional[str] = None,
    ) -> object:
        """Ingest one Artifact Instance (one submission = one artifact = one record, §3).

        Outcome is exactly one explicit type — never silent:
          IngestCompleted | IngestDuplicateAtCapture | IngestIntegrityFailureHit |
          IngestSettledFailure (D-1) | IngestUniquenessConflict (UAC loser, P3) |
          IngestStorageUnavailable (D-2 residue; startup recovery will settle).
        """
        received_at = received_at or utc_now_iso()                       # F-09 (event time)
        hint = artifact_format_hint if artifact_format_hint is not None else self.sniff_format_hint(content)

        # Step 1 (S1 §6): compute S1 over the exact delivered bytes.
        # R-S1-1 single handoff: THIS byte sequence is also what the store persists.
        try:
            s1v = self._s1.compute(content)
        except S1ComputationFailure as exc:
            # S1 §9 F1 / Contract §14 r2: explicit FAILED_INCOMPLETE + note — never silent,
            # no COMPLETED record without S1 (INV-C1).
            rec = self._store.create_active(
                received_at=received_at, source_label=source_label,
                artifact_format_hint=hint, capture_entry_metadata=capture_entry_metadata)
            self._store.settle_failed(rec.capture_id, NOTE_S1_COMPUTATION_FAILED)
            return IngestSettledFailure(rec.capture_id, NOTE_S1_COMPUTATION_FAILED, str(exc))

        # Step 2 (S1 §6): COMPLETED-restricted lookup; the decision is exactly §9's branches.
        hits = self._store.find_completed(s1v.s1, s1v.s1_algorithm_id)
        if hits:
            hit = hits[0]
            if hit.integrity_status == IntegrityStatus.FAILED:
                # §9 step 2b / §14 r5: explicit integrity-failure path — NEVER a dedup
                # success, no new record, never silent.
                return IngestIntegrityFailureHit(hit.capture_id, s1v.s1, s1v.s1_algorithm_id)
            # §9 step 2a: hit with VALID (a COMPLETED record is never UNVERIFIED — Store
            # completion gate). No second record is created.
            return IngestDuplicateAtCapture(hit.capture_id, s1v.s1, s1v.s1_algorithm_id)

        # Step 3 (S1 §6 miss branch): new record through Store §3 Steps 0–4.
        try:
            record = self._store.create_active(                          # Step 0 (R-1)
                received_at=received_at, source_label=source_label,
                artifact_format_hint=hint, capture_entry_metadata=capture_entry_metadata)
        except RecordCreationFailed as exc:
            # Store F2: nothing persisted; explicit failure; no residue.
            return IngestSettledFailure(None, NOTE_PERSISTENCE_INCOMPLETE, str(exc))

        try:
            self._store.persist_content(record.capture_id, content)      # Step 1 (R-2 basis)
        except ExplicitPersistenceFailure as exc:
            # §6.1 D-1: the store already settled FAILED_INCOMPLETE synchronously.
            return IngestSettledFailure(exc.capture_id, exc.settlement_note, str(exc))
        except StorageUnavailable as exc:
            # §6.1 D-2: no verdict durably recordable — ACTIVE residue, settled at startup.
            return IngestStorageUnavailable(str(exc))

        self._store.attach_s1(record.capture_id, s1v.s1, s1v.s1_algorithm_id)   # Step 2

        # Step 3: first verification — over the byte-exact STORED content (Contract §10:
        # recompute over the content of artifact_ref), using the record's own id.
        # Refresh the record first: artifact_ref/F-13 were finalized at Step 1 (R-2 basis).
        record = self._store.get_record(record.capture_id)
        try:
            stored = self._store.get_content(record.artifact_ref)
        except ContentMissing:
            # O-3 at V-1: FAILED (unreadable/missing) — recorded, gate unmet → settlement.
            verified_at = utc_now_iso()
            self._store.record_verification(record.capture_id, "FAILED", verified_at)
            self._store.settle_failed(record.capture_id, NOTE_VERIFY_FAILED)
            return IngestSettledFailure(record.capture_id, NOTE_VERIFY_FAILED,
                                        "first verification could not read stored content")

        verdict = self._s1.verify(stored, s1v.s1, s1v.s1_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            # Store §5 note / S1 §9 F2: no verdict computable → the only contract-legal
            # ending is conservative FAILED_INCOMPLETE; no integrity write (INV-V8 analog).
            self._store.settle_failed(record.capture_id, NOTE_VERIFICATION_UNAVAILABLE)
            return IngestSettledFailure(record.capture_id, NOTE_VERIFICATION_UNAVAILABLE,
                                        verdict.reason or "verification unavailable")
        if verdict.outcome == "FAILED":
            # S1 §9 F5: first verification FAILED → completion gate unmet → synchronous
            # settlement with the pinned FAILED + note; record retained as evidence.
            verified_at = utc_now_iso()
            self._store.record_verification(record.capture_id, "FAILED", verified_at)
            self._store.settle_failed(record.capture_id, NOTE_VERIFY_FAILED)
            return IngestSettledFailure(record.capture_id, NOTE_VERIFY_FAILED, "first verification FAILED")

        self._store.record_verification(record.capture_id, "VALID", utc_now_iso())  # gate input

        # Step 4: completion through the store's UAC primitive — the only completion path.
        outcome = self._store.complete_record(record.capture_id)
        if outcome == UAC_GRANTED:
            return IngestCompleted(record.capture_id, self._store.get_record(record.capture_id))

        # UAC_UNIQUENESS_CONFLICT (S1 §9 F4 / Store §9.1 P3): settle THIS record
        # FAILED_INCOMPLETE with the uniqueness-conflict note; explicit conflict outcome.
        self._store.settle_failed(record.capture_id, NOTE_UNIQUENESS_CONFLICT)
        return IngestUniquenessConflict(record.capture_id, NOTE_UNIQUENESS_CONFLICT)

    # ------------------------------------------------------------------
    # Evidence read — VOR §4–§7 (V-3; R-V1; write-before-outcome)
    # ------------------------------------------------------------------

    def read_evidence(self, capture_id: str) -> object:
        """Read artifact evidence with a definitive integrity verdict computed INSIDE the
        read (R-V1 — no caching). COMPLETED records only; every outcome explicit:
          ReadSuccess (content + VALID, same read) | ReadIntegrityFailure (FAILED + reason,
          NEVER content) | ReadRefused (non-COMPLETED / unknown id) |
          ReadVerificationUnavailable (O-4 NO-VERDICT; Issue-Report surfacing).
        The restricted F-07/F-08 write always completes BEFORE the outcome is returned
        (VOR §7 rule 3 / INV-V3). No lifecycle transition is ever performed here."""
        try:
            record = self._store.get_record(capture_id)
        except RecordNotFound:
            return ReadRefused(None, None, "no such capture record")

        if record.capture_state != CaptureState.COMPLETED:
            # VOR §5 scope rule / INV-V6: ACTIVE is unresolved, FAILED_INCOMPLETE is pinned
            # terminal — no content, no verdict, no state change.
            return ReadRefused(record.capture_id, record.capture_state.value,
                               "evidence read serves COMPLETED records only")

        if record.integrity_status == IntegrityStatus.UNVERIFIED or not record.s1 or not record.s1_algorithm_id:
            # Unreachable per the store's completion gate + INV-C1 — a store-defect
            # condition: explicit read failure + Issue-Report surfacing; never a verdict,
            # never content (VOR §5 matrix row 1).
            issue = ("store defect: COMPLETED record violates the completion gate / INV-C1 "
                     "(UNVERIFIED or missing S1 fields)")
            self._issues.append(issue)
            return ReadVerificationUnavailable(record.capture_id, issue + " — Issue Report required")

        try:
            content = self._store.get_content(record.artifact_ref)
        except ContentMissing:
            # O-3: FAILED (unreadable/missing) — write-before-outcome; no auto-repair,
            # no delete, no rewrite (§10 r4); resolution path = Issue Report only.
            verified_at = utc_now_iso()
            self._store.record_verification(record.capture_id, "FAILED", verified_at)
            return ReadIntegrityFailure(record.capture_id, READ_REASON_UNREADABLE, verified_at)

        # O-1 / O-2 / O-4 via the record's OWN s1_algorithm_id (INV-V4).
        verdict = self._s1.verify(content, record.s1, record.s1_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            # O-4: no integrity-field write (INV-V8), no content, explicit read failure
            # + Issue-Report surfacing (VOR §5 rows with O-4; §6).
            issue = f"verification unavailable: {verdict.reason or 'capability failure'}"
            self._issues.append(f"capture {record.capture_id}: {issue}")
            return ReadVerificationUnavailable(record.capture_id, issue + " — Issue Report required")

        verified_at = utc_now_iso()
        # Restricted write BEFORE the outcome is returned (INV-V3) — the only write this
        # path ever performs (INV-V5). Truthful latest result semantics (F-07), including
        # the FAILED→VALID transition, which is a recorded verdict — NOT auto-repair
        # (content untouched; Store I-1; corruption resolution stays with Issue Report).
        self._store.record_verification(record.capture_id, verdict.outcome, verified_at)

        if verdict.outcome == "VALID":
            return ReadSuccess(record.capture_id, content, "VALID",
                               record.s1, record.s1_algorithm_id, verified_at)
        return ReadIntegrityFailure(record.capture_id, READ_REASON_MISMATCH, verified_at)

    # ------------------------------------------------------------------
    # Issue-report surface (VOR §2 "surfaced defects" — minimal MVP hook)
    # ------------------------------------------------------------------

    def issue_reports(self) -> list:
        """Accumulated Issue-Report items surfaced by this service instance (O-4 /
        store-defect conditions). MVP: in-memory only, operator-facing."""
        return list(self._issues)
