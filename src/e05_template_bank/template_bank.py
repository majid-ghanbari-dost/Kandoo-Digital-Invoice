"""Build, persist, and query E-05 geometry/numeric-format template banks.

Training data are label/canonical pairs. This module validates provenance and
uses only the provided layout measurements; it does not invoke OCR or inspect
image pixels. Runtime observations must be supplied by the calling pipeline.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics
from typing import Any

from image_extraction_adapter.canonical_invoice import validate_canonical_invoice

from .confidence import score_bank
from .template import (
    FieldPosition,
    LayoutObservation,
    LayoutTemplate,
    TemplateBank,
    TemplateMatch,
)


_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ASCII_DIGITS = "0123456789"
_DIGIT_TRANSLATION = str.maketrans(_PERSIAN_DIGITS, _ASCII_DIGITS)


def parse_labeled_integer(value: str) -> int:
    """Parse the fixture label's Persian-digit integer without rounding.

    Thousands commas are accepted only in groups of three. No signs, decimal
    fractions, whitespace inside the value, or inferred toman/rial conversion
    are accepted.
    """
    if not isinstance(value, str) or not value:
        raise ValueError("labeled numeric value must be a non-empty string")
    if any(character not in _PERSIAN_DIGITS + "," for character in value):
        raise ValueError(f"unsupported character in labeled integer {value!r}")
    if "," in value:
        groups = value.split(",")
        if not 1 <= len(groups[0]) <= 3 or any(len(group) != 3 for group in groups[1:]):
            raise ValueError(f"invalid thousands grouping in labeled integer {value!r}")
        if any(not group for group in groups):
            raise ValueError(f"empty group in labeled integer {value!r}")
    digits = value.translate(_DIGIT_TRANSLATION).replace(",", "")
    if not digits.isdigit():
        raise ValueError(f"invalid labeled integer {value!r}")
    return int(digits)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"required JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def _validate_label_canonical_pair(
    label: dict[str, Any],
    invoice: dict[str, Any],
    source_id: str,
) -> None:
    valid, errors = validate_canonical_invoice(invoice)
    if not valid:
        raise ValueError(f"canonical fixture for {source_id} is invalid: {errors}")
    if invoice.get("schema_version") != "0":
        raise ValueError(f"canonical fixture for {source_id} is not schema version 0")

    row_count = int(label["row_count"])
    line_items = invoice.get("line_items", [])
    if len(line_items) != row_count:
        raise ValueError(f"canonical fixture for {source_id} has the wrong row count")
    values = label.get("values", {})
    for index, item in enumerate(line_items):
        quantity = parse_labeled_integer(values[f"line.{index}.quantity"])
        line_total = parse_labeled_integer(values[f"line.{index}.total"])
        if item.get("quantity") != quantity:
            raise ValueError(f"canonical fixture {source_id} line {index} quantity differs from labels")
        if item.get("line_total") != line_total:
            raise ValueError(f"canonical fixture {source_id} line {index} total differs from labels")
        if quantity <= 0 or line_total % quantity:
            raise ValueError(f"canonical fixture {source_id} line {index} has no exact integer unit price")
        if item.get("unit_price") != line_total // quantity:
            raise ValueError(f"canonical fixture {source_id} line {index} unit price is not the exact derivation")

    expected_payable = parse_labeled_integer(values["invoice.payable"])
    if invoice.get("summary", {}).get("payable") != expected_payable:
        raise ValueError(f"canonical fixture {source_id} payable differs from labels")
    expected_subtotal = sum(parse_labeled_integer(values[f"line.{i}.total"]) for i in range(row_count))
    summary = invoice.get("summary", {})
    if summary.get("subtotal") != expected_subtotal:
        raise ValueError(f"canonical fixture {source_id} subtotal differs from labeled line totals")
    if expected_payable != expected_subtotal:
        raise ValueError(f"labeled payable for {source_id} differs from the labeled line-total sum")


def load_training_observations(
    canonical_dir: str | Path,
    labels_path: str | Path | None = None,
) -> tuple[LayoutObservation, ...]:
    """Load label geometry after validating its sidecar and canonical instances.

    The manifest's ``synthesized_from_labels`` marker is deliberately outside
    Canonical Invoice JSON so the frozen v0 schema remains unchanged.
    """
    directory = Path(canonical_dir).resolve()
    labels_file = (
        Path(labels_path).resolve()
        if labels_path is not None
        else (directory.parent / "labels.json").resolve()
    )
    manifest = _load_json(directory / "synthesis-manifest.json")
    if manifest.get("synthesis_marker") != "synthesized_from_labels":
        raise ValueError("canonical sidecar is missing synthesized_from_labels marker")
    if not isinstance(manifest.get("invoices"), list) or not manifest["invoices"]:
        raise ValueError("canonical sidecar must list synthesized invoice fixtures")
    source_file = manifest.get("source_file")
    if not isinstance(source_file, str) or (directory / source_file).resolve() != labels_file:
        raise ValueError("manifest source_file does not resolve to the supplied labels.json")

    labels_root = _load_json(labels_file)
    if labels_root.get("label_status") != "OPERATOR_CONFIRMED":
        raise ValueError("template training requires operator-confirmed label values")
    label_by_id: dict[str, dict[str, Any]] = {}
    for label in labels_root.get("invoices", []):
        source_id = str(label["id"])
        if source_id in label_by_id:
            raise ValueError(f"duplicate source label id {source_id}")
        label_by_id[source_id] = label

    observations: list[LayoutObservation] = []
    seen_ids: set[str] = set()
    for manifest_record in manifest["invoices"]:
        if manifest_record.get("synthesized_from_labels") is not True:
            raise ValueError("every training invoice must be marked synthesized_from_labels")
        synthetic_fields = manifest_record.get("synthetic_context_fields")
        if (
            not isinstance(synthetic_fields, list)
            or not synthetic_fields
            or any(not isinstance(field, str) or not field for field in synthetic_fields)
            or not isinstance(manifest_record.get("synthetic_context_source"), str)
        ):
            raise ValueError("manifest must identify synthetic context fields and their source")
        source_id = str(manifest_record.get("source_id", ""))
        if not source_id or source_id in seen_ids:
            raise ValueError("manifest source ids must be non-empty and unique")
        seen_ids.add(source_id)
        if source_id not in label_by_id:
            raise ValueError(f"manifest source id {source_id} is absent from labels.json")
        label = label_by_id[source_id]

        filename = manifest_record.get("canonical_file")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError(f"unsafe or missing canonical filename for source {source_id}")
        invoice = _load_json(directory / filename)
        if manifest_record.get("canonical_state") != invoice.get("state"):
            raise ValueError(f"manifest state disagrees with canonical fixture for {source_id}")
        _validate_label_canonical_pair(label, invoice, source_id)

        source_image = (labels_file.parent / label["path"]).resolve()
        source_image_reference = manifest_record.get("source_image")
        if (
            not isinstance(source_image_reference, str)
            or (directory / source_image_reference).resolve() != source_image
        ):
            raise ValueError(f"manifest source image path disagrees with labels for {source_id}")
        if not source_image.is_file():
            raise ValueError(f"source image is missing for label {source_id}: {source_image}")
        actual_sha256 = hashlib.sha256(source_image.read_bytes()).hexdigest()
        expected_sha256 = manifest_record.get("source_image_sha256")
        if actual_sha256 != expected_sha256 or invoice.get("provenance", {}).get("image_sha256") != actual_sha256:
            raise ValueError(f"source image hash mismatch for label {source_id}")

        width, height = label["image_dimensions"]
        raw_values = label.get("values", {})
        observations.append(
            LayoutObservation(
                source_id=source_id,
                image_width=int(width),
                image_height=int(height),
                column_boundaries=tuple(float(value) for value in label["column_boundaries"]),
                row_bands=tuple(tuple(float(value) for value in band) for band in label["row_bands"]),
                payable_bbox=tuple(float(value) for value in label["payable_bbox"]),
                field_values=raw_values,
            )
        )

    if len(observations) != len(manifest["invoices"]):
        raise ValueError("not all manifest fixtures were loaded")
    return tuple(sorted(observations, key=lambda observation: observation.source_id))


def _layout_compatible(left: LayoutObservation, right: LayoutObservation) -> bool:
    """Conservative layout clustering, independent of invoice row count."""
    column_delta = max(
        abs(a - b)
        for a, b in zip(left.normalized_column_boundaries, right.normalized_column_boundaries)
    )
    return (
        column_delta <= 0.01
        and abs(left.row_height_over_width - right.row_height_over_width) <= 0.025
        and abs(left.table_top_over_width - right.table_top_over_width) <= 0.04
        and abs(left.payable_gap_over_width - right.payable_gap_over_width) <= 0.025
    )


def _median(values: tuple[float, ...] | list[float]) -> float:
    return float(statistics.median(values))


def _aggregate_cluster(
    observations: list[LayoutObservation],
    cluster_index: int,
) -> LayoutTemplate:
    normalized_columns = tuple(
        _median([observation.normalized_column_boundaries[index] for observation in observations])
        for index in range(5)
    )
    row_height = _median([observation.row_height_over_width for observation in observations])
    row_pitch = _median([observation.row_pitch_over_width for observation in observations])
    row_cv = _median([observation.row_height_cv for observation in observations])
    table_top = _median([observation.table_top_over_width for observation in observations])
    payable_gap = _median([observation.payable_gap_over_width for observation in observations])
    payable_boxes = [observation.payable_bbox_over_width for observation in observations]
    payable_left = _median([box[0] for box in payable_boxes])
    payable_width = _median([box[2] for box in payable_boxes])
    payable_height = _median([box[3] for box in payable_boxes])
    row_counts = tuple(sorted({observation.row_count for observation in observations}))

    # E-02 crop_spatial_cells currently trims 8 px from a row's top and 3 px
    # from its bottom. Store those insets as fractions of the learned row band.
    # Payable geometry remains in image-width units, so it scales with raster size.
    median_row_height_px = _median([observation.median_row_height for observation in observations])
    row_y_start = min(0.95, 8.0 / median_row_height_px)
    row_y_end = max(row_y_start + 0.01, 1.0 - 3.0 / median_row_height_px)
    column_intervals = (
        (normalized_columns[0], normalized_columns[1]),
        (normalized_columns[1], normalized_columns[2]),
        (normalized_columns[2], normalized_columns[3]),
        (normalized_columns[3], normalized_columns[4]),
    )
    field_positions = [
        FieldPosition("line.total", *column_intervals[0], row_y_start, row_y_end, "row_fraction"),
        FieldPosition("line.quantity", *column_intervals[1], row_y_start, row_y_end, "row_fraction"),
        FieldPosition("line.description", *column_intervals[2], row_y_start, row_y_end, "row_fraction"),
        FieldPosition("line.sequence", *column_intervals[3], row_y_start, row_y_end, "row_fraction"),
    ]
    payable_x_start = _median([box[0] for box in payable_boxes])
    payable_x_end = _median([box[0] + box[2] for box in payable_boxes])
    payable_y_start = _median([box[1] for box in payable_boxes])
    payable_y_end = _median([box[1] + box[3] for box in payable_boxes])
    field_positions.append(
        FieldPosition(
            "invoice.payable",
            payable_x_start,
            payable_x_end,
            payable_y_start,
            payable_y_end,
            "page_over_width",
        )
    )

    observed_characters = {
        character
        for observation in observations
        for _, text in observation.field_values
        for character in text
    }
    digit_alphabet = tuple(
        character
        for character in _PERSIAN_DIGITS + _ASCII_DIGITS
        if character in observed_characters
    )
    separators = {
        character
        for observation in observations
        for _, text in observation.field_values
        for character in text
        if character not in _PERSIAN_DIGITS + _ASCII_DIGITS
    }
    if len(separators) > 1:
        raise ValueError(f"one template cannot learn multiple amount separators: {separators}")
    amount_separator = next(iter(separators), None)
    if amount_separator is not None:
        if not all(character == amount_separator for character in separators):
            raise ValueError("inconsistent amount separator")
        observed_group_lengths = {
            len(group)
            for observation in observations
            for field_name, text in observation.field_values
            if field_name.endswith(".total") or field_name == "invoice.payable"
            for group in text.split(amount_separator)[1:]
        }
        if len(observed_group_lengths) != 1:
            raise ValueError("training amount strings do not share one grouping size")
        amount_group_size = next(iter(observed_group_lengths))
    else:
        amount_group_size = 3

    return LayoutTemplate(
        template_id=f"e05-layout-{cluster_index:02d}",
        source_invoice_ids=tuple(sorted(observation.source_id for observation in observations)),
        row_count_min=min(row_counts),
        row_count_max=max(row_counts),
        known_row_counts=row_counts,
        normalized_column_boundaries=normalized_columns,
        median_row_height_over_width=row_height,
        median_row_pitch_over_width=row_pitch,
        median_row_height_cv=row_cv,
        table_top_over_width=table_top,
        payable_gap_over_width=payable_gap,
        payable_bbox_left_over_width=payable_left,
        payable_bbox_width_over_width=payable_width,
        payable_bbox_height_over_width=payable_height,
        field_positions=tuple(field_positions),
        digit_alphabet=digit_alphabet,
        amount_thousands_separator=amount_separator,
        amount_group_size=amount_group_size,
    )


def build_template_bank(
    canonical_dir: str | Path,
    labels_path: str | Path | None = None,
    *,
    confidence_threshold: float = 0.85,
    currency_unit: str | None = None,
) -> TemplateBank:
    """Build clustered templates and retain the caller's onboarding currency.

    The builder never infers or converts the unit from fixture values. Omitted
    and unsupported values remain on the bank for E-06 to route to REVIEW.
    """
    observations = load_training_observations(canonical_dir, labels_path)
    clusters: list[list[LayoutObservation]] = []
    for observation in observations:
        for cluster in clusters:
            if _layout_compatible(cluster[0], observation):
                cluster.append(observation)
                break
        else:
            clusters.append([observation])
    templates = tuple(
        _aggregate_cluster(cluster, index)
        for index, cluster in enumerate(clusters, start=1)
    )
    return TemplateBank(
        templates=templates,
        confidence_threshold=confidence_threshold,
        currency_unit=currency_unit,
    )


def match_observation(
    bank: TemplateBank,
    observation: LayoutObservation,
    *,
    threshold: float | None = None,
) -> TemplateMatch:
    """Return the highest-confidence layout match, with transparent reasons."""
    minimum = bank.confidence_threshold if threshold is None else threshold
    matches = score_bank(bank.templates, observation, threshold=minimum)
    if not matches:
        raise ValueError("cannot match against an empty template bank")
    return matches[0]


def save_template_bank(bank: TemplateBank, path: str | Path) -> None:
    """Persist a reusable bank as UTF-8 JSON at the caller-selected path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(bank.to_dict(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output_path.write_bytes(payload)


def load_template_bank(path: str | Path) -> TemplateBank:
    """Load a bank previously written by :func:`save_template_bank`."""
    value = _load_json(Path(path))
    if not isinstance(value, dict):
        raise ValueError("template-bank document must be a JSON object")
    return TemplateBank.from_dict(value)
