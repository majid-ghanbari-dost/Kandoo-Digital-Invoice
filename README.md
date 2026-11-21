# فاکتور دیجیتال کندو — مخزن Python

## ساختار مخزن

```text
.github/workflows/  CI تست Python و بسته‌بندی Windows
contracts/          قراردادها و نمونه‌های قراردادیِ versioned
deliveries/         گزارش‌ها و شواهد اجرای کارها
docs/               راهنمای فنی، مرزهای سامانه و گزارش‌ها
registers/          ثبت تصمیم، ریسک، وظیفه و پذیرش
schemas/            JSON Schema و نمونه‌های versioned
scripts/            harnessها، verifierها و ابزارهای محلی
specs/              قراردادها و طرح‌های Work Package
src/                بسته‌های Python برای پردازش/سرویس‌های پروژه
tests/              تست‌ها و fixtureهای بسته‌شده
```

> ساختار جریان داده، نقش بسته‌های اصلی و دستورهای harness دقت در
> [راهنمای فنی Python](docs/E-39-python-technical-map.md) آمده است. این راهنما
> مسیر image-extraction را از pipeline پایدار capture-to-canonical جدا می‌کند.

## پروتکل حاکم برای همه Agentها

1. **منبع کار:** Agent فقط از `Registers + Frozen Baseline + Work Package + Task` کار می‌کند. Architecture دیگر محل کار روزمره Agent نیست.
2. **Cold-Start:** هر Task باید بدون دسترسی به گفتگوها یا حافظه Agentهای قبلی قابل اجرا باشد. هر ارجاع = مسیر فایل یا شناسه رکورد.
3. **STOP Protocol:** اگر در حین اجرا به تصمیمی برخورد شد که در Baseline یا Registerها وجود ندارد:
   `STOP → Issue Report → Technical Manager Review → PO Decision (if required)` — و هرگز خودِ Agent آن را به Architecture تبدیل نمی‌کند.
4. **Mمنوعات همیشگی:** انتخاب OCR/VLM، انتخاب Database در سطح معماری، طراحی API/UI، اجرای Migration/Schema، بررسی اجرایی Holoo DB، باز کردن اقلام Deferred، ایجاد تصمیم معماری جدید.
5. **گزارش‌دهی:** هر Task با قالب استاندارد Reporting Format خود بسته می‌شود و وضعیتش در Task Register و Acceptance Register ثبت می‌گردد.
6. **Implementation Detail:** جزئیات اجرایی داخل Scope Task با مجوز صریحِ همان Task حل می‌شوند و در گزارش ذیل «Delegated Implementation Detail Decisions» اعلام می‌شوند؛ معماری متوقف نمی‌شود.

## وضعیت Gateها

| Gate | وضعیت |
|---|---|
| G1 Architecture Approval | ✅ PASS — PO Baseline را تأیید کرد |
| G2 Work Package Approval | ✅ PASS — 2026-10-01 (WP-1.1 approved؛ T-1.1.1 DONE) |
| G3 Phase Exit (P1) | ✅ PASS — 2026-10-01 (TM dispatch)؛ شواهد: WP-1.1 IMPLEMENTED + 8/8 AC PASS (REG-AR) + 54/54 tests + SMOKE OK؛ Risk review: RSK-3 → MITIGATED، هیچ blocker؛ P2 فعال شد — WP-2.1 decomposed (T-2.1.1..T-2.1.4) |
| G4 Pilot Acceptance | — |
| G5 Release Readiness | — |
