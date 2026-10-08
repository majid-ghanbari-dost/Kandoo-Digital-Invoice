"""Cold-start smoke check for WP-2.2 — runs the evidence path end-to-end without pytest.

  Capture موجود → Reconstruction → Document → ordered Pages → verified Read
  → durable tamper-evident Evidence (DOCUMENT_COMPLETED + spans → VERIFIED_READ → …)

Usage: python3 kandoo/src/run_smoke_evidence.py /tmp/kandoo-evidence-smoke
Creates <path>-capture.db, <path>-recon.db and <path>-evidence.db next to each other.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import (  # noqa: E402
    CaptureService,
    CaptureStore,
    ReadSuccess,
    S1Service,
)

from reconstruction import (  # noqa: E402
    EV_DOCUMENT_COMPLETED,
    EV_RECOVERY_SETTLED,
    EV_VERIFIED_READ,
    DocumentReadIntegrityFailure,
    DocumentReadSuccess,
    EvidenceReadIntegrityFailure,
    EvidenceReadSuccess,
    ReconstructCompleted,
    ReconstructionService,
    ReconstructionStore,
    EvidenceStore,
    run_reconstruction_recovery,
)

PAGES = [b"evidence-smoke-header;", b"evidence-smoke-lines;", b"evidence-smoke-totals;"]


def main(base: str) -> int:
    capture_db, recon_db, evidence_db = (f"{base}-capture.db", f"{base}-recon.db",
                                         f"{base}-evidence.db")
    cstore = CaptureStore(capture_db)
    cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    estore = EvidenceStore(evidence_db, S1Service())
    svc = ReconstructionService(rstore, cap, S1Service(), evidence=estore)

    artifact = CaptureService.aggregate(PAGES)
    ingest = cap.ingest(artifact, source_label="smoke-evidence")
    built = svc.reconstruct(ingest.capture_id)
    assert isinstance(built, ReconstructCompleted), built
    doc_id = built.document.document_id
    ev = estore.read_document_evidence(doc_id)
    assert isinstance(ev, EvidenceReadSuccess) and len(ev.events) == 1
    completed = ev.events[0]
    assert completed.event_type == EV_DOCUMENT_COMPLETED
    assert completed.payload["page_count"] == 3
    assert len(completed.payload["page_spans"]) == 3
    print(f"1. reconstruct  -> COMPLETED document_id={doc_id[:12]}… "
          f"evidence=DOCUMENT_COMPLETED (3 page spans, capture-bound)")

    read = svc.read_document(doc_id)
    assert isinstance(read, DocumentReadSuccess)
    ev = estore.read_document_evidence(doc_id)
    assert [(e.event_type, e.payload.get("verdict")) for e in ev.events] == [
        (EV_DOCUMENT_COMPLETED, None), (EV_VERIFIED_READ, "VALID")]
    audit = estore.verify_chain()
    assert audit.valid and audit.records == 2
    print(f"2. verified read -> VALID; evidence chain "
          f"[DOCUMENT_COMPLETED → VERIFIED_READ/VALID]; verify_chain OK (records={audit.records})")

    src = cap.read_evidence(ingest.capture_id)
    assert isinstance(src, ReadSuccess)
    durable_pages = rstore.get_pages(doc_id)
    for span, page in zip(completed.payload["page_spans"], durable_pages):
        assert artifact[span["byte_start"]:span["byte_end"]] == page.content
        assert span["page_fingerprint"] == page.page_fingerprint
    print("3. span fidelity -> artifact[start:end] == durable page bytes (byte-exact), "
          "page fingerprints match")

    cstore.close(); rstore.close(); estore.close()
    cstore = CaptureStore(capture_db); cap = CaptureService(cstore, S1Service())
    rstore = ReconstructionStore(recon_db)
    estore = EvidenceStore(evidence_db, S1Service())
    svc = ReconstructionService(rstore, cap, S1Service(), evidence=estore)
    report = run_reconstruction_recovery(rstore, S1Service(), evidence=estore)
    assert report.complete and report.remaining_active == 0
    read2 = svc.read_document(doc_id)
    assert isinstance(read2, DocumentReadSuccess)
    ev = estore.read_document_evidence(doc_id)
    assert ev.verified_up_to_seq == 3 and estore.verify_chain().valid
    print(f"4. restart      -> recovery complete; evidence durable; chain valid up to "
          f"seq={ev.verified_up_to_seq}; post-restart read VALID evidenced")

    rstore._conn.execute(
        "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = 2",
        (b"evidence-smoke-TAMPERED;", doc_id))
    bad = svc.read_document(doc_id)
    assert isinstance(bad, DocumentReadIntegrityFailure)
    ev = estore.read_document_evidence(doc_id)
    assert ev.events[-1].event_type == EV_VERIFIED_READ
    assert ev.events[-1].payload["verdict"] == "FAILED"
    assert ev.events[-1].payload["reason"] == "page content mismatch"
    assert estore.verify_chain().valid
    print("5. page tamper  -> read FAILED; evidence VERIFIED_READ/FAILED recorded "
          "(audit trail of the integrity failure)")

    estore._conn.execute(
        "UPDATE reconstruction_evidence SET payload = payload || ? WHERE seq = 1",
        (',"forged":"x"',))
    broken = estore.read_document_evidence(doc_id)
    assert isinstance(broken, EvidenceReadIntegrityFailure)
    print(f"6. evidence tamper -> explicit IntegrityFailure at seq={broken.failure_seq} "
          f"(no silent broken evidence read)")

    rstore.close(); cstore.close(); estore.close()
    print("SMOKE OK — Capture → Reconstruction → verified Read with durable, "
          "tamper-evident, structural Evidence works end-to-end")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-evidence-smoke"))
