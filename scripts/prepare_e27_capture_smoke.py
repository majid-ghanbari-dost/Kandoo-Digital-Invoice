#!/usr/bin/env python3
"""Prepare synthetic E-27 capture folders from repository image fixtures.

The generated SPL bytes and Report.txt syntax are harness conventions, not
KandooPrintProbe output. They deliberately carry a digest so corruption can be
detected without claiming to parse a Windows spool format.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any


SYNTHETIC_TIMESTAMP = "2026-10-26T11:12:13+03:30"


def _spl_bytes(fixture_id: str) -> bytes:
    return b"SYNTHETIC E-27 SPL; NOT A WINDOWS SPOOL FILE\x00" + fixture_id.encode("ascii")


def _write_capture(
    repo_root: Path,
    folder: Path,
    *,
    fixture_ids: tuple[str, ...],
    job_id: str,
    page_count: int,
    timestamp: str = SYNTHETIC_TIMESTAMP,
    duplicate_job_id: bool = False,
    include_pages: bool = True,
) -> None:
    fixture_dir = repo_root / "tests" / "fixtures" / "real"
    folder.mkdir(parents=True, exist_ok=True)
    spl_bytes = _spl_bytes(job_id)
    (folder / "capture-job.spl").write_bytes(spl_bytes)
    if include_pages:
        for index, fixture_id in enumerate(fixture_ids, start=1):
            shutil.copyfile(fixture_dir / f"{fixture_id}.png", folder / f"page{index}.png")

    lines = [
        "SYNTHETIC KandooPrintProbe Report; NOT A REAL PROBE REPORT",
        "Printer: Synthetic fixture device",
        f"Spool job ID: {job_id}",
    ]
    if duplicate_job_id:
        lines.append(f"Spool job ID: {job_id}-duplicate")
    lines.extend((
        f"Timestamp: {timestamp}",
        f"Page count: {page_count}",
        f"SPL SHA-256: {hashlib.sha256(spl_bytes).hexdigest()}",
    ))
    (folder / "Report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_e27_capture_folders(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    """Create four valid fixture-backed folders and five failure scenarios."""
    repo_root = repo_root.resolve()
    output_dir = output_dir.resolve()
    fixture_dir = repo_root / "tests" / "fixtures" / "real"
    for fixture_id in ("29", "31", "32", "33"):
        if not (fixture_dir / f"{fixture_id}.png").is_file():
            raise FileNotFoundError(f"required real fixture PNG is missing: {fixture_id}.png")
        if not (fixture_dir / "canonical" / f"canonical-{fixture_id}.json").is_file():
            raise FileNotFoundError(f"required Canonical JSON golden is missing: {fixture_id}")

    output_dir.mkdir(parents=True, exist_ok=True)
    valid: list[dict[str, str]] = []
    for fixture_id in ("29", "31", "32", "33"):
        folder = output_dir / f"valid-{fixture_id}"
        _write_capture(
            repo_root,
            folder,
            fixture_ids=(fixture_id,),
            job_id=f"e27-valid-{fixture_id}",
            page_count=1,
        )
        valid.append({
            "fixture_id": fixture_id,
            "folder": str(folder),
            "captured_at": SYNTHETIC_TIMESTAMP,
            "canonical_golden": str(fixture_dir / "canonical" / f"canonical-{fixture_id}.json"),
        })

    failures: list[dict[str, str]] = []
    failure_specs = (
        ("missing-png", ("29",), 1, False, False, "MISSING_PNG"),
        ("corrupt-spl", ("29",), 1, False, True, "SPL_HASH_MISMATCH"),
        ("empty-job", ("29",), 0, False, True, "EMPTY_JOB"),
        ("duplicate-job-id", ("29",), 1, True, True, "DUPLICATE_JOB_ID"),
        ("two-png-page-count-mismatch", ("29", "31"), 1, False, True, "PAGE_COUNT_MISMATCH"),
    )
    for name, fixture_ids, page_count, duplicate, include_pages, expected_code in failure_specs:
        folder = output_dir / name
        _write_capture(
            repo_root,
            folder,
            fixture_ids=fixture_ids,
            job_id=f"e27-{name}",
            page_count=page_count,
            duplicate_job_id=duplicate,
            include_pages=include_pages,
        )
        if name == "corrupt-spl":
            (folder / "capture-job.spl").write_bytes(b"CORRUPTED AFTER REPORT HASH")
        failures.append({
            "case": name,
            "folder": str(folder),
            "expected_error_code": expected_code,
        })

    return {"valid": valid, "failures": failures}
