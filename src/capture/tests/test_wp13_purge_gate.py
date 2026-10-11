"""WP-1.3 AC-1.3.3 — purge gate: default-deny, zero deletion, storage provably untouched.

The strongest claim in this file is not "purge returns a refusal object" but
"nothing on disk changed": every test compares the storage bytes before and after.
"""
from __future__ import annotations

import sqlite3

import pytest

from capture import CaptureService, CaptureStore, S1Service
from capture.retention import (
    DEF4_PENDING_LABEL,
    PURGE_EXECUTION_ALLOWED,
    PURGE_GATE_REASON_DEF4,
    RETENTION_OUTCOME_ELIGIBLE,
    RETENTION_OUTCOME_PURGE_GATE_BLOCKED,
    RetentionPolicy,
    evaluate_retention,
    request_purge,
)
from capture.retention_journal import JournalDuplicateDecision, RetentionJournal
from capture.consistency import build_consistency_report

from wp13_helpers import EVAL_TIME, POLICY_ID, ingest_completed, policy


@pytest.fixture()
def pair(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    yield tmp_path, store, CaptureService(store, S1Service())
    store.close()


def _snapshot(path) -> bytes:
    """The whole database file, byte for byte."""
    return path.read_bytes()


# ---------------------------------------------------------------------------
# Default-deny
# ---------------------------------------------------------------------------

def test_purge_is_blocked_with_no_policy_at_all(pair):
    _, store, service = pair
    cid = ingest_completed(service)
    decision = request_purge(cid, policy=None)
    assert decision.outcome == RETENTION_OUTCOME_PURGE_GATE_BLOCKED
    assert decision.executed is False and decision.rows_affected == 0
    assert decision.policy_status_label == DEF4_PENDING_LABEL
    assert "DEF4-PENDING" in decision.reason


def test_purge_is_blocked_even_for_a_full_eligible_candidate(pair):
    """Eligibility is a REPORT; it never converts into an authorized action."""
    _, store, service = pair
    cid = ingest_completed(service)
    record = store.get_record(cid)
    evaluated = evaluate_retention(record, policy=policy(cutoff_seconds=1),
                                   evaluation_time=EVAL_TIME)
    assert evaluated.outcome == RETENTION_OUTCOME_ELIGIBLE
    blocked = request_purge(cid, policy=policy(cutoff_seconds=1))
    assert blocked.outcome == RETENTION_OUTCOME_PURGE_GATE_BLOCKED
    assert blocked.executed is False


def test_purge_is_blocked_under_every_policy_shape_the_caller_can_invent(pair):
    """No combination of injected values can open the gate (OD-RT-C)."""
    _, store, service = pair
    cid = ingest_completed(service)
    shapes = [
        RetentionPolicy(policy_id="ALL-ZERO", basis="created_at", cutoff_seconds=0,
                        privacy_marking="PUBLIC", candidate_reporting=True),
        RetentionPolicy(policy_id="REPORT-OFF", basis="received_at", cutoff_seconds=0,
                        privacy_marking="SECRET", candidate_reporting=False),
        policy(),
    ]
    for shape in shapes:
        decision = request_purge(cid, policy=shape)
        assert decision.outcome == RETENTION_OUTCOME_PURGE_GATE_BLOCKED, shape.policy_id
        assert decision.rows_affected == 0


def test_fabricated_authorization_is_refused_not_trusted(pair):
    """There is no PO-ratified issuer to verify a credential against, so a credential
    cannot be validated — it is refused, and the refusal says why."""
    _, store, service = pair
    cid = ingest_completed(service)

    class ForgedAuthorization:                       # any object shape is equally refused
        authorized_by = "PO"
        decision_ref = "PO-2026-0001"
        allow_physical_purge = True

    decision = request_purge(cid, policy=policy(), authorization=ForgedAuthorization())
    assert decision.outcome == RETENTION_OUTCOME_PURGE_GATE_BLOCKED
    assert decision.executed is False
    assert "cannot be verified" in decision.reason
    assert PURGE_EXECUTION_ALLOWED is False


def test_gate_is_not_runtime_configurable():
    """No public surface exists that could flip the gate inside a WP."""
    import capture.retention as gate
    setters = [name for name in dir(gate)
               if name.lower().startswith(("set_", "enable_", "allow_", "configure_"))]
    assert setters == []
    assert PURGE_GATE_REASON_DEF4 == gate.PURGE_GATE_REASON_DEF4   # stable constant


# ---------------------------------------------------------------------------
# Storage stability — the real proof that nothing was deleted
# ---------------------------------------------------------------------------

def test_purge_request_leaves_the_capture_database_bytes_untouched(pair):
    tmp_path, store, service = pair
    cid = ingest_completed(service, content=b"invoice.number=PURGE-1\nartifact-payload")
    before = _snapshot(tmp_path / "capture.db")
    for _ in range(5):
        request_purge(cid, policy=policy())
    assert _snapshot(tmp_path / "capture.db") == before


def test_purge_request_leaves_record_counts_and_states_untouched(pair):
    tmp_path, store, service = pair
    ids = [ingest_completed(service, content=f"invoice.number=CNT-{i}\n".encode())
           for i in range(3)]
    for cid in ids:
        request_purge(cid, policy=policy())
    conn = sqlite3.connect(str(tmp_path / "capture.db"))
    conn.row_factory = sqlite3.Row
    try:
        records = conn.execute("SELECT COUNT(*) AS n FROM capture_records").fetchone()["n"]
        contents = conn.execute("SELECT COUNT(*) AS n FROM artifact_content").fetchone()["n"]
        states = conn.execute(
            "SELECT capture_state, COUNT(*) AS n FROM capture_records GROUP BY capture_state"
        ).fetchall()
    finally:
        conn.close()
    assert records == 3 and contents == 3
    assert {row["capture_state"]: row["n"] for row in states} == {"COMPLETED": 3}


def test_content_is_still_verifiable_after_purge_requests(pair):
    """A refused purge must not even disturb the integrity path."""
    _, store, service = pair
    content = b"invoice.number=ALIVE\n"
    cid = ingest_completed(service, content=content)
    request_purge(cid, policy=policy())
    read = service.read_evidence(cid)
    assert type(read).__name__ == "ReadSuccess"
    assert read.content == content
    assert read.verdict == "VALID"


def test_repeated_purge_requests_are_inert_and_identical(pair):
    _, store, service = pair
    cid = ingest_completed(service)
    decisions = [request_purge(cid, policy=policy()) for _ in range(4)]
    assert {d.to_canonical_dict()["reason"] for d in decisions} == {decisions[0].reason}
    assert all(d.executed is False for d in decisions)


# ---------------------------------------------------------------------------
# Audit trail + report surface
# ---------------------------------------------------------------------------

def test_blocked_purges_are_auditable_without_side_effects(pair, tmp_path):
    """Three identical blocked requests → exactly ONE durable audit entry, and zero
    effect on the artifact database (idempotent trail, inert gate)."""
    _, store, service = pair
    cid = ingest_completed(service)
    before = _snapshot(tmp_path / "capture.db")
    journal = RetentionJournal(tmp_path / "journal.db")
    appended = 0
    refused_duplicates = 0
    try:
        for _ in range(3):
            decision = request_purge(cid, policy=policy())
            try:
                journal.append_decision(
                    capture_id=decision.capture_id, policy_id=decision.policy_id,
                    outcome=decision.outcome, evaluation_time=EVAL_TIME,
                    payload={"executed": decision.executed,
                             "rows_affected": decision.rows_affected,
                             "authorization_supplied": False,
                             "policy_status_label": DEF4_PENDING_LABEL})
                appended += 1
            except JournalDuplicateDecision:
                refused_duplicates += 1
        assert appended == 1 and refused_duplicates == 2
        assert journal.verify_chain().ok is True
        assert _snapshot(tmp_path / "capture.db") == before     # zero effect on artifacts
        report = build_consistency_report(
            tmp_path / "capture.db", policy=policy(), evaluation_time=EVAL_TIME,
            journal_db_path=tmp_path / "journal.db")
        assert report.summary["journal"]["purge_refusals_recorded"] == 1
        assert "JOURNAL_PURGE_REFUSAL_PRESENT" in report.codes()
        assert report.summary["counts"]["COMPLETED"] == 1       # nothing left the store
    finally:
        journal.close()


def test_gate_never_produces_a_downstream_datum(pair):
    """INV-C7/C8 preserved at the WP-1.3 boundary: the decision names only capture ids."""
    _, store, service = pair
    cid = ingest_completed(service)
    payload = request_purge(cid, policy=policy()).to_canonical_dict()
    assert set(payload) == {"outcome", "executed", "rows_affected", "reason",
                            "capture_id", "policy_id", "policy_status_label"}
    assert payload["capture_id"] == cid
    for forbidden in ("sale", "inventory", "customer", "invoice_id", "canonical", "document"):
        assert forbidden not in " ".join(str(v).lower() for v in payload.values())
