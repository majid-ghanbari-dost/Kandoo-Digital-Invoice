#!/usr/bin/env python3
"""Measure offline Persian product-name OCR on the four real receipt fixtures.

Images are cropped and recognized locally.  The optional engine packages/models
must be installed before this script starts; this program performs no downloads
and sends no image bytes to a network service.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("Pillow is required to crop the local receipt fixtures") from exc

ROOT = Path(__file__).resolve().parents[1]
SOURCE_INVOICES = ("29", "31", "32", "33")
TESSDATA_FAST_COMMIT = "87416418657359cb625c412a48b6e1d6d41c29bd"

# These six references are supplied provisionally by the existing visual report.
# They are not owner-confirmed.  The other 19 product-name crops have no supplied
# text reference and are retained as raw, unscored outputs only.
PROVISIONAL_REFERENCES: dict[str, str] = {
    "31_row0": "دستمال سفره تم",
    "32_row0": "دستمال سفره تم",
    "31_row1": "رد پا یا فلش تم",
    "32_row3": "رد پا یا فلش تم",
    "31_row2": "خلال کوچک",
    "33_row1": "خلال کوچک",
}

# These are the pre-existing, fixed table-cell insets from the visual crop
# experiment.  They are not changed based on OCR results.
X_INSET = 4
TOP_INSET = 8
BOTTOM_INSET = 3


@dataclass(frozen=True)
class CropRecord:
    crop_id: str
    invoice_id: str
    row_index: int
    bbox: tuple[int, int, int, int]
    unprocessed: Any
    otsu_binarized: Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_crops(repo_root: Path) -> list[CropRecord]:
    """Use the established dynamic projection/label agreement check to crop all 25 rows."""
    try:
        from run_name_cluster_experiment import (
            _geometry_for_invoice,
            _read_and_validate_inputs,
        )
        from image_extraction_adapter.preprocessing import otsu_binarize
    except Exception as exc:  # pragma: no cover - import-path configuration
        raise RuntimeError(
            "add the repository src/ directory to PYTHONPATH before running") from exc

    labels_path = repo_root / "tests" / "fixtures" / "real" / "labels.json"
    labels, labels_dir = _read_and_validate_inputs(labels_path)
    entries = {str(item["id"]): item for item in labels["invoices"]}
    if set(entries) != set(SOURCE_INVOICES):
        raise ValueError("N-01 requires real fixtures 29, 31, 32, and 33")

    crops: list[CropRecord] = []
    for invoice_id in SOURCE_INVOICES:
        entry = entries[invoice_id]
        image_path = labels_dir / entry["path"]
        geometry = _geometry_for_invoice(entry, image_path)
        if len(geometry.label_row_bands) != int(entry["row_count"]):
            raise ValueError(f"row count changed for invoice {invoice_id}")
        x_left, x_right = geometry.description_x
        with Image.open(image_path) as opened:
            opened.load()
            for row_index, (top, bottom) in enumerate(geometry.label_row_bands):
                box = (
                    int(round(x_left)) + X_INSET,
                    int(round(top)) + TOP_INSET,
                    int(round(x_right)) - X_INSET,
                    int(round(bottom)) - BOTTOM_INSET,
                )
                if box[2] <= box[0] or box[3] <= box[1]:
                    raise ValueError(
                        f"empty product-name crop for {invoice_id}_row{row_index}")
                # No changes beyond the table-cell crop in the unprocessed arm.
                unprocessed = opened.crop(box).copy()
                # One fixed, existing preprocessing path: grayscale/autocontrast,
                # per-image global Otsu binarization; no deskew, denoise, scaling,
                # or crop-specific parameter adjustment.
                otsu = otsu_binarize(unprocessed)
                crops.append(CropRecord(
                    crop_id=f"{invoice_id}_row{row_index}",
                    invoice_id=invoice_id,
                    row_index=row_index,
                    bbox=box,
                    unprocessed=unprocessed,
                    otsu_binarized=otsu,
                ))
    if len(crops) != 25:
        raise RuntimeError(f"expected 25 description crops; got {len(crops)}")
    return crops


def _normalise_for_comparison(text: str) -> str:
    """Minimal Persian comparison normalization; raw engine text is never altered."""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(str.maketrans({"ي": "ی", "ك": "ک"}))
    return " ".join(text.split())


def _levenshtein(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, 1):
        current = [left_index]
        for right_index, right_char in enumerate(right, 1):
            current.append(min(
                current[-1] + 1,
                previous[right_index] + 1,
                previous[right_index - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def _tesseract_engine(tessdata_dir: Path) -> tuple[Callable[[Any], dict[str, Any]], dict[str, Any]]:
    try:
        import tesserocr
    except Exception as exc:  # pragma: no cover - optional engine dependency
        raise RuntimeError("install the pinned tesserocr wheel") from exc
    model_path = tessdata_dir / "fas.traineddata"
    if not model_path.is_file():
        raise FileNotFoundError(f"missing Persian Tesseract model: {model_path}")

    def recognize(image: Any) -> dict[str, Any]:
        with tesserocr.PyTessBaseAPI(
            path=str(tessdata_dir),
            lang="fas",
            psm=tesserocr.PSM.SINGLE_LINE,
        ) as api:
            api.SetImage(image.convert("RGB"))
            text = api.GetUTF8Text() or ""
            try:
                confidence: float | None = float(api.MeanTextConf())
                if confidence < 0:
                    confidence = None
            except Exception:
                confidence = None
        return {"raw_text": text, "confidence": confidence, "segments": [text] if text else []}

    version = str(tesserocr.tesseract_version()).splitlines()[0]
    return recognize, {
        "engine": "Tesseract",
        "binding": f"tesserocr {importlib.metadata.version('tesserocr')}",
        "engine_version": version,
        "language": "fas",
        "traineddata_file": "fas.traineddata",
        "traineddata_source": (
            "tesseract-ocr/tessdata_fast@" + TESSDATA_FAST_COMMIT),
        "traineddata_sha256": _sha256(model_path),
        "page_segmentation_mode": "SINGLE_LINE",
    }


def _parisaocr_engine() -> tuple[Callable[[Any], dict[str, Any]], dict[str, Any]]:
    try:
        import torch
        import parisaocr
        from parisaocr import OCR
    except Exception as exc:  # pragma: no cover - optional engine dependency
        raise RuntimeError("install the pinned ParisaOCR package and dependencies") from exc

    # CPU-only inference is the intended CI/deployment path.  Bound PyTorch's
    # host thread pool so the same machine-independent request is run locally.
    torch.set_num_threads(1)
    reader = OCR(cpu=True)
    package_root = Path(parisaocr.__file__).resolve().parent
    recognizer = package_root / "models" / "parisaocr-fa-0.1.safetensors"
    detector = package_root / "models" / "ppocrv6-det-small.onnx"
    if not recognizer.is_file() or not detector.is_file():
        raise FileNotFoundError("ParisaOCR's bundled local model files are missing")

    def recognize(image: Any) -> dict[str, Any]:
        lines = reader.lines(image)
        segments = [str(line.text) for line in lines]
        text = "\n".join(segments)
        confidences = [float(line.conf) for line in lines if line.conf is not None]
        confidence = sum(confidences) / len(confidences) if confidences else None
        return {"raw_text": text, "confidence": confidence, "segments": segments}

    return recognize, {
        "engine": "ParisaOCR",
        "package_version": importlib.metadata.version("parisaocr"),
        "module_version": getattr(parisaocr, "__version__", None),
        "recognizer": "Kraken 7.1.1 / parisaocr-fa-0.1",
        "recognizer_sha256": _sha256(recognizer),
        "line_detector": "PP-OCRv6 small via RapidOCR/ONNX Runtime",
        "detector_sha256": _sha256(detector),
        "kraken_version": importlib.metadata.version("kraken"),
        "torch_version": torch.__version__,
        "device": "CPU",
        "cuda_available": bool(torch.cuda.is_available()),
        "network_downloads_during_inference": False,
    }


def _metrics(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    scored = [
        row for row in rows
        if row["preprocessing"] == variant and row["reference_name"] is not None
    ]
    matches = 0
    total_distance = 0
    reference_characters = 0
    for row in scored:
        predicted = _normalise_for_comparison(row["raw_text"])
        expected = _normalise_for_comparison(row["reference_name"])
        matches += predicted == expected
        total_distance += _levenshtein(predicted, expected)
        reference_characters += len(expected)
    all_rows = [row for row in rows if row["preprocessing"] == variant]
    hard_failures = sum(row["error"] is not None for row in all_rows)
    empty_outputs = sum(
        row["error"] is None and not _normalise_for_comparison(row["raw_text"])
        for row in all_rows
    )
    scored_empty = sum(
        row["error"] is None and not _normalise_for_comparison(row["raw_text"])
        for row in scored
    )
    return {
        "provisional_reference_crops": len(scored),
        "exact_name_matches": matches,
        "exact_name_rate": matches / len(scored) if scored else None,
        "character_error_count": total_distance,
        "reference_character_count": reference_characters,
        "character_error_rate": (
            total_distance / reference_characters if reference_characters else None),
        "hard_failures_all_crops": hard_failures,
        "empty_outputs_all_crops": empty_outputs,
        "hard_failures_scored_crops": sum(row["error"] is not None for row in scored),
        "empty_outputs_scored_crops": scored_empty,
        "total_crops": len(all_rows),
        "unscored_crops": len(all_rows) - len(scored),
    }


def run_experiment(
    repo_root: Path,
    tessdata_dir: Path,
    *,
    require_both_engines: bool = True,
) -> dict[str, Any]:
    crops = _load_crops(repo_root)
    variants = (
        ("unprocessed", lambda crop: crop.unprocessed),
        ("otsu_binarized", lambda crop: crop.otsu_binarized),
    )
    rows: list[dict[str, Any]] = []
    engine_info: dict[str, dict[str, Any]] = {}
    engine_errors: dict[str, str] = {}
    for engine_key, factory in (
        ("tesseract_fas", lambda: _tesseract_engine(tessdata_dir)),
        ("parisaocr", _parisaocr_engine),
    ):
        try:
            recognize, info = factory()
            engine_info[engine_key] = info
        except Exception as exc:
            engine_errors[engine_key] = f"{type(exc).__name__}: {exc}"
            if require_both_engines:
                raise RuntimeError(f"required engine {engine_key} unavailable: {exc}") from exc
            continue
        for crop in crops:
            for variant_name, image_for in variants:
                result: dict[str, Any]
                try:
                    result = recognize(image_for(crop))
                    raw_text = str(result.get("raw_text", ""))
                    confidence = result.get("confidence")
                    if confidence is not None:
                        confidence = round(float(confidence), 4)
                    segments = [str(item) for item in result.get("segments", [])]
                    error = None
                except Exception as exc:  # retain per-crop failures in the evidence
                    raw_text = ""
                    confidence = None
                    segments = []
                    error = f"{type(exc).__name__}: {exc}"
                rows.append({
                    "engine_key": engine_key,
                    "crop_id": crop.crop_id,
                    "invoice_id": crop.invoice_id,
                    "row_index": crop.row_index,
                    "crop_bbox": list(crop.bbox),
                    "preprocessing": variant_name,
                    "reference_name": PROVISIONAL_REFERENCES.get(crop.crop_id),
                    "reference_status": (
                        "PROVISIONAL_UNCONFIRMED"
                        if crop.crop_id in PROVISIONAL_REFERENCES else None),
                    "raw_text": raw_text,
                    "segments": segments,
                    "confidence": confidence,
                    "error": error,
                })

    if require_both_engines and len(engine_info) != 2:
        raise RuntimeError("both required OCR engines did not initialize")
    summary = {
        "experiment": "N-01 product-name crop OCR",
        "source_fixtures": list(SOURCE_INVOICES),
        "source_image_directory": "tests/fixtures/real",
        "reference_source": "docs/name-cluster-report.md",
        "reference_status": "Provisional visual mapping; not owner-confirmed",
        "all_product_name_crops": len(crops),
        "scored_product_name_crops": len(PROVISIONAL_REFERENCES),
        "unscored_product_name_crops": len(crops) - len(PROVISIONAL_REFERENCES),
        "metric_normalization": (
            "Unicode NFC; fold Arabic Yeh/Kaf to Persian Yeh/Kaf; collapse whitespace; "
            "no punctuation or other character removal"),
        "cer_definition": "micro-averaged Levenshtein code-point edits / reference code points",
        "preprocessing_variants": [
            "unprocessed: geometric crop only; source mode retained",
            "otsu_binarized: existing otsu_binarize helper (grayscale, autocontrast, per-crop Otsu); no resizing",
        ],
        "engine_info": engine_info,
        "engine_initialization_errors": engine_errors,
        "metrics": {
            engine_key: {
                variant: _metrics(
                    [row for row in rows if row["engine_key"] == engine_key], variant)
                for variant, _ in variants
            }
            for engine_key in engine_info
        },
        "raw_outputs": rows,
    }
    return summary


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# N-01 — Offline Persian Product-Name OCR Measurement",
        "",
        "> **Reference names are provisional and not owner-confirmed.** Only the six crops with supplied visual references are scored; all other crops are unscored.",
        "",
        "## Summary",
        "",
        f"- Source fixtures: {', '.join(summary['source_fixtures'])}.",
        f"- Product-name crops run per engine/variant: {summary['all_product_name_crops']}.",
        f"- Provisionally scored crops: {summary['scored_product_name_crops']}; unscored (no supplied reference): {summary['unscored_product_name_crops']}.",
        "- Metrics compare only the six crops with provisional references. Confidence values are retained for diagnostics and are not calibrated.",
        "",
        "## Engine and preprocessing metrics",
        "",
        "| Engine | Input | Exact names | CER | Hard failures (all / scored) | Empty outputs (all / scored) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for engine_key, variants in summary["metrics"].items():
        engine_name = summary["engine_info"][engine_key]["engine"]
        for variant, metric in variants.items():
            exact = (
                f"{metric['exact_name_matches']}/{metric['provisional_reference_crops']} "
                f"({metric['exact_name_rate'] * 100:.1f}%)"
                if metric["exact_name_rate"] is not None else "n/a")
            cer = (
                f"{metric['character_error_count']}/{metric['reference_character_count']} "
                f"({metric['character_error_rate'] * 100:.2f}%)"
                if metric["character_error_rate"] is not None else "n/a")
            lines.append(
                f"| {engine_name} | `{variant}` | {exact} | {cer} | "
                f"{metric['hard_failures_all_crops']} / {metric['hard_failures_scored_crops']} | "
                f"{metric['empty_outputs_all_crops']} / {metric['empty_outputs_scored_crops']} |")
    lines += [
        "",
        "## Method and boundaries",
        "",
        "- `labels.json` geometry and the existing projection checks define the product-description cells in real fixtures 29, 31, 32, and 33. The same 25 geometric crops are sent to both engines under both inputs.",
        "- `unprocessed` means the original pixel values after cropping the description cell only. `otsu_binarized` uses the repository's existing `otsu_binarize` helper: grayscale, autocontrast, one global Otsu threshold per crop. No crop-specific tuning, deskewing, denoising, or resizing was performed.",
        "- Tesseract uses the locally installed `fas` traineddata and `SINGLE_LINE` page segmentation. ParisaOCR runs its bundled PP-OCRv6-small line detector and Kraken Persian recognizer on CPU; its API's RTL/Unicode handling is part of that engine's output.",
        "- Comparison normalization is Unicode NFC, Arabic Yeh/Kaf folded to Persian Yeh/Kaf, and whitespace collapsed. No punctuation or other characters are removed. CER is a micro-average of Levenshtein code-point edits over the six provisional reference strings.",
        "- The fixture's numeric `labels.json` status does not confirm product names. The three repeated-name pairings come from `docs/name-cluster-report.md` and remain visual/unconfirmed. Nineteen additional crops have no supplied reference and are not scored.",
        "- Images are read from the checkout and remain local. Both engines and all model data are loaded locally; the runner performs no image upload or OCR network request.",
        "",
        "## Installed engines and local model identifiers",
        "",
    ]
    for engine_key, info in summary["engine_info"].items():
        lines.append(f"### {info['engine']}")
        lines.append("")
        for key, value in info.items():
            if key == "engine":
                continue
            lines.append(f"- `{key}`: `{value}`.")
        lines.append("")
    lines += [
        "## Raw outputs",
        "",
        "Every crop/engine/input result is listed below. `raw_text` is JSON-quoted so trailing newlines, tabs, and empty output remain visible. The original raw values and error strings are also preserved in the companion JSON file.",
        "",
        "| Engine | Crop | Provisional reference | Input | Raw engine output | Confidence (diagnostic only) | Error |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in summary["raw_outputs"]:
        engine_name = summary["engine_info"].get(
            row["engine_key"], {"engine": row["engine_key"]})["engine"]
        reference = row["reference_name"] or "— (unscored)"
        raw = json.dumps(row["raw_text"], ensure_ascii=False)
        error = row["error"] or "—"
        confidence = "—" if row["confidence"] is None else f"{row['confidence']:.2f}"
        cells = [engine_name, row["crop_id"], reference, row["preprocessing"], raw, confidence, error]
        escaped = [str(value).replace("|", "\\|").replace("\n", " ") for value in cells]
        lines.append("| " + " | ".join(escaped) + " |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--tessdata-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument(
        "--allow-engine-errors",
        action="store_true",
        help="record initialization errors instead of requiring both engines",
    )
    args = parser.parse_args(argv)
    summary = run_experiment(
        args.repo_root.resolve(),
        args.tessdata_dir.resolve(),
        require_both_engines=not args.allow_engine_errors,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.output_markdown.write_text(
        render_markdown(summary), encoding="utf-8", newline="\n")
    print(json.dumps({
        "json": str(args.output_json),
        "markdown": str(args.output_markdown),
        "metrics": summary["metrics"],
        "engine_initialization_errors": summary["engine_initialization_errors"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
