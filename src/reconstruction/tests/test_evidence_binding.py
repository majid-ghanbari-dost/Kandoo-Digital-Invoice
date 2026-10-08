"""WP-2.2 evidence binding tests — page → source byte-range fidelity (AC-2.2.2),
verdict/recovery event trails (AC-2.2.6)."""
from ev_helpers import EvidenceStack, build_completed

from capture import CaptureService, ReadSuccess, S1Service
from reconstruction import (
    NOTE_PAGES_INCOMPLETE,
    NOTE_VERIFY_FAILED,
    EV_DOCUMENT_COMPLETED,
    EV_DOCUMENT_SETTLED_FAILED,
    EV_RECOVERY_SETTLED,
    EV_VERIFIED_READ,
    DocumentReadIntegrityFailure,
    DocumentReadSuccess,
    EvidenceReadSuccess,
    ReconstructCompleted,
    ReconstructSettledFailure,
    derive_pages,
    reassemble,
    run_reconstruction_recovery,
)

AGG_PARTS = [b"alpha-part;", b"beta-part!", b"gamma-part?"]


def _artifact_of(stack, capture_id):
    read = stack.capture.read_evidence(capture_id)
    assert isinstance(read, ReadSuccess)
    return read.content


def test_completed_event_page_spans_tile_the_aggregate_artifact(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        capture_id, document_id = build_completed(stack, AGG_PARTS)
        artifact = _artifact_of(stack, capture_id)
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadSuccess)
        event = read.events[0]
        assert event.event_type == EV_DOCUMENT_COMPLETED
        spans = event.payload["page_spans"]
        assert [s["page_index"] for s in spans] == [0, 1, 2]
        assert spans[0]["byte_start"] == 8                       # after the first header
        for earlier, later in zip(spans, spans[1:]):
            assert later["byte_start"] == earlier["byte_end"] + 8  # one header between parts
        assert spans[-1]["byte_end"] == len(artifact)            # total coverage
        for span, part in zip(spans, AGG_PARTS):                 # verbatim slices, in order
            assert artifact[span["byte_start"]:span["byte_end"]] == part
    finally:
        stack.close()


