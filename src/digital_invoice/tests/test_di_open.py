"""WP-10.1 open-ladder tests (SPEC §4): the ONLY entry is the P6.2 verified
read + whole-chain trace; INV-DI-1:1; replay verbatim; fail-closed upstream."""
import pytest

from canonical_assembly import (
    AssemblyReadRefused,
    AssemblyReadSuccess,
    AssemblyTraceSuccess,
)
from digital_invoice import (
    DigitalInvoiceInputIntegrityFailure,
    DigitalInvoiceOpenReplay,
    DigitalInvoiceOpened,
    DigitalInvoiceRequestRefused,
    DigitalInvoiceTraceSuccess,
    STATE_DRAFT,
    STATE_ISSUED,
    ORIGIN_HOLOO_CAPTURE,
)

from di_helpers import unique_di_pages


def test_open_happy_path_creates_one_digital_invoice_in_draft(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-open-1")
    outcome = stack.open_ok(invoice_id)
    record = outcome.record
    assert record.invoice_id == invoice_id
    assert record.origin == ORIGIN_HOLOO_CAPTURE     # frozen origin verbatim
    assert record.capture_s1 == outcome.invoice_read.invoice.capture_s1
    assert record.document_id == outcome.invoice_read.invoice.document_id
    assert record.record_fingerprint                  # sha256-v1 anchored
    read = stack.read_ok(invoice_id)
    assert read.current_state == STATE_DRAFT          # DRAFT by construction
    assert read.events == ()                          # no genesis event (OD-DI-E)
    # the verified P6.2 read is carried, not re-implemented
    assert isinstance(outcome.invoice_read, AssemblyReadSuccess)


def test_open_replay_returns_existing_verbatim_with_zero_new_rows(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-open-2")
    first = stack.open_ok(invoice_id)
    before_rows = len(stack.di.digital_invoices())
    before_events = len(stack.di.lifecycle_events())
    replay = stack.di.open_digital_invoice(invoice_id)
    assert isinstance(replay, DigitalInvoiceOpenReplay), replay
    assert replay.record == first.record
    assert replay.current_state == STATE_DRAFT
    assert len(stack.di.digital_invoices()) == before_rows == 1
    assert len(stack.di.lifecycle_events()) == before_events == 0


def test_open_replay_even_after_lifecycle_progress_verbatim(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-open-3")
    stack.open_ok(invoice_id)
    stack.advance_ok(invoice_id, "mark_extracted")
    stack.advance_ok(invoice_id, "mark_validated")
    stack.advance_ok(invoice_id, "issue")
    replay = stack.di.open_digital_invoice(invoice_id)
    assert isinstance(replay, DigitalInvoiceOpenReplay), replay
    assert replay.current_state == STATE_ISSUED       # the LIVE projection


def test_open_unknown_invoice_refused_with_zero_residue(stack):
    outcome = stack.di.open_digital_invoice("no-such-invoice-id")
    assert isinstance(outcome, DigitalInvoiceRequestRefused), outcome
    assert "no issued Canonical Invoice" in outcome.detail
    assert len(stack.di.digital_invoices()) == 0      # zero residue


def test_open_empty_invoice_id_refused(stack):
    outcome = stack.di.open_digital_invoice("")
    assert isinstance(outcome, DigitalInvoiceRequestRefused), outcome
    assert len(stack.di.digital_invoices()) == 0


def test_open_admission_only_no_invoice_without_assembly(stack):
    """A P6.1 ACCEPTED admission that was NEVER assembled has no issued
    invoice — the lifecycle refuses (P6.2 is the ONLY entry)."""
    gate_outcome = stack.build_accepted_lines_admission(
        parts=unique_di_pages(), label="di-open-4")
    assert isinstance(gate_outcome, CanonicalizationAccepted), gate_outcome
    admission_id = gate_outcome.canonical_invoice.canonical_invoice_id
    outcome = stack.di.open_digital_invoice(admission_id)
    assert isinstance(outcome, DigitalInvoiceRequestRefused), outcome
    assert len(stack.di.digital_invoices()) == 0


def test_open_tampered_canonical_invoice_fails_closed(stack, tmp_path):
    _, invoice_id = stack.assemble_di_invoice(label="di-open-5")
    stack.open_ok(invoice_id)
    # second invoice for the tamper probe
    _, invoice2 = stack.assemble_di_invoice(parts=unique_di_pages(),
                                            label="di-open-5b")
    stack.open_ok(invoice2)
    # tamper with invoice2's canonical row directly (P6.2 store)
    import sqlite3
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        conn.execute("UPDATE canonical_invoices SET capture_id = 'forged' "
                     "WHERE invoice_id = ?", (invoice2,))
        conn.commit()
    finally:
        conn.close()
    outcome = stack.di.read_digital_invoice(invoice2)
    from digital_invoice import DigitalInvoiceReadIntegrityFailure
    assert isinstance(outcome, DigitalInvoiceReadIntegrityFailure), outcome


def test_open_two_invoices_two_digital_invoices(stack):
    _, inv1 = stack.assemble_di_invoice(label="di-open-6a")
    _, inv2 = stack.assemble_di_invoice(parts=unique_di_pages(),
                                        label="di-open-6b")
    stack.open_ok(inv1)
    stack.open_ok(inv2)
    assert len(stack.di.digital_invoices()) == 2
    assert len({r.invoice_id for r in stack.di.digital_invoices()}) == 2


def test_trace_digital_invoice_head_link_onto_intact_p62_chain(stack):
    _, invoice_id = stack.assemble_di_invoice(label="di-open-7")
    stack.open_ok(invoice_id)
    stack.advance_ok(invoice_id, "mark_extracted")
    trace = stack.di.trace_digital_invoice(invoice_id)
    assert isinstance(trace, DigitalInvoiceTraceSuccess), trace
    assert trace.current_state == "EXTRACTED"
    assert any(l.startswith("digital_invoice:") for l in trace.chain)
    assert any(l.startswith("canonical_invoice:") for l in trace.chain)
    # the P6.2 chain itself is intact and consumed, not re-walked here
    p62 = stack.assembly.trace_assembled_invoice(invoice_id)
    assert isinstance(p62, AssemblyTraceSuccess), p62


def test_trace_unknown_invoice_refused(stack):
    from digital_invoice import DigitalInvoiceTraceRefused
    outcome = stack.di.trace_digital_invoice("no-such-invoice")
    assert isinstance(outcome, DigitalInvoiceTraceRefused), outcome


# import used by the admission test
from canonicalization import CanonicalizationAccepted  # noqa: E402
