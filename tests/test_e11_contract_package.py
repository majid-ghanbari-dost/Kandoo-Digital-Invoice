from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest
from typing import Any

from jsonschema import Draft202012Validator

from image_extraction_adapter.canonical_invoice import (
    _canonical_json_bytes,
    _scan_for_floats,
    compute_issued_content_sha256,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = REPO_ROOT / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "canonical_invoice_v0.schema.json"
MANIFEST_PATH = CONTRACTS_DIR / "goldens" / "manifest.json"
POST_ISSUE_STATES = {"ISSUED", "REVOKED", "SUPERSEDED"}
PRE_ISSUE_STATES = {"DRAFT", "EXTRACTED", "VALIDATED"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ref_values(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref":
                yield child
            yield from _ref_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _ref_values(child)


def _verdict_and_failure(
    invoice: dict[str, Any], validator: Draft202012Validator
) -> tuple[str, str | None]:
    if _scan_for_floats(invoice):
        return "INVALID", "FLOATING_POINT_NOT_ALLOWED"
    schema_errors = list(validator.iter_errors(invoice))
    if schema_errors:
        if (
            invoice.get("state") in PRE_ISSUE_STATES
            and invoice.get("display_number") is not None
        ):
            return "INVALID", "DISPLAY_NUMBER_BEFORE_ISSUE"
        items = invoice.get("line_items", [])
        if items and type(items[0].get("quantity_millis")) is not int:
            return "INVALID", "QUANTITY_MILLIS_NOT_INTEGER"
        return "INVALID", "SCHEMA_VALIDATION_FAILED"

    state = invoice.get("state")
    if state in POST_ISSUE_STATES:
        if invoice.get("issued_content_sha256") != compute_issued_content_sha256(invoice):
            return "INVALID", "ISSUED_CONTENT_HASH_MISMATCH"
    return "VALID", None


class E11ContractPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = _load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)
        cls.manifest = _load_json(MANIFEST_PATH)

    def test_schema_is_versioned_and_has_no_external_refs(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["x-contract-version"], "v0")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0")
        self.assertTrue(
            all(ref.startswith("#") for ref in _ref_values(self.schema)),
            "all schema $refs must resolve within the published file",
        )

    def test_quantity_millis_is_a_signed_integer_encoding(self) -> None:
        quantity_schema = self.schema["properties"]["line_items"]["items"]["properties"][
            "quantity_millis"
        ]
        self.assertEqual(quantity_schema["type"], "integer")
        self.assertNotIn("minimum", quantity_schema)
        self.assertNotIn("maximum", quantity_schema)

        draft = _load_json(
            CONTRACTS_DIR / "goldens" / "valid" / "draft_mode_b_null_display_number.json"
        )
        for value in (-1250, 0, 1250):
            candidate = json.loads(json.dumps(draft))
            candidate["line_items"][0]["quantity_millis"] = value
            self.assertEqual(list(self.validator.iter_errors(candidate)), [], value)

        # JSON Schema's abstract numeric model can treat 1250.0 as an integer;
        # the reused E-01 semantic float guard rejects that lexical/value form.
        floating = json.loads(json.dumps(draft))
        floating["line_items"][0]["quantity_millis"] = 1250.0
        self.assertEqual(list(self.validator.iter_errors(floating)), [])
        self.assertEqual(
            _verdict_and_failure(floating, self.validator),
            ("INVALID", "FLOATING_POINT_NOT_ALLOWED"),
        )

    def test_goldens_are_byte_stable_and_match_manifest_verdicts(self) -> None:
        entries = self.manifest["goldens"]
        self.assertEqual(self.manifest["contract_version"], "v0")
        self.assertEqual(
            self.manifest["counts"],
            {
                "valid": sum(entry["expected_verdict"] == "VALID" for entry in entries),
                "invalid": sum(entry["expected_verdict"] == "INVALID" for entry in entries),
            },
        )

        for entry in entries:
            with self.subTest(path=entry["path"]):
                path = CONTRACTS_DIR / "goldens" / entry["path"]
                raw = path.read_bytes()
                self.assertTrue(raw.endswith(b"\n"))
                instance = json.loads(raw.decode("utf-8"))
                self.assertEqual(raw, _canonical_json_bytes(instance) + b"\n")
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["file_sha256"])

                verdict, failure = _verdict_and_failure(instance, self.validator)
                self.assertEqual(verdict, entry["expected_verdict"])
                self.assertEqual(failure, entry["expected_failure_code"])

                if instance["state"] in POST_ISSUE_STATES:
                    expected_hash = compute_issued_content_sha256(instance)
                    self.assertEqual(expected_hash, entry["expected_issued_content_sha256"])
                    if verdict == "VALID":
                        self.assertEqual(instance["issued_content_sha256"], expected_hash)
                    else:
                        self.assertNotEqual(instance["issued_content_sha256"], expected_hash)
                else:
                    self.assertIsNone(entry["expected_issued_content_sha256"])

    def test_hash_mismatch_golden_is_schema_valid_but_rejected(self) -> None:
        entry = next(
            item
            for item in self.manifest["goldens"]
            if item["expected_failure_code"] == "ISSUED_CONTENT_HASH_MISMATCH"
        )
        instance = _load_json(CONTRACTS_DIR / "goldens" / entry["path"])
        self.assertEqual(list(self.validator.iter_errors(instance)), [])
        self.assertEqual(
            _verdict_and_failure(instance, self.validator),
            ("INVALID", "ISSUED_CONTENT_HASH_MISMATCH"),
        )


if __name__ == "__main__":
    unittest.main()
