# Kandoo Digital Invoice — PROJECT CONTINUITY HANDOFF

```text
نوع سند:        Handoff تداوم پروژه (مستقل از تاریخچه گفتگو)
نسخه:           1.0
تاریخ:           2026-10-11
نویسنده:        Agent 1 (Implementation Owner) — به دستور Technical Manager
وضعیت:          مستند/حکمرانی صرف؛ هیچ کد اجرایی در این سند تغییر نکرده است
مبنای داده‌ها:   بررسی زندهٔ GitHub + اجرای واقعی تست در سندباکس (۲۰۲۶-۱۰-۱۱)
قاعداولویت:     هرچه در این سند است در برابر مخزن «گزارش‌شده» است، نه «تأییدشده».
                منبع حقیقت، مخزن و Registerها هستند؛ این سند نقشهٔ ورود است.
```

> **چگونه این سند را بخوانیم:** هر ادعا یکی از این برچسب‌ها را دارد:
> `تأییدشده` (با فرمان/خروجی قابل بازتولید) · `گزارش‌شده ایجنت` (بدون بازبینی مستقل) · `ثبت‌شده در Register` (ادعای مستندات، لزوماً نه واقعیت مخزن) · `باز/بدون تصمیم`.
> هیچ عددی در این سند «حدس» نیست؛ اعدادی که خودم اجرا نکرده‌ام صریحاً برچسب‌دارند.

---

## ۱. هویت پروژه و مأموریت

**Kandoo Digital Invoice** خط توسعه‌ای برای **دریافت، نگهداری و پردازش قابل‌ردیابی اسناد و فاکتورهای دیجیتال** است (Holoo/POS capture ← Canonicalization). این پروژه «OCR ساده» نیست؛ هدف معماری این است که محتوای خامِ منابع بیرونی **هرگز زودبه‌زود و بدون شاهد** به داده تجاری قطعی تبدیل نشود.

**جریان رسمی External Flow (AS-01، Frozen):**

```text
External POS/Holoo → Capture → Reconstruction → Extraction → Normalization
  → Canonicalization Gate → Validation → Invoice → Digital Invoice
```

**مسیر Native Flow (AS-02):** `Product → Sale → Invoice → Digital Invoice` — مستقل از pipeline capture خارجی.

**لایه‌های پیاده‌سازی‌شده در مخزن (۱۷ package در `src/`):** `capture`، `reconstruction`، `extraction`، `normalization`، `derivation`، `validation`، `validation_domain`، `canonicalization`، `canonical_assembly`، `identity_resolution`، `duplicate_flows`، `product_candidate`، `customer_linking`، `digital_invoice`، `holoo_spike`، `corpus`، `calibration` — stdlib-only (SQLite embedded، بدون شبکه)، Python، بدون وابستگی خارجی.

**جهت MVP:** ثبت evidence و رساندن سند تا `Invoice/Digital Invoice` **بدون** هر اثر خودکار بر Sale/Inventory (AD-03/DEF1)، و بدون ساخت خودکار Customer (D-06/DEF3).

### نقش‌ها

| نقش | مسئولیت | مرز |
|---|---|---|
| **Product Owner (کاربر)** | تصمیم محصولی، Acceptance رسمی، مجوز ادغام در `main`، ratification آستانه‌ها (D-07/D-08)، باز کردن اقلام Deferred | تنها صاحب تصمیم‌های Frozen |
| **Technical Manager / Coordinator (ChatGPT)** | ابلاغ مأموریت، بازبینی شواهد، توصیه Acceptance، حل تعارض ایجنت‌ها، تعیین تکلیف PRها | تصمیم معماری جدید فقط از مسیر STOP |
| **Agent 1 — Implementation** | پیاده‌سازی + تست اجرایی + شواهد + commit/push + PR | ادغام ممنوع بدون دستور صریح |
| **Agent 2 — Independent review** | بازبینی مستقل، راستی‌آزمایی ادعاهای Register/ایجنت ۱، بدون لمس هم‌زمان فایل‌های در حال پیاده‌سازی | ادعای «تأیید شد» فقط با اجرای خودش |

**پروتکل توقف (همیشه):** هر تصمیم تعریف‌نشده → `STOP → Issue Report → Technical Manager Review → PO Decision (if required)`. ایجنت هرگز خود تبدیل به Architecture نمی‌کند (D-09).

---

## ۲. منبع حقیقت

### ۲.۱ مخزن و SHAها

