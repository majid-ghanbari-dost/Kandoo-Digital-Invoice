from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from image_extraction_adapter import (
    ImageExtractionAdapter,
    ImageExtractionReviewRequired,
    ImageIssuanceSubmission,
    OCRResult,
    parse_invoice_text,
)


OCR_TEXT = """SYNTHETIC INVOICE - OCR TEST ONLY
INVOICE NO: SYNTH-IMG-001
DATE: 2026-10-14
ITEM | QUANTITY | UNIT PRICE | LINE TOTAL
Synthetic Widget | 2 | 500.00 | 1000.00
NET TOTAL: 1000.00
TAX: 80.00
AMOUNT DUE: 1080.00
"""
EXPECTED_FIELDS = (
    ("invoice.number", "SYNTH-IMG-001"),
    ("invoice.date", "2026-10-14"),
    ("total.net", "1000.00"),
    ("tax.amount", "80.00"),
    ("invoice.payable", "1080.00"),
    ("line.0.description", "Synthetic Widget"),
    ("line.0.quantity", "2"),
    ("line.0.unit_price", "500.00"),
    ("line.0.total", "1000.00"),
)
DECLARATION = {
    "source_label": "synthetic-image-adapter-test",
    "declared_origin": "HOLOO_CAPTURE",
    "identity_binding": {
        "INVOICE_NUMBER": "invoice.number",
        "INVOICE_DATE": "invoice.date",
        "INVOICE_TOTAL": "invoice.payable",
    },
    "line_binding": {
        0: {
            "LINE_QUANTITY": "line.0.quantity",
            "LINE_UNIT_PRICE": "line.0.unit_price",
            "LINE_TOTAL": "line.0.total",
        }
    },
    "ruleset_id": "synthetic-image-test-declared",
    "ruleset_version": "1",
}


class FakeOCR:
    def __init__(self, *, confidences=(90.0, 95.0), text=OCR_TEXT):
        self.result = OCRResult("fake-test-backend", "eng", text, tuple(confidences))

    def recognize(self, image_path):
        return self.result


class RecordingService:
    def __init__(self):
        self.calls = []

    def submit(self, pages, **kwargs):
        result = object()
        self.calls.append((pages, kwargs, result))
        return result


class ImageExtractionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="image-adapter-test-")
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "synthetic.png"
        self.image.write_bytes(b"synthetic test image bytes")

    def test_parser_maps_labeled_table_without_coordinates(self):
        parsed = parse_invoice_text(OCR_TEXT)
        self.assertEqual(parsed.fields, EXPECTED_FIELDS)
        self.assertEqual(parsed.line_count, 1)
        self.assertIn(b"line.0.quantity=2\n", parsed.key_value_page)
        self.assertIn(b"invoice.payable=1080.00\n", parsed.key_value_page)

    def test_high_confidence_image_calls_existing_submit_with_key_value_page(self):
        service = RecordingService()
        adapter = ImageExtractionAdapter(
            FakeOCR(confidences=(91.0, 96.0)), minimum_word_confidence=80.0)

        result = adapter.submit_image(
            self.image, service, **DECLARATION)

        self.assertIsInstance(result, ImageIssuanceSubmission)
        self.assertEqual(result.extraction.field_values, EXPECTED_FIELDS)
        self.assertEqual(len(service.calls), 1)
        pages, kwargs, submitted_result = service.calls[0]
        self.assertEqual(pages, [result.extraction.key_value_page])
        self.assertEqual(kwargs, DECLARATION)
        self.assertIs(result.submission, submitted_result)

    def test_low_confidence_is_review_hold_and_never_submits(self):
        service = RecordingService()
        adapter = ImageExtractionAdapter(
            FakeOCR(confidences=(48.0, 93.0)), minimum_word_confidence=80.0)

        result = adapter.submit_image(
            self.image, service, **DECLARATION)

        self.assertIsInstance(result, ImageExtractionReviewRequired)
        self.assertIn("below the declared threshold", result.reason)
        self.assertEqual(result.field_values, EXPECTED_FIELDS)
        self.assertEqual(service.calls, [])

    def test_missing_word_confidences_are_review_not_success(self):
        service = RecordingService()
        adapter = ImageExtractionAdapter(
            FakeOCR(confidences=()), minimum_word_confidence=80.0)

        result = adapter.submit_image(
            self.image, service, **DECLARATION)

        self.assertIsInstance(result, ImageExtractionReviewRequired)
        self.assertIn("no word confidence", result.reason)
        self.assertEqual(service.calls, [])

    def test_invalid_confidence_values_are_review_not_success(self):
        service = RecordingService()
        adapter = ImageExtractionAdapter(
            FakeOCR(confidences=(float("nan"), 95.0)),
            minimum_word_confidence=80.0,
        )

        result = adapter.submit_image(
            self.image, service, **DECLARATION)

        self.assertIsInstance(result, ImageExtractionReviewRequired)
        self.assertIn("invalid word confidence", result.reason)
        self.assertEqual(service.calls, [])

    def test_ambiguous_parse_is_review_not_success(self):
        ambiguous = OCR_TEXT.replace(
            "INVOICE NO: SYNTH-IMG-001",
            "INVOICE NO: SYNTH-IMG-001\nINVOICE NO: SYNTH-IMG-002")
        service = RecordingService()
        adapter = ImageExtractionAdapter(
            FakeOCR(confidences=(95.0,), text=ambiguous),
            minimum_word_confidence=80.0,
        )

        result = adapter.submit_image(
            self.image, service, **DECLARATION)

        self.assertIsInstance(result, ImageExtractionReviewRequired)
        self.assertIn("exactly one invoice number", result.reason)
        self.assertEqual(service.calls, [])


if __name__ == "__main__":
    unittest.main()
