# Kandoo Digital Invoice — Project Repository

تاریخ Bootstrap: 2026-10-01 | وضعیت: Execution Management (پس از تأیید PO)

## ساختار

```text
kandoo/
├── README.md                       ← همین فایل — پروتکل حاکم
├── baseline/                       ← اسناد Frozen Baseline ( pending commit — see note)
├── specs/                          ← مشخصه‌های سطح WP (مثل Capture Record Contract)
└── registers/
    ├── decision-register.md           ← Single Source of Truth معماری
    ├── deferred-decision-register.md  ← مرز ممنوعیت پیاده‌سازی
    ├── work-package-register.md       ← Roadmap → Work Packages
    ├── task-register.md               ← WP → Agent Tasks (حافظه رسمی پروژه)
    ├── acceptance-register.md         ← AC → Evidence → Acceptance
    └── risk-register.md               ← ریسک‌های واقعی و فعال
```

**Note — Baseline Docs:** سه سند Baseline (Frozen Canonical Invoice v1، Master Architecture، Master Roadmap) به‌علاوه Management Readiness Review باید در `kandoo/baseline/` commit شوند. تا آن زمان، Decision Register بازنماییِ متنیِ معتبر و self-contained تصمیمات Frozen است. پس از commit، ستون Source Document در Registerها باید به مسیر فایل‌ها به‌روزرسانی شود. (غیربازدارنده — Maintenance Note: MNT-1)

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
