# WP-1.1 — Capture Record Contract

```text
Contract ID:   SPEC-WP11-CRC | Version: 1.1 | Date: 2026-10-01 | Status: ACTIVE
Authority:     Locked Decisions D-02, D-03, D-09 (kandoo/registers/decision-register.md)
               G1 Architecture Approval: PASS | G2 Work Package Approval for WP-1.1: APPROVED
Binding for:   T-1.1.2 (Durable Local Capture Store) و T-1.1.3 (S1 Fingerprint & Idempotency Lookup Service)
Change Control: تغییر این Contract فقط از مسیر STOP Protocol → Issue Report → TM Review → PO Decision (D-09)
Missing Input: kandoo/baseline/ خالی است (اسناد Baseline هنوز commit نشده‌اند — MNT-1/RSK-2).
               این Contract صرفاً از Decision Register (SSOT موقت معتبر) ساخته شده است؛ هیچ حدسی وارد نشده است.
Revision:      v1.1 — سه اصلاح قراردادی C1–C3 بنا بر نتیجه TM Review (CONDITIONAL PASS). هیچ Frozen Decision و هیچ مرز معماری تغییر نکرده است.
```

---

## 1. Purpose

این سند قرارداد دقیق و implementation-independent برای **Capture Record** در لایه Capture پروژه Kandoo Digital Invoice را تعریف می‌کند. Contract مشخص می‌کند یک Capture Record چه اطلاعاتی دارد، چگونه به artifact دریافتی متصل است، چه وضعیت‌هایی دارد، چه اطلاعاتی برای traceability لازم است، و رفتارهای مورد انتظار آن در برابر idempotency، integrity و recovery چیست. این سند مرجع الزامی پیاده‌سازی T-1.1.2 و T-1.1.3 است و مرز لایه Capture را نسبت به همه مراحل downstream قفل می‌کند: Capture فقط ثبت و نگهداری evidence است و هیچ نسبت دیگری با سند، فاکتور یا دامنه‌های کسب‌وکار ندارد.

## 2. Scope

**In Scope:** تعریف Capture Record | تعریف Artifact و artifact reference و artifact metadata | فیلد S1 و semantics آن | lifecycle/status مربوط به Capture | فیلدهای traceability | فیلدهای integrity | رفتار و فیلدهای idempotency | وضعیت recovery | رابطه Capture Record با artifact | invariants قابل تست | error/failure semantics | نگاشت به ACهای WP-1.1 | فهرست تفویض‌های implementation.

**Out of Scope (ممنوع مطلق):** کدنویسی | Database schema | Migration | API | ORM | انتخاب SQLite/PostgreSQL یا هر storage technology | انتخاب SHA-256 یا هر الگوریتم مشخص برای S1 (فقط به‌عنوان گزینه implementation در §16) | OCR | VLM | Reconstruction | Extraction | Normalization | Canonicalization | Product Matching | Customer Matching | Digital Invoice | Inventory | Sale | Holoo DB | Cloud Sync | Retention Policy (DEF4) | Privacy Policy (DEF4) | UI | Production deployment.

## 3. Capture Record Definition

**تعریف:** Capture Record، ثبتِ **یک رویداد دریافت (capture event)** است: پیوندِ (artifact به همان شکلی که تحویل داده شده) ↔ `S1` ↔ وضعیت lifecycle و integrity ↔ metadata مربوط به همان رویداد دریافت.

Capture Record **نیست:** فاکتور، موجودیت Canonical، سند استخراج‌شده یا نرمال‌شده، رکورد Sale، رکورد Inventory، یا هرگونه نمای تجاری از محتوا.

**اصل واحد دریافت (Ingest Unit):** یک submission از نقطه ورود capture = یک Artifact Instance = یک Capture Record. لایه Capture هیچ فرضی نمی‌کند که artifact یک سند منطقی کامل است؛ تعیین صفحه/سند و ترتیب‌دهی، مسئولیت Reconstruction (P2) است.

**استقلال مکانیزم:** این Contract به هیچ فناوری ذخیره‌سازی، الگوریتم fingerprint مشخص، یا پیاده‌سازی خاصی وابسته نیست؛ انتخاب‌ها فقط در چارچوب §16 تفویض می‌شوند.

## 4. Artifact Definition

**Artifact** = محتوای evidence دریافتی (توالی opaque از بایت‌ها) به همان شکلی که نقطه ورود capture تحویل داده، به‌علاوه provenance مربوط به همان رویداد دریافت.

قواعد الزامی:

