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
| `E-03-kit-v2` print-extraction kit | Current implementation agent | 3+1 PAGES, VALUES, COVERAGE, AND CAPTURE CONTRACT COMPLETE; ACTUAL WINDOWS HELLO CAPTURE OWNER-VERIFICATION PENDING; V1 PRESERVED/OBSOLETE |
| `E-04.5 + E-05` label-derived fixtures and template bank | Current implementation agent | COMMITTED/PUSHED; 9 FOCUSED TESTS PASS; `stable-e-05` VERIFIED |
| `E-06` onboarding verdict | Current implementation agent | COMPLETE; COMMIT `91f5b04` WITH `stable-e-06` PRESENT IN LOCAL HISTORY |
| `E-26` onboarding CLI | Current implementation agent | IMPLEMENTED; local verification complete; built-executable smoke-flow wired for Windows CI; final push-CI proof recorded in E-26 closeout |
| Native Checkout Q1–Q4 decisions | Product Owner | RECORDED; future architecture only, not current MVP priority |
| WP-11.2 Holoo database adapter | None until its decisions/evidence are resolved | DEFERRED; separate from image OCR |
| Governance/handoff | Technical Manager / governance agent | EOD sync recorded in `AGENT_HANDOFF.md` |

## Rules

1. One WP = one owner.
2. Do not edit another agent's active WP/files concurrently.
3. Reviews do not transfer ownership.
4. This Arena session is fixed to `arena/d892dd9b-kandoo-digital-invoice`; do not switch/create another branch.
5. Frozen files require explicit evidence/authorization before modification.
6. Update this file and `AGENT_HANDOFF.md` when ownership or project state changes.
7. Stop at genuine decision, evidence, contract, or architecture blockers.
8. Never claim source integration or Holoo accuracy without verifiable artifacts and real-source evidence.
9. Do not merge a PR unless explicitly authorized. PR #11 was merged before the current window; do not alter that completed merge.

## Current Serial Dispatch — 2026-10-28

- PR #11 was merged before this window. `main` is based at merge commit `a8662f458255d66307d0783bd7e14b80addeb06b`; this session stays on the fixed branch `arena/d892dd9b-kandoo-digital-invoice`.
- E-26 implements `onboard build`, `onboard verdict`, and `onboard register-type`; the E-16 schemas, stable exit codes, Windows one-folder packaging, E-20 synthetic built-executable smoke flow, five focused CLI tests, and C# `Process.Start` guide are in place. The full Python suite passed 1,954 tests plus 119 subtests; focused E-05/E-06/E-08/E-16 tests passed 52; onboarding CLI tests passed 5. `git diff --check` and `py_compile` passed.
- `scripts/verify_windows_bundle.py` now runs the built executable through build → verdict → register-type against the E-20 synthetic store. No local Windows execution is claimed; acceptance evidence is the `windows-build` and `python-tests` push workflows at the full E-26 task SHA. The final task report records that SHA, the exact run URLs/statuses, and the `stable-e-26` tag.
- Frozen `contracts/` and `src/image_extraction_adapter/adapter.py` are unchanged. Task sequence: E-26 → E-27 → N-07 → E-28 → E-29.

## Historical Serial Dispatch — 2026-10-27 (superseded)

