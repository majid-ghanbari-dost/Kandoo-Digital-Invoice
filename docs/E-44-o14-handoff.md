# E-44 — handoff نهایی ORDER 14-PY

**وضعیت: DONE.** این یادداشت دامنهٔ E-44، وضعیت E-39 تا E-47، تصمیم‌های D-A..D-K و مرز انتشار را به‌هم پیوند می‌دهد. دفتر تصمیم: [`DECISIONS.md`](DECISIONS.md)؛ waiver: [`E-43-holoo-mapping-gate-blocked.md`](E-43-holoo-mapping-gate-blocked.md)؛ دفتر tag: [`../registers/o14-tag-ledger.md`](../registers/o14-tag-ledger.md).

## مرجع و شاخه

- مرجع واحد سفارش: **ORDER 14-PY**؛ حکم مدیر `O14-PY-RULING-1` مورخ **2026-11-13** نهایی است.
- شاخهٔ مجاز: `arena/60d98123-kandoo-digital-invoice`؛ PR #15 همچنان OPEN است و به آن دست‌کاری نشده است.
- E-40 پیش از گروه E-44 روی `afb3df51af533867bb44d4bba2501da2153a7c31` قرار داشت؛ چهار CI مربوط E-40 سبز بودند. E-44 فقط پس از green شدن CI گروه خودش `o14-E-44` گرفت.
- هیچ گزارش یا فایل دادهٔ واقعی E-45..E-47 وارد index/commit/push نشده است؛ `DiagnosticResults/` با `.git/info/exclude` محلی نادیده گرفته می‌شود.

## تصمیم‌های ثبت‌شده

D-A..D-J و D-K عین دامنهٔ Order در [`DECISIONS.md`](DECISIONS.md) ثبت شده‌اند. D-K عیناً:

> D-K Out of scope: kando-internal-ai-v01 is frozen; kandoo-internal-engine-v1 is run by a separate agent outside this order.

نام‌ها و معناها کامل‌اند: `kando-internal-ai-v01 (frozen)` و `kandoo-internal-engine-v1 (run by a separate agent outside this order)`. هیچ تأیید یا نام دیگری pending نیست. E-43 نیز طبق D-I **WAIVED / NOT EXECUTED** است.

## وضعیت اجرایی E-39..E-47

| Task | نتیجه در ORDER 14 | مرجع tag/ثبت | شاهد یا مرز |
|---|---|---|---|
| E-39 | SKIPPED | tag تاریخی `w11-E-39` | PR #15 باز بود؛ E-39 در O14 دوباره اجرا نشد. |
| E-40 | ACCEPTED / DONE | `o14-E-40` → `afb3df51af533867bb44d4bba2501da2153a7c31` | سه golden افزایشی synthetic-only و manifest؛ چهار CI سبز، لینک‌ها در دفتر tag. Public-view golden پایه‌دار ساخته نشد. |
| E-41 | ACCEPTED پیش‌تر | `w11-E-41` | generator synthetic قبلی حفظ شد؛ در این سفارش دوباره اجرا نشد. |
| E-42 | ACCEPTED پیش‌تر / SKIPPED در O14 | `w11-E-42b` | harness synthetic قبلی حفظ شد؛ در این سفارش دوباره اجرا نشد. |
| E-43 | WAIVED طبق D-I | بدون tag O14 | هیچ parse/join/mapping/test روی sampleهای Holoo انجام نشد. |
| E-44 | DONE | `o14-E-44` | handoff، D-A..D-K، دفتر tag و waiver E-43 در یک commit group؛ tag تنها پس از CI سبز. مشخصات SHA و run URLها در annotation همان tag و close-out ثبت می‌شوند. |
| E-45 | ACCEPTED؛ فقط محلی | بدون commit/tag | ورودی ۱۱ فایل byte-exact بازسازی شد. پوشهٔ واقعی Job_2 با سه SPL روی `AMBIGUOUS_SPL` متوقف؛ Job_3 و Unassigned با فایل‌های لازمِ غایب مسدود. probe جداگانهٔ SPL خالی `EMPTY_SPL` داد؛ جایگزین نتیجهٔ واقعی Job_2 نیست. |
| E-46 | ACCEPTED؛ فقط محلی | بدون commit/tag | دو PNG byte-identical؛ هر ۹ candidate عددی REVIEW به‌علت DR-1؛ `EXTRACTED-but-wrong = 0`; arithmetic gate passed. هیچ thresholdی تغییر نکرد. جدول per-field در close-out چت است؛ JSON و گزارش فقط محلی‌اند. |
| E-47 | ACCEPTED؛ فقط محلی | بدون commit/tag | raster `576×1296`; detector `OK`, چهار ردیف و ستون‌های ثبت‌شده در geometry محلی. گزارش و geometry در `DiagnosticResults/` باقی ماندند. |

## شواهد CI/tag

Tag `o14-E-44` به commit واحد اسناد E-44 اشاره می‌کند. Annotation آن فهرست چهار CI اجرای همان commit را با conclusion و URL ثبت می‌کند؛ tag فقط پس از تکمیل و موفقیت همهٔ gateهای لازم ساخته شده است. Tag ledger تاریخی O14 و جزئیات قبلی E-40 در [`registers/o14-tag-ledger.md`](../registers/o14-tag-ledger.md) است. اعداد و URLهای نهایی نیز در close-out چت آمده‌اند.

## مرز امنیت/داده

`DiagnosticResults/` حاوی ورودی/خروجی واقعی است و فقط local-only/git-ignored می‌ماند. هیچ file inventory، OCR output، raster، hash دادهٔ واقعی، pipeline JSON یا گزارش تفصیلی E-45..E-47 در commitهای E-44/E-40 یا PR #15 درج نمی‌شود. فقط وضعیت و جمع‌بندی غیرمحتوایی فوق در handoff عمومی ثبت شده است.

## ادامهٔ کار

E-44 بسته است؛ `o14-E-44` مرجع ثبت commit و CI است. O14 هیچ اقدام PR-object مجاز نمی‌کند: PR #15 و PR #2 باز می‌مانند؛ `main`، tagهای `w11-*` و `stable-*` تغییر نمی‌کنند. دادهٔ محرمانهٔ E-45..E-47 تا مجوز صریح PO فقط در مسیر محلی و ignored باقی می‌ماند.
