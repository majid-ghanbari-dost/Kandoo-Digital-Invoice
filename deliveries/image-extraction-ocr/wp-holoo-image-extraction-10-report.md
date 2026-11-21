# WP-HOLOO-IMAGE-EXTRACTION-10 — Glyph Integration & Guarded E2E

## Outcome

**PASS — the target page was held for review and no submit attempt or Digital Invoice issuance occurred.** This is a fail-closed behavior result, not an OCR-accuracy or ground-truth validation claim.

- `ImageExtractionAdapter` now accepts an explicit spatial numeric OCR backend; the smoke run injected `GlyphClassifierOCR` using `src/templates.json`. Tesseract remained the full-page text/layout backend.
- The run used `deliveries/image-extraction-ocr/13.png` and dynamically returned all **13 rows**, with **27 numeric cells** (13 quantities, 13 line totals, payable).
- Glyph result: **12 EXTRACTED, 15 REVIEW**. All 13 totals and payable were held by the arithmetic gate; one quantity was also REVIEW.
- **Arithmetic gate: FAIL.** `line.9.total` was read as `??۹,۶۰۰,۰۰۰`, which is malformed; payable was also malformed as `????۷,????۰,۰۰۰`. The gate could not safely reconcile line sum and payable.
- Adapter outcome: `ImageExtractionReviewRequired`. The adapter’s submit hook was instrumented with a `NonIssuingSubmitProbe`; it observed **0 calls**. The real issuance service was not attached to this guarded image path, so no Digital Invoice could be created. **No `ISSUED` state was reached and no critical issuance bug was observed.**

## Implementation and safety behavior

- Configured `numeric_ocr_backend` is primary for numeric cells. Any non-`EXTRACTED` numeric result, missing coverage, or disagreement with the parsed numeric transcript holds the entire page. OCR/backend exceptions also fail closed.
- The full-page parse failure path invokes the configured Glyph backend and returns its raw cell results/reasons with the page-level review hold.
- When Glyph evidence passes, the accepted cell variants are carried in `ImageExtractionReady`; `submit_extraction` rechecks them when a numeric backend is configured, so a ready object without valid numeric evidence cannot bypass the gate.
- The smoke runner no longer labels `--image` overrides Synthetic. Real-image mode requires Glyph templates and uses a non-delegating probe rather than the actual issuance service.
- The adapter-local hold is **not** a persisted Frozen P5.2 review record. Frozen contracts D-01–D-09 were not changed. No change to issuance eligibility or automatic repair was made.

## Evidence limits

- The included image is non-synthetic, but visual labels/references are provisional and **not invoice-owner-confirmed ground truth**.
- WP-09’s “0 False Positive” means only that zero cells marked EXTRACTED disagreed with provisional visual labels in that limited evaluation. It is not owner-confirmed or general accuracy evidence.
- The prior 13-row train/evaluation split is by rows from the same invoice, not independent-invoice validation. This E2E run is a control-flow check, not a new labeled accuracy evaluation.

## Reproduction and runtime

Command used:

```sh
PYTHONPATH=/tmp/kandoo-glyph-runtime:src python src/run_smoke_image_extraction.py \
  --profile fa \
  --tessdata-dir /tmp/kandoo-glyph-runtime/share/tessdata \
  --language fas+eng \
  --minimum-confidence 60 \
  --image deliveries/image-extraction-ocr/13.png \
  --glyph-templates src/templates.json \
  --expected-rows 13
```

Runtime: Tesseract 5.5.1; tesserocr 2.11.0; Pillow 11.3.0. The `fas`/`eng` traineddata and Python runtimes were kept under `/tmp/kandoo-glyph-runtime` and not added to the repository.

| Asset | SHA-256 |
|---|---|
| `deliveries/image-extraction-ocr/13.png` | `2ffe4a33b54a513dc8df9a0eac22ac514f9ebf7aae89958ee11d0fa00cc67e80` |
| `src/templates.json` | `c55857af5c83708d780cec94c5f0fbbbb5dba58de1576232ce55d3d8090a1b45` |
| `fas.traineddata` | `db1c0a91208aff00d3cf1ed2c1d23f76419afd5f024688b4f71adc3f2ce4a505` |
| `eng.traineddata` | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` |

Validation:

- Focused image-adapter suite: **25 passed**.
- Full repository suite: **1,719 passed, 6 subtests passed**.
- `git diff --check`: passed.
- Smoke result: **PASS** — 13-row geometry observed, arithmetic gate failed closed, submit calls zero.

## Complete E2E log

The verbatim log is also saved separately at `deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-e2e.log`.

```text
evidence.class=Non-synthetic image; provisional visual references are not owner-confirmed ground truth
image.path=deliveries/image-extraction-ocr/13.png
image.expected_rows=13
ocr.minimum_word_confidence_threshold=60.0
numeric_ocr.engine=GlyphClassifierOCR
numeric_ocr.templates=src/templates.json
issuance.submit_target=NonIssuingSubmitProbe (real service not attached)
ocr.status=REVIEW_REQUIRED
source_image.sha256=2ffe4a33b54a513dc8df9a0eac22ac514f9ebf7aae89958ee11d0fa00cc67e80
ocr.engine=tesseract 5.5.1
ocr.language=fas+eng
ocr.word_count=167
ocr.mean_confidence=71.17123005988024
ocr.minimum_confidence=0.0
ocr.raw_text.begin
13:45 1405.07.04

