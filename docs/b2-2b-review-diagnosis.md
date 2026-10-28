# B2-2b — Diagnosis of correct cells marked REVIEW

## Evaluation setup

Four-fold leave-one-invoice-out evaluation: each fold builds templates from the other three invoices and evaluates only the held-out invoice. This script captures the existing `build` and `evaluate` CLI outputs and independently recomputes the same readings from the saved template bank to expose per-glyph details. In-process results are checked against the CLI's status, raw value, and `digits_match_reference` output.

Command: `PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python scripts/diagnose_b2_2b.py --labels tests/fixtures/real/labels.json --output docs/b2-2b-review-diagnosis.md`
Report path: `/home/user/Kandoo-Digital-Invoice/docs/b2-2b-review-diagnosis.md`
Thresholds used unchanged: max distance 0.25, minimum margin 0.15, minimum confidence 60.0. No classifier settings or defaults were changed.

Total evaluated numeric cells: 54; REVIEW: 18; REVIEW with `digits_match_reference=True`: **10**; correctly EXTRACTED: 36.

## 1. Per-cell REVIEW diagnosis

Condition flags are evaluated independently; a cell can fail more than one condition. The reason string shown is the final classifier result after the arithmetic gate, with the pre-gate reason included where relevant.

### total: `line.0.total` — fold-4, held-out #33

- Raw/reference: `۷,۸۸۰,۰۰۰` / `۷,۸۸۰,۰۰۰`; confidence `99.98`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۷': best='۷' distance=0.0000 margin=0.2256 second='۴' (0.2256) accepted=True bbox=(12, 7, 24, 27)`
  - `g2 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(27, 20, 32, 30)`
  - `g3 expected='۸': best='۸' distance=0.0000 margin=0.3744 second='۵' (0.3744) accepted=True bbox=(33, 7, 45, 27)`
  - `g4 expected='۸': best='۸' distance=0.0000 margin=0.3744 second='۵' (0.3744) accepted=True bbox=(47, 7, 59, 27)`
  - `g5 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(62, 15, 69, 22)`
  - `g6 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(73, 20, 78, 30)`
  - `g7 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(79, 15, 86, 22)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(89, 15, 96, 22)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(99, 15, 106, 22)`

### total: `line.1.total` — fold-4, held-out #33

- Raw/reference: `۴,۸۵۰,۰۰۰` / `۴,۸۵۰,۰۰۰`; confidence `99.99`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۴': best='۴' distance=0.0000 margin=0.2101 second='۳' (0.2101) accepted=True bbox=(13, 4, 25, 24)`
  - `g2 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(28, 17, 33, 27)`
  - `g3 expected='۸': best='۸' distance=0.0000 margin=0.3744 second='۵' (0.3744) accepted=True bbox=(34, 4, 46, 24)`
  - `g4 expected='۵': best='۵' distance=0.0000 margin=0.3744 second='۸' (0.3744) accepted=True bbox=(48, 4, 60, 24)`
  - `g5 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(62, 12, 69, 19)`
  - `g6 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(73, 17, 78, 27)`
  - `g7 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(79, 12, 86, 19)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(89, 12, 96, 19)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(99, 12, 106, 19)`

### quantity: `line.1.quantity` — fold-4, held-out #33

- Raw/reference: `۱۰` / `۱۰`; confidence `34.29`; status `REVIEW`.
- Final classifier reason: 'cell OCR confidence 34.29 is below 60.00'
- Pre-arithmetic-gate reason: 'cell OCR confidence 34.29 is below 60.00'
- Failed conditions: confidence < minimum_confidence.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۱': best='۱' distance=0.0000 margin=0.3256 second='۹' (0.3256) accepted=True bbox=(11, 6, 17, 27)`
  - `g2 expected='۰': best='۰' distance=0.1643 margin=0.6607 second=',' (0.8250) accepted=True bbox=(21, 14, 29, 22)`

### total: `line.2.total` — fold-4, held-out #33

