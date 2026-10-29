# E-28 DR-1: per-symbol Glyph drift monitor

DR-1 measures glyph-distance drift at the adapter boundary. For each image run that reaches numeric-cell recognition, the pipeline groups `GlyphReading.distance` values by their predicted `best_label` and records the mean and glyph count for every observed symbol. The record is available as `PipelineResult.glyph_drift`; callers that serialize a pipeline result can opt in with `to_dict(include_glyph_drift=True)`. Capture-folder output includes the record under each page's `e02.glyph_drift`. Image-mode CLI callers can persist it with `--drift-report PATH`; ordinary Canonical JSON stdout remains unchanged.

The monitor is fail-closed. It compares the invoice's per-symbol means with a baseline tied to the exact Glyph template-bank SHA-256. A missing or malformed baseline, a template-bank mismatch, an unseen symbol, or a measured deviation above its bound sets pipeline `status=REVIEW` and the exact `reason` **`onboarding required`**. On a drift hold, every numeric cell is downgraded to `REVIEW`, no Canonical Invoice candidate is emitted, and operator corrections cannot remove the hold. The monitor never edits the recognized text, never upgrades a result, and does not modify the frozen Canonical Invoice schema or the legacy adapter.

## Bound derivation and current fixture baseline

`src/glyph_drift_baseline_v1.json` is a deterministic, fixture-derived baseline tied to template library `b42688770113faaba9e4024e3af66fa4eed2cb039d184daff6429e0cef047931` (`baseline_id=e28-5b3684f43b60a9936f2c`). The baseline uses four operator-confirmed repository invoices (fixtures 29, 31, 32, and 33). For each symbol, it takes the equal-weight average of each source invoice's own mean distance; a long invoice therefore cannot dominate the per-invoice mean.

The per-symbol drift bound is measured, not hand-selected: it is the maximum absolute deviation from that baseline mean across 16 clean controls (four source invoices × four variants: identity, brightness ×1.01, contrast ×1.01, and numeric-cell Gaussian blur radius 0.75). A trigger uses strict `delta > bound` with a `1e-8` tolerance only for eight-decimal JSON serialization. The table gives the baseline mean and resulting bound:

| Symbol | Baseline mean | Clean-control bound |
|---|---:|---:|
| `,` | 0.00000786 | 0.00643404 |
| `۰` | 0.00000594 | 0.00000155 |
| `۱` | 0.00000942 | 0.00000248 |
| `۲` | 0.00005900 | 0.00399656 |
| `۳` | 0.00004154 | 0.00198730 |
| `۴` | 0.00004258 | 0.00588463 |
| `۵` | 0.00004928 | 0.00861828 |
| `۶` | 0.00007262 | 0.00002738 |
| `۷` | 0.00004001 | 0.00372130 |
| `۸` | 0.00003218 | 0.00357155 |
| `۹` | 0.00003333 | 0.00594524 |

The deterministic synthetic stress controls were evaluated on all four fixtures. Thinning (`MaxFilter(3)`) triggered in 4/4 samples, with minimum excess over a symbol's bound of 0.17766031; numeric-cell Gaussian blur radius 1.0 triggered in 4/4, minimum excess 0.02259682; and deterministic 2% salt/pepper noise inside numeric crops triggered in 4/4, minimum excess 0.00065771. Clean controls did not trigger. These are synthetic calibration tests, not claims about authentic printer/scanner degradation or a production store's onboarding distribution.

## Building a deployment onboarding baseline

Use the active Glyph bank and already-accepted local onboarding images:

```bash
PYTHONPATH=src:scripts python scripts/build_e28_drift_baseline.py \
  --templates /path/to/templates.json \
  --images /path/to/onboarding-1.png /path/to/onboarding-2.png \
  --output /path/to/templates.drift.json
```

The output stores sample IDs and SHA-256 digests, aggregate per-symbol means, data-derived bounds, and control results; it does not copy invoice images or store paths. The baseline's `template_library_id` must match the active bank. For the repository default bank the standard baseline is loaded automatically. A custom bank uses a companion `<bank-stem>.drift.json` or an explicitly supplied `--drift-baseline`; a byte-identical copy of the default bank can reuse the default baseline by its exact hash. Absence/mismatch routes to REVIEW.

The repository baseline is a reproducible acceptance fixture, not a substitute for a store-specific production onboarding baseline. Rebuild it from the target store's accepted images before production use.

## Verification

`tests/test_e28_drift_monitor.py` checks baseline schema/provenance, four accepted fixtures and zero EXTRACTED-but-wrong cells, clean variation pass-through, synthetic thinning/blur/noise holds, missing-baseline fail-closed behavior, correction non-bypass, and deterministic baseline regeneration. The CLI sidecar test confirms DR-1 metrics are persisted without contaminating Canonical JSON stdout.
