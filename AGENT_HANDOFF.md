# KANDOO DIGITAL INVOICE — AGENT HANDOFF

> This file is the mandatory project handoff and operational source for onboarding agents.
> It must be updated at the end of every meaningful project conversation/change affecting this repository.
> It is NOT a replacement for authoritative specs/registers; those remain authoritative for technical contracts.

## 1. Project Identity

Repository: `majid-ghanbari-dost/Kandoo-Digital-Invoice`
Purpose: dedicated development line for Kandoo Digital Invoice / Holoo capture / canonicalization work.
Parent project: `majid-ghanbari-dost/Kandoo`

This repository must contain only the Digital Invoice project line and its directly required artifacts.

Conceptual relationship:

Kandoo (parent)
└── Digital Invoice development line
    └── Kandoo-Digital-Invoice

The repositories are intentionally separate during development. At a later integration point the Digital Invoice line may be synchronized/merged back into the parent Kandoo project.

## 2. Mandatory Collaboration Rule

At the end of every meaningful project conversation or implementation change concerning this repository:

1. Update this file with the new verified state.
2. Record completed/changed WPs, decisions, blockers, ownership and next executable work.
3. Update relevant authoritative specs/registers/code/tests in the same project change.
4. Commit the resulting state.
5. Do not claim a change is integrated until the repository state reflects it.

Administrative discussion that causes no project-state change need not create a commit.

### Automatic Project-Sync Policy

For every conversation that produces a real project output/change, the coordinator must:
- update the actual project artifact in the authoritative repository when the available connector permits it;
- update this handoff in the same change/commit;
- update `KANDO_AGENT_COORDINATION.md` when ownership or execution state changes;
- report the exact repository commit/HEAD in the final report;
- never claim source integration when only a local/archive artifact was produced.

If the current tool environment cannot transfer a required local artifact into GitHub, record that limitation here and continue using the verified artifact as the source package; do not fabricate a successful sync.

## 3. Roles

Product Owner / Final Decision Maker: user
Technical Manager / Architect / Coordinator: ChatGPT
Agent 1: current implementation agent
Agent 2: second implementation/research agent

Each WP has one owner. Agents must not concurrently modify the same WP/files.

## 4. Collaboration Rules

- Frozen decisions are not reopened without direct contradictory evidence.
- No Architecture Loop.
- If contract + acceptance criteria are sufficient, implement directly.
- A mission should continue through multiple executable WPs when dependencies and ownership permit.
- Stop only at a real boundary: PO decision, missing contract/AC, real-world evidence requirement, contradiction with frozen architecture, or genuine technical blocker.
- Reports/artifact extraction are not independent project phases.
- Agent branches must not overwrite another agent's work.
- Main is the integration/source branch.
- Every substantive implementation must be tested and committed.
- Full archive + manifest + SHA-256 remain required for delivery checkpoints.

## 5. Frozen Architecture / Domain Principles

- Business → Store → Users/Devices.
- SQLite local Outbox ↔ Cloud API ↔ PostgreSQL.
- OperationId = idempotency key.
- Global Revision = sync cursor.
- AggregateVersion / OCC with base_version.
- No silent overwrite.
- Inventory is ledger-based.
- Negative inventory is allowed.
- Inventory shortage alone must not reject a Sale.
- CorrelationId is not a transaction/FK.
- Product deactivation uses is_active=false.
- Employee cannot final-confirm Product Candidate.
- Customer capture cannot auto-create a Customer.
- Canonical Invoice v1 is source-independent.
- UNRESOLVED and provenance are allowed.
- Native path: Sale → Invoice → Digital Invoice.
- External captures enter domain only through Canonicalization Gate.
- Gate outcomes: AUTO / REVIEW / REJECT.
- External capture must not silently create Sale / Inventory / KPI.
- Digital Invoice lifecycle: DRAFT → EXTRACTED → VALIDATED → ISSUED, plus REVOKED / SUPERSEDED.
- Holoo is an external accounting/tax system.
- Current Holoo path: Holoo → Print Spooler → Kandoo Agent → Raw Capture → durable local storage → extraction/recognition → Canonicalization Gate.
- No real production Holoo DB connection is permitted by the current project boundary.

