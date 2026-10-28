# B2-3 real-invoice E2E run — operator instructions

Run this diagnostic on the operator PC. It uses local Tesseract and the repository's Glyph classifier; it does not call a VLM, cloud OCR, or another network service.

## Prerequisites

- Tesseract installed from the [UB-Mannheim Windows installer](https://github.com/UB-Mannheim/tesseract/wiki), with `tesseract.exe` available on `PATH`.
- Tesseract traineddata for both `fas` and `eng` available to the local installation (the script requests `fas+eng`).
- Python 3.11 or newer installed and available as `python` in PowerShell.
- Pillow installed: `python -m pip install Pillow`.
- Git installed and authenticated for the project's GitHub remote.
- Repository cloned, with the current branch set to `arena/9dc17500-kandoo-digital-invoice`.
- Latest branch changes pulled before running the diagnostic.

The script has no required command-line arguments. It uses `/tmp/kandoo-t2-venv` if that interpreter exists on the host; otherwise it continues with the Python interpreter used to launch it. On a normal Windows PC, use system Python.

## Run the diagnostic

Open PowerShell from within the cloned repository (the repository root or any subdirectory) and paste this block as-is:

```powershell
$repo = git rev-parse --show-toplevel
Set-Location -LiteralPath $repo
git pull origin arena/9dc17500-kandoo-digital-invoice
python scripts/run_e2e_real.py
```

The script first checks for Tesseract. If found, it runs all four fixtures (`29.png`, `31.png`, `32.png`, and `33.png`) in both `glyph` and default `tesseract_parse` authority modes. It prints each outcome, reason, numeric cell results, runtime payable bbox beside the labeled reference bbox, and arithmetic-gate result. It writes the complete UTF-8 output to `docs/e2e-real-report.md`, including the timestamp, Tesseract/Python/Pillow versions, and Git HEAD SHA.

## If the run succeeds

Review `docs/e2e-real-report.md`, then commit and push the report:

```powershell
git add docs/e2e-real-report.md
git commit -m "docs(e2e): B2-3 report from operator PC"
git push origin arena/9dc17500-kandoo-digital-invoice
```

## If the script fails for a reason other than missing Tesseract

Capture the complete console output to the error log. Do not stage the E2E report in this case; commit the error log instead:

```powershell
python scripts/run_e2e_real.py *> docs/e2e-error.log
$e2eExitCode = $LASTEXITCODE
if ($e2eExitCode -ne 0 -and $e2eExitCode -ne 30) {
    git add docs/e2e-error.log
    git commit -m "docs(e2e): B2-3 error log from operator PC"
    git push origin arena/9dc17500-kandoo-digital-invoice
}
```

If the first run already failed, rerun it with this redirection to capture the output. Stage only `docs/e2e-error.log`; if an E2E report was also created, do not include it in this error-log commit.

## If Tesseract is missing

The script prints the following and exits with code `30` before running OCR or writing `docs/e2e-real-report.md`:

```text
ERROR: Tesseract is not installed or not on PATH.
Please install Tesseract from:
https://github.com/UB-Mannheim/tesseract/wiki
Then add it to your PATH and re-run this script.
```

Do **not** commit anything for this case. Install Tesseract, ensure it is on `PATH` (and `fas`/`eng` traineddata are available), then rerun the diagnostic.
