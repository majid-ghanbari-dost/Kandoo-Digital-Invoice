"""Ingest flow tests — S1 §6 three-branch idempotency + Store §6.1 settlement (AC-T113-3..5).

Also covers AC-1.1.2/1.1.3/1.1.4 support at the composition level and the Provable-Data
boundary (no downstream datum in any record or outcome — INV-C7/INV-F6).
"""
import json

from capture import (
    NOTE_S1_COMPUTATION_FAILED,
    NOTE_VERIFY_FAILED,
    CaptureService,
    CaptureState,
    IngestCompleted,
    IngestDuplicateAtCapture,
    IngestIntegrityFailureHit,
    IngestSettledFailure,
    IntegrityStatus,
    S1Service,
    S1ComputationFailure,
    FORMAT_HINT_UNKNOWN,
)


def _assert_completed(outcome):
    assert isinstance(outcome, IngestCompleted), f"expected IngestCompleted, got {outcome!r}"
    return outcome


def test_happy_path_ingest_completes(service):
    outcome = _assert_completed(service.ingest(b"first-artifact", source_label="pos-01"))
    rec = outcome.record
    # INV-C1: full identity/evidence field set on COMPLETED
    assert rec.capture_id and rec.s1 and rec.s1_algorithm_id == "sha256-v1"
    assert rec.artifact_ref and rec.created_at and rec.received_at
    assert rec.source_label == "pos-01"
    assert rec.capture_state is CaptureState.COMPLETED
    assert rec.integrity_status is IntegrityStatus.VALID
    assert rec.integrity_verified_at is not None
    assert rec.artifact_size_bytes == len(b"first-artifact")      # F-13
    assert rec.settlement_note is None
    # Provable-Data: entry metadata stored verbatim, nothing inferred (F-12 / INV-C8)
    service2 = service
    rec2 = service2._store.get_record(rec.capture_id)
    assert json.loads(rec2.capture_entry_metadata) == {}


def test_ingest_unknown_channel_and_format_are_explicit(service):
    outcome = _assert_completed(service.ingest(b"\x00\x01opaque"))
    rec = outcome.record
    assert rec.source_label == "UNDECLARED"      # §14 r6
    assert rec.artifact_format_hint == "UNKNOWN"  # §14 r7


def test_format_hint_is_mechanical_only(service):
    outcome = _assert_completed(service.ingest(b"%PDF-1.7 fake pdf bytes"))
    assert outcome.record.artifact_format_hint == "application/pdf"
    outcome2 = _assert_completed(service.ingest(b"\x89PNG\r\n\x1a\nrest"))
    assert outcome2.record.artifact_format_hint == "image/png"


def test_duplicate_submission_returns_existing_capture_id(service):
    """AC-T113-3 / §9 step 2a: duplicate → existing capture_id + duplicate marker; no second record."""
    content = b"same-invoice-scan"
    first = _assert_completed(service.ingest(content, source_label="a"))
    second = service.ingest(content, source_label="b")
    assert isinstance(second, IngestDuplicateAtCapture)
    assert second.existing_capture_id == first.capture_id
    assert second.s1 == first.record.s1 and second.s1_algorithm_id == "sha256-v1"
    completed, total = service._store.count_by_key(second.s1, second.s1_algorithm_id)
    assert completed == 1 and total == 1          # NO second record created (INV-C3)


def test_duplicate_hit_on_failed_record_is_never_dedup_success(service):
    """AC-T113-4 / §14 r5: hit on integrity-FAILED COMPLETED record → explicit integrity failure."""
    content = b"will-be-corrupted"
    first = _assert_completed(service.ingest(content))
    # out-of-store tampering (bypasses the store; Store I-1 makes in-store rewrite impossible)
    raw = service._store._conn
    raw.execute("UPDATE artifact_content SET content = ?", (b"tampered-bytes!!",))
    # the read path now fails explicitly and marks the record FAILED (VOR §7)
    from capture import ReadIntegrityFailure
    read = service.read_evidence(first.capture_id)
    assert isinstance(read, ReadIntegrityFailure)
    assert service._store.get_record(first.capture_id).integrity_status is IntegrityStatus.FAILED

    again = service.ingest(content)
    assert isinstance(again, IngestIntegrityFailureHit)     # never a dedup success
    assert again.existing_capture_id == first.capture_id
    completed, total = service._store.count_by_key(again.s1, again.s1_algorithm_id)
    assert completed == 1 and total == 1                    # no new record


