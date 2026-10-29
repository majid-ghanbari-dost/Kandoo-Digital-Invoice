"""Local, fail-closed E-02 image pipeline for Canonical Invoice v0.

This module is deliberately separate from the legacy flat-text adapter. It uses
layout geometry, Glyph numeric cells, the existing arithmetic gate, and the
existing offline dHash helpers. It never calls a network service, Tesseract, the
flat-text parser, or an issuance API. Source images are read locally and only a
SHA-256 is retained in output metadata.

Canonical Invoice v0 requires producer-owned identity/customer fields and
human-meaningful product names that are not present in numeric OCR or dHash
clusters. Those values are never synthesized here: supply an explicit
``canonical_context`` to assemble a schema-validated EXTRACTED candidate, or
receive a numeric extraction result with canonical blockers.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from .canonical_invoice import validate_canonical_invoice
from .drift_monitor import (
    DRIFT_REASON,
    aggregate_mean_distance_by_symbol,
    evaluate_glyph_drift,
    load_glyph_drift_baseline,
)
from .glyph_classifier import (
    GlyphClassifierOCR,
    GlyphTemplateSet,
    LabeledCell,
    apply_arithmetic_gate,
    build_templates,
    normalize_label_text,
    parse_amount_text,
)
from .model import CellOCRVariantResult
from .preprocessing import (
    LayoutSafetyResult,
    crop_spatial_cells,
    detect_layout_safe,
    otsu_binarize,
)


ENGINE_VERSION = "pipeline-v0/0.1.0"
DEFAULT_MINIMUM_CONFIDENCE = 60.0
DEFAULT_DHASH_THRESHOLD = 1
SUPPORTED_FIXTURE_IDS = ("29", "31", "32", "33")

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LABELS_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "real" / "labels.json"
DEFAULT_TEMPLATE_BANK_PATH = REPOSITORY_ROOT / "src" / "templates_bank_default.json"
DEFAULT_GLYPH_DRIFT_BASELINE_PATH = REPOSITORY_ROOT / "src" / "glyph_drift_baseline_v1.json"
LEGACY_TEMPLATE_BANK_PATH = REPOSITORY_ROOT / "src" / "templates.json"

# Payable-region search is relative to detected table geometry. These are
# conservative geometric bounds, not Glyph-classifier/confidence thresholds.
_PAYABLE_Y_START_ROW_RATIO = 0.18
_PAYABLE_Y_END_ROW_RATIO = 0.80
_PAYABLE_RIGHT_EXTRA_QUANTITY_WIDTHS = 2.0
_PAYABLE_COMPONENT_GAP_ROW_RATIO = 0.12
_PAYABLE_MIN_COMPONENTS = 4
_PAYABLE_MIN_WIDTH_SEPARATION = 1.5

_RIAL_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_QUANTITY_FIELD = re.compile(r"^line\.(\d+)\.quantity$")
_TOTAL_FIELD = re.compile(r"^line\.(\d+)\.total$")
_CORRECTABLE_FIELD = re.compile(
    r"^(?:line\.\d+\.(?:quantity|total)|invoice\.payable)$")
_LEGACY_DERIVED_CROP = re.compile(
    r"^glyph-classifier-build-(?P<parent>.+?)-rows\d+-\d+\.png$")


class TemplateLeakageError(RuntimeError):
    """Raised when an evaluation image appears in template provenance."""


class TemplateProvenanceError(RuntimeError):
    """Raised when evaluation cannot establish template-source provenance."""


class TemplateBankBuildError(RuntimeError):
    """Raised when a template bank cannot be safely built from local labels."""


@dataclass(frozen=True)
class AttentionCell:
    field: str
    raw_value: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "raw_value": self.raw_value, "reason": self.reason}


@dataclass(frozen=True)
class DescriptionCluster:
    field_name: str
    crop_id: str
    bbox: tuple[int, int, int, int]
    dhash: str
    name_cluster_id: str
    cluster_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "crop_id": self.crop_id,
            "bbox": list(self.bbox),
            "dhash": self.dhash,
            "name_cluster_id": self.name_cluster_id,
            "cluster_size": self.cluster_size,
        }


@dataclass(frozen=True)
class PipelineResult:
    """Adapter-local routing result; ``status`` is not an invoice lifecycle state."""

    status: Literal["AUTO_CANDIDATE", "REVIEW", "REJECT"]
    reason: str
    image_sha256: str | None
    layout_status: str
    layout_reason: str
    row_count: int | None
    cell_results: tuple[CellOCRVariantResult, ...]
    arithmetic_gate: Any | None
    attention_cells: tuple[AttentionCell, ...]
    description_clusters: tuple[DescriptionCluster, ...]
    template_library_id: str | None
    template_sources: tuple[Mapping[str, Any], ...]
    template_bank_path: str | None
    canonical_invoice: Mapping[str, Any] | None
    canonical_valid: bool | None
    canonical_errors: tuple[str, ...]
    canonical_blockers: tuple[str, ...]
    operator_confirmed_fields: tuple[str, ...] = ()
    operator_confirmed_values: tuple[tuple[str, str], ...] = ()
    operator_original_values: tuple[tuple[str, str], ...] = ()
    template_bank_updated: bool = False
    bank_update_eligible: bool = False
    captured_at: str | None = None
    glyph_drift: Mapping[str, Any] | None = None
    canonical_context: Mapping[str, Any] | None = field(default=None, repr=False, compare=False)
    _non_numeric_attention: tuple[AttentionCell, ...] = field(
        default=(), repr=False, compare=False)
    _description_failures: tuple[str, ...] = field(
        default=(), repr=False, compare=False)

    def to_dict(self, *, include_glyph_drift: bool = False) -> dict[str, Any]:
        gate = asdict(self.arithmetic_gate) if self.arithmetic_gate is not None else None
        document = {
            "pipeline_status": self.status,
            "reason": self.reason,
            "image_sha256": self.image_sha256,
            "layout": {
                "status": self.layout_status,
                "reason": self.layout_reason,
                "row_count": self.row_count,
            },
            "numeric_cells": [asdict(cell) for cell in self.cell_results],
            "arithmetic_gate": gate,
            "attention_cells": [cell.to_dict() for cell in self.attention_cells],
            "description_clusters": [cell.to_dict() for cell in self.description_clusters],
            "template_provenance": {
                "template_library_id": self.template_library_id,
                "template_bank_path": self.template_bank_path,
                "source_images": [dict(source) for source in self.template_sources],
            },
            "canonical_invoice": (
                copy.deepcopy(dict(self.canonical_invoice))
                if self.canonical_invoice is not None else None
            ),
            "canonical_validation": {
                "valid": self.canonical_valid,
                "errors": list(self.canonical_errors),
                "blockers": list(self.canonical_blockers),
            },
            "operator_confirmed_fields": list(self.operator_confirmed_fields),
            "operator_confirmed_values": [
                {"field": name, "value": value}
                for name, value in self.operator_confirmed_values
            ],
            "operator_original_values": [
                {"field": name, "value": value}
                for name, value in self.operator_original_values
            ],
            "template_bank_updated": self.template_bank_updated,
            "bank_update_eligible": self.bank_update_eligible,
        }
        if include_glyph_drift and self.glyph_drift is not None:
            document["glyph_drift"] = copy.deepcopy(dict(self.glyph_drift))
        return document

    def to_json(self, *, indent: int = 2, include_glyph_drift: bool = False) -> str:
        return json.dumps(
            self.to_dict(include_glyph_drift=include_glyph_drift),
            ensure_ascii=False,
            indent=indent,
        ) + "\n"


@dataclass(frozen=True)
class TemplateBankBuildReport:
    output_path: str
    bank_sha256: str
    source_images: tuple[Mapping[str, Any], ...]
    template_counts: Mapping[str, Mapping[str, int]]
    training_cell_count: int
    used_cell_count: int
    skipped_cells: tuple[str, ...]


@dataclass(frozen=True)
class LeaveOneOutFoldOutcome:
    invoice_id: str
    status: str
    numeric_cells: int
    extracted_cells: int
    review_cells: int
    blocked_cells: int
    arithmetic_gate_passed: bool
    arithmetic_gate_reason: str | None
    extracted_but_wrong: int
    independent_extracted_label_comparisons: int
    excluded_ground_truth_fields: tuple[str, ...]
    canonical_invoice_created: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_rials(value: str | None) -> int | None:
    """Strict local equivalent of the frozen adapter's integer-Rial converter.

    This intentionally does not import ``adapter.py`` (which also imports the
    legacy parser). It accepts Persian digits and grouping commas only; decimal
    fractions, Arabic-Indic digits that were not normalized, signs, and other
    characters return ``None`` rather than being rounded or guessed.
    """
    if not isinstance(value, str) or not value:
        return None
    normalized = value.translate(_RIAL_DIGIT_TRANSLATION).replace(",", "")
    if not normalized or not normalized.isascii() or not normalized.isdigit():
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _template_set_sha256(templates: GlyphTemplateSet) -> str:
    payload = json.dumps(
        templates.to_json_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalise_path(path: Path) -> str:
    return str(Path(path).resolve()).casefold()


def _source_path_candidates(
    source_name: str,
    *,
    bank_path: Path | None,
    repo_root: Path,
) -> tuple[Path, ...]:
    source = Path(source_name)
    if source.is_absolute():
        return (source.resolve(),)
    candidates: list[Path] = []
    if bank_path is not None:
        candidates.append((bank_path.parent / source).resolve())
    candidates.append((repo_root / source).resolve())
    # Keep order while removing duplicate paths.
    unique: dict[str, Path] = {}
    for candidate in candidates:
        unique.setdefault(_normalise_path(candidate), candidate)
    return tuple(unique.values())


def _known_derived_parent_paths(source_path: Path) -> tuple[Path, ...]:
    """Resolve the recorded legacy rows-crop naming pattern to its full source.

    The legacy template bank contains ``glyph-classifier-build-13-rows03-08.png``.
    Its sibling ``13.png`` is the full receipt source. Treating this as a parent
    source is deliberately conservative: using any derived crop counts as using
    its original image during evaluation.
    """
    match = _LEGACY_DERIVED_CROP.fullmatch(source_path.name)
    if match is None:
        return ()
    parent = source_path.with_name(f"{match.group('parent')}.png").resolve()
    return (parent,) if parent.is_file() else ()


def _source_records_from_bank(data: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    provenance = data.get("provenance")
    if isinstance(provenance, list):
        records.extend(item for item in provenance if isinstance(item, Mapping))
    metadata = data.get("bank_metadata")
    if isinstance(metadata, Mapping):
        for key in ("source_images", "sources"):
            items = metadata.get(key)
            if isinstance(items, list):
                records.extend(item for item in items if isinstance(item, Mapping))
    unique: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in records:
        source_name = str(item.get("image") or item.get("path") or "")
        source_hash = str(item.get("sha256") or "")
        if not source_name and not source_hash:
            continue
        unique.setdefault((source_name, source_hash), dict(item))
    return tuple(unique.values())


def assert_no_template_leakage(
    image_path: Path | str,
    template_sources: Sequence[Mapping[str, Any]],
    *,
    bank_path: Path | str | None = None,
    repo_root: Path | str = REPOSITORY_ROOT,
) -> None:
    """Refuse an evaluation image matching any bank source path or SHA-256.

    A derived crop's recognized sibling source is also treated as provenance.
    Evaluation fails closed when source metadata is absent or unusable.
    """
    target = Path(image_path).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"evaluation image is missing: {target}")
    target_hash = _sha256_file(target)
    if not template_sources:
        raise TemplateProvenanceError(
            "evaluation requires template provenance; no source images were recorded")
    bank = Path(bank_path).resolve() if bank_path is not None else None
    root = Path(repo_root).resolve()
    checked = 0
    for record in template_sources:
        if not isinstance(record, Mapping):
            continue
        source_name = str(record.get("image") or record.get("path") or "")
        source_hash = str(record.get("sha256") or "").lower()
        if not source_name and not source_hash:
            continue
        checked += 1
        if source_hash and source_hash == target_hash:
            raise TemplateLeakageError(
                f"evaluation refused: image SHA-256 {target_hash} appears in template provenance")
        if source_name:
            for source_path in _source_path_candidates(
                source_name, bank_path=bank, repo_root=root):
                if _normalise_path(source_path) == _normalise_path(target):
                    raise TemplateLeakageError(
                        f"evaluation refused: source path {source_path} appears in template provenance")
                for parent_path in _known_derived_parent_paths(source_path):
                    if (_normalise_path(parent_path) == _normalise_path(target)
                            or _sha256_file(parent_path) == target_hash):
                        raise TemplateLeakageError(
                            "evaluation refused: image is the source of a derived template crop "
                            f"({source_path.name})")
    if checked == 0:
        raise TemplateProvenanceError(
            "evaluation requires at least one usable template source path or SHA-256")


def _open_rgb_image(image_path: Path) -> Any:
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("Pillow is required for the local image pipeline") from exc
    with Image.open(image_path) as opened:
        opened.load()
        return opened.convert("RGB")


def _component_boxes(binary_image: Any) -> list[tuple[int, int, int, int, int]]:
    """Return connected-component boxes as (left, top, right, bottom, pixels)."""
    gray = binary_image.convert("L")
    width, height = gray.size
    pixels = gray.tobytes()
    seen = bytearray(width * height)
    components: list[tuple[int, int, int, int, int]] = []
    for offset, value in enumerate(pixels):
        if value >= 128 or seen[offset]:
            continue
        seen[offset] = 1
        stack = [offset]
        x0 = x1 = offset % width
        y0 = y1 = offset // width
        count = 0
        while stack:
            current = stack.pop()
            x = current % width
            y = current // width
            count += 1
            x0 = min(x0, x)
            x1 = max(x1, x)
            y0 = min(y0, y)
            y1 = max(y1, y)
            for dy in (-1, 0, 1):
                next_y = y + dy
                if not 0 <= next_y < height:
                    continue
                row_offset = next_y * width
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    next_x = x + dx
                    if not 0 <= next_x < width:
                        continue
                    next_offset = row_offset + next_x
                    if pixels[next_offset] < 128 and not seen[next_offset]:
                        seen[next_offset] = 1
                        stack.append(next_offset)
        if count >= 4:
            components.append((x0, y0, x1 + 1, y1 + 1, count))
    return components


def detect_payable_bbox(image: Any, geometry: Any) -> tuple[int, int, int, int] | None:
    """Find one isolated payable text cluster below the detected table.

    The search rectangle is expressed from column boundaries and the median row
    height. It excludes the short horizontal divider immediately below the last
    table row, groups adjacent connected components, and accepts only a clearly
    widest text cluster. If the geometry or cluster is ambiguous, return ``None``
    so the arithmetic gate holds the invoice for review.
    """
    try:
        width, height = image.size
        boundaries = tuple(float(value) for value in geometry.column_boundaries)
        row_bands = tuple(geometry.row_bands)
        median_row_height = float(geometry.median_row_height)
        if (len(boundaries) != 5 or not row_bands
                or not math.isfinite(median_row_height) or median_row_height <= 0):
            return None
        c0, c1, c2 = boundaries[:3]
        table_bottom = math.floor(float(row_bands[-1][1]))
        x0 = max(0, math.floor(c0))
        x1 = min(
            width,
            math.ceil(c2 + _PAYABLE_RIGHT_EXTRA_QUANTITY_WIDTHS * (c2 - c1)),
        )
        y0 = max(
            0,
            table_bottom + math.ceil(_PAYABLE_Y_START_ROW_RATIO * median_row_height),
        )
        y1 = min(
            height,
            table_bottom + math.ceil(_PAYABLE_Y_END_ROW_RATIO * median_row_height),
        )
        if x1 <= x0 or y1 <= y0:
            return None
        binary = otsu_binarize(image.crop((x0, y0, x1, y1)))
        components = _component_boxes(binary)
        if not components:
            return None
        horizontal_gap = max(
            2, round(_PAYABLE_COMPONENT_GAP_ROW_RATIO * median_row_height))
        groups: list[list[tuple[int, int, int, int, int]]] = []
        for component in sorted(components, key=lambda item: (item[0], item[1])):
            if (not groups
                    or component[0] - max(item[2] for item in groups[-1]) > horizontal_gap):
                groups.append([component])
            else:
                groups[-1].append(component)
        candidates: list[tuple[int, int, tuple[int, int, int, int]]] = []
        for group in groups:
            if len(group) < _PAYABLE_MIN_COMPONENTS:
                continue
            left = min(item[0] for item in group)
            top = min(item[1] for item in group)
            right = max(item[2] for item in group)
            bottom = max(item[3] for item in group)
            candidates.append((
                right - left,
                len(group),
                (left + x0, top + y0, right + x0, bottom + y0),
            ))
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if not candidates:
            return None
        if (len(candidates) > 1
                and candidates[0][0] < _PAYABLE_MIN_WIDTH_SEPARATION * candidates[1][0]):
            return None
        left, top, right, bottom = candidates[0][2]
        # A text cluster touching the search boundary may have been clipped.
        if left <= x0 or right >= x1 or top <= y0 or bottom >= y1:
            return None
        if right <= left or bottom <= top:
            return None
        return left, top, right - left, bottom - top
    except (AttributeError, IndexError, TypeError, ValueError, OverflowError, RuntimeError):
        return None


def _spatial_for_geometry(geometry: Any, payable_bbox: tuple[int, int, int, int] | None) -> Any:
    assessments: tuple[Any, ...] = ()
    if payable_bbox is not None:
        assessments = (SimpleNamespace(
            field_name="invoice.payable", bbox=payable_bbox, status=None),)
    return SimpleNamespace(
        column_boundaries=tuple(geometry.column_boundaries),
        row_bands=tuple(tuple(band) for band in geometry.row_bands),
        assessments=assessments,
    )


def _dhash_helpers():
    """Load the already-tested T3 helpers without importing them at module load."""
    try:
        from run_name_cluster_experiment import _dhash, _hamming, _normalize_crop
    except Exception as exc:  # pragma: no cover - source-path misconfiguration
        raise RuntimeError(
            "existing dHash helpers are unavailable; add repository src/ to PYTHONPATH") from exc
    return _dhash, _hamming, _normalize_crop


def cluster_description_crops(crops: Iterable[Any]) -> tuple[DescriptionCluster, ...]:
    """Assign stable per-crop dHash cluster IDs using the prior threshold of 1.

    The output is adapter-local sidecar evidence, not a product-name transcript
    and not a Canonical Invoice v0 extension. Crops should come from
    ``crop_spatial_cells(..., include_descriptions=True)``.
    """
    materialised = tuple(crops)
    if not materialised:
        return ()
    dhash, hamming, normalize_crop = _dhash_helpers()
    records: list[dict[str, Any]] = []
    for crop in materialised:
        normalized, _ = normalize_crop(crop.image)
        value = dhash(normalized)
        row_match = re.search(r"^line\.(\d+)\.description$", crop.field_name)
        row_index = int(row_match.group(1)) if row_match else len(records)
        records.append({
            "field_name": crop.field_name,
            "crop_id": f"row{row_index}",
            "bbox": tuple(int(value) for value in crop.bbox),
            "hash": value,
        })
    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            if hamming(records[left]["hash"], records[right]["hash"]) <= DEFAULT_DHASH_THRESHOLD:
                union(left, right)
    groups: dict[int, list[int]] = {}
    for index in range(len(records)):
        groups.setdefault(find(index), []).append(index)
    output: list[DescriptionCluster | None] = [None] * len(records)
    for members in groups.values():
        representative = min(records[index]["hash"] for index in members)
        cluster_id = f"name-dhash-{representative:016x}"
        for index in members:
            item = records[index]
            output[index] = DescriptionCluster(
                field_name=item["field_name"],
                crop_id=item["crop_id"],
                bbox=item["bbox"],
                dhash=f"{item['hash']:016x}",
                name_cluster_id=cluster_id,
                cluster_size=len(members),
            )
    return tuple(item for item in output if item is not None)


def _numeric_attention(
    cells: Sequence[CellOCRVariantResult],
) -> tuple[AttentionCell, ...]:
    output: list[AttentionCell] = []
    seen: set[tuple[str, str, str]] = set()
    for cell in cells:
        if cell.status == "EXTRACTED" and "?" not in cell.raw_value:
            continue
        reason = cell.reason or "numeric cell requires operator attention"
        item = AttentionCell(cell.field_name, cell.raw_value, reason)
        key = (item.field, item.raw_value, item.reason)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return tuple(output)


def _pipeline_status(
    *,
    layout_status: str,
    cells: Sequence[CellOCRVariantResult],
    gate: Any | None,
    non_numeric_attention: Sequence[AttentionCell],
    description_failures: Sequence[str],
) -> Literal["AUTO_CANDIDATE", "REVIEW", "REJECT"]:
    if layout_status == "BLOCKED":
        return "REJECT"
    if layout_status != "OK":
        return "REVIEW"
    if any(cell.status == "BLOCKED" for cell in cells):
        return "REJECT"
    if (gate is None or not gate.passed
            or any(cell.status != "EXTRACTED" or "?" in cell.raw_value for cell in cells)
            or non_numeric_attention or description_failures):
        return "REVIEW"
    return "AUTO_CANDIDATE"


def _cell_integer_value(cell: CellOCRVariantResult) -> int | None:
    normalized = normalize_label_text(cell.raw_value)
    if _QUANTITY_FIELD.fullmatch(cell.field_name):
        if not normalized or not all("۰" <= char <= "۹" for char in normalized):
            return None
        value = to_rials(normalized)
        return value if value is not None and value > 0 else None
    if _TOTAL_FIELD.fullmatch(cell.field_name) or cell.field_name == "invoice.payable":
        parsed = parse_amount_text(normalized)
        converted = to_rials(normalized)
        return converted if parsed is not None and converted == parsed else None
    return None


def _context_blockers(context: Mapping[str, Any], row_count: int) -> list[str]:
    blockers: list[str] = []
    required_strings = (
        "invoice_id", "display_number", "operation_id", "device_id", "public_token", "store_id")
    mode = context.get("mode")
    if not isinstance(mode, str) or mode not in {"A", "B"}:
        blockers.append("canonical_context.mode must be explicitly supplied as 'A' or 'B'")
    for name in required_strings:
        value = context.get(name)
        if not isinstance(value, str) or not value.strip():
            blockers.append(f"canonical_context.{name} must be supplied by the producer")
    customer = context.get("customer")
    if not isinstance(customer, Mapping):
        blockers.append("canonical_context.customer must be supplied by the producer")
    else:
        phone = customer.get("phone")
        if not isinstance(phone, str) or not phone.strip():
            blockers.append("canonical_context.customer.phone must be supplied; it is not read from the image")
        phone_status = customer.get("phone_status")
        if not isinstance(phone_status, str) or phone_status not in {"claimed", "verified"}:
            blockers.append("canonical_context.customer.phone_status must be 'claimed' or 'verified'")
        phone_provenance = customer.get("phone_provenance")
        if (not isinstance(phone_provenance, str)
                or phone_provenance not in {"native", "captured"}):
            blockers.append("canonical_context.customer.phone_provenance must be 'native' or 'captured'")
    names = context.get("product_names")
    if not isinstance(names, Sequence) or isinstance(names, (str, bytes)):
        blockers.append("canonical_context.product_names must contain one supplied name per detected row")
    elif len(names) != row_count or any(not isinstance(name, str) or not name.strip() for name in names):
        blockers.append("canonical_context.product_names must contain one non-empty supplied name per detected row")
    name_labels = context.get("product_name_provenance")
    allowed_name_labels = {"native", "captured", "derived", "untrusted"}
    if (not isinstance(name_labels, Sequence) or isinstance(name_labels, (str, bytes))
            or len(name_labels) != row_count
            or any(not isinstance(label, str) or label not in allowed_name_labels
                   for label in name_labels)):
        blockers.append(
            "canonical_context.product_name_provenance must provide one allowed v0 provenance label per row")
    return blockers


def _build_canonical_invoice(
    *,
    context: Mapping[str, Any],
    cells: Sequence[CellOCRVariantResult],
    row_count: int,
    attention_cells: Sequence[AttentionCell],
    image_sha256: str | None,
    template_library_id: str | None,
    captured_at: str | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    blockers = _context_blockers(context, row_count)
    by_field = {cell.field_name: cell for cell in cells}
    line_values: list[tuple[int, int, int, str, str]] = []
    for row in range(row_count):
        quantity_cell = by_field.get(f"line.{row}.quantity")
        total_cell = by_field.get(f"line.{row}.total")
        if quantity_cell is None or total_cell is None:
            blockers.append(f"line {row}: numeric quantity and total cells are required")
            continue
        quantity = _cell_integer_value(quantity_cell)
        total = _cell_integer_value(total_cell)
        if quantity is None:
            blockers.append(f"line.{row}.quantity is not a valid positive integer")
        if total is None:
            blockers.append(f"line.{row}.total is not a valid integer-Rial amount")
        if quantity is None or total is None:
            continue
        unit_price, remainder = divmod(total, quantity)
        if remainder:
            blockers.append(
                f"line.{row}.unit_price cannot be derived exactly in integer rials; no rounding is permitted")
            continue
        line_values.append((quantity, total, unit_price, quantity_cell.status, total_cell.status))
    payable_cell = by_field.get("invoice.payable")
    payable = _cell_integer_value(payable_cell) if payable_cell is not None else None
    if payable is None:
        blockers.append("invoice.payable is unavailable or not a valid integer-Rial amount")
    if blockers:
        return None, blockers
    if len(line_values) != row_count:
        return None, ["canonical line-item count does not match detected rows"]

    customer = context["customer"]
    product_names = list(context["product_names"])
    product_name_labels = list(context["product_name_provenance"])
    line_items: list[dict[str, Any]] = []
    line_labels: list[dict[str, str]] = []
    for index, (quantity, total, unit_price, quantity_status, total_status) in enumerate(line_values):
        line_items.append({
            "product_name": product_names[index],
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": total,
        })
        line_labels.append({
            "product_name": product_name_labels[index],
            "quantity": "captured" if quantity_status == "EXTRACTED" else "untrusted",
            "unit_price": "derived",
            "line_total": "captured" if total_status == "EXTRACTED" else "untrusted",
        })
    subtotal = sum(item["line_total"] for item in line_items)
    payable_label = "captured" if payable_cell is not None and payable_cell.status == "EXTRACTED" else "untrusted"
    operation_id = context["operation_id"]
    device_id = context["device_id"]
    canonical: dict[str, Any] = {
        "schema_version": "0",
        "mode": context["mode"],
        "invoice_id": context["invoice_id"],
        "display_number": context["display_number"],
        "operation_id": operation_id,
        "device_id": device_id,
        "public_token": context["public_token"],
        "store_id": context["store_id"],
        "customer": {
            "phone": customer["phone"],
            "phone_status": customer["phone_status"],
        },
        "state": "EXTRACTED",
        "state_history": [{
            "from_state": "DRAFT",
            "to_state": "EXTRACTED",
            "operation_id": operation_id,
            "device_id": device_id,
        }],
        "line_items": line_items,
        "summary": {
            "subtotal": subtotal,
            "extra_amounts": {},
            "payable": payable,
        },
        "attention_cells": [cell.to_dict() for cell in attention_cells],
        "header": {
            "captured_at": captured_at,
            "printed_date": None,
            "printed_time": None,
            "invoice_number": None,
        },
        "provenance": {
            "image_sha256": image_sha256,
            "template_library_id": template_library_id,
            "engine_version": ENGINE_VERSION,
            "fields": {
                "invoice_id": "native",
                "display_number": "native",
                "operation_id": "native",
                "device_id": "native",
                "public_token": "native",
                "store_id": "native",
                "customer": {
                    "phone": customer["phone_provenance"],
                    "phone_status": "native",
                },
                "line_items": line_labels,
                "summary": {
                    "subtotal": "derived",
                    "extra_amounts": {},
                    "payable": payable_label,
                },
                "header": {
                    "captured_at": "derived" if captured_at is not None else "unavailable",
                    "printed_date": "unavailable",
                    "printed_time": "unavailable",
                    "invoice_number": "unavailable",
                },
            },
        },
    }
    return canonical, []


def _reason_for_result(
    status: str,
    gate: Any | None,
    cells: Sequence[CellOCRVariantResult],
    non_numeric_attention: Sequence[AttentionCell],
    description_failures: Sequence[str],
    *,
    explicit_reason: str | None = None,
) -> str:
    if explicit_reason:
        return explicit_reason
    if status == "AUTO_CANDIDATE":
        return "All emitted numeric cells are EXTRACTED and the arithmetic gate passed."
    reasons: list[str] = []
    if gate is not None and not gate.passed and gate.reason:
        reasons.append(f"arithmetic gate: {gate.reason}")
    reasons.extend(cell.reason for cell in cells if cell.status == "REVIEW" and cell.reason)
    reasons.extend(cell.reason for cell in non_numeric_attention)
    reasons.extend(description_failures)
    if not reasons:
        reasons.append("layout or pipeline evidence requires review")
    return "; ".join(dict.fromkeys(reasons))


def _blocked_result(
    *,
    image_sha256: str | None,
    reason: str,
    template_sources: Sequence[Mapping[str, Any]] = (),
    template_library_id: str | None = None,
    template_bank_path: str | None = None,
    layout_status: str = "BLOCKED",
    layout_reason: str | None = None,
) -> PipelineResult:
    return PipelineResult(
        status="REJECT",
        reason=reason,
        image_sha256=image_sha256,
        layout_status=layout_status,
        layout_reason=layout_reason or reason,
        row_count=None,
        cell_results=(),
        arithmetic_gate=None,
        attention_cells=(),
        description_clusters=(),
        template_library_id=template_library_id,
        template_sources=tuple(dict(source) for source in template_sources),
        template_bank_path=template_bank_path,
        canonical_invoice=None,
        canonical_valid=None,
        canonical_errors=(),
        canonical_blockers=("blocked extraction has no Canonical Invoice candidate",),
    )


def _execute_pipeline(
    image_path: Path,
    *,
    templates: GlyphTemplateSet,
    template_sources: Sequence[Mapping[str, Any]],
    template_library_id: str,
    template_bank_path: Path | None,
    captured_at: str | None,
    canonical_context: Mapping[str, Any] | None,
    evaluation: bool,
    drift_baseline_path: Path | None = None,
    enable_drift_monitor: bool = False,
    repo_root: Path = REPOSITORY_ROOT,
) -> PipelineResult:
    if evaluation:
        assert_no_template_leakage(
            image_path,
            template_sources,
            bank_path=template_bank_path,
            repo_root=repo_root,
        )
    try:
        image_sha256 = _sha256_file(image_path)
        image = _open_rgb_image(image_path)
    except Exception as exc:
        return _blocked_result(
            image_sha256=None,
            reason=f"local image read blocked: {type(exc).__name__}: {exc}",
            template_sources=template_sources,
            template_library_id=template_library_id,
            template_bank_path=str(template_bank_path) if template_bank_path else None,
        )

    safety: LayoutSafetyResult = detect_layout_safe(image)
    if safety.status == "BLOCKED":
        return _blocked_result(
            image_sha256=image_sha256,
            reason=safety.reason,
            template_sources=template_sources,
            template_library_id=template_library_id,
            template_bank_path=str(template_bank_path) if template_bank_path else None,
            layout_status="BLOCKED",
            layout_reason=safety.reason,
        )
    if safety.status != "OK" or safety.geometry is None:
        attention = (AttentionCell("layout", "", safety.reason),)
        return PipelineResult(
            status="REVIEW",
            reason=f"layout_uncertain: {safety.reason}",
            image_sha256=image_sha256,
            layout_status=safety.status,
            layout_reason=safety.reason,
            row_count=safety.row_count,
            cell_results=(),
            arithmetic_gate=None,
            attention_cells=attention,
            description_clusters=(),
            template_library_id=template_library_id,
            template_sources=tuple(dict(source) for source in template_sources),
            template_bank_path=str(template_bank_path) if template_bank_path else None,
            canonical_invoice=None,
            canonical_valid=None,
            canonical_errors=(),
            canonical_blockers=("layout uncertainty prevents Canonical Invoice assembly",),
            captured_at=captured_at,
            canonical_context=copy.deepcopy(canonical_context),
            _non_numeric_attention=attention,
        )

    payable_bbox = detect_payable_bbox(image, safety.geometry)
    spatial = _spatial_for_geometry(safety.geometry, payable_bbox)
    base_attention: list[AttentionCell] = []
    if payable_bbox is None:
        base_attention.append(AttentionCell(
            "invoice.payable", "",
            "payable text region could not be isolated unambiguously from layout geometry"))

    try:
        classifier = GlyphClassifierOCR(templates)
        raw_cells = classifier.recognize_spatial_cells(
            image_path,
            spatial,
            minimum_confidence=DEFAULT_MINIMUM_CONFIDENCE,
            extra_amounts=0,
            apply_gate=True,
        )
        # The classifier call applies the gate for its normal path. Re-run it
        # explicitly here so this result carries the gate report for routing,
        # canonical assembly, correction, and evaluation.
        cells, gate = apply_arithmetic_gate(raw_cells, extra_amounts=0)
        glyph_drift: dict[str, Any] | None = None
        drift_review = False
        if enable_drift_monitor:
            means, counts, measurement_errors = aggregate_mean_distance_by_symbol(
                classifier.last_glyph_readings)
            baseline = None
            baseline_error = None
            if drift_baseline_path is None:
                baseline_error = "onboarding baseline was not configured"
            else:
                try:
                    baseline = load_glyph_drift_baseline(drift_baseline_path)
                except Exception as exc:
                    baseline_error = (
                        f"onboarding baseline could not be loaded: {type(exc).__name__}: {exc}")
            glyph_drift = evaluate_glyph_drift(
                means,
                counts,
                template_library_id=template_library_id,
                baseline=baseline,
                baseline_error=baseline_error,
                measurement_errors=measurement_errors,
            )
            drift_review = glyph_drift["status"] == "REVIEW"
            if drift_review:
                cells = tuple(
                    replace(
                        cell,
                        status="REVIEW",
                        reason="; ".join(dict.fromkeys(
                            part for part in (cell.reason, DRIFT_REASON) if part)),
                    )
                    for cell in cells
                )
    except Exception as exc:
        return _blocked_result(
            image_sha256=image_sha256,
            reason=f"Glyph cell recognition blocked: {type(exc).__name__}: {exc}",
            template_sources=template_sources,
            template_library_id=template_library_id,
            template_bank_path=str(template_bank_path) if template_bank_path else None,
            layout_status="OK",
            layout_reason=safety.reason,
        )

    description_failures: list[str] = []
    try:
        description_crops = tuple(
            crop for crop in crop_spatial_cells(
                image,
                spatial,
                include_descriptions=True,
                include_payable=False,
            )
            if crop.field_name.endswith(".description")
        )
        description_clusters = cluster_description_crops(description_crops)
        if len(description_clusters) != safety.row_count:
            description_failures.append(
                f"description crop coverage mismatch: {len(description_clusters)} clusters for "
                f"{safety.row_count} detected rows")
    except Exception as exc:
        description_clusters = ()
        description_failures.append(
            f"description dHash clustering failed: {type(exc).__name__}: {exc}")

    base_attention.extend(
        AttentionCell("description", "", failure) for failure in description_failures)
    base_attention.extend(_numeric_attention(cells))
    if drift_review:
        base_attention.append(AttentionCell("glyph_drift", "", DRIFT_REASON))
    status = _pipeline_status(
        layout_status="OK",
        cells=cells,
        gate=gate,
        non_numeric_attention=base_attention,
        description_failures=description_failures,
    )
    if drift_review:
        status = "REVIEW"
    attention = tuple(base_attention)
    canonical_invoice: dict[str, Any] | None = None
    canonical_valid: bool | None = None
    canonical_errors: tuple[str, ...] = ()
    canonical_blockers: list[str] = []
    if drift_review:
        canonical_blockers.append(DRIFT_REASON)
    if canonical_context is None:
        canonical_blockers.extend((
            "Canonical Invoice v0 requires producer-supplied mode, platform identifiers, customer data, "
            "and a human-readable product-name mapping.",
            "dHash cluster IDs are visual sidecar evidence, not product_name text and are not added to the frozen v0 schema.",
        ))
    elif not drift_review:
        canonical_invoice, blockers = _build_canonical_invoice(
            context=canonical_context,
            cells=cells,
            row_count=safety.row_count or 0,
            attention_cells=attention,
            image_sha256=image_sha256,
            template_library_id=template_library_id,
            captured_at=captured_at,
        )
        canonical_blockers.extend(blockers)
        if canonical_invoice is not None:
            canonical_valid, errors = validate_canonical_invoice(canonical_invoice)
            canonical_errors = tuple(errors)
            if not canonical_valid:
                canonical_blockers.append("assembled Canonical Invoice candidate failed v0 validation")
                canonical_invoice = None
        if canonical_blockers and status == "AUTO_CANDIDATE":
            status = "REVIEW"

    reason = _reason_for_result(
        status,
        gate,
        cells,
        base_attention,
        description_failures,
        explicit_reason=(
            DRIFT_REASON if drift_review else (
                "Canonical context did not produce a valid v0 candidate."
                if canonical_context is not None and canonical_blockers else None
            )
        ),
    )
    return PipelineResult(
        status=status,
        reason=reason,
        image_sha256=image_sha256,
        layout_status="OK",
        layout_reason=safety.reason,
        row_count=safety.row_count,
        cell_results=tuple(cells),
        arithmetic_gate=gate,
        attention_cells=attention,
        description_clusters=description_clusters,
        template_library_id=template_library_id,
        template_sources=tuple(dict(source) for source in template_sources),
        template_bank_path=str(template_bank_path) if template_bank_path else None,
        canonical_invoice=canonical_invoice,
        canonical_valid=canonical_valid,
        canonical_errors=canonical_errors,
        canonical_blockers=tuple(canonical_blockers),
        captured_at=captured_at,
        glyph_drift=glyph_drift,
        canonical_context=copy.deepcopy(canonical_context),
        _non_numeric_attention=tuple(
            item for item in base_attention
            if item.field in {"invoice.payable", "layout", "description"}
        ),
        _description_failures=tuple(description_failures),
    )


def _load_template_bank(path: Path) -> tuple[GlyphTemplateSet, tuple[Mapping[str, Any], ...], str]:
    if not path.is_file():
        raise FileNotFoundError(f"template bank is missing: {path}")
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8"))
        templates = GlyphTemplateSet.from_json_dict(data)
    except Exception as exc:
        raise TemplateBankBuildError(f"could not load Glyph template bank {path}: {exc}") from exc
    sources = _source_records_from_bank(data)
    library_id = hashlib.sha256(raw).hexdigest()
    return templates, sources, library_id


def _resolve_drift_baseline_path(
    bank_path: Path,
    library_id: str,
    requested_path: Path | str | None,
) -> Path:
    if requested_path is not None:
        return Path(requested_path).resolve()
    if bank_path == DEFAULT_TEMPLATE_BANK_PATH.resolve():
        return DEFAULT_GLYPH_DRIFT_BASELINE_PATH

    companion = bank_path.with_name(f"{bank_path.stem}.drift.json")
    if companion.is_file():
        return companion.resolve()

    # A byte-identical copy has the same immutable library ID and may reuse
    # the matching baseline; a changed/custom bank must bring its own baseline.
    try:
        default_baseline = load_glyph_drift_baseline(DEFAULT_GLYPH_DRIFT_BASELINE_PATH)
    except Exception:
        default_baseline = None
    if (default_baseline is not None
            and default_baseline.get("template_library_id") == library_id):
        return DEFAULT_GLYPH_DRIFT_BASELINE_PATH
    return companion.resolve()


def _validate_captured_at(captured_at: str | None) -> None:
    if captured_at is None:
        return
    if not isinstance(captured_at, str) or not captured_at.strip():
        raise ValueError("captured_at must be a non-empty ISO 8601 timestamp or None")
    try:
        parsed = datetime.fromisoformat(
            captured_at[:-1] + "+00:00" if captured_at.endswith("Z") else captured_at)
    except (TypeError, ValueError) as exc:
        raise ValueError("captured_at must be an ISO 8601 timestamp with a UTC offset") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("captured_at must include an explicit UTC offset")


def extract_pipeline_v0(
    image: Path | str,
    templates_path: Path | str = DEFAULT_TEMPLATE_BANK_PATH,
    captured_at: str | None = None,
    *,
    canonical_context: Mapping[str, Any] | None = None,
    evaluation: bool = False,
    drift_baseline_path: Path | str | None = None,
) -> PipelineResult:
    """Extract one local invoice image through the E-02 Glyph pipeline.

    ``evaluation=True`` is a hard leakage guard: a matching source path, source
    SHA, or known parent of a derived-crop template raises
    :class:`TemplateLeakageError` before OCR runs. The classifier's existing
    minimum-confidence value (60) and all Glyph thresholds remain unchanged.
    DR-1 is enabled for runtime extraction. The default bank uses the
    repository's versioned baseline; a custom bank needs a companion
    ``<bank-stem>.drift.json`` baseline or an explicit ``drift_baseline_path``.
    Missing or mismatched baselines REVIEW rather than silently accepting.
    """
    _validate_captured_at(captured_at)
    image_path = Path(image).resolve()
    bank_path = Path(templates_path).resolve()
    templates, sources, library_id = _load_template_bank(bank_path)
    active_drift_baseline = _resolve_drift_baseline_path(
        bank_path,
        library_id,
        drift_baseline_path,
    )
    return _execute_pipeline(
        image_path,
        templates=templates,
        template_sources=sources,
        template_library_id=library_id,
        template_bank_path=bank_path,
        captured_at=captured_at,
        canonical_context=canonical_context,
        evaluation=evaluation,
        drift_baseline_path=active_drift_baseline,
        enable_drift_monitor=True,
    )


def apply_operator_correction(
    result: PipelineResult,
    corrections: Mapping[str, str],
) -> PipelineResult:
    """Apply explicit numeric operator corrections and rerun the arithmetic gate.

    Corrections are recorded only in the returned result. This function never
    writes or mutates a Glyph template bank. ``bank_update_eligible`` is true
    only when valid corrections leave the arithmetic gate passing; an eligible
    value still requires a separate, explicit bank-management action.
    """
    if not isinstance(corrections, Mapping) or not corrections:
        raise ValueError("corrections must be a non-empty field-to-string mapping")
    if result.status == "REJECT" or result.layout_status != "OK":
        return result

    indexed = {cell.field_name: cell for cell in result.cell_results}
    confirmed_fields = list(result.operator_confirmed_fields)
    confirmed_values = dict(result.operator_confirmed_values)
    original_values = dict(result.operator_original_values)
    unhandled: list[AttentionCell] = []
    valid_correction_count = 0
    for field_name, raw_value in corrections.items():
        if not isinstance(field_name, str) or not isinstance(raw_value, str):
            unhandled.append(AttentionCell(
                str(field_name), str(raw_value), "operator correction field and value must be strings"))
            continue
        current = indexed.get(field_name)
        if current is None or _CORRECTABLE_FIELD.fullmatch(field_name) is None:
            unhandled.append(AttentionCell(
                field_name, raw_value,
                "operator correction does not identify an emitted numeric cell"))
            continue
        if any(character.isspace() for character in raw_value):
            valid_value = None
            normalized = raw_value
        else:
            normalized = normalize_label_text(raw_value)
            if _QUANTITY_FIELD.fullmatch(field_name):
                valid_value = (
                    to_rials(normalized)
                    if normalized and all("۰" <= char <= "۹" for char in normalized)
                    else None
                )
                if valid_value is not None and valid_value <= 0:
                    valid_value = None
            else:
                parsed = parse_amount_text(normalized)
                converted = to_rials(normalized)
                valid_value = converted if parsed is not None and converted == parsed else None
        if valid_value is None:
            indexed[field_name] = replace(
                current,
                raw_value=raw_value,
                confidence=None,
                status="REVIEW",
                reason="operator correction is not a strict positive integer quantity or integer-Rial amount",
            )
            continue
        original_values.setdefault(field_name, current.raw_value)
        indexed[field_name] = replace(
            current,
            raw_value=normalized,
            confidence=None,
            status="EXTRACTED",
            reason=None,
        )
        if field_name not in confirmed_fields:
            confirmed_fields.append(field_name)
        confirmed_values[field_name] = normalized
        valid_correction_count += 1

    drift_hold = (
        isinstance(result.glyph_drift, Mapping)
        and result.glyph_drift.get("status") == "REVIEW"
    )
    ordered_cells = tuple(indexed[cell.field_name] for cell in result.cell_results)
    gated_cells, gate = apply_arithmetic_gate(ordered_cells, extra_amounts=0)
    if drift_hold:
        gated_cells = tuple(
            replace(
                cell,
                status="REVIEW",
                reason="; ".join(dict.fromkeys(
                    part for part in (cell.reason, DRIFT_REASON) if part)),
            )
            for cell in gated_cells
        )
    numeric_attention = list(_numeric_attention(gated_cells))
    attention: list[AttentionCell] = list(result._non_numeric_attention)
    attention.extend(numeric_attention)
    if drift_hold:
        attention.append(AttentionCell("glyph_drift", "", DRIFT_REASON))
    attention.extend(unhandled)
    attention_tuple = tuple(attention)
    description_failures = result._description_failures
    new_status = _pipeline_status(
        layout_status=result.layout_status,
        cells=gated_cells,
        gate=gate,
        non_numeric_attention=tuple(result._non_numeric_attention) + tuple(unhandled),
        description_failures=description_failures,
    )
    if result.status == "REVIEW" and not valid_correction_count:
        new_status = "REVIEW"
    if drift_hold:
        new_status = "REVIEW"
    canonical_invoice: dict[str, Any] | None = None
    canonical_valid: bool | None = None
    canonical_errors: tuple[str, ...] = ()
    canonical_blockers: list[str] = []
    if drift_hold:
        canonical_blockers.append(DRIFT_REASON)
    if result.canonical_context is not None and not drift_hold:
        canonical_invoice, canonical_blockers = _build_canonical_invoice(
            context=result.canonical_context,
            cells=gated_cells,
            row_count=result.row_count or 0,
            attention_cells=attention_tuple,
            image_sha256=result.image_sha256,
            template_library_id=result.template_library_id,
            captured_at=result.captured_at,
        )
        if canonical_invoice is not None:
            canonical_valid, errors = validate_canonical_invoice(canonical_invoice)
            canonical_errors = tuple(errors)
            if not canonical_valid:
                canonical_blockers.append("corrected Canonical Invoice candidate failed v0 validation")
                canonical_invoice = None
    elif result.canonical_context is None:
        canonical_blockers.extend(result.canonical_blockers)
    if result.canonical_context is not None and canonical_blockers:
        new_status = "REVIEW"
    correction_reason = _reason_for_result(
        new_status,
        gate,
        gated_cells,
        tuple(result._non_numeric_attention) + tuple(unhandled),
        description_failures,
    )
    if drift_hold:
        correction_reason = DRIFT_REASON
    elif new_status == "REVIEW" and valid_correction_count and gate.reason:
        correction_reason = f"operator correction applied; {correction_reason}"
    return replace(
        result,
        status=new_status,
        reason=correction_reason,
        cell_results=tuple(gated_cells),
        arithmetic_gate=gate,
        attention_cells=attention_tuple,
        canonical_invoice=canonical_invoice,
        canonical_valid=canonical_valid,
        canonical_errors=canonical_errors,
        canonical_blockers=tuple(canonical_blockers),
        operator_confirmed_fields=tuple(confirmed_fields),
        operator_confirmed_values=tuple(confirmed_values.items()),
        operator_original_values=tuple(original_values.items()),
        template_bank_updated=False,
        bank_update_eligible=bool(
            valid_correction_count == len(corrections)
            and valid_correction_count > 0
            and gate.passed
            and new_status == "AUTO_CANDIDATE"
        ),
    )


def _read_confirmed_fixture_labels(labels_path: Path) -> tuple[list[dict[str, Any]], Path]:
    try:
        data = json.loads(labels_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemplateBankBuildError(f"cannot read local fixture labels {labels_path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise TemplateBankBuildError("fixture labels root must be a JSON object")
    if data.get("label_status") != "OPERATOR_CONFIRMED":
        raise TemplateBankBuildError("fixture labels must declare label_status=OPERATOR_CONFIRMED")
    entries = data.get("invoices")
    if not isinstance(entries, list):
        raise TemplateBankBuildError("fixture labels need an 'invoices' list")
    ids = [str(item.get("id")) for item in entries if isinstance(item, Mapping)]
    if len(ids) != 4 or set(ids) != set(SUPPORTED_FIXTURE_IDS) or len(set(ids)) != 4:
        raise TemplateBankBuildError(
            "default bank/LOO evaluation requires exactly fixture IDs 29, 31, 32, and 33")
    return entries, labels_path.parent.resolve()


def _relative_source_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _build_template_set(
    entries: Sequence[Mapping[str, Any]],
    labels_dir: Path,
    *,
    repo_root: Path,
) -> tuple[GlyphTemplateSet, tuple[Mapping[str, Any], ...], tuple[str, ...], int]:
    templates = GlyphTemplateSet()
    source_metadata: list[Mapping[str, Any]] = []
    build_logs: list[str] = []
    training_cell_count = 0
    for entry in entries:
        image_path = (labels_dir / str(entry.get("path", ""))).resolve()
        if not image_path.is_file():
            raise TemplateBankBuildError(f"fixture image is missing: {image_path}")
        try:
            image = _open_rgb_image(image_path)
        except Exception as exc:
            raise TemplateBankBuildError(f"could not read fixture image {image_path}: {exc}") from exc
        safety = detect_layout_safe(image)
        if safety.status != "OK" or safety.geometry is None:
            raise TemplateBankBuildError(
                f"fixture #{entry.get('id')} layout is not safe: {safety.status}: {safety.reason}")
        payable_bbox = detect_payable_bbox(image, safety.geometry)
        spatial = _spatial_for_geometry(safety.geometry, payable_bbox)
        crops = crop_spatial_cells(
            image,
            spatial,
            include_descriptions=False,
            include_payable=True,
        )
        values = entry.get("values", {})
        if not isinstance(values, Mapping):
            raise TemplateBankBuildError(f"fixture #{entry.get('id')} has no numeric values map")
        labelled: list[LabeledCell] = []
        excluded_fields: list[str] = []
        for crop in crops:
            if crop.field_name == "invoice.payable" and entry.get("payable_label_note"):
                # Fixture #31's payable is derived from confirmed line totals;
                # it is not an independent visual glyph label for training.
                excluded_fields.append(crop.field_name)
                continue
            value = values.get(crop.field_name)
            if value is None:
                continue
            if not isinstance(value, str):
                raise TemplateBankBuildError(
                    f"fixture #{entry.get('id')} label {crop.field_name} must be a string")
            if _cell_label_value(crop.field_name, value) is None:
                raise TemplateBankBuildError(
                    f"fixture #{entry.get('id')} label {crop.field_name} is not a strict numeric label")
            labelled.append(LabeledCell(crop.field_name, crop.image, value))
        training_cell_count += len(labelled)
        templates, report = build_templates(labelled, templates)
        build_logs.extend(report)
        source_hash = _sha256_file(image_path)
        source_name = _relative_source_path(image_path, repo_root)
        source_record = {
            "image": source_name,
            "path": source_name,
            "sha256": source_hash,
            "fixture_id": str(entry.get("id")),
        }
        templates.provenance.append({"image": source_name, "sha256": source_hash})
        used_fields = [cell.field_name for cell in labelled]
        source_metadata.append({
            **source_record,
            "training_fields": used_fields,
            "excluded_fields": excluded_fields,
        })
        if payable_bbox is None:
            build_logs.append(
                f"SKIP invoice.payable for fixture #{entry.get('id')}: payable region was ambiguous")
    return templates, tuple(source_metadata), tuple(build_logs), training_cell_count


def _cell_label_value(field_name: str, value: str) -> int | None:
    normalized = normalize_label_text(value)
    if _QUANTITY_FIELD.fullmatch(field_name):
        if not normalized or not all("۰" <= char <= "۹" for char in normalized):
            return None
        converted = to_rials(normalized)
        return converted if converted is not None and converted > 0 else None
    if _TOTAL_FIELD.fullmatch(field_name) or field_name == "invoice.payable":
        parsed = parse_amount_text(normalized)
        converted = to_rials(normalized)
        return converted if parsed is not None and converted == parsed else None
    return None


def _assert_default_bank_destination(output_path: Path, repo_root: Path) -> None:
    if output_path.resolve() == (repo_root / "src" / "templates.json").resolve():
        raise TemplateBankBuildError(
            "refusing to overwrite frozen src/templates.json; use src/templates_bank_default.json")


def build_default_template_bank(
    *,
    labels_path: Path | str = DEFAULT_LABELS_PATH,
    output_path: Path | str = DEFAULT_TEMPLATE_BANK_PATH,
    repo_root: Path | str = REPOSITORY_ROOT,
) -> TemplateBankBuildReport:
    """Build a fresh all-four Glyph bank with source hashes and field lineage."""
    root = Path(repo_root).resolve()
    target = Path(output_path).resolve()
    _assert_default_bank_destination(target, root)
    entries, labels_dir = _read_confirmed_fixture_labels(Path(labels_path).resolve())
    templates, source_metadata, logs, training_cell_count = _build_template_set(
        entries, labels_dir, repo_root=root)
    payload = templates.to_json_dict()
    payload["bank_metadata"] = {
        "bank_id": "default-e-02-v0",
        "purpose": "default runtime bank; never use to evaluate its source fixtures",
        "built_by": "scripts/build_default_template_bank.py",
        "source_images": [dict(item) for item in source_metadata],
        "leakage_policy": "evaluation refuses any matching source path or SHA-256",
        "dhash_threshold": DEFAULT_DHASH_THRESHOLD,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    used_count = sum(line.startswith("USED ") for line in logs)
    skipped = tuple(line for line in logs if line.startswith("SKIP "))
    return TemplateBankBuildReport(
        output_path=str(target),
        bank_sha256=_sha256_file(target),
        source_images=source_metadata,
        template_counts=templates.counts(),
        training_cell_count=training_cell_count,
        used_cell_count=used_count,
        skipped_cells=skipped,
    )


def build_templates_for_fold(
    labels_path: Path | str,
    held_out_invoice_id: str,
    *,
    repo_root: Path | str = REPOSITORY_ROOT,
) -> GlyphTemplateSet:
    """Build fold-local templates from the other three fixtures only."""
    if str(held_out_invoice_id) not in SUPPORTED_FIXTURE_IDS:
        raise ValueError(f"unsupported held-out invoice ID: {held_out_invoice_id}")
    entries, labels_dir = _read_confirmed_fixture_labels(Path(labels_path).resolve())
    held_out = str(held_out_invoice_id)
    training = [entry for entry in entries if str(entry.get("id")) != held_out]
    if len(training) != 3:
        raise TemplateBankBuildError("leave-one-out folds must train on exactly three fixtures")
    templates, _, _, _ = _build_template_set(
        training,
        labels_dir,
        repo_root=Path(repo_root).resolve(),
    )
    return templates


def run_leave_one_out_evaluation(
    labels_path: Path | str = DEFAULT_LABELS_PATH,
    *,
    repo_root: Path | str = REPOSITORY_ROOT,
) -> tuple[LeaveOneOutFoldOutcome, ...]:
    """Run four fold-specific, provenance-checked pipeline evaluations in memory."""
    entries, labels_dir = _read_confirmed_fixture_labels(Path(labels_path).resolve())
    root = Path(repo_root).resolve()
    outcomes: list[LeaveOneOutFoldOutcome] = []
    for held_out in entries:
        invoice_id = str(held_out["id"])
        templates = build_templates_for_fold(
            labels_path,
            invoice_id,
            repo_root=root,
        )
        image_path = (labels_dir / str(held_out["path"])).resolve()
        sources = _source_records_from_bank({"provenance": templates.provenance})
        library_id = _template_set_sha256(templates)
        result = _execute_pipeline(
            image_path,
            templates=templates,
            template_sources=sources,
            template_library_id=library_id,
            template_bank_path=None,
            captured_at=None,
            canonical_context=None,
            evaluation=True,
            repo_root=root,
        )
        labels = held_out.get("values", {})
        derived_payable = bool(held_out.get("payable_label_note"))
        excluded = ("invoice.payable",) if derived_payable else ()
        comparisons = 0
        wrong = 0
        for cell in result.cell_results:
            reference = labels.get(cell.field_name) if isinstance(labels, Mapping) else None
            if (cell.status != "EXTRACTED" or not isinstance(reference, str)
                    or (derived_payable and cell.field_name == "invoice.payable")):
                continue
            comparisons += 1
            predicted_value = _cell_label_value(cell.field_name, cell.raw_value)
            reference_value = _cell_label_value(cell.field_name, reference)
            if predicted_value is None or reference_value is None or predicted_value != reference_value:
                wrong += 1
        cells = result.cell_results
        outcomes.append(LeaveOneOutFoldOutcome(
            invoice_id=invoice_id,
            status=result.status,
            numeric_cells=len(cells),
            extracted_cells=sum(cell.status == "EXTRACTED" for cell in cells),
            review_cells=sum(cell.status == "REVIEW" for cell in cells),
            blocked_cells=sum(cell.status == "BLOCKED" for cell in cells),
            arithmetic_gate_passed=bool(result.arithmetic_gate and result.arithmetic_gate.passed),
            arithmetic_gate_reason=(result.arithmetic_gate.reason if result.arithmetic_gate else result.reason),
            extracted_but_wrong=wrong,
            independent_extracted_label_comparisons=comparisons,
            excluded_ground_truth_fields=excluded,
            canonical_invoice_created=result.canonical_invoice is not None,
        ))
    return tuple(outcomes)


__all__ = [
    "AttentionCell",
    "DescriptionCluster",
    "LeaveOneOutFoldOutcome",
    "PipelineResult",
    "TemplateBankBuildError",
    "TemplateBankBuildReport",
    "TemplateLeakageError",
    "TemplateProvenanceError",
    "apply_operator_correction",
    "assert_no_template_leakage",
    "build_default_template_bank",
    "build_templates_for_fold",
    "cluster_description_crops",
    "detect_payable_bbox",
    "extract_pipeline_v0",
    "run_leave_one_out_evaluation",
    "to_rials",
]
