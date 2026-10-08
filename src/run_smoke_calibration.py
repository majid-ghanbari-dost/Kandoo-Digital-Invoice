"""Cold-start smoke check — WP-12.2 Calibration Runs (19th smoke).

Runs the dispatched calibration path WITHOUT pytest on fresh, cold-start
directories: corpus assembly (three templates) → verified reads → calibration
runs → report determinism → D-08 sweep texture → re-run refusal → corpus byte
stability → fail-closed inputs.

Usage: python3 kandoo/src/run_smoke_calibration.py /tmp/kandoo-smoke-cal
"""
import json
import shutil
import sqlite3
import sys
from pathlib import Path

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-smoke-cal")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import S1Service  # noqa: E402
from corpus import (  # noqa: E402
    CorpusAssemblyService,
    CorpusStore,
)
from calibration import (  # noqa: E402
    CalibrationRunRefused,
    CalibrationRunService,
    RunConfig,
)


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)          # cold start — stale state never reused
    BASE.mkdir(parents=True, exist_ok=True)
    s1 = S1Service()

    # 1. assemble the three declared synthetic corpora (clearly marked)
    with CorpusStore(BASE / "corpus.db", s1) as store:
        assembly = CorpusAssemblyService(store, s1)
        corpora = {}
        for name, template, count, seed in (
                ("clean", "kv-invoice-clean-v1", 3, 11),
                ("rounding", "kv-invoice-rounding-probe-v1", 6, 22),
                ("review", "kv-invoice-review-probe-v1", 2, 33)):
            outcome = assembly.assemble(template, count, seed)
            corpora[name] = assembly.read_corpus(
                outcome.manifest.corpus_version_id)
    print(f"1. corpora     -> 3 SYNTHETIC corpora assembled "
          f"(clean=3, rounding=6, review=2 entries; marked "
          f"SYNTHETIC_PILOT_FIXTURE)")

    # 2. clean-corpus run — the ACCEPTED path, all reference rules VALID
    clean_report = CalibrationRunService(BASE / "ws-clean", s1).run(
        corpora["clean"],
        RunConfig(corpus_version_id=corpora["clean"].manifest.corpus_version_id))
    clean_json = json.loads(clean_report.to_json_bytes())
    assert clean_json["gate_counts"] == {"ACCEPTED": 3}, clean_json["gate_counts"]
    assert all(counts == {"MATCH": 3}
               for counts in clean_json["field_counts"].values())
    print("2. clean run   -> gate ACCEPTED x3; all labels MATCH; "
          "4 reference rules VALID")

    # 3. rounding-corpus run — the D-08 sweep surface
    rounding_report = CalibrationRunService(BASE / "ws-rounding", s1).run(
        corpora["rounding"],
        RunConfig(corpus_version_id=corpora["rounding"].manifest.corpus_version_id))
    rounding_json = json.loads(rounding_report.to_json_bytes())
    sweeps = {c["tolerance"]: c for c in
              rounding_json["tolerance_candidate_results"]}
    assert sweeps["0.00"]["beyond_tolerance"] == 6
    assert sweeps["0.02"]["within_tolerance"] == 6
    assert sweeps["0.01"]["within_tolerance"] >= 1 \
        and sweeps["0.01"]["beyond_tolerance"] >= 1
    print("3. D-08 sweep  -> 0.00: all beyond | 0.01: split | "
          "0.02: all within (counts only — nothing ratified)")

    # 4. review-corpus run — the uncertainty path, ABSENT label matched
    review_report = CalibrationRunService(BASE / "ws-review", s1).run(
        corpora["review"],
        RunConfig(corpus_version_id=corpora["review"].manifest.corpus_version_id))
    review_json = json.loads(review_report.to_json_bytes())
    assert review_json["gate_counts"] == {"REVIEW": 2}
    assert review_json["field_counts"]["tax.amount"] == {"MATCH": 2}
    print("4. review run  -> gate REVIEW x2 (upstream uncertainty held); "
          "ABSENT label matched")

    # 5. determinism — a fresh workspace reproduces BYTE-IDENTICAL JSON
    twin = CalibrationRunService(BASE / "ws-rounding-twin", s1).run(
        corpora["rounding"],
        RunConfig(corpus_version_id=corpora["rounding"].manifest.corpus_version_id))
    assert twin.to_json_bytes() == rounding_report.to_json_bytes()
    print("5. determinism -> fresh workspace: byte-identical report JSON")

    # 6. re-run refusal — one run per workspace
    try:
        CalibrationRunService(BASE / "ws-rounding", s1).run(
            corpora["rounding"],
            RunConfig(corpus_version_id=corpora["rounding"].manifest.corpus_version_id))
        raise AssertionError("re-run was accepted")
    except CalibrationRunRefused:
        pass
    print("6. re-run      -> CalibrationRunRefused (one run per workspace)")

    # 7. corpus byte stability — the runs never touched the corpus store
    conn = sqlite3.connect(str(BASE / "corpus.db"))
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM corpus_entries").fetchone()[0]
    finally:
        conn.close()
    assert rows == 3 + 6 + 2
    print(f"7. corpus safe -> corpus store unchanged ({rows} entries)")

    # 8. fail-closed inputs — used workspace + unverified corpus refused
    try:
        CalibrationRunService(BASE / "ws-clean", s1).run(
            corpora["rounding"],
            RunConfig(corpus_version_id=corpora["rounding"].manifest.corpus_version_id))
        raise AssertionError("used workspace accepted")
    except CalibrationRunRefused:
        pass
    print("8. fail-closed -> used workspace refused; report-only output")

    print("SMOKE OK — calibration run path works end-to-end (cold start)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
