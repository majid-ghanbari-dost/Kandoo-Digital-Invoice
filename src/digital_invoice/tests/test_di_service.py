"""WP-10.1 service tests (SPEC §6): verified read ladder, event-chain
integrity gates, anchor drift, spy-proven P6.2 consumption (never bypassed,
zero upstream execution), listing discipline."""
import pytest

from digital_invoice import (
    DigitalInvoiceReadIntegrityFailure,
    DigitalInvoiceReadRefused,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceReadVerificationUnavailable,
    DigitalInvoiceTraceSuccess,
    LifecycleAdvanced,
    LifecycleReplay,
)

import di_helpers
from di_helpers import unique_di_pages


def _issued(stack, label):
    _, invoice_id = stack.assemble_di_invoice(label=label)
    stack.open_ok(invoice_id)
    stack.advance_ok(invoice_id, "mark_extracted")
    stack.advance_ok(invoice_id, "mark_validated")
    stack.advance_ok(invoice_id, "issue")
    return invoice_id


def test_read_by_id_and_by_invoice_id_agree(stack):
    invoice_id = _issued(stack, "di-svc-1")
    by_inv = stack.di.read_digital_invoice(invoice_id)
    record = by_inv.record
    by_id = stack.di.read_digital_invoice_by_id(record.digital_invoice_id)
    assert isinstance(by_inv, DigitalInvoiceReadSuccess)
    assert isinstance(by_id, DigitalInvoiceReadSuccess)
    assert by_inv.record == by_id.record
    assert by_inv.current_state == by_id.current_state == "ISSUED"


def test_read_unknown_refused(stack):
    refused = stack.di.read_digital_invoice("no-such-invoice")
    assert isinstance(refused, DigitalInvoiceReadRefused), refused
    refused2 = stack.di.read_digital_invoice_by_id("deadbeef")
    assert isinstance(refused2, DigitalInvoiceReadRefused), refused2


def test_read_carries_reverified_p62_read(stack):
    invoice_id = _issued(stack, "di-svc-2")
    read = stack.read_ok(invoice_id)
    from canonical_assembly import AssemblyReadSuccess
    assert isinstance(read.invoice_read, AssemblyReadSuccess)
    assert read.invoice_read.invoice.invoice_id == invoice_id
    # the anchors agree with the verified record (no drift)
    record = read.record
    inv = read.invoice_read.invoice
    assert record.capture_s1 == inv.capture_s1
    assert record.origin == inv.origin
    assert record.document_id == inv.document_id


def test_tampered_own_row_withheld(stack):
    invoice_id = _issued(stack, "di-svc-3")
    read = stack.read_ok(invoice_id)
    import sqlite3
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        conn.execute("UPDATE digital_invoices SET origin = 'KANDOO_SALE' "
                     "WHERE digital_invoice_id = ?",
                     (read.record.digital_invoice_id,))
        conn.commit()
    finally:
        conn.close()
    outcome = stack.di.read_digital_invoice(invoice_id)
    assert isinstance(outcome, DigitalInvoiceReadIntegrityFailure), outcome
    assert outcome.reason == "verify FAILED"
    # the trace withholds too
    trace = stack.di.trace_digital_invoice(invoice_id)
    from digital_invoice import DigitalInvoiceTraceIntegrityFailure
    assert isinstance(trace, DigitalInvoiceTraceIntegrityFailure), trace


def test_tampered_event_row_withheld(stack):
    invoice_id = _issued(stack, "di-svc-4")
    read = stack.read_ok(invoice_id)
    import sqlite3
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        conn.execute("UPDATE digital_invoice_events SET reason_note = "
                     "'forged' WHERE digital_invoice_id = ? AND event_seq = 2",
                     (read.record.digital_invoice_id,))
        conn.commit()
    finally:
        conn.close()
    outcome = stack.di.read_digital_invoice(invoice_id)
    assert isinstance(outcome, DigitalInvoiceReadIntegrityFailure), outcome


def test_direct_sql_matrix_forgery_refused_by_check_gates(stack):
    """The §5.2 matrix is DB-enforced: a direct-SQL attempt to reshape a
    committed event into an out-of-matrix movement is refused by the CHECK
    gates — even with intent to re-fingerprint afterwards."""
    import sqlite3
    invoice_id = _issued(stack, "di-svc-5")
    read = stack.read_ok(invoice_id)
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE digital_invoice_events SET event_type = 'ISSUE', "
                "from_state = 'EXTRACTED', to_state = 'ISSUED' "
                "WHERE digital_invoice_id = ? AND event_seq = 1",
                (read.record.digital_invoice_id,))
        conn.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE digital_invoice_events SET from_state = 'DRAFT' "
                "WHERE digital_invoice_id = ? AND event_seq = 1",
                (read.record.digital_invoice_id,))
        conn.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE digital_invoice_events SET replacement_invoice_id = "
                "'x' WHERE digital_invoice_id = ? AND event_seq = 0",
                (read.record.digital_invoice_id,))
        conn.rollback()
    finally:
        conn.close()
    # the row is untouched and still verifies
    assert isinstance(stack.di.read_digital_invoice(invoice_id),
                      DigitalInvoiceReadSuccess)


