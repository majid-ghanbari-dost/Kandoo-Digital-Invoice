"""T-1.1.2 store tests — lifecycle, mutability enforcement, UAC, settlement, lookup scope."""
import dataclasses
import sqlite3

import pytest

from capture import (
    NOTE_CONTENT_MISSING,
    NOTE_CONTENT_PERSIST_FAILED,
    NOTE_VERIFY_FAILED,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
    CaptureRecord,
    CaptureState,
    CompletionGateUnmet,
    ContentMissing,
    ExplicitPersistenceFailure,
    IllegalFieldWrite,
    IllegalTransition,
    IntegrityStatus,
    RecordNotFound,
    StorageUnavailable,
    CaptureStore,
    S1Service,
    SOURCE_LABEL_UNDECLARED,
    FORMAT_HINT_UNKNOWN,
)


@pytest.fixture()
def s1():
    return S1Service()


def _ingest_record(store, s1, content=b"durable-bytes", complete=True):
    """Drive a record to (optionally) COMPLETED through the store primitives only."""
    rec = store.create_active(received_at="2026-10-01T00:00:00+00:00", source_label="test-channel")
    store.persist_content(rec.capture_id, content)
    v = s1.compute(content)
    store.attach_s1(rec.capture_id, v.s1, v.s1_algorithm_id)
    if complete:
        store.record_verification(rec.capture_id, "VALID", "2026-10-01T00:00:01+00:00")
        outcome = store.complete_record(rec.capture_id)
        assert outcome == UAC_GRANTED
    return store.get_record(rec.capture_id)


def test_record_has_exactly_14_contract_fields():
    """AC-T112-8: the record structure is exactly the 14 contract fields (F-01..F-13, F-15);
    F-14 is retired (v1.1-C1) and no downstream field exists (INV-C7 / I-5)."""
    names = [f.name for f in dataclasses.fields(CaptureRecord)]
    assert names == [
        "capture_id", "s1", "s1_algorithm_id", "artifact_ref", "created_at",
        "capture_state", "integrity_status", "integrity_verified_at", "received_at",
        "source_label", "artifact_format_hint", "capture_entry_metadata",
        "artifact_size_bytes", "settlement_note",
    ]
    assert len(names) == 14
    assert "lineage_reserved" not in names


def test_create_active_defaults_provable_data(store):
    rec = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    assert rec.capture_state is CaptureState.ACTIVE
    assert rec.integrity_status is IntegrityStatus.UNVERIFIED
    assert rec.integrity_verified_at is None
    assert rec.source_label == SOURCE_LABEL_UNDECLARED      # §14 r6 — no guessing
    assert rec.artifact_format_hint == FORMAT_HINT_UNKNOWN  # §14 r7 — no guessing
    assert rec.capture_entry_metadata == "{}"
    assert rec.s1 is None and rec.artifact_ref is None and rec.settlement_note is None
    assert rec.created_at and rec.received_at               # F-05/F-09 present


def test_persist_content_finalizes_f13_and_is_one_time(store):
    rec = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    store.persist_content(rec.capture_id, b"0123456789")
    after = store.get_record(rec.capture_id)
    assert after.artifact_ref and after.artifact_ref.startswith("capture-content:v1:")
    assert after.artifact_size_bytes == 10                  # F-13 finalized (Store Step 1)
    with pytest.raises(IllegalFieldWrite):                  # immutable one-time binding (I-2/I-3)
        store.persist_content(rec.capture_id, b"other-bytes")


def test_content_read_is_byte_exact(store):
    rec = _ingest_record(store, S1Service(), content=b"\x00\x01\x02PDF-fake\xff", complete=False)
    assert store.get_content(rec.artifact_ref) == b"\x00\x01\x02PDF-fake\xff"


def test_content_missing_surfaces(store):
    # a record whose content was never persisted carries no artifact_ref (W2 residue)
    bare = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    with pytest.raises(ContentMissing):
        store.get_content(bare.artifact_ref)                    # None
    with pytest.raises(ContentMissing):
        store.get_content(None)
    with pytest.raises(ContentMissing):
        store.get_content("capture-content:v1:does-not-exist")
    # content persisted → byte-exact read succeeds
    filled = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    store.persist_content(filled.capture_id, b"present")
    assert store.get_content(store.get_record(filled.capture_id).artifact_ref) == b"present"


def test_attach_s1_is_one_time_and_active_only(store, s1):
    rec = _ingest_record(store, s1, complete=False)
    v = s1.compute(b"anything")
    with pytest.raises(IllegalFieldWrite):                  # immutable after attach (F-02/F-03)
        store.attach_s1(rec.capture_id, v.s1, v.s1_algorithm_id)
    with pytest.raises(IllegalFieldWrite):
        store.attach_s1(rec.capture_id, "", "")


