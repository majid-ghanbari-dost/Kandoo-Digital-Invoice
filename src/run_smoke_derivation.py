"""Cold-start smoke check for WP-4.2 — runs the exact-derivation path end-to-end
without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → Normalization (frozen WP-4.1) → WP-4.2 DERIVED (declared formula, exact
  arithmetic, full provenance) → verified/reloaded output + whole-chain trace

Usage: python3 kandoo/src/run_smoke_derivation.py /tmp/kandoo-deriv-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization,derivation}*.db.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import CaptureService, CaptureStore, S1Service            # noqa: E402
from derivation import (                                               # noqa: E402
    DerivationAlreadyExists,
    DerivationCompleted,
    DerivationDeferred,
    DerivationFormulaNotRegistered,
    DerivationReadIntegrityFailure,
    DerivationReadSuccess,
    DerivationStore,
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

PAGES = [
    b"invoice.number=SMOKE-2026-042\ntotal.net=1000.00\ntax.amount=80\n",
    b"seller.name=Kandoo GmbH\n",
]
PAGES_NO_TAX = [b"invoice.number=SMOKE-2026-043\ntotal.net=500\n"]

FORMULA = "kandoo-der-total-gross-from-net-tax"


def main(base: str) -> int:
    capture_db, recon_db = f"{base}-capture.db", f"{base}-recon.db"
    extraction_db, binding_db = f"{base}-extraction.db", f"{base}-bindings.db"
    norm_db, deriv_db = f"{base}-normalization.db", f"{base}-derivation.db"
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
    from derivation import (DerivationFormulaRegistry,
                            ReferenceDerivationFormulasV1, DerivationService)
    registry = DerivationFormulaRegistry(ReferenceDerivationFormulasV1(), S1Service())
    deriv = DerivationService(dstore, norm, ext, binder, recon, registry, S1Service())

    # 1. frozen upstream: capture → document → extraction → binding
    capture_id = cap.ingest(CaptureService.aggregate(PAGES),
                            source_label="smoke-derivation").capture_id
    document_id = recon.reconstruct(capture_id).document.document_id
    done = ext.extract(document_id, "reference-delimited-v1")
    assert isinstance(done, ExtractionCompleted), done
    extraction_id = done.extraction.extraction_id
    assert isinstance(binder.bind_extraction(extraction_id), BindingCompleted)
    print("1. frozen path   -> Capture → Document → Extraction → WP-3.2 Binding OK")

    # 2. normalize (frozen WP-4.1) — the ONLY sanctioned value path for derivation
    normed = norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(normed, NormalizationCompleted), normed
    normalization_id = normed.record.normalization_id
    print(f"2. normalize     -> {normed.record.normalized_count} NORMALIZED "
          f"(total.net=1000.00, tax.amount=80) — WP-4.1 FROZEN grammar")

    # 3. derive — declared formula, exact arithmetic, DERIVED provenance
    outcome = deriv.derive(normalization_id, FORMULA, "1")
    assert isinstance(outcome, DerivationCompleted), outcome
    rec = outcome.record
    assert rec.output_value == "1080" and rec.output_provenance == "DERIVED"
    assert rec.formula_fingerprint == registry.fingerprint_of(FORMULA, "1")
    print(f"3. derive        -> DERIVED total.gross={rec.output_value} "
          f"(= 1000.00 + 80, exact; formula {FORMULA}/1, fp {rec.formula_fingerprint[:12]}…)")

    # 4. whole-chain provenance walk — every link re-verified in this walk
    walk = deriv.trace_derivation(rec.derivation_id)
    assert type(walk).__name__ == "DerivationTraceSuccess", walk
    print("4. trace         -> derivation → formula → inputs → normalization → "
          "extraction → binding → Document/Page/span → Capture S1: ALL LINKS OK")

    # 5. idempotent replay + explicit refusals (nothing invented, nothing persisted)
    replay = deriv.derive(normalization_id, FORMULA, "1")
    assert isinstance(replay, DerivationAlreadyExists)
    ghost = deriv.derive(normalization_id, "no-such-formula", "1")
    assert isinstance(ghost, DerivationFormulaNotRegistered)
    cap2 = cap.ingest(CaptureService.aggregate(PAGES_NO_TAX),
                      source_label="smoke-deriv-defer").capture_id
    doc2 = recon.reconstruct(cap2).document.document_id
    ext2 = ext.extract(doc2, "reference-delimited-v1")
    binder.bind_extraction(ext2.extraction.extraction_id)   # evidence first (fail-closed)
    norm2 = norm.normalize(ext2.extraction.extraction_id, "kandoo-norm-v1")
    deferred = deriv.derive(norm2.record.normalization_id, FORMULA, "1")
    assert isinstance(deferred, DerivationDeferred)          # NOT_DERIVABLE, no value
    assert deferred.reason_code == "input-missing"
    assert deriv.derivations_for_normalization(norm2.record.normalization_id) == ()
    print("5. refusals      -> replay=AlreadyExists (INV-D-1:1); unknown formula "
          "refused; missing input → NOT_DERIVABLE (no value, no UNRESOLVED, "
          "nothing persisted)")

    # 6. restart — durability + verified reload + replay still idempotent
    for store in (cstore, rstore, estore, xstore, bstore, nstore, dstore):
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
    registry = DerivationFormulaRegistry(ReferenceDerivationFormulasV1(), S1Service())
    deriv = DerivationService(dstore, norm, ext, binder, recon, registry, S1Service())
    read = deriv.read_derivation(rec.derivation_id)
    assert isinstance(read, DerivationReadSuccess)
    assert read.record.output_value == "1080"
    assert type(deriv.trace_derivation(rec.derivation_id)).__name__ \
        == "DerivationTraceSuccess"
    assert isinstance(deriv.derive(normalization_id, FORMULA, "1"),
                      DerivationAlreadyExists)
    print("6. restart       -> derivation durable; verified read VALID; whole chain "
          "re-verifies; replay idempotent")

    # 7. tamper — verified read never delivers broken content
    dstore._conn.execute(
        "UPDATE derivation_records SET output_value = 'TAMPERED' "
        "WHERE derivation_id = ?", (rec.derivation_id,))
    broken = deriv.read_derivation(rec.derivation_id)
    assert isinstance(broken, DerivationReadIntegrityFailure)
    assert not hasattr(broken, "record")
    print("7. tamper        -> mutated DERIVED value caught (fingerprint mismatch); "
          "content withheld; outcome explicit")

    # 8. vocabulary sweep — DERIVED is the only label this layer ever stored
    rows = dstore._conn.execute(
        "SELECT output_provenance, COUNT(*) AS n FROM derivation_records "
        "GROUP BY output_provenance").fetchall()
    assert [(r["output_provenance"], r["n"]) for r in rows] == [("DERIVED", 1)]
    assert not dstore._conn.execute(
        "SELECT COUNT(*) AS n FROM derivation_records WHERE output_provenance = "
        "'UNRESOLVED'").fetchone()["n"]
    for store in (cstore, rstore, estore, xstore, bstore, nstore, dstore):
        store.close()
    print("8. vocabulary    -> stored provenance sweep: exactly one label — DERIVED "
          "(UNRESOLVED structurally impossible; P5 territory)")
    print("SMOKE OK — Exact Derivation is real, durable, deterministic, evidence-bound, "
          "and traceable end-to-end (ready for Canonicalization Gate consumers)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-derivation-smoke"))
