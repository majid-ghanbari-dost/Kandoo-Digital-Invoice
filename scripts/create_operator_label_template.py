"""Create a local operator-label JSON template from E-61 review evidence."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from image_extraction_adapter.operator_labels import build_operator_label_template


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        required=True,
        help="local E-61 review-evidence directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="new filename inside the evidence directory (default: operator-labels.local.json)",
    )
    args = parser.parse_args(argv)
    try:
        target = build_operator_label_template(args.evidence_dir, args.out)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 30
    print(f"Created local operator label template: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
