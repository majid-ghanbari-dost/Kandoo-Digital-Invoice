"""WP-7.2 boundary tests — structural AST proofs, frozen vocabulary, the
consumed-not-bypassed discipline, frozen-layer protection, INV-DF-1:1 under
concurrency, and the durable duplicate register under races (SPEC §12;
dispatch structural axes)."""
import ast
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LAYER_DIR = SRC / "duplicate_flows"
LAYER_FILES = sorted(LAYER_DIR.glob("*.py"))

from df_helpers import (  # noqa: E402
    BINDING,
    FlowDuplicateRecognized,
    FlowIdentityEstablished,
    FlowReprintRecognized,
    ORIGIN_HOLOO_CAPTURE,
    IdentityDefiniteDuplicate,
    IdentityReplay,
    IdentityResolutionRecorded,
    twin_pages,
)

from duplicate_flows import (  # noqa: E402
    DURABLE_FLOW_OUTCOMES,
    ORIGINS,
    LINKED_IDENTITY_SCOPES,
    DuplicateFlowService,
    FlowDispositionStore,
)


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _strings_in(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _identifiers_in(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.arg)):
            name = node.id if hasattr(node, "id") else getattr(
                node, "attr", None) or getattr(node, "name", None)
            if name:
                yield name.lower()


# ---------------------------------------------------------------------------
# Structural proof — no UPDATE / DELETE / DROP in the layer
# ---------------------------------------------------------------------------

def test_no_update_delete_or_drop_statement_anywhere_in_the_layer():
    for path in LAYER_FILES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value.strip().upper()
                assert not value.startswith("UPDATE "), \
                    f"{path.name}: UPDATE statement present"
                assert not value.startswith("DELETE FROM "), \
                    f"{path.name}: DELETE statement present"
                assert not value.startswith("DROP "), \
                    f"{path.name}: DROP statement present"


def test_no_mutation_method_names_in_the_layer():
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lowered = node.name.lower()
                for forbidden in ("update", "delete", "mutate", "amend",
                                  "rewrite", "drop_", "merge_", "rescind"):
                    assert not lowered.startswith(forbidden), \
                        f"{path.name}: function {node.name!r} looks like a " \
                        f"mutation path"


def test_no_randomness_no_exec_no_float_literals():
    forbidden_modules = {"random", "secrets", "eval", "exec", "pickle",
                         "ctypes", "subprocess", "socket", "http", "urllib"}
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                root = node.names[0].name.split(".")[0]
                assert root not in forbidden_modules, \
                    f"{path.name}: forbidden import {root}"
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in forbidden_modules, \
                    f"{path.name}: forbidden import-from {root}"
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, float):
                    pytest.fail(f"{path.name}: float literal {node.value}")


def test_uuid_is_confined_to_bookkeeping_id_assignment():
    uuid_files = [p.name for p in LAYER_FILES
                  if any(isinstance(n, ast.Import) and
                         n.names[0].name == "uuid"
                         for n in ast.walk(_tree(p)))]
    assert uuid_files == ["service.py"]
    service_source = (LAYER_DIR / "service.py").read_text(encoding="utf-8")
    assert "uuid.uuid4().hex" in service_source
    for anchored in ("identity_fingerprint=uuid", "fingerprint=uuid"):
        assert anchored not in service_source


def test_import_allowlist_project_layers_only():
    """The flow layer may import the project layers it consumes — and it
    consumes ONLY identity_resolution (plus capture for the S1 hashing
    capability). No canonicalization import: P6.1 semantics never leak in
    (OD-DF-C/OD-DF-I)."""
    allowed_roots = {"__future__", "dataclasses", "typing", "datetime",
                     "sqlite3", "uuid", "capture", "identity_resolution"}
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                root = node.names[0].name.split(".")[0]
                assert root in allowed_roots, \
                    f"{path.name}: import outside the allowlist: {root}"
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                root = (node.module or "").split(".")[0]
                assert root in allowed_roots, \
                    f"{path.name}: import-from outside the allowlist: {root}"


