"""WP-3.2 read path — VOR verified binding read, tamper matrix with coarse link
attribution, content-free failures, and the NO_VERDICT path (AC-3.2.3)."""
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extraction import (
    BindingCompleted,
    BindingLink,
    BindingReadIntegrityFailure,
    BindingReadRefused,
    BindingReadSuccess,
    BindingReadVerificationUnavailable,
)
import pytest


def _bind(binding_stack, parts=None):
    extraction_id = binding_stack.build_and_extract(parts)
    outcome = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(outcome, BindingCompleted), outcome
    return extraction_id, outcome


def test_read_success_delivers_binding_and_entries(binding_stack):
    extraction_id, done = _bind(binding_stack)
    read = binding_stack.binder.read_binding(extraction_id)
    assert isinstance(read, BindingReadSuccess), read
    assert read.binding.binding_id == done.binding.binding_id
    assert read.entries == done.entries
    assert read.verified_at                    # same-read verdict timestamp


def test_read_refused_for_unknown_or_unbound(binding_stack):
    assert isinstance(binding_stack.binder.read_binding("ghost"), BindingReadRefused)
    extraction_id = binding_stack.build_and_extract()      # unbound
    assert isinstance(binding_stack.binder.read_binding(extraction_id),
                      BindingReadRefused)


def _assert_integrity_failure(outcome, link):
    assert isinstance(outcome, BindingReadIntegrityFailure), outcome
    assert outcome.link == link
    # content-free failure: neither the binding nor its entries are ever delivered
    assert not hasattr(outcome, "binding")
    assert not hasattr(outcome, "entries")
    assert outcome.reason


def test_tamper_binding_entry_offset_read_fails_link_binding(binding_stack):
    extraction_id, _ = _bind(binding_stack)
    binding_stack.binding_store._conn.execute(
        "UPDATE extraction_binding_fields SET byte_start = byte_start + 1 "
        "WHERE field_seq = 2")
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.BINDING)


def test_tamper_binding_scalar_read_fails_link_binding(binding_stack):
    extraction_id, _ = _bind(binding_stack)
    binding_stack.binding_store._conn.execute(
        "UPDATE extraction_bindings SET capture_s1 = "
        "'0000000000000000000000000000000000000000000000000000000000000000'")
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.BINDING)


def test_tamper_binding_field_name_read_fails_link_binding(binding_stack):
    extraction_id, _ = _bind(binding_stack)
    binding_stack.binding_store._conn.execute(
        "UPDATE extraction_binding_fields SET field_name = 'hijacked' "
        "WHERE field_seq = 0")
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.BINDING)


def test_delete_binding_tail_row_read_fails_link_binding(binding_stack):
    """Truncation attack: the head anchor makes a deleted tail explicit."""
    extraction_id, done = _bind(binding_stack)
    binding_stack.binding_store._conn.execute(
        "DELETE FROM extraction_binding_fields WHERE binding_id = ?",
        (done.binding.binding_id,))
    binding_stack.binding_store._conn.execute(
        "DELETE FROM extraction_bindings WHERE binding_id = ?",
        (done.binding.binding_id,))
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.BINDING)


def test_tamper_extraction_value_read_fails_link_extraction(binding_stack):
    extraction_id, _ = _bind(binding_stack)
    binding_stack.extraction_store._conn.execute(
        "UPDATE extraction_fields SET value_verbatim = 'TAMPERED' "
        "WHERE extraction_id = ? AND field_seq = 1", (extraction_id,))
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.EXTRACTION)


def test_delete_extraction_record_read_fails_link_extraction(binding_stack):
    """A bound extraction that later VANISHES is an integrity failure of the binding —
    the binding's purpose is exactly to make such deletions provable."""
    extraction_id, done = _bind(binding_stack)
    binding_stack.extraction_store._conn.execute(
        "DELETE FROM extraction_fields WHERE extraction_id = ?", (extraction_id,))
    binding_stack.extraction_store._conn.execute(
        "DELETE FROM extraction_records WHERE extraction_id = ?", (extraction_id,))
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.EXTRACTION)


def test_tamper_reconstruction_evidence_read_fails_link_evidence(binding_stack):
    extraction_id, _ = _bind(binding_stack)
    binding_stack.evidence_store._conn.execute(
        "UPDATE reconstruction_evidence SET payload = '{\"forged\":true}' "
        "WHERE event_type = 'DOCUMENT_COMPLETED'")
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.EVIDENCE)


