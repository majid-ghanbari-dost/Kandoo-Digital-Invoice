# Kandoo Digital Invoice — PROJECT CONTINUITY HANDOFF

```text
نوع سند:        Handoff تداوم پروژه — نسخه ۲.۱ (بازسازی‌کامل بر اساس حقیقت زندهٔ GitHub)
نسخه:           2.4 (پیشین: 2.3 — ثبت انتقال گزارش Agent 2 به Issue #5؛ نسخه‌های پیشین تاریخی‌اند)
تاریخ:          2026-10-12 · ویرایش: پس از ادغام PR #6 و ثبت SHA ادغام
زمان ثبت (UTC): 2026-10-12T06:47:37Z (ادغام PR #6) · پیگیری: انتقال گزارش به Issue #5 توسط TM
نویسنده:        Agent 2 — governance/handoff/review (مأموریت رسمی: Issue #5)
مبنای داده‌ها:   فقط بررسی زندهٔ GitHub (gh/git در همین سندباکس) + اجرای واقعی تست؛
                هیچ ادعای «گزارش‌شده» بدون برچسب «قطعی» نشده است.
آدرس‌رسانی:     شاخهٔ اختصاصی arena/a776e4f2-kandoo-digital-invoice →
                PR #6 (https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/6)
                شواهد نهایی/SHAها: گزارش همین PR (ثبتِ گزارش در Issue #5 با اتصال
                فعلی HTTP 403 شد و انجام نشده است — GOV-PP-01 v1.1 بند ۱/الف)
پروتکل اجباری:  PUBLICATION_PROTOCOL.md (GOV-PP-01 **v1.1** — fallback 403 + ارجاع
                تعیین‌تکلیف‌نشدهٔ CLI به PO/TM) — الزام‌آور برای همهٔ تحویل‌ها
```

> **برچسب‌های ادعا (الزامی):** `اجراشده` = خروجی واقعی همین سندباکس، قابل بازتولید با فرمانِ ثبت‌شده · `گزارش‌شده` = ادعای ایجنت/سند دیگر با نام منبع · `ثبت‌شده` = ادعای Register (لزوماً = واقعیت نیست) · `باز` = بدون تصمیم.

---

## ۱. هویت، مالکیت فایل‌ها، پروتکل

جریان رسمی (AS-01، Frozen): `External POS/Holoo → Capture → Reconstruction → Extraction → Normalization → Canonicalization Gate → Validation → Invoice → Digital Invoice`. مخزن stdlib-only (SQLite embedded)، ۱۷ package در `src/`.