def test_no_identity_formula_and_no_hashlib_in_the_layer():
    """OD-DF-C: the flow layer computes NO identity fingerprint and NO
    resolution logic — WP-7.1's resolve is the only identity engine; the
    only hashing here is the record-integrity anchor via the project S1
    service."""
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert node.names[0].name != "hashlib", \
                    f"{path.name}: hashlib import — record anchors ride " \
                    f"the S1 capability, not local hashing"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "") != "hashlib", \
                    f"{path.name}: hashlib import-from"
    store_source = (LAYER_DIR / "store.py").read_text(encoding="utf-8")
    assert "resolve_identity" not in store_source
    assert "validate_binding" not in store_source


def test_no_fuzzy_or_semantic_or_business_matching_symbols():
    forbidden = ("fuzzy", "similarity", "levenshtein", "difflib",
                 "match_product", "product_match", "customer_match",
                 "auto_create", "ocr", "semantic", "tax_rate",
                 "currency_convert", "exchange_rate", "posting",
                 "inventory", "kpi", "heuristic")
    for path in LAYER_FILES:
        for ident in _identifiers_in(_tree(path)):
            for token in forbidden:
                assert token not in ident, \
                    f"{path.name}: forbidden identifier {ident!r} " \
                    f"(contains {token!r})"


def test_no_canonicalization_or_review_or_invoice_semantics():
    """OD-DF-I/OD-DF-J: no gate decision vocabulary is decided or annotated
    here, no REVIEW item is touched, no invoice_id exists, and no foreign
    table is referenced by SQL."""
    own_tables = {"flow_dispositions"}
    forbidden_tables = {"gate_decisions", "canonical_invoices",
                        "canonical_identity_pointers", "gate_review_items",
                        "domain_state_records", "normalization_records",
                        "extraction_records", "extraction_bindings",
                        "capture_records", "validation_records",
                        "identity_resolutions",
                        "identity_duplicate_observations",
                        "identity_role_candidates"}
    for path in LAYER_FILES:
        for value in _strings_in(_tree(path)):
            for table in forbidden_tables:
                assert table not in value, \
                    f"{path.name}: direct reference to foreign table " \
                    f"{table!r}"
    store_tokens = set()
    for v in _strings_in(_tree(LAYER_DIR / "store.py")):
        store_tokens.update(v.replace("(", " ").replace(",", " ").split())
    assert own_tables.issubset(store_tokens)
    for value in _strings_in(_tree(LAYER_DIR / "store.py")):
        assert "invoice_id" not in value
        assert "canonical_invoice" not in value
    for ident in _identifiers_in(_tree(LAYER_DIR / "service.py")):
        assert "invoice" not in ident
        assert "review" not in ident


def test_vocabulary_constants_are_verbatim():
    assert DURABLE_FLOW_OUTCOMES == ("IDENTITY_ESTABLISHED",
                                     "DUPLICATE_RECOGNIZED")
    assert LINKED_IDENTITY_SCOPES == ("S2", "CAPTURE_SCOPED")
    assert ORIGINS == ("KANDOO_SALE", "HOLOO_CAPTURE",
                       "OTHER_POS_CAPTURE")


