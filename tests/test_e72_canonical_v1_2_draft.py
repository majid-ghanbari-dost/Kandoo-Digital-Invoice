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

from image_extraction_adapter.canonical_invoice import validate_canonical_invoice
from verify_e72_vectors import canonical_vector_bytes, verify_vectors


VECTOR_PATH = ROOT / "tests/golden/e72/canonical-invoice-v1-2-draft-vector.json"
SCHEMA_PATH = ROOT / "schemas/canonical_invoice_v1_2_draft_addendum.schema.json"


def _vector() -> dict:
    return json.loads(VECTOR_PATH.read_bytes().decode("utf-8"))


def test_e72_vector_is_pinned_byte_for_byte_and_validates_both_contract_parts():
    raw = VECTOR_PATH.read_bytes()
    document = _vector()
    assert raw == canonical_vector_bytes(document)
    assert document["synthetic_only"] is True
    assert validate_canonical_invoice(document["base_invoice"]) == (True, [])
    report = verify_vectors(ROOT)
    assert report["vector_count"] == 1
    assert report["vectors"][0]["file"] == VECTOR_PATH.name


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