- Raw/reference: `۸,۷۵۰,۰۰۰` / `۸,۷۵۰,۰۰۰`; confidence `99.98`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۸': best='۸' distance=0.0000 margin=0.3744 second='۵' (0.3744) accepted=True bbox=(12, 4, 24, 24)`
  - `g2 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(27, 17, 32, 27)`
  - `g3 expected='۷': best='۷' distance=0.0000 margin=0.2256 second='۴' (0.2256) accepted=True bbox=(33, 4, 45, 24)`
  - `g4 expected='۵': best='۵' distance=0.0000 margin=0.3744 second='۸' (0.3744) accepted=True bbox=(47, 4, 59, 24)`
  - `g5 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(62, 12, 69, 19)`
  - `g6 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(73, 17, 78, 27)`
  - `g7 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(79, 12, 86, 19)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(89, 12, 96, 19)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(99, 12, 106, 19)`

### total: `line.4.total` — fold-4, held-out #33

- Raw/reference: `۴۹,۴۰۰,۰۰۰` / `۴۹,۴۰۰,۰۰۰`; confidence `99.99`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۴': best='۴' distance=0.0000 margin=0.2101 second='۳' (0.2101) accepted=True bbox=(9, 4, 21, 24)`
  - `g2 expected='۹': best='۹' distance=0.0000 margin=0.3244 second='۱' (0.3244) accepted=True bbox=(23, 4, 32, 24)`
  - `g3 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(35, 17, 40, 27)`
  - `g4 expected='۴': best='۴' distance=0.0000 margin=0.2101 second='۳' (0.2101) accepted=True bbox=(41, 4, 53, 24)`
  - `g5 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(55, 12, 62, 19)`
  - `g6 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(66, 12, 73, 19)`
  - `g7 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(77, 17, 82, 27)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(83, 12, 90, 19)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(93, 12, 100, 19)`
  - `g10 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(103, 12, 110, 19)`

### total: `line.5.total` — fold-4, held-out #33

- Raw/reference: `۱,۵۷۰,۰۰۰` / `۱,۵۷۰,۰۰۰`; confidence `99.98`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۱': best='۱' distance=0.0000 margin=0.3244 second='۹' (0.3244) accepted=True bbox=(16, 4, 21, 24)`
  - `g2 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(26, 17, 31, 27)`
  - `g3 expected='۵': best='۵' distance=0.0000 margin=0.3744 second='۸' (0.3744) accepted=True bbox=(32, 4, 44, 24)`
  - `g4 expected='۷': best='۷' distance=0.0000 margin=0.2256 second='۴' (0.2256) accepted=True bbox=(46, 4, 58, 24)`
  - `g5 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(60, 12, 67, 19)`
  - `g6 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(71, 17, 76, 27)`
  - `g7 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(77, 12, 84, 19)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(87, 12, 94, 19)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(97, 12, 104, 19)`

### total: `line.8.total` — fold-4, held-out #33

- Raw/reference: `۳,۷۰۰,۰۰۰` / `۳,۷۰۰,۰۰۰`; confidence `99.98`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۳': best='۳' distance=0.0000 margin=0.2101 second='۴' (0.2101) accepted=True bbox=(14, 4, 27, 24)`
  - `g2 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(30, 17, 35, 27)`
  - `g3 expected='۷': best='۷' distance=0.0000 margin=0.2256 second='۴' (0.2256) accepted=True bbox=(36, 4, 48, 24)`
  - `g4 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(50, 12, 57, 19)`
  - `g5 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(61, 12, 68, 19)`
  - `g6 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(72, 17, 77, 27)`
  - `g7 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(78, 12, 85, 19)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(88, 12, 95, 19)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(98, 12, 105, 19)`

### total: `line.10.total` — fold-4, held-out #33

