"""T-1.1.3 capability tests — S1 properties (AC-T113-1; INV-C2 / P-S1-1..P-S1-7)."""
import hashlib

from capture import S1Service, S1ComputationFailure, S1_ALGORITHM_ID
from capture import CaptureService


def test_determinism_same_bytes_same_s1():
    s1 = S1Service()
    data = b"invoice-scan-bytes-2026"
    first = s1.compute(data)
    second = s1.compute(data)
    assert first.s1 == second.s1 == hashlib.sha256(data).hexdigest()
    assert first.s1_algorithm_id == S1_ALGORITHM_ID == "sha256-v1"


def test_known_vector_abc():
    s1 = S1Service()
    assert s1.compute(b"abc").s1 == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


def test_single_byte_mutation_changes_s1():
    s1 = S1Service()
    a = s1.compute(b"total: 1000")
    b = s1.compute(b"total: 1001")   # one byte differs
    assert a.s1 != b.s1


def test_empty_and_large_inputs_deterministic():
    s1 = S1Service()
    assert s1.compute(b"").s1 == hashlib.sha256(b"").hexdigest()
    blob = bytes(range(256)) * 1024
    assert s1.compute(blob).s1 == s1.compute(bytes(blob)).s1


def test_lowercase_hex_no_truncation():
    s1 = S1Service()
    v = s1.compute(b"x")
    assert len(v.s1) == 64                              # full 256-bit digest
    assert v.s1 == v.s1.lower()
    int(v.s1, 16)                                       # canonical hex


def test_verify_valid_failed_no_verdict():
    s1 = S1Service()
    v = s1.compute(b"payload")
    assert s1.verify(b"payload", v.s1, v.s1_algorithm_id).outcome == "VALID"
    assert s1.verify(b"payloaD", v.s1, v.s1_algorithm_id).outcome == "FAILED"
    nv = s1.verify(b"payload", v.s1, "sha999-v42")      # unknown id → NO-VERDICT (S1 §8 F2)
    assert nv.outcome == "NO_VERDICT"
    assert nv.reason and "unknown s1_algorithm_id" in nv.reason


def test_compute_failure_raises_explicitly(monkeypatch):
    s1 = S1Service()

    def boom(_content):
        raise RuntimeError("digest engine down")
    monkeypatch.setattr(hashlib, "sha256", boom)
    try:
        s1.compute(b"data")
        raised = False
    except S1ComputationFailure:
        raised = True
    assert raised


def test_aggregation_determinism_v1_1_c3():
    """Entry-point aggregation: same ordered content set → same bytes → same S1 (C3)."""
    parts = [b"page-1-bytes", b"page-2-bytes", b"page-3-bytes"]
    a = CaptureService.aggregate(parts)
    b = CaptureService.aggregate(list(parts))
    assert a == b
    s1 = S1Service()
    assert s1.compute(a).s1 == s1.compute(b).s1
    # order matters (deterministic, not order-insensitive): different order → different S1
    assert CaptureService.aggregate(parts) != CaptureService.aggregate(list(reversed(parts)))
    # any single-part content change → different aggregate (content sensitivity)
    mutated = [b"page-1-bytes", b"page-2-bytes!", b"page-3-bytes"]
    assert CaptureService.aggregate(parts) != CaptureService.aggregate(mutated)
    # framing is unambiguous: no accidental concatenation collisions
    assert CaptureService.aggregate([b"ab", b"c"]) != CaptureService.aggregate([b"a", b"bc"])
