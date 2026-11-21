# گزارش E-71 — ORDER 16

- **وضعیت:** مولد سه layout ساختگی، train/holdout مستقل و سنجه‌های جداگانهٔ layout-match و numeric exact آماده و آزموده شدند.
- **شاخه:** `arena/d0587e71-kandoo-digital-invoice`
- **ثبت کامل:** `9d772799817603e53b9fb81b09b2d79df775a3f5`
- **اجرای CI:** [44885771939](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44885771939)؛ harness Ubuntu موفق شد.
- **نتیجهٔ ساختگی holdout:** `layout-1`: layout `1/1`, numeric `5/5`; `layout-2`: `1/1`, numeric `5/5`; `layout-3`: `1/1`, numeric `5/5`. در هر سه `EXTRACTED-but-wrong=0` و `REVIEW/missing=0` بود.
- **محدوده:** همهٔ اعداد فقط از تصاویر و برچسب‌های ساختگی‌اند؛ هیچ ادعایی دربارهٔ فاکتور واقعی یا تعمیم دنیای واقعی ندارند.
- **آزمون بازگشت:** آزمون‌های E-71 در مجموعهٔ کامل Python اجرا شدند؛ نتیجهٔ کل harness `1717 passed` بود.
- **Artifact API:** گزارش ساختگی harness در `order16-python-harness-74375ff090b09649414ce4a7eb1fdfc4d15284ca` ثبت شد. metadata از API بررسی شد؛ محتوای artifact به‌علت EOF در endpoint دانلود دریافت نشد.
- **Tag:** **BLOCKED** — تعارض ORDER 16 با Rules v2؛ tag ساخته نشد.
- **PR:** **BLOCKED** — محدودیت شاخهٔ Arena امکان PR جداگانه برای این کار را نمی‌دهد؛ هیچ PR ادغام نشد.