- Raw/reference: `۱۹,۰۵۰,۰۰۰` / `۱۹,۰۵۰,۰۰۰`; confidence `99.99`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۱': best='۱' distance=0.0000 margin=0.3244 second='۹' (0.3244) accepted=True bbox=(13, 4, 18, 24)`
  - `g2 expected='۹': best='۹' distance=0.0000 margin=0.3244 second='۱' (0.3244) accepted=True bbox=(22, 4, 31, 24)`
  - `g3 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(34, 17, 39, 27)`
  - `g4 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(40, 12, 47, 19)`
  - `g5 expected='۵': best='۵' distance=0.0000 margin=0.3744 second='۸' (0.3744) accepted=True bbox=(50, 4, 62, 24)`
  - `g6 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(64, 12, 71, 19)`
  - `g7 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(75, 17, 80, 27)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(81, 12, 88, 19)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(91, 12, 98, 19)`
  - `g10 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(101, 12, 108, 19)`

### total: `line.11.total` — fold-4, held-out #33

- Raw/reference: `۱,۳۸۰,۰۰۰` / `۱,۳۸۰,۰۰۰`; confidence `99.99`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۱': best='۱' distance=0.0000 margin=0.3244 second='۹' (0.3244) accepted=True bbox=(15, 4, 20, 24)`
  - `g2 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(25, 17, 30, 27)`
  - `g3 expected='۳': best='۳' distance=0.0000 margin=0.2101 second='۴' (0.2101) accepted=True bbox=(31, 4, 44, 24)`
  - `g4 expected='۸': best='۸' distance=0.0000 margin=0.3744 second='۵' (0.3744) accepted=True bbox=(46, 4, 58, 24)`
  - `g5 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(60, 12, 67, 19)`
  - `g6 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(71, 17, 76, 27)`
  - `g7 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(77, 12, 84, 19)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(87, 12, 94, 19)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(97, 12, 104, 19)`

### total: `line.12.total` — fold-4, held-out #33

- Raw/reference: `۱,۵۷۰,۰۰۰` / `۱,۵۷۰,۰۰۰`; confidence `99.98`; status `REVIEW`.
- Final classifier reason: "arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
- Pre-arithmetic-gate reason: None
- Failed conditions: arithmetic gate.
- Other glyph/text conditions: none.
- Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; source status=None.
- Per-glyph evidence:
  - `g1 expected='۱': best='۱' distance=0.0000 margin=0.3244 second='۹' (0.3244) accepted=True bbox=(16, 4, 21, 24)`
  - `g2 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(26, 17, 31, 27)`
  - `g3 expected='۵': best='۵' distance=0.0000 margin=0.3744 second='۸' (0.3744) accepted=True bbox=(32, 4, 44, 24)`
  - `g4 expected='۷': best='۷' distance=0.0000 margin=0.2256 second='۴' (0.2256) accepted=True bbox=(46, 4, 58, 24)`
  - `g5 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(60, 12, 67, 19)`
  - `g6 expected=',': best=',' distance=0.0000 margin=0.8643 second='۰' (0.8643) accepted=True bbox=(71, 17, 76, 27)`
  - `g7 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(77, 12, 84, 19)`
  - `g8 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(87, 12, 94, 19)`
  - `g9 expected='۰': best='۰' distance=0.0000 margin=0.8643 second=',' (0.8643) accepted=True bbox=(97, 12, 104, 19)`

## 2. Invoice #33 payable diagnosis

Invoice #33 held out in `fold-4`: raw `?۴۷,۹۲۰,۰۰۰`, reference `۳۴۷,۹۲۰,۰۰۰`, digits_match_reference=False, status `REVIEW`, confidence 0.00.
Final reason: "glyph 1 not accepted: ambiguous: margin 0.142 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
Pre-gate reason: 'glyph 1 not accepted: ambiguous: margin 0.142 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format'
The cell has 11/11 glyph readings; rejected glyphs: 1. One-glyph rejection: yes; arithmetic gate failure: yes. The REVIEW is attributable to both per-glyph/classifier checks and the arithmetic gate.
Gate: passed=False; reason="line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"; line sum=None; payable=None.
Template labels available to payable profile (payable + row fallback): ',', '۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'.
Reference labels absent from that pool: none.

Counterfactual isolation: relaxing only the margin check would accept glyph 1 as `۳` (best distance 0.0611, margin 0.1423) and make the raw payable match the reference; the separate arithmetic gate would still fail because `line.3.total` is malformed, so the payable would remain REVIEW. Relaxing only the arithmetic gate would leave the `?` glyph and incorrect raw value, so it also would not become EXTRACTED. Both blockers would have to clear.

