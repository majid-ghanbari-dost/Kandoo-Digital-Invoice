"""Run the complete ORDER 16 Python regression and synthetic accuracy gate."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from image_extraction_adapter.synthetic_layouts import (
    measure_layout_match_accuracy,
    measure_synthetic_numeric_accuracy_by_layout,
    render_synthetic_invoice,
    synthetic_layouts,
)
from verify_e72_vectors import verify_vectors


class HarnessFailure(RuntimeError):
    pass


def _run_pytest() -> str:
    environment = os.environ.copy()
    current = environment.get("PYTHONPATH", "")
    source_paths = [str(ROOT / "src"), str(ROOT / "scripts")]
    if current:
        source_paths.append(current)
    environment["PYTHONPATH"] = os.pathsep.join(source_paths)
    command = [sys.executable, "-m", "pytest", "-q"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = result.stdout or ""
    print(output, end="" if output.endswith("\n") or not output else "\n")
    if result.returncode != 0:
        raise HarnessFailure(f"full Python test suite exited {result.returncode}")
    return output


def _synthetic_metrics(temp_root: Path) -> dict[str, Any]:
    profiles = synthetic_layouts()
    training = [
        render_synthetic_invoice(
            temp_root / f"{profile.layout_id}-train.png",
            layout_id=profile.layout_id,
            invoice_index=0,
        )
        for profile in profiles
    ]
    holdout = [
        render_synthetic_invoice(
            temp_root / f"{profile.layout_id}-holdout.png",
            layout_id=profile.layout_id,
            invoice_index=1,
        )
        for profile in profiles
    ]
    layout_metrics = measure_layout_match_accuracy(training, holdout)
    numeric_metrics = measure_synthetic_numeric_accuracy_by_layout(training, holdout)
    if set(layout_metrics) != set(numeric_metrics) or set(numeric_metrics) != {
        profile.layout_id for profile in profiles
    }:
        raise HarnessFailure("synthetic harness did not produce a count for every declared layout")

    wrong_total = 0
    for layout_id, result in numeric_metrics.items():
        expected = result.get("expected_fields")
        extracted = result.get("extracted_fields")
        correct = result.get("correct_fields")
        wrong = result.get("extracted_but_wrong")
        review = result.get("review_or_missing_fields")
        counts = (expected, extracted, correct, wrong, review)
        if any(type(count) is not int or count < 0 for count in counts):
            raise HarnessFailure(f"invalid numeric-cell counts for {layout_id}")
        if correct + wrong != extracted or extracted + review != expected:
            raise HarnessFailure(f"numeric-cell counts do not reconcile for {layout_id}")
        wrong_total += wrong
    if wrong_total != 0:
        raise HarnessFailure(f"hard accuracy gate failed: EXTRACTED-but-wrong={wrong_total}")
    for layout_id, result in layout_metrics.items():
        correct = result.get("correct")
        total = result.get("total")
        if type(correct) is not int or type(total) is not int or total <= 0 or not 0 <= correct <= total:
            raise HarnessFailure(f"invalid synthetic layout-match counts for {layout_id}")
    return {
        "synthetic_only": True,
        "layout_match_accuracy_by_layout": layout_metrics,
        "numeric_exact_accuracy_by_layout": numeric_metrics,
        "extracted_but_wrong_total": wrong_total,
    }


def run(executable: Path | None = None) -> dict[str, Any]:
    pytest_output = _run_pytest()
    vector_report = verify_vectors(ROOT)
    print(f"E-72 vectors: PASS ({vector_report['vector_count']} synthetic vector(s))")

    # The O15 verifier exercises the source CLI on Ubuntu and the actual
    # one-folder executable when --exe is supplied on the Windows job.
    from verify_o15_e60 import verify as verify_o15

    verify_o15(executable)
    print("O15 synthetic CLI/evidence/label verification: PASS")

    from verify_e70_onboard import verify as verify_e70

    verify_e70(executable)
    onboarding_smoke = "FROZEN_PASS" if executable is not None else "SOURCE_PASS"
    print(f"E-70 onboarding smoke ({onboarding_smoke.lower()}): PASS")

    with tempfile.TemporaryDirectory(prefix="order16-layout-harness-") as raw_temp:
        metrics = _synthetic_metrics(Path(raw_temp))
    for layout_id in sorted(metrics["numeric_exact_accuracy_by_layout"]):
        layout = metrics["layout_match_accuracy_by_layout"][layout_id]
        numeric = metrics["numeric_exact_accuracy_by_layout"][layout_id]
        print(
            f"{layout_id}: layout_match={layout['correct']}/{layout['total']} "
            f"({layout['accuracy']:.1%}); numeric_exact={numeric['correct_fields']}/"
            f"{numeric['expected_fields']} ({numeric['accuracy']:.1%}); "
            f"EXTRACTED-but-wrong={numeric['extracted_but_wrong']}; "
            f"REVIEW/missing={numeric['review_or_missing_fields']}"
        )
    print("ORDER 16 hard gate: EXTRACTED-but-wrong=0")
    return {
        "schema_version": "e74.order16-harness-summary.v1",
        "synthetic_only": True,
        "python_test_suite": "PASS",
        "pytest_output_tail": "\n".join(pytest_output.splitlines()[-2:]),
        "o15_verifier": "PASS",
        "e70_onboarding_smoke": onboarding_smoke,
        "e72_vectors": vector_report,
        **metrics,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, help="optional frozen Windows one-folder executable")
    parser.add_argument("--summary-path", type=Path, help="optional path for the synthetic-only JSON summary")
    args = parser.parse_args(argv)
    try:
        summary = run(args.exe)
        if args.summary_path is not None:
            path = args.summary_path.expanduser().resolve(strict=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"Summary written: {path.name}")
    except Exception as exc:
        message = f"ORDER 16 harness FAILED: {type(exc).__name__}: {exc}"
        annotation = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=ORDER 16 Python harness::{annotation}")
        print(message, file=sys.stderr)
        return 1
    print("ORDER 16 Python harness: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
