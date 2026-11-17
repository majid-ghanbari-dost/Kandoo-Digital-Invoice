#!/usr/bin/env python3
"""Measure offline product-name clustering with aHash and dHash.

The script uses only Pillow and the supplied row geometry. It does not run
OCR: the known repeated-name pairs are used only for scoring, after manual
visual mapping to row indices. Projection geometry is checked against the
four T2 receipt fixtures before any crops are made.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageOps
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("Pillow is required; use /tmp/kandoo-t2-venv/bin/python") from exc

from image_extraction_adapter.preprocessing import detect_dynamic_table_layout


REPO_ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20)
NORMALIZED_SIZE = (64, 16)
NON_WHITE_CUTOFF = 245
# T2's RTL table schema is amount, quantity, product description, row number.
DESCRIPTION_LEFT_BOUNDARY_INDEX = 2
DESCRIPTION_RIGHT_BOUNDARY_INDEX = 3
# Exclude the projected rule edges while keeping all interior product-name ink.
X_INSET = 4
TOP_INSET = 8
BOTTOM_INSET = 3

# Visually mapped against the user-supplied unconfirmed name list. These labels
# are never consulted by hashing or clustering, only by the evaluation metrics.
GROUND_TRUTH_GROUPS: dict[str, tuple[str, str]] = {
    "A (دستمال سفره تم)": ("31_row0", "32_row0"),
    "B (رد پا یا فلش تم)": ("31_row1", "32_row3"),
    "C (خلال کوچک)": ("31_row2", "33_row1"),
}


@dataclass(frozen=True)
class CropRecord:
    crop_id: str
    invoice_id: str
    row_index: int
    source_bbox: tuple[int, int, int, int]
    text_bbox: tuple[int, int, int, int]
    ahash: int
    dhash: int


@dataclass(frozen=True)
class SweepResult:
    algorithm: str
    threshold: int
    clusters: tuple[tuple[str, ...], ...]
    correct_groups: tuple[str, ...]
    wrong_merges: int
    mixed_cluster_names: tuple[str, ...]

    @property
    def cluster_count(self) -> int:
        return len(self.clusters)

    @property
    def correct_merge_count(self) -> int:
        return len(self.correct_groups)


@dataclass(frozen=True)
class InvoiceGeometry:
    invoice_id: str
    image_size: tuple[int, int]
    boundaries: tuple[float, ...]
    detected_row_bands: tuple[tuple[float, float], ...]
    label_row_bands: tuple[tuple[float, float], ...]
    description_x: tuple[float, float]


def _crop_id(invoice_id: str, row_index: int) -> str:
    return f"{invoice_id}_row{row_index}"


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _ahash(image: Any) -> int:
    resampling = getattr(Image, "Resampling", Image)
    small = ImageOps.grayscale(image).resize((8, 8), resampling.LANCZOS)
    values = list(small.tobytes())
    mean = sum(values) / len(values)
    result = 0
    for index, value in enumerate(values):
        if value < mean:
            result |= 1 << (63 - index)
    return result


def _dhash(image: Any) -> int:
    resampling = getattr(Image, "Resampling", Image)
    small = ImageOps.grayscale(image).resize((9, 8), resampling.LANCZOS)
    values = list(small.tobytes())
    result = 0
    bit_index = 0
    for y in range(8):
        for x in range(8):
            left = values[y * 9 + x]
            right = values[y * 9 + x + 1]
            if left > right:
                result |= 1 << (63 - bit_index)
            bit_index += 1
    return result


def _read_and_validate_inputs(labels_path: Path) -> tuple[dict[str, Any], Path]:
    data = json.loads(labels_path.read_text(encoding="utf-8"))
    if data.get("label_status") != "OPERATOR_CONFIRMED":
        raise ValueError("labels.json must have label_status=OPERATOR_CONFIRMED")
    invoices = data.get("invoices")
    if not isinstance(invoices, list) or len(invoices) != 4:
        raise ValueError("labels.json must contain exactly four invoices")
    ids = [str(entry.get("id")) for entry in invoices]
    if len(set(ids)) != 4 or set(ids) != {"29", "31", "32", "33"}:
        raise ValueError("labels.json must contain unique invoices 29, 31, 32, 33")
    return data, labels_path.parent


def _geometry_for_invoice(entry: dict[str, Any], image_path: Path) -> InvoiceGeometry:
    with Image.open(image_path) as opened:
        opened.load()
        layout = detect_dynamic_table_layout(opened)
        image_size = opened.size
    if layout is None:
        raise RuntimeError(f"projection detector returned no layout for {image_path}")
    if len(layout.column_boundaries) != 5:
        raise RuntimeError(f"expected five projected column boundaries for {image_path}")

    labels_bands = tuple(
        (float(band[0]), float(band[1])) for band in entry["row_bands"]
    )
    detected_bands = tuple(
        (float(band[0]), float(band[1])) for band in layout.row_bands
    )
    if len(detected_bands) != int(entry["row_count"]):
        raise RuntimeError(
            f"projection row count mismatch for #{entry['id']}: "
            f"detected {len(detected_bands)}, labeled {entry['row_count']}"
        )
    if len(labels_bands) != len(detected_bands):
        raise RuntimeError(f"row-band count mismatch for #{entry['id']}")
    if any(
        abs(detected_edge - label_edge) > 1.0
        for detected, labeled in zip(detected_bands, labels_bands)
        for detected_edge, label_edge in zip(detected, labeled)
    ):
        raise RuntimeError(f"projection and T2 label row bands differ for #{entry['id']}")

    boundaries = tuple(float(value) for value in layout.column_boundaries)
    label_boundaries = tuple(float(value) for value in entry["column_boundaries"])
    if len(label_boundaries) != 5 or any(
        abs(detected - labeled) > 1.0
        for detected, labeled in zip(boundaries, label_boundaries)
    ):
        raise RuntimeError(f"projection and T2 label columns differ for #{entry['id']}")

    description_x = (
        boundaries[DESCRIPTION_LEFT_BOUNDARY_INDEX],
        boundaries[DESCRIPTION_RIGHT_BOUNDARY_INDEX],
    )
    return InvoiceGeometry(
        invoice_id=str(entry["id"]),
        image_size=image_size,
        boundaries=boundaries,
        detected_row_bands=detected_bands,
        label_row_bands=labels_bands,
        description_x=description_x,
    )


def _normalize_crop(crop: Any) -> tuple[Any, tuple[int, int, int, int]]:
    gray = ImageOps.grayscale(crop)
    ink_mask = gray.point(lambda value: 255 if value < NON_WHITE_CUTOFF else 0)
    bbox = ink_mask.getbbox()
    if bbox is None:
        raise ValueError("description cell contains no non-white pixels")
    text = gray.crop(bbox)
    resampling = getattr(Image, "Resampling", Image)
    normalized = text.resize(NORMALIZED_SIZE, resampling.LANCZOS)
    return normalized, tuple(int(value) for value in bbox)


def _make_crops(
    invoices: list[dict[str, Any]],
    labels_dir: Path,
    crop_dir: Path,
) -> tuple[list[CropRecord], list[InvoiceGeometry]]:
    crop_dir.mkdir(parents=True, exist_ok=True)
    records: list[CropRecord] = []
    geometries: list[InvoiceGeometry] = []

    for entry in invoices:
        image_path = (labels_dir / entry["path"]).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"invoice image does not exist: {image_path}")
        geometry = _geometry_for_invoice(entry, image_path)
        geometries.append(geometry)
        left, right = geometry.description_x
        with Image.open(image_path) as opened:
            opened.load()
            gray = ImageOps.grayscale(opened)
            for row_index, (top, bottom) in enumerate(geometry.label_row_bands):
                box = (
                    int(round(left)) + X_INSET,
                    int(round(top)) + TOP_INSET,
                    int(round(right)) - X_INSET,
                    int(round(bottom)) - BOTTOM_INSET,
                )
                if box[2] <= box[0] or box[3] <= box[1]:
                    raise ValueError(f"empty description crop for #{entry['id']} row {row_index}")
                normalized, text_bbox = _normalize_crop(gray.crop(box))
                crop_id = _crop_id(str(entry["id"]), row_index)
                normalized.save(crop_dir / f"{crop_id}.png")
                records.append(CropRecord(
                    crop_id=crop_id,
                    invoice_id=str(entry["id"]),
                    row_index=row_index,
                    source_bbox=box,
                    text_bbox=text_bbox,
                    ahash=_ahash(normalized),
                    dhash=_dhash(normalized),
                ))
    if len(records) != 25:
        raise RuntimeError(f"expected 25 description crops; created {len(records)}")
    return records, geometries


def _ground_truth_labels(crop_ids: list[str]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for group_name, pair in GROUND_TRUTH_GROUPS.items():
        for crop_id in pair:
            if crop_id not in crop_ids:
                raise ValueError(f"ground-truth crop does not exist: {crop_id}")
            if crop_id in labels:
                raise ValueError(f"crop appears in more than one ground-truth group: {crop_id}")
            labels[crop_id] = group_name
    for crop_id in crop_ids:
        labels.setdefault(crop_id, f"unique:{crop_id}")
    return labels


def _cluster_records(
    records: list[CropRecord], algorithm: str, threshold: int,
    gt_labels: dict[str, str],
) -> SweepResult:
    hashes = [getattr(record, algorithm) for record in records]
    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index in range(len(records)):
        for right_index in range(left_index + 1, len(records)):
            if _hamming(hashes[left_index], hashes[right_index]) <= threshold:
                union(left_index, right_index)

    groups: dict[int, list[str]] = {}
    for index, record in enumerate(records):
        groups.setdefault(find(index), []).append(record.crop_id)
    clusters = tuple(
        tuple(members) for members in sorted(
            groups.values(), key=lambda members: min(records.index(
                next(record for record in records if record.crop_id == crop_id)
            ) for crop_id in members)
        )
    )
    # Every visual same-name pair is one expected positive crop pair.
    correct_groups = tuple(
        group_name for group_name, pair in GROUND_TRUTH_GROUPS.items()
        if any(set(pair).issubset(cluster) for cluster in clusters)
    )
    wrong_merges = 0
    mixed_names: set[str] = set()
    for cluster in clusters:
        cluster_labels = [gt_labels[crop_id] for crop_id in cluster]
        distinct_labels = set(cluster_labels)
        if len(distinct_labels) > 1:
            mixed_names.update(distinct_labels)
        for left_index in range(len(cluster)):
            for right_index in range(left_index + 1, len(cluster)):
                if cluster_labels[left_index] != cluster_labels[right_index]:
                    wrong_merges += 1

    return SweepResult(
        algorithm=algorithm,
        threshold=threshold,
        clusters=clusters,
        correct_groups=correct_groups,
        wrong_merges=wrong_merges,
        mixed_cluster_names=tuple(sorted(mixed_names)),
    )


def _format_distance_value(value: int) -> str:
    return f"{value:016x}"


def _best_result(results: list[SweepResult]) -> SweepResult:
    # Primary: most known pairs recovered. Secondary: fewest false-positive
    # row-pair joins. Tie-break: the smallest tested threshold.
    return min(
        results,
        key=lambda result: (
            -result.correct_merge_count,
            result.wrong_merges,
            result.threshold,
        ),
    )


def _format_report(
    records: list[CropRecord],
    geometries: list[InvoiceGeometry],
    sweeps: dict[str, list[SweepResult]],
    best: dict[str, SweepResult],
    tesseract_path: str | None,
) -> str:
    crop_ids = [record.crop_id for record in records]
    lines = [
        "# Offline Product-Name Clustering by Image Hash",
        "",
        "## Method",
        "",
        "The experiment crops the product-description cell from every labeled row, converts it to grayscale, finds the non-white text bounding box using a 245/255 cutoff, crops to that box, and resizes to 64×16 pixels. aHash uses an 8×8 resize and comparison against the pixel mean; dHash uses a 9×8 resize and horizontal adjacent-pixel comparisons. Clustering is single-link connected components: an edge is added for each pair of hashes with Hamming distance less than or equal to the tested threshold.",
        "",
        "Only Pillow is used for image processing and hashing. The projection detector is used to verify that the T2 geometry agrees with the receipt fixtures. Clustering uses only the hashes. Ground-truth group labels below are used only to score the result.",
        "",
        "Crop boxes use the product-name column interior with 4 px horizontal, 8 px top and 3 px bottom insets to exclude table rules. Crop files are saved under `/tmp/t3-crops/` as `{invoice_id}_row{row_idx}.png`.",
        "",
        "## Projection Geometry Check",
        "",
        "The actual detector output confirms the RTL column order `[amount, quantity, description, row number]` for these receipts. The product-description cells are between x=293 and x=487. The task's suggested x=116–244 range is the printed amount/total column on these images, not the product-name column, so it was not used for name hashes.",
        "",
        "| invoice | image size | detected rows | detected column boundaries | description x range |",
        "|---:|---:|---:|---|---:|",
    ]
    for geometry in geometries:
        lines.append(
            f"| {geometry.invoice_id} | {geometry.image_size[0]}×{geometry.image_size[1]} "
            f"| {len(geometry.detected_row_bands)} | "
            f"{list(geometry.boundaries)} | "
            f"{geometry.description_x[0]:.0f}–{geometry.description_x[1]:.0f} |"
        )
    lines.extend([
        "",
        "Each projection row count and band agrees with `tests/fixtures/real/labels.json` (within 1 px).",
        "",
        "## Ground Truth Used for Scoring (Visual, Unconfirmed)",
        "",
        "The three names below were visually mapped to rows from the description crops; no OCR was run and this mapping is not operator-confirmed. All other row names are treated as distinct, per the task brief.",
        "",
        "| group | visually mapped rows |",
        "|---|---|",
    ])
    for group_name, pair in GROUND_TRUTH_GROUPS.items():
        lines.append(f"| {group_name} | {pair[0]}, {pair[1]} |")
    lines.extend([
        "",
        "## Per-Crop Hashes",
        "",
        "| crop | source crop bbox (x1,y1,x2,y2) | text bbox inside crop | aHash | dHash |",
        "|---|---:|---:|---|---|",
    ])
    for record in records:
        lines.append(
            f"| {record.crop_id} | {record.source_bbox} | {record.text_bbox} "
            f"| `{_format_distance_value(record.ahash)}` "
            f"| `{_format_distance_value(record.dhash)}` |"
        )
    lines.extend([
        "",
        "## Threshold Sweep",
        "",
        "`wrong_merges` counts unordered crop pairs from different ground-truth product-name labels that became part of the same connected component. `correct_merges` counts recovered known same-name pairs (0–3).",
        "",
        "| hash | threshold (bits) | clusters | correct_merges / 3 | wrong_merges (false-positive pairs) |",
        "|---|---:|---:|---:|---:|",
    ])
    for algorithm in ("ahash", "dhash"):
        for result in sweeps[algorithm]:
            lines.append(
                f"| {algorithm} | {result.threshold} | {result.cluster_count} "
                f"| {result.correct_merge_count} / 3 | {result.wrong_merges} |"
            )
    lines.extend([
        "",
        "## Best Tested Thresholds",
        "",
        "Selection rule: maximize recovered known pairs, then minimize false-positive pair joins, then choose the lowest threshold. The two hash algorithms are selected independently.",
        "",
    ])
    for algorithm in ("ahash", "dhash"):
        result = best[algorithm]
        pair_status = []
        for group_name, pair in GROUND_TRUTH_GROUPS.items():
            merged = any(set(pair).issubset(cluster) for cluster in result.clusters)
            pair_status.append(f"{group_name}: {'merged' if merged else 'not merged'}")
        expected_clusters = 22
        lines.extend([
            f"### {algorithm}: threshold {result.threshold}",
            "",
            f"- Correct known groups merged: {result.correct_merge_count}/3 "
            f"({'; '.join(pair_status)}).",
            f"- Wrong merges: {result.wrong_merges} false-positive crop-pair joins.",
            f"- Distinct ground-truth name labels in mixed clusters: "
            f"{len(result.mixed_cluster_names)} "
            f"({', '.join(result.mixed_cluster_names) if result.mixed_cluster_names else 'none'}).",
            f"- Observed clusters: {result.cluster_count}; expected ground-truth "
            f"clusters: {expected_clusters} (3 pairs + 19 singles).",
            "",
            "Pair status: " + "; ".join(pair_status),
            "",
        ])
    lines.extend([
        "## Cluster Memberships at Every Tested Threshold",
        "",
        "Each section lists every connected component, including singletons, so all 25 crops are accounted for at every threshold.",
        "",
    ])
    for algorithm in ("ahash", "dhash"):
        for result in sweeps[algorithm]:
            lines.extend([
                f"### {algorithm}, threshold {result.threshold} "
                f"(clusters={result.cluster_count}, correct={result.correct_merge_count}/3, "
                f"wrong={result.wrong_merges})",
                "",
                "```text",
            ])
            for index, cluster in enumerate(result.clusters, start=1):
                lines.append(f"C{index:02d}: {', '.join(cluster)}")
            lines.extend(["```", ""])
    lines.extend([
        "## Tesseract Comparison",
        "",
    ])
    if tesseract_path is None:
        lines.append(
            "Tesseract comparison skipped: no `tesseract` executable is available in this environment. No OCR or network/VLM service was used."
        )
    else:
        lines.append(
            f"Tesseract executable found at `{tesseract_path}`, but this experiment did not invoke OCR; the requested offline hash-only grouping was kept independent. A separate full-page Tesseract comparison was not run."
        )
    lines.extend([
        "",
        "## Reproduction",
        "",
        "```sh",
        "PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python src/run_name_cluster_experiment.py \\",
        "  --labels tests/fixtures/real/labels.json \\",
        "  --crop-dir /tmp/t3-crops \\",
        "  --output docs/name-cluster-report.md",
        "```",
        "",
        f"Generated {len(records)} description crops; thresholds tested: "
        + ", ".join(str(value) for value in THRESHOLDS) + ".",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--crop-dir", type=Path, default=Path("/tmp/t3-crops"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    labels_path = args.labels.resolve()
    data, labels_dir = _read_and_validate_inputs(labels_path)
    crop_dir = args.crop_dir if args.crop_dir.is_absolute() else REPO_ROOT / args.crop_dir
    records, geometries = _make_crops(data["invoices"], labels_dir, crop_dir)
    crop_ids = [record.crop_id for record in records]
    gt_labels = _ground_truth_labels(crop_ids)
    sweeps = {
        algorithm: [
            _cluster_records(records, algorithm, threshold, gt_labels)
            for threshold in THRESHOLDS
        ]
        for algorithm in ("ahash", "dhash")
    }
    best = {algorithm: _best_result(results) for algorithm, results in sweeps.items()}
    report = _format_report(
        records,
        geometries,
        sweeps,
        best,
        shutil.which("tesseract"),
    )
    output_path = args.output
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"report_path={output_path}")
    print(f"crop_dir={crop_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
