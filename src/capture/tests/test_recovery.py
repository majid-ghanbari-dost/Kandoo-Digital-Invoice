"""Recovery tests — Contract §11 / Store §4–§5 (AC-T112-3/4/9; INV-C6/C9; AC-1.1.7 support).

Simulates the crash windows W2–W4 by building residues step-by-step (a real kill -9 is
process-level and covered structurally: every residue below is exactly what a crash at
that step leaves durable).
"""
from capture import (
    NOTE_CONTENT_MISSING,
    NOTE_S1_MISSING,
    NOTE_UNIQUENESS_CONFLICT,
    NOTE_VERIFY_FAILED,
    CaptureState,
    IntegrityStatus,
    S1Service,
    run_startup_recovery,
)


def _residue_after_create(store):
    rec = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    return rec.capture_id


def _residue_after_persist(store, content=b"crash-window-content"):
    cid = _residue_after_create(store)
    store.persist_content(cid, content)
    return cid


def _residue_after_attach(store, content=b"crash-window-content"):
    cid = _residue_after_persist(store, content)
    v = S1Service().compute(content)
    store.attach_s1(cid, v.s1, v.s1_algorithm_id)
    return cid


def test_w2_residue_settles_content_missing(store):
    """W2: crash after record creation, before/during content persist (Store §4)."""
    cid = _residue_after_create(store)
    report = run_startup_recovery(store, S1Service())
    assert report.complete is True                 # INV-C6: zero ACTIVE after completed recovery
    assert report.remaining_active == 0
    assert (cid, NOTE_CONTENT_MISSING) in report.settled_failed
    rec = store.get_record(cid)
    assert rec.capture_state is CaptureState.FAILED_INCOMPLETE
    assert rec.integrity_status is IntegrityStatus.FAILED       # v1.1-C2 pin
    assert rec.settlement_note == NOTE_CONTENT_MISSING          # INV-C9


def test_w3_residue_settles_s1_missing(store):
    """W3: content durable, crash before S1 attach — identity not provable (§7 r1)."""
    cid = _residue_after_persist(store)
    report = run_startup_recovery(store, S1Service())
    assert report.complete is True
    assert (cid, NOTE_S1_MISSING) in report.settled_failed
    rec = store.get_record(cid)
    assert rec.capture_state is CaptureState.FAILED_INCOMPLETE
    assert rec.settlement_note == NOTE_S1_MISSING


def test_w4_residue_completes_when_verification_valid(store):
    """W4: S1 attached, no verdict yet — recovery verifies and completes through UAC."""
    cid = _residue_after_attach(store, b"recoverable-content")
    report = run_startup_recovery(store, S1Service())
    assert report.complete is True
    assert report.settled_completed == [cid]
    rec = store.get_record(cid)
    assert rec.capture_state is CaptureState.COMPLETED
    assert rec.integrity_status is IntegrityStatus.VALID
    assert rec.integrity_verified_at is not None


def test_w4_residue_with_corrupted_content_settles_verify_failed(store):
    """W4 variant: content corrupted out-of-store before restart → verify FAILED settlement."""
    cid = _residue_after_attach(store, b"honest-content")
    store._conn.execute("UPDATE artifact_content SET content = ?", (b"dishonest-content",))
    report = run_startup_recovery(store, S1Service())
    assert report.complete is True
    assert (cid, NOTE_VERIFY_FAILED) in report.settled_failed
    rec = store.get_record(cid)
    assert rec.capture_state is CaptureState.FAILED_INCOMPLETE
    assert rec.integrity_status is IntegrityStatus.FAILED


def test_recovery_uniqueness_precondition_mints_only_one_completed(store):
    """Store §5 step (b) precondition: two identical ACTIVE leftovers → exactly one
    completes through UAC; the other settles with the uniqueness-conflict note."""
    content = b"twin-leftovers"
    cid_a = _residue_after_attach(store, content)
    cid_b = _residue_after_attach(store, content)
    assert cid_a != cid_b
    report = run_startup_recovery(store, S1Service())
    assert report.complete is True
    assert len(report.settled_completed) == 1
    assert (report.settled_completed[0] in {cid_a, cid_b})
    loser = cid_b if report.settled_completed[0] == cid_a else cid_a
    assert (loser, NOTE_UNIQUENESS_CONFLICT) in report.settled_failed
    rec_loser = store.get_record(loser)
    assert rec_loser.capture_state is CaptureState.FAILED_INCOMPLETE
    assert rec_loser.settlement_note == NOTE_UNIQUENESS_CONFLICT
    winner = store.get_record(report.settled_completed[0])
    assert winner.capture_state is CaptureState.COMPLETED
    completed, total = store.count_by_key(winner.s1, winner.s1_algorithm_id)
    assert completed == 1 and total == 2            # INV-C3 holds through recovery


def test_recovery_is_idempotent(store):
    """§11 r4 / AC-T112-4: repeated runs produce zero state change."""
    cid = _residue_after_attach(store, b"idempotent-content")
    first = run_startup_recovery(store, S1Service())
    assert first.complete is True and first.settled_completed == [cid]
    snapshot = store.get_record(cid)
    second = run_startup_recovery(store, S1Service())
    assert second.complete is True
    assert second.settled_completed == [] and second.settled_failed == []
    assert second.remaining_active == 0
    after = store.get_record(cid)
    assert after == snapshot                        # nothing changed


def test_restart_recovery_mixed_residues_all_settled(store):
    """A restart with mixed leftovers settles every record explicitly (AC-1.1.7)."""
    w2 = _residue_after_create(store)
    w3 = _residue_after_persist(store, b"w3-content")
    w4 = _residue_after_attach(store, b"w4-content")
    done = store.create_active(received_at="2026-10-01T00:00:09+00:00")  # a COMPLETED record stays untouched
    store.persist_content(done.capture_id, b"already-complete")
    v = S1Service().compute(b"already-complete")
    store.attach_s1(done.capture_id, v.s1, v.s1_algorithm_id)
    store.record_verification(done.capture_id, "VALID", "2026-10-01T00:00:10+00:00")
    store.complete_record(done.capture_id)

    report = run_startup_recovery(store, S1Service())
    assert report.complete is True
    assert report.remaining_active == 0
    assert store.get_record(w2).capture_state is CaptureState.FAILED_INCOMPLETE
    assert store.get_record(w3).capture_state is CaptureState.FAILED_INCOMPLETE
    assert store.get_record(w4).capture_state is CaptureState.COMPLETED
    assert store.get_record(done.capture_id).capture_state is CaptureState.COMPLETED  # untouched
