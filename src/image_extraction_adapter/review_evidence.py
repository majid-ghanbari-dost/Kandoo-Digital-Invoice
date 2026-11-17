"""Local-only field crop evidence and an offline HTML review queue.

The frozen capture-folder JSON remains unchanged. This additive sidecar records
what the extractor read, its confidence/reason, and the exact source-image crop
region so an operator can inspect it locally.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import html
import io
import json
import math
from pathlib import Path
import shutil
import tempfile
from typing import Any, Sequence


REVIEW_EVIDENCE_VERSION = "o15.review-evidence.v1"


@dataclass(frozen=True)
class ReviewPageSource:
    """One validated capture page plus the E-02 outcome used for evidence."""

    page_index: int
    image_path: Path
    pipeline_status: str
    layout_status: str
    layout_reason: str
    pipeline_reason: str
    cell_results: tuple[Any, ...] = ()
    error: str | None = None


def _bounded_box(value: Any, width: int, height: int) -> tuple[int, int, int, int] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    if any(isinstance(part, bool) or not isinstance(part, int) for part in value):
        return None
    left, top, right, bottom = value
    left = max(0, min(width, left))
    top = max(0, min(height, top))
    right = max(0, min(width, right))
    bottom = max(0, min(height, bottom))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _confidence(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    if not math.isfinite(normalized) or not 0 <= normalized <= 100:
        return None
    return normalized


def _effective_reason(cell: Any, status: str) -> str:
    reason = getattr(cell, "reason", None)
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    if status == "EXTRACTED":
        return (
            "No review trigger was reported by the classifier; this is not an "
            "independent correctness check."
        )
    return "The extractor did not provide a specific reason; operator review is required."


def _page_fallback_status(page: ReviewPageSource) -> str:
    if page.pipeline_status == "REVIEW" or page.layout_status == "REVIEW":
        return "REVIEW"
    if (
        page.pipeline_status in {"REJECT", "BLOCKED"}
        or page.layout_status == "BLOCKED"
        or page.error is not None
    ):
        return "BLOCKED"
    return "REVIEW"


def _append_reason(existing: str, addition: str) -> str:
    return f"{existing} {addition}" if existing else addition


def _render_html(items: Sequence[dict[str, Any]], crop_bytes: Sequence[bytes]) -> str:
    cards: list[str] = []
    for item, image_bytes in zip(items, crop_bytes, strict=True):
        value = item["value"]
        displayed_value = html.escape(value, quote=True) if value else "<em>No numeric value read.</em>"
        confidence = item["confidence"]
        displayed_confidence = "Not available" if confidence is None else f"{confidence:.2f}%"
        region = ", ".join(str(part) for part in item["crop_region"])
        encoded = base64.b64encode(image_bytes).decode("ascii")
        cards.append(
            "<article class=\"evidence\">"
            f"<h2>Page {item['page_index']} — {html.escape(item['field_name'], quote=True)}</h2>"
            f"<p><strong>Evidence ID:</strong> {html.escape(item['evidence_id'], quote=True)}</p>"
            f"<p><strong>What I read:</strong> {displayed_value}</p>"
            f"<p><strong>Status:</strong> {html.escape(item['status'], quote=True)}</p>"
            f"<p><strong>Confidence:</strong> {displayed_confidence}</p>"
            f"<p><strong>Reason:</strong> {html.escape(item['reason'], quote=True)}</p>"
            f"<p><strong>Crop region (left, top, right, bottom):</strong> {region} pixels, "
            f"<strong>image:</strong> {html.escape(item['image_file'], quote=True)}</p>"
            f"<img alt=\"Page {item['page_index']} {html.escape(item['field_name'], quote=True)} crop\" "
            f"src=\"data:image/png;base64,{encoded}\">"
            "</article>"
        )
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
        "img-src data:; style-src 'unsafe-inline'\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>O15 local review queue</title>\n"
        "<style>body{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;"
        "padding:0 1rem;color:#18212f}"
        ".notice{padding:1rem;background:#fff4d6;border:1px solid #e6b84c}"
        ".evidence{border:1px solid #cbd5e1;border-radius:.6rem;padding:1rem;margin:1.2rem 0}"
        ".evidence img{display:block;max-width:100%;height:auto;image-rendering:auto}"
        ".muted{color:#526174}</style>\n</head>\n<body>\n"
        "<h1>O15 local review queue</h1>\n"
        "<p class=\"notice\">Local-only evidence. “What I read” is the extractor's reading, "
        "not confirmed truth. No online learning or automatic correction is performed.</p>\n"
        + "\n".join(cards)
        + "\n</body>\n</html>\n"
    )


def write_review_evidence(
    output_dir: Path | str,
    pages: Sequence[ReviewPageSource],
) -> Path:
    """Write evidence JSON, crop PNGs, and a self-contained local HTML queue.

    Crop coordinates use image pixels in ``[left, top, right, bottom]``
    half-open form. The output directory must be new; no absolute source paths
    or owner folder names are written into the sidecar.
    """
    target = Path(output_dir).expanduser().resolve(strict=False)
    if target.exists():
        raise FileExistsError(f"review evidence directory already exists: {target}")
    if not target.parent.is_dir():
        raise FileNotFoundError(f"review evidence parent directory does not exist: {target.parent}")

    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
    items: list[dict[str, Any]] = []
    image_bytes_by_item: list[bytes] = []
    try:
        (staging / "crops").mkdir()
        from PIL import Image

        for page in pages:
            with Image.open(page.image_path) as source:
                source.load()
                rgb = source.convert("RGB")
            try:
                width, height = rgb.size
                raw_cells = tuple(page.cell_results)
                candidates = raw_cells
                fallback_reason = page.error or page.layout_reason or page.pipeline_reason
                if not candidates:
                    status = _page_fallback_status(page)
                    if not fallback_reason:
                        fallback_reason = (
                            "No numeric field candidate was produced; operator review is required."
                        )
                    candidates = (None,)

                for ordinal, cell in enumerate(candidates, start=1):
                    if cell is None:
                        field_name = "layout" if page.layout_status != "OK" else "numeric_fields"
                        value = ""
                        confidence = None
                        status = _page_fallback_status(page)
                        reason = fallback_reason
                        box = (0, 0, width, height)
                    else:
                        field_name = str(getattr(cell, "field_name", "numeric_field"))
                        raw_value = getattr(cell, "raw_value", "")
                        value = raw_value if isinstance(raw_value, str) else ""
                        source_status = str(getattr(cell, "status", "REVIEW"))
                        status = (
                            source_status
                            if source_status in {"EXTRACTED", "REVIEW", "BLOCKED"}
                            else "REVIEW"
                        )
                        confidence = _confidence(getattr(cell, "confidence", None))
                        reason = _effective_reason(cell, status)
                        box = _bounded_box(getattr(cell, "bbox", None), width, height)
                        if box is None:
                            status = "REVIEW"
                            reason = _append_reason(
                                reason,
                                "The reported crop region was invalid; the full page is shown instead.",
                            )
                            box = (0, 0, width, height)
                        if source_status == "EXTRACTED" and (
                            not value or confidence is None
                        ):
                            status = "REVIEW"
                            reason = _append_reason(
                                reason,
                                "An EXTRACTED reading lacked a non-empty value or valid confidence; "
                                "downgraded for review.",
                            )

                    left, top, right, bottom = box
                    crop = rgb.crop(box)
                    buffer = io.BytesIO()
                    try:
                        crop.save(buffer, format="PNG", optimize=False)
                    finally:
                        crop.close()
                    encoded_crop = buffer.getvalue()
                    evidence_id = f"p{page.page_index:03d}-{ordinal:03d}"
                    crop_file = f"crops/{evidence_id}.png"
                    (staging / crop_file).write_bytes(encoded_crop)
                    items.append({
                        "evidence_id": evidence_id,
                        "page_index": page.page_index,
                        "field_name": field_name,
                        "value": value,
                        "confidence": confidence,
                        "status": status,
                        "reason": reason,
                        "image_file": page.image_path.name,
                        "image_size": [width, height],
                        "crop_file": crop_file,
                        "crop_region": [left, top, right, bottom],
                    })
                    image_bytes_by_item.append(encoded_crop)
            finally:
                rgb.close()

        document = {
            "schema_version": REVIEW_EVIDENCE_VERSION,
            "confidence_scale": "0-100",
            "crop_coordinate_system": "image_pixels_xyxy_half_open",
            "accuracy": {
                "status": "NOT_SCORED",
                "expected_values_available": False,
                "extracted_but_wrong": None,
                "reason": (
                    "No independent expected-value labels were supplied; classifier confidence "
                    "is not a correctness label."
                ),
            },
            "items": items,
        }
        payload = (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        (staging / "review-evidence-v1.json").write_bytes(payload)
        (staging / "review-queue.html").write_text(
            _render_html(items, image_bytes_by_item), encoding="utf-8", newline="\n"
        )
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target
