from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from image_extraction_adapter.canonical_invoice import (
    is_issuable,
    validate_canonical_invoice,
)
from image_extraction_adapter.pipeline_v0 import (
    DEFAULT_TEMPLATE_BANK_PATH,
    LEGACY_TEMPLATE_BANK_PATH,
    TemplateBankBuildError,
    TemplateLeakageError,
    TemplateProvenanceError,
    apply_operator_correction,
    assert_no_template_leakage,
    build_default_template_bank,
    build_templates_for_fold,
    cluster_description_crops,
    detect_payable_bbox,
    extract_pipeline_v0,
    run_leave_one_out_evaluation,
    to_rials,
)
from image_extraction_adapter.preprocessing import (
    LayoutSafetyResult,
    crop_spatial_cells,
    detect_layout_safe,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "real"
LABELS_PATH = FIXTURES / "labels.json"
DEFAULT_BANK = ROOT / "src" / "templates_bank_default.json"
LEGACY_BANK = ROOT / "src" / "templates.json"


class PipelineV0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
        cls.by_id = {str(item["id"]): item for item in cls.labels["invoices"]}
        if not DEFAULT_BANK.is_file():
            raise RuntimeError("run scripts/build_default_template_bank.py before the tests")

    def _extract(self, invoice_id: str, **kwargs):
        return extract_pipeline_v0(
            FIXTURES / f"{invoice_id}.png",
            templates_path=DEFAULT_BANK,
            **kwargs,
        )

    def _canonical_context(self, row_count: int) -> dict:
        # Test-only values: production identifiers/customer data must be supplied
        # by the caller; pipeline_v0 does not generate these values.
        return {
            "mode": "B",
            "invoice_id": "test-invoice-29",
            "display_number": "test-display-29",
            "operation_id": "test-operation-29",
            "device_id": "test-device-29",
            "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
            "store_id": "test-store-29",
            "customer": {
                "phone": "+15551234567",
                "phone_status": "claimed",
                "phone_provenance": "captured",
            },
            "product_names": [f"Synthetic item {index}" for index in range(row_count)],
            "product_name_provenance": ["captured"] * row_count,
        }

    def test_payable_detector_matches_reference_boxes_on_all_four_fixtures(self) -> None:
        for invoice_id, entry in self.by_id.items():
            with self.subTest(invoice=invoice_id):
                with Image.open(FIXTURES / entry["path"]) as opened:
                    opened.load()
                    image = opened.convert("RGB")
                safety = detect_layout_safe(image)
                self.assertEqual(safety.status, "OK")
                self.assertEqual(
                    detect_payable_bbox(image, safety.geometry),
                    tuple(entry["payable_bbox"]),
                )

    def test_default_bank_provenance_includes_all_four_images_and_sha256(self) -> None:
        data = json.loads(DEFAULT_BANK.read_text(encoding="utf-8"))
        sources = data["bank_metadata"]["source_images"]
        self.assertEqual({item["fixture_id"] for item in sources}, {"29", "31", "32", "33"})
        for source in sources:
            image_path = ROOT / source["path"]
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            self.assertEqual(source["sha256"], digest)
        fixture31 = next(item for item in sources if item["fixture_id"] == "31")
        self.assertIn("invoice.payable", fixture31["excluded_fields"])
        self.assertNotIn("invoice.payable", fixture31["training_fields"])

    def test_default_bank_builder_is_deterministic_and_never_overwrites_legacy_bank(self) -> None:
        legacy_before = hashlib.sha256(LEGACY_BANK.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="pipeline-v0-bank-") as temp:
            output = Path(temp) / "templates_bank_default.json"
            report = build_default_template_bank(
                labels_path=LABELS_PATH,
                output_path=output,
                repo_root=ROOT,
            )
            written_bank = output.read_bytes()
            self.assertNotIn(b"\r", written_bank)
            self.assertEqual(report.bank_sha256, hashlib.sha256(written_bank).hexdigest())
            self.assertEqual(report.bank_sha256, hashlib.sha256(DEFAULT_BANK.read_bytes()).hexdigest())
        with self.assertRaises(TemplateBankBuildError):
            build_default_template_bank(
                labels_path=LABELS_PATH,
                output_path=LEGACY_BANK,
                repo_root=ROOT,
            )
        self.assertEqual(hashlib.sha256(LEGACY_BANK.read_bytes()).hexdigest(), legacy_before)

    def test_fold_bank_contains_only_three_non_held_out_sources(self) -> None:
        templates = build_templates_for_fold(LABELS_PATH, "29", repo_root=ROOT)
        source_hashes = {item["sha256"] for item in templates.provenance}
        held_hash = hashlib.sha256((FIXTURES / "29.png").read_bytes()).hexdigest()
        self.assertEqual(len(templates.provenance), 3)
        self.assertNotIn(held_hash, source_hashes)
        self.assertEqual(
            {Path(item["image"]).name for item in templates.provenance},
            {"31.png", "32.png", "33.png"},
        )
        with tempfile.TemporaryDirectory(prefix="pipeline-v0-fold-save-") as temp_name:
            serialized_bank = Path(temp_name) / "fold-templates.json"
            templates.save(serialized_bank)
            self.assertNotIn(b"\r", serialized_bank.read_bytes())

    def test_leave_one_out_has_three_auto_candidates_one_review_and_no_wrong_extracted_values(self) -> None:
        outcomes = run_leave_one_out_evaluation(LABELS_PATH, repo_root=ROOT)
        by_id = {item.invoice_id: item for item in outcomes}
        self.assertEqual(set(by_id), {"29", "31", "32", "33"})
        self.assertEqual(sum(item.status == "AUTO_CANDIDATE" for item in outcomes), 3)
        self.assertEqual(sum(item.status == "REVIEW" for item in outcomes), 1)
        self.assertEqual(by_id["33"].status, "REVIEW")
        self.assertFalse(by_id["33"].arithmetic_gate_passed)
        self.assertEqual(by_id["33"].review_cells, 18)
        self.assertEqual(by_id["33"].extracted_cells, 9)
        for invoice_id in ("29", "31", "32"):
            self.assertTrue(by_id[invoice_id].arithmetic_gate_passed)
            self.assertEqual(by_id[invoice_id].extracted_cells, by_id[invoice_id].numeric_cells)
        self.assertEqual(sum(item.extracted_but_wrong for item in outcomes), 0)
        self.assertEqual(by_id["31"].excluded_ground_truth_fields, ("invoice.payable",))
        self.assertEqual(by_id["31"].independent_extracted_label_comparisons, 6)
        self.assertTrue(all(not item.canonical_invoice_created for item in outcomes))

    def test_evaluation_refuses_default_bank_source_sha_before_glyph_runs(self) -> None:
        with patch(
            "image_extraction_adapter.pipeline_v0.GlyphClassifierOCR.recognize_spatial_cells",
            side_effect=AssertionError("OCR must not run after leakage is detected"),
        ):
            with self.assertRaises(TemplateLeakageError):
                self._extract("29", evaluation=True)

    def test_evaluation_refuses_hash_match_at_a_different_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pipeline-v0-leak-") as temp:
            copied = Path(temp) / "renamed-local-copy.png"
            shutil.copyfile(FIXTURES / "33.png", copied)
            data = json.loads(DEFAULT_BANK.read_text(encoding="utf-8"))
            with self.assertRaises(TemplateLeakageError):
                assert_no_template_leakage(
                    copied,
                    data["bank_metadata"]["source_images"],
                    bank_path=DEFAULT_BANK,
                    repo_root=ROOT,
                )

    def test_legacy_bank_refuses_direct_and_derived_fixture_sources(self) -> None:
        data = json.loads(LEGACY_BANK.read_text(encoding="utf-8"))
        for invoice_id in ("29", "32", "33"):
            with self.subTest(invoice=invoice_id):
                with self.assertRaises(TemplateLeakageError):
                    assert_no_template_leakage(
                        FIXTURES / f"{invoice_id}.png",
                        data["provenance"],
                        bank_path=LEGACY_BANK,
                        repo_root=ROOT,
                    )

    def test_evaluation_without_provenance_fails_closed(self) -> None:
        with self.assertRaises(TemplateProvenanceError):
            assert_no_template_leakage(FIXTURES / "29.png", (), repo_root=ROOT)

    def test_blank_and_truncated_images_are_rejected_by_layout_safety(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pipeline-v0-layout-") as temp:
            blank_path = Path(temp) / "blank.png"
            Image.new("RGB", (576, 1296), "white").save(blank_path)
            blank = extract_pipeline_v0(blank_path, templates_path=DEFAULT_BANK)
            self.assertEqual(blank.layout_status, "BLOCKED")
            self.assertEqual(blank.status, "REJECT")

            truncated_path = Path(temp) / "truncated.png"
            with Image.open(FIXTURES / "33.png") as source:
                source.load()
                source.crop((0, 0, source.width, int(source.height * 0.60))).save(truncated_path)
            truncated = extract_pipeline_v0(truncated_path, templates_path=DEFAULT_BANK)
            self.assertEqual(truncated.layout_status, "BLOCKED")
            self.assertEqual(truncated.status, "REJECT")
            self.assertIsNone(truncated.arithmetic_gate)

    def test_uncertain_layout_uses_layout_uncertain_review_without_running_glyph(self) -> None:
        uncertain = LayoutSafetyResult(
            status="REVIEW",
            reason="incomplete row geometry",
            geometry=None,
            row_count=None,
        )
        with patch(
            "image_extraction_adapter.pipeline_v0.detect_layout_safe",
            return_value=uncertain,
        ), patch(
            "image_extraction_adapter.pipeline_v0.GlyphClassifierOCR.recognize_spatial_cells",
            side_effect=AssertionError("Glyph must not run on uncertain layout"),
        ):
            result = self._extract("29")
        self.assertEqual(result.status, "REVIEW")
        self.assertIn("layout_uncertain", result.reason)
        self.assertEqual(result.attention_cells[0].field, "layout")

    def test_question_mark_cell_is_review_and_listed_for_attention(self) -> None:
        templates = build_templates_for_fold(LABELS_PATH, "33", repo_root=ROOT)
        with tempfile.TemporaryDirectory(prefix="pipeline-v0-fold33-") as temp:
            fold_bank = Path(temp) / "fold-33-templates.json"
            fold_bank.write_text(
                json.dumps(templates.to_json_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            result = extract_pipeline_v0(
                FIXTURES / "33.png",
                templates_path=fold_bank,
                evaluation=True,
            )
        cell = next(item for item in result.cell_results if item.field_name == "line.3.total")
        self.assertEqual(result.status, "REVIEW")
        self.assertIn("?", cell.raw_value)
        self.assertEqual(cell.status, "REVIEW")
        self.assertIn("line.3.total", {item.field for item in result.attention_cells})
        self.assertFalse(result.arithmetic_gate.passed)

    def test_no_context_means_no_fabricated_canonical_invoice(self) -> None:
        result = self._extract("29")
        self.assertEqual(result.status, "AUTO_CANDIDATE")
        self.assertIsNone(result.canonical_invoice)
        self.assertIsNone(result.canonical_valid)
        self.assertTrue(any("producer-supplied" in item for item in result.canonical_blockers))
        self.assertTrue(result.description_clusters)
        self.assertTrue(all(item.name_cluster_id for item in result.description_clusters))

    def test_explicit_test_context_builds_only_an_extracted_v0_candidate(self) -> None:
        context = self._canonical_context(4)
        result = self._extract(
            "29",
            canonical_context=context,
            captured_at="2026-10-22T09:30:00Z",
        )
        self.assertEqual(result.status, "AUTO_CANDIDATE")
        self.assertIsNotNone(result.canonical_invoice)
        self.assertTrue(result.canonical_valid)
        self.assertEqual(result.canonical_invoice["state"], "EXTRACTED")
        self.assertNotIn("name_cluster_id", result.canonical_invoice["line_items"][0])
        valid, errors = validate_canonical_invoice(result.canonical_invoice)
        self.assertTrue(valid, errors)
        self.assertFalse(is_issuable(result.canonical_invoice))

    def test_invalid_context_is_not_used_to_invent_required_fields(self) -> None:
        result = self._extract(
            "29",
            canonical_context={"mode": "B", "product_names": ["item"]},
        )
        self.assertIsNone(result.canonical_invoice)
        self.assertFalse(result.canonical_valid)
        self.assertEqual(result.status, "REVIEW")
        self.assertTrue(any("invoice_id" in item for item in result.canonical_blockers))

    def test_dhash_cluster_ids_match_prior_known_repeated_description_crops(self) -> None:
        pairs = (("31", 0, "32", 0), ("31", 1, "32", 3), ("31", 2, "33", 1))
        for left_id, left_row, right_id, right_row in pairs:
            with self.subTest(pair=(left_id, left_row, right_id, right_row)):
                left = self._description_crop(left_id, left_row)
                right = self._description_crop(right_id, right_row)
                left_cluster = cluster_description_crops((left,))[0]
                right_cluster = cluster_description_crops((right,))[0]
                self.assertEqual(left_cluster.name_cluster_id, right_cluster.name_cluster_id)
                self.assertEqual(left_cluster.cluster_size, 1)

    def _description_crop(self, invoice_id: str, row_index: int):
        with Image.open(FIXTURES / f"{invoice_id}.png") as opened:
            opened.load()
            image = opened.convert("RGB")
        safety = detect_layout_safe(image)
        spatial = SimpleNamespace(
            column_boundaries=safety.geometry.column_boundaries,
            row_bands=safety.geometry.row_bands,
            assessments=(),
        )
        crops = crop_spatial_cells(
            image,
            spatial,
            include_descriptions=True,
            include_payable=False,
        )
        expected = f"line.{row_index}.description"
        return next(crop for crop in crops if crop.field_name == expected)

    def test_operator_corrections_rerun_gate_and_never_mutate_template_bank(self) -> None:
        original_bank = DEFAULT_BANK.read_bytes()
        result = self._extract("29")
        wrong = apply_operator_correction(result, {"line.0.total": "۱,۴۵۰,۰۰۱"})
        self.assertEqual(wrong.status, "REVIEW")
        self.assertFalse(wrong.arithmetic_gate.passed)
        self.assertFalse(wrong.bank_update_eligible)
        self.assertFalse(wrong.template_bank_updated)
        self.assertIn("line.0.total", wrong.operator_confirmed_fields)
        self.assertEqual(wrong.operator_original_values, (("line.0.total", "۱,۴۵۰,۰۰۰"),))
        self.assertEqual(wrong.operator_confirmed_values, (("line.0.total", "۱,۴۵۰,۰۰۱"),))

        corrected = apply_operator_correction(result, {"line.0.total": "۱,۴۵۰,۰۰۰"})
        self.assertEqual(corrected.status, "AUTO_CANDIDATE")
        self.assertTrue(corrected.arithmetic_gate.passed)
        self.assertTrue(corrected.bank_update_eligible)
        self.assertFalse(corrected.template_bank_updated)
        self.assertEqual(corrected.operator_confirmed_values, (("line.0.total", "۱,۴۵۰,۰۰۰"),))
        self.assertEqual(corrected.operator_original_values, (("line.0.total", "۱,۴۵۰,۰۰۰"),))
        self.assertEqual(DEFAULT_BANK.read_bytes(), original_bank)

    def test_operator_correction_rejects_decimals_and_unknown_fields(self) -> None:
        result = self._extract("29")
        decimal = apply_operator_correction(result, {"line.0.total": "1,450.75"})
        self.assertEqual(decimal.status, "REVIEW")
        self.assertFalse(decimal.arithmetic_gate.passed)
        self.assertFalse(decimal.bank_update_eligible)
        unknown = apply_operator_correction(result, {"line.88.total": "۱,۰۰۰"})
        self.assertEqual(unknown.status, "REVIEW")
        self.assertFalse(unknown.bank_update_eligible)
        self.assertTrue(any(item.field == "line.88.total" for item in unknown.attention_cells))

    def test_integer_rial_converter_is_strict_and_decimal_free(self) -> None:
        self.assertEqual(to_rials("۱,۲۳۴"), 1234)
        self.assertEqual(to_rials("۰"), 0)
        self.assertIsNone(to_rials("۱,۲۳۴.۵"))
        self.assertIsNone(to_rials("-۱۲۳"))
        self.assertIsNone(to_rials("١٢٣"))


if __name__ == "__main__":
    unittest.main()
