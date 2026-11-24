# گزارش پیگیری ORDER 17 — E-72، PY-T2 و E-73

**تاریخ:** 2026-10-12
**شاخه:** `arena/d0587e71-kandoo-digital-invoice`
**وضعیت:** آزمون محلی و CI راه‌دور سبز؛ `o17-E-72` و `o17-PY-T2` ساخته شدند. C# review trigger ارسال شد و پاسخ مستقل در انتظار است؛ PR #16 باز و `CONFLICTING` است و طبق دستور دست‌نخورده می‌ماند.

## E-72 — بردار پیش‌نویس

- بردار synthetic به شکل مصرف‌کنندهٔ C# اصلاح شد: `quantity` با `quantity_millis` جایگزین شد (۱ واحد = `1000` هزارم) و مقدار provenance هم همان نام را دارد؛ در DRAFT، `display_number=null` و provenance برابر `unavailable` است.
- بازبینی مجدد نشان داد `image_sha256` و `template_library_id` از ابتدا فقط داخل `base_invoice.provenance` بوده‌اند، نه در ریشهٔ `base_invoice`. مصرف‌کننده و قرارداد E-11 این فیلدهای provenance را لازم می‌دانند؛ بنابراین حفظ شدند و `RootAllowed` دست‌نخورده ماند. ادعای قبلی دربارهٔ فیلدهای اضافی در ریشه نیازمند اصلاح است.
- verifier از قرارداد منجمد بین‌مخزنی `contracts/canonical_invoice_v0.schema.json` (E-11/C#) استفاده می‌کند؛ شِمای E-01 در `schemas/canonical_invoice_v0.json` و خودِ قراردادهای منجمد تغییر نکردند. verifier: **PASS**؛ بردار `1518` بایت، SHA-256 برابر `4a9f8555fdb29e53ed1d42ba2d5ce50fba8ea181c7cb46bba4596e781ccadf95`؛ آزمون E-72: **4 passed**.

## PY-T2 — ground truth فاکتور 34

| ردیف | کالا | تعداد | مبلغ ردیف (ریال) |
|---:|---|---:|---:|
| 1 | قاشق ثم | 2 | 12,926,922 |
| 2 | نایر بلند | 6 | 12,159,159 |
| 3 | کارت دعوت | 2 | 12,525,252 |
| 4 | کلاه‌زم برجسته | 9 | 12,440,096 |
| **جمع** |  |  | **50,051,429** |

بازخوانی برش مبلغ از تصویر اصلی، `49,547,706` را نشان می‌دهد؛ رستر ESC/POS قبلاً بایت‌به‌بایت با همان تصویر تطبیق داده شده است، پس خوانش اصلاح‌شدهٔ رستر نیز `49,547,706` است. رونویسی پیشین `49,547,790`، ۸۴ ریال بیش‌خوانی داشت. جمع چهار ردیف **503,723 ریال** از مبلغ قابل‌پرداخت بیشتر است. مدرکی برای تخفیف سطح فاکتور یا آشتی این اختلاف پیدا نشد؛ اختلاف **حل‌نشده** می‌ماند و تخفیفی فرض نمی‌شود.

## E-73 — پایداری capture

- آزمون فقط ساختار سه‌پوشه‌ای و ۱۱ فایل را با payload کاملاً ساختگی بازسازی می‌کند: دو جفت SPL/PNG همسان، SPL صفر‌بایتی `14050816_135747_803_00002.SPL` و SHD نابه‌جا زیر `Unassigned`؛ همهٔ سه پوشه در آزمون در `REVIEW` می‌مانند.
- شمار کدهای آزمون: `AMBIGUOUS_SPL=1`, `EMPTY_SPL=1`, `JOB_IN_WRONG_FOLDER=1`, `MISSING_PNG=2`, `MISSING_REPORT=1`, `MISSING_SPL=2`. هیچ SPL/SHD/PNG یا گزارش واقعی به Git، CI یا artifact وارد نشده است؛ خروجی استخراج/OCR اجرا نشده است.
- فرادادهٔ بسته‌ایِ ارائه‌شده فقط برای زمینه ثبت شد: printer `GA-E200`، template `FishPrint6Cm.fr3`، owner `Gilbyte`، تاریخ `1405/08/16`. این موارد وارد payload آزمون نشده‌اند.
- آزمون هدفمند E-73/onboarding/capture-folder: **41 passed in 4.91s**. آزمون کامل synthetic ORDER 16: **2088 passed in 229.65s**؛ verifier E-72، O15، E-70 smoke و hard gate سه layout همگی PASS. این اعداد نتیجهٔ ساختگی‌اند و امتیاز دقت فاکتور واقعی نیستند.

## تحویل

دو commit این کار: E-72 `1e029bd` و PY-T2/E-73 `e6339a4`. Tagهای یکتا: `o17-E-72` روی commit اول و `o17-PY-T2` روی commit دوم.

CI push در SHA `e6339a4c97eff6e328a2ba0ece7925c4e1cd9dbd`:
- [Python tests — 45391144844](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144844) — success.
- [Windows one-folder build — 45391144767](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144767) — success.
- [O15 extractor bundle/full harness — 45391144776](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45391144776) — success.

Required checks سبز شدند؛ N-01/N-04 اختیاری `SKIPPED` بودند. فقط هشدار deprecation مربوط به Node.js 20 و notice موفقیت Windows ثبت شد؛ annotation خطا وجود نداشت. Artifactهای runها در API موجود و منقضی‌نشده‌اند؛ payloadها دانلود نشدند.

درخواست بازبینی C# در [کامنت PR #16](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7131272676) ثبت شد؛ پذیرش C# تا پاسخ مستقل ادعا نمی‌شود. PR #16 باز و create-only باقی می‌ماند؛ وضعیت فعلی GitHub `CONFLICTING` است و merge/rebase انجام نمی‌شود. `main` دست‌نخورده ماند.
