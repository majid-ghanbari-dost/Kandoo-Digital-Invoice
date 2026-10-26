#!/usr/bin/env python3
"""Measure the optional ParisaOCR stack and suggestions on Windows-latest.

The script has a stdlib-only ``--snapshot-site-packages`` mode for measuring an
isolated venv before installation. Normal mode loads the local ParisaOCR models,
measures cold initialization, and times each of the 22 representative N-02
candidate crops. It performs no network access during inference.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import sysconfig
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _directory_snapshot() -> dict[str, Any]:
    purelib = Path(sysconfig.get_paths()["purelib"]).resolve()
    total_bytes = 0
    file_count = 0
    for directory, _, filenames in os.walk(purelib):
        for filename in filenames:
            path = Path(directory) / filename
            try:
                if path.is_file():
                    total_bytes += path.stat().st_size
                    file_count += 1
            except OSError:
                continue
    return {
        "site_packages_directory": str(purelib),
        "logical_file_bytes": total_bytes,
        "file_count": file_count,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _distribution_licenses() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for distribution in importlib.metadata.distributions():
        metadata = distribution.metadata
        name = metadata.get("Name") or distribution.name or "UNKNOWN"
        raw_license = metadata.get("License")
        if raw_license:
            raw_license = " ".join(raw_license.split())[:500]
        inventory.append({
            "name": name,
            "version": distribution.version,
            "license_expression": metadata.get("License-Expression"),
            "license": raw_license,
            "license_classifiers": sorted(
                value for value in metadata.get_all("Classifier", [])
                if value.startswith("License ::")
            ),
            "license_files": sorted(metadata.get_all("License-File", [])),
            "base_venv_tool": name.lower().replace("_", "-") in {"pip", "setuptools"},
        })
    return sorted(inventory, key=lambda item: item["name"].casefold())


def _peak_memory() -> dict[str, Any]:
    """Return process peak resident set size using the native runner API."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return {
            "metric": "Windows PeakWorkingSetSize (resident set)",
            "peak_resident_bytes": int(counters.PeakWorkingSetSize),
            "current_resident_bytes": int(counters.WorkingSetSize),
            "peak_pagefile_bytes": int(counters.PeakPagefileUsage),
        }

    # Useful for a manual Linux rerun; the committed Windows workflow uses the
    # Windows API above. ru_maxrss is KiB on Linux and bytes on macOS.
    import resource

    raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    scale = 1024 if sys.platform.startswith("linux") else 1
    return {
        "metric": "resource.getrusage(RUSAGE_SELF).ru_maxrss",
        "peak_resident_bytes": raw * scale,
        "current_resident_bytes": None,
        "peak_pagefile_bytes": None,
    }


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _escape_github_command_data(value: str) -> str:
    """Escape a workflow-command message while keeping it on one log line."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _emit_github_notice(title: str, payload: Any) -> None:
    message = _compact_json(payload)
    print(f"::notice title={title}::{_escape_github_command_data(message)}", flush=True)


def _chunk_github_notice_items(
    items: list[Any], max_message_chars: int = 3000
) -> list[list[Any]]:
    """Split list data below the Actions annotation message-size limit."""
    chunks: list[list[Any]] = []
    current: list[Any] = []
    for item in items:
        candidate = current + [item]
        encoded = _escape_github_command_data(_compact_json(candidate))
        if current and len(encoded) > max_message_chars:
            chunks.append(current)
            current = [item]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _emit_github_notice_chunks(title: str, items: list[Any]) -> None:
    chunks = _chunk_github_notice_items(items)
    for index, chunk in enumerate(chunks, start=1):
        _emit_github_notice(f"{title} {index}/{len(chunks)}", chunk)


def _markdown_report(result: dict[str, Any]) -> str:
    runtime = result["runtime"]
    measurements = result["measurements"]
    lines = [
        "# N-04 ParisaOCR Windows-latest raw benchmark",
        "",
        f"- GitHub run: `{runtime.get('github_run_id')}`; source SHA: `{runtime.get('github_sha')}`.",
        f"- Runner: `{runtime.get('runner_os')}` / `{runtime.get('runner_image')}`; Python `{runtime['python_version']}`.",
        f"- Measurement timestamp (UTC): `{runtime['measured_at_utc']}`.",
        f"- CPU inference: `{result['engine']['device']}`; crops: `{measurements['crop_count']}`.",
        "- References are provisional and not owner-confirmed; this benchmark makes no accuracy claim.",
        "",
        "## Raw measurements",
        "",
        f"- New files in isolated venv site-packages: `{measurements['installed_site_packages_delta_bytes']}` bytes ({measurements['installed_site_packages_delta_mib']:.3f} MiB); measured by before/after logical file-size delta.",
        f"- ParisaOCR import + CPU reader/model cold initialization: `{measurements['cold_initialization_seconds']:.6f}` s.",
        f"- First crop inference (includes first-use effects): `{measurements['first_crop_seconds']:.6f}` s.",
        f"- Warm+first per-crop inference, min / median / p95 / max: `{measurements['per_crop_min_seconds']:.6f}` / `{measurements['per_crop_median_seconds']:.6f}` / `{measurements['per_crop_p95_seconds']:.6f}` / `{measurements['per_crop_max_seconds']:.6f}` s.",
        f"- Peak resident working set: `{measurements['peak_memory']['peak_resident_bytes']}` bytes ({measurements['peak_memory']['peak_resident_bytes'] / 1024**2:.3f} MiB); Windows `PeakWorkingSetSize`.",
        "",
        "### Per-crop inference timings",
        "",
        "| Crop ID | Seconds | Recognized lines | Confidence (0–100; diagnostic only) |",
        "|---|---:|---:|---:|",
    ]
    for item in measurements["per_crop"]:
        confidence = "—" if item["confidence"] is None else f"{item['confidence']:.4f}"
        lines.append(
            f"| `{item['crop_id']}` | {item['elapsed_seconds']:.6f} | "
            f"{item['line_count']} | {confidence} |")
    lines += [
        "",
        "## Resolved distributions and license metadata",
        "",
        "License metadata is taken from the installed distributions; empty/ambiguous metadata is not a legal determination.",
        "",
        "| Distribution | Version | SPDX expression | License field / classifier |",
        "|---|---|---|---|",
    ]
    for item in result["license_inventory"]:
        if item["base_venv_tool"]:
            continue
        license_value = item["license"] or ", ".join(item["license_classifiers"]) or "not declared in metadata"
        expression = item["license_expression"] or "—"
        license_cell = license_value.replace("|", "\\|")
        lines.append(
            f"| `{item['name']}` | `{item['version']}` | `{expression}` | "
            f"{license_cell} |")
    lines.append("")
    return "\n".join(lines)


def run_benchmark(repo_root: Path, baseline_path: Path, output_json: Path) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("N-04 benchmark is specified for a native Windows-latest runner")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    before = _directory_snapshot()
    if Path(baseline["site_packages_directory"]).resolve() != Path(
        before["site_packages_directory"]
    ).resolve():
        raise ValueError("site-packages baseline belongs to a different Python environment")

    try:
        from run_n02_product_candidates import build_product_candidates
        from n04_name_suggestions import (
            ParisaOCRNameSuggester,
            enrich_product_candidates,
        )
    except Exception as exc:
        raise RuntimeError("add src/ and scripts/ to PYTHONPATH") from exc

    source_document = build_product_candidates(
        repo_root.resolve(), write_reference_crops=False)
    process_memory_before = _peak_memory()
    engine = ParisaOCRNameSuggester()
    inference_timings: dict[str, float] = {}
    suggestion_document = enrich_product_candidates(
        source_document,
        repo_root,
        suggester=engine,
        inference_timings=inference_timings,
    )
    peak_memory = _peak_memory()
    after = _directory_snapshot()

    per_crop = []
    for candidate in suggestion_document["candidates"]:
        suggestion = candidate["name_suggestions"][0]
        crop_id = suggestion["crop_reference"]["crop_id"]
        per_crop.append({
            "crop_id": crop_id,
            "elapsed_seconds": round(inference_timings[crop_id], 9),
            "line_count": len(suggestion["lines"]),
            "confidence": suggestion["confidence"],
            "suggested_name": suggestion["suggested_name"],
            "accepted": suggestion["accepted"],
        })
    times = [item["elapsed_seconds"] for item in per_crop]
    install_delta = after["logical_file_bytes"] - int(baseline["logical_file_bytes"])
    if install_delta < 0:
        raise RuntimeError("site-packages shrank after installation; size delta is invalid")

    requirements_file = repo_root / "scripts" / "n04-parisaocr-requirements.txt"
    distribution_list = _distribution_licenses()
    result: dict[str, Any] = {
        "schema_version": "n04.parisaocr-windows-benchmark.v1",
        "runtime": {
            "github_sha": os.environ.get("GITHUB_SHA"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "runner_os": os.environ.get("RUNNER_OS", platform.system()),
            "runner_image": os.environ.get("ImageOS"),
            "runner_image_version": os.environ.get("ImageVersion"),
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
            "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            "requirements_file": requirements_file.relative_to(repo_root).as_posix(),
            "requirements_sha256": _sha256(requirements_file),
            "site_packages_before": before,
            "site_packages_after": after,
            "pip_freeze": subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True, text=True, check=True,
            ).stdout.splitlines(),
        },
        "engine": {
            **engine.provenance(),
            "cold_initialization_seconds": round(engine.initialization_seconds, 9),
        },
        "measurements": {
            "crop_count": len(per_crop),
            "installed_site_packages_delta_bytes": install_delta,
            "installed_site_packages_delta_mib": round(install_delta / 1024**2, 6),
            "cold_initialization_seconds": round(engine.initialization_seconds, 9),
            "first_crop_seconds": times[0] if times else None,
            "per_crop_min_seconds": min(times) if times else None,
            "per_crop_median_seconds": statistics.median(times) if times else None,
            "per_crop_p95_seconds": _percentile95(times),
            "per_crop_max_seconds": max(times) if times else None,
            "per_crop": per_crop,
            "peak_memory": peak_memory,
            "process_memory_before_engine": process_memory_before,
        },
        "license_inventory": distribution_list,
        "suggestion_document": suggestion_document,
        "limitations": [
            "The six N-01 evaluation references are provisional and not owner-confirmed; this benchmark scores no OCR accuracy.",
            "Confidence is copied from ParisaOCR and is not calibrated or an acceptance threshold.",
            "Install footprint is the logical file-byte delta in an isolated Python venv; it is not a PyInstaller bundle size or downloaded-wheel total.",
            "Cold initialization measures ParisaOCR/PyTorch imports plus CPU reader/model initialization, not a fresh Windows process launch.",
            "Peak memory is the process peak resident working set, including the Python process and loaded packages/models, measured with the Windows API.",
        ],
    }
    _write_json(output_json, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-site-packages",
        type=Path,
        help="write the current isolated venv baseline and exit (stdlib-only)",
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--install-baseline", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    parser.add_argument("--error-json", type=Path)
    args = parser.parse_args(argv)

    if args.snapshot_site_packages:
        snapshot = _directory_snapshot()
        snapshot["python_executable"] = sys.executable
        snapshot["python_version"] = platform.python_version()
        _write_json(args.snapshot_site_packages.resolve(), snapshot)
        print(json.dumps(snapshot, sort_keys=True))
        return 0

    if not args.install_baseline or not args.output_json or not args.output_markdown:
        parser.error("normal benchmark mode requires --install-baseline, --output-json, and --output-markdown")
    try:
        result = run_benchmark(
            args.repo_root.resolve(),
            args.install_baseline.resolve(),
            args.output_json.resolve(),
        )
    except Exception as exc:
        trace = traceback.format_exc()
        if args.error_json:
            _write_json(args.error_json.resolve(), {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": trace,
                "github_sha": os.environ.get("GITHUB_SHA"),
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            })
        encoded_trace = (trace.replace("%", "%25")
                         .replace("\r", "%0D")
                         .replace("\n", "%0A"))
        print(f"::error title=N-04 benchmark traceback::{encoded_trace}")
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with Path(summary_path).open("a", encoding="utf-8", newline="\n") as output:
                output.write("## N-04 benchmark failure\n\n```text\n")
                output.write(trace)
                output.write("\n```\n")
        raise
    markdown = _markdown_report(result)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.write_text(markdown, encoding="utf-8", newline="\n")
    summary = {
        "schema_version": result["schema_version"],
        "github_sha": result["runtime"]["github_sha"],
        "github_run_id": result["runtime"]["github_run_id"],
        "crop_count": result["measurements"]["crop_count"],
        "installed_site_packages_delta_bytes": result["measurements"]["installed_site_packages_delta_bytes"],
        "installed_site_packages_delta_mib": result["measurements"]["installed_site_packages_delta_mib"],
        "cold_initialization_seconds": result["measurements"]["cold_initialization_seconds"],
        "first_crop_seconds": result["measurements"]["first_crop_seconds"],
        "per_crop_min_seconds": result["measurements"]["per_crop_min_seconds"],
        "per_crop_median_seconds": result["measurements"]["per_crop_median_seconds"],
        "per_crop_p95_seconds": result["measurements"]["per_crop_p95_seconds"],
        "per_crop_max_seconds": result["measurements"]["per_crop_max_seconds"],
        "peak_resident_bytes": result["measurements"]["peak_memory"]["peak_resident_bytes"],
        "per_crop": [
            {key: item[key] for key in ("crop_id", "elapsed_seconds", "line_count", "confidence")}
            for item in result["measurements"]["per_crop"]
        ],
    }
    print("N04_BENCHMARK_SUMMARY=" + json.dumps(summary, sort_keys=True))
    _emit_github_notice("N04 aggregate benchmark measurements", {
        "runtime": {
            key: result["runtime"][key]
            for key in (
                "github_sha", "github_run_id", "runner_os", "runner_image",
                "runner_image_version", "python_version", "requirements_file",
                "requirements_sha256",
            )
        },
        "engine": result["engine"],
        "measurements": {
            key: value for key, value in summary.items() if key != "per_crop"
        },
    })
    _emit_github_notice_chunks(
        "N04 per-crop inference timings", summary["per_crop"])
    _emit_github_notice_chunks(
        "N04 resolved pip freeze", result["runtime"]["pip_freeze"])
    license_inventory = [
        {
            key: distribution[key]
            for key in (
                "name", "version", "license_expression", "license",
                "license_classifiers", "license_files",
            )
        }
        for distribution in result["license_inventory"]
        if not distribution["base_venv_tool"]
    ]
    _emit_github_notice_chunks(
        "N04 resolved dependency license metadata", license_inventory)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8", newline="\n") as output:
            output.write(markdown + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
