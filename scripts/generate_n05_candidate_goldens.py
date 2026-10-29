#!/usr/bin/env python3
"""Generate four deterministic N-05 ProductCandidate golden examples.

The base build is text-free and OCR-free. N-04 suggestions are added only when
an optional suggester is explicitly supplied (the CLI flag also requires that
the optional ParisaOCR package be installed).
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
    SOURCE_SCHEMA_VERSION,
    CropReference,
    NameRecognition,
    NameSuggester,
    NameSuggestion,
    serialize_document,
)
from run_n02_product_candidates import (  # noqa: E402
    CANONICAL_DIR,
    build_product_candidates,
)

N05_SCHEMA_VERSION = "n05.product-candidate.v1"
GOLDEN_DIR = Path("tests/fixtures/real/n05-goldens")
EXAMPLE_CROPS = (
    ("29", "29_row0"),
    ("31", "31_row0"),
    ("32", "32_row1"),
    ("33", "33_row10"),
)


def _empty_name_confirmation() -> dict[str, Any]:
    return {
        "confirmed_name": "",
        "confirmation_status": "UNCONFIRMED",
        "confirmation_source_cluster_id": None,
        "review_required": False,
        "review_reasons": [],
        "near_threshold_cluster_ids": [],
    }


def build_n05_candidate_examples(
    repo_root: Path = ROOT,
    *,
    suggester: NameSuggester | None = None,
) -> dict[str, dict[str, Any]]:
    """Build one candidate example per fixture; default behavior performs no OCR."""
    root = Path(repo_root).resolve()
    n02_document = build_product_candidates(root, write_reference_crops=False)
    candidates_by_crop = {
        Path(candidate["reference_crop_file"]).stem: candidate
        for candidate in n02_document["candidates"]
    }
    examples: dict[str, dict[str, Any]] = {}
    for fixture_id, crop_id in EXAMPLE_CROPS:
        if crop_id not in candidates_by_crop:
            raise ValueError(f"N-02 has no reference candidate for {crop_id}")
        candidate = dict(candidates_by_crop[crop_id])
        if crop_id not in candidate["source_crop_ids"]:
            raise ValueError(f"N-02 candidate reference does not include {crop_id}")
        if candidate["reference_crop_file"].rsplit("/", 1)[-1] != f"{crop_id}.png":
            raise ValueError(f"N-02 candidate reference crop is not the selected crop {crop_id}")

        crop_path = root / candidate["reference_crop_file"]
        if not crop_path.is_file():
            raise FileNotFoundError(f"missing N-02 reference crop: {crop_path}")
        candidate["name_confirmation"] = _empty_name_confirmation()
        candidate["name_suggestions"] = []
        if suggester is not None:
            recognition = suggester.suggest(crop_path)
            if not isinstance(recognition, NameRecognition):
                raise TypeError("suggester.suggest() must return NameRecognition")
            crop_reference = CropReference(
                crop_id=crop_id,
                file=candidate["reference_crop_file"],
                sha256=hashlib.sha256(crop_path.read_bytes()).hexdigest(),
            )
            suggestion = NameSuggestion(
                lines=recognition.lines,
                confidence=recognition.confidence,
                engine=str(suggester.engine_name),
                engine_version=str(suggester.engine_version),
                model_version=str(suggester.model_version),
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
            "name_suggestions_enabled": suggester is not None,
            "candidate": candidate,
        }
    return examples


def write_n05_candidate_goldens(
    repo_root: Path = ROOT,
    output_dir: Path = GOLDEN_DIR,
    *,
    suggester: NameSuggester | None = None,
) -> dict[str, str]:
    """Write canonical UTF-8 JSON goldens and return their serialized contents."""
    root = Path(repo_root).resolve()
    destination = Path(output_dir)
    if not destination.is_absolute():
        destination = root / destination
    destination.mkdir(parents=True, exist_ok=True)

    serialized: dict[str, str] = {}
    for filename, example in build_n05_candidate_examples(root, suggester=suggester).items():
        content = serialize_document(example)
        (destination / filename).write_text(content, encoding="utf-8", newline="\n")
        serialized[filename] = content
    return serialized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=GOLDEN_DIR)
    parser.add_argument(
        "--suggest-names",
        action="store_true",
        help="opt in to the optional local ParisaOCR runtime; omitted by default",
    )
    args = parser.parse_args(argv)

    suggester = None
    if args.suggest_names:
        import importlib.util

        if importlib.util.find_spec("parisaocr") is None:
            parser.error("--suggest-names requires the optional ParisaOCR package to be installed")
        from n04_name_suggestions import ParisaOCRNameSuggester

        suggester = ParisaOCRNameSuggester()
    outputs = write_n05_candidate_goldens(
        args.repo_root,
        args.output_dir,
        suggester=suggester,
    )
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "golden_files": sorted(outputs),
        "golden_count": len(outputs),
        "schema_version": N05_SCHEMA_VERSION,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
