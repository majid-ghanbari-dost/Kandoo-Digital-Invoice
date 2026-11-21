from __future__ import annotations

import json
import random
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from image_extraction_adapter.preprocessing import (
    DynamicTableLayout,
    detect_dynamic_table_layout,
)


ROOT = Path(__file__).resolve().parents[1]
REAL_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "real"
LABELS_PATH = REAL_FIXTURE_DIR / "labels.json"
EXPECTED_BOUNDARIES = (116.0, 244.0, 293.0, 487.0, 527.0)
REAL_EXPECTATIONS = {
    "29": ((576, 1296), 4),
    "31": ((576, 1224), 3),
    "32": ((576, 1368), 5),
    "33": ((576, 1680), 13),
}


class RealProjectionLayoutTests(unittest.TestCase):
    """Real and negative-input checks for the existing Pillow projection detector."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
        cls.labels_by_id = {
            str(entry["id"]): entry for entry in cls.labels["invoices"]
        }
        cls.temp_dir = Path("/tmp")
        cls.blank_path = cls.temp_dir / "t4-blank.png"
        cls.no_table_path = cls.temp_dir / "t4-no-table.png"
        cls.truncated_path = cls.temp_dir / "t4-truncated.png"
        cls._make_blank_image()
        cls._make_no_table_image()
        cls._make_truncated_image()

    @classmethod
    def _make_blank_image(cls) -> None:
        image = Image.new("L", (576, 1296), 255)
        image.save(cls.blank_path)

    @classmethod
    def _make_no_table_image(cls) -> None:
        """Make scattered, small dark marks without shared rules or a grid."""
        image = Image.new("L", (576, 1296), 255)
        draw = ImageDraw.Draw(image)
        rng = random.Random(1405)
        for _ in range(110):
            anchor_x = rng.randint(20, 540)
            anchor_y = rng.randint(30, 1260)
            for _ in range(rng.randint(2, 5)):
                width = rng.randint(2, 12)
                height = rng.randint(2, 9)
                x = max(2, min(573, anchor_x + rng.randint(-15, 15)))
                y = max(2, min(1293, anchor_y + rng.randint(-9, 9)))
                draw.rectangle(
                    (x, y, min(574, x + width), min(1294, y + height)),
                    fill=0,
                )
        image.save(cls.no_table_path)

    @classmethod
    def _make_truncated_image(cls) -> None:
        source_path = REAL_FIXTURE_DIR / "33.png"
        with Image.open(source_path) as source:
            source.load()
            # Keep the top 60% and discard the bottom 40%, including the final
            # five-ish item rows and all payable/footer content.
            cut_height = int(source.height * 0.60)
            source.crop((0, 0, source.width, cut_height)).save(cls.truncated_path)

    def _assert_real_invoice(self, invoice_id: str) -> DynamicTableLayout:
        expected_size, expected_rows = REAL_EXPECTATIONS[invoice_id]
        image_path = REAL_FIXTURE_DIR / f"{invoice_id}.png"
        self.assertTrue(image_path.is_file(), f"missing real fixture: {image_path}")
        with Image.open(image_path) as image:
            image.load()
            self.assertEqual(image.size, expected_size)
            layout = detect_dynamic_table_layout(image)
        self.assertIsInstance(layout, DynamicTableLayout)
        self.assertEqual(len(layout.row_bands), expected_rows)
        self.assertEqual(layout.column_boundaries, EXPECTED_BOUNDARIES)
        self.assertEqual(
            len(layout.row_bands),
            int(self.labels_by_id[invoice_id]["row_count"]),
        )
        return layout

    def test_real_29_has_4_rows(self) -> None:
        self._assert_real_invoice("29")

    def test_real_31_has_3_rows(self) -> None:
        self._assert_real_invoice("31")

    def test_real_32_has_5_rows(self) -> None:
        self._assert_real_invoice("32")

    def test_real_33_has_13_rows(self) -> None:
        self._assert_real_invoice("33")

    def test_blank_image_no_exception(self) -> None:
        with Image.open(self.blank_path) as image:
            image.load()
            layout = detect_dynamic_table_layout(image)
        # The projection API returns no geometry rather than raising. It does
        # not itself attach a REVIEW/Blocked state; the caller must fail closed.
        self.assertIsNone(layout)

    def test_no_table_image_no_exception(self) -> None:
        with Image.open(self.no_table_path) as image:
            image.load()
            layout = detect_dynamic_table_layout(image)
        self.assertIsNone(layout)

    def test_truncated_image_no_exception(self) -> None:
        with Image.open(self.truncated_path) as image:
            image.load()
            self.assertEqual(image.size, (576, 1008))
            layout = detect_dynamic_table_layout(image)
        # The detector returns only a partial seven-row geometry. It has no
        # invoice-completeness or state field; callers must hold this known
        # truncated input for review and must not treat the partial rows as ready.
        self.assertIsInstance(layout, DynamicTableLayout)
        self.assertEqual(len(layout.row_bands), 7)
        self.assertLess(len(layout.row_bands), REAL_EXPECTATIONS["33"][1])
        self.assertFalse(hasattr(layout, "payable_bbox"))

    def test_payable_box_excluded_from_rows(self) -> None:
        for invoice_id, entry in self.labels_by_id.items():
            with self.subTest(invoice=invoice_id):
                image_path = REAL_FIXTURE_DIR / f"{invoice_id}.png"
                with Image.open(image_path) as image:
                    image.load()
                    layout = detect_dynamic_table_layout(image)
                self.assertIsNotNone(layout)
                payable_left, payable_top, payable_width, payable_height = entry[
                    "payable_bbox"
                ]
                payable_bottom = payable_top + payable_height
                for row_top, row_bottom in layout.row_bands:
                    overlaps_payable = (
                        row_top < payable_bottom and row_bottom > payable_top
                    )
                    self.assertFalse(
                        overlaps_payable,
                        f"invoice #{invoice_id} row {(row_top, row_bottom)} "
                        f"overlaps payable bbox {entry['payable_bbox']}",
                    )
                self.assertLess(layout.row_bands[-1][1], payable_top)


if __name__ == "__main__":
    unittest.main()
