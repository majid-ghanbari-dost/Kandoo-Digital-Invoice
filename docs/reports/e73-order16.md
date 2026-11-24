# گزارش E-73 — پایداری capture — ORDER 16

| task | branch | full SHA | CI run URL | result | artifact names |
|---|---|---|---|---|---|
| E-73 | `arena/d0587e71-kandoo-digital-invoice` | `3f931abce392060343729514b3bf97c408d9a5e2` (E-73 regression/report commit؛ منطق اصلی در `2c24ce70f7f89e3db5d1697244c5e71e1c146401`) | [Python push 44993447549](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44993447549), [Windows push 44993447554](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44993447554), [O15/harness push 44993447593](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44993447593); PR-event runs: [44993451066](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44993451066), [44993451046](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44993451046), [44993451131](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44993451131) | **ACTIVE / PARTIAL**؛ هر سه push run و PR run سبز، smokeهای Ubuntu/Windows موفق، آزمون هدفمند محلی `16 passed`. تأیید ساختار واقعی نزد agent انجام نشده و نباید انجام شود؛ طبق PM-06 دادهٔ واقعی به agent داده نمی‌شود و تأیید محلی مالک هنوز لازم است. | `order16-python-harness-3f931abce392060343729514b3bf97c408d9a5e2`, `kandoo-extract-windows-3f931abce392060343729514b3bf97c408d9a5e2`, `windows-onefolder-44993447554` (همه unexpired) |

## وضعیت و محدوده

- `inspect_capture_folder` و `inspect_capture_batch` fail-closed می‌مانند: SPL/PNG/Report صفر‌بایتی یا نامعتبر، job تو‌در‌تو، metadata تکراری و spool ID تکراری به‌طور امن رد یا برای بازبینی نگه داشته می‌شوند؛ هیچ job تکراری برندهٔ خودکار نمی‌شود.
- آزمون‌های عامل فقط fixtureهای ساختگی دارند. آزمون افزوده‌شده، صف ساختگی دارای spool ID تکراری و SPL صفر‌بایتی را از مسیر ابزار محلی می‌گذراند و تأیید می‌کند که کنسول و summary فایل فقط شمارش‌ها و کدهای ساختاریِ allowlist‌شده را نشان دهند؛ نام job، ID، مسیر و payload ظاهر نمی‌شوند.
- CI روی SHA بالا شامل اجرای harness کامل Python و E-74، smoke منبعی Ubuntu، smoke executable Windows، verifierهای O15/E-70/E-72 و build مستقل Windows بود؛ همهٔ required jobs و push/PR checks موفق شدند. N-01 و N-04 اختیاری `SKIPPED` ماندند. API فهرست artifactها را تأیید کرد؛ Windows evidence notice گفت `status=PASS`, `exe_bytes=4201273`, `bundle_bytes=37523819`, `startup_median_s=0.1531` (این سنجه‌ها به E-75 مربوط نیستند). Annotationهای دیگر فقط هشدار deprecation مربوط به Node.js 20 در actions موجود بودند؛ annotation خطای کد نبود.
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

اجرای هدفمند نهایی محلی پس از push: `16 passed in 0.74s`؛ آزمون‌های CI نیز همان harness کامل را اجرا کردند. اجرای محلی مالک روی نمونهٔ واقعی هنوز انجام نشده است؛ نتیجهٔ ساختگی جانشین آن نیست.

## افزودهٔ PY-T2 / ORDER 17 — بازبینی ساختاری و تصحیح خوانش (2026-10-12)

گزارش قبلی ثبت می‌کند که raster ESC/POS پاکت DiagnosticResults با تصویر اصلیِ PO-certified بایت‌به‌بایت یکسان بوده است؛ raw raster در checkout فعلی حاضر نیست و این نوبت تطبیق را مستقل تکرار نکردم. تصویر PO-certified موجود `samples/real-layout-fictional/invoice-34.png` در ناحیهٔ payable بصری `49,547,706` را نشان می‌دهد، در برابر مقدار مبنای ابلاغ‌شدهٔ `49,547,790`. جمع چهار ردیفِ ثبت‌شده `50,051,429` بدون تغییر است؛ بنابراین تفاضل‌های حسابی متناظر `503,723` (از PNG) و `503,639` (از payable ابلاغ‌شده) هستند، و فاصلهٔ ۸۴ ریال منشأاش اختلاف payable است، نه ردیف‌ها. تا PO مقدار مرجع را تأیید کند، هیچ‌یک از دو عدد را با دیگری جایگزین نمی‌کنیم و تخفیف/اصلاح استنتاج نمی‌شود. جدول ردیف‌ها در `docs/reports/py-t2-order17-fa.md` آمده است.

بازبینی aggregate-only پاکت محلیِ Git-ignored:
- `folders_seen=3`, `ready=0`, `review=3` (exit `10`, REVIEW مورد انتظار).
- کدها: `AMBIGUOUS_SPL=1`, `EMPTY_SPL=1`, `JOB_IN_WRONG_FOLDER=1`, `MISSING_PNG=2`, `MISSING_REPORT=1`, `MISSING_SPL=2`.
- یک SPL صفر‌بایتی و دو SPL غیرخالی/دو PNG در جفت‌های تکراری بایت‌به‌بایت یکسان مشاهده شدند؛ پوشهٔ `Unassigned` برای پردازش نگه داشته شد.
- هیچ OCR، استخراج مقداری، CI یا upload روی دادهٔ خام اجرا نشد؛ payload فقط owner-local و Git-ignored ماند.

رگرسیون جدید ساختار **۱۱ فایل/سه پوشه** را با بایت‌های کاملاً synthetic بازسازی می‌کند: duplicate SPL/PNG، SPL صفر‌بایتی، و SHD نابه‌جا در `Unassigned`; هر سه پوشه در REVIEW هستند و شمار کدها با triage aggregate بالا برابر است. آزمون هدفمند E-73/onboarding/capture-folder: **41 passed in 4.91s**؛ full local ORDER 16 synthetic harness: **2088 passed in 229.65s**. E-72 verifier، O15، E-70 smoke و `EXTRACTED-but-wrong=0` برای سه layout ساختگی PASS شدند. این نتایج دقت فاکتور واقعی نیستند و جایگزین label-based scoring نمی‌شوند.

## CI و برچسب ORDER 17

کد و رگرسیون ساختگی E-73 همراه پیگیری PY-T2 در commit `e6339a4` ثبت و با tag یکتای `o17-PY-T2` نشان‌گذاری شد. این tag فقط پوشش **synthetic** را نشان می‌دهد؛ E-73 همچنان **PARTIAL** است و gate بررسی محلیِ ساختار capture توسط مالک باز می‌ماند. نتیجهٔ قبلیِ aggregate-only (۳ پوشه، ۰ ready، ۳ review) gate را نمی‌بندد؛ هیچ payload خام به Git/CI/artifact افزوده نشده و OCR/استخراج مقداری اجرا نشده است.

CI روی SHA کد `e6339a4`: Python [45391144844](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144844)، Windows [45391144767](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144767)، O15/full harness [45391144776](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144776) همگی success شدند. PR #16 اکنون OPEN و `CONFLICTING / DIRTY` با base `main`=`180b279b6c692f841cab739577ad4fedeefb77c3` است. طبق دستور، rebase/merge/close انجام نشده؛ تصمیم PM/PO در [کامنت PR #16](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7132327892) درخواست شده است.
