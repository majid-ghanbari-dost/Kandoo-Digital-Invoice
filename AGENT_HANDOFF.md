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

- Work is on the Arena-fixed branch `arena/9dc17500-kandoo-digital-invoice`, starting from SHA `931d14111dace044681b3d902b791fa8539066c8`. No other branch was used and `main` was not changed.
- Native Checkout PO decisions remain recorded in `specs/native-checkout-contract-proposal.md`: Q1=Option 1, Q2=Option 2, Q3=Option 1, Q4=Option 1. Per PO direction this is future architecture, not current MVP priority; no Native Checkout code was added.
- `WP-HOLOO-IMAGE-EXTRACTION-02 — Persian OCR Support` is implemented in the experimental `src/image_extraction_adapter/` on top of the existing Tesseract/image-to-issuance path. `fas+eng` is configured, Persian/Arabic digits and separators and bidi controls are normalized, and the parser supports the tested Persian labels and line blocks. The original image extraction is preflighted against expected synthetic values before the existing `IssuanceService` is called.
- The explicitly synthetic Persian PNG was read by Tesseract 5.5.1 with `fas+eng`: 47 word scores, mean 91.04255319148936, minimum 65.0. All 13 expected values matched, including both requested Persian item names and the payable label. The raw OCR and full result are in `deliveries/image-extraction-ocr/synthetic-persian-ocr-e2e.log`; the fixture SHA-256 is `df0e79c5acef87a6f2bcd3c9d36c6afadfb612a7210afadc0ea717c08856d782`.
- The existing pipeline completed for the synthetic fixture: 4 configured validations `VALID`, domain `VALID/CLEAR`, canonicalization `ACCEPTED`, 2 canonical lines, and lifecycle `DRAFT → EXTRACTED → VALIDATED → ISSUED`; final Digital Invoice was verified with a 24-link trace. Evidence and IDs are in the retained smoke log and `deliveries/image-extraction-ocr/synthetic-digital-invoice-evidence.md`.
- A confidence threshold of 70 returned adapter-local `REVIEW_REQUIRED` at measured minimum 65; issuance was not called and no Digital Invoice was created. This is not a persisted P5.2 ReviewQueue record: Frozen contracts do not carry OCR confidence.
- Persian `fas` and English `eng` traineddata were successfully installed and exercised from `/tmp/kandoo-ocr-runtime`; model provenance and SHA-256 checksums are in the evidence document. Optional OCR/test packages and model binaries are not committed.
- Focused image-adapter tests passed (9); the full repository suite passed (1,703). The English synthetic smoke regression also completed and reached `ISSUED`; its run is retained in `deliveries/image-extraction-ocr/synthetic-english-regression.log`.
- No genuine, authorized Holoo invoice was available. These results establish synthetic Persian-path behavior only, not Holoo accuracy. Frozen contracts D-01–D-09 were not changed.

## EOD Status [2026-10-15]

- Native Checkout Q1–Q4 decisions remain approved for future architecture, not current MVP priority.
- `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian implementation and verification are complete. Persian OCR is configured using `fas+eng`; actual OCR text, expected/actual comparisons, confidence review, pipeline completion, and test results are retained under `deliveries/image-extraction-ocr/`.
- Real Holoo validation is **BLOCKED pending a sanitized, authorized Holoo invoice sample**. Do not infer Holoo layout/accuracy from the synthetic fixture.
- Next executable work, when a sample is supplied: run the existing parser/OCR flow against that authorized sample, record actual OCR and field-level mismatches, and preserve fail-closed behavior. Do not substitute Native Checkout or WP-11.2 database-adapter work for this external-image path.

## 7. Current Agent Ownership

- **Current implementation:** `WP-HOLOO-IMAGE-EXTRACTION-02` synthetic Persian support is complete and evidence-backed; further real-source validation awaits a sanitized, authorized sample.
- **Product Owner:** Native Checkout Q1–Q4 decisions are recorded; any later change to those decisions or MVP priority remains a PO decision.
- **WP-11.2 Holoo DB adapter:** remains a separate deferred scope; the image-extraction adapter does not resolve its source mapping/authority/synchronization decisions.
- Preserve unrelated work already present in the working tree; do not absorb the untracked spooler adapter or runner into this image-extraction change.

## 8. Current Real Boundaries

1. Synthetic Persian OCR is verified, but no genuine authorized Holoo invoice is available. Holoo-specific recognition/layout suitability remains unverified.
2. The low-confidence path is an adapter-local `REVIEW_REQUIRED` hold. The Frozen contracts do not persist OCR confidence or provide a proven P5.2 review-queue mapping; do not describe this local hold as a persistent Frozen `REVIEW` state.
3. The synthetic smoke reached `ISSUED` through the existing pipeline; this does not prove Holoo accuracy. The successful threshold 60 is a test setting, not a production recommendation; confidence is not calibrated.
4. The parser recognizes the tested English/Persian labels and line-block layouts, normalizes Persian/Arabic digits and bidi controls, and fails closed for incomplete/ambiguous fields. Jalali-to-Gregorian calendar conversion is not implemented.
5. Native Checkout is future architecture only under the recorded Q1–Q4 choices; it is not the current MVP priority and no Native Checkout code was added.
6. WP-11.2 (Holoo database adapter/enrichment) remains separate and deferred pending its own decisions/evidence.

## 9. Repository and EOD Branch Status

All task-scoped Persian image-extraction source, tests, synthetic fixture, evidence, and handoff updates stay on `arena/9dc17500-kandoo-digital-invoice`, whose work started at `931d14111dace044681b3d902b791fa8539066c8`. No change is to be merged to `main`. The unrelated untracked spooler adapter/runner is intentionally left out of the image-extraction change. Do not force-push or overwrite remote work if a future non-fast-forward condition occurs; report that blocker instead.

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
