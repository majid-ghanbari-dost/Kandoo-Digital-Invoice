# Synthetic image OCR → Digital Invoice evidence

**Evidence class: Synthetic test only.** These fixtures and pipeline records are
not Holoo invoices or Spooler captures. No authorized genuine Holoo raster was
available or used, so these tests do not establish Holoo accuracy or production
readiness. Frozen contracts D-01–D-09 were not changed.

## English baseline

- Fixture: `src/image_extraction_adapter/tests/fixtures/synthetic_invoice.png`
- Source image SHA-256: `c06075646afe254528925093d0b8877be1dd7ea0ff382865aa74aef7bead65cd`
- OCR: Tesseract 5.5.1, language `eng`, 47 word scores
- Minimum / mean word confidence: 87.00 / 95.21
- Confidence threshold for the successful run: 80
- All nine explicitly synthetic values matched; the raw OCR and complete
  pipeline output are retained in `synthetic-ocr-success.log`.

The recognized values were invoice `SYNTH-IMG-001`, date `2026-10-14`, one
`Synthetic Widget` line (quantity 2, unit price 500.00, line total 1000.00),
net total 1000.00, tax 80.00, and amount due 1080.00. No currency is inferred.
The separate threshold-90 run is retained in `synthetic-confidence-review.log`.

## Persian OCR support — synthetic fixture

- Fixture: `src/image_extraction_adapter/tests/fixtures/synthetic_invoice_fa.png`
- Fixture SHA-256: `df0e79c5acef87a6f2bcd3c9d36c6afadfb612a7210afadc0ea717c08856d782`
- The PNG visibly declares `SYNTHETIC TEST ONLY` and includes the requested
  Persian item descriptions, quantities, amounts, and payable label.
- OCR: Tesseract 5.5.1 with `fas+eng`; 47 word scores, mean confidence
  91.04255319148936, minimum confidence 65.0.
- The exact raw OCR, full expected/actual comparison, and resulting pipeline
  record are in `synthetic-persian-ocr-e2e.log`.

Successful run command (the optional runtime and traineddata were installed
outside the repository):

```sh
PYTHONPATH=/tmp/kandoo-ocr-runtime:src PYTHONDONTWRITEBYTECODE=1 \
  python3 src/run_smoke_image_extraction.py --profile fa \
  --tessdata-dir /tmp/kandoo-ocr-runtime/share/tessdata \
  --language fas+eng --minimum-confidence 60 \
  --image src/image_extraction_adapter/tests/fixtures/synthetic_invoice_fa.png
```

- All 13 declared fields matched exactly, including `ساندویچ کالباس`,
  `دستمال سفره تم`, both item quantities/prices/totals, net total 1300.00,
  tax 104.00, and payable 1404.00. Persian quantity digit `۲` was normalized
  to numeric value `2`; Persian text was preserved as UTF-8. No Unicode
  encoding failure was observed.

The actual OCR-generated UTF-8 `key=value` page was preflighted against the
synthetic expectations and submitted once through the existing
`IssuanceService`. The pipeline completed; all four configured validation
rules were `VALID`, the validation domain was `VALID/CLEAR`, and
canonicalization was `ACCEPTED`.

- Canonical invoice ID: `8cab57b0e0684f5889d3f5dd379c9030`
- Canonical line count: 2; canonical field count: 14
- Derived `total.gross`: 1404
- Digital Invoice ID: `19b527b2432542d5b1dc7c62354bf8ea`
- Explicit lifecycle: `DRAFT → EXTRACTED → VALIDATED → ISSUED`
- Final state: `ISSUED`; verified: `true`
- Trace result: `DigitalInvoiceTraceSuccess`, 24 links

The smoke's isolated workspace was temporary; the complete OCR and pipeline
output is preserved in `synthetic-persian-ocr-e2e.log`.

### Confidence fail-closed probe

The same Persian fixture was run with a declared minimum confidence of 70.0.
Its measured minimum remained 65.0, so the adapter returned
`REVIEW_REQUIRED`; `IssuanceService.submit` was **not called** and no Digital
Invoice was created. Raw OCR text and the exact reason are retained in
`synthetic-persian-confidence-review.log`.

This is an adapter-local hold, not a persisted Frozen P5.2 ReviewQueue record
or a Digital Invoice `REVIEW` state. Frozen contracts do not carry OCR
confidence; the hold must be presented to an operator by a caller.

### Persian model and parser details

`PERSIAN_TESSERACT_LANGUAGE` is exported as `fas+eng`. Both `fas.traineddata`
and `eng.traineddata` were downloaded and successfully exercised from the
pinned `tesseract-ocr/tessdata_fast` snapshot
`87416418657359cb625c412a48b6e1d6d41c29bd`:

- `fas.traineddata` SHA-256:
  `db1c0a91208aff00d3cf1ed2c1d23f76419afd5f024688b4f71adc3f2ce4a505`
- `eng.traineddata` SHA-256:
  `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`
- Source archive:
  `https://codeload.github.com/tesseract-ocr/tessdata_fast/zip/87416418657359cb625c412a48b6e1d6d41c29bd`

For this run, optional runtime packages and traineddata were installed under
`/tmp/kandoo-ocr-runtime`, outside the repository. Neither model binary nor
those optional packages are committed. The parser normalizes Persian and
Arabic-Indic digits, Persian decimal/group separators, Arabic/Persian letter
variants, and bidirectional controls; its UTF-8 `key=value` output is covered
by unit tests. Invoice dates are interpreted as Gregorian dates; Jalali
calendar conversion is not implemented. The fixture deliberately uses a
Gregorian ISO date.

## Verification performed

- Focused adapter unit tests: 9 passed, including Persian UTF-8, localized
  digit/separator, and low-confidence resubmission guard cases.
- Full repository suite: 1,703 passed using pytest 9.1.1, installed only in
  `/tmp/kandoo-ocr-runtime` for verification.
- Synthetic Persian issuance smoke at threshold 60: passed as recorded above.
- Synthetic Persian confidence probe at threshold 70: review hold, no submit.
- English synthetic smoke regression: completed and reached `ISSUED`; full run
  retained in `synthetic-english-regression.log`.
- `git diff --check`: passed.

## Scope limits

- English and Persian text-label parsing is coordinate-free; it is not a
  Holoo layout model. Unknown, incomplete, or ambiguous fields fail closed for
  review.
- No real Holoo invoice was supplied. A genuine sanitized/authorized sample
  remains required before validating Holoo-specific recognition or claiming
  accuracy on Holoo output.
- Tesseract confidence is a review heuristic, not a calibrated probability;
  the successful synthetic threshold does not establish a production threshold.
- The reference validators confirmed the four configured rules. They did not
  add a new contract-level assertion connecting extracted `invoice.payable` to
  derived `total.gross`; both happen to be 1404 for this synthetic fixture.
- Capture stores the OCR transcript page. The source raster hash is reported
  by the adapter but is not persisted in the Frozen Capture contract.
