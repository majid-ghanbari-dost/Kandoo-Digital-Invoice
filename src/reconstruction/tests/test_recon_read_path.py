"""Verified document read — VOR pattern bound to documents (AC-2.1.4).

Every-read verification, write-before-outcome, content never delivered without the
same-read VALID verdict, coarse reasons only, no silent broken read.
"""
import pytest

from reconstruction import (
    DocumentIntegrity,
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadSuccess,
    DocumentState,
    ReconstructCompleted,
    READ_REASON_DOC_MISMATCH,
    READ_REASON_PAGE_MISMATCH,
)

from helpers import ingest_parts

PARTS = [b"read-page-alpha;", b"read-page-beta;", b"read-page-gamma;"]


def _completed(stack, parts=PARTS):
    cap = ingest_parts(stack.capture, parts)
    outcome = stack.recon.reconstruct(cap)
    assert isinstance(outcome, ReconstructCompleted), outcome
    return outcome.document


def test_healthy_read_delivers_ordered_pages_with_fresh_verdict(stack):
    doc = _completed(stack)
    read = stack.recon.read_document(doc.document_id)
    assert isinstance(read, DocumentReadSuccess)
    assert read.document_id == doc.document_id
    assert read.capture_id == doc.capture_id
    assert read.capture_s1 == doc.capture_s1 and read.capture_s1_algorithm_id == "sha256-v1"
    assert read.page_count == 3
    assert [p.page_index for p in read.pages] == [0, 1, 2]
    assert [p.content for p in read.pages] == PARTS
    rec = stack.recon_store.get_document(doc.document_id)
    assert rec.integrity_status is DocumentIntegrity.VALID
    assert rec.integrity_verified_at == read.verified_at        # same-read verdict recorded


def test_every_read_reverifies_no_caching_truthful_latest_result(stack):
    doc = _completed(stack)
    page_ref = stack.recon_store.get_pages(doc.document_id)[1].page_ref
    stack.recon_store._conn.execute(
        "UPDATE document_pages SET content = ? WHERE page_ref = ?", (b"tampered!", page_ref))
    bad = stack.recon.read_document(doc.document_id)
    assert isinstance(bad, DocumentReadIntegrityFailure)
    assert bad.reason == READ_REASON_PAGE_MISMATCH
    assert stack.recon_store.get_document(doc.document_id).integrity_status \
        is DocumentIntegrity.FAILED
    # restore the exact bytes → the next read verifies VALID again (truthful latest result,
    # NOT auto-repair: content untouched by the layer, verdict recomputed every read)
    stack.recon_store._conn.execute(
        "UPDATE document_pages SET content = ? WHERE page_ref = ?", (PARTS[1], page_ref))
    good = stack.recon.read_document(doc.document_id)
    assert isinstance(good, DocumentReadSuccess)
    assert stack.recon_store.get_document(doc.document_id).integrity_status \
        is DocumentIntegrity.VALID


def test_tampered_page_fails_explicitly_and_never_delivers_content(stack):
    doc = _completed(stack)
    stack.recon_store._conn.execute(
        "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = 0",
        (b"\x00corrupted", doc.document_id))
    bad = stack.recon.read_document(doc.document_id)
    assert isinstance(bad, DocumentReadIntegrityFailure)
    assert bad.reason == READ_REASON_PAGE_MISMATCH
    assert bad.verified_at
    assert not hasattr(bad, "pages") and not hasattr(bad, "content")   # structurally content-free


def test_document_fingerprint_mismatch_fails_explicitly(stack):
    doc = _completed(stack)
    # flip the document-level anchor only (pages still intact) → reassembly check must fire
    stack.recon_store._conn.execute(
        "UPDATE reconstruction_documents SET document_fingerprint = ? WHERE document_id = ?",
        ("f" * 64, doc.document_id))
    bad = stack.recon.read_document(doc.document_id)
    assert isinstance(bad, DocumentReadIntegrityFailure)
    assert bad.reason == READ_REASON_DOC_MISMATCH


def test_read_refused_for_non_completed_or_unknown_documents(stack):
    assert isinstance(stack.recon.read_document("no-such-document"), DocumentReadRefused)
    doc = _completed(stack)
    # an ACTIVE document is refused with no content and no state change
    from reconstruction import ReconstructionStore
    active = stack.recon_store.create_active_document(
        capture_id="cap-x", capture_s1="a" * 64, capture_s1_algorithm_id="sha256-v1",
        document_fingerprint="a" * 64, fingerprint_algorithm_id="sha256-v1")
    out = stack.recon.read_document(active.document_id)
    assert isinstance(out, DocumentReadRefused)
    assert out.document_state == DocumentState.ACTIVE.value
    settled = stack.recon_store.create_active_document(
        capture_id="cap-y", capture_s1="b" * 64, capture_s1_algorithm_id="sha256-v1",
        document_fingerprint="b" * 64, fingerprint_algorithm_id="sha256-v1")
    stack.recon_store.settle_failed(settled.document_id, "pages missing/incomplete")
    out2 = stack.recon.read_document(settled.document_id)
    assert isinstance(out2, DocumentReadRefused)
    assert out2.document_state == DocumentState.FAILED_INCOMPLETE.value
    assert doc.document_id                                       # sanity: completed doc unaffected


def test_read_does_not_mutate_lifecycle_or_page_bytes(stack):
    doc = _completed(stack)
    before_pages = [(p.page_ref, p.content) for p in stack.recon_store.get_pages(doc.document_id)]
    before_state = stack.recon_store.get_document(doc.document_id).document_state
    stack.recon.read_document(doc.document_id)
    after_pages = [(p.page_ref, p.content) for p in stack.recon_store.get_pages(doc.document_id)]
    assert before_pages == after_pages                            # I-1/I-5 analog: no rewrite
    assert stack.recon_store.get_document(doc.document_id).document_state is before_state
