# SPEC-WP13-RETR — WP-1.3 Retention & Recovery (Completion) — Mechanics-Only Contract

```text
Spec ID:     SPEC-WP13-RETR
Version:     1.0-MVP
Date:        2026-10-11
Amended:     2026-10-11 (PR #2 re-review B1/M1): §3/§5 — foreign `s1_algorithm_id`
             is explicitly `INTEGRITY_DEFERRED` (never a candidate); §10 OD-RT-F —
             read-only URI paths are percent-encoded (holoo_spike idiom); §9 — new
             named test bound to AC-1.3.1.
Status:      ACTIVE — binding for the WP-1.3 mechanics implementation
             (the registered decompose step: WP-1.3 "DEFINED — decompose after
             WP-1.1; policy values BLOCKED per DEF4")
Authority:   REG-WPR WP-1.3 «Retention & Recovery (Completion)» (Goal/Scope/
             Out of Scope/DoD as registered — this spec does not redefine them)
             + Mission dispatch «WP-1.3 Retention / Recovery — Formal Decomposition
               + Mechanics-Only Implementation» (Technical Manager, 2026-10-11)
             + Decision Register D-02 (S1, FROZEN), D-03 (idempotency, FROZEN),
               D-09 (freeze governance) | Deferred Register DEF4 (BLOCKED AREA)
             + FROZEN WP-1.1 designs (binding, verbatim): Contract v1.1 |
               Store Design v0.2 | S1 Design v1.0 | VOR Design v1.0
Upstream:    WP-1.1 (CLOSED + G3 PASS 2026-10-01) and WP-1.2 (IMPLEMENTED
             2026-10-09) deliverables inside src/capture — consumed verbatim
Downstream:  none — no WP-1.3 output is consumed by P2..P12 and none may be
             (additive-only); WP-10.2 / DEF4 / DEF5 remain the owners of any
             retention policy, presentation or delivery behaviour
```

## §1 Purpose

WP-1.3 completes the P1 capture foundation on the axis the frozen WP-1.1/WP-1.2
work deliberately left open: **what the layer can say about retention and recovery
without owning a retention policy**. It adds (a) a retention evaluation gate whose
policy arrives entirely from the caller, (b) a durable, tamper-evident journal of
retention decisions and purge refusals, (c) a deterministic consistency/orphan report,
and (d) the recovery-hardening evidence for the crash windows and the
recovery/live-ingest interaction.

The registered WP Register limits this WP to *mechanics*, and `DEF4` blocks its
*policy values*. This spec holds that line literally: **no number, label, or default
in this WP expresses a retention duration, a privacy class, a sharing rule or a
purge authorization.** Where a required value is absent, the layer refuses explicitly.

Physical deletion is **not implemented**. The purge path is gate-only: it reports
eligible candidates and refuses requests; it never executes removal, and no code path
in this WP deletes a row, a file, or an artifact.

## §2 Normative boundaries (absolute)

1. **DEF4 is a values boundary, not a mechanics permission.** Absent policy → typed
   refusal. A "reasonable default" is a policy value and is FORBIDDEN here.
2. **No new lifecycle state and no new integrity status.** `ACTIVE | COMPLETED |
   FAILED_INCOMPLETE` and `UNVERIFIED | VALID | FAILED` are frozen (Contract §5/§7/§10);
   retention verdicts live in a separate, capture-side vocabulary (§3).
3. **No new identity or dedup definition (D-03).** Journal-entry idempotency (§7) is
   idempotency of *decision records*; it is never a document-level duplicate decision
   and is never consulted for identity. `S1` stays the only capture-level idempotency key.
4. **No physical delete, anywhere.** No `DELETE`/`UPDATE`-as-erasure/`VACUUM`/file
   removal in any WP-1.3 module; proven structurally (§9) and by byte-comparison (§9).
5. **No content interpretation.** The gate reads durable fields (ids, state, integrity,
   timestamps) — never artifact bytes. Report details never quote content (INV-C7/C8).
6. **No downstream semantics.** No Sale / Inventory / Customer / Canonical Invoice /
   Digital Invoice object or label appears in any WP-1.3 output (AD-02/AD-03/DEF1/DEF3).
7. **Additive-only.** No file created by WP-1.1/WP-1.2 or by P2–P12 is modified, and no
   frozen module imports WP-1.3. `src/capture/__init__.py` is NOT extended: WP-1.3 is
   reached by explicit submodule import only (`capture.retention`,
   `capture.retention_journal`, `capture.consistency`), so the frozen surface is unchanged.