1. **عدم تفسیر:** لایه Capture محتوا را opaque تلقی می‌کند و فقط ویژگی‌های مکانیکیِ سطح بایت (طول، و به‌صورت اختیاری hint فرمت) را ثبت می‌کند — نه تفسیر محتوایی.
2. **اتصال یکتا:** هر Artifact Instance دقیقاً یک `S1` دارد که بر کل محتوای تحویل‌شده محاسبه می‌شود.
3. **تغییرناپذیری:** پس از رسیدن رکورد به `COMPLETED`، محتوای artifact و پیوند `artifact_ref ↔ S1` تغییرناپذیرند؛ هر تغییری = شکست integrity (§10).
4. **`artifact_ref`:** ارجاع opaque به محتوای ذخیره‌شده دائمی؛ ساختار داخلی آن تفویض‌شده است (§16) و معنای قراردادی آن فقط «مکان دائمی محتوای همان Artifact Instance» است.
5. **چندفایلی:** اگر نقطه ورود چند فایل را در یک submission تحویل دهد، همه یک Artifact Instance واحدند (یک رکورد، یک S1 روی مجموعه محتوا). تفکیک یا ادغام واحدها = Reconstruction (P2) و در این لایه ممنوع است.
   **الزام determinism تجمیع (v1.1 — C3):** تجمیع چند فایل در توالی/مجموعه بایتی که ورودی S1 می‌شود باید قطعی (deterministic) باشد: همان مجموعه/ترتیب محتوا باید تحت همان `s1_algorithm_id` همیشه همان S1 را تولید کند. الگوریتم تجمیع مشخص Frozen نمی‌شود و جزئیات آن تفویض §16 است، اما **خودِ الزام determinism قراردادی و غیرقابل تفویض است**.

## 5. Field Contract

قاعده کلی پرشدن (Provable-Data Rule): هر فیلد فقط از یکی از سه منبع زیر پر می‌شود: (الف) بایت‌های artifact، (ب) رویداد capture، (ج) وضعیت فرایند خود لایه Capture. **هر داده fabricated یا inferred از محتوا ممنوع است.**

### F-01 — `capture_id`
- Required/Optional: **Required** | Type: شناسه یکتای opaque (Conceptual Type: identifier)
- Meaning: شناسه یکتای این رکورد دریافت در لایه Capture؛ handle محلی برای traceability
- Source: تولیدشده توسط لایه Capture در لحظه ایجاد رکورد (طرح تولید = تفویض §16)
- Mutability: Immutable | Null/Unknown: هرگز null نیست
- Integrity relevance: مرجع رکورد برای ثبت نتیجه verification | Idempotency relevance: خودش کلید idempotency نیست (`S1` هست)؛ در پاسخ duplicate برمی‌گردد
- Traceability relevance: نقطه اتصال مراحل downstream به این رویداد دریافت

### F-02 — `s1`
- Required/Optional: **Required** | Type: مقدار fingerprint روی محتوا (Conceptual Type: content fingerprint value)
- Meaning: `capture_content_fingerprint` = **Capture Identity** این Artifact Instance و کلید idempotency سطح Capture (D-02، D-03)
- Source: محاسبه از بایت‌های محتوای artifact با الگوریتم مندرج در `s1_algorithm_id`
- Mutability: Immutable پس از اتصال | Null/Unknown: برای رکورد `COMPLETED` هرگز null نیست؛ رکورد بدون S1 هرگز `COMPLETED` نمی‌شود (INV-C1)
- Integrity relevance: مبنای verify-on-read (§10) | Idempotency relevance: **کلید idempotency** (§9)
- Traceability relevance: پیوند پایدار محتوا به رویداد دریافت، مستقل از مکان ذخیره‌سازی

### F-03 — `s1_algorithm_id`
- Required/Optional: **Required** | Type: شناسه الگوریتم (Conceptual Type: label/enum متعلق به implementation)
- Meaning: برچسب الگوریتم/نسخه‌ای که S1 با آن تولید شده — برای راستی‌آزمایی مجدد یکپارچگی و agility آینده
- Source: تعیین‌شده در لحظه محاسبه S1 | Mutability: Immutable
- Null/Unknown: هرگز null نیست
- Integrity relevance: verification فقط با همین شناسه معتبر تکرار می‌شود | Idempotency relevance: مقایسه S1ها فقط درون الگوریتم یکسان معتبر است
- Traceability relevance: ثبت چگونگی تولید اثر انگشت برای بازبینی‌های بعدی

### F-04 — `artifact_ref`
- Required/Optional: **Required** | Type: ارجاع opaque به محتوای ذخیره‌شده (Conceptual Type: locator)
- Meaning: مکان دائمی محتوای همان Artifact Instance؛ محتوا = evidence
- Source: ایجاد هنگام persist محتوا (طرح = تفویض §16) | Mutability: Immutable پس از `COMPLETED`
- Null/Unknown: برای `COMPLETED` هرگز null نیست
- Integrity relevance: verification روی همین محتوا انجام می‌شود | Idempotency relevance: غیرمستقیم (S1 روی همین محتوا محاسبه می‌شود)
- Traceability relevance: لنگرگاه provenance — «چه چیزی دریافت شد»

### F-05 — `created_at`
- Required/Optional: **Required** | Type: timestamp
- Meaning: زمان ایجاد رکورد | Source: ساعت لایه Capture (منبع ساعت = تفویض §16)
- Mutability: Immutable | Null/Unknown: هرگز null
- Integrity relevance: ندارد (روی S1 اثر ندارد) | Idempotency relevance: ندارد
- Traceability relevance: «کی ثبت شد» — جزو provenance رویداد

### F-06 — `capture_state`
- Required/Optional: **Required** | Type: enum: `ACTIVE | COMPLETED | FAILED_INCOMPLETE`
- Meaning: وضعیت lifecycle رویداد دریافت (§7) | Source: لایه Capture طبق قواعد گذار §7
- Mutability: فقط طبق گذارهای مجاز §7 | Null/Unknown: هرگز null
- Integrity relevance: فقط رکورد `COMPLETED` مشمول verify و تحویل evidence معتبر است
- Idempotency relevance: lookup فقط روی `COMPLETED` انجام می‌شود (§9)
- Traceability relevance: وضعیت ثبت‌شده رویداد در زنجیره lineage

