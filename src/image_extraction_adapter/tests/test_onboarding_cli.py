from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "real"
SCHEMA_DIR = ROOT / "schemas" / "mode-b" / "v1"
E20_REPORT = ROOT / "docs" / "e20-second-store.json"
E20_VALUES = ROOT / "docs" / "E-03-kit-v3" / "expected-values.json"
FIXED_TIME = "2026-10-28T00:00:00Z"


def _run_cli(arguments: list[str | Path], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT / "src"), str(ROOT / "scripts"), existing) if part
    )
    return subprocess.run(
        [sys.executable, "-m", "image_extraction_adapter.cli", *(str(value) for value in arguments)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        timeout=120,
        check=False,
    )


def _artifact(path: Path, schema_name: str) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(value)
    return value


def test_onboard_build_uses_operator_confirmed_capture_labels_and_e16_schema(tmp_path: Path) -> None:
    output = tmp_path / "operator-template-bank.json"
    result = _run_cli([
        "onboard", "build",
        "--capture-root", FIXTURE_DIR,
        "--canonical-dir", FIXTURE_DIR / "canonical",
        "--labels", FIXTURE_DIR / "labels.json",
        "--store-id", "e05-synth-store",
        "--currency-unit", "rial",
        "--created-at", FIXED_TIME,
        "--output", output,
    ])

    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    output_bytes = output.read_bytes()
    assert b"\r" not in output_bytes
    assert output_bytes.endswith(b"\n")
    artifact = _artifact(output, "template-bank.schema.json")
    assert artifact["artifact_type"] == "kandoo.mode-b.template-bank"
    assert artifact["store_id"] == "e05-synth-store"
    assert artifact["template_bank"]["currency_unit"] == "rial"
    assert len(artifact["template_bank"]["templates"]) == 1


def test_e20_synthetic_flow_runs_build_verdict_and_register_type(tmp_path: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from prepare_e26_e20_smoke_inputs import prepare_e26_e20_inputs

    inputs = prepare_e26_e20_inputs(ROOT, tmp_path / "inputs")
    bank_path = tmp_path / "e20-template-bank.json"
    build = _run_cli([
        "onboard", "build",
        "--synthetic-e20-report", E20_REPORT,
        "--synthetic-e20-values", E20_VALUES,
        "--store-id", "synthetic-second-store",
        "--currency-unit", "rial",
        "--created-at", FIXED_TIME,
        "--output", bank_path,
    ])
    assert build.returncode == 0, build.stderr.decode("utf-8", errors="replace")
    bank_artifact = _artifact(bank_path, "template-bank.schema.json")
    assert bank_artifact["store_id"] == "synthetic-second-store"

    verdict_path = tmp_path / "e20-verdict.json"
    verdict = _run_cli([
        "onboard", "verdict",
        "--template-bank", bank_path,
        "--store-id", "synthetic-second-store",
        "--invoice-id", "e26-e20-exam-pipeline",
        "--observation", inputs["pipeline_observation"],
        "--processed-invoice-count", "0",
        "--template-bank-unlocked",
        "--d14-agreement-required",
        "--no-require-kit-digit-coverage",
        "--extraction-confidence", "0.0",
        "--missing-field", "line.0.quantity",
        "--missing-field", "line.0.total",
        "--missing-field", "line.1.total",
        "--missing-field", "invoice.payable",
        "--evaluated-at", FIXED_TIME,
        "--output", verdict_path,
    ])
    assert verdict.returncode == 10, verdict.stderr.decode("utf-8", errors="replace")
    verdict_artifact = _artifact(verdict_path, "onboarding-verdict.schema.json")
    assert verdict_artifact["result"]["verdict"] == "REVIEW"
    assert verdict_artifact["store_id"] == "synthetic-second-store"
    assert verdict_artifact["template_bank_sha256"] == hashlib.sha256(bank_path.read_bytes()).hexdigest()

    candidate_path = tmp_path / "e20-new-type-candidate.json"
    register = _run_cli([
        "onboard", "register-type",
        "--template-bank", bank_path,
        "--store-id", "synthetic-second-store",
        "--invoice-id", "e26-e20-exam-invoice",
        "--invoice", inputs["candidate_invoice"],
        "--observation", inputs["new_layout_observation"],
        "--accepted-invoice-count", "4",
        "--template-bank-locked",
        "--d14-agreement-signed",
        "--extraction-confidence", "0.99",
        "--detected-at", FIXED_TIME,
        "--exported-at", FIXED_TIME,
        "--output", candidate_path,
    ])
    assert register.returncode == 10, register.stderr.decode("utf-8", errors="replace")
    candidate_artifact = _artifact(candidate_path, "new-type-candidate.schema.json")
    assert candidate_artifact["store_id"] == "synthetic-second-store"
    assert candidate_artifact["candidate"]["state"] == "PROPOSED"
    assert candidate_artifact["candidate"]["source_invoice_ids"] == ["e26-e20-exam-invoice"]


def test_onboard_build_refuses_capture_paths_outside_capture_root(tmp_path: Path) -> None:
    output = tmp_path / "blocked-bank.json"
    result = _run_cli([
        "onboard", "build",
        "--capture-root", tmp_path,
        "--canonical-dir", FIXTURE_DIR / "canonical",
        "--labels", FIXTURE_DIR / "labels.json",
        "--store-id", "e05-synth-store",
        "--currency-unit", "rial",
        "--output", output,
    ])
    assert result.returncode == 30
    assert b"escapes --capture-root" in result.stderr
    assert not output.exists()


def test_onboard_parser_errors_use_stable_exit_code_30() -> None:
    result = _run_cli(["onboard", "build", "--help"])
    assert result.returncode == 0
    assert b"--capture-root" in result.stdout

    missing_currency = _run_cli([
        "onboard", "build",
        "--capture-root", FIXTURE_DIR,
        "--canonical-dir", FIXTURE_DIR / "canonical",
        "--labels", FIXTURE_DIR / "labels.json",
        "--store-id", "e05-synth-store",
        "--output", ROOT / "build-should-not-exist.json",
    ])
    assert missing_currency.returncode == 30
    assert b"--currency-unit" in missing_currency.stderr
    assert not (ROOT / "build-should-not-exist.json").exists()


def test_onboard_verdict_rejects_missing_manual_override_timestamp(tmp_path: Path) -> None:
    bank_path = tmp_path / "template-bank.json"
    build = _run_cli([
        "onboard", "build",
        "--capture-root", FIXTURE_DIR,
        "--canonical-dir", FIXTURE_DIR / "canonical",
        "--labels", FIXTURE_DIR / "labels.json",
        "--store-id", "e05-synth-store",
        "--currency-unit", "rial",
        "--created-at", FIXED_TIME,
        "--output", bank_path,
    ])
    assert build.returncode == 0, build.stderr.decode("utf-8", errors="replace")

    override_path = tmp_path / "manual-override.json"
    override_path.write_text(
        json.dumps({
            "target": "REVIEW",
            "actor_id": "store-owner-1",
            "actor_role": "store_owner",
            "audit_id": "audit-1",
            "reason": "missing source timestamp must not be synthesized",
            "occurred_at": None,
            "verified_fields": [],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "verdict.json"
    verdict = _run_cli([
        "onboard", "verdict",
        "--template-bank", bank_path,
        "--store-id", "e05-synth-store",
        "--invoice-id", "missing-candidate",
        "--processed-invoice-count", "0",
        "--template-bank-unlocked",
        "--d14-agreement-required",
        "--no-require-kit-digit-coverage",
        "--manual-override", override_path,
        "--evaluated-at", FIXED_TIME,
        "--output", output,
    ])
    assert verdict.returncode == 30
    assert b"manual override occurred_at" in verdict.stderr
    assert not output.exists()
