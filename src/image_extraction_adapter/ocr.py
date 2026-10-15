"""Optional real Tesseract OCR backend using the tesserocr API binding.

The core repository remains stdlib-only. `tesserocr`, Pillow, and the requested
Tesseract traineddata are optional deployment dependencies supplied by caller.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Optional, Protocol

from .model import OCRResult


PERSIAN_TESSERACT_LANGUAGE = "fas+eng"


class OCRBackend(Protocol):
    def recognize(self, image_path: Path) -> OCRResult:
        """Read a raster image and return text plus word confidence values."""
        ...


class OCREngineUnavailable(RuntimeError):
    """The configured OCR binding or traineddata is unavailable."""


class OCRExecutionError(RuntimeError):
    """The installed OCR engine could not process this image."""


class TesseractOCR:
    """Tesseract 5 OCR backend; does not require fixed image coordinates.

    `tessdata_dir` and `language` are explicit so a deployment cannot silently
    fall back to an unconfigured language/model. For Persian invoices mixing
    Persian labels with Latin identifiers/decimals, use `fas+eng` (also exported
    as `PERSIAN_TESSERACT_LANGUAGE`) and supply both traineddata files.
    `page_segmentation_mode=None` delegates layout analysis to Tesseract AUTO.
    """

    def __init__(
        self,
        *,
        tessdata_dir: Path,
        language: str,
        page_segmentation_mode: Optional[int] = None,
    ) -> None:
        if not isinstance(language, str) or not language.strip():
            raise ValueError("language must be explicitly declared")
        self._tessdata_dir = Path(tessdata_dir).resolve()
        self._language = language.strip()
        self._psm = page_segmentation_mode

    def recognize(self, image_path: Path) -> OCRResult:
        image = Path(image_path)
        if not image.is_file():
            raise OCRExecutionError(f"image file is missing or not regular: {image}")
        if not self._tessdata_dir.is_dir():
            raise OCREngineUnavailable(
                f"Tesseract traineddata directory does not exist: {self._tessdata_dir}")
        for language in self._language.split("+"):
            model = self._tessdata_dir / f"{language}.traineddata"
            if not model.is_file():
                raise OCREngineUnavailable(
                    f"Tesseract traineddata is missing for {language!r}: {model}")

        try:
            tesserocr = importlib.import_module("tesserocr")
            pil_image = importlib.import_module("PIL.Image")
        except Exception as exc:
            raise OCREngineUnavailable(
                "install the optional tesserocr and Pillow packages to enable OCR") from exc

        psm = self._psm
        if psm is None:
            psm = tesserocr.PSM.AUTO
        try:
            with pil_image.open(image) as opened:
                opened.load()
                raster = opened.convert("RGB")
            with tesserocr.PyTessBaseAPI(
                    path=str(self._tessdata_dir), lang=self._language, psm=psm) as api:
                api.SetImage(raster)
                text = api.GetUTF8Text() or ""
                raw_confidences = api.AllWordConfidences() or ()
                confidences = tuple(
                    float(value) for value in raw_confidences
                    if isinstance(value, (int, float)) and 0 <= value <= 100
                )
                version = str(tesserocr.tesseract_version()).splitlines()[0]
        except OCREngineUnavailable:
            raise
        except Exception as exc:
            raise OCRExecutionError(
                f"Tesseract failed to process image {image.name}: {exc}") from exc

        return OCRResult(
            engine=version,
            language=self._language,
            text=text,
            word_confidences=confidences,
        )
