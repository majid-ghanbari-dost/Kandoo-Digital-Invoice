"""Cold-start smoke check — runs the dispatched MVP path without pytest.

Usage: python3 kandoo/src/run_smoke.py /tmp/kandoo-smoke.db
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import (  # noqa: E402
    CaptureService,
    CaptureStore,
    CaptureState,
    IngestCompleted,
    IngestDuplicateAtCapture,
    IntegrityStatus,
    ReadIntegrityFailure,
    ReadSuccess,
    S1Service,
    run_startup_recovery,
)


def main(db_path: str) -> int:
    store = CaptureStore(db_path)
    service = CaptureService(store, S1Service())

    artifact = CaptureService.aggregate([b"page-one;", b"page-two;"])
    outcome = service.ingest(artifact, source_label="smoke")
    assert isinstance(outcome, IngestCompleted), outcome
    print(f"1. ingest      -> COMPLETED capture_id={outcome.capture_id[:12]}… "
          f"s1={outcome.record.s1[:16]}… state={outcome.record.capture_state.value}")

    read = service.read_evidence(outcome.capture_id)
    assert isinstance(read, ReadSuccess) and read.content == artifact
    print(f"2. read        -> verdict={read.verdict} bytes={len(read.content)} (byte-exact)")

    dup = service.ingest(artifact)
    assert isinstance(dup, IngestDuplicateAtCapture)
    print(f"3. duplicate   -> existing capture_id={dup.existing_capture_id[:12]}… (dedup, no new record)")

    store.close()
    store2 = CaptureStore(db_path)
    service2 = CaptureService(store2, S1Service())
    report = run_startup_recovery(store2, S1Service())
    assert report.complete and report.remaining_active == 0
    print(f"4. restart     -> recovery complete, remaining_active={report.remaining_active}")

    store2._conn.execute("UPDATE artifact_content SET content = ?", (b"corrupted!!",))
    bad = service2.read_evidence(outcome.capture_id)
    assert isinstance(bad, ReadIntegrityFailure) and bad.reason == "mismatch"
    rec = store2.get_record(outcome.capture_id)
    assert rec.integrity_status is IntegrityStatus.FAILED and rec.capture_state is CaptureState.COMPLETED
    print(f"5. tamper      -> read verdict=FAILED reason={bad.reason}; record integrity=FAILED, state=COMPLETED")

    store2.close()
    print("SMOKE OK — full MVP path works end-to-end")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-smoke.db"))
