"""WP-7.1 durability tests — atomic commit, zero residue, restart safety,
tamper detection matrix, SQL CHECK/UNIQUE backstops, immutability (SPEC §8;
dispatch §12 forged-row/corrupted-hash/partial-failure/restart axes)."""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1ComputationFailure, S1Service  # noqa: E402

from ir_helpers import (  # noqa: E402
    BINDING,
    IdentityInputIntegrityFailure,
    IdentityReplay,
    IdentityResolutionRecorded,
    IdentityResolutionStack,
    IdentityStorageUnavailable,
    ORIGIN_HOLOO_CAPTURE,
    twin_pages,
    unique_ir_pages,
)

from identity_resolution import (  # noqa: E402
    IdentityReadIntegrityFailure,
    IdentityReadRefused,
    IdentityReadSuccess,
    IdentityReadVerificationUnavailable,
    IdentityResolutionService,
    IdentityResolutionStore,
    ResolutionNotFound,
)

IDENTITY_TABLES = ("identity_resolutions", "identity_role_candidates",
                   "identity_duplicate_observations")


def _identity_rows(stack):
    counts = {}
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        for table in IDENTITY_TABLES:
            counts[table] = conn.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()
    return counts


def _resolve(stack, state_id):
    return stack.identity.resolve(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)


def _recording(stack, label="ir-dur"):
    _, projection = stack.build_valid_identity_state(label=label)
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityResolutionRecorded), outcome
    return outcome


def _duplicate_pair(stack, label="ir-dur-dup"):
    _, p1 = stack.build_valid_identity_state(label=label + "-1")
    first = _resolve(stack, p1.record.domain_state_id)
    assert isinstance(first, IdentityResolutionRecorded)
    _, p2 = stack.build_valid_identity_state(parts=twin_pages(),
                                             label=label + "-2")
    outcome = _resolve(stack, p2.record.domain_state_id)
    assert type(outcome).__name__ == "IdentityDefiniteDuplicate", outcome
    return first, outcome


# ---------------------------------------------------------------------------
# Atomic commit — everything rides one transaction, zero residue on failure
# ---------------------------------------------------------------------------

def test_resolution_commit_is_complete(stack):
    outcome = _recording(stack, label="ir-dur-atomic")
    counts = _identity_rows(stack)
    assert counts["identity_resolutions"] == 1
    assert counts["identity_role_candidates"] == 3
    assert counts["identity_duplicate_observations"] == 0


def test_duplicate_commit_carries_resolution_roles_and_observation(stack):
    first, dup = _duplicate_pair(stack, label="ir-dur-atomic2")
    counts = _identity_rows(stack)
    assert counts["identity_resolutions"] == 2
    assert counts["identity_role_candidates"] == 6
    assert counts["identity_duplicate_observations"] == 1


def test_forced_mid_commit_failure_leaves_zero_residue(stack):
    """The observation fingerprint is anchored AFTER the resolution rows are
    inserted — a capability failure there must roll the WHOLE commit back."""
    _, p1 = stack.build_valid_identity_state(label="ir-dur-res-1")
    assert isinstance(_resolve(stack, p1.record.domain_state_id),
                      IdentityResolutionRecorded)
    _, p2 = stack.build_valid_identity_state(parts=twin_pages(),
                                             label="ir-dur-res-2")

    class BrokenS1(S1Service):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def compute(self, content):
            self.calls += 1
            if self.calls >= 2:      # 1st = resolution fp, 2nd = observation
                raise S1ComputationFailure("injected capability failure")
            return super().compute(content)

    broken_store = IdentityResolutionStore(stack.identity_db, BrokenS1())
    service = IdentityResolutionService(broken_store, stack.vsm, stack.norm,
                                        S1Service())
    outcome = service.resolve(p2.record.domain_state_id, ORIGIN_HOLOO_CAPTURE,
                              BINDING)
    assert isinstance(outcome, IdentityStorageUnavailable), outcome
    broken_store.close()
    assert _identity_rows(stack) == {
        "identity_resolutions": 1,
        "identity_role_candidates": 3,
        "identity_duplicate_observations": 0}
    # a clean retry succeeds — the capture is NOT burned by the failure
    retry = _resolve(stack, p2.record.domain_state_id)
    assert type(retry).__name__ == "IdentityDefiniteDuplicate", retry


def test_storage_failure_on_first_fingerprint_leaves_zero_residue(stack):
    _, projection = stack.build_valid_identity_state(label="ir-dur-res-3")

    class DeadS1(S1Service):
        def compute(self, content):
            raise S1ComputationFailure("dead capability")

    dead_store = IdentityResolutionStore(stack.identity_db, DeadS1())
    service = IdentityResolutionService(dead_store, stack.vsm, stack.norm,
                                        S1Service())
    outcome = service.resolve(projection.record.domain_state_id,
                              ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, IdentityStorageUnavailable), outcome
    dead_store.close()
    assert _identity_rows(stack) == {
        "identity_resolutions": 0,
        "identity_role_candidates": 0,
        "identity_duplicate_observations": 0}


