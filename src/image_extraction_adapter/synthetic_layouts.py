"""Explicitly synthetic E-71 invoices for multi-layout mechanics testing.

The generator has no access to owner data or external services. It renders three
visibly distinct table profiles and returns independent expected values for
per-layout layout-match measurements. Those measurements are not OCR accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from e05_template_bank import LayoutObservation, TemplateBank, build_template_bank_from_observations, match_observation


@dataclass(frozen=True)
class SyntheticPrintLayout:
    layout_id: str
    column_boundaries: tuple[int, int, int, int, int]
    logo_size: tuple[int, int]
    currency_label: str
    table_top: int = 230
    header_height: int = 36
    row_height: int = 48


@dataclass(frozen=True)
class SyntheticLayoutInvoice:
    layout_id: str
    invoice_index: int
    image_path: Path
    profile: SyntheticPrintLayout
    expected_values: dict[str, str]
    observation: LayoutObservation


_LAYOUTS = (
    SyntheticPrintLayout(
        layout_id="layout-1",
        column_boundaries=(50, 170, 225, 480, 590),
        logo_size=(52, 34),
        currency_label="RIAL",
    ),
    SyntheticPrintLayout(
        layout_id="layout-2",
        column_boundaries=(35, 145, 275, 455, 610),
        logo_size=(82, 48),
        currency_label="IRR",
    ),
    SyntheticPrintLayout(
        layout_id="layout-3",
        column_boundaries=(72, 235, 300, 465, 580),
        logo_size=(30, 24),
        currency_label="TOMAN",
    ),
)


_LAYOUT_BY_ID = {layout.layout_id: layout for layout in _LAYOUTS}
_IMAGE_WIDTH = 640
_IMAGE_HEIGHT = 520


def synthetic_layouts() -> tuple[SyntheticPrintLayout, ...]:
    """Return the immutable, explicitly synthetic layout definitions."""
    return _LAYOUTS


def _expected_values(invoice_index: int) -> dict[str, str]:
    if type(invoice_index) is not int or invoice_index not in {0, 1}:
        raise ValueError("synthetic invoice_index must be 0 (training) or 1 (holdout)")
    if invoice_index == 0:
        values = {
            "line.0.quantity": "2",
            "line.0.total": "1200",
            "line.1.quantity": "1",
            "line.1.total": "800",
            "invoice.payable": "2000",
        }
    else:
        values = {
            "line.0.quantity": "1",
            "line.0.total": "1000",
            "line.1.quantity": "2",
            "line.1.total": "800",
            "invoice.payable": "1800",
        }
    return values


def _observation(
    profile: SyntheticPrintLayout,
    invoice_index: int,
) -> tuple[dict[str, str], LayoutObservation]:
    values = _expected_values(invoice_index)
    row_start = profile.table_top + profile.header_height
    row_bands = tuple(
        (
            float(row_start + index * profile.row_height),
            float(row_start + (index + 1) * profile.row_height),
        )
        for index in range(2)
    )
    payable_bbox = (
        float(profile.column_boundaries[0] + 100),
        float(row_bands[-1][1] + 54),
        90.0,
        18.0,
    )
    observation = LayoutObservation(
        source_id=f"synthetic-{profile.layout_id}-invoice-{invoice_index}",
        image_width=_IMAGE_WIDTH,
        image_height=_IMAGE_HEIGHT,
        column_boundaries=tuple(float(value) for value in profile.column_boundaries),
        row_bands=row_bands,
        payable_bbox=payable_bbox,
        field_values=values,
    )
    return values, observation


def render_synthetic_invoice(
    output_path: Path | str,
    *,
    layout_id: str,
    invoice_index: int,
) -> SyntheticLayoutInvoice:
    """Render one fabricated layout sample and return its known label vector."""
    profile = _LAYOUT_BY_ID.get(layout_id)
    if profile is None:
        raise ValueError(f"unknown synthetic layout ID: {layout_id!r}")
    values, observation = _observation(profile, invoice_index)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - dependency install guidance
        raise RuntimeError("Pillow is required to render E-71 synthetic layouts") from exc

    image = Image.new("RGB", (_IMAGE_WIDTH, _IMAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    logo_left, logo_top = 28, 35
    logo_width, logo_height = profile.logo_size
    draw.rectangle(
        (logo_left, logo_top, logo_left + logo_width, logo_top + logo_height),
        outline=(30, 70, 110),
        fill=(228, 238, 248),
        width=2,
    )
    draw.text(
        (logo_left + 5, logo_top + 5),
        profile.layout_id.upper(),
        fill=(20, 40, 70),
        font=font,
    )
    draw.text((170, 58), "SYNTHETIC INVOICE", fill=(20, 20, 20), font=font)
    draw.text((170, 78), f"CURRENCY {profile.currency_label}", fill=(20, 20, 20), font=font)

    columns = profile.column_boundaries
    table_top = profile.table_top
    header_bottom = table_top + profile.header_height
    table_bottom = header_bottom + 2 * profile.row_height
    for y in (table_top, header_bottom, table_bottom - profile.row_height, table_bottom):
        draw.line((columns[0], y, columns[-1], y), fill=(0, 0, 0), width=2)
    for x in columns:
        draw.line((x, table_top, x, table_bottom), fill=(0, 0, 0), width=2)

    for column_index, label in enumerate(("TOTAL", "QTY", "DESCRIPTION", "ROW")):
        left, right = columns[column_index], columns[column_index + 1]
        draw.text((left + 5, table_top + 12), label, fill=(0, 0, 0), font=font)

    for row_index in range(2):
        center_y = header_bottom + row_index * profile.row_height + 18
        total = values[f"line.{row_index}.total"]
        quantity = values[f"line.{row_index}.quantity"]
        draw.text((columns[0] + 5, center_y), total, fill=(0, 0, 0), font=font)
        draw.text((columns[1] + 5, center_y), quantity, fill=(0, 0, 0), font=font)
        draw.text((columns[2] + 5, center_y), "SYNTHETIC ITEM", fill=(0, 0, 0), font=font)
        draw.text((columns[3] + 5, center_y), str(row_index + 1), fill=(0, 0, 0), font=font)

    payable_top = int(observation.payable_bbox[1])
    draw.text((columns[0] + 105, payable_top + 3), values["invoice.payable"], fill=(0, 0, 0), font=font)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False)
    image.close()
    return SyntheticLayoutInvoice(
        layout_id=layout_id,
        invoice_index=invoice_index,
        image_path=path,
        profile=profile,
        expected_values=values,
        observation=observation,
    )


def _spatial_for_invoice(invoice: SyntheticLayoutInvoice) -> Any:
    from types import SimpleNamespace

    x, y, width, height = invoice.observation.payable_bbox
    return SimpleNamespace(
        column_boundaries=invoice.observation.column_boundaries,
        row_bands=invoice.observation.row_bands,
        assessments=(SimpleNamespace(
            field_name="invoice.payable",
            bbox=(int(x), int(y), int(width), int(height)),
            status=None,
        ),),
    )


def measure_synthetic_numeric_accuracy_by_layout(
    training: tuple[SyntheticLayoutInvoice, ...] | list[SyntheticLayoutInvoice],
    holdout: tuple[SyntheticLayoutInvoice, ...] | list[SyntheticLayoutInvoice],
) -> dict[str, dict[str, Any]]:
    """Measure exact numeric-cell results by layout using a separate holdout.

    Training uses only the explicitly synthetic training invoices. Every field
    marked EXTRACTED is compared with the independent synthetic answer vector;
    any mismatch is counted as wrong. REVIEW and missing fields are never
    counted as correct. This is a mechanics measurement, not real-world proof.
    """
    from PIL import Image

    from .glyph_classifier import (
        GlyphClassifierOCR,
        GlyphTemplateSet,
        LabeledCell,
        build_templates,
        normalize_label_text,
    )
    from .preprocessing import crop_spatial_cells
    from .pipeline_v0 import DEFAULT_MINIMUM_CONFIDENCE

    training_items = tuple(training)
    holdout_items = tuple(holdout)
    if not training_items or not holdout_items:
        raise ValueError("E-71 needs separate synthetic training and holdout invoices")
    if any(item.invoice_index != 0 for item in training_items):
        raise ValueError("E-71 training data must use the declared synthetic training split")
    if any(item.invoice_index != 1 for item in holdout_items):
        raise ValueError("E-71 evaluation data must use the declared synthetic holdout split")
    train_ids = {item.layout_id for item in training_items}
    holdout_ids = {item.layout_id for item in holdout_items}
    if train_ids != holdout_ids or train_ids != set(_LAYOUT_BY_ID):
        raise ValueError("E-71 requires one training and one holdout invoice for each declared layout")

    templates = GlyphTemplateSet()
    for invoice in training_items:
        spatial = _spatial_for_invoice(invoice)
        with Image.open(invoice.image_path) as opened:
            opened.load()
            image = opened.convert("RGB")
        crops = ()
        try:
            crops = crop_spatial_cells(
                image, spatial, include_descriptions=False, include_payable=True
            )
            labeled = [
                LabeledCell(crop.field_name, crop.image, invoice.expected_values[crop.field_name])
                for crop in crops
                if crop.numeric and crop.field_name in invoice.expected_values
            ]
            if not labeled:
                raise ValueError(f"synthetic training invoice {invoice.layout_id} had no numeric crops")
            templates, logs = build_templates(labeled, templates)
            if not any(line.startswith("USED ") for line in logs):
                raise ValueError(f"synthetic training invoice {invoice.layout_id} produced no Glyph templates")
        finally:
            image.close()
            for crop in crops:
                try:
                    crop.image.close()
                except Exception:
                    pass

    engine = GlyphClassifierOCR(templates)
    metrics: dict[str, dict[str, Any]] = {}
    for invoice in sorted(holdout_items, key=lambda value: value.layout_id):
        results = engine.recognize_spatial_cells(
            invoice.image_path,
            _spatial_for_invoice(invoice),
            minimum_confidence=DEFAULT_MINIMUM_CONFIDENCE,
            extra_amounts=0,
            apply_gate=True,
        )
        expected = invoice.expected_values
        by_name = {result.field_name: result for result in results}
        extracted = correct = wrong = review = 0
        for field_name, expected_value in expected.items():
            result = by_name.get(field_name)
            if result is None:
                review += 1
            elif result.status == "EXTRACTED":
                extracted += 1
                if normalize_label_text(result.raw_value) == normalize_label_text(expected_value):
                    correct += 1
                else:
                    wrong += 1
            else:
                review += 1
        metrics[invoice.layout_id] = {
            "metric": "synthetic_numeric_cell_exact_accuracy",
            "expected_fields": len(expected),
            "extracted_fields": extracted,
            "correct_fields": correct,
            "extracted_but_wrong": wrong,
            "review_or_missing_fields": review,
            "accuracy": correct / extracted if extracted else None,
        }
    return metrics


def measure_layout_match_accuracy(
    training: tuple[SyntheticLayoutInvoice, ...] | list[SyntheticLayoutInvoice],
    holdout: tuple[SyntheticLayoutInvoice, ...] | list[SyntheticLayoutInvoice],
) -> dict[str, dict[str, Any]]:
    """Measure E-05 layout-ID accuracy per profile using separate holdout samples.

    This metric scores layout matching only. It must not be reported as field
    extraction accuracy, real-world accuracy, or evidence from real invoices.
    """
    training_items = tuple(training)
    holdout_items = tuple(holdout)
    if not training_items or not holdout_items:
        raise ValueError("E-71 needs separate synthetic training and holdout invoices")
    if any(item.invoice_index != 0 for item in training_items):
        raise ValueError("E-71 training data must use the declared synthetic training split")
    if any(item.invoice_index != 1 for item in holdout_items):
        raise ValueError("E-71 evaluation data must use the declared synthetic holdout split")
    train_ids = {item.layout_id for item in training_items}
    holdout_ids = {item.layout_id for item in holdout_items}
    if train_ids != holdout_ids or train_ids != set(_LAYOUT_BY_ID):
        raise ValueError("E-71 requires one training and one holdout invoice for each declared layout")

    ordered_training = sorted(training_items, key=lambda value: value.layout_id)
    bank: TemplateBank = build_template_bank_from_observations(
        [item.observation for item in ordered_training],
        currency_unit="rial",
    )
    layout_to_template = {
        item.layout_id: template
        for item, template in zip(ordered_training, bank.templates, strict=True)
    }
    metrics: dict[str, dict[str, Any]] = {}
    for invoice in sorted(holdout_items, key=lambda value: value.layout_id):
        match = match_observation(bank, invoice.observation)
        expected_template_id = layout_to_template[invoice.layout_id].template_id
        correct = match.matched and match.template_id == expected_template_id
        metrics[invoice.layout_id] = {
            "metric": "synthetic_layout_match_accuracy",
            "correct": int(correct),
            "total": 1,
            "accuracy": 1.0 if correct else 0.0,
            "expected_template_id": expected_template_id,
            "matched_template_id": match.template_id,
        }
    return metrics