| نقش | مالکیت فایل/دامنه | مرز |
|---|---|---|
| **Product Owner** | Acceptance رسمی، merge به `main`، RATIFICATION (D-07/D-08)، باز کردن DEFها | تنها صاحب تصمیم Frozen؛ هیچ Agent از جانب PO Acceptance ثبت نمی‌کند |
| **Technical Manager** | dispatch مأموریت، بازبینی شواهد، توصیهٔ Acceptance | تصمیم جدید فقط از مسیر STOP |
| **Agent 1** — مأموریت باز **[Issue #4](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/issues/4)** | `src/**` + تست‌های محصولی قابلیت‌ها + شواهد اجراشدهٔ پیاده‌سازی | دست‌زدنِ Agent 2 به سورس/تست محصول ممنوع |
| **Agent 2** — مأموریت باز **[Issue #5](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/issues/5)** | `PROJECT_CONTINUITY_HANDOFF.md`، `registers/*` (governance)، `PUBLICATION_PROTOCOL.md`، بازبینی/دفاتر | Acceptance از جانب PO ممنوع؛ تغییر سورس/تست محصول ممنوع |

**هم‌زمانی فایل ( GOV-PP-01 بند ۶):** PR بازی که فایلی را لمس می‌کند ↔ ممنوعیت ویرایش هم‌زمان همان فایل. همین‌حالا: **PR #1 دارد `AGENT_HANDOFF.md` و `KANDOO_AGENT_COORDINATION.md` را ویرایش می‌کند → هیچ ایجنت دیگری آن دو فایل را تا تکلیف PR #1 دست نمی‌زند** (مخالفت‌ها در بند ۷.۹ ثبت‌اند).

**پروتکل توقف:** هر تصمیم تعریف‌نشده → `STOP → Issue Report → TM Review → PO Decision` (D-09). **Golden Rule:** بدون مجوز صریح TM هیچ فایل/تست Frozen دست نمی‌خورد؛ بدون دستور PO هیچ merge/ Acceptance ثبت نمی‌شود؛ هیچ merge/PASS/Acceptance بدون شاهد اعلام نمی‌شود.

---

## ۲. حقیقت زندهٔ GitHub — ثبت `2026-10-11T20:28:02Z` (`اجراشده`)

### ۲.۱ SHAها و شاخه‌ها

| مورد | مقدار | وضعیت و شاهد |
|---|---|---|
| **`main`** | **`77edafa8b474cf8037a9152593fcad5056e86b57`** | `اجراشده` با `git ls-remote origin refs/heads/main` · **تک‌commit بدون والد** (بازنویسی/squash تاریخچه پس از ادغام PR #3) · message: `docs(continuity): publish current project handoff` |
| تاریخچهٔ قدیم `main` | `80d7c73fea9c00a1176736b357325d431f1a7abe` | **دیگر والدِ `main` نیست** (`git merge-base --is-ancestor` ناموفق) · روی شاخهٔ `integration/wp-1.3-retention-recovery` محفوظ است |
| merge commit ثبت‌شدهٔ GitHub برای PR #2 | `de38db0dc0e66158028b823aaffd6facd3fd1fc5` | `ثبت‌شده` از GitHub API (`gh pr view 2`) · در تاریخچهٔ `main` فعلی **نیست** (پیامد همان بازنویسی) |
| head نهایی PR #2 (پیش از ادغام) | `25565e8f5ab74297ca6a9fdd18c38efbf5416381` | `اجراشده` — شامل رفع B1/M1 · همچنان روی `arena/23993033-…` و `refs/pull/2/head` |
| head نهایی PR #3 | `b6a2eccfaae734abbe9888ec74358ec1af59c97f` | `اجراشده` — سند هندآف (بازنویسی‌شدهٔ v2.0) |
| head PR #1 (باز) | `b3c6194b6f1b3f5e2c9aeabab688d50463bb41b9` | `اجراشده` |
| `baseline/` | **غایب** | `اجراشده` — MNT-1/RSK-2 باز |
| درخت `main` | ۲۹۷ فایل (۲۵۹ `.py`) | `اجراشده` با `git ls-tree -r origin/main` — شامل کامل WP-1.3 + هندآف |

### ۲.۲ PRها و Issueها — وضعیت قطعی (بدون استنتاج)

| مورد | وضعیت GitHub (`gh pr/issue view`) | محتوا | تکلیف |
|---|---|---|---|
| **PR #1** | `OPEN` · `MERGEABLE` · `CLEAN` · ادغام‌نشده | فقط ۲ سند حکمرانی (`AGENT_HANDOFF.md`، `KANDOO_AGENT_COORDINATION.md`) — صفر سورس | **باز** → بازبینی + توصیه در بند ۷.۹؛ merge/close فقط PO |
| **PR #2** | **`MERGED`** @ `2026-10-11T19:28:01Z` توسط `majid-ghanbari-dost` · merge commit (API) `de38db0…` | ۱۸ فایل سورس/تست/رегистر WP-1.3 از head `25565e8…` (**شامل رفع B1/M1**) | **ادغام‌شده** — محتوا اکنون در `main` است (بند ۳ تأیید فایلی) |
| **PR #3** | **`MERGED`** @ `2026-10-11T19:30:20Z` توسط `majid-ghanbari-dost` · merge commit (API) `77edafa…` (= `main` فعلی) | ۱ فایل `PROJECT_CONTINUITY_HANDOFF.md` از head `b6a2ecc…` | **ادغام‌شده** — نسخهٔ ۲.۰ سند بود؛ همین نسخه ۲.۱ جایگزین آن می‌شود |
| **Issue #4** | `OPEN` @ `2026-10-11T20:06:31Z` | مأموریت Agent 1: MVP Reality Audit + اولین شکاف بحرانی | **باز — مالک: Agent 1** |
| **Issue #5** | `OPEN` @ `2026-10-11T20:06:48Z` | مأموریت این نسخه: GitHub Truth + Governance Repair + Continuous Handoff | **باز — مالک: Agent 2** (این سند با اجرای آن ساخته شد) |
| **PR #6** | **MERGED** در `2026-10-12T06:47:37Z` · squash merge commit `23ee54392fcc35be9d2cef94a5af7ba15741c4c6` · head پیش از merge `948d5782569063468f95143671fef956838fb27a` | هندآف v2.2 + GOV-PP-01 v1.1 + اصلاح شواهد REG-AR + آرشیو/مانیفست | **ادغام شد**؛ F1/F3/F4 اصلاح شدند، CLI (F2) صرفاً به PO ارجاع شده و تصمیم محصولی/مجوزی جداگانه می‌خواهد. Issue #5 همچنان باز است؛ ثبت گزارش در آن با 403 انجام نشده است.

> **تفکیک حیاتی:** ادغام PR ≠ Acceptance رسمی ≠ G3. `main` اکنون حاوی WP-1.3 است؛ این هیچ ستون Acceptance را پر نمی‌کند (بند ۲.۴).

### ۲.۳ وضعیت WPها و Acceptance (از REG-WPR/REG-AR خوانده‌شده + برچسب)

| لایه | واقعیت | برچسب |
|---|---|---|
| **WP-1.1** | CLOSED — IMPLEMENTED؛ 8/8 AC PASS؛ **G3 PASS فاز P1 (2026-10-01)** — تنها G3 ثبت‌شده | `ثبت‌شده` |
| **WP-1.2** | IMPLEMENTED (2026-10-09)؛ 4/4 AC PASS در سطح **TM (T-1.2.4)**؛ **در انتظار Acceptance رسمی PO** | `ثبت‌شده` |
| **WP-1.3** | IMPLEMENTED و **ادغام‌شده در `main`** (PR #2)؛ 4/4 AC PASS «Pending — TM review» تحویل‌دهنده Agent 1؛ بازبینی Agent 2 مستقللاً B1/M1 را یافت و رفع کرد (بند ۳) → **Acceptance رسمی PO/TM ثبت نشده؛ پیشنهاد: TM روی head رفع‌شده دوباره AC-1.3.4 را تأیید کند** | `ثبت‌شده` + `اجراشده` (رفع) |
| **WP-7.1** | **ACCEPTED/FROZEN** (2026-10-08 — PO) — تنها WP با Acceptance ثبت‌شده علاوه بر WP-1.1 | `ثبت‌شده` |
| سایر P2..P12 | همه `IMPLEMENTED` (یا FROZEN مثل WP-4.1) و **در انتظار Acceptance** — REG-WPR امروز **۱۹ ارجاع** «در انتظار Acceptance» دارد (`اجراشده` با grep) | `ثبت‌شده` |
| **WP-12.3** | **DEFERRED** — Ratification آستانه‌ها = PO/G4 (D-07/D-08) | `ثبت‌شده` |
| G3 فازهای P2..P12 | **هیچ G3 فازی اعلام نشده** — فقط P1 (2026-10-01) | واقعیت |
| قاعده | **PASSِ تست ≠ Acceptance ≠ ادغام.** Acceptance فقط ستون ثبت‌شدهٔ PO/TM در REG-AR است. | — |

### ۲.۴ آرشیو / MANIFEST / SHA-256 این تحویل

طبق GOV-PP-01 بند ۴، تحویل این مأموریت: `deliveries/issue-5/` (آرشیو کامل درخت + `MANIFEST-SHA256.txt` + README با `ARCHIVE-SHA-256`) — hashها در همان پوشه و در commentهای همین PR ثبت شده‌اند؛ **ثبتِ آن‌ها در Issue #5 با اتصال فعلی HTTP 403 شد و انجام نشده است** (بلوک انتقالِ دستی: GOV-PP-01 v1.1 بند ۱/الف). پوشش‌دهی: درختِ کاملِ محتوا؛ commit انتشار فقط metadata است (غیررکورسیو — توضیح در README پوشه).

---

## ۳. B1 و M1 — یافته، رفع، اثبات حضور در `main`

- **B1 (BLOCKER) — URI فقط‌خواندنی:** `src/capture/consistency.py` مسیرِ دارای `?`/`#`/`%` را بدون کدگذاری می‌گذاشت → بازشدن فایلِ اشتباه + گم‌شدن `mode=ro`. **رفع:** `quote(Path(db_path).resolve().as_posix(), safe="/") + "?mode=ro"` در `_open_read_only` (الگوی `src/holoo_spike/store.py`) + ۴ تست رگرسیون در `test_wp13_consistency.py`. **اثبات حضور در `main`:** خواندن `origin/main:src/capture/consistency.py` → `uri = "file:" + quote(…)` در خط ۱۲۸ (`اجراشده`).
- **M1 (MAJOR) — الگوریتم خارجی:** رکورد با `s1_algorithm_id` غیر از `sha256-v1` نباید `ELIGIBLE_CANDIDATE` شود. **رفع:** `evaluate_retention` → `INTEGRITY_DEFERRED` با detail صریح + قرارداد §3/§5/§9 «Amended» + تست `test_foreign_algorithm_record_is_deferred_not_eligible`. **اثبات حضور در `main`:** `origin/main:src/capture/retention.py` → بند `R4b foreign s1_algorithm_id → INTEGRITY_DEFERRED` (خط ۲۸۷ و مسیر اجرایی خط ۳۴۳) (`اجراشده`).
- **گاز زدن تست‌ها (`اجراشده`):** ۵ تست جدید/تغییریافته روی `0b073c9` (پیش از رفع) FAILED و روی کد رفع‌شده PASSED.
- زنجیرهٔ انتشار: `0b073c9` → `25565e8` (رفع، شاخهٔ Agent 2) → انتقال به head PR #2 → **MERGED در `main`**.

## ۳.۳ شواهد تست — قابل انتساب به SHA (`اجراشده`)

محیط: Python 3.11.2 · pytest 9.1.1 (`/tmp/kandoo-review-venv`) · اجرا روی head این شاخه که **درختش با `main@77edafa` بایت‌به‌بایت یکسان است** (`git diff 77edafa… HEAD` = ۰ خط — `اجراشده`)؛ کد در کل تحویل تغییر نمی‌کند (diff نهایی در بدنهٔ PR دوباره تأیید می‌شود).

| Evidence | خروجی واقعی |
|---|---|
| شش فایل WP-1.3 | **130 passed** in 2.16s |
| کل پکیج `capture` | **220 passed** in 3.91s |
| رگرسیون کامل مخزن | **1606 passed, 0 failed** in 179.38s (۱۴۷۶ baseline + ۱۳۰ ✓) |
| Smoke (`run_smoke_retention_recovery.py` در دایرکتوری تازه) | **SMOKE OK** — ۸ مرحله cold-start، exit 0 |
| `python -m compileall -q .` | exit 0 |
| سابقهٔ مستقل روی `0b073c9` (بازتولیدِ ادعاهای تحویل اولیه) | 125 / 215 / **1601/0** (167.51s) / smoke 8/8 — حساب `1476+125=1601` ✓ |

فرمان‌های بازتولید (ریشهٔ مخزن):

```bash
python3 -m venv /tmp/k && /tmp/k/bin/pip install -q pytest
cd src && /tmp/k/bin/python -m pytest capture/tests/test_wp13_*.py -q     # 130
cd src && /tmp/k/bin/python -m pytest capture/tests/ -q                   # 220
cd src && /tmp/k/bin/python -m pytest -q                                  # رگرسیون کامل
cd src && /tmp/k/bin/python run_smoke_retention_recovery.py /tmp/s1       # SMOKE OK
cd src && /tmp/k/bin/python -m compileall -q .                            # exit 0
```

---

## ۴. DEFها — وضعیت واقعی (`registers/deferred-decision-register.md` بایت‌به‌بایت بدون تغییر از `80d7c73` — `اجراشده`)

| DEF | وضعیت | مفهوم |
|---|---|---|
| **DEF4** | `DEFERRED` | مقادیر retention/privacy/TTL هرگز حدس نمی‌شوند؛ **حذف فیزیکی مسدود است**: `request_purge` فقط `PURGE_GATE_BLOCKED` (`executed=False`، `rows_affected=0`؛ AST+تست)؛ همهٔ خروجی‌ها `DEF4-PENDING` |
| **DEF5** | `DEFERRED` | ارائه/قالب Digital Invoice بازنشده (WP-10.2) |
| **DEF6** | `DEFERRED` | نگاشت فیلدهای Modian بازنشده (WP-11.2) |
| سایر | `DEFERRED` | DEF1/DEF2/DEF3/… طبق REG-DDR؛ باز کردن = تصمیم PO |

---

## ۵. تصمیم‌های Frozen (تغییر = فقط مسیر STOP)

| شناسه | قاعدهٔ binding (خلاصه) |
|---|---|
| **D-02 / D-03** | هویت‌ها (S1/S2/invoice_id) و `sha256-v1`؛ `S1` تنها idempotency سطح Capture؛ dedup جدید ممنوع |
| **D-06/DEF3 · AD-03/DEF1** | ساخت خودکار Customer ممنوع؛ هیچ اثر خودکار Sale/Inventory از External Capture |
| **D-07/D-08/WP-12.3** | آستانه‌ها placeholder؛ ratification = PO/G4 |
| **AS-01..AS-04** | خط لوله و state ماشین‌ها/fیلدها از مرجع Frozen؛ هیچ state جدید در سطح WP ممنوع |
| **D-09 + Golden Rule** | پس از Freeze: بدون انتخاب OCR/VLM/DB جدید، بدون Migration معماری، بدون باز کردن DEFها؛ بدون مجوز TM فایل فروزن دست نمی‌خورد |

اصل «مقدار ناشناخته ≠ مقدار قطعی»: بدون ورودی سیاست → `NOT_EVALUATED` / `UNRESOLVED` / `DEF4-PENDING` — هرگز صفر یا «منطقی».

---

## ۶. یافته‌های بازِ بازبینی (غیر از B1/M1 که بسته شدند)

| یافته | خلاصه | وضعیت |
|---|---|---|
| suffix هماهنگ زنجیر | حذف هم‌زمان ردیف+anchor قابل‌تشخیص نیست — wording قرارداد §7 اغراق (طراحی class-inherented) | `باز` — پیشنهاد کلامی به TM |
| کدگذاری `\n` در fingerprint | boundary فیلدها با newline قابل جابه‌جایی | `باز` — WP آتی |
| age زیر-ثانیه / snapshot ناکامل / blank policy / KeyError خام | چهار MINOR جزئی (typede fail-closed در همه) | `باز` — جزئی |
| مسیرهای `kandoo/` | ۲۳۲ ارجاع در registers+README (`اجراشده` با grep روی `main`) | `باز` → اقدام ۸.۴ |
| تست تاریخ‌حساس `test_ir_provenance` | شکست قطعی فقط در روز مطلق `2026-10-08` (گذشته؛ fixture سالانه نیست — تصحیح نسخهٔ ۱)؛ فایل Frozen = مجوز TM | `باز` |
| observation هم‌زمانی recovery↔ingest | رفتار تایپ‌دار ناخوشایند، نه defect (INV-C6 برقرار) | `باز` |

---

## ۷. تناقض‌های یافت‌شده در ممیزی Issue #5 و تکلیف هرکدام

| # | ادعا/فایل | واقعیت GitHub (`اجراشده`) | اقدام |
|---|---|---|---|
| ۷.۱ | هندآف نسخهٔ ۲.۰ (روی `main`): `main = de38db0…`، PR #3 باز | `main = 77edafa…` (تک‌commit)؛ PR #3 MERGED | **اصلاح شد** — همین نسخه ۲.۱ |
| ۷.۲ | REG-WPR: «WP-1.3 IN-BRANCH / ادغام انجام نشده» (۳ سطر) | PR #2 MERGED؛ محتوا در `main` (بند ۳) | **اصلاح شد** — سطرهای وضعیت + Reconciliation تاریخی |
| ۷.۳ | REG-WPR Tests: «125 / 1601» بدون تفکیک نسخه | 125/1601 مربوط `0b073c9` (اجراشده)؛ نسخهٔ نهایی 130/1606 | **اصلاح شد** — تفکیک انتساب |
| ۷.۴ | REG-AR AC-1.3.1: فهرست تست‌ها بدون تست رفع M1 | قرارداد §9 تست را به AC-1.3.1 گره می‌زند | **اصلاح شد** — نام تست به ستون evidence افزوده شد؛ ستون تصویب دست‌نخورده (Pending) |
| ۷.۵ | `AGENT_HANDOFF.md` §6–§9: «درخت ۲۸۱ فایلی هنوز transfer نشده»، «bootstrap انجام نشده» | **۲۹۷ فایل در `main`**؛ bootstrap از `80d7c73` یکپارچه بود؛ اکنون WP-1.3+هندآف هم هست | **ثبت شد — دست‌نخورده**: PR #1 باز این فایل را ویرایش می‌کند (GOV-PP-01 بند ۶) → تکلیف: بند ۷.۹ |
| ۷.۶ | `KANDOO_AGENT_COORDINATION.md`: «implementation tree integrated نیست» + ZIP `b8cda029…`/281 فایل | درخت integrated است؛ ZIP = `گزارش‌شده` (بستهٔ تاریخی خارج از repo، قابل راستی‌آزمایی درون‌مخزنی نیست) | **ثبت شد — دست‌نخورده** (همان قید PR #1) |
| ۷.۷ | ادعاهای `MANIFEST-SHA256.txt` در REG-TASK برای WP-5.1..7.2 | artifact در repo موجود نیست → **`گزارش‌شده` (تاریخی)**؛ قابل تأیید مجدد نیست | برچسب‌گذاری شد؛ از این پس GOV-PP-01 بند ۴ اجباری است |
| ۷.۸ | بازنویسی تاریخچهٔ `main` (نکتهٔ مرجعیت SHA) | `de38db0`/`80d7c73` والدِ `main` نیستند؛ `integration/wp-1.3-retention-recovery` @ `80d7c73` محفوظ | ثبت در ۲.۱ + REG-WPR (بند ۸) — با `is-ancestor` اثبات‌پذیر |
| ۷.۹ | PR #1 (باز): بازنویسی reconش `2026-10-08` + ادعای «WP-1.3 اجرا نشده» + روایت ZIP (بدنه: «تحویل ZIP + manifest 291 فایلی دریافت شد») | WP-1.3 اکنون در `main` ادغام‌شده؛ روایت ZIP تاریخی/`گزارش‌شده` | **توصیه (بدون merge/close — فقط PO):** rebase روی `77edafa` + حذف/به‌روزرسانی ادعاهای WP-1.3 و bootstrap یا بستن به‌عنوان superseded + ثبت تکلیف در Issue #5 |
| ۷.۱۰ | آستانهٔ «Python 3.12+» در `src/README.md` | اجرای سبز روی 3.11.2 | `باز` — سند یا اجرا (مالک: TM/Agent 1) |
| ۷.۱۱ | ادعای «۱۷ بند در انتظار» نسخهٔ قبلی هندآف | شمارش امروز REG-WPR: **۱۹ ارجاع** «در انتظار Acceptance» | اصلاح عدد + ارجاع به grep |
| ۷.۱۲ | بازبینی PR #6 — **F1**: GOV-PP-01 ثبت در Issue را اجباری می‌کرد، ولی `POST …/issues/…/comments` با دسترسی ایجنت = **HTTP 403** | **تعیین تکلیف 2026-10-12:** GOV-PP-01 **v1.1 بند ۱/الف** — fallback حسابرسی (سندِ رکورد در PR + بلوک قابل‌کپی برای انتقال توسط PO/TM + شاهد endpoint/status/UTC) و **ممنوعیتِ صریحِ ادعای «ثبت در Issue»**؛ شاهدِ «گزارش در Issue» تا انتقال واقعی **UNMET** |
| ۷.۱۳ | بازبینی PR #6 — **F2**: محدودهٔ CLI هیچ سند مرجعی ندارد (D-09 فقط Freeze معماری است؛ قراردادها/AGENT docs/README ساکت‌اند) | **REFERRRED TO PO/TM** — GOV-PP-01 v1.1 بند ۱/ب فقط واقعیت را ثبت کرده؛ **نه «مجاز» و نه «ممنوع» اعلام شد** (هر تفسیر منتظر تصمیم PO/TM) |
| ۷.۱۴ | بازبینی PR #6 — **F3/F4**: شمارش‌های evidence در REG-AR (retention ۳۵ / consistency ۲۶) از فایل‌های واقعی (۳۶/۳۰) عقب بود | **اصلاح شد 2026-10-12** — با حفظ سابقهٔ تغییر در همان سلول‌ها (`۳۵+۱ رفع`، `۲۶+۴ رفع`)؛ `--collect-only` بازبینی: retention=36، consistency=30 |

---

## ۸. اقدامات بعدی — مالک + شاهد بستن

| # | اقدام | مالک | شاهد بستن |
|---|---|---|---|
| ۸.۱ | مأموریت **Issue #4** (MVP Reality Audit + اجرای اولین شکاف) | Agent 1 | PR لینک‌دار + پاسخ در Issue #4 |
| ۸.۲ | بررسی/تکلیف **PR #1** طبق توصیهٔ ۷.۹ (merge/close فقط دستور PO) | TM/PO | وضعیت نهایی PR #1 در GitHub |
| ۸.۳ | **بستن Issue #5** پس از پذیرش گزارش تحویل (PR + شواهد + archive/manifest + هندآف + next action — GOV-PP-01 بند ۱۰) | TM/PO | Issue #5 بسته‌شده + لینک گزارش |
| ۸.۴ | پاک‌سازی ۲۳۲ ارجاع `kandoo/` در PR مستندات‌محور جدا | Agent 1 / TM | `git grep -E 'kandoo/(specs\|src\|baseline)' main -- 'registers/*.md' 'README.md' \| wc -l` = 0 |
| ۸.۵ | commit اسناد `baseline/` (MNT-1/RSK-2؛ deadline گذشته) | PO/TM | فایل‌ها در `main` + به‌روزرسانی RSK-2 |
| ۸.۶ | Acceptance رسمی WPهای منتظر (1.2/1.3/…) و G3 فازهای بعدی | PO (توصیهٔ TM) | ستون‌های REG-AR/REG-WPR به‌روز |
| ۸.۷ | اجرای GOV-PP-01 در همهٔ تحویل‌های آینده (archive+manifest+SHA) | همهٔ ایجنت‌ها | deliveries/ در هر PR سورسی |
| ۸.۸ | تصمیم ۶ (تست تاریخ) و observation هم‌زمانی | TM → PO در صورت لمس فروزن | ثبت در REG-RR/REG-WPR |
| ۸.۹ | تصمیم‌های DEF4/5/6، WP-12.3، D-07/D-08 | PO | ثبت در REG-DDR/REG-DR |

---

## ۹. پروتکل همکاری + بازیابی جلسهٔ تازه

۱) Agent 1 = سورس/تست (Issue #4) · ۲) Agent 2 = governance/handoff/review (Issue #5) · ۳) تغییر هم‌زمان روی یک فایل ممنوع (GOV-PP-01 بند ۶) · ۴) هر تحویل = branch مستقل از HEAD واقعی `main` + commit + PR + شواهد + archive/manifest/SHA + هندآف همگام (GOV-PP-01 بندهای ۱–۱۰) · ۵) merge فقط با دستور PO؛ Acceptance فقط ثبت PO/TM؛ `main` = منبع حقیقت · ۶) پس از هر merge/بازنویسی تاریخچه، SHAها را دوباره با `ls-remote` بگیرید، نه از این سند.

### پرامپت آمادهٔ کپی برای جلسهٔ جدید

```text
You are resuming as Technical Manager for Kandoo Digital Invoice.

Repository: majid-ghanbari-dost/Kandoo-Digital-Invoice — repository is the
source of truth; do not trust chat history.

First read: PROJECT_CONTINUITY_HANDOFF.md (v2.1), PUBLICATION_PROTOCOL.md
(GOV-PP-01, mandatory), README.md, then registers/*.md.

Then verify LIVE state before trusting anything:
  git ls-remote origin
  gh pr list --state all
  gh pr view 1 --json state,headRefOid,mergeable
  gh issue view 4 --json state
  gh issue view 5 --json state

Known live state after PR #6 merge — recorded 2026-10-12T06:47:37Z (re-verify before next release):
  main = 23ee54392fcc35be9d2cef94a5af7ba15741c4c6 (squash merge of Agent 2 PR #6).
  PR #6 MERGED; governance delivery is on main. No product source files changed by PR #6.
  PR #1 OPEN (governance docs only, head b3c6194…; overlaps no files with PR #6; do not merge/close until its own review and explicit disposition).
  PR #2 MERGED 2026-10-11T19:28:01Z; WP-1.3 source/fixes present in main.
  PR #3 MERGED 2026-10-11T19:30:20Z; prior handoff superseded.
  Issue #4 OPEN (Agent 1 — source/tests owner). Agent 1's MVP pipeline is NOT yet on GitHub in a reviewable PR; latest delivery is textual/local only, based on the agent's report. The 19-file package and tests are reported, not independently verified here.
  Issue #5 OPEN (Agent 2 — governance). Agent 2's original comment attempt failed with HTTP 403, but TM subsequently transferred the delivery report to a real Issue #5 comment: https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/issues/5#issuecomment-6119226926.
  Reported test evidence from Agent 2 on the prior main tree: WP-1.3 130 passed, capture 220 passed, full regression 1606 passed, smoke OK, compileall 0. No CI/check-runs are configured on the PR; these are agent-local execution results.

Preserve Frozen decisions (D-01..D-09, AD-*, AS-*) and DEF1..DEF6 — DEF4 stays
DEFERRED, no policy values, physical deletion stays blocked. Never edit frozen
files or Agent 1's source/tests without authorization. Never merge without PO
order; PASS in tests is not Acceptance. Start by re-verifying live state and
reporting the next three actions from handoff section 8.
```

---

```text
پایان سند — نسخه ۲.۴. این سند مستندات‌محور است: هیچ کد/تست/Frozen/DEF تغییر نکرده؛
REGISTER فقط سطرهای وضعیتِ زنده را با reconciliation تاریخی اصلاح کرده (بند ۷).
SHA-256 نسخهٔ نهایی این فایل در پیام commit این به‌روزرسانی ثبت می‌شود؛
ثبت در Issue #5 طبق GOV-PP-01 v1.1 بند ۱/الف فقط با انتقالِ واقعیِ PO/TM برقرار می‌شود.
هر ادعای «اجراشده» با فرمان‌های بند ۳.۳ قابل بازتولید است؛ باقی برچسب دارند.
```

---

## پیوست ۲۰۲۶-۱۰-۱۲ (UTC) — به‌روزرسانی از جلسهٔ پیاده‌سازی Issue #4 (اتصال GitHub فعال)

> این پیوست **الحاقی** است و متن نسخهٔ ۲.۴ بالا را بازنویسی نمی‌کند؛ اظهارهای
> پایان سند بالا مربوط به همان نسخه/تاریخ خودش است. نویسندهٔ این پیوست: جلسهٔ
> پیاده‌سازی Agent 1 (مأموریت Issue #4 — مالکیت `src/**` + تست محصول). فایل‌های
> تحت مالکیت PR #1 (`AGENT_HANDOFF.md`, `KANDOO_AGENT_COORDINATION.md`) دست‌نخورده‌اند.

برچسب‌ها طبق قاعدهٔ همین سند: `اجراشده` = خروجی واقعی همین سندباکس.

**۱) حقیقت زندهٔ GitHub (`اجراشده`، همین جلسه):** `main` =
`2d61b4dd61837810134cfcd97df8e7d4c0eba9b0` (سرِ `main` با merge commit مربوط به PR #9
یکسان است — بررسی‌شده). PR #9 (`feat(pipeline): PO-authorized verified
capture-to-canonical composition`) **MERGED** در `2026-10-12T09:00:59Z`؛ Issue #4
**OPEN** (آخرین به‌روزرسانی `2026-10-12T09:07:13Z`). تنها PR باز: **PR #1**
(حکمرانی؛ فقط `AGENT_HANDOFF.md` + `KANDOO_AGENT_COORDINATION.md`).

**۲) تحویل جدید این جلسه (`اجراشده`):** شکاف انتخابی = **Digital Issuance
composition** (اتصال دو نیمهٔ موجود: `pipeline` → `digital_invoice`). بستهٔ افزودنی
`src/issuance/` + `src/run_smoke_issuance.py` (بیست‌ودومین smoke) ساخته و تست شد:

- سورسِ تست‌شده: `93e1c6e8b3e225f4351cf87214307ec98431d673` (tree
  `6707f9eb165d63bb5b3058198715e9e55f90ec1f`)، شاخه
  `arena/5fbd6749-kandoo-digital-invoice` (پایه = `main` تأییدشده).
- focused: `pytest src/issuance/tests` → **29 passed** (7.27s)؛ رگرسیون کامل →
  **1683 passed** (183.96s؛ حساب additive: 1654 + 29 = 1683، صفر شکست جدید)؛
  **همهٔ 22 smoke runner** → `EXIT_CODE=0` (شامل smoke جدید با ۸ گام).
- گزارش: `specs/ISSUE-4-issuance-composition-report.md`؛ شواهد خام و archive/manifest
  زیر `deliveries/issue-4-issuance/` در همان PR.
- مرزها: هیچ حالت/واژه/سیاست/CLI/purge/presentation جدید؛ DEF1–DEF6 بازنشده؛ هیچ
  فایل سورس/تست موجودی تغییر نکرد (ویرایش‌ها فقط مستندات/رجیستری/هندآف).

**۳) وضعیت ثبت‌ها (`اجراشده`):** `registers/task-register.md` (T-APP-1)،
`registers/acceptance-register.md` (بلوک checks مشتق‌شده — **ثبت Acceptance نیست**)،
`registers/work-package-register.md` (APP-ISS — افزایش سطح کاربرد، نه WP جدید)،
`src/README.md` (بخش لایهٔ جدید) و همین پیوست به‌روز شدند. Decision Register و
Deferred Decision Register **تغییر نکردند**.

**۴) اقدام بعدی:** بازبینی TM روی PR (شواهد، مرزها، archive/manifest/SHA)؛
**merge/Acceptance فقط با دستور صریح PO** و تا آن زمان این تحویل «IMPLEMENTED — در
PR باز» است. شکاف‌های باقی‌ماندهٔ MVP که به تصمیم PO/TM نیاز دارند (نه افزایش
Agent): اپ‌های Windows/Android، نقش‌ها/onboarding (DEF2)، ثبت کالا/موجودی روی جریان
Native (AS-02 بدون قرارداد پیاده‌سازی → STOP)، ارائه/تحویل رسید (DEF5)، adapter
POS/Holoo/Modian (DEF6/WP-11.2)، سیاست نگهداری (DEF4)، محدودهٔ CLI (D-09)،
ratification آستانه‌ها (WP-12.3).