def test_coherent_page_forgery_read_fails_link_span(binding_stack):
    """Fingerprints recomputed coherently (verified read VALID) — the span gate still
    catches the forgery because the anchored spans no longer decode to the values."""
    from reconstruction import DocumentReadSuccess, reassemble
    from capture import S1Service
    extraction_id, _ = _bind(binding_stack, [b"invoice.number=INV-2024-001\n"])
    b = binding_stack.binder.read_binding(extraction_id).binding
    s1 = S1Service()
    forged = b"invoice.number=EVIL-000001\n"
    fp = s1.compute(forged).s1
    binding_stack.recon_store._conn.execute(
        "UPDATE document_pages SET content = ?, byte_len = ?, page_fingerprint = ? "
        "WHERE document_id = ? AND page_index = 0",
        (forged, len(forged), fp, b.document_id))
    pages = binding_stack.recon_store.get_pages(b.document_id)
    binding_stack.recon_store._conn.execute(
        "UPDATE reconstruction_documents SET document_fingerprint = ? "
        "WHERE document_id = ?", (s1.compute(reassemble(p.content for p in pages)).s1,
                                  b.document_id))
    assert isinstance(binding_stack.recon.read_document(b.document_id),
                      DocumentReadSuccess)          # forgery passes the frozen layer...
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.SPAN)     # ...and NOT the binding


def test_delete_document_pages_store_defect_read_unavailable(binding_stack):
    """A vanished page SET is a store defect (no verdict computable) — mapped to the
    explicit VerificationUnavailable outcome, never guessed around."""
    extraction_id, done = _bind(binding_stack)
    binding_stack.recon_store._conn.execute(
        "DELETE FROM document_pages WHERE document_id = ?", (done.binding.document_id,))
    outcome = binding_stack.binder.read_binding(extraction_id)
    assert isinstance(outcome, BindingReadVerificationUnavailable), outcome


def test_tamper_document_page_content_read_fails_link_document(binding_stack):
    """Page bytes mutated in place (fingerprints stale) — the frozen verified read
    returns FAILED and the binding read fails at the document link."""
    extraction_id, done = _bind(binding_stack)
    binding_stack.recon_store._conn.execute(
        "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = 0",
        (b"invoice.number=TAMPERED-00\n", done.binding.document_id))
    _assert_integrity_failure(binding_stack.binder.read_binding(extraction_id),
                              BindingLink.DOCUMENT)


def test_evidence_anchor_drift_read_fails_link_evidence(binding_stack, tmp_path):
    """A DIFFERENT evidence log (anchor seq/hash unknown there) fails the evidence link —
    the binding is log-position-specific, never portable across logs."""
    from reconstruction import EvidenceStore
    from capture import S1Service
    from extraction import ExtractionEvidenceBinder
    extraction_id, _ = _bind(binding_stack)
    other = EvidenceStore(tmp_path / "other-evidence.db", S1Service())
    try:
        drift_binder = ExtractionEvidenceBinder(
            binding_stack.binding_store, binding_stack.extraction,
            binding_stack.recon, other, S1Service())
        outcome = drift_binder.read_binding(extraction_id)
        assert isinstance(outcome, BindingReadIntegrityFailure), outcome
        assert outcome.link == BindingLink.EVIDENCE
    finally:
        other.close()


def test_unverifiable_fingerprint_algorithm_read_unavailable(make_binding_stack):
    """A binding log anchored under a different S1 algorithm instantiation ('md5-v1')
    cannot be verified by this sha256 binder — NO_VERDICT, Issue-Report surfaced,
    nothing delivered (the stored content-free discipline holds)."""
    from capture import S1Service
    from extraction import ExtractionBindingStore, ExtractionEvidenceBinder
    stack = make_binding_stack()
    try:
        md5_store = ExtractionBindingStore(stack.binding_db,
                                           S1Service(algorithm_id="md5-v1"))
        stack.binding_store.close()
        stack.binding_store = md5_store
        stack.binder = ExtractionEvidenceBinder(
            md5_store, stack.extraction, stack.recon, stack.evidence_store,
            S1Service())                     # sha256 binder over an md5-anchored log
        extraction_id = stack.build_and_extract()
        outcome = stack.binder.bind_extraction(extraction_id)
        assert type(outcome).__name__ == "BindingCompleted", outcome
        read = stack.binder.read_binding(extraction_id)
        # the md5 store's own chain is self-consistent, but the binder's verify() yields
        # NO_VERDICT for the unknown 'md5-v1' algorithm id
        assert isinstance(read, BindingReadVerificationUnavailable), read
        assert "md5-v1" in read.issue_report
        assert stack.binder.issue_reports()      # Issue-Report surfaced
    finally:
        stack.close()


def test_replay_still_explicit_after_reads(binding_stack):
    extraction_id, done = _bind(binding_stack)
    assert isinstance(binding_stack.binder.read_binding(extraction_id), BindingReadSuccess)
    from extraction import BindingAlreadyExists
    replay = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(replay, BindingAlreadyExists)
    assert replay.binding_id == done.binding.binding_id
