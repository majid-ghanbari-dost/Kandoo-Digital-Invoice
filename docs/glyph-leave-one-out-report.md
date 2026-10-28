## T2 Leave-One-Out Evaluation Report

### Methodology

Four-fold leave-one-invoice-out evaluation. Each fold builds Glyph templates from all rows and numeric labels in the other three invoices, then evaluates the held-out invoice. The build and evaluate CLI are run in separate temporary label/template directories. The evaluate command does not receive `--allow-leakage`; the classifier's leakage guard remains enabled. Exact-cell/CER/arithmetic/calibration metrics come from the existing evaluator. EXTRACTED-but-wrong counts are computed from its per-cell status and `digits_match_reference` output.

Payable value for invoice #31 is labeled `DERIVED_FROM_ARITHMETIC` as supplied by the operator. It is included in the fold metrics and gate checks, but is not an independent visual ground-truth label.

### Results per Fold

| fold | held_out | templates | exact_cells | total_cells | CER | gate_passed | extracted_but_wrong | cells_by_status |
|---|---:|---:|---:|---:|---:|---|---:|---|
| fold-1 | 29 | 22 | 8 | 9 | 2.70% | False | 0 | EXTRACTED=4, REVIEW=5 |
| fold-2 | 31 | 22 | 6 | 7 | 10.71% | False | 0 | EXTRACTED=3, REVIEW=4 |
| fold-3 | 32 | 17 | 10 | 11 | 2.33% | False | 0 | EXTRACTED=5, REVIEW=6 |
| fold-4 | 33 | 15 | 19 | 27 | 10.83% | False | 0 | EXTRACTED=9, REVIEW=18 |

### Total

| fold | held_out | templates | exact_cells | total_cells | CER | gate_passed | extracted_but_wrong |
|---|---:|---:|---:|---:|---:|---|---:|
| TOTAL | 4-fold | — | 43 | 54 | 7.89% | 0/4 | 0 |

### Calibration Lines

#### fold-1 (held-out #29)
`calibration.best_label_correct.distance n=36 min=0.000 max=0.000`
`calibration.best_label_correct.margin   n=36 min=0.198 max=0.864`
`calibration.best_label_wrong.distance   n=0`
`calibration.best_label_wrong.margin   n=0`

#### fold-2 (held-out #31)
`calibration.best_label_correct.distance n=24 min=0.000 max=0.000`
`calibration.best_label_correct.margin   n=24 min=0.198 max=0.864`
`calibration.best_label_wrong.distance   n=0`
`calibration.best_label_wrong.margin   n=0`

#### fold-3 (held-out #32)
`calibration.best_label_correct.distance n=52 min=0.000 max=0.168`
`calibration.best_label_correct.margin   n=52 min=0.135 max=0.864`
`calibration.best_label_wrong.distance   n=0`
`calibration.best_label_wrong.margin   n=0`

#### fold-4 (held-out #33)
`calibration.best_label_correct.distance n=128 min=0.000 max=0.164`
`calibration.best_label_correct.margin   n=128 min=0.153 max=0.864`
`calibration.best_label_wrong.distance   n=9 min=0.198 max=0.319`
`calibration.best_label_wrong.margin   n=9 min=0.022 max=0.052`

### Known Limitations

