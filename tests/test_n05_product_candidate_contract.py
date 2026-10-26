from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_n05_candidate_goldens import (  # noqa: E402
    N05_SCHEMA_VERSION,
    build_n05_candidate_examples,
)
from n04_name_suggestions import serialize_document  # noqa: E402

SCHEMA_PATH = ROOT / "schemas" / "n05" / "product_candidate_v1.schema.json"
GOLDEN_DIR = ROOT / "tests" / "fixtures" / "real" / "n05-goldens"
FIXTURE_IDS = ("29", "31", "32", "33")


def _validate_example_relationships(example: dict) -> None:
    candidate = example["candidate"]
    source_crop_ids = set(candidate["source_crop_ids"])
    invoice_ids = set(candidate["invoice_ids"])
    for suggestion in candidate["name_suggestions"]:
        crop_reference = suggestion["crop_reference"]
        if crop_reference["file"] != candidate["reference_crop_file"]:
            raise ValueError("suggestion crop file must match the candidate reference crop")
        if crop_reference["crop_id"] != Path(crop_reference["file"]).stem:
            raise ValueError("crop ID must match the crop-reference file stem")
        if crop_reference["crop_id"] not in source_crop_ids:
            raise ValueError("suggestion crop ID must be a source crop for the candidate")
    for observation in candidate["price_observations"]:
        if observation["source_crop_id"] not in source_crop_ids:
            raise ValueError("price-observation crop ID must be a source crop for the candidate")
        source_invoice_id = (
            "e05-synth-invoice-" + observation["source_crop_id"].split("_", 1)[0]
        )
        if observation["invoice_id"] not in invoice_ids or observation["invoice_id"] != source_invoice_id:
            raise ValueError("price observation must point to its candidate source invoice")