def test_span_slices_equal_durable_page_bytes_and_fingerprints(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        capture_id, document_id = build_completed(stack, AGG_PARTS)
        artifact = _artifact_of(stack, capture_id)
        durable_pages = stack.recon_store.get_pages(document_id)
        event = stack.evidence_store.read_document_evidence(document_id).events[0]
        s1 = S1Service()
        for span, page in zip(event.payload["page_spans"], durable_pages):
            source_slice = artifact[span["byte_start"]:span["byte_end"]]
            assert source_slice == page.content                  # evidence ↔ durable bytes
            assert span["page_fingerprint"] == page.page_fingerprint
            assert s1.compute(source_slice).s1 == page.page_fingerprint
    finally:
        stack.close()


def test_single_page_fallback_span_covers_whole_artifact(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        artifact = b"not-a-framing-artifact!"                    # 8-byte header parse fails → fallback
        ingest = stack.capture.ingest(artifact, source_label="raw")
        outcome = stack.recon.reconstruct(ingest.capture_id)
        assert isinstance(outcome, ReconstructCompleted)
        document_id = outcome.document.document_id
        record = stack.recon_store.get_document(document_id)
        assert record.page_count == 1
        assert record.document_fingerprint != record.capture_s1  # fallback: reassembly adds framing
        event = stack.evidence_store.read_document_evidence(document_id).events[0]
        spans = event.payload["page_spans"]
        assert spans == [{"page_index": 0, "byte_start": 0, "byte_end": len(artifact),
                          "page_fingerprint": stack.recon_store.get_pages(document_id)[0].page_fingerprint}]
        assert artifact[0:len(artifact)] == stack.recon_store.get_pages(document_id)[0].content
    finally:
        stack.close()


def test_verified_read_verdicts_are_recorded_in_order(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, AGG_PARTS)
        ok = stack.recon.read_document(document_id)
        assert isinstance(ok, DocumentReadSuccess)
        stack.recon_store._conn.execute(
            "UPDATE document_pages SET content = ? WHERE document_id = ? AND page_index = 0",
            (b"TAMPERED;", document_id),
        )
        bad = stack.recon.read_document(document_id)
        assert isinstance(bad, DocumentReadIntegrityFailure)
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadSuccess)
        types = [(e.event_type, e.payload.get("verdict"), e.payload.get("reason"))
                 for e in read.events]
        assert types == [
            (EV_DOCUMENT_COMPLETED, None, None),
            (EV_VERIFIED_READ, "VALID", None),
            (EV_VERIFIED_READ, "FAILED", "page content mismatch"),
        ]
        assert read.events[0].seq < read.events[1].seq < read.events[2].seq
    finally:
        stack.close()


def _leave_active_residue(stack, parts):
    """Record-first construction interrupted before completion → ACTIVE leftover."""
    capture_id = None
    content = CaptureService.aggregate(parts)
    ingest = stack.capture.ingest(content, source_label="residue")
    capture_id = ingest.capture_id
    read = stack.capture.read_evidence(capture_id)
    assert isinstance(read, ReadSuccess)
    s1 = S1Service()
    parts_derived = derive_pages(read.content)
    page_fps = [(p, s1.compute(p).s1, s1.compute(p).s1_algorithm_id) for p in parts_derived]
    doc_fp = s1.compute(reassemble(parts_derived))
    record = stack.recon_store.create_active_document(
        capture_id=capture_id, capture_s1=read.s1,
        capture_s1_algorithm_id=read.s1_algorithm_id,
        document_fingerprint=doc_fp.s1, fingerprint_algorithm_id=doc_fp.s1_algorithm_id,
    )
    stack.recon_store.persist_pages(record.document_id, page_fps)
    return capture_id, record.document_id                       # left ACTIVE (no completion)


def test_recovery_settlement_completed_event_carries_spans(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        parts = [b"rec-a;", b"rec-b;"]
        capture_id, document_id = _leave_active_residue(stack, parts)
        artifact = _artifact_of(stack, capture_id)
        stack.reopen()                                          # restart
        report = run_reconstruction_recovery(stack.recon_store, S1Service(),
                                             evidence=stack.evidence_store)
        assert report.complete and report.settled_completed == [document_id]
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadSuccess)
        event = read.events[-1]
        assert event.event_type == EV_RECOVERY_SETTLED
        assert event.payload["final_state"] == "COMPLETED"
        assert event.payload["settlement_note"] is None
        spans = event.payload["page_spans"]
        assert [s["page_index"] for s in spans] == [0, 1]
        for span, part in zip(spans, parts):
            assert artifact[span["byte_start"]:span["byte_end"]] == part
        assert stack.evidence_store.verify_chain().valid
    finally:
        stack.close()


def test_recovery_settlement_failed_event_recorded_without_spans(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        capture_id = None
        content = CaptureService.aggregate([b"never-completed;"])
        ingest = stack.capture.ingest(content, source_label="residue-fail")
        capture_id = ingest.capture_id
        read = stack.capture.read_evidence(capture_id)
        assert isinstance(read, ReadSuccess)
        s1 = S1Service()
        doc_fp = s1.compute(b"unused")
        record = stack.recon_store.create_active_document(
            capture_id=capture_id, capture_s1=read.s1,
            capture_s1_algorithm_id=read.s1_algorithm_id,
            document_fingerprint=doc_fp.s1, fingerprint_algorithm_id=doc_fp.s1_algorithm_id,
        )                                                        # no pages persisted
        stack.reopen()
        report = run_reconstruction_recovery(stack.recon_store, S1Service(),
                                             evidence=stack.evidence_store)
        assert report.complete
        assert report.settled_failed == [(record.document_id, NOTE_PAGES_INCOMPLETE)]
        read_ev = stack.evidence_store.read_document_evidence(record.document_id)
        assert isinstance(read_ev, EvidenceReadSuccess)
        event = read_ev.events[-1]
        assert event.event_type == EV_RECOVERY_SETTLED
        assert event.payload["final_state"] == "FAILED_INCOMPLETE"
        assert event.payload["settlement_note"] == NOTE_PAGES_INCOMPLETE
        assert event.payload["page_spans"] is None               # honest absence — never guessed
    finally:
        stack.close()


def test_settled_failure_outcome_is_evidenced(tmp_path):
    """A deterministic D-1 (injected page-persist failure) settles the document
    FAILED_INCOMPLETE — and the settlement is evidenced (DOCUMENT_SETTLED_FAILED),
    with the subsequent read refusal evidenced as VERIFIED_READ/REFUSED."""
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        capture_id = None
        content = CaptureService.aggregate([b"doomed-persist;"])
        ingest = stack.capture.ingest(content, source_label="doomed")
        capture_id = ingest.capture_id
        # inject a definitive persist failure at the SQL level (corruption-injection pattern)
        stack.recon_store._conn.execute(
            "CREATE TRIGGER fail_pages BEFORE INSERT ON document_pages "
            "BEGIN SELECT RAISE(ABORT, 'injected persist failure'); END")
        outcome = stack.recon.reconstruct(capture_id)
        assert isinstance(outcome, ReconstructSettledFailure), outcome
        assert outcome.document_id is not None
        record = stack.recon_store.get_document(outcome.document_id)
        assert record.document_state.value == "FAILED_INCOMPLETE"
        refused = stack.recon.read_document(outcome.document_id)
        assert type(refused).__name__ == "DocumentReadRefused"
        assert refused.document_state == "FAILED_INCOMPLETE"
        read_ev = stack.evidence_store.read_document_evidence(outcome.document_id)
        assert isinstance(read_ev, EvidenceReadSuccess)
        types = [(e.event_type, e.payload) for e in read_ev.events]
        assert types == [
            (EV_DOCUMENT_SETTLED_FAILED, {"settlement_note": "page persist failed"}),
            (EV_VERIFIED_READ, {"verdict": "REFUSED", "state": "FAILED_INCOMPLETE"}),
        ]
        assert stack.evidence_store.verify_chain().valid
    finally:
        stack.close()
