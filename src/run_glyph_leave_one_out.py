#!/usr/bin/env python3
"""Run four-fold leave-one-invoice-out evaluation of the Glyph classifier.

The CLI evaluator remains the source of exact-cell, CER, arithmetic-gate, and
calibration metrics. This runner builds one template bank from three invoices
per fold, evaluates only the held-out invoice, and independently counts
EXTRACTED-but-wrong labeled cells from the evaluator's per-cell output.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
CELL_LINE = re.compile(
    r"^\s*(?P<field>[^|]+)\|(?P<preprocessing>[^|]+)\|raw=(?P<raw>.*?)"
    r"\|confidence=(?P<confidence>[0-9]+(?:\.[0-9]+)?)"
    r"\|status=(?P<status>[A-Z_]+)(?P<tail>.*)$"
)
REFERENCE_LINE = re.compile(
    r"\|reference=(?P<reference>.+?)"
    r"\|digits_match_reference=(?P<match>True|False)"
)
EXACT_METRIC = re.compile(
    r"metrics\.glyph\.exact_digit_cells=(?P<exact>\d+)/(?P<total>\d+) "
    r"digit_CER=(?P<cer>[0-9]+(?:\.[0-9]+)?)%"
)
GATE_METRIC = re.compile(r"arithmetic_gate passed=(?P<passed>True|False)")


@dataclass
class CellResult:
    field_name: str
    raw_value: str
    confidence: float
    status: str
    reference: str
    digits_match_reference: bool


@dataclass
class FoldResult:
    fold_id: str
    held_out_invoice: str
    template_count: int
    exact_digit_cells: int
    total_digit_cells: int
    digit_cer: float
    arithmetic_gate_passed: bool
    extracted_but_wrong: int
    cells_by_status: Counter[str]
    cells: list[CellResult]
    calibration_lines: list[str]
    build_command: str
    build_output: str
    evaluate_command: str
    evaluate_output: str
    edit_count: int
    reference_digit_count: int


def _digits_only(value: str) -> str:
    return "".join(character for character in value if character in PERSIAN_DIGITS)


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for index, left_character in enumerate(left, start=1):
        current = [index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(min(
                previous[right_index] + 1,
                current[right_index - 1] + 1,
                previous[right_index - 1] + (left_character != right_character),
            ))
        previous = current
    return previous[-1]


def _run_command(command: list[str], *, env: dict[str, str]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = completed.stdout
    if completed.stderr:
        if output and not output.endswith("\n"):
            output += "\n"
        output += completed.stderr
    return completed.returncode, output


def _cli_entry(invoice: dict[str, Any], labels_dir: Path) -> dict[str, Any]:
    image_path = (labels_dir / invoice["path"]).resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"invoice image does not exist: {image_path}")
    return {
        "path": str(image_path),
        "column_boundaries": invoice["column_boundaries"],
        "row_bands": invoice["row_bands"],
        "payable_bbox": invoice["payable_bbox"],
        "values": invoice["values"],
    }


def _write_cli_labels(path: Path, entries: list[dict[str, Any]]) -> None:
    payload = {
        "label_status": "OPERATOR_CONFIRMED",
        "images": entries,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _parse_evaluation(output: str) -> tuple[
    int, int, float, bool, int, Counter[str], list[CellResult], list[str], int, int
]:
    metric = EXACT_METRIC.search(output)
    if metric is None:
        raise ValueError("evaluate output did not contain exact-cell/CER metrics")
    gate = GATE_METRIC.search(output)
    if gate is None:
        raise ValueError("evaluate output did not contain an arithmetic-gate result")

    exact = int(metric.group("exact"))
    total = int(metric.group("total"))
    reported_cer = float(metric.group("cer"))
    cells: list[CellResult] = []
    status_counts: Counter[str] = Counter()
    extracted_but_wrong = 0
    edit_count = 0
    reference_digit_count = 0

    for line in output.splitlines():
        match = CELL_LINE.match(line)
        if match is None:
            continue
        reference_match = REFERENCE_LINE.search(match.group("tail"))
        if reference_match is None:
            continue
        try:
            raw_value = ast.literal_eval(match.group("raw"))
            reference = ast.literal_eval(reference_match.group("reference"))
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"could not parse evaluator cell line: {line}") from exc
        if not isinstance(raw_value, str) or not isinstance(reference, str):
            raise ValueError(f"evaluator returned non-string cell values: {line}")
        status = match.group("status")
        digits_match = reference_match.group("match") == "True"
        cell = CellResult(
            field_name=match.group("field").strip(),
            raw_value=raw_value,
            confidence=float(match.group("confidence")),
            status=status,
            reference=reference,
            digits_match_reference=digits_match,
        )
        cells.append(cell)
        status_counts[status] += 1
        if status == "EXTRACTED" and not digits_match:
            extracted_but_wrong += 1
        predicted_digits = _digits_only(raw_value)
        reference_digits = _digits_only(reference)
        edit_count += _edit_distance(predicted_digits, reference_digits)
        reference_digit_count += len(reference_digits)

    calibration_lines = [
        line for line in output.splitlines()
        if line.startswith("calibration.best_label_correct.")
        or line.startswith("calibration.best_label_wrong.")
    ]
    return (
        exact,
        total,
        reported_cer,
        gate.group("passed") == "True",
        extracted_but_wrong,
        status_counts,
        cells,
        calibration_lines,
        edit_count,
        reference_digit_count,
    )


def _template_count(path: Path) -> int:
    from image_extraction_adapter.glyph_classifier import GlyphTemplateSet

    templates = GlyphTemplateSet.load(path)
    return sum(sum(counts.values()) for counts in templates.counts().values())


def _run_fold(
    fold_index: int,
    held_out: dict[str, Any],
    training: list[dict[str, Any]],
    labels_dir: Path,
    env: dict[str, str],
) -> FoldResult:
    fold_id = f"fold-{fold_index}"
    with tempfile.TemporaryDirectory(prefix=f"glyph-loo-{held_out['id']}-") as temp:
        temp_dir = Path(temp)
        training_labels = temp_dir / "train-labels.json"
        test_labels = temp_dir / "test-labels.json"
        templates_path = temp_dir / "templates.json"
        _write_cli_labels(
            training_labels, [_cli_entry(item, labels_dir) for item in training])
        _write_cli_labels(test_labels, [_cli_entry(held_out, labels_dir)])

        build_args = [
            sys.executable,
            "-m",
            "image_extraction_adapter.glyph_classifier",
            "build",
            "--labels",
            str(training_labels),
            "--out",
            str(templates_path),
        ]
        build_code, build_output = _run_command(build_args, env=env)
        build_command = shlex.join(build_args)
        if build_code != 0:
            raise RuntimeError(
                f"{fold_id} build failed with exit code {build_code}\n{build_output}")
        if not templates_path.is_file():
            raise RuntimeError(f"{fold_id} build did not create {templates_path}")

        template_count = _template_count(templates_path)
        evaluate_args = [
            sys.executable,
            "-m",
            "image_extraction_adapter.glyph_classifier",
            "evaluate",
            "--labels",
            str(test_labels),
            "--templates",
            str(templates_path),
        ]
        # Deliberately do not pass --allow-leakage: the evaluator's guard stays on.
        evaluate_code, evaluate_output = _run_command(evaluate_args, env=env)
        evaluate_command = shlex.join(evaluate_args)
        if evaluate_code != 0:
            raise RuntimeError(
                f"{fold_id} evaluate failed with exit code {evaluate_code}\n"
                f"{evaluate_output}")
        if "LEAKAGE:" in evaluate_output:
            raise RuntimeError(f"{fold_id} unexpectedly reported template leakage")

        (
            exact,
            total,
            cer,
            gate_passed,
            extracted_but_wrong,
            status_counts,
            cells,
            calibration_lines,
            edit_count,
            reference_digit_count,
        ) = _parse_evaluation(evaluate_output)
        return FoldResult(
            fold_id=fold_id,
            held_out_invoice=str(held_out["id"]),
            template_count=template_count,
            exact_digit_cells=exact,
            total_digit_cells=total,
            digit_cer=cer,
            arithmetic_gate_passed=gate_passed,
            extracted_but_wrong=extracted_but_wrong,
            cells_by_status=status_counts,
            cells=cells,
            calibration_lines=calibration_lines,
            build_command=build_command,
            build_output=build_output,
            evaluate_command=evaluate_command,
            evaluate_output=evaluate_output,
            edit_count=edit_count,
            reference_digit_count=reference_digit_count,
        )


def _format_report(results: list[FoldResult]) -> str:
    total_exact = sum(result.exact_digit_cells for result in results)
    total_cells = sum(result.total_digit_cells for result in results)
    total_edits = sum(result.edit_count for result in results)
    total_reference_digits = sum(result.reference_digit_count for result in results)
    overall_cer = (
        100.0 * total_edits / total_reference_digits
        if total_reference_digits else 0.0
    )
    total_wrong = sum(result.extracted_but_wrong for result in results)
    all_folds_pass = all(result.extracted_but_wrong == 0 for result in results)

    lines = [
        "## T2 Leave-One-Out Evaluation Report",
        "",
        "### Methodology",
        "",
        "Four-fold leave-one-invoice-out evaluation. Each fold builds Glyph templates from all rows and numeric labels in the other three invoices, then evaluates the held-out invoice. The build and evaluate CLI are run in separate temporary label/template directories. The evaluate command does not receive `--allow-leakage`; the classifier's leakage guard remains enabled. Exact-cell/CER/arithmetic/calibration metrics come from the existing evaluator. EXTRACTED-but-wrong counts are computed from its per-cell status and `digits_match_reference` output.",
        "",
        "Payable value for invoice #31 is labeled `DERIVED_FROM_ARITHMETIC` as supplied by the operator. It is included in the fold metrics and gate checks, but is not an independent visual ground-truth label.",
        "",
        "### Results per Fold",
        "",
        "| fold | held_out | templates | exact_cells | total_cells | CER | gate_passed | extracted_but_wrong | cells_by_status |",
        "|---|---:|---:|---:|---:|---:|---|---:|---|",
    ]
    for result in results:
        status_text = ", ".join(
            f"{status}={count}" for status, count in sorted(result.cells_by_status.items())
        ) or "none"
        lines.append(
            f"| {result.fold_id} | {result.held_out_invoice} | {result.template_count} "
            f"| {result.exact_digit_cells} | {result.total_digit_cells} "
            f"| {result.digit_cer:.2f}% | {result.arithmetic_gate_passed} "
            f"| {result.extracted_but_wrong} | {status_text} |"
        )
    lines.extend([
        "",
        "### Total",
        "",
        "| fold | held_out | templates | exact_cells | total_cells | CER | gate_passed | extracted_but_wrong |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
        f"| TOTAL | 4-fold | — | {total_exact} | {total_cells} | {overall_cer:.2f}% | "
        f"{sum(result.arithmetic_gate_passed for result in results)}/4 | {total_wrong} |",
        "",
        "### Calibration Lines",
        "",
    ])
    for result in results:
        lines.append(f"#### {result.fold_id} (held-out #{result.held_out_invoice})")
        if result.calibration_lines:
            lines.extend(f"`{line}`" for line in result.calibration_lines)
        else:
            lines.append("No calibration lines were emitted by the evaluator.")
        lines.append("")
    lines.extend([
        "### Known Limitations",
        "",
        "- Payable templates only built successfully from 1 invoice (5.png / #32). Other invoices' payable crops had component-count mismatches. Payable cells are REVIEW in most folds.",
        "- 31.png payable label is DERIVED_FROM_ARITHMETIC, not directly operator-confirmed from the image.",
        "- Tesseract binary not available; full-page OCR path not tested.",
        "- The reported cell coverage is limited to cells emitted by the projection/cropper and evaluator. REVIEW cells are not counted as EXTRACTED-but-wrong.",
        "",
        "### Acceptance",
        "",
        f"EXTRACTED-but-wrong = 0 in all 4 folds: {'PASS' if all_folds_pass else 'FAIL'}",
    ])
    if not all_folds_pass:
        for result in results:
            if result.extracted_but_wrong:
                lines.append(f"- Fold {result.fold_id}, invoice #{result.held_out_invoice}:")
                for cell in result.cells:
                    if cell.status == "EXTRACTED" and not cell.digits_match_reference:
                        lines.append(
                            f"  - {cell.field_name}: glyph={cell.raw_value!r}; "
                            f"reference={cell.reference!r}; confidence={cell.confidence:.1f}; "
                            f"status={cell.status}"
                        )
    lines.extend([
        "",
        "### Raw Fold Output",
        "",
        "The following are the complete build/evaluate commands and their combined stdout/stderr for every fold.",
        "",
    ])
    for result in results:
        lines.extend([
            f"#### {result.fold_id}: build (held-out #{result.held_out_invoice})",
            "",
            f"`{result.build_command}`",
            "",
            "```text",
            result.build_output.rstrip(),
            "```",
            "",
            f"#### {result.fold_id}: evaluate (held-out #{result.held_out_invoice})",
            "",
            f"`{result.evaluate_command}`",
            "",
            "```text",
            result.evaluate_output.rstrip(),
            "```",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    labels_path = args.labels.resolve()
    labels_dir = labels_path.parent
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    invoices = data.get("invoices")
    if data.get("label_status") != "OPERATOR_CONFIRMED":
        raise ValueError("labels.json must have label_status=OPERATOR_CONFIRMED")
    if not isinstance(invoices, list) or len(invoices) != 4:
        raise ValueError("labels.json must contain exactly four invoices")
    if len({str(item.get("id")) for item in invoices}) != 4:
        raise ValueError("invoice IDs in labels.json must be unique")

    env = os.environ.copy()
    source_path = str(REPO_ROOT / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_path if not existing_pythonpath
        else source_path + os.pathsep + existing_pythonpath
    )

    results: list[FoldResult] = []
    for index, held_out in enumerate(invoices, start=1):
        training = [invoice for invoice in invoices if invoice is not held_out]
        print(f"=== {held_out['id']} fold: build from {len(training)} invoices ===")
        result = _run_fold(index, held_out, training, labels_dir, env)
        print(f"$ {result.build_command}")
        print(result.build_output, end="" if result.build_output.endswith("\n") else "\n")
        print(f"=== {held_out['id']} fold: evaluate ===")
        print(f"$ {result.evaluate_command}")
        print(result.evaluate_output, end="" if result.evaluate_output.endswith("\n") else "\n")
        status_text = ", ".join(
            f"{status}={count}" for status, count in sorted(result.cells_by_status.items())
        ) or "none"
        print(
            f"fold_id={result.fold_id} held_out_invoice={result.held_out_invoice} "
            f"template_count={result.template_count} "
            f"exact_digit_cells={result.exact_digit_cells} "
            f"total_digit_cells={result.total_digit_cells} "
            f"digit_CER={result.digit_cer:.2f}% "
            f"arithmetic_gate_passed={result.arithmetic_gate_passed} "
            f"extracted_but_wrong={result.extracted_but_wrong} "
            f"cells_by_status={status_text}"
        )
        results.append(result)

    report = _format_report(results)
    output_path = args.output
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print("=== REPORT ===")
    print(report, end="")

    if any(result.extracted_but_wrong for result in results):
        print("ACCEPTANCE=FAIL; no threshold changes made", file=sys.stderr)
    else:
        print("ACCEPTANCE=PASS")
    print(f"report_path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
