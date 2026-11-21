#!/usr/bin/env python3
"""Build the deterministic, OCR-free-by-default N-07 name work-list."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from n04_name_suggestions import ParisaOCRNameSuggester
from n07_name_worklist import (
    build_name_worklist,
    load_confirmations,
    serialize_worklist,
)

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--confirmations",
        type=Path,
        help="optional n07.name-confirmations.v1 JSON keyed by exact crop-cluster ID",
    )
    parser.add_argument(
        "--captured-at",
        metavar="ISO",
        help="optional offset-aware Probe capture time for price observations",
    )
    parser.add_argument(
        "--suggest-names",
        action="store_true",
        help="opt in to N-04 ParisaOCR; default work-list performs no OCR",
    )
    args = parser.parse_args(argv)

    confirmations = load_confirmations(args.confirmations) if args.confirmations else {}
    suggester = None
    if args.suggest_names:
        if importlib.util.find_spec("parisaocr") is None:
            parser.error("--suggest-names requires the optional ParisaOCR package to be installed")
        suggester = ParisaOCRNameSuggester()

    output_dir = args.output_dir.expanduser().resolve()
    document = build_name_worklist(
        args.repo_root.resolve(),
        output_dir,
        captured_at=args.captured_at,
        confirmed_names=confirmations,
        suggester=suggester,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "name-worklist.json"
    output_path.write_text(serialize_worklist(document), encoding="utf-8", newline="\n")
    summary = {
        "output_json": str(output_path),
        "schema_version": document["schema_version"],
        "candidate_count": len(document["work_items"]),
        "crop_image_count": sum(item["crop_image"]["file"].endswith(".png") for item in document["work_items"]),
        "unconfirmed_count": sum(
            item["candidate"]["name_confirmation"]["confirmation_status"] == "UNCONFIRMED"
            for item in document["work_items"]
        ),
        "review_required_count": sum(
            item["candidate"]["name_confirmation"]["review_required"]
            for item in document["work_items"]
        ),
        "name_suggestions_enabled": document["name_suggestions_enabled"],
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
