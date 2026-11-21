# User-supplied Holoo image — spatial OCR evidence

**Evidence class: user-supplied, cleaned invoice image; one-image exploratory validation.**
This report records what the adapter recognized and deliberately leaves uncertain
values in `REVIEW`. It does not establish general Holoo OCR accuracy or production
readiness. Frozen contracts D-01–D-09 were not changed.

## Input and OCR runtime

- Image: `holo_row_detection.png`
- Repository path: `deliveries/image-extraction-ocr/holo_row_detection.png`
- Image SHA-256: `61d6d16594ca35d622099ad5c453292d0279127ee65744ce784952b3a781586a`
- OCR engine: Tesseract 5.5.1, language `fas+eng`
- TSV word records: 85; mean confidence: `71.06630628235297`; minimum: `0.0`
- Field confidence threshold: `60.0` (test setting, not a production recommendation)
- Spatial input: Tesseract level-5 TSV text/confidence/left/top/width/height boxes.
  `pytesseract` and the Tesseract CLI were unavailable in this runtime, so the
  adapter uses `tesserocr.GetTSVText(0)`, which returns the equivalent TSV box
  fields. No `pytesseract.image_to_data` call is claimed.

The flat-text parser stopped at the unlabeled date (`expected exactly one invoice
date, OCR yielded 0`). The adapter then ran the spatial fallback. Detected table
column boundaries (x pixels) were `113.5, 241.5, 290.5, 484.5, 524.5`, corresponding
right-to-left to amount, quantity, item name, and row number. Four row bands were
identified in ascending order (y pixels): `520.75–588.25`, `588.25–656.0`,
`656.0–724.0`, and `724.0–792.0`.

**Layout result:** Four numbered rows (۱–۴) were assigned to the expected
right-to-left columns; there is no observed row/column transposition in this
parse. The amount *column positions* were recovered, but the amount OCR strings
are not trustworthy numeric values. No amount has been repaired or inferred.

## Extracted adapter fields

Raw strings below are preserved from OCR. `EXTRACTED` means only that the field
passed this adapter's confidence/format checks; it is not independent ground
truth. `REVIEW` values must not be issued as invoice values.

```text
invoice.number=۷۹ [EXTRACTED; confidence 86.90]
invoice.date=1405.06.18 [REVIEW; confidence 95.19; unlabeled dot date, calendar conversion undeclared]
invoice.payable=۰۰۰و ۷,۴۶۰‏ [REVIEW; confidence 0.00; raw value fails numeric format]
tax.amount=۰ [EXTRACTED; confidence 88.23]
total.net= [REVIEW; missing]
charges.amount=۰ [EXTRACTED; confidence 89.17; adapter-local supplementary field]

line.0.sequence=۱ [EXTRACTED]
line.0.description=ریسه تم [REVIEW; confidence 52.35]
line.0.quantity=| [REVIEW; confidence 13.25; raw value fails numeric format]
line.0.total=۴۵۰و [REVIEW; confidence 0.00; raw value fails numeric format]
line.0.unit_price= [REVIEW; no unit-price column recognized]

line.1.sequence=۲ [EXTRACTED]
line.1.description=دوهرنگی دستی [REVIEW; confidence 46.01]
line.1.quantity=٩‏ [REVIEW; confidence 57.04]
line.1.total=دره۴,۸۷ [REVIEW; confidence 0.00; raw value fails numeric format]
line.1.unit_price= [REVIEW; no unit-price column recognized]

line.2.sequence=۳ [EXTRACTED]
line.2.description=چنگال تم [EXTRACTED; confidence 91.12]
line.2.quantity=!| [REVIEW; confidence 43.68; raw value fails numeric format]
line.2.total=۵۷۰,۰۰ [REVIEW; confidence 78.56; raw value fails numeric format]
line.2.unit_price= [REVIEW; no unit-price column recognized]

line.3.sequence=۴ [EXTRACTED]
line.3.description=چاقو نم [REVIEW; confidence 37.93]
line.3.quantity=!| [REVIEW; confidence 43.68; raw value fails numeric format]
line.3.total=۵۷۰,۰۰ [REVIEW; confidence 78.56; raw value fails numeric format]
line.3.unit_price= [REVIEW; no unit-price column recognized]
```

All review fields: `invoice.date`, `invoice.payable`, `total.net`,
`line.0.description`, `line.0.quantity`, `line.0.total`, `line.0.unit_price`,
`line.1.description`, `line.1.quantity`, `line.1.total`, `line.1.unit_price`,
`line.2.quantity`, `line.2.total`, `line.2.unit_price`, `line.3.description`,
`line.3.quantity`, `line.3.total`, and `line.3.unit_price`.

In particular, raw OCR strings such as `۴۵۰و`, `دره۴,۸۷`, `۵۷۰,۰۰`, `|`, and `!|`
remain unchanged. The adapter does **not** reinterpret them as numeric values.

## Issuance boundary

- Adapter result: `ImageExtractionReviewRequired`
- `IssuanceService.submit` calls: **0**
- Digital Invoice issued: **No** (`NONE`)
- Invoice lifecycle started: **No**
- Review mechanism: adapter-local hold only; this is not a persisted Frozen P5.2
  review record or a new Digital Invoice `REVIEW` lifecycle state.

The report supports a narrow conclusion: the geometry parser found and aligned
four rows and captured raw values in their spatial columns, but critical date,
payable, net-total, line quantity/amount, and unit-price fields remain under
review. The sample therefore correctly failed closed before issuance.

## Verification

- Focused image adapter tests: 12 passed.
- Full repository test suite: 1,706 passed.
- Synthetic English and Persian OCR smoke regressions passed separately. They
  remain **Synthetic** evidence and do not validate this Holoo image.
- `git diff --check`: passed.
