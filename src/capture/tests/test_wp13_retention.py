"""WP-1.3 AC-1.3.1 / AC-1.3.4 — retention policy gate (injection, default-deny, fail-closed).

Every test here asserts an OBSERVABLE behavior of the gate: a typed outcome, a typed
refusal, or the byte-identity of two independent evaluations. No test reads a default
policy value, because none may exist (DEF4).
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from capture import CaptureService, CaptureStore, S1Service
from capture.retention import (
    DEF4_PENDING_LABEL,
    POLICY_VALUE_UNSPECIFIED,
    PURGE_EXECUTION_ALLOWED,
    PURGE_GATE_REASON_DEF4,
    RETENTION_BASES,
    RETENTION_BASIS_CREATED_AT,
    RETENTION_OUTCOME_DATA_ANOMALY,
    RETENTION_OUTCOME_ELIGIBLE,
    RETENTION_OUTCOME_INTEGRITY_DEFERRED,
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
from capture.model import CaptureState, IntegrityStatus

from wp13_helpers import (AGE_FROM_RECEIVED_AT, EVAL_TIME, POLICY_ID, PRIVACY_MARKING,
                          RECEIVED_AT, ingest_completed, policy)


@pytest.fixture()
def capture(tmp_path):
    store = CaptureStore(tmp_path / "capture.db")
    service = CaptureService(store, S1Service())
    yield store, service
    store.close()


# ---------------------------------------------------------------------------
# AC-1.3.1 — no policy value exists in the layer; absence is a typed refusal
# ---------------------------------------------------------------------------

def test_policy_has_no_usable_defaults():
    """Every policy field is mandatory: no TTL/duration/privacy value is baked in."""
    sig = inspect.signature(RetentionPolicy.__init__)
    for name, param in list(sig.parameters.items())[1:]:          # drop self
        assert param.default is inspect.Parameter.empty or param.default is None, (
            f"field {name!r} carries a default {param.default!r} — a default would be "
            f"an invented DEF4 policy value")
    assert RetentionPolicy.REQUIRED_FIELDS == tuple(
        name for name, p in list(sig.parameters.items())[1:])


def test_constructing_an_empty_policy_is_refused():
    with pytest.raises(RetentionPolicyIncomplete) as exc:
        RetentionPolicy.unsupplied()
    assert exc.value.missing == ("basis", "candidate_reporting", "cutoff_seconds",
                                 "policy_id", "privacy_marking")


@pytest.mark.parametrize("missing", ["policy_id", "basis", "cutoff_seconds",
                                    "privacy_marking", "candidate_reporting"])
def test_each_missing_field_alone_is_refused(missing):
    values = dict(policy_id=POLICY_ID, basis=RETENTION_BASIS_CREATED_AT,
                  cutoff_seconds=1000, privacy_marking=PRIVACY_MARKING,
                  candidate_reporting=True)
    values[missing] = None
    with pytest.raises(RetentionPolicyIncomplete) as exc:
        RetentionPolicy(**values)
    assert exc.value.missing == (missing,)


def test_unspecified_sentinel_is_not_a_value():
    """The sentinel marks absence — it never becomes a usable policy value."""
    with pytest.raises(RetentionPolicyIncomplete):
        RetentionPolicy(policy_id=POLICY_ID, basis=RETENTION_BASIS_CREATED_AT,
                        cutoff_seconds=POLICY_VALUE_UNSPECIFIED,
                        privacy_marking=PRIVACY_MARKING, candidate_reporting=True)


def test_policy_field_types_are_enforced_not_coerced():
    with pytest.raises(RetentionIllegalInput):
        RetentionPolicy(policy_id=POLICY_ID, basis="created_at", cutoff_seconds=True,
                        privacy_marking="A", candidate_reporting=True)     # bool is not a duration
    with pytest.raises(RetentionIllegalInput):
        RetentionPolicy(policy_id=POLICY_ID, basis="created_at", cutoff_seconds="3600",
                        privacy_marking="A", candidate_reporting=True)      # no string coercion
    with pytest.raises(RetentionIllegalInput):
        RetentionPolicy(policy_id=POLICY_ID, basis="created_at", cutoff_seconds=-1,
                        privacy_marking="A", candidate_reporting=True)      # negative window
    with pytest.raises(RetentionIllegalInput):
        RetentionPolicy(policy_id="", basis="created_at", cutoff_seconds=1,
                        privacy_marking="A", candidate_reporting=True)      # empty label
    with pytest.raises(RetentionIllegalInput):
        RetentionPolicy(policy_id=POLICY_ID, basis="modified_at", cutoff_seconds=1,
                        privacy_marking="A", candidate_reporting=True)     # unknown basis
    with pytest.raises(RetentionIllegalInput):
        RetentionPolicy(policy_id=POLICY_ID, basis="created_at", cutoff_seconds=1,
                        privacy_marking="A", candidate_reporting="yes")    # non-bool switch
    assert RETENTION_BASES == frozenset({"created_at", "received_at"})


def test_evaluate_with_no_policy_object_is_a_typed_refusal(capture):
    store, service = capture
    cid = ingest_completed(service)
    decision = evaluate_retention(store.get_record(cid), policy=None,
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_POLICY_UNDECLARED
    assert decision.capture_id == cid
    assert "DEF4" in decision.detail
    # and a half-built policy can never reach the evaluator at all
    with pytest.raises(RetentionPolicyIncomplete):
        RetentionPolicy(policy_id=POLICY_ID)


def test_zero_cutoff_is_a_legitimate_injected_value_not_a_refusal(capture):
    """0 is accepted ONLY because the caller declared it — the layer proposes nothing."""
    store, service = capture
    cid = ingest_completed(service)
    decision = evaluate_retention(store.get_record(cid),
                                  policy=policy(cutoff_seconds=0),
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_ELIGIBLE
    assert decision.age_seconds == AGE_FROM_RECEIVED_AT


# ---------------------------------------------------------------------------
# AC-1.3.4 — evaluation is a pure function: injected instant only, no clock
# ---------------------------------------------------------------------------

def test_module_reads_no_clock():
    """AST probe: neither the gate nor the report may consult a wall clock."""
    import ast
    for filename in ("retention.py", "consistency.py"):
        source = (Path(__file__).resolve().parents[1] / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Attribute, ast.Name)):
                attr = getattr(node, "attr", None) or getattr(node, "id", None)
                assert attr not in {"now", "today", "utcnow", "time", "time_ns",
                                    "monotonic"}, f"{filename}:{node.lineno} reads a clock"


def test_evaluation_time_is_mandatory(capture):
    store, service = capture
    cid = ingest_completed(service)
    decision = evaluate_retention(store.get_record(cid), policy=policy(),
                                  evaluation_time=None)
    assert decision.outcome == RETENTION_OUTCOME_DATA_ANOMALY
    assert "clock" in decision.detail


def test_same_inputs_yield_identical_decisions(capture):
    store, service = capture
    cid = ingest_completed(service)
    record = store.get_record(cid)
    first = evaluate_retention(record, policy=policy(), evaluation_time=EVAL_TIME)
    second = evaluate_retention(record, policy=policy(), evaluation_time=EVAL_TIME)
    assert first == second
    assert first.to_canonical_dict() == second.to_canonical_dict()


def test_boundary_age_exactly_at_cutoff_is_eligible(capture):
    store, service = capture
    record = store.get_record(ingest_completed(service))
    decision = evaluate_retention(record, policy=policy(cutoff_seconds=AGE_FROM_RECEIVED_AT),
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_ELIGIBLE


def test_age_one_second_below_cutoff_is_not_eligible(capture):
    store, service = capture
    record = store.get_record(ingest_completed(service))
    decision = evaluate_retention(record, policy=policy(cutoff_seconds=AGE_FROM_RECEIVED_AT + 1),
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_NOT_ELIGIBLE
    assert decision.remaining_seconds == 1


def test_candidate_reporting_disabled_suppresses_the_candidate(capture):
    store, service = capture
    record = store.get_record(ingest_completed(service))
    decision = evaluate_retention(record,
                                  policy=policy(cutoff_seconds=1, candidate_reporting=False),
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_NOT_ELIGIBLE
    assert "candidate reporting" in decision.detail


def test_every_decision_carries_the_def4_pending_label(capture):
    store, service = capture
    record = store.get_record(ingest_completed(service))
    cases = [
        evaluate_retention(record, policy=None, evaluation_time=EVAL_TIME),
        evaluate_retention(record, policy=policy(), evaluation_time=None),
        evaluate_retention(record, policy=policy(), evaluation_time=EVAL_TIME),
        evaluate_retention(record, policy=policy(cutoff_seconds=10 ** 12),
                           evaluation_time=EVAL_TIME),
        request_purge(record.capture_id, policy=policy()),
    ]
    for decision in cases:
        assert decision.policy_status_label == DEF4_PENDING_LABEL


# ---------------------------------------------------------------------------
# AC-1.3.1 — fail-closed on non-terminal / non-trustworthy targets
# ---------------------------------------------------------------------------

def test_active_record_is_state_refused_not_assessed(capture):
    store, _ = capture
    rec = store.create_active(received_at=RECEIVED_AT)
    decision = evaluate_retention(store.get_record(rec.capture_id), policy=policy(),
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_STATE_REFUSED
    assert decision.age_seconds is None


def test_settled_failed_record_is_state_refused(capture):
    from capture.model import NOTE_CONTENT_MISSING
    store, _ = capture
    rec = store.create_active(received_at=RECEIVED_AT)
    store.settle_failed(rec.capture_id, NOTE_CONTENT_MISSING)
    decision = evaluate_retention(store.get_record(rec.capture_id), policy=policy(),
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_STATE_REFUSED


def test_completed_but_integrity_failed_is_deferred_to_review(capture):
    """Evidence conflict never becomes a retention candidate (REVIEW > guessing)."""
    store, service = capture
    cid = ingest_completed(service)
    store.record_verification(cid, "FAILED", "2026-10-11T00:00:00+00:00")
    record = store.get_record(cid)
    assert record.capture_state is CaptureState.COMPLETED
    assert record.integrity_status is IntegrityStatus.FAILED
    decision = evaluate_retention(record, policy=policy(cutoff_seconds=1),
                                  evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_INTEGRITY_DEFERRED
    assert "review" in decision.detail


@pytest.mark.parametrize("bad_time", [
    "2026-09-01",             # naive — no offset to trust
    "not-a-date", "", "   ",
    "2026-13-45T99:99:99+00:00",
    None, 12345, 3.5, [], {},
])
def test_unusable_timestamps_are_data_anomalies(capture, bad_time):
    """A naive or malformed instant is refused; it is never assumed UTC or assumed old.

    The anomaly is exercised at BOTH operand positions (record timestamp and injected
    evaluation instant) — either one alone must be enough to refuse the verdict.
    """
    from types import SimpleNamespace
    store, service = capture
    cid = ingest_completed(service, content=b"invoice.number=WP13-TS\n")
    record = SimpleNamespace(capture_id=cid, capture_state="COMPLETED",
                             integrity_status="VALID", received_at=bad_time,
                             created_at=RECEIVED_AT)
    assert evaluate_retention(record, policy=policy(),
                              evaluation_time=EVAL_TIME).outcome == RETENTION_OUTCOME_DATA_ANOMALY
    good = store.get_record(cid)
    assert evaluate_retention(good, policy=policy(),
                              evaluation_time=bad_time).outcome == RETENTION_OUTCOME_DATA_ANOMALY


def test_negative_age_is_anomaly_never_a_verdict(capture):
    store, service = capture
    cid = ingest_completed(service, content=b"invoice.number=WP13-NEG\n")
    record = store.get_record(cid)
    decision = evaluate_retention(record, policy=policy(cutoff_seconds=1),
                                  evaluation_time="2026-01-01T00:00:00+00:00")
    assert decision.outcome == RETENTION_OUTCOME_DATA_ANOMALY
    assert "negative age" in decision.detail


def test_non_record_input_is_refused_not_crashed():
    """A wrong type surfaces as an explicit refusal, never a silent pass."""
    from types import SimpleNamespace
    empty = SimpleNamespace()
    decision = evaluate_retention(empty, policy=policy(), evaluation_time=EVAL_TIME)
    assert decision.outcome == RETENTION_OUTCOME_STATE_REFUSED
    assert decision.capture_id is None


# ---------------------------------------------------------------------------
# Boundary discipline
# ---------------------------------------------------------------------------

def test_gate_module_contains_no_mutation_or_execution_surface():
    """AC-1.3.3 structural half: the gate has no delete/execute capability at all —
    not a function, not a SQL statement, not an import of a writer."""
    import ast
    import capture.retention as gate
    source = Path(gate.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert names == {"__post_init__", "unsupplied", "defaultless_field_names",
                     "to_canonical_dict", "parse_aware_iso", "is_aware_iso",
                     "__init__", "evaluate_retention", "request_purge"}, names
    forbidden = {"execute_purge", "purge_now", "delete", "delete_capture",
                 "physical_delete", "drop", "erase", "destroy", "shred", "vacuum"}
    assert names.isdisjoint(forbidden)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "dataclasses", "datetime", "typing", "inspect"}
    # Stronger than a keyword sweep: the module cannot touch storage or the filesystem
    # at all, because it holds no database/file handles and issues no execute call.
    assert "sqlite3" not in imported and "os" not in imported and "pathlib" not in imported
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                calls.add(node.func.id)
    assert calls.isdisjoint({"execute", "executescript", "executemany", "open", "remove",
                             "unlink", "rmtree", "truncate", "system", "popen"})


def test_purge_gate_is_closed_by_construction():
    assert PURGE_EXECUTION_ALLOWED is False
    assert DEF4_PENDING_LABEL in PURGE_GATE_REASON_DEF4
