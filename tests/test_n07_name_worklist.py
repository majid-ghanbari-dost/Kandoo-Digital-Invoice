from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jsonschema import Draft202012Validator
from PIL import Image
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from n04_name_suggestions import NameRecognition  # noqa: E402
from n07_name_worklist import (  # noqa: E402
    build_name_worklist,
    build_name_worklist_from_occurrences,
    load_confirmations,
    serialize_worklist,
    write_confirmation_file,
)
from run_n02_product_candidates import (  # noqa: E402
    CandidateOccurrence,
    collect_candidate_occurrences,
)
from run_n07_name_worklist import main as n07_main  # noqa: E402

N05_SCHEMA_PATH = ROOT / "schemas" / "n05" / "product_candidate_v1.schema.json"
N07_SCHEMA_PATH = ROOT / "schemas" / "n07" / "name_worklist_v1.schema.json"


class _FakeNameSuggester:
    engine_name = "FakeN04"
    engine_version = "test-1"
    model_version = "test-model"

    def suggest(self, crop_path: Path) -> NameRecognition:
        if not crop_path.is_file():
            raise FileNotFoundError(crop_path)
        return NameRecognition(("optional", "name"), 87.5)


class N07NameWorklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.n05_schema = json.loads(N05_SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.n07_schema = json.loads(N07_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.n05_schema)
        Draft202012Validator.check_schema(cls.n07_schema)
        registry = Registry().with_resource(
            cls.n05_schema["$id"], Resource.from_contents(cls.n05_schema)
        )
        cls.validator = Draft202012Validator(cls.n07_schema, registry=registry)

    def _validate(self, document: dict) -> None:
        self.validator.validate(document)

    def test_default_worklist_writes_one_crop_and_empty_confirmation_per_candidate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="n07-worklist-default-") as temp:
            output_dir = Path(temp)
            document = build_name_worklist(ROOT, output_dir)
            self._validate(document)

            self.assertEqual(document["schema_version"], "n07.name-worklist.v1")
            self.assertFalse(document["name_suggestions_enabled"])
            self.assertEqual(len(document["work_items"]), 22)
            cluster_ids: list[str] = []
            for item in document["work_items"]:
                candidate = item["candidate"]
                cluster_id = candidate["name_crop_cluster_id"]
                cluster_ids.append(cluster_id)
                confirmation = candidate["name_confirmation"]
                self.assertEqual(confirmation["confirmed_name"], "")
                self.assertEqual(confirmation["confirmation_status"], "UNCONFIRMED")
                self.assertFalse(confirmation["review_required"])
                self.assertEqual(confirmation["review_reasons"], [])
                self.assertEqual(confirmation["near_threshold_cluster_ids"], [])
                self.assertEqual(candidate["name_suggestions"], [])

                crop_path = output_dir / item["crop_image"]["file"]
                self.assertTrue(crop_path.is_file())
                self.assertEqual(
                    item["crop_image"]["sha256"],
                    hashlib.sha256(crop_path.read_bytes()).hexdigest(),
                )
                with Image.open(crop_path) as crop:
                    self.assertGreater(crop.width, 0)
                    self.assertGreater(crop.height, 0)
            self.assertEqual(len(cluster_ids), len(set(cluster_ids)))

    def test_same_inputs_rerun_to_byte_identical_json_and_crop_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="n07-worklist-rerun-") as temp:
            root = Path(temp)
            first_dir, second_dir = root / "first", root / "second"
            first = build_name_worklist(ROOT, first_dir)
            second = build_name_worklist(ROOT, second_dir)
            self.assertEqual(serialize_worklist(first), serialize_worklist(second))
            self.assertEqual(
                sorted(path.name for path in (first_dir / "crops").iterdir()),
                sorted(path.name for path in (second_dir / "crops").iterdir()),
            )
            for path in sorted((first_dir / "crops").iterdir()):
                self.assertEqual(
                    path.read_bytes(),
                    (second_dir / "crops" / path.name).read_bytes(),
                )

    def test_confirmation_is_reused_by_exact_cluster_for_a_later_invoice(self) -> None:
        occurrences, crop_images = collect_candidate_occurrences(ROOT)
        with tempfile.TemporaryDirectory(prefix="n07-worklist-initial-") as temp:
            initial = build_name_worklist_from_occurrences(
                occurrences, crop_images, Path(temp) / "initial"
            )
        target = next(
            item["candidate"]
            for item in initial["work_items"]
            if "31_row0" in item["candidate"]["source_crop_ids"]
        )
        cluster_id = target["name_crop_cluster_id"]
        added = CandidateOccurrence(
            name_crop_cluster_id=cluster_id,
            source_crop_id="34_row0",
            reference_crop_file=target["reference_crop_file"],
            invoice_id="e05-synth-invoice-34",
            quantity=2,
            unit_price_rials=125000,
            observed_on=None,
        )
        later_occurrences = [*occurrences, added]
        later_images = dict(crop_images)
        later_images["34_row0"] = crop_images["31_row0"].copy()
        confirmed_names = {cluster_id: "Human-confirmed repeated item"}

        with tempfile.TemporaryDirectory(prefix="n07-worklist-later-") as temp:
            confirmation_path = Path(temp) / "confirmations.json"
            write_confirmation_file(confirmation_path, confirmed_names)
            loaded_confirmations = load_confirmations(confirmation_path)
            self.assertEqual(loaded_confirmations, confirmed_names)
            first = build_name_worklist_from_occurrences(
                later_occurrences,
                later_images,
                Path(temp) / "first",
                confirmed_names=loaded_confirmations,
            )
            second = build_name_worklist_from_occurrences(
                later_occurrences,
                later_images,
                Path(temp) / "second",
                confirmed_names=loaded_confirmations,
            )

        self.assertEqual(serialize_worklist(first), serialize_worklist(second))
        reused = next(
            item["candidate"] for item in first["work_items"]
            if item["candidate"]["name_crop_cluster_id"] == cluster_id
        )
        self.assertEqual(reused["occurrence_count"], target["occurrence_count"] + 1)
        self.assertIn("34_row0", reused["source_crop_ids"])
        self.assertEqual(reused["name_confirmation"]["confirmed_name"], "Human-confirmed repeated item")
        self.assertEqual(reused["name_confirmation"]["confirmation_status"], "CONFIRMED")
        self.assertEqual(reused["name_confirmation"]["confirmation_source_cluster_id"], cluster_id)

    def test_near_threshold_hashes_remain_separate_and_require_review(self) -> None:
        crop_paths = (
            ROOT / "tests/fixtures/real/n02-reference-crops/29_row0.png",
            ROOT / "tests/fixtures/real/n02-reference-crops/31_row0.png",
        )
        crop_images = {}
        for crop_id, path in zip(("29_row0", "31_row0"), crop_paths, strict=True):
            with Image.open(path) as image:
                crop_images[crop_id] = image.copy()
        occurrences = [
            CandidateOccurrence(
                name_crop_cluster_id="name-dhash-0000000000000000",
                source_crop_id=crop_id,
                reference_crop_file=path.relative_to(ROOT).as_posix(),
                invoice_id=f"e05-synth-invoice-{crop_id.split('_', 1)[0]}",
                quantity=1,
                unit_price_rials=1000,
                observed_on=None,
            )
            for crop_id, path in zip(("29_row0", "31_row0"), crop_paths, strict=True)
        ]
        # Isolate the threshold boundary: these normalized dHashes differ by one bit.
        fake_hashes = [
            SimpleNamespace(dhash="0000000000000000"),
            SimpleNamespace(dhash="0000000000000001"),
        ]
        with tempfile.TemporaryDirectory(prefix="n07-near-threshold-") as temp:
            with patch("n07_name_worklist.cluster_description_crops", return_value=fake_hashes):
                document = build_name_worklist_from_occurrences(
                    occurrences,
                    crop_images,
                    Path(temp),
                    confirmed_names={"name-dhash-0000000000000000": "Prior confirmation"},
                )
            self._validate(document)

        self.assertEqual(len(document["work_items"]), 2)
        by_id = {
            item["candidate"]["name_crop_cluster_id"]: item["candidate"]
            for item in document["work_items"]
        }
        left_id = "name-dhash-0000000000000000"
        right_id = "name-dhash-0000000000000001"
        self.assertEqual(set(by_id), {left_id, right_id})
        self.assertEqual(by_id[left_id]["occurrence_count"], 1)
        self.assertEqual(by_id[right_id]["occurrence_count"], 1)
        for cluster_id, neighbor_id in ((left_id, right_id), (right_id, left_id)):
            confirmation = by_id[cluster_id]["name_confirmation"]
            self.assertEqual(confirmation["confirmation_status"], "REVIEW")
            self.assertTrue(confirmation["review_required"])
            self.assertEqual(confirmation["review_reasons"], ["NEAR_THRESHOLD_CLUSTER"])
            self.assertEqual(confirmation["near_threshold_cluster_ids"], [neighbor_id])
            self.assertNotIn(cluster_id, confirmation["near_threshold_cluster_ids"])
        self.assertEqual(by_id[left_id]["name_confirmation"]["confirmed_name"], "Prior confirmation")
        self.assertEqual(by_id[right_id]["name_confirmation"]["confirmed_name"], "")

    def test_optional_n04_suggester_is_attached_only_when_supplied(self) -> None:
        with tempfile.TemporaryDirectory(prefix="n07-worklist-optional-n04-") as temp:
            document = build_name_worklist(
                ROOT,
                Path(temp),
                suggester=_FakeNameSuggester(),
            )
            self._validate(document)
        self.assertTrue(document["name_suggestions_enabled"])
        for item in document["work_items"]:
            suggestions = item["candidate"]["name_suggestions"]
            self.assertEqual(len(suggestions), 1)
            self.assertEqual(suggestions[0]["lines"], ["optional", "name"])
            self.assertEqual(suggestions[0]["suggested_name"], "optional\nname")
            self.assertFalse(suggestions[0]["accepted"])

    def test_cli_default_does_not_construct_optional_ocr(self) -> None:
        with tempfile.TemporaryDirectory(prefix="n07-worklist-cli-default-") as temp:
            stdout = io.StringIO()
            with patch("run_n07_name_worklist.ParisaOCRNameSuggester") as suggester:
                with contextlib.redirect_stdout(stdout):
                    code = n07_main([
                        "--repo-root", str(ROOT),
                        "--output-dir", temp,
                    ])
            suggester.assert_not_called()
            document = json.loads((Path(temp) / "name-worklist.json").read_text())
        self.assertEqual(code, 0)
        self.assertFalse(document["name_suggestions_enabled"])
        self.assertIn('"name_suggestions_enabled": false', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
