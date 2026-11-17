"""Transparent confidence scoring for E-05 layout-template matches.

This module scores caller-provided layout measurements and raw OCR formatting.
It neither extracts data from images nor promotes an invoice to a workflow state.
"""
from __future__ import annotations

from collections.abc import Mapping

from .template import LayoutObservation, LayoutTemplate, TemplateMatch


CONFIDENCE_WEIGHTS: dict[str, float] = {
    "columns": 0.24,
    "row_count": 0.18,
    "row_rhythm": 0.18,
    "table_anchor": 0.11,
    "payable_anchor": 0.11,
    "numeric_format": 0.18,
}

# Tolerances are in normalized image-width units, except row-height CV, which
# is unitless. Scores are linear within each tolerance and clamp at zero.
COLUMN_MEAN_ABS_TOLERANCE = 0.025
ROW_HEIGHT_TOLERANCE = 0.04
ROW_PITCH_TOLERANCE = 0.04
ROW_HEIGHT_CV_TOLERANCE = 0.05
TABLE_TOP_TOLERANCE = 0.06
PAYABLE_GAP_TOLERANCE = 0.04
PAYABLE_LEFT_TOLERANCE = 0.08
PAYABLE_WIDTH_TOLERANCE = 0.12
PAYABLE_HEIGHT_TOLERANCE = 0.05


