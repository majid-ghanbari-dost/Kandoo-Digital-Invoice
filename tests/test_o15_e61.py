from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from demo_capture import main as demo_main
from image_extraction_adapter import pipeline_v0
from image_extraction_adapter.capture_folder import extract_capture_folder
from image_extraction_adapter.pipeline_v0 import DEFAULT_MINIMUM_CONFIDENCE, extract_pipeline_v0
from image_extraction_adapter.preprocessing import LayoutSafetyResult
from image_extraction_adapter.review_evidence import ReviewPageSource, write_review_evidence

FIXTURE = ROOT / "tests/fixtures/o15/capture-folder"
EVIDENCE_SCHEMA = ROOT / "schemas/o15/review-evidence-v1.schema.json"


def _validate_evidence(document: object) -> None:
    from jsonschema import Draft202012Validator

    schema = json.loads(EVIDENCE_SCHEMA.read_bytes().decode("utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)


def test_evidence_records_reading_confidence_reason_and_exact_crop(tmp_path):
    image_path = tmp_path / "page1.png"
    Image.new("RGB", (32, 24), "white").save(image_path)
    output_dir = tmp_path / "review-evidence"
    cell = SimpleNamespace(
        field_name="line.1.total",
        raw_value="1234",
        confidence=88.5,
        status="REVIEW",
        reason="Arithmetic witness did not agree.",
        bbox=(4, 5, 20, 18),
    )
    page = ReviewPageSource(
        page_index=1,
        image_path=image_path,
        pipeline_status="REVIEW",
        layout_status="OK",
        layout_reason="Complete table geometry detected.",
        pipeline_reason="Arithmetic review required.",
        cell_results=(cell,),
    )

    write_review_evidence(output_dir, (page,))
    document = json.loads((output_dir / "review-evidence-v1.json").read_bytes().decode("utf-8"))
    _validate_evidence(document)
    assert document["accuracy"]["status"] == "NOT_SCORED"
    assert document["accuracy"]["extracted_but_wrong"] is None

    item = document["items"][0]
    assert item["field_name"] == "line.1.total"
    assert item["value"] == "1234"
    assert item["confidence"] == 88.5
    assert item["reason"] == "Arithmetic witness did not agree."
    assert item["crop_region"] == [4, 5, 20, 18]
    with Image.open(output_dir / item["crop_file"]) as crop:
        assert crop.size == (16, 13)
    queue = (output_dir / "review-queue.html").read_text(encoding="utf-8")
    assert "Evidence ID:" in queue
    assert "What I read:" in queue
    assert "1234" in queue
    assert "Arithmetic witness did not agree." in queue
    assert "data:image/png;base64," in queue
    assert "<script" not in queue.casefold()


def test_incomplete_extracted_evidence_is_downgraded_to_review(tmp_path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (20, 12), "white").save(image_path)
    page = ReviewPageSource(
        page_index=1,
        image_path=image_path,
        pipeline_status="AUTO_CANDIDATE",
        layout_status="OK",
        layout_reason="Complete table geometry detected.",
        pipeline_reason="",
        cell_results=(SimpleNamespace(
            field_name="invoice.payable",
            raw_value="",
            confidence=None,
            status="EXTRACTED",
            reason=None,
            bbox=(2, 2, 18, 10),
        ),),
    )

    output_dir = write_review_evidence(tmp_path / "review", (page,))
    document = json.loads((output_dir / "review-evidence-v1.json").read_bytes().decode("utf-8"))
    item = document["items"][0]
    assert item["status"] == "REVIEW"
    assert "lacked a non-empty value or valid confidence" in item["reason"]


def test_demo_writes_blocked_page_review_queue_without_changing_capture_json(tmp_path):
    output_dir = tmp_path / "demo-run"
    code = demo_main([
        "--capture-folder", str(FIXTURE),
        "--out-dir", str(output_dir),
        "--e05-bank", str(ROOT / "tests/fixtures/o15/e05-bank-synthetic.json"),
    ])
    assert code == 20

    capture_result = json.loads((output_dir / "capture-folder-result.json").read_bytes().decode("utf-8"))
    assert capture_result["result_version"] == "capture-folder-result-v1"
    assert capture_result["numeric_candidates"] == {"quantity": [], "line_total": [], "payable": []}
    evidence_dir = output_dir / "review-evidence"
    document = json.loads((evidence_dir / "review-evidence-v1.json").read_bytes().decode("utf-8"))
    _validate_evidence(document)
    item = document["items"][0]
    assert item["field_name"] == "layout"
    assert item["value"] == ""
    assert item["confidence"] is None
    assert item["status"] == "BLOCKED"
    assert item["reason"] == "No table geometry was detected."
    assert item["crop_region"] == [0, 0, item["image_size"][0], item["image_size"][1]]
    assert (evidence_dir / item["crop_file"]).is_file()
    queue = (evidence_dir / "review-queue.html").read_text(encoding="utf-8")
    assert "No numeric value read." in queue
    assert "No table geometry was detected." in queue


def test_evidence_output_is_rejected_inside_repository():
    with pytest.raises(ValueError, match="outside the repository/bundle"):
        extract_capture_folder(
            FIXTURE,
            review_evidence_dir=ROOT / "private-extractor-output" / "e61-test",
        )


def test_evidence_output_does_not_modify_source_capture_folder(tmp_path):
    source_folder = tmp_path / "owner-capture"
    shutil.copytree(FIXTURE, source_folder)
    with pytest.raises(ValueError, match="separate from the source capture folder"):
        extract_capture_folder(
            source_folder,
            review_evidence_dir=source_folder / "review-evidence",
        )
    assert not (source_folder / "review-evidence").exists()


def test_frozen_bundle_directory_is_not_an_evidence_destination(tmp_path, monkeypatch):
    bundle = tmp_path / "kandoo-extract"
    bundle.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(bundle / "kandoo-extract.exe"))
    with pytest.raises(ValueError, match="outside the repository/bundle"):
        extract_capture_folder(
            FIXTURE,
            review_evidence_dir=bundle / "owner-output",
        )


def test_unknown_but_readable_layout_routes_to_review_without_threshold_tuning(tmp_path, monkeypatch):
    image_path = tmp_path / "unknown-layout.png"
    Image.new("RGB", (80, 60), "white").save(image_path)
    monkeypatch.setattr(
        pipeline_v0,
        "detect_layout_safe",
        lambda _image: LayoutSafetyResult(
            status="REVIEW",
            reason="Unknown readable layout.",
            geometry=None,
            row_count=None,
        ),
    )

    result = extract_pipeline_v0(image_path)
    assert result.status == "REVIEW"
    assert result.layout_status == "REVIEW"
    assert result.layout_reason == "Unknown readable layout."
    assert result.cell_results == ()
    assert result.canonical_invoice is None

    capture_result = extract_capture_folder(
        FIXTURE,
        e05_bank_path=ROOT / "tests/fixtures/o15/e05-bank-synthetic.json",
    )
    assert capture_result["status"] == "REVIEW"
    assert capture_result["verdict"] == "REVIEW"
    assert capture_result["pages"][0]["e02"]["layout_status"] == "REVIEW"
    assert DEFAULT_MINIMUM_CONFIDENCE == 60.0
