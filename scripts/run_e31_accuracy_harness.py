#!/usr/bin/env python3
"""Run E-31 accuracy and timing checks across every labeled real invoice.

Accuracy uses a four-fold leave-one-fixture-out Glyph evaluation: each image is
classified with templates built from the other three images, and template
provenance overlap is rejected. The E-30 CLI is separately smoke-tested and
timed (source mode on Ubuntu; the frozen executable on Windows CI). Synthetic
producer context is used only at that CLI boundary, never as accuracy evidence.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from e05_template_bank import parse_labeled_integer  # noqa: E402
from image_extraction_adapter.canonical_invoice import validate_canonical_invoice  # noqa: E402
from image_extraction_adapter.pipeline_v0 import (  # noqa: E402
    REPOSITORY_ROOT,
    _execute_pipeline,
    _source_records_from_bank,
    _template_set_sha256,
    build_templates_for_fold,
)

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "real"
LABELS_PATH = FIXTURE_DIR / "labels.json"
FIXED_CAPTURED_AT = "2026-10-30T00:00:00Z"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
EXIT_FOR_STATUS = {"AUTO_CANDIDATE": 0, "REVIEW": 10, "REJECT": 20}
ROUTE_FOR_STATUS = {"AUTO_CANDIDATE": "EXTRACTED", "REVIEW": "REVIEW", "REJECT": "BLOCKED"}
NUMERIC_STATUSES = ("EXTRACTED", "REVIEW", "BLOCKED")
RUNTIME_ROUTE_FOR_EXIT = {0: "EXTRACTED", 10: "REVIEW", 20: "BLOCKED"}


def _context(fixture_id: str, row_count: int) -> dict[str, Any]:
    """Return explicitly synthetic producer context for CLI mechanics only."""
    return {
        "mode": "B",
        "invoice_id": f"e31-synthetic-invoice-{fixture_id}",
        "display_number": f"E31-SYN-{fixture_id}",
        "operation_id": f"e31-synthetic-operation-{fixture_id}",
        "device_id": "e31-synthetic-device",
        "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
        "store_id": "e31-synthetic-store",
        "customer": {
            "phone": "+15551234567",
            "phone_status": "claimed",
            "phone_provenance": "captured",
        },
        "product_names": [f"Synthetic E31 fixture {fixture_id} item {index + 1}" for index in range(row_count)],
        "product_name_provenance": ["untrusted"] * row_count,
    }


def _write_json_bytes(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    path.write_bytes(payload.encode("utf-8"))


def _read_labels_and_confirm_inventory() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(LABELS_PATH.read_bytes().decode("utf-8"))
    if payload.get("label_status") != "OPERATOR_CONFIRMED":
        raise AssertionError("real-fixture labels are not marked OPERATOR_CONFIRMED")
    fixtures = payload.get("invoices")
    if not isinstance(fixtures, list) or not fixtures:
        raise AssertionError("real-fixture labels contain no invoices")

    ids = [str(fixture.get("id")) for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise AssertionError("real-fixture labels contain duplicate invoice IDs")
    label_paths: list[str] = []
    for fixture in fixtures:
        raw_path = fixture.get("path")
        if not isinstance(raw_path, str):
            raise AssertionError(f"fixture {fixture.get('id')} has no relative image path")
        relative = Path(raw_path)
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            raise AssertionError(f"invoice fixture path must be a top-level relative filename: {raw_path!r}")
        label_paths.append(relative.as_posix())

    root_images = sorted(
        path.name for path in FIXTURE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    nested_images = sorted(
        path.relative_to(FIXTURE_DIR).as_posix()
        for path in FIXTURE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES and path.parent != FIXTURE_DIR
    )
    if len(label_paths) != len(set(label_paths)):
        raise AssertionError("real-fixture labels refer to the same image more than once")
    if set(root_images) != set(label_paths):
        raise AssertionError(
            "complete real-invoice inventory mismatch: "
            f"unlabeled={sorted(set(root_images) - set(label_paths))}; "
            f"missing={sorted(set(label_paths) - set(root_images))}"
        )
    if any(not path.startswith("n02-reference-crops/") for path in nested_images):
        raise AssertionError(
            "unexpected nested real-fixture image found; review whether it is an invoice input "
            "or a derived reference crop before publishing metrics"
        )

    inventory = {
        "labels_file": str(LABELS_PATH.relative_to(ROOT)),
        "invoice_images": root_images,
        "invoice_fixture_count": len(root_images),
        "nested_non_invoice_reference_crops_excluded": nested_images,
        "selection_rule": (
            "Every top-level image in tests/fixtures/real must appear exactly once in labels.json. "
            "Images nested under n02-reference-crops are derived row crops, not invoice fixtures."
        ),
    }
    return fixtures, inventory


def _expected_numeric_values(fixture: dict[str, Any]) -> dict[str, int]:
    values = fixture.get("values")
    if not isinstance(values, dict) or not values:
        raise AssertionError(f"fixture {fixture.get('id')} has no expected numeric labels")
    parsed: dict[str, int] = {}
    for field, text in values.items():
        field = str(field)
        if not (field.endswith(".quantity") or field.endswith(".total") or field == "invoice.payable"):
            continue
        try:
            parsed[field] = parse_labeled_integer(str(text))
        except (TypeError, ValueError) as exc:
            raise AssertionError(
                f"fixture {fixture.get('id')} label {field} is not a strict integer: {text!r}"
            ) from exc
    if not parsed or "invoice.payable" not in parsed:
        raise AssertionError(f"fixture {fixture.get('id')} lacks numeric quantity/total/payable labels")
    return parsed


def _compare_cli_invoice(invoice: dict[str, Any], expected: dict[str, int], fixture_id: str) -> list[str]:
    items = invoice.get("line_items")
    if not isinstance(items, list):
        raise AssertionError(f"fixture {fixture_id}: Canonical output has no line_items array")
    expected_rows = sum(field.endswith(".quantity") for field in expected)
    if len(items) != expected_rows:
        raise AssertionError(f"fixture {fixture_id}: output rows={len(items)} expected={expected_rows}")
    wrong_fields: list[str] = []
    for index, item in enumerate(items):
        for output_field, label_field in (
            ("quantity", f"line.{index}.quantity"),
            ("line_total", f"line.{index}.total"),
        ):
            if label_field not in expected:
                raise AssertionError(f"fixture {fixture_id}: missing operator label {label_field}")
            if item.get(output_field) != expected[label_field]:
                wrong_fields.append(label_field)
    summary = invoice.get("summary", {})
    if summary.get("payable") != expected["invoice.payable"]:
        wrong_fields.append("invoice.payable")
    subtotal = sum(value for field, value in expected.items() if field.endswith(".total"))
    if summary.get("subtotal") != subtotal:
        wrong_fields.append("invoice.subtotal")
    return wrong_fields


def _run_process(exe: Path | None, args: Sequence[str | Path], timeout: int = 180) -> subprocess.CompletedProcess[bytes]:
    command = [str(exe)] if exe is not None else [sys.executable, "-m", "image_extraction_adapter.cli"]
    command.extend(str(value) for value in args)
    environment = os.environ.copy()
    paths = [str(ROOT / "src"), str(ROOT / "scripts")]
    if environment.get("PYTHONPATH"):
        paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _run_leave_one_out(fixtures: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Score each held-out fixture only against templates from the other fixtures."""
    outcomes: dict[str, dict[str, Any]] = {}
    totals: dict[str, Any] = {
        "invoice_outcomes": {status: 0 for status in NUMERIC_STATUSES},
        "numeric_cells": {status: 0 for status in NUMERIC_STATUSES},
        "extracted_but_wrong": 0,
        "independent_extracted_label_comparisons": 0,
        "derived_payable_checks": 0,
        "expected_numeric_fields": 0,
    }

    for fixture in fixtures:
        fixture_id = str(fixture["id"])
        image_path = (FIXTURE_DIR / str(fixture["path"])).resolve()
        expected = _expected_numeric_values(fixture)
        templates = build_templates_for_fold(
            LABELS_PATH,
            fixture_id,
            repo_root=REPOSITORY_ROOT,
        )
        sources = _source_records_from_bank({"provenance": templates.provenance})
        result = _execute_pipeline(
            image_path,
            templates=templates,
            template_sources=sources,
            template_library_id=_template_set_sha256(templates),
            template_bank_path=None,
            captured_at=None,
            canonical_context=None,
            evaluation=True,
            repo_root=REPOSITORY_ROOT,
        )
        if result.status not in ROUTE_FOR_STATUS:
            raise AssertionError(f"fixture {fixture_id}: unsupported LOO status {result.status!r}")
        invoice_status = ROUTE_FOR_STATUS[result.status]
        actual_by_field: dict[str, Any] = {}
        for cell in result.cell_results:
            if cell.field_name not in expected:
                continue
            if cell.field_name in actual_by_field:
                raise AssertionError(f"fixture {fixture_id}: duplicate numeric cell {cell.field_name}")
            actual_by_field[cell.field_name] = cell

        cell_counts = {status: 0 for status in NUMERIC_STATUSES}
        wrong_fields: list[str] = []
        independent_comparisons = 0
        derived_payable_checks = 0
        payable_is_derived = bool(fixture.get("payable_label_note"))
        for field_name, expected_value in expected.items():
            cell = actual_by_field.get(field_name)
            if cell is None:
                # Missing numeric output cannot count as an extraction; preserve the
                # invoice-level fail-closed route in the per-expected-field totals.
                cell_status = "BLOCKED" if invoice_status == "BLOCKED" else "REVIEW"
            else:
                cell_status = cell.status
            if cell_status not in cell_counts:
                raise AssertionError(f"fixture {fixture_id}: unsupported cell status {cell_status!r}")
            cell_counts[cell_status] += 1
            if cell_status == "EXTRACTED":
                try:
                    observed = parse_labeled_integer(cell.raw_value)
                except (AttributeError, TypeError, ValueError):
                    observed = None
                if observed != expected_value:
                    wrong_fields.append(field_name)
                if payable_is_derived and field_name == "invoice.payable":
                    derived_payable_checks += 1
                else:
                    independent_comparisons += 1

        if invoice_status == "EXTRACTED" and cell_counts["REVIEW"] + cell_counts["BLOCKED"]:
            raise AssertionError(f"fixture {fixture_id}: EXTRACTED invoice contains non-EXTRACTED numeric fields")
        if sum(cell_counts.values()) != len(expected):
            raise AssertionError(f"fixture {fixture_id}: numeric classification count mismatch")
        if wrong_fields:
            raise AssertionError(
                f"fixture {fixture_id}: EXTRACTED-but-wrong fields: {', '.join(wrong_fields)}"
            )

        invoice_counts = {status: int(status == invoice_status) for status in NUMERIC_STATUSES}
        totals["invoice_outcomes"][invoice_status] += 1
        for status, count in cell_counts.items():
            totals["numeric_cells"][status] += count
        totals["extracted_but_wrong"] += len(wrong_fields)
        totals["independent_extracted_label_comparisons"] += independent_comparisons
        totals["derived_payable_checks"] += derived_payable_checks
        totals["expected_numeric_fields"] += len(expected)
        outcomes[fixture_id] = {
            "fixture_id": fixture_id,
            "image": str(image_path.relative_to(ROOT)),
            "invoice_status": invoice_status,
            "pipeline_status": result.status,
            "invoice_counts": invoice_counts,
            "numeric_cell_counts": cell_counts,
            "expected_numeric_fields": len(expected),
            "emitted_numeric_cells": len(actual_by_field),
            "missing_numeric_fields": sorted(set(expected) - set(actual_by_field)),
            "independent_extracted_label_comparisons": independent_comparisons,
            "derived_payable_checks": derived_payable_checks,
            "extracted_but_wrong": len(wrong_fields),
            "wrong_fields": wrong_fields,
            "arithmetic_gate_passed": bool(result.arithmetic_gate and result.arithmetic_gate.passed),
            "arithmetic_gate_reason": result.arithmetic_gate.reason if result.arithmetic_gate else result.reason,
            "template_library_id": result.template_library_id,
            "canonical_invoice_created": result.canonical_invoice is not None,
        }

    if totals["extracted_but_wrong"] != 0:
        raise AssertionError("E-31 requires zero EXTRACTED-but-wrong fields")
    return outcomes, totals


