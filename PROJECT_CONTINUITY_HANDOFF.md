# Kandoo Digital Invoice — PROJECT CONTINUITY HANDOFF

```text
نوع سند:        Handoff تداوم پروژه (بازسازی‌شده بر اساس حقیقت تازهٔ GitHub)
نسخه:           2.0 (جایگزین نسخهٔ 1.0 شاخهٔ docs/project-continuity-handoff)
تاریخ:          2026-10-11
نویسنده:        Agent 2 — بازبین مستقل و مسئول تکمیل (شاخهٔ جلسه: arena/a776e4f2-kandoo-digital-invoice)
وضعیت:          مستند/حکمرانی؛ هیچ فایل Frozen، Register یا DEF4 در بازسازی تغییر نکرد
مبنای داده‌ها:   بررسی زندهٔ GitHub + اجرای واقعی تست در همین سندباکس (۲۰۲۶-۱۰-۱۱)
آدرس‌رسانی:     نسخهٔ به‌روزشده در شاخهٔ docs/project-continuity-handoff و PR #3 قرار دارد.
```

> **برچسب‌های ادعا (الزامی برای همهٔ خوانندگان):**
> `اجراشده` = خروجی واقعی همین سندباکس، قابل بازتولید با فرمان‌های همین سند ·
> `گزارش‌شده` = ادعای ایجنت/سند دیگر که خودم اجرا نکرده‌ام ·
> `ثبت‌شده` = ادعای Register/سند، لزوماً واقعیت مخزن نیست ·
> `باز` = بدون تصمیم. هیچ ادعای اجرا‌نشده‌ای «قطعی» نمی‌شود.

---

## ۱. هویت پروژه، نقش‌ها، پروتکل

**Kandoo Digital Invoice**: خط توسعهٔ دریافت/نگهداری/پردازش قابل‌ردیابی سند و فاکتور دیجیتال (Holoo/POS capture ← Canonicalization). جریان رسمی External (AS-01، Frozen): `External POS/Holoo → Capture → Reconstruction → Extraction → Normalization → Canonicalization Gate → Validation → Invoice → Digital Invoice`. مخزن stdlib-only (SQLite embedded، بدون شبکه)، ۱۷ package در `src/`.

| نقش | مسئولیت | مرز |
|---|---|---|
| **Product Owner (کاربر)** | تصمیم محصولی، Acceptance رسمی، مجوز ادغام در `main`، ratification (D-07/D-08)، باز کردن DEFها | تنها صاحب تصمیم‌های Frozen |
| **Technical Manager** | ابلاغ مأموریت، بازبینی شواهد، توصیهٔ Acceptance، تکلیف PRها | تصمیم معماری جدید فقط از مسیر STOP |
| **Agent 1 — پیاده‌سازی** | پیاده‌سازی + شواهد اجراشده + commit/push روی شاخهٔ خود | ادغام بدون دستور صریح ممنوع |
| **Agent 2 — بازبین/تکمیل** | بازبینی مستقل، راستی‌آزمایی ادعاهای ایجنت‌ها، تکمیل موارد مجوزدار | ادعای «تأیید شد» فقط با اجرای خودش؛ هم‌زمانی ویرایش با ایجنت دیگر ممنوع |

**پروتکل توقف (همیشه):** هر تصمیم تعریف‌نشده → `STOP → Issue Report → TM Review → PO Decision` (D-09). **قاعده طلایی:** هیچ ویرایش فایل/تست Frozen بدون مجوز صریح TM. **قاعدهٔ ادغام:** هرگز merge، PASS شدن تست، Acceptance یا تغییر GitHub را بدون شاهد اعلام نکنید.

---

## ۲. حقیقت زندهٔ GitHub (۲۰۲۶-۱۰-۱۱ — `اجراشده` با `gh`/`git` در این سندباکس)

### ۲.۱ SHAها

