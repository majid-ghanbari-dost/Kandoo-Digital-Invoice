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
import re
from pathlib import Path
from typing import Any, Optional, Protocol

from .model import CellOCRVariantResult, OCRResult, OCRWord
from .preprocessing import PREPROCESSING_MODES, crop_spatial_cells, preprocess_cell


PERSIAN_TESSERACT_LANGUAGE = "fas+eng"
NUMERIC_TESSERACT_WHITELIST = "0123456789۰۱۲۳۴۵۶۷۸۹.,"
_NUMERIC_DIGITS = "0123456789۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"
_NUMERIC_DIGITS_ASCII = "012345678901234567890123456789"
_NUMERIC_DIGIT_TRANSLATION = str.maketrans(
    _NUMERIC_DIGITS, _NUMERIC_DIGITS_ASCII)
_NUMERIC_FORMAT = re.compile(
    r"^(?:[0-9۰-۹٠-٩]+|[0-9۰-۹٠-٩]{1,3}(?:,[0-9۰-۹٠-٩]{3})+)"
    r"(?:\.[0-9۰-۹٠-٩]+)?$"
)


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


def _digits_for_diagnostic(value: str) -> str:
    return "".join(
        char.translate(_NUMERIC_DIGIT_TRANSLATION)
        for char in value
        if char.translate(_NUMERIC_DIGIT_TRANSLATION).isdigit()
    )


def _numeric_cell_review_reason(
    raw_value: str,
    *,
    unrestricted_raw_value: str,
    confidence: Optional[float],
    minimum_confidence: float,
    source_status: Optional[str],
) -> Optional[str]:
    """Reject invalid/ambiguous numeric output without normalizing its value."""
    reasons: list[str] = []
    if not raw_value:
        reasons.append("cell OCR returned no numeric text")
    if any(char in raw_value or char in unrestricted_raw_value for char in "|!"):
        reasons.append("pipe/exclamation OCR glyph is invalid; no digit substitution allowed")
    if confidence is None:
        reasons.append("cell OCR returned no confidence score")
    elif confidence < minimum_confidence:
        reasons.append(
            f"cell OCR confidence {confidence:.2f} is below "
            f"{minimum_confidence:.2f}")
    if raw_value and _NUMERIC_FORMAT.fullmatch(raw_value) is None:
        reasons.append("raw cell OCR does not match the declared numeric format")
    if unrestricted_raw_value and raw_value:
        if _digits_for_diagnostic(unrestricted_raw_value) != _digits_for_diagnostic(raw_value):
            reasons.append("whitelisted OCR differs from unrestricted diagnostic OCR")
    if source_status == "REVIEW":
        reasons.append("full-page spatial assessment remains REVIEW; cell OCR is supplementary")
    return "; ".join(dict.fromkeys(reasons)) or None


def _prepare_cell_for_tesseract(
    image: Any, *, scale_factor: int = 2, white_padding: int = 8
) -> Any:
    try:
        from PIL import Image, ImageOps
    except Exception as exc:  # pragma: no cover - environment dependent
        raise OCREngineUnavailable("Pillow is required for cell OCR") from exc
    if scale_factor < 1 or scale_factor > 6:
        raise ValueError("cell OCR scale_factor must be from 1 through 6")
    fill = 255 if image.mode == "L" else (255, 255, 255)
    prepared = ImageOps.expand(image, border=white_padding, fill=fill)
    if scale_factor > 1:
        prepared = prepared.resize(
            (prepared.width * scale_factor, prepared.height * scale_factor),
            Image.Resampling.LANCZOS,
        )
    return prepared.convert("RGB")


def _cell_confidence(api: Any) -> Optional[float]:
    try:
        score = float(api.MeanTextConf())
    except Exception:
        return None
    return score if 0 <= score <= 100 else None


def _cell_text(api: Any) -> str:
    return (api.GetUTF8Text() or "").strip()


