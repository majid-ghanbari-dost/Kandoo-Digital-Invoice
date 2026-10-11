# Delivery Record — Issue #5 (Governance Reconciliation & Continuous Handoff)

```text
تاریخ:            2026-10-11 (UTC ثبت: 2026-10-11T20:28:02Z)
تحویل‌دهنده:      Agent 2 — شاخهٔ arena/a776e4f2-kandoo-digital-invoice → PR #6
PR:               https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/pull/6
Issue مرجع:       https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/issues/5
پروتکل:           GOV-PP-01 (PUBLICATION_PROTOCOL.md) — بند ۴ + چک‌لیست بند «ب»
SHA پایه (main):  77edafa8b474cf8037a9152593fcad5056e86b57
کامیتِ پوشش‌داده‌شده: 7e1a549 (هندآف v2.1 + GOV-PP-01 + reconciliation ثبت‌ها)
کامیتِ انتشار:     همین commit (فقط metadata تحویل — غیررکورسیو؛ در آرشیو نیست)
```

## فایل‌های این تحویل

| فایل | SHA-256 |
|---|---|
| `kandoo-governance-issue5-7e1a549.zip` (آرشیو کامل درخت در `7e1a549` — ۲۹۸ فایل) | `5fe32578ed7d698298cc6a4cc3712057239fb2118daf7bd0adc33c93d9319fc9` |
| `MANIFEST-SHA256.txt` (hash هر ۲۹۸ فایل درختِ `7e1a549`) | `5769946b546e768a41bd76b6a3dcf83b4b61217482f2350991c671e79bfb1f71` |

## راستی‌آزمایی مستقل (باید VERIFY-OK بدهد)

```bash
# manifest
sha256sum -c MANIFEST-SHA256.txt            # از داخل extract شدهٔ آرشیو
# آرشیو
sha256sum kandoo-governance-issue5-7e1a549.zip
# انتساب به main: درختِ 7e1a549 بدون هیچ تغییری در سورس/تست نسبت به main
git diff 77edafa8b474cf8037a9152593fcad5056e86b57 7e1a549 -- '*.py'   # خالی
```

## بازتولید از صفر (چک‌لیست GOV-PP-01)

```bash
C=7e1a549   # یا SHA دقیقِ درختِ مورد نظر
git archive --format=zip -o /tmp/kandoo-${C:0:7}.zip $C
sha256sum /tmp/kandoo-${C:0:7}.zip                     # → باید برابر بالا شود
tmp=$(mktemp -d) && git archive $C | tar -x -C "$tmp"
(cd "$tmp" && find . -type f | LC_ALL=C sort | xargs sha256sum) > /tmp/MANIFEST-SHA256.txt
sha256sum /tmp/MANIFEST-SHA256.txt                     # → باید برابر بالا شود
(cd "$tmp" && sha256sum -c /tmp/MANIFEST-SHA256.txt >/dev/null && echo VERIFY-OK)
```

## شواهد تست متعلق به همین درخت (`اجراشده` — 2026-10-11، Agent 2)

- `pytest capture/tests/test_wp13_*.py -q` → **130 passed** (2.16s)
- `pytest capture/tests/ -q` → **220 passed** (3.91s)
- `pytest -q` → **1606 passed, 0 failed** (179.38s)
- `run_smoke_retention_recovery.py` (دایرکتوری تازه) → **SMOKE OK** (۸ گام، exit 0)
- `python -m compileall -q .` → **exit 0**
- محیط: Python 3.11.2 · pytest 9.1.1 · درختِ اجرا = درختِ `main@77edafa` (`git diff` = ۰ خط)

پوشش: آرشیو/manifest درخت در `7e1a549` را پوشش می‌دهند؛ commit انتشار (این پوشه + سطرهای sync هندآف) metadata است و عمداً در آرشیو نیست (غیررکورسیو). SHA پایه/نهایی کامل و وضعیت PRها: **گزارش Issue #5**.