# ---------------------------------------------------------------------------
# Restart safety
# ---------------------------------------------------------------------------

def test_restart_reopen_read_verify_and_replay(make_stack):
    stack = make_stack()
    try:
        outcome = _recording(stack, label="ir-dur-restart")
        resolution_id = outcome.record.resolution_id
    finally:
        stack.close()
    reopened = make_stack()
    try:
        read = reopened.identity.read_resolution(resolution_id)
        assert isinstance(read, IdentityReadSuccess)
        assert read.record.resolution_id == resolution_id
        outcome = _resolve(reopened, read.record.domain_state_id)
        assert isinstance(outcome, IdentityReplay)
        assert outcome.record.record_fingerprint != ""
    finally:
        reopened.close()


def test_genuinely_fresh_database_is_empty(make_stack, tmp_path):
    stack = make_stack()
    try:
        _recording(stack, label="ir-dur-fresh")
    finally:
        stack.close()
    base = tmp_path / "fresh"
    base.mkdir()
    fresh = IdentityResolutionStack(
        base / "capture.db", base / "recon.db", base / "extraction.db",
        base / "bindings.db", base / "norm.db", base / "deriv.db",
        base / "val.db", base / "vsm.db", base / "identity.db")
    try:
        assert fresh.identity_store.list_resolutions() == []
    finally:
        fresh.close()


# ---------------------------------------------------------------------------
# Verify-on-Read — the tamper matrix (content withheld, never served)
# ---------------------------------------------------------------------------

def _tamper(stack, sql, params):
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def test_tampered_resolution_content_is_withheld(stack):
    """A content anchor outside the CHECK gates is tampered → the record
    hash no longer matches → content withheld."""
    outcome = _recording(stack, label="ir-dur-tamper1")
    _tamper(stack, "UPDATE identity_resolutions SET capture_id = "
                   "'tampered' WHERE resolution_id = ?",
            (outcome.record.resolution_id,))
    read = stack.identity.read_resolution(outcome.record.resolution_id)
    assert isinstance(read, IdentityReadIntegrityFailure), read


def test_check_gates_refuse_scope_reason_tamper_of_an_s2_row(stack):
    """The SQL CHECKs refuse even the TAMPER of an S2 row's reason — the
    database itself defends the frozen scope shape."""
    outcome = _recording(stack, label="ir-dur-tamper1b")
    with pytest.raises(sqlite3.IntegrityError):
        _tamper(stack, "UPDATE identity_resolutions SET scope_reason = "
                       "'s2-not-attempted-state-not-valid' WHERE "
                       "resolution_id = ?", (outcome.record.resolution_id,))


def test_corrupted_record_hash_is_withheld(stack):
    outcome = _recording(stack, label="ir-dur-tamper2")
    _tamper(stack, "UPDATE identity_resolutions SET record_fingerprint = "
                   "'0' * 64 WHERE resolution_id = ?",
            (outcome.record.resolution_id,))
    read = stack.identity.read_resolution(outcome.record.resolution_id)
    assert isinstance(read, IdentityReadIntegrityFailure), read


def test_tampered_role_row_is_withheld(stack):
    outcome = _recording(stack, label="ir-dur-tamper3")
    _tamper(stack, "UPDATE identity_role_candidates SET source_field_name "
                   "= 'tampered' WHERE resolution_id = ? AND role = "
                   "'INVOICE_DATE'", (outcome.record.resolution_id,))
    read = stack.identity.read_resolution(outcome.record.resolution_id)
    assert isinstance(read, IdentityReadIntegrityFailure), read


def test_check_gates_refuse_candidate_count_tamper(stack):
    """candidate_count=2 with a resolved pointer violates the role-row CHECK
    — the tamper is refused at the SQL level."""
    outcome = _recording(stack, label="ir-dur-tamper3b")
    with pytest.raises(sqlite3.IntegrityError):
        _tamper(stack, "UPDATE identity_role_candidates SET "
                       "candidate_count = 2 WHERE resolution_id = ? AND "
                       "role = 'INVOICE_DATE'",
                (outcome.record.resolution_id,))


def test_tampered_observation_is_withheld(stack):
    first, dup = _duplicate_pair(stack, label="ir-dur-tamper4")
    _tamper(stack, "UPDATE identity_duplicate_observations SET "
                   "original_capture_s1 = 'forged' WHERE resolution_id = ?",
            (dup.record.resolution_id,))
    read = stack.identity.read_resolution(dup.record.resolution_id)
    assert isinstance(read, IdentityReadIntegrityFailure), read


