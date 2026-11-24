# گزارش E-72 — پیش‌نویس افزایشی Canonical Invoice v1.2 — ORDER 16

| task | branch | full SHA | CI run URL | result | artifact names |
|---|---|---|---|---|---|
| E-72 | `arena/d0587e71-kandoo-digital-invoice` | verification/tag commit `f99ab20f0d39b5e4a293d1c3bce9413d9b77d791` (`o16-E-72`)؛ پیاده‌سازی در `b494fa84237e4bc58b43e0ad48917b0c14fa5f7d` | push: [Python 44994331602](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331602), [full ORDER 16 harness 44994331598](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331598), [Windows 44994331615](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331615); PR: [44994335316](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335316), [44994335259](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335259), [44994335282](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335282) | **COMPLETE — draft only.** Addendum, synthetic byte vector, manifest, independent verifier and tests are green. No frozen contract changed; this is not runtime/migration approval. | `order16-python-harness-f99ab20f0d39b5e4a293d1c3bce9413d9b77d791`, `kandoo-extract-windows-f99ab20f0d39b5e4a293d1c3bce9413d9b77d791`, `windows-onefolder-44994331615` (API: unexpired) |

## شواهد بردار مصنوعی

- یک vector ساختگی، 1505 بایت؛ SHA-256: `0885c7571fb3ccc781f1a73e5505cd94805b065fb13e93f35fa4feb12d061d36`.
- verifier، بایت‌های دقیق، طول/hash پین‌شده و اعتبارسنجی schema را در harness source و Windows تأیید می‌کند. اجرای full harness در commit بالا و verifier Windows سبز شدند؛ artifact summary و Windows bundle موجود و unexpired هستند.
- دامنهٔ draft: cheque، تخفیف سطح فاکتور با provenance و پرچم nullable walk-in؛ جمع/محاسبه/آشتی مبلغ یا ادعای مالیاتی/حقوقی تعریف نمی‌کند.

## محدودیت و وضعیت

فایل‌های Canonical v1.2 فقط افزایشی‌اند؛ پیش‌نویس غیرمصوب است و قرارداد frozen، مصرف اجرایی یا migration نیست. بردار کاملاً synthetic است و حاوی نمونهٔ واقعی نیست. تگ یکتای `o16-E-72` پس از سبزشدن CI روی SHA جدول ساخته شد. PR #16 تجمیعی، open و create-only باقی است؛ merge انجام نشده.

## پیگیری ORDER 17 — اصلاح بردار برای بررسی C# (2026-10-12)

- بازبینی فایل `CanonicalInvoiceConsumer.cs` در commit `26d8806` نشان می‌دهد دو فیلد `image_sha256` و `template_library_id` در ریشهٔ `base_invoice` نبودند؛ فقط زیر `provenance` قرار دارند و خودِ `ValidateProvenance` آن‌ها را مجاز و الزامی می‌داند. بنابراین آن‌ها در provenance حفظ شدند؛ ادعای گزارش C# دربارهٔ unexpected root fields با ساختار وکتور تطبیق نداشت. هیچ تغییری در `RootAllowed` داده نشد.
- دو ناسازگاری تأییدشده اصلاح شدند: `quantity` به `quantity_millis` در داده و provenance تغییر کرد (مقدار `1000` یعنی 1.000 واحد)؛ مقدار DRAFT به `display_number=null` و provenance به `unavailable` تغییر یافت.
- verifier از قرارداد منجمد E-11 بین‌مخزنی در `contracts/canonical_invoice_v0.schema.json` استفاده می‌کند. شِمای E-01 در `schemas/canonical_invoice_v0.json` و هر دو قرارداد منجمد دست‌نخورده‌اند.
- manifest جدید: `1518` بایت، SHA-256 برابر `4a9f8555fdb29e53ed1d42ba2d5ce50fba8ea181c7cb46bba4596e781ccadf95`. verifier PASS، آزمون هدفمند E-72 `4 passed` و full ORDER 16 synthetic harness `2088 passed in 229.65s`.
- بازبینی مجدد C# برای وکتور اصلاح‌شده از PR #16 درخواست می‌شود؛ نتیجهٔ پذیرش C# تا پاسخ مستقلِ مصرف‌کننده ادعا نمی‌شود.
