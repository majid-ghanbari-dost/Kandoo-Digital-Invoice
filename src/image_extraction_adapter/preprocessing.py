"""Pillow-only cell cropping, thresholding, and morphological rule removal.

All operations work on copies. The source invoice image is never modified or
replaced. Pillow is loaded lazily so the base adapter remains stdlib-only.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Literal


PreprocessingMode = Literal["none", "otsu", "adaptive"]
PREPROCESSING_MODES: tuple[PreprocessingMode, ...] = ("none", "otsu", "adaptive")
_CELL_CLASS_INFO_KEY = "kandoo_cell_class"


@dataclass(frozen=True)
class CellCrop:
    """One cropped spatial cell; coordinates are (left, top, right, bottom)."""

    field_name: str
    bbox: tuple[int, int, int, int]
    image: Any
    numeric: bool


@dataclass(frozen=True)
class PreprocessedCell:
    """OCR image plus a count of foreground pixels removed as table rules."""

    image: Any
    mode: PreprocessingMode
    line_pixels_removed: int = 0


@dataclass(frozen=True)
class DynamicTableLayout:
    """Image-projection result for a table's columns and item-row bands."""

    column_boundaries: tuple[float, ...]
    row_bands: tuple[tuple[float, float], ...]
    horizontal_lines: tuple[float, ...]
    vertical_lines: tuple[float, ...]
    median_row_height: float
    header_row_excluded: bool


@dataclass(frozen=True)
class LayoutSafetyResult:
    """Fail-closed status wrapper around the existing layout geometry."""

    status: Literal["OK", "REVIEW", "BLOCKED"]
    reason: str
    geometry: Any | None
    row_count: int | None


def _pillow():
    try:
        from PIL import Image, ImageChops, ImageFilter, ImageOps
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Pillow is required for cell cropping/preprocessing") from exc
    return Image, ImageChops, ImageFilter, ImageOps


