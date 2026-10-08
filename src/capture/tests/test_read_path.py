"""Verify-on-Read tests — VOR §3–§9 (AC-T114-1..6; INV-V1..V8)."""
import pytest

from capture import (
    READ_REASON_MISMATCH,
    READ_REASON_UNREADABLE,
    CaptureService,
    CaptureState,
    IntegrityStatus,
    ReadIntegrityFailure,
    ReadRefused,
    ReadSuccess,
    ReadVerificationUnavailable,
    S1Service,
)


def _make_completed(service, content=b"evidence-bytes", source_label="ch"):
    outcome = service.ingest(content, source_label=source_label)
    from capture import IngestCompleted
    assert isinstance(outcome, IngestCompleted)
    return outcome.capture_id


def test_healthy_read_delivers_content_with_fresh_verdict(service):
    """AC-T114-2 / INV-V1: intact content + VALID computed in that read; F-08 refreshed."""
    cid = _make_completed(service, b"healthy-content")
    first = service.read_evidence(cid)
    assert isinstance(first, ReadSuccess)
    assert first.content == b"healthy-content"               # byte-exact (§4 r3)
    assert first.verdict == "VALID"
    assert first.s1_algorithm_id == "sha256-v1"
    assert first.integrity_verified_at == service._store.get_record(cid).integrity_verified_at

    second = service.read_evidence(cid)
    assert isinstance(second, ReadSuccess)
    assert second.integrity_verified_at >= first.integrity_verified_at   # F-08 rewritten per read


def test_corruption_injection_fails_explicitly_never_delivers(service):
    """AC-T114-1 / INV-V2/V3 / INV-C4: post-COMPLETED byte flip → explicit FAILED outcome,
    no content, record integrity FAILED with fresh verified_at, still COMPLETED."""
    content = b"tamper-target-content"
    cid = _make_completed(service, content)
    # out-of-store mutation (the store itself has no rewrite path — Store I-1)
    service._store._conn.execute(
        "UPDATE artifact_content SET content = ?", (b"tamper-TARGET-content",))

    read = service.read_evidence(cid)
    assert isinstance(read, ReadIntegrityFailure)
    assert read.reason == READ_REASON_MISMATCH
    assert not hasattr(read, "content") or read.__dataclass_fields__.get("content") is None
    rec = service._store.get_record(cid)
    assert rec.integrity_status is IntegrityStatus.FAILED
    assert rec.integrity_verified_at == read.verified_at     # write-before-outcome (INV-V3)
    assert rec.capture_state is CaptureState.COMPLETED       # §7 r4: lifecycle unchanged

    # next read re-verifies truthfully (stable re-failure — VOR §5 row 6)
    again = service.read_evidence(cid)
    assert isinstance(again, ReadIntegrityFailure)
    assert again.reason == READ_REASON_MISMATCH


def test_failed_record_can_return_to_valid_by_truthful_verification(service):
    """VOR §5 row 5: FAILED → O-1 VALID delivers content + records VALID (truthful latest
    result; NOT auto-repair — content untouched, resolution stays with Issue Report)."""
    content = b"flip-back-content"
    cid = _make_completed(service, content)
    raw = service._store._conn
    raw.execute("UPDATE artifact_content SET content = ?", (b"flip-back-CONTENT",))
    bad = service.read_evidence(cid)
    assert isinstance(bad, ReadIntegrityFailure)
    # operator restores the exact original bytes out-of-store (issue resolution)
    raw.execute("UPDATE artifact_content SET content = ?", (content,))
    good = service.read_evidence(cid)
    assert isinstance(good, ReadSuccess)
    assert good.content == content
    assert service._store.get_record(cid).integrity_status is IntegrityStatus.VALID


