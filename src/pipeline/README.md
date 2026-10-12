# Reference capture-to-canonical Python API — Issue #4

This additive application service replaces the unavailable MVP package under
explicit PO authorization on 2026-10-12. It is **not** recovered original code,
a product CLI, an OCR engine, a Windows app, or a Digital Invoice delivery UI.
No pre-existing service, contract, decision or register is modified.

## Use from a trusted application

With `src` on the Python import path:

```python
from pathlib import Path
from pipeline import PipelineWorkspace, PipelineCompleted, PipelineStopped
from validation import ReferenceValidationRulesV1

# Values must come from the caller's explicit declaration, NOT from this API.
# Supplying them does not constitute PO/G4 calibration ratification.
rules = ReferenceValidationRulesV1(
    tolerance=declared_tolerance, precision=declared_precision, mode=declared_mode)
with PipelineWorkspace(Path(application_owned_directory), validation_rules=rules) as ws:
    result = ws.pipeline.process(
        ordered_page_bytes,
        source_label=declared_source_label,
        declared_origin=declared_origin,      # HOLOO_CAPTURE or OTHER_POS_CAPTURE
        identity_binding=declared_identity_binding,
        line_binding=declared_line_binding,   # None = no declared lines
        ruleset_id=declared_ruleset_id,
        ruleset_version=declared_ruleset_version,
    )
    if isinstance(result, PipelineCompleted):
        canonical_invoice = result.invoice  # AssemblyReadSuccess, includes fields/lines
        verified_chain = result.trace       # AssemblyTraceSuccess
    elif isinstance(result, PipelineStopped):
        # Preserve exact upstream reason/type; do NOT auto-resolve or issue.
        stopped_stage, upstream_outcome = result.stage, result.outcome
```

The reference engine accepts UTF-8 `key=value` page grammar only. Source-field
bindings are explicitly declared through the existing gate/assembly validators;
there is no source mapping discovery. The registered normalization ruleset is
`kandoo-norm-v1`; the attempted derivation is the existing
`kandoo-der-total-gross-from-net-tax/1`. Every caller-supplied validation rule is
executed, then the exact declared set is passed to the domain projector.

## Execution / retry semantics

1. Validate declarations and bytes-page shape before ingest; no raw-value guesses.
2. Aggregate ordered pages via `CaptureService.aggregate`; ingest via S1.
3. **Explicit capture verified read on every run, including capture replay.**
   Reconstruction's existing-document replay does not itself re-read raw capture.
4. Reconstruction → extraction → evidence binding → normalization → derivation →
   validation → domain projection → gate, using public frozen service calls only.
5. `DerivationDeferred` remains an explicit observation; validation/domain/gate
   handle missing/uncertain values. Infrastructure/integrity/refusal outcomes stop.
6. Gate decisions are re-read through VOR even on replay. Only an existing
   **ACCEPTED** admission reaches assembly. REVIEW / REJECTED /
   ALREADY_CANONICALIZED stop; no duplicate invoice or automatic resolution.
7. Return success only after assembly, verified invoice read and whole-chain trace.
   `PipelineCompleted` is an execution result, **not a new domain/lifecycle state**.

All stage outcomes are retained in `steps` (including rejected-line details from
assembly). These may contain source data: this is a trusted in-process API, not a
customer-facing serialization/logging interface. Do not blindly expose them.

Re-submit identical pages and declarations to replay or resume a successful
durable prefix. Frozen identity/version/declaration semantics remain authoritative:
no new global idempotency key, no silent rewrite, no multi-store atomic transaction.
Read verification may update verification metadata and append audit evidence;
replay does **not** mean byte-identical DB files. Stage/business entity counts
remain stable for identical successful replay. Gate replay never re-decides prior
origin/identity declarations; changing an input is not an amendment API. Assembly
line-declaration drift is explicitly refused by the existing service.

Unexpected exceptions raise `PipelineExecutionError` with `stage`, `capture_id`,
completed `steps` and the original `__cause__`. Durable prior stages are preserved,
not deleted/rolled back. Opening the workspace is non-destructive; partial
constructor failure closes already-owned handles. `close()` is idempotent.

## Boundaries / limitations

- One synchronous caller per workspace instance; no process lock, tenant isolation,
  transport authentication, encrypted database, bounded upload size or scheduler.
  Paths and inputs must be application-owned/trusted. Verification is point-in-time,
  not an atomic snapshot across all stores.
- No automatic recovery of incomplete low-level writes; existing capture and
  reconstruction recovery services remain the authorized mechanisms. Tested resume
  covers interruptions between successfully committed stages, not power loss.
- No Digital Invoice open/issue action, customer/product creation, Sale, inventory,
  KPI, accounting/tax posting, Holoo DB access, OCR/VLM choice or OS spooler hook.
- DEF4/5/6, WP-12.3, D-09/CLI scope remain unresolved/unchanged. No physical purge.
- Only synthetic reference-format end-to-end behavior is verified here; no claim
  of real Holoo/Windows/Android readiness or formal product acceptance.

## Derived acceptance checks for this increment

These are traceability checks, **not new Frozen contracts or PO acceptance entries**.

| Check | Existing authority | Focused evidence |
|---|---|---|
| P-1: real ordered capture → verified canonical fields/lines/provenance | WP-1.1..6.2, AS-01; existing canonical assembly smoke composition | cold-start; multipage tests |
| P-2: replay/restart/resume without a second invoice | D-02/D-03; WP-2.1/3.1/4.1/5.2/6.1/6.2 replay contracts | entity-count, restart, interruption and final-verification-retry tests |
| P-3: gate outcomes preserved; no assembly for REVIEW/REJECT/duplicate | WP-5.2; WP-6.1 §4; WP-6.2 §1/§4 | review/missing input, rejection, S2 duplicate and capture re-projection tests |
| P-4: verification/refusal/unavailability never becomes success | WP-1.1 VOR; WP-3.2; WP-6.2 §4/§9 | capture/gate/invoice tamper; all-stage stop matrix |
| P-5: no deferred policy or unauthorized side effect | D-06/D-08/D-09, DEF4/5/6, WP-12.3 | explicit-rule validation, import/AST, DB-set, no-CLI tests; baseline diff |
| P-6: owned resources and zero ingest on malformed declarations | existing store ownership and gate/assembly validators | constructor failure, repeated close, preflight tests |

Run focused tests from repository root: `python -m pytest src/pipeline/tests -q`.
See `specs/ISSUE-4-pipeline-implementation-report.md` for executed evidence,
publication limitations and the bounded continuation handoff.
