# E-15 fail-closed robustness suite

- Evaluated code HEAD: `84c4c92872b838ecc5bc6a3cbf3c98a7cc206078`
- Generated at (UTC): `2026-10-24T17:32:01+00:00`
- Runtime: Python 3.11.2, Pillow 13.0.0, jsonschema 4.26.0
- Source images: `tests/fixtures/real/{29,31,32,33}.png` with their operator-confirmed label values; fixture 31 payable remains derived from its line totals.
- E-02: existing leave-one-fixture-out Glyph fold for each source fixture. E-05: existing label-derived four-fixture bank. E-06: existing verdict function; thresholds and policy constants were not changed.
- Perturbations operate on decoded fixture pixels and are saved as temporary PNGs; all seven perturbation types run once per fixture (28 total). No invoice submission or issuance occurs.
- `EXTRACTED-but-wrong` is counted only when a cell remains `EXTRACTED` after the existing arithmetic gate and its parsed value differs from the operator label. Any final verdict other than E-06 `REVIEW` or `REJECT` fails the acceptance gate.

## Per-perturbation fail-closed rates

| Perturbation | Runs | E-06 REVIEW | E-06 REJECT | REVIEW/REJECT rate | E-02 AUTO_CANDIDATE | E-02 REVIEW | E-02 REJECT | EXTRACTED-but-wrong | CORRECT | NOT-EXTRACTED |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `shift_1px` | 4 | 1 | 3 | 100% | 3 | 1 | 0 | 0 | 36 | 18 |
| `shift_2px` | 4 | 1 | 3 | 100% | 3 | 1 | 0 | 0 | 36 | 18 |
| `small_blur` | 4 | 1 | 3 | 100% | 3 | 1 | 0 | 0 | 36 | 18 |
| `small_noise` | 4 | 1 | 3 | 100% | 3 | 1 | 0 | 0 | 36 | 18 |
| `swap_digit_crops` | 4 | 3 | 1 | 100% | 0 | 4 | 0 | 0 | 21 | 33 |
| `replace_digit_glyph` | 4 | 3 | 1 | 100% | 0 | 4 | 0 | 0 | 21 | 33 |
| `delete_one_row` | 4 | 4 | 0 | 100% | 0 | 0 | 4 | 0 | 0 | 54 |

## Run-level results

