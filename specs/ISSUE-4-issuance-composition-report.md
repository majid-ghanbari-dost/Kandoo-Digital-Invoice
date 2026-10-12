# Issue #4 — Digital Issuance composition: implementation report and bounded handoff

Date: 2026-10-12. Owner: implementation session (Agent 1 scope: `src/**` + product tests).
Branch: `arena/5fbd6749-kandoo-digital-invoice` (session branch, based on the verified
`main` HEAD). Verified base main: `2d61b4dd61837810134cfcd97df8e7d4c0eba9b0`.
**Tested source commit: `93e1c6e8b3e225f4351cf87214307ec98431d673`** (tree
`6707f9eb165d63bb5b3058198715e9e55f90ec1f`). Status: **IMPLEMENTED + EXECUTED TEST
EVIDENCE** — not PO acceptance and not merged.

## Selected gap and eligibility

The frozen AS-01 external flow is
`External POS/Holoo → Capture → Reconstruction → Extraction → Normalization →
Canonicalization Gate → Validation → Invoice → Digital Invoice`.
After PR #9 (merged at `2d61b4dd…`) both halves are implemented and tested — but
**no production composition connects them**:

- `src/pipeline/` deliberately forbids any digital-invoice surface (its boundary
  test rejects the attribute names `issue` / `open_digital_invoice` and excludes
  `digital_invoice` from its import allowlist);
- `src/digital_invoice/` (WP-10.1) consumes only the P6.2 verified read/trace and is
  reachable exclusively from its own tests and from `src/run_smoke_digital_invoice.py`,
  which hand-wires eleven upstream stores inside a synthetic harness;
- consequently an application could not reach an ISSUED Digital Invoice from raw
  pages through any reusable, durable, restart-safe entry point, and there was no
  cold-start reproducible runner for the composed path (the pipeline layer has none).

Selected gap: **an additive application composition that owns ONE durable directory
through both halves and exposes the explicit-act caller surface** — nothing
automatic, no new vocabulary, no policy value. Eligibility check against the
deferred register: it opens no DEF item (DEF1 Sale, DEF2 access matrix, DEF3 auto
customer, DEF4 retention/purge, DEF5 presentation/delivery, DEF6 Modian), touches no
Frozen decision (D-01…D-09, AD-01…AD-04, AS-01…AS-04), no WP-12.3 threshold, and no
CLI product scope (D-09 stays referred to PO/TM). Duplicate check: it does not
re-implement any WP — it consumes the two existing compositions verbatim.

## What was added (exact paths)

- `src/issuance/__init__.py` — package boundary statement + public surface
  (`DigitalIssuanceWorkspace`, `IssuanceService`, `IssuanceSubmission`,
  `DigitalInvoiceStatus`, `DIGITAL_INVOICE_DB`).
- `src/issuance/model.py` — result shapes only (`IssuanceSubmission`,
  `DigitalInvoiceStatus`); no state, act, transition, origin or identifier.
- `src/issuance/service.py` — verbatim delegation: `submit`, the six explicit
  lifecycle acts, `read`, `trace`, `status`, and the three read-only discovery
  helpers.
- `src/issuance/workspace.py` — `DigitalIssuanceWorkspace`: `ExitStack` ownership of
  the eleven pipeline stores plus `digital-invoice.db`; the WP-10.1 service is
  constructed over the SAME `CanonicalAssemblyService` the pipeline assembles into;
  `close()` idempotent; constructor failure closes already-opened stores.
- `src/issuance/tests/conftest.py`, `src/issuance/tests/test_issuance_flow.py`,
  `src/issuance/tests/test_issuance_boundary.py` — 29 focused tests.
- `src/run_smoke_issuance.py` — 22nd cold-start smoke runner (8 steps, stdlib only).
- `src/issuance/README.md` — caller API, boundaries, delegated declarations
  OD-IX-A…D and the derived checks D-1…D-6.

No pre-existing source, test or contract file is modified by this increment (see
`deliveries/issue-4-issuance/evidence/boundary-check.txt`). The only pre-existing
files touched by this delivery are documentation/registers/handoff (this report,
`src/README.md`, `registers/*`, `PROJECT_CONTINUITY_HANDOFF.md`).

## Behavior (implemented, not just declared)

1. `submit()` performs the pipeline run and returns its outcome **verbatim**
   (`IssuanceSubmission.pipeline`) — REVIEW / REJECT / duplicate stops are never
   converted, retried or auto-resolved; malformed declarations raise `ValueError`
   before any ingest.
2. **Nothing is automatic**: a successful submission creates no Digital Invoice and
   performs no act; the five acts and the read are refused until an explicit
   `open_digital_invoice` call.
3. `open/mark_extracted/mark_validated/issue/revoke/supersede` return the frozen
   WP-10.1 outcome objects unchanged; no new act semantics, precondition or
   idempotency rule exists in this layer.
4. Verified reads and the whole-chain trace are the frozen ones; `status()` is a
   projection of ONE verified read and never softens a withholding (it raises
   `TypeError` on an unknown outcome instead of guessing).
5. Replay and restart are idempotent (zero new business rows); `awaiting_digital_invoice()`
   is durable across restarts and only an explicit act resumes it.
6. Tampered Digital Invoice or Canonical Invoice rows are withheld: read/trace fail
   closed and nothing is served.
