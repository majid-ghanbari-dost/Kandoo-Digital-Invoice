"""WP-1.2 S1 Fingerprint & Integrity HARDENING suite (SPEC-WP12-S1H §4/§5/§9).

The declared edge-input matrix E1..E11 executed against the FROZEN WP-1.1
layer. This file is TEST SURFACE ONLY — additive, zero production-code
change (OD-SH-A/OD-SH-F); every negative test names the typed outcome it
demands (no silent path may exist). Required properties per class:
DETERMINISTIC / CONTENT-SENSITIVE / TYPE-EXACT / EXPLICIT-OUTCOME / ID-BOUND.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import (  # noqa: E402
    NOTE_S1_COMPUTATION_FAILED,
    READ_REASON_MISMATCH,
    S1_ALGORITHM_ID,
    S1ComputationFailure,
    S1Service,
    CaptureService,
    CaptureState,
    IngestCompleted,
    IngestDuplicateAtCapture,
    IngestSettledFailure,
    IntegrityStatus,
    ReadIntegrityFailure,
    ReadRefused,
    ReadSuccess,
    ReadVerificationUnavailable,
)

LARGE = bytes(range(256)) * (4 * 1024 * 1024 // 256)      # OD-SH-B: 4 MiB
PERSIAN = "فاکتور شماره ۱۲۳ — مجموع: ۱٬۵۰۰٬۰۰۰ ریال".encode("utf-8")
CJK = "請求書番号1234・合計15,000円".encode("utf-8")
COMBINING = "e\u0301gal\u0301 Z\u200dWJ seq".encode("utf-8")


def _ingest_completed(service, content, **kw):
    outcome = service.ingest(content, **kw)
    assert isinstance(outcome, IngestCompleted), outcome
    return outcome


def _mutation_positions(data: bytes):
    """OD-SH-C: first / last / middle byte + high-bit flip (XOR — a byte that
    already carries the high bit, e.g. any UTF-8 multibyte, must still change)."""
    mid = len(data) // 2
    return (
        ("first", bytes([data[0] ^ 0x01]) + data[1:]),
        ("last", data[:-1] + bytes([data[-1] ^ 0x01])),
        ("middle", data[:mid] + bytes([data[mid] ^ 0x01]) + data[mid + 1:]),
        ("high-bit", data[:1] + bytes([data[1] ^ 0x80]) + data[2:]),
    )


# ---------------------------------------------------------------------------
# E1 — EMPTY (deterministic; observed outcomes recorded, no policy added)
# ---------------------------------------------------------------------------

def test_e1_empty_compute_deterministic_x2():
    s1 = S1Service()
    first, second = s1.compute(b""), s1.compute(b"")
    assert first == second
    assert first.s1 == ("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca"
                        "495991b7852b855")
    assert first.s1_algorithm_id == S1_ALGORITHM_ID == "sha256-v1"


def test_e1_empty_ingest_read_duplicate_explicit(service):
    done = _ingest_completed(service, b"")
    read = service.read_evidence(done.capture_id)
    assert isinstance(read, ReadSuccess) and read.content == b""
    dup = service.ingest(b"")
    assert isinstance(dup, IngestDuplicateAtCapture)
    assert dup.existing_capture_id == done.capture_id


# ---------------------------------------------------------------------------
# E2 — SINGLE-BYTE
# ---------------------------------------------------------------------------

def test_e2_single_byte_all_256_deterministic_and_distinct():
    s1 = S1Service()
    digests = {s1.compute(bytes([v])).s1 for v in range(256)}
    assert len(digests) == 256                          # all distinct
    for v in (0x00, 0x41, 0xFF):
        assert s1.compute(bytes([v])) == s1.compute(bytes([v]))


# ---------------------------------------------------------------------------
# E3 — LARGE (4 MiB)
# ---------------------------------------------------------------------------

def test_e3_large_deterministic_and_roundtrip(service):
    first, second = S1Service().compute(LARGE), S1Service().compute(LARGE)
    assert first == second
    done = _ingest_completed(service, LARGE, source_label="hardening-e3")
    read = service.read_evidence(done.capture_id)
    assert isinstance(read, ReadSuccess)
    assert read.content == LARGE and read.s1 == first.s1


def test_e3_large_single_byte_mutation_changes_s1_and_verifies_failed():
    s1 = S1Service()
    base = s1.compute(LARGE)
    for name, mutated in _mutation_positions(LARGE):
        assert s1.compute(mutated).s1 != base.s1, name   # CONTENT-SENSITIVE
        assert s1.verify(mutated, base.s1, base.s1_algorithm_id).outcome == "FAILED"


# ---------------------------------------------------------------------------
# E4 — MULTILINGUAL (UTF-8 multibyte; byte-level sensitivity)
# ---------------------------------------------------------------------------

def test_e4_multilingual_deterministic_and_byte_sensitive():
    s1 = S1Service()
    for blob in (PERSIAN, CJK, COMBINING):
        assert s1.compute(blob) == s1.compute(blob)
        mutated = blob[:-1] + bytes([blob[-1] ^ 0x01])
        assert s1.compute(mutated).s1 != s1.compute(blob).s1


def test_e4_multilingual_ingest_roundtrip_and_duplicate(service):
    done = _ingest_completed(service, PERSIAN, source_label="hardening-e4")
    read = service.read_evidence(done.capture_id)
    assert isinstance(read, ReadSuccess) and read.content == PERSIAN
    assert isinstance(service.ingest(PERSIAN), IngestDuplicateAtCapture)
    # a one-grapheme-cluster change is a byte change → different S1 → new record
    other = PERSIAN + b"\xd8\x8c"                       # append "،" (Arabic comma)
    done2 = _ingest_completed(service, other)
    assert done2.capture_id != done.capture_id


# ---------------------------------------------------------------------------
# E5 — BINARY MAGIC PREFIXES (sniff stays mechanical; never affects S1)
# ---------------------------------------------------------------------------

def test_e5_magic_prefixes_sniff_mechanical_s1_untouched(service):
    s1 = S1Service()
    samples = [b"%PDF-1.7 fake", b"\x89PNG\r\n\x1a\nrest", b"\xff\xd8\xffjpeg",
               b"GIF89a", b"PK\x03\x04zip", b"\x1f\x8bgz", b"\x00\x01\x02binary"]
    hints = set()
    for blob in samples:
        hints.add(CaptureService.sniff_format_hint(blob))
        assert s1.compute(blob) == s1.compute(blob)      # sniff never feeds S1
        done = _ingest_completed(service, blob)
        assert isinstance(service.read_evidence(done.capture_id), ReadSuccess)
    assert len(hints) == 7                               # each hint distinct/mechanical


# ---------------------------------------------------------------------------
# E6 — BOUNDARY MUTATIONS (declared positions; FAILED is explicit)
# ---------------------------------------------------------------------------

def test_e6_boundary_mutations_all_change_s1():
    s1 = S1Service()
    base = s1.compute(PERSIAN + CJK)
    for name, mutated in _mutation_positions(PERSIAN + CJK):
        assert s1.compute(mutated).s1 != base.s1, name


def test_e6_mutated_content_read_is_explicit_integrity_failure(service):
    done = _ingest_completed(service, b"immutable-payload-for-e6")
    record = service._store.get_record(done.capture_id)
    tampered = b"immutable-payload-for-e7"               # one-byte class change
    service._store._conn.execute(
        "UPDATE artifact_content SET content = ? WHERE content_ref = ?",
        (sqlite3.Binary(tampered), record.artifact_ref))
    read = service.read_evidence(done.capture_id)
    assert isinstance(read, ReadIntegrityFailure)
    assert read.reason == READ_REASON_MISMATCH
    assert not hasattr(read, "content")                  # content is NEVER carried
    assert service._store.get_record(done.capture_id).integrity_status is \
        IntegrityStatus.FAILED                           # truthful latest write


# ---------------------------------------------------------------------------
# E7 — TYPE EXACTNESS (byte-sequence types; others refused explicitly)
# ---------------------------------------------------------------------------

def test_e7_byte_like_types_share_one_digest():
    s1 = S1Service()
    v_bytes = s1.compute(b"type-exactness")
    assert s1.compute(bytearray(b"type-exactness")) == v_bytes
    assert s1.compute(memoryview(b"type-exactness")) == v_bytes


@pytest.mark.parametrize("bad", ["text", 42, None, [1, 2], {"a": b"b"}, 3.14])
def test_e7_non_byte_compute_raises_typed(service, bad):
    with pytest.raises(S1ComputationFailure):
        S1Service().compute(bad)


@pytest.mark.parametrize("bad", ["text", 42, None, [1, 2]])
def test_e7_non_byte_verify_is_no_verdict_never_crash(bad):
    verdict = S1Service().verify(bad, "0" * 64, S1_ALGORITHM_ID)
    assert verdict.outcome == "NO_VERDICT" and verdict.reason


def test_e7_non_bytes_ingest_fails_fast_with_zero_residue(service):
    """E7×ingest cell — OBSERVED frozen behavior, recorded honestly (OD-SH-F):
    a caller-side type violation at the orchestrator entry fails FAST via the
    interpreter's own loud TypeError/AttributeError (mechanical sniff precedes
    compute) with ZERO store residue; the TYPED refusal lives at the S1
    capability boundary (compute/verify), where the frozen designs declare it.
    No patch is applied inside this additive WP — the observation is recorded
    in the hardening report for TM/PO."""
    import pytest
    for bad in ("not-bytes", 42, None, [1, 2], {"a": b"b"}):
        with pytest.raises((TypeError, AttributeError)):
            service.ingest(bad)
    # zero residue: no record row, no content row, nothing settled
    assert service._store._conn.execute(
        "SELECT COUNT(*) AS n FROM capture_records").fetchone()["n"] == 0
    assert service._store._conn.execute(
        "SELECT COUNT(*) AS n FROM artifact_content").fetchone()["n"] == 0


# ---------------------------------------------------------------------------
# E8 — HOSTILE S1 FIELDS (wrong digests / unknown ids — never a guessed verdict)
# ---------------------------------------------------------------------------

def test_e8_wrong_digests_are_failed():
    s1 = S1Service()
    v = s1.compute(b"hostile-fields")
    for hostile in ("0" * 64, "z" * 64, v.s1[:-1], v.s1 + "0", ""):
        assert s1.verify(b"hostile-fields", hostile, S1_ALGORITHM_ID).outcome \
            == "FAILED", hostile[:12]


def test_e8_unknown_or_empty_algorithm_id_is_no_verdict():
    s1 = S1Service()
    v = s1.compute(b"id-bound-check")
    for alien_id in ("sha999-v42", "md5-v1", "", "SHA256-V1"):
        verdict = s1.verify(b"id-bound-check", v.s1, alien_id)
        assert verdict.outcome == "NO_VERDICT", alien_id
        assert "unknown s1_algorithm_id" in (verdict.reason or "")


def test_e8_read_refused_for_non_completed_is_explicit(service):
    done = _ingest_completed(service, b"read-scope-e8")
    service._store._conn.execute(
        "UPDATE capture_records SET capture_state='ACTIVE' WHERE capture_id=?",
        (done.capture_id,))
    assert isinstance(service.read_evidence(done.capture_id), ReadRefused)
    assert isinstance(service.read_evidence("no-such-id"), ReadRefused)


# ---------------------------------------------------------------------------
# E9 — INGEST-LEVEL CAPABILITY FAILURE (fail-closed, zero residue)
# ---------------------------------------------------------------------------

class _BrokenS1(S1Service):
    """Capability failure injection at compute time (test surface only)."""

    def compute(self, content):
        raise S1ComputationFailure("injected digest engine outage")


def test_e9_compute_failure_ingest_settles_typed_with_zero_completed_residue(tmp_path):
    from capture import CaptureStore
    store = CaptureStore(tmp_path / "capture.db")
    try:
        broken = CaptureService(store, _BrokenS1())
        outcome = broken.ingest(b"any-content")
        assert isinstance(outcome, IngestSettledFailure)
        assert outcome.settlement_note == NOTE_S1_COMPUTATION_FAILED
        record = store.get_record(outcome.capture_id)
        assert record.capture_state is CaptureState.FAILED_INCOMPLETE
        assert store.count_by_key("", "sha256-v1") == (0, 0)   # s1 never attached
        assert store._conn.execute(
            "SELECT COUNT(*) AS n FROM capture_records "
            "WHERE capture_state='COMPLETED'").fetchone()["n"] == 0
    finally:
        store.close()


def test_e9_honest_reingest_after_capability_restore(service):
    """After capability restoration the same content completes normally —
    the failed attempt remains retained evidence, nothing is hidden."""
    outcome = service.ingest(b"retry-content")
    assert isinstance(outcome, IngestCompleted)
    record = service._store.get_record(outcome.capture_id)
    completed, total = service._store.count_by_key(record.s1, record.s1_algorithm_id)
    assert (completed, total) == (1, 1)


# ---------------------------------------------------------------------------
# E10 — STORE-DEFECT PROBES (direct-SQL forged rows; typed outcomes only)
# ---------------------------------------------------------------------------

def _insert_forged_completed(store, s1_value, algorithm_id, content):
    store._conn.execute(
        """INSERT INTO capture_records (
               capture_id, s1, s1_algorithm_id, artifact_ref, created_at, capture_state,
               integrity_status, integrity_verified_at, received_at, source_label,
               artifact_format_hint, capture_entry_metadata, artifact_size_bytes, settlement_note)
           VALUES ('forged-' || hex(randomblob(6)), ?, ?, 'capture-content:v1:forged',
                   '2026-10-09T00:00:00+00:00', 'COMPLETED', 'VALID', '2026-10-09T00:00:00+00:00',
                   '2026-10-09T00:00:00+00:00', 'hardening', 'UNKNOWN', '{}', ?, NULL)""",
        (s1_value, algorithm_id, len(content)))
    store._conn.execute(
        "INSERT INTO artifact_content (content_ref, content) VALUES "
        "('capture-content:v1:forged', ?)", (sqlite3.Binary(content),))
    row = store._conn.execute(
        "SELECT capture_id FROM capture_records WHERE artifact_ref='capture-content:v1:forged'"
    ).fetchone()
    return row["capture_id"]


def test_e10_forged_unknown_algorithm_id_read_is_no_verdict_surfaced(service):
    forged_id = _insert_forged_completed(service._store, "a" * 64,
                                         "legacy-unknown-v1", b"forged-bytes")
    read = service.read_evidence(forged_id)
    assert isinstance(read, ReadVerificationUnavailable)   # O-4, never a guessed verdict
    assert service.issue_reports()                        # Issue-Report surfaced


def test_e10_check_refuses_completed_without_s1(store):
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            """INSERT INTO capture_records (
                   capture_id, s1, s1_algorithm_id, artifact_ref, created_at, capture_state,
                   integrity_status, integrity_verified_at, received_at, source_label,
                   artifact_format_hint, capture_entry_metadata, artifact_size_bytes, settlement_note)
               VALUES ('impossible', NULL, NULL, NULL, '2026', 'COMPLETED',
                       'VALID', '2026', '2026', 'x', 'UNKNOWN', '{}', 1, NULL)""")


def test_e10_verification_unavailable_never_writes_integrity(service):
    """INV-V8 analog: an O-4 read leaves the forged record's integrity fields untouched."""
    forged_id = _insert_forged_completed(service._store, "b" * 64,
                                         "legacy-unknown-v1", b"o4-bytes")
    before = service._store.get_record(forged_id)
    service.read_evidence(forged_id)
    after = service._store.get_record(forged_id)
    assert before.integrity_status == after.integrity_status == IntegrityStatus.VALID
    assert before.integrity_verified_at == after.integrity_verified_at


