# O15 — گزارش تحویل و وضعیت پذیرش

**تاریخ:** 2026-10-12 (UTC)

**شاخه:** `arena/d0587e71-kandoo-digital-invoice`

**دامنه:** E-60 تا E-63؛ E-64 شامل به‌روزرسانی handoff و همین گزارش است.

## وضعیت تسک‌ها

| Task | Tag | Commit SHA کامل | CI شاخه / CI تگ | نتیجه پذیرش |
|---|---|---|---|---|
| E-60 | `o15-E-60-fix-1` | `68be0e7c08c264a064bae598b5a3917fe6bf4dd9` | [شاخه: run 44030291494](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44030291494) · [تگ: run 44030430963](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44030430963) | **PASS** — باندل یک‌پوشه‌ای Windows، CLI و golden parity مصنوعی Ubuntu/Windows. |
| E-61 | `o15-E-61` | `595d84120a33fd720b9871dc2a2b3b7715b60570` | [شاخه: run 44033421569](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44033421569) · [تگ: run 44033581850](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44033581850) | **PASS** — evidence sidecar و صف بازبینی آفلاین؛ بدون expected labels، دقت `NOT_SCORED` و `extracted_but_wrong: null`. |
| E-62 | `o15-E-62` | `5a126ae9fb82bef77662ed6dd380638c90612ceb` | [شاخه: run 44035249445](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035249445) · [تگ: run 44035251303](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035251303) | **PASS** — قالب محلی اپراتور، schema، CLI و تست؛ 18 تست focused، verifier موفق و کل suite با `1701 passed`. |
| E-63 | — | — | محلی روی رایانهٔ مالک؛ CI ندارد | **BLOCKED** — capture واقعی مالک در اختیار این checkout نیست؛ دادهٔ واقعی خوانده یا جابه‌جا نشده است. |

> تگ قدیمی `o15-E-60` به commit اولیهٔ E-60 اشاره می‌کند؛ تگ نهاییِ پذیرفته‌شده `o15-E-60-fix-1` است. CIهای جدول واقعاً باز و وضعیت موفق آن‌ها با `gh run view` تأیید شده‌اند.

## جمع‌بندی فارسی

E-60 تا E-62 روی شاخهٔ تعیین‌شده تکمیل، تست، تگ و در CI شاخه و تگ تأیید شدند. E-60 باندل Windows و برابری golden مصنوعی را تثبیت می‌کند؛ E-61 شواهد محلیِ مقدار/اطمینان/ناحیهٔ برش و صف HTML آفلاین را بدون تغییر قراردادهای منجمد اضافه می‌کند؛ E-62 نیز قالب برچسب اپراتور را با `read_correctly` و `corrected_value` فراهم می‌سازد. برچسب‌ها پیش‌فرض خالی‌اند و هیچ یادگیری آنلاین یا به‌روزرسانی Glyph انجام نمی‌شود.

این نتایج **اثبات دقت روی capture واقعی نیستند**: در نبود برچسب مستقل، وضعیت دقت همچنان `NOT_SCORED` است و شمار `EXTRACTED-but-wrong` اثبات نشده. E-63 عمداً مسدود مانده تا مالک باندل تگ‌شده را روی رایانهٔ خودش اجرا کند؛ ورودی، OCR، cropها، خروجی‌ها و برچسب‌های واقعی باید همان‌جا بمانند و نباید در Git، CI، upload یا چت قرار گیرند. پس از اجرا فقط یک خلاصهٔ مجاز و عاری از دادهٔ حساس لازم است. E-65 (STRETCH) آغاز نشده و تا تعیین تکلیف تمام MUSTها شروع نخواهد شد.

## گام بعدی مالک برای E-63

از artifact Windows در [CI تگ E-62](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035251303) استفاده شود. روی Windows، پوشهٔ خروجی تازه‌ای بیرون از repository و پوشهٔ capture ساخته و سپس اجرا شود:

```powershell
$bundle = 'C:\path\to\kandoo-extract'
$capture = 'C:\path\to\private-owner-capture'
$base = Join-Path $env:LOCALAPPDATA 'Kandoo\O15'
New-Item -ItemType Directory -Force -Path $base | Out-Null
$run = Join-Path $base ('run-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $run | Out-Null
$exe = Join-Path $bundle 'kandoo-extract.exe'
& $exe extract --capture-folder $capture `
  --out (Join-Path $run 'capture-folder-result.json') `
  --review-evidence-dir (Join-Path $run 'review-evidence')
$extractExit = $LASTEXITCODE  # 0 ready, 10 review, 20 blocked/reject, 30 error
if (Test-Path (Join-Path $run 'review-evidence\review-evidence-v1.json')) {
  & $exe operator-label-template --evidence-dir (Join-Path $run 'review-evidence')
  $labelsExit = $LASTEXITCODE
}
```

فایل‌های `$run` و ورودی capture را محلی نگه دارید؛ برای تحویل فقط نتیجهٔ کلی/وضعیت اجرا را بدون مقدار OCR، اطلاعات مشتری، تصویر، crop، hash یا فایل برگردانید. توضیح قراردادها در `docs/extraction-bundle-v1.md` و `docs/operator-labels-o15.md` است.
