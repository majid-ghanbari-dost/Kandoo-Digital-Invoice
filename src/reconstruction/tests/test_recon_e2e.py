"""E2E — the full mandated MVP path, real cross-layer journey + invariant sweep.

  Capture موجود → Reconstruction → Document → ordered Pages → verified Read
  + restart/recovery + tamper + source-integrity failure + traceability + no-extraction.
"""
from capture import (
    CaptureService,
    CaptureStore,
    CaptureState,
    IntegrityStatus,
    S1Service,
)

from reconstruction import (
    DocumentIntegrity,
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadSuccess,
    DocumentState,
    ReconstructAlreadyExists,
    ReconstructCompleted,
    ReconstructSourceIntegrityFailure,
    ReconstructionStore,
    run_reconstruction_recovery,
)

from helpers import ingest_parts

PARTS = [b"e2e-invoice-header-bytes;", b"e2e-line-items-bytes;", b"e2e-totals-bytes;"]


def test_full_reconstruction_mvp_journey(make_stack, capture_db, recon_db):
    # ---- 1. existing capture (WP-1.1 real path) -------------------------------
    stack = make_stack()
    try:
        cap = ingest_parts(stack.capture, PARTS)
        dup = stack.capture.ingest(CaptureService.aggregate(PARTS))
        assert dup.existing_capture_id == cap                       # capture idempotency intact

        # ---- 2. Reconstruction → Document -------------------------------------
        outcome = stack.recon.reconstruct(cap)
        assert isinstance(outcome, ReconstructCompleted), outcome
        doc = outcome.document
        doc_id = doc.document_id

        # ---- 3. ordered pages + verified read + byte fidelity -----------------
        read = stack.recon.read_document(doc_id)
        assert isinstance(read, DocumentReadSuccess)
        assert [p.content for p in read.pages] == PARTS             # ordered, byte-exact
        assert CaptureService.aggregate([p.content for p in read.pages]) \
            == CaptureService.aggregate(PARTS)

        # ---- 4. duplicate reconstruction is explicit --------------------------
        again = stack.recon.reconstruct(cap)
        assert isinstance(again, ReconstructAlreadyExists)
        assert again.document_id == doc_id
    finally:
        stack.close()

    # ---- 5. restart: durability + startup recovery ----------------------------
    stack2 = make_stack()
    try:
        report = run_reconstruction_recovery(stack2.recon_store, S1Service())
        assert report.complete and report.remaining_active == 0
        read2 = stack2.recon.read_document(doc_id)
        assert isinstance(read2, DocumentReadSuccess)
        assert [p.content for p in read2.pages] == PARTS            # survived the restart
        assert read2.capture_id == cap

        # ---- 6. tamper a page → explicit failure, never silent ----------------
        stack2.recon_store._conn.execute(
            "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = 2",
            (b"e2e-TAMPERED;", doc_id))
        bad = stack2.recon.read_document(doc_id)
        assert isinstance(bad, DocumentReadIntegrityFailure)
        assert bad.reason == "page content mismatch"
        rec = stack2.recon_store.get_document(doc_id)
        assert rec.integrity_status is DocumentIntegrity.FAILED
        assert rec.document_state is DocumentState.COMPLETED        # lifecycle untouched by reads

        # ---- 7. capture-side corruption blocks NEW reconstruction explicitly --
        # (the already-built document correctly answers AlreadyExists — the durable,
        # self-verified document does not depend on re-reading the capture)
        still_idempotent = stack2.recon.reconstruct(cap)
        assert isinstance(still_idempotent, ReconstructAlreadyExists)
        cap_bad = ingest_parts(stack2.capture, [b"e2e-doomed-capture;"])
        stack2.capture_store._conn.execute(
            "UPDATE artifact_content SET content = ?", (b"e2e-corrupted!!",))
        refused = stack2.recon.reconstruct(cap_bad)
        assert isinstance(refused, ReconstructSourceIntegrityFailure)
        assert stack2.recon_store.count_for_capture(cap_bad) == (0, 0)   # nothing created

        # ---- 8. a fresh capture still reconstructs cleanly --------------------
        cap2 = ingest_parts(stack2.capture, [b"e2e-second-document;"])
        o2 = stack2.recon.reconstruct(cap2)
        assert isinstance(o2, ReconstructCompleted)
        r2 = stack2.recon.read_document(o2.document.document_id)
        assert isinstance(r2, DocumentReadSuccess)
        assert [p.content for p in r2.pages] == [b"e2e-second-document;"]
    finally:
        stack2.close()

    # ---- 9. invariant sweep on cold storage ------------------------------------
    cstore = CaptureStore(capture_db)
    rstore = ReconstructionStore(recon_db)
    try:
        assert len(rstore.enumerate_active()) == 0                  # INV: zero ACTIVE
        for cap_id in (cap, cap2):
            completed, total = rstore.count_for_capture(cap_id)
            assert completed in (0, 1)                              # INV-R-1:1 (≤1 COMPLETED)
        final = rstore.get_document(o2.document.document_id)
        assert final.capture_id == cap2 and final.capture_s1        # traceability present
        assert final.created_at and final.integrity_verified_at     # timestamps present
    finally:
        rstore.close()
        cstore.close()


def test_no_interpretive_data_enters_the_reconstruction_path(make_stack):
    """The mandated boundary test: even invoice-shaped content produces structure only."""
    stack = make_stack()
    try:
        cap = ingest_parts(stack.capture, [
            b"Invoice No: 99\nDate: 2026-10-01\nTotal: 1250.00 USD",
            b"Vendor: ACME GmbH\nVAT: DE123456789",
        ])
        outcome = stack.recon.reconstruct(cap)
        assert isinstance(outcome, ReconstructCompleted)
        doc = outcome.document
        # the document record itself carries only structure/identity — assert by fields
        assert doc.page_count == 2
        # read delivers exactly the raw bytes; nothing parsed, nothing added
        read = stack.recon.read_document(doc.document_id)
        assert isinstance(read, DocumentReadSuccess)
        delivered = b"".join(p.content for p in read.pages)
        assert delivered == (b"Invoice No: 99\nDate: 2026-10-01\nTotal: 1250.00 USD"
                             b"Vendor: ACME GmbH\nVAT: DE123456789")
        for page in read.pages:
            assert isinstance(page.content, bytes)
            assert page.page_fingerprint and page.fingerprint_algorithm_id == "sha256-v1"
        # no extraction-ish attribute exists anywhere on the outcome types
        assert not any(hasattr(read, a) for a in
                       ("fields", "amounts", "vendor", "total", "invoice_number", "items"))
        # capture layer remained the identity owner (D-02): document's s1 IS the capture's s1
        cap_rec = stack.capture_store.get_record(cap)
        assert read.capture_s1 == cap_rec.s1
        assert cap_rec.capture_state is CaptureState.COMPLETED       # capture untouched
        assert cap_rec.integrity_status is IntegrityStatus.VALID
    finally:
        stack.close()
