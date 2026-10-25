#!/usr/bin/env python3
"""Smoke-test a frozen one-folder CLI against the four real fixture invoices.

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

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_IDS = ("29", "31", "32", "33")
E01_SCHEMA = REPO_ROOT / "schemas" / "canonical_invoice_v0.json"
E11_SCHEMA = REPO_ROOT / "contracts" / "canonical_invoice_v0.schema.json"
E11_DRAFT_GOLDEN = (
    REPO_ROOT / "contracts" / "goldens" / "valid" /
    "draft_mode_b_null_display_number.json"
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


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
                if result.returncode != 0 or "--image" not in result.stdout:
                    raise AssertionError(
                        "frozen extract --help failed: "
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
                context_path.write_text(
                    json.dumps(context, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
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
