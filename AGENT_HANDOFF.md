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

## 6. Historical P12/Bootstrap Snapshot (pre-O15; superseded by Section 11)

> The statements below preserve the handoff inherited at repository bootstrap. They are not the current execution state of the active Arena O15 branch; Section 11 is authoritative for current state.

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

## 7. Historical Agent Ownership Snapshot (pre-O15; superseded by Section 11)

Agent 1:
- Owns the active P12 execution stream until it reaches its genuine PO/evidence boundary.
- Must not assume this new repository already contains the working tree.

Agent 2:
- Owns independent work only after inspecting this repository and coordination state.
- Must not modify Agent 1's active WP/files concurrently.

## 8. Historical Real Boundaries (pre-O15; superseded by Section 11)

1. P12.3: PO/G4 ratification of D-07, D-08 and DEF2.
2. WP-11.2: required source mapping/authority/sync/conflict/write-back decisions and sufficient contract before Adapter implementation.
3. Repository bootstrap: actual 281-file project tree must still be transferred from the verified local ZIP into `main`.

## 9. Historical Repository Bootstrap Status (pre-O15; superseded by Section 11)

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

## 11. Current O15 Execution State — updated 2026-10-12

> This section is authoritative for the active Arena branch. Sections 6–9 preserve an older pre-O15 bootstrap snapshot and are historical only.

- Repository: `majid-ghanbari-dost/Kandoo-Digital-Invoice`.
- Active branch: `arena/d0587e71-kandoo-digital-invoice`; never switch branches, merge, or push to `main` for this order.
- E-62 source anchor before the E-64 handoff/report changes: `5a126ae9fb82bef77662ed6dd380638c90612ceb`, tagged `o15-E-62`.
- E-60: **COMPLETE**. Final accepted tag `o15-E-60-fix-1`; SHA `68be0e7c08c264a064bae598b5a3917fe6bf4dd9`. The earlier `o15-E-60` tag remains on the initial commit and is not the accepted final version.
- E-61: **COMPLETE**. Tag `o15-E-61`; SHA `595d84120a33fd720b9871dc2a2b3b7715b60570`. C-84's value/confidence/crop-region and frozen result contract remain unchanged. Without independent expected-value labels, accuracy is `NOT_SCORED` and `extracted_but_wrong` is `null`.
- E-62: **COMPLETE**. Tag `o15-E-62`; SHA `5a126ae9fb82bef77662ed6dd380638c90612ceb`. Local label templates validate against the O15 schema, default to pending values, and do not update Glyph or enable online learning.
- E-63: **DELIVERED — task and evidence are documented; this is not final acceptance.** Extractor result is `REVIEW`, not `AUTO` and not an accuracy PASS. The owner retains final acceptance. The report separates technical health, extraction quality, and criterion compliance with evidence. Synthetic input and raw outputs stayed in the sandbox; the remote transfer branch was deleted after validation. No capture payload, file hash/size, OCR value, or raw output is in Git.
- E-63 initial run: source tag `o15-E-60-fix-1`, SHA `68be0e7c08c264a064bae598b5a3917fe6bf4dd9`, Linux/Pillow `11.1.0`, returned `BLOCKED / REJECT` (exit `20`), one blocked page, zero numeric candidates. `src/image_extraction_adapter/preprocessing.py:642` called missing `Image.get_flattened_data()`; the default E-05 bank was also unavailable because its real fixture JSONs are absent. This first result is retained, not overwritten.
- E-63 fix-forward: tag `o15-E-63-fix-1`, commit/SHA `89f78b2099d0f15d01bbf84bd68cc1a997c754c2`. Diff: only replace `line_mask.get_flattened_data()` with Pillow-11.1-compatible `line_mask.getdata()`; Pillow pin, extraction semantics, banks, schemas and workflow are unchanged. `test_line_mask_flattened_pixel_count_uses_pillow_11_1_data_api` asserts the expected 30-pixel removal, cleaned output, and unchanged input on a synthetic grayscale image.
- E-63 verification: full local suite `1702 passed`; `scripts/verify_o15_e60.py` PASS. Branch CI [44080880091](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44080880091) and tag CI [44081030928](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44081030928) succeeded.
- E-63 artifact status: E-60 run `44030430963`, artifact ID `14305290850`, declared digest `sha256:60f9baee9b8910d2817878d9777627b60ae3dde275d74cc8263eb53c9d5be083`. One authenticated API retry returned EOF and zero bytes; **actual artifact hash was not verified**. Per executive instruction, E-63 proceeded from Linux source at the approved fix-forward tag/SHA.
- E-63 final aggregate: two post-fix runs from the exact tag/SHA produced identical aggregate metrics; each had one invoice/one page, exit `10`, result `REVIEW`, zero blocked pages/errors, and schema-valid result/demo JSON. There were nine numeric candidates and all nine `REVIEW`; confidence bins `[0,25)=0`, `[25,50)=0`, `[50,75)=0`, `[75,100]=9`, `UNSCORED=0`; E-06 `REVIEW` (`PARTIAL_MATCH`, `NEW_LAYOUT`). Glyph templates loaded (17 row/10 payable); glyph drift `REVIEW`. E-05 bank `UNAVAILABLE`/zero templates. Accuracy `NOT_SCORED`, `extracted_but_wrong: null`.
- E-63 disposition per executive: **DELIVERED** means the task is documented, not accepted; final acceptance remains with the owner. Exactly these items remain **NOT-VERIFIED**: Holoo origin, artifact, and diversity. Input structure/count/integrity/reporting evidence and the `NOT_SCORED` limitation remain as in the report; no result number was added or reinterpreted.
- Transfer cleanup: `git push origin --delete o15-e63-transfer` succeeded; the removed branch's last SHA was `d042001f8827fe591cfa428e859c91ff1846fa45`. The branch was not recreated. Input and outputs remain sandbox-only.
- E-64: handoff, coordination, and status report are recorded at tag `o15-E-64`, SHA `d01d82d30799089a1b64422900cfb01897dad580`; branch CI [44035893690](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035893690) and tag CI [44035895508](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035895508) succeeded.
- E-65 (STRETCH): **NOT STARTED.** E-63 is dispositioned `DELIVERED` (not final acceptance). The authoritative repository documents state only the label “Holoo v1.2 stretch” and provide no executable scope/acceptance criteria. Under the manager's two-step gate, do not implement or tag until the owner supplies complete written criteria.

Verification at E-62: focused E-60/E-61/E-62 tests `18 passed`; `scripts/verify_o15_e60.py` passed; full local suite `1701 passed in 167.58s`. Both E-62 CI workflows succeeded: branch run [44035249445](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035249445) and tag run [44035251303](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035251303). E-63 fix-forward CI and exact details are recorded above and in `docs/o15-final-report.md`. All recent workflow notices were non-blocking Node.js 20 deprecations.

**Next executable action:** Quote the existing E-65 label and gating statements from `AGENT_HANDOFF.md`, `KANDOO_AGENT_COORDINATION.md`, and the O15 order documents. They do not provide executable scope/acceptance criteria. Send the owner a request/template for the missing scope; do not implement or tag. E-63 is already dispositioned `DELIVERED` (not final acceptance). Preserve E-63 records and keep capture files/raw outputs outside Git.
