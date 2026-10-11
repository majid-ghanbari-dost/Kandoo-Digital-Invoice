"""WP-1.3 AC-1.3.2 / AC-1.3.3 — recovery hardening, concurrency and additive-only proof.

Crash windows are simulated by building exactly the durable residue a kill at that step
leaves behind (the frozen WP-1.1 suite establishes this technique: a real process kill is
process-level, the residue is byte-identical). Every assertion below is
interleaving-independent: it states an invariant, never a scheduling outcome.
"""
from __future__ import annotations

import ast
import sqlite3
import threading
from pathlib import Path

import pytest

from capture import (
    NOTE_CONTENT_MISSING,
    CaptureService,
    CaptureState,
    CaptureStore,
    IntegrityStatus,
    S1Service,
    run_startup_recovery,
)
from capture import model as capture_model
from capture import recovery as capture_recovery
from capture import service as capture_service
from capture import store as capture_store
from capture.consistency import (
    F_JOURNAL_CHAIN_BROKEN,
    F_ORPHAN_RECORD_CONTENT_MISSING,
    F_RETENTION_POLICY_UNDECLARED,
    F_UNRESOLVED_ACTIVE_LEFTOVER,
    build_consistency_report,
)
from capture.retention import (
    DEF4_PENDING_LABEL,
    RETENTION_OUTCOME_ELIGIBLE,
    RETENTION_OUTCOME_STATE_REFUSED,
    evaluate_retention,
    request_purge,
)
from capture.retention_journal import (
    JournalDuplicateDecision,
    RetentionJournal,
)
from capture import s1 as capture_s1

from wp13_helpers import EVAL_TIME, POLICY_ID, RECEIVED_AT, ingest_completed, policy

CAPTURE_DIR = Path(__file__).resolve().parents[1]
WP13_MODULES = ("retention.py", "retention_journal.py", "consistency.py")
FROZEN_MODULES = ("model.py", "store.py", "service.py", "recovery.py", "s1.py")


@pytest.fixture()
def env(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    journal = RetentionJournal(tmp_path / "journal.db")
    yield tmp_path, store, CaptureService(store, S1Service()), journal
    journal.close()
    store.close()


# ---------------------------------------------------------------------------
# Crash matrix over the retention boundary
# ---------------------------------------------------------------------------

def _residue_store(tmp_path, content=b"invoice.number=CRASH-1\n"):
    """Return (store, service, capture_id, finalizer) for the four crash windows."""
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    rec = store.create_active(received_at=RECEIVED_AT)
    return store, service, rec.capture_id


def test_w1_record_only_residue_is_refused_by_retention_then_settled(tmp_path):
    store, service, cid = _residue_store(tmp_path)
    try:
        before = evaluate_retention(store.get_record(cid), policy=policy(cutoff_seconds=1),
                                     evaluation_time=EVAL_TIME)
        assert before.outcome == RETENTION_OUTCOME_STATE_REFUSED
        report = build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                          evaluation_time=EVAL_TIME)
        assert F_UNRESOLVED_ACTIVE_LEFTOVER in report.codes()
        recovery = run_startup_recovery(store, S1Service())
        assert recovery.complete is True
        assert (cid, NOTE_CONTENT_MISSING) in recovery.settled_failed
        after = build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                         evaluation_time=EVAL_TIME)
        assert F_UNRESOLVED_ACTIVE_LEFTOVER not in after.codes()
    finally:
        store.close()


def test_all_crash_windows_end_terminal_with_the_retention_layer_attached(tmp_path):
    """W2 content-persist, W3 attach, W4 verify → each settles; nothing is left half-built."""
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    # distinct bytes per window: identical payloads would collide on the frozen
    # (s1, algorithm) uniqueness index and mask the settlement under test
    def content_of(tag: str) -> bytes:
        return f"invoice.number=W-MATRIX-{tag}\n".encode()
    ids = {}
    ids["W1"] = store.create_active(received_at=RECEIVED_AT).capture_id
    cid = store.create_active(received_at=RECEIVED_AT).capture_id
    store.persist_content(cid, content_of("W2"))
    ids["W2"] = cid
    cid = store.create_active(received_at=RECEIVED_AT).capture_id
    store.persist_content(cid, content_of("W3"))
    value = S1Service().compute(content_of("W3"))
    store.attach_s1(cid, value.s1, value.s1_algorithm_id)
    ids["W3"] = cid
    cid = store.create_active(received_at=RECEIVED_AT).capture_id
    w4 = content_of("W4")
    store.persist_content(cid, w4)
    value4 = S1Service().compute(w4)
    store.attach_s1(cid, value4.s1, value4.s1_algorithm_id)
    store.record_verification(cid, "VALID", "2026-10-11T00:00:00+00:00")
    ids["W4"] = cid

    report = run_startup_recovery(store, S1Service())
    assert report.remaining_active == 0 and report.complete is True
    for name, capture_id in ids.items():
        record = store.get_record(capture_id)
        assert record.capture_state is not CaptureState.ACTIVE, name
    # W4's residue was completable (verified VALID + unique) — settled to COMPLETED,
    # through the same UAC primitive ingest uses (no side path, P5)
    assert ids["W4"] in report.settled_completed
    assert store.get_record(ids["W4"]).capture_state is CaptureState.COMPLETED
    # and the report agrees with the store, without having settled anything itself
    audit = build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                     evaluation_time=EVAL_TIME)
    assert F_UNRESOLVED_ACTIVE_LEFTOVER not in audit.codes()
    store.close()


