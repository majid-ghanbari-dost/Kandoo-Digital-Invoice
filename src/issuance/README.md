# Digital Issuance application composition — Issue #4 continuation

Additive composition of the two existing production layers into ONE durable,
owned workspace that carries the frozen AS-01 external flow from raw ordered
pages to an ISSUED Digital Invoice:

    pipeline (Issue #4 / PR #9)      capture → … → gate → canonical assembly
    digital_invoice (WP-10.1)        Digital Invoice lifecycle over an issued invoice
    issuance (this package)          the composition + explicit caller surface

It is **not** a CLI, a receipt/presentation surface, a Windows/Android app, a
source adapter or an OCR engine. Nothing here is automatic: submission performs
**no** Digital Invoice action, and every lifecycle movement is one explicit
caller act delegated verbatim to the frozen WP-10.1 service.

## Use from a trusted application

With `src` on the Python import path:

```python
from pathlib import Path
from issuance import DigitalIssuanceWorkspace
from validation import ReferenceValidationRulesV1

# Values are the CALLER's explicit declaration — not defaults of this layer.
rules = ReferenceValidationRulesV1(
    tolerance=declared_tolerance, precision=declared_precision, mode=declared_mode)

with DigitalIssuanceWorkspace(Path(application_owned_directory),
                              validation_rules=rules) as workspace:
    submission = workspace.service.submit(
        ordered_page_bytes,
        source_label=declared_source_label,
        declared_origin=declared_origin,        # HOLOO_CAPTURE or OTHER_POS_CAPTURE
        identity_binding=declared_identity_binding,
        line_binding=declared_line_binding,     # None = no declared lines
        ruleset_id=declared_ruleset_id,
        ruleset_version=declared_ruleset_version)

    if submission.completed:                    # durable Canonical Invoice exists
        invoice_id = submission.invoice_id
        # NOTHING was opened automatically — explicit acts only:
        workspace.service.open_digital_invoice(invoice_id)      # → DRAFT
        workspace.service.mark_extracted(invoice_id, "checked")
        workspace.service.mark_validated(invoice_id)
        workspace.service.issue(invoice_id, "handed to the customer")
        status = workspace.service.status(invoice_id)           # verified read
        trace = workspace.service.trace(invoice_id)             # → Capture S1
    else:
        stopped = submission.pipeline           # verbatim PipelineStopped
```

Restart-resumption uses `service.awaiting_digital_invoice()` — the issued
invoices that have no Digital Invoice yet. It is read-only: an application
resumes with its own explicit acts.

## Semantics

1. `submit` delegates to the pipeline composition verbatim: invalid
   declarations/pages raise `ValueError` before any ingest (zero residue);
   REVIEW / REJECT / already-canonicalized return the pipeline's own typed stop
   and never reach the Digital Invoice layer.
2. The six lifecycle methods (`open_digital_invoice`, `mark_extracted`,
   `mark_validated`, `issue`, `revoke`, `supersede`) are the frozen WP-10.1
   acts executed on this workspace, returning the frozen outcome objects
   verbatim (`DigitalInvoiceOpened` / `…OpenReplay` / `LifecycleAdvanced` /
   `LifecycleReplay` / typed refusals). No act name, state, transition,
   precondition or idempotency rule is added or re-implemented.
3. `read` / `trace` are the frozen verified read and whole-chain trace
   (own-row VOR + event chain + linked P6.2 re-verification; the trace adds one
   head link onto the intact P6.2 chain down to Capture S1).
4. `status` is a compact projection of ONE verified read. `verified=True` means
   every link re-verified inside that call; any withholding yields
   `verified=False` with the outcome's own reason in `detail` and
   `current_state=None` ("no state delivered" — never a new state name). An
   unknown outcome type raises `TypeError` instead of being guessed.
5. Replays are idempotent: re-submitting identical pages/declarations, re-opening
   or re-issuing returns the durable facts with ZERO new business rows.
   Verification may append audit evidence; replays are not byte-identical
   database files.
6. Tampered rows (Digital Invoice row or the linked Canonical Invoice) withhold
   content: the read/trace fail closed and nothing is served.

## Boundaries / limitations

- One synchronous caller per workspace; no transport authentication, encryption,
  process lock, tenancy, bounded upload or scheduler. The directory must be
  application-owned/trusted.
- No presentation/receipt/delivery-channel surface (WP-10.2 / **DEF5**), no
  customer or product semantics (D-06 / DEF3 / WP-8.1 / WP-9.1), no Sale
  (**DEF1**), no inventory effect (AD-03), no source adapter or Modian mapping
  (**DEF6** / WP-11.2), no retention or purge surface (**DEF4** — physical purge
  remains blocked and unreachable from this layer), no access-matrix surface
  (**DEF2**), no threshold value (**WP-12.3**), no CLI product scope (**D-09** —
  still referred to PO/TM).
- Only the synthetic reference-format path is verified here; no claim of real
  Holoo/POS/Windows/Android readiness or of formal product acceptance.

## Delegated implementation details (declared per D-09)

- OD-IX-A module shape: `src/issuance/` = `model.py` (result shapes only) +
  `service.py` (verbatim delegation) + `workspace.py` (ownership) +
  `__init__.py`; smoke runner `run_smoke_issuance.py` (22nd smoke). No new
  lifecycle module, no new vocabulary module.
- OD-IX-B no policy default: `validation_rules` is mandatory and is passed
  through verbatim; the layer contains no tolerance/precision/mode/threshold
  value (AST-proven).
- OD-IX-C one assembly binding: the Digital Invoice service is constructed with
  the SAME `CanonicalAssemblyService` the workspace's pipeline assembles into —
  the provenance guarantee is structural (identity-checked in tests), not a
  promise.
- OD-IX-D discovery only: `issued_canonical_invoices()` / `opened_digital_invoices()`
  / `awaiting_digital_invoice()` are read-only projections of the existing
  listing surfaces; they decide and advance nothing.

## Derived acceptance checks for this increment

Traceability checks — **not** new Frozen contracts and **not** PO acceptance.

| Check | Existing authority | Focused evidence |
|---|---|---|
| D-1: raw pages → verified Canonical Invoice → ISSUED Digital Invoice on the real stores | AS-01; WP-1.1…6.2; WP-10.1 | `test_product_path_from_raw_pages_to_issued_digital_invoice`, `test_whole_chain_trace_covers_every_frozen_layer` |
| D-2: nothing is automatic; explicit acts only | WP-10.1 §5 (no automatic behavior); D-03 | `test_submission_alone_never_opens_or_advances_anything`, `test_state_of_a_fresh_digital_invoice_is_the_frozen_draft`, `test_review_stop_never_reaches_the_digital_invoice` |
| D-3: replay/restart/resume idempotence | D-02/D-03; WP-1.1 VOR; WP-10.1 replay | `test_replay_and_restart_are_idempotent`, `test_resume_after_a_stop_before_the_open_act` |
| D-4: fail-closed refusals with zero residue | WP-6.2 §4/§9; WP-10.1 §5.3 | `test_refusals_and_foreign_invoices_leave_zero_residue`, `test_malformed_declarations_never_touch_the_workspace`, `test_tampered_durable_rows_are_withheld_never_served` |
| D-5: no deferred policy, no frozen edit, no side surface | D-06/D-09, DEF1–DEF6, WP-12.3 | `test_no_sql_process_policy_or_deferred_identifier_anywhere`, `test_no_frozen_vocabulary_literal_outside_a_docstring`, `test_production_inventory_is_exactly_the_declared_surface`, `test_imports_stay_inside_the_declared_allowlist`, `test_physical_purge_stays_blocked_and_out_of_the_composed_surface` |
| D-6: ownership and declarations | existing store-ownership pattern | `test_workspace_requires_explicit_declarations_before_creating_files`, `test_workspace_owns_exactly_the_frozen_stores`, `test_constructor_failure_closes_already_opened_stores`, `test_close_is_idempotent_and_closed_workspace_refuses_work` |

## Run the tests

```bash
# repository root
PYTHONDONTWRITEBYTECODE=1 python -m pytest src/issuance/tests -q -p no:cacheprovider
# cold-start smoke (no pytest needed)
PYTHONDONTWRITEBYTECODE=1 python src/run_smoke_issuance.py /tmp/kandoo-issuance-smoke
```

See `specs/ISSUE-4-issuance-composition-report.md` for the executed evidence,
the tested commit identity and the bounded continuation handoff.
