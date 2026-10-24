# E-03 print-extraction kit — v2

This kit has **exactly three learning pages and one exam page**. Its four controlled value sets are intended to be entered as fabricated test invoices in Hello, printed by Hello on Windows, and captured from the real Windows print spool.

## The four pages

| Role | Page file |
|---|---|
| Learning | [`learning-1.md`](learning-1.md) |
| Learning | [`learning-2.md`](learning-2.md) |
| Learning | [`learning-3.md`](learning-3.md) |
| Exam | [`exam.md`](exam.md) |

The page files are entry guides, **not print-source documents**. Do not print these Markdown pages or recreate the invoices in a word processor. Each page corresponds to one Hello print job.

## Numeric ground-truth scope

For each item, the only numeric values in scope are **quantity** and **line total**. **Payable is invoice-level.** There is no unit-price column, no unit-price answer, and no unit-price calculation in this kit. The answer key [`expected-values.json`](expected-values.json) contains only the four pages' `quantities`, `line_totals`, and `payable` fields. It intentionally contains no item labels, invoice metadata, prices, tax, discount, or other numeric fields.

The controlled answer-key strings use Persian glyphs `۰`–`۹` and the standard comma `,` as the target print characters. Counts are computed only from the controlled quantity, line-total, and payable strings in the four page files / expected-values file. Page headings, item labels, this matrix, generated invoice metadata, and other text are not counted. Hello's rendered glyphs have not been verified; the owner must compare the actual PNG with these targets before claiming print coverage.

### Combined glyph-coverage matrix

| Numeric digit | Printed glyph | Count across all four pages | Meets minimum of 5? |
|---:|---:|---:|---|
| 0 | `۰` | 10 | Yes |
| 1 | `۱` | 14 | Yes |
| 2 | `۲` | 23 | Yes |
| 3 | `۳` | 9 | Yes |
| 4 | `۴` | 12 | Yes |
| 5 | `۵` | 11 | Yes |
| 6 | `۶` | 20 | Yes |
| 7 | `۷` | 6 | Yes |
| 8 | `۸` | 8 | Yes |
| 9 | `۹` | 7 | Yes |
| comma | `,` | 20 | Yes |

Each of the eleven required glyphs occurs at least five times in the combined controlled values. The per-page values also retain at least five instances each of Persian `۲` and `۶` for the existing E-06 kit-scoped coverage gate. Run `python scripts/verify_e03_kit_v2.py` from the repository root to recheck the page count, page tables, arithmetic, glyph counts, and this matrix.

## Owner-confirmed safety decision

**Hello test invoices contain fabricated data only. No real customer, sale, or stock movement occurs. There is nothing to cancel, delete, or roll back. The print job itself is the test artifact; the fake invoice may be discarded.**

Do not use or enter real customer, sale, or stock data. Do not add numeric fields outside the specified quantities, line totals, and invoice-level payable. If the Hello test path would require an unapproved real sale or stock movement, stop rather than substituting another print source.

## Required Hello → SPL → PNG capture workflow

1. Use the actual **Hello Windows application** and only the fabricated test values on the selected page. Enter each item's quantity and line total, then the invoice-level payable. Do not infer, add, or enter a unit price. If Hello requires a unit-price input instead of accepting the specified line totals, stop and ask the owner; do not invent a price or change this answer key.
2. Print that invoice from Hello to the intended Windows printer queue. One source page is one Hello print job. The Hello-generated print job—not a document assembled elsewhere—is the test artifact.
3. While the real print job is in the Windows spooler, use **KandooPrintProbe** to capture its actual `.SPL` spool file. Have the probe convert that SPL to a `.PNG`; the PNG is the downstream OCR/extraction input. Keep the captured SPL with its derived PNG for traceability.
4. Have KandooPrintProbe write `Report.txt` beside the PNG for that print job. The report must identify the printer, Windows spool job ID, timestamp (ISO 8601 with an explicit zone offset), and page count. Expected sidecar layout:

   ```text
   captures/
     learning-1/
       learning-1.spl
       learning-1.png
       Report.txt
     learning-2/
       learning-2.spl
       learning-2.png
       Report.txt
     learning-3/
       learning-3.spl
       learning-3.png
       Report.txt
     exam/
       exam.spl
       exam.png
       Report.txt
   ```

   Each `Report.txt` should contain, at minimum:

   ```text
   Printer: <Windows printer queue name>
   Spool job ID: <Windows spool job ID>
   Timestamp: <ISO-8601 timestamp with zone offset>
   Page count: 1
   ```

5. Do not substitute a phone scan, screenshot, word-processor print, generated image, or reconstructed SPL for the actual Hello Windows print job. Do not count a capture as verified merely because a PNG or report file exists.

The optional capture check is `python scripts/verify_e03_kit_v2.py --capture-root <captures-directory>`. It checks the agreed filenames, nonempty SPL, PNG signature, required report fields, timestamp zone, and one-page count. It checks file/metadata shape only: it cannot prove that a spool file came from Hello or that the PNG was correctly converted. Those checks require the owner's real Windows print job and review of its output.

**Print-capture verification needed from the owner.** No Windows printer or Hello print job is available in the Arena sandbox; no actual SPL capture or SPL-to-PNG conversion is claimed as locally verified.
