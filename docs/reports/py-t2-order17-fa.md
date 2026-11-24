# گزارش پیگیری ORDER 17 — E-72، PY-T2 و E-73

**تاریخ:** 2026-10-12
**شاخه:** `arena/d0587e71-kandoo-digital-invoice`
**وضعیت:** E-72 وکتور در دور دوم طبق رأی C# به ریشهٔ flat اصلاح شد؛ تگ تازهٔ `o17-E-72-r2` پس از سبزشدن CI روی گروه‌کامیت ساخته می‌شود و بازبینی سوم C# پس از تگ درخواست خواهد شد. PY-T2 طبق R-009 روی `main` در `eed35610ea05d034a40222a0404ef331e4cc261c` **BLOCKED-on-evidence** است؛ E-73 همچنان **PARTIAL** با gate بررسی محلیِ ساختار capture توسط مالک است. PR #16 باز و create-only است؛ بررسی API **پیش از گروه‌کامیت این دور** `mergeable=false`, `mergeable_state=dirty`, base=`180b279b6c692f841cab739577ad4fedeefb77c3`, head=`b4387c43f013897670e6886d9dd47774355643ad` را نشان داد؛ هیچ rebase/merge/close انجام نشده. تصمیم PM/PO دربارهٔ تعارض از طریق [کامنت PR](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7132327892) و درخواست تصویر اصلی از طریق [کامنت evidence request](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7138881898) ثبت شده‌اند.

## E-72 — بردار پیش‌نویس

- رأی اصلاح‌شدهٔ C# `6039821259`، vector دور اول را با خطای `SchemaValidationFailed | Unexpected field: base_invoice.` ناسازگار اعلام کرد؛ گزارش مقایسهٔ اصلاح‌شده حکم می‌کند که consumer ریشهٔ flat می‌خواهد. برداشت دور اول دربارهٔ wrapper اکنون superseded است.
- اصلاح دور دوم `base_invoice` را flatten و چهار کلید envelope را حذف کرد؛ root دقیقاً ۱۶ فیلد required E-11 دارد. اصلاحات قبلی `quantity_millis`, DRAFT `display_number=null`, provenance `unavailable` حفظ شدند؛ `image_sha256` و `template_library_id` فقط در root `provenance` ماندند.
- verifier با قرارداد منجمد `contracts/canonical_invoice_v0.schema.json` اجرا می‌شود؛ شِمای E-01 و قراردادهای frozen دست‌نخورده‌اند. نسخهٔ flat: `1205` بایت، SHA-256 `36939192b6d7e5de57c732309272edc5fe6594d79e15b419754eda6afaff14fd`; آزمون E-72 دور دوم **4 passed in 0.33s** و verifier **PASS**. جزئیات/MD5/byte evidence در `docs/reports/e72-order17-flat-root-r2.md` ثبت است؛ پذیرش مستقل C# نسخهٔ تازه هنوز در انتظار بازبینی است.

## PY-T2 — ground truth فاکتور 34

| ردیف | کالا | تعداد | مبلغ ردیف (ریال) |
|---:|---|---:|---:|
| 1 | قاشق ثم | 2 | 12,926,922 |
| 2 | نایر بلند | 6 | 12,159,159 |
| 3 | کارت دعوت | 2 | 12,525,252 |
| 4 | کلاه‌زم برجسته | 9 | 12,440,096 |
| **جمع** |  |  | **50,051,429** |

## PY-T2 — اعمال حکم R-009 و وضعیت evidence

طبق R-009 ثبت‌شده در `main` همین مخزن در commit `eed35610ea05d034a40222a0404ef331e4cc261c`، فاکتور ۳۴ دقیقاً چهار ردیف دارد؛ payable مرجع `49,547,790` ریال است و خوانش پیشین `49,547,706` **منسوخ** شده است. جمع ردیف‌ها `50,051,429` و اختلاف ملاک `503,639` ریال است.

