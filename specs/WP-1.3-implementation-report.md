# WP-1.3 IMPLEMENTATION REPORT — Retention & Recovery (mechanics-only)

```text
Report ID:   WP13-RPT
Version:     1.0
Date:        2026-10-11
Author:      Agent 1 — Implementation Owner
Mission:     «WP-1.3 Retention / Recovery — Formal Decomposition + Mechanics-Only Implementation»
             (Technical Manager, 2026-10-11)
Binding:     SPEC-WP13-RETR v1.0-MVP (specs/WP-1.3-retention-recovery-contract.md)
Delivery:    branch arena/23993033-kandoo-digital-invoice — PR (source delivery), NOT merged
Base:        80d7c73fea9c00a1176736b357325d431f1a7abe (main)
Status claim: IMPLEMENTED + 4/4 AC evidence PASS. NO acceptance claim, NO G3 claim,
              NO merge into main (merge requires an explicit Technical Manager order).
```

## §1 Deliverables produced (13 new files + 5 documentation updates)

| # | Path | Kind | Purpose |
|---|---|---|---|
| 1 | `specs/WP-1.3-retention-recovery-contract.md` | new | SPEC-WP13-RETR — the registered decompose: vocabulary, boundaries, AC↔test obligations, OD-RT-A..J |
| 2 | `src/capture/retention.py` | new | Retention gate: `RetentionPolicy` (mandatory fields, zero defaults) + `evaluate_retention` (pure, clock-free) + `request_purge` (gate-only) |
| 3 | `src/capture/retention_journal.py` | new | Durable append-only decision journal: sha256-v1 fingerprints, hash chain, append-only anchor table, pre-append chain verification, verified reads, decision-level idempotency |
| 4 | `src/capture/consistency.py` | new | Read-only (`mode=ro`) deterministic consistency/orphan report + report fingerprint |
| 5 | `src/capture/tests/test_wp13_retention.py` | new | AC-1.3.1 / AC-1.3.4 gate evidence (35 tests) |
| 6 | `src/capture/tests/test_wp13_journal.py` | new | AC-1.3.2 / AC-1.3.3 journal evidence (24 tests) |
| 7 | `src/capture/tests/test_wp13_purge_gate.py` | new | AC-1.3.3 purge default-deny + storage-stability evidence (11 tests) |
| 8 | `src/capture/tests/test_wp13_consistency.py` | new | AC-1.3.4 report/determinism/read-only evidence (26 tests) |
| 9 | `src/capture/tests/test_wp13_recovery_matrix.py` | new | AC-1.3.2/AC-1.3.3 crash matrix, concurrency, rollback, additive-only proofs (15 tests) |
| 10 | `src/capture/tests/test_wp13_traceability.py` | new | Mechanical AC↔named-test↔register traceability + DEF4-boundary probes (14 tests) |
| 11 | `src/capture/tests/wp13_helpers.py` | new | Shared fixtures: injected instants/policies, relaxed-schema storage-defect fixture |
| 12 | `src/run_smoke_retention_recovery.py` | new | 21st smoke — 8-step cold-start walkthrough of the whole WP-1.3 surface |
| 13 | `specs/WP-1.3-implementation-report.md` | new | this report |
| 14 | `registers/work-package-register.md` | updated | WP-1.3 section → IMPLEMENTED (in-branch) + Phase Index P1 row |
| 15 | `registers/task-register.md` | updated | T-1.3.1..T-1.3.4 registered + DONE with evidence paths |
| 16 | `registers/acceptance-register.md` | updated | AC-1.3.1..AC-1.3.4 rows with evidence + policy-boundary declaration |
| 17 | `registers/risk-register.md` | updated | RSK-5 evidence note → MITIGATED (in-branch, pending TM review) |
| 18 | `src/README.md` | updated | WP-1.3 module table + delegated decisions (project convention) |

