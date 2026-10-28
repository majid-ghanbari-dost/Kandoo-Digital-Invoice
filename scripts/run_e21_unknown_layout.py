#!/usr/bin/env python3
"""Run E-21's synthetic unknown-layout fail-closed checks.

The five pages are generated from E-03 v3 answer-key values. This is a
mechanics/safety test only, not evidence about a physical Holo printer or a real
store. No E-02/E-05/E-06 thresholds are changed. A suitable already-installed
Persian-digit font is required; this script never downloads or substitutes one.
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import tempfile
from typing import Any, Mapping

try:
    from PIL import Image, __version__ as PILLOW_VERSION
except ImportError:
    Image = None  # type: ignore[assignment]
    PILLOW_VERSION = None

from synthetic_thermal_invoice import (
    PAGE_IDS,
    PersianFontUnavailable,
    build_synthetic_e05_bank,
    build_synthetic_glyph_bank,
    glyph_value_map,
    load_kit,
    normalize_numeric,
    observe_page,
    render_page,
    select_persian_font,
    synthetic_context,
)


VARIANTS = (
    ("swapped-columns", "Swapped columns"),
    ("no-vertical-rules", "No vertical rules"),
    ("three-columns", "Three columns"),
    ("extra-column", "Extra column"),
    ("different-table-position", "Different table position"),
)
SAFE_FINAL_OUTCOMES = {"REVIEW", "BLOCKED"}


def _pipeline_confidence(result: Any) -> float | None:
    confidences = [
        float(cell.confidence) / 100.0
        for cell in result.cell_results
        if cell.confidence is not None
    ]
    return min(confidences) if confidences else None


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# E-21 — Synthetic unknown-layout safety checks",
        "",
        f"- **Status:** {report.get('status', 'UNKNOWN')}",
        f"- **Execution environment:** {report['platform']['system']} / Python {report['platform']['python']} / "
        f"Pillow {report['platform']['pillow']}.",
        "- **Evidence class:** synthetic mechanics only; not a Holo capture, not real-store evidence, "
        "and not production OCR accuracy.",
        "",
    ]
    if report.get("font"):
        lines.extend([
            "## Test setup",
            "",
            f"- Installed font: **{report['font']['family']} {report['font']['style']}** "
            f"(`{report['font']['path']}`; SHA-256 `{report['font']['sha256']}`).",
            "- The five exam variants are rendered at 576 pixels wide, 1-bit, from the frozen E-03 v3 values.",
            "- E-05/Glyph banks are trained only on the three synthetic learning pages; each variant is held out.",
            "- E-05 reference comparisons use E-03 answer-key labels for numeric evidence and are not OCR predictions.",
            "- Thresholds tuned: **False**. No font download or substitution was attempted.",
            "",
            "## Per-variant routing and value safety",
            "",
            "Rates use one synthetic page per variant (`safe outcomes / 1`); they are not statistical claims.",
            "",
            "| Variant | E-02 / layout | E-05 reference | E-06 | Final | Safe-route rate | Correct EXTRACTED | EXTRACTED-but-wrong | Reason |",
            "|---|---|---|---|---|---:|---:|---:|---|",
        ])
        for variant in report["variants"]:
            e05 = variant["e05_reference_match"]
            e05_text = (
                f"{e05['confidence_score']:.3f} / {e05['matched']}"
                if e05 is not None else "No safe observation"
            )
            cells = variant["cell_counts"]
            lines.append(
                f"| {variant['label']} | {variant['pipeline_status']} / {variant['layout_status']} | "
                f"{e05_text} | {variant['e06_verdict']} | **{variant['final_outcome']}** | "
                f"{variant['safe_route_count']}/{variant['sample_count']} "
                f"({variant['safe_route_rate_percent']:.0f}%) | "
                f"{cells['extracted_correct']} | {cells['extracted_wrong']} | {variant['final_reason']} |"
            )
        lines.extend([
            "",
            "## Aggregate result",
            "",
            f"- Safely routed to REVIEW/BLOCKED: **{report['aggregate']['safe_route_count']}/"
            f"{report['aggregate']['sample_count']} ({report['aggregate']['safe_route_rate_percent']:.0f}%)**.",
            f"- EXTRACTED-but-wrong numeric cells: **{report['aggregate']['extracted_wrong']}**.",
            f"- Confident wrong values forwarded as an E-02 Canonical candidate: **{report['aggregate']['wrong_candidate_count']}**.",
            f"- Variants with a non-empty final reason: **{report['aggregate']['variants_with_reason']}/"
            f"{report['aggregate']['sample_count']}**.",
            f"- Thresholds tuned: **{report['aggregate']['thresholds_tuned']}**.",
            "",
            "## Variant details",
            "",
        ])
        for variant in report["variants"]:
            lines.extend([
                f"### {variant['label']}",
                "",
                f"- Synthetic image SHA-256: `{variant['image_sha256']}`; raster: "
                f"{variant['width']}×{variant['height']} px, mode `{variant['mode']}`.",
                f"- E-02: `{variant['pipeline_status']}` / layout `{variant['layout_status']}`; "
                f"{variant['cell_counts']['extracted_correct']} correct EXTRACTED, "
                f"{variant['cell_counts']['extracted_wrong']} EXTRACTED-but-wrong, "
                f"{variant['cell_counts']['review_or_blocked']} REVIEW/other.",
                f"- E-02 reason: {variant['pipeline_reason']}",
                f"- E-06: `{variant['e06_verdict']}`; reason codes: "
                f"{', '.join(f'`{code}`' for code in variant['e06_reason_codes']) or 'None'}.",
                f"- Final E-21 route: **{variant['final_outcome']}** — {variant['final_reason']}",
                f"- Candidate emitted: **{variant['canonical_candidate_emitted']}**; "
                f"candidate had wrong values: **{variant['candidate_has_wrong_values']}**.",
                "",
            ])
        lines.extend([
            "## Synthetic limitations",
            "",
            "These pages are rendered by Pillow from test values. They are not real invoices and do not establish "
            "generalization to another store. E-21 checks that these deliberately changed geometries are routed "
            "to review/blocking without emitting a confident wrong candidate; it does not tune or validate thresholds.",
            "",
        ])
        return "\n".join(lines)

    lines.extend([
        "## Fail-closed stop",
        "",
        f"- Reason: {report.get('font_selection_error') or report.get('error') or 'No suitable installed Persian-digit font.'}",
        "- No substitute font was downloaded or installed; the five variants were not evaluated.",
        "",
    ])
    return "\n".join(lines)


def _write_outputs(report: Mapping[str, Any], report_json: Path | None, report_md: Path | None) -> None:
    if report_json is not None:
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if report_md is not None:
        report_md.parent.mkdir(parents=True, exist_ok=True)
        report_md.write_text(render_markdown(report), encoding="utf-8")
    if report_json is None and report_md is None:
        print(render_markdown(report), end="")


def _base_report() -> dict[str, Any]:
    return {
        "task": "E-21",
        "status": "BLOCKED",
        "synthetic_only": True,
        "notice": (
            "Synthetic mechanics test only: not a Holo capture, not real-store evidence, "
            "and not a production OCR accuracy claim."
        ),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "pillow": PILLOW_VERSION,
        },
    }


def _route(result: Any, e06: Any) -> tuple[str, str]:
    if result.layout_status == "BLOCKED" or result.status == "REJECT":
        reason = result.layout_reason or result.reason or "E-02 blocked extraction"
        return "BLOCKED", f"E-02 failed closed: {reason}"
    if e06.verdict.value == "REJECT":
        details = "; ".join(e06.details) or ", ".join(e06.reason_code_strings)
        return "BLOCKED", f"E-06 rejected the variant; E-21 holds it: {details}"
    if e06.verdict.value == "ACCEPT":
        return "ACCEPT", "Unexpected E-06 acceptance; E-21 safety requirement failed."
    details = "; ".join(e06.details) or result.reason or ", ".join(e06.reason_code_strings)
    return "REVIEW", f"E-06 REVIEW: {details}"


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
            "next_action": "Stop. Do not download, install, or substitute another font for E-21.",
        })
        _write_outputs(report, report_json, report_md)
        return 2

    try:
        expected, item_names, _ = load_kit()
        with tempfile.TemporaryDirectory(prefix="kandoo-e21-") as temporary:
            work = Path(temporary)
            pages = {}
            learning_observations = []
            for page_id in PAGE_IDS[:3]:
                page = render_page(
                    page_id,
                    expected[page_id],
                    item_names[page_id],
                    font,
                    work / "learning" / f"{page_id}.png",
                )
                observation, safety, payable_bbox = observe_page(page)
                if observation is None or safety.geometry is None or payable_bbox is None:
                    raise RuntimeError(
                        f"synthetic E-21 learning page {page_id} is not safely measurable: {safety.reason}"
                    )
                learning_observations.append(observation)
                pages[page_id] = page
            from e05_template_bank import match_observation

            e05_bank = build_synthetic_e05_bank(learning_observations)
            glyph_path = work / "glyph-templates.json"
            glyph_templates, labelled_cells, build_log = build_synthetic_glyph_bank(
                [pages[f"learning-{index}"] for index in (1, 2, 3)], glyph_path
            )
            used_cells = sum(": USED " in line for line in build_log)
            if used_cells != labelled_cells:
                raise RuntimeError(
                    f"E-21 Glyph training unexpectedly skipped labels: used {used_cells}/{labelled_cells}"
                )

            from image_extraction_adapter.pipeline_v0 import extract_pipeline_v0
            from e06_onboarding_verdict import evaluate_verdict

            variant_reports = []
            for variant_id, label in VARIANTS:
                page = render_page(
                    "exam",
                    expected["exam"],
                    item_names["exam"],
                    font,
                    work / "variants" / f"{variant_id}.png",
                    variant=variant_id,
                )
                with Image.open(page.image_path) as opened:
                    opened.load()
                    mode = opened.mode
                    width, height = opened.size
                if mode != "1" or width != 576:
                    raise RuntimeError(
                        f"{variant_id}: expected 576-pixel-wide 1-bit raster, got {width}x{height} mode={mode}"
                    )

                target_observation, target_safety, _ = observe_page(page)
                target_match = (
                    match_observation(e05_bank, target_observation)
                    if target_observation is not None else None
                )
                result = extract_pipeline_v0(
                    page.image_path,
                    templates_path=glyph_path,
                    canonical_context=synthetic_context(page),
                    evaluation=True,
                )
                expected_fields = glyph_value_map(page.values)
                cell_rows = []
                extracted_correct = 0
                extracted_wrong = 0
                review_cells = 0
                for cell in result.cell_results:
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
                    cell_rows.append({
                        "field": cell.field_name,
                        "raw_value": cell.raw_value,
                        "expected_value": expected_value,
                        "confidence": cell.confidence,
                        "status": cell.status,
                        "correct_after_normalization": is_correct,
                        "reason": cell.reason,
                    })

                actual_values = {
                    cell.field_name: cell.raw_value for cell in result.cell_results
                }
                actual_observation, actual_safety, _ = observe_page(
                    page,
                    source_id=f"{variant_id}-pipeline-readings",
                    field_values_override=actual_values,
                )
                e06_observation = actual_observation or target_observation
                e06 = evaluate_verdict(
                    result.canonical_invoice,
                    e05_bank,
                    e06_observation,
                    _pipeline_confidence(result),
                    processed_invoice_count=0,
                    template_bank_locked=False,
                    d14_agreement_signed=False,
                    missing_fields=(
                        result.canonical_blockers or ("E-02 emitted no Canonical Invoice candidate",)
                        if result.canonical_invoice is None
                        else ()
                    ),
                )
                final_outcome, final_reason = _route(result, e06)
                expected_by_field = expected_fields
                candidate_wrong_fields: list[str] = []
                candidate = result.canonical_invoice
                if candidate is not None:
                    candidate_values = {}
                    for index, line in enumerate(candidate.get("line_items", [])):
                        candidate_values[f"line.{index}.quantity"] = str(line.get("quantity", ""))
                        candidate_values[f"line.{index}.total"] = str(line.get("line_total", ""))
                    candidate_values["invoice.payable"] = str(
                        candidate.get("summary", {}).get("payable", "")
                    )
                    candidate_wrong_fields = [
                        field for field, actual in candidate_values.items()
                        if field in expected_by_field
                        and normalize_numeric(actual) != normalize_numeric(expected_by_field[field])
                    ]
                safe = final_outcome in SAFE_FINAL_OUTCOMES
                reason_present = bool(final_reason.strip())
                variant_passed = safe and reason_present and extracted_wrong == 0 and not candidate_wrong_fields
                variant_reports.append({
                    "variant_id": variant_id,
                    "label": label,
                    "synthetic": True,
                    "image_sha256": page.sha256,
                    "width": width,
                    "height": height,
                    "mode": mode,
                    "target_layout_status": target_safety.status,
                    "target_layout_reason": target_safety.reason,
                    "e05_reference_match": target_match.to_dict() if target_match else None,
                    "pipeline_status": result.status,
                    "pipeline_reason": result.reason,
                    "layout_status": result.layout_status,
                    "layout_reason": result.layout_reason,
                    "row_count": result.row_count,
                    "arithmetic_gate": (
                        {
                            "passed": result.arithmetic_gate.passed,
                            "reason": result.arithmetic_gate.reason,
                        }
                        if result.arithmetic_gate is not None else None
                    ),
                    "cell_counts": {
                        "total": len(result.cell_results),
                        "extracted_correct": extracted_correct,
                        "extracted_wrong": extracted_wrong,
                        "review_or_blocked": review_cells,
                    },
                    "cells": cell_rows,
                    "canonical_candidate_emitted": candidate is not None,
                    "candidate_wrong_fields": candidate_wrong_fields,
                    "candidate_has_wrong_values": bool(candidate_wrong_fields),
                    "e06_verdict": e06.verdict.value,
                    "e06_reason_codes": list(e06.reason_code_strings),
                    "e06_details": list(e06.details),
                    "e06_template_match": e06.template_match.to_dict() if e06.template_match else None,
                    "final_outcome": final_outcome,
                    "final_reason": final_reason,
                    "sample_count": 1,
                    "safe_route_count": int(safe),
                    "safe_route_rate_percent": 100.0 if safe else 0.0,
                    "reason_present": reason_present,
                    "passed": variant_passed,
                })

            sample_count = len(variant_reports)
            safe_count = sum(variant["safe_route_count"] for variant in variant_reports)
            wrong_count = sum(variant["cell_counts"]["extracted_wrong"] for variant in variant_reports)
            wrong_candidate_count = sum(
                variant["candidate_has_wrong_values"] for variant in variant_reports
            )
            variants_with_reason = sum(variant["reason_present"] for variant in variant_reports)
            overall_safe_rate = (safe_count / sample_count) if sample_count else 0.0
            passed = (
                sample_count == len(VARIANTS)
                and safe_count == sample_count
                and wrong_count == 0
                and wrong_candidate_count == 0
                and variants_with_reason == sample_count
                and all(variant["passed"] for variant in variant_reports)
            )
            report.update({
                "status": "PASS" if passed else "FAIL",
                "font": {
                    "family": font.family,
                    "style": font.style,
                    "path": str(font.path),
                    "sha256": font.sha256,
                    "no_substitution": True,
                },
                "training": {
                    "source_pages": ["learning-1", "learning-2", "learning-3"],
                    "e05_template_count": len(e05_bank.templates),
                    "glyph_labelled_numeric_cells": labelled_cells,
                    "glyph_used_numeric_cells": used_cells,
                    "thresholds_tuned": False,
                },
                "variants": variant_reports,
                "aggregate": {
                    "sample_count": sample_count,
                    "safe_route_count": safe_count,
                    "safe_route_rate_percent": overall_safe_rate * 100.0,
                    "extracted_wrong": wrong_count,
                    "wrong_candidate_count": wrong_candidate_count,
                    "variants_with_reason": variants_with_reason,
                    "thresholds_tuned": False,
                    "passed": passed,
                },
            })
    except Exception as exc:
        report.update({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
        _write_outputs(report, report_json, report_md)
        return 1

    _write_outputs(report, report_json, report_md)
    return 0 if report["status"] == "PASS" else 1


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
