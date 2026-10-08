"""Startup recovery for Reconstruction — settlement of half-built documents (AC-2.1.5).

W2-analog (record without pages), W4-analog (pages durable, completion interrupted),
corruption, NO-VERDICT, uniqueness loser, idempotence, mixed residues.
"""
from capture import S1Service

from reconstruction import (
    DocumentIntegrity,
    DocumentReadSuccess,
    DocumentState,
    ReconstructCompleted,
    ReconstructionStore,
    derive_pages,
    reassemble,
    run_reconstruction_recovery,
)

from helpers import ingest_parts

NOTE = "uniqueness conflict: a COMPLETED document for the same capture_id exists"


def _make_active_with_pages(stack, capture_id, parts, corrupt_index=None, fp_id="sha256-v1"):
    """Simulate a crash window: ACTIVE document + durable pages, no verification/completion."""
    from capture import CaptureService
    artifact = CaptureService.aggregate(parts)
    s1 = S1Service()
    doc = stack.recon_store.create_active_document(
        capture_id=capture_id, capture_s1=s1.compute(artifact).s1,
        capture_s1_algorithm_id="sha256-v1",
        document_fingerprint=s1.compute(reassemble(derive_pages(artifact))).s1,
        fingerprint_algorithm_id="sha256-v1")
    page_rows = [(part, s1.compute(part).s1, fp_id) for part in derive_pages(artifact)]
    stack.recon_store.persist_pages(doc.document_id, page_rows)
    if corrupt_index is not None:
        stack.recon_store._conn.execute(
            "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = ?",
            (b"crashed-bytes", doc.document_id, corrupt_index))
    return doc


def test_record_without_pages_settles_pages_missing_incomplete(stack):
    doc = stack.recon_store.create_active_document(
        capture_id="cap-w2", capture_s1="a" * 64, capture_s1_algorithm_id="sha256-v1",
        document_fingerprint="a" * 64, fingerprint_algorithm_id="sha256-v1")
    report = run_reconstruction_recovery(stack.recon_store, S1Service())
    assert report.complete and report.remaining_active == 0
    assert ("x" not in dict(report.settled_failed)) and (doc.document_id, "pages missing/incomplete") in report.settled_failed
    settled = stack.recon_store.get_document(doc.document_id)
    assert settled.document_state is DocumentState.FAILED_INCOMPLETE
    assert settled.integrity_status is DocumentIntegrity.FAILED     # pinned, never valid


def test_interrupted_construction_with_all_pages_completes_at_recovery(stack):
    cap = ingest_parts(stack.capture, [b"rec-a;", b"rec-b;"])
    doc = _make_active_with_pages(stack, cap, [b"rec-a;", b"rec-b;"])
    report = run_reconstruction_recovery(stack.recon_store, S1Service())
    assert report.complete and doc.document_id in report.settled_completed
    rec = stack.recon_store.get_document(doc.document_id)
    assert rec.document_state is DocumentState.COMPLETED
    read = stack.recon.read_document(doc.document_id)               # usable after recovery
    assert isinstance(read, DocumentReadSuccess)
    assert [p.content for p in read.pages] == [b"rec-a;", b"rec-b;"]


def test_corrupted_page_in_residue_settles_verify_failed(stack):
    cap = ingest_parts(stack.capture, [b"good-a;", b"good-b;"])
    doc = _make_active_with_pages(stack, cap, [b"good-a;", b"good-b;"], corrupt_index=1)
    report = run_reconstruction_recovery(stack.recon_store, S1Service())
    assert report.complete
    assert (doc.document_id, "verify FAILED") in report.settled_failed
    settled = stack.recon_store.get_document(doc.document_id)
    assert settled.document_state is DocumentState.FAILED_INCOMPLETE
    assert settled.settlement_note == "verify FAILED"


def test_unknown_fingerprint_algorithm_is_conservative_never_completed(stack):
    cap = ingest_parts(stack.capture, [b"algo-a;"])
    doc = _make_active_with_pages(stack, cap, [b"algo-a;"], fp_id="md5-obsolete")
    report = run_reconstruction_recovery(stack.recon_store, S1Service())
    assert report.complete
    assert (doc.document_id, "verification unavailable (no verdict computable)") \
        in report.settled_failed
    assert any("Issue" not in i and "verification unavailable" in i for i in report.issues)
    settled = stack.recon_store.get_document(doc.document_id)
    assert settled.document_state is DocumentState.FAILED_INCOMPLETE


def test_uniqueness_conflict_loser_in_recovery_settles_explicitly(stack):
    cap = ingest_parts(stack.capture, [b"uniq-a;", b"uniq-b;"])
    winner = stack.recon.reconstruct(cap)
    assert isinstance(winner, ReconstructCompleted)
    loser = _make_active_with_pages(stack, cap, [b"uniq-a;", b"uniq-b;"])   # crashed duplicate
    report = run_reconstruction_recovery(stack.recon_store, S1Service())
    assert report.complete
    assert (loser.document_id, NOTE) in report.settled_failed
    assert winner.document.document_id in report.settled_completed or \
        stack.recon_store.get_document(winner.document.document_id).document_state \
        is DocumentState.COMPLETED
    completed, total = stack.recon_store.count_for_capture(cap)
    assert (completed, total) == (1, 2)


def test_recovery_is_idempotent_rerun_changes_nothing(stack):
    cap = ingest_parts(stack.capture, [b"idem-a;"])
    doc_ok = _make_active_with_pages(stack, cap, [b"idem-a;"])
    doc_bad = stack.recon_store.create_active_document(
        capture_id="cap-idem-bad", capture_s1="c" * 64, capture_s1_algorithm_id="sha256-v1",
        document_fingerprint="c" * 64, fingerprint_algorithm_id="sha256-v1")
    r1 = run_reconstruction_recovery(stack.recon_store, S1Service())
    assert r1.complete and r1.remaining_active == 0
    states_1 = {d: stack.recon_store.get_document(d).document_state
                for d in (doc_ok.document_id, doc_bad.document_id)}
    r2 = run_reconstruction_recovery(stack.recon_store, S1Service())
    assert r2.complete and r2.remaining_active == 0
    assert r2.settled_completed == [] and r2.settled_failed == []
    states_2 = {d: stack.recon_store.get_document(d).document_state
                for d in (doc_ok.document_id, doc_bad.document_id)}
    assert states_1 == states_2                                     # terminals never change


def test_mixed_residues_all_settled_zero_active_remain(stack):
    cap1 = ingest_parts(stack.capture, [b"mix-a;", b"mix-b;"])
    ok = _make_active_with_pages(stack, cap1, [b"mix-a;", b"mix-b;"])
    orphan = stack.recon_store.create_active_document(
        capture_id="cap-mix-orphan", capture_s1="d" * 64, capture_s1_algorithm_id="sha256-v1",
        document_fingerprint="d" * 64, fingerprint_algorithm_id="sha256-v1")
    cap3 = ingest_parts(stack.capture, [b"mix-c;"])
    corrupted = _make_active_with_pages(stack, cap3, [b"mix-c;"], corrupt_index=0)
    report = run_reconstruction_recovery(stack.recon_store, S1Service())
    assert report.complete and report.remaining_active == 0
    assert ok.document_id in report.settled_completed
    notes = dict(report.settled_failed)
    assert notes[orphan.document_id] == "pages missing/incomplete"
    assert notes[corrupted.document_id] == "verify FAILED"
    assert len(report.settled_completed) + len(report.settled_failed) == 3
