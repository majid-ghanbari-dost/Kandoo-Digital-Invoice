"""Cold-start smoke check for WP-6.1 — runs the Canonicalization Gate path
end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (frozen) → WP-5.1 VALIDATION
  (frozen) → WP-5.2 DOMAIN STATE (frozen) → WP-6.1 CANONICALIZATION GATE
  (fail-closed decision table G1..G6, D-02 identity resolution, D-03
  idempotency/duplicate handling) → CANONICAL INVOICE ADMISSION RECORD
  (immutable, provenance-anchored) → verified/reloaded output + whole-chain
  trace → restart → tamper detection

Usage: python3 kandoo/src/run_smoke_canonicalization.py /tmp/kandoo-cg-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation,validation-domain,gate}*.db.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import CaptureService, CaptureStore, S1Service            # noqa: E402
from canonicalization import (                                         # noqa: E402
    CanonicalizationAccepted,
    CanonicalizationAlreadyCanonicalized,
    CanonicalizationAlreadyDecided,
    CanonicalizationRejected,
    CanonicalizationRoutedToReview,
    CanonicalInvoiceReadSuccess,
    CanonicalInvoiceReadIntegrityFailure,
    CanonicalInvoiceTraceSuccess,
    CanonicalizationGateService,
    CanonicalizationGateStore,
    GateDecisionReadSuccess,
    GateEventAppended,
    GateEventRefused,
    GateReviewItemReadSuccess,
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
    ValidationAlreadyExists,
    ValidationCompleted,
    ValidationReadSuccess,
    ValidationRuleRegistry,
    ValidationService,
    ValidationStore,
    ReferenceValidationRulesV1,
)
from validation_domain import (                                        # noqa: E402
    DomainStateAlreadyExists,
    DomainStateProjected,
    DomainStateReadSuccess,
    DomainStateTraceSuccess,
    ValidationDomainService,
    ValidationDomainStore,
)

PAGES_OK = [
    b"invoice.number=CG-SMOKE-2026-1\ninvoice.date=2026-10-07\n"
    b"total.net=2500.00\ntax.amount=200.00\n",
]
PAGES_TWIN = [
    b"invoice.date=2026-10-07\ninvoice.number=CG-SMOKE-2026-1\n"
    b"tax.amount=200.00\ntotal.net=2500.00\n",
]   # same identity values, different bytes → different capture, same S2
PAGES_AMBIGUOUS = [
    b"invoice.number=CG-AMBIG-A\ninvoice.number=CG-AMBIG-B\n"
    b"invoice.date=2026-10-07\ntotal.net=900.00\ntax.amount=72\n",
]

FORMULA = "kandoo-der-total-gross-from-net-tax"
R_PRESENT = "kandoo-val-total-net-present"
R_CONSIST = "kandoo-val-total-gross-consistency"
R_TOLERANCE = "kandoo-val-total-gross-tolerance"
R_ROUNDED = "kandoo-val-total-gross-rounded"
REF_KEYS = [(R_PRESENT, "1"), (R_CONSIST, "1"), (R_TOLERANCE, "1"),
            (R_ROUNDED, "1")]
TOLERANCE, PRECISION, MODE = "0.02", 2, "HALF_UP"
BINDING = {"INVOICE_NUMBER": "invoice.number",
           "INVOICE_DATE": "invoice.date",
           "INVOICE_TOTAL": "total.net"}

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
    return {
        "capture_store": capture_store, "capture": capture,
        "recon_store": recon_store, "evidence_store": evidence_store,
        "recon": recon, "extraction_store": extraction_store,
        "extraction": extraction, "binding_store": binding_store,
        "binder": binder, "norm_store": norm_store, "norm": norm,
        "deriv_store": deriv_store, "deriv": deriv, "val_store": val_store,
        "val": val, "vsm_store": vsm_store, "vsm": vsm,
        "gate_store": gate_store, "gate": gate,
    }


def close_stack(stack):
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
        normed.record.normalization_id, "smoke-cg-rules", "1", list(REF_KEYS))
    assert type(projected).__name__ == "DomainStateProjected", projected
    assert projected.record.domain_state == "VALID"
    assert projected.record.disposition == "CLEAR"
    return projected


@step(1, "frozen pipeline + VALID/CLEAR state → gate ACCEPTED → canonical "
      "invoice + full-chain trace")
def step1(stack, shared):
    projected = run_pipeline(stack, PAGES_OK, "cg-smoke-1")
    outcome = stack["gate"].canonicalize(
        projected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    assert outcome.decision.decision == "ACCEPTED"
    assert outcome.canonical_invoice.origin == "HOLOO_CAPTURE"
    assert outcome.canonical_invoice.identity_class == "DETERMINISTIC"
    assert outcome.canonical_invoice.identity_source == "S2_EXTRACTED_VERIFIED"
    assert len(outcome.identity_pointers) == 3
    trace = stack["gate"].trace_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert isinstance(trace, CanonicalInvoiceTraceSuccess), trace
    assert any("capture: OK" in link for link in trace.chain)
    shared["invoice_id"] = outcome.canonical_invoice.canonical_invoice_id
    shared["decision_id"] = outcome.decision.decision_id
    shared["s2_fingerprint"] = outcome.canonical_invoice.identity_fingerprint
    shared["first_capture_s1"] = outcome.canonical_invoice.capture_s1


@step(2, "D-03 identity ambiguity (two candidates) → REVIEW + gate queue item")
def step2(stack, shared):
    projected = run_pipeline(stack, PAGES_AMBIGUOUS, "cg-smoke-2")
    outcome = stack["gate"].canonicalize(
        projected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision == "REVIEW"
    assert outcome.decision.decision_reason == \
        "d03-conflicting-document-identity"
    assert len(stack["gate"].list_gate_review_items()) == 1
    shared["review_id"] = outcome.review_item.review_id


@step(3, "D-03 duplicate: same S2 from a different capture → decisive "
      "REJECTED, exactly one canonical invoice")
def step3(stack, shared):
    projected = run_pipeline(stack, PAGES_TWIN, "cg-smoke-3")
    assert projected.record.capture_s1 != shared["first_capture_s1"]
    outcome = stack["gate"].canonicalize(
        projected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, CanonicalizationRejected), outcome
    assert outcome.decision.decision_reason == "d03-definite-document-duplicate"
    assert outcome.decision.identity_fingerprint == shared["s2_fingerprint"]
    assert len(stack["gate"].canonical_invoices()) == 1


@step(4, "idempotency: state replay → AlreadyDecided; capture replay via "
      "re-projection → ALREADY_CANONICALIZED")
def step4(stack, shared):
    # re-canonicalize the ACCEPTED state (decision replay)
    from canonicalization import CanonicalizationAccepted as _A
    accepted_decision = stack["gate"].read_gate_decision(shared["decision_id"])
    assert type(accepted_decision).__name__ == "GateDecisionReadSuccess"
    replay = stack["gate"].canonicalize(
        accepted_decision.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(replay, CanonicalizationAlreadyDecided), replay
    # re-project the SAME normalization under a new ruleset identity → same
    # capture S1 → the D-02 capture-level idempotency route
    nid = accepted_decision.record.normalization_id
    reprojected = stack["vsm"].project_domain_state(
        nid, "smoke-cg-rules-b", "1", list(REF_KEYS))
    assert type(reprojected).__name__ == "DomainStateProjected", reprojected
    outcome = stack["gate"].canonicalize(
        reprojected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, CanonicalizationAlreadyCanonicalized), outcome
    assert outcome.existing_canonical_invoice.canonical_invoice_id == \
        shared["invoice_id"]
    assert len(stack["gate"].canonical_invoices()) == 1


@step(5, "gate REVIEW lifecycle: annotate → close (terminal) → post-close "
      "refused")
def step5(stack, shared):
    review_id = shared["review_id"]
    note = stack["gate"].append_gate_review_event(review_id, "ANNOTATE",
                                                  "operator inspection",
                                                  "op-1")
    assert type(note).__name__ == "GateEventAppended", note
    bad = stack["gate"].append_gate_review_event(review_id, "RESOLVE", "auto",
                                                 "bot")
    assert type(bad).__name__ == "GateEventRefused", bad
    closed = stack["gate"].append_gate_review_event(review_id, "CLOSE",
                                                    "handled", "supervisor")
    assert type(closed).__name__ == "GateEventAppended", closed
    late = stack["gate"].append_gate_review_event(review_id, "ANNOTATE",
                                                  "late", "op-1")
    assert type(late).__name__ == "GateEventRefused", late
    read = stack["gate"].read_gate_review_item(review_id)
    assert type(read).__name__ == "GateReviewItemReadSuccess", read
    assert read.status == "CLOSED" and len(read.events) == 2


@step(6, "restart recovery: reopen, re-verify, admission survives")
def step6(stack, shared):
    close_stack(stack)
    reopened = build_stack(Path(shared["base"]))
    read = reopened["gate"].read_canonical_invoice(shared["invoice_id"])
    assert type(read).__name__ == "CanonicalInvoiceReadSuccess", read
    assert read.record.origin == "HOLOO_CAPTURE"
    dread = reopened["gate"].read_gate_decision(shared["decision_id"])
    assert type(dread).__name__ == "GateDecisionReadSuccess", dread
    trace = reopened["gate"].trace_canonical_invoice(shared["invoice_id"])
    assert isinstance(trace, CanonicalInvoiceTraceSuccess), trace
    item = reopened["gate"].read_gate_review_item(shared["review_id"])
    assert type(item).__name__ == "GateReviewItemReadSuccess", item
    assert item.status == "CLOSED"
    shared["reopened"] = reopened
    shared["stack"] = reopened


@step(7, "tamper detection: forged invoice row → content withheld")
def step7(stack, shared):
    conn = sqlite3.connect(str(Path(shared["base"]) / "gate.db"))
    try:
        conn.execute("UPDATE canonical_invoices SET origin = 'OTHER_POS_"
                     "CAPTURE' WHERE canonical_invoice_id = ?",
                     (shared["invoice_id"],))
        conn.commit()
    finally:
        conn.close()
    read = shared["reopened"]["gate"].read_canonical_invoice(
        shared["invoice_id"])
    assert type(read).__name__ == "CanonicalInvoiceReadIntegrityFailure", read


@step(8, "frozen-layer survival sweep: P1..P5.2 verified reads intact + gate "
      "vocabulary sweep")
def step8(stack, shared):
    s = shared["reopened"]
    replay = s["val"].validate(
        s["gate"]._store.get_decision(shared["decision_id"]).normalization_id,
        R_PRESENT, "1")
    assert type(replay).__name__ == "ValidationAlreadyExists", replay
    norm_read = s["norm"].read_normalization(
        s["gate"]._store.get_decision(shared["decision_id"]).normalization_id)
    assert type(norm_read).__name__ == "NormalizationReadSuccess", norm_read
    conn = sqlite3.connect(str(Path(shared["base"]) / "gate.db"))
    try:
        decisions = {r[0] for r in conn.execute(
            "SELECT DISTINCT decision FROM gate_decisions")}
        origins = {r[0] for r in conn.execute(
            "SELECT DISTINCT origin FROM canonical_invoices")} | \
            {r[0] for r in conn.execute(
                "SELECT DISTINCT declared_origin FROM gate_decisions")}
        roles = {r[0] for r in conn.execute(
            "SELECT DISTINCT role FROM canonical_identity_pointers")}
    finally:
        conn.close()
    assert decisions <= {"ACCEPTED", "REJECTED", "REVIEW",
                         "ALREADY_CANONICALIZED"}
    assert origins <= {"KANDOO_SALE", "HOLOO_CAPTURE", "OTHER_POS_CAPTURE"}
    assert roles == {"INVOICE_NUMBER", "INVOICE_DATE", "INVOICE_TOTAL"}


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 \
        else Path("/tmp/kandoo-cg-smoke")
    if base.exists():
        for f in base.glob("*"):
            f.unlink()
    base.mkdir(parents=True, exist_ok=True)
    shared = {"base": str(base)}
    stack = build_stack(base)
    try:
        for number, title, fn in STEPS:
            if number in (6, 7, 8):
                continue                      # run after the restart step
            fn(stack, shared)
            print(f"  step {number}: {title} — OK")
        # step 6 reopens the stack (closes the old one) and swaps `shared`
        for number, title, fn in STEPS:
            if number in (6, 7, 8):
                fn(stack, shared)
                print(f"  step {number}: {title} — OK")
    finally:
        if "reopened" in shared:
            close_stack(shared["reopened"])
        else:
            close_stack(stack)
    print("SMOKE OK — Canonicalization Gate is real, durable, deterministic, "
          "provenance-complete, boundary-safe (WP-6.1).")


if __name__ == "__main__":
    main()
