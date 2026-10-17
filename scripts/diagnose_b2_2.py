#!/usr/bin/env python3
"""Measure the payable-only vertical-rule-removal change and run four-fold LOO.

The controls compare the current default morphology against the proposed
payable-tagged path on the supplied real fixtures. Glyph component filtering is
reused unchanged from the B2-1 diagnostic, including its width/height hairline
rule. Leave-one-invoice-out folds are executed by the existing evaluator
runner; this script adds per-class reporting without changing the classifier.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = REPO_ROOT / "tests" / "fixtures" / "real" / "labels.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "b2-2-payable-preprocessing-report.md"
CLASS_NAMES = ("total", "quantity", "payable")

for import_root in (REPO_ROOT / "src", REPO_ROOT / "scripts"):
    resolved = str(import_root)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)

from PIL import Image  # noqa: E402
import run_glyph_leave_one_out as loo  # noqa: E402
from diagnose_payable import (  # noqa: E402
    RULE_MAX_WIDTH,
    RULE_MIN_HEIGHT_RATIO,
    _expected_symbol_count,
    connected_components,
)
from image_extraction_adapter.preprocessing import (  # noqa: E402
    crop_spatial_cells,
    otsu_binarize,
    preprocess_cell,
    remove_morphological_table_lines,
)


@dataclass(frozen=True)
class CellControl:
    invoice_id: str
    field_name: str
    cell_class: str
    height: int
    vertical_kernel: int
    before_components: int
    after_components: int
    expected_components: int
    before_removed_pixels: int
    after_removed_pixels: int
    pixels_changed: bool


def _field_class(field_name: str) -> str | None:
    if field_name == "invoice.payable":
        return "payable"
    if field_name.endswith(".total"):
        return "total"
    if field_name.endswith(".quantity"):
        return "quantity"
    return None


def _effective_vertical_kernel(height: int) -> int:
    kernel = max(15, int(height * 0.55))
    return kernel + (kernel % 2 == 0)


def _spatial_from_entry(entry: dict[str, Any]) -> SimpleNamespace:
    payable_bbox = entry.get("payable_bbox")
    assessments = ()
    if payable_bbox:
        assessments = (SimpleNamespace(
            field_name="invoice.payable",
            bbox=tuple(payable_bbox),
            status=None,
        ),)
    return SimpleNamespace(
        column_boundaries=tuple(entry.get("column_boundaries", ())),
        row_bands=tuple(tuple(band) for band in entry.get("row_bands", ())),
        assessments=assessments,
    )


def _measure_controls(
    entries: list[dict[str, Any]], labels_path: Path
) -> list[CellControl]:
    controls: list[CellControl] = []
    for entry in entries:
        image_path = (labels_path.parent / entry["path"]).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"fixture image does not exist: {image_path}")
        with Image.open(image_path) as opened:
            opened.load()
            source = opened.convert("RGB")
        crops = crop_spatial_cells(
            source,
            _spatial_from_entry(entry),
            include_descriptions=False,
            include_payable=True,
            horizontal_inset=int(entry.get("horizontal_inset", 4)),
        )
        values = entry.get("values", {})
        for crop in crops:
            cell_class = _field_class(crop.field_name)
            if cell_class is None or crop.field_name not in values:
                continue
            old_image, old_removed = remove_morphological_table_lines(
                otsu_binarize(crop.image),
                skip_vertical_rule_removal=False,
            )
            new_result = preprocess_cell(crop.image, "otsu")
            controls.append(CellControl(
                invoice_id=str(entry["id"]),
                field_name=crop.field_name,
                cell_class=cell_class,
                height=crop.image.height,
                vertical_kernel=_effective_vertical_kernel(crop.image.height),
                before_components=len(connected_components(old_image)),
                after_components=len(connected_components(new_result.image)),
                expected_components=_expected_symbol_count(str(values[crop.field_name])),
                before_removed_pixels=old_removed,
                after_removed_pixels=new_result.line_pixels_removed,
                pixels_changed=old_image.tobytes() != new_result.image.tobytes(),
            ))
    return controls


def _run_leave_one_out(
    entries: list[dict[str, Any]], labels_path: Path
) -> list[loo.FoldResult]:
    env = os.environ.copy()
    source_path = str(REPO_ROOT / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_path if not existing_pythonpath
        else source_path + os.pathsep + existing_pythonpath
    )
    labels_dir = labels_path.parent
    results: list[loo.FoldResult] = []
    for index, held_out in enumerate(entries, start=1):
        training = [item for item in entries if item is not held_out]
        print(f"Running fold {index}/4; held-out invoice #{held_out['id']}...")
        results.append(loo._run_fold(
            index, held_out, training, labels_dir, env))
    return results


def _fold_cell_metrics(results: list[loo.FoldResult]) -> dict[str, dict[str, int]]:
    totals: dict[str, Counter[str]] = {
        name: Counter() for name in CLASS_NAMES
    }
    for result in results:
        for cell in result.cells:
            cell_class = _field_class(cell.field_name)
            if cell_class is None:
                continue
            totals[cell_class]["cells"] += 1
            totals[cell_class]["exact"] += int(cell.digits_match_reference)
            totals[cell_class]["extracted_wrong"] += int(
                cell.status == "EXTRACTED" and not cell.digits_match_reference)
            totals[cell_class][f"status_{cell.status}"] += 1
    return {name: dict(counts) for name, counts in totals.items()}


def _pairs_for_class(
    controls: list[CellControl], invoice_id: str, cell_class: str
) -> str:
    entries = [
        item for item in controls
        if item.invoice_id == invoice_id and item.cell_class == cell_class
    ]
    return ", ".join(
        f"{item.field_name.rsplit('.', 1)[0] if item.field_name != 'invoice.payable' else 'payable'} "
        f"{item.height}px/{item.vertical_kernel}px"
        for item in entries
    ) or "—"


def _format_report(
    entries: list[dict[str, Any]],
    controls: list[CellControl],
    results: list[loo.FoldResult],
    command: str,
) -> tuple[str, bool]:
    controls_by_class = {
        name: [item for item in controls if item.cell_class == name]
        for name in CLASS_NAMES
    }
    mismatches_before = {
        name: sum(item.before_components != item.expected_components
                  for item in items)
        for name, items in controls_by_class.items()
    }
    mismatches_after = {
        name: sum(item.after_components != item.expected_components
                  for item in items)
        for name, items in controls_by_class.items()
    }
    changed_by_class = {
        name: sum(item.pixels_changed for item in items)
        for name, items in controls_by_class.items()
    }
    fold_metrics = _fold_cell_metrics(results)
    gate_passes = sum(result.arithmetic_gate_passed for result in results)
    extracted_wrong = sum(result.extracted_but_wrong for result in results)
    payable_after_match = all(
        item.after_components == item.expected_components
        for item in controls_by_class["payable"]
    )
    row_controls_unchanged = (
        changed_by_class["total"] == 0 and changed_by_class["quantity"] == 0
    )
    payable_component_coverage = {
        item.invoice_id: item.after_components == item.expected_components
        for item in controls_by_class["payable"]
    }
    payable_statuses: dict[str, str] = {}
    for result in results:
        cell = next((item for item in result.cells
                     if item.field_name == "invoice.payable"), None)
        if cell is not None:
            payable_statuses[result.held_out_invoice] = cell.status
    all_covered_payables_extracted = all(
        not covered or payable_statuses.get(invoice_id) == "EXTRACTED"
        for invoice_id, covered in payable_component_coverage.items()
    )
    no_wrong_extractions = extracted_wrong == 0
    gate_acceptance = gate_passes >= 3
    acceptance = (
        row_controls_unchanged
        and payable_after_match
        and no_wrong_extractions
        and gate_acceptance
        and all_covered_payables_extracted
    )

    lines = [
        "# B2-2 — Payable-only vertical-rule removal",
        "",
        "## Scope and method",
        "",
        "The production change keeps the existing Otsu/adaptive thresholds and the existing vertical-kernel formula (`max(15, int(cell_height * 0.55))`, rounded up to an odd length by the morphology helper). Crops are tagged by class; only `invoice.payable` skips the vertical-rule mask. Horizontal-rule removal remains enabled. The skip flag defaults to `False`, so untagged crops and direct calls retain prior behavior.",
        "",
        f"The unchanged glyph hairline filter remains `width <= {RULE_MAX_WIDTH}px` and `height >= {RULE_MIN_HEIGHT_RATIO:.1f} * cell height`; `glyph_classifier.py` was not modified. Component counts use the B2-1 diagnostic's same 8-connected, minimum-size, hairline-filter, and x-overlap-merge logic. Expected counts include digit and comma/separator glyphs from the confirmed labels.",
        "",
        f"Reproduction command: `{command}`",
        "",
        "## PM crop geometry",
        "",
        "For each row cell, the listed `height/kernel` pairs are in row order. Total and quantity crops use the same row-band height but are listed separately as requested. All measured row kernels are compared with the approximately 24px digit height from the diagnosis.",
        "",
        "| invoice | payable height/kernel | row total height/kernel | quantity height/kernel | row kernels > ~24px |",
        "|---|---:|---|---|---|",
    ]
    for entry in entries:
        invoice_id = str(entry["id"])
        payable = _pairs_for_class(controls, invoice_id, "payable")
        totals = _pairs_for_class(controls, invoice_id, "total")
        quantities = _pairs_for_class(controls, invoice_id, "quantity")
        row_records = [
            item for item in controls
            if item.invoice_id == invoice_id and item.cell_class in {"total", "quantity"}
        ]
        row_exceeds = bool(row_records) and all(
            item.vertical_kernel > 24 for item in row_records)
        lines.append(
            f"| {invoice_id} | {payable} | {totals} | {quantities} | "
            f"{'yes' if row_exceeds else 'no'} |"
        )

    lines.extend([
        "",
        "## Component-count controls (before → after)",
        "",
        "`pixels changed` compares the complete preprocessed binary bytes. The total/quantity controls must remain byte-identical; payable output may differ only when the old vertical mask removed foreground.",
        "",
        "| class | cells | mismatches before | mismatches after | cells with pixel changes |",
        "|---|---:|---:|---:|---:|",
    ])
    for name in CLASS_NAMES:
        items = controls_by_class[name]
        lines.append(
            f"| {name} | {len(items)} | {mismatches_before[name]} "
            f"| {mismatches_after[name]} | {changed_by_class[name]} |"
        )
    lines.extend([
        "",
        "### Per-cell controls",
        "",
        "| invoice | class | field | crop h | vertical kernel | components before → after | expected | pixels changed | removed px before → after |",
        "|---|---|---|---:|---:|---:|---:|---|---:|",
    ])
    for item in controls:
        lines.append(
            f"| {item.invoice_id} | {item.cell_class} | `{item.field_name}` "
            f"| {item.height} | {item.vertical_kernel} "
            f"| {item.before_components} → {item.after_components} "
            f"| {item.expected_components} | {'yes' if item.pixels_changed else 'no'} "
            f"| {item.before_removed_pixels} → {item.after_removed_pixels} |"
        )

    lines.extend([
        "",
        "## Four-fold leave-one-invoice-out results",
        "",
        "Each fold trained templates on the other three fixture invoices and evaluated the held-out invoice through the existing CLI evaluator. No leakage override or threshold changes were used.",
        "",
        "| class | component-count mismatches before → after | exact digit cells | EXTRACTED-but-wrong | statuses |",
        "|---|---:|---:|---:|---|",
    ])
    for name in CLASS_NAMES:
        metrics = fold_metrics[name]
        status_text = ", ".join(
            f"{key.removeprefix('status_')}={count}"
            for key, count in sorted(metrics.items()) if key.startswith("status_")
        ) or "none"
        lines.append(
            f"| {name} | {mismatches_before[name]}/{len(controls_by_class[name])} "
            f"→ {mismatches_after[name]}/{len(controls_by_class[name])} "
            f"| {metrics.get('exact', 0)}/{metrics.get('cells', 0)} "
            f"| {metrics.get('extracted_wrong', 0)} | {status_text} |"
        )
    lines.extend([
        "",
        "### Fold-by-fold",
        "",
        "| fold | held-out | total exact | quantity exact | payable exact/status | gate passed | EXTRACTED-but-wrong |",
        "|---|---:|---:|---:|---|---|---:|",
    ])
    for result in results:
        counts: dict[str, tuple[int, int]] = {}
        for name in ("total", "quantity"):
            class_cells = [cell for cell in result.cells
                           if _field_class(cell.field_name) == name]
            counts[name] = (
                sum(cell.digits_match_reference for cell in class_cells),
                len(class_cells),
            )
        payable = next((cell for cell in result.cells
                        if cell.field_name == "invoice.payable"), None)
        payable_metric = (
            f"{int(payable.digits_match_reference)}/1, {payable.status}"
            if payable is not None else "no payable cell"
        )
        lines.append(
            f"| {result.fold_id} | {result.held_out_invoice} "
            f"| {counts['total'][0]}/{counts['total'][1]} "
            f"| {counts['quantity'][0]}/{counts['quantity'][1]} "
            f"| {payable_metric} | {result.arithmetic_gate_passed} "
            f"| {result.extracted_but_wrong} |"
        )

    lines.extend([
        "",
        "### Acceptance checks",
        "",
        f"- Total and quantity preprocessed bytes unchanged: {'PASS' if row_controls_unchanged else 'FAIL'} ({changed_by_class['total']} total and {changed_by_class['quantity']} quantity cells changed).",
        f"- Payable component counts match labels after the fix: {'PASS' if payable_after_match else 'FAIL'} ({mismatches_after['payable']}/{len(controls_by_class['payable'])} mismatches).",
        f"- EXTRACTED-but-wrong is zero: {'PASS' if no_wrong_extractions else 'FAIL'} ({extracted_wrong}).",
        f"- Arithmetic gates pass at least 3/4 folds: {'PASS' if gate_acceptance else 'FAIL'} ({gate_passes}/4).",
        f"- Every component-covered payable is EXTRACTED: {'PASS' if all_covered_payables_extracted else 'FAIL'}.",
        f"- Overall B2-2 diagnostics: {'PASS' if acceptance else 'FAIL'}.",
        "",
        "## Per-fold payable statuses",
        "",
        "| invoice | expected components | post-fix components | component coverage | LOO status |",
        "|---|---:|---:|---|---|",
    ])
    for item in controls_by_class["payable"]:
        covered = item.after_components == item.expected_components
        lines.append(
            f"| {item.invoice_id} | {item.expected_components} | "
            f"{item.after_components} | {'yes' if covered else 'no'} | "
            f"{payable_statuses.get(item.invoice_id, 'missing')} |"
        )
    lines.extend([
        "",
        "## Summary",
        "",
        "The payable-only behavior is carried from `crop_spatial_cells()` through Pillow image metadata to `preprocess_cell()`, avoiding any change to the frozen glyph-classifier caller. No bbox/Tesseract, HTTP, real-image adapter extraction, or glyph-classifier code was changed.",
        "",
    ])
    return "\n".join(lines), acceptance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    labels_path = args.labels.resolve()
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    if payload.get("label_status") != "OPERATOR_CONFIRMED":
        raise ValueError("labels file must have label_status=OPERATOR_CONFIRMED")
    entries = payload.get("invoices")
    if not isinstance(entries, list) or len(entries) != 4:
        raise ValueError("labels file must contain exactly four fixture invoices")

    controls = _measure_controls(entries, labels_path)
    results = _run_leave_one_out(entries, labels_path)
    output_path = args.output.resolve()
    command = (
        f"{sys.executable} {Path(__file__).relative_to(REPO_ROOT)} "
        f"--labels {labels_path.relative_to(REPO_ROOT)} "
        f"--output {output_path.relative_to(REPO_ROOT)}"
    )
    report, accepted = _format_report(entries, controls, results, command)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"report_path={output_path}")
    print(f"ACCEPTANCE={'PASS' if accepted else 'FAIL'}")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