| مورد | مقدار | وضعیت |
|---|---|---|
| Repository | `majid-ghanbari-dost/Kandoo-Digital-Invoice` | — |
| `main` (HEAD) | **`80d7c73fea9c00a1176736b357325d431f1a7abe`** | `تأییدشده` با `git ls-remote` در ۲۰۲۶-۱۰-۱۱؛ محتوای **۲۸۳ فایل** (۲۴۸ `.py` + ۳۵ `.md`)، ۱۷ package در `src/`، ۲۵ فایل در `specs/`، ۲۰ اسکریپت `run_smoke*` |
| شاخه کاری Agent 1 | `arena/23993033-kandoo-digital-invoice` @ `0b073c92b5b08c75bdc98b4def259e8d0978fde9` | `تأییدشده` (push موفق) |
| شاخه Agent 2 | `arena/7bee5f10-kandoo-digital-invoice` @ `b3c6194b6f1b3f5e2c9aeabab688d50463bb41b9` | `تأییدشده` (مستند/حکمرانی) |
| شاخه `integration/wp-1.3-retention-recovery` | @ `80d7c73…` (بدون commit سورس) | `تأییدشده` — ادغام‌نشده، خالی از سورس WP-1.3 |

### ۲.۲ PRها

| PR | عنوان (خلاصه) | head | وضعیت GitHub | معنا |
|---|---|---|---|---|
| **#1** | `chore(governance): WP-1.3 artifact received; independent verification passed, source integration pending` | `b3c6194` | `OPEN` · `MERGEABLE` · **ادغام‌نشده** | **فقط مستندات** (۲ فایل: `AGENT_HANDOFF.md`، `KANDOO_AGENT_COORDINATION.md`؛ +91/−69، صفر خط سورس). محتوایش ادعاهای متناقض دارد — بند ۴.۶ |
| **#2** | `feat(WP-1.3): retention/recovery mechanics — policy gate, decision journal, consistency report (125 tests + 21st smoke; DEF4 values unset)` | `0b073c9` | `OPEN` · `MERGEABLE` · **ادغام‌نشده** · ۱۸ فایل · +4349/−13 | **تحویل سورس WP-1.3**. `reviewDecision` خالی، `reviews=0`، `comments=0` |

### ۲.۳ تفکیک وضعیت‌ها (بسیار مهم)

| دسته | اقلام |
|---|---|
| **ادغام‌شده در `main`** | WP-1.1 … WP-12.2 (سورس + specs + تست‌ها) — `تأییدشده` با شمارش محتوای `main` (۲۸۳ فایل) |
| **باز، ادغام‌نشده** | PR #1 (governance) · PR #2 (سورس WP-1.3) |
| **در انتظار Acceptance رسمی PO/TM** | **۱۷ بند WP**: ۱۶ ردیف `IMPLEMENTED` (WP-1.2، 3.1، 3.2، 4.2، 5.1، 5.2، 6.1، 6.2، 7.1، 7.2، 8.1، 9.1، 10.1، 11.1، 12.1، 12.2) + WP-1.3 (`IMPLEMENTED — IN-BRANCH`) — `تأییدشده` با شمارش خط‌های `Status:` در REG-WPR |
| **FROZEN / CLOSED** | WP-1.1 (CLOSED + G3 PASS 2026-10-01) · WP-2.1 · WP-2.2 (CLOSED) · WP-4.1 (فریز رسمی ۲۰۲۶-۱۰-۰۵) · WP-7.1 (ACCEPTED/FROZEN — PO ۲۰۲۶-۱۰-۰۸) · تصمیمات D-01..D-09، AD-01..AD-04، AS-01..AS-04 |
| **DEFERRED / مسدود** | DEF1..DEF6 · WP-8.2 (PLANNED — تصمیم PO) · WP-10.2 (DEF5) · WP-11.2 (تصمیم PO/TM) · WP-12.3 (PO/G4) |
| **بدون G3 اعلام‌شده** | Gate فاز P2 … P12 هنوز اعلام نشده (Register صریحاً می‌گوید «هنوز اعلام نشده») |

> **قاعداولویت حکمرانی:** **وجود یک PR به‌معنای Acceptance یا Integration نیست.** وجود یک ردیف `IMPLEMENTED` در Register هم اثبات نمی‌کند که تغییر در `main` است. تنها سه چیز واقعیت است: **(۱)** محتوای فایل روی شاخه، **(۲)** خروجی اجرای واقعی تست، **(۳)** CommitMergeRecord صریح TM/PO.

### ۲.۴ Registerها (مخزن، مسیرهای واقعی)

