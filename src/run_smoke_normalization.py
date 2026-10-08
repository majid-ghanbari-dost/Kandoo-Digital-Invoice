"""Cold-start smoke check for WP-4.1 — runs the normalization path end-to-end without pytest.

  Capture → Reconstruction → Extraction (frozen) → Evidence Binding (frozen)
  → P4 Normalization → Normalized structured data (durable, traceable, deterministic)
  → verified/reloaded output (input-ready for the future Canonicalization Gate)

Usage: python3 kandoo/src/run_smoke_normalization.py /tmp/kandoo-norm-smoke
Creates <path>-{capture,recon,extraction,bindings,normalization}*.db next to each other.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import CaptureService, CaptureStore, S1Service            # noqa: E402
from extraction import (                                               # noqa: E402
    BindingCompleted,
    ExtractionAlreadyExists,
    ExtractionCompleted,
    ExtractionBindingStore,
    ExtractionEvidenceBinder,
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
)
from normalization import (                                            # noqa: E402
    NormalizationAlreadyExists,
    NormalizationCompleted,
    NormalizationReadIntegrityFailure,
    NormalizationReadSuccess,
    NormalizationRulesetNotRegistered,
    NormalizationStatus,
    NormalizationStore,
    NormalizationService,
    ReferenceNormalizationRulesV1,
)
from reconstruction import (                                           # noqa: E402
    EvidenceStore,
    ReconstructionService,
    ReconstructionStore,
)

PAGES = [
    b"invoice.number=  SMOKE-2026-100 \ninvoice.date=2026-10-01\n",
    b"seller.name=Kandoo GmbH\ntotal.gross=1.234,56\ncurrency.label=EUR\n",
    b"quantity=12,345\nnotes=   \n",          # ambiguous number + whitespace-only → DEFERRED
]


def main(base: str) -> int:
    capture_db, recon_db = f"{base}-capture.db", f"{base}-recon.db"
    extraction_db, binding_db, norm_db = (f"{base}-extraction.db",
                                          f"{base}-bindings.db",
                                          f"{base}-normalization.db")
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

    # 1. frozen upstream: capture → document → extraction
    capture_id = cap.ingest(CaptureService.aggregate(PAGES),
                            source_label="smoke-normalization").capture_id
    document_id = recon.reconstruct(capture_id).document.document_id
    done = ext.extract(document_id, "reference-delimited-v1")
    assert isinstance(done, ExtractionCompleted), done
    extraction_id = done.extraction.extraction_id
    print(f"1. extract      -> frozen P3 path OK: document={document_id[:12]}…, "
          f"{done.extraction.field_count} verbatim fields")

    # 2. frozen WP-3.2 binding before normalization
    bound = binder.bind_extraction(extraction_id)
    assert isinstance(bound, BindingCompleted), bound
    print("2. bind         -> frozen WP-3.2 binding OK (five-link whole-chain verification)")

    # 3. normalize — TOTAL positional mapping with explicit statuses
    result = norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(result, NormalizationCompleted), result
    rec, fields = result.record, result.fields
    by_name = {f.source_field_name: f for f in fields}
    assert by_name["invoice.number"].normalized_value == "SMOKE-2026-100"     # trim
    assert by_name["total.gross"].normalized_value == "1234.56"              # 1.234,56
    assert by_name["invoice.date"].normalized_value == "2026-10-01"          # ISO date
    assert by_name["quantity"].status is NormalizationStatus.DEFERRED        # ambiguous
    assert by_name["notes"].status is NormalizationStatus.DEFERRED           # empty
    assert (rec.normalized_count, rec.deferred_count, rec.rejected_count) == (5, 2, 0)
    print(f"3. normalize    -> {rec.field_count} fields: "
          f"{rec.normalized_count} NORMALIZED, {rec.deferred_count} DEFERRED, "
          f"{rec.rejected_count} REJECTED (total mapping — nothing invented, nothing lost)")

    # 4. provenance walk: normalized → extraction verbatim → binding span → capture S1
    ext_read = ext.read_extraction(extraction_id)
    doc_read = recon.read_document(document_id)
    binding_read = binder.read_binding(extraction_id)
    assert doc_read.capture_s1 == ext_read.extraction.capture_s1
    for nf, entry in zip(fields, binding_read.entries):
        ef = {f.field_seq: f for f in ext_read.fields}[nf.field_seq]
        page = doc_read.pages[entry.page_index]
        verbatim = bytes(page.content)[entry.byte_start:entry.byte_end].decode("utf-8")
        assert verbatim == ef.value_verbatim
    print("4. provenance   -> walk verified: normalized field → (extraction_id, field_seq) "
          "→ verbatim span → Document/Page → Capture S1")

    # 5. idempotency + explicit refusals
    replay = norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(replay, NormalizationAlreadyExists) \
        and replay.normalization_id == rec.normalization_id
    ghost = norm.normalize(extraction_id, "no-such-ruleset")
    assert isinstance(ghost, NormalizationRulesetNotRegistered)
    print("5. idempotency  -> replay = explicit AlreadyExists (INV-N-1:1); "
          "unknown ruleset refused explicitly; zero residue")

    # 6. REJECTED status is explicit (control character = corruption marker, never laundered)
    cap2 = cap.ingest(CaptureService.aggregate([b"memo=bad\x00value\n"]),
                      source_label="smoke-norm-reject").capture_id
    doc2 = recon.reconstruct(cap2).document.document_id
    ext2 = ext.extract(doc2, "reference-delimited-v1")
    assert isinstance(ext2, ExtractionCompleted)
    norm2 = norm.normalize(ext2.extraction.extraction_id, "kandoo-norm-v1")
    assert isinstance(norm2, NormalizationCompleted)
    f2 = norm2.fields[0]
    assert f2.status is NormalizationStatus.REJECTED and f2.reason_code == "control-character"
    assert norm2.record.rejected_count == 1
    print("6. rejection    -> control-character value → REJECTED with reason "
          "(never 'fixed', never silent)")

    # 7. restart — durability + verified reload + idempotent replay
    for store in (cstore, rstore, estore, xstore, bstore, nstore):
        store.close()
    cstore = CaptureStore(capture_db); cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    estore = EvidenceStore(recon_db + ".evidence.db", S1Service())
    recon = ReconstructionService(rstore, cap, S1Service(), evidence=estore)
    xstore = ExtractionStore(extraction_db, S1Service())
    ext = ExtractionService(xstore, recon,
                            {"reference-delimited-v1": ReferenceDelimitedEngine()}, S1Service())
    bstore = ExtractionBindingStore(binding_db, S1Service())
    binder = ExtractionEvidenceBinder(bstore, ext, recon, estore, S1Service())
    nstore = NormalizationStore(norm_db, S1Service())
    norm = NormalizationService(nstore, ext,
                                {"kandoo-norm-v1": ReferenceNormalizationRulesV1()}, S1Service())
    read = norm.read_normalization(rec.normalization_id)
    assert isinstance(read, NormalizationReadSuccess)
    assert [(f.field_seq, f.status.value, f.normalized_value) for f in read.fields] == \
           [(f.field_seq, f.status.value, f.normalized_value) for f in fields]
    assert binder.read_binding(extraction_id).binding.binding_id
    assert isinstance(norm.normalize(extraction_id, "kandoo-norm-v1"),
                      NormalizationAlreadyExists)
    print("7. restart      -> record + fields durable; verified read VALID; "
          "frozen binding intact; replay idempotent")

    # 8. tamper detection — verified read never delivers broken content
    nstore._conn.execute(
        "UPDATE normalization_fields SET normalized_value = 'TAMPERED' "
        "WHERE normalization_id = ? AND field_seq = 0", (rec.normalization_id,))
    broken = norm.read_normalization(rec.normalization_id)
    assert isinstance(broken, NormalizationReadIntegrityFailure)
    assert not hasattr(broken, "fields")
    print("8. tamper       -> mutated normalized value caught (fingerprint mismatch); "
          "content withheld; outcome explicit")

    for store in (cstore, rstore, estore, xstore, bstore, nstore):
        store.close()
    print("SMOKE OK — Extraction → Normalization is real, durable, deterministic, "
          "engine-independent, and traceable end-to-end (ready for the Canonicalization Gate)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-normalization-smoke"))