## 6. Current Verified Project State

### E-03-kit — Known-answer print specification (2026-10-23)

- Created three Persian owner-facing documents: `docs/E-03-kit-inventory.md`, `docs/E-03-kit-guide-fa.md`, and `docs/E-03-kit-checklist.md`.
- The task-specific kit defines four synthetic invoices with exact row counts 4, 11, 4, and 11. Persian glyphs `۲` and `۶` each occur at least five times in every invoice's numeric cells. Exam invoices 3 and 4 are each printed twice on separate sheets, for six scans total.
- No invoice was entered into a live POS or inventory, and no print, scan, OCR, or pipeline execution was performed for the kit. Owner printing/scanning remains pending. The PM later authorized E-04.5/E-05 using the existing operator-confirmed `labels.json`; the six kit scans remain future cross-validation evidence, not a blocker to this label-derived template-bank task.
- The older Known-Answer note in `docs/PROJECT_STATE.md` differs (3 learning + 1 exam; every digit 0–9 and comma at least five times). The task-specific precedence and unresolved broader coverage are recorded in `docs/DECISIONS.md`; do not claim the old broader acceptance is met.
- `docs/MASTER_HANDOFF.md` is not present in this checkout; `AGENT_HANDOFF.md`, `KANDO_AGENT_COORDINATION.md`, `docs/DECISIONS.md`, `docs/PROJECT_STATE.md`, and the existing pipeline/E-07 docs were consulted.

### E-04.5 + E-05 — Label-derived fixtures and template bank (2026-10-23)

- PM authorized synthesis of four strict Canonical Invoice v0 fixtures from operator-confirmed `tests/fixtures/real/labels.json`. Files 29/31/32 are `EXTRACTED` fixture projections of E-07 `AUTO_CANDIDATE`; 33 is `DRAFT` because E-07 returned `REVIEW`. None is pipeline-emitted, `VALIDATED`, or `ISSUED`.
- `tests/fixtures/real/canonical/README.md` and `synthesis-manifest.json` identify `synthesized_from_labels: true`, source hashes, synthetic context fields, and statuses. Label quantities/totals remain integer v0 values; unit prices/subtotals are derived as documented. No extra Canonical property was added.
- `src/e05_template_bank/` builds a serializable geometry/numeric-format bank using label measurements and schema-validated canonical pairs. It performs no OCR. Four training observations cluster into one layout template; scores are advisory and resubstitution only.
- Validation: E-05 tests 9 passed; existing Canonical Invoice v0 tests 42 passed plus 39 subtests; `compileall` and `git diff --check` passed. Pytest/jsonschema were installed in a temporary `/tmp` virtual environment and were not added as repository dependencies.
- E-03 kit scans remain pending for later cross-validation. No OCR or image-extraction pipeline was run for E-04.5/E-05. E-05 was committed as `66b4274597471a2837b79f3019f03d13c8ff00e0`, pushed to the fixed branch, and tagged `stable-e-05`; remote branch/tag verification passed. Do not merge or create another PR. Existing PR #11 remains open; no PR action was performed.

### E-06 — Onboarding verdict (2026-10-23)