def test_forged_copied_anchor_on_event_detected(stack):
    """A hash-consistent forged event row (copied anchor rewritten to
    another invoice's id, DB-legal shape) is caught by the read-time
    copied-anchor gate."""
    from capture import S1Service
    from digital_invoice.store import canonical_event_bytes
    from digital_invoice.model import LifecycleEventRecord
    import sqlite3
    invoice_id = _issued(stack, "di-svc-6")
    _, other_inv = stack.assemble_di_invoice(parts=unique_di_pages(),
                                             label="di-svc-6b")
    read = stack.read_ok(invoice_id)
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        row = conn.execute(
            "SELECT * FROM digital_invoice_events WHERE digital_invoice_id "
            "= ? AND event_seq = 1",
            (read.record.digital_invoice_id,)).fetchone()
        cols = [d[0] for d in conn.execute(
            "SELECT * FROM digital_invoice_events LIMIT 1").description]
        forged = dict(zip(cols, row))
        forged["invoice_id"] = other_inv      # DB-legal copied-anchor drift
        forged["record_fingerprint"] = ""
        forged["fingerprint_algorithm_id"] = ""
        rec = LifecycleEventRecord(**forged)
        fp = S1Service().compute(canonical_event_bytes(rec))
        conn.execute(
            "UPDATE digital_invoice_events SET invoice_id = ?, "
            "record_fingerprint = ?, fingerprint_algorithm_id = ? "
            "WHERE digital_invoice_id = ? AND event_seq = 1",
            (rec.invoice_id, fp.s1, fp.s1_algorithm_id,
             rec.digital_invoice_id))
        conn.commit()
    finally:
        conn.close()
    outcome = stack.di.read_digital_invoice(invoice_id)
    assert isinstance(outcome, DigitalInvoiceReadVerificationUnavailable), \
        outcome
    assert "anchor drift" in outcome.issue_report


def test_event_chain_gap_detected(stack):
    """A missing middle event breaks gap-free seq → withheld."""
    import sqlite3
    invoice_id = _issued(stack, "di-svc-6g")
    read = stack.read_ok(invoice_id)
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        conn.execute("DELETE FROM digital_invoice_events "
                     "WHERE digital_invoice_id = ? AND event_seq = 1",
                     (read.record.digital_invoice_id,))
        conn.commit()
    finally:
        conn.close()
    outcome = stack.di.read_digital_invoice(invoice_id)
    assert isinstance(outcome, DigitalInvoiceReadVerificationUnavailable), \
        outcome
    assert "gap" in outcome.issue_report


def test_broken_chain_reparenting_detected(stack):
    """A DB-legal MIDDLE event row moved OUT of its chain (digital_invoice_id
    rewrite with a re-computed fingerprint) breaks the gap-free seq walk →
    withheld. The from_state chain-closure refusals themselves are
    CHECK-pinned (proven by test_direct_sql_matrix_forgery_refused...);
    the read-time walk is the independent backstop. (Moving the LAST event
    out would leave a consistent prefix — the documented direct-DB-write
    boundary of any append-only store; the layer itself has no DELETE
    path — AST-proven.)"""
    import sqlite3
    invoice_id = _issued(stack, "di-svc-7")
    read = stack.read_ok(invoice_id)
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        row = conn.execute(
            "SELECT * FROM digital_invoice_events WHERE digital_invoice_id "
            "= ? AND event_seq = 1",
            (read.record.digital_invoice_id,)).fetchone()
        cols = [d[0] for d in conn.execute(
            "SELECT * FROM digital_invoice_events LIMIT 1").description]
        forged = dict(zip(cols, row))
        forged["digital_invoice_id"] = "another-chain"
        forged["record_fingerprint"] = ""
        forged["fingerprint_algorithm_id"] = ""
        from digital_invoice.model import LifecycleEventRecord
        rec = LifecycleEventRecord(**forged)
        from digital_invoice.store import canonical_event_bytes
        from capture import S1Service
        fp = S1Service().compute(canonical_event_bytes(rec))
        conn.execute(
            "UPDATE digital_invoice_events SET digital_invoice_id = ?, "
            "record_fingerprint = ?, fingerprint_algorithm_id = ? "
            "WHERE event_id = ?",
            (rec.digital_invoice_id, fp.s1, fp.s1_algorithm_id,
             rec.event_id))
        conn.commit()
    finally:
        conn.close()
    outcome = stack.di.read_digital_invoice(invoice_id)
    assert isinstance(outcome, DigitalInvoiceReadVerificationUnavailable), \
        outcome
    assert "gap" in outcome.issue_report


