from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_n02_product_candidates import (  # noqa: E402
    CandidateOccurrence,
    ProductCandidate,
    aggregate_candidate_occurrences,
    build_product_candidates,
    collect_candidate_occurrences,
    serialize_document,
)

SCHEMA_PATH = ROOT / "schemas" / "product_candidate_prototype_v1.json"
GOLDEN_PATH = ROOT / "tests" / "fixtures" / "real" / "canonical" / "product-candidates.golden.json"


class N02ProductCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    def test_output_matches_schema_and_committed_golden(self) -> None:
        output = build_product_candidates(ROOT, write_reference_crops=False)
        self.validator.validate(output)
        expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(output, expected)
        self.assertEqual(serialize_document(output), GOLDEN_PATH.read_text(encoding="utf-8"))
        cluster_ids = [item["name_crop_cluster_id"] for item in output["candidates"]]
        self.assertEqual(len(cluster_ids), len(set(cluster_ids)))

    def test_same_inputs_produce_byte_identical_output(self) -> None:
        first = serialize_document(
            build_product_candidates(ROOT, write_reference_crops=False))
        second = serialize_document(
            build_product_candidates(ROOT, write_reference_crops=False))
        self.assertEqual(first, second)

    def test_expected_repeated_crop_groups_aggregate_once(self) -> None:
        output = build_product_candidates(ROOT, write_reference_crops=False)
        candidates = output["candidates"]
        self.assertEqual(len(candidates), 22)
        self.assertEqual(sum(item["occurrence_count"] for item in candidates), 25)
        self.assertEqual(sum(item["quantity_sum"] for item in candidates), 87)

        expected_groups = (
            ({"31_row0", "32_row0"}, 2, {"e05-synth-invoice-31", "e05-synth-invoice-32"}),
            ({"31_row1", "32_row3"}, 2, {"e05-synth-invoice-31", "e05-synth-invoice-32"}),
            ({"31_row2", "33_row1"}, 11, {"e05-synth-invoice-31", "e05-synth-invoice-33"}),
        )
        for crop_ids, quantity_sum, invoice_ids in expected_groups:
            with self.subTest(crop_ids=sorted(crop_ids)):
                matching = [
                    item for item in candidates
                    if crop_ids.issubset(set(item["source_crop_ids"]))
                ]
                self.assertEqual(len(matching), 1)
                candidate = matching[0]
                self.assertEqual(candidate["source_crop_ids"], sorted(crop_ids))
                self.assertEqual(candidate["occurrence_count"], 2)
                self.assertEqual(candidate["quantity_sum"], quantity_sum)
                self.assertEqual(set(candidate["invoice_ids"]), invoice_ids)
                self.assertEqual(candidate["reference_crop_file"].rsplit("/", 1)[-1],
                                 f"{sorted(crop_ids)[0]}.png")

    def test_no_names_categories_or_inferred_price_dates_are_emitted(self) -> None:
        output = build_product_candidates(ROOT, write_reference_crops=False)
        serialized = serialize_document(output)
        self.assertNotIn("product_name", serialized)
        self.assertNotIn("Example product", serialized)
        self.assertNotIn("category", serialized)
        self.assertNotIn("دستمال", serialized)
        self.assertNotIn("رد پا", serialized)
        self.assertNotIn("خلال", serialized)
        self.assertEqual(output["price_observation_date_source"], "header.printed_date")
        self.assertTrue(all(not item["price_observations"] for item in output["candidates"]))

    def test_reference_crop_files_exist_and_are_readable(self) -> None:
        output = build_product_candidates(ROOT, write_reference_crops=False)
        self.assertEqual(len(output["candidates"]), 22)
        for candidate in output["candidates"]:
            path = ROOT / candidate["reference_crop_file"]
            with self.subTest(path=str(path)):
                self.assertTrue(path.is_file())
                with Image.open(path) as crop:
                    self.assertGreater(crop.width, 0)
                    self.assertGreater(crop.height, 0)

    def test_adding_an_invoice_updates_one_candidate_and_keeps_date(self) -> None:
        occurrences, _ = collect_candidate_occurrences(ROOT)
        before = aggregate_candidate_occurrences(occurrences)
        self.assertTrue(all(isinstance(item, ProductCandidate) for item in before))
        target_before = next(
            item for item in before if "31_row0" in item.source_crop_ids)
        added = CandidateOccurrence(
            name_crop_cluster_id=target_before.name_crop_cluster_id,
            source_crop_id="34_row0",
            reference_crop_file=target_before.reference_crop_file,
            invoice_id="e05-synth-invoice-34",
            quantity=4,
            unit_price_rials=123456,
            printed_date="2099-12-31",  # Synthetic sentinel for the date serialization path.
        )

        after = aggregate_candidate_occurrences([*occurrences, added])
        self.assertEqual(len(after), len(before))
        target_after = next(
            item for item in after if "31_row0" in item.source_crop_ids)
        self.assertEqual(target_after.occurrence_count, 3)
        self.assertEqual(target_after.quantity_sum, 6)
        self.assertEqual(
            target_after.invoice_ids,
            ("e05-synth-invoice-31", "e05-synth-invoice-32", "e05-synth-invoice-34"),
        )
        self.assertEqual(
            target_after.source_crop_ids, ("31_row0", "32_row0", "34_row0"))
        self.assertEqual(target_after.reference_crop_file, target_before.reference_crop_file)
        self.assertEqual([item.to_dict() for item in target_after.price_observations], [{
            "observed_on": "2099-12-31",
            "unit_price_rials": 123456,
            "invoice_id": "e05-synth-invoice-34",
            "source_crop_id": "34_row0",
        }])

    def test_duplicate_source_crop_is_rejected(self) -> None:
        occurrences, _ = collect_candidate_occurrences(ROOT)
        with self.assertRaisesRegex(ValueError, "duplicate source crop"):
            aggregate_candidate_occurrences([*occurrences, occurrences[0]])


if __name__ == "__main__":
    unittest.main()
