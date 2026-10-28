# Operator onboarding CLI (E-26)

This guide is for a C# Mode B client that starts the local Windows one-folder
CLI with `Process.Start`. The command surface wraps the existing E-05 template
builder/matcher, E-06 onboarding evaluator, and E-08 new-type detector. It does
not perform OCR, alter Canonical Invoice v0, issue an invoice, or install a new
template into the active bank.

## Commands and artifacts

The executable is `kandoo-extract.exe`. Its onboarding commands are:

```text
kandoo-extract.exe onboard build ...
kandoo-extract.exe onboard verdict ...
kandoo-extract.exe onboard register-type ...
```

Each emitted artifact is UTF-8 JSON without a BOM and is validated before it is
written against the frozen Draft 2020-12 schema under
`schemas/mode-b/v1/`:

| Command | E-16 artifact | Behavior |
|---|---|---|
| `onboard build` | `template-bank.schema.json` | Builds and exports an E-05 bank. The normal path requires operator-confirmed labels, their Canonical v0 fixtures/sidecar, and the PNGs under the capture root. Currency is always explicit. |
| `onboard verdict` | `onboarding-verdict.schema.json` | Writes the E-06 result and records SHA-256 over the exact input bank-file bytes. A verdict artifact is written for ACCEPT, REVIEW, and REJECT. |
| `onboard register-type` | `new-type-candidate.schema.json` | Runs E-08 and writes a candidate snapshot only when E-08 returns a candidate. The candidate remains `PROPOSED` and separate from the active bank. |

The CLI does not emit `layout-font-fingerprint.json`: that E-16 artifact also
requires the E-02 Glyph feature profile, which E-08's candidate API does not
produce. The CLI does not fabricate a font profile from layout geometry.

Output paths must be new; existing artifact files are not overwritten. The
parent directory is created if necessary. Choose versioned, store-scoped paths
for bank snapshots, and keep the exact bank bytes used for each verdict.

## Stable process exit codes

| Code | Meaning |
|---:|---|
| `0` | Operation completed without a review/reject hold. `build` wrote a bank, or E-06/E-08 returned ACCEPT. ACCEPT remains an onboarding result, not authorization to issue an invoice. |
| `10` | A valid artifact/result is held for human review. E-06 returned REVIEW, or E-08 returned a review outcome (including a proposed candidate). If E-08 creates no candidate, no candidate artifact is written. |
| `20` | E-06 returned REJECT, or E-08 identified a hard failure. A verdict artifact is still written for E-06 REJECT. |
| `30` | CLI arguments, input files, schemas, or output writing failed. No trustworthy result artifact is available. |

The concise status is written to standard error. Artifact data is written to the
requested file, not to standard output. Redirect both output streams when
calling the executable; do not decide outcomes by parsing human-readable
`details` text. Use the artifact's stable `verdict`, `reason_codes`, `candidate`
state, and process exit code.

## Build an E-05 bank

The normal training path requires all three inputs below:

```powershell
kandoo-extract.exe onboard build `
  --capture-root C:\onboarding\captures `
  --canonical-dir C:\onboarding\canonical `
  --labels C:\onboarding\labels.json `
  --store-id shop-opaque-id `
  --currency-unit rial `
  --output C:\onboarding\artifacts\template-bank-v1.json
```

`labels.json` must declare `label_status` as `OPERATOR_CONFIRMED`. Each label's
PNG path must resolve inside `--capture-root`; E-05 then checks the canonical
synthesis manifest, label/canonical numeric agreement, and image hashes. The
canonical fixtures must all carry the explicit `--store-id`. This command
builds the layout/numeric-format bank only. It neither infers currency nor
converts rial and toman.

`--confidence-threshold` is optional and defaults to the existing E-05 value
`0.85`; do not treat it as an E-06 verdict threshold. `--created-at` accepts an
ISO 8601 timestamp with an explicit UTC offset. When omitted, the CLI records
the current UTC time. IDs are opaque strings and are never inferred from a
folder, file name, or invoice value.

For the Windows/CI mechanics test only, the CLI also has an explicitly named
E-20 route. It consumes the checked-in synthetic E-20 measurement report and
E-03 v3 answer key; it does not mark those test labels as operator-confirmed:

```powershell
kandoo-extract.exe onboard build `
  --synthetic-e20-report C:\repo\docs\e20-second-store.json `
  --synthetic-e20-values C:\repo\docs\E-03-kit-v3\expected-values.json `
  --store-id synthetic-second-store `
  --currency-unit rial `
  --output C:\temp\e20-template-bank.json
```

This option exists to exercise serialization and command wiring. E-20's pages
are synthetic mechanics fixtures, not Holo captures, real-store evidence, or
production-accuracy evidence. Do not use this route to train a production bank.

## Evaluate an E-06 verdict

All decision inputs are explicit. Pass the same E-16 bank artifact that the
verdict must reference:

```powershell
kandoo-extract.exe onboard verdict `
  --template-bank C:\onboarding\artifacts\template-bank-v1.json `
  --store-id shop-opaque-id `
  --invoice-id invoice-opaque-id `
  --invoice C:\onboarding\candidate\canonical-invoice-v0.json `
  --observation C:\onboarding\candidate\layout-observation.json `
  --processed-invoice-count 4 `
  --template-bank-locked `
  --d14-agreement-signed `
  --no-require-kit-digit-coverage `
  --extraction-confidence 0.98 `
  --evaluated-at 2026-10-28T12:00:00Z `
  --output C:\onboarding\artifacts\verdict-invoice-opaque-id.json
