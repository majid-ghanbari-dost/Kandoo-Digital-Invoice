from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from image_extraction_adapter import (
    ImageExtractionAdapter,
    ImageExtractionReady,
    ImageExtractionReviewRequired,
    ImageIssuanceSubmission,
    OCRResult,
    OCRWord,
    PERSIAN_TESSERACT_LANGUAGE,
    parse_invoice_geometry,
    parse_invoice_text,
)
from image_extraction_adapter.ocr import _parse_tsv_words


OCR_TEXT = """SYNTHETIC INVOICE - OCR TEST ONLY
INVOICE NO: SYNTH-IMG-001
DATE: 2026-10-14
ITEM | QUANTITY | UNIT PRICE | LINE TOTAL
Synthetic Widget | 2 | 500.00 | 1000.00
NET TOTAL: 1000.00
TAX: 80.00
AMOUNT DUE: 1080.00
"""
PERSIAN_OCR_TEXT = """فاکتور مصنوعی
SYNTHETIC TEST ONLY
INVOICE NO: 1001
DATE: 2026-10-14
شرح کالا: ساندویچ کالباس
تعداد: ۲
قیمت واحد: 500.00
جمع ردیف: 1000.00
شرح کالا: دستمال سفره تم
تعداد: 1
قیمت واحد: 300.00
جمع ردیف: 300.00
NET TOTAL: 1,300.00
104.00 \u200fمالیات:\u200e
مبلغ قابل پرداخت: 1,404.00
"""
EXPECTED_PERSIAN_FIELDS = (
    ("invoice.number", "1001"),
    ("invoice.date", "2026-10-14"),
    ("total.net", "1300.00"),
    ("tax.amount", "104.00"),
    ("invoice.payable", "1404.00"),
    ("line.0.description", "ساندویچ کالباس"),
    ("line.0.quantity", "2"),
    ("line.0.unit_price", "500.00"),
    ("line.0.total", "1000.00"),
    ("line.1.description", "دستمال سفره تم"),
    ("line.1.quantity", "1"),
    ("line.1.unit_price", "300.00"),
    ("line.1.total", "300.00"),
)
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


