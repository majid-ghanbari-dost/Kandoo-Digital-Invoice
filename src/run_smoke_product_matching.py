"""Cold-start smoke check for WP-8.1 — runs the Product Exact Match
end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (frozen) → WP-5.1 VALIDATION
  (frozen) → WP-5.2 DOMAIN STATE (frozen) → WP-6.1 CANONICALIZATION GATE
  (frozen) → WP-6.2 CANONICAL ASSEMBLY (frozen)
  → WP-8.1 PRODUCT EXACT MATCH
  (explicit catalog registration → byte-exact D-05 Exact Match pointing at
  the catalog identity; unregistered → durable UNRESOLVED — ambiguity stays
  ambiguity; replay verbatim with zero new rows; declared-field refusals;
  restart recovery; tamper withholding; frozen-layer survival + vocabulary
  sweep)

Usage: python3 kandoo/src/run_smoke_product_matching.py /tmp/kandoo-pm-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation,validation-domain,gate,assembly,product}*.db.
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
from product_candidate import (                                        # noqa: E402
    DURABLE_MATCH_OUTCOMES,
    ProductCandidateService,
    ProductCandidateStore,
    ProductExactMatched,
    ProductMatchReadSuccess,
    ProductMatchReplay,
    ProductMatchRequestRefused,
    ProductReferenceUnresolved,
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

PAGES_PRODUCTS = [
    b"invoice.number=INV-PM-SMOKE-1\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n"
    b"line.0.product_code=SKU-SMOKE-A-001\n"
    b"line.1.quantity=3\nline.1.unit_price=60.00\nline.1.total=180.00\n"
    b"line.1.product_code=SKU-SMOKE-B-002\n",
]
PAGES_CASE_DIFF = [
    b"invoice.number=INV-PM-SMOKE-2\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n"
    b"line.0.product_code=sku-smoke-a-001\n"
    b"line.1.quantity=3\nline.1.unit_price=60.00\nline.1.total=180.00\n"
    b"line.1.product_code=SKU-SMOKE-B-002\n",
]
PC_FIELD_0 = "line.0.product_code"
PC_FIELD_1 = "line.1.product_code"
PC_KIND = "SKU"
PC_VALUE_0 = "SKU-SMOKE-A-001"

LINE_BINDING = {
    0: {"LINE_QUANTITY": "line.0.quantity",
        "LINE_UNIT_PRICE": "line.0.unit_price",
        "LINE_TOTAL": "line.0.total"},
    1: {"LINE_QUANTITY": "line.1.quantity",
        "LINE_UNIT_PRICE": "line.1.unit_price",
        "LINE_TOTAL": "line.1.total"},
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
    product_store = ProductCandidateStore(base / "product.db", S1Service())
    products = ProductCandidateService(product_store, assembly, S1Service())
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
        "product_store": product_store, "products": products,
    }


def close_stack(stack):
    stack["product_store"].close()
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


def run_pipeline(stack, pages, label, ruleset="smoke-pm-rules"):
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


@step(1, "explicit catalog registration + frozen pipeline → issued invoice "
      "→ byte-exact D-05 EXACT_MATCHED pointing at the catalog identity")
def step1(stack, shared):
    registered = stack["products"].register_catalog_identity(
        PC_KIND, PC_VALUE_0)
    assert type(registered).__name__ == "CatalogIdentityRegistered", registered
    invoice_id = run_pipeline(stack, PAGES_PRODUCTS, "pm-smoke-1")
    outcome = stack["products"].match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductExactMatched), outcome
    assert outcome.record.match_outcome == "EXACT_MATCHED"
    assert outcome.record.catalog_identity_id \
        == registered.catalog_identity.catalog_identity_id
    assert outcome.record.provenance == "EXTRACTED"
    read = stack["products"].read_match_by_id(outcome.record.match_id)
    assert isinstance(read, ProductMatchReadSuccess), read
    # the LIVE byte-identity re-proof: invoice value == registered identifier
    assert read.invoice_read.fields[outcome.record.canonical_seq] \
        .canonical_value == registered.catalog_identity.identifier_value
    shared["first"] = outcome
    shared["invoice_id"] = invoice_id


@step(2, "replay: same declaration → ProductMatchReplay verbatim, ZERO new "
      "rows; second declared reference appends (append-only facts)")
def step2(stack, shared):
    before = len(stack["product_store"].list_matches())
    replay = stack["products"].match(shared["invoice_id"], PC_FIELD_0,
                                     PC_KIND)
    assert isinstance(replay, ProductMatchReplay), replay
    assert replay.record == shared["first"].record
    assert len(stack["product_store"].list_matches()) == before
    registered_b = stack["products"].register_catalog_identity(
        PC_KIND, "SKU-SMOKE-B-002")
    assert type(registered_b).__name__ == "CatalogIdentityRegistered"
    second = stack["products"].match(shared["invoice_id"], PC_FIELD_1,
                                     PC_KIND)
    assert isinstance(second, ProductExactMatched), second
    assert len(stack["product_store"].list_matches()) == before + 1
    shared["second"] = second


@step(3, "unregistered identifier → durable UNRESOLVED (ambiguity remains "
      "ambiguity); a later registration never rewrites the fact")
def step3(stack, shared):
    invoice2 = run_pipeline(stack, PAGES_CASE_DIFF, "pm-smoke-2",
                            ruleset="smoke-pm-rules-2")
    unresolved = stack["products"].match(invoice2, PC_FIELD_0, PC_KIND)
    assert isinstance(unresolved, ProductReferenceUnresolved), unresolved
    assert unresolved.record.unresolved_reason == "no-catalog-identity"
    replay = stack["products"].match(invoice2, PC_FIELD_0, PC_KIND)
    assert isinstance(replay, ProductMatchReplay)          # never re-decides
    assert replay.record == unresolved.record
    shared["unresolved"] = unresolved


@step(4, "declared-field refusals: unknown field / empty declaration → "
      "refused with ZERO durable residue")
def step4(stack, shared):
    refused = stack["products"].match(shared["invoice_id"], "no.such.field",
                                      PC_KIND)
    assert isinstance(refused, ProductMatchRequestRefused), refused
    refused2 = stack["products"].match(shared["invoice_id"], "", PC_KIND)
    assert isinstance(refused2, ProductMatchRequestRefused), refused2
    assert len(stack["product_store"].list_matches()) == 3   # unchanged


@step(5, "restart: durable matches survive and re-verify; replay verbatim")
def step5(stack, shared):
    close_stack(stack)
    reopened = build_stack(shared["base"])
    try:
        read = reopened["products"].read_match_by_id(
            shared["first"].record.match_id)
        assert isinstance(read, ProductMatchReadSuccess), read
        replay = reopened["products"].match(shared["invoice_id"], PC_FIELD_0,
                                            PC_KIND)
        assert isinstance(replay, ProductMatchReplay), replay
        assert replay.record == shared["first"].record
        unresolved_read = reopened["products"].read_match_by_id(
            shared["unresolved"].record.match_id)
        assert isinstance(unresolved_read, ProductMatchReadSuccess)
        shared["reopened"] = reopened
    except Exception:
        close_stack(reopened)
        raise


@step(6, "tamper detection: a forged match row AND a tampered invoice both "
      "withhold content — never served")
def step6(stack, shared):
    reopened = shared["reopened"]
    conn = sqlite3.connect(str(shared["base"] / "product.db"))
    try:
        conn.execute("UPDATE product_matches SET declared_field_name = "
                     "'forged.field' WHERE match_id = ?",
                     (shared["second"].record.match_id,))
        conn.commit()
    finally:
        conn.close()
    read = reopened["products"].read_match_by_id(
        shared["second"].record.match_id)
    assert type(read).__name__ == "ProductMatchReadIntegrityFailure", read


@step(7, "byte-identity discipline: a case-different identifier is a "
      "DIFFERENT identifier (no folding, no tolerance, OD-PM3)")
def step7(stack, shared):
    reopened = shared["reopened"]
    # PAGES_CASE_DIFF carries sku-smoke-a-001 — already UNRESOLVED in step 3
    outcome = reopened["products"].match(shared["unresolved"].record.invoice_id,
                                         PC_FIELD_1, PC_KIND)
    assert isinstance(outcome, ProductExactMatched), outcome
    read = reopened["products"].read_match_by_id(outcome.record.match_id)
    assert isinstance(read, ProductMatchReadSuccess), read
    assert read.catalog_identity.identifier_kind == PC_KIND


@step(8, "frozen-layer survival + vocabulary sweep: matching grew NO frozen "
      "store; the durable vocabulary knows exactly two outcomes")
def step8(stack, shared):
    reopened = shared["reopened"]
    assert DURABLE_MATCH_OUTCOMES == ("EXACT_MATCHED", "UNRESOLVED")
    conn = sqlite3.connect(str(shared["base"] / "product.db"))
    try:
        stored = {row[0] for row in conn.execute(
            "SELECT DISTINCT match_outcome FROM product_matches").fetchall()}
        n_matches = conn.execute(
            "SELECT COUNT(*) FROM product_matches").fetchone()[0]
        n_catalog = conn.execute(
            "SELECT COUNT(*) FROM catalog_identities").fetchone()[0]
        # pointer discipline: no value column exists on the match table
        cols = {row[1] for row in conn.execute(
            "PRAGMA table_info(product_matches)").fetchall()}
    finally:
        conn.close()
    assert stored == {"EXACT_MATCHED", "UNRESOLVED"}
    assert n_matches == 4
    assert n_catalog == 2
    assert "canonical_value" not in cols and "identifier_value" not in cols
    # the frozen invoice still verifies — matching mutated nothing upstream
    inv_read = reopened["assembly"].read_assembled_invoice(
        shared["invoice_id"])
    assert isinstance(inv_read, AssemblyReadSuccess), inv_read


def main():
    base = Path(sys.argv[1] if len(sys.argv) > 1
                else "/tmp/kandoo-pm-smoke")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    print(f"WP-8.1 smoke — base: {base}")
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
          f"(product exact match, cold-start)")


if __name__ == "__main__":
    main()
