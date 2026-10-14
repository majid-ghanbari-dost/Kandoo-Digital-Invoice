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

Verified for this EOD update on 2026-10-15:

- The checkout is on the Arena-fixed branch `arena/9dc17500-kandoo-digital-invoice`; this EOD work started from `1b79e630a8f476ed13d2d9fa7b6fb1c3de391cd0` and was replayed onto the existing remote branch tip `ade8af5f0c80d5bfb9b58e3d65dd9f231ba18a02` to preserve its commits. No other branch was used.
- Native Checkout PO decisions are recorded in `specs/native-checkout-contract-proposal.md`: Q1=Option 1, Q2=Option 2, Q3=Option 1, Q4=Option 1. Per PO direction, this is future architecture, not current MVP priority; no Native Checkout code was added.
- `WP-HOLOO-IMAGE-EXTRACTION-01` has an experimental `src/image_extraction_adapter/` using Tesseract, with a labeled synthetic English invoice fixture and an existing-issuance-service smoke runner. This is an external printed-invoice/OCR path, not Native Checkout and not the WP-11.2 Holoo database adapter.
- Actual synthetic E2E evidence is saved in `deliveries/image-extraction-ocr/`: Tesseract 5.5.1 (`eng`) read the fixture with 47 word scores (minimum 87.00, mean 95.21); all nine expected extracted values matched; the pipeline completed and a Digital Invoice reached `ISSUED`, verified `true`, with a 24-link trace. No genuine Holoo raster was available, so this is not evidence of Holoo accuracy.
- A second run at confidence threshold 90 returned adapter-local `REVIEW_REQUIRED`; issuance was not called and no Digital Invoice was created. This is not a persisted P5.2 ReviewQueue record: Frozen contracts do not carry OCR confidence.
- Persian/RTL OCR and Persian invoice parsing are not implemented. WP-11.2 (Holoo database adapter/enrichment) remains a separate deferred scope under its decision package.
- Frozen contracts D-01–D-09 were not changed.

## EOD Status [2026-10-15]

- Native Checkout Q1–Q4 decisions were recorded in `specs/native-checkout-contract-proposal.md`; they are approved for future architecture, not current MVP priority.
- Today `src/image_extraction_adapter/` was built with Tesseract OCR and exercised end-to-end on a synthetic English invoice; the existing pipeline produced an `ISSUED` Digital Invoice. The fixture is synthetic and does not establish Holoo accuracy.
- Persian/RTL is not currently supported.
- **Priority for the next agent:** extend Tesseract configuration and parsing for Persian, add a clearly labeled synthetic Persian fixture, then test against a real Holoo invoice when a sanitized, authorized sample is supplied. Do not substitute Native Checkout work for this external-image path.

## 7. Current Agent Ownership

- **Next implementation agent:** continue `WP-HOLOO-IMAGE-EXTRACTION-01`, starting with Persian OCR/parser support and a synthetic Persian fixture; do not substitute Native Checkout work for this external-image task.
- **Product Owner:** Native Checkout Q1–Q4 decisions are recorded; any later change to those decisions or MVP priority remains a PO decision.
- **WP-11.2 Holoo DB adapter:** remains a separate deferred scope; the image-extraction adapter does not resolve its source mapping/authority/synchronization decisions.
- Preserve unrelated work already present in the working tree; do not absorb other agents' uncommitted files into this EOD commit.

## 8. Current Real Boundaries

1. `WP-HOLOO-IMAGE-EXTRACTION-01` has only a synthetic English proof. Persian OCR/layout support and a genuine, authorized Holoo invoice sample are still required before claiming external-source suitability.
2. The low-confidence path is an adapter-local `REVIEW_REQUIRED` hold. The Frozen contracts do not persist OCR confidence or provide a proven P5.2 review-queue mapping; do not describe this local hold as a persistent Frozen `REVIEW` state.
3. The synthetic smoke reached `ISSUED` through the existing pipeline; this does not prove Holoo accuracy or Persian readiness.
4. Native Checkout is future architecture only under the recorded Q1–Q4 choices; it is not the current MVP priority and no Native Checkout code was added.
5. WP-11.2 (Holoo database adapter/enrichment) remains separate and deferred pending its own decisions/evidence.

## 9. Repository and EOD Branch Status

The checkout contains the project source tree. The EOD image-extraction code, synthetic OCR evidence, Native Checkout decision note and handoff updates are scoped to the fixed Arena branch `arena/9dc17500-kandoo-digital-invoice`; no change is to be merged to `main`.

The image-extraction/EOD change is based on the existing remote tip `ade8af5f0c80d5bfb9b58e3d65dd9f231ba18a02`; its prior commits were preserved. The final commit SHA and push result are reported from Git in the EOD response. Do not force-push or overwrite remote work if a future divergence occurs. Unrelated pre-existing spooler artifacts remain uncommitted and outside this image-extraction commit.

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
