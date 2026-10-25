# N-01 — Offline Persian Product-Name OCR Measurement

**Measured:** 2026-10-25, locally on Debian 12 / Python 3.11.2 / Pillow 13.0.0 / x86-64, CPU inference.

**Reproducer:** [`scripts/run_n01_name_reading.py`](../scripts/run_n01_name_reading.py); pinned engine dependencies are in [`scripts/n01-ocr-requirements.txt`](../scripts/n01-ocr-requirements.txt), and the manual CI workflow is [`.github/workflows/n01-name-reading.yml`](../.github/workflows/n01-name-reading.yml).

**Raw machine-readable evidence:** [`docs/n01-name-reading.json`](n01-name-reading.json).

> **Reference names are provisional and not owner-confirmed.** Only the six crops with supplied visual references are scored; all other crops are unscored.

## Summary

- Source fixtures: 29, 31, 32, 33.
- Product-name crops run per engine/variant: 25.
- Provisionally scored crops: 6; unscored (no supplied reference): 19.
- Metrics compare only the six crops with provisional references. Confidence values are retained for diagnostics and are not calibrated.

## Engine and preprocessing metrics

| Engine | Input | Exact names | CER | Hard failures (all / scored) | Empty outputs (all / scored) |
|---|---|---:|---:|---:|---:|
| Tesseract | `unprocessed` | 2/6 (33.3%) | 8/76 (10.53%) | 0 / 0 | 3 / 0 |
| Tesseract | `otsu_binarized` | 2/6 (33.3%) | 8/76 (10.53%) | 0 / 0 | 3 / 0 |
| ParisaOCR | `unprocessed` | 4/6 (66.7%) | 2/76 (2.63%) | 0 / 0 | 0 / 0 |
| ParisaOCR | `otsu_binarized` | 4/6 (66.7%) | 2/76 (2.63%) | 0 / 0 | 0 / 0 |

## Operator-confirmation verdict

- **ParisaOCR: usable as an operator-confirmation suggestion only.** It returned non-empty output for all six provisionally referenced crops; 4/6 matched exactly, and the other two differed only by the missing space in `رد پا` (`ردپا`). The micro-CER was 2/76 characters (2.63%). Show the source crop alongside every suggestion and require an operator to confirm or correct it. Do not auto-accept, auto-fill, classify, or trigger stock/issuance actions from OCR output. This is a small, provisional sample—not owner-confirmed accuracy evidence.
- **Tesseract `fas`: not usable as the operator-confirmation suggestion engine on this sample.** It matched 2/6 names exactly and had 8/76 character edits (10.53% CER). The other supplied names were read as `دستمال سغره تم` and `ردپا با فلش قم`; the latter changes multiple characters. Its three empty outputs were among the 19 unscored crops. Treat it as an experimental baseline, not as a name suggestion to operators. Tesseract confidence is uncalibrated and does not override this verdict.
- Otsu binarization changed **none** of the 50 crop/engine pairs: each crop's raw and Otsu output was identical, so exact-name rate and CER did not improve.

## Method and boundaries

- `labels.json` geometry and the existing projection checks define the product-description cells in real fixtures 29, 31, 32, and 33. The same 25 geometric crops are sent to both engines under both inputs.
- `unprocessed` means the original pixel values after cropping the description cell only. `otsu_binarized` uses the repository's existing `otsu_binarize` helper: grayscale, autocontrast, one global Otsu threshold per crop. No crop-specific tuning, deskewing, denoising, or resizing was performed.
- Tesseract uses the locally installed `fas` traineddata and `SINGLE_LINE` page segmentation. ParisaOCR runs its bundled PP-OCRv6-small line detector and Kraken Persian recognizer on CPU; its API's RTL/Unicode handling is part of that engine's output. ParisaOCR's model card describes training on printed books and synthetic lines, not receipts; this small fixture result does not establish broader invoice accuracy.
- Comparison normalization is Unicode NFC, Arabic Yeh/Kaf folded to Persian Yeh/Kaf, and whitespace collapsed. No punctuation or other characters are removed. CER is a micro-average of Levenshtein code-point edits over the six provisional reference strings.
- The fixture's numeric `labels.json` status does not confirm product names. The three repeated-name pairings come from `docs/name-cluster-report.md` and remain visual/unconfirmed. Nineteen additional crops have no supplied reference and are not scored.
- Images are read from the checkout and remain local. Both engines and all model data are loaded locally; the runner performs no image upload or OCR network request.

## Installed engines and local model identifiers

### Tesseract

- `binding`: `tesserocr 2.12.0`.
- `engine_version`: `tesseract 5.5.3`.
- `language`: `fas`.
- `traineddata_file`: `fas.traineddata`.
- `traineddata_source`: `tesseract-ocr/tessdata_fast@87416418657359cb625c412a48b6e1d6d41c29bd`.
- `traineddata_sha256`: `db1c0a91208aff00d3cf1ed2c1d23f76419afd5f024688b4f71adc3f2ce4a505`.
- `page_segmentation_mode`: `SINGLE_LINE`.