def run_harness(exe: Path | None = None) -> dict[str, Any]:
    """Run E-30 golden verification, leak-free accuracy checks, and CLI timing."""
    if exe is not None:
        exe = exe.resolve()
        if not exe.is_file():
            raise FileNotFoundError(f"frozen executable not found: {exe}")

    # E-31 consumes E-30's contract and pack; verify the exact same bytes first.
    from verify_e30_golden_pack import verify as verify_e30

    golden_report = verify_e30(exe)
    if golden_report.get("status") != "PASS":
        raise AssertionError(f"E-30 golden pack did not pass: {golden_report.get('failure', 'unknown failure')}")

    fixtures, inventory = _read_labels_and_confirm_inventory()
    if {str(fixture.get("id")) for fixture in fixtures} != {"29", "31", "32", "33"}:
        raise AssertionError("current leave-one-out pipeline supports real invoice IDs 29, 31, 32, and 33")
    accuracy_by_id, accuracy_totals = _run_leave_one_out(fixtures)
    if set(accuracy_by_id) != {str(fixture["id"]) for fixture in fixtures}:
        raise AssertionError("leave-one-out results do not cover the complete labeled invoice inventory")

    report: dict[str, Any] = {
        "status": "FAIL",
        "contract": "e30.extraction-bridge.v1",
        "golden_pack_status": golden_report["status"],
        "executor": "source CLI" if exe is None else "PyInstaller one-folder executable",
        "python_version": sys.version.split()[0],
        "fixture_inventory": inventory,
        "accuracy_method": (
            "Four-fold leave-one-invoice-out E-02/Glyph evaluation. Each invoice's templates are built "
            "from the other three labeled fixtures, and evaluation=True rejects matching source path, "
            "SHA-256, or known derived-parent provenance. Pipeline AUTO_CANDIDATE is counted as the "
            "EXTRACTED route, REVIEW as REVIEW, and REJECT as BLOCKED. The LOO numeric run has no "
            "producer context, so it does not assemble a Canonical invoice."
        ),
        "accuracy_scope_note": (
            "Accuracy labels are from tests/fixtures/real/labels.json. Fixture 31 payable is explicitly "
            "derived from operator-confirmed line totals; its payable is checked but reported separately "
            "from independent label comparisons. The separate default-bank CLI route/timing probe is not "
            "independent accuracy evidence because that bank's provenance includes these four images. "
            "These four fixtures are a proxy, not a Holoo-wide claim."
        ),
        "startup_seconds": [],
        "fixtures": [],
        "counts": accuracy_totals,
        "runtime_cli_counts": {
            "invoice_outcomes": {status: 0 for status in NUMERIC_STATUSES},
            "extracted_but_wrong": 0,
        },
    }

    with tempfile.TemporaryDirectory(prefix="e31-accuracy-") as temp_name:
        temp = Path(temp_name)
        startup_times: list[float] = []
        for index in range(5):
            started = time.perf_counter()
            result = _run_process(exe, ["--help"], timeout=60)
            elapsed = time.perf_counter() - started
            startup_times.append(elapsed)
            help_text = result.stdout.decode("utf-8", errors="replace")
            if result.returncode != 0 or "extract" not in help_text or "onboard" not in help_text:
                raise AssertionError(
                    f"startup sample {index + 1}: CLI help failed; exit={result.returncode}; "
                    f"stderr={result.stderr.decode('utf-8', errors='replace')[-1000:]}"
                )
        report["startup_seconds"] = [round(value, 4) for value in startup_times]
        report["startup_median_seconds"] = round(statistics.median(startup_times), 4)
        report["startup_min_seconds"] = round(min(startup_times), 4)
        report["startup_max_seconds"] = round(max(startup_times), 4)

        for fixture in fixtures:
            fixture_id = str(fixture["id"])
            image_path = FIXTURE_DIR / str(fixture["path"])
            expected = _expected_numeric_values(fixture)
            context = _context(fixture_id, int(fixture.get("row_count", 0)))
            context_path = temp / f"canonical-context-{fixture_id}.json"
            _write_json_bytes(context_path, context)

            cli_started = time.perf_counter()
            cli_result = _run_process(exe, [
                "extract", "--image", image_path,
                "--context", context_path,
                "--captured-at", FIXED_CAPTURED_AT,
            ], timeout=180)
            cli_elapsed = time.perf_counter() - cli_started
            if cli_result.returncode not in RUNTIME_ROUTE_FOR_EXIT:
                raise AssertionError(
                    f"fixture {fixture_id}: invalid CLI exit={cli_result.returncode}; stderr="
                    f"{cli_result.stderr.decode('utf-8', errors='replace')[-1600:]}"
                )
            runtime_status = RUNTIME_ROUTE_FOR_EXIT[cli_result.returncode]
            if runtime_status == "BLOCKED" and cli_result.stdout:
                raise AssertionError(f"fixture {fixture_id}: BLOCKED CLI result must have empty stdout")
            if runtime_status == "EXTRACTED" and cli_result.stderr:
                raise AssertionError(f"fixture {fixture_id}: successful CLI result must have empty stderr")
            canonical: dict[str, Any] | None = None
            runtime_wrong_fields: list[str] = []
            if cli_result.stdout:
                canonical = json.loads(cli_result.stdout.decode("utf-8"))
                valid, errors = validate_canonical_invoice(canonical)
                if not valid:
                    raise AssertionError(f"fixture {fixture_id}: CLI output is not Canonical v0: {errors}")
                if runtime_status == "EXTRACTED":
                    if canonical.get("state") != "EXTRACTED":
                        raise AssertionError(f"fixture {fixture_id}: exit 0 did not produce EXTRACTED Canonical state")
                    runtime_wrong_fields = _compare_cli_invoice(canonical, expected, fixture_id)
            elif runtime_status == "EXTRACTED":
                raise AssertionError(f"fixture {fixture_id}: EXTRACTED CLI result has no Canonical candidate")

            report["runtime_cli_counts"]["invoice_outcomes"][runtime_status] += 1
            report["runtime_cli_counts"]["extracted_but_wrong"] += len(runtime_wrong_fields)
            accuracy = accuracy_by_id[fixture_id]
            item = dict(accuracy)
            item["runtime_cli"] = {
                "invoice_status": runtime_status,
                "exit_code": cli_result.returncode,
                "per_invoice_seconds": round(cli_elapsed, 4),
                "canonical_state": canonical.get("state") if canonical is not None else None,
                "synthetic_context_used": True,
                "extracted_but_wrong": len(runtime_wrong_fields),
            }
            report["fixtures"].append(item)

    if report["counts"]["extracted_but_wrong"] != 0:
        raise AssertionError("E-31 requires zero leave-one-out EXTRACTED-but-wrong fields")
    if report["runtime_cli_counts"]["extracted_but_wrong"] != 0:
        raise AssertionError("E-31 runtime CLI EXTRACTED-but-wrong fields must be zero")
    report["status"] = "PASS"
    return report


