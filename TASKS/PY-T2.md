# [AGENT-TASK PY-T2] PM-17 samples rule + un-deferred local checks + ORDER 17 Python batch

**Lane:** Python (`majid-ghanbari-dost/Kandoo-Digital-Invoice`) — **Posted by:** exec-manager (2026-11-24, Asia/Tehran)
**Source orders:** M-008 §1–§2 (supersedes M-007 §4), `docs/messages/M-008.md` and `docs/messages/M-007.md` on `main` of the C# repo `majid-ghanbari-dost/Kandoo`. Manager answer filed as R-008 in `docs/messages/MANAGER-TO-PM.md` on `arena/order-15-status` of the C# repo.
**Reporting (mandatory, GitHub only):** update the `## Status` line in THIS file + report comment on PR #16 and any new PR. PM is the trigger; PM/PO are the only mergers.

## 1. PM-17 data rule (M-008 §1) — effective immediately
- Samples with **real layout and fictional content** may be used and stored in git:
  - folder `samples/real-layout-fictional/`,
  - capture folder `agent-github-test/DiagnosticResults/` (Job_2, Job_3, Unassigned).
- Ground truth for the samples (PO correction, 2026-10-12): invoice no. 34, date 1405.08.16, **four lines** (supersedes the earlier five-line count), payable 49,547,706. The supplied ESC/POS raster is byte-identical to the certified original image; the image's payable is 49,547,706, not the transcribed 49,547,790.
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
## Status: PARTIAL — invoice 34 دقیقاً ۴ ردیف دارد؛ تصویر اصلی و رستر بایت‌به‌بایت یکسان، payable=`49,547,706` را تأیید می‌کنند و رونویسی `49,547,790` با خطای +84 ریال اصلاح شد. جمع=`50,051,429`؛ اختلاف payable=`503,723` ریال حل‌نشده و بدون مدرک تخفیف است. E-72 بردار DRAFT اصلاح و به E-11/C# هم‌تراز شد؛ C# review trigger ثبت شد و پاسخ مستقل در انتظار است. E-73 رگرسیون ۱۱ فایل/سه پوشه فقط با payload ساختگی دارد؛ triage محلی: `3 folders, 0 ready, 3 review`, کدها `AMBIGUOUS_SPL=1`, `EMPTY_SPL=1`, `JOB_IN_WRONG_FOLDER=1`, `MISSING_PNG=2`, `MISSING_REPORT=1`, `MISSING_SPL=2`. آزمون‌های محلی: E72 `4 passed`; هدفمند E73 `41 passed in 4.91s`; full synthetic harness `2088 passed in 229.65s`. CI pushها روی `e6339a4`: Python [45391144844](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144844), Windows [45391144767](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144767), O15/full harness [45391144776](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144776) همگی success؛ N-01/N-04 اختیاری skipped، فقط هشدار deprecation. Tagها: `o17-E-72` روی `1e029bd`, `o17-PY-T2` روی `e6339a4`. E-70، E-71 layoutهای 2/3 و E-74 همچنان مسدود؛ E-63 deferred. PR #16 باز است ولی اکنون `CONFLICTING`; طبق دستور merge/rebase نمی‌شود. گزارش: `docs/reports/py-t2-order17-fa.md`; C# review trigger: https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7131272676

### Ground truth فاکتور 34 — چهار ردیف، بدون ردیف پنجم

| ردیف | کالا | تعداد | مبلغ ردیف (ریال) |
|---:|---|---:|---:|
| 1 | قاشق ثم | 2 | 12,926,922 |
| 2 | نایر بلند | 6 | 12,159,159 |
| 3 | کارت دعوت | 2 | 12,525,252 |
| 4 | کلاه‌زم برجسته | 9 | 12,440,096 |
| **جمع** |  |  | **50,051,429** |

تصویر/رستر هر دو `49,547,706` را نشان می‌دهند؛ اختلاف جمع با payable `503,723` ریال است و تخفیف invoice-level فرض نشده است.
