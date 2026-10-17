#!/usr/bin/env python3
"""Inventory invoice PNGs, compare exact file hashes, and cross-check labels.

Uses only Pillow and Python's standard library. It does not invoke OCR,
Tesseract, an external service, or any image-recognition model.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = REPO_ROOT / "tests" / "fixtures" / "real" / "labels.json"
IMAGE_DIRS = (
    ("tests/fixtures/real", REPO_ROOT / "tests" / "fixtures" / "real"),
    ("deliveries/image-extraction-ocr", REPO_ROOT / "deliveries" / "image-extraction-ocr"),
    ("deliveries/issue-4-smoke-suite", REPO_ROOT / "deliveries" / "issue-4-smoke-suite"),
)
TEHRAN = ZoneInfo("Asia/Tehran")


@dataclass(frozen=True)
class ImageRecord:
    directory: str
    path: Path
    filename: str
    size_bytes: int
    md5: str
    dimensions: tuple[int, int] | None
    mtime_utc: str
    mtime_tehran: str
    error: str | None = None

    @property
    def relative_path(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_record(directory: str, path: Path) -> ImageRecord:
    stat = path.stat()
    mtime_utc = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    mtime_tehran = mtime_utc.astimezone(TEHRAN)
    dimensions = None
    error = None
    try:
        with Image.open(path) as image:
            image.load()
            dimensions = image.size
    except Exception as exc:  # report unreadable files without losing hash/stat data
        error = f"{type(exc).__name__}: {exc}"
    return ImageRecord(
        directory=directory,
        path=path,
        filename=path.name,
        size_bytes=stat.st_size,
        md5=md5_file(path),
        dimensions=dimensions,
        mtime_utc=mtime_utc.isoformat(timespec="microseconds"),
        mtime_tehran=mtime_tehran.isoformat(timespec="microseconds"),
        error=error,
    )


def load_labels() -> tuple[list[dict[str, Any]], str, list[str]]:
    if not LABELS_PATH.is_file():
        return [], "unavailable", [f"labels file missing: {LABELS_PATH.relative_to(REPO_ROOT)}"]
    try:
        data = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], "unavailable", [f"cannot read labels JSON: {exc}"]
    entries = data.get("invoices", data.get("images"))
    if not isinstance(entries, list):
        return [], "unavailable", ["labels JSON must contain an 'invoices' or 'images' list"]
    return entries, str(data.get("label_status", "unspecified")), []


def label_index(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        relative = Path(str(entry.get("path", ""))).as_posix()
        if relative:
            result[relative] = entry
    return result


def printable_dimensions(dimensions: tuple[int, int] | None) -> str:
    return f"{dimensions[0]}x{dimensions[1]}" if dimensions else "ERROR"


def main() -> int:
    records: list[ImageRecord] = []
    directory_counts: list[tuple[str, str, int]] = []
    for label, directory in IMAGE_DIRS:
        if not directory.is_dir():
            directory_counts.append((label, "MISSING", 0))
            continue
        files = sorted(
            (path for path in directory.rglob("*")
             if path.is_file() and path.suffix.lower() == ".png"),
            key=lambda path: path.as_posix().casefold(),
        )
        directory_counts.append((label, "present", len(files)))
        records.extend(image_record(label, path) for path in files)

    entries, label_status, label_errors = load_labels()
    labels_by_path = label_index(entries)
    records_by_path = {record.relative_path: record for record in records}

    print("Image integrity inventory (PNG bytes; no OCR)")
    print(f"Repository root: {REPO_ROOT}")
    print(f"Labels: {LABELS_PATH.relative_to(REPO_ROOT)}")
    print("Directories scanned:")
    for label, status, count in directory_counts:
        print(f"  {label}: {status}; PNG files={count}")

    print("\nFile inventory")
    print("directory | filename | bytes | MD5 | dimensions | mtime (Tehran) | mtime (UTC)")
    for record in records:
        print(
            f"{record.directory} | {record.filename} | {record.size_bytes} | "
            f"{record.md5} | {printable_dimensions(record.dimensions)} | "
            f"{record.mtime_tehran} | {record.mtime_utc}"
        )
        if record.error:
            print(f"  IMAGE_ERROR: {record.error}")

    groups: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        groups[record.md5].append(record)
    print("\nGroups by exact MD5 (same bytes => same file content)")
    for digest, group in sorted(groups.items()):
        dimensions = sorted({record.dimensions for record in group if record.dimensions})
        dimension_text = ", ".join(printable_dimensions(item) for item in dimensions) or "ERROR"
        print(f"  MD5 {digest}; dimensions={dimension_text}")
        for record in group:
            print(f"    ({record.directory}, {record.filename})")

    fixture_records = [
        record for record in records if record.directory == "tests/fixtures/real"
    ]
    fixture_ids_by_hash: dict[str, set[str]] = defaultdict(set)
    fixture_path_by_hash: dict[str, list[str]] = defaultdict(list)
    consistency_issues: list[str] = list(label_errors)
    for record in fixture_records:
        label_relative_path = record.path.relative_to(LABELS_PATH.parent).as_posix()
        entry = labels_by_path.get(label_relative_path)
        if entry is None:
            consistency_issues.append(f"extra fixture PNG has no labels entry: {record.filename}")
            continue
        invoice_id = str(entry.get("id", ""))
        fixture_ids_by_hash[record.md5].add(invoice_id)
        fixture_path_by_hash[record.md5].append(record.filename)

    print("\nLabels cross-reference")
    print(f"  label status: {label_status}")
    labelled_paths: set[str] = set()
    for entry in entries:
        relative = Path(str(entry.get("path", ""))).as_posix()
        invoice_id = str(entry.get("id", ""))
        if not relative:
            consistency_issues.append(f"label entry has no path (invoice id={invoice_id!r})")
            continue
        labelled_paths.add(relative)
        full_path = (LABELS_PATH.parent / relative).resolve()
        fixture_relative_path = (Path("tests/fixtures/real") / relative).as_posix()
        record = records_by_path.get(fixture_relative_path)
        exists = full_path.is_file()
        if not exists:
            consistency_issues.append(f"labels reference missing fixture: {relative} (invoice {invoice_id})")
        if record is None:
            actual_dimensions = "not inventoried"
        else:
            actual_dimensions = printable_dimensions(record.dimensions)
        declared_dimensions = entry.get("image_dimensions")
        dimensions_match = (
            isinstance(declared_dimensions, list) and record is not None
            and tuple(declared_dimensions) == record.dimensions
        )
        stem = Path(relative).stem
        filename_match = stem == invoice_id
        status = "OK" if exists and dimensions_match and filename_match else "CHECK"
        print(
            f"  invoice {invoice_id}: {relative}; exists={'YES' if exists else 'NO'}; "
            f"filename-id={'MATCH' if filename_match else 'MISMATCH'}; "
            f"dimensions declared={declared_dimensions}, actual={actual_dimensions}; "
            f"dimensions={'MATCH' if dimensions_match else 'MISMATCH'}; {status}"
        )
    for record in fixture_records:
        label_relative_path = record.path.relative_to(LABELS_PATH.parent).as_posix()
        if label_relative_path not in labelled_paths:
            consistency_issues.append(f"fixture PNG not referenced by labels: {label_relative_path}")

    print("\nDelivery filename/content cross-reference")
    for record in records:
        if record.directory == "tests/fixtures/real":
            continue
        inferred = sorted(fixture_ids_by_hash.get(record.md5, set()) - {""})
        if inferred:
            numeric_stem = record.path.stem if record.path.stem.isdigit() else None
            stem_match = numeric_stem in inferred if numeric_stem is not None else None
            stem_status = (
                "MATCH" if stem_match is True else
                "MISMATCH" if stem_match is False else
                "non-numeric filename"
            )
            print(
                f"  {record.relative_path}: exact fixture content for invoice(s) "
                f"{','.join(inferred)}; filename-id={stem_status}"
            )
        else:
            print(f"  {record.relative_path}: no exact fixture-content match; invoice id unknown without OCR")

    by_relative_path = {record.relative_path: record for record in records}

    def same_content(left: str, right: str) -> str:
        a = by_relative_path.get(left)
        b = by_relative_path.get(right)
        if a is None or b is None:
            return "UNAVAILABLE (one or both files are missing)"
        return "YES" if a.md5 == b.md5 else "NO"

    print("\nCritical filename/hash checks")
    fixture_32 = "tests/fixtures/real/32.png"
    delivery_5 = "deliveries/image-extraction-ocr/5.png"
    fixture_33 = "tests/fixtures/real/33.png"
    delivery_13 = "deliveries/image-extraction-ocr/13.png"
    print(f"  {fixture_32} exists: {'YES' if (REPO_ROOT / fixture_32).is_file() else 'NO'}")
    print(f"  {fixture_32} == {delivery_5}: {same_content(fixture_32, delivery_5)}")
    print(f"  {fixture_32} MD5: {by_relative_path[fixture_32].md5 if fixture_32 in by_relative_path else 'MISSING'}")
    print(f"  {delivery_5} MD5: {by_relative_path[delivery_5].md5 if delivery_5 in by_relative_path else 'MISSING'}")
    print(f"  {delivery_5} == {fixture_33}: {same_content(delivery_5, fixture_33)}")
    matches_13 = fixture_path_by_hash.get(by_relative_path[delivery_13].md5, []) if delivery_13 in by_relative_path else []
    print(
        f"  {delivery_13} == any fixture: "
        f"{'YES (' + ', '.join(matches_13) + ')' if matches_13 else 'NO'}"
    )

    print("\nLabels consistency summary")
    if consistency_issues:
        for issue in consistency_issues:
            print(f"  ISSUE: {issue}")
    else:
        print(f"  PASS: all {len(entries)} label paths exist, filename IDs and declared dimensions match, and all {len(fixture_records)} fixture PNGs are labeled")
    print("  Note: a hash match proves byte identity, not provenance or original upload time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
