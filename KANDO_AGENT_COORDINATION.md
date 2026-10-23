# KANDOO DIGITAL INVOICE — AGENT COORDINATION

## Purpose

Operational coordination between implementation and governance agents. This file and `AGENT_HANDOFF.md` must reflect the verified repository state, not historical transfer-package status.

## Ownership

| Area | Owner | Status |
|---|---|---|
| `WP-HOLOO-IMAGE-EXTRACTION-02` | Current implementation agent | SYNTHETIC PERSIAN SUPPORT COMPLETE; synthetic evidence remains separate from Holoo validation |
| `HOLOO-EXTRACTION-CONTINUATION-01` | Current implementation agent | SPATIAL OCR FALLBACK IMPLEMENTED; one user-supplied image yielded four rows but remains REVIEW_REQUIRED; issuance not reached |
| `WP-HOLOO-IMAGE-EXTRACTION-05` | Current implementation agent | GEOMETRY-BASED CELL CROPS, PIL PREPROCESSING, AND PSM-7 OCR IMPLEMENTED; benchmark complete; supplied image remains REVIEW_REQUIRED |
| `WP-HOLOO-IMAGE-EXTRACTION-09` | Current implementation agent | COMPLETE; DYNAMIC PROJECTION TESTED ON 4/5/13-ROW IMAGES; GLYPH EVALUATION FAILS ARITHMETIC GATE |
| `WP-HOLOO-IMAGE-EXTRACTION-10` | Current implementation agent | COMPLETE; GLYPH INTEGRATED AS PRIMARY NUMERIC-CELL BACKEND; GUARDED 13-ROW E2E RETURNS PAGE-LEVEL REVIEW; NO SUBMIT |
| `E-03-kit` known-answer print specification | Current implementation agent | PERSIAN DOCUMENTS COMPLETE; OWNER PRINT/SCANS PENDING; FUTURE CROSS-VALIDATION |
| `E-04.5 + E-05` label-derived fixtures and template bank | Current implementation agent | COMMITTED/PUSHED; 9 FOCUSED TESTS PASS; `stable-e-05` VERIFIED |
| `E-06` onboarding verdict | Current implementation agent | IMPLEMENTED AND VALIDATED; COMMIT/PUSH/TAG PENDING; FIXED BRANCH ONLY |
| Native Checkout Q1–Q4 decisions | Product Owner | RECORDED; future architecture only, not current MVP priority |
| WP-11.2 Holoo database adapter | None until its decisions/evidence are resolved | DEFERRED; separate from image OCR |
| Governance/handoff | Technical Manager / governance agent | EOD sync recorded in `AGENT_HANDOFF.md` |

## Rules

1. One WP = one owner.
2. Do not edit another agent's active WP/files concurrently.
3. Reviews do not transfer ownership.
4. This Arena session is fixed to `arena/9dc17500-kandoo-digital-invoice`; do not switch/create another branch.
5. Frozen files require explicit evidence/authorization before modification.
6. Update this file and `AGENT_HANDOFF.md` when ownership or project state changes.
7. Stop at genuine decision, evidence, contract, or architecture blockers.
8. Never claim source integration or Holoo accuracy without verifiable artifacts and real-source evidence.
9. No merge to `main` is authorized by this EOD update.

## Current State — 2026-10-23

### E-03-kit — Known-answer print specification

- The three Persian deliverables are `docs/E-03-kit-inventory.md`, `docs/E-03-kit-guide-fa.md`, and `docs/E-03-kit-checklist.md`. They specify four synthetic invoice contents (4/11/4/11 rows), at least five Persian `۲` and `۶` glyphs per invoice, and two separate prints each for the exam invoices, for six scans.
- No live sales/inventory data is used. At E-03-kit completion, no invoice had been printed or scanned and no OCR or extraction pipeline had been run. The PM subsequently authorized E-04.5/E-05 from the existing operator-confirmed labels. The six scans remain pending for future cross-validation; they are not a prerequisite for the label-derived bank.
- The older `docs/PROJECT_STATE.md` summary specifies 3 learning/1 exam and coverage of every digit plus comma; the current task instead gives 2 learning/2 exam and glyphs ۲/۶. This unresolved scope discrepancy is recorded in `docs/DECISIONS.md`; the kit does not claim the broader condition is met.

### E-04.5 + E-05 — Label-derived fixtures and template bank

- Four Canonical v0 fixtures (29/31/32/33) are synthesized from `labels.json`; the manifest/README mark provenance and identify every synthetic context field. Invoice 33 remains `DRAFT`; no fixture is pipeline-emitted or issuable.
- The Python package `src/e05_template_bank/` validates label/canonical agreement, groups the four layouts into one reusable profile, and exposes weighted advisory matching/JSON serialization. It does not run OCR or alter the E-02 pipeline.
- Focused E-05 suite: 9 passed. Existing Canonical Invoice v0 tests: 42 passed plus 39 subtests. Self-match scores are 0.998544 (29), 0.995653 (31), 0.997350 (32), and 0.971928 (33); these are training-set resubstitution only, not independent accuracy. Commit `66b4274597471a2837b79f3019f03d13c8ff00e0`, branch push, and `stable-e-05` tag are verified.

