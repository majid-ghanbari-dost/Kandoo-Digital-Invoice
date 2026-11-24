# [AGENT-TASK PY-T2] PM-17 samples rule + un-deferred local checks + ORDER 17 Python batch

**Lane:** Python (`majid-ghanbari-dost/Kandoo-Digital-Invoice`) — **Posted by:** exec-manager (2026-11-24, Asia/Tehran)
**Source orders:** M-008 §1–§2 (supersedes M-007 §4), `docs/messages/M-008.md` and `docs/messages/M-007.md` on `main` of the C# repo `majid-ghanbari-dost/Kandoo`. Manager answer filed as R-008 in `docs/messages/MANAGER-TO-PM.md` on `arena/order-15-status` of the C# repo.
**Reporting (mandatory, GitHub only):** update the `## Status` line in THIS file + report comment on PR #16 and any new PR. PM is the trigger; PM/PO are the only mergers.

## 1. PM-17 data rule (M-008 §1) — effective immediately
- Samples with **real layout and fictional content** may be used and stored in git:
  - folder `samples/real-layout-fictional/`,
  - capture folder `agent-github-test/DiagnosticResults/` (Job_2, Job_3, Unassigned).
- Ground truth/source note for invoice 34: the PO-certified fictional image shows **four lines**; its visible payable is `49,547,706`. The latest registered/communicated baseline says `49,547,790`, an 84-Rial conflict. An earlier report records the ESC/POS raster as byte-identical to the image, but the raw raster is absent from the current checkout and was not re-compared in this follow-up. Do not silently substitute either figure; resolve with PO. No discount/adjustment is inferred.
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
## Status: PARTIAL — چهار ردیف فاکتور 34 جمعاً `50,051,429` هستند. تصویر PO-certified در checkout payable=`49,547,706` را نشان می‌دهد، درحالی‌که مبنای ابلاغ‌شده در پیام اخیر `49,547,790` است: تفاضل‌ها به‌ترتیب `503,723` و `503,639` و اختلاف 84 ریال در **payable** است، نه ردیف‌ها. رستر خام حاضر نیست تا تطبیق قبلی دوباره اجرا شود؛ گزارش قبلی byte-identity را ثبت کرده است. PO باید payable مرجع را تعیین کند؛ هیچ تخفیف/اصلاحی استنتاج نمی‌شود. E-72 بردار DRAFT به E-11/C# هم‌تراز شد و review trigger ارسال شد؛ پاسخ مستقل در انتظار است. **E-73 PARTIAL:** tag `o17-PY-T2` (commit `e6339a4`) فقط regression/fixtureهای synthetic را پوشش می‌دهد؛ gate بازبینی محلیِ ساختار capture توسط مالک باز است. triage قبلی aggregate-only: `3 folders, 0 ready, 3 review`; کدها `AMBIGUOUS_SPL=1`, `EMPTY_SPL=1`, `JOB_IN_WRONG_FOLDER=1`, `MISSING_PNG=2`, `MISSING_REPORT=1`, `MISSING_SPL=2`. OCR/استخراج مقدار روی raw capture انجام نشود. آزمون‌های محلی: E72 `4 passed`; هدفمند E73 `41 passed in 4.91s`; full synthetic harness `2088 passed in 229.65s`. CI runهای کد روی `e6339a4`، سه workflow success؛ لینک‌ها در گزارش. PR #16 باز و `CONFLICTING / DIRTY` با base `180b279b6c692f841cab739577ad4fedeefb77c3` است؛ طبق دستور rebase/merge/close انجام نشود. تصمیم PM/PO: [کامنت PR](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7132327892). Tagها: `o17-E-72` روی `1e029bd`, `o17-PY-T2` روی `e6339a4`. گزارش: `docs/reports/py-t2-order17-fa.md`.

### Ground truth فاکتور 34 — چهار ردیف، بدون ردیف پنجم

| ردیف | کالا | تعداد | مبلغ ردیف (ریال) |
|---:|---|---:|---:|
| 1 | قاشق ثم | 2 | 12,926,922 |
| 2 | نایر بلند | 6 | 12,159,159 |
| 3 | کارت دعوت | 2 | 12,525,252 |
| 4 | کلاه‌زم برجسته | 9 | 12,440,096 |
| **جمع** |  |  | **50,051,429** |

تصویر PO-certified قابل مشاهده `49,547,706` را نشان می‌دهد؛ پیام اخیر مقدار مبنا را `49,547,790` اعلام می‌کند. ۸۴ ریال اختلاف در payable است؛ رستر خام در checkout حاضر نیست تا تطبیق byte-identical قبلی دوباره انجام شود. دو تفاضل متناظر (`503,723` از PNG، `503,639` از مقدار ابلاغ‌شده) تا تأیید PO جدا نگه داشته می‌شوند؛ تخفیف invoice-level فرض نشده است.
