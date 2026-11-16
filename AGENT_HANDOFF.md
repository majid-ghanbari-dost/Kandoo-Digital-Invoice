# KANDOO DIGITAL INVOICE — PYTHON AGENT HANDOFF

**آخرین محدودهٔ فعال:** ORDER 14-PY، dispatch نهایی E-44

**حکم D-K:** `O14-PY-RULING-1` مورخ 2026-11-13 — قطعی؛ هیچ نام یا تأیید دیگری لازم نیست.

## 1. Checkout و مرز Git

- مخزن: `majid-ghanbari-dost/Kandoo-Digital-Invoice`.
- شاخهٔ مجاز: `arena/60d98123-kandoo-digital-invoice`؛ شاخهٔ session ثابت است.
- پایهٔ E-44 پیش از گروه مستندات: `afb3df51af533867bb44d4bba2501da2153a7c31`، که E-40 و tag `o14-E-40` را دربر دارد.
- checkout همچنان shallow است؛ از unshallow/history rewrite/force-push پرهیز شود. worktree پیش از این dispatch با remote head همگام شد و فایل‌های محلی موجود byte-exact حفظ شدند.
- PR #15 همچنان OPEN است؛ PR #2 نیز باید باز بماند. تنها push مجاز، push همین branch برای انتشار commit مجاز E-44 است. هیچ PR-object action (merge/close، تغییر metadata، comment یا review) انجام نشود.
- `main`، tagهای `w11-*` و `stable-*` ثابت‌اند.

## 2. وضعیت ORDER 14

| Task | وضعیت نهایی | ثبت |
|---|---|---|
| E-39 | در O14 SKIPPED چون PR #15 باز است | tag تاریخی `w11-E-39` |
| E-40 | ACCEPTED / DONE؛ synthetic delta؛ چهار CI سبز | `o14-E-40` → `afb3df51af533867bb44d4bba2501da2153a7c31` |
| E-41 | قبلاً پذیرفته؛ O14 rerun نشد | `w11-E-41` |
| E-42 | قبلاً پذیرفته؛ در O14 SKIPPED | `w11-E-42b` |
| E-43 | WAIVED طبق D-I؛ هیچ E-43 اجرا نشد | `docs/E-43-holoo-mapping-gate-blocked.md` |
| E-44 | DONE با یک commit group؛ tag پس از سبزشدن همهٔ CI | `o14-E-44`; SHA و run URLs در annotation tag |
| E-45 | ACCEPTED؛ داده/گزارش فقط local و git-ignored | `DiagnosticResults/`; بدون commit/tag |
| E-46 | ACCEPTED؛ تمام عددها REVIEW تحت DR-1؛ `EXTRACTED-but-wrong=0` | `DiagnosticResults/`; بدون commit/tag؛ threshold تغییر نکرد |
| E-47 | ACCEPTED؛ geometry/report فقط local و git-ignored | `DiagnosticResults/`; بدون commit/tag |

جزئیات نهایی هر task، tagها و CI در [`registers/o14-tag-ledger.md`](registers/o14-tag-ledger.md) و [`docs/E-44-o14-handoff.md`](docs/E-44-o14-handoff.md) است. Inventory ۱۱ فایل واقعی E-45 و جدول per-field E-46 در close-out چت ارائه می‌شوند؛ داده‌های واقعی در مخزن عمومی ثبت نمی‌شوند.

## 3. تصمیم‌ها و حدود اجرا

- D-A..D-J در `docs/DECISIONS.md` ثبت شده‌اند؛ D-I waiver مربوط به E-43 است.
- D-K باید عیناً بماند:
  `D-K Out of scope: kando-internal-ai-v01 is frozen; kandoo-internal-engine-v1 is run by a separate agent outside this order.`
- نام‌ها و معناهای کامل: `kando-internal-ai-v01 (frozen)`؛ `kandoo-internal-engine-v1 (run by a separate agent outside this order)`. ORDER 14 مرجع واحد است؛ چیزی pending نیست.
- فایل‌های E-45..E-47 در `/DiagnosticResults/` محلی و git-ignored هستند. دادهٔ واقعی، hashها، pipeline JSONها و گزارش‌های تفصیلی را stage/commit/push/public نکنید، مگر مجوز صریح PO.
- E-46 نتیجهٔ تمام-REVIEW به‌علت DR-1 است. برابر بودن candidateها یا موفقیت arithmetic gate، status را EXTRACTED نمی‌کند؛ thresholdها دست‌نخورده می‌مانند.

## 4. انتشار E-44

E-44 یک commit group مستنداتی واحد دارد. فایل‌های مرتبط: این handoff، `docs/DECISIONS.md`، `docs/E-44-o14-handoff.md`، `docs/E-43-holoo-mapping-gate-blocked.md` و `registers/o14-tag-ledger.md`. هیچ فایل `DiagnosticResults/` در گروه نیست.

`o14-E-44` فقط پس از CI سبز ساخته می‌شود و باید به commit همان گروه اشاره کند. Annotation تگ، پس از تأیید CI، نام task، full commit SHA و URL/conclusion هر چهار CI اجرا را نگه می‌دارد؛ SHA و run URLs نیز در close-out نهایی می‌آیند. پس از tag، E-44 را با یک close-out واحد ببندید و taskهای دیگر را دوباره اجرا نکنید.

## 5. منابع

- `docs/DECISIONS.md` — فرض‌های Canonical Invoice v0 و تصمیم‌های O14 D-A..D-K.
- `docs/E-44-o14-handoff.md` — خلاصهٔ سرد-شروع E-39..E-47.
- `docs/E-43-holoo-mapping-gate-blocked.md` — وضعیت تاریخی W11 و waiver نهایی D-I.
- `registers/o14-tag-ledger.md` — tagها، SHAها و CIهای عمومی.
- `DiagnosticResults/` — داده و گزارش محلی E-45..E-47؛ git-ignored/confidential.
