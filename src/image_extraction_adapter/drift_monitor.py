"""Fail-closed DR-1 glyph-distance monitoring against an onboarding baseline.

The metric is the mean distance per predicted glyph symbol over the numeric
cells of one invoice. A measured onboarding baseline is tied to its Glyph bank;
a missing, malformed, or mismatched baseline cannot silently accept an invoice.
The monitor only downgrades results and never repairs OCR text.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

DRIFT_BASELINE_SCHEMA = "e28.glyph-drift-baseline.v1"
DRIFT_REASON = "onboarding required"
# Baselines are serialized to eight decimals; tolerate only that rounding noise.
_FLOAT_TOLERANCE = 1e-8


class DriftBaselineError(ValueError):
    """Raised when a DR-1 baseline cannot be safely loaded or validated."""


def load_glyph_drift_baseline(path: str | Path) -> dict[str, Any]:
    """Load and minimally validate a versioned, local DR-1 baseline."""
    baseline_path = Path(path)
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DriftBaselineError(
            f"cannot load glyph-drift baseline {baseline_path}: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise DriftBaselineError("glyph-drift baseline root must be a JSON object")
    if data.get("schema_version") != DRIFT_BASELINE_SCHEMA:
        raise DriftBaselineError("unsupported glyph-drift baseline schema_version")
    if not isinstance(data.get("baseline_id"), str) or not data["baseline_id"].strip():
        raise DriftBaselineError("glyph-drift baseline needs a non-empty baseline_id")
    if not isinstance(data.get("template_library_id"), str) or not data["template_library_id"].strip():
        raise DriftBaselineError("glyph-drift baseline needs a non-empty template_library_id")
    symbols = data.get("symbols")
    if not isinstance(symbols, dict) or not symbols:
        raise DriftBaselineError("glyph-drift baseline needs a non-empty symbols object")
    return data


def aggregate_mean_distance_by_symbol(
    cell_readings: Iterable[tuple[str, Any]],
) -> tuple[dict[str, float], dict[str, int], tuple[str, ...]]:
    """Aggregate each ``GlyphReading.distance`` by its best/predicted symbol.

    ``cell_readings`` is the private, adapter-local diagnostic stream emitted by
    ``GlyphClassifierOCR``: ``(field_name, CellReading)`` pairs. Rejected glyphs
    are retained in the diagnostic mean so quality degradation is measurable;
    the pipeline separately downgrades all cells if DR-1 fires.
    """
    scores: dict[str, list[float]] = defaultdict(list)
    errors: list[str] = []
    for field_name, cell_reading in cell_readings:
        readings = getattr(cell_reading, "readings", None)
        if not isinstance(readings, (list, tuple)):
            errors.append(f"{field_name}: per-glyph readings are unavailable")
            continue
        for index, glyph in enumerate(readings, start=1):
            symbol = getattr(glyph, "best_label", None)
            distance = getattr(glyph, "distance", None)
            if not isinstance(symbol, str) or not symbol:
                errors.append(f"{field_name} glyph {index}: predicted symbol is unavailable")
                continue
            if (isinstance(distance, bool)
                    or not isinstance(distance, (int, float))
                    or not math.isfinite(float(distance))
                    or float(distance) < 0):
                errors.append(f"{field_name} glyph {index}: distance is missing or invalid")
                continue
            scores[symbol].append(float(distance))
    means = {
        symbol: sum(values) / len(values)
        for symbol, values in sorted(scores.items())
        if values
    }
    counts = {symbol: len(scores[symbol]) for symbol in sorted(scores) if scores[symbol]}
    return means, counts, tuple(errors)


def evaluate_glyph_drift(
    means: Mapping[str, float],
    counts: Mapping[str, int],
    *,
    template_library_id: str | None,
    baseline: Mapping[str, Any] | None,
    baseline_error: str | None = None,
    measurement_errors: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a serializable DR-1 record; any uncertainty yields REVIEW.

    The trigger is per symbol: ``abs(invoice_mean - onboarding_mean)`` must be
    strictly greater than that symbol's measured clean-control bound. Unknown
    symbols, malformed measurements, and template-bank mismatches fail closed.
    """
    reasons: list[str] = []
    baseline_id: str | None = None
    symbols: dict[str, Any] = {}
    if baseline_error:
        reasons.append(str(baseline_error))
    if baseline is None:
        reasons.append("onboarding baseline is unavailable")
    else:
        candidate_id = baseline.get("baseline_id")
        if isinstance(candidate_id, str):
            baseline_id = candidate_id
        expected_library = baseline.get("template_library_id")
        if (not isinstance(template_library_id, str)
                or not isinstance(expected_library, str)
                or template_library_id != expected_library):
            reasons.append("onboarding baseline does not match the active Glyph template bank")

    for error in measurement_errors:
        reasons.append(str(error))
    if not means:
        reasons.append("no per-symbol glyph distances were measured")

    baseline_symbols: Mapping[str, Any] = {}
    if baseline is not None:
        candidate_symbols = baseline.get("symbols")
        if isinstance(candidate_symbols, Mapping):
            baseline_symbols = candidate_symbols
        else:
            reasons.append("onboarding baseline symbol table is invalid")

    triggered: list[str] = []
    for symbol in sorted(means):
        mean = means[symbol]
        count = counts.get(symbol)
        entry = baseline_symbols.get(symbol)
        valid_entry = isinstance(entry, Mapping)
        baseline_mean = entry.get("mean_distance") if valid_entry else None
        bound = entry.get("bound") if valid_entry else None
        valid_numbers = all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and float(value) >= 0
            for value in (mean, baseline_mean, bound)
        )
        if not valid_entry or not valid_numbers:
            reasons.append(f"symbol {symbol!r} has no valid onboarding measurement")
            symbols[symbol] = {
                "mean_distance": round(float(mean), 8) if isinstance(mean, (int, float)) else None,
                "glyph_count": count if isinstance(count, int) and not isinstance(count, bool) else None,
                "baseline_mean": None,
                "bound": None,
                "absolute_delta": None,
            }
            triggered.append(symbol)
            continue

        delta = abs(float(mean) - float(baseline_mean))
        if delta > float(bound) + _FLOAT_TOLERANCE:
            triggered.append(symbol)
        symbols[symbol] = {
            "mean_distance": round(float(mean), 8),
            "glyph_count": count if isinstance(count, int) and not isinstance(count, bool) else None,
            "baseline_mean": round(float(baseline_mean), 8),
            "bound": round(float(bound), 8),
            "absolute_delta": round(delta, 8),
        }

    if triggered:
        reasons.append("per-symbol mean distance exceeded the measured clean-control bound")
    review = bool(reasons)
    return {
        "status": "REVIEW" if review else "CLEAR",
        "reason": DRIFT_REASON if review else None,
        "baseline_id": baseline_id,
        "template_library_id": template_library_id,
        "mean_distance_by_symbol": symbols,
        "triggered_symbols": sorted(set(triggered)),
        "diagnostics": list(dict.fromkeys(reasons)),
    }


__all__ = [
    "DRIFT_BASELINE_SCHEMA",
    "DRIFT_REASON",
    "DriftBaselineError",
    "aggregate_mean_distance_by_symbol",
    "evaluate_glyph_drift",
    "load_glyph_drift_baseline",
]