8. **REVIEW beats guessing.** A COMPLETED record whose integrity is FAILED, a foreign
   `s1_algorithm_id`, an unparseable timestamp, or a broken journal chain is *surfaced*,
   never repaired, never assumed eligible/ineligible.

## §3 Vocabulary (fixed — no synonyms, no additions outside this table)

| Token | Meaning | Produced by |
|---|---|---|
| `POLICY_UNDECLARED` | no injected policy object; nothing evaluated | gate |
| `ELIGIBLE_CANDIDATE` | age ≥ injected cutoff, reporting permitted — **a report, not an action** | gate |
| `NOT_ELIGIBLE` | age < injected cutoff (also: candidate reporting disabled by policy) | gate |
| `STATE_REFUSED` | target is not COMPLETED (recovery owns unresolved state) | gate |
| `INTEGRITY_DEFERRED` | COMPLETED but integrity FAILED, or a foreign `s1_algorithm_id` (NO-VERDICT class) → review, not candidacy | gate |
| `DATA_ANOMALY` | timestamp/operand unusable (naive, malformed, negative age, no injected instant) | gate, report |
| `PURGE_GATE_BLOCKED` | the only possible answer to a purge request | gate |
| `DEF4-PENDING` | carried by every decision, journal entry and report | all |

`RETENTION_BASES = {created_at, received_at}` — the two frozen timestamps the caller may
name. Naming a basis is *selection*, not a policy value; which basis a ratified policy
picks is a DEF4 decision the caller supplies.

## §4 RetentionPolicy — injection surface (no values)

`RetentionPolicy` is a frozen dataclass whose five fields are **all mandatory**
(`policy_id`, `basis`, `cutoff_seconds`, `privacy_marking`, `candidate_reporting`);
none has a usable default. Construction with any field missing/blank/sentinel raises
`RetentionPolicyIncomplete` naming the missing fields. Type exactness is enforced
without coercion: a `bool` is not an integer duration, a string is not silently parsed,
a negative window is refused, a non-bool reporting switch is refused.

Consequence: the "policy undeclared" state is **unrepresentable as a policy object** —
it can only be expressed by not calling, which the gate answers with
`POLICY_UNDECLARED`.

## §5 Evaluation (pure, clock-free)

`evaluate_retention(record, *, policy, evaluation_time)` is a pure function. Refusal
order is fixed: policy absent → `POLICY_UNDECLARED`; no injected instant →
`DATA_ANOMALY` (the module owns no clock and never substitutes one); non-COMPLETED →
`STATE_REFUSED`; integrity FAILED → `INTEGRITY_DEFERRED`; **`s1_algorithm_id` foreign
to the frozen binding → `INTEGRITY_DEFERRED`** (the NO-VERDICT class of §2.8 — no
candidate, no age verdict, review only); unusable timestamp or negative
age → `DATA_ANOMALY`; else `ELIGIBLE_CANDIDATE` iff `age_seconds >= cutoff_seconds`
(boundary inclusive), else `NOT_ELIGIBLE` with `remaining_seconds`.

Timestamp mechanics (OD-RT-A): ISO-8601 with an explicit offset only. A naive instant is
refused rather than assumed UTC.

## §6 Purge — gate-only interpretation

`request_purge(capture_id, *, policy=None, authorization=None)` returns
`PURGE_GATE_BLOCKED` with `executed=False`, `rows_affected=0`, reason naming DEF4 —
under **every** input combination. There is no companion execute function; the module
imports no database and opens no file (asserted by AST). A supplied `authorization`
object is refused *and says why*: with no PO-ratified issuer there is nothing to verify
it against, so a credential cannot be honoured. `PURGE_EXECUTION_ALLOWED = False` is a
construction constant, not a policy value: opening the gate is a DEF4 PO decision, never
a WP change, and no setter exists.

## §7 Retention decision journal (durable, append-only, chain-evident)

One SQLite file (`retention_decisions` + `retention_journal_anchor`), `synchronous=FULL`,
explicit `BEGIN IMMEDIATE`, single clock reused from the frozen capture layer.

* `record_fingerprint = sha256-v1(canonical record bytes)`; `record_hash =
  sha256-v1("retention-journal-chain:v1" ‖ prev_record_hash ‖ record_fingerprint)`;
  genesis `prev = "0"×64`; seq contiguous from 1.
* **Anchor table is append-only** (one anchor row per decision, never an upsert), so the
  store contains no `UPDATE` at all, and a *deleted anchor* is detected exactly like a
  deleted record (OD-RT-D).
* Payload keys are whitelisted per outcome; artifact content and any downstream datum are
  unrepresentable.
