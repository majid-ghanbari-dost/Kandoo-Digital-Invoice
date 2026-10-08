# Task Register — Kandoo Digital Invoice

```text
Register ID:  REG-TR | Version: 1.0 | Date: 2026-10-01 | Owner: Technical Manager
Rule:         این Register حافظه رسمی پروژه برای Agentهای stateless است.
Status Flow:  PLANNED → READY (پس از G2) → IN PROGRESS → DONE / BLOCKED
Cold-Start:   هر Task باید بدون حافظه گفتگوهای قبلی قابل اجرا باشد؛ هر ارجاع = مسیر فایل یا شناسه رکورد.
Rule:         Taskها فقط «طراحی» شده‌اند و اجرا نشده‌اند. اجرای اولین Task فقط پس از تأیید Bootstrap (G2) مجاز است.
```

---

## T-1.1.1 — Capture Record Contract Specification

```text
Task ID:              T-1.1.1
Phase:                P1 — Capture Foundation
Work Package:         WP-1.1
Objective:            تولید مشخصه (Contract) Capture Record به‌صورت سند implementation-independent:
                      فیلدها، وضعیت‌ها، semantics مربوط به S1 و integrity و recovery، فیلدهای traceability.
Context:              WP-1.1 پایه durable capture را می‌سازد. این Task فقط سند مشخصه تولید می‌کند، بدون هیچ کد.
                      Contract باید Capture Identity و idempotency سطح Capture را منعکس کند و به هر AC از WP-1.1 نگاشت داشته باشد.
Locked Decisions:     D-02 (S1 = capture_content_fingerprint، کلید idempotency سطح Capture) | D-03 (S1 → Capture Idempotency) | D-09 (حکمرانی Freeze)
Reference Documents:  kandoo/registers/decision-register.md (D-02, D-03, D-09)
                      kandoo/registers/work-package-register.md (WP-1.1)
                      kandoo/registers/deferred-decision-register.md (DEF4 — فقط برای یادداشت رزرو hook، بدون مقدار سیاست)
Inputs:               فهرست ۸ AC در WP-1.1 | قالب فیلدهای traceability در AC-1.1.8
Scope:                سند مشخصه شامل: فیلدهای رکورد (capture_id, S1, timestamp, source_label, state, integrity_status, lineage_reserved)،
                      وضعیت‌های چرخه capture (active/completed/failed_incomplete/integrity_failed)، نگاشت AC → عنصر Contract.
Out of Scope:         هرگونه کد، اجرای schema، انتخاب مکانیزم ذخیره‌سازی، فیلدهای extraction، cloud، Holoo، تغییر تصمیمات Frozen.
Files / Components:   ایجاد: kandoo/specs/WP-1.1-capture-record-contract.md
Forbidden Actions:    کدنویسی | انتخاب DB/ذخیره‌ساز در سطح معماری | طراحی API | اجرای Migration/Schema | باز کردن اقلام Deferred | ایجاد تصمیم معماری جدید
Dependencies:         G1 (PASS) + G2 (تأیید Bootstrap)
Expected Deliverables: kandoo/specs/WP-1.1-capture-record-contract.md (کامل و قابل ارجاع)
Tests:                چک‌لیست بازبینی: هر AC از WP-1.1 به ≥1 عنصر Contract نگاشت شده باشد؛ هیچ وضعیت تعریف‌نشده وجود نداشته باشد؛
                      هیچ انتخاب implementation در Contract تزریق نشده باشد.
Acceptance Criteria:  (۱) سند در مسیر مقصد موجود است؛ (۲) همه فیلدهای Scope حاضرند؛ (۳) جدول نگاشت AC→Contract کامل است؛
                      (۴) semantics مربوط به S1 عیناً با D-02/D-03 سازگار است.
DoD:                  سند commit شده | وضعیت Task در همین Register به‌روز | گزارش استاندارد ثبت شده | بدون Forbidden Action
Reporting Format:     گزارش استاندارد: Summary | Files Changed | AC Mapping Status | Delegated Implementation Detail Decisions (در صورت وجود) | Issues (در صورت وجود)
Status:               DONE — 2026-10-01 | Evidence: kandoo/specs/WP-1.1-capture-record-contract.md (§18: 10/10 AC-T111 PASS) | G2: APPROVED | بدون Forbidden Action
```

---

## T-1.1.2 — Durable Local Capture Store

```text
Task ID:              T-1.1.2
Phase:                P1 — Capture Foundation
Work Package:         WP-1.1
Objective:            پیاده‌سازی persistence دائمی local برای Capture Recordها طبق Contract T-1.1.1؛ رکوردها پس از restart باقی و قابل خواندن می‌مانند.
Context:              انتخاب مکانیزم ذخیره‌سازی (embedded store / filesystem و مانند آن) یک Implementation Detail تفویض‌شده است با قیدها:
                      durable، local، بدون وابستگی به سرویس شبکه؛ انتخاب باید در گزارش Task اعلام شود و تصمیم معماری محسوب نمی‌شود (مطابق D-09 و پروتکل README §6).
Locked Decisions:     D-02 | D-09 | AC-1.1.1 / AC-1.1.6 / AC-1.1.7 (از WP Register)
Reference Documents:  kandoo/specs/WP-1.1-capture-record-contract.md (خروجی T-1.1.1)
                      kandoo/registers/decision-register.md (D-02, D-09) | kandoo/registers/work-package-register.md (WP-1.1)
Inputs:               Contract Capture Record | فهرست ACهای مرتبط
Scope:                کامپوننت Store: ایجاد/خواندن رکورد، persistence دائمی، وضعیت‌های خطای پایه، رفتار در restart.
Out of Scope:         محاسبه S1 (T-1.1.3) | منطق verify-on-read (T-1.1.4) | retention/purge (WP-1.3) | cloud | Holoo | هر تغییر Contract
Files / Components:   کامپوننت‌ها زیر kandoo/src/capture/ (چیدمان نهایی داخل Task تعیین و در گزارش اعلام می‌شود) + تست‌های هم‌مسیر
Forbidden Actions:    انتخاب DB در سطح معماری | اجرای Migration/Schema روی محیط مشترک | نوشتن منطق extraction | ساخت Sale/Customer | باز کردن Deferred
Dependencies:         T-1.1.1 (DONE)
Expected Deliverables: کامپوننت Store + تست‌های unit/restart + گزارش
Tests:                AC-1.1.1 (ایجاد/بازیابی) | AC-1.1.6 (restart durability) | پشتیبانی از سناریوی AC-1.1.7 (interruption injection)
Acceptance Criteria:  مطابق AC-1.1.1 و AC-1.1.6 در WP Register — راستی‌آزمایی عینی با اجرای تست و ثبت شواهد
DoD:                  تست‌ها سبز | شواهد در Acceptance Register | انتخاب مکانیزم در گزارش اعلام شده | Registerها به‌روز
Reporting Format:     گزارش استاندارد (همان قالب T-1.1.1)
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-1.1-IMPL؛ تأیید TM) | Evidence: kandoo/src/capture/store.py + tests/test_store.py (۱۸ تست) + tests/test_e2e.py | انتخاب ذخیره‌ساز اعلامی طبق D-09: embedded SQLite stdlib (durable/local/no-network، synchronous=FULL، UAC با BEGIN IMMEDIATE + partial UNIQUE index)
```

---

## T-1.1.3 — S1 Fingerprint & Idempotency Lookup Service

```text
Task ID:              T-1.1.3
Phase:                P1 — Capture Foundation
Work Package:         WP-1.1
Objective:            پیاده‌سازی تولید، ذخیره و lookup سرویس S1 = capture_content_fingerprint؛ تضمین قطعیت و حساسیت به محتوا؛ فراهم کردن idempotency سطح Capture.
Context:              انتخاب الگوریتم fingerprint یک Implementation Detail تفویض‌شده با قیدها: deterministic، content-sensitive
                      (هر تغییر محتوا → S1 متفاوت)، و قابل گزارش. طبق D-03، S1 تنها کلید idempotency سطح Capture است.
Locked Decisions:     D-02 (تعریف S1) | D-03 (S1 → Capture Idempotency) | AC-1.1.2 / AC-1.1.3 / AC-1.1.4
Reference Documents:  kandoo/specs/WP-1.1-capture-record-contract.md | kandoo/registers/decision-register.md (D-02, D-03)
Inputs:               Contract (فیلد S1 و semantics آن) | کامپوننت Store از T-1.1.2 (برای ذخیره/lookup)
Scope:                سرویس S1: محاسبه روی محتوای artifact، ذخیره همراه رکورد، lookup با مقدار S1، پاسخ استاندارد به تلاش re-capture با محتوای تکراری.
Out of Scope:         dedup سطح سند (S2 — P7) | تفسیر معنایی محتوا | extraction | تغییر تعریف S1 | Holoo
Files / Components:   کامپوننت‌ها زیر kandoo/src/capture/ + تست‌های هم‌مسیر
Forbidden Actions:    تغییر تعریف S1 | افزودن قواعد dedup سند | انتخاب موتور OCR/VLM | ایجاد تصمیم معماری جدید
Dependencies:         T-1.1.1 (DONE) | یکپارچگی با T-1.1.2
Expected Deliverables: سرویس S1 + تست‌های قطعیت/حساسیت/lookup + گزارش
Tests:                AC-1.1.2 (property test: ≥2 ورودی یکسان → S1 برابر؛ mutation تک‌بایتی → S1 متفاوت) | AC-1.1.3 (ذخیره و lookup) | AC-1.1.4 (duplicate submission)
Acceptance Criteria:  مطابق AC-1.1.2 / AC-1.1.3 / AC-1.1.4 در WP Register
DoD:                  تست‌ها سبز | شواهد ثبت | الگوریتم انتخابی در گزارش اعلام شده | Registerها به‌روز
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-1.1-IMPL؛ تأیید TM) | Evidence: kandoo/src/capture/s1.py + tests/test_s1.py (۸ تست) + tests/test_ingest_idempotency.py (۱۰ تست) | الگوریتم اعلامی: SHA-256 کامل lowercase hex با s1_algorithm_id=sha256-v1
```

---

## T-1.1.4 — Integrity Verification on Read

```text
Task ID:              T-1.1.4
Phase:                P1 — Capture Foundation
Work Package:         WP-1.1
Objective:            پیاده‌سازی verify-on-read: در هر خواندن رکورد، یکپارچگی محتوا در برابر S1 ذخیره‌شده بررسی شود؛ محتوای ناسازگار → وضعیت fail صریح، بدون خواندن ساکتِ خراب.
Context:              این قابلیت شرط «integrity» در Goal مربوط به WP-1.1 است و مبنای اعتماد همه مراحل بعدی به artifact ذخیره‌شده است.
Locked Decisions:     D-02 (S1 به‌عنوان مبنای یکپارچگی) | AC-1.1.5
Reference Documents:  kandoo/specs/WP-1.1-capture-record-contract.md (وضعیت integrity_status) | kandoo/registers/decision-register.md (D-02)
Inputs:               کامپوننت Store (T-1.1.2) | سرویس S1 (T-1.1.3)
Scope:                منطق verification هنگام خواندن + تنظیم integrity_status + رفتار استاندارد در fail (علامت‌گذاری + عدم ارائه محتوای ناسازگار به‌عنوان سالم)
Out of Scope:         ترمیم خودکار محتوا | retention | reconstruction | هر تغییر در سرویس S1
Files / Components:   کامپوننت‌ها زیر kandoo/src/capture/ + تست‌های هم‌مسیر
Forbidden Actions:    سیاست‌های حذف/نگهداری (DEF4) | تغییر Contract بدون ثبت در Register | کد در نواحی Deferred
Dependencies:         T-1.1.2 | T-1.1.3
Expected Deliverables: کامپوننت verify-on-read + تست corruption injection + گزارش
Tests:                AC-1.1.5 (تزریق خرابی: تغییر محتوای ذخیره‌شده → خواندن بعدی fail صریح)
Acceptance Criteria:  مطابق AC-1.1.5 در WP Register
DoD:                  تست‌ها سبز | شواهد ثبت | Registerها به‌روز
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-1.1-IMPL؛ تأیید TM) | Evidence: kandoo/src/capture/service.py (read_evidence طبق VOR v1.0 FROZEN) + tests/test_read_path.py (۸ تست) + tests/test_s1.py::test_verify_valid_failed_no_verdict
```

---

## T-1.1.5 — Initial Recovery Behavior

```text
Task ID:              T-1.1.5
Phase:                P1 — Capture Foundation
Work Package:         WP-1.1
Objective:            پیاده‌سازی رفتار اولیه recovery: capture قطع‌شده/نیمه‌نوشته در شروع بعدی یا کامل یا با وضعیت صریح failed/incomplete علامت بخورد؛ هیچ رکورد نیمه‌ساخت valid ارائه نشود.
Context:              «رفتار اولیه» یعنی حداقل رفتار درست در برابر interruption؛ سخت‌سازی کامل ماتریس crash در WP-1.3 است.
Locked Decisions:     D-09 | AC-1.1.7
Reference Documents:  kandoo/specs/WP-1.1-capture-record-contract.md (وضعیت‌های recovery) | kandoo/registers/work-package-register.md (WP-1.1, WP-1.3)
Inputs:               کامپوننت Store (T-1.1.2) | Contract
Scope:                شناسایی رکورد نیمه‌نوشته در startup، تسویه به completed یا failed_incomplete، ثبت نتیجه در state رکورد
Out of Scope:         ماتریس کامل crash/orphan (WP-1.3) | retention | هر retry خودکار به سمت sourceهای خارجی
Files / Components:   کامپوننت‌ها زیر kandoo/src/capture/ + تست‌های هم‌مسیر
Forbidden Actions:    پیش‌بردن WP-1.3 داخل این Task | تعیین مقادیر retention (DEF4) | تغییر معماری ذخیره‌سازی
Dependencies:         T-1.1.2
Expected Deliverables: کامپوننت recovery اولیه + تست interruption injection + گزارش
Tests:                AC-1.1.7 (شبیه‌سازی قطع نوشتن → شروع مجدد → وضعیت نهایی صریح)
Acceptance Criteria:  مطابق AC-1.1.7 در WP Register
DoD:                  تست‌ها سبز | شواهد ثبت | Registerها به‌روز
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-1.1-IMPL؛ تأیید TM) | Evidence: kandoo/src/capture/recovery.py (طبق Contract §11 / Store §5) + tests/test_recovery.py (۷ تست W2/W3/W4/uniqueness/idempotence/mixed) + tests/test_e2e.py::test_full_mvp_journey
```

---

## T-1.1.6 — Traceability Fields & Acceptance Closure

```text
Task ID:              T-1.1.6
Phase:                P1 — Capture Foundation
Work Package:         WP-1.1
Objective:            تکمیل فیلدهای traceability در رکوردها (AC-1.1.8)، اجرای کامل مجموعه تست هر ۸ AC، جمع‌آوری شواهد، و بستن Acceptance Register برای WP-1.1.
Context:              این Task نقطه اتصال WP-1.1 به Gate G3 است؛ خروجی آن شواهد لازم برای Phase Exit فاز Capture Foundation را فراهم می‌کند.
Locked Decisions:     D-02 | D-03 | D-09 | AC-1.1.8
Reference Documents:  kandoo/specs/WP-1.1-capture-record-contract.md | kandoo/registers/acceptance-register.md | kandoo/registers/task-register.md
Inputs:               خروجی کامل T-1.1.2 تا T-1.1.5 | Acceptance Register
Scope:                اعتبارسنجی حضور فیلدهای lineage/traceability | اجرای مجموعه تست کامل | ثبت شواهد با مسیر | به‌روزرسانی دو Register
Out of Scope:         پیاده‌سازی مراحل downstream (lineage فقط field رزروشده است) | بستن G3 (تصمیم PM+QA است) | هر قلم Out of Scope مربوط به WP-1.1
Files / Components:   تست‌های تجمیعی زیر kandoo/src/capture/ + به‌روزرسانی Registerها
Forbidden Actions:    ساخت lineage واقعی به extraction/canonical (P3/P6) | اعلام G3 بدون شواهد | هر تصمیم معماری
Dependencies:         T-1.1.2 | T-1.1.3 | T-1.1.4 | T-1.1.5 (همه DONE)
Expected Deliverables: گزارش شواهد کامل هر ۸ AC + دو Register به‌روز + وضعیت آمادگی G3
Tests:                اجرای کامل AC-1.1.1 تا AC-1.1.8 با ثبت مسیر شواهد
Acceptance Criteria:  مطابق AC-1.1.8 + بسته‌شدن رسمی ردیف‌های Acceptance Register مربوط به WP-1.1
DoD:                  همه ACها با شواهد بسته | Registerها به‌روز | گزارش نهایی WP-1.1 ارائه شده
Reporting Format:     گزارش استاندارد + جدول وضعیت نهایی ۸ AC با مسیر شواهد
Status:               DONE — 2026-10-01 | Evidence: kandoo/registers/acceptance-register.md (8/8 AC PASS با مسیر شواهد) + بازاجرای زنده: pytest 54/54 PASSED (0.40s) + kandoo/src/run_smoke.py → SMOKE OK | Registerها به‌روز (Acceptance + Task + WP) | G3: READY — بستن رسمی نزد PM+QA/PO | بدون Forbidden Action
```

---

## T-2.1.1 — Reconstruction Document/Page Contract Specification

```text
Task ID:              T-2.1.1
Phase:                P2 — Reconstruction
Work Package:         WP-2.1
Objective:            تولید مشخصه (Contract) ساختار Document/Page به‌صورت implementation-independent: فیلدها، lifecycle، پیوند صریح به
                      capture_id/S1، semantics ترتیب صفحات، integrity/recovery semantics، نگاشت به ۶ AC.
Context:              طبق dispatch TM (2026-10-01): Reconstruction فقط artifact/capture را به ساختار Document/Page مصرف‌پذیر برای Extraction تبدیل
                      می‌کند — هیچ استخراج داده فاکتور (P3) و هیچ OCR/VLM. الگوی حکمرانی همان WP-1.1: Contract اول، سپس implementation.
Locked Decisions:     D-02 (هویت Capture = S1؛ document identity در P7 حل می‌شود — اینجا کار نمی‌شود) | D-03 (idempotency فقط سطح Capture) |
                      D-09 (حکمرانی Freeze) | AS-01 (توالی External Flow)
Reference Documents:  kandoo/registers/decision-register.md (D-02, D-03, D-09, AS-01) | kandoo/registers/work-package-register.md (WP-2.1) |
                      kandoo/specs/WP-1.1-capture-record-contract.md (§5 Extensibility Reservation — پیوند downstream فقط با capture_id/S1)
Inputs:               فهرست ۶ AC در WP-2.1 | رفتارهای Frozen WP-1.1 (دریافت verified از Capture)
Scope:                سند مشخصه شامل: فیلدهای Document/Page، lifecycle (ACTIVE/COMPLETED/FAILED_INCOMPLETE)، قواعد ترتیب صفحات MVP (قطعی،
                      بدون heuristic معنایی)، پیوند page → capture_id/S1، verify-on-read semantics، recovery/settlement semantics، نگاشت AC → عنصر Contract.
Out of Scope:         هرگونه کد | استخراج داده فاکتور | OCR/VLM | S2/Identity Resolution (P7) | dedup سطح سند (P7) | WP-2.2 | تغییر Contract یا رفتارهای Frozen WP-1.1
Files / Components:   ایجاد: kandoo/specs/WP-2.1-reconstruction-contract.md
Forbidden Actions:    کدنویسی | انتخاب OCR/VLM/DB | طراحی API | اجرای Migration/Schema روی محیط مشترک | باز کردن Deferred | ایجاد تصمیم معماری جدید | کار روی S2
Dependencies:         G3 (PASS — 2026-10-01) | WP-1.1 (CLOSED — IMPLEMENTED)
Expected Deliverables: kandoo/specs/WP-2.1-reconstruction-contract.md (کامل و قابل ارجاع)
Tests:                چک‌لیست بازبینی: هر AC از WP-2.1 به ≥1 عنصر Contract نگاشت شده باشد؛ هیچ انتخاب implementation بدون برچسب delegated تزریق نشده باشد؛
                      هیچ رفتار جدیدی با D-02/D-03 تعارض نداشته باشد.
Acceptance Criteria:  (۱) سند در مسیر مقصد موجود است؛ (۲) همه عناصر Scope حاضرند؛ (۳) جدول نگاشت AC→Contract کامل است؛
                      (۴) سازگاری با Contract v1.1 §5 و D-02/D-03 صریح است.
DoD:                  سند commit شده | وضعیت Task در همین Register به‌روز | گزارش استاندارد ثبت شده | بدون Forbidden Action
Reporting Format:     گزارش استاندارد: Summary | Files Changed | AC Mapping Status | Delegated Implementation Detail Decisions | Issues
Status:               DONE — 2026-10-01 (اجرای inline در dispatch یکپارچه WP-2.1-IMPL به دستور TM: «Contract حداقلی را در حین کار مشخص کن؛ T-2.1.1 را به مرحله مستقل و طولانی تبدیل نکن») | Evidence: kandoo/specs/WP-2.1-reconstruction-contract.md (v1.0-MVP — فیلدهای Document/Page، lifecycle حداقلی، derivation قطعی، verified-read، مرز Reconstruction/Extraction، نگاشت ۶ AC، جزئیات delegated اعلامی) | بدون Forbidden Action
```

