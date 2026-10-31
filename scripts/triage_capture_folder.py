#!/usr/bin/env python3
"""Run the repository's plain-language capture-folder triage tool."""
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from image_extraction_adapter.capture_triage import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