def _clear_cell_adaptation(api: Any) -> None:
    clear = getattr(api, "ClearAdaptiveClassifier", None)
    if callable(clear):
        clear()


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

    def recognize_spatial_cells(
        self,
        image_path: Path,
        spatial: Any,
        *,
        minimum_confidence: float,
        scale_factor: int = 3,
        white_padding: int = 8,
    ) -> tuple[CellOCRVariantResult, ...]:
        """OCR geometry-cropped cells with PSM 7 and explicit numeric whitelist.

        Numeric cells are run through raw, Otsu, and adaptive variants. Otsu and
        adaptive images receive directional morphological line removal. A
        separate unrestricted pass is retained as a diagnostic: if it reads
        `|` or `!`, a whitelisted numeric result remains REVIEW. Description
        cells use PSM 7 without a numeric whitelist. These observations never
        overwrite the full-page field values or make a review result issuable.
        """
        image = Path(image_path)
        if not image.is_file():
            raise OCRExecutionError(f"image file is missing or not regular: {image}")
        if (isinstance(minimum_confidence, bool)
                or not isinstance(minimum_confidence, (int, float))
                or not 0 <= float(minimum_confidence) <= 100):
            raise ValueError("minimum_confidence must be a number from 0 to 100")
        try:
            tesserocr = importlib.import_module("tesserocr")
            pil_image = importlib.import_module("PIL.Image")
        except Exception as exc:
            raise OCREngineUnavailable(
                "install the optional tesserocr and Pillow packages for cell OCR") from exc

        try:
            with pil_image.open(image) as opened:
                opened.load()
                source = opened.convert("RGB")
            cells = crop_spatial_cells(source, spatial)
            if not cells:
                return ()

            psm = getattr(tesserocr.PSM, "SINGLE_LINE", 7)
            results: list[CellOCRVariantResult] = []
            source_assessments = {
                assessment.field_name: assessment
                for assessment in getattr(spatial, "assessments", ())
            }
            with tesserocr.PyTessBaseAPI(
                    path=str(self._tessdata_dir), lang=self._language, psm=psm) as numeric_api, \
                    tesserocr.PyTessBaseAPI(
                    path=str(self._tessdata_dir), lang=self._language, psm=psm) as unrestricted_api:
                if not numeric_api.SetVariable(
                        "tessedit_char_whitelist", NUMERIC_TESSERACT_WHITELIST):
                    raise OCRExecutionError("Tesseract rejected the numeric character whitelist")

                for cell in cells:
                    baseline = preprocess_cell(cell.image, "none")
                    baseline_image = _prepare_cell_for_tesseract(
                        baseline.image,
                        scale_factor=scale_factor,
                        white_padding=white_padding,
                    )
                    _clear_cell_adaptation(unrestricted_api)
                    unrestricted_api.SetImage(baseline_image)
                    unrestricted_raw = _cell_text(unrestricted_api)
                    unrestricted_confidence = _cell_confidence(unrestricted_api)
                    source_assessment = source_assessments.get(cell.field_name)
                    source_status = (
                        source_assessment.status if source_assessment is not None else None)

                    if not cell.numeric:
                        text_reason: list[str] = []
                        if not unrestricted_raw:
                            text_reason.append("cell OCR returned no text")
                        if unrestricted_confidence is None:
                            text_reason.append("cell OCR returned no confidence score")
                        elif unrestricted_confidence < minimum_confidence:
                            text_reason.append(
                                f"cell OCR confidence {unrestricted_confidence:.2f} is below "
                                f"{minimum_confidence:.2f}")
                        if any(char in unrestricted_raw for char in "|!"):
                            text_reason.append("table separator/uncertain glyph remains in text cell")
                        if (source_assessment is not None
                                and unrestricted_raw != source_assessment.raw_value):
                            text_reason.append(
                                "cell OCR differs from the full-page raw field; manual review required")
                        if source_status == "REVIEW":
                            text_reason.append(
                                "full-page spatial assessment remains REVIEW; cell OCR is supplementary")
                        results.append(CellOCRVariantResult(
                            field_name=cell.field_name,
                            preprocessing="none",
                            bbox=cell.bbox,
                            raw_value=unrestricted_raw,
                            confidence=unrestricted_confidence,
                            status="REVIEW" if text_reason else "EXTRACTED",
                            reason="; ".join(dict.fromkeys(text_reason)) or None,
                            unrestricted_raw_value=unrestricted_raw,
                            line_pixels_removed=0,
                            psm=7,
                            whitelist=None,
                        ))
                        continue

                    for mode in PREPROCESSING_MODES:
                        processed = preprocess_cell(cell.image, mode)
                        prepared = _prepare_cell_for_tesseract(
                            processed.image,
                            scale_factor=scale_factor,
                            white_padding=white_padding,
                        )
                        _clear_cell_adaptation(numeric_api)
                        numeric_api.SetImage(prepared)
                        raw_value = _cell_text(numeric_api)
                        confidence = _cell_confidence(numeric_api)
                        reason = _numeric_cell_review_reason(
                            raw_value,
                            unrestricted_raw_value=unrestricted_raw,
                            confidence=confidence,
                            minimum_confidence=float(minimum_confidence),
                            source_status=source_status,
                        )
                        results.append(CellOCRVariantResult(
                            field_name=cell.field_name,
                            preprocessing=mode,
                            bbox=cell.bbox,
                            raw_value=raw_value,
                            confidence=confidence,
                            status="REVIEW" if reason else "EXTRACTED",
                            reason=reason,
                            unrestricted_raw_value=unrestricted_raw,
                            line_pixels_removed=processed.line_pixels_removed,
                            psm=7,
                            whitelist=NUMERIC_TESSERACT_WHITELIST,
                        ))
        except (OCRExecutionError, OCREngineUnavailable):
            raise
        except Exception as exc:
            raise OCRExecutionError(
                f"Tesseract failed to process spatial cells in {image.name}: {exc}") from exc
        return tuple(results)
