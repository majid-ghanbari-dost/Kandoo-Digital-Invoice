"""WP-3.2 core — binding creation, INV-B-1:1 replay, per-field traceability walk,
document-scoped enumeration, and the bind-path explicit-outcome matrix (AC-3.2.1/3.2.2)."""
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from reconstruction import (
    EV_DOCUMENT_COMPLETED,
    EvidenceReadSuccess,
)
from extraction import (
    BindingAlreadyExists,
    BindingCompleted,
    BindingLink,
    BindingReadRefused,
    BindingSourceIntegrityFailure,
    BindingSourceRefused,
)


def _bind_one(binding_stack, parts=None):
    extraction_id = binding_stack.build_and_extract(parts)
    outcome = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(outcome, BindingCompleted), outcome
    return extraction_id, outcome


def test_bind_creates_durable_binding_with_full_chain(binding_stack):
    extraction_id, done = _bind_one(binding_stack)
    b = done.binding
    er = binding_stack.extraction.read_extraction(extraction_id)
    assert isinstance(er.extraction, object)
    rec = er.extraction
    # extraction anchor — copied verbatim from the verified extraction read
    assert b.extraction_id == extraction_id
    assert b.extraction_record_fingerprint == rec.record_fingerprint
    assert b.extraction_fingerprint_algorithm_id == rec.fingerprint_algorithm_id
    # document/capture anchor
    assert (b.document_id, b.capture_id, b.capture_s1) == (
        rec.document_id, rec.capture_id, rec.capture_s1)
    assert b.capture_s1_algorithm_id == rec.capture_s1_algorithm_id
    # reconstruction evidence anchor — the DOCUMENT_COMPLETED record, verified
    ev = binding_stack.evidence_store.read_document_evidence(b.document_id)
    assert isinstance(ev, EvidenceReadSuccess)
    completed = [e for e in ev.events if e.event_type == EV_DOCUMENT_COMPLETED]
    assert len(completed) == 1
    assert b.recon_evidence_seq == completed[0].seq
    assert b.recon_evidence_record_hash == completed[0].record_hash
    # per-field entries tile the extraction field set exactly
    assert b.field_binding_count == len(done.entries) == rec.field_count == 6
    assert [e.field_seq for e in done.entries] == list(range(6))
    fields = er.fields
    for entry, field in zip(done.entries, fields):
        assert entry.field_name == field.field_name
        assert entry.page_index == field.span.page_index
        assert entry.byte_start == field.span.byte_start
        assert entry.byte_end == field.span.byte_end
        assert entry.page_fingerprint == field.span.page_fingerprint
    # tamper-evident binding itself
    assert len(b.binding_fingerprint) == 64 and len(b.binding_hash) == 64
    assert b.prev_binding_hash == "0" * 64          # first binding = genesis
    assert b.binding_fingerprint_algorithm_id == "sha256-v1"


def test_binding_replay_is_explicit_idempotent(binding_stack):
    extraction_id, done = _bind_one(binding_stack)
    replay = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(replay, BindingAlreadyExists), replay
    assert replay.binding_id == done.binding.binding_id
    assert replay.extraction_id == extraction_id
    # no second binding row exists
    assert len(binding_stack.binding_store.find_for_document(
        done.binding.document_id)) == 1
    # and the binding still reads back successfully
    read = binding_stack.binder.read_binding(extraction_id)
    assert type(read).__name__ == "BindingReadSuccess"
    assert read.binding.binding_id == done.binding.binding_id


