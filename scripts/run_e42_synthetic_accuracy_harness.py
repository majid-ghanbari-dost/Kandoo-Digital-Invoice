#!/usr/bin/env python3
"""Measure E-02 numeric routing on held-out E-41 synthetic layouts only.

Training and evaluation rasters are generated at runtime from distinct seeds.
No repository invoice fixture, external image, or production template bank is
read. The timing column measures one in-process ``_execute_pipeline`` call per
known synthetic invoice; generation and synthetic-template training are outside
that per-invoice timing boundary.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import platform
from pathlib import Path
import statistics
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PIL import Image, __version__ as PILLOW_VERSION  # noqa: E402

from synthetic_layout_generator import (  # noqa: E402
    GENERATOR_VERSION,
    SYNTHETIC_MARKER,
    generate_dataset,
)
from image_extraction_adapter.glyph_classifier import (  # noqa: E402
    GlyphTemplateSet,
    LabeledCell,
    build_templates,
    normalize_label_text,
    parse_amount_text,
)
from image_extraction_adapter.layout_profiles import evaluate_profile_row  # noqa: E402
from image_extraction_adapter.pipeline_v0 import (  # noqa: E402
    REPOSITORY_ROOT,
    _execute_pipeline,
    _spatial_for_geometry,
    _source_records_from_bank,
    _template_set_sha256,
    detect_payable_bbox,
)
from image_extraction_adapter.preprocessing import (  # noqa: E402
    crop_spatial_cells,
    detect_dynamic_table_layout,
    detect_layout_safe,
)

TASK = "E-42"
TRAIN_SEED = 420031
EVALUATION_SEED = 420042
TRAIN_SAMPLE_COUNT = 8
EVALUATION_SAMPLE_COUNT = 8
KNOWN_LAYOUT_PROFILES = frozenset({
    "standard-v1",
    "wide-description-v1",
    "narrow-description-v1",
    "shifted-grid-v1",
})
ROUTE_STATUSES = ("EXTRACTED", "REVIEW", "BLOCKED")
FORBIDDEN_KEYS = frozenset({
    "address",
    "customer",
    "customer_name",
    "phone",
    "store_id",
})


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in FORBIDDEN_KEYS or _contains_forbidden_key(child)
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_synthetic_manifest(
    manifest: Mapping[str, Any], *, seed: int, count: int, output_dir: Path,
) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != GENERATOR_VERSION:
        raise AssertionError("E-41 generator version in manifest does not match the imported generator")
    if manifest.get("evidence_class") != "SYNTHETIC_ONLY":
        raise AssertionError("dataset is not explicitly marked SYNTHETIC_ONLY")
    if manifest.get("synthetic_marker") != SYNTHETIC_MARKER:
        raise AssertionError("dataset synthetic marker does not match E-41")
    if manifest.get("seed") != seed or manifest.get("sample_count") != count:
        raise AssertionError("generated manifest does not match the declared seed/count")
    if manifest.get("generator_inputs") != ["seed", "count"]:
        raise AssertionError("E-41 generator inputs changed unexpectedly")
    if manifest.get("external_input_sources") != []:
        raise AssertionError("E-42 accepts no external input sources")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or len(samples) != count:
        raise AssertionError("generated manifest has an incomplete sample inventory")

    clean_samples: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise AssertionError("E-41 sample entry must be a JSON object")
        if _contains_forbidden_key(sample):
            raise AssertionError("synthetic sample contains a prohibited customer/store field")
        sample_id = sample.get("sample_id")
        profile_id = sample.get("layout_profile")
        image_file = sample.get("image_file")
        image_sha = sample.get("image_sha256")
        if not isinstance(sample_id, str) or "SYNTHETIC" not in sample_id:
            raise AssertionError("sample ID is not visibly synthetic")
        if sample_id in seen_ids:
            raise AssertionError(f"duplicate synthetic sample ID: {sample_id}")
        seen_ids.add(sample_id)
        if not isinstance(profile_id, str) or not profile_id:
            raise AssertionError(f"{sample_id}: missing layout profile ID")
        if not isinstance(image_file, str) or Path(image_file).name != image_file:
            raise AssertionError(f"{sample_id}: invalid generated image filename")
        if not isinstance(image_sha, str) or len(image_sha) != 64:
            raise AssertionError(f"{sample_id}: invalid image SHA-256")
        image_path = output_dir / image_file
        if not image_path.is_file() or _sha256(image_path) != image_sha:
            raise AssertionError(f"{sample_id}: image bytes do not match manifest SHA-256")
        clean_samples.append(sample)
    return clean_samples


def _expected_numeric_values(sample: Mapping[str, Any]) -> dict[str, str]:
    rows = sample.get("line_items")
    if not isinstance(rows, list) or not rows:
        raise AssertionError(f"{sample.get('sample_id')}: no synthetic line items")
    expected: dict[str, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise AssertionError(f"{sample.get('sample_id')}: malformed line-item labels")
        for suffix, key in (("total", "line_total"), ("quantity", "quantity")):
            value = row.get(key)
            if type(value) is not int or value <= 0:
                raise AssertionError(f"{sample.get('sample_id')}: invalid integer label {key}")
            expected[f"line.{index}.{suffix}"] = str(value)
    payable = sample.get("payable_test_only")
    if type(payable) is not int or payable <= 0:
        raise AssertionError(f"{sample.get('sample_id')}: invalid synthetic payable label")
    expected["invoice.payable"] = str(payable)
    if sum(
        int(value) for field, value in expected.items()
        if field.endswith(".total")
    ) != payable:
        raise AssertionError(f"{sample.get('sample_id')}: manifest line sum disagrees with payable")
    return expected


def _train_synthetic_templates(
    samples: Sequence[Mapping[str, Any]], *, output_dir: Path, seed: int,
) -> tuple[GlyphTemplateSet, tuple[Mapping[str, Any], ...], dict[str, Any]]:
    templates = GlyphTemplateSet()
    template_sources: list[Mapping[str, Any]] = []
    profile_counts: Counter[str] = Counter()
    excluded_unknown_profiles: list[dict[str, str]] = []
    used_cell_count = 0
    skipped_cell_count = 0

    for sample in samples:
        sample_id = str(sample["sample_id"])
        profile_id = str(sample["layout_profile"])
        if profile_id not in KNOWN_LAYOUT_PROFILES:
            # Unknown synthetic profiles never enter the template bank.
            excluded_unknown_profiles.append({
                "sample_id": sample_id,
                "layout_profile": profile_id,
            })
            continue
        image_path = output_dir / str(sample["image_file"])
        with Image.open(image_path) as opened:
            opened.load()
            image = opened.convert("RGB")
        safety = detect_layout_safe(image)
        if safety.status != "OK" or safety.geometry is None:
            raise AssertionError(
                f"training sample {sample_id} did not have complete E-41 geometry: "
                f"{safety.status}: {safety.reason}"
            )
        payable_bbox = detect_payable_bbox(image, safety.geometry)
        if payable_bbox is None:
            raise AssertionError(f"training sample {sample_id}: synthetic payable crop was not found")
        spatial = _spatial_for_geometry(safety.geometry, payable_bbox)
        crops = crop_spatial_cells(
            image,
            spatial,
            include_descriptions=False,
            include_payable=True,
        )
        crops_by_field: dict[str, Any] = {}
        for crop in crops:
            if crop.field_name in crops_by_field:
                raise AssertionError(f"training sample {sample_id}: duplicate crop {crop.field_name}")
            crops_by_field[crop.field_name] = crop
        expected = _expected_numeric_values(sample)
        if set(crops_by_field) != set(expected):
            raise AssertionError(
                f"training sample {sample_id}: crop/label inventory mismatch; "
                f"missing={sorted(set(expected) - set(crops_by_field))}; "
                f"unexpected={sorted(set(crops_by_field) - set(expected))}"
            )
        labelled_cells = [
            LabeledCell(field_name, crops_by_field[field_name].image, value)
            for field_name, value in expected.items()
        ]
        templates, build_log = build_templates(labelled_cells, templates)
        used = sum(line.startswith("USED ") for line in build_log)
        skipped = len(build_log) - used
        if used != len(labelled_cells) or skipped:
            raise AssertionError(
                f"training sample {sample_id}: Glyph template builder used {used}/"
                f"{len(labelled_cells)} labelled numeric cells; skipped={skipped}"
            )
        used_cell_count += used
        skipped_cell_count += skipped
        profile_counts[profile_id] += 1
        image_sha = str(sample["image_sha256"])
        # Stable relative provenance is part of the template-library ID.
        templates.provenance.append({
            "image": str(sample["image_file"]),
            "sha256": image_sha,
            "synthetic_sample_id": sample_id,
        })
        # Absolute paths plus hashes are used only by the existing leakage guard.
        template_sources.append({
            "image": str(image_path.resolve()),
            "sha256": image_sha,
            "synthetic_sample_id": sample_id,
        })

    missing_profiles = sorted(KNOWN_LAYOUT_PROFILES - set(profile_counts))
    if missing_profiles:
        raise AssertionError(
            "synthetic training split does not cover all supported E-41 profiles: "
            + ", ".join(missing_profiles)
        )
    if not template_sources or not templates.profiles:
        raise AssertionError("no synthetic-only Glyph templates were built")

    sources = _source_records_from_bank({"provenance": list(template_sources)})
    summary = {
        "synthetic_only": True,
        "seed": seed,
        "generated_sample_count": len(samples),
        "known_profile_training_sample_count": sum(profile_counts.values()),
        "training_numeric_cells_used": used_cell_count,
        "training_numeric_cells_skipped": skipped_cell_count,
        "training_samples_by_layout": dict(sorted(profile_counts.items())),
        "excluded_unknown_profile_samples": excluded_unknown_profiles,
        "source_sample_ids": [str(source["synthetic_sample_id"]) for source in template_sources],
        "source_image_sha256": [str(source["sha256"]) for source in template_sources],
        "template_library_id": _template_set_sha256(templates),
        "thresholds_tuned": False,
    }
    return templates, sources, summary


def _route_pipeline_status(
    *,
    profile_id: str,
    pipeline_status: str,
    layout_status: str,
    all_expected_numeric_fields_extracted: bool,
) -> str:
    """Map E-02 results to the harness' invoice routes, with no profile guessing."""
    if profile_id not in KNOWN_LAYOUT_PROFILES:
        return "REVIEW"
    if layout_status == "REVIEW":
        return "REVIEW"
    if layout_status == "BLOCKED" or pipeline_status == "REJECT":
        return "BLOCKED"
    if layout_status != "OK" or pipeline_status == "REVIEW":
        return "REVIEW"
    if pipeline_status == "AUTO_CANDIDATE" and all_expected_numeric_fields_extracted:
        return "EXTRACTED"
    return "REVIEW"