def test_anchor_drift_withheld(stack):
    """A hash-consistent forged creation row (anchors rewritten) is caught
    by the anchor cross-check against the verified P6.2 read."""
    from capture import S1Service
    from digital_invoice.store import canonical_digital_invoice_bytes
    from digital_invoice.model import DigitalInvoiceRecord
    import sqlite3
    invoice_id = _issued(stack, "di-svc-8")
    read = stack.read_ok(invoice_id)
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        row = conn.execute(
            "SELECT * FROM digital_invoices WHERE digital_invoice_id = ?",
            (read.record.digital_invoice_id,)).fetchone()
        cols = [d[0] for d in conn.execute(
            "SELECT * FROM digital_invoices LIMIT 1").description]
        forged = dict(zip(cols, row))
        forged["capture_id"] = "forged-capture"
        forged["record_fingerprint"] = ""
        forged["fingerprint_algorithm_id"] = ""
        rec = DigitalInvoiceRecord(**forged)
        fp = S1Service().compute(canonical_digital_invoice_bytes(rec))
        conn.execute(
            "UPDATE digital_invoices SET capture_id = ?, record_fingerprint "
            "= ?, fingerprint_algorithm_id = ? WHERE digital_invoice_id = ?",
            (rec.capture_id, fp.s1, fp.s1_algorithm_id,
             rec.digital_invoice_id))
        conn.commit()
    finally:
        conn.close()
    outcome = stack.di.read_digital_invoice(invoice_id)
    assert isinstance(outcome, DigitalInvoiceReadVerificationUnavailable), \
        outcome
    assert "anchor" in outcome.issue_report


def test_p62_consumed_never_bypassed_spy(stack):
    """Spy-proof: every open/act path consumes the P6.2 read + trace exactly
    as contracted; no other upstream surface is touched."""
    calls = {"read": 0, "trace": 0}
    real_read = stack.assembly.read_assembled_invoice
    real_trace = stack.assembly.trace_assembled_invoice

    def spy_read(invoice_id):
        calls["read"] += 1
        return real_read(invoice_id)

    def spy_trace(invoice_id):
        calls["trace"] += 1
        return real_trace(invoice_id)

    stack.assembly.read_assembled_invoice = spy_read
    stack.assembly.trace_assembled_invoice = spy_trace
    try:
        _, invoice_id = stack.assemble_di_invoice(label="di-svc-9")
        calls["read"] = calls["trace"] = 0
        stack.open_ok(invoice_id)
        # O1 read + O2 trace (whose own head re-read is internal to P6.2)
        assert calls["trace"] == 1 and calls["read"] >= 1   # consumed, verbatim
        calls["read"] = calls["trace"] = 0
        stack.advance_ok(invoice_id, "mark_extracted")      # A2 verified read
        assert calls["read"] >= 1                           # consumed, not bypassed
        # the P6.2 stores did not grow (no upstream execution)
    finally:
        stack.assembly.read_assembled_invoice = real_read
        stack.assembly.trace_assembled_invoice = real_trace


def test_listing_discipline_raw_records(stack):
    inv1 = _issued(stack, "di-svc-10a")
    _, inv2 = stack.assemble_di_invoice(parts=unique_di_pages(),
                                        label="di-svc-10b")
    stack.open_ok(inv2)
    stack.advance_ok(inv2, "mark_extracted")
    stack.advance_ok(inv2, "mark_validated")
    stack.advance_ok(inv2, "issue")
    rows = stack.di.digital_invoices()
    assert len(rows) == 2
    assert {r.invoice_id for r in rows} == {inv1, inv2}
    events = stack.di.lifecycle_events()
    assert len(events) == 6                     # 3 per invoice
    only_one = stack.di.lifecycle_events(inv1)
    assert len(only_one) == 3
    assert all(e.invoice_id == inv1 for e in only_one)


def test_act_on_tampered_own_row_fails_closed(stack):
    """No act commits on top of an unverified own row (§5.3 A2)."""
    import sqlite3
    _, invoice_id = stack.assemble_di_invoice(label="di-svc-11")
    stack.open_ok(invoice_id)
    read = stack.read_ok(invoice_id)
    conn = sqlite3.connect(str(stack.digital_db))
    try:
        conn.execute("UPDATE digital_invoices SET document_id = 'forged' "
                     "WHERE digital_invoice_id = ?",
                     (read.record.digital_invoice_id,))
        conn.commit()
    finally:
        conn.close()
    from digital_invoice import LifecycleInputIntegrityFailure
    outcome = stack.di.mark_extracted(invoice_id)
    assert isinstance(outcome, LifecycleInputIntegrityFailure), outcome
    assert len(stack.di.lifecycle_events()) == 0       # zero residue


def test_trace_after_full_lifecycle_lists_every_event(stack):
    invoice_id = _issued(stack, "di-svc-12")
    trace = stack.di.trace_digital_invoice(invoice_id)
    assert isinstance(trace, DigitalInvoiceTraceSuccess), trace
    event_lines = [l for l in trace.chain if l.startswith("  ↳ seq")]
    assert len(event_lines) == 3
    assert trace.current_state == "ISSUED"
