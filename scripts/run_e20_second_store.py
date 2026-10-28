#!/usr/bin/env python3
"""Run E-20's synthetic, fail-closed alternate-font mechanics check.

This deliberately does not create evidence about a real store, a Holo printer,
or production OCR accuracy. It validates that a suitable font is already
installed, renders synthetic 576-pixel 1-bit pages, builds E-05/Glyph templates
from the three synthetic learning pages, and evaluates the held-out synthetic
exam page without changing any thresholds.
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

try:
    from PIL import Image, __version__ as PILLOW_VERSION
except ImportError:
    Image = None  # type: ignore[assignment]
    PILLOW_VERSION = None

from synthetic_thermal_invoice import (
    CONTROLLED_GLYPHS,
    PAGE_IDS,
    PersianFontUnavailable,
    build_synthetic_e05_bank,
    build_synthetic_glyph_bank,
    digit_counts,
    glyph_value_map,
    load_kit,
    normalize_numeric,
    observe_page,
    render_page,
    select_persian_font,
    synthetic_context,
)


def _jsonable_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {glyph: int(counts.get(glyph, 0)) for glyph in CONTROLLED_GLYPHS}


def _pipeline_confidence(result: Any) -> float | None:
    confidences = [
        float(cell.confidence) / 100.0
        for cell in result.cell_results
        if cell.confidence is not None
    ]
    return min(confidences) if confidences else None


def _write_outputs(report: Mapping[str, Any], report_json: Path | None, report_md: Path | None) -> None:
    json_text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    markdown_text = render_markdown(report)
    if report_json is not None:
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(json_text, encoding="utf-8")
    if report_md is not None:
        report_md.parent.mkdir(parents=True, exist_ok=True)
        report_md.write_text(markdown_text, encoding="utf-8")
    if report_json is None and report_md is None:
        print(markdown_text, end="")


def _base_report() -> dict[str, Any]:
    return {
        "task": "E-20",
        "status": "BLOCKED",
        "synthetic_only": True,
        "notice": (
            "Synthetic mechanics test only: not a Holo capture, not real-store evidence, "
            "and not a claim of production OCR accuracy."
        ),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "pillow": PILLOW_VERSION,
        },
    }


def run(report_json: Path | None = None, report_md: Path | None = None) -> int:
    report = _base_report()
    try:
        if Image is None:
            raise PersianFontUnavailable("Pillow is missing; installed fonts cannot be inspected")
        font = select_persian_font()
    except PersianFontUnavailable as exc:
        report.update({
            "status": "BLOCKED_FONT_UNAVAILABLE",
            "font": None,
            "font_selection_error": str(exc),
            "next_action": "Stop. Do not download, install, or substitute another font for this test.",
        })
        _write_outputs(report, report_json, report_md)
        return 2

    try:
        expected, item_names, kit_counts = load_kit()
        with tempfile.TemporaryDirectory(prefix="kandoo-e20-") as temporary:
            work = Path(temporary)
            pages = {}
            observations = {}
            page_reports = []
            for page_id in PAGE_IDS:
                page = render_page(
                    page_id,
                    expected[page_id],
                    item_names[page_id],
                    font,
                    work / "pages" / f"{page_id}.png",
                )
                observation, safety, payable_bbox = observe_page(page)
                with Image.open(page.image_path) as opened:
                    opened.load()
                    mode = opened.mode
                    dimensions = list(opened.size)
                if mode != "1" or dimensions[0] != 576:
                    raise RuntimeError(
                        f"{page_id}: expected 576-pixel-wide 1-bit PNG; got {dimensions} mode={mode}"
                    )
                pages[page_id] = page
                observations[page_id] = observation
                page_reports.append({
                    "page_id": page_id,
                    "role": "exam" if page_id == "exam" else "learning",
                    "synthetic": True,
                    "sha256": page.sha256,
                    "width": page.width,
                    "height": page.height,
                    "mode": mode,
                    "threshold": 180,
                    "detected_layout_status": safety.status,
                    "detected_layout_reason": safety.reason,
                    "detected_row_count": (
                        len(safety.geometry.row_bands) if safety.geometry is not None else None
                    ),
                    "detected_column_boundaries": (
                        list(safety.geometry.column_boundaries) if safety.geometry is not None else []
                    ),
                    "detected_payable_bbox": list(payable_bbox) if payable_bbox else None,
                })

            learning_pages = [pages[f"learning-{index}"] for index in (1, 2, 3)]
            learning_observations = [observations[page.page_id] for page in learning_pages]
            if any(observation is None for observation in learning_observations):
                raise RuntimeError("a synthetic learning page did not yield a safe E-05 observation")
            e05_bank = build_synthetic_e05_bank(learning_observations)
            exam_target_observation = observations["exam"]
            if exam_target_observation is None:
                raise RuntimeError("synthetic exam page did not yield a safe E-05 observation")
            from e05_template_bank import match_observation

            e05_match = match_observation(e05_bank, exam_target_observation)

            glyph_path = work / "glyph-templates.json"
            glyph_templates, label_count, build_log = build_synthetic_glyph_bank(
                learning_pages, glyph_path
            )
            learning_values = [
                value
                for page in learning_pages
                for value in (
                    *page.values["quantities"],
                    *page.values["line_totals"],
                    page.values["payable"],
                )
            ]
            exam_values = [
                *pages["exam"].values["quantities"],
                *pages["exam"].values["line_totals"],
                pages["exam"].values["payable"],
            ]
            learning_symbol_counts = digit_counts(learning_values)
            exam_symbol_counts = digit_counts(exam_values)
            symbols_missing_from_learning = [
                symbol for symbol in CONTROLLED_GLYPHS if learning_symbol_counts[symbol] == 0
            ]
            exam_symbols_missing_from_learning = [
                symbol for symbol in CONTROLLED_GLYPHS
                if exam_symbol_counts[symbol] > 0 and learning_symbol_counts[symbol] == 0
            ]
            profile_missing = {
                profile: [
                    symbol for symbol in CONTROLLED_GLYPHS
                    if glyph_templates.counts().get(profile, {}).get(symbol, 0) == 0
                ]
                for profile in sorted(glyph_templates.profiles)
            }

            from image_extraction_adapter.pipeline_v0 import extract_pipeline_v0

            exam_page = pages["exam"]
            pipeline_result = extract_pipeline_v0(
                exam_page.image_path,
                templates_path=glyph_path,
                canonical_context=synthetic_context(exam_page),
                evaluation=True,
            )
            expected_fields = glyph_value_map(exam_page.values)
            cells = []
            extracted_correct = 0
            extracted_wrong = 0
            review_cells = 0
            for cell in pipeline_result.cell_results:
                expected_value = expected_fields.get(cell.field_name)
                is_correct = (
                    expected_value is not None
                    and normalize_numeric(cell.raw_value) == normalize_numeric(expected_value)
                )
                if cell.status == "EXTRACTED":
                    if is_correct:
                        extracted_correct += 1
                    else:
                        extracted_wrong += 1
                else:
                    review_cells += 1
                cells.append({
                    "field": cell.field_name,
                    "raw_value": cell.raw_value,
                    "expected_value": expected_value,
                    "confidence": cell.confidence,
                    "status": cell.status,
                    "exact_numeric_match_after_normalization": is_correct,
                    "reason": cell.reason,
                })

            actual_values = {
                cell.field_name: cell.raw_value for cell in pipeline_result.cell_results
            }
            exam_pipeline_observation, exam_safety, exam_payable_bbox = observe_page(
                exam_page,
                source_id="exam-pipeline-readings",
                field_values_override=actual_values,
            )
            if exam_pipeline_observation is None:
                raise RuntimeError(
                    "pipeline-readings E-05 observation could not be safely reconstructed: "
                    f"{exam_safety.reason}"
                )
            from e06_onboarding_verdict import evaluate_verdict

            e06 = evaluate_verdict(
                pipeline_result.canonical_invoice,
                e05_bank,
                exam_pipeline_observation,
                _pipeline_confidence(pipeline_result),
                processed_invoice_count=0,
                template_bank_locked=False,
                d14_agreement_signed=False,
                missing_fields=(
                    pipeline_result.canonical_blockers
                    if pipeline_result.canonical_invoice is None
                    else ()
                ),
            )

            glyph_counts = glyph_templates.counts()
            exam_symbols_not_in_row_templates = [
                symbol for symbol in CONTROLLED_GLYPHS
                if exam_symbol_counts[symbol] > 0
                and glyph_counts.get("row", {}).get(symbol, 0) == 0
            ]
            no_confident_wrong = extracted_wrong == 0
            no_accept = e06.verdict.value != "ACCEPT"
            e05_matched = bool(e05_match.matched)
            coverage_complete = not symbols_missing_from_learning and not exam_symbols_missing_from_learning
            passed = no_confident_wrong and no_accept and e05_matched and coverage_complete

            report.update({
                "status": "PASS" if passed else "FAIL",
                "font": {
                    "family": font.family,
                    "style": font.style,
                    "path": str(font.path),
                    "sha256": font.sha256,
                    "size_pixels": {
                        "title": 20,
                        "body": 17,
                        "numeric": 18 if "mono" in font.family.casefold() else 21,
                    },
                    "glyph_mask_validation": {
                        "tested_symbols": list(CONTROLLED_GLYPHS),
                        "all_masks_nonempty": True,
                        "ten_digit_masks_distinct": True,
                        "comma_mask_distinct_from_digits": True,
                    },
                    "substitution_policy": "No font download, installation, or fallback substitution.",
                },
                "rendering": {
                    "width_pixels": 576,
                    "bit_depth": 1,
                    "threshold_rule": "grayscale pixel < 180 becomes black; otherwise white",
                    "layout": "synthetic Holo-inspired 4-row invoice table",
                    "real_store_evidence": False,
                },
                "e03_kit_v3": {
                    "verified": True,
                    "controlled_learning_symbol_counts": _jsonable_counts(learning_symbol_counts),
                    "controlled_exam_symbol_counts": _jsonable_counts(exam_symbol_counts),
                    "symbols_missing_from_learning_pages": symbols_missing_from_learning,
                    "exam_symbols_missing_from_learning_pages": exam_symbols_missing_from_learning,
                },
                "pages": page_reports,
                "e05": {
                    "learning_source_ids": [page.page_id for page in learning_pages],
                    "synthetic_training_method": (
                        "Existing E-05 layout cluster aggregator, applied directly to pixel-detected "
                        "observations carrying E-03 controlled labels; no synthetic source was marked "
                        "operator-confirmed."
                    ),
                    "template_count": len(e05_bank.templates),
                    "exam_observation_basis": "pixel-detected geometry/payable plus E-03 answer-key values",
                    "exam_match": e05_match.to_dict(),
                    "match_passed": e05_matched,
                },
                "glyph_training": {
                    "learning_page_ids": [page.page_id for page in learning_pages],
                    "labelled_numeric_cells": label_count,
                    "used_cell_count": sum(": USED " in line for line in build_log),
                    "skipped_cells": [line for line in build_log if line.startswith("SKIP ")],
                    "template_counts_by_profile": glyph_counts,
                    "missing_symbols_by_template_profile": profile_missing,
                    "exam_symbols_missing_from_row_templates": exam_symbols_not_in_row_templates,
                },
                "pipeline_exam": {
                    "pipeline_status": pipeline_result.status,
                    "reason": pipeline_result.reason,
                    "layout_status": pipeline_result.layout_status,
                    "layout_reason": pipeline_result.layout_reason,
                    "row_count": pipeline_result.row_count,
                    "arithmetic_gate": (
                        {
                            "passed": pipeline_result.arithmetic_gate.passed,
                            "reason": pipeline_result.arithmetic_gate.reason,
                            "line_sum": pipeline_result.arithmetic_gate.line_sum,
                            "payable": pipeline_result.arithmetic_gate.payable,
                        }
                        if pipeline_result.arithmetic_gate is not None else None
                    ),
                    "canonical_candidate_emitted": pipeline_result.canonical_invoice is not None,
                    "canonical_blockers": list(pipeline_result.canonical_blockers),
                    "cell_counts": {
                        "total": len(pipeline_result.cell_results),
                        "extracted_correct": extracted_correct,
                        "extracted_wrong": extracted_wrong,
                        "review_or_blocked": review_cells,
                    },
                    "extracted_but_wrong_fields": [
                        cell["field"] for cell in cells
                        if cell["status"] == "EXTRACTED"
                        and not cell["exact_numeric_match_after_normalization"]
                    ],
                    "cells": cells,
                },
                "e06": {
                    "verdict": e06.verdict.value,
                    "reason_codes": list(e06.reason_code_strings),
                    "details": list(e06.details),
                    "confidence_score": e06.confidence_score,
                    "template_match": e06.template_match.to_dict() if e06.template_match else None,
                    "owner_acceptance_eligible": e06.owner_acceptance_eligible,
                    "input_candidate_source": (
                        "actual E-02 pipeline candidate; absent candidates are passed as None"
                    ),
                    "processed_invoice_count": 0,
                    "thresholds_tuned": False,
                },
                "acceptance": {
                    "zero_extracted_but_wrong_required": True,
                    "zero_extracted_but_wrong_observed": no_confident_wrong,
                    "all_exam_symbols_covered_by_learning_values": coverage_complete,
                    "e05_exam_observation_matched": e05_matched,
                    "e06_did_not_accept": no_accept,
                    "thresholds_tuned": False,
                    "passed": passed,
                },
            })
    except Exception as exc:
        report.update({
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
        })
        _write_outputs(report, report_json, report_md)
        return 1

    _write_outputs(report, report_json, report_md)
    return 0 if report["status"] == "PASS" else 1


def _md_list(values: list[Any]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "None"


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# E-20 — Synthetic second-store mechanics test",
        "",
        f"- **Status:** {report.get('status', 'UNKNOWN')}",
        f"- **Execution environment:** {report['platform']['system']} / Python {report['platform']['python']} / "
        f"Pillow {report['platform']['pillow']} (local runner; CI verification is a separate gate).",
        "- **Evidence class:** synthetic mechanics only; not a Holo capture, not real-store evidence, "
        "and not production OCR accuracy.",
        "",
    ]
    if report.get("font"):
        font = report["font"]
        lines.extend([
            "## Font and rasterization",
            "",
            f"- Selected installed font: **{font['family']} {font['style']}** ({font['path']}).",
            f"- Font SHA-256: `{font['sha256']}`.",
            f"- Glyph-mask check: digits ۰–۹ have distinct nonempty masks; comma is nonempty and distinct.",
            "- No font was downloaded, installed, or substituted. If no suitable installed font exists, "
            "the runner reports `BLOCKED_FONT_UNAVAILABLE` and stops.",
            "- Pages: 576 pixels wide, 1-bit, synthetic Holo-inspired four-row layout; grayscale threshold `< 180`.",
            "",
            "## E-03 v3 symbol coverage",
            "",
            f"- Learning-page values missing controlled symbols: **{_md_list(report['e03_kit_v3']['symbols_missing_from_learning_pages'])}**.",
            f"- Exam symbols absent from learning-page values: **{_md_list(report['e03_kit_v3']['exam_symbols_missing_from_learning_pages'])}**.",
            f"- E-02 row templates missing exam symbols: **{_md_list(report['glyph_training']['exam_symbols_missing_from_row_templates'])}**.",
            f"- E-02 per-profile gaps: {', '.join(f'`{profile}`: {_md_list(missing)}' for profile, missing in report['glyph_training']['missing_symbols_by_template_profile'].items())}. "
            "The current pipeline uses row templates for payable cells by default.",
            "- Counts below are synthetic rendered-target values from the frozen E-03 v3 kit:",
            "",
            "| Symbol | Learning pages | Exam page |",
            "|---:|---:|---:|",
        ])
        learning_counts = report['e03_kit_v3']['controlled_learning_symbol_counts']
        exam_counts = report['e03_kit_v3']['controlled_exam_symbol_counts']
        for symbol in CONTROLLED_GLYPHS:
            label = "comma" if symbol == "," else symbol
            lines.append(f"| `{label}` | {learning_counts[symbol]} | {exam_counts[symbol]} |")
        lines.extend([
            "",
            "## E-05, E-02, and E-06 results",
            "",
            f"- E-05 bank: {report['e05']['template_count']} synthetic cluster(s), trained on learning pages only; "
            f"held-out exam reference match `{report['e05']['exam_match']['confidence_score']:.3f}` "
            f"(matched: **{report['e05']['match_passed']}**). The match uses E-03 target labels for numeric evidence, "
            "not an OCR prediction.",
            f"- E-02 exam pipeline: **{report['pipeline_exam']['pipeline_status']}**; "
            f"{report['pipeline_exam']['cell_counts']['extracted_correct']} correct EXTRACTED, "
            f"{report['pipeline_exam']['cell_counts']['extracted_wrong']} EXTRACTED-but-wrong, "
            f"{report['pipeline_exam']['cell_counts']['review_or_blocked']} REVIEW/other cells.",
            f"- Arithmetic gate: `{report['pipeline_exam']['arithmetic_gate']['passed'] if report['pipeline_exam']['arithmetic_gate'] else 'not run'}`"
            + (
                f" ({report['pipeline_exam']['arithmetic_gate']['reason']})"
                if report['pipeline_exam']['arithmetic_gate'] and report['pipeline_exam']['arithmetic_gate']['reason']
                else ""
            )
            + ".",
            f"- Canonical Invoice candidate emitted: **{report['pipeline_exam']['canonical_candidate_emitted']}**.",
            f"- E-06 verdict: **{report['e06']['verdict']}**; reason codes: "
            f"{_md_list(report['e06']['reason_codes'])}.",
            f"- E-06 details: {'; '.join(report['e06']['details']) or 'None'}",
            "- E-06 input is the actual E-02 candidate; when E-02 emits no candidate, E-06 receives `None`. "
            "The separate E-05 reference match is not presented as an OCR result.",
            "",
            "## Acceptance checks",
            "",
            f"- Zero EXTRACTED-but-wrong: **{report['acceptance']['zero_extracted_but_wrong_observed']}**.",
            f"- All exam symbols represented in learning values: **{report['acceptance']['all_exam_symbols_covered_by_learning_values']}**.",
            f"- E-06 did not ACCEPT: **{report['acceptance']['e06_did_not_accept']}**.",
            f"- Thresholds tuned: **{report['acceptance']['thresholds_tuned']}**.",
            f"- Overall E-20 mechanics result: **{report['acceptance']['passed']}**.",
            "",
            "## Per-page raster and detected layout",
            "",
            "| Page | Role | Raster | Mode | Detection | Rows | SHA-256 |",
            "|---|---|---:|---|---|---:|---|",
        ])
        for page in report["pages"]:
            lines.append(
                f"| {page['page_id']} | {page['role']} | {page['width']}×{page['height']} | "
                f"{page['mode']} | {page['detected_layout_status']} | "
                f"{page['detected_row_count']} | `{page['sha256']}` |"
            )
        lines.extend([
            "",
            "## Synthetic limitations",
            "",
            "These pages were rendered by Pillow from the frozen E-03 answer key. They do not originate from "
            "Holo, a Windows spool job, KandooPrintProbe, a physical printer, or any real store. The test checks "
            "pipeline mechanics and fail-closed behavior only; it does not establish generalization to real stores.",
            "",
        ])
        return "\n".join(lines)

    lines.extend([
        "## Fail-closed stop",
        "",
        f"- Reason: {report.get('font_selection_error') or report.get('error') or 'No suitable installed Persian-digit font.'}",
        "- No pages were rendered with a substitute font. Installations/downloads are intentionally not attempted.",
        "- The E-20 mechanics evaluation did not proceed.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, help="Write the JSON evidence report to this path")
    parser.add_argument("--report-md", type=Path, help="Write the Markdown report to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run(report_json=args.report_json, report_md=args.report_md)


if __name__ == "__main__":
    raise SystemExit(main())
