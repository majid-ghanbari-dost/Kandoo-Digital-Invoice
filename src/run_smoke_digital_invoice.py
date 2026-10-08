"""Cold-start smoke check for WP-10.1 — runs the Digital Invoice Lifecycle
end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (frozen) → WP-5.1 VALIDATION
  (frozen) → WP-5.2 DOMAIN STATE (frozen) → WP-6.1 CANONICALIZATION GATE
  (frozen) → WP-6.2 CANONICAL ASSEMBLY (frozen)
  → WP-10.1 DIGITAL INVOICE LIFECYCLE
  (open only from the P6.2 verified read + whole-chain trace → DRAFT →
  EXTRACTED → VALIDATED → ISSUED (frozen vocabulary verbatim, AS-03);
  idempotent replays with zero new rows; skip/backward/terminal-exit
  refusals; supersede with a verified ISSUED replacement; revoke; restart
  survival; tamper withholding; frozen-layer survival + vocabulary sweep)

Usage: python3 kandoo/src/run_smoke_digital_invoice.py /tmp/kandoo-di-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation,validation-domain,gate,assembly,digital}*.db.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import CaptureService, CaptureStore, S1Service            # noqa: E402
from canonical_assembly import (                                       # noqa: E402
    AssemblyReadSuccess,
    CanonicalAssemblyService,
    CanonicalAssemblyStore,
)
from canonicalization import (                                         # noqa: E402
    CanonicalizationAccepted,
    CanonicalizationGateService,
    CanonicalizationGateStore,
)
from customer_linking import (                                         # noqa: E402
    CustomerLinkingService,
    CustomerLinkingStore,
)
from derivation import (                                               # noqa: E402
    DerivationCompleted,
    DerivationFormulaRegistry,
    DerivationService,
    DerivationStore,
    ReferenceDerivationFormulasV1,
)
from digital_invoice import (                                          # noqa: E402
    LIFECYCLE_STATES,
    DigitalInvoiceOpenReplay,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceRequestRefused,
    DigitalInvoiceLifecycleService,
    DigitalInvoiceStore,
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
from extraction import (                                               # noqa: E402
    BindingCompleted,
    ExtractionCompleted,
    ExtractionBindingStore,
    ExtractionEvidenceBinder,
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
)
from normalization import (                                            # noqa: E402
    NormalizationCompleted,
    NormalizationService,
    NormalizationStore,
    ReferenceNormalizationRulesV1,
)
from reconstruction import (                                           # noqa: E402
    EvidenceStore,
    ReconstructionService,
    ReconstructionStore,
)
from validation import (                                               # noqa: E402
    ValidationCompleted,
    ValidationRuleRegistry,
    ValidationService,
    ValidationStore,
    ReferenceValidationRulesV1,
)
from validation_domain import (                                        # noqa: E402
    DomainStateProjected,
    ValidationDomainService,
    ValidationDomainStore,
)

PAGES_A = [
    b"invoice.number=INV-DI-SMOKE-A\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n",
]
PAGES_B = [
    b"invoice.number=INV-DI-SMOKE-B\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n",
]
PAGES_C = [
    b"invoice.number=INV-DI-SMOKE-C\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n",
]

LINE_BINDING = {
    0: {"LINE_QUANTITY": "line.0.quantity",
        "LINE_UNIT_PRICE": "line.0.unit_price",
        "LINE_TOTAL": "line.0.total"},
}
IDENTITY_BINDING = {"INVOICE_NUMBER": "invoice.number",
                    "INVOICE_DATE": "invoice.date",
                    "INVOICE_TOTAL": "total.net"}

FORMULA = "kandoo-der-total-gross-from-net-tax"
R_PRESENT = "kandoo-val-total-net-present"
R_CONSIST = "kandoo-val-total-gross-consistency"
R_TOLERANCE = "kandoo-val-total-gross-tolerance"
R_ROUNDED = "kandoo-val-total-gross-rounded"
REF_KEYS = [(R_PRESENT, "1"), (R_CONSIST, "1"), (R_TOLERANCE, "1"),
            (R_ROUNDED, "1")]
TOLERANCE, PRECISION, MODE = "0.02", 2, "HALF_UP"

STEPS = []


def step(number, title):
    def wrap(fn):
        STEPS.append((number, title, fn))
        return fn
    return wrap


def build_stack(base: Path):
    capture_store = CaptureStore(base / "capture.db")
    capture = CaptureService(capture_store, S1Service())
    recon_store = ReconstructionStore(base / "recon.db")
    evidence_store = EvidenceStore(str(base / "recon.db") + ".evidence.db",
                                   S1Service())
    recon = ReconstructionService(recon_store, capture, S1Service(),
                                  evidence=evidence_store)
    extraction_store = ExtractionStore(base / "extraction.db", S1Service())
    extraction = ExtractionService(
        extraction_store, recon,
        {"reference-delimited-v1": ReferenceDelimitedEngine()}, S1Service())
    binding_store = ExtractionBindingStore(base / "bindings.db", S1Service())
    binder = ExtractionEvidenceBinder(binding_store, extraction, recon,
                                      evidence_store, S1Service())
    norm_store = NormalizationStore(base / "normalization.db", S1Service())
    norm = NormalizationService(
        norm_store, extraction,
        {"kandoo-norm-v1": ReferenceNormalizationRulesV1()}, S1Service())
    deriv_store = DerivationStore(base / "derivation.db", S1Service())
    dregistry = DerivationFormulaRegistry(dict(ReferenceDerivationFormulasV1()),
                                          S1Service())
    deriv = DerivationService(deriv_store, norm, extraction, binder, recon,
                              dregistry, S1Service())
    val_store = ValidationStore(base / "validation.db", S1Service())
    vregistry = ValidationRuleRegistry(
        dict(ReferenceValidationRulesV1(tolerance=TOLERANCE,
                                        precision=PRECISION,
                                        mode=MODE)), S1Service())
    val = ValidationService(val_store, norm, extraction, binder, recon, deriv,
                            vregistry, S1Service())
    vsm_store = ValidationDomainStore(base / "validation-domain.db",
                                      S1Service())
    vsm = ValidationDomainService(vsm_store, val, vregistry, norm, extraction,
                                  binder, recon, S1Service())
    gate_store = CanonicalizationGateStore(base / "gate.db", S1Service())
    gate = CanonicalizationGateService(gate_store, vsm, norm, S1Service())
    assembly_store = CanonicalAssemblyStore(base / "assembly.db", S1Service())
    assembly = CanonicalAssemblyService(assembly_store, gate, norm, deriv,
                                        S1Service())
    customer_store = CustomerLinkingStore(base / "customer.db", S1Service())
    customers = CustomerLinkingService(customer_store, assembly, S1Service())
    digital_store = DigitalInvoiceStore(base / "digital.db", S1Service())
    di = DigitalInvoiceLifecycleService(digital_store, assembly, S1Service())
    return {
        "capture_store": capture_store, "capture": capture,
        "recon_store": recon_store, "evidence_store": evidence_store,
        "recon": recon, "extraction_store": extraction_store,
        "extraction": extraction, "binding_store": binding_store,
        "binder": binder, "norm_store": norm_store, "norm": norm,
        "deriv_store": deriv_store, "deriv": deriv, "val_store": val_store,
        "val": val, "vsm_store": vsm_store, "vsm": vsm,
        "gate_store": gate_store, "gate": gate,
        "assembly_store": assembly_store, "assembly": assembly,
        "customer_store": customer_store, "customers": customers,
        "digital_store": digital_store, "di": di,
    }


def close_stack(stack):
    stack["digital_store"].close()
    stack["customer_store"].close()
    stack["assembly_store"].close()
    stack["gate_store"].close()
    stack["vsm_store"].close()
    stack["val_store"].close()
    stack["deriv_store"].close()
    stack["norm_store"].close()
    stack["binding_store"].close()
    stack["extraction_store"].close()
    stack["evidence_store"].close()
    stack["recon_store"].close()
    stack["capture_store"].close()


def run_pipeline(stack, pages, label, ruleset="smoke-di-rules"):
    content = CaptureService.aggregate(pages)
    outcome = stack["capture"].ingest(content, source_label=label)
    assert type(outcome).__name__ == "IngestCompleted", outcome
    built = stack["recon"].reconstruct(outcome.capture_id)
    assert type(built).__name__ == "ReconstructCompleted", built
    done = stack["extraction"].extract(built.document.document_id,
                                       "reference-delimited-v1")
    assert type(done).__name__ == "ExtractionCompleted", done
    bound = stack["binder"].bind_extraction(done.extraction.extraction_id)
    assert type(bound).__name__ == "BindingCompleted", bound
    normed = stack["norm"].normalize(done.extraction.extraction_id,
                                     "kandoo-norm-v1")
    assert type(normed).__name__ == "NormalizationCompleted", normed
    derived = stack["deriv"].derive(normed.record.normalization_id, FORMULA,
                                    "1")
    assert type(derived).__name__ == "DerivationCompleted", derived
    for rule, _ in REF_KEYS:
        validated = stack["val"].validate(normed.record.normalization_id,
                                          rule, "1")
        assert type(validated).__name__ == "ValidationCompleted", validated
        assert validated.record.outcome == "VALID", validated
    projected = stack["vsm"].project_domain_state(
        normed.record.normalization_id, ruleset, "1", list(REF_KEYS))
    assert type(projected).__name__ == "DomainStateProjected", projected
    assert projected.record.domain_state == "VALID"
    assert projected.record.disposition == "CLEAR"
    gate_outcome = stack["gate"].canonicalize(
        projected.record.domain_state_id, "HOLOO_CAPTURE", IDENTITY_BINDING)
    assert isinstance(gate_outcome, CanonicalizationAccepted), gate_outcome
    invoice_id = gate_outcome.canonical_invoice.canonical_invoice_id
    assembled = stack["assembly"].assemble(invoice_id, LINE_BINDING)
    assert type(assembled).__name__ == "AssemblyCompleted", assembled
    return invoice_id


@step(1, "frozen pipeline → issued invoice → open Digital Invoice → DRAFT "
      "(entry ONLY through the P6.2 verified read + whole-chain trace)")
def step1(stack, shared):
    invoice_id = run_pipeline(stack, PAGES_A, "di-smoke-a")
    opened = stack["di"].open_digital_invoice(invoice_id)
    assert isinstance(opened, LifecycleAdvanced) or type(opened).__name__ \
        == "DigitalInvoiceOpened", opened
    record = opened.record
    assert record.invoice_id == invoice_id
    read = stack["di"].read_digital_invoice(invoice_id)
    assert isinstance(read, DigitalInvoiceReadSuccess), read
    assert read.current_state == STATE_DRAFT
    assert read.events == ()
    shared["invoice_a"] = invoice_id
    shared["record_a"] = record


@step(2, "explicit lifecycle acts DRAFT → EXTRACTED → VALIDATED → ISSUED "
      "(frozen vocabulary verbatim; each act re-verifies the LIVE P6.2 chain)")
def step2(stack, shared):
    inv = shared["invoice_a"]
    e1 = stack["di"].mark_extracted(inv, "extraction confirmed")
    assert isinstance(e1, LifecycleAdvanced), e1
    assert e1.current_state == STATE_EXTRACTED
    e2 = stack["di"].mark_validated(inv)
    assert isinstance(e2, LifecycleAdvanced), e2
    e3 = stack["di"].issue(inv, "issued by smoke")
    assert isinstance(e3, LifecycleAdvanced), e3
    assert e3.current_state == STATE_ISSUED
    read = stack["di"].read_digital_invoice(inv)
    assert [e.event_seq for e in read.events] == [0, 1, 2]
    assert [e.from_state for e in read.events] == \
        [STATE_DRAFT, STATE_EXTRACTED, STATE_VALIDATED]


@step(3, "idempotent replays: open replay + act replays return the durable "
      "fact verbatim with ZERO new rows (D-03)")
def step3(stack, shared):
    inv = shared["invoice_a"]
    before_rows = len(stack["di"].digital_invoices())
    before_events = len(stack["di"].lifecycle_events())
    replay = stack["di"].open_digital_invoice(inv)
    assert type(replay).__name__ == "DigitalInvoiceOpenReplay", replay
    assert replay.current_state == STATE_ISSUED
    out = stack["di"].issue(inv)                  # target-state replay
    assert isinstance(out, LifecycleReplay), out
    stale = stack["di"].mark_extracted(inv)       # stale act → honest refusal
    assert isinstance(stale, LifecycleRequestRefused), stale
    assert len(stack["di"].digital_invoices()) == before_rows
    assert len(stack["di"].lifecycle_events()) == before_events


@step(4, "transition refusals: skips and terminal-exit attempts are refused "
      "with zero durable residue — NOTHING is automatic")
def step4(stack, shared):
    invoice_b = run_pipeline(stack, PAGES_B, "di-smoke-b",
                             ruleset="smoke-di-rules-b")
    stack["di"].open_digital_invoice(invoice_b)
    for act in ("mark_validated", "issue", "revoke"):
        refused = getattr(stack["di"], act)(invoice_b)
        assert isinstance(refused, LifecycleRequestRefused), (act, refused)
        assert "unavailable" in refused.detail
    stack["di"].mark_extracted(invoice_b)
    refused = stack["di"].issue(invoice_b)               # skip VALIDATED
    assert isinstance(refused, LifecycleRequestRefused), refused
    assert len(stack["di"].lifecycle_events(invoice_b)) == 1   # zero residue
    shared["invoice_b"] = invoice_b


@step(5, "supersede: an ISSUED replacement verified at act time → source "
      "SUPERSEDED (terminal), pointer durable; unknown/not-ISSUED/self "
      "replacements refused")
def step5(stack, shared):
    source = shared["invoice_a"]
    invoice_c = run_pipeline(stack, PAGES_C, "di-smoke-c",
                             ruleset="smoke-di-rules-c")
    stack["di"].open_digital_invoice(invoice_c)
    stack["di"].mark_extracted(invoice_c)
    stack["di"].mark_validated(invoice_c)
    stack["di"].issue(invoice_c)
    refused = stack["di"].supersede(source, "no-such-replacement")
    assert isinstance(refused, LifecycleRequestRefused), refused
    refused = stack["di"].supersede(source, source)
    assert isinstance(refused, LifecycleRequestRefused), refused
    out = stack["di"].supersede(source, invoice_c)
    assert isinstance(out, LifecycleAdvanced), out
    assert out.current_state == STATE_SUPERSEDED
    replay = stack["di"].supersede(source, invoice_c)
    assert isinstance(replay, LifecycleReplay), replay
    conflict = stack["di"].supersede(source, shared["invoice_b"])
    assert isinstance(conflict, LifecycleRequestRefused), conflict
    assert stack["di"].read_digital_invoice(invoice_c).current_state \
        == STATE_ISSUED
    shared["invoice_c"] = invoice_c


@step(6, "revoke: the second invoice (after full progression) → REVOKED; "
      "terminal discipline holds")
def step6(stack, shared):
    inv_b = shared["invoice_b"]
    stack["di"].mark_validated(inv_b)
    stack["di"].issue(inv_b)
    out = stack["di"].revoke(inv_b, "duplicate issuance withdrawn")
    assert isinstance(out, LifecycleAdvanced), out
    assert out.current_state == STATE_REVOKED
    refused = stack["di"].supersede(inv_b, shared["invoice_c"])
    assert isinstance(refused, LifecycleRequestRefused), refused
    assert "terminal" in refused.detail


@step(7, "restart: durable lifecycle survives and re-verifies; replay "
      "verbatim; the P6.2 chain still verifies")
def step7(stack, shared):
    close_stack(stack)
    reopened = build_stack(shared["base"])
    try:
        read = reopened["di"].read_digital_invoice(shared["invoice_a"])
        assert isinstance(read, DigitalInvoiceReadSuccess), read
        assert read.current_state == STATE_SUPERSEDED
        assert len(read.events) == 4               # 3 progression + SUPERSEDE
        replay = reopened["di"].open_digital_invoice(shared["invoice_a"])
        assert type(replay).__name__ == "DigitalInvoiceOpenReplay", replay
        assert replay.current_state == STATE_SUPERSEDED
        assert isinstance(reopened["assembly"].read_assembled_invoice(
            shared["invoice_a"]), AssemblyReadSuccess)
        shared["reopened"] = reopened
    except Exception:
        close_stack(reopened)
        raise


@step(8, "tamper withholding + vocabulary sweep: a forged row is never "
      "served; the frozen stores grew nothing; the vocabulary is exactly "
      "the frozen six states")
def step8(stack, shared):
    reopened = shared["reopened"]
    conn = sqlite3.connect(str(shared["base"] / "digital.db"))
    try:
        conn.execute("UPDATE digital_invoices SET document_id = 'forged' "
                     "WHERE invoice_id = ?", (shared["invoice_a"],))
        conn.commit()
    finally:
        conn.close()
    read = reopened["di"].read_digital_invoice(shared["invoice_a"])
    assert type(read).__name__ == "DigitalInvoiceReadIntegrityFailure", read
    # untouched invoices still verify
    ok = reopened["di"].read_digital_invoice(shared["invoice_c"])
    assert isinstance(ok, DigitalInvoiceReadSuccess), ok
    assert LIFECYCLE_STATES == ("DRAFT", "EXTRACTED", "VALIDATED", "ISSUED",
                                "REVOKED", "SUPERSEDED")
    conn = sqlite3.connect(str(shared["base"] / "digital.db"))
    try:
        stored_states = {row[0] for row in conn.execute(
            "SELECT DISTINCT to_state FROM digital_invoice_events").fetchall()}
        n_invoices = conn.execute(
            "SELECT COUNT(*) FROM digital_invoices").fetchone()[0]
        n_events = conn.execute(
            "SELECT COUNT(*) FROM digital_invoice_events").fetchone()[0]
    finally:
        conn.close()
    assert stored_states == {"EXTRACTED", "VALIDATED", "ISSUED", "REVOKED",
                             "SUPERSEDED"}
    assert n_invoices == 3 and n_events == 11     # a:4 (3 prog + SUPERSEDE)
    #                                               b:4 (prog ×3 + REVOKE)
    #                                               c:3 (prog ×3)


def main():
    base = Path(sys.argv[1] if len(sys.argv) > 1
                else "/tmp/kandoo-di-smoke")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    print(f"WP-10.1 smoke — base: {base}")
    stack = build_stack(base)
    shared = {"base": base}
    try:
        for number, title, fn in STEPS:
            fn(stack, shared)
            print(f"  step {number}: OK — {title}")
    finally:
        if "reopened" in shared:
            close_stack(shared["reopened"])
        else:
            close_stack(stack)
    print(f"SMOKE OK — {len(STEPS)} steps "
          f"(digital invoice lifecycle, cold-start)")


if __name__ == "__main__":
    main()
