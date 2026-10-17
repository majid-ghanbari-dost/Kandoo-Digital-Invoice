# Stash 72c4b48 inventory — target not present in this checkout

> **Important:** The requested stash object `72c4b4866f2b11dd845522ec6698a9d4d2265597` is not available in the current repository. The only stash listed is `fea913acede9`. The outputs below are faithfully recorded for `stash@{0}` for comparison and are **not** represented as the contents of stash 72c4b48.

## Section 1: `git stash list` output

Command: `git stash list`

```text
stash@{0}: On arena/9dc17500-kandoo-digital-invoice: safety snapshot before B2-2b
```

The listed stash resolves to `fea913acede9a750ea78a1aa9caacbd26289b596`. The requested SHA check returned:

```text
fatal: Not a valid object name 72c4b4866f2b11dd845522ec6698a9d4d2265597^{commit}
```

## Section 2: `git stash show --stat` output

Requested command: `git stash show --stat stash@{0}`

```text
 AGENT_HANDOFF.md | 110 ++++++++++++++++++++++++++++---------------------------
 1 file changed, 56 insertions(+), 54 deletions(-)
```

That default view reports only the tracked diff. To show the untracked snapshot paths included in the available stash, the following supplemental command was run. It reports the full path list for `fea913acede9`, not for the unavailable 72c4b48 object.

Command: `git stash show --stat --include-untracked stash@{0}`

