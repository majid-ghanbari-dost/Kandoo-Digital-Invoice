"""WP-7.1 service tests — the fail-closed ladder, refusal matrix, storage
failure mapping, end-to-end flow, and concurrency (same identity ≠ multiple
identities, DB uniqueness as the final backstop) (SPEC §3/§4/§8; dispatch
§12/§13 axes)."""
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1ComputationFailure, S1Service  # noqa: E402

from ir_helpers import (  # noqa: E402
    BINDING,
    IdentityDefiniteDuplicate,
    IdentityInputIntegrityFailure,
    IdentityReplay,
    IdentityRequestRefused,
    IdentityResolutionRecorded,
    IdentityResolutionService,
    IdentityResolutionStack,
    IdentityStorageUnavailable,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_KANDOO_SALE,
    ORIGIN_OTHER_POS_CAPTURE,
    third_order_pages,
    twin_pages,
    unique_ir_pages,
)

from identity_resolution import (  # noqa: E402
    IDENTITY_SCOPE_S2,
    IdentityResolutionStore,
)


def _resolve(stack, state_id, origin=ORIGIN_HOLOO_CAPTURE, binding=None):
    return stack.identity.resolve(state_id, origin,
                                  BINDING if binding is None else binding)


# ---------------------------------------------------------------------------
# End-to-end: frozen pipeline → identity resolution
# ---------------------------------------------------------------------------

def test_e2e_pipeline_to_identity_resolution(stack):
    _, projection = stack.build_valid_identity_state(label="ir-svc-e2e")
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.identity_scope == IDENTITY_SCOPE_S2
    read = stack.identity.read_resolution(outcome.record.resolution_id)
    assert type(read).__name__ == "IdentityReadSuccess"
    assert len(read.role_rows) == 3


# ---------------------------------------------------------------------------
# Refusal matrix (V1/V3/V4 — every refusal explicit, zero residue)
# ---------------------------------------------------------------------------

def test_unknown_state_id_refused(stack):
    outcome = stack.identity.resolve("no-such-state", ORIGIN_HOLOO_CAPTURE,
                                     BINDING)
    assert isinstance(outcome, IdentityRequestRefused), outcome
    assert "no-such-domain-state-record" in outcome.detail


def test_unknown_origin_refused(stack):
    _, projection = stack.build_valid_identity_state(label="ir-svc-o1")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     "SOME_SHOP", BINDING)
    assert isinstance(outcome, IdentityRequestRefused), outcome
    assert "outside the frozen origin vocabulary" in outcome.detail


def test_native_flow_origin_refused(stack):
    _, projection = stack.build_valid_identity_state(label="ir-svc-o2")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_KANDOO_SALE, BINDING)
    assert isinstance(outcome, IdentityRequestRefused), outcome
    assert "native-flow" in outcome.detail


def test_refusals_leave_zero_residue(stack):
    _, projection = stack.build_valid_identity_state(label="ir-svc-res")
    for origin in ("SOME_SHOP", ORIGIN_KANDOO_SALE):
        stack.identity.resolve(projection.record.domain_state_id, origin,
                               BINDING)
    stack.identity.resolve(projection.record.domain_state_id,
                           ORIGIN_HOLOO_CAPTURE, {"INVOICE_NUMBER": "x"})
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM identity_resolutions").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


# ---------------------------------------------------------------------------
# Integrity + storage failure mapping
# ---------------------------------------------------------------------------

def test_v1_integrity_failure_surfaces(stack):
    _, projection = stack.build_valid_identity_state(label="ir-svc-v1")
    conn = sqlite3.connect(str(stack.vsm_db))
    try:
        conn.execute("UPDATE domain_state_records SET capture_id = 'x' "
                     "WHERE domain_state_id = ?",
                     (projection.record.domain_state_id,))
        conn.commit()
    finally:
        conn.close()
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityInputIntegrityFailure), outcome