| مورد | مقدار | وضعیت |
|---|---|---|
| `main` | **`de38db0dc0e66158028b823aaffd6facd3fd1fc5`** | `تأییدشده` — PR #2 با squash merge ادغام شد؛ این SHA باید با `git ls-remote origin refs/heads/main` دوباره قابل تأیید باشد |
| head PR #1 | `b3c6194b6f1b3f5e2c9aeabab688d50463bb41b9` | `اجراشده` |
| PR #2 head پیش از ادغام | `25565e8f5ab74297ca6a9fdd18c38efbf5416381` | `تأییدشده` — شامل fixهای B1/M1؛ ادغام با commit `de38db0dc0e66158028b823aaffd6facd3fd1fc5` |
| head PR #3 | `d1cb3b3b17c262eb8158b94f142c717e25e040e3` (سند v2.0 ثبت‌شده؛ این نسخه به‌روزرسانی می‌شود) | `اجراشده` — شاخهٔ سند مستقل از کد |
| commit تکمیل (B1/M1) | **`25565e8f5ab74297ca6a9fdd18c38efbf5416381`** | `تأییدشده` — در PR #2 ادغام شد و اکنون در `main` است |
| محتوای `main` | WP-1.3 اکنون در `main` است؛ شمارش فایل‌ها باید از HEAD جاری استخراج شود | `اجراشده` — PR #2 ادغام شده |
| `baseline/` | **غایب** | `اجراشده` — MNT-1/RSK-2 همچنان باز است |

### ۲.۲ PRها — وضعیت قطعی

| PR | head (شاخه @ SHA) | وضعیت GitHub | تغییرات | تکلیف |
|---|---|---|---|---|
| **#1** | `arena/7bee5f10-kandoo-digital-invoice` @ `b3c6194…` | `OPEN` · `MERGEABLE` · `CLEAN` · ادغام‌نشده | فقط ۲ سند حکمرانی (`AGENT_HANDOFF.md`، `KANDOO_AGENT_COORDINATION.md`)، صفر سورس؛ بدنه‌اش ادعاهای متناقض artifact دارد (بند ۷.۶) | **باز** — این سند را لمس نکرد |
| **#2** | `arena/23993033-kandoo-digital-invoice` @ `25565e8…` | **MERGED** · merge commit `de38db0dc0e66158028b823aaffd6facd3fd1fc5` | ۱۸ فایل، +4495/−13 — سورس WP-1.3 به‌همراه رفع B1/M1 | **ادغام‌شده**؛ تست‌های نسخه اصلاح‌شده در بند ۳.۳ گزارش شده‌اند |
| **#3** | `docs/project-continuity-handoff` @ `9a2a3d0…` (بازنویسی می‌شود تا بر مبنای main باشد) | `OPEN` · mergeability پس از بازپایه‌گذاری بررسی شود | **فقط** `PROJECT_CONTINUITY_HANDOFF.md` | **باز — هندآف به‌روزشده؛ ادغام پس از تأیید diff** |

 > **تفکیک مهم:** `main` شامل WP-1.3 پس از ادغام PR #2 است. ادغام به‌تنهایی Acceptance رسمی PO/TM یا G3 را اثبات نمی‌کند.

### ۲.۳ وضعیت پذیرش WP-1.3 (مرز تست ↔ Acceptance)

| لایه | واقعیت | برچسب |
|---|---|---|
| شواهد تست | سبز روی head PR #2 **و** سبز روی نسخهٔ تکمیل‌شده (بند ۳.۳) | `اجراشده` |
| ردیف REG-AR | `AC-1.3.1..4 = PASS` با ستون تصویب `Pending — TM review` | `ثبت‌شده` |
| Acceptance رسمی PO/TM | **انجام نشده است** — ستون Accepted خالی است | واقعیت |
| G3 / ادغام P1 | **اعلام رسمی G3 هنوز ثبت نشده است**؛ کد WP-1.3 در `main` است | واقعیت |
| قاعده | **PASS شدن تست ≠ Acceptance.** سبز شدن suite فقط شرط لازم است؛ Acceptance با ثبت صریح TM/PO و ادغام با دستور صریح انجام می‌شود. | — |

---

## ۳. اجرای مأموریت تکمیل (این سندباکس) — B1 و M1

### ۳.۱ یافته B1 (BLOCKER) — ساخت URI فقط‌خواندنی

