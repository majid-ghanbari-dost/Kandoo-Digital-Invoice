from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for import_path in (SRC, SCRIPTS):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from build_e28_drift_baseline import DEFAULT_IMAGES, build_baseline  # noqa: E402
from e28_drift_calibration import (  # noqa: E402
    CLEAN_VARIANTS,
    STRESS_VARIANTS,
    apply_calibration_variant,
)
from image_extraction_adapter.drift_monitor import (  # noqa: E402
    DRIFT_REASON,
    DRIFT_BASELINE_SCHEMA,
    aggregate_mean_distance_by_symbol,
    evaluate_glyph_drift,
    load_glyph_drift_baseline,
)
from image_extraction_adapter.pipeline_v0 import (  # noqa: E402
    DEFAULT_GLYPH_DRIFT_BASELINE_PATH,
    DEFAULT_TEMPLATE_BANK_PATH,
    apply_operator_correction,
    extract_pipeline_v0,
    normalize_label_text,
)

BASELINE_SCHEMA_PATH = ROOT / "schemas/e28/glyph_drift_baseline_v1.schema.json"
LABELS_PATH = ROOT / "tests/fixtures/real/labels.json"


class E28GlyphDriftMonitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = load_glyph_drift_baseline(DEFAULT_GLYPH_DRIFT_BASELINE_PATH)
        schema = json.loads(BASELINE_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)
        cls.validator.validate(cls.baseline)
        cls.labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _context(row_count: int) -> dict:
        return {
            "mode": "B",
            "invoice_id": "e28-test-invoice",
            "display_number": "e28-test-display",
            "operation_id": "e28-test-operation",
            "device_id": "e28-test-device",
            "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
            "store_id": "e28-test-store",
            "customer": {
                "phone": "+15551234567",
                "phone_status": "claimed",
                "phone_provenance": "captured",
            },
            "product_names": [f"Confirmed item {index}" for index in range(row_count)],
            "product_name_provenance": ["captured"] * row_count,
        }

    def _run_variant(self, variant: str, temp: Path, *, context: bool = True):
        with Image.open(ROOT / "tests/fixtures/real/29.png") as opened:
            opened.load()
            original = opened.convert("RGB")
        image_path = temp / f"{variant}.png"
        apply_calibration_variant(original, variant).save(image_path, format="PNG")
        return extract_pipeline_v0(
            image_path,
            templates_path=DEFAULT_TEMPLATE_BANK_PATH,
            drift_baseline_path=DEFAULT_GLYPH_DRIFT_BASELINE_PATH,
            canonical_context=self._context(4) if context else None,
        )

    def test_baseline_is_data_derived_versioned_and_matches_default_bank(self) -> None:
        self.assertEqual(self.baseline["schema_version"], DRIFT_BASELINE_SCHEMA)
        self.assertEqual(
            self.baseline["template_library_id"],
            hashlib.sha256(DEFAULT_TEMPLATE_BANK_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(len(self.baseline["source_images"]), 4)
        self.assertEqual(len(self.baseline["symbols"]), 11)
        self.assertTrue(all(item["bound"] >= 0 for item in self.baseline["symbols"].values()))
        self.assertEqual(
            set(self.baseline["calibration"]["clean_control_variants"]),
            set(CLEAN_VARIANTS),
        )
        for result in self.baseline["calibration"]["synthetic_stress_checks"].values():
            self.assertEqual(result["sample_count"], 4)
            self.assertEqual(result["triggered_sample_count"], 4)
            self.assertGreater(result["minimum_excess_over_bound"], 0)

    def test_all_four_accepted_invoices_record_symbol_means_with_zero_wrong_extracted(self) -> None:
        extracted_but_wrong = 0
        accepted = 0
        for entry in self.labels["invoices"]:
            with self.subTest(invoice=entry["id"]):
                result = extract_pipeline_v0(
                    ROOT / "tests/fixtures/real" / entry["path"],
                    templates_path=DEFAULT_TEMPLATE_BANK_PATH,
                    drift_baseline_path=DEFAULT_GLYPH_DRIFT_BASELINE_PATH,
                )
                self.assertEqual(result.status, "AUTO_CANDIDATE")
                accepted += 1
                record = result.glyph_drift
                self.assertIsNotNone(record)
                self.assertEqual(record["status"], "CLEAR")
                self.assertEqual(record["reason"], None)
                self.assertTrue(record["mean_distance_by_symbol"])
                self.assertEqual(
                    result.to_dict().get("glyph_drift"),
                    None,
                    "legacy PipelineResult serialization remains byte-compatible by default",
                )
                self.assertEqual(
                    result.to_dict(include_glyph_drift=True)["glyph_drift"], record)
                for cell in result.cell_results:
                    if cell.status != "EXTRACTED":
                        continue
                    reference = entry["values"].get(cell.field_name)
                    if reference is not None and normalize_label_text(cell.raw_value) != normalize_label_text(reference):
                        extracted_but_wrong += 1
        self.assertEqual(accepted, 4)
        self.assertEqual(extracted_but_wrong, 0)

    def test_clean_quality_variations_do_not_trigger_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e28-clean-variations-") as temp_name:
            temp = Path(temp_name)
            for variant in CLEAN_VARIANTS:
                with self.subTest(variant=variant):
                    result = self._run_variant(variant, temp)
                    self.assertEqual(result.status, "AUTO_CANDIDATE", result.reason)
                    self.assertEqual(result.glyph_drift["status"], "CLEAR")
                    self.assertFalse(result.glyph_drift["triggered_symbols"])
                    self.assertIsNotNone(result.canonical_invoice)
                    self.assertEqual(result.canonical_invoice["state"], "EXTRACTED")

    def test_thinning_blur_and_noise_hold_every_cell_for_onboarding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e28-stress-variations-") as temp_name:
            temp = Path(temp_name)
            for variant in STRESS_VARIANTS:
                with self.subTest(variant=variant):
                    result = self._run_variant(variant, temp)
                    self.assertEqual(result.status, "REVIEW")
                    self.assertEqual(result.reason, DRIFT_REASON)
                    self.assertEqual(result.glyph_drift["status"], "REVIEW")
                    self.assertEqual(result.glyph_drift["reason"], DRIFT_REASON)
                    self.assertTrue(result.glyph_drift["triggered_symbols"])
                    self.assertTrue(result.glyph_drift["mean_distance_by_symbol"])
                    self.assertTrue(result.cell_results)
                    self.assertTrue(all(cell.status == "REVIEW" for cell in result.cell_results))
                    self.assertIsNone(result.canonical_invoice)

    def test_operator_correction_cannot_bypass_a_drift_hold(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e28-correction-hold-") as temp_name:
            result = self._run_variant("cell_blur_1.0", Path(temp_name))
        corrected = apply_operator_correction(result, {"line.0.total": "1450000"})
        self.assertEqual(corrected.status, "REVIEW")
        self.assertEqual(corrected.reason, DRIFT_REASON)
        self.assertTrue(all(cell.status == "REVIEW" for cell in corrected.cell_results))
        self.assertIsNone(corrected.canonical_invoice)
        self.assertIn(DRIFT_REASON, corrected.canonical_blockers)

    def test_missing_baseline_fails_closed_and_does_not_emit_extracted_cells(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e28-missing-baseline-") as temp_name:
            missing = Path(temp_name) / "missing.json"
            result = extract_pipeline_v0(
                ROOT / "tests/fixtures/real/29.png",
                templates_path=DEFAULT_TEMPLATE_BANK_PATH,
                drift_baseline_path=missing,
                canonical_context=self._context(4),
            )
        self.assertEqual(result.status, "REVIEW")
        self.assertEqual(result.reason, DRIFT_REASON)
        self.assertTrue(all(cell.status == "REVIEW" for cell in result.cell_results))
        self.assertIsNone(result.canonical_invoice)

    def test_measurement_and_evaluator_fail_closed_on_unknown_symbols(self) -> None:
        class _Reading:
            def __init__(self, symbol: str, distance: float) -> None:
                self.best_label = symbol
                self.distance = distance

        class _CellReading:
            readings = (_Reading("⚑", 0.02),)

        means, counts, errors = aggregate_mean_distance_by_symbol(
            (("line.0.total", _CellReading()),)
        )
        self.assertEqual(means, {"⚑": 0.02})
        self.assertEqual(counts, {"⚑": 1})
        self.assertFalse(errors)
        record = evaluate_glyph_drift(
            means,
            counts,
            template_library_id=self.baseline["template_library_id"],
            baseline=self.baseline,
        )
        self.assertEqual(record["status"], "REVIEW")
        self.assertEqual(record["reason"], DRIFT_REASON)
        self.assertEqual(record["triggered_symbols"], ["⚑"])

    def test_baseline_builder_reproduces_committed_measurements(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e28-baseline-rebuild-") as temp_name:
            output = Path(temp_name) / "baseline.json"
            rebuilt = build_baseline(
                DEFAULT_IMAGES,
                templates_path=DEFAULT_TEMPLATE_BANK_PATH,
                output_path=output,
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                self.baseline,
            )
            self.validator.validate(rebuilt)


if __name__ == "__main__":
    unittest.main()
