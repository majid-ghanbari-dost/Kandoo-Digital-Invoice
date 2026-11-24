# [AGENT-TASK PY-T2] PM-17 samples rule + un-deferred local checks + ORDER 17 Python batch

**Lane:** Python (`majid-ghanbari-dost/Kandoo-Digital-Invoice`) — **Posted by:** exec-manager (2026-11-24, Asia/Tehran)
**Source orders:** M-008 §1–§2 (supersedes M-007 §4), `docs/messages/M-008.md` and `docs/messages/M-007.md` on `main` of the C# repo `majid-ghanbari-dost/Kandoo`. Manager answer filed as R-008 in `docs/messages/MANAGER-TO-PM.md` on `arena/order-15-status` of the C# repo.
**Reporting (mandatory, GitHub only):** update the `## Status` line in THIS file + report comment on PR #16 and any new PR. PM is the trigger; PM/PO are the only mergers.

## 1. PM-17 data rule (M-008 §1) — effective immediately
- Samples with **real layout and fictional content** may be used and stored in git:
  - folder `samples/real-layout-fictional/`,
  - capture folder `agent-github-test/DiagnosticResults/` (Job_2, Job_3, Unassigned).
- **R-009 ruling** (Digital-Invoice `main`, commit `eed35610ea05d034a40222a0404ef331e4cc261c`): invoice 34 has exactly four rows totaling `50,051,429`; controlling payable is `49,547,790`, so the difference is `503,639`. The earlier `49,547,706` reading is obsolete, not a competing baseline. The raw original image/raster is unavailable; mark PY-T2 **BLOCKED-on-evidence**. Keep only two hypotheses—invoice-level discount or raster-read error—and infer no discount without evidence. Request the original image through the repo; any real original/payload must remain owner-local and Git-ignored, and real data must not enter Git, CI, or artifacts.
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
## Status: PARTIAL — R-009 برای PY-T2: فاکتور 34 دقیقاً چهار ردیف با جمع `50,051,429` دارد؛ payable کنترل‌کننده `49,547,790` و اختلاف `503,639` است. `49,547,706` خوانش قبلی و منسوخ‌شده است، نه baseline رقیب. چون تصویر اصلی/raster خام موجود نیست، PY-T2 **BLOCKED-on-evidence** می‌ماند. فقط دو فرضیه ثبت می‌شوند: تخفیف سطح فاکتور یا خطای خوانش رستر؛ هیچ تخفیفی بدون evidence استنتاج نشود. تصویر اصلی از طریق [درخواست PR #16](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7138881898) درخواست شده؛ تصویر/دادهٔ واقعی باید محلی و Git-ignored بماند و وارد Git/CI/artifact نشود. **E-72:** بازبینی اصلاح‌شدهٔ C# `6039821259` vector wrapped را به‌دلیل `Unexpected field: base_invoice` رد کرد؛ اصلاح دور دوم root را flat کرده و با قرارداد frozen E-11 آزموده شده است؛ هنوز پذیرش مستقل C# برای vector جدید ادعا نمی‌شود. اصلاح E-72 و R-009 در یک گروه‌کامیت روی شاخهٔ فعلی ثبت می‌شوند؛ tag تازه فقط پس از CI سبز ساخته می‌شود. **E-73 PARTIAL:** tag `o17-PY-T2` (commit `e6339a4`) فقط regression/fixtureهای synthetic را پوشش می‌دهد؛ gate بازبینی محلیِ ساختار capture توسط مالک باز است. triage پیشین aggregate-only: `3 folders, 0 ready, 3 review`; کدهای ثبت‌شده فقط aggregate هستند: `AMBIGUOUS_SPL=1`, `EMPTY_SPL=1`, `JOB_IN_WRONG_FOLDER=1`, `MISSING_PNG=2`, `MISSING_REPORT=1`, `MISSING_SPL=2`. OCR/استخراج مقدار روی raw capture انجام نشود. آزمون‌های محلی E-72 دور دوم: `4 passed in 0.33s`; verifier PASS برای یک vector. کل Python pytest suite در این دور `2088 passed in 245.34s`. آزمون E-73 `41 passed in 4.91s`; full synthetic harness `2088 passed in 229.65s` (سابقهٔ پیشین). CI گروه‌کامیت از PR #16 checks پیگیری شود؛ tag تازه فقط پس از سبزشدن workflowهای لازم ساخته شود و review C# جدید درخواست شود. PR #16 باز و create-only است؛ هیچ rebase/merge/close انجام نشود. تصمیم قبلی PM/PO دربارهٔ PR: [کامنت](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7132327892). Tagهای قبلی `o17-E-72` روی `1e029bd` و `o17-PY-T2` روی `e6339a4` دست‌نخورده می‌مانند. گزارش‌ها: `docs/reports/py-t2-order17-fa.md`, `docs/reports/e72-order17-flat-root-r2.md`.

### Ground truth فاکتور 34 — چهار ردیف، بدون ردیف پنجم

| ردیف | کالا | تعداد | مبلغ ردیف (ریال) |
|---:|---|---:|---:|
| 1 | قاشق ثم | 2 | 12,926,922 |
| 2 | نایر بلند | 6 | 12,159,159 |
| 3 | کارت دعوت | 2 | 12,525,252 |
| 4 | کلاه‌زم برجسته | 9 | 12,440,096 |
| **جمع** |  |  | **50,051,429** |

طبق R-009، مبلغ `49,547,790` مرجع کنترل است و `49,547,706` obsolete است؛ تفاوت ردیف‌ها با payable برابر `503,639` ریال است. تصویر اصلی/raster خام در checkout نیست، پس وضعیت **BLOCKED-on-evidence** باقی می‌ماند. فقط فرضیه‌های «تخفیف سطح فاکتور» و «خطای خوانش رستر» باز هستند؛ هیچ تخفیفی استنتاج نمی‌شود. تصویر اصلی درخواست شده و باید بیرون از Git، محلی و git-ignored تحویل شود.