Per-glyph best and second-best candidates:

- `g1 expected='۳': best='۳' distance=0.0611 margin=0.1423 second='۴' (0.2034) accepted=False bbox=(4, 4, 20, 28) note='ambiguous: margin 0.142 below 0.150'`
- `g2 expected='۴': best='۴' distance=0.0001 margin=0.2225 second='۷' (0.2226) accepted=True bbox=(22, 4, 37, 28)`
- `g3 expected='۷': best='۷' distance=0.0001 margin=0.2212 second='۲' (0.2212) accepted=True bbox=(39, 4, 54, 28)`
- `g4 expected=',': best=',' distance=0.0000 margin=0.8428 second='۰' (0.8428) accepted=True bbox=(57, 20, 63, 32)`
- `g5 expected='۹': best='۹' distance=0.0821 margin=0.2661 second='۱' (0.3482) accepted=True bbox=(65, 4, 76, 28)`
- `g6 expected='۲': best='۲' distance=0.0001 margin=0.2057 second='۴' (0.2058) accepted=True bbox=(78, 4, 91, 28)`
- `g7 expected='۰': best='۰' distance=0.0000 margin=0.8208 second=',' (0.8208) accepted=True bbox=(94, 14, 103, 23)`
- `g8 expected=',': best=',' distance=0.0000 margin=0.8428 second='۰' (0.8428) accepted=True bbox=(107, 20, 113, 32)`
- `g9 expected='۰': best='۰' distance=0.0000 margin=0.8208 second=',' (0.8208) accepted=True bbox=(116, 14, 125, 23)`
- `g10 expected='۰': best='۰' distance=0.0000 margin=0.8208 second=',' (0.8208) accepted=True bbox=(129, 14, 138, 23)`
- `g11 expected='۰': best='۰' distance=0.0000 margin=0.8208 second=',' (0.8208) accepted=True bbox=(142, 14, 151, 23)`

## 3. REVIEW counts per failure condition

Counts are overlapping condition flags, not mutually exclusive primary causes. `All REVIEW` includes incorrect and correct cells; `correct REVIEW` is the subset with `digits_match_reference=True`.

| condition | all REVIEW cells flagged | correct REVIEW cells flagged |
|---|---:|---:|
| distance > max_distance | 4 | 0 |
| margin < min_margin | 8 | 0 |
| confidence < minimum_confidence | 9 | 1 |
| format check | 8 | 0 |
| arithmetic gate | 14 | 9 |
| source REVIEW | 0 | 0 |
| other glyph/text checks (edge, width, no text, etc.) | 0 | 0 |

Unique REVIEW cells: 18; correct REVIEW cells: 10. Since flags can overlap, condition columns need not sum to the number of REVIEW cells.

## 4. What-if: relax one condition at a time

This is a read-only counterfactual over the current correct REVIEW cells. A cell is counted only if the selected condition is its sole active failure; all other checks, including the arithmetic gate, remain unchanged. No thresholds or defaults are altered.

| condition hypothetically relaxed | correct REVIEW cells with this as sole blocker | newly EXTRACTED | total correct cells EXTRACTED after this single relaxation |
|---|---:|---:|---:|
| distance > max_distance | 0 | 0 | 36 |
| margin < min_margin | 0 | 0 | 36 |
| confidence < minimum_confidence | 1 | 1 | 37 |
| format check | 0 | 0 | 36 |
| arithmetic gate | 9 | 9 | 45 |
| source REVIEW | 0 | 0 | 36 |
| other glyph/text checks | 0 | 0 | 36 |

## 5. Conclusion

