# B2-2 — Payable-only vertical-rule removal

## Scope and method

The production change keeps the existing Otsu/adaptive thresholds and the existing vertical-kernel formula (`max(15, int(cell_height * 0.55))`, rounded up to an odd length by the morphology helper). Crops are tagged by class; only `invoice.payable` skips the vertical-rule mask. Horizontal-rule removal remains enabled. The skip flag defaults to `False`, so untagged crops and direct calls retain prior behavior.

The unchanged glyph hairline filter remains `width <= 2px` and `height >= 0.8 * cell height`; `glyph_classifier.py` was not modified. Component counts use the B2-1 diagnostic's same 8-connected, minimum-size, hairline-filter, and x-overlap-merge logic. Expected counts include digit and comma/separator glyphs from the confirmed labels.

Reproduction command: `/tmp/kandoo-t2-venv/bin/python scripts/diagnose_b2_2.py --labels tests/fixtures/real/labels.json --output docs/b2-2-payable-preprocessing-report.md`

## PM crop geometry

For each row cell, the listed `height/kernel` pairs are in row order. Total and quantity crops use the same row-band height but are listed separately as requested. All measured row kernels are compared with the approximately 24px digit height from the diagnosis.

| invoice | payable height/kernel | row total height/kernel | quantity height/kernel | row kernels > ~24px |
|---|---:|---|---|---|
| 29 | payable 36px/19px | line.0 60px/33px, line.1 57px/31px, line.2 57px/31px, line.3 58px/31px | line.0 60px/33px, line.1 57px/31px, line.2 57px/31px, line.3 58px/31px | yes |
| 31 | payable 36px/19px | line.0 60px/33px, line.1 57px/31px, line.2 58px/31px | line.0 60px/33px, line.1 57px/31px, line.2 58px/31px | yes |
| 32 | payable 36px/19px | line.0 60px/33px, line.1 57px/31px, line.2 57px/31px, line.3 57px/31px, line.4 57px/31px | line.0 60px/33px, line.1 57px/31px, line.2 57px/31px, line.3 57px/31px, line.4 57px/31px | yes |
| 33 | payable 36px/19px | line.0 60px/33px, line.1 57px/31px, line.2 57px/31px, line.3 57px/31px, line.4 57px/31px, line.5 57px/31px, line.6 57px/31px, line.7 56px/31px, line.8 57px/31px, line.9 57px/31px, line.10 57px/31px, line.11 57px/31px, line.12 58px/31px | line.0 60px/33px, line.1 57px/31px, line.2 57px/31px, line.3 57px/31px, line.4 57px/31px, line.5 57px/31px, line.6 57px/31px, line.7 56px/31px, line.8 57px/31px, line.9 57px/31px, line.10 57px/31px, line.11 57px/31px, line.12 58px/31px | yes |

## Component-count controls (before → after)

`pixels changed` compares the complete preprocessed binary bytes. The total/quantity controls must remain byte-identical; payable output may differ only when the old vertical mask removed foreground.

| class | cells | mismatches before | mismatches after | cells with pixel changes |
|---|---:|---:|---:|---:|
| total | 25 | 0 | 0 | 0 |
| quantity | 25 | 0 | 0 | 0 |
| payable | 4 | 3 | 0 | 3 |

### Per-cell controls

