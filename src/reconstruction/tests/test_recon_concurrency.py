"""Concurrency — INV-R-1:1 under real threads (MVP-required duplicate/concurrency shape).

N threads with INDEPENDENT store connections reconstruct the same capture concurrently.
Guarantees under test:
  - at most one COMPLETED document per capture_id, whatever the interleaving;
  - every loser receives an explicit outcome and settles FAILED_INCOMPLETE;
  - distinct captures never interfere.
"""
import threading

from capture import CaptureStore, CaptureService, S1Service

from reconstruction import (
    ReconstructAlreadyExists,
    ReconstructCompleted,
    ReconstructUniquenessConflict,
    ReconstructionService,
    ReconstructionStore,
    DocumentState,
)

from helpers import ingest_parts


def test_n_concurrent_reconstructions_of_one_capture_produce_exactly_one_completed(
        make_stack, capture_db, recon_db):
    # Seed ONE completed capture before the race.
    seed = make_stack()
    try:
        cap = ingest_parts(seed.capture, [b"race-page-1;", b"race-page-2;", b"race-page-3;"])
    finally:
        seed.close()

    n = 8
    barrier = threading.Barrier(n)
    outcomes = [None] * n
    errors = []

    def worker(i):
        try:
            cstore = CaptureStore(capture_db)          # independent connection per caller
            rstore = ReconstructionStore(recon_db)
            try:
                svc = ReconstructionService(rstore, CaptureService(cstore, S1Service()), S1Service())
                barrier.wait(timeout=30)               # maximize contention
                outcomes[i] = svc.reconstruct(cap)
            finally:
                rstore.close()
                cstore.close()
        except Exception as exc:                       # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert errors == [], f"worker errors: {errors}"
    assert all(o is not None for o in outcomes)

    completed = [o for o in outcomes if isinstance(o, ReconstructCompleted)]
    already = [o for o in outcomes if isinstance(o, ReconstructAlreadyExists)]
    conflicts = [o for o in outcomes if isinstance(o, ReconstructUniquenessConflict)]
    assert len(completed) == 1, f"exactly one completion expected, got {len(completed)}"
    assert len(already) + len(conflicts) == n - 1      # every loser explicit, never silent
    if already:
        assert all(a.document_id == completed[0].document.document_id for a in already)

    check = ReconstructionStore(recon_db)              # fresh connection — storage-level truth
    try:
        winner_completed, total = check.count_for_capture(cap)
        assert winner_completed == 1                   # INV-R-1:1 held under contention
        assert total == len(conflicts) + 1             # losers retained as explicit evidence
        assert len(check.enumerate_active()) == 0      # losers already settled (P3 shape)
        done = check.find_completed_for_capture(cap)
        assert done.document_id == completed[0].document.document_id
    finally:
        check.close()


def test_concurrent_reconstructions_of_distinct_captures_all_complete(make_stack, capture_db,
                                                                       recon_db):
    seed = make_stack()
    try:
        caps = [ingest_parts(seed.capture, [f"distinct-doc-{i}-page;".encode()])
                for i in range(6)]
    finally:
        seed.close()

    n = len(caps)
    barrier = threading.Barrier(n)
    outcomes = [None] * n
    errors = []

    def worker(i):
        try:
            cstore = CaptureStore(capture_db)
            rstore = ReconstructionStore(recon_db)
            try:
                svc = ReconstructionService(rstore, CaptureService(cstore, S1Service()), S1Service())
                barrier.wait(timeout=30)
                outcomes[i] = svc.reconstruct(caps[i])
            finally:
                rstore.close()
                cstore.close()
        except Exception as exc:                       # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert errors == []
    assert all(isinstance(o, ReconstructCompleted) for o in outcomes), outcomes
    assert len({o.document.document_id for o in outcomes}) == n        # one document each
    check = ReconstructionStore(recon_db)
    try:
        assert len(check.enumerate_active()) == 0
        for cap, o in zip(caps, outcomes):
            completed, _ = check.count_for_capture(cap)
            assert completed == 1
            assert check.get_document(o.document.document_id).document_state \
                is DocumentState.COMPLETED
    finally:
        check.close()