### F-07 — `integrity_status`
- Required/Optional: **Required** | Type: enum: `UNVERIFIED | VALID | FAILED`
- Meaning: نتیجه آخرین verification یکپارچگی محتوا در برابر S1 (§10)
- Source: فرایند verification لایه Capture | Mutability: فقط توسط verification (§10)
- Null/Unknown: هرگز null (`UNVERIFIED` = هنوز ارزیابی نشده)
- Integrity relevance: **محور اصلی** | Idempotency relevance: hit روی رکورد FAILED به‌عنوان موفقیت dedup برگردانده نمی‌شود (§9)
- Traceability relevance: اعتبار evidence را برای downstream صریح می‌کند

### F-08 — `integrity_verified_at`
- Required/Optional: **Optional** (تا اولین verification) | Type: timestamp
- Meaning: زمان آخرین اجرای verification | Source: فرایند verification | Mutability: با هر verification بازنویسی
- Null/Unknown: تا قبل از اولین verification خالی — معنایش «هنوز ارزیابی نشده»، نه «نامعلوم»
- Integrity relevance: همراه F-07 | Idempotency relevance: ندارد | Traceability relevance: زمان‌بندی اعتبارسنجی ثبت می‌شود

### F-09 — `received_at`
- Required/Optional: **Required** | Type: timestamp
- Meaning: زمان دریافت artifact توسط نقطه ورود capture | Source: رویداد capture (منبع ساعت = تفویض §16)
- Mutability: Immutable | Null/Unknown: هرگز null
- Integrity relevance: ندارد | Idempotency relevance: ندارد
- Traceability relevance: «کی دریافت شد» — مستقل از «کی ثبت شد» (F-05)

### F-10 — `source_label`
- Required/Optional: **Required** | Type: label/enum کانال ورود
- Meaning: برچسب اعلان‌شده کانال/مسیر دریافت artifact توسط نقطه ورود — فقط برچسب origin رویداد، نه هیچ هویت سیستمی یا تجاری
- Source: نقطه ورود capture (رویداد capture) | Mutability: Immutable
- Null/Unknown: اگر نقطه ورود برچسبی ندهد → مقدار صریح `UNDECLARED`؛ **حدس زدن ممنوع**
- Integrity relevance: ندارد | Idempotency relevance: ندارد (جزء محاسبه S1 نیست)
- Traceability relevance: «از کجا آمد» — provenance رویداد

### F-11 — `artifact_format_hint`
- Required/Optional: **Optional** | Type: label (طبقه‌بندی مکانیکی سطح بایت، شبیه MIME)
- Meaning: طبقه‌بندی مکانیکیِ قالب محتوا — فقط در حدی که بدون تفسیر محتوایی از بایت‌ها قابل تعیین باشد
- Source: بایت‌های artifact (ویژگی مکانیکی) | Mutability: Immutable پس از `COMPLETED`
- Null/Unknown: اگر قابل تعیین نیست → `UNKNOWN`؛ هیچ‌گاه با تفسیر حدس زده نمی‌شود
- Integrity relevance: ندارد | Idempotency relevance: ندارد (جزء S1 نیست)
- Traceability relevance: hint غیرالزامی؛ downstream نباید بر آن به‌عنوان evidence تکیه کند

### F-12 — `capture_entry_metadata`
- Required/Optional: **Optional** | Type: مجموعه key/value خام (verbatim)
- Meaning: هر metadata که نقطه ورود همراه submission فراهم کرده — عیناً و بدون تفسیر ذخیره می‌شود؛ لایه Capture صحت آن را تضمین نمی‌کند
- Source: رویداد capture | Mutability: Immutable
- Null/Unknown: خالی مجاز — معنایش «فراهم نشده»
- Integrity relevance: ندارد | Idempotency relevance: ندارد
- Traceability relevance: provenance خام رویداد برای بازبینی/audit آینده

### F-13 — `artifact_size_bytes`
- Required/Optional: **Optional** | Type: عدد صحیح نامنفی
- Meaning: طول بایتی محتوای artifact — ویژگی مکانیکی | Source: بایت‌های artifact
- Mutability: Immutable پس از `COMPLETED` | Null/Unknown: نامشخص تا persist کامل → پس از `COMPLETED` حاضر است
- Integrity relevance: sanity check برای تشخیص truncate در تست‌ها | Idempotency relevance: ندارد
- Traceability relevance: توصیف مکانیکی محتوای دریافت‌شده

> **F-14 (`lineage_reserved`) — حذف‌شده در v1.1 بنا بر TM Review (اصلاح C1):** فیلد فیزیکی از Capture Record حذف شد؛ شناسه F-14 بازنشسته است و دوباره استفاده نمی‌شود. مبنای حذف: فیلدی که توسط مراحل آینده پر می‌شود با Provable-Data Rule همین بخش ناسازگار بود. جایگزین: **Extensibility Reservation** در پایان همین بخش (Contract-Level، فیلد نیست). Capture Record فعلی هیچ فیلد فیزیکی lineage/downstream ندارد.