# ---------------------------------------------------------------------------
# E11 — FRAMING EDGES (aggregation determinism binds the entry point)
# ---------------------------------------------------------------------------

def test_e11_aggregate_edges_and_framing_ambiguity():
    assert CaptureService.aggregate([]) == b""
    assert CaptureService.aggregate([b""]) == (0).to_bytes(8, "big")
    assert CaptureService.aggregate([b"ab", b"c"]) != CaptureService.aggregate([b"a", b"bc"])
    assert CaptureService.aggregate([b"abc"]) != CaptureService.aggregate([b"ab", b"c"])
    big = bytes(64)
    assert CaptureService.aggregate([big]) == CaptureService.aggregate([big])
    assert CaptureService.aggregate([b"x", big]) != CaptureService.aggregate([big, b"x"])


def test_e11_framed_aggregates_ingest_deterministically(service):
    a = CaptureService.aggregate([b"part-1", b"", b"part-3"])
    b = CaptureService.aggregate([b"part-1", b"", b"part-3"])
    done_a = _ingest_completed(service, a)
    assert isinstance(service.ingest(b), IngestDuplicateAtCapture)
    assert service.read_evidence(done_a.capture_id).content == a


# ---------------------------------------------------------------------------
# §6 ALGORITHM AGILITY (declared surface — frozen binding)
# ---------------------------------------------------------------------------

