from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import local_onboarding_eval as local_evaluation
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
    first = _job(batch / "job-a", "synthetic-duplicate-001")
    second = _job(batch / "job-b", "synthetic-duplicate-001")
    _job(batch / "job-c", "synthetic-unique-001")

    # Reproduce two byte-identical synthetic capture pairs without relying on
    # any owner capture or embedding its payload in the repository.
    assert (first / "capture.spl").read_bytes() == (second / "capture.spl").read_bytes()
    assert (first / "page1.png").read_bytes() == (second / "page1.png").read_bytes()

    items = inspect_capture_batch(batch)
    assert [item.status for item in items] == ["REVIEW", "REVIEW", "READY"]
    assert {problem.code for item in items[:2] for problem in item.problems} == {"DUPLICATE_JOB_ID"}
    assert items[2].capture is not None
    assert "synthetic-duplicate-001" not in repr(items[:2])


def test_two_identical_pairs_and_zero_byte_spl_are_all_reported(tmp_path):
    folder = _job(tmp_path / "Job_2", "synthetic-repeated-capture")
    original_spl = (folder / "capture.spl").read_bytes()
    original_png = (folder / "page1.png").read_bytes()
    (folder / "repeat.SPL").write_bytes(original_spl)
    (folder / "repeat_page.PNG").write_bytes(original_png)
    (folder / "empty.SPL").write_bytes(b"")

    assert (folder / "capture.spl").read_bytes() == (folder / "repeat.SPL").read_bytes()
    assert (folder / "page1.png").read_bytes() == (folder / "repeat_page.PNG").read_bytes()
    assert {"AMBIGUOUS_SPL", "EMPTY_SPL"} <= _codes(folder)


def test_job_nested_in_wrong_folder_is_explicitly_reported(tmp_path):
    misplaced = tmp_path / "misplaced-job"
    nested = misplaced / "job-files"
    _job(nested, "synthetic-wrong-folder-001")

    codes = _codes(misplaced)
    assert {"MISSING_SPL", "MISSING_PNG", "MISSING_REPORT", "JOB_IN_WRONG_FOLDER"} <= codes


def test_complete_job_under_unassigned_is_held_for_review(tmp_path):
    batch = tmp_path / "DiagnosticResults"
    _job(batch / "Unassigned", "synthetic-unassigned-job")

    items = inspect_capture_batch(batch)
    assert len(items) == 1
    assert items[0].status == "REVIEW"
    assert items[0].capture is None
    assert {problem.code for problem in items[0].problems} == {"JOB_IN_WRONG_FOLDER"}
    assert "synthetic-unassigned-job" not in repr(items)


def test_unassigned_metadata_only_folder_is_reviewed_with_missing_artifacts(tmp_path):
    batch = tmp_path / "DiagnosticResults"
    unassigned = batch / "Unassigned"
    unassigned.mkdir(parents=True)
    (unassigned / "synthetic-capture.SHD").write_bytes(b"SYNTHETIC SHD METADATA")

    items = inspect_capture_batch(batch)
    assert len(items) == 1
    assert items[0].status == "REVIEW"
    assert items[0].capture is None
    assert {problem.code for problem in items[0].problems} == {
        "JOB_IN_WRONG_FOLDER", "MISSING_SPL", "MISSING_PNG", "MISSING_REPORT",
    }
    assert "synthetic-capture.SHD" not in repr(items)


