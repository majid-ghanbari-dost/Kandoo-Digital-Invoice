# Capture-folder triage — v1

## Purpose and language

This read-only tool summarizes the existing capture-folder adapter for one local
folder containing SPL, PNG page(s), and `Report.txt`. Its report language is
**English**, following the repository's CLI and documentation convention. The
report is plain text for an operator; the E-30 JSON result remains the machine
interface.

The frozen E-30 CLI, schema, and golden pack are consumed read-only. The tool
uses the adapter's existing exit-code mapping and adds no exit codes:

| Exit | Meaning |
|---:|---|
| `0` | Accepted / ready |
| `10` | Review |
| `20` | Blocked / rejected |
| `30` | Command-line, input, runtime, or output error |

## Run

From the repository root:

```sh
PYTHONPATH=src python scripts/triage_capture_folder.py --capture-folder PATH
```

The report inventories immediate SPL, PNG, `Report.txt`, and other entries,
then explains capture intake, E-02 extraction, E-05 layout matching, and E-06
routing when those stages ran. It prints no absolute paths and writes UTF-8
with LF line endings so the default report does not depend on the host locale
or path separator.

## Data versus environment

A missing image decoder is reported as an **environment issue**, not a finding
that the PNG is corrupt. For example, the report names the dependency failure
verbatim: `ModuleNotFoundError: No module named 'PIL'`. The adapter's existing
blocked result and E-30 exit code `20` are preserved; no new code is introduced.

Malformed or inconsistent capture contents are described as data problems at
the relevant intake stage—for example an empty SPL, a repeated spool-job ID, a
page-count mismatch, or an SPL digest mismatch. SPL bytes are inventoried but
not interpreted. E-02/E-05 results are not accuracy claims; accuracy remains
`NOT_SCORED` because the capture-folder input does not carry expected-value
labels. The default E-05 bank is repository-fixture-derived and any matching
page is identified as non-independent evidence.

## Evidence boundary

The tests and examples use only the repository's existing synthetic
extraction-bridge capture folder and its synthetic expected result. They do
not create or claim authentic owner capture samples, validate an external
Probe report format, or assess real capture accuracy. The frozen contract
artifacts remain unchanged.
