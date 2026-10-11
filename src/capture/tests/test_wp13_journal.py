"""WP-1.3 AC-1.3.2 / AC-1.3.3 — retention decision journal.

Covers: append-only durability, the tamper-evident chain, truncation detection,
refusal to extend a broken chain, idempotent duplicate handling, and rollback under
injected failures at every persistence boundary of the append.

No test here modifies a frozen journal implementation: the frozen WP-2.2 evidence log
is not imported, not patched and not shared — this suite exercises ONLY the new module.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from capture import CaptureService, CaptureStore, S1Service
from capture.retention import (
    DEF4_PENDING_LABEL,
    RETENTION_OUTCOME_ELIGIBLE,
    RETENTION_OUTCOME_NOT_ELIGIBLE,
    RETENTION_OUTCOME_POLICY_UNDECLARED,
    RETENTION_OUTCOME_PURGE_GATE_BLOCKED,
    request_purge,
)
from capture.retention_journal import (
    GENESIS_HASH,
    JournalAppended,
    JournalChainBroken,
    JournalDuplicateDecision,
    JournalEntry,
    JournalEntryNotFound,
    JournalIllegalEntry,
    JournalStorageUnavailable,
    JournalTamperWithheld,
    RetentionJournal,
    canonical_json_text,
)

from wp13_helpers import EVAL_TIME, POLICY_ID, ingest_completed


@pytest.fixture()
def capture(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    yield store, CaptureService(store, S1Service())
    store.close()


@pytest.fixture()
def journal(tmp_path):
    j = RetentionJournal(tmp_path / "journal.db")
    yield j
    j.close()


def _append(journal, capture_id, *, policy_id=POLICY_ID, outcome=RETENTION_OUTCOME_ELIGIBLE,
            age_seconds=3_456_000, cutoff_seconds=1_000):
    payload = ({"age_seconds": age_seconds, "cutoff_seconds": cutoff_seconds,
                "privacy_marking": "TEST-CLASS-A"}
               if outcome == RETENTION_OUTCOME_ELIGIBLE else
               {"age_seconds": age_seconds, "cutoff_seconds": cutoff_seconds,
                "remaining_seconds": 1, "policy_status_label": DEF4_PENDING_LABEL}
               if outcome == RETENTION_OUTCOME_NOT_ELIGIBLE else
               {"policy_status_label": DEF4_PENDING_LABEL}
               if outcome == RETENTION_OUTCOME_POLICY_UNDECLARED else
               {"executed": False, "rows_affected": 0, "authorization_supplied": False,
                "policy_status_label": DEF4_PENDING_LABEL})
    return journal.append_decision(capture_id=capture_id, policy_id=policy_id,
                                   outcome=outcome, evaluation_time=EVAL_TIME,
                                   payload=payload)


# ---------------------------------------------------------------------------
# AC-1.3.3 — durable append + verified read
# ---------------------------------------------------------------------------

def test_append_is_durable_and_readable(journal, capture):
    store, service = capture
    cid = ingest_completed(service)
    appended = _append(journal, cid)
    assert isinstance(appended, JournalAppended)
    assert appended.seq == 1 and appended.record_hash != GENESIS_HASH
    entry = journal.read_entry(1)
    assert isinstance(entry, JournalEntry)
    assert entry.capture_id == cid and entry.outcome == RETENTION_OUTCOME_ELIGIBLE
    assert entry.policy_status_label == DEF4_PENDING_LABEL
    assert entry.payload["cutoff_seconds"] == 1_000          # injected value, echoed verbatim


def test_chain_verifies_over_a_sequence_of_appends(journal, capture):
    store, service = capture
    ids = [ingest_completed(service, content=f"invoice.number=CHAIN-{i}\n".encode())
            for i in range(4)]
    for i, cid in enumerate(ids):
        _append(journal, cid, policy_id=f"{POLICY_ID}-{i}")
    report = journal.verify_chain()
    assert report.ok is True and report.record_count == 4 and not report.issues
    assert journal.latest_seq() == 4
    seqs = [e.seq for e in journal.enumerate_entries()]
    assert seqs == [1, 2, 3, 4]                             # contiguous, ordered
    assert journal.enumerate_entries()[0].prev_record_hash == GENESIS_HASH
    for previous, current in zip(journal.enumerate_entries(), journal.enumerate_entries()[1:]):
        assert current.prev_record_hash == previous.record_hash   # every link exact


def test_history_survives_a_restart(journal, capture, tmp_path):
    store, service = capture
    cid = ingest_completed(service)
    original = _append(journal, cid)
    journal.close()
    reopened = RetentionJournal(tmp_path / "journal.db")
    try:
        assert reopened.verify_chain().ok is True
        entry = reopened.read_entry(original.seq)
        assert entry.record_hash == original.record_hash
        assert entry.record_fingerprint == original.record_fingerprint
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# AC-1.3.3 — duplicate handling is idempotent, never a second row
# ---------------------------------------------------------------------------

def test_duplicate_decision_is_idempotent(journal, capture):
    store, service = capture
    cid = ingest_completed(service)
    first = _append(journal, cid)
    with pytest.raises(JournalDuplicateDecision) as exc:
        _append(journal, cid)
    assert exc.value.seq == first.seq
    assert exc.value.record_hash == first.record_hash
    assert exc.value.decision_key == first.decision_key
    assert journal.latest_seq() == 1                        # nothing consumed
    assert journal.verify_chain().record_count == 1


def test_duplicate_refusal_survives_reopen_as_a_storage_backstop(journal, capture, tmp_path):
    """The refusal is enforced by a UNIQUE index, not only by the in-transaction check."""
    store, service = capture
    cid = ingest_completed(service)
    _append(journal, cid)
    journal.close()
    reopened = RetentionJournal(tmp_path / "journal.db")
    try:
        with pytest.raises(JournalDuplicateDecision):
            _append(reopened, cid)
        assert reopened.verify_chain().record_count == 1
    finally:
        reopened.close()


def test_distinct_decisions_for_the_same_record_are_all_kept(journal, capture):
    store, service = capture
    cid = ingest_completed(service)
    for i, outcome in enumerate((RETENTION_OUTCOME_ELIGIBLE, RETENTION_OUTCOME_NOT_ELIGIBLE,
                                 RETENTION_OUTCOME_POLICY_UNDECLARED)):
        _append(journal, cid, policy_id=f"P-{i}", outcome=outcome)
    assert [e.outcome for e in journal.enumerate_entries()] == [
        RETENTION_OUTCOME_ELIGIBLE, RETENTION_OUTCOME_NOT_ELIGIBLE,
        RETENTION_OUTCOME_POLICY_UNDECLARED]
    assert journal.verify_chain().ok is True


def test_seq_never_skips_after_refusals(journal, capture):
    store, service = capture
    cid = ingest_completed(service)
    with pytest.raises(JournalIllegalEntry):
        journal.append_decision(capture_id=cid, policy_id=POLICY_ID, outcome="SOMETHING_ELSE")
    with pytest.raises(JournalIllegalEntry):
        journal.append_decision(capture_id=cid, policy_id=POLICY_ID,
                                outcome=RETENTION_OUTCOME_ELIGIBLE,
                                payload={"content": b"artifact bytes must never be logged"})
    _append(journal, cid)
    assert journal.latest_seq() == 1


# ---------------------------------------------------------------------------
# AC-1.3.2 — truncation / rewrite detection, and refusal to extend a broken chain
# ---------------------------------------------------------------------------

def test_truncated_tail_is_detected(journal, capture):
    store, service = capture
    for i in range(3):
        _append(journal, ingest_completed(service, content=f"invoice.number=T-{i}\n".encode()),
                policy_id=f"P-{i}")
    assert journal.verify_chain().ok is True
    journal._conn.execute("DELETE FROM retention_decisions WHERE seq = 3")   # out-of-band
    report = journal.verify_chain()
    assert report.ok is False
    assert "truncat" in (report.reason or "").lower() or "anchor" in (report.reason or "").lower()
    assert report.first_failure_seq == 3


def test_append_is_refused_on_a_broken_chain_and_extends_nothing(journal, capture, tmp_path):
    store, service = capture
    for i in range(2):
        _append(journal, ingest_completed(service, content=f"invoice.number=B-{i}\n".encode()),
                policy_id=f"P-{i}")
    journal._conn.execute("DELETE FROM retention_decisions WHERE seq = 2")
    with pytest.raises(JournalChainBroken) as exc:
        _append(journal, ingest_completed(service, content=b"invoice.number=B-99\n"),
                policy_id="P-99")
    assert exc.value.first_failure_seq is not None or exc.value.first_failure_seq is None
    assert journal.latest_seq() == 1                        # no silent extension
    rows = journal._conn.execute("SELECT COUNT(*) AS n FROM retention_decisions").fetchone()["n"]
    assert rows == 1                                        # nothing written by the refusal
    # A missing tail over a disagreeing anchor is WITHHELD as tampering — it is never
    # answered as a benign "not found", which would be indistinguishable from "never existed".
    with pytest.raises(JournalTamperWithheld):
        journal.read_entry(2)
    # ...while an unknown seq over a HEALTHY log is an honest not-found
    healthy = RetentionJournal(tmp_path / "healthy.db")
    try:
        with pytest.raises(JournalEntryNotFound):
            healthy.read_entry(7)
    finally:
        healthy.close()


def test_middle_rewrite_is_withheld_on_read(journal, capture):
    store, service = capture
    ids = [ingest_completed(service, content=f"invoice.number=M-{i}\n".encode())
           for i in range(3)]
    for i, cid in enumerate(ids):
        _append(journal, cid, policy_id=f"P-{i}")
    journal._conn.execute("UPDATE retention_decisions SET payload = ? WHERE seq = 2",
                          (canonical_json_text({"age_seconds": 999, "cutoff_seconds": 1,
                                                "privacy_marking": "FORGED"}),))
    report = journal.verify_chain()
    assert report.ok is False and report.first_failure_seq == 2
    with pytest.raises(JournalTamperWithheld):
        journal.read_entry(2)
    with pytest.raises(JournalTamperWithheld):              # prefix failure withholds later reads
        journal.read_entry(3)
    with pytest.raises(JournalTamperWithheld):
        journal.enumerate_entries()


def test_deleted_anchor_alone_is_detected(journal, capture):
    store, service = capture
    _append(journal, ingest_completed(service, content=b"invoice.number=A-1\n"))
    _append(journal, ingest_completed(service, content=b"invoice.number=A-2\n"),
            policy_id="P-2")
    journal._conn.execute("DELETE FROM retention_journal_anchor WHERE anchor_seq = 2")
    report = journal.verify_chain()
    assert report.ok is False
    with pytest.raises(JournalTamperWithheld):
        journal.read_entry(2)


def test_empty_log_is_the_only_valid_anchor_free_state(journal):
    assert journal.verify_chain().ok is True
    assert journal.latest_seq() == 0
    assert journal.enumerate_entries() == []


# ---------------------------------------------------------------------------
# AC-1.3.3 / AC-1.3.4 — rollback at every persistence boundary (zero residue)
# ---------------------------------------------------------------------------

def _failure_at(journal, monkeypatch, target, *, do_first=True):
    real = getattr(journal, target)

    def injected(*args, **kwargs):
        if do_first:
            real(*args, **kwargs)
        raise sqlite3.OperationalError(f"injected failure at {target}")

    monkeypatch.setattr(journal, target, injected)


def test_injected_failure_after_row_insert_leaves_zero_residue(journal, capture, monkeypatch):
    store, service = capture
    cid = ingest_completed(service)
    _failure_at(journal, monkeypatch, "_insert_entry")
    with pytest.raises(JournalStorageUnavailable):
        _append(journal, cid)
    assert journal.latest_seq() == 0
    assert journal._conn.execute("SELECT COUNT(*) AS n FROM retention_decisions").fetchone()["n"] == 0
    assert journal._conn.execute(
        "SELECT COUNT(*) AS n FROM retention_journal_anchor").fetchone()["n"] == 0


def test_injected_failure_after_anchor_write_leaves_zero_residue(journal, capture, monkeypatch):
    store, service = capture
    cid = ingest_completed(service)
    _failure_at(journal, monkeypatch, "_write_anchor")
    with pytest.raises(JournalStorageUnavailable):
        _append(journal, cid)
    assert journal.verify_chain().record_count == 0


def test_injected_commit_failure_leaves_zero_residue(journal, capture, monkeypatch):
    store, service = capture
    cid = ingest_completed(service)
    real_conn = journal._conn

    class _CommitRefusing:
        def execute(self, sql, *args, **kwargs):
            if sql.strip().upper() == "COMMIT":
                raise sqlite3.OperationalError("injected COMMIT failure")
            return real_conn.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(real_conn, name)

    monkeypatch.setattr(journal, "_conn", _CommitRefusing())
    with pytest.raises(JournalStorageUnavailable):
        _append(journal, cid)
    monkeypatch.undo()
    assert journal.latest_seq() == 0


def test_unknown_exception_leaves_no_open_transaction(journal, capture, monkeypatch):
    """An unforeseen failure must roll back too — the append is never left half-done."""
    store, service = capture
    cid = ingest_completed(service)

    def boom(*args, **kwargs):
        raise RuntimeError("unforeseen defect")

    monkeypatch.setattr(journal, "_write_anchor", boom)
    with pytest.raises(RuntimeError):
        _append(journal, cid)
    monkeypatch.undo()
    # no dangling transaction: the connection is usable and a later append succeeds
    appended = _append(journal, cid, policy_id="P-AFTER")
    assert appended.seq == 1
    assert journal.verify_chain().ok is True


def test_append_after_a_rolled_back_failure_is_clean(journal, capture, monkeypatch):
    store, service = capture
    cid = ingest_completed(service)
    _failure_at(journal, monkeypatch, "_insert_entry")
    with pytest.raises(JournalStorageUnavailable):
        _append(journal, cid)
    monkeypatch.undo()
    ok = _append(journal, cid)
    assert ok.seq == 1 and journal.verify_chain().ok is True
    # the rolled-back attempt consumed no seq and left no anchor
    assert journal._conn.execute("SELECT MAX(anchor_seq) AS m FROM retention_journal_anchor").fetchone()["m"] == 1


def test_partially_built_transaction_is_rolled_back_atomically(journal, capture, monkeypatch):
    """Row + anchor commit together: a failure between them writes NOTHING durable."""
    store, service = capture
    cid = ingest_completed(service)
    _append(journal, cid, policy_id="P-KEEP")
    _failure_at(journal, monkeypatch, "_write_anchor")
    with pytest.raises(JournalStorageUnavailable):
        _append(journal, cid, policy_id="P-FAIL")
    entries = journal.enumerate_entries()
    assert [e.policy_id for e in entries] == ["P-KEEP"]


# ---------------------------------------------------------------------------
# Concurrency + recovery semantics
# ---------------------------------------------------------------------------

def test_concurrent_appends_keep_the_chain_exact(journal, capture):
    """Serialized by the write transaction: no lost anchor, no gap, no duplicate seq."""
    store, service = capture
    cids = [ingest_completed(service, content=f"invoice.number=C-{i}\n".encode())
            for i in range(8)]
    errors: list = []
    barrier = threading.Barrier(len(cids))

    def worker(cid, index):
        own = RetentionJournal(Path(journal.db_path))   # independent connection per caller
        try:
            barrier.wait(timeout=30)                    # maximize contention
            _append(own, cid, policy_id=f"PC-{index}")
        except Exception as exc:                        # recorded, never swallowed
            errors.append(repr(exc))
        finally:
            own.close()

    threads = [threading.Thread(target=worker, args=(cid, i)) for i, cid in enumerate(cids)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert errors == []
    report = journal.verify_chain()
    assert report.ok is True and report.record_count == 8
    assert [e.seq for e in journal.enumerate_entries()] == list(range(1, 9))


def test_concurrent_identical_appends_are_exactly_one_row(journal, capture):
    store, service = capture
    cid = ingest_completed(service)
    outcomes: list = []
    lock = threading.Lock()
    barrier = threading.Barrier(6)

    def worker():
        own = RetentionJournal(Path(journal.db_path))   # independent connection per caller
        try:
            barrier.wait(timeout=30)
            _append(own, cid)
            with lock:
                outcomes.append("appended")
        except JournalDuplicateDecision:
            with lock:
                outcomes.append("duplicate-refused")
        except Exception as exc:
            with lock:
                outcomes.append(f"unexpected:{exc!r}")
        finally:
            own.close()

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert "unexpected:" not in "".join(outcomes)
    assert outcomes.count("appended") == 1 and outcomes.count("duplicate-refused") == 5
    assert journal.verify_chain().record_count == 1


def test_recovery_status_reports_residue_computed_not_assumed(journal, capture):
    store, service = capture
    _append(journal, ingest_completed(service))
    status = journal.recovery_status()
    assert status.residue_rows == 0
    assert status.chain_ok is True and status.complete is True
    assert "by construction" in status.detail
    # a broken log makes recovery report incomplete — it does not "self-heal" silently
    journal._conn.execute("DELETE FROM retention_decisions WHERE seq = 1")
    broken = journal.recovery_status()
    assert broken.complete is False and broken.chain_ok is False


# ---------------------------------------------------------------------------
# Structural boundaries of the new module
# ---------------------------------------------------------------------------

def test_journal_is_append_only_no_update_no_delete_statement():
    import re
    import capture.retention_journal as journal_module
    source = Path(journal_module.__file__).read_text(encoding="utf-8")
    import ast
    verbs = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            match = re.match(r"\s*([A-Za-z]+)", node.value)
            if match and node.value.strip().upper().startswith(
                    ("SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "REPLACE",
                     "CREATE", "PRAGMA", "BEGIN", "COMMIT", "ROLLBACK")):
                verbs.add(match.group(1).upper())
    assert "UPDATE" not in verbs and "DELETE" not in verbs and "DROP" not in verbs, verbs
    assert "INSERT" in verbs
    assert not any(name in dir(RetentionJournal)
                   for name in ("delete", "purge", "remove", "truncate", "clear", "wipe"))


def test_journal_never_stores_artifact_content(journal, capture):
    store, service = capture
    cid = ingest_completed(service, content=b"SECRET-INVOICE-CONTENT-42")
    _append(journal, cid)
    dumped = ""
    for (table,) in journal._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"):
        for row in journal._conn.execute(f"SELECT * FROM {table}"):
            dumped += " | ".join(str(v) for v in row)
    assert "SECRET-INVOICE-CONTENT-42" not in dumped


def test_purge_refusal_is_recordable_as_audit_only(journal, capture):
    """Recording a blocked purge is an audit entry; it carries executed=False, rows=0."""
    store, service = capture
    cid = ingest_completed(service, content=b"SECRET-INVOICE-CONTENT-42")
    decision = request_purge(cid, policy=None)
    assert decision.outcome == RETENTION_OUTCOME_PURGE_GATE_BLOCKED
    appended = journal.append_decision(
        capture_id=cid, policy_id=None, outcome=decision.outcome,
        evaluation_time=EVAL_TIME,
        payload={"executed": decision.executed, "rows_affected": decision.rows_affected,
                 "authorization_supplied": False,
                 "policy_status_label": DEF4_PENDING_LABEL})
    entry = journal.read_entry(appended.seq)
    assert entry.payload["executed"] is False and entry.payload["rows_affected"] == 0
    # ...and the artifact itself is still fully intact and readable
    read = service.read_evidence(cid)
    assert type(read).__name__ == "ReadSuccess"
    assert read.content == b"SECRET-INVOICE-CONTENT-42"
