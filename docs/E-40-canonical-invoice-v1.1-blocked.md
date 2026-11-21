# E-40 — افزونهٔ ثبت‌شدهٔ فاکتور v1.1

**وضعیت: پیاده‌سازی مرجع Python انجام شد؛ اتصال به Cloud واقعی در این checkout وجود ندارد.**

این یادداشت جایگزین وضعیت مسدود تاریخی است. blocker قبلی به‌درستی می‌گفت schema هنجاری در checkout موجود نیست؛ بعداً بستهٔ courier دریافت و اندازه/SHA آن تأیید شد. قراردادهای v0 همچنان frozen هستند و تغییر نکرده‌اند.

## مراجع تأییدشده

- Addendum v1.1: 7,841 bytes؛ SHA-256 برابر با
  `4206c23f18fa4cc2f1f5f216099aec51a3ab6480eabf8af07b16863c0c385e69`.
- `docs/schemas/v1-1/issued-invoice-v1-1.schema.json`: 2,011 bytes؛ SHA-256
  `04af72824d15bd17d01a98604265c39bf8d5d5da8ed11d406fe74a28bd5ad15c`.
- `docs/schemas/v1-1/public-invoice-view-v1-1.schema.json`: 2,174 bytes؛
  SHA-256 `78620a233199dbe191e9c9cf4264a0080aaba744a53e2a820056bf98f4992650`.
- قرارداد Cloud تحویلی فقط برای بررسی مرزها: 58,755 bytes؛ SHA-256
  `6d4f491a84e93803ab61831084713e5fe7209fdbfbc3d22d794037975037663e`.

دو schema به‌صورت additive و byte-identical در مسیرهای مقرر نگهداری می‌شوند؛
آن‌ها و schema/contractهای frozen v0 بازنویسی نشده‌اند.

## رفتار مرجع پیاده‌سازی‌شده

`src/cloud_contract/v1_1.py` قرارداد افزایشی را در مرز Python پیاده می‌کند:

- نسخه فقط از `response_snapshot.response.invoice.invoice_schema_version`
  خوانده می‌شود. نبود marker یعنی v1.0، حتی اگر نام فیلدهای v1.1 حاضر یا
  نامعتبر باشند. marker حاضر فقط وقتی معتبر است که دقیقاً رشتهٔ `"1.1"` باشد.
- برای marker معتبر، چهار فیلد optional با schema تحویلی و پروفایل عدد صحیح
  signed 64-bit اعتبارسنجی می‌شوند: `customer_name`، `payments`،
  `currency_unit` و `remaining_balance`.
- preflight کل batch قبل از برگرداندن هر projection plan اعتبارسنجی می‌کند.
  خطای marker/content به `InvoiceV1_1ValidationError` با نگاشت
  `HTTP 400 / VALIDATION_ERROR / FIX_REQUEST` تبدیل می‌شود؛ در نتیجه caller
  نمی‌تواند از این تابع plan ناقص بگیرد و باید آن را پیش از هر projection
  اجرا کند.
- مقادیر فقط از چهار کلید حاضر کپی می‌شوند؛ کلید غایب اضافه نمی‌شود، `null`
  صریح حفظ می‌شود، marker به public fields نشت نمی‌کند، و مبلغ/واحد/مانده
  تبدیل یا محاسبه نمی‌شود. validator ورودی و `response_snapshot` را تغییر
  نمی‌دهد؛ hash/fingerprint یا projection rules بازنویسی/محاسبهٔ دوباره
  نمی‌شوند.
- batchهای mixed نسخه‌به‌نسخه بررسی می‌شوند. marker در سطح دیگری از snapshot
  نسخهٔ invoice را عوض نمی‌کند.

## مرزهای اثبات و محدودیت

این checkout هیچ Cloud HTTP endpoint، database transaction یا public projection
runtime برای پروتکل replication را شامل نمی‌شود. بنابراین این commit، منطق
reference/preflight و نگاشت خطای قراردادی را می‌آزماید، اما اجرای واقعی پاسخ HTTP
یا rollback پایگاه‌دادهٔ Cloud را ادعا نمی‌کند. مصرف‌کنندهٔ Cloud باید preflight
را پیش از projection، داخل تراکنش واحد، وصل کند؛ خطاهای معمول projection همچنان
باید مسیر `500` موجود در قرارداد را حفظ کنند. این helper خودش entry hash یا batch
fingerprint را نمی‌سازد و نباید جایگزین تأیید آن‌ها شود.

Schema عمومی دارای `$ref` به schema پایهٔ v1.0 است که در این Python checkout
تحویل نشده است. برای همین تست‌ها syntax/schema و قواعد چهار property افزایشی را
سنجیده‌اند، نه کل public view را با جعل schema پایه. مرجع حل‌نشده دست‌نخورده
و بدون حدس باقی مانده است.

## آزمون

تست‌های E-40، schema hash pin، قواعد marker، null/optional، رشته‌های control/DEL،
اعتبارسنجی مقادیر، عدم mutation و preflight کامل batch را پوشش می‌دهند. اجرای محلی
کل مجموعه با Python 3.11.2، pytest 9.2.0، Pillow 13.0.0 و jsonschema 4.26.0
سبز بود: `2035 passed, 138 subtests passed`. تست‌های Canonical Invoice v0 نیز
در همان اجرا گذشتند تا رفتار frozen v0 کنترل شود.

## Delta در O14 — goldenهای synthetic و شکاف‌های Holoo

سه golden افزایشیِ issued-invoice در `docs/schemas/v1-1/examples/` اضافه شدند: نمونهٔ کامل recorded fields، نمونهٔ حداقلی با فیلدهای optional غایب، و نمونهٔ explicit-null. همه synthetic-only هستند و به‌عنوان invoice کاملِ v0 یا دادهٔ مشتری تعبیر نمی‌شوند. `manifest.json` و `tests/test_e40_v1_1_golden_examples.py` اندازه/SHA-256 دقیق هر فایل را pin می‌کنند و JSONها را در برابر schema صادرشده اعتبارسنجی می‌کنند؛ همان hash tests در Ubuntu و Windows اجرا می‌شود.

برای public view همچنان golden کامل ساخته نمی‌شود: schema پایهٔ v1.0 در این checkout وجود ندارد و حدس‌زدن آن مجاز نیست. چک، به‌عنوان payment type، و تخفیف سطح فاکتور نیز شکاف‌های مشاهده‌شدهٔ Holoo هستند؛ در این delta فقط ثبت شده‌اند و به schema یا v1.1 اضافه نشده‌اند.
