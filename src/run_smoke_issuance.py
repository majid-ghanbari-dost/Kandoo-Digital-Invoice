"""Cold-start smoke check for the composed issuance path — runs the complete
frozen external flow (AS-01) end-to-end without pytest:

  ordered raw pages → Capture → Reconstruction → Extraction → Evidence Binding
  → Normalization → Derivation → Validation → WP-5.2 DOMAIN STATE
  → WP-6.1 CANONICALIZATION GATE → WP-6.2 CANONICAL ASSEMBLY
  → WP-10.1 DIGITAL INVOICE LIFECYCLE (explicit acts only)
  → ISSUED Digital Invoice + whole-chain trace down to Capture S1.

Also proves the composition boundary: nothing is automatic, replays/restarts
are idempotent, refusals leave zero residue, tampered rows are withheld, no
purge/CLI/SQL surface is reachable from the composed layer, and the workspace
owns exactly the twelve frozen stores.

Usage: python3 kandoo/src/run_smoke_issuance.py /tmp/kandoo-issuance-smoke
"""
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture.retention import PURGE_EXECUTION_ALLOWED, request_purge  # noqa: E402
from digital_invoice import (                                          # noqa: E402
    DigitalInvoiceOpenReplay,
    DigitalInvoiceOpened,
    DigitalInvoiceReadIntegrityFailure,
    DigitalInvoiceReadRefused,
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
from issuance import DIGITAL_INVOICE_DB, DigitalIssuanceWorkspace  # noqa: E402
from pipeline import PipelineStopped                                 # noqa: E402
from validation import ReferenceValidationRulesV1                    # noqa: E402

STORE_NAMES = {"capture.db", "recon.db", "recon.evidence.db", "extraction.db",
               "binding.db", "norm.db", "deriv.db", "val.db", "vsm.db",
               "gate.db", "assembly.db", DIGITAL_INVOICE_DB}

DECLARED_RULES = dict(ReferenceValidationRulesV1(
    tolerance="0.02", precision=2, mode="HALF_UP"))
DECLARATION = dict(
    source_label="issuance-smoke",
    declared_origin="HOLOO_CAPTURE",
    identity_binding={"INVOICE_NUMBER": "invoice.number",
                      "INVOICE_DATE": "invoice.date",
                      "INVOICE_TOTAL": "total.net"},
    line_binding={0: {"LINE_QUANTITY": "line.0.quantity",
                      "LINE_UNIT_PRICE": "line.0.unit_price",
                      "LINE_TOTAL": "line.0.total"}},
    ruleset_id="issuance-smoke-declared", ruleset_version="1")


def pages(number):
    return [f"invoice.number={number}\ninvoice.date=2026-10-01\n"
            f"total.net=1000.00\ntax.amount=80\n"
            f"line.0.quantity=2\nline.0.unit_price=500\n"
            f"line.0.total=1000\n".encode("utf-8")]


def entity_counts(base):
    """Business/stage entities — reads, refusals and replays never grow them."""
    counts = {}
    for db in sorted(Path(base).glob("*.db")):
        if db.name == "recon.evidence.db":
            continue
        with sqlite3.connect(db) as connection:
            for (table,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"):
                counts[(db.name, table)] = connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    return counts


STEPS = []


def step(number, title):
    def register(function):
        STEPS.append((number, title, function))
        return function
    return register


def open_workspace(base):
    return DigitalIssuanceWorkspace(Path(base),
                                    validation_rules=DECLARED_RULES)


def advance_acts(service, invoice_id):
    """The three explicit progression acts — never an automatic transition."""
    for act, state in ((service.mark_extracted, STATE_EXTRACTED),
                       (service.mark_validated, STATE_VALIDATED),
                       (service.issue, STATE_ISSUED)):
        outcome = act(invoice_id, "issuance smoke")
        assert isinstance(outcome, LifecycleAdvanced), outcome
        assert outcome.current_state == state, outcome


@step(1, "cold start: raw pages → verified Canonical Invoice (fields, lines, "
         "provenance) through the frozen capture-to-canonical composition")
def step1(ctx):
    submission = ctx["service"].submit(pages("ISS-SMOKE-A"), **DECLARATION)
    assert submission.completed, submission.pipeline
    assert submission.invoice_id == submission.pipeline.trace.invoice_id
    invoice = submission.pipeline.invoice.invoice
    assert invoice.line_count == 1 and invoice.field_count >= 1, invoice
    assert {field.provenance for field in submission.pipeline.invoice.fields} \
        == {"EXTRACTED", "DERIVED"}
    assert submission.pipeline.invoice.lines, "no canonical lines"
    ctx["a"] = submission.invoice_id
    ctx["capture_a"] = submission.capture_id
    ctx["s1_a"] = invoice.capture_s1


@step(2, "the submission opened nothing: the verified read and all five "
         "lifecycle acts are refused before an explicit open (explicit acts)")
def step2(ctx):
    service, invoice_id = ctx["service"], ctx["a"]
    before = entity_counts(ctx["base"])
    assert service.opened_digital_invoices() == ()
    assert isinstance(service.read(invoice_id), DigitalInvoiceReadRefused)
    assert service.awaiting_digital_invoice() == (invoice_id,)
    for call in (service.mark_extracted, service.mark_validated, service.issue,
                 service.revoke):
        assert isinstance(call(invoice_id), LifecycleRequestRefused), call
    assert isinstance(service.supersede(invoice_id, "ISS-SMOKE-NOPE"),
                      LifecycleRequestRefused)
    assert entity_counts(ctx["base"]) == before, "zero-residue refusal violated"


@step(3, "explicit acts: open → DRAFT → EXTRACTED → VALIDATED → ISSUED on the "
         "frozen vocabulary (AS-03), each act re-verifying the LIVE P6.2 chain")
def step3(ctx):
    service, invoice_id = ctx["service"], ctx["a"]
    opened = service.open_digital_invoice(invoice_id)
    assert isinstance(opened, DigitalInvoiceOpened), opened
    status = service.status(invoice_id)
    assert (status.exists, status.verified, status.current_state) \
        == (True, True, STATE_DRAFT), status
    advance_acts(service, invoice_id)
    status = service.status(invoice_id)
    assert status.current_state == STATE_ISSUED and status.verified, status
    assert status.outcome.record.capture_s1 == ctx["s1_a"]
    assert [event.event_seq for event in status.outcome.events] == [0, 1, 2]


@step(4, "idempotent replays: submit replay, open replay and act replay return "
         "the durable facts with ZERO new rows (D-03)")
def step4(ctx):
    service, invoice_id = ctx["service"], ctx["a"]
    before = entity_counts(ctx["base"])
    replay = service.submit(pages("ISS-SMOKE-A"), **DECLARATION)
    assert replay.completed and replay.invoice_id == invoice_id
    assert replay.capture_id == ctx["capture_a"]
    assert isinstance(service.open_digital_invoice(invoice_id),
                      DigitalInvoiceOpenReplay)
    assert isinstance(service.issue(invoice_id), LifecycleReplay)
    assert entity_counts(ctx["base"]) == before, "replay grew business entities"


@step(5, "after a restart the composed path still serves the verified ISSUED "
         "fact and the whole-chain trace down to Capture S1")
def step5(ctx):
    service = ctx["service"]
    status = service.status(ctx["a"])
    assert (status.exists, status.verified, status.current_state) \
        == (True, True, STATE_ISSUED), status
    trace = service.trace(ctx["a"])
    assert isinstance(trace, DigitalInvoiceTraceSuccess), trace
    joined = "\n".join(trace.chain)
    for layer in ("digital_invoice:", "issued_invoice:", "admission:",
                  "canonical_invoice:", "gate_decision:", "domain_state:",
                  "validation[", "normalization:", "extraction:", "binding:",
                  "document:", "capture:"):
        assert layer in joined, f"trace lost {layer}"
    assert ctx["s1_a"][:12] in joined, "trace does not reach Capture S1"
    assert service.awaiting_digital_invoice() == ()


@step(6, "resume: an invoice submitted before a stop stays outstanding after "
         "restart until an explicit act opens it (no automatic behaviour)")
def step6(ctx):
    service = ctx["service"]
    submitted = service.submit(pages("ISS-SMOKE-B"), **DECLARATION)
    assert submitted.completed
    ctx["b"] = submitted.invoice_id
    assert service.awaiting_digital_invoice() == (ctx["b"],)
    with open_workspace(ctx["base"]) as reopened:
        assert reopened.service.awaiting_digital_invoice() == (ctx["b"],)
        assert isinstance(reopened.service.status(ctx["b"]).outcome,
                          DigitalInvoiceReadRefused)
        assert isinstance(reopened.service.open_digital_invoice(ctx["b"]),
                          DigitalInvoiceOpened)
        assert reopened.service.awaiting_digital_invoice() == ()


@step(7, "refusals stay honest: skips/backward/terminal-exit/unknown invoices "
         "and a REVIEW stop never produce a Digital Invoice (zero residue)")
def step7(ctx):
    service, invoice_id = ctx["service"], ctx["b"]
    before = entity_counts(ctx["base"])
    assert isinstance(service.mark_validated(invoice_id),
                      LifecycleRequestRefused)
    assert isinstance(service.issue(invoice_id), LifecycleRequestRefused)
    assert isinstance(service.revoke(invoice_id), LifecycleRequestRefused)
    assert isinstance(service.mark_extracted("ISS-UNKNOWN"),
                      LifecycleRequestRefused)
    assert isinstance(service.open_digital_invoice("ISS-UNKNOWN"),
                      DigitalInvoiceRequestRefused)
    assert entity_counts(ctx["base"]) == before, "refusal left residue"

    # A REVIEW stop legitimately writes upstream stage rows (the frozen
    # pipeline's own durable work) but can never produce an invoice or a
    # Digital Invoice.
    invoices_before = len(service.issued_canonical_invoices())
    digital_before = len(service.opened_digital_invoices())
    review_pages = [pages("ISS-SMOKE-R")[0].replace(b"tax.amount=80\n", b"")]
    stopped = service.submit(review_pages, **DECLARATION)
    assert not stopped.completed and isinstance(stopped.pipeline, PipelineStopped)
    assert stopped.pipeline.stage == "gate"
    assert stopped.pipeline.outcome.decision.decision == "REVIEW"
    assert len(service.issued_canonical_invoices()) == invoices_before
    assert len(service.opened_digital_invoices()) == digital_before
    assert service.awaiting_digital_invoice() == ()


@step(8, "supersede/revoke reach their terminal states, a tampered row is "
         "withheld, and the composition boundary holds (no purge/CLI/SQL)")
def step8(ctx):
    service, base = ctx["service"], ctx["base"]
    advance_acts(service, ctx["b"])
    superseded = service.supersede(ctx["a"], ctx["b"], "corrected invoice")
    assert isinstance(superseded, LifecycleAdvanced), superseded
    assert superseded.current_state == STATE_SUPERSEDED
    revoked = service.revoke(ctx["b"], "cancelled")
    assert isinstance(revoked, LifecycleAdvanced), revoked
    assert revoked.current_state == STATE_REVOKED

    with sqlite3.connect(Path(base) / DIGITAL_INVOICE_DB) as connection:
        connection.execute("UPDATE digital_invoices SET origin = 'KANDOO_SALE' "
                           "WHERE invoice_id = ?", (ctx["a"],))
    status = service.status(ctx["a"])
    assert status.exists and not status.verified \
        and status.current_state is None, status
    assert isinstance(status.outcome, DigitalInvoiceReadIntegrityFailure)
    assert isinstance(service.trace(ctx["a"]),
                      DigitalInvoiceTraceIntegrityFailure)

    assert PURGE_EXECUTION_ALLOWED is False
    assert request_purge("any-capture-id").executed is False
    assert not hasattr(service, "request_purge")
    assert not hasattr(service, "request_purge")
    import issuance.workspace as workspace_module
    assert not [name for name in ("execute", "executemany", "request_purge",
                                  "remove", "system", "popen")
                if hasattr(workspace_module, name)]
    assert {path.name for path in Path(base).iterdir()} == STORE_NAMES, \
        "workspace owns more than the twelve frozen stores"
    assert not [path for path in Path(base).iterdir() if path.is_dir()]
    assert service._workspace.digital_invoice._assembly \
        is service._workspace.pipeline_workspace.assembly


def main(base_dir):
    base = Path(base_dir)
    if base.exists():
        shutil.rmtree(base)
    print(f"Digital issuance smoke — base: {base}")
    ctx = {"base": base}
    with open_workspace(base) as workspace:
        ctx["service"] = workspace.service
        for number, title, function in STEPS[:4]:
            function(ctx)
            print(f"  step {number}: OK — {title}")
        assert {path.name for path in base.iterdir()} == STORE_NAMES
        with open_workspace(base) as restarted:      # simulated process restart
            ctx["service"] = restarted.service
            for number, title, function in STEPS[4:]:
                function(ctx)
                print(f"  step {number}: OK — {title}")
        ctx["service"] = workspace.service
    print(f"SMOKE OK — {len(STEPS)} steps")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else "/tmp/kandoo-issuance-smoke"))
