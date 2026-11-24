# گزارش پیگیری ORDER 17 — E-72، PY-T2 و E-73

**تاریخ:** 2026-10-12
**شاخه:** `arena/d0587e71-kandoo-digital-invoice`
**وضعیت:** آزمون محلی و CI راه‌دور سبز؛ `o17-E-72` و `o17-PY-T2` ساخته شدند. E-73 همچنان **PARTIAL** است و gate بازبینی ساختار capture توسط مالک باز می‌ماند؛ tag فقط پوشش synthetic دارد. PR #16 باز و `CONFLICTING / DIRTY` با base=`180b279b6c692f841cab739577ad4fedeefb77c3` است؛ طبق دستور هیچ rebase/merge/close انجام نشده و تصمیم PM/PO در [کامنت PR](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/16#issuecomment-7132327892) درخواست شده است.

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

چهار مبلغ ردیف و جمع `50,051,429` در این بازبینی تغییر نکرده‌اند. بازخوانی بصریِ ناحیهٔ payable در تصویر PO-certified `samples/real-layout-fictional/invoice-34.png` (۴۹٬۸۸۲ بایت؛ SHA-256=`f02033ee8ac274fd54546d4aa63516a99872517684c6904f27f894557c6c8cfb`) رقم `49,547,706` را نشان می‌دهد؛ **نه** `49,547,790`. رقم `49,547,790` که در پیام اخیر به‌عنوان مبنای ثبت‌شده آمده، از جمع کم شود `503,639` می‌دهد؛ اما از رقم قابل‌مشاهدهٔ تصویر (`49,547,706`) مقدار `503,723` به‌دست می‌آید. پس منشأ اختلاف ۸۴ ریالی، **رقم payable** است (`…790` در مبنای ابلاغ‌شده در برابر `…706` در PNG)، نه تغییر در یکی از چهار مبلغ ردیف.

گزارش قبلی ثبت می‌کند که رستر ESC/POS با تصویر بایت‌به‌بایت یکسان بوده است؛ خودِ رستر خام در checkout فعلی موجود نیست، بنابراین این نوبت امکان تطبیق مستقل/دوبارهٔ بایت‌ها را نداشتم. بر پایهٔ همان تطبیقِ ثبت‌شده، رستر باید همان `49,547,706` را نشان دهد؛ `49,547,790` را نمی‌توان از PNG موجود تأیید کرد. تا تأیید PO دربارهٔ مبلغ payable مرجع، هر دو تفاضل را جدا نگه می‌داریم و هیچ تخفیف/اصلاحی استنتاج نمی‌شود.

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