* **Pre-append verification:** anchor↔log agreement plus full-chain re-verification. A
  truncated or rewritten tail makes the append REFUSE (`JournalChainBroken`) and write
  nothing — the journal never silently extends a broken history (AC-1.3.2).
* **Verified read:** `read_entry`/`enumerate_entries` re-verify the prefix; any defect
  withholds the entry (`JournalTamperWithheld`). A missing tail over a disagreeing anchor
  is reported as tampering, never as a benign "not found".
* **Idempotency (AC-1.3.3):** `decision_key = sha256-v1(canonical decision bytes)` with a
  UNIQUE index; a duplicate append is refused and returns the existing seq/hash; no seq is
  consumed. The refusal also survives a reopen (storage-level backstop, not convention).
* **Zero residue by construction:** row + anchor commit in ONE transaction, so no
  pending/ACTIVE journal state exists and recovery is a *verification* (`recovery_status()`),
  never a sweep — and it is computed, not assumed.
* Non-member `append` failures (injected at `_insert_entry`, `_write_anchor`, or COMMIT,
  including a non-`sqlite3` exception) roll back and leave the store usable: unknown
  defects must not strand an open write transaction.

## §8 Consistency & orphan report (read-only by construction)

`build_consistency_report(capture_db, *, policy=None, evaluation_time=None,
journal_db_path=None)` opens the databases **`mode=ro`** (OD-RT-F): non-mutation is a
storage property, not a promise. It reports, without repairing:

| Code | Condition |
|---|---|
| `UNRESOLVED_ACTIVE_LEFTOVER` | ACTIVE residue (recovery's job, never this report's) |
| `INVARIANT_VIOLATION_INV_C1` | COMPLETED missing s1 / algorithm id / ref / size |
| `INVARIANT_VIOLATION_INV_C9` | FAILED_INCOMPLETE without note or without pinned FAILED |
| `INTEGRITY_UNVERIFIED_ON_COMPLETED` | COMPLETED never verified (completion-gate breach) |
| `ORPHAN_RECORD_CONTENT_MISSING` | record binds an `artifact_ref` with no content row |
| `ORPHAN_CONTENT_UNREFERENCED` | content row referenced by no record (never deleted here) |
| `TIMESTAMP_UNPARSEABLE` | `created_at`/`received_at` not an offset-bearing ISO instant |
| `FOREIGN_FINGERPRINT_ALGORITHM` | `s1_algorithm_id` foreign to `sha256-v1` (NO-VERDICT class) |
| `DUPLICATE_COMPLETED_S1_KEY` | >1 COMPLETED for one (s1, algorithm id) — backstop verified, not assumed |
| `RETENTION_POLICY_UNDECLARED` | candidates **not evaluated** (never reported as 0) |
| `JOURNAL_ORPHAN_DECISION` | journal decision naming an absent capture_id |
| `JOURNAL_CHAIN_BROKEN` | journal anchor/log disagreement |
| `JOURNAL_PURGE_REFUSAL_PRESENT` | blocked purges exist in the audit trail (informational) |

Determinism (AC-1.3.4): findings ordered by `(code, subject)`; canonical JSON (sorted
keys, no whitespace); no uuid, no path, no wall clock; `report_fingerprint =
sha256-v1(report bytes)`. Same state + same injected inputs ⇒ byte-identical text, across
reopens and separate connections. Absent inputs are reported as `NOT_EVALUATED`.

## §9 Testing obligations (binding)

Each registered AC must be traceable to at least one named test in the WP-1.3 suite
(`test_wp13_retention.py`, `test_wp13_journal.py`, `test_wp13_purge_gate.py`,
`test_wp13_consistency.py`, `test_wp13_recovery_matrix.py`) and to the smoke runner. A
traceability probe test re-checks this table mechanically.

