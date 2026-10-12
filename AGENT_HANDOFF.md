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

## 6. Current Verified Project State (as of Agent 2 Source-of-Truth Recon, 2026-10-08)

GitHub HEAD: `80d7c73fea9c00a1176736b357325d431f1a7abe` — `merge: integrate remote project governance history`.
Repository working tree: 283 files (248 Python, 35 Markdown). The full implementation tree (P1–P12.2) IS present on `main`; bootstrap transfer is complete.

P1 Capture Foundation:
- WP-1.1: CLOSED — IMPLEMENTED (2026-10-01), 8/8 AC PASS.
- WP-1.2: IMPLEMENTED (2026-10-09 per register records), 4/4 AC PASS (REG-AR), awaiting formal PO acceptance. All 4 deliverables present:
  - `specs/WP-1.2-s1-hardening-contract.md`
  - `specs/WP-1.2-hardening-report.md`
  - `src/capture/tests/test_s1_hardening.py` (36 edge tests)
  - `src/run_smoke_s1_hardening.py` (20th smoke, 8 cold-start steps)
- WP-1.3: DEFINED — policy values BLOCKED per DEF4 (retention/privacy TTL/purge values). Mechanic scope (parametric TTL hooks, full crash/orphan recovery matrix, status reporting) is technically unblocked and does not require PO policy values. No WP-1.3 artifacts (spec, tests, code) exist yet; WP-1.3 has NOT been executed.

P2–P12.2: all work packages up through WP-12.2 are marked IMPLEMENTED per the authoritative registers, awaiting formal PO acceptance.
- WP-12.3: DEFERRED — PO/G4 ratification of D-07/D-08/DEF2 required.
- WP-11.2: DEFERRED — source mapping/authority/sync/conflict/write-back decisions required (DEF6); Decision Package exists at `specs/WP-11.2-decision-package.md`.
- WP-10.2: DEFERRED — DEF5 (presentation/delivery channel).
- WP-8.2: PLANNED — fuzzy policy/candidate-approval matrix requires PO decision.

Reference transfer package (historical — bootstrap already integrated at `80d7c73`):
- File: `kandoo-current-implementation10.zip`
- ZIP SHA-256: `b8cda0290d5811ffd511b7e96b147c917cc2458a9f8faee40c60e46d388bc753`
- Manifest: 281 project files; 281/281 hashes matched.
- Note: The embedded manifest file itself is not present in the repository; project file count (248 .py + 33 .md project + handoff/README/register/spec delta) matches the ZIP payload. The two extra .md files in HEAD (`AGENT_HANDOFF.md`, `KANDOO_AGENT_COORDINATION.md`, `README.md`, plus post-bootstrap register/spec updates from WP-1.2 mission) account for the markdown delta from 33 to 35.

Reported verification figures (carried forward from Agent 1 reports, not independently re-run by Agent 2 in this recon):
- WP-1.2: 36/36 ×3 independent repeats, SMOKE 20/20, full regression 1475/1476 (1 pre-existing date-sensitive flake).
- WP-12.1: 90/90 ×3; WP-12.2: 33/33 ×3; Smoke 20/20; Regression 1475/1476.

## 7. Current Agent Ownership

Agent 1 (implementation):
- Previous active mission executed WP-1.2 hardening (registered as IMPLEMENTED, awaiting PO acceptance).
- Subsequent WP-1.3 execution claim: NOT YET INTEGRATED — Agent 2 Source-of-Truth recon finds no WP-1.3 spec/tests/code in `main`; any Agent 1 report of WP-1.3 completion would be local-only and not represented on GitHub.
- Must coordinate with Agent 2 / TM before claiming further integration.

Agent 2 (independent reviewer / GitHub operator):
- Completed Source-of-Truth recon on `main` at commit `80d7c73` (2026-10-08).
- Has no active WP claim beyond governance/handoff correction in this turn.
- Must not modify production code; must not execute WP-1.3 without explicit mission dispatch.

## 8. Current Real Boundaries (after recon)

