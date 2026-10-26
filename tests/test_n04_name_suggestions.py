from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.benchmark_n04_parisaocr import (
    _chunk_github_notice_items,
    _compact_json,
    _escape_github_command_data,
)
from scripts.n04_name_suggestions import (
    MODEL_VERSION,
    SCHEMA_VERSION,
    SOURCE_SCHEMA_VERSION,
    NameRecognition,
    _make_windows_resource_stub,
    enrich_product_candidates,
)


class _FakeSuggester:
    engine_name = "ParisaOCR"
    engine_version = "0.7.2"
    model_version = MODEL_VERSION

    def __init__(self, result: NameRecognition) -> None:
        self.result = result
        self.seen: list[Path] = []

    def suggest(self, crop_path: Path) -> NameRecognition:
        self.seen.append(crop_path)
        return self.result


def _source_document(crop_names: tuple[str, ...]) -> dict:
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source_fixture_files": ["fixture.json"],
        "price_observation_date_source": "header.printed_date",
        "candidates": [
            {
                "name_crop_cluster_id": f"name-dhash-{index:016x}",
                "reference_crop_file": f"crops/{crop_name}.png",
                "occurrence_count": 1,
                "quantity_sum": 1,
                "source_crop_ids": [crop_name],
                "price_observations": [],
                "invoice_ids": [f"invoice-{index}"],
            }
            for index, crop_name in enumerate(crop_names, start=1)
        ],
    }


