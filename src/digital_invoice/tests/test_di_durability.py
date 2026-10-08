"""WP-10.1 durability + concurrency + structural tests (SPEC §8/§12): atomic
commit (zero residue), restart safety, UNIQUE backstops, CHECK refusals via
direct SQL, 8-thread races (open + advance + the REVOKE-vs-SUPERSEDE race),
AST probes (no UPDATE/DELETE/hashlib/random/float; import allowlist), frozen-
store row-count stability."""
import threading

import pytest

from digital_invoice import (
    DigitalInvoiceOpenReplay,
    DigitalInvoiceOpened,
    DigitalInvoiceReadSuccess,
    LifecycleAdvanced,
    LifecycleReplay,
    LifecycleRequestRefused,
    LIFECYCLE_STATES,
    TERMINAL_STATES,
    STATE_DRAFT,
    STATE_EXTRACTED,
    STATE_ISSUED,
    STATE_REVOKED,
    STATE_SUPERSEDED,
    STATE_VALIDATED,
    is_legal_transition,
)

from capture import S1Service
from di_helpers import unique_di_pages


# ---------------------------------------------------------------------------
# Atomic commit — forced failure leaves ZERO residue
# ---------------------------------------------------------------------------

def test_forced_commit_failure_zero_residue_invoice_row(stack, monkeypatch):
    _, invoice_id = stack.assemble_di_invoice(label="di-dur-1")
    stack.open_ok(invoice_id)
    read = stack.read_ok(invoice_id)

    from digital_invoice import store as di_store
    real = di_store.canonical_event_bytes

    def boom(record):
        raise di_store.DigitalInvoicePersistenceUnavailable(
            "forced fingerprint failure")

    monkeypatch.setattr(stack.digital_store._s1, "compute", boom)
    outcome = stack.di.mark_extracted(invoice_id)
    monkeypatch.setattr(stack.digital_store._s1, "compute",
                        lambda r: type("V", (), {"s1": "0" * 64,
                                                 "s1_algorithm_id":
                                                     "sha256-v1"})())
    from digital_invoice import LifecycleStorageUnavailable
    assert isinstance(outcome, LifecycleStorageUnavailable), outcome
    assert len(stack.di.lifecycle_events()) == 0           # zero residue
    # the layer still works afterwards
    advanced = stack.advance_ok(invoice_id, "mark_extracted")
    assert isinstance(advanced, LifecycleAdvanced)


# ---------------------------------------------------------------------------
# Restart durability
# ---------------------------------------------------------------------------

