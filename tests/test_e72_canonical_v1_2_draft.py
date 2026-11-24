from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from verify_e72_vectors import (
    _validate_e72_draft_semantics,
    canonical_vector_bytes,
    verify_vectors,
)


VECTOR_PATH = ROOT / "tests/golden/e72/canonical-invoice-v1-2-draft-vector.json"
BASE_SCHEMA_PATH = ROOT / "contracts/canonical_invoice_v0.schema.json"
SCHEMA_PATH = ROOT / "schemas/canonical_invoice_v1_2_draft_addendum.schema.json"


def _vector() -> dict:
    return json.loads(VECTOR_PATH.read_bytes().decode("utf-8"))


def test_e72_vector_is_pinned_byte_for_byte_and_validates_both_contract_parts():
    raw = VECTOR_PATH.read_bytes()
    document = _vector()
    base_invoice = document["base_invoice"]
    assert raw == canonical_vector_bytes(document)
    assert document["synthetic_only"] is True

    # E-72 targets the frozen E-11 cross-repository/C# consumer contract.
    # The older schemas/canonical_invoice_v0.json validates the E-01 pipeline
    # shape and is intentionally left unchanged.
    base_schema = json.loads(BASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(base_schema)
    Draft202012Validator(base_schema).validate(base_invoice)
    _validate_e72_draft_semantics(base_invoice)

    # These two fields are allowed and required *inside provenance*, not at
    # the base_invoice root; retain the nested frozen contract fields.
    assert "image_sha256" not in base_invoice
    assert "template_library_id" not in base_invoice
    assert {"image_sha256", "template_library_id"} <= set(base_invoice["provenance"])

    line_item = base_invoice["line_items"][0]
    provenance_line = base_invoice["provenance"]["fields"]["line_items"][0]
    assert "quantity" not in line_item
    assert line_item["quantity_millis"] == 1000  # 1 whole unit × 1000 millis
    assert "quantity" not in provenance_line
    assert provenance_line["quantity_millis"] == "captured"
    assert base_invoice["display_number"] is None
    assert base_invoice["provenance"]["fields"]["display_number"] == "unavailable"

    report = verify_vectors(ROOT)
    assert report["vector_count"] == 1
    assert report["vectors"][0]["file"] == VECTOR_PATH.name


def test_e72_draft_semantics_reject_root_metadata_aliases_and_issued_display():
    base_invoice = _vector()["base_invoice"]

    base_schema = json.loads(BASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(base_schema)
    for field in ("image_sha256", "template_library_id"):
        root_metadata = copy.deepcopy(base_invoice)
        root_metadata[field] = None
        with pytest.raises(ValidationError):
            validator.validate(root_metadata)

    quantity_alias = copy.deepcopy(base_invoice)
    quantity_alias["line_items"][0]["quantity"] = 1
    with pytest.raises(ValueError, match="quantity_millis only"):
        _validate_e72_draft_semantics(quantity_alias)

    issued_display = copy.deepcopy(base_invoice)
    issued_display["display_number"] = "SYN-E72-001"
    issued_display["provenance"]["fields"]["display_number"] = "native"
    with pytest.raises(ValueError, match="display_number must be null"):
        _validate_e72_draft_semantics(issued_display)


def test_e72_addendum_schema_covers_cheque_discount_and_nullable_walk_in():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    addendum = _vector()["v1_2_draft_addendum"]
    validator.validate(addendum)

    invalid_payment = copy.deepcopy(addendum)
    invalid_payment["payments"][0]["type"] = "unrecognized"
    with pytest.raises(ValidationError):
        validator.validate(invalid_payment)

    invalid_walk_in = copy.deepcopy(addendum)
    invalid_walk_in["walk_in_customer"] = "yes"
    with pytest.raises(ValidationError):
        validator.validate(invalid_walk_in)

    unknown_field = copy.deepcopy(addendum)
    unknown_field["computed_balance"] = 0
    with pytest.raises(ValidationError):
        validator.validate(unknown_field)


def test_e72_vector_verifier_rejects_whitespace_or_byte_drift():
    document = _vector()
    dirty_bytes = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    assert dirty_bytes != VECTOR_PATH.read_bytes()
    assert canonical_vector_bytes(document) == VECTOR_PATH.read_bytes()
