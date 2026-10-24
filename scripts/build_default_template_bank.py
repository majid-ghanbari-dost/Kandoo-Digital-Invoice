#!/usr/bin/env python3
"""Build the E-02 all-four default Glyph bank from local operator-confirmed fixtures."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from image_extraction_adapter.pipeline_v0 import (  # noqa: E402
    DEFAULT_LABELS_PATH,
    DEFAULT_TEMPLATE_BANK_PATH,
    TemplateBankBuildError,
    build_default_template_bank,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--labels",
        type=Path,
        default=DEFAULT_LABELS_PATH,
        help="local OPERATOR_CONFIRMED labels.json (default: tests/fixtures/real/labels.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_TEMPLATE_BANK_PATH,
        help="output path (never src/templates.json)",
    )
    args = parser.parse_args(argv)
    try:
        report = build_default_template_bank(
            labels_path=args.labels,
            output_path=args.out,
            repo_root=REPOSITORY_ROOT,
        )
    except (TemplateBankBuildError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "output_path": report.output_path,
        "bank_sha256": report.bank_sha256,
        "source_images": [dict(source) for source in report.source_images],
        "template_counts": report.template_counts,
        "training_cell_count": report.training_cell_count,
        "used_cell_count": report.used_cell_count,
        "skipped_cells": list(report.skipped_cells),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
