# O15 — گزارش تحویل، شواهد E-63 و وضعیت پذیرش

**تاریخ:** 2026-10-12 (UTC)

**شاخه:** `arena/d0587e71-kandoo-digital-invoice`

**دامنه:** E-60 تا E-63؛ E-64 ثبت handoff را انجام داد. اجرای E-63 در این گزارش تفکیک و مستند شده است. تگ fix-forward مجوز اصلاح است، نه پذیرش نهایی نتیجه.

## وضعیت تسک‌ها

| Task | Tag | Commit SHA کامل | CI شاخه / CI تگ | وضعیت |
|---|---|---|---|---|
| E-60 | `o15-E-60-fix-1` | `68be0e7c08c264a064bae598b5a3917fe6bf4dd9` | [شاخه: run 44030291494](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44030291494) · [تگ: run 44030430963](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44030430963) | **PASS** — باندل Windows، CLI و parity مصنوعی Ubuntu/Windows. |
| E-61 | `o15-E-61` | `595d84120a33fd720b9871dc2a2b3b7715b60570` | [شاخه: run 44033421569](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44033421569) · [تگ: run 44033581850](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44033581850) | **PASS** — evidence sidecar و صف بازبینی آفلاین. |
| E-62 | `o15-E-62` | `5a126ae9fb82bef77662ed6dd380638c90612ceb` | [شاخه: run 44035249445](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035249445) · [تگ: run 44035251303](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44035251303) | **PASS** — برچسب اپراتور محلی؛ accuracy بدون برچسب مستقل `NOT_SCORED`. |
| E-63 fix-forward | `o15-E-63-fix-1` | `89f78b2099d0f15d01bbf84bd68cc1a997c754c2` | [شاخه: run 44080880091](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44080880091) · [تگ: run 44081030928](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44081030928) | **DELIVERED** — تکلیف مستند شد، نه پذیرش نهایی؛ پذیرش با مالک است. |
| E-65 (STRETCH) | — | — | — | **NOT STARTED** — تعریف مکتوب scope و معیار پذیرش کامل نیست. |

> تگ قدیمی `o15-E-60` به commit اولیهٔ E-60 اشاره می‌کند؛ تگ نهایی E-60 `o15-E-60-fix-1` است. تگ و commitهای قبلی حفظ شده‌اند و بازنویسی تاریخچه انجام نشده است.

## E-63 — شواهد و ارزیابی تفکیک‌شده

### الف) سلامت اجرای فنی و صحت عملکرد استخراج‌گر

**اجرای نخست، پیش از fix-forward:** source تگ `o15-E-60-fix-1` در SHA `68be0e7c08c264a064bae598b5a3917fe6bf4dd9` با Pillow `11.1.0` روی Linux اجرا شد و `BLOCKED / REJECT` با exit code `20` داد؛ یک صفحه مسدود و صفر numeric candidate. علت ثبت‌شده در JSON نتیجه این بود که `src/image_extraction_adapter/preprocessing.py:642` متد `Image.get_flattened_data()` را صدا می‌زد، درحالی‌که این متد در Pillow پین‌شده وجود ندارد. stderr خالی بود. این نتیجهٔ اولیه در این گزارش و handoff حفظ شده است.

**رفع محدود و کنترل‌شده:** در commit `89f78b2099d0f15d01bbf84bd68cc1a997c754c2`، تگ `o15-E-63-fix-1`، فقط فراخوانی `line_mask.get_flattened_data()` به API معادل موجود در Pillow `11.1.0` یعنی `line_mask.getdata()` تغییر کرد. dependency pin، bankها، thresholds، منطق و قرارداد extraction، schema، workflow و golden تغییر نکردند. این یک دور fix-forward از سقف مجاز بود؛ دور دیگری لازم نشد.

تست مشخص `test_line_mask_flattened_pixel_count_uses_pillow_11_1_data_api` با تصویر synthetic فراخوانی اصلاح‌شده را در Pillow `11.1.0` اجرا می‌کند، مقدار مورد انتظار 30 پیکسل خط حذف‌شده را assert می‌کند، پاک‌شدن خط از خروجی را بررسی می‌کند و ثابت‌ماندن تصویر ورودی را ثابت می‌کند. بنابراین هم کارکرد API اصلاح‌شده و هم رفتار قابل مشاهدهٔ شمارش/پاک‌سازی حفظ‌شده در این fixture به‌طور مشخص regression-tested است.