---

## T-2.1.2 — Durable Document/Page Store

```text
Task ID:              T-2.1.2
Phase:                P2 — Reconstruction
Work Package:         WP-2.1
Objective:            پیاده‌سازی persistence دائمی local برای Document/Page طبق Contract T-2.1.1؛ سندها پس از restart باقی و قابل خواندن می‌مانند.
Context:              هم‌الگوی WP-1.1 store: lifecycle صریح + settlement قطعی + recovery اولیه. انتخاب مکانیزم ذخیره‌سازی = Implementation Detail
                      تفویض‌شده (قیدها: durable، local، بدون وابستگی به سرویس شبکه) — باید در گزارش اعلام شود (D-09).
Locked Decisions:     D-02 | D-09 | AC-2.1.1 / AC-2.1.4 / AC-2.1.5 / AC-2.1.6
Reference Documents:  kandoo/specs/WP-2.1-reconstruction-contract.md (خروجی T-2.1.1) | kandoo/src/capture/store.py (الگوی مرجع — بدون تغییر رفتار Frozen آن)
Inputs:               Contract Reconstruction | کامپوننت‌های WP-1.1 (برای دریافت verified از Capture)
Scope:                کامپوننت Document/Page Store: ایجاد/خواندن، persistence دائمی، پیوند page → capture_id/S1، وضعیت‌های خطای پایه، رفتار در restart.
Out of Scope:         منطق build/reconstruction (T-2.1.3) | extraction | OCR/VLM | retention/purge (WP-1.3/DEF4) | WP-2.2 | هر تغییر در Capture Store
Files / Components:   کامپوننت‌ها زیر kandoo/src/reconstruction/ (چیدمان نهایی داخل Task تعیین و در گزارش اعلام می‌شود) + تست‌های هم‌مسیر
Forbidden Actions:    انتخاب DB در سطح معماری | اجرای Migration/Schema روی محیط مشترک | extraction | OCR/VLM | باز کردن Deferred | تغییر رفتار Frozen WP-1.1
Dependencies:         T-2.1.1 (DONE)
Expected Deliverables: کامپوننت Document/Page Store + تست‌های unit/restart + گزارش
Tests:                AC-2.1.1 (ایجاد/بازیابی + restart) | AC-2.1.6 (traceability fields) | پشتیبانی از سناریوی AC-2.1.5 (interruption injection)
Acceptance Criteria:  مطابق AC-2.1.1 و AC-2.1.6 در WP Register — راستی‌آزمایی عینی با اجرای تست و ثبت شواهد
DoD:                  تست‌ها سبز | شواهد در Acceptance Register | انتخاب مکانیزم اعلام شده | Registerها به‌روز
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-2.1-IMPL؛ تأیید اجرایی: 101/101 tests + SMOKE OK) | Evidence: kandoo/src/reconstruction/store.py + kandoo/src/reconstruction/tests/test_recon_store.py (۱۴ تست) + tests/test_recon_e2e.py | انتخاب ذخیره‌ساز اعلامی طبق D-09: embedded SQLite stdlib در DB فایل مجزا (durable/local/no-network، synchronous=FULL، BEGIN IMMEDIATE، backstop partial UNIQUE index روی capture_id برای COMPLETED) — Capture Store Frozen دست‌نخورده
```

---

## T-2.1.3 — Reconstruction Service (Build + Verified Read + Recovery)

```text
Task ID:              T-2.1.3
Phase:                P2 — Reconstruction
Work Package:         WP-2.1
Objective:            پیاده‌سازی سرویس Reconstruction: تبدیل capture (از مسیر verified read) به ساختار Document/Page مصرف‌پذیر برای Extraction؛
                      شامل verify-on-read خروجی و recovery ساخت‌های نیمه‌تمام.
Context:              MVP طبق dispatch TM: ترتیب صفحات قطعی و بدون heuristic معنایی (ترتیب صریح ورودی؛ استراتژی دقیق page derivation =
                      Implementation Detail تفویض‌شده با قید قطعیت و عدم تفسیر محتوا — در گزارش اعلام می‌شود). هیچ استخراج داده‌ای انجام نمی‌شود.
Locked Decisions:     D-02 | D-03 | D-09 | AS-01 | AC-2.1.2 / AC-2.1.3 / AC-2.1.4 / AC-2.1.5
Reference Documents:  kandoo/specs/WP-2.1-reconstruction-contract.md | kandoo/src/capture/service.py (الگوی verified read) | kandoo/src/capture/recovery.py
Inputs:               Document/Page Store (T-2.1.2) | Contract | کامپوننت‌های Capture (WP-1.1)
Scope:                build document از capture/های COMPLETED (از مسیر verified read)، تولید صفحات با ترتیب قطعی، ذخیره از طریق Store،
                      verify-on-read سند، settlement ساخت‌های نیمه‌تمام در startup.
Out of Scope:         extraction | OCR/VLM | S2/identity | dedup سند | heuristic ترتیب معنایی | WP-2.2 | تغییر capture components
Files / Components:   کامپوننت‌ها زیر kandoo/src/reconstruction/ + تست‌های هم‌مسیر
Forbidden Actions:    انتخاب OCR/VLM | هرگونه تفسیر محتوایی/استخراج داده | باز کردن Deferred | تغییر رفتار Frozen WP-1.1 | ایجاد تصمیم معماری جدید
Dependencies:         T-2.1.1 | T-2.1.2 | WP-1.1 components (CLOSED)
Expected Deliverables: سرویس Reconstruction + تست‌های ordering/durability/corruption/recovery + گزارش
Tests:                AC-2.1.2 (قطعیت ترتیب) | AC-2.1.3 (پیوند page→منبع؛ مرز بدون extraction) | AC-2.1.4 (corruption injection) | AC-2.1.5 (interruption/restart)
Acceptance Criteria:  مطابق AC-2.1.2 / AC-2.1.3 / AC-2.1.4 / AC-2.1.5 در WP Register
DoD:                  تست‌ها سبز | شواهد ثبت | انتخاب‌های delegated اعلام شده | Registerها به‌روز
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-2.1-IMPL) | Evidence: kandoo/src/reconstruction/service.py + pages.py + recovery.py + tests/test_recon_service.py (۸ تست) + test_recon_read_path.py (۶) + test_recon_recovery.py (۷) + test_recon_concurrency.py (۲) + test_recon_e2e.py (۲) | استراتژی page derivation اعلامی (delegated طبق D-09): پارس مکانیکی framing تجمیع Frozen WP-1.1 (8-byte BE، total-consumption؛ artifact غیرمنطبق = تک‌صفحه) — content-blind، قطعی، بدون heuristic معنایی؛ هویت سند = document_id محلی (بدون S2/dedup سند — P7)؛ INV-R-1:1 = حداکثر یک Document COMPLETED برای هر capture با الگوی UAC
```

---

## T-2.1.4 — Acceptance Closure WP-2.1

```text
Task ID:              T-2.1.4
Phase:                P2 — Reconstruction
Work Package:         WP-2.1
Objective:            اجرای کامل مجموعه تست هر ۶ AC، جمع‌آوری شواهد، و بستن Acceptance Register برای WP-2.1.
Context:              نقطه اتصال WP-2.1 به Gate Phase Exit فاز P2؛ خروجی آن شواهد لازم برای عبور فاز Reconstruction را فراهم می‌کند.
Locked Decisions:     D-02 | D-03 | D-09 | AC-2.1.6
Reference Documents:  kandoo/specs/WP-2.1-reconstruction-contract.md | kandoo/registers/acceptance-register.md | kandoo/registers/task-register.md
Inputs:               خروجی کامل T-2.1.2 و T-2.1.3 | Acceptance Register
Scope:                اعتبارسنجی حضور فیلدهای traceability سند | اجرای مجموعه تست کامل | ثبت شواهد با مسیر | به‌روزرسانی دو Register
Out of Scope:         هر کد جدید | استخراج داده | WP-2.2 | بستن Gate فاز P2 (تصمیم PM+QA است)
Files / Components:   به‌روزرسانی Registerها (بدون کد جدید؛ تست تجمیعی فقط در صورت نبود پوشش)
Forbidden Actions:    ساخت lineage واقعی به extraction (P3) | اعلام Gate بدون شواهد | هر تصمیم معماری | جعل evidence
Dependencies:         T-2.1.2 | T-2.1.3 (هر دو DONE)
Expected Deliverables: گزارش شواهد کامل هر ۶ AC + دو Register به‌روز + وضعیت آمادگی Gate P2
Tests:                اجرای کامل AC-2.1.1 تا AC-2.1.6 با ثبت مسیر شواهد
Acceptance Criteria:  مطابق AC-2.1.6 + بسته‌شدن رسمی ردیف‌های Acceptance Register مربوط به WP-2.1
DoD:                  همه ACها با شواهد بسته | Registerها به‌روز | گزارش نهایی WP-2.1 ارائه شده
Reporting Format:     گزارش استاندارد + جدول وضعیت نهایی ۶ AC با مسیر شواهد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-2.1-IMPL) | Evidence: kandoo/registers/acceptance-register.md (6/6 AC PASS با مسیر شواهد) + بازاجرای زنده: pytest kandoo/src/capture/tests kandoo/src/reconstruction/tests → 101/101 PASSED (47 reconstruction + 54 capture؛ 0.75s) + kandoo/src/run_smoke_reconstruction.py → SMOKE OK (۷ گام) + kandoo/src/run_smoke.py → SMOKE OK (رجرسیون WP-1.1) | Registerها به‌روز (Acceptance + Task + WP) | بدون Forbidden Action
```

---

## T-2.2.1 — Reconstruction Evidence Contract Specification

```text
Task ID:              T-2.2.1
Phase:                P2 — Reconstruction
Work Package:         WP-2.2
Objective:            تولید مشخصه (Contract) Evidence سطح Reconstruction به‌صورت حداقلی و inline:
                      واژگان رویداد ثابت، شکل record، زنجیره هش ضد دستکاری، binding بازه بایتی
                      page→منبع، verified evidence read، مرز no-content، نگاشت به ۶ AC.
Context:              طبق dispatch TM (2026-10-01): «بدون ایجاد فاز طراحی/Review جدید — مستقیماً
                      ساخت واقعی». Contract حداقلی در حین کار مشخص شد (هم‌الگوی T-2.1.1).
Locked Decisions:     D-02 (پیوند فقط capture_id/S1) | D-03 (بدون تعریف idempotency جدید) |
                      D-09 (حکمرانی Freeze) | AS-01 | SPEC-WP21-RC (رفتار Frozen WP-2.1 دست‌نخورده)
Reference Documents:  kandoo/specs/WP-2.1-reconstruction-contract.md | kandoo/registers/work-package-register.md (WP-2.2) |
                      kandoo/registers/decision-register.md (D-02, D-03, D-09, AS-01)
Inputs:               رفتارهای Frozen WP-2.1 (Document/Page/UAC/VOR/recovery) | قیدهای ساختاری evidence
Scope:                سند مشخصه: واژگان ۴ رویداد document-scoped، ستون‌های record، قواعد fingerprint/chain/genesis،
                      لنگر head (کشف truncation)، قاعده spans_from_durable، outcomeهای خواندن evidence،
                      اتصال غیرمخرب، مرز no-content، جدول نگاشت AC، فهرست deferred.
Out of Scope:         هرگونه کد در این سند | audit سطح attempt برای outcomeهای بدون سند (deferred) | retention (DEF4) | S2 | Extraction
Files / Components:   ایجاد: kandoo/specs/WP-2.2-reconstruction-evidence-contract.md
Forbidden Actions:    انتخاب OCR/VLM/DB در سطح معماری | باز کردن Deferred | ایجاد تصمیم معماری جدید | تغییر رفتار Frozen WP-2.1/WP-1.1
Dependencies:         WP-2.1 (CLOSED — IMPLEMENTED)
Expected Deliverables: kandoo/specs/WP-2.2-reconstruction-evidence-contract.md (کامل و قابل ارجاع)
Tests:                چک‌لیست بازبینی: هر AC از WP-2.2 به ≥1 عنصر Contract نگاشت شده؛ هیچ کلید payload خارج از
                      واژگان ثابت؛ سازگاری با D-02/D-03 و SPEC-WP21-RC صریح.
Acceptance Criteria:  (۱) سند در مسیر مقصد موجود است؛ (۲) همه عناصر Scope حاضرند؛ (۳) نگاشت AC→Contract کامل؛
                      (۴) مرز no-content و قاعده spans دقیق و قطعی مشخص‌اند.
DoD:                  سند commit شده | وضعیت Task به‌روز | بدون Forbidden Action
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (inline در dispatch یکپارچه WP-2.2-IMPL) | Evidence: kandoo/specs/WP-2.2-reconstruction-evidence-contract.md (v1.0-MVP — §1–§10؛ نگاشت ۶ AC در §9؛ deferred صریح در §10) | بدون Forbidden Action
```

---

## T-2.2.2 — Evidence Store + Page→Source Binding + Verified Evidence Read

```text
Task ID:              T-2.2.2
Phase:                P2 — Reconstruction
Work Package:         WP-2.2
Objective:            پیاده‌سازی Evidence Store فقط-الحاقی دائمی (فایل DB مجزا)، fingerprint هر record با
                      قابلیت S1 موجود، زنجیره هش سراسری + لنگر head، binding قطعی page→بازه منبع،
                      verified evidence read (VOR روی evidence)، و اتصال غیرمخرب به service/recovery.
Context:              هم‌الگوی WP-2.1 (lifecycle صریح، settlement قطعی، explicit outcomes). انتخاب مکانیزم
                      ذخیره‌سازی = Implementation Detail تفویض‌شده (D-09): SQLite stdlib فایل مجزا — اعلام شد.
Locked Decisions:     D-02 | D-03 | D-09 | AC-2.2.1 / AC-2.2.2 / AC-2.2.3 / AC-2.2.4 / AC-2.2.5 / AC-2.2.6
Reference Documents:  kandoo/specs/WP-2.2-reconstruction-evidence-contract.md | kandoo/src/reconstruction/{store,service,recovery}.py (Frozen WP-2.1 — بدون تغییر رفتار)
Inputs:               Contract T-2.2.1 | ReconstructionStore/Service/Recovery | S1Service (sha256-v1)
Scope:                evidence.py (مدل + EvidenceStore + spans_from_durable)؛ پارامتر اختیاری evidence در
                      ReconstructionService و run_reconstruction_recovery؛ emission رویداد در نقاط terminal؛
                      خروجی‌های پکیج (__init__.py). هیچ تغییر در رفتار Frozen.
Out of Scope:         Extraction/OCR/VLM | S2/dedup سند | audit سطح attempt (deferred) | retention (DEF4) | تغییر Capture Store یا ReconstructionStore
Files / Components:   ایجاد: kandoo/src/reconstruction/evidence.py + kandoo/src/reconstruction/tests/{ev_helpers.py, test_evidence_store.py, test_evidence_binding.py, test_evidence_chain.py, test_evidence_e2e.py}
                      تغییر (افزودنی، بدون تغییر رفتار): service.py، recovery.py، __init__.py
Forbidden Actions:    انتخاب DB در سطح معماری | UPDATE/DELETE روی evidence log | افزودن محتوا به evidence | باز کردن Deferred | تغییر رفتار Frozen WP-2.1/WP-1.1
Dependencies:         T-2.2.1 (DONE)
Expected Deliverables: Evidence Store + binding + verified read + اتصال غیرمخرب + تست‌های هم‌مسیر
Tests:                AC-2.2.1 (دوام + restart) | AC-2.2.2 (tile/fingerprint/binding در هر دو فرمت) | AC-2.2.3 (ماتریس دستکاری: جهش/حذف/لنگر/درج + همروندی ۸ نخ) | AC-2.2.4 (ساختاری no-content) | AC-2.2.5 (شکست evidence بدون تغییر outcome + issue) | AC-2.2.6 (ترتیب seq رویدادهای واقعی)
Acceptance Criteria:  مطابق AC-2.2.1..AC-2.2.6 در WP Register — راستی‌آزمایی با اجرای تست و ثبت شواهد
DoD:                  تست‌ها سبز | شواهد در Acceptance Register | انتخاب‌های delegated اعلام شده (OD-E1..OD-E6) | Registerها به‌روز
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-2.2-IMPL) | Evidence: kandoo/src/reconstruction/evidence.py + tests/test_evidence_store.py (۸) + test_evidence_binding.py (۷) + test_evidence_chain.py (۸) + test_evidence_e2e.py (۲) = ۲۵ تست | انتخاب‌های اعلامی طبق D-09: OD-E1 SQLite stdlib فایل مجزا (synchronous=FULL)؛ OD-E2 واژگان ۴ رویداد document-scoped؛ OD-E3 زنجیره sha256-v1 + genesis 0×64 + لنگر evidence_head هم‌تراکنش؛ OD-E4 spans_from_durable (فقط از وضعیت durable؛ قاعده framing/fallback)؛ OD-E5 recorder غیرمخرب با issue surfacing؛ OD-E6 ساعت واحد لایه | بدون Forbidden Action
```

---

## T-2.2.3 — Acceptance Closure WP-2.2

```text
Task ID:              T-2.2.3
Phase:                P2 — Reconstruction
Work Package:         WP-2.2
Objective:            اجرای کامل مجموعه تست هر ۶ AC، اجرای Smoke E2E واقعی evidence، جمع‌آوری شواهد،
                      و بستن Acceptance Register برای WP-2.2.
Context:              نقطه اتصال WP-2.2 به Gate فاز P2 (بستن Gate = تصمیم PM+QA/PO، خارج از دامنه این Task).
Locked Decisions:     D-02 | D-03 | D-09 | AC-2.2.6
Reference Documents:  kandoo/specs/WP-2.2-reconstruction-evidence-contract.md | kandoo/registers/acceptance-register.md | kandoo/registers/task-register.md
Inputs:               خروجی T-2.2.2 | Acceptance Register
Scope:                اجرای رگرسیون کامل سه لایه | اجرای هر سه Smoke | ثبت شواهد با مسیر | به‌روزرسانی Registerها
Out of Scope:         هر کد جدید | استخراج داده | بستن Gate فاز P2 | جعل evidence
Files / Components:   به‌روزرسانی Registerها (بدون کد جدید)
Forbidden Actions:    اعلام Gate بدون شواهد | هر تصمیم معماری | جعل evidence
Dependencies:         T-2.2.2 (DONE)
Expected Deliverables: گزارش شواهد کامل هر ۶ AC + Registerها به‌روز + وضعیت فاز P2
Tests:                pytest kandoo/src/capture/tests kandoo/src/reconstruction/tests (کامل) + run_smoke_evidence.py + run_smoke_reconstruction.py + run_smoke.py
Acceptance Criteria:  مطابق AC-2.2.1..AC-2.2.6 + بسته‌شدن رسمی ردیف‌های Acceptance Register مربوط به WP-2.2
DoD:                  همه ACها با شواهد بسته | Registerها به‌روز | گزارش نهایی WP-2.2 ارائه شده
Reporting Format:     گزارش استاندارد + جدول وضعیت نهایی ۶ AC با مسیر شواهد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-2.2-IMPL) | Evidence: kandoo/registers/acceptance-register.md (6/6 AC PASS با مسیر شواهد) + بازاجرای زنده: pytest → 126/126 PASSED (54 capture + 47 reconstruction + 25 evidence؛ 0.98s) + run_smoke_evidence.py → SMOKE OK (۶ گام) + run_smoke_reconstruction.py → SMOKE OK (۷ گام) + run_smoke.py → SMOKE OK (۵ گام) | Registerها به‌روز (Acceptance + Task + WP) | بدون Forbidden Action
```

