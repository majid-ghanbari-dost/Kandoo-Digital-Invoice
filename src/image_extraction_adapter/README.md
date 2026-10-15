# Experimental image-to-invoice extraction adapter

`ImageExtractionAdapter` accepts a raster image, calls a real OCR backend, and
uses the existing `IssuanceService.submit` only for a high-confidence,
contract-shaped text parse. If that parse is incomplete, the adapter can use
word-level geometry for a right-to-left spatial table fallback. The core
service, SQLite schema, and Frozen contracts are unchanged.

## OCR backend and cell extraction

`TesseractOCR` uses optional `tesserocr` and Pillow dependencies. The core
application remains stdlib-only; provide the traineddata directory and language
explicitly. The repository does not vendor Tesseract binaries or traineddata.
The full-page OCR retains Tesseract TSV text/confidence/left/top/width/height
boxes. When spatial table geometry is detected, the adapter crops amount,
quantity, and description cells from each row and also crops the labeled payable
value when a box is available. The source invoice image is never modified.

Cell OCR uses Tesseract PSM 7 (`SINGLE_LINE`). Numeric cells use
`NUMERIC_TESSERACT_WHITELIST` (`0123456789۰۱۲۳۴۵۶۷۸۹.,`); description cells do
not get that whitelist. Numeric cells are tested in three modes:

- `none`: unthresholded cell-crop control;
- `otsu`: global Otsu threshold followed by directional morphological removal
  of long horizontal/vertical table rules;
- `adaptive`: local-mean threshold followed by the same rule removal.

The preprocessing helpers use Pillow morphology and thresholding; no OpenCV
runtime is required. Processed crops are copies. Each variant is returned as
`CellOCRVariantResult` with its raw OCR string, confidence, crop box, PSM,
whitelist and review reason. Variant text never silently replaces the original
spatial parse. Whitelisted output is also compared with an unrestricted crop
read; disagreement, low confidence, invalid numeric format, or `|` / `!` keeps
the result in `REVIEW`. No digit substitution or amount repair is performed.

## Confidence and review behavior

`minimum_word_confidence` is a required caller declaration (0–100). Missing
scores, low confidence, invalid values, or incomplete/ambiguous parsing returns
`ImageExtractionReviewRequired`; `submit_image` then does not call Capture and
cannot create a Digital Invoice. Cell variants are supplementary evidence and
do not turn that review result into a ready invoice. This is a fail-closed
adapter-local hold, **not** a new frozen state and **not** a persisted WP-5.2
ReviewQueue item: current Frozen contracts do not carry OCR confidence. A
`PipelineStopped`/REVIEW result from `IssuanceService.submit` is returned
unchanged.

The current spatial rule parser targets numbered rows and vertical-rule columns
in the supplied receipt layout; it is not a general Holoo layout model. A unit
price column is not inferred when the image contains no detected unit-price
column. Jalali calendar conversion is not implemented.

## Preprocessing benchmark

Run the three numeric-cell variants against the user-supplied image without
calling issuance:

```bash
PYTHONPATH=/path/to/ocr/site-packages:src python3 \
  src/run_image_preprocessing_benchmark.py \
  --tessdata-dir /path/to/tessdata --language fas+eng \
  --minimum-confidence 60
```

The script uses an explicitly documented manual visual transcription for
scoring only. It reports exact digit-cell error rate and digit-only character
error rate after mapping digit scripts for comparison. That scoring
normalization is not applied to OCR output or adapter field values.

## Synthetic fixture and tests

`tests/fixtures/synthetic_invoice.png`, `.svg`, and
`tests/fixtures/synthetic_invoice_fa.png` are explicitly synthetic. They are not
Holoo samples and are not evidence of Holoo OCR accuracy. Unit tests cover the
parser, confidence/review gate, TSV boxes, spatial cropping, thresholding,
morphological line removal, and invalid numeric glyph handling. The separate
smoke runner exercises real Tesseract plus issuance services only on synthetic
fixtures.