- Payable templates only built successfully from 1 invoice (5.png / #32). Other invoices' payable crops had component-count mismatches. Payable cells are REVIEW in most folds.
- 31.png payable label is DERIVED_FROM_ARITHMETIC, not directly operator-confirmed from the image.
- Tesseract binary not available; full-page OCR path not tested.
- The reported cell coverage is limited to cells emitted by the projection/cropper and evaluator. REVIEW cells are not counted as EXTRACTED-but-wrong.

### Acceptance

EXTRACTED-but-wrong = 0 in all 4 folds: PASS

### Raw Fold Output

The following are the complete build/evaluate commands and their combined stdout/stderr for every fold.

#### fold-1: build (held-out #29)

`/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier build --labels /tmp/glyph-loo-29-m8wzol_9/train-labels.json --out /tmp/glyph-loo-29-m8wzol_9/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/31.png
  USED line.0.total: ۹۷۰,۰۰۰ (+4 new templates)
  USED line.0.quantity: ۱ (+1 new templates)
  USED line.1.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۴۸۵,۰۰۰ (+3 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 12 components != 9 symbols in '۲,۴۲۵,۰۰۰'
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/32.png
  USED line.0.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.0.quantity: ۱ (+0 new templates)
  USED line.1.total: ۳,۹۵۰,۰۰۰ (+1 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۱,۸۷۰,۰۰۰ (+1 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED line.3.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.3.quantity: ۱ (+0 new templates)
  USED line.4.total: ۹۰,۰۰۰ (+0 new templates)
  USED line.4.quantity: ۱ (+0 new templates)
  USED invoice.payable: ۷,۸۵۰,۰۰۰ (+5 new templates)
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/33.png
  USED line.0.total: ۷,۸۸۰,۰۰۰ (+0 new templates)
  USED line.0.quantity: ۴ (+1 new templates)
  USED line.1.total: ۴,۸۵۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱۰ (+1 new templates)
  USED line.2.total: ۸,۷۵۰,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۵ (+1 new templates)
  USED line.3.total: ۶,۴۰۰,۰۰۰ (+1 new templates)
  USED line.3.quantity: ۲ (+1 new templates)
  USED line.4.total: ۴۹,۴۰۰,۰۰۰ (+0 new templates)
  USED line.4.quantity: ۲۰ (+0 new templates)
  USED line.5.total: ۱,۵۷۰,۰۰۰ (+0 new templates)
  USED line.5.quantity: ۱ (+0 new templates)
  USED line.6.total: ۶,۹۰۰,۰۰۰ (+0 new templates)
  USED line.6.quantity: ۵ (+0 new templates)
  USED line.7.total: ۶,۸۷۰,۰۰۰ (+0 new templates)
  USED line.7.quantity: ۱ (+0 new templates)
  USED line.8.total: ۳,۷۰۰,۰۰۰ (+0 new templates)
  USED line.8.quantity: ۲ (+0 new templates)
  USED line.9.total: ۲۲۹,۶۰۰,۰۰۰ (+1 new templates)
  USED line.9.quantity: ۸ (+1 new templates)
  USED line.10.total: ۱۹,۰۵۰,۰۰۰ (+0 new templates)
  USED line.10.quantity: ۱۵ (+0 new templates)
  USED line.11.total: ۱,۳۸۰,۰۰۰ (+0 new templates)
  USED line.11.quantity: ۱ (+0 new templates)
  USED line.12.total: ۱,۵۷۰,۰۰۰ (+0 new templates)
  USED line.12.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 15 components != 11 symbols in '۳۴۷,۹۲۰,۰۰۰'
profile row: ,x1 ۰x2 ۱x2 ۲x2 ۳x1 ۴x2 ۵x2 ۶x1 ۷x1 ۸x2 ۹x1
profile payable: ,x1 ۰x1 ۵x1 ۷x1 ۸x1
saved /tmp/glyph-loo-29-m8wzol_9/templates.json
<frozen runpy>:128: RuntimeWarning: 'image_extraction_adapter.glyph_classifier' found in sys.modules after import of package 'image_extraction_adapter', but prior to execution of 'image_extraction_adapter.glyph_classifier'; this may result in unpredictable behaviour
```

#### fold-1: evaluate (held-out #29)

`/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier evaluate --labels /tmp/glyph-loo-29-m8wzol_9/test-labels.json --templates /tmp/glyph-loo-29-m8wzol_9/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/29.png
  line.0.total|glyph|raw='۱,۴۵۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۱,۴۵۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '۷,??۶۰,۰۰۰' is not a well-formed amount"
  line.0.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.1.total|glyph|raw='۴,۸۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۴,۸۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '۷,??۶۰,۰۰۰' is not a well-formed amount"
  line.1.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.2.total|glyph|raw='۵۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۵۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '۷,??۶۰,۰۰۰' is not a well-formed amount"
  line.2.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.3.total|glyph|raw='۵۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۵۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '۷,??۶۰,۰۰۰' is not a well-formed amount"
  line.3.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  invoice.payable|glyph|raw='۷,??۶۰,۰۰۰'|confidence=0.0|status=REVIEW|reference='۷,۴۶۰,۰۰۰'|digits_match_reference=False|reason="glyph 3 not accepted: distance 0.393 exceeds 0.250; glyph 4 not accepted: distance 0.446 exceeds 0.250; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: payable '۷,??۶۰,۰۰۰' is not a well-formed amount"
  arithmetic_gate passed=False line_sum=None payable=None extra=0 reason=payable '۷,??۶۰,۰۰۰' is not a well-formed amount
metric.definition=exact match and CER on digit strings; separators ignored for scoring only
metrics.glyph.exact_digit_cells=8/9 digit_CER=2.70%
metrics.glyph.segmentation_mismatch_cells=1
metrics.glyph.arithmetic_gate_passed=0/1
calibration.best_label_correct.distance n=36 min=0.000 max=0.000
calibration.best_label_correct.margin   n=36 min=0.198 max=0.864
calibration.best_label_wrong.distance   n=0
calibration.best_label_wrong.margin   n=0
<frozen runpy>:128: RuntimeWarning: 'image_extraction_adapter.glyph_classifier' found in sys.modules after import of package 'image_extraction_adapter', but prior to execution of 'image_extraction_adapter.glyph_classifier'; this may result in unpredictable behaviour
```

#### fold-2: build (held-out #31)

`/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier build --labels /tmp/glyph-loo-31-ncpftyuy/train-labels.json --out /tmp/glyph-loo-31-ncpftyuy/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/29.png
  USED line.0.total: ۱,۴۵۰,۰۰۰ (+5 new templates)
  USED line.0.quantity: ۱ (+1 new templates)
  USED line.1.total: ۴,۸۷۰,۰۰۰ (+2 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۵۷۰,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED line.3.total: ۵۷۰,۰۰۰ (+0 new templates)
  USED line.3.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 10 components != 9 symbols in '۷,۴۶۰,۰۰۰'
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/32.png
  USED line.0.total: ۹۷۰,۰۰۰ (+1 new templates)
  USED line.0.quantity: ۱ (+0 new templates)
  USED line.1.total: ۳,۹۵۰,۰۰۰ (+1 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۱,۸۷۰,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED line.3.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.3.quantity: ۱ (+0 new templates)
  USED line.4.total: ۹۰,۰۰۰ (+0 new templates)
  USED line.4.quantity: ۱ (+0 new templates)
  USED invoice.payable: ۷,۸۵۰,۰۰۰ (+5 new templates)
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/33.png
  USED line.0.total: ۷,۸۸۰,۰۰۰ (+0 new templates)
  USED line.0.quantity: ۴ (+1 new templates)
  USED line.1.total: ۴,۸۵۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱۰ (+1 new templates)
  USED line.2.total: ۸,۷۵۰,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۵ (+1 new templates)
  USED line.3.total: ۶,۴۰۰,۰۰۰ (+1 new templates)
  USED line.3.quantity: ۲ (+1 new templates)
  USED line.4.total: ۴۹,۴۰۰,۰۰۰ (+0 new templates)
  USED line.4.quantity: ۲۰ (+0 new templates)
  USED line.5.total: ۱,۵۷۰,۰۰۰ (+0 new templates)
  USED line.5.quantity: ۱ (+0 new templates)
  USED line.6.total: ۶,۹۰۰,۰۰۰ (+0 new templates)
  USED line.6.quantity: ۵ (+0 new templates)
  USED line.7.total: ۶,۸۷۰,۰۰۰ (+0 new templates)
  USED line.7.quantity: ۱ (+0 new templates)
  USED line.8.total: ۳,۷۰۰,۰۰۰ (+0 new templates)
  USED line.8.quantity: ۲ (+0 new templates)
  USED line.9.total: ۲۲۹,۶۰۰,۰۰۰ (+1 new templates)
  USED line.9.quantity: ۸ (+1 new templates)
  USED line.10.total: ۱۹,۰۵۰,۰۰۰ (+0 new templates)
  USED line.10.quantity: ۱۵ (+0 new templates)
  USED line.11.total: ۱,۳۸۰,۰۰۰ (+0 new templates)
  USED line.11.quantity: ۱ (+0 new templates)
  USED line.12.total: ۱,۵۷۰,۰۰۰ (+0 new templates)
  USED line.12.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 15 components != 11 symbols in '۳۴۷,۹۲۰,۰۰۰'
profile row: ,x1 ۰x2 ۱x2 ۲x2 ۳x1 ۴x2 ۵x2 ۶x1 ۷x1 ۸x2 ۹x1
profile payable: ,x1 ۰x1 ۵x1 ۷x1 ۸x1
saved /tmp/glyph-loo-31-ncpftyuy/templates.json
<frozen runpy>:128: RuntimeWarning: 'image_extraction_adapter.glyph_classifier' found in sys.modules after import of package 'image_extraction_adapter', but prior to execution of 'image_extraction_adapter.glyph_classifier'; this may result in unpredictable behaviour
```

#### fold-2: evaluate (held-out #31)

`/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier evaluate --labels /tmp/glyph-loo-31-ncpftyuy/test-labels.json --templates /tmp/glyph-loo-31-ncpftyuy/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/31.png
  line.0.total|glyph|raw='۹۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۹۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '??,????۵,۰۰۰' is not a well-formed amount"
  line.0.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.1.total|glyph|raw='۹۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۹۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '??,????۵,۰۰۰' is not a well-formed amount"
  line.1.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.2.total|glyph|raw='۴۸۵,۰۰۰'|confidence=100.0|status=REVIEW|reference='۴۸۵,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '??,????۵,۰۰۰' is not a well-formed amount"
  line.2.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  invoice.payable|glyph|raw='??,????۵,۰۰۰'|confidence=0.0|status=REVIEW|reference='۲,۴۲۵,۰۰۰'|digits_match_reference=False|reason="glyph 1 not accepted: distance 0.308 exceeds 0.250; glyph 2 not accepted: distance 0.452 exceeds 0.250; glyph 4 not accepted: distance 0.308 exceeds 0.250; glyph 5 not accepted: distance 0.434 exceeds 0.250; glyph 6 not accepted: distance 0.308 exceeds 0.250; glyph 7 not accepted: distance 0.452 exceeds 0.250; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: payable '??,????۵,۰۰۰' is not a well-formed amount"
  arithmetic_gate passed=False line_sum=None payable=None extra=0 reason=payable '??,????۵,۰۰۰' is not a well-formed amount
metric.definition=exact match and CER on digit strings; separators ignored for scoring only
metrics.glyph.exact_digit_cells=6/7 digit_CER=10.71%
metrics.glyph.segmentation_mismatch_cells=1
metrics.glyph.arithmetic_gate_passed=0/1
calibration.best_label_correct.distance n=24 min=0.000 max=0.000
calibration.best_label_correct.margin   n=24 min=0.198 max=0.864
calibration.best_label_wrong.distance   n=0
calibration.best_label_wrong.margin   n=0
<frozen runpy>:128: RuntimeWarning: 'image_extraction_adapter.glyph_classifier' found in sys.modules after import of package 'image_extraction_adapter', but prior to execution of 'image_extraction_adapter.glyph_classifier'; this may result in unpredictable behaviour
```

#### fold-3: build (held-out #32)

`/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier build --labels /tmp/glyph-loo-32-b39qcz24/train-labels.json --out /tmp/glyph-loo-32-b39qcz24/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/29.png
  USED line.0.total: ۱,۴۵۰,۰۰۰ (+5 new templates)
  USED line.0.quantity: ۱ (+1 new templates)
  USED line.1.total: ۴,۸۷۰,۰۰۰ (+2 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۵۷۰,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED line.3.total: ۵۷۰,۰۰۰ (+0 new templates)
  USED line.3.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 10 components != 9 symbols in '۷,۴۶۰,۰۰۰'
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/31.png
  USED line.0.total: ۹۷۰,۰۰۰ (+1 new templates)
  USED line.0.quantity: ۱ (+0 new templates)
  USED line.1.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۴۸۵,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 12 components != 9 symbols in '۲,۴۲۵,۰۰۰'
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/33.png
  USED line.0.total: ۷,۸۸۰,۰۰۰ (+0 new templates)
  USED line.0.quantity: ۴ (+1 new templates)
  USED line.1.total: ۴,۸۵۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱۰ (+1 new templates)
  USED line.2.total: ۸,۷۵۰,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۵ (+1 new templates)
  USED line.3.total: ۶,۴۰۰,۰۰۰ (+1 new templates)
  USED line.3.quantity: ۲ (+1 new templates)
  USED line.4.total: ۴۹,۴۰۰,۰۰۰ (+0 new templates)
  USED line.4.quantity: ۲۰ (+0 new templates)
  USED line.5.total: ۱,۵۷۰,۰۰۰ (+0 new templates)
  USED line.5.quantity: ۱ (+0 new templates)
  USED line.6.total: ۶,۹۰۰,۰۰۰ (+0 new templates)
  USED line.6.quantity: ۵ (+0 new templates)
  USED line.7.total: ۶,۸۷۰,۰۰۰ (+0 new templates)
  USED line.7.quantity: ۱ (+0 new templates)
  USED line.8.total: ۳,۷۰۰,۰۰۰ (+1 new templates)
  USED line.8.quantity: ۲ (+0 new templates)
  USED line.9.total: ۲۲۹,۶۰۰,۰۰۰ (+1 new templates)
  USED line.9.quantity: ۸ (+1 new templates)
  USED line.10.total: ۱۹,۰۵۰,۰۰۰ (+0 new templates)
  USED line.10.quantity: ۱۵ (+0 new templates)
  USED line.11.total: ۱,۳۸۰,۰۰۰ (+0 new templates)
  USED line.11.quantity: ۱ (+0 new templates)
  USED line.12.total: ۱,۵۷۰,۰۰۰ (+0 new templates)
  USED line.12.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 15 components != 11 symbols in '۳۴۷,۹۲۰,۰۰۰'
profile row: ,x1 ۰x2 ۱x2 ۲x2 ۳x1 ۴x2 ۵x2 ۶x1 ۷x1 ۸x2 ۹x1
saved /tmp/glyph-loo-32-b39qcz24/templates.json
<frozen runpy>:128: RuntimeWarning: 'image_extraction_adapter.glyph_classifier' found in sys.modules after import of package 'image_extraction_adapter', but prior to execution of 'image_extraction_adapter.glyph_classifier'; this may result in unpredictable behaviour
```

#### fold-3: evaluate (held-out #32)

`/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier evaluate --labels /tmp/glyph-loo-32-b39qcz24/test-labels.json --templates /tmp/glyph-loo-32-b39qcz24/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/32.png
  line.0.total|glyph|raw='۹۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۹۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '?,۸۵۰,۰۰۰' is not a well-formed amount"
  line.0.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.1.total|glyph|raw='۳,۹۵۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۳,۹۵۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '?,۸۵۰,۰۰۰' is not a well-formed amount"
  line.1.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.2.total|glyph|raw='۱,۸۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۱,۸۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '?,۸۵۰,۰۰۰' is not a well-formed amount"
  line.2.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.3.total|glyph|raw='۹۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۹۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '?,۸۵۰,۰۰۰' is not a well-formed amount"
  line.3.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.4.total|glyph|raw='۹۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۹۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: payable '?,۸۵۰,۰۰۰' is not a well-formed amount"
  line.4.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  invoice.payable|glyph|raw='?,۸۵۰,۰۰۰'|confidence=0.0|status=REVIEW|reference='۷,۸۵۰,۰۰۰'|digits_match_reference=False|reason="glyph 1 not accepted: ambiguous: margin 0.135 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: payable '?,۸۵۰,۰۰۰' is not a well-formed amount"
  arithmetic_gate passed=False line_sum=None payable=None extra=0 reason=payable '?,۸۵۰,۰۰۰' is not a well-formed amount
metric.definition=exact match and CER on digit strings; separators ignored for scoring only
metrics.glyph.exact_digit_cells=10/11 digit_CER=2.33%
metrics.glyph.segmentation_mismatch_cells=0
metrics.glyph.arithmetic_gate_passed=0/1
calibration.best_label_correct.distance n=52 min=0.000 max=0.168
calibration.best_label_correct.margin   n=52 min=0.135 max=0.864
calibration.best_label_wrong.distance   n=0
calibration.best_label_wrong.margin   n=0
<frozen runpy>:128: RuntimeWarning: 'image_extraction_adapter.glyph_classifier' found in sys.modules after import of package 'image_extraction_adapter', but prior to execution of 'image_extraction_adapter.glyph_classifier'; this may result in unpredictable behaviour
```

#### fold-4: build (held-out #33)

`/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier build --labels /tmp/glyph-loo-33-9ca0mrx1/train-labels.json --out /tmp/glyph-loo-33-9ca0mrx1/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/29.png
  USED line.0.total: ۱,۴۵۰,۰۰۰ (+5 new templates)
  USED line.0.quantity: ۱ (+1 new templates)
  USED line.1.total: ۴,۸۷۰,۰۰۰ (+2 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۵۷۰,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED line.3.total: ۵۷۰,۰۰۰ (+0 new templates)
  USED line.3.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 10 components != 9 symbols in '۷,۴۶۰,۰۰۰'
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/31.png
  USED line.0.total: ۹۷۰,۰۰۰ (+1 new templates)
  USED line.0.quantity: ۱ (+0 new templates)
  USED line.1.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۴۸۵,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  SKIP invoice.payable: 12 components != 9 symbols in '۲,۴۲۵,۰۰۰'
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/32.png
  USED line.0.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.0.quantity: ۱ (+0 new templates)
  USED line.1.total: ۳,۹۵۰,۰۰۰ (+1 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۱,۸۷۰,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED line.3.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.3.quantity: ۱ (+0 new templates)
  USED line.4.total: ۹۰,۰۰۰ (+0 new templates)
  USED line.4.quantity: ۱ (+0 new templates)
  USED invoice.payable: ۷,۸۵۰,۰۰۰ (+5 new templates)
profile row: ,x1 ۰x1 ۱x2 ۳x1 ۴x1 ۵x1 ۷x1 ۸x1 ۹x1
profile payable: ,x1 ۰x1 ۵x1 ۷x1 ۸x1
WARNING: row profile has no template for: ۲ ۶
saved /tmp/glyph-loo-33-9ca0mrx1/templates.json
<frozen runpy>:128: RuntimeWarning: 'image_extraction_adapter.glyph_classifier' found in sys.modules after import of package 'image_extraction_adapter', but prior to execution of 'image_extraction_adapter.glyph_classifier'; this may result in unpredictable behaviour
```

#### fold-4: evaluate (held-out #33)

`/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier evaluate --labels /tmp/glyph-loo-33-9ca0mrx1/test-labels.json --templates /tmp/glyph-loo-33-9ca0mrx1/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/33.png
  line.0.total|glyph|raw='۷,۸۸۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۷,۸۸۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.0.quantity|glyph|raw='۴'|confidence=69.3|status=EXTRACTED|reference='۴'|digits_match_reference=True
  line.1.total|glyph|raw='۴,۸۵۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۴,۸۵۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.1.quantity|glyph|raw='۱۰'|confidence=34.3|status=REVIEW|reference='۱۰'|digits_match_reference=True|reason='cell OCR confidence 34.29 is below 60.00'
  line.2.total|glyph|raw='۸,۷۵۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۸,۷۵۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.2.quantity|glyph|raw='۵'|confidence=60.7|status=EXTRACTED|reference='۵'|digits_match_reference=True
  line.3.total|glyph|raw='?,۴۰۰,۰۰۰'|confidence=0.0|status=REVIEW|reference='۶,۴۰۰,۰۰۰'|digits_match_reference=False|reason="glyph 1 not accepted: distance 0.319 exceeds 0.250; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.3.quantity|glyph|raw='?'|confidence=0.0|status=REVIEW|reference='۲'|digits_match_reference=False|reason='glyph 1 not accepted: ambiguous: margin 0.026 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format'
  line.4.total|glyph|raw='۴۹,۴۰۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۴۹,۴۰۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.4.quantity|glyph|raw='?۰'|confidence=0.0|status=REVIEW|reference='۲۰'|digits_match_reference=False|reason='glyph 1 not accepted: ambiguous: margin 0.026 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format'
  line.5.total|glyph|raw='۱,۵۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۱,۵۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.5.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.6.total|glyph|raw='?,۹۰۰,۰۰۰'|confidence=0.0|status=REVIEW|reference='۶,۹۰۰,۰۰۰'|digits_match_reference=False|reason="glyph 1 not accepted: distance 0.319 exceeds 0.250; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.6.quantity|glyph|raw='۵'|confidence=60.7|status=EXTRACTED|reference='۵'|digits_match_reference=True
  line.7.total|glyph|raw='?,۸۷۰,۰۰۰'|confidence=0.0|status=REVIEW|reference='۶,۸۷۰,۰۰۰'|digits_match_reference=False|reason="glyph 1 not accepted: distance 0.319 exceeds 0.250; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.7.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.8.total|glyph|raw='۳,۷۰۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۳,۷۰۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.8.quantity|glyph|raw='?'|confidence=0.0|status=REVIEW|reference='۲'|digits_match_reference=False|reason='glyph 1 not accepted: ambiguous: margin 0.026 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format'
  line.9.total|glyph|raw='??۹,?۰۰,۰۰۰'|confidence=0.0|status=REVIEW|reference='۲۲۹,۶۰۰,۰۰۰'|digits_match_reference=False|reason="glyph 1 not accepted: ambiguous: margin 0.052 below 0.150; glyph 2 not accepted: ambiguous: margin 0.052 below 0.150; glyph 5 not accepted: distance 0.319 exceeds 0.250; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.9.quantity|glyph|raw='۸'|confidence=66.2|status=EXTRACTED|reference='۸'|digits_match_reference=True
  line.10.total|glyph|raw='۱۹,۰۵۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۱۹,۰۵۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.10.quantity|glyph|raw='۱۵'|confidence=60.7|status=EXTRACTED|reference='۱۵'|digits_match_reference=True
  line.11.total|glyph|raw='۱,۳۸۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۱,۳۸۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.11.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.12.total|glyph|raw='۱,۵۷۰,۰۰۰'|confidence=100.0|status=REVIEW|reference='۱,۵۷۰,۰۰۰'|digits_match_reference=True|reason="arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  line.12.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  invoice.payable|glyph|raw='????۷,????۰,۰۰۰'|confidence=0.0|status=REVIEW|reference='۳۴۷,۹۲۰,۰۰۰'|digits_match_reference=False|reason="glyph 1 not accepted: distance 0.644 exceeds 0.250; glyph 2 not accepted: distance 0.476 exceeds 0.250; glyph 3 not accepted: distance 0.308 exceeds 0.250; glyph 4 not accepted: distance 0.502 exceeds 0.250; glyph 7 not accepted: distance 0.887 exceeds 0.250; glyph 8 not accepted: distance 0.748 exceeds 0.250; glyph 9 not accepted: distance 0.308 exceeds 0.250; glyph 10 not accepted: distance 0.500 exceeds 0.250; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  arithmetic_gate passed=False line_sum=None payable=None extra=0 reason=line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount
metric.definition=exact match and CER on digit strings; separators ignored for scoring only
metrics.glyph.exact_digit_cells=19/27 digit_CER=10.83%
metrics.glyph.segmentation_mismatch_cells=1
metrics.glyph.arithmetic_gate_passed=0/1
calibration.best_label_correct.distance n=128 min=0.000 max=0.164
calibration.best_label_correct.margin   n=128 min=0.153 max=0.864
calibration.best_label_wrong.distance   n=9 min=0.198 max=0.319
calibration.best_label_wrong.margin   n=9 min=0.022 max=0.052
<frozen runpy>:128: RuntimeWarning: 'image_extraction_adapter.glyph_classifier' found in sys.modules after import of package 'image_extraction_adapter', but prior to execution of 'image_extraction_adapter.glyph_classifier'; this may result in unpredictable behaviour
```
