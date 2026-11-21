from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from image_extraction_adapter.adapter import ImageExtractionAdapter, to_rials
from image_extraction_adapter.model import (
    CellOCRVariantResult,
    ImageExtractionBlocked,
    ImageExtractionReady,
    ImageExtractionReviewRequired,
    ImageIssuanceSubmission,
    OCRResult,
)
from image_extraction_adapter.parser import ParsedImageInvoice, parse_invoice_text


OCR_TEXT = """SYNTHETIC INVOICE - OCR TEST ONLY
INVOICE NO: SYNTH-IMG-001
DATE: 2026-10-14
ITEM | QUANTITY | UNIT PRICE | LINE TOTAL
Synthetic Widget | 2 | 500.00 | 1000.00
NET TOTAL: 1000.00
TAX: 80.00
AMOUNT DUE: 1080.00
"""
DECLARATION = {
    "source_label": "numeric-authority-test",
    "declared_origin": "HOLOO_CAPTURE",
    "identity_binding": {"INVOICE_NUMBER": "invoice.number"},
    "line_binding": None,
    "ruleset_id": "numeric-authority-test",
    "ruleset_version": "1",
}


def _variant(field_name: str, value: str, *, status: str = "EXTRACTED"):
    return CellOCRVariantResult(
        field_name=field_name,
        preprocessing="glyph",
        bbox=(1, 2, 12, 14),
        raw_value=value,
        confidence=98.0,
        status=status,
        reason=None if status == "EXTRACTED" else f"glyph result is {status}",
    )


def _glyph_results(
    *,
    payable: str = "۱۰۸۰",
    quantity: str = "۲",
    line_total: str = "۱۰۰۰",
):
    return (
        _variant("invoice.payable", payable),
        _variant("line.0.quantity", quantity),
        _variant("line.0.total", line_total),
    )


class FakeTesseract:
    def __init__(self, *, text: str = OCR_TEXT):
        self.result = OCRResult(
            engine="fake-tesseract",
            language="eng",
            text=text,
            word_confidences=(95.0, 96.0),
        )

    def recognize(self, _image_path: Path) -> OCRResult:
        return self.result


class FakeGlyph:
    def __init__(self, results):
        self.results = tuple(results)
        self.calls = 0

    def recognize_spatial_cells(self, _image_path, _spatial, *, minimum_confidence):
        self.calls += 1
        self.minimum_confidence = minimum_confidence
        return self.results


class RecordingSubmitter:
    def __init__(self):
        self.calls = []

    def submit(self, pages, **kwargs):
        result = object()
        self.calls.append((pages, kwargs, result))
        return result


class NumericAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="numeric-authority-test-")
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "synthetic.png"
        self.image.write_bytes(b"synthetic test bytes; no OCR runtime used")

    def _adapter(self, *, authority="tesseract_parse", glyph=None):
        return ImageExtractionAdapter(
            FakeTesseract(),
            minimum_word_confidence=80.0,
            numeric_ocr_backend=glyph,
            numeric_authority=authority,
        )

    def test_default_flag_value_is_tesseract_parse(self):
        self.assertEqual(
            inspect.signature(ImageExtractionAdapter).parameters[
                "numeric_authority"].default,
            "tesseract_parse",
        )
        self.assertEqual(self._adapter().numeric_authority, "tesseract_parse")

    def test_tesseract_parse_mode_preserves_existing_behavior(self):
        baseline = self._adapter().extract(self.image)
        self.assertIsInstance(baseline, ImageExtractionReady)

        glyph = FakeGlyph(_glyph_results(line_total="۹۹۹"))
        result = self._adapter(glyph=glyph).extract(self.image)

        self.assertIsInstance(result, ImageExtractionReviewRequired)
        self.assertIn("numeric OCR disagrees with parsed values: line.0.total", result.reason)
        self.assertNotEqual(result.reason, "tesseract_disagreement_with_glyph_authority")

    def test_glyph_mode_agreement_with_tesseract_is_extracted(self):
        glyph = FakeGlyph(_glyph_results())
        adapter = self._adapter(authority="glyph", glyph=glyph)

        extraction = adapter.extract(self.image)

        self.assertIsInstance(extraction, ImageExtractionReady)
        self.assertEqual(glyph.calls, 1)
        self.assertEqual(dict(extraction.field_values)["invoice.payable"], "1080")
        self.assertEqual(dict(extraction.field_values)["line.0.total"], "1000")
        self.assertIn(b"invoice.payable=1080\n", extraction.key_value_page)

        submitter = RecordingSubmitter()
        submission = adapter.submit_extraction(extraction, submitter, **DECLARATION)
        self.assertIsInstance(submission, ImageIssuanceSubmission)
        self.assertEqual(len(submitter.calls), 1)

    def test_glyph_mode_disagreement_with_tesseract_is_review(self):
        glyph = FakeGlyph(_glyph_results(line_total="۹۹۹"))

        result = self._adapter(authority="glyph", glyph=glyph).extract(self.image)

        self.assertIsInstance(result, ImageExtractionReviewRequired)
        self.assertEqual(result.reason, "tesseract_disagreement_with_glyph_authority")

    def test_glyph_mode_tesseract_missing_is_extracted(self):
        parsed = parse_invoice_text(OCR_TEXT)
        variants = _glyph_results()
        payable_missing = tuple(
            (field, value) for field, value in parsed.fields
            if field != "invoice.payable")
        payable_empty = tuple(
            (field, "" if field == "invoice.payable" else value)
            for field, value in parsed.fields)

        for name, fields in (("missing", payable_missing), ("empty", payable_empty)):
            with self.subTest(tesseract_payable=name):
                stub_parse = ParsedImageInvoice(
                    fields=fields,
                    key_value_page="".join(
                        f"{field}={value}\n" for field, value in fields).encode("utf-8"),
                    line_count=parsed.line_count,
                )
                glyph = FakeGlyph(variants)
                adapter = self._adapter(authority="glyph", glyph=glyph)
                submitter = RecordingSubmitter()
                with patch(
                    "image_extraction_adapter.adapter.parse_invoice_text",
                    return_value=stub_parse,
                ):
                    result = adapter.submit_image(
                        self.image, submitter, **DECLARATION)

                self.assertIsInstance(result, ImageIssuanceSubmission)
                self.assertEqual(
                    dict(result.extraction.field_values)["invoice.payable"], "1080")
                self.assertEqual(len(submitter.calls), 1)

    def test_glyph_mode_glyph_review_stays_review(self):
        variants = (
            _variant("invoice.payable", "۱۰۸۰", status="REVIEW"),
            *_glyph_results()[1:],
        )

        result = self._adapter(
            authority="glyph", glyph=FakeGlyph(variants)).extract(self.image)

        self.assertIsInstance(result, ImageExtractionReviewRequired)
        self.assertIn("glyph_authority_requires_review", result.reason)
        self.assertNotEqual(result.reason, "tesseract_disagreement_with_glyph_authority")

    def test_glyph_mode_glyph_blocked_stays_blocked(self):
        variants = (
            _variant("invoice.payable", "۱۰۸۰", status="BLOCKED"),
            *_glyph_results()[1:],
        )

        result = self._adapter(
            authority="glyph", glyph=FakeGlyph(variants)).extract(self.image)

        self.assertIsInstance(result, ImageExtractionBlocked)
        self.assertIn("glyph_authority_blocked", result.reason)

    def test_to_rials_converts_persian_digits_and_commas(self):
        self.assertEqual(to_rials("۲,۴۲۵,۰۰۰"), 2425000)

    def test_to_rials_handles_none_and_empty(self):
        self.assertIsNone(to_rials(None))
        self.assertIsNone(to_rials(""))

    def test_to_rials_handles_invalid_input(self):
        for value in ("۲۴x", "۲۴۲۵.۰۰", " ۲۴۲۵", ",,,"):
            with self.subTest(value=value):
                self.assertIsNone(to_rials(value))


if __name__ == "__main__":
    unittest.main()
