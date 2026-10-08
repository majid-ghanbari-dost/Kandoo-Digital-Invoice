# Work Package Register — Kandoo Digital Invoice

```text
Register ID:  REG-WPR | Version: 1.0 | Date: 2026-10-01 | Owner: Technical Manager | Approver: Product Owner (G2)
Rule:         هر WP فقط با قالب استاندارد (۱۴ فیلد) تعریف می‌شود. تغییر AC فقط با ثبت در همین Register.
              تبدیل Phase به WP: فعلاً فقط Phase 1 کامل Instantiate شده؛ سایر Phaseها در سطح Index هستند.
Packaging Note: طبق Bootstrap §5، WP-1.1 پکیج یکپارچه Foundation است (Store + S1 + Integrity + Recovery اولیه + Traceability)
              و WP-1.2 / WP-1.3 نقش Hardening/Completion دارند. این بازبسته‌بندی، scheduling اجرایی است و تصمیم معماری جدیدی نیست.
```

## Phase Index (Master Roadmap → WP Plan)

| Phase | عنوان | وضعیت | WP Plan |
|---|---|---|---|
| P0 | Architecture Freeze | ✅ DONE | Baseline + MRR + این Bootstrap |
| P1 | Capture Foundation | ✅ G3 PASS (2026-10-01) — WP-1.1 CLOSED؛ WP-1.2 **IMPLEMENTED** (2026-10-09 — Mission dispatch «CONTINUE FORWARD BEYOND BLOCKED P12 DECISIONS»: 4/4 AC PASS + hardening 36/36 ×3 independent repeats + رگرسیون کامل 1475/1476 سبز + ۱ flake ثبت‌شدهٔ از پیش موجود — SMOKE 20/20؛ در انتظار Acceptance رسمی PO)؛ WP-1.3 معوق (policy values طبق DEF4 مسدود؛ mechanics قابل decompose) | WP-1.1، WP-1.2، WP-1.3 (زیر — کامل) |
| P2 | Reconstruction | ✅ WP-2.1 IMPLEMENTED (2026-10-01 — 6/6 AC PASS)؛ WP-2.2 IMPLEMENTED (2026-10-01 — 6/6 AC PASS)؛ هر دو WP فاز P2 بسته‌اند (Gate فاز P2 هنوز اعلام نشده) | WP-2.1 Page Ordering & Artifact Reconstruction (پایین — کامل)؛ WP-2.2 Reconstruction Evidence (پایین — کامل) |
| P3 | Extraction | ✅ WP-3.1 IMPLEMENTED (2026-10-01 — 6/6 AC PASS)؛ WP-3.2 IMPLEMENTED (2026-10-01 — 4/4 AC PASS)؛ هر دو WP فاز P3 بسته‌اند (Gate فاز P3 هنوز اعلام نشده) | WP-3.1 Engine-Agnostic Extraction Pipeline (پایین — کامل)؛ WP-3.2 Evidence Binding (پایین — کامل) |
| P4 | Normalization | ❄️ WP-4.1 **FROZEN** (2026-10-05 — freeze dispatch PO/TM؛ correction pass 92/92 + رگرسیون 292/292 + SMOKE 6/6؛ اولین Freeze رسمی WP در پروژه)؛ WP-4.2 **IMPLEMENTED** (2026-10-06 — 4/4 AC PASS + P4.2 101/101 + رگرسیون 393/393 + SMOKE 7/7؛ در انتظار Acceptance رسمی PO) | WP-4.1 Normalization Rules (پایین — کامل، FROZEN)؛ WP-4.2 DERIVED Provenance & Exact Derivation Mechanism (پایین — کامل، IMPLEMENTED) |
| P5 | Validation | 🔨 WP-5.1 **IMPLEMENTED** (2026-10-07 — dispatch اجرایی PO/TM «BUILD واقعی»: 4/4 AC PASS + P5.1 172/172 + رگرسیون کامل 565/565 + SMOKE 8/8؛ در انتظار Acceptance رسمی PO)؛ WP-5.2 **IMPLEMENTED** (2026-10-07 — dispatch اجرایی PO/TM «BUILD واقعی، نه design-only»: 4/4 AC PASS + P5.2 125/125 + رگرسیون کامل 690/690 + SMOKE 9/9؛ در انتظار Acceptance رسمی PO) | WP-5.1 R1/R2 Engine (پایین — کامل، IMPLEMENTED)؛ WP-5.2 Validation State Machine + REVIEW Queue (پایین — کامل، IMPLEMENTED) |
| P6 | Canonicalization | 🔨 WP-6.1 **IMPLEMENTED** (2026-10-07 — dispatch اجرایی PO/TM «BUILD واقعی»: 4/4 AC PASS + P6.1 112/112 + رگرسیون کامل 802/802 + SMOKE 10/10)؛ WP-6.2 **IMPLEMENTED** (2026-10-08 — dispatch اجرایی PO/TM «BUILD واقعی»: 4/4 AC PASS + P6.2 100/100 + رگرسیون کامل 902/902 + SMOKE 11/11؛ هر دو در انتظار Acceptance رسمی PO) | WP-6.1 Canonicalization Gate (پایین — کامل، IMPLEMENTED)؛ WP-6.2 Canonical Assembly + invoice_id Issuance (پایین — کامل، IMPLEMENTED) |
| P7 | Duplicate / Idempotency | 🔨 WP-7.1 **IMPLEMENTED** (2026-10-08 — dispatch اجرایی PO/TM «BUILD واقعی»: 4/4 AC PASS + P7.1 108/108 + رگرسیون کامل 1010/1010 + SMOKE 12/12) و **ACCEPTED/FROZEN** (2026-10-08 — PO)؛ WP-7.2 **IMPLEMENTED** (2026-10-08 — dispatch اجرایی PO/TM «reconnaissance سپس BUILD»: 4/4 AC PASS + P7.2 58/58 + رگرسیون کامل 1067/1068 سبز + ۱ flake ثبت‌شدهٔ از پیش موجود — SMOKE 13/13؛ در انتظار Acceptance رسمی PO) | WP-7.1 Identity Resolution S1/S2/CAPTURE_SCOPED (پایین — کامل، IMPLEMENTED/FROZEN)؛ WP-7.2 Reprint & Duplicate Flows (پایین — کامل، IMPLEMENTED) |
| P8 | Product Candidate | 🔨 WP-8.1 **IMPLEMENTED** (2026-10-08 — Mission dispatch «PRODUCT IDENTITY & CUSTOMER LINKING» Phase A: 4/4 AC PASS + P8.1 57/57 + رگرسیون کامل 1124/1125 سبز + ۱ flake ثبت‌شدهٔ از پیش موجود — SMOKE 14/14؛ در انتظار Acceptance رسمی PO)؛ WP-8.2 PLANNED (خارج از مأموریت — نیازمند تصمیم PO برای policy فازی/تولید کاندید و ماتریس تأیید) | WP-8.1 Exact Match (پایین — کامل، IMPLEMENTED)؛ WP-8.2 Candidate Generation & Approval (فقط Level Index) |
| P9 | Customer Linkage | 🔨 WP-9.1 **IMPLEMENTED** (2026-10-08 — Mission dispatch «PRODUCT IDENTITY & CUSTOMER LINKING» Phase C: 4/4 AC PASS + P9.1 59/59 + رگرسیون کامل 1183/1184 سبز + ۱ flake ثبت‌شدهٔ از پیش موجود — SMOKE 15/15؛ در انتظار Acceptance رسمی PO) | WP-9.1 Deterministic Customer Linking (پایین — کامل، IMPLEMENTED) |
| P10 | Digital Invoice | 🔨 WP-10.1 **IMPLEMENTED** (2026-10-08 — Mission dispatch «DIGITAL INVOICE LIFECYCLE — P10»: 4/4 AC PASS + P10.1 54/54 + رگرسیون کامل 1237/1238 سبز + ۱ flake ثبت‌شدهٔ از پیش موجود — SMOKE 16/16؛ در انتظار Acceptance رسمی PO)؛ WP-10.2 **DEFERRED** (DEF5 — ارائه/قالب/کانال تحویل تصمیم PO؛ تعریف کامل WP نیز موجود نیست) | WP-10.1 Digital Invoice Lifecycle (پایین — کامل، IMPLEMENTED)؛ WP-10.2 Delivery (فقط Level Index — DEF5) |
| P11 | Holoo Integration / Enrichment | 🔨 WP-11.1 **IMPLEMENTED** (2026-10-08 — Mission dispatch «HOLOO INTEGRATION — READ-ONLY SPIKE»: 4/4 AC PASS + P11.1 79/79 + رگرسیون کامل 1316/1317 سبز + ۱ flake ثبت‌شدهٔ از پیش موجود — SMOKE 17/17؛ در انتظار Acceptance رسمی PO)؛ WP-11.2 **DEFERRED** (نیازمند تصمیم PO/TM: نگاشت فیلد منبع، source authority، sync semantics — سابقهٔ DEF6؛ فقط Level Index) | WP-11.1 Holoo DB Spike (پایین — کامل، IMPLEMENTED)؛ WP-11.2 Adapter/Enrichment (فقط Level Index — DEFERRED) |
| P12 | Pilot | 🔨 WP-12.1 **IMPLEMENTED** (2026-10-08 — Mission dispatch «P12 PILOT — CORPUS ASSEMBLY AND DOWNSTREAM IMPLEMENTATION»: 4/4 AC PASS + P12.1 90/90 + رگرسیون کامل 1439/1440 سبز + ۱ flake ثبت‌شدهٔ از پیش موجود — SMOKE 18/18؛ در انتظار Acceptance رسمی PO)؛ WP-12.2 **IMPLEMENTED** (2026-10-08 — همان Mission: 4/4 AC PASS + P12.2 33/33 + SMOKE 19/19؛ در انتظار Acceptance رسمی PO)؛ WP-12.3 **DEFERRED** (تصمیم انحصاری PO/G4 — Ratification آستانه‌ها؛ فقط Level Index) | WP-12.1 Corpus Assembly (پایین — کامل، IMPLEMENTED)؛ WP-12.2 Calibration Runs (پایین — کامل، IMPLEMENTED)؛ WP-12.3 Threshold Ratification (فقط Level Index — PO/G4) |

---

## WP-1.1 — Capture Foundation: Durable Capture Store & Integrity

```text
WP ID:        WP-1.1
Phase:        P1 — Capture Foundation
Status:       CLOSED — IMPLEMENTED (2026-10-01) | Acceptance: 8/8 AC PASS (REG-AR) | Tasks: 6/6 DONE (T-1.1.1..T-1.1.6 ✅) | G3: PASS (2026-10-01 — TM dispatch) | WP-1.2 / WP-1.3: معوق — طبق dispatch TM فعلاً اجرا نمی‌شوند
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** ذخیره‌سازی دائمی local و یکپارچگی artifactهای دریافتی — به‌طوری که هر artifact با `S1` قابل ردیابی، idempotent در سطح Capture، و مقاوم به restart/interruption باشد.

**Scope:**
- Capture Record (مدل رکورد دریافت artifact)
- persistent local storage (دائمی، local)
- تولید و ذخیره `S1` = `capture_content_fingerprint`
- integrity verification on read
- رفتار اولیه recovery (interrupted/incomplete capture)
- traceability (فیلدهای پیوند capture → S1 → رکورد + رزرو lineage برای مراحل بعد)

**Out of Scope:**
- Reconstruction (P2) | Extraction (P3) | انتخاب OCR/VLM (Deferred) | Holoo integration (P11 / D-04) | Canonical redesign | Digital Invoice (P10) | Inventory (AD-03) | Cloud implementation

**Inputs:** Decision Register (D-02, D-03, D-09) | Deferred Decision Register (DEF4) | همین WP Register | مهارتهای حذف‌شده از ACها ممنوع

**Dependencies:**
- G1 Architecture Approval (✅ PASS)
- G2 Work Package Approval (✅ PASS — 2026-10-01)

**Deliverables:**
1. `kandoo/specs/WP-1.1-capture-record-contract.md` — مشخصه Capture Record (پیوند از T-1.1.1)
2. Capture Store component (durable local persistence)
3. S1 Fingerprint Service (تولید/ذخیره/lookup)
4. Integrity Verification on Read (وضعیت fail صریح)
5. Initial Recovery Behavior
6. Test Suite + شواهد اجرا (پیوند به Acceptance Register)
7. به‌روزرسانی Task Register و Acceptance Register

**Acceptance Criteria:** (جزئیات verification در Acceptance Register)
- AC-1.1.1 — ایجاد و بازیابی Capture Record پس از restart
- AC-1.1.2 — S1 قطعی و حساس به محتوا (همان محتوا → همان S1؛ هر تغییر محتوا → S1 متفاوت)
- AC-1.1.3 — هر رکورد دقیقاً یک S1 ذخیره‌شده دارد؛ lookup با S1 ممکن است
- AC-1.1.4 — ارسال مجدد همان محتوا با lookup S1 شناسایی می‌شود (Capture-level idempotency — D-03)
- AC-1.1.5 — verify-on-read: محتوای دستکاری‌شده → fail صریح، بدون خواندنِ ساکتِ خراب
- AC-1.1.6 — durability: پس از پایان/راه‌اندازی مجدد process همه رکوردهای قبلی سالم و قابل خواندن‌اند
- AC-1.1.7 — capture قطع‌شده در شروع بعدی یا کامل یا با وضعیت صریح failed/incomplete علامت می‌خورد؛ هرگز رکورد نیمه‌ساخت به‌عنوان valid ارائه نمی‌شود
- AC-1.1.8 — فیلدهای traceability (capture_id، S1، timestamp، source label، رزرو lineage) در هر رکورد حاضرند

**Tests:** unit tests + property test تعیین‌کنندگی S1 (≥2 ورودی یکسان + mutation تک‌بایتی) | duplicate submission test | corruption injection | restart durability test | interruption injection | mechanism-agnostic (وابسته به انتخاب ذخیره‌سازی نیست)

**DoD:**
- [x] هر ۸ AC با شواهد در Acceptance Register بسته شده باشد (REG-AR: 8/8 PASS — T-1.1.6؛ 54/54 tests + SMOKE OK)
- [x] کد reviewed شده و انتخاب‌های delegated (مکانیزم ذخیره‌سازی، الگوریتم S1) در گزارش Task اعلام شده باشد (گزارش WP-1.1-IMPL تأیید TM؛ D-09)
- [x] هیچ قلم از Out of Scope / Forbidden Actions اجرا نشده باشد
- [x] Registerها (Task + Acceptance) به‌روز باشند
- [x] در صورت بروز مورد خارج از Baseline: STOP Protocol رعایت شده (N/A — موردی خارج از Baseline رخ نداد؛ OI-1/RSK-2 از قبل tracked و non-blocking)

---

## WP-1.2 — S1 Fingerprint & Integrity (Hardening)

```text
WP ID:        WP-1.2
Phase:        P1 — Capture Foundation
Status:       IMPLEMENTED (2026-10-09) | Acceptance: 4/4 AC PASS (REG-AR — در انتظار Acceptance رسمی PO) | Tasks: 4/4 DONE (T-1.2.1..T-1.2.4 ✅)
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** سخت‌سازی لایه اثر انگشت و یکپارچگی برای پوشش کامل رفتارهای لبه — اثبات + ثبت، نه بازطراحی (SPEC-WP12-S1H §1).

**Scope:**
- ماتریس ورودی‌های لبهٔ DECLARED (E1..E11: خالی، تک‌بایت، بزرگ 4MiB، چندزبانه، magic-prefix باینری، جهش مرزی، type exactness، فیلدهای hostile S1، fail-closed سطح ingest، کاوش store-defect، framing) — اجرا و ثبت روی لایهٔ فروزن WP-1.1
- تست‌های منفی/مرزی اضافی (هر نتیجهٔ ناسازگار فقط در outcome تایپ‌دار؛ هیچ مسیر ساکتی)
- گزارش agility الگوریتم (سطح constructor اعلام‌شدهٔ S1Service — P-S1-6؛ مقایسه فقط درون id برابر؛ uniqueness جفت‌کلید (s1, s1_algorithm_id))
- مستندسازی محدودیت‌های S1 (HARD-RPT-WP12 §4 — هفت بند الزامی)

**Out of Scope:**
تغییر تعریف S1 (Frozen D-02) | هر سیاست dedup سطح سند (D-03/P7) | انتخاب موتور خارجی | retention/purge (WP-1.3/DEF4) | هر تغییر فایل موجود (additive-only) | معنای downstream/canonical (INV-C7)

**Inputs:** خروجی‌های CLOSED WP-1.1 (src/capture: model/s1/store/service/recovery) | Decision Register D-02/D-03/D-09 | همین WP Register | Mission dispatch «CONTINUE FORWARD BEYOND BLOCKED P12 DECISIONS» (PO، 2026-10-09)

**Dependencies:** WP-1.1 (DoD کامل — CLOSED + G3 PASS 2026-10-01)

**Deliverables:**
1. `kandoo/specs/WP-1.2-s1-hardening-contract.md` — SPEC-WP12-S1H v1.0-MVP (decompose ثبت‌شده؛ §1..§11؛ OD-SH-A..F)
2. `kandoo/src/capture/tests/test_s1_hardening.py` — مجموعهٔ اختصاصی ماتریس لبه (۳۶ تست؛ E1..E11 + agility + hygiene)
3. `kandoo/src/run_smoke_s1_hardening.py` — بیستمین smoke (۸ گام cold-start)
4. `kandoo/specs/WP-1.2-hardening-report.md` — HARD-RPT-WP12 (نتایج ماتریس per-cell + agility + محدودیت‌ها + observation ثبت‌شده)
5. به‌روزرسانی Registerها (Task + Acceptance + همین Register) + src/README.md

**Acceptance Criteria:** (جزئیات در REG-AR)
- AC-1.2.1 — ماتریس لبهٔ کامل (E1..E11) اجرا و ثبت شده؛ DETERMINISTIC/CONTENT-SENSITIVE روی همهٔ کلاس‌های مربوطه برقرار
- AC-1.2.2 — هیچ ورودی لبه‌ای به S1 غیرقطعی یا fail ساکت نمی‌رسد؛ هر anomaly فقط در outcome تایپ‌دار فروزن (S1ComputationFailure / Verdict FAILED|NO_VERDICT / outcomeهای تایپ‌دار ingest/read / refusals تایپ‌دار store)
- AC-1.2.3 — binding تک‌الگوریتم + agility: فقط sha256-v1؛ id ناشناخته → NO_VERDICT (هرگز guessed)؛ مقایسه فقط درون id برابر؛ uniqueness جفت‌کلید
- AC-1.2.4 — مرزها و اثبات: additive-only (فایل‌های فروزن byte-identical)؛ بدون semantic dedup جدید؛ بدون موتور خارجی؛ محدودیت‌های S1 مستند؛ ×≥2 اجرای مستقل سبز + smoke + رگرسیون کامل

**Tests:** ماتریس لبهٔ کامل (خالی/تک‌بایت/4MiB/چندزبانه/magic/جهش/type/hostile/fail-closed/store-defect/framing) | negative tests نام‌برده (هرکدام outcome تایپ‌دار مشخص) | AST hygiene probe | ×≥2 اجرای مستقل | smoke بیستم | رگرسیون کامل + اثبات additive-only

**Implementation Record (2026-10-09 — T-1.2.1..T-1.2.4):**
- decompose ثبت‌شده (SPEC-WP12-S1H) و اجرا طبق deliverableهای ثبت‌شدهٔ WP (گزارش hardening + تست‌های لبه + به‌روزرسانی AR) — بدون هیچ تغییر کد تولیدی (OD-SH-F: اثبات، نه وصله).
- dedicated 36/36 (×3 تکرار مستقل)؛ SMOKE 8-گام cold-start OK (بیستمین smoke، ×2)؛ رگرسیون کامل 1476 جمع‌کل = 1475 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود (همان flake تاریخ‌حساس WP-7.1 — verbatim؛ تفکیک طبق Flake Policy). حساب additive: 1440 قبلی + 36 جدید = 1476 — صفر failure جدید.
- Observation ثبت‌شده برای TM/PO (HARD-RPT-WP12 §2.3): ورودی non-bytes در مرز ورود ingest به‌صورت fail-fast (TypeError/AttributeError از sniff مکانیکی) با ZERO residue crash می‌کند — پیش از هر فراخوانی store؛ ردِ تایپ‌دار در مرز capability (S1 compute/verify) است که طراحی فروزن آن را اعلام کرده؛ هیچ وصله‌ای در این WP additive اعمال نشد.

---

## WP-1.3 — Retention & Recovery (Completion)

```text
WP ID: WP-1.3 | Phase: P1 | Status: DEFINED — decompose after WP-1.1; policy values BLOCKED per DEF4
Owner Role: Backend Dev + QA | Agent Type: implementation + QA-verification
```

**Goal:** تکمیل mechanics نگهداری و recovery بدون وارد کردن مقادیر سیاست.
**Scope:** mechanics retention (قلاب‌های TTL/پاک‌سازی به‌صورت پارامتریک) | سخت‌سازی recovery (ماتریس crash، رکوردهای orphan) | گزارش‌گیری وضعیت.
**Out of Scope:** مقادیر retention/privacy (Blocked: DEF4 — PO) | حذف فیزیکی داده بدون سیاست مصوب | هر تغییر معماری ذخیره‌سازی.
**Inputs:** WP-1.1 deliverables | DEF4 | Decision Register.
**Dependencies:** WP-1.1 (DoD کامل).
**Deliverables:** mechanics retention پارامتریک + ماتریس recovery + شواهد تست.
**Acceptance Criteria:** (در زمان decompose) mechanics با مقادیر placeholder پارامتریک کار می‌کند؛ هیچ مقدار سیاست hardcoded نیست.
**Tests:** crash matrix + purge-parameter tests (بدون اجرای سیاست واقعی).
**DoD:** بسته‌شدن ACها با شواهد + ثبت صریح «policy values pending DEF4».

---

## WP-2.1 — Page Ordering & Artifact Reconstruction

