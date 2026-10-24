"""Image OCR/spatial extraction adapter; the frozen pipeline remains authoritative."""
from __future__ import annotations

import hashlib
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping, Optional, Protocol, Sequence

from .model import (
    CellOCRVariantResult,
    ImageAdapterOutcome,
    ImageExtractionBlocked,
    ImageExtractionReady,
    ImageExtractionReviewRequired,
    ImageIssuanceSubmission,
    OCRResult,
)
from .ocr import OCRBackend, OCREngineUnavailable, OCRExecutionError
from .parser import InvoiceTextParseError, parse_invoice_geometry, parse_invoice_text


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


class SpatialCellOCRBackend(Protocol):
    def recognize_spatial_cells(
        self,
        image_path: Path,
        spatial: object,
        *,
        minimum_confidence: float,
    ) -> Sequence[CellOCRVariantResult]:
        """Recognize numeric cells using geometry from the full-page OCR pass."""
        ...


_NUMERIC_FIELD = re.compile(r"^line\.\d+\.(?:quantity|total)$")
_DIGIT_AND_SEPARATOR_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٬٫",
    "01234567890123456789,.",
)
_PERSIAN_RIAL_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹",
    "0123456789",
)


def to_rials(value: Optional[str]) -> Optional[int]:
    """Convert Persian digits and comma-grouped integer Rials to ``int``.

    Values containing anything other than Persian/ASCII digits and grouping
    commas are uncertain and return ``None`` rather than being guessed.
    """
    if not isinstance(value, str) or not value:
        return None
    normalized = value.translate(_PERSIAN_RIAL_DIGIT_TRANSLATION).replace(",", "")
    if not normalized or not normalized.isascii() or not normalized.isdigit():
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


