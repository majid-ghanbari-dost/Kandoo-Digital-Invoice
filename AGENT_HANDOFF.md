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

Verified for this update on 2026-10-15:

- Work is on the Arena-fixed branch `arena/9dc17500-kandoo-digital-invoice`. This continuation started from `3fa1a7f0644342f810f1ae50f064f6b55c9b1869`, which added the user-supplied image; no other branch was used and `main` was not changed.
- Native Checkout PO decisions remain recorded in `specs/native-checkout-contract-proposal.md`: Q1=Option 1, Q2=Option 2, Q3=Option 1, Q4=Option 1. Per PO direction this is future architecture, not current MVP priority; no Native Checkout code was added.
- `WP-HOLOO-IMAGE-EXTRACTION-02 — Persian OCR Support` is implemented in the experimental `src/image_extraction_adapter/` on top of the existing Tesseract/image-to-issuance path. `fas+eng` is configured, Persian/Arabic digits and separators and bidi controls are normalized, and the parser supports the tested Persian labels and line blocks. The original image extraction is preflighted against expected synthetic values before the existing `IssuanceService` is called.
- The current spatial-backend regression on the explicitly Synthetic Persian PNG used Tesseract 5.5.1 with `fas+eng`: 47 word scores, mean 91.47784295744681, minimum 65.31218. Declared values matched and the smoke reached `ISSUED`; its complete output is `deliveries/image-extraction-ocr/synthetic-spatial-regression-fa.log`. The fixture SHA-256 remains `df0e79c5acef87a6f2bcd3c9d36c6afadfb612a7210afadc0ea717c08856d782`. Earlier pre-spatial output is retained in `synthetic-persian-ocr-e2e.log`.
- The existing pipeline completed for the synthetic fixture: 4 configured validations `VALID`, domain `VALID/CLEAR`, canonicalization `ACCEPTED`, 2 canonical lines, and lifecycle `DRAFT → EXTRACTED → VALIDATED → ISSUED`; final Digital Invoice was verified with a 24-link trace. Evidence and IDs are in the retained smoke log and `deliveries/image-extraction-ocr/synthetic-digital-invoice-evidence.md`.
- A confidence threshold of 70 returned adapter-local `REVIEW_REQUIRED` at measured minimum 65; issuance was not called and no Digital Invoice was created. This is not a persisted P5.2 ReviewQueue record: Frozen contracts do not carry OCR confidence.
- Persian `fas` and English `eng` traineddata were successfully installed and exercised from `/tmp/kandoo-ocr-runtime`; model provenance and SHA-256 checksums are in the evidence document. Optional OCR/test packages and model binaries are not committed.
- `HOLOO-EXTRACTION-CONTINUATION-01` adds level-5 TSV word boxes and a right-to-left spatial fallback in `src/image_extraction_adapter/`. On the user-supplied cleaned image `deliveries/image-extraction-ocr/holo_row_detection.png`, it found four ordered table rows and assigned description/quantity/amount columns without visible row transposition. It preserved OCR strings and marked ambiguous or missing values `REVIEW`; report: `deliveries/image-extraction-ocr/real-holoo-spatial-evidence.md`.
- A `submit_image()` run used a counting wrapper around the real `IssuanceService`: `IssuanceService.submit` calls = 0, no Digital Invoice was issued, and lifecycle did not start. This remains an adapter-local hold, not a persisted P5.2 review record.
- The single image did not produce trustworthy numeric line amounts or a payable amount. Its date, payable, net total, row quantities, most descriptions, all unit prices, and all line totals remain `REVIEW`. This is a narrow sample result, not broad Holoo accuracy evidence.
- Spatial OCR uses `tesserocr.GetTSVText(0)`, which supplies the equivalent level-5 text/confidence/left/top/width/height data. `pytesseract` and the native Tesseract CLI were unavailable in this runtime; neither is claimed as used. Tesseract 5.5.1 and `fas+eng` traineddata remain under `/tmp/kandoo-ocr-runtime` and are not committed.
- Focused image-adapter tests passed (12); the full repository suite passed (1,706). Current English and Persian smoke regressions passed on explicitly synthetic fixtures; logs are `deliveries/image-extraction-ocr/synthetic-spatial-regression-en.log` and `synthetic-spatial-regression-fa.log`. Synthetic issuance is not Holoo validation. Frozen contracts D-01–D-09 were not changed.

## EOD Status [2026-10-15]

- Native Checkout Q1–Q4 decisions remain approved for future architecture, not current MVP priority.
- `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian implementation and verification remain complete. Its results stay explicitly Synthetic and are not treated as Holoo evidence.
- `HOLOO-EXTRACTION-CONTINUATION-01` implemented the spatial fallback and ran the supplied cleaned image. Four row positions were recovered, but critical fields remain `REVIEW`; `IssuanceService.submit` was not reached and no invoice was issued. See `deliveries/image-extraction-ocr/real-holoo-spatial-evidence.md`.
- Next executable work: obtain confirmed ground truth for reviewed fields and additional authorized examples before making accuracy claims or broadening the layout parser. Keep uncertain values fail-closed; do not use Synthetic fixtures as substitutes. Do not substitute Native Checkout or WP-11.2 database-adapter work for this external-image path.

## 7. Current Agent Ownership

- **Current implementation:** `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian support remains complete. `HOLOO-EXTRACTION-CONTINUATION-01` implements spatial OCR and is tested against one user-supplied cleaned image; that image returns adapter-local review and does not pass issuance.
- **Product Owner:** Native Checkout Q1–Q4 decisions are recorded; any later change to those decisions or MVP priority remains a PO decision.
- **WP-11.2 Holoo DB adapter:** remains a separate deferred scope; the image-extraction adapter does not resolve its source mapping/authority/synchronization decisions.
- Preserve unrelated work already present in the working tree; do not absorb the untracked spooler adapter or runner into this image-extraction change.

## 8. Current Real Boundaries

1. One user-supplied cleaned invoice image was processed. The spatial parser detected four numbered rows and their column positions, but the result is partial; most line values and key totals remain `REVIEW`. This does not establish general Holoo accuracy or suitability across layouts.
2. `IssuanceService.submit` was called zero times for that sample; no Digital Invoice was issued. The low-confidence path is an adapter-local `REVIEW_REQUIRED` hold, not a persistent Frozen `REVIEW` state or P5.2 ReviewQueue record.
3. Synthetic English and Persian smokes reached `ISSUED` through the existing pipeline, but this is Synthetic evidence only. Threshold 60 is a test setting, not a production recommendation; confidence is not calibrated.
4. The flat text parser handles tested English/Persian labels; the spatial fallback currently targets numbered rows and vertical-rule columns in the observed image. Both preserve/fail closed on incomplete or ambiguous values. Jalali-to-Gregorian calendar conversion is not implemented.
5. Native Checkout is future architecture only under the recorded Q1–Q4 choices; it is not the current MVP priority and no Native Checkout code was added.
6. WP-11.2 (Holoo database adapter/enrichment) remains separate and deferred pending its own decisions/evidence.

## 9. Repository and EOD Branch Status

All task-scoped image-extraction source, tests, Synthetic regression evidence, real-image spatial report, and handoff updates stay on `arena/9dc17500-kandoo-digital-invoice`; this continuation started from `3fa1a7f0644342f810f1ae50f064f6b55c9b1869`. No change is to be merged to `main`. The unrelated untracked spooler adapter/runner is intentionally left out of the image-extraction change. Do not force-push or overwrite remote work if a future non-fast-forward condition occurs; report that blocker instead.

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