def test_per_field_traceability_walk_field_to_capture(binding_stack):
    """The crown jewel (AC-3.2.2): every entry resolves the FULL machine-checkable walk
    field → page span + page fingerprint → page bytes → artifact span (WP-2.2 evidence)
    → capture S1."""
    parts = [b"invoice.number=INV-2024-001\ninvoice.date=2026-10-01\n",
             b"seller.name=Acme GmbH\ntotal.gross=129.90\ncurrency.label=EUR\n"]
    extraction_id, done = _bind_one(binding_stack, parts)
    b = done.binding
    er = binding_stack.extraction.read_extraction(extraction_id)
    fields = {f.field_seq: f for f in er.fields}
    durable_pages = {p.page_index: p for p in
                     binding_stack.recon_store.get_pages(b.document_id)}
    ev = binding_stack.evidence_store.read_document_evidence(b.document_id)
    completed = [e for e in ev.events if e.event_type == EV_DOCUMENT_COMPLETED][0]
    ev_spans = {s["page_index"]: s for s in completed.payload["page_spans"]}

    for entry in done.entries:
        field = fields[entry.field_seq]
        page = durable_pages[entry.page_index]
        # field → page: fingerprint join + span slice decodes to the verbatim value
        assert entry.page_fingerprint == page.page_fingerprint == field.span.page_fingerprint
        value = bytes(page.content)[entry.byte_start:entry.byte_end].decode(
            field.value_encoding)
        assert value == field.value_verbatim
        # page → artifact: the WP-2.2 evidence span carries the SAME page fingerprint
        # and the artifact byte range slices back to exactly this page's bytes
        ev_span = ev_spans[entry.page_index]
        assert ev_span["page_fingerprint"] == entry.page_fingerprint
        cap_record = binding_stack.capture_store.get_record(b.capture_id)
        artifact = binding_stack.capture_store.get_content(cap_record.artifact_ref)
        assert bytes(artifact)[ev_span["byte_start"]:ev_span["byte_end"]] \
            == bytes(page.content)
    # capture anchor closes the walk
    assert b.capture_s1 == completed.payload["capture_s1"]
    # one concrete known value proves the walk is real, not vacuous
    seq0 = done.entries[0]
    assert fields[seq0.field_seq].value_verbatim == "INV-2024-001"


def test_bindings_for_document_enumeration(binding_stack):
    doc_a = binding_stack.build_document(label="doc-a")
    doc_b = binding_stack.build_document(
        [b"other.number=B-2026-002\n", b"seller.name=Beta AG\n"], label="doc-b")
    # two engines → two extraction records for doc A (INV-X-1:1 is per-triple)
    from extraction import ExtractionCompleted, ReferenceDelimitedEngine
    ea = binding_stack.extraction.extract(doc_a, "reference-delimited-v1")
    assert isinstance(ea, ExtractionCompleted)
    ida1 = ea.extraction.extraction_id
    binding_stack.extraction._engines["alt-delimited-v1"] = \
        ReferenceDelimitedEngine(engine_id="alt-delimited-v1")
    ea2 = binding_stack.extraction.extract(doc_a, "alt-delimited-v1")
    assert isinstance(ea2, ExtractionCompleted)
    ida2 = ea2.extraction.extraction_id
    eb = binding_stack.extraction.extract(doc_b, "reference-delimited-v1")
    assert isinstance(eb, ExtractionCompleted)
    idb = eb.extraction.extraction_id

    # before binding: enumeration lists nothing (no fabrication)
    assert binding_stack.binder.bindings_for_document(doc_a) == ()
    r1 = binding_stack.binder.bind_extraction(ida2)
    r2 = binding_stack.binder.bind_extraction(ida1)
    r3 = binding_stack.binder.bind_extraction(idb)
    assert all(isinstance(x, BindingCompleted) for x in (r1, r2, r3))

    refs_a = binding_stack.binder.bindings_for_document(doc_a)
    assert [(r.extraction_id, r.binding_id) for r in refs_a] == [
        (ida1, r2.binding.binding_id), (ida2, r1.binding.binding_id)]  # extraction order
    refs_b = binding_stack.binder.bindings_for_document(doc_b)
    assert len(refs_b) == 1 and refs_b[0].extraction_id == idb
    assert binding_stack.binder.bindings_for_document("no-such-document") == ()


def test_bind_refused_for_unknown_extraction(binding_stack):
    outcome = binding_stack.binder.bind_extraction("no-such-extraction")
    assert isinstance(outcome, BindingSourceRefused), outcome
    assert outcome.link == BindingLink.EXTRACTION
    # nothing was persisted
    report = binding_stack.binder.verify_chain()
    assert report.valid and report.records == 0