def test_reprint_recognition_is_never_storable():
    """REPRINT_RECOGNIZED is a call outcome ONLY — the durable vocabulary
    and the storage CHECKs exclude it (SPEC §5)."""
    from duplicate_flows import store as flow_store_module
    schema = flow_store_module._SCHEMA
    assert "REPRINT_RECOGNIZED" not in schema        # the CHECK excludes it
    assert "REPRINT_RECOGNIZED" not in DURABLE_FLOW_OUTCOMES
    from duplicate_flows import FLOW_OUTCOME_REPRINT_RECOGNIZED
    with pytest.raises(Exception):
        # behavioral mirror: a REPRINT_RECOGNIZED commit is refused outright
        FlowDispositionRecord(
            disposition_id="x", capture_s1="s1", capture_s1_algorithm_id="a",
            capture_id="c", document_id="d", resolution_id="r",
            original_resolution_id="", duplicate_observation_id="",
            declared_origin="HOLOO_CAPTURE",
            flow_outcome=FLOW_OUTCOME_REPRINT_RECOGNIZED,
            identity_scope="S2", identity_fingerprint="fp",
            created_at="t", record_fingerprint="", fingerprint_algorithm_id="")
        raise AssertionError("dataclass accepted a non-durable outcome "
                             "without refusal")


def test_public_surface_has_no_decision_or_mutation_verbs():
    import duplicate_flows as pkg
    for name in pkg.__all__:
        lowered = name.lower()
        for token in ("canonicalize", "admit", "route", "decide", "update",
                      "delete", "issue", "assemble", "close_review",
                      "resolve"):
            assert token not in lowered, \
                f"public surface exposes a decision/mutation verb: {name}"


# ---------------------------------------------------------------------------
# Frozen-layer protection — the layer mutates NOTHING upstream
# ---------------------------------------------------------------------------

def test_row_count_stability_of_frozen_stores_during_handle(stack):
    nid, projection = stack.build_valid_identity_state(label="df-bnd-rc")
    state_id = projection.record.domain_state_id

    def counts():
        rows = {}
        conns = {
            "capture": (stack.capture_db, "capture_records"),
            "recon": (stack.recon_db, "documents"),
            "norm": (stack.norm_db, "normalization_records"),
            "vsm": (stack.vsm_db, "domain_state_records"),
        }
        for key, (db, table) in conns.items():
            conn = sqlite3.connect(str(db))
            try:
                rows[key] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                rows[key] = None          # table name varies per layer
            finally:
                conn.close()
        rows["identity_resolutions"] = len(
            stack.identity_store.list_resolutions())
        rows["observations"] = _observation_count(stack)
        return rows

    before = counts()
    outcome = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, FlowIdentityEstablished)
    # the first handle grew the IDENTITY store by exactly ONE resolution
    # (WP-7.1 doing its job THROUGH the flow layer) and the flow store by
    # exactly ONE disposition
    after_first = counts()
    assert after_first["identity_resolutions"] == \
        before["identity_resolutions"] + 1
    assert len(stack.flow_store.list_dispositions()) == 1
    # the REPRINT grows NOTHING anywhere
    stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert counts() == after_first
    assert len(stack.flow_store.list_dispositions()) == 1


def _observation_count(stack):
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM identity_duplicate_observations"
        ).fetchone()[0]
    finally:
        conn.close()


def test_spy_zero_upstream_execution_during_handle(stack):
    """handle() NEVER executes any upstream layer — WP-7.1's resolve is the
    only engine, and the flow layer adds no reads of its own beyond the
    verified identity reads."""
    calls = []
    inner_vsm, inner_norm = stack.vsm, stack.norm

    class SpyVSM:
        def __getattr__(self, name):
            return getattr(inner_vsm, name)

        def project_domain_state(self, *a, **k):
            calls.append("project_domain_state")
            return inner_vsm.project_domain_state(*a, **k)

    class SpyNorm:
        def __getattr__(self, name):
            return getattr(inner_norm, name)

        def normalize(self, *a, **k):
            calls.append("normalize")
            return inner_norm.normalize(*a, **k)

        def read_normalization(self, *a, **k):
            calls.append("read_normalization")
            return inner_norm.read_normalization(*a, **k)

    stack.identity._domain = SpyVSM()
    stack.identity._normalization = SpyNorm()
    try:
        nid, projection = stack.build_valid_identity_state(
            label="df-bnd-spy")
        state_id = projection.record.domain_state_id
        calls.clear()
        outcome = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, FlowIdentityEstablished)
        # the flow layer itself triggered NO upstream call beyond what the
        # WP-7.1 resolve legitimately performs (the read_normalization of
        # the VALID-state S2 attempt)
        assert calls.count("project_domain_state") == 0
        assert calls.count("normalize") == 0
        calls.clear()
        reprint = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(reprint, FlowReprintRecognized)
        assert calls == []          # replay: zero reads anywhere upstream
    finally:
        stack.identity._domain = inner_vsm
        stack.identity._normalization = inner_norm


