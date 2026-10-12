# KANDOO DIGITAL INVOICE — AGENT COORDINATION

## Purpose

Operational coordination between Agent 1 and Agent 2.

## Ownership

| Area | Owner | Status |
|---|---|---|
| WP-1.2 (S1 Hardening) artifact on `main` | Agent 1 (implemented) | INTEGRATED at `80d7c73` — awaiting formal PO acceptance (4/4 AC PASS per REG-AR) |
| WP-1.3 (Retention & Recovery — Completion) | UNASSIGNED | Mechanic scope UNBLOCKED (per DEF4 mechanics can proceed with parametric placeholders); policy values remain BLOCKED (DEF4). Next critical-path WP. Requires explicit TM/PO mission dispatch before any agent claims it. |
| P2–P10 WP artifacts on `main` | Agent 1 (implemented, per register history) | INTEGRATED at `80d7c73` — awaiting formal PO acceptance |
| WP-11.1 Holoo Spike | Agent 1 | INTEGRATED at `80d7c73` — awaiting formal PO acceptance |
| WP-12.1 / WP-12.2 Corpus/Calibration | Agent 1 | INTEGRATED at `80d7c73` — awaiting formal PO acceptance |
| P12.3 D-07/D-08/DEF2 ratification | Product Owner / G4 | DECISION REQUIRED |
| WP-11.2 Adapter | NONE | BLOCKED — source mapping/authority/sync/conflict/write-back decisions required (DEF6); Decision Package exists |
| WP-10.2 Delivery | NONE | BLOCKED — DEF5 (presentation/channel decisions) |
| WP-8.2 Candidate Generation | NONE | BLOCKED — PO policy decision required |
| Repository bootstrap / source transfer | COMPLETE | INTEGRATED at `80d7c73` on 2026-10-08 (283 files present: 248 Python, 35 Markdown) |
| Independent new WPs | Agent 2 | CLAIM ONLY AFTER RECON + mission dispatch; no architecture expansion |

## Rules

1. One WP = one owner.
2. Do not edit another agent's active WP/files concurrently.
3. Reviews do not transfer ownership.
4. Use branches for agent work; never commit directly to `main` except integration commits approved by TM.
5. Frozen files require explicit evidence before modification.
6. Update this file and `AGENT_HANDOFF.md` when ownership or project state changes.
7. Missions should cover multiple executable WPs where possible.
8. Stop only at genuine decision/evidence/contract/architecture blockers.
9. Never claim source integration when the repository does not contain the resulting artifact.
10. Agent 1 reports are NOT automatically truth — Agent 2 must verify claims against GitHub `main` before any integration commit.

## Current State (after Agent 2 Source-of-Truth Recon, 2026-10-08)

GitHub HEAD: `80d7c73fea9c00a1176736b357325d431f1a7abe` — `merge: integrate remote project governance history`.

The implementation tree IS fully integrated (283 files):
- All WP-1.1 through WP-12.2 deliverables listed in the registers are present on disk.
- WP-1.2 artifacts verified present: `specs/WP-1.2-s1-hardening-contract.md`, `specs/WP-1.2-hardening-report.md`, `src/capture/tests/test_s1_hardening.py`, `src/run_smoke_s1_hardening.py`.
- WP-1.3: NO artifacts (spec/test/code) exist on `main`; WP-1.3 status in REG-WPR is correctly `DEFINED — ... policy values BLOCKED per DEF4`. Any Agent 1 claim of WP-1.3 completion is local-only and not yet integrated.

Next executable work (ordered by critical path):
1. **WP-1.3 Retention & Recovery (Completion) — Mechanics portion**: parametric TTL/purge hooks (no hardcoded policy values per DEF4), extended crash/orphan recovery matrix (beyond WP-1.1's W2–W4 minimum), status/reporting surface; explicit "policy values pending DEF4" labeling in code and registers. Requires:
   - Mission dispatch from TM/PO;
   - Decompose (contract spec) before implementation;
   - Additive-only against frozen WP-1.1/WP-1.2 (no production behavior changes to frozen files unless hardening evidence requires it, recorded via D-09 path).
2. Downstream deferred WPs (11.2/10.2/8.2/12.3) remain PO-decision-blocked.

Test-environment note: `pytest` is not installed in this sandbox, so Agent 2 did not independently re-run suites; pass/fail figures are carried from authoritative register records and require QA re-verification on a mission with the proper environment.
