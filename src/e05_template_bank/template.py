"""Immutable value objects used by the E-05 invoice layout template bank.

The bank stores normalized spatial measurements and observed numeric formatting;
it does not contain OCR, image, or invoice-issuance behavior.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from statistics import median
from typing import Any


def _finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


@dataclass(frozen=True)
class LayoutObservation:
    """One caller-supplied invoice layout and optional raw OCR value sample.

    Coordinates use image pixels. ``field_values`` preserves the raw visible
    text (for example Persian digits and comma grouping); numeric values are
    never parsed or changed by this value object.
    """

    source_id: str
    image_width: int
    image_height: int
    column_boundaries: tuple[float, ...]
    row_bands: tuple[tuple[float, float], ...]
    payable_bbox: tuple[float, float, float, float]
    field_values: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id must be a non-empty string")
        if type(self.image_width) is not int or self.image_width <= 0:
            raise ValueError("image_width must be a positive integer")
        if type(self.image_height) is not int or self.image_height <= 0:
            raise ValueError("image_height must be a positive integer")

        columns = tuple(
            _finite_number(value, f"column_boundaries[{index}]")
            for index, value in enumerate(self.column_boundaries)
        )
        if len(columns) != 5:
            raise ValueError("column_boundaries must contain exactly five values")
        if any(value < 0 or value > self.image_width for value in columns):
            raise ValueError("column_boundaries must lie within the image width")
        if any(right <= left for left, right in zip(columns, columns[1:])):
            raise ValueError("column_boundaries must be strictly increasing")
        object.__setattr__(self, "column_boundaries", columns)

        try:
            bands = tuple(
                (
                    _finite_number(band[0], f"row_bands[{index}].top"),
                    _finite_number(band[1], f"row_bands[{index}].bottom"),
                )
                for index, band in enumerate(self.row_bands)
            )
        except (IndexError, TypeError) as exc:
            raise ValueError("row_bands must contain (top, bottom) pairs") from exc
        if not bands:
            raise ValueError("row_bands must contain at least one item row")
        previous_bottom = 0.0
        for index, (top, bottom) in enumerate(bands):
            if top < 0 or bottom <= top or bottom > self.image_height:
                raise ValueError(f"row_bands[{index}] has invalid image bounds")
            if index and top < previous_bottom:
                raise ValueError("row_bands must be ordered and must not overlap")
            previous_bottom = bottom
        object.__setattr__(self, "row_bands", bands)

        bbox = tuple(
            _finite_number(value, f"payable_bbox[{index}]")
            for index, value in enumerate(self.payable_bbox)
        )
        if len(bbox) != 4:
            raise ValueError("payable_bbox must be (x, y, width, height)")
        x, y, width, height = bbox
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ValueError("payable_bbox has invalid dimensions")
        if x + width > self.image_width or y + height > self.image_height:
            raise ValueError("payable_bbox must lie within the image")
        object.__setattr__(self, "payable_bbox", bbox)

        if isinstance(self.field_values, Mapping):
            pairs = tuple(sorted((str(key), str(value)) for key, value in self.field_values.items()))
        else:
            try:
                pairs = tuple(sorted((str(key), str(value)) for key, value in self.field_values))
            except (TypeError, ValueError) as exc:
                raise ValueError("field_values must be a mapping or key/value pairs") from exc
        if any(not key for key, _ in pairs):
            raise ValueError("field_values keys must be non-empty strings")
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError("field_values keys must be unique")
        object.__setattr__(self, "field_values", pairs)

    @property
    def row_count(self) -> int:
        return len(self.row_bands)

    @property
    def normalized_column_boundaries(self) -> tuple[float, ...]:
        return tuple(value / self.image_width for value in self.column_boundaries)

    @property
    def row_heights(self) -> tuple[float, ...]:
        return tuple(bottom - top for top, bottom in self.row_bands)

    @property
    def median_row_height(self) -> float:
        return float(median(self.row_heights))

    @property
    def row_height_over_width(self) -> float:
        return self.median_row_height / self.image_width

    @property
    def row_pitch_over_width(self) -> float:
        if self.row_count < 2:
            return self.row_height_over_width
        centers = tuple((top + bottom) / 2 for top, bottom in self.row_bands)
        pitches = tuple(right - left for left, right in zip(centers, centers[1:]))
        return float(median(pitches)) / self.image_width

    @property
    def row_height_cv(self) -> float:
        mean_height = sum(self.row_heights) / self.row_count
        if mean_height == 0:
            return 0.0
        variance = sum((height - mean_height) ** 2 for height in self.row_heights) / self.row_count
        return math.sqrt(variance) / mean_height

    @property
    def table_top_over_width(self) -> float:
        return self.row_bands[0][0] / self.image_width

    @property
    def payable_gap_over_width(self) -> float:
        return (self.payable_bbox[1] - self.row_bands[-1][1]) / self.image_width

    @property
    def payable_bbox_over_width(self) -> tuple[float, float, float, float]:
        x, y, width, height = self.payable_bbox
        return (
            x / self.image_width,
            y / self.image_width,
            width / self.image_width,
            height / self.image_width,
        )

    def values_as_dict(self) -> dict[str, str]:
        return dict(self.field_values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "column_boundaries": list(self.column_boundaries),
            "row_bands": [list(band) for band in self.row_bands],
            "payable_bbox": list(self.payable_bbox),
            "field_values": dict(self.field_values),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LayoutObservation":
        return cls(
            source_id=value["source_id"],
            image_width=value["image_width"],
            image_height=value["image_height"],
            column_boundaries=tuple(value["column_boundaries"]),
            row_bands=tuple(tuple(band) for band in value["row_bands"]),
            payable_bbox=tuple(value["payable_bbox"]),
            field_values=value.get("field_values", {}),
        )


@dataclass(frozen=True)
class FieldPosition:
    """Normalized field coordinates retained in a reusable layout template.

    Row-cell y coordinates are fractions of the row band. A payable y
    coordinate is measured in image-width units from the page top.
    """

    field_name: str
    x_start: float
    x_end: float
    y_start: float
    y_end: float
    y_reference: str

    def __post_init__(self) -> None:
        if not self.field_name:
            raise ValueError("field_name must be non-empty")
        for name in ("x_start", "x_end", "y_start", "y_end"):
            object.__setattr__(self, name, _finite_number(getattr(self, name), name))
        if not (0 <= self.x_start < self.x_end <= 1):
            raise ValueError("field x coordinates must satisfy 0 <= start < end <= 1")
        if not self.y_start < self.y_end:
            raise ValueError("field y coordinates must satisfy start < end")
        if self.y_reference == "row_fraction":
            if self.y_start < 0 or self.y_end > 1:
                raise ValueError("row-relative y coordinates must lie in [0, 1]")
        elif self.y_reference == "page_over_width":
            if self.y_start < 0:
                raise ValueError("page-relative y coordinates must be non-negative")
        else:
            raise ValueError("y_reference must be row_fraction or page_over_width")

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "x_start": self.x_start,
            "x_end": self.x_end,
            "y_start": self.y_start,
            "y_end": self.y_end,
            "y_reference": self.y_reference,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FieldPosition":
        return cls(
            field_name=value["field_name"],
            x_start=value["x_start"],
            x_end=value["x_end"],
            y_start=value["y_start"],
            y_end=value["y_end"],
            y_reference=value["y_reference"],
        )


@dataclass(frozen=True)
class LayoutTemplate:
    """Aggregate spatial and numeric-format profile for one layout cluster."""

    template_id: str
    source_invoice_ids: tuple[str, ...]
    row_count_min: int
    row_count_max: int
    known_row_counts: tuple[int, ...]
    normalized_column_boundaries: tuple[float, ...]
    median_row_height_over_width: float
    median_row_pitch_over_width: float
    median_row_height_cv: float
    table_top_over_width: float
    payable_gap_over_width: float
    payable_bbox_left_over_width: float
    payable_bbox_width_over_width: float
    payable_bbox_height_over_width: float
    field_positions: tuple[FieldPosition, ...]
    digit_alphabet: tuple[str, ...]
    amount_thousands_separator: str | None
    amount_group_size: int

    def __post_init__(self) -> None:
        if not self.template_id:
            raise ValueError("template_id must be non-empty")
        if not self.source_invoice_ids:
            raise ValueError("a layout template must retain at least one source id")
        if self.row_count_min <= 0 or self.row_count_max < self.row_count_min:
            raise ValueError("row-count range is invalid")
        if len(self.normalized_column_boundaries) != 5:
            raise ValueError("normalized_column_boundaries must contain five values")
        if any(
            not math.isfinite(float(value))
            for value in self.normalized_column_boundaries
        ):
            raise ValueError("normalized column boundaries must be finite")
        if any(
            right <= left
            for left, right in zip(
                self.normalized_column_boundaries,
                self.normalized_column_boundaries[1:],
            )
        ):
            raise ValueError("normalized column boundaries must be increasing")
        if self.amount_group_size <= 0:
            raise ValueError("amount_group_size must be positive")
        if self.amount_thousands_separator is not None and len(self.amount_thousands_separator) != 1:
            raise ValueError("amount_thousands_separator must be one character or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "source_invoice_ids": list(self.source_invoice_ids),
            "row_count_min": self.row_count_min,
            "row_count_max": self.row_count_max,
            "known_row_counts": list(self.known_row_counts),
            "normalized_column_boundaries": list(self.normalized_column_boundaries),
            "median_row_height_over_width": self.median_row_height_over_width,
            "median_row_pitch_over_width": self.median_row_pitch_over_width,
            "median_row_height_cv": self.median_row_height_cv,
            "table_top_over_width": self.table_top_over_width,
            "payable_gap_over_width": self.payable_gap_over_width,
            "payable_bbox_left_over_width": self.payable_bbox_left_over_width,
            "payable_bbox_width_over_width": self.payable_bbox_width_over_width,
            "payable_bbox_height_over_width": self.payable_bbox_height_over_width,
            "field_positions": [position.to_dict() for position in self.field_positions],
            "digit_alphabet": list(self.digit_alphabet),
            "amount_thousands_separator": self.amount_thousands_separator,
            "amount_group_size": self.amount_group_size,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LayoutTemplate":
        return cls(
            template_id=value["template_id"],
            source_invoice_ids=tuple(value["source_invoice_ids"]),
            row_count_min=int(value["row_count_min"]),
            row_count_max=int(value["row_count_max"]),
            known_row_counts=tuple(int(item) for item in value["known_row_counts"]),
            normalized_column_boundaries=tuple(value["normalized_column_boundaries"]),
            median_row_height_over_width=float(value["median_row_height_over_width"]),
            median_row_pitch_over_width=float(value["median_row_pitch_over_width"]),
            median_row_height_cv=float(value["median_row_height_cv"]),
            table_top_over_width=float(value["table_top_over_width"]),
            payable_gap_over_width=float(value["payable_gap_over_width"]),
            payable_bbox_left_over_width=float(value["payable_bbox_left_over_width"]),
            payable_bbox_width_over_width=float(value["payable_bbox_width_over_width"]),
            payable_bbox_height_over_width=float(value["payable_bbox_height_over_width"]),
            field_positions=tuple(
                FieldPosition.from_dict(item) for item in value["field_positions"]
            ),
            digit_alphabet=tuple(value["digit_alphabet"]),
            amount_thousands_separator=value.get("amount_thousands_separator"),
            amount_group_size=int(value["amount_group_size"]),
        )


@dataclass(frozen=True)
class TemplateBank:
    """Serializable layout policy with an explicit, fail-closed currency setting.

    ``currency_unit`` is onboarding metadata, not a conversion instruction.
    E-06 accepts only ``"rial"`` or ``"toman"``; missing or unsupported values
    are retained on load so the verdict layer can route the candidate to REVIEW.
    """

    templates: tuple[LayoutTemplate, ...]
    confidence_threshold: float = 0.85
    algorithm_version: str = "e05-template-bank-v1"
    currency_unit: str | None = None

    def __post_init__(self) -> None:
        if not self.templates:
            raise ValueError("template bank must contain at least one template")
        threshold = _finite_number(self.confidence_threshold, "confidence_threshold")
        if not 0 < threshold <= 1:
            raise ValueError("confidence_threshold must be in (0, 1]")
        object.__setattr__(self, "confidence_threshold", threshold)
        if not self.algorithm_version:
            raise ValueError("algorithm_version must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm_version": self.algorithm_version,
            "confidence_threshold": self.confidence_threshold,
            "currency_unit": self.currency_unit,
            "templates": [template.to_dict() for template in self.templates],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TemplateBank":
        return cls(
            algorithm_version=value["algorithm_version"],
            confidence_threshold=float(value["confidence_threshold"]),
            templates=tuple(
                LayoutTemplate.from_dict(item) for item in value["templates"]
            ),
            currency_unit=value.get("currency_unit"),
        )


@dataclass(frozen=True)
class TemplateMatch:
    """Best template match plus transparent component scores and reasons."""

    template_id: str
    confidence_score: float
    matched: bool
    source_invoice_ids: tuple[str, ...]
    components: tuple[tuple[str, float], ...]
    reasons: tuple[str, ...]
    numeric_evidence_present: bool

    @property
    def component_scores(self) -> dict[str, float]:
        return dict(self.components)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "confidence_score": self.confidence_score,
            "matched": self.matched,
            "source_invoice_ids": list(self.source_invoice_ids),
            "components": dict(self.components),
            "reasons": list(self.reasons),
            "numeric_evidence_present": self.numeric_evidence_present,
        }