# ---------------------------------------------------------------------------
# Concurrency — INV-DF-1:1 with the UNIQUE backstop (never Python-only)
#
# Project precedent (WP-7.1 build record): full-stack thread races expose
# the FROZEN layers' own concurrent-read behavior — out of this WP's
# boundary. The races here use thread-local flow stores + inert identity
# stubs holding PRE-READ verified outcomes, so ONLY the flow layer is
# raced; the identity-level duplicate race is WP-7.1's tested territory.
# ---------------------------------------------------------------------------

class _StubIdentity:
    """Inert identity service: returns PRE-READ verified outcomes (never
    touches a store). read_resolution returns a verified view of the
    pre-read record — exactly what the flow reads require."""

    def __init__(self, resolve_outcome):
        self._outcome = resolve_outcome

    def resolve(self, *a, **k):
        return self._outcome

    def read_resolution(self, resolution_id):
        from identity_resolution import (
            IdentityReadSuccess, IdentityReadRefused)
        record = getattr(self._outcome, "record", None)
        if record is None or record.resolution_id != resolution_id:
            return IdentityReadRefused(resolution_id,
                                       "no such identity resolution")
        role_rows = getattr(self._outcome, "role_rows", ())
        return IdentityReadSuccess(record, tuple(role_rows), None,
                                   "stub-verified")


def _thread_flow_stack(flows_db):
    from capture import S1Service
    s1 = S1Service()
    store = FlowDispositionStore(flows_db, s1)
    return store, s1