```text
README.md                                  ← پروتکل حاکم + Cold-Start + STOP + وضعیت Gateها
registers/decision-register.md             ← REG-DR  (۱۷ تصمیم، همه FROZEN)
registers/deferred-decision-register.md    ← REG-DDR (DEF1..DEF6)
registers/work-package-register.md         ← REG-WPR (۲۴ بند WP + Phase Index)
registers/task-register.md                 ← REG-TR  (حافظه رسمی؛ ۸۰ بلوک تسک روی main، ۸۴ با T-1.3.x)
registers/acceptance-register.md           ← REG-AR  (۹۰ ردیف AC روی main، ۹۴ با PR #2 — ستون نتیجه همه PASS)
registers/risk-register.md                 ← REG-RR  (RSK-1..RSK-5)
specs/                                     ← ۲۵ سند روی main (۲۷ با دو سند WP-1.3 در PR #2)
src/                                       ← پیاده‌سازی + تست‌ها + ۲۰ اسکریپت smoke روی main (۲۱ با WP-1.3)
```

`AGENT_HANDOFF.md` و `KANDOO_AGENT_COORDINATION.md` هم در ریشه‌اند، اما **در زمان نوشتن این سند stale هستند** (بند ۴.۶) و مالکیت‌شان با PR #1 / Agent 2 است.

---

## ۳. وضعیت مأموریت جاری (WP-1.3 — Retention & Recovery)

مأموریت: *«Formal Decomposition + Mechanics-Only Implementation»* (TM، ۲۰۲۶-۱۰-۱۱).
خروجی: **PR #2** — سورس واقعی، نه گزارش‌محور.

| | |
|---|---|
| Base SHA | `80d7c73fea9c00a1176736b357325d431f1a7abe` `تأییدشده` |
| Head SHA (انتظار می‌رود) | `0b073c92b5b08c75bdc98b4def259e8d0978fde9` `تأییدشده` روی GitHub |
| Tasks | `T-1.3.1`..`T-1.3.4` — در REG-TR ثبت‌شده، `✅ DONE (2026-10-11)` |
| ACها | `AC-1.3.1`..`AC-1.3.4` — در REG-AR با ستون نتیجه `PASS` و ستون تصویب `Pending — TM review` |
| Contract | `specs/WP-1.3-retention-recovery-contract.md` (SPEC-WP13-RETR v1.0-MVP) |
| Report | `specs/WP-1.3-implementation-report.md` (WP13-RPT) |
| سورس | `src/capture/retention.py` · `src/capture/retention_journal.py` · `src/capture/consistency.py` |
| تست | `src/capture/tests/test_wp13_{retention,journal,purge_gate,consistency,recovery_matrix,traceability}.py` + `wp13_helpers.py` |
| Smoke | `src/run_smoke_retention_recovery.py` (بیست‌ویکمین smoke، ۸ گام cold-start) |

### ۳.۱ شواهد — تفکیک «گزارش‌شده» از «تأییدشده»

| ادعا | عدد | برچسب |
|---|---|---|
| تست‌های جدید WP-1.3 | **125 passed** (×3 تکرار مستقل) · 35 retention + 24 journal + 11 purge-gate + 26 consistency + 15 recovery-matrix + 14 traceability | `گزارش‌شده ایجنت` (خروجی واقعی در سندباکس Agent 1؛ بازبینی مستقل انجام نشده) |
| کل پکیج `capture` | **215 passed** = 90 تست از قبل موجود + 125 جدید | `گزارش‌شده ایجنت` |
| رگرسیون کامل | **1601 passed / 0 failed / 0 error / 0 skipped** در ۲۰۳٫۳۷s | `گزارش‌شده ایجنت` |
| Smoke | **8/8 گام، SMOKE OK، exit 0** (×2 اجرای مستقل با دایرکتوری تازه) | `گزارش‌شده ایجنت` |
| additive-only | `git diff --name-only -- '*.py'` خالی (صفر تغییر در کد/تست baseline) | `گزارش‌شده ایجنت` — قابل بازتولید با همین فرمان روی PR |
| Audit مستقل baseline (Agent 2) | **1476 full-suite** و **90 capture** passed روی محیط اعلامی Agent 2 | `گزارش‌شده ایجنت` — **سازگار** با اندازه‌گیری مستقل Agent 1 از همان baseline (۱۴۷۶ و ۹۰ هر دو دقیقاً تأیید شدند)؛ اما به‌عنوان «خروجی رسمی بازبینی» معتبر نیست |
| بازبینی Agent 2 روی PR #2 | — | **PENDING** — هیچ review/comment روی PR #2 ثبت نشده (`reviews=0`, `comments=0`, `reviewDecision=""`). **نتیجه‌ای برای آن ثبت نکنید تا گزارش نهایی خودش منتشر شود.** |
| CI | — | **وجود ندارد** — هیچ workflow در مخزن نیست؛ «Checks tab خالی» نشانه شکست نیست |