- **Are thresholds unnecessarily strict?** Only 1 currently correct REVIEW cell(s) are blocked solely by the 60.0 confidence cutoff (the correct `line.1.quantity` at 34.29); 1 correct REVIEW cell(s) become EXTRACTED if one of the numeric thresholds is relaxed in isolation. The nine correctly read totals are REVIEW because the invoice-wide arithmetic gate fails, not because their glyph thresholds are too strict. The #33 payable's first glyph misses the margin cutoff narrowly (0.1423 vs 0.1500), but relaxing that alone would not clear the gate. This is a caution signal, not enough evidence to change defaults.
- **Is template coverage really the issue?** 0 correct REVIEW cell(s) have reference labels absent from their profile pool; #33 payable has no missing reference labels, and all digits plus the comma are available. Its top label is the expected `۳`, with `۴` a close runner-up. This points to ambiguity/margin rather than missing-label coverage for #33.
- **What does the data suggest?** Nine of the ten correct REVIEW cells are totals downgraded because the separate `line.3.total` prediction contains `?`, which causes the arithmetic gate to fail for invoice #33. One quantity cell is REVIEW solely for low confidence. The payable itself has one ambiguous first glyph and is also subject to that failed gate. Keep uncertain values in REVIEW; the data distinguishes gate propagation from the isolated confidence and margin checks, and the PM should decide whether any calibrated threshold change is justified.

### Full raw LOO evaluation output (all per-cell lines)

The following are the complete evaluator stdout/stderr captures for each fold, including every cell's status, reference match, reason, arithmetic gate, and calibration summaries.

#### fold-1 — held-out invoice #29

Build command: `/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier build --labels /tmp/b2-2b-loo-29-inkdxbde/train-labels.json --out /tmp/b2-2b-loo-29-inkdxbde/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/31.png
  USED line.0.total: ۹۷۰,۰۰۰ (+4 new templates)
  USED line.0.quantity: ۱ (+1 new templates)
  USED line.1.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۴۸۵,۰۰۰ (+3 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED invoice.payable: ۲,۴۲۵,۰۰۰ (+5 new templates)
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
  USED invoice.payable: ۷,۸۵۰,۰۰۰ (+2 new templates)
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
  USED invoice.payable: ۳۴۷,۹۲۰,۰۰۰ (+2 new templates)
profile row: ,x1 ۰x2 ۱x2 ۲x2 ۳x1 ۴x2 ۵x2 ۶x1 ۷x1 ۸x2 ۹x1
profile payable: ,x1 ۰x1 ۲x1 ۳x1 ۴x1 ۵x1 ۷x1 ۸x1 ۹x1
saved /tmp/b2-2b-loo-29-inkdxbde/templates.json
```

Evaluate command: `/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier evaluate --labels /tmp/b2-2b-loo-29-inkdxbde/test-labels.json --templates /tmp/b2-2b-loo-29-inkdxbde/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/29.png
  line.0.total|glyph|raw='۱,۴۵۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۱,۴۵۰,۰۰۰'|digits_match_reference=True
  line.0.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.1.total|glyph|raw='۴,۸۷۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۴,۸۷۰,۰۰۰'|digits_match_reference=True
  line.1.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.2.total|glyph|raw='۵۷۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۵۷۰,۰۰۰'|digits_match_reference=True
  line.2.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.3.total|glyph|raw='۵۷۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۵۷۰,۰۰۰'|digits_match_reference=True
  line.3.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  invoice.payable|glyph|raw='۷,۴۶۰,۰۰۰'|confidence=73.5|status=EXTRACTED|reference='۷,۴۶۰,۰۰۰'|digits_match_reference=True
  arithmetic_gate passed=True line_sum=7460000 payable=7460000 extra=0 reason=None
metric.definition=exact match and CER on digit strings; separators ignored for scoring only
metrics.glyph.exact_digit_cells=9/9 digit_CER=0.00%
metrics.glyph.segmentation_mismatch_cells=0
metrics.glyph.arithmetic_gate_passed=1/1
calibration.best_label_correct.distance n=45 min=0.000 max=0.066
calibration.best_label_correct.margin   n=45 min=0.198 max=0.864
calibration.best_label_wrong.distance   n=0
calibration.best_label_wrong.margin   n=0
```

#### fold-2 — held-out invoice #31

