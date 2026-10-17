# B2-1 — Payable-cell segmentation diagnosis

**Scope:** diagnosis only. No production code or segmentation behavior was changed. No Tesseract binary/API was run or installed, and no real-image `ImageExtractionAdapter.extract()` call was made.

## Method and bbox provenance

The label file is `tests/fixtures/real/labels.json`. Its `payable_bbox` entries are reference annotations around the payable amount, in `[x, y, width, height]` form. The offline Glyph build/evaluate path uses that reference bbox and then calls `crop_spatial_cells`; its default payable padding is 4 pixels.

The *runtime adapter* does not derive the payable bbox from projection geometry or a fixed page offset. The code path is:

1. `adapter.py::_primary_numeric_review()` calls `parse_invoice_geometry()` with the full-page OCR result.
2. `parser.py::_labeled_value_words()` finds same-line OCR words matching the Persian payable label (`مبلغ`, `قابل`, `پرداخت`) and selects numeric OCR words left of the label. It uses OCR word positions and a 32-pixel y tolerance.
3. `parser.py::_assessment()` obtains the field bbox from `_bbox()`—the union of the selected OCR word boxes.
4. `ocr.py::recognize_spatial_cells()` calls `crop_spatial_cells()`. That crops the assessment bbox with the default 4-pixel payable padding. Projection geometry supplies item-table rows/columns, not the payable bbox.

No Tesseract word boxes are stored with these fixtures, and Tesseract was not run for B2-1. Therefore the *live runtime* payable bbox cannot be reported honestly here. The coordinates below are the labeled reference bboxes used by the offline Glyph fixtures, plus the cropper's 4-pixel padding; they are not represented as measured Tesseract runtime boxes.

### Analysis procedure

- Expected symbol count = Persian/ASCII digits plus comma separators in the labeled value.
- For each `labels.json` reference bbox, the script obtains the payable crop using `crop_spatial_cells(..., payable_padding=4)`. The printed crop coordinates are original-image coordinates with right/bottom exclusive.
- It reports three connected-component counts: a raw grayscale threshold control (`pixel < 128`), Otsu threshold only, and the actual Glyph training preprocessing path (Otsu plus morphological table-line removal). The last uses `preprocess_cell(crop, "otsu")`.
- The component pass uses 8-connectivity, drops components under 4 pixels and narrow full-height rules, then applies the same x-overlap merge rule as the Glyph segmenter (overlap ratio at least 0.70). Bboxes in the component tables are crop-relative `[x, y, width, height]`; right/bottom edges are exclusive. Pixel count is foreground pixels after preprocessing.
- Reproduce the report with:

  ```sh
  PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python scripts/diagnose_payable.py
  ```

  Optional paths can be supplied with `--image PATH` (repeatable) and `--labels PATH`.

## Summary

| Invoice | Image | Labeled payable | Reference bbox `[x,y,w,h]` | Analyzed crop `[left,top,right,bottom)` | Expected | Raw / Otsu-only | Otsu + line removal | Delta |
|---:|---|---|---|---|---:|---:|---:|---:|
| 29 | `29.png` | `۷,۴۶۰,۰۰۰` | `[214,820,116,28]` | `[210,816,334,852)` | 9 | 9 / 9 | 10 | +1 |
| 31 | `31.png` | `۲,۴۲۵,۰۰۰` | `[214,752,116,28]` | `[210,748,334,784)` | 9 | 9 / 9 | 12 | +3 |
| 32 | `32.png` | `۷,۸۵۰,۰۰۰` | `[214,888,116,28]` | `[210,884,334,920)` | 9 | 9 / 9 | 9 | 0 |
| 33 | `33.png` | `۳۴۷,۹۲۰,۰۰۰` | `[199,1431,147,28]` | `[195,1427,350,1463)` | 11 | 11 / 11 | 15 | +4 |

All analyzed crops are 36 pixels high. The label file names invoice #32 as `32.png` (there is no `5.png` in this fixture directory). The #31 payable label carries the note `DERIVED_FROM_ARITHMETIC`: its expected value is not an independent operator-confirmed visual label.

## Per-invoice component details

### Invoice #29 — `29.png`

