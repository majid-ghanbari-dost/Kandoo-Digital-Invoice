# گزارش E-70 — ORDER 16

| task | branch | full SHA | CI run URL | result | artifact names |
|---|---|---|---|---|---|
| E-70 | `arena/d0587e71-kandoo-digital-invoice` | در انتظار commit | در انتظار push | **ACTIVE**؛ پیاده‌سازی آموزش آفلاینِ تأییدشدهٔ اپراتور موجود است و ابزار ارزیابی محلیِ aggregate-only در این task افزوده می‌شود. این محیط هیچ فاکتور واقعی نخوانده است. | پس از اجرای CI ثبت می‌شود |

## اجرای مالک روی رایانهٔ خودش

هر job باید پوشهٔ مستقیم و جداگانه داشته باشد؛ داده و sidecar واقعی فقط روی رایانهٔ مالک بمانند:

```text
C:\Kandoo-Owner-Eval\captures\
  job-001\
    capture.spl
    Report.txt
    page1.png
    expected-fields.local.json
  job-002\
    capture.spl
    Report.txt
    page1.png
    expected-fields.local.json
```

در هر `expected-fields.local.json` فقط مقدارهای عددیِ هر صفحه را که اپراتور دستی تأیید کرده است بگذارید؛ نام مشتری، تلفن، شناسهٔ فاکتور و شرح کالا در این فایل وارد نشود. قالب، با جایگزین‌کردن placeholderها:

```json
{
  "schema_version": "o16.owner-confirmed-numeric-fields.v1",
  "pages": [
    {
      "page_index": 1,
      "fields": {
        "line.0.quantity": "<مقدار عددیِ تأییدشده>",
        "line.0.total": "<مبلغِ تأییدشده>",
        "invoice.payable": "<مبلغِ تأییدشده>"
      }
    }
  ]
}
```

فرمان‌های زیر را در PowerShell از ریشهٔ checkout کپی/اجرا کنید؛ فقط مسیر `$captures` را به پوشهٔ محلی خود تغییر دهید:

```powershell
Set-Location C:\Kandoo\Kandoo-Digital-Invoice
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-extractor.txt
$captures = 'C:\Kandoo-Owner-Eval\captures'
.\.venv\Scripts\python.exe tools\local_onboarding_eval.py --capture-root $captures
```

خروجی تجمیعی در `.owner-local\local-onboarding-eval-summary.local.json` ساخته می‌شود؛ این فایل و sidecarهای `expected-fields.local.json` در `.gitignore` هستند. ابزار ورودی واقع‌شده داخل مخزن را رد می‌کند. از خروجی `extract` خام برای گزارش یا اشتراک‌گذاری استفاده نکنید.

## معنی شمارش‌ها و مرز ایمنی

- `pass`: خروجی EXTRACTED دقیقاً با برچسب عددیِ دستی‌تأییدشده برابر است؛ `fail`: خروجی EXTRACTED با آن برابر نیست؛ `review`: خروجی موجود است اما extractor آن را تأیید نکرده یا چندنامزد است؛ `missing`: برای فیلدِ برچسب‌خورده نامزدی وجود ندارد.
- گروه‌های فیلد فقط `quantity`، `line_total` و `payable` هستند؛ خروجی به تفکیک job یا صفحه، مسیر، نام فایل، ID، timestamp، هش، مقدار OCR، نام، تلفن یا مبلغ چاپ نمی‌کند. `Capture issue codes` فقط شمار خطاهای ساختاری E-73 است.
- نتیجه فقط مقایسهٔ محلی با برچسب‌های اپراتور است؛ به‌خودی‌خود ادعای دقت واقعی، مجوز پذیرش خودکار یا تأیید baseline نیست. ابزار ارزیابی بانک پیش‌فرض را تغییر نمی‌دهد و یادگیری برخط انجام نمی‌دهد. فرمان موجود `onboard learn` جداگانه و فقط با تصمیم صریح اپراتور از برچسب‌های تأییدشده استفاده می‌کند.
- تمام fixtureها و آزمون‌های agent synthetic هستند. مطابق PM-06، هیچ نمونهٔ واقعی‌ای به agent داده نشده و این گزارش نمونهٔ واقعی را ادعا نمی‌کند؛ اجرای محلی مالک هنوز انجام‌نشده است.