شماره فاکتور : ۳۳

نام مشتری: _ مفتری

‎os‏ کاربر:

‏3 نام ‎YW‏ 3 جع کل

‏| |ساک کادو سایز بزرک | ۴ | رد۷۸۸

‎۴۸۵۰ | ۰ |  کچوک‌لالخ‎ ۲

‏۳ | حباب‌سازتتنگی | ۵ | ۸,۷۵۰,۳۰۰

‏۴ جعبه کادو قلب ۴۲ | ‎F Fores‏

‎FA Foo eee ۲.۰ ‏عددی‎ ۰۰ Jo ۵

‎۱۵۷۰۰ ۱ ‏چسونی‎ |g

‏۷ | جاقو کیک تم وپاپیون | ۵ | ««حرهءگر۶
دار و متالایزی

‏۸ | جعبه چرمی قفل دار | ۱ | ۶,۸۷۰,۰۰۰

‎Foose | ۲ ‏جعبه روسری‎ ٩

‏>‘ تویوپ‌بادی ‎A‏ ۲۲۹,۶۰
۱ بیش دستی کافذی | ‎11D‏ ۱۹,۰۵۰,۰۰۰
+ اقایی تم
۴ تاج بسته بندی تم ۱ ‎A FAs joes‏

‏۴۳| پیش دستی و لیوان‌تم | ۱ | ۱,۵۷۰,۰۰۰

‏مبلغ قابل پرداخت: ۳۴۷,۹۲۰,۰۰۰ ربال

‏مالیات بر ارزش افزوده : ۰

‏عوارض: ۰
آدرس:تیلان ‎Glee‏ -بلوارآمام رضا
مابین کلستان ۲۰ ۲۲

