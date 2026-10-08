# Deferred Decision Register — Kandoo Digital Invoice

```text
Register ID:  REG-DDR | Version: 1.0 | Date: 2026-10-01 | Owner: Product Owner
Rule:         اقلام این Register نواحی مسدودشده پیاده‌سازی هستند. باز کردن هرکدام فقط با تصمیم PO.
              هیچ Agent/WP اجازه ندارد در این نواحی پیاده‌سازی انجام دهد یا تصمیم جایگزین بسازد.
```

| Deferred ID | Topic | Current Status | Why Deferred | Blocked Implementation Area | Decision Owner |
|---|---|---|---|---|---|
| DEF1 | External Invoice → Kandoo Sale | DEFERRED — خارج از MVP؛ جریان External در MVP تا Invoice/Digital Invoice پیش می‌رود | اتصال فاکتور خارجی به Sale یک enrichment آینده است و در Freeze وارد نشد تا مرز دامنه‌ها (AD-02) و مرز Inventory (AD-03) حفظ شود | هر منطقی که از External Capture رکورد Sale بسازد یا موجودی/فروش را از جریان خارجی تغییر دهد | PO |
| DEF2 | Review Operation / Access Matrix | DEFERRED — مکانیزم `REVIEW` در Validation (WP-5.2) ساخته می‌شود؛ ماتریس عملیاتی و دسترسی بعداً | ماتریس «چه کسی، با چه دسترسی، چگونه REVIEW را می‌بندد» تصمیم عملیاتی/سیاستی است و باید با Pilot (P12) کالیبره شود | ابزار REVIEWqueue، نقش‌ها و سطوح دسترسی، SLA بازبینی، قواعد escalation | PO (با پشتیبانی Technical Manager) |
| DEF3 | Automatic Customer Creation | DEFERRED — در External Capture ممنوع (Frozen D-06)؛ مجوز در هیچ جریان دیگری هم تعریف نشده | ریسک آلودگی داده در لحظه Capture؛ deterministic link اول، enrich بعد | هر منطق ساخت خودکار Customer از مسیر Capture/Enrichment؛ مدل‌های merge/dedup مشتری | PO |
| DEF4 | Capture Artifact Retention / Privacy | DEFERRED — مقادیر سیاست (مدت نگهداری، حذف، حریم خصوصی) تعیین نشده | نیازمند calibration سیاستی/حقوقی با داده واقعی؛ mechanics می‌تواند ساخته شود ولی مقادیر نه | مقادیر retention در WP-1.3 (TTL، purge policy)، قواعد privacy artifact، سیاست اشتراک‌گذاری | PO |
| DEF5 | Digital Invoice Presentation | DEFERRED — ارائه/قالب/رندر Digital Invoice به‌صورت صریح به آینده موکول شد | Presentation جزئیات UI/ارائه است و در معماری Frozen وارد نشده (اصل جدایی Architecture از Implementation) | قالب نمایش، رندر، جزئیات کانال‌های تحویل در سطح presentation | PO |
| DEF6 | Modian Field Mapping | DEFERRED — نگاشت فیلدهای Modian تعریف نشده | نگاشت source داخلی جزئیات Adapter است؛ Canonical باید source-agnostic بماند (اصل D-04 نسبت به هر source) | Adapter Modian، enrichment مبتنی بر Modian، هر فرض schema Modian در لایه‌های بالادستی | Technical Manager (Ratify: PO) |