Build command: `/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier build --labels /tmp/b2-2b-loo-31-mvxrjur2/train-labels.json --out /tmp/b2-2b-loo-31-mvxrjur2/templates.json`

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
  USED invoice.payable: ۷,۴۶۰,۰۰۰ (+5 new templates)
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
  USED invoice.payable: ۷,۸۵۰,۰۰۰ (+2 new templates)
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
  USED invoice.payable: ۳۴۷,۹۲۰,۰۰۰ (+3 new templates)
profile row: ,x1 ۰x2 ۱x2 ۲x2 ۳x1 ۴x2 ۵x2 ۶x1 ۷x1 ۸x2 ۹x1
profile payable: ,x1 ۰x1 ۲x1 ۳x1 ۴x1 ۵x1 ۶x1 ۷x1 ۸x1 ۹x1
saved /tmp/b2-2b-loo-31-mvxrjur2/templates.json
```

Evaluate command: `/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier evaluate --labels /tmp/b2-2b-loo-31-mvxrjur2/test-labels.json --templates /tmp/b2-2b-loo-31-mvxrjur2/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/31.png
  line.0.total|glyph|raw='۹۷۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۹۷۰,۰۰۰'|digits_match_reference=True
  line.0.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.1.total|glyph|raw='۹۷۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۹۷۰,۰۰۰'|digits_match_reference=True
  line.1.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.2.total|glyph|raw='۴۸۵,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۴۸۵,۰۰۰'|digits_match_reference=True
  line.2.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  invoice.payable|glyph|raw='۲,۴۲۵,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۲,۴۲۵,۰۰۰'|digits_match_reference=True
  arithmetic_gate passed=True line_sum=2425000 payable=2425000 extra=0 reason=None
metric.definition=exact match and CER on digit strings; separators ignored for scoring only
metrics.glyph.exact_digit_cells=7/7 digit_CER=0.00%
metrics.glyph.segmentation_mismatch_cells=0
metrics.glyph.arithmetic_gate_passed=1/1
calibration.best_label_correct.distance n=33 min=0.000 max=0.000
calibration.best_label_correct.margin   n=33 min=0.198 max=0.864
calibration.best_label_wrong.distance   n=0
calibration.best_label_wrong.margin   n=0
```

#### fold-3 — held-out invoice #32

Build command: `/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier build --labels /tmp/b2-2b-loo-32-9vky1_qa/train-labels.json --out /tmp/b2-2b-loo-32-9vky1_qa/templates.json`

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
  USED invoice.payable: ۷,۴۶۰,۰۰۰ (+5 new templates)
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/31.png
  USED line.0.total: ۹۷۰,۰۰۰ (+1 new templates)
  USED line.0.quantity: ۱ (+0 new templates)
  USED line.1.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۴۸۵,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED invoice.payable: ۲,۴۲۵,۰۰۰ (+2 new templates)
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
  USED invoice.payable: ۳۴۷,۹۲۰,۰۰۰ (+2 new templates)
profile row: ,x1 ۰x2 ۱x2 ۲x2 ۳x1 ۴x2 ۵x2 ۶x1 ۷x1 ۸x2 ۹x1
profile payable: ,x1 ۰x1 ۲x1 ۳x1 ۴x1 ۵x1 ۶x1 ۷x1 ۹x1
saved /tmp/b2-2b-loo-32-9vky1_qa/templates.json
```

Evaluate command: `/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier evaluate --labels /tmp/b2-2b-loo-32-9vky1_qa/test-labels.json --templates /tmp/b2-2b-loo-32-9vky1_qa/templates.json`