- Part A is documented in `docs/E-06-onboarding-verdict.md`; decisions ASM-35 through ASM-40 are in `docs/DECISIONS.md`. The policy is fail-closed: confidence `>=0.95` only advances to later gates, `[0.80, 0.95)` is REVIEW, `<0.80` is REJECT; N=4 warm-up, locked bank, D14 signed agreement, kit-only digit coverage, exact numeric checks, and audited store-owner verification gate ACCEPT.
- Part B is in `src/e06_onboarding_verdict/` with E-05-backed scoring, stable reason enums, configurable thresholds, and tests. Canonical-derived label fixtures are not used as kit scans; bad/partial fixtures are synthetic test-only, and bad fixture provenance is recorded by sidecar.
- Final verification: E-06 suite 18 passed; E-05 suite 9 passed; Canonical Invoice v0 suite 42 passed plus 39 subtests; `py_compile` and `git diff --check` passed. `TemplateMatch.to_dict()` compatibility is asserted through `VerdictResult.to_dict()`.
- The E-06 task commit, branch push/remote verification, and `stable-e-06` tag are pending. Work remains on `arena/9dc17500-kandoo-digital-invoice`; do not merge, force-push, create, or otherwise manage a PR. Existing PR #11 remains open and untouched.

WP-05 was verified on 2026-10-15; WP-09 and WP-10 verification was added on 2026-10-16 below.

- Work is on the Arena-fixed branch `arena/9dc17500-kandoo-digital-invoice`. `HOLOO-IMAGE-EXTRACTION-05` started from commit `395443ebdc3843767a526151f403170266fd3fbf`; no other branch was used and `main` was not changed.
- Native Checkout PO decisions remain recorded in `specs/native-checkout-contract-proposal.md`: Q1=Option 1, Q2=Option 2, Q3=Option 1, Q4=Option 1. Per PO direction this is future architecture, not current MVP priority; no Native Checkout code was added.
- `WP-HOLOO-IMAGE-EXTRACTION-02 — Persian OCR Support` is implemented in the experimental `src/image_extraction_adapter/` on top of the existing Tesseract/image-to-issuance path. `fas+eng` is configured, Persian/Arabic digits and separators and bidi controls are normalized, and the parser supports the tested Persian labels and line blocks. The original image extraction is preflighted against expected synthetic values before the existing `IssuanceService` is called.
- The current spatial-backend regression on the explicitly Synthetic Persian PNG used Tesseract 5.5.1 with `fas+eng`: 47 word scores, mean 91.47784295744681, minimum 65.31218. Declared values matched and the smoke reached `ISSUED`; its complete output is `deliveries/image-extraction-ocr/synthetic-spatial-regression-fa.log`. The fixture SHA-256 remains `df0e79c5acef87a6f2bcd3c9d36c6afadfb612a7210afadc0ea717c08856d782`. Earlier pre-spatial output is retained in `synthetic-persian-ocr-e2e.log`.
- The existing pipeline completed for the synthetic fixture: 4 configured validations `VALID`, domain `VALID/CLEAR`, canonicalization `ACCEPTED`, 2 canonical lines, and lifecycle `DRAFT → EXTRACTED → VALIDATED → ISSUED`; final Digital Invoice was verified with a 24-link trace. Evidence and IDs are in the retained smoke log and `deliveries/image-extraction-ocr/synthetic-digital-invoice-evidence.md`.
- A confidence threshold of 70 returned adapter-local `REVIEW_REQUIRED` at measured minimum 65; issuance was not called and no Digital Invoice was created. This is not a persisted P5.2 ReviewQueue record: Frozen contracts do not carry OCR confidence.
- Persian `fas` and English `eng` traineddata were successfully installed and exercised from `/tmp/kandoo-ocr-runtime`; model provenance and SHA-256 checksums are in the evidence document. Optional OCR/test packages and model binaries are not committed.
- `HOLOO-EXTRACTION-CONTINUATION-01` adds level-5 TSV word boxes and a right-to-left spatial fallback in `src/image_extraction_adapter/`. On the user-supplied cleaned image `deliveries/image-extraction-ocr/holo_row_detection.png`, it found four ordered table rows and assigned description/quantity/amount columns without visible row transposition. It preserved OCR strings and marked ambiguous or missing values `REVIEW`; report: `deliveries/image-extraction-ocr/real-holoo-spatial-evidence.md`.
- A `submit_image()` run used a counting wrapper around the real `IssuanceService`: `IssuanceService.submit` calls = 0 and no Digital Invoice was issued. This remains an adapter-local hold, not a persisted P5.2 review record.
- `WP-HOLOO-IMAGE-EXTRACTION-05 — OCR Preprocessing & Cell Isolation` crops row amounts, quantities, descriptions, and a detected payable box using TSV-derived geometry. Pillow implements Otsu/adaptive thresholding plus directional morphological line removal; numeric crops use PSM 7 and whitelist `0123456789۰۱۲۳۴۵۶۷۸۹.,`, while descriptions have no numeric whitelist. All three cell modes are returned as supplementary variants; they never overwrite the original fields.
- Real-image comparison: Otsu and adaptive tied at 4/9 exact digit-cell matches (55.56% exact-cell error, 56.76% digit CER); the unthresholded cell crop achieved 1/9 (88.89% error, 67.57% CER). The full-page baseline had 0/9 exact matches but a lower CER (54.05%). None of the five monetary cells matched the provisional manual visual reference in any cell mode. No numeric output was accepted; all remain `REVIEW`. Details: `deliveries/image-extraction-ocr/cell-preprocessing-comparison.md` and `.log`.
- The `submit_image()` preprocessing guard run returned `ImageExtractionReviewRequired`; the real-service spy counted 0 submit calls and no Digital Invoice was created. Evidence: `cell-preprocessing-issuance-guard.log`.
- The one-image scoring reference is a manual visual transcription not confirmed by the invoice owner; metrics are exploratory and do not establish general Holoo accuracy. The source image remains unchanged and Frozen contracts D-01–D-09 were not changed.
- Spatial/cell OCR uses `tesserocr.GetTSVText(0)`, which supplies equivalent level-5 text/confidence/box fields. `pytesseract` and the native Tesseract CLI were unavailable in this runtime; neither is claimed as used. Pillow 11.3.0, Tesseract 5.5.1, `tesserocr` 2.11.0, and `fas+eng` traineddata were supplied from `/tmp/kandoo-ocr-runtime`, not committed.
- Focused image-adapter/preprocessing tests passed (18); the full repository suite passed (1,712). Current English and Persian smoke regressions passed on explicitly Synthetic fixtures; those results are not Holoo validation.

