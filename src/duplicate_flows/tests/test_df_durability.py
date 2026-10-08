"""WP-7.2 durability tests — the project store pattern applied to flow
dispositions: atomic single-row commit with zero residue on forced failure,
restart safety, the tamper matrix (own row + hash-consistent forged row +
tampered LINKED identity facts), CHECK/UNIQUE backstops via direct SQL, and
INV-DF-1:1 (SPEC §6/§7/§8; OD-DF2/DF3/DF5/DF6/DF7)."""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from df_helpers import (  # noqa: E402
    BINDING,
    REF_KEYS,
    FlowDuplicateRecognized,
    FlowIdentityEstablished,
    FlowInputIntegrityFailure,
    FlowReadIntegrityFailure,
    FlowReadSuccess,
    FlowReadVerificationUnavailable,
    FlowReprintRecognized,
    FlowStorageUnavailable,
    ORIGIN_HOLOO_CAPTURE,
    twin_pages,
    unique_ir_pages,
)

from duplicate_flows import (  # noqa: E402
    DispositionDuplicate,
    FlowDispositionRecord,
    FlowDispositionStore,
    FlowPersistenceUnavailable,
)
from capture import S1Service  # noqa: E402


def _project(stack, nid):
    return stack.project(nid, REF_KEYS, ruleset_id="kandoo-ir-rules",
                         ruleset_version="1")


# ---------------------------------------------------------------------------
# INV-DF-1:1 — in-transaction check + UNIQUE backstop (direct SQL)
# ---------------------------------------------------------------------------

def test_unique_capture_s1_backstop_rejects_a_second_disposition(stack):
    outcome, _ = stack.establish(label="df-dur-u1")
    duplicate = FlowDispositionRecord(
        disposition_id="different-bookkeeping-id",
        capture_s1=outcome.disposition.capture_s1,   # SAME S1 anchor
        capture_s1_algorithm_id=outcome.disposition.capture_s1_algorithm_id,
        capture_id=outcome.disposition.capture_id,
        document_id=outcome.disposition.document_id,
        resolution_id=outcome.disposition.resolution_id,
        original_resolution_id="",
        duplicate_observation_id="",
        declared_origin=outcome.disposition.declared_origin,
        flow_outcome="IDENTITY_ESTABLISHED",
        identity_scope=outcome.disposition.identity_scope,
        identity_fingerprint=outcome.disposition.identity_fingerprint,
        created_at=outcome.disposition.created_at,
        record_fingerprint="",
        fingerprint_algorithm_id="")
    with pytest.raises(DispositionDuplicate):
        stack.flow_store.commit_disposition(duplicate)
    assert len(stack.flow_store.list_dispositions()) == 1


