# E-36 — window-5 handoff and consolidated report

**Status:** E-34 and E-35 are executive-certified; this document is the E-36 handoff deliverable. The active branch remains `arena/188a5ebf-kandoo-digital-invoice`; `main` was not changed.

## Deliverable map

| Task | Annotated tag | Commit SHA | Deliverable | CI |
|---|---|---|---|---|
| E-34 | `stable-e-34` | `4070979c0e9a770b5c2a77f36558a431398032b4` | Plain-language capture-folder triage CLI, report formatter, tests, and usage/evidence documentation. | Executive certification relayed; run URL not independently opened. |
| E-35 | `stable-e-35` | `ebd890b38ed00b5a46e25320542401756ba9e5cf` | E-27 synthetic failure regressions for corrupt SPL, empty job, duplicate job ID, and two-PNG page-count mismatch; byte-stable report output. | Executive certification relayed; run URL not independently opened. |
| E-36 | `stable-e-36` | This handoff commit | Consolidated project handoff and current evidence/owner-blocker boundary. | awaiting executive verification. |

## Evidence and verification boundary

E-34 tests use the committed repository synthetic capture folder; E-35 adds cases from the E-27 folder generator using existing image fixtures. No capture data was added, and no fixture is represented as authentic Probe, SPL, or SHD evidence. Output omits file sizes and absolute paths and is asserted as exact UTF-8/LF bytes. **no local PNG decode — CI-only evidence.** The sole authorized install attempt, `python -m pip install pytest Pillow 'jsonschema>=4.18,<5'`, failed with `externally-managed-environment`; it was not retried. No E-34/E-35 CI run URL was independently opened for this handoff, so this report makes no independent CI-success claim. E-36 CI is **awaiting executive verification.**

## Still blocked on owner inputs

- Real SPL/SHD samples.
- Holoo price-entry test and Holoo data export.
- Hosting and legal text.
- Faraz credentials.

These remain out of scope pending owner inputs. No legal or tax claims, or tax-authority integration, are made. No credentials are requested or stored in this report.
