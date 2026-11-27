# O15 Windows extractor bundle v1

This E-60 deliverable packages the existing local Glyph image pipeline in a Windows PyInstaller one-folder directory. The assigned Arena branch was missing this pipeline; only the files listed in `o15-source-provenance.json` were ported from `origin/main` `180b279b6c692f841cab739577ad4fedeefb77c3`. No branch switch, merge, or rebase was performed.

## Stable executable surface

The Windows executable is `dist/kandoo-extract/kandoo-extract.exe` inside the CI-built `kandoo-extract-windows-<sha>` artifact. It is offline and does not require Tesseract. The application source entry is `python -m image_extraction_adapter.cli`.

| Outcome | Exit code | Meaning |
|---|---:|---|
| Ready | 0 | A schema-valid Canonical Invoice v0 candidate is emitted. |
| Review | 10 | A candidate needs operator review, or a readable image has an unknown/uncertain layout. No implicit correction occurs. |
| Blocked/reject | 20 | Invalid/unreadable capture or an unsafe extraction boundary; no Canonical Invoice is emitted. |
| Input/runtime error | 30 | Invalid CLI input or an internal error. |

For the existing image command, producer-owned Canonical v0 context is required:

```powershell
kandoo-extract.exe extract --image PAGE.png --context canonical-context.json
```

The CLI never invents invoice identifiers, store/device IDs, customer details, or product names. Exit 10 may contain a valid candidate or empty stdout; callers must check the exit code. Output is UTF-8 JSON without BOM, with LF line endings and a final LF.

For a KandooPrintProbe capture folder (one `.spl`, one `Report.txt`, and one or more `.png` pages):

```powershell
kandoo-extract.exe extract --capture-folder C:\path\to\capture `
  --e05-bank C:\path\to\approved-e05-bank.json `
  --out C:\Users\<owner>\AppData\Local\Kandoo\O15\run-001\capture-folder-result.json `
  --review-evidence-dir C:\Users\<owner>\AppData\Local\Kandoo\O15\run-001\review-evidence
```

The capture-folder API is the frozen `capture-folder-result-v1` schema at `schemas/extraction-bridge/v1/capture-folder-result.schema.json`. `--review-evidence-dir` must be a new directory outside the repository/bundle and separate from the source capture folder. The Windows one-folder bundle includes the evidence and operator-label schemas under `_internal/schemas/o15/`. It also supports `kandoo-extract.exe operator-label-template --evidence-dir <review-evidence-dir>` to create a local `operator-labels.local.json`. The local demo wrapper can additionally accept `--context` for a one-page Canonical v0 candidate and an optional `--v1-1-recorded-fields` file. v1.1 extension fields are validated and passed through separately; they are not merged into or used to modify frozen Canonical v0. If the extractor has no schema-valid candidate, the demo emits `canonical_invoice_v0: null` and a REVIEW note rather than fabricating values.

```powershell
python scripts/demo_capture.py --capture-folder C:\path\to\capture `
  --out-dir C:\Users\<owner>\AppData\Local\Kandoo\O15\run-001 `
  --context C:\path\to\producer-context.json `
  --v1-1-recorded-fields C:\path\to\recorded-v1-1-fields.json
```

`--out-dir` must be new and outside the repository. It contains `demo-output.json`, the detailed `capture-folder-result.json`, and `review-evidence/` with `review-evidence-v1.json`, field/layout crop PNGs, a self-contained `review-queue.html`, and a blank `operator-labels.local.json` generated from the field evidence. The evidence schema is `schemas/o15/review-evidence-v1.schema.json`; each record uses `value`, `confidence` (0–100), `reason`, and a half-open image-pixel `crop_region` `[left, top, right, bottom]`. The label schema is `schemas/o15/operator-label-v1.schema.json`; set `read_correctly` to `true` or `false`, and provide `corrected_value` only when false. Leave both fields null until reviewed. The frozen capture-folder v1 JSON is not changed. The queue says “What I read” and explicitly does not treat the machine reading as confirmed truth; accuracy remains `NOT_SCORED` without independent expected values. Operator labels never train/update Glyph and are not sent back to extraction. The real capture, OCR, labels, crops, queue, and JSON must never be uploaded, sent in chat, or added to Git/CI.

## Byte determinism and CI

`requirements-extractor.txt` pins Pillow and jsonschema. `tests/fixtures/o15/` is synthetic-only. `scripts/verify_o15_e60.py` executes the same capture-folder and demo invocations against the committed goldens in `tests/golden/o15/`; Ubuntu source mode and the Windows executable must both match the exact same UTF-8/LF bytes. A match by both platforms proves equality to the same bytes. CI never reads an owner capture; the Windows bundle artifact contains the app only.

A synthetic smoke is not an accuracy claim. The owner-local run remains separate and is required to report E-63.