### F-15 — `settlement_note`
- Required/Optional: **Optional** (الزامی برای رکوردهای `FAILED_INCOMPLETE`) | Type: متن/کد کوتاه
- Meaning: دلیل ثبت‌شده توسط recovery یا فرایند capture برای وضعیت نهایی (§11، §14)
- Source: وضعیت فرایند خود لایه Capture (مشاهده خودِ فرایند، نه حدس درباره محتوا)
- Mutability: فقط در لحظه settlement | Null/Unknown: برای `COMPLETED` بی‌معنا و خالی
- Integrity relevance: ندارد | Idempotency relevance: ندارد
- Traceability relevance: «چرا این‌طور تمام شد» — برای audit و بازبینی

### Extensibility Reservation (Contract-Level — v1.1، جایگزین F-14 سابق)

- Capture Record فعلی **هیچ فیلد فیزیکی برای پیوند lineage/downstream ندارد** — نه `lineage_reserved` و نه هیچ فیلد مشابه دیگری. این بند جایگزین فیلد حذف‌شده F-14 است و خودش فیلد نیست.
- مراحل downstream آینده (Reconstruction/Extraction/Canonicalization) برای ارجاع به یک Capture Record فقط از سازوکارهای هویت/ارجاع موجود لایه Capture استفاده می‌کنند: `capture_id` (F-01) و/یا `S1` (F-02، همراه `s1_algorithm_id`).
- هر مرحله downstream باید **قرارداد پیوند خودش (linkage contract)** را در WP/Contract خودش تعریف کند؛ لایه Capture هیچ linkage contractی برای آن‌ها تعریف یا پیش‌فرض نمی‌کند.
- **معرفی هر فیلد جدید در Capture Record ممنوع است** مگر از مسیر Change Control (STOP Protocol → Issue Report → TM Review → PO Decision، D-09). این رزرو، جای فیلد آینده را رزرو نمی‌کند؛ فقط مرز فعلی را قفل می‌کند و توسعه را قراردادی می‌کند.

## 6. Field Semantics

**کلاس‌های تغییرناپذیری:** (۱) Immutable در لحظه ایجاد: F-01, F-02, F-03, F-04, F-05, F-09, F-10, F-11, F-12, F-13 — (۲) فقط با گذار lifecycle: F-06 — (۳) فقط توسط verification: F-07, F-08 — (۴) فقط در settlement: F-15. (کلاس پنجم سابق «فقط توسط مراحل آینده: F-14» با حذف فیلد در v1.1 حذف شد — Extensibility Reservation، §5.)

**مقادیر صریح ناشناخته:** `UNDECLARED` (اعلام نشده توسط نقطه ورود) | `UNKNOWN` (از بایت‌ها قابل تعیین نبود) | خالی (Optional فراهم نشده). هیچ null بدون معنا و هیچ مقدار حدسی مجاز نیست.

**قاعده انحصار داده:** جدول ممنوعات داده‌ای — هرگونه نتیجه extraction، هرگونه attribute فاکتور (شماره/تاریخ/جمع)، هرگونه داده Product/Customer/Sale/Inventory، هرگونه برچسب مبتنی بر تفسیر محتوا، و هر فیلد متعلق به مراحل بعدی، در Capture Record ممنوع است (INV-C7, INV-C8).

## 7. Capture Status/Lifecycle

```text
                 ingest موفق (persist دائمی + S1 متصل + verification معتبر)
   [ingest] ──► ACTIVE ─────────────────────────────────────► COMPLETED  (ترمینال lifecycle)
                 │                                              │
                 │ خطا / قطع / settlement ناکافی                │ integrity_status مستقل تغییر می‌کند:
                 ▼                                              │ UNVERIFIED → VALID | FAILED
           FAILED_INCOMPLETE (ترمینال؛ integrity_status = FAILED الزامی) ◄─┘ (تغییر state نیست)
```

قواعد الزامی گذار:

1. `ACTIVE → COMPLETED` فقط وقتی: محتوا به‌صورت دائمی persist شده **و** `s1` متصل است **و** اولین verification نتیجه `VALID` داده است.
2. `ACTIVE → FAILED_INCOMPLETE` وقتی: خطای ingest رخ داده یا recovery در startup داده durable کافی برای تکمیل نمی‌یابد؛ همیشه با `settlement_note`. **در همان لحظه settlement، `integrity_status = FAILED` نیز ثبت می‌شود — الزامی و همیشگی برای همه رکوردهای `FAILED_INCOMPLETE` (v1.1 — C2).**
3. `FAILED_INCOMPLETE` پس از settlement ترمینال است: صریح، نگهداری‌شده، هرگز به‌عنوان valid ارائه نمی‌شود، هرگز بی‌صدا حذف نمی‌شود؛ `integrity_status` آن همواره `FAILED` است، پس از settlement تغییر نمی‌کند و هیچ‌گاه به `COMPLETED` یا رکورد معتبر تبدیل نمی‌شود.
4. `COMPLETED` ترمینال lifecycle است؛ وضعیت integrity آن (F-07) مستقل از state تغییر می‌کند — رکورد `COMPLETED` با `integrity_status=FAILED` همچنان `COMPLETED` است ولی evidence معتبر محسوب نمی‌شود (§10).
5. هیچ گذار برگشتی وجود ندارد؛ هیچ stateی re-open نمی‌شود؛ حذف رکورد در این Contract تعریف نشده (retention = WP-1.3 / DEF4).
6. `integrity_status` و `capture_state` دو محور متعامدند — ادغامشان ممنوع.