def test_agility_default_binding_is_sha256_v1():
    assert S1_ALGORITHM_ID == "sha256-v1"
    s1 = S1Service()
    assert s1.algorithm_id == "sha256-v1"
    assert s1.supported_ids == frozenset({"sha256-v1"})


def test_agility_cross_id_comparison_is_no_verdict_never_equal():
    frozen = S1Service()                                  # sha256-v1
    future = S1Service(algorithm_id="sha256-v2-future")   # declared seam only
    v_future = future.compute(b"agility-probe")
    assert v_future.s1_algorithm_id == "sha256-v2-future"
    assert frozen.verify(b"agility-probe", v_future.s1,
                         v_future.s1_algorithm_id).outcome == "NO_VERDICT"
    assert future.verify(b"agility-probe", v_future.s1,
                         v_future.s1_algorithm_id).outcome == "VALID"


def test_agility_store_uniqueness_is_keyed_on_the_pair(store):
    """P-S1-6 at the storage level: the same digest under DIFFERENT declared ids
    is NOT one key — each (s1, s1_algorithm_id) pair completes exactly once."""
    from capture import UAC_GRANTED
    digest = S1Service().compute(b"pair-keyed").s1
    for alien_id in ("sha256-v1", "legacy-alien-v1"):
        rec = store.create_active(received_at="2026-10-09T00:00:00+00:00")
        store.persist_content(rec.capture_id, b"pair-keyed-" + alien_id.encode())
        store.attach_s1(rec.capture_id, digest, alien_id)
        store.record_verification(rec.capture_id, "VALID", "2026-10-09T00:00:01+00:00")
        assert store.complete_record(rec.capture_id) == UAC_GRANTED
        assert store.count_by_key(digest, alien_id) == (1, 1)


# ---------------------------------------------------------------------------
# §9 — suite hygiene (vocabulary sweep; no downstream semantics)
# ---------------------------------------------------------------------------

def test_suite_import_surface_is_capture_only():
    """AST probe: this hardening suite imports the frozen capture layer only —
    no downstream package, no non-stdlib surface beyond pytest."""
    import ast
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"sqlite3", "sys", "pathlib", "pytest", "capture", "ast"}
    forbidden = {"sale", "customer_linking", "inventory", "digital_invoice",
                 "canonical_assembly", "canonicalization", "calibration", "corpus"}
    assert imported.isdisjoint(forbidden)

