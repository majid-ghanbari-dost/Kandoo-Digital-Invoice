"""Concurrency tests — Store §9.1 UAC under real threads (AC-T112-10 / AC-T113-6; INV-C3).

N threads with INDEPENDENT store connections ingest identical content concurrently.
Guarantees under test:
  P2 — at most one COMPLETED record per (s1, s1_algorithm_id), whatever the interleaving;
  P3 — every loser receives an explicit outcome and settles FAILED_INCOMPLETE;
  P6 — the lookup stays deterministic afterwards.
"""
import threading

from capture import (
    CaptureService,
    CaptureStore,
    IngestCompleted,
    IngestDuplicateAtCapture,
    IngestUniquenessConflict,
    S1Service,
)


def test_n_concurrent_identical_ingests_produce_exactly_one_completed(db_path):
    n = 8
    content = b"concurrent-identical-content"
    barrier = threading.Barrier(n)
    outcomes = [None] * n
    errors = []

    def worker(i):
        try:
            store = CaptureStore(db_path)          # independent connection per caller
            try:
                service = CaptureService(store, S1Service())
                barrier.wait(timeout=30)           # maximize contention
                outcomes[i] = service.ingest(content, source_label=f"thread-{i}")
            finally:
                store.close()
        except Exception as exc:                   # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert errors == [], f"worker errors: {errors}"
    assert all(o is not None for o in outcomes)

    # every attempt received an explicit, typed outcome — no silent result exists
    completed = [o for o in outcomes if isinstance(o, IngestCompleted)]
    duplicates = [o for o in outcomes if isinstance(o, IngestDuplicateAtCapture)]
    conflicts = [o for o in outcomes if isinstance(o, IngestUniquenessConflict)]

    assert len(completed) == 1, f"exactly one completion expected, got {len(completed)}"
    assert len(duplicates) + len(conflicts) == n - 1
    # duplicates must reference the single winner; conflicts must be settled losers
    if duplicates:
        assert all(d.existing_capture_id == completed[0].capture_id for d in duplicates)

    # P2/INV-C3: at most one COMPLETED record for the key — via a fresh connection
    check = CaptureStore(db_path)
    try:
        rec = check.get_record(completed[0].capture_id)
        completed_count, total = check.count_by_key(rec.s1, rec.s1_algorithm_id)
        assert completed_count == 1
        assert total == len(conflicts) + 1         # losers retained as explicit evidence
        assert len(check.enumerate_active()) == 0  # losers already settled (P3)
        # P6: lookup is deterministic afterwards
        hits = check.find_completed(rec.s1, rec.s1_algorithm_id)
        assert [r.capture_id for r in hits] == [completed[0].capture_id]
    finally:
        check.close()


def test_concurrent_distinct_contents_all_complete(db_path):
    """Different contents → different S1 keys → all complete (no false dedup)."""
    n = 6
    barrier = threading.Barrier(n)
    outcomes = [None] * n
    errors = []

    def worker(i):
        try:
            store = CaptureStore(db_path)
            try:
                service = CaptureService(store, S1Service())
                barrier.wait(timeout=30)
                outcomes[i] = service.ingest(f"distinct-content-{i}".encode())
            finally:
                store.close()
        except Exception as exc:                   # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert errors == []
    assert all(isinstance(o, IngestCompleted) for o in outcomes)
    assert len({o.capture_id for o in outcomes}) == n
