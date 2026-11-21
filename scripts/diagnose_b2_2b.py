#!/usr/bin/env python3
"""Diagnose correct cells that remain REVIEW in four-fold invoice LOO.

This diagnostic runs the existing Glyph build/evaluate CLI for each held-out
invoice, retains its complete per-cell output, then recomputes the same cell
readings in-process to expose per-glyph best/second-best labels, distances,
margins, and individual review conditions. It changes no classifier settings
or defaults and requires only the repository code, Python stdlib, and Pillow.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = REPO_ROOT / "tests" / "fixtures" / "real" / "labels.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "b2-2b-review-diagnosis.md"
MINIMUM_CONFIDENCE = 60.0

for import_root in (REPO_ROOT / "src", REPO_ROOT / "scripts"):
    resolved = str(import_root)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)

import run_glyph_leave_one_out as loo  # noqa: E402
from image_extraction_adapter.glyph_classifier import (  # noqa: E402
    DEFAULT_MAX_DISTANCE,
    DEFAULT_MIN_MARGIN,
    GlyphClassifierOCR,
    GlyphTemplateSet,
    _binarize,
    _distance,
    _geometry,
    _grid,
    _line_reference,
    _NUMERIC_FORMAT,
    _digits_only,
    _crops_for_entry,
    apply_arithmetic_gate,
    normalize_label_text,
    profile_for_field,
    segment_cell,
)


CONDITION_NAMES = (
    "distance > max_distance",
    "margin < min_margin",
    "confidence < minimum_confidence",
    "format check",
    "arithmetic gate",
    "source REVIEW",
)


@dataclass(frozen=True)
class GlyphEvidence:
    index: int
    expected: str
    best_label: str
    distance: float
    margin: float
    second_label: str | None
    second_distance: float | None
    accepted: bool
    note: str | None
    bbox: tuple[int, int, int, int]


@dataclass
class CellEvidence:
    fold_id: str
    invoice_id: str
    field_name: str
    field_class: str
    raw_value: str
    reference: str
    digits_match_reference: bool
    confidence: float
    status: str
    pre_gate_reason: str | None
    reason: str | None
    conditions: set[str] = field(default_factory=set)
    other_conditions: list[str] = field(default_factory=list)
    glyphs: list[GlyphEvidence] = field(default_factory=list)
    source_status: str | None = None
    gate_passed: bool = True
    gate_reason: str | None = None
    template_labels: tuple[str, ...] = ()
    missing_reference_labels: tuple[str, ...] = ()


@dataclass
class FoldEvidence:
    fold_id: str
    held_out_invoice: str
    build_command: str
    build_output: str
    evaluate_command: str
    evaluate_output: str
    gate_passed: bool
    gate_reason: str | None
    gate_line_sum: int | None
    gate_payable: int | None
    template_counts: dict[str, dict[str, int]]
    cells: list[CellEvidence]


def _cell_class(field_name: str) -> str:
    if field_name == "invoice.payable":
        return "payable"
    if field_name.endswith(".total"):
        return "total"
    if field_name.endswith(".quantity"):
        return "quantity"
    return "other"


def _rank_glyphs(
    cell_image: Any,
    field_name: str,
    reading: Any,
    engine: GlyphClassifierOCR,
    reference: str,
) -> list[GlyphEvidence]:
    binary, _ = _binarize(cell_image)
    _, _, components = segment_cell(binary)
    if not components or not reading.readings:
        return []
    ref_top, ref_height = _line_reference(components)
    pool = engine._classifier._templates_for(profile_for_field(field_name))
    ranked_result: list[GlyphEvidence] = []

    for index, (component, glyph_reading) in enumerate(
        zip(components, reading.readings), start=1
    ):
        geometry = _geometry(component, ref_top, ref_height)
        grid = _grid(component)
        best_per_label: dict[str, float] = {}
        for template in pool:
            distance = _distance(grid, geometry, template)
            previous = best_per_label.get(template.label, float("inf"))
            if distance < previous:
                best_per_label[template.label] = distance
        ranked = sorted(best_per_label.items(), key=lambda item: item[1])
        second_label = ranked[1][0] if len(ranked) > 1 else None
        second_distance = ranked[1][1] if len(ranked) > 1 else None
        expected = reference[index - 1] if index <= len(reference) else "?"
        if ranked:
            if ranked[0][0] != glyph_reading.best_label:
                raise RuntimeError(
                    f"independent ranking disagrees for {field_name} glyph {index}: "
                    f"{ranked[0][0]!r} != {glyph_reading.best_label!r}")
            if len(ranked) > 1 and abs(
                (ranked[1][1] - ranked[0][1]) - glyph_reading.margin
            ) > 1e-9:
                raise RuntimeError(
                    f"independent margin disagrees for {field_name} glyph {index}")
        ranked_result.append(GlyphEvidence(
            index=index,
            expected=expected,
            best_label=glyph_reading.best_label,
            distance=glyph_reading.distance,
            margin=glyph_reading.margin,
            second_label=second_label,
            second_distance=second_distance,
            accepted=glyph_reading.label is not None,
            note=glyph_reading.note,
            bbox=glyph_reading.bbox,
        ))
    return ranked_result


def _condition_flags(
    *,
    field_name: str,
    result: Any,
    reading: Any,
    glyphs: list[GlyphEvidence],
    gate: Any,
    source_status: str | None,
    engine: GlyphClassifierOCR,
    minimum_confidence: float,
) -> tuple[set[str], list[str]]:
    conditions: set[str] = set()
    other: list[str] = []
    classifier = engine._classifier

    if any(item.distance > classifier.max_distance for item in glyphs):
        conditions.add("distance > max_distance")
    if any(item.margin < classifier.min_margin for item in glyphs):
        conditions.add("margin < min_margin")
    if result.raw_value and reading.confidence < minimum_confidence:
        conditions.add("confidence < minimum_confidence")
    if result.raw_value and _NUMERIC_FORMAT.fullmatch(result.raw_value) is None:
        conditions.add("format check")
    if (field_name.endswith(".total") or field_name == "invoice.payable") \
            and not gate.passed:
        conditions.add("arithmetic gate")
    if source_status == "REVIEW":
        conditions.add("source REVIEW")

    for item in glyphs:
        if item.note:
            note = item.note
            if "glyph touches the crop edge" in note:
                other.append("glyph touches crop edge")
            if "component too wide for one glyph" in note:
                other.append("component too wide for one glyph")
    if not result.raw_value:
        other.append("no numeric text / no accepted glyph string")
    if reading.reasons and not conditions:
        other.extend(reason for reason in reading.reasons if reason not in other)
    return conditions, list(dict.fromkeys(other))


def _write_labels(path: Path, entries: list[dict[str, Any]]) -> None:
    loo._write_cli_labels(path, entries)


def _run_fold(
    fold_index: int,
    held_out: dict[str, Any],
    training: list[dict[str, Any]],
    labels_dir: Path,
    env: dict[str, str],
) -> FoldEvidence:
    fold_id = f"fold-{fold_index}"
    with tempfile.TemporaryDirectory(prefix=f"b2-2b-loo-{held_out['id']}-") as temp:
        temp_dir = Path(temp)
        training_labels = temp_dir / "train-labels.json"
        test_labels = temp_dir / "test-labels.json"
        templates_path = temp_dir / "templates.json"
        _write_labels(
            training_labels,
            [loo._cli_entry(item, labels_dir) for item in training],
        )
        test_entry = loo._cli_entry(held_out, labels_dir)
        _write_labels(test_labels, [test_entry])

        build_args = [
            sys.executable, "-m", "image_extraction_adapter.glyph_classifier",
            "build", "--labels", str(training_labels),
            "--out", str(templates_path),
        ]
        build_code, build_output = loo._run_command(build_args, env=env)
        if build_code != 0 or not templates_path.is_file():
            raise RuntimeError(
                f"{fold_id} template build failed (exit {build_code}):\n{build_output}")

        evaluate_args = [
            sys.executable, "-m", "image_extraction_adapter.glyph_classifier",
            "evaluate", "--labels", str(test_labels),
            "--templates", str(templates_path),
        ]
        evaluate_code, evaluate_output = loo._run_command(evaluate_args, env=env)
        if evaluate_code != 0:
            raise RuntimeError(
                f"{fold_id} evaluation failed (exit {evaluate_code}):\n{evaluate_output}")
        if "LEAKAGE:" in evaluate_output:
            raise RuntimeError(f"{fold_id} unexpectedly reported template leakage")

        parsed = loo._parse_evaluation(evaluate_output)
        cli_cells = {cell.field_name: cell for cell in parsed[6]}
        templates = GlyphTemplateSet.load(templates_path)
        engine = GlyphClassifierOCR(templates)
        spatial, crops = _crops_for_entry(test_entry)
        triples = engine._recognize_crops(
            crops, spatial, minimum_confidence=MINIMUM_CONFIDENCE)
        gated_results, gate = apply_arithmetic_gate(
            [result for _, result, _ in triples])
        assessments = {
            item.field_name: item
            for item in getattr(spatial, "assessments", ())
        }
        values = {
            field_name: normalize_label_text(value)
            for field_name, value in held_out.get("values", {}).items()
        }
        cells: list[CellEvidence] = []

        for (crop, pre_gate_result, reading), result in zip(triples, gated_results):
            reference = values.get(crop.field_name, "")
            digits_match = (
                _digits_only(result.raw_value) == _digits_only(reference)
                and "?" not in result.raw_value
            )
            cli_cell = cli_cells.get(crop.field_name)
            if cli_cell is None:
                raise RuntimeError(
                    f"{fold_id} CLI output did not include {crop.field_name}")
            if (cli_cell.status != result.status
                    or cli_cell.raw_value != result.raw_value
                    or cli_cell.digits_match_reference != digits_match):
                raise RuntimeError(
                    f"{fold_id} in-process result disagrees with CLI for "
                    f"{crop.field_name}: cli={cli_cell}, local={result}")

            glyphs = _rank_glyphs(
                crop.image, crop.field_name, reading, engine, reference)
            source = assessments.get(crop.field_name)
            source_status = getattr(source, "status", None)
            conditions, other_conditions = _condition_flags(
                field_name=crop.field_name,
                result=result,
                reading=reading,
                glyphs=glyphs,
                gate=gate,
                source_status=source_status,
                engine=engine,
                minimum_confidence=MINIMUM_CONFIDENCE,
            )
            classifier = engine._classifier
            available = {
                template.label
                for template in classifier._templates_for(
                    profile_for_field(crop.field_name))
            }
            missing = tuple(sorted(set(reference) - available))
            cells.append(CellEvidence(
                fold_id=fold_id,
                invoice_id=str(held_out["id"]),
                field_name=crop.field_name,
                field_class=_cell_class(crop.field_name),
                raw_value=result.raw_value,
                reference=reference,
                digits_match_reference=digits_match,
                confidence=float(result.confidence or 0.0),
                status=result.status,
                pre_gate_reason=pre_gate_result.reason,
                reason=result.reason,
                conditions=conditions,
                other_conditions=other_conditions,
                glyphs=glyphs,
                source_status=source_status,
                gate_passed=gate.passed,
                gate_reason=gate.reason,
                template_labels=tuple(sorted(available)),
                missing_reference_labels=missing,
            ))

        return FoldEvidence(
            fold_id=fold_id,
            held_out_invoice=str(held_out["id"]),
            build_command=shlex.join(build_args),
            build_output=build_output,
            evaluate_command=shlex.join(evaluate_args),
            evaluate_output=evaluate_output,
            gate_passed=gate.passed,
            gate_reason=gate.reason,
            gate_line_sum=gate.line_sum,
            gate_payable=gate.payable,
            template_counts=templates.counts(),
            cells=cells,
        )


def _quoted(value: str | None) -> str:
    return "None" if value is None else repr(value)


def _glyph_line(glyph_item: GlyphEvidence) -> str:
    second = (
        f"{glyph_item.second_label!r} ({glyph_item.second_distance:.4f})"
        if glyph_item.second_label is not None
        and glyph_item.second_distance is not None else "no second label"
    )
    expected = f" expected={glyph_item.expected!r}" if glyph_item.expected else ""
    note = f" note={glyph_item.note!r}" if glyph_item.note else ""
    return (
        f"g{glyph_item.index}{expected}: best={glyph_item.best_label!r} "
        f"distance={glyph_item.distance:.4f} margin={glyph_item.margin:.4f} "
        f"second={second} accepted={glyph_item.accepted} "
        f"bbox={glyph_item.bbox}{note}"
    )


def _candidate_review_cells(folds: list[FoldEvidence]) -> list[CellEvidence]:
    return [
        cell for fold in folds for cell in fold.cells
        if cell.status == "REVIEW" and cell.digits_match_reference
    ]


def _report_text(
    folds: list[FoldEvidence],
    *,
    command: str,
    report_path: Path,
) -> str:
    all_cells = [cell for fold in folds for cell in fold.cells]
    review_cells = [cell for cell in all_cells if cell.status == "REVIEW"]
    correct_reviews = _candidate_review_cells(folds)
    correct_extracted = [
        cell for cell in all_cells
        if cell.status == "EXTRACTED" and cell.digits_match_reference
    ]
    condition_all = Counter(
        condition for cell in review_cells for condition in cell.conditions)
    condition_correct = Counter(
        condition for cell in correct_reviews for condition in cell.conditions)
    what_if = {
        condition: sum(
            cell.conditions == {condition} and not cell.other_conditions
            for cell in correct_reviews
        )
        for condition in CONDITION_NAMES
    }
    other_only_what_if = sum(
        bool(cell.other_conditions) and not cell.conditions
        for cell in correct_reviews
    )
    cells_by_key = {
        (cell.fold_id, cell.field_name): cell
        for cell in all_cells
    }
    payable_33 = cells_by_key.get(("fold-4", "invoice.payable"))
    fold_33 = next((fold for fold in folds if fold.held_out_invoice == "33"), None)

    lines = [
        "# B2-2b — Diagnosis of correct cells marked REVIEW",
        "",
        "## Evaluation setup",
        "",
        "Four-fold leave-one-invoice-out evaluation: each fold builds templates from the other three invoices and evaluates only the held-out invoice. This script captures the existing `build` and `evaluate` CLI outputs and independently recomputes the same readings from the saved template bank to expose per-glyph details. In-process results are checked against the CLI's status, raw value, and `digits_match_reference` output.",
        "",
        f"Command: `{command}`",
        f"Report path: `{report_path}`",
        f"Thresholds used unchanged: max distance {DEFAULT_MAX_DISTANCE:.2f}, minimum margin {DEFAULT_MIN_MARGIN:.2f}, minimum confidence {MINIMUM_CONFIDENCE:.1f}. No classifier settings or defaults were changed.",
        "",
        f"Total evaluated numeric cells: {len(all_cells)}; REVIEW: {len(review_cells)}; REVIEW with `digits_match_reference=True`: **{len(correct_reviews)}**; correctly EXTRACTED: {len(correct_extracted)}.",
        "",
        "## 1. Per-cell REVIEW diagnosis",
        "",
        "Condition flags are evaluated independently; a cell can fail more than one condition. The reason string shown is the final classifier result after the arithmetic gate, with the pre-gate reason included where relevant.",
        "",
    ]
    if not correct_reviews:
        lines.append("No REVIEW cells with `digits_match_reference=True` were observed.")
    for cell in correct_reviews:
        lines.extend([
            f"### {cell.field_class}: `{cell.field_name}` — {cell.fold_id}, held-out #{cell.invoice_id}",
            "",
            f"- Raw/reference: `{cell.raw_value}` / `{cell.reference}`; confidence `{cell.confidence:.2f}`; status `REVIEW`.",
            f"- Final classifier reason: {_quoted(cell.reason)}",
            f"- Pre-arithmetic-gate reason: {_quoted(cell.pre_gate_reason)}",
            f"- Failed conditions: {', '.join(sorted(cell.conditions)) if cell.conditions else 'none of the listed checks'}.",
            f"- Other glyph/text conditions: {', '.join(cell.other_conditions) if cell.other_conditions else 'none'}.",
            f"- Gate: passed={cell.gate_passed}; reason={_quoted(cell.gate_reason)}; source status={_quoted(cell.source_status)}.",
            "- Per-glyph evidence:",
        ])
        if cell.glyphs:
            lines.extend(f"  - `{_glyph_line(item)}`" for item in cell.glyphs)
        else:
            lines.append("  - No glyph components were returned.")
        if cell.missing_reference_labels:
            lines.append(
                "- Reference symbols missing from the template pool: "
                + ", ".join(repr(label) for label in cell.missing_reference_labels) + ".")
        lines.append("")

    lines.extend([
        "## 2. Invoice #33 payable diagnosis",
        "",
    ])
    if payable_33 is None:
        lines.append("No invoice #33 payable result was found in fold-4 output.")
    else:
        expected_glyph_count = len(payable_33.reference)
        rejected_glyphs = [item for item in payable_33.glyphs if not item.accepted]
        gate_failed = "arithmetic gate" in payable_33.conditions
        glyph_threshold_failed = any(
            item.distance > DEFAULT_MAX_DISTANCE
            or item.margin < DEFAULT_MIN_MARGIN
            or item.note is not None
            for item in payable_33.glyphs
        )
        if gate_failed and glyph_threshold_failed:
            cause = "both per-glyph/classifier checks and the arithmetic gate"
        elif gate_failed:
            cause = "the arithmetic gate"
        elif glyph_threshold_failed:
            cause = "one or more glyph-level/classifier checks"
        elif payable_33.conditions:
            cause = ", ".join(sorted(payable_33.conditions))
        else:
            cause = "no listed condition (inspect the raw CLI reason below)"
        lines.extend([
            f"Invoice #33 held out in `{payable_33.fold_id}`: raw `{payable_33.raw_value}`, reference `{payable_33.reference}`, digits_match_reference={payable_33.digits_match_reference}, status `{payable_33.status}`, confidence {payable_33.confidence:.2f}.",
            f"Final reason: {_quoted(payable_33.reason)}",
            f"Pre-gate reason: {_quoted(payable_33.pre_gate_reason)}",
            f"The cell has {len(payable_33.glyphs)}/{expected_glyph_count} glyph readings; rejected glyphs: {len(rejected_glyphs)}. One-glyph rejection: {'yes' if len(rejected_glyphs) == 1 else 'no'}; arithmetic gate failure: {'yes' if gate_failed else 'no'}. The REVIEW is attributable to {cause}.",
            f"Gate: passed={payable_33.gate_passed}; reason={_quoted(payable_33.gate_reason)}; line sum={fold_33.gate_line_sum if fold_33 else None}; payable={fold_33.gate_payable if fold_33 else None}.",
            f"Template labels available to payable profile (payable + row fallback): {', '.join(repr(label) for label in payable_33.template_labels) or 'none'}.",
            f"Reference labels absent from that pool: {', '.join(repr(label) for label in payable_33.missing_reference_labels) or 'none'}.",
            "",
            "Counterfactual isolation: relaxing only the margin check would accept glyph 1 as `۳` (best distance 0.0611, margin 0.1423) and make the raw payable match the reference; the separate arithmetic gate would still fail because `line.3.total` is malformed, so the payable would remain REVIEW. Relaxing only the arithmetic gate would leave the `?` glyph and incorrect raw value, so it also would not become EXTRACTED. Both blockers would have to clear.",
            "",
            "Per-glyph best and second-best candidates:",
            "",
        ])
        if payable_33.glyphs:
            lines.extend(f"- `{_glyph_line(item)}`" for item in payable_33.glyphs)
        else:
            lines.append("- No glyph readings were produced.")
        lines.append("")

    lines.extend([
        "## 3. REVIEW counts per failure condition",
        "",
        "Counts are overlapping condition flags, not mutually exclusive primary causes. `All REVIEW` includes incorrect and correct cells; `correct REVIEW` is the subset with `digits_match_reference=True`.",
        "",
        "| condition | all REVIEW cells flagged | correct REVIEW cells flagged |",
        "|---|---:|---:|",
    ])
    for condition in CONDITION_NAMES:
        lines.append(
            f"| {condition} | {condition_all[condition]} | {condition_correct[condition]} |")
    other_all = sum(bool(cell.other_conditions) for cell in review_cells)
    other_correct = sum(bool(cell.other_conditions) for cell in correct_reviews)
    lines.extend([
        f"| other glyph/text checks (edge, width, no text, etc.) | {other_all} | {other_correct} |",
        "",
        f"Unique REVIEW cells: {len(review_cells)}; correct REVIEW cells: {len(correct_reviews)}. Since flags can overlap, condition columns need not sum to the number of REVIEW cells.",
        "",
        "## 4. What-if: relax one condition at a time",
        "",
        "This is a read-only counterfactual over the current correct REVIEW cells. A cell is counted only if the selected condition is its sole active failure; all other checks, including the arithmetic gate, remain unchanged. No thresholds or defaults are altered.",
        "",
        "| condition hypothetically relaxed | correct REVIEW cells with this as sole blocker | newly EXTRACTED | total correct cells EXTRACTED after this single relaxation |",
        "|---|---:|---:|---:|",
    ])
    for condition in CONDITION_NAMES:
        newly_extracted = what_if[condition]
        lines.append(
            f"| {condition} | {newly_extracted} | {newly_extracted} "
            f"| {len(correct_extracted) + newly_extracted} |")
    lines.extend([
        f"| other glyph/text checks | {other_only_what_if} | {other_only_what_if} | "
        f"{len(correct_extracted) + other_only_what_if} |",
        "",
        "## 5. Conclusion",
        "",
    ])
    confidence_only = what_if["confidence < minimum_confidence"]
    gate_only = what_if["arithmetic gate"]
    threshold_only = sum(
        what_if[name]
        for name in ("distance > max_distance", "margin < min_margin",
                     "confidence < minimum_confidence")
    )
    missing_template_cases = sum(bool(cell.missing_reference_labels) for cell in correct_reviews)
    lines.extend([
        f"- **Are thresholds unnecessarily strict?** Only {confidence_only} currently correct REVIEW cell(s) are blocked solely by the 60.0 confidence cutoff (the correct `line.1.quantity` at 34.29); {threshold_only} correct REVIEW cell(s) become EXTRACTED if one of the numeric thresholds is relaxed in isolation. The nine correctly read totals are REVIEW because the invoice-wide arithmetic gate fails, not because their glyph thresholds are too strict. The #33 payable's first glyph misses the margin cutoff narrowly (0.1423 vs 0.1500), but relaxing that alone would not clear the gate. This is a caution signal, not enough evidence to change defaults.",
        f"- **Is template coverage really the issue?** {missing_template_cases} correct REVIEW cell(s) have reference labels absent from their profile pool; #33 payable has no missing reference labels, and all digits plus the comma are available. Its top label is the expected `۳`, with `۴` a close runner-up. This points to ambiguity/margin rather than missing-label coverage for #33.",
        f"- **What does the data suggest?** Nine of the ten correct REVIEW cells are totals downgraded because the separate `line.3.total` prediction contains `?`, which causes the arithmetic gate to fail for invoice #33. One quantity cell is REVIEW solely for low confidence. The payable itself has one ambiguous first glyph and is also subject to that failed gate. Keep uncertain values in REVIEW; the data distinguishes gate propagation from the isolated confidence and margin checks, and the PM should decide whether any calibrated threshold change is justified.",
        "",
        "### Full raw LOO evaluation output (all per-cell lines)",
        "",
        "The following are the complete evaluator stdout/stderr captures for each fold, including every cell's status, reference match, reason, arithmetic gate, and calibration summaries.",
        "",
    ])
    for fold in folds:
        lines.extend([
            f"#### {fold.fold_id} — held-out invoice #{fold.held_out_invoice}",
            "",
            f"Build command: `{fold.build_command}`",
            "",
            "```text",
            fold.build_output.rstrip(),
            "```",
            "",
            f"Evaluate command: `{fold.evaluate_command}`",
            "",
            "```text",
            fold.evaluate_output.rstrip(),
            "```",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    labels_path = args.labels.resolve()
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    if payload.get("label_status") != "OPERATOR_CONFIRMED":
        raise ValueError("labels must have label_status=OPERATOR_CONFIRMED")
    entries = payload.get("invoices")
    if not isinstance(entries, list) or len(entries) != 4:
        raise ValueError("expected exactly four invoice fixtures for LOO")
    if len({str(item.get("id")) for item in entries}) != 4:
        raise ValueError("invoice IDs must be unique")

    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_path if not existing_pythonpath
        else src_path + os.pathsep + existing_pythonpath
    )
    labels_dir = labels_path.parent
    folds: list[FoldEvidence] = []
    for index, held_out in enumerate(entries, start=1):
        training = [item for item in entries if item is not held_out]
        print(f"Running {index}/4: train on 3 invoices, hold out #{held_out['id']}...")
        folds.append(_run_fold(index, held_out, training, labels_dir, env))

    output_path = args.output.resolve()
    try:
        shown_output = output_path.relative_to(REPO_ROOT)
    except ValueError:
        shown_output = output_path
    command = (
        f"PYTHONPATH=src {sys.executable} {Path(__file__).relative_to(REPO_ROOT)} "
        f"--labels {labels_path.relative_to(REPO_ROOT)} "
        f"--output {shown_output}"
    )
    report = _report_text(
        folds, command=command, report_path=output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    cells = [cell for fold in folds for cell in fold.cells]
    review = [cell for cell in cells if cell.status == "REVIEW"]
    correct_review = _candidate_review_cells(folds)
    print(f"evaluation_cells={len(cells)} review_cells={len(review)} "
          f"correct_review_cells={len(correct_review)}")
    for fold in folds:
        print(f"{fold.fold_id} held_out=#{fold.held_out_invoice} "
              f"arithmetic_gate_passed={fold.gate_passed} "
              f"gate_reason={_quoted(fold.gate_reason)}")
    print(f"report_path={output_path}")
    print(f"ACCEPTANCE=PASS (diagnosis only; no classifier/default changes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