- Work remains on `arena/9dc17500-kandoo-digital-invoice`; PR #11 is open and `main` is unchanged. No merge, force-push, or frozen-contract edit is authorized.
- N-04 is complete: measurement SHA `3d9d28b00acbf0f1944024d5530a4922f15b16e9` passed Python [40311286610](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40311286610) and Windows [40311286720](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40311286720); docs-only closeout SHA `8308023e208d8a648b6bd410f63f2c821d476ab7` is tagged `stable-n-04` and passed Python [40313438293](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40313438293) and Windows [40313438283](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40313438283). Intermediate run [40308983293](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40308983293) was at `af8dae13b323f71df0b0b535eb6938672fa74930`, job `Windows / Python 3.11 / PyInstaller onedir`; it failed at step “Windows tests - frozen E-11 contract package” (`pytest tests/test_e11_contract_package.py`), exit 1. PyInstaller never ran, and the failing assertion is unidentified because log retrieval returned EOF. The same-SHA PR Windows run passed; green final tagged-commit runs supersede this intermediate red. Calling it a Windows packaging failure was an executive-manager mischaracterization. The owner/verifier audit of the whole-window 17 changed paths found no file under `contracts/` and no `src/image_extraction_adapter/adapter.py`.
- N-05 is complete: implementation SHA `3f5a26e7add23d188163188ba61cfba6d802b691`; closeout SHA `0cc7f32769b8bbc0a035b6ea27fd6e411e1fa256`, tagged `stable-n-05`. Final Python run [40316077949](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40316077949) and Windows run [40316078058](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40316078058) both passed. Evaluation references stay provisional and owner-unconfirmed; dated price observations are not inferred from the four null-date fixtures.
- E-24 implementation SHA `b8f4047cef946daaab3f11880669266de932e5bb` passed Python [40322487925](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40322487925) and Windows [40322487999](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40322487999). It adds the explicit profile registry/evaluator, 11 synthetic fail-closed routes (zero EXTRACTED-but-wrong), and four byte-compatible Holo output goldens. Docs-only closeout commit `9305efbf75091f3a5df1c57bb6fe9756af096c9b` is tagged `stable-e-24`; closeout Python run [40323114292](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40323114292) and Windows run [40323114298](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40323114298) both passed.
- N-06 is complete at `bbf08e1aed31d6f165294ffe4ca0f9cf4db3d2cb`, tagged `stable-n-06`. PM-relayed push Python run #61 / [40391678234](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40391678234) passed (5m 40s); push Windows run #57 passed (1m 19s; global ID was not relayed). PR Windows run [40391682594](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40391682594) passed. PR Python run [40391682589](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40391682589) first failed in `Ubuntu / Python 3.12` with exit 1; its attempt-2 rerun was green (20:15:24Z–20:18:35Z, conclusion SUCCESS). The identical tree passed push run #61; the first-attempt red is classified TRANSIENT (flake or ubuntu-26 runner migration), with no code change. PR #11 checks are all green after the rerun.
- E-25 is the current docs-only closeout for this window: correct the N-04 intermediate-failure description in `AGENT_HANDOFF.md` and `docs/n04-name-suggestions.md` in the same commit group, retain the task-window SHA/tag/CI ledger, and create only the new annotated `stable-e-25` tag. PR #11 remains open; `main` is unchanged.

## Historical State — 2026-10-24

### E-03-kit-v1 — archived and obsolete

- The original v1 files `docs/E-03-kit-inventory.md`, `docs/E-03-kit-guide-fa.md`, and `docs/E-03-kit-checklist.md` remain preserved for audit history and now carry the exact warning “Kit v1 is OBSOLETE per Director, do not use.”
- V1 must not be printed or used: it specified the incorrect print source, phone-scanned capture, an assumed unit-price column, and incomplete digit coverage.

### E-03-kit-v2 — active print-extraction kit

- `docs/E-03-kit-v2/` contains exactly three learning pages and one exam page, a combined 0–9/comma coverage matrix, and expected values restricted to quantities, line totals, and invoice-level payable; no unit-price field is assumed or included.
- Combined counts from controlled value strings are `۰` 10, `۱` 14, `۲` 23, `۳` 9, `۴` 12, `۵` 11, `۶` 20, `۷` 6, `۸` 8, `۹` 7, and comma 20. Each page also satisfies the existing E-06 minimum of five Persian `۲` and `۶` glyphs.
- Owner-confirmed safety boundary: Hello test invoices contain fabricated data only; no real customer, sale, or stock movement occurs; nothing needs cancellation, deletion, or rollback; the print job itself is the test artifact and the fake invoice may be discarded.
- Required capture uses an actual Hello Windows print job: KandooPrintProbe captures its SPL, converts to PNG for downstream OCR/extraction, and writes adjacent `Report.txt` metadata (printer, spool job ID, timestamp, page count). Phone scans and word-processor prints are prohibited. Actual Windows SPL capture/conversion is not available in Arena and remains owner verification; no local verification is claimed.
- See `docs/E-03-kit-v2/README.md`, `scripts/verify_e03_kit_v2.py`, and `tests/test_e03_kit_v2.py` for the workflow, checker, and tests. Local validation passed: 5 focused tests, all eleven glyph thresholds, `py_compile`, and `git diff --check`; capture mode was not run because no real owner capture is available in Arena.