```text
WP ID:        WP-2.1
Phase:        P2 — Reconstruction
Status:       CLOSED — IMPLEMENTED (2026-10-01) | Acceptance: 6/6 AC PASS (REG-AR) | Tasks: 4/4 DONE (T-2.1.1..T-2.1.4 ✅ — dispatch یکپارچه WP-2.1-IMPL به دستور TM: اجرای واقعی بدون چرخه مدیریتی جدید) | Tests: 101/101 PASSED (47 reconstruction + 54 capture رجرسیون) + SMOKE OK (run_smoke_reconstruction.py ۷ گام) + SMOKE OK رجرسیون WP-1.1 | WP-2.2: هنوز decompose نشده
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** تبدیل artifact/capture به یک ساختار Document/Page دائمی local و قابل اطمینان که مصرف‌پذیر برای Extraction (P3) باشد — بدون هیچ استخراج داده فاکتور و بدون تفسیر محتوایی.

**Scope:**
- ساختار Document/Page با پیوند صریح به capture_id/S1 (طبق Contract v1.1 §5 Extensibility Reservation)
- page ordering قطعی و بازتولیدپذیر (MVP: ترتیب صریح/تعیین‌شده؛ بدون heuristic معنایی)
- persistence دائمی local برای Document/Page (هم‌الگوی WP-1.1: lifecycle صریح + settlement قطعی + recovery اولیه)
- verify-on-read برای خروجی Reconstruction (هم‌اصل VOR — بدون ارائه ساکت خراب)
- رفتار اولیه recovery برای ساخت‌های نیمه‌تمام/قطع‌شده
- traceability (document_id، پیوند capture_id/S1، timestampها)

**Out of Scope:**
- هرگونه استخراج داده فاکتور (P3) | انتخاب/اجرا OCR/VLM (Frozen D-09) | S2/Identity Resolution (P7 — D-02) | dedup سطح سند (P7 — D-03) | Reconstruction Evidence (WP-2.2) | Holoo (P11/D-04) | heuristic ترتیب معنایی به‌عنوان target مهندسی (D-07) | مقادیر retention (DEF4)

**Inputs:** خروجی CLOSED WP-1.1 (Capture Store + S1 + VOR + recovery) | Decision Register (D-02, D-03, D-09, AS-01) | همین WP Register

**Dependencies:**
- G3 Phase Exit P1 (✅ PASS — 2026-10-01)
- WP-1.1 (✅ CLOSED — IMPLEMENTED، 8/8 AC PASS)

**Deliverables:**
1. `kandoo/specs/WP-2.1-reconstruction-contract.md` — مشخصه Document/Page (پیوند از T-2.1.1)
2. Document/Page Store component (durable local persistence)
3. Reconstruction Service (build + verified read + recovery)
4. Test Suite + شواهد اجرا (پیوند به Acceptance Register)
5. به‌روزرسانی Task Register و Acceptance Register

**Acceptance Criteria:** (جزئیات verification پس از اجرا در Acceptance Register ثبت می‌شود)
- AC-2.1.1 — برای هر capture COMPLETED، یک Document با پیوند صریح capture_id/S1 ایجاد و دائمی ذخیره می‌شود و پس از restart قابل بازیابی است
- AC-2.1.2 — page ordering قطعی و بازتولیدپذیر است: همان ورودی → همان ترتیب صفحات (بدون heuristic معنایی)
- AC-2.1.3 — هر page به منبع خود پیوند دارد و هیچ داده فاکتوری استخراج/حدس زده نمی‌شود (فقط ساختار)
- AC-2.1.4 — verify-on-read فعال است: سند/page دستکاری‌شده → fail صریح، بدون خواندن ساکتِ خراب
- AC-2.1.5 — ساخت نیمه‌تمام/قطع‌شده در شروع بعدی یا کامل یا صریحاً failed تسویه می‌شود؛ هیچ سند نیمه‌ساخت valid ارائه نمی‌شود
- AC-2.1.6 — فیلدهای traceability (document_id، پیوند capture_id/S1، timestampها) در هر سند حاضرند

**Tests:** deterministic ordering test | no-extraction boundary test (ساختاری) | corruption injection | restart durability | interruption injection | mechanism-agnostic

**DoD:**
- [x] هر ۶ AC با شواهد در Acceptance Register بسته شده باشد (REG-AR: 6/6 PASS — WP-2.1-IMPL؛ 101/101 tests + SMOKE OK)
- [x] انتخاب‌های delegated (مکانیزم ذخیره‌سازی، استراتژی page derivation) در گزارش Task اعلام شده باشد (D-09 — SQLite stdlib فایل مجزا؛ پارس مکانیکی framing تجمیع Frozen WP-1.1)
- [x] هیچ قلم از Out of Scope / Forbidden Actions اجرا نشده باشد (بدون OCR/VLM/Extraction/S2/dedup سند؛ Capture Store Frozen دست‌نخورده)
- [x] Registerها (Task + Acceptance) به‌روز باشند
- [x] در صورت بروز مورد خارج از Baseline: STOP Protocol رعایت شده (N/A — موردی خارج از Baseline رخ نداد)

---

## WP-2.2 — Reconstruction Evidence

```text
WP ID:        WP-2.2
Phase:        P2 — Reconstruction
Status:       CLOSED — IMPLEMENTED (2026-10-01) | Acceptance: 6/6 AC PASS (REG-AR) | Tasks: 3/3 DONE (T-2.2.1..T-2.2.3 ✅ — dispatch یکپارچه WP-2.2-IMPL به دستور TM 2026-10-01: «مستقیماً سراغ اولین WP بعدی در مسیر P2 — بدون فاز طراحی/Review جدید») | Tests: 126/126 PASSED (54 capture + 47 reconstruction + 25 evidence) + SMOKE OK × ۳ (run_smoke_evidence.py ۶ گام + رجرسیون run_smoke_reconstruction.py + run_smoke.py) | Blocker: هیچ
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** تولید و نگهداری شواهد ساختاری دائمی و ضد دستکاری برای مرحله Reconstruction — پیوند هر Document/Page به منبع Capture آن (capture_id/S1 + بازه بایتی هر page در artifact) و ثبت رویدادهای lifecycle — به‌طوری که WP-3.2 (Evidence Binding) بتواند مصرف کند؛ بدون هیچ محتوا یا داده تفسیری.

**Scope:**
- Evidence log فقط-الحاقی (append-only) در فایل DB مجزا (هم‌الگوی WP-2.1: SQLite stdlib، synchronous=FULL)
- واژگان رویداد ثابت document-scoped: DOCUMENT_COMPLETED | DOCUMENT_SETTLED_FAILED | VERIFIED_READ | RECOVERY_SETTLED
- fingerprint هر record با قابلیت S1 موجود (sha256-v1) + زنجیره هش سراسری ضد دستکاری + لنگر head (کشف truncation)
- binding page_index → (byte_start, byte_end) در artifact منبع — مشتق قطعی از وضعیت durable (spans_from_durable)
- verified evidence read (الگوی VOR روی evidence) + verify_chain سراسری
- اتصال غیرمخرب به ReconstructionService و recovery (پارامتر اختیاری؛ عدم تغییر هر رفتار Frozen WP-2.1)

**Out of Scope:**
- هرگونه استخراج داده (P3) | OCR/VLM (Frozen D-09) | S2/dedup سند (P7 — D-02/D-03) | audit سطح attempt برای outcomeهای بدون سند (deferred) | retention/purge (WP-1.3/DEF4) | evidence لایه Capture | Gate فاز P2 (تصمیم PM+QA/PO)

**Inputs:** WP-2.1 CLOSED (Document/Page Store + Service + Recovery) | SPEC-WP21-RC | Decision Register (D-02, D-03, D-09, AS-01) | همین WP Register

**Dependencies:**
- WP-2.1 (✅ CLOSED — IMPLEMENTED، 6/6 AC PASS)
- G3 (✅ PASS — 2026-10-01)

**Deliverables:**
1. `kandoo/specs/WP-2.2-reconstruction-evidence-contract.md` — مشخصه Evidence (پیوند از T-2.2.1)
2. Evidence Store component (append-only + chain + verified read) — `kandoo/src/reconstruction/evidence.py`
3. اتصال service/recovery (emission غیرمخرب) + خروجی‌های پکیج
4. Test Suite (۲۵ تست) + `kandoo/src/run_smoke_evidence.py` (E2E واقعی)
5. به‌روزرسانی Task Register و Acceptance Register

**Acceptance Criteria:** (جزئیات verification در Acceptance Register)
- AC-2.2.1 — برای هر reconstruct نهایی یک evidence record دائمی با پیوند document_id/capture_id/capture_s1 ثبت و پس از restart قابل خواندن است
- AC-2.2.2 — DOCUMENT_COMPLETED حاوی binding page_index → بازه بایتی منبع است؛ هر بازه بایت‌به‌بایت با محتوای page ذخیره‌شده و fingerprint آن برابر است و بازه‌ها artifact را دقیقاً tile می‌کنند
- AC-2.2.3 — evidence ضد دستکاری است: جهش فیلد، حذف ردیف/انتها، حذف لنگر، درج جعلی → fail صریح در خواندن بعدی؛ هیچ خواندن ساکتِ خرابِ evidence وجود ندارد
- AC-2.2.4 — evidence فقط داده ساختاری حمل می‌کند (کلیدهای payload مجاز ثابت)؛ هیچ محتوا/داده تفسیری وارد evidence نمی‌شود
- AC-2.2.5 — شکست evidence رفتار Reconstruction را تغییر نمی‌دهد و هرگز ساکت نیست (issue surfacing)؛ رگرسیون کامل WP-2.1/WP-1.1 سبز می‌ماند
- AC-2.2.6 — رویدادهای lifecycle واقعی (build/settle/verified-read/recovery-settled) فقط-الحاقی با seq صعودی و timestamp ثبت می‌شوند

**Tests:** binding fidelity (slice == page bytes) | tamper matrix (فیلد/حذف/لنگر/درج) | concurrency append (۸ نخ) | restart durability | non-intrusive failure | structural no-content | mechanism-agnostic

**DoD:**
- [x] هر ۶ AC با شواهد در Acceptance Register بسته شده باشد (REG-AR: 6/6 PASS — WP-2.2-IMPL؛ 126/126 tests + SMOKE OK × ۳)
- [x] انتخاب‌های delegated اعلام شده باشد (D-09 — OD-E1 فایل DB مجزا؛ OD-E3 زنجیره + لنگر head؛ OD-E4 spans از وضعیت durable؛ OD-E5 recorder غیرمخرب)
- [x] هیچ قلم از Out of Scope / Forbidden Actions اجرا نشده باشد (بدون Extraction/OCR/VLM/S2/dedup؛ رفتار Frozen WP-2.1/WP-1.1 دست‌نخورده — 101/101 رگرسیون)
- [x] Registerها (Task + Acceptance) به‌روز باشند
- [x] در صورت بروز مورد خارج از Baseline: STOP Protocol رعایت شده (N/A — موردی خارج از Baseline رخ نداد)

---

## WP-3.1 — Engine-Agnostic Extraction Pipeline

```text
WP ID:        WP-3.1
Phase:        P3 — Extraction
Status:       IMPLEMENTED (2026-10-01) | Acceptance: 6/6 AC PASS (REG-AR) | Tasks: 3/3 DONE (T-3.1.1..T-3.1.3 ✅ — dispatch یکپارچه WP-3.1-IMPL به دستور TM 2026-10-01: «وارد P3 شو — decomposition فقط به اندازه لازم و inline، بلافاصله ساخت واقعی») | Tests: 164/164 PASSED (54 capture + 72 reconstruction + 38 extraction) + SMOKE OK × ۴ (run_smoke_extraction.py ۶ گام + رجرسیون سه Smoke قبلی) | Blocker: هیچ
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** ساخت زیرساخت واقعی Extraction: `Document/Page → Extraction-ready input → Extracted structured data` — engine-agnostic با abstraction قابل‌تعویض (بدون انتخاب OCR/VLM طبق D-09)، با traceability کامل به Document/Page و source span/position، و بدون ورود به Normalization/Canonicalization/Validation/Invoice.

**Scope:**
- ExtractionInput (پروجکشن صریح extraction-ready) فقط از DocumentReadSuccess تأییدشده (مرز §7 قرارداد WP-2.1 — بدون تفسیر موازی artifact خام)
- ExtractionEngine ABC قابل‌تعویض + ReferenceDelimitedEngine (موتور مرجع قطعی برای اجراپذیری MVP؛ grammar اعلان‌شده — انتخاب موتور محصول باقی deferred است)
- اعتبارسنجی قرارداد موتور (C1..C5) قبل از persistence — fail-closed
- ExtractionStore دائمی (فایل DB مجزا؛ commit اتمیک record+fields — صفر residue؛ بدون UPDATE/DELETE)
- INV-X-1:1: حداکثر یک record به‌ازای (document_id, engine_id, engine_schema_version) — replay صریح؛ موتور/schema دیگر → record جدا
- verified extraction read (الگوی VOR با record_fingerprint sha256-v1)
- Provenance مدل D-01 (EXTRACTED | DERIVED | UNRESOLVED) — این لایه فقط EXTRACTED تولید/ذخیره می‌کند (CHECK سطح storage)

**Out of Scope:**
- Normalization/Canonicalization/Validation/Invoice/Digital Invoice (P4+) | انتخاب OCR/VLM/موتور واقعی (Frozen D-09) | S2/dedup سند (P7 — D-02/D-03؛ توالی فیلدها هرگز dedup نمی‌شود) | نگاشت فیلد Canonical (P6 — نقل AS-04) | WP-3.2 Evidence Binding | مقادیر retention (DEF4) | تغییر Capture یا Reconstruction

**Inputs:** WP-2.1 CLOSED (DocumentReadSuccess + PageView — مرز §7) | WP-2.2 CLOSED | Decision Register (D-01, D-02, D-03, D-09, AS-01) | همین WP Register

**Dependencies:**
- Phase P2 (✅ کامل — اعلام TM 2026-10-01)
- WP-2.1 / WP-2.2 (✅ CLOSED — IMPLEMENTED)

**Deliverables:**
1. `kandoo/specs/WP-3.1-extraction-contract.md` — مشخصه Extraction v1.0-MVP (پیوند از T-3.1.1)
2. Extraction Layer: `kandoo/src/extraction/` (model.py / engine.py / store.py / service.py / __init__.py)
3. Test Suite (۳۸ تست) + `kandoo/src/run_smoke_extraction.py` (E2E واقعی ۶ گام)
4. به‌روزرسانی Task Register و Acceptance Register

**Acceptance Criteria:** (جزئیات verification در Acceptance Register)
- AC-3.1.1 — برای هر سند تأییدشده، extraction یک record ساختاریافته دائمی با پیوند صریح document_id/capture_id/capture_s1 تولید می‌کند و پس از restart قابل خواندن است
- AC-3.1.2 — pipeline موتور-آگنوستیک است: موتورها پشت یک interface یکسان تعویض می‌شوند؛ خروجی موتور (spans/indices/provenance) پیش از persistence اعتبارسنجی می‌شود؛ موتور ناشناس → outcome صریح، هرگز ساکت نیست
- AC-3.1.3 — هر فیلد استخراج‌شده به منبع خود پیوند دارد: page_index + بازه بایتی + page_fingerprint؛ value_verbatim دقیقاً برابر decoding بایت‌های بازه است (بدون هیچ تبدیل/normalization)
- AC-3.1.4 — idempotency سطح Extraction: همان (document_id, engine_id, engine_schema_version) → دقیقاً یک record؛ replay موجودِ صریح؛ موتور/schema دیگر → record جدا
- AC-3.1.5 — verified extraction read فعال است: record/field دستکاری‌شده → fail صریح بدون تحویل محتوا؛ همه outcomeها صریح‌اند (source/refused/engine failure/contract violation/storage)
- AC-3.1.6 — مرز: هیچ داده normalization/canonicalization/validation/invoice در مدل/store/outcomes نیست؛ provenance فقط EXTRACTED (واژگان D-01 رزرو)؛ رفتار Frozen WP-1.1/WP-2.1/WP-2.2 دست‌نخورده (رگرسیون کامل سبز)

**Tests:** determinism موتور مرجع | verbatim span binding (slice decode == value) | ماتریس contract violation (۶ بردار fail-closed) | INV-X-1:1 + چند موتور | durability/restart | tamper matrix (field/record scalar/row deletion) | explicit outcomes (unknown engine، engine failure، source refused، source integrity failure) | مرز ساختاری (field-set/columns دقیق + EXTRACTED-only) | mechanism-agnostic

**DoD:**
- [x] هر ۶ AC با شواهد در Acceptance Register بسته شده باشد (REG-AR: 6/6 PASS — WP-3.1-IMPL؛ 164/164 tests + SMOKE OK × ۴)
- [x] انتخاب‌های delegated اعلام شده باشد (D-09 — OD-X1..OD-X8 در store.py + §1/§4/§8 Contract؛ reference engine = انتخاب اجراپذیری MVP، نه انتخاب موتور محصول)
- [x] هیچ قلم از Out of Scope / Forbidden Actions اجرا نشده باشد (بدون OCR/VLM/Normalization/S2/dedup؛ Capture/Reconstruction Frozen دست‌نخورده — 126/126 رگرسیون سبز)
- [x] Registerها (Task + Acceptance) به‌روز باشند
- [x] در صورت بروز مورد خارج از Baseline: STOP Protocol رعایت شده (N/A — موردی خارج از Baseline رخ نداد)

---

## WP-3.2 — Extraction Evidence Binding

```text
WP ID:        WP-3.2
Phase:        P3 — Extraction
Status:       IMPLEMENTED (2026-10-01) | Acceptance: 4/4 AC PASS (REG-AR) | Tasks: 3/3 DONE (T-3.2.1..T-3.2.3 ✅ — dispatch یکپارچه WP-3.2-IMPL به دستور TM 2026-10-01: «بدون باز کردن WP-3.1 و بدون ایجاد Design/Review Stage جدید، مستقیماً WP-3.2 را اجرا کن») | Tests: 200/200 PASSED (54 capture + 72 reconstruction + 38 extraction + 36 binding) + SMOKE OK × ۵ (run_smoke_binding.py ۸ گام + رگرسیون چهار Smoke قبلی) | Blocker: هیچ
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** اتصال قابل‌اثبات خروجی Extraction به Evidence/Document/Page با حفظ traceability تا source — برای هر extracted field بتوان به‌صورت ماشین‌چک‌پذیر مشخص کرد داده از کدام Document/Page و کدام source span/position آمده است، و این اثبات دائمی و ضد دستکاری باشد.

**Scope:**
- ExtractionBindingStore دائمی (فایل DB مجزا؛ append-only؛ commit اتمیک binding+entries؛ INV-B-1:1: حداکثر یک binding به‌ازای extraction_id — in-txn check + UNIQUE backstop؛ replay صریح)
- binding_fingerprint (sha256-v1 با reuse capture S1) روی canonical bytes از record scalars + همه entries در field_seq order؛ hash chain سراسری (prev_binding_hash → binding_hash، genesis 64×"0") + head anchor (نگهبان truncation) — الگوی WP-2.2، لایه جدید، صفر دست‌زدن به log فروزن
- bind_extraction با راستی‌آزمایی کامل زنجیره در لحظه bind: verified extraction read → fresh verified document read (+ تطبیق linkage) → verified evidence read (لنگر DOCUMENT_COMPLETED: seq + record_hash) → span fidelity کامل → atomic append
- read_binding با الگوی VOR پنج‌حلقه‌ای داخل خود read: binding log / extraction (برابری fingerprint لنگرشده) / document / evidence anchor / span fidelity؛ شکست هر حلقه → BindingReadIntegrityFailure با attribution قطعی BindingLink (binding | extraction | document | evidence | span) و بدون تحویل entries
- bindings_for_document (مصرف extraction_ids_for_document؛ بدون fabrication) + verify_chain (audit کل log) + issue_reports
- لنگر متقاطع رمزنگارانه بین log binding و evidence log فروزن WP-2.2 — بدون افزودن event type جدید به vocabulary فروزن

**Out of Scope:**
- تغییر Capture (WP-1.1) / Reconstruction (WP-2.1) / Evidence log (WP-2.2 — فقط read-only از verified-read موجود) | بازنویسی رفتار WP-3.1 (فقط exportهای additive به __init__) | hook خودکار binding داخل extract() | هر داده تفسیری Normalization/Canonicalization/Validation (P4+) | DERIVED evidence (WP-4.2) | retention (DEF4)

**Inputs:** WP-3.1 CLOSED (ExtractionRecord + spans + extraction_ids_for_document) | WP-2.2 CLOSED (DOCUMENT_COMPLETED page_spans — مصرف read-only) | WP-2.1/WP-1.1 Frozen (verified reads) | Decision Register (D-01, D-02, D-03, D-09, AS-01)

**Dependencies:**
- WP-3.1 (✅ CLOSED — IMPLEMENTED)
- Phase P2 (✅ کامل — هر دو WP بسته)

**Deliverables:**
1. `kandoo/specs/WP-3.2-evidence-binding-contract.md` — مشخصه Evidence Binding v1.0-MVP (inline از T-3.2.1)
2. Binding Layer: `kandoo/src/extraction/binding_model.py` + `kandoo/src/extraction/binding.py` (store + binder) + exportهای additive در `__init__.py`
3. Test Suite (۳۶ تست) + `kandoo/src/run_smoke_binding.py` (E2E واقعی ۸ گام)
4. به‌روزرسانی Task Register و Acceptance Register + src/README.md (اعلام OD-B1..OD-B7)

**Acceptance Criteria:** (جزئیات verification در Acceptance Register)
- AC-3.2.1 — bind فقط پس از راستی‌آزمایی هر پنج حلقه در لحظه bind ایجاد می‌شود؛ replay صریح با همان binding_id؛ همه outcomeها صریح (Completed/AlreadyExists/SourceIntegrityFailure/SourceRefused/SourceUnavailable/StorageUnavailable)؛ رد شدن → صفر residue
- AC-3.2.2 — هر field از طریق binding به Document/Page (page_index + page_fingerprint) و span دقیق منبع حل می‌شود؛ walk کامل field → page → artifact span (evidence WP-2.2) → capture S1 ماشین‌چک‌پذیر؛ enumeration سند-محور قطعی و بدون fabrication
- AC-3.2.3 — verified binding read (VOR) همه حلقه‌ها را داخل read بازررسی می‌کند؛ هر بردار دستکاری/حذف/جعل → IntegrityFailure با attribution قطعی یکی از پنج BindingLink، بدون تحویل entries؛ NO_VERDICT → VerificationUnavailable با Issue-Report؛ حذف bound extraction/evidence قابل اثبات است
- AC-3.2.4 — durability/restart (synchronous=FULL، append-only، بدون UPDATE/DELETE)؛ tamper-evidence خود log (chain + head anchor: حذف دم/جعل میانی کشف می‌شود)؛ idempotency؛ مرز ساختاری: payload فقط ساختاری (بدون value)؛ رگرسیون کامل Frozen سبز (200/200)

**Tests:** whole-chain bind | replay/INV-B-1:1 | provenance walk چهار حلقه‌ای | enumeration دو سند × دو موتور | ماتریس bind-path (unknown extraction / extraction tampered / document tampered / evidence absent) | ماتریس read-path ۸ بردار با link attribution (BINDING: entry offset/scalar/field-name/tail-deletion؛ EXTRACTION: value tamper/record deletion؛ EVIDENCE: payload tamper/anchor drift؛ DOCUMENT: content tamper/page-set defect؛ SPAN: coherent forgery) | NO_VERDICT (الگوریتم lنگر نامطمئن) | content-free failures | restart | chain audit (tail deletion + mid-log forgery) | zero residue | 8-thread concurrent append exactness | boundary ساختاری (field-sets دقیق، بدون value در payload/canonical/rows، بدون ستون value، بدون مسیر UPDATE/DELETE در API، سالم ماندن هر چهار لایه پس از ترافیک binding)