```text
 AGENT_HANDOFF.md                                   |  110 +-
 KANDO_AGENT_COORDINATION.md                        |   76 +
 deliveries/image-extraction-ocr/13.png             |  Bin 0 -> 68437 bytes
 deliveries/image-extraction-ocr/31.png             |  Bin 0 -> 46209 bytes
 deliveries/image-extraction-ocr/5.png              |  Bin 0 -> 51303 bytes
 .../cell-preprocessing-benchmark.log               |   75 +
 .../cell-preprocessing-comparison.md               |  103 +
 .../cell-preprocessing-issuance-guard.log          |    8 +
 .../dynamic-layout-projection.log                  |    7 +
 .../glyph-classifier-build-13-rows03-08.png        |  Bin 0 -> 6816 bytes
 .../glyph-classifier-build-3invoices.log           |   38 +
 ...ph-classifier-evaluate-13row-3invoice-build.log |   37 +
 .../image-extraction-ocr/holo_row_detection.png    |  Bin 0 -> 24659 bytes
 .../real-holoo-spatial-evidence.md                 |  101 +
 .../synthetic-confidence-review.log                |    9 +
 .../synthetic-digital-invoice-evidence.md          |  147 +
 .../synthetic-english-regression.log               |   71 +
 .../image-extraction-ocr/synthetic-ocr-success.log |   71 +
 .../synthetic-persian-confidence-review.log        |   37 +
 .../synthetic-persian-ocr-e2e.log                  |   90 +
 .../synthetic-spatial-regression-en.log            |   71 +
 .../synthetic-spatial-regression-fa.log            |   90 +
 .../wp-holoo-image-extraction-09-report.md         |   41 +
 .../wp-holoo-image-extraction-10-e2e.log           |  108 +
 .../wp-holoo-image-extraction-10-report.md         |  171 ++
 deliveries/issue-4-smoke-suite/ARCHIVE-SHA256.txt  |    1 +
 deliveries/issue-4-smoke-suite/MANIFEST-SHA256.txt |  342 +++
 deliveries/issue-4-smoke-suite/README.md           |   58 +
 .../kandoo-issue4-smoke-suite-aca72c94.zip         |  Bin 0 -> 9680820 bytes
 docs/PROJECT_STATE.md                              |  234 ++
 docs/b2-2-payable-preprocessing-report.md          |  140 +
 docs/e2e-operator-instructions.md                  |   67 +
 docs/git-sync-report.md                            |  409 +++
 docs/glyph-leave-one-out-report.md                 |  407 +++
 docs/name-cluster-report.md                        |  674 +++++
 docs/payable-segmentation-diagnosis.md             |  150 +
 docs/stabilization-report.md                       |  406 +++
 scripts/diagnose_b2_2.py                           |  429 +++
 scripts/diagnose_payable.py                        |  432 +++
 scripts/run_e2e_real.py                            |  457 +++
 scripts/verify_image_integrity.py                  |  266 ++
 specs/native-checkout-contract-proposal.md         |    9 +
 src/image_extraction_adapter/README.md             |   86 +
 src/image_extraction_adapter/__init__.py           |   75 +
 src/image_extraction_adapter/adapter.py            |  582 ++++
 src/image_extraction_adapter/glyph_classifier.py   |  938 +++++++
 src/image_extraction_adapter/model.py              |  140 +
 src/image_extraction_adapter/ocr.py                |  378 +++
 src/image_extraction_adapter/parser.py             |  701 +++++
 src/image_extraction_adapter/preprocessing.py      |  684 +++++
 src/image_extraction_adapter/tests/__init__.py     |    1 +
 .../tests/fixtures/synthetic_invoice.png           |  Bin 0 -> 57603 bytes
 .../tests/fixtures/synthetic_invoice.svg           |   17 +
 .../tests/fixtures/synthetic_invoice_fa.png        |  Bin 0 -> 83045 bytes
 src/image_extraction_adapter/tests/test_adapter.py |  543 ++++
 .../tests/test_layout_safe.py                      |  168 ++
 .../tests/test_numeric_authority.py                |  230 ++
 .../tests/test_preprocessing.py                    |  243 ++
 src/labels_build.json                              |   63 +
 src/labels_eval.json                               |   31 +
 src/run_dynamic_layout_benchmark.py                |   75 +
 src/run_glyph_leave_one_out.py                     |  479 ++++
 src/run_image_preprocessing_benchmark.py           |  189 ++
 src/run_name_cluster_experiment.py                 |  528 ++++
 src/run_smoke_all.py                               |  128 +
 src/run_smoke_image_extraction.py                  |  405 +++
 src/templates.json                                 | 2896 ++++++++++++++++++++
 src/test_run_smoke_all.py                          |   90 +
 tests/fixtures/real/29.png                         |  Bin 0 -> 24659 bytes
 tests/fixtures/real/31.png                         |  Bin 0 -> 46209 bytes
 tests/fixtures/real/32.png                         |  Bin 0 -> 51303 bytes
 tests/fixtures/real/33.png                         |  Bin 0 -> 68437 bytes
 tests/fixtures/real/labels.json                    |  104 +
 tests/test_layout_real.py                          |  161 ++
 74 files changed, 15823 insertions(+), 54 deletions(-)
```

## Section 3: First 200 lines of the stash diff

Requested command: `git stash show -p stash@{0} | head -200`