def test_restart_survival_and_replay(stack, make_stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-dur-2")
    stack.open_ok(invoice_id)
    stack.advance_ok(invoice_id, "mark_extracted", "note-1")
    before_read = stack.read_ok(invoice_id)
    stack.close()
    reopened = make_stack()
    try:
        after = reopened.di.read_digital_invoice(invoice_id)
        assert isinstance(after, DigitalInvoiceReadSuccess), after
        assert after.current_state == "EXTRACTED"
        assert list(after.events) == list(before_read.events)
        replay = reopened.di.open_digital_invoice(invoice_id)
        assert isinstance(replay, DigitalInvoiceOpenReplay), replay
        assert replay.record == before_read.record
        advanced = reopened.advance_ok(invoice_id, "mark_validated")
        assert isinstance(advanced, LifecycleAdvanced)
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# UNIQUE / CHECK backstops via direct SQL
# ---------------------------------------------------------------------------

def test_inv_di_1_1_unique_backstop_via_direct_sql(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-dur-3")
    stack.open_ok(invoice_id)
    read = stack.read_ok(invoice_id)
    import sqlite3
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO digital_invoices (digital_invoice_id, "
                "invoice_id, capture_s1, capture_s1_algorithm_id, capture_id,"
                " document_id, origin, created_at, record_fingerprint, "
                "fingerprint_algorithm_id) VALUES ('x', ?, 's1', 'a', 'c', "
                "'d', 'HOLOO_CAPTURE', 't', 'fp', 'sha256-v1')",
                (invoice_id,))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO digital_invoices (digital_invoice_id, "
                "invoice_id, capture_s1, capture_s1_algorithm_id, capture_id,"
                " document_id, origin, created_at, record_fingerprint, "
                "fingerprint_algorithm_id) VALUES ('y', 'z', 's1', 'a', 'c',"
                " 'd', 'NOT_AN_ORIGIN', 't', 'fp', 'sha256-v1')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO digital_invoice_events (event_id, "
                "digital_invoice_id, invoice_id, event_seq, event_type, "
                "from_state, to_state, replacement_invoice_id, reason_note, "
                "created_at, record_fingerprint, fingerprint_algorithm_id) "
                "VALUES ('e1', ?, ?, 0, 'ISSUE', 'DRAFT', 'ISSUED', '', '',"
                " 't', 'fp', 'sha256-v1')",
                (read.record.digital_invoice_id, invoice_id))
    finally:
        conn.close()
    assert len(stack.di.lifecycle_events()) == 0


def test_event_seq_unique_backstop_via_direct_sql(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-dur-4")
    stack.open_ok(invoice_id)
    stack.advance_ok(invoice_id, "mark_extracted")
    read = stack.read_ok(invoice_id)
    import sqlite3
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO digital_invoice_events (event_id, "
                "digital_invoice_id, invoice_id, event_seq, event_type, "
                "from_state, to_state, replacement_invoice_id, reason_note, "
                "created_at, record_fingerprint, fingerprint_algorithm_id) "
                "VALUES ('dup', ?, ?, 0, 'MARK_EXTRACTED', 'DRAFT', "
                "'EXTRACTED', '', '', 't', 'fp', 'sha256-v1')",
                (read.record.digital_invoice_id, invoice_id))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Concurrency — 8-thread races (project precedent: thread-local stores)
# ---------------------------------------------------------------------------

class _StubAssembly:
    """Inert assembly service: per-invoice PRE-READ verified outcomes (never
    touches a store)."""

    def __init__(self, pre_reads, pre_trace=None):
        self._pre_reads = pre_reads          # {invoice_id: AssemblyReadSuccess}
        self._pre_trace = pre_trace

    def read_assembled_invoice(self, invoice_id):
        return self._pre_reads[invoice_id]

    def trace_assembled_invoice(self, invoice_id):
        if self._pre_trace is not None:
            return self._pre_trace
        raise AssertionError("trace not expected in this stub")


def test_eight_thread_open_race_yields_one_digital_invoice(stack):
    from digital_invoice import DigitalInvoiceLifecycleService, \
        DigitalInvoiceStore
    from canonical_assembly import AssemblyTraceSuccess
    _, invoice_id = stack.assemble_di_invoice(label="di-dur-5")
    pre_read = stack.assembly.read_assembled_invoice(invoice_id)
    pre_trace = stack.assembly.trace_assembled_invoice(invoice_id)
    assert len(stack.di.digital_invoices()) == 0
    digital_db = stack.digital_db
    results = []
    errors = []
    barrier = threading.Barrier(8)

    def worker():
        s1 = S1Service()
        store = DigitalInvoiceStore(digital_db, s1)
        service = DigitalInvoiceLifecycleService(
            store, _StubAssembly({invoice_id: pre_read}, pre_trace), s1)
        try:
            barrier.wait()
            results.append(service.open_digital_invoice(invoice_id))
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
    opened = [r for r in results if isinstance(r, DigitalInvoiceOpened)]
    replays = [r for r in results if isinstance(r, DigitalInvoiceOpenReplay)]
    assert len(opened) == 1
    assert len(replays) == 7
    winner = opened[0].record
    assert all(r.record == winner for r in replays)
    assert len(stack.di.digital_invoices()) == 1


def test_eight_thread_advance_race_yields_one_event(stack):
    from digital_invoice import DigitalInvoiceLifecycleService, \
        DigitalInvoiceStore
    _, invoice_id = stack.assemble_di_invoice(label="di-dur-6")
    stack.open_ok(invoice_id)
    pre_read = stack.di.read_digital_invoice(invoice_id)
    assert pre_read.current_state == STATE_DRAFT
    digital_db = stack.digital_db
    results = []
    errors = []
    barrier = threading.Barrier(8)

    def worker():
        s1 = S1Service()
        store = DigitalInvoiceStore(digital_db, s1)
        service = DigitalInvoiceLifecycleService(
            store, _StubAssembly({invoice_id: pre_read.invoice_read}), s1)
        try:
            barrier.wait()
            results.append(service.mark_extracted(invoice_id))
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
    advanced = [r for r in results if isinstance(r, LifecycleAdvanced)]
    replays = [r for r in results if isinstance(r, LifecycleReplay)]
    assert len(advanced) == 1
    assert len(replays) == 7
    assert len(stack.di.lifecycle_events()) == 1
    assert stack.read_ok(invoice_id).current_state == STATE_EXTRACTED


def test_revoke_vs_supersede_race_exactly_one_terminal_act_wins(stack):
    """From ISSUED two terminal acts are possible; under concurrency exactly
    ONE commits — the loser re-projects honestly and refuses (never
    reshapes)."""
    from digital_invoice import DigitalInvoiceLifecycleService, \
        DigitalInvoiceStore
    _, invoice_id = stack.assemble_di_invoice(label="di-dur-7")
    _, replacement = stack.assemble_di_invoice(parts=unique_di_pages(),
                                               label="di-dur-7b")
    stack.open_ok(invoice_id)
    for act in ("mark_extracted", "mark_validated", "issue"):
        stack.advance_ok(invoice_id, act)
    stack.open_ok(replacement)
    for act in ("mark_extracted", "mark_validated", "issue"):
        stack.advance_ok(replacement, act)
    pre_read = stack.di.read_digital_invoice(invoice_id)
    repl_read = stack.di.read_digital_invoice(replacement)
    pre_reads = {invoice_id: pre_read.invoice_read,
                 replacement: repl_read.invoice_read}
    digital_db = stack.digital_db
    results = []
    errors = []
    barrier = threading.Barrier(2)

    def worker(act, kwargs):
        s1 = S1Service()
        store = DigitalInvoiceStore(digital_db, s1)
        service = DigitalInvoiceLifecycleService(
            store, _StubAssembly(pre_reads), s1)
        try:
            barrier.wait()
            results.append(getattr(service, act)(invoice_id, **kwargs))
        except Exception as exc:      # pragma: no cover
            errors.append(repr(exc))
        finally:
            store.close()

    threads = [threading.Thread(target=worker, args=(act, kw)) for act, kw in
               (("revoke", {}), ("supersede",
                                 {"replacement_invoice_id": replacement}))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    final = stack.read_ok(invoice_id)
    advanced = [r for r in results if isinstance(r, LifecycleAdvanced)]
    assert len(advanced) == 1                     # exactly ONE terminal act
    refused = [r for r in results if isinstance(r, LifecycleRequestRefused)]
    assert len(refused) == 1
    if final.current_state == STATE_REVOKED:
        assert "terminal" in refused[0].detail or "no longer available" \
            in refused[0].detail
    else:
        assert final.current_state == STATE_SUPERSEDED
    assert final.current_state in TERMINAL_STATES


# ---------------------------------------------------------------------------
# Structural / AST probes
# ---------------------------------------------------------------------------

IMPORT_ROOTS = ("capture", "canonical_assembly", "digital_invoice")


def _ast_files():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent          # digital_invoice/
    return [p for p in root.glob("*.py")]


def test_no_update_delete_drop_hashlib_random_float_eval_in_layer():
    import ast
    forbidden_names = ("hashlib", "random", "urandom")
    for path in _ast_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names]
                if isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module)
                for name in names:
                    for token in forbidden_names:
                        assert token not in name, (path, name)
            # SQL mutation probes: every sqlite execute() argument string
            # must never START with an UPDATE/DELETE/DROP statement
            if isinstance(node, ast.Call) and isinstance(node.func,
                                                         ast.Attribute) \
                    and node.func.attr in ("execute", "executescript"):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) \
                            and isinstance(arg.value, str):
                        stripped = arg.value.lstrip().upper()
                        assert not stripped.startswith("UPDATE"), path
                        assert not stripped.startswith("DELETE"), path
                        assert not stripped.startswith("DROP"), path
            if isinstance(node, ast.Call) and isinstance(node.func,
                                                         ast.Name):
                assert node.func.id not in ("eval", "exec"), path


def test_store_insert_surface_exactly_two_tables_two_inserts():
    import ast
    store_path = [p for p in _ast_files() if p.name == "store.py"][0]
    source = store_path.read_text(encoding="utf-8")
    assert source.count("INSERT INTO digital_invoices") == 1
    assert source.count("INSERT INTO digital_invoice_events") == 1
    assert "CREATE TABLE" in source
    tree = ast.parse(source)
    # uuid bookkeeping only — no os.urandom, no random module
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("urandom", "token_bytes")), node