def test_forged_resolution_row_is_detected(stack):
    """A row hand-inserted with a self-consistent-looking but forged
    fingerprint cannot serve content: the hash is wrong AND the durable-set
    shape is impossible."""
    _recording(stack, label="ir-dur-forge1")
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        conn.execute(
            """INSERT INTO identity_resolutions (
                   resolution_id, capture_s1, capture_s1_algorithm_id,
                   capture_id, document_id, extraction_id, normalization_id,
                   domain_state_id, declared_origin,
                   binding_declaration_fingerprint, identity_scope,
                   identity_source, identity_fingerprint, scope_reason,
                   created_at, record_fingerprint, fingerprint_algorithm_id)
               VALUES ('forged-1', 'forgeS1', 'sha256-v1', 'c', 'd', 'e',
                       'n', 'ds', 'HOLOO_CAPTURE', '', 'S2',
                       'S2_EXTRACTED_VERIFIED', 'fp', '', '2026-01-01',
                       'forged-fp', 'sha256-v1')""")
        conn.commit()
    finally:
        conn.close()
    read = stack.identity.read_resolution("forged-1")
    assert isinstance(read, (IdentityReadIntegrityFailure,
                             IdentityReadVerificationUnavailable)), read


def test_structural_gate_catches_a_hash_consistent_forged_s2_row(stack):
    """A forger can re-hash a row, but not the MISSING evidence: an S2 row
    whose fingerprint is correctly computed over its own (role-less) bytes
    is caught by the durable-set structural gate."""
    from identity_resolution import (
        IdentityResolutionRecord,
        canonical_resolution_bytes,
    )
    _recording(stack, label="ir-dur-forge3")
    forged = IdentityResolutionRecord(
        resolution_id="forge-2", capture_s1="forgeS1b",
        capture_s1_algorithm_id="sha256-v1", capture_id="c",
        document_id="d", extraction_id="e", normalization_id="n",
        domain_state_id="ds", declared_origin="HOLOO_CAPTURE",
        binding_declaration_fingerprint="", identity_scope="S2",
        identity_source="S2_EXTRACTED_VERIFIED",
        identity_fingerprint="f" * 64, scope_reason="",
        created_at="2026-10-08T00:00:00+00:00", record_fingerprint="",
        fingerprint_algorithm_id="sha256-v1")
    fp = stack.identity_store._s1.compute(
        canonical_resolution_bytes(forged, [])).s1
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        conn.execute(
            """INSERT INTO identity_resolutions (
                   resolution_id, capture_s1, capture_s1_algorithm_id,
                   capture_id, document_id, extraction_id, normalization_id,
                   domain_state_id, declared_origin,
                   binding_declaration_fingerprint, identity_scope,
                   identity_source, identity_fingerprint, scope_reason,
                   created_at, record_fingerprint, fingerprint_algorithm_id)
               VALUES ('forge-2', 'forgeS1b', 'sha256-v1', 'c', 'd', 'e',
                       'n', 'ds', 'HOLOO_CAPTURE', '', 'S2',
                       'S2_EXTRACTED_VERIFIED', ?, '',
                       '2026-10-08T00:00:00+00:00', ?, 'sha256-v1')""",
            (forged.identity_fingerprint, fp))
        conn.commit()
    finally:
        conn.close()
    read = stack.identity.read_resolution("forge-2")
    assert isinstance(read, IdentityReadVerificationUnavailable), read
    assert "inconsistent" in read.issue_report


def test_unknown_resolution_read_is_refused(stack):
    refused = stack.identity.read_resolution("no-such-id")
    assert isinstance(refused, IdentityReadRefused)
    with pytest.raises(ResolutionNotFound):
        stack.identity_store.get_resolution("no-such-id")
    by_capture = stack.identity.read_resolution_by_capture("no-such-s1")
    assert isinstance(by_capture, IdentityReadRefused)


# ---------------------------------------------------------------------------
# SQL CHECK + UNIQUE backstops (the database is the final safety net)
# ---------------------------------------------------------------------------

