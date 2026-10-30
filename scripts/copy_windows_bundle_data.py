#!/usr/bin/env python3
"""Copy runtime data files required by the Windows one-folder executable."""
from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist" / "kandoo-extract"


def _copy_file(source: str, destination: str) -> None:
    source_path = ROOT / source
    destination_path = BUNDLE / destination
    if not source_path.is_file():
        raise FileNotFoundError(f"required bundle input is missing: {source_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)


def main() -> int:
    executable = BUNDLE / "kandoo-extract.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"PyInstaller did not produce {executable}")

    for relative in (
        "src/templates_bank_default.json",
        "src/glyph_drift_baseline_v1.json",
        "schemas/canonical_invoice_v0.json",
        "tests/fixtures/real/labels.json",
        "tests/fixtures/real/29.png",
        "tests/fixtures/real/31.png",
        "tests/fixtures/real/32.png",
        "tests/fixtures/real/33.png",
    ):
        _copy_file(relative, relative)

    mode_b_source = ROOT / "schemas" / "mode-b" / "v1"
    if not mode_b_source.is_dir():
        raise FileNotFoundError(f"required Mode B schema directory is missing: {mode_b_source}")
    shutil.copytree(mode_b_source, BUNDLE / "schemas" / "mode-b" / "v1", dirs_exist_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
