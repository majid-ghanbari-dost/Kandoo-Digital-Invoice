from __future__ import annotations

import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import local_onboarding_eval as evaluation


def _write_capture(
    folder: Path,
    *,
    job_id: str,
    expected_fields: dict[str, str] | None = None,
) -> Path:
    folder.mkdir(parents=True)
    (folder / "capture.spl").write_bytes(b"SYNTHETIC LOCAL EVALUATION SPL\n")
    (folder / "Report.txt").write_text(
        "SYNTHETIC TEST REPORT\n"
        f"Spool job ID: {job_id}\n"
        "Page count: 1\n"
        "Customer: PRIVATE-CUSTOMER-NAME-SENTINEL\n"
        "Phone: PRIVATE-PHONE-SENTINEL\n",
        encoding="utf-8",
        newline="\n",
    )
    Image.new("RGB", (64, 48), "white").save(folder / "page1.png", format="PNG")
    if expected_fields is not None:
        sidecar = {
            "schema_version": evaluation.EXPECTED_SCHEMA,
            "pages": [{"page_index": 1, "fields": expected_fields}],
        }
        (folder / evaluation.EXPECTED_NAME).write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return folder


def _fake_result(*candidates: tuple[int, str, str, str]) -> dict:
    grouped = {"quantity": [], "line_total": [], "payable": []}
    for page_index, field_name, raw_value, status in candidates:
        if field_name.endswith(".quantity"):
            category = "quantity"
        elif field_name.endswith(".total"):
            category = "line_total"
        else:
            category = "payable"
        grouped[category].append({
            "page_index": page_index,
            "field_name": field_name,
            "raw_value": raw_value,
            "status": status,
        })
    return {"status": "REVIEW", "numeric_candidates": grouped}


