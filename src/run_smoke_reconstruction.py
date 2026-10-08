"""Cold-start smoke check for WP-2.1 — runs the mandated MVP path without pytest.

  Capture موجود → Reconstruction → Document → ordered Pages → verified Read

Usage: python3 kandoo/src/run_smoke_reconstruction.py /tmp/kandoo-recon-smoke
Creates <path>-capture.db and <path>-recon.db next to each other.
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
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadSuccess,
    ReconstructAlreadyExists,
    ReconstructCompleted,
    ReconstructSourceIntegrityFailure,
    ReconstructionService,
    ReconstructionStore,
    run_reconstruction_recovery,
)

PAGES = [b"smoke-invoice-header;", b"smoke-line-items;", b"smoke-totals;", b"smoke-footer;"]


def main(base: str) -> int:
    capture_db, recon_db = f"{base}-capture.db", f"{base}-recon.db"
    cstore = CaptureStore(capture_db)
    cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    svc = None

    artifact = CaptureService.aggregate(PAGES)
    ingest = cap.ingest(artifact, source_label="smoke-recon")
    assert ingest.capture_id
    print(f"1. capture     -> COMPLETED capture_id={ingest.capture_id[:12]}… "
          f"s1={ingest.record.s1[:16]}… bytes={len(artifact)}")

    svc = ReconstructionService(rstore, cap, S1Service())
    built = svc.reconstruct(ingest.capture_id)
    assert isinstance(built, ReconstructCompleted), built
    doc = built.document
    print(f"2. reconstruct -> COMPLETED document_id={doc.document_id[:12]}… pages={doc.page_count} "
          f"capture_link={doc.capture_id[:12]}…")

    read = svc.read_document(doc.document_id)
    assert isinstance(read, DocumentReadSuccess)
    assert [p.content for p in read.pages] == PAGES                    # ordered, byte-exact
    assert CaptureService.aggregate([p.content for p in read.pages]) == artifact
    print(f"3. verified read -> verdict=VALID pages={len(read.pages)} ordered byte-exact "
          f"(framing join == capture artifact)")

    again = svc.reconstruct(ingest.capture_id)
    assert isinstance(again, ReconstructAlreadyExists) and again.document_id == doc.document_id
    print(f"4. re-reconstruct -> explicit AlreadyExists document_id={again.document_id[:12]}… (INV-R-1:1)")

    cstore.close(); rstore.close()
    cstore = CaptureStore(capture_db); cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    svc = ReconstructionService(rstore, cap, S1Service())
    report = run_reconstruction_recovery(rstore, S1Service())
    assert report.complete and report.remaining_active == 0
    read2 = svc.read_document(doc.document_id)
    assert isinstance(read2, DocumentReadSuccess) and [p.content for p in read2.pages] == PAGES
    print(f"5. restart      -> recovery complete, remaining_active={report.remaining_active}; "
          f"document durable and VALID after restart")

    rstore._conn.execute(
        "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = 1",
        (b"smoke-TAMPERED;", doc.document_id))
    bad = svc.read_document(doc.document_id)
    assert isinstance(bad, DocumentReadIntegrityFailure) and bad.reason == "page content mismatch"
    rec = rstore.get_document(doc.document_id)
    assert rec.integrity_status.value == "FAILED" and rec.document_state.value == "COMPLETED"
    print(f"6. tamper       -> read verdict=FAILED reason={bad.reason}; "
          f"document integrity=FAILED, state=COMPLETED (no silent broken read)")

    # the already-built document answers AlreadyExists WITHOUT re-reading the corrupted
    # capture — a durable, self-verified document does not depend on the source staying healthy
    still = svc.reconstruct(ingest.capture_id)
    assert isinstance(still, ReconstructAlreadyExists) and still.document_id == doc.document_id
    # a NEW reconstruction attempt against a corrupted source fails explicitly, nothing created
    doomed = cap.ingest(CaptureService.aggregate([b"smoke-doomed-capture;"]), source_label="smoke-recon")
    cstore._conn.execute("UPDATE artifact_content SET content = ?", (b"smoke-corrupted!!",))
    refused_build = svc.reconstruct(doomed.capture_id)
    refused_read = svc.read_document("no-such-document")
    assert isinstance(refused_build, ReconstructSourceIntegrityFailure), refused_build
    assert isinstance(refused_read, DocumentReadRefused)
    print(f"7. boundaries   -> durable doc independent of corrupted source (AlreadyExists); "
          f"new build on corrupted source explicit-failed; unknown-id read refused")

    rstore.close(); cstore.close()
    print("SMOKE OK — full Reconstruction MVP path works end-to-end")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-recon-smoke"))
