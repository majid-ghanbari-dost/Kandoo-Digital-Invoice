# نقشهٔ فنی Python برای فاکتور دیجیتال کندو

**دامنه:** نمای راهبریِ ساختار مخزن، دو مسیر دادهٔ Python و اجرای harness دقت E-31. این سند توصیفی است؛ قرارداد جدید تعریف نمی‌کند و رفتار کد را تغییر نمی‌دهد. برای جزئیات هنجاری به `specs/`, `contracts/` و schemaهای مرجع پیوند داده‌شده در بخش‌های زیر رجوع کنید.

## ۱. ساختار مخزن

| مسیر | نقش فعلی |
|---|---|
| `src/` | بسته‌های Python. لایهٔ پایدار شامل `capture`, `reconstruction`, `extraction`, `normalization`, `derivation`, `validation`, `validation_domain`, `canonicalization` و `canonical_assembly` است؛ `pipeline/` آن‌ها را به‌ترتیب هماهنگ می‌کند. |
| `src/image_extraction_adapter/` | استخراج محلی از تصویر، adapter/CLI و pipeline تصویری E-02؛ جدا از `src/pipeline/`. |
| `src/e05_template_bank/`, `src/e06_onboarding_verdict/`, `src/e08_new_type_flow/` | بانک template چیدمان E-05، verdict ورود فروشگاه E-06 و تشخیص/بازبینی نوع جدید E-08. |
| `src/digital_invoice/`, `src/issuance/`, `src/identity_resolution/`, `src/product_candidate/`, `src/customer_linking/`, `src/duplicate_flows/` | اجزای دامنه، lifecycle و issuance جداگانه؛ `PipelineService` آن‌ها را فراخوانی نمی‌کند. |
| `src/corpus/`, `src/calibration/` | ورودی synthetic و گزارش‌گیری اندازه‌گیری در لایهٔ pilot؛ corpus وابستگی production نیست. |
| `src/holoo_spike/` | ابزار WP-11.1 برای گزارش منبع SQLite با guardهای read-only؛ مرحله‌ای از `PipelineService` نیست. |
| `tests/`, `tests/fixtures/` | تست‌ها و fixtureهای بسته‌شده؛ harness E-31 تصویرهای top-level و برچسب‌های `tests/fixtures/real/` را مصرف می‌کند. |
| `scripts/` | verifierها، smoke runnerها و ابزارهای اندازه‌گیری، از جمله `run_e31_accuracy_harness.py`. |
| `docs/`, `specs/`, `registers/` | راهنما/گزارش، مشخصه‌های Work Package و ثبت‌های تصمیم/پذیرش/ریسک. |
| `contracts/`, `schemas/` | artifactها و schemaهای قراردادی؛ schemaی Canonical Invoice v0 در `schemas/canonical_invoice_v0.json` و توضیحش در [`docs/canonical-invoice-v0.md`](canonical-invoice-v0.md) است. |
| `.github/workflows/`, `deliveries/` | تنظیمات CI و گزارش‌ها/شواهد اجرای کارها. |

## ۲. دو مسیر دادهٔ متمایز

### الف) ترکیب پایدار capture-to-canonical

نقطهٔ ورود نمونه‌ای `PipelineWorkspace` و `PipelineService` در `src/pipeline/` است. caller صفحه‌های bytes مرتب، منشأ، bindingهای هویت/ردیف، و نسخهٔ قواعد اعتبارسنجی را صریح می‌دهد. ترتیب orchestrator:

```text
ordered pages
  → capture aggregate/ingest + verified capture read
  → reconstruction (verified source read + durable-page verification)
  → extraction + evidence binding
  → normalization → derivation → declared validations
  → validation-domain projection → canonicalization gate
  → canonical assembly/read/trace (فقط پس از پذیرش gate)
```

`PipelineWorkspace` سرویس‌ها و مخازن محلی هر مرحله را می‌سازد؛ `PipelineService` نتایج هر مرحله را حفظ می‌کند. مرحلهٔ `reconstruct` خودش منبع را با read معتبر می‌خواند و bytes صفحات پایدار را پیش از تکمیل بررسی می‌کند؛ orchestrator پس از آن `read_document` جداگانه‌ای اجرا نمی‌کند. `PipelineStopped` همان نتیجهٔ upstream را برمی‌گرداند و `PipelineExecutionError` خطای اجرایی را با مرحله ثبت می‌کند؛ شکست بین چند مخزن rollback سراسری ایجاد نمی‌کند. `PipelineCompleted` به معنی ساخت/خواندن/ردیابی Canonical invoice در این مسیر است، نه ارسال یا صدور آن. جزئیات اجرا در `src/pipeline/service.py` و `src/pipeline/workspace.py` است.

### ب) استخراج محلی از تصویر