- **ایراد (پیش از رفع، روی `0b073c9`):** `src/capture/consistency.py` تابع `_open_read_only` مسیر را بدون کدگذاری در `f"file:{db_path}?mode=ro"` می‌گذاشت. مسیرِ دارای `?`/`#`/`%` باعث می‌شد URI در اولین `?` بشکند: اتصال به **فایل اشتباهِ** پیشوند باز شود (گزارشِ ساکت غلط) و پارامتر `mode=ro` **گم** شود (اتصال عملاً read-write).
- **اثبات روی کد قدیمی (`اجراشده`):** دیتابیس هدف با ۱ رکورد COMPLETED در مسیر `cap?main…` → گزارش `records_total=0` (تحلیل فایل غلط)؛ الگوی همان URI یک `UPDATE` را پذیرفت (read-only از دست رفته)؛ پیشوندِ غلط در حالت rw **ایجاد** می‌شد.
- **رفع (`اجراشده`):** percent-encoding مسیر با الگوی مستقر مخزن (`src/holoo_spike/store.py` — `read_only_uri`): `quote(Path(db_path).resolve().as_posix(), safe="/") + "?mode=ro"` در `_open_read_only` (همان تابع، هر سه بازشدن capture/dup-keys/journal را پوشش می‌دهد). به‌روزرسانی مستند §10 OD-RT-F در قرارداد.
- **تست‌های رگرسیون (۴ تست تازه در `src/capture/tests/test_wp13_consistency.py`):**
  `test_metacharacter_path_reads_the_intended_database` ·
  `test_metacharacter_path_never_creates_the_parsed_away_prefix_file` ·
  `test_read_only_connection_rejects_writes_for_metacharacter_paths` (INSERT/UPDATE/DELETE هر سه رد SQLite + پایداری بایت فایل) ·
  `test_metacharacter_journal_path_is_read_correctly`
- **گاز زدن تست‌ها (`اجراشده`):** هر۴ تست + تست M1 روی کد `0b073c9` **FAILED** و روی کد رفع‌شده **PASSED** — یعنی تست‌ها واقعاً ایراد را می‌گیرند، تزیینی نیستند.
- **وضعیت نهایی:** **رفع‌شده و در `main` ادغام‌شده** با PR #2 (merge commit `de38db0…`).

### ۳.۲ یافته M1 (MAJOR) — الگوریتم fingerprint ناشناخته

- **ایراد:** قرارداد §2.8 می‌گوید رکورد با `s1_algorithm_id` خارجی «هرگز eligible/ineligible فرض نشود»، اما gate چنین رکوردی را `ELIGIBLE_CANDIDATE` می‌کرد (تست `test_foreign_fingerprint_algorithm_is_surfaced_not_resolved` رفتار غلط را cement کرده بود: `candidates == 1`).
- **رفع (`اجراشده`):** در `src/capture/retention.py` — `evaluate_retention` پس از بررسی `integrity FAILED`، اگر `record.s1_algorithm_id` مقداری غیر از `sha256-v1` داشته باشد → **`INTEGRITY_DEFERRED`** (همان وضعیت deferred امنِ موجود؛ بدون هیچ واژگان/state جدید) با detail صریح؛ `age_seconds` هرگز محاسبه نمی‌شود. رکورد با binding فروزن دست‌نخورده از eligibility عبور می‌کند.
- **هماهنگ‌سازی قرارداد (`اجراشده`):** §3 (ردیف `INTEGRITY_DEFERRED`)، §5 (ترتیب refusal — بند صریح «foreign → INTEGRITY_DEFERRED»)، §9 (نام تست تازه به AC-1.3.1 گره خورد: `test_foreign_algorithm_record_is_deferred_not_eligible`)، شرح header «Amended».
- **تست‌ها:** تست تازهٔ gate (`test_foreign_algorithm_record_is_deferred_not_eligible`) + بازنویسی تست گزارش (`candidates==0`، `refused==1`، `candidate_capture_ids==[]`، finding پابرجا).
- **وضعیت نهایی:** **رفع‌شده و در `main` ادغام‌شده** با PR #2 (merge commit `de38db0…`).

### ۳.۳ شواهد تست — نسخهٔ نهایی این سندباکس (`اجراشده`)

محیط: Python 3.11.2 · pytest 9.1.1 در venv خارج از مخزن · بدون وابستگی تازه.

