# KANDOO DIGITAL INVOICE — AGENT COORDINATION

## Purpose

Operational coordination between Agent 1 and Agent 2.

## Ownership

| Area | Owner | Status |
|---|---|---|
| Active P12 execution stream | Agent 1 | ACTIVE |
| P12.3 D-07/D-08/DEF2 ratification | Product Owner / G4 | DECISION REQUIRED |
| WP-11.2 Adapter | NONE | BLOCKED until sufficient contract/PO decisions |
| Independent new WPs | Agent 2 | CLAIM ONLY AFTER RECON |
| Repository bootstrap / exact source transfer | Technical Manager / Coordinator | BLOCKED BY CURRENT CONNECTOR CAPABILITY |

## Rules

1. One WP = one owner.
2. Do not edit another agent's active WP/files.
3. Reviews do not transfer ownership.
4. Use branches for agent work.
5. Frozen files require explicit evidence before modification.
6. Update this file and AGENT_HANDOFF.md when ownership or project state changes.
7. Missions should cover multiple executable WPs where possible.
8. Stop only at genuine decision/evidence/contract/architecture blockers.
9. Never claim source integration when the repository does not contain the resulting artifact.

## Current State

The repository contains the collaboration/handoff files.

Verified current implementation package:
- kandoo-current-implementation10.zip
- ZIP SHA-256: b8cda0290d5811ffd511b7e96b147c917cc2458a9f8faee40c60e46d388bc753
- 281 project files + embedded manifest
- 281/281 manifest hashes verified

The current GitHub connector has repository write permissions but no bulk local-directory upload/Git-push operation. The implementation tree is therefore not yet claimed as integrated.

Next executable action: transfer the exact 281 files into main, verify against the package manifest, then record the resulting HEAD here and in AGENT_HANDOFF.md.