```diff
diff --git a/AGENT_HANDOFF.md b/AGENT_HANDOFF.md
index 3986763..ed019b4 100644
--- a/AGENT_HANDOFF.md
+++ b/AGENT_HANDOFF.md
@@ -37,7 +37,7 @@ Administrative discussion that causes no project-state change need not create a
 For every conversation that produces a real project output/change, the coordinator must:
 - update the actual project artifact in the authoritative repository when the available connector permits it;
 - update this handoff in the same change/commit;
-- update `KANDOO_AGENT_COORDINATION.md` when ownership or execution state changes;
+- update `KANDO_AGENT_COORDINATION.md` when ownership or execution state changes;
 - report the exact repository commit/HEAD in the final report;
 - never claim source integration when only a local/archive artifact was produced.
 
@@ -93,66 +93,68 @@ Each WP has one owner. Agents must not concurrently modify the same WP/files.
 
 ## 6. Current Verified Project State
 
-P1–P10: completed/frozen.
-WP-11.1: implemented, tested, packaged and accepted at implementation level.
-WP-12.1: implemented and tested.
-WP-12.2: implemented and tested.
-WP-12.3: PO/G4 decision boundary; D-07/D-08/DEF2 require ratification.
-WP-11.2: Adapter must NOT be implemented until its required decisions/contract are resolved; a Decision Package exists.
-
-Latest reported P12 implementation source anchor: `d8dbc29`.
-Latest reported final delivery/hygiene commits in the previous working project: `a73fde5`, `574444f`.
-These commit IDs refer to the previous working project history and are not yet present in this newly-created repository.
-
-Latest verified transfer package available for bootstrap:
-- File: `kandoo-current-implementation10.zip`
-- ZIP SHA-256: `b8cda0290d5811ffd511b7e96b147c917cc2458a9f8faee40c60e46d388bc753`
-- Project files inside ZIP: 281
-- Total ZIP entries: 282 (281 project files + embedded manifest)
-- Manifest reports: 281 files
-- Manifest verification: 281/281 file hashes matched; 0 missing; 0 extra; 0 size mismatches.
-- Project content types verified: 248 Python, 33 Markdown, 1 text manifest.
-- This package is the current authoritative transfer candidate and supersedes the older 277-file delivery package for bootstrap purposes.
-- The package includes source anchor `54211b6` according to its embedded manifest.
-
-Latest reported verification from the working project:
-- WP-12.1 dedicated tests: 90/90, repeated independently ×3.
-- WP-12.2 dedicated tests: 33/33, repeated independently ×3.
-- Smoke: 19/19.
-- Full regression: 1439/1440 passed, with one known pre-existing date-sensitive flake:
-  `test_ir_provenance::test_no_raw_pipeline_values_are_stored`.
-- No new regression failure was reported.
+WP-05 was verified on 2026-10-15; WP-09 and WP-10 verification was added on 2026-10-16 below.
+
+- Work is on the Arena-fixed branch `arena/9dc17500-kandoo-digital-invoice`. `HOLOO-IMAGE-EXTRACTION-05` started from commit `395443ebdc3843767a526151f403170266fd3fbf`; no other branch was used and `main` was not changed.
+- Native Checkout PO decisions remain recorded in `specs/native-checkout-contract-proposal.md`: Q1=Option 1, Q2=Option 2, Q3=Option 1, Q4=Option 1. Per PO direction this is future architecture, not current MVP priority; no Native Checkout code was added.
+- `WP-HOLOO-IMAGE-EXTRACTION-02 — Persian OCR Support` is implemented in the experimental `src/image_extraction_adapter/` on top of the existing Tesseract/image-to-issuance path. `fas+eng` is configured, Persian/Arabic digits and separators and bidi controls are normalized, and the parser supports the tested Persian labels and line blocks. The original image extraction is preflighted against expected synthetic values before the existing `IssuanceService` is called.
+- The current spatial-backend regression on the explicitly Synthetic Persian PNG used Tesseract 5.5.1 with `fas+eng`: 47 word scores, mean 91.47784295744681, minimum 65.31218. Declared values matched and the smoke reached `ISSUED`; its complete output is `deliveries/image-extraction-ocr/synthetic-spatial-regression-fa.log`. The fixture SHA-256 remains `df0e79c5acef87a6f2bcd3c9d36c6afadfb612a7210afadc0ea717c08856d782`. Earlier pre-spatial output is retained in `synthetic-persian-ocr-e2e.log`.
+- The existing pipeline completed for the synthetic fixture: 4 configured validations `VALID`, domain `VALID/CLEAR`, canonicalization `ACCEPTED`, 2 canonical lines, and lifecycle `DRAFT → EXTRACTED → VALIDATED → ISSUED`; final Digital Invoice was verified with a 24-link trace. Evidence and IDs are in the retained smoke log and `deliveries/image-extraction-ocr/synthetic-digital-invoice-evidence.md`.
+- A confidence threshold of 70 returned adapter-local `REVIEW_REQUIRED` at measured minimum 65; issuance was not called and no Digital Invoice was created. This is not a persisted P5.2 ReviewQueue record: Frozen contracts do not carry OCR confidence.
+- Persian `fas` and English `eng` traineddata were successfully installed and exercised from `/tmp/kandoo-ocr-runtime`; model provenance and SHA-256 checksums are in the evidence document. Optional OCR/test packages and model binaries are not committed.
+- `HOLOO-EXTRACTION-CONTINUATION-01` adds level-5 TSV word boxes and a right-to-left spatial fallback in `src/image_extraction_adapter/`. On the user-supplied cleaned image `deliveries/image-extraction-ocr/holo_row_detection.png`, it found four ordered table rows and assigned description/quantity/amount columns without visible row transposition. It preserved OCR strings and marked ambiguous or missing values `REVIEW`; report: `deliveries/image-extraction-ocr/real-holoo-spatial-evidence.md`.
+- A `submit_image()` run used a counting wrapper around the real `IssuanceService`: `IssuanceService.submit` calls = 0 and no Digital Invoice was issued. This remains an adapter-local hold, not a persisted P5.2 review record.
+- `WP-HOLOO-IMAGE-EXTRACTION-05 — OCR Preprocessing & Cell Isolation` crops row amounts, quantities, descriptions, and a detected payable box using TSV-derived geometry. Pillow implements Otsu/adaptive thresholding plus directional morphological line removal; numeric crops use PSM 7 and whitelist `0123456789۰۱۲۳۴۵۶۷۸۹.,`, while descriptions have no numeric whitelist. All three cell modes are returned as supplementary variants; they never overwrite the original fields.
+- Real-image comparison: Otsu and adaptive tied at 4/9 exact digit-cell matches (55.56% exact-cell error, 56.76% digit CER); the unthresholded cell crop achieved 1/9 (88.89% error, 67.57% CER). The full-page baseline had 0/9 exact matches but a lower CER (54.05%). None of the five monetary cells matched the provisional manual visual reference in any cell mode. No numeric output was accepted; all remain `REVIEW`. Details: `deliveries/image-extraction-ocr/cell-preprocessing-comparison.md` and `.log`.
+- The `submit_image()` preprocessing guard run returned `ImageExtractionReviewRequired`; the real-service spy counted 0 submit calls and no Digital Invoice was created. Evidence: `cell-preprocessing-issuance-guard.log`.
+- The one-image scoring reference is a manual visual transcription not confirmed by the invoice owner; metrics are exploratory and do not establish general Holoo accuracy. The source image remains unchanged and Frozen contracts D-01–D-09 were not changed.
+- Spatial/cell OCR uses `tesserocr.GetTSVText(0)`, which supplies equivalent level-5 text/confidence/box fields. `pytesseract` and the native Tesseract CLI were unavailable in this runtime; neither is claimed as used. Pillow 11.3.0, Tesseract 5.5.1, `tesserocr` 2.11.0, and `fas+eng` traineddata were supplied from `/tmp/kandoo-ocr-runtime`, not committed.
+- Focused image-adapter/preprocessing tests passed (18); the full repository suite passed (1,712). Current English and Persian smoke regressions passed on explicitly Synthetic fixtures; those results are not Holoo validation.
+
+### WP-HOLOO-IMAGE-EXTRACTION-09 — Dynamic Layout Detector (2026-10-16)
+
+- `preprocessing.py` now uses Pillow image projection as the primary `crop_spatial_cells` geometry source. Horizontal and vertical candidates are contiguous black runs at least 80% of the axis maximum. The longest median-spaced horizontal chain identifies the grid; a shorter header interval is excluded, median row height filters rounded-payable borders, and vertical rules are projected only across the table span. TSV geometry is retained only as a compatibility fallback when projection is incomplete.
+- `deliveries/image-extraction-ocr/dynamic-layout-projection.log` reports successful geometry and cell crops for all supplied images: `holo_row_detection.png` 4 rows/5 vertical boundaries/12 cells; `5.png` 5/5/15; `13.png` 13/5/39. These are the only three real layouts tested; this does not prove general invoice-layout accuracy.
+- Glyph build used all three receipts. The row template profile contains all ten Persian digits plus comma. The evaluation is a row-disjoint split within the same 13-row invoice: source rows 3–8 train from a separate crop; rows 0–2 and 9–12 plus payable are scored from the full image. It is not independent-invoice validation. The visual labels are provisional and not confirmed by the invoice owner.
+- The prior Adapter spatial geometry produced payable bbox `(199, 1431, 147, 28)` for `13.png`; its raw payable is `۳۴۷,۹۲۰,۰۰۰`. The Glyph evaluation's payable result did not match and remains `REVIEW`.
+- 13-row Glyph evaluation: `exact_digit_cells=12/15`; 12 of 27 returned numeric cells were `EXTRACTED`, 15 were `REVIEW`; zero extracted values were wrong against the available visual labels. Arithmetic Gate failed because line 9 total was malformed (`??۹,۶۰۰,۰۰۰`); all amount cells remained REVIEW. Output: `deliveries/image-extraction-ocr/glyph-classifier-evaluate-13row-3invoice-build.log`.
+- Focused image-adapter suite: 21 passed plus 6 subtests. Full repository suite: 1,715 passed plus 6 subtests. At WP-09 completion, `glyph_classifier.py` was not yet connected to `adapter.py`; WP-10 subsequently authorized and implemented that integration. Pillow, tesserocr, and pytest used for this run were installed only under `/tmp/kandoo-glyph-runtime`.
+
+### WP-HOLOO-IMAGE-EXTRACTION-10 — Glyph Integration & E2E (2026-10-16)
+
+- `ImageExtractionAdapter` accepts an explicit numeric-cell backend; `GlyphClassifierOCR` is now the primary numeric-cell engine while Tesseract remains the full-page text/layout backend. Any numeric cell with status other than `EXTRACTED`, missing numeric coverage, disagreement with parsed values, or a backend failure holds the whole page as `ImageExtractionReviewRequired`.
+- The accepted Glyph variants are carried on `ImageExtractionReady`, and `submit_extraction()` rechecks the evidence when Glyph is configured so a ready result without valid numeric evidence cannot bypass the gate. Frozen contracts D-01–D-09 were unchanged.
+- Guarded E2E on `deliveries/image-extraction-ocr/13.png` used `src/templates.json` and detected 13 rows/27 numeric cells: 12 EXTRACTED, 15 REVIEW. The arithmetic gate failed on malformed `line.9.total` (`??۹,۶۰۰,۰۰۰`); the payable was also malformed. The adapter returned `ImageExtractionReviewRequired`.
+- E2E passed its fail-closed check: `NonIssuingSubmitProbe` call count was zero. The real `IssuanceService` was not attached to this guarded real-image run; no Digital Invoice was created and no `ISSUED` state was reached. Do not describe this as a production accuracy result or as an actual invoice issuance-service run.
+- Full log and report: `deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-e2e.log` and `deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-report.md`. Focused image-adapter suite: 25 passed; full repository suite: 1,719 passed plus 6 subtests.
+
+## EOD Status [2026-10-16]
+
+- **WP-09 (Dynamic Layout):** Successfully implemented and pushed as `e5ff46d`. Dynamic projection detected the supplied 4-, 5-, and 13-row layouts and their table columns. These are three tested layouts, not proof of general layout accuracy.
+- **WP-10 (Integration & E2E):** Glyph was integrated into the adapter as the primary numeric-cell engine and the 13-row image was run with the Glyph templates/runtime assets. The arithmetic gate failed, so the adapter returned page-level `ImageExtractionReviewRequired`; the non-issuing submit probe recorded zero calls. The actual issuance service was not attached, so no Digital Invoice could be created and none reached `ISSUED`. Commit: `76a37f0`.
+- The E2E demonstrates the extraction/review fail-closed path, not production OCR accuracy or owner-confirmed values. WP-09 labels/references remain provisional and the row-level train/evaluation split is within the same invoice, not independent-invoice validation. This adapter-local hold is not a persisted Frozen P5.2 review record; D-01–D-09 remain unchanged.
+- **Priority for tomorrow:** Discuss the Windows App interface and the Per-Store Calibration process (clustering and operator labeling). The MVP technical control path for dynamic layout plus fail-closed numeric review has been demonstrated; production OCR accuracy/calibration is not yet proven. Keep Synthetic results separate from Holoo evidence.
 
 ## 7. Current Agent Ownership
 
-Agent 1:
-- Owns the active P12 execution stream until it reaches its genuine PO/evidence boundary.
-- Must not assume this new repository already contains the working tree.
-
-Agent 2:
-- Owns independent work only after inspecting this repository and coordination state.
-- Must not modify Agent 1's active WP/files concurrently.
+- **Current implementation:** `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian support remains complete. `HOLOO-EXTRACTION-CONTINUATION-01` provides spatial OCR; `WP-HOLOO-IMAGE-EXTRACTION-05` adds cell preprocessing; `WP-HOLOO-IMAGE-EXTRACTION-09` adds dynamic projection layout; `WP-HOLOO-IMAGE-EXTRACTION-10` integrates Glyph as the primary numeric-cell backend with a page-level fail-closed review gate. The guarded 13-row E2E returned REVIEW and recorded zero submit-probe calls; real issuance was not attached and no invoice issued. OCR accuracy remains unproven and visual labels are provisional.
+- **Product Owner:** Native Checkout Q1–Q4 decisions are recorded; any later change to those decisions or MVP priority remains a PO decision.
+- **WP-11.2 Holoo DB adapter:** remains a separate deferred scope; the image-extraction adapter does not resolve its source mapping/authority/synchronization decisions.
+- Preserve unrelated work already present in the working tree; do not absorb the untracked spooler adapter or runner into this image-extraction change.
 
 ## 8. Current Real Boundaries
 
