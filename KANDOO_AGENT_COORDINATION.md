# KANDOO DIGITAL INVOICE — AGENT COORDINATION

## Purpose

Operational coordination between Agent 1 and Agent 2.
This file prevents overlapping ownership and keeps the two-agent workflow deterministic.

## Ownership

| Area | Owner | Status |
|---|---|---|
| Active P12 execution stream | Agent 1 | ACTIVE |
| P12.3 D-07/D-08/DEF2 ratification | Product Owner / G4 | DECISION REQUIRED |
| WP-11.2 Adapter | NONE | BLOCKED until sufficient contract/PO decisions |
| Independent new WPs | Agent 2 | CLAIM ONLY AFTER RECON |

## Rules

1. One WP = one owner.
2. Do not edit another agent's active WP/files.
3. Reviews may be performed independently, but review does not transfer ownership.
4. Use branches for agent work; do not push competing changes directly over another agent's branch.
5. Rebase/merge only after checking the latest integration state.
6. Frozen files require explicit evidence before modification.
7. Update this file and AGENT_HANDOFF.md when ownership or project state changes.
8. A mission should cover multiple executable WPs where possible.
9. Stop only at genuine decision/evidence/contract/architecture blockers.

## Current State

Repository bootstrap is in progress.
The repository is intentionally empty of project implementation until the actual working tree is transferred.