def spatial_words_fixture():
    words = []

    def add(text, left, top, width, height=20, confidence=95.0):
        words.append(OCRWord(text, left, top, width, height, confidence))

    # Long whitespace TSV components mark the receipt's outer and inner rules.
    add(" ", 100, 0, 5, 1000)
    add(" ", 220, 300, 5, 200)
    add(" ", 280, 300, 5, 200)
    add(" ", 450, 300, 5, 200)
    add(" ", 500, 0, 5, 1000)

    add("1405.06.18", 300, 40, 100, confidence=95.0)
    add("شماره", 500, 90, 60)
    add("فاکتور", 430, 90, 60)
    add("۷۹", 380, 90, 25, confidence=90.0)

    add("3", 470, 320, 10, confidence=76.0)  # header, not item row one
    add("۱", 470, 390, 10, confidence=95.0)
    add("ریسه", 350, 390, 40, confidence=90.0)
    add("تم", 320, 390, 20, confidence=91.0)
    add("۱", 250, 390, 12, confidence=95.0)
    add("۴۵۰و", 140, 390, 70, confidence=0.0)

    add("۲", 470, 450, 10, confidence=95.0)
    add("چنگال", 350, 450, 50, confidence=92.0)
    add("تم", 320, 450, 20, confidence=92.0)
    add("۱", 250, 450, 12, confidence=95.0)
    add("۵۷۰,۰۰", 140, 450, 72, confidence=90.0)

    add("مبلغ", 470, 600, 50)
    add("قابل", 420, 600, 40)
    add("پرداخت:", 340, 600, 70)
    add("۰۰۰و ۷,۴۶۰", 180, 600, 120, confidence=0.0)
    add("مالیات", 470, 650, 50)
    add("بر", 430, 650, 20)
    add("ارزش", 390, 650, 35)
    add("افزوده", 330, 650, 50)
    add("۰", 200, 650, 8, height=8, confidence=90.0)
    return tuple(words)


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
    def __init__(
        self, *, confidences=(90.0, 95.0), text=OCR_TEXT, language="eng",
        words=(), image_size=(0, 0),
    ):
        self.result = OCRResult(
            "fake-test-backend", language, text, tuple(confidences), tuple(words),
            image_size[0], image_size[1],
        )

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

    def test_persian_parser_normalizes_digits_and_bidi_controls_to_utf8(self):
        parsed = parse_invoice_text(PERSIAN_OCR_TEXT)

        self.assertEqual(parsed.fields, EXPECTED_PERSIAN_FIELDS)
        self.assertEqual(parsed.line_count, 2)
        page = parsed.key_value_page.decode("utf-8")
        self.assertIn("line.0.description=ساندویچ کالباس\n", page)
        self.assertIn("line.0.quantity=2\n", page)
        self.assertIn("line.1.description=دستمال سفره تم\n", page)
        self.assertNotRegex(page, r"[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]")
        self.assertEqual(PERSIAN_TESSERACT_LANGUAGE, "fas+eng")

        localized_numbers = (
            PERSIAN_OCR_TEXT.replace("تعداد: 1", "تعداد: ۱")
            .replace("500.00", "۵۰۰٫۰۰")
            .replace("1000.00", "۱٬۰۰۰٫۰۰")
            .replace("300.00", "۳۰۰٫۰۰")
            .replace("1,300.00", "۱٬۳۰۰٫۰۰")
            .replace("104.00", "۱۰۴٫۰۰")
            .replace("1,404.00", "۱٬۴۰۴٫۰۰")
        )
        self.assertEqual(parse_invoice_text(localized_numbers).fields, EXPECTED_PERSIAN_FIELDS)

    def test_tesseract_tsv_reader_retains_word_boxes_and_whitespace_rules(self):
        tsv = (
            "5\t1\t2\t1\t1\t1\t10\t20\t30\t40\t80.5\t۱۲\n"
            "5\t1\t3\t1\t2\t1\t50\t20\t5\t200\t95\t \n"
        )

        words = _parse_tsv_words(tsv)

        self.assertEqual(len(words), 2)
        self.assertEqual(words[0].text, "۱۲")
        self.assertEqual((words[0].left, words[0].top, words[0].width, words[0].height),
                         (10, 20, 30, 40))
        self.assertEqual(words[0].confidence, 80.5)
        self.assertEqual(words[1].text, " ")
        self.assertEqual(words[1].height, 200)

    def test_geometry_parser_groups_right_to_left_cells_and_preserves_uncertain_raw(self):
        ocr = OCRResult(
            "fake-test-backend", "fas+eng", "", (),
            words=spatial_words_fixture(), image_width=600, image_height=1000,
        )

        parsed = parse_invoice_geometry(ocr, minimum_confidence=60.0)
        fields = {item.field_name: item for item in parsed.assessments}

        self.assertEqual(len(parsed.column_boundaries), 5)
        self.assertEqual(len(parsed.row_bands), 2)
        self.assertEqual(fields["line.0.description"].raw_value, "ریسه تم")
        self.assertEqual(fields["line.0.description"].status, "EXTRACTED")
        self.assertEqual(fields["line.0.quantity"].raw_value, "۱")
        self.assertEqual(fields["line.0.quantity"].status, "EXTRACTED")
        self.assertEqual(fields["line.0.total"].raw_value, "۴۵۰و")
        self.assertEqual(fields["line.0.total"].status, "REVIEW")
        self.assertEqual(fields["line.1.description"].raw_value, "چنگال تم")
        self.assertEqual(fields["line.1.total"].raw_value, "۵۷۰,۰۰")
        self.assertEqual(fields["line.1.total"].status, "REVIEW")
        self.assertEqual(fields["invoice.date"].raw_value, "1405.06.18")
        self.assertEqual(fields["invoice.date"].status, "REVIEW")

    def test_adapter_spatial_fallback_holds_and_never_submits(self):
        service = RecordingService()
        adapter = ImageExtractionAdapter(
            FakeOCR(
                confidences=(90.0, 95.0),
                text="INVOICE NO: 79\n11:28 1405.06.18",
                language=PERSIAN_TESSERACT_LANGUAGE,
                words=spatial_words_fixture(),
                image_size=(600, 1000),
            ),
            minimum_word_confidence=60.0,
        )

        result = adapter.submit_image(self.image, service, **DECLARATION)

        self.assertIsInstance(result, ImageExtractionReviewRequired)
        self.assertIn("expected exactly one invoice date", result.reason)
        fields = {item.field_name: item for item in result.field_assessments}
        self.assertEqual(fields["line.0.total"].raw_value, "۴۵۰و")
        self.assertEqual(fields["line.0.total"].status, "REVIEW")
        self.assertEqual(service.calls, [])

    def test_high_confidence_persian_ocr_submits_utf8_fields(self):
        service = RecordingService()
        adapter = ImageExtractionAdapter(
            FakeOCR(confidences=(91.0, 96.0), text=PERSIAN_OCR_TEXT,
                    language=PERSIAN_TESSERACT_LANGUAGE),
            minimum_word_confidence=80.0,
        )

        result = adapter.submit_image(self.image, service, **DECLARATION)

        self.assertIsInstance(result, ImageIssuanceSubmission)
        self.assertEqual(result.extraction.field_values, EXPECTED_PERSIAN_FIELDS)
        pages, _, _ = service.calls[0]
        self.assertIn("ساندویچ کالباس".encode("utf-8"), pages[0])
        self.assertIn(b"invoice.payable=1404.00\n", pages[0])

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

    def test_submit_extraction_rejects_low_confidence_ready_result(self):
        parsed = parse_invoice_text(OCR_TEXT)
        extraction = ImageExtractionReady(
            source_image_sha256="0" * 64,
            ocr=FakeOCR(confidences=(48.0, 93.0)).result,
            field_values=parsed.fields,
            key_value_page=parsed.key_value_page,
        )
        service = RecordingService()
        adapter = ImageExtractionAdapter(
            FakeOCR(confidences=(90.0,)), minimum_word_confidence=80.0)

        with self.assertRaisesRegex(ValueError, "below the declared confidence threshold"):
            adapter.submit_extraction(extraction, service, **DECLARATION)

        self.assertEqual(service.calls, [])

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
