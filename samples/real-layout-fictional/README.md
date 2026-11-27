# samples/real-layout-fictional

This directory contains examples that use a real print-layout family with fictional content. The Product Owner certified the captures as fictional-content samples on 2026-11-23; the owner’s 2026-11-27 certification and synthetic-data order are recorded in `TASKS/PY-T3.md` (MANAGER RULING 3). Generated material must remain clearly labeled synthetic/fictional and must never be presented as a real scan.

## Sources and use

- Capture-folder examples came from `majid-ghanbari-dost/agent-github-test`, `DiagnosticResults/` (`Job_2`, `Job_3`, and `Unassigned`; capture dated 2026-11-07).
- The top-level `invoice-34.png` and the PO-provided image under `holdout-invoice-34/invoice_34.png` are distinct rasters. The latter’s provenance, pinned hash, and **holdout-only** restrictions are authoritative in [`holdout-invoice-34/README.md`](holdout-invoice-34/README.md); do not replace or copy it.
- `lane-synthetic-01/` is a separate fixture fabricated by PY-A under the owner’s override. Its README and self-labels explicitly identify it as generated test data; it is not a real scan or operator-confirmed evidence.
- These samples support E-70, E-71, E-73, E-74, and the authorized local checks. The holdout image is not training data.

## Invoice-34 ground-truth correction

Per the corrected PO ruling R-009, invoice 34 has **four** lines and a payable of `49,547,790`. The line sum is `50,051,429`, leaving a `503,639` difference whose cause is not established by the available raster evidence. The earlier five-line / `49,547,706` reading is superseded. Do not infer an invoice-level discount without evidence.

If any sample is found to contain real personal or sales data, stop and report it. Preserve provenance and follow the owner/manager direction; do not silently relabel or substitute files.