def test_diagnosticresults_11_file_three_folder_structure_uses_synthetic_payloads(tmp_path):
    batch = tmp_path / "DiagnosticResults"
    job2 = batch / "Job_2_14050816_135747_753"
    job2.mkdir(parents=True)

    duplicate_spl = b"SYNTHETIC SPL CONTENT - duplicate pair\n"
    first_spl = job2 / "14050816_135747_753_00002.SPL"
    duplicate_spl_path = job2 / "synthetic-duplicate.SPL"
    first_spl.write_bytes(duplicate_spl)
    duplicate_spl_path.write_bytes(duplicate_spl)
    (job2 / "14050816_135747_803_00002.SPL").write_bytes(b"")

    first_png = job2 / "14050816_135747_753_00002.PNG"
    Image.new("RGB", (32, 24), "white").save(first_png, format="PNG")
    duplicate_png_path = job2 / "synthetic-duplicate.PNG"
    duplicate_png_path.write_bytes(first_png.read_bytes())
    (job2 / "Report.txt").write_text(
        "Spool job ID: synthetic-diagnostic-job\nPage count: 1\n",
        encoding="utf-8",
        newline="\n",
    )

    job3 = batch / "Job_3_14050816_135803_641"
    job3.mkdir()
    (job3 / "Report.txt").write_text("Synthetic report placeholder\n", encoding="utf-8", newline="\n")
    for index in range(1, 4):
        (job3 / f"synthetic-sidecar-{index}.SHD").write_bytes(b"SYNTHETIC SHD METADATA")

    unassigned = batch / "Unassigned"
    unassigned.mkdir()
    (unassigned / "14050816_135747_774_00002.SHD").write_bytes(b"SYNTHETIC MISPLACED SHD")

    assert sum(path.is_file() for path in batch.rglob("*")) == 11
    assert first_spl.read_bytes() == duplicate_spl_path.read_bytes()
    assert first_png.read_bytes() == duplicate_png_path.read_bytes()
    assert (job2 / "14050816_135747_803_00002.SPL").stat().st_size == 0

    items = inspect_capture_batch(batch)
    assert len(items) == 3
    assert [item.status for item in items] == ["REVIEW", "REVIEW", "REVIEW"]
    assert all(item.capture is None for item in items)
    code_counts = {
        code: sum(problem.code == code for item in items for problem in item.problems)
        for code in (
            "AMBIGUOUS_SPL",
            "EMPTY_SPL",
            "JOB_IN_WRONG_FOLDER",
            "MISSING_PNG",
            "MISSING_REPORT",
            "MISSING_SPL",
        )
    }
    assert code_counts == {
        "AMBIGUOUS_SPL": 1,
        "EMPTY_SPL": 1,
        "JOB_IN_WRONG_FOLDER": 1,
        "MISSING_PNG": 2,
        "MISSING_REPORT": 1,
        "MISSING_SPL": 2,
    }
    assert "14050816_135747_774_00002.SHD" not in repr(items)
    assert "synthetic-diagnostic-job" not in repr(items)


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


def test_owner_local_evaluation_aggregates_capture_issues_without_identifiers(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    batch = tmp_path / "private-e73-batch-path"
    private_job_id = "PRIVATE-E73-SPOOL-ID-SENTINEL"
    _job(batch / "PRIVATE-E73-JOB-A-SENTINEL", private_job_id)
    _job(batch / "PRIVATE-E73-JOB-B-SENTINEL", private_job_id)
    empty = _job(batch / "PRIVATE-E73-EMPTY-JOB-SENTINEL", "synthetic-empty-job")
    (empty / "capture.spl").write_bytes(b"")
    _job(batch / "Unassigned", "synthetic-unassigned-job")

    exit_code = local_evaluation.main(
        ["--capture-root", str(batch)],
        repository_root=repo,
        extractor=lambda _folder: {},
    )
    captured = capsys.readouterr()
    summary_path = repo / ".owner-local" / local_evaluation.SUMMARY_NAME
    summary_text = summary_path.read_text(encoding="utf-8")

    assert exit_code == 10
    assert captured.err == ""
    assert "Outcome: NOT_SCORED" in captured.out
    assert "Capture folders: seen=4 ready=0 review=4" in captured.out
    assert "Capture issue codes: DUPLICATE_JOB_ID=2, EMPTY_SPL=1, JOB_IN_WRONG_FOLDER=1" in captured.out
    for private_value in (
        private_job_id,
        "PRIVATE-E73-JOB-A-SENTINEL",
        "PRIVATE-E73-JOB-B-SENTINEL",
        "PRIVATE-E73-EMPTY-JOB-SENTINEL",
        "synthetic-unassigned-job",
        str(batch),
    ):
        assert private_value not in captured.out
        assert private_value not in summary_text


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