### WP-HOLOO-IMAGE-EXTRACTION-09 — Dynamic Layout Detector (2026-10-16)

- `preprocessing.py` now uses Pillow image projection as the primary `crop_spatial_cells` geometry source. Horizontal and vertical candidates are contiguous black runs at least 80% of the axis maximum. The longest median-spaced horizontal chain identifies the grid; a shorter header interval is excluded, median row height filters rounded-payable borders, and vertical rules are projected only across the table span. TSV geometry is retained only as a compatibility fallback when projection is incomplete.
- `deliveries/image-extraction-ocr/dynamic-layout-projection.log` reports successful geometry and cell crops for all supplied images: `holo_row_detection.png` 4 rows/5 vertical boundaries/12 cells; `5.png` 5/5/15; `13.png` 13/5/39. These are the only three real layouts tested; this does not prove general invoice-layout accuracy.
- Glyph build used all three receipts. The row template profile contains all ten Persian digits plus comma. The evaluation is a row-disjoint split within the same 13-row invoice: source rows 3–8 train from a separate crop; rows 0–2 and 9–12 plus payable are scored from the full image. It is not independent-invoice validation. The visual labels are provisional and not confirmed by the invoice owner.
- The prior Adapter spatial geometry produced payable bbox `(199, 1431, 147, 28)` for `13.png`; its raw payable is `۳۴۷,۹۲۰,۰۰۰`. The Glyph evaluation's payable result did not match and remains `REVIEW`.
- 13-row Glyph evaluation: `exact_digit_cells=12/15`; 12 of 27 returned numeric cells were `EXTRACTED`, 15 were `REVIEW`; zero extracted values were wrong against the available visual labels. Arithmetic Gate failed because line 9 total was malformed (`??۹,۶۰۰,۰۰۰`); all amount cells remained REVIEW. Output: `deliveries/image-extraction-ocr/glyph-classifier-evaluate-13row-3invoice-build.log`.
- Focused image-adapter suite: 21 passed plus 6 subtests. Full repository suite: 1,715 passed plus 6 subtests. At WP-09 completion, `glyph_classifier.py` was not yet connected to `adapter.py`; WP-10 subsequently authorized and implemented that integration. Pillow, tesserocr, and pytest used for this run were installed only under `/tmp/kandoo-glyph-runtime`.