def test_owner_summary_contains_only_aggregates_and_field_level_counts(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    captures = tmp_path / "private-owner-captures"
    private_job_name = "PRIVATE-INVOICE-ID-SENTINEL"
    _write_capture(
        captures / private_job_name,
        job_id="PRIVATE-SPOOL-ID-SENTINEL",
        expected_fields={
            "line.0.quantity": "۱",
            "line.0.total": "۱۲۳۴۵۶",
            "invoice.payable": "۱۲۳۴۵۶",
            "line.1.quantity": "۲",
        },
    )
    extraction = _fake_result(
        (1, "line.0.quantity", "۱", "EXTRACTED"),
        (1, "line.0.total", "۱۲۳۴۵۷", "EXTRACTED"),
        (1, "invoice.payable", "۱۲۳۴۵۶", "REVIEW"),
    )

    summary = evaluation.evaluate_capture_batch(
        captures,
        repository_root=repo,
        extractor=lambda _folder: extraction,
    )
    output_file = evaluation.write_aggregate_summary(summary, repository_root=repo)
    console = evaluation.render_aggregate_summary(summary)
    capsys.readouterr()
    output_text = output_file.read_text(encoding="utf-8")
    combined = console + output_text

    assert summary["outcome"] == "FAIL"
    assert summary["capture_batch"] == {"folders_seen": 1, "intake_ready": 1, "held_for_review": 0}
    assert summary["fields"]["quantity"] == {
        "expected": 2, "pass": 1, "fail": 0, "review": 0, "missing": 1,
    }
    assert summary["fields"]["line_total"] == {
        "expected": 1, "pass": 0, "fail": 1, "review": 0, "missing": 0,
    }
    assert summary["fields"]["payable"] == {
        "expected": 1, "pass": 0, "fail": 0, "review": 1, "missing": 0,
    }
    for private_value in (
        private_job_name,
        "PRIVATE-SPOOL-ID-SENTINEL",
        "PRIVATE-CUSTOMER-NAME-SENTINEL",
        "PRIVATE-PHONE-SENTINEL",
        "۱۲۳۴۵۶",
        "۱۲۳۴۵۷",
        str(captures),
    ):
        assert private_value not in combined
    assert output_file == repo / ".owner-local" / evaluation.SUMMARY_NAME
    assert output_file.exists()


def test_command_line_prints_only_counts_and_writes_ignored_summary(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    captures = tmp_path / "private-command-captures"
    job_name = "PRIVATE-JOB-NAME-SENTINEL"
    _write_capture(
        captures / job_name,
        job_id="PRIVATE-SPOOL-ID-SENTINEL",
        expected_fields={"invoice.payable": "۷۷۷۷۷۷"},
    )
    result = _fake_result((1, "invoice.payable", "۷۷۷۷۷۷", "EXTRACTED"))

    exit_code = evaluation.main(
        ["--capture-root", str(captures)],
        repository_root=repo,
        extractor=lambda _folder: result,
    )
    console = capsys.readouterr().out
    summary_path = repo / ".owner-local" / evaluation.SUMMARY_NAME
    stored = summary_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert "Outcome: PASS" in console
    assert "payable: 1 / 1 / 0 / 0 / 0" in console
    for private_value in (
        job_name,
        "PRIVATE-SPOOL-ID-SENTINEL",
        "PRIVATE-CUSTOMER-NAME-SENTINEL",
        "PRIVATE-PHONE-SENTINEL",
        "۷۷۷۷۷۷",
        str(captures),
    ):
        assert private_value not in console
        assert private_value not in stored


def test_batch_robustness_is_only_reported_as_aggregate_issue_counts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    captures = tmp_path / "synthetic-batch"
    _write_capture(captures / "duplicate-a", job_id="synthetic-duplicate-job")
    _write_capture(captures / "duplicate-b", job_id="synthetic-duplicate-job")
    empty = _write_capture(captures / "empty-spl", job_id="synthetic-empty-spl")
    (empty / "capture.spl").write_bytes(b"")
    misplaced = captures / "misplaced"
    _write_capture(misplaced / "nested-job", job_id="synthetic-misplaced-job")

    summary = evaluation.evaluate_capture_batch(
        captures,
        repository_root=repo,
        extractor=lambda _folder: _fake_result(),
    )

    assert summary["capture_batch"]["folders_seen"] == 4
    assert summary["capture_batch"]["intake_ready"] == 0
    assert summary["capture_batch"]["held_for_review"] == 4
    assert summary["capture_issue_counts"]["DUPLICATE_JOB_ID"] == 2
    assert summary["capture_issue_counts"]["EMPTY_SPL"] == 1
    assert summary["capture_issue_counts"]["JOB_IN_WRONG_FOLDER"] == 1
    assert summary["operator_labels"]["valid"] == 0
    assert summary["outcome"] == "NOT_SCORED"


def test_non_numeric_fields_are_rejected_without_echoing_sidecar_content(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    captures = tmp_path / "synthetic-bad-labels"
    _write_capture(
        captures / "job-a",
        job_id="synthetic-job-a",
        expected_fields={"customer.phone": "PRIVATE-PHONE-SENTINEL"},
    )

    summary = evaluation.evaluate_capture_batch(
        captures,
        repository_root=repo,
        extractor=lambda _folder: _fake_result(),
    )

    assert summary["operator_labels"]["invalid"] == 1
    assert summary["evaluation"]["jobs_not_evaluated"] == 1
    assert summary["outcome"] == "NOT_SCORED"
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "PRIVATE-PHONE-SENTINEL" not in serialized
    assert "customer.phone" not in serialized


def test_capture_and_output_paths_are_confined(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    captures = repo / "inside-repository"
    captures.mkdir()

    try:
        evaluation.evaluate_capture_batch(captures, repository_root=repo)
    except evaluation.EvaluationInputError:
        pass
    else:
        raise AssertionError("capture input inside the repository must be rejected")

    summary = evaluation._empty_summary()
    unsafe_output = tmp_path / "outside" / evaluation.SUMMARY_NAME
    try:
        evaluation.write_aggregate_summary(
            summary,
            output_path=unsafe_output,
            repository_root=repo,
        )
    except evaluation.EvaluationInputError:
        pass
    else:
        raise AssertionError("aggregate output outside .owner-local must be rejected")
    assert not unsafe_output.exists()


def test_output_directory_and_local_label_sidecar_are_git_ignored():
    assert "**/expected-fields.local.json" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/.owner-local/local-onboarding-eval-summary.local.json" in (
        ROOT / ".gitignore"
    ).read_text(encoding="utf-8")
