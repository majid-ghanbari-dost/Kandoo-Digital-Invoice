# E-42 — دقت و مسیردهیِ layoutهای synthetic

## دامنه و داده

این تسک فقط rasterهای E-41 را به‌کار می‌گیرد. اسکریپت `scripts/run_e42_synthetic_accuracy_harness.py` در هر اجرا دو مجموعه را با seedهای جداگانه تولید می‌کند؛ Glyph templateها فقط از هشت تصویر آموزشی synthetic ساخته می‌شوند و هشت تصویر seed دیگر برای ارزیابی held-out می‌مانند. شناسه و SHA-256 ورودی‌ها در JSON گزارش ثبت می‌شود و leakage guard موجود نیز مسیر/SHA templateهای آموزشی را با تصاویر ارزیابی مقایسه می‌کند. تصاویر و templateها در پوشهٔ موقت ساخته می‌شوند و به Git افزوده نمی‌شوند. هیچ fixture فاکتور واقعی، template bank پیش‌فرض، ورودی Holoo، دادهٔ مشتری یا سرویس شبکه‌ای خوانده نمی‌شود.

## سنجه و قواعد گزارش

هر فاکتور ارزیابی، بر اساس خروجی واقعی pipeline، با یکی از routeهای `EXTRACTED`، `REVIEW` یا `BLOCKED` گزارش می‌شود. این‌ها routeهای محلی E-42 هستند؛ `EXTRACTED` معادل E-02 `AUTO_CANDIDATE` است و به معنی ساخت یا تغییر state در Canonical Invoice نیست؛ harness عمداً هیچ Canonical Invoiceای نمی‌سازد. شمارش فیلدهای عددی نیز جداگانه برای همین سه وضعیت ارائه می‌شود. expected valueها از manifest مولد E-41 گرفته می‌شوند؛ مقدارهای `EXTRACTED` با آن‌ها مقایسه می‌شوند و هر اختلاف، از جمله مقدار استخراج‌شدهٔ بدون برچسب، `EXTRACTED-but-wrong` است. شرط پذیرش: صفر مقدار `EXTRACTED-but-wrong`، حداقل یک مقایسهٔ واقعیِ مقدار استخراج‌شده، استفادهٔ کامل از سلول‌های آموزشی، و موفقیت دو کنترل REVIEW است. دقت شرطی بر فیلدهای واقعاً `EXTRACTED` گزارش می‌شود؛ پوشش استخراج نسبت به همهٔ فیلدهای مورد انتظار نیز جداگانه نشان داده می‌شود تا دقت شرطی با پوشش اشتباه نشود. برای هر profile، شمار فاکتورها و فیلدهای E/R/B گزارش می‌شود.

Thresholdها تغییر یا تنظیم نمی‌شوند. حداقل پوشش استخراج تعیین نشده است؛ بنابراین شمارش‌ها بدون ادعای نرخ تعمیم به اسناد واقعی منتشر می‌شوند. نتیجهٔ این تست به کیفیت واقعی فاکتور، Holoo، فروشگاه دیگر یا کیفیت چاپ تعمیم داده نمی‌شود.

## کنترل‌های ایمنی

- شناسهٔ profile ناشناخته با exact-ID evaluator و guard خود harness آزمایش می‌شود و باید پیش از استخراج به `REVIEW` برود. این کنترل وارد denominator دقت OCR نمی‌شود.
- کنترل geometry کم‌اطمینان از یک تصویر E-41 استفاده می‌کند، اما خروجی detector عمداً با یک مرز عمودیِ حذف‌شده شبیه‌سازی می‌شود. pipeline باید `REVIEW` بدهد. این کنترل نیز سنجهٔ طبیعی detector یا accuracy sample نیست.
- اجرای pipeline برای هر فاکتور شناخته‌شده زمان دیواری یک فراخوانی in-process از `_execute_pipeline` را ثبت می‌کند. تولید تصویر، آموزش template، شروع process و نوشتن گزارش در زمان per-invoice نیست. Workflow ویندوز همین گزارش را روی Windows runner می‌سازد و به artifact و Step Summary می‌افزاید؛ زمان محلی Linux جایگزین زمان Windows نیست.

## E-40 — تأیید golden exampleها

درخت commit پذیرفته‌شدهٔ E-40، `dfc2ed41b71751d94f7640c02d7b9312f5e8375b`، دقیقاً شش مسیر دارد:

1. `docs/E-40-canonical-invoice-v1.1-blocked.md`
2. `docs/schemas/v1-1/issued-invoice-v1-1.schema.json`
3. `docs/schemas/v1-1/public-invoice-view-v1-1.schema.json`
4. `src/cloud_contract/__init__.py`
5. `src/cloud_contract/v1_1.py`
6. `tests/test_e40_v1_1_contract.py`

هیچ فایل golden/example مجزایی در این commit group نیست؛ شمار فایل‌های golden/example برابر **صفر** است. تست‌ها داده‌های synthetic را به‌صورت objectهای inline می‌سازند، نه fixture golden نسخه‌دار.

دلیل ثبت‌شده برای نساختن golden کاملِ public-view، نبود schema پایهٔ v1.0 در این checkout است؛ E-40 فقط مرز propertyهای افزایشی و Python preflight را آزمود و اعتبارسنجی کامل public view/cross-stack به‌عنوان مرز پذیرفته‌شده deferred ماند. بنابراین golden ساختگی یا schema پایهٔ حدسی اضافه نمی‌شود و tag پذیرفته‌شدهٔ `w11-E-40b` دست‌نخورده می‌ماند.

## اجرا و خروجی

```sh
PYTHONPATH=src:scripts python scripts/run_e42_synthetic_accuracy_harness.py \
  --report-json /tmp/e42-synthetic.json \
  --report-md /tmp/e42-synthetic.md
```

JSON شامل شمارش‌های per-layout/per-invoice، hash ورودی‌ها، کنترل‌های REVIEW، محیط اجرا و زمان هر فاکتور است؛ Markdown به فارسی برای CI Summary ساخته می‌شود. خروجی‌های metric جزو source tree نیستند و هر CI اجرا artifact مستقل خودش را دارد. یادداشت قدیمی `E-42-accuracy-harness-blocked.md` صرفاً سابقهٔ blocker قبلی است؛ GO مدیر و دامنهٔ synthetic-only حاضر بر آن مقدم‌اند.
