from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image
import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from image_extraction_adapter.cli import main as cli_main
from image_extraction_adapter.operator_labels import build_operator_label_template
from image_extraction_adapter.review_evidence import ReviewPageSource, write_review_evidence

LABEL_SCHEMA_PATH = ROOT / "schemas/o15/operator-label-v1.schema.json"


def _evidence_dir(tmp_path: Path) -> Path:
    image_path = tmp_path / "synthetic-page.png"
    Image.new("RGB", (30, 20), "white").save(image_path)
    cell = SimpleNamespace(
        field_name="line.1.total",
        raw_value="1234",
        confidence=91.5,
        status="EXTRACTED",
        reason=None,
        bbox=(3, 4, 24, 15),
    )
    page = ReviewPageSource(
        page_index=1,
        image_path=image_path,
        pipeline_status="AUTO_CANDIDATE",
        layout_status="OK",
        layout_reason="Synthetic test geometry.",
        pipeline_reason="Synthetic test evidence.",
        cell_results=(cell,),
    )
    return write_review_evidence(tmp_path / "review-evidence", (page,))


def _validator() -> Draft202012Validator:
    schema = json.loads(LABEL_SCHEMA_PATH.read_bytes().decode("utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_operator_label_template_has_correctness_and_correction_slots_without_learning(tmp_path):
    evidence_dir = _evidence_dir(tmp_path)
    template_bank = ROOT / "src/templates_bank_default.json"
    before = hashlib.sha256(template_bank.read_bytes()).hexdigest()

    output_path = build_operator_label_template(evidence_dir)
    document = json.loads(output_path.read_bytes().decode("utf-8"))
    _validator().validate(document)
    assert document["online_learning"] is False
    assert len(document["entries"]) == 1
    entry = document["entries"][0]
    assert entry["field_name"] == "line.1.total"
    assert entry["value"] == "1234"
    assert entry["confidence"] == 91.5
    assert entry["read_correctly"] is None
    assert entry["corrected_value"] is None
    assert hashlib.sha256(template_bank.read_bytes()).hexdigest() == before


def test_cli_operator_label_template_command(tmp_path):
    evidence_dir = _evidence_dir(tmp_path)
    assert cli_main([
        "operator-label-template",
        "--evidence-dir",
        str(evidence_dir),
    ]) == 0
    output_path = evidence_dir / "operator-labels.local.json"
    document = json.loads(output_path.read_bytes().decode("utf-8"))
    _validator().validate(document)
    assert document["online_learning"] is False


def test_operator_label_schema_accepts_correct_and_corrected_and_rejects_conflicts(tmp_path):
    evidence_dir = _evidence_dir(tmp_path)
    document = json.loads(
        build_operator_label_template(evidence_dir).read_bytes().decode("utf-8")
    )
    validator = _validator()
    entry = document["entries"][0]

    entry["read_correctly"] = True
    validator.validate(document)
    entry["read_correctly"] = False
    entry["corrected_value"] = "1299"
    validator.validate(document)

    entry["corrected_value"] = None
    with pytest.raises(ValidationError):
        validator.validate(document)
    entry["read_correctly"] = True
    entry["corrected_value"] = "1299"
    with pytest.raises(ValidationError):
        validator.validate(document)


def test_operator_label_output_is_local_and_never_overwrites(tmp_path):
    evidence_dir = _evidence_dir(tmp_path)
    with pytest.raises(ValueError, match="outside the repository/bundle"):
        build_operator_label_template(
            evidence_dir,
            ROOT / "operator-labels.local.json",
        )
    assert not (ROOT / "operator-labels.local.json").exists()
    with pytest.raises(ValueError, match="written in the evidence directory"):
        build_operator_label_template(evidence_dir, tmp_path / "separate-labels.json")

    output_path = build_operator_label_template(evidence_dir)
    with pytest.raises(FileExistsError):
        build_operator_label_template(evidence_dir, output_path)
