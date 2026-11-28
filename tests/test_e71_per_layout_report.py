"""CI gate for the E-71 per-layout numbers report (PY-B, PM-36).

The report must cover every declared synthetic layout with reconciled counts,
pass the EXTRACTED-but-wrong = 0 gate, and carry the honesty label in every
view. Numbers are generator mechanics only.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_e71_per_layout_report import SCHEMA_VERSION, collect_per_layout_numbers  # noqa: E402

GOLDEN_PATH = ROOT / "tests" / "golden" / "e71-per-layout-numbers.json"


def test_report_covers_three_layouts_with_reconciled_counts(tmp_path: Path):
    report = collect_per_layout_numbers(tmp_path)
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["synthetic_only"] is True
    assert "NOT real-data extraction accuracy" in report["honesty_label"]
    assert [row["layout_id"] for row in report["layouts"]] == ["layout-1", "layout-2", "layout-3"]
    for row in report["layouts"]:
        numeric = row["numeric_cell_exact"]
        assert numeric["correct_fields"] + numeric["extracted_but_wrong"] == numeric["extracted_fields"]
        assert numeric["extracted_fields"] + numeric["review_or_missing_fields"] == numeric["expected_fields"]
        assert numeric["extracted_but_wrong"] == 0
        assert row["layout_match"]["correct"] == row["layout_match"]["total"] == 1
        # Each layout keeps its own distinct print geometry.
        assert row["layout_profile"]["column_boundaries"]


def test_layout_profiles_stay_distinct(tmp_path: Path):
    report = collect_per_layout_numbers(tmp_path)
    boundaries = {tuple(row["layout_profile"]["column_boundaries"]) for row in report["layouts"]}
    logos = {tuple(row["layout_profile"]["logo_size"]) for row in report["layouts"]}
    currencies = {row["layout_profile"]["currency_label"] for row in report["layouts"]}
    assert len(boundaries) == len(logos) == len(currencies) == 3


def test_gate_result_is_recorded(tmp_path: Path):
    report = collect_per_layout_numbers(tmp_path)
    assert report["gate"] == {
        "name": "EXTRACTED-but-wrong = 0",
        "extracted_but_wrong_total": 0,
        "result": "PASS",
    }


def test_numbers_match_golden(tmp_path: Path):
    report = collect_per_layout_numbers(tmp_path)
    golden = json.loads(GOLDEN_PATH.read_bytes().decode("utf-8"))
    assert json.dumps(report, ensure_ascii=False, indent=2) + "\n" == (
        json.dumps(golden, ensure_ascii=False, indent=2) + "\n"
    )