**DoD:**
- [x] هر ۴ AC با شواهد در Acceptance Register بسته شده باشد (REG-AR: 4/4 PASS — WP-3.2-IMPL؛ 200/200 tests + SMOKE OK × ۵)
- [x] انتخاب‌های delegated اعلام شده باشد (D-09 — OD-B1..OD-B7 در binding.py + §6 Contract)
- [x] هیچ قلم از Out of Scope / Forbidden Actions اجرا نشده باشد (Capture/Reconstruction/Evidence/Extraction Frozen — صفر تغییر کد؛ فقط export additive؛ Evidence فقط read-only)
- [x] Registerها (Task + Acceptance) به‌روز باشند
- [x] در صورت بروز مورد خارج از Baseline: STOP Protocol رعایت شده (N/A — موردی خارج از Baseline رخ نداد؛ دو باگ یافت‌شده در Build→Test→Fix هر دو در کد جدید همین WP بودند: crash به‌جای outcome صریح هنگام نبود evidence store، و ترتیب head-guard قبل از refusal در read)

---

## WP-4.1 — Normalization Rules

```text
WP ID:        WP-4.1
Phase:        P4 — Normalization
Status:       **FROZEN (2026-10-05 — formal freeze dispatch PO/TM؛ بدون contradiction؛ SPEC-WP41-NORM v1.0-MVP + §4.1/§4.2 سند Frozen این لایه است — تغییرات آینده فقط از seam نسخه جدید ruleset)** | IMPLEMENTED + PRE-FREEZE CLARIFICATION (2026-10-05) | Acceptance: 4/4 AC PASS (REG-AR — evidence حفظ شده) | Tasks: 5/5 DONE (T-4.1.1..T-4.1.3 ✅ dispatch یکپارچه WP-4.1-IMPL به دستور TM 2026-10-01؛ T-4.1.4 ✅ اصلاح نهایی پیش از Freeze به دستور PO/TM 2026-10-05 — شفاف‌سازی §4.1/§4.2: DEFERRED ≠ UNRESOLVED + مرز DERIVED؛ T-4.1.5 ✅ Freeze رسمی) | Tests: 292/292 PASSED (54 capture + 72 reconstruction + 38 extraction + 36 binding + 92 normalization [84 + 8 تست مرزی جدید]) + SMOKE OK × ۶ (run_smoke_normalization.py ۸ گام + رگرسیون پنج Smoke قبلی) | Blocker: هیچ
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** تبدیل قطعی و مستقل از موتورِ خروجی Extraction به داده Normalized ساختاراً پایدار برای Canonicalization Gate — بدون هیچ تصمیم هویتی/business و با حفظ traceability تا source extracted value و از آن طریق تا Document/Page/span و Capture S1.

**Scope:**
- NormalizationRuleSet قابل‌تعویض + ReferenceNormalizationRulesV1 (ruleset مرجع قطعی با grammar اعلان‌شده: control gate → NFC → trim → kind rule؛ kinds: text | decimal | date با kind_profile اعلانی و fallback text برای نام‌های ناشناخته)
- وضعیت صریح per-field: NORMALIZED | DEFERRED | REJECTED (+ reason codes ثابت) — نگاشت TOTAL و positional؛ هیچ مقداری جعل یا «تعمیر» نمی‌شود
- عدد کانونی به‌صورت STRING اعشاری (بدون float)؛ حفظ دقیق ارقام اعشار (بدون rounding/حذف صفر انتهایی)؛ الگوهای مبهم → DEFER صریح (هرگز حدس زده نمی‌شود)
- NormalizationStore دائمی (فایل DB مجزا؛ commit اتمیک record+fields — صفر residue؛ بدون UPDATE/DELETE)
- INV-N-1:1: حداکثر یک record به‌ازای (extraction_id, ruleset_id, ruleset_version) — replay صریح؛ ruleset/نسخه دیگر → record جدا
- verified normalization read (الگوی VOR با record_fingerprint sha256-v1 — reuse S1Service)
- relay verbatim پرووننس D-01 (فقط EXTRACTED در این لایه — CHECK سطح storage؛ DERIVED = WP-4.2، UNRESOLVED = P5)

**Out of Scope:**
- Canonical field mapping / Canonicalization Gate (P6) | Product/Customer/Invoice identity و fuzzy/semantic matching | Invoice/Digital Invoice/Sale/Inventory (D-06/AD-03) | tax/business rules | اختراع/تبدیل ارز | محاسبه DERIVED (WP-4.2) | UNRESOLVED (P5) | OCR/VLM/موتور جدید (D-09) | S2/dedup سند (P7) | retention (DEF4) | تغییر هر لایه Frozen P1/P2/P3

**Inputs:** WP-3.1 CLOSED (ExtractionReadSuccess از verified read — تنها مسیر ورودی طبق SPEC §2) | WP-3.2 CLOSED (مصرف read-only در E2E) | Decision Register (D-01, D-02, D-03, D-09, AS-01) | همین WP Register

**Dependencies:**
- Phase P3 (✅ کامل — WP-3.1 + WP-3.2 هر دو IMPLEMENTED)
- WP-3.1 verified extraction read (✅ CLOSED)

**Deliverables:**
1. `kandoo/specs/WP-4.1-normalization-contract.md` — مشخصه Normalization v1.0-MVP (inline از T-4.1.1)
2. Normalization Layer: `kandoo/src/normalization/` (model.py / rules.py / store.py / service.py / __init__.py)
3. Test Suite (۹۲ تست) + `kandoo/src/run_smoke_normalization.py` (E2E واقعی ۸ گام)
4. به‌روزرسانی Task Register و Acceptance Register + src/README.md (اعلام OD-N1..OD-N8)

**Acceptance Criteria:** (جزئیات verification در Acceptance Register)
- AC-4.1.1 — نرمال‌سازی قطعی per-field با نگاشت TOTAL positional؛ statuses/reasons صریح؛ خروجی محتوایی تابع خالص (محتوای ورودی + نسخه ruleset)؛ provenance فقط EXTRACTED (relay D-01؛ هرگز بازتخصیص نمی‌شود)
- AC-4.1.2 — traceability ماشین‌چک‌پذیر: هر normalized field → (extraction_id, field_seq) → value_verbatim → binding WP-3.2 → Document/Page/span → Capture S1؛ تضمین‌های binding/evidence پس از ترافیک normalization دست‌نخورده
- AC-4.1.3 — persistence طبق الگوی پروژه: SQLite فایل مجزا، synchronous=FULL، commit اتمیک، INV-N-1:1 با replay صریح، بدون UPDATE/DELETE، verified read (VOR)، restart-safe، صفر residue در ردشدگی‌ها
- AC-4.1.4 — مرز: هیچ datum کانونی/هویتی/business در مدل/store نیست؛ مستقل از موتور (import صفر از engineها؛ هم‌ارزی stub engine)؛ رگرسیون کامل Frozen سبز

**Tests:** ماتریس grammar عددی (پذیرش/ابهام→DEFER/ناقص→DEFER) | NFC/trim/حفظ whitespace داخلی | empty/whitespace-only → DEFER | date ISO اعتبار تقویمی | control char → REJECTED | نگاشت TOTAL و counts reconciled | INV-N-1:1 + ruleset دیگر → record جدا | unknown ruleset/extraction صریح | tampered extraction → fail-closed + صفر residue | engine-independence (stub equivalence) | قطعیت محتوا (دو ruleset هم‌گرامر → مقادیر برابر) | VOR tamper matrix (value/scalar/status-gate/row-deletion/NO_VERDICT) | restart/idempotency پس از restart | gates سطح storage (provenance/status/value/reason) | مرز ساختاری (field-sets دقیق، بدون ستون کانونی/هویتی، بدون کپی span/content) | E2E walk کامل تا S1 با restart | مرز پیش از Freeze (T-4.1.4 — test_norm_freeze_boundary.py: عدد مبهم/ناقص و تاریخ پشتیبانی‌نشده → DEFERRED و هرگز UNRESOLVED | sweep بدون هر datum UNRESOLVED در رکورد durable | بدون مقادیر DERIVED + رد ساختاری DERIVED/UNRESOLVED در storage gate | بدون محاسبهٔ unit_amount/فیلد جعلی | قطعیت خروجی‌های grammar اعلان‌شده دست‌نخورده) | رگرسیون کامل

**DoD:**
- [x] هر ۴ AC با شواهد در Acceptance Register بسته شده باشد (REG-AR: 4/4 PASS — WP-4.1-IMPL؛ 284/284 tests + SMOKE OK × ۶)
- [x] انتخاب‌های delegated اعلام شده باشد (D-09 — OD-N1..OD-N8 در store.py/service.py + §9 Contract)
- [x] هیچ قلم از Out of Scope / Forbidden Actions اجرا نشده باشد (صفر تغییر در کد Frozen P1/P2/P3؛ هیچ datum کانونی/هویتی؛ DERIVED/UNRESOLVED تولید نشد)
- [x] Registerها (Task + Acceptance) به‌روز باشند
- [x] در صورت بروز مورد خارج از Baseline: STOP Protocol رعایت شده (N/A — موردی خارج از Baseline رخ نداد؛ باگ‌های یافت‌شده در Build→Test→Fix همگی در کد جدید همین WP بودند: shape نادرست ExtractionReadSuccess در service، نام کلاس import در store، و اصلاح یک تست برخلاف grammar اعلان‌شده قرارداد)

---

## WP-4.2 — DERIVED Provenance & Exact Derivation Mechanism (rescoped 2026-10-05)

```text
WP ID:        WP-4.2
Phase:        P4 — Normalization (AS-01 position: قبل از Canonicalization Gate)
Status:       IMPLEMENTED (2026-10-06 — dispatch اجرایی PO/TM: «BUILD واقعی، نه گزارش
              طراحی دیگر») | Scope ثبت‌شده (rescoped 2026-10-05) عیناً به implementation
              contract تبدیل شد: SPEC-WP42-DER v1.0-MVP (kandoo/specs/WP-4.2-derivation-
              contract.md) | Taskهای واقعی: T-4.2.1..T-4.2.4 (همه DONE) | 4/4 AC PASS |
              P4.2 101/101 + رگرسیون کامل 393/393 + SMOKE OK × ۷ (شامل
              run_smoke_derivation.py ۸ گام) | تغییر کد: فقط فایل‌های جدید
              (src/derivation/ + run_smoke_derivation.py) — صفر تغییر در P1–P4.1 Frozen
Owner Role:   Technical Manager + Backend Dev + QA (acceptance: PO)
Agent Type:   implementation agent (انجام شد — 2026-10-06)
```

**Goal:** تولید provenance مدل و سازوکار قطعی محاسبهٔ DERIVED طبق D-01 — فقط با arithmetic دقیق
(بدون rounding، بدون float) و فقط روی ورودی‌هایی که درون یک extraction record «بدون ابهام»
شناسایی می‌شوند — با traceability ماشین‌چک‌پذیر تا source؛ بدون هیچ تصمیم association/هویتی/business.

**واژگان مرجع (تفاوت‌ها — normative برای این WP):**

| مفهوم | لایه/فاز | معنا |
|---|---|---|
| `EXTRACTED` | P3 (WP-3.1) | label پرووننس مقدار verbatim خوانده‌شده از artifact؛ همیشه evidence-bound (WP-3.2) |
| `NORMALIZED` | P4.1 (FROZEN) | **status** لایه Normalization — نه label پرووننس: مقدار verbatim زیر grammar اعلان‌شده به شکل کانونی تبدیل شد |
| `DEFERRED` | P4.1 (FROZEN) | **status** لایه Normalization: تبدیل امن زیر grammar ممکن نبود — بدون تفسیر، بدون اختراع؛ `DEFERRED ≠ UNRESOLVED` (SPEC-WP41-NORM §4.1) |
| `DERIVED` | P4.2 (این WP) | label پرووننس D-01: مقداری که «خوانده» نشده بلکه از ورودی‌های دارای evidence با فرمول اعلان‌شده محاسبه شده |
| `UNRESOLVED` | P5 (Validation) | label پرووننس D-01 — انتهای ترتیب حل `EXTRACTED → DERIVED → UNRESOLVED`؛ تولیدش طبق یادداشت موجود Registerها با P5 است (AD-04: می‌تواند Invoice را به REVIEW ببرد)؛ P3/P4.1/P4.2 آن را تولید نمی‌کنند |

**قاعدهٔ محاسبه‌پذیری قبل از Canonicalization (هستهٔ rescope):** یک derivation فقط زمانی در P4.2
قابل اجرا است که «همهٔ» شرایط زیر برقرار باشد:
1. هر ورودی درون همان extraction record بدون ابهام شناسایی شود — singleton سطح سند با نام فیلد
   یکتا (مثلاً دقیقاً یک total.net و یک tax.amount)، یا فیلد line-scoped که خود موتور استخراج
   صراحتاً اعلام کرده باشد؛
2. همهٔ ورودی‌ها دارای evidence باشند (EXTRACTED + binding سالم WP-3.2) و مقادیر NORMALIZED
   آن‌ها موجود باشد (DEFERRED/REJECTED → refusal صریح، نه حدس)؛
3. فرمول «اعلان‌شده» باشد (formula_id + نسخه در registry داده‌ای — نه inference) و نتیجه با
   arithmetic دقیق (اعشاری string/گویا) بدون هیچ rounding به‌دست آید؛
4. نتیجهٔ غیردقیق (مثلاً تقسیم غیرمتناهی) → refusal صریح — هرگز گرد نمی‌شود (rounding = D-08/WP-5.1).

**نتیجهٔ عملی برای unit_amount:** `unit_amount = total / quantity` به‌عنوان قاعدهٔ عمومی «در
P4.2 پیاده نمی‌شود» — (۱) برای سند چندخطی association-ambiguous است (line grouping متعلق به
Canonicalization Gate است) و (۲) تقسیم عموماً غیردقیق است و نیاز به R2 دارد که D-08 آن را به
WP-5.1 سپرده. این محاسبه فقط پس از P6 — آنجا که mapping کانونی خطوط/فیلدها مشخص شده — و با
قاعدهٔ rounding پارامتریک WP-5.1 قابل instant شدن است؛ سازوکار P4.2 باید طوری ساخته شود که
P6 بتواند بدون تغییر مجدد، derivationهای line-scoped اعلانی را از همین seam اجرا کند.

**Scope (مجاز):**
1. پرووننس مدل DERIVED (D-01 verbatim — label فقط روی خروجی derivation اعلانی؛ CHECK سطح storage)
2. فرمول‌ریجیstry اعلانی (formula_id + version + امضای ورودی + تعریف arithmetic دقیق — داده، نه کد پنهان)
3. موتور derivation با arithmetic دقیق روی مقادیر NORMALIZED (decimal string؛ بدون float/rounding)
4. outcomeهای صریح و exhaustive (Completed | Refused به دلایل اعلانی: ورودی ناکافی/غیردقیق/فرمول
   ثبت‌نشده/duplicate | شکست integrity منبع) — هرگز silent
5. traceability: derived record → اشاره‌گر ورودی‌ها (normalization_id/extraction_id + field_seq) →
   extracted field → binding WP-3.2 → Document/Page/span → Capture S1 (الگوی pointer، بدون کپی داده)
6. persistence طبق الگوی پروژه (SQLite فایل مجزا، synchronous=FULL، commit اتمیک، INV idempotency
   triple، بدون UPDATE/DELETE، verified read با fingerprint sha256-v1)
7. تست‌های رفتاری مرز (دقیقاً مثل WP-4.1: REFUSAL ماتریس، قطعیت، tamper، رگرسیون کامل Frozen)

**Out of Scope (صریح — ممنوع به‌دلیل نیاز به semantics دامنه/معماری Frozen):**
- Line-item grouping / کشف association بین فیلدها (P6 — Canonicalization Gate)
- محاسبهٔ عمومی unit_amount از total/quantity (به دلایل بالا — فقط instant پذیری P6+ از seam)
- tax rate / rounding R2 / تخفیف / markup / هر logic مالی-مالیاتی (WP-5.1 + قواعد Validation)
- تبدیل ارز | product/customer matching | fuzzy/semantic هر چیز | verdict سازگاری totals (Validation)
- تاریخ arithmetic بین فیلدها | محاسبهٔ بین-سندی | تولید/نسبت دادن UNRESOLVED (P5 طبق Register)
- تغییر رفتار Frozen WP-4.1/WP-3.x/WP-2.x/WP-1.1 | وابستگی رو-به-جلو به artifactهای P5/P6

**Inputs:** WP-4.1 FROZEN (verified normalization reads — تنها مسیر ورودی مقادیر) | WP-3.2
(evidence-bearing-ness از طریق verified binding read — فقط read-only) | WP-3.1/WP-2.1/WP-1.1
FROZEN | Decision Register: D-01 (واژگان و ترتیب حل)، D-08 (R2 + tolerance پارامتریک)، D-09
(حکمرانی)، AS-01 (توالی)، AD-02/AD-04 (مرز دامنه + مصرف UNRESOLVED در Validation)

**Dependencies:**
- Upstream: WP-4.1 (✅ FROZEN) | زنجیرهٔ P3 (✅) | هیچ وابستگی به P5/P6 (توالی AS-01)
- Downstream: P5 Validation (مصرف DERIVED و outcomeهای not-derivable برای REVIEW طبق AD-04/D-08) |
  P6 Canonicalization (مصرف سازوکار + پرووننس برای canonical assembly؛ instant کردن derivationهای
  line-scoped اعلانی پس از mapping) — هر دو فقط مصرف‌کنندهٔ خروجی این WP هستند

**Deliverables / AC / Tests / DoD:** با dispatch پیاده‌سازی بعدی (decomposition + AC + evidence)
تعریف می‌شود — این بخش فقط Scope مصوب پیش از coding است.

**Implementation Record (2026-10-06 — T-4.2.1..T-4.2.4، dispatch اجرایی):**

- **Contract (T-4.2.1):** SPEC-WP42-DER v1.0-MVP (`kandoo/specs/WP-4.2-derivation-contract.md`) —
  Scope مصوب ثبت‌شده به قرارداد پیاده‌سازی تبدیل شد: §1 هدف/مرز | §2 مسیر ورودی (verified
  normalization read = تنها مسیر مقدار + healthy binding WP-3.2 fail-closed) | §3 Formula
  Registry اعلانی/versioned/fingerprinted (داده، نه کد؛ ساخت-time validation fail-closed؛
  fingerprint sha256-v1 روی serialization کانونی declaration) | §4 arithmetic دقیق
  (Fraction گویا از decimal string کانونی؛ بدون float؛ ADD/SUB/MUL دقیق؛ DIV فقط terminating —
  غیر دقیق → refusal، هرگز گرد نمی‌شود؛ خروجی = expansion دقیق minimal) | §5 واژگان outcome:
  DERIVED (label ذخیرشونده D-01) | NOT_DERIVABLE/mechanism-DEFERRED (refusal گذرا با reason
  code؛ هیچ مقدار، هیچ persist، هرگز UNRESOLVED ≠) | UNRESOLVED = P5 | §6 مدل داده
  (DerivationRecord + DerivationInputRef — pointer بدون مقدار) | §7 قطعیت | §8 outcomeهای
  exhaustive | §9 persistence INV-D-1:1 (OD-D1..D7) | §10 زنجیرهٔ traceability | §11
  OD-D8..D10 | §12 AC mapping | §13 انتظارات تست (۱۸ محور dispatch).

- **Implementation (T-4.2.2):** `kandoo/src/derivation/` — `model.py` (records/outcomes/
  reason codes؛ DERIVED-only) | `arithmetic.py` (parse کانونی → Fraction دقیق؛ evaluate؛
  non-terminating DIV → NonExactResult؛ to_exact_decimal_string) | `formulas.py`
  (DerivationFormula/FormulaInput/FormulaInputRef/FormulaOp + validation fail-closed +
  canonical_formula_bytes + formula_fingerprint + DerivationFormulaRegistry کلید
  (formula_id, version) + ReferenceDerivationFormulasV1: دقیقاً یک فرمول
  `total.gross = ADD(total.net, tax.amount)` — بدون unit_amount) | `store.py` (SQLite مجزا،
  synchronous=FULL، commit اتمیک record+input refs، INV-D-1:1 + UNIQUE backstop،
  record_fingerprint sha256-v1، CHECK: output_provenance='DERIVED' فقط، بدون UPDATE/DELETE) |
  `service.py` (derive: registry lookup → VOR normalization → VOR binding → INV pre-check →
  singleton slot resolution (NORMALIZED-only؛ 0→input-missing، >1→input-ambiguous) →
  output-present gate → arithmetic دقیق (non-canonical → refusal؛ non-exact → refusal) →
  commit اتمیک | read_derivation: VOR | trace_derivation: walk کامل هر ۵+۱ لینک با verified
  read در یک فراخوانی | enumeration + issue_reports). مستقل از موتور: صفر reference به Engine.

- **Tests (T-4.2.3):** 101 تست در 7 فایل — test_deriv_arithmetic.py (۱۶) | test_deriv_formulas.py
  (۱۹) | test_deriv_service.py (۲۴) | test_deriv_read_path.py (۱۱) | test_deriv_durability.py
  (۸) | test_deriv_trace.py (۸) | test_deriv_boundary.py (۱۵) — پوشش کامل ۱۸ محور الزامی
  dispatch (successful exact derivation؛ formula version determinism؛ no-float با اثبات AST
  صفر literal/call؛ missing/ambiguous/invalid input؛ invalid formula؛ deterministic
  fingerprint؛ VOR؛ tamper matrix؛ idempotent replay؛ distinct version؛ chain کامل؛
  عدم تولید UNRESOLVED با sweep+gate؛ عدم unit_amount؛ عدم cross-document؛ عدم اجرای کد
  دلخواه با AST scan؛ رگرسیون کامل Frozen). Smoke: `run_smoke_derivation.py` — ۸ گام
  (frozen path → normalize → derive 1000.00+80=«1080» → trace کامل → refusals → restart →
  tamper → vocabulary sweep).

- **Numbers (اجرای واقعی 2026-10-06):** P4.2 = 101/101 PASSED | رگرسیون کامل =
  **393/393 PASSED** (54 capture + 72 reconstruction + 74 extraction [38+36 binding] +
  92 normalization + 101 derivation؛ Python 3.12.14 / pytest 9.0.2) | SMOKE OK × ۷
  (۶ Smoke قبلی + run_smoke_derivation.py) | تغییر کد: فقط additive — هیچ فایل Frozen
  P1–P4.1 تغییر نکرده (git status: فقط فایل‌های جدید) | هیچ تست موجودی حذف/تضعیف نشد.

---

## WP-5.1 — R1/R2 Validation Engine (IMPLEMENTED)

```text
WP ID:        WP-5.1
Phase:        P5 — Validation (AS-01 position: P3 → P4.1 → P4.2 → P5.1 → P6 downstream)
Status:       IMPLEMENTED (2026-10-07 — dispatch اجرایی PO/TM: «WP-5.1 — BUILD واقعی،
              نه scope-only») | Scope dispatch به implementation contract تبدیل شد:
              SPEC-WP51-VAL v1.0-MVP (kandoo/specs/WP-5.1-validation-contract.md)
              | Taskهای واقعی: T-5.1.1..T-5.1.4 (همه DONE) | 4/4 AC PASS |
              P5.1 172/172 + رگرسیون کامل 565/565 + SMOKE OK × ۸ (شامل
              run_smoke_validation.py — ۸ گام) | تغییر کد: فقط فایل‌های جدید
              (src/validation/ + run_smoke_validation.py + spec) — صفر تغییر در
              P1–P4.2
