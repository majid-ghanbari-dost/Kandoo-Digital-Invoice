#!/usr/bin/env python3
"""Build an N-04 ProductCandidate document with optional local name suggestions.

The default path does not import an OCR engine and writes an explicit empty
``name_suggestions`` list for every candidate. Pass ``--suggest-names`` to
opt into the CPU-only, locally bundled ParisaOCR runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from n04_name_suggestions import (
    ROOT,
    ParisaOCRNameSuggester,
    build_name_suggestion_document,
    serialize_document,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument(
        "--suggest-names",
        action="store_true",
        help="explicitly enable the optional ParisaOCR CPU runtime",
    )
    args = parser.parse_args(argv)

    suggester = ParisaOCRNameSuggester() if args.suggest_names else None
    document = build_name_suggestion_document(
        args.repo_root.resolve(), suggester=suggester)
    output_path = args.output_json.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        serialize_document(document), encoding="utf-8", newline="\n")

    print(json.dumps({
        "output_json": str(output_path),
        "schema_version": document["schema_version"],
        "candidate_count": len(document["candidates"]),
        "name_suggestions_enabled": document["name_suggestions_enabled"],
        "candidate_suggestion_count": sum(
            len(candidate["name_suggestions"])
            for candidate in document["candidates"]
        ),
        "accepted_suggestion_count": sum(
            int(suggestion["accepted"])
            for candidate in document["candidates"]
            for suggestion in candidate["name_suggestions"]
        ),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
