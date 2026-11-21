# E-21 — Synthetic unknown-layout safety checks

- **Status:** PASS
- **Execution environment:** Linux / Python 3.11.2 / Pillow 13.0.0.
- **Evidence class:** synthetic mechanics only; not a Holo capture, not real-store evidence, and not production OCR accuracy.

## Test setup

- Installed font: **DejaVu Sans Mono Book** (`/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf`; SHA-256 `0f5db4f1749979d961019838b160bec74abdf7f9eca69553fe1aa856bbff49a4`).
- The five exam variants are rendered at 576 pixels wide, 1-bit, from the frozen E-03 v3 values.
- E-05/Glyph banks are trained only on the three synthetic learning pages; each variant is held out.
- E-05 reference comparisons use E-03 answer-key labels for numeric evidence and are not OCR predictions.
- Thresholds tuned: **False**. No font download or substitution was attempted.

## Per-variant routing and value safety

Rates use one synthetic page per variant (`safe outcomes / 1`); they are not statistical claims.

| Variant | E-02 / layout | E-05 reference | E-06 | Final | Safe-route rate | Correct EXTRACTED | EXTRACTED-but-wrong | Reason |
|---|---|---|---|---|---:|---:|---:|---|
| Swapped columns | REVIEW / OK | 0.999 / True | REVIEW | **REVIEW** | 1/1 (100%) | 0 | 0 | E-06 REVIEW: Missing fields: invoice.payable is unavailable or not a valid integer-Rial amount, line.0.quantity is not a valid positive integer, line.0.total is not a valid integer-Rial amount, line.1.quantity is not a valid positive integer, line.2.quantity is not a valid positive integer, line.2.total is not a valid integer-Rial amount, line.3.quantity is not a valid positive integer, line.3.total is not a valid integer-Rial amount |
| No vertical rules | REJECT / BLOCKED | No safe observation | REVIEW | **BLOCKED** | 1/1 (100%) | 0 | 0 | E-02 failed closed: No table geometry was detected. |
| Three columns | REJECT / BLOCKED | No safe observation | REVIEW | **BLOCKED** | 1/1 (100%) | 0 | 0 | E-02 failed closed: No table geometry was detected. |
| Extra column | REJECT / BLOCKED | No safe observation | REVIEW | **BLOCKED** | 1/1 (100%) | 0 | 0 | E-02 failed closed: No table geometry was detected. |
| Different table position | REVIEW / OK | 0.635 / False | REVIEW | **REVIEW** | 1/1 (100%) | 3 | 0 | E-06 REVIEW: Missing fields: invoice.payable is unavailable or not a valid integer-Rial amount, line.0.quantity is not a valid positive integer, line.0.total is not a valid integer-Rial amount, line.1.total is not a valid integer-Rial amount |

## Aggregate result

- Safely routed to REVIEW/BLOCKED: **5/5 (100%)**.
- EXTRACTED-but-wrong numeric cells: **0**.
- Confident wrong values forwarded as an E-02 Canonical candidate: **0**.
- Variants with a non-empty final reason: **5/5**.
- Thresholds tuned: **False**.

## Variant details

### Swapped columns

- Synthetic image SHA-256: `24cd6ef5f62e73e782fbd97ee46e1cf18ba8cced712bf9a2a024d49d6d5f9650`; raster: 576×872 px, mode `1`.
- E-02: `REVIEW` / layout `OK`; 0 correct EXTRACTED, 0 EXTRACTED-but-wrong, 9 REVIEW/other.
- E-02 reason: Canonical context did not produce a valid v0 candidate.
- E-06: `REVIEW`; reason codes: `PARTIAL_MATCH`.
- Final E-21 route: **REVIEW** — E-06 REVIEW: Missing fields: invoice.payable is unavailable or not a valid integer-Rial amount, line.0.quantity is not a valid positive integer, line.0.total is not a valid integer-Rial amount, line.1.quantity is not a valid positive integer, line.2.quantity is not a valid positive integer, line.2.total is not a valid integer-Rial amount, line.3.quantity is not a valid positive integer, line.3.total is not a valid integer-Rial amount
- Candidate emitted: **False**; candidate had wrong values: **False**.

### No vertical rules

- Synthetic image SHA-256: `496c7a01f20add4dfb291cc13b83e8fca8ce5d93691314804dccf6b713ba15f8`; raster: 576×872 px, mode `1`.
- E-02: `REJECT` / layout `BLOCKED`; 0 correct EXTRACTED, 0 EXTRACTED-but-wrong, 0 REVIEW/other.
- E-02 reason: No table geometry was detected.
- E-06: `REVIEW`; reason codes: `PARTIAL_MATCH`, `NEW_LAYOUT`.
- Final E-21 route: **BLOCKED** — E-02 failed closed: No table geometry was detected.
- Candidate emitted: **False**; candidate had wrong values: **False**.

### Three columns

- Synthetic image SHA-256: `d6ce0ef992976d566b2bfae19533ba7bd9c6dc322aaeaadd9995fb8228bd2df6`; raster: 576×872 px, mode `1`.
- E-02: `REJECT` / layout `BLOCKED`; 0 correct EXTRACTED, 0 EXTRACTED-but-wrong, 0 REVIEW/other.
- E-02 reason: No table geometry was detected.
- E-06: `REVIEW`; reason codes: `PARTIAL_MATCH`, `NEW_LAYOUT`.
- Final E-21 route: **BLOCKED** — E-02 failed closed: No table geometry was detected.
- Candidate emitted: **False**; candidate had wrong values: **False**.

### Extra column

- Synthetic image SHA-256: `4e24d66a55b6cf878ba758545cdb1ba4283cdd40946003679e779cf8f9514d02`; raster: 576×872 px, mode `1`.
- E-02: `REJECT` / layout `BLOCKED`; 0 correct EXTRACTED, 0 EXTRACTED-but-wrong, 0 REVIEW/other.
- E-02 reason: No table geometry was detected.
- E-06: `REVIEW`; reason codes: `PARTIAL_MATCH`, `NEW_LAYOUT`.
- Final E-21 route: **BLOCKED** — E-02 failed closed: No table geometry was detected.
- Candidate emitted: **False**; candidate had wrong values: **False**.

### Different table position

- Synthetic image SHA-256: `8ca3da64002371f3042e0cec7cc28c40458671f90c26800141e4217d5c99da62`; raster: 576×906 px, mode `1`.
- E-02: `REVIEW` / layout `OK`; 3 correct EXTRACTED, 0 EXTRACTED-but-wrong, 6 REVIEW/other.
- E-02 reason: Canonical context did not produce a valid v0 candidate.
- E-06: `REVIEW`; reason codes: `PARTIAL_MATCH`.
- Final E-21 route: **REVIEW** — E-06 REVIEW: Missing fields: invoice.payable is unavailable or not a valid integer-Rial amount, line.0.quantity is not a valid positive integer, line.0.total is not a valid integer-Rial amount, line.1.total is not a valid integer-Rial amount
- Candidate emitted: **False**; candidate had wrong values: **False**.

## Synthetic limitations

These pages are rendered by Pillow from test values. They are not real invoices and do not establish generalization to another store. E-21 checks that these deliberately changed geometries are routed to review/blocking without emitting a confident wrong candidate; it does not tune or validate thresholds.