Owner Role:   Technical Manager + Backend Dev + QA (acceptance: PO)
Agent Type:   implementation agent (انجام شد — 2026-10-07)
```

**Goal:** ساخت Validation Engine برای اعمال قواعد R1 (ساختاری/سازگاری) و R2
(پارامتریک/rounding طبق D-08) روی خروجی pipeline فعلی — deterministic، explicit،
قابل audit، با حفظ provenance ورودی‌ها، بدون اختراع هیچ مقدار/label جدید، بدون
Canonicalization behavior، و با تولید VERDICT — نه value.

**Scope (اجرا شده):**
1. Rule Registry اعلانی/versioned/fingerprinted (داده، نه کد؛ validation fail-closed
   در registration؛ fingerprint sha256-v1 روی serialization کانونی declaration).
2. R1 — دو rule type: `presence` (وجود مقدار usable) و `exact-consistency`
   (برابری EXACT بین target و expression — همان verdict سازگاری totals که
   SPEC-WP42-DER به Validation سپرده بود).
3. R2 — دو rule type: `tolerated-equality` (مقایسه با tolerance پارامتریک D-08)
   و `rounded-equality` (rounding صریح پارامتریک — تنها محل مجاز non-exact
   intermediate).
4. Rounding دقیق (D-08): float ممنوع (Fraction دقیق)، modes اعلانی
   HALF_UP/HALF_EVEN/FLOOR/CEILING/DOWN، precision صریح در خروجی (فرم fixed)،
   ثبت audit قابل بازتولید (rule_id/rule_version/precision/mode/input/output)
   داخل خود ValidationRecord — خروجی rounding صرفاً audit artifact است و هرگز
   value یا canonical/derived field نمی‌شود.
5. پارامترهای R2 (tolerance/precision/mode) REQUIRED constructor arguments — هیچ
   مقدار ثابتی در engine hardcode نشده (D-08: calibration parameter)؛ بخشی از
   rule fingerprint هستند.
6. Outcome واژگان صریح: `VALID | INVALID | DEFERRED` — دائمی و قابل audit؛
   DEFERRED = تصمیم «عدم امکان تصمیم» (insufficient/ambiguous/non-exact) که خودش
   نتیجهٔ ثبت‌شونده است؛ UNRESOLVED ساختاراً غیرممکن (CHECK سطح SQL) — P5 domain
   layer territory؛ State Machine و REVIEW/REJECT = WP-5.2 (AS-03/AD-04 — این WP
   هیچ invoice state تعریف نمی‌کند)؛ mapping INVALID/DEFERRED → REVIEW فقط به‌عنوان
   یادداشت downstream مستند شد، نه پیاده‌سازی.
7. Input path (فقط مسیرهای verified): NORMALIZED از WP-4.1 VOR؛ DERIVED از WP-4.2
   service (read_derivation/derivations_for_normalization)؛ gate اجباری binding
   سالم WP-3.2 (fail-closed)؛ scope = یک normalization record + derivationهای
   همان record (بدون cross-document/cross-record).
8. Provenance: input POINTER rows (بدون کپی مقدار)؛ trace_validation کامل —
   برای ورودی‌های DERIVED از walk کل-زنجیرهٔ WP-4.2 استفاده می‌شود (provenance
   P4.2 مصرف می‌شود، نه دور زده/نابود)؛ زنجیره: validation → rule/_fp → inputs →
   [WP-4.2 sub-chain] → normalization → extraction → binding → Document/Page/span
   → Capture S1.
9. Persistence طبق الگوی پروژه (OD-V1..OD-V7): SQLite فایل مجزا، synchronous=FULL،
   commit اتمیک record+inputs، INV-V-1:1 روی (normalization_id, rule_id,
   rule_version) با UNIQUE backstop، record_fingerprint sha256-v1 (VOR)، بدون
   UPDATE/DELETE؛ CHECKهای ساختاری: outcome IN (VALID,INVALID,DEFERRED)،
   rule_kind IN (R1,R2)، R1→rounding_applied=0، همه-NULL/همه-NOT-NULL برای فیلدهای
   rounding، سازگاری pointer rows per origin.

**Out of Scope (رعایت شده):** Canonicalization هر نوع (mapping/grouping/matching/
identity) | تولید Sale/Invoice/Digital Invoice | Inventory/KPI mutation | tax rate/
discount/markup/currency/date arithmetic | cross-document validation | حل خودکار
domain UNRESOLVED | پیاده‌سازی State Machine/REVIEW Queue (WP-5.2) | تغییر Frozen
P1–P4.2 | وابستگی رو-به-جلو به P6.

**Reference Registry (MVP):** `ReferenceValidationRulesV1(tolerance, precision, mode)`
— دقیقاً ۴ rule اعلانی: `kandoo-val-total-net-present` v1 (R1 presence) |
`kandoo-val-total-gross-consistency` v1 (R1: total.gross == ADD(total.net,
tax.amount)) | `kandoo-val-total-gross-tolerance` v1 (R2 tolerated) |
`kandoo-val-total-gross-rounded` v1 (R2 rounded) — بدون unit_amount و بدون هیچ
business rule.

**Deliverables / AC / Tests / DoD:** طبق dispatch پیاده‌سازی اجرا شد؛ AC mapping در
SPEC §12؛ شواهد در REG-AR §WP-5.1.

**Implementation Record (2026-10-07 — T-5.1.1..T-5.1.4، dispatch اجرایی):**

- **T-5.1.1 Contract:** SPEC-WP51-VAL v1.0-MVP (§1..§13: purpose/scope، input path،
  rule registry، exact arithmetic + rounding semantics، outcome vocabulary، data
  model، determinism، outcomes، persistence + INV-V-1:1، provenance chain،
  OD-V1..OD-V11، AC mapping، test expectations). قاعدهٔ کلیدی: rounding صریحِ
  rounded-equality تنها context مجاز برای non-exact intermediate؛ در R1 و
  tolerated-equality هر non-exact → DEFERRED (`non-exact-intermediate`) — هرگز
  implicit rounding.
- **T-5.1.2 Implementation:** kandoo/src/validation/{model,rounding,rules,store,
  service,__init__}.py + run_smoke_validation.py — reuse اعلانی arithmetic دقیق
  WP-4.2 (OD-V8: یک grammar کانونی، یک parser) + rounding محلی روی Fraction
  (integer arithmetic خالص؛ ۵ mode؛ فرم fixed با precision صریح؛
  `exact_value_string`: terminating → minimal expansion، non-terminating → "p/q"
  کانونی برای audit input).
- **T-5.1.3 Tests:** 172 تست در 8 فایل — test_val_rules.py (۳۰) |
  test_val_rounding.py (۲۴) | test_val_service.py (۳۷) | test_val_read_path.py
  (۱۴) | test_val_durability.py (۷) | test_val_trace.py (۹) | test_val_boundary.py
  (۳۴) | test_val_e2e.py (۴) — پوشش کامل ۲۰ محور الزامی dispatch. اثبات ساختاری:
  AST scan صفر float literal/float()، صفر eval/exec/compile/__import__، import
  allowlist، صفر engine symbol؛ UNRESOLVED هرگز (gate + sweep)؛ تعیین‌کنندگی
  (reordered-bytes D-03 → همان محتوای validation)؛ tamper matrix (outcome/detail/
  rounding/rule_fp/input pointer → content withheld)؛ replay/idempotency؛
  version separation؛ جدا شدن v1/v2 به‌عنوان record متمایز؛ DERIVED-input chain؛
  بدون Canonicalization/business inference (رفتاری)؛ بقای Frozen layers.
- **T-5.1.4 Verification + governance + delivery:** P5.1 = 172/172 PASSED؛
  رگرسیون کامل = **565/565 PASSED** (54 capture + 72 reconstruction + 74 extraction
  [38+36 binding] + 92 normalization + 101 derivation + 172 validation؛ Python
  3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۸ (شامل run_smoke_validation.py — ۸ گام:
  frozen path → derive → R1 → R2 → trace با WP-4.2 sub-chain → DEFERRED/INVALID
  probes → restart → tamper + vocabulary sweep)؛ registerها و README به‌روز؛
  archive کامل + MANIFEST-SHA256.txt بازتولید و مستقل verify شد.
- **Build → Test → Fix iterations (همه داخل فایل‌های جدید WP-5.1):** (۱) presence
  rule بدون expression در serialization کانونی (None → skip)؛ (۲) exact-consistency
  از شاخهٔ R2 checks عبور می‌کرد (fall-through) → return زودهنگام R1؛ (۳) import
  جامانده canonical_validation_bytes در service؛ (۴) helper تست label→engine_id
  positional bug؛ (۵) DIV غیرمتناهی در rounded-equality نباید DEFERRED می‌شد →
  evaluator محلی با `allow_non_terminating` (سیاست termination = تصمیم caller)؛
  (۶) audit input برای non-terminating: `exact_value_string` ("p/q") به‌جای
  truncate خطرناک to_exact_decimal_string (که فقط برای terminating تعریف شده بود)؛
  (۷) corpusهای تست با «80.004» به‌دلیل ambiguity-guard Frozen WP-4.1 DEFERRED
  می‌شدند → مقادیر با ≥4 رقم اعشار استفاده شد (رفتار Frozen دست نخورد — تست‌ها
  اصلاح شدند).
- **Frozen-layer note (پیش از commit):** `git diff HEAD -- kandoo/src/{capture,
  reconstruction,extraction,normalization,derivation}` = صفر؛ هیچ تست موجودی
  حذف/تضعیف نشد؛ تغییر سطح کد فقط additive.
- **Known pre-existing flake (خارج از WP-5.1، گزارش صادقانه):**
  `extraction/tests/test_binding_durability.py::test_concurrent_bind_appends_are_exact`
  (لایهٔ Frozen P3) تحت stress لوپ تکراری ~۱۰٪ fail می‌شود (race برنامه‌ریزی thread
  روی BEGIN IMMEDIATE) — در اجرای جدا و در اجرای رسمی نهایی PASS؛ این WP هیچ
  ارتباطی به آن ندارد (تغییر سطح صفر در P3؛ تست از commits قبل از WP-5.1) و طبق
  Frozen Layer Protection reopen نشد؛ برای توجه PM/QA ثبت شد.

## WP-5.2 — Validation State Machine + REVIEW Queue (IMPLEMENTED)

```text
WP ID:        WP-5.2
Phase:        P5 — Validation (AS-01 position: P3 → P4.1 → P4.2 → P5.1 → P5.2 → P6 downstream)
Status:       IMPLEMENTED (2026-10-07 — dispatch اجرایی PO/TM: «WP-5.2 — BUILD واقعی،
              نه design-only») | Scope dispatch به implementation contract تبدیل شد:
              SPEC-WP52-VSM v1.0-MVP (kandoo/specs/WP-5.2-validation-domain-contract.md)
              | Taskهای واقعی: T-5.2.1..T-5.2.4 (همه DONE) | 4/4 AC PASS |
              P5.2 125/125 + رگرسیون کامل 690/690 + SMOKE OK × ۹ (شامل
              run_smoke_validation_domain.py — ۸ گام) | تغییر کد: فقط فایل‌های جدید
              (src/validation_domain/ + run_smoke_validation_domain.py + spec) —
              صفر تغییر در P1–P5.1
Owner Role:   Technical Manager + Backend Dev + QA (acceptance: PO)
Agent Type:   implementation agent (انجام شد — 2026-10-07)
```

**Goal:** ساخت Validation State Machine + REVIEW Queue — انتقال outcomeهای
P5.1 به stateهای دامنه‌ای با واژگان عیناً Frozen (AS-03/AD-04/CL-1: واژگان
VERBATIM از Registerهای Frozen و dispatch اجرایی؛ سند فیزیکی Canonical Invoice v1
هنوز commit نشده — MNT-1 — و Decision Register بازنمایی معتبر self-contained آن
است)، ایجاد field-level UNRESOLVED فقط طبق resolution order و معنای D-01، و
مکانیزم REVIEW واقعی/durable — بدون هیچ رفتار Canonicalization و بدون هیچ
semantic resolution.

**Scope (اجرا شده):**
1. State Machine deterministic با priority جدول اعلانی T1..T5 (هر route لنگر
   Frozen دارد: T1 decisive-INVALID → REJECT طبق AD-04؛ T2 mismatch-beyond-
   tolerance/mismatch-after-rounding → REVIEW طبق D-08؛ T3 field-UNRESOLVED →
   REVIEW طبق D-01/AD-04؛ T4 rule-DEFERRED → REVIEW طبق راهنمای SPEC-WP51-VAL §5
   و الگوی D-03؛ T5 → VALID/CLEAR)؛ ترتیب ثابت اولویت به‌عنوان delegated detail
   اعلان شد (OD-S8) — هیچ state اضافه/تغییرنام/ترکیب.
2. واژگان دقیق: DOMAIN_STATE = VALID | INVALID | DEFERRED | UNRESOLVED (عیناً
   dispatch) + DISPOSITION = REVIEW | REJECT (AD-04) + CLEAR (مارکر صریحِ
   empty-routing در سطح mechanism — نه state جدید Canonical Invoice).
3. UNRESOLVED field-level فقط این‌جا — طبق D-01 order (EXTRACTED → DERIVED →
   UNRESOLVED) و با معنای دست‌نخورده: reason ثابت d01-no-valid-method، status،
   provenance، قابل trace؛ ambiguous هرگز UNRESOLVED نمی‌شود (روش وجود دارد —
   association = Canonicalization Gate؛ OD-S10)؛ هیچ auto-resolve.
4. REVIEW Queue واقعی: durable (SQLite الگوی پروژه)، idempotent (INV-R-1:1)،
   duplicate کنترل‌شده، reason/provenance-carrying، VOR fingerprints، lifecycle
   append-only با event hash-chain (ANNOTATE | CLOSE — CLOSE terminal با
   partial-UNIQUE backstop)، status همیشه از history مشتق می‌شود — هیچ
   UPDATE/DELETE؛ queue فقط uncertainty نگه می‌دارد، semantic resolver نیست.
5. Persistence طبق الگوی پروژه (OD-S1..OD-S7): SQLite فایل مجزا، synchronous=FULL،
   commit اتمیک (state record + validation refs + field projections + review item)،
   INV-S-1:1 روی (normalization_id, ruleset_fingerprint)، record/item/event
   fingerprints با sha256-v1 (S1 capability)، CHECK gates (شامل state↔disposition
   consistency و شکل projection rows)، بدون UPDATE/DELETE (اثبات AST).
6. Completeness gate: keys اعلام‌شده باید دقیقاً برابر records ارزیابی‌شدهٔ P5.1
   باشند (هم missing و هم extra رد می‌شوند — state هرگز از facts جزئی project
   نمی‌شود)؛ declaration drift (registry fingerprint ≠ record fingerprint) =
   integrity failure؛ همه مسیرها فقط verified reads (P5.1 VOR + WP-4.1 VOR).
7. Provenance: pointer rows (بدون کپی مقدار)؛ trace_domain_state هر validation
   ref را از طریق trace_validation کل-زنجیرهٔ WP-5.1 (شامل sub-chain WP-4.2)
   مجدداً verify می‌کند و tail تا Capture S1 را walk می‌کند؛ هیچ زنجیره‌ای قطع
   یا جایگزین نمی‌شود.

**Out of Scope (رعایت شده):** اجرای validation/derivation/normalization | هر نوع
Canonicalization (mapping/grouping/matching/identity) | semantic resolution
خودکار | tax/currency/date | Sale/Invoice/Digital Invoice creation/issuance |
Inventory/KPI mutation | Canonicalization Gate logic (P6) | حل خودکار REVIEW |
تغییر Frozen P1–P5.1 | وابستگی رو-به-جلو به P6.

**Deliverables / AC / Tests / DoD:** طبق dispatch پیاده‌سازی اجرا شد؛ AC mapping
در SPEC §12؛ شواهد در REG-AR §WP-5.2.

**Implementation Record (2026-10-07 — T-5.2.1..T-5.2.4، dispatch اجرایی):**

- **T-5.2.1 Contract:** SPEC-WP52-VSM v1.0-MVP (§1..§13: purpose/scope، input
  path، state machine vocabulary + transition table + dispositions، UNRESOLVED
  creation D-01، REVIEW queue، data model، determinism، outcomes، persistence +
  invariants، provenance chain، OD-S1..OD-S14، AC mapping، test expectations).
  تصمیم کلیدی واژگان: dispatch اجرایی تمایز عیناً VALID/INVALID/DEFERRED/
  UNRESOLVED را الزامی کرده و AD-04 مدل خروجی REVIEW/REJECT را Frozen می‌کند —
  ترتیب اولویت T1..T5 به‌عنوان delegated detail اعلان شد (D-09/OD-S8)؛ STOP
  لازم نشد چون هیچ contradiction واقعی با Frozen وجود نداشت.
- **T-5.2.2 Implementation:** kandoo/src/validation_domain/{model,machine,store,
  service,__init__}.py + run_smoke_validation_domain.py — machine.py خالص
  (بدون I/O/clock/randomness؛ project_fields + derive_state + ruleset
  fingerprint)؛ store.py با ۵ جدول (domain_state_records /
  domain_state_validations / domain_state_fields / review_queue_items /
  review_queue_events)؛ service.py با project_domain_state (۱۰ گام fail-closed) +
  read VOR × ۲ + append_review_event (terminality + parent-integrity gate) +
  trace_domain_state (sub-walks WP-5.1).
- **T-5.2.3 Tests:** 8 فایل / 125 تست — test_vsm_state.py (۲۲) |
  test_vsm_unresolved.py (۸) | test_vsm_review.py (۱۳) | test_vsm_service.py (۹) |
  test_vsm_read_path.py (۱۸) | test_vsm_durability.py (۱۳) | test_vsm_trace.py (۹) |
  test_vsm_boundary.py (۲۷) | test_vsm_e2e.py (۳) — پوشش کامل ۲۰ محور الزامی
  dispatch. اثبات ساختاری: AST scan صفر float/eval/exec/compile/__import__؛
  import allowlist؛ صفر symbol ممنوع (canonicalinvoice/sale/digitalinvoice/
  inventory/match...)؛ صفر UPDATE/DELETE SQL؛ vocabulary sweep روی DB (شامل
  امتناع CHECK در برابر tamper مستقیم SQL)؛ refusals ناقص/اضافه/خالی/تکراری.
- **Build → Test → Fix iterations (همه داخل فایل‌های جدید WP-5.2):** (۱) schema:
  double PRIMARY KEY در review_queue_events → event_id UNIQUE؛ (۲) ruleset
  fingerprint باید ruleset identity (id+version) را هم پوشش دهد تا
  version-separation کار کند؛ (۳) state_detail T4 باید detail متن P5.1 را
  verbatim relay کند (اشارهٔ Canonicalization Gate)؛ (۴) unresolved detail باید
  upstream statuses را relay کند (unresolved_notes)؛ (۵) append_review_event
  fail-closed روی parent projection خراب (gate جدید — در SPEC §5 مستند شد)؛ (۶)
  اصلاحات تست: D-03 (باز-ingest بایت یکسان ممنوع) → PAGE_ALT_OK؛ probes باید در
  registry pre-register شوند؛ completeness gate درست است — تست‌ها اصلاح شدند.
- **T-5.2.4 Verification + governance + delivery:** P5.2 = 125/125 PASSED؛
  رگرسیون کامل = **690/690 PASSED** (54 capture + 72 reconstruction + 74
  extraction [38+36 binding] + 92 normalization + 101 derivation + 172
  validation + 125 validation_domain؛ Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK
  × ۹ (شامل run_smoke_validation_domain.py — ۸ گام: VALID/CLEAR + trace →
  UNRESOLVED + queue → replay → lifecycle → determinism → restart → tamper →
  survival sweep)؛ registerها و README به‌روز؛ archive کامل + MANIFEST-SHA256.txt
  بازتولید و مستقل verify شد.
- **Frozen-layer protection verified:** git diff روی P1–P5.1 = صفر؛ تغییر سطح کد
  فقط additive (spec + src/validation_domain/ + smoke + registers/README)؛ هیچ
  تست موجودی حذف/تضعیف نشد.
- **Known pre-existing flake (خارج از WP-5.2، گزارش صادقانه):** همان flake
  concurrency ثبت‌شدهٔ P3
  (`extraction/tests/test_binding_durability.py::test_concurrent_bind_appends_are_exact`)
  در اجرای رسمی نهایی این WP نیز PASS شد؛ طبق dispatch اصلاح نشد و scope منحرف
  نشد.

---

## WP-6.1 — Canonicalization Gate (IMPLEMENTED)

```text
WP ID:        WP-6.1
Phase:        P6 — Canonicalization (AS-01 position: P3 → P4.1 → P4.2 → P5.1 →
              P5.2 → P6.1؛ مرز واقعی ورود داده به Canonical Invoice domain)
Status:       IMPLEMENTED (2026-10-07 — dispatch اجرایی PO/TM: «WP-6.1 — BUILD
              واقعی، نه صرفاً design/spec») | Scope dispatch به implementation
              contract تبدیل شد: SPEC-WP61-CANGATE v1.0-MVP
              (kandoo/specs/WP-6.1-canonicalization-gate-contract.md)
              | Taskهای واقعی: T-6.1.1..T-6.1.4 (همه DONE) | 4/4 AC PASS |
              P6.1 112/112 + رگرسیون کامل 802/802 + SMOKE OK × ۱۰ (شامل
              run_smoke_canonicalization.py — ۸ گام) | تغییر کد: فقط فایل‌های
              جدید (src/canonicalization/ + run_smoke_canonicalization.py +
              spec) — صفر تغییر در P1–P5.2