## 8. S1 / Capture Identity Semantics

**تعریف صریح:** `S1 = capture_content_fingerprint` = **Capture Identity** این Artifact Instance. ورودی S1 فقط بایت‌های محتوای artifact است — نه metadata، نه timestamp، نه هیچ فیلد دیگری.

**خواص الزامی:** (۱) **Deterministic** — همان محتوا → همان S1، در هر زمان و هر اجرا. (۲) **Content-Sensitive** — هر تغییر بایتی محتوا → S1 متفاوت. (۳) الگوریتم مشخص تفویض‌شده است (§16) و با `s1_algorithm_id` ثبت می‌شود؛ این Contract هیچ الگوریتمی را Frozen نمی‌کند. (۴) مقایسه دو S1 فقط درون یک `s1_algorithm_id` معتبر است. (۵) **ورودی تجمیع‌شده قطعی (v1.1 — C3):** برای submission چندفایلی، ورودی S1 توالی/مجموعه بایتی حاصل از تجمیع deterministic است (§4-قانون ۵): همان مجموعه/ترتیب محتوا → همان S1 تحت همان `s1_algorithm_id`. الگوریتم تجمیع Frozen نمی‌شود.

**تفکیک سه هویت (الزام D-02 — AC-T111-3):**

| هویت | متعلق به | مقدار/کلید | چه کسی می‌سازد | جای آن در این Contract |
|---|---|---|---|---|
| **Capture Identity** | Artifact Instance دریافتی | `S1` (capture_content_fingerprint) | لایه Capture در لحظه دریافت | **تعریف و ذخیره در همین Contract (F-02)** |
| **External Document Identity** | Invoice در سیستم مبدأ | شناسه قطعی از Adapter، یا ترکیب S2 (شماره فاکتور + تاریخ + جمع) در صورت استخراج و تأیید کامل، یا برچسب `CAPTURE_SCOPED` | Identity Resolution در مرز Canonicalization (P6/P7) | **اینجا ساخته/ذخیره/حدس زده نمی‌شود** — فقط این حقیقت ثبت است که S1 هیچ چیزی درباره آن بیان نمی‌کند |
| **Canonical Identity** | Invoice در Kandoo | `invoice_id` | فقط Kandoo (P6) | خارج از Capture — مطلقاً غایب |

نتیجه الزامی: دو دریافت از همان محتوای فیزیکی یکسان → همان S1 (این یعنی dedup سطح Capture)؛ تعیین اینکه آیا دو capture مربوط به «همان سند» هستند، تصمیم سطح document (P7) است و با S1 یکسان بودن یکی نمی‌شود.

## 9. Idempotency Contract

**کلید:** `S1`. **دامنه تضمین:** فقط سطح Capture (D-03). تضمین سطح سند از این Contract خارج است.

رویه الزامی ingest:

1. S1 روی محتوای submitted محاسبه شود.
2. Lookup بین رکوردهای `capture_state = COMPLETED`:
   - **Hit با `integrity_status ≠ FAILED`:** تلاش به‌عنوان duplicate-at-capture شناسایی می‌شود؛ رکورد فعال مستقل دومی **ساخته نمی‌شود**؛ پاسخ = `capture_id` موجود + نشانگر duplicate-at-capture. (ثبت‌شدن تلاش‌ها = تفویض §16.)
   - **Hit با `integrity_status = FAILED`:** به‌عنوان موفقیت dedup برگردانده **نمی‌شود**؛ مسیر صریح شکست integrity (§10/§14) فعال می‌شود — هرگز بی‌صدا.
   - **No hit:** رکورد جدید در `ACTIVE` ایجاد و ingest ادامه می‌یابد.

**ثابت‌ها:** حداکثر یک رکورد `COMPLETED` به‌ازای هر S1 (INV-C3) | هیچ الگوریتم یا تعریف idempotency جدیدی معرفی نمی‌شود (D-03) | معنای `CAPTURE_SCOPED` برای ارجاع: فقط dedup سطح Capture تضمین می‌شود و ambiguity سطح سند به `REVIEW` می‌رود — این Contract هیچ قضاوتی درباره سطح سند نمی‌کند.

## 10. Integrity Verification Contract

**عملیات verify(record):** بازمحاسبه S1 روی محتوای `artifact_ref` با الگوریتم `s1_algorithm_id` و مقایسه با `s1` ذخیره‌شده.

**احکام ممکن:** `VALID` (تطابق) | `FAILED` (عدم تطابق **یا** محتوای ناخوانا/موجود نبودن محتوا — با دلیل) | `UNVERIFIED` فقط وضعیت گذرا پیش از اولین verification است.

