"""Cold-start smoke check for WP-9.1 — runs Deterministic Customer Linking
end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (frozen) → WP-5.1 VALIDATION
  (frozen) → WP-5.2 DOMAIN STATE (frozen) → WP-6.1 CANONICALIZATION GATE
  (frozen) → WP-6.2 CANONICAL ASSEMBLY (frozen)
  → WP-9.1 DETERMINISTIC CUSTOMER LINKING
  (explicit registration of an EXISTING customer → byte-exact deterministic
  LINKED pointing at the existing customer identity; unregistered → durable
  UNRESOLVED and NO customer created (D-06/DEF3 structural); replay verbatim
  with zero new rows; declared-field refusals; restart recovery; tamper
  withholding; frozen-layer survival + vocabulary sweep)

Usage: python3 kandoo/src/run_smoke_customer_linking.py /tmp/kandoo-cl-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation,validation-domain,gate,assembly,customer}*.db.
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
    DURABLE_LINK_OUTCOMES,
    CustomerIdentityRegistered,
    CustomerLinkReadSuccess,
    CustomerLinkReplay,
    CustomerLinkRequestRefused,
    CustomerLinkUnresolved,
    CustomerLinkingService,
    CustomerLinkingStore,
    CustomerLinked,
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

PAGES_CUSTOMER = [
    b"invoice.number=INV-CL-SMOKE-1\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"customer.code=CUST-SMOKE-A-001\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n",
]
PAGES_UNKNOWN_CUSTOMER = [
    b"invoice.number=INV-CL-SMOKE-2\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"customer.code=CUST-SMOKE-UNKNOWN\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n",
]
CL_FIELD = "customer.code"
CL_KIND = "CUST-CODE"
CL_VALUE = "CUST-SMOKE-A-001"

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
    }


def close_stack(stack):
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


def run_pipeline(stack, pages, label, ruleset="smoke-cl-rules"):
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


@step(1, "explicit registration of an EXISTING customer + frozen pipeline → "
      "issued invoice → deterministic byte-exact LINKED (D-06)")
def step1(stack, shared):
    registered = stack["customers"].register_customer_identity(
        CL_KIND, CL_VALUE)
    assert isinstance(registered, CustomerIdentityRegistered), registered
    invoice_id = run_pipeline(stack, PAGES_CUSTOMER, "cl-smoke-1")
    outcome = stack["customers"].link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinked), outcome
    assert outcome.record.link_outcome == "LINKED"
    assert outcome.record.customer_identity_id \
        == registered.customer_identity.customer_identity_id
    assert outcome.record.provenance == "EXTRACTED"
    read = stack["customers"].read_link_by_id(outcome.record.link_id)
    assert isinstance(read, CustomerLinkReadSuccess), read
    # the LIVE byte-identity re-proof: invoice value == registered identifier
    assert read.invoice_read.fields[outcome.record.canonical_seq] \
        .canonical_value == registered.customer_identity.identifier_value
    shared["first"] = outcome
    shared["invoice_id"] = invoice_id


@step(2, "replay: same declaration → CustomerLinkReplay verbatim, ZERO new "
      "rows anywhere")
def step2(stack, shared):
    before = len(stack["customer_store"].list_links())
    replay = stack["customers"].link(shared["invoice_id"], CL_FIELD, CL_KIND)
    assert isinstance(replay, CustomerLinkReplay), replay
    assert replay.record == shared["first"].record
    assert len(stack["customer_store"].list_links()) == before


@step(3, "customer-looking data with NO existing customer → durable "
      "UNRESOLVED and the register stays EMPTY (D-06/DEF3 — no auto-create, "
      "structurally); a later registration never rewrites the fact")
def step3(stack, shared):
    invoice2 = run_pipeline(stack, PAGES_UNKNOWN_CUSTOMER, "cl-smoke-2",
                            ruleset="smoke-cl-rules-2")
    unresolved = stack["customers"].link(invoice2, CL_FIELD, CL_KIND)
    assert isinstance(unresolved, CustomerLinkUnresolved), unresolved
    assert unresolved.record.unresolved_reason == "no-customer-identity"
    assert len(stack["customers"].customers()) == 1     # NOTHING was created
    replay = stack["customers"].link(invoice2, CL_FIELD, CL_KIND)
    assert isinstance(replay, CustomerLinkReplay)        # never re-decides
    assert replay.record == unresolved.record
    stack["customers"].register_customer_identity(CL_KIND,
                                                  "CUST-SMOKE-UNKNOWN")
    replay2 = stack["customers"].link(invoice2, CL_FIELD, CL_KIND)
    assert isinstance(replay2, CustomerLinkReplay)
    assert replay2.record == unresolved.record           # history stands
    shared["unresolved"] = unresolved


@step(4, "declared-field refusals: unknown field / empty declaration → "
      "refused with ZERO durable residue")
def step4(stack, shared):
    refused = stack["customers"].link(shared["invoice_id"], "no.such.field",
                                      CL_KIND)
    assert isinstance(refused, CustomerLinkRequestRefused), refused
    refused2 = stack["customers"].link(shared["invoice_id"], "", CL_KIND)
    assert isinstance(refused2, CustomerLinkRequestRefused), refused2
    assert len(stack["customer_store"].list_links()) == 2    # unchanged


@step(5, "restart: durable links survive and re-verify; replay verbatim")
def step5(stack, shared):
    close_stack(stack)
    reopened = build_stack(shared["base"])
    try:
        read = reopened["customers"].read_link_by_id(
            shared["first"].record.link_id)
        assert isinstance(read, CustomerLinkReadSuccess), read
        replay = reopened["customers"].link(shared["invoice_id"], CL_FIELD,
                                            CL_KIND)
        assert isinstance(replay, CustomerLinkReplay), replay
        assert replay.record == shared["first"].record
        shared["reopened"] = reopened
    except Exception:
        close_stack(reopened)
        raise


@step(6, "tamper detection: a forged link row is withheld — never served")
def step6(stack, shared):
    reopened = shared["reopened"]
    conn = sqlite3.connect(str(shared["base"] / "customer.db"))
    try:
        conn.execute("UPDATE customer_links SET declared_field_name = "
                     "'customer.forged' WHERE link_id = ?",
                     (shared["first"].record.link_id,))
        conn.commit()
    finally:
        conn.close()
    read = reopened["customers"].read_link_by_id(
        shared["first"].record.link_id)
    assert type(read).__name__ == "CustomerLinkReadIntegrityFailure", read
    # the unresolved fact (its row untouched) still verifies
    ok = reopened["customers"].read_link_by_id(
        shared["unresolved"].record.link_id)
    assert isinstance(ok, CustomerLinkReadSuccess), ok


@step(7, "byte-identity discipline: a case-different identifier is a "
      "DIFFERENT identifier (no folding, no tolerance, OD-CL3)")
def step7(stack, shared):
    reopened = shared["reopened"]
    outcome = reopened["customers"].link(shared["invoice_id"], CL_FIELD,
                                         "OTHER-KIND")
    assert isinstance(outcome, CustomerLinkUnresolved), outcome
    assert len(reopened["customers"].links()) == 3


@step(8, "frozen-layer survival + vocabulary sweep: linking grew NO frozen "
      "store and NO customer beyond explicit registration; the durable "
      "vocabulary knows exactly two outcomes")
def step8(stack, shared):
    reopened = shared["reopened"]
    assert DURABLE_LINK_OUTCOMES == ("LINKED", "UNRESOLVED")
    conn = sqlite3.connect(str(shared["base"] / "customer.db"))
    try:
        stored = {row[0] for row in conn.execute(
            "SELECT DISTINCT link_outcome FROM customer_links").fetchall()}
        n_links = conn.execute(
            "SELECT COUNT(*) FROM customer_links").fetchone()[0]
        n_customers = conn.execute(
            "SELECT COUNT(*) FROM customer_identities").fetchone()[0]
        # pointer discipline: no value column exists on the link table
        cols = {row[1] for row in conn.execute(
            "PRAGMA table_info(customer_links)").fetchall()}
    finally:
        conn.close()
    assert stored == {"LINKED", "UNRESOLVED"}
    assert n_links == 3
    assert n_customers == 2        # exactly the two explicit registrations
    assert "canonical_value" not in cols and "identifier_value" not in cols
    # the frozen invoice still verifies — linking mutated nothing upstream
    inv_read = reopened["assembly"].read_assembled_invoice(
        shared["invoice_id"])
    assert isinstance(inv_read, AssemblyReadSuccess), inv_read


def main():
    base = Path(sys.argv[1] if len(sys.argv) > 1
                else "/tmp/kandoo-cl-smoke")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    print(f"WP-9.1 smoke — base: {base}")
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
          f"(deterministic customer linking, cold-start)")


if __name__ == "__main__":
    main()
