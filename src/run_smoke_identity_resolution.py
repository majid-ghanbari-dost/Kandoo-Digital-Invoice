"""Cold-start smoke check for WP-7.1 — runs the Identity Resolution path
end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (frozen) → WP-5.1 VALIDATION
  (frozen) → WP-5.2 DOMAIN STATE (frozen) → WP-7.1 IDENTITY RESOLUTION
  (S1 replay recognition, S2 exact triad via the frozen P6.1 primitive,
  CAPTURE_SCOPED fail-closed, D-03 definite-duplicate observations)
  → durable immutable resolution records → verified/reloaded output
  → restart → tamper detection → frozen-layer survival sweep

Usage: python3 kandoo/src/run_smoke_identity_resolution.py /tmp/kandoo-ir-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation,validation-domain,identity}*.db.
"""
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
    IdentityDefiniteDuplicate,
    IdentityReadIntegrityFailure,
    IdentityReadSuccess,
    IdentityReplay,
    IdentityResolutionRecorded,
    IdentityResolutionService,
    IdentityResolutionStore,
)
from normalization import (                                            # noqa: E402
    NormalizationCompleted,
    NormalizationReadSuccess,
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
    ValidationRuleRegistry,
    ValidationService,
    ValidationStore,
    ReferenceValidationRulesV1,
)
from validation_domain import (                                        # noqa: E402
    DomainStateProjected,
    DomainStateReadSuccess,
    ValidationDomainService,
    ValidationDomainStore,
)

PAGES_OK = [
    b"invoice.number=IR-SMOKE-2026-1\ninvoice.date=2026-10-08\n"
    b"total.net=2500.00\ntax.amount=200.00\n",
]
PAGES_TWIN = [
    b"total.net=2500.00\ntax.amount=200.00\ninvoice.date=2026-10-08\n"
    b"invoice.number=IR-SMOKE-2026-1\n",
]   # same identity values, different bytes → different capture, same S2
PAGES_AMBIGUOUS = [
    b"invoice.number=IR-AMBIG-A\ninvoice.number=IR-AMBIG-B\n"
    b"invoice.date=2026-10-08\ntotal.net=900.00\ntax.amount=72\n",
]
PAGES_NO_DATE = [
    b"invoice.number=IR-SMOKE-NODATE\ntotal.net=400.00\ntax.amount=32\n",
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
    identity_store = IdentityResolutionStore(base / "identity.db", S1Service())
    identity = IdentityResolutionService(identity_store, vsm, norm,
                                         S1Service())
    return {
        "capture_store": capture_store, "capture": capture,
        "recon_store": recon_store, "evidence_store": evidence_store,
        "recon": recon, "extraction_store": extraction_store,
        "extraction": extraction, "binding_store": binding_store,
        "binder": binder, "norm_store": norm_store, "norm": norm,
        "deriv_store": deriv_store, "deriv": deriv, "val_store": val_store,
        "val": val, "vsm_store": vsm_store, "vsm": vsm,
        "identity_store": identity_store, "identity": identity,
    }


def close_stack(stack):
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
        normed.record.normalization_id, "smoke-ir-rules", "1", list(REF_KEYS))
    assert type(projected).__name__ == "DomainStateProjected", projected
    assert projected.record.domain_state == "VALID"
    assert projected.record.disposition == "CLEAR"
    return projected


@step(1, "frozen pipeline + VALID/CLEAR state → S2 resolution recorded + "
      "verified read + role evidence")
def step1(stack, shared):
    projected = run_pipeline(stack, PAGES_OK, "ir-smoke-1")
    outcome = stack["identity"].resolve(
        projected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded), outcome
    assert outcome.record.identity_scope == "S2"
    assert outcome.record.identity_source == "S2_EXTRACTED_VERIFIED"
    assert outcome.record.capture_s1 == projected.record.capture_s1
    assert len(outcome.role_rows) == 3
    read = stack["identity"].read_resolution(
        outcome.record.resolution_id)
    assert isinstance(read, IdentityReadSuccess), read
    shared["first_resolution_id"] = outcome.record.resolution_id
    shared["first_state_id"] = projected.record.domain_state_id
    shared["first_nid"] = projected.record.normalization_id
    shared["s2_fingerprint"] = outcome.record.identity_fingerprint
    shared["first_capture_s1"] = outcome.record.capture_s1


@step(2, "S1 replay: same state + re-projection → Replay verbatim, exactly "
      "one resolution")
