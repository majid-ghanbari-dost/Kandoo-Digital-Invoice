"""WP-1.3 AC-1.3.4 — deterministic consistency / orphan reporting over the capture store.

Two properties are tested together because they are the point of the module:
  (a) every structural defect an out-of-band rewrite can leave behind is REPORTED, and
  (b) reporting changes NOTHING — the report is read-only at the storage layer, and its
      bytes depend only on (database state, injected policy, injected instant).

The relaxed-schema fixture (wp13_helpers.relaxed_capture_db) is the same column layout
as the frozen store with the CHECK constraints and unique indexes removed: it emulates a
database file that was rewritten outside the store, which is exactly what the report
must detect. The frozen store itself refuses such rows (proven by the WP-1.2 suite).
"""
from __future__ import annotations

import sqlite3

import pytest

from capture import CaptureService, CaptureStore, S1Service
from capture.retention_journal import RetentionJournal
from capture.consistency import (
    DEF4_PENDING_LABEL,
    F_DUPLICATE_COMPLETED_KEY,
    F_FOREIGN_FINGERPRINT_ALGORITHM,
    F_INTEGRITY_UNVERIFIED_ON_COMPLETED,
    F_INVARIANT_INV_C1,
    F_INVARIANT_INV_C9,
    F_JOURNAL_CHAIN_BROKEN,
    F_JOURNAL_ORPHAN_DECISION,
    F_ORPHAN_CONTENT_UNREFERENCED,
    F_ORPHAN_RECORD_CONTENT_MISSING,
    F_RETENTION_POLICY_UNDECLARED,
    F_TIMESTAMP_UNPARSEABLE,
    F_UNRESOLVED_ACTIVE_LEFTOVER,
    NOT_EVALUATED,
    REPORT_KIND,
    ConsistencyReport,
    build_consistency_report,
)
from capture.consistency import ConsistencyStorageUnavailable

from wp13_helpers import (EVAL_TIME, PRIVACY_MARKING, RECEIVED_AT, ingest_completed,
                          insert_relaxed_row, policy, relaxed_capture_db)