def test_completion_gate_fail_closed(store, s1):
    """§7 r1 / R-2: completion without durable content, without S1, or without VALID → refused."""
    # no content, no s1, no verdict
    r1 = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    with pytest.raises(CompletionGateUnmet):
        store.complete_record(r1.capture_id)
    # content durable, but no s1
    store.persist_content(r1.capture_id, b"bytes")
    with pytest.raises(CompletionGateUnmet):
        store.complete_record(r1.capture_id)
    # s1 attached, but no VALID verdict
    v = s1.compute(b"bytes")
    store.attach_s1(r1.capture_id, v.s1, v.s1_algorithm_id)
    with pytest.raises(CompletionGateUnmet):
        store.complete_record(r1.capture_id)
    assert store.get_record(r1.capture_id).capture_state is CaptureState.ACTIVE


def test_complete_grants_and_record_is_completed(store, s1):
    rec = _ingest_record(store, s1, content=b"complete-me")
    assert rec.capture_state is CaptureState.COMPLETED
    assert rec.integrity_status is IntegrityStatus.VALID
    assert rec.integrity_verified_at is not None
    assert rec.settlement_note is None                      # F-15 meaningless on COMPLETED


def test_record_verification_restricted_writer(store, s1):
    """§6 class 3: only F-07/F-08 change; UNVERIFIED is not a writable verdict;
    FAILED_INCOMPLETE integrity fields are pinned (§10 r5)."""
    rec = _ingest_record(store, s1, complete=False)
    with pytest.raises(IllegalFieldWrite):
        store.record_verification(rec.capture_id, "UNVERIFIED", "2026-10-01T00:00:02+00:00")
    store.record_verification(rec.capture_id, "FAILED", "2026-10-01T00:00:02+00:00")
    assert store.get_record(rec.capture_id).integrity_status is IntegrityStatus.FAILED
    # settlement path pins FAILED; later verification writes are rejected
    store.settle_failed(rec.capture_id, NOTE_VERIFY_FAILED)
    settled = store.get_record(rec.capture_id)
    assert settled.capture_state is CaptureState.FAILED_INCOMPLETE
    assert settled.integrity_status is IntegrityStatus.FAILED
    assert settled.settlement_note == NOTE_VERIFY_FAILED
    with pytest.raises(IllegalTransition):
        store.record_verification(rec.capture_id, "VALID", "2026-10-01T00:00:03+00:00")


def test_settlement_only_from_active_and_terminal_states_never_change(store, s1):
    rec = _ingest_record(store, s1, complete=True)          # COMPLETED
    with pytest.raises(IllegalTransition):                  # §7 r3/r5: COMPLETED never re-opened
        store.settle_failed(rec.capture_id, "attempt")
    with pytest.raises(IllegalTransition):                  # and never re-completed
        store.complete_record(rec.capture_id)
    active = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    store.settle_failed(active.capture_id, "content missing/unreadable")
    with pytest.raises(IllegalTransition):                  # FAILED_INCOMPLETE is terminal
        store.settle_failed(active.capture_id, "again")


def test_settlement_note_mandatory(store):
    rec = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    with pytest.raises(IllegalFieldWrite):                  # INV-C9
        store.settle_failed(rec.capture_id, "")


def test_uac_conflict_loser_is_explicit_never_completed(store, s1):
    """INV-C3 / INV-S10: a second completion with the same (s1, s1_algorithm_id) loses
    with an explicit uniqueness-conflict outcome and never becomes COMPLETED."""
    content = b"duplicate-content"
    first = _ingest_record(store, s1, content=content, complete=False)
    store.record_verification(first.capture_id, "VALID", "2026-10-01T00:00:01+00:00")
    assert store.complete_record(first.capture_id) == UAC_GRANTED

    second = store.create_active(received_at="2026-10-01T00:00:05+00:00")
    store.persist_content(second.capture_id, content)
    v = s1.compute(content)
    store.attach_s1(second.capture_id, v.s1, v.s1_algorithm_id)
    store.record_verification(second.capture_id, "VALID", "2026-10-01T00:00:06+00:00")
    assert store.complete_record(second.capture_id) == UAC_UNIQUENESS_CONFLICT
    assert store.get_record(second.capture_id).capture_state is CaptureState.ACTIVE  # untouched; caller settles

    completed, total = store.count_by_key(v.s1, v.s1_algorithm_id)
    assert completed == 1                                   # INV-C3
    assert total == 2                                       # both records retained


