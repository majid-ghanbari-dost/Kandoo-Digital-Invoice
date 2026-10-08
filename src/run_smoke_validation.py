"""Cold-start smoke check for WP-5.1 — runs the R1/R2 validation path end-to-end
without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (declared formula, exact
  arithmetic) → WP-5.1 VALIDATION (R1 presence + R1 exact-consistency + R2
  tolerated-equality + R2 rounded-equality — explicit verdicts, D-08 parametric
  rounding, full provenance) → verified/reloaded output + whole-chain trace

Usage: python3 kandoo/src/run_smoke_validation.py /tmp/kandoo-val-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation,
validation}*.db.
"""
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
    ValidationReadIntegrityFailure,
    ValidationReadSuccess,
    ValidationRuleNotRegistered,
    ValidationRuleRegistry,
    ValidationService,
    ValidationStore,
    ReferenceValidationRulesV1,
)

PAGES = [
    b"invoice.number=SMOKE-2026-051\ntotal.net=1000.00\ntax.amount=80\n",
    b"seller.name=Kandoo GmbH\n",
]
PAGES_MISMATCH = [b"invoice.number=SMOKE-2026-052\ntotal.net=1000.00\ntax.amount=80\n"
                  b"total.gross=999\n"]

R_PRESENT = "kandoo-val-total-net-present"
R_CONSIST = "kandoo-val-total-gross-consistency"
R_TOLERANCE = "kandoo-val-total-gross-tolerance"
R_ROUNDED = "kandoo-val-total-gross-rounded"
FORMULA = "kandoo-der-total-gross-from-net-tax"


