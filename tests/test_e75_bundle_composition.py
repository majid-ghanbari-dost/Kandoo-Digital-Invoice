"""Unit tests for the E-75 bundle composition accounting (PY-B, PM-36)."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_windows_bundle import _bundle_composition  # noqa: E402


def _make_bundle(root: Path) -> tuple[Path, list[Path]]:
    """Mirror the real PyInstaller 6 one-dir layout (runtime under _internal/)."""
    bundle = root / "kandoo-extract"
    files = {
        "kandoo-extract.exe": 4_000_000,
        "_internal/python311.dll": 5_000_000,
        "_internal/libcrypto-3.dll": 5_191_960,
        "_internal/base_library.zip": 2_000_000,
        "_internal/PIL/_imaging.cp311-win_amd64.pyd": 2_662_400,
        "_internal/PIL/_avif.cp311-win_amd64.pyd": 7_888_896,
        "_internal/PIL/Image.py": 150_000,
        "_internal/jsonschema/validators.py": 60_000,
        "_internal/jsonschema/tests/test_validators.py": 20_000,
        "_internal/rpds/rpds.pyd": 2_500_000,
        "_internal/python-code.pyc": 346_362,
        "schemas/canonical_invoice_v0.json": 15_000,
        "tests/fixtures/real/29.png": 24_000,
        "README.txt": 100,
    }
    for relative, size in files.items():
        path = bundle / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    return bundle, [path for path in bundle.rglob("*") if path.is_file()]


def test_composition_categorizes_and_ranks(tmp_path: Path):
    bundle, files = _make_bundle(tmp_path)
    composition = _bundle_composition(bundle, files)
    categories = composition["categories_bytes"]
    assert categories["package:PIL"] == 7_888_896 + 2_662_400 + 150_000
    assert categories["package:jsonschema"] == 80_000
    assert categories["package:rpds"] == 2_500_000
    assert categories["app-data"] == 39_000
    assert categories["python-base-zip"] == 2_000_000
    assert categories["python-code"] == 346_362
    assert categories["native-libs"] == 5_000_000 + 5_191_960
    assert categories["other"] == 4_000_000 + 100
    largest = composition["largest_files"]
    assert largest[0] == {
        "path": "_internal/PIL/_avif.cp311-win_amd64.pyd",
        "bytes": 7_888_896,
    }
    assert largest[1] == {"path": "_internal/libcrypto-3.dll", "bytes": 5_191_960}
    assert largest[2] == {"path": "_internal/python311.dll", "bytes": 5_000_000}
    assert len(largest) == len(files)


def test_composition_totals_reconcile_with_bundle_size(tmp_path: Path):
    bundle, files = _make_bundle(tmp_path)
    composition = _bundle_composition(bundle, files)
    total = sum(composition["categories_bytes"].values())
    assert total == sum(path.stat().st_size for path in files)