| Evidence | خروجی واقعی |
|---|---|
| تست‌های متمرکز WP-1.3 (۶ فایل) | **130 passed** in 2.22s (۱۲۵ قبلی + ۵ تست تازه/بازنویسی‌شده) |
| کل پکیج `capture` | **220 passed** in 2.94s (۹۰ فروزن + ۱۳۰ WP-1.3) |
| رگرسیون کامل مخزن | **1606 passed, 0 failed** in 191.69s (۱۴۷۶ baseline + ۱۳۰ ✓) |
| Smoke ×۲ (دایرکتوری تازه) | **SMOKE OK — 8/8 steps, exit 0** هر دو بار |
| `python -m compileall` (src) | exit 0 |
| مقایسه با baseline | `git diff --name-only --diff-filter=M 80d7c73 -- '*.py'` = **خالی**؛ فایل‌های فروزن source و ۹ فایل تست فروزن capture **byte-untouched**؛ تغییرات نسبت به base = همان ۱۸ فایل PR #2 |
| delta تکمیل نسبت به `0b073c9` | **۶ فایل، +160/−14** — `consistency.py`، `retention.py`، قرارداد، `test_wp13_consistency.py`، `test_wp13_retention.py`، `test_wp13_recovery_matrix.py` (همه متعلق به WP-1.3) |
| DEF4 / Decision Register | **۰ تغییر** نسبت به base؛ ردیف `| DEF4 | … DEFERRED` پابرجا |

**بازتولید مستقل ادعاهای نسخهٔ قبلی (برچسبِ پیشین «گزارش‌شده» را به «اجراشده» ارتقا داد):** روی head `0b073c9` — **125 passed** (۳ تکرار) · **215 passed** capture · **1601 passed / 0 failed** در 167.51s · smoke 8/8 exit 0. حساب `1476 + 125 = 1601` تأیید شد. (اعداد ۱۶۰۳/۲۲۰+ بالا مربوط به نسخهٔ **رفع‌شده** است؛ این دو را قاطی نکنید.)

فرمان‌های بازتولید (از ریشهٔ مخزن، روی شاخهٔ `arena/a776e4f2-kandoo-digital-invoice`):

```bash
python3 -m venv /tmp/k && /tmp/k/bin/pip install -q pytest
cd src && /tmp/k/bin/python -m pytest capture/tests/test_wp13_*.py -q     # 130
cd src && /tmp/k/bin/python -m pytest capture/tests/ -q                   # 220
cd src && /tmp/k/bin/python -m pytest -q                                  # 1606
cd src && /tmp/k/bin/python run_smoke_retention_recovery.py /tmp/s1       # SMOKE OK
cd src && /tmp/k/bin/python -m compileall -q .                            # exit 0
git diff --name-only --diff-filter=M 80d7c73 -- '*.py'                    # خالی
```

### ۳.۴ تاریخچه مانع ادغام (اکنون برطرف شده)

مأموریت ادغام را مشروط کرده بود به: (۱) رفع هر دو ایراد اصلی، (۲) موفقیت تست‌ها، (۳) دست‌نخورده ماندن Frozen، (۴) امکان‌پذیر بودن ادغام از GitHub.

- شرط (۲) ✅ (`130/220/1606/smoke×2/compileall` — بند ۳.۳)، شرط (۳) ✅ (بند ۳.۳)، شرط (۴) ✅ (`MERGEABLE/CLEAN` — **GitHub مانع نیست**).
- این مانع در اجرای بعدی رفع شد: commit `25565e8f5ab74297ca6a9fdd18c38efbf5416381` با fast-forward به شاخهٔ PR #2 منتقل شد و سپس PR #2 با commit `de38db0dc0e66158028b823aaffd6facd3fd1fc5` ادغام شد.
- نتیجهٔ تاریخی: پیش از انتقال fixها، ادغام ممنوع بود چون head حاوی B1/M1 بود. اکنون B1/M1 رفع و PR #2 ادغام شده است؛ این بخش سابقهٔ رخداد را نگه می‌دارد، نه وضعیت فعلی را.
- رفع مسیر باز: بند ۸.۱.

---

## ۴. DEF4 و حذف فیزیکی (غیرقابل مذاکره)

