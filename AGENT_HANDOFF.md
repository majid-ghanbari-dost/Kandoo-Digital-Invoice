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

P1–P10: completed/frozen.
WP-11.1: implemented, tested, packaged and accepted at implementation level.
WP-12.1: implemented and tested.
WP-12.2: implemented and tested.
WP-12.3: PO/G4 decision boundary; D-07/D-08/DEF2 require ratification.
WP-11.2: Adapter must NOT be implemented until its required decisions/contract are resolved; a Decision Package exists.

Latest reported P12 implementation source anchor: `d8dbc29`.
Latest reported final delivery/hygiene commits in the previous working project: `a73fde5`, `574444f`.
These commit IDs refer to the previous working project history and are not yet present in this newly-created repository.

Latest verified transfer package available for bootstrap:
- File: `kandoo-current-implementation10.zip`
- ZIP SHA-256: `b8cda0290d5811ffd511b7e96b147c917cc2458a9f8faee40c60e46d388bc753`
- Project files inside ZIP: 281
- Total ZIP entries: 282 (281 project files + embedded manifest)
- Manifest reports: 281 files
- Manifest verification: 281/281 file hashes matched; 0 missing; 0 extra; 0 size mismatches.
- Project content types verified: 248 Python, 33 Markdown, 1 text manifest.
- This package is the current authoritative transfer candidate and supersedes the older 277-file delivery package for bootstrap purposes.
- The package includes source anchor `54211b6` according to its embedded manifest.

Latest reported verification from the working project:
- WP-12.1 dedicated tests: 90/90, repeated independently ×3.
- WP-12.2 dedicated tests: 33/33, repeated independently ×3.
- Smoke: 19/19.
- Full regression: 1439/1440 passed, with one known pre-existing date-sensitive flake:
  `test_ir_provenance::test_no_raw_pipeline_values_are_stored`.
- No new regression failure was reported.

## 7. Current Agent Ownership

Agent 1:
- Owns the active P12 execution stream until it reaches its genuine PO/evidence boundary.
- Must not assume this new repository already contains the working tree.

Agent 2:
- Owns independent work only after inspecting this repository and coordination state.
- Must not modify Agent 1's active WP/files concurrently.

## 8. Current Real Boundaries

1. P12.3: PO/G4 ratification of D-07, D-08 and DEF2.
2. WP-11.2: required source mapping/authority/sync/conflict/write-back decisions and sufficient contract before Adapter implementation.
3. Repository bootstrap: actual 281-file project tree must still be transferred from the verified local ZIP into `main`.

## 9. Repository Bootstrap Status

The repository contains the collaboration/handoff files, but the actual 281-file implementation tree has not yet been transferred.

Verified transfer candidate:
`kandoo-current-implementation10.zip` with SHA-256 `b8cda0290d5811ffd511b7e96b147c917cc2458a9f8faee40c60e46d388bc753`.

The current GitHub connector has repository write permissions but no bulk local-directory upload/Git-push operation. Therefore the ZIP cannot be truthfully represented as integrated source until the 281 files are actually written to Git.

Next bootstrap action:
- transfer the exact 281 project files without reconstruction or modification;
- preserve the embedded manifest;
- verify repository file count/content against the transfer package;
- update this handoff with actual repository HEAD and verification results.

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
