"""Cold-start smoke check for WP-7.2 — runs the Reprint & Duplicate Flows
end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (frozen) → WP-5.1 VALIDATION
  (frozen) → WP-5.2 DOMAIN STATE (frozen) → WP-7.1 IDENTITY RESOLUTION (frozen)
  → WP-7.2 REPRINT & DUPLICATE FLOWS
  (first sighting → IDENTITY_ESTABLISHED; reprint recognition verbatim with
  zero new rows; D-03 definite duplicate → DUPLICATE_RECOGNIZED pointing at
  the deterministic original; the durable duplicate register; CAPTURE_SCOPED
  never a duplicate; declaration-drift refusal propagated; restart recovery;
  tamper detection; frozen-layer survival + vocabulary sweep)

Usage: python3 kandoo/src/run_smoke_duplicate_flows.py /tmp/kandoo-df-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation,validation-domain,identity,flows}*.db.
"""
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import CaptureService, CaptureStore, S1Service            # noqa: E402
from derivation import (                                               # noqa: E402
    DerivationCompleted,
    DerivationFormulaRegistry,
    DerivationService,
    DerivationStore,
    ReferenceDerivationFormulasV1,
)
from duplicate_flows import (                                          # noqa: E402
    DuplicateFlowService,
    FlowDispositionStore,
    FlowDuplicateRecognized,
    FlowIdentityEstablished,
    FlowInputIntegrityFailure,
    FlowReadIntegrityFailure,
    FlowReadSuccess,
    FlowReprintRecognized,
    FlowRequestRefused,
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
from identity_resolution import (                                      # noqa: E402
    IdentityReadSuccess,
    IdentityReplay,
    IdentityResolutionRecorded,
    IdentityResolutionService,
    IdentityResolutionStore,
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
    b"invoice.number=DF-SMOKE-2026-1\ninvoice.date=2026-10-08\n"
    b"total.net=2500.00\ntax.amount=200.00\n",
]
PAGES_TWIN = [
    b"total.net=2500.00\ntax.amount=200.00\ninvoice.date=2026-10-08\n"
    b"invoice.number=DF-SMOKE-2026-1\n",
]   # same identity values, different bytes → different capture, same S2
PAGES_THIRD = [
    b"tax.amount=200.00\ninvoice.number=DF-SMOKE-2026-1\ntotal.net=2500.00\n"
    b"invoice.date=2026-10-08\n",
]
PAGES_AMBIGUOUS = [
    b"invoice.number=DF-AMBIG-A\ninvoice.number=DF-AMBIG-B\n"
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
BINDING = {"INVOICE_NUMBER": "invoice.number",
           "INVOICE_DATE": "invoice.date",
           "INVOICE_TOTAL": "total.net"}
BINDING_DRIFT = {"INVOICE_NUMBER": "invoice.number",
                 "INVOICE_DATE": "invoice.date",
                 "INVOICE_TOTAL": "tax.amount"}

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
    identity_store = IdentityResolutionStore(base / "identity.db",
                                             S1Service())
    identity = IdentityResolutionService(identity_store, vsm, norm,
                                         S1Service())
    flow_store = FlowDispositionStore(base / "flows.db", S1Service())
    flows = DuplicateFlowService(flow_store, identity, S1Service())
    return {
        "capture_store": capture_store, "capture": capture,
        "recon_store": recon_store, "evidence_store": evidence_store,
        "recon": recon, "extraction_store": extraction_store,
        "extraction": extraction, "binding_store": binding_store,
        "binder": binder, "norm_store": norm_store, "norm": norm,
        "deriv_store": deriv_store, "deriv": deriv, "val_store": val_store,
        "val": val, "vsm_store": vsm_store, "vsm": vsm,
        "identity_store": identity_store, "identity": identity,
        "flow_store": flow_store, "flows": flows,
    }


def close_stack(stack):
    stack["flow_store"].close()
    stack["identity_store"].close()
    stack["vsm_store"].close()
    stack["val_store"].close()
    stack["deriv_store"].close()
    stack["norm_store"].close()
    stack["binding_store"].close()
    stack["extraction_store"].close()
    stack["evidence_store"].close()
    stack["recon_store"].close()
    stack["capture_store"].close()


def run_pipeline(stack, pages, label, ruleset="smoke-df-rules"):
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
    return projected


@step(1, "frozen pipeline + VALID/CLEAR state → first flow sighting → "
      "IDENTITY_ESTABLISHED (S2) + verified flow read")
def step1(stack, shared):
    projected = run_pipeline(stack, PAGES_OK, "df-smoke-1")
    outcome = stack["flows"].handle(projected.record.domain_state_id,
                                    "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, FlowIdentityEstablished), outcome
    assert outcome.disposition.flow_outcome == "IDENTITY_ESTABLISHED"
    assert outcome.disposition.original_resolution_id == ""
    assert outcome.record.identity_scope == "S2"
    assert outcome.disposition.identity_fingerprint \
        == outcome.record.identity_fingerprint
    read = stack["flows"].read_disposition_by_id(
        outcome.disposition.disposition_id)
    assert isinstance(read, FlowReadSuccess), read
    assert read.original_resolution is None and read.observation is None
    shared["first"] = outcome
    shared["first_state_id"] = projected.record.domain_state_id
    shared["first_nid"] = projected.record.normalization_id


@step(2, "reprint recognition: same state + re-projection → "
      "FlowReprintRecognized verbatim, zero new rows anywhere")
def step2(stack, shared):
    first = shared["first"]
    before_resolutions = len(stack["identity_store"].list_resolutions())
    before_dispositions = len(stack["flow_store"].list_dispositions())
    reprint = stack["flows"].handle(shared["first_state_id"],
                                    "HOLOO_CAPTURE", BINDING)
    assert isinstance(reprint, FlowReprintRecognized), reprint
    assert reprint.disposition == first.disposition
    assert reprint.record == first.record
    reprojected = stack["vsm"].project_domain_state(
        shared["first_nid"], "smoke-df-rules-b", "1", list(REF_KEYS))
    assert type(reprojected).__name__ == "DomainStateProjected", reprojected
    reprint2 = stack["flows"].handle(reprojected.record.domain_state_id,
                                     "HOLOO_CAPTURE", BINDING)
    assert isinstance(reprint2, FlowReprintRecognized), reprint2
    assert reprint2.disposition == first.disposition
    assert len(stack["identity_store"].list_resolutions()) \
        == before_resolutions
    assert len(stack["flow_store"].list_dispositions()) == before_dispositions


@step(3, "D-03 definite duplicates: twin + third-order captures → "
      "DUPLICATE_RECOGNIZED pointing at the ONE original + the durable "
      "duplicate register")
def step3(stack, shared):
    first = shared["first"]
    twin = stack["flows"].handle(
        run_pipeline(stack, PAGES_TWIN, "df-smoke-twin",
                     ruleset="smoke-df-twin").record.domain_state_id,
        "HOLOO_CAPTURE", BINDING)
    assert isinstance(twin, FlowDuplicateRecognized), twin
    assert twin.disposition.original_resolution_id \
        == first.record.resolution_id
    third = stack["flows"].handle(
        run_pipeline(stack, PAGES_THIRD, "df-smoke-third",
                     ruleset="smoke-df-third").record.domain_state_id,
        "HOLOO_CAPTURE", BINDING)
    assert isinstance(third, FlowDuplicateRecognized), third
    assert third.disposition.original_resolution_id \
        == first.record.resolution_id
    register = stack["flows"].duplicates_of(first.record.resolution_id)
    assert {d.disposition_id for d in register} == {
        twin.disposition.disposition_id, third.disposition.disposition_id}
    assert len(stack["identity_store"].list_resolutions()) == 3
    assert len(stack["flow_store"].list_dispositions()) == 3
    shared["twin_disposition_id"] = twin.disposition.disposition_id
    shared["original_resolution_id"] = first.record.resolution_id


@step(4, "CAPTURE_SCOPED capture → IDENTITY_ESTABLISHED with NO document "
      "identity — never a duplicate, never guessed (D-03)")
def step4(stack, shared):
    projected = run_pipeline(stack, PAGES_AMBIGUOUS, "df-smoke-ambig",
                             ruleset="smoke-df-ambig")
    outcome = stack["flows"].handle(projected.record.domain_state_id,
                                    "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, FlowIdentityEstablished), outcome
    assert outcome.record.identity_scope == "CAPTURE_SCOPED"
    assert outcome.disposition.identity_fingerprint == ""
    assert outcome.disposition.flow_outcome == "IDENTITY_ESTABLISHED"
    assert outcome.disposition.original_resolution_id == ""
    assert len(stack["flow_store"].list_dispositions()) == 4


@step(5, "declaration drift on reprint → FlowRequestRefused propagated "
      "verbatim, zero durable residue")
def step5(stack, shared):
    first = shared["first"]
    drifted = stack["flows"].handle(shared["first_state_id"],
                                    "HOLOO_CAPTURE", BINDING_DRIFT)
    assert isinstance(drifted, FlowRequestRefused), drifted
    assert len(stack["flow_store"].list_dispositions()) == 4
    assert len(stack["identity_store"].list_resolutions()) == 4


@step(6, "restart: the durable dispositions survive and re-verify — reprints "
      "recognized, the duplicate register coherent")
def step6(stack, shared):
    close_stack(stack)
    reopened = build_stack(shared["base"])
    try:
        reprint = reopened["flows"].handle(shared["first_state_id"],
                                           "HOLOO_CAPTURE", BINDING)
        assert isinstance(reprint, FlowReprintRecognized), reprint
        read = reopened["flows"].read_disposition_by_id(
            shared["twin_disposition_id"])
        assert isinstance(read, FlowReadSuccess), read
        assert read.original_resolution.resolution_id \
            == shared["original_resolution_id"]
        register = reopened["flows"].duplicates_of(
            shared["original_resolution_id"])
        assert len(register) == 2
        shared["reopened"] = reopened
    except Exception:
        close_stack(reopened)
        raise


@step(7, "tamper detection: a forged disposition row is withheld — never "
      "served, never recognized")
def step7(stack, shared):
    reopened = shared["reopened"]
    conn = sqlite3.connect(str(shared["base"] / "flows.db"))
    try:
        conn.execute("UPDATE flow_dispositions SET document_id = 'forged' "
                     "WHERE disposition_id = ?",
                     (shared["twin_disposition_id"],))
        conn.commit()
    finally:
        conn.close()
    read = reopened["flows"].read_disposition_by_id(
        shared["twin_disposition_id"])
    assert isinstance(read, FlowReadIntegrityFailure), read
    # the identity facts underneath remain intact and verifiable
    identity_read = reopened["identity"].read_resolution(
        shared["original_resolution_id"])
    assert isinstance(identity_read, IdentityReadSuccess), identity_read


@step(8, "frozen-layer survival + vocabulary sweep: frozen stores untouched "
      "by reprints; REPRINT_RECOGNIZED never durable; upstream rows stable")
def step8(stack, shared):
    reopened = shared["reopened"]
    first = shared["first"]
    # vocabulary: the durable set knows exactly two outcomes
    from duplicate_flows import DURABLE_FLOW_OUTCOMES
    assert DURABLE_FLOW_OUTCOMES == ("IDENTITY_ESTABLISHED",
                                     "DUPLICATE_RECOGNIZED")
    conn = sqlite3.connect(str(shared["base"] / "flows.db"))
    try:
        stored = {row[0] for row in conn.execute(
            "SELECT DISTINCT flow_outcome FROM flow_dispositions").fetchall()}
    finally:
        conn.close()
    assert stored == {"IDENTITY_ESTABLISHED", "DUPLICATE_RECOGNIZED"}
    assert "REPRINT_RECOGNIZED" not in stored
    # a reprint still adds zero rows anywhere (frozen stores untouched)
    before_resolutions = len(reopened["identity_store"].list_resolutions())
    before_dispositions = len(reopened["flow_store"].list_dispositions())
    outcome = reopened["flows"].handle(shared["first_state_id"],
                                       "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, FlowReprintRecognized), outcome
    assert len(reopened["identity_store"].list_resolutions()) \
        == before_resolutions
    assert len(reopened["flow_store"].list_dispositions()) \
        == before_dispositions
    # the original identity record is byte-stable across the whole journey
    identity_read = reopened["identity"].read_resolution(
        first.record.resolution_id)
    assert isinstance(identity_read, IdentityReadSuccess), identity_read
    assert identity_read.record == first.record


def main():
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-df-smoke")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    print(f"WP-7.2 smoke — base: {base}")
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
          f"(reprint & duplicate flows, cold-start)")


if __name__ == "__main__":
    main()
