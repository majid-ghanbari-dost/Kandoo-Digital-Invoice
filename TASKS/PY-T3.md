# [AGENT-TASK PY-T3] Python lane — M-010/M-011 sprint chain (demo blockers only)

**Lane:** Python (`majid-ghanbari-dost/Kandoo-Digital-Invoice`) — **Posted by:** exec-manager (2026-11-25, Asia/Tehran)
**Source orders:** M-010 + M-011 (`docs/messages/` on `main` of the C# repo `majid-ghanbari-dost/Kandoo`). Manager answer: R-010 in `docs/messages/MANAGER-TO-PM.md` on `arena/order-15-status` of the C# repo; R-014 in `docs/messages/R-014.md` on the same branch.
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

## MANAGER RULING 2 (2026-11-26) — E-74 training sample (answers the agent's follow-up; Decision 28)

**ANSWER: Option 2 — "I'll provide an independent sample" — APPROVED as the target state**, with the conditions below. The lane's diagnosis is correct: training on invoice 34 itself would invalidate the holdout score, and the 4-of-8 quantity/line-total misreads need a second same-layout sample to fix. M-012 Q5 acknowledged: the PM accepts the PO ruling (payable 49,547,790, four lines); the honest-verification protocol continues unchanged.

**Conditions (all mandatory):**
1. **The sample comes from the PO/owner** — the lane does NOT fabricate, synthesize or otherwise substitute a sample, and does NOT reuse any real capture. PM-06/PM-17 unchanged.
2. **Certification:** real-layout + fictional-content, PO-certified (certified README per PM-17), uploaded by the PO/owner under `samples/real-layout-fictional/` in a NEW folder; same layout family as invoice-34, DISTINCT content.
3. **Labels:** operator-confirmed quantity AND line-total for EVERY line; **payable stays EXCLUDED from scoring and REPORT** (as the lane proposed).
4. **Holdout integrity:** invoice 34 remains the ONLY official E-74 scoring source/holdout (the 2026-11-25 ruling and Decision 27 unchanged). Once the sample lands, the EXTRACTED-but-wrong = 0 gate is evaluated on BOTH rasters.

**Until the sample lands on `main`:** the official E-74 score stays 0/9 PARTIAL (NOT-RUN ≠ zero). Per M-011 (agents never idle) the lane does NOT wait: **start Stage 3 (E-70) NOW**, then continue into Stage 4 (E-72 round-3 vector work; the C# verdict INCOMPATIBLE stands). Return to E-74 the moment the sample lands. Option 3's "do not start Stage 3" clause is OVERRIDDEN by M-011.

Recorded as **Decision 28** in R-011 (`docs/messages/MANAGER-TO-PM.md`, `arena/order-15-status` of the C# repo); back-filled into `docs/decisions-made.md` on `Kandoo` `main` 2026-11-27 (Decision 28 = E-74 training sample, commit `505920f`).

## MANAGER RULING 3 (2026-11-27) — OWNER OVERRIDE: the lane builds the sample ITSELF; data restriction LIFTED

**The OWNER's direct order, in force immediately, recorded in R-014** (`docs/messages/R-014.md`, branch `arena/order-15-status` of the C# repo): the owner CERTIFIES that no real data exists anywhere in this project — all invoice data in the invoices and samples is FICTIONAL — and orders that every boundary built so far be removed until project delivery, with speed-only forward motion, executed now.

1. **PM-06/PM-17 real-data restriction is LIFTED by the owner's certification** for the remainder of the project. MANAGER RULING 2 conditions (a) "sample comes from the PO/owner — the lane does NOT fabricate", (b) "PO-certified", (c) "operator-confirmed labels" are OVERRIDDEN. **The lane is AUTHORIZED to fabricate/synthesize the second E-74 sample ITSELF, NOW.**
2. **Build the sample immediately — this outranks the Stage 3/4 sequencing (owner speed order):** same print-layout family as invoice-34, DISTINCT fictional content (shop name, items, quantities, amounts — all invented; realistic Persian-looking values; nothing copied from any existing capture), rendered as a print-style raster like `invoice-34.png`, in a NEW folder under `samples/real-layout-fictional/` (suggested name `lane-synthetic-01/`), with a README stating: fabricated by the lane under the owner's 2026-11-27 override; layout real, content fictional.
3. **Labels:** write the exact ground truth for EVERY field into a labels file in that folder (invoice no., date, line count, per-line name/quantity/line-total, payable). The lane generated the content, so the labels are exact by construction; no operator confirmation needed.
4. **Scoring:** once the sample lands, evaluate on BOTH rasters — invoice 34 remains the official holdout per Decision 27 (its labels unchanged), the new sample is scored against the lane's own labels. The payable-exclusion of RULING 2 applied to an owner-provided sample and does NOT apply to a lane-generated one — score payable on the new sample. Report E-74 as two columns (invoice-34 / synthetic-01).
5. **Honesty labeling replaces the data ban:** every generated artifact is clearly marked synthetic/fictional in its README and filename; never present a generated raster as a real scan; invoice-34 labels stay untouched (Decision 27).
6. **Then continue the chain without idle:** E-74 re-score -> Stage 3 (E-70) -> Stage 4 (E-72 round 3; the C# verdict INCOMPATIBLE stands).

## Constraints (updated 2026-11-27 by MANAGER RULING 3)
PR #16 stays OPEN, create-only. PM-06/PM-17 real-data restriction is LIFTED by the owner's certification (all project data is fictional); the honesty labeling rule (RULING 3 item 5) replaces it. Workflow-touching PRs declare it in the FIRST body line. Tags `o17-<task>`; never move existing tags. Never merge/close — PM merges.

---
**Status:** DISPATCHED (T0 2026-11-25) — MANAGER RULING 3 (2026-11-27, OWNER OVERRIDE): PM-06/PM-17 lifted by owner certification; the lane builds the second E-74 sample ITSELF NOW (fabrication authorized; exact self-labels; README marked fabricated), re-scores E-74 on BOTH rasters (payable scored on the synthetic sample; invoice-34 holdout unchanged), then E-70 (Stage 3), then E-72 round 3 (Stage 4); owner speed order in force — no idle.