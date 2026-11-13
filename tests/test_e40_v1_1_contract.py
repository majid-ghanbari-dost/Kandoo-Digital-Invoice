from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from cloud_contract.v1_1 import (
    LEGACY_INVOICE_SCHEMA_VERSION,
    V1_1_INVOICE_FIELDS,
    V1_1_INVOICE_SCHEMA_VERSION,
    InvoiceV1_1ValidationError,
    preflight_v1_1_batch,
    validate_issued_invoice,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "docs" / "schemas" / "v1-1"
ISSUED_SCHEMA_PATH = SCHEMA_DIR / "issued-invoice-v1-1.schema.json"
PUBLIC_SCHEMA_PATH = SCHEMA_DIR / "public-invoice-view-v1-1.schema.json"
EXPECTED_SCHEMAS = {
    ISSUED_SCHEMA_PATH: (
        2011,
        "04af72824d15bd17d01a98604265c39bf8d5d5da8ed11d406fe74a28bd5ad15c",
    ),
    PUBLIC_SCHEMA_PATH: (
        2174,
        "78620a233199dbe191e9c9cf4264a0080aaba744a53e2a820056bf98f4992650",
    ),
}


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _invoice(**fields):
    return {"invoice_schema_version": "1.1", **fields}


def _entry(invoice: dict) -> dict:
    return {
        "entry_hash": "synthetic-hash-is-not-recomputed-by-this-helper",
        "response_snapshot": {
            "operation_seq": 1,
            "status": "SUCCEEDED",
            "result_status": "SUCCEEDED",
            "response": {"invoice": invoice},
        },
    }


def _without_descriptions(value):
    if isinstance(value, dict):
        return {
            key: _without_descriptions(child)
            for key, child in value.items()
            if key != "description"
        }
    if isinstance(value, list):
        return [_without_descriptions(child) for child in value]
    return value


def test_courier_schemas_are_byte_pinned_and_valid_draft_2020_12():
    for path, (expected_size, expected_sha256) in EXPECTED_SCHEMAS.items():
        raw = path.read_bytes()
        assert len(raw) == expected_size
        assert hashlib.sha256(raw).hexdigest() == expected_sha256
        schema = json.loads(raw.decode("utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(schema)


def test_v1_1_fields_remain_optional_in_both_pinned_schemas():
    issued = _load_schema(ISSUED_SCHEMA_PATH)
    public = _load_schema(PUBLIC_SCHEMA_PATH)

    assert issued["additionalProperties"] is True
    assert public["additionalProperties"] is False
    assert not set(V1_1_INVOICE_FIELDS).intersection(issued.get("required", []))
    assert not set(V1_1_INVOICE_FIELDS).intersection(public["required"])

    for name in V1_1_INVOICE_FIELDS:
        assert name in issued["properties"]
        assert name in public["properties"]
        # The public schema is an independent full view, not an allOf wrapper;
        # compare the extension property rules without prose descriptions.
        assert _without_descriptions(issued["properties"][name]) == _without_descriptions(
            public["properties"][name]
        )


def test_public_schema_v1_1_extension_properties_validate_without_base_ref():
    public = _load_schema(PUBLIC_SCHEMA_PATH)
    extension_schema = {
        "$schema": public["$schema"],
        "type": "object",
        "properties": {
            name: public["properties"][name] for name in V1_1_INVOICE_FIELDS
        },
        "additionalProperties": True,
    }
    validator = Draft202012Validator(extension_schema)

    valid = {
        "customer_name": "Synthetic customer",
        "payments": [{"type": "card-reader", "amount": 120}, {"type": "credit", "amount": 0}],
        "currency_unit": "toman",
        "remaining_balance": 45,
    }
    assert list(validator.iter_errors(valid)) == []
    assert list(validator.iter_errors({})) == []  # Every v1.1 field is optional.

    for invalid in (
        {"customer_name": ""},
        {"payments": [{"type": "bank-transfer", "amount": 1}]},
        {"payments": [{"type": "cash", "amount": 1, "extra": True}]},
        {"currency_unit": "USD"},
        {"remaining_balance": -1},
    ):
        assert list(validator.iter_errors(invalid)), invalid


def test_v1_1_values_are_recorded_verbatim_and_not_calculated_or_defaulted():
    invoice = _invoice(
        customer_name="A\u0001\u007f",
        payments=[{"type": "cash", "amount": 7}],
        currency_unit="toman",
        remaining_balance=999,
        payable_rials=100,
    )
    before = copy.deepcopy(invoice)

    validated = validate_issued_invoice(invoice)

    assert validated.schema_version == V1_1_INVOICE_SCHEMA_VERSION
    assert dict(validated.recorded_fields) == {
        "customer_name": "A\u0001\u007f",
        "payments": [{"type": "cash", "amount": 7}],
        "currency_unit": "toman",
        "remaining_balance": 999,
    }
    assert "invoice_schema_version" not in validated.recorded_fields
    assert "payable_rials" not in validated.recorded_fields
    assert invoice == before  # Validation does not rewrite hash-covered input.


def test_v1_1_fields_and_explicit_nulls_are_optional_but_not_materialized():
    no_fields = validate_issued_invoice(_invoice())
    assert no_fields.schema_version == V1_1_INVOICE_SCHEMA_VERSION
    assert dict(no_fields.recorded_fields) == {}

    explicit_nulls = validate_issued_invoice(
        _invoice(
            customer_name=None,
            payments=None,
            currency_unit=None,
            remaining_balance=None,
        )
    )
    assert dict(explicit_nulls.recorded_fields) == {
        "customer_name": None,
        "payments": None,
        "currency_unit": None,
        "remaining_balance": None,
    }


def test_marker_absence_means_v1_0_even_if_v1_1_fields_are_present_or_invalid():
    invoice = {
        "customer_name": "",
        "payments": [{"type": "not-a-payment-type", "amount": -1}],
        "currency_unit": "USD",
        "remaining_balance": -50,
    }

    validated = validate_issued_invoice(invoice)

    assert validated.schema_version == LEGACY_INVOICE_SCHEMA_VERSION
    assert dict(validated.recorded_fields) == {}


@pytest.mark.parametrize("marker", ["1.0", "1.2", "", None, 1, True, [], {}])
def test_any_present_non_1_1_marker_fails_as_400_validation_error(marker):
    with pytest.raises(InvoiceV1_1ValidationError) as caught:
        validate_issued_invoice({"invoice_schema_version": marker})

    assert caught.value.http_status == 400
    assert caught.value.error_code == "VALIDATION_ERROR"
    assert caught.value.retry_action == "FIX_REQUEST"
    assert caught.value.field_paths == ("$.invoice_schema_version",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("customer_name", ""),
        ("customer_name", "x" * 256),
        ("customer_name", 7),
        ("payments", [{"type": "bank-transfer", "amount": 1}]),
        ("payments", [{"type": "cash"}]),
        ("payments", [{"type": "cash", "amount": 1, "extra": 1}]),
        ("payments", [{"type": "cash", "amount": -1}]),
        ("payments", [{"type": "cash", "amount": 1.0}]),
        ("payments", [{"type": "cash", "amount": True}]),
        ("payments", [{"type": "cash", "amount": 1 << 63}]),
        ("currency_unit", "USD"),
        ("remaining_balance", -1),
        ("remaining_balance", 1.0),
        ("remaining_balance", True),
        ("remaining_balance", 1 << 63),
    ],
)
def test_schema_violating_marked_v1_1_values_fail_closed(field, value):
    with pytest.raises(InvoiceV1_1ValidationError) as caught:
        validate_issued_invoice(_invoice(**{field: value}))

    assert caught.value.http_status == 400
    assert caught.value.error_code == "VALIDATION_ERROR"
    assert caught.value.field_paths


def test_mixed_batch_is_validated_per_entry_and_only_exact_invoice_path_is_used():
    legacy = {
        "customer_name": "not-inferred",
        "payments": [{"type": "cash", "amount": 5}],
    }
    current = _invoice(customer_name="Synthetic", currency_unit="rial")
    entries = [
        _entry(legacy),
        {"response_snapshot": {"response": {"invoice_schema_version": "1.1", "invoice": {}}}},
        {"response_snapshot": {"response": {"invoice": current}}},
        {"operation_type": "product.update"},
    ]
    before = copy.deepcopy(entries)

    preflight = preflight_v1_1_batch(entries)

    assert [item.entry_index for item in preflight] == [0, 1, 2, 3]
    assert [item.invoice.schema_version if item.invoice else None for item in preflight] == [
        "1.0",
        "1.0",
        "1.1",
        None,
    ]
    assert dict(preflight[0].invoice.recorded_fields) == {}
    assert dict(preflight[2].invoice.recorded_fields) == {
        "customer_name": "Synthetic",
        "currency_unit": "rial",
    }
    assert entries == before


def test_invalid_entry_aborts_full_batch_preflight_before_any_projection_plan():
    entries = [
        _entry(_invoice(customer_name="valid")),
        _entry(_invoice(payments=[{"type": "cash", "amount": -1}])),
        _entry(_invoice(currency_unit="toman")),
    ]
    before = copy.deepcopy(entries)
    would_be_projected = []

    with pytest.raises(InvoiceV1_1ValidationError) as caught:
        plan = preflight_v1_1_batch(entries)
        # A caller can build/apply projections only after complete preflight.
        would_be_projected.extend(plan)

    assert caught.value.entry_index == 1
    assert caught.value.http_status == 400
    assert caught.value.error_code == "VALIDATION_ERROR"
    assert would_be_projected == []
    assert entries == before


def test_batch_preflight_does_not_remove_marker_or_change_hash_covered_snapshot():
    entry = _entry(
        _invoice(
            customer_name="با کنترل\u0001\u007f",
            payments=[{"type": "card-to-card", "amount": 3}],
            currency_unit="toman",
            remaining_balance=21,
        )
    )
    before = copy.deepcopy(entry)

    result = preflight_v1_1_batch([entry])

    assert result[0].invoice.schema_version == "1.1"
    assert entry == before
    assert entry["response_snapshot"]["response"]["invoice"][
        "invoice_schema_version"
    ] == "1.1"
    assert entry["response_snapshot"]["response"]["invoice"]["remaining_balance"] == 21


def test_preflight_requires_an_iterable_batch():
    with pytest.raises(TypeError):
        preflight_v1_1_batch("not-a-batch")
