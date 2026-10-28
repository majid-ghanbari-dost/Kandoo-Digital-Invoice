from __future__ import annotations

import unittest
from pathlib import Path

from scripts.run_n01_name_reading import (
    PROVISIONAL_REFERENCES,
    _levenshtein,
    _load_crops,
    _normalise_for_comparison,
)


ROOT = Path(__file__).resolve().parents[1]


class N01NameReadingTests(unittest.TestCase):
    def test_comparison_normalization_only_folds_persian_unicode_and_whitespace(self) -> None:
        self.assertEqual(
            _normalise_for_comparison(" كَتاب  ي "),
            "کَتاب ی",
        )
        self.assertEqual(
            _normalise_for_comparison("رد  پا"),
            "رد پا",
        )

    def test_levenshtein_counts_insertions_deletions_and_substitutions(self) -> None:
        self.assertEqual(_levenshtein("kitten", "sitting"), 3)
        self.assertEqual(_levenshtein("ردپا", "رد پا"), 1)
        self.assertEqual(_levenshtein("", "سه"), 2)

    def test_only_the_six_supplied_reference_crops_are_scored(self) -> None:
        self.assertEqual(len(PROVISIONAL_REFERENCES), 6)
        self.assertEqual(
            set(PROVISIONAL_REFERENCES),
            {
                "31_row0", "32_row0", "31_row1", "32_row3", "31_row2", "33_row1",
            },
        )

    def test_all_25_real_name_crops_use_the_validated_table_geometry(self) -> None:
        crops = _load_crops(ROOT)
        self.assertEqual(len(crops), 25)
        self.assertEqual(
            [crop.crop_id for crop in crops],
            [
                *(f"29_row{row}" for row in range(4)),
                *(f"31_row{row}" for row in range(3)),
                *(f"32_row{row}" for row in range(5)),
                *(f"33_row{row}" for row in range(13)),
            ],
        )
        first_known = next(crop for crop in crops if crop.crop_id == "31_row0")
        self.assertEqual(first_known.bbox, (297, 533, 483, 593))
        self.assertEqual(first_known.unprocessed.size, (186, 60))
        self.assertEqual(first_known.otsu_binarized.size, (186, 60))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
