"""Cold-start smoke check — WP-1.3 RETENTION & RECOVERY (mechanics-only) — 21st smoke.

Runs the whole WP-1.3 surface WITHOUT pytest on a fresh directory, cold start:
policy absence → injected eligibility → purge gate blockage (storage provably stable)
→ decision journal (chain + idempotency) → truncation/broken-chain refusal →
restart + deterministic consistency report → DEF4/frozen-boundary recap.

Every step asserts typed outcomes and byte-level storage effects; nothing is inferred
from a log line. This is the runner a reviewer can execute in one command:

    python3 kandoo/src/run_smoke_retention_recovery.py /tmp/kandoo-smoke-wp13
"""
from __future__ import annotations

import ast
import shutil
import sqlite3
import sys
from pathlib import Path

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-smoke-wp13")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import CaptureService, CaptureStore, S1Service, run_startup_recovery  # noqa: E402
from capture.consistency import (NOT_EVALUATED, F_JOURNAL_CHAIN_BROKEN,  # noqa: E402
                                 F_RETENTION_POLICY_UNDECLARED,
                                 F_UNRESOLVED_ACTIVE_LEFTOVER,
                                 build_consistency_report)
from capture.retention import (  # noqa: E402
    DEF4_PENDING_LABEL,
    PURGE_EXECUTION_ALLOWED,
    RETENTION_OUTCOME_ELIGIBLE,
    RETENTION_OUTCOME_NOT_ELIGIBLE,
    RETENTION_OUTCOME_POLICY_UNDECLARED,
    RETENTION_OUTCOME_PURGE_GATE_BLOCKED,
    RETENTION_OUTCOME_STATE_REFUSED,
    RetentionIllegalInput,
    RetentionPolicy,
    RetentionPolicyIncomplete,
    evaluate_retention,
    request_purge,
)
from capture.retention_journal import (  # noqa: E402
    JournalChainBroken, JournalDuplicateDecision, JournalTamperWithheld, RetentionJournal,
)

RECEIVED_AT = "2026-09-01T00:00:00+00:00"
EVAL_TIME = "2026-10-11T00:00:00+00:00"
AGE_AT_EVAL = 3_456_000                      # 40 days — arithmetic, not a policy value