```text
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/32.png
  line.0.total|glyph|raw='۹۷۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۹۷۰,۰۰۰'|digits_match_reference=True
  line.0.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.1.total|glyph|raw='۳,۹۵۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۳,۹۵۰,۰۰۰'|digits_match_reference=True
  line.1.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.2.total|glyph|raw='۱,۸۷۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۱,۸۷۰,۰۰۰'|digits_match_reference=True
  line.2.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.3.total|glyph|raw='۹۷۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۹۷۰,۰۰۰'|digits_match_reference=True
  line.3.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  line.4.total|glyph|raw='۹۰,۰۰۰'|confidence=100.0|status=EXTRACTED|reference='۹۰,۰۰۰'|digits_match_reference=True
  line.4.quantity|glyph|raw='۱'|confidence=100.0|status=EXTRACTED|reference='۱'|digits_match_reference=True
  invoice.payable|glyph|raw='۷,۸۵۰,۰۰۰'|confidence=73.3|status=EXTRACTED|reference='۷,۸۵۰,۰۰۰'|digits_match_reference=True
  arithmetic_gate passed=True line_sum=7850000 payable=7850000 extra=0 reason=None
metric.definition=exact match and CER on digit strings; separators ignored for scoring only
metrics.glyph.exact_digit_cells=11/11 digit_CER=0.00%
metrics.glyph.segmentation_mismatch_cells=0
metrics.glyph.arithmetic_gate_passed=1/1
calibration.best_label_correct.distance n=52 min=0.000 max=0.067
calibration.best_label_correct.margin   n=52 min=0.198 max=0.864
calibration.best_label_wrong.distance   n=0
calibration.best_label_wrong.margin   n=0
```

#### fold-4 — held-out invoice #33

Build command: `/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier build --labels /tmp/b2-2b-loo-33-td12vmxt/train-labels.json --out /tmp/b2-2b-loo-33-td12vmxt/templates.json`

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
  USED invoice.payable: ۷,۴۶۰,۰۰۰ (+5 new templates)
== /home/user/Kandoo-Digital-Invoice/tests/fixtures/real/31.png
  USED line.0.total: ۹۷۰,۰۰۰ (+1 new templates)
  USED line.0.quantity: ۱ (+0 new templates)
  USED line.1.total: ۹۷۰,۰۰۰ (+0 new templates)
  USED line.1.quantity: ۱ (+0 new templates)
  USED line.2.total: ۴۸۵,۰۰۰ (+0 new templates)
  USED line.2.quantity: ۱ (+0 new templates)
  USED invoice.payable: ۲,۴۲۵,۰۰۰ (+2 new templates)
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
  USED invoice.payable: ۷,۸۵۰,۰۰۰ (+1 new templates)
profile row: ,x1 ۰x1 ۱x2 ۳x1 ۴x1 ۵x1 ۷x1 ۸x1 ۹x1
profile payable: ,x1 ۰x1 ۲x1 ۴x1 ۵x1 ۶x1 ۷x1 ۸x1
WARNING: row profile has no template for: ۲ ۶
saved /tmp/b2-2b-loo-33-td12vmxt/templates.json
```

Evaluate command: `/tmp/kandoo-t2-venv/bin/python -m image_extraction_adapter.glyph_classifier evaluate --labels /tmp/b2-2b-loo-33-td12vmxt/test-labels.json --templates /tmp/b2-2b-loo-33-td12vmxt/templates.json`

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
  invoice.payable|glyph|raw='?۴۷,۹۲۰,۰۰۰'|confidence=0.0|status=REVIEW|reference='۳۴۷,۹۲۰,۰۰۰'|digits_match_reference=False|reason="glyph 1 not accepted: ambiguous: margin 0.142 below 0.150; cell OCR confidence 0.00 is below 60.00; raw cell OCR does not match the declared numeric format; arithmetic gate failed: line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount"
  arithmetic_gate passed=False line_sum=None payable=None extra=0 reason=line.3.total '?,۴۰۰,۰۰۰' is not a well-formed amount
metric.definition=exact match and CER on digit strings; separators ignored for scoring only
metrics.glyph.exact_digit_cells=19/27 digit_CER=8.33%
metrics.glyph.segmentation_mismatch_cells=0
metrics.glyph.arithmetic_gate_passed=0/1
calibration.best_label_correct.distance n=139 min=0.000 max=0.164
calibration.best_label_correct.margin   n=139 min=0.142 max=0.864
calibration.best_label_wrong.distance   n=9 min=0.198 max=0.319
calibration.best_label_wrong.margin   n=9 min=0.022 max=0.052
```