### WP-HOLOO-IMAGE-EXTRACTION-10 — Glyph Integration & E2E (2026-10-16)

- `ImageExtractionAdapter` accepts an explicit numeric-cell backend; `GlyphClassifierOCR` is now the primary numeric-cell engine while Tesseract remains the full-page text/layout backend. Any numeric cell with status other than `EXTRACTED`, missing numeric coverage, disagreement with parsed values, or a backend failure holds the whole page as `ImageExtractionReviewRequired`.
- The accepted Glyph variants are carried on `ImageExtractionReady`, and `submit_extraction()` rechecks the evidence when Glyph is configured so a ready result without valid numeric evidence cannot bypass the gate. Frozen contracts D-01–D-09 were unchanged.
- Guarded E2E on `deliveries/image-extraction-ocr/13.png` used `src/templates.json` and detected 13 rows/27 numeric cells: 12 EXTRACTED, 15 REVIEW. The arithmetic gate failed on malformed `line.9.total` (`??۹,۶۰۰,۰۰۰`); the payable was also malformed. The adapter returned `ImageExtractionReviewRequired`.
- E2E passed its fail-closed check: `NonIssuingSubmitProbe` call count was zero. The real `IssuanceService` was not attached to this guarded real-image run; no Digital Invoice was created and no `ISSUED` state was reached. Do not describe this as a production accuracy result or as an actual invoice issuance-service run.
- Full log and report: `deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-e2e.log` and `deliveries/image-extraction-ocr/wp-holoo-image-extraction-10-report.md`. Focused image-adapter suite: 25 passed; full repository suite: 1,719 passed plus 6 subtests.

## EOD Status [2026-10-16]

- **WP-09 (Dynamic Layout):** Successfully implemented and pushed as `e5ff46d`. Dynamic projection detected the supplied 4-, 5-, and 13-row layouts and their table columns. These are three tested layouts, not proof of general layout accuracy.
- **WP-10 (Integration & E2E):** Glyph was integrated into the adapter as the primary numeric-cell engine and the 13-row image was run with the Glyph templates/runtime assets. The arithmetic gate failed, so the adapter returned page-level `ImageExtractionReviewRequired`; the non-issuing submit probe recorded zero calls. The actual issuance service was not attached, so no Digital Invoice could be created and none reached `ISSUED`. Commit: `76a37f0`.
- The E2E demonstrates the extraction/review fail-closed path, not production OCR accuracy or owner-confirmed values. WP-09 labels/references remain provisional and the row-level train/evaluation split is within the same invoice, not independent-invoice validation. This adapter-local hold is not a persisted Frozen P5.2 review record; D-01–D-09 remain unchanged.
- **Priority for tomorrow:** Discuss the Windows App interface and the Per-Store Calibration process (clustering and operator labeling). The MVP technical control path for dynamic layout plus fail-closed numeric review has been demonstrated; production OCR accuracy/calibration is not yet proven. Keep Synthetic results separate from Holoo evidence.

## 7. Current Agent Ownership

