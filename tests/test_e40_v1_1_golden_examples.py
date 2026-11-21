from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = REPO_ROOT / "docs" / "schemas" / "v1-1" / "examples"
MANIFEST_PATH = EXAMPLE_DIR / "manifest.json"
ISSUED_SCHEMA_PATH = REPO_ROOT / "docs" / "schemas" / "v1-1" / "issued-invoice-v1-1.schema.json"
EXPECTED_MANIFEST = (
    965,
    "6074d237fb6052ea87e654bf762451a03a160ff7f0d3bcda5b5179a0f4d8ea9a",
)
EXPECTED_EXAMPLES = {
    "issued-invoice-v1-1-full.json": (
        279,
        "4eab66e1d6b057dfb9ed3500b14cebcb269c79b0608697d3c8884506a4a7b5c0",
    ),
    "issued-invoice-v1-1-minimal.json": (
        38,
        "0e36b7d464af9ee869d941a7fdf1f3fb5e2969ab8fa0997c8015bd99c5ec41dd",
    ),
    "issued-invoice-v1-1-explicit-nulls.json": (
        137,
        "79f6b9625bc3fb458b0bd05651487f1997d28add25ed5cb30ed75054694a2cc1",
    ),
}


def _read_manifest() -> tuple[dict, bytes]:
    raw = MANIFEST_PATH.read_bytes()
    assert (len(raw), hashlib.sha256(raw).hexdigest()) == EXPECTED_MANIFEST
    return json.loads(raw.decode("utf-8")), raw


def test_manifest_is_byte_pinned_and_marks_scope_and_deferred_boundaries() -> None:
    manifest, _ = _read_manifest()

    assert manifest["task"] == "E-40"
    assert manifest["evidence_class"] == "SYNTHETIC_ONLY"
    assert {item["path"] for item in manifest["examples"]} == set(EXPECTED_EXAMPLES)
    assert manifest["public_view_golden"]["status"] == "DEFERRED"
    assert manifest["known_holoo_gaps_not_added"] == [
        "cheque payment type",
        "invoice-level discount",
    ]
    assert not any("public-invoice-view" in name for name in EXPECTED_EXAMPLES)


def test_issued_invoice_goldens_are_byte_pinned_and_validate_on_each_platform() -> None:
    manifest, _ = _read_manifest()
    listed = {item["path"]: item for item in manifest["examples"]}
    assert set(listed) == set(EXPECTED_EXAMPLES)

    schema = json.loads(ISSUED_SCHEMA_PATH.read_bytes().decode("utf-8"))
    validator = Draft202012Validator(schema)

    for name, expected in EXPECTED_EXAMPLES.items():
        raw = (EXAMPLE_DIR / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert (len(raw), digest) == expected
        assert (listed[name]["size_bytes"], listed[name]["sha256"]) == expected
        assert b"\r" not in raw, f"{name} must retain pinned LF bytes on Windows"
        example = json.loads(raw.decode("utf-8"))
        assert example.get("invoice_schema_version") == "1.1"
        validator.validate(example)