def _write_report(path: Path | None, value: dict[str, Any], markdown: bool = False) -> None:
    if path is None:
        return
    if markdown:
        counts = value.get("counts", {})
        runtime_counts = value.get("runtime_cli_counts", {})
        inventory = value.get("fixture_inventory", {})
        lines = [
            "# E-31 real-fixture accuracy and speed harness",
            "",
            f"- Status: **{value.get('status', 'FAIL')}**",
            f"- Executor: `{value.get('executor', 'unknown')}`",
            f"- E-30 golden pack: **{value.get('golden_pack_status', 'not verified')}**",
            f"- Complete top-level invoice inventory: `{', '.join(inventory.get('invoice_images', [])) or 'not confirmed'}`",
            f"- Startup (five fresh `--help` processes): median `{value.get('startup_median_seconds', 'not measured')}` s; "
            f"min `{value.get('startup_min_seconds', 'not measured')}` s; max `{value.get('startup_max_seconds', 'not measured')}` s",
            f"- LOO invoice outcomes (E/R/B): `{counts.get('invoice_outcomes', 'not recorded')}`",
            f"- LOO numeric-cell outcomes (E/R/B): `{counts.get('numeric_cells', 'not recorded')}`",
            f"- LOO EXTRACTED-but-wrong: **{counts.get('extracted_but_wrong', 'not recorded')}**",
            f"- Runtime CLI outcomes (E/R/B): `{runtime_counts.get('invoice_outcomes', 'not recorded')}`",
            f"- Runtime CLI EXTRACTED-but-wrong: **{runtime_counts.get('extracted_but_wrong', 'not recorded')}**",
            "",
            "| Fixture | LOO invoice outcome (E/R/B) | LOO numeric cells (E/R/B) | Independent comparisons | Derived payable checks | Wrong | Runtime CLI | Seconds |",
            "|---|---|---|---:|---:|---:|---|---:|",
        ]
        for item in value.get("fixtures", []):
            invoices = item.get("invoice_counts", {})
            cells = item.get("numeric_cell_counts", {})
            runtime = item.get("runtime_cli", {})
            lines.append(
                f"| {item.get('fixture_id', 'unknown')} | "
                f"{invoices.get('EXTRACTED', 0)}/{invoices.get('REVIEW', 0)}/{invoices.get('BLOCKED', 0)} | "
                f"{cells.get('EXTRACTED', 0)}/{cells.get('REVIEW', 0)}/{cells.get('BLOCKED', 0)} | "
                f"{item.get('independent_extracted_label_comparisons', 0)} | {item.get('derived_payable_checks', 0)} | "
                f"{item.get('extracted_but_wrong', 'not recorded')} | "
                f"{runtime.get('invoice_status', 'not measured')} (exit {runtime.get('exit_code', 'n/a')}) | "
                f"{runtime.get('per_invoice_seconds', 'n/a')} |"
            )
        lines.extend([
            "",
            f"Accuracy method: {value.get('accuracy_method', 'not recorded')}",
            f"Scope note: {value.get('accuracy_scope_note', 'not recorded')}",
        ])
        if value.get("failure"):
            lines.extend(["", f"Failure: `{value['failure']}`"])
        lines.extend([
            "",
            "Nested images under `n02-reference-crops/` are derived row crops and are excluded from invoice counts.",
            "",
        ])
        payload = "\n".join(lines).encode("utf-8")
    else:
        payload = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, help="built executable; omit to use the source CLI")
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    args = parser.parse_args(argv)
    exe = args.exe.resolve() if args.exe is not None else None
    try:
        report = run_harness(exe)
    except Exception as exc:
        report = {
            "status": "FAIL",
            "executor": "source CLI" if exe is None else "PyInstaller one-folder executable",
            "failure": f"{type(exc).__name__}: {exc}",
            "fixtures": [],
        }
    _write_report(args.report_json, report)
    _write_report(args.report_md, report, markdown=True)
    if report.get("status") != "PASS":
        print(report.get("failure", "E-31 harness failed"), file=sys.stderr)
        return 1
    print(
        "PASS E-31 "
        f"LOO_invoice_counts={report['counts']['invoice_outcomes']} "
        f"LOO_cell_counts={report['counts']['numeric_cells']} "
        f"LOO_extracted_but_wrong={report['counts']['extracted_but_wrong']}"
    )
    for item in report["fixtures"]:
        print(
            f"fixture={item['fixture_id']} LOO={item['invoice_status']} "
            f"cells={item['numeric_cell_counts']} comparisons="
            f"{item['independent_extracted_label_comparisons']}+derived:{item['derived_payable_checks']} "
            f"runtime={item['runtime_cli']['invoice_status']} "
            f"seconds={item['runtime_cli']['per_invoice_seconds']}"
        )
    print(
        f"startup_median_seconds={report['startup_median_seconds']} "
        f"min={report['startup_min_seconds']} max={report['startup_max_seconds']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