- Full local suite: **1702 passed**.
- `scripts/verify_o15_e60.py`: **PASS** (parity مصنوعی JSON و بررسی sidecarهای E-61/E-62).
- CI شاخهٔ fix commit: **PASS**, run `44080880091`؛ هر دو job پشتیبانی‌شده، Ubuntu و Windows.
- CI تگ `o15-E-63-fix-1`: **PASS**, run `44081030928`؛ هر دو job، Ubuntu و Windows.
- اجرای نهایی از source clone دقیقاً روی همان tag/SHA در Linux با CPython `3.11.2`, Pillow `11.1.0`, jsonschema `4.26.0` انجام شد. دو اجرای واقعی با پوشهٔ خروجی تازه، exit code `10` و aggregate یکسان دادند؛ هر دو JSON خروجی با schema متناظر **PASS** شدند. خطاهای top-level و page صفر و stderr خالی بود.
- یک فراخوانی پیش‌پرواز با مسیر خروجی ازپیش‌موجود به‌درستی با exit `30` رد شد، پیش از پردازش capture؛ اجرای واقعی با مسیر تازه انجام شد. هیچ تغییری در ورودی برای این کار صورت نگرفت.

**Artifact/provenance:** run موفق تگ E-60 `44030430963`، artifact ID `14305290850` و digest اعلامی `sha256:60f9baee9b8910d2817878d9777627b60ae3dde275d74cc8263eb53c9d5be083` دارد. یک تلاش مجدد با API احرازشده با EOF پایان یافت و فایل صفر بایت بود؛ **hash واقعی artifact تأیید نشد**. طبق ابلاغ مدیر اجرایی، E-63 از source Linux در tag/SHA fix-forward ادامه یافت؛ artifact ویندوزی در Linux اجرا نشد. این عبارت به معنی mismatch نیست؛ بایت معتبری برای مقایسه نرسید.

### ب) کیفیت واقعی استخراج از capture

ورودی، طبق مجوز مدیر اجرایی، ساختگی و غیرحساس بود؛ هیچ مقدار invoice/OCR در این گزارش درج نشده است. شاخص‌های واقعی دو اجرای نهایی:

| شاخص | نتیجه |
|---|---:|
| Invoice ورودی / دارای JSON | 1 / 1 |
| صفحه | 1 |
| وضعیت invoice / verdict | `REVIEW` / `REVIEW` |
| `BLOCKED` / `ERROR` | 0 / 0 |
| خطاهای top-level / page | 0 / 0 |
| Numeric candidateها | 9: quantity 4, line_total 4, payable 1 |
| Candidateهای `REVIEW` | 9/9 (100%) |
| Confidence `[0,25)` / `[25,50)` / `[50,75)` / `[75,100]` / `UNSCORED` | 0 / 0 / 0 / 9 / 0 |
| E-06 | `REVIEW`: `PARTIAL_MATCH`, `NEW_LAYOUT` |

**Glyph bankها جدا هستند:** default Glyph template bank در source بارگذاری شد (profile `row`: 17 template؛ `payable`: 10); glyph-drift monitor وضعیت `REVIEW` داد. هیچ bank update یا online learning رخ نداد. در مقابل، default E-05 layout/template bank **`UNAVAILABLE`, صفر template** بود؛ fixtureهای `tests/fixtures/real/canonical` و `tests/fixtures/real/labels.json` در tag source وجود ندارند، پس E-05 تطبیقی انجام نشد.

Accuracy برابر **`NOT_SCORED`** است: expected-value labels در دسترس نبودند و `extracted_but_wrong` برابر `null` ماند. Confidence بالا صحت را ثابت نمی‌کند. از آنجا که همهٔ 9 candidate در `REVIEW` هستند، کیفیت استخراج از نظر عملی نیازمند بازبینی است؛ این نتیجه نه `AUTO/ACCEPT` است و نه PASS دقت. یک invoice/صفحه، بدون labels مستقل، نمایندگی آماری یا صحت واقعی را اثبات نمی‌کند. هیچ مقدار یا برچسبی حدس یا برای بهترشدن نتیجه اصلاح نشد.

### ج) انطباق با معیارهای ازپیش‌تعیین‌شدهٔ E-63

