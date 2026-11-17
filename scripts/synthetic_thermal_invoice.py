"""Helpers for explicitly synthetic 576-pixel E-03 thermal-style mechanics tests.

These generated pages are test inputs only. They are not Holo captures, proof of
any real store's layout, or evidence of real-world recognition accuracy.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
KIT_DIR = REPO_ROOT / "docs" / "E-03-kit-v3"
PAGES_DIR = REPO_ROOT / "deliveries" / "e20-second-store" / "synthetic-pages"
PAGE_IDS = ("learning-1", "learning-2", "learning-3", "exam")
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
CONTROLLED_GLYPHS = PERSIAN_DIGITS + ","
IMAGE_WIDTH = 576
BASE_COLUMN_BOUNDARIES = (116.0, 244.0, 293.0, 487.0, 527.0)
TABLE_TOP = 420
HEADER_HEIGHT = 48
ROW_HEIGHT = 68

if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class PersianFontUnavailable(RuntimeError):
    """No installed alternate font could render all Persian numeric glyphs."""


@dataclass(frozen=True)
class FontChoice:
    path: Path
    family: str
    style: str
    sha256: str


@dataclass(frozen=True)
class SyntheticPage:
    page_id: str
    image_path: Path
    width: int
    height: int
    column_boundaries: tuple[float, ...]
    row_bands: tuple[tuple[float, float], ...]
    payable_bbox: tuple[int, int, int, int] | None
    values: Mapping[str, Any]
    item_names: tuple[str, ...]
    sha256: str


def load_kit() -> tuple[dict[str, Any], dict[str, tuple[str, ...]], dict[str, int]]:
    """Validate the frozen E-03 kit and return its numeric targets and names."""
    from verify_e03_kit_v3 import PAGE_FILES, _page_values_from_markdown, verify_kit

    coverage = verify_kit(KIT_DIR)
    expected = json.loads((KIT_DIR / "expected-values.json").read_text(encoding="utf-8"))
    names: dict[str, tuple[str, ...]] = {}
    for page_id, filename in PAGE_FILES.items():
        page = _page_values_from_markdown(KIT_DIR / filename)
        names[page_id] = tuple(page["item_names"])
        if (
            page["quantities"] != expected[page_id]["quantities"]
            or page["line_totals"] != expected[page_id]["line_totals"]
            or page["payable"] != expected[page_id]["payable"]
        ):
            raise ValueError(f"E-03 rendered target values diverge for {page_id}")
    return expected, names, coverage


def _candidate_font_paths() -> list[Path]:
    roots = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / ".local" / "share" / "fonts",
    ]
    paths: set[Path] = set()
    for root in roots:
        if root.is_dir():
            for suffix in ("*.ttf", "*.otf", "*.ttc"):
                paths.update(path for path in root.rglob(suffix) if path.is_file())
    priority_names = (
        "notonaskharabic-regular.ttf",
        "notoserifarabic-regular.ttf",
        "liberationserif-regular.ttf",
        "freeserif.ttf",
        "dejavusansmono.ttf",
        "dejavusans.ttf",
        "dejavusans-bold.ttf",
    )

    def sort_key(path: Path) -> tuple[int, str, str]:
        name = path.name.casefold()
        try:
            priority = priority_names.index(name)
        except ValueError:
            priority = len(priority_names)
        return priority, name, str(path).casefold()

    return sorted(paths, key=sort_key)


def _font_supports_digits(font: Any) -> bool:
    """Reject blank/missing-glyph masks and fonts that map digits to one box."""
    try:
        masks = []
        for glyph in CONTROLLED_GLYPHS:
            mask = font.getmask(glyph)
            if mask.getbbox() is None:
                return False
            masks.append((mask.size, bytes(mask)))
        return len(set(masks[:10])) == 10 and masks[10] not in set(masks[:10])
    except Exception:
        return False


def select_persian_font() -> FontChoice:
    """Find an installed font with distinct glyph masks for Persian digits.

    No font is downloaded or substituted. If the CI image lacks a suitable
    installed font, the caller must stop and report that limitation.
    """
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise PersianFontUnavailable("Pillow is missing; cannot inspect installed fonts") from exc

    checked: list[str] = []
    for path in _candidate_font_paths():
        checked.append(str(path))
        try:
            font = ImageFont.truetype(str(path), 28)
            family, style = font.getname()
            if not _font_supports_digits(font):
                continue
            return FontChoice(
                path=path,
                family=str(family),
                style=str(style),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        except Exception:
            continue
    preview = ", ".join(checked[:8]) or "no system font files found"
    raise PersianFontUnavailable(
        "No installed font rendered distinct Persian digits ۰–۹ plus comma. "
        f"Inspected: {preview}"
    )


def _page_layout(page_id: str, row_count: int, variant: str | None) -> tuple[
    tuple[float, ...], int, int, tuple[int, ...], tuple[tuple[float, float], ...], tuple[int, ...]
]:
    boundaries = list(BASE_COLUMN_BOUNDARIES)
    table_top = TABLE_TOP
    extra_verticals: tuple[int, ...] = ()
    if variant == "different-table-position":
        boundaries = [value + 28 for value in boundaries]
        table_top += 34
    elif variant == "extra-column":
        extra_verticals = (390,)
    elif variant not in (None, "no-vertical-rules", "three-columns", "swapped-columns"):
        raise ValueError(f"unknown synthetic layout variant: {variant}")

    header_bottom = table_top + HEADER_HEIGHT
    table_bottom = header_bottom + row_count * ROW_HEIGHT
    bands = tuple(
        (float(header_bottom + index * ROW_HEIGHT), float(header_bottom + (index + 1) * ROW_HEIGHT))
        for index in range(row_count)
    )
    horizontal_lines = tuple(
        [table_top, header_bottom]
        + [header_bottom + index * ROW_HEIGHT for index in range(1, row_count + 1)]
    )
    return tuple(boundaries), table_top, table_bottom, extra_verticals, bands, horizontal_lines


def render_page(
    page_id: str,
    values: Mapping[str, Any],
    item_names: tuple[str, ...],
    font_choice: FontChoice,
    output_path: Path,
    *,
    variant: str | None = None,
) -> SyntheticPage:
    """Render one Holo-inspired but entirely fabricated invoice page."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required to render the synthetic page") from exc

    quantities = list(values["quantities"])
    line_totals = list(values["line_totals"])
    payable = str(values["payable"])
    if not (len(quantities) == len(line_totals) == len(item_names) == 4):
        raise ValueError(f"{page_id} must have four controlled item rows")

    boundaries, table_top, table_bottom, extra_verticals, row_bands, horizontal_lines = _page_layout(
        page_id, len(quantities), variant
    )
    height = table_bottom + 132
    image = Image.new("L", (IMAGE_WIDTH, height), 255)
    draw = ImageDraw.Draw(image)
    numeric_size = 18 if "mono" in font_choice.family.casefold() else 21
    numeric_font = ImageFont.truetype(str(font_choice.path), numeric_size)
    name_font = ImageFont.truetype(str(font_choice.path), 17)
    header_font = ImageFont.truetype(str(font_choice.path), 13)
    title_font = ImageFont.truetype(str(font_choice.path), 20)
    payable_font = ImageFont.truetype(str(font_choice.path), 22)

    draw.text((IMAGE_WIDTH // 2, 110), "فروشگاه آزمایشی", fill=0, font=title_font, anchor="mm")
    draw.text((IMAGE_WIDTH // 2, 148), "فاکتور ساختگی — آزمون مکانیکی", fill=0, font=name_font, anchor="mm")

    left, right = boundaries[0], boundaries[-1]
    for y in horizontal_lines:
        draw.line((left, y, right, y), fill=0, width=2)

    if variant not in ("no-vertical-rules",):
        verticals = list(boundaries)
        if variant == "three-columns":
            # Remove one interior rule: four detected borders instead of five.
            verticals.remove(boundaries[3])
        if variant == "extra-column":
            verticals.extend(extra_verticals)
        for x in sorted(verticals):
            draw.line((x, table_top, x, table_bottom), fill=0, width=2)

    if variant == "swapped-columns":
        left_header, right_header = "تعداد", "مبلغ ردیف"
    else:
        left_header, right_header = "مبلغ ردیف", "تعداد"
    header_y = table_top + HEADER_HEIGHT // 2
    draw.text(((boundaries[0] + boundaries[1]) / 2, header_y), left_header, fill=0, font=header_font, anchor="mm")
    draw.text(((boundaries[1] + boundaries[2]) / 2, header_y), right_header, fill=0, font=header_font, anchor="mm")
    draw.text(((boundaries[2] + boundaries[3]) / 2, header_y), "شرح کالا", fill=0, font=header_font, anchor="mm")
    draw.text(((boundaries[3] + boundaries[4]) / 2, header_y), "", fill=0, font=header_font, anchor="mm")

    for index, (quantity, total, item_name, band) in enumerate(
        zip(quantities, line_totals, item_names, row_bands, strict=True)
    ):
        center_y = (band[0] + band[1]) / 2
        if variant == "swapped-columns":
            left_value, right_value = quantity, total
        else:
            left_value, right_value = total, quantity
        draw.text(((boundaries[0] + boundaries[1]) / 2, center_y), left_value, fill=0, font=numeric_font, anchor="mm")
        draw.text(((boundaries[1] + boundaries[2]) / 2, center_y), right_value, fill=0, font=numeric_font, anchor="mm")
        draw.text(((boundaries[2] + boundaries[3]) / 2, center_y), item_name, fill=0, font=name_font, anchor="mm")

    payable_y = table_bottom + 34
    payable_x = (boundaries[0] + boundaries[2]) / 2
    draw.text((payable_x, payable_y), payable, fill=0, font=payable_font, anchor="mm")
    # The non-numeric label stays outside the payable search window so the
    # controlled target remains exactly the E-03 numeric answer key.
    label_x = min(IMAGE_WIDTH - 50, boundaries[-1] - 12)
    draw.text((label_x, payable_y), "قابل پرداخت", fill=0, font=header_font, anchor="mm")

    # Thermal-like 1-bit rasterization after antialiased text rendering.
    image = image.point(lambda pixel: 0 if pixel < 180 else 255, mode="1")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)

    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return SyntheticPage(
        page_id=page_id,
        image_path=output_path,
        width=IMAGE_WIDTH,
        height=height,
        column_boundaries=boundaries,
        row_bands=row_bands,
        payable_bbox=None,
        values=dict(values),
        item_names=item_names,
        sha256=digest,
    )


def observe_page(
    page: SyntheticPage,
    source_id: str | None = None,
    field_values_override: Mapping[str, str] | None = None,
):
    """Detect geometry/payable from pixels and construct an E-05 observation.

    By default, ``field_values`` are the controlled E-03 answer-key values.
    Pass an override to build an observation from actual pipeline readings.
    """
    from PIL import Image
    from e05_template_bank import LayoutObservation
    from image_extraction_adapter.pipeline_v0 import detect_payable_bbox
    from image_extraction_adapter.preprocessing import detect_layout_safe

    with Image.open(page.image_path) as opened:
        opened.load()
        image = opened.convert("RGB")
    safety = detect_layout_safe(image)
    if safety.status != "OK" or safety.geometry is None:
        return None, safety, None
    payable_bbox = detect_payable_bbox(image, safety.geometry)
    if payable_bbox is None:
        return None, safety, None
    values = page.values
    field_values: dict[str, str] = (
        {str(key): str(value) for key, value in field_values_override.items()}
        if field_values_override is not None
        else {}
    )
    if field_values_override is None:
        for index, quantity in enumerate(values["quantities"]):
            field_values[f"line.{index}.quantity"] = str(quantity)
        for index, total in enumerate(values["line_totals"]):
            field_values[f"line.{index}.total"] = str(total)
        field_values["invoice.payable"] = str(values["payable"])
    observation = LayoutObservation(
        source_id=source_id or page.page_id,
        image_width=image.width,
        image_height=image.height,
        column_boundaries=tuple(safety.geometry.column_boundaries),
        row_bands=tuple(tuple(band) for band in safety.geometry.row_bands),
        payable_bbox=payable_bbox,
        field_values=field_values,
    )
    return observation, safety, payable_bbox


def build_synthetic_e05_bank(observations: Sequence[Any]):
    """Use E-05's normal cluster aggregator without fabricating operator labels."""
    from e05_template_bank import TemplateBank
    from e05_template_bank.template_bank import _aggregate_cluster, _layout_compatible

    clusters: list[list[Any]] = []
    for observation in observations:
        for cluster in clusters:
            if _layout_compatible(cluster[0], observation):
                cluster.append(observation)
                break
        else:
            clusters.append([observation])
    templates = tuple(
        _aggregate_cluster(cluster, index)
        for index, cluster in enumerate(clusters, start=1)
    )
    return TemplateBank(templates=templates)


def build_synthetic_glyph_bank(
    pages: Sequence[SyntheticPage], output_path: Path
):
    """Build E-02 Glyph templates from the specified synthetic learning pages."""
    from PIL import Image
    from image_extraction_adapter.glyph_classifier import (
        GlyphTemplateSet,
        LabeledCell,
        build_templates,
    )
    from image_extraction_adapter.preprocessing import crop_spatial_cells

    templates = GlyphTemplateSet()
    logs: list[str] = []
    label_count = 0
    for page in pages:
        observation, safety, payable_bbox = observe_page(page)
        if observation is None or safety.geometry is None or payable_bbox is None:
            raise RuntimeError(
                f"synthetic learning page {page.page_id} is not safely measurable: {safety.reason}"
            )
        with Image.open(page.image_path) as opened:
            opened.load()
            image = opened.convert("RGB")
        spatial = SimpleNamespace(
            column_boundaries=tuple(safety.geometry.column_boundaries),
            row_bands=tuple(tuple(band) for band in safety.geometry.row_bands),
            assessments=(SimpleNamespace(
                field_name="invoice.payable", bbox=payable_bbox, status=None
            ),),
        )
        crops = crop_spatial_cells(
            image, spatial, include_descriptions=False, include_payable=True
        )
        labels = glyph_value_map(page.values)
        labelled = [
            LabeledCell(crop.field_name, crop.image, labels[crop.field_name])
            for crop in crops
            if crop.numeric and crop.field_name in labels
        ]
        label_count += len(labelled)
        templates, report = build_templates(labelled, templates)
        logs.extend(f"{page.page_id}: {line}" for line in report)
        templates.provenance.append({
            "image": str(page.image_path.resolve()),
            "sha256": hashlib.sha256(page.image_path.read_bytes()).hexdigest(),
        })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    templates.save(output_path)
    return templates, label_count, tuple(logs)


def glyph_value_map(values: Mapping[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {"invoice.payable": str(values["payable"])}
    for index, quantity in enumerate(values["quantities"]):
        output[f"line.{index}.quantity"] = str(quantity)
    for index, total in enumerate(values["line_totals"]):
        output[f"line.{index}.total"] = str(total)
    return output


def digit_counts(values: list[str] | tuple[str, ...]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for value in values:
        counts.update(character for character in value if character in CONTROLLED_GLYPHS)
    return counts


def normalize_numeric(value: str) -> str:
    """Normalize digit-script variants without changing separators or values."""
    from image_extraction_adapter.glyph_classifier import normalize_label_text
    return normalize_label_text(value)


def synthetic_context(page: SyntheticPage) -> dict[str, Any]:
    row_count = len(page.values["quantities"])
    return {
        "mode": "B",
        "invoice_id": f"synthetic-{page.page_id}-invoice",
        "display_number": f"SYN-{page.page_id.upper()}",
        "operation_id": f"synthetic-{page.page_id}-operation",
        "device_id": "synthetic-second-store-device",
        "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
        "store_id": "synthetic-second-store",
        "customer": {
            "phone": "+15550000000",
            "phone_status": "claimed",
            "phone_provenance": "captured",
        },
        "product_names": list(page.item_names[:row_count]),
        "product_name_provenance": ["untrusted"] * row_count,
    }
