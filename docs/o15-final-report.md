# O15 — گزارش تحویل و وضعیت پذیرش

**تاریخ:** 2026-10-12 (UTC)

**شاخه:** `arena/d0587e71-kandoo-digital-invoice`

**دامنه:** E-60 تا E-63؛ E-64 تغییرات handoff/report را ثبت کرده بود. اجرای E-63 در این گزارش ثبت شده است. E-65 هنوز شروع نشده، چون دامنه و معیار پذیرش آن در منابع موجود تعریف نشده است.

## وضعیت تسک‌ها

| Task | Tag | Commit SHA کامل | CI شاخه / CI تگ | نتیجه |
|---|---|---|---|---|
| E-60 | `o15-E-60-fix-1` | `68be0e7c08c264a064bae598b5a3917fe6bf4dd9` | [شاخه: run 44030291494](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44030291494) · [تگ: run 44030430963](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44030430963) | **PASS** — باندل یک‌پوشه‌ای Windows، CLI و golden parity مصنوعی Ubuntu/Windows. |
| E-61 | `o15-E-61` | `595d84120a33fd720b9871dc2a2b3b7715b60570` | [شاخه: run 44033421569](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44033421569) · [تگ: run 44033581850](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44033581850) | **PASS** — evidence sidecar و صف بازبینی آفلاین؛ بدون expected labels، دقت `NOT_SCORED` و `extracted_but_wrong: null`. |
| E-62 | `o15-E-62` | `5a126ae9fb82bef77662ed6dd380638c90612ceb` | [شاخه: run 44035249445](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035249445) · [تگ: run 44035251303](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035251303) | **PASS** — قالب محلی اپراتور، schema و CLI؛ 18 تست focused و suite آن مرحله `1701 passed`. |
| E-63 fix-forward | `o15-E-63-fix-1` | `89f78b2099d0f15d01bbf84bd68cc1a997c754c2` | [شاخه: run 44080880091](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44080880091) · [تگ: run 44081030928](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44081030928) | **اجرای E-63 کامل؛ نتیجهٔ extractor برابر REVIEW است، نه پذیرش AUTO و نه ادعای دقت.** |
| E-65 (STRETCH) | — | — | — | **NOT STARTED** — دامنه و معیار پذیرش در اسناد/Issues/PRهای بررسی‌شده موجود نیست؛ لازم است مالک آن را مشخص کند. |

> تگ قدیمی `o15-E-60` به commit اولیهٔ E-60 اشاره می‌کند؛ تگ پذیرفته‌شدهٔ E-60 `o15-E-60-fix-1` است. CIهای مندرج در جدول برای commitهای متناظر بررسی شده‌اند.

## E-63 — روش، رفع blocker و نتیجه

### ورودی و محدودهٔ نگهداری

- یک پوشهٔ capture ساختگی و غیرحساس، با یک invoice و یک صفحه، بررسی شد؛ هر سه فایل مورد انتظار دقیقاً با اندازه و SHA-256 مرجع تطبیق داشتند. مقادیر واقعی hash/اندازه و فایل‌ها در این گزارش ثبت نشده‌اند.
- شاخهٔ راه‌دور `o15-e63-transfer` با مجوز مدیر اجرایی، پس از اعتبارسنجی، با `git push origin --delete o15-e63-transfer` حذف شد؛ آخرین commit آن `d042001f8827fe591cfa428e859c91ff1846fa45` بود. پس از ناپدیدشدن محیط موقت بین نوبت‌ها، همان commit فقط برای بازیابی ورودی به sandbox از codeload خوانده و سه فایل دوباره تطبیق داده شدند؛ شاخه بازسازی نشد.
- ZIP، ورودی استخراج‌شده و همهٔ JSON/logهای اجرا بیرون از checkout و فقط در sandbox نگه داشته شدند. هیچ دادهٔ capture، مقدار OCR، تصویر، hash یا JSON خام وارد Git، commit، tag یا workflow نشده است.

### اجرای نخست — نتیجهٔ BLOCKED حفظ‌شده

- منبع تگ `o15-E-60-fix-1`، SHA `68be0e7c08c264a064bae598b5a3917fe6bf4dd9`، در Linux با Pillow `11.1.0` اجرا شد.
- خروجی نخست: `BLOCKED / REJECT`, exit code `20`, یک صفحهٔ مسدود، صفر numeric candidate. در stderr خطی نبود؛ JSON نتیجه علت را ثبت کرد.
- blocker: `preprocessing.py:642` فراخوانی `line_mask.get_flattened_data()` داشت، اما این متد در `Pillow 11.1.0` روی `Image` وجود ندارد؛ glyph processing با `AttributeError` متوقف می‌شد. در همان اجرا بانک پیش‌فرض E-05 نیز به fixtureهای canonical/labels مورد انتظار دسترسی نداشت، چون آن فایل‌ها در source تگ موجود نبودند.

### Fix-forward کنترل‌شده