Owner Role:   Technical Manager + Backend Dev + QA (acceptance: PO)
Agent Type:   implementation agent (انجام شد — 2026-10-07)
```

**Goal:** ساخت Canonicalization Gate — اولین مرز واقعی ورود داده به Canonical
Invoice domain. Gate یک validation-domain result تأییدشدهٔ P5.2 را مصرف می‌کند،
زنجیرهٔ provenance کامل upstream را مجدداً verify می‌کند (از طریق trace_domain_state
— مصرف، نه bypass)، External Document Identity را دقیقاً طبق D-02 حل می‌کند،
جدول تصمیم idempotency/duplicate طبق D-03 را اعمال می‌کند، و فقط وقتی همهٔ
شروط Frozen برقرار است Canonical Invoice admission record را می‌سازد؛ در
غیر این صورت fail-closed به واژگان routing Frozen می‌رود. تمایز معماری dispatch
حفظ شد: Validation ≠ Canonicalization — VALID/CLEAR لازم است اما کافی نیست.

**Scope (اجرا شده):**
1. **Decision table deterministic با اولویت اعلانی G1..G6** (هر route لنگر
   Frozen دارد): G1 disposition REJECT → REJECTED/upstream-decisive-invalid
   (AD-04/OD-S9)؛ G2 disposition REVIEW → REVIEW با relay عیناً state_reason
   P5.2 (D-08/D-01/T4 — CL-1 بدون پارافریز) با ارجاع upstream_review_id و بدون
   duplicate آیتم (OD-G9)؛ G3 VALID/CLEAR + CAPTURE_SCOPED → REVIEW با سه reason
   اعلانی incomplete/conflicting/undetermined (D-03 ناقص/متعارض/ambiguity)؛
   G4 replay سطح capture (S1) → ALREADY_CANONICALIZED/d02-capture-idempotent-
   replay (D-02: S1 کلید idempotency سطح Capture)؛ G5 S2 کامل+دقیق از capture
   متفاوت → REJECTED/d03-definite-document-duplicate (قطعی، نه uncertainty)؛
   G6 → ACCEPTED/all-frozen-conditions-met. G0 (replay تصمیم موجود) قبل از همه
   با INV-D-1:1. واژگان تصمیم = عیناً paths dispatch §14: ACCEPTED | REJECTED |
   REVIEW | ALREADY_CANONICALIZED. UNRESOLVED هرگز در این لایه ساخته نمی‌شود
   (D-01: فقط P5.2) — ورودی‌های unresolved مسیر G2.
2. **Identity Resolution دقیقاً D-02/D-03** (identity.py خالص): فقط مسیر
   deterministic دوم D-02 — triad شماره فاکتور + تاریخ + جمع «کاملاً استخراج و
   تأیید شده» (OD-G3: دقیقاً یک ردیف NORMALIZED قابل‌استفاده per role در read
   تأییدشدهٔ WP-4.1 + state P5.2 VALID/CLEAR)؛ در غیر این صورت صراحتاً
   CAPTURE_SCOPED (D-02). مسیر adapter-document-id RESERVED اعلان شد (OD-G5 —
   هیچ producer در pipeline پیاده‌شده وجود ندارد؛ D-04 post-freeze). binding
   اعلانی سه‌نقشی (roles Frozen) با validation سخت (partial/unknown/duplicate/
   non-string → refusal). identity_fingerprint = sha256-v1 روی
   (declared_origin + سه مقدار canonical به ترتیب role) — معادل S2 برای S1؛
   مقایسه duplicate فقط exact-equality fingerprint — هیچ fuzzy/heuristic/AI.
   multiple candidates → DO NOT AUTO-RESOLVE (dispatch §6).
3. **Canonical Invoice admission record** (SPEC §6): source-independent (D-04 —
   فقط origin enum + pointers)، origin عیناً از dispatch §7 (KANDOO_SALE |
   HOLOO_CAPTURE | OTHER_POS_CAPTURE — CHECK gate؛ KANDOO_SALE روی ورودی
   P5.2-sourced refuse می‌شود — OD-G6/OD-G7 چون native flow بدون capture
   pipeline است — AS-02)، deterministic fingerprint، immutable (بدون
   UPDATE/DELETE — AST-proven)، INV-CI-1:1 با تصمیم ACCEPTED در همان تراکنش؛
   tuple S2 به‌صورت fingerprint + سه pointer row (بدون کپی مقدار) ذخیره
   می‌شود؛ assembly کامل field/line و issuance رسمی invoice_id = WP-6.2
   (OD-G8).
4. **Gate REVIEW Queue** (الگوی P5.2 §5): جدول‌های مجزا در store P6.1؛ INV-GR-1:1
   (هر تصمیم REVIEW دقیقاً یک آیتم؛ بقیه هیچ)؛ append-only hash-chained events
   (ANNOTATE | CLOSE terminal با partial-UNIQUE)؛ status مشتق از history؛ هر
   append fail-closed روی verified read والدین (تصمیم + state P5.2).
5. **Persistence الگوی پروژه** (OD-C1..OD-C7): SQLite فایل مجزا
   (canonicalization-gate.db)، synchronous=FULL، commit اتمیک (تصمیم + invoice
   + pointers + review item)، backstopهای UNIQUE (decision per state، invoice
   per decision، capture_s1، identity_fingerprint، review item per decision،
   single CLOSE)، fingerprints sha256-v1 روی canonical bytes، CHECK gates
   (decision/origin/identity_class/ACCEPTED↔invoice/reason codes)، VOR روی همه
   reads، restart-safe.
6. **Provenance (SPEC §9):** trace_canonical_invoice — canonical invoice →
   gate decision → trace_domain_state (کل-زنجیرهٔ P5.2 شامل sub-walks WP-5.1 و
   P4.2 تا Capture S1) → re-join pointer rows روی read تأییدشده؛ هیچ broken
   link silently پذیرفته نمی‌شود (V2 قبل از هر تصمیم).
7. **مرزها (رعایت شده — dispatch §11):** هیچ Inventory/Sale/KPI/Customer
   mutation؛ هیچ product fuzzy/semantic matching (هویت این WP = DOCUMENT identity
   طبق D-02/D-03)؛ هیچ tax/currency/accounting interpretation؛ هیچ AI identity
   resolution؛ هیچ OCR؛ هیچ تغییر P1–P5.2 یا Frozen architecture؛ هیچ اجرای
   upstream (spy-proven).

**Out of Scope (رعایت شده):** Canonical Assembly + invoice_id issuance رسمی
(WP-6.2) | حل خودکار REVIEW | duplicate flows (P7) | product/customer matching
(P8/P9) | تغییر Frozen P1–P5.2.

**Deliverables / AC / Tests / DoD:** طبق dispatch پیاده‌سازی اجرا شد؛ AC mapping
در SPEC §11؛ شواهد در REG-AR §WP-6.1.

**Implementation Record (2026-10-07 — T-6.1.1..T-6.1.4، dispatch اجرایی):**

- **T-6.1.1 Contract:** SPEC-WP61-CANGATE v1.0-MVP (§1..§12: purpose/scope،
  input path، request contract، decision table G0..G6، identity resolution،
  admission record، gate review queue، persistence OD-C1..OD-C7، provenance
  chain، OD-G1..OD-G10، AC mapping، test expectations). منبع واژگان: سند فیزیکی
  Canonical Invoice v1 در baseline موجود نیست (MNT-1 — قبلاً ثبت شده و به‌تنهایی
  دلیل STOP نیست) — origins عیناً از dispatch §7 و decision paths عیناً از
  dispatch §14؛ D-02/D-03 مکانیک identity/idempotency را Frozen می‌کنند؛ STOP
  لازم نشد چون هیچ contradiction واقعی با Frozen وجود نداشت.
- **T-6.1.2 Implementation:** kandoo/src/canonicalization/{model,identity,gate,
  store,service,__init__}.py + run_smoke_canonicalization.py — identity.py و
  gate.py خالص (بدون I/O/clock/randomness)؛ store.py با ۵ جدول (gate_decisions /
  canonical_invoices / canonical_identity_pointers / gate_review_items /
  gate_review_events)؛ service.py با canonicalize (V1 verified read → V2
  whole-chain trace → V3 origin → V4 binding → G0 replay → G1..G6 → commit
  اتمیک) + read VOR ×۳ + append_gate_review_event (terminality + parent-
  integrity gate) + trace_canonical_invoice.
- **T-6.1.3 Tests:** 9 فایل / 112 تست — test_cg_decision.py (۱۷) |
  test_cg_identity.py (۱۸) | test_cg_invoice.py (۱۵) | test_cg_provenance.py (۱۰) |
  test_cg_idempotency.py (۹) | test_cg_boundary.py (۳۴) | test_cg_service.py (۹)
  — پوشش کامل ۲۵ محور الزامی dispatch (شامل: پذیرش VALID/CLEAR، رد INVALID،
  DEFERRED/UNRESOLVED handling، exact-match/no-match/multi-candidate، منع fuzzy،
  provenance/broken chain/P4.2، tamper، duplicate/replay، atomicity، restart،
  origin، immutability، deterministic fingerprint، منع downstream mutation،
  frozen-layer protection، malformed input، boundary، e2e، بدون اجرای تصادفی
  P5.2 (spy)، AST checks، و «هیچ canonicalization بدون Gate»).
  اثبات ساختاری: AST صفر float/eval/exec/compile/__import__؛ import allowlist؛
  صفر symbol ممنوع (fuzzy/similarity/match_product/create_sale/OCR/...)؛ صفر
  UPDATE/DELETE SQL در store؛ vocabulary sweep روی DB؛ row-count stability
  لایه‌های Frozen در برابر ترافیک gate.
- **Build → Test → Fix iterations (همه داخل فایل‌های جدید WP-6.1):** (۱) binding
  نقش INVOICE_TOTAL به total.gross (DERIVED) ← total.net — D-02 «کاملاً استخراج»
  فقط EXTRACTED را می‌گیرد و read تأییدشدهٔ WP-4.1 فقط مسیر value-level مجاز است؛
  (۲) تخصیص frozen dataclass در service → بازساخت؛ (۳) V2 VerificationUnavailable
  باید با پیشوند provenance گزارش شود (auditability)؛ (۴) تست byte-identity روی
  لایه‌های Frozen با write-on-read خودِ آن لایه‌ها (مثل F-08 در P1) تضاد داشت →
  اثبات به row-count stability + spy تغییر یافت (صادقانه‌تر و layer-agnostic)؛
  (۵) صفحات تست duplicate باید مقدار S2 یکسان با بایت متفاوت داشته باشند
  (PAGE_IDENTITY_TWIN/TWIN3) — محدودیت S1-level dedup در Capture.
- **T-6.1.4 Verification + governance + delivery:** P6.1 = 112/112 PASSED؛
  رگرسیون کامل = **802/802 PASSED** (54 capture + 72 reconstruction + 74
  extraction + 92 normalization + 101 derivation + 172 validation + 125
  validation_domain + 112 canonicalization؛ Python 3.12.14 / pytest 9.0.2)؛
  SMOKE OK × ۱۰ (همه ۹ قبلی + run_smoke_canonicalization.py — ۸ گام: ACCEPTED +
  trace → conflicting REVIEW → definite duplicate → double idempotency →
  lifecycle → restart → tamper → survival sweep)؛ registerها و README به‌روز؛
  archive کامل + MANIFEST-SHA256.txt بازتولید و مستقل verify شد.
- **Frozen-layer protection verified:** git diff روی P1–P5.2 = صفر؛ تغییر سطح کد
  فقط additive (spec + src/canonicalization/ + smoke + registers/README)؛ flake
  ثبت‌شدهٔ P3 در اجرای رسمی PASS (5/5 تکرار مستقل) و طبق dispatch دست‌نخورده ماند.

---

## WP-6.2 — Canonical Assembly + invoice_id Issuance

```text
Status:       IMPLEMENTED (2026-10-08 — dispatch اجرایی PO/TM «BUILD واقعی»)
Spec:         kandoo/specs/WP-6.2-canonical-assembly-contract.md (SPEC-WP62-CANASM v1.0-MVP)
Code:         kandoo/src/canonical_assembly/ (model/assembly/store/service/__init__.py)
Smoke:        kandoo/src/run_smoke_canonical_assembly.py
Tests:        kandoo/src/canonical_assembly/tests/ (100/100 PASSED)
```

**Scope of record (dispatch 2026-10-08):** مصرف Admission/ACCEPTED output از
P6.1 و ساخت Canonical Invoice واقعی: canonical field assembly، canonical line
assembly، canonical identity، رسمی‌سازی invoice_id، immutable persistence،
deterministic/idempotent issuance، complete provenance.

**In Scope (پیاده‌سازی شد):**

1. **نردبان verification ورودی fail-closed** (SPEC §4 A1..A6): A1 verified
   read admission از P6.1 (تنها مسیر مجاز — consumed، هرگز bypass نمی‌شود)؛
   A2 trace_canonical_invoice از P6.1 (whole-chain تا Capture S1)؛ A3 فقط
   تصمیم ACCEPTED admission دارد (REVIEW/REJECTED/ALREADY_CANONICALIZED هیچ‌
   گاه invoice نمی‌سازند — refusal صریح بدون residue)؛ A4 اعتبارسنجی declared
   line binding؛ A5 verified reads مقداری WP-4.1/WP-4.2؛ A6 کنسistency انکر
   هویت (بازمحاسبه serialization OD-G4 از P6.1 و مقایسه با identity_fingerprint
   admission — همان فرمول، فرمول جدید نه).
2. **Canonical field assembly** (SPEC §5): inventory کامل — هر ردیف NORMALIZED
   قابل‌استفاده (به‌ترتیب field_seq) + هر خروجی DERIVED تأییدشدهٔ P4.2 (ترتیب
   deterministic)؛ مقادیر VERBATIM (بدون rename، بدون default، بدون coercion)؛
   provenance طبق D-01 عیناً EXTRACTED | DERIVED (UNRESOLVED اینجا ساخته
   نمی‌شود)؛ هر field با pointer مجدد-به‌هم‌پیوند-پذیر. Header anchors = سه نقش
   Frozen D-02 (INVOICE_NUMBER | INVOICE_DATE | INVOICE_TOTAL). customer
   reference صراحتاً ABSENT با کد پایدار (OD-A9 — D-06: auto-create ممنوع،
   linking = WP-9.1).
3. **Line assembly declared-only** (SPEC §6 / OD-A4): ساختار خط ورودی DECLARED
   است (line_key int → LINE_QUANTITY | LINE_UNIT_PRICE | LINE_TOTAL →
   source_field_name) — assembler هیچ‌گاه خط کشف/گروه‌بندی نمی‌کند؛ ≥2 ردیف
   قابل‌استفاده → refuse کل درخواست (هیچ auto-resolution)؛ 0 ردیف → نقش صراحتاً
   ABSENT؛ خط با هر سه نقش غایب → REJECT صریح (empty-line-rejected، هرگز silent
   drop)؛ ترتیب خطوط صعودی declared key (explicit sort — هرگز dict/set iteration)؛
   **هیچ حسابگری بین fieldها** (OD-A7 — totals semantics در P5.1 مانده؛
   consistency = byte-identity با verified sources + A6).
4. **invoice_id Issuance** (SPEC §7 / OD-A1): invoice_id = canonical_invoice_id
   صادرهٔ Kandoo در P6.1 — VERBATIM مصرف می‌شود (D-02 هویت سوم؛ OD-G8 صراحتاً
   issuance رسمی را به همین WP سپرده)؛ در این لایه هیچ UUID/random ساخته
   نمی‌شود (AST-proven) و فرمول هویت متفاوتی ساخته نمی‌شود؛ unique/stable/
   collision-safe (PK + UNIQUE backstops)؛ idempotent: replay همان admission +
   همان declaration → AssemblyAlreadyAssembled (رکورد موجود verbatim)؛ همان
   admission با declaration متفاوت → refusal صریح assembly-declaration-conflict
   (OD-A8 — نه invoice دوم، نه reshape خاموش).
5. **Persistence الگوی پروژه** (SPEC §8 OD-C1..OD-C7): SQLite فایل مجزا
   (canonical-assembly.db)؛ synchronous=FULL؛ BEGIN IMMEDIATE/COMMIT صریح؛
   commit اتمیک invoice + anchors + fields + lines + line_fields (بدون حالت
   نیمه‌ساخته)؛ INV-AI-1:1 (حداکثر یک invoice صادره per admission — چک
   in-transaction + UNIQUE backstop)؛ UNIQUE(identity_fingerprint)؛ CHECK gates
   (origin، provenance↔pointer، present↔value، شمارنده‌ها)؛ sha256-v1
   fingerprints (record + declaration) با VOR در هر read؛ بدون UPDATE/DELETE
   (AST-proven)؛ restart-safe؛ tamper-evident.
6. **Provenance/trace** (SPEC §9): trace_assembled_invoice همهٔ لینک‌ها را در
   یک فراخوانی re-verify می‌کند: issued invoice (VOR کامل محتوا) → admission +
   trace_canonical_invoice (consumed، هرگز bypass) → P5.2 whole-chain تا
   Capture S1 → re-join هر canonical field/line با byte-identity. شکست هر
   لینک → fail-closed صریح.

**Out of Scope (رعایت شده):** هر تصمیم canonicalization مجدد | inventory/KPI/
accounting/tax/Holoo mutation | customer auto-create | product fuzzy/semantic
matching | OCR | تغییر هر لایهٔ Frozen P1–P6.1 | Digital Invoice issuance
(WP-10.x) | lifecycle صف REVIEW (مالکیت P6.1).

**Implementation Record (2026-10-08 — T-6.2.1..T-6.2.4، dispatch اجرایی):**

- **T-6.2.1 Contract:** SPEC-WP62-CANASM v1.0-MVP (§1..§12: purpose/scope،
  input path، request contract، verification ladder A1..A6، field/line
  assembly، invoice_id issuance، persistence OD-C1..C7، provenance chain،
  OD-A1..A10، AC mapping، test expectations). AS-04 رعایت شد: فقط واژگان
  موجود در منابع Frozen quote شد (نقش‌های D-02، origin enum، provenance D-01،
  حوزه‌های محتوایی dispatch §5)؛ ساختار خط = DECLARED input (الگوی
  identity_field_binding در P6.1)؛ سند فیزیکی baseline هنوز غایب (MNT-1 —
  pre-registered، دلیل STOP نیست)؛ هیچ contradiction واقعی با Frozen نبود.
- **T-6.2.2 Implementation:** kandoo/src/canonical_assembly/{model,assembly,
  store,service,__init__}.py + run_smoke_canonical_assembly.py — assembly.py
  خالص (بدون I/O/clock/randomness؛ validate_line_binding/declaration_bytes/
  resolve_declared_field/assemble_fields/assemble_header_anchors/
  identity_anchor_payload/assemble_lines)؛ store.py با ۵ جدول
  (canonical_invoices / canonical_header_anchors / canonical_fields /
  canonical_lines / canonical_line_fields)؛ service.py با assemble (A1..A6 →
  replay gate → assembly → commit اتمیک) + read VOR + trace.
- **T-6.2.3 Tests:** 7 فایل / 100 تست — test_ca_assembly.py (۲۵: declaration
  mechanics، fingerprint پایدار، resolution، inventory، anchors، OD-G4 quote،
  خطوط) | test_ca_service.py (۱۷: e2e، non-ACCEPTED → هیچ invoice، replay/
  drift، spy مصرف P6.1، منع اجرای upstream، byte-identity مقادیر، ambiguity،
  origin ×۲، determinism محتوا، A6) | test_ca_invoice.py (۲۰: invoice_id
  verbatim/unique/replay، source-independence، exact assembly، انکرها، D-06
  absent، immutability، tamper matrix ×۵، backstopهای SQL ×۴) |
  test_ca_lines.py (۹: دو خط، ترتیب deterministic، dict-order استقلال، absent
  جزئی، empty-line rejection، duplicate target، bind به identity field،
  zero-line) | test_ca_provenance.py (۹: trace تا S1، broken chain
  (normalization/binding)، tamper detect، re-join DERIVED) |
  test_ca_durability.py (۷: atomicity zero-residue ×۲، restart ×۲، issuance
  مکرر، race backstop، UNIQUE مستقیم SQL) | test_ca_boundary.py (۱۳: AST بدون
  UPDATE/DELETE/DROP، بدون uuid/random/secrets/float/eval/exec، import
  allowlist، صفر identifier ممنوع (fuzzy/semantic/ocr/inventory/...)، صفر
  ارجاع مستقیم به جدول‌های upstream، واژگان verbatim، ساختاری consumed-not-
  bypassed، row-count stability لایه‌های Frozen، surface تمیز) — پوشش کامل ۲۷
  محور الزامی dispatch §13.
- **Build → Test → Fix iterations (همه داخل فایل‌های جدید WP-6.2):** (۱)
  assemble_fields باید invoice_id را از ابتدا بپذیرد (رکوردهای "" → 0 ردیف
  در read)؛ (۲) assemble_lines نیازمند normalization_id صریح برای pointerهای
  خط؛ (۳) تست duplicate line keys از طریق dict literal ساختنی نیست (Python
  کلیدها را collapse می‌کند) → تست bool-key (True == 1) جایگزین شد؛ (۴) تست
  dict-order استقلال نباید مستقیماً DELETE کند → مقایسه replay با dict
  به‌هم‌ریخته (fingerprint declaration key-sorted است)؛ (۵) tamper artifact
  خام capture در walk دیده نمی‌شود (chain روی رکوردهای reconstruction لنگر
  است) → tamper رکورد WP-3.2 (همان الگوی محترمانهٔ suite در P6.1)؛ (۶) sweep
  identifier ممنوع باید AST باشد نه متن خام (docstringها مرزها را DECLARE
  می‌کنند).
- **T-6.2.4 Verification + governance + delivery:** P6.2 dedicated = **100/100
  PASSED**؛ رگرسیون کامل = **902/902 PASSED** (54 capture + 72 reconstruction +
  74 extraction + 92 normalization + 101 derivation + 172 validation + 125
  validation_domain + 112 canonicalization + 100 canonical_assembly؛ Python
  3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۱۱ (همه ۱۰ قبلی +
  run_smoke_canonical_assembly.py — ۶ گام: ACCEPTED→assembly+trace → REVIEW→
  هیچ invoice → replay+drift → restart → tamper → survival sweep)؛
  Frozen P1–P6.1 untouched (git diff = صفر)؛ registerها (REG-WPR/REG-TR/
  REG-AR) + src/README.md + worklog به‌روز؛ archive کامل + MANIFEST-SHA256.txt
  بازتولید و مستقل verify شد.
- **Frozen-layer protection verified:** git diff روی P1–P6.1 = صفر؛ تغییر سطح
  کد فقط additive (spec + src/canonical_assembly/ + smoke + registers/README)؛
  flake ثبت‌شدهٔ P3 در اجرای رسمی PASS و طبق dispatch دست‌نخورده ماند.

---

## WP-7.1 — Identity Resolution (S1 / S2 / CAPTURE_SCOPED)

```text
Status:       IMPLEMENTED (2026-10-08 — dispatch اجرایی PO/TM «BUILD واقعی»)
Spec:         kandoo/specs/WP-7.1-identity-resolution-contract.md (SPEC-WP71-IDRES v1.0-MVP)
Code:         kandoo/src/identity_resolution/ (model/resolver/store/service/__init__.py)
Smoke:        kandoo/src/run_smoke_identity_resolution.py
Tests:        kandoo/src/identity_resolution/tests/ (108/108 PASSED)
```

**Scope of record (dispatch 2026-10-08):** پیاده‌سازی Identity Resolution با
مدل هویت Frozen (S1 / S2 / CAPTURE_SCOPED) — تشخیص replay سطح Capture، حل
exact سند طبق D-02، مدیریت duplicate قطعی طبق D-03، persistence مستقل
immutable، حفظ provenance کامل، تقویت زیرساخت هویتی موجود P6.1 بدون تغییر
رفتار Gate.

**In Scope (پیاده‌سازی شد):**

1. **نردبان verification ورودی fail-closed** (SPEC §4): V1 verified read
   domain state از P5.2 → V2 trace_domain_state کل-زنجیره تا Capture S1
   (consumed، هرگز bypass نمی‌شود؛ broken provenance → FAIL CLOSED با zero
   residue) → V3 اعتبارسنجی origin (واژگان Frozen؛ KANDOO_SALE روی ورودی
   P5.2-sourced refuse — AS-02) → V4 اعتبارسنجی binding (سخت، بدون repair).
2. **حالت‌های حل هویت صریح** (SPEC §5): **S1** = capture_s1 روی هر رکورد
   (کلید idempotency سطح Capture؛ UNIQUE — هر artifact دقیقاً یک resolution
   دائمی) + رفتار replay recognition (R0 → IdentityReplay verbatim، read-only،
   پس از VOR روی رکورد موجود — replay از ردیف دستکاری‌شده هرگز)؛ **S2** =
   هویت سند زمانی که triad Frozen «کاملاً استخراج و تأیید شده» باشد — فقط از
   طریق primitive فروزن P6.1 (`canonicalization.identity.resolve_identity`)
   مصرف‌شده VERBATIM (OD-IR-G — بدون فرمول جدید، بدون fork؛ fingerprint
   sha256-v1 روی declared_origin + سه مقدار canonical) + source
   S2_EXTRACTED_VERIFIED + سه ردیف evidence با pointer قابل re-join؛
   **CAPTURE_SCOPED** = خروجی صریح بی‌S2 با reason پایدار (سه کد D-03 عیناً
   از P6.1 + `s2-not-attempted-state-not-valid` برای state غیر VALID/CLEAR
   بدون هیچ مصرف مقداری — OD-IR-C). وضعیت‌های سومی ابداع نشد؛ UNRESOLVED
   اینجا ساخته نمی‌شود (D-01)؛ ≥2 کاندید → هرگز auto-select، evidence حفظ
   (dispatch §8).
3. **مدیریت duplicate قطعی D-03** (SPEC §6): مقایسه فقط exact-equality
   fingerprint بین captureهای متفاوت (origin داخل fingerprint است — برخورد
   بین-origin ذاتاً ناممکن)؛ resolution جدید capture دوم + observation
   append-only ارجاع‌دهنده به original (انتخاب deterministic earliest
   created_at/resolution_id — OD-IR-E) در همان commit اتمیک؛ «یک هویت سند»
   فکت دائمی و auditable می‌شود، نه merge و نه حذف.
4. **Replay discipline** (OD-IR-F): تطبیق declaration = همان declared_origin
   + همان binding_declaration_fingerprint (sha256-v1 serialization
   key-sorted — مستقل از ترتیب dict؛ '' = بدون declaration)؛ replay با
   declaration متفاوت → refusal صریح `replay-declaration-drift` — بدون هویت
   دوم، بدون reshape خاموش.
5. **Persistence الگوی پروژه** (SPEC §7/§8 OD-IR1..IR7): SQLite فایل مجزا
   (identity-resolution.db)؛ synchronous=FULL؛ BEGIN IMMEDIATE/COMMIT صریح؛
   commit اتمیک resolution + role rows + observation؛ INV-IR-S1:1
   (UNIQUE(capture_s1) — «هیچ هویت دومی ساخته نمی‌شود») + INV-IR-DUP:1
   (UNIQUE(resolution_id) روی observations)؛ CHECK gates (scope/source/
   fingerprint/reason consistency، واژگان origin/role، شکل candidateها)؛
   sha256-v1 fingerprints (record + role rows به ترتیب role فروزن) با VOR در
   هر read + structural gates روی شکل durable set؛ بدون UPDATE/DELETE
   (AST-proven)؛ restart-safe؛ tamper-evident.
6. **Provenance (SPEC §9):** هر resolution بعد از re-verify کامل زنجیره
   (V2) commit می‌شود و anchor set کامل (capture_s1/capture_id/document_id/
   extraction_id/normalization_id/domain_state_id) را حمل می‌کند؛ role
   candidate rows فقط counts + pointer (بدون هیچ مقدار raw — pointer
   discipline)؛ re-join byte-identity از طریق read تأییدشده WP-4.1؛ دستکاری
   upstream حتی replay را هم می‌شکند (V1/V2 قبل از R0).
7. **مرزها (رعایت شده — dispatch §14):** بدون Product/Customer matching از
   هر نوع؛ بدون OCR/AI/heuristic/fuzzy (AST symbol sweep)؛ بدون
   Inventory/Sales/Digital Invoice/Holoo/Sync/UI؛ بدون تغییر رفتار P6.1
   (تغییر سطح کد فقط additive)؛ بدون اجرای upstream (spy-proven)؛
   invoice_id در این لایه mint/ذخیره/ارجاع نمی‌شود (OD-IR-I).

**Out of Scope (رعایت شده):** Product Recognition | Customer auto-create |
Customer fuzzy matching | OCR | AI matching | inventory | sales | Digital
Invoice lifecycle | Holoo parser | Cloud sync | UI | mobile | بازکردن هر
لایه Frozen P1–P6.2 | هر تصمیم canonicalization مجدد | WP-7.2 (Reprint &
Duplicate Flows).

**Deliverables / AC / Tests / DoD:** طبق dispatch پیاده‌سازی اجرا شد؛ AC
mapping در SPEC §11؛ شواهد در REG-AR §WP-7.1.

**Implementation Record (2026-10-08 — T-7.1.1..T-7.1.4، dispatch اجرایی):**

- **T-7.1.1 Contract:** SPEC-WP71-IDRES v1.0-MVP (§1..§12: purpose/scope،
  input path، request contract، verification ladder + جدول R0..R3، حالت‌های
  S1/S2/CAPTURE_SCOPED، duplicate handling، durable records، persistence
  OD-IR1..IR7، provenance chain، OD-IR-A..J، AC mapping، test expectations).
  منبع واژگان: D-02/D-03 عیناً + کدهای reason از P6.1 verbatim + dispatch
  §7/§8/§11-§15؛ سند فیزیکی baseline هنوز غایب (MNT-1 — pre-registered، دلیل
  STOP نیست)؛ هیچ contradiction واقعی با Frozen نبود → STOP لازم نشد.
- **T-7.1.2 Implementation:** kandoo/src/identity_resolution/{model,resolver,
  store,service,__init__}.py + run_smoke_identity_resolution.py — resolver.py
  خالص (بدون I/O/clock/randomness؛ delegation به primitive فروزن P6.1)؛
  store.py با ۳ جدول (identity_resolutions / identity_role_candidates /
  identity_duplicate_observations)؛ service.py با resolve (V1→V2→V3→V4→R0→
  R1→R2→R3 → commit اتمیک) + read_resolution/read_resolution_by_capture
  (VOR + structural gates).
- **T-7.1.3 Tests:** 6 فایل / 108 تست — test_ir_resolution.py (۲۸: S2
  establishment، نقش‌ها/pointerها، incomplete ×۳، conflicting ×۳،
  undetermined، non-VALID ×۴ بدون مصرف مقدار (spy)، validationهای binding،
  re-join byte-identity) | test_ir_idempotency.py (۱۹: Case A replay
  (همان state + بین-stateها + بعد از restart + verified-not-blind)، Case B
  definite duplicate + یک هویت سند + observation یکتا، Case C/F تفاوت هویت،
  Case D/E، مرز whitespace/canonical-serialization طبق قرارداد فروزن،
  declaration fingerprint order-independent و collision-safe، drift
  refusal ×۳) | test_ir_durability.py (۲۴: atomicity، zero-residue شکست
  اجباری mid-commit ×۲، restart ×۲، ماتریس tamper (record/hash/role row/
  observation/forged row/hash-consistent forged row — structural gate)،
  CHECK/UNIQUE backstops با INSERT مستقیم SQL ×۷، immutability رفتاری) |
  test_ir_provenance.py (۱۱: spy مصرف walk، انکرها = state تأییدشده،
  provenance روی CAPTURE_SCOPED، شکست زنجیره قبل/بعد از resolution،
  pointer discipline (هیچ مقدار raw در DB)، re-join evidence ابهام) |
  test_ir_boundary.py (۱۴: AST صفر UPDATE/DELETE/DROP، صفر
  random/eval/exec/float، uuid فقط bookkeeping (service.py فقط)، import
  allowlist، صفر identifier ممنوع (fuzzy/similarity/semantic/ocr/...)،
  اثبات reuse فرمول (بدون hashlib)، صفر ارجاع SQL به جدول‌های بیگانه،
  بدون ستون invoice، واژگان verbatim، row-count stability لایه‌های Frozen،
  spy صفر اجرای upstream، determinism بین دو stack مستقل) |
  test_ir_service.py (۱۲: e2e، refusal matrix ×۴، V1 integrity، storage
  mapping، race همگام ۸ thread با storeهای thread-local + backstop
  UNIQUE، race duplicate چند-capture با یک original، تکرار متوالی پایدار)
  — پوشش کامل محورهای dispatch §11-§13.
- **Build → Test → Fix iterations (همه داخل فایل‌های جدید WP-7.1):** (۱)
  صفحات twin باید شماره فاکتور آخرین state تولیدشده را reuse کنند (counter
  ماژول-سراسری تست)؛ (۲) کمک‌تست `_resolve` با پیش‌فرض binding=None باعث
  می‌شد تست drift عملاً همان declaration را بفرستد → فراخوانی صریح service؛
  (۳) tamper مستقیم scope_reason/candidate_count توسط CHECK gates خود store
  رد می‌شود (رفتار درست!) → تست‌ها به ستون‌های خارج CHECK منتقل + تست‌های
  صریح CHECK-refusal اضافه شد؛ (۴) fingerprint متفاوت در تست determinism
  چون corpus بین دو run عوض می‌شد → corpus یک‌بار تولید شد؛ (۵) race
  threadها روی stackهای کامل، رفتار concurrent لایه‌های Frozen (P5.1
  read-on-write) را نمایان می‌کرد — خارج از مرز این WP → race فقط روی لایه
  هویت با ورودی‌های verified از پیش‌خوانده‌شده (stubs inert) + تست
  store-level؛ رفتار Frozen دست‌نخورده و صادقانه مستند شد.
- **T-7.1.4 Verification + governance + delivery:** P7.1 dedicated = **108/
  108 PASSED** (3 تکرار مستقل اضافی هم 108/108)؛ رگرسیون کامل = **1010/1010
  PASSED** (54 capture + 72 reconstruction + 74 extraction + 92 normalization
  + 101 derivation + 172 validation + 125 validation_domain + 112
  canonicalization + 100 canonical_assembly + 108 identity_resolution؛
  Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۱۲ (همه ۱۱ قبلی +
  run_smoke_identity_resolution.py — ۸ گام: S2 recorded → S1 replay →
  definite duplicate → CAPTURE_SCOPED → drift refusal → restart → tamper →
  survival sweep؛ مسیر سرد با پایگاه دادهٔ تازه)؛ Frozen P1–P6.2 untouched
  (git diff = صفر)؛ registerها (REG-WPR/REG-TR/REG-AR) + src/README.md +
  worklog به‌روز؛ archive کامل + MANIFEST-SHA256.txt بازتولید و مستقل verify
  شد.
- **Frozen-layer protection verified:** git diff روی P1–P6.2 = صفر؛ تغییر
  سطح کد فقط additive (spec + src/identity_resolution/ + smoke +
  registers/README)؛ flake ثبت‌شدهٔ P3 در اجرای رسمی PASS (طبق dispatch
  دست‌نخورده ماند).

---

## WP-7.2 — Reprint & Duplicate Flows

```text
WP ID:        WP-7.2
Phase:        P7 — Duplicate / Idempotency
Status:       IMPLEMENTED (2026-10-08 — dispatch اجرایی PO/TM «reconnaissance سپس BUILD») | Acceptance: 4/4 AC PASS (REG-AR) | Tasks: 4/4 DONE (T-7.2.1..T-7.2.4 ✅) | در انتظار Acceptance رسمی PO
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
Spec:         kandoo/specs/WP-7.2-reprint-duplicate-flows-contract.md (SPEC-WP72-DUPFLOW v1.0-MVP)
Code:         kandoo/src/duplicate_flows/ (model/store/service/__init__.py)
Smoke:        kandoo/src/run_smoke_duplicate_flows.py
Tests:        kandoo/src/duplicate_flows/tests/ (58/58 PASSED)
```

**Goal:** تبدیل factهای هویتی دائمی WP-7.1 به جریان‌های عملیاتی صریح —
هر capture artifact دقیقاً یک disposition جریان دائمی و auditable دارد
(INV-DF-1:1): دید اول = `IDENTITY_ESTABLISHED` (S2 یا CAPTURE_SCOPED)؛
ارائهٔ مجدد همان capture = شناسایی reprint (verbatim، read-only، صفر ردیف
جدید)؛ capture متفاوت با همان S2 دقیق = `DUPLICATE_RECOGNIZED` ارجاع‌دهنده
به original قطعی (OD-IR-E) به‌همراه register دائمی duplicate ها — طبق
D-03، بدون هیچ تعریف idempotency جدید و بدون تصمیم canonicalization.

**Scope (پیاده‌سازی شد):**
- نردبان جریان F1–F6 (SPEC §4): passthrough fail-closed refusal/خطاهای
  WP-7.1 (جزئیات verbatim)؛ F2 IDENTITY_ESTABLISHED؛ F3
  DUPLICATE_RECOGNIZED (original + observation)؛ F4 شناسایی reprint
  verbatim با صفر ردیف جدید؛ F5 backfill قطعی از شکل durable خود resolution
  (مستقل از ترتیب استقرار — OD-DF-E)؛ F6 برخورد همزمانی → بازخوانی برنده.
- readهای تأییدشدهٔ جریان (SPEC §6): VOR ردیف خود + باز-تأیید همهٔ
  identity facts لینک‌شده از طریق readهای تأییدشدهٔ WP-7.1 (resolution،
  original، observation) + gates ساختاری بین-store‌ای (drift هر انکر →
  withhold؛ fail-closed).
- register دائمی duplicate ها: `duplicates_of(original_resolution_id)` —
  کوئری روی dispositionهای commit‌شده؛ ذخیرهٔ هیچ مقدار raw (pointer
  discipline).
- Persistence الگوی پروژه (SPEC §7/§8 OD-DF1..DF7): SQLite فایل مجزا
  (duplicate-flows.db)؛ synchronous=FULL؛ commit اتمیک تک‌ردیفی؛ immutable
  (بدون UPDATE/DELETE — AST-proven)؛ sha256-v1 از طریق سرویس S1 پروژه
  (بدون hashlib)؛ CHECK + UNIQUE(capture_s1) به‌عنوان backstop نهایی
  INV-DF-1:1؛ restart-safe؛ tamper-evident.
- واژگان جریان (OD-DF-B، تفویض D-09): durable =
  `IDENTITY_ESTABLISHED | DUPLICATE_RECOGNIZED`؛ `REPRINT_RECOGNIZED`
  فقط outcome فراخوانی، هرگز ذخیره‌شدنی (CHECK منع می‌کند)؛ بدون هیچ
  مترادفFrozen و بدون scope جدید.

**Out of Scope (رعایت شده):** تصمیم canonicalization مجدد (P6.1 تنها مرجع —
G4/G5 تکرار نشد) | Canonical Assembly / invoice_id (P6.2) | عملیات REVIEW
queue | تطابق product/customer | OCR/AI/fuzzy/heuristic | تغییر هر لایهٔ
Frozen P1–P7.1 | merge/delete/reshape resolutionها و observationها | event
log اضافی برای reprint (شناسایی read-only است — بدون قابلیت speculative) |
Holoo parser | Cloud sync | UI | mobile.

**Deliverables / AC / Tests / DoD:** طبق dispatch پیاده‌سازی شد؛ AC mapping
در SPEC §11؛ شواهد در REG-AR §WP-7.2.

**Implementation Record (2026-10-08 — T-7.2.1..T-7.2.4، dispatch اجرایی):**

- **T-7.2.1 Contract:** SPEC-WP72-DUPFLOW v1.0-MVP (§1..§12) — basis فروزن:
  D-02/D-03 verbatim، SPEC-WP71-IDRES (لایهٔ مصرف‌شده)، SPEC-WP61-CANGATE
  ( authority انحصاری canonicalization). منبع scope: REG-WPR Phase Index P7
  («WP-7.2 Reprint & Duplicate Flows») + downstream note SPEC-WP71 §header
  («WP-7.2 … any future consumer of durable identity resolutions»)؛ هیچ
  contradiction واقعی با Frozen نبود → STOP لازم نشد.
- **T-7.2.2 Implementation:** kandoo/src/duplicate_flows/{model,store,
  service,__init__}.py — بدون resolver.py (طبق OD-DF-A: هیچ منطق هویتی
  در این لایه نیست؛ classification نگاشت قطعی outcome typeهای WP-7.1 است).
  store.py: جدول flow_dispositions با CHECK gates شکل outcome/reference و
  scope/fingerprint؛ service.py: handle (F1..F6) + read_disposition /
  read_disposition_by_id (VOR + باز-تأیید لینک‌ها + structural gates) +
  duplicates_of / dispositions (OD-DF-H)؛ run_smoke_duplicate_flows.py
  (۸ گام، cold-start).
- **T-7.2.3 Tests:** 6 فایل / 58 تست — test_df_reprint.py (۱۱: دید اول،
  reprint verbatim صفر-ردیف، بین-stateها (A3)، restart، drift refusal ×۲،
  tamper disposition → fail-closed، reprint duplicate/CAPTURE_SCOPED،
  third-capture یک original) | test_df_duplicate.py (۱۰: twin/third → یک
  original، register، read با باز-تأیید original+observation، Case F
  یک-کاراکتر، مرز whitespace، بدون fuzzy، CAPTURE_SCOPED هرگز duplicate
  ×۳) | test_df_service.py (۱۳: refusal passthrough ×۴ با جزئیات verbatim،
  stateهای non-VALID → established بدون مصرف مقدار، delegation
  spy-proven، idempotency handle، F5 backfill عادی/duplicate، خواندن‌ها و
  refusal صریح) | test_df_durability.py (۹: UNIQUE backstop دوباره،
  CHECK gates با SQL مستقیم ×۵، refusalهای Python-side، zero-residue شکست
  اجباری، restart، ماتریس tamper (own row / hash-consistent forged →
  structural gate / linked resolution / original)) | test_df_boundary.py
  (۱۵: AST صفر UPDATE/DELETE/DROP/random/eval/float/hashlib، uuid فقط
  bookkeeping، import allowlist بدون canonicalization، بدون فرمول هویت،
  identifier sweep، بدون جدول بیگانه/ستون invoice/واژگان review، واژگان
  verbatim، REPRINT_RECOGNIZED هرگز ذخیره‌شدنی، عمومیت سطح عمومی،
  row-count stability لایه‌های Frozen، spy صفر اجرای upstream، race
  ۸-thread با storeهای thread-local + stubs inert (الگوی ثبت‌شدهٔ WP-7.1)،
  race twin با یک original، determinism استقرار) — پوشش محورهای SPEC §12.
- **Build → Test → Fix iterations (همه داخل فایل‌های جدید WP-7.2):** (۱)
  نام فیلد outcomeها به `record` هم‌تراز شد با ladderهای WP-7.1؛ (۲)
  twinهای duplicate باید captureهای «جدید» می‌بودند (handle_new) نه
  re-projection همان nid (DomainStateAlreadyExists) — الگوی A3 فقط برای
  تست reprint بین-stateها؛ (۳) corpus بدون شماره باید byte-mتمایز شود وگرنه
  capture خودش dedup می‌شود (IngestDuplicateAtCapture — رفتار درست
  Frozen)؛ (۴) raceها طبق سابقهٔ ثبت‌شدهٔ WP-7.1 فقط روی لایهٔ جریان با
  storeهای thread-local + stubs inert اجرا شدند (رفتار concurrent لایه‌های
  Frozen خارج از مرز این WP و دست‌نخورده)؛ (۵) دو ناهماهنگی تست (assert
  detail verbatim / row_factory) در فایل‌های تست اصلاح شد — هیچ تغییری در
  کد لایه برای سبز شدن لازم نبود.
- **T-7.2.4 Verification + governance + delivery:** P7.2 dedicated = **58/
  58 PASSED** (2 تکرار مستقل اضافی هم 58/58)؛ رگرسیون کامل = **1067/1068
  جمع‌کل (1067 PASSED + 1 flake ثبت‌شدهٔ از پیش موجود)** — اجرای خالص
  بدون flake = **1067/1067 PASSED** (54+72+74+92+101+172+125+112+100+108+
  58؛ Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۱۳ (همه ۱۲ قبلی +
  run_smoke_duplicate_flows.py — ۸ گام: establish → reprint verbatim →
  definite duplicate + register → CAPTURE_SCOPED → drift refusal → restart
  → tamper withhold → survival/vocabulary sweep؛ cold-start)؛ **flake
  ثبت‌شده:** test_ir_provenance.py::test_no_raw_pipeline_values_are_stored
  (suite فروزن WP-7.1) — وابسته به تاریخ: در UTC date برابر با تاریخ corpus
  (2026-10-08)، timestamp کتاب‌نگاری created_at خودِ رکورد (متادیتای
  مشروعِ هر لایه) با مقدار تاریخ corpus برخورد می‌کند و false-positive
  می‌سازد؛ در worktree خالص HEAD 9d7f372 (بدون هیچ کد WP-7.2) هم بازتولید
  شد ⇒ از پیش موجود، نه ناشی از این WP؛ pointer discipline به‌ر_ast سالم
  است (هیچ مقدار pipeline ذخیره نشده — تنها hit در created_at)؛ طبق
  حکمرانی Frozen فایل دست‌نخورده ماند (الگوی flake-note ثبت‌شدهٔ WP-6.1/
  WP-7.1)؛ registerها (REG-WPR/REG-TR/REG-AR) + src/README.md + worklog
  به‌روز؛ archive کامل + MANIFEST-SHA256.txt بازتولید و مستقل verify شد.
- **Frozen-layer protection verified:** git diff روی P1–P7.1 = صفر (فقط
  فایل‌های جدید WP-7.2 + registerها/README/spec/worklog/packager)؛ تغییر
  سطح کد فقط additive.

---

## WP-8.1 — Product Exact Match

```text
WP ID:        WP-8.1
Phase:        P8 — Product Candidate
Status:       IMPLEMENTED (2026-10-08 — Mission dispatch «PRODUCT IDENTITY &
              CUSTOMER LINKING» Phase A) | Acceptance: 4/4 AC PASS (REG-AR) |
              Tasks: 4/4 DONE (T-8.1.1..T-8.1.4 ✅) | در انتظار Acceptance رسمی PO
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
Spec:         kandoo/specs/WP-8.1-product-exact-match-contract.md (SPEC-WP81-PMATCH v1.0-MVP)
Code:         kandoo/src/product_candidate/ (model/store/service/__init__.py)
Smoke:        kandoo/src/run_smoke_product_matching.py
Tests:        kandoo/src/product_candidate/tests/ (57/57 PASSED)
```

**Goal:** پیاده‌سازی دقیقاً همان قاعدهٔ فروزن D-05 — Exact Match فقط با
identifier قطعی معتبر — به‌عنوان fact دائمی، auditable و deterministic در
دامنهٔ Product Candidate (AD-02)، به‌همراه حداقل Catalog Identity register
لازم برای خروجی `Catalog Identity`؛ هر چیز دیگر unresolved می‌ماند:
**ابهام، ابهام می‌ماند** — بدون candidate generation، بدون confidence، بدون
approval، بدون هر گونه fuzzy/semantic/AI matching (Mission dispatch + D-05).

**Scope (پیاده‌سازی شد):**
- Catalog Identity register (OD-PM2): ثبت explicit/idempotent/append-only —
  API ثبت هیچ پارامتر capture/invoice ندارد ⇒ جهش کاتالوگ از مسیر capture
  ساختاراً ناممکن است (AS-02: محصول قبل از فاکتور؛ analog دیسیپلین D-06/DEF3)؛
  UNIQUE(kind, value) ⇒ قطعیت identifier با ساخت تضمین می‌شود (OD-PM5).
- نردبان matching M1–M6 (SPEC §4): خواندن verified مصرفی P6.2 (verbatim،
  fail-closed، spy-proven) → اعتبارسنجی declaration → resolution مرجع declared
  با قاعدهٔ exactly-one (0/≥2 → refusal، هرگز auto-resolution) → replay
  verbatim با صفر ردیف جدید (هرگز re-decide نمی‌شود — OD-PM4) → lookup دقیق
  count-based (0 → UNRESOLVED(no-catalog-identity) دائمی؛ 1 → EXACT_MATCHED؛
  ≥2 → fail-closed integrity) → commit اتمیک تک‌ردیفی.
- readهای تأییدشده (SPEC §6): VOR ردیف خود + باز-تأیید فاکتور لینک‌شده از
  طریق read verified P6.2 + re-join اشاره‌گر (canonical_seq/field_name/
  provenance) + باز-تأیید catalog identity + اثبات زندهٔ byte-identity؛ ردیف
  دستکاری‌شده در هر لایه‌ای withhold می‌شود.
- Pointer discipline (OD-PM6): ردیف match هیچ مقدار identifier را ذخیره
  نمی‌کند — مقدار در read verified P6.2 (زنده) و در محتوای ثبت‌شدهٔ خود
  کاتالوگ زندگی می‌کند.
- Persistence الگوی پروژه (SPEC §7/OD-PM1): SQLite فایل مجزا
  (product-candidate.db)؛ synchronous=FULL؛ commit اتمیک تک‌ردیفی؛ immutable
  (بدون UPDATE/DELETE — AST-proven)؛ sha256-v1 از طریق سرویس S1 پروژه (بدون
  hashlib)؛ CHECK + UNIQUE backstops؛ restart-safe؛ tamper-evident.
- واژگان (OD-PM7): durable = `EXACT_MATCHED | UNRESOLVED` (با reason پایدار
  `no-catalog-identity`) — بدون هیچ واژگان candidate/approval/confidence و
  بدون مترادف هیچ واژهٔ فروزن.

**Out of Scope (رعایت شده):** Candidate Generation / Candidate Approval
(WP-8.2 — نیازمند تصمیم PO؛ در این Mission ساخت آن‌ها ممنوع) | barcode
semantics/grammar/checksum (هیچ‌کجا frozen نشده — ممنوع) | تصمیم
canonicalization/identity (P6.1/P7.1) | هر چیز customer (WP-9.1) | عملیات
REVIEW | جهش هر رکورد upstream | اجرای upstream | Holoo parser | Cloud sync |
UI | mobile | تغییر هر لایهٔ Frozen P1–P7.2.

**Deliverables / AC / Tests / DoD:** طبق Mission dispatch پیاده‌سازی شد؛ AC
mapping در SPEC §9؛ شواهد در REG-AR §WP-8.1.

**Implementation Record (2026-10-08 — T-8.1.1..T-8.1.4، Mission dispatch):**
- Scope of record = REG-WPR Phase Index P8 «WP-8.1 Exact Match» + Mission
  dispatch 2026-10-08؛ مشتق فقط از سوابق برقرار (D-05/AD-02/AS-02/OD-A9
  precedents/الگوی OD-A4 declared-input) — هیچ نیازمندی محصولی اختراع نشد؛
  هیچ تناقض معماری پیدا نشد ⇒ STOP صادر نشد.
- پیاده‌سازی additive صرف؛ مصرف verbatim سرویس verified read پ6.2؛
  الگوی store/service/test/smoke دقیقاً مطابق الگوهای WP-7.1/WP-7.2؛
  dedicated 57/57 (+2 تکرار مستقل)؛ رگرسیون کامل 1124/1125 (۱ flake ثبت‌شدهٔ
  از پیش موجود در suite فروزن WP-7.1 — بازتولیدشده در dispatch قبل)؛
  SMOKE 8-گام cold-start OK؛ Frozen P1–P7.2 byte-untouched (git diff روی
  tracked فایل‌ها = فقط ثبت‌های حکمرانی + فایل‌های جدید WP-8.1).

---

## WP-9.1 — Deterministic Customer Linking

```text
WP ID:        WP-9.1
Phase:        P9 — Customer Linkage
Status:       IMPLEMENTED (2026-10-08 — Mission dispatch «PRODUCT IDENTITY &
              CUSTOMER LINKING» Phase C) | Acceptance: 4/4 AC PASS (REG-AR) |
              Tasks: 4/4 DONE (T-9.1.1..T-9.1.4 ✅) | در انتظار Acceptance رسمی PO
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
Spec:         kandoo/specs/WP-9.1-customer-linking-contract.md (SPEC-WP91-CUSTLINK v1.0-MVP)
Code:         kandoo/src/customer_linking/ (model/store/service/__init__.py)
Smoke:        kandoo/src/run_smoke_customer_linking.py
Tests:        kandoo/src/customer_linking/tests/ (59/59 PASSED)
```

**Goal:** پیاده‌سازی دقیقاً همان تصمیم فروزن D-06 — link قطعی و auditable
فقط به Customer **موجود**؛ auto-create ساختاراً ناموجود — به‌عنوان fact
لینک append-only در دامنهٔ Customer Linkage (AD-02) با تنها قاعدهٔ
deterministic برقرار پروژه: **identifier قطعی معتبر با تطابق byte-exact به
دقیقاً یک customer identity ثبت‌شده**؛ در غیر این صورت UNRESOLVED دائمی و
auditable — **ابهام، ابهام می‌ماند** و هیچ مشتری‌ای ساخته نمی‌شود.

**Scope (پیاده‌سازی شد):**
- Customer Identity register (OD-CL2): ثبت explicit/idempotent/append-only
  هویت مشتریان موجود — API ثبت هیچ پارامتر capture/invoice ندارد و نردبان
  link هیچ شاخهٔ creation ندارد ⇒ هیچ مسیر کدی از capture/فاکتور به ردیف
  مشتری وجود ندارد (اثبات AST + signature + behavioral).
- نردبان linking L1–L6 (SPEC §4): خواندن verified مصرفی P6.2 (verbatim،
  fail-closed، spy-proven) → اعتبارسنجی declaration → resolution مرجع
  declared با قاعدهٔ exactly-one (0/≥2 → refusal، هرگز auto-resolution) →
  replay verbatim با صفر ردیف جدید (هرگز re-decide نمی‌شود — OD-CL4) →
  lookup دقیق count-based (0 → UNRESOLVED(no-customer-identity) دائمی؛
  1 → LINKED به مشتری موجود؛ ≥2 → fail-closed integrity) → commit اتمیک
  تک‌ردیفی؛ برخورد همزمانی → replay read-only.
- readهای تأییدشده (SPEC §6): VOR ردیف خود + باز-تأیید فاکتور لینک‌شده از
  طریق read verified P6.2 + re-join اشاره‌گر + باز-تأیید customer identity +
  اثبات زندهٔ byte-identity؛ ردیف دستکاری‌شده در هر لایه‌ای withhold می‌شود.
- Pointer discipline (OD-CL6): ردیف link هیچ مقدار identifier را ذخیره
  نمی‌کند — مقدار در read verified P6.2 (زنده) و در محتوای ثبت‌شدهٔ خود
  register زندگی می‌کند.
- Persistence الگوی پروژه (SPEC §7/OD-CL1): SQLite فایل مجزا
  (customer-linking.db)؛ synchronous=FULL؛ commit اتمیک تک‌ردیفی؛ immutable
  (بدون UPDATE/DELETE — AST-proven)؛ sha256-v1 از طریق سرویس S1 پروژه (بدون
  hashlib)؛ CHECK + UNIQUE backstops؛ restart-safe؛ tamper-evident.
- واژگان (OD-CL7): durable = `LINKED | UNRESOLVED` (با reason پایدار
  `no-customer-identity`) — بدون هیچ واژگان creation/merge/enrichment و
  بدون مترادف هیچ واژهٔ فروزن؛ OD-A9 فاکتور canonical (absent در زمان
  assembly) دست‌نخورده می‌ماند — خروجی این WP رکوردهای additive رجیستر
  لینک است، نه جهش فاکتور فروزن.

**Out of Scope (رعایت شده):** ایجاد خودکار مشتری از هر مسیر (D-06/DEF3 —
ساختاراً ناممکن) | merge/dedup مشتری (DEF3 — PO) | enrichment (D-06 —
خارج از Freeze؛ WP-11.x) | fuzzy/semantic/AI/best-match (تنها قاعده =
exact definitive-identifier) | barcode semantics | تصمیم
canonicalization/identity (P6.1/P7.1) | product matching (WP-8.1) | عملیات
REVIEW | جهش هر رکورد upstream | اجرای upstream | Holoo parser | Cloud sync |
UI | mobile | تغییر هر لایهٔ Frozen P1–P8.1.

**Deliverables / AC / Tests / DoD:** طبق Mission dispatch پیاده‌سازی شد؛ AC
mapping در SPEC §9؛ شواهد در REG-AR §WP-9.1.

**Implementation Record (2026-10-08 — T-9.1.1..T-9.1.4، Mission dispatch):**
- Scope of record = REG-WPR Phase Index P9 «WP-9.1 Deterministic Customer
  Linking» + Mission dispatch 2026-10-08؛ مشتق فقط از سوابق برقرار
  (D-06/DEF3/OD-A9/D-05 semantics/الگوی declared-input) — هیچ نیازمندی
  محصولی اختراع نشد؛ قاعدهٔ link = همان semantics تطبیق قطعی برقرار پروژه؛
  هیچ تناقض معماری پیدا نشد ⇒ STOP صادر نشد.
- پیاده‌سازی additive صرف؛ مصرف verbatim سرویس verified read پ6.2؛ دامنهٔ
  مجزا (Customer Linkage) بدون shared code path با WP-8.1 (No speculative
  abstraction)؛ الگوی store/service/test/smoke دقیقاً مطابق الگوهای
  WP-7.1/WP-7.2/WP-8.1؛ dedicated 59/59 (+2 تکرار مستقل)؛ رگرسیون کامل
  1183/1184 (۱ flake ثبت‌شدهٔ از پیش موجود در suite فروزن WP-7.1)؛ SMOKE
  8-گام cold-start OK؛ Frozen P1–P8.1 byte-untouched.

---

## WP-10.1 — Digital Invoice Lifecycle

```text
WP ID:        WP-10.1
Phase:        P10 — Digital Invoice
Status:       IMPLEMENTED (2026-10-08) | Acceptance: 4/4 AC PASS (REG-AR — در انتظار Acceptance رسمی PO) | Tasks: 4/4 DONE (T-10.1.1..T-10.1.4 ✅)
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** ایجاد سازوکار Lifecycle فاکتور دیجیتال — یک register دائمی، append-only، tamper-evident با 1:1 به هر Canonical Invoice صادرشدهٔ P6.2، که پیشروی آن را با واژگان فروزن `DRAFT → EXTRACTED → VALIDATED → ISSUED → REVOKED | SUPERSEDED` (انتقال عیناً طبق AS-03) ثبت می‌کند؛ هر حرکت یک act صریح و fail-closed با باز-تأیید زندهٔ زنجیرهٔ P6.2 در لحظهٔ act؛ هیچ چیز خودکار نیست.