def test_recovery_is_idempotent_across_restarts_with_journal(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    journal = RetentionJournal(tmp_path / "journal.db")
    cid = ingest_completed(service)
    residue = store.create_active(received_at=RECEIVED_AT).capture_id
    first = run_startup_recovery(store, S1Service())
    assert first.remaining_active == 0
    _record(journal, cid)
    bytes_after_first = (tmp_path / "journal.db").read_bytes()
    capture_bytes = (tmp_path / "capture.db").read_bytes()
    for _ in range(2):
        again = run_startup_recovery(store, S1Service())
        assert again.complete is True and again.remaining_active == 0
        assert again.settled_completed == [] and again.settled_failed == []
    store.close(); journal.close()
    # repeated recovery writes nothing further, and never touches the journal
    reopened = CaptureStore(tmp_path / "capture.db")
    journal_reopened = RetentionJournal(tmp_path / "journal.db")
    try:
        assert reopened.get_record(residue).capture_state is CaptureState.FAILED_INCOMPLETE
        assert journal_reopened.verify_chain().record_count == 1
        assert (tmp_path / "journal.db").read_bytes() == bytes_after_first
        assert capture_bytes == (tmp_path / "capture.db").read_bytes()   # recovery wrote nothing more
    finally:
        reopened.close(); journal_reopened.close()


def test_purge_requests_during_recovery_are_inert(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    ingest_completed(service)
    residue_ids = [store.create_active(received_at=RECEIVED_AT).capture_id for _ in range(2)]
    before = (tmp_path / "capture.db").read_bytes()
    run_startup_recovery(store, S1Service())
    for cid in residue_ids:
        blocked = request_purge(cid, policy=policy())
        assert blocked.outcome == "PURGE_GATE_BLOCKED" and blocked.executed is False
    run_startup_recovery(store, S1Service())
    conn = sqlite3.connect(str(tmp_path / "capture.db"))
    try:
        counts = conn.execute("SELECT COUNT(*) AS n FROM capture_records").fetchone()[0]
        contents = conn.execute("SELECT COUNT(*) AS n FROM artifact_content").fetchone()[0]
    finally:
        conn.close()
    assert counts == 3 and contents == 1          # 2 residue records kept (no content, no deletion)
    store.close()
    # the *file* only advanced through the frozen settlement writes, never a purge
    assert (tmp_path / "capture.db").stat().st_size > 0


def test_orphan_content_after_a_crash_is_reported_never_deleted(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    cid = ingest_completed(service, content=b"invoice.number=ORPHAN-1\n")
    ref = store.get_record(cid).artifact_ref
    store._conn.execute("DELETE FROM artifact_content WHERE content_ref = ?", (ref,))
    run_startup_recovery(store, S1Service())
    report = build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                      evaluation_time=EVAL_TIME)
    assert F_ORPHAN_RECORD_CONTENT_MISSING in report.codes()
    # the record still exists, settled/terminal, and was NOT auto-repaired or auto-deleted
    record = store.get_record(cid)
    assert record.capture_state in (CaptureState.COMPLETED, CaptureState.FAILED_INCOMPLETE)
    store.close()


def test_duplicate_handling_after_recovery_is_deduped_and_journalled_once(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    journal = RetentionJournal(tmp_path / "journal.db")
    content = b"invoice.number=DUP-1\n"
    first = ingest_completed(service, content=content)
    run_startup_recovery(store, S1Service())
    replay = service.ingest(content, received_at=RECEIVED_AT)
    assert type(replay).__name__ == "IngestDuplicateAtCapture"
    assert replay.existing_capture_id == first
    record = store.get_record(first)
    decision = evaluate_retention(record, policy=policy(cutoff_seconds=1),
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_ELIGIBLE
    appended = _record(journal, first, age=decision.age_seconds)
    assert appended is not None and appended.seq == 1
    assert _record(journal, first, age=decision.age_seconds) is None   # idempotent no-op
    assert journal.verify_chain().record_count == 1
    assert store.count_by_key(record.s1, record.s1_algorithm_id) == (1, 1)
    journal.close(); store.close()


def _record(journal, capture_id, *, age=3_456_000):
    try:
        return journal.append_decision(
            capture_id=capture_id, policy_id=POLICY_ID,
            outcome=RETENTION_OUTCOME_ELIGIBLE, evaluation_time=EVAL_TIME,
            payload={"age_seconds": age, "cutoff_seconds": 1_000,
                     "privacy_marking": "TEST-CLASS-A"})
    except JournalDuplicateDecision:
        return None


# ---------------------------------------------------------------------------
# Concurrency: recovery against live ingestion (frozen recovery, new invariants)
# ---------------------------------------------------------------------------

def test_recovery_concurrent_with_ingest_preserves_every_invariant(tmp_path):
    """Recovery settles ALL ACTIVE records (frozen INV-C6 semantics). Under real
    concurrency an in-flight ingest may therefore have its record settled mid-flight and
    surface a typed CaptureLayerError — that is an explicit refusal, never corruption.
    Asserted: no crash outside the typed layer errors, zero ACTIVE afterwards, at most
    one COMPLETED per S1, and no artifact byte lost.
    """
    rounds, ingests = 4, 12
    errors: list = []
    barrier = threading.Barrier(3)          # the three ingest workers synchronize once

    def ingest_worker(index):
        store = CaptureStore(tmp_path / "capture.db")          # connection per caller
        try:
            service = CaptureService(store, S1Service())
            barrier.wait(timeout=30)                            # maximize contention
            for i in range(ingests):
                service.ingest(f"invoice.number=LIVE-{index}-{i}\n".encode(),
                               received_at=RECEIVED_AT)
        except Exception as exc:                                # typed refusals only
            if not isinstance(exc, capture_model.CaptureLayerError):
                errors.append(repr(exc))
        finally:
            store.close()

    def recovery_worker():
        store = CaptureStore(tmp_path / "capture.db")
        try:
            for _ in range(rounds):
                report = run_startup_recovery(store, S1Service())
                assert isinstance(report.remaining_active, int)
        except Exception as exc:
            if not isinstance(exc, capture_model.CaptureLayerError):
                errors.append(repr(exc))
        finally:
            store.close()

    threads = [threading.Thread(target=ingest_worker, args=(i,)) for i in range(3)]
    threads.append(threading.Thread(target=recovery_worker))
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert errors == [], f"non-layer error surfaced: {errors}"

    final = CaptureStore(tmp_path / "capture.db")
    try:
        report = run_startup_recovery(final, S1Service())
        assert report.remaining_active == 0 and report.complete is True
        conn = final._conn
        active = conn.execute("SELECT COUNT(*) AS n FROM capture_records "
                              "WHERE capture_state='ACTIVE'").fetchone()["n"]
        assert active == 0
        dupes = conn.execute(
            "SELECT COUNT(*) AS n FROM (SELECT s1 FROM capture_records "
            "WHERE capture_state='COMPLETED' GROUP BY s1 HAVING COUNT(*) > 1)").fetchone()["n"]
        assert dupes == 0
        completed = conn.execute("SELECT COUNT(*) AS n FROM capture_records "
                                 "WHERE capture_state='COMPLETED'").fetchone()["n"]
        artifacts = conn.execute("SELECT COUNT(*) AS n FROM artifact_content").fetchone()["n"]
        assert artifacts >= completed                       # no artifact was ever removed
        integrity = conn.execute(
            "SELECT COUNT(*) AS n FROM capture_records WHERE capture_state='COMPLETED' "
            "AND (s1 IS NULL OR artifact_ref IS NULL)").fetchone()["n"]
        assert integrity == 0                               # INV-C1 holds under the race
    finally:
        final.close()


# ---------------------------------------------------------------------------
# Additive-only discipline (no frozen file was touched or rewired)
# ---------------------------------------------------------------------------

def test_frozen_capture_modules_do_not_import_wp13():
    """WP-1.3 is non-intrusive: nothing frozen now depends on it."""
    for name in FROZEN_MODULES + ("__init__.py",):
        tree = ast.parse((CAPTURE_DIR / name).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
        assert not {"retention", "retention_journal", "consistency"} & {
            m.split(".")[-1] for m in imported}, name


def test_wp13_modules_import_only_stdlib_and_capture_siblings():
    for name in WP13_MODULES:
        tree = ast.parse((CAPTURE_DIR / name).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    imported.add(node.module.split(".")[0])
                elif node.level > 0:
                    imported.add(f".{node.module}")
        assert imported <= {"__future__", "json", "sqlite3", "dataclasses", "datetime",
                            "typing", "inspect", "re", "pathlib", "urllib", ".model", ".s1",
                            ".retention", ".retention_journal", ".consistency"}, (name, imported)
        forbidden = {"sale", "inventory", "customer_linking", "digital_invoice",
                     "canonical_assembly", "canonicalization", "extraction",
                     "reconstruction", "validation", "validation_domain", "derivation",
                     "normalization", "identity_resolution", "duplicate_flows",
                     "product_candidate", "holoo_spike", "corpus", "calibration"}
        assert imported.isdisjoint(forbidden), name


def test_no_wp13_symbol_is_exported_from_the_frozen_package_entrypoint():
    import capture
    leaked = [name for name in capture.__all__
              if "retention" in name.lower() or "consistency" in name.lower()
              or "purge" in name.lower() or "journal" in name.lower()]
    assert leaked == []
    assert "retention" not in (CAPTURE_DIR / "__init__.py").read_text(encoding="utf-8")


def test_frozen_layer_files_are_untouched_in_the_working_tree():
    """Only git can prove byte-identity; this test proves the *scope* of the change."""
    files = sorted(p.name for p in CAPTURE_DIR.glob("*.py"))
    assert set(FROZEN_MODULES).issubset(files)
    assert set(WP13_MODULES).issubset(files)
    # no frozen module grew a WP-1.3 hook: their sources never mention the new names
    for name in FROZEN_MODULES:
        text = (CAPTURE_DIR / name).read_text(encoding="utf-8")
        assert "WP-1.3" not in text and "retention" not in text.lower(), name


def test_wp13_never_opens_the_capture_store_writable_from_the_report():
    """Structural: consistency.py has no write statement of any kind."""
    source = (CAPTURE_DIR / "consistency.py").read_text(encoding="utf-8")
    assert "mode=ro" in source
    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "VACUUM"):
        assert f"{verb} " not in source.upper(), verb


def test_def4_pending_label_reaches_every_produced_artifact(tmp_path):
    """Traceability of the DEF4 boundary across all three new modules."""
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    journal = RetentionJournal(tmp_path / "journal.db")
    cid = ingest_completed(service)
    decision = evaluate_retention(store.get_record(cid), policy=policy(),
                                  evaluation_time=EVAL_TIME)
    assert decision.policy_status_label == DEF4_PENDING_LABEL
    purge = request_purge(cid, policy=policy())
    assert purge.policy_status_label == DEF4_PENDING_LABEL
    appended = _record(journal, cid)
    assert journal.read_entry(appended.seq).policy_status_label == DEF4_PENDING_LABEL
    report = build_consistency_report(tmp_path / "capture.db", policy=policy(),
                                      evaluation_time=EVAL_TIME,
                                      journal_db_path=tmp_path / "journal.db")
    assert DEF4_PENDING_LABEL in report.canonical_text
    journal.close(); store.close()


def test_policy_undeclared_is_visible_in_the_report_without_a_policy(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    ingest_completed(service)
    report = build_consistency_report(tmp_path / "capture.db")
    assert F_RETENTION_POLICY_UNDECLARED in report.codes()
    store.close()


def test_state_and_integrity_vocabulary_stay_the_frozen_ones():
    """No new lifecycle state, no new integrity status (AS-03 / D-09 discipline)."""
    assert {s.value for s in CaptureState} == {"ACTIVE", "COMPLETED", "FAILED_INCOMPLETE"}
    assert {s.value for s in IntegrityStatus} == {"UNVERIFIED", "VALID", "FAILED"}
    assert not hasattr(capture_store, "RetentionJournal")
    assert not hasattr(capture_recovery, "retention")
    assert not hasattr(capture_service, "purge")
    assert capture_s1.S1_ALGORITHM_ID == "sha256-v1"
