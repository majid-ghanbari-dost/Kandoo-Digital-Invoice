from __future__ import annotations

import copy
import json
import unittest
from jsonschema import Draft202012Validator

from image_extraction_adapter.canonical_invoice import (
    POST_ISSUANCE_STATES,
    _SCHEMA_PATH,
    compute_issued_content_sha256,
    get_provenance_label,
    is_issuable,
    is_valid_transition,
    validate_canonical_invoice,
)


TRANSITION_PATHS = {
    "DRAFT": (),
    "EXTRACTED": (("DRAFT", "EXTRACTED"),),
    "VALIDATED": (("DRAFT", "EXTRACTED"), ("EXTRACTED", "VALIDATED")),
    "ISSUED": (
        ("DRAFT", "EXTRACTED"),
        ("EXTRACTED", "VALIDATED"),
        ("VALIDATED", "ISSUED"),
    ),
    "REVOKED": (
        ("DRAFT", "EXTRACTED"),
        ("EXTRACTED", "VALIDATED"),
        ("VALIDATED", "ISSUED"),
        ("ISSUED", "REVOKED"),
    ),
    "SUPERSEDED": (
        ("DRAFT", "EXTRACTED"),
        ("EXTRACTED", "VALIDATED"),
        ("VALIDATED", "ISSUED"),
        ("ISSUED", "SUPERSEDED"),
    ),
}


def make_invoice(
    *,
    mode: str = "B",
    state: str = "EXTRACTED",
    phone_status: str = "claimed",
    attention_cells: list[dict[str, str]] | None = None,
) -> dict:
    """Create a complete synthetic contract fixture; no production data."""
    is_native = mode == "A"
    header = {
        "captured_at": "2026-10-22T09:30:00Z",
        "printed_date": None,
        "printed_time": None,
        "invoice_number": None if is_native else "POS-0042",
    }
    item_provenance = {
        "product_name": "native" if is_native else "captured",
        "quantity": "native" if is_native else "captured",
        "unit_price": "native" if is_native else "derived",
        "line_total": "native" if is_native else "captured",
    }
    summary_provenance = "native" if is_native else "captured"
    customer_phone_provenance = "native" if is_native else "captured"
    fields = {
        "invoice_id": "native",
        "display_number": "native",
        "operation_id": "native",
        "device_id": "native",
        "public_token": "native",
        "store_id": "native",
        "customer": {"phone": customer_phone_provenance, "phone_status": "native"},
        "line_items": [copy.deepcopy(item_provenance)],
        "summary": {
            "subtotal": summary_provenance,
            "extra_amounts": {"tax": summary_provenance},
            "payable": summary_provenance,
        },
        "header": {
            "captured_at": "derived",
            "printed_date": "unavailable",
            "printed_time": "unavailable",
            "invoice_number": "unavailable" if is_native else "untrusted",
        },
    }
    data = {
        "schema_version": "0",
        "mode": mode,
        "invoice_id": f"inv-{mode.lower()}-0007",
        "display_number": "2026-000007",
        "operation_id": "op-create-0007",
        "device_id": "device-01",
        "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
        "store_id": "store-01",
        "customer": {"phone": "+15551234567", "phone_status": phone_status},
        "state": state,
        "state_history": [
            {
                "from_state": from_state,
                "to_state": to_state,
                "operation_id": f"op-transition-{index + 1}",
                "device_id": "device-01",
            }
            for index, (from_state, to_state) in enumerate(TRANSITION_PATHS[state])
        ],
        "line_items": [
            {
                "product_name": "Synthetic Widget",
                "quantity": 2,
                "unit_price": 500,
                "line_total": 1000,
            }
        ],
        "summary": {
            "subtotal": 1000,
            "extra_amounts": {"tax": 80},
            "payable": 1080,
        },
        "attention_cells": copy.deepcopy(attention_cells or []),
        "header": header,
        "provenance": {
            "image_sha256": None if is_native else "a" * 64,
            "template_library_id": None if is_native else "synthetic-template-v0",
            "engine_version": None if is_native else "synthetic-engine-0.1",
            "fields": fields,
        },
    }
    if state in POST_ISSUANCE_STATES:
        data["issued_content_sha256"] = compute_issued_content_sha256(data)
    return data