def _evaluate_known_sample(
    sample: Mapping[str, Any], *,
    image_path: Path,
    templates: GlyphTemplateSet,
    template_sources: Sequence[Mapping[str, Any]],
    template_library_id: str,
) -> dict[str, Any]:
    sample_id = str(sample["sample_id"])
    profile_id = str(sample["layout_profile"])
    expected = _expected_numeric_values(sample)
    started = time.perf_counter()
    result = _execute_pipeline(
        image_path.resolve(),
        templates=templates,
        template_sources=template_sources,
        template_library_id=template_library_id,
        template_bank_path=None,
        captured_at=None,
        canonical_context=None,
        evaluation=True,
        repo_root=REPOSITORY_ROOT,
    )
    elapsed = time.perf_counter() - started
    if result.canonical_invoice is not None:
        raise AssertionError(f"{sample_id}: E-42 must not assemble a Canonical Invoice")

    cells_by_field: dict[str, Any] = {}
    for cell in result.cell_results:
        if cell.field_name in cells_by_field:
            raise AssertionError(f"{sample_id}: duplicate emitted numeric cell {cell.field_name}")
        cells_by_field[cell.field_name] = cell
    unexpected_fields = sorted(set(cells_by_field) - set(expected))
    missing_fields = sorted(set(expected) - set(cells_by_field))

    field_counts = {status: 0 for status in ROUTE_STATUSES}
    extracted_correct = 0
    extracted_comparisons = 0
    wrong_fields: list[str] = []
    for field_name, expected_text in expected.items():
        cell = cells_by_field.get(field_name)
        if cell is None:
            field_status = "BLOCKED" if result.status == "REJECT" else "REVIEW"
        else:
            field_status = cell.status
            if field_status not in ROUTE_STATUSES:
                raise AssertionError(f"{sample_id}: unsupported numeric-cell status {field_status!r}")
        field_counts[field_status] += 1
        if cell is None or cell.status != "EXTRACTED":
            continue
        extracted_comparisons += 1
        observed_value = parse_amount_text(normalize_label_text(cell.raw_value))
        expected_value = int(expected_text)
        if observed_value != expected_value:
            wrong_fields.append(field_name)
        else:
            extracted_correct += 1

    # An EXTRACTED value outside the generator's numeric answer key is also a
    # wrong extraction; it is never silently omitted from the score.
    unlabeled_extracted_fields = [
        field_name for field_name in unexpected_fields
        if cells_by_field[field_name].status == "EXTRACTED"
    ]
    wrong_fields.extend(unlabeled_extracted_fields)
    all_fields_extracted = (
        not missing_fields
        and not unexpected_fields
        and all(field_counts[status] == 0 for status in ("REVIEW", "BLOCKED"))
        and field_counts["EXTRACTED"] == len(expected)
    )
    invoice_status = _route_pipeline_status(
        profile_id=profile_id,
        pipeline_status=result.status,
        layout_status=result.layout_status,
        all_expected_numeric_fields_extracted=all_fields_extracted,
    )
    if invoice_status == "EXTRACTED" and not all_fields_extracted:
        raise AssertionError(f"{sample_id}: EXTRACTED invoice has incomplete numeric coverage")

    return {
        "sample_id": sample_id,
        "layout_profile": profile_id,
        "image_sha256": str(sample["image_sha256"]),
        "image_size": [int(sample["image_width"]), int(sample["image_height"])],
        "invoice_status": invoice_status,
        "pipeline_status": result.status,
        "layout_status": result.layout_status,
        "layout_reason": result.layout_reason,
        "row_count": result.row_count,
        "numeric_field_counts": field_counts,
        "expected_numeric_fields": len(expected),
        "emitted_numeric_fields": len(cells_by_field),
        "missing_numeric_fields": missing_fields,
        "unexpected_numeric_fields": unexpected_fields,
        "extracted_correct": extracted_correct,
        "extracted_label_comparisons": extracted_comparisons,
        "extracted_but_wrong": len(wrong_fields),
        "wrong_fields": wrong_fields,
        "arithmetic_gate_passed": (
            bool(result.arithmetic_gate and result.arithmetic_gate.passed)
        ),
        "canonical_invoice_created": result.canonical_invoice is not None,
        "reason": result.reason,
        "per_invoice_seconds": round(elapsed, 6),
        "timing_scope": "one in-process _execute_pipeline call; excludes generation and template training",
    }


