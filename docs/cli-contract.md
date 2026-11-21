# E-09 CLI contract

## 1. Overview

`image_extraction_adapter.cli` is the local process boundary between the Python
E-02 image pipeline and the parent platform. The C# caller starts it with
`Process.Start`, supplies an image and producer-owned Canonical Invoice
context, reads UTF-8 Canonical Invoice JSON from stdout, and interprets the
process exit code as the extraction routing result.

The CLI does not generate platform identifiers, customer information, or
human-readable product names. Those values must be supplied in a JSON context
file by the caller. This preserves the E-01 contract boundary and the E-02 rule
against inventing required invoice fields.

## 2. Command reference

Run from the repository root:

```text
PYTHONPATH=src python -m image_extraction_adapter.cli extract \
  --image PATH --context PATH [--captured-at ISO] [--templates PATH]
```

Arguments:

| Argument | Required | Meaning |
| --- | --- | --- |
| `extract` | Yes | Run one local E-02 extraction. |
| `--image PATH` | Yes | Existing local image file to process. |
| `--context PATH` | Yes | Existing UTF-8 JSON object containing the producer-supplied `canonical_context` fields: mode, platform IDs/token, customer data, and product names/provenance. It is not a wrapper object. |
| `--captured-at ISO` | No | ISO 8601 datetime with an explicit UTC offset, such as `2026-10-22T09:30:00Z`. |
| `--templates PATH` | No | Existing local Glyph template bank. Defaults to `src/templates_bank_default.json`. |

The E-02 API cannot construct Canonical Invoice v0 without producer-owned
context. Therefore `--context` is required for this CLI to produce an AUTO or
REVIEW Canonical Invoice. It is never synthesized from OCR, filenames, or dHash
clusters.

## 3. Exit codes

| Code | Meaning | stdout |
| ---: | --- | --- |
| `0` | `AUTO_CANDIDATE` with a schema-valid Canonical Invoice candidate. | Canonical JSON. |
| `10` | `REVIEW`. If a schema-valid candidate can be assembled, stdout contains it; otherwise stdout is empty and the reason is written to stderr. | Candidate JSON or empty. |
| `20` | `REJECT` / blocked extraction. A blocked result has no Canonical Invoice. | Empty. |
| `30` | Invalid arguments or paths, invalid timestamp/context, internal exception, or Canonical schema validation failure. | Empty. |

The exit code communicates pipeline routing. No pipeline-status property is
added to the frozen Canonical Invoice schema.

## 4. Output format

When a Canonical candidate exists, stdout contains exactly one Canonical Invoice
v0 JSON object encoded as UTF-8, followed by a newline. There is no status
wrapper, log prefix, or diagnostic text in stdout. The CLI independently calls
`validate_canonical_invoice()` immediately before writing the object.

For `REJECT`, and for a `REVIEW` result for which E-02 cannot assemble a
schema-valid candidate, stdout is empty; details go to stderr. A caller must
not interpret an empty stdout stream as an invoice. The exit code and stderr
explain the routing result.

## 5. Usage examples

The following context is synthetic documentation data only. Production callers
must supply their actual producer-owned values through a local file and must
protect customer data according to the product's data-handling decisions.

Example `canonical-context.json`:

```json
{
  "mode": "B",
  "invoice_id": "producer-invoice-id",
  "display_number": "producer-display-number",
  "operation_id": "producer-operation-id",
  "device_id": "producer-device-id",
  "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
  "store_id": "producer-store-id",
  "customer": {
    "phone": "+15551234567",
    "phone_status": "claimed",
    "phone_provenance": "captured"
  },
  "product_names": ["Example product one", "Example product two"],
  "product_name_provenance": ["captured", "captured"]
}
```

The number of `product_names` and `product_name_provenance` entries must match
the detected item rows. The example IDs and phone are not production defaults.

### Bash