---

## T-3.1.1 — Extraction Contract Specification (inline)

```text
Task ID:              T-3.1.1
Phase:                P3 — Extraction
Work Package:         WP-3.1
Objective:            تولید مشخصه Extraction به‌صورت minimal و inline (بدون فاز Design/Review جدا):
                      مرز ورودی (فقط DocumentReadSuccess — §7 قرارداد WP-2.1)، abstraction موتور
                      قابل‌تعویض و قرارداد C1..C5، مدل داده (SourceSpan/ExtractedField/ExtractionRecord/
                      Provenance طبق D-01)، INV-X-1:1، verified read، نگاشت AC، deferredها.
Context:              WP-3.1 اولین WP فاز P3 است و در Register فقط در سطح Index بود؛ طبق dispatch TM
                      decomposition فقط به اندازه لازم و inline انجام شد و بلافاصله ساخت واقعی آغاز گردید.
Locked Decisions:     D-01 | D-02 | D-03 | D-09 | AS-01
Reference Documents:  kandoo/registers/decision-register.md | kandoo/specs/WP-2.1-reconstruction-contract.md (§7) | kandoo/registers/work-package-register.md (WP-3.1)
Inputs:               AC-3.1.1..AC-3.1.6 در WP Register | الگوی قراردادهای WP-2.1/WP-2.2
Scope:                فقط سند مشخصه — kandoo/specs/WP-3.1-extraction-contract.md (v1.0-MVP، ۸ بخش)
Out of Scope:         هر کد در این Task | انتخاب OCR/VLM | نگاشت فیلد Canonical | Normalization
Files / Components:   ایجاد: kandoo/specs/WP-3.1-extraction-contract.md
Forbidden Actions:    انتخاب موتور واقعی | باز کردن Deferred | هر تصمیم معماری جدید | ایجاد فاز جداگانه طراحی
Dependencies:         WP-2.2 (DONE)
Expected Deliverables: SPEC-WP31-EXT v1.0-MVP
Tests:                N/A (سند) — اعتبارسنجی از مسیر پیاده‌سازی T-3.1.2
Acceptance Criteria:  قرارداد شامل مرز §7، قرارداد موتور، مدل داده، INV-X-1:1، verified read، نگاشت ۶ AC
DoD:                  سند موجود + سازگار با Frozen Decisions + mapping کامل ACها
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-3.1-IMPL) | Evidence: kandoo/specs/WP-3.1-extraction-contract.md | بدون Forbidden Action
```

---

## T-3.1.2 — Extraction Layer Implementation (model + engine + store + service)

```text
Task ID:              T-3.1.2
Phase:                P3 — Extraction
Work Package:         WP-3.1
Objective:            پیاده‌سازی واقعی زیرساخت Extraction: Document/Page → Extraction-ready input →
                      Extracted structured data — با ورودیِ فقط DocumentReadSuccess (مرز §7)،
                      ExtractionEngine ABC قابل‌تعویض + ReferenceDelimitedEngine قطعی، اعتبارسنجی
                      قرارداد موتور قبل از persistence، ExtractionStore دائمی با commit اتمیک،
                      INV-X-1:1 و verified extraction read (VOR).
Context:              بدون OCR/VLM و بدون انتخاب موتور واقعی (D-09)؛ بدون Normalization/Canonicalization/
                      Validation/Invoice؛ بدون تغییر Capture/Reconstruction؛ بدون S2/dedup (D-02/D-03).
Locked Decisions:     D-01 | D-02 | D-03 | D-09 | AS-01 | AC-3.1.1..AC-3.1.6
Reference Documents:  kandoo/specs/WP-3.1-extraction-contract.md | kandoo/src/reconstruction/{model,service}.py (Frozen — فقط مصرف) | kandoo/src/capture/s1.py (S1Service — reuse)
Inputs:               SPEC-WP31-EXT | ReconstructionService.read_document | S1Service (sha256-v1)
Scope:                model.py (Provenance/SourceSpan/ExtractedField/ExtractionRecord/ExtractionInput + outcomes جامع)؛
                      engine.py (ExtractionEngine ABC + ExtractionEngineError + ReferenceDelimitedEngine)؛
                      store.py (ExtractionStore: SQLite فایل مجزا، synchronous=FULL، commit اتمیک record+fields،
                      UNIQUE index روی triple، record_fingerprint، canonical_extraction_bytes، بدون UPDATE/DELETE)؛
                      service.py (ExtractionService: registry → verified read → ExtractionInput → engine →
                      validation C2..C5 → field_seq → commit؛ read_extraction با recompute fingerprint؛
                      extraction_ids_for_document؛ issue_reports)؛ __init__.py (خروجی‌های پکیج).
Out of Scope:         OCR/VLM | Normalization/Canonicalization/Validation/Invoice | S2/dedup | WP-3.2 evidence | retention | تغییر لایه‌های Frozen
Files / Components:   ایجاد: kandoo/src/extraction/{__init__.py, model.py, engine.py, store.py, service.py} + kandoo/src/extraction/tests/{conftest.py, ext_helpers.py, test_ext_engine.py, test_ext_store.py, test_ext_service.py, test_ext_read_path.py, test_ext_e2e.py} + kandoo/src/run_smoke_extraction.py
                      تغییر: هیچ فایل Frozen تغییر نکرد (capture/، reconstruction/، smokeهای قبلی دست‌نخورده)
Forbidden Actions:    انتخاب DB در سطح معماری | انتخاب OCR/VLM | هر تبدیل مقدار (normalized_value و امثالها ممنوع — تست ساختاری) | dedup فیلدها | خواندن موازی artifact خام | تغییر Capture/Reconstruction
Dependencies:         T-3.1.1 (DONE)
Expected Deliverables: Extraction Layer کامل + ۳۸ تست + Smoke ۶ گام
Tests:                AC-3.1.1 (traceability + restart) | AC-3.1.2 (stub engine جدا + ماتریس violation ۶ بردار + unknown engine) | AC-3.1.3 (slice decode == value در engine/service/e2e) | AC-3.1.4 (INV-X-1:1 + چند موتور + schema دیگر) | AC-3.1.5 (tamper matrix: field/record scalar/row deletion + refused + NO_VERDICT) | AC-3.1.6 (field-set/columns دقیق + EXTRACTED-only + رگرسیون کامل)
Acceptance Criteria:  مطابق AC-3.1.1..AC-3.1.6 در WP Register — راستی‌آزمایی با اجرای تست و ثبت شواهد
DoD:                  تست‌ها سبز | Smoke OK | انتخاب‌های delegated اعلامی (OD-X1..OD-X8) | Registerها به‌روز
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-3.1-IMPL) | Evidence: kandoo/src/extraction/ (۴ ماژول) + tests (۳۸: engine ۶ / store ۸ / service ۱۴ / read_path ۵ / e2e ۲ + conftest/helpers) + run_smoke_extraction.py | انتخاب‌های اعلامی طبق D-09: OD-X1 SQLite stdlib فایل مجزا (synchronous=FULL)؛ OD-X2 commit اتمیک record+fields → صفر residue، بدون recovery sweep؛ OD-X3 INV-X-1:1 با UNIQUE index؛ OD-X4 extraction_id = uuid4hex؛ OD-X5 record_fingerprint sha256-v1 روی canonical_extraction_bytes (VOR روی خواندن)؛ OD-X6 CHECK سطح storage: فقط provenance='EXTRACTED'؛ OD-X7 ساعت واحد لایه؛ OD-X8 بدون مسیر UPDATE/DELETE | رفع باگ در Build→Test→Fix: (۱) _KEY_OK باید frozenset بایتی‌ها باشد نه رشته‌ها؛ (۲) validation باید violation object برگرداند نه raise dataclass؛ (۳) fingerprint واقعی صفحه در stubهای تست | بدون Forbidden Action
```

---

## T-3.1.3 — Acceptance Closure WP-3.1

```text
Task ID:              T-3.1.3
Phase:                P3 — Extraction
Work Package:         WP-3.1
Objective:            اجرای کامل مجموعه تست هر ۶ AC، اجرای Smoke E2E واقعی extraction، اجرای رگرسیون
                      کامل سه لایه Frozen، جمع‌آوری شواهد، و بستن Acceptance Register برای WP-3.1.
Context:              بستن Gate فاز P3 خارج از دامنه این Task است (تصمیم PM+QA/PO).
Locked Decisions:     D-01 | D-09 | AC-3.1.6
Reference Documents:  kandoo/specs/WP-3.1-extraction-contract.md | kandoo/registers/acceptance-register.md | kandoo/registers/task-register.md
Inputs:               خروجی T-3.1.2 | Acceptance Register
Scope:                اجرای رگرسیون کامل چهار لایه | اجرای چهار Smoke | ثبت شواهد با مسیر | به‌روزرسانی Registerها
Out of Scope:         هر کد جدید | بستن Gate فاز P3 | جعل evidence
Files / Components:   به‌روزرسانی Registerها (بدون کد جدید)
Forbidden Actions:    اعلام Gate بدون شواهد | هر تصمیم معماری | جعل evidence
Dependencies:         T-3.1.2 (DONE)
Expected Deliverables: گزارش شواهد کامل هر ۶ AC + Registerها به‌روز + وضعیت فاز P3
Tests:                pytest kandoo/src/capture/tests kandoo/src/reconstruction/tests kandoo/src/extraction/tests (کامل) + run_smoke_extraction.py + run_smoke_evidence.py + run_smoke_reconstruction.py + run_smoke.py
Acceptance Criteria:  مطابق AC-3.1.1..AC-3.1.6 + بسته‌شدن رسمی ردیف‌های Acceptance Register مربوط به WP-3.1
DoD:                  همه ACها با شواهد بسته | Registerها به‌روز | گزارش نهایی WP-3.1 ارائه شده
Reporting Format:     گزارش استاندارد + جدول وضعیت نهایی ۶ AC با مسیر شواهد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-3.1-IMPL) | Evidence: kandoo/registers/acceptance-register.md (6/6 AC PASS با مسیر شواهد) + بازاجرای زنده: pytest → 164/164 PASSED (54 capture + 72 reconstruction + 38 extraction؛ Python 3.12.14 / pytest 9.0.2) + run_smoke_extraction.py → SMOKE OK (۶ گام) + run_smoke_evidence.py → SMOKE OK + run_smoke_reconstruction.py → SMOKE OK + run_smoke.py → SMOKE OK | Registerها به‌روز (Acceptance + Task + WP) | بدون Forbidden Action
```

---

## T-3.2.1 — Extraction Evidence Binding Contract Specification (inline)

```text
Task ID:              T-3.2.1
Phase:                P3 — Extraction
Work Package:         WP-3.2
Objective:            تعیین دقیق Scope و ACهای WP-3.2 از Registerها و تدوین مشخصه حداقلی inline (بدون فاز Design/Review جدید) و شروع فوری Build
Context:              WP-3.2 در Register فقط به‌صورت «در انتظار decompose» بود؛ طبق dispatch TM (قاعده ۱–۳) decomposition فقط inline و حداقلی، سپس بلافاصله ساخت واقعی
Locked Decisions:     D-01 | D-02 | D-03 | D-09 | AS-01
Reference Documents:  kandoo/specs/WP-3.1-extraction-contract.md (§8 — مصرف extraction_ids + spans) | kandoo/specs/WP-2.2-reconstruction-evidence-contract.md | kandoo/registers/work-package-register.md
Inputs:               WP Register (ردیف P3) | Acceptance Register | Contractهای فروزن WP-1.1/WP-2.1/WP-2.2/WP-3.1
Scope:                SPEC-WP32-EVB v1.0-MVP: verified extraction record → durable, tamper-evident Extraction Evidence Binding → per-field provable traceability | §2 محتوای یک binding (anchorهای extraction/document/capture + لنگر evidence + entries ساختاری) | §3 مسیر bind با راستی‌آزمایی کامل زنجیره | §4 read با VOR پنج‌حلقه‌ای | §5 مدل داده | §6 انتخاب‌های delegated (OD-B1..OD-B7) | §7 نگاشت ۴ AC | §8 Deferred
Out of Scope:         تغییر هر لایه فروزن | hook خودکار binding داخل extract() | داده‌های P4+ | هر چرخه Review جدید
Files / Components:   ایجاد: kandoo/specs/WP-3.2-evidence-binding-contract.md
Forbidden Actions:    جعل evidence | تعیین engine محصول | هر تصمیم در تضاد با Frozen Decisions
Dependencies:         WP-3.1 (DONE)
Expected Deliverables: Contract حداقلی قابل استناد + شروع فوری T-3.2.2
Tests:                N/A (سند) — اعتبارسنجی از مسیر پیاده‌سازی T-3.2.2
Acceptance Criteria:  مطابق AC-3.2.1..AC-3.2.4 در WP Register
DoD:                  Contract ثبت‌شده با نگاشت AC | شروع Build در همان dispatch
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-3.2-IMPL) | Evidence: kandoo/specs/WP-3.2-evidence-binding-contract.md (۸ بخش + OD-B1..OD-B7) | بدون Forbidden Action
```

---

## T-3.2.2 — Evidence Binding Layer Implementation (model + store + binder)

```text
Task ID:              T-3.2.2
Phase:                P3 — Extraction
Work Package:         WP-3.2
Objective:            ساخت واقعی لایه Evidence Binding: ذخیره‌گاه دائمی ضد دستکاری + binder سرویس با راستی‌آزمایی کامل زنجیره در bind و read
Context:              طبق dispatch TM: «اتصال قابل‌اثبات خروجی Extraction به Evidence/Document/Page و حفظ traceability تا source»؛ هر extracted field باید به Document/Page و source span/position حل شود
Locked Decisions:     D-01 | D-02 | D-03 | D-09 | SPEC-WP32-EVB
Reference Documents:  kandoo/specs/WP-3.2-evidence-binding-contract.md | kandoo/src/reconstruction/evidence.py (الگوی chain/head) | kandoo/src/extraction/store.py (الگوی canonical/atomic)
Inputs:               ExtractionService.read_extraction | ReconstructionService.read_document | EvidenceStore.read_document_evidence | S1Service (sha256-v1)
Scope:                binding_model.py (BindingFieldEntry ساختاری / ExtractionBindingRecord / BindingLink / ۶ outcome مسیر bind / ۴ outcome مسیر read / BindingChainReport / استثناهای صریح)؛
                      binding.py (ExtractionBindingStore: SQLite فایل مجزا، synchronous=FULL، BEGIN IMMEDIATE، commit اتمیک binding+entries، INV-B-1:1 با UNIQUE extraction_id،
                      binding_fingerprint sha256-v1 روی canonical_binding_bytes، hash chain + head anchor، verify_chain؛
                      ExtractionEvidenceBinder: bind_extraction با ۵ گate ترتیبی fail-closed، read_binding با VOR پنج‌حلقه‌ای و link attribution،
                      bindings_for_document، verify_chain، issue_reports)؛
                      __init__.py (فقط exportهای additive — صفر تغییر رفتار WP-3.1)
Out of Scope:         تغییر capture/ | تغییر reconstruction/ (شامل evidence.py — فقط read-only) | بازنویسی service/store/engine/model فاز 3.1 | هر داده value در binding | hook خودکار در extract()
Files / Components:   ایجاد: kandoo/src/extraction/binding_model.py + kandoo/src/extraction/binding.py + kandoo/src/extraction/tests/binding_helpers.py
                      تغییر: kandoo/src/extraction/__init__.py (exportهای additive) + kandoo/src/extraction/tests/conftest.py (fixtureهای additive)
Forbidden Actions:    تغییر کد Frozen | خواندن موازی artifact خام | افزودن event type به vocabulary فروزن WP-2.2 | نگهداری value_verbatim/value_encoding در binding | UPDATE/DELETE در store binding
Dependencies:         T-3.2.1 (DONE)
Expected Deliverables: Binding Layer کامل + ۳۶ تست + Smoke ۸ گام
Tests:                AC-3.2.1 (whole-chain bind + replay + ماتریس bind-path + zero residue) | AC-3.2.2 (provenance walk چهار حلقه‌ای + enumeration) | AC-3.2.3 (ماتریس read-path ۸ بردار با link attribution + NO_VERDICT + content-free) | AC-3.2.4 (restart + chain audit + concurrency ۸ thread + boundary ساختاری)
Acceptance Criteria:  مطابق AC-3.2.1..AC-3.2.4 در WP Register — راستی‌آزمایی با اجرای تست و ثبت شواهد
DoD:                  تست‌ها سبز | Smoke OK | انتخاب‌های delegated اعلامی (OD-B1..OD-B7) | Registerها به‌روز
Reporting Format:     گزارش استاندارد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-3.2-IMPL) | Evidence: kandoo/src/extraction/binding_model.py + binding.py (store + binder) + tests (۳۶: core ۱۰ / read_path ۱۵ / durability ۵ / boundary ۶ + binding_helpers) + run_smoke_binding.py (۸ گام) | انتخاب‌های اعلامی طبق D-09: OD-B1 SQLite stdlib فایل مجزا append-only؛ OD-B2 chain + head anchor به الگوی WP-2.2؛ OD-B3 binding_id=uuid4hex + seq با coherence guard؛ OD-B4 binding_fingerprint sha256-v1 روی canonical_binding_bytes؛ OD-B5 INV-B-1:1 با UNIQUE extraction_id؛ OD-B6 ساعت واحد لایه extraction؛ OD-B7 binding بدون value (فقط ساختاری — fidelity با join دو verified read اثبات می‌شود) | رفع باگ در Build→Test→Fix: (۱) crash به‌جای outcome صریح هنگام نبود evidence store → دو guard صریح EVIDENCE در هر دو مسیر؛ (۲) head-guard قبل از refusal در read (حذف دم هرگز «never bound» جلوه نمی‌کند)؛ (۳) rename متدهای chain store به public | بدون Forbidden Action
```

---

## T-3.2.3 — Acceptance Closure WP-3.2

```text
Task ID:              T-3.2.3
Phase:                P3 — Extraction
Work Package:         WP-3.2
Objective:            اجرای کامل مجموعه تست هر ۴ AC، اجرای Smoke E2E واقعی binding، اجرای رگرسیون کامل چهار لایه (سه لایه Frozen + extraction)، جمع‌آوری شواهد، و بستن Acceptance Register برای WP-3.2
Context:              بستن Gate فاز P3 خارج از دامنه این Task است (تصمیم PM+QA/PO)
Locked Decisions:     D-01 | D-09 | AC-3.2.4
Reference Documents:  kandoo/specs/WP-3.2-evidence-binding-contract.md | kandoo/registers/acceptance-register.md | kandoo/registers/task-register.md
Inputs:               خروجی T-3.2.2 | Acceptance Register
Scope:                اجرای رگرسیون کامل پنج‌گانه | اجرای پنج Smoke | ثبت شواهد با مسیر | به‌روزرسانی Registerها + src/README.md
Out of Scope:         هر کد جدید | بستن Gate فاز P3 | جعل evidence
Files / Components:   به‌روزرسانی Registerها + src/README.md (بدون کد جدید)
Forbidden Actions:    اعلام Gate بدون شواهد | هر تصمیم معماری | جعل evidence
Dependencies:         T-3.2.2 (DONE)
Expected Deliverables: گزارش شواهد کامل هر ۴ AC + Registerها به‌روز + وضعیت فاز P3
Tests:                pytest kandoo/src/capture/tests kandoo/src/reconstruction/tests kandoo/src/extraction/tests (کامل) + run_smoke_binding.py + run_smoke_extraction.py + run_smoke_evidence.py + run_smoke_reconstruction.py + run_smoke.py
Acceptance Criteria:  مطابق AC-3.2.1..AC-3.2.4 + بسته‌شدن رسمی ردیف‌های Acceptance Register مربوط به WP-3.2
DoD:                  همه ACها با شواهد بسته | Registerها به‌روز | گزارش نهایی WP-3.2 ارائه شده
Reporting Format:     گزارش استاندارد + جدول وضعیت نهایی ۴ AC با مسیر شواهد
Status:               DONE — 2026-10-01 (dispatch یکپارچه WP-3.2-IMPL) | Evidence: kandoo/registers/acceptance-register.md (4/4 AC PASS با مسیر شواهد) + بازاجرای زنده: pytest → 200/200 PASSED (54 capture + 72 reconstruction + 38 extraction + 36 binding؛ Python 3.12.14 / pytest 9.0.2) + run_smoke_binding.py → SMOKE OK (۸ گام) + run_smoke_extraction.py → SMOKE OK + run_smoke_evidence.py → SMOKE OK + run_smoke_reconstruction.py → SMOKE OK + run_smoke.py → SMOKE OK | Registerها به‌روز (Acceptance + Task + WP + README) | بدون Forbidden Action
```

