# گزارش E-70 — ORDER 16

| task | branch | full SHA | CI run URL | result | artifact names |
|---|---|---|---|---|---|
| E-70 | `arena/d0587e71-kandoo-digital-invoice` | implementation/tag commit `3bdc6481f71d6234c78260bca045105069a57859` (`o16-E-70`؛ tag تغییر/جابجا نشده) | push: [Python 44992804113](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992804113), [O15 + full ORDER 16 harness 44992804023](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992804023), [Windows build 44992804013](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992804013); PR checks روی همان SHA: [44992808380](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992808380), [44992808219](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992808219), [44992808257](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992808257) | پیاده‌سازی محلیِ آموزش تأییدشده و evaluator aggregate-only سبز؛ harness، smoke منبع و Windows سبز. **اجرای مالک روی فاکتور واقعی انجام‌نشده**؛ این گزارش ادعای دقت واقعی یا تأیید baseline نمی‌کند. | `order16-python-harness-3bdc6481f71d6234c78260bca045105069a57859`, `kandoo-extract-windows-3bdc6481f71d6234c78260bca045105069a57859`, `windows-onefolder-44992804013` (API تأیید کرد موجود و unexpired) |

## آموزش و ارزیابیِ جدا از هم

جریان آموزش `onboard learn` فقط با تصمیم صریح اپراتور از شواهد محلی و برچسب‌های عددیِ `read_correctly: true` یا اصلاح‌شدهٔ دستی استفاده می‌کند؛ نامطمئن‌ها `REVIEW` می‌مانند. این جریان آفلاین و مستقل از evaluator است و بانک پیش‌فرض را تغییر نمی‌دهد. راهنمای مراحل، دستورها و شرط‌های fail-closed در [`docs/e70-real-invoice-onboarding.md`](../e70-real-invoice-onboarding.md) است. عامل هیچ نمونهٔ واقعی دریافت نکرده است.

Evaluator جدید، خودِ آموزش را اجرا نمی‌کند؛ مالک از آن برای سنجش محلیِ خروجی extractor در برابر برچسب numeric تأییدشده استفاده می‌کند. فایل summary فقط aggregate counts و شمارهای سطح فیلد است. همهٔ fixtureها و تست‌های agent synthetic هستند.

## اجرای evaluator در رایانهٔ مالک

ساختار پیشنهادیِ بیرون از checkout؛ هر job پوشهٔ مستقیم خودش را دارد:

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

در هر `expected-fields.local.json` فقط مقدارهای عددی هر صفحه را که اپراتور دستی تأیید کرده است وارد کنید؛ نام مشتری، تلفن، شناسهٔ فاکتور و شرح کالا در sidecar قرار نگیرد. قالب با placeholderها:

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

PowerShell را در ریشهٔ checkout اجرا کنید؛ فقط `$captures` را به مسیر محلی خود تغییر دهید:

```powershell
Set-Location C:\Kandoo\Kandoo-Digital-Invoice
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-extractor.txt
$captures = 'C:\Kandoo-Owner-Eval\captures'
.\.venv\Scripts\python.exe tools\local_onboarding_eval.py --capture-root $captures
```

summary در `.owner-local\local-onboarding-eval-summary.local.json` ساخته می‌شود. این مسیر و sidecarهای `expected-fields.local.json` در `.gitignore` هستند؛ ورودی واقع‌شده در checkout رد می‌شود. داده، sidecar و تصویر باید فقط روی رایانهٔ مالک بمانند. خروجی خام extractor را گزارش یا share نکنید.

## معنی outcome و شمارش‌ها

- `PASS` / exit `0`: تمام labelهای عددی معتبر با یک نامزد `EXTRACTED` برابرند و مورد ساختاری/برچسبی unresolved باقی نمانده است.
- `FAIL` / exit `10`: دست‌کم یک مقدار `EXTRACTED` با label اپراتور متفاوت است؛ مقدار یا نمونه در خروجی چاپ نمی‌شود.
- `REVIEW` / exit `10`: نامزد نامطمئن/چندگانه، مورد ساختاری، label مفقود یا برچسب نامعتبر نیازمند بررسی محلی است.
- `NOT_SCORED` / exit `10`: هیچ label عددیِ معتبر برای امتیازدهی وجود ندارد؛ به‌معنی PASS نیست.
- `30`: ورودی/آرگومان/sidecar ناامن یا نامعتبر بود؛ ابزار پیام عمومی می‌دهد.
- فیلدها فقط `quantity`, `line_total`, `payable` هستند و به شکل `expected / pass / fail / review / missing` چاپ می‌شوند. کدهای E-73 فقط به‌صورت شمارش می‌آیند. کنسول و summary هیچ payload، مقدار OCR، نام، تلفن، مبلغ، تصویر، مسیر، نام فایل، ID، timestamp یا hash ندارند.

## اعتبارسنجی synthetic و مرز ادعا

- آزمون‌های محلیِ هدفمند در commit E-70: `15 passed in 0.81s`; `py_compile` موفق.
- run `44992804023` گام‌های `Run ORDER 16 full Python harness and E-74 accuracy gate`, `Verify E-70 frozen onboarding with synthetic operator labels`, build و upload artifact را سبز کرد؛ runهای Python و Windows نیز موفق بودند. PR #16 روی آن SHA نیز سبز بود. N-01/N-04 اختیاری skipped شدند.
- `o16-E-70` تگ یکتا روی commit `3bdc6481f71d6234c78260bca045105069a57859` است. PR #16 همچنان تجمیعی، باز و create-only است؛ merge انجام نشده.
- اجرای محلی مالک روی نمونهٔ واقعی هنوز انجام نشده؛ گزارش، CI و artifactها فقط synthetic هستند. نتیجهٔ synthetic، ادعای دقت واقعی، مجوز پذیرش خودکار یا تأیید baseline نیست.
