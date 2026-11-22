# گزارش E-74 — harness و دروازهٔ دقت — ORDER 16

| task | branch | full SHA | CI run URL | result | artifact names |
|---|---|---|---|---|---|
| E-74 | `arena/d0587e71-kandoo-digital-invoice` | verification/tag commit `f99ab20f0d39b5e4a293d1c3bce9413d9b77d791` (`o16-E-74`)؛ پیاده‌سازی harness در `74375ff090b09649414ce4a7eb1fdfc4d15284ca` | push: [Python 44994331602](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331602), [harness + smoke 44994331598](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331598), [Windows build 44994331615](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994331615); PR: [44994335316](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335316), [44994335259](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335259), [44994335282](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/44994335282) | **COMPLETE.** یک فرمان، آزمون کامل Python، verifierهای O15 و E-72، smoke آموزش E-70 و سنجه‌های جداگانهٔ E-71 را اجرا می‌کند؛ دروازهٔ سخت و smokeهای required سبز شدند. | `order16-python-harness-f99ab20f0d39b5e4a293d1c3bce9413d9b77d791`, `kandoo-extract-windows-f99ab20f0d39b5e4a293d1c3bce9413d9b77d791`, `windows-onefolder-44994331615` (API: unexpired; payload دانلود نشد) |

## فرمان و دروازه

از ریشهٔ مخزن در محیط Python توسعهٔ نصب‌شده اجرا کنید:

```bash
.venv/bin/python scripts/run_order16_harness.py
```

در Windows CI همان harness روی source اجرا شد و مسیرهای O15/E-70 به‌طور جداگانه با executable one-folder smoke شدند. فرمان کامل این موارد را اجرا می‌کند: کل pytest suite؛ verifier بایت‌به‌بایت بردارهای synthetic E-72؛ verifier O15؛ smoke محلی E-70؛ ساخت train/holdout مستقل برای سه layout؛ سنجه‌های layout match و numeric exact به تفکیک layout.

دروازه فقط وقتی موفق است که شمارها سازگار باشند، `EXTRACTED-but-wrong=0` و سنجهٔ هر layout جداگانه گزارش شود. `REVIEW/missing` به‌اشتباه correct شمرده نمی‌شود.

## نتیجه و شواهد

- اجرای محلی کامل ثبت‌شده روی SHA `9ddfae31fa42559a76c5fe2afc9257bb979b2f61`: `2076 passed in 341.23s`; O15 verifier، E-70 source smoke، E-72 vector و E-74 hard gate PASS.
- در همان synthetic holdout: هر layout `layout-match=1/1`, `numeric exact=5/5`, `EXTRACTED-but-wrong=0`, `REVIEW/missing=0`. این اعداد فقط برای fixtureهای کاملاً ساختگی‌اند.
- روی verification SHA جدول، CI گام `Run ORDER 16 full Python harness and E-74 accuracy gate` موفق شد و summary synthetic upload شد. Windows executable build, E-70 frozen smoke, E-72 vector verification و artifact upload نیز موفق شدند؛ تمام required push و PR checks سبز بودند. N-01/N-04 اختیاری skipped شدند. Artifact API فقط metadata/unexpired را تأیید کرد؛ payload دانلود/بازبینی نشده است.
- تگ یکتای `o16-E-74` روی SHA جدول ایجاد شد، پس از CI سبز و ثبت artifact. E-75 آغاز نشده است؛ blocker E-73 برای تطبیق محلی ساختار واقعی همچنان جداگانه باز است.
- PR #16 تجمیعی، باز و create-only است؛ merge انجام نشده است.