---

## T-4.1.1 — Normalization Contract Specification

```text
Task ID:              T-4.1.1
Phase:                P4 — Normalization
Work Package:         WP-4.1
Objective:            تولید مشخصه (Contract) Normalization به‌صورت implementation-oriented:
                      ورودی (verified extraction read به‌عنوان تنها مسیر)، خروجی (NormalizedField/Record)،
                      قواعد deterministic (control gate → NFC → trim → kind rule)، واژگان وضعیت
                      (NORMALIZED/DEFERRED/REJECTED + reason codes)، قطعیت، versioning،
                      persistence (INV-N-1:1 + VOR)، provenance (relay D-01)، non-goals صریح.
Status:               ✅ DONE (2026-10-01 — inline طبق dispatch TM؛ بدون فاز طراحی جدید)
Locked Decisions:     D-01 | D-02/D-03 (untouched) | D-09 | AS-01
Reference Documents:  kandoo/specs/WP-3.1-extraction-contract.md §2 | kandoo/specs/WP-3.2-evidence-binding-contract.md
Output:               kandoo/specs/WP-4.1-normalization-contract.md (v1.0-MVP — §1..§11 شامل OD-N1..OD-N8)
Out of Scope:         هر کد در این Task | Canonical field mapping (P6) | DERIVED (WP-4.2)
Evidence:             SPEC-WP41-NORM §10 (AC mapping) + §11 (test expectations)
```

## T-4.1.2 — Normalization Layer Implementation + Test Suite

```text
Task ID:              T-4.1.2
Phase:                P4 — Normalization
Work Package:         WP-4.1
Objective:            پیاده‌سازی واقعی لایه Normalization طبق SPEC-WP41-NORM:
                      model.py (وضعیت‌ها/outcomeها)، rules.py (seam قابل‌تعویض + ReferenceNormalizationRulesV1)،
                      store.py (SQLite فایل مجزا، commit اتمیک، INV-N-1:1، fingerprint، بدون UPDATE/DELETE)،
                      service.py (normalize/read_normalization/enumeration با VOR) + تست‌های جامع رفتاری.
Status:               ✅ DONE (2026-10-01 — Build → Test → Fix → Test: 84/84 PASS)
Locked Decisions:     D-01 (relay فقط EXTRACTED — CHECK سطح storage) | D-09 (OD-N1..OD-N8) | AS-01
Implementation Notes: kandoo/src/normalization/{model,rules,store,service,__init__}.py —
                      OD-N1 فایل DB مجزا synchronous=FULL | OD-N2 commit اتمیک صفر residue |
                      OD-N3 INV-N-1:1 + UNIQUE backstop | OD-N4 uuid4 + ساعت واحد |
                      OD-N5 fingerprint sha256-v1 (reuse S1Service) | OD-N6 gates سطح storage |
                      OD-N7 بدون UPDATE/DELETE | OD-N8 ruleset مرجع = انتخاب اجراپذیری MVP
Tests:                kandoo/src/normalization/tests/ (۸۴ تست): test_norm_rules.py (۳۱) +
                      test_norm_service.py (۱۲) + test_norm_read_path.py (۷) +
                      test_norm_durability.py (۸) + test_norm_boundary.py (۸) + test_norm_e2e.py (۴)
                      + norm_helpers.py/conftest.py | پوشش کامل ۱۶ محور dispatch (§12)
Out of Scope:         Canonicalization/identity/fuzzy | DERIVED | موتور جدید | تغییر لایه‌های Frozen
Evidence:             pytest kandoo/src/normalization/tests → 84/84 PASSED؛ رگرسیون کامل 284/284
```

## T-4.1.3 — Smoke E2E + Register Updates

```text
Task ID:              T-4.1.3
Phase:                P4 — Normalization
Work Package:         WP-4.1
Objective:            Smoke واقعی end-to-end: Extraction (frozen) → Binding (frozen) →
                      Normalization → verified reload → provenance walk تا Capture S1 →
                      idempotency → DEFERRED/REJECTED صریح → tamper detection؛
                      سپس به‌روزرسانی نتیجه‌محور Registerها.
Status:               ✅ DONE (2026-10-01 — run_smoke_normalization.py: 8/8 گام SMOKE OK)
Implementation Notes: kandoo/src/run_smoke_normalization.py — ۸ گام (extract/bind/normalize/
                      provenance walk/idempotency/rejection/restart/tamper)؛ رگرسیون ۵ Smoke قبلی OK
Evidence:             SMOKE OK × ۶ (پنج Smoke Frozen + Smoke جدید) | رگرسیون کامل 284/284 PASSED
Out of Scope:         Canonicalization (smoke فقط readiness برای Gate بعدی را اثبات می‌کند)
```

## T-4.1.4 — Pre-Freeze Boundary Clarification (DEFERRED ≠ UNRESOLVED, DERIVED boundary)

```text
Task ID:              T-4.1.4
Phase:                P4 — Normalization
Work Package:         WP-4.1
Objective:            اصلاح نهایی پیش از Freeze (dispatch PO/TM 2026-10-05): شفاف‌سازی معنایی
                      DEFERRED در WP-4.1 به‌عنوان وضعیتِ «لایهٔ Normalization» (DEFERRED ≠
                      UNRESOLVED؛ WP-4.1 هرگز UNRESOLVED نمی‌سازد/نسبت نمی‌دهد/استنتاج/حل
                      نمی‌کند) + تأیید صریح مرز DERIVED (بدون محاسبهٔ DERIVED، بدون محاسبهٔ
                      unit_amount از فیلدهای دیگر، بدون arithmetic معنایی، بدون استنتاج
                      مقادیر business) + تست‌های مرزی متمرکز + رگرسیون کامل + بستهٔ تحویل کامل.
Status:               ✅ DONE (2026-10-05 — WP-4.1-FREEZE-CORR؛ رفتار قطعی normalization تغییر نکرد)
Implementation Notes: SPEC-WP41-NORM §4.1/§4.2 + سرصفحه Clarification اضافه شد (بدون تغییر
                      هیچ rule/grammar/status/mapping/persistence) | تست مرزی جدید:
                      kandoo/src/normalization/tests/test_norm_freeze_boundary.py (۸ تست:
                      عدد مبهم/ناقص، تاریخ پشتیبانی‌نشده، empty/whitespace-only → DEFERRED و
                      هرگز UNRESOLVED؛ sweep دادهٔ durable بدون هر datum UNRESOLVED؛ بدون
                      مقادیر DERIVED + رد ساختاری DERIVED/UNRESOLVED در storage gate؛ بدون
                      محاسبهٔ unit_amount / بدون فیلد جعلی؛ قطعیت رفتار قبلی دست‌نخورده) |
                      README/Registers هم‌سازگار شدند.
Out of Scope:         WP-4.2 شروع نشد | هیچ قرارداد Frozen P1–P3 تغییر نکرد | هیچ رفتار موجود
                      ضعیف/حذف نشد
Evidence:             pytest kandoo/src/normalization/tests → 92/92 PASSED (84 قبلی + 8 مرزی)؛
                      رگرسیون کامل 292/292 PASSED (54 capture + 72 reconstruction + 74
                      extraction [38 extraction + 36 binding] + 92 normalization)؛
                      SMOKE OK × ۶ (شامل run_smoke_normalization.py ۸ گام)
```

## T-4.1.5 — WP-4.1 Formal Freeze (Phase Governance)

```text
Task ID:              T-4.1.5
Phase:                P4 — Normalization
Work Package:         WP-4.1
Objective:            انتقال رسمی وضعیت WP-4.1 به FROZEN در Registerهای لازم به دستور PO/TM
                      (2026-10-05) — بدون هیچ تغییر رفتاری در کد، بدون بازکردن P1/P2/P3 یا
                      Canonical Invoice v1، بدون شروع WP-4.2؛ حفظ کامل Acceptance evidence.
Status:               ✅ DONE (2026-10-05 — contradiction واقعی وجود نداشت)
Implementation Notes: REG-WPR (Phase Index P4 → FROZEN + WP-4.1 Status → FROZEN) | REG-AR
                      (freeze note — evidence حفظ شد) | src/README.md (header FROZEN) |
                      T-4.1.5 فقط governance است — کد P4.1 لمس نشد.
Out of Scope:         هر تغییر کد | بازکردن هر لایه Frozen | decomposition یا coding WP-4.2
Evidence:             رگرسیون کامل مجدداً اجرا شد (اعداد در گزارش Freeze) + بستهٔ تحویل کامل
                      پس از Freeze بازتولید و verify شد (Manifest جدید)
```

## T-4.2.1 — WP-4.2 Implementation Contract (Scope → SPEC)

```text
Task ID:              T-4.2.1
Phase:                P4 — Normalization
Work Package:         WP-4.2
Objective:            تبدیل Scope مصوب ثبت‌شدهٔ WP-4.2 (rescoped 2026-10-05) به implementation
                      contract الزام‌آور — بدون تغییر هیچ تصمیم Frozen (D-01/D-08/D-09/AS-01)
Status:               ✅ DONE (2026-10-06)
Implementation Notes: SPEC-WP42-DER v1.0-MVP (kandoo/specs/WP-4.2-derivation-contract.md،
                      §1..§13) — شامل واژگان outcome (DERIVED | NOT_DERIVABLE/
                      mechanism-DEFERRED | UNRESOLVED=P5) با تعریف دقیق و غیرمبهم تفاوت
                      DEFERRED لایهٔ P4.1 (status فیلد) و DEFERRED سطح mechanism P4.2
                      (outcome refusal فرمول) — هر دو بدون مقدار و هرگز UNRESOLVED
Out of Scope:         هر تغییر رفتاری در لایه‌های Frozen P1–P4.1
Evidence:             kandoo/specs/WP-4.2-derivation-contract.md
```

## T-4.2.2 — WP-4.2 Implementation (Formula Registry + Exact Arithmetic + Store + Service)

```text
Task ID:              T-4.2.2
Phase:                P4 — Normalization
Work Package:         WP-4.2
Objective:            Build واقعی مکانیزم derivation: فرمول‌ریجیstry اعلانی versioned
                      fingerprinted، arithmetic دقیق بدون float/rounding، persistence
                      append-only با INV-D-1:1 و VOR، integration واقعی با WP-4.1
                      (verified read) و WP-3.2 (binding fail-closed)، traceability کامل
Status:               ✅ DONE (2026-10-06)
Implementation Notes: kandoo/src/derivation/{model,arithmetic,formulas,store,service,
                      __init__}.py — ReferenceDerivationFormulasV1 دقیقاً یک فرمول
                      (total.gross = ADD(total.net, tax.amount) v1)؛ DIV فقط terminating؛
                      singleton slot resolution NORMALIZED-only؛ output-present gate؛
                      pointer pattern (بدون کپی مقدار)؛ SQLite مجزا synchronous=FULL؛
                      commit اتمیک؛ CHECK output_provenance='DERIVED' فقط؛ بدون
                      UPDATE/DELETE؛ derive/read_derivation/trace_derivation/
                      derivations_for_normalization/issue_reports
Out of Scope:         unit_amount عمومی | grouping/association | هر تفسیر semantic/
                      business | تولید/حل UNRESOLVED | ساخت Sale/Invoice/Digital Invoice
Evidence:             kandoo/src/derivation/ + run_smoke_derivation.py (۸ گام SMOKE OK)
```

## T-4.2.3 — WP-4.2 Test Suite (۱۸ محور الزامی dispatch)

```text
Task ID:              T-4.2.3
Phase:                P4 — Normalization
Work Package:         WP-4.2
Objective:            تست رفتاری واقعی هر ۱۸ محور الزامی dispatch — بدون coverage صوری؛
                      بدون تضعیف هیچ تست موجود
Status:               ✅ DONE (2026-10-06 — 101/101 PASSED)
Implementation Notes: 7 فایل/101 تست: arithmetic (۱۶) | formulas (۱۹) | service (۲۴) |
                      read_path (۱۱) | durability (۸) | trace (۸) | boundary (۱۵) —
                      اثبات no-float در سطح AST (صفر float literal/call در کل بسته) +
                      عدم eval/exec/__import__ + import allowlist + صفر coupling به
                      Engine + sweep دادهٔ durable بدون UNRESOLVED + storage-gate
                      UNRESOLVED/EXTRACTED → IntegrityError
Out of Scope:         —
Evidence:             P4.2 = 101/101 PASSED (Python 3.12.14 / pytest 9.0.2)؛
                      run_smoke_derivation.py SMOKE OK (۸ گام)
```

## T-4.2.4 — WP-4.2 Regression + Registers + Delivery

```text
Task ID:              T-4.2.4
Phase:                P4 — Normalization
Work Package:         WP-4.2
Objective:            رگرسیون کامل زنده با اعداد واقعی + به‌روزرسانی Registerها
                      (WPR/TR/AR) + src/README.md + commit منطقی + بستهٔ کامل تحویل
                      (archive + MANIFEST-SHA256.txt + independent verify)
Status:               ✅ DONE (2026-10-06)
Implementation Notes: رگرسیون کامل = 393/393 PASSED (54+72+74+92+101)؛ SMOKE OK × ۷ |
                      فقط فایل‌های جدید به کد اضافه شد — صفر تغییر P1–P4.1 |
                      archive کامل پروژه + manifest بازتولید و مستقل verify شد
Out of Scope:         git push (درخواست نشده) | شروع WP بعدی
Evidence:             گزارش نهایی WP-4.2 (بخش Tests/Regression/Archive) + worklog
```

---

## T-5.1.1 — WP-5.1 Implementation Contract (SPEC-WP51-VAL)

```text
Task ID:              T-5.1.1
Phase:                P5 — Validation
Work Package:         WP-5.1
Objective:            تبدیل scope dispatch اجرایی (R1/R2 Validation Engine) به
                      implementation contract الزام‌آور — بدون Architecture Loop جدید و
                      بدون reopen لایه‌های Frozen
Status:               ✅ DONE (2026-10-07)
Implementation Notes: SPEC-WP51-VAL v1.0-MVP (§1..§13) تولید شد — rule registry
                      اعلانی، R1 (presence/exact-consistency) و R2
                      (tolerated-equality/rounded-equality)، rounding semantics
                      دقیق D-08 (بدون float، بدون implicit)، واژگان outcome
                      (VALID/INVALID/DEFERRED؛ UNRESOLVED ممنوع)، persistence
                      OD-V1..OD-V7، provenance chain، AC mapping، test axes
Locked Decisions:     D-01 | D-08 | D-09 | AD-02 | AD-04 | AS-01 | AS-03
Reference Documents:  kandoo/registers/decision-register.md | kandoo/specs/WP-4.2-derivation-contract.md | kandoo/specs/WP-4.1-normalization-contract.md
Evidence:             kandoo/specs/WP-5.1-validation-contract.md
Out of Scope:         هر تغییر در لایه‌های Frozen | هر انتخاب معماری جدید
```

---

## T-5.1.2 — WP-5.1 Implementation (code + persistence + smoke)

```text
Task ID:              T-5.1.2
Phase:                P5 — Validation
Work Package:         WP-5.1
Objective:            پیاده‌سازی واقعی Validation Engine طبق SPEC-WP51-VAL — کد +
                      persistence + provenance + smoke، بدون design report
Status:               ✅ DONE (2026-10-07)
Implementation Notes: kandoo/src/validation/{model,rounding,rules,store,service,
                      __init__}.py + run_smoke_validation.py (۸ گام) — Rule
                      Registry اعلانی/fingerprinted با validation fail-closed؛
                      R1/R2 rule types؛ rounding دقیق روی Fraction با ۵ mode
                      اعلانی و audit record بازتولیدپذیر؛ ValidationStore با
                      INV-V-1:1 و CHECK gates (UNRESOLVED structurally
                      impossible؛ R1 هرگز round نمی‌کند)؛ ValidationService با
                      مسیر ورودی فقط-verified (WP-4.1 VOR + WP-4.2 service) و
                      trace_validation کامل (شامل sub-chain WP-4.2 برای ورودی‌های
                      DERIVED)
Locked Decisions:     D-01 | D-08 | D-09 (OD-V1..OD-V11) | AS-01
Evidence:             kandoo/src/validation/ + kandoo/src/run_smoke_validation.py (SMOKE OK)
Out of Scope:         Canonicalization | State Machine (WP-5.2) | ایجاد value
```

---

## T-5.1.3 — WP-5.1 Test Suite (behavior, not line coverage)

```text
Task ID:              T-5.1.3
Phase:                P5 — Validation
Work Package:         WP-5.1
Objective:            تست‌های رفتاری واقعی برای هر ۲۰ محور الزامی dispatch +
                      اثبات ساختاری مرزها (AST/gates) + رگرسیون کامل
Status:               ✅ DONE (2026-10-07) — 172/172 PASSED
Implementation Notes: 8 فایل — test_val_rules (۳۰) | test_val_rounding (۲۴) |
                      test_val_service (۳۷) | test_val_read_path (۱۴) |
                      test_val_durability (۷) | test_val_trace (۹) |
                      test_val_boundary (۳۴) | test_val_e2e (۴)؛ AST scan: صفر
                      float literal/call، صفر eval/exec/compile/__import__، import
                      allowlist، صفر engine symbol؛ رفع‌های محصور در فایل‌های جدید
                      WP-5.1 (۷ iteration مستند در REG-WPR §WP-5.1)
Locked Decisions:     D-08 (rounding axes) | D-01 (no UNRESOLVED)
Evidence:             kandoo/src/validation/tests/ + خروجی pytest (172 passed)
Out of Scope:         تضعیف/حذف هر تست موجود
```

---

## T-5.1.4 — Final Verification, Governance, Delivery

```text
Task ID:              T-5.1.4
Phase:                P5 — Validation
Work Package:         WP-5.1
Objective:            رگرسیون کامل زنده + تمام smokeها + ثبت Registerها (WPR/TR/AR)
                      + src/README.md + worklog + commit منطقی + archive کامل با
                      MANIFEST-SHA256.txt و independent verification
Status:               ✅ DONE (2026-10-07)
Implementation Notes: رگرسیون کامل = 565/565 PASSED (54+72+74+92+101+172)؛ SMOKE OK
                      × ۸ (شامل run_smoke_validation.py)؛ Frozen P1–P4.2
                      untouched (git diff = صفر)؛ known pre-existing flake در تست
                      concurrency Frozen P3 مستند شد (خارج از دامنه، reopen نشد)؛
                      archive کامل + manifest بازتولید و مستقل verify شد
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection
Evidence:             REG-WPR §WP-5.1 | REG-AR §WP-5.1 | worklog | MANIFEST-SHA256.txt
Out of Scope:         git push (درخواست نشده) | شروع WP بعدی
```

---

## T-5.2.1 — WP-5.2 Implementation Contract (SPEC-WP52-VSM)