### E-06 — Onboarding verdict

- Part A is documented in `docs/E-06-onboarding-verdict.md`; ASM-35 through ASM-40 are in `docs/DECISIONS.md`. The evaluator is fail-closed, uses existing E-05 matching, and requires high confidence, exact raw/canonical numeric agreement, N=4 warm-up, locked bank, D14 signed-agreement evidence, kit-scoped `۲`/`۶` coverage, and audited store-owner field verification before ACCEPT.
- Part B is implemented under `src/e06_onboarding_verdict/`; bad and partial onboarding fixtures are test-only synthetic data. The bad Canonical-derived fixture has provenance in an adjacent sidecar rather than an out-of-schema Canonical property.
- Final verification: E-06 tests 18 passed; E-05 tests 9 passed; Canonical Invoice v0 tests 42 passed plus 39 subtests; `py_compile` and `git diff --check` passed. The serialization test confirms compatibility with `TemplateMatch.to_dict()`. E-06 commit, branch remote verification, and `stable-e-06` tag are pending.
- Continue only on `arena/9dc17500-kandoo-digital-invoice`. Do not create, close, merge, or otherwise manage a PR; existing PR #11 is open and was not changed.

### Native Checkout

PO choices are recorded in `specs/native-checkout-contract-proposal.md`:

- Q1: Option 1 — additive native-source contract, no fake capture.
- Q2: Option 2 — non-fiscal pilot with operator-entered amounts, no tax claim.
- Q3: Option 1 — no post-commit correction in this slice.
- Q4: Option 1 — stable `sale_id` for idempotency.

This is approved for future architecture, not current MVP priority. No Native Checkout code was added.

### External image OCR

