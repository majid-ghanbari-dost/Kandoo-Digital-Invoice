"""WP-2.2 evidence end-to-end tests — the full mandated path with evidence, plus the
structural no-content boundary of the evidence surface (AC-2.2.4)."""
import json

from ev_helpers import EvidenceStack, build_completed

from capture import CaptureService, ReadSuccess
from reconstruction import (
    EV_DOCUMENT_COMPLETED,
    EV_VERIFIED_READ,
    DocumentReadSuccess,
    EvidenceReadSuccess,
)
from reconstruction.evidence import _ALLOWED_PAYLOAD_KEYS, _EVENT_VOCABULARY

PARTS = [b"INVOICE #123 total=999;", b"item: widget x2 = 200;", b"footer signature;", b"page-4;"]


def test_full_path_capture_to_verified_evidence_chain_across_restart(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        capture_id, document_id = build_completed(stack, PARTS)
        ok = stack.recon.read_document(document_id)
        assert isinstance(ok, DocumentReadSuccess)
        assert [p.content for p in ok.pages] == PARTS           # ordered, byte-exact

        stack.reopen()                                          # full restart simulation
        ok2 = stack.recon.read_document(document_id)
        assert isinstance(ok2, DocumentReadSuccess)
        assert [p.content for p in ok2.pages] == PARTS

        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadSuccess)
        assert [(e.event_type, e.payload.get("verdict")) for e in read.events] == [
            (EV_DOCUMENT_COMPLETED, None),
            (EV_VERIFIED_READ, "VALID"),
            (EV_VERIFIED_READ, "VALID"),
        ]
        assert [e.seq for e in read.events] == sorted(e.seq for e in read.events)

        artifact_read = stack.capture.read_evidence(capture_id)
        assert isinstance(artifact_read, ReadSuccess)
        artifact = artifact_read.content
        spans = read.events[0].payload["page_spans"]
        assert len(spans) == 4
        for span, part in zip(spans, PARTS):
            assert artifact[span["byte_start"]:span["byte_end"]] == part

        audit = stack.evidence_store.verify_chain()
        assert audit.valid and audit.records == 3
    finally:
        stack.close()


def test_structural_no_content_boundary_in_evidence(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        stack.recon.read_document(document_id)

        rows = stack.evidence_store._conn.execute(
            "SELECT * FROM reconstruction_evidence ORDER BY seq").fetchall()
        assert rows
        for row in rows:
            assert row["event_type"] in _EVENT_VOCABULARY
            allowed = _ALLOWED_PAYLOAD_KEYS[row["event_type"]]
            payload = json.loads(row["payload"])
            assert set(payload.keys()) <= allowed, (row["event_type"], payload.keys())
            # no page content may appear anywhere in any evidence column value
            for column in ("document_id", "capture_id", "event_type", "payload",
                           "created_at", "fingerprint_algorithm_id",
                           "record_fingerprint", "prev_record_hash", "record_hash"):
                value = row[column]
                for fragment in (b"INVOICE", b"widget", b"total=999", b"footer", b"page-4;"):
                    assert fragment not in str(value).encode()
        # the durable pages themselves are the ONLY place content lives (store layer)
        pages = stack.recon_store.get_pages(document_id)
        assert b"INVOICE" in pages[0].content
    finally:
        stack.close()