**معنای خواندن (verify-on-read — الزام WP-1.1 AC-1.1.5):**
1. هر خواندنی که محتوای artifact را ارائه می‌کند باید یک **حک قطعی integrity** همراه داشته باشد: `VALID` یا `FAILED`.
2. محتوای با حک `FAILED` هرگز به‌عنوان evidence سالم ارائه نمی‌شود — هیچ خواندنِ ساکتِ خراب مجاز نیست.
3. `UNVERIFIED` هرگز به‌عنوان حک نهایی خواندن برگردانده نمی‌شود (داخل خواندن باید verification اجرا شود تا حک قطعی حاصل شود).
4. در `FAILED`: `integrity_status = FAILED` و `integrity_verified_at` ثبت می‌شود؛ بدون ترمیم خودکار، بدون حذف، بدون بازنویسی محتوا؛ مسیر حل فقط از Issue Report می‌گذرد.
5. رکورد `FAILED_INCOMPLETE` همواره `integrity_status = FAILED` دارد (§7-قانون ۲ و ۳، §11 — v1.1 — C2)؛ این مقدار پس از settlement توسط اجرای مجدد verification تغییر نمی‌کند و verify-on-read مربوط به ارائه محتوا است — رکورد `FAILED_INCOMPLETE` هرگز محتوای معتبر ارائه نمی‌کند. **هیچ state integrity جدیدی معرفی نمی‌شود**؛ مجموعه احکام همان `UNVERIFIED | VALID | FAILED` می‌ماند.

**زمان‌بندی verification (enforce در هر خواندن در مقابل cache بین خواندها) = تفویض §16** — اما تضمین «حک قطعی هنگام خواندن» قراردادی و غیرقابل تفویض است.

## 11. Recovery Contract

1. **Startup Scan الزامی:** در هر شروع، همه رکوردهای جامانده در `ACTIVE` یافت می‌شوند.
2. **قاعده Settlement برای هر جامانده:**
   - اگر محتوا durable و readable است **و** `s1` متصل است **و** verification نتیجه `VALID` می‌دهد → تسویه به `COMPLETED`.
   - در غیر این صورت → تسویه به `FAILED_INCOMPLETE` با `settlement_note` صریح (دلیل کمبود داده/شکست verify) و ثبت همزمان `integrity_status = FAILED` (الزام §7 — v1.1 — C2).
3. `FAILED_INCOMPLETE` صریح و نگهداری‌شده است: هرگز بی‌صدا رها نمی‌شود، هرگز به‌عنوان valid ارائه نمی‌شود؛ `integrity_status` آن همواره `FAILED` است (§7) و recovery هرگز آن را به رکورد معتبر تبدیل نمی‌کند.
4. **Idempotent بودن recovery:** اجرای مکرر recovery امن است و وضعیت را تغییر نمی‌دهد.
5. **بدون retry خودکار** به سمت منابع خارجی — re-fetch از source ممنوع است (این Contract فقط با داده durable کار می‌کند).
6. پس از هر crash/restart هیچ رکوردی در `ACTIVE` باقی نمی‌ماند (INV-C6) و هیچ رکوردی در «حالت نمایشی ناسازگار سوم» ظاهر نمی‌شود: یا state سازگار دارد یا توسط scan تسویه می‌شود.
7. سخت‌سازی کامل ماتریس crash/orphan = WP-1.3؛ این Contract حداقل رفتار درست را الزام می‌کند و مانع سخت‌سازی بعدی نیست.

## 12. Traceability / Provenance

**آنچه هر رکورد حفظ می‌کند:**
- **چه چیزی:** `artifact_ref`، `s1`، `artifact_size_bytes`، `artifact_format_hint`
- **چه زمانی:** `received_at`، `created_at`، `integrity_verified_at`
- **از کجا:** `source_label` (+ `capture_entry_metadata` به‌صورت verbatim و بدون تفسیر)
- **چگونه اثر انگشت خورد:** `s1_algorithm_id`
- **اکنون در چه وضعیتی است:** `capture_state`، `integrity_status`، `settlement_note`
- **پیوند آینده:** وجود ندارد — Capture Record هیچ فیلد فیزیکی lineage/downstream ندارد (v1.1 — C1)؛ مراحل آینده فقط از طریق `capture_id`/`S1` و با قرارداد پیوند خودشان ارجاع می‌دهند (Extensibility Reservation، §5)

**جهت lineage:** Capture Record نقطه مبدأ زنجیره lineage است؛ مراحل بعدی (Reconstruction/Extraction/Canonicalization) به `capture_id`/`S1` ارجاع می‌دهند — Capture هرگز به آن‌ها ارجاع عطفی معناداری نمی‌سازد؛ هر مرحله downstream قرارداد پیوند (linkage contract) خودش را در WP/Contract خودش تعریف می‌کند (Extensibility Reservation، §5).

**قاعده Provable-Data (AC-T111-8):** هر مقدار فیلد باید به یکی از این سه منبع برسد: بایت‌های artifact، رویداد capture، وضعیت فرایند خود Capture. موارد صریحاً ممنوع: نتایج extraction، attributes فاکتور، داده Product/Customer/Sale/Inventory، برچسب‌های تفسیری محتوا، و هر داده‌ای که «به نظر می‌رسد» درست باشد.

## 13. Invariants

