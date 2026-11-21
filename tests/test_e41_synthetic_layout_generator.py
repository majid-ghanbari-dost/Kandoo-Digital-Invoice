from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from synthetic_layout_generator import (
    MAX_SAMPLES,
    SYNTHETIC_MARKER,
    generate_dataset,
)


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


def test_seed_reproduces_identical_manifest_and_png_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    left = generate_dataset(first, seed=20261108, count=8)
    right = generate_dataset(second, seed=20261108, count=8)

    assert left == right
    assert _files(first) == _files(second)
    assert len(left["samples"]) == 8


def test_generated_pages_are_synthetic_only_and_have_no_customer_fields(tmp_path: Path) -> None:
    output = tmp_path / "dataset"
    manifest = generate_dataset(output, seed=41, count=4)
    forbidden_fields = {"customer", "customer_name", "phone", "address", "store_id"}

    assert manifest["evidence_class"] == "SYNTHETIC_ONLY"
    assert manifest["synthetic_marker"] == SYNTHETIC_MARKER
    assert manifest["external_input_sources"] == []
    assert set(manifest["generator_inputs"]) == {"seed", "count"}
    for sample in manifest["samples"]:
        assert forbidden_fields.isdisjoint(sample)
        assert "SYNTHETIC" in sample["sample_id"]
        assert all(item["description"].startswith("SYNTHETIC ITEM ")
                   for item in sample["line_items"])
        assert sample["subtotal_test_only"] == sum(
            item["line_total"] for item in sample["line_items"]
        )
        assert sample["payable_test_only"] == sample["subtotal_test_only"]
        image_path = output / sample["image_file"]
        assert len(sample["image_sha256"]) == 64
        assert hashlib.sha256(image_path.read_bytes()).hexdigest() == sample["image_sha256"]


def test_generated_grid_and_payable_geometry_match_declared_labels(tmp_path: Path) -> None:
    Image = pytest.importorskip("PIL.Image")
    from image_extraction_adapter.pipeline_v0 import detect_payable_bbox
    from image_extraction_adapter.preprocessing import detect_dynamic_table_layout

    output = tmp_path / "dataset"
    manifest = generate_dataset(output, seed=4107, count=12)
    observed_profiles: set[str] = set()
    for sample in manifest["samples"]:
        with Image.open(output / sample["image_file"]) as opened:
            opened.load()
            image = opened.convert("L")
        layout = detect_dynamic_table_layout(image)
        assert layout is not None, sample["sample_id"]
        assert len(layout.column_boundaries) == 5
        assert len(layout.row_bands) == len(sample["row_bands"])
        for actual, expected in zip(
            layout.column_boundaries, sample["column_boundaries"], strict=True
        ):
            assert abs(round(actual) - expected) <= 1
        for actual, expected in zip(layout.row_bands, sample["row_bands"], strict=True):
            assert all(abs(round(value) - target) <= 1
                       for value, target in zip(actual, expected, strict=True))
        assert detect_payable_bbox(image, layout) is not None
        observed_profiles.add(sample["layout_profile"])
    assert len(observed_profiles) == 4


def test_different_seed_changes_generated_samples(tmp_path: Path) -> None:
    left = generate_dataset(tmp_path / "left", seed=17, count=4)
    right = generate_dataset(tmp_path / "right", seed=18, count=4)

    assert left["samples"] != right["samples"]
    assert [item["image_sha256"] for item in left["samples"]] != [
        item["image_sha256"] for item in right["samples"]
    ]


@pytest.mark.parametrize("seed", [-1, True, 0x8000000000000000, "41"])
def test_invalid_seed_is_refused(tmp_path: Path, seed: object) -> None:
    with pytest.raises(ValueError, match="seed"):
        generate_dataset(tmp_path / "dataset", seed=seed, count=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("count", [0, -1, True, MAX_SAMPLES + 1, "4"])
def test_invalid_count_is_refused(tmp_path: Path, count: object) -> None:
    with pytest.raises(ValueError, match="count"):
        generate_dataset(tmp_path / "dataset", seed=1, count=count)  # type: ignore[arg-type]


def test_nonempty_output_directory_is_not_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "nonempty"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("leave untouched", encoding="utf-8")

    with pytest.raises(ValueError, match="must be empty"):
        generate_dataset(output, seed=1, count=1)
    assert sentinel.read_text(encoding="utf-8") == "leave untouched"


def test_manifest_is_stable_json_with_the_declared_seed(tmp_path: Path) -> None:
    output = tmp_path / "dataset"
    manifest = generate_dataset(output, seed=0, count=1)
    raw = (output / "manifest.json").read_bytes()

    assert raw.endswith(b"\n")
    assert json.loads(raw.decode("utf-8")) == manifest
    assert manifest["seed"] == 0
    assert manifest["sample_count"] == 1