class ImageExtractionAdapter:
    """OCR one raster invoice, parse text labels, and optionally call submit.

    The caller must explicitly set the minimum word-confidence threshold. A
    low-confidence, empty-confidence, ambiguous parse, or uncertain numeric
    cell returns an adapter-local `ImageExtractionReviewRequired` and DOES NOT
    call the issuance service. ``numeric_authority`` defaults to
    ``"tesseract_parse"`` for the existing behavior. In explicit ``"glyph"``
    mode, ``numeric_ocr_backend`` is authoritative for numeric fields and the
    full-page backend supplies text/layout context; disagreements produce REVIEW
    rather than BLOCKED.

    This is a fail-closed review hold, not a new Digital Invoice state or a
    persisted P5.2 ReviewQueue record; the frozen contracts have no
    OCR-confidence field. Any `PipelineStopped` result from the existing
    service is returned verbatim.
    """

    def __init__(
        self,
        ocr_backend: OCRBackend,
        *,
        minimum_word_confidence: float,
        numeric_ocr_backend: Optional[SpatialCellOCRBackend] = None,
        numeric_authority: str = "tesseract_parse",
    ):
        if (isinstance(minimum_word_confidence, bool)
                or not isinstance(minimum_word_confidence, (int, float))
                or not math.isfinite(float(minimum_word_confidence))
                or not 0 <= float(minimum_word_confidence) <= 100):
            raise ValueError("minimum_word_confidence must be explicitly set from 0 to 100")
        if numeric_authority not in ("tesseract_parse", "glyph"):
            raise ValueError("numeric_authority must be 'tesseract_parse' or 'glyph'")
        self._ocr = ocr_backend
        self._numeric_ocr = numeric_ocr_backend
        self._numeric_authority = numeric_authority
        self._minimum_word_confidence = float(minimum_word_confidence)

    @property
    def numeric_authority(self) -> str:
        """Configured authority for parsed numeric fields."""
        return self._numeric_authority

    def _recognize_numeric_cells(
        self,
        image: Path,
        spatial: object,
        *,
        fallback_to_full_page_backend: bool,
    ) -> tuple[tuple[CellOCRVariantResult, ...], Optional[str]]:
        backend = self._numeric_ocr
        if backend is None and fallback_to_full_page_backend:
            backend = self._ocr  # backwards-compatible supplementary path
        method = getattr(backend, "recognize_spatial_cells", None)
        if not callable(method):
            return (), None
        try:
            variants = tuple(method(
                image,
                spatial,
                minimum_confidence=self._minimum_word_confidence,
            ))
        except Exception as exc:
            return (), f"numeric cell OCR failed: {exc}"
        return variants, None

    @staticmethod
    def _numeric_value(value: str) -> Optional[Decimal]:
        if not isinstance(value, str):
            return None
        normalized = value.translate(_DIGIT_AND_SEPARATOR_TRANSLATION).replace(",", "")
        try:
            parsed = Decimal(normalized)
        except (InvalidOperation, ValueError):
            return None
        return parsed if parsed.is_finite() else None

    @classmethod
    def _canonical_numeric_value(cls, value: str) -> Optional[str]:
        rials = to_rials(value)
        if rials is not None:
            return str(rials)
        parsed = cls._numeric_value(value)
        return format(parsed, "f") if parsed is not None else None

    def _numeric_backend_review(
        self,
        digest: str,
        ocr: OCRResult,
        fields: tuple[tuple[str, str], ...],
        *,
        spatial: object,
        variants: Sequence[CellOCRVariantResult],
        reason: str,
    ) -> ImageExtractionReviewRequired:
        return ImageExtractionReviewRequired(
            source_image_sha256=digest,
            ocr=ocr,
            reason=reason,
            field_values=fields,
            field_assessments=tuple(getattr(spatial, "assessments", ())),
            spatial_column_boundaries=tuple(
                getattr(spatial, "column_boundaries", ())),
            spatial_row_bands=tuple(getattr(spatial, "row_bands", ())),
            cell_ocr_variants=tuple(variants),
        )

    def _numeric_evidence_problem(
        self,
        fields: tuple[tuple[str, str], ...],
        variants: Sequence[CellOCRVariantResult],
    ) -> Optional[str]:
        if not variants:
            return "primary numeric OCR returned no numeric cells"
        reviewed = [item for item in variants if item.status != "EXTRACTED"]
        if reviewed:
            details = "; ".join(
                f"{item.field_name}: {item.reason or item.status}"
                for item in reviewed)
            return f"primary numeric OCR requires page review: {details}"

        expected = {
            field: value for field, value in fields
            if field == "invoice.payable" or _NUMERIC_FIELD.fullmatch(field)
        }
        observed = {item.field_name: item.raw_value for item in variants}
        duplicates = len(observed) != len(variants)
        missing = sorted(set(expected) - set(observed))
        unexpected = sorted(set(observed) - set(expected))
        mismatched = []
        for field in sorted(set(expected) & set(observed)):
            expected_value = self._numeric_value(expected[field])
            observed_value = self._numeric_value(observed[field])
            if (expected_value is None or observed_value is None
                    or expected_value != observed_value):
                mismatched.append(field)
        if duplicates or missing or unexpected or mismatched:
            problems = []
            if duplicates:
                problems.append("duplicate numeric OCR field results")
            if missing:
                problems.append("missing numeric OCR fields: " + ", ".join(missing))
            if unexpected:
                problems.append("unexpected numeric OCR fields: " + ", ".join(unexpected))
            if mismatched:
                problems.append("numeric OCR disagrees with parsed values: "
                                + ", ".join(mismatched))
            return "primary numeric OCR coverage/consistency failed: " + "; ".join(problems)
        return None

    @staticmethod
    def _is_numeric_authority_field(field: str) -> bool:
        return field == "invoice.payable" or bool(_NUMERIC_FIELD.fullmatch(field))

    def _glyph_authority_problem(
        self,
        fields: tuple[tuple[str, str], ...],
        variants: Sequence[CellOCRVariantResult],
    ) -> Optional[tuple[str, str]]:
        """Assess glyph results without allowing Tesseract to veto authority.

        A present, non-empty Tesseract value is compared as evidence. Missing
        or empty Tesseract numeric values do not invalidate extracted glyph
        values. Glyph REVIEW/BLOCKED statuses, incomplete coverage, and invalid
        glyph values remain fail-closed.
        """
        if not variants:
            return "REVIEW", "glyph_authority_returned_no_numeric_cells"

        blocked = [item for item in variants if item.status == "BLOCKED"]
        if blocked:
            details = "; ".join(
                f"{item.field_name}: {item.reason or item.status}" for item in blocked)
            return "BLOCKED", f"glyph_authority_blocked: {details}"

        reviewed = [item for item in variants if item.status != "EXTRACTED"]
        if reviewed:
            details = "; ".join(
                f"{item.field_name}: {item.reason or item.status}" for item in reviewed)
            return "REVIEW", f"glyph_authority_requires_review: {details}"

        numeric_field_names = [
            field for field, _ in fields if self._is_numeric_authority_field(field)
        ]
        if len(set(numeric_field_names)) != len(numeric_field_names):
            return "REVIEW", "glyph_authority_input_has_duplicate_numeric_fields"

        observed = {item.field_name: item for item in variants}
        if len(observed) != len(variants):
            return "REVIEW", "glyph_authority_returned_duplicate_numeric_fields"

        unexpected = sorted(
            field for field in observed if not self._is_numeric_authority_field(field)
        )
        if unexpected:
            return "REVIEW", (
                "glyph_authority_returned_non_numeric_fields: " + ", ".join(unexpected))

        expected = {
            field: value for field, value in fields
            if self._is_numeric_authority_field(field)
        }
        missing = sorted(set(expected) - set(observed))
        if missing:
            return "REVIEW", "glyph_authority_missing_numeric_fields: " + ", ".join(missing)

        for item in variants:
            if self._numeric_value(item.raw_value) is None:
                return "REVIEW", f"glyph_authority_invalid_numeric_value: {item.field_name}"

        for field, tesseract_value in expected.items():
            if not isinstance(tesseract_value, str) or not tesseract_value.strip():
                continue
            glyph_value = observed[field].raw_value
            if self._numeric_value(tesseract_value) != self._numeric_value(glyph_value):
                return "REVIEW", "tesseract_disagreement_with_glyph_authority"
        return None

    @classmethod
    def _fields_with_glyph_numeric_authority(
        cls,
        fields: tuple[tuple[str, str], ...],
        variants: Sequence[CellOCRVariantResult],
    ) -> tuple[tuple[str, str], ...]:
        """Overlay canonical glyph values while preserving nonnumeric fields."""
        output = list(fields)
        positions = {field: index for index, (field, _) in enumerate(output)}
        for item in variants:
            value = cls._canonical_numeric_value(item.raw_value)
            if value is None:
                continue
            if item.field_name in positions:
                output[positions[item.field_name]] = (item.field_name, value)
            else:
                positions[item.field_name] = len(output)
                output.append((item.field_name, value))
        return tuple(output)

    @staticmethod
    def _key_value_page(fields: tuple[tuple[str, str], ...]) -> bytes:
        return "".join(f"{name}={value}\n" for name, value in fields).encode("utf-8")

    def _primary_numeric_review(
        self,
        image: Path,
        digest: str,
        ocr: OCRResult,
        fields: tuple[tuple[str, str], ...],
    ) -> tuple[Optional[ImageExtractionReviewRequired | ImageExtractionBlocked],
               tuple[CellOCRVariantResult, ...]]:
        if self._numeric_ocr is None:
            if self._numeric_authority == "glyph":
                spatial = parse_invoice_geometry(
                    ocr, minimum_confidence=self._minimum_word_confidence)
                return self._numeric_backend_review(
                    digest, ocr, fields, spatial=spatial, variants=(),
                    reason="glyph_authority_backend_not_configured"), ()
            return None, ()
        spatial = parse_invoice_geometry(
            ocr, minimum_confidence=self._minimum_word_confidence)
        variants, backend_error = self._recognize_numeric_cells(
            image, spatial, fallback_to_full_page_backend=False)
        if backend_error:
            reason = (
                f"glyph_authority_backend_failed: {backend_error}"
                if self._numeric_authority == "glyph"
                else f"primary numeric OCR failed; full page held: {backend_error}"
            )
            return self._numeric_backend_review(
                digest, ocr, fields, spatial=spatial, variants=variants,
                reason=reason), variants

        if self._numeric_authority == "glyph":
            authority_problem = self._glyph_authority_problem(fields, variants)
            if authority_problem is None:
                return None, variants
            status, reason = authority_problem
            if status == "BLOCKED":
                return ImageExtractionBlocked(digest, reason), variants
            return self._numeric_backend_review(
                digest, ocr, fields, spatial=spatial, variants=variants,
                reason=reason), variants

        problem = self._numeric_evidence_problem(fields, variants)
        if problem:
            return self._numeric_backend_review(
                digest, ocr, fields, spatial=spatial, variants=variants,
                reason=problem + "; full page held"), variants
        return None, variants

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
            spatial = parse_invoice_geometry(
                ocr, minimum_confidence=self._minimum_word_confidence)
            spatial_summary = "; ".join(spatial.reasons) or "spatial fields need review"
            base_reason = (
                f"flat-text parser blocked: {exc}; spatial parser: {spatial_summary}")
            cell_ocr_variants, cell_ocr_error = self._recognize_numeric_cells(
                image, spatial, fallback_to_full_page_backend=True)
            reasons = [base_reason]
            if cell_ocr_error:
                reasons.append(cell_ocr_error)
            reviewed = [item for item in cell_ocr_variants
                        if item.status != "EXTRACTED"]
            if reviewed:
                reasons.append(
                    "numeric OCR REVIEW cell(s): "
                    + ", ".join(item.field_name for item in reviewed))
            if cell_ocr_variants or cell_ocr_error or spatial.assessments:
                return ImageExtractionReviewRequired(
                    source_image_sha256=digest,
                    ocr=ocr,
                    reason="; ".join(reasons),
                    field_values=spatial.field_values,
                    field_assessments=spatial.assessments,
                    spatial_column_boundaries=spatial.column_boundaries,
                    spatial_row_bands=spatial.row_bands,
                    cell_ocr_variants=cell_ocr_variants,
                )
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

        numeric_review, numeric_ocr_variants = self._primary_numeric_review(
            image, digest, ocr, parsed.fields)
        if numeric_review is not None:
            return numeric_review

        field_values = parsed.fields
        key_value_page = parsed.key_value_page
        if self._numeric_authority == "glyph":
            field_values = self._fields_with_glyph_numeric_authority(
                parsed.fields, numeric_ocr_variants)
            key_value_page = self._key_value_page(field_values)

        return ImageExtractionReady(
            source_image_sha256=digest,
            ocr=ocr,
            field_values=field_values,
            key_value_page=key_value_page,
            numeric_ocr_variants=numeric_ocr_variants,
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
        return self.submit_extraction(
            extraction,
            issuance_service,
            source_label=source_label,
            declared_origin=declared_origin,
            identity_binding=identity_binding,
            line_binding=line_binding,
            ruleset_id=ruleset_id,
            ruleset_version=ruleset_version,
        )

    def submit_extraction(
        self,
        extraction: ImageExtractionReady,
        issuance_service: IssuanceSubmitter,
        *,
        source_label: str,
        declared_origin: str,
        identity_binding: Mapping[str, str],
        line_binding: Optional[Mapping[int, Mapping[str, str]]],
        ruleset_id: str,
        ruleset_version: str,
    ) -> ImageAdapterOutcome:
        """Submit a previously reviewed ready result without running OCR again."""
        if not isinstance(extraction, ImageExtractionReady):
            raise TypeError("only a high-confidence ImageExtractionReady can be submitted")
        ocr = extraction.ocr
        if any(
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
            or not 0 <= float(score) <= 100
            for score in ocr.word_confidences
        ):
            raise ValueError("ready extraction has invalid OCR confidence values")
        minimum = ocr.minimum_confidence
        if minimum is None or minimum < self._minimum_word_confidence:
            raise ValueError("ready extraction is below the declared confidence threshold")
        parsed = parse_invoice_text(ocr.text)
        expected_fields = parsed.fields
        expected_page = parsed.key_value_page
        if self._numeric_authority == "glyph":
            authority_problem = self._glyph_authority_problem(
                parsed.fields, extraction.numeric_ocr_variants)
            if authority_problem is not None:
                status, reason = authority_problem
                if status == "BLOCKED":
                    return ImageExtractionBlocked(
                        extraction.source_image_sha256, reason)
                return ImageExtractionReviewRequired(
                    source_image_sha256=extraction.source_image_sha256,
                    ocr=ocr,
                    reason=reason + "; submit blocked",
                    field_values=parsed.fields,
                    cell_ocr_variants=extraction.numeric_ocr_variants,
                )
            expected_fields = self._fields_with_glyph_numeric_authority(
                parsed.fields, extraction.numeric_ocr_variants)
            expected_page = self._key_value_page(expected_fields)
        if (expected_fields != extraction.field_values
                or expected_page != extraction.key_value_page):
            raise ValueError("ready extraction fields do not match its OCR transcript")
        if (self._numeric_authority == "tesseract_parse"
                and self._numeric_ocr is not None):
            numeric_problem = self._numeric_evidence_problem(
                parsed.fields, extraction.numeric_ocr_variants)
            if numeric_problem:
                return ImageExtractionReviewRequired(
                    source_image_sha256=extraction.source_image_sha256,
                    ocr=ocr,
                    reason=numeric_problem + "; submit blocked",
                    field_values=parsed.fields,
                    cell_ocr_variants=extraction.numeric_ocr_variants,
                )
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
