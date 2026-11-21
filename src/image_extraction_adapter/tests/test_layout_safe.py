from __future__ import annotations

import random
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from image_extraction_adapter.preprocessing import (
    DynamicTableLayout,
    LayoutSafetyResult,
    detect_dynamic_table_layout,
    detect_layout_safe,
)


ROOT = Path(__file__).resolve().parents[3]
REAL_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "real"
REAL_ROW_COUNTS = {"29": 4, "31": 3, "32": 5, "33": 13}


class _CorruptImage:
    """Image-like input that simulates a decode/conversion failure."""

    def convert(self, _mode: str):
        raise OSError("corrupt image data")


class DetectLayoutSafeTests(unittest.TestCase):
    def test_all_real_invoices_return_ok_with_labeled_row_counts(self) -> None:
        for invoice_id, expected_rows in REAL_ROW_COUNTS.items():
            with self.subTest(invoice=invoice_id):
                path = REAL_FIXTURE_DIR / f"{invoice_id}.png"
                self.assertTrue(path.is_file(), f"missing real fixture: {path}")
                with Image.open(path) as image:
                    image.load()
                    result = detect_layout_safe(image)

                self.assertIsInstance(result, LayoutSafetyResult)
                self.assertEqual(result.status, "OK")
                self.assertEqual(result.row_count, expected_rows)
                self.assertIsInstance(result.geometry, DynamicTableLayout)
                self.assertTrue(result.reason)

    def test_blank_image_is_classified_without_raising(self) -> None:
        image = Image.new("RGB", (800, 600), "white")

        result = detect_layout_safe(image)

        self.assertIn(result.status, {"BLOCKED", "REVIEW"})
        self.assertIsNotNone(result.reason)
        if result.status == "BLOCKED":
            self.assertIsNone(result.geometry)
            self.assertIsNone(result.row_count)

    def test_text_only_image_is_review_or_blocked(self) -> None:
        image = Image.new("RGB", (800, 600), "white")
        draw = ImageDraw.Draw(image)
        rng = random.Random(2505)
        for _ in range(24):
            x = rng.randint(8, 700)
            y = rng.randint(8, 565)
            draw.text((x, y), f"text-{rng.randrange(10000)}", fill="black")

        result = detect_layout_safe(image)

        self.assertIn(result.status, {"BLOCKED", "REVIEW"})
        self.assertIsNotNone(result.reason)
        if result.status == "BLOCKED":
            self.assertIsNone(result.geometry)
            self.assertIsNone(result.row_count)

    def test_tiny_truncated_image_is_blocked(self) -> None:
        image = Image.new("RGB", (10, 10), "white")

        result = detect_layout_safe(image)

        self.assertEqual(result.status, "BLOCKED")
        self.assertIsNone(result.geometry)
        self.assertIsNone(result.row_count)
        self.assertIn("No table geometry", result.reason)

    def test_partial_geometry_touching_edge_is_blocked_as_truncated(self) -> None:
        path = REAL_FIXTURE_DIR / "33.png"
        with Image.open(path) as source:
            source.load()
            partial_image = source.crop((0, 0, source.width, int(source.height * 0.60)))

        existing_result = detect_dynamic_table_layout(partial_image)
        self.assertIsNotNone(existing_result)
        self.assertEqual(len(existing_result.row_bands), 7)

        result = detect_layout_safe(partial_image)

        self.assertEqual(result.status, "BLOCKED")
        self.assertIsNone(result.geometry)
        self.assertIsNone(result.row_count)
        self.assertIn("image edge", result.reason)

    def test_detector_exception_from_corrupt_image_is_blocked(self) -> None:
        result = detect_layout_safe(_CorruptImage())

        self.assertEqual(result.status, "BLOCKED")
        self.assertIsNone(result.geometry)
        self.assertIsNone(result.row_count)
        self.assertIn("OSError", result.reason)
        self.assertIn("corrupt image data", result.reason)

    def test_incomplete_geometry_is_review_and_preserved(self) -> None:
        with Image.open(REAL_FIXTURE_DIR / "29.png") as image:
            image.load()
            geometry = detect_dynamic_table_layout(image)
        self.assertIsNotNone(geometry)
        partial_geometry = replace(geometry, vertical_lines=geometry.vertical_lines[:-1])

        with patch(
            "image_extraction_adapter.preprocessing.detect_dynamic_table_layout",
            return_value=partial_geometry,
        ):
            result = detect_layout_safe(Image.new("RGB", (576, 1296), "white"))

        self.assertEqual(result.status, "REVIEW")
        self.assertIs(result.geometry, partial_geometry)
        self.assertEqual(result.row_count, 4)
        self.assertIn("vertical_lines", result.reason)

    def test_zero_rows_are_review_and_preserved(self) -> None:
        with Image.open(REAL_FIXTURE_DIR / "29.png") as image:
            image.load()
            geometry = detect_dynamic_table_layout(image)
        self.assertIsNotNone(geometry)
        empty_geometry = replace(geometry, row_bands=())

        with patch(
            "image_extraction_adapter.preprocessing.detect_dynamic_table_layout",
            return_value=empty_geometry,
        ):
            result = detect_layout_safe(Image.new("RGB", (576, 1296), "white"))

        self.assertEqual(result.status, "REVIEW")
        self.assertIs(result.geometry, empty_geometry)
        self.assertEqual(result.row_count, 0)
        self.assertIn("row_bands", result.reason)

    def test_unreasonable_row_count_is_review(self) -> None:
        with Image.open(REAL_FIXTURE_DIR / "29.png") as image:
            image.load()
            geometry = detect_dynamic_table_layout(image)
        self.assertIsNotNone(geometry)
        many_rows = tuple((float(index * 2), float(index * 2 + 1)) for index in range(51))
        unreasonable_geometry = replace(geometry, row_bands=many_rows)

        with patch(
            "image_extraction_adapter.preprocessing.detect_dynamic_table_layout",
            return_value=unreasonable_geometry,
        ):
            result = detect_layout_safe(Image.new("RGB", (576, 1296), "white"))

        self.assertEqual(result.status, "REVIEW")
        self.assertIs(result.geometry, unreasonable_geometry)
        self.assertEqual(result.row_count, 51)
        self.assertIn("1..50", result.reason)


if __name__ == "__main__":
    unittest.main()