def _distance_score(delta: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 1.0 if delta == 0 else 0.0
    return max(0.0, min(1.0, 1.0 - abs(delta) / tolerance))


def _numeric_role(field_name: str) -> str | None:
    if field_name == "invoice.payable":
        return "amount"
    if field_name.endswith(".quantity"):
        return "quantity"
    if field_name.endswith(".total"):
        return "amount"
    return None


def _matches_numeric_pattern(
    text: str,
    *,
    role: str,
    digit_alphabet: tuple[str, ...],
    separator: str | None,
    group_size: int,
) -> bool:
    value = text.strip()
    if not value:
        return False
    allowed_digits = set(digit_alphabet)
    if role == "quantity":
        return all(character in allowed_digits for character in value)

    if separator is None:
        return bool(value) and all(character in allowed_digits for character in value)
    if any(character != separator and character not in allowed_digits for character in value):
        return False
    groups = value.split(separator)
    if any(not group for group in groups):
        return False
    if len(groups) == 1:
        # The learned format uses grouping for amounts of four digits or more.
        return len(groups[0]) <= group_size
    return (
        1 <= len(groups[0]) <= group_size
        and all(len(group) == group_size for group in groups[1:])
    )


def _numeric_format_score(
    observation: LayoutObservation,
    template: LayoutTemplate,
) -> tuple[float | None, bool, tuple[str, ...]]:
    """Return score, whether data were supplied, and field-level diagnostics."""
    role_values: dict[str, list[tuple[str, str]]] = {
        "quantity": [],
        "amount": [],
    }
    for field_name, raw_text in observation.field_values:
        role = _numeric_role(field_name)
        if role is not None:
            role_values[role].append((field_name, raw_text))

    if not role_values["quantity"] and not role_values["amount"]:
        return None, False, ()

    problems: list[str] = []
    if not role_values["quantity"]:
        problems.append("quantity values are missing")
    if not any(name == "invoice.payable" for name, _ in role_values["amount"]):
        problems.append("payable value is missing")
    if not any(name.endswith(".total") for name, _ in role_values["amount"]):
        problems.append("line-total values are missing")

    for field_name, raw_text in (*role_values["quantity"], *role_values["amount"]):
        role = _numeric_role(field_name)
        assert role is not None
        if not _matches_numeric_pattern(
            raw_text,
            role=role,
            digit_alphabet=template.digit_alphabet,
            separator=template.amount_thousands_separator,
            group_size=template.amount_group_size,
        ):
            problems.append(f"{field_name} does not match the learned numeric format")

    return (0.0 if problems else 1.0), True, tuple(dict.fromkeys(problems))


def score_template(
    template: LayoutTemplate,
    observation: LayoutObservation,
    *,
    threshold: float = 0.85,
) -> TemplateMatch:
    """Score one observation against one template and return an explainable result."""
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")

    column_deltas = tuple(
        abs(observed - expected)
        for observed, expected in zip(
            observation.normalized_column_boundaries,
            template.normalized_column_boundaries,
        )
    )
    if len(column_deltas) != len(template.normalized_column_boundaries):
        columns_score = 0.0
    else:
        mean_delta = sum(column_deltas) / len(column_deltas)
        columns_score = _distance_score(mean_delta, COLUMN_MEAN_ABS_TOLERANCE)

    row_count_score = (
        1.0
        if template.row_count_min <= observation.row_count <= template.row_count_max
        else 0.0
    )
    row_height_score = _distance_score(
        observation.row_height_over_width - template.median_row_height_over_width,
        ROW_HEIGHT_TOLERANCE,
    )
    row_pitch_score = _distance_score(
        observation.row_pitch_over_width - template.median_row_pitch_over_width,
        ROW_PITCH_TOLERANCE,
    )
    row_cv_score = _distance_score(
        observation.row_height_cv - template.median_row_height_cv,
        ROW_HEIGHT_CV_TOLERANCE,
    )
    row_rhythm_score = (row_height_score + row_pitch_score + row_cv_score) / 3

    table_anchor_score = _distance_score(
        observation.table_top_over_width - template.table_top_over_width,
        TABLE_TOP_TOLERANCE,
    )
    observed_payable_x, _, observed_payable_width, observed_payable_height = (
        observation.payable_bbox_over_width
    )
    payable_anchor_score = sum(
        (
            _distance_score(
                observation.payable_gap_over_width - template.payable_gap_over_width,
                PAYABLE_GAP_TOLERANCE,
            ),
            _distance_score(
                observed_payable_x - template.payable_bbox_left_over_width,
                PAYABLE_LEFT_TOLERANCE,
            ),
            _distance_score(
                observed_payable_width - template.payable_bbox_width_over_width,
                PAYABLE_WIDTH_TOLERANCE,
            ),
            _distance_score(
                observed_payable_height - template.payable_bbox_height_over_width,
                PAYABLE_HEIGHT_TOLERANCE,
            ),
        )
    ) / 4

    numeric_score, numeric_evidence_present, numeric_problems = _numeric_format_score(
        observation, template
    )
    components: dict[str, float] = {
        "columns": columns_score,
        "row_count": row_count_score,
        "row_rhythm": row_rhythm_score,
        "table_anchor": table_anchor_score,
        "payable_anchor": payable_anchor_score,
    }
    if numeric_score is not None:
        components["numeric_format"] = numeric_score

    active_weight = sum(CONFIDENCE_WEIGHTS[name] for name in components)
    confidence = sum(
        CONFIDENCE_WEIGHTS[name] * value for name, value in components.items()
    ) / active_weight

    reasons: list[str] = []
    if row_count_score == 0:
        reasons.append(
            f"row count {observation.row_count} is outside the learned range "
            f"{template.row_count_min}–{template.row_count_max}"
        )
    if columns_score < 0.8:
        reasons.append("column geometry differs from the learned layout")
    if row_rhythm_score < 0.8:
        reasons.append("row height or pitch differs from the learned rhythm")
    if table_anchor_score < 0.8:
        reasons.append("table top anchor differs from the learned layout")
    if payable_anchor_score < 0.8:
        reasons.append("payable position or box dimensions differ from the learned layout")
    if not numeric_evidence_present:
        reasons.append("no raw numeric values supplied; numeric formatting was not evaluated")
    elif numeric_problems:
        reasons.extend(numeric_problems)
    if not reasons:
        reasons.append("all supplied layout and numeric-format evidence is consistent")

    hard_failure = (
        row_count_score == 0
        or columns_score == 0
        or bool(numeric_problems)
    )
    matched = confidence >= threshold and not hard_failure
    return TemplateMatch(
        template_id=template.template_id,
        confidence_score=confidence,
        matched=matched,
        source_invoice_ids=template.source_invoice_ids,
        components=tuple(sorted(components.items())),
        reasons=tuple(reasons),
        numeric_evidence_present=numeric_evidence_present,
    )


def score_bank(
    templates: tuple[LayoutTemplate, ...],
    observation: LayoutObservation,
    *,
    threshold: float = 0.85,
) -> tuple[TemplateMatch, ...]:
    """Return one score per template, ordered from strongest to weakest."""
    scored = tuple(
        score_template(template, observation, threshold=threshold)
        for template in templates
    )
    return tuple(sorted(scored, key=lambda match: match.confidence_score, reverse=True))


def score_components_as_mapping(match: TemplateMatch) -> Mapping[str, float]:
    """Small convenience for callers that want named score components."""
    return dict(match.components)