### ۳.۲ محیط تست اعلام‌شده

`Python 3.11.2` · `pytest 9.1.1` نصب‌شده **خارج از مخزن** (`/home/user/.venv-kandoo`) · صفر وابستگی تازه به پروژه · `src/README.md` کف «Python 3.12+» را اعلام می‌کند که **تأیید نشده** (بند ۴.۵).

### ۳.ۢ فرمان‌های بازتولید (از ریشه مخزن)

```bash
git ls-remote origin                                  # main = 80d7c73 …
git fetch origin arena/23993033-kandoo-digital-invoice
python3 -m venv /tmp/k && /tmp/k/bin/pip install -q pytest   # pytest در مخزن نیست
cd src && /tmp/k/bin/python -m pytest -q                      # رگرسیون کامل
cd src && /tmp/k/bin/python -m pytest capture/tests/test_wp13_retention.py \
  capture/tests/test_wp13_journal.py capture/tests/test_wp13_purge_gate.py \
  capture/tests/test_wp13_consistency.py capture/tests/test_wp13_recovery_matrix.py \
  capture/tests/test_wp13_traceability.py -q                    # تست‌های WP-1.3
cd src && /tmp/k/bin/python run_smoke_retention_recovery.py /tmp/wp13-smoke   # SMOKE OK
git diff --name-only 80d7c73..0b073c9 -- '*.py'                 # خالی = فقط فایل تازه
```

---

## ۴. یافته‌ها و تصمیم‌های باز (هیچ‌کدام در این سند بسته نشده)

### ۴.۱ Observation هم‌زمانی WP-1.3 (بازیابی فروزن ↔ ingest در حال اجرا)
اگر `run_startup_recovery` رکورد `ACTIVE` در-جریان را تسویه کند، همان `CaptureService.ingest` با `IllegalTransition` (از `CaptureLayerError`) به‌صورت exception بیرون می‌آید، نه با یک outcome تایپ‌دار «باختن به recovery». **هیچ خوردگی/نیمه‌حالتی رخ نمی‌دهد** و INV-C6 («recovery همه ACTIVE را تسویه می‌کند») نقض نشده — تست هم‌زمانی مبتنی بر invariant این را تأیید می‌کند. چون `service.py`/`recovery.py` فروزندند، در WP-1.3 وصله‌ای اعمال **نشد**.
**تصمیم لازم:** TM/PO — (الف) پذیرش رفتار فعلی + ثبت در Register، (ب) مجوز اصلاح فایل فروزن، (ج) افزودن outcome تایپ‌دار در یک WP آتی.

### ۴.۲ تست تاریخ‌حساس: `test_ir_provenance::test_no_raw_pipeline_values_are_stored`
فایل **فrozen** (متعلق به WP-7.1). کاوش نشان داد این «flake» نیست، بلکه **date-collision قطعی** است: assert می‌کند رشته literal تاریخ fixture یعنی `2026-10-08` در dump دیتابیس نباشد، ولی `created_at` از `datetime.now(UTC)` ساخته می‌شود → **در هر روزی که تاریخ UTC اجرا برابر تاریخ fixture باشد می‌شکند** (اثبات: ساعت فورس‌شده → `FAILED`؛ ساعت واقعی → `PASSED`).
پیامدها: (۱) در اجرای ۲۰۲۶-۱۰-۱۱ رخ نداد → رگرسیون ۱۶۰۱/۱۶۰۱ است، نه «۱۶۰۰ + ۱ flake»؛ الگوی عددی WPهای پیشین بازتولید نشد. (۲) هر **۸ اکتبر** سالانه تکرار می‌شود. (۳) اصلاح ارزان و test-side است ولی فایل Frozen است → **بدون مجوز صریح TM دست نخورده**.

### ۴.۳ DEF4 و حذف فیزیکی
`DEF4` همچنان `DEFERRED` است: **هیچ** مقدار مدت نگهداری/TTL/privacy/اشتراک‌سازی/مجازسازی purge وجود ندارد و **نباید ساخته شود**. WP-1.3 فقط mechanics پارامتریک داد (همه مقادیر تزریق‌شده؛ فقدان = refusal). **حذف فیزیکی در WP-1.3 پیاده‌سازی نشده و مسدود است** (`PURGE_GATE_BLOCKED`، `executed=False`، `rows_affected=0`، رد credential ساختگی، و اثبات بی‌اثری با مقایسه بایت‌به‌بایت فایل دیتابیس).

