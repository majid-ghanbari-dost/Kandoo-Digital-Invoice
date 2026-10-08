"""WP-6.2 durability tests — restart safety, atomic commit zero-residue,
repeated/concurrent issuance, UNIQUE backstops (SPEC §8; dispatch §13 axes
10, 11, 24)."""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ca_helpers import (  # noqa: E402
    LINE_BINDING,
    CanonicalAssemblyStack,
    unique_line_pages,
)
from canonical_assembly import (  # noqa: E402
    AssemblyAlreadyAssembled,
    AssemblyCompleted,
    AssemblyReadSuccess,
    AssemblyStorageUnavailable,
    AssemblyTraceSuccess,
)
from canonicalization import CanonicalizationAccepted  # noqa: E402
from capture import S1ComputationFailure  # noqa: E402


def admitted(stack, label="ca-dur"):
    outcome = stack.build_accepted_lines_admission(unique_line_pages(),
                                                   label=label)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    return outcome


# ---------------------------------------------------------------------------
# Axis 10: atomic commit — any failure leaves ZERO residue
# ---------------------------------------------------------------------------

def test_fingerprint_failure_mid_commit_rolls_back_atomically(stack,
                                                              monkeypatch):
    """The commit computes the record fingerprint inside the transaction —
    a capability failure at that point rolls back EVERYTHING (invoice +
    anchors + fields + lines + line fields): no half-assembled state."""
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id

    class FailingS1:
        def compute(self, payload):
            raise S1ComputationFailure("forced failure for atomicity test")

        def verify(self, *args, **kwargs):
            raise S1ComputationFailure("forced failure for atomicity test")

    stack.assembly_store._s1 = FailingS1()
    result = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(result, AssemblyStorageUnavailable), result
    # zero residue — by construction, checked row by row
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        for table in ("canonical_invoices", "canonical_header_anchors",
                      "canonical_fields", "canonical_lines",
                      "canonical_line_fields"):
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0, f"{table} has {count} rows after rollback"
    finally:
        conn.close()


def test_failed_assembly_leaves_the_admission_reusable(stack, monkeypatch):
    """After a failed commit, a corrected attempt assembles cleanly — the
    admission was never consumed by the failure."""
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id

    class FailingS1:
        def compute(self, payload):
            raise S1ComputationFailure("forced")

        def verify(self, *args, **kwargs):
            raise S1ComputationFailure("forced")

    stack.assembly_store._s1 = FailingS1()
    failed = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(failed, AssemblyStorageUnavailable)
    from capture import S1Service
    stack.assembly_store._s1 = S1Service()
    recovered = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(recovered, AssemblyCompleted), recovered


# ---------------------------------------------------------------------------
# Axis 11: restart durability
# ---------------------------------------------------------------------------

def test_issued_invoice_survives_restart_with_full_verification(
        stack, make_stack):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    asm = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    stack.close()

    reopened = make_stack()
    try:
        read = reopened.assembly.read_assembled_invoice(invoice_id)
        assert isinstance(read, AssemblyReadSuccess), read
        assert read.invoice.invoice_id == invoice_id
        assert read.invoice.record_fingerprint == \
            asm.invoice.record_fingerprint
        assert read.fields == asm.fields
        assert read.line_fields == asm.line_fields
        tr = reopened.assembly.trace_assembled_invoice(invoice_id)
        assert isinstance(tr, AssemblyTraceSuccess), tr
        replay = reopened.assembly.assemble(invoice_id, LINE_BINDING)
        assert isinstance(replay, AssemblyAlreadyAssembled)
    finally:
        reopened.close()


def test_restart_after_failed_commit_is_clean(stack, make_stack,
                                              monkeypatch):
    outcome = admitted(stack)

    class FailingS1:
        def compute(self, payload):
            raise S1ComputationFailure("forced")

        def verify(self, *args, **kwargs):
            raise S1ComputationFailure("forced")

    stack.assembly_store._s1 = FailingS1()
    failed = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(failed, AssemblyStorageUnavailable)
    stack.close()

    reopened = make_stack()
    try:
        assert reopened.assembly.issued_invoices() == []
        recovered = reopened.assembly.assemble(
            outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
        assert isinstance(recovered, AssemblyCompleted), recovered
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# Axis 24: repeated / concurrent issuance — deterministic single winner
# ---------------------------------------------------------------------------

def test_repeated_issuance_is_idempotent_single_row(stack):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    results = [stack.assembly.assemble(invoice_id, LINE_BINDING)
               for _ in range(5)]
    assert sum(1 for r in results
               if isinstance(r, AssemblyCompleted)) == 1
    assert all(isinstance(r, AssemblyAlreadyAssembled) for r in results[1:])
    assert len(stack.assembly.issued_invoices()) == 1


def test_commit_time_duplicate_race_is_caught_by_the_backstop(stack):
    """Simulating the lost-update race: a stale service (replay gate sees
    nothing) still hits the in-transaction + UNIQUE backstop — one row."""
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    first = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(first, AssemblyCompleted)

    import canonical_assembly.service as service_module
    stale = stack.assembly
    original_find = stale._store.find_invoice_by_admission

    def blind_find(admission_decision_id):
        return None          # simulate a stale read that missed the row

    monkeypatched = False
    try:
        stale._store.find_invoice_by_admission = blind_find
        # rebuild the service so the replay gate uses the blind finder
        from canonical_assembly import CanonicalAssemblyService
        from capture import S1Service
        service2 = CanonicalAssemblyService(
            stale._store, stale._gate, stale._normalization,
            stale._derivation, S1Service())
        monkeypatched = True
        result = service2.assemble(invoice_id, LINE_BINDING)
        # the backstop catches the duplicate → explicit already-assembled
        assert isinstance(result, AssemblyAlreadyAssembled), result
    finally:
        if monkeypatched:
            stale._store.find_invoice_by_admission = original_find
    assert len(stack.assembly.issued_invoices()) == 1


def test_direct_sql_duplicate_insert_hits_the_unique_backstop(stack):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    asm = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        row = conn.execute(
            "SELECT * FROM canonical_invoices WHERE invoice_id = ?",
            (invoice_id,)).fetchone()
        cols = [d[0] for d in conn.execute(
            "SELECT * FROM canonical_invoices LIMIT 1").description]
        values = list(row)
        values[0] = "forged-second-id"          # same admission, new PK
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO canonical_invoices ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' * len(cols))})", values)
    finally:
        conn.close()
    assert len(stack.assembly.issued_invoices()) == 1