def test_persistence_failure_maps_to_storage_unavailable(stack):
    _, projection = stack.build_valid_identity_state(label="ir-svc-store")

    class DeadS1(S1Service):
        def compute(self, content):
            raise S1ComputationFailure("dead capability")

    dead_store = IdentityResolutionStore(stack.identity_db, DeadS1())
    service = IdentityResolutionService(dead_store, stack.vsm, stack.norm,
                                        S1Service())
    try:
        outcome = service.resolve(projection.record.domain_state_id,
                                  ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, IdentityStorageUnavailable), outcome
    finally:
        dead_store.close()


def test_resolve_read_paths_are_explicit_outcomes(stack):
    _, projection = stack.build_valid_identity_state(label="ir-svc-read")
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityResolutionRecorded)
    ok = stack.identity.read_resolution(outcome.record.resolution_id)
    assert type(ok).__name__ == "IdentityReadSuccess"
    by_capture = stack.identity.read_resolution_by_capture(
        outcome.record.capture_s1)
    assert type(by_capture).__name__ == "IdentityReadSuccess"
    assert by_capture.record.resolution_id == outcome.record.resolution_id


# ---------------------------------------------------------------------------
# Concurrency — same identity ≠ multiple identities; the DB backstop is final
# ---------------------------------------------------------------------------

