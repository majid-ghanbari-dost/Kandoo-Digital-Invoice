from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from image_extraction_adapter.capture_folder import (
    CaptureFolderValidationError,
    inspect_capture_batch,
    inspect_capture_folder,
)


def _job(folder: Path, job_id: str = "synthetic-job-001") -> Path:
    folder.mkdir(parents=True)
    (folder / "capture.spl").write_bytes(b"SYNTHETIC SPL envelope\n")
    (folder / "Report.txt").write_text(
        f"Spool job ID: {job_id}\nPage count: 1\n",
        encoding="utf-8",
        newline="\n",
    )
    Image.new("RGB", (32, 24), "white").save(folder / "page1.png", format="PNG")
    return folder


def _codes(folder: Path) -> set[str]:
    with pytest.raises(CaptureFolderValidationError) as error:
        inspect_capture_folder(folder)
    return {problem.code for problem in error.value.problems}


def test_zero_byte_spl_png_and_report_fail_closed(tmp_path):
    empty_spl = _job(tmp_path / "empty-spl")
    (empty_spl / "capture.spl").write_bytes(b"")
    assert "EMPTY_SPL" in _codes(empty_spl)

    empty_png = _job(tmp_path / "empty-png")
    (empty_png / "page1.png").write_bytes(b"")
    assert "INVALID_PNG" in _codes(empty_png)

    empty_report = _job(tmp_path / "empty-report")
    (empty_report / "Report.txt").write_bytes(b"")
    assert "EMPTY_REPORT" in _codes(empty_report)


def test_duplicate_jobs_are_all_held_for_review_without_selecting_a_winner(tmp_path):
    batch = tmp_path / "queue"
    _job(batch / "job-a", "synthetic-duplicate-001")
    _job(batch / "job-b", "synthetic-duplicate-001")
    _job(batch / "job-c", "synthetic-unique-001")

    items = inspect_capture_batch(batch)
    assert [item.status for item in items] == ["REVIEW", "REVIEW", "READY"]
    assert {problem.code for item in items[:2] for problem in item.problems} == {"DUPLICATE_JOB_ID"}
    assert items[2].capture is not None
    assert "synthetic-duplicate-001" not in repr(items[:2])


def test_job_nested_in_wrong_folder_is_explicitly_reported(tmp_path):
    misplaced = tmp_path / "misplaced-job"
    nested = misplaced / "job-files"
    _job(nested, "synthetic-wrong-folder-001")

    codes = _codes(misplaced)
    assert {"MISSING_SPL", "MISSING_PNG", "MISSING_REPORT", "JOB_IN_WRONG_FOLDER"} <= codes


def test_repeated_job_id_metadata_in_one_report_is_not_silently_accepted(tmp_path):
    folder = _job(tmp_path / "repeated-report-id")
    (folder / "Report.txt").write_text(
        "Spool job ID: synthetic-duplicate-field\n"
        "Spool job ID: synthetic-duplicate-field\n"
        "Page count: 1\n",
        encoding="utf-8",
        newline="\n",
    )
    assert "DUPLICATE_JOB_ID" in _codes(folder)


def test_batch_root_with_job_files_directly_is_a_wrong_folder(tmp_path):
    direct = _job(tmp_path / "batch-root")
    items = inspect_capture_batch(direct)
    assert len(items) == 1
    assert items[0].status == "REVIEW"
    assert {problem.code for problem in items[0].problems} == {"JOB_IN_WRONG_FOLDER"}


def test_batch_summary_script_does_not_print_ids_or_paths(tmp_path):
    batch = tmp_path / "private-synthetic-queue"
    secret_id = "synthetic-private-spool-id"
    _job(batch / "job-a", secret_id)
    _job(batch / "job-b", secret_id)
    script = ROOT / "scripts" / "inspect_capture_batch.py"
    result = subprocess.run(
        [sys.executable, str(script), "--capture-root", str(batch)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 10
    document = json.loads(result.stdout.decode("utf-8"))
    assert document["ready_count"] == 0
    assert document["review_count"] == 2
    assert secret_id not in result.stdout.decode("utf-8")
    assert str(batch) not in result.stdout.decode("utf-8")