```text
Task ID:              T-5.2.1
Phase:                P5 — Validation
Work Package:         WP-5.2
Objective:            تبدیل scope dispatch (WP-5.2 — Validation State Machine +
                      REVIEW Queue — BUILD واقعی) به implementation contract الزام‌آور
Status:               ✅ DONE (2026-10-07)
Implementation Notes: kandoo/specs/WP-5.2-validation-domain-contract.md
                      (SPEC-WP52-VSM v1.0-MVP §1..§13) — واژگان عیناً Frozen
                      (AS-03/AD-04/CL-1 + dispatch: VALID/INVALID/DEFERRED/
                      UNRESOLVED + REVIEW/REJECT)؛ جدول transition اعلانی T1..T5 با
                      لنگر Frozen هر route؛ UNRESOLVED field-level فقط D-01؛ REVIEW
                      queue durable/idempotent/append-only؛ persistence OD-S1..S7؛
                      provenance chain؛ OD-S8..S14 (delegated details اعلانی).
                      Baseline note: سند فیزیکی Canonical Invoice v1 هنوز commit
                      نشده (MNT-1)؛ Decision Register بازنمایی معتبر self-contained
                      است — contradiction واقعی یافت نشد؛ STOP لازم نشد.
Locked Decisions:     AS-03 | AD-04 | D-01 | D-03 | D-08 | D-09 | AS-01 | SPEC-WP51-VAL
Evidence:             kandoo/specs/WP-5.2-validation-domain-contract.md
Out of Scope:         هر کد رفتاری | تغییر Frozen P1–P5.1 | بازتعریف stateها
```

---

## T-5.2.2 — WP-5.2 Implementation (State Machine + REVIEW Queue)

```text
Task ID:              T-5.2.2
Phase:                P5 — Validation
Work Package:         WP-5.2
Objective:            پیاده‌سازی واقعی State Machine deterministic + ایجاد D-01
                      UNRESOLVED + REVIEW Queue durable + persistence + provenance
Status:               ✅ DONE (2026-10-07)
Implementation Notes: kandoo/src/validation_domain/{model,machine,store,service,
                      __init__}.py + run_smoke_validation_domain.py (۸ گام) —
                      machine.py خالص (transition function T1..T5 اولویت اعلانی +
                      project_fields D-01 + ruleset fingerprint sha256-v1)؛
                      store.py ۵ جدول با CHECK gates (state/disposition
                      consistency؛ projection shape؛ single-CLOSE partial UNIQUE)
                      و INV-S-1:1 / INV-R-1:1؛ service.py فقط مسیرهای verified
                      (P5.1 VOR + WP-4.1 VOR + registry fingerprint check) با
                      completeness gate؛ event hash-chain با status مشتق؛
                      trace_domain_state با sub-walkهای کل-زنجیرهٔ WP-5.1
Locked Decisions:     AS-03 | AD-04 | D-01 | D-03 | D-08 | D-09 (OD-S1..S14)
Evidence:             kandoo/src/validation_domain/ + kandoo/src/run_smoke_validation_domain.py (SMOKE OK)
Out of Scope:         Canonicalization | semantic resolution | اجرای P5.1 | تغییر Frozen
```

---

## T-5.2.3 — WP-5.2 Test Suite (behavior, not line coverage)

```text
Task ID:              T-5.2.3
Phase:                P5 — Validation
Work Package:         WP-5.2
Objective:            تست‌های رفتاری واقعی برای هر ۲۰ محور الزامی dispatch +
                      اثبات ساختاری مرزها (AST/gates/sweeps) + رگرسیون کامل
Status:               ✅ DONE (2026-10-07) — 125/125 PASSED
Implementation Notes: 8 فایل — test_vsm_state (۲۲) | test_vsm_unresolved (۸) |
                      test_vsm_review (۱۳) | test_vsm_service (۹) |
                      test_vsm_read_path (۱۸) | test_vsm_durability (۱۳) |
                      test_vsm_trace (۹) | test_vsm_boundary (۲۷) |
                      test_vsm_e2e (۳)؛ AST scan: صفر float literal/call، صفر
                      eval/exec/compile/__import__، import allowlist، صفر symbol
                      ممنوع business/canonicalization؛ AST: صفر UPDATE/DELETE SQL
                      در store/service؛ vocabulary sweep روی DB؛ CHECK-gate
                      refusals در برابر tamper مستقیم SQL؛ tamper matrix کامل
                      (state/refs/fields/item/event chain/deletion)؛ refusals:
                      incomplete/extra/empty/duplicate-keys/drift/integrity
Locked Decisions:     D-01 (UNRESOLVED meaning) | D-08 (T2 route) | AD-04 | AS-03
Evidence:             kandoo/src/validation_domain/tests/ + خروجی pytest (125 passed)
Out of Scope:         تضعیف/حذف هر تست موجود | اصلاح flake Frozen P3
```

---

## T-5.2.4 — Final Verification, Governance, Delivery

```text
Task ID:              T-5.2.4
Phase:                P5 — Validation
Work Package:         WP-5.2
Objective:            رگرسیون کامل زنده + تمام smokeها (قدیمی + جدید) + ثبت
                      Registerها (WPR/TR/AR) + src/README.md + worklog + commit
                      منطقی + archive کامل با MANIFEST-SHA256.txt و independent
                      verification
Status:               ✅ DONE (2026-10-07)
Implementation Notes: رگرسیون کامل = 690/690 PASSED (54 capture + 72
                      reconstruction + 74 extraction [38+36 binding] + 92
                      normalization + 101 derivation + 172 validation + 125
                      validation_domain؛ Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK
                      × ۹ (۸ قبلی + run_smoke_validation_domain.py — ۸ گام)؛
                      Frozen P1–P5.1 untouched (git diff = صفر)؛ known
                      pre-existing flake P3 در اجرای رسمی PASS شد (طبق dispatch
                      دست نخورد)؛ archive کامل + manifest بازتولید و مستقل verify شد
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection
Evidence:             REG-WPR §WP-5.2 | REG-AR §WP-5.2 | worklog | MANIFEST-SHA256.txt
Out of Scope:         git push (درخواست نشده) | شروع WP بعدی
```

---

## T-6.1.1 — WP-6.1 Implementation Contract (SPEC-WP61-CANGATE)

```text
Task ID:              T-6.1.1
Phase:                P6 — Canonicalization
Work Package:         WP-6.1
Objective:            تبدیل scope dispatch (WP-6.1 — Canonicalization Gate — BUILD
                      واقعی) به implementation contract الزام‌آور
Status:               ✅ DONE (2026-10-07)
Implementation Notes: kandoo/specs/WP-6.1-canonicalization-gate-contract.md
                      (SPEC-WP61-CANGATE v1.0-MVP §1..§12) — تصمیم‌های G0..G6 با
                      لنگر Frozen (AD-04/D-01/D-02/D-03/D-08)؛ واژگان تصمیم عیناً
                      dispatch §14 (ACCEPTED/REJECTED/REVIEW/ALREADY_CANONICALIZED)
                      و origins عیناً dispatch §7 (KANDOO_SALE/HOLOO_CAPTURE/
                      OTHER_POS_CAPTURE)؛ identity resolution فقط مسیر deterministic
                      S2 (D-02) با CAPTURE_SCOPED صریح و adapter path RESERVED؛
                      admission record source-independent؛ gate REVIEW queue؛
                      persistence OD-C1..C7؛ provenance chain؛ OD-G1..G10 اعلانی.
                      Baseline note: سند فیزیکی Canonical Invoice v1 commit نشده
                      (MNT-1) — Decision Register + dispatch بازنمایی معتبر
                      self-contained؛ contradiction واقعی یافت نشد؛ STOP لازم نشد.
Locked Decisions:     D-02 | D-03 | AD-04 | AS-03 | AS-04 | AS-01 | AS-02 | D-01 |
                      D-08 | D-09 | D-04 | AD-01 | SPEC-WP52-VSM
Evidence:             kandoo/specs/WP-6.1-canonicalization-gate-contract.md
Out of Scope:         هر کد رفتاری | تغییر Frozen P1–P5.2 | Canonical Assembly
                      (WP-6.2) | بازتعریف state/decision
```

---

## T-6.1.2 — WP-6.1 Implementation (Gate + Identity + Admission Store)

```text
Task ID:              T-6.1.2
Phase:                P6 — Canonicalization
Work Package:         WP-6.1
Objective:            پیاده‌سازی واقعی Gate/decision engine + identity resolution +
                      Canonical Invoice admission + persistence + provenance
Status:               ✅ DONE (2026-10-07)
Implementation Notes: kandoo/src/canonicalization/{model,identity,gate,store,
                      service,__init__}.py + run_smoke_canonicalization.py (۸ گام) —
                      identity.py/gate.py خالص (بدون I/O)؛ store.py ۵ جدول با
                      CHECK gates (decision/origin/identity_class؛ ACCEPTED↔invoice؛
                      reason codes؛ single-CLOSE partial UNIQUE) و backstopهای
                      INV-D-1:1 / INV-CI-1:1 / INV-GR-1:1 + UNIQUE(capture_s1) +
                      UNIQUE(identity_fingerprint)؛ service.py فقط مسیرهای verified
                      (P5.2 read+trace، WP-4.1 VOR) با fail-closed V1→V4 قبل از هر
                      تصمیم؛ commit اتمیک (تصمیم+invoice+pointers+review item)؛
                      event hash-chain با status مشتق؛ trace_canonical_invoice
                      (کل-زنجیرهٔ P5.2 مصرف می‌شود، نه bypass)؛ بدون UPDATE/DELETE
Locked Decisions:     D-02 | D-03 | AD-04 | D-01 | D-08 | D-09 | D-04 (OD-C1..C7, OD-G1..G10)
Evidence:             kandoo/src/canonicalization/ + kandoo/src/run_smoke_canonicalization.py (SMOKE OK)
Out of Scope:         semantic resolution | fuzzy/AI matching | اجرای upstream |
                      Inventory/Sale/KPI/Customer mutation | تغییر Frozen P1–P5.2
```

---

## T-6.1.3 — WP-6.1 Test Suite (behavior, not line coverage)

```text
Task ID:              T-6.1.3
Phase:                P6 — Canonicalization
Work Package:         WP-6.1
Objective:            پوشش رفتاری همهٔ ۲۵ محور الزامی dispatch + AST checks
Status:               ✅ DONE (2026-10-07) — 112/112 PASSED
Implementation Notes: kandoo/src/canonicalization/tests/ — 9 فایل: conftest.py +
                      cg_helpers.py (stack کامل P1→P6.1؛ pages منحصربه‌فرد برای
                      capture-level dedup؛ BINDING اعلانی سه‌نقشی) |
                      test_cg_decision.py (۱۷: G0..G6، replay، priority، relay
                      verbatim، ارجاع OD-G9) | test_cg_identity.py (۱۸: S2 exact،
                      deterministic fingerprint، scope با declared origin،
                      incomplete/conflicting/undetermined، binding refusals،
                      value-honesty resolver، adapter RESERVED) |
                      test_cg_invoice.py (۱۵: origin preservation، source-
                      independence، immutability، tamper matrix، deterministic
                      fingerprint، INV-CI-1:1، no-canonicalization-without-Gate) |
                      test_cg_provenance.py (۱۰: trace تا Capture S1، broken chain
                      zero-residue، P4.2 DERIVED در sub-walks، pointer re-join) |
                      test_cg_idempotency.py (۹: state replay، capture replay،
                      definite duplicate ×3 captures، atomicity zero-residue،
                      UNIQUE backstops مستقیم SQL، restart) | test_cg_boundary.py
                      (۳۴: AST صفر float/eval/exec، import allowlist، صفر symbol
                      ممنوع fuzzy/matching/business، صفر UPDATE/DELETE SQL،
                      vocabulary sweeps، spy بدون اجرای upstream، row-count
                      stability لایه‌های Frozen، malformed input) |
                      test_cg_service.py (۹: determinism محتوا، engine-independence
                      ساختاری، e2e کامل، origin scope)
Locked Decisions:     D-02 | D-03 | AD-04 | D-01 | D-08 | D-09
Evidence:             kandoo/src/canonicalization/tests/ (112/112 PASSED)
Out of Scope:         تضعیف/حذف تست‌های موجود | performance optimization
```

---

## T-6.1.4 — WP-6.1 Verification + Governance + Delivery

```text
Task ID:              T-6.1.4
Phase:                P6 — Canonicalization
Work Package:         WP-6.1
Objective:            اجرای رسمی tests/regression/smokes + به‌روزرسانی registerها +
                      README + worklog + archive کامل + manifest + Git
Status:               ✅ DONE (2026-10-07)
Implementation Notes: P6.1 dedicated = 112/112 PASSED؛ رگرسیون کامل = 802/802
                      PASSED (54+72+74+92+101+172+125+112؛ Python 3.12.14 /
                      pytest 9.0.2)؛ SMOKE OK × ۱۰ (همه ۹ قبلی +
                      run_smoke_canonicalization.py — ۸ گام)؛ Frozen P1–P5.2
                      untouched (git diff = صفر)؛ flake ثبت‌شدهٔ P3 در اجرای رسمی
                      PASS + 5/5 تکرار مستقل (طبق dispatch دست نخورد)؛ registerها
                      (REG-WPR/REG-TR/REG-AR) + src/README.md + worklog به‌روز؛
                      archive کامل + MANIFEST-SHA256.txt بازتولید و مستقل verify شد
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection
Evidence:             REG-WPR §WP-6.1 | REG-AR §WP-6.1 | worklog | MANIFEST-SHA256.txt
Out of Scope:         git push (درخواست نشده) | شروع WP بعدی
```

---

## T-6.2.1 — WP-6.2 Contract Specification

```text
Task ID:              T-6.2.1
Phase:                P6 — Canonicalization
Work Package:         WP-6.2
Objective:            تولید SPEC-WP62-CANASM — قرارداد پیاده‌سازی Canonical Assembly + invoice_id Issuance
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/specs/WP-6.2-canonical-assembly-contract.md — §1..§12؛
                      نردبان A1..A6 (fail-closed)؛ field/line assembly بدون حدس
                      (AS-04 quote discipline؛ ساختار خط DECLARED — OD-A4)؛
                      issuance = مصرف verbatim هویت صادرهٔ Kandoo در P6.1
                      (OD-A1/D-02/OD-G8)؛ persistence OD-C1..C7؛ provenance §9؛
                      OD-A1..A10؛ MNT-1 رعایت شد (baseline غایب — registers +
                      dispatch منبع خودبسنده)
Locked Decisions:     D-01 | D-02 | D-03 | D-04 | D-06 | D-08 | D-09 | AD-02 | AD-03 |
                      AD-04/CL-1 | AS-01 | AS-02 | AS-03 | AS-04 | SPEC-WP61-CANGATE
Evidence:             kandoo/specs/WP-6.2-canonical-assembly-contract.md
Out of Scope:         هر تصمیم معماری جدید | بازتعریف واژگان Frozen | Digital Invoice (WP-10.x)
```

---

## T-6.2.2 — WP-6.2 Implementation (assembly engine + store + service)

```text
Task ID:              T-6.2.2
Phase:                P6 — Canonicalization
Work Package:         WP-6.2
Objective:            پیاده‌سازی واقعی Canonical Assembly + invoice_id Issuance
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/src/canonical_assembly/ — model.py (واژگان verbatim،
                      رکوردها، outcomeهای صریح) | assembly.py خالص (validate_line_binding،
                      declaration_bytes، resolve_declared_field، assemble_fields،
                      assemble_header_anchors، identity_anchor_payload (quote دقیق
                      OD-G4)، assemble_lines — بدون I/O/clock/randomness) | store.py
                      (۵ جدول، synchronous=FULL، commit اتمیک، INV-AI-1:1 + UNIQUE
                      backstops، CHECK gates، sha256-v1 + VOR، بدون UPDATE/DELETE) |
                      service.py (A1..A6 → replay gate → assembly → commit؛ read VOR؛
                      trace_assembled_invoice با re-join byte-identity) |
                      run_smoke_canonical_assembly.py (۶ گام)
Locked Decisions:     D-01 | D-02 | D-03 | D-04 | D-06 | D-09 | AD-02 | AD-04 | AS-03 | AS-04
Evidence:             kandoo/src/canonical_assembly/ (واردات و smoke سبز)
Out of Scope:         تغییر هر لایهٔ Frozen P1–P6.1 | هر اجرای upstream | هر UUID/random در لایه
```

---

## T-6.2.3 — WP-6.2 Test Suite (behavior, not line coverage)

```text
Task ID:              T-6.2.3
Phase:                P6 — Canonicalization
Work Package:         WP-6.2
Objective:            پوشش رفتاری همهٔ ۲۷ محور الزامی dispatch §13 + AST checks
Status:               ✅ DONE (2026-10-08) — 100/100 PASSED
Implementation Notes: kandoo/src/canonical_assembly/tests/ — 7 فایل: conftest.py +
                      ca_helpers.py (stack کامل P1→P6.2؛ corpus خط‌دار؛ LINE_BINDING
                      اعلانی) | test_ca_assembly.py (۲۵) | test_ca_service.py (۱۷:
                      e2e، non-ACCEPTED→هیچ invoice، spy مصرف P6.1، منع اجرای
                      upstream، determinism) | test_ca_invoice.py (۲۰: issuance/
                      immutability/tamper/backstopها) | test_ca_lines.py (۹:
                      ترتیب/absent/empty/duplicate) | test_ca_provenance.py (۹:
                      trace تا S1، broken chain، re-join byte-identity) |
                      test_ca_durability.py (۷: atomicity/restart/race/UNIQUE) |
                      test_ca_boundary.py (۱۳: AST بدون UPDATE/DELETE، بدون
                      uuid/random/float/eval/exec، allowlist، identifier sweep،
                      row-count stability Frozen)
Locked Decisions:     D-02 | D-03 | D-06 | AD-04 | AS-03 | AS-04 | D-09
Evidence:             kandoo/src/canonical_assembly/tests/ (100/100 PASSED)
Out of Scope:         تضعیف/حذف تست‌های موجود | performance optimization
```

---

## T-6.2.4 — WP-6.2 Verification + Governance + Delivery

```text
Task ID:              T-6.2.4
Phase:                P6 — Canonicalization
Work Package:         WP-6.2
Objective:            اجرای رسمی tests/regression/smokes + به‌روزرسانی registerها +
                      README + worklog + archive کامل + manifest + Git
Status:               ✅ DONE (2026-10-08)
Implementation Notes: P6.2 dedicated = 100/100 PASSED؛ رگرسیون کامل = 902/902
                      PASSED (54+72+74+92+101+172+125+112+100؛ Python 3.12.14 /
                      pytest 9.0.2)؛ SMOKE OK × ۱۱ (همه ۱۰ قبلی +
                      run_smoke_canonical_assembly.py — ۶ گام)؛ Frozen P1–P6.1
                      untouched (git diff = صفر)؛ flake ثبت‌شدهٔ P3 در اجرای رسمی
                      PASS (طبق dispatch دست‌نخورده)؛ registerها (REG-WPR/REG-TR/
                      REG-AR) + src/README.md + worklog به‌روز؛ archive کامل +
                      MANIFEST-SHA256.txt بازتولید و مستقل verify شد
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection
Evidence:             REG-WPR §WP-6.2 | REG-AR §WP-6.2 | worklog | MANIFEST-SHA256.txt
Out of Scope:         git push (درخواست نشده) | شروع WP بعدی
```

---

## T-7.1.1 — WP-7.1 Contract Specification

```text
Task ID:              T-7.1.1
Phase:                P7 — Duplicate / Idempotency
Work Package:         WP-7.1
Objective:            تولید SPEC-WP71-IDRES — قرارداد پیاده‌سازی Identity Resolution (S1/S2/CAPTURE_SCOPED)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/specs/WP-7.1-identity-resolution-contract.md — §1..§12؛
                      نردبان V1..V4 + جدول R0..R3 (fail-closed)؛ حالت‌های S1/S2/
                      CAPTURE_SCOPED صریح و durable؛ مصرف VERBATIM primitive فروزن
                      P6.1 (بدون فرمول جدید — OD-IR-G)؛ D-03 duplicate فقط exact
                      fingerprint بین captureهای متفاوت؛ persistence OD-IR1..IR7؛
                      provenance §9؛ OD-IR-A..J؛ MNT-1 رعایت شد (baseline غایب —
                      registers + dispatch منبع خودبسنده)
Locked Decisions:     D-01 | D-02 | D-03 | D-04 | D-08 | D-09 | AD-01 | AD-02 |
                      AD-04/CL-1 | AS-01 | AS-02 | AS-03 | AS-04 | SPEC-WP61-CANGATE
Evidence:             kandoo/specs/WP-7.1-identity-resolution-contract.md
Out of Scope:         هر تصمیم معماری جدید | بازتعریف واژگان Frozen | WP-7.2 | تغییر P6.1
```

