# [AGENT-TASK PY-T2] PM-17 samples rule + un-deferred local checks + ORDER 17 Python batch

**Lane:** Python (`majid-ghanbari-dost/Kandoo-Digital-Invoice`) — **Posted by:** exec-manager (2026-11-24, Asia/Tehran)
**Source orders:** M-008 §1–§2 (supersedes M-007 §4), `docs/messages/M-008.md` and `docs/messages/M-007.md` on `main` of the C# repo `majid-ghanbari-dost/Kandoo`. Manager answer filed as R-008 in `docs/messages/MANAGER-TO-PM.md` on `arena/order-15-status` of the C# repo.
**Reporting (GitHub only):** per PM-33, report status through the PR description, tags, and the generated status view; no per-task report/comment is required. Under PM-31, this lane may merge PR #16 after merging the latest `origin/main` into this branch and confirming required CI is green.

## 1. PM-17 data rule (M-008 §1) — effective immediately
- Samples with **real layout and fictional content** may be used and stored in git:
  - folder `samples/real-layout-fictional/`,
  - capture folder `agent-github-test/DiagnosticResults/` (Job_2, Job_3, Unassigned).
- Ground truth for invoice 34 (corrected 2026-11-24 per PO ruling R-009): invoice no. 34, date 1405.08.16, exactly **four lines**; the earlier five-line reading is superseded. The raster-read line sum is `50,051,429` and controlling payable is `49,547,790`, a difference of `503,639`; confirm against the original image before treating raster-derived fields as ground truth and resolve/report the difference without guessing a discount.
- Each sample folder carries a short `README.md`: "layout real, content fictional, certified by the PO on <date>" + the source listed.
- If a sample is found to contain a real person's name, phone number or a real sale, stop and report it; follow the owner/manager direction for removal.
- The owner certification in R-014 (2026-11-27) lifts PM-06/PM-17 restrictions for this project; the honesty rule remains: every generated artifact must be clearly labeled synthetic/fictional and never presented as a real scan (MANAGER RULING 3 in `TASKS/PY-T3.md`).

## 2. Work items (ORDER 17)
1. **E-70** — learn from the first invoices with operator confirmation, on the real-layout samples.
2. **E-73** — capture robustness, on the samples (including `DiagnosticResults/` Job_2, Job_3, Unassigned).
3. **Two previously DEFERRED local checks (M-007 §4) are UNDEFERRED** — run them NOW on the samples; report NUMBERS ONLY (no invoice content beyond the fictional samples).
4. **E-72** — Canonical Invoice v1.2 vectors, produced for review by the C# and PHP lanes (C# reviews in `majid-ghanbari-dost/Kandoo`, PHP in `majid-ghanbari-dost/kandoo-cloud-php`); request the cross-lane review by PR comments linking the vectors file.
5. **E-71** — second and third print layouts.
6. **E-74** — accuracy gate with per-layout numbers and EXTRACTED-but-wrong = 0.
7. **E-63** — the scoring / unverified-bundle limitation: address ONLY if it takes less than half a day, otherwise stays deferred; state which in the report.

## 3. PR and tag discipline
- PM-31 (2026-11-27) supersedes earlier create-only/PM-only merge instructions: merge latest `origin/main` into this branch first; once required CI is green and GitHub confirms mergeability, this lane may merge PR #16 by merge commit or squash. Never force-push or rewrite history.
- New ORDER 17 work follows the current team/path-ownership instructions in `TASKS/MVP1-TEAM.md` on `Kandoo` `main`.
- Tags: `o16-<task>` for ORDER 16 items, `o17-<task>` for ORDER 17; never move/delete existing tags (o16-E-70 -> 3bdc648, o16-E-71/E-72/E-74 -> f99ab20).
- Workflow-touching PRs may also be lane-merged under PM-31 after required CI is green; do not force-push or rewrite history.

## 4. Report format (R-008 §3)
DONE-green / PARTIAL / BLOCKED per item, with branch names, tags, CI run URLs and the verbatim error line for anything red.

---
## Status: PARTIAL — E-74 review-only; no accuracy pass

- E-70 regression: 3 tests passed and the onboarding smoke verifier passed. The local sample evaluator remains `NOT_SCORED` (`0 evaluated / 3 not evaluated / 0 errors`); missing operator labels are not counted as zero error.
- E-73 robustness/local-onboarding tests: 18 passed; capture-folder/triage tests: 27 passed. These are regression results, not an owner-side acceptance of every capture.
- E-74: invoice-34 and `lane-synthetic-01` each had 9 expected numeric fields, 0 extracted, and all 9 in `REVIEW`. `EXTRACTED-but-wrong=0` is vacuous at zero coverage, so the accuracy gate is **NOT MET**. Invoice-34 arithmetic gate passed; the synthetic sample arithmetic gate failed. No exact-extraction claim is made.
- `scripts/run_order16_harness.py`: 2,092 tests passed (synthetic/regression only). JSON-schema validation of the new synthetic labels was not run.
- Invoice-34 line sum `50,051,429` vs payable `49,547,790` leaves `503,639` unexplained by the verified raster evidence; no discount is inferred. See the ground-truth table below.
- PM-31 sequence: latest `origin/main` is integrated into this branch by a normal merge commit; no force-push/history rewrite. PR #16 is merged only after required CI is green and GitHub confirms mergeability.

### Ground truth فاکتور 34 — چهار ردیف، بدون ردیف پنجم

| ردیف | کالا | تعداد | مبلغ ردیف (ریال) |
|---:|---|---:|---:|
| 1 | قاشق ثم | 2 | 12,926,922 |
| 2 | نایر بلند | 6 | 12,159,159 |
| 3 | کارت دعوت | 2 | 12,525,252 |
| 4 | کلاه‌زم برجسته | 9 | 12,440,096 |
| **جمع** |  |  | **50,051,429** |

طبق R-009، مبلغ `49,547,790` مرجع کنترل است و `49,547,706` obsolete است؛ تفاوت ردیف‌ها با payable برابر `503,639` ریال است. تصویر مرجع PO اکنون در `samples/real-layout-fictional/holdout-invoice-34/invoice_34.png` موجود است و README همان پوشه هش و محدودیت holdout-only را تعیین می‌کند؛ این تصویر را کپی یا برای آموزش استفاده نکنید. نتایج ثبت‌شده هنوز علت اختلاف را از روی شواهد تصویری حل نکرده‌اند؛ فقط فرضیه‌های «تخفیف سطح فاکتور» و «خطای خوانش رستر» باز هستند و هیچ تخفیفی استنتاج نمی‌شود.