### ParisaOCR

- `package_version`: `0.7.2`.
- `module_version`: `0.7.2`.
- `recognizer`: `Kraken 7.1.1 / parisaocr-fa-0.1`.
- `recognizer_sha256`: `cf41676c0cf590cd0a01ebb342faf1ce72c42e19a213984cbad6e5ddc91ae265`.
- `line_detector`: `PP-OCRv6 small via RapidOCR/ONNX Runtime`.
- `detector_sha256`: `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f`.
- `kraken_version`: `7.1.1`.
- `torch_version`: `2.14.0+cu130`.
- `device`: `CPU`.
- `cuda_available`: `False`.
- `network_downloads_during_inference`: `False`.

## Raw outputs

Every crop/engine/input result is listed below. `raw_text` is JSON-quoted so trailing newlines, tabs, and empty output remain visible. The original raw values and error strings are also preserved in the companion JSON file.

| Engine | Crop | Provisional reference | Input | Raw engine output | Confidence (diagnostic only) | Error |
|---|---|---|---|---|---:|---|
| Tesseract | 29_row0 | — (unscored) | unprocessed | "رسه تم\n" | 91.00 | — |
| Tesseract | 29_row0 | — (unscored) | otsu_binarized | "رسه تم\n" | 91.00 | — |
| Tesseract | 29_row1 | — (unscored) | unprocessed | "دود رنگی دستی\n" | 80.00 | — |
| Tesseract | 29_row1 | — (unscored) | otsu_binarized | "دود رنگی دستی\n" | 80.00 | — |
| Tesseract | 29_row2 | — (unscored) | unprocessed | "چنگال تم\n" | 75.00 | — |
| Tesseract | 29_row2 | — (unscored) | otsu_binarized | "چنگال تم\n" | 75.00 | — |
| Tesseract | 29_row3 | — (unscored) | unprocessed | "چاقوتم\n" | 84.00 | — |
| Tesseract | 29_row3 | — (unscored) | otsu_binarized | "چاقوتم\n" | 84.00 | — |
| Tesseract | 31_row0 | دستمال سفره تم | unprocessed | "دستمال سغره تم\n" | 84.00 | — |
| Tesseract | 31_row0 | دستمال سفره تم | otsu_binarized | "دستمال سغره تم\n" | 84.00 | — |
| Tesseract | 31_row1 | رد پا یا فلش تم | unprocessed | "ردپا با فلش قم\n" | 64.00 | — |
| Tesseract | 31_row1 | رد پا یا فلش تم | otsu_binarized | "ردپا با فلش قم\n" | 64.00 | — |
| Tesseract | 31_row2 | خلال کوچک | unprocessed | "خلال کوچک\n" | 88.00 | — |
| Tesseract | 31_row2 | خلال کوچک | otsu_binarized | "خلال کوچک\n" | 88.00 | — |
| Tesseract | 32_row0 | دستمال سفره تم | unprocessed | "دستمال سغره تم\n" | 84.00 | — |
| Tesseract | 32_row0 | دستمال سفره تم | otsu_binarized | "دستمال سغره تم\n" | 84.00 | — |
| Tesseract | 32_row1 | — (unscored) | unprocessed | "سطل شن بازی کوچک\n" | 89.00 | — |
| Tesseract | 32_row1 | — (unscored) | otsu_binarized | "سطل شن بازی کوچک\n" | 89.00 | — |
| Tesseract | 32_row2 | — (unscored) | unprocessed | "برف شادی\n" | 84.00 | — |
| Tesseract | 32_row2 | — (unscored) | otsu_binarized | "برف شادی\n" | 84.00 | — |
| Tesseract | 32_row3 | رد پا یا فلش تم | unprocessed | "ردپا با فلش قم\n" | 64.00 | — |
| Tesseract | 32_row3 | رد پا یا فلش تم | otsu_binarized | "ردپا با فلش قم\n" | 64.00 | — |
| Tesseract | 32_row4 | — (unscored) | unprocessed | "پاد‌کنک\n" | 54.00 | — |
| Tesseract | 32_row4 | — (unscored) | otsu_binarized | "پاد‌کنک\n" | 54.00 | — |
| Tesseract | 33_row0 | — (unscored) | unprocessed | "ساک کادو سایز بزرگ\n" | 76.00 | — |
| Tesseract | 33_row0 | — (unscored) | otsu_binarized | "ساک کادو سایز بزرگ\n" | 76.00 | — |
| Tesseract | 33_row1 | خلال کوچک | unprocessed | "خلال کوچک\n" | 88.00 | — |
| Tesseract | 33_row1 | خلال کوچک | otsu_binarized | "خلال کوچک\n" | 88.00 | — |
| Tesseract | 33_row2 | — (unscored) | unprocessed | "حباب ساز تفنگی\n" | 91.00 | — |
| Tesseract | 33_row2 | — (unscored) | otsu_binarized | "حباب ساز تفنگی\n" | 91.00 | — |
| Tesseract | 33_row3 | — (unscored) | unprocessed | "جعبه کادو قلب\n" | 87.00 | — |
| Tesseract | 33_row3 | — (unscored) | otsu_binarized | "جعبه کادو قلب\n" | 87.00 | — |
| Tesseract | 33_row4 | — (unscored) | unprocessed | "جنگال ۱۰۰ عددی\n" | 69.00 | — |
| Tesseract | 33_row4 | — (unscored) | otsu_binarized | "جنگال ۱۰۰ عددی\n" | 69.00 | — |
| Tesseract | 33_row5 | — (unscored) | unprocessed | "" | 0.00 | — |
| Tesseract | 33_row5 | — (unscored) | otsu_binarized | "" | 0.00 | — |
| Tesseract | 33_row6 | — (unscored) | unprocessed | "" | 0.00 | — |
| Tesseract | 33_row6 | — (unscored) | otsu_binarized | "" | 0.00 | — |
| Tesseract | 33_row7 | — (unscored) | unprocessed | "جعبه چرمی قفل دار\n" | 88.00 | — |
| Tesseract | 33_row7 | — (unscored) | otsu_binarized | "جعبه چرمی قفل دار\n" | 88.00 | — |
| Tesseract | 33_row8 | — (unscored) | unprocessed | "جعبه روسری\n" | 87.00 | — |
| Tesseract | 33_row8 | — (unscored) | otsu_binarized | "جعبه روسری\n" | 87.00 | — |
| Tesseract | 33_row9 | — (unscored) | unprocessed | "تویوپ بادی\n" | 86.00 | — |
| Tesseract | 33_row9 | — (unscored) | otsu_binarized | "تویوپ بادی\n" | 86.00 | — |
| Tesseract | 33_row10 | — (unscored) | unprocessed | "" | 0.00 | — |
| Tesseract | 33_row10 | — (unscored) | otsu_binarized | "" | 0.00 | — |
| Tesseract | 33_row11 | — (unscored) | unprocessed | "تاج بسته بندی قم\n" | 88.00 | — |
| Tesseract | 33_row11 | — (unscored) | otsu_binarized | "تاج بسته بندی قم\n" | 88.00 | — |
| Tesseract | 33_row12 | — (unscored) | unprocessed | "پیش دستی و لیوان تم\n" | 84.00 | — |
| Tesseract | 33_row12 | — (unscored) | otsu_binarized | "پیش دستی و لیوان تم\n" | 84.00 | — |
| ParisaOCR | 29_row0 | — (unscored) | unprocessed | "ریسه تم" | 99.80 | — |
| ParisaOCR | 29_row0 | — (unscored) | otsu_binarized | "ریسه تم" | 99.80 | — |
| ParisaOCR | 29_row1 | — (unscored) | unprocessed | "دود رنگی دستی" | 100.00 | — |
| ParisaOCR | 29_row1 | — (unscored) | otsu_binarized | "دود رنگی دستی" | 100.00 | — |
| ParisaOCR | 29_row2 | — (unscored) | unprocessed | "چنگال تم" | 99.80 | — |
| ParisaOCR | 29_row2 | — (unscored) | otsu_binarized | "چنگال تم" | 99.80 | — |
| ParisaOCR | 29_row3 | — (unscored) | unprocessed | "چاقوتم" | 99.80 | — |
| ParisaOCR | 29_row3 | — (unscored) | otsu_binarized | "چاقوتم" | 99.80 | — |
| ParisaOCR | 31_row0 | دستمال سفره تم | unprocessed | "دستمال سفره تم" | 100.00 | — |
| ParisaOCR | 31_row0 | دستمال سفره تم | otsu_binarized | "دستمال سفره تم" | 100.00 | — |
| ParisaOCR | 31_row1 | رد پا یا فلش تم | unprocessed | "ردپا یا فلش تم" | 99.90 | — |
| ParisaOCR | 31_row1 | رد پا یا فلش تم | otsu_binarized | "ردپا یا فلش تم" | 99.90 | — |
| ParisaOCR | 31_row2 | خلال کوچک | unprocessed | "خلال کوچک" | 99.80 | — |
| ParisaOCR | 31_row2 | خلال کوچک | otsu_binarized | "خلال کوچک" | 99.80 | — |
| ParisaOCR | 32_row0 | دستمال سفره تم | unprocessed | "دستمال سفره تم" | 100.00 | — |
| ParisaOCR | 32_row0 | دستمال سفره تم | otsu_binarized | "دستمال سفره تم" | 100.00 | — |
| ParisaOCR | 32_row1 | — (unscored) | unprocessed | "سطل شن بازی کوچک" | 100.00 | — |
| ParisaOCR | 32_row1 | — (unscored) | otsu_binarized | "سطل شن بازی کوچک" | 100.00 | — |
| ParisaOCR | 32_row2 | — (unscored) | unprocessed | "برف شادی" | 100.00 | — |
| ParisaOCR | 32_row2 | — (unscored) | otsu_binarized | "برف شادی" | 100.00 | — |
| ParisaOCR | 32_row3 | رد پا یا فلش تم | unprocessed | "ردپا یا فلش تم" | 99.90 | — |
| ParisaOCR | 32_row3 | رد پا یا فلش تم | otsu_binarized | "ردپا یا فلش تم" | 99.90 | — |
| ParisaOCR | 32_row4 | — (unscored) | unprocessed | "بادکنک" | 100.00 | — |
| ParisaOCR | 32_row4 | — (unscored) | otsu_binarized | "بادکنک" | 100.00 | — |
| ParisaOCR | 33_row0 | — (unscored) | unprocessed | "ساک کادو سایز بزرگ" | 99.70 | — |
| ParisaOCR | 33_row0 | — (unscored) | otsu_binarized | "ساک کادو سایز بزرگ" | 99.70 | — |
| ParisaOCR | 33_row1 | خلال کوچک | unprocessed | "خلال کوچک" | 100.00 | — |
| ParisaOCR | 33_row1 | خلال کوچک | otsu_binarized | "خلال کوچک" | 100.00 | — |
| ParisaOCR | 33_row2 | — (unscored) | unprocessed | "حباب ساز تفنگی" | 99.60 | — |
| ParisaOCR | 33_row2 | — (unscored) | otsu_binarized | "حباب ساز تفنگی" | 99.60 | — |
| ParisaOCR | 33_row3 | — (unscored) | unprocessed | "جعبه کادو قلب" | 99.80 | — |
| ParisaOCR | 33_row3 | — (unscored) | otsu_binarized | "جعبه کادو قلب" | 99.80 | — |
| ParisaOCR | 33_row4 | — (unscored) | unprocessed | "چنگال ۱۰۰ عددی" | 99.90 | — |
| ParisaOCR | 33_row4 | — (unscored) | otsu_binarized | "چنگال ۱۰۰ عددی" | 99.90 | — |
| ParisaOCR | 33_row5 | — (unscored) | unprocessed | "چسبونک" | 98.40 | — |
| ParisaOCR | 33_row5 | — (unscored) | otsu_binarized | "چسبونک" | 98.40 | — |
| ParisaOCR | 33_row6 | — (unscored) | unprocessed | "چاقو کیک‌تم وپاپیون\nدار و متالایزی" | 99.25 | — |
| ParisaOCR | 33_row6 | — (unscored) | otsu_binarized | "چاقو کیک‌تم وپاپیون\nدار و متالایزی" | 99.25 | — |
| ParisaOCR | 33_row7 | — (unscored) | unprocessed | "جعبه چرمی قفل دار" | 99.00 | — |
| ParisaOCR | 33_row7 | — (unscored) | otsu_binarized | "جعبه چرمی قفل دار" | 99.00 | — |
| ParisaOCR | 33_row8 | — (unscored) | unprocessed | "جعبه روسری" | 99.90 | — |
| ParisaOCR | 33_row8 | — (unscored) | otsu_binarized | "جعبه روسری" | 99.90 | — |
| ParisaOCR | 33_row9 | — (unscored) | unprocessed | "تویوپ بادی" | 100.00 | — |
| ParisaOCR | 33_row9 | — (unscored) | otsu_binarized | "تویوپ بادی" | 100.00 | — |
| ParisaOCR | 33_row10 | — (unscored) | unprocessed | "پیش دستی کاغذی\nماتایی تم" | 98.65 | — |
| ParisaOCR | 33_row10 | — (unscored) | otsu_binarized | "پیش دستی کاغذی\nماتایی تم" | 98.65 | — |
| ParisaOCR | 33_row11 | — (unscored) | unprocessed | "تاج بسته بندی تم" | 99.80 | — |
| ParisaOCR | 33_row11 | — (unscored) | otsu_binarized | "تاج بسته بندی تم" | 99.80 | — |
| ParisaOCR | 33_row12 | — (unscored) | unprocessed | "پیش دستی و لیوان‌تم" | 100.00 | — |
| ParisaOCR | 33_row12 | — (unscored) | otsu_binarized | "پیش دستی و لیوان‌تم" | 100.00 | — |