### E-04.5 + E-05 — Label-derived fixtures and template bank

- Four Canonical v0 fixtures (29/31/32/33) are synthesized from `labels.json`; the manifest/README mark provenance and identify every synthetic context field. Invoice 33 remains `DRAFT`; no fixture is pipeline-emitted or issuable.
- The Python package `src/e05_template_bank/` validates label/canonical agreement, groups the four layouts into one reusable profile, and exposes weighted advisory matching/JSON serialization. It does not run OCR or alter the E-02 pipeline.
- Focused E-05 suite: 9 passed. Existing Canonical Invoice v0 tests: 42 passed plus 39 subtests. Self-match scores are 0.998544 (29), 0.995653 (31), 0.997350 (32), and 0.971928 (33); these are training-set resubstitution only, not independent accuracy. Commit `66b4274597471a2837b79f3019f03d13c8ff00e0`, branch push, and `stable-e-05` tag are verified.

### E-06 — Onboarding verdict

- Part A is documented in `docs/E-06-onboarding-verdict.md`; ASM-35 through ASM-40 are in `docs/DECISIONS.md`. The evaluator is fail-closed, uses existing E-05 matching, and requires high confidence, exact raw/canonical numeric agreement, N=4 warm-up, locked bank, D14 signed-agreement evidence, kit-scoped `۲`/`۶` coverage, and audited store-owner field verification before ACCEPT.
- Part B is implemented under `src/e06_onboarding_verdict/`; bad and partial onboarding fixtures are test-only synthetic data. The bad Canonical-derived fixture has provenance in an adjacent sidecar rather than an out-of-schema Canonical property.
- Final verification: E-06 tests 18 passed; E-05 tests 9 passed; Canonical Invoice v0 tests 42 passed plus 39 subtests; `py_compile` and `git diff --check` passed. The serialization test confirms compatibility with `TemplateMatch.to_dict()`. E-06 is complete at commit `91f5b04`; the local `stable-e-06` tag is present.
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

The only remaining E-03-kit-v2 evidence action is for the owner to run the four fabricated pages through Hello on Windows and provide the actual KandooPrintProbe SPL→PNG captures with adjacent `Report.txt` files. Arena cannot run this Windows print-capture verification. Do not substitute scans or word-processor prints, and do not claim capture success until the owner reviews the actual outputs. The technical extraction/review path through WP-10 remains fail-closed and the 13-row E2E is not production-accuracy evidence. Before accuracy/calibration claims, use held-out owner-authorized prints and independent invoices. Keep uncertain fields in REVIEW and do not present label-derived fixtures as Holoo evidence. Native Checkout remains outside current MVP priority; WP-11.2 remains a separate deferred Holoo database-adapter scope. Persian calendar (Jalali) conversion is not implemented.

## Branch / integration boundary

Continue using only `arena/9dc17500-kandoo-digital-invoice`; E-03-kit-v2 started from remote-verified commit `d70fb3778b6f69de23740ec9f16cbb4ac221445b` (`stable-e-08`). Push only this fixed branch and verify its remote SHA before creating the annotated `stable-e-03-kit-v2` tag. Do not force-push or overwrite remote work if a non-fast-forward condition is encountered; report the blocker. Do not merge or operate on PR #11, which remains open and untouched.