| invoice | class | field | crop h | vertical kernel | components before → after | expected | pixels changed | removed px before → after |
|---|---|---|---:|---:|---:|---:|---|---:|
| 29 | total | `line.0.total` | 60 | 33 | 9 → 9 | 9 | no | 0 → 0 |
| 29 | quantity | `line.0.quantity` | 60 | 33 | 1 → 1 | 1 | no | 0 → 0 |
| 29 | total | `line.1.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 29 | quantity | `line.1.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 29 | total | `line.2.total` | 57 | 31 | 7 → 7 | 7 | no | 0 → 0 |
| 29 | quantity | `line.2.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 29 | total | `line.3.total` | 58 | 31 | 7 → 7 | 7 | no | 0 → 0 |
| 29 | quantity | `line.3.quantity` | 58 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 29 | payable | `invoice.payable` | 36 | 19 | 10 → 9 | 9 | yes | 43 → 0 |
| 31 | total | `line.0.total` | 60 | 33 | 7 → 7 | 7 | no | 0 → 0 |
| 31 | quantity | `line.0.quantity` | 60 | 33 | 1 → 1 | 1 | no | 0 → 0 |
| 31 | total | `line.1.total` | 57 | 31 | 7 → 7 | 7 | no | 0 → 0 |
| 31 | quantity | `line.1.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 31 | total | `line.2.total` | 58 | 31 | 7 → 7 | 7 | no | 0 → 0 |
| 31 | quantity | `line.2.quantity` | 58 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 31 | payable | `invoice.payable` | 36 | 19 | 12 → 9 | 9 | yes | 127 → 0 |
| 32 | total | `line.0.total` | 60 | 33 | 7 → 7 | 7 | no | 0 → 0 |
| 32 | quantity | `line.0.quantity` | 60 | 33 | 1 → 1 | 1 | no | 0 → 0 |
| 32 | total | `line.1.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 32 | quantity | `line.1.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 32 | total | `line.2.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 32 | quantity | `line.2.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 32 | total | `line.3.total` | 57 | 31 | 7 → 7 | 7 | no | 0 → 0 |
| 32 | quantity | `line.3.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 32 | total | `line.4.total` | 57 | 31 | 6 → 6 | 6 | no | 0 → 0 |
| 32 | quantity | `line.4.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 32 | payable | `invoice.payable` | 36 | 19 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | total | `line.0.total` | 60 | 33 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.0.quantity` | 60 | 33 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.1.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.1.quantity` | 57 | 31 | 2 → 2 | 2 | no | 0 → 0 |
| 33 | total | `line.2.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.2.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.3.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.3.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.4.total` | 57 | 31 | 10 → 10 | 10 | no | 0 → 0 |
| 33 | quantity | `line.4.quantity` | 57 | 31 | 2 → 2 | 2 | no | 0 → 0 |
| 33 | total | `line.5.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.5.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.6.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.6.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.7.total` | 56 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.7.quantity` | 56 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.8.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.8.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.9.total` | 57 | 31 | 11 → 11 | 11 | no | 0 → 0 |
| 33 | quantity | `line.9.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.10.total` | 57 | 31 | 10 → 10 | 10 | no | 0 → 0 |
| 33 | quantity | `line.10.quantity` | 57 | 31 | 2 → 2 | 2 | no | 0 → 0 |
| 33 | total | `line.11.total` | 57 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.11.quantity` | 57 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | total | `line.12.total` | 58 | 31 | 9 → 9 | 9 | no | 0 → 0 |
| 33 | quantity | `line.12.quantity` | 58 | 31 | 1 → 1 | 1 | no | 0 → 0 |
| 33 | payable | `invoice.payable` | 36 | 19 | 15 → 11 | 11 | yes | 209 → 0 |

## Four-fold leave-one-invoice-out results

Each fold trained templates on the other three fixture invoices and evaluated the held-out invoice through the existing CLI evaluator. No leakage override or threshold changes were used.

| class | component-count mismatches before → after | exact digit cells | EXTRACTED-but-wrong | statuses |
|---|---:|---:|---:|---|
| total | 0/25 → 0/25 | 21/25 | 0 | EXTRACTED=12, REVIEW=13 |
| quantity | 0/25 → 0/25 | 22/25 | 0 | EXTRACTED=21, REVIEW=4 |
| payable | 3/4 → 0/4 | 3/4 | 0 | EXTRACTED=3, REVIEW=1 |

### Fold-by-fold

| fold | held-out | total exact | quantity exact | payable exact/status | gate passed | EXTRACTED-but-wrong |
|---|---:|---:|---:|---|---|---:|
| fold-1 | 29 | 4/4 | 4/4 | 1/1, EXTRACTED | True | 0 |
| fold-2 | 31 | 3/3 | 3/3 | 1/1, EXTRACTED | True | 0 |
| fold-3 | 32 | 5/5 | 5/5 | 1/1, EXTRACTED | True | 0 |
| fold-4 | 33 | 9/13 | 10/13 | 0/1, REVIEW | False | 0 |

### Acceptance checks

- Total and quantity preprocessed bytes unchanged: PASS (0 total and 0 quantity cells changed).
- Payable component counts match labels after the fix: PASS (0/4 mismatches).
- EXTRACTED-but-wrong is zero: PASS (0).
- Arithmetic gates pass at least 3/4 folds: PASS (3/4).
- Every component-covered payable is EXTRACTED: FAIL.
- Overall B2-2 diagnostics: FAIL.

## Per-fold payable statuses

| invoice | expected components | post-fix components | component coverage | LOO status |
|---|---:|---:|---|---|
| 29 | 9 | 9 | yes | EXTRACTED |
| 31 | 9 | 9 | yes | EXTRACTED |
| 32 | 9 | 9 | yes | EXTRACTED |
| 33 | 11 | 11 | yes | REVIEW |

## Summary

The payable-only behavior is carried from `crop_spatial_cells()` through Pillow image metadata to `preprocess_cell()`, avoiding any change to the frozen glyph-classifier caller. No bbox/Tesseract, HTTP, real-image adapter extraction, or glyph-classifier code was changed.

## Unit-test verification

Command: `PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m unittest discover -s src -p 'test_*.py' -v`

Result: **Ran 46 tests in 1.302s — OK.** The focused preprocessing tests include checks that the new skip flag defaults to the old behavior and only payable-tagged crops skip vertical-rule removal.

## Acceptance note

Overall diagnostics are **FAIL** only for the requirement that every component-covered payable be `EXTRACTED`: invoice #33 has the expected 11/11 components but remains `REVIEW` in its held-out fold. EXTRACTED-but-wrong is 0 and the arithmetic gate passes 3/4 folds. Per the task instruction, no threshold or classifier changes were made after this result.
