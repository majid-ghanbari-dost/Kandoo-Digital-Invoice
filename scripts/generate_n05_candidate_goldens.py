#!/usr/bin/env python3
"""Generate the four deterministic N-05 ProductCandidate golden examples.

The candidate values are rebuilt from the canonical N-02 fixture inputs. The
name suggestions are the already-recorded, unprocessed ParisaOCR results in
``docs/n01-name-reading.json``; this script does not load or run an OCR engine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from n04_name_suggestions import (  # noqa: E402
    MODEL_VERSION,
    SOURCE_SCHEMA_VERSION,
    CropReference,
    NameRecognition,
    NameSuggestion,
    serialize_document,
)
from run_n02_product_candidates import (  # noqa: E402
    CANONICAL_DIR,
    build_product_candidates,
)

N05_SCHEMA_VERSION = "n05.product-candidate.v1"
N01_RESULTS_PATH = Path("docs/n01-name-reading.json")
GOLDEN_DIR = Path("tests/fixtures/real/n05-goldens")
EXAMPLE_CROPS = (
    ("29", "29_row0"),
    ("31", "31_row0"),
    ("32", "32_row1"),
    ("33", "33_row10"),
)


def build_n05_candidate_examples(repo_root: Path = ROOT) -> dict[str, dict[str, Any]]:
    """Build one actual-crop candidate example for each canonical fixture."""
    root = Path(repo_root).resolve()
    n02_document = build_product_candidates(root, write_reference_crops=False)
    raw_results_path = root / N01_RESULTS_PATH
    n01_document = json.loads(raw_results_path.read_text(encoding="utf-8"))

    engine_info = n01_document["engine_info"]["parisaocr"]
    engine_name = engine_info["engine"]
    engine_version = engine_info["package_version"]
    if not engine_name or not engine_version:
        raise ValueError("N-01 ParisaOCR engine and package versions are required")
    if MODEL_VERSION not in engine_info["recognizer"]:
        raise ValueError("N-01 recognizer version does not match the N-04 model version")

    raw_by_crop: dict[str, dict[str, Any]] = {}
    for result in n01_document["raw_outputs"]:
        if result.get("engine_key") != "parisaocr" or result.get("preprocessing") != "unprocessed":
            continue
        crop_id = result.get("crop_id")
        if crop_id in raw_by_crop:
            raise ValueError(f"duplicate unprocessed ParisaOCR result for {crop_id}")
        raw_by_crop[crop_id] = result

    candidates_by_crop = {
        Path(candidate["reference_crop_file"]).stem: candidate
        for candidate in n02_document["candidates"]
    }
    examples: dict[str, dict[str, Any]] = {}
    for fixture_id, crop_id in EXAMPLE_CROPS:
        if crop_id not in candidates_by_crop:
            raise ValueError(f"N-02 has no reference candidate for {crop_id}")
        if crop_id not in raw_by_crop:
            raise ValueError(f"N-01 has no unprocessed ParisaOCR result for {crop_id}")
        source_result = raw_by_crop[crop_id]
        if source_result.get("error") is not None:
            raise ValueError(f"N-01 ParisaOCR failed for {crop_id}: {source_result['error']}")
        if source_result.get("invoice_id") != fixture_id:
            raise ValueError(f"N-01 crop {crop_id} is not from fixture {fixture_id}")

        lines = tuple(
            line for line in source_result.get("segments", [])
            if isinstance(line, str) and line.strip()
        )
        recognition = NameRecognition(lines, source_result.get("confidence"))
        candidate = dict(candidates_by_crop[crop_id])
        if crop_id not in candidate["source_crop_ids"]:
            raise ValueError(f"N-02 candidate reference does not include {crop_id}")
        if candidate["reference_crop_file"].rsplit("/", 1)[-1] != f"{crop_id}.png":
            raise ValueError(f"N-02 candidate reference crop is not the selected crop {crop_id}")

        crop_path = root / candidate["reference_crop_file"]
        if not crop_path.is_file():
            raise FileNotFoundError(f"missing N-02 reference crop: {crop_path}")
        crop_reference = CropReference(
            crop_id=crop_id,
            file=candidate["reference_crop_file"],
            sha256=hashlib.sha256(crop_path.read_bytes()).hexdigest(),
        )
        suggestion = NameSuggestion(
            lines=recognition.lines,
            confidence=recognition.confidence,
            engine=engine_name,
            engine_version=engine_version,
            model_version=MODEL_VERSION,
            crop_reference=crop_reference,
        )
        candidate["name_suggestions"] = [suggestion.to_dict()]

        fixture_file = (CANONICAL_DIR / f"canonical-{fixture_id}.json").as_posix()
        if not (root / fixture_file).is_file():
            raise FileNotFoundError(f"missing canonical fixture: {root / fixture_file}")
        examples[f"product-candidate-{fixture_id}.golden.json"] = {
            "schema_version": N05_SCHEMA_VERSION,
            "source_schema_version": SOURCE_SCHEMA_VERSION,
            "source_fixture_id": fixture_id,
            "source_fixture_file": fixture_file,
            "price_observation_date_source": n02_document["price_observation_date_source"],
            "name_suggestions_enabled": True,
            "candidate": candidate,
        }
    return examples


def write_n05_candidate_goldens(
    repo_root: Path = ROOT,
    output_dir: Path = GOLDEN_DIR,
) -> dict[str, str]:
    """Write canonical UTF-8 JSON goldens and return their serialized contents."""
    root = Path(repo_root).resolve()
    destination = Path(output_dir)
    if not destination.is_absolute():
        destination = root / destination
    destination.mkdir(parents=True, exist_ok=True)

    serialized: dict[str, str] = {}
    for filename, example in build_n05_candidate_examples(root).items():
        content = serialize_document(example)
        (destination / filename).write_text(content, encoding="utf-8", newline="\n")
        serialized[filename] = content
    return serialized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=GOLDEN_DIR)
    args = parser.parse_args(argv)

    outputs = write_n05_candidate_goldens(args.repo_root, args.output_dir)
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "golden_files": sorted(outputs),
        "golden_count": len(outputs),
        "schema_version": N05_SCHEMA_VERSION,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