def test_missing_content_fails_with_unreadable_reason(service):
    """AC-T114-3 / O-3: content missing → FAILED (content unreadable/missing), no content."""
    cid = _make_completed(service, b"vanishing-content")
    service._store._conn.execute("DELETE FROM artifact_content")
    read = service.read_evidence(cid)
    assert isinstance(read, ReadIntegrityFailure)
    assert read.reason == READ_REASON_UNREADABLE
    rec = service._store.get_record(cid)
    assert rec.integrity_status is IntegrityStatus.FAILED
    assert rec.integrity_verified_at == read.verified_at


def test_refusal_for_non_completed_records(service):
    """AC-T114-4 / INV-V6: ACTIVE and FAILED_INCOMPLETE are refused — no content, no
    verdict, no state change anywhere."""
    from capture import IngestSettledFailure, S1ComputationFailure

    # ACTIVE leftover (record-first, never completed)
    rec = service._store.create_active(received_at="2026-10-01T00:00:00+00:00")
    r1 = service.read_evidence(rec.capture_id)
    assert isinstance(r1, ReadRefused)
    assert r1.capture_state == "ACTIVE"
    assert service._store.get_record(rec.capture_id).capture_state is CaptureState.ACTIVE

    # FAILED_INCOMPLETE (settled residue)
    class BrokenS1(S1Service):
        def compute(self, content):
            raise S1ComputationFailure("no engine")
    settled = CaptureService(service._store, BrokenS1()).ingest(b"x")
    assert isinstance(settled, IngestSettledFailure)
    r2 = service.read_evidence(settled.capture_id)
    assert isinstance(r2, ReadRefused)
    assert r2.capture_state == "FAILED_INCOMPLETE"
    # pinned FAILED untouched by the refused read (§10 r5)
    assert service._store.get_record(settled.capture_id).integrity_status is IntegrityStatus.FAILED

    # unknown capture id → explicit refusal
    r3 = service.read_evidence("no-such-id")
    assert isinstance(r3, ReadRefused)


def test_version_skew_yields_no_verdict_no_write(service):
    """AC-T114-6 / INV-V8: unknown s1_algorithm_id at read → explicit read failure,
    no content, F-07/F-08 unchanged, Issue-Report surfaced — never a fabricated FAILED."""
    content = b"skew-check-content"
    cid = _make_completed(service, content)
    before = service._store.get_record(cid)
    assert before.integrity_status is IntegrityStatus.VALID

    # a future installation that no longer supports sha256-v1 (version-skew simulation)
    skewed_service = CaptureService(service._store, S1Service(supported_ids=frozenset({"sha999-v9"})))
    read = skewed_service.read_evidence(cid)
    assert isinstance(read, ReadVerificationUnavailable)
    assert "sha256-v1" in read.issue_report
    assert len(skewed_service.issue_reports()) == 1          # Issue-Report surfacing

    after = service._store.get_record(cid)
    assert after.integrity_status is before.integrity_status  # unchanged (no fabricated verdict)
    assert after.integrity_verified_at == before.integrity_verified_at
    assert after.capture_state is CaptureState.COMPLETED


def test_no_content_without_same_read_verdict_is_structural(service):
    """INV-V1/V2 structural check: ReadIntegrityFailure has no content field at all;
    ReadSuccess always carries verdict VALID computed in the same read."""
    assert "content" not in ReadIntegrityFailure.__dataclass_fields__
    fields = ReadSuccess.__dataclass_fields__
    assert "content" in fields and "verdict" in fields and "integrity_verified_at" in fields


def test_read_outcome_carries_no_downstream_datum(service):
    """INV-V7 / D-02 boundary inspection: read outcomes expose capture-layer facts only."""
    cid = _make_completed(service, b"boundary-content")
    ok = service.read_evidence(cid)
    assert isinstance(ok, ReadSuccess)
    payload = vars(ok)
    forbidden_tokens = ("invoice_id", "canonical", "external_doc", "s2", "vendor",
                        "customer", "product", "sale", "inventory")
    for token in forbidden_tokens:
        assert token not in {k.lower() for k in payload}
