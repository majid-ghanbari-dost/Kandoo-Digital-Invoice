from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for import_path in (ROOT / "src", ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from image_extraction_adapter.layout_profiles import (  # noqa: E402
    ProfileCell,
    evaluate_profile_row,
    load_layout_profile_registry,
)
from image_extraction_adapter.pipeline_v0 import (  # noqa: E402
    DEFAULT_TEMPLATE_BANK_PATH,
    extract_pipeline_v0,
)
from scripts.run_e24_layout_profiles import build_e24_report  # noqa: E402

REAL_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "real"
HOLO_GOLDEN_DIR = REAL_FIXTURE_DIR / "e24-holo-profile"
HOLO_GOLDEN_SHA256 = {
    "29": "0f2810f8aadf9b1e55994db91aefbdf7218a3382ed336019244626e7fa888b31",
    "31": "e66f3455c660848013db8ebf88be7c3c2bdd2ef65ab5675fc955df83b5d4c69c",
    "32": "342dc7223fcb7ce47b1d13fa1f1ebe2bfa1946ef7dc3522a33b9ee8292b89e51",
    "33": "8466d15909aae930ddb849a02ef1e6c3efdff095b731c843c44b70cff53c4502",
}


def _stable_holo_pipeline_bytes(fixture_id: str) -> bytes:
    result = extract_pipeline_v0(
        REAL_FIXTURE_DIR / f"{fixture_id}.png",
        templates_path=DEFAULT_TEMPLATE_BANK_PATH,
    )
    document = result.to_dict()
    # The golden normalizes this environment-specific absolute path only;
    # every other byte of the existing Holo/Glyph pipeline result is retained.
    document["template_provenance"]["template_bank_path"] = "src/templates_bank_default.json"
    serialized = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    return serialized.encode("utf-8")


class E24LayoutProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_layout_profile_registry()

    def test_registry_is_versioned_and_declares_exact_column_roles_and_order(self) -> None:
        self.assertEqual(cls_version := self.registry.schema_version,
                         "e24.layout-profile-registry.v1")
        self.assertTrue(cls_version)
        holo = self.registry.get("holo-rtl-four-column-v1")
        self.assertIsNotNone(holo)
        self.assertEqual(
            holo.column_roles,
            ("line_total", "quantity", "description", "row_number"),
        )
        self.assertIsNone(holo.line_total_unit_price_role)
        discounted = self.registry.get("synthetic-rtl-unit-discount-v1")
        self.assertEqual(
            discounted.column_roles,
            (
                "line_total",
                "discounted_price",
                "discount_percent",
                "unit_price",
                "quantity",
                "description",
                "row_number",
            ),
        )
        self.assertEqual(discounted.line_total_unit_price_role, "discounted_price")

    def test_holo_profile_without_per_unit_role_reviews_instead_of_dividing_total(self) -> None:
        result = evaluate_profile_row(
            "holo-rtl-four-column-v1",
            ["2400", "2", "Synthetic Holo row", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(result.status, "REVIEW")
        self.assertEqual(result.reason_code, "UNIT_PRICE_ROLE_UNDECLARED")
        self.assertNotIn("unit_price", result.witnesses)

    def test_unknown_layout_id_and_reordered_roles_fail_closed(self) -> None:
        unknown = evaluate_profile_row(
            "unregistered-layout-v99",
            ["1000", "1000", "1", "Synthetic", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(unknown.status, "REVIEW")
        self.assertEqual(unknown.reason_code, "UNKNOWN_LAYOUT_PROFILE")

        profile = self.registry.get("synthetic-rtl-unit-price-v1")
        wrong_order = evaluate_profile_row(
            profile.profile_id,
            ["1000", "1000", "1", "Synthetic", "1"],
            currency_unit="rial",
            observed_column_roles=("unit_price", "line_total", "quantity", "description", "row_number"),
            registry=self.registry,
        )
        self.assertEqual(wrong_order.status, "REVIEW")
        self.assertEqual(wrong_order.reason_code, "COLUMN_ORDER_MISMATCH")

    def test_exact_quantity_price_witness_and_two_line_description(self) -> None:
        result = evaluate_profile_row(
            "synthetic-rtl-unit-price-v1",
            ["2400", "1200", "2", ["Synthetic item", "second line"], "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(result.status, "EXTRACTED")
        self.assertEqual(result.fields["description_lines"], ["Synthetic item", "second line"])
        self.assertEqual(result.fields["description"], "Synthetic item\nsecond line")
        self.assertEqual(result.witnesses["quantity_x_unit_price_equals_line_total"]["expected_line_total"], 2400)
        self.assertTrue(result.witnesses["quantity_x_unit_price_equals_line_total"]["passed"])

        mismatch = evaluate_profile_row(
            "synthetic-rtl-unit-price-v1",
            ["2401", "1200", "2", "Synthetic item", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(mismatch.status, "REVIEW")
        self.assertEqual(mismatch.reason_code, "LINE_TOTAL_WITNESS_FAILED")
        self.assertFalse(mismatch.witnesses["quantity_x_unit_price_equals_line_total"]["passed"])

    def test_discounted_price_and_discount_percent_are_explicit_exact_witnesses(self) -> None:
        result = evaluate_profile_row(
            "synthetic-rtl-unit-discount-v1",
            ["1800", "900", "10", "1000", "2", "Synthetic discounted item", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(result.status, "EXTRACTED")
        self.assertEqual(result.fields["line_total_unit_price_role"], "discounted_price")
        self.assertTrue(result.witnesses["discount_percent"]["passed"])
        self.assertTrue(result.witnesses["quantity_x_unit_price_equals_line_total"]["passed"])

        bad_discount = evaluate_profile_row(
            "synthetic-rtl-unit-discount-v1",
            ["1800", "950", "10", "1000", "2", "Synthetic mismatch", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(bad_discount.status, "REVIEW")
        self.assertEqual(bad_discount.reason_code, "DISCOUNT_WITNESS_FAILED")
        self.assertFalse(bad_discount.witnesses["discount_percent"]["passed"])

        # Discount details are optional as a group; with no pre-discount price
        # or percent, the explicitly declared discounted_price remains the sole
        # per-unit witness and is not reconstructed from the line total.
        optional_discount = evaluate_profile_row(
            "synthetic-rtl-unit-discount-v1",
            ["1800", "900", None, None, "2", "Synthetic discounted item", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(optional_discount.status, "EXTRACTED")
        self.assertIsNone(optional_discount.fields["unit_price"])
        self.assertIsNone(optional_discount.fields["discount_percent"])

        incomplete_discount = evaluate_profile_row(
            "synthetic-rtl-unit-discount-v1",
            ["1800", "900", "10", None, "2", "Synthetic incomplete item", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(incomplete_discount.status, "REVIEW")
        self.assertEqual(incomplete_discount.reason_code, "DISCOUNT_EVIDENCE_INCOMPLETE")

        crossed_out_discount_input = evaluate_profile_row(
            "synthetic-rtl-unit-discount-v1",
            [
                "1800",
                "900",
                "10",
                ProfileCell("1000", crossed_out=True),
                "2",
                "Synthetic crossed-out unit price",
                "1",
            ],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(crossed_out_discount_input.status, "REVIEW")
        self.assertEqual(
            crossed_out_discount_input.reason_code,
            "DISCOUNT_INPUT_CROSSED_OUT",
        )

    def test_crossed_out_consumer_price_is_not_used_as_the_unit_price_witness(self) -> None:
        result = evaluate_profile_row(
            "synthetic-rtl-crossed-consumer-price-v1",
            [
                "1800",
                ProfileCell("2500", crossed_out=True),
                "900",
                "2",
                "Synthetic product",
                "1",
            ],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(result.status, "EXTRACTED")
        self.assertEqual(result.fields["consumer_price"], "2500")
        self.assertTrue(result.fields["consumer_price_crossed_out"])
        self.assertEqual(result.fields["line_total_unit_price_role"], "unit_price")

        crossed_witness = evaluate_profile_row(
            "synthetic-rtl-unit-price-v1",
            ["1800", ProfileCell("900", crossed_out=True), "2", "Synthetic product", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(crossed_witness.status, "REVIEW")
        self.assertEqual(crossed_witness.reason_code, "WITNESS_PRICE_CROSSED_OUT")

    def test_extra_columns_and_missing_currency_setting_review_without_guessing(self) -> None:
        profile = self.registry.get("synthetic-rtl-unit-price-v1")
        extra = evaluate_profile_row(
            profile.profile_id,
            ["1800", "900", "2", "Synthetic product", "1", "UNDECLARED"],
            currency_unit="rial",
            observed_column_roles=profile.column_roles + ("unknown_extra",),
            registry=self.registry,
        )
        self.assertEqual(extra.status, "REVIEW")
        self.assertEqual(extra.reason_code, "COLUMN_ORDER_MISMATCH")

        missing_unit = evaluate_profile_row(
            profile.profile_id,
            ["3000", "1500", "2", "Synthetic toman item", "1"],
            currency_unit=None,
            registry=self.registry,
        )
        self.assertEqual(missing_unit.status, "REVIEW")
        self.assertEqual(missing_unit.reason_code, "CURRENCY_UNIT_UNCONFIRMED")

        malformed_unit = evaluate_profile_row(
            profile.profile_id,
            ["3000", "1500", "2", "Synthetic item", "1"],
            currency_unit=["rial"],
            registry=self.registry,
        )
        self.assertEqual(malformed_unit.status, "REVIEW")
        self.assertEqual(malformed_unit.reason_code, "CURRENCY_UNIT_UNSUPPORTED")

        malformed_grouping = evaluate_profile_row(
            profile.profile_id,
            ["1,20,0", "600", "2", "Synthetic item", "1"],
            currency_unit="rial",
            registry=self.registry,
        )
        self.assertEqual(malformed_grouping.status, "REVIEW")
        self.assertEqual(malformed_grouping.reason_code, "CELL_VALUE_INVALID")

    def test_rial_and_toman_are_explicit_units_and_are_never_converted(self) -> None:
        profile_id = "synthetic-rtl-unit-price-v1"
        values = ["3000", "1500", "2", "Synthetic item", "1"]
        rial = evaluate_profile_row(
            profile_id, values, currency_unit="rial", registry=self.registry)
        toman = evaluate_profile_row(
            profile_id, values, currency_unit="toman", registry=self.registry)
        self.assertEqual(rial.status, "EXTRACTED")
        self.assertEqual(toman.status, "EXTRACTED")
        self.assertEqual(rial.fields["line_total"], toman.fields["line_total"])
        self.assertEqual(rial.fields["unit_price"], toman.fields["unit_price"])
        self.assertEqual(rial.fields["currency_unit"], "rial")
        self.assertEqual(toman.fields["currency_unit"], "toman")

    def test_legacy_holo_pipeline_output_is_byte_identical_on_four_real_fixtures(self) -> None:
        fixture_ids = ("29", "31", "32", "33")
        for fixture_id in fixture_ids:
            with self.subTest(fixture_id=fixture_id):
                expected_path = HOLO_GOLDEN_DIR / f"pipeline-v0-{fixture_id}.golden.json"
                expected = expected_path.read_bytes()
                self.assertEqual(
                    hashlib.sha256(expected).hexdigest(),
                    HOLO_GOLDEN_SHA256[fixture_id],
                )
                actual = _stable_holo_pipeline_bytes(fixture_id)
                self.assertEqual(actual, expected)

    def test_synthetic_report_is_fail_closed_and_deterministic(self) -> None:
        first = build_e24_report()
        second = build_e24_report()
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "PASS")
        self.assertTrue(first["synthetic_only"])
        self.assertEqual(first["images_loaded"], 0)
        self.assertFalse(first["network_or_ocr_used"])
        self.assertEqual(first["aggregate"]["sample_count"], 11)
        self.assertEqual(first["aggregate"]["safe_profile_witness_or_review_count"], 11)
        self.assertEqual(first["aggregate"]["extracted_but_wrong"], 0)
        self.assertTrue(all(case["safe_outcome"] for case in first["variants"]))


if __name__ == "__main__":
    unittest.main()
