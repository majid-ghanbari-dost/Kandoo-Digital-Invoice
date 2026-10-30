"""Glyph-template engine for numeric cells of Holo thermal-receipt rasters.

Why this exists
---------------
Holo prints with a fixed bitmap font on a 203-dpi thermal raster, so a numeric
cell contains only twelve possible symbols: the digits ۰-۹ and the thousands
comma. General OCR (Tesseract) drops the small diamond zero and confuses glyphs
of this font. This module segments a cell into connected components and
classifies each component against labelled glyph templates.

Policy (unchanged from ocr.py)
------------------------------
* The engine reports what it read. Nothing is repaired, guessed or "fixed":
  an unrecognised glyph is emitted as ``?`` and the cell stays REVIEW.
* A cell is EXTRACTED only when every check passes; any doubt means REVIEW.
* The arithmetic gate can only DOWNGRADE results (to REVIEW), never upgrade.
* The engine never makes a result issuable. Full-page REVIEW stays REVIEW.

Scope
-----
Numeric cells only (line totals, quantities, payable). Description cells are
not handled here. Pillow is imported lazily; the rest is pure standard library.

Calibration warning
-------------------
``DEFAULT_MAX_DISTANCE`` and ``DEFAULT_MIN_MARGIN`` were set from one pair of
invoices (templates from one, scored on the other, in both directions): correct
glyphs had distance <= 0.164 and margin >= 0.198; wrong glyphs had distance
>= 0.198 and margin <= 0.108. That is a tiny sample. Re-check them with the
``evaluate`` command on invoices that were NOT used to build the templates.

Command line (run from the directory that contains ``image_extraction_adapter``)::

    python -m image_extraction_adapter.glyph_classifier build \
        --labels labels_build.json --out templates.json
    python -m image_extraction_adapter.glyph_classifier evaluate \
        --labels labels_eval.json --templates templates.json

Label file format (JSON)::

    {"images": [{
        "path": "invoice.png",
        "column_boundaries": [113.5, 241.5, 290.5, 484.5, 524.5],  # optional fallback
        "row_bands": [[520.75, 588.25], [588.25, 656.0]],          # optional fallback
        "payable_bbox": [left, top, width, height],      # optional
        "values": {"line.0.total": "۱,۴۵۰,۰۰۰", "line.0.quantity": "۱",
                   "invoice.payable": "۷,۴۶۰,۰۰۰"}
    }]}

``values`` must be CONFIRMED values (from Holo), never OCR output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Optional

from .model import CellOCRVariantResult
from .ocr import OCREngineUnavailable, OCRExecutionError
from .preprocessing import crop_spatial_cells, preprocess_cell

__all__ = [
    "ArithmeticGateReport",
    "CellReading",
    "GlyphClassifierOCR",
    "GlyphReading",
    "GlyphTemplate",
    "GlyphTemplateSet",
    "LabeledCell",
    "apply_arithmetic_gate",
    "build_templates",
    "evaluate_arithmetic_gate",
    "parse_amount_text",
]

ENGINE_NAME = "glyph-classifier/1"
PREPROCESSING_LABEL = "glyph"
GLYPH_ALPHABET = "۰۱۲۳۴۵۶۷۸۹,"
TEMPLATE_FORMAT_VERSION = 1

GRID_WIDTH = 10
GRID_HEIGHT = 14
FOREGROUND_THRESHOLD = 128
MIN_COMPONENT_PIXELS = 4
X_OVERLAP_MERGE_RATIO = 0.7
GEOMETRY_WEIGHT = 2.0
RULE_MAX_WIDTH = 2
RULE_MIN_HEIGHT_RATIO = 0.8

DEFAULT_MAX_DISTANCE = 0.25
DEFAULT_MIN_MARGIN = 0.15
DEFAULT_MAX_GLYPH_WIDTH_RATIO = 1.0

PROFILE_ROW = "row"
PROFILE_PAYABLE = "payable"
PAYABLE_FIELD = "invoice.payable"

SOURCE_REVIEW_REASON = (
    "full-page spatial assessment remains REVIEW; cell OCR is supplementary")

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ALL_DIGIT_SCRIPTS = "0123456789٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹"
_TO_PERSIAN = str.maketrans(_ALL_DIGIT_SCRIPTS, _PERSIAN_DIGITS * 3)
_TO_ASCII = str.maketrans(_PERSIAN_DIGITS, "0123456789")
_NUMERIC_FORMAT = re.compile(r"^(?:[۰-۹]+|[۰-۹]{1,3}(?:,[۰-۹]{3})+)$")
_LINE_TOTAL_FIELD = re.compile(r"^line\.(\d+)\.total$")


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Component:
    left: int
    top: int
    right: int      # exclusive
    bottom: int     # exclusive
    pixels: int
    rows: tuple     # tuple of bytes; one 0/1 byte per pixel, width = right-left

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def _foreground_rows(image: Any) -> tuple[int, int, list[bytearray]]:
    gray = image.convert("L")
    width, height = gray.size
    data = gray.tobytes()
    rows = []
    for y in range(height):
        base = y * width
        rows.append(bytearray(
            1 if data[base + x] < FOREGROUND_THRESHOLD else 0
            for x in range(width)))
    return width, height, rows


def _component_from_points(points: list[tuple[int, int]]) -> _Component:
    left = min(x for x, _ in points)
    right = max(x for x, _ in points) + 1
    top = min(y for _, y in points)
    bottom = max(y for _, y in points) + 1
    grid = [bytearray(right - left) for _ in range(bottom - top)]
    for x, y in points:
        grid[y - top][x - left] = 1
    return _Component(left, top, right, bottom, len(points),
                      tuple(bytes(row) for row in grid))


def _label_components(width: int, height: int,
                      rows: list[bytearray]) -> list[_Component]:
    seen = [bytearray(width) for _ in range(height)]
    components: list[_Component] = []
    for y0 in range(height):
        for x0 in range(width):
            if not rows[y0][x0] or seen[y0][x0]:
                continue
            seen[y0][x0] = 1
            stack = [(x0, y0)]
            points: list[tuple[int, int]] = []
            while stack:
                x, y = stack.pop()
                points.append((x, y))
                for ny in (y - 1, y, y + 1):
                    if not 0 <= ny < height:
                        continue
                    for nx in (x - 1, x, x + 1):
                        if (0 <= nx < width and rows[ny][nx]
                                and not seen[ny][nx]):
                            seen[ny][nx] = 1
                            stack.append((nx, ny))
            components.append(_component_from_points(points))
    return components


def _union(a: _Component, b: _Component) -> _Component:
    left, right = min(a.left, b.left), max(a.right, b.right)
    top, bottom = min(a.top, b.top), max(a.bottom, b.bottom)
    grid = [bytearray(right - left) for _ in range(bottom - top)]
    for comp in (a, b):
        for y, row in enumerate(comp.rows):
            for x, value in enumerate(row):
                if value:
                    grid[comp.top - top + y][comp.left - left + x] = 1
    return _Component(left, top, right, bottom, a.pixels + b.pixels,
                      tuple(bytes(row) for row in grid))


def _x_overlap_ratio(a: _Component, b: _Component) -> float:
    overlap = min(a.right, b.right) - max(a.left, b.left)
    smaller = min(a.width, b.width)
    return max(0, overlap) / smaller if smaller else 0.0


def _is_rule_remnant(comp: _Component, cell_height: int) -> bool:
    """A hairline spanning most of the cell height is a table rule, not a glyph.

    Rule removal in preprocessing normally deletes these; this is a second
    defence for rule pixels that survive it. Digit strokes are wider than
    RULE_MAX_WIDTH, so no glyph is dropped by this test.
    """
    return (comp.width <= RULE_MAX_WIDTH
            and comp.height >= RULE_MIN_HEIGHT_RATIO * cell_height)


def segment_cell(binary_image: Any) -> tuple[int, int, list[_Component]]:
    """Return (cell_width, cell_height, components ordered left to right)."""
    width, height, rows = _foreground_rows(binary_image)
    components = [c for c in _label_components(width, height, rows)
                  if c.pixels >= MIN_COMPONENT_PIXELS
                  and not _is_rule_remnant(c, height)]
    components.sort(key=lambda c: (c.left, c.top))
    merged: list[_Component] = []
    for comp in components:
        if merged and _x_overlap_ratio(merged[-1], comp) >= X_OVERLAP_MERGE_RATIO:
            merged[-1] = _union(merged[-1], comp)
        else:
            merged.append(comp)
    return width, height, merged


# --------------------------------------------------------------------------
# Features
# --------------------------------------------------------------------------

def _line_reference(components: list[_Component]) -> tuple[float, float]:
    """Return (reference_top, reference_height) from the tall glyphs of a cell.

    Geometry is expressed relative to the digit line so it does not depend on
    the absolute row position or on the font size of the cell.
    """
    max_height = max(c.height for c in components)
    tall = [c for c in components if c.height >= 0.6 * max_height]
    return (float(statistics.median(c.top for c in tall)),
            float(statistics.median(c.height for c in tall)))


def _geometry(comp: _Component, ref_top: float, ref_height: float
              ) -> tuple[float, float, float, float]:
    return (comp.width / ref_height,
            comp.height / ref_height,
            (comp.top - ref_top) / ref_height,
            (comp.bottom - ref_top) / ref_height)


def _grid(comp: _Component) -> tuple[float, ...]:
    width, height = comp.width, comp.height
    values: list[float] = []
    for gy in range(GRID_HEIGHT):
        y0 = gy * height // GRID_HEIGHT
        y1 = max(y0 + 1, -(-(gy + 1) * height // GRID_HEIGHT))
        for gx in range(GRID_WIDTH):
            x0 = gx * width // GRID_WIDTH
            x1 = max(x0 + 1, -(-(gx + 1) * width // GRID_WIDTH))
            total = count = 0
            for y in range(y0, min(y1, height)):
                row = comp.rows[y]
                for x in range(x0, min(x1, width)):
                    total += row[x]
                    count += 1
            values.append(total / count if count else 0.0)
    return tuple(values)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GlyphTemplate:
    label: str
    geometry: tuple[float, float, float, float]
    grid: tuple[float, ...]


class GlyphTemplateSet:
    """Labelled glyph templates grouped by profile ('row', 'payable')."""

    def __init__(self, profiles: Optional[dict[str, list[GlyphTemplate]]] = None,
                 provenance: Optional[list[dict]] = None) -> None:
        self.profiles: dict[str, list[GlyphTemplate]] = profiles or {}
        self.provenance: list[dict] = provenance or []

    def add(self, profile: str, template: GlyphTemplate) -> bool:
        """Add a template unless an identical one exists; True if added."""
        key = (template.label,
               tuple(round(v, 2) for v in template.grid),
               tuple(round(v, 2) for v in template.geometry))
        bucket = self.profiles.setdefault(profile, [])
        for existing in bucket:
            if key == (existing.label,
                       tuple(round(v, 2) for v in existing.grid),
                       tuple(round(v, 2) for v in existing.geometry)):
                return False
        bucket.append(template)
        return True

    def counts(self) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        for profile, templates in self.profiles.items():
            tally: dict[str, int] = {}
            for template in templates:
                tally[template.label] = tally.get(template.label, 0) + 1
            result[profile] = tally
        return result

    def to_json_dict(self) -> dict:
        return {
            "format_version": TEMPLATE_FORMAT_VERSION,
            "grid": [GRID_WIDTH, GRID_HEIGHT],
            "provenance": self.provenance,
            "profiles": {
                profile: [{
                    "label": t.label,
                    "geometry": [round(v, 4) for v in t.geometry],
                    "grid": [round(v, 3) for v in t.grid],
                } for t in templates]
                for profile, templates in self.profiles.items()
            },
        }

    @classmethod
    def from_json_dict(cls, data: dict) -> "GlyphTemplateSet":
        if data.get("format_version") != TEMPLATE_FORMAT_VERSION:
            raise ValueError("unsupported glyph template format_version")
        if list(data.get("grid", ())) != [GRID_WIDTH, GRID_HEIGHT]:
            raise ValueError("glyph template grid size does not match this module")
        profiles: dict[str, list[GlyphTemplate]] = {}
        for profile, items in data.get("profiles", {}).items():
            bucket = []
            for item in items:
                label = item["label"]
                if label not in GLYPH_ALPHABET:
                    raise ValueError(f"template label outside alphabet: {label!r}")
                geometry = tuple(float(v) for v in item["geometry"])
                grid = tuple(float(v) for v in item["grid"])
                if len(geometry) != 4 or len(grid) != GRID_WIDTH * GRID_HEIGHT:
                    raise ValueError("malformed glyph template")
                bucket.append(GlyphTemplate(label, geometry, grid))
            profiles[profile] = bucket
        return cls(profiles, list(data.get("provenance", [])))

    def save(self, path: Path) -> None:
        data = json.dumps(self.to_json_dict(), ensure_ascii=False, indent=1).encode("utf-8")
        Path(path).write_bytes(data)

    @classmethod
    def load(cls, path: Path) -> "GlyphTemplateSet":
        return cls.from_json_dict(
            json.loads(Path(path).read_bytes().decode("utf-8")))


# --------------------------------------------------------------------------
# Reading a cell
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class GlyphReading:
    """Classification of one component. ``label`` is None when rejected."""

    label: Optional[str]
    best_label: str
    distance: float
    margin: float
    confidence: float
    bbox: tuple[int, int, int, int]
    note: Optional[str] = None


@dataclass(frozen=True)
class CellReading:
    raw_value: str
    confidence: float
    readings: tuple[GlyphReading, ...]
    reasons: tuple[str, ...]
    line_pixels_removed: int = 0


def _distance(grid: tuple[float, ...], geometry: tuple[float, ...],
              template: GlyphTemplate) -> float:
    bitmap = sum(abs(a - b) for a, b in zip(grid, template.grid)) / len(grid)
    geo = sum(abs(a - b) for a, b in zip(geometry, template.geometry)) / 4
    return bitmap + GEOMETRY_WEIGHT * geo


def _profile_chain(profile: str, payable_uses_row: bool) -> tuple[str, ...]:
    if profile == PROFILE_PAYABLE and payable_uses_row:
        return (PROFILE_PAYABLE, PROFILE_ROW)
    return (profile,)


def profile_for_field(field_name: str) -> str:
    return PROFILE_PAYABLE if field_name == PAYABLE_FIELD else PROFILE_ROW


def normalize_label_text(text: str) -> str:
    """Persian-digit form of a confirmed value; spaces removed, ٬ -> ','."""
    return text.translate(_TO_PERSIAN).replace("٬", ",").replace(" ", "")


def parse_amount_text(text: Optional[str]) -> Optional[int]:
    """Integer value of a well-formed Persian-digit amount, else None."""
    if not isinstance(text, str) or _NUMERIC_FORMAT.fullmatch(text) is None:
        return None
    return int(text.replace(",", "").translate(_TO_ASCII))


class _Classifier:
    def __init__(self, templates: GlyphTemplateSet, *, max_distance: float,
                 min_margin: float, max_glyph_width_ratio: float,
                 payable_uses_row_templates: bool) -> None:
        if max_distance <= 0:
            raise ValueError("max_distance must be positive")
        if min_margin < 0:
            raise ValueError("min_margin must not be negative")
        self.templates = templates
        self.max_distance = max_distance
        self.min_margin = min_margin
        self.max_glyph_width_ratio = max_glyph_width_ratio
        self.payable_uses_row_templates = payable_uses_row_templates

    def _templates_for(self, profile: str) -> list[GlyphTemplate]:
        pooled: list[GlyphTemplate] = []
        for name in _profile_chain(profile, self.payable_uses_row_templates):
            pooled.extend(self.templates.profiles.get(name, ()))
        return pooled

    def classify(self, grid: tuple[float, ...], geometry: tuple[float, ...],
                 pool: list[GlyphTemplate]) -> tuple[str, float, float]:
        best: dict[str, float] = {}
        for template in pool:
            d = _distance(grid, geometry, template)
            if d < best.get(template.label, float("inf")):
                best[template.label] = d
        ranked = sorted(best.items(), key=lambda item: item[1])
        label, d1 = ranked[0]
        margin = (ranked[1][1] - d1) if len(ranked) > 1 else self.max_distance
        return label, d1, margin

    def read(self, binary_image: Any, profile: str,
             line_pixels_removed: int = 0) -> CellReading:
        width, height, components = segment_cell(binary_image)
        reasons: list[str] = []
        if not components:
            return CellReading("", 0.0, (), ("cell OCR returned no glyphs",),
                               line_pixels_removed)
        pool = self._templates_for(profile)
        if not pool:
            return CellReading(
                "", 0.0, (),
                (f"no glyph templates for profile {profile!r}",),
                line_pixels_removed)

        ref_top, ref_height = _line_reference(components)
        readings: list[GlyphReading] = []
        text: list[str] = []
        for index, comp in enumerate(components, start=1):
            bbox = (comp.left, comp.top, comp.right, comp.bottom)
            geometry = _geometry(comp, ref_top, ref_height)
            problems: list[str] = []
            if comp.left == 0 or comp.right == width or comp.top == 0 or comp.bottom == height:
                problems.append("glyph touches the crop edge (possible clipping)")
            if geometry[0] > self.max_glyph_width_ratio:
                problems.append("component too wide for one glyph (touching glyphs?)")
            label, d1, margin = self.classify(_grid(comp), geometry, pool)

            note = None
            if d1 > self.max_distance:
                note = f"distance {d1:.3f} exceeds {self.max_distance:.3f}"
            elif margin < self.min_margin:
                note = f"ambiguous: margin {margin:.3f} below {self.min_margin:.3f}"
            if problems:
                note = "; ".join(problems + ([note] if note else []))

            if note:
                readings.append(GlyphReading(
                    None, label, d1, margin, 0.0, bbox, note))
                text.append("?")
                reasons.append(f"glyph {index} not accepted: {note}")
            else:
                # Confidence reflects distance only; the margin is a hard
                # accept/reject test above, not a score.
                confidence = 100.0 * (1.0 - d1 / self.max_distance)
                readings.append(GlyphReading(
                    label, label, d1, margin,
                    max(0.0, min(100.0, confidence)), bbox))
                text.append(label)
        raw_value = "".join(text)
        confidence = min(r.confidence for r in readings)
        return CellReading(raw_value, confidence, tuple(readings),
                           tuple(dict.fromkeys(reasons)), line_pixels_removed)


def _binarize(cell_image: Any) -> tuple[Any, int]:
    """Same Otsu + table-rule removal path used by the Tesseract backend."""
    processed = preprocess_cell(cell_image, "otsu")
    return processed.image, processed.line_pixels_removed


# --------------------------------------------------------------------------
# Building templates from confirmed labels
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LabeledCell:
    field_name: str
    image: Any          # PIL image of the cell crop
    text: str           # CONFIRMED value, never OCR output


def build_templates(cells: Iterable[LabeledCell],
                    templates: Optional[GlyphTemplateSet] = None
                    ) -> tuple[GlyphTemplateSet, list[str]]:
    """Add templates from labelled cells; skip cells that do not segment cleanly.

    A cell is used only when its component count equals its symbol count, so a
    template can never be built from a mis-segmented glyph.
    """
    result = templates or GlyphTemplateSet()
    report: list[str] = []
    for cell in cells:
        text = normalize_label_text(cell.text)
        profile = profile_for_field(cell.field_name)
        if not text or any(ch not in GLYPH_ALPHABET for ch in text):
            report.append(f"SKIP {cell.field_name}: label {cell.text!r} has symbols outside the alphabet")
            continue
        binary, _ = _binarize(cell.image)
        _, _, components = segment_cell(binary)
        if len(components) != len(text):
            report.append(
                f"SKIP {cell.field_name}: {len(components)} components != {len(text)} symbols in {text!r}")
            continue
        ref_top, ref_height = _line_reference(components)
        added = 0
        for symbol, comp in zip(text, components):
            template = GlyphTemplate(
                symbol, _geometry(comp, ref_top, ref_height), _grid(comp))
            added += result.add(profile, template)
        report.append(f"USED {cell.field_name}: {text} (+{added} new templates)")
    return result, report


# --------------------------------------------------------------------------
# Arithmetic gate
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ArithmeticGateReport:
    passed: bool
    reason: Optional[str]
    line_sum: Optional[int]
    payable: Optional[int]
    extra_amounts: int
    checked_fields: tuple[str, ...]


def evaluate_arithmetic_gate(results: Iterable[CellOCRVariantResult], *,
                             extra_amounts: int = 0,
                             preprocessing: str = PREPROCESSING_LABEL
                             ) -> ArithmeticGateReport:
    """Check: sum(line totals) + extra_amounts == payable.

    ``extra_amounts`` is VAT plus levies already known to the caller. It
    defaults to 0, which is only right for invoices whose VAT/levy lines are
    empty (as on the sample invoices). Fails closed on any missing, malformed
    or non-contiguous cell.
    """
    totals: dict[int, CellOCRVariantResult] = {}
    payable: Optional[CellOCRVariantResult] = None
    for result in results:
        if result.preprocessing != preprocessing:
            continue
        match = _LINE_TOTAL_FIELD.match(result.field_name)
        if match:
            totals[int(match.group(1))] = result
        elif result.field_name == PAYABLE_FIELD:
            payable = result

    def fail(reason: str, line_sum=None, payable_value=None):
        return ArithmeticGateReport(
            False, reason, line_sum, payable_value, extra_amounts,
            tuple(sorted(r.field_name for r in totals.values()))
            + ((PAYABLE_FIELD,) if payable else ()))

    if not totals:
        return fail("no line total cells to cross-check")
    if sorted(totals) != list(range(len(totals))):
        return fail("line total cells are not contiguous from line.0")
    if payable is None:
        return fail("payable cell missing; line sum cannot be cross-checked")

    values: dict[int, int] = {}
    for index, result in totals.items():
        value = parse_amount_text(result.raw_value)
        if value is None:
            return fail(f"line.{index}.total {result.raw_value!r} is not a well-formed amount")
        values[index] = value
    payable_value = parse_amount_text(payable.raw_value)
    if payable_value is None:
        return fail(f"payable {payable.raw_value!r} is not a well-formed amount")

    line_sum = sum(values.values())
    if line_sum + extra_amounts != payable_value:
        return fail(
            f"line sum {line_sum} + extras {extra_amounts} != payable {payable_value}",
            line_sum, payable_value)
    return ArithmeticGateReport(
        True, None, line_sum, payable_value, extra_amounts,
        tuple(f"line.{i}.total" for i in sorted(values)) + (PAYABLE_FIELD,))


def apply_arithmetic_gate(results: Iterable[CellOCRVariantResult], *,
                          extra_amounts: int = 0,
                          preprocessing: str = PREPROCESSING_LABEL
                          ) -> tuple[tuple[CellOCRVariantResult, ...], ArithmeticGateReport]:
    """Downgrade total/payable cells to REVIEW when the gate fails.

    Never upgrades a result and never alters ``raw_value``.
    """
    materialised = tuple(results)
    report = evaluate_arithmetic_gate(
        materialised, extra_amounts=extra_amounts, preprocessing=preprocessing)
    if report.passed:
        return materialised, report
    note = f"arithmetic gate failed: {report.reason}"
    adjusted = []
    for result in materialised:
        is_amount = (result.preprocessing == preprocessing
                     and (_LINE_TOTAL_FIELD.match(result.field_name)
                          or result.field_name == PAYABLE_FIELD))
        if is_amount:
            reason = "; ".join(dict.fromkeys(
                [part for part in (result.reason, note) if part]))
            result = replace(result, status="REVIEW", reason=reason)
        adjusted.append(result)
    return tuple(adjusted), report


# --------------------------------------------------------------------------
# Engine (drop-in sibling of TesseractOCR.recognize_spatial_cells)
# --------------------------------------------------------------------------

class GlyphClassifierOCR:
    """Numeric-cell engine with the same call shape as TesseractOCR."""

    def __init__(self, templates: GlyphTemplateSet, *,
                 max_distance: float = DEFAULT_MAX_DISTANCE,
                 min_margin: float = DEFAULT_MIN_MARGIN,
                 max_glyph_width_ratio: float = DEFAULT_MAX_GLYPH_WIDTH_RATIO,
                 payable_uses_row_templates: bool = True) -> None:
        self._classifier = _Classifier(
            templates, max_distance=max_distance, min_margin=min_margin,
            max_glyph_width_ratio=max_glyph_width_ratio,
            payable_uses_row_templates=payable_uses_row_templates)
        # Adapter-local diagnostics consumed by DR-1; not part of the frozen
        # Canonical Invoice contract or the public OCR cell-result schema.
        self.last_glyph_readings: tuple[tuple[str, CellReading], ...] = ()

    @classmethod
    def from_file(cls, templates_path: Path, **kwargs: Any) -> "GlyphClassifierOCR":
        return cls(GlyphTemplateSet.load(templates_path), **kwargs)

    def _recognize_crops(self, crops: Iterable[Any], spatial: Any,
                         minimum_confidence: float
                         ) -> list[tuple[Any, CellOCRVariantResult, CellReading]]:
        assessments = {
            assessment.field_name: assessment
            for assessment in getattr(spatial, "assessments", ())}
        output = []
        for crop in crops:
            if not crop.numeric:
                continue
            binary, removed = _binarize(crop.image)
            reading = self._classifier.read(
                binary, profile_for_field(crop.field_name), removed)
            reasons = list(reading.reasons)
            if not reading.raw_value:
                reasons.append("cell OCR returned no numeric text")
            elif reading.confidence < minimum_confidence:
                reasons.append(
                    f"cell OCR confidence {reading.confidence:.2f} is below "
                    f"{minimum_confidence:.2f}")
            if reading.raw_value and _NUMERIC_FORMAT.fullmatch(reading.raw_value) is None:
                reasons.append("raw cell OCR does not match the declared numeric format")
            source = assessments.get(crop.field_name)
            if getattr(source, "status", None) == "REVIEW":
                reasons.append(SOURCE_REVIEW_REASON)
            reason = "; ".join(dict.fromkeys(reasons)) or None
            output.append((crop, CellOCRVariantResult(
                field_name=crop.field_name,
                preprocessing=PREPROCESSING_LABEL,
                bbox=crop.bbox,
                raw_value=reading.raw_value,
                confidence=reading.confidence,
                status="REVIEW" if reason else "EXTRACTED",
                reason=reason,
                unrestricted_raw_value=None,
                line_pixels_removed=reading.line_pixels_removed,
                psm=0,                      # not applicable: no Tesseract page mode
                whitelist=GLYPH_ALPHABET,
            ), reading))
        return output

    def recognize_spatial_cells(
        self,
        image_path: Path,
        spatial: Any,
        *,
        minimum_confidence: float,
        scale_factor: int = 1,         # accepted for call compatibility; unused
        white_padding: int = 0,        # accepted for call compatibility; unused
        horizontal_inset: int = 4,
        extra_amounts: int = 0,
        apply_gate: bool = True,
    ) -> tuple[CellOCRVariantResult, ...]:
        """Read numeric cells (totals, quantities, payable) of one invoice image."""
        self.last_glyph_readings = ()
        image = Path(image_path)
        if not image.is_file():
            raise OCRExecutionError(f"image file is missing or not regular: {image}")
        if (isinstance(minimum_confidence, bool)
                or not isinstance(minimum_confidence, (int, float))
                or not 0 <= float(minimum_confidence) <= 100):
            raise ValueError("minimum_confidence must be a number from 0 to 100")
        try:
            from PIL import Image
        except Exception as exc:
            raise OCREngineUnavailable("Pillow is required for glyph OCR") from exc
        try:
            with Image.open(image) as opened:
                opened.load()
                source = opened.convert("RGB")
            crops = crop_spatial_cells(
                source, spatial, include_descriptions=False,
                horizontal_inset=horizontal_inset)
            triples = self._recognize_crops(crops, spatial, float(minimum_confidence))
            self.last_glyph_readings = tuple(
                (crop.field_name, reading) for crop, _, reading in triples)
        except (OCRExecutionError, OCREngineUnavailable):
            raise
        except Exception as exc:
            raise OCRExecutionError(
                f"glyph classifier failed on {image.name}: {exc}") from exc
        results = tuple(result for _, result, _ in triples)
        if apply_gate:
            results, _ = apply_arithmetic_gate(results, extra_amounts=extra_amounts)
        return results


# --------------------------------------------------------------------------
# Command line: build templates / evaluate against confirmed labels
# --------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_entries(labels_path: Path) -> list[dict]:
    data = json.loads(Path(labels_path).read_bytes().decode("utf-8"))
    entries = data.get("images")
    if not isinstance(entries, list) or not entries:
        raise ValueError("label file needs a non-empty 'images' list")
    return entries


def _spatial_from_entry(entry: dict) -> SimpleNamespace:
    assessments = ()
    if entry.get("payable_bbox"):
        assessments = (SimpleNamespace(
            field_name=PAYABLE_FIELD, bbox=tuple(entry["payable_bbox"]),
            status=None),)
    return SimpleNamespace(
        # Image-projection geometry is primary; these optional values are only
        # a compatibility fallback for images the dynamic detector cannot parse.
        column_boundaries=tuple(entry.get("column_boundaries", ())),
        row_bands=tuple(tuple(band) for band in entry.get("row_bands", ())),
        assessments=assessments)


def _crops_for_entry(entry: dict) -> tuple[Any, Any]:
    from PIL import Image
    with Image.open(entry["path"]) as opened:
        opened.load()
        source = opened.convert("RGB")
    spatial = _spatial_from_entry(entry)
    return spatial, crop_spatial_cells(
        source, spatial, include_descriptions=False,
        horizontal_inset=int(entry.get("horizontal_inset", 4)))


def _edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _digits_only(text: str) -> str:
    return "".join(ch for ch in text if ch in _PERSIAN_DIGITS)


def _cmd_build(args: argparse.Namespace) -> int:
    templates = GlyphTemplateSet()
    for entry in _load_entries(Path(args.labels)):
        spatial, crops = _crops_for_entry(entry)
        values = entry.get("values", {})
        labelled = [LabeledCell(c.field_name, c.image, values[c.field_name])
                    for c in crops if c.field_name in values]
        _, report = build_templates(labelled, templates)
        templates.provenance.append({
            "image": entry["path"], "sha256": _sha256(Path(entry["path"]))})
        print(f"== {entry['path']}")
        for line in report:
            print("  " + line)
    templates.save(Path(args.out))
    for profile, tally in templates.counts().items():
        print(f"profile {profile}: " + " ".join(
            f"{label}x{n}" for label, n in sorted(tally.items())))
    missing = [s for s in GLYPH_ALPHABET
               if s not in templates.counts().get(PROFILE_ROW, {})]
    if missing:
        print("WARNING: row profile has no template for: " + " ".join(missing))
    print(f"saved {args.out}")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    templates = GlyphTemplateSet.load(Path(args.templates))
    engine = GlyphClassifierOCR(
        templates, max_distance=args.max_distance, min_margin=args.min_margin)
    built_from = {item.get("sha256") for item in templates.provenance}
    exact = total_cells = edits = ref_digits = seg_mismatch = 0
    correct_d: list[float] = []
    correct_m: list[float] = []
    wrong_d: list[float] = []
    wrong_m: list[float] = []
    leakage = False
    gates_passed = gates_total = 0

    for entry in _load_entries(Path(args.labels)):
        path = Path(entry["path"])
        if _sha256(path) in built_from:
            leakage = True
            print(f"LEAKAGE: {path} was used to build these templates; "
                  "its scores are not valid evidence")
        spatial, crops = _crops_for_entry(entry)
        values = {k: normalize_label_text(v)
                  for k, v in entry.get("values", {}).items()}
        triples = engine._recognize_crops(crops, spatial, args.minimum_confidence)
        results, gate = apply_arithmetic_gate(
            [r for _, r, _ in triples], extra_amounts=args.extra_amounts)
        gates_total += 1
        gates_passed += gate.passed
        print(f"== {path}")
        for (crop, _, reading), result in zip(triples, results):
            reference = values.get(crop.field_name)
            line = (f"  {result.field_name}|{PREPROCESSING_LABEL}|raw={result.raw_value!r}"
                    f"|confidence={result.confidence:.1f}|status={result.status}")
            if reference is not None:
                total_cells += 1
                match = _digits_only(result.raw_value) == _digits_only(reference) \
                    and "?" not in result.raw_value
                exact += match
                edits += _edit_distance(_digits_only(result.raw_value),
                                        _digits_only(reference))
                ref_digits += len(_digits_only(reference))
                line += f"|reference={reference!r}|digits_match_reference={match}"
                if len(reading.readings) == len(reference):
                    for glyph, symbol in zip(reading.readings, reference):
                        (correct_d if glyph.best_label == symbol else wrong_d
                         ).append(glyph.distance)
                        (correct_m if glyph.best_label == symbol else wrong_m
                         ).append(glyph.margin)
                else:
                    seg_mismatch += 1
            if result.reason:
                line += f"|reason={result.reason!r}"
            print(line)
        print(f"  arithmetic_gate passed={gate.passed} line_sum={gate.line_sum} "
              f"payable={gate.payable} extra={gate.extra_amounts} reason={gate.reason}")

    print("metric.definition=exact match and CER on digit strings; separators ignored for scoring only")
    print(f"metrics.glyph.exact_digit_cells={exact}/{total_cells} "
          f"digit_CER={(100.0 * edits / ref_digits) if ref_digits else 0.0:.2f}%")
    print(f"metrics.glyph.segmentation_mismatch_cells={seg_mismatch}")
    print(f"metrics.glyph.arithmetic_gate_passed={gates_passed}/{gates_total}")

    def span(values: list[float]) -> str:
        return (f"n={len(values)} min={min(values):.3f} max={max(values):.3f}"
                if values else "n=0")
    print("calibration.best_label_correct.distance " + span(correct_d))
    print("calibration.best_label_correct.margin   " + span(correct_m))
    print("calibration.best_label_wrong.distance   " + span(wrong_d))
    print("calibration.best_label_wrong.margin   " + span(wrong_m))
    if leakage and not args.allow_leakage:
        print("EXIT 3: evaluation used images that built the templates")
        return 3
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Glyph-template engine for Holo numeric cells")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build templates from confirmed labels")
    build.add_argument("--labels", required=True)
    build.add_argument("--out", required=True)
    build.set_defaults(func=_cmd_build)

    evaluate = sub.add_parser("evaluate", help="score the engine on confirmed labels")
    evaluate.add_argument("--labels", required=True)
    evaluate.add_argument("--templates", required=True)
    evaluate.add_argument("--minimum-confidence", type=float, default=60.0)
    evaluate.add_argument("--max-distance", type=float, default=DEFAULT_MAX_DISTANCE)
    evaluate.add_argument("--min-margin", type=float, default=DEFAULT_MIN_MARGIN)
    evaluate.add_argument("--extra-amounts", type=int, default=0)
    evaluate.add_argument("--allow-leakage", action="store_true")
    evaluate.set_defaults(func=_cmd_evaluate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