```bash
PYTHONPATH=src python -m image_extraction_adapter.cli extract \
  --image tests/fixtures/real/29.png \
  --context /secure/local/path/canonical-context.json \
  --captured-at 2026-10-22T09:30:00Z
```

### PowerShell

```powershell
$env:PYTHONPATH = "src"
python -m image_extraction_adapter.cli extract `
  --image "tests/fixtures/real/29.png" `
  --context "C:\Kandoo\private\canonical-context.json" `
  --captured-at "2026-10-22T09:30:00Z"
$exitCode = $LASTEXITCODE
```

## 6. How C# calls this CLI

Use `ProcessStartInfo.ArgumentList` rather than shell-concatenated command text,
redirect both streams, and set UTF-8 explicitly. The Python process reads only
local files; the parent should securely create and manage the context file.

```csharp
using System.Diagnostics;
using System.Text;

var start = new ProcessStartInfo
{
    FileName = "python",
    WorkingDirectory = repositoryRoot,
    UseShellExecute = false,
    RedirectStandardOutput = true,
    RedirectStandardError = true,
    StandardOutputEncoding = Encoding.UTF8,
    StandardErrorEncoding = Encoding.UTF8,
};
start.Environment["PYTHONPATH"] = Path.Combine(repositoryRoot, "src");
start.ArgumentList.Add("-m");
start.ArgumentList.Add("image_extraction_adapter.cli");
start.ArgumentList.Add("extract");
start.ArgumentList.Add("--image");
start.ArgumentList.Add(imagePath);
start.ArgumentList.Add("--context");
start.ArgumentList.Add(contextPath);

using var process = Process.Start(start)
    ?? throw new InvalidOperationException("Could not start invoice extraction CLI.");
string stdout = await process.StandardOutput.ReadToEndAsync();
string stderr = await process.StandardError.ReadToEndAsync();
await process.WaitForExitAsync();

// Interpret process.ExitCode (0, 10, 20, or 30) before consuming stdout.
```

The sample demonstrates process invocation only; it does not implement the
parent application, context-file security, invoice persistence, or issuance.

## 7. Error handling

Argument parsing, missing/non-file paths, invalid `--captured-at`, invalid
context JSON, and schema failures return `30`. Human-readable diagnostics are
written to stderr. Unexpected exceptions include debugging details on stderr;
stack traces are never written to stdout. The CLI does not emit partial JSON.

`REJECT` returns `20` with the pipeline reason on stderr and no Canonical JSON.
`REVIEW` returns `10`; a candidate is emitted only when E-02 could assemble and
validate one. If no candidate exists, stderr explains why and stdout remains
empty. A caller must preserve REVIEW rather than auto-correcting uncertain
values.

## 8. What is not included

- No HTTP server or listening socket.
- No network calls or cloud OCR.
- No Tesseract executable or Tesseract OCR call is required.
- No generated platform IDs, customer phone/status, product names, or
  `canonical_context`.
- No image upload, invoice persistence, lifecycle advancement, validation-to-
  issuance transition, or issuance operation.
- No automatic correction, arithmetic repair, threshold tuning, or accounting
  computation.

Images and the context file are read locally. The CLI emits only the validated
Canonical Invoice candidate when one exists; it does not transmit or persist
the source image.

## 9. Relationship to E-01 and E-02

E-02 (`pipeline_v0.py`) performs local layout detection, Glyph numeric-cell
recognition, arithmetic gating, description clustering, and routing to
`AUTO_CANDIDATE`, `REVIEW`, or `REJECT`. Its `canonical_context` is
caller-owned. The CLI passes the local image, local template bank, optional
capture timestamp, and supplied context to that API without changing the E-02
pipeline.

E-01 (`canonical_invoice.py` and
`schemas/canonical_invoice_v0.json`) defines the output structure and validator.
The CLI emits the pipeline's Canonical Invoice candidate only after validating
it against E-01. Pipeline routing status is represented by the process exit
code, not by adding fields or states to the Canonical Invoice contract.
