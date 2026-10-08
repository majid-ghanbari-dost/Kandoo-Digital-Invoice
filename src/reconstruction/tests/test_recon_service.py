"""Reconstruction service — build path: verified capture → durable ordered Document.

Covers AC-2.1.1 (build + linkage), AC-2.1.2 (deterministic ordering), AC-2.1.3
(page→source linkage + structural no-extraction boundary), byte/content fidelity,
and every explicit source-side outcome.
"""
import dataclasses

from capture import (
    CaptureService,
    CaptureStore,
    CaptureState,
    S1Service,
)

from reconstruction import (
    ReconstructAlreadyExists,
    ReconstructCompleted,
    ReconstructSourceIntegrityFailure,
    ReconstructSourceRefused,
    ReconstructSettledFailure,
    ReconstructUniquenessConflict,
    DocumentRecord,
    PageView,
    DocumentReadSuccess,
    derive_pages,
    reassemble,
)

from helpers import ingest_parts

PARTS = [b"INVOICE #1 header bytes", b"line items page bytes", b"totals page bytes"]


def test_reconstruct_from_completed_capture_builds_document_with_ordered_pages(stack):
    cap = ingest_parts(stack.capture, PARTS)
    outcome = stack.recon.reconstruct(cap)
    assert isinstance(outcome, ReconstructCompleted), outcome
    doc = outcome.document
    assert doc.capture_id == cap
    assert doc.document_state.value == "COMPLETED"
    assert doc.page_count == len(PARTS)
    assert doc.capture_s1 and doc.capture_s1_algorithm_id == "sha256-v1"
    assert doc.created_at and doc.integrity_verified_at
    assert doc.settlement_note is None
    read = stack.recon.read_document(doc.document_id)
    assert isinstance(read, DocumentReadSuccess)
    assert [p.content for p in read.pages] == PARTS          # verbatim, ordered
    assert [p.page_index for p in read.pages] == [0, 1, 2]


def test_reconstruct_is_idempotent_per_capture_inv_r11(stack):
    cap = ingest_parts(stack.capture, PARTS)
    first = stack.recon.reconstruct(cap)
    assert isinstance(first, ReconstructCompleted)
    again = stack.recon.reconstruct(cap)
    assert isinstance(again, ReconstructAlreadyExists)
    assert again.document_id == first.document.document_id
    assert again.capture_id == cap
    completed, total = stack.recon_store.count_for_capture(cap)
    assert (completed, total) == (1, 1)                      # no second document exists


def test_reconstruct_refused_for_unknown_or_non_completed_capture(stack):
    assert isinstance(stack.recon.reconstruct("does-not-exist"), ReconstructSourceRefused)
    # ACTIVE (unresolved) capture — refused, nothing created
    rec = stack.capture_store.create_active(received_at="2026-10-01T00:00:00+00:00")
    out = stack.recon.reconstruct(rec.capture_id)
    refused = isinstance(out, ReconstructSourceRefused)
    assert refused and out.capture_state == CaptureState.ACTIVE.value
    assert stack.recon_store.count_for_capture(rec.capture_id) == (0, 0)


def test_reconstruct_fails_explicitly_on_capture_integrity_failure_no_document_created(stack):
    cap = ingest_parts(stack.capture, PARTS)
    stack.capture_store._conn.execute(
        "UPDATE artifact_content SET content = ?", (b"corrupted!!",))
    outcome = stack.recon.reconstruct(cap)
    assert isinstance(outcome, ReconstructSourceIntegrityFailure)
    assert outcome.capture_id == cap
    assert outcome.reason                                    # coarse reason surfaced
    assert stack.recon_store.count_for_capture(cap) == (0, 0)   # nothing created, no residue


def test_ordering_is_deterministic_and_bound_to_input_order(stack):
    cap1 = ingest_parts(stack.capture, [b"A", b"B", b"C"])
    cap2 = ingest_parts(stack.capture, [b"C", b"B", b"A"])   # different order → different S1
    o1 = stack.recon.reconstruct(cap1)
    o2 = stack.recon.reconstruct(cap2)
    assert isinstance(o1, ReconstructCompleted) and isinstance(o2, ReconstructCompleted)
    r1 = stack.recon.read_document(o1.document.document_id)
    r2 = stack.recon.read_document(o2.document.document_id)
    assert [p.content for p in r1.pages] == [b"A", b"B", b"C"]
    assert [p.content for p in r2.pages] == [b"C", b"B", b"A"]
    # re-reading is stable — order never drifts between reads
    r1b = stack.recon.read_document(o1.document.document_id)
    assert [p.content for p in r1b.pages] == [p.content for p in r1.pages]


