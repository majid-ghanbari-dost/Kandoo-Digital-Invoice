# گزارش E-71 — پشتیبانی چندچیدمان — ORDER 16

| task | branch | full SHA | CI run URL | result | artifact names |
|---|---|---|---|---|---|
| E-71 | `arena/d0587e71-kandoo-digital-invoice` | verification/tag commit `f99ab20f0d39b5e4a293d1c3bce9413d9b77d791` (`o16-E-71`)؛ پیاده‌سازی افزایشی در `9d772799817603e53b9fb81b09b2d79df775a3f5` | push: [Python 44994331602](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331602), [full ORDER 16 harness 44994331598](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331598), [Windows 44994331615](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331615); PR: [44994335316](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335316), [44994335259](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335259), [44994335282](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335282) | **COMPLETE — synthetic scope.** سه layout ساختگی، train/holdout مجزا و سنجه‌های layout match و numeric exact به‌تفکیک layout؛ gate `EXTRACTED-but-wrong=0` موفق. هیچ نتیجه‌ای دربارهٔ layout واقعی ادعا نمی‌شود. | `order16-python-harness-f99ab20f0d39b5e4a293d1c3bce9413d9b77d791`, `kandoo-extract-windows-f99ab20f0d39b5e4a293d1c3bce9413d9b77d791`, `windows-onefolder-44994331615` (API: unexpired) |

## نتیجهٔ synthetic

در اجرای محلی ثبت‌شدهٔ harness روی `9ddfae31fa42559a76c5fe2afc9257bb979b2f61`: `2076 passed in 341.23s`; هر یک از سه layout روی holdout، layout-match برابر `1/1` و numeric exact برابر `5/5` داشت، با `EXTRACTED-but-wrong=0` و `REVIEW/missing=0`. اجرای CI روی verification SHA بالا نیز full Python harness و E-74 hard gate را موفق اجرا و summary synthetic را upload کرد؛ verifierهای Windows و smokeهای وابسته هم سبز بودند.

همهٔ تصاویر و labelها ساختگی‌اند؛ این سنجه‌ها فقط صحت generator/test harness را نشان می‌دهند، نه دقت روی فاکتور واقعی یا تعمیم دنیای واقعی.

## وضعیت ادغام

تگ یکتای `o16-E-71` روی SHA بالا ایجاد شد، پس از سبزشدن CI و تأیید artifactها. PR #16 تجمیعی و create-only باقی است؛ ادغام انجام نشده است.