- با حفظ dependency pin `Pillow==11.1.0`، تنها فراخوانی ناسازگار با API هم‌ارز آن نسخه جایگزین شد: `line_mask.get_flattened_data()` → `line_mask.getdata()`. `getdata()` همان مقادیر پیکسل را به‌ترتیب مسطح‌شده برمی‌گرداند؛ منطق حذف خط، شمارش، آستانه‌ها و bankها تغییر نکردند.
- یک تست synthetic افزوده شد که تعداد پیکسل‌های خط حذف‌شده و عدم تغییر تصویر ورودی را بررسی می‌کند. dependency، glyph bank، schema، contract، workflow و golden تغییر نکردند.
- Commit/tag: `89f78b2099d0f15d01bbf84bd68cc1a997c754c2`, `o15-E-63-fix-1`.
- آزمون محلی: **1702 passed**؛ `scripts/verify_o15_e60.py`، شامل parity مصنوعی JSON و sidecarهای E-61/E-62، **PASS**. CI شاخه run `44080880091` و CI تگ run `44081030928` هر دو موفق شدند (Linux و Windows).

### Artifact و provenance

- GitHub برای run تگ E-60 `44030430963`، artifact ID `14305290850` و digest اعلام‌شدهٔ `sha256:60f9baee9b8910d2817878d9777627b60ae3dde275d74cc8263eb53c9d5be083` گزارش کرده است.
- یک تلاش مجدد با API احرازشده نیز با `EOF` هنگام دریافت از Azure Blob پایان یافت و فایل دریافتی صفر بایت بود؛ بنابراین **hash واقعی artifact تأیید نشد**. این مورد mismatch نیست؛ بایت معتبری برای مقایسه دریافت نشد.
- طبق ابلاغ مدیر اجرایی، E-63 قفل artifact نشد و اجرای واقعی از source Linux در SHA جدید و تأییدشدهٔ `o15-E-63-fix-1` انجام شد. باندل Windows به‌عنوان برنامهٔ قابل اجرای Linux استفاده نشد.

### اجرای نهایی و شاخص‌های تجمیعی

- روش اجرا: Linux x86_64، CPython `3.11.2`، Pillow `11.1.0`, jsonschema `4.26.0`; clone موقت source دقیقاً روی tag/SHA بالا. فرمان از نوع `python scripts/demo_capture.py --capture-folder <sandbox>/input/invoice-001 --out-dir <تازه‌ساخته‌شده در sandbox>` بود؛ بدون `--context` و بدون bank خارجی.
- نتیجهٔ فرایند: exit code `10`؛ یک invoice/یک JSON نتیجه/یک صفحه؛ وضعیت invoice و verdict هر دو `REVIEW` (1/1، 100%)؛ `BLOCKED=0`, `ERROR=0`; خطاهای top-level و page هر دو صفر. هر دو فایل JSON خروجی با schema متناظر **PASS** شدند.
- Numeric candidates: **9** (quantity `4`, line_total `4`, payable `1`); هر `9/9` با status `REVIEW` ماندند. توزیع confidence: `[0,25)=0`, `[25,50)=0`, `[50,75)=0`, `[75,100]=9`, `UNSCORED=0`. Confidence histogram سنجهٔ صحت نیست.
- E-06: `REVIEW`, reason codes: `PARTIAL_MATCH`, `NEW_LAYOUT`.
- **Glyph template bank:** فایل پیش‌فرض source بارگذاری شد (17 template در profile `row`, 10 در `payable`); glyph-drift monitor نتیجهٔ `REVIEW` داد. هیچ bank update یا online learning رخ نداد.
- **E-05 layout/template bank:** `UNAVAILABLE`, تعداد template `0`; bank پیش‌فرض به fixtureهای `tests/fixtures/real/canonical` و `tests/fixtures/real/labels.json` نیاز دارد که در تگ وجود ندارند؛ بنابراین E-05 تطبیقی انجام نشد.
- **Accuracy:** `NOT_SCORED`, expected labels در دسترس نبودند و `extracted_but_wrong: null` باقی ماند. یک نمونهٔ ساختگی و بدون برچسب مستقل، دقت یا نمایندگی آماری را ثابت نمی‌کند.

### برداشت و محدودیت

E-63 به‌عنوان اجرای اندازه‌گیری کامل شد، اما خروجی آن **REVIEW** است: نه `AUTO/ACCEPT` و نه ارزیابی صحت. هر 9 candidate نیازمند بازبینی است، با اینکه confidenceهایشان در بازهٔ بالایی قرار گرفته‌اند. وضعیت `NEW_LAYOUT`, نبود E-05 bank قابل استفاده و نبود expected-value labels محدودیت‌های نتیجه‌اند. این گزارش عمداً مقدار OCR، محتوای invoice، تصویر/crop، hash/اندازهٔ capture یا JSON خام را درج نمی‌کند.

## وضعیت E-65

E-65 هنوز شروع نشده است. در handoff، اسناد محلی، Issues و PRهای بررسی‌شده فقط عبارت «Holoo v1.2 stretch» دیده شد؛ task/acceptance criteria قابل اجرا پیدا نشد. برای جلوگیری از scope invention یا تغییر قراردادهای منجمد، پیش از ایجاد tag یا CI لازم است مالک دامنه و معیار پذیرش E-65 را مشخص کند.

## سوابق E-60 تا E-62

E-60 تا E-62 روی شاخهٔ تعیین‌شده پیاده‌سازی، تست، تگ و در CI شاخه و تگ تأیید شدند. برچسب‌های E-62 پیش‌فرض خالی‌اند و هیچ یادگیری آنلاین یا به‌روزرسانی Glyph انجام نمی‌شود. هشدار deprecation مربوط به Node.js 20 در workflowها غیرمسدودکننده بود.