**Scope:**
- Entry (open) فقط از read تأییدشده + whole-chain trace پ6.2 (مصرف verbatim — never bypassed؛ spy-proven)
- State machine lifecycle با ماتریس انتقال declarative (۵ انتقال قانونی؛ DB CHECK-enforced) + انضباط terminal
- اعمال lifecycle: mark_extracted / mark_validated / issue / revoke / supersede — صریح، idempotent در state هدف، replay verbatim (D-03)
- verified reads (VOR own + یکپارچگی زنجیرهٔ event + باز-تأیید P6.2 + cross-check anchor + باز-تأیید replacement) + trace_digital_invoice (یک head link روی زنجیرهٔ سالم P6.2 تا Capture S1)
- persistence با الگوی store پروژه (SQLite FULL، commit اتمیک، append-only بدون UPDATE/DELETE، sha256-v1 از طریق S1، CHECK/UNIQUE gates، restart-safe، tamper-evident، CAS append درون تراکنش)

**Out of Scope:**
ارائه/قالب/رندر/کانال تحویل (WP-10.2 / DEF5 — PO) | بازتعریف canonicalization (P6.1) | assembly/invoice_id (P6.2) | عملیات REVIEW (P5.2/P6.1) | ساخت مسیر native Sale/Invoice (AS-02/DEF1) | semantics مشتری (WP-9.1/D-06) | product matching (WP-8.1) | fuzzy/AI matching | inventory (AD-03) | تفسیر ارز/مالیات (IRR نقل واژگان فروزن است؛ پیاده‌سازی نیست) | OCR/Holoo/Cloud/UI/mobile | هر رفتار خودکار lifecycle