1. WP-1.3 — Retention policy VALUES remain BLOCKED per DEF4 (PO decision required on TTL/purge/privacy values).
2. WP-1.3 — Mechanics (parametric retention hooks, crash/orphan matrix, status reporting) are technically unblocked and are the next executable WP on the critical path; require decompose + mission dispatch before execution.
3. WP-12.3: PO/G4 ratification of D-07, D-08 and DEF2 (thresholds).
4. WP-11.2: required source mapping/authority/sync/conflict/write-back decisions before Adapter implementation (DEF6).
5. WP-10.2: delivery/presentation decisions (DEF5).
6. WP-8.2: fuzzy matching / candidate-approval policy (PO).

Repository bootstrap is COMPLETE at `80d7c73`; no file-transfer action is outstanding.

### WP-1.3 Integration Mission (Agent 2, 2026-10-10) — BLOCKED: artifact not delivered

- Mission dispatch: TM/PO directed Agent 2 to receive ZIP+MANIFEST from Agent 1, verify SHA-256, validate additive 10 new + 4 governance files against baseline 281, confirm DEF4 compliance, then integrate into `main`.
- Actual state: the WP-1.3 delivery artifact (ZIP + embedded MANIFEST) is NOT present in the Agent 2 sandbox. Exhaustive search of `/home/user`, `/tmp`, `/var/tmp`, `/root`, and the repository working tree found zero ZIP files, zero MANIFEST files, and zero files whose name/path matches WP-1.3/retention outside of what already exists in `main` at `80d7c73`. No open PRs, branches, releases, or issues on GitHub carry a WP-1.3 payload either.
- Handoff channel: there is no filesystem share, connector, or Agent1→Agent2 messaging surface in this environment other than what the user/TM relays through the mission text itself. The mission text does not include a download URL or SHA-256; it only instructs me to coordinate with Agent 1 to obtain the package.
- Conclusion: per the non-negotiable rule («هیچ‌کدام از این موارد را صرفاً بر اساس گزارش، تکمیل‌شده تلقی نکنید») and my own governance rule (Agent 1 reports are not automatically truth until verified against GitHub main), I CANNOT:
  - compute SHA-256,
  - diff the 281 baseline files against the claimed 10 new + 4 governance,
  - validate DEF4 / Frozen-architecture compliance on real code,
  - run or audit the dedicated tests/smoke,
  - or truthfully claim WP-1.3 is integrated.
- Therefore: NO INTEGRATION COMMIT to `main` in this turn. Branch `arena/7bee5f10-kandoo-digital-invoice` remains one governance commit ahead of `main` (`1fcd25a`) and only records this BLOCK note.
- Required to unblock: Agent 1 must deliver the WP-1.3 ZIP + MANIFEST (with stated SHA-256) into a location Agent 2 can read, OR publish a PR/branch on GitHub that Agent 2 can `fetch` and verify. Once delivered, Agent 2 will: validate hashes; diff baseline files for byte-identity; inspect every new/changed file against DEF4 (no hardcoded TTL/purge/privacy values; parametric placeholders + "policy values pending DEF4" labeling; additive-only against frozen WP-1.1/WP-1.2); confirm 10 new + 4 governance files align with the report; execute the dedicated WP-1.3 tests (after installing pytest); update registers/handoff/coordination/README; commit with an explicit message; PR to `main`; re-verify HEAD.
- I did not fabricate, infer, or synthesize any WP-1.3 artifacts on my own, and I did not open the WP-1.2 / Frozen architecture — both are forbidden by mission constraints and by project Frozen rules.

## 9. Repository Bootstrap Status

BOOTSTRAP COMPLETE. The full project implementation tree is present in `main` at commit `80d7c73` (283 working-tree files: 248 Python, 35 Markdown). The historical note about a pending 281-file ZIP transfer was stale and has been corrected.

Note on pytest environment: Agent 2 did not re-run test suites in this recon because `pytest` is not installed in the sandbox image; test figures are carried forward from the authoritative register records and Agent 1 reports. Independent verification re-runs belong to a QA-verification mission, not this Source-of-Truth control pass.

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
