#!/usr/bin/env python3
"""Run deterministic fail-closed perturbation trials on four legacy fixtures.

No production thresholds or OCR templates are changed. Each fixture uses the
existing leave-one-fixture-out E-02/Glyph fold, the existing E-05 bank, and the
E-06 verdict function. The emitted report is diagnostic evidence, not a claim
of general OCR accuracy or physical print/scan robustness.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from e05_template_bank import (  # noqa: E402
    build_template_bank,
    parse_labeled_integer,
)
from e06_onboarding_verdict import evaluate_verdict  # noqa: E402
from image_extraction_adapter.glyph_classifier import _binarize, segment_cell  # noqa: E402
from image_extraction_adapter.pipeline_v0 import (  # noqa: E402
    REPOSITORY_ROOT,
    _execute_pipeline,
    _source_records_from_bank,
    _template_set_sha256,
    build_templates_for_fold,
)
from image_extraction_adapter.preprocessing import detect_layout_safe  # noqa: E402
from run_e06_dry_run import (  # noqa: E402
    CANONICAL_DIR,
    EXPECTED_FIXTURE_IDS,
    LABELS_PATH,
    REAL_DIR,
    _build_observation,
    _extraction_confidence,
    _expected_numeric_values,
    _read_inputs,
)


REPORT_PATH = REPO_ROOT / "deliveries" / "e15-robustness" / "report.md"
PERTURBATION_ORDER = (
    "shift_1px",
    "shift_2px",
    "small_blur",
    "small_noise",
    "swap_digit_crops",
    "replace_digit_glyph",
    "delete_one_row",
)


class RobustnessRunError(RuntimeError):
    """Raised when an input cannot be perturbed or evaluated safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _score_expected(
    expected: Mapping[str, str],
    cells: tuple[Any, ...],
) -> tuple[int, int, int, list[dict[str, str]]]:
    by_name = {cell.field_name: cell for cell in cells}
    correct = not_extracted = wrong = 0
    wrong_values: list[dict[str, str]] = []
    for field_name, expected_raw in expected.items():
        cell = by_name.get(field_name)
        if cell is None or cell.status != "EXTRACTED":
            not_extracted += 1
            continue
        try:
            actual_value = parse_labeled_integer(cell.raw_value)
            expected_value = parse_labeled_integer(expected_raw)
        except (TypeError, ValueError):
            actual_value = None
            expected_value = parse_labeled_integer(expected_raw)
        if actual_value == expected_value:
            correct += 1
        else:
            wrong += 1
            wrong_values.append({
                "field": field_name,
                "extracted": str(cell.raw_value),
                "expected": expected_raw,
            })
    if correct + not_extracted + wrong != len(expected):
        raise AssertionError("numeric score counts do not sum to the expected field count")
    return correct, not_extracted, wrong, wrong_values


