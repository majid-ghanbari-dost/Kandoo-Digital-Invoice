"""Image-to-text ingestion adapter; the frozen pipeline remains authoritative."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Mapping, Optional, Protocol, Sequence

from .model import (
    ImageAdapterOutcome,
    ImageExtractionBlocked,
    ImageExtractionReady,
    ImageExtractionReviewRequired,
    ImageIssuanceSubmission,
    OCRResult,
)
from .ocr import OCRBackend, OCREngineUnavailable, OCRExecutionError
from .parser import InvoiceTextParseError, parse_invoice_text


class IssuanceSubmitter(Protocol):
    def submit(
        self,
        pages: Sequence[bytes],
        *,
        source_label: str,
        declared_origin: str,
        identity_binding: Mapping[str, str],
        line_binding: Optional[Mapping[int, Mapping[str, str]]],
        ruleset_id: str,
        ruleset_version: str,
    ) -> object:
        ...


class ImageExtractionAdapter:
    """OCR one raster invoice, parse text labels, and optionally call submit.

    The caller must explicitly set the minimum word-confidence threshold. A
    low-confidence, empty-confidence, or ambiguous parse returns an adapter-local
    `ImageExtractionReviewRequired` and DOES NOT call the issuance service. This
    is a fail-closed review hold, not a new Digital Invoice state or a persisted
    P5.2 ReviewQueue record; the frozen contracts have no OCR-confidence field.
    Any `PipelineStopped` result from the existing service is returned verbatim.
    """

    def __init__(self, ocr_backend: OCRBackend, *, minimum_word_confidence: float):
        if (isinstance(minimum_word_confidence, bool)
                or not isinstance(minimum_word_confidence, (int, float))
                or not math.isfinite(float(minimum_word_confidence))
                or not 0 <= float(minimum_word_confidence) <= 100):
            raise ValueError("minimum_word_confidence must be explicitly set from 0 to 100")
        self._ocr = ocr_backend
        self._minimum_word_confidence = float(minimum_word_confidence)

    def extract(self, image_path: Path) -> ImageExtractionReady | ImageExtractionReviewRequired | ImageExtractionBlocked:
        image = Path(image_path)
        if not image.is_file():
            return ImageExtractionBlocked(None, f"image file is missing: {image}")
        try:
            digest = self._sha256_file(image)
        except OSError as exc:
            return ImageExtractionBlocked(None, f"image cannot be read: {exc}")

        try:
            ocr = self._ocr.recognize(image)
        except (OCREngineUnavailable, OCRExecutionError) as exc:
            return ImageExtractionBlocked(digest, str(exc))

        try:
            parsed = parse_invoice_text(ocr.text)
        except InvoiceTextParseError as exc:
            return ImageExtractionReviewRequired(
                source_image_sha256=digest,
                ocr=ocr,
                reason=f"OCR text is incomplete/ambiguous: {exc}",
            )

        if any(
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
            or not 0 <= float(score) <= 100
            for score in ocr.word_confidences
        ):
            return ImageExtractionReviewRequired(
                source_image_sha256=digest,
                ocr=ocr,
                reason="OCR returned invalid word confidence values; confidence is unverified",
                field_values=parsed.fields,
            )

        minimum = ocr.minimum_confidence
        if minimum is None:
            return ImageExtractionReviewRequired(
                source_image_sha256=digest,
                ocr=ocr,
                reason="OCR returned no word confidence scores; confidence is unverified",
                field_values=parsed.fields,
            )
        if minimum < self._minimum_word_confidence:
            return ImageExtractionReviewRequired(
                source_image_sha256=digest,
                ocr=ocr,
                reason=(f"minimum word confidence {minimum:.2f} is below the "
                        f"declared threshold {self._minimum_word_confidence:.2f}"),
                field_values=parsed.fields,
            )

        return ImageExtractionReady(
            source_image_sha256=digest,
            ocr=ocr,
            field_values=parsed.fields,
            key_value_page=parsed.key_value_page,
        )

    def submit_image(
        self,
        image_path: Path,
        issuance_service: IssuanceSubmitter,
        *,
        source_label: str,
        declared_origin: str,
        identity_binding: Mapping[str, str],
        line_binding: Optional[Mapping[int, Mapping[str, str]]],
        ruleset_id: str,
        ruleset_version: str,
    ) -> ImageAdapterOutcome:
        """Submit only high-confidence parsed UTF-8 text to the existing API.

        The Capture artifact is the deterministic OCR transcript page, not the
        source image. The image SHA-256 is returned for caller-side correlation;
        adding an image pointer to the frozen Capture contract is out of scope.
        """
        extraction = self.extract(image_path)
        if not isinstance(extraction, ImageExtractionReady):
            return extraction
        submission = issuance_service.submit(
            [extraction.key_value_page],
            source_label=source_label,
            declared_origin=declared_origin,
            identity_binding=identity_binding,
            line_binding=line_binding,
            ruleset_id=ruleset_id,
            ruleset_version=ruleset_version,
        )
        return ImageIssuanceSubmission(extraction, submission)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
