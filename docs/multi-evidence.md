# E-07 — Multi-evidence acceptance

## 1. Overview

E-07 adds an optional, conservative acceptance gate over the E-09 extraction result. The gate combines the existing arithmetic sum check with five additional witnesses: Persian thousands grouping, layout row count, Glyph distance, Glyph margin, and absence of `?` in numeric values.

The new CLI option is `--multi-evidence`. It is **off by default**, so invocations without the option retain the existing E-09 behavior. With the option enabled, an `AUTO_CANDIDATE` is retained only when all six witnesses pass. A failed witness downgrades the CLI result to `REVIEW`; an existing `REVIEW` is never upgraded and `REJECT` continues to use the existing exit code 20 behavior.

The evaluator is `image_extraction_adapter.multi_evidence.evaluate_multi_evidence(cell_results, gate_result, layout_result)`. It returns `MultiEvidenceResult` with a named witness dictionary, `all_pass`, status `AUTO_CANDIDATE` or `REVIEW`, and a list of failed witness names.

## 2. Witnesses

| Witness | What it checks | Pass condition |
|---|---|---|
| `sum_gate` | Existing arithmetic cross-check | `gate_result.passed is True`. |
| `thousands_pattern` | Numeric cell spelling and Persian comma grouping | Every value contains Persian digits. Values with fewer than four digits are ungrouped; values with four or more digits use 1–3 leading digits followed by comma-separated groups of exactly three. Thus `۷,۴۶۰,۰۰۰` passes; `۷۴۶۰۰۰۰` and `۷,۴۶,۰۰۰` fail. A `?` is removed only while checking the grouping witness so `no_question_mark` can report that independent failure; it still prevents overall acceptance. |
| `row_count` | Detected layout rows against extracted invoice lines | `layout_result.row_count` equals the count of complete line rows with both `line.N.quantity` and `line.N.total` marked `EXTRACTED`. |
| `glyph_distance` | Every glyph distance against the existing classifier maximum | Each explicit score is `<= DEFAULT_MAX_DISTANCE` (currently 0.25). When normal E-09 `CellOCRVariantResult` summaries are supplied, `EXTRACTED` is the existing classifier's certificate that every glyph passed; a REVIEW cell is not accepted except a cell downgraded solely by the arithmetic gate. |
| `glyph_margin` | Every glyph margin against the existing classifier minimum | Each explicit score is `>= DEFAULT_MIN_MARGIN` (currently 0.15). The same upstream-certificate rule applies when raw scores are not present in the pipeline summary. |
| `no_question_mark` | Unrecognized glyph marker in numeric cell values | No numeric cell string contains `?`; missing/non-string values fail closed. |

All six are evaluated and reported, even when one fails. The evaluator does not alter cell values, thresholds, or classifier output.

## 3. AUTO-candidate logic

The result is `AUTO_CANDIDATE` if and only if all six witness entries have `passed=True`. Otherwise it is `REVIEW`, and `reasons` lists each failed witness name. The CLI applies the result only when `--multi-evidence` is supplied:

- Pipeline `AUTO_CANDIDATE` + all six pass → remain `AUTO_CANDIDATE` (exit 0 with valid Canonical JSON).
- Pipeline `AUTO_CANDIDATE` + any witness fails → effective `REVIEW` (exit 10); if the pipeline supplied a valid candidate, the existing E-09 behavior emits that candidate and writes witness diagnostics to stderr.
- Pipeline `REVIEW` remains `REVIEW`, even if the six checks pass.
- Pipeline `REJECT` remains `REJECT` (exit 20).
- Without `--multi-evidence`, the multi-evidence evaluator is not called and the prior CLI status behavior is unchanged.

## 4. Compensating errors and how multi-evidence catches them

The injected test changes two line totals in opposite directions while keeping the payable fixed:

```text
line 0: 1,450,000 → 1,451,000  (+1,000)
line 1: 4,870,000 → 4,869,000  (-1,000)
line 2:   570,000
line 3:   570,000
payable: 7,460,000
```

The altered sum still equals the payable (`1,451,000 + 4,869,000 + 570,000 + 570,000 = 7,460,000`), so `sum_gate` passes. Grouping, four-row count, and no-`?` checks also pass. The test injects a first glyph distance above 0.25 and a second glyph margin below 0.15; `glyph_distance` and `glyph_margin` fail and the combined result is `REVIEW`. This demonstrates that compensating numeric errors cannot pass solely because their sum reconciles when the glyph evidence itself is doubtful.

Separate unit tests isolate each witness, including the invalid grouping examples above, a 5-versus-4 row-count mismatch, each classifier threshold independently, and `?۴۶۰,۰۰۰` (caught by `no_question_mark`).