class N05ProductCandidateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    def _golden(self, fixture_id: str) -> dict:
        path = GOLDEN_DIR / f"product-candidate-{fixture_id}.golden.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_four_real_fixture_goldens_match_schema_and_provenance(self) -> None:
        paths = sorted(GOLDEN_DIR.glob("product-candidate-*.golden.json"))
        self.assertEqual(
            [path.name for path in paths],
            [f"product-candidate-{fixture_id}.golden.json" for fixture_id in FIXTURE_IDS],
        )

        for fixture_id, path in zip(FIXTURE_IDS, paths):
            with self.subTest(fixture_id=fixture_id):
                raw = path.read_text(encoding="utf-8")
                example = json.loads(raw)
                self.validator.validate(example)
                self.assertEqual(serialize_document(example), raw)
                self.assertEqual(example["schema_version"], N05_SCHEMA_VERSION)
                self.assertEqual(example["source_fixture_id"], fixture_id)
                fixture_path = ROOT / example["source_fixture_file"]
                self.assertTrue(fixture_path.is_file())
                fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
                self.assertIsNone(fixture["header"]["captured_at"])
                self.assertEqual(example["price_observation_date_source"], "probe.captured_at")

                candidate = example["candidate"]
                _validate_example_relationships(example)
                self.assertEqual(candidate["price_observations"], [])
                self.assertTrue(example["name_suggestions_enabled"])
                self.assertEqual(len(candidate["name_suggestions"]), 1)
                suggestion = candidate["name_suggestions"][0]
                self.assertEqual(suggestion["engine"], "ParisaOCR")
                self.assertEqual(suggestion["engine_version"], "0.7.2")
                self.assertEqual(suggestion["model_version"], "parisaocr-fa-0.1")
                self.assertIsInstance(suggestion["confidence"], float)
                self.assertFalse(suggestion["accepted"])
                self.assertEqual(
                    suggestion["suggested_name"], "\n".join(suggestion["lines"])
                )

                crop_reference = suggestion["crop_reference"]
                self.assertEqual(crop_reference["file"], candidate["reference_crop_file"])
                self.assertEqual(crop_reference["crop_id"], Path(crop_reference["file"]).stem)
                crop_path = ROOT / crop_reference["file"]
                self.assertEqual(
                    crop_reference["sha256"],
                    hashlib.sha256(crop_path.read_bytes()).hexdigest(),
                )

        # The 31-row candidate is deliberately the real repeated cluster shared
        # with fixture 32; the example retains that N-02 aggregation unchanged.
        repeated = self._golden("31")["candidate"]
        self.assertEqual(repeated["source_crop_ids"], ["31_row0", "32_row0"])
        self.assertEqual(repeated["occurrence_count"], 2)

        # This actual OCR result contains two printed lines; do not flatten it.
        two_line = self._golden("33")["candidate"]["name_suggestions"][0]
        self.assertEqual(len(two_line["lines"]), 2)
        self.assertEqual(two_line["suggested_name"], "\n".join(two_line["lines"]))

    def test_same_input_generation_is_byte_identical_and_matches_committed_goldens(self) -> None:
        first = {
            name: serialize_document(example)
            for name, example in build_n05_candidate_examples(ROOT).items()
        }
        second = {
            name: serialize_document(example)
            for name, example in build_n05_candidate_examples(ROOT).items()
        }
        committed = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(GOLDEN_DIR.glob("product-candidate-*.golden.json"))
        }
        self.assertEqual(first, second)
        self.assertEqual(first, committed)

    def test_explicitly_disabled_suggestions_are_an_empty_array(self) -> None:
        example = copy.deepcopy(self._golden("29"))
        example["name_suggestions_enabled"] = False
        example["candidate"]["name_suggestions"] = []
        self.validator.validate(example)

        example["candidate"]["name_suggestions"] = [
            self._golden("29")["candidate"]["name_suggestions"][0]
        ]
        with self.assertRaises(ValidationError):
            self.validator.validate(example)

    def test_price_observation_schema_accepts_only_explicitly_dated_records(self) -> None:
        # Synthetic schema probe only. The committed examples remain empty
        # because the canonical fixtures carry no Probe captured_at value.
        example = copy.deepcopy(self._golden("29"))
        example["candidate"]["price_observations"] = [{
            "observed_on": "2099-01-02",
            "unit_price_rials": 125000,
            "invoice_id": "e05-synth-invoice-29",
            "source_crop_id": "29_row0",
        }]
        self.validator.validate(example)
        _validate_example_relationships(example)

        wrong_source = copy.deepcopy(example)
        wrong_source["candidate"]["price_observations"][0]["invoice_id"] = (
            "e05-synth-invoice-32"
        )
        self.validator.validate(wrong_source)
        with self.assertRaisesRegex(ValueError, "source invoice"):
            _validate_example_relationships(wrong_source)

        example["candidate"]["price_observations"][0]["observed_on"] = "not-a-date"
        with self.assertRaises(ValidationError):
            self.validator.validate(example)

    def test_suggestions_cannot_be_accepted_and_confidence_is_bounded(self) -> None:
        example = copy.deepcopy(self._golden("29"))
        suggestion = example["candidate"]["name_suggestions"][0]
        suggestion["accepted"] = True
        with self.assertRaises(ValidationError):
            self.validator.validate(example)

        suggestion["accepted"] = False
        suggestion["confidence"] = 100.01
        with self.assertRaises(ValidationError):
            self.validator.validate(example)

    def test_crop_reference_must_match_candidate_crop_and_actual_bytes(self) -> None:
        example = copy.deepcopy(self._golden("29"))
        suggestion = example["candidate"]["name_suggestions"][0]
        suggestion["crop_reference"]["file"] = (
            "tests/fixtures/real/n02-reference-crops/29_row1.png"
        )
        # Both paths are structurally safe; the cross-field relationship is
        # checked semantically because JSON Schema cannot compare these values.
        self.validator.validate(example)
        with self.assertRaisesRegex(ValueError, "must match"):
            _validate_example_relationships(example)


if __name__ == "__main__":
    unittest.main()