-1. P12.3: PO/G4 ratification of D-07, D-08 and DEF2.
-2. WP-11.2: required source mapping/authority/sync/conflict/write-back decisions and sufficient contract before Adapter implementation.
-3. Repository bootstrap: actual 281-file project tree must still be transferred from the verified local ZIP into `main`.
-
-## 9. Repository Bootstrap Status
-
-The repository contains the collaboration/handoff files, but the actual 281-file implementation tree has not yet been transferred.
-
-Verified transfer candidate:
-`kandoo-current-implementation10.zip` with SHA-256 `b8cda0290d5811ffd511b7e96b147c917cc2458a9f8faee40c60e46d388bc753`.
+1. The 13-row target `deliveries/image-extraction-ocr/13.png` was processed through full-page Tesseract plus Glyph numeric-cell OCR. Dynamic crop geometry returned 13 rows and 27 numeric cells (12 EXTRACTED, 15 REVIEW); all 13 totals and payable remain REVIEW after the arithmetic gate failed on malformed `line.9.total`. This does not establish general Holoo accuracy or suitability across layouts.
+2. The guarded E2E adapter outcome was `ImageExtractionReviewRequired`; `NonIssuingSubmitProbe` recorded zero calls. The real `IssuanceService` was not attached to this run, so no Digital Invoice was created or reached `ISSUED`. This is an adapter-local hold, not a persistent Frozen `REVIEW` state or P5.2 ReviewQueue record.
+3. WP-09 visual labels and references are provisional and unconfirmed by the invoice owner. The 13-row train/evaluation split is by rows from the same invoice, not independent-invoice validation. Do not use these results to auto-correct values or claim general accuracy.
+4. Synthetic English and Persian smokes reached `ISSUED` through the existing pipeline, but this is Synthetic evidence only. Threshold 60 is a test setting, not a production recommendation; confidence is not calibrated.
+5. The flat text parser handles tested English/Persian labels. The dynamic projection detector recovered four-column RTL tables in the three supplied images (4, 5, and 13 rows); it has not been validated on other layouts. Projection is primary for crops, with TSV geometry fallback. Ambiguous values remain REVIEW. Jalali-to-Gregorian calendar conversion is not implemented.
+6. Native Checkout is future architecture only under the recorded Q1–Q4 choices; it is not the current MVP priority and no Native Checkout code was added.
+7. WP-11.2 (Holoo database adapter/enrichment) remains separate and deferred pending its own decisions/evidence.
 
