from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_e03_kit_v3 import (  # noqa: E402
    KIT_DIR,
    REQUIRED_GLYPHS,
    verify_kit,
)


class E03KitV3Tests(unittest.TestCase):
    def test_pages_arithmetic_and_coverage_matrix_pass(self) -> None:
        counts = verify_kit()
        self.assertEqual(set(counts), set(REQUIRED_GLYPHS))
        self.assertEqual(
            counts,
            {
                "۰": 13,
                "۱": 17,
                "۲": 32,
                "۳": 7,
                "۴": 10,
                "۵": 14,
                "۶": 25,
                "۷": 8,
                "۸": 8,
                "۹": 6,
                ",": 25,
            },
        )
        self.assertEqual(verify_kit.last_arithmetic_rows, 16)
        self.assertTrue(all(count >= 5 for count in counts.values()))

    def test_ground_truth_has_only_quantity_line_total_and_payable(self) -> None:
        data = json.loads((KIT_DIR / "expected-values.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"learning-1", "learning-2", "learning-3", "exam"})
        for page in data.values():
            self.assertEqual(set(page), {"quantities", "line_totals", "payable"})

    def test_wrong_entry_only_price_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e03-kit-v3-arithmetic-") as temporary:
            copied_kit = Path(temporary) / "kit"
            shutil.copytree(KIT_DIR, copied_kit)
            page = copied_kit / "learning-1.md"
            text = page.read_text(encoding="utf-8")
            self.assertIn("۶,۳۱۳,۱۳۱", text)
            page.write_text(text.replace("۶,۳۱۳,۱۳۱", "۶,۳۱۳,۱۳۲", 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "quantity .* unit price"):
                verify_kit(copied_kit)

    def test_write_coverage_regenerates_a_stale_matrix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e03-kit-v3-coverage-") as temporary:
            copied_kit = Path(temporary) / "kit"
            shutil.copytree(KIT_DIR, copied_kit)
            readme_path = copied_kit / "README.md"
            readme = readme_path.read_text(encoding="utf-8")
            self.assertIn("| 0 | `۰` | 13 | Yes |", readme)
            readme_path.write_text(
                readme.replace("| 0 | `۰` | 13 | Yes |", "| 0 | `۰` | 12 | Yes |", 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "coverage matrix is stale"):
                verify_kit(copied_kit)

            counts = verify_kit(copied_kit, write_coverage=True)
            regenerated = readme_path.read_text(encoding="utf-8")

        self.assertEqual(counts["۰"], 13)
        self.assertIn("| 0 | `۰` | 13 | Yes |", regenerated)


if __name__ == "__main__":
    unittest.main()