class N04NameSuggestionTests(unittest.TestCase):
    def test_workflow_notice_message_escapes_percent_and_newlines(self) -> None:
        self.assertEqual(
            _escape_github_command_data("100%\r\nnext"),
            "100%25%0D%0Anext",
        )

    def test_workflow_notice_lists_are_chunked_below_message_limit(self) -> None:
        items = [{"name": f"dep-{index}", "metadata": "x" * 700}
                 for index in range(7)]
        chunks = _chunk_github_notice_items(items, max_message_chars=1500)

        self.assertGreater(len(chunks), 1)
        self.assertEqual([item for chunk in chunks for item in chunk], items)
        for chunk in chunks:
            encoded = _escape_github_command_data(_compact_json(chunk))
            self.assertLessEqual(len(encoded), 1500)

    def test_optional_disabled_path_adds_empty_list_to_every_candidate(self) -> None:
        source = _source_document(("29_row0", "31_row1"))
        original = repr(source)

        enriched = enrich_product_candidates(source, Path("."))

        self.assertEqual(enriched["schema_version"], SCHEMA_VERSION)
        self.assertEqual(enriched["source_schema_version"], SOURCE_SCHEMA_VERSION)
        self.assertFalse(enriched["name_suggestions_enabled"])
        self.assertEqual(len(enriched["candidates"]), 2)
        self.assertTrue(all(candidate["name_suggestions"] == []
                            for candidate in enriched["candidates"]))
        self.assertEqual(repr(source), original)

    def test_enabled_path_preserves_two_lines_and_never_accepts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crop_paths = [root / "crops" / "29_row0.png", root / "crops" / "31_row1.png"]
            for crop_path in crop_paths:
                crop_path.parent.mkdir(parents=True, exist_ok=True)
                crop_path.write_bytes(b"test crop bytes: " + crop_path.name.encode("ascii"))
            source = _source_document(("29_row0", "31_row1"))
            suggester = _FakeSuggester(
                NameRecognition(("نام خط اول", "نام خط دوم"), 98.7654321))
            timings: dict[str, float] = {}

            enriched = enrich_product_candidates(
                source, root, suggester=suggester, inference_timings=timings)

            self.assertTrue(enriched["name_suggestions_enabled"])
            self.assertEqual(suggester.seen, crop_paths)
            self.assertEqual(set(timings), {"29_row0", "31_row1"})
            self.assertTrue(all(value >= 0 for value in timings.values()))
            for candidate, crop_path in zip(enriched["candidates"], crop_paths):
                self.assertEqual(len(candidate["name_suggestions"]), 1)
                suggestion = candidate["name_suggestions"][0]
                self.assertEqual(suggestion["lines"], ["نام خط اول", "نام خط دوم"])
                self.assertEqual(suggestion["suggested_name"], "نام خط اول\nنام خط دوم")
                self.assertEqual(suggestion["confidence"], 98.7654)
                self.assertEqual(suggestion["engine"], "ParisaOCR")
                self.assertEqual(suggestion["engine_version"], "0.7.2")
                self.assertEqual(suggestion["model_version"], MODEL_VERSION)
                self.assertFalse(suggestion["accepted"])
                self.assertEqual(
                    suggestion["crop_reference"],
                    {
                        "crop_id": crop_path.stem,
                        "file": f"crops/{crop_path.stem}.png",
                        "sha256": hashlib.sha256(crop_path.read_bytes()).hexdigest(),
                    },
                )

    def test_empty_recognition_is_still_a_non_accepted_suggestion_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crop = root / "crops" / "33_row2.png"
            crop.parent.mkdir(parents=True)
            crop.write_bytes(b"empty-result-test")
            enriched = enrich_product_candidates(
                _source_document(("33_row2",)),
                root,
                suggester=_FakeSuggester(NameRecognition((), None)),
            )

        suggestion = enriched["candidates"][0]["name_suggestions"][0]
        self.assertEqual(suggestion["lines"], [])
        self.assertEqual(suggestion["suggested_name"], "")
        self.assertIsNone(suggestion["confidence"])
        self.assertFalse(suggestion["accepted"])

    def test_unsafe_or_missing_crop_reference_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            suggester = _FakeSuggester(NameRecognition(("نام",), 90.0))
            unsafe = _source_document(("29_row0",))
            unsafe["candidates"][0]["reference_crop_file"] = "../29_row0.png"
            with self.assertRaisesRegex(ValueError, "safe POSIX"):
                enrich_product_candidates(unsafe, root, suggester=suggester)

            drive_path = _source_document(("29_row0",))
            drive_path["candidates"][0]["reference_crop_file"] = "C:/external/29_row0.png"
            with self.assertRaisesRegex(ValueError, "safe POSIX"):
                enrich_product_candidates(drive_path, root, suggester=suggester)

            windows_path = _source_document(("29_row0",))
            windows_path["candidates"][0]["reference_crop_file"] = "crops\\29_row0.png"
            with self.assertRaisesRegex(ValueError, "safe POSIX"):
                enrich_product_candidates(windows_path, root, suggester=suggester)

            missing = _source_document(("29_row0",))
            with self.assertRaisesRegex(FileNotFoundError, "missing candidate reference crop"):
                enrich_product_candidates(missing, root, suggester=suggester)

    def test_non_finite_or_out_of_range_confidence_is_rejected(self) -> None:
        for value in (-0.1, 100.1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    NameRecognition(("نام",), value)

    def test_windows_compatibility_stub_refuses_posix_only_memory_limit_calls(self) -> None:
        resource_stub = _make_windows_resource_stub()
        self.assertEqual(resource_stub.RLIMIT_AS, 0)
        with self.assertRaisesRegex(RuntimeError, "requires POSIX resource APIs"):
            resource_stub.setrlimit(resource_stub.RLIMIT_AS, (1024, 1024))

    def test_source_version_and_preexisting_suggestions_are_not_silently_overwritten(self) -> None:
        wrong_version = _source_document(("29_row0",))
        wrong_version["schema_version"] = "unrecognized.v1"
        with self.assertRaisesRegex(ValueError, "expected source schema"):
            enrich_product_candidates(wrong_version)

        preexisting = _source_document(("29_row0",))
        preexisting["candidates"][0]["name_suggestions"] = [{"accepted": True}]
        with self.assertRaisesRegex(ValueError, "already contains"):
            enrich_product_candidates(preexisting)


if __name__ == "__main__":
    unittest.main()
