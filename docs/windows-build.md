# Windows one-folder CLI build (E-19)

**Status:** complete. Native Windows build, focused tests, and frozen-executable smoke passed.

## Scope and reproducible workflow

The [`Windows one-folder build`](../.github/workflows/windows-build.yml) workflow runs on `windows-latest` with Python 3.11. It installs `pytest`, Pillow, `jsonschema>=4.18,<5`, and PyInstaller 6.22.3; runs Windows tests for `pipeline_v0`, the extraction adapter, E-05, E-06, and the frozen E-11 contract package; builds the `kandoo-extract.exe` one-folder CLI; and runs the frozen executable's `extract` command on real fixtures 29, 31, 32, and 33. The default Glyph template bank and E-01 schema are placed at the source-relative paths expected by the current modules. The full cross-repository suite remains covered by the existing Ubuntu matrix in `python-tests.yml`.

The workflow does **not** install Tesseract or `tesserocr`. Before each frozen smoke run, the verifier asserts that neither the Tesseract executable nor the `tesserocr` module is available. It does not pass `--templates`, so successful extraction also verifies the bundled default Glyph bank.

## Canonical comparison boundary

There is no honest byte-for-byte comparison between the four real-fixture outputs and the existing E-11 golden objects: E-11 goldens are synthetic examples with `quantity_millis` and pre-ISSUE display-number rules, while this CLI emits the older E-01 `quantity` shape and the four real invoices have their own label-derived canonical fixtures. The frozen files under `contracts/` remain untouched.

The workflow uses this explicit **test-only crosswalk**:

1. Compare each executable output's row count, quantity, line total, subtotal, and payable to its matching label-derived `tests/fixtures/real/canonical/canonical-{29,31,32,33}.json` object.
2. Validate the emitted object against the current E-01 schema.
3. For contract-shape comparison only, project `quantity` to `quantity_millis = quantity × 1000` and mark the pre-ISSUE display number unavailable. Validate that projection against the frozen E-11 schema and compare its contract key-shape with E-11's `draft_mode_b_null_display_number.json` golden. The synthetic values in that E-11 golden are not treated as expected values for the real images.

This projection exists only in the smoke-test process; it does not modify CLI output or any frozen contract.

## CI evidence

- **Passing Windows run:** [40176606025](https://github.com/majid-ghanbari-dost/Kandoo-Digital-Invoice/actions/runs/40176606025), verified commit `be083056cc7f1f7d75944d4adec63c1b5d257b99`.
- **Windows test groups:** all five passed (`pipeline_v0`, extraction adapter, E-05, E-06, E-11 contract package).
- **Executable size:** 3,671,939 bytes (3.502 MiB).
- **One-folder directory size:** 34,117,267 bytes (32.537 MiB, including the executable, dependencies, Glyph bank, and E-01 schema).
- **Startup timing:** `kandoo-extract.exe extract --help`, five fresh process launches; minimum 0.1604 s, median 0.1749 s, maximum 0.1927 s.
- **Real fixtures:** 29 (4 rows), 31 (3 rows), 32 (5 rows), and 33 (13 rows) all exited 0; every row quantity/line total and both summary totals matched its fixture-specific canonical golden. No template path was passed.
- **Tesseract:** executable absent; `tesserocr` absent. No Tesseract dependency was installed.
- **Artifact:** `windows-onefolder-40176606025`, uploaded by the passing run; it contains the one-folder build and the JSON/Markdown evidence report (14-day retention).

### Failures and deviations recorded

- The initial Windows attempt to run the entire 1,898-test suite exceeded the 45-minute job limit while still in pytest. It timed out without a completed test summary; this is not diagnosed as an assertion failure. Windows CI was narrowed to the extraction/runtime and contract tests above, while the full suite remains on the Ubuntu Python 3.11/3.12 workflow. The local full suite passed with 1,898 tests and 82 subtests.
- The first focused Windows run's E-11 byte-stability group failed. After the workflow explicitly disabled `core.autocrlf` and restored the frozen `contracts/` files from Git, that test group passed in subsequent runs. No files under `contracts/` were changed.
- A non-blocking GitHub Actions warning notes that the checked-out `actions/*@v4/v5` steps are being forced to Node.js 24; it did not affect the passing build.

The passing run's uploaded `windows-build-evidence.md` and `.json` are the raw per-run record. A Linux build is not a substitute for the native Windows result.
