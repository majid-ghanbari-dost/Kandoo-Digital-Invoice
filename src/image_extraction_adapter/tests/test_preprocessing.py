from __future__ import annotations

import unittest
from types import SimpleNamespace

from image_extraction_adapter import (
    NUMERIC_TESSERACT_WHITELIST,
    adaptive_binarize,
    crop_spatial_cells,
    otsu_binarize,
    preprocess_cell,
    remove_morphological_table_lines,
)
from image_extraction_adapter.ocr import _numeric_cell_review_reason


try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - optional OCR runtime
    Image = None
    ImageDraw = None


@unittest.skipIf(Image is None, "optional Pillow runtime is not installed")
class CellPreprocessingTests(unittest.TestCase):
    def test_otsu_threshold_zero_keeps_black_foreground(self):
        image = Image.new("L", (20, 12), 255)
        ImageDraw.Draw(image).rectangle((5, 3, 7, 9), fill=0)

        result = otsu_binarize(image)

        self.assertEqual(result.getpixel((6, 5)), 0)
        self.assertEqual(result.getpixel((0, 0)), 255)

    def test_morphological_opening_removes_long_rules_not_small_glyph(self):
        image = Image.new("L", (120, 80), 255)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 5, 119, 7), fill=0)
        draw.rectangle((5, 0, 7, 79), fill=0)
        draw.rectangle((55, 30, 64, 48), fill=0)

        cleaned, removed = remove_morphological_table_lines(image)

        self.assertGreater(removed, 0)
        self.assertEqual(cleaned.getpixel((40, 6)), 255)
        self.assertEqual(cleaned.getpixel((6, 40)), 255)
        self.assertEqual(cleaned.getpixel((60, 39)), 0)

    def test_spatial_crop_uses_rtl_columns_and_preserves_source(self):
        source = Image.new("RGB", (100, 80), "white")
        ImageDraw.Draw(source).rectangle((10, 20, 29, 39), fill="black")
        original_pixel = source.getpixel((15, 25))
        spatial = SimpleNamespace(
            column_boundaries=(10, 30, 40, 80, 90),
            row_bands=((20, 40),),
            assessments=(SimpleNamespace(
                field_name="invoice.payable", bbox=(50, 50, 20, 10)),),
        )

        cells = crop_spatial_cells(source, spatial)
        by_name = {cell.field_name: cell for cell in cells}

        self.assertEqual(by_name["line.0.total"].bbox, (14, 28, 26, 37))
        self.assertEqual(by_name["line.0.quantity"].bbox, (34, 28, 36, 37))
        self.assertEqual(by_name["line.0.description"].bbox, (44, 28, 76, 37))
        self.assertEqual(by_name["line.0.total"].image.size, (12, 9))
        self.assertTrue(by_name["line.0.total"].numeric)
        self.assertFalse(by_name["line.0.description"].numeric)
        self.assertEqual(source.getpixel((15, 25)), original_pixel)
        self.assertEqual(
            by_name["invoice.payable"].bbox,
            (46, 46, 74, 64),
        )

    def test_all_modes_return_copies_and_keep_dimensions(self):
        source = Image.new("RGB", (80, 50), "white")
        ImageDraw.Draw(source).line((0, 2, 79, 2), fill="black", width=2)
        original = source.copy()

        outputs = [preprocess_cell(source, mode) for mode in ("none", "otsu", "adaptive")]

        self.assertEqual([item.mode for item in outputs], ["none", "otsu", "adaptive"])
        self.assertTrue(all(item.image.size == source.size for item in outputs))
        self.assertEqual(list(source.getdata()), list(original.getdata()))

    def test_numeric_review_rejects_pipe_bang_and_unrestricted_disagreement(self):
        self.assertIn(
            "pipe/exclamation",
            _numeric_cell_review_reason(
                "|", unrestricted_raw_value="|", confidence=95,
                minimum_confidence=60, source_status="REVIEW",
            ),
        )
        self.assertIn(
            "pipe/exclamation",
            _numeric_cell_review_reason(
                "۱", unrestricted_raw_value="!|", confidence=95,
                minimum_confidence=60, source_status="REVIEW",
            ),
        )
        self.assertIn(
            "does not match the declared numeric format",
            _numeric_cell_review_reason(
                "۴۵۰و", unrestricted_raw_value="۴۵۰و", confidence=95,
                minimum_confidence=60, source_status="REVIEW",
            ),
        )
        self.assertIsNone(
            _numeric_cell_review_reason(
                "۱,۴۵۰,۰۰۰", unrestricted_raw_value="1,450,000", confidence=95,
                minimum_confidence=60, source_status="EXTRACTED",
            ),
        )
        self.assertEqual(NUMERIC_TESSERACT_WHITELIST, "0123456789۰۱۲۳۴۵۶۷۸۹.,")


if __name__ == "__main__":
    unittest.main()