def _cell_glyphs(
    image: Any,
    cell: Any,
    expected_raw: str,
) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Map ground-truth characters to foreground component boxes in one cell."""
    crop = image.crop(cell.bbox)
    binary, _removed = _binarize(crop)
    _width, _height, components = segment_cell(binary)
    characters = list(expected_raw)
    if len(characters) != len(components):
        raise RobustnessRunError(
            f"{cell.field_name}: expected {len(characters)} glyphs but segmented {len(components)}"
        )
    left, top, _right, _bottom = cell.bbox
    return [
        (
            char,
            (
                left + component.left,
                top + component.top,
                left + component.right,
                top + component.bottom,
            ),
        )
        for char, component in zip(characters, components, strict=True)
    ]


def _glyph_patch(image: Any, source_box: tuple[int, int, int, int], target_box: tuple[int, int, int, int]) -> Any:
    from PIL import Image

    source = image.crop(source_box).convert("L")
    mask = source.point(lambda pixel: 255 if pixel < 128 else 0)
    target_size = (target_box[2] - target_box[0], target_box[3] - target_box[1])
    if mask.size != target_size:
        mask = mask.resize(target_size, Image.Resampling.NEAREST)
    patch = Image.new("RGB", target_size, (255, 255, 255))
    patch.paste((0, 0, 0), (0, 0, target_size[0], target_size[1]), mask)
    return patch


def _paste_glyph(image: Any, source_image: Any, source_box: tuple[int, int, int, int], target_box: tuple[int, int, int, int]) -> None:
    patch = _glyph_patch(source_image, source_box, target_box)
    image.paste(patch, target_box)


def _swap_two_digit_crops(image: Any, baseline: Any, expected: Mapping[str, str]) -> tuple[Any, str]:
    cells = {
        cell.field_name: cell
        for cell in baseline.cell_results
        if cell.field_name.endswith(".total") and cell.field_name in expected and cell.bbox
    }
    target_field = "line.0.total"
    if target_field not in cells:
        raise RobustnessRunError("cannot locate line.0.total for digit-crop swap")
    glyphs = _cell_glyphs(image, cells[target_field], expected[target_field])
    pair = None
    digit_boxes = [(char, box) for char, box in glyphs if char != ","]
    for index, (left_char, left_box) in enumerate(digit_boxes):
        for right_char, right_box in digit_boxes[index + 1:]:
            if left_char != right_char:
                pair = (left_char, left_box, right_char, right_box)
                break
        if pair is not None:
            break
    if pair is None:
        raise RobustnessRunError(f"{target_field}: no two different digit crops to swap")

    left_char, left_box, right_char, right_box = pair
    original = image.copy()
    output = image.copy()
    _paste_glyph(output, original, right_box, left_box)
    _paste_glyph(output, original, left_box, right_box)
    original.close()
    return output, f"{target_field}: swapped glyph {left_char} with {right_char}"


def _replace_one_digit_glyph(image: Any, baseline: Any, expected: Mapping[str, str]) -> tuple[Any, str]:
    cells = {
        cell.field_name: cell
        for cell in baseline.cell_results
        if cell.field_name.endswith(".total") and cell.field_name in expected and cell.bbox
    }
    target_field = "line.0.total"
    if target_field not in cells:
        raise RobustnessRunError("cannot locate line.0.total for digit replacement")
    target_glyphs = _cell_glyphs(image, cells[target_field], expected[target_field])
    target_char, target_box = next((char, box) for char, box in target_glyphs if char != ",")

    source = None
    for field_name, cell in cells.items():
        if field_name == target_field:
            continue
        glyphs = _cell_glyphs(image, cell, expected[field_name])
        for char, box in glyphs:
            if char != "," and char != target_char and box != target_box:
                source = (field_name, char, box)
                break
        if source is not None:
            break
    if source is None:
        raise RobustnessRunError("no distinct source digit glyph available for replacement")

    source_field, source_char, source_box = source
    output = image.copy()
    _paste_glyph(output, image, source_box, target_box)
    return output, (
        f"{target_field}: replaced glyph {target_char} with {source_char} "
        f"from {source_field}"
    )


def _delete_one_row(image: Any) -> tuple[Any, str]:
    from PIL import ImageDraw

    safety = detect_layout_safe(image)
    if safety.status != "OK" or safety.geometry is None:
        raise RobustnessRunError(f"cannot select a row for deletion: {safety.status}: {safety.reason}")
    rows = safety.geometry.row_bands
    index = len(rows) // 2
    top, bottom = rows[index]
    left = safety.geometry.column_boundaries[0]
    right = safety.geometry.column_boundaries[-1]
    box = (
        round(left) + 2,
        round(top) + 3,
        round(right) - 2,
        round(bottom) - 3,
    )
    output = image.copy()
    ImageDraw.Draw(output).rectangle(box, fill=(255, 255, 255))
    return output, f"cleared item row {index} (zero-based) while retaining table rules"


def _noise_image(image: Any, seed: int) -> tuple[Any, str]:
    output = image.copy()
    pixels = output.load()
    rng = random.Random(seed)
    count = max(1, (output.width * output.height) // 500)
    for _ in range(count):
        x = rng.randrange(output.width)
        y = rng.randrange(output.height)
        delta = rng.choice((-8, -6, 6, 8))
        red, green, blue = pixels[x, y]
        pixels[x, y] = tuple(
            max(0, min(255, channel + delta))
            for channel in (red, green, blue)
        )
    return output, f"{count} deterministic sparse RGB perturbations (delta ±6/±8)"


def _make_perturbations(
    image: Any,
    baseline: Any,
    expected: Mapping[str, str],
    fixture_id: str,
) -> dict[str, tuple[Any, str]]:
    from PIL import Image, ImageFilter

    perturbations: dict[str, tuple[Any, str]] = {}
    for delta in (1, 2):
        shifted = image.transform(
            image.size,
            Image.Transform.AFFINE,
            (1, 0, -delta, 0, 1, 0),
            resample=Image.Resampling.NEAREST,
            fillcolor=(255, 255, 255),
        )
        perturbations[f"shift_{delta}px"] = (shifted, f"translate right {delta} px, white fill")
    perturbations["small_blur"] = (
        image.filter(ImageFilter.GaussianBlur(radius=0.4)),
        "Gaussian blur radius 0.4 px",
    )
    perturbations["small_noise"] = _noise_image(image, seed=1500 + int(fixture_id))
    perturbations["swap_digit_crops"] = _swap_two_digit_crops(image, baseline, expected)
    perturbations["replace_digit_glyph"] = _replace_one_digit_glyph(image, baseline, expected)
    perturbations["delete_one_row"] = _delete_one_row(image)
    return perturbations


def _run_one(
    fixture_id: str,
    fixture_index: int,
    case_name: str,
    injection: str,
    image: Any,
    source_path: Path,
    temporary_dir: Path,
    templates: Any,
    template_sources: tuple[Mapping[str, Any], ...],
    template_library_id: str,
    expected: Mapping[str, str],
    canonical: Mapping[str, Any],
    e05_bank: Any,
) -> dict[str, Any]:
    output_path = temporary_dir / f"fixture-{fixture_id}-{case_name}.png"
    image.save(output_path, format="PNG")
    output_hash = _sha256(output_path)
    if output_hash == _sha256(source_path):
        raise RobustnessRunError(f"{fixture_id}/{case_name}: perturbation did not alter input bytes")

    pipeline = _execute_pipeline(
        output_path,
        templates=templates,
        template_sources=template_sources,
        template_library_id=template_library_id,
        template_bank_path=None,
        captured_at=None,
        canonical_context=None,
        evaluation=True,
        repo_root=REPOSITORY_ROOT,
    )
    correct, not_extracted, wrong, wrong_values = _score_expected(
        expected,
        tuple(pipeline.cell_results),
    )

    observation, observation_status = _build_observation(image, fixture_id, pipeline)
    confidence = _extraction_confidence(tuple(pipeline.cell_results))
    verdict = evaluate_verdict(
        canonical,
        e05_bank,
        observation,
        confidence,
        processed_invoice_count=fixture_index,
        template_bank_locked=False,
        d14_agreement_signed=False,
        require_kit_digit_coverage=False,
    )
    template_match = verdict.template_match
    return {
        "fixture": fixture_id,
        "perturbation": case_name,
        "injection": injection,
        "source_sha256": _sha256(source_path),
        "perturbed_sha256": output_hash,
        "input_changed": True,
        "e02_status": pipeline.status,
        "layout_status": pipeline.layout_status,
        "row_count": pipeline.row_count,
        "e05_status": (
            ("MATCH" if template_match.matched else "NO_MATCH")
            if template_match is not None else "NOT_EVALUATED"
        ),
        "e05_score": template_match.confidence_score if template_match is not None else None,
        "observation_status": observation_status,
        "e06_verdict": verdict.verdict.value,
        "e06_reason_codes": list(verdict.reason_code_strings),
        "correct": correct,
        "not_extracted": not_extracted,
        "wrong": wrong,
        "wrong_values": wrong_values,
    }


def run_matrix() -> tuple[list[dict[str, Any]], dict[str, int]]:
    try:
        from PIL import Image
        from PIL import __version__ as pillow_version
        import jsonschema
        from importlib.metadata import version

        schema_version = version("jsonschema")
    except Exception as exc:  # pragma: no cover - environment-dependent
        raise RobustnessRunError(f"Pillow and jsonschema are required: {exc}") from exc

    entries, by_id = _read_inputs()
    if tuple(sorted(by_id, key=int)) != EXPECTED_FIXTURE_IDS:
        raise RobustnessRunError("expected the four labeled fixtures 29, 31, 32, and 33")
    e05_bank = build_template_bank(CANONICAL_DIR, LABELS_PATH, currency_unit="rial")
    records: list[dict[str, Any]] = []
    totals = {
        "runs": 0,
        "correct": 0,
        "not_extracted": 0,
        "wrong": 0,
        "review": 0,
        "reject": 0,
        "accept": 0,
        "input_changed": 0,
    }

    with TemporaryDirectory(prefix="kandoo-e15-robustness-") as temporary:
        temporary_dir = Path(temporary)
        for fixture_index, entry in enumerate(entries):
            fixture_id = str(entry["id"])
            source_path = (REAL_DIR / str(entry["path"])).resolve()
            expected = _expected_numeric_values(entry)
            canonical = json.loads(
                (CANONICAL_DIR / f"canonical-{fixture_id}.json").read_text(encoding="utf-8")
            )
            templates = build_templates_for_fold(
                LABELS_PATH,
                fixture_id,
                repo_root=REPOSITORY_ROOT,
            )
            template_sources = _source_records_from_bank({"provenance": templates.provenance})
            template_library_id = _template_set_sha256(templates)

            baseline_path = temporary_dir / f"fixture-{fixture_id}-baseline.png"
            with Image.open(source_path) as opened:
                opened.load()
                baseline_image = opened.convert("RGB")
                baseline_image.save(baseline_path, format="PNG")
            baseline = _execute_pipeline(
                baseline_path,
                templates=templates,
                template_sources=template_sources,
                template_library_id=template_library_id,
                template_bank_path=None,
                captured_at=None,
                canonical_context=None,
                evaluation=True,
                repo_root=REPOSITORY_ROOT,
            )
            cases = _make_perturbations(baseline_image, baseline, expected, fixture_id)
            for case_name in PERTURBATION_ORDER:
                case_image, injection = cases[case_name]
                record = _run_one(
                    fixture_id,
                    fixture_index,
                    case_name,
                    injection,
                    case_image,
                    source_path,
                    temporary_dir,
                    templates,
                    template_sources,
                    template_library_id,
                    expected,
                    canonical,
                    e05_bank,
                )
                records.append(record)
                totals["runs"] += 1
                totals["correct"] += record["correct"]
                totals["not_extracted"] += record["not_extracted"]
                totals["wrong"] += record["wrong"]
                totals[record["e06_verdict"].casefold()] += 1
                totals["input_changed"] += int(record["input_changed"])
                case_image.close()
            baseline_image.close()

    if len(records) != len(EXPECTED_FIXTURE_IDS) * len(PERTURBATION_ORDER):
        raise AssertionError(f"expected 28 perturbation results, got {len(records)}")
    return records, {
        **totals,
        "pillow_version": pillow_version,
        "jsonschema_version": schema_version,
    }


def _verdict_rates(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for name in PERTURBATION_ORDER:
        subset = [record for record in records if record["perturbation"] == name]
        closed = sum(record["e06_verdict"] in {"REVIEW", "REJECT"} for record in subset)
        e02_counts = Counter(record["e02_status"] for record in subset)
        e06_counts = Counter(record["e06_verdict"] for record in subset)
        summary[name] = {
            "runs": len(subset),
            "fail_closed": closed,
            "fail_closed_rate": closed / len(subset) if subset else 0.0,
            "wrong": sum(record["wrong"] for record in subset),
            "e02_statuses": e02_counts,
            "e06_verdicts": e06_counts,
            "correct": sum(record["correct"] for record in subset),
            "not_extracted": sum(record["not_extracted"] for record in subset),
        }
    return summary


def _render_report(
    records: list[dict[str, Any]],
    totals: dict[str, Any],
    *,
    base_sha: str,
) -> str:
    rates = _verdict_rates(records)
    lines = [
        "# E-15 fail-closed robustness suite",
        "",
        f"- Evaluated code HEAD: `{base_sha}`",
        f"- Generated at (UTC): `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
        f"- Runtime: Python {sys.version.split()[0]}, Pillow {totals['pillow_version']}, jsonschema {totals['jsonschema_version']}",
        "- Source images: `tests/fixtures/real/{29,31,32,33}.png` with their operator-confirmed label values; fixture 31 payable remains derived from its line totals.",
        "- E-02: existing leave-one-fixture-out Glyph fold for each source fixture. E-05: existing label-derived four-fixture bank. E-06: existing verdict function; thresholds and policy constants were not changed.",
        "- Perturbations operate on decoded fixture pixels and are saved as temporary PNGs; all seven perturbation types run once per fixture (28 total). No invoice submission or issuance occurs.",
        "- `EXTRACTED-but-wrong` is counted only when a cell remains `EXTRACTED` after the existing arithmetic gate and its parsed value differs from the operator label. Any final verdict other than E-06 `REVIEW` or `REJECT` fails the acceptance gate.",
        "",
        "## Per-perturbation fail-closed rates",
        "",
        "| Perturbation | Runs | E-06 REVIEW | E-06 REJECT | REVIEW/REJECT rate | E-02 AUTO_CANDIDATE | E-02 REVIEW | E-02 REJECT | EXTRACTED-but-wrong | CORRECT | NOT-EXTRACTED |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in PERTURBATION_ORDER:
        result = rates[name]
        lines.append(
            f"| `{name}` | {result['runs']} | {result['e06_verdicts'].get('REVIEW', 0)} | "
            f"{result['e06_verdicts'].get('REJECT', 0)} | {result['fail_closed_rate']:.0%} | "
            f"{result['e02_statuses'].get('AUTO_CANDIDATE', 0)} | "
            f"{result['e02_statuses'].get('REVIEW', 0)} | "
            f"{result['e02_statuses'].get('REJECT', 0)} | {result['wrong']} | "
            f"{result['correct']} | {result['not_extracted']} |"
        )
    lines.extend(
        [
            "",
            "## Run-level results",
            "",
            "| Fixture | Perturbation | Applied modification | E-02 | E-05 | E-06 final verdict | CORRECT | NOT-EXTRACTED | EXTRACTED-but-wrong |",
            "|---|---|---|---|---|---|---:|---:|---:|",
        ]
    )
    for record in records:
        score = "—" if record["e05_score"] is None else f"{record['e05_score']:.3f}"
        lines.append(
            f"| {record['fixture']} | `{record['perturbation']}` | {record['injection']} | "
            f"{record['e02_status']} / {record['layout_status']} | "
            f"{record['e05_status']} ({score}) | {record['e06_verdict']} | "
            f"{record['correct']} | {record['not_extracted']} | {record['wrong']} |"
        )
    acceptance = (
        totals["wrong"] == 0
        and totals["accept"] == 0
        and totals["review"] + totals["reject"] == totals["runs"]
        and totals["input_changed"] == totals["runs"]
    )
    lines.extend(
        [
            "",
            "## Gate result",
            "",
            f"- Total injected runs: **{totals['runs']}**; all inputs changed: **{totals['input_changed']}/{totals['runs']}**.",
            f"- EXTRACTED-but-wrong: **{totals['wrong']}**; CORRECT: **{totals['correct']}**; NOT-EXTRACTED: **{totals['not_extracted']}**.",
            f"- Final E-06 verdicts: ACCEPT **{totals['accept']}**, REVIEW **{totals['review']}**, REJECT **{totals['reject']}**.",
            f"- Acceptance gate: **{'PASS' if acceptance else 'FAIL'}** (zero EXTRACTED-but-wrong and every injected case ends REVIEW/REJECT).",
            "",
            "## Method limits",
            "",
            "The four images are legacy labeled fixtures, not the E-03-kit-v3 Holo captures. The small blur/noise and pixel-shift trials are deterministic software perturbations, not measured physical scan variance. E-05 training uses the same four labeled invoices and therefore remains resubstitution evidence; E-06 is deliberately run with an unlocked bank and unsigned D14 agreement, and its REVIEW/REJECT outcomes must not be read as general accuracy or independent validation. Thresholds were not tuned.",
            "",
        ]
    )
    return "\n".join(lines)


def run_and_write_report(report_path: Path = REPORT_PATH) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
    records, totals = run_matrix()
    base_sha = "unknown"
    try:
        base_sha = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
        pass
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(records, totals, base_sha=base_sha), encoding="utf-8")
    acceptance = (
        totals["wrong"] == 0
        and totals["accept"] == 0
        and totals["review"] + totals["reject"] == totals["runs"]
        and totals["input_changed"] == totals["runs"]
    )
    return (0 if acceptance else 2), records, totals


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_PATH, help="Markdown report output path")
    args = parser.parse_args(argv)
    try:
        code, records, totals = run_and_write_report(args.report)
    except Exception as exc:
        print(f"E-15 robustness run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    rates = _verdict_rates(records)
    print(f"Report written: {args.report}")
    print(
        f"runs={totals['runs']} review={totals['review']} reject={totals['reject']} "
        f"accept={totals['accept']} extracted_wrong={totals['wrong']}"
    )
    for name in PERTURBATION_ORDER:
        result = rates[name]
        print(
            f"{name}: REVIEW/REJECT={result['fail_closed']}/{result['runs']} "
            f"({result['fail_closed_rate']:.0%}); EXTRACTED-but-wrong={result['wrong']}"
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