class CanonicalInvoiceV0Tests(unittest.TestCase):
    def test_schema_is_valid_draft_2020_12(self):
        with _SCHEMA_PATH.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        Draft202012Validator.check_schema(schema)

    def test_valid_examples_for_modes_a_and_b(self):
        for mode in ("A", "B"):
            with self.subTest(mode=mode):
                invoice = make_invoice(mode=mode, state="EXTRACTED")
                valid, errors = validate_canonical_invoice(invoice)
                self.assertTrue(valid, errors)
                self.assertEqual(invoice["mode"], mode)

    def test_valid_issued_example_and_is_issuable(self):
        invoice = make_invoice(state="ISSUED", phone_status="verified")
        valid, errors = validate_canonical_invoice(invoice)
        self.assertTrue(valid, errors)
        self.assertTrue(is_issuable(invoice))
        self.assertEqual(len(invoice["issued_content_sha256"]), 64)

    def test_valid_claimed_customer_remains_issuable(self):
        invoice = make_invoice(state="ISSUED", phone_status="claimed")
        self.assertTrue(validate_canonical_invoice(invoice)[0])
        self.assertTrue(is_issuable(invoice))

    def test_unit_price_can_be_derived_or_printed(self):
        derived = make_invoice(mode="B")
        self.assertEqual(
            derived["provenance"]["fields"]["line_items"][0]["unit_price"],
            "derived",
        )
        self.assertTrue(validate_canonical_invoice(derived)[0])

        printed = make_invoice(mode="B")
        printed["provenance"]["fields"]["line_items"][0]["unit_price"] = "captured"
        self.assertTrue(validate_canonical_invoice(printed)[0])

        missing_origin = make_invoice(mode="B")
        missing_origin["provenance"]["fields"]["line_items"][0]["unit_price"] = "untrusted"
        valid, errors = validate_canonical_invoice(missing_origin)
        self.assertFalse(valid)
        self.assertTrue(any("unit_price" in error for error in errors))

    def test_header_provenance_and_optional_printed_fields(self):
        invoice = make_invoice(state="ISSUED")
        header = invoice["header"]
        labels = invoice["provenance"]["fields"]["header"]
        self.assertEqual(header["captured_at"], "2026-10-22T09:30:00Z")
        self.assertEqual(labels["captured_at"], "derived")
        self.assertIsNone(header["printed_date"])
        self.assertEqual(labels["printed_date"], "unavailable")
        self.assertEqual(header["invoice_number"], "POS-0042")
        self.assertEqual(labels["invoice_number"], "untrusted")
        self.assertTrue(validate_canonical_invoice(invoice)[0])

    def test_header_value_and_provenance_must_agree(self):
        invoice = make_invoice()
        invoice["provenance"]["fields"]["header"]["captured_at"] = "captured"
        valid, errors = validate_canonical_invoice(invoice)
        self.assertFalse(valid)
        self.assertTrue(any("captured_at" in error for error in errors))

        invoice = make_invoice()
        invoice["header"]["printed_date"] = "2026-10-21"
        valid, errors = validate_canonical_invoice(invoice)
        self.assertFalse(valid)
        self.assertTrue(any("printed_date" in error for error in errors))

    def test_probe_timestamp_must_be_offset_aware(self):
        invoice = make_invoice()
        invoice["header"]["captured_at"] = "2026-10-22T09:30:00"
        valid, errors = validate_canonical_invoice(invoice)
        self.assertFalse(valid)
        self.assertTrue(any("UTC offset" in error for error in errors))

    def test_attention_cells_are_valid_before_validation_but_block_issue(self):
        attention = [
            {
                "field": "line.0.product_name",
                "raw_value": "Synthetic Widge?",
                "reason": "operator confirmation required",
            }
        ]
        extracted = make_invoice(state="EXTRACTED", attention_cells=attention)
        self.assertTrue(validate_canonical_invoice(extracted)[0])
        self.assertFalse(is_issuable(extracted))

        validated = make_invoice(state="VALIDATED", attention_cells=attention)
        valid, errors = validate_canonical_invoice(validated)
        self.assertFalse(valid)
        self.assertTrue(any("attention_cells" in error for error in errors))

    def test_all_six_states_and_terminal_transitions(self):
        for state in TRANSITION_PATHS:
            with self.subTest(state=state):
                invoice = make_invoice(state=state)
                valid, errors = validate_canonical_invoice(invoice)
                self.assertTrue(valid, errors)
                self.assertEqual(invoice["state"], state)
                self.assertEqual(
                    invoice["state_history"][-1]["to_state"] if invoice["state_history"] else "DRAFT",
                    state,
                )
                if state != "ISSUED":
                    self.assertFalse(is_issuable(invoice))

        self.assertTrue(is_valid_transition("ISSUED", "REVOKED"))
        self.assertTrue(is_valid_transition("ISSUED", "SUPERSEDED"))
        self.assertFalse(is_valid_transition("DRAFT", "ISSUED"))
        self.assertFalse(is_valid_transition("REVOKED", "SUPERSEDED"))
        self.assertFalse(is_valid_transition("SUPERSEDED", "ISSUED"))

    def test_invalid_direct_or_discontinuous_transition_history(self):
        direct = make_invoice(state="ISSUED")
        direct["state_history"] = [
            {
                "from_state": "DRAFT",
                "to_state": "ISSUED",
                "operation_id": "op-direct",
                "device_id": "device-01",
            }
        ]
        valid, errors = validate_canonical_invoice(direct)
        self.assertFalse(valid)
        self.assertTrue(any("not allowed" in error for error in errors))

        discontinuous = make_invoice(state="VALIDATED")
        discontinuous["state_history"][1]["from_state"] = "DRAFT"
        valid, errors = validate_canonical_invoice(discontinuous)
        self.assertFalse(valid)
        self.assertTrue(any("contiguous history" in error for error in errors))

    def test_issued_content_mutations_fail_immutability_validation(self):
        base = make_invoice(state="ISSUED")
        self.assertTrue(validate_canonical_invoice(base)[0])
        mutations = (
            lambda invoice: invoice["line_items"][0].__setitem__("line_total", 999),
            lambda invoice: invoice["summary"].__setitem__("payable", 1079),
            lambda invoice: invoice["customer"].__setitem__("phone", "+15550000000"),
            lambda invoice: invoice["provenance"]["fields"]["header"].__setitem__(
                "invoice_number", "unavailable"
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                changed = copy.deepcopy(base)
                mutate(changed)
                valid, errors = validate_canonical_invoice(changed)
                self.assertFalse(valid)
                self.assertTrue(any("issued_content_sha256" in error for error in errors))
                self.assertFalse(is_issuable(changed))

    def test_issued_fingerprint_is_stable_across_state_history_only_changes(self):
        issued = make_invoice(state="ISSUED")
        revoked = make_invoice(state="REVOKED")
        self.assertEqual(
            issued["issued_content_sha256"], revoked["issued_content_sha256"]
        )
        self.assertTrue(validate_canonical_invoice(revoked)[0])
        self.assertFalse(is_issuable(revoked))

    def test_digest_is_deterministic_and_uses_utf8_content(self):
        invoice = make_invoice(mode="B")
        invoice["line_items"][0]["product_name"] = "کالای نمونه"
        first = compute_issued_content_sha256(invoice)
        second = compute_issued_content_sha256(copy.deepcopy(invoice))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_issued_digest_known_answer(self):
        invoice = make_invoice(state="ISSUED")
        self.assertEqual(
            invoice["issued_content_sha256"],
            "89a1c7ae619eb9d40c118754a5798fc8ab78c9599aba9b8fde2538ff6c0bd45f",
        )

    def test_floating_point_and_boolean_amounts_are_rejected(self):
        for path, value in (
            (("summary", "payable"), 1080.5),
            (("line_items", 0, "unit_price"), 500.0),
            (("summary", "subtotal"), True),
        ):
            with self.subTest(path=path):
                invoice = make_invoice()
                target = invoice
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                valid, errors = validate_canonical_invoice(invoice)
                self.assertFalse(valid)
                self.assertTrue(errors)

    def test_negative_amount_and_fractional_quantity_are_rejected(self):
        for path, value in (
            (("summary", "subtotal"), -1),
            (("summary", "extra_amounts", "tax"), -1),
            (("line_items", 0, "quantity"), 1.5),
            (("line_items", 0, "quantity"), 0),
        ):
            with self.subTest(path=path):
                invoice = make_invoice()
                target = invoice
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                self.assertFalse(validate_canonical_invoice(invoice)[0])

    def test_missing_required_fields_are_rejected(self):
        required = (
            "schema_version",
            "mode",
            "invoice_id",
            "display_number",
            "operation_id",
            "device_id",
            "public_token",
            "store_id",
            "customer",
            "state",
            "state_history",
            "line_items",
            "summary",
            "attention_cells",
            "header",
            "provenance",
        )
        for field_name in required:
            with self.subTest(field=field_name):
                invoice = make_invoice()
                del invoice[field_name]
                self.assertFalse(validate_canonical_invoice(invoice)[0])

        invoice = make_invoice()
        del invoice["customer"]["phone"]
        self.assertFalse(validate_canonical_invoice(invoice)[0])

        invoice = make_invoice()
        del invoice["line_items"][0]["line_total"]
        self.assertFalse(validate_canonical_invoice(invoice)[0])

    def test_invalid_phone_status_and_provenance_are_rejected(self):
        invoice = make_invoice()
        invoice["customer"]["phone_status"] = "UNKNOWN"
        self.assertFalse(validate_canonical_invoice(invoice)[0])

        invoice = make_invoice()
        invoice["provenance"]["fields"]["line_items"][0]["quantity"] = "missing"
        self.assertFalse(validate_canonical_invoice(invoice)[0])

    def test_provenance_mirrors_line_items_and_extra_amounts(self):
        invoice = make_invoice()
        invoice["provenance"]["fields"]["line_items"] = []
        valid, errors = validate_canonical_invoice(invoice)
        self.assertFalse(valid)
        self.assertTrue(any("one provenance record" in error for error in errors))

        invoice = make_invoice()
        invoice["provenance"]["fields"]["summary"]["extra_amounts"] = {}
        valid, errors = validate_canonical_invoice(invoice)
        self.assertFalse(valid)
        self.assertTrue(any("keys must match" in error for error in errors))

    def test_no_arithmetic_repair_or_implicit_reconciliation(self):
        invoice = make_invoice()
        invoice["summary"]["payable"] = 1234
        before = copy.deepcopy(invoice)
        self.assertTrue(validate_canonical_invoice(invoice)[0])
        self.assertEqual(invoice, before)

    def test_provenance_policy_helper(self):
        self.assertEqual(get_provenance_label("invoice_id"), "native")
        self.assertEqual(get_provenance_label("line.3.unit_price"), "derived")
        self.assertEqual(get_provenance_label("unit_price"), "derived")
        self.assertEqual(get_provenance_label("header.captured_at"), "derived")
        self.assertEqual(get_provenance_label("invoice_number"), "untrusted")
        self.assertEqual(get_provenance_label("customer.phone"), "captured")
        self.assertEqual(get_provenance_label("unknown.field"), "unavailable")

    def test_malformed_nested_types_are_rejected_without_crashing(self):
        malformed_values = []
        invoice = make_invoice()
        invoice["state"] = []
        malformed_values.append(invoice)

        invoice = make_invoice()
        invoice["header"]["captured_at"] = 123
        malformed_values.append(invoice)

        invoice = make_invoice()
        invoice["state_history"][0]["to_state"] = []
        malformed_values.append(invoice)

        invoice = make_invoice()
        invoice["provenance"]["fields"]["line_items"][0]["unit_price"] = []
        malformed_values.append(invoice)

        for malformed in malformed_values:
            with self.subTest(invoice=malformed):
                valid, errors = validate_canonical_invoice(malformed)
                self.assertFalse(valid)
                self.assertTrue(errors)

    def test_unknown_properties_and_short_public_tokens_are_rejected(self):
        invoice = make_invoice()
        invoice["unexpected"] = "not part of v0"
        self.assertFalse(validate_canonical_invoice(invoice)[0])

        invoice = make_invoice()
        invoice["public_token"] = "too-short"
        self.assertFalse(validate_canonical_invoice(invoice)[0])


if __name__ == "__main__":
    unittest.main()
