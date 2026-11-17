"""Conservative multi-witness acceptance for the E-09 Glyph pipeline.

The evaluator never repairs values or tunes classifier settings. It combines
existing arithmetic/layout/classifier evidence with strict Persian digit
formatting and an explicit unknown-glyph check. Pipeline ``CellOCRVariantResult``
objects do not carry raw per-glyph scores; an EXTRACTED cell (or a REVIEW cell
with only the arithmetic-gate downgrade) is therefore treated as the existing
Glyph classifier's certificate that its configured distance and margin rules
passed. Callers/tests that have raw ``GlyphReading`` objects may attach them as
``glyph_readings`` or ``readings`` for direct numeric checks.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from .glyph_classifier import DEFAULT_MAX_DISTANCE, DEFAULT_MIN_MARGIN


MultiEvidenceStatus = Literal["AUTO_CANDIDATE", "REVIEW"]

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_UNGROUPED_PERSIAN = re.compile(r"^[۰-۹]+$")
_GROUPED_PERSIAN = re.compile(r"^[۰-۹]{1,3}(?:,[۰-۹]{3})+$")
_LINE_ITEM_FIELD = re.compile(r"^line\.(\d+)\.(quantity|total)$")
_MISSING = object()


@dataclass(frozen=True)
class MultiEvidenceResult:
    """Result of the six-witness acceptance check.

    ``witnesses`` is keyed by the stable witness names and each value contains
    ``passed`` and human-readable ``detail`` fields. ``reasons`` contains the
    names of failed witnesses in evaluation order.
    """

    witnesses: dict[str, dict[str, bool | str]]
    all_pass: bool
    status: MultiEvidenceStatus
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "witnesses": {
                name: dict(result) for name, result in self.witnesses.items()
            },
            "all_pass": self.all_pass,
            "status": self.status,
            "reasons": list(self.reasons),
        }


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _materialise_cells(cell_results: Iterable[Any] | None) -> tuple[Any, ...]:
    if cell_results is None or isinstance(cell_results, (str, bytes, Mapping)):
        return ()
    try:
        return tuple(cell_results)
    except TypeError:
        return ()


def _field_name(cell: Any, index: int) -> str:
    value = _get(cell, "field_name", _get(cell, "field"))
    return value if isinstance(value, str) and value else f"cell[{index}]"


def _raw_value(cell: Any) -> str | None:
    value = _get(cell, "raw_value", _get(cell, "value"))
    return value if isinstance(value, str) else None


def _status(cell: Any) -> str | None:
    value = _get(cell, "status")
    return value if isinstance(value, str) else None


def _thousands_pattern_witness(cells: tuple[Any, ...]) -> tuple[bool, str]:
    if not cells:
        return False, "no numeric cell values were supplied"

    failures: list[str] = []
    for index, cell in enumerate(cells):
        field = _field_name(cell, index)
        value = _raw_value(cell)
        if value is None:
            failures.append(f"{field}: missing string value")
            continue

        # Leave '?' to the dedicated no_question_mark witness so the two
        # witnesses can be diagnosed independently. All remaining characters
        # must still form a correctly grouped Persian integer.
        grouped_candidate = value.replace("?", "")
        digit_count = sum(char in _PERSIAN_DIGITS for char in grouped_candidate)
        if digit_count == 0:
            failures.append(f"{field}: no Persian digits in {value!r}")
        elif digit_count < 4:
            valid = _UNGROUPED_PERSIAN.fullmatch(grouped_candidate) is not None
            if not valid:
                failures.append(
                    f"{field}: fewer than four digits must be ungrouped; value={value!r}"
                )
        elif _GROUPED_PERSIAN.fullmatch(grouped_candidate) is None:
            failures.append(
                f"{field}: four or more digits must use 1–3 leading digits and groups "
                f"of three; value={value!r}"
            )

    if failures:
        return False, "; ".join(failures)
    return True, f"all {len(cells)} numeric cell values use Persian integer grouping"


def _extracted_line_item_count(cells: tuple[Any, ...]) -> tuple[int, int]:
    fields_by_row: dict[int, set[str]] = {}
    extracted_by_row: dict[int, set[str]] = {}
    for cell in cells:
        field_name = _get(cell, "field_name")
        if not isinstance(field_name, str):
            continue
        match = _LINE_ITEM_FIELD.fullmatch(field_name)
        if match is None:
            continue
        row = int(match.group(1))
        component = match.group(2)
        fields_by_row.setdefault(row, set()).add(component)
        if _status(cell) == "EXTRACTED":
            extracted_by_row.setdefault(row, set()).add(component)

    complete_rows = {
        row for row, components in extracted_by_row.items()
        if {"quantity", "total"}.issubset(components)
    }
    # Keep the count tied to declared line rows even if an incomplete row was
    # present; only a complete EXTRACTED quantity+total pair is an extracted
    # line item for this witness.
    return len(complete_rows), len(fields_by_row)


def _row_count_witness(cells: tuple[Any, ...], layout_result: Any) -> tuple[bool, str]:
    row_count = _get(layout_result, "row_count")
    item_count, seen_rows = _extracted_line_item_count(cells)
    if isinstance(row_count, bool) or not isinstance(row_count, int) or row_count < 0:
        return False, f"layout row_count is unavailable or invalid: {row_count!r}"
    passed = row_count == item_count
    detail = (
        f"layout row_count={row_count}; complete EXTRACTED line items={item_count}"
        f" (line rows present={seen_rows})"
    )
    return passed, detail


def _gate_witness(gate_result: Any) -> tuple[bool, str]:
    if isinstance(gate_result, bool):
        passed = gate_result
        reason = None
    else:
        passed = _get(gate_result, "passed") is True
        reason = _get(gate_result, "reason")
    detail = "arithmetic sum gate passed" if passed else "arithmetic sum gate did not pass"
    if reason:
        detail += f": {reason}"
    return passed, detail


def _question_mark_witness(cells: tuple[Any, ...]) -> tuple[bool, str]:
    if not cells:
        return False, "no numeric cell values were supplied"
    unknown: list[str] = []
    missing: list[str] = []
    for index, cell in enumerate(cells):
        field = _field_name(cell, index)
        value = _raw_value(cell)
        if value is None:
            missing.append(field)
        elif "?" in value:
            unknown.append(f"{field}={value!r}")
    if unknown or missing:
        details = []
        if unknown:
            details.append("question mark found in " + ", ".join(unknown))
        if missing:
            details.append("missing value for " + ", ".join(missing))
        return False, "; ".join(details)
    return True, f"no question marks in {len(cells)} numeric cell values"


def _explicit_glyph_readings(cell: Any) -> tuple[tuple[Any, ...], bool]:
    for name in ("glyph_readings", "readings"):
        value = _get(cell, name, _MISSING)
        if value is _MISSING or value is None:
            continue
        if isinstance(value, Mapping):
            return (value,), True
        if isinstance(value, (str, bytes)):
            return (), True
        try:
            return tuple(value), True
        except TypeError:
            return (value,), True

    # Also accept parallel score sequences or scalar score fields for light
    # integrations/tests that do not construct GlyphReading objects.
    distances = _get(cell, "glyph_distances", _get(cell, "distances", _MISSING))
    margins = _get(cell, "glyph_margins", _get(cell, "margins", _MISSING))
    if distances is not _MISSING or margins is not _MISSING:
        def as_tuple(value: Any) -> tuple[Any, ...]:
            if value is _MISSING:
                return ()
            if isinstance(value, (str, bytes, Mapping)):
                return (value,)
            try:
                return tuple(value)
            except TypeError:
                return (value,)

        distance_values = as_tuple(distances)
        margin_values = as_tuple(margins)
        count = max(len(distance_values), len(margin_values))
        return tuple(
            {
                "distance": distance_values[index] if index < len(distance_values) else None,
                "margin": margin_values[index] if index < len(margin_values) else None,
            }
            for index in range(count)
        ), True

    distance = _get(cell, "distance", _get(cell, "glyph_distance", _MISSING))
    margin = _get(cell, "margin", _get(cell, "glyph_margin", _MISSING))
    if distance is not _MISSING or margin is not _MISSING:
        return ({"distance": distance, "margin": margin},), True
    return (), False


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _gate_only_review(reason: Any) -> bool:
    if not isinstance(reason, str) or not reason.strip():
        return False
    parts = [part.strip().lower() for part in reason.split(";") if part.strip()]
    return bool(parts) and all(part.startswith("arithmetic gate failed:") for part in parts)


def _glyph_threshold_witness(
    cells: tuple[Any, ...], *, metric: Literal["distance", "margin"]
) -> tuple[bool, str]:
    if not cells:
        return False, "no numeric cells were supplied"

    failures: list[str] = []
    explicit_scores = 0
    certified_cells = 0
    for index, cell in enumerate(cells):
        field = _field_name(cell, index)
        status = _status(cell)
        reason = _get(cell, "reason")
        gate_only_review = status == "REVIEW" and _gate_only_review(reason)
        status_failure = None
        if status == "REVIEW" and not gate_only_review:
            status_failure = (
                f"{field}: cell status REVIEW does not satisfy the existing all-EXTRACTED gate"
            )
        elif status not in (None, "EXTRACTED", "REVIEW"):
            status_failure = f"{field}: unsupported cell status {status!r}"

        readings, explicit = _explicit_glyph_readings(cell)
        if explicit:
            if not readings:
                failures.append(f"{field}: explicit glyph readings are empty")
                if status_failure:
                    failures.append(status_failure)
                continue
            for glyph_index, reading in enumerate(readings, start=1):
                score = _get(reading, metric, _MISSING)
                if not _is_finite_number(score):
                    failures.append(
                        f"{field} glyph {glyph_index}: {metric} score is missing or invalid"
                    )
                    continue
                explicit_scores += 1
                if metric == "distance" and score > DEFAULT_MAX_DISTANCE:
                    failures.append(
                        f"{field} glyph {glyph_index}: distance {score:.3f} exceeds "
                        f"{DEFAULT_MAX_DISTANCE:.3f}"
                    )
                elif metric == "margin" and score < DEFAULT_MIN_MARGIN:
                    failures.append(
                        f"{field} glyph {glyph_index}: margin {score:.3f} is below "
                        f"{DEFAULT_MIN_MARGIN:.3f}"
                    )
            if status_failure:
                failures.append(status_failure)
            continue

        # PipelineResult deliberately exposes CellOCRVariantResult summaries,
        # not GlyphReading floats. EXTRACTED is emitted only after the existing
        # classifier's distance/margin checks pass. A gate-only downgrade is
        # also known to have started from an EXTRACTED cell.
        status = _status(cell)
        if status == "EXTRACTED" or (
            status == "REVIEW" and _gate_only_review(_get(cell, "reason"))
        ):
            certified_cells += 1
            continue

        reason = _get(cell, "reason")
        detail = (
            f"{field}: no explicit per-glyph {metric} scores and status "
            f"{status!r} does not certify threshold acceptance"
        )
        if reason:
            detail += f" (reason={reason})"
        failures.append(detail)

    if failures:
        return False, "; ".join(failures)
    detail_parts = []
    if explicit_scores:
        detail_parts.append(
            f"checked {explicit_scores} explicit glyph {metric} scores"
        )
    if certified_cells:
        detail_parts.append(
            f"{certified_cells} cells carry the existing Glyph acceptance certificate"
        )
    if metric == "distance":
        detail_parts.append(f"all distances <= {DEFAULT_MAX_DISTANCE:.3f}")
    else:
        detail_parts.append(f"all margins >= {DEFAULT_MIN_MARGIN:.3f}")
    return True, "; ".join(detail_parts)


def evaluate_multi_evidence(
    cell_results: Iterable[Any],
    gate_result: Any,
    layout_result: Any,
) -> MultiEvidenceResult:
    """Evaluate the six independent/orthogonal acceptance witnesses.

    ``cell_results`` normally contains ``CellOCRVariantResult`` objects;
    test/integration callers with per-glyph measurements may provide cells with
    ``glyph_readings`` or ``readings`` sequences containing ``distance`` and
    ``margin`` values. ``layout_result`` must expose ``row_count`` (for example,
    the E-09 ``PipelineResult`` or ``LayoutSafetyResult``).
    """
    cells = _materialise_cells(cell_results)
    sum_passed, sum_detail = _gate_witness(gate_result)
    pattern_passed, pattern_detail = _thousands_pattern_witness(cells)
    row_passed, row_detail = _row_count_witness(cells, layout_result)
    distance_passed, distance_detail = _glyph_threshold_witness(
        cells, metric="distance")
    margin_passed, margin_detail = _glyph_threshold_witness(
        cells, metric="margin")
    question_passed, question_detail = _question_mark_witness(cells)

    witnesses: dict[str, dict[str, bool | str]] = {
        "sum_gate": {"passed": sum_passed, "detail": sum_detail},
        "thousands_pattern": {"passed": pattern_passed, "detail": pattern_detail},
        "row_count": {"passed": row_passed, "detail": row_detail},
        "glyph_distance": {"passed": distance_passed, "detail": distance_detail},
        "glyph_margin": {"passed": margin_passed, "detail": margin_detail},
        "no_question_mark": {"passed": question_passed, "detail": question_detail},
    }
    all_pass = all(result["passed"] is True for result in witnesses.values())
    reasons = [
        name for name, result in witnesses.items()
        if result["passed"] is not True
    ]
    return MultiEvidenceResult(
        witnesses=witnesses,
        all_pass=all_pass,
        status="AUTO_CANDIDATE" if all_pass else "REVIEW",
        reasons=reasons,
    )


__all__ = ["MultiEvidenceResult", "evaluate_multi_evidence"]
