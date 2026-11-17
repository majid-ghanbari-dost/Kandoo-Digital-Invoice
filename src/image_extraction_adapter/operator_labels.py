"""Create owner-local operator labels without any online learning path."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from .bundle_paths import resource_root


LABEL_VERSION = "o15.operator-labels.v1"
EVIDENCE_VERSION = "o15.review-evidence.v1"


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _protected_roots() -> tuple[Path, ...]:
    roots = [resource_root().resolve()]
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    return tuple(roots)


def _require_outside_app(path: Path, description: str) -> None:
    if any(_within(path, root) for root in _protected_roots()):
        raise ValueError(f"{description} must remain outside the repository/bundle")


def _load_json(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {description} as UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object")
    return value


def _validate(document: object, schema_path: Path, description: str) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - install guidance
        raise RuntimeError("jsonschema is required to validate local operator labels") from exc
    schema = _load_json(schema_path, f"{description} schema")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)


def build_operator_label_template(
    evidence_dir: Path | str,
    output_path: Path | str | None = None,
) -> Path:
    """Create blank correctness/correction entries from local E-61 evidence.

    The generated file contains the machine reading and relative crop reference.
    It is never sent to the extractor, used to update Glyph templates, or
    transmitted anywhere. Corrections are labels only, not online learning.
    """
    evidence_root = Path(evidence_dir).expanduser().resolve(strict=True)
    if not evidence_root.is_dir():
        raise ValueError("--evidence-dir must name a directory")
    _require_outside_app(evidence_root, "real review evidence")
    evidence = _load_json(evidence_root / "review-evidence-v1.json", "E-61 evidence")
    resources = resource_root()
    _validate(
        evidence,
        resources / "schemas" / "o15" / "review-evidence-v1.schema.json",
        "E-61 evidence",
    )
    if evidence.get("schema_version") != EVIDENCE_VERSION:
        raise ValueError("unsupported E-61 evidence schema")

    for item in evidence["items"]:
        crop_path = (evidence_root / item["crop_file"]).resolve(strict=True)
        if not _within(crop_path, evidence_root):
            raise ValueError("E-61 crop path escaped the local evidence directory")

    target = (
        Path(output_path).expanduser().resolve(strict=False)
        if output_path is not None
        else evidence_root / "operator-labels.local.json"
    )
    _require_outside_app(target, "operator label file")
    if target.parent != evidence_root:
        raise ValueError("operator label file must be written in the evidence directory so crop references stay relative")
    if target.exists():
        raise FileExistsError(f"operator label file already exists: {target}")
    if not target.parent.is_dir():
        raise FileNotFoundError(f"operator label parent directory does not exist: {target.parent}")

    entries: list[dict[str, Any]] = []
    for item in evidence["items"]:
        field_name = item["field_name"]
        if field_name in {"layout", "numeric_fields"}:
            continue
        entries.append({
            "evidence_id": item["evidence_id"],
            "page_index": item["page_index"],
            "field_name": field_name,
            "value": item["value"],
            "confidence": item["confidence"],
            "reason": item["reason"],
            "crop_file": item["crop_file"],
            "crop_region": item["crop_region"],
            "read_correctly": None,
            "corrected_value": None,
        })
    document = {
        "schema_version": LABEL_VERSION,
        "source_evidence_schema": EVIDENCE_VERSION,
        "online_learning": False,
        "entries": entries,
    }
    schema_path = resources / "schemas" / "o15" / "operator-label-v1.schema.json"
    _validate(document, schema_path, "operator label")
    payload = (
        json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    with target.open("xb") as stream:
        stream.write(payload)
        stream.flush()
    return target
