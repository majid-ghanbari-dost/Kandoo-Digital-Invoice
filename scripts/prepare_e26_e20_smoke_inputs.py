#!/usr/bin/env python3
"""Materialize JSON-only E-20 inputs for the E-26 CLI smoke.

No page is rendered here. Geometry and OCR readings are taken from the checked-in
E-20 report; expected numeric labels come from the frozen E-03 v3 answer key.
The Canonical object is a mechanics-only projection and is never a production
invoice or evidence of real-store recognition.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from e05_template_bank import parse_labeled_integer  # noqa: E402
from image_extraction_adapter.canonical_invoice import validate_canonical_invoice  # noqa: E402
from image_extraction_adapter.onboarding_cli import (  # noqa: E402
    E20_STORE_ID,
    build_e20_observations,
    build_e20_pipeline_observation,
)


E20_REPORT = ROOT / "docs" / "e20-second-store.json"
E03_EXPECTED = ROOT / "docs" / "E-03-kit-v3" / "expected-values.json"
CANONICAL_TEMPLATE = ROOT / "tests" / "fixtures" / "real" / "canonical" / "canonical-29.json"


def build_e20_canonical_candidate(base: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    """Create a schema-valid, explicitly synthetic exam candidate for E-08 tests."""
    candidate = copy.deepcopy(base)
    candidate["invoice_id"] = "e26-e20-exam-invoice"
    candidate["display_number"] = "E20-EXAM"
    candidate["operation_id"] = "e26-e20-exam-operation"
    candidate["device_id"] = "e20-synthetic-second-store-device"
    candidate["store_id"] = E20_STORE_ID
    candidate["customer"]["phone"] = "+15550000000"
    candidate["attention_cells"] = []

    quantities = [parse_labeled_integer(value) for value in values["quantities"]]
    line_totals = [parse_labeled_integer(value) for value in values["line_totals"]]
    if len(quantities) != len(line_totals) or not quantities:
        raise ValueError("E-03 exam quantities and line totals must have the same non-zero length")
    items: list[dict[str, Any]] = []
    line_provenance: list[dict[str, str]] = []
    for index, (quantity, line_total) in enumerate(zip(quantities, line_totals, strict=True)):
        if quantity <= 0 or line_total % quantity:
            raise ValueError(f"E-03 exam line {index} has no exact integer unit price")
        items.append({
            "product_name": f"Synthetic E20 item {index + 1}",
            "quantity": quantity,
            "unit_price": line_total // quantity,
            "line_total": line_total,
        })
        line_provenance.append({
            "product_name": "captured",
            "quantity": "captured",
            "unit_price": "derived",
            "line_total": "captured",
        })
    subtotal = sum(line_totals)
    payable = parse_labeled_integer(values["payable"])
    if subtotal != payable:
        raise ValueError("E-03 exam payable does not equal the exact sum of line totals")
    candidate["line_items"] = items
    candidate["summary"]["subtotal"] = subtotal
    candidate["summary"]["extra_amounts"] = {}
    candidate["summary"]["payable"] = payable

    candidate["state_history"][0]["operation_id"] = candidate["operation_id"]
    candidate["state_history"][0]["device_id"] = candidate["device_id"]
    provenance = candidate["provenance"]
    provenance["image_sha256"] = None
    fields = provenance["fields"]
    fields["customer"]["phone"] = "captured"
    fields["line_items"] = line_provenance
    fields["summary"]["subtotal"] = "derived"
    fields["summary"]["payable"] = "captured"

    valid, errors = validate_canonical_invoice(candidate)
    if not valid:
        raise ValueError(f"generated E-20 mechanics candidate fails Canonical v0 validation: {errors}")
    return candidate


def prepare_e26_e20_inputs(repo_root: Path, output_dir: Path) -> dict[str, Path]:
    """Write the deterministic, test-only observation and candidate JSON files."""
    repo_root = repo_root.resolve()
    output_dir = output_dir.resolve()
    report_path = repo_root / "docs" / "e20-second-store.json"
    expected_path = repo_root / "docs" / "E-03-kit-v3" / "expected-values.json"
    template_path = repo_root / "tests" / "fixtures" / "real" / "canonical" / "canonical-29.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    base_invoice = json.loads(template_path.read_text(encoding="utf-8"))

    observations = build_e20_observations(report_path, expected_path)
    exam_observation = observations["exam"]
    pipeline_observation = build_e20_pipeline_observation(report_path, expected_path)
    candidate_invoice = build_e20_canonical_candidate(base_invoice, expected["exam"])
    shifted_columns = tuple(value + 30.0 for value in exam_observation.column_boundaries)
    if shifted_columns[-1] > exam_observation.image_width:
        raise ValueError("E-20 shifted-layout fixture exceeds the synthetic page width")
    new_layout_observation = exam_observation.__class__(
        source_id="e20-synthetic-new-layout",
        image_width=exam_observation.image_width,
        image_height=exam_observation.image_height,
        column_boundaries=shifted_columns,
        row_bands=exam_observation.row_bands,
        payable_bbox=exam_observation.payable_bbox,
        field_values=exam_observation.field_values,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    values = {
        "candidate_invoice": candidate_invoice,
        "exam_observation": exam_observation.to_dict(),
        "pipeline_observation": pipeline_observation.to_dict(),
        "new_layout_observation": new_layout_observation.to_dict(),
        "store_id": E20_STORE_ID,
        "e20_status": report["status"],
    }
    paths: dict[str, Path] = {}
    for name, value in values.items():
        path = output_dir / f"{name.replace('_', '-')}.json"
        path.write_text(
            json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        paths[name] = path
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    created = prepare_e26_e20_inputs(args.repo_root, args.output_dir)
    for name, path in created.items():
        print(f"{name}={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
