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
from n04_name_suggestions import NameRecognition, serialize_document  # noqa: E402

SCHEMA_PATH = ROOT / "schemas" / "n05" / "product_candidate_v1.schema.json"
GOLDEN_DIR = ROOT / "tests" / "fixtures" / "real" / "n05-goldens"
FIXTURE_IDS = ("29", "31", "32", "33")


def _validate_example_relationships(example: dict) -> None:
    candidate = example["candidate"]
    source_crop_ids = set(candidate["source_crop_ids"])
    invoice_ids = set(candidate["invoice_ids"])
    confirmation = candidate["name_confirmation"]
    confirmation_source = confirmation["confirmation_source_cluster_id"]
    if confirmation["confirmed_name"] and confirmation_source != candidate["name_crop_cluster_id"]:
        raise ValueError("confirmation must be scoped to the exact crop cluster")
    if candidate["name_crop_cluster_id"] in confirmation["near_threshold_cluster_ids"]:
        raise ValueError("a near-threshold cluster must remain a separate candidate")
    if confirmation["near_threshold_cluster_ids"] and confirmation["confirmation_status"] != "REVIEW":
        raise ValueError("near-threshold cluster requires human review")
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


class _FakeNameSuggester:
    engine_name = "FakeN04"
    engine_version = "test-1"
    model_version = "test-model"

    def suggest(self, crop_path: Path) -> NameRecognition:
        if not crop_path.is_file():
            raise FileNotFoundError(crop_path)
        return NameRecognition(("synthetic", "suggestion"), 88.0)


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
                self.assertFalse(example["name_suggestions_enabled"])
                self.assertEqual(candidate["name_suggestions"], [])
                confirmation = candidate["name_confirmation"]
                self.assertEqual(confirmation["confirmed_name"], "")
                self.assertEqual(confirmation["confirmation_status"], "UNCONFIRMED")
                self.assertIsNone(confirmation["confirmation_source_cluster_id"])
                self.assertFalse(confirmation["review_required"])
                self.assertEqual(confirmation["review_reasons"], [])
                self.assertEqual(confirmation["near_threshold_cluster_ids"], [])

        # The 31-row candidate is deliberately the real repeated cluster shared
        # with fixture 32; the example retains that N-02 aggregation unchanged.
        repeated = self._golden("31")["candidate"]
        self.assertEqual(repeated["source_crop_ids"], ["31_row0", "32_row0"])
        self.assertEqual(repeated["occurrence_count"], 2)
        self.assertTrue((ROOT / repeated["reference_crop_file"]).is_file())

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

    def test_default_build_has_no_ocr_and_suggestions_are_empty(self) -> None:
        example = copy.deepcopy(self._golden("29"))
        self.assertFalse(example["name_suggestions_enabled"])
        self.assertEqual(example["candidate"]["name_suggestions"], [])
        self.validator.validate(example)

        example["candidate"]["name_suggestions"] = [{}]
        with self.assertRaises(ValidationError):
            self.validator.validate(example)

    def test_optional_suggester_adds_non_accepting_n04_suggestion(self) -> None:
        examples = build_n05_candidate_examples(ROOT, suggester=_FakeNameSuggester())
        for example in examples.values():
            with self.subTest(fixture=example["source_fixture_id"]):
                self.validator.validate(example)
                self.assertTrue(example["name_suggestions_enabled"])
                suggestions = example["candidate"]["name_suggestions"]
                self.assertEqual(len(suggestions), 1)
                self.assertEqual(suggestions[0]["lines"], ["synthetic", "suggestion"])
                self.assertEqual(suggestions[0]["suggested_name"], "synthetic\nsuggestion")
                self.assertFalse(suggestions[0]["accepted"])
                crop_reference = suggestions[0]["crop_reference"]
                crop_path = ROOT / crop_reference["file"]
                self.assertEqual(crop_reference["file"], example["candidate"]["reference_crop_file"])
                self.assertEqual(
                    crop_reference["sha256"],
                    hashlib.sha256(crop_path.read_bytes()).hexdigest(),
                )

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
        example = copy.deepcopy(
            build_n05_candidate_examples(ROOT, suggester=_FakeNameSuggester())[
                "product-candidate-29.golden.json"
            ]
        )
        suggestion = example["candidate"]["name_suggestions"][0]
        suggestion["accepted"] = True
        with self.assertRaises(ValidationError):
            self.validator.validate(example)

        suggestion["accepted"] = False
        suggestion["confidence"] = 100.01
        with self.assertRaises(ValidationError):
            self.validator.validate(example)

    def test_crop_reference_must_match_candidate_crop_and_actual_bytes(self) -> None:
        example = copy.deepcopy(
            build_n05_candidate_examples(ROOT, suggester=_FakeNameSuggester())[
                "product-candidate-29.golden.json"
            ]
        )
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