- `DEF4` = **`DEFERRED`** — `registers/deferred-decision-register.md` در این مأموریت **۰ تغییر** (`اجراشده`). هیچ مدت نگهداری/TTL/privacy/sharing/مجوز purge در هیچ فایلی وجود ندارد و نباید ساخته شود.
- **حذف فیزیکی اجرا یا فعال نشد و مسدود است:** `request_purge` فقط `PURGE_GATE_BLOCKED` برمی‌گرداند (`executed=False`، `rows_affected=0`)؛ هیچ تابع execute/DELETE/فایل‌پاک‌کنی در ماژول‌های WP-1.3 نیست (AST probe + بازبینی خط‌به‌خط `اجراشده`؛ پایداری بایت دیتابیس در تست‌ها).
- افزوده‌های این مأموریت (کدگذاری URI، deferral الگوریتم خارجی) **هیچ** مسیر حذف/مقادیر سیاستی نساختند؛ gate بسته‌تر شد، نه بازتر.
- برچسب همهٔ خروجی‌ها: `DEF4-PENDING`.

---

## ۵. تصمیم‌های Frozen و مرزهای ایمنی (تغییر = فقط مسیر STOP)

| شناسه | قاعده (خلاصهٔ binding) |
|---|---|
| **D-02** | S1/S2/invoice_id — هویت‌ها؛ الگوریتم capture = `sha256-v1` (همان چیزی که M1 به آن binding داد) |
| **D-03** | `S1` تنها idempotency سطح Capture؛ تعریف idempotency/dedup جدید ممنوع |
| **D-06/DEF3** | ساخت خودکار Customer ممنوع |
| **AD-03/DEF1** | هیچ اثر خودکار Sale/Inventory از External Capture |
| **D-07/D-08/WP-12.3** | آستانه‌ها placeholder کالیبراسیون‌اند؛ ratification = PO/G4 |
| **AS-03/AS-04** | state ماشین‌ها و فیلدها از مرجع Frozen؛ هیچ state جدید در سطح WP ممنوع |
| **DEF4** | مقادیر retention/privacy هرگز حدس نمی‌شوند؛ حذف فیزیکی مسدود |
| **DEF2/DEF5/DEF6** | REVIEW-matrix، ارائه، نقشه Modian بازنشده |
| **D-09** | پس از Freeze: بدون انتخاب OCR/VLM/DB جدید، بدون Migration معماری، بدون بازکردن DEFها |
| **Golden Rule** | بدون مجوز صریح TM: هیچ فایل/تست Frozen دست نمی‌خورد؛ بدون دستور PO/TM: `main` ادغام نمی‌شود |

اصل «مقدار ناشناخته ≠ مقدار قطعی»: خروجی بدون ورودی سیاست → `NOT_EVALUATED` / `UNRESOLVED` / `DEF4-PENDING`، هرگز صفر یا «منطقی».

---

## ۶. یافته‌های بازِ بازبینی (B1/M1 که رفع شدند؛ مابقی برای TM)

B1 و M1 در بند ۳ ثبت، رفع، تست و از طریق PR #2 در `main` ادغام شدند. مابقی یافته‌های بازبینی مستقل PR #2 که **نیاز به تصمیم/کار ندارند ولی ثبت‌شده‌اند** (کلاس MINOR/INFO؛ جزئیات در گزارش بازبینی جلسه):

| یافته | خلاصه | وضعیت |
|---|---|---|
| قطع هماهنگ suffix (حذف ردیف + anchor با هم) | زنجیر self-contained بدون anchor خارجی قابل تشخیص نیست — wording قرارداد §7 اغراق است؛ طبق طراحی class- inherented | `باز` — کلامِ تهدید-مدل در §7 پیشنهاد می‌شود (TM) |
| کدگذاری field separator (`\n`) در fingerprint | ورودی‌های دارای newline می‌توانند boundary را جابه‌جا کنند؛ ردِ ورودی ساختاری پیشنهادی | `باز` — اصلاح جزئی در WP آتی |
| age زیر-ثانیه‌ای منفی | `int()` صفر می‌کند؛ فقط با cutoff=0 و skew زیر-ثانیه معتبر می‌شود | `باز` — جزئی |
| نااتمامی snapshot گزارش (۳ اتصال) | زیر نوشتن هم‌زمان، false-positive گذرای orphan ممکن؛ فرض quiescence مستند نیست | `باز` — جزئی |
| blank در `RetentionPolicy` | قرارداد §4 می‌گوید `Incomplete`، کد/تست `IllegalInput` می‌دهند (هر دو typed و fail-closed) | `باز` — هماهنگ‌سازی متنی |
| مسیرهای `kandoo/` | روی `main` (registers+README): **۲۳۲ ارجاع** با الگوی `kandoo/(specs|src|baseline)` (`اجراشده`)؛ ضمناً `src/README.md` و docstringِ smokeِ خودِ PR #2 هم `kandoo/src` دارند (ارتقای همین نسخه) | `باز` — بند ۸.۴ |

