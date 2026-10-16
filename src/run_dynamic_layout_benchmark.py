"""Report projection-based table geometry for the supplied 4/5/13-row images."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from image_extraction_adapter.preprocessing import (  # noqa: E402
    crop_spatial_cells,
    detect_dynamic_table_layout,
)


EXPECTED_ROWS = {
    "holo_row_detection.png": 4,
    "5.png": 5,
    "13.png": 13,
}


def main() -> int:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - optional runtime
        print(f"Missing Module: Pillow is required for projection geometry: {exc}")
        return 2

    root = Path(__file__).resolve().parents[1]
    image_root = root / "deliveries" / "image-extraction-ocr"
    ok = True
    print("detector=projection/median-row-height")
    print("line_fraction=0.80")
    print("row_coords=derived-from-image; no fixed x/y row coordinates")
    for name, expected_rows in EXPECTED_ROWS.items():
        path = image_root / name
        if not path.is_file():
            print(f"{name}: MISSING {path}")
            ok = False
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with Image.open(path) as opened:
            opened.load()
            image = opened.convert("RGB")
            layout = detect_dynamic_table_layout(image)
            if layout is None:
                print(f"{name}: DETECTION_FAILED sha256={digest}")
                ok = False
                continue
            crops = crop_spatial_cells(
                image,
                SimpleNamespace(assessments=()),
                include_payable=False,
            )
        success = (len(layout.row_bands) == expected_rows
                   and len(layout.column_boundaries) == 5
                   and len(crops) == expected_rows * 3)
        ok &= success
        print(
            f"{name}: rows={len(layout.row_bands)}/{expected_rows} "
            f"columns={len(layout.column_boundaries)} "
            f"row_cells={len(crops)} median_row_height={layout.median_row_height:.1f} "
            f"header_excluded={layout.header_row_excluded} "
            f"horizontal_lines={tuple(round(y, 1) for y in layout.horizontal_lines)} "
            f"column_boundaries={tuple(round(x, 1) for x in layout.column_boundaries)} "
            f"sha256={digest} result={'PASS' if success else 'FAIL'}"
        )
    print(f"overall={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