- Payable: `۷,۴۶۰,۰۰۰`; expected 9 symbols.
- Reference bbox source: `labels.json`, `[214,820,116,28]`.
- Analyzed crop: `[210,816,334,852)` = `[210,816,124,36]` in `[x,y,w,h]` form.
- Counts: raw threshold 9; Otsu-only 9; Otsu + line removal 10. The line-removal pass reports 43 removed foreground pixels.
- Result: +1 component. The vertical removal mask is `[34,6,36,28)` in crop-relative `[left,top,right,bottom)` coordinates; it splits the Otsu-only component `[29,4,15,24]` into post-cleanup components 03 and 04 (`[29,5,5,18]` and `[36,4,8,22]`). They occupy one expected numeral position. No merged glyph is apparent.

| # | Crop-relative bbox `[x,y,w,h]` | Pixels | Width | Height |
|---:|---|---:|---:|---:|
| 01 | `[4,4,15,24]` | 158 | 15 | 24 |
| 02 | `[22,20,6,12]` | 48 | 6 | 12 |
| 03 | `[29,5,5,18]` | 46 | 5 | 18 |
| 04 | `[36,4,8,22]` | 64 | 8 | 22 |
| 05 | `[46,4,14,24]` | 145 | 14 | 24 |
| 06 | `[64,14,9,9]` | 41 | 9 | 9 |
| 07 | `[77,20,6,12]` | 48 | 6 | 12 |
| 08 | `[85,14,9,9]` | 41 | 9 | 9 |
| 09 | `[98,14,9,9]` | 41 | 9 | 9 |
| 10 | `[111,14,9,9]` | 41 | 9 | 9 |

### Invoice #31 — `31.png`

- Payable: `۲,۴۲۵,۰۰۰`; expected 9 symbols. The label is derived from the confirmed line-item sum, not independent visual confirmation.
- Reference bbox source: `labels.json`, `[214,752,116,28]`.
- Analyzed crop: `[210,748,334,784)` = `[210,748,124,36]` in `[x,y,w,h]` form.
- Counts: raw threshold 9; Otsu-only 9; Otsu + line removal 12. The line-removal pass reports 127 removed foreground pixels.
- Result: +3 components. The vertical removal mask bbox is `[9,6,51,28)` in crop-relative coordinates. It splits Otsu-only components 01, 03, and 04 into post-cleanup pairs 01+02, 04+05, and 06+07, respectively. Each pair occupies one expected numeral position. No merged glyph is apparent.

| # | Crop-relative bbox `[x,y,w,h]` | Pixels | Width | Height |
|---:|---|---:|---:|---:|
| 01 | `[4,5,5,18]` | 46 | 5 | 18 |
| 02 | `[11,4,6,21]` | 51 | 6 | 21 |
| 03 | `[20,20,6,12]` | 48 | 6 | 12 |
| 04 | `[27,5,5,18]` | 46 | 5 | 18 |
| 05 | `[34,4,8,22]` | 64 | 8 | 22 |
| 06 | `[44,5,5,18]` | 46 | 5 | 18 |
| 07 | `[51,4,6,21]` | 51 | 6 | 21 |
| 08 | `[59,4,14,24]` | 184 | 14 | 24 |
| 09 | `[77,20,6,12]` | 48 | 6 | 12 |
| 10 | `[85,14,9,9]` | 41 | 9 | 9 |
| 11 | `[98,14,9,9]` | 41 | 9 | 9 |
| 12 | `[111,14,9,9]` | 41 | 9 | 9 |

### Invoice #32 — `32.png`

- Payable: `۷,۸۵۰,۰۰۰`; expected 9 symbols.
- Reference bbox source: `labels.json`, `[214,888,116,28]`.
- Analyzed crop: `[210,884,334,920)` = `[210,884,124,36]` in `[x,y,w,h]` form.
- Counts: raw threshold 9; Otsu-only 9; Otsu + line removal 9. No foreground pixels were removed by the line-removal pass.
- Result: count matches. The line-removal mask is empty (bbox `None`); this is the only payable crop among the four with a clean count under the current preprocessing. Count agreement alone does not prove classification correctness. No split or merged glyph is apparent.

| # | Crop-relative bbox `[x,y,w,h]` | Pixels | Width | Height |
|---:|---|---:|---:|---:|
| 01 | `[4,4,15,24]` | 158 | 15 | 24 |
| 02 | `[22,20,6,12]` | 48 | 6 | 12 |
| 03 | `[29,4,15,24]` | 160 | 15 | 24 |
| 04 | `[46,4,14,24]` | 184 | 14 | 24 |
| 05 | `[64,14,9,9]` | 41 | 9 | 9 |
| 06 | `[77,20,6,12]` | 48 | 6 | 12 |
| 07 | `[85,14,9,9]` | 41 | 9 | 9 |
| 08 | `[98,14,9,9]` | 41 | 9 | 9 |
| 09 | `[111,14,9,9]` | 41 | 9 | 9 |