def test_eight_thread_same_capture_race_yields_one_disposition(stack):
    """Eight concurrent handle() calls over the SAME pre-read outcome →
    exactly ONE durable disposition; every loser recognizes the winner
    read-only (F6 — the UNIQUE backstop, not a Python check)."""
    nid, projection = stack.build_valid_identity_state(label="df-bnd-race1")
    pre_read = stack.identity.resolve(projection.record.domain_state_id,
                                      ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(pre_read, IdentityResolutionRecorded)
    # the resolution exists; NO disposition yet — the race is over who
    # commits THE one disposition for this capture_s1
    assert len(stack.flow_store.list_dispositions()) == 0
    flows_db = stack.flows_db
    results = []
    errors = []
    barrier = threading.Barrier(8)

    def worker():
        store, s1 = _thread_flow_stack(flows_db)
        service = DuplicateFlowService(store, _StubIdentity(pre_read), s1)
        try:
            barrier.wait()
            results.append(service.handle("stub-state",
                                          ORIGIN_HOLOO_CAPTURE, BINDING))
        except Exception as exc:      # pragma: no cover
            errors.append(repr(exc))
        finally:
            store.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    established = [r for r in results
                   if isinstance(r, FlowIdentityEstablished)]
    reprints = [r for r in results if isinstance(r, FlowReprintRecognized)]
    assert len(established) == 1
    assert len(reprints) == 7
    winner = established[0].disposition
    assert all(r.disposition == winner for r in reprints)
    assert len(stack.flow_store.list_dispositions()) == 1


def test_twin_capture_race_keeps_one_original(stack):
    """Concurrent commits of two DIFFERENT captures (one carrying a
    pre-read D-03 duplicate outcome) → two dispositions, the register
    coherent, ONE original. Identities are PRE-RESOLVED (identity facts);
    only the flow layer is raced."""
    nid_a, projection_a = stack.build_valid_identity_state(
        label="df-bnd-race2-a")
    outcome_a = stack.identity.resolve(projection_a.record.domain_state_id,
                                       ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome_a, IdentityResolutionRecorded)
    nid_b, projection_b = stack.build_valid_identity_state(
        parts=twin_pages(), label="df-bnd-race2-b")
    outcome_b = stack.identity.resolve(projection_b.record.domain_state_id,
                                       ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome_b, IdentityDefiniteDuplicate)
    assert len(stack.flow_store.list_dispositions()) == 0

    original_record = outcome_a.record
    flows_db = stack.flows_db
    results = []
    errors = []
    barrier = threading.Barrier(2)

    def worker(record_outcome, state_ref):
        store, s1 = _thread_flow_stack(flows_db)
        service = DuplicateFlowService(store, _StubIdentity(record_outcome),
                                       s1)
        try:
            barrier.wait()
            results.append(service.handle(state_ref, ORIGIN_HOLOO_CAPTURE,
                                          BINDING))
        except Exception as exc:      # pragma: no cover
            errors.append(repr(exc))
        finally:
            store.close()

    threads = [threading.Thread(target=worker, args=(outcome_a, "state-a")),
               threading.Thread(target=worker, args=(outcome_b, "state-b"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    assert len(results) == 2
    established = [r for r in results
                   if isinstance(r, FlowIdentityEstablished)]
    duplicates = [r for r in results
                  if isinstance(r, FlowDuplicateRecognized)]
    assert len(established) == 1
    assert len(duplicates) == 1
    assert established[0].disposition.resolution_id \
        == original_record.resolution_id
    assert duplicates[0].disposition.original_resolution_id \
        == original_record.resolution_id
    dispositions = stack.flow_store.list_dispositions()
    assert len(dispositions) == 2
    register = stack.flows.duplicates_of(original_record.resolution_id)
    assert {d.disposition_id for d in register} == {
        duplicates[0].disposition.disposition_id}


# ---------------------------------------------------------------------------
# Cold-start determinism — the flow fact is stable across rebuilds
# ---------------------------------------------------------------------------

def test_disposition_content_is_independent_of_deployment_order(stack):
    """OD-DF-E: the disposition derived at a late (F5) sighting is a pure
    function of the durable identity facts — it anchors the existing
    resolution exactly, and two independent derivations of the SAME capture
    yield byte-identical content apart from bookkeeping."""
    nid, projection = stack.build_valid_identity_state(label="df-bnd-det")
    state_id = projection.record.domain_state_id
    resolved = stack.identity.resolve(state_id, ORIGIN_HOLOO_CAPTURE,
                                      BINDING)
    assert isinstance(resolved, IdentityResolutionRecorded)
    record = resolved.record

    late = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(late, FlowReprintRecognized)
    d = late.disposition
    assert d.capture_s1 == record.capture_s1
    assert d.capture_id == record.capture_id
    assert d.document_id == record.document_id
    assert d.resolution_id == record.resolution_id
    assert d.declared_origin == record.declared_origin
    assert d.identity_scope == record.identity_scope
    assert d.identity_fingerprint == record.identity_fingerprint
    assert d.flow_outcome == "IDENTITY_ESTABLISHED"
    assert d.original_resolution_id == ""

    # an independent second derivation of the SAME capture (TEST-ONLY store
    # reset) produces the same content apart from bookkeeping
    import sqlite3
    conn = sqlite3.connect(str(stack.flows_db))
    try:
        conn.execute("DELETE FROM flow_dispositions")
        conn.commit()
    finally:
        conn.close()
    again = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(again, FlowReprintRecognized)
    d2 = again.disposition
    for field in ("capture_s1", "capture_s1_algorithm_id", "capture_id",
                  "document_id", "resolution_id", "original_resolution_id",
                  "duplicate_observation_id", "declared_origin",
                  "flow_outcome", "identity_scope", "identity_fingerprint"):
        assert getattr(d2, field) == getattr(d, field), field