### ۴.۴ ارجاع‌های legacy با پیشوند `kandoo/`
روی `main` دقیقاً **۳۲۰ ارجاع** به مسیرهایی مثل `kandoo/specs/…`، `kandoo/src/…`، `kandoo/baseline/…` در `registers/*.md` + `README.md` وجود دارد که **از ریشه مخزن resolve نمی‌شوند** (پوشه `kandoo/` وجود ندارد). بازتولید شمارش: `git ls-tree -r main --name-only | grep -E '^(registers/|README)'` و شمارش `kandoo/(specs|src|baseline)`. این نقض Cold-Start rule §2 («هر ارجاع = مسیر فایل یا شناسه رکورد») است. رکوردهای تازه WP-1.3 عمداً repo-root-relative نوشته شدند.
**تصمیم لازم:** پاک‌سازی کنترل‌شده و مستقلاً قابل‌بازبینی (document-only PR)، نه اصلاح پراکنده در PRهای اجرایی.

### ۴.۵ بدهی MNT-1 و وضعیت Acceptance/G3
* `baseline/` هنوز در مخزن **وجود ندارد**؛ چهار سند Baseline (Frozen Canonical Invoice v1، Master Architecture، Master Roadmap، MRR) commit نشده‌اند → REG-DR همچنان SSOT موقت متنی است (**RSK-2 باز**). deadline ثبت‌شده در ریسک («پیش از G3 فاز P2») گذشته است و ۱۰ فاز بعدی اجرا شده.
* **G3 برای P2…P12 اعلام نشده**؛ **۱۷ بند WP** هنوز «در انتظار Acceptance رسمی» هستند (۱۶ `IMPLEMENTED` + WP-1.3 `IN-BRANCH`)؛ تنها WP-1.1 / WP-2.1 / WP-2.2 به `CLOSED` رسیده‌اند، WP-4.1 فریز رسمی است و WP-7.1 در Phase Index به `ACCEPTED/FROZEN (PO)` رسیده است.
* `src/README.md` کف «Python 3.12+» را نگه می‌دارد درحالی‌که کل suite روی 3.11.2 سبز است — یا اصلاح مستند یا اجرای واقعی روی 3.12+.
* `history` مخزن یک commit گrafted است → `git log` روی `main` هیچ ادعای WP را substantiate نمی‌کند؛ راستی‌آزمایی فقط با **حضور فایل + اجرای تست**.

