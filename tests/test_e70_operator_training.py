from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from e05_template_bank import LayoutObservation
from image_extraction_adapter.cli import main as cli_main
from image_extraction_adapter.operator_labels import build_operator_label_template
from image_extraction_adapter.operator_training import build_operator_training_report
from image_extraction_adapter.review_evidence import ReviewPageSource, write_review_evidence


def _make_sample(tmp_path: Path, sample_id: str, labels: dict[str, tuple[str, bool | None, str | None]]):
    capture_dir = tmp_path / f"capture-{sample_id}"
    capture_dir.mkdir()
    (capture_dir / "job.spl").write_bytes(b"SYNTHETIC E-70 capture envelope\n")
    (capture_dir / "Report.txt").write_text(
        f"Spool job ID: synthetic-e70-{sample_id}\nPage count: 1\n",
        encoding="utf-8",
    )

    image_path = capture_dir / "page1.png"
    image = Image.new("RGB", (360, 260), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    cells = []
    for ordinal, (field_name, (machine_value, _confirmed, _correction)) in enumerate(labels.items()):
        left = 12
        top = 12 + ordinal * 45
        right = 345
        bottom = top + 34
        draw.text((left + 5, top + 8), machine_value or "?", fill="black", font=font)
        cells.append(SimpleNamespace(
            field_name=field_name,
            raw_value=machine_value,
            confidence=88.0,
            status="EXTRACTED" if machine_value else "REVIEW",
            reason="Synthetic E-70 test cell.",
            bbox=(left, top, right, bottom),
        ))
    image.save(image_path, format="PNG")
    image.close()

    evidence_dir = write_review_evidence(
        tmp_path / f"evidence-{sample_id}",
        (ReviewPageSource(
            page_index=1,
            image_path=image_path,
            pipeline_status="REVIEW",
            layout_status="OK",
            layout_reason="Synthetic test geometry.",
            pipeline_reason="Synthetic operator-confirmation test.",
            cell_results=tuple(cells),
        ),),
    )
    labels_path = build_operator_label_template(evidence_dir)
    labels_doc = json.loads(labels_path.read_text(encoding="utf-8"))
    for entry in labels_doc["entries"]:
        field_name = entry["field_name"]
        _value, confirmed, correction = labels[field_name]
        entry["read_correctly"] = confirmed
        entry["corrected_value"] = correction
    labels_path.write_text(
        json.dumps(labels_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return capture_dir, evidence_dir, labels_path


def _fake_observation(
    image_path: Path,
    *,
    source_id: str,
    image_width: int,
    image_height: int,
    field_values: dict[str, str],
    payable_bbox: tuple[int, int, int, int],
) -> LayoutObservation:
    assert image_path.is_file()
    return LayoutObservation(
        source_id=source_id,
        image_width=image_width,
        image_height=image_height,
        column_boundaries=(10, 80, 110, 260, 350),
        row_bands=((70, 110),),
        payable_bbox=payable_bbox,
        field_values=field_values,
    )


def test_only_operator_confirmed_values_train_and_unknown_fields_stay_review(tmp_path, monkeypatch):
    import image_extraction_adapter.operator_training as training

    monkeypatch.setattr(training, "_page_layout_observation", _fake_observation)
    incomplete = _make_sample(
        tmp_path,
        "incomplete",
        {
            "line.0.quantity": ("2", False, "3"),
            "line.0.total": ("400", True, None),
            "invoice.payable": ("400", True, None),
            "line.1.quantity": ("999", None, None),
        },
    )
    complete = _make_sample(
        tmp_path,
        "complete",
        {
            "line.0.quantity": ("3", True, None),
            "line.0.total": ("400", True, None),
            "invoice.payable": ("400", True, None),
        },
    )

    report = build_operator_training_report(
        (incomplete, complete),
        currency_unit="rial",
    )
    row_labels = report.glyph_templates.counts()["row"]
    assert "۳" in row_labels
    assert "۲" not in row_labels  # the machine reading lost to the operator correction
    assert "۹" not in row_labels  # the uncertain field never entered the baseline
    assert report.confirmed_label_count == 6
    assert report.uncertain_label_count == 1
    assert report.layout_observation_count == 1
    assert report.layout_review_page_count == 1
    assert report.layout_bank.currency_unit == "rial"
    assert len(report.layout_bank.templates) == 1


def test_onboard_learn_writes_local_baselines_without_test_kit_and_returns_review(tmp_path, monkeypatch):
    import image_extraction_adapter.operator_training as training

    monkeypatch.setattr(training, "_page_layout_observation", _fake_observation)
    uncertain_sample = _make_sample(
        tmp_path,
        "cli-uncertain",
        {
            "line.0.quantity": ("3", True, None),
            "line.0.total": ("400", True, None),
            "invoice.payable": ("400", True, None),
            "line.1.quantity": ("999", None, None),
        },
    )
    complete_sample = _make_sample(
        tmp_path,
        "cli-complete",
        {
            "line.0.quantity": ("3", True, None),
            "line.0.total": ("400", True, None),
            "invoice.payable": ("400", True, None),
        },
    )
    output_dir = tmp_path / "local-e70-baseline"
    exit_code = cli_main([
        "onboard",
        "learn",
        "--sample", str(uncertain_sample[0]), str(uncertain_sample[1]), str(uncertain_sample[2]),
        "--sample", str(complete_sample[0]), str(complete_sample[1]), str(complete_sample[2]),
        "--store-id", "synthetic-store-e70",
        "--currency-unit", "rial",
        "--output-dir", str(output_dir),
    ])
    assert exit_code == 10
    assert {path.name for path in output_dir.iterdir()} == {
        "glyph-templates.local.json",
        "e05-template-bank.local.json",
        "e70-onboarding-summary.local.json",
    }
    summary = json.loads((output_dir / "e70-onboarding-summary.local.json").read_text(encoding="utf-8"))
    assert summary["online_learning"] is False
    assert summary["uncertain_label_count"] == 1
    assert summary["layout_review_page_count"] == 1
    assert "999" not in (output_dir / "glyph-templates.local.json").read_text(encoding="utf-8")

    schema_path = ROOT / "schemas/mode-b/v1/template-bank.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    artifact = json.loads((output_dir / "e05-template-bank.local.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(artifact)


def test_onboard_learn_refuses_repository_output(tmp_path):
    sample = _make_sample(
        tmp_path,
        "repo-output",
        {
            "line.0.quantity": ("3", True, None),
            "line.0.total": ("400", True, None),
            "invoice.payable": ("400", True, None),
        },
    )
    exit_code = cli_main([
        "onboard",
        "learn",
        "--sample", str(sample[0]), str(sample[1]), str(sample[2]),
        "--store-id", "synthetic-store-e70",
        "--currency-unit", "rial",
        "--output-dir", str(ROOT / "e70-baseline.local"),
    ])
    assert exit_code == 30
    assert not (ROOT / "e70-baseline.local").exists()