---

## T-7.1.2 — WP-7.1 Implementation (resolver + store + service)

```text
Task ID:              T-7.1.2
Phase:                P7 — Duplicate / Idempotency
Work Package:         WP-7.1
Objective:            پیاده‌سازی واقعی Identity Resolution با مدل هویت Frozen
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/src/identity_resolution/ — model.py (واژگان verbatim:
                      S2|CAPTURE_SCOPED + S1 leg؛ رکوردها؛ outcomeهای صریح) |
                      resolver.py خالص (validate_declared_origin؛
                      binding_declaration_bytes/fingerprint؛ resolve_document_identity —
                      state gate بدون مصرف مقدار برای non-VALID + delegation به
                      primitive فروزن P6.1 با relay verbatim reasonها و حفظ
                      candidate evidence) | store.py (۳ جدول، synchronous=FULL، commit
                      اتمیک، INV-IR-S1:1 + INV-IR-DUP:1 backstops، CHECK gates،
                      sha256-v1 + VOR، بدون UPDATE/DELETE) | service.py (V1..V4 →
                      R0 replay recognition → R1 S2 attempt → R2 exact duplicate →
                      R3 commit؛ read VOR + structural gates) |
                      run_smoke_identity_resolution.py (۸ گام)
Locked Decisions:     D-01 | D-02 | D-03 | D-04 | D-09 | AD-02 | AD-04 | AS-02 | AS-03
Evidence:             kandoo/src/identity_resolution/ (واردات و smoke سبز)
Out of Scope:         تغییر هر لایهٔ Frozen P1–P6.2 | هر اجرای upstream | mint هر invoice_id
```

---

## T-7.1.3 — WP-7.1 Test Suite (behavior, not line coverage)

```text
Task ID:              T-7.1.3
Phase:                P7 — Duplicate / Idempotency
Work Package:         WP-7.1
Objective:            پوشش رفتاری محورهای الزامی dispatch §11-§13 (Caseهای A-F،
                      adversarial، concurrency) + AST checks
Status:               ✅ DONE (2026-10-08) — 108/108 PASSED (+3 تکرار مستقل 108/108)
Implementation Notes: kandoo/src/identity_resolution/tests/ — 6 فایل: conftest.py +
                      ir_helpers.py (stack کامل P1→P5.2 + identity؛ corpus هویتی؛
                      stateهای non-VALID با probe rules) | test_ir_resolution.py (۲۸) |
                      test_ir_idempotency.py (۱۹: Caseهای A-F + restart + drift + مرز
                      whitespace/serialization) | test_ir_durability.py (۲۴:
                      atomicity/zero-residue/restart/tamper matrix/backstopهای
                      CHECK+UNIQUE با SQL مستقیم) | test_ir_provenance.py (۱۱: spy
                      walk، broken chain، pointer discipline، re-join) |
                      test_ir_boundary.py (۱۴: AST صفر UPDATE/DELETE/random/hashlib،
                      allowlist، identifier sweep، reuse فرمول، row-count stability
                      Frozen، determinism بین stackها) | test_ir_service.py (۱۲:
                      refusal matrix، storage mapping، race ۸ thread با
                      thread-local store + ورودی verified ثابت، backstop UNIQUE)
Locked Decisions:     D-02 | D-03 | AD-04 | AS-03 | D-09
Evidence:             kandoo/src/identity_resolution/tests/ (108/108 PASSED)
Out of Scope:         تضعیف/حذف تست‌های موجود | تغییر رفتار concurrent لایه‌های Frozen | performance optimization
```

---

## T-7.1.4 — WP-7.1 Verification + Governance + Delivery

```text
Task ID:              T-7.1.4
Phase:                P7 — Duplicate / Idempotency
Work Package:         WP-7.1
Objective:            اجرای رسمی tests/regression/smokes + به‌روزرسانی registerها +
                      README + worklog + archive کامل + manifest + Git
Status:               ✅ DONE (2026-10-08)
Implementation Notes: P7.1 dedicated = 108/108 PASSED؛ رگرسیون کامل = 1010/1010
                      PASSED (54+72+74+92+101+172+125+112+100+108؛ Python 3.12.14 /
                      pytest 9.0.2)؛ SMOKE OK × ۱۲ (همه ۱۱ قبلی +
                      run_smoke_identity_resolution.py — ۸ گام)؛ Frozen P1–P6.2
                      untouched (git diff = صفر)؛ flake ثبت‌شدهٔ P3 در اجرای رسمی
                      PASS (طبق dispatch دست‌نخورده)؛ registerها (REG-WPR/REG-TR/
                      REG-AR) + src/README.md + worklog به‌روز؛ archive کامل +
                      MANIFEST-SHA256.txt بازتولید و مستقل verify شد
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection
Evidence:             REG-WPR §WP-7.1 | REG-AR §WP-7.1 | worklog | MANIFEST-SHA256.txt
Out of Scope:         git push (درخواست نشده) | شروع WP بعدی
```

---

## T-7.2.1 — WP-7.2 Contract Specification

```text
Task ID:              T-7.2.1
Phase:                P7 — Duplicate / Idempotency
Work Package:         WP-7.2
Objective:            تولید SPEC-WP72-DUPFLOW — قرارداد پیاده‌سازی Reprint & Duplicate Flows
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/specs/WP-7.2-reprint-duplicate-flows-contract.md — §1..§12؛
                      نردبان F1..F6 (fail-closed)؛ disposition دائمی per-capture با
                      INV-DF-1:1؛ واژگان جریان IDENTITY_ESTABLISHED |
                      DUPLICATE_RECOGNIZED (durable) + REPRINT_RECOGNIZED (فقط
                      فراخوانی)؛ مصرف VERBATIM سطح سرویس WP-7.1 (بدون هیچ منطق
                      هویتی — OD-DF-C)؛ باز-تأیید همهٔ identity facts لینک‌شده در
                      هر read (OD-DF-D)؛ persistence OD-DF1..DF7؛ MNT-1 رعایت شد
Locked Decisions:     D-01 | D-02 | D-03 | D-04 | D-09 | AD-01 | AD-02 |
                      AD-04/CL-1 | AS-01 | AS-02 | AS-03 | AS-04 | SPEC-WP71-IDRES |
                      SPEC-WP61-CANGATE (authority انحصاری canonicalization)
Evidence:             kandoo/specs/WP-7.2-reprint-duplicate-flows-contract.md
Out of Scope:         هر تصمیم معماری جدید | بازتعریف واژگان Frozen | بازکردن WP-7.1 | تغییر P6.1/P6.2
```

---

## T-7.2.2 — WP-7.2 Implementation (store + service)

```text
Task ID:              T-7.2.2
Phase:                P7 — Duplicate / Idempotency
Work Package:         WP-7.2
Objective:            پیاده‌سازی واقعی جریان‌های Reprint & Duplicate روی factهای دائمی WP-7.1
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/src/duplicate_flows/ — model.py (واژگان جریان؛
                      FlowDispositionRecord؛ outcomeهای صریح handle/read) |
                      store.py (جدول flow_dispositions؛ synchronous=FULL؛ commit اتمیک
                      تک‌ردیفی؛ UNIQUE(capture_s1) backstop؛ CHECK gates شکل
                      outcome/reference و scope/fingerprint؛ sha256-v1 از طریق سرویس
                      S1 — بدون hashlib؛ بدون UPDATE/DELETE) | service.py (handle با
                      نردبان F1..F6 — passthrough verbatim refusalها، delegation به
                      resolve() فروزن WP-7.1، F5 backfill قطعی از شکل durable، F6
                      برخورد همزمانی؛ read_disposition / read_disposition_by_id با
                      VOR + باز-تأیید لینک‌ها + structural gates بین-store‌ای؛
                      duplicates_of / dispositions) | بدون resolver.py طبق OD-DF-A |
                      run_smoke_duplicate_flows.py (۸ گام)
Locked Decisions:     D-01 | D-02 | D-03 | D-04 | D-09 | AD-02 | AD-04 | AS-02 | AS-03
Evidence:             kandoo/src/duplicate_flows/ (واردات و smoke سبز)
Out of Scope:         تغییر هر لایهٔ Frozen P1–P7.1 | هر اجرای upstream | تصمیم canonicalization | هر invoice_id / عملیات REVIEW
```

---

## T-7.2.3 — WP-7.2 Test Suite (behavior, not line coverage)

```text
Task ID:              T-7.2.3
Phase:                P7 — Duplicate / Idempotency
Work Package:         WP-7.2
Objective:            پوشش رفتاری کامل جریان‌ها — reprint / duplicate / delegation / durability / boundary
Status:               ✅ DONE (2026-10-08)
Implementation Notes: 6 فایل / 58 تست — test_df_reprint.py (۱۱) |
                      test_df_duplicate.py (۱۰) | test_df_service.py (۱۳) |
                      test_df_durability.py (۹) | test_df_boundary.py (۱۵) |
                      df_helpers.py (DuplicateFlowStack روی WP-7.1 stack verbatim +
                      corpusهای no-number متمایز) — محورها: reprint verbatim صفر-ردیف
                      (حتی بین-stateها و پس از restart)؛ drift refusal verbatim؛
                      definite duplicate با یک original + register؛ Case F/whitespace
                      طبق قرارداد فروزن؛ CAPTURE_SCOPED هرگز duplicate؛ F5 backfill
                      قطعی؛ tamper matrix (own row / hash-consistent forged →
                      structural gate / linked resolution / original)؛ CHECK/UNIQUE
                      backstops با SQL مستقیم؛ zero-residue؛ AST (صفر
                      UPDATE/DELETE/DROP/hashlib/random/float؛ import allowlist؛
                      uuid فقط bookkeeping)؛ row-count stability لایه‌های Frozen؛ spy
                      صفر اجرای upstream؛ race ۸-thread (الگوی WP-7.1: storeهای
                      thread-local + stubs inert) + race twin با یک original
Locked Decisions:     D-01 | D-02 | D-03 | D-09 | AD-04/CL-1 | AS-03
Evidence:             kandoo/src/duplicate_flows/tests/ (58/58 PASSED — 2 تکرار مستقل)
Out of Scope:         تغییر فایل‌های Frozen (حتی تست‌های Frozen) | پوشش line-based
```

---

## T-7.2.4 — WP-7.2 Verification + Governance + Delivery

```text
Task ID:              T-7.2.4
Phase:                P7 — Duplicate / Idempotency
Work Package:         WP-7.2
Objective:            اجرای رسمی tests/regression/smokes + به‌روزرسانی registerها + README + worklog + archive کامل + manifest + Git
Status:               ✅ DONE (2026-10-08)
Implementation Notes: P7.2 dedicated = 58/58 PASSED؛ رگرسیون کامل = 1067/1068 جمع‌کل
                      (1067 PASSED + 1 flake از پیش موجود) — اجرای خالص بدون flake =
                      1067/1067 PASSED (54+72+74+92+101+172+125+112+100+108+58؛
                      Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۱۳ (همه ۱۲ قبلی +
                      run_smoke_duplicate_flows.py — ۸ گام)؛ flake ثبت‌شده:
                      test_ir_provenance.py::test_no_raw_pipeline_values_are_stored
                      (suite فروزن WP-7.1 — وابسته به تاریخ UTC؛ برخورد created_at
                      کتاب‌نگاری با تاریخ corpus؛ بازتولید در worktree خالص HEAD
                      9d7f372 بدون کد WP-7.2 ⇒ از پیش موجود؛ pointer discipline
                      سالم؛ فایل Frozen طبق حکمرانی دست‌نخورده)؛ registerها
                      (REG-WPR/REG-TR/REG-AR) + src/README.md + worklog به‌روز؛
                      archive کامل + MANIFEST-SHA256.txt بازتولید و مستقل verify شد
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection
Evidence:             REG-WPR §WP-7.2 | REG-AR §WP-7.2 | worklog | MANIFEST-SHA256.txt
Out of Scope:         git push (درخواست نشده) | شروع WP بعدی
```

---

## T-8.1.1 — WP-8.1 Contract Specification

```text
Task ID:              T-8.1.1
Phase:                P8 — Product Candidate
Work Package:         WP-8.1
Objective:            نگارش قرارداد پیاده‌سازی SPEC-WP81-PMATCH مشتق فقط از سوابق برقرار (بدون اختراع نیازمندی)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: SPEC-WP81-PMATCH v1.0-MVP (§1..§10) — D-05 Exact Match فقط با identifier قطعی
                      معتبر؛ کاتالوگ = حداقل register هویت Product-side (OD-PM2؛ ثبت explicit — بدون
                      مسیر capture)؛ واژگان identifier = declared opaque بدون barcode semantics (OD-PM3)؛
                      INV-PM-1:1 + replay verbatim (OD-PM4)؛ قطعیت با UNIQUE ساخت (OD-PM5)؛ مرجع declared
                      با قاعدهٔ exactly-one + pointer discipline (OD-PM6)؛ بدون fuzzy/confidence/approval
                      (OD-PM7)؛ مرز canonicalization/customer/REVIEW (OD-PM8)؛ MNT-1 baseline note
Locked Decisions:     D-05 | D-09 | AD-02 | AD-03 | AS-02 | AS-03 | AS-04/AD-04/CL-1 | D-01 | D-06/DEF3 (analog ساختاری) | SPEC-WP62-CANASM | SPEC-WP71-IDRES (OD-IR-J)
Evidence:             kandoo/specs/WP-8.1-product-exact-match-contract.md
Out of Scope:         WP-8.2 (candidate/approval) | هر semantic فازی | تغییر contract فروزن
```

## T-8.1.2 — WP-8.1 Implementation (store + service)

```text
Task ID:              T-8.1.2
Phase:                P8 — Product Candidate
Work Package:         WP-8.1
Objective:            BUILD واقعی لایهٔ Product Candidate (مدل/store/service) با مصرف verbatim read verified پ6.2
Status:               ✅ DONE (2026-10-08)
Implementation Notes: src/product_candidate/{model,store,service,__init__}.py — matching ladder M1–M6
                      fail-closed؛ exactly-one declared-reference resolution (0/≥2 → refusal، هرگز
                      auto-resolution)؛ lookup count-based (0→UNRESOLVED دائمی، 1→EXACT_MATCHED، ≥2→
                      integrity fail-closed)؛ commit اتمیک تک‌ردیفی؛ readهای تأییدشده با VOR خود +
                      باز-تأیید فاکتور لینک‌شده + re-join اشاره‌گر + باز-تأیید کاتالوگ + اثبات زندهٔ
                      byte-identity؛ ثبت کاتالوگ idempotent با replay verbatim؛ sha256-v1 از طریق S1
                      service؛ بدون hashlib/UPDATE/DELETE/float/random (AST)؛ uuid فقط bookkeeping
Locked Decisions:     OD-PM1..PM8 | D-01 (relay provenance) | D-05
Evidence:             kandoo/src/product_candidate/ | run_smoke_product_matching.py (8 گام OK)
Out of Scope:         هر logik فازی | جهش upstream | مسیر capture به کاتالوگ
```

## T-8.1.3 — WP-8.1 Test Suite (behavior, not line coverage)

```text
Task ID:              T-8.1.3
Phase:                P8 — Product Candidate
Work Package:         WP-8.1
Objective:            suite اختصاصی P8.1 — رفتار، مرز، adversarial، durability، همزمانی، AST
Status:               ✅ DONE (2026-10-08)
Implementation Notes: ۵ فایل / ۵۷ تست (catalog 10 | match 12 | service 8 | durability 12 | boundary 15) —
                      ثبت کاتالوگ + idempotency verbatim + UNIQUE/CHECK backstops با SQL مستقیم؛
                      EXACT_MATCHED/UNRESOLVED/replay-verbatim/never-re-decide؛ provenance DERIVED به‌عنوان
                      مرجع معتبر؛ byte-identity (تفاوت case → UNRESOLVED)؛ spy-proven مصرف دقیق یک‌بارهٔ
                      read verified؛ refusal matrix + zero residue؛ tamper matrix (own row / flip /
                      hash-consistent forged → structural gates / linked invoice / linked catalog /
                      canonical value)؛ forced failure + capability failure → zero residue؛ race
                      ۸-thread (thread-local stores + stub inert با read verified پیش‌خوانده — الگوی
                      ثبت‌شدهٔ WP-7.1/7.2) ⇒ یک برنده + ۷ replay؛ determinism استقرار؛ AST (صفر
                      UPDATE/DELETE/DROP/hashlib/random/float؛ import allowlist؛ uuid فقط bookkeeping؛
                      identifier sweep منع fuzzy/confidence/approval/customer/barcode)؛ row-count
                      stability لایه‌های Frozen؛ schema pointer-discipline probe
Locked Decisions:     D-05 | D-09 | AD-04/CL-1 | AS-03
Evidence:             kandoo/src/product_candidate/tests/ (57/57 PASSED — +2 تکرار مستقل)
Out of Scope:         تغییر فایل‌های Frozen (حتی تست‌های Frozen) | پوشش line-based
```

## T-8.1.4 — WP-8.1 Verification + Governance

```text
Task ID:              T-8.1.4
Phase:                P8 — Product Candidate
Work Package:         WP-8.1
Objective:            اجرای رسمی tests/regression/smokes + به‌روزرسانی registerها + README + worklog + commit
Status:               ✅ DONE (2026-10-08)
Implementation Notes: P8.1 dedicated = 57/57 PASSED (+2 تکرار مستقل 57/57)؛ رگرسیون کامل = 1125 جمع‌کل
                      (1124 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود — test_ir_provenance::
                      test_no_raw_pipeline_values_are_stored، suite فروزن WP-7.1، وابسته به تاریخ UTC —
                      dispatch قبل در worktree خالص بازتولید کرده؛ فایل Frozen طبق حکمرانی دست‌نخورده)؛
                      SMOKE OK = run_smoke_product_matching.py (۸ گام، cold-start)؛ registerها
                      (REG-WPR/REG-TR/REG-AR) + src/README.md به‌روز؛ commit محلی؛ archive کامل در پایان
                      Mission بازتولید و مستقل verify می‌شود
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection | Flake Policy
Evidence:             REG-WPR §WP-8.1 | REG-AR §WP-8.1 | worklog | خروجی pytest
Out of Scope:         git push (درخواست نشده) | archive بازسازی‌شده در همین task (در پایان Mission)
```

---

## T-9.1.1 — WP-9.1 Contract Specification

```text
Task ID:              T-9.1.1
Phase:                P9 — Customer Linkage
Work Package:         WP-9.1
Objective:            نگارش قرارداد پیاده‌سازی SPEC-WP91-CUSTLINK مشتق فقط از سوابق برقرار (بدون اختراع نیازمندی)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: SPEC-WP91-CUSTLINK v1.0-MVP (§1..§10) — D-06: auto-create ممنوع، فقط link قطعی به
                      Customer موجود؛ DEF3 دست‌نخورده؛ قاعدهٔ link = تنها semantics تطبیق قطعی برقرار
                      (D-05/P6.1: identifier قطعی با byte-exact به دقیقاً یک identity)؛ register مشتری =
                      حداقل سطح دامنه (OD-CL2؛ ثبت explicit — بدون مسیر capture؛ شاخهٔ creation در نردبان
                      ساختاراً ناموجود)؛ واژگان identifier = declared opaque (OD-CL3)؛ INV-CL-1:1 + replay
                      verbatim (OD-CL4)؛ قطعیت با UNIQUE ساخت (OD-CL5)؛ مرجع declared با exactly-one +
                      pointer discipline (OD-CL6)؛ بدون fuzzy/best-match/merge/enrichment (OD-CL7)؛ OD-A9
                      دست‌نخورده (OD-CL8)؛ MNT-1 baseline note
Locked Decisions:     D-06 | DEF3 | D-09 | AD-02 | AD-03 | AS-02 | AS-03 | AS-04/AD-04/CL-1 | D-01 | D-05 (semantics) | SPEC-WP62-CANASM (OD-A9) | SPEC-WP71-IDRES (OD-IR-J) | SPEC-WP81-PMATCH (sibling derivation)
Evidence:             kandoo/specs/WP-9.1-customer-linking-contract.md
Out of Scope:         merge/dedup/enrichment (DEF3/D-06/WP-11.x) | هر semantic فازی | جهش فاکتور فروزن
```

