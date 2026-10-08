"""Cold-start smoke check for WP-5.2 — runs the Validation State Machine + REVIEW
Queue path end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (frozen) → WP-5.1 VALIDATION
  (frozen) → WP-5.2 DOMAIN STATE MACHINE (verbatim frozen vocabulary:
  VALID | INVALID | DEFERRED | UNRESOLVED + REVIEW/REJECT dispositions per
  AD-04, D-01 field-level UNRESOLVED creation, deterministic transitions) →
  REVIEW QUEUE (durable, idempotent, append-only hash-chained lifecycle) →
  verified/reloaded output + whole-chain trace → restart → tamper detection

Usage: python3 kandoo/src/run_smoke_validation_domain.py /tmp/kandoo-vsm-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation,validation-domain}*.db.
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
    DomainStateReadIntegrityFailure,
    DomainStateReadSuccess,
    DomainStateTraceSuccess,
    ReviewEventAppended,
    ReviewEventRefused,
    ReviewItemReadSuccess,
    ValidationDomainService,
    ValidationDomainStore,
)

PAGES_OK = [
    b"invoice.number=VSM-SMOKE-2026-1\ntotal.net=2500.00\ntax.amount=200.00\n",
]
PAGES_MISSING = [
    b"invoice.number=VSM-SMOKE-2026-2\ntotal.net=2500.00\n",
]

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
    return {
        "capture_store": capture_store, "capture": capture,
        "recon_store": recon_store, "evidence_store": evidence_store,
        "recon": recon, "extraction_store": extraction_store,
        "extraction": extraction, "binding_store": binding_store,
        "binder": binder, "norm_store": norm_store, "norm": norm,
        "deriv_store": deriv_store, "deriv": deriv, "val_store": val_store,
        "val": val, "vsm_store": vsm_store, "vsm": vsm,
    }


def close_stack(stack):
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
    return normed.record.normalization_id


@step(1, "frozen pipeline + WP-5.1 evaluation + VALID/CLEAR projection + trace")
def step1(stack, shared):
    nid = run_pipeline(stack, PAGES_OK, "vsm-smoke-1")
    derived = stack["deriv"].derive(nid, FORMULA, "1")
    assert type(derived).__name__ == "DerivationCompleted", derived
    for rule, _ in REF_KEYS:
        outcome = stack["val"].validate(nid, rule, "1")
        assert type(outcome).__name__ == "ValidationCompleted", outcome
        assert outcome.record.outcome == "VALID"
    projected = stack["vsm"].project_domain_state(
        nid, "smoke-vsm-rules", "1", list(REF_KEYS))
    assert type(projected).__name__ == "DomainStateProjected", projected
    assert projected.record.domain_state == "VALID"
    assert projected.record.disposition == "CLEAR"
    assert projected.review_item is None
    walk = stack["vsm"].trace_domain_state(projected.record.domain_state_id)
    assert type(walk).__name__ == "DomainStateTraceSuccess", walk
    assert any(link.startswith("capture: OK") for link in walk.chain)
    shared["valid_nid"] = nid


@step(2, "D-01 field-level UNRESOLVED creation → UNRESOLVED/REVIEW + queue item")
def step2(stack, shared):
    nid = run_pipeline(stack, PAGES_MISSING, "vsm-smoke-2")
    outcome = stack["val"].validate(nid, R_TOLERANCE, "1")
    assert type(outcome).__name__ == "ValidationCompleted", outcome
    projected = stack["vsm"].project_domain_state(
        nid, "smoke-vsm-rules", "1", [(R_TOLERANCE, "1")])
    assert type(projected).__name__ == "DomainStateProjected", projected
    assert projected.record.domain_state == "UNRESOLVED"
    assert projected.record.disposition == "REVIEW"
    assert projected.record.unresolved_count >= 1
    fields = {r.field_name: r for r in projected.field_projections}
    assert fields["total.gross"].projection_status == "UNRESOLVED"
    assert fields["total.gross"].unresolved_reason == "d01-no-valid-method"
    assert projected.review_item is not None
    shared["unres_nid"] = nid
    shared["review_id"] = projected.review_item.review_id
    shared["unres_state_id"] = projected.record.domain_state_id


@step(3, "idempotent replay — no second record, no duplicate queue item")
def step3(stack, shared):
    replay = stack["vsm"].project_domain_state(
        shared["valid_nid"], "smoke-vsm-rules", "1", list(REF_KEYS))
    assert type(replay).__name__ == "DomainStateAlreadyExists", replay
    assert len(stack["vsm"].list_review_items()) == 1


@step(4, "REVIEW lifecycle: annotate → close (terminal) → post-close refused")
def step4(stack, shared):
    review_id = shared["review_id"]
    note = stack["vsm"].append_review_event(review_id, "ANNOTATE",
                                            "operator inspection", "op-1")
    assert type(note).__name__ == "ReviewEventAppended", note
    bad = stack["vsm"].append_review_event(review_id, "RESOLVE", "auto", "bot")
    assert type(bad).__name__ == "ReviewEventRefused", bad
    closed = stack["vsm"].append_review_event(review_id, "CLOSE", "handled",
                                              "supervisor")
    assert type(closed).__name__ == "ReviewEventAppended", closed
    late = stack["vsm"].append_review_event(review_id, "ANNOTATE", "late",
                                            "op-1")
    assert type(late).__name__ == "ReviewEventRefused", late
    read = stack["vsm"].read_review_item(review_id)
    assert type(read).__name__ == "ReviewItemReadSuccess", read
    assert read.status == "CLOSED" and len(read.events) == 2


@step(5, "determinism: D-03-honoring content equality via distinct corpus")
def step5(stack, shared):
    pages_alt = [b"total.net=2500.00\ntax.amount=200.00\n"
                 b"invoice.number=VSM-SMOKE-2026-3\n"]
    nid = run_pipeline(stack, pages_alt, "vsm-smoke-3")
    derived = stack["deriv"].derive(nid, FORMULA, "1")
    assert type(derived).__name__ == "DerivationCompleted", derived
    for rule, _ in REF_KEYS:
        outcome = stack["val"].validate(nid, rule, "1")
        assert type(outcome).__name__ == "ValidationCompleted", outcome
    a = stack["vsm"].project_domain_state(
        shared["valid_nid"], "smoke-vsm-det", "1", list(REF_KEYS))
    assert type(a).__name__ == "DomainStateProjected", a
    b = stack["vsm"].project_domain_state(
        nid, "smoke-vsm-det", "1", list(REF_KEYS))
    assert type(b).__name__ == "DomainStateProjected", b
    assert a.record.state_detail == b.record.state_detail
    assert a.record.ruleset_fingerprint == b.record.ruleset_fingerprint
    assert a.record.domain_state == b.record.domain_state == "VALID"


@step(6, "restart recovery: reopen, re-verify, derived status survives")
def step6(stack, shared):
    close_stack(stack)
    reopened = build_stack(Path(shared["base"]))
    read = reopened["vsm"].read_domain_state(shared["unres_state_id"])
    assert type(read).__name__ == "DomainStateReadSuccess", read
    assert read.record.domain_state == "UNRESOLVED"
    assert read.review_status == "CLOSED"
    item = reopened["vsm"].read_review_item(shared["review_id"])
    assert type(item).__name__ == "ReviewItemReadSuccess", item
    assert len(item.events) == 2
    walk = reopened["vsm"].trace_domain_state(shared["unres_state_id"])
    assert type(walk).__name__ == "DomainStateTraceSuccess", walk
    shared["reopened"] = reopened
    shared["stack"] = reopened


@step(7, "tamper detection: forged state row → content withheld, queue frozen")
def step7(stack, shared):
    conn = sqlite3.connect(str(Path(shared["base"]) / "validation-domain.db"))
    try:
        conn.execute("UPDATE domain_state_records SET state_reason = 'forged' "
                     "WHERE domain_state_id = ?", (shared["unres_state_id"],))
        conn.commit()
    finally:
        conn.close()
    read = shared["reopened"]["vsm"].read_domain_state(shared["unres_state_id"])
    assert type(read).__name__ == "DomainStateReadIntegrityFailure", read
    refused = shared["reopened"]["vsm"].append_review_event(
        shared["review_id"], "ANNOTATE", "note", "op")
    assert type(refused).__name__ == "ReviewEventRefused", refused


@step(8, "frozen-layer survival sweep: P1..P5.1 replay + verified reads intact")
def step8(stack, shared):
    s = shared["reopened"]
    replay = s["val"].validate(shared["valid_nid"], R_PRESENT, "1")
    assert type(replay).__name__ == "ValidationAlreadyExists", replay
    norm_read = s["norm"].read_normalization(shared["valid_nid"])
    assert type(norm_read).__name__ == "NormalizationReadSuccess", norm_read
    outcome = s["capture"].ingest(CaptureService.aggregate(PAGES_OK),
                                  source_label="vsm-smoke-idem")
    assert type(outcome).__name__ == "IngestCompleted" or \
        type(outcome).__name__ == "IngestDuplicateAtCapture"
    # vocabulary sweep over the durable store
    conn = sqlite3.connect(str(Path(shared["base"]) / "validation-domain.db"))
    try:
        states = {r[0] for r in conn.execute(
            "SELECT DISTINCT domain_state FROM domain_state_records")}
        dispositions = {r[0] for r in conn.execute(
            "SELECT DISTINCT disposition FROM domain_state_records")}
    finally:
        conn.close()
    assert states <= {"VALID", "INVALID", "DEFERRED", "UNRESOLVED"}
    assert dispositions <= {"CLEAR", "REVIEW", "REJECT"}


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/kandoo-vsm-smoke")
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
    print("SMOKE OK — Validation State Machine + REVIEW Queue are real, durable, "
          "deterministic, provenance-complete, boundary-safe (WP-5.2).")


if __name__ == "__main__":
    main()
