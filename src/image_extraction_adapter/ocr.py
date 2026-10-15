"""Optional real Tesseract OCR backend with word-level spatial data.

The core repository remains stdlib-only. `tesserocr`, Pillow, and the requested
Tesseract traineddata are optional deployment dependencies supplied by caller.
Tesseract's TSV API returns the same level-5 text/confidence/left/top/width/height
columns used by `pytesseract.image_to_data`, without requiring a separate CLI.
"""
from __future__ import annotations

import csv
import importlib
import io
from pathlib import Path
from typing import Optional, Protocol

from .model import OCRResult, OCRWord


PERSIAN_TESSERACT_LANGUAGE = "fas+eng"


class OCRBackend(Protocol):
    def recognize(self, image_path: Path) -> OCRResult:
        """Read a raster image and return text, scores, and word boxes."""
        ...


class OCREngineUnavailable(RuntimeError):
    """The configured OCR binding or traineddata is unavailable."""


class OCRExecutionError(RuntimeError):
    """The installed OCR engine could not process this image."""


def _parse_tsv_words(tsv: str) -> tuple[OCRWord, ...]:
    """Parse Tesseract TSV level-5 rows, retaining whitespace rule boxes."""
    words: list[OCRWord] = []
    for row in csv.reader(io.StringIO(tsv), delimiter="\t"):
        if len(row) < 12 or row[0].strip().casefold() == "level":
            continue
        try:
            level = int(row[0])
            if level != 5:
                continue
            page_num, block_num, paragraph_num, line_num, word_num = (
                int(value) for value in row[1:6]
            )
            left, top, width, height = (int(value) for value in row[6:10])
            confidence = float(row[10])
        except (TypeError, ValueError):
            continue
        text = "\t".join(row[11:])
        words.append(OCRWord(
            text=text,
            left=left,
            top=top,
            width=width,
            height=height,
            confidence=confidence,
            block_num=block_num,
            paragraph_num=paragraph_num,
            line_num=line_num,
            word_num=word_num,
        ))
    return tuple(words)


class TesseractOCR:
    """Tesseract 5 backend returning raw UTF-8 text and TSV word boxes.

    `tessdata_dir` and `language` are explicit so a deployment cannot silently
    fall back to an unconfigured language/model. For Persian invoices mixing
    Persian labels with Latin identifiers/decimals, use `fas+eng` (also exported
    as `PERSIAN_TESSERACT_LANGUAGE`) and supply both traineddata files.
    `page_segmentation_mode=None` delegates layout analysis to Tesseract AUTO.
    The TSV boxes are image-space coordinates in pixels.
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
                image_width, image_height = opened.size
                raster = opened.convert("RGB")
            with tesserocr.PyTessBaseAPI(
                    path=str(self._tessdata_dir), lang=self._language, psm=psm) as api:
                api.SetImage(raster)
                text = api.GetUTF8Text() or ""
                tsv = api.GetTSVText(0) or ""
                words = _parse_tsv_words(tsv)
                raw_confidences = api.AllWordConfidences() or ()
                confidences = tuple(
                    float(value) for value in raw_confidences
                    if isinstance(value, (int, float)) and 0 <= value <= 100
                )
                # The TSV and API confidence lists should align. Retain the TSV
                # values when possible so each score belongs to its bounding box.
                if len(words) == len(confidences):
                    confidences = tuple(word.confidence for word in words)
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
            words=words,
            image_width=image_width,
            image_height=image_height,
        )
