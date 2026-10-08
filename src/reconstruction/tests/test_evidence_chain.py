"""WP-2.2 evidence chain tests — tamper evidence (AC-2.2.3), concurrency, and the
non-intrusive recorder guarantee (AC-2.2.5)."""
import threading

from ev_helpers import EvidenceStack, build_completed

from capture import CaptureService, S1Service
from reconstruction import (
    EV_VERIFIED_READ,
    ChainVerificationReport,
    EvidenceReadIntegrityFailure,
    EvidenceReadSuccess,
    EvidenceStore,
    ReconstructAlreadyExists,
    ReconstructCompleted,
    DocumentReadSuccess,
    run_reconstruction_recovery,
)

PARTS = [b"chain-a;", b"chain-b;"]


def test_genesis_and_chain_links_are_correct(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        stack.recon.read_document(document_id)
        rows = stack.evidence_store._conn.execute(
            "SELECT seq, prev_record_hash, record_hash FROM reconstruction_evidence ORDER BY seq"
        ).fetchall()
        assert rows[0]["prev_record_hash"] == "0" * 64          # genesis
        for earlier, later in zip(rows, rows[1:]):
            assert later["prev_record_hash"] == earlier["record_hash"]
        head = stack.evidence_store._conn.execute(
            "SELECT last_seq, last_hash FROM evidence_head WHERE id = 1").fetchone()
        assert head["last_seq"] == rows[-1]["seq"]
        assert head["last_hash"] == rows[-1]["record_hash"]
    finally:
        stack.close()


def test_record_field_tamper_is_detected_explicitly(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        stack.evidence_store._conn.execute(
            "UPDATE reconstruction_evidence SET payload = payload || ? WHERE seq = 1",
            ('","injected":"x"',),
        )
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadIntegrityFailure)
        assert read.failure_seq == 1 and "fingerprint mismatch" in read.reason
        audit = stack.evidence_store.verify_chain()
        assert not audit.valid and audit.failure_seq == 1
    finally:
        stack.close()


def test_row_deletion_truncation_is_detected_explicitly(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        stack.recon.read_document(document_id)                  # 2 events exist
        stack.evidence_store._conn.execute("DELETE FROM reconstruction_evidence WHERE seq = 2")
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadIntegrityFailure)
        assert "truncated" in read.reason
        audit = stack.evidence_store.verify_chain()
        assert not audit.valid and "truncated" in audit.reason
    finally:
        stack.close()


def test_head_anchor_deletion_is_detected_explicitly(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        stack.evidence_store._conn.execute("DELETE FROM evidence_head")
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadIntegrityFailure)
        assert "head anchor missing" in read.reason
        assert not stack.evidence_store.verify_chain().valid
    finally:
        stack.close()


def test_forged_row_insertion_is_detected_explicitly(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        # forge an extra tail record whose fields cannot carry a valid fingerprint
        stack.evidence_store._conn.execute(
            """INSERT INTO reconstruction_evidence (
                   document_id, capture_id, event_type, payload, created_at,
                   fingerprint_algorithm_id, record_fingerprint, prev_record_hash, record_hash)
               SELECT document_id, capture_id, event_type, payload, created_at,
                      fingerprint_algorithm_id, record_fingerprint, record_hash,
                      substr(record_hash, 2) || '0'
               FROM reconstruction_evidence WHERE seq = 1""")
        audit = stack.evidence_store.verify_chain()
        assert not audit.valid
        read = stack.evidence_store.read_document_evidence(document_id)
        assert isinstance(read, EvidenceReadIntegrityFailure)
    finally:
        stack.close()


def test_concurrent_appends_produce_exact_contiguous_chain(tmp_path):
    db = tmp_path / "e.db"
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", db)
    try:
        _, document_id = build_completed(stack, PARTS)
    finally:
        stack.close()

    errors = []

    def _worker(n):
        try:
            store = EvidenceStore(db, S1Service())
            try:
                for i in range(3):
                    outcome = store.append(document_id, "cap-x", EV_VERIFIED_READ,
                                           {"verdict": "VALID"})
                    assert not hasattr(outcome, "detail"), outcome   # no EvidenceUnavailable
            finally:
                store.close()
        except Exception as exc:                        # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors

    store = EvidenceStore(db, S1Service())
    try:
        audit = store.verify_chain()
        assert audit.valid, audit.reason
        assert audit.records == 1 + 24                  # 1 build event + 8×3 appends
        assert audit.last_seq == audit.records
        rows = store._conn.execute(
            "SELECT seq FROM reconstruction_evidence ORDER BY seq").fetchall()
        assert [r["seq"] for r in rows] == list(range(1, audit.records + 1))
    finally:
        store.close()


def test_evidence_failure_never_alters_reconstruction_outcomes(tmp_path):
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        build_completed(stack, PARTS)                           # healthy evidence so far
        stack.evidence_store.close()                            # break the evidence layer
        content = CaptureService.aggregate([b"still-built;"])
        ingest = stack.capture.ingest(content, source_label="after-break")
        outcome = stack.recon.reconstruct(ingest.capture_id)
        assert isinstance(outcome, ReconstructCompleted)        # outcome unchanged (AC-2.2.5)
        read = stack.recon.read_document(outcome.document.document_id)
        assert isinstance(read, DocumentReadSuccess)            # verified read unaffected
        again = stack.recon.reconstruct(ingest.capture_id)
        assert isinstance(again, ReconstructAlreadyExists)
        issues = stack.recon.issue_reports()
        assert issues and all("evidence" in i for i in issues)  # surfaced, never silent

        # leave an ACTIVE residue so recovery ATTEMPTS an evidence write while broken
        from capture import ReadSuccess
        ingest2 = stack.capture.ingest(CaptureService.aggregate([b"residue;"]),
                                       source_label="residue")
        src = stack.capture.read_evidence(ingest2.capture_id)
        assert isinstance(src, ReadSuccess)
        fp = S1Service().compute(b"pending")
        residue = stack.recon_store.create_active_document(
            capture_id=ingest2.capture_id, capture_s1=src.s1,
            capture_s1_algorithm_id=src.s1_algorithm_id,
            document_fingerprint=fp.s1, fingerprint_algorithm_id=fp.s1_algorithm_id,
        )                                                        # no pages → settles FAILED
        report = run_reconstruction_recovery(stack.recon_store, S1Service(),
                                             evidence=stack.evidence_store)
        assert report.complete and report.remaining_active == 0  # recovery completeness intact
        assert report.settled_failed == [(residue.document_id, "pages missing/incomplete")]
        assert report.issues                                     # evidence failure surfaced
    finally:
        stack.recon_store.close()
        stack.capture_store.close()


def test_verify_chain_whole_log_audit_states(tmp_path):
    store = EvidenceStore(tmp_path / "e.db", S1Service())
    try:
        empty = store.verify_chain()
        assert isinstance(empty, ChainVerificationReport)
        assert empty.valid and empty.records == 0 and empty.last_seq is None
    finally:
        store.close()
    stack = EvidenceStack(tmp_path / "c.db", tmp_path / "r.db", tmp_path / "e.db")
    try:
        _, document_id = build_completed(stack, PARTS)
        audit = stack.evidence_store.verify_chain()
        assert audit.valid and audit.records == 1 and audit.last_seq == 1
    finally:
        stack.close()