def test_unique_index_is_storage_level_backstop(store, s1):
    """Even a direct SQL write path cannot mint a second COMPLETED for one key (INV-S10)."""
    content = b"backstop-content"
    _ingest_record(store, s1, content=content, complete=True)
    v = s1.compute(content)
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            """INSERT INTO capture_records (
                   capture_id, s1, s1_algorithm_id, artifact_ref, created_at, capture_state,
                   integrity_status, integrity_verified_at, received_at, source_label,
                   artifact_format_hint, capture_entry_metadata, artifact_size_bytes, settlement_note)
               VALUES ('forced-id', ?, ?, 'capture-content:v1:x', '2026', 'COMPLETED',
                       'VALID', '2026', '2026', 'x', 'UNKNOWN', '{}', 1, NULL)""",
            (v.s1, v.s1_algorithm_id),
        )


def test_find_completed_is_completed_restricted_and_deterministic(store, s1):
    """§9 step 2 / S1 INV-F4: ACTIVE and FAILED_INCOMPLETE never match; repeated queries
    return identical results (AC-T113-2)."""
    v = s1.compute(b"scoped-content")
    hit = _ingest_record(store, s1, content=b"scoped-content", complete=False)
    store.record_verification(hit.capture_id, "VALID", "2026-10-01T00:00:01+00:00")
    store.complete_record(hit.capture_id)

    active = store.create_active(received_at="2026-10-01T00:00:02+00:00")
    store.persist_content(active.capture_id, b"scoped-content")
    store.attach_s1(active.capture_id, v.s1, v.s1_algorithm_id)
    failed = store.create_active(received_at="2026-10-01T00:00:03+00:00")
    store.settle_failed(failed.capture_id, "content missing/unreadable")

    first = store.find_completed(v.s1, v.s1_algorithm_id)
    second = store.find_completed(v.s1, v.s1_algorithm_id)
    assert [r.capture_id for r in first] == [hit.capture_id]
    assert first == second                                  # deterministic
    assert all(r.capture_state is CaptureState.COMPLETED for r in first)
    assert active.capture_id not in [r.capture_id for r in first]
    assert failed.capture_id not in [r.capture_id for r in first]


def test_enumerate_active_is_complete(store, s1):
    _ingest_record(store, s1, content=b"done", complete=True)
    a = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    b = store.create_active(received_at="2026-10-01T00:00:01+00:00")
    leftovers = store.enumerate_active()
    assert {r.capture_id for r in leftovers} == {a.capture_id, b.capture_id}


def test_record_not_found_surfaces(store):
    with pytest.raises(RecordNotFound):
        store.get_record("missing-id")


def test_d1_definitive_persist_error_settles_synchronously(store):
    """AC-T112-9 / Store §6.1 D-1: a definitive persist error returned to the live store
    settles the record synchronously to FAILED_INCOMPLETE + note + FAILED — never ACTIVE."""
    rec = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    # fault injection: the content table becomes unwritable (definitive storage failure)
    store._conn.execute("DROP TABLE artifact_content")
    with pytest.raises(ExplicitPersistenceFailure) as excinfo:
        store.persist_content(rec.capture_id, b"bytes")
    assert excinfo.value.settlement_note == NOTE_CONTENT_PERSIST_FAILED
    settled = store.get_record(rec.capture_id)
    assert settled.capture_state is CaptureState.FAILED_INCOMPLETE   # synchronous (same attempt)
    assert settled.integrity_status is IntegrityStatus.FAILED        # v1.1-C2 pin
    assert settled.settlement_note == NOTE_CONTENT_PERSIST_FAILED    # INV-C9


def test_d2_settlement_write_failure_leaves_recoverable_residue(tmp_path):
    """AC-T112-9 / Store §6.1 D-2: when no verdict is durably recordable, the record
    remains ACTIVE solely as recoverable residue; startup recovery then settles it."""
    db = tmp_path / "d2.db"
    store = CaptureStore(db)
    rec = store.create_active(received_at="2026-10-01T00:00:00+00:00")
    store.close()                                    # storage wholly unavailable
    with pytest.raises(StorageUnavailable):
        store.persist_content(rec.capture_id, b"bytes")
    # storage returns: the residue must still be ACTIVE and settleable
    reopened = CaptureStore(db)
    try:
        residue = reopened.get_record(rec.capture_id)
        assert residue.capture_state is CaptureState.ACTIVE       # D-2 residue (never FAILED-fabricated)
        from capture import run_startup_recovery, S1Service
        report = run_startup_recovery(reopened, S1Service())
        assert report.complete is True                            # INV-C6
        assert (rec.capture_id, NOTE_CONTENT_MISSING) in report.settled_failed
        assert reopened.get_record(rec.capture_id).capture_state is CaptureState.FAILED_INCOMPLETE
    finally:
        reopened.close()