---

## ۷. تصمیم‌ها و موانع باز (هیچ‌کدام اینجا قطعی نشده)

1. **تست تاریخ‌حساس** `identity_resolution/tests/test_ir_provenance.py::test_no_raw_pipeline_values_are_stored` (Frozen — WP-7.1): dump کل جدول‌ها را می‌سنجد و literal `2026-10-08` را قدغن می‌کند در حالی که `created_at` از `datetime.now(UTC)` می‌آید → **شکست قطعی فقط در روزِ ۲۰۲۶-۱۰-۰۸** (`اجراشده` با خواندن کد؛ اجرای امروز ۲۰۲۶-۱۰-۱۱ سبز است). **تصحیح نسبت به نسخهٔ ۱: «هر ۸ اکتبر سالانه» غلط است — fixture مطلق است و تکرار سالانه ندارد؛ روز برخورد گذشته است.** اصلاح test-side نیازمند مجوز TM (فایل Frozen)؛ فوریت ندارد.
2. **Observation هم‌زمانی recovery↔ingest**: رکورد ACTIVE در-جریان با `IllegalTransition` (زیرمجموعهٔ `CaptureLayerError`) از `ingest` بیرون می‌آید؛ INV-C6 نقض نمی‌شود، خوردگی نیست — رفتار تایپ‌دارِ ناخوشایند، نه defect (تأیید `اجراشده` روی کد فروزن). تغییر = فایل فروزن = مجوز TM.
3. **PR #1**: متناقض و فقط‌مستندات — تکلیف (merge/close/supersede) با TM/PO.
4. **B1/M1 روی PR #2** — رفع و ادغام‌شده؛ دیگر blocker نیست.
5. **بدهی MNT-1/RSK-2**: `baseline/` غایب؛ deadline «پیش از G3 پ۲» گذشته.
6. **Python floor**: `src/README.md` می‌گوید 3.12+؛ کل suite روی 3.11.2 سبز است — یا سند اصلاح شود یا اجرا روی 3.12+.
7. **بدون CI**: هیچ workflow نیست (`اجراشده`: `.github` غایب)؛ شواهد فقط محلی است.
8. **۱۷ بند WP** (شامل WP-1.3) در انتظار Acceptance رسمی؛ هیچ G3 فاز P2..P12 اعلام نشده.

---

## ۸. اقدامات بعدی — مالک + شهود بستن

| # | اقدام | مالک | شاهد بستن |
|---|---|---|---|
| ۸.۱ | انتقال fixهای B1/M1 به PR #2 | **انجام شد** | head `25565e8` ادغام شد؛ merge commit `de38db0…` |
| ۸.۲ | **ادغام PR #2 در `main`** | **انجام شد** | GitHub گزارش داد `merged=true`؛ merge commit: `de38db0dc0e66158028b823aaffd6facd3fd1fc5` |
| ۸.۳ | **به‌روزرسانی هندآف در PR #3** | **انجام شد؛ بازپایه‌گذاری و بررسی نهایی باقی است** | سند باید بر مبنای `main` باشد و diff فقط همین سند بماند |
| ۸.۴ | **ادغام PR #3** پس از تأیید سند تازه و diff تک‌فایلی | TM/PO | وضعیت `merged` و merge commit از GitHub تأیید شود |
| ۸.۵ | **تکلیف PR #1** (بند ۷.۳) | TM (+PO اگر به Acceptance مستندات برسد) | وضعیت نهایی ثبت‌شده در PR و REG؛ هرگز «تحویل سورس» گزارش نشود |
| ۸.۶ | تصمیم ۷.۱ (fix تست تاریخ) و ۷.۲ (رفتار هم‌زمانی) | TM → در صورت لمس فروزن: PO | ثبت تصمیم در REG-RR/REG-WPR |
| ۸.۷ | پاک‌سازی `kandoo/` (۲۳۲ ارجاع + دو مورد جدیدِ README/smoke) در یک PR مستندات‌محور | Agent 1 (اجرا) / TM (بازبینی) | `git grep -E 'kandoo/(specs|src|baseline)' main -- 'registers/*.md' 'README.md' | wc -l` = 0 |
| ۸.۸ | commit اسناد `baseline/` + Acceptance رسمی ۱۷ بند + اعلام G3 فازها | PO (با توصیهٔ TM) | فایل‌ها در `main`؛ ستون Accepted در REG-AR؛ Phase Index به‌روز |

