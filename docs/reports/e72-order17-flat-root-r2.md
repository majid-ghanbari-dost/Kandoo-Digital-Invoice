# گزارش اصلاح دوم E-72 — Canonical Invoice v1.2 / ORDER 17

**تاریخ:** 2026-10-12
**نتیجهٔ C# پیش از اصلاح:** `INCOMPATIBLE` در بازبینی اصلاح‌شدهٔ [review 6039821259 در PR #16](https://github.com/majid-ghanbari-dost/Kandoo/pull/16#pullrequestreview-6039821259).
**وضعیت این اصلاح:** بردار و verifier به قرارداد flat-root اصلاح و آزمون شدند؛ پس از ثبت روی شاخهٔ PR #16 می‌توانند دوباره توسط C# بررسی شوند. پذیرش مستقل C# برای نسخهٔ جدید ادعا نمی‌شود.

## حکم و شواهد قرارداد

بازبینی اصلاح‌شده خطای fail-fast را چنین گزارش می‌کند: `SchemaValidationFailed | Unexpected field: base_invoice.` گزارش مقایسهٔ اصلاح‌شدهٔ O17 در [مخزن C#](https://github.com/majid-ghanbari-dost/Kandoo/blob/arena/4bb6cd51-kandoo/docs/reports/E72-CANONICAL-INVOICE-V1-2-O17-CSHARP-COMPARISON-FA.md) و `CanonicalInvoiceConsumer.cs` در همان شاخه، قرارداد ریشه را مشخص می‌کنند: ۱۶ فیلد الزامی، به‌علاوهٔ فقط `issued_content_sha256` به‌عنوان فیلد اختیاری مجاز. مصرف‌کننده ابتدا فیلد ناشناخته را رد می‌کند؛ در نتیجه wrapper قبلی پیش از بررسی فیلدهای اجباری شکست می‌خورد.

این اصلاح حکم را می‌پذیرد، نه اینکه با آن مخالفت کند. محتوای `base_invoice` به ریشهٔ سند منتقل شد و این چهار کلید از ریشه و vector حذف شدند: `base_invoice`, `synthetic_only`, `v1_2_draft_addendum`, `vector_id`. ریشه اکنون دقیقاً همان ۱۶ فیلد الزامی E-11 را دارد:

`schema_version`, `mode`, `invoice_id`, `display_number`, `operation_id`, `device_id`, `public_token`, `store_id`, `customer`, `state`, `state_history`, `line_items`, `summary`, `attention_cells`, `header`, `provenance`.

`issued_content_sha256` در vector لازم نبود و افزوده نشد. `image_sha256` و `template_library_id` فقط در `provenance` باقی ماندند؛ کلید ریشه‌ای برای آن‌ها نساختیم و `RootAllowed` یا قرارداد منجمد C# را تغییر ندادیم. اعتبارسنجی با قرارداد frozen بین‌مخزنی `contracts/canonical_invoice_v0.schema.json` انجام می‌شود؛ قرارداد قدیمی E-01 و schemaهای frozen تغییر نکردند. ضمیمهٔ v1.2 پیش‌نویس مستقل و غیرمصوب است؛ فیلدهای `currency_unit`, `invoice_discount`, `payments`, `walk_in_customer` به این flat v0 vector اضافه نشده‌اند.

## اصلاحات پذیرفته‌شدهٔ دور اول

این سه مورد بدون تغییر حفظ شدند:

- هر line item از `quantity` به `quantity_millis` استفاده می‌کند؛ مقدار داده `1000` است و provenance هم فقط کلید `quantity_millis` با مقدار `captured` دارد.
- چون state برابر `DRAFT` است، `display_number` برابر `null` است.
- `provenance.fields.display_number` برابر `unavailable` است.

## شواهد بایتی و آزمون

نسخهٔ قبلی از Git (`e6339a4c97eff6e328a2ba0ece7925c4e1cd9dbd`) به‌صورت root wrapper ثبت شده بود: 1,518 بایت، SHA-256 `4a9f8555fdb29e53ed1d42ba2d5ce50fba8ea181c7cb46bba4596e781ccadf95`، MD5 `1dc1a55dd9814e9434c1abeadd349163`. این byte evidence با خطای wrapper در رأی C# سازگار است؛ رأی اصلاح‌شده مورد اختلاف قرار نگرفت.

Vector flat فعلی، با serialization تعریف‌شده در manifest (UTF-8، JSON فشرده، کلیدهای مرتب، بدون BOM و newline پایانی)، **1,205 بایت** است: SHA-256 `36939192b6d7e5de57c732309272edc5fe6594d79e15b419754eda6afaff14fd`، MD5 `55d5cdbfdcb4a5d4c6417db51cda303d`. Manifest با همین اندازه و SHA-256 پین شد. Verifier اکنون فلت‌بودن ریشه، نبودن چهار کلید ممنوعه، byte profile، hash/اندازه، قرارداد E-11 و قواعد DRAFT/quantity را بررسی می‌کند.

آزمون هدفمند: `PYTHONPATH=src:scripts .venv/bin/python -m pytest -q tests/test_e72_canonical_v1_2_draft.py` → **4 passed in 0.33s**. کل suite: `PYTHONPATH=src:scripts .venv/bin/python -m pytest -q` → **2088 passed in 245.34s**. Verifier: `PYTHONPATH=src:scripts .venv/bin/python scripts/verify_e72_vectors.py` → **PASS**, یک vector synthetic؛ 1,205 bytes و SHA-256 بالا. هیچ raster/تصویر واقعی، OCR یا استخراج مقداری در این اصلاح استفاده نشد.

## پیگیری و محدودیت‌ها

این گزارش و `docs/decisions-made.md` اصلاح دور دوم را مرجع جاری می‌دانند و برداشت ناسازگار گزارش‌های قدیمی‌تر دربارهٔ سازگاری vector قبلی را supersede می‌کنند. تغییرات E-72 و R-009 در یک گروه‌کامیت روی شاخهٔ فعلی نگه داشته می‌شوند؛ tagهای قبلی `o17-E-72` و `o17-PY-T2` دست‌نخورده‌اند. نام tag یکتای این اصلاح `o17-E-72-r2` است؛ tag روی همان گروه‌کامیت و فقط پس از سبزشدن CI قرار می‌گیرد. Push فقط به شاخهٔ PR انجام می‌شود، نه به `main`. PR #16 باز می‌ماند؛ merge، rebase یا close انجام نمی‌شود.