Not touched (deliberately): `registers/decision-register.md`, `registers/deferred-decision-register.md`
(PO-owned; DEF4 must stay DEFERRED), `AGENT_HANDOFF.md`, `KANDOO_AGENT_COORDINATION.md`
(PR #1 / Agent 2 territory — editing them here would create a coordination conflict), and
every pre-existing `.py` file.

## §2 Environment and exact commands

```text
Sandbox      Linux, repo root /home/user/Kandoo-Digital-Invoice
Python       3.11.2 (system)          ← note: src/README.md declares “Python 3.12+”
pytest       9.1.1 (installed into /home/user/.venv-kandoo, OUTSIDE the repository)
Dependencies none added — the project stays stdlib-only (sqlite3 from stdlib)
Base HEAD    80d7c73 (main) — verified equal to the mission's stated baseline
```

| # | Command (from repo root unless noted) | Result |
|---|---|---|
| 1 | `git rev-parse HEAD` on the work branch | `80d7c73…` base, branch `arena/23993033-kandoo-digital-invoice` |
| 2 | `cd src && python -m pytest capture/tests/test_wp13_retention.py … test_wp13_traceability.py -q` (×3) | **125 passed** / 0 failed — 2.44s, 2.46s, 2.58s |
| 3 | `cd src && python -m pytest capture/tests/ -q` (whole capture package: frozen + new) | **215 passed** = 90 pre-existing capture-layer tests + 125 WP-1.3 tests |
| 4 | `python src/run_smoke_retention_recovery.py /tmp/kandoo-smoke-wp13-1` (and `-2`, fresh dirs) | **SMOKE OK**, exit 0, 8/8 steps, twice |
| 5 | `cd src && python -m pytest -q` (FULL regression, all 17 domains) | **1601 passed, 0 failed, 0 error, 0 skipped** in 203.37s |
| 6 | `git diff --name-only -- 'src/**/*.py'` | empty → zero source/test modifications vs baseline |
| 7 | `python -m compileall src` | exit 0 (all sources compile on Python 3.11) |

### §2.1 Additive arithmetic check (independent, not copied)

```text
baseline regression at 80d7c73 (re-run by this agent before any edit): 1476 passed / 0 failed
WP-1.3 dedicated additions:                                             +125
observed full regression on the branch:                                 1601 passed / 0 failed
1476 + 125 = 1601 ✓  — zero pre-existing test changed state, zero new failure.
```

### §2.2 Tests NOT run / limits of this environment (explicit)

- **Not run:** no CI pipeline exists in this repository (no workflow files), so there is no
  CI evidence — evidence here is local command output only.
- **Not run:** no execution under Python 3.12/3.13 (only 3.11.2 is installed). The suite
  compiles and passes on 3.11; the declared "3.12+" floor in `src/README.md` remains an
  unverified documentation claim (recorded as a limitation, not fixed here).
- **Not run:** no real OS `kill -9` crash harness. Crash windows are simulated by building
  the exact durable residue each window leaves (the frozen WP-1.1 technique) plus injected
  failures at the three persistence boundaries of the append.
- **Not run:** no real Holoo/POS/external system, no network storage, no multi-host test.
- **Known flake — did not occur in this run, mechanism now identified:**
  `identity_resolution/tests/test_ir_provenance.py::test_no_raw_pipeline_values_are_stored`
  (frozen WP-7.1) is not a race: it forbids the fixture's literal date `2026-10-08` in the
  DB dump while `created_at` comes from `datetime.now(UTC)`, so it fails deterministically on
  any run whose UTC date equals the fixture date (proved by forcing the clock → FAILED;
  real clock → PASSED). This WP left the frozen file untouched per Flake Policy; the register
  records the corrected characterization.

## §3 AC → test evidence matrix (every registered AC ↔ observable behavior ↔ named tests)

### AC-1.3.1 — injected policy only, default-deny, fail-closed (35 tests: `test_wp13_retention.py`)

| Registered obligation | Proven by |
|---|---|
| no policy-bearing default exists | `test_policy_has_no_usable_defaults`, `test_constructing_an_empty_policy_is_refused`, `test_each_missing_field_alone_is_refused` (×5 params), `test_unspecified_sentinel_is_not_a_value`, `test_zero_cutoff_is_a_legitimate_injected_value_not_a_refusal` |
| type exactness, no coercion | `test_policy_field_types_are_enforced_not_coerced` (bool≠int duration, str≠int, negative, empty label, unknown basis, non-bool switch) |
| absence → typed refusal | `test_evaluate_with_no_policy_object_is_a_typed_refusal`, `test_evaluation_time_is_mandatory`, `test_module_reads_no_clock` |
| unusable data → `DATA_ANOMALY`, never a guess | `test_unusable_timestamps_are_data_anomalies` (×10 params, both operand positions), `test_negative_age_is_anomaly_never_a_verdict`, `test_non_record_input_is_refused_not_crashed` |
| non-terminal / conflicting target → refusal or review | `test_active_record_is_state_refused_not_assessed`, `test_settled_failed_record_is_state_refused`, `test_completed_but_integrity_failed_is_deferred_to_review` |
| boundary + determinism | `test_boundary_age_exactly_at_cutoff_is_eligible`, `test_age_one_second_below_cutoff_is_not_eligible`, `test_same_inputs_yield_identical_decisions`, `test_candidate_reporting_disabled_suppresses_the_candidate` |
| DEF4 label + no execution surface | `test_every_decision_carries_the_def4_pending_label`, `test_gate_module_contains_no_mutation_or_execution_surface`, `test_purge_gate_is_closed_by_construction` |

### AC-1.3.2 — recovery + tamper evidence (39 tests across `test_wp13_journal.py` / `test_wp13_recovery_matrix.py`)

| Registered obligation | Proven by |
|---|---|
| crash residues W1..W4 settle through the frozen path | `test_w1_record_only_residue_is_refused_by_retention_then_settled`, `test_all_crash_windows_end_terminal_with_the_retention_layer_attached` |
| recovery is idempotent, journal untouched | `test_recovery_is_idempotent_across_restarts_with_journal` |
| recovery never repairs, only reports | `test_orphan_content_after_a_crash_is_reported_never_deleted`, `test_active_leftover_is_reported_and_never_settled`, `test_purge_requests_during_recovery_are_inert` |
| truncation / rewrite / anchor deletion detected | `test_truncated_tail_is_detected`, `test_middle_rewrite_is_withheld_on_read`, `test_deleted_anchor_alone_is_detected`, `test_broken_journal_is_reported_as_inconsistent` |
| append on a broken chain is refused, extends nothing | `test_append_is_refused_on_a_broken_chain_and_extends_nothing` |
| verified read withholds; recovery status computed | `test_empty_log_is_the_only_valid_anchor_free_state`, `test_recovery_status_reports_residue_computed_not_assumed`, `test_history_survives_a_restart` |
| frozen journal implementation untouched | `test_frozen_layer_files_are_untouched_in_the_working_tree`, `test_wp13_modules_import_only_stdlib_and_capture_siblings`, `git diff` on `src/**/*.py` = empty |

### AC-1.3.3 — purge gate-only + idempotency + rollback (35 tests: `test_wp13_purge_gate.py` / journal)

| Registered obligation | Proven by |
|---|---|
| default-deny purge under every input shape | `test_purge_is_blocked_with_no_policy_at_all`, `test_purge_is_blocked_even_for_a_full_eligible_candidate`, `test_purge_is_blocked_under_every_policy_shape_the_caller_can_invent`, `test_gate_is_not_runtime_configurable` |
| forged credential refused, with the reason | `test_fabricated_authorization_is_refused_not_trusted` |
| **no physical deletion; storage provably stable** | `test_purge_request_leaves_the_capture_database_bytes_untouched`, `test_purge_request_leaves_record_counts_and_states_untouched`, `test_content_is_still_verifiable_after_purge_requests`, `test_repeated_purge_requests_are_inert_and_identical`, `test_gate_never_produces_a_downstream_datum` |
| audit trail without side effects | `test_blocked_purges_are_auditable_without_side_effects`, `test_purge_refusal_is_recordable_as_audit_only` |
| duplicate handling idempotent (journal + capture) | `test_duplicate_decision_is_idempotent`, `test_duplicate_refusal_survives_reopen_as_a_storage_backstop`, `test_seq_never_skips_after_refusals`, `test_duplicate_handling_after_recovery_is_deduped_and_journalled_once` |
| rollback at every persistence boundary, zero residue | `test_injected_failure_after_row_insert_leaves_zero_residue`, `test_injected_failure_after_anchor_write_leaves_zero_residue`, `test_injected_commit_failure_leaves_zero_residue`, `test_unknown_exception_leaves_no_open_transaction`, `test_append_after_a_rolled_back_failure_is_clean`, `test_partially_built_transaction_is_rolled_back_atomically` |
| concurrency keeps the chain exact | `test_concurrent_appends_keep_the_chain_exact`, `test_concurrent_identical_appends_are_exactly_one_row`, `test_recovery_concurrent_with_ingest_preserves_every_invariant` |

### AC-1.3.4 — deterministic read-only report + boundaries + traceability (40 tests)

| Registered obligation | Proven by |
|---|---|
| orphan/inconsistent detection matrix | `test_orphan_unreferenced_content_is_reported`, `test_record_bound_to_missing_content_is_reported`, `test_completion_gate_breach_is_detected`, `test_settlement_pin_breach_is_detected`, `test_unverified_completed_is_detected`, `test_unparseable_timestamps_are_detected` (×3 params), `test_foreign_fingerprint_algorithm_is_surfaced_not_resolved`, `test_duplicate_completed_key_is_detected`, `test_findings_are_ordered_by_code_then_subject`, `test_orphan_journal_decision_is_reported` |
| determinism with injected instant | `test_two_independent_reports_are_byte_identical`, `test_a_fresh_process_view_of_the_same_state_reports_identically`, `test_injected_time_changes_the_answer_deterministically` |
| honest absence, never a false zero | `test_missing_policy_is_not_reported_as_zero_candidates`, `test_journal_not_supplied_is_declared_not_guessed`, `test_healthy_store_produces_no_findings`, `test_empty_database_is_reported_as_such_not_as_an_error` |
| read-only guarantee | `test_report_never_mutates_the_capture_or_journal_storage`, `test_wp13_never_opens_the_capture_store_writable_from_the_report`, `test_report_carries_no_paths_no_clock_and_no_content`, `test_report_reads_are_not_a_content_channel` |
| explicit failure surface | `test_unreachable_storage_fails_explicitly`, `test_foreign_schema_fails_explicitly` |
| DEF4 labels everywhere + no invented values | `test_def4_pending_label_reaches_every_produced_artifact`, `test_wp13_modules_declare_no_numeric_policy_constant`, `test_policy_undeclared_is_visible_in_the_report_without_a_policy` |
| frozen surface / no rewiring | `test_frozen_capture_modules_do_not_import_wp13`, `test_no_wp13_symbol_is_exported_from_the_frozen_package_entrypoint`, `test_state_and_integrity_vocabulary_stay_the_frozen_ones` |
| mechanical AC↔test traceability | `test_ac_is_registered_in_the_acceptance_register` (×4), `test_ac_is_bound_to_named_tests_that_exist` (×4), `test_every_ac_is_covered_and_no_citation_is_dangling`, `test_smoke_runner_exists_and_is_cold_start`, `test_register_updates_record_this_wp_only_where_it_should`, `test_purge_language_never_becomes_an_execution_surface` |

## §4 Delegated implementation decisions (declared per D-09 — no architecture change)

See SPEC-WP13-RETR §10 for the normative list (OD-RT-A..J). Selection rationale, briefly:

1. **Refusal over default** (OD-RT-B): the only way to satisfy "no DEF4 value may be
   invented" *and* keep the mechanics executable is to make an incomplete policy
   unconstructible. A `None` default would have been a silent policy ("no retention").
2. **Gate closed by constant, not by configuration** (OD-RT-C): a configurable flag would
   itself be a policy mechanism. `PURGE_EXECUTION_ALLOWED = False` with no setter, and a
   purge request that refuses unverifiable credentials, keeps the decision with the PO.
3. **Append-only anchor table** (OD-RT-D): the frozen reconstruction log uses a
   `ON CONFLICT DO UPDATE` head anchor. Copying that idiom would have put the only `UPDATE`
   in the WP-1.3 source. One anchor row per decision removes it, costs nothing, and makes
   anchor deletion detectable.
4. **`mode=ro` URIs for the report** (OD-RT-F): non-mutation is then a storage property
   (and the test asserts byte-identical DB files, not just "no exception").
5. **Zero-residue by construction, no sweep** (journal): a startup sweep would require a
   pending state to exist; a single-transaction commit means none can. `recovery_status()`
   therefore *verifies* rather than claims.
6. **`capture/__init__.py` untouched** (OD-RT-I): re-exporting WP-1.3 there would modify a
   frozen file for convenience; submodule imports are sufficient and keep the frozen
   surface byte-identical.
7. **Test-side fault injection by monkeypatch** (OD-RT-J): matches the frozen suites and
   avoids shipping a fault-injection flag in production code.

## §5 Observations and risks surfaced (no action taken — TM/PO ownership)

1. **Ingest under recovery concurrency surfaces a typed error** (not a defect claim, an
   observation): if the frozen recovery settles an in-flight `ACTIVE` record, that ingest's
   next store write raises `IllegalTransition` out of `CaptureService.ingest`. INV-C6
   semantics are satisfied and nothing is corrupted (asserted by the invariant-based
   concurrency test), but the ingest path has no typed "lost to recovery" outcome.
   Fixing it means touching a frozen file → **decision required, not implemented here.**
2. **The "known flake" is a date-collision false positive** (see §2.2) — it will recur on
   every October 8th run. Cheap test-side fix exists; blocked by Flake Policy without
   authorization.
3. **Register path convention:** legacy AC/Task rows cite `kandoo/specs/…` paths that do not
   resolve from the repository root. New WP-1.3 rows deliberately use repo-root-relative
   paths; normalizing the legacy ones is a separate governance item (not silently done here).
4. **`src/README.md` declares Python 3.12+** but everything compiles and passes on 3.11.2;
   the floor statement is unverified either way.
5. **WP-1.3 mechanics are not wired into any pipeline entry point** by design (additive-only):
   no frozen layer calls the gate. Activation is a follow-on decision once DEF4 values exist.

## §6 Policy boundary declaration (DEF4)

```text
DEF4 status at delivery:            DEFERRED — unchanged in registers/deferred-decision-register.md
Retention duration / TTL:           NOT SET — no value exists in any WP-1.3 module
Privacy marking / sharing rule:     NOT SET — the field must be injected by the caller
Physical purge / deletion:          NOT IMPLEMENTED — refused with PURGE_GATE_BLOCKED
Journal-side retention of evidence: append-only; no removal path exists
Any change to the above:            PO decision via STOP Protocol, never a WP default
```

## §7 What this delivery does NOT claim

- **No** integration into `main` (the branch/PR is the delivery; merge requires an explicit
  Technical Manager order).
- **No** Acceptance: all four ACs are recorded `PASS` against the evidence in REG-AR with the
  acceptance column left `Pending — TM review`; no PO sign-off is implied.
- **No** G3/phase-gate closure for P1.
- **No** relation to, and no merge of, PR #1 (governance-only). Its title/body claims about
  received artifacts and a "1566 tests" verification were **not** reproduced or relied on
  here: the only numbers in this report are the ones in §2, produced in this sandbox.
- **No** fabricated test counts: every figure above is copied from a command actually run
  in this session (see the commands column).