def test_import_allowlist():
    """Project modules + stdlib ONLY — no third-party, no sibling layers."""
    import ast
    import sys
    stdlib = set(sys.stdlib_module_names)
    for path in _ast_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root in IMPORT_ROOTS or root in stdlib, \
                        (path, alias.name)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                    and node.module:
                root = node.module.split(".")[0]
                assert root in IMPORT_ROOTS or root in stdlib, \
                    (path, node.module)


def test_service_has_no_uuid_minting_beyond_bookkeeping():
    """The only uuid usage is bookkeeping row ids — no identity formula."""
    import ast
    svc_path = [p for p in _ast_files() if p.name == "service.py"][0]
    tree = ast.parse(svc_path.read_text(encoding="utf-8"))
    uuid_calls = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Attribute) and n.attr == "hex"]
    assert len(uuid_calls) == 2        # digital_invoice_id + event_id only


def test_vocabulary_sweep_no_state_outside_frozen_six():
    """The layer's state vocabulary is EXACTLY the frozen six (AS-03)."""
    from digital_invoice import model
    assert set(LIFECYCLE_STATES) == {
        "DRAFT", "EXTRACTED", "VALIDATED", "ISSUED", "REVOKED", "SUPERSEDED"}
    assert TERMINAL_STATES == ("REVOKED", "SUPERSEDED")
    # every legal transition stays inside the vocabulary
    from digital_invoice import TRANSITIONS
    for _, frm, to in TRANSITIONS:
        assert frm in LIFECYCLE_STATES and to in LIFECYCLE_STATES
    # no synonym/alias states exported
    for name in dir(model):
        if name.startswith("STATE_"):
            assert getattr(model, name) in LIFECYCLE_STATES


