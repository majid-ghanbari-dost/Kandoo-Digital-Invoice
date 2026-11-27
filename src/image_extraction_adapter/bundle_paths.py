"""Locate immutable app assets in source checkouts and PyInstaller onedir builds."""
from __future__ import annotations

from pathlib import Path
import sys


def resource_root() -> Path:
    """Return the repository/bundle directory containing schemas and template data.

    PyInstaller's module ``__file__`` layout may omit the source ``src/`` level,
    while one-folder data files live under ``sys._MEIPASS`` (normally
    ``<bundle>/_internal``). Probe those explicit roots instead of assuming a
    fixed number of parents from a frozen module path.
    """
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str) and meipass:
        base = Path(meipass).resolve()
        candidates.extend((base, base / "_internal"))
    executable_dir = Path(sys.executable).resolve().parent
    candidates.extend((executable_dir / "_internal", executable_dir))
    module_path = Path(__file__).resolve()
    candidates.extend((module_path.parents[1], module_path.parents[2]))

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve(strict=False)
        if candidate in seen:
            continue
        seen.add(candidate)
        if (
            (candidate / "schemas" / "canonical_invoice_v0.json").is_file()
            and (candidate / "src" / "templates_bank_default.json").is_file()
            and (candidate / "src" / "glyph_drift_baseline_v1.json").is_file()
        ):
            return candidate

    # Keep the source-mode failure message anchored at the project root, while
    # missing frozen assets still fail closed at their normal file checks.
    return module_path.parents[2]
