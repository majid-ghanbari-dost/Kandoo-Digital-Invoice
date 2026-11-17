"""Adapter-local OCR and review outcomes; no new frozen invoice states."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


@dataclass(frozen=True)
class OCRWord:
    """One Tesseract level-5 TSV item, including its image-space bounding box.

    Whitespace-only TSV items are retained because Tesseract may use them for
    long table rules; confidence aggregation still considers them as returned by
    the engine, matching its word-confidence API.
    """

    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float
    block_num: int = 0
    paragraph_num: int = 0
    line_num: int = 0
    word_num: int = 0

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def center_x(self) -> float:
        return self.left + self.width / 2

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2


@dataclass(frozen=True)
class FieldAssessment:
    """A raw adapter field plus a local EXTRACTED/REVIEW assessment."""

    field_name: str
    raw_value: str
    status: str
    confidence: Optional[float] = None
    bbox: Optional[tuple[int, int, int, int]] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class CellOCRVariantResult:
    """Non-canonical OCR evidence for one cropped cell/preprocessing variant."""

    field_name: str
    preprocessing: str
    bbox: tuple[int, int, int, int]
    raw_value: str
    confidence: Optional[float]
    status: str
    reason: Optional[str] = None
    unrestricted_raw_value: Optional[str] = None
    line_pixels_removed: int = 0
    psm: int = 7
    whitelist: Optional[str] = None


@dataclass(frozen=True)
class OCRResult:
    """Text, word-level confidence, and spatial boxes returned by an OCR backend."""
    engine: str
    language: str
    text: str
    word_confidences: tuple[float, ...]
    words: tuple[OCRWord, ...] = ()
    image_width: int = 0
    image_height: int = 0

    @property
    def mean_confidence(self) -> Optional[float]:
        if not self.word_confidences:
            return None
        return sum(self.word_confidences) / len(self.word_confidences)

    @property
    def minimum_confidence(self) -> Optional[float]:
        if not self.word_confidences:
            return None
        return min(self.word_confidences)


@dataclass(frozen=True)
class ImageExtractionReady:
    """OCR parsed with sufficient confidence; page is ready for existing API."""
    source_image_sha256: str
    ocr: OCRResult
    field_values: tuple[tuple[str, str], ...]
    key_value_page: bytes
    numeric_ocr_variants: tuple[CellOCRVariantResult, ...] = ()


@dataclass(frozen=True)
class ImageExtractionReviewRequired:
    """Fail-closed adapter hold: an operator should review; no submit occurred."""
    source_image_sha256: str
    ocr: OCRResult
    reason: str
    field_values: tuple[tuple[str, str], ...] = ()
    field_assessments: tuple[FieldAssessment, ...] = ()
    spatial_column_boundaries: tuple[float, ...] = ()
    spatial_row_bands: tuple[tuple[float, float], ...] = ()
    cell_ocr_variants: tuple[CellOCRVariantResult, ...] = ()


@dataclass(frozen=True)
class ImageExtractionBlocked:
    """OCR could not run (missing optional runtime/model or unreadable image)."""
    source_image_sha256: Optional[str]
    reason: str


@dataclass(frozen=True)
class ImageIssuanceSubmission:
    """Original IssuanceService result after a high-confidence image extraction."""
    extraction: ImageExtractionReady
    submission: object


ImageExtractionOutcome = Union[
    ImageExtractionReady,
    ImageExtractionReviewRequired,
    ImageExtractionBlocked,
]
ImageAdapterOutcome = Union[ImageExtractionOutcome, ImageIssuanceSubmission]