**Inputs:** Decision Register (AS-03, AS-02, AS-01, AS-04, AD-01..04, D-01..D-09) | Deferred Decision Register (DEF1, DEF5) | Mission dispatch «DIGITAL INVOICE LIFECYCLE — P10» (2026-10-08) | SPEC-WP62-CANASM (upstream boundary) | الگوهای WP-7.1/7.2/8.1/9.1

**Dependencies:**
- P6.2 Canonical Assembly (IMPLEMENTED — read + trace تأییدشده)
- زنجیرهٔ کامل P1–P9 (فروزن/IMPLEMENTED)

**Deliverables:**
1. `kandoo/specs/WP-10.1-digital-invoice-lifecycle-contract.md` — SPEC-WP101-DILIFE v1.0-MVP (§1..§12؛ OD-DI-A..K)
2. `kandoo/src/digital_invoice/` — model/store/service/__init__ (ماتریس انتقال + projection pure-function)
3. Test Suite اختصاصی (`src/digital_invoice/tests/` — ۵ فایل، ۵۴ تست)
4. Smoke runner: `run_smoke_digital_invoice.py` (شانزدهمین smoke — ۸ گام cold-start)
5. به‌روزرسانی Registerها (REG-WPR/REG-TR/REG-AR) + src/README.md + worklog

**Acceptance Criteria:** (جزئیات verification در Acceptance Register)
- AC-10.1.1 — Entry & boundary: ورود فقط از P6.2 (spy-proven, never bypassed)؛ INV-DI-1:1 (UNIQUE backstop + race ۸-thread)؛ refusals fail-closed با zero residue؛ origin verbatim (CHECK واژگان فروزن)؛ بدون هر semantics ممنوع (AST + vocabulary sweep)
- AC-10.1.2 — State machine: واژگان فروزن عیناً (بدون افزودن/تغییر نام state)؛ ماتریس دقیقاً §5.2 (DB CHECK + mirror پایتون + تست‌های رفتاری)؛ REVOKE/SUPERSEDE از ISSUED منحصراً؛ چرخهٔ supersede ساختاراً ناممکن؛ هیچ رفتار خودکار
- AC-10.1.3 — Idempotency & auditability: replay verbatim صفر-ردیف در همهٔ stateهای هدف؛ supersede replay byte-match؛ event chain append-only با seq gap-free به‌صورت CAS درون-تراکنشی؛ projection = pure function (determinism cross-stack)؛ anchoring sha256-v1
- AC-10.1.4 — Persistence & provenance: الگوی کامل store؛ read ladder کامل؛ trace یک head link تا Capture S1؛ pointer discipline (بدون ذخیرهٔ مقدار canonical)؛ Frozen P1–P9 byte-untouched (رگرسیون کامل)

**Tests:** happy path open/lifecycle | ماتریس کامل (قانونی/غیرقانونی) | replay صفر-ردیف | supersede ladder + byte-match conflict + چرخه | reason_note verbatim | tamper matrix (own/event/hash-consistent forged/CHECK via SQL مستقیم/UNIQUE backstop) | gap/chain-break/anchor-drift gates | forced failure zero-residue | restart durability | race ۸-thread (open/advance/REVOKE-vs-SUPERSEDE) | AST probes (صفر UPDATE/DELETE/DROP/hashlib/random/eval؛ allowlist import؛ INSERT surface = دقیقاً ۲) | spy P6.2 | row-count stability فروزن | end-to-end تا terminal

**DoD:**
- [x] هر ۴ AC با شواهد در Acceptance Register بسته شده باشد (REG-AR: 4/4 PASS — T-10.1.4؛ 54/54 tests + SMOKE OK)
- [x] کد طبق الگوهای برقرار و انتخاب‌های delegated (OD-DI-A..K) در SPEC اعلام شده باشد (D-09)
- [x] هیچ قلم از Out of Scope / Forbidden Actions اجرا نشده باشد
- [x] Registerها (Task + Acceptance + همین Register) به‌روز باشند
- [x] مورد خارج از Baseline رخ نداد ⇒ STOP Protocol لازم نشد (MNT-1 baseline note طبق عرف WP-6.1..WP-9.1 رعایت شد)

**Implementation Record (2026-10-08 — T-10.1.1..T-10.1.4، Mission dispatch):**
- Scope of record = REG-WPR Phase Index P10 «WP-10.1 Digital Invoice Lifecycle» + Mission dispatch «DIGITAL INVOICE LIFECYCLE — P10» 2026-10-08 که واژگان lifecycle فروزن را self-contained اعلام کرد؛ طبق AS-03 عیناً منتقل شد (بدون state جدید/تغییر نام)؛ ماتریس انتقال و act semantics به‌عنوان delegated detail (OD-DI-D و بقیه OD-DI-*) اعلام شدند — هیچ نیازمندی محصولی اختراع نشد؛ هیچ تناقض معماری پیدا نشد ⇒ STOP صادر نشد.
- اصلاح طراحی حین تست (پیش از commit): gate «replacement باید ISSUED باشد» فقط قانون لحظهٔ act است (§5.4)؛ در read-time حذف شد تا read تاریخچهٔ زنجیره‌های تصحیح (a→b→c) قطعی بماند؛ commit event به CAS درون-تراکنشی ارتقا یافت (stale-state append ساختاراً ناممکن — OD-DI3).
- پیاده‌سازی additive صرف؛ Frozen P1–P9 byte-untouched؛ dedicated 54/54 (+2 تکرار مستقل)؛ رگرسیون کامل 1237/1238 (۱ flake ثبت‌شدهٔ از پیش موجود در suite فروزن WP-7.1 — تفکیک طبق Flake Policy)؛ SMOKE 8-گام cold-start OK (شانزدهمین smoke).

---

## WP-10.2 — Delivery (DEFERRED — PO DECISION REQUIRED)

```text
WP ID: WP-10.2 | Phase: P10 | Status: DEFERRED — DEF5 (PO) + بدون تعریف کامل WP (فقط Level Index)
Owner Role: Product Owner
```

**Goal (index-level):** تحویل/ارائهٔ Digital Invoice.

**چرا اجرا نشد (Stop-4 + DEF5):** واژگان «Delivery» در سطح presentation/کانال تحویل قرار دارد که DEF5 آن را صریحاً به تصمیم PO موکول کرده است (قالب نمایش، رندر، جزئیات کانال‌های تحویل). تعریف ۱۴-فیلدی کامل WP نیز در REG-WPR وجود ندارد؛ اجرای آن مستلزم حدس زدن contract یا business rule جدید بود. هیچ policy جایگزینی ساخته نشد.

---

## WP-11.1 — Holoo DB Spike (READ-ONLY)

