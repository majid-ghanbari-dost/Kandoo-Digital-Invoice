"""Pillow-only cell cropping, thresholding, and morphological rule removal.

All operations work on copies. The source invoice image is never modified or
replaced. Pillow is loaded lazily so the base adapter remains stdlib-only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal


PreprocessingMode = Literal["none", "otsu", "adaptive"]
PREPROCESSING_MODES: tuple[PreprocessingMode, ...] = ("none", "otsu", "adaptive")


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
            crops.append(CellCrop(
                field_name=f"line.{row_index}.{suffix}",
                bbox=box,
                image=image.crop(box).copy(),
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
                    image=image.crop(box).copy(),
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
) -> tuple[Any, int]:
    """Remove long horizontal/vertical rules from a binarized cell copy.

    Morphological opening with directional line kernels identifies likely table
    rules. The detected union is subtracted from the foreground mask; pixels
    outside the mask are unchanged. A mask can intersect a glyph near a rule,
    so resulting OCR remains subject to confidence/format review. Returns the
    cleaned binary image and count of removed foreground pixels.
    """
    _, image_chops, _, image_ops = _pillow()
    gray = binary_image.convert("L")
    width, height = gray.size
    if horizontal_kernel is None:
        horizontal_kernel = max(15, int(width * 0.55))
    if vertical_kernel is None:
        vertical_kernel = max(15, int(height * 0.55))
    foreground = image_ops.invert(gray)
    horizontal_mask = _opening_line_mask(
        foreground, horizontal_kernel, horizontal=True)
    vertical_mask = _opening_line_mask(
        foreground, vertical_kernel, horizontal=False)
    line_mask = image_chops.lighter(horizontal_mask, vertical_mask)
    cleaned_foreground = image_chops.subtract(foreground, line_mask)
    removed_pixels = sum(1 for value in line_mask.getdata() if value > 0)
    return image_ops.invert(cleaned_foreground), removed_pixels


def preprocess_cell(
    image: Any,
    mode: PreprocessingMode,
    *,
    adaptive_radius: int = 9,
    adaptive_offset: int = 10,
) -> PreprocessedCell:
    """Prepare a cell for OCR without mutating the original crop.

    `none` is the unthresholded control. Otsu and adaptive modes each threshold
    a grayscale copy and then remove detected horizontal/vertical table rules.
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
    cleaned, removed = remove_morphological_table_lines(binary)
    return PreprocessedCell(
        image=image_ops.autocontrast(cleaned),
        mode=mode,
        line_pixels_removed=removed,
    )