-The current GitHub connector has repository write permissions but no bulk local-directory upload/Git-push operation. Therefore the ZIP cannot be truthfully represented as integrated source until the 281 files are actually written to Git.
+## 9. Repository and EOD Branch Status
 
-Next bootstrap action:
-- transfer the exact 281 project files without reconstruction or modification;
-- preserve the embedded manifest;
-- verify repository file count/content against the transfer package;
-- update this handoff with actual repository HEAD and verification results.
+All task-scoped image-extraction source, tests, Synthetic regression evidence, real-image spatial/preprocessing/Glyph reports, and handoff updates stay on `arena/9dc17500-kandoo-digital-invoice`. WP-05 was pushed as `fbfe7c0`; remote upload commit `ccb9e99` added the supplied `5.png` and `13.png` images before WP-09 work. WP-09 was pushed as `e5ff46d`; WP-10 was pushed as `76a37f0`. No change is to be merged to `main`. Earlier untracked WP-06 classifier artifacts and the unrelated spooler adapter/runner are intentionally left out of task commits. Do not force-push or overwrite remote work if a future non-fast-forward condition occurs; report that blocker instead.
 
 ## 10. Handoff Protocol
 
@@ -161,7 +163,7 @@ Every agent joining this project must:
 1. Read this file completely.
 2. Inspect current Git HEAD and working tree.
 3. Read authoritative registers/specs.
