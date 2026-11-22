# گزارش E-73 — پایداری capture — ORDER 16

| task | branch | full SHA | CI run URL | result | artifact names |
|---|---|---|---|---|---|
| E-73 | `arena/d0587e71-kandoo-digital-invoice` | منطق اصلی `2c24ce70f7f89e3db5d1697244c5e71e1c146401`; CI تازهٔ آزمون aggregate/privacy در انتظار push است | baseline integration: [44992804113](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992804113), [44992804023](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992804023), [44992804013](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44992804013)؛ run تازه پس از push ثبت می‌شود | **ACTIVE / PARTIAL**؛ regressionهای ساختگی و aggregate-only گزارش batch سبز محلی‌اند. تأیید چیدمان با نمونهٔ واقعی نزد agent انجام نشده و نباید انجام شود؛ PM-06 دسترسی agent به نمونهٔ واقعی را نمی‌دهد. | baseline: `order16-python-harness-3bdc6481f71d6234c78260bca045105069a57859`, `kandoo-extract-windows-3bdc6481f71d6234c78260bca045105069a57859`, `windows-onefolder-44992804013`; artifactهای run تازه پس از push ثبت می‌شوند |

## وضعیت و محدوده

- `inspect_capture_folder` و `inspect_capture_batch` fail-closed می‌مانند: SPL/PNG/Report صفر‌بایتی یا نامعتبر، job تو‌در‌تو، metadata تکراری و spool ID تکراری به‌طور امن رد یا برای بازبینی نگه داشته می‌شوند؛ هیچ job تکراری برندهٔ خودکار نمی‌شود.
- آزمون‌های عامل فقط fixtureهای ساختگی دارند. آزمون افزوده‌شده، صف ساختگی دارای spool ID تکراری و SPL صفر‌بایتی را از مسیر ابزار محلی می‌گذراند و تأیید می‌کند که کنسول و summary فایل فقط شمارش‌ها و کدهای ساختاریِ allowlist‌شده را نشان دهند؛ نام job، ID، مسیر و payload ظاهر نمی‌شوند.
- نتیجهٔ baseline در commit `3bdc6481f71d6234c78260bca045105069a57859` شامل harness کامل، smoke منبعی/Windows و artifactهای بالا است؛ checkهای push و PR سبز بودند، N-01/N-04 اختیاری skipped شدند. این run، آزمون تازهٔ E-73 که در worktree افزوده شده را شامل نمی‌شود؛ CI آن باید پس از push تأیید شود.
- **محدودیت واقعی:** هیچ نمونهٔ واقعی به agent داده نشده است و دادهٔ واقعی از رایانهٔ مالک خارج نمی‌شود. بنابراین تطبیق parser با ساختار یک capture واقعی هنوز `BLOCKED` است؛ این مورد **deferred نیست** و تا اجرای مالک/تأیید ساختار به‌صورت aggregate-only باز می‌ماند. هیچ درخواست یا مجوز فرضی برای دادهٔ واقعی ثبت نمی‌شود.

## اجرای محلیِ مالک و تفسیر

Captureهای هر job باید در پوشهٔ مستقیم جداگانه باشند: یک فایل `*.spl`، یک `Report.txt`، دست‌کم یک `*.png` و در صورت امتیازدهی، sidecar محلی `expected-fields.local.json` با مقادیر عددیِ تأییدشدهٔ اپراتور. برای قالب sidecar و مراحل نصب محیط به گزارش E-70 مراجعه کنید. داده، sidecar و تصاویر فقط روی رایانهٔ مالک بمانند.

پس از ساخت venv و نصب وابستگی‌های runtime طبق گزارش E-70، از PowerShell در ریشهٔ checkout اجرا کنید؛ فقط `$captures` را به پوشهٔ محلی تغییر دهید:

```powershell
Set-Location C:\Kandoo\Kandoo-Digital-Invoice
$captures = 'C:\Kandoo-Owner-Eval\captures'
.\.venv\Scripts\python.exe tools\local_onboarding_eval.py --capture-root $captures
```

کنسول و `.owner-local\local-onboarding-eval-summary.local.json` فقط outcome، شمار پوشه/job و برچسب، شمارهای `expected/pass/fail/review/missing` برای `quantity`, `line_total`, `payable` و شمار کدهای ساختاری E-73 را دارند. مسیر خروجی و `expected-fields.local.json` در `.gitignore` هستند؛ مسیر ورودی باید بیرون از checkout باشد. هیچ payload، نام، تلفن، مبلغ، تصویر، مسیر، ID یا hash چاپ یا در summary ذخیره نمی‌شود. از خروجی خام extractor استفاده یا آن را ارسال نکنید.

- `PASS` / exit `0`: همهٔ برچسب‌های عددیِ معتبر با نامزدهای `EXTRACTED` تطبیق دارند و هیچ مورد unresolved/issue باقی نمانده است.
- `FAIL` / exit `10`: دست‌کم یک مقدار `EXTRACTED` با برچسب اپراتور نمی‌خواند؛ بررسی فقط محلی انجام شود.
- `REVIEW` / exit `10`: ورودی ساختاری برای بازبینی نگه داشته شده، برچسبی مفقود/نامعتبر است یا خروجی برای تطبیق قطعی کافی نیست؛ کدهای E-73 فقط به‌شکل شمارش نمایش داده می‌شوند.
- `NOT_SCORED` / exit `10`: هنوز هیچ برچسب عددی معتبر برای امتیازدهی وجود ندارد. در این حالت شمار `ready/review` و `capture_issue_counts` همچنان برای triage ساختاری مفیدند؛ نبود امتیاز، PASS نیست.
- exit `30`: مسیر/آرگومان/sidecar نامعتبر یا ناامن بود؛ ابزار پیام عمومی می‌دهد و جزئیات خصوصی را افشا نمی‌کند.

## آزمون ساختگی

```bash
.venv/bin/python -m pytest -q tests/test_e73_capture_robustness.py tests/test_local_onboarding_eval.py tests/test_e70_operator_training.py
```

آخرین اجرای محلی پیش از push: `16 passed in 0.88s` برای مجموعهٔ هدفمند E-70/E-73 و onboarding. اجرای محلی مالک روی نمونهٔ واقعی هنوز انجام نشده است؛ نتیجهٔ ساختگی جانشین آن نیست.