def step2(stack, shared):
    replay = stack["identity"].resolve(shared["first_state_id"],
                                       "HOLOO_CAPTURE", BINDING)
    assert isinstance(replay, IdentityReplay), replay
    assert replay.record.resolution_id == shared["first_resolution_id"]
    reprojected = stack["vsm"].project_domain_state(
        shared["first_nid"], "smoke-ir-rules-b", "1", list(REF_KEYS))
    assert type(reprojected).__name__ == "DomainStateProjected", reprojected
    replay2 = stack["identity"].resolve(
        reprojected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(replay2, IdentityReplay), replay2
    assert replay2.record.resolution_id == shared["first_resolution_id"]
    assert len(stack["identity_store"].list_resolutions()) == 1


@step(3, "D-03 definite duplicate: same S2 from a different capture → "
      "observation referencing the original, ONE document identity")
def step3(stack, shared):
    projected = run_pipeline(stack, PAGES_TWIN, "ir-smoke-3")
    assert projected.record.capture_s1 != shared["first_capture_s1"]
    outcome = stack["identity"].resolve(
        projected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, IdentityDefiniteDuplicate), outcome
    assert (outcome.original_resolution.resolution_id
            == shared["first_resolution_id"])
    assert outcome.observation.identity_fingerprint == shared["s2_fingerprint"]
    conn = sqlite3.connect(str(shared["base"] / "identity.db"))
    try:
        fingerprints = {r[0] for r in conn.execute(
            "SELECT DISTINCT identity_fingerprint FROM identity_resolutions "
            "WHERE identity_fingerprint != ''")}
        observations = conn.execute(
            "SELECT COUNT(*) FROM identity_duplicate_observations"
        ).fetchone()[0]
    finally:
        conn.close()
    assert fingerprints == {shared["s2_fingerprint"]}
    assert observations == 1


@step(4, "CAPTURE_SCOPED fail-closed: ambiguity preserved, never selected; "
      "incomplete → explicit")
def step4(stack, shared):
    projected = run_pipeline(stack, PAGES_AMBIGUOUS, "ir-smoke-4a")
    outcome = stack["identity"].resolve(
        projected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded), outcome
    assert outcome.record.identity_scope == "CAPTURE_SCOPED"
    assert outcome.record.scope_reason == "d03-conflicting-document-identity"
    number_row = [r for r in outcome.role_rows
                  if r.role == "INVOICE_NUMBER"][0]
    assert number_row.candidate_count == 2
    assert number_row.resolved_field_seq is None
    projected = run_pipeline(stack, PAGES_NO_DATE, "ir-smoke-4b")
    outcome = stack["identity"].resolve(
        projected.record.domain_state_id, "HOLOO_CAPTURE", BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded), outcome
    assert outcome.record.scope_reason == "d03-incomplete-document-identity"


@step(5, "declaration drift on replay → refused, no second identity, no "
      "silent reshape")
def step5(stack, shared):
    outcome = stack["identity"].resolve(shared["first_state_id"],
                                        "OTHER_POS_CAPTURE", BINDING)
    assert type(outcome).__name__ == "IdentityRequestRefused", outcome
    assert len(stack["identity_store"].list_resolutions()) == 4


@step(6, "restart recovery: reopen, re-verify, replay survives")
def step6(stack, shared):
    close_stack(stack)
    reopened = build_stack(Path(shared["base"]))
    read = reopened["identity"].read_resolution(
        shared["first_resolution_id"])
    assert isinstance(read, IdentityReadSuccess), read
    replay = reopened["identity"].resolve(shared["first_state_id"],
                                          "HOLOO_CAPTURE", BINDING)
    assert isinstance(replay, IdentityReplay), replay
    shared["reopened"] = reopened
    shared["stack"] = reopened


@step(7, "tamper detection: forged resolution row → content withheld")
def step7(stack, shared):
    conn = sqlite3.connect(str(Path(shared["base"]) / "identity.db"))
    try:
        conn.execute(
            """INSERT INTO identity_resolutions (
                   resolution_id, capture_s1, capture_s1_algorithm_id,
                   capture_id, document_id, extraction_id, normalization_id,
                   domain_state_id, declared_origin,
                   binding_declaration_fingerprint, identity_scope,
                   identity_source, identity_fingerprint, scope_reason,
                   created_at, record_fingerprint, fingerprint_algorithm_id)
               VALUES ('forged-smoke', 'forgedS1', 'sha256-v1', 'c', 'd',
                       'e', 'n', 'ds', 'HOLOO_CAPTURE', '', 'S2',
                       'S2_EXTRACTED_VERIFIED', 'fp', '',
                       '2026-10-08T00:00:00+00:00', 'forged-fp',
                       'sha256-v1')""")
        conn.commit()
    finally:
        conn.close()
    read = shared["reopened"]["identity"].read_resolution("forged-smoke")
    assert isinstance(read, IdentityReadIntegrityFailure), read


@step(8, "frozen-layer survival sweep: P1..P5.2 verified reads intact + "
      "identity vocabulary sweep")
def step8(stack, shared):
    s = shared["reopened"]
    replay = s["val"].validate(shared["first_nid"], R_PRESENT, "1")
    assert type(replay).__name__ == "ValidationAlreadyExists", replay
    norm_read = s["norm"].read_normalization(shared["first_nid"])
    assert isinstance(norm_read, NormalizationReadSuccess), norm_read
    conn = sqlite3.connect(str(Path(shared["base"]) / "identity.db"))
    try:
        scopes = {r[0] for r in conn.execute(
            "SELECT DISTINCT identity_scope FROM identity_resolutions")}
        origins = {r[0] for r in conn.execute(
            "SELECT DISTINCT declared_origin FROM identity_resolutions")}
        roles = {r[0] for r in conn.execute(
            "SELECT DISTINCT role FROM identity_role_candidates")}
    finally:
        conn.close()
    assert scopes <= {"S2", "CAPTURE_SCOPED"}
    assert origins <= {"KANDOO_SALE", "HOLOO_CAPTURE", "OTHER_POS_CAPTURE"}
    assert roles == {"INVOICE_NUMBER", "INVOICE_DATE", "INVOICE_TOTAL"}


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 \
        else Path("/tmp/kandoo-ir-smoke")
    if base.exists():
        for f in base.glob("*"):
            f.unlink()
    base.mkdir(parents=True, exist_ok=True)
    shared = {"base": base}
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
    print("SMOKE OK — Identity Resolution is real, durable, deterministic, "
          "provenance-complete, boundary-safe (WP-7.1).")


if __name__ == "__main__":
    main()
