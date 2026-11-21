"""Deterministic synthetic image variants used only to calibrate/test E-28 DR-1.

These controls alter detected numeric cell crops while leaving the surrounding
page layout untouched; they are not claimed as genuine printer or scanner data.
"""
from __future__ import annotations

from typing import Any

from PIL import Image, ImageEnhance, ImageFilter

from image_extraction_adapter.pipeline_v0 import (
    _spatial_for_geometry,
    detect_payable_bbox,
)
from image_extraction_adapter.preprocessing import (
    crop_spatial_cells,
    detect_layout_safe,
)

CLEAN_VARIANTS = (
    "identity",
    "brightness_1.01",
    "contrast_1.01",
    "cell_blur_0.75",
)
STRESS_VARIANTS = (
    "cell_thinning_maxfilter_3",
    "cell_blur_1.0",
    "cell_salt_pepper_2pct",
)


def _numeric_crops(image: Any):
    safety = detect_layout_safe(image)
    if safety.status != "OK" or safety.geometry is None:
        raise ValueError(f"cannot calibrate image with layout status {safety.status}: {safety.reason}")
    spatial = _spatial_for_geometry(
        safety.geometry,
        detect_payable_bbox(image, safety.geometry),
    )
    return crop_spatial_cells(
        image,
        spatial,
        include_descriptions=False,
        include_payable=True,
    )


def apply_calibration_variant(image: Any, variant: str) -> Any:
    """Return a deterministic clean control or synthetic stress image."""
    source = image.convert("RGB")
    if variant == "identity":
        return source.copy()
    if variant == "brightness_1.01":
        return ImageEnhance.Brightness(source).enhance(1.01)
    if variant == "contrast_1.01":
        return ImageEnhance.Contrast(source).enhance(1.01)

    transforms = {
        "cell_blur_0.75": lambda crop: crop.filter(ImageFilter.GaussianBlur(0.75)),
        "cell_thinning_maxfilter_3": lambda crop: crop.filter(ImageFilter.MaxFilter(3)),
        "cell_blur_1.0": lambda crop: crop.filter(ImageFilter.GaussianBlur(1.0)),
    }
    if variant not in (*transforms, "cell_salt_pepper_2pct"):
        raise ValueError(f"unknown E-28 calibration variant: {variant}")

    output = source.copy()
    for crop in _numeric_crops(source):
        local = crop.image.convert("RGB")
        if variant == "cell_salt_pepper_2pct":
            gray = local.convert("L")
            width, _ = gray.size
            pixels = bytearray(gray.tobytes())
            # Fixed integer hash: about 2% of pixels receive salt/pepper noise.
            for index, pixel in enumerate(pixels):
                selector = (index * 7919 + 7 * 104729) % 10000
                if selector < 200:
                    pixels[index] = 0 if (index * 104729 + 7) % 2 else 255
                else:
                    pixels[index] = pixel
            local = Image.frombytes("L", gray.size, bytes(pixels)).convert("RGB")
        else:
            local = transforms[variant](local)
        output.paste(local, crop.bbox)
    return output


__all__ = ["CLEAN_VARIANTS", "STRESS_VARIANTS", "apply_calibration_variant"]
