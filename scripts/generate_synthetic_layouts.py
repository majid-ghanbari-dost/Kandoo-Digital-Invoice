#!/usr/bin/env python3
"""Generate deterministic E-41 synthetic invoice-layout test samples."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from synthetic_layout_generator import MAX_SAMPLES, generate_dataset  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True, help="non-negative signed-64-bit seed")
    parser.add_argument("--count", type=int, required=True, help=f"sample count in 1..{MAX_SAMPLES}")
    parser.add_argument("--out-dir", type=Path, required=True, help="new or empty output directory")
    args = parser.parse_args(argv)
    try:
        manifest = generate_dataset(args.out_dir, seed=args.seed, count=args.count)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"BLOCKED E-41: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        f"PASS E-41 seed={manifest['seed']} samples={manifest['sample_count']} "
        f"evidence_class={manifest['evidence_class']} "
        f"manifest={Path(args.out_dir).resolve() / 'manifest.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