### Invoice #33 — `33.png`

- Payable: `۳۴۷,۹۲۰,۰۰۰`; expected 11 symbols.
- Reference bbox source: `labels.json`, `[199,1431,147,28]`.
- Analyzed crop: `[195,1427,350,1463)` = `[195,1427,155,36]` in `[x,y,w,h]` form.
- Counts: raw threshold 11; Otsu-only 11; Otsu + line removal 15. The line-removal pass reports 209 removed foreground pixels.
- Result: +4 components. The vertical removal mask bbox is `[8,4,85,28)` in crop-relative coordinates. It splits Otsu-only components 01, 02, 05, and 06 into post-cleanup pairs 01+02, 03+04, 07+08, and 09+10, respectively. Each pair occupies one expected numeral position. No merged glyph is apparent.

| # | Crop-relative bbox `[x,y,w,h]` | Pixels | Width | Height |
|---:|---|---:|---:|---:|
| 01 | `[4,4,4,14]` | 32 | 4 | 14 |
| 02 | `[11,5,9,19]` | 71 | 9 | 19 |
| 03 | `[22,5,5,18]` | 46 | 5 | 18 |
| 04 | `[29,4,8,22]` | 64 | 8 | 22 |
| 05 | `[39,4,15,24]` | 158 | 15 | 24 |
| 06 | `[57,20,6,12]` | 48 | 6 | 12 |
| 07 | `[65,4,6,13]` | 54 | 6 | 13 |
| 08 | `[74,7,2,21]` | 22 | 2 | 21 |
| 09 | `[78,5,5,18]` | 46 | 5 | 18 |
| 10 | `[85,4,6,21]` | 51 | 6 | 21 |
| 11 | `[94,14,9,9]` | 41 | 9 | 9 |
| 12 | `[107,20,6,12]` | 48 | 6 | 12 |
| 13 | `[116,14,9,9]` | 41 | 9 | 9 |
| 14 | `[129,14,9,9]` | 41 | 9 | 9 |
| 15 | `[142,14,9,9]` | 41 | 9 | 9 |

## Root cause

The component-count ablation isolates the failure: the raw-threshold and Otsu-only counts equal the expected symbol count on **all four** labeled crops. The excess appears only after Otsu's morphological table-line removal: #29 changes 9→10, #31 9→12, and #33 11→15. #32 removes no pixels and stays at 9.

The line-removal implementation performs directional morphological openings. For these 36-pixel-high crops, its vertical kernel is `max(15, int(36 * 0.55)) = 19` pixels. Inspection of the actual masks found **zero horizontal-mask pixels** removed and respectively **43, 127, 0, and 209 vertical-mask pixels** removed for #29, #31, #32, and #33. That vertical mask overlaps tall/narrow numeral strokes in the payable amounts and breaks connected glyphs into multiple components. The effect is not caused by an overly broad label crop, payable-label text, or table projection: the reference crops are amount-only regions, and the raw/Otsu controls already have the expected counts. No merged glyph is evident in the listed components; the observed mismatch is over-segmentation.

This is a likely root cause for the B2-1 fixtures, not a claim about runtime Tesseract crop coordinates, which were unavailable.

## B2-2 recommendations (future work; not implemented here)

1. **Gate or omit vertical rule removal for payable crops.** First test the amount-only crop without the vertical morphological mask; the current ablation suggests that is the most direct change to evaluate. Keep actual table-rule removal where rules exist, rather than treating every tall vertical stroke as a rule.
2. **Add a focused regression/ablation test** over all four fixtures that records raw, Otsu-only, and post-line-removal component counts and verifies that preprocessing does not create new splits for these labeled amounts. Include additional held-out invoice samples before generalizing the behavior.
3. **Keep per-glyph diagnostics and fail-closed handling.** Review component masks/bboxes around the removed vertical pixels; do not infer or repair a payable value from arithmetic. If future samples still have split or touching glyphs without line removal, evaluate a geometry-aware component grouping/splitting strategy rather than assuming every connected component is one symbol.
4. **Capture live bbox evidence when a Tesseract-enabled test environment is available.** Compare the runtime OCR-word union and its 4-pixel crop against these label-reference bboxes before treating them as interchangeable.

B2-1 makes no proposed production change; implementation and verification belong to B2-2.