## T-9.1.2 — WP-9.1 Implementation (store + service)

```text
Task ID:              T-9.1.2
Phase:                P9 — Customer Linkage
Work Package:         WP-9.1
Objective:            BUILD واقعی لایهٔ Customer Linkage (مدل/store/service) با مصرف verbatim read verified پ6.2
Status:               ✅ DONE (2026-10-08)
Implementation Notes: src/customer_linking/{model,store,service,__init__}.py — linking ladder L1–L6
                      fail-closed؛ exactly-one declared-reference resolution (0/≥2 → refusal، هرگز
                      auto-resolution)؛ lookup count-based (0→UNRESOLVED دائمی، 1→LINKED به مشتری موجود،
                      ≥2→integrity fail-closed)؛ NO creation branch (تنها نوشتنیِ نردبان = link row
                      append-only)؛ commit اتمیک تک‌ردیفی؛ readهای تأییدشده با VOR خود + باز-تأیید فاکتور
                      لینک‌شده + re-join اشاره‌گر + باز-تأیید مشتری + اثبات زندهٔ byte-identity؛ ثبت مشتری
                      idempotent با replay verbatim؛ sha256-v1 از طریق S1 service؛ بدون
                      hashlib/UPDATE/DELETE/float/random (AST)؛ uuid فقط bookkeeping
Locked Decisions:     OD-CL1..CL8 | D-01 (relay provenance) | D-06
Evidence:             kandoo/src/customer_linking/ | run_smoke_customer_linking.py (8 گام OK)
Out of Scope:         هر logik فازی/creation | جهش upstream | مسیر capture به register
```

## T-9.1.3 — WP-9.1 Test Suite (behavior, not line coverage)

```text
Task ID:              T-9.1.3
Phase:                P9 — Customer Linkage
Work Package:         WP-9.1
Objective:            suite اختصاصی P9.1 — رفتار، مرز، adversarial، durability، همزمانی، AST
Status:               ✅ DONE (2026-10-08)
Implementation Notes: ۵ فایل / ۵۹ تست (customers 10 | link 11 | service 8 | durability 12 | boundary 18) —
                      اثبات ساختاری no-auto-create (AST: صفر INSERT در service؛ فقط دو INSERT مجزا در
                      store روی دو مسیر commit مجزا؛ signature probe؛ behavioral: هر outcome رجیستر را
                      رشد نمی‌دهد)؛ ثبت + idempotency verbatim + UNIQUE/CHECK backstops با SQL مستقیم؛
                      LINKED/UNRESOLVED/replay-verbatim/never-re-decide (حتی پس از ثبت بعدی)؛ provenance
                      DERIVED معتبر؛ byte-identity (تفاوت case → UNRESOLVED)؛ spy-proven مصرف دقیق
                      read verified؛ refusal matrix + zero residue؛ tamper matrix (own row / flip شکل /
                      hash-consistent forged → structural gates / فاکتور لینک‌شده / مشتری / مقدار
                      canonical)؛ forced failure + capability failure → zero residue؛ race ۸-thread
                      (thread-local stores + stub inert — الگوی ثبت‌شده) ⇒ یک برنده + ۷ replay؛
                      determinism استقرار؛ AST identifier sweep منع merge/dedup/enrichment/fuzzy/
                      confidence/customer-create؛ row-count stability لایه‌های Frozen؛ schema
                      pointer-discipline probe؛ public-surface probe (بدون create/merge/enrich verb)
Locked Decisions:     D-06 | DEF3 | D-09 | AD-04/CL-1 | AS-03
Evidence:             kandoo/src/customer_linking/tests/ (59/59 PASSED — +2 تکرار مستقل)
Out of Scope:         تغییر فایل‌های Frozen (حتی تست‌های Frozen) | پوشش line-based
```

## T-9.1.4 — WP-9.1 Verification + Governance

```text
Task ID:              T-9.1.4
Phase:                P9 — Customer Linkage
Work Package:         WP-9.1
Objective:            اجرای رسمی tests/regression/smokes + به‌روزرسانی registerها + README + worklog + commit
Status:               ✅ DONE (2026-10-08)
Implementation Notes: P9.1 dedicated = 59/59 PASSED (+2 تکرار مستقل 59/59)؛ رگرسیون کامل = 1184 جمع‌کل
                      (1183 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود — test_ir_provenance::
                      test_no_raw_pipeline_values_are_stored، suite فروزن WP-7.1، وابسته به تاریخ UTC؛
                      فایل Frozen طبق Flake Policy دست‌نخورده)؛ SMOKE OK = run_smoke_customer_linking.py
                      (۸ گام، cold-start)؛ registerها (REG-WPR/REG-TR/REG-AR) + src/README.md به‌روز؛
                      commit محلی؛ archive کامل در پایان Mission بازتولید و مستقل verify می‌شود
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection | Flake Policy
Evidence:             REG-WPR §WP-9.1 | REG-AR §WP-9.1 | worklog | خروجی pytest
Out of Scope:         git push (درخواست نشده) | archive بازسازی‌شده در همین task (در پایان Mission)
```

---

## T-10.1.1 — WP-10.1 Contract Specification

```text
Task ID:              T-10.1.1
Phase:                P10 — Digital Invoice
Work Package:         WP-10.1
Objective:            تولید SPEC-WP101-DILIFE — قرارداد پیاده‌سازی Digital Invoice Lifecycle مشتق فقط از سوابق برقرار (بدون اختراع نیازمندی)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/specs/WP-10.1-digital-invoice-lifecycle-contract.md — §1..§12؛
                      واژگان lifecycle فروزن عیناً از Mission dispatch (AS-03):
                      DRAFT | EXTRACTED | VALIDATED | ISSUED | REVOKED |
                      SUPERSEDED — بدون state جدید/تغییر نام؛ ماتریس انتقال
                      declarative (۵ انتقال؛ هر state دقیقاً یک پیشین؛ terminal
                      بدون خروجی)؛ entry فقط از read + trace تأییدشدهٔ P6.2
                      (OD-DI-B)؛ INV-DI-1:1؛ acts صریح idempotent (D-03)؛
                      supersede با نردبان تأیید replacement (§5.4)؛ CAS append
                      درون-تراکنشی (OD-DI3)؛ pointer discipline (OD-DI-J — هیچ
                      مقدار canonical ذخیره نمی‌شود)؛ MNT-1 baseline note
Locked Decisions:     AS-03 | AS-04 | AS-02/AS-01 | AD-01..04 | AD-04/CL-1 |
                      D-02 | D-03 | D-01 | D-06/DEF3 | D-09 | DEF1 | DEF5 |
                      SPEC-WP62-CANASM (authority انحصاری invoice path)
Evidence:             kandoo/specs/WP-10.1-digital-invoice-lifecycle-contract.md
Out of Scope:         هر تصمیم معماری جدید | بازتعریف واژگان Frozen | ارائه/کانال تحویل (WP-10.2/DEF5) | مسیر native Sale | تغییر P6.1/P6.2
```

---

## T-10.1.2 — WP-10.1 Implementation (store + service)

```text
Task ID:              T-10.1.2
Phase:                P10 — Digital Invoice
Work Package:         WP-10.1
Objective:            پیاده‌سازی واقعی Digital Invoice Lifecycle روی خروجی فروزن P6.2
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/src/digital_invoice/ — model.py (واژگان فروزن + واژگان act
                      واگذارشده OD-DI-C؛ ماتریس TRANSITIONS + helperهای pure:
                      is_legal_transition/predecessor_of/expected_outgoing/
                      project_current_state؛ رکوردها + outcomeهای صریح exhaustive) |
                      store.py (جداول digital_invoices + digital_invoice_events؛
                      synchronous=FULL؛ commit اتمیک تک‌ردیفی؛ ماتریس §5.2 در سطح DB
                      با CHECK؛ CAS append: seq == len(chain) AND current ==
                      from_state درون تراکنش؛ UNIQUE(invoice_id) backstop
                      INV-DI-1:1؛ UNIQUE(digital_invoice_id,event_seq)؛ sha256-v1
                      از طریق سرویس S1 — بدون hashlib؛ بدون UPDATE/DELETE) |
                      service.py (open ladder O1..O4 با مصرف verbatim read+trace
                      پ6.2؛ نردبان acts مشترک A0..A5: advance فقط از پیشین دقیق،
                      replay فقط در state هدف، refusal صادق در بقیه؛ supersede با
                      تأیید act-time replacement (exists/verified/ISSUED/≠self) و
                      replay byte-match (OD-DI-H)؛ verified reads: own VOR +
                      یکپارچگی زنجیره (VOR هر event، seq gap-free، بستار زنجیره،
                      شکل ماتریس، anchor drift) + باز-تأیید زندهٔ P6.2 + باز-تأیید
                      replacement یک-سطح (بدون شرط state در read — قطعیت تاریخچه)
                      + trace_digital_invoice؛ listing discipline) |
                      بدون machine.py طبق OD-DI-A (ماتریس ۵ سطری در model)
Locked Decisions:     AS-03 | D-02 | D-03 | D-09 | AD-02 | AD-04 | SPEC-WP62-CANASM
Evidence:             kandoo/src/digital_invoice/ (واردات و smoke سبز)
Out of Scope:         تغییر هر لایهٔ Frozen P1–P9 | هر اجرای upstream | هر تصمیم canonicalization/identity | هر رفتار خودکار lifecycle
```

---

## T-10.1.3 — WP-10.1 Test Suite (behavior, not line coverage)

```text
Task ID:              T-10.1.3
Phase:                P10 — Digital Invoice
Work Package:         WP-10.1
Objective:            پوشش رفتاری کامل lifecycle — open / matrix / service / durability / boundary
Status:               ✅ DONE (2026-10-08)
Implementation Notes: 5 فایل / 54 تست — test_di_open.py (۱۰) | test_di_lifecycle.py (۱۵) |
                      test_di_service.py (۱۴) | test_di_durability.py (۱۵) |
                      di_helpers.py + conftest.py (stack کامل روی P6.2 verbatim +
                      corpus یکتا) — محورها: open happy/replay/unknown/admission-
                      بدون-assembly/tamper؛ پیشروی کامل DRAFT→ISSUED با بستار
                      زنجیره و seq gap-free؛ ماتریس کامل (skip/backward/
                      terminal-exit refused با zero residue؛ replay صفر-ردیف در
                      state هدف)؛ REVOKE/SUPERSEDE انحصار + چرخهٔ ساختاراً ناممکن
                      + byte-match conflict + زنجیرهٔ a→b→c؛ reason_note verbatim
                     ؛ tamper matrix (own row/event/hash-consistent forged →
                      gates/anchor drift/CHECK via SQL مستقیم/UNIQUE backstops)
                     ؛ gap/reparenting؛ forced failure zero-residue؛ restart؛
                      race ۸-thread (open → ۱ برنده + ۷ replay؛ advance → ۱
                      event؛ REVOKE-vs-SUPERSEDE → دقیقاً یک terminal)؛ AST
                      (صفر UPDATE/DELETE/DROP/hashlib/random/eval؛ allowlist
                      import؛ INSERT surface = دقیقاً ۲؛ uuid فقط bookkeeping ×۲)
                     ؛ spy مصرف P6.2؛ row-count stability لایه‌های فروزن؛
                      end-to-end تا SUPERSEDED
Locked Decisions:     AS-03 | D-03 | D-09 | AD-04/CL-1 | SPEC-WP62-CANASM
Evidence:             kandoo/src/digital_invoice/tests/ (54/54 PASSED — 2 تکرار مستقل)
Out of Scope:         تغییر فایل‌های Frozen (حتی تست‌های Frozen) | پوشش line-based
```

---

## T-10.1.4 — WP-10.1 Verification + Governance + Delivery

```text
Task ID:              T-10.1.4
Phase:                P10 — Digital Invoice
Work Package:         WP-10.1
Objective:            اجرای رسمی tests/regression/smokes + به‌روزرسانی registerها + README + worklog + archive کامل + manifest + Git
Status:               ✅ DONE (2026-10-08)
Implementation Notes: P10.1 dedicated = 54/54 PASSED (+2 تکرار مستقل 54/54)؛
                      رگرسیون کامل = 1238 جمع‌کل (1237 PASSED + 1 flake ثبت‌شدهٔ
                      از پیش موجود) — Python 3.12.14 / pytest؛ SMOKE OK =
                      run_smoke_digital_invoice.py (۸ گام: open→DRAFT →
                      پیشروی→ISSUED → replay صفر-ردیف → refusals → supersede با
                      pointer تأییدشده → revoke → restart survival → tamper
                      withhold + vocabulary sweep؛ مسیر سرد)؛ flake ثبت‌شده:
                      test_ir_provenance.py::test_no_raw_pipeline_values_are_
                      stored (suite فروزن WP-7.1 — تاریخ‌حساس؛ همان flake
                      قبلی؛ فایل Frozen طبق حکمرانی دست‌خورده ماند)؛
                      registerها (REG-WPR/REG-TR/REG-AR) + src/README.md +
                      worklog به‌روز؛ archive کامل + MANIFEST-SHA256.txt بازتولید
                      و مستقل verify شد
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection
Evidence:             REG-WPR §WP-10.1 | REG-AR §WP-10.1 | worklog | MANIFEST-SHA256.txt
Out of Scope:         git push (درخواست نشده) | شروع WP بعدی خارج از P10
```

---

## T-11.1.1 — WP-11.1 Contract Specification

```text
Task ID:              T-11.1.1
Phase:                P11 — Holoo Integration / Enrichment
Work Package:         WP-11.1
Objective:            تولید SPEC-WP111-HDS — قرارداد Holoo DB Spike (READ-ONLY) مشتق فقط از سوابق برقرار + Mission dispatch (بدون اختراع نیازمندی)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/specs/WP-11.1-holoo-db-spike-contract.md — §1..§14؛
                      مرز READ-ONLY مطلق (§2 — ۹ بند الزامی)؛ ladder پنج‌لایهٔ
                      enforcement (§6: engine mode=ro | query_only | runtime
                      guard | AST | byte proofs)؛ نگاشت DECLARED عملگر با
                      اعتبارسنجی fail-closed (§5 — بدون حدس schema طبق D-04)؛
                      extraction قطعی با دو statement گاردگذاری‌شده (§8)؛
                      encoding type-tagged قطعی (§9)؛ گزارش = تنها خروجی،
                      بدون wall-clock، فقط-حافظه (§10)؛ failure semantics
                      صادقانه (§11)؛ OD-HS-A..K (D-09)
Locked Decisions:     D-04 (FROZEN — «Spike فقط گزارش می‌دهد») | AD-01 | AS-01 |
                      D-02 | D-03 | D-06/DEF3 | D-08 | D-09 | DEF1 | DEF3 |
                      DEF4 | سابقهٔ DEF6 | G1 PASS (شرط Phase Index)
Evidence:             kandoo/specs/WP-11.1-holoo-db-spike-contract.md
Out of Scope:         نوشتن در Holoo (DEF1) | Adapter/live-engine/نگاشت schema (WP-11.2 — PO/TM) | ورود مقدار استخراج‌شده به دامنه | تغییر P1–P10
```

---

## T-11.1.2 — WP-11.1 Implementation (read-only spike layer)

```text
Task ID:              T-11.1.2
Phase:                P11 — Holoo Integration / Enrichment
Work Package:         WP-11.1
Objective:            پیاده‌سازی src/holoo_spike — read-only by construction، بدون write path، additive-only
Status:               ✅ DONE (2026-10-08)
Implementation Notes: model.py — واژگان ۵ نقش گزارشی (§3)، ۴ استثنای تایپ‌دار،
                      HolooSelection frozen با validation لبه‌ای، report
                      dataclass + to_json_bytes قطعی، encode_value type-tagged؛
                      store.py — read_only_uri با quote (L1)،
                      PRAGMA query_only=ON literal در open (L2)،
                      assert_read_only_sql token-based allowlist (L3 — فقط
                      SELECT/PRAGMA-read whitelist؛ بدون کامنت/چند-statement/
                      set-form)، open_source با هدر-probe SQLite، introspection
                      با PRAGMAهای whitelisted، count/project (§8)؛
                      service.py — build_report: hash S1 در open/close (OD-HS-D
                      — بدون hashlib دوم)، validation §5 fail-closed، refusal
                      صادقانه در گزارش، ردِ گزارش در hash mismatch، بدون
                      wall-clock (OD-HS-E)؛ __init__.py exports؛ هیچ import
                      دامنه‌ای جز capture/S1
Locked Decisions:     D-04 | D-09 (OD-HS-A..K) | AS-01 | AD-01
Evidence:             kandoo/src/holoo_spike/ (۴ فایل تولیدی) + py_compile OK
Out of Scope:         هر persistence/API در package | هر semantics دامنه | هر write مسیر
```

---

## T-11.1.3 — WP-11.1 Test Suite (behavior + byte-proof, not line coverage)

```text
Task ID:              T-11.1.3
Phase:                P11 — Holoo Integration / Enrichment
Work Package:         WP-11.1
Objective:             suite اختصاصی اثبات READ-ONLY + read path + fail-closed + determinism (dispatch §8)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: test_hs_read_path (۱۰) — shape/discovery/extraction
                      verbatim چند-نوعی/determinism ×2/JSON canonical/audit
                      verbatim/order_by قطعی/declaration بدون حدس؛
                      test_hs_guards (۲۱) — engine refusals (L1) +
                      query_only readback + ۲۴ parametrized گارد رد + ۹
                      parametrized مجاز + refusal پیش از audit + AST probes
                      (بدون SQL mutating constant/بدون commit/executescript/
                      executemany/بدون eval-exec-hashlib-random/import
                      allowlist/fixture-sweep/literalهای mode=ro) +
                      vocabulary sweep + duplicate names؛ test_hs_failures
                      (۱۲) — missing/dir/non-sqlite/empty → hard failure،
                      SQLite بی‌ربط → refusal صادقانه، جدول/ستون/order_by
                      ناموجود، بدون case-guessing، ادامهٔ بقیهٔ selectionها؛
                      test_hs_durability (۱۱) — L5 byte proofs (hash/size/
                      mtime/change-counter/dir-listing در ۱ و ۵ اجرا + write-
                      refusal hammer)، replay ×5 byte-identical، empty table،
                      truncation صدادار، int64 max، identifier quote/space،
                      استقلال بخش‌های گزارش از ترتیب declaration؛
                      hs_helpers = SYNTHETIC fixture builder (OD-HS-K — فقط
                      tests/؛ هرگز از package تولیدی import نمی‌شود)
Locked Decisions:     SPEC-WP111-HDS §12 (الزامات dispatch §8 عیناً) | D-09
Evidence:             kandoo/src/holoo_spike/tests/ (۶ فایل) — 79/79 PASSED ×2 تکرار مستقل
Out of Scope:         pytest روی سیستم واقعی Holoo (وجود ندارد — offline-safe) | تغییری در suiteهای فروزن
```

---

## T-11.1.4 — WP-11.1 Verification + Governance