| ID | Invariant | قابل تست با |
|---|---|---|
| INV-C1 | هر رکورد `COMPLETED` دارای `capture_id`، `s1`، `artifact_ref`، `created_at`، `received_at`، `source_label`، `s1_algorithm_id` غیرخالی است | بازرسی رکورد (پایه AC-1.1.8) |
| INV-C2 | S1 deterministic و content-sensitive است: ورودی یکسان → S1 یکسان؛ جهش تک‌بایتی → S1 متفاوت | property + mutation test (پایه AC-1.1.2) |
| INV-C3 | حداکثر یک رکورد `COMPLETED` به‌ازای هر S1 (درون یک `s1_algorithm_id`) وجود دارد | duplicate submission test (پایه AC-1.1.4) |
| INV-C4 | محتوای رکورد `COMPLETED` تغییرناپذیر است؛ هر تغییر بایتی ⇒ verification بعدی `FAILED` | corruption injection (پایه AC-1.1.5) |
| INV-C5 | هر خواندن محتوا حک قطعی `VALID`/`FAILED` دارد؛ `UNVERIFIED` حک نهایی خواندن نیست | تست رفتار خواندن (پایه AC-1.1.5) |
| INV-C6 | پس از هر restart، هیچ رکوردی در `ACTIVE` نیست؛ همه یا `COMPLETED`‌اند یا با settlement صریح | restart + interruption test (پایه AC-1.1.6, AC-1.1.7) |
| INV-C7 | هیچ فیلد رکورد داده مراحل downstream (extraction/canonical/product/customer/sale/inventory) را حمل نمی‌کند | بازرسی schema + رکورد (پایه AC-T111-9) |
| INV-C8 | هر مقدار فیلد به artifact bytes، رویداد capture یا وضعیت فرایند Capture می‌رسد؛ هیچ داده fabricated/inferred وجود ندارد | بازرسی مسیر منبع هر فیلد در §5 |
| INV-C9 | هر `FAILED_INCOMPLETE` دارای `settlement_note` و `integrity_status = FAILED` است و هرگز بی‌صدا حذف یا valid جلوه داده نمی‌شود | interruption test (پایه AC-1.1.7) |
| INV-C10 | رکورد و Contract به انتخاب OCR/VLM، Holoo، Canonical implementation و storage technology وابستگی ساختاری ندارند | بازرسی Contract + رکورد (پایه AC-T111-1, AC-T111-10) |

## 14. Error/Failure Semantics

| حالت خرابی | رفتار الزامی Contract |
|---|---|
| شکست نوشتن دائمی در ingest | رکورد `COMPLETED` نمی‌شود؛ یا در `ACTIVE` برای recovery می‌ماند یا با `FAILED_INCOMPLETE` + note تسویه می‌شود (همواره با `integrity_status = FAILED`)؛ از دست‌رفتن بی‌صدا ممنوع |
| شکست محاسبه S1 | ingest قابل تکمیل نیست → `FAILED_INCOMPLETE` + `settlement_note` + `integrity_status = FAILED`؛ رکورد `COMPLETED` بدون S1 وجود ندارد (INV-C1) |
| عدم تطابق در verification / محتوای ناخوانا | `integrity_status = FAILED` با دلیل (§10)؛ ارائه به‌عنوان evidence سالم ممنوع؛ ترمیم خودکار ممنوع |
| قطع فرایند حین ingest | settlement توسط recovery در شروع بعدی (§11) — فقط دو پایان ممکن: `COMPLETED` یا `FAILED_INCOMPLETE` صریح (همواره با `integrity_status = FAILED`) |
| duplicate hit روی رکورد `integrity_status = FAILED` | مسیر صریح شکست integrity فعال می‌شود؛ بازگشت به‌عنوان dedup موفق ممنوع (§9) |
| نقطه ورود بدون source_label | `source_label = UNDECLARED` — حدس زدن ممنوع |
| قالب غیرقابل تعیین | `artifact_format_hint = UNKNOWN` — تفسیر ممنوع |
| پر بودن فضای ذخیره‌سازی / عدم دسترسی | ingest با شکست صریح تمام می‌شود؛ هیچ رکورد partial-valid شکل نمی‌گیرد |
| مشاهده برخورد S1 (دو محتوای متفاوت با S1 یکسان) | آن را به‌عنوان issue گزارش کن (STOP Protocol) — رکورد دوم را به‌زور رد یا ادغام نکن |

## 15. Acceptance Mapping to WP-1.1

| WP AC | عناصر Contract که آن را پوشش می‌دهند |
|---|---|
| AC-1.1.1 (ایجاد/بازیابی پس از restart) | F-01, F-04, F-06 + §7 (گذار) + §11 (recovery) |
| AC-1.1.2 (S1 قطعی و حساس به محتوا) | F-02, F-03 + §8 (خواص الزامی) + INV-C2 |
| AC-1.1.3 (ذخیره و lookup تک‌مقداری S1) | F-02 + §9 (رویه ingest) + INV-C1, INV-C3 |
| AC-1.1.4 (idempotent re-capture) | §9 کامل + INV-C3 + F-06 (دامنه lookup) |
| AC-1.1.5 (verify-on-read با fail صریح) | F-07, F-08 + §10 کامل + INV-C4, INV-C5 |
| AC-1.1.6 (durability پس از restart) | §7 + §11 + INV-C6 + F-04 |
| AC-1.1.7 (تسویه صریح interrupted) | §11 کامل + F-15 + INV-C6, INV-C9 (+ پین `integrity_status = FAILED` — v1.1) |
| AC-1.1.8 (فیلدهای traceability) | F-01, F-02, F-09, F-10 + §12 + Extensibility Reservation (§5) + INV-C1 |

## 16. Explicit Implementation Delegations

