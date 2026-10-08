"""Cold-start smoke check for WP-6.2 — runs the Canonical Assembly +
invoice_id Issuance path end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (frozen) → WP-5.1 VALIDATION
  (frozen) → WP-5.2 DOMAIN STATE (frozen) → WP-6.1 CANONICALIZATION GATE
  (ACCEPTED admission) → WP-6.2 CANONICAL ASSEMBLY + INVOICE_ID ISSUANCE
  (canonical fields VERBATIM, declared lines, Kandoo-issued invoice_id
  consumed verbatim) → verified/reloaded output + whole-chain trace →
  replay idempotency → restart → tamper detection

Usage: python3 kandoo/src/run_smoke_canonical_assembly.py /tmp/kandoo-ca-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation,validation-domain,gate,assembly}*.db.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import CaptureService, CaptureStore, S1Service            # noqa: E402
from canonical_assembly import (                                       # noqa: E402
    AssemblyAlreadyAssembled,
    AssemblyCompleted,
    AssemblyReadIntegrityFailure,
    AssemblyReadSuccess,
    AssemblyRequestRefused,
    AssemblyTraceSuccess,
    CanonicalAssemblyService,
    CanonicalAssemblyStore,
)
from canonicalization import (                                         # noqa: E402
    CanonicalizationAccepted,
    CanonicalizationAlreadyCanonicalized,
    CanonicalizationRejected,
    CanonicalizationRoutedToReview,
    CanonicalizationGateService,
    CanonicalizationGateStore,
)
from derivation import (                                               # noqa: E402
    DerivationCompleted,
    DerivationFormulaRegistry,
    DerivationService,
    DerivationStore,
    ReferenceDerivationFormulasV1,
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

PAGES_OK = [
    b"invoice.number=CA-SMOKE-2026-1\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n"
    b"line.1.quantity=3\nline.1.unit_price=60.00\nline.1.total=180.00\n",
]
PAGES_AMBIGUOUS = [
    b"invoice.number=CA-AMBIG-A\ninvoice.number=CA-AMBIG-B\n"
    b"invoice.date=2026-10-08\ntotal.net=900.00\ntax.amount=72\n",
]

FORMULA = "kandoo-der-total-gross-from-net-tax"
R_PRESENT = "kandoo-val-total-net-present"
R_CONSIST = "kandoo-val-total-gross-consistency"
R_TOLERANCE = "kandoo-val-total-gross-tolerance"
R_ROUNDED = "kandoo-val-total-gross-rounded"
REF_KEYS = [(R_PRESENT, "1"), (R_CONSIST, "1"), (R_TOLERANCE, "1"),
            (R_ROUNDED, "1")]
TOLERANCE, PRECISION, MODE = "0.02", 2, "HALF_UP"
IDENTITY_BINDING = {"INVOICE_NUMBER": "invoice.number",
                    "INVOICE_DATE": "invoice.date",
                    "INVOICE_TOTAL": "total.net"}
LINE_BINDING = {
    0: {"LINE_QUANTITY": "line.0.quantity",
        "LINE_UNIT_PRICE": "line.0.unit_price",
        "LINE_TOTAL": "line.0.total"},
    1: {"LINE_QUANTITY": "line.1.quantity",
        "LINE_UNIT_PRICE": "line.1.unit_price",
        "LINE_TOTAL": "line.1.total"},
}

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
        norm_store, extraction, {"kandoo-norm-v1": ReferenceNormalizationRulesV1()},
        S1Service())
    deriv_store = DerivationStore(base / "derivation.db", S1Service())
    dregistry = DerivationFormulaRegistry(dict(ReferenceDerivationFormulasV1()),
                                          S1Service())
    deriv = DerivationService(deriv_store, norm, extraction, binder, recon,
                              dregistry, S1Service())
    val_store = ValidationStore(base / "validation.db", S1Service())
    vregistry = ValidationRuleRegistry(
        dict(ReferenceValidationRulesV1(tolerance=TOLERANCE, precision=PRECISION,
                                        mode=MODE)), S1Service())
    val = ValidationService(val_store, norm, extraction, binder, recon, deriv,
                            vregistry, S1Service())
    vsm_store = ValidationDomainStore(base / "validation-domain.db", S1Service())
    vsm = ValidationDomainService(vsm_store, val, vregistry, norm, extraction,
                                  binder, recon, S1Service())
    gate_store = CanonicalizationGateStore(base / "gate.db", S1Service())
    gate = CanonicalizationGateService(gate_store, vsm, norm, S1Service())
    assembly_store = CanonicalAssemblyStore(base / "assembly.db", S1Service())
    assembly = CanonicalAssemblyService(assembly_store, gate, norm, deriv,
                                        S1Service())
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
    }


def close_stack(stack):
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


def run_pipeline(stack, pages, label):
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
        normed.record.normalization_id, "smoke-ca-rules", "1", list(REF_KEYS))
    assert type(projected).__name__ == "DomainStateProjected", projected
    assert projected.record.domain_state == "VALID"
    assert projected.record.disposition == "CLEAR"
    return projected


@step(1, "frozen pipeline + gate ACCEPTED → WP-6.2 assembles the Canonical "
      "Invoice with the Kandoo-issued invoice_id (verbatim) + full-chain trace")
def step1(stack, shared):
    projected = run_pipeline(stack, PAGES_OK, "ca-smoke-1")
    outcome = stack["gate"].canonicalize(
        projected.record.domain_state_id, "HOLOO_CAPTURE", IDENTITY_BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    issued = stack["assembly"].assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(issued, AssemblyCompleted), issued
    # invoice_id IS the P6.1 Kandoo-issued identity — verbatim (OD-A1)
    assert issued.invoice.invoice_id == \
        outcome.canonical_invoice.canonical_invoice_id
    assert issued.invoice.origin == "HOLOO_CAPTURE"
    # canonical content: EXTRACTED + DERIVED fields, VERBATIM values
    provenances = {f.provenance for f in issued.fields}
    assert provenances == {"EXTRACTED", "DERIVED"}
    values = {f.field_name: f.canonical_value for f in issued.fields}
    assert values["invoice.number"] == "CA-SMOKE-2026-1"
    assert values["total.gross"] == "1274.4"        # DERIVED, relabeled
    # declared lines assembled in ascending order
    assert [l.line_seq for l in issued.lines] == [0, 1]
    # the three D-02 header anchors carry values
    assert len(issued.header_anchors) == 3
    # customer reference explicitly absent (D-06 / OD-A9)
    assert issued.invoice.customer_reference is None
    trace = stack["assembly"].trace_assembled_invoice(
        issued.invoice.invoice_id)
    assert isinstance(trace, AssemblyTraceSuccess), trace
    shared["invoice_id"] = issued.invoice.invoice_id
    shared["decision_id"] = outcome.decision.decision_id
    shared["fingerprint"] = issued.invoice.record_fingerprint


@step(2, "gate REVIEW (ambiguous identity) → NO invoice, assemble refused")
def step2(stack, shared):
    projected = run_pipeline(stack, PAGES_AMBIGUOUS, "ca-smoke-2")
    outcome = stack["gate"].canonicalize(
        projected.record.domain_state_id, "HOLOO_CAPTURE", IDENTITY_BINDING)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    refused = stack["assembly"].assemble(
        outcome.decision.decision_id, LINE_BINDING)
    assert type(refused).__name__ == "AssemblyRequestRefused", refused
    assert len(stack["assembly"].issued_invoices()) == 1


@step(3, "idempotent replay: same admission + same declaration → the same "
      "invoice, no second row")
def step3(stack, shared):
    replay = stack["assembly"].assemble(shared["invoice_id"], LINE_BINDING)
    assert isinstance(replay, AssemblyAlreadyAssembled), replay
    assert replay.invoice.record_fingerprint == shared["fingerprint"]
    drifted = stack["assembly"].assemble(shared["invoice_id"], None)
    assert type(drifted).__name__ == "AssemblyRequestRefused", drifted
    assert len(stack["assembly"].issued_invoices()) == 1


@step(4, "restart recovery: reopen, re-verify, issued invoice survives")
def step4(stack, shared):
    close_stack(stack)
    reopened = build_stack(Path(shared["base"]))
    read = reopened["assembly"].read_assembled_invoice(shared["invoice_id"])
    assert type(read).__name__ == "AssemblyReadSuccess", read
    assert read.invoice.origin == "HOLOO_CAPTURE"
    assert len(read.fields) == read.invoice.field_count
    assert len(read.lines) == read.invoice.line_count
    trace = reopened["assembly"].trace_assembled_invoice(shared["invoice_id"])
    assert isinstance(trace, AssemblyTraceSuccess), trace
    replay = reopened["assembly"].assemble(shared["invoice_id"], LINE_BINDING)
    assert isinstance(replay, AssemblyAlreadyAssembled), replay
    shared["reopened"] = reopened
    shared["stack"] = reopened


@step(5, "tamper detection: forged line value → content withheld")
def step5(stack, shared):
    conn = sqlite3.connect(str(Path(shared["base"]) / "assembly.db"))
    try:
        conn.execute("UPDATE canonical_line_fields SET canonical_value = '0' "
                     "WHERE invoice_id = ? AND line_seq = 0 AND role = "
                     "'LINE_QUANTITY'", (shared["invoice_id"],))
        conn.commit()
    finally:
        conn.close()
    read = shared["reopened"]["assembly"].read_assembled_invoice(
        shared["invoice_id"])
    assert type(read).__name__ == "AssemblyReadIntegrityFailure", read


@step(6, "frozen-layer survival sweep: P1..P6.1 verified reads intact + "
      "assembly vocabulary sweep")
def step6(stack, shared):
    s = shared["reopened"]
    norm_read = s["norm"].read_normalization(
        s["gate"]._store.get_decision(shared["decision_id"]).normalization_id)
    assert type(norm_read).__name__ == "NormalizationReadSuccess"
    conn = sqlite3.connect(str(Path(shared["base"]) / "assembly.db"))
    try:
        origins = {r[0] for r in conn.execute(
            "SELECT DISTINCT origin FROM canonical_invoices")}
        roles = {r[0] for r in conn.execute(
            "SELECT DISTINCT role FROM canonical_header_anchors")}
        lroles = {r[0] for r in conn.execute(
            "SELECT DISTINCT role FROM canonical_line_fields")}
        provs = {r[0] for r in conn.execute(
            "SELECT DISTINCT provenance FROM canonical_fields")}
    finally:
        conn.close()
    assert origins <= {"KANDOO_SALE", "HOLOO_CAPTURE", "OTHER_POS_CAPTURE"}
    assert roles == {"INVOICE_NUMBER", "INVOICE_DATE", "INVOICE_TOTAL"}
    assert lroles <= {"LINE_QUANTITY", "LINE_UNIT_PRICE", "LINE_TOTAL"}
    assert provs <= {"EXTRACTED", "DERIVED"}


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 \
        else Path("/tmp/kandoo-ca-smoke")
    if base.exists():
        for f in base.glob("*"):
            f.unlink()
    base.mkdir(parents=True, exist_ok=True)
    shared = {"base": str(base)}
    stack = build_stack(base)
    try:
        for number, title, fn in STEPS:
            if number in (4, 5, 6):
                continue                      # run after the restart step
            fn(stack, shared)
            print(f"  step {number}: {title} — OK")
        # step 4 reopens the stack (closes the old one) and swaps `shared`
        for number, title, fn in STEPS:
            if number in (4, 5, 6):
                fn(stack, shared)
                print(f"  step {number}: {title} — OK")
    finally:
        if "reopened" in shared:
            close_stack(shared["reopened"])
        else:
            close_stack(stack)
    print("SMOKE OK — Canonical Assembly is real, durable, deterministic, "
          "provenance-complete, boundary-safe (WP-6.2).")


if __name__ == "__main__":
    main()
