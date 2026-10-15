# KANDOO DIGITAL INVOICE — AGENT COORDINATION

## Purpose

Operational coordination between implementation and governance agents. This file and `AGENT_HANDOFF.md` must reflect the verified repository state, not historical transfer-package status.

## Ownership

| Area | Owner | Status |
|---|---|---|
| `WP-HOLOO-IMAGE-EXTRACTION-02` | Current implementation agent | SYNTHETIC PERSIAN SUPPORT COMPLETE; real-source validation blocked pending an authorized Holoo sample |
| Native Checkout Q1–Q4 decisions | Product Owner | RECORDED; future architecture only, not current MVP priority |
| WP-11.2 Holoo database adapter | None until its decisions/evidence are resolved | DEFERRED; separate from image OCR |
| Governance/handoff | Technical Manager / governance agent | EOD sync recorded in `AGENT_HANDOFF.md` |

## Rules

1. One WP = one owner.
2. Do not edit another agent's active WP/files concurrently.
3. Reviews do not transfer ownership.
4. This Arena session is fixed to `arena/9dc17500-kandoo-digital-invoice`; do not switch/create another branch.
5. Frozen files require explicit evidence/authorization before modification.
6. Update this file and `AGENT_HANDOFF.md` when ownership or project state changes.
7. Stop at genuine decision, evidence, contract, or architecture blockers.
8. Never claim source integration or Holoo accuracy without verifiable artifacts and real-source evidence.
9. No merge to `main` is authorized by this EOD update.

## Current State — 2026-10-15

### Native Checkout

PO choices are recorded in `specs/native-checkout-contract-proposal.md`:

- Q1: Option 1 — additive native-source contract, no fake capture.
- Q2: Option 2 — non-fiscal pilot with operator-entered amounts, no tax claim.
- Q3: Option 1 — no post-commit correction in this slice.
- Q4: Option 1 — stable `sale_id` for idempotency.

This is approved for future architecture, not current MVP priority. No Native Checkout code was added.

### External image OCR

- `src/image_extraction_adapter/` uses Tesseract and a coordinate-free, fail-closed labeled-text parser. `PERSIAN_TESSERACT_LANGUAGE` is `fas+eng`; Persian/Arabic digits, decimal/group separators, Arabic/Persian letter forms, and bidirectional controls are normalized.
- The clearly labeled synthetic Persian raster passed actual Tesseract → expected-value preflight → existing `IssuanceService` → Digital Invoice smoke. OCR: Tesseract 5.5.1 (`fas+eng`), 47 word scores, minimum 65.0, mean 91.04255319148936. All 13 declared values matched. The pipeline reached `ISSUED`, verified `true`, with a 24-link trace.
- Evidence: `deliveries/image-extraction-ocr/synthetic-persian-ocr-e2e.log`, `synthetic-persian-confidence-review.log`, `synthetic-english-regression.log`, and `synthetic-digital-invoice-evidence.md`. The earlier English synthetic evidence remains in `synthetic-ocr-success.log` and `synthetic-confidence-review.log`.
- At threshold 70, the Persian fixture was held as adapter-local `REVIEW_REQUIRED`; issuance was not called. This is not a persisted Frozen P5.2 ReviewQueue item or a Digital Invoice `REVIEW` state.
- Persian `fas` and English `eng` traineddata were installed and exercised from `/tmp`; provenance/checksums are recorded in the evidence. No traineddata binaries or optional runtime packages were added to the repository.
- No genuine, sanitized/authorized Holoo invoice was available. Synthetic recognition does not establish Holoo accuracy; Holoo-specific validation remains blocked until such a sample is supplied.
- Frozen contracts D-01–D-09 were not changed. The original raster hash is logged by the adapter but is not persisted by the Frozen Capture contract.

### Next executable work

Synthetic Persian support and regression testing for `WP-HOLOO-IMAGE-EXTRACTION-02` are complete. The next real-source step, when an authorized sanitized Holoo invoice is supplied, is to run OCR/parser against it, preserve raw OCR and field-by-field mismatches, and keep low/uncertain recognition fail-closed. Do not claim Holoo accuracy before that evidence exists. Keep Native Checkout outside current MVP implementation priority. WP-11.2 remains a separate deferred Holoo database-adapter scope. Persian calendar (Jalali) conversion is not implemented.

## Branch / integration boundary

All EOD changes must stay on `arena/9dc17500-kandoo-digital-invoice` and be pushed only to that branch. Do not force-push or overwrite remote work if a non-fast-forward condition is encountered; report the blocker. No merge to `main` is part of this task.
