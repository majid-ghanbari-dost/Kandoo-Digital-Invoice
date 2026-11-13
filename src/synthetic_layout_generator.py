"""E-41 deterministic synthetic invoice-layout samples.

This module generates test-only rasters and declared numeric/layout labels from
only an integer seed and sample count. It reads no invoice fixtures, customer
records, Holoo inputs, external font/image assets, or network resources; drawing
uses Pillow's built-in font.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

GENERATOR_VERSION = "e41-synthetic-layout-v1"
SYNTHETIC_MARKER = "SYNTHETIC ONLY — NOT CUSTOMER DATA"
MAX_SAMPLES = 100
IMAGE_WIDTH = 900

# Each profile has five left-to-right grid rules for total, quantity,
# description, and row number. Ratios are deliberately varied, not learned
# from a source invoice.
_LAYOUT_PROFILES: tuple[tuple[str, tuple[float, ...]], ...] = (
    ("standard-v1", (0.06, 0.27, 0.42, 0.88, 0.96)),
    ("wide-description-v1", (0.05, 0.22, 0.37, 0.92, 0.97)),
    ("narrow-description-v1", (0.08, 0.34, 0.50, 0.83, 0.95)),
    ("shifted-grid-v1", (0.12, 0.33, 0.47, 0.89, 0.98)),
)


def _draw(seed: int, ordinal: int, label: str, upper: int) -> int:
    """Return a stable pseudorandom integer using a versioned SHA-256 domain."""
    if upper <= 0:
        raise ValueError("upper must be positive")
    payload = f"{GENERATOR_VERSION}\0{seed}\0{ordinal}\0{label}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % upper


def _validate_declaration(seed: int, count: int) -> None:
    if type(seed) is not int or not 0 <= seed <= 0x7FFFFFFFFFFFFFFF:
        raise ValueError("seed must be a non-negative signed-64-bit integer")
    if type(count) is not int or not 1 <= count <= MAX_SAMPLES:
        raise ValueError(f"count must be an integer in 1..{MAX_SAMPLES}")


def _sample(seed: int, ordinal: int) -> dict[str, Any]:
    profile_offset = _draw(seed, 0, "profile-order", len(_LAYOUT_PROFILES))
    profile_id, ratios = _LAYOUT_PROFILES[
        (profile_offset + ordinal - 1) % len(_LAYOUT_PROFILES)
    ]
    horizontal_jitter = _draw(seed, ordinal, "horizontal-jitter", 17) - 8
    boundaries = [round(IMAGE_WIDTH * ratio) + horizontal_jitter for ratio in ratios]
    if any(right <= left for left, right in zip(boundaries, boundaries[1:])):
        raise AssertionError("declared synthetic profile produced invalid column boundaries")

    row_count = 1 + _draw(seed, ordinal, "row-count", 8)
    row_height = 54 + _draw(seed, ordinal, "row-height", 13)
    header_height = max(30, round(row_height * 0.70))
    table_top = 112 + _draw(seed, ordinal, "table-top", 21)
    header_bottom = table_top + header_height
    table_bottom = header_bottom + row_count * row_height
    row_bands = [
        [header_bottom + row * row_height, header_bottom + (row + 1) * row_height]
        for row in range(row_count)
    ]

    line_items: list[dict[str, Any]] = []
    for row in range(row_count):
        quantity = 1 + _draw(seed, ordinal, f"quantity-{row}", 5)
        unit_price = 1000 + _draw(seed, ordinal, f"unit-price-{row}", 9000)
        line_items.append({
            "description": f"SYNTHETIC ITEM {row + 1:02d}",
            "quantity": quantity,
            "unit_price_test_only": unit_price,
            "line_total": quantity * unit_price,
        })
    payable = sum(item["line_total"] for item in line_items)
    return {
        "sample_id": f"E41-SYNTHETIC-{seed:016d}-{ordinal:04d}",
        "seed": seed,
        "ordinal": ordinal,
        "layout_profile": profile_id,
        "image_width": IMAGE_WIDTH,
        "image_height": table_bottom + 112,
        "column_roles_left_to_right": ["line_total", "quantity", "description", "row_number"],
        "column_boundaries": boundaries,
        "table_top": table_top,
        "header_bottom": header_bottom,
        "table_bottom": table_bottom,
        "row_bands": row_bands,
        "median_row_height": row_height,
        "line_items": line_items,
        "subtotal_test_only": payable,
        "payable_test_only": payable,
    }


def _draw_numeric(draw: Any, text: str, center: tuple[int, int], font: Any) -> None:
    """Draw digits with a small fixed gap so each synthetic glyph is distinct."""
    widths = [draw.textbbox((0, 0), character, font=font)[2] -
              draw.textbbox((0, 0), character, font=font)[0]
              for character in text]
    gap = 3
    x = center[0] - (sum(widths) + gap * max(0, len(widths) - 1)) // 2
    for character, width in zip(text, widths, strict=True):
        draw.text((x, center[1]), character, fill=0, font=font, anchor="lm")
        x += width + gap


def _render(sample: dict[str, Any]) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Pillow is required to render E-41 synthetic layouts") from exc

    image = Image.new("1", (sample["image_width"], sample["image_height"]), 1)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((24, 22), "SYNTHETIC INVOICE - TEST ONLY", fill=0, font=font)
    draw.text((24, 48), sample["sample_id"], fill=0, font=font)

    boundaries = sample["column_boundaries"]
    top = sample["table_top"]
    bottom = sample["table_bottom"]
    horizontal = [top, sample["header_bottom"]]
    horizontal.extend(band[1] for band in sample["row_bands"])
    for y in horizontal:
        draw.line((boundaries[0], y, boundaries[-1], y), fill=0, width=2)
    for x in boundaries:
        draw.line((x, top, x, bottom), fill=0, width=2)

    header_y = (top + sample["header_bottom"]) // 2
    headers = ("TOTAL", "QTY", "ITEM", "NO")
    for index, label in enumerate(headers):
        center_x = (boundaries[index] + boundaries[index + 1]) // 2
        draw.text((center_x, header_y), label, fill=0, font=font, anchor="mm")

    for row, (band, item) in enumerate(zip(sample["row_bands"], sample["line_items"], strict=True)):
        center_y = (band[0] + band[1]) // 2
        values = (
            str(item["line_total"]),
            str(item["quantity"]),
            item["description"],
            str(row + 1),
        )
        for column, value in enumerate(values):
            center_x = (boundaries[column] + boundaries[column + 1]) // 2
            if column == 2:
                draw.text((center_x, center_y), value, fill=0, font=font, anchor="mm")
            else:
                _draw_numeric(draw, value, (center_x, center_y), font)

    # The payable amount sits in a separate, geometry-relative band used by the
    # existing payable-region locator; no customer or merchant field is drawn.
    payable_y = bottom + round(sample["median_row_height"] * 0.48)
    payable_x = (boundaries[0] + boundaries[2]) // 2
    _draw_numeric(draw, str(sample["payable_test_only"]), (payable_x, payable_y), font)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def generate_dataset(output_dir: str | Path, *, seed: int, count: int) -> dict[str, Any]:
    """Render a deterministic synthetic dataset and write its JSON manifest.

    ``output_dir`` must be new or empty. Each sample contains only generated
    invoice-like numeric labels, geometry, a synthetic identifier, and a PNG;
    it has no customer, store, phone, address, or source-image data.
    """
    _validate_declaration(seed, count)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError(f"output directory must be empty: {destination}")

    generated: list[tuple[dict[str, Any], bytes]] = []
    for ordinal in range(1, count + 1):
        sample = _sample(seed, ordinal)
        image_bytes = _render(sample)
        sample["image_file"] = f"{sample['sample_id']}.png"
        sample["image_sha256"] = hashlib.sha256(image_bytes).hexdigest()
        generated.append((sample, image_bytes))

    manifest: dict[str, Any] = {
        "schema_version": GENERATOR_VERSION,
        "evidence_class": "SYNTHETIC_ONLY",
        "synthetic_marker": SYNTHETIC_MARKER,
        "seed": seed,
        "sample_count": count,
        "generator_inputs": ["seed", "count"],
        "external_input_sources": [],
        "samples": [sample for sample, _ in generated],
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    for sample, image_bytes in generated:
        (destination / sample["image_file"]).write_bytes(image_bytes)
    (destination / "manifest.json").write_bytes(manifest_bytes)
    return manifest
