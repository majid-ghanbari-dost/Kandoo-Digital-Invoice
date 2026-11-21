# E-03-kit-v3 verification

**Result: PASS — executable Holo entry values and generated coverage matrix.** Verified at pre-commit HEAD `ff54f7c8edcea0dbdf0b7d852e876d40dcd52f5e` on 2026-10-24.

## Checks performed

Commands:

```sh
PYTHONDONTWRITEBYTECODE=1 python scripts/verify_e03_kit_v3.py --write-coverage
PYTHONDONTWRITEBYTECODE=1 python scripts/verify_e03_kit_v3.py
PYTHONPATH=/tmp/kandoo-e03-v3-deps:src PYTHONDONTWRITEBYTECODE=1 \
  python -m pytest -q tests/test_e03_kit_v2.py tests/test_e03_kit_v3.py
```

- **16/16** item rows passed exact integer arithmetic: entered Holo unit price × quantity = target line total.
- All four page payables equal the sum of their line totals; page tables agree with `expected-values.json`.
- The JSON ground truth has only `quantities`, `line_totals`, and `payable`; the entry-only price values and Persian item names are excluded.
- Three learning pages and one exam page are present. Every page contains at least five `۲` and `۶` glyphs and an adjacent `۲۶`/`۶۲` pair.
- The script regenerated the README coverage matrix from controlled expected values. Combined counts (minimum 5 each): `۰` 13, `۱` 17, `۲` 32, `۳` 7, `۴` 10, `۵` 14, `۶` 25, `۷` 8, `۸` 8, `۹` 6, comma 25.
- E-03 v2 regression: **9 passed, 4 subtests passed**. The v2 pages, verifier, and tests remain unchanged.

Learning page 1 has four 8-digit line totals (`12,626,262`, `12,156,156`, `12,525,252`, `12,240,036`) and an 8-digit payable (`49,547,706`).

## Scope limit

This verifies authored values and entry arithmetic only. No Holo Windows application, printer, KandooPrintProbe spool capture, or actual SPL-to-PNG conversion is available in Arena. The owner must still confirm that Holo can hide its unit-price column in the print form and provide real capture evidence before print-capture validation is claimed.
