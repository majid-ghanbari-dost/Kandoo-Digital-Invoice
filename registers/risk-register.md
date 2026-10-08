# Risk Register — Kandoo Digital Invoice

```text
Register ID:  REG-RR | Version: 1.0 | Date: 2026-10-01 | Owner: Technical Manager | Approver: Product Owner
Rule:         فقط ریسک‌های واقعی و فعلی. هر ریسک باید Mitigation فعال داشته باشد. بازبینی در هر Gate G3.
Status:       OPEN / MITIGATED / CLOSED
```

| Risk ID | Description | Impact | Likelihood | Owner Role | Mitigation | Status |
|---|---|---|---|---|---|---|
| RSK-1 | تفسیر اشتباه اعداد کالیبراسیون (99.9% / 99% / 50–70%) به‌عنوان target مهندسی پیش از Pilot، که اولویت‌های پیاده‌سازی P3–P5 را منحرف می‌کند | High | Medium | Technical Manager | ثبت D-07 در Decision Register؛ تکرار Forbidden Action در همه WP/Taskها تا Ratification در G4 | OPEN |
| RSK-2 | عدم commit شدن اسناد Baseline به ریپو — Traceability فعلاً به Decision Register (بازنمایی متنی) متکی است؛ ریسک واگرایی با شناسه‌های legacy [D#] در آرشیو | Medium | Medium | Technical Manager / PO | Decision Register به‌عنوان SSOT موقت (MNT-1)؛ commit اسناد در kandoo/baseline/ و Reconciliation شناسه‌ها در اولین فرصت پیش از G3 فاز P1 | [G3 review 2026-10-01: Missing Input — اسناد Baseline در repo موجود نیستند؛ G3-blocking ارزیابی نشد (ریسک traceability مستندات است، نه صحت محصول؛ SSOT موقت = REG-DR طبق MNT-1). Carried into P2 — commit باید پیش از G3 فاز P2 انجام شود] | OPEN |
| RSK-3 | انتخاب ضعیف الگوریتم fingerprint در T-1.1.3 (تفویض‌شده به‌عنوان implementation detail) می‌تواند idempotency سطح Capture را با false hit/miss تضعیف کند | High | Low | Backend Dev + Technical Manager | قید قطعیت و حساسیت به محتوا در AC-1.1.2 (property + mutation test)؛ الزام اعلام الگوریتم در گزارش Task و بازبینی TM | [G3 review 2026-10-01: شواهد mitigation — AC-1.1.2 PASS (determinism + mutation + known-vector)؛ sha256-v1 اعلام و تأیید TM شد؛ residual → WP-1.2 (معوق)] | MITIGATED |
| RSK-4 | Scope creep ایجنت‌ها به نواحی Deferred (DEF1–DEF6) یا تصمیم‌گیری معماری در حین اجرا | High | Medium | Technical Manager | Forbidden Actions در هر Task؛ Deferred Register؛ پروتکل STOP → Issue Report → TM Review → PO Decision در README | OPEN |
| RSK-5 | پیاده‌سازی زودهنگام مقادیر retention/privacy در WP-1.3 در حالی که سیاست مصوب ندارد (DEF4) | Medium | Medium | PO / Backend Dev | Scope مربوط به WP-1.3 فقط mechanics پارامتریک است؛ هر مقدار سیاست با placeholder پارامتریک و برچسب «pending DEF4» | OPEN |

```text
G3 Review — 2026-10-01 (P1 Phase Exit / WP-1.1) — طبق Rule این Register:
- RSK-3 → MITIGATED (شواهد: AC-1.1.2 PASS؛ sha256-v1 اعلام‌شده و تأیید TM؛ residual به WP-1.2 معوق منتقل شد).
- RSK-2 → OPEN، غیربازدارنده برای G3 (Missing Input: اسناد Baseline در repo نیستند؛ REG-DR همان SSOT موقت است — MNT-1)؛ Carried into P2 — commit پیش از G3 فاز P2.
- RSK-1 / RSK-4 / RSK-5 → OPEN؛ mitigation فعال و بدون تغییر؛ هیچ‌کدام G3-blocking نیستند (RSK-5: WP-1.3 dispatch نشده و ریسک فعال نیست).
- نتیجه: هیچ ریسک بازدارنده‌ای برای عبور G3 وجود ندارد.
```