def _crop_box(
    x_left: float,
    y_top: float,
    x_right: float,
    y_bottom: float,
    *,
    image_size: tuple[int, int],
    padding: int = 0,
) -> tuple[int, int, int, int] | None:
    width, height = image_size
    box = (
        max(0, math.floor(x_left) - padding),
        max(0, math.floor(y_top) - padding),
        min(width, math.ceil(x_right) + padding),
        min(height, math.ceil(y_bottom) + padding),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    return box


def _contiguous_groups(indices: list[int]) -> list[list[int]]:
    groups: list[list[int]] = []
    for index in indices:
        if not groups or index > groups[-1][-1] + 1:
            groups.append([index])
        else:
            groups[-1].append(index)
    return groups


def _longest_black_runs(binary_image: Any, *, horizontal: bool) -> list[int]:
    """Measure contiguous black runs on each row or column of a binary copy."""
    width, height = binary_image.size
    pixels = binary_image.convert("L").tobytes()
    count = height if horizontal else width
    span = width if horizontal else height
    runs: list[int] = []
    for primary in range(count):
        longest = current = 0
        for secondary in range(span):
            offset = (primary * width + secondary if horizontal
                      else secondary * width + primary)
            if pixels[offset] < 128:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        runs.append(longest)
    return runs


def _long_line_centers(runs: list[int], *, fraction: float = 0.8) -> tuple[float, ...]:
    longest = max(runs, default=0)
    if longest <= 0:
        return ()
    cutoff = math.ceil(longest * fraction)
    candidates = [index for index, length in enumerate(runs) if length >= cutoff]
    return tuple((group[0] + group[-1]) / 2.0
                 for group in _contiguous_groups(candidates))


def _longest_regular_line_chain(
    lines: tuple[float, ...],
    *,
    minimum_ratio: float = 0.65,
    maximum_ratio: float = 1.4,
) -> tuple[float, ...]:
    """Pick the longest median-spaced sequence; short rounded-box edges split it."""
    if len(lines) < 2:
        return ()
    gaps = [right - left for left, right in zip(lines, lines[1:])]
    pitch = statistics.median(gaps)
    if pitch <= 0:
        return ()
    minimum_gap = minimum_ratio * pitch
    maximum_gap = maximum_ratio * pitch
    chains: list[list[float]] = []
    current = [lines[0]]
    for line in lines[1:]:
        gap = line - current[-1]
        if minimum_gap <= gap <= maximum_gap:
            current.append(line)
        else:
            chains.append(current)
            current = [line]
    chains.append(current)
    best = max(chains, key=lambda chain: (
        len(chain), chain[-1] - chain[0], -chain[0]))
    return tuple(best) if len(best) >= 2 else ()


def detect_dynamic_table_layout(
    image: Any,
    *,
    line_fraction: float = 0.8,
    minimum_row_ratio: float = 0.65,
    maximum_row_ratio: float = 1.4,
) -> DynamicTableLayout | None:
    """Detect table borders from horizontal/vertical image projections.

    A line candidate must contain a contiguous black run at least 80% as long
    as the longest run on that axis. The table is the longest median-spaced
    horizontal-line chain. A shorter leading interval is treated as the table
    header; the remaining consecutive intervals are item rows. Median row
    height rejects nearby short rounded-payable borders and other false edges.
    Column rules are projected only between the selected table's first and last
    horizontal borders. No page-specific coordinates or expected row count are
    used.
    """
    try:
        binary = otsu_binarize(image)
    except (RuntimeError, AttributeError, TypeError, ValueError):
        return None

    horizontal_runs = _longest_black_runs(binary, horizontal=True)
    horizontal_candidates = _long_line_centers(
        horizontal_runs, fraction=line_fraction)
    chain = _longest_regular_line_chain(
        horizontal_candidates,
        minimum_ratio=minimum_row_ratio,
        maximum_ratio=maximum_row_ratio,
    )
    if len(chain) < 2:
        return None

    chain_gaps = [right - left for left, right in zip(chain, chain[1:])]
    header_row_excluded = False
    if len(chain_gaps) >= 2:
        body_pitch = statistics.median(chain_gaps[1:])
        if body_pitch > 0 and chain_gaps[0] < 0.92 * body_pitch:
            header_row_excluded = True
    body_borders = chain[1:] if header_row_excluded else chain
    body_gaps = [right - left for left, right in zip(body_borders, body_borders[1:])]
    if not body_gaps:
        return None

    median_row_height = statistics.median(body_gaps)
    row_bands = tuple(
        (top, bottom)
        for top, bottom in zip(body_borders, body_borders[1:])
        if minimum_row_ratio * median_row_height
        <= bottom - top
        <= maximum_row_ratio * median_row_height
    )
    if not row_bands:
        return None

    width, height = binary.size
    pixels = binary.convert("L").tobytes()
    y_start = max(0, math.floor(chain[0]))
    y_end = min(height - 1, math.ceil(chain[-1]))
    vertical_runs: list[int] = []
    for x in range(width):
        longest = current = 0
        for y in range(y_start, y_end + 1):
            if pixels[y * width + x] < 128:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        vertical_runs.append(longest)
    longest_vertical = max(vertical_runs, default=0)
    if longest_vertical <= 0:
        return None
    vertical_cutoff = math.ceil(longest_vertical * line_fraction)
    vertical_candidates = [
        x for x, length in enumerate(vertical_runs) if length >= vertical_cutoff]
    vertical_lines = tuple(
        (group[0] + group[-1]) / 2.0
        for group in _contiguous_groups(vertical_candidates)
    )
    # This invoice table has four RTL columns (amount, quantity, name, sequence)
    # bounded by five rules. Ambiguous extra/missing rules fail closed.
    if len(vertical_lines) != 5:
        return None
    if any(right <= left for left, right in zip(vertical_lines, vertical_lines[1:])):
        return None

    return DynamicTableLayout(
        column_boundaries=vertical_lines,
        row_bands=row_bands,
        horizontal_lines=chain,
        vertical_lines=vertical_lines,
        median_row_height=median_row_height,
        header_row_excluded=header_row_excluded,
    )


def _layout_geometry_issues(layout: DynamicTableLayout) -> list[str]:
    """Return structural problems without changing detector behavior."""
    issues: list[str] = []

    def ordered_values(
        name: str,
        values: Any,
        *,
        expected_count: int | None = None,
        minimum_count: int = 1,
    ) -> None:
        try:
            numbers = tuple(float(value) for value in values)
        except (TypeError, ValueError, OverflowError):
            issues.append(f"{name} is missing or non-numeric")
            return
        if expected_count is not None and len(numbers) != expected_count:
            issues.append(f"{name} must contain exactly {expected_count} values")
        elif len(numbers) < minimum_count:
            issues.append(f"{name} must contain at least {minimum_count} values")
        if any(not math.isfinite(value) for value in numbers):
            issues.append(f"{name} contains non-finite values")
        if any(right <= left for left, right in zip(numbers, numbers[1:])):
            issues.append(f"{name} is not strictly increasing")

    ordered_values("column_boundaries", layout.column_boundaries, expected_count=5)
    ordered_values("vertical_lines", layout.vertical_lines, expected_count=5)
    ordered_values("horizontal_lines", layout.horizontal_lines, minimum_count=2)

    try:
        row_bands = tuple(layout.row_bands)
    except TypeError:
        row_bands = ()
        issues.append("row_bands is missing or invalid")
    if not row_bands:
        issues.append("row_bands contains no item rows")
    previous_bottom: float | None = None
    for index, band in enumerate(row_bands):
        try:
            top, bottom = (float(value) for value in band)
        except (TypeError, ValueError, OverflowError):
            issues.append(f"row_bands[{index}] is not a numeric (top, bottom) pair")
            continue
        if not math.isfinite(top) or not math.isfinite(bottom) or bottom <= top:
            issues.append(f"row_bands[{index}] has invalid bounds")
        if previous_bottom is not None and top < previous_bottom:
            issues.append(f"row_bands[{index}] overlaps or precedes the previous row")
        previous_bottom = bottom

    try:
        median_row_height = float(layout.median_row_height)
    except (TypeError, ValueError, OverflowError):
        median_row_height = 0.0
    if not math.isfinite(median_row_height) or median_row_height <= 0:
        issues.append("median_row_height must be positive and finite")

    return issues


def detect_layout_safe(image: Any) -> LayoutSafetyResult:
    """Call the unchanged projection detector and fail closed on its result.

    The detector's public API still returns ``DynamicTableLayout | None``.
    This additive wrapper translates its result into OK/REVIEW/BLOCKED and
    treats geometry that reaches the image edge as likely truncated input.
    """
    try:
        layout = detect_dynamic_table_layout(image)
    except Exception as exc:
        return LayoutSafetyResult(
            status="BLOCKED",
            reason=f"Layout detector raised {type(exc).__name__}: {exc}",
            geometry=None,
            row_count=None,
        )

    if layout is None:
        return LayoutSafetyResult(
            status="BLOCKED",
            reason="No table geometry was detected.",
            geometry=None,
            row_count=None,
        )

    if not isinstance(layout, DynamicTableLayout):
        return LayoutSafetyResult(
            status="REVIEW",
            reason="Detector returned an unsupported or incomplete geometry type.",
            geometry=layout,
            row_count=None,
        )

    try:
        row_bands = tuple(layout.row_bands)
        row_count = len(row_bands)
    except Exception as exc:
        return LayoutSafetyResult(
            status="REVIEW",
            reason=f"Could not determine the detected row count: {type(exc).__name__}: {exc}",
            geometry=layout,
            row_count=None,
        )

    try:
        issues = _layout_geometry_issues(layout)
    except Exception as exc:
        return LayoutSafetyResult(
            status="BLOCKED",
            reason=f"Could not validate detected geometry: {type(exc).__name__}: {exc}",
            geometry=None,
            row_count=None,
        )
    if row_count < 1 or row_count > 50:
        issues.append(f"row count {row_count} is outside the supported range 1..50")
    if issues:
        return LayoutSafetyResult(
            status="REVIEW",
            reason="Incomplete or unreasonable table geometry: " + "; ".join(issues),
            geometry=layout,
            row_count=row_count,
        )

    try:
        width, height = image.size
        edge_margin = 5
        horizontal = tuple(float(value) for value in layout.horizontal_lines)
        vertical = tuple(float(value) for value in layout.vertical_lines)
        reaches_image_edge = (
            any(value <= edge_margin or value >= height - 1 - edge_margin
                for value in horizontal)
            or any(value <= edge_margin or value >= width - 1 - edge_margin
                   for value in vertical)
        )
    except Exception as exc:
        return LayoutSafetyResult(
            status="BLOCKED",
            reason=f"Could not validate image bounds: {type(exc).__name__}: {exc}",
            geometry=None,
            row_count=None,
        )

    if reaches_image_edge:
        return LayoutSafetyResult(
            status="BLOCKED",
            reason="Detected table geometry reaches the image edge; input may be truncated.",
            geometry=None,
            row_count=None,
        )

    return LayoutSafetyResult(
        status="OK",
        reason="Complete table geometry detected.",
        geometry=layout,
        row_count=row_count,
    )


def _cell_class_for_field(field_name: str) -> str | None:
    if field_name == "invoice.payable":
        return "payable"
    for class_name in ("total", "quantity", "description"):
        if field_name.endswith(f".{class_name}"):
            return class_name
    return None


def _tag_cell_image(image: Any, field_name: str) -> Any:
    """Attach the crop class to its private Pillow image copy for preprocessing."""
    cell_class = _cell_class_for_field(field_name)
    if cell_class is not None:
        existing_info = getattr(image, "info", None)
        info = dict(existing_info) if isinstance(existing_info, dict) else {}
        info[_CELL_CLASS_INFO_KEY] = cell_class
        image.info = info
    return image


def crop_spatial_cells(
    image: Any,
    spatial: Any,
    *,
    include_descriptions: bool = True,
    include_payable: bool = True,
    horizontal_inset: int = 4,
    top_inset: int = 8,
    bottom_inset: int = 3,
    payable_padding: int = 4,
) -> tuple[CellCrop, ...]:
    """Crop row cells from detected column bounds and y-position row bands.

    The table is read right-to-left: amount, quantity, description, sequence.
    No fixed page coordinates are used. Unit-price cells are omitted when the
    layout parser did not find a unit-price column.
    """
    layout = detect_dynamic_table_layout(image)
    if layout is not None:
        boundaries = layout.column_boundaries
        row_bands = layout.row_bands
    else:
        # Preserve the existing spatial parser as a fail-closed compatibility
        # fallback when projection geometry is incomplete or Pillow is absent.
        boundaries = tuple(getattr(spatial, "column_boundaries", ()))
        row_bands = tuple(getattr(spatial, "row_bands", ()))
    if len(boundaries) != 5 or not row_bands:
        return ()

    crops: list[CellCrop] = []
    width, height = image.size
    column_specs = [
        ("total", boundaries[0], boundaries[1], True),
        ("quantity", boundaries[1], boundaries[2], True),
    ]
    if include_descriptions:
        column_specs.append(("description", boundaries[2], boundaries[3], False))

    for row_index, (top, bottom) in enumerate(row_bands):
        for suffix, left, right, numeric in column_specs:
            box = _crop_box(
                left + horizontal_inset,
                top + top_inset,
                right - horizontal_inset,
                bottom - bottom_inset,
                image_size=(width, height),
            )
            if box is None:
                continue
            field_name = f"line.{row_index}.{suffix}"
            crops.append(CellCrop(
                field_name=field_name,
                bbox=box,
                image=_tag_cell_image(image.crop(box).copy(), field_name),
                numeric=numeric,
            ))

    if include_payable:
        payable = next((
            assessment for assessment in getattr(spatial, "assessments", ())
            if assessment.field_name == "invoice.payable" and assessment.bbox
        ), None)
        if payable is not None:
            left, top, box_width, box_height = payable.bbox
            box = _crop_box(
                left, top, left + box_width, top + box_height,
                image_size=(width, height), padding=payable_padding,
            )
            if box is not None:
                crops.append(CellCrop(
                    field_name="invoice.payable",
                    bbox=box,
                    image=_tag_cell_image(
                        image.crop(box).copy(), "invoice.payable"),
                    numeric=True,
                ))
    return tuple(crops)


def otsu_threshold(image: Any) -> int:
    """Return the global Otsu threshold for a grayscale image."""
    _, _, _, image_ops = _pillow()
    gray = image_ops.autocontrast(image.convert("L"))
    histogram = gray.histogram()[:256]
    total = sum(histogram)
    if total == 0:
        return 127
    total_sum = sum(level * count for level, count in enumerate(histogram))
    background_weight = 0
    background_sum = 0
    best_variance = -1.0
    threshold = 127
    for level, count in enumerate(histogram):
        background_weight += count
        background_sum += level * count
        foreground_weight = total - background_weight
        if background_weight == 0 or foreground_weight == 0:
            continue
        background_mean = background_sum / background_weight
        foreground_mean = (total_sum - background_sum) / foreground_weight
        variance = (background_weight * foreground_weight
                    * (background_mean - foreground_mean) ** 2)
        if variance > best_variance:
            best_variance = variance
            threshold = level
    return threshold


def otsu_binarize(image: Any) -> Any:
    """Return a black-text/white-background Otsu image, including threshold 0."""
    _, _, _, image_ops = _pillow()
    gray = image_ops.autocontrast(image.convert("L"))
    threshold = otsu_threshold(gray)
    # `<=` is important for already-binary scans where Otsu's threshold is 0.
    return gray.point(lambda pixel: 0 if pixel <= threshold else 255)


def adaptive_binarize(
    image: Any, *, radius: int = 9, offset: int = 10
) -> Any:
    """Local-mean adaptive threshold using Pillow's box blur as the mean image."""
    _, _, image_filter, image_ops = _pillow()
    gray = image_ops.autocontrast(image.convert("L"))
    local_mean = gray.filter(image_filter.BoxBlur(max(1, int(radius))))
    source = gray.load()
    mean = local_mean.load()
    output = gray.copy()
    target = output.load()
    for y in range(gray.height):
        for x in range(gray.width):
            target[x, y] = 0 if source[x, y] <= mean[x, y] - offset else 255
    return output


def _shift_with_black_fill(image: Any, dx: int, dy: int) -> Any:
    """Translate a mask without wraparound; pixels outside the crop are black."""
    Image, _, _, _ = _pillow()
    width, height = image.size
    shifted = Image.new("L", (width, height), 0)
    source_left = max(0, -dx)
    source_top = max(0, -dy)
    source_right = min(width, width - dx)
    source_bottom = min(height, height - dy)
    if source_right > source_left and source_bottom > source_top:
        shifted.paste(
            image.crop((source_left, source_top, source_right, source_bottom)),
            (max(0, dx), max(0, dy)),
        )
    return shifted


def _morph_axis(image: Any, length: int, *, horizontal: bool, erode: bool) -> Any:
    Image, image_chops, _, _ = _pillow()
    length = max(3, int(length))
    if length % 2 == 0:
        length += 1
    radius = length // 2
    initial = 255 if erode else 0
    result = Image.new("L", image.size, initial)
    for offset in range(-radius, radius + 1):
        shifted = _shift_with_black_fill(
            image,
            offset if horizontal else 0,
            0 if horizontal else offset,
        )
        result = (image_chops.darker(result, shifted) if erode
                  else image_chops.lighter(result, shifted))
    return result


def _opening_line_mask(image: Any, length: int, *, horizontal: bool) -> Any:
    eroded = _morph_axis(image, length, horizontal=horizontal, erode=True)
    return _morph_axis(eroded, length, horizontal=horizontal, erode=False)


def remove_morphological_table_lines(
    binary_image: Any,
    *,
    horizontal_kernel: int | None = None,
    vertical_kernel: int | None = None,
    skip_vertical_rule_removal: bool = False,
) -> tuple[Any, int]:
    """Remove long horizontal/vertical rules from a binarized cell copy.

    Morphological opening with directional line kernels identifies likely table
    rules. The detected union is subtracted from the foreground mask; pixels
    outside the mask are unchanged. `skip_vertical_rule_removal` defaults to
    False to preserve the existing behavior. When True, horizontal rules are
    still removed while the vertical-rule mask is omitted. Returns the cleaned
    binary image and count of removed foreground pixels.
    """
    Image, image_chops, _, image_ops = _pillow()
    gray = binary_image.convert("L")
    width, height = gray.size
    if horizontal_kernel is None:
        horizontal_kernel = max(15, int(width * 0.55))
    if vertical_kernel is None:
        vertical_kernel = max(15, int(height * 0.55))
    foreground = image_ops.invert(gray)
    horizontal_mask = _opening_line_mask(
        foreground, horizontal_kernel, horizontal=True)
    if skip_vertical_rule_removal:
        vertical_mask = Image.new("L", foreground.size, 0)
    else:
        vertical_mask = _opening_line_mask(
            foreground, vertical_kernel, horizontal=False)
    line_mask = image_chops.lighter(horizontal_mask, vertical_mask)
    cleaned_foreground = image_chops.subtract(foreground, line_mask)
    removed_pixels = sum(1 for value in line_mask.get_flattened_data() if value > 0)
    return image_ops.invert(cleaned_foreground), removed_pixels


def preprocess_cell(
    image: Any,
    mode: PreprocessingMode,
    *,
    adaptive_radius: int = 9,
    adaptive_offset: int = 10,
    skip_vertical_rule_removal: bool = False,
) -> PreprocessedCell:
    """Prepare a cell for OCR without mutating the original crop.

    `none` is the unthresholded control. Otsu and adaptive modes each threshold
    a grayscale copy and then remove detected table rules. The vertical-rule
    skip flag defaults to False; tagged payable crops also skip only vertical
    rule removal, without changing total, quantity, or untagged-image behavior.
    """
    _, _, _, image_ops = _pillow()
    if mode not in PREPROCESSING_MODES:
        raise ValueError(f"unsupported preprocessing mode: {mode!r}")
    if mode == "none":
        return PreprocessedCell(image=image.copy(), mode=mode)

    if mode == "otsu":
        binary = otsu_binarize(image)
    else:
        binary = adaptive_binarize(
            image, radius=adaptive_radius, offset=adaptive_offset)
    image_info = getattr(image, "info", None)
    cell_class = (
        image_info.get(_CELL_CLASS_INFO_KEY)
        if isinstance(image_info, dict) else None
    )
    skip_vertical = skip_vertical_rule_removal or cell_class == "payable"
    cleaned, removed = remove_morphological_table_lines(
        binary, skip_vertical_rule_removal=skip_vertical)
    return PreprocessedCell(
        image=image_ops.autocontrast(cleaned),
        mode=mode,
        line_pixels_removed=removed,
    )
