# Windows one-folder CLI build (E-19)

**Status:** implementation is ready; Windows CI evidence is pending the first `windows-build.yml` run.

## Scope and reproducible workflow

The [`Windows one-folder build`](../.github/workflows/windows-build.yml) workflow runs on `windows-latest` with Python 3.11. It installs `pytest`, Pillow, `jsonschema>=4.18,<5`, and PyInstaller 6.22.3; runs the full Python test suite; builds the `kandoo-extract.exe` one-folder CLI; and runs the frozen executable's `extract` command on real fixtures 29, 31, 32, and 33. The default Glyph template bank and E-01 schema are placed at the source-relative paths expected by the current modules. The resulting bundle and machine-readable/human-readable evidence are uploaded as the `windows-onefolder-<run-id>` artifact.

The workflow does **not** install Tesseract or `tesserocr`. The smoke script records and asserts that neither the Tesseract executable nor `tesserocr` is available before invoking the built CLI. It does not pass `--templates`, so a successful extraction also verifies the bundled default Glyph bank.

## Canonical comparison boundary

There is no honest byte-for-byte comparison between the four real-fixture outputs and the existing E-11 golden objects: E-11 goldens are synthetic examples with `quantity_millis` and pre-ISSUE display-number rules, while this CLI emits the older E-01 `quantity` shape and the four real invoices have their own label-derived canonical fixtures. The frozen files under `contracts/` remain untouched.

The workflow uses this explicit **test-only crosswalk**:

1. Compare each executable output's row count, quantity, line total, subtotal, and payable to its matching label-derived `tests/fixtures/real/canonical/canonical-{29,31,32,33}.json` object.
2. Validate the emitted object against the current E-01 schema.
3. For contract-shape comparison only, project `quantity` to `quantity_millis = quantity × 1000` and mark the pre-ISSUE display number unavailable. Validate that projection against the frozen E-11 schema and compare its contract key-shape with E-11's `draft_mode_b_null_display_number.json` golden. The synthetic values in that E-11 golden are not treated as expected values for the real images.

This projection exists only in the smoke-test process; it does not modify CLI output or any frozen contract.

## CI evidence

Populate this section from the first successful Windows workflow run:

- Workflow run / commit: pending.
- Full-suite result: pending.
- Bundle size: pending.
- `extract --help` process-startup timing (five launches; min/median/max): pending.
- Real fixture 29/31/32/33 results: pending.
- Tesseract absence check: pending.
- Failures or deviations: pending.
- Artifact: pending.

The workflow's uploaded `windows-build-evidence.md` and `.json` are the raw per-run record; this document is the checked-in handoff summary. A Linux build is not a substitute for the native Windows result.
