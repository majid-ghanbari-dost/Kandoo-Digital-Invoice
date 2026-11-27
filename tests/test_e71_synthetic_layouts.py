from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from image_extraction_adapter.synthetic_layouts import (
    measure_layout_match_accuracy,
    measure_synthetic_numeric_accuracy_by_layout,
    render_synthetic_invoice,
    synthetic_layouts,
)


def test_second_and_third_synthetic_layouts_change_columns_logo_and_currency(tmp_path):
    profiles = synthetic_layouts()
    assert [profile.layout_id for profile in profiles] == ["layout-1", "layout-2", "layout-3"]
    assert len({profile.column_boundaries for profile in profiles}) == 3
    assert len({profile.logo_size for profile in profiles}) == 3
    assert len({profile.currency_label for profile in profiles}) == 3

    rendered = [
        render_synthetic_invoice(
            tmp_path / f"{profile.layout_id}-train.png",
            layout_id=profile.layout_id,
            invoice_index=0,
        )
        for profile in profiles
    ]
    assert all(invoice.expected_values["invoice.payable"] == "2000" for invoice in rendered)
    for invoice in rendered:
        with Image.open(invoice.image_path) as image:
            assert image.format == "PNG"
            assert image.size == (640, 520)


def test_layout_match_accuracy_is_reported_separately_for_each_holdout_layout(tmp_path):
    profiles = synthetic_layouts()
    training = [
        render_synthetic_invoice(
            tmp_path / f"{profile.layout_id}-train.png",
            layout_id=profile.layout_id,
            invoice_index=0,
        )
        for profile in profiles
    ]
    holdout = [
        render_synthetic_invoice(
            tmp_path / f"{profile.layout_id}-holdout.png",
            layout_id=profile.layout_id,
            invoice_index=1,
        )
        for profile in profiles
    ]

    metrics = measure_layout_match_accuracy(training, holdout)
    assert set(metrics) == {profile.layout_id for profile in profiles}
    assert all(item["metric"] == "synthetic_layout_match_accuracy" for item in metrics.values())
    assert all(item["correct"] == 1 and item["total"] == 1 for item in metrics.values())
    assert all(item["accuracy"] == 1.0 for item in metrics.values())


def test_numeric_accuracy_is_measured_by_layout_with_zero_extracted_wrong(tmp_path):
    profiles = synthetic_layouts()
    training = [
        render_synthetic_invoice(
            tmp_path / f"{profile.layout_id}-train.png",
            layout_id=profile.layout_id,
            invoice_index=0,
        )
        for profile in profiles
    ]
    holdout = [
        render_synthetic_invoice(
            tmp_path / f"{profile.layout_id}-holdout.png",
            layout_id=profile.layout_id,
            invoice_index=1,
        )
        for profile in profiles
    ]

    metrics = measure_synthetic_numeric_accuracy_by_layout(training, holdout)
    assert set(metrics) == {profile.layout_id for profile in profiles}
    for result in metrics.values():
        assert result["expected_fields"] == 5
        assert result["extracted_fields"] == 5
        assert result["correct_fields"] == 5
        assert result["extracted_but_wrong"] == 0
        assert result["review_or_missing_fields"] == 0
        assert result["accuracy"] == 1.0
