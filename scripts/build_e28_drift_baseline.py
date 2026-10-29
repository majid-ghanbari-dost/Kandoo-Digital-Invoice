#!/usr/bin/env python3
"""Build a local, data-derived E-28 per-symbol Glyph drift baseline.

The default inputs are the repository's four operator-confirmed real invoice
fixtures. A deployment can pass its own already-accepted onboarding invoice
images; only their SHA-256 digests and aggregate distance metrics are written.
The synthetic controls are deterministic calibration checks, not genuine Probe
or printer/scanner observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

from image_extraction_adapter.drift_monitor import DRIFT_BASELINE_SCHEMA
from image_extraction_adapter.pipeline_v0 import (
    DEFAULT_GLYPH_DRIFT_BASELINE_PATH,
    DEFAULT_TEMPLATE_BANK_PATH,
    REPOSITORY_ROOT,
    extract_pipeline_v0,
)
from e28_drift_calibration import CLEAN_VARIANTS, STRESS_VARIANTS, apply_calibration_variant

DEFAULT_IMAGES = tuple(
    REPOSITORY_ROOT / "tests" / "fixtures" / "real" / f"{invoice_id}.png"
    for invoice_id in ("29", "31", "32", "33")
)
_FLOAT_TOLERANCE = 1e-8


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _measurement(result: Any, *, source: str) -> tuple[dict[str, float], dict[str, int]]:
    drift = getattr(result, "glyph_drift", None)
    if not isinstance(drift, dict):
        raise ValueError(f"DR-1 produced no glyph-distance record for {source}")
    symbol_records = drift.get("mean_distance_by_symbol")
    if not isinstance(symbol_records, dict) or not symbol_records:
        raise ValueError(f"DR-1 measured no symbols for {source}")
    means: dict[str, float] = {}
    counts: dict[str, int] = {}
    for symbol, record in symbol_records.items():
        if not isinstance(symbol, str) or not isinstance(record, dict):
            raise ValueError(f"DR-1 produced a malformed symbol record for {source}")
        mean = record.get("mean_distance")
        count = record.get("glyph_count")
        if (not isinstance(mean, (int, float)) or isinstance(mean, bool)
                or not isinstance(count, int) or isinstance(count, bool) or count <= 0):
            raise ValueError(f"DR-1 produced an invalid measurement for {source}, symbol {symbol!r}")
        means[symbol] = float(mean)
        counts[symbol] = count
    return means, counts


def build_baseline(
    images: Sequence[Path],
    *,
    templates_path: Path = DEFAULT_TEMPLATE_BANK_PATH,
    output_path: Path = DEFAULT_GLYPH_DRIFT_BASELINE_PATH,
) -> dict[str, Any]:
    if not images:
        raise ValueError("at least one onboarding image is required")
    if not templates_path.is_file():
        raise ValueError(f"Glyph template bank is missing: {templates_path}")
    for path in images:
        if not path.is_file():
            raise ValueError(f"onboarding image is missing: {path}")

    source_hashes = [_sha256(path) for path in images]
    identity: list[dict[str, Any]] = []
    clean_samples: list[tuple[str, dict[str, float], dict[str, int]]] = []
    stress_samples: dict[str, list[tuple[str, dict[str, float]]]] = {
        variant: [] for variant in STRESS_VARIANTS
    }

    with tempfile.TemporaryDirectory(prefix="e28-drift-calibration-") as temp:
        scratch = Path(temp)
        missing_baseline = scratch / "not-yet-built-baseline.json"
        for sample_index, image_path in enumerate(images, start=1):
            sample_id = f"onboarding-{sample_index:03d}"
            with Image.open(image_path) as opened:
                opened.load()
                original = opened.convert("RGB")
            for variant in CLEAN_VARIANTS:
                clean_image = apply_calibration_variant(original, variant)
                variant_path = scratch / f"{sample_id}-{variant}.png"
                clean_image.save(variant_path, format="PNG")
                result = extract_pipeline_v0(
                    variant_path,
                    templates_path=templates_path,
                    drift_baseline_path=missing_baseline,
                )
                means, counts = _measurement(result, source=f"{sample_id}/{variant}")
                clean_samples.append((variant, means, counts))
                if variant == "identity":
                    identity.append({
                        "sample_id": sample_id,
                        "sha256": source_hashes[sample_index - 1],
                        "means": means,
                        "counts": counts,
                    })
            for variant in STRESS_VARIANTS:
                degraded = apply_calibration_variant(original, variant)
                variant_path = scratch / f"{sample_id}-{variant}.png"
                degraded.save(variant_path, format="PNG")
                result = extract_pipeline_v0(
                    variant_path,
                    templates_path=templates_path,
                    drift_baseline_path=missing_baseline,
                )
                means, _ = _measurement(result, source=f"{sample_id}/{variant}")
                stress_samples[variant].append((sample_id, means))

    pooled: dict[str, list[float]] = defaultdict(list)
    glyph_counts: dict[str, int] = defaultdict(int)
    for sample in identity:
        for symbol, mean in sample["means"].items():
            pooled[symbol].append(mean)
            glyph_counts[symbol] += sample["counts"][symbol]
    if not pooled:
        raise ValueError("onboarding invoices yielded no per-symbol Glyph distances")

    baseline_means = {
        symbol: sum(per_invoice_means) / len(per_invoice_means)
        for symbol, per_invoice_means in pooled.items()
    }
    clean_bounds: dict[str, float] = {symbol: 0.0 for symbol in baseline_means}
    for _, means, _ in clean_samples:
        for symbol, mean in means.items():
            if symbol not in baseline_means:
                raise ValueError(f"clean control emitted an unseen symbol: {symbol!r}")
            clean_bounds[symbol] = max(
                clean_bounds[symbol], abs(mean - baseline_means[symbol]))

    stress_checks: dict[str, Any] = {}
    for variant, samples in stress_samples.items():
        triggered_samples = 0
        excesses: list[float] = []
        for sample_id, means in samples:
            sample_excesses = [
                abs(mean - baseline_means.get(symbol, 0.0)) - clean_bounds.get(symbol, 0.0)
                for symbol, mean in means.items()
                if symbol in baseline_means
                and abs(mean - baseline_means[symbol])
                > clean_bounds[symbol] + _FLOAT_TOLERANCE
            ]
            if sample_excesses:
                triggered_samples += 1
                excesses.extend(sample_excesses)
        if triggered_samples == 0:
            raise ValueError(
                f"synthetic stress {variant!r} did not exceed any measured clean-control bound")
        stress_checks[variant] = {
            "sample_count": len(samples),
            "triggered_sample_count": triggered_samples,
            "minimum_excess_over_bound": round(min(excesses), 8),
        }

    template_library_id = _sha256(templates_path)
    baseline_seed = "\n".join((template_library_id, *source_hashes)).encode("utf-8")
    baseline_id = "e28-" + hashlib.sha256(baseline_seed).hexdigest()[:20]
    symbols = {
        symbol: {
            "mean_distance": round(baseline_means[symbol], 8),
            "bound": round(clean_bounds[symbol], 8),
            "invoice_observation_count": len(pooled[symbol]),
            "glyph_observation_count": glyph_counts[symbol],
        }
        for symbol in sorted(baseline_means)
    }
    baseline = {
        "schema_version": DRIFT_BASELINE_SCHEMA,
        "baseline_id": baseline_id,
        "template_library_id": template_library_id,
        "metric": "equal-weight per-invoice mean GlyphReading.distance grouped by best_label",
        "source_images": [
            {"sample_id": item["sample_id"], "sha256": item["sha256"]}
            for item in identity
        ],
        "calibration": {
            "baseline_method": "equal-weight mean of each onboarding invoice's per-symbol mean",
            "bound_method": (
                "per-symbol maximum absolute deviation from baseline over all declared clean controls; "
                "trigger on strict greater-than with 1e-8 float-rounding tolerance"
            ),
            "clean_control_variants": list(CLEAN_VARIANTS),
            "clean_control_count": len(clean_samples),
            "synthetic_stress_checks": stress_checks,
            "synthetic_only_notice": (
                "Thinning, blur, and salt/pepper variants are deterministic test controls, "
                "not genuine printer/scanner observations."
            ),
        },
        "symbols": symbols,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(baseline, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return baseline


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images", nargs="+", type=Path, default=list(DEFAULT_IMAGES),
        help="already accepted local onboarding invoice images",
    )
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATE_BANK_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_GLYPH_DRIFT_BASELINE_PATH)
    args = parser.parse_args(argv)
    baseline = build_baseline(
        args.images,
        templates_path=args.templates,
        output_path=args.output,
    )
    print(json.dumps({
        "status": "BUILT",
        "baseline_id": baseline["baseline_id"],
        "symbols": len(baseline["symbols"]),
        "source_images": len(baseline["source_images"]),
        "stress_checks": baseline["calibration"]["synthetic_stress_checks"],
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