def test_reingest_after_failed_incomplete_is_a_legal_new_attempt(service):
    """AC-T113-5 / S1 §6 note 2: re-capture after FAILED_INCOMPLETE proceeds as new."""
    # force a first-verification FAILED settlement via out-of-store corruption between
    # persist and verify is not reachable through the public flow; instead use the S1 F1
    # path to produce a FAILED_INCOMPLETE, then re-ingest identical content.
    class BrokenS1(S1Service):
        def compute(self, content):
            raise S1ComputationFailure("engine unavailable")
    broken = CaptureService(service._store, BrokenS1())
    failed_outcome = broken.ingest(b"retry-content")
    assert isinstance(failed_outcome, IngestSettledFailure)
    assert failed_outcome.settlement_note == NOTE_S1_COMPUTATION_FAILED
    rec = service._store.get_record(failed_outcome.capture_id)
    assert rec.capture_state is CaptureState.FAILED_INCOMPLETE
    assert rec.integrity_status is IntegrityStatus.FAILED   # v1.1-C2 pin

    good = _assert_completed(service.ingest(b"retry-content"))   # legal new attempt
    completed, total = service._store.count_by_key(good.record.s1, good.record.s1_algorithm_id)
    assert completed == 1 and total == 1
    # the earlier failure carries no S1 key (computation failed pre-attach) — it is not
    # part of this key's counts, but it is retained explicit evidence (INV-C9):
    failed_rec = service._store.get_record(failed_outcome.capture_id)
    assert failed_rec.capture_state is CaptureState.FAILED_INCOMPLETE
    assert failed_rec.settlement_note == NOTE_S1_COMPUTATION_FAILED


def test_s1_compute_failure_settles_explicitly(service):
    """S1 §9 F1 / §14 r2: S1 computation failure → FAILED_INCOMPLETE + note + FAILED."""
    class BrokenS1(S1Service):
        def compute(self, content):
            raise S1ComputationFailure("digest unavailable")
    broken = CaptureService(service._store, BrokenS1())
    outcome = broken.ingest(b"whatever")
    assert isinstance(outcome, IngestSettledFailure)
    assert outcome.settlement_note == NOTE_S1_COMPUTATION_FAILED
    rec = service._store.get_record(outcome.capture_id)
    assert rec.capture_state is CaptureState.FAILED_INCOMPLETE
    assert rec.integrity_status is IntegrityStatus.FAILED
    assert rec.settlement_note == NOTE_S1_COMPUTATION_FAILED  # INV-C9
    assert rec.s1 is None                                      # INV-C1: no COMPLETED without S1


def test_first_verification_failed_settles_with_verify_note(service):
    """S1 §9 F5: first verification FAILED → FAILED_INCOMPLETE (note: verify FAILED)."""
    from capture import Verdict

    class LyingS1(S1Service):
        def verify(self, content, s1, s1_algorithm_id):
            return Verdict("FAILED", "mismatch")            # forced FAILED at V-1
    liar = CaptureService(service._store, LyingS1())
    outcome = liar.ingest(b"verified-bad")
    assert isinstance(outcome, IngestSettledFailure)
    assert outcome.settlement_note == NOTE_VERIFY_FAILED
    rec = service._store.get_record(outcome.capture_id)
    assert rec.capture_state is CaptureState.FAILED_INCOMPLETE
    assert rec.integrity_status is IntegrityStatus.FAILED


def test_entry_metadata_stored_verbatim(service):
    meta = {"channel": "scanner-3", "batch": "B-99"}
    outcome = _assert_completed(
        service.ingest(b"meta-bytes", source_label="scanner", capture_entry_metadata=meta))
    rec = service._store.get_record(outcome.capture_id)
    stored = json.loads(rec.capture_entry_metadata)
    assert stored == meta                                    # verbatim, uninterpreted (F-12)


def test_multi_file_submission_one_record_one_s1(service):
    """§4 r5: one multi-file submission = ONE artifact instance = one record."""
    parts = [b"invoice-page-1", b"invoice-page-2"]
    outcome = _assert_completed(service.ingest(CaptureService.aggregate(parts)))
    assert outcome.record.artifact_size_bytes == len(CaptureService.aggregate(parts))
    dup = service.ingest(CaptureService.aggregate(list(parts)))
    assert isinstance(dup, IngestDuplicateAtCapture)         # same aggregate → same S1 → dedup
