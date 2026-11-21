#!/usr/bin/env python3
"""Diagnose payable-cell connected-component segmentation on labeled fixtures.

By default, analyze every invoice in tests/fixtures/real/labels.json. An
optional --image can restrict the run to one fixture, and --labels accepts a
compatible label JSON file. This is a diagnostic only: it does not run OCR,
Tesseract, or change any production behavior.

The crop and Otsu/line-removal preprocessing use the repository's Pillow-only
preprocessing helpers. The connected-component pass mirrors the glyph
segmenter's standard-library 8-connected flood fill and filters so the count
is comparable to the template-build diagnostics.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = REPO_ROOT / "tests" / "fixtures" / "real" / "labels.json"
PAYABLE_FIELD = "invoice.payable"
PADDING = 4
FOREGROUND_THRESHOLD = 128
MIN_COMPONENT_PIXELS = 4
X_OVERLAP_MERGE_RATIO = 0.7
RULE_MAX_WIDTH = 2
RULE_MIN_HEIGHT_RATIO = 0.8
_DIGITS = set("0123456789٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹")
_SEPARATORS = {",", "٬"}


@dataclass(frozen=True)
class Component:
    """Connected foreground component; right/bottom are exclusive."""

    left: int
    top: int
    right: int
    bottom: int
    pixels: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def _component(points: list[tuple[int, int]]) -> Component:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return Component(min(xs), min(ys), max(xs) + 1, max(ys) + 1, len(points))


def _raw_components(binary_image: Any) -> list[Component]:
    """Return 8-connected black-pixel components using Pillow bytes + stdlib."""
    gray = binary_image.convert("L")
    width, height = gray.size
    data = gray.tobytes()
    rows = [
        bytearray(1 if data[y * width + x] < FOREGROUND_THRESHOLD else 0
                  for x in range(width))
        for y in range(height)
    ]
    seen = [bytearray(width) for _ in range(height)]
    result: list[Component] = []

    for y0 in range(height):
        for x0 in range(width):
            if not rows[y0][x0] or seen[y0][x0]:
                continue
            seen[y0][x0] = 1
            stack = [(x0, y0)]
            points: list[tuple[int, int]] = []
            while stack:
                x, y = stack.pop()
                points.append((x, y))
                for ny in (y - 1, y, y + 1):
                    if not 0 <= ny < height:
                        continue
                    for nx in (x - 1, x, x + 1):
                        if (0 <= nx < width and rows[ny][nx]
                                and not seen[ny][nx]):
                            seen[ny][nx] = 1
                            stack.append((nx, ny))
            result.append(_component(points))

    return result


def _overlap_ratio(a: Component, b: Component) -> float:
    overlap = min(a.right, b.right) - max(a.left, b.left)
    smaller_width = min(a.width, b.width)
    return max(0, overlap) / smaller_width if smaller_width else 0.0


def connected_components(binary_image: Any) -> list[Component]:
    """Apply the same size/rule filters and x-overlap merging as glyph segmenter."""
    _, height = binary_image.size
    components = [
        item for item in _raw_components(binary_image)
        if item.pixels >= MIN_COMPONENT_PIXELS
        and not (item.width <= RULE_MAX_WIDTH
                 and item.height >= RULE_MIN_HEIGHT_RATIO * height)
    ]
    components.sort(key=lambda item: (item.left, item.top))

    merged: list[Component] = []
    for item in components:
        if merged and _overlap_ratio(merged[-1], item) >= X_OVERLAP_MERGE_RATIO:
            previous = merged[-1]
            merged[-1] = Component(
                left=min(previous.left, item.left),
                top=min(previous.top, item.top),
                right=max(previous.right, item.right),
                bottom=max(previous.bottom, item.bottom),
                pixels=previous.pixels + item.pixels,
            )
        else:
            merged.append(item)
    return merged


def _entry_image_path(entry: dict[str, Any], labels_path: Path) -> Path:
    path = Path(entry["path"])
    if path.is_absolute():
        return path.resolve()
    return (labels_path.parent / path).resolve()


def _select_entries(
    entries: list[dict[str, Any]], labels_path: Path, image_paths: list[Path]
) -> list[tuple[dict[str, Any], Path]]:
    if not image_paths:
        return [(entry, _entry_image_path(entry, labels_path)) for entry in entries]

    selected: list[tuple[dict[str, Any], Path]] = []
    used: set[str] = set()
    for image_path in image_paths:
        requested = image_path.resolve()
        exact = [
            entry for entry in entries
            if _entry_image_path(entry, labels_path) == requested
        ]
        matches = exact or [
            entry for entry in entries
            if Path(str(entry.get("path", ""))).name == image_path.name
        ]
        if len(matches) != 1:
            raise ValueError(
                f"image {image_path} matches {len(matches)} label entries; "
                "use an image path present in the labels file"
            )
        entry = matches[0]
        key = str(entry.get("id", entry.get("path")))
        if key in used:
            continue
        used.add(key)
        # Use the caller's path when supplied; this allows an image copy whose
        # filename matches an entry to be diagnosed alongside that label.
        selected.append((entry, requested))
    return selected


def _load_crop_helpers():
    """Import the repository's Pillow-only crop and preprocessing helpers."""
    source_root = str(REPO_ROOT / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from PIL import Image  # noqa: PLC0415 - keep Pillow requirement explicit
    from image_extraction_adapter.preprocessing import (  # noqa: PLC0415
        crop_spatial_cells,
        otsu_binarize,
        preprocess_cell,
    )
    return Image, crop_spatial_cells, otsu_binarize, preprocess_cell


def _crop_payable(
    source: Any,
    entry: dict[str, Any],
    crop_spatial_cells: Any,
) -> Any:
    payable_bbox = entry.get("payable_bbox")
    if not isinstance(payable_bbox, (list, tuple)) or len(payable_bbox) != 4:
        raise ValueError(f"invoice {entry.get('id', '?')} has no four-value payable_bbox")
    bbox = tuple(int(value) for value in payable_bbox)
    spatial = SimpleNamespace(
        column_boundaries=tuple(entry.get("column_boundaries", ())),
        row_bands=tuple(tuple(band) for band in entry.get("row_bands", ())),
        assessments=(SimpleNamespace(field_name=PAYABLE_FIELD, bbox=bbox),),
    )
    crops = crop_spatial_cells(
        source, spatial, include_descriptions=False, include_payable=True,
        payable_padding=PADDING)
    payable = next((item for item in crops if item.field_name == PAYABLE_FIELD), None)
    if payable is None:
        raise ValueError(
            f"invoice {entry.get('id', '?')} did not yield a payable crop; "
            "check payable_bbox and image bounds"
        )
    return payable


def _expected_symbol_count(value: str) -> int:
    return sum(character in _DIGITS or character in _SEPARATORS for character in value)


def _xywh(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    return left, top, right - left, bottom - top


def _split_component_groups(
    before: list[Component], after: list[Component]
) -> list[tuple[int, tuple[int, ...]]]:
    """Map Otsu-only components split into multiple post-cleanup components."""
    groups = []
    for before_index, original in enumerate(before, start=1):
        children = []
        for after_index, cleaned in enumerate(after, start=1):
            if (cleaned.left >= original.left and cleaned.top >= original.top
                    and cleaned.right <= original.right
                    and cleaned.bottom <= original.bottom):
                children.append(after_index)
        if len(children) > 1:
            groups.append((before_index, tuple(children)))
    return groups


def _format_bbox(box: tuple[int, int, int, int]) -> str:
    return "[" + ", ".join(str(value) for value in box) + "]"


def diagnose(
    entry: dict[str, Any], image_path: Path,
    image_module: Any, crop_spatial_cells: Any, otsu_binarize: Any,
    preprocess_cell: Any,
) -> dict[str, Any]:
    if not image_path.is_file():
        raise FileNotFoundError(f"image file does not exist: {image_path}")
    payable_value = entry.get("values", {}).get(PAYABLE_FIELD)
    if not isinstance(payable_value, str) or not payable_value:
        raise ValueError(f"invoice {entry.get('id', '?')} has no labeled payable value")
    expected = _expected_symbol_count(payable_value)
    if expected == 0:
        raise ValueError(f"invoice {entry.get('id', '?')} payable label has no digits/commas")

    with image_module.open(image_path) as opened:
        opened.load()
        source = opened.convert("RGB")
    payable_crop = _crop_payable(source, entry, crop_spatial_cells)
    # These three counts isolate changes caused by thresholding vs line removal.
    # The last path is the exact Pillow-only preprocessing used by glyph training.
    raw_count = len(connected_components(payable_crop.image))
    otsu_image = otsu_binarize(payable_crop.image)
    otsu_components = connected_components(otsu_image)
    otsu_count = len(otsu_components)
    preprocessed = preprocess_cell(payable_crop.image, "otsu")
    components = connected_components(preprocessed.image)
    split_groups = _split_component_groups(otsu_components, components)
    removed_pixels = preprocessed.line_pixels_removed

    label_bbox = tuple(int(value) for value in entry["payable_bbox"])
    crop_bbox = tuple(int(value) for value in payable_crop.bbox)
    delta = len(components) - expected
    if delta > 0 and otsu_count == expected and len(components) > otsu_count:
        diagnosis = (
            f"OVER-segmented by {delta}; raw/Otsu-only counts match the {expected} "
            "labeled symbols, and the excess appears only after morphological "
            "line removal, which likely severs numeral strokes"
        )
    elif delta > 0:
        diagnosis = (
            f"OVER-segmented by {delta}: one or more numeral strokes are split "
            "into separate connected components"
        )
    elif delta < 0:
        diagnosis = (
            f"UNDER-segmented by {-delta}: at least one expected symbol may be "
            "joined to a neighbor or clipped"
        )
    else:
        diagnosis = (
            "component count matches the labeled symbol count; this is a count "
            "check only, not proof that every component maps to the right symbol"
        )

    return {
        "id": str(entry.get("id", image_path.stem)),
        "image": image_path,
        "value": payable_value,
        "expected": expected,
        "raw_count": raw_count,
        "otsu_count": otsu_count,
        "actual": len(components),
        "delta": delta,
        "split_groups": split_groups,
        "diagnosis": diagnosis,
        "label_bbox": label_bbox,
        "crop_bbox": crop_bbox,
        "crop_size": payable_crop.image.size,
        "line_pixels_removed": removed_pixels,
        "components": components,
    }


def print_report(result: dict[str, Any]) -> None:
    identifier = result["id"]
    label_bbox = result["label_bbox"]
    crop_bbox = result["crop_bbox"]
    crop_left, crop_top, _, _ = crop_bbox
    delta = result["delta"]
    sign = "+" if delta > 0 else ""
    print(f"\nInvoice #{identifier} — {result['image'].name}")
    print(f"  labeled payable: {result['value']!r}")
    print(f"  expected symbols (digits + commas): {result['expected']}")
    print(
        "  reference payable_bbox [x, y, width, height]: "
        f"{_format_bbox(label_bbox)} (from labels.json; not a live OCR bbox)"
    )
    print(
        "  analyzed crop [left, top, right, bottom), xywh: "
        f"{_format_bbox(crop_bbox)}, {_format_bbox(_xywh(crop_bbox))}"
    )
    print(
        f"  crop source: label reference bbox + crop_spatial_cells default "
        f"{PADDING}px payable padding; crop size={result['crop_size'][0]}x"
        f"{result['crop_size'][1]}"
    )
    print(
        "  component-count controls: "
        f"raw threshold={result['raw_count']}, Otsu only={result['otsu_count']}, "
        f"Otsu + line removal={result['actual']}"
    )
    print(
        f"  preprocessing: Otsu + morphological rule removal; "
        f"removed foreground pixels={result['line_pixels_removed']}"
    )
    if result["split_groups"]:
        split_text = "; ".join(
            f"Otsu {before:02d} -> "
            + "+".join(f"{after:02d}" for after in children)
            for before, children in result["split_groups"]
        )
        print(f"  components split by line removal (Otsu -> final): {split_text}")
    else:
        print("  components split by line removal (Otsu -> final): none")
    print(
        f"  components: {result['actual']} (delta {sign}{delta} vs expected); "
        f"8-connected flood fill, filtered and x-overlap merged"
    )
    print("  component list (left-to-right; bbox=[x,y,width,height] crop-relative):")
    for index, component in enumerate(result["components"], start=1):
        absolute_bbox = (
            crop_left + component.left,
            crop_top + component.top,
            component.width,
            component.height,
        )
        print(
            f"    {index:02d} bbox="
            f"[{component.left}, {component.top}, {component.width}, {component.height}] "
            f"pixels={component.pixels} width={component.width} height={component.height} "
            f"absolute_xywh={_format_bbox(absolute_bbox)}"
        )
    print(f"  diagnosis: {result['diagnosis']}.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image", type=Path, action="append", default=[], metavar="PATH",
        help="analyze one labeled image (repeat for multiple); omit for all invoices",
    )
    parser.add_argument(
        "--labels", type=Path, default=DEFAULT_LABELS, metavar="PATH",
        help=f"labels JSON (default: {DEFAULT_LABELS.relative_to(REPO_ROOT)})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    labels_path = args.labels.resolve()
    if not labels_path.is_file():
        print(f"error: labels file does not exist: {labels_path}", file=sys.stderr)
        return 2
    try:
        data = json.loads(labels_path.read_text(encoding="utf-8"))
        entries = data.get("invoices", data.get("images"))
        if not isinstance(entries, list) or not entries:
            raise ValueError("labels JSON needs a non-empty 'invoices' or 'images' list")
        selected = _select_entries(entries, labels_path, args.image)
        image_module, crop_spatial_cells, otsu_binarize, preprocess_cell = _load_crop_helpers()
        print(f"Labels: {labels_path}")
        print("Scope: label-reference payable boxes; runtime Tesseract word boxes are not reproduced.")
        print("Segmentation: Pillow preprocessing + standard-library connected components.")
        results = []
        for entry, image_path in selected:
            result = diagnose(
                entry, image_path, image_module, crop_spatial_cells,
                otsu_binarize, preprocess_cell,
            )
            results.append(result)
            print_report(result)

        print("\nSummary")
        print("  invoice | expected | components | delta")
        for result in results:
            delta = result["delta"]
            sign = "+" if delta > 0 else ""
            print(
                f"  {result['id']:>7} | {result['expected']:>8} | "
                f"{result['actual']:>10} | {sign}{delta}"
            )
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