---

## ۹. پروتکل همکاری و بازیابی برای جلسهٔ تازه

۱) Agent 1 پیاده‌سازی + شواهد اجراشده می‌دهد؛ ۲) Agent 2 مستقل بازمی‌گرداند و هم‌زمان فایلِ ایجنت دیگر را ویرایش نمی‌کند؛ ۳) TM مأموریت با Scope/AC/فایل مجاز/شرایط پایان می‌فرستد و شواهد را می‌خواند؛ ۴) PO تصمیم نهایی/ادغام/Acceptance؛ ۵) هیچ merge/PASS/Acceptance/تغییر GitHub بدون شاهد نیست؛ ۶) هر WP یک مالک، شاخه‌های جدا، `main` فقط شاخهٔ ادغام؛ ۷) پس از هر ادغام/تغییر معنادار، همین سند از طریق PR مستندات‌محور (PR #3) به‌روز شود؛ ۸) تعارض دستور/پلتفرم: محدودیت را شفاف گزارش کنید، بی‌صدا نادیده نگیرید.

### پرامپت آمادهٔ کپی برای جلسهٔ جدید

```text
You are resuming as Technical Manager for the Kandoo Digital Invoice project.

Repository: majid-ghanbari-dost/Kandoo-Digital-Invoice. Repository is the source
of truth; do not trust chat history.

First read: PROJECT_CONTINUITY_HANDOFF.md (this file, v2.0), README.md, then
registers/{decision,deferred-decision,work-package,task,acceptance,risk}-register.md.

Then verify LIVE state before trusting anything:
  git ls-remote origin
  gh pr list --state all
  gh pr view 1 --json state,headRefOid
  gh pr view 2 --json state,headRefOid,mergedAt,comments
  gh pr view 3 --json state,headRefOid,files

Known live state as of 2026-10-11 (re-verify): main = de38db0dc0e66158028b823aaffd6facd3fd1fc5
(PR #2 merged; verify with `git ls-remote origin refs/heads/main`). PR #1 remains OPEN governance-only
(head b3c6194…). PR #2 is MERGED from head 25565e8f5ab74297ca6a9fdd18c38efbf5416381; merge commit
`de38db0dc0e66158028b823aaffd6facd3fd1fc5`. The B1/M1 fixes are now in `main`. Evidence for the
fixed version, executed by Agent 2: WP-1.3 130 passed, capture 220, full regression 1606/0, smoke
8/8 ×2, compileall 0. Evidence on old PR head 0b073c9 was independently reproduced: 125 / 215 /
1601 / smoke. PR #3 remains the documentation-only handoff update; merge it after rebase and one-file diff verification. No CI exists in this repo.

Do not restart completed work (P1–P12.2 code is on main). Preserve all Frozen
decisions (D-01..D-09, AD-01..AD-04, AS-01..AS-04) and DEF1..DEF6 — DEF4 stays
DEFERRED, no retention/privacy values, physical deletion stays blocked; never edit
a frozen source/test without explicit authorization; never merge without explicit
order; PASS in tests is not Acceptance. Start by re-verifying live state and
reporting the next three decisions from section 8 of the handoff.
```

---

```text
پایان سند — نسخه ۲.۰. این سند مستندات‌محور است: هیچ کد، تست، Register یا تصمیم Frozen را تغییر نمی‌دهد. وضعیت GitHub باید پیش از استفاده در جلسه جدید دوباره راستی‌آزمایی شود.
هر ادعای «اجراشده» با فرمان‌های بند ۳.۳ روی همین شاخه قابل بازتولید است؛ بقیه برچسب دارند.
```
