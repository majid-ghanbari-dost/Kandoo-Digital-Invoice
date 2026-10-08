"""Durable Document/Page Store — lifecycle, gates, INV-R-1:1, restart durability."""
import pytest

from capture import CaptureService, CaptureStore, S1Service

from reconstruction import (
    CompletionGateUnmet,
    DocumentCreationFailed,
    DocumentIntegrity,
    DocumentNotFound,
    DocumentState,
    IllegalFieldWrite,
    IllegalTransition,
    ReconstructionStore,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
)

from helpers import Stack, ingest_parts

FP = "0" * 64
FP_ID = "sha256-v1"
FP2 = "1" * 64


def _active_document(store: ReconstructionStore, capture_id="cap-1"):
    return store.create_active_document(
        capture_id=capture_id, capture_s1=FP, capture_s1_algorithm_id=FP_ID,
        document_fingerprint=FP, fingerprint_algorithm_id=FP_ID)


def test_create_active_document_roundtrip_with_full_traceability(stack):
    doc = _active_document(stack.recon_store, capture_id="cap-XYZ")
    fetched = stack.recon_store.get_document(doc.document_id)
    assert fetched.document_state is DocumentState.ACTIVE
    assert fetched.integrity_status is DocumentIntegrity.UNVERIFIED
    assert fetched.capture_id == "cap-XYZ"
    assert fetched.capture_s1 == FP and fetched.capture_s1_algorithm_id == FP_ID
    assert fetched.created_at and fetched.integrity_verified_at is None
    assert fetched.page_count is None and fetched.settlement_note is None
    assert fetched.document_fingerprint == FP and fetched.fingerprint_algorithm_id == FP_ID


def test_create_requires_non_empty_binding_fields(stack):
    with pytest.raises(Exception):
        stack.recon_store.create_active_document(
            capture_id="", capture_s1=FP, capture_s1_algorithm_id=FP_ID,
            document_fingerprint=FP, fingerprint_algorithm_id=FP_ID)


def test_persist_pages_sets_page_count_and_is_one_time(stack):
    doc = _active_document(stack.recon_store)
    stack.recon_store.persist_pages(doc.document_id, [(b"p0", FP, FP_ID), (b"p1", FP2, FP_ID)])
    pages = stack.recon_store.get_pages(doc.document_id)
    assert [p.page_index for p in pages] == [0, 1]
    assert pages[0].content == b"p0" and pages[1].content == b"p1"
    assert all(p.byte_len == len(p.content) for p in pages)
    assert stack.recon_store.get_document(doc.document_id).page_count == 2
    with pytest.raises(IllegalFieldWrite):
        stack.recon_store.persist_pages(doc.document_id, [(b"again", FP, FP_ID)])


def test_persist_pages_requires_active_document(stack):
    doc = _active_document(stack.recon_store)
    stack.recon_store.settle_failed(doc.document_id, "pages missing/incomplete")
    with pytest.raises(IllegalTransition):
        stack.recon_store.persist_pages(doc.document_id, [(b"p", FP, FP_ID)])


def test_persist_pages_rejects_missing_fingerprints(stack):
    doc = _active_document(stack.recon_store)
    with pytest.raises(IllegalFieldWrite):
        stack.recon_store.persist_pages(doc.document_id, [(b"p", "", FP_ID)])
    # nothing persisted by the failed txn
    assert stack.recon_store.get_document(doc.document_id).page_count is None


def test_completion_gate_is_fail_closed(stack):
    doc = _active_document(stack.recon_store)
    with pytest.raises(CompletionGateUnmet):          # no pages persisted
        stack.recon_store.complete_document(doc.document_id)
    stack.recon_store.persist_pages(doc.document_id, [(b"p0", FP, FP_ID)])
    with pytest.raises(CompletionGateUnmet):          # first verification not VALID yet
        stack.recon_store.complete_document(doc.document_id)


def test_completion_grants_after_valid_verification_and_pins_state(stack):
    doc = _active_document(stack.recon_store)
    stack.recon_store.persist_pages(doc.document_id, [(b"p0", FP, FP_ID)])
    stack.recon_store.record_verification(doc.document_id, "VALID", "2026-10-01T00:00:00+00:00")
    assert stack.recon_store.complete_document(doc.document_id) == UAC_GRANTED
    done = stack.recon_store.get_document(doc.document_id)
    assert done.document_state is DocumentState.COMPLETED
    assert done.settlement_note is None
    assert done.integrity_status is DocumentIntegrity.VALID


def test_record_verification_is_the_restricted_integrity_writer(stack):
    doc = _active_document(stack.recon_store)
    with pytest.raises(IllegalFieldWrite):            # UNVERIFIED is never a verdict
        stack.recon_store.record_verification(doc.document_id, "UNVERIFIED", "t")
    stack.recon_store.record_verification(doc.document_id, "FAILED", "t1")
    stack.recon_store.record_verification(doc.document_id, "VALID", "t2")  # truthful latest
    rec = stack.recon_store.get_document(doc.document_id)
    assert rec.integrity_status is DocumentIntegrity.VALID and rec.integrity_verified_at == "t2"
    stack.recon_store.settle_failed(doc.document_id, "verify FAILED")
    with pytest.raises(IllegalTransition):            # pinned terminal
        stack.recon_store.record_verification(doc.document_id, "VALID", "t3")