- **Current implementation:** `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian support remains complete. `HOLOO-EXTRACTION-CONTINUATION-01` provides spatial OCR; `WP-HOLOO-IMAGE-EXTRACTION-05` adds cell preprocessing; `WP-HOLOO-IMAGE-EXTRACTION-09` adds dynamic projection layout; `WP-HOLOO-IMAGE-EXTRACTION-10` integrates Glyph as the primary numeric-cell backend with a page-level fail-closed review gate. The guarded 13-row E2E returned REVIEW and recorded zero submit-probe calls; real issuance was not attached and no invoice issued. OCR accuracy remains unproven and visual labels are provisional.
- **Product Owner:** Native Checkout Q1–Q4 decisions are recorded; any later change to those decisions or MVP priority remains a PO decision.
- **WP-11.2 Holoo DB adapter:** remains a separate deferred scope; the image-extraction adapter does not resolve its source mapping/authority/synchronization decisions.
- Preserve unrelated work already present in the working tree; do not absorb the untracked spooler adapter or runner into this image-extraction change.

## 8. Current Real Boundaries

1. The 13-row target `deliveries/image-extraction-ocr/13.png` was processed through full-page Tesseract plus Glyph numeric-cell OCR. Dynamic crop geometry returned 13 rows and 27 numeric cells (12 EXTRACTED, 15 REVIEW); all 13 totals and payable remain REVIEW after the arithmetic gate failed on malformed `line.9.total`. This does not establish general Holoo accuracy or suitability across layouts.
2. The guarded E2E adapter outcome was `ImageExtractionReviewRequired`; `NonIssuingSubmitProbe` recorded zero calls. The real `IssuanceService` was not attached to this run, so no Digital Invoice was created or reached `ISSUED`. This is an adapter-local hold, not a persistent Frozen `REVIEW` state or P5.2 ReviewQueue record.
3. WP-09 visual labels and references are provisional and unconfirmed by the invoice owner. The 13-row train/evaluation split is by rows from the same invoice, not independent-invoice validation. Do not use these results to auto-correct values or claim general accuracy.
4. Synthetic English and Persian smokes reached `ISSUED` through the existing pipeline, but this is Synthetic evidence only. Threshold 60 is a test setting, not a production recommendation; confidence is not calibrated.
5. The flat text parser handles tested English/Persian labels. The dynamic projection detector recovered four-column RTL tables in the three supplied images (4, 5, and 13 rows); it has not been validated on other layouts. Projection is primary for crops, with TSV geometry fallback. Ambiguous values remain REVIEW. Jalali-to-Gregorian calendar conversion is not implemented.
6. Native Checkout is future architecture only under the recorded Q1–Q4 choices; it is not the current MVP priority and no Native Checkout code was added.
7. WP-11.2 (Holoo database adapter/enrichment) remains separate and deferred pending its own decisions/evidence.

## 9. Repository and EOD Branch Status

All task-scoped image-extraction source, tests, Synthetic regression evidence, real-image spatial/preprocessing/Glyph reports, and handoff updates stay on `arena/9dc17500-kandoo-digital-invoice`. WP-05 was pushed as `fbfe7c0`; remote upload commit `ccb9e99` added the supplied `5.png` and `13.png` images before WP-09 work. WP-09 was pushed as `e5ff46d`; WP-10 was pushed as `76a37f0`. No change is to be merged to `main`. Earlier untracked WP-06 classifier artifacts and the unrelated spooler adapter/runner are intentionally left out of task commits. Do not force-push or overwrite remote work if a future non-fast-forward condition occurs; report that blocker instead.

## 10. Handoff Protocol

Every agent joining this project must:

1. Read this file completely.
2. Inspect current Git HEAD and working tree.
3. Read authoritative registers/specs.
4. Read `KANDO_AGENT_COORDINATION.md` for current WP ownership/status. `KANDOO_AGENT_COORDINATION.md` is legacy repository-bootstrap context, not the current image-extraction status.
5. Identify active WP ownership before editing anything.
6. Work only inside its assigned ownership boundary.
7. Run required tests/regression/smoke.
8. Commit.
9. Update this handoff and coordination state.
10. Report exact commit, tests, blockers and next executable work.

Never infer missing technical contracts from this handoff when an authoritative spec/register is available.