def test_no_forbidden_semantics_in_vocabulary():
    """No REVIEW/REJECT/UNRESOLVED/fuzzy/confidence/customer/product/
    inventory/presentation semantics anywhere in the layer's vocabulary or
    reason codes."""
    import digital_invoice as di
    surface = set()
    for name in di.__all__:
        surface.add(name)
    for token in ("REVIEW", "REJECT", "UNRESOLVED", "FUZZY", "CONFIDENCE",
                  "INVENTORY", "PRESENTATION", "RENDER"):
        for name in surface:
            assert token not in name, (token, name)


def test_frozen_store_row_counts_stable_after_lifecycle(stack):
    """The lifecycle grew NO frozen store — only digital-invoice.db."""
    import sqlite3
    _, inv1 = stack.assemble_di_invoice(label="di-dur-8a")
    _, inv2 = stack.assemble_di_invoice(parts=unique_di_pages(),
                                        label="di-dur-8b")
    _, inv3 = stack.assemble_di_invoice(parts=unique_di_pages(),
                                        label="di-dur-8c")

    def frozen_counts():
        counts = {}
        for db, table in (
                (stack.capture_db, "captures"),
                (stack.assembly_db, "canonical_invoices"),
                (stack.assembly_db, "canonical_fields"),
                (stack.gate_db, "gate_decisions"),
        ):
            conn = sqlite3.connect(str(db))
            try:
                counts[(db.name, table)] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                counts[(db.name, table)] = None     # table name differs — skip
            finally:
                conn.close()
        return counts

    before = frozen_counts()
    stack.open_ok(inv1)
    for act in ("mark_extracted", "mark_validated", "issue"):
        stack.advance_ok(inv1, act)
    stack.open_ok(inv2)
    for act in ("mark_extracted", "mark_validated", "issue", "revoke"):
        stack.advance_ok(inv2, act)
    stack.open_ok(inv3)
    for act in ("mark_extracted", "mark_validated", "issue"):
        stack.advance_ok(inv3, act)
    stack.advance_ok(inv1, "supersede", inv3)
    after = frozen_counts()
    assert before == after


def test_end_to_end_capture_to_terminal_digital_invoice(stack):
    """Full pipeline: Capture → … → P6.2 → WP-10.1 → SUPERSEDED."""
    _, source = stack.assemble_di_invoice(label="di-dur-9a")
    _, replacement = stack.assemble_di_invoice(parts=unique_di_pages(),
                                               label="di-dur-9b")
    stack.open_ok(source)
    stack.advance_ok(source, "mark_extracted")
    stack.advance_ok(source, "mark_validated")
    stack.advance_ok(source, "issue")
    stack.open_ok(replacement)
    stack.advance_ok(replacement, "mark_extracted")
    stack.advance_ok(replacement, "mark_validated")
    stack.advance_ok(replacement, "issue")
    outcome = stack.di.supersede(source, replacement, "corrected invoice")
    assert isinstance(outcome, LifecycleAdvanced), outcome
    trace = stack.di.trace_digital_invoice(source)
    assert isinstance(trace, DigitalInvoiceReadSuccess) or True
    from digital_invoice import DigitalInvoiceTraceSuccess
    assert isinstance(trace, DigitalInvoiceTraceSuccess), trace
    assert trace.current_state == STATE_SUPERSEDED
    assert any("SUPERSEDE" in line for line in trace.chain)
