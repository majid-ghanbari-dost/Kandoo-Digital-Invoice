"""Compare cell-level OCR preprocessing on the user-supplied Holoo image.

This diagnostic does not submit to IssuanceService. The visual reference values
are kept here only for offline error scoring; they are never fed back into OCR,
field values, or the adapter's review decision.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from image_extraction_adapter import (  # noqa: E402
    ImageExtractionAdapter,
    ImageExtractionReviewRequired,
    NUMERIC_TESSERACT_WHITELIST,
    PERSIAN_TESSERACT_LANGUAGE,
    TesseractOCR,
)

# Human visual reference transcription from the image's numeric cells. This is
# an evaluation fixture only, not an OCR correction rule or canonical payload.
VISUAL_REFERENCE = {
    "line.0.quantity": "۱",
    "line.0.total": "۱,۴۵۰,۰۰۰",
    "line.1.quantity": "۱",
    "line.1.total": "۴,۸۷۰,۰۰۰",
    "line.2.quantity": "۱",
    "line.2.total": "۵۷۰,۰۰۰",
    "line.3.quantity": "۱",
    "line.3.total": "۵۷۰,۰۰۰",
    "invoice.payable": "۷,۴۶۰,۰۰۰",
}
_DIGITS_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def _digit_sequence(value: str) -> str:
    normalized = value.translate(_DIGITS_TRANSLATION)
    return "".join(char for char in normalized if char.isdigit())


def _levenshtein(left: str, right: str) -> int:
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


def _scores(values: dict[str, str]) -> tuple[int, int, float, float]:
    exact = 0
    edits = 0
    expected_chars = 0
    for field_name, expected_raw in VISUAL_REFERENCE.items():
        expected = _digit_sequence(expected_raw)
        observed = _digit_sequence(values.get(field_name, ""))
        exact += observed == expected
        edits += _levenshtein(observed, expected)
        expected_chars += len(expected)
    count = len(VISUAL_REFERENCE)
    exact_error_rate = 100.0 * (count - exact) / count
    character_error_rate = 100.0 * edits / max(expected_chars, 1)
    return exact, count, exact_error_rate, character_error_rate


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image", type=Path,
        default=Path("deliveries/image-extraction-ocr/holo_row_detection.png"),
    )
    parser.add_argument(
        "--tessdata-dir", type=Path, required=True,
        help="Tesseract traineddata directory",
    )
    parser.add_argument("--language", default=PERSIAN_TESSERACT_LANGUAGE)
    parser.add_argument("--minimum-confidence", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = _args()
    image = args.image.resolve()
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    backend = TesseractOCR(
        tessdata_dir=args.tessdata_dir,
        language=args.language,
    )
    extraction = ImageExtractionAdapter(
        backend,
        minimum_word_confidence=args.minimum_confidence,
    ).extract(image)
    print("evidence.class=User-supplied image; benchmark only; no issuance")
    print(f"image.path={args.image}")
    print(f"image.sha256={digest}")
    print(f"ocr.language={args.language}")
    print(f"ocr.minimum_field_confidence={args.minimum_confidence}")
    print(f"outcome={type(extraction).__name__}")
    if not isinstance(extraction, ImageExtractionReviewRequired):
        print(f"outcome.reason={getattr(extraction, 'reason', 'unexpected ready result')}")
        return 2

    print(f"ocr.engine={extraction.ocr.engine}")
    print(f"ocr.word_count={len(extraction.ocr.word_confidences)}")
    print(f"ocr.mean_confidence={extraction.ocr.mean_confidence}")
    print(f"ocr.minimum_confidence={extraction.ocr.minimum_confidence}")
    print(f"spatial.column_boundaries={extraction.spatial_column_boundaries}")
    print(f"spatial.row_bands={extraction.spatial_row_bands}")
    print("reference.provenance=manual visual transcription; not user-confirmed; scoring only")
    print("reference.values=")
    for field_name, value in VISUAL_REFERENCE.items():
        print(f"  {field_name}={value}")
    print("adapter.original_numeric_fields=")
    assessments = {item.field_name: item for item in extraction.field_assessments}
    for field_name in VISUAL_REFERENCE:
        item = assessments.get(field_name)
        raw = item.raw_value if item else ""
        status = item.status if item else "REVIEW"
        print(f"  {field_name}={raw!r} [{status}]")

    variants = [
        item for item in extraction.cell_ocr_variants
        if item.field_name in VISUAL_REFERENCE and item.whitelist is not None
    ]
    modes = ("none", "otsu", "adaptive")
    result_values: dict[str, dict[str, str]] = {mode: {} for mode in modes}
    print("numeric_cell_variants=")
    for item in variants:
        result_values[item.preprocessing][item.field_name] = item.raw_value
        expected = VISUAL_REFERENCE[item.field_name]
        matches = _digit_sequence(item.raw_value) == _digit_sequence(expected)
        print(
            f"  {item.field_name}|{item.preprocessing}|raw={item.raw_value!r}|"
            f"confidence={item.confidence}|status={item.status}|"
            f"unrestricted={item.unrestricted_raw_value!r}|"
            f"line_pixels_removed={item.line_pixels_removed}|"
            f"psm={item.psm}|whitelist={item.whitelist!r}|"
            f"digits_match_reference={matches}|reason={item.reason!r}"
        )

    print("text_cell_config=")
    for item in extraction.cell_ocr_variants:
        if item.field_name.endswith(".description"):
            print(
                f"  {item.field_name}|raw={item.raw_value!r}|confidence={item.confidence}|"
                f"status={item.status}|psm={item.psm}|whitelist={item.whitelist!r}"
            )

    print("metric.definition=exact match and CER on digit strings after Persian/Arabic/ASCII digit-script mapping; separators ignored for scoring only")
    print("metric.note=OCR output itself is preserved unchanged; these scores never repair or replace a field")
    for mode in modes:
        exact, count, exact_error_rate, cer = _scores(result_values[mode])
        print(
            f"metrics.{mode}.exact_digit_cells={exact}/{count} "
            f"exact_cell_error_rate={exact_error_rate:.2f}% "
            f"digit_CER={cer:.2f}%"
        )

    baseline = {
        field_name: assessments[field_name].raw_value
        for field_name in VISUAL_REFERENCE
        if field_name in assessments
    }
    exact, count, exact_error_rate, cer = _scores(baseline)
    print(
        f"metrics.full_page_spatial_baseline.exact_digit_cells={exact}/{count} "
        f"exact_cell_error_rate={exact_error_rate:.2f}% "
        f"digit_CER={cer:.2f}%"
    )
    print(f"tesseract.numeric_whitelist={NUMERIC_TESSERACT_WHITELIST!r}")
    print("issuance.submit_calls=0")
    print("digital_invoice=NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