### ۴.۶ PR #1 — متناقض، و سورس نیست
عنوان/بدنه PR #1 می‌گوید «artifact دریافت شد، ۱۵۶۶ تست PASS»؛ commitهای **همان PR** می‌گویند «BLOCKED — artifact هرگز deliver نشد، هیچ ZIP/manifest یافت نشد». محتوای واقعی: ۲ فایل مستندات، **صفر سورس**. ادعای «1566» در این سندباکس **قابل بازتولید نیست** (۱۴۷۶ عدد واقعی baseline است؛ ۱۵۶۶ − ۱۴۷۶ = ۹۰ که با اندازه WP-1.3 هم‌خوان است، اما تأییدشده نیست).
ضمناً `AGENT_HANDOFF.md` روی `main` stale است: بند ۹ آن می‌گوید «درخت پیاده‌سازی هنوز منتقل نشده»، درحالی‌که `main` کاملِ P1–P12.2 را دارد (PR #1 همین stale بودن را رفع می‌کند و عدد ۱۴۷۶ تست baseline آن با اندازه‌گیری مستقل این سندباکس یکی است).
**تصمیم لازم:** تکلیف PR #1 (merge اصلاح هندآف / close / supersede) + اصلاح عنوان گمراه‌کننده — جدا از تحویل سورس.

### ۴.۷ مالکیت فایل مشترک (تعارض ایجنت‌ها)
`AGENT_HANDOFF.md` و `KANDOO_AGENT_COORDINATION.md` هم‌اکنون تحت مالکیت PR #1/Agent 2‌اند. به همین دلیل WP-1.3 آن‌ها را **لمس نکرد** و به‌جایشان این سند مستقل (`PROJECT_CONTINUITY_HANDOFF.md`) ساخته شد. هر دو فایل را هم‌زمان ویرایش نکنید.

### ۴.۸ ناهمخوانی‌های داخلی Register (ثبت شد، اصلاح نشد)
| مورد | مشاهده |
|---|---|
| وضعیت WP-7.1 | خط `Status:` بند WP-7.1 همچنان `IMPLEMENTED (2026-10-08)` است و در کل بند آن (خطوط ~۱۱۱۷–۱۲۶۶) هیچ واژه `ACCEPTED` نمی‌آید؛ اعلام **ACCEPTED/FROZEN (PO ۲۰۲۶-۱۰-۰۸)** فقط در «Phase Index» بالای همان فایل آمده است. هر دو متن در مخزن‌اند؛ «Accepted By/Date» در REG-AR برای ACهای P7 بررسی/تکمیل شود. |
| عدد رگرسیون در بدنه PR #1 | بدنه PR #1 «۱۵۶۶ تست PASS» را claim می‌کند؛ عدد baseline اندازه‌گیری‌شده در این سندباکس **۱۴۷۶** است و PR #2 آن را **۱۶۰۱** (= ۱۴۷۶ + ۱۲۵) گزارش می‌کند. **۱۵۶۶ در این مخزن بازتولیدناپذیر است** و هیچ جای دیگر ثبت نشده. |
| `IMPLEMENTED` ≠ ادغام | ردیف `IMPLEMENTED` در Register به‌تنهایی اثبات نمی‌کند سورس روی `main` است؛ برای WP-1.3 این ردیف **در PR #2** است و هنوز ادغام نشده (`تأییدشده` با `gh pr view 2 --json state,mergedAt`). |


---

## ۵. تصمیمات Frozen و مرزهای ایمنی (تغییر = فقط مسیر STOP)

| شناسه | قاعده |
|---|---|
| **D-02** | مدل سه‌هویتی: Capture Identity (`S1 = capture_content_fingerprint`) · External Document Identity (`S2`/`CAPTURE_SCOPED`) · Canonical `invoice_id` — **فقط Kandoo صادر می‌کند** |
| **D-03** | `S1` → idempotency سطح Capture؛ duplicate قطعی سند فقط با `S2` کامل؛ هر ابهام → `REVIEW`؛ **تعریف idempotency جدید ممنوع** |
| **D-06 / DEF3** | **ساخت خودکار Customer از Capture ممنوع** — فقط deterministic link |
| **AD-03 / DEF1** | **Inventory در MVP هیچ اثری از External Capture نمی‌بیند**؛ اتصال فاکتور خارجی به `Sale` نیز enrichment آینده است (DEF1) — ساخت خودکار Sale/Inventory ممنوع |
| **D-01** | `unit_amount` یک Core field است و ترتیب حل آن `EXTRACTED → DERIVED → UNRESOLVED`؛ `DERIVED` فقط از مقدار دارای evidence |
| **D-04** | مسیر Holoo: `Holoo DB → Adapter / Enrichment → Canonical`؛ **Canonical هرگز به ساختار source وابسته نمی‌شود** |
| **AD-01** | دو جریان منبع (Native / External) که هر دو در Canonicalization به Canonical می‌رسند — مرز مسئولیت ۱۱ دامنه (AD-02) در همین چارچوب است |
| **D-05** | Product Matching: چهار قرارداد خروجی؛ Exact Match فقط با identifier قطعی |
| **D-07 / D-08** | اعداد 99.9% / 99% / 50–70% و rounding tolerance **placeholder کالیبراسیون‌اند**، نه target مهندسی؛ ratification = WP-12.3 (PO/G4) |
| **AS-04** | فهرست fieldها، invariants و مدل provenance: **Frozen Canonical Invoice v1 مرجع قطعی است**؛ WPها باید نقل (quote) کنند، نه بازنویسی |
| **AD-04** | خروجی Validation شامل `REVIEW`/`REJECT` است و `UNRESOLVED` فیلد-سطحی می‌تواند Invoice را به `REVIEW` ببرد — **نام وضعیت‌ها از سند مبدأ منتقل می‌شود** |
| **AS-03** | Validation State Machine و Digital Invoice State Machine عیناً از Master Architecture §E منتقل می‌شوند؛ **هیچ state جدید در سطح WP ساخته نمی‌شود** |
| **DEF4** | **مقادیر سیاست retention/privacy حدس زده نمی‌شوند**؛ mechanics پارامتریک؛ تا مصوب شدن سیاست، حذف فیزیکی مسدود |
| **DEF2** | ماتریس عملیاتی/دسترسی REVIEW ساخته نمی‌شود (mechanism در WP-5.2 هست) |
| **DEF5 / DEF6** | ارائه Digital Invoice و نگاشت فیلدهای Modian تعریف‌نشده‌اند |
| **D-09** | پس از Freeze: بدون انتخاب OCR/VLM/DB، بدون طراحی API/UI، بدون Migration/Schema سطح معماری، بدون بازکردن اقلام Deferred |
| **Canonicalization Gate** | خروجی فقط **`AUTO` / `REVIEW` / `REJECT`**؛ در ابهام، `REVIEW` بر حدس ارجح است |
| **قاعده طلایی** | **هیچ ویرایشی در فایل/تست Frozen بدون مجوز صریح TM مجاز نیست** (الگوی Flake Policy: ثبت observation، نه وصله پنهان) |

**اصل «مقدار ناشناخته ≠ مقدار قطعی»:** هر خروجی‌ای که ورودی سیاست ندارد باید `NOT_EVALUATED`/`UNRESOLVED`/`DEF4-PENDING` بدهد، نه صفر، نه مقدار «منطقی».

---

## ۶. پروتکل همکاری

1. **Agent 1:** پیاده‌سازی + **شواهد قابل‌اجرا** (فرمان، خروجی، تعداد واقعی). هیچ تستی بدون اجرای واقعی `PASS` نمی‌شود.
2. **Agent 2:** بازبینی **مستقل** با اجرای خودش؛ هم‌زمان فایل‌های در حال پیاده‌سازیِ ایجنت دیگر را ویرایش نمی‌کند؛ بازبینی، مالکیت را منتقل نمی‌کند.
3. **TM/ChatGPT:** مأموریت با Scope + فایل‌های مجاز + ACها + شرایط پایان ابلاغ می‌کند؛ شواهد را می‌خواند؛ Acceptance را **توصیه** می‌کند؛ تکلیف تعارض‌ها را روشن می‌کند.
4. **PO:** تصمیم نهایی محصول؛ Acceptance رسمی؛ **مجوز صریح ادغام**؛ ratification آستانه‌ها؛ باز کردن DEFها.
5. **هرگز بدون شاهد اعلام نکنید:** merge، PASS شدن تست، دریافت/verify شدن artifact، Acceptance، تغییر روی GitHub، یا «Register گفت پس انجام شده».
6. **هر WP یک مالک**؛ کار ایجنت‌ها روی شاخه‌های جدا؛ `main` فقط شاخه ادغام است.
7. **پس از هر تغییر معنادار پروژه:** به‌روزرسانی همین سند تداوم — از طریق **یک PR مستندات‌محور مستقل** یا تغییر حکمرانیِ صریحاً مجوزدار (نه لابه‌لای PR سورس).
8. **تعارض دستور/پلتفرم:** اگر خواسته‌ای با قید محیطی در تضاد بود، محدودیت را شفاف گزارش کنید و کمینه‌نقض‌کننده‌ترین مسیر را پیشنهاد دهید — نه اینکه بی‌صدا یکی را نادیده بگیرید.

---

## ۷. اقدامات بعدی دقیق (مالک + شاهد بستن)

| # | اقدام | مالک | چه چیزی آن را می‌بندد |
|---|---|---|---|
| 1 | **بازبینی مستقل PR #2** — اجرای ۳ فرمان بند ۳.۳ در سندباکس خودش و ثبت عدد واقعی + بررسی اینکه هیچ فایل Frozen تغییر نکرده | **Agent 2** | Review/Report منتشرشده روی PR #2 با اعداد اجراشده؛ تا پیش از آن، هیچ‌یک از اعداد بند ۳.۱ «تأییدشده» نیست |
| 2 | **بررسی Observation هم‌زمانی ۴.۱** و تصمیم (پذیرش / مجوز اصلاح / WP آتی) | **TM → در صورت تغییر رفتار: PO** | تصمیم ثبت‌شده در REG-RR یا REG-WPR؛ اگر فایل فروزن لمس شود: مجوز صریح + AC جدید |
| 3 | **تصمیم درباره تست تاریخ‌حساس ۴.۲** (اصلاح test-side نیازمند مجوز لمس فایل Frozen) | **TM** | یا مجوز اصلاح با AC، یا ثبت رسمی به‌عنوان ریسک پذیرفته‌شدهٔ سالانه |
| 4 | **PR #2 را باز نگه دارید** — بدون merge تا پایان بند ۱ و مجوز صریح PO | **TM/PO** | دستور ادغام صریح + ثبت SHA ادغام در همین سند |
| 5 | **تکلیف PR #1** (merge اصلاح هندآف / close / supersede) و اصلاح عنوان گمراه‌کننده‌اش | **TM (+PO برای Acceptance مستندات)** | تصمیم ثبت‌شده + وضعیت نهایی PR؛ **هیچ‌گاه آن را «تحویل سورس» گزارش نکنید** |
| 6 | **پاک‌سازی مسیرهای `kandoo/`** (بند ۴.۴) در یک PR مستندات‌محور مستقل | **Agent 1 (اجرا) / TM (بازبینی)** | `grep -c 'kandoo/\(specs\|src\|baseline\)'` = 0 و نمونه‌برداری resolveشدن مسیرها |
| 7 | **commit اسناد Baseline** در `baseline/` + Reconciliation شناسه‌های `[D#]` (MNT-1/RSK-2) | **PO + TM** | حضور فایل‌ها روی `main` + به‌روزرسانی ستون Source Document در REG-DR |
| 8 | **اعلام G3 فازها و Acceptance رسمی** برای ۱۷ بند WP باز | **PO (با توصیه TM)** | ستون Accepted By/Date در REG-AR + به‌روزرسانی Phase Index |
| 9 | **تصمیم‌های مسدودساز مسیر بعدی:** WP-12.3 (D-07/D-08)، WP-11.2 (DEF6)، WP-10.2 (DEF5)، WP-8.2 | **PO/G4** | Decision Register update — پیش از آن هیچ پیاده‌سازی‌ای در این نواحی مجاز نیست |

---

## ۸. بازیابی برای گفتگوی جدید ChatGPT (Technical Manager تازه)

**مخزن را بخوانید، نه تاریخچه گفتگو را.** ترتیب: `PROJECT_CONTINUITY_HANDOFF.md` (این فایل) → `README.md` → `registers/decision-register.md` → `registers/deferred-decision-register.md` → `registers/work-package-register.md` → `registers/task-register.md` → `registers/acceptance-register.md` → `specs/` مرتبط → سپس **بررسی زنده** `main`، PRها و SHAها با `git ls-remote` / `gh pr view`.

### پرامپت آماده کپی

```text
You are resuming as Technical Manager for the Kandoo Digital Invoice project.

Repository: majid-ghanbari-dost/Kandoo-Digital-Invoice. Do not rely on prior chat
history; the repository is the source of truth and I have no memory of earlier sessions.

First: read PROJECT_CONTINUITY_HANDOFF.md at the repo root, then README.md, then
registers/{decision,deferred-decision,work-package,task,acceptance,risk}-register.md.

Second, before trusting anything recorded there, verify live state:
  git ls-remote origin
  gh pr list --state all
  gh pr view 1 --json state,mergedAt,files
  gh pr view 2 --json state,mergedAt,headRefOid,files,reviews,comments
main is expected at 80d7c73fea9c00a1176736b357325d431f1a7abe; WP-1.3 source is
delivered as OPEN PR #2 at 0b073c92b5b08c75bdc98b4def259e8d0978fde9 (unmerged, no
acceptance, no CI in this repo). Agent 1's reported evidence for PR #2 is: 125 new
tests, 215 capture-package tests, 1601 full-regression tests, 8/8 smoke steps —
treat these as UNVERIFIED until you (or Agent 2) re-run them with the commands in
section 3.3 of the handoff. Agent 2's review of PR #2 is still PENDING; do not invent
its result. PR #1 is governance-only and contains contradictory artifact claims —
it is not source integration.

Then continue as Technical Manager: dispatch narrow missions with explicit scope,
authorized files, acceptance criteria and end conditions; require real test output;
review evidence before recommending acceptance.

Constraints you must preserve: all Frozen decisions (D-01..D-09, AD-01..AD-04,
AS-01..AS-04) and the Deferred items DEF1..DEF6 — never implement a deferred area or
invent DEF4 retention/privacy/purge policy values; physical deletion stays blocked;
REVIEW beats guessing; Canonicalization Gate outcomes are only AUTO/REVIEW/REJECT;
no automatic Sale/Inventory/Customer creation from captures; never edit a frozen
source or test file without explicit authorization; never merge to main without an
explicit PO/TM order; never claim a merge, test, artifact verification, acceptance or
GitHub change without evidence.

Multi-agent protocol: one owner per WP; Agent 1 implements with executable evidence,
Agent 2 reviews independently, no concurrent edits to the same files, update
PROJECT_CONTINUITY_HANDOFF.md after each integration via a documentation-only PR.

Do not restart completed work (P1–P12.2 code is already on main) and do not ask me to
repeat project history that this file already contains. Start by reporting the verified
live state and the next three decisions from section 7.
```

---

```text
پایان سند. این سند مستندات‌محور است: هیچ کد، تست، Register یا تصمیم Frozen را تغییر نمی‌دهد.
هر ادعای «تأییدشده» در آن با فرمان‌های بند ۳.۳ روی مخزن زنده قابل بازتولید است.
```
