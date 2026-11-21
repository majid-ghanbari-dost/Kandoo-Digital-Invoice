#!/usr/bin/env python3
"""Run the versioned E-30 extraction-bridge pack and compare exact output bytes.

Without --exe, the source CLI is launched as a Python subprocess. On Windows CI,
--exe must point to the freshly built PyInstaller one-folder executable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Sequence

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs" / "extraction-bridge" / "golden-pack" / "v1"
FIXTURES = PACK / "fixtures"
EXPECTED = PACK / "expected"
FIXED_TIME = "2026-10-30T00:00:00Z"


def _json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def _schema(schema_path: Path, payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload.decode("utf-8"))
    schema = _json(schema_path)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    if not isinstance(value, dict):
        raise AssertionError(f"{label} must be a JSON object")
    return value


def _hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_and_check_manifest() -> dict[str, Any]:
    manifest_path = PACK / "manifest.json"
    manifest = _json(manifest_path)
    if manifest.get("pack_version") != "e30.extraction-bridge.golden.v1":
        raise AssertionError("unsupported E-30 golden-pack version")
    for group_name in ("fixtures", "expected"):
        entries = manifest.get(group_name)
        if not isinstance(entries, dict) or not entries:
            raise AssertionError(f"golden manifest {group_name} must be a non-empty object")
        root = FIXTURES if group_name == "fixtures" else EXPECTED
        for relative, record in entries.items():
            if not isinstance(record, dict):
                raise AssertionError(f"invalid {group_name} manifest record for {relative}")
            path = root / relative
            payload = path.read_bytes()
            if len(payload) != record.get("bytes") or _hash(payload) != record.get("sha256"):
                raise AssertionError(f"{group_name} bytes/hash do not match manifest: {relative}")
    return manifest


def _command(exe: Path | None, arguments: Sequence[str | Path], timeout: int) -> subprocess.CompletedProcess[bytes]:
    if exe is None:
        command = [sys.executable, "-m", "image_extraction_adapter.cli"]
    else:
        command = [str(exe)]
    command.extend(str(value) for value in arguments)
    environment = os.environ.copy()
    extra_paths = [str(ROOT / "src"), str(ROOT / "scripts")]
    existing = environment.get("PYTHONPATH")
    if existing:
        extra_paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(extra_paths)
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _assert_exit(label: str, result: subprocess.CompletedProcess[bytes], expected: int) -> None:
    if result.returncode != expected:
        stderr = result.stderr.decode("utf-8", errors="replace")[-3000:]
        raise AssertionError(f"{label}: expected exit {expected}, got {result.returncode}; stderr={stderr}")


def _compare_bytes(label: str, actual: bytes, expected_name: str) -> dict[str, Any]:
    expected = (EXPECTED / expected_name).read_bytes()
    if actual != expected:
        mismatch = next((index for index, (left, right) in enumerate(zip(actual, expected)) if left != right), min(len(actual), len(expected)))
        raise AssertionError(
            f"{label}: byte mismatch at offset {mismatch}; actual={len(actual)} bytes, "
            f"expected={len(expected)} bytes"
        )
    if b"\r" in actual:
        raise AssertionError(f"{label}: CR byte found; golden contract requires binary UTF-8/LF output")
    if not actual.endswith(b"\n"):
        raise AssertionError(f"{label}: JSON artifact is missing its final LF")
    return {"golden": expected_name, "bytes": len(actual), "sha256": _hash(actual)}


def verify(exe: Path | None = None) -> dict[str, Any]:
    _load_and_check_manifest()
    report: dict[str, Any] = {
        "status": "FAIL",
        "contract": "e30.extraction-bridge.v1",
        "executor": "source CLI" if exe is None else "PyInstaller one-folder executable",
        "commands": [],
        "cross_platform_rule": "Every artifact is byte-compared with the same committed UTF-8/LF golden file.",
    }

    context = "docs/extraction-bridge/golden-pack/v1/fixtures/canonical-context-29.json"
    image = "tests/fixtures/real/29.png"
    captured_at = FIXED_TIME
    image_args: list[str | Path] = [
        "extract", "--image", image, "--context", context, "--captured-at", captured_at,
    ]

    image_result = _command(exe, image_args, 180)
    _assert_exit("extract-image", image_result, 0)
    if image_result.stderr:
        raise AssertionError("extract-image success must not emit stderr")
    invoice = _schema(ROOT / "schemas" / "canonical_invoice_v0.json", image_result.stdout, "extract-image")
    if invoice.get("schema_version") != "0" or invoice.get("state") != "EXTRACTED":
        raise AssertionError("extract-image golden must be a Canonical Invoice v0 EXTRACTED candidate")
    report["commands"].append({
        "id": "extract-image-29",
        "exit_code": image_result.returncode,
        "stdout": _compare_bytes("extract-image-29 stdout", image_result.stdout, "extract-image-29.stdout.json"),
        "stderr_bytes": len(image_result.stderr),
    })

    with tempfile.TemporaryDirectory(prefix="e30-golden-pack-") as temp_name:
        temp = Path(temp_name)
        drift_path = temp / "glyph-drift-report.json"
        drift_result = _command(exe, [*image_args, "--drift-report", drift_path], 180)
        _assert_exit("extract-image-drift", drift_result, 0)
        if drift_result.stderr:
            raise AssertionError("extract-image --drift-report success must not emit stderr")
        if drift_result.stdout != image_result.stdout:
            raise AssertionError("--drift-report must not change the Canonical Invoice stdout bytes")
        drift_bytes = drift_path.read_bytes()
        drift = _schema(ROOT / "schemas" / "e28" / "glyph_drift_report_v1.schema.json", drift_bytes, "drift report")
        if drift.get("schema_version") != "e28.glyph-drift-report.v1":
            raise AssertionError("drift sidecar schema_version is missing")
        report["commands"].append({
            "id": "extract-image-drift-report",
            "exit_code": drift_result.returncode,
            "stdout_sha256": _hash(drift_result.stdout),
            "sidecar": _compare_bytes("drift report", drift_bytes, "extract-image-29.drift.json"),
        })

        capture_path = "docs/extraction-bridge/golden-pack/v1/fixtures/capture-folder"
        e05_bank = "docs/extraction-bridge/golden-pack/v1/fixtures/e05-layout-bank.json"
        capture_out = temp / "capture-folder-result.json"
        capture_result = _command(exe, [
            "extract", "--capture-folder", capture_path, "--e05-bank", e05_bank,
            "--out", capture_out,
        ], 180)
        _assert_exit("extract-capture-folder", capture_result, 10)
        if capture_result.stdout:
            raise AssertionError("capture-folder --out success must leave stdout empty")
        if not capture_result.stderr:
            raise AssertionError("capture-folder review must emit a human-readable stderr summary")
        capture_bytes = capture_out.read_bytes()
        capture = _schema(
            ROOT / "schemas" / "extraction-bridge" / "v1" / "capture-folder-result.schema.json",
            capture_bytes,
            "capture-folder result",
        )
        if capture.get("result_version") != "capture-folder-result-v1":
            raise AssertionError("capture-folder result_version is missing")
        if capture.get("capture_folder") != capture_path:
            raise AssertionError("relative capture-folder path is not serialized portably")
        report["commands"].append({
            "id": "extract-capture-folder-29",
            "exit_code": capture_result.returncode,
            "stderr_bytes": len(capture_result.stderr),
            "artifact": _compare_bytes("capture-folder result", capture_bytes, "extract-capture-folder-29.json"),
        })

        bank_path = temp / "template-bank.json"
        build_result = _command(exe, [
            "onboard", "build",
            "--synthetic-e20-report", "docs/extraction-bridge/golden-pack/v1/fixtures/e20-second-store.json",
            "--synthetic-e20-values", "docs/extraction-bridge/golden-pack/v1/fixtures/e03-kit-v3-expected-values.json",
            "--store-id", "synthetic-second-store",
            "--currency-unit", "rial",
            "--created-at", FIXED_TIME,
            "--output", bank_path,
        ], 120)
        _assert_exit("onboard-build", build_result, 0)
        if build_result.stdout or not build_result.stderr.startswith(b"WROTE "):
            raise AssertionError("onboard build stream behavior differs from contract")
        bank_bytes = bank_path.read_bytes()
        bank = _schema(ROOT / "schemas" / "mode-b" / "v1" / "template-bank.schema.json", bank_bytes, "template bank")
        if bank.get("store_id") != "synthetic-second-store":
            raise AssertionError("onboard build used the wrong synthetic store scope")
        report["commands"].append({
            "id": "onboard-build-e20",
            "exit_code": build_result.returncode,
            "stderr_bytes": len(build_result.stderr),
            "artifact": _compare_bytes("template bank", bank_bytes, "onboard-template-bank.json"),
        })

        verdict_path = temp / "onboarding-verdict.json"
        verdict_result = _command(exe, [
            "onboard", "verdict",
            "--template-bank", bank_path,
            "--store-id", "synthetic-second-store",
            "--invoice-id", "e26-e20-exam-pipeline",
            "--observation", "docs/extraction-bridge/golden-pack/v1/fixtures/e20-pipeline-observation.json",
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
        ], 120)
        _assert_exit("onboard-verdict", verdict_result, 10)
        if verdict_result.stdout or not verdict_result.stderr.startswith(b"REVIEW "):
            raise AssertionError("onboard verdict stream behavior differs from contract")
        verdict_bytes = verdict_path.read_bytes()
        verdict = _schema(ROOT / "schemas" / "mode-b" / "v1" / "onboarding-verdict.schema.json", verdict_bytes, "onboarding verdict")
        if verdict.get("result", {}).get("verdict") != "REVIEW":
            raise AssertionError("golden verdict should fail closed to REVIEW")
        report["commands"].append({
            "id": "onboard-verdict-e20",
            "exit_code": verdict_result.returncode,
            "stderr_bytes": len(verdict_result.stderr),
            "artifact": _compare_bytes("onboarding verdict", verdict_bytes, "onboard-verdict.json"),
        })

        candidate_path = temp / "new-type-candidate.json"
        register_result = _command(exe, [
            "onboard", "register-type",
            "--template-bank", bank_path,
            "--store-id", "synthetic-second-store",
            "--invoice-id", "e26-e20-exam-invoice",
            "--invoice", "docs/extraction-bridge/golden-pack/v1/fixtures/e20-candidate-invoice.json",
            "--observation", "docs/extraction-bridge/golden-pack/v1/fixtures/e20-new-layout-observation.json",
            "--accepted-invoice-count", "4",
            "--template-bank-locked",
            "--d14-agreement-signed",
            "--extraction-confidence", "0.99",
            "--detected-at", FIXED_TIME,
            "--exported-at", FIXED_TIME,
            "--output", candidate_path,
        ], 120)
        _assert_exit("onboard-register-type", register_result, 10)
        if register_result.stdout or not register_result.stderr.startswith(b"NEW_TYPE REVIEW "):
            raise AssertionError("onboard register-type stream behavior differs from contract")
        candidate_bytes = candidate_path.read_bytes()
        candidate = _schema(ROOT / "schemas" / "mode-b" / "v1" / "new-type-candidate.schema.json", candidate_bytes, "new-type candidate")
        if candidate.get("candidate", {}).get("state") != "PROPOSED":
            raise AssertionError("new-type candidate must remain PROPOSED")
        report["commands"].append({
            "id": "onboard-register-type-e20",
            "exit_code": register_result.returncode,
            "stderr_bytes": len(register_result.stderr),
            "artifact": _compare_bytes("new-type candidate", candidate_bytes, "onboard-new-type-candidate.json"),
        })

    report["status"] = "PASS"
    return report


def _write_report(path: Path | None, value: dict[str, Any], *, markdown: bool = False) -> None:
    if path is None:
        return
    if markdown:
        lines = [
            "# E-30 extraction-bridge golden-pack verification",
            "",
            f"- Status: **{value['status']}**",
            f"- Executor: `{value['executor']}`",
            f"- Contract: `{value['contract']}`",
            "",
            "| Command | Exit | Compared outputs |",
            "|---|---:|---|",
        ]
        for item in value.get("commands", []):
            outputs = item.get("artifact", item.get("stdout", {}))
            if item.get("sidecar"):
                outputs = {"stdout_sha256": item.get("stdout_sha256"), "sidecar": item["sidecar"]}
            lines.append(f"| {item['id']} | {item['exit_code']} | `{json.dumps(outputs, sort_keys=True)}` |")
        payload = ("\n".join(lines) + "\n").encode("utf-8")
    else:
        payload = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, help="built CLI executable; omit to run the source Python CLI")
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    args = parser.parse_args(argv)
    executable = args.exe.resolve() if args.exe is not None else None
    if executable is not None and not executable.is_file():
        print(f"ERROR: frozen executable does not exist: {executable}", file=sys.stderr)
        return 1
    try:
        report = verify(executable)
    except Exception as exc:
        report = {
            "status": "FAIL",
            "contract": "e30.extraction-bridge.v1",
            "executor": "source CLI" if executable is None else "PyInstaller one-folder executable",
            "commands": [],
            "failure": f"{type(exc).__name__}: {exc}",
        }
    _write_report(args.report_json, report)
    _write_report(args.report_md, report, markdown=True)
    if report.get("status") != "PASS":
        print(report.get("failure", "golden-pack verification failed"), file=sys.stderr)
        return 1
    for item in report["commands"]:
        print(f"PASS {item['id']} exit={item['exit_code']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
