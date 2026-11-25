# E-74 — ORDER 17 per-layout raster score

## Scope and provenance

The user-authorized scoring source is the fictional real-layout raster `samples/real-layout-fictional/invoice-34.png` (SHA-256 `f02033ee8ac274fd54546d4aa63516a99872517684c6904f27f894557c6c8cfb`). The four line quantities/totals and payable labels in PY-T2 were confirmed by the user as operator-verified for this raster. No template was trained or changed on the evaluation image; the existing pipeline ran with its evaluation leakage guard enabled.

The approved capture tree contains two byte-identical copies of this raster, so it supplies **one unique raster/layout**, not two independent samples. The other capture folders had no usable raster and remain in the E-73 structural-review outcome. The per-layout score below is therefore limited to this one fictional layout; it is not a multi-layout or real-customer accuracy claim.

## Per-layout numeric metrics

| Evaluated layout | Detector / rows | Expected fields | EXTRACTED | Correct | EXTRACTED-but-wrong | REVIEW | Missing | Numeric exact accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Invoice 34 — one unique raster/layout | `OK` / 4 | 9 | 0 | 0 | 0 | 9 | 0 | N/A — no extracted fields |

Counts reconcile: `correct + EXTRACTED-but-wrong = EXTRACTED`, and `EXTRACTED + REVIEW + missing = expected`. **The zero `EXTRACTED-but-wrong` count is vacuous:** the glyph-drift monitor returned `REVIEW`, leaving all nine numeric cells in `REVIEW`. Coverage is 0/9, so the required accuracy gate is **NOT MET**; it must not be reported as a 0% accuracy pass or as accepted extraction.

For diagnostic context only, comparing the untrusted raw candidate readings (which all remained `REVIEW`) with the confirmed labels produced 4/9 exact matches: quantity candidates 3/4, line-total candidates 1/4, payable 0/1. These candidates are not `EXTRACTED` and do not contribute to the accepted numeric-accuracy metric. The pipeline arithmetic check returned `passed=true` on its own candidate readings; that does not override the confirmed labels or explain their sum/payable difference.

## Confirmed line-sum / payable outcome

The four confirmed line totals sum to **50,051,429**; confirmed payable is **49,547,790**; the line sum exceeds payable by **503,639**. This scoring run does not establish whether the difference is an invoice-level discount or a raster-reading issue. No discount is inferred. The cause remains **unresolved**.

## Local checks and CI

- Aggregate local E-70/E-73 evaluator: `NOT_SCORED`; 3 capture folders, 0 READY / 3 REVIEW; jobs 0 evaluated / 3 not evaluated / 0 extraction errors; operator labels valid/missing/invalid `0/0/0`; quantity, line-total, and payable counts each `0/0/0/0/0` (expected/pass/fail/review/missing). E-73 structural issue counts remain `AMBIGUOUS_SPL=1`, `EMPTY_SPL=1`, `JOB_IN_WRONG_FOLDER=1`, `MISSING_PNG=2`, `MISSING_REPORT=1`, `MISSING_SPL=2`.
- Regression CI on evaluated code SHA `ede16fd472c6a75f84e4b4449b9347ad486646ea`: [Python 45626308071](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45626308071), [Windows 45626308149](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45626308149), and [O15 bundle / ORDER 16 harness 45626308049](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/45626308049) succeeded. These CI checks and their artifacts are regression/build or synthetic-only evidence; they did **not** score the fictional raster. No raster or label payload was uploaded to CI.
- `o17-E-74` is an annotated tag on evaluated code SHA `ede16fd472c6a75f84e4b4449b9347ad486646ea`; the tag records this evaluation point and does not signify that the E-74 accuracy gate passed.

## Status

**E-74 PARTIAL — scored, acceptance gate NOT MET.** Only one unique fictional layout was available. All nine values remained `REVIEW`, with no extracted-field accuracy denominator. The 503,639 difference remains unexplained. PR #16 stays open and create-only; no merge, rebase, or close was performed.