```text
WP ID:        WP-11.1
Phase:        P11 — Holoo Integration / Enrichment
Status:       IMPLEMENTED (2026-10-08) | Acceptance: 4/4 AC PASS (REG-AR — در انتظار Acceptance رسمی PO) | Tasks: 4/4 DONE (T-11.1.1..T-11.1.4 ✅)
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** اثباتِ امکان خواندن/استخراج اطلاعات مورد نیاز از یک منبعِ Holoo-shaped — به‌صورت READ-ONLY مطلق، fail-closed، deterministic و فقط-گزارش (D-04: «Spike فقط گزارش می‌دهد»). خروجی Spike فقط یک گزارش provenance-preserving است؛ هیچ مقداری وارد دامنهٔ Kandoo نمی‌شود.

**Scope:**
- لایهٔ enforcement پنج‌لایهٔ READ-ONLY (SPEC §6): engine `mode=ro` (L1) | `PRAGMA query_only=ON` با read-back evidence (L2) | runtime SQL read-guard با allowlist محافظه‌کار (L3) | AST probes ساختاری روی کل package (L4) | اثبات بایت‌سطح: hash/size/mtime/change-counter/فهرست پوشه قبل و بعد از هر اجرا + بدون side-file (L5)
- Schema discovery فقط با PRAGMAهای read-whitelisted، خروجی sorted (بدون حدس schema — §2.7)
- نگاشت DECLARED عملگر → اعتبارسنجی fail-closed علیه schema کشف‌شده (جدول/ستون/order_by ناموجود → MAPPING_REFUSED با reason؛ duplicate name → refusal کل request)
- Extraction قطعی: دقیقاً دو statement گاردگذاری‌شده به‌ازای هر selection (COUNT + projection با ORDER BY/LIMIT)؛ encoding type-tagged قطعی (NULL/INT/REAL-hex/TEXT/BLOB-base64)؛ truncation صدادار
- گزارش HolooSpikeReport — بدون wall-clock، JSON canonical، فقط-حافظه (package هیچ فایلی نمی‌نویسد)

**Out of Scope:**
هرگونه نوشتن در Holoo (DEF1/AD-03/D-04) | ساخت Sale (DEF1) | ساخت مشتری (D-06/DEF3) | inventory/accounting (AD-03) | ورود هر مقدار استخراج‌شده به دامنهٔ Kandoo (D-04 — مسیر تنها: External Flow کامل طبق AS-01، فضای تصمیم WP-11.2+/PO) | نگاشت schema Holoo، source authority، sync semantics، write-back (WP-11.2 — STOP؛ سابقهٔ DEF6) | Adapter موتور live (ODBC/SQL Server)، منبع شبکه‌ای، API Holoo (offline-safe: فقط فایل SQLite استاندارد) | OCR/VLM | UI | fuzzy/AI matching (D-08) | retention/privacy مقادیر (DEF4) | باز کردن هر لایهٔ فروزن P1–P10

**Inputs:** Decision Register (D-04 FROZEN، AD-01، AS-01، D-02، D-03، D-06، D-08، D-09) | Deferred Decision Register (DEF1، DEF3، DEF4، سابقهٔ DEF6) | Mission dispatch «HOLOO INTEGRATION — READ-ONLY SPIKE» (PO، 2026-10-08 — self-contained READ-ONLY boundary) | REG-WPR Phase Index P11 «قابل شروع پس از G1» (G1 ✅ PASS) | الگوهای WP-6.2/WP-7.1/WP-7.2/WP-8.1/WP-9.1/WP-10.1

**Dependencies:**
- G1 Architecture Approval (✅ PASS — شرط صریح Phase Index برای شروع WP-11.1)
- زنجیرهٔ کامل P1–P10 (فروزن/IMPLEMENTED — هیچ تغییری لازم ندارد؛ additive-only)

**Deliverables:**
1. `kandoo/specs/WP-11.1-holoo-db-spike-contract.md` — SPEC-WP111-HDS v1.0-MVP (§1..§14؛ OD-HS-A..K)
2. `kandoo/src/holoo_spike/` — model/store/service/__init__ (read-only by construction؛ بازاستفادهٔ S1 برای hash — بدون hashlib دوم؛ بدون identity/canonicalization دوم)
3. Test Suite اختصاصی (`src/holoo_spike/tests/` — ۴ فایل + conftest + hs_helpers SYNTHETIC fixture؛ ۷۹ تست)
4. Smoke runner: `run_smoke_holoo_spike.py` (هفدهمین smoke — ۸ گام cold-start)
5. به‌روزرسانی Registerها (REG-WPR/REG-TR/REG-AR) + src/README.md + worklog

**Acceptance Criteria:** (جزئیات verification در Acceptance Register)
- AC-11.1.1 — Read path: read provenance-preserving منبع Holoo-shaped با نگاشت DECLARED؛ discovery کامل؛ extraction صحیح چند-نوعی (unicode/NULL/int64/REAL/BLOB/identifier فاصله‌دار)؛ تکرار ×2 byte-identical (determinism)
- AC-11.1.2 — Zero-mutation proof: ردِ write در سطح engine از طریق connection تولیدی (INSERT/UPDATE/DELETE/CREATE/DROP)؛ ردِ گارد برای همهٔ کلاس‌های mutating؛ hash/size/mtime/change-counter/dir-listing قبل==بعد در اجراهای متوالی؛ بدون side-file؛ گزارش فقط وقتی صادر می‌شود که hash در open==close هم‌ارز باشد
- AC-11.1.3 — Fail-closed inputs: منبع ناموجود/directory/غیر-SQLite/خالی → hard failure بدون گزارش؛ نگاشت نامعتبر → MAPPING_REFUSED با reason دقیق و صفر ردیف ساختگی؛ duplicate selection names → refusal کل request؛ case-folding حدس زده نمی‌شود
- AC-11.1.4 — Boundary discipline: خروجی فقط گزارش (D-04)؛ import allowlist (stdlib + capture) و هیچ sibling دامنه‌ای؛ vocabulary sweep (فقط ۵ role گزارشی؛ بدون Sale/Canonical/REVIEW/…)؛ sweep سازندهٔ fixture از package تولیدی (OD-HS-K)؛ additive-only — Frozen P1–P10 byte-untouched (رگرسیون کامل)

**Tests:** read path end-to-end | discovery sorted + internal-object count | همهٔ storage-classهای SQLite در encoding | determinism ×2 + استقلال از ترتیب declaration (بخش‌های گزارش) | audit SQL verbatim execution-true | ۲۴ parametrized گارد (mutating/malformed) + ۹ parametrized مجاز | engine refusals | L5 byte proofs (۱/۵ اجرا + write-refusal hammer) | unavailable/malformed sources | refusals با reason | empty table | truncation | int64 max | identifier با quote/space | duplicate names | AST probes (no mutating SQL constant، no commit/executescript/executemany، no eval/exec/hashlib/random، import allowlist، literalهای mode=ro/query_only) | vocabulary sweep

**DoD:**
- [x] هر ۴ AC با شواهد در Acceptance Register بسته شده باشد (REG-AR: 4/4 PASS — T-11.1.4؛ 79/79 tests + SMOKE OK)
- [x] کد طبق الگوهای برقرار و انتخاب‌های delegated (OD-HS-A..K) در SPEC اعلام شده باشد (D-09)
- [x] هیچ قلم از Out of Scope / Forbidden Actions اجرا نشده باشد
- [x] Registerها (Task + Acceptance + همین Register) به‌روز باشند
- [x] مورد خارج از Baseline رخ نداد ⇒ STOP Protocol لازم نشد (MNT-1 baseline note طبق عرف WP-6.1..WP-10.1 رعایت شد)

**Implementation Record (2026-10-08 — T-11.1.1..T-11.1.4، Mission dispatch):**
- Scope of record = REG-WPR Phase Index P11 «WP-11.1 Holoo DB Spike (read-only؛ قابل شروع پس از G1)» + Mission dispatch «HOLOO INTEGRATION — READ-ONLY SPIKE» 2026-10-08 که مرز READ-ONLY را self-contained تعریف کرد؛ واژگان نقش گزارش (§3) و الزامات آزمون از dispatch استخراج شد — هیچ نیازمندی محصولی اختراع نشد؛ هیچ تناقض معماری پیدا نشد ⇒ STOP صادر نشد.
- «بررسی اجرایی Holoo DB» در ممنوعات همیشگی README فقط ناظر به بازرسی عملیاتی/اجرایی Holoo واقعی توسط Agent است؛ WP-11.1 سازوکار read-only را می‌سازد و فقط روی fixture SYNTHETIC (ساخت خود suite، برچسب‌گذاری صریح) اجرا می‌شود — هیچ سیستم واقعی Holoo لمس نشد؛ عملیات روی منبع واقعی با عملگر/PO است (OD-HS-A).
- پیاده‌سازی additive صرف؛ Frozen P1–P10 byte-untouched؛ dedicated 79/79 (×2 تکرار مستقل)؛ رگرسیون کامل 1316/1317 (۱ flake ثبت‌شدهٔ از پیش موجود در suite فروزن WP-7.1 — تفکیک طبق Flake Policy)؛ SMOKE 8-گام cold-start OK (هفدهمین smoke).

---

## WP-11.2 — Adapter / Enrichment (DEFERRED — PO/TM DECISION REQUIRED)

```text
WP ID: WP-11.2 | Phase: P11 | Status: DEFERRED — بدون تعریف کامل WP (فقط Level Index) + تصمیم‌های PO/TM لازم
Owner Role: Product Owner (با ratify Technical Manager)
```

**Goal (index-level):** Adapter از Holoo به‌سمت Canonical و Enrichment.

**چرا اجرا نشد (Stop-4):** (۱) تعریف کامل WP/contract/AC در REG-WPR وجود ندارد (فقط Level Index)؛ (۲) اجرای آن مستلزم تصمیم‌های اعلام‌نشدهٔ زیر است که در Baseline/Registerها وجود ندارند: نگاشت فیلد Holoo→Canonical (سابقهٔ DEF6 — نگاشت منبع، جزئیات Adapter است: TM ratify/PO)، source authority (کدام منبع در تعارض حاکم است)، synchronization semantics (pull/push/frequency)، ownership of accounting truth، write-back به Holoo (DEF1 خارج از MVP است)، semantics تسویهٔ enrichment؛ (۳) طبق D-04 مسیر مجاز «Holoo DB → Adapter/Enrichment → Canonical» است ولی Adapter باید به‌سمت Canonical بنویسد و هیچ وابستگی schema/source در لایهٔ Canonical مجاز نیست — طراحی این مرز تصمیم معماری/محصولی جدید است. هیچ policy جایگزینی ساخته نشد و هیچ فرضی جای تصمیم PO/TM را نگرفت.

**Decision Package (2026-10-08 — Mission P12 §5):** `kandoo/specs/WP-11.2-decision-package.md` — ۱۷ قلم تصمیم لازم، هرکدام با classification دقیق (FROZEN / DERIVED FROM EXISTING DECISION / REQUIRES PO DECISION / REQUIRES REAL-HOLOO EVIDENCE) + «کوتاه‌ترین مسیر تصمیم PO». هیچ آیتمی توسط Agent تصمیم‌گیری نشده است؛ WP-11.2 تا پاسخ PO مسدود می‌ماند.

---

## WP-12.1 — Corpus Assembly (Pilot)

```text
WP ID:        WP-12.1
Phase:        P12 — Pilot
Status:       IMPLEMENTED (2026-10-08) | Acceptance: 4/4 AC PASS (REG-AR — در انتظار Acceptance رسمی PO) | Tasks: 4/4 DONE (T-12.1.1..T-12.1.4 ✅)
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** سازوکار مونتاژ Corpus پیلوت — تولید قطعی، برچسب‌گذاری صریح، و ذخیره‌سازی دائمیِ مواد آزمون/پیلوت SYNTHETIC با ground-truth labels اعلام‌شده، به‌عنوان ورودی کالیبراسیون (D-07/D-08/DEF2). هیچ مقداری وارد دامنهٔ تولیدی نمی‌شود؛ هیچ آستانه‌ای ratify نمی‌شود.

**Scope:**
- قالب‌های declared (generator) با entropy قطعی مبتنی بر S1 (بدون random/hashlib/زمان) — سه قالب v1: clean (بدون gross چاپ‌شده — مسیر derivation) / rounding-probe (gross چاپ‌شده با residual ±1-2 سنتی — سطح D-08) / review-probe (tax غایب — مسیر uncertainty)
- نشانی‌دهی محتوایی: entry_fingerprint و corpus_version_id = manifest fingerprint (محتواجه‌نشده — replay طبیعی D-03)
- Store پروژه (SQLite، synchronous=FULL، تراکنش اتمیک کل-نسخه، append-only، VOR، CHECK/UNIQUE، restart-safe، بدون هیچ ستون زمانی — OD-CA-J)
- برچسب‌گذاری مطلق: origin_role = SYNTHETIC_PILOT_FIXTURE + marking دقیق روی هر ردیف (CHECK + service)

**Out of Scope:**
دریافت corpus واقعی (اپراتور/PO) | هر اندازه‌گیری/سوییپ/نرخ (WP-12.2) | هر ratification یا تغییر پارامتر (WP-12.3 — PO/G4؛ D-07/D-08) | اجرای pipeline فروزن | فروش/مشتری/موجودی/Digital Invoice (DEF1/D-06/DEF3/AD-03) | fuzzy (D-05) | باز کردن هر لایهٔ فروزن P1–P11.1

**Inputs:** REG-WPR Phase Index P12 | Mission dispatch P12 (PO، 2026-10-08 — §4 اصول لایهٔ Pilot/Corpus) | D-07، D-08، DEF2، D-09، D-03 | الگوهای WP-11.1/WP-10.1

**Dependencies:** G1 (✅ PASS) | زنجیرهٔ کامل P1–P11.1 (فروزن/IMPLEMENTED — additive-only)

**Deliverables:**
1. `kandoo/specs/WP-12.1-corpus-assembly-contract.md` — SPEC-WP121-CORPUS v1.0-MVP (§1..§11؛ OD-CA-A..J)
2. `kandoo/src/corpus/` — model/generator/store/service/__init__
3. Test Suite اختصاصی (`src/corpus/tests/` — ۴ فایل + conftest؛ ۹۰ تست)
4. Smoke runner: `run_smoke_corpus.py` (هجدهمین smoke — ۸ گام cold-start)
5. به‌روزرسانی Registerها + src/README.md + worklog

**Acceptance Criteria:** (جزئیات در REG-AR)
- AC-12.1.1 — قطعیت مونتاژ: همان (template, count, seed_base) → corpus بایت-یکسان با address محتوایی؛ ×2 تکرار مستقل → replay verbatim صفر-ردیف؛ اعلان متفاوت → address متفاوت
- AC-12.1.2 — برچسب‌گذاری و provenance: هر ردیف با origin_role/marking دقیق؛ ردِ هر origin دیگر (CHECK + service + AST)
- AC-12.1.3 — یکپارچگی و persistence: fingerprint sha256-v1 از طریق S1؛ VOR؛ tamper withhold؛ restart-safe؛ UNIQUE backstops با SQL مستقیم؛ zero-residue در خطای اجباری
- AC-12.1.4 — مرزها: import فقط stdlib+capture؛ هیچ package تولیدی corpus را import نمی‌کند (sweep)؛ clock-free (AST)؛ append-only (AST)؛ vocabulary sweep؛ additive-only — Frozen P1–P11.1 byte-untouched

**Tests:** قطعیت تولید ×2 | پوشش سه قالب + توافق label↔document (شامل variant EURO) | bounds/ورودی خراب/تکراری | persistence/restart | tamper matrix (فلیپ بایت، forged، CHECK با SQL مستقیم، UNIQUE backstops) | replay ×4 | zero-residue | AST probes (بدون random/eval/exec/hash/time-datetime، بدون UPDATE/DELETE، allowlist، sweep تولیدی، clock-free، flake-window avoidance) | vocabulary sweep

**Implementation Record (2026-10-08 — T-12.1.1..T-12.1.4):**
- Scope of record = Phase Index P12 + Mission dispatch P12 §4. قرارداد فقط از سوابق برقرار مشتق شد — هیچ نیازمندی محصولی اختراع نشد؛ D-07/D-08 دست‌نخورده (placeholderها placeholder ماندند).
- پیاده‌سازی additive صرف؛ Frozen P1–P11.1 byte-untouched؛ dedicated 90/90 (×3 تکرار مستقل)؛ SMOKE 8-گام cold-start OK (هجدهمین smoke).

---

## WP-12.2 — Calibration Runs (Pilot)

```text
WP ID:        WP-12.2
Phase:        P12 — Pilot
Status:       IMPLEMENTED (2026-10-08) | Acceptance: 4/4 AC PASS (REG-AR — در انتظار Acceptance رسمی PO) | Tasks: 4/4 DONE (T-12.2.1..T-12.2.4 ✅)
Owner Role:   Backend Dev (implementation) + QA (verification) + Technical Manager (review)
Agent Type:   implementation agents + QA-verification agent
```

**Goal:** اجرای کالیبراسیون — pipeline فروزن (AS-01 تا Gate P6.1) روی corpus تأییدشدهٔ WP-12.1 در workspace ایزوله، مقایسه با labels اعلام‌شده، و صدور ONE deterministic CALIBRATION REPORT (فقط اندازه‌گیری: شمارش‌ها + سوییپ کاندیدهای tolerance D-08). Ratification = WP-12.3 (PO/G4)؛ هیچ آستانه‌ای تغییر نمی‌کند.

**Scope:**
- measured path M1..M9: capture → reconstruct → extract → bind → normalize → derive → validate (۴ rule مرجع) → project (P5.2) → gate (P6.1) — مصرف verbatim سرویس‌های فروزن، بدون بازپیاده‌سازی
- مشاهدهٔ فیلدها: MATCH / MISMATCH / MISSING / UNEXPECTED_PRESENT نسبت به labels
- سوییپ D-08: هر کاندید declared → sub-workspace تازه → rule declared «kandoo-cal-declared-gross-agreement» (R2 tolerated-equality روی gross چاپ‌شده) → شمارش within/beyond/not_evaluable
- گزارش قطعی JSON canonical (بدون wall-clock/uuid/path) + یک اجرا به‌ازای هر workspace (refusal تyped)

**Out of Scope:**
Ratification یا pass/fail نسبت به placeholderها (WP-12.3 — PO/G4) | نرخ/درصد به‌عنوان verdict | P6.2/کالیبراسیون خطی (آینده، corpus واقعی) | fuzzy/candidate (D-05 — WP-8.2/DEF2) | corpus واقعی (اپراتور/PO) | هر دسترسی به store تولیدی | lifecycle act دیجیتال (پیلوت تا Gate می‌سنجد، نه فراتر) | تغییر P1–P11.1

**Inputs:** SPEC-WP121-CORPUS (corpus verified read) | Mission dispatch P12 §4 | D-07/D-08/DEF2/D-09 | AS-01 | الگوهای stack فروزن (ترکیب سرویس‌ها verbatim)

**Dependencies:** WP-12.1 IMPLEMENTED | زنجیرهٔ کامل P1–P11.1

**Deliverables:**
1. `kandoo/specs/WP-12.2-calibration-runs-contract.md` — SPEC-WP122-CAL v1.0-MVP (§1..§11؛ OD-CR-A..G)
2. `kandoo/src/calibration/` — model/stack/runner/__init__
3. Test Suite اختصاصی (`src/calibration/tests/` — ۲ فایل + conftest؛ ۳۳ تست)
4. Smoke runner: `run_smoke_calibration.py` (نوزدهمین smoke — ۸ گام cold-start)
5. به‌روزرسانی Registerها + src/README.md + worklog

**Acceptance Criteria:** (جزئیات در REG-AR)
- AC-12.2.1 — اجرای اندازه‌گیری: pipeline فروزن روی هر entry در workspace ایزوله؛ طبقه‌بندی فیلدها + تصمیم gate هر entry؛ گزارش قطعی (×2 workspace تازه → JSON بایت-یکسان؛ بدون wall-clock/path)
- AC-12.2.2 — سوییپ D-08: کاندیدهای declared → شمارش‌های within/beyond/not_evaluable از طریق engine فروزن با rule declared؛ هیچ کاندیدی تأیید نمی‌شود
- AC-12.2.3 — ایزوله و صفر-اثر: نوشتن فقط داخل workspace؛ corpus store بایت-پایدار قبل/بعد؛ ردِ اجرای مجدد (typed)؛ عدم باز کردن مسیر تولیدی
- AC-12.2.4 — مرزها: بدون import test-helper (AST sweep)؛ import surface اعلام‌شده (pipeline + corpus + capture)؛ گزارش = تنها خروجی؛ بدون ratification/تغییر آستانه؛ additive-only — Frozen byte-untouched

**Tests:** happy-path سه قالب با pinned observations (clean → ACCEPTED + MATCH کامل؛ rounding → REVIEW + sweep texture؛ review → REVIEW + ABSENT matched) | قطعیت گزارش ×2/×3 workspace مستقل | شکل گزارش (بدون uuid/timestamp/path) | echo config | سازگاری شمارش‌ها | re-run refusal | corpus byte-stability | path provenance | AST probes | vocabulary sweep

**Implementation Record (2026-10-08 — T-12.2.1..T-12.2.4):**
- کشف مستند در حین پیاده‌سازی: gate output-present فروزنِ derivation یعنی سند دارای gross چاپ‌شده هرگز DERIVED gross نمی‌گیرد → قالب clean بدون خط gross طراحی شد (مسیر derivation/ACCEPTED) و سطح D-08 در قالب rounding-probe ماند — رفتار فروزن تغییر نکرد؛ طراحی مواد آزمون با آن هم‌راستا شد (REG-AR note).
- dedicated 33/33 (×3 تکرار مستقل)؛ SMOKE 8-گام cold-start OK (نوزدهمین smoke)؛ رگرسیون کامل 1440 جمع‌کل = 1439 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود.

---

## WP-12.3 — Threshold Ratification (DEFERRED — PO/G4 DECISION REQUIRED)

```text
WP ID: WP-12.3 | Phase: P12 | Status: DEFERRED — تصمیم انحصاری PO/G4 (فقط Level Index)
Owner Role: Product Owner (Gate G4)
```

**Goal (index-level):** Ratification رسمی آستانه‌های دقت (D-07: 99.9% / 99% / 50–70%) و پارامتر tolerance (D-08) و ماتریس عملیاتی REVIEW (DEF2) بر اساس شواهد Pilot.

**چرا اجرا نشد (Stop-2 — تصمیم PO):** خودِ نام WP در Phase Index «(PO/G4)» است — ratification یک تصمیم محصولی صریح است که فقط PO می‌تواند انجام دهد؛ هیچ Agent/WP مجاز نیست مقدار آستانه‌ای را ratify کند (D-07: «هیچ WP قبل از P12 مجاز نیست این اعداد را به‌عنوان target مهندسی بنویسد» — و پس از P12 نیز ratification در G4 است). ورودی‌های اندازه‌گیریِ لازم توسط WP-12.2 فراهم شد (report فقط شمارش)؛ نکتهٔ تصمیم‌سازی برای PO: شواهد فعلی SYNTHETIC است (corpus برچسب‌خورده) — ratification نهایی روی corpus واقعی طبق D-07 («با Corpus واقعی و Pilot») تصمیم PO است؛ دو مسیر: (الف) ratification آزمایشی/مشروط روی شواهد synthetic، (ب) تهیهٔ corpus واقعی توسط اپراتور/PO و سپس ratification. هیچ policy جایگزینی ساخته نشد.