| Fixture | Perturbation | Applied modification | E-02 | E-05 | E-06 final verdict | CORRECT | NOT-EXTRACTED | EXTRACTED-but-wrong |
|---|---|---|---|---|---|---:|---:|---:|
| 29 | `shift_1px` | translate right 1 px, white fill | AUTO_CANDIDATE / OK | MATCH (0.981) | REJECT | 9 | 0 | 0 |
| 29 | `shift_2px` | translate right 2 px, white fill | AUTO_CANDIDATE / OK | MATCH (0.964) | REJECT | 9 | 0 | 0 |
| 29 | `small_blur` | Gaussian blur radius 0.4 px | AUTO_CANDIDATE / OK | MATCH (0.999) | REJECT | 9 | 0 | 0 |
| 29 | `small_noise` | 1492 deterministic sparse RGB perturbations (delta ±6/±8) | AUTO_CANDIDATE / OK | MATCH (0.999) | REJECT | 9 | 0 | 0 |
| 29 | `swap_digit_crops` | line.0.total: swapped glyph ۱ with ۴ | REVIEW / OK | NO_MATCH (0.819) | REVIEW | 4 | 5 | 0 |
| 29 | `replace_digit_glyph` | line.0.total: replaced glyph ۱ with ۴ from line.1.total | REVIEW / OK | NO_MATCH (0.819) | REVIEW | 4 | 5 | 0 |
| 29 | `delete_one_row` | cleared item row 2 (zero-based) while retaining table rules | REJECT / BLOCKED | NOT_EVALUATED (—) | REVIEW | 0 | 9 | 0 |
| 31 | `shift_1px` | translate right 1 px, white fill | AUTO_CANDIDATE / OK | MATCH (0.978) | REVIEW | 7 | 0 | 0 |
| 31 | `shift_2px` | translate right 2 px, white fill | AUTO_CANDIDATE / OK | MATCH (0.961) | REVIEW | 7 | 0 | 0 |
| 31 | `small_blur` | Gaussian blur radius 0.4 px | AUTO_CANDIDATE / OK | MATCH (0.996) | REVIEW | 7 | 0 | 0 |
| 31 | `small_noise` | 1410 deterministic sparse RGB perturbations (delta ±6/±8) | AUTO_CANDIDATE / OK | MATCH (0.996) | REVIEW | 7 | 0 | 0 |
| 31 | `swap_digit_crops` | line.0.total: swapped glyph ۹ with ۷ | REVIEW / OK | NO_MATCH (0.816) | REVIEW | 3 | 4 | 0 |
| 31 | `replace_digit_glyph` | line.0.total: replaced glyph ۹ with ۷ from line.1.total | REVIEW / OK | NO_MATCH (0.816) | REVIEW | 3 | 4 | 0 |
| 31 | `delete_one_row` | cleared item row 1 (zero-based) while retaining table rules | REJECT / BLOCKED | NOT_EVALUATED (—) | REVIEW | 0 | 7 | 0 |
| 32 | `shift_1px` | translate right 1 px, white fill | AUTO_CANDIDATE / OK | MATCH (0.980) | REJECT | 11 | 0 | 0 |
| 32 | `shift_2px` | translate right 2 px, white fill | AUTO_CANDIDATE / OK | MATCH (0.963) | REJECT | 11 | 0 | 0 |
| 32 | `small_blur` | Gaussian blur radius 0.4 px | AUTO_CANDIDATE / OK | MATCH (0.997) | REJECT | 11 | 0 | 0 |
| 32 | `small_noise` | 1575 deterministic sparse RGB perturbations (delta ±6/±8) | AUTO_CANDIDATE / OK | MATCH (0.997) | REJECT | 11 | 0 | 0 |
| 32 | `swap_digit_crops` | line.0.total: swapped glyph ۹ with ۷ | REVIEW / OK | NO_MATCH (0.817) | REVIEW | 5 | 6 | 0 |
| 32 | `replace_digit_glyph` | line.0.total: replaced glyph ۹ with ۳ from line.1.total | REVIEW / OK | NO_MATCH (0.817) | REVIEW | 5 | 6 | 0 |
| 32 | `delete_one_row` | cleared item row 2 (zero-based) while retaining table rules | REJECT / BLOCKED | NOT_EVALUATED (—) | REVIEW | 0 | 11 | 0 |
| 33 | `shift_1px` | translate right 1 px, white fill | REVIEW / OK | NO_MATCH (0.776) | REJECT | 9 | 18 | 0 |
| 33 | `shift_2px` | translate right 2 px, white fill | REVIEW / OK | NO_MATCH (0.760) | REJECT | 9 | 18 | 0 |
| 33 | `small_blur` | Gaussian blur radius 0.4 px | REVIEW / OK | NO_MATCH (0.792) | REJECT | 9 | 18 | 0 |
| 33 | `small_noise` | 1935 deterministic sparse RGB perturbations (delta ±6/±8) | REVIEW / OK | NO_MATCH (0.792) | REJECT | 9 | 18 | 0 |
| 33 | `swap_digit_crops` | line.0.total: swapped glyph ۷ with ۸ | REVIEW / OK | NO_MATCH (0.792) | REJECT | 9 | 18 | 0 |
| 33 | `replace_digit_glyph` | line.0.total: replaced glyph ۷ with ۴ from line.1.total | REVIEW / OK | NO_MATCH (0.792) | REJECT | 9 | 18 | 0 |
| 33 | `delete_one_row` | cleared item row 6 (zero-based) while retaining table rules | REJECT / BLOCKED | NOT_EVALUATED (—) | REVIEW | 0 | 27 | 0 |

## Gate result

- Total injected runs: **28**; all inputs changed: **28/28**.
- EXTRACTED-but-wrong: **0**; CORRECT: **186**; NOT-EXTRACTED: **192**.
- Final E-06 verdicts: ACCEPT **0**, REVIEW **14**, REJECT **14**.
- Acceptance gate: **PASS** (zero EXTRACTED-but-wrong and every injected case ends REVIEW/REJECT).

## Method limits

The four images are legacy labeled fixtures, not the E-03-kit-v3 Holo captures. The small blur/noise and pixel-shift trials are deterministic software perturbations, not measured physical scan variance. E-05 training uses the same four labeled invoices and therefore remains resubstitution evidence; E-06 is deliberately run with an unlocked bank and unsigned D14 agreement, and its REVIEW/REJECT outcomes must not be read as general accuracy or independent validation. Thresholds were not tuned.
