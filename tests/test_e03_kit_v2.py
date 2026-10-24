from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_e03_kit_v2 import KIT_DIR, REQUIRED_GLYPHS, verify_kit  # noqa: E402


class E03KitV2Tests(unittest.TestCase):
    def test_pages_values_arithmetic_and_coverage_matrix_pass(self) -> None:
        counts = verify_kit()
        self.assertEqual(set(counts), set(REQUIRED_GLYPHS))
        self.assertEqual(
            counts,
            {
                "۰": 10,
                "۱": 14,
                "۲": 23,
                "۳": 9,
                "۴": 12,
                "۵": 11,
                "۶": 20,
                "۷": 6,
                "۸": 8,
                "۹": 7,
                ",": 20,
            },
        )
        self.assertTrue(all(count >= 5 for count in counts.values()))

    def test_answer_key_has_only_the_three_allowed_value_classes(self) -> None:
        data = json.loads((KIT_DIR / "expected-values.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"learning-1", "learning-2", "learning-3", "exam"})
        for page in data.values():
            self.assertEqual(set(page), {"quantities", "line_totals", "payable"})

    def test_learning_exam_page_files_are_exactly_three_plus_one(self) -> None:
        page_files = {
            path.name
            for path in KIT_DIR.glob("*.md")
            if path.name != "README.md"
        }
        self.assertEqual(
            page_files,
            {"learning-1.md", "learning-2.md", "learning-3.md", "exam.md"},
        )

    def test_page_tables_have_no_unit_price_column(self) -> None:
        for page_path in KIT_DIR.glob("*.md"):
            if page_path.name == "README.md":
                continue
            with self.subTest(page=page_path.name):
                content = page_path.read_text(encoding="utf-8").casefold()
                self.assertNotIn("unit price", content)
                self.assertNotIn("قیمت واحد", content)

    def test_stale_coverage_matrix_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e03-kit-v2-") as temporary:
            copied_kit = Path(temporary) / "kit"
            shutil.copytree(KIT_DIR, copied_kit)
            readme_path = copied_kit / "README.md"
            readme = readme_path.read_text(encoding="utf-8")
            readme = readme.replace("| `۰` | 10 | Yes |", "| `۰` | 9 | Yes |", 1)
            readme_path.write_text(readme, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "coverage matrix does not match"):
                verify_kit(copied_kit)


if __name__ == "__main__":
    unittest.main()
