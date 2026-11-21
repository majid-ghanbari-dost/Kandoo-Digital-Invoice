#!/usr/bin/env python3
"""Smoke-test the frozen CLI on fixture extraction and the E-26 E-20 flow.

The E-01 CLI and the immutable E-11 contract do not share an identical wire
schema. This test therefore compares extracted business values to the matching
label-derived real-fixture Canonical objects, then performs an explicit,
test-only E-01 -> E-11 projection and validates its structure against the
frozen E-11 schema and draft golden. It never edits or claims byte equality
with the unrelated synthetic E-11 golden values.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_IDS = ("29", "31", "32", "33")
E01_SCHEMA = REPO_ROOT / "schemas" / "canonical_invoice_v0.json"
E11_SCHEMA = REPO_ROOT / "contracts" / "canonical_invoice_v0.schema.json"
E11_DRAFT_GOLDEN = (
    REPO_ROOT / "contracts" / "goldens" / "valid" /
    "draft_mode_b_null_display_number.json"
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def _validate_mode_b_artifact(repo_root: Path, path: Path, schema_name: str) -> dict[str, Any]:
    schema_path = repo_root / "schemas" / "mode-b" / "v1" / schema_name
    schema = _read_json(schema_path)
    artifact = _read_json(path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda error: list(error.absolute_path))
    if errors:
        raise AssertionError(f"{path.name} fails {schema_name}: {errors[0].message}")
    return artifact


def _run_onboard_e20_smoke(
    exe: Path,
    repo_root: Path,
    work_dir: Path,
    report: dict[str, Any],
) -> None:
    """Exercise the frozen E-26 CLI through all three commands on E-20 data."""
    from prepare_e26_e20_smoke_inputs import prepare_e26_e20_inputs

    inputs = prepare_e26_e20_inputs(repo_root, work_dir / "e20-inputs")
    fixed_time = "2026-10-28T00:00:00Z"
    bank_path = work_dir / "e20-template-bank.json"
    verdict_path = work_dir / "e20-onboarding-verdict.json"
    candidate_path = work_dir / "e20-new-type-candidate.json"
    e20_report = repo_root / "docs" / "e20-second-store.json"
    expected_values = repo_root / "docs" / "E-03-kit-v3" / "expected-values.json"
    store_id = "synthetic-second-store"

    build = subprocess.run(
        [
            str(exe), "onboard", "build",
            "--synthetic-e20-report", str(e20_report.resolve()),
            "--synthetic-e20-values", str(expected_values.resolve()),
            "--store-id", store_id,
            "--currency-unit", "rial",
            "--created-at", fixed_time,
            "--output", str(bank_path.resolve()),
        ],
        cwd=work_dir,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if build.returncode != 0:
        raise AssertionError(
            "frozen onboard build failed: "
            f"exit={build.returncode}; stderr={build.stderr.decode('utf-8', errors='replace')[-2500:]}"
        )
    bank_artifact = _validate_mode_b_artifact(repo_root, bank_path, "template-bank.schema.json")
    if bank_artifact.get("store_id") != store_id:
        raise AssertionError("frozen onboard build used an unexpected E-20 store ID")

    verdict = subprocess.run(
        [
            str(exe), "onboard", "verdict",
            "--template-bank", str(bank_path.resolve()),
            "--store-id", store_id,
            "--invoice-id", "e26-e20-exam-pipeline",
            "--observation", str(inputs["pipeline_observation"].resolve()),
            "--processed-invoice-count", "0",
            "--template-bank-unlocked",
            "--d14-agreement-required",
            "--no-require-kit-digit-coverage",
            "--extraction-confidence", "0.0",
            "--missing-field", "line.0.quantity",
            "--missing-field", "line.0.total",
            "--missing-field", "line.1.total",
            "--missing-field", "invoice.payable",
            "--evaluated-at", fixed_time,
            "--output", str(verdict_path.resolve()),
        ],
        cwd=work_dir,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if verdict.returncode != 10:
        raise AssertionError(
            "frozen onboard verdict did not hold the E-20 candidate for review: "
            f"exit={verdict.returncode}; stderr={verdict.stderr.decode('utf-8', errors='replace')[-2500:]}"
        )
    verdict_artifact = _validate_mode_b_artifact(
        repo_root, verdict_path, "onboarding-verdict.schema.json"
    )
    bank_sha256 = hashlib.sha256(bank_path.read_bytes()).hexdigest()
    if verdict_artifact.get("template_bank_sha256") != bank_sha256:
        raise AssertionError("onboard verdict did not bind to the exact E-16 bank bytes")
    if verdict_artifact.get("store_id") != store_id or verdict_artifact.get("result", {}).get("verdict") != "REVIEW":
        raise AssertionError("onboard verdict did not preserve the E-20 review outcome")

    register = subprocess.run(
        [
            str(exe), "onboard", "register-type",
            "--template-bank", str(bank_path.resolve()),
            "--store-id", store_id,
            "--invoice-id", "e26-e20-exam-invoice",
            "--invoice", str(inputs["candidate_invoice"].resolve()),
            "--observation", str(inputs["new_layout_observation"].resolve()),
            "--accepted-invoice-count", "4",
            "--template-bank-locked",
            "--d14-agreement-signed",
            "--extraction-confidence", "0.99",
            "--detected-at", fixed_time,
            "--exported-at", fixed_time,
            "--output", str(candidate_path.resolve()),
        ],
        cwd=work_dir,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if register.returncode != 10:
        raise AssertionError(
            "frozen onboard register-type did not return the expected review result: "
            f"exit={register.returncode}; stderr={register.stderr.decode('utf-8', errors='replace')[-2500:]}"
        )
    candidate_artifact = _validate_mode_b_artifact(
        repo_root, candidate_path, "new-type-candidate.schema.json"
    )
    candidate = candidate_artifact.get("candidate", {})
    if (
        candidate_artifact.get("store_id") != store_id
        or candidate.get("store_id") != store_id
        or candidate.get("state") != "PROPOSED"
    ):
        raise AssertionError("onboard register-type did not export a store-scoped PROPOSED candidate")

    report["onboarding_e20"] = {
        "status": "PASS",
        "store_id": store_id,
        "synthetic_only": True,
        "build": {
            "exit_code": build.returncode,
            "artifact": "template-bank.schema.json",
            "stderr": build.stderr.decode("utf-8", errors="replace")[-1000:],
        },
        "verdict": {
            "exit_code": verdict.returncode,
            "artifact": "onboarding-verdict.schema.json",
            "verdict": verdict_artifact["result"]["verdict"],
            "template_bank_sha256": bank_sha256,
        },
        "register_type": {
            "exit_code": register.returncode,
            "artifact": "new-type-candidate.schema.json",
            "candidate_id": candidate["candidate_id"],
            "candidate_state": candidate["state"],
        },
        "evidence_boundary": (
            "E-20 report and E-03 answer key are synthetic mechanics fixtures; "
            "the proposed changed-layout candidate is not installed in the active bank."
        ),
    }


def _capture_numeric_values_match(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    from e05_template_bank import parse_labeled_integer

    candidates = actual.get("numeric_candidates", {})
    expected_items = expected.get("line_items", [])
    for kind, field in (("quantity", "quantity"), ("line_total", "line_total")):
        values = sorted(candidates.get(kind, []), key=lambda item: item.get("line_index", -1))
        if len(values) != len(expected_items):
            raise AssertionError(
                f"capture {kind} candidate count differs: output={len(values)} expected={len(expected_items)}"
            )
        for index, (candidate, expected_item) in enumerate(zip(values, expected_items, strict=True)):
            if candidate.get("status") != "EXTRACTED":
                raise AssertionError(
                    f"capture line {index} {kind} is not EXTRACTED: {candidate.get('status')}"
                )
            observed = parse_labeled_integer(candidate.get("raw_value", ""))
            expected_value = expected_item.get(field)
            if observed != expected_value:
                raise AssertionError(
                    f"capture line {index} {kind} differs: output={observed!r} expected={expected_value!r}"
                )

    payable = candidates.get("payable", [])
    if len(payable) != 1 or payable[0].get("status") != "EXTRACTED":
        raise AssertionError("capture payable must have exactly one EXTRACTED candidate")
    observed_payable = parse_labeled_integer(payable[0].get("raw_value", ""))
    expected_payable = expected.get("summary", {}).get("payable")
    if observed_payable != expected_payable:
        raise AssertionError(
            f"capture payable differs: output={observed_payable!r} expected={expected_payable!r}"
        )

    expected_subtotal = expected.get("summary", {}).get("subtotal")
    observed_subtotal = sum(
        parse_labeled_integer(candidate.get("raw_value", ""))
        for candidate in candidates.get("line_total", [])
    )
    if observed_subtotal != expected_subtotal:
        raise AssertionError(
            f"capture subtotal differs: sum(line totals)={observed_subtotal!r} expected={expected_subtotal!r}"
        )


def _run_e27_capture_folder_smoke(
    exe: Path,
    repo_root: Path,
    work_dir: Path,
    report: dict[str, Any],
) -> None:
    """Run E-12 capture-folder mode against fixture goldens and failure cases."""
    from prepare_e27_capture_smoke import prepare_e27_capture_folders

    inputs = prepare_e27_capture_folders(repo_root, work_dir / "e27-capture-inputs")
    valid_results: list[dict[str, Any]] = []
    for case in inputs["valid"]:
        fixture_id = case["fixture_id"]
        output_path = work_dir / f"e27-capture-{fixture_id}.json"
        result = subprocess.run(
            [
                str(exe), "extract",
                "--capture-folder", case["folder"],
                "--out", str(output_path.resolve()),
            ],
            cwd=work_dir,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 10:
            raise AssertionError(
                f"E-27 valid capture {fixture_id} expected exit 10, got {result.returncode}: "
                f"{result.stderr.decode('utf-8', errors='replace')[-2500:]}"
            )
        actual = _read_json(output_path)
        expected = _read_json(Path(case["canonical_golden"]))
        if actual.get("status") != "REVIEW" or actual.get("verdict") != "REVIEW":
            raise AssertionError(f"E-27 valid capture {fixture_id} did not fail closed to REVIEW")
        if actual.get("captured_at") != case["captured_at"]:
            raise AssertionError(
                f"E-27 capture {fixture_id} did not read captured_at from Report.txt: "
                f"{actual.get('captured_at')!r}"
            )
        if actual.get("artifacts", {}).get("probe_metadata", {}).get("captured_at") != case["captured_at"]:
            raise AssertionError(f"E-27 capture {fixture_id} did not inventory its report timestamp")
        _capture_numeric_values_match(actual, expected)
        valid_results.append({
            "fixture_id": fixture_id,
            "exit_code": result.returncode,
            "status": actual["status"],
            "captured_at": actual["captured_at"],
            "canonical_golden": str(Path(case["canonical_golden"]).relative_to(repo_root)),
            "canonical_numeric_match": True,
        })

    failure_results: list[dict[str, Any]] = []
    for case in inputs["failures"]:
        output_path = work_dir / f"e27-failure-{case['case']}.json"
        result = subprocess.run(
            [
                str(exe), "extract",
                "--capture-folder", case["folder"],
                "--out", str(output_path.resolve()),
            ],
            cwd=work_dir,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 20:
            raise AssertionError(
                f"E-27 failure {case['case']} expected stable exit 20, got {result.returncode}: "
                f"{result.stderr.decode('utf-8', errors='replace')[-2500:]}"
            )
        actual = _read_json(output_path)
        error_codes = [error.get("code") for error in actual.get("errors", [])]
        if actual.get("status") != "BLOCKED" or actual.get("verdict") != "REVIEW":
            raise AssertionError(f"E-27 failure {case['case']} did not return BLOCKED / REVIEW")
        if case["expected_error_code"] not in error_codes:
            raise AssertionError(
                f"E-27 failure {case['case']} missing {case['expected_error_code']}; "
                f"observed error codes: {error_codes}"
            )
        failure_results.append({
            "case": case["case"],
            "exit_code": result.returncode,
            "status": actual["status"],
            "verdict": actual["verdict"],
            "expected_error_code": case["expected_error_code"],
            "observed_error_codes": error_codes,
        })

    report["e27_capture_folder"] = {
        "status": "PASS",
        "adapter": "built Windows executable: extract --capture-folder (E-12)",
        "synthetic_report_and_spl": True,
        "valid_fixture_golden_comparisons": valid_results,
        "failure_cases": failure_results,
        "evidence_boundary": (
            "Repository real-render fixture PNGs and label-derived Canonical JSON goldens were used; "
            "SPL bytes and Report.txt fields are synthetic harness data, not authentic Probe output."
        ),
    }


def _context_for(expected: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    """Build explicitly synthetic producer context; no real identities are used."""
    row_count = len(expected["line_items"])
    return {
        "mode": "B",
        "invoice_id": f"windows-build-synthetic-{fixture_id}",
        "display_number": f"WINDOWS-SYN-{fixture_id}",
        "operation_id": f"windows-build-operation-{fixture_id}",
        "device_id": "windows-build-synthetic-device",
        "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
        "store_id": "windows-build-synthetic-store",
        "customer": {
            "phone": "+15551234567",
            "phone_status": "claimed",
            "phone_provenance": "captured",
        },
        "product_names": [f"Synthetic Windows build item {index + 1}" for index in range(row_count)],
        "product_name_provenance": ["untrusted"] * row_count,
    }


def _project_e01_to_e11(invoice: dict[str, Any]) -> dict[str, Any]:
    """Apply the documented test-only contract crosswalk; never alter CLI JSON."""
    projected = copy.deepcopy(invoice)
    provenance_fields = projected["provenance"]["fields"]
    projected["display_number"] = None
    provenance_fields["display_number"] = "unavailable"

    line_provenance = provenance_fields["line_items"]
    for item, labels in zip(projected["line_items"], line_provenance, strict=True):
        quantity = item.pop("quantity")
        item["quantity_millis"] = quantity * 1000
        labels["quantity_millis"] = labels.pop("quantity")
    return projected


def _shape_snapshot(invoice: dict[str, Any]) -> dict[str, Any]:
    """Compare the contract-bearing object shapes, not synthetic example values."""
    fields = invoice["provenance"]["fields"]
    return {
        "top_level": sorted(invoice),
        "customer": sorted(invoice["customer"]),
        "line_item": sorted(invoice["line_items"][0]),
        "summary": sorted(invoice["summary"]),
        "header": sorted(invoice["header"]),
        "provenance": sorted(invoice["provenance"]),
        "provenance_fields": sorted(fields),
        "provenance_customer": sorted(fields["customer"]),
        "provenance_line_item": sorted(fields["line_items"][0]),
        "provenance_summary": sorted(fields["summary"]),
    }


def _numeric_values_match(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    actual_items = actual.get("line_items", [])
    expected_items = expected.get("line_items", [])
    if len(actual_items) != len(expected_items):
        raise AssertionError(
            f"row count differs: output={len(actual_items)} expected={len(expected_items)}"
        )
    for index, (got, want) in enumerate(zip(actual_items, expected_items, strict=True)):
        for field in ("quantity", "line_total"):
            if got.get(field) != want.get(field):
                raise AssertionError(
                    f"line {index} {field} differs: output={got.get(field)!r} "
                    f"expected={want.get(field)!r}"
                )
    for field in ("subtotal", "payable"):
        if actual.get("summary", {}).get(field) != expected.get("summary", {}).get(field):
            raise AssertionError(
                f"summary.{field} differs: output={actual.get('summary', {}).get(field)!r} "
                f"expected={expected.get('summary', {}).get(field)!r}"
            )


def _write_reports(
    json_path: Path,
    markdown_path: Path,
    report: dict[str, Any],
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    json_path.write_bytes(json_payload)
    lines = [
        "# Windows one-folder build evidence",
        "",
        f"- Status: **{report['status']}**",
        f"- Python: `{report.get('python_version', 'not recorded')}`",
        f"- PyInstaller: `{report.get('pyinstaller_version', 'not recorded')}`",
        f"- Executable size: {report.get('executable_size_bytes', 'not recorded')} bytes "
        f"({report.get('executable_size_mib', 'not recorded')} MiB)",
        f"- One-folder bundle size: {report.get('bundle_size_bytes', 'not recorded')} bytes "
        f"({report.get('bundle_size_mib', 'not recorded')} MiB)",
        f"- Bundle files: {report.get('bundle_file_count', 'not recorded')}",
        f"- Startup (`extract --help`, {len(report.get('startup_seconds', []))} launches): "
        f"median {report.get('startup_median_seconds', 'not recorded')} s; "
        f"min {report.get('startup_min_seconds', 'not recorded')} s; "
        f"max {report.get('startup_max_seconds', 'not recorded')} s",
        f"- Tesseract executable present: `{report.get('tesseract_executable_present', 'not recorded')}`",
        f"- `tesserocr` importable: `{report.get('tesserocr_importable', 'not recorded')}`",
        "- Glyph path: built `extract` ran four real fixture images without passing a template path; "
        "the bundled default Glyph bank was used.",
        "",
        "## Per-fixture smoke",
        "",
        "| Fixture | Exit | State | Rows | Payable | Numeric match | Runtime (s) |",
        "|---|---:|---|---:|---:|---|---:|",
    ]
    for item in report.get("fixtures", []):
        lines.append(
            f"| {item['fixture_id']} | {item.get('exit_code', '—')} | "
            f"{item.get('state', '—')} | {item.get('row_count', '—')} | "
            f"{item.get('payable', '—')} | {item.get('numeric_match', '—')} | "
            f"{item.get('runtime_seconds', '—')} |"
        )
    lines.extend(["", "## E-26 onboarding CLI / E-20 synthetic flow", ""])
    if report.get("onboard_help"):
        lines.append(
            f"- Frozen `onboard --help`: exit {report['onboard_help']['exit_code']}; "
            f"commands present: `{report['onboard_help']['commands_present']}`."
        )
    onboarding = report.get("onboarding_e20")
    if onboarding:
        lines.extend([
            f"- Flow status: **{onboarding['status']}**; store `{onboarding['store_id']}`; synthetic only: `{onboarding['synthetic_only']}`.",
            f"- Built-executable commands: `build` exit {onboarding['build']['exit_code']}; "
            f"`verdict` exit {onboarding['verdict']['exit_code']} ({onboarding['verdict']['verdict']}); "
            f"`register-type` exit {onboarding['register_type']['exit_code']} "
            f"(candidate {onboarding['register_type']['candidate_state']}).",
            f"- E-16 bank SHA-256 bound into verdict: `{onboarding['verdict']['template_bank_sha256']}`.",
            f"- Evidence boundary: {onboarding['evidence_boundary']}",
        ])
    else:
        lines.append("- Flow status: **not completed**; see the failure detail below.")
    capture_smoke = report.get("e27_capture_folder")
    lines.extend(["", "## E-27 capture-folder adapter smoke", ""])
    if capture_smoke:
        lines.append(
            f"- Status: **{capture_smoke['status']}**; executable path: `{capture_smoke['adapter']}`; "
            f"synthetic report/SPL: `{capture_smoke['synthetic_report_and_spl']}`."
        )
        lines.extend([
            "",
            "| Fixture | Exit | Status | Report captured_at | Canonical numeric match |",
            "|---|---:|---|---|---|",
        ])
        for item in capture_smoke["valid_fixture_golden_comparisons"]:
            lines.append(
                f"| {item['fixture_id']} | {item['exit_code']} | {item['status']} | "
                f"`{item['captured_at']}` | {item['canonical_numeric_match']} |"
            )
        lines.extend([
            "",
            "| Failure case | Exit | Status | Verdict | Expected error | Observed errors |",
            "|---|---:|---|---|---|---|",
        ])
        for item in capture_smoke["failure_cases"]:
            lines.append(
                f"| {item['case']} | {item['exit_code']} | {item['status']} | {item['verdict']} | "
                f"{item['expected_error_code']} | {', '.join(item['observed_error_codes'])} |"
            )
        lines.extend([
            "",
            f"- Evidence boundary: {capture_smoke['evidence_boundary']}",
        ])
    else:
        lines.append("- Status: **not completed**; see the failure detail below.")
    lines.extend([
        "",
        "## Contract comparison boundary",
        "",
        "The executable emits the existing E-01 Canonical shape (`quantity`). Each output was compared "
        "field-by-field for quantities, line totals, subtotal, and payable against its matching, "
        "label-derived real-fixture canonical object. A separate test-only projection maps integer "
        "quantity to `quantity_millis = quantity × 1000` and marks the pre-ISSUE display number "
        "unavailable; it is validated against the frozen E-11 schema and checked for contract-key "
        "shape against `draft_mode_b_null_display_number.json`. E-11's synthetic example values are "
        "not claimed as expected output for these four real images, and no file under `contracts/` "
        "is modified.",
        "",
    ])
    if report.get("failure"):
        lines.extend(["## Failure", "", f"`{report['failure']}`", ""])
    markdown_path.write_bytes("\n".join(lines).encode("utf-8"))


def run(exe: Path, repo_root: Path, report_json: Path, report_md: Path) -> int:
    exe = exe.resolve()
    report: dict[str, Any] = {
        "status": "FAIL",
        "python_version": sys.version.split()[0],
        "executable": str(exe.resolve()),
        "fixtures": [],
        "startup_seconds": [],
        "e11_comparison": {
            "method": "test-only E-01 to E-11 projection; not byte-for-byte equality",
            "expected_value_source": "per-fixture label-derived real canonical JSON",
            "e11_schema": str(E11_SCHEMA.relative_to(repo_root)),
            "e11_reference_golden": str(E11_DRAFT_GOLDEN.relative_to(repo_root)),
        },
    }
    if importlib.util.find_spec("PyInstaller") is not None:
        try:
            import PyInstaller  # type: ignore[import-not-found]
            report["pyinstaller_version"] = getattr(PyInstaller, "__version__", "unknown")
        except Exception:
            report["pyinstaller_version"] = "unknown"

    try:
        if not exe.is_file():
            raise FileNotFoundError(f"frozen executable not found: {exe}")
        tesseract_path = shutil.which("tesseract")
        try:
            tesserocr_present = importlib.util.find_spec("tesserocr") is not None
        except (ImportError, ValueError):
            tesserocr_present = False
        report["tesseract_executable_present"] = tesseract_path is not None
        report["tesserocr_importable"] = tesserocr_present
        if tesseract_path is not None or tesserocr_present:
            raise AssertionError(
                "Tesseract or tesserocr is present on the runner; the no-Tesseract build proof is inconclusive"
            )

        executable_size = exe.stat().st_size
        report["executable_size_bytes"] = executable_size
        report["executable_size_mib"] = round(executable_size / (1024 * 1024), 3)
        bundle_dir = exe.parent
        bundle_files = [path for path in bundle_dir.rglob("*") if path.is_file()]
        bundle_size = sum(path.stat().st_size for path in bundle_files)
        report["bundle_size_bytes"] = bundle_size
        report["bundle_size_mib"] = round(bundle_size / (1024 * 1024), 3)
        report["bundle_file_count"] = len(bundle_files)

        with tempfile.TemporaryDirectory(prefix="kandoo-windows-smoke-") as temp_name:
            cwd = Path(temp_name)
            startup: list[float] = []
            for _ in range(5):
                started = time.perf_counter()
                result = subprocess.run(
                    [str(exe), "extract", "--help"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    check=False,
                )
                elapsed = time.perf_counter() - started
                startup.append(elapsed)
                if (
                    result.returncode != 0
                    or "--image" not in result.stdout
                    or "--capture-folder" not in result.stdout
                ):
                    raise AssertionError(
                        "frozen extract --help failed or omitted capture-folder mode: "
                        f"exit={result.returncode}; stderr={result.stderr[-1200:]}"
                    )
            report["startup_seconds"] = [round(value, 4) for value in startup]
            report["startup_min_seconds"] = round(min(startup), 4)
            report["startup_median_seconds"] = round(statistics.median(startup), 4)
            report["startup_max_seconds"] = round(max(startup), 4)

            e01_validator = Draft202012Validator(_read_json(E01_SCHEMA))
            e11_validator = Draft202012Validator(_read_json(E11_SCHEMA))
            e11_golden = _read_json(E11_DRAFT_GOLDEN)
            reference_shape = _shape_snapshot(e11_golden)
            fixture_dir = repo_root / "tests" / "fixtures" / "real"
            canonical_dir = fixture_dir / "canonical"
            for fixture_id in FIXTURE_IDS:
                expected = _read_json(canonical_dir / f"canonical-{fixture_id}.json")
                context = _context_for(expected, fixture_id)
                context_path = cwd / f"context-{fixture_id}.json"
                context_payload = (json.dumps(context, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                context_path.write_bytes(context_payload)
                command = [
                    str(exe),
                    "extract",
                    "--image",
                    str((fixture_dir / f"{fixture_id}.png").resolve()),
                    "--context",
                    str(context_path.resolve()),
                ]
                started = time.perf_counter()
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    capture_output=True,
                    timeout=180,
                    check=False,
                )
                elapsed = time.perf_counter() - started
                item: dict[str, Any] = {
                    "fixture_id": fixture_id,
                    "exit_code": result.returncode,
                    "runtime_seconds": round(elapsed, 4),
                    "stderr": result.stderr.decode("utf-8", errors="replace")[-2000:],
                }
                report["fixtures"].append(item)
                if result.returncode != 0:
                    raise AssertionError(
                        f"fixture {fixture_id} extract exit={result.returncode}: "
                        f"{item['stderr']}"
                    )
                actual = json.loads(result.stdout.decode("utf-8"))
                errors = list(e01_validator.iter_errors(actual))
                if errors:
                    raise AssertionError(
                        f"fixture {fixture_id} output fails the current E-01 schema: "
                        f"{errors[0].message}"
                    )
                _numeric_values_match(actual, expected)
                item.update({
                    "state": actual.get("state"),
                    "row_count": len(actual.get("line_items", [])),
                    "payable": actual.get("summary", {}).get("payable"),
                    "numeric_match": True,
                })
                projection = _project_e01_to_e11(actual)
                e11_errors = list(e11_validator.iter_errors(projection))
                if e11_errors:
                    raise AssertionError(
                        f"fixture {fixture_id} E-11 test-only projection fails frozen schema: "
                        f"{e11_errors[0].message}"
                    )
                if _shape_snapshot(projection) != reference_shape:
                    raise AssertionError(
                        f"fixture {fixture_id} E-11 projection key shape differs from the E-11 draft golden"
                    )

            onboard_help = subprocess.run(
                [str(exe), "onboard", "--help"],
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
            commands_present = all(
                command in onboard_help.stdout for command in ("build", "verdict", "register-type")
            )
            if onboard_help.returncode != 0 or not commands_present:
                raise AssertionError(
                    "frozen onboard --help failed or omitted a command: "
                    f"exit={onboard_help.returncode}; stdout={onboard_help.stdout[-1200:]}; "
                    f"stderr={onboard_help.stderr[-1200:]}"
                )
            report["onboard_help"] = {
                "exit_code": onboard_help.returncode,
                "commands_present": commands_present,
            }
            _run_onboard_e20_smoke(exe, repo_root, cwd, report)
            _run_e27_capture_folder_smoke(exe, repo_root, cwd, report)

        report["status"] = "PASS"
        report["tesseract_absence_proof"] = (
            "tesseract executable and tesserocr module were both absent; no Tesseract dependency was installed"
        )
    except Exception as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
    finally:
        _write_reports(report_json, report_md, report)
    fixtures_summary = ",".join(
        f"{item['fixture_id']}:{item.get('numeric_match', False)}"
        for item in report.get("fixtures", [])
    ) or "none"
    notice = (
        f"status={report['status']}; exe_bytes={report.get('executable_size_bytes', 'n/a')}; "
        f"exe_mib={report.get('executable_size_mib', 'n/a')}; "
        f"bundle_bytes={report.get('bundle_size_bytes', 'n/a')}; "
        f"bundle_mib={report.get('bundle_size_mib', 'n/a')}; "
        f"startup_median_s={report.get('startup_median_seconds', 'n/a')}; "
        f"startup_min_s={report.get('startup_min_seconds', 'n/a')}; "
        f"startup_max_s={report.get('startup_max_seconds', 'n/a')}; "
        f"fixtures={fixtures_summary}; "
        f"tesseract_present={report.get('tesseract_executable_present', 'n/a')}; "
        f"tesserocr_present={report.get('tesserocr_importable', 'n/a')}"
    )
    print(f"::notice title=Windows one-folder evidence::{notice}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True, help="path to the frozen CLI executable")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.exe, args.repo_root.resolve(), args.report_json, args.report_md)


if __name__ == "__main__":
    raise SystemExit(main())