| معیار checklist | شواهد ثبت‌شده | وضعیت |
|---|---|---|
| نوع/ساختار ورودی: capture-folder شامل SPL، `Report.txt` و PNG؛ ZIP فقط بسته‌بندی انتقال است | دقیقاً سه فایل مورد انتظار در مسیر invoice؛ CLI ورودی را پذیرفت و یک page result ساخت | **PASS** |
| حداقل تعداد: یک invoice کامل | 1 invoice، 1 صفحه؛ JSON نتیجه تولید شد | **PASS** |
| منبع/ساختگی‌بودن | synthetic/non-sensitive بودن را مدیر اجرایی اعلام کرد؛ شواهد موجود مبدأ Holoo را مستقل اثبات نمی‌کنند و CLI نیز آن را تشخیص نمی‌دهد | synthetic بودن **OWNER-ASSERTED**؛ Holoo-origin **NOT-VERIFIED** |
| تنوع | در معیار frozen حداقل تنوع تعیین نشده؛ یک نمونه کافی است | **NOT-VERIFIED**؛ از این نمونه ادعای نمایندگی نمی‌شود |
| پسوند/سلامت فایل‌ها | SPL غیرخالی، Report قابل خواندن، PNG قابل decode؛ خطای ساختاری/صفحه‌ای صفر | **PASS** |
| Manifest/sidecar و فایل‌های ممنوع | manifest جداگانه لازم نبود؛ Report تنها sidecar ورودی بود؛ bank/labels/context/output قبلی به ZIP اضافه نشد | **PASS** |
| درخت دقیق ZIP و اصالت فایل‌های capture | سه عضو دقیقاً با اندازه/hashهای مرجع تطبیق داشتند؛ مقادیر فایل‌ها در repo ثبت نشدند | **PASS** |
| روش اجرا و خروجی | source tag/SHA ثبت، Linux اجرا، هر دو JSON schema-valid، counts و محدودیت‌ها گزارش شدند | **PASS** |
| accuracy مستقل | labels مورد انتظار وجود نداشتند؛ `NOT_SCORED`, `extracted_but_wrong: null` | **UNSCORABLE**؛ نه pass و نه fail دقت |
| باینری Windows تگ E-60 | API احرازشده EOF داد؛ digest رسمی هست ولی بایت واقعی برای مقایسه نیست؛ ادامه از source tag جدید با مجوز صریح انجام شد | **NOT-VERIFIED**؛ محدودیت صریح، نه hash-match ادعایی |

### موارد NOT-VERIFIED

سه مورد NOT-VERIFIED طبق ابلاغ: مبدأ Holoo، artifact و تنوع. برای تنوع هیچ عدد یا تفسیر تازه‌ای افزوده نشده است.

### Disposition E-63

طبق ابلاغ مدیر اجرایی، وضعیت E-63 **`DELIVERED`** است: تکلیف و شواهد مستند شده‌اند، نه اینکه پذیرش نهایی اعلام شده باشد. نتیجهٔ extraction همچنان `REVIEW` است، E-05 bank در دسترس نبود و accuracy `NOT_SCORED` می‌ماند. پذیرش نهایی با مالک است؛ این disposition نه کیفیت را PASS می‌کند و نه نتیجهٔ REVIEW را به‌تنهایی دلیل پذیرش می‌گیرد.

## حفظ داده و انتقال

سه فایل ورودی در sandbox با مقادیر مرجع تطبیق داده شدند؛ hash/اندازهٔ capture در این گزارش ثبت نشده است. شاخهٔ راه‌دور `o15-e63-transfer`، آخرین SHA `d042001f8827fe591cfa428e859c91ff1846fa45`، طبق مجوز با `git push origin --delete o15-e63-transfer` حذف شد و بازسازی نشد. ZIP/ورودی/خروجی خام در repo، commit، tag یا workflow قرار نگرفتند. JSONهای کامل و logها فقط در sandbox باقی می‌مانند.

## وضعیت E-65

E-63 اکنون `DELIVERED` است، بدون ادعای پذیرش نهایی. متن‌های معتبر بررسی‌شده فقط عبارت «Holoo v1.2 stretch» و gateهای E-65 را ثبت می‌کنند؛ scope و معیارهای اجرایی کامل پیدا نشد. بنابراین E-65 **NOT STARTED** می‌ماند تا مالک scope/acceptance criteria را تکمیل کند. هیچ تغییری به `main` یا merge انجام نشده است.

## سوابق E-60 تا E-62

E-60 تا E-62 روی شاخهٔ تعیین‌شده پیاده‌سازی، تست، تگ و در CI شاخه و تگ تأیید شدند. برچسب‌های E-62 پیش‌فرض خالی‌اند و هیچ یادگیری آنلاین یا به‌روزرسانی Glyph انجام نمی‌شود. هشدار deprecation مربوط به Node.js 20 در workflowها غیرمسدودکننده بود.