7. The composed layer contains no SQL, no CLI, no `hashlib`/`random`/`uuid`, no
   tolerance/precision/threshold literal, and no retention/purge surface
   (AST-swept); physical purge remains blocked and unreachable
   (`PURGE_EXECUTION_ALLOWED is False`, no execute companion).

## Executed tests — real outputs, this session

Environment: Linux `e2b.local` 6.1.158+, Python **3.11.2**, pytest **9.1.1**
(installed in `/home/user/.venv`; production dependencies remain stdlib + repo
packages).

```bash
# repository root — focused suite
PYTHONDONTWRITEBYTECODE=1 /home/user/.venv/bin/python -m pytest src/issuance/tests -q -p no:cacheprovider
# 29 passed in 7.27s   (exit 0)

# src/ — full regression
PYTHONDONTWRITEBYTECODE=1 /home/user/.venv/bin/python -m pytest -q -p no:cacheprovider
# 1683 passed in 183.96s (0:03:03)   (exit 0)
# baseline accounting: 1654 (PR #9 full regression) + 29 new = 1683 — zero new failures

# all smoke runners in fresh temporary paths (21 pre-existing + the new one)
ALL 22 SMOKE RUNNERS PASSED           # every run EXIT_CODE=0
# the new one: run_smoke_issuance.py → "SMOKE OK — 8 steps" (exit 0)
```

Raw outputs: `deliveries/issue-4-issuance/evidence/{environment,focused-tests,full-regression,smoke-tests,boundary-check}.txt`.

Test-to-commit identity: the runs above executed against the tree that is committed
as `93e1c6e8b3e225f4351cf87214307ec98431d673`. The subsequent documentation/evidence
commit adds only `.md`/`evidence` files — `git diff --stat 93e1c6e… <docs commit> -- src`
is empty (recorded in `evidence/boundary-check.txt`).

## Derived acceptance checks (increment-level; no register/PO acceptance claim)

| Check | Status | Evidence |
|---|---|---|
| D-1 raw pages → verified Canonical Invoice → ISSUED Digital Invoice | PASS | `test_product_path_from_raw_pages_to_issued_digital_invoice`, `test_whole_chain_trace_covers_every_frozen_layer`, smoke steps 1/3/5 |
| D-2 nothing automatic; explicit acts only | PASS | `test_submission_alone_never_opens_or_advances_anything`, `test_state_of_a_fresh_digital_invoice_is_the_frozen_draft`, `test_review_stop_never_reaches_the_digital_invoice`, smoke step 2 |
| D-3 replay/restart/resume idempotence | PASS | `test_replay_and_restart_are_idempotent`, `test_resume_after_a_stop_before_the_open_act`, smoke steps 4/6 |
| D-4 fail-closed refusals with zero residue | PASS | `test_refusals_and_foreign_invoices_leave_zero_residue`, `test_malformed_declarations_never_touch_the_workspace`, `test_tampered_durable_rows_are_withheld_never_served[digital_invoice|canonical_invoice]`, smoke steps 2/7/8 |
| D-5 no deferred policy, no frozen edit, no side surface | PASS | `test_no_sql_process_policy_or_deferred_identifier_anywhere`, `test_no_frozen_vocabulary_literal_outside_a_docstring`, `test_production_inventory_is_exactly_the_declared_surface`, `test_imports_stay_inside_the_declared_allowlist`, `test_physical_purge_stays_blocked_and_out_of_the_composed_surface`, `test_unknown_frozen_outcome_is_refused_not_guessed` |
| D-6 ownership, declarations, read-only discovery | PASS | `test_workspace_requires_explicit_declarations_before_creating_files`, `test_workspace_owns_exactly_the_frozen_stores`, `test_constructor_failure_closes_already_opened_stores`, `test_close_is_idempotent_and_closed_workspace_refuses_work`, `test_lifecycle_layer_reads_the_same_assembly_store_it_was_composed_with`, `test_reads_and_listings_never_grow_business_entities` |

## Limitations and bounded continuation handoff

The delivered scope is a local, trusted, reference-format **Python application
composition** — not the store/customer product. It has no network/auth layer,
product CLI, encrypted database, process lock, tenancy, upload bound or scheduler;
verification is point-in-time (no cross-store atomic snapshot); a crash inside a
lower store still requires that layer's existing recovery APIs; replays may append
audit evidence and update verification timestamps (databases are not byte-identical
after replay).

Next owner/action: TM reviews this PR and its archive/manifest hashes; PO retains
merge and acceptance authority. Remaining MVP gaps that require a PO/TM decision
rather than an agent increment: Windows/Android applications, store/customer roles
and onboarding (DEF2), product/inventory registration on the native flow (AS-02 has
no implementation contract — STOP/PO decision needed), customer receipt
presentation and delivery (DEF5), POS/Holoo and Modian adapter mapping (DEF6/WP-11.2),
retention/privacy policy (DEF4), CLI product scope (D-09), threshold ratification
(WP-12.3).

Rollback: remove/revert only this additive package, its tests/smoke runner, the
report/evidence and the delivery metadata; no schema migration to reverse and no
frozen contract to restore. Preserve application-owned workspace data.

No merge, no formal acceptance and no Issue-comment registration is claimed for this
delivery (GOV-PP-01 §1/الف applies when the Issue comment is unavailable).
