"""Cold-start smoke check for WP-3.1 — runs the extraction path end-to-end without pytest.

  Capture → Reconstruction → Document → ordered Pages → verified Read
  → Extraction-ready input → registered engine → Extracted structured data
  (durable, traceable, verbatim spans) → verified extraction read

Usage: python3 kandoo/src/run_smoke_extraction.py /tmp/kandoo-extraction-smoke
Creates <path>-capture.db, <path>-recon.db and <path>-extraction.db next to each other.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import (  # noqa: E402
    CaptureService,
    CaptureStore,
    S1Service,
)

from reconstruction import (  # noqa: E402
    ReconstructCompleted,
    ReconstructionService,
    ReconstructionStore,
)

from extraction import (  # noqa: E402
    ExtractionAlreadyExists,
    ExtractionCompleted,
    ExtractionEngineFailed,
    ExtractionEngineNotRegistered,
    ExtractionReadIntegrityFailure,
    ExtractionReadSuccess,
    ExtractionSourceRefused,
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
)

PAGES = [
    b"invoice.number=SMOKE-2026-001\ninvoice.date=2026-10-01\n",
    b"seller.name=Kandoo GmbH\ntotal.gross=129.90\n",
]


def main(base: str) -> int:
    capture_db, recon_db, extraction_db = (f"{base}-capture.db", f"{base}-recon.db",
                                           f"{base}-extraction.db")
    cstore = CaptureStore(capture_db)
    cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    recon = ReconstructionService(rstore, cap, S1Service())
    estore = ExtractionStore(extraction_db, S1Service())
    ext = ExtractionService(estore, recon,
                            {"reference-delimited-v1": ReferenceDelimitedEngine()},
                            S1Service())

    artifact = CaptureService.aggregate(PAGES)
    capture_id = cap.ingest(artifact, source_label="smoke-extraction").capture_id
    built = recon.reconstruct(capture_id)
    assert isinstance(built, ReconstructCompleted), built
    document_id = built.document.document_id
    print(f"1. reconstruct  -> COMPLETED document_id={document_id[:12]}… (2 pages)")

    done = ext.extract(document_id, "reference-delimited-v1")
    assert isinstance(done, ExtractionCompleted), done
    extraction_id = done.extraction.extraction_id
    rec = done.extraction
    assert (rec.document_id, rec.capture_id, rec.capture_s1) == (
        document_id, capture_id, built.document.capture_s1)
    assert rec.field_count == 4
    names = [f.field_name for f in done.fields]
    assert names == ["invoice.number", "invoice.date", "seller.name", "total.gross"], names
    print(f"2. extract      -> ExtractionCompleted: 4 verbatim fields {names} "
          f"(each bound to page_index + byte span + page_fingerprint)")

    # span fidelity — values slice the SOURCE artifact byte-exactly (no transformation)
    durable_pages = rstore.get_pages(document_id)
    for field in done.fields:
        page = durable_pages[field.span.page_index]
        assert bytes(page.content)[field.span.byte_start:field.span.byte_end].decode(
            field.value_encoding) == field.value_verbatim
    assert done.fields[0].value_verbatim == "SMOKE-2026-001"
    print("3. span fidelity -> page bytes[start:end] decoded == value_verbatim "
          "(byte-exact, EXTRACTED-only provenance)")

    replay = ext.extract(document_id, "reference-delimited-v1")
    assert isinstance(replay, ExtractionAlreadyExists) and \
        replay.extraction_id == extraction_id
    print("4. idempotency  -> same document+engine replay returns the SAME extraction_id "
          "(INV-X-1:1, no second record)")

    cstore.close(); rstore.close(); estore.close()
    cstore = CaptureStore(capture_db); cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    recon = ReconstructionService(rstore, cap, S1Service())
    estore = ExtractionStore(extraction_db, S1Service())
    ext = ExtractionService(estore, recon,
                            {"reference-delimited-v1": ReferenceDelimitedEngine()},
                            S1Service())
    read = ext.read_extraction(extraction_id)
    assert isinstance(read, ExtractionReadSuccess) and len(read.fields) == 4
    assert ext.extraction_ids_for_document(document_id) == (extraction_id,)
    print(f"5. restart      -> record + fields durable; verified read VALID "
          f"(verified_at={read.verified_at[:19]}…)")

    ghost = ext.extract(document_id, "no-such-engine")
    assert isinstance(ghost, ExtractionEngineNotRegistered), ghost
    estore._conn.execute(
        "UPDATE extraction_fields SET value_verbatim = 'SMOKE-TAMPERED' "
        "WHERE extraction_id = ? AND field_seq = 0", (extraction_id,))
    broken = ext.read_extraction(extraction_id)
    assert isinstance(broken, ExtractionReadIntegrityFailure), broken
    assert not hasattr(broken, "fields")
    bin_doc = recon.reconstruct(cap.ingest(
        CaptureService.aggregate([b"name=\xff\xfe"]), source_label="smoke-bin").capture_id)
    engine_fail = ext.extract(bin_doc.document.document_id, "reference-delimited-v1")
    assert isinstance(engine_fail, ExtractionEngineFailed), engine_fail
    refused = ext.extract("no-such-document", "reference-delimited-v1")
    assert isinstance(refused, ExtractionSourceRefused), refused
    print("6. explicit outcomes -> unknown engine / tampered record (read FAILED, "
          "content withheld) / undecodable page (engine failed) / unknown document "
          "(refused) — all explicit, nothing silent")

    cstore.close(); rstore.close(); estore.close()
    print("SMOKE OK — Document/Page → Extraction-ready input → Extracted structured "
          "data works end-to-end (durable, traceable, verbatim, engine-agnostic)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-extraction-smoke"))
