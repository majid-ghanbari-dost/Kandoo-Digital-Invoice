"""E-71 per-layout numbers report — PY-B backlog item 2 (PM-36).

Renders the three explicitly synthetic E-71 print layouts (one training and
one holdout invoice per layout), measures per-layout layout-match accuracy and
numeric-cell exact accuracy, enforces the EXTRACTED-but-wrong = 0 hard gate,
and emits a machine-readable numbers report. EVERYTHING here is synthetic and
the report says so in every row; these numbers describe generator/harness
mechanics only and are never presented as real-data extraction accuracy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from image_extraction_adapter.synthetic_layouts import (  # noqa: E402
    measure_layout_match_accuracy,
    measure_synthetic_numeric_accuracy_by_layout,
    render_synthetic_invoice,
    synthetic_layouts,
)

SCHEMA_VERSION = "e71.per-layout-numbers.v1"


class E71GateFailure(RuntimeError):
    pass


def collect_per_layout_numbers(temp_root: Path) -> dict[str, Any]:
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
    declared = {profile.layout_id for profile in profiles}
    if set(layout_metrics) != declared or set(numeric_metrics) != declared:
        raise E71GateFailure("per-layout metrics must cover every declared layout exactly")

    rows: list[dict[str, Any]] = []
    wrong_total = 0
    for profile in sorted(profiles, key=lambda item: item.layout_id):
        layout_id = profile.layout_id
        layout = layout_metrics[layout_id]
        numeric = numeric_metrics[layout_id]
        counts = (
            numeric["expected_fields"], numeric["extracted_fields"],
            numeric["correct_fields"], numeric["extracted_but_wrong"],
            numeric["review_or_missing_fields"],
        )
        if any(type(count) is not int or count < 0 for count in counts):
            raise E71GateFailure(f"invalid numeric-cell counts for {layout_id}")
        if numeric["correct_fields"] + numeric["extracted_but_wrong"] != numeric["extracted_fields"]:
            raise E71GateFailure(f"numeric-cell counts do not reconcile for {layout_id}")
        if numeric["extracted_fields"] + numeric["review_or_missing_fields"] != numeric["expected_fields"]:
            raise E71GateFailure(f"numeric-cell coverage does not reconcile for {layout_id}")
        wrong_total += numeric["extracted_but_wrong"]
        rows.append({
            "layout_id": layout_id,
            "layout_profile": {
                "column_boundaries": list(profile.column_boundaries),
                "logo_size": list(profile.logo_size),
                "currency_label": profile.currency_label,
            },
            "layout_match": {
                "correct": layout["correct"],
                "total": layout["total"],
                "accuracy": layout["accuracy"],
                "expected_template_id": layout["expected_template_id"],
                "matched_template_id": layout["matched_template_id"],
            },
            "numeric_cell_exact": {
                "expected_fields": numeric["expected_fields"],
                "extracted_fields": numeric["extracted_fields"],
                "correct_fields": numeric["correct_fields"],
                "extracted_but_wrong": numeric["extracted_but_wrong"],
                "review_or_missing_fields": numeric["review_or_missing_fields"],
                "accuracy": numeric["accuracy"],
            },
        })

    if wrong_total != 0:
        raise E71GateFailure(f"hard accuracy gate failed: EXTRACTED-but-wrong={wrong_total}")

    return {
        "schema_version": SCHEMA_VERSION,
        "synthetic_only": True,
        "honesty_label": (
            "SYNTHETIC/FICTIONAL — generator mechanics only. Every raster is stamped "
            "'SYNTHETIC INVOICE' on-image; these numbers are NOT real-data extraction "
            "accuracy and make no claim about real invoices."
        ),
        "gate": {
            "name": "EXTRACTED-but-wrong = 0",
            "extracted_but_wrong_total": wrong_total,
            "result": "PASS",
        },
        "layouts": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None, help="write the numbers report JSON here")
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(prefix="e71-per-layout-") as raw_temp:
            report = collect_per_layout_numbers(Path(raw_temp))
    except E71GateFailure as exc:
        message = f"E-71 per-layout numbers FAILED: {exc}"
        annotation = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=E-71 per-layout::{annotation}")
        print(message, file=sys.stderr)
        return 1
    if args.output:
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"E-71 per-layout numbers ({report['schema_version']}):")
    for row in report["layouts"]:
        layout = row["layout_match"]
        numeric = row["numeric_cell_exact"]
        print(
            f"  {row['layout_id']}: layout_match={layout['correct']}/{layout['total']} "
            f"({layout['accuracy']:.1%}); numeric_exact={numeric['correct_fields']}/"
            f"{numeric['expected_fields']} ({numeric['accuracy']:.1%}); "
            f"EXTRACTED-but-wrong={numeric['extracted_but_wrong']}; "
            f"REVIEW/missing={numeric['review_or_missing_fields']}"
        )
    print(f"gate: {report['gate']['name']} -> {report['gate']['result']}")
    print("honesty: SYNTHETIC/FICTIONAL — not real-data accuracy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
