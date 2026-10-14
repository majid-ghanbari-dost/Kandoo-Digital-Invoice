"""Adapter-local OCR and review outcomes; no new frozen invoice states."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


@dataclass(frozen=True)
class OCRResult:
    """Text and word-level confidence returned by an OCR backend."""
    engine: str
    language: str
    text: str
    word_confidences: tuple[float, ...]

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


@dataclass(frozen=True)
class ImageExtractionReviewRequired:
    """Fail-closed adapter hold: an operator should review; no submit occurred."""
    source_image_sha256: str
    ocr: OCRResult
    reason: str
    field_values: tuple[tuple[str, str], ...] = ()


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