@pytest.fixture()
def capture(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    yield tmp_path, store, CaptureService(store, S1Service())
    store.close()


def _report(tmp_path, **kwargs):
    return build_consistency_report(tmp_path / "capture.db", **kwargs)


# ---------------------------------------------------------------------------
# Healthy state + honest absence
# ---------------------------------------------------------------------------

def test_healthy_store_produces_no_findings(capture):
    tmp_path, store, service = capture
    ingest_completed(service)
    report = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    assert isinstance(report, ConsistencyReport)
    assert report.findings == []
    assert report.summary["counts"] == {"records_total": 1, "COMPLETED": 1, "ACTIVE": 0,
                                        "FAILED_INCOMPLETE": 0}


def test_empty_database_is_reported_as_such_not_as_an_error(tmp_path):
    CaptureStore(tmp_path / "capture.db").close()
    report = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    assert report.findings == []
    assert report.summary["counts"]["records_total"] == 0


def test_missing_policy_is_not_reported_as_zero_candidates(capture):
    """'0 candidates' would be a verdict; the honest answer is NOT_EVALUATED (DEF4)."""
    tmp_path, store, service = capture
    ingest_completed(service)
    report = _report(tmp_path, policy=None, evaluation_time=None)
    assert F_RETENTION_POLICY_UNDECLARED in report.codes()
    assert report.summary["retention"]["candidates"] == NOT_EVALUATED
    assert report.summary["retention"]["status"] == DEF4_PENDING_LABEL
    assert report.summary["policy_status_label"] == DEF4_PENDING_LABEL


def test_journal_not_supplied_is_declared_not_guessed(capture):
    tmp_path, store, service = capture
    ingest_completed(service)
    report = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    assert report.summary["journal"] == {"status": "NOT_SUPPLIED", "decisions": NOT_EVALUATED,
                                         "chain_ok": NOT_EVALUATED, "orphans": NOT_EVALUATED}


# ---------------------------------------------------------------------------
# Orphans and inconsistencies
# ---------------------------------------------------------------------------

def test_orphan_unreferenced_content_is_reported(capture):
    tmp_path, store, service = capture
    ingest_completed(service)
    store._conn.execute("INSERT INTO artifact_content (content_ref, content) VALUES (?, ?)",
                        ("capture-content:v1:loose-orphan", sqlite3.Binary(b"orphan")))
    report = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_ORPHAN_CONTENT_UNREFERENCED in report.codes()
    assert report.subjects(F_ORPHAN_CONTENT_UNREFERENCED) == ["capture-content:v1:loose-orphan"]


def test_record_bound_to_missing_content_is_reported(capture):
    tmp_path, store, service = capture
    cid = ingest_completed(service)
    ref = store.get_record(cid).artifact_ref
    store._conn.execute("DELETE FROM artifact_content WHERE content_ref = ?", (ref,))
    report = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_ORPHAN_RECORD_CONTENT_MISSING in report.codes()
    assert report.subjects(F_ORPHAN_RECORD_CONTENT_MISSING) == [cid]


def test_active_leftover_is_reported_and_never_settled(capture):
    tmp_path, store, service = capture
    rec = store.create_active(received_at=RECEIVED_AT)
    report = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_UNRESOLVED_ACTIVE_LEFTOVER in report.codes()
    assert report.summary["counts"]["ACTIVE"] == 1
    # the report is not a repair path: the record is still ACTIVE afterwards
    assert store.get_record(rec.capture_id).capture_state.value == "ACTIVE"


def test_completion_gate_breach_is_detected(tmp_path):
    db = relaxed_capture_db(tmp_path / "capture.db")
    conn = sqlite3.connect(str(db))
    insert_relaxed_row(conn, capture_id="broken-inv-c1", artifact_ref=None,
                       artifact_size_bytes=None, s1=None)
    conn.close()
    report = build_consistency_report(db, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_INVARIANT_INV_C1 in report.codes()
    assert report.subjects(F_INVARIANT_INV_C1) == ["broken-inv-c1"]


def test_settlement_pin_breach_is_detected(tmp_path):
    db = relaxed_capture_db(tmp_path / "capture.db")
    conn = sqlite3.connect(str(db))
    insert_relaxed_row(conn, capture_id="broken-inv-c9", capture_state="FAILED_INCOMPLETE",
                       integrity_status="FAILED", settlement_note=None, with_content=False,
                       artifact_ref=None)
    conn.close()
    report = build_consistency_report(db, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_INVARIANT_INV_C9 in report.codes()


def test_unverified_completed_is_detected(tmp_path):
    db = relaxed_capture_db(tmp_path / "capture.db")
    conn = sqlite3.connect(str(db))
    insert_relaxed_row(conn, capture_id="unverified-completed", integrity_status="UNVERIFIED")
    conn.close()
    report = build_consistency_report(db, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_INTEGRITY_UNVERIFIED_ON_COMPLETED in report.codes()


@pytest.mark.parametrize("bad", ["2026-09-01", "garbage", ""])
def test_unparseable_timestamps_are_detected(tmp_path, bad):
    db = relaxed_capture_db(tmp_path / "capture.db")
    conn = sqlite3.connect(str(db))
    insert_relaxed_row(conn, capture_id=f"bad-ts-{len(bad)}", received_at=bad)
    conn.close()
    report = build_consistency_report(db, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_TIMESTAMP_UNPARSEABLE in report.codes()


def test_foreign_fingerprint_algorithm_is_surfaced_not_resolved(tmp_path):
    """A foreign id is a NO-VERDICT class: it is reported for review, never re-hashed."""
    db = relaxed_capture_db(tmp_path / "capture.db")
    conn = sqlite3.connect(str(db))
    insert_relaxed_row(conn, capture_id="foreign-alg", s1_algorithm_id="legacy-md5-v0")
    conn.close()
    report = build_consistency_report(db, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_FOREIGN_FINGERPRINT_ALGORITHM in report.codes()
    assert report.summary["retention"]["candidates"] == 1   # still reported as a candidate


def test_duplicate_completed_key_is_detected(tmp_path):
    db = relaxed_capture_db(tmp_path / "capture.db")
    conn = sqlite3.connect(str(db))
    # the relaxed fixture materializes each row's content automatically
    insert_relaxed_row(conn, capture_id="dup-a", s1="d" * 64,
                       artifact_ref="capture-content:v1:dup-a")
    insert_relaxed_row(conn, capture_id="dup-b", s1="d" * 64,
                       artifact_ref="capture-content:v1:dup-b")
    conn.commit()
    conn.close()
    report = build_consistency_report(db, policy=policy(), evaluation_time=EVAL_TIME)
    assert F_DUPLICATE_COMPLETED_KEY in report.codes()
    assert report.subjects(F_DUPLICATE_COMPLETED_KEY) == ["dup-a"]   # lowest id, deterministic


def test_findings_are_ordered_by_code_then_subject(tmp_path):
    db = relaxed_capture_db(tmp_path / "capture.db", rows=0)
    conn = sqlite3.connect(str(db))
    for i in range(4):
        insert_relaxed_row(conn, capture_id=f"ts-{i}", received_at="nope",
                           artifact_ref=f"capture-content:v1:ts-{i}")
    insert_relaxed_row(conn, capture_id="z-alive")
    conn.execute("INSERT INTO artifact_content (content_ref, content) VALUES ('loose', x'41')")
    conn.commit()
    conn.close()
    report = build_consistency_report(db, policy=policy(), evaluation_time=EVAL_TIME)
    keys = [(f.code, f.subject) for f in report.findings]
    assert keys == sorted(keys)
    assert len(keys) > 1


# ---------------------------------------------------------------------------
# Determinism + read-only guarantees
# ---------------------------------------------------------------------------

def test_two_independent_reports_are_byte_identical(capture):
    tmp_path, store, service = capture
    for i in range(3):
        ingest_completed(service, content=f"invoice.number=DET-{i}\n".encode())
    first = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    second = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    assert first.canonical_text == second.canonical_text
    assert first.report_fingerprint == second.report_fingerprint
    assert first.report_algorithm_id == "sha256-v1"


def test_a_fresh_process_view_of_the_same_state_reports_identically(capture):
    """Determinism across a restart: close, reopen, re-report."""
    tmp_path, store, service = capture
    ingest_completed(service)
    first = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    store.close()
    reopened = CaptureStore(tmp_path / "capture.db")
    try:
        second = build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                          evaluation_time=EVAL_TIME)
    finally:
        reopened.close()
    assert first.canonical_text == second.canonical_text


def test_injected_time_changes_the_answer_deterministically(capture):
    tmp_path, store, service = capture
    cid = ingest_completed(service)
    cutoff = 10_000_000        # ~115 days — between the two injected instants
    young = _report(tmp_path, policy=policy(cutoff_seconds=cutoff),
                    evaluation_time=EVAL_TIME)
    old = _report(tmp_path, policy=policy(cutoff_seconds=cutoff),
                  evaluation_time="2030-01-01T00:00:00+00:00")
    assert young.summary["retention"]["candidates"] == 0
    assert old.summary["retention"]["candidates"] == 1
    assert old.summary["retention"]["candidate_capture_ids"] == [cid]
    assert young.canonical_text != old.canonical_text


def test_report_never_mutates_the_capture_or_journal_storage(capture, tmp_path):
    _, store, service = capture
    cid = ingest_completed(service)
    journal = RetentionJournal(tmp_path / "journal.db")
    _append_decision(journal, cid)
    capture_before = (tmp_path / "capture.db").read_bytes()
    journal_before = (tmp_path / "journal.db").read_bytes()
    for _ in range(3):
        build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                 evaluation_time=EVAL_TIME,
                                 journal_db_path=tmp_path / "journal.db")
    assert (tmp_path / "capture.db").read_bytes() == capture_before
    assert (tmp_path / "journal.db").read_bytes() == journal_before
    journal.close()


def test_report_carries_no_paths_no_clock_and_no_content(capture, tmp_path):
    _, store, service = capture
    ingest_completed(service, content=b"INVOICE-PLAINTEXT-PAYLOAD")
    report = _report(tmp_path, policy=policy(), evaluation_time=EVAL_TIME)
    text = report.canonical_text
    assert "capture.db" not in text and str(tmp_path) not in text
    assert "INVOICE-PLAINTEXT-PAYLOAD" not in text
    assert report.summary["kind"] == REPORT_KIND
    assert "report_scope_note" in report.summary


def test_report_reads_are_not_a_content_channel(tmp_path):
    """Even with content present, no finding detail ever quotes artifact bytes."""
    db = relaxed_capture_db(tmp_path / "capture.db", rows=2)
    report = build_consistency_report(db, policy=policy(), evaluation_time=EVAL_TIME)
    assert all("xxx" not in f.detail for f in report.findings)


# ---------------------------------------------------------------------------
# Journal cross-checks
# ---------------------------------------------------------------------------

def _append_decision(journal, capture_id, *, policy_id="P1"):
    from capture.retention import RETENTION_OUTCOME_ELIGIBLE
    return journal.append_decision(
        capture_id=capture_id, policy_id=policy_id, outcome=RETENTION_OUTCOME_ELIGIBLE,
        evaluation_time=EVAL_TIME,
        payload={"age_seconds": 3_456_000, "cutoff_seconds": 1_000,
                 "privacy_marking": PRIVACY_MARKING})


def test_orphan_journal_decision_is_reported(capture, tmp_path):
    _, store, service = capture
    real_cid = ingest_completed(service)
    journal = RetentionJournal(tmp_path / "journal.db")
    _append_decision(journal, real_cid)
    _append_decision(journal, "capture-id-that-does-not-exist", policy_id="P-ORPHAN")
    report = build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                      evaluation_time=EVAL_TIME,
                                      journal_db_path=tmp_path / "journal.db")
    assert F_JOURNAL_ORPHAN_DECISION in report.codes()
    assert report.summary["journal"]["orphans"] == 1
    journal.close()


def test_broken_journal_is_reported_as_inconsistent(capture, tmp_path):
    _, store, service = capture
    cid = ingest_completed(service)
    journal = RetentionJournal(tmp_path / "journal.db")
    _append_decision(journal, cid)
    _append_decision(journal, cid, policy_id="P2")
    journal._conn.execute("DELETE FROM retention_decisions WHERE seq = 2")
    report = build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                      evaluation_time=EVAL_TIME,
                                      journal_db_path=tmp_path / "journal.db")
    assert F_JOURNAL_CHAIN_BROKEN in report.codes()
    assert report.summary["journal"]["status"] == "CHAIN_SUSPECT"
    assert report.summary["journal"]["chain_ok"] is False
    journal.close()


# ---------------------------------------------------------------------------
# Failure surface
# ---------------------------------------------------------------------------

def test_unreachable_storage_fails_explicitly(tmp_path):
    with pytest.raises(ConsistencyStorageUnavailable):
        build_consistency_report(tmp_path / "does-not-exist.db", policy=policy(),
                                  evaluation_time=EVAL_TIME)


def test_foreign_schema_fails_explicitly(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "capture.db"))
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()
    with pytest.raises(ConsistencyStorageUnavailable):
        build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                 evaluation_time=EVAL_TIME)
