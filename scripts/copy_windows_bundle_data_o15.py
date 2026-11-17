"""Copy only required, non-customer runtime data into a PyInstaller one-folder build."""
from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist" / "kandoo-extract"

DATA_FILES = (
    ("src/templates_bank_default.json", "src/templates_bank_default.json"),
    ("src/glyph_drift_baseline_v1.json", "src/glyph_drift_baseline_v1.json"),
    ("schemas/canonical_invoice_v0.json", "schemas/canonical_invoice_v0.json"),
    (
        "schemas/o15/review-evidence-v1.schema.json",
        "schemas/o15/review-evidence-v1.schema.json",
    ),
    (
        "schemas/e28/glyph_drift_baseline_v1.schema.json",
        "schemas/e28/glyph_drift_baseline_v1.schema.json",
    ),
    (
        "schemas/e28/glyph_drift_report_v1.schema.json",
        "schemas/e28/glyph_drift_report_v1.schema.json",
    ),
    ("schemas/mode-b/v1/template-bank.schema.json", "schemas/mode-b/v1/template-bank.schema.json"),
    ("schemas/mode-b/v1/onboarding-verdict.schema.json", "schemas/mode-b/v1/onboarding-verdict.schema.json"),
    ("schemas/mode-b/v1/new-type-candidate.schema.json", "schemas/mode-b/v1/new-type-candidate.schema.json"),
    ("schemas/mode-b/v1/layout-font-fingerprint.schema.json", "schemas/mode-b/v1/layout-font-fingerprint.schema.json"),
)


def main() -> int:
    executable = BUNDLE / "kandoo-extract.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"PyInstaller did not produce {executable}")

    # PyInstaller 6 one-folder apps keep Python modules/data in _internal.
    # Fall back to the bundle root for compatible builds configured without it.
    internal = BUNDLE / "_internal"
    destination_root = internal if internal.is_dir() else BUNDLE
    for source_name, destination_name in DATA_FILES:
        source = ROOT / source_name
        if not source.is_file():
            raise FileNotFoundError(f"required bundle input is missing: {source_name}")
        target = destination_root / destination_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
