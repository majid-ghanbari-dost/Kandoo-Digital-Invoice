"""Cold-start smoke check — WP-1.2 S1 Fingerprint & Integrity HARDENING
(20th smoke; SPEC-WP12-S1H §9/§10 OD-SH-D).

Runs the declared edge-input matrix E1..E11 WITHOUT pytest on fresh, cold-start
directories: determinism ×2 over every class → content sensitivity + framing →
type exactness + hostile fields → ingest/read edge roundtrips → capability
failure fail-closed → store-defect probes → algorithm agility → frozen binding
recap. Every step asserts TYPED outcomes only — no silent path is tolerated.

Usage: python3 kandoo/src/run_smoke_s1_hardening.py /tmp/kandoo-smoke-s1h
"""
import shutil
import sqlite3
import sys
from pathlib import Path

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-smoke-s1h")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import (  # noqa: E402
    NOTE_S1_COMPUTATION_FAILED,
    S1_ALGORITHM_ID,
    S1ComputationFailure,
    S1Service,
    CaptureService,
    CaptureStore,
    IngestCompleted,
    IngestDuplicateAtCapture,
    IngestSettledFailure,
    ReadIntegrityFailure,
    ReadSuccess,
    ReadVerificationUnavailable,
)

LARGE = bytes(range(256)) * (4 * 1024 * 1024 // 256)          # E3 (OD-SH-B)
PERSIAN = "فاکتور شماره ۱۲۳ — مجموع: ۱٬۵۰۰٬۰۰۰ ریال".encode("utf-8")   # E4


class BrokenS1(S1Service):
    """E9: capability failure injected at compute time."""

    def compute(self, content):
        raise S1ComputationFailure("injected digest engine outage")


def step(ok, label):
    print(f"{label}")
    if not ok:
        print("SMOKE FAILED", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)              # cold start — stale state never reused
    BASE.mkdir(parents=True, exist_ok=True)
    s1 = S1Service()

    # 1. determinism ×2 over every declared class (E1..E5, E11 inputs)
    classes = {"empty": b"", "single": b"A", "large": LARGE, "persian": PERSIAN,
               "magic": b"%PDF-1.7 fake", "framed": CaptureService.aggregate(
                   [b"part-1", b"", b"part-3"])}
    for name, blob in classes.items():
        assert s1.compute(blob) == s1.compute(blob), name
    step(True, "1. determinism  -> x2 identical (S1,id) on all 6 declared classes")

    # 2. content sensitivity (E3/E4/E6) + framing ambiguity (E11)
    for blob in (LARGE, PERSIAN, b"boundary"):
        mid = len(blob) // 2
        assert s1.compute(blob[:mid] + bytes([blob[mid] ^ 0x01]) + blob[mid + 1:]).s1 \
            != s1.compute(blob).s1
    assert CaptureService.aggregate([b"ab", b"c"]) != CaptureService.aggregate([b"a", b"bc"])
    step(True, "2. sensitivity  -> every declared mutation changes S1; framing unambiguous")

    # 3. type exactness (E7) + hostile fields (E8)
    v = s1.compute(b"type-exact")
    assert s1.compute(bytearray(b"type-exact")) == s1.compute(memoryview(b"type-exact")) == v
    for bad in ("text", 42, None, [1]):
        try:
            s1.compute(bad)
            raise AssertionError("non-byte compute accepted")
        except S1ComputationFailure:
            pass
        assert s1.verify(bad, "0" * 64, S1_ALGORITHM_ID).outcome == "NO_VERDICT"
    assert s1.verify(b"type-exact", "z" * 64, S1_ALGORITHM_ID).outcome == "FAILED"
    assert s1.verify(b"type-exact", v.s1, "sha999-v42").outcome == "NO_VERDICT"
    step(True, "3. type/hostile  -> bytes-only compute typed; wrong digest FAILED; "
               "unknown id NO_VERDICT")

    # 4. ingest/read edge roundtrips + duplicate explicitness (E1/E3/E4)
    store = CaptureStore(BASE / "capture.db")
    service = CaptureService(store, S1Service())
    done_ids = {}
    for name, blob in (("empty", b""), ("persian", PERSIAN), ("large", LARGE)):
        outcome = service.ingest(blob, source_label="smoke-s1h")
        assert isinstance(outcome, IngestCompleted), name
        read = service.read_evidence(outcome.capture_id)
        assert isinstance(read, ReadSuccess) and read.content == blob, name
        assert isinstance(service.ingest(blob), IngestDuplicateAtCapture), name
        done_ids[name] = outcome.capture_id
    step(True, "4. roundtrips   -> empty/persian/4MiB ingest+read VALID; "
               "duplicates explicit")

    # 5. capability failure (E9) — typed settlement, zero COMPLETED residue
    broken = CaptureService(store, BrokenS1())
    outcome = broken.ingest(b"any-content")
    assert isinstance(outcome, IngestSettledFailure)
    assert outcome.settlement_note == NOTE_S1_COMPUTATION_FAILED
    assert store.get_record(outcome.capture_id).capture_state.value == "FAILED_INCOMPLETE"
    assert store._conn.execute(
        "SELECT COUNT(*) AS n FROM capture_records "
        "WHERE capture_state='COMPLETED'").fetchone()["n"] == 3   # only the 3 valid ones
    step(True, "5. fail-closed   -> compute outage: IngestSettledFailure, pinned, "
               "zero COMPLETED residue")

    # 6. store-defect probes (E10): tampered content + forged unknown id
    store._conn.execute(
        "UPDATE artifact_content SET content = ? WHERE content_ref = "
        "(SELECT artifact_ref FROM capture_records WHERE capture_id = ?)",
        (sqlite3.Binary(b"tampered!"), done_ids["persian"]))
    read = service.read_evidence(done_ids["persian"])
    assert isinstance(read, ReadIntegrityFailure)        # never content, never silent
    forged = store._conn.execute(
        """INSERT INTO capture_records (
               capture_id, s1, s1_algorithm_id, artifact_ref, created_at, capture_state,
               integrity_status, integrity_verified_at, received_at, source_label,
               artifact_format_hint, capture_entry_metadata, artifact_size_bytes, settlement_note)
           VALUES ('forged-smoke', ?, 'legacy-unknown-v1', 'capture-content:v1:forged',
                   '2026-10-09T00:00:00+00:00', 'COMPLETED', 'VALID',
                   '2026-10-09T00:00:00+00:00', '2026-10-09T00:00:00+00:00',
                   'smoke', 'UNKNOWN', '{}', 12, NULL)""", ("c" * 64,))
    store._conn.execute(
        "INSERT INTO artifact_content (content_ref, content) VALUES "
        "('capture-content:v1:forged', ?)", (sqlite3.Binary(b"forged-bytes"),))
    read = service.read_evidence("forged-smoke")
    assert isinstance(read, ReadVerificationUnavailable)  # O-4, never a guessed verdict
    assert service.issue_reports()                        # Issue-Report surfaced
    try:
        store._conn.execute(
            """INSERT INTO capture_records (
                   capture_id, s1, s1_algorithm_id, artifact_ref, created_at, capture_state,
                   integrity_status, integrity_verified_at, received_at, source_label,
                   artifact_format_hint, capture_entry_metadata, artifact_size_bytes, settlement_note)
               VALUES ('impossible', NULL, NULL, NULL, 'x', 'COMPLETED', 'VALID',
                       'x', 'x', 'x', 'UNKNOWN', '{}', 1, NULL)""")
        raise AssertionError("CHECK constraint did not refuse")
    except sqlite3.IntegrityError:
        pass
    step(True, "6. store defects -> tamper ReadIntegrityFailure; forged unknown id "
               "ReadVerificationUnavailable + issue; CHECK refuses impossible state")

    # 7. algorithm agility (§6): ID-bound comparisons; pair-keyed uniqueness
    future = S1Service(algorithm_id="sha256-v2-future")   # declared seam only
    v_future = future.compute(b"agility-probe")
    assert s1.verify(b"agility-probe", v_future.s1, v_future.s1_algorithm_id) \
        .outcome == "NO_VERDICT"
    assert future.verify(b"agility-probe", v_future.s1, v_future.s1_algorithm_id) \
        .outcome == "VALID"
    from capture import UAC_GRANTED
    digest = s1.compute(b"pair-keyed").s1
    for alien_id in ("sha256-v1", "legacy-alien-v1"):
        rec = store.create_active(received_at="2026-10-09T00:00:01+00:00")
        store.persist_content(rec.capture_id, b"pair-keyed-" + alien_id.encode())
        store.attach_s1(rec.capture_id, digest, alien_id)
        store.record_verification(rec.capture_id, "VALID", "2026-10-09T00:00:02+00:00")
        assert store.complete_record(rec.capture_id) == UAC_GRANTED
        assert store.count_by_key(digest, alien_id) == (1, 1)
    step(True, "7. agility       -> cross-id NO_VERDICT; uniqueness keyed on "
               "(s1, s1_algorithm_id) pairs")

    # 8. frozen binding recap + full-matrix recap (counts only, nothing patched)
    assert S1_ALGORITHM_ID == "sha256-v1"
    assert s1.algorithm_id == "sha256-v1" and s1.supported_ids == frozenset({"sha256-v1"})
    completed = store._conn.execute(
        "SELECT COUNT(*) AS n FROM capture_records "
        "WHERE capture_state='COMPLETED'").fetchone()["n"]
    store.close()
    assert completed == 6                                 # 3 valid + 1 forged defect probe + 2 pair-keyed
    print(f"8. binding recap-> S1_ALGORITHM_ID == sha256-v1 (FROZEN); "
          f"{completed} COMPLETED records; E1..E11 executed; zero code patched")
    print("SMOKE OK — S1 hardening edge matrix holds end-to-end (cold start)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
