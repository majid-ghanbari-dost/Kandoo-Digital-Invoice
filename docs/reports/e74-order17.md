# E-74 — ORDER 17 two-raster score (PY-A re-score)

**Status: PARTIAL — the accuracy acceptance gate is NOT MET.** This re-score supersedes the earlier one-raster summary in this file. The extraction code evaluated is the unmodified `fc20f5858929f25288f6c8e1ddcf7717b91afd16` baseline on branch `arena/b264b596-kandoo-digital-invoice`.

## Scope, provenance, and leakage controls

- The scoring rasters are `samples/real-layout-fictional/invoice-34.png` (SHA-256 `f02033ee8ac274fd54546d4aa63516a99872517684c6904f27f894557c6c8cfb`) and `samples/real-layout-fictional/lane-synthetic-01/lane-synthetic-01.png` (SHA-256 `55acad10c41c9b5e7e4aee89fddedd93083f23e0ffec65eef059b1c452974d61`).
- The pinned `samples/real-layout-fictional/holdout-invoice-34/invoice_34.png` (SHA-256 `b92185fe1f028e215f54dbda25aaee3edfb6613661aaec53f0c1832e55346013`) was used only for an independent visual label check. It was not passed through the extraction pipeline, copied into the template bank, or used for training, fitting, calibration, or threshold changes.
- Both scoring rasters were run through `extract_pipeline_v0(..., evaluation=True)` against the existing default Glyph bank and drift baseline. The pipeline's source-path/SHA leakage guard remained enabled. Neither scoring raster was added to training data, and neither label source was edited. The synthetic label file remains SHA-256 `695cb4db0f1bf4cebe065460ed308b5ae6aa9074ce8d31d49f0e9186fea42405`.
- The synthetic labels passed local integrity checks for the fictional-only markers, four-line/nine-field structure, raster hash/dimensions/mode, and line-sum/payable arithmetic. This is not an OCR accuracy result; no formal JSON Schema is defined for this label format.
- No tag was created, moved, or deleted by this re-score.

## Independent invoice-34 reference read and label discrepancy

The holdout reference visually reads invoice number **34**, date **1405/08/16**, and **four** item rows. Its row values read:

| Row | Quantity read from reference | Line total read from reference (IRR) |
|---:|---:|---:|
| 1 | 2 | 12,626,262 |
| 2 | 6 | 12,156,156 |
| 3 | 2 | 12,525,252 |
| 4 | 7 | 12,743,759 |
| **Sum** |  | **50,051,429** |

The summary box reads total `50,051,429`, an explicit **`تخفیف` (invoice-level discount) of `503,639`**, and payable `49,547,790`. The discount row therefore accounts for the `503,639` difference; this is visible evidence, not an inferred discount. The original image's table and summary evidence is at `holdout-invoice-34/invoice_34.png`, source-pixel region approximately `(x=130..1060, y=900..2060)`; invoice number/date evidence is in `(x=130..1060, y=450..1000)`.

Invoice number, date, row count, row 1–3 quantities, row 3 total, and payable agree with the existing task labels. Four of the nine numeric labels do **not** agree with this independent reference read: row 1 total, row 2 total, row 4 quantity, and row 4 total. Per Decision 27, the existing invoice-34 labels are left untouched. Those four fields are **not scored** pending label reconciliation; they are not silently treated as model errors or as zero-error comparisons. The five uncontested numeric fields remain eligible for the score.

## Per-raster pipeline results

| Scoring raster | Layout / rows | Existing numeric labels | Independently scoreable | EXTRACTED | Correct | EXTRACTED-but-wrong | REVIEW | Missing | Not scored: label conflict | Exact accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Invoice 34 | `OK` / 4 | 9 | 5 | 0 | 0 | 0 | 5 | 0 | 4 | N/A — no extracted fields |
| `lane-synthetic-01` | `OK` / 4 | 9 | 9 | 0 | 0 | 0 | 9 | 0 | 0 | N/A — no extracted fields |

The `EXTRACTED` / `REVIEW` / `Missing` counts above cover only independently scoreable fields; the four disputed invoice-34 fields are shown separately as not scored. All nine invoice-34 cells nevertheless remained `REVIEW` (`onboarding required`). The invoice-34 raw candidates matched 4/5 independently confirmed numeric labels; no candidate contributes to accepted extraction accuracy. The pipeline's internal arithmetic check passed on its own raw invoice-34 candidates, whose line sum and payable were both `49,547,706`; that does not override the reference read or the official labels. For `lane-synthetic-01`, all nine cells remained `REVIEW`; the raw candidates matched 0/9 exact-by-construction labels and the arithmetic check failed.

Across the **14 independently scoreable fields**, extraction coverage is **0/14**. `EXTRACTED-but-wrong = 0` is therefore vacuous, not a pass; the required E-74 accuracy gate is **NOT MET**. Four invoice-34 fields remain unscored due to the label/reference conflict. No automatic correction, threshold tuning, or model retraining was performed.

## Status

**E-74 PARTIAL — both scoring rasters were evaluated, but acceptance was not achieved.** The invoice-34 reference resolves the subtotal/payable gap as a printed invoice-level discount, while exposing four conflicting line-item labels that remain unchanged under Decision 27. Both scoring rasters have zero extraction coverage. The current report should be read together with the existing labels in `TASKS/PY-T2.md`; it does not replace or edit them.