def test_bind_fails_closed_when_extraction_tampered(binding_stack):
    extraction_id = binding_stack.build_and_extract()
    binding_stack.extraction_store._conn.execute(
        "UPDATE extraction_fields SET value_verbatim = 'TAMPERED' "
        "WHERE extraction_id = ? AND field_seq = 0", (extraction_id,))
    outcome = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(outcome, BindingSourceIntegrityFailure), outcome
    assert outcome.link == BindingLink.EXTRACTION
    report = binding_stack.binder.verify_chain()
    assert report.valid and report.records == 0     # nothing bound, zero residue


def test_bind_fails_closed_when_document_tampered(binding_stack):
    extraction_id = binding_stack.build_and_extract()
    document_id = binding_stack.extraction.read_extraction(
        extraction_id).extraction.document_id
    binding_stack.recon_store._conn.execute(
        "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = 0",
        (b"invoice.number=TAMPERED\ninvoice.date=2026-10-01\n", document_id))
    outcome = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(outcome, BindingSourceIntegrityFailure), outcome
    assert outcome.link == BindingLink.DOCUMENT
    report = binding_stack.binder.verify_chain()
    assert report.valid and report.records == 0


def test_bind_refused_without_reconstruction_evidence(make_binding_stack):
    """A stack whose reconstruction service has no evidence store wired: extraction
    works, but the evidence anchor is unobtainable → explicit refusal (no fabrication)."""
    stack = make_binding_stack(with_evidence=False)
    try:
        extraction_id = stack.build_and_extract()
        outcome = stack.binder.bind_extraction(extraction_id)
        assert isinstance(outcome, BindingSourceRefused), outcome
        assert outcome.link == BindingLink.EVIDENCE
        assert stack.binder.verify_chain().records == 0
        # reading a binding that does not exist stays refused
        assert isinstance(stack.binder.read_binding(extraction_id), BindingReadRefused)
    finally:
        stack.close()


def test_read_binding_refused_when_unbound(binding_stack):
    extraction_id = binding_stack.build_and_extract()   # extracted but NOT bound
    assert isinstance(binding_stack.binder.read_binding(extraction_id),
                      BindingReadRefused)
    assert isinstance(binding_stack.binder.read_binding("ghost"), BindingReadRefused)


def test_bind_fails_closed_on_coherent_page_forgery(binding_stack):
    """The strongest forgery: page content mutated AND all fingerprints recomputed
    coherently so the verified document read returns VALID — the span-fidelity gate
    still refuses the bind (the extraction's anchored spans no longer decode)."""
    from reconstruction import reassemble
    from capture import S1Service
    extraction_id = binding_stack.build_and_extract(
        [b"invoice.number=INV-2024-001\ninvoice.date=2026-10-01\n",
         b"seller.name=Acme GmbH\ntotal.gross=129.90\n"])
    document_id = binding_stack.extraction.read_extraction(
        extraction_id).extraction.document_id
    s1 = S1Service()
    forged = b"invoice.number=EVIL-9999999\ninvoice.date=2026-10-01\n"
    fp = s1.compute(forged).s1
    binding_stack.recon_store._conn.execute(
        "UPDATE document_pages SET content = ?, byte_len = ?, page_fingerprint = ? "
        "WHERE document_id = ? AND page_index = 0",
        (forged, len(forged), fp, document_id))
    pages = binding_stack.recon_store.get_pages(document_id)
    canonical = reassemble(p.content for p in pages)
    doc_fp = s1.compute(canonical).s1
    binding_stack.recon_store._conn.execute(
        "UPDATE reconstruction_documents SET document_fingerprint = ? "
        "WHERE document_id = ?", (doc_fp, document_id))
    # the forged document now verifies — and the binder STILL refuses (span gate)
    from reconstruction import DocumentReadSuccess
    assert isinstance(binding_stack.recon.read_document(document_id), DocumentReadSuccess)
    outcome = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(outcome, BindingSourceIntegrityFailure), outcome
    assert outcome.link == BindingLink.SPAN
    assert binding_stack.binder.verify_chain().records == 0

