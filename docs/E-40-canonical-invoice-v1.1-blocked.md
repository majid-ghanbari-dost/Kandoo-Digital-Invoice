# E-40 — پشتیبانی Canonical Invoice v1.1

**وضعیت: BLOCKED — بدون پیاده‌سازی**

## مبنا

در checkout فعلی، جست‌وجوی `docs/`, `specs/`, `contracts/`, `schemas/`, `src/` و `tests/` هیچ schema یا قرارداد هنجاری برای Canonical Invoice v1.1 پیدا نکرد. قراردادهای موجود Canonical به v0 محدودند: `schemas/canonical_invoice_v0.json` و `contracts/canonical_invoice_v0.schema.json`. ارجاع‌های «v1.1» در لایهٔ Capture Record به قرارداد دیگری مربوط‌اند و مشخصهٔ Canonical Invoice نیستند.

`docs/E-37-layout-survey.md` زیر بخش «افزونه‌های اختیاری پیشنهادیِ v1.1» نام‌هایی مانند `customer_name` و `payments[]` و مفهوم واحد پول/مانده را مطرح می‌کند، اما همان بخش صریحاً نوع و قواعد تازه‌ای تعریف نمی‌کند. `docs/E-38-onboarding-v2-feasibility.md` نیز پیوند نهایی manifest به شکل‌های اختیاری v1.1 را `UNCONFIRMED` ثبت می‌کند. این پیشنهادها مبنای کافی برای تعیین نوع، الزام/اختیار، provenance، اعتبارسنجی، lifecycle یا سازگاری نیستند.

## تصمیم و گام رفع blocker

بدون مرجع هنجاری، افزودن schema، validator، migration، نمونهٔ تأییدشده یا تغییر خروجی v0 مستلزم حدس دربارهٔ قرارداد است؛ بنابراین E-40 پیاده‌سازی نمی‌شود و خروجی/رفتار v0 دست‌نخورده می‌ماند. برای بازگشایی، مرجع مصوب Canonical Invoice v1.1 باید نسخه و منشأ مشخص داشته و fieldها، نوع و قواعد هر field، optionality، provenance، lifecycle/validation، سازگاری با v0 و نمونه‌های معتبر را تعیین کند. تا دریافت و ثبت آن مرجع، وضعیت **BLOCKED** باقی می‌ماند.
