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
- update `KANDOO_AGENT_COORDINATION.md` when ownership or execution state changes;
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

WP-05 was verified on 2026-10-15; WP-09 verification was added on 2026-10-16 below.

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
- Focused image-adapter suite: 21 passed plus 6 subtests. Full repository suite: 1,715 passed plus 6 subtests. `glyph_classifier.py` is not connected to `adapter.py`; no issuance path or Frozen contract changed. Pillow, tesserocr, and pytest used for this run were installed only under `/tmp/kandoo-glyph-runtime`.

## EOD Status [2026-10-16]

- Native Checkout Q1–Q4 decisions remain approved for future architecture, not current MVP priority.
- `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian implementation and verification remain complete. Its results stay explicitly Synthetic and are not treated as Holoo evidence.
- `HOLOO-EXTRACTION-CONTINUATION-01` implemented the spatial fallback and ran the supplied cleaned image. Four row positions were recovered, but critical fields remain `REVIEW`; see `deliveries/image-extraction-ocr/real-holoo-spatial-evidence.md`.
- `WP-HOLOO-IMAGE-EXTRACTION-05` implemented cell crops, Pillow Otsu/adaptive thresholding, morphological rule removal, and PSM-7 column-specific OCR. Otsu/adaptive improved exact-cell quantity matching but failed all monetary cells; all OCR variants remained `REVIEW` and no issuance occurred. The one-image manual scoring reference remains unconfirmed.
- `WP-HOLOO-IMAGE-EXTRACTION-09` implemented dynamic image-projection layout detection. It recovered 4, 5, and 13 rows with five rules and cropped all expected cells. Glyph evaluation on a disjoint row subset of the 13-row invoice reached 12/15 exact labelled cells, but Arithmetic Gate failed on an unreadable line total; 12 cells were EXTRACTED and 15 REVIEW, with no incorrect EXTRACTED values against provisional labels. Labels are not owner-confirmed, and the split is not independent-invoice validation.
- Next executable work: obtain invoice-owner-confirmed ground truth and additional independent authorized invoice layouts, then address the glyph classifier's 13-row amount/payable errors. Keep uncertain values fail-closed and the classifier unconnected to issuance until separately authorized. Do not use Synthetic fixtures as Holoo evidence or substitute Native Checkout/WP-11.2 work for this path.

## 7. Current Agent Ownership

- **Current implementation:** `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian support remains complete. `HOLOO-EXTRACTION-CONTINUATION-01` provides spatial OCR; `WP-HOLOO-IMAGE-EXTRACTION-05` adds cell preprocessing; `WP-HOLOO-IMAGE-EXTRACTION-09` adds dynamic projection layout and a test-only glyph evaluation. The Glyph engine remains unconnected to issuance.
- **Product Owner:** Native Checkout Q1–Q4 decisions are recorded; any later change to those decisions or MVP priority remains a PO decision.
- **WP-11.2 Holoo DB adapter:** remains a separate deferred scope; the image-extraction adapter does not resolve its source mapping/authority/synchronization decisions.
- Preserve unrelated work already present in the working tree; do not absorb the untracked spooler adapter or runner into this image-extraction change.

## 8. Current Real Boundaries

1. One user-supplied cleaned invoice image was processed. The spatial parser detected four numbered rows and their column positions, but the result is partial; most line values and key totals remain `REVIEW`. This does not establish general Holoo accuracy or suitability across layouts.
2. `IssuanceService.submit` was called zero times for that sample; no Digital Invoice was issued. The low-confidence path is an adapter-local `REVIEW_REQUIRED` hold, not a persistent Frozen `REVIEW` state or P5.2 ReviewQueue record.
3. Otsu/adaptive cell preprocessing improved some quantity OCR but did not recover any monetary cell on the one image. The manual scoring transcription is unconfirmed by the invoice owner; do not use it to auto-correct values.
4. Synthetic English and Persian smokes reached `ISSUED` through the existing pipeline, but this is Synthetic evidence only. Threshold 60 is a test setting, not a production recommendation; confidence is not calibrated.
5. The flat text parser handles tested English/Persian labels. The dynamic projection detector recovered the four-column RTL tables in three supplied images (4, 5, and 13 rows); it has not been validated on other layouts. Projection is primary for crops, with TSV geometry fallback. Ambiguous values remain REVIEW. Jalali-to-Gregorian calendar conversion is not implemented.
6. Native Checkout is future architecture only under the recorded Q1–Q4 choices; it is not the current MVP priority and no Native Checkout code was added.
7. WP-11.2 (Holoo database adapter/enrichment) remains separate and deferred pending its own decisions/evidence.

## 9. Repository and EOD Branch Status

All task-scoped image-extraction source, tests, Synthetic regression evidence, real-image spatial/preprocessing/Glyph reports, and handoff updates stay on `arena/9dc17500-kandoo-digital-invoice`. WP-05 was pushed as `fbfe7c0`; remote upload commit `ccb9e99` added the supplied `5.png` and `13.png` images before WP-09 work. No change is to be merged to `main`. The unrelated untracked spooler adapter/runner is intentionally left out of this image-extraction change. Do not force-push or overwrite remote work if a future non-fast-forward condition occurs; report that blocker instead.

## 10. Handoff Protocol

Every agent joining this project must:

1. Read this file completely.
2. Inspect current Git HEAD and working tree.
3. Read authoritative registers/specs.
4. Read `KANDOO_AGENT_COORDINATION.md`.
5. Identify active WP ownership before editing anything.
6. Work only inside its assigned ownership boundary.
7. Run required tests/regression/smoke.
8. Commit.
9. Update this handoff and coordination state.
10. Report exact commit, tests, blockers and next executable work.

Never infer missing technical contracts from this handoff when an authoritative spec/register is available.