def main(base: str) -> int:
    capture_db, recon_db = f"{base}-capture.db", f"{base}-recon.db"
    extraction_db, binding_db = f"{base}-extraction.db", f"{base}-bindings.db"
    norm_db = f"{base}-normalization.db"
    deriv_db, val_db = f"{base}-derivation.db", f"{base}-validation.db"
    cstore = CaptureStore(capture_db)
    cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    estore = EvidenceStore(recon_db + ".evidence.db", S1Service())
    recon = ReconstructionService(rstore, cap, S1Service(), evidence=estore)
    xstore = ExtractionStore(extraction_db, S1Service())
    ext = ExtractionService(xstore, recon,
                            {"reference-delimited-v1": ReferenceDelimitedEngine()},
                            S1Service())
    bstore = ExtractionBindingStore(binding_db, S1Service())
    binder = ExtractionEvidenceBinder(bstore, ext, recon, estore, S1Service())
    nstore = NormalizationStore(norm_db, S1Service())
    norm = NormalizationService(nstore, ext,
                                {"kandoo-norm-v1": ReferenceNormalizationRulesV1()},
                                S1Service())
    dstore = DerivationStore(deriv_db, S1Service())
    dregistry = DerivationFormulaRegistry(ReferenceDerivationFormulasV1(), S1Service())
    deriv = DerivationService(dstore, norm, ext, binder, recon, dregistry, S1Service())
    vstore = ValidationStore(val_db, S1Service())
    # D-08: R2 parameters are calibration parameters — injected, never hardcoded
    vregistry = ValidationRuleRegistry(
        ReferenceValidationRulesV1(tolerance="0.005", precision=2, mode="HALF_UP"),
        S1Service())
    val = ValidationService(vstore, norm, ext, binder, recon, deriv, vregistry,
                            S1Service())

    # 1. frozen upstream: capture → document → extraction → binding → normalization
    capture_id = cap.ingest(CaptureService.aggregate(PAGES),
                            source_label="smoke-validation").capture_id
    document_id = recon.reconstruct(capture_id).document.document_id
    done = ext.extract(document_id, "reference-delimited-v1")
    assert isinstance(done, ExtractionCompleted), done
    extraction_id = done.extraction.extraction_id
    assert isinstance(binder.bind_extraction(extraction_id), BindingCompleted)
    normed = norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(normed, NormalizationCompleted), normed
    normalization_id = normed.record.normalization_id
    print("1. frozen path   -> Capture → Document → Extraction → WP-3.2 Binding → "
          "WP-4.1 Normalization OK")

    # 2. derive (WP-4.2) — the DERIVED input the consistency rules compare against
    outcome = deriv.derive(normalization_id, FORMULA, "1")
    assert isinstance(outcome, DerivationCompleted), outcome
    assert outcome.record.output_value == "1080"
    print(f"2. derive        -> DERIVED total.gross={outcome.record.output_value} "
          f"(WP-4.2 exact mechanism)")

    # 3. R1 presence + R1 exact-consistency — explicit durable verdicts
    v1 = val.validate(normalization_id, R_PRESENT, "1")
    assert isinstance(v1, ValidationCompleted) and v1.record.outcome == "VALID", v1
    v2 = val.validate(normalization_id, R_CONSIST, "1")
    assert isinstance(v2, ValidationCompleted) and v2.record.outcome == "VALID", v2
    assert v2.record.rule_kind == "R1" and v2.record.rounding_applied == 0
    print(f"3. R1            -> presence=VALID; exact-consistency=VALID "
          f"(total.gross == 1000.00 + 80 EXACTLY — no rounding anywhere in R1)")

    # 4. R2 tolerated-equality + R2 rounded-equality — D-08 parametric validation
    v3 = val.validate(normalization_id, R_TOLERANCE, "1")
    assert isinstance(v3, ValidationCompleted) and v3.record.outcome == "VALID", v3
    assert v3.record.outcome_reason == "exact-match"     # exact kept, no tolerance
    v4 = val.validate(normalization_id, R_ROUNDED, "1")
    assert isinstance(v4, ValidationCompleted) and v4.record.outcome == "VALID", v4
    assert v4.record.outcome_reason == "exact-match"     # exact value preserved
    assert v4.record.rounding_applied == 0
    print("4. R2            -> tolerated-equality=VALID (exact-match, tolerance "
          "not consumed); rounded-equality=VALID (exact value preserved — no "
          "rounding applied)")

    # 5. whole-chain provenance walk — every link re-verified in this walk
    walk = val.trace_validation(v2.record.validation_id)
    assert type(walk).__name__ == "ValidationTraceSuccess", walk
    assert any("WP-4.2 whole-chain" in link for link in walk.chain)
    print("5. trace         -> validation → rule → inputs → WP-4.2 sub-chain → "
          "normalization → extraction → binding → Document/Page/span → Capture S1: "
          "ALL LINKS OK")

    # 6. refusals + explicit negative verdicts — nothing invented, nothing silent
    #    (a) document carrying a literal total.gross: the upstream output-present
    #    gate makes a DERIVED total.gross impossible, so the consistency rule can
    #    only report durable DEFERRED (insufficient information) — never a guess
    cap2 = cap.ingest(CaptureService.aggregate(PAGES_MISMATCH),
                      source_label="smoke-val-deferred").capture_id
    doc2 = recon.reconstruct(cap2).document.document_id
    ext2 = ext.extract(doc2, "reference-delimited-v1")
    binder.bind_extraction(ext2.extraction.extraction_id)
    norm2 = norm.normalize(ext2.extraction.extraction_id, "kandoo-norm-v1")
    v5 = val.validate(norm2.record.normalization_id, R_CONSIST, "1")
    assert isinstance(v5, ValidationCompleted) and v5.record.outcome == "DEFERRED", v5
    assert v5.record.outcome_reason == "insufficient-input"
    #    (b) presence of a field the document does not carry → INVALID (absent)
    from validation import (ValidationRule as VR, RuleInput as RI,
                            ValidationRuleRegistry as VRR)
    probe = VR(rule_id="kandoo-val-smoke-absent-probe", rule_version="1",
               rule_kind="R1", rule_type="presence",
               inputs=(RI(slot_name="field", field_name="seller.vat",
                          origin="normalized"),),
               target_slot=None, expression=None)
    probe_registry = VRR({**(ReferenceValidationRulesV1(tolerance="0.005",
                                                        precision=2,
                                                        mode="HALF_UP")),
                          (probe.rule_id, probe.rule_version): probe}, S1Service())
    val_probe = ValidationService(vstore, norm, ext, binder, recon, deriv,
                                  probe_registry, S1Service())
    v6 = val_probe.validate(normalization_id, probe.rule_id, "1")
    assert isinstance(v6, ValidationCompleted) and v6.record.outcome == "INVALID", v6
    assert v6.record.outcome_reason == "absent"
    replay = val.validate(normalization_id, R_PRESENT, "1")
    assert isinstance(replay, ValidationAlreadyExists)      # INV-V-1:1
    ghost = val.validate(normalization_id, "no-such-rule", "1")
    assert isinstance(ghost, ValidationRuleNotRegistered)
    print("6. verdicts      -> literal-total document: consistency=DEFERRED "
          "(insufficient-input — no DERIVED value possible, no guess); absent "
          "field probe: presence=INVALID (absent); replay=AlreadyExists "
          "(INV-V-1:1); unknown rule refused")

    # 7. restart — durability + verified reload + replay still idempotent
    for store in (cstore, rstore, estore, xstore, bstore, nstore, dstore, vstore):
        store.close()
    cstore = CaptureStore(capture_db); cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    estore = EvidenceStore(recon_db + ".evidence.db", S1Service())
    recon = ReconstructionService(rstore, cap, S1Service(), evidence=estore)
    xstore = ExtractionStore(extraction_db, S1Service())
    ext = ExtractionService(xstore, recon,
                            {"reference-delimited-v1": ReferenceDelimitedEngine()},
                            S1Service())
    bstore = ExtractionBindingStore(binding_db, S1Service())
    binder = ExtractionEvidenceBinder(bstore, ext, recon, estore, S1Service())
    nstore = NormalizationStore(norm_db, S1Service())
    norm = NormalizationService(nstore, ext,
                                {"kandoo-norm-v1": ReferenceNormalizationRulesV1()},
                                S1Service())
    dstore = DerivationStore(deriv_db, S1Service())
    dregistry = DerivationFormulaRegistry(ReferenceDerivationFormulasV1(), S1Service())
    deriv = DerivationService(dstore, norm, ext, binder, recon, dregistry, S1Service())
    vstore = ValidationStore(val_db, S1Service())
    vregistry = ValidationRuleRegistry(
        ReferenceValidationRulesV1(tolerance="0.005", precision=2, mode="HALF_UP"),
        S1Service())
    val = ValidationService(vstore, norm, ext, binder, recon, deriv, vregistry,
                            S1Service())
    read = val.read_validation(v4.record.validation_id)
    assert isinstance(read, ValidationReadSuccess)
    assert read.record.outcome == "VALID"
    assert type(val.trace_validation(v2.record.validation_id)).__name__ \
        == "ValidationTraceSuccess"
    assert isinstance(val.validate(normalization_id, R_PRESENT, "1"),
                      ValidationAlreadyExists)
    print("7. restart       -> validation durable; verified read VALID; whole chain "
          "(incl. WP-4.2 sub-chain) re-verifies; replay idempotent")

    # 8. tamper + vocabulary sweep — broken content never delivered; no UNRESOLVED
    vstore._conn.execute(
        "UPDATE validation_records SET outcome_reason = 'TAMPERED' "
        "WHERE validation_id = ?", (v4.record.validation_id,))
    broken = val.read_validation(v4.record.validation_id)
    assert isinstance(broken, ValidationReadIntegrityFailure)
    assert not hasattr(broken, "record")
    rows = vstore._conn.execute(
        "SELECT outcome, COUNT(*) AS n FROM validation_records "
        "GROUP BY outcome ORDER BY outcome").fetchall()
    outcomes = {r["outcome"]: r["n"] for r in rows}
    assert set(outcomes) <= {"VALID", "INVALID", "DEFERRED"}, outcomes
    assert not vstore._conn.execute(
        "SELECT COUNT(*) AS n FROM validation_records WHERE outcome = 'UNRESOLVED'"
    ).fetchone()["n"]
    for store in (cstore, rstore, estore, xstore, bstore, nstore, dstore, vstore):
        store.close()
    print("8. vocabulary    -> tamper caught (content withheld); stored outcome "
          f"sweep {outcomes} — exactly the declared vocabulary; UNRESOLVED "
          "structurally impossible (P5 domain layer territory)")
    print("SMOKE OK — R1/R2 Validation is real, durable, deterministic, "
          "evidence-bound, and traceable end-to-end (ready for the WP-5.2 "
          "Validation State Machine)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-validation-smoke"))