```text
Task ID:              T-11.1.4
Phase:                P11 — Holoo Integration / Enrichment
Work Package:         WP-11.1
Objective:            smoke + رگرسیون کامل + به‌روزرسانی Registerها + README + commit
Status:               ✅ DONE (2026-10-08)
Implementation Notes: run_smoke_holoo_spike.py — ۸ گام cold-start (fixture →
                      spike run → determinism → byte proofs → engine refusals
                      → guard refusals → mapping refusal + duplicate → report
                      JSON توسط runner)؛ SMOKE OK (هفدهمین smoke)؛ رگرسیون
                      کامل ۱۶ suite: 1317 collected = 1316 PASSED + ۱ flake
                      ثبت‌شدهٔ از پیش موجود (frozen WP-7.1 test_ir_provenance —
                      verbatim مشابه P10؛ تفکیک طبق Flake Policy؛ فایل فروزن
                      دست‌نخورده)؛ REG-WPR (Phase Index P11 + بخش کامل WP-11.1
                      + WP-11.2 DEFERRED)، REG-TR (T-11.1.1..4)، REG-AR
                      (AC-11.1.1..4) + src/README.md + worklog؛ Frozen P1–P10
                      byte-untouched
Locked Decisions:     WP-11.2 → DEFERRED (STOP-4: نگاشت منبع/authority/sync/
                      write-back = تصمیم PO/TM؛ سابقهٔ DEF6؛ بدون تعریف کامل WP)
Evidence:             خروجی SMOKE OK + خروجی pytest + به‌روزرسانی registerها
Out of Scope:         هر commit بعدی بدون گزارش | push (لازم نیست) | history rewrite (ممنوع)
```

---

## T-12.1.1 — WP-12.1 Contract Specification

```text
Task ID:              T-12.1.1
Phase:                P12 — Pilot
Work Package:         WP-12.1
Objective:            تولید SPEC-WP121-CORPUS — قرارداد Corpus Assembly مشتق فقط از سوابق برقرار + Mission dispatch §4 (بدون اختراع نیازمندی)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/specs/WP-12.1-corpus-assembly-contract.md — §1..§11؛
                      مرزهای مطلق §2 (فقط SYNTHETIC، بدون اثر تولیدی، بدون
                      وابستگی تولیدی به corpus، قطعیت + clock-free OD-CA-J،
                      fail-closed، بدون fuzzy/ratification، append-only)؛
                      واژگان §3 (origin/marking/label kinds)؛ سه قالب §4؛
                      نشانی‌دهی محتوایی §5؛ store §6؛ نردبان مونتاژ §7؛
                      failure semantics §8؛ الزامات آزمون §9؛ OD-CA-A..J (D-09)
Locked Decisions:     D-07 (FROZEN — thresholds فقط تا ratification placeholder) |
                      D-08 (FROZEN — tolerance = Calibration Parameter) |
                      DEF2 | D-03 (replay) | D-09 | D-06/DEF3 | DEF1 | AD-03 |
                      G1 PASS
Evidence:             kandoo/specs/WP-12.1-corpus-assembly-contract.md
Out of Scope:         هر اندازه‌گیری/ratification | corpus واقعی | تغییر P1–P11.1
```

---

## T-12.1.2 — WP-12.1 Implementation (corpus layer)

```text
Task ID:              T-12.1.2
Phase:                P12 — Pilot
Work Package:         WP-12.1
Objective:            پیاده‌سازی src/corpus — deterministic، clock-free، additive-only
Status:               ✅ DONE (2026-10-08)
Implementation Notes: model.py — واژگان دقیق origin/marking/label-kind، ۸
                      استثنای تایپ‌دار، CorpusEntry/Manifest/Label + outcomes؛
                      generator.py — entropy با زنجیرهٔ digests S1 (بدون
                      random/hashlib/زمان)، serialization قطعی LP-8byte
                      (entry/manifest)، سه قالب declared با integer-cents +
                      HALF_UP + variant EURO (label همیشه canonical)؛
                      store.py — الگوی کامل store پروژه، تراکنش اتمیک
                      کل-نسخه، بدون ستون زمانی، VOR با بازسازی canonical
                      bytes از ستون‌ها، CHECK origin/marking/algorithm،
                      UNIQUE(corpus_version_id, ordinal) + UNIQUE(entry_
                      fingerprint)؛ service.py — نردبان A1..A5 با replay
                      مسیر VOR-کامل (tamper → refusal، هرگز replay)؛
                      __init__.py exports؛ فقط stdlib + capture
Locked Decisions:     SPEC-WP121-CORPUS (OD-CA-A..J) | D-09 | D-03
Evidence:             kandoo/src/corpus/ (۵ فایل تولیدی) + py_compile OK
Out of Scope:         هر رفتار دامنه | هر مسیر نوشتن بیرون store خودش
```

---

## T-12.1.3 — WP-12.1 Test Suite (behavior, not line coverage)

```text
Task ID:              T-12.1.3
Phase:                P12 — Pilot
Work Package:         WP-12.1
Objective:            پوشش رفتاری کامل corpus — generator/store/service/boundary (dispatch §7)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: ۴ فایل / ۹۰ تست — test_co_generator (۲۲): قطعیت
                      expansion/seed، HALF_UP sweep exact-rationale، EURO
                      refusal شکل کوتاه، پوشش سه قالب، توافق label↔document
                      (شامل EURO-variant با label canonical)، residual
                      vocabulary، serialization حساس به محتوا/ترتیب، refusal
                      labelهای خراب؛ test_co_store (۱۸): round-trip blobs،
                      persistence/verified read، restart، replay صفر-ردیف،
                      tamper matrix کامل (fingerprint/part/ordinal/count/
                      ledger/delete → withhold)، CHECK/UNIQUE با SQL مستقیم،
                      static probe بدون UPDATE/DELETE در store source،
                      unopenable path؛ test_co_service (۱۵): ۱۱ parametrized
                      ورودی خراب، refusals بدون residue، قطعیت بین دو store
                      مستقل، address متفاوت برای اعلان متفاوت، replay ×4،
                      کشف ناسازگاری storage با VOR-full replay،
                      zero-residue با forced failure (proxy connection)،
                      UNIQUE backstop؛ test_co_boundary (۱۲): allowlist
                      import، ممنوعیت random/hashlib/time/datetime/os/...،
                      بدون eval/exec/open، clock-free sweep، append-only،
                      بدون file I/O، sweep «هیچ package تولیدی corpus را
                      import نمی‌کند»، sweep smoke runnerهای قبلی، vocabulary
                      sweep، marking literal، flake-window avoidance
Locked Decisions:     SPEC-WP121-CORPUS §9 | D-09
Evidence:             kandoo/src/corpus/tests/ (۵ فایل) — 90/90 PASSED ×3 تکرار مستقل
Out of Scope:         تغییر suiteهای فروزن | pytest روی منبع واقعی (وجود ندارد)
```

---

## T-12.1.4 — WP-12.1 Verification + Governance

```text
Task ID:              T-12.1.4
Phase:                P12 — Pilot
Work Package:         WP-12.1
Objective:            smoke + رگرسیون + به‌روزرسانی Registerها + README + commit
Status:               ✅ DONE (2026-10-08)
Implementation Notes: run_smoke_corpus.py — ۸ گام cold-start (assemble →
                      replay صفر-ردیف → verified read + marking → address
                      متمایز → determinism بین دو store → tamper withhold →
                      restart → fail-closed)؛ SMOKE OK (هجدهمین smoke)؛
                      رگرسیون کامل ۱۸ suite: 1440 جمع‌کل = 1439 PASSED + ۱
                      flake ثبت‌شدهٔ از پیش موجود (frozen WP-7.1
                      test_ir_provenance — تاریخ‌حساس؛ UTC 2026-10-08؛
                      تفکیک طبق Flake Policy؛ فایل فروزن دست‌خورده)؛
                      registerها + src/README.md + worklog به‌روز
Locked Decisions:     D-09 (حکمرانی) | Frozen Layer Protection
Evidence:             SMOKE OK + pytest + registerها
Out of Scope:         push | history rewrite | شروع WP خارج از P12 بدون مجوز
```

---

## T-12.2.1 — WP-12.2 Contract Specification

```text
Task ID:              T-12.2.1
Phase:                P12 — Pilot
Work Package:         WP-12.2
Objective:            تولید SPEC-WP122-CAL — قرارداد Calibration Runs (فقط اندازه‌گیری؛ ratification = PO/G4)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: kandoo/specs/WP-12.2-calibration-runs-contract.md —
                      §1..§11؛ مرزهای §2 (report-only، workspace ایزوله،
                      pipeline فروزن verbatim، بدون test-helper import،
                      corpus فقط-خواندنی، بدون domain promotion، گزارش
                      قطعی، یک اجرا به‌ازای هر workspace)؛ RunConfig §3؛
                      measured path M1..M9 §4؛ طبقه‌بندی فیلدها §5؛ سوییپ
                      D-08 با rule declared §6؛ گزارش §7؛ failure §8؛
                      الزامات آزمون §9؛ OD-CR-A..G (D-09)
Locked Decisions:     D-07 | D-08 | DEF2 | AS-01 (مسیر اندازه‌گیری) | D-09 |
                      D-04/D-03/D-06 (مرزهای gate)
Evidence:             kandoo/specs/WP-12.2-calibration-runs-contract.md
Out of Scope:         Ratification | P6.2 | fuzzy | corpus واقعی | store تولیدی
```

---

## T-12.2.2 — WP-12.2 Implementation (calibration layer)

```text
Task ID:              T-12.2.2
Phase:                P12 — Pilot
Work Package:         WP-12.2
Objective:            پیاده‌سازی src/calibration — measured path + report قطعی، additive-only
Status:               ✅ DONE (2026-10-08)
Implementation Notes: model.py — RunConfig (echo کامل؛ پارامترهای D-08
                      تزریقی نه hardcoded)، FieldObservation/EntryObservation
                      (بدون uuid/زمان/path)، CandidateResult،
                      CalibrationReport.to_json_bytes قطعی (sort_keys،
                      separators ثابت)؛ stack.py — سیم‌کشی verbatim سرویس‌های
                      فروزن (capture→gate) داخل workspace (OD-CR-B) بدون هر
                      import test-helper؛ runner.py — pre-flight (اعتبارسنجی
                      config، verified-corpus، claim workspace با جدول
                      calibration_runs — یک اجرا)، M1..M9 با نگاشت صادقانهٔ
                      outcomeها (duplicate capture → replay مسیر موجود؛
                      derivation deferred → observation؛ gate decisions از
                      vocabulary فروزن)، طبقه‌بندی فیلدها §5، سوییپ §6 با
                      sub-workspace به‌ازای هر کاندید + rule declared،
                      aggregation فقط شمارش؛ کشف مستند: output-present gate
                      فروزن → قالب clean بدون gross چاپ‌شده (REG-AR note)
Locked Decisions:     SPEC-WP122-CAL (OD-CR-A..G) | D-09 | AS-01
Evidence:             kandoo/src/calibration/ (۴ فایل تولیدی) + py_compile OK
Out of Scope:         هر verdict/rate | هر نوشتن بیرون workspace | تغییر فروزن
```

---

## T-12.2.3 — WP-12.2 Test Suite (behavior + determinism, not line coverage)

```text
Task ID:              T-12.2.3
Phase:                P12 — Pilot
Work Package:         WP-12.2
Objective:            suite اختصاصی اثبات اندازه‌گیری قطعی + ایزوله + مرزها (dispatch §7)
Status:               ✅ DONE (2026-10-08)
Implementation Notes: test_cal_runner (۱۶) — clean: gate ACCEPTED ×3 + ۴
                      rule VALID + MATCH کامل + sweep صادقانهٔ
                      not_evaluable؛ rounding: REVIEW ×6 (output-present
                      فروزن) + sweep texture pinned (0.00: 6 beyond؛ 0.02:
                      6 within؛ 0.01: split) + labels چاپ‌شده MATCH؛
                      review: REVIEW ×2 + ABSENT matched + DEFERRED
                      رکوردهای rule؛ قطعیت ×2 workspace مستقل (دو قالب)؛
                      گزارش بدون uuid/ISO-timestamp/path (regex)؛ echo
                      config verbatim؛ سازگاری شمارش‌ها؛
                      test_cal_boundary (۱۷) — تمام فایل‌ها زیر workspace؛
                      re-run refusal + corpus متفاوت در workspace مصرف‌شده؛
                      corpus byte-stability قبل/بعد (row-level digest)؛
                      unverified corpus → refusal؛ mismatch address →
                      refusal؛ ۷ parametrized config خراب؛ allowlist import
                      (بدون helper/stdlib ممنوع)؛ بدون ارجاع متنی به
                      helperها؛ report path clock-free؛ sweep «هیچ package
                      تولیدی calibration را import نمی‌کند»؛ sweep smoke
                      runnerهای قبلی؛ vocabulary sweep؛ گزارش فقط-حافظه؛
                      S1Service الزامی
Locked Decisions:     SPEC-WP122-CAL §9 | D-09
Evidence:             kandoo/src/calibration/tests/ (۳ فایل) — 33/33 PASSED ×3 تکرار مستقل
Out of Scope:         تغییر suiteهای فروزن | هر اتصال واقعی
```

---

## T-12.2.4 — WP-12.2 Verification + Governance

```text
Task ID:              T-12.2.4
Phase:                P12 — Pilot
Work Package:         WP-12.2
Objective:            smoke + رگرسیون + registerها + README + worklog + commit
Status:               ✅ DONE (2026-10-08)
Implementation Notes: run_smoke_calibration.py — ۸ گام cold-start (سه corpus
                      → clean run ACCEPTED → D-08 sweep texture → review run
                      → determinism بایت-یکسان → re-run refusal → corpus
                      byte-stability → fail-closed)؛ SMOKE OK (نوزدهمین
                      smoke)؛ رگرسیون کامل ۱۸ suite: 1440 جمع‌کل = 1439
                      PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود (verbatim WP-7.1
                      — UTC 2026-10-08؛ Flake Policy)؛ registerها
                      (REG-WPR/REG-TR/REG-AR) + src/README.md + worklog؛
                      WP-12.3 DEFERRED (PO/G4) + WP-11.2 Decision Package
Locked Decisions:     WP-12.3 → DEFERRED (Stop-2: تصمیم انحصاری PO/G4؛
                      D-07/D-08/DEF2) | WP-11.2 → Decision Package فقط
Evidence:             SMOKE OK + pytest + registerها + specs/WP-11.2-decision-package.md
Out of Scope:         push | history rewrite | ratification هر مقداری
```

---

## T-1.2.1 — WP-1.2 Hardening Contract (Registered Decompose)

```text
Task ID:              T-1.2.1
Phase:                P1 — Capture Foundation
Work Package:         WP-1.2
Objective:            تولید SPEC-WP12-S1H (decompose ثبت‌شدهٔ WP-1.2 بعد از Acceptance WP-1.1): ماتریس لبهٔ DECLARED (E1..E11)، properties الزامی، obligations گزارش agility/محدودیت‌ها، مرزهای مطلق additive-only
Status:               ✅ DONE (2026-10-09)
Implementation Notes: قرارداد فقط از سوابق برقرار مشتق شد — هیچ نیازمندی اختراعی؛ deliverableهای ثبت‌شدهٔ WP (گزارش hardening + تست‌های لبه + به‌روزرسانی AR) عیناً محترم؛ OD-SH-F: صفر تغییر کد تولیدی — هر GAP = Architecture Issue
Locked Decisions:     D-02 (تعریف S1 فروزن) | D-03 (بدون semantic dedup) | D-09
Reference Documents:  REG-WPR WP-1.2 | specs/WP-1.1-capture-record-contract.md | D-02/D-03/D-09
Evidence:             kandoo/specs/WP-1.2-s1-hardening-contract.md (SPEC-WP12-S1H v1.0-MVP — §1..§11، OD-SH-A..F)
Out of Scope:         هر تغییر فایل موجود | هر policy جدید | retention (WP-1.3/DEF4)
```

---

## T-1.2.2 — WP-1.2 Edge-Input Matrix Suite

```text
Task ID:              T-1.2.2
Phase:                P1 — Capture Foundation
Work Package:         WP-1.2
Objective:            اجرای ماتریس لبهٔ DECLARED E1..E11 روی لایهٔ فروزن WP-1.1 به‌صورت مجموعهٔ تست اختصاصی additive (فایل جدید؛ بدون تغییر فایل موجود)
Status:               ✅ DONE (2026-10-09)
Implementation Notes: test_s1_hardening.py — ۳۶ تست: E1 خالی (digest معروف + roundtrip + duplicate صریح) | E2 تک‌بایت (۲۵۶ مقدار متمایز) | E3 بزرگ 4MiB (roundtrip + جهش) | E4 چندزبانه (فارسی/CJK/combining/ZWJ) | E5 magic-prefix (sniff مکانیکی، بی‌اثر بر S1) | E6 جهش مرزی (XOR first/last/mid/high-bit — جهش‌ها باید تغییر بدهند؛ خواندن محتوای دستکاری‌شده → ReadIntegrityFailure + FAILED صادقانه) | E7 type exactness (bytes/bytearray/memoryview یکسان؛ non-bytes compute → S1ComputationFailure؛ verify → NO_VERDICT؛ ingest non-bytes → fail-fast با ZERO residue — observation ثبت‌شده) | E8 فیلدهای hostile (FAILED برای digest غلط؛ NO_VERDICT برای id ناشناخته) | E9 fail-closed (outage تزریقی → IngestSettledFailure + صفر COMPLETED residue + re-ingest صادقانه) | E10 store-defect (forged unknown-id → ReadVerificationUnavailable + issue؛ CHECK refusal؛ INV-V8 analog) | E11 framing (empty/ambiguity/order/determinism) + agility (cross-id NO_VERDICT؛ جفت‌کلید uniqueness) + AST hygiene probe
Locked Decisions:     OD-SH-A (محل suite) | OD-SH-B (4MiB) | OD-SH-C (جهش‌های XOR) | OD-SH-F (بدون وصله)
Evidence:             kandoo/src/capture/tests/test_s1_hardening.py — 36/36 PASSED ×3 تکرار مستقل (2026-10-09)
Out of Scope:         تغییر src/capture/*.py | هر patch درون-mission | semantic dedup
```

---

## T-1.2.3 — WP-1.2 Hardening Report (Agility + Limitations)

```text
Task ID:              T-1.2.3
Phase:                P1 — Capture Foundation
Work Package:         WP-1.2
Objective:            تولید HARD-RPT-WP12 — گزارش hardening ثبت‌شدهٔ WP: نتایج ماتریس per-cell، گزارش agility الگوریتم، محدودیت‌های S1 (۷ بند الزامی)، observation ثبت‌شده برای TM/PO
Status:               ✅ DONE (2026-10-09)
Implementation Notes: هیچ GAP یافت نشد — همهٔ cellها OBSERVED-PASS؛ observation واحد: non-bytes در مرز ورود ingest = fail-fast (TypeError/AttributeError از sniff مکانیکی، پیش از هر store call) با صفر residue؛ ردِ تایپ‌دار در مرز capability است (طبق طراحی فروزن) — برای هر تغییر، تصمیم TM/PO لازم است (فایل service.py فروزن است؛ additive WP دست نزد)
Locked Decisions:     OD-SH-E (مسیر گزارش) | OD-SH-F (بدون وصله)
Evidence:             kandoo/specs/WP-1.2-hardening-report.md (HARD-RPT-WP12 v1.0)
Out of Scope:         ratification هر رفتاری | هر تغییر رفتار فروزن | پیشنهاد پیاده‌سازی write-back
```

---

## T-1.2.4 — WP-1.2 Verification + Governance

```text
Task ID:              T-1.2.4
Phase:                P1 — Capture Foundation
Work Package:         WP-1.2
Objective:            smoke + رگرسیون + registerها + README + worklog + commit
Status:               ✅ DONE (2026-10-09)
Implementation Notes: run_smoke_s1_hardening.py — ۸ گام cold-start (determinism → sensitivity/framing → type/hostile → roundtrips → fail-closed → store-defects → agility → binding recap)؛ SMOKE OK (بیستمین smoke؛ ×2)؛ رگرسیون کامل: 1476 جمع‌کل = 1475 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود (verbatim WP-7.1 test_ir_provenance::test_no_raw_pipeline_values_are_stored — Flake Policy؛ حساب additive: 1440 + 36 = 1476)؛ registerها (REG-WPR/REG-TR/REG-AR) + src/README.md + worklog؛ اثبات additive-only با git diff در commit
Locked Decisions:     بدون ratification | بدون تغییر فروزن
Evidence:             SMOKE OK ×2 + pytest + registerها + git diff صفر روی فایل‌های موجود
Out of Scope:         push | history rewrite | باز کردن WP-1.3 (DEF4 values) | ratification آستانه‌ها (P12.3)
```
