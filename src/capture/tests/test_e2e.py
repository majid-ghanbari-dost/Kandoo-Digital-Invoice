"""Minimal E2E — the full dispatched MVP path, real and end-to-end:

  Artifact (multi-file, deterministically aggregated)
    → Durable Local Store (record-first R-1, byte-exact content)
    → S1 (sha256-v1)
    → Capture-level Idempotency (three-branch §9)
    → Verification (first verification VALID, UAC completion)
    → COMPLETED
    → Verified Read (R-V1 verify-inside-read)
  + failure/recovery behavior mandated by the frozen documents (restart, tamper).
"""
import pytest

from capture import (
    CaptureService,
    CaptureStore,
    CaptureState,
    IngestCompleted,
    IngestDuplicateAtCapture,
    IngestIntegrityFailureHit,
    IntegrityStatus,
    ReadIntegrityFailure,
    ReadSuccess,
    S1Service,
    run_startup_recovery,
)


def test_full_mvp_journey(tmp_path):
    db_path = tmp_path / "e2e-capture.db"

    # ---- 1. ingest a multi-file artifact through the deterministic entry-point aggregation
    store = CaptureStore(db_path)
    service = CaptureService(store, S1Service())
    artifact = CaptureService.aggregate([b"invoice-scan-page-1;", b"invoice-scan-page-2;"])
    outcome = service.ingest(artifact, source_label="pos-01",
                             capture_entry_metadata={"terminal": "T-7"})
    assert isinstance(outcome, IngestCompleted)
    capture_id = outcome.capture_id
    record = outcome.record
    assert record.capture_state is CaptureState.COMPLETED
    assert record.integrity_status is IntegrityStatus.VALID
    assert record.artifact_size_bytes == len(artifact)
    assert record.s1_algorithm_id == "sha256-v1"

    # ---- 2. verified read delivers byte-exact content with a same-read VALID verdict
    read = service.read_evidence(capture_id)
    assert isinstance(read, ReadSuccess)
    assert read.content == artifact
    assert read.verdict == "VALID"

    # ---- 3. capture-level idempotency: same artifact → duplicate-at-capture, no new record
    dup = service.ingest(artifact, source_label="pos-02")
    assert isinstance(dup, IngestDuplicateAtCapture)
    assert dup.existing_capture_id == capture_id

    # ---- 4. restart: fresh process opens the same durable store; startup recovery runs
    store.close()
    store2 = CaptureStore(db_path)
    service2 = CaptureService(store2, S1Service())
    report = run_startup_recovery(store2, S1Service())
    assert report.complete is True and report.remaining_active == 0   # INV-C6
    reread = service2.read_evidence(capture_id)
    assert isinstance(reread, ReadSuccess)
    assert reread.content == artifact                                 # durability (AC-1.1.6)

    # ---- 5. a different artifact ingests independently (no false dedup)
    other = CaptureService.aggregate([b"another-document;"])
    other_outcome = service2.ingest(other, source_label="pos-01")
    assert isinstance(other_outcome, IngestCompleted)
    assert other_outcome.capture_id != capture_id

    # ---- 6. out-of-store tampering of the FIRST artifact → next read fails explicitly
    store2._conn.execute(
        "UPDATE artifact_content SET content = ? WHERE content_ref = ?",
        (b"invoice-scan-page-1!;invoice-scan-page-2;", record.artifact_ref))
    tampered_read = service2.read_evidence(capture_id)
    assert isinstance(tampered_read, ReadIntegrityFailure)
    assert tampered_read.reason == "mismatch"
    tampered_record = store2.get_record(capture_id)
    assert tampered_record.integrity_status is IntegrityStatus.FAILED     # INV-V3
    assert tampered_record.capture_state is CaptureState.COMPLETED        # §7 r4
    assert tampered_record.settlement_note is None                        # F-15 stays empty

    # ---- 7. re-ingest of the now-FAILED artifact → explicit integrity failure, never dedup
    hit = service2.ingest(artifact)
    assert isinstance(hit, IngestIntegrityFailureHit)
    assert hit.existing_capture_id == capture_id

    # ---- 8. second restart: recovery settles nothing new (idempotent), zero ACTIVE
    store2.close()
    store3 = CaptureStore(db_path)
    service3 = CaptureService(store3, S1Service())
    report2 = run_startup_recovery(store3, S1Service())
    assert report2.complete is True
    assert report2.settled_completed == [] and report2.settled_failed == []

    # ---- 9. final invariants sweep over the whole store
    rows = store3._conn.execute("SELECT capture_state, COUNT(*) AS n FROM capture_records GROUP BY capture_state").fetchall()
    states = {r["capture_state"]: r["n"] for r in rows}
    assert states.get("ACTIVE", 0) == 0                                   # INV-C6
    assert states.get("COMPLETED", 0) == 2                                # two valid captures
    failed_rows = store3._conn.execute(
        "SELECT COUNT(*) AS n FROM capture_records WHERE capture_state = 'FAILED_INCOMPLETE' "
        "AND (settlement_note IS NULL OR integrity_status <> 'FAILED')").fetchone()["n"]
    assert failed_rows == 0                                               # INV-C9
    store3.close()