-4. Read `KANDOO_AGENT_COORDINATION.md`.
+4. Read `KANDO_AGENT_COORDINATION.md` for current WP ownership/status. `KANDOO_AGENT_COORDINATION.md` is legacy repository-bootstrap context, not the current image-extraction status.
 5. Identify active WP ownership before editing anything.
 6. Work only inside its assigned ownership boundary.
 7. Run required tests/regression/smoke.
```

This diff is the tracked `AGENT_HANDOFF.md` portion of available stash `fea913acede9`. It is not the requested stash 72c4b48 diff. Untracked files are not included in this plain `git stash show -p` output.

## Section 4: Summary

- **Requested stash:** `72c4b4866f2b11dd845522ec6698a9d4d2265597` — unavailable in this checkout; it is absent from `git stash list`, and `git cat-file -e <sha>^{commit}` reports that the object is unavailable. Therefore its asserted 70-path / 14,625-insertion inventory cannot be verified or truthfully reproduced here.
- **Available stash examined:** `fea913acede9a750ea78a1aa9caacbd26289b596` (`stash@{0}`), a different object.
- **Available stash default stat:** 1 tracked path, `AGENT_HANDOFF.md`; 56 insertions and 54 deletions.
- **Available stash including untracked paths:** 74 paths, 15,823 insertions and 54 deletions, as reported by the supplemental command above.
- **Kinds of files in the available snapshot:** Python source and tests; Markdown handoff/docs/reports; JSON labels/templates; PNG/SVG fixtures and other binary images; logs; text manifests; a ZIP smoke-suite archive; and coordination/specification files.
- **Notable content in the available snapshot:** the tracked handoff changes project-state/coordination references. The untracked snapshot includes the image-extraction adapter and Glyph classifier, B2-2 diagnostics/reporting, invoice fixtures and labels, OCR/evaluation logs, and an issue-4 smoke-suite archive. These observations apply to stash `fea913acede9` only and must not be attributed to stash 72c4b48.
- **Stash safety:** no stash was applied or dropped. The requested object could not be inventoried because it is not present in this checkout.