```

Use `--template-bank-unlocked` instead of `--template-bank-locked` when the
bank is not locked; use `--d14-agreement-required` when the agreement gate is
not signed. The CLI requires one explicit choice for each pair. For an E-03
known-answer kit invoice, use `--require-kit-digit-coverage`; otherwise select
`--no-require-kit-digit-coverage` explicitly. `--missing-field FIELD` can be
repeated for incomplete extractions. `--invoice` may be omitted only when there
is no Canonical candidate; in that case still pass an explicit `--invoice-id`,
and E-06 returns a fail-closed REVIEW result. `--observation` is optional only
when no observation is available.

The output's `template_bank_sha256` is calculated over the exact bytes read from
the bank file (not a reserialized JSON object). The envelope `store_id` must
match the bank and, when supplied, the Canonical Invoice. The explicit
`invoice_id` must match the Canonical Invoice's `invoice_id`.

`--manual-override` accepts the E-06/E-16 owner-audit JSON shape. Its presence
only gives E-06 the supplied audit data: the CLI does not authenticate the
actor, verify a signature, confirm ownership, or persist a durable audit event.
Those checks must be performed by the authorized application before providing
the file. An E-06 ACCEPT remains only an onboarding verdict and does not change
Canonical Invoice lifecycle or authorize issuance.

## Detect/register a new type with E-08

```powershell
kandoo-extract.exe onboard register-type `
  --template-bank C:\onboarding\artifacts\locked-bank-v1.json `
  --store-id shop-opaque-id `
  --invoice-id invoice-opaque-id `
  --invoice C:\onboarding\candidate\canonical-invoice-v0.json `
  --observation C:\onboarding\candidate\layout-observation.json `
  --accepted-invoice-count 4 `
  --template-bank-locked `
  --d14-agreement-signed `
  --extraction-confidence 0.99 `
  --output C:\onboarding\candidates\candidate-v1.json
```

The accepted-invoice count, locked-bank state, D14 state, and extraction
confidence are caller-supplied facts; the CLI does not authenticate them. E-08
still checks the existing E-05/E-06 gates. A new layout can result in a
`PROPOSED` E-16 candidate, but it is not an active template, an accepted
invoice, or approval to issue. The E-05 bank is never modified.

The Python E-08 registry and hash-chained audit trail are in-memory in this
one-shot CLI invocation; E-16's candidate file is a snapshot, not that audit
trail. The caller must durably persist/append E-08 events, apply access controls,
and enforce candidate lifecycle transitions. If E-08 reports no candidate,
inspect the process status and route the invoice to review; no E-16 candidate
file is created. Use a new output path for each exported candidate snapshot.

## C# `Process.Start` example

Use a fully qualified executable path, disable shell execution, and add each
argument separately. This avoids command-shell quoting and injection issues.
The example targets modern .NET (6 or later):

```csharp
using System.Diagnostics;

static async Task<(int ExitCode, string Stdout, string Stderr)> RunKandooAsync(
    string executablePath,
    IEnumerable<string> arguments,
    CancellationToken cancellationToken = default)
{
    var startInfo = new ProcessStartInfo
    {
        FileName = executablePath,
        UseShellExecute = false,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        CreateNoWindow = true,
    };

    foreach (var argument in arguments)
        startInfo.ArgumentList.Add(argument);

    using var process = Process.Start(startInfo)
        ?? throw new InvalidOperationException("Could not start kandoo-extract.exe.");

    // Drain both pipes concurrently so neither can fill and block the child.
    var stdoutTask = process.StandardOutput.ReadToEndAsync();
    var stderrTask = process.StandardError.ReadToEndAsync();
    await process.WaitForExitAsync(cancellationToken);

    return (process.ExitCode, await stdoutTask, await stderrTask);
}

var args = new[]
{
    "onboard", "build",
    "--capture-root", captureRoot,
    "--canonical-dir", canonicalDir,
    "--labels", labelsPath,
    "--store-id", storeId,
    "--currency-unit", "rial",
    "--output", bankArtifactPath,
};

var result = await RunKandooAsync(executablePath, args, cancellationToken);
if (result.ExitCode == 30)
    throw new InvalidOperationException($"Onboarding CLI failed: {result.Stderr}");
if (result.ExitCode is not (0 or 10 or 20))
    throw new InvalidOperationException($"Unexpected onboarding exit code {result.ExitCode}: {result.Stderr}");

// For build, expect 0. For verdict/register-type, handle 10 and 20 as
// explicit review/reject outcomes, then validate the E-16 file at the path
// supplied in the arguments. Never infer success by parsing diagnostic prose.
```

Before launching `verdict` or `register-type`, ensure the bank has the exact
versioned bytes the application expects and that the explicit store/invoice IDs
match the intended records. Treat files as untrusted inputs: validate E-16,
check cross-file hashes and store scoping, and keep the owner/legal/audit gates
in the authorized C# application.