## 5. Integration with `pipeline_v0`

Integration is at the E-09 CLI boundary rather than in `pipeline_v0.py`: after `extract_pipeline_v0` returns, the CLI passes `result.cell_results`, `result.arithmetic_gate`, and the result's `row_count` to `evaluate_multi_evidence` when the flag is on. A failed check can only downgrade an AUTO result; it cannot create or repair a Canonical Invoice candidate.

`PipelineResult` exposes `CellOCRVariantResult` summaries, not the raw `GlyphReading` floats. The evaluator supports cells that carry explicit `glyph_readings`/`readings` for direct distance and margin checks (used by the injected unit tests). For the actual E-09 pipeline output, the existing Glyph classifier's `EXTRACTED` status is used as the certificate: its current classifier marks a cell EXTRACTED only after each glyph passed its distance and margin thresholds. A non-gate REVIEW cell is not treated as such a certificate and stays REVIEW. This keeps the CLI integration on existing result data without rerunning OCR or modifying `pipeline_v0.py`.

`pipeline_v0.py`, `adapter.py`, `canonical_invoice.py`, and frozen contracts are unchanged. The new behavior is opt-in; all existing CLI callers retain their previous default.

## 6. Leave-one-out results

Four-fold leave-one-invoice-out evaluation used the confirmed labels in `tests/fixtures/real/labels.json`, rebuilding templates from the other three fixtures for each held-out invoice. The pre-change baseline was recorded with `run_leave_one_out_evaluation`; the multi-evidence counts were then computed by applying the new evaluator to each equivalent fold `PipelineResult`.

| Held-out invoice | Baseline pipeline | Sum | Grouping | Row count | Distance | Margin | No `?` | After multi-evidence | EXTRACTED-but-wrong |
|---:|---|---:|---:|---:|---:|---:|---:|---|---:|
| 29 | AUTO_CANDIDATE | PASS | PASS | PASS | PASS | PASS | PASS | AUTO_CANDIDATE | 0 |
| 31 | AUTO_CANDIDATE | PASS | PASS | PASS | PASS | PASS | PASS | AUTO_CANDIDATE | 0 |
| 32 | AUTO_CANDIDATE | PASS | PASS | PASS | PASS | PASS | PASS | AUTO_CANDIDATE | 0 |
| 33 | REVIEW | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | REVIEW | 0 |

- **AUTO-candidate folds:** 3/4 before; 3/4 after multi-evidence.
- **EXTRACTED-but-wrong:** 0 before and 0 after across 35 independent labelled cell comparisons (the existing evaluation excludes the derived payable label where applicable).
- Fold 33 was already REVIEW: the arithmetic gate failed and multiple cells were not EXTRACTED, so the added witnesses preserved REVIEW. The multi-evidence gate did not reduce the three passing folds in this dataset.

The LOO `PipelineResult` path carries classifier status summaries rather than raw distance/margin floats, so those two fold witnesses rely on the existing classifier certificate described in Section 5. Direct numeric boundary checks and the compensating-error case exercise the raw-score branch.

## 7. What is NOT included

- No threshold tuning: the existing defaults `DEFAULT_MAX_DISTANCE=0.25` and `DEFAULT_MIN_MARGIN=0.15` are used unchanged.
- No automatic correction, normalization of incorrect OCR, arithmetic repair, or guessed values.
- No changes to `pipeline_v0.py`, `adapter.py`, `canonical_invoice.py`, or frozen contracts.
- No Tesseract/network dependency; this remains an optional local Glyph-path gate.
- No change to default CLI behavior. The stricter decision is activated only with `--multi-evidence`.
- No independent new source of raw glyph measurements in `PipelineResult`; the implementation uses the existing EXTRACTED certificate unless a caller supplies explicit reading evidence.

Verification: all 11 new multi-evidence tests passed; the complete `unittest` discovery run passed all 117 tests (the existing 106 plus 11 new tests).

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m unittest discover -s src -p 'test_*.py' -v
Ran 117 tests in 3.292s
OK
```

The new test cases are `test_all_six_witnesses_pass`, `test_sum_gate_failure_alone_returns_review`, `test_thousands_pattern_valid_and_invalid_groupings`, `test_short_persian_values_need_no_grouping`, `test_row_count_mismatch_alone_returns_review`, `test_glyph_distance_above_existing_maximum_alone_returns_review`, `test_glyph_margin_below_existing_minimum_alone_returns_review`, `test_question_mark_fails_its_witness_without_hiding_grouping_result`, `test_compensating_errors_pass_sum_but_fail_glyph_witnesses`, `test_extracted_pipeline_cells_certify_existing_distance_and_margin_gate`, and `test_cli_flag_downgrades_candidate_and_default_behavior_is_unchanged`.
