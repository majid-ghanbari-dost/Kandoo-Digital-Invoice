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

`--captured-at` accepts an offset-aware ISO 8601 value and remains available
for callers whose report does not contain a timestamp. The adapter also reads
one exact `Timestamp: <ISO-8601-with-offset>` line from `Report.txt`, uses it as
`captured_at`, and forwards it to E-02. If both sources provide a timestamp,
they must identify the same instant or the folder is blocked. The E-27 harness
uses an explicitly synthetic key/value subset: `Spool job ID:`, `Timestamp:`,
`Page count:`, and optional `SPL SHA-256:`. This is not asserted to be the real
KandooPrintProbe report format; production-format confirmation remains pending.
Unknown report lines stay opaque and the raw file's bytes, hash, and line count
remain inventoried.

The machine-readable result is JSON on stdout unless `--out` is supplied, in
which case it is written atomically to that file. A concise human summary is
always written to stderr so stdout remains pipe-safe JSON. The result uses the
E-06 verdict strings `ACCEPT`, `REVIEW`, and `REJECT`; capture-artifact
validation failures are represented as `status: BLOCKED` / `verdict: REVIEW`
with stable error codes. Exit codes follow the existing CLI convention: 0
accepted/ready, 10 review, 20 blocked/rejected, and 30 command-line input or
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
  but not parsed, executed, or converted by this adapter. If a synthetic/test
  report includes `SPL SHA-256:`, the digest is checked against the exact SPL
  bytes; this does not imply knowledge of the SPL binary format.
- Exactly one readable, non-empty UTF-8 `Report.txt` is required. Its bytes,
  SHA-256, and line count are recorded. The narrow key/value subset described
  above is parsed only when those exact fields are present: duplicate spool
  job IDs, invalid timestamps, zero/mismatched page counts, and a mismatched
  optional SPL digest fail closed. `Page count:` must match the number of PNG
  files when present. This parsing is synthetic harness behavior, not a claim
  about the unverified real Probe report format.
- At least one readable PNG is required. Each file must decode as PNG; one bad
  page fails the folder rather than being skipped.
- Extension matching is case-insensitive. PNG pages are ordered by natural,
  case-insensitive filename order (`page2.png` precedes `page10.png`), with the
  original filename as a deterministic tie-breaker. All pages are treated as
  one invoice; line rows are concatenated in that order and retain source-page
  indices.
- Unknown sibling files are tolerated and listed in `artifacts.extra_files`.
  Duplicate SPL or Report files are ambiguous and fail closed.
- Missing/ambiguous/empty required artifacts, malformed report metadata, and
  invalid PNGs return `status: BLOCKED` / `verdict: REVIEW`, exit 20, and
  explicit error codes (including `MISSING_SPL`, `MISSING_PNG`, `EMPTY_JOB`,
  `DUPLICATE_JOB_ID`, and `PAGE_COUNT_MISMATCH`). No missing page is silently
  omitted. Invalid CLI arguments or output I/O still use exit 30.

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
`tests/fixtures/real/{29,31,32,33}.png`, synthetic `.spl` bytes, and a
synthetic `Report.txt`. They cover timestamp forwarding from the report,
conflicting timestamps, checksum corruption, an empty-job declaration, a
duplicate spool job ID, a two-PNG/page-count mismatch, missing artifacts,
natural multi-page ordering, and tolerated extra files. The Windows bundle
verifier additionally runs the built executable via the E-12 capture-folder
adapter against fixture-derived Canonical JSON goldens and checks stable
blocked exit codes for the failure cases. The fixture PNGs are legacy renders
and the SPL/report files are not genuine KandooPrintProbe outputs. In
particular, the `Timestamp:`, `Page count:`, and optional `SPL SHA-256:` test
fields are synthetic harness conventions, not verification of a real Probe
report format. The tests verify harness plumbing and fail-closed behavior only;
they do not verify Windows spool generation, SPL-to-PNG rendering, physical
print/scan variance, or v2-page OCR accuracy.

The default E-05 bank is label-derived from the same four legacy fixtures, so
matches involving those exact PNGs are resubstitution evidence. When the input
PNG hash equals a known training fixture, the JSON marks
`resubstitution_source_fixture` and `independent_evidence: false`. Replace the
development bank with an approved locked per-store bank before treating any
match as independent evidence. No fixture data are written to a live sale or
stock movement.