- `src/image_extraction_adapter/` uses Tesseract with both a coordinate-free text parser and a fail-closed spatial fallback. The fallback groups TSV word boxes into right-to-left columns and numbered rows. `PERSIAN_TESSERACT_LANGUAGE` is `fas+eng`; text normalization supports Persian/Arabic digits, separators, letter forms, and bidirectional controls.
- The clearly labeled Synthetic Persian raster passed the current post-spatial-backend Tesseract → expected-value preflight → existing `IssuanceService` → Digital Invoice smoke. OCR: Tesseract 5.5.1 (`fas+eng`), 47 word scores, minimum 65.31218, mean 91.47784295744681. Declared values matched; the pipeline reached `ISSUED`, verified `true`, with a 24-link trace. The English Synthetic regression also passed.
- Evidence includes `synthetic-spatial-regression-fa.log`, `synthetic-spatial-regression-en.log`, `synthetic-digital-invoice-evidence.md`, and the earlier `synthetic-persian-ocr-e2e.log` / `synthetic-persian-confidence-review.log`. These Synthetic results do not validate Holoo.
- At threshold 70, the Persian fixture was held as adapter-local `REVIEW_REQUIRED`; issuance was not called. This is not a persisted Frozen P5.2 ReviewQueue item or a Digital Invoice `REVIEW` state.
- Persian `fas` and English `eng` traineddata were installed and exercised from `/tmp`; provenance/checksums are recorded in the evidence. No traineddata binaries or optional runtime packages were added to the repository.
- One user-supplied cleaned image, `deliveries/image-extraction-ocr/holo_row_detection.png`, was run through `submit_image()`. The spatial parser found four ordered rows and the amount/quantity/name/sequence columns, while preserving ambiguous raw values. Per-field output and the image hash are in `deliveries/image-extraction-ocr/real-holoo-spatial-evidence.md`.
- The image returned `ImageExtractionReviewRequired`; a counting wrapper around the real `IssuanceService` recorded zero `submit` calls. No Digital Invoice was issued. This is an adapter-local hold, not a persisted Frozen P5.2 review record.
- The single image did not yield reliable line totals, payable, net total, quantities, or unit prices. It demonstrates a partial layout parse only—not general Holoo accuracy.
- WP-05 added geometry-based crops for numeric cells and descriptions, plus a payable crop. The source raster is not modified. OCR operates on crops; Pillow performs Otsu/adaptive thresholding and directional morphological rule removal. Numeric cells use PSM 7 and whitelist `0123456789۰۱۲۳۴۵۶۷۸۹.,`; description cells receive no numeric whitelist. Cell variants are supplementary and do not replace existing assessment values.
- For this image, the unprocessed numeric-crop mode scored 1/9 exact matches (88.89% exact-cell error; 67.57% digit CER); Otsu and adaptive both scored 4/9 (55.56% error; 56.76% CER). The full-page baseline scored 0/9 exact with 54.05% CER. Neither preprocessing mode matched any of five monetary cells to the provisional visual transcription. The transcription is manual and unconfirmed by the invoice owner; all variants remain REVIEW. Reproducible details are in `deliveries/image-extraction-ocr/cell-preprocessing-comparison.md` and `cell-preprocessing-benchmark.log`.
- A separate `submit_image()` guard probe using the real workspace service returned `ImageExtractionReviewRequired`, collected 31 variants, and recorded zero `IssuanceService.submit` calls and no Digital Invoice was created. See `cell-preprocessing-issuance-guard.log`. This is an adapter-local hold, not a persisted Frozen P5.2 review record.
- Geometry uses `tesserocr.GetTSVText(0)` for level-5 text/confidence/box fields because neither `pytesseract` nor the native Tesseract CLI is present in this runtime. It does not claim to call `pytesseract.image_to_data`.
- Frozen contracts D-01–D-09 were not changed. The original raster hash is reported by the adapter but is not persisted by the Frozen Capture contract.
- WP-05 validation: 18 focused preprocessing/adapter tests passed; full repository suite passed (1,712 tests). Synthetic English and Persian smoke checks passed and remain explicitly Synthetic, not Holoo evidence.
- WP-09 added `detect_dynamic_table_layout()` and made image projections primary in `crop_spatial_cells()`; old OCR geometry is fallback only. Contiguous black horizontal/vertical runs use the 80%-of-longest rule; the longest median-spaced grid excludes the short rounded-payable edges and applies median row-height filtering. No page-specific row coordinates or expected row count are used.
- The projection benchmark returned 4/4, 5/5, and 13/13 rows, five column rules, and 12/15/39 amount/quantity/description cell crops respectively. Detailed boundaries, medians, and image hashes: `deliveries/image-extraction-ocr/dynamic-layout-projection.log`.
- Glyph templates were built from all three receipts: all 0–9 plus comma are present in the `row` profile. The 13-row image is split by rows 3–8 for training and rows 0–2 plus 9–12 for labelled holdout; the payable is scored. This is a within-invoice row holdout, not independent-invoice validation. All labels are provisional visual transcriptions, not invoice-owner-confirmed ground truth.
- 13-row Glyph evaluation: `exact_digit_cells=12/15`; 12 `EXTRACTED`, 15 `REVIEW` (counted across all 27 returned numeric cells), zero `EXTRACTED` values mismatch their visual labels. Arithmetic Gate **failed** on unreadable `line.9.total` (`??۹,۶۰۰,۰۰۰`); the payable also remains `REVIEW`. Full output is `deliveries/image-extraction-ocr/glyph-classifier-evaluate-13row-3invoice-build.log`.
- WP-09 validation: image-adapter suite 21 passed plus 6 subtests; full repository suite 1,715 passed plus 6 subtests. Temporary Pillow/tesserocr/pytest runtime stayed under `/tmp`; no repository dependency changes. At WP-09 completion, `glyph_classifier.py` had not yet been connected to `adapter.py`; WP-10 subsequently authorized and implemented that integration.
- WP-10 integrated `GlyphClassifierOCR` as the adapter's primary numeric-cell backend, retaining Tesseract for full-page text/layout context. If any numeric cell is REVIEW, results are missing, or Glyph disagrees with parsed numeric values, the entire page stays `ImageExtractionReviewRequired`; accepted Glyph evidence is carried through Ready and rechecked by `submit_extraction`.
- Guarded E2E used `deliveries/image-extraction-ocr/13.png`, `src/templates.json`, and required temporary runtime assets. It detected 13 rows/27 numeric cells (12 EXTRACTED, 15 REVIEW); the arithmetic gate failed on malformed `line.9.total` and payable. The adapter returned page-level REVIEW. `NonIssuingSubmitProbe` recorded 0 calls; the actual issuance service was not attached, so no Digital Invoice could be created and none reached ISSUED. This is a control-flow result, not proof of OCR accuracy.
- WP-10 report and complete output: `deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-report.md` and `wp-holoo-image-extraction-10-e2e.log`. WP-10 focused suite: 25 passed; full repository suite: 1,719 passed plus 6 subtests. Visual labels are provisional, not owner-confirmed; row-level holdout is within one invoice.

### Next executable work

E-06 final compilation, tests, and `git diff --check` have passed. Remove generated caches, stage and review the E-06 task group, then commit it on the fixed branch, push only that branch, verify with `git ls-remote origin`, and create/push `stable-e-06`. Do not merge or manage a PR; the existing PR #11 remains open and untouched. E-03-kit scans remain pending for later cross-validation. The technical extraction/review path through WP-10 remains fail-closed and the 13-row E2E is not production-accuracy evidence. Before accuracy/calibration claims, use held-out owner-authorized scans and independent invoices. Keep uncertain fields in REVIEW and do not present label-derived fixtures as Holoo evidence. Native Checkout remains outside current MVP priority; WP-11.2 remains a separate deferred Holoo database-adapter scope. Persian calendar (Jalali) conversion is not implemented.

## Branch / integration boundary

WP-09 (`e5ff46d`) and WP-10 (`76a37f0`) are pushed to `arena/9dc17500-kandoo-digital-invoice`. Continue using that fixed branch. Do not force-push or overwrite remote work if a non-fast-forward condition is encountered; report the blocker. No merge to `main` is part of this task.