def test_concurrent_same_capture_yields_exactly_one_resolution(stack):
    """Eight threads race the resolution of the SAME capture — each with its
    OWN store connection and the SAME verified inputs (pre-read once in the
    main thread, held by inert stubs). BEGIN IMMEDIATE + the in-transaction
    check + the UNIQUE backstop leave exactly ONE durable resolution:
    same identity ≠ multiple identities, and the database — not a Python
    check — is the final arbiter."""
    _, projection = stack.build_valid_identity_state(label="ir-svc-cc1")
    state_id = projection.record.domain_state_id
    # verified inputs, read once (the frozen layers are consumed single-
    # threaded here exactly as they are in production)
    head = stack.vsm.read_domain_state(state_id)
    walk = stack.vsm.trace_domain_state(state_id)
    norm_read = stack.norm.read_normalization(projection.record.normalization_id)

    class _StaticDomain:
        def __init__(self):
            self.head, self.walk = head, walk

        def read_domain_state(self, domain_state_id):
            return self.head

        def trace_domain_state(self, domain_state_id):
            return self.walk

    class _StaticNorm:
        def __init__(self):
            self.read = norm_read

        def read_normalization(self, normalization_id):
            return self.read

    results = []
    lock = threading.Lock()

    def worker():
        store = IdentityResolutionStore(stack.identity_db, S1Service())
        service = IdentityResolutionService(store, _StaticDomain(),
                                            _StaticNorm(), S1Service())
        try:
            outcome = service.resolve(state_id, ORIGIN_HOLOO_CAPTURE,
                                      BINDING)
            with lock:
                results.append(type(outcome).__name__)
        finally:
            store.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("IdentityResolutionRecorded") == 1
    assert results.count("IdentityReplay") == 7
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM identity_resolutions").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_concurrent_store_commits_hit_the_unique_backstop(stack):
    """Store-level race: identical capture, separate connections, identical
    declared request — exactly one commit wins, the rest see the duplicate
    exception (the DB backstop, not a Python check)."""
    from identity_resolution import IdentityResolutionRecord, \
        ResolutionDuplicate, utc_now_iso
    record_template = IdentityResolutionRecord(
        resolution_id="", capture_s1="race-s1",
        capture_s1_algorithm_id="sha256-v1", capture_id="c", document_id="d",
        extraction_id="e", normalization_id="n", domain_state_id="ds",
        declared_origin="HOLOO_CAPTURE", binding_declaration_fingerprint="",
        identity_scope="CAPTURE_SCOPED",
        identity_source="", identity_fingerprint="",
        scope_reason="s2-not-attempted-state-not-valid",
        created_at=utc_now_iso(), record_fingerprint="",
        fingerprint_algorithm_id="")
    outcomes = []
    errors = []
    lock = threading.Lock()

    def worker(i):
        store = IdentityResolutionStore(stack.identity_db, S1Service())
        try:
            record = IdentityResolutionRecord(
                **{**record_template.__dict__,
                   "resolution_id": f"race-{i}"})
            store.commit_resolution(record, (), None)
            with lock:
                outcomes.append(record.resolution_id)
        except ResolutionDuplicate as exc:
            with lock:
                errors.append(exc.existing_id)
        except Exception as exc:                       # noqa: BLE001
            with lock:
                errors.append(str(exc))
        finally:
            store.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(outcomes) == 1
    assert len(errors) == 7
    assert set(errors) == set(outcomes)   # every loser saw THE winner's id
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM identity_resolutions").fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_concurrent_duplicate_captures_keep_one_document_identity(stack):
    """Three different captures sharing one exact S2 identity race their
    resolution (own store connections, verified inputs pre-read) — every
    later capture records its duplicate observation against the SAME
    earliest original; one document identity total."""
    _, p1 = stack.build_valid_identity_state(label="ir-svc-cc3-1")
    first = _resolve(stack, p1.record.domain_state_id)
    assert isinstance(first, IdentityResolutionRecorded)
    twins = []
    for label in ("ir-svc-cc3-t1", "ir-svc-cc3-t2"):
        _, projection = stack.build_valid_identity_state(
            parts=twin_pages() if label.endswith("t1")
            else third_order_pages(), label=label)
        head = stack.vsm.read_domain_state(
            projection.record.domain_state_id)
        walk = stack.vsm.trace_domain_state(
            projection.record.domain_state_id)
        norm_read = stack.norm.read_normalization(
            projection.record.normalization_id)
        twins.append((projection.record.domain_state_id, head, walk,
                      norm_read))

    class _StaticDomain:
        def __init__(self, head, walk):
            self.head, self.walk = head, walk

        def read_domain_state(self, domain_state_id):
            return self.head

        def trace_domain_state(self, domain_state_id):
            return self.walk

    class _StaticNorm:
        def __init__(self, read):
            self.read = read

        def read_normalization(self, normalization_id):
            return self.read

    results = []
    originals = []
    lock = threading.Lock()

    def worker(payload):
        state_id, head, walk, norm_read = payload
        store = IdentityResolutionStore(stack.identity_db, S1Service())
        service = IdentityResolutionService(store, _StaticDomain(head, walk),
                                            _StaticNorm(norm_read),
                                            S1Service())
        try:
            outcome = service.resolve(state_id, ORIGIN_HOLOO_CAPTURE,
                                      BINDING)
            with lock:
                results.append(type(outcome).__name__)
                if getattr(outcome, "observation", None) is not None:
                    originals.append(outcome.observation
                                     .original_resolution_id)
        finally:
            store.close()

    threads = [threading.Thread(target=worker, args=(payload,))
               for payload in twins]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == ["IdentityDefiniteDuplicate",
                       "IdentityDefiniteDuplicate"]
    assert set(originals) == {first.record.resolution_id}
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        fingerprints = {r[0] for r in conn.execute(
            "SELECT DISTINCT identity_fingerprint FROM "
            "identity_resolutions WHERE identity_fingerprint != ''")}
    finally:
        conn.close()
    assert len(fingerprints) == 1      # ONE document identity


def test_repeated_sequential_resolutions_are_stable(stack):
    _, projection = stack.build_valid_identity_state(label="ir-svc-rep")
    first = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(first, IdentityResolutionRecorded)
    for _ in range(5):
        outcome = _resolve(stack, projection.record.domain_state_id)
        assert isinstance(outcome, IdentityReplay)
        assert outcome.record == first.record
    assert len(stack.identity_store.list_resolutions()) == 1