def _raw_insert_resolution(stack, **overrides):
    row = {
        "resolution_id": "raw-1", "capture_s1": "rawS1",
        "capture_s1_algorithm_id": "sha256-v1", "capture_id": "c",
        "document_id": "d", "extraction_id": "e", "normalization_id": "n",
        "domain_state_id": "ds", "declared_origin": "HOLOO_CAPTURE",
        "binding_declaration_fingerprint": "", "identity_scope": "S2",
        "identity_source": "S2_EXTRACTED_VERIFIED",
        "identity_fingerprint": "f" * 64, "scope_reason": "",
        "created_at": "2026-10-08T00:00:00+00:00",
        "record_fingerprint": "r" * 64,
        "fingerprint_algorithm_id": "sha256-v1"}
    row.update(overrides)
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        conn.execute(
            """INSERT INTO identity_resolutions (
                   resolution_id, capture_s1, capture_s1_algorithm_id,
                   capture_id, document_id, extraction_id, normalization_id,
                   domain_state_id, declared_origin,
                   binding_declaration_fingerprint, identity_scope,
                   identity_source, identity_fingerprint, scope_reason,
                   created_at, record_fingerprint, fingerprint_algorithm_id)
               VALUES (:resolution_id, :capture_s1,
                       :capture_s1_algorithm_id, :capture_id, :document_id,
                       :extraction_id, :normalization_id, :domain_state_id,
                       :declared_origin, :binding_declaration_fingerprint,
                       :identity_scope, :identity_source,
                       :identity_fingerprint, :scope_reason, :created_at,
                       :record_fingerprint, :fingerprint_algorithm_id)""",
            row)
        conn.commit()
    finally:
        conn.close()


def test_unique_backstop_refuses_second_resolution_for_one_capture(stack):
    _recording(stack, label="ir-dur-uq1")
    outcome = _recording(stack, label="ir-dur-uq2")
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_resolution(stack, resolution_id="raw-dup",
                               capture_s1=outcome.record.capture_s1)


def test_sql_check_refuses_origin_outside_the_frozen_vocabulary(stack):
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_resolution(stack, declared_origin="SOME_SHOP")


def test_sql_check_refuses_scope_fingerprint_mismatch(stack):
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_resolution(stack, identity_scope="CAPTURE_SCOPED",
                               identity_fingerprint="f" * 64)


def test_sql_check_refuses_s2_with_empty_fingerprint(stack):
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_resolution(stack, identity_fingerprint="")


def test_sql_check_refuses_resolved_pointer_on_zero_candidates(stack):
    _recording(stack, label="ir-dur-check5")
    outcome = stack.identity_store.list_resolutions()[0]
    with pytest.raises(sqlite3.IntegrityError):
        _tamper(stack, "UPDATE identity_role_candidates SET "
                       "candidate_count = 0, resolved_field_seq = 0 WHERE "
                       "resolution_id = ?",
                (outcome.resolution_id,))


def test_sql_check_refuses_observation_with_same_capture(stack):
    _recording(stack, label="ir-dur-check6")
    rec = stack.identity_store.list_resolutions()[0]
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO identity_duplicate_observations (
                       observation_id, resolution_id,
                       original_resolution_id, identity_fingerprint,
                       original_capture_s1, duplicate_capture_s1,
                       created_at, observation_fingerprint,
                       fingerprint_algorithm_id)
                   VALUES ('obs-1', ?, ?, 'fp', ?, ?, 't', 'o', 'sha256-v1')""",
                (rec.resolution_id, rec.resolution_id, rec.capture_s1,
                 rec.capture_s1))
            conn.commit()
    finally:
        conn.close()


def test_unique_backstop_refuses_second_observation_per_resolution(stack):
    first, dup = _duplicate_pair(stack, label="ir-dur-check7")
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO identity_duplicate_observations (
                       observation_id, resolution_id,
                       original_resolution_id, identity_fingerprint,
                       original_capture_s1, duplicate_capture_s1,
                       created_at, observation_fingerprint,
                       fingerprint_algorithm_id)
                   VALUES ('obs-x', ?, ?, 'fp', ?, ?, 't', 'o', 'sha256-v1')""",
                (dup.record.resolution_id, first.record.resolution_id,
                 first.record.capture_s1, dup.record.capture_s1))
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Immutability — the layer has no mutation surface (behavioral complement to
# the AST proofs in the boundary suite)
# ---------------------------------------------------------------------------

def test_store_has_no_update_or_delete_surface():
    store_methods = {name for name in dir(IdentityResolutionStore)
                     if not name.startswith("__")}
    service_methods = {name for name in dir(IdentityResolutionService)
                       if not name.startswith("_")}
    for forbidden in ("update", "delete", "remove", "mutate", "amend",
                      "rewrite", "drop"):
        assert not any(name.startswith(forbidden)
                       for name in store_methods), forbidden
        assert not any(name.startswith(forbidden)
                       for name in service_methods), forbidden


def test_identity_rows_cannot_silently_vanish_via_service(stack):
    outcome = _recording(stack, label="ir-dur-immutable")
    before = _identity_rows(stack)
    # every read-path entry leaves the durable set untouched
    stack.identity.read_resolution(outcome.record.resolution_id)
    stack.identity.read_resolution_by_capture(outcome.record.capture_s1)
    _resolve(stack, outcome.record.domain_state_id)
    assert _identity_rows(stack) == before
