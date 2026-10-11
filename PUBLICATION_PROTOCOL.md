# Kandoo Digital Invoice — PUBLICATION & TRACEABILITY PROTOCOL

```text
شناسه:          GOV-PP-01 | نسخه: 1.0 | تاریخ ثبت: 2026-10-11
ثبت‌کننده:      Agent 2 (مأموریت Issue #5 — بخش C)
محل ثبت:        این فایل (سند مرجع مستقل) + لینک از PROJECT_CONTINUITY_HANDOFF.md
چرا این فایل:   AGENT_HANDOFF.md و KANDOO_AGENT_COORDINATION.md هم‌زمان توسط PR #1 باز
                در حال ویرایش‌اند؛ طبق بند ۶ همین پروتکل، تغییر هم‌زمان روی یک فایل
                ممنوع است — پس پروتکل در فایل جدید مستقل ثبت شد. پس از تکلیف PR #1،
                TM/PO می‌تواند این پروتکل را در فایل هماهنگ‌تری ادغام کند.
وضعیت:          لازم‌الاجرا از لحظهٔ ثبت؛ نقض هر بند = تحویل ناقص (DONE محسوب نمی‌شود).
```

## الف) ده قاعدهٔ دائمی انتشار و ردیابی

1. **هر مأموریت روی branch مستقل از HEAD واقعی `main`** آغاز می‌شود؛ هیچ‌گاه مستقیم روی `main` commit نزنید. SHA پایه را با `git ls-remote origin refs/heads/main` ثبت کنید، نه با حافظه.
2. **`commit` + `push` + PR الزامی است.** هیچ تحویل صرفاً متنی/چت‌محور پذیرفته نمی‌شود؛ لینک PR در Issue مأموریت درج شود.
3. **شواهد تست داخل همین PR ثبت می‌شود** — فرمان کامل، محیط (نگارش Python/pytest)، SHA دقیقِ اجرا، و **خروجی واقعی** (نه خلاصهٔ ادعاشده). خلاصه‌سازی فقط با حفظ عدد/فرمان خروجی.
4. **پس از هر تحویل سورس:** آرشیو کامل درخت + `MANIFEST-SHA256.txt` (hash هر فایل) + **SHA-256 آرشیو**؛ فایل‌ها/شواهد باید **روی GitHub قابل دسترسی** باشند (مثلاً `deliveries/<issue>/` در همان PR — روش در بند ج). اگر upload ممکن نبود، مانع را دقیق بگویید و حداقل manifest + فرمان بازتولید را در PR بگذارید.
5. **هندآف در همان PR یا PR حکمرانیِ وابسته به همان تحویل، هم‌زمان به‌روز می‌شود** — هرگز «بعداً». پس از هر commit مهم، هندآف با وضعیت **همان commit/PR** همگام می‌شود و هرگز دربارهٔ وضعیت آینده ادعا نمی‌کند.
6. **مالکیت فایل:** Agent 1 مالک `src/` + تست‌های محصولی قابلیت‌ها (مأموریت Issue #4)؛ Agent 2 مالک مستقل `PROJECT_CONTINUITY_HANDOFF.md`، Registerهای governance و بازبینی. **تغییر هم‌زمانِ دو ایجنت روی یک فایل ممنوع است** — پیش از ویرایش، `gh pr list` + `gh pr diff <PR>` بزنید و اگر PR بازی همان فایل را دارد، یا با صاحبش هماهنگ کنید یا در فایل/PR جدا کار کنید.
7. **هیچ merge به `main` بدون دستور صریح PO.** PASS شدن تست، مرز Acceptance نیست؛ Acceptance فقط با ثبت رسمی PO/TM در Register.
8. **هر اختلاف بین artifact محلی و `main`** با `compare`/`hash` و **هویت commit** حل می‌شود — «تاریخ فایل» یا «نسخهٔ من» به‌تنهایی کافی نیست. SHA قدیمی که از تاریخچهٔ `main` خارج شده، با `ls-remote` + `git merge-base --is-ancestor` اثبات شود.
9. **هر ادعای «گزارش‌شده» از «اجراشده» جدا می‌ماند** (برچسب‌های هندآف را رعایت کنید): اجرای خودتان = `اجراشده` + فرمان؛ نقل از ایجنت/سند دیگر = `گزارش‌شده` با منبع و تاریخ.
10. **اعلام DONE فقط با پنج شاهد:** (الف) لینک PR باز/ادغام‌شده، (ب) شواهد تست اجراشده، (ج) archive + manifest + SHA-256 (بند ۴)، (د) هندآفِ همگام (بند ۵)، (هـ) next action با مالک و شاهد بستن.

## ب) چک‌لیست قابل تکرار انتشار archive + MANIFEST-SHA256 + SHA-256

از ریشهٔ مخزن، با `<COMMIT>` = SHA دقیقِ درختِ تحویل (محتوای سورس باید در آن commit نهایی شده باشد):

```bash
# ۱) ثبت هویت
git rev-parse HEAD                                  # → <COMMIT> (این عدد را در PR و Issue بنویسید)

# ۲) آرشیو کامل درخت در همان instant
git archive --format=zip -o /tmp/kandoo-<COMMIT:0:12>.zip <COMMIT>
sha256sum /tmp/kandoo-<COMMIT:0:12>.zip             # → ARCHIVE-SHA-256

# ۳) manifest همهٔ فایل‌های همان درخت
tmp=$(mktemp -d)
git archive <COMMIT> | tar -x -C "$tmp"
(cd "$tmp" && find . -type f | LC_ALL=C sort | xargs sha256sum) > /tmp/MANIFEST-SHA256.txt
sha256sum /tmp/MANIFEST-SHA256.txt                  # → MANIFEST-SHA256 of the manifest

# ۴) راستی‌آزمایی مستقل (باید بی‌صدا تمام شود)
(cd "$tmp" && sha256sum -c /tmp/MANIFEST-SHA256.txt >/dev/null && echo VERIFY-OK)

# ۵) انتشار روی GitHub (در همان PRِ تحویل)
mkdir -p deliveries/<issue>
cp /tmp/kandoo-<COMMIT:0:12>.zip  deliveries/<issue>/
cp /tmp/MANIFEST-SHA256.txt       deliveries/<issue>/
# + deliveries/<issue>/README.md با: SHA تحویل، ARCHIVE-SHA-256، hash خودِ manifest،
#   کامیتِ پوشش‌داده‌شده، فرمان‌های بالا، و تاریخ/محل ثبت (این PR + گزارش Issue)
git add deliveries/<issue>/ && git commit -m "delivery(artifact): archive + MANIFEST-SHA256 for <COMMIT>"
```

سپس در **بدنهٔ PR** و **گزارش Issue مأموریت** دقیقاً ثبت کنید:
`<COMMIT>` · `ARCHIVE-SHA-256` · `MANIFEST hash` · مسیر فایل‌ها در repo · فرمان راستی‌آزمایی.

> پوشش‌دهی: آرشیو/manifest درختِ `COMMIT` را می‌سازند؛ commitِ انتشار (خودِ `deliveries/`) metadata تحویل است و در آرشیو نمی‌گنجد — این قاعده عمدی و غیررکورسیو است و باید در README تحویل قید شود.

## ج) لینک‌ها و مرجع

- مأموریت مرجع این پروتکل: [Issue #5](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/issues/5)
- هندآف پروژه: `PROJECT_CONTINUITY_HANDOFF.md` (این پروتکل را link می‌خورد)
- مالکیت‌ها و مرز ایجنت‌ها: Issue #4 (Agent 1 — سورس/تست محصول) و Issue #5 (Agent 2 — governance/handoff/review)
