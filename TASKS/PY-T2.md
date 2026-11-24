# [AGENT-TASK PY-T2] PM-17 samples rule + un-deferred local checks + ORDER 17 Python batch

**Lane:** Python (`majid-ghanbari-dost/Kandoo-Digital-Invoice`) — **Posted by:** exec-manager (2026-11-24, Asia/Tehran)
**Source orders:** M-008 §1–§2 (supersedes M-007 §4), `docs/messages/M-008.md` and `docs/messages/M-007.md` on `main` of the C# repo `majid-ghanbari-dost/Kandoo`. Manager answer filed as R-008 in `docs/messages/MANAGER-TO-PM.md` on `arena/order-15-status` of the C# repo.
**Reporting (mandatory, GitHub only):** update the `## Status` line in THIS file + report comment on PR #16 and any new PR. PM is the trigger; PM/PO are the only mergers.

## 1. PM-17 data rule (M-008 §1) — effective immediately
- Samples with **real layout and fictional content** may be used and stored in git:
  - folder `samples/real-layout-fictional/`,
  - capture folder `agent-github-test/DiagnosticResults/` (Job_2, Job_3, Unassigned).
- Ground truth for the samples (CORRECTED 2026-11-24 per PO ruling, see R-009 in `Kandoo/docs/messages/MANAGER-TO-PM.md` on `arena/order-15-status`): invoice no. 34, date 1405.08.16, exactly **FOUR lines** — the earlier five-line entry is superseded.
- All invoice-34 figures remain raster-read (limited resolution) and MUST be confirmed by this lane against the ORIGINAL invoice-34 image before E-72/E-74 treat them as ground truth: payable 49,547,790 (raster read; the earlier 49,547,706 entry is superseded). Line-sum 50,051,429 vs payable leaves a 503,639 difference — resolve it inside this task (invoice-level discount vs read error) and report the outcome.
- Each sample folder carries a short `README.md`: "layout real, content fictional, certified by the PO on <date>" + the source listed.
- If a sample is later found to contain a real person's name, phone number or a real sale: STOP, remove it from git history if committed, and report to the PM.
- Real sales data from real customers remains FORBIDDEN in git, CI and reports (PM-06 unchanged).

## 2. Work items (ORDER 17)
1. **E-70** — learn from the first invoices with operator confirmation, on the real-layout samples.
2. **E-73** — capture robustness, on the samples (including `DiagnosticResults/` Job_2, Job_3, Unassigned).
3. **Two previously DEFERRED local checks (M-007 §4) are UNDEFERRED** — run them NOW on the samples; report NUMBERS ONLY (no invoice content beyond the fictional samples).
4. **E-72** — Canonical Invoice v1.2 vectors, produced for review by the C# and PHP lanes (C# reviews in `majid-ghanbari-dost/Kandoo`, PHP in `majid-ghanbari-dost/kandoo-cloud-php`); request the cross-lane review by PR comments linking the vectors file.
5. **E-71** — second and third print layouts.
6. **E-74** — accuracy gate with per-layout numbers and EXTRACTED-but-wrong = 0.
7. **E-63** — the scoring / unverified-bundle limitation: address ONLY if it takes less than half a day, otherwise stays deferred; state which in the report.

## 3. PR and tag discipline
- PR #16 stays OPEN, create-only — no merge, no rebase (PM merges).
- New ORDER 17 work on own branch(es) + create-only PR(s).
- Tags: `o16-<task>` for ORDER 16 items, `o17-<task>` for ORDER 17; never move/delete existing tags (o16-E-70 -> 3bdc648, o16-E-71/E-72/E-74 -> f99ab20).
- Rule from M-007 §2: any PR that changes `.github/workflows/` says so in its FIRST line; those PRs are merged by the PO, all others by the PM.

## 4. Report format (R-008 §3)
DONE-green / PARTIAL / BLOCKED per item, with branch names, tags, CI run URLs and the verbatim error line for anything red.

---
## Status: OPEN — samples rule first, then E-70/E-73 on samples + the two un-deferred checks; ground truth corrected to FOUR lines per PO ruling (R-009)