def test_direct_sql_insert_of_a_second_row_is_rejected_by_the_unique_index(
        stack):
    outcome, _ = stack.establish(label="df-dur-u2")
    conn = sqlite3.connect(str(stack.flows_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO flow_dispositions (disposition_id, capture_s1,"
                " capture_s1_algorithm_id, capture_id, document_id,"
                " resolution_id, original_resolution_id,"
                " duplicate_observation_id, declared_origin, flow_outcome,"
                " identity_scope, identity_fingerprint, created_at,"
                " record_fingerprint, fingerprint_algorithm_id)"
                " VALUES ('x2', ?, 'alg', 'c', 'd', 'r', '', '',"
                " 'HOLOO_CAPTURE', 'IDENTITY_ESTABLISHED', 'S2', 'fp',"
                " 't', 'fp-x', 'sha256-v1')",
                (outcome.disposition.capture_s1,))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Storage CHECK gates via direct SQL (OD-DF6)
# ---------------------------------------------------------------------------

def test_direct_sql_check_gates_refuse_malformed_rows(stack):
    outcome, _ = stack.establish(label="df-dur-check")
    s1v = outcome.disposition.capture_s1
    cid = outcome.disposition.capture_id
    rid = outcome.disposition.resolution_id
    base = (s1v, cid, rid)
    bad_rows = [
        # REPRINT_RECOGNIZED is never storable
        f"INSERT INTO flow_dispositions (disposition_id, capture_s1,"
        f" capture_s1_algorithm_id, capture_id, document_id, resolution_id,"
        f" original_resolution_id, duplicate_observation_id,"
        f" declared_origin, flow_outcome, identity_scope,"
        f" identity_fingerprint, created_at, record_fingerprint,"
        f" fingerprint_algorithm_id) VALUES"
        f" ('c1', '{s1v}xa', 'alg', 'alg', '{cid}', '{rid}',"
        f" '', '', 'HOLOO_CAPTURE', 'REPRINT_RECOGNIZED', 'S2', 'fp',"
        f" 't', 'fp', 'sha256-v1')",
        # IDENTITY_ESTABLISHED with duplicate references
        f"INSERT INTO flow_dispositions (disposition_id, capture_s1,"
        f" capture_s1_algorithm_id, capture_id, document_id, resolution_id,"
        f" original_resolution_id, duplicate_observation_id,"
        f" declared_origin, flow_outcome, identity_scope,"
        f" identity_fingerprint, created_at, record_fingerprint,"
        f" fingerprint_algorithm_id) VALUES"
        f" ('c2', '{s1v}xb', 'alg', 'alg', '{cid}', '{rid}',"
        f" 'orig', 'obs', 'HOLOO_CAPTURE', 'IDENTITY_ESTABLISHED', 'S2',"
        f" 'fp', 't', 'fp', 'sha256-v1')",
        # DUPLICATE_RECOGNIZED without references
        f"INSERT INTO flow_dispositions (disposition_id, capture_s1,"
        f" capture_s1_algorithm_id, capture_id, document_id, resolution_id,"
        f" original_resolution_id, duplicate_observation_id,"
        f" declared_origin, flow_outcome, identity_scope,"
        f" identity_fingerprint, created_at, record_fingerprint,"
        f" fingerprint_algorithm_id) VALUES"
        f" ('c3', '{s1v}xc', 'alg', 'alg', '{cid}', '{rid}',"
        f" '', '', 'HOLOO_CAPTURE', 'DUPLICATE_RECOGNIZED', 'S2', 'fp',"
        f" 't', 'fp', 'sha256-v1')",
        # S2 scope with empty fingerprint
        f"INSERT INTO flow_dispositions (disposition_id, capture_s1,"
        f" capture_s1_algorithm_id, capture_id, document_id, resolution_id,"
        f" original_resolution_id, duplicate_observation_id,"
        f" declared_origin, flow_outcome, identity_scope,"
        f" identity_fingerprint, created_at, record_fingerprint,"
        f" fingerprint_algorithm_id) VALUES"
        f" ('c4', '{s1v}xd', 'alg', 'alg', '{cid}', '{rid}',"
        f" '', '', 'HOLOO_CAPTURE', 'IDENTITY_ESTABLISHED', 'S2', '',"
        f" 't', 'fp', 'sha256-v1')",
        # origin outside the frozen vocabulary
        f"INSERT INTO flow_dispositions (disposition_id, capture_s1,"
        f" capture_s1_algorithm_id, capture_id, document_id, resolution_id,"
        f" original_resolution_id, duplicate_observation_id,"
        f" declared_origin, flow_outcome, identity_scope,"
        f" identity_fingerprint, created_at, record_fingerprint,"
        f" fingerprint_algorithm_id) VALUES"
        f" ('c5', '{s1v}xe', 'alg', 'alg', '{cid}', '{rid}',"
        f" '', '', 'MY_POS', 'IDENTITY_ESTABLISHED', 'CAPTURE_SCOPED', '',"
        f" 't', 'fp', 'sha256-v1')",
    ]
    conn = sqlite3.connect(str(stack.flows_db))
    try:
        for sql in bad_rows:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)
        conn.commit()
    finally:
        conn.close()
    assert len(stack.flow_store.list_dispositions()) == 1


def test_python_side_commit_refusals_mirror_the_checks(stack):
    outcome, _ = stack.establish(label="df-dur-py")
    with pytest.raises(FlowPersistenceUnavailable):
        stack.flow_store.commit_disposition(FlowDispositionRecord(
            **{**outcome.disposition.__dict__,
               "disposition_id": "py-1",
               "capture_s1": outcome.disposition.capture_s1 + "py",
               "flow_outcome": "REPRINT_RECOGNIZED"}))
    with pytest.raises(FlowPersistenceUnavailable):
        stack.flow_store.commit_disposition(FlowDispositionRecord(
            **{**outcome.disposition.__dict__,
               "disposition_id": "py-2",
               "capture_s1": outcome.disposition.capture_s1 + "py",
               "declared_origin": "MY_POS"}))
    assert len(stack.flow_store.list_dispositions()) == 1


# ---------------------------------------------------------------------------
# Zero residue on forced failure (OD-DF2)
# ---------------------------------------------------------------------------

def test_forced_fingerprint_failure_leaves_zero_residue(stack):
    outcome, _ = stack.establish(label="df-dur-residue")
    from capture import S1ComputationFailure

    class FailingS1:
        def compute(self, *a, **k):
            raise S1ComputationFailure("forced")

        def verify(self, *a, **k):
            raise S1ComputationFailure("forced")

        @property
        def algorithm_id(self):
            return "sha256-v1"

        @property
        def supported_ids(self):
            return frozenset({"sha256-v1"})

    store = FlowDispositionStore(stack.flows_db, FailingS1())
    try:
        with pytest.raises(FlowPersistenceUnavailable):
            store.commit_disposition(FlowDispositionRecord(
                **{**outcome.disposition.__dict__,
                   "disposition_id": "forced-1",
                   "capture_s1": outcome.disposition.capture_s1 + "forced",
                   "created_at": "2026-10-08T00:00:00+00:00",
                   "record_fingerprint": "",
                   "fingerprint_algorithm_id": ""}))
    finally:
        store.close()
    conn = sqlite3.connect(str(stack.flows_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM flow_dispositions WHERE capture_s1 = ?",
            (outcome.disposition.capture_s1 + "forced",)).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


# ---------------------------------------------------------------------------
# Restart safety + tamper matrix (own row / linked resolution / original)
# ---------------------------------------------------------------------------

def test_dispositions_survive_a_restart_and_still_verify(make_stack):
    stack = make_stack()
    outcome, _ = stack.establish(label="df-dur-restart")
    twin = stack.handle_new(parts=twin_pages(),
                            label="df-dur-twin")
    assert isinstance(twin, FlowDuplicateRecognized)
    stack.close()

    reopened = make_stack()
    try:
        read = reopened.flows.read_disposition_by_id(
            outcome.disposition.disposition_id)
        assert isinstance(read, FlowReadSuccess)
        read2 = reopened.flows.read_disposition_by_id(
            twin.disposition.disposition_id)
        assert isinstance(read2, FlowReadSuccess)
        assert read2.original_resolution.resolution_id \
            == outcome.record.resolution_id
    finally:
        reopened.close()


def test_tampered_own_row_withholds_content(stack, make_stack):
    outcome, _ = stack.establish(label="df-dur-tamper-own")
    disposition_id = outcome.disposition.disposition_id
    stack.close()

    reopened = make_stack()
    try:
        conn = sqlite3.connect(str(reopened.flows_db))
        try:
            conn.execute("UPDATE flow_dispositions SET created_at = 'x' "
                         "WHERE disposition_id = ?", (disposition_id,))
            conn.commit()
        finally:
            conn.close()
        read = reopened.flows.read_disposition_by_id(disposition_id)
        assert isinstance(read, FlowReadIntegrityFailure)
    finally:
        reopened.close()


def test_hash_consistent_forged_row_is_withheld_by_structural_gates(
        stack, make_stack):
    """A forged row whose fingerprint is recomputed consistently still has
    to agree with the LINKED WP-7.1 resolution — the cross-store gates
    catch what the hash alone cannot."""
    outcome, _ = stack.establish(label="df-dur-forge")
    disposition_id = outcome.disposition.disposition_id
    stack.close()

    reopened = make_stack()
    try:
        conn = sqlite3.connect(str(reopened.flows_db))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM flow_dispositions WHERE disposition_id = ?",
                (disposition_id,)).fetchone()
            forged = FlowDispositionRecord(
                **{**{k: row[k] for k in row.keys()},
                   "document_id": "forged-doc",
                   "record_fingerprint": "",
                   "fingerprint_algorithm_id": ""})
            fp = reopened._s1 if hasattr(reopened, "_s1") else S1Service()
            from duplicate_flows import canonical_disposition_bytes
            computed = fp.compute(canonical_disposition_bytes(forged))
            conn.execute(
                "UPDATE flow_dispositions SET document_id = ?, "
                "record_fingerprint = ?, fingerprint_algorithm_id = ? "
                "WHERE disposition_id = ?",
                ("forged-doc", computed.s1, computed.s1_algorithm_id,
                 disposition_id))
            conn.commit()
        finally:
            conn.close()
        read = reopened.flows.read_disposition_by_id(disposition_id)
        assert isinstance(read, FlowReadVerificationUnavailable)
        assert "document_id drift" in read.issue_report
    finally:
        reopened.close()


def test_tampered_linked_resolution_withholds_the_disposition(
        stack, make_stack):
    """The flow layer never trusts the linked identity fact: a tampered
    WP-7.1 resolution row withholds the flow disposition (fail-closed)."""
    outcome, _ = stack.establish(label="df-dur-link")
    disposition_id = outcome.disposition.disposition_id
    stack.close()

    reopened = make_stack()
    try:
        conn = sqlite3.connect(str(reopened.identity_db))
        try:
            conn.execute("UPDATE identity_resolutions SET document_id = "
                         "'tampered' WHERE resolution_id = ?",
                         (outcome.record.resolution_id,))
            conn.commit()
        finally:
            conn.close()
        read = reopened.flows.read_disposition_by_id(disposition_id)
        assert isinstance(read, FlowReadIntegrityFailure)
        assert "linked resolution" in read.reason
    finally:
        reopened.close()


def test_tampered_original_withholds_a_duplicate_disposition(
        stack, make_stack):
    first, _ = stack.establish(label="df-dur-orig")
    twin = stack.handle_new(parts=twin_pages(),
                            label="df-dur-twin")
    assert isinstance(twin, FlowDuplicateRecognized)
    twin_disposition_id = twin.disposition.disposition_id
    original_resolution_id = first.record.resolution_id
    stack.close()

    reopened = make_stack()
    try:
        conn = sqlite3.connect(str(reopened.identity_db))
        try:
            conn.execute("UPDATE identity_resolutions SET document_id = "
                         "'tampered' WHERE resolution_id = ?",
                         (original_resolution_id,))
            conn.commit()
        finally:
            conn.close()
        read = reopened.flows.read_disposition_by_id(twin_disposition_id)
        assert isinstance(read, FlowReadIntegrityFailure)
    finally:
        reopened.close()