| AC | Observable behaviour proven | Named tests (excerpt) |
|---|---|---|
| AC-1.3.1 | policy injection only; default-deny; fail-closed on unusable data | `test_policy_has_no_usable_defaults`, `test_each_missing_field_alone_is_refused`, `test_evaluate_with_no_policy_object_is_a_typed_refusal`, `test_unusable_timestamps_are_data_anomalies`, `test_active_record_is_state_refused_not_assessed`, `test_completed_but_integrity_failed_is_deferred_to_review`, `test_foreign_algorithm_record_is_deferred_not_eligible` |
| AC-1.3.2 | crash residues settle via the frozen path; broken chain detected and append refused; read withheld | `test_w1_record_only_residue_is_refused_by_retention_then_settled`, `test_all_crash_windows_end_terminal_with_the_retention_layer_attached`, `test_recovery_is_idempotent_across_restarts_with_journal`, `test_truncated_tail_is_detected`, `test_append_is_refused_on_a_broken_chain_and_extends_nothing`, `test_middle_rewrite_is_withheld_on_read`, `test_deleted_anchor_alone_is_detected` |
| AC-1.3.3 | purge blocked and inert (bytes stable); journal durable, idempotent, rollback-clean | `test_purge_is_blocked_with_no_policy_at_all`, `test_fabricated_authorization_is_refused_not_trusted`, `test_purge_request_leaves_the_capture_database_bytes_untouched`, `test_duplicate_decision_is_idempotent`, `test_duplicate_refusal_survives_reopen_as_a_storage_backstop`, `test_injected_failure_after_row_insert_leaves_zero_residue`, `test_injected_commit_failure_leaves_zero_residue`, `test_unknown_exception_leaves_no_open_transaction` |
| AC-1.3.4 | deterministic read-only report; DEF4 labels; additive-only boundaries | `test_two_independent_reports_are_byte_identical`, `test_report_never_mutates_the_capture_or_journal_storage`, `test_missing_policy_is_not_reported_as_zero_candidates`, `test_report_carries_no_paths_no_clock_and_no_content`, `test_every_decision_carries_the_def4_pending_label`, `test_frozen_capture_modules_do_not_import_wp13`, `test_no_wp13_symbol_is_exported_from_the_frozen_package_entrypoint`, `test_module_reads_no_clock` |

Required coverage also includes: recovery vs live ingest under real threads; concurrency
of journal appends (chain exact, no lost anchor); payload-key and vocabulary refusals
with zero residue; `smoke` 8-step cold-start run twice; full regression with the frozen
suites untouched.

## §10 Delegated implementation decisions (declared per D-09)

| ID | Decision | Reason |
|---|---|---|
| OD-RT-A | ISO-8601-with-offset parsing; naive/malformed → `DATA_ANOMALY` | guessing an offset would invent a value (Contract §14 discipline) |
| OD-RT-B | policy self-validates at construction; no partial policy representable | makes "undeclared policy" impossible to mistake for "policy that allows it" |
| OD-RT-C | purge gate closed by constant, no setter, credentials unverifiable | DEF4 has no ratified authorization scheme; a WP must not create one |
| OD-RT-D | append-only anchor table (one row per decision) instead of a head upsert | yields a strictly append-only store with **no** UPDATE/DELETE statement; anchor loss detectable |
| OD-RT-E | verified reads raise typed `JournalTamperWithheld` (withhold, not deliver) | VOR pattern applied to the journal: no silent broken read |
| OD-RT-F | report opens `mode=ro` SQLite URIs with the path percent-encoded (holoo_spike `read_only_uri` idiom) | non-mutation becomes a storage-enforced property, and `?`/`#`/`%` in a legal path can neither redirect the URI nor drop `mode=ro` |
| OD-RT-G | reuse the frozen `capture.model.utc_now_iso` as the only clock (journal `created_at` only); gate/report own no clock | one layer clock (OD-8 precedent); determinism where determinism is required |
| OD-RT-H | canonical JSON + `(code, subject)` ordering + fingerprint over report bytes | byte-level determinism is then testable, not asserted |
| OD-RT-I | WP-1.3 not re-exported from `capture/__init__.py` | editing that file would touch a frozen module; submodule import is sufficient |
| OD-RT-J | fault injection via test-side monkeypatch of `_insert_entry`/`_write_anchor` (no production fault flags) | matches the frozen suites' idiom; keeps production code flag-free |

## §11 Out of scope (FORBIDDEN — boundary of WP-1.3)

Retention/TTL/purge **policy values** and privacy markings (DEF4 — PO) | physical
deletion, data erasure, `VACUUM`, file removal | retention *execution* of any kind |
the operational REVIEW queue/access matrix (DEF2) | artifact presentation (DEF5) |
auto-creating Customers (D-06/DEF3) | any Sale/Inventory effect from the capture line
(AD-03/DEF1) | new idempotency or dedup definitions at document level (D-03) | new
lifecycle states or statuses (AS-03) | changes to any frozen file, including tests |
algorithm or storage selection changes | schema migration frameworking | threshold
ratification (D-07/P12.3) | opening DEF4 to "unblock" this WP.

**Policy boundary statement.** At delivery time `DEF4` retains
`Current Status: DEFERRED` with no values. WP-1.3 delivered mechanics only:
retention duration = unset, privacy marking = unset, purge = blocked, physical
deletion = not implemented. Any future WP that needs a value must receive it from a PO
policy decision, not from a default in this layer.
