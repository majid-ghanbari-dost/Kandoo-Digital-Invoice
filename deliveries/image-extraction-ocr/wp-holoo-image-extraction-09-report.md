# WP-HOLOO-IMAGE-EXTRACTION-09 — Dynamic Layout and Glyph Evaluation

## Scope and guardrails

`crop_spatial_cells()` now prefers image-projection geometry and uses TSV geometry only as a compatibility fallback if projection detection fails. `GlyphClassifierOCR` remains test-only and is **not** connected to `adapter.py` or the issuance path. Frozen contracts D-01–D-09 were not changed.

The label strings below were transcribed visually and marked **Provisional** in both JSON files; the invoice owner has not confirmed them. All reported OCR scores are exploratory and not trusted ground truth.

## Dynamic layout projection

The detector binarizes a copy with Pillow/Otsu, finds contiguous horizontal and vertical black runs at least 80% of the longest run on that axis, selects the longest median-spaced horizontal chain, excludes the shorter table-header interval, and filters row bands around the median body-row height. The vertical projection is restricted to the selected table span. This rejects the nearby rounded payable-box top/bottom borders without fixed page coordinates or a configured row count.

| Input image | Dimensions | Detected item rows | Vertical rules | Cell crops (amount, quantity, description) | Median row height | Result |
|---|---:|---:|---:|---:|---:|---|
| `holo_row_detection.png` | 576 × 1296 | 4 | 5 | 12 | 68.5 px | PASS |
| `5.png` | 576 × 1368 | 5 | 5 | 15 | 68.0 px | PASS |
| `13.png` | 576 × 1680 | 13 | 5 | 39 | 68.0 px | PASS |

All three images produced boundaries `(116, 244, 293, 487, 527)` in the sampled rasters. The selected horizontal sequences end at y=801, y=868, and y=1412 respectively; the short rounded-payable border candidates are excluded by spacing/median filtering. Full output and source hashes: `dynamic-layout-projection.log`.

## Glyph template build and evaluation split

`labels_build.json` uses the four-row and five-row receipts plus a cropped set of rows 3–8 from the 13-row image. The separate crop is included at `glyph-classifier-build-13-rows03-08.png`; these six rows are omitted from the evaluation labels. The row template profile contains every Persian digit ۰–۹ and comma. Payable templates were built from the four- and five-row receipts where segmentation matched; the 13-row payable uses those templates with the row profile fallback.

The 13-row evaluation processes all 13 rows, but exact scoring is limited to rows 0–2 and 9–12 plus payable (15 labelled cells). This is a disjoint-row holdout within the same invoice, **not** independent-invoice validation. The `payable_bbox` in `labels_eval.json` is `[199, 1431, 147, 28]` (left, top, width, height), from the Adapter spatial `FieldAssessment`; its Adapter raw payable was `۳۴۷,۹۲۰,۰۰۰`.

Results:

- `exact_digit_cells`: **12/15** (digit CER 10.00%). The mismatches are the first row's quantity, line 9 total, and payable.
- Statuses across all 27 returned numeric cells: **12 EXTRACTED, 15 REVIEW**.
- **EXTRACTED but wrong:** 0 against the available provisional visual labels. All 12 extracted values are quantities; monetary cells are held in REVIEW by the arithmetic gate.
- **Arithmetic Gate: FAIL (0/1).** `line.9.total` was emitted as `??۹,۶۰۰,۰۰۰`, not a well-formed amount, so the payable cross-check could not pass. The payable glyph read was also rejected and remains REVIEW.

Verbatim CLI output: `glyph-classifier-evaluate-13row-3invoice-build.log`. Build output: `glyph-classifier-build-3invoices.log`. The diagnostic output is not a production accuracy claim and does not promote any field into the adapter.

## Validation

- Focused image-adapter suite: **21 passed**, plus **6 subtests**.
- Full repository suite: **1,715 passed**, plus **6 subtests**.
- Projection benchmark: **PASS** on the supplied 4-, 5-, and 13-row images.
- Temporary Pillow/tesserocr/pytest packages and Tesseract traineddata remained under `/tmp/kandoo-glyph-runtime`; no runtime dependency was added to the repository.
