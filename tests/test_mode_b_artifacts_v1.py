from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "schemas" / "mode-b" / "v1"
EXAMPLES_DIR = PACKAGE_DIR / "examples"
GENERATOR = ROOT / "scripts" / "generate_mode_b_artifact_goldens.py"
EXPECTED_FILES = {
    "template-bank.json",
    "onboarding-verdict.json",
    "layout-font-fingerprint.json",
    "new-type-candidate.json",
}


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_v1_schemas_validate_every_golden_and_manifest_hash() -> None:
    manifest = _load_json(EXAMPLES_DIR / "manifest.json")
    assert manifest["manifest_version"] == "1"
    assert manifest["generated_by"] == "scripts/generate_mode_b_artifact_goldens.py"
    assert {item["path"] for item in manifest["examples"]} == EXPECTED_FILES

    for item in manifest["examples"]:
        example_path = EXAMPLES_DIR / item["path"]
        schema_path = (EXAMPLES_DIR / item["schema"]).resolve()
        schema = _load_json(schema_path)
        example = _load_json(example_path)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(example), key=lambda error: list(error.absolute_path))
        assert not errors, (item["path"], [error.message for error in errors])
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].endswith(":1")
        assert example["artifact_type"] == item["artifact_type"]
        assert example["artifact_version"] == "1"
        assert example["mode"] == "B"
        assert hashlib.sha256(example_path.read_bytes()).hexdigest() == item["sha256"]


def test_goldens_are_reproducible_from_existing_python_apis(tmp_path: Path) -> None:
    generated_dir = tmp_path / "generated"
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT / "src"), existing_pythonpath) if part
    )
    subprocess.run(
        [sys.executable, str(GENERATOR), "--output-dir", str(generated_dir)],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    for name in (*sorted(EXPECTED_FILES), "manifest.json"):
        assert (generated_dir / name).read_bytes() == (EXAMPLES_DIR / name).read_bytes()


def test_candidate_and_fingerprint_share_the_e08_identity_without_installing_it() -> None:
    fingerprint = _load_json(EXAMPLES_DIR / "layout-font-fingerprint.json")
    candidate_artifact = _load_json(EXAMPLES_DIR / "new-type-candidate.json")
    candidate = candidate_artifact["candidate"]

    assert fingerprint["fingerprint_id"] == candidate["candidate_id"]
    assert fingerprint["store_id"] == candidate_artifact["store_id"] == candidate["store_id"]
    assert candidate["state"] == "PROPOSED"
    assert fingerprint["layout_signature"] == candidate["layout_signature"]
    assert fingerprint["field_positions"] == candidate["field_positions"]
    assert fingerprint["numeric_digit_alphabet"] == candidate["numeric_digit_alphabet"]
    assert fingerprint["glyph_profile"]["grid"] == [10, 14]
    assert fingerprint["glyph_profile"]["training_sources"]

    bank = _load_json(EXAMPLES_DIR / "template-bank.json")
    verdict = _load_json(EXAMPLES_DIR / "onboarding-verdict.json")
    bank_bytes = (EXAMPLES_DIR / "template-bank.json").read_bytes()
    assert verdict["template_bank_sha256"] == hashlib.sha256(bank_bytes).hexdigest()
    assert verdict["store_id"] == bank["store_id"]
    assert verdict["result"]["verdict"] == "REVIEW"


def test_v1_rejects_unknown_versions_and_invalid_candidate_transitions() -> None:
    candidate_schema = _load_json(PACKAGE_DIR / "new-type-candidate.schema.json")
    candidate_validator = Draft202012Validator(
        candidate_schema,
        format_checker=FormatChecker(),
    )
    candidate_artifact = _load_json(EXAMPLES_DIR / "new-type-candidate.json")

    wrong_version = dict(candidate_artifact, artifact_version="2")
    assert list(candidate_validator.iter_errors(wrong_version))

    invalid_transition = json.loads(json.dumps(candidate_artifact))
    invalid_transition["candidate"]["state"] = "REVIEWED"
    # A REVIEWED state requires reviewer identity, timestamp, and reason; the
    # PROPOSED golden correctly has those lifecycle fields set to null.
    assert list(candidate_validator.iter_errors(invalid_transition))