def test_inv_r11_uac_conflict_loser_is_explicit_and_settles(stack):
    cap = "cap-dup"
    first = _active_document(stack.recon_store, capture_id=cap)
    second = _active_document(stack.recon_store, capture_id=cap)
    for doc, fp in ((first, FP), (second, FP2)):
        stack.recon_store.persist_pages(doc.document_id, [(b"p0", fp, FP_ID)])
        stack.recon_store.record_verification(doc.document_id, "VALID", "t")
    assert stack.recon_store.complete_document(first.document_id) == UAC_GRANTED
    assert stack.recon_store.complete_document(second.document_id) == UAC_UNIQUENESS_CONFLICT
    # loser stays explicitly FAILED once settled; winner is the only COMPLETED
    stack.recon_store.settle_failed(second.document_id,
                                    "uniqueness conflict: a COMPLETED document for the same capture_id exists")
    completed, total = stack.recon_store.count_for_capture(cap)
    assert (completed, total) == (1, 2)
    assert stack.recon_store.find_completed_for_capture(cap).document_id == first.document_id
    assert len(stack.recon_store.enumerate_active()) == 0


def test_uac_backstop_survives_direct_storage_race_shape(stack):
    # The partial UNIQUE index fires even if the gate check were bypassed by a racing txn:
    # both rows satisfy every CHECK, so the conflict comes from uq_completed_capture itself.
    import sqlite3
    first = _active_document(stack.recon_store, capture_id="cap-ix")
    stack.recon_store.persist_pages(first.document_id, [(b"p", FP, FP_ID)])
    stack.recon_store.record_verification(first.document_id, "VALID", "t")
    assert stack.recon_store.complete_document(first.document_id) == UAC_GRANTED
    other = _active_document(stack.recon_store, capture_id="cap-ix")
    stack.recon_store.persist_pages(other.document_id, [(b"p", FP2, FP_ID)])
    with pytest.raises(sqlite3.IntegrityError):
        stack.recon_store._conn.execute(
            "UPDATE reconstruction_documents SET document_state = 'COMPLETED' WHERE document_id = ?",
            (other.document_id,))


def test_settlement_requires_note_and_active_only(stack):
    doc = _active_document(stack.recon_store)
    with pytest.raises(IllegalFieldWrite):
        stack.recon_store.settle_failed(doc.document_id, "")
    stack.recon_store.settle_failed(doc.document_id, "pages missing/incomplete")
    settled = stack.recon_store.get_document(doc.document_id)
    assert settled.document_state is DocumentState.FAILED_INCOMPLETE
    assert settled.integrity_status is DocumentIntegrity.FAILED  # pinned at settlement
    with pytest.raises(IllegalTransition):            # terminal states never change
        stack.recon_store.settle_failed(doc.document_id, "again")


def test_unknown_document_operations_are_explicit(stack):
    with pytest.raises(DocumentNotFound):
        stack.recon_store.get_document("nope")
    with pytest.raises(DocumentNotFound):
        stack.recon_store.settle_failed("nope", "x")
    with pytest.raises(DocumentNotFound):
        stack.recon_store.complete_document("nope")
    with pytest.raises(DocumentNotFound):
        stack.recon_store.persist_pages("nope", [])
    assert stack.recon_store.find_completed_for_capture("nope") is None


def test_documents_and_pages_are_durable_across_restart(make_stack):
    s1 = make_stack()
    try:
        cap = ingest_parts(s1.capture, [b"restart-a", b"restart-b"])
        doc = _active_document(s1.recon_store, capture_id=cap)
        s1.recon_store.persist_pages(doc.document_id, [(b"restart-a", FP, FP_ID),
                                                       (b"restart-b", FP2, FP_ID)])
        doc_id = doc.document_id
    finally:
        s1.close()
    s2 = make_stack()                                  # fresh process shape
    try:
        rec = s2.recon_store.get_document(doc_id)
        assert rec.capture_id == cap and rec.page_count == 2
        pages = s2.recon_store.get_pages(doc_id)
        assert [p.content for p in pages] == [b"restart-a", b"restart-b"]
    finally:
        s2.close()


def test_document_creation_failure_is_explicit_no_residue(make_stack, recon_db, capture_db):
    # Genuine storage-failure simulation: a closed connection raises sqlite3.Error inside
    # the creation txn → explicit DocumentCreationFailed, nothing persisted (F2 analog).
    s = make_stack()
    s.recon_store.close()
    from reconstruction import IllegalFieldWrite
    with pytest.raises((DocumentCreationFailed, IllegalFieldWrite)):
        s.recon_store.create_active_document(
            capture_id="cap-boom", capture_s1=FP, capture_s1_algorithm_id=FP_ID,
            document_fingerprint=FP, fingerprint_algorithm_id=FP_ID)
    s.close()
    fresh = ReconstructionStore(recon_db)              # cold-storage truth
    try:
        assert fresh.count_for_capture("cap-boom") == (0, 0)   # no residue
    finally:
        fresh.close()
