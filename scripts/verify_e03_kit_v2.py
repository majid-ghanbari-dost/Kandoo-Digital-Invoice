#!/usr/bin/env python3
"""Validate the E-03 v2 page set, numeric ground truth, and coverage matrix.

This script validates the authored values and, when requested, the shape of an
owner-provided KandooPrintProbe capture directory. It does not capture a Windows
spool job, convert SPL to PNG, or certify the origin/accuracy of a capture.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
KIT_DIR = REPO_ROOT / "docs" / "E-03-kit-v2"
PAGE_FILES = {
    "learning-1": "learning-1.md",
    "learning-2": "learning-2.md",
    "learning-3": "learning-3.md",
    "exam": "exam.md",
}
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
REQUIRED_GLYPHS = PERSIAN_DIGITS + ","
MIN_GLYPH_COUNT = 5
PERSIAN_TO_ASCII = str.maketrans(PERSIAN_DIGITS, "0123456789")
QUANTITY_RE = re.compile(r"^[۰-۹]+$")
AMOUNT_RE = re.compile(r"^[۰-۹]{1,3}(?:,[۰-۹]{3})+$")
MATRIX_ROW_RE = re.compile(
    r"^\|\s*(?:\d+|comma)\s*\|\s*`([۰-۹,])`\s*\|\s*(\d+)\s*\|"
)
ITEM_LABEL_RE = re.compile(r"^Item [A-D]$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _fail(message: str) -> None:
    raise ValueError(message)


def _parse_quantity(value: Any, where: str) -> int:
    if not isinstance(value, str) or not QUANTITY_RE.fullmatch(value):
        _fail(f"{where} must be a whole Persian-digit quantity without separators")
    parsed = int(value.translate(PERSIAN_TO_ASCII))
    if parsed <= 0:
        _fail(f"{where} must be greater than zero")
    return parsed


def _parse_amount(value: Any, where: str) -> int:
    if not isinstance(value, str) or not AMOUNT_RE.fullmatch(value):
        _fail(f"{where} must use Persian digits and comma-separated thousands")
    return int(value.translate(PERSIAN_TO_ASCII).replace(",", ""))


def _page_values_from_markdown(path: Path) -> dict[str, Any]:
    quantities: list[str] = []
    line_totals: list[str] = []
    payable: str | None = None

    for source_line in path.read_text(encoding="utf-8").splitlines():
        line = source_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("*").strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        label = cells[0]
        if ITEM_LABEL_RE.fullmatch(label):
            quantities.append(cells[1])
            line_totals.append(cells[2])
        elif label.casefold().startswith("payable"):
            payable = cells[-1]

    if not quantities or payable is None:
        _fail(f"{path.name}: expected item rows and an invoice-level payable table row")
    return {"quantities": quantities, "line_totals": line_totals, "payable": payable}


def _coverage_from_values(data: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for page_id, page in data.items():
        page_counts: Counter[str] = Counter()
        for field in ("quantities", "line_totals"):
            page_counts.update(glyph for value in page[field] for glyph in value)
        page_counts.update(page["payable"])
        counts.update(page_counts)
        if page_counts["۲"] < MIN_GLYPH_COUNT or page_counts["۶"] < MIN_GLYPH_COUNT:
            _fail(
                f"{page_id}: existing E-06 kit coverage also requires at least five "
                f"Persian ۲ and ۶ glyphs on each page"
            )
    return counts


def _read_matrix(readme_path: Path) -> dict[str, int]:
    matrix: dict[str, int] = {}
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        match = MATRIX_ROW_RE.match(line.strip())
        if match:
            glyph, count = match.groups()
            if glyph in matrix:
                _fail(f"README coverage matrix repeats glyph {glyph!r}")
            matrix[glyph] = int(count)
    if set(matrix) != set(REQUIRED_GLYPHS):
        _fail("README coverage matrix must contain exactly digits ۰–۹ and comma")
    return matrix


def verify_kit(kit_dir: Path = KIT_DIR) -> dict[str, int]:
    """Validate the four authored pages, answer key, arithmetic, and matrix."""
    expected_page_files = {"README.md", "expected-values.json", *PAGE_FILES.values()}
    actual_files = {path.name for path in kit_dir.iterdir() if path.is_file()}
    markdown_pages = {name for name in actual_files if name.endswith(".md") and name != "README.md"}
    if markdown_pages != set(PAGE_FILES.values()):
        _fail(
            "kit must contain exactly three learning page files and one exam page file; "
            f"found {sorted(markdown_pages)}"
        )
    missing = expected_page_files - actual_files
    if missing:
        _fail(f"kit is missing required files: {sorted(missing)}")

    values_path = kit_dir / "expected-values.json"
    try:
        data = json.loads(values_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"expected-values.json is invalid JSON: {exc}")
    if not isinstance(data, dict) or set(data) != set(PAGE_FILES):
        _fail(f"expected-values.json must contain exactly these page keys: {list(PAGE_FILES)}")

    for page_id, filename in PAGE_FILES.items():
        page = data[page_id]
        if not isinstance(page, dict) or set(page) != {"quantities", "line_totals", "payable"}:
            _fail(
                f"{page_id}: expected-values fields must be only quantities, line_totals, and payable"
            )
        quantities = page["quantities"]
        line_totals = page["line_totals"]
        if not isinstance(quantities, list) or not isinstance(line_totals, list):
            _fail(f"{page_id}: quantities and line_totals must be arrays")
        if len(quantities) != len(line_totals) or len(quantities) != 4:
            _fail(f"{page_id}: each page must have exactly four quantity/line-total pairs")

        quantity_values = [
            _parse_quantity(value, f"{page_id}.quantities[{index}]")
            for index, value in enumerate(quantities)
        ]
        total_values = [
            _parse_amount(value, f"{page_id}.line_totals[{index}]")
            for index, value in enumerate(line_totals)
        ]
        payable_value = _parse_amount(page["payable"], f"{page_id}.payable")
        if sum(total_values) != payable_value:
            _fail(f"{page_id}: payable does not equal the sum of line totals")
        if any(value <= 0 for value in quantity_values):
            _fail(f"{page_id}: quantities must be positive whole numbers")

        page_path = kit_dir / filename
        if not page_path.is_file():
            _fail(f"missing page file: {filename}")
        rendered = _page_values_from_markdown(page_path)
        if rendered != page:
            _fail(f"{filename}: page table values do not match expected-values.json")

    counts = _coverage_from_values(data)
    missing_glyphs = {
        glyph: counts[glyph]
        for glyph in REQUIRED_GLYPHS
        if counts[glyph] < MIN_GLYPH_COUNT
    }
    if missing_glyphs:
        _fail(f"combined controlled-value glyph coverage is below five: {missing_glyphs}")

    matrix = _read_matrix(kit_dir / "README.md")
    actual_counts = {glyph: counts[glyph] for glyph in REQUIRED_GLYPHS}
    if matrix != actual_counts:
        _fail(f"README coverage matrix does not match expected values: {matrix} != {actual_counts}")
    return actual_counts


def _canonical_report_key(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.casefold())


def verify_capture_root(capture_root: Path) -> None:
    """Check file/metadata shape only; this cannot certify capture provenance."""
    for page_id in PAGE_FILES:
        page_dir = capture_root / page_id
        spl_path = page_dir / f"{page_id}.spl"
        png_path = page_dir / f"{page_id}.png"
        report_path = page_dir / "Report.txt"
        for path in (spl_path, png_path, report_path):
            if not path.is_file():
                _fail(f"capture artifact is missing: {path}")
        if spl_path.stat().st_size == 0:
            _fail(f"captured SPL is empty: {spl_path}")
        with png_path.open("rb") as png_file:
            if png_file.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                _fail(f"PNG signature is invalid: {png_path}")

        metadata: dict[str, str] = {}
        for line in report_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                key, separator, value = line.partition("=")
            if separator:
                metadata[_canonical_report_key(key.strip())] = value.strip()
        for key in ("printer", "spooljobid", "timestamp", "pagecount"):
            if not metadata.get(key):
                _fail(f"{report_path}: required metadata field is missing: {key}")

        timestamp = metadata["timestamp"]
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            _fail(f"{report_path}: timestamp is not ISO 8601: {exc}")
        if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
            _fail(f"{report_path}: timestamp must include a zone offset")
        if not metadata["pagecount"].isdigit() or int(metadata["pagecount"]) != 1:
            _fail(f"{report_path}: each source page must report page count 1")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture-root",
        type=Path,
        help="optional owner-provided KandooPrintProbe capture directory to shape-check",
    )
    args = parser.parse_args(argv)

    try:
        counts = verify_kit()
        print("E-03-kit-v2 pages, expected values, arithmetic, and README matrix: PASS")
        print("Glyph | Combined count | Result")
        for glyph in REQUIRED_GLYPHS:
            print(f"{glyph} | {counts[glyph]} | PASS (minimum {MIN_GLYPH_COUNT})")
        if args.capture_root is None:
            print("Capture file/metadata check: NOT RUN (no capture root supplied).")
        else:
            verify_capture_root(args.capture_root)
            print("Capture file/metadata shape: PASS (origin and conversion still require owner review).")
    except (OSError, ValueError) as exc:
        print(f"E-03-kit-v2 validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
