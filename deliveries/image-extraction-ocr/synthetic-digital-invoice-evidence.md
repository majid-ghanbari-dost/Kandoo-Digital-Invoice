# Synthetic image OCR → Digital Invoice evidence

**Evidence class: Synthetic test only.** No Holoo invoice or Spooler print was
available or used. This does not establish accuracy on Holoo/Persian invoices.

## Raster OCR and extracted values

- Fixture: `src/image_extraction_adapter/tests/fixtures/synthetic_invoice.png`
- Source image SHA-256: `c06075646afe254528925093d0b8877be1dd7ea0ff382865aa74aef7bead65cd`
- OCR: Tesseract 5.5.1, language `eng`, 47 word scores
- Minimum / mean word confidence: 87.00 / 95.21
- Confidence threshold for this successful run: 80
- All nine parsed values matched the explicit synthetic expectations in the
  saved log: `synthetic-ocr-success.log`.

The OCR text includes invoice `SYNTH-IMG-001`, date `2026-10-14`, one
`Synthetic Widget` line (quantity 2, unit price 500.00, line total 1000.00),
net total 1000.00, tax 80.00, and amount due 1080.00. Values are synthetic and
no currency is inferred.

## Existing pipeline and final Digital Invoice

The adapter submitted the OCR-generated UTF-8 key/value page through the
existing `IssuanceService.submit`; the pipeline completed without changes to
Frozen contracts. The smoke used the reference validation rules and reported
four validation results `VALID`, domain `VALID/CLEAR`, and canonicalization
`ACCEPTED`.

- Canonical invoice ID: `25b63f98ca4a42b6afcda693b3f6a799`
- Canonical line count: 1; canonical field count: 10
- Derived `total.gross`: 1080
- Digital Invoice ID: `27bd8bd5a9834e78aca9a8600e9401a4`
- Explicit lifecycle: `DRAFT → EXTRACTED → VALIDATED → ISSUED`
- Final state: `ISSUED`; verified: `true`
- Trace result: `DigitalInvoiceTraceSuccess`, 24 links

The full actual OCR text, field-by-field expected/actual comparison, pipeline
stages, validation results, canonical fields, lifecycle, and final trace summary
are in `synthetic-ocr-success.log`. The smoke workspace itself was temporary;
the log is the retained evidence artifact.

## Fail-closed confidence probe

A second actual Tesseract run used the same image with a declared threshold of
90. The measured minimum remained 87, so the adapter returned
`REVIEW_REQUIRED`; `IssuanceService.submit` was **not called**, and there was no
Digital Invoice. See `synthetic-confidence-review.log`.

This is an adapter-local review hold, not a persisted Frozen P5.2 ReviewQueue
record or a Digital Invoice state named `REVIEW`: current Frozen contracts do
not carry OCR confidence, and they were intentionally left unchanged. The
caller must present this hold to an operator; if persisted P5.2 routing is
required, it needs an approved contract-level path.

## Scope limitations

- The parser recognizes the labeled, pipe-delimited **English synthetic**
  format only; it does not use image coordinates. It is not a Holoo layout
  parser.
- `eng` was tested. Persian-trained OCR data, Persian labels/RTL handling, and
  the applicable numeric conventions have not been tested or implemented.
- Tesseract confidence is a review heuristic, not a calibrated probability.
- The existing reference validators confirmed their four configured rules;
  they did not directly assert that the extracted `invoice.payable` equals the
  derived `total.gross`. Both are 1080 for this fixture, but production policy
  for that relationship should be explicitly approved.
- Capture stores the OCR transcript page. The source raster's hash is reported
  by this adapter but is not persisted in the Frozen Capture contract.