def test_byte_content_fidelity_pages_tile_capture_artifact_exactly(stack):
    cap = ingest_parts(stack.capture, PARTS)
    outcome = stack.recon.reconstruct(cap)
    read = stack.recon.read_document(outcome.document.document_id)
    contents = [p.content for p in read.pages]
    assert reassemble(contents) == CaptureService.aggregate(PARTS)   # canonical join
    assert b"".join(contents) == b"".join(PARTS)                     # verbatim tiling
    assert all(p.byte_len == len(p.content) for p in read.pages)
    # fingerprints anchor every page to its exact bytes
    s1 = S1Service()
    for p in read.pages:
        assert s1.verify(p.content, p.page_fingerprint, p.fingerprint_algorithm_id).outcome == "VALID"


def test_structural_no_extraction_boundary_model_and_read_surface(stack):
    # 1) model field sets are exactly the contract sets — no extraction-ish field exists
    assert {f.name for f in dataclasses.fields(DocumentRecord)} == {
        "document_id", "capture_id", "capture_s1", "capture_s1_algorithm_id", "created_at",
        "document_state", "integrity_status", "integrity_verified_at", "page_count",
        "document_fingerprint", "fingerprint_algorithm_id", "settlement_note"}
    assert {f.name for f in dataclasses.fields(PageView)} == {
        "page_index", "content", "byte_len", "page_fingerprint", "fingerprint_algorithm_id"}
    # 2) store columns carry structure/fingerprints only
    doc_cols = {r["name"] for r in stack.recon_store._conn.execute(
        "PRAGMA table_info(reconstruction_documents)").fetchall()}
    page_cols = {r["name"] for r in stack.recon_store._conn.execute(
        "PRAGMA table_info(document_pages)").fetchall()}
    banned = {"text", "ocr_text", "amount", "total", "vendor", "customer", "invoice_number",
              "extracted", "normalized", "canonical", "s2"}
    assert not (doc_cols & banned) and not (page_cols & banned)
    # 3) invoice-looking content reconstructs to raw bytes and NOTHING else
    cap = ingest_parts(stack.capture, [b"Invoice No: 123, Total: 100 USD", b"Vendor: ACME"])
    outcome = stack.recon.reconstruct(cap)
    read = stack.recon.read_document(outcome.document.document_id)
    assert isinstance(read, DocumentReadSuccess)
    delivered_fields = {f.name for f in dataclasses.fields(DocumentReadSuccess)}
    assert delivered_fields == {
        "document_id", "capture_id", "capture_s1", "capture_s1_algorithm_id",
        "page_count", "pages", "verified_at"}
    assert [p.content for p in read.pages] == [b"Invoice No: 123, Total: 100 USD", b"Vendor: ACME"]


def test_concurrent_shaped_duplicate_reconstruction_loses_explicitly(stack):
    # Sequential simulation of the UAC loser path (thread race covered in test_concurrency):
    # an ACTIVE document for a capture that already has a COMPLETED document.
    cap = ingest_parts(stack.capture, PARTS)
    winner = stack.recon.reconstruct(cap)
    assert isinstance(winner, ReconstructCompleted)
    loser = stack.recon_store.create_active_document(
        capture_id=cap, capture_s1=winner.document.capture_s1,
        capture_s1_algorithm_id=winner.document.capture_s1_algorithm_id,
        document_fingerprint=winner.document.document_fingerprint,
        fingerprint_algorithm_id=winner.document.fingerprint_algorithm_id)
    stack.recon_store.persist_pages(loser.document_id, [(b"x", winner.document.capture_s1, "sha256-v1")])
    stack.recon_store.record_verification(loser.document_id, "VALID", "t")
    assert stack.recon_store.complete_document(loser.document_id) == "UAC_UNIQUENESS_CONFLICT"
    stack.recon_store.settle_failed(loser.document_id,
                                    "uniqueness conflict: a COMPLETED document for the same capture_id exists")
    completed, total = stack.recon_store.count_for_capture(cap)
    assert (completed, total) == (1, 2)
    assert not isinstance(stack.recon.reconstruct(cap), ReconstructSettledFailure)
