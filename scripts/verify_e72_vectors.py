"""Verify additive E-72 draft schemas and the byte-for-byte synthetic vector."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIR = ROOT / "tests" / "golden" / "e72"


def _read_json_bytes(payload: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def canonical_vector_bytes(document: dict[str, Any]) -> bytes:
    """Encode the agreed compact, sorted-key UTF-8 JSON byte profile."""
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def verify_vectors(root: Path = ROOT) -> dict[str, Any]:
    vector_dir = root / "tests" / "golden" / "e72"
    manifest = _read_json_bytes((vector_dir / "manifest.json").read_bytes(), "E-72 manifest")
    if manifest.get("schema_version") != "e72.golden-manifest.v1" or manifest.get("synthetic_only") is not True:
        raise ValueError("E-72 manifest version or synthetic-only marker is invalid")
    entries = manifest.get("vectors")
    if not isinstance(entries, list) or not entries:
        raise ValueError("E-72 manifest must list at least one vector")

    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - installation guidance
        raise RuntimeError("jsonschema is required to verify the E-72 vector") from exc

    extension_schema_path = root / "schemas" / "canonical_invoice_v1_2_draft_addendum.schema.json"
    base_schema_path = root / "schemas" / "canonical_invoice_v0.json"
    extension_schema = _read_json_bytes(extension_schema_path.read_bytes(), "E-72 draft schema")
    base_schema = _read_json_bytes(base_schema_path.read_bytes(), "Canonical Invoice v0 schema")
    Draft202012Validator.check_schema(extension_schema)
    Draft202012Validator.check_schema(base_schema)
    extension_validator = Draft202012Validator(extension_schema)
    base_validator = Draft202012Validator(base_schema)

    vector_records: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("E-72 manifest vector entries must be objects")
        filename = entry.get("file")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError("E-72 vector filename must be a safe basename")
        raw = (vector_dir / filename).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry.get("sha256") or len(raw) != entry.get("bytes"):
            raise ValueError(f"E-72 vector pin mismatch: {filename}")
        if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or raw.endswith(b"\n"):
            raise ValueError(f"E-72 vector encoding is not the declared no-BOM/no-newline profile: {filename}")
        document = _read_json_bytes(raw, f"E-72 vector {filename}")
        if document.get("synthetic_only") is not True:
            raise ValueError(f"E-72 vector is not marked synthetic-only: {filename}")
        if canonical_vector_bytes(document) != raw:
            raise ValueError(f"E-72 vector bytes do not match compact sorted-key canonical JSON: {filename}")

        base_invoice = document.get("base_invoice")
        addendum = document.get("v1_2_draft_addendum")
        base_errors = sorted(
            base_validator.iter_errors(base_invoice),
            key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
        )
        extension_errors = sorted(
            extension_validator.iter_errors(addendum),
            key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
        )
        if base_errors:
            raise ValueError(f"Canonical Invoice v0 vector is invalid: {base_errors[0].message}")
        if extension_errors:
            raise ValueError(f"v1.2 draft addendum is invalid: {extension_errors[0].message}")
        if base_invoice.get("invoice_id") != addendum.get("invoice_id"):
            raise ValueError("v1.2 draft addendum invoice_id does not bind to the v0 base")
        if not any(payment.get("type") == "cheque" for payment in addendum.get("payments", [])):
            raise ValueError("E-72 vector does not exercise the cheque payment type")
        if addendum.get("invoice_discount") is None:
            raise ValueError("E-72 vector does not exercise invoice-level discount")
        if addendum.get("walk_in_customer") is not True:
            raise ValueError("E-72 vector does not exercise the walk-in flag")
        vector_records.append({"file": filename, "sha256": digest, "bytes": len(raw)})

    return {"vector_count": len(vector_records), "vectors": vector_records}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        report = verify_vectors(args.repo_root.resolve())
    except Exception as exc:
        message = f"E-72 vector verification FAILED: {type(exc).__name__}: {exc}"
        annotation = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=E-72 vectors::{annotation}")
        print(message, file=sys.stderr)
        return 1
    print(f"E-72 vector verification PASS: {report['vector_count']} synthetic vector(s).")
    for vector in report["vectors"]:
        print(f"{vector['file']} bytes={vector['bytes']} sha256={vector['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