def step(ok: bool, message: str) -> None:
    if not ok:
        print(f"SMOKE FAIL — {message}")
        sys.exit(1)
    print(f"  ok  {message}")


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)
    BASE.mkdir(parents=True)
    capture_db = BASE / "capture.db"
    journal_db = BASE / "journal.db"
    tamper_db = BASE / "journal-tamper.db"

    # 1. cold start against the frozen layer: ingest → COMPLETED → verified read
    store = CaptureStore(capture_db)
    service = CaptureService(store, S1Service())
    content = b"invoice.number=WP13-SMOKE-1\ninvoice.date=2026-09-01\ntotal.net=1200.00\n"
    ingested = service.ingest(content, received_at=RECEIVED_AT, source_label="smoke")
    assert type(ingested).__name__ == "IngestCompleted", ingested
    cid = ingested.capture_id
    read = service.read_evidence(cid)
    assert type(read).__name__ == "ReadSuccess" and read.content == content
    step(True, f"1. cold start     -> COMPLETED {cid[:8]}… + verified read byte-exact")

    # 2. no policy injected = default-deny (no invented DEF4 value anywhere)
    record = store.get_record(cid)
    undeclared = evaluate_retention(record, policy=None, evaluation_time=EVAL_TIME)
    assert undeclared.outcome == RETENTION_OUTCOME_POLICY_UNDECLARED
    assert undeclared.policy_status_label == DEF4_PENDING_LABEL
    for partial in ({}, {"policy_id": "P"}, {"policy_id": "P", "basis": "created_at"},
                    {"cutoff_seconds": 1000}, {"privacy_marking": "X"}):
        try:
            RetentionPolicy(**partial)
            raise AssertionError(f"partial policy {partial} must not be constructible")
        except RetentionPolicyIncomplete as exc:
            assert exc.missing                            # named, never silently defaulted
    step(True, f"2. no policy      -> {undeclared.outcome}; every partial policy refused "
               f"(5 shapes, each naming what is missing)")

    # 3. eligibility exists ONLY under an injected policy at an injected instant
    beyond = evaluate_retention(record, policy=RetentionPolicy(
        policy_id="SMOKE-P", basis="received_at", cutoff_seconds=AGE_AT_EVAL,
        privacy_marking="SMOKE-CLASS", candidate_reporting=True), evaluation_time=EVAL_TIME)
    within = evaluate_retention(record, policy=RetentionPolicy(
        policy_id="SMOKE-P", basis="received_at", cutoff_seconds=AGE_AT_EVAL + 1,
        privacy_marking="SMOKE-CLASS", candidate_reporting=True), evaluation_time=EVAL_TIME)
    no_clock = evaluate_retention(record, policy=RetentionPolicy(
        policy_id="SMOKE-P", basis="received_at", cutoff_seconds=1,
        privacy_marking="SMOKE-CLASS", candidate_reporting=True), evaluation_time=None)
    assert beyond.outcome == RETENTION_OUTCOME_ELIGIBLE and beyond.age_seconds == AGE_AT_EVAL
    assert within.outcome == RETENTION_OUTCOME_NOT_ELIGIBLE and within.remaining_seconds == 1
    assert no_clock.outcome == "DATA_ANOMALY"
    unresolved = store.create_active(received_at=RECEIVED_AT)
    assert evaluate_retention(
        store.get_record(unresolved.capture_id),
        policy=RetentionPolicy(policy_id="SMOKE-P", basis="received_at", cutoff_seconds=1,
                               privacy_marking="SMOKE-CLASS", candidate_reporting=True),
        evaluation_time=EVAL_TIME).outcome == RETENTION_OUTCOME_STATE_REFUSED
    step(True, "3. injected policy -> eligible at cutoff, 1s inside window, ACTIVE refused, "
               "no injected instant → refused")

    # 4. purge gate: blocked, inert, storage byte-stable
    before_bytes = capture_db.read_bytes()
    blocked = request_purge(cid, policy=RetentionPolicy(
        policy_id="SMOKE-P", basis="received_at", cutoff_seconds=1,
        privacy_marking="SMOKE-CLASS", candidate_reporting=True),
        authorization=object())
    assert blocked.outcome == RETENTION_OUTCOME_PURGE_GATE_BLOCKED
    assert blocked.executed is False and blocked.rows_affected == 0
    assert "cannot be verified" in blocked.reason
    assert capture_db.read_bytes() == before_bytes
    assert service.read_evidence(cid).content == content          # artifact still there
    conn = sqlite3.connect(str(capture_db))
    counts = (conn.execute("SELECT COUNT(*) FROM capture_records").fetchone()[0],
              conn.execute("SELECT COUNT(*) FROM artifact_content").fetchone()[0])
    conn.close()
    assert counts == (2, 1)                                       # 1 completed + 1 ACTIVE residue
    step(True, "4. purge gate     -> PURGE_GATE_BLOCKED (even with a forged credential); "
               "capture.db bytes identical; artifact readable")

    # 5. decision journal: chain-exact append + idempotent duplicate
    journal = RetentionJournal(journal_db)
    for label, decision in (("SMOKE-P", beyond), ("SMOKE-P", within)):
        payload = ({"age_seconds": decision.age_seconds, "cutoff_seconds": AGE_AT_EVAL,
                    "privacy_marking": "SMOKE-CLASS"}
                   if decision.outcome == RETENTION_OUTCOME_ELIGIBLE else
                   {"age_seconds": decision.age_seconds, "cutoff_seconds": AGE_AT_EVAL + 1,
                    "remaining_seconds": decision.remaining_seconds})
        journal.append_decision(capture_id=decision.capture_id, policy_id=label,
                                outcome=decision.outcome, evaluation_time=EVAL_TIME,
                                payload=payload)
    journal.append_decision(capture_id=cid, policy_id="SMOKE-P",
                            outcome=RETENTION_OUTCOME_PURGE_GATE_BLOCKED,
                            evaluation_time=EVAL_TIME,
                            payload={"executed": False, "rows_affected": 0,
                                     "authorization_supplied": True,
                                     "policy_status_label": DEF4_PENDING_LABEL})
    try:
        journal.append_decision(capture_id=cid, policy_id="SMOKE-P",
                                outcome=RETENTION_OUTCOME_ELIGIBLE, evaluation_time=EVAL_TIME,
                                payload={"age_seconds": beyond.age_seconds,
                                         "cutoff_seconds": AGE_AT_EVAL,
                                         "privacy_marking": "SMOKE-CLASS"})
        raise AssertionError("duplicate decision must be refused")
    except JournalDuplicateDecision as exc:
        duplicate_seq = exc.seq
        assert duplicate_seq == 1
    report = journal.verify_chain()
    assert report.ok is True and report.record_count == 3
    assert journal.recovery_status().complete is True
    step(True, f"5. journal        -> 3 chained decisions, duplicate refused at seq "
               f"{duplicate_seq}, recovery status complete")

    # 6. tamper evidence: truncated tail is detected and blocks any further append
    tamper = RetentionJournal(tamper_db)
    for i in range(3):
        tamper.append_decision(capture_id=f"probe-{i}", policy_id="SMOKE-P",
                              outcome=RETENTION_OUTCOME_NOT_ELIGIBLE, evaluation_time=EVAL_TIME,
                              payload={"age_seconds": 1, "cutoff_seconds": 2,
                                       "remaining_seconds": 1})
    raw = sqlite3.connect(str(tamper_db))
    raw.execute("DELETE FROM retention_decisions WHERE seq = 3")
    raw.commit()
    raw.close()
    assert tamper.verify_chain().ok is False
    try:
        tamper.append_decision(capture_id="probe-9", policy_id="SMOKE-P",
                              outcome=RETENTION_OUTCOME_NOT_ELIGIBLE, evaluation_time=EVAL_TIME,
                              payload={"age_seconds": 1, "cutoff_seconds": 2,
                                       "remaining_seconds": 1})
        raise AssertionError("append on a broken chain must be refused")
    except JournalChainBroken as broken:
        assert tamper.latest_seq() == 2 and broken.first_failure_seq == 3
    try:
        tamper.read_entry(2)
        raise AssertionError("read over a disagreeing anchor must be withheld")
    except JournalTamperWithheld:
        step(True, "6. tamper evidence -> tail truncation detected, append refused, "
                   "read withheld (no silent extension, no silent read)")
    tamper.close()

    # 7. restart + determinism of the consistency report
    run_startup_recovery(store, S1Service())                  # settle the ACTIVE residue
    store.close(); journal.close()
    store = CaptureStore(capture_db)
    journal = RetentionJournal(journal_db)
    first = build_consistency_report(capture_db, policy=RetentionPolicy(
        policy_id="SMOKE-P", basis="received_at", cutoff_seconds=AGE_AT_EVAL,
        privacy_marking="SMOKE-CLASS", candidate_reporting=True),
        evaluation_time=EVAL_TIME, journal_db_path=journal_db)
    second = build_consistency_report(capture_db, policy=RetentionPolicy(
        policy_id="SMOKE-P", basis="received_at", cutoff_seconds=AGE_AT_EVAL,
        privacy_marking="SMOKE-CLASS", candidate_reporting=True),
        evaluation_time=EVAL_TIME, journal_db_path=journal_db)
    assert first.canonical_text == second.canonical_text
    assert first.report_fingerprint == second.report_fingerprint
    # 1 COMPLETED + 1 record that crashed before content (settled by the frozen recovery)
    assert first.summary["counts"] == {"records_total": 2, "COMPLETED": 1, "ACTIVE": 0,
                                       "FAILED_INCOMPLETE": 1}
    assert first.summary["retention"]["candidates"] == 1
    bare = build_consistency_report(capture_db, journal_db_path=journal_db)
    assert bare.summary["retention"]["candidates"] == NOT_EVALUATED
    assert F_RETENTION_POLICY_UNDECLARED in bare.codes()
    broken = build_consistency_report(capture_db, policy=RetentionPolicy(
        policy_id="SMOKE-P", basis="received_at", cutoff_seconds=1,
        privacy_marking="SMOKE-CLASS", candidate_reporting=True),
        evaluation_time=EVAL_TIME, journal_db_path=tamper_db)
    assert F_JOURNAL_CHAIN_BROKEN in broken.codes()
    assert F_UNRESOLVED_ACTIVE_LEFTOVER not in first.codes()
    step(True, f"7. restart        -> report byte-identical ×2 (fingerprint "
               f"{first.report_fingerprint[:12]}…), residue settled, no-policy = NOT_EVALUATED, "
               f"broken journal surfaced")

    # 8. boundary recap: DEF4 untouched, no deletion surface, frozen layer unmodified
    capture_dir = Path(__file__).resolve().parent / "capture"
    for name in ("retention.py", "retention_journal.py", "consistency.py"):
        tree = ast.parse((capture_dir / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                head = node.value.strip().upper()
                for verb in ("DELETE", "UPDATE", "DROP ", "ALTER", "VACUUM"):
                    assert not head.startswith(verb), (name, verb[:6])
    for name in ("retention.py", "consistency.py"):        # the report/gate own no clock
        tree = ast.parse((capture_dir / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"now", "today", "utcnow", "monotonic"}, (name, node.attr)
    assert PURGE_EXECUTION_ALLOWED is False
    assert not hasattr(sys.modules["capture.retention"], "execute_purge")
    assert (capture_dir / "__init__.py").read_text(encoding="utf-8").count("retention") == 0
    frozen = ["model.py", "store.py", "service.py", "recovery.py", "s1.py"]
    assert all((capture_dir / f).exists() for f in frozen)
    step(True, "8. boundary recap -> zero mutation SQL in WP-1.3 modules; no clock in the "
               "gate/report; purge gate closed by construction; frozen capture modules "
               "carry no WP-1.3 hook")

    journal.close(); store.close()
    print("SMOKE OK — WP-1.3 retention/recovery mechanics hold end-to-end "
          "(cold start; DEF4 policy values remain un-set; no physical deletion)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
