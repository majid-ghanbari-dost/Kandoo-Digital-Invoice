# Experimental image-to-invoice extraction adapter

`ImageExtractionAdapter` accepts a raster image, calls a real OCR backend, parses
recognized labels/table text (not image coordinates), and sends the resulting
UTF-8 `key=value` page to the existing `IssuanceService.submit`. No core service,
SQLite schema, or Frozen contract is modified.

## OCR backend

`TesseractOCR` uses the optional `tesserocr` binding to Tesseract and Pillow for
raster loading. The core application remains stdlib-only; install the OCR
runtime separately and provide a traineddata directory and language explicitly.
The repository does not vendor Tesseract binaries or traineddata.

The included parser is deliberately limited to the labelled, pipe-delimited
English example used by the synthetic fixture. It maps invoice number/date,
net/tax/payable totals, and item/quantity/unit-price/line-total fields. It uses
OCR text labels and row delimiters; it does not use fixed pixel coordinates,
infer missing values, calculate taxes, or claim to parse Holoo layouts. A real
Holoo image requires a sanitized real fixture and a validated layout/language
mapping before this parser can be considered suitable.

## Confidence and review behavior

`minimum_word_confidence` is a required caller declaration (0–100). The adapter
uses the minimum Tesseract word confidence, not just an average. Missing scores,
low confidence, or incomplete/ambiguous parsing returns
`ImageExtractionReviewRequired`; `submit_image` then does not call Capture and
cannot create a Digital Invoice. This is a fail-closed adapter-local review hold,
**not** a new frozen state and **not** a persisted WP-5.2 ReviewQueue item: the
current Frozen contracts do not carry OCR confidence. A PipelineStopped/REVIEW
result from `IssuanceService.submit` is returned unchanged. Issuance remains an
explicit caller action.

Capture stores the OCR-generated key/value page, not the source image. The
adapter returns the image SHA-256 for external correlation, but no source-image
pointer is added to frozen Capture records.

## Synthetic fixture and tests

`tests/fixtures/synthetic_invoice.png` and `.svg` are explicitly synthetic. They
are not a Holoo sample and are not evidence of Holoo OCR accuracy. The unit
tests use small fake OCR results only to test the confidence gate/parser; the
smoke runner exercises real Tesseract plus the actual issuance services.

Example local commands (supply the appropriate optional packages/model):

```bash
PYTHONPATH=src python3 -m unittest discover -s src/image_extraction_adapter/tests -v
PYTHONPATH=/path/to/ocr/site-packages:src python3 src/run_smoke_image_extraction.py \
  --tessdata-dir /path/to/tessdata --language eng --minimum-confidence 80
```

For a Persian Holoo image, both a Persian OCR model and a Persian-specific text
parser/decimal convention are needed; the included English fixture does not
verify that path.