‎fq)  Jashn_sun
ocr.raw_text.end
review.reason=flat-text parser blocked: expected exactly one invoice date, OCR yielded 0; spatial parser: row sequence 2 is missing before 4; only one increasing row-number anchor was recognized; fields require review: invoice.date, total.net; numeric OCR REVIEW cell(s): line.0.total, line.0.quantity, line.1.total, line.2.total, line.3.total, line.4.total, line.5.total, line.6.total, line.7.total, line.8.total, line.9.total, line.10.total, line.11.total, line.12.total, invoice.payable
spatial.column_boundary_count=5
spatial.row_band_count=0
spatial.field_assessment_count=6
spatial.field=invoice.number status=EXTRACTED raw='۳۳' reason=None
spatial.field=invoice.date status=REVIEW raw='1405.07.04' reason='unlabeled dot-separated date; calendar conversion is not declared'
spatial.field=invoice.payable status=EXTRACTED raw='۳۴۷,۹۲۰,۰۰۰' reason=None
spatial.field=tax.amount status=EXTRACTED raw='۰' reason=None
spatial.field=total.net status=REVIEW raw='' reason='no overall net amount was recognized beside a net-total label; no OCR word recognized in the field region; field has no word confidence score'
spatial.field=charges.amount status=EXTRACTED raw='۰' reason=None
glyph.cells.total=27
glyph.cells.EXTRACTED=12
glyph.cells.REVIEW=15
glyph.arithmetic_gate=FAIL
glyph.cell=line.0.total status=REVIEW raw='۷,۸۸۰,۰۰۰' confidence=99.9847619047619 bbox=(120, 533, 240, 593) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.0.quantity status=REVIEW raw='?' confidence=0.0 bbox=(248, 533, 289, 593) reason='glyph 1 not accepted: ambiguous: margin 0.146 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format'
glyph.cell=line.1.total status=REVIEW raw='۴,۸۵۰,۰۰۰' confidence=99.98761904761905 bbox=(120, 604, 240, 661) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.1.quantity status=EXTRACTED raw='۱۰' confidence=99.97047619047619 bbox=(248, 604, 289, 661) reason=None
glyph.cell=line.2.total status=REVIEW raw='۸,۷۵۰,۰۰۰' confidence=99.9847619047619 bbox=(120, 672, 240, 729) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.2.quantity status=EXTRACTED raw='۵' confidence=99.97809523809524 bbox=(248, 672, 289, 729) reason=None
glyph.cell=line.3.total status=REVIEW raw='۶,۴۰۰,۰۰۰' confidence=99.98190476190476 bbox=(120, 740, 240, 797) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.3.quantity status=EXTRACTED raw='۲' confidence=99.99809523809525 bbox=(248, 740, 289, 797) reason=None
glyph.cell=line.4.total status=REVIEW raw='۴۹,۴۰۰,۰۰۰' confidence=99.98761904761905 bbox=(120, 808, 240, 865) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.4.quantity status=EXTRACTED raw='۲۰' confidence=99.97047619047619 bbox=(248, 808, 289, 865) reason=None
glyph.cell=line.5.total status=REVIEW raw='۱,۵۷۰,۰۰۰' confidence=99.9847619047619 bbox=(120, 876, 240, 933) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.5.quantity status=EXTRACTED raw='۱' confidence=99.99714285714286 bbox=(248, 876, 289, 933) reason=None
glyph.cell=line.6.total status=REVIEW raw='۶,۹۰۰,۰۰۰' confidence=99.98190476190476 bbox=(120, 944, 240, 1001) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.6.quantity status=EXTRACTED raw='۵' confidence=99.97809523809524 bbox=(248, 944, 289, 1001) reason=None
glyph.cell=line.7.total status=REVIEW raw='۶,۸۷۰,۰۰۰' confidence=99.98190476190476 bbox=(120, 1012, 240, 1068) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.7.quantity status=EXTRACTED raw='۱' confidence=99.99714285714286 bbox=(248, 1012, 289, 1068) reason=None
glyph.cell=line.8.total status=REVIEW raw='۳,۷۰۰,۰۰۰' confidence=99.9847619047619 bbox=(120, 1079, 240, 1136) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.8.quantity status=EXTRACTED raw='۲' confidence=99.99809523809525 bbox=(248, 1079, 289, 1136) reason=None
glyph.cell=line.9.total status=REVIEW raw='??۹,۶۰۰,۰۰۰' confidence=0.0 bbox=(120, 1147, 240, 1204) reason="glyph 1 not accepted: ambiguous: margin 0.108 below 0.150; glyph 2 not accepted: ambiguous: margin 0.108 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.9.quantity status=EXTRACTED raw='۸' confidence=66.1847619047619 bbox=(248, 1147, 289, 1204) reason=None
glyph.cell=line.10.total status=REVIEW raw='۱۹,۰۵۰,۰۰۰' confidence=99.98761904761905 bbox=(120, 1215, 240, 1272) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.10.quantity status=EXTRACTED raw='۱۵' confidence=99.97809523809524 bbox=(248, 1215, 289, 1272) reason=None
glyph.cell=line.11.total status=REVIEW raw='۱,۳۸۰,۰۰۰' confidence=99.9863492063492 bbox=(120, 1283, 240, 1340) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.11.quantity status=EXTRACTED raw='۱' confidence=99.99714285714286 bbox=(248, 1283, 289, 1340) reason=None
glyph.cell=line.12.total status=REVIEW raw='۱,۵۷۰,۰۰۰' confidence=99.9847619047619 bbox=(120, 1351, 240, 1409) reason="arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.cell=line.12.quantity status=EXTRACTED raw='۱' confidence=99.99714285714286 bbox=(248, 1351, 289, 1409) reason=None
glyph.cell=invoice.payable status=REVIEW raw='????۷,????۰,۰۰۰' confidence=0.0 bbox=(195, 1427, 350, 1463) reason="glyph 1 not accepted: distance 0.644 exceeds 0.250; glyph 2 not accepted: distance 0.466 exceeds 0.250; glyph 3 not accepted: distance 0.308 exceeds 0.250; glyph 4 not accepted: distance 0.434 exceeds 0.250; glyph 7 not accepted: distance 0.855 exceeds 0.250; glyph 8 not accepted: distance 0.743 exceeds 0.250; glyph 9 not accepted: distance 0.308 exceeds 0.250; glyph 10 not accepted: distance 0.500 exceeds 0.250; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.9.total '??۹,۶۰۰,۰۰۰' is not a well-formed amount"
glyph.detected_line_rows=13
glyph.detected_line_indices=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
issuance.submit_calls=0
issuance.submit=NOT_CALLED
digital_invoice=NONE (non-issuing probe; no delegate attached)
e2e.result=PASS (uncertain numeric page held before submit)
```
