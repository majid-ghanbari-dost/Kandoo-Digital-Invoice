from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from verify_e72_vectors import (  # noqa: E402
    _validate_e72_draft_semantics,
    canonical_vector_bytes,
    verify_vectors,
)


VECTOR_PATH = ROOT / "tests/golden/e72/canonical-invoice-v1-2-draft-vector.json"
MANIFEST_PATH = ROOT / "tests/golden/e72/manifest.json"
BASE_SCHEMA_PATH = ROOT / "contracts/canonical_invoice_v0.schema.json"
FORBIDDEN_ENVELOPE_KEYS = {
    "base_invoice",
    "synthetic_only",
    "v1_2_draft_addendum",
    "vector_id",
}


def _vector() -> dict:
    return json.loads(VECTOR_PATH.read_bytes().decode("utf-8"))


def _base_validator() -> Draft202012Validator:
    schema = json.loads(BASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_e72_vector_is_flat_and_pinned_to_frozen_e11_with_first_round_fixes():
    raw = VECTOR_PATH.read_bytes()
    invoice = _vector()
    schema = json.loads(BASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    required = set(schema["required"])

    assert raw == canonical_vector_bytes(invoice)
    assert set(invoice) == required
    assert not (FORBIDDEN_ENVELOPE_KEYS & set(invoice))
    _base_validator().validate(invoice)
    _validate_e72_draft_semantics(invoice)

    # E-72 targets the frozen E-11 cross-repository/C# consumer contract.
    # The older schemas/canonical_invoice_v0.json validates E-01 pipeline
    # shape and is intentionally left unchanged.
    assert required == {
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
    }

    # Provenance metadata stays nested; no root aliases are introduced.
    assert "image_sha256" not in invoice
    assert "template_library_id" not in invoice
    assert {"image_sha256", "template_library_id"} <= set(invoice["provenance"])

    line_item = invoice["line_items"][0]
    provenance_line = invoice["provenance"]["fields"]["line_items"][0]
    assert "quantity" not in line_item
    assert line_item["quantity_millis"] == 1000  # 1 whole unit × 1000 millis
    assert "quantity" not in provenance_line
    assert provenance_line["quantity_millis"] == "captured"
    assert invoice["display_number"] is None
    assert invoice["provenance"]["fields"]["display_number"] == "unavailable"

    report = verify_vectors(ROOT)
    assert report["vector_count"] == 1
    assert report["vectors"][0]["file"] == VECTOR_PATH.name


def test_e72_semantics_reject_root_metadata_aliases_quantity_alias_and_issued_display():
    invoice = _vector()
    validator = _base_validator()

    for field in ("image_sha256", "template_library_id"):
        root_metadata = copy.deepcopy(invoice)
        root_metadata[field] = None
        with pytest.raises(ValidationError):
            validator.validate(root_metadata)

    quantity_alias = copy.deepcopy(invoice)
    quantity_alias["line_items"][0]["quantity"] = 1
    with pytest.raises(ValueError, match="quantity_millis only"):
        _validate_e72_draft_semantics(quantity_alias)

    issued_display = copy.deepcopy(invoice)
    issued_display["display_number"] = "SYN-E72-001"
    issued_display["provenance"]["fields"]["display_number"] = "native"
    with pytest.raises(ValueError, match="display_number must be null"):
        _validate_e72_draft_semantics(issued_display)


def test_e72_verifier_rejects_each_legacy_root_envelope_key(tmp_path: Path):
    source_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_schema = BASE_SCHEMA_PATH.read_bytes()
    vector_dir = tmp_path / "tests" / "golden" / "e72"
    vector_dir.mkdir(parents=True)
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts" / "canonical_invoice_v0.schema.json").write_bytes(source_schema)

    for key in sorted(FORBIDDEN_ENVELOPE_KEYS):
        invoice = copy.deepcopy(_vector())
        invoice[key] = {} if key in {"base_invoice", "v1_2_draft_addendum"} else True
        raw = canonical_vector_bytes(invoice)
        (vector_dir / VECTOR_PATH.name).write_bytes(raw)
        manifest = copy.deepcopy(source_manifest)
        manifest["vectors"] = [
            {
                "file": VECTOR_PATH.name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        ]
        (vector_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="forbidden envelope keys"):
            verify_vectors(tmp_path)


def test_e72_vector_verifier_rejects_whitespace_or_byte_drift():
    invoice = _vector()
    dirty_bytes = json.dumps(invoice, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    assert dirty_bytes != VECTOR_PATH.read_bytes()
    assert canonical_vector_bytes(invoice) == VECTOR_PATH.read_bytes()