def _evaluate_unknown_profile_control() -> dict[str, Any]:
    # This is a profile-registry routing control, not an OCR measurement. The
    # E-24 exact-ID evaluator and the E-42 harness gate must both hold an
    # unregistered synthetic profile for REVIEW before any field is extracted.
    profile_id = "unregistered-synthetic-layout-v99"
    probe = evaluate_profile_row(
        profile_id,
        ["1000", "1", "SYNTHETIC UNKNOWN LAYOUT", "1"],
        currency_unit="rial",
    )
    routed = _route_pipeline_status(
        profile_id=profile_id,
        pipeline_status="AUTO_CANDIDATE",
        layout_status="OK",
        all_expected_numeric_fields_extracted=True,
    )
    if probe.status != "REVIEW" or routed != "REVIEW":
        raise AssertionError("unknown synthetic layout did not fail closed to REVIEW")
    return {
        "control": "unknown-layout-profile",
        "layout_profile": profile_id,
        "e24_profile_status": probe.status,
        "harness_route": routed,
        "pipeline_invoked": False,
        "counted_in_accuracy_metrics": False,
        "reason": probe.reason,
    }


def _evaluate_low_confidence_control(
    sample: Mapping[str, Any], *,
    output_dir: Path,
    templates: GlyphTemplateSet,
    template_sources: Sequence[Mapping[str, Any]],
    template_library_id: str,
) -> dict[str, Any]:
    image_path = output_dir / str(sample["image_file"])
    with Image.open(image_path) as opened:
        opened.load()
        image = opened.convert("RGB")
    geometry = detect_dynamic_table_layout(image)
    if geometry is None or len(geometry.vertical_lines) != 5:
        raise AssertionError("low-confidence control source has no complete synthetic E-41 geometry")
    # Simulate a projection detector returning incomplete geometry. The image
    # remains an E-41 synthetic raster; this routing probe is intentionally not
    # counted as a natural detector-accuracy sample.
    low_confidence_geometry = geometry.__class__(
        column_boundaries=geometry.column_boundaries,
        row_bands=geometry.row_bands,
        horizontal_lines=geometry.horizontal_lines,
        vertical_lines=geometry.vertical_lines[:-1],
        median_row_height=geometry.median_row_height,
        header_row_excluded=geometry.header_row_excluded,
    )
    with patch(
        "image_extraction_adapter.preprocessing.detect_dynamic_table_layout",
        return_value=low_confidence_geometry,
    ):
        result = _execute_pipeline(
            image_path.resolve(),
            templates=templates,
            template_sources=template_sources,
            template_library_id=template_library_id,
            template_bank_path=None,
            captured_at=None,
            canonical_context=None,
            evaluation=True,
            repo_root=REPOSITORY_ROOT,
        )
    routed = _route_pipeline_status(
        profile_id=str(sample["layout_profile"]),
        pipeline_status=result.status,
        layout_status=result.layout_status,
        all_expected_numeric_fields_extracted=False,
    )
    if result.layout_status != "REVIEW" or result.status != "REVIEW" or routed != "REVIEW":
        raise AssertionError(
            "incomplete synthetic layout geometry did not route to REVIEW: "
            f"pipeline={result.status}, layout={result.layout_status}, route={routed}"
        )
    return {
        "control": "low-confidence-layout-geometry",
        "source_sample_id": str(sample["sample_id"]),
        "synthetic_image_sha256": str(sample["image_sha256"]),
        "detector_geometry_override": "one of five vertical boundaries withheld",
        "pipeline_status": result.status,
        "layout_status": result.layout_status,
        "route": routed,
        "pipeline_invoked": True,
        "counted_in_accuracy_metrics": False,
        "reason": result.reason,
    }


