"""Explicit local E-70 training from operator-confirmed capture evidence.

This module is intentionally separate from extraction. It consumes a human-
completed O15 label file, trains only confirmed numeric crops, and creates E-05
layout observations only for pages whose numeric labels are all confirmed.
Unknown labels are never inferred or learned.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence

from e05_template_bank import (
    LayoutObservation,
    TemplateBank,
    build_template_bank_from_observations,
)
from .bundle_paths import resource_root
from .capture_folder import inspect_capture_folder
from .glyph_classifier import (
    GlyphTemplateSet,
    LabeledCell,
    build_templates,
    normalize_label_text,
    parse_amount_text,
)
from .preprocessing import detect_layout_safe


_NUMERIC_FIELD = re.compile(r"^line\.(\d+)\.(quantity|total)$")


@dataclass(frozen=True)
class OperatorTrainingReport:
    """In-memory result of an explicit operator-training request.

    The report intentionally contains counts and trained artifacts only; it
    never carries invoice values, source paths, images, or source hashes.
    """

    glyph_templates: GlyphTemplateSet
    layout_bank: TemplateBank
    sample_count: int
    confirmed_label_count: int
    uncertain_label_count: int
    skipped_label_count: int
    layout_observation_count: int
    layout_review_page_count: int


def _protected_roots() -> tuple[Path, ...]:
    roots = [resource_root().resolve()]
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    return tuple(roots)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _require_local_input(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if any(_within(resolved, root) for root in _protected_roots()):
        raise ValueError(f"{description} must remain outside the repository/bundle")
    return resolved


def _read_json(path: Path, description: str) -> dict[str, Any]:
    try:
        document = json.loads(
            path.read_bytes().decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON number {value!r}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"cannot read {description} as strict UTF-8 JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"{description} must be a JSON object")
    return document


def _validate(document: dict[str, Any], schema_name: str, description: str) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - install guidance
        raise RuntimeError("jsonschema is required for local operator training") from exc
    schema_path = resource_root() / "schemas" / "o15" / schema_name
    schema = _read_json(schema_path, f"{description} schema")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)


def _confirmed_numeric_label(field_name: str, value: str) -> str:
    normalized = normalize_label_text(value)
    match = _NUMERIC_FIELD.fullmatch(field_name)
    if field_name != "invoice.payable" and match is None:
        raise ValueError("only line quantity/total and invoice payable labels can train E-70")
    if match is not None and match.group(2) == "quantity":
        if not normalized or not all("۰" <= char <= "۹" for char in normalized):
            raise ValueError("confirmed quantity label must contain Persian digits only")
        if int(normalized.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))) <= 0:
            raise ValueError("confirmed quantity label must be positive")
    elif parse_amount_text(normalized) is None:
        raise ValueError("confirmed amount label must use the supported integer format")
    return normalized


def _safe_crop(evidence_root: Path, crop_file: str) -> Path:
    candidate = evidence_root / crop_file
    if candidate.is_symlink():
        raise ValueError("operator evidence crops must not be symbolic links")
    crop = candidate.resolve(strict=True)
    if not _within(crop, evidence_root) or not crop.is_file():
        raise ValueError("operator evidence crop escaped its local evidence directory")
    from PIL import Image

    try:
        with Image.open(crop) as image:
            if image.format != "PNG":
                raise ValueError("operator evidence crop is not PNG")
            image.verify()
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("operator evidence crop cannot be decoded") from exc
    return crop


def _page_layout_observation(
    image_path: Path,
    *,
    source_id: str,
    image_width: int,
    image_height: int,
    field_values: dict[str, str],
    payable_bbox: tuple[int, int, int, int],
) -> LayoutObservation | None:
    from PIL import Image

    try:
        with Image.open(image_path) as opened:
            opened.load()
            image = opened.convert("RGB")
        try:
            safety = detect_layout_safe(image)
            if safety.status != "OK" or safety.geometry is None:
                return None
            if image.size != (image_width, image_height):
                return None
            left, top, right, bottom = payable_bbox
            if (
                left < 0
                or top < safety.geometry.row_bands[-1][1]
                or right <= left
                or bottom <= top
                or right > image.width
                or bottom > image.height
            ):
                return None
            return LayoutObservation(
                source_id=source_id,
                image_width=image.width,
                image_height=image.height,
                column_boundaries=tuple(safety.geometry.column_boundaries),
                row_bands=tuple(tuple(band) for band in safety.geometry.row_bands),
                payable_bbox=(left, top, right - left, bottom - top),
                field_values=field_values,
            )
        finally:
            image.close()
    except (OSError, ValueError, TypeError):
        return None


def build_operator_training_report(
    samples: Sequence[tuple[Path | str, Path | str, Path | str]],
    *,
    currency_unit: str,
    confidence_threshold: float = 0.85,
    base_templates_path: Path | str | None = None,
) -> OperatorTrainingReport:
    """Build local E-02/E-05 baselines from explicit operator confirmations.

    Each sample is ``(capture_folder, evidence_dir, labels_json)``. Captures,
    evidence and labels must stay outside the application/repository. The E-05
    layout bank is deliberately built from direct observations and therefore
    does not need the E-03 test kit or Canonical fixture sidecars.
    """
    if not samples:
        raise ValueError("at least one operator-reviewed capture sample is required")
    if currency_unit not in {"rial", "toman"}:
        raise ValueError("currency_unit must be explicitly confirmed as rial or toman")

    if base_templates_path is None:
        templates = GlyphTemplateSet()
    else:
        base_path = Path(base_templates_path).expanduser().resolve(strict=True)
        templates = GlyphTemplateSet.load(base_path)

    observations: list[LayoutObservation] = []
    confirmed_count = uncertain_count = skipped_count = 0
    layout_review_pages = 0
    sample_ordinal = 0

    for capture_input, evidence_input, labels_input in samples:
        sample_ordinal += 1
        capture_root = _require_local_input(Path(capture_input), "real capture folder")
        evidence_root = _require_local_input(Path(evidence_input), "real review evidence")
        labels_path = _require_local_input(Path(labels_input), "operator labels")
        if not capture_root.is_dir() or not evidence_root.is_dir() or not labels_path.is_file():
            raise ValueError("each E-70 sample needs a capture folder, evidence directory, and labels file")
        if _within(evidence_root, capture_root) or _within(capture_root, evidence_root):
            raise ValueError("capture and review evidence directories must remain separate")
        if _within(labels_path, capture_root):
            raise ValueError("operator labels must not be stored inside the source capture folder")

        capture = inspect_capture_folder(capture_root)
        evidence = _read_json(evidence_root / "review-evidence-v1.json", "review evidence")
        labels = _read_json(labels_path, "operator labels")
        _validate(evidence, "review-evidence-v1.schema.json", "review evidence")
        _validate(labels, "operator-label-v1.schema.json", "operator labels")

        evidence_by_id: dict[str, dict[str, Any]] = {}
        evidence_by_page: dict[int, list[dict[str, Any]]] = {}
        for item in evidence["items"]:
            evidence_id = item["evidence_id"]
            if evidence_id in evidence_by_id:
                raise ValueError("review evidence contains duplicate evidence IDs")
            evidence_by_id[evidence_id] = item
            evidence_by_page.setdefault(item["page_index"], []).append(item)

        labels_by_id: dict[str, dict[str, Any]] = {}
        for entry in labels["entries"]:
            evidence_id = entry["evidence_id"]
            if evidence_id in labels_by_id:
                raise ValueError("operator labels contain duplicate evidence IDs")
            source = evidence_by_id.get(evidence_id)
            if source is None:
                raise ValueError("operator label references evidence that is not in its evidence file")
            if (
                entry["field_name"] != source["field_name"]
                or entry["value"] != source["value"]
                or entry["crop_file"] != source["crop_file"]
                or entry["crop_region"] != source["crop_region"]
            ):
                raise ValueError("operator label content does not match its source evidence")
            labels_by_id[evidence_id] = entry
            _safe_crop(evidence_root, entry["crop_file"])

        page_by_index = {page.page_index: page for page in capture.pages}
        for page_index, page_items in sorted(evidence_by_page.items()):
            capture_page = page_by_index.get(page_index)
            if capture_page is None or any(
                item["image_file"] != capture_page.path.name
                or item["image_size"] != [capture_page.width, capture_page.height]
                for item in page_items
            ):
                layout_review_pages += 1
                continue

            confirmed_values: dict[str, str] = {}
            page_complete = True
            numeric_items = [
                item for item in page_items
                if item["field_name"] == "invoice.payable"
                or _NUMERIC_FIELD.fullmatch(item["field_name"])
            ]
            if not numeric_items:
                layout_review_pages += 1
                continue

            for item in numeric_items:
                entry = labels_by_id.get(item["evidence_id"])
                if entry is None or entry["read_correctly"] is None:
                    uncertain_count += 1
                    page_complete = False
                    continue
                chosen_value = (
                    item["value"]
                    if entry["read_correctly"] is True
                    else entry["corrected_value"]
                )
                if not isinstance(chosen_value, str):
                    uncertain_count += 1
                    page_complete = False
                    continue
                try:
                    normalized_value = _confirmed_numeric_label(item["field_name"], chosen_value)
                except ValueError:
                    skipped_count += 1
                    page_complete = False
                    continue
                confirmed_count += 1
                confirmed_values[item["field_name"]] = normalized_value

                crop_path = _safe_crop(evidence_root, item["crop_file"])
                from PIL import Image

                with Image.open(crop_path) as opened:
                    opened.load()
                    crop_image = opened.convert("RGB")
                try:
                    _, logs = build_templates(
                        (LabeledCell(item["field_name"], crop_image, normalized_value),),
                        templates,
                    )
                finally:
                    crop_image.close()
                if not logs or not logs[0].startswith("USED "):
                    skipped_count += 1

            line_indexes = {
                int(match.group(1))
                for field_name in confirmed_values
                if (match := _NUMERIC_FIELD.fullmatch(field_name))
                and match.group(2) == "quantity"
            }
            total_indexes = {
                int(match.group(1))
                for field_name in confirmed_values
                if (match := _NUMERIC_FIELD.fullmatch(field_name))
                and match.group(2) == "total"
            }
            if (
                not page_complete
                or not line_indexes
                or line_indexes != total_indexes
                or "invoice.payable" not in confirmed_values
            ):
                layout_review_pages += 1
                continue

            payable_evidence = next(
                (item for item in numeric_items if item["field_name"] == "invoice.payable"),
                None,
            )
            if payable_evidence is None:
                layout_review_pages += 1
                continue
            payable_crop = tuple(payable_evidence["crop_region"])
            observation = _page_layout_observation(
                capture_page.path,
                source_id=f"e70-sample-{sample_ordinal:04d}-page-{page_index:04d}",
                image_width=capture_page.width,
                image_height=capture_page.height,
                field_values=confirmed_values,
                payable_bbox=payable_crop,
            )
            if observation is None:
                layout_review_pages += 1
                continue
            observations.append(observation)

    if not observations:
        raise ValueError("no fully confirmed, safely detected invoice page is eligible for the E-05 baseline")
    if not any(templates.profiles.values()):
        raise ValueError("no confirmed glyph crop segmented cleanly; no E-02 baseline was written")

    layout_bank = build_template_bank_from_observations(
        observations,
        confidence_threshold=confidence_threshold,
        currency_unit=currency_unit,
    )
    return OperatorTrainingReport(
        glyph_templates=templates,
        layout_bank=layout_bank,
        sample_count=len(samples),
        confirmed_label_count=confirmed_count,
        uncertain_label_count=uncertain_count,
        skipped_label_count=skipped_count,
        layout_observation_count=len(observations),
        layout_review_page_count=layout_review_pages,
    )