هیچ‌یک از موارد زیر تصمیم معماری نیست (D-09)؛ هر انتخاب باید در گزارش Task ذیل «Delegated Implementation Detail Decisions» اعلام و با قیدهای Contract سازگار باشد:

| قلم تفویض‌شده | قیدهای الزامی | ثبت/گزارش |
|---|---|---|
| الگوریتم S1 | deterministic + content-sensitive (§8)؛ شکست ماتریس ممنوع | ثبت در `s1_algorithm_id` + اعلام در گزارش (مثال‌ها مثل SHA-256 فقط گزینه هستند، نه تصمیم) |
| مکانیزم ذخیره‌سازی | durable، local، بدون وابستگی به سرویس شبکه؛ سازگار با §7/§11 | اعلام در گزارش؛ هیچ DB-selection معماری رخ نمی‌دهد |
| طرح `artifact_ref` و چیدمان محتوا | opaque بودن برای همه مصرف‌کنندگان؛ ثبات پس از `COMPLETED` | اعلام در گزارش |
| طرح تولید `capture_id` | یکتایی در دامنه لایه Capture | اعلام در گزارش |
| ثبت لاگ تلاش‌های duplicate ingestion | اختیاری؛ نباید INV-C3 را نقض کند | در صورت پیاده‌سازی، اعلام در گزارش |
| زمان‌بندی/کش verification | باید تضمین حک قطعی هنگام خواندن (§10) را حفظ کند | اعلام در گزارش |
| منبع ساعت برای timestampها | سازگاری و پیوستگی زمانی منطقی درون لایه | اعلام در گزارش |
| تجمیع ورودی نقطه entry (واحد submission) | مالکیت با نقطه ورود؛ Contract فرضی نمی‌سازد (§3, §4)؛ **الزام determinism تجمیع (§4-قانون ۵، §8) غیرقابل تخطی است** — همان مجموعه/ترتیب محتوا → همان S1 تحت همان `s1_algorithm_id` | اعلام در گزارش |

## 17. Open Issues

| ID | موضوع | وضعیت و Handling |
|---|---|---|
| OI-1 | Missing Input: اسناد Baseline (Frozen Canonical Invoice v1، Master Architecture، Master Roadmap) هنوز در `kandoo/baseline/` commit نشده‌اند | OPEN — tracked (MNT-1 / RSK-2). این Contract عمداً فقط از Decision Register ساخته شده و هیچ حدسی جایگزین سند نشده است. پس از commit، فقط ارجاع Source به‌روز می‌شود؛ محتوای Contract نیازی به تغییر ندارد مگر در صورت contradiction — که در آن صورت STOP Protocol فعال می‌شود. |

هیچ Open Issue دیگری ناشی از این Task وجود ندارد.

## 18. Contract-Level Verification (بدون اجرای تست — بازبینی سند)

| AC Task | روش راستی‌آزمایی در همین سند | نتیجه |
|---|---|---|
| AC-T111-1 | تعریف رکورد (§3) هیچ نسبت به Canonical ندارد؛ INV-C7, INV-C10 آن را قفل می‌کنند | PASS |
| AC-T111-2 | §8 + F-02: S1 صریحاً capture_content_fingerprint و Capture Identity | PASS |
| AC-T111-3 | جدول تفکیک سه هویت در §8 + محدودیت نگهداشت در INV-C7 | PASS |
| AC-T111-4 | §4 (اتصال artifact/ref/binding) + §12 (provenance و F-04/F-09/F-10) | PASS |
| AC-T111-5 | §9 رفتار کامل idempotency با S1 به‌عنوان کلید، بدون Freeze الگوریتم (§16) | PASS |
| AC-T111-6 | §10 + §14: احکام، معنای خواندن، و جدول خرابی‌ها — همگی قابل تست (INV-C4, INV-C5) | PASS |
| AC-T111-7 | §11: startup scan، قاعده settlement، idempotent بودن recovery — بدون ورود به مکانیزم | PASS |
| AC-T111-8 | Provable-Data Rule (§5, §6, §12) + INV-C8 — با حذف F-14 در v1.1، تنها استثنای سابق این قاعده از بین رفت | PASS |
| AC-T111-9 | §2 Out of Scope + INV-C7 + INV-C10 | PASS |
| AC-T111-10 | §15 نگاشت کامل ۸ AC به عناصر Contract؛ T-1.1.2/T-1.1.3 مستقیماً به §5/§7/§9/§10/§11 ارجاع دارند | PASS |

```text
Contract Verification Summary: 10/10 AC-T111 PASS — Contract ACTIVE و قابل استفاده توسط T-1.1.2 و T-1.1.3
Change Log: v1.0 — 2026-10-01 — نسخه اولیه توسط T-1.1.1
            v1.1 — 2026-10-01 — اصلاحات قراردادی بنا بر TM Review (CONDITIONAL PASS): C1 حذف فیلد فیزیکی F-14/lineage_reserved و جایگزینی با Extensibility Reservation قراردادی (§5) + به‌روزرسانی §6/§12/§15؛ C2 پین صریح `integrity_status = FAILED` برای FAILED_INCOMPLETE (§4-دیاگرام/§7/§10/§11/§14/INV-C9)؛ C3 الزام determinism تجمیع چندفایلی (§4/§8/§16). هیچ Frozen Decision و هیچ مرز معماری تغییر نکرده است.
```