def _counts() -> dict[str, int]:
    return {status: 0 for status in ROUTE_STATUSES}


def _summarize_by_layout(
    outcomes: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_profile: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in outcomes:
        by_profile[str(item["layout_profile"])].append(item)

    layouts: list[dict[str, Any]] = []
    for profile_id in sorted(set(by_profile) | set(KNOWN_LAYOUT_PROFILES)):
        items = by_profile.get(profile_id, [])
        invoice_counts = _counts()
        field_counts = _counts()
        extracted_correct = 0
        extracted_comparisons = 0
        expected_numeric_fields = 0
        wrong = 0
        for item in items:
            invoice_counts[str(item["invoice_status"])] += 1
            for status in ROUTE_STATUSES:
                field_counts[status] += int(item["numeric_field_counts"][status])
            extracted_correct += int(item["extracted_correct"])
            extracted_comparisons += int(item["extracted_label_comparisons"])
            expected_numeric_fields += int(item["expected_numeric_fields"])
            wrong += int(item["extracted_but_wrong"])
        accuracy = (
            round(100.0 * extracted_correct / extracted_comparisons, 2)
            if extracted_comparisons else None
        )
        coverage = (
            round(100.0 * field_counts["EXTRACTED"] / expected_numeric_fields, 2)
            if expected_numeric_fields else None
        )
        layouts.append({
            "layout_profile": profile_id,
            "sample_count": len(items),
            "expected_numeric_fields": expected_numeric_fields,
            "invoice_status_counts": invoice_counts,
            "numeric_field_counts": field_counts,
            "extracted_field_coverage_percent": coverage,
            "extracted_correct": extracted_correct,
            "extracted_label_comparisons": extracted_comparisons,
            "extracted_value_accuracy_percent": accuracy,
            "extracted_but_wrong": wrong,
            "per_invoice_status": [
                {"sample_id": item["sample_id"], "status": item["invoice_status"]}
                for item in items
            ],
        })

    overall_invoice_counts = _counts()
    overall_field_counts = _counts()
    total_correct = total_comparisons = total_expected = total_wrong = 0
    for item in outcomes:
        overall_invoice_counts[str(item["invoice_status"])] += 1
        for status in ROUTE_STATUSES:
            overall_field_counts[status] += int(item["numeric_field_counts"][status])
        total_correct += int(item["extracted_correct"])
        total_comparisons += int(item["extracted_label_comparisons"])
        total_expected += int(item["expected_numeric_fields"])
        total_wrong += int(item["extracted_but_wrong"])
    overall_accuracy = (
        round(100.0 * total_correct / total_comparisons, 2)
        if total_comparisons else None
    )
    extracted_coverage = (
        round(100.0 * overall_field_counts["EXTRACTED"] / total_expected, 2)
        if total_expected else None
    )
    aggregate = {
        "evaluation_invoice_outcomes": overall_invoice_counts,
        "evaluation_numeric_field_outcomes": overall_field_counts,
        "expected_numeric_fields": total_expected,
        "extracted_field_coverage_percent": extracted_coverage,
        "extracted_correct": total_correct,
        "extracted_label_comparisons": total_comparisons,
        "extracted_value_accuracy_percent": overall_accuracy,
        "extracted_but_wrong": total_wrong,
    }
    return layouts, aggregate


def run_harness(
    *,
    train_seed: int = TRAIN_SEED,
    evaluation_seed: int = EVALUATION_SEED,
    train_count: int = TRAIN_SAMPLE_COUNT,
    evaluation_count: int = EVALUATION_SAMPLE_COUNT,
) -> dict[str, Any]:
    if train_seed == evaluation_seed:
        raise ValueError("training and evaluation seeds must differ")
    if train_count < len(KNOWN_LAYOUT_PROFILES) or train_count % len(KNOWN_LAYOUT_PROFILES):
        raise ValueError("train_count must be a positive multiple of the four E-41 profiles")
    if evaluation_count < len(KNOWN_LAYOUT_PROFILES) or evaluation_count % len(KNOWN_LAYOUT_PROFILES):
        raise ValueError("evaluation_count must be a positive multiple of the four E-41 profiles")

    with tempfile.TemporaryDirectory(prefix="kandoo-e42-synthetic-") as temporary:
        work = Path(temporary)
        train_dir = work / "train"
        evaluation_dir = work / "evaluation"
        train_manifest = generate_dataset(train_dir, seed=train_seed, count=train_count)
        evaluation_manifest = generate_dataset(
            evaluation_dir,
            seed=evaluation_seed,
            count=evaluation_count,
        )
        training_samples = _validate_synthetic_manifest(
            train_manifest,
            seed=train_seed,
            count=train_count,
            output_dir=train_dir,
        )
        evaluation_samples = _validate_synthetic_manifest(
            evaluation_manifest,
            seed=evaluation_seed,
            count=evaluation_count,
            output_dir=evaluation_dir,
        )
        train_hashes = {str(item["image_sha256"]) for item in training_samples}
        eval_hashes = {str(item["image_sha256"]) for item in evaluation_samples}
        if train_hashes & eval_hashes:
            raise AssertionError("synthetic training/evaluation image SHA-256 sets overlap")
        train_ids = {str(item["sample_id"]) for item in training_samples}
        eval_ids = {str(item["sample_id"]) for item in evaluation_samples}
        if train_ids & eval_ids:
            raise AssertionError("synthetic training/evaluation sample IDs overlap")

        templates, template_sources, training_summary = _train_synthetic_templates(
            training_samples,
            output_dir=train_dir,
            seed=train_seed,
        )
        template_library_id = str(training_summary["template_library_id"])

        known_evaluation_samples = [
            item for item in evaluation_samples
            if str(item["layout_profile"]) in KNOWN_LAYOUT_PROFILES
        ]
        if set(str(item["layout_profile"]) for item in known_evaluation_samples) != KNOWN_LAYOUT_PROFILES:
            raise AssertionError("held-out synthetic evaluation does not cover all four known layouts")

        outcomes: list[dict[str, Any]] = []
        for sample in evaluation_samples:
            profile_id = str(sample["layout_profile"])
            if profile_id in KNOWN_LAYOUT_PROFILES:
                outcomes.append(_evaluate_known_sample(
                    sample,
                    image_path=evaluation_dir / str(sample["image_file"]),
                    templates=templates,
                    template_sources=template_sources,
                    template_library_id=template_library_id,
                ))
            else:
                # Unknown future E-41 profiles are held before OCR and counted
                # as REVIEW, never trained or scored as extracted values.
                expected_count = len(_expected_numeric_values(sample))
                outcomes.append({
                    "sample_id": str(sample["sample_id"]),
                    "layout_profile": profile_id,
                    "image_sha256": str(sample["image_sha256"]),
                    "image_size": [int(sample["image_width"]), int(sample["image_height"])],
                    "invoice_status": "REVIEW",
                    "pipeline_status": "NOT_RUN_UNKNOWN_PROFILE",
                    "layout_status": "REVIEW",
                    "layout_reason": "No exact synthetic layout profile is registered; profile guessing is disabled.",
                    "row_count": len(sample.get("line_items", [])),
                    "numeric_field_counts": {"EXTRACTED": 0, "REVIEW": expected_count, "BLOCKED": 0},
                    "expected_numeric_fields": expected_count,
                    "emitted_numeric_fields": 0,
                    "missing_numeric_fields": sorted(_expected_numeric_values(sample)),
                    "unexpected_numeric_fields": [],
                    "extracted_correct": 0,
                    "extracted_label_comparisons": 0,
                    "extracted_but_wrong": 0,
                    "wrong_fields": [],
                    "arithmetic_gate_passed": False,
                    "reason": "Unknown synthetic profile was routed to REVIEW before OCR.",
                    "per_invoice_seconds": None,
                    "timing_scope": "not measured; unknown profile was held before OCR",
                })

        unknown_control = _evaluate_unknown_profile_control()
        if not known_evaluation_samples:
            raise AssertionError("no known synthetic evaluation samples were measured")
        low_confidence_control = _evaluate_low_confidence_control(
            known_evaluation_samples[0],
            output_dir=evaluation_dir,
            templates=templates,
            template_sources=template_sources,
            template_library_id=template_library_id,
        )
        layouts, aggregate = _summarize_by_layout(outcomes)
        measured_times = [
            float(item["per_invoice_seconds"])
            for item in outcomes
            if item["per_invoice_seconds"] is not None
        ]
        if aggregate["extracted_label_comparisons"] == 0:
            accuracy_evidence_status = "NOT_MEASURED_NO_EXTRACTED_LABELS"
        else:
            accuracy_evidence_status = "MEASURED"

        all_controls_review = (
            unknown_control["harness_route"] == "REVIEW"
            and unknown_control["e24_profile_status"] == "REVIEW"
            and low_confidence_control["route"] == "REVIEW"
        )
        status = (
            "PASS"
            if aggregate["extracted_but_wrong"] == 0
            and aggregate["extracted_label_comparisons"] > 0
            and all_controls_review
            and training_summary["training_numeric_cells_skipped"] == 0
            else "FAIL"
        )
        return {
            "task": TASK,
            "status": status,
            "synthetic_only": True,
            "evidence_class": "SYNTHETIC_ONLY",
            "synthetic_marker": SYNTHETIC_MARKER,
            "generator": GENERATOR_VERSION,
            "external_input_sources": [],
            "real_invoice_fixtures_read": False,
            "network_access_used": False,
            "external_ocr_service_used": False,
            "local_glyph_classifier_used": True,
            "thresholds_tuned": False,
            "evaluation_method": (
                "Seed-separated E-41 synthetic-only training and evaluation. Glyph templates are built "
                "only from the training-seed images; each evaluation image is checked against those "
                "synthetic labels, and the existing provenance leakage guard is active. Harness-local "
                "EXTRACTED maps E-02 AUTO_CANDIDATE; no Canonical Invoice is assembled. EXTRACTED-value "
                "accuracy is computed only over numeric fields the pipeline actually marks EXTRACTED."
            ),
            "scope_note": (
                "این rasterهای قطعیِ Pillow فقط سازوکار adapter و harness را می‌آزمایند؛ فاکتور مشتری، "
                "تصویر Holoo یا شاهد دقت production نیستند و تعمیم به layoutهای بیرون از چهار profile "
                "مولد E-41 را اثبات نمی‌کنند. `EXTRACTED` در این گزارش برچسب محلیِ route برای `AUTO_CANDIDATE` "
                "در E-02 است؛ Canonical Invoice ساخته نمی‌شود. حداقل پوشش استخراج تعیین نشده است؛ شمارش‌ها "
                "بدون تغییر thresholdهای Glyph گزارش می‌شوند. کنترل profile ناشناخته در مرز profile-ID و کنترل "
                "confidence با geometry کم‌اطمینانِ تزریق‌شده انجام می‌شود؛ هیچ‌کدام وارد denominator دقت نیستند."
            ),
            "training": training_summary,
            "evaluation": {
                "seed": evaluation_seed,
                "sample_count": len(evaluation_samples),
                "known_layout_sample_count": len(known_evaluation_samples),
                "evaluation_samples_by_layout": dict(sorted(Counter(
                    str(item["layout_profile"]) for item in evaluation_samples
                ).items())),
                "source_sample_ids": [str(item["sample_id"]) for item in evaluation_samples],
                "source_image_sha256": [str(item["image_sha256"]) for item in evaluation_samples],
                "accuracy_evidence_status": accuracy_evidence_status,
                "known_layouts": layouts,
                "invoice_outcomes": outcomes,
            },
            "routing_controls": {
                "unknown_profile": unknown_control,
                "low_confidence_geometry": low_confidence_control,
                "all_routed_to_review": all_controls_review,
            },
            "aggregate": {
                **aggregate,
                "accuracy_evidence_status": accuracy_evidence_status,
                "per_invoice_seconds": measured_times,
                "per_invoice_seconds_median": round(statistics.median(measured_times), 6)
                if measured_times else None,
                "per_invoice_seconds_min": round(min(measured_times), 6) if measured_times else None,
                "per_invoice_seconds_max": round(max(measured_times), 6) if measured_times else None,
            },
            "timing_environment": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "python": platform.python_version(),
                "pillow": PILLOW_VERSION,
                "measurement": (
                    "Wall-clock seconds for one in-process _execute_pipeline call per known evaluation "
                    "invoice, including local image read/hash, layout detection, numeric Glyph pass, "
                    "arithmetic gate, and description sidecar clustering; excludes generator, template "
                    "training, process startup, and report serialization."
                ),
            },
        }


