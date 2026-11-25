# [AGENT-TASK PY-T3] Python lane — M-010/M-011 sprint chain (demo blockers only)

**Lane:** Python (`majid-ghanbari-dost/Kandoo-Digital-Invoice`) — **Posted by:** exec-manager (2026-11-25, Asia/Tehran)
**Source orders:** M-010 + M-011 (`docs/messages/` on `main` of the C# repo `majid-ghanbari-dost/Kandoo`). Manager answer: R-010 in `docs/messages/MANAGER-TO-PM.md` on `arena/order-15-status` of the C# repo.
**Reporting (GitHub only):** update the `## Status` line in THIS file + report comment on PR #16 and any new PR. One short line per green stage (branch, tag, run URL). Never merge/close — PM merges.

## Sprint ordering (M-010 — everything else PAUSED)
The samples HAVE landed — manager-verified on `main` @ `d453225480dd8333c1b832904c53334192137184` ("Add fictional print diagnostic samples"): `samples/real-layout-fictional/README.md` + `samples/real-layout-fictional/DiagnosticResults/` (Job_2, Job_3, Unassigned). BLOCKED-WAITING-FOR-SAMPLES is cleared; no polling needed.

## Stage 1 — E-73 capture robustness + capture-folder -> review item (T0–T+12h)
On the samples (incl. the three DiagnosticResults folders and the 0-byte class, e.g. `14050816_135747_803_00002.SPL`): capture robustness AND the capture-folder -> review-item path with "what I read" beside the picture. Tag `o17-E-73` on the green commit.

## Stage 2 — E-74 accuracy numbers (by ~T+30h)
Per-layout accuracy on the samples; EXTRACTED-but-wrong = 0. Ground truth per PY-T2 §1: invoice no. 34, date 1405.08.16, FOUR lines, payable 49,547,790 (raster-read; confirm against the original invoice-34 image); resolve the 503,639 line-sum vs payable difference (invoice-level discount vs read error) and report the outcome. Also run the two un-deferred local checks (numbers only) if not already reported. Tag `o17-E-74`.

## Stage 3 (pre-approved; NOT sprint scope)
E-70 onboarding from the first invoices with operator confirmation.

## Stage 4 (pre-approved)
E-72 vectors for C#/PHP review (round 3; the C# round-2 verdict stands INCOMPATIBLE — fix the wrapper / missing required root fields / unknown root fields first), then E-71 second and third layouts.

## MANAGER RULING (2026-11-25) — E-74 scoring source (answers the agent's blocking question)

**CHOSEN: Option 1 — "Confirm existing fictional raster".** No new uploads, no real customer data; PM-06/PM-17 untouched. Options 2 and 3 rejected (option 2 adds a needless upload delay; option 3 blocks on evidence the manager already holds).

1. **Scoring source = the certified fictional raster already in `samples/real-layout-fictional/`** (the invoice-34.png duplicate inside the approved capture samples). Nothing else is authorized as the scoring source.
2. **The Stage 2 labels ARE the operator-verified labels for that raster** — manager raster verification 2026-11-25: invoice no. 34, date 1405.08.16, FOUR lines, payable 49,547,790. This supersedes the older R-008 reading (five lines / 49,547,706). Use them as-is; E-74 does NOT wait for any new upload.
3. **Order of work (honest-verification protocol):** (a) independently re-read the raster FIRST and print your raw readings; (b) if they match the labels, score immediately — the EXTRACTED-but-wrong = 0 gate is unchanged; (c) if ANY reading differs (line count, date, payable), do NOT score that field — report the mismatch with crop citations as PARTIAL and score the uncontested fields anyway; NOT-RUN ≠ zero, per rules.
4. **The 503,639 line-sum vs payable gap: resolve FROM THE RASTER itself.** If an invoice-level discount row/field is visible in the raster, report "invoice-level discount" and cite the row; if nothing visible explains the gap, report "unexplained by the raster" with the crops. Do not guess and do not silently pick one.
5. Decision recorded in `docs/decisions-made.md` on the C# repo (`D-E74-scoring-source`).

## Constraints (unchanged)
PR #16 stays OPEN, create-only. Real customer data NEVER in git/CI/reports (PM-06/PM-17). Workflow-touching PRs declare it in the FIRST body line. Tags `o17-<task>`; never move existing tags.

---
**Status:** DISPATCHED (T0 2026-11-25) — E-74 scoring-source ruling added 2026-11-25 (Option 1 confirmed; stage 2 is UNBLOCKED) — start stage 1 (E-73) immediately.
