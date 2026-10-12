"""Composed product path: raw pages → Canonical Invoice → explicit Digital
Invoice lifecycle, on the real stores, including replay/restart/fail-closure."""
import sqlite3

import pytest

from digital_invoice import (
    DigitalInvoiceOpenReplay,
    DigitalInvoiceOpened,
    DigitalInvoiceReadIntegrityFailure,
    DigitalInvoiceReadRefused,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceRequestRefused,
    DigitalInvoiceTraceIntegrityFailure,
    DigitalInvoiceTraceSuccess,
    LifecycleAdvanced,
    LifecycleReplay,
    LifecycleRequestRefused,
    STATE_DRAFT,
    STATE_EXTRACTED,
    STATE_ISSUED,
    STATE_REVOKED,
    STATE_SUPERSEDED,
    STATE_VALIDATED,
)
from issuance import DIGITAL_INVOICE_DB, DigitalIssuanceWorkspace
from pipeline import PipelineStopped


def entity_counts(path):
    """Business/stage entities must not grow on replay (evidence logs may)."""
    counts = {}
    for db in sorted(path.glob("*.db")):
        if db.name == "recon.evidence.db":
            continue
        with sqlite3.connect(db) as connection:
            for (table,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"):
                counts[(db.name, table)] = connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    return counts


def advance_to_issued(service, invoice_id, note="issuance-flow-test"):
    assert isinstance(service.open_digital_invoice(invoice_id),
                      DigitalInvoiceOpened)
    for act, state in ((service.mark_extracted, STATE_EXTRACTED),
                       (service.mark_validated, STATE_VALIDATED),
                       (service.issue, STATE_ISSUED)):
        outcome = act(invoice_id, note)
        assert isinstance(outcome, LifecycleAdvanced), outcome
        assert outcome.current_state == state
    return invoice_id


def test_product_path_from_raw_pages_to_issued_digital_invoice(
        workspace, unique_pages, declaration):
    submission = workspace.service.submit(unique_pages(), **declaration)
    assert submission.completed
    invoice_id = submission.invoice_id
    assert invoice_id == submission.pipeline.trace.invoice_id
    invoice = submission.pipeline.invoice.invoice
    assert invoice.line_count == 1
    assert invoice.customer_reference is None
    assert {field.provenance for field in submission.pipeline.invoice.fields} \
        == {"EXTRACTED", "DERIVED"}

    # The submission performed NO Digital Invoice action of any kind.
    assert workspace.service.opened_digital_invoices() == ()
    assert isinstance(workspace.service.read(invoice_id),
                      DigitalInvoiceReadRefused)
    assert workspace.service.awaiting_digital_invoice() == (invoice_id,)

    advance_to_issued(workspace.service, invoice_id)
    status = workspace.service.status(invoice_id)
    assert (status.exists, status.verified) == (True, True)
    assert status.current_state == STATE_ISSUED
    assert status.detail == ""
    assert (isinstance(status.outcome, DigitalInvoiceReadSuccess)
            and status.outcome.current_state == STATE_ISSUED)
    # the composed read carries the re-verified P6.2 invoice (pointer
    # discipline: content is only ever re-read live, never stored here).
    assert status.outcome.invoice_read.invoice.invoice_id == invoice_id
    assert status.outcome.record.capture_s1 == invoice.capture_s1

    trace = workspace.service.trace(invoice_id)
    assert isinstance(trace, DigitalInvoiceTraceSuccess), trace
    assert trace.current_state == STATE_ISSUED
    assert trace.invoice_id == invoice_id
    assert len(trace.chain) > 1 and trace.chain[0].startswith("digital_invoice:")


def test_submission_alone_never_opens_or_advances_anything(
        workspace, unique_pages, declaration, tmp_path):
    submission = workspace.service.submit(unique_pages(), **declaration)
    invoice_id = submission.invoice_id
    before = entity_counts(tmp_path)
    assert isinstance(workspace.service.mark_extracted(invoice_id),
                      LifecycleRequestRefused)
    assert isinstance(workspace.service.mark_validated(invoice_id),
                      LifecycleRequestRefused)
    assert isinstance(workspace.service.issue(invoice_id),
                      LifecycleRequestRefused)
    assert isinstance(workspace.service.revoke(invoice_id),
                      LifecycleRequestRefused)
    assert isinstance(workspace.service.supersede(invoice_id, "ISS-SEQ-9999"),
                      LifecycleRequestRefused)
    assert workspace.service.opened_digital_invoices() == ()
    assert entity_counts(tmp_path) == before


def test_replay_and_restart_are_idempotent(tmp_path, rules, unique_pages,
                                           declaration):
    pages = unique_pages()
    with DigitalIssuanceWorkspace(tmp_path, validation_rules=rules) as ws:
        first = ws.service.submit(pages, **declaration)
        advance_to_issued(ws.service, first.invoice_id)
        before = entity_counts(tmp_path)

        replay = ws.service.submit(pages, **declaration)
        assert replay.completed and replay.invoice_id == first.invoice_id
        assert isinstance(ws.service.open_digital_invoice(first.invoice_id),
                          DigitalInvoiceOpenReplay)
        assert isinstance(ws.service.issue(first.invoice_id), LifecycleReplay)
        assert entity_counts(tmp_path) == before

    with DigitalIssuanceWorkspace(tmp_path, validation_rules=rules) as reopened:
        assert entity_counts(tmp_path) == before
        assert reopened.service.awaiting_digital_invoice() == ()
        status = reopened.service.status(first.invoice_id)
        assert (status.verified, status.current_state) == (True, STATE_ISSUED)
        assert reopened.service.submit(pages, **declaration).invoice_id \
            == first.invoice_id
        assert isinstance(reopened.service.trace(first.invoice_id),
                          DigitalInvoiceTraceSuccess)
        assert entity_counts(tmp_path) == before


def test_resume_after_a_stop_before_the_open_act(tmp_path, rules,
                                                unique_pages, declaration):
    with DigitalIssuanceWorkspace(tmp_path, validation_rules=rules) as ws:
        first = ws.service.submit(unique_pages(), **declaration)
        second = ws.service.submit(unique_pages(), **declaration)
        assert first.invoice_id != second.invoice_id
        assert set(ws.service.awaiting_digital_invoice()) \
            == {first.invoice_id, second.invoice_id}
        assert len(ws.service.issued_canonical_invoices()) == 2

    # The application stopped between submission and the explicit open act:
    # nothing was opened automatically, and the outstanding set is durable.
    with DigitalIssuanceWorkspace(tmp_path, validation_rules=rules) as resumed:
        outstanding = resumed.service.awaiting_digital_invoice()
        assert set(outstanding) == {first.invoice_id, second.invoice_id}
        opened = resumed.service.open_digital_invoice(outstanding[0])
        assert isinstance(opened, DigitalInvoiceOpened)
        assert resumed.service.awaiting_digital_invoice() \
            == (outstanding[1],)
        assert resumed.service.status(outstanding[0]).current_state == STATE_DRAFT


def test_review_stop_never_reaches_the_digital_invoice(workspace,
                                                       unique_pages, declaration):
    pages = unique_pages()
    pages = [pages[0].replace(b"tax.amount=80\n", b"")]
    submission = workspace.service.submit(pages, **declaration)
    assert not submission.completed
    assert submission.invoice_id is None
    assert isinstance(submission.pipeline, PipelineStopped)
    assert submission.pipeline.stage == "gate"
    assert submission.pipeline.outcome.decision.decision == "REVIEW"
    assert workspace.service.opened_digital_invoices() == ()
    assert workspace.service.awaiting_digital_invoice() == ()
    refused = workspace.service.open_digital_invoice("ISS-NOT-A-CANONICAL-ID")
    assert isinstance(refused, DigitalInvoiceRequestRefused), refused


def test_refusals_and_foreign_invoices_leave_zero_residue(
        workspace, tmp_path, rules, unique_pages, declaration):
    invoice_id = workspace.service.submit(unique_pages(), **declaration).invoice_id
    assert isinstance(workspace.service.open_digital_invoice(invoice_id),
                      DigitalInvoiceOpened)
    before = entity_counts(tmp_path)

    # Skip, backward and terminal-exit attempts are refused with zero residue.
    assert isinstance(workspace.service.mark_validated(invoice_id),
                      LifecycleRequestRefused)
    assert isinstance(workspace.service.issue(invoice_id),
                      LifecycleRequestRefused)
    assert isinstance(workspace.service.revoke(invoice_id),
                      LifecycleRequestRefused)
    assert isinstance(workspace.service.supersede(invoice_id, "ISS-SEQ-0000"),
                      LifecycleRequestRefused)
    assert isinstance(workspace.service.mark_extracted("UNKNOWN-INVOICE"),
                      LifecycleRequestRefused)
    assert workspace.service.status(invoice_id).current_state == STATE_DRAFT
    assert entity_counts(tmp_path) == before

    # An invoice of ANOTHER workspace is not readable through this one.
    with DigitalIssuanceWorkspace(tmp_path / "other",
                                  validation_rules=rules) as other:
        foreign = other.service.submit(unique_pages(), **declaration)
        assert isinstance(
            workspace.service.open_digital_invoice(foreign.invoice_id),
            DigitalInvoiceRequestRefused)


def test_supersede_and_revoke_through_the_composed_surface(
        workspace, unique_pages, declaration):
    first = workspace.service.submit(unique_pages(), **declaration).invoice_id
    second = workspace.service.submit(unique_pages(), **declaration).invoice_id
    advance_to_issued(workspace.service, first)
    advance_to_issued(workspace.service, second)

    superseded = workspace.service.supersede(first, second, "corrected invoice")
    assert isinstance(superseded, LifecycleAdvanced), superseded
    assert superseded.current_state == STATE_SUPERSEDED
    revoked = workspace.service.revoke(second, "cancelled by store")
    assert isinstance(revoked, LifecycleAdvanced), revoked
    assert revoked.current_state == STATE_REVOKED

    assert workspace.service.status(first).current_state == STATE_SUPERSEDED
    assert workspace.service.status(second).current_state == STATE_REVOKED
    assert isinstance(workspace.service.trace(first),
                      DigitalInvoiceTraceSuccess)


@pytest.mark.parametrize("target", ["digital_invoice", "canonical_invoice"])
def test_tampered_durable_rows_are_withheld_never_served(
        workspace, tmp_path, unique_pages, declaration, target):
    invoice_id = workspace.service.submit(unique_pages(), **declaration).invoice_id
    advance_to_issued(workspace.service, invoice_id)

    if target == "digital_invoice":
        with sqlite3.connect(tmp_path / DIGITAL_INVOICE_DB) as connection:
            connection.execute(
                "UPDATE digital_invoices SET origin = 'KANDOO_SALE' "
                "WHERE invoice_id = ?", (invoice_id,))
    else:
        with sqlite3.connect(tmp_path / "assembly.db") as connection:
            connection.execute(
                "UPDATE canonical_invoices SET document_id = 'forged'")

    status = workspace.service.status(invoice_id)
    assert status.exists is True
    assert status.verified is False
    assert status.current_state is None
    assert isinstance(status.outcome, DigitalInvoiceReadIntegrityFailure)
    assert status.detail
    assert isinstance(workspace.service.trace(invoice_id),
                      DigitalInvoiceTraceIntegrityFailure)


@pytest.mark.parametrize("field,value", [
    ("declared_origin", "KANDOO_SALE"), ("declared_origin", "invented"),
    ("identity_binding", {"invented": "invoice.number"}),
    ("line_binding", {0: {}}), ("ruleset_id", ""), ("source_label", None),
])
def test_malformed_declarations_never_touch_the_workspace(
        workspace, unique_pages, declaration, tmp_path, field, value):
    declaration[field] = value
    before = entity_counts(tmp_path)
    with pytest.raises(ValueError):
        workspace.service.submit(unique_pages(), **declaration)
    assert entity_counts(tmp_path) == before
    assert workspace.service.issued_canonical_invoices() == ()
    assert workspace.service.opened_digital_invoices() == ()


def test_whole_chain_trace_covers_every_frozen_layer(
        workspace, unique_pages, declaration):
    invoice_id = workspace.service.submit(unique_pages(), **declaration).invoice_id
    advance_to_issued(workspace.service, invoice_id)
    trace = workspace.service.trace(invoice_id)
    assert isinstance(trace, DigitalInvoiceTraceSuccess), trace
    joined = "\n".join(trace.chain)
    for layer in ("digital_invoice:", "issued_invoice:", "admission:",
                  "canonical_invoice:", "gate_decision:", "domain_state:",
                  "validation[", "normalization:", "extraction:", "binding:",
                  "document:", "capture:"):
        assert layer in joined, f"missing {layer} in\n{joined}"
    assert "S1" in joined