def render_markdown(report: Mapping[str, Any]) -> str:
    aggregate = report.get("aggregate", {})
    training = report.get("training", {})
    evaluation = report.get("evaluation", {})
    layouts = evaluation.get("known_layouts", [])
    lines = [
        "# گزارش E-42 — harness دقت layout مصنوعی",
        "",
        f"- **نتیجه:** {report.get('status', 'نامشخص')}",
        "- **داده:** فقط rasterهای تولیدشده با E-41؛ بدون fixture واقعی، منبع بیرونی یا سرویس OCR/network.",
        f"- **مولد:** `{report.get('generator', 'نامشخص')}`؛ seed آموزش `{training.get('seed', TRAIN_SEED)}` و seed ارزیابی `{evaluation.get('seed', EVALUATION_SEED)}`.",
        f"- **آموزش:** {training.get('known_profile_training_sample_count', 0)} تصویر synthetic؛ "
        f"{training.get('training_numeric_cells_used', 0)} سلول برچسب‌دار استفاده‌شده؛ "
        f"{training.get('training_numeric_cells_skipped', 0)} سلول ردشده.",
        f"- **ارزیابی held-out:** {evaluation.get('sample_count', 0)} تصویر synthetic؛ "
        f"EXTRACTED-but-wrong = **{aggregate.get('extracted_but_wrong', 'ناموجود')}**.",
        f"- **دقت شرطیِ مقدارهای واقعاً EXTRACTED:** "
        f"{aggregate.get('extracted_correct', 0)}/{aggregate.get('extracted_label_comparisons', 0)} "
        f"({aggregate.get('extracted_value_accuracy_percent') if aggregate.get('extracted_value_accuracy_percent') is not None else 'اندازه‌گیری‌نشده'}%). "
        f"**پوشش فیلدها:** {aggregate.get('evaluation_numeric_field_outcomes', {}).get('EXTRACTED', 0)}/"
        f"{aggregate.get('expected_numeric_fields', 0)} "
        f"({aggregate.get('extracted_field_coverage_percent') if aggregate.get('extracted_field_coverage_percent') is not None else 'اندازه‌گیری‌نشده'}%).",
        f"- **تنظیم threshold:** `{report.get('thresholds_tuned', 'ناموجود')}`.",
        "",
        "| چیدمان | نمونه | فاکتور EXTRACTED | فاکتور REVIEW | فاکتور BLOCKED | فیلد EXTRACTED | فیلد REVIEW | فیلد BLOCKED | پوشش فیلد | EXTRACTED درست/مقایسه | EXTRACTED غلط |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in layouts:
        invoice_counts = item.get("invoice_status_counts", {})
        field_counts = item.get("numeric_field_counts", {})
        lines.append(
            f"| `{item.get('layout_profile')}` | {item.get('sample_count', 0)} | "
            f"{invoice_counts.get('EXTRACTED', 0)} | {invoice_counts.get('REVIEW', 0)} | "
            f"{invoice_counts.get('BLOCKED', 0)} | {field_counts.get('EXTRACTED', 0)} | "
            f"{field_counts.get('REVIEW', 0)} | {field_counts.get('BLOCKED', 0)} | "
            f"{field_counts.get('EXTRACTED', 0)}/{item.get('expected_numeric_fields', 0)} "
            f"({item.get('extracted_field_coverage_percent') if item.get('extracted_field_coverage_percent') is not None else 'n/a'}%) | "
            f"{item.get('extracted_correct', 0)}/{item.get('extracted_label_comparisons', 0)} | "
            f"{item.get('extracted_but_wrong', 0)} |"
        )
    lines.extend([
        "",
        f"## نتیجه به‌ازای هر فاکتور و زمان‌گیری در {report.get('timing_environment', {}).get('system', 'محیط اجرا')}",
        "",
        "زمان هر ردیف، زمان دیواری یک فراخوانی in-process از `_execute_pipeline` است؛ تولید تصویر، ساخت template، startup و نوشتن گزارش در آن نیست.",
        "",
        "| شناسه نمونه | Layout | نتیجه | فیلدهای E/R/B | مقدار EXTRACTED غلط | ثانیه در محیط اجرا |",
        "|---|---|---|---|---:|---:|",
    ])
    for item in evaluation.get("invoice_outcomes", []):
        field_counts = item.get("numeric_field_counts", {})
        elapsed = item.get("per_invoice_seconds")
        lines.append(
            f"| `{item.get('sample_id')}` | `{item.get('layout_profile')}` | "
            f"{item.get('invoice_status')} | "
            f"{field_counts.get('EXTRACTED', 0)}/{field_counts.get('REVIEW', 0)}/"
            f"{field_counts.get('BLOCKED', 0)} | {item.get('extracted_but_wrong', 0)} | "
            f"{elapsed if elapsed is not None else 'اندازه‌گیری‌نشده'} |"
        )
    lines.extend([
        "",
        "## کنترل‌های مسیردهی",
        "",
        "| کنترل synthetic | نتیجه | اجرا/شمارش |",
        "|---|---|---|",
    ])
    controls = report.get("routing_controls", {})
    unknown = controls.get("unknown_profile", {})
    low = controls.get("low_confidence_geometry", {})
    lines.append(
        f"| profile ناشناخته `{unknown.get('layout_profile', 'ناموجود')}` | "
        f"E-24={unknown.get('e24_profile_status', 'ناموجود')}؛ harness={unknown.get('harness_route', 'ناموجود')} | "
        f"pipeline اجرا نشد؛ خارج از accuracy denominator |"
    )
    lines.append(
        f"| geometry کم‌اطمینان از تصویر `{low.get('source_sample_id', 'ناموجود')}` | "
        f"layout={low.get('layout_status', 'ناموجود')}؛ route={low.get('route', 'ناموجود')} | "
        "یک مرز عمودی در detector override شد؛ خارج از accuracy denominator |"
    )
    lines.extend([
        "",
        "### محدودهٔ ادعا",
        "",
        str(report.get("scope_note", "")),
        "",
    ])
    return "\n".join(lines)


def _write_outputs(
    report: Mapping[str, Any], *, report_json: Path | None, report_md: Path | None,
) -> None:
    if report_json is not None:
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if report_md is not None:
        report_md.parent.mkdir(parents=True, exist_ok=True)
        report_md.write_text(render_markdown(report), encoding="utf-8")
    if report_json is None and report_md is None:
        print(render_markdown(report), end="")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", type=Path, help="write machine-readable evidence JSON")
    parser.add_argument("--report-md", type=Path, help="write the Persian evidence summary")
    parser.add_argument("--train-seed", type=int, default=TRAIN_SEED)
    parser.add_argument("--evaluation-seed", type=int, default=EVALUATION_SEED)
    parser.add_argument("--train-count", type=int, default=TRAIN_SAMPLE_COUNT)
    parser.add_argument("--evaluation-count", type=int, default=EVALUATION_SAMPLE_COUNT)
    args = parser.parse_args(argv)
    try:
        report = run_harness(
            train_seed=args.train_seed,
            evaluation_seed=args.evaluation_seed,
            train_count=args.train_count,
            evaluation_count=args.evaluation_count,
        )
    except Exception as exc:
        report = {
            "task": TASK,
            "status": "FAIL",
            "synthetic_only": True,
            "evidence_class": "SYNTHETIC_ONLY",
            "external_input_sources": [],
            "real_invoice_fixtures_read": False,
            "thresholds_tuned": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    _write_outputs(report, report_json=args.report_json, report_md=args.report_md)
    if report.get("status") != "PASS":
        print(f"E-42 {report.get('status')}: {report.get('error', 'acceptance conditions not met')}", file=sys.stderr)
        return 1
    print(
        f"PASS E-42: synthetic evaluation samples={report['evaluation']['sample_count']} "
        f"EXTRACTED-but-wrong={report['aggregate']['extracted_but_wrong']} "
        f"timing_os={report['timing_environment']['system']} "
        "timing_scope=in-process pipeline"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
