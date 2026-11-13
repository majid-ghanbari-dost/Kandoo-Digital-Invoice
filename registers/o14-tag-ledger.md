# دفتر tagهای ORDER 14-PY

**Branch ثابت:** `arena/60d98123-kandoo-digital-invoice`

**مرجع:** `docs/E-44-o14-handoff.md` و `docs/DECISIONS.md`.
Tagهای `w11-*` و `stable-*` immutable هستند؛ این دفتر هیچ‌کدام را جابه‌جا نمی‌کند. داده‌های E-45..E-47 فقط local/git-ignored هستند و هرگز در این دفتر hash یا مسیر محرمانه ثبت نمی‌شود.

| Task | O14 disposition | Tag | Full commit SHA | CI / trace |
|---|---|---|---|---|
| E-39 | SKIPPED؛ PR #15 باز بود | `w11-E-39` (تاریخی) | `199ea0d9efca8be8987039cbdf8a4a8674c80965` | اجرای دوبارهٔ O14 انجام نشد. |
| E-40 | ACCEPTED / DONE | `o14-E-40` | `afb3df51af533867bb44d4bba2501da2153a7c31` | Python push [43389120727](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/43389120727); Windows push [43389120717](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/43389120717); Python PR [43389127480](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/43389127480); Windows PR [43389127492](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/43389127492) — همه success. |
| E-41 | ACCEPTED پیش‌تر؛ O14 rerun نشد | `w11-E-41` (تاریخی) | `495995f9bb1c789faafb5a1a24335efe804ffbd0` | synthetic-layout generator؛ سابقهٔ W11 حفظ شد. |
| E-42 | ACCEPTED پیش‌تر؛ SKIPPED در O14 | `w11-E-42b` (تاریخی) | `8028d13aa56ef001bfa401f5b09b4759ec08beee` | Python push [43075626735](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/43075626735); Windows push [43075626836](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/43075626836); Python PR [43075637975](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/43075637975); Windows PR [43075637826](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/43075637826) — همه success. |
| E-43 | WAIVED طبق D-I؛ اجرا نشد | بدون tag O14 | — | waiver در `docs/E-43-holoo-mapping-gate-blocked.md`; بدون اجرای Holoo sample. |
| E-44 | DONE؛ یک commit group؛ tag پس از CI سبز | `o14-E-44` | عین target همین tag | Annotation tag پس از موفقیت CI، commit full SHA و URL/conclusion هر چهار run را ثبت می‌کند. |
| E-45 | ACCEPTED؛ فقط local/git-ignored | بدون tag | — | هیچ CI/commit/push برای دادهٔ واقعی انجام نشد. |
| E-46 | ACCEPTED؛ فقط local/git-ignored | بدون tag | — | تمام REVIEW تحت DR-1؛ thresholdها دست‌نخورده. |
| E-47 | ACCEPTED؛ فقط local/git-ignored | بدون tag | — | geometry/report فقط در `DiagnosticResults/` محلی. |

**ثبت E-44:** چون ledger در همان commit group قرار دارد و متن یک commit نمی‌تواند hash خودش را در خود ثبت کند، `o14-E-44` یک annotated tag است و annotation آن، پس از CI سبز، full SHA و URLهای CI را به‌عنوان رکورد نهایی tag نگه می‌دارد. SHA کامل نیز با `git rev-parse 'o14-E-44^{commit}'` قابل راستی‌آزمایی است. این روش نیازی به commit گروه دوم ندارد.
