#!/usr/bin/env python3
"""Build deterministic, text-free ProductCandidate prototype records (N-02).

The numeric fields come only from the four label-derived Canonical Invoice v0
fixtures. Name-crop cluster IDs come from the existing local dHash sidecar. No
product-name text or category is read or copied into a candidate record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Iterable

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("Pillow is required to read the local receipt fixtures") from exc

from image_extraction_adapter.pipeline_v0 import cluster_description_crops
from image_extraction_adapter.preprocessing import crop_spatial_cells, detect_layout_safe
from run_name_cluster_experiment import (
    _geometry_for_invoice,
    _read_and_validate_inputs,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_IDS = ("29", "31", "32", "33")
CANONICAL_DIR = Path("tests/fixtures/real/canonical")
LABELS_REL_PATH = Path("tests/fixtures/real/labels.json")
REFERENCE_CROP_DIR = Path("tests/fixtures/real/n02-reference-crops")
SCHEMA_VERSION = "n02.product-candidates.v1"
PRICE_DATE_SOURCE = "probe.captured_at"
_CROP_ID_RE = re.compile(r"^(?P<invoice>\d+)_row(?P<row>\d+)$")
_CLUSTER_ID_RE = re.compile(r"^name-dhash-[0-9a-f]{16}$")


@dataclass(frozen=True)
class CandidateOccurrence:
    """One canonical line item joined to one local name-crop cluster."""

    name_crop_cluster_id: str
    source_crop_id: str
    reference_crop_file: str
    invoice_id: str
    quantity: int
    unit_price_rials: int
    observed_on: str | None


@dataclass(frozen=True)
class PriceObservation:
    """A unit price dated by an explicit Probe capture timestamp and source row."""

    observed_on: str
    unit_price_rials: int
    invoice_id: str
    source_crop_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_on": self.observed_on,
            "unit_price_rials": self.unit_price_rials,
            "invoice_id": self.invoice_id,
            "source_crop_id": self.source_crop_id,
        }


@dataclass(frozen=True)
class ProductCandidate:
    """One deterministic aggregate keyed by a name-crop cluster ID.

    This N-02 prototype record is not part of the existing durable product
    exact-match layer and is not a confirmed catalog identity.
    """

    name_crop_cluster_id: str
    reference_crop_file: str
    occurrence_count: int
    quantity_sum: int
    source_crop_ids: tuple[str, ...]
    price_observations: tuple[PriceObservation, ...]
    invoice_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name_crop_cluster_id": self.name_crop_cluster_id,
            "reference_crop_file": self.reference_crop_file,
            "occurrence_count": self.occurrence_count,
            "quantity_sum": self.quantity_sum,
            "source_crop_ids": list(self.source_crop_ids),
            "price_observations": [item.to_dict() for item in self.price_observations],
            "invoice_ids": list(self.invoice_ids),
        }


def _crop_sort_key(crop_id: str) -> tuple[int, int]:
    match = _CROP_ID_RE.fullmatch(crop_id)
    if match is None:
        raise ValueError(f"invalid source crop ID: {crop_id!r}")
    return int(match.group("invoice")), int(match.group("row"))


def _captured_at_date(value: Any, *, source: str) -> str | None:
    """Return the date in an explicit offset-aware Probe capture timestamp."""
    if value is None:
        return None
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{source} must be a non-empty ISO 8601 datetime")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{source} must be an ISO 8601 datetime with a UTC offset") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{source} must include an explicit UTC offset")
    return parsed.date().isoformat()


def _canonical_observation_date(value: Any, *, invoice_id: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"observation date for {invoice_id} must be a string or null")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"observation date for {invoice_id} is not an ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"observation date for {invoice_id} must use YYYY-MM-DD")
    return value


def aggregate_candidate_occurrences(
    occurrences: Iterable[CandidateOccurrence],
) -> list[ProductCandidate]:
    """Aggregate by the supplied stable crop-cluster ID; emit one row per ID.

    Re-running over the same contributions is deterministic. A contribution
    from a new invoice with an existing cluster ID increments that one record;
    it does not append a second candidate. Repeated source crop IDs are rejected
    to avoid accidental double ingestion of an invoice.
    """
    groups: dict[str, list[CandidateOccurrence]] = {}
    seen_crop_ids: set[str] = set()
    materialised = list(occurrences)
    if not materialised:
        return []

    for item in materialised:
        if not _CLUSTER_ID_RE.fullmatch(item.name_crop_cluster_id):
            raise ValueError(f"invalid name-crop cluster ID: {item.name_crop_cluster_id!r}")
        if not _CROP_ID_RE.fullmatch(item.source_crop_id):
            raise ValueError(f"invalid source crop ID: {item.source_crop_id!r}")
        if item.source_crop_id in seen_crop_ids:
            raise ValueError(f"duplicate source crop contribution: {item.source_crop_id}")
        seen_crop_ids.add(item.source_crop_id)
        if not item.invoice_id:
            raise ValueError("invoice_id must be non-empty")
        if type(item.quantity) is not int or item.quantity <= 0:
            raise ValueError(f"quantity for {item.source_crop_id} must be a positive integer")
        if type(item.unit_price_rials) is not int or item.unit_price_rials <= 0:
            raise ValueError(f"unit price for {item.source_crop_id} must be a positive integer")
        if item.observed_on is not None:
            _canonical_observation_date(item.observed_on, invoice_id=item.invoice_id)
        crop_path = PurePosixPath(item.reference_crop_file)
        if crop_path.is_absolute() or ".." in crop_path.parts:
            raise ValueError("reference_crop_file must be a safe repository-relative path")
        groups.setdefault(item.name_crop_cluster_id, []).append(item)

    output: list[ProductCandidate] = []
    for cluster_id in sorted(groups):
        members = sorted(groups[cluster_id], key=lambda item: _crop_sort_key(item.source_crop_id))
        price_observations = [
            PriceObservation(
                observed_on=item.observed_on,
                unit_price_rials=item.unit_price_rials,
                invoice_id=item.invoice_id,
                source_crop_id=item.source_crop_id,
            )
            for item in members
            if item.observed_on is not None
        ]
        price_observations.sort(key=lambda item: (
            item.observed_on, item.invoice_id, item.source_crop_id,
            item.unit_price_rials,
        ))
        output.append(ProductCandidate(
            name_crop_cluster_id=cluster_id,
            reference_crop_file=members[0].reference_crop_file,
            occurrence_count=len(members),
            quantity_sum=sum(item.quantity for item in members),
            source_crop_ids=tuple(item.source_crop_id for item in members),
            price_observations=tuple(price_observations),
            invoice_ids=tuple(sorted({item.invoice_id for item in members})),
        ))
    return output


def _read_canonical_fixtures(
    repo_root: Path,
    *,
    captured_at: str | None = None,
) -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}
    captured_at_override = _captured_at_date(
        captured_at,
        source="--captured-at",
    )
    manifest_path = repo_root / CANONICAL_DIR / "synthesis-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("synthesis_marker") != "synthesized_from_labels":
        raise ValueError("canonical fixture synthesis marker is missing or changed")
    manifest_entries = {
        str(item.get("source_id")): item for item in manifest.get("invoices", [])
    }
    if set(manifest_entries) != set(FIXTURE_IDS):
        raise ValueError("canonical synthesis manifest must list exactly the four N-02 fixtures")

    for fixture_id in FIXTURE_IDS:
        path = repo_root / CANONICAL_DIR / f"canonical-{fixture_id}.json"
        provenance = manifest_entries[fixture_id]
        if (not provenance.get("synthesized_from_labels")
                or provenance.get("canonical_file") != path.name):
            raise ValueError(f"canonical provenance mismatch for fixture {fixture_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        expected_invoice_id = f"e05-synth-invoice-{fixture_id}"
        if data.get("invoice_id") != expected_invoice_id:
            raise ValueError(f"unexpected invoice_id in {path}")
        items = data.get("line_items")
        if not isinstance(items, list) or not items:
            raise ValueError(f"line_items must be a non-empty array in {path}")
        header = data.get("header")
        if not isinstance(header, dict):
            raise ValueError(f"header must be an object in {path}")
        fixture_capture_date = _captured_at_date(
            header.get("captured_at"),
            source=f"header.captured_at for {expected_invoice_id}",
        )
        data["_n02_observed_on"] = (
            captured_at_override if captured_at is not None else fixture_capture_date
        )
        fixtures[fixture_id] = data
    return fixtures


def _load_crop_inputs(
    repo_root: Path,
    fixtures: dict[str, dict[str, Any]],
) -> tuple[list[tuple[str, Any]], dict[str, Any]]:
    labels_path = repo_root / LABELS_REL_PATH
    labels, labels_dir = _read_and_validate_inputs(labels_path)
    label_entries = {str(item["id"]): item for item in labels["invoices"]}
    if set(label_entries) != set(FIXTURE_IDS):
        raise ValueError("N-02 requires label geometry for fixtures 29, 31, 32, and 33")

    crop_inputs: list[tuple[str, Any]] = []
    crop_images: dict[str, Any] = {}
    for fixture_id in FIXTURE_IDS:
        entry = label_entries[fixture_id]
        image_path = labels_dir / entry["path"]
        geometry = _geometry_for_invoice(entry, image_path)
        image_sha256 = _sha256(image_path)
        canonical_sha256 = fixtures[fixture_id].get("provenance", {}).get("image_sha256")
        if canonical_sha256 != image_sha256:
            raise ValueError(f"canonical source-image hash mismatch for fixture {fixture_id}")

        with Image.open(image_path) as opened:
            opened.load()
            image = opened.convert("RGB")
        safety = detect_layout_safe(image)
        if safety.status != "OK" or safety.row_count != len(fixtures[fixture_id]["line_items"]):
            raise ValueError(f"unsafe or inconsistent description layout for fixture {fixture_id}")
        if len(geometry.label_row_bands) != len(fixtures[fixture_id]["line_items"]):
            raise ValueError(f"line-item/crop row count mismatch for fixture {fixture_id}")

        spatial = SimpleNamespace(
            column_boundaries=geometry.boundaries,
            row_bands=geometry.label_row_bands,
            assessments=(),
        )
        cells = crop_spatial_cells(
            image,
            spatial,
            include_descriptions=True,
            include_payable=False,
        )
        descriptions = [cell for cell in cells if cell.field_name.endswith(".description")]
        descriptions.sort(key=lambda cell: int(cell.field_name.split(".")[1]))
        if len(descriptions) != len(fixtures[fixture_id]["line_items"]):
            raise ValueError(f"expected one description crop per line item in fixture {fixture_id}")
        for row_index, cell in enumerate(descriptions):
            expected_field = f"line.{row_index}.description"
            if cell.field_name != expected_field:
                raise ValueError(f"unexpected crop order in fixture {fixture_id}: {cell.field_name}")
            crop_id = f"{fixture_id}_row{row_index}"
            if crop_id in crop_images:
                raise ValueError(f"duplicate crop ID: {crop_id}")
            crop_inputs.append((crop_id, cell))
            crop_images[crop_id] = cell.image

    if len(crop_inputs) != 25:
        raise ValueError(f"expected 25 product-name crops, got {len(crop_inputs)}")
    return crop_inputs, crop_images


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_candidate_occurrences(
    repo_root: Path = ROOT,
    *,
    captured_at: str | None = None,
) -> tuple[list[CandidateOccurrence], dict[str, Any]]:
    """Read fixtures and return per-line contributions plus crop images.

    An explicit CLI/API timestamp overrides fixture header metadata for this
    deterministic batch. Otherwise each fixture's own ``header.captured_at`` is
    used; ``printed_date`` is never read.
    """
    root = Path(repo_root).resolve()
    fixtures = _read_canonical_fixtures(root, captured_at=captured_at)
    crop_inputs, crop_images = _load_crop_inputs(root, fixtures)
    clusters = cluster_description_crops([cell for _, cell in crop_inputs])
    if len(clusters) != len(crop_inputs):
        raise RuntimeError("cluster output count does not match product-name crop count")

    cluster_for_crop = {
        crop_id: cluster.name_cluster_id
        for (crop_id, _), cluster in zip(crop_inputs, clusters)
    }
    if len(cluster_for_crop) != len(crop_inputs):
        raise RuntimeError("crop-to-cluster mapping is not one-to-one")

    occurrences: list[CandidateOccurrence] = []
    for fixture_id in FIXTURE_IDS:
        invoice = fixtures[fixture_id]
        invoice_id = invoice["invoice_id"]
        observed_on = invoice["_n02_observed_on"]
        items = invoice["line_items"]
        for row_index, line_item in enumerate(items):
            crop_id = f"{fixture_id}_row{row_index}"
            occurrences.append(CandidateOccurrence(
                name_crop_cluster_id=cluster_for_crop[crop_id],
                source_crop_id=crop_id,
                reference_crop_file=(REFERENCE_CROP_DIR / f"{crop_id}.png").as_posix(),
                invoice_id=invoice_id,
                quantity=line_item.get("quantity"),
                unit_price_rials=line_item.get("unit_price"),
                observed_on=observed_on,
            ))
    return occurrences, crop_images


def build_product_candidates(
    repo_root: Path = ROOT,
    *,
    captured_at: str | None = None,
    write_reference_crops: bool = True,
) -> dict[str, Any]:
    """Build N-02 records, using only explicit Probe capture timestamps for dates."""
    root = Path(repo_root).resolve()
    occurrences, crop_images = collect_candidate_occurrences(
        root,
        captured_at=captured_at,
    )
    candidate_records = aggregate_candidate_occurrences(occurrences)
    candidates = [candidate.to_dict() for candidate in candidate_records]
    selected_reference_ids = [candidate.source_crop_ids[0] for candidate in candidate_records]
    if write_reference_crops:
        crop_dir = root / REFERENCE_CROP_DIR
        crop_dir.mkdir(parents=True, exist_ok=True)
        for crop_id in selected_reference_ids:
            image = crop_images[crop_id]
            image.save(crop_dir / f"{crop_id}.png", format="PNG", optimize=False)
    else:
        missing = [
            str(root / REFERENCE_CROP_DIR / f"{crop_id}.png")
            for crop_id in selected_reference_ids
            if not (root / REFERENCE_CROP_DIR / f"{crop_id}.png").is_file()
        ]
        if missing:
            raise FileNotFoundError("missing reference crop files: " + ", ".join(missing))

    source_fixture_files = [
        (CANONICAL_DIR / f"canonical-{fixture_id}.json").as_posix()
        for fixture_id in FIXTURE_IDS
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_fixture_files": source_fixture_files,
        "price_observation_date_source": PRICE_DATE_SOURCE,
        "candidates": candidates,
    }


def serialize_document(document: dict[str, Any]) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument(
        "--captured-at",
        metavar="ISO",
        help=(
            "offset-aware ISO 8601 KandooPrintProbe captured_at value; "
            "explicitly overrides fixture header timestamps for this batch"
        ),
    )
    args = parser.parse_args(argv)

    document = build_product_candidates(
        args.repo_root.resolve(),
        captured_at=args.captured_at,
    )
    output_path = args.output_json.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialize_document(document), encoding="utf-8", newline="\n")
    print(json.dumps({
        "output_json": str(output_path),
        "candidate_count": len(document["candidates"]),
        "occurrence_count": sum(item["occurrence_count"] for item in document["candidates"]),
        "dated_price_observation_count": sum(
            len(item["price_observations"]) for item in document["candidates"]),
        "reference_crop_count": len(document["candidates"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
