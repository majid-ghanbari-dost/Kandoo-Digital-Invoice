# Extraction Bridge Golden Pack v1

- **Pack ID:** `e30.extraction-bridge.golden.v1`
- **Contract:** [`../../cli-surface-v1.md`](../../cli-surface-v1.md)
- **Manifest:** [`manifest.json`](manifest.json)

This pack exercises the byte-facing `extract --image`, `extract --capture-folder`, `--drift-report`, `onboard build`, `onboard verdict`, and `onboard register-type` paths. Each generated JSON artifact is compared byte-for-byte with the committed file in `expected/`; all expected JSON is UTF-8, has no BOM or CR bytes, uses LF, and ends with LF. The fixture/output SHA-256 and byte lengths are pinned in `manifest.json`.

The Ubuntu Python job runs `scripts/verify_e30_golden_pack.py` in source mode. The Windows workflow runs the same verifier against the just-built PyInstaller one-folder executable. Both use the same pack and expected byte files; neither rewrites goldens.

## Evidence boundary

- `fixtures/capture-folder/Report.txt` and `capture-job.spl` are explicitly synthetic mechanics data. They are not authentic KandooPrintProbe output, real SPL/SHD, or product-owner evidence.
- `fixtures/capture-folder/page1.png` is a byte-identical copy of the repository's existing `tests/fixtures/real/29.png`. Its numeric content is used only for an executable smoke comparison.
- `fixtures/canonical-context-29.json` uses synthetic producer IDs, phone, and product-name placeholders. It is not a live customer or issuance context.
- E-20/E-03 onboarding inputs are synthetic mechanics fixtures. The resulting bank/verdict/candidate goldens do not represent production onboarding or a production-approved bank.
- No expected output is an accuracy claim. E-31's separate harness measures the checked-in labeled real-render fixtures and reports its limits.

## Files

- `fixtures/` — versioned input bytes, including the E-20 source report/answer key, deterministic observations, synthetic context, raw E-05 bank, and capture folder.
- `expected/` — exact command output bytes for each deterministic invocation.
- `manifest.json` — pinned SHA-256 and size for every fixture and expected output (the manifest does not hash itself).
