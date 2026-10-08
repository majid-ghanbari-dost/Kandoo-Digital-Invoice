"""WP-2.2 evidence store tests — durability, linkage, vocabulary, canonical payloads,
append-only shape (AC-2.2.1 structural, AC-2.2.4 structural, AC-2.2.6 vocabulary)."""
import json
import sqlite3
from pathlib import Path

import pytest

from ev_helpers import EvidenceStack, build_completed

from capture import S1Service
from reconstruction import (
    DERIVATION_ID,
    EV_DOCUMENT_COMPLETED,
    EV_VERIFIED_READ,
    EvidenceIllegalEvent,
    EvidenceReadRefused,
    EvidenceReadSuccess,
    EvidenceStore,
    GENESIS_HASH,
)

PARTS = [b"alpha-part;", b"beta-part!", b"gamma-part?"]


def test_document_completed_event_binds_document_and_capture(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        capture_id, document_id = build_completed(stack, PARTS)
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadSuccess)
        assert len(read.events) == 1
        event = read.events[0]
        assert event.event_type == EV_DOCUMENT_COMPLETED
        assert event.document_id == document_id
        assert event.capture_id == capture_id
        record = stack.recon_store.get_document(document_id)
        assert event.payload["capture_s1"] == record.capture_s1
        assert event.payload["page_count"] == record.page_count == 3
        assert event.payload["document_fingerprint"] == record.document_fingerprint
        assert event.payload["fingerprint_algorithm_id"] == record.fingerprint_algorithm_id
        assert event.payload["derivation_id"] == DERIVATION_ID
    finally:
        stack.close()


def test_events_are_durable_across_restart(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        before = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(before, EvidenceReadSuccess)
        stack.reopen()                                   # full process-restart simulation
        after = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(after, EvidenceReadSuccess)
        assert [(e.seq, e.event_type, e.created_at, e.record_hash) for e in after.events] \
            == [(e.seq, e.event_type, e.created_at, e.record_hash) for e in before.events]
        audit = stack.evidence_store.verify_chain()
        assert audit.valid and audit.records == 1
    finally:
        stack.close()


def test_unknown_document_evidence_read_is_refused(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        build_completed(stack, PARTS)
        refused = stack.evidence_store.read_document_evidence("no-such-document")
        assert isinstance(refused, EvidenceReadRefused)
        assert refused.document_id == "no-such-document"
    finally:
        stack.close()


def test_event_vocabulary_and_payload_keys_are_enforced(tmp_path):
    store = EvidenceStore(tmp_path / "e.db", S1Service())
    try:
        with pytest.raises(EvidenceIllegalEvent):
            store.append("doc", "cap", "NOT_AN_EVENT_TYPE", {})
        with pytest.raises(EvidenceIllegalEvent):
            store.append("doc", "cap", EV_VERIFIED_READ,
                         {"verdict": "VALID", "content": b"smuggled"})
    finally:
        store.close()


def test_payload_is_stored_as_canonical_json_text(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadSuccess)
        row = stack.evidence_store._conn.execute(
            "SELECT payload FROM reconstruction_evidence WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        canonical = json.dumps(read.events[0].payload, sort_keys=True,
                               separators=(",", ":"))
        assert row["payload"] == canonical              # stored text IS the canonical form
        assert json.loads(row["payload"]) == read.events[0].payload
    finally:
        stack.close()


def test_every_record_carries_algorithm_id_and_chain_fields(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        stack.recon.read_document(document_id)
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadSuccess)
        rows = stack.evidence_store._conn.execute(
            "SELECT * FROM reconstruction_evidence ORDER BY seq").fetchall()
        assert [r["seq"] for r in rows] == [1, 2]
        assert rows[0]["prev_record_hash"] == GENESIS_HASH
        assert rows[1]["prev_record_hash"] == rows[0]["record_hash"]
        for row, event in zip(rows, read.events):
            assert row["fingerprint_algorithm_id"] == "sha256-v1"
            assert event.fingerprint_algorithm_id == "sha256-v1"
            assert len(event.record_fingerprint) == 64 and event.record_fingerprint == event.record_fingerprint.lower()
            assert len(event.record_hash) == 64 and event.record_hash == event.record_hash.lower()
    finally:
        stack.close()


def test_append_only_no_update_or_delete_paths_exist():
    """Structural proof: the evidence module contains no UPDATE/DELETE against the
    evidence log — the append-only property is a code-level fact, not a convention."""
    source = Path(__file__).resolve().parent.parent / "evidence.py"
    text = source.read_text(encoding="utf-8")
    assert "UPDATE reconstruction_evidence" not in text
    assert "DELETE FROM reconstruction_evidence" not in text
    assert "DELETE FROM evidence_head" not in text


def test_document_scoped_read_returns_only_that_documents_events(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, doc1 = build_completed(stack, [b"one;"], label="doc1")
        _, doc2 = build_completed(stack, [b"two;", b"more;"], label="doc2")
        read1 = stack.evidence_store.read_document_evidence(doc1)
        read2 = stack.evidence_store.read_document_evidence(doc2)
        assert isinstance(read1, EvidenceReadSuccess) and isinstance(read2, EvidenceReadSuccess)
        assert [e.event_type for e in read1.events] == [EV_DOCUMENT_COMPLETED]
        assert all(e.document_id == doc1 for e in read1.events)
        assert [e.event_type for e in read2.events] == [EV_DOCUMENT_COMPLETED]
        assert all(e.document_id == doc2 for e in read2.events)
        assert read2.events[0].seq == read1.events[0].seq + 1   # global append order kept
    finally:
        stack.close()