وضعیت **BLOCKED-on-evidence** می‌ماند چون raster خام برای بازخوانی/تطبیق در دسترس نیست. فقط دو فرضیهٔ باقیمانده‌اند: (۱) تخفیف سطح فاکتور؛ (۲) خطای خوانش رستر. هیچ‌کدام انتخاب یا اثبات نشده و تخفیفی بدون سند استنتاج نمی‌شود. درخواست تصویر اصلی از مسیر [کامنت PR #16](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7138881898) ثبت شده است؛ هر دادهٔ واقعی باید فقط محلی و Git-ignored بماند و وارد Git/CI/artifact نشود.

## E-73 — پایداری capture

- آزمون فقط ساختار سه‌پوشه‌ای و ۱۱ فایل را با payload کاملاً ساختگی بازسازی می‌کند: دو جفت SPL/PNG همسان، SPL صفر‌بایتی `14050816_135747_803_00002.SPL` و SHD نابه‌جا زیر `Unassigned`؛ همهٔ سه پوشه در آزمون در `REVIEW` می‌مانند.
- شمار کدهای آزمون: `AMBIGUOUS_SPL=1`, `EMPTY_SPL=1`, `JOB_IN_WRONG_FOLDER=1`, `MISSING_PNG=2`, `MISSING_REPORT=1`, `MISSING_SPL=2`. هیچ SPL/SHD/PNG یا گزارش واقعی به Git، CI یا artifact وارد نشده است؛ خروجی استخراج/OCR اجرا نشده است.
- فرادادهٔ بسته‌ایِ ارائه‌شده فقط برای زمینه ثبت شد: printer `GA-E200`، template `FishPrint6Cm.fr3`، owner `Gilbyte`، تاریخ `1405/08/16`. این موارد وارد payload آزمون نشده‌اند.
- آزمون هدفمند E-73/onboarding/capture-folder: **41 passed in 4.91s**. آزمون کامل synthetic ORDER 16: **2088 passed in 229.65s**؛ verifier E-72، O15، E-70 smoke و hard gate سه layout همگی PASS. این اعداد نتیجهٔ ساختگی‌اند و امتیاز دقت فاکتور واقعی نیستند.

## تحویل

سابقهٔ پایه: E-72 دور اول `1e029bd` با tag `o17-E-72`؛ PY-T2/E-73 synthetic `e6339a4` با tag `o17-PY-T2`. اصلاح E-72 دور دوم و به‌روزرسانی R-009 در یک گروه‌کامیت انجام می‌شوند؛ tag تازهٔ `o17-E-72-r2` فقط پس از سبزشدن CI روی همان گروه‌کامیت قرار می‌گیرد و tagهای قبلی دست‌نخورده می‌مانند.

CI push در SHA `e6339a4c97eff6e328a2ba0ece7925c4e1cd9dbd`:
- [Python tests — 45391144844](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144844) — success.
- [Windows one-folder build — 45391144767](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144767) — success.
- [O15 extractor bundle/full harness — 45391144776](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144776) — success.

Required checks سبز شدند؛ N-01/N-04 اختیاری `SKIPPED` بودند. فقط هشدار deprecation مربوط به Node.js 20 و notice موفقیت Windows ثبت شد؛ annotation خطا وجود نداشت. Artifactهای runها در API موجود و منقضی‌نشده‌اند؛ payloadها دانلود نشدند.

بازبینی اصلاح‌شدهٔ C# با شناسهٔ `6039821259` بردار قبلی را به‌دلیل `Unexpected field: base_invoice` رد کرد؛ نسخهٔ اصلاحی پس از push و tag در همان PR برای بازبینی دوباره فرستاده می‌شود. PR #16 باز و create-only باقی می‌ماند؛ بررسی API در همین دور `mergeable=false / dirty` با base=`180b279b6c692f841cab739577ad4fedeefb77c3` و head=`b4387c43f013897670e6886d9dd47774355643ad` بود؛ merge/rebase انجام نمی‌شود. `main` دست‌نخورده ماند.