مسیر `src/image_extraction_adapter/pipeline_v0.py` تصویر raster را محلی می‌خواند، layout را تشخیص می‌دهد، سلول‌های عددی را با classifier/Glyph بررسی می‌کند، gate حسابی را اعمال می‌کند و crop/dHash را به‌صورت خوشه‌های بصریِ توصیف کالا گزارش می‌دهد؛ این خوشه‌ها نام متنی کالا تولید نمی‌کنند. نتیجه می‌تواند `AUTO_CANDIDATE`, `REVIEW` یا `REJECT` باشد؛ با context صریح caller امکان ساخت نامزد Canonical Invoice v0 وجود دارد. این مسیر جدا از `PipelineWorkspace` است: خودش مخزن پایدار، صدور یا اتصال شبکه‌ای ایجاد نمی‌کند و `AUTO_CANDIDATE` برابر با پذیرش/صدور نیست. شرح رفتار در [`docs/pipeline-v0.md`](pipeline-v0.md) و مرز CLI در [`docs/extraction-bridge/cli-surface-v1.md`](extraction-bridge/cli-surface-v1.md) است.

`onboard build` از ورودی‌های صریح بانک E-05 می‌سازد؛ `onboard verdict` نتیجهٔ E-06 را در artifact جداگانه می‌نویسد؛ `onboard register-type` از E-08 استفاده می‌کند و نامزدش از بانک فعال جدا و در وضعیت `PROPOSED` می‌ماند. این فرمان‌ها pipeline پایدار را اجرا یا invoice صادر نمی‌کنند؛ currency در مسیر build صریح است و تبدیل خودکار ارز انجام نمی‌شود. مرجع هر جزء: [`E-05`](E-05-template-bank-algorithm.md)، [`E-06`](E-06-onboarding-verdict.md)، [`E-08`](E-08-new-invoice-type-flow.md).

## ۳. اجرای harness دقت E-31

Harness در `scripts/run_e31_accuracy_harness.py` ابتدا همان E-30 golden pack را verify می‌کند؛ سپس برای fixtureهای 29، 31، 32 و 33 چهار fold از leave-one-invoice-out اجرا می‌کند، هر بار با ساخت template از سه invoice دیگر و کنترل نشت منبع/تصویر مشتق‌شده. پس از آن پنج اجرای تازهٔ `--help` را برای startup و اجرای CLI روی هر fixture را برای زمان هر run اندازه می‌گیرد. برچسب‌های مرجع از `tests/fixtures/real/labels.json` خوانده می‌شوند و inventory تصاویر با آن تطبیق داده می‌شود. در LOO، routeهای `AUTO_CANDIDATE`, `REVIEW`, `REJECT` به‌ترتیب `EXTRACTED`, `REVIEW`, `BLOCKED` شمرده می‌شوند. زمینهٔ synthetic producer فقط برای اجرای مکانیکی CLI است، نه برای محاسبهٔ دقت LOO.

از ریشهٔ مخزن اجرا کنید (Pillow و `jsonschema>=4.18,<5` باید در محیط نصب باشند؛ Tesseract لازم نیست):

```sh
python scripts/run_e31_accuracy_harness.py \
  --report-json /tmp/e31-accuracy.json \
  --report-md /tmp/e31-accuracy.md
```

برای ارزیابی executable ساخته‌شده، `--exe PATH` را اضافه کنید؛ در غیر این صورت harness از source CLI استفاده می‌کند. کد خروجی صفر و `status=PASS` یعنی شرط‌های خود harness پاس شده‌اند، از جمله نبودن فیلد `EXTRACTED` نادرست. فایل JSON و Markdown شامل inventory، شمار نتیجه‌ها و جدول هر fixture هستند. شمار دقت با ورودی ثابت باید تکرارپذیر باشد؛ زمان‌ها اندازه‌گیری محیط اجرا هستند و نباید انتظار یکسانی داشته باشند. این مجموعهٔ چهار fixture، ادعای پوشش همهٔ چاپ‌ها یا نتیجهٔ عمومی برای فروشگاه‌های دیگر نیست.

CI همین harness را در job `Extraction bridge golden pack / Ubuntu Python 3.11` در [`.github/workflows/python-tests.yml`](../.github/workflows/python-tests.yml) اجرا می‌کند. [`.github/workflows/windows-build.yml`](../.github/workflows/windows-build.yml) آن را روی executable بسته‌بندی‌شده نیز اجرا می‌کند. تست مرزی `tests/test_e31_accuracy_harness.py` مسیر layout ناشناخته را کنترل می‌کند تا نتیجه `REVIEW` بماند و Canonical candidate ساخته نشود؛ اجرای کامل تست‌ها جداگانه با `python -m pytest -q` انجام می‌شود.
