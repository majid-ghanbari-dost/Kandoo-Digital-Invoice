# Holoo cell preprocessing comparison

**Evidence class: one user-supplied cleaned invoice image; exploratory OCR benchmark.**
The values below are raw OCR outputs plus a manually inspected visual reference
used only to compute metrics. The reference has not been confirmed by the invoice
owner; it is not injected into the parser or used to correct a field. Frozen
contracts D-01–D-09 were not changed.

## Setup

- Image: `holo_row_detection.png`
- SHA-256: `61d6d16594ca35d622099ad5c453292d0279127ee65744ce784952b3a781586a`
- Image dimensions: 576 × 1296 pixels
- OCR: Tesseract 5.5.1 / `tesserocr` 2.11.0 / language `fas+eng`
- Full-page TSV: 85 word records; mean confidence `71.0663`; minimum `0.0`
- Cell regions were cropped from the detected column boundaries and row bands,
  with a 4 px horizontal inset and 8 px top / 3 px bottom inset to keep table
  rules out of the text interior. The original image file is read-only.
- Numeric OCR used PSM 7 and whitelist
  `0123456789۰۱۲۳۴۵۶۷۸۹.,`. Item-description OCR used PSM 7 with no numeric
  whitelist. Otsu/adaptive variants ran directional morphological opening to
  detect and remove long horizontal/vertical rules before OCR.
- Scale factor: 3×; white OCR padding: 8 px; field review threshold: 60.
- Numeric cells scored: four quantities, four line totals, and the payable
  amount (9 total).

## Reference and measured result

For scoring only, the image was visually transcribed as quantities `۱` in all
four rows; line totals `۱,۴۵۰,۰۰۰`, `۴,۸۷۰,۰۰۰`, `۵۷۰,۰۰۰`, `۵۷۰,۰۰۰`; and
payable `۷,۴۶۰,۰۰۰`. These are provisional manual references, not accepted
invoice fields.

| Method | Exact digit-cell matches | Exact-cell error rate | Digit CER |
|---|---:|---:|---:|
| Cell crop, no threshold (`none`) | 1/9 | 88.89% | 67.57% |
| Otsu + morphological line removal | 4/9 | 55.56% | 56.76% |
| Adaptive threshold + morphological line removal | 4/9 | 55.56% | 56.76% |
| Existing full-page spatial OCR | 0/9 | 100.00% | 54.05% |

Exact-cell/CER scoring maps Persian, Arabic-Indic, and ASCII digit scripts and
ignores punctuation/spacing **for the metric only**. OCR strings are not
normalized in the adapter. Because the full-page baseline has a slightly lower
CER while Otsu/adaptive improve exact cell count, there is no single winner on
both metrics.

Otsu and adaptive produced identical numeric strings on this image. They
improved the quantity candidates (4/4 digit matches versus 1/4 for the raw cell
crop), but the unrestricted crop OCR disagreed on three quantities, so those
candidates remain `REVIEW`. None of the five monetary cells (four line totals
plus payable) matched the visual reference in any cell preprocessing mode.

### Raw cell outputs

The outputs below are not corrected or promoted into invoice fields:

| Field | Reference (scoring only) | None | Otsu | Adaptive |
|---|---|---|---|---|
| `line.0.quantity` | `۱` | `۱` | `۱` | `۱` |
| `line.0.total` | `۱,۴۵۰,۰۰۰` | `۱` | `۱ ۵۰` | `۱ ۵۰` |
| `line.1.quantity` | `۱` | `7` | `۱` | `۱` |
| `line.1.total` | `۴,۸۷۰,۰۰۰` | `۴۷۰` | `۴۷۰` | `۴۷۰` |
| `line.2.quantity` | `۱` | `7` | `۱` | `۱` |
| `line.2.total` | `۵۷۰,۰۰۰` | `۸۷۰` | `۸۷۰` | `۸۷۰` |
| `line.3.quantity` | `۱` | `7` | `۱` | `۱` |
| `line.3.total` | `۵۷۰,۰۰۰` | `۸۷۰` | `۸۷۰` | `۸۷۰` |
| `invoice.payable` | `۷,۴۶۰,۰۰۰` | `۷۳۶۰` | `۷۳۰` | `۷۳۰` |

All 27 numeric cell-variant records remain `REVIEW`: full-page fields were
already under review; some variants fall below confidence 60, some fail the
numeric format, and the whitelisted quantity values in rows 2–4 disagree with
the unrestricted diagnostic OCR (`7`). The full-page raw quantities still
include `|`, `٩‏`, and `!|`; those are invalid and were not changed into digits.

**Answer to the amount question:** No. The first row's manual visual reference
appears to be `۱,۴۵۰,۰۰۰` (not `۴۵۰۰`); the cell variants returned `۱` or the
invalid raw string `۱ ۵۰`. The other line amounts and payable were also
truncated/misread. No reliable amount was recovered and no automatic correction
was attempted.

## Decision and issuance boundary

- Otsu/adaptive tie for the best exact-cell score, but neither recovered any
  monetary field. Their CER is also slightly worse than the full-page baseline.
- Keep Otsu as the simpler candidate for further experiments only; do not accept
  it (or adaptive) as an issuance source on this image. All raw cells remain
  `REVIEW` until independently verified.
- The benchmark runner returned `ImageExtractionReviewRequired` and calls
  `extract()` only. Separately, `submit_image()` was exercised with a counting
  wrapper around the real workspace service: `IssuanceService.submit` calls = 0
  and no Digital Invoice was created. See
  `cell-preprocessing-issuance-guard.log`.

Detailed per-cell output, confidence, whitelist, crop boxes, and pixel removal
counts are retained in `cell-preprocessing-benchmark.log`. Reproduce with:

```sh
PYTHONPATH=/tmp/kandoo-ocr-runtime:src PYTHONDONTWRITEBYTECODE=1 \
  python3 src/run_image_preprocessing_benchmark.py \
  --image deliveries/image-extraction-ocr/holo_row_detection.png \
  --tessdata-dir /tmp/kandoo-ocr-runtime/share/tessdata \
  --language fas+eng --minimum-confidence 60
```
