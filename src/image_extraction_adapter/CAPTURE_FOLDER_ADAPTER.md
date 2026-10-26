# KandooPrintProbe capture-folder adapter

## CLI

From the repository root, with `src/` on `PYTHONPATH`:

```sh
PYTHONPATH=src python -m image_extraction_adapter.cli extract \
  --capture-folder <capture-folder> [--captured-at <ISO-8601>] [--out <result.json>]
```

The adapter module is `image_extraction_adapter.capture_folder`.
`--templates <path>` may select an alternate E-02/Glyph bank; `--e05-bank <path>` may select an approved serialized E-05 layout bank. If no E-05 bank is
specified, the local default is built from the repository's existing fixture
labels and Canonical fixtures; this is a development proxy, not a store's
production bank. E-05 bank artifacts store a `currency_unit` field; only the
explicit values `rial` and `toman` are confirmed. Unset or unsupported values
are reported as unconfirmed and keep E-06 in REVIEW. No currency conversion is
performed.

`--captured-at` accepts the offset-aware ISO 8601 `captured_at` value supplied
by KandooPrintProbe. The caller must pass it explicitly; the adapter records it
and forwards it to E-02. The raw `Report.txt` remains inventoried, not parsed,
because the real Probe report format has not been supplied.

The machine-readable result is JSON on stdout unless `--out` is supplied, in
which case it is written atomically to that file. A concise human summary is
always written to stderr so stdout remains pipe-safe JSON. The result uses the
E-06 verdict strings `ACCEPT`, `REVIEW`, and `REJECT`; adapter status separately
identifies `ERROR` or `BLOCKED` outcomes. Exit codes follow the existing CLI
convention: 0 accepted/ready, 10 review, 20 blocked/rejected, and 30 input or
output error.

## Folder contract

The adapter inspects immediate files in one capture folder:

```text
<capture-folder>/
  <one-job>.spl
  <page-1>.png
  <page-2>.png       # zero or more additional PNG pages
  Report.txt
  <optional extra files>
```

- Exactly one non-empty `*.spl` file is required. It is hashed and inventoried
  but not parsed, executed, or converted by this adapter.
- Exactly one readable, non-empty UTF-8 `Report.txt` is required. Its bytes,
  SHA-256, and line count are recorded. Probe-specific key/value content is not
  interpreted because a real Probe report format has not yet been supplied.
- At least one readable PNG is required. Each file must decode as PNG; one bad
  page fails the folder rather than being skipped.
- Extension matching is case-insensitive. PNG pages are ordered by natural,
  case-insensitive filename order (`page2.png` precedes `page10.png`), with the
  original filename as a deterministic tie-breaker. All pages are treated as
  one invoice; line rows are concatenated in that order and retain source-page
  indices.
- Unknown sibling files are tolerated and listed in `artifacts.extra_files`.
  Duplicate SPL or Report files are ambiguous and fail closed.
- Missing/ambiguous/empty required artifacts and invalid PNGs return
  `status: ERROR` with explicit error codes (including `MISSING_SPL` and
  `MISSING_PNG`) and the E-06-compatible overall `verdict: REJECT`. No missing
  page is silently omitted.

## Extraction and verdict behavior

Every ordered PNG is passed through the existing E-02 `extract_pipeline_v0`
path. Extracted quantity, line-total, and payable candidates are then placed in
an E-05 `LayoutObservation` when safe page geometry and a payable box are
available; each page receives a separate E-05 layout match. The output exposes
only the numeric candidate classes `quantity`, `line_total`, and `payable` for
the kit-v2 comparison scope. No expected-value labels are present in this
folder contract, so the adapter marks accuracy `NOT_SCORED`; it does not claim
an accuracy result. It does not compare or score unit price, subtotal, product
name, or other numeric values, and it never sums or arbitrarily chooses among
multiple page-level payable candidates.

Capture folders do not supply producer-owned Canonical Invoice context such as
platform identifiers, customer data, or a human-readable product-name mapping.
The adapter does not fabricate these values. E-06 therefore returns `REVIEW`
for a well-formed folder until that context is provided through a separate
approved integration. An E-02 blocked page overrides the overall verdict to
`REJECT`/`BLOCKED`. `ACCEPT` is not attainable from the capture-folder inputs
alone. `e06` and per-page `e02`/`e05` details remain in the JSON result for
diagnosis.

## Synthetic test coverage and evidence limit

Tests construct synthetic capture directories using repository PNG fixtures
`tests/fixtures/real/{29,31,32,33}.png`, a non-empty synthetic `.spl` byte
file, and a synthetic `Report.txt`. They cover the valid one-page path, missing
SPL, missing PNG, natural multi-page ordering, and tolerated extra files. The
fixture PNGs are legacy renders and the SPL/report files are not genuine
KandooPrintProbe outputs. The multi-page test combines distinct synthetic
fixture pages to exercise ordering/aggregation plumbing; it is not a real
multi-page invoice. Consequently, the tests verify folder plumbing and
fail-closed behavior only; they do not verify a real Probe report format,
Windows spool generation, SPL-to-PNG rendering, physical print/scan variance,
or v2-page OCR accuracy.

The default E-05 bank is label-derived from the same four legacy fixtures, so
matches involving those exact PNGs are resubstitution evidence. When the input
PNG hash equals a known training fixture, the JSON marks
`resubstitution_source_fixture` and `independent_evidence: false`. Replace the
development bank with an approved locked per-store bank before treating any
match as independent evidence. No fixture data are written to a live sale or
stock movement.
