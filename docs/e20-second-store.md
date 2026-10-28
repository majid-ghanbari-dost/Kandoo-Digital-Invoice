# E-20 — Synthetic second-store mechanics test

- **Status:** PASS
- **Execution environment:** Linux / Python 3.11.2 / Pillow 13.0.0 (local runner; CI verification is a separate gate).
- **Evidence class:** synthetic mechanics only; not a Holo capture, not real-store evidence, and not production OCR accuracy.

## Font and rasterization

- Selected installed font: **DejaVu Sans Mono Book** (/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf).
- Font SHA-256: `0f5db4f1749979d961019838b160bec74abdf7f9eca69553fe1aa856bbff49a4`.
- Glyph-mask check: digits ۰–۹ have distinct nonempty masks; comma is nonempty and distinct.
- No font was downloaded, installed, or substituted. If no suitable installed font exists, the runner reports `BLOCKED_FONT_UNAVAILABLE` and stops.
- Pages: 576 pixels wide, 1-bit, synthetic Holo-inspired four-row layout; grayscale threshold `< 180`.

## E-03 v3 symbol coverage

- Learning-page values missing controlled symbols: **None**.
- Exam symbols absent from learning-page values: **None**.
- E-02 row templates missing exam symbols: **None**.
- E-02 per-profile gaps: `payable`: `۱`, `۳`, `۸`, `row`: None. The current pipeline uses row templates for payable cells by default.
- Counts below are synthetic rendered-target values from the frozen E-03 v3 kit:

| Symbol | Learning pages | Exam page |
|---:|---:|---:|
| `۰` | 10 | 3 |
| `۱` | 14 | 3 |
| `۲` | 26 | 6 |
| `۳` | 3 | 4 |
| `۴` | 8 | 2 |
| `۵` | 11 | 3 |
| `۶` | 20 | 5 |
| `۷` | 7 | 1 |
| `۸` | 5 | 3 |
| `۹` | 4 | 2 |
| `comma` | 20 | 5 |

## E-05, E-02, and E-06 results

- E-05 bank: 1 synthetic cluster(s), trained on learning pages only; held-out exam reference match `0.999` (matched: **True**). The match uses E-03 target labels for numeric evidence, not an OCR prediction.
- E-02 exam pipeline: **REVIEW**; 3 correct EXTRACTED, 0 EXTRACTED-but-wrong, 6 REVIEW/other cells.
- Arithmetic gate: `False` (line.0.total '۱??,۶??' is not a well-formed amount).
- Canonical Invoice candidate emitted: **False**.
- E-06 verdict: **REVIEW**; reason codes: `PARTIAL_MATCH`.
- E-06 details: Missing fields: invoice.payable is unavailable or not a valid integer-Rial amount, line.0.quantity is not a valid positive integer, line.0.total is not a valid integer-Rial amount, line.1.total is not a valid integer-Rial amount
- E-06 input is the actual E-02 candidate; when E-02 emits no candidate, E-06 receives `None`. The separate E-05 reference match is not presented as an OCR result.

## Acceptance checks

- Zero EXTRACTED-but-wrong: **True**.
- All exam symbols represented in learning values: **True**.
- E-06 did not ACCEPT: **True**.
- Thresholds tuned: **False**.
- Overall E-20 mechanics result: **True**.

## Per-page raster and detected layout

| Page | Role | Raster | Mode | Detection | Rows | SHA-256 |
|---|---|---:|---|---|---:|---|
| learning-1 | learning | 576×872 | 1 | OK | 4 | `4d45529d5ea556b23d557ebfe53d5b4343ba0705bb34fd22ac45cbcee933964a` |
| learning-2 | learning | 576×872 | 1 | OK | 4 | `bad385c6f6a5c0ecc5b481530d846b4966b806977fd2544cb09f2c7208dc62af` |
| learning-3 | learning | 576×872 | 1 | OK | 4 | `2a5b48b9397c802f485698b2d3c11c3713099dc3249086db644d37404c3fcb51` |
| exam | exam | 576×872 | 1 | OK | 4 | `574e229b93821b5723c3fd06af5ae94b3d0f16de5c73db71e31f60cf5c4ee808` |

## Synthetic limitations

These pages were rendered by Pillow from the frozen E-03 answer key. They do not originate from Holo, a Windows spool job, KandooPrintProbe, a physical printer, or any real store. The test checks pipeline mechanics and fail-closed behavior only; it does not establish generalization to real stores.
