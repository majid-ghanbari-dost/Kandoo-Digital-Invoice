from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from image_extraction_adapter import (
    DynamicTableLayout,
    NUMERIC_TESSERACT_WHITELIST,
    adaptive_binarize,
    crop_spatial_cells,
    detect_dynamic_table_layout,
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
    @staticmethod
    def _projection_table(row_count):
        width, header_top, header_bottom, row_height = 360, 50, 70, 28
        table_bottom = header_bottom + row_count * row_height
        image = Image.new("L", (width, table_bottom + 90), 255)
        draw = ImageDraw.Draw(image)
        rules = (20, 120, 160, 300, 340)
        draw.line((20, header_top, 340, header_top), fill=0, width=2)
        draw.line((20, header_bottom, 340, header_bottom), fill=0, width=2)
        for row in range(1, row_count + 1):
            y = header_bottom + row * row_height
            draw.line((20, y, 340, y), fill=0, width=2)
        for x in rules:
            draw.line((x, header_top, x, table_bottom), fill=0, width=2)
        # Rounded payable-box edges are long enough to pass the 80% projection
        # cutoff but are too close/far from the table median row pitch.
        draw.line((45, table_bottom + 7, 315, table_bottom + 7), fill=0, width=2)
        draw.line((45, table_bottom + 68, 315, table_bottom + 68), fill=0, width=2)
        return image

    def test_projection_detects_four_five_and_thirteen_rows_without_fixed_coords(self):
        for row_count in (4, 5, 13):
            with self.subTest(row_count=row_count):
                image = self._projection_table(row_count)
                layout = detect_dynamic_table_layout(image)
                self.assertIsInstance(layout, DynamicTableLayout)
                self.assertEqual(len(layout.row_bands), row_count)
                self.assertEqual(len(layout.column_boundaries), 5)
                self.assertEqual(layout.median_row_height, 28)
                self.assertTrue(layout.header_row_excluded)
                self.assertLess(layout.row_bands[-1][1], image.height - 80)

    def test_real_holoo_images_have_dynamic_row_and_column_geometry(self):
        root = Path(__file__).resolve().parents[3]
        image_root = root / "deliveries" / "image-extraction-ocr"
        expected = {"holo_row_detection.png": 4, "5.png": 5, "13.png": 13}
        for name, row_count in expected.items():
            with self.subTest(image=name):
                path = image_root / name
                self.assertTrue(path.is_file(), f"missing supplied image: {path}")
                with Image.open(path) as opened:
                    opened.load()
                    layout = detect_dynamic_table_layout(opened)
                    crops = crop_spatial_cells(
                        opened, SimpleNamespace(assessments=()),
                        include_payable=False,
                    )
                self.assertIsNotNone(layout)
                self.assertEqual(len(layout.row_bands), row_count)
                self.assertEqual(len(layout.column_boundaries), 5)
                self.assertEqual(len(crops), row_count * 3)

    def test_crop_uses_projection_before_spatial_fallback(self):
        source = self._projection_table(4)
        spatial = SimpleNamespace(column_boundaries=(0, 1, 2, 3, 4), row_bands=())

        cells = crop_spatial_cells(
            source, spatial, include_descriptions=False, include_payable=False)

        self.assertEqual(len(cells), 8)
        self.assertEqual(cells[0].field_name, "line.0.total")
        self.assertEqual(cells[-1].field_name, "line.3.quantity")
        self.assertGreater(cells[0].bbox[2] - cells[0].bbox[0], 90)

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
