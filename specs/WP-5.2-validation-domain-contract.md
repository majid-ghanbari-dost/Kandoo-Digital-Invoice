# SPEC-WP52-VSM — Validation State Machine + REVIEW Queue Contract v1.0-MVP

```text
Spec ID:      SPEC-WP52-VSM | Version: 1.0-MVP | Date: 2026-10-07
Status:       IMPLEMENTATION CONTRACT (T-5.2.1) — produced inline per TM/PO
              implementation dispatch 2026-10-07 ("WP-5.2 — Validation State
              Machine + REVIEW Queue — BUILD, not design-only")
Authority:    REG-WPR Phase Index P5 row (WP-5.2 Validation State Machine + REVIEW
              Queue) + PO implementation dispatch 2026-10-07 is the scope of
              record; this spec converts that scope into the binding
              implementation contract.
Frozen basis: AS-03 (the Validation State Machine is transferred VERBATIM from the
              frozen source vocabulary; redefining states or adding states is
              forbidden at WP level) | AD-04 (the Validation output model includes
              REVIEW and REJECT; field-level UNRESOLVED can take the Invoice to
              REVIEW; Clarification CL-1 — no paraphrase) | D-01 (value resolution
              order EXTRACTED → DERIVED → UNRESOLVED; in the absence of a valid
              method the value is UNRESOLVED and can take the Invoice to REVIEW —
              P5.2 is the layer where this domain label is finally created, per
              the dispatch, strictly inside this vocabulary) | D-03 (incomplete /
              conflicting cases → REVIEW) | D-08 (unresolved mismatch → REVIEW) |
              D-09 (delegated implementation details declared) | AD-02 (Validation
              domain boundary) | AS-01 (pipeline position) | SPEC-WP51-VAL
              (FROZEN — the engine this layer consumes; §5 records the downstream
              mapping guidance implemented HERE) | SPEC-WP42-DER | SPEC-WP41-NORM |
              SPEC-WP32-EVB | SPEC-WP31-EXT | WP-2.1/WP-2.2 | WP-1.1 (S1).
Baseline note (MNT-1): the physical Canonical Invoice v1 / Master Architecture
              documents are not yet committed (kandoo/baseline/ pending); per the
              project README the Decision Register is the valid self-contained
              textual representation of the Frozen decisions. The state vocabulary
              implemented here is therefore taken VERBATIM from the frozen
              register text + the implementation dispatch, which names the exact
              distinction to preserve: VALID | INVALID | DEFERRED | UNRESOLVED,
              plus REVIEW and REJECT from AD-04. No other state exists in this
              layer; no state is renamed, merged, or invented.
Upstream:     P3 → P4.1 → P4.2 → P5.1 → **P5.2** (consumes VERIFIED P5.1 validation
              records — the R1/R2 engine's durable verdicts — plus verified
              normalization reads for value-level projection).
Downstream:   P5.2 → Canonicalization Gate (P6) / REVIEW consumers. This layer
              implements NO gate logic; VALID records simply carry the explicit
              disposition that no REVIEW/REJECT action exists here.
```

## 1. Purpose and scope

WP-5.2 delivers ONE deterministic state machine plus ONE durable REVIEW queue. The
state machine projects the P5.1 validation engine's rule outcomes onto the domain
states required by the frozen vocabulary; the REVIEW queue durably holds validation
and canonicalization UNCERTAINTY for downstream handling. Both are mechanisms:
neither resolves semantics, neither creates business data, neither performs any
Canonicalization behavior.

In scope:
1. **Domain state projection** — a pure, deterministic, declared-priority function
   over VERIFIED P5.1 records: `VALID | INVALID | DEFERRED | UNRESOLVED` + a
   disposition (`REVIEW | REJECT | CLEAR`).
2. **Field-level UNRESOLVED creation** — the ONLY layer allowed to create the
   domain label, strictly per the D-01 resolution order and vocabulary (§4).
3. **REVIEW Queue** — durable, deterministic, traceable, idempotent, reason- and
   provenance-carrying, Verify-on-Read, append-only event lifecycle (§5).
4. **Persistence** per the project store pattern (separate SQLite file,
   synchronous=FULL, atomic commit, immutable history, deterministic fingerprints,
   no UPDATE/DELETE, tamper detection) (§9).
5. **Provenance preservation** — full-chain traceability through P5.1 into the
   frozen layers (§10).
6. Behavioral boundary tests (refusal matrix, determinism, tamper, restart, full
   Frozen regression).

Out of scope (FORBIDDEN — boundary of this WP): Canonicalization behavior of any
kind (canonical field mapping, line grouping/association, product/customer/
invoice-identity matching, semantic/fuzzy anything); automatic semantic resolution
of ANY kind; running R1/R2 validation itself (P5.1 does that — this layer only
consumes its verified records); normalization or derivation re-execution; tax
interpretation, currency conversion, date arithmetic; inventory mutation; Sale/
Invoice/Digital Invoice creation; Digital Invoice issuance; business entity
creation; Canonicalization Gate logic (P6); resolving or auto-closing REVIEW items
semantically; modifying Frozen P1–P5.1.

## 2. Input path (normative)

The verified validation read (WP-5.1 `read_validation`, VOR) is the ONLY sanctioned
path to P5.1 rule outcomes. The verified normalization read (WP-4.1) is the ONLY
sanctioned path for value-level field projection. Rule DECLARATIONS are consumed
through the frozen WP-5.1 Rule Registry (data), fingerprint-checked against each
P5.1 record's `rule_fingerprint` — declaration drift is an integrity failure. This
layer never reads stores in parallel, never re-reads raw artifacts, never accepts
values from any other source, and NEVER triggers validation, derivation, or
normalization itself.

Scope of one projection = ONE normalization record + the COMPLETE set of P5.1
records declared by the projected ruleset. Completeness is enforced fail-closed:
the declared rule-key list must EXACTLY equal the set of P5.1 records existing for
the normalization (missing keys AND extra records both refuse — a state is never
projected from partial facts, and evaluated outcomes are never silently ignored).

## 3. State machine — vocabulary and transitions (normative)

Domain states (VERBATIM frozen vocabulary — AS-03/AD-04/CL-1 discipline; the
dispatch names the distinction to preserve):

| State | Meaning (frozen anchors) |
|---|---|
| `VALID` | All declared rules of the projected ruleset hold; no field-level UNRESOLVED exists. The success state named by the dispatch ("حداقل distinction بین VALID / INVALID / DEFERRED / UNRESOLVED"). |
| `INVALID` | At least one declared rule was DECIDABLY violated (the comparison ran and failed). |
| `DEFERRED` | At least one rule could not decide (insufficient/ambiguous/non-exact) — validation uncertainty. |
| `UNRESOLVED` | A declared field's value resolution exhausted the D-01 order (no usable EXTRACTED value, no DERIVED value) — field-level, reason/status-bearing, traceable. |

Dispositions (the AD-04 Validation output model — REVIEW and REJECT — plus the
explicit empty-routing marker; dispositions are ROUTING markers of this layer, not
additional invoice states):

| Disposition | Meaning |
|---|---|
| `REVIEW` | The record is routed to the REVIEW queue (§5) — uncertainty held, never auto-resolved. |
| `REJECT` | Decisive, non-recoverable invalidity recorded on the state record; no REVIEW item. |
| `CLEAR` | Explicit empty routing — no REVIEW/REJECT action exists in this layer. Mechanism marker (analog of P5.1's mechanism-level vocabulary), not a Canonical Invoice state. |

Transition function (pure, deterministic, DECLARED priority — first match wins;
fixed order is a declared delegated detail per D-09 because the frozen text does
not order co-occurring outcomes; every route is anchored to a frozen source):

| # | Condition (over verified P5.1 records + field projection) | State | Disposition | Frozen anchor |
|---|---|---|---|---|
| T1 | any rule outcome `INVALID` with reason ∈ {`absent`, `present-not-usable`, `mismatch`} | `INVALID` | `REJECT` | AD-04 REJECT; decisive violation — the rule decided; D-08's REVIEW path is scoped to tolerance/rounding semantics |
| T2 | any rule outcome `INVALID` with reason ∈ {`mismatch-beyond-tolerance`, `mismatch-after-rounding`} | `INVALID` | `REVIEW` | D-08 (عدم تطابق حل‌نشده → REVIEW); SPEC-WP51-VAL §4 ("feeds the REVIEW path downstream per D-08 — the mapping itself is WP-5.2") |
| T3 | any projected field is `UNRESOLVED` (§4) | `UNRESOLVED` | `REVIEW` | D-01 (UNRESOLVED → REVIEW per Validation rules); AD-04 |
| T4 | any rule outcome `DEFERRED` | `DEFERRED` | `REVIEW` | SPEC-WP51-VAL §5 guidance (DEFERRED = insufficient information routes REVIEW); D-03 pattern (ambiguous → REVIEW; detail names the Canonicalization Gate) |
| T5 | else | `VALID` | `CLEAR` | All declared rules hold; the Canonicalization Gate (P6) remains the next downstream authority |

Stable `state_reason` codes: `decisive-invalid` (T1) | `d08-mismatch-review` (T2) |
`d01-unresolved-review` (T3) | `validation-deferred-review` (T4) | `all-rules-valid`
(T5). `state_detail` lists every contributing rule outcome (rule_id, version,
outcome, reason) and every UNRESOLVED field — the projection is auditable end to
end. Counters (`valid_count`, `invalid_count`, `deferred_count`,
`unresolved_count`) persist alongside.

REVIEW queue lifecycle (the only other transitions in this layer): queue item is
born `OPEN` at creation; append-only events evolve it; the CURRENT status is
always deterministically REDUCED from the event history (`OPEN`, or `CLOSED` once
a CLOSE event exists — terminal). Events never rewrite history; there is no
reopen, no update, no delete. Status is derived, never stored-and-mutated.

## 4. Field-level UNRESOLVED creation (normative — D-01 discipline)

P5.2 is the P5 domain layer where D-01's terminal resolution order
(`EXTRACTED → DERIVED → UNRESOLVED`) is finally materialized as durable domain
data. Creation is legal ONLY inside the frozen vocabulary and meaning:

- Declared fields = the union of `inputs[].field_name` over the projected ruleset's
  rule declarations (fingerprint-verified against the P5.1 records). Nothing else
  is projected — P5.2 never invents domain interest the ruleset did not declare.
- A declared field projects `RESOLVED` iff a usable value exists per the D-01
  order: a NORMALIZED (EXTRACTED-bearing) pointer from the P5.1 input refs, or a
  DERIVED pointer, or (for fields no rule resolved but the verified normalization
  read shows NORMALIZED rows for) the lowest-`field_seq` NORMALIZED row — with the
  candidate count recorded. Origin is relayed (`NORMALIZED` preferred per D-01
  order, else `DERIVED`); pointers are preserved; NOTHING is re-decided.
- A declared field projects `UNRESOLVED` iff NO usable value exists anywhere in
  the verified sources — exactly D-01's "در نبود روش معتبر" (absence of a valid
  method): no NORMALIZED row, no DERIVED record. Row carries `unresolved_reason =
  d01-no-valid-method`, the field name, scope pointers, and a detail naming the
  observed upstream statuses (or absence). UNRESOLVED is FIELD-LEVEL (D-01), never
  record-level invention.
- Ambiguous slots (≥2 candidates — association decisions belong to the
  Canonicalization Gate per SPEC-WP51-VAL OD-V10) are **NOT** UNRESOLVED: methods
  exist, so D-01's meaning is preserved verbatim. They surface as rule `DEFERRED`
  (T4) with the ambiguity detail naming the Gate, and the field projects RESOLVED
  with the candidate count recorded. P5.2 never resolves the ambiguity.
- UNRESOLVED rows are durable, fingerprint-anchored, traceable (§10), and never
  auto-resolved by this layer or any lifecycle event.

## 5. REVIEW Queue (normative — a real mechanism, not a list)

Durable queue in the same P5.2 store (separate tables, same transactional
pattern). One REVIEW item per projected state record whose disposition is `REVIEW`
(INV-R-1:1); `REJECT` and `CLEAR` never create items. Every item carries:

- identity: `review_id`, `domain_state_id`, `normalization_id`, `extraction_id`,
  `document_id`, `capture_id`, `capture_s1` (provenance anchors — pointers);
- context: `ruleset_id`, `ruleset_version`, `ruleset_fingerprint`, the projected
  `domain_state` and `state_reason`;
- reason: `review_reason` ∈ {`d08-mismatch-review`, `d01-unresolved-review`,
  `validation-deferred-review`} + `review_detail` (the full contributing-outcome
  listing) — the queue holds VALIDATION/CANONICALIZATION UNCERTAINTY, exactly;
- lifecycle: append-only, hash-chained event rows (`ANNOTATE`, `CLOSE`) with
  seq-contiguous per item, `prev_event_fingerprint` chaining, opaque actor string,
  free-text note, own fingerprint; at most ONE CLOSE per item (terminal; SQL
  partial-unique backstop + in-transaction check); the current status (`OPEN`/
  `CLOSED`) is derived from the history on every read.

The queue is NOT a semantic resolver: it never resolves UNRESOLVED, never retries
validation, never mutates upstream layers, never infers anything. Closing is an
explicit external act RECORDED here (append-only), with the decision itself living
outside this layer. Every append is fail-closed: the item AND its parent state
record must verify — a broken projection freezes its queue item (no event may
ride on broken provenance).

## 6. Data model (exact field sets — structural test enforced)

`DomainStateRecord` (durable header):
`domain_state_id`, `normalization_id`, `extraction_id`, `document_id`,
`capture_id`, `capture_s1`, `capture_s1_algorithm_id`, `ruleset_id`,
`ruleset_version`, `ruleset_fingerprint`, `ruleset_fingerprint_algorithm_id`,
`domain_state`, `disposition`, `state_reason`, `state_detail`, `rule_count`,
`valid_count`, `invalid_count`, `deferred_count`, `unresolved_count`, `created_at`,
`record_fingerprint`, `fingerprint_algorithm_id`.

`StateValidationRef` (pointer row, declared order):
`domain_state_id`, `ord_slot`, `validation_id`, `rule_id`, `rule_version`,
`rule_kind`, `rule_fingerprint`, `outcome`, `outcome_reason`.

`FieldProjectionRow` (durable, one per declared field):
`domain_state_id`, `field_name`, `projection_status` (`RESOLVED` | `UNRESOLVED`),
`origin_relayed` (`NORMALIZED` | `DERIVED`, RESOLVED only), `candidate_count`,
`source_normalization_id`, `source_extraction_id`, `source_field_seq`,
`source_derivation_id`, `unresolved_reason` (UNRESOLVED only), `detail`.

`ReviewQueueItem` (durable):
`review_id`, `domain_state_id`, `normalization_id`, `extraction_id`,
`document_id`, `capture_id`, `capture_s1`, `ruleset_id`, `ruleset_version`,
`ruleset_fingerprint`, `domain_state`, `review_reason`, `review_detail`,
`created_at`, `item_fingerprint`, `fingerprint_algorithm_id`.

`ReviewQueueEvent` (append-only, hash-chained):
`event_id`, `review_id`, `event_seq`, `event_type` (`ANNOTATE` | `CLOSE`),
`event_note`, `event_actor`, `created_at`, `prev_event_fingerprint`,
`event_fingerprint`, `fingerprint_algorithm_id`.

Pointer pattern is normative: NO pipeline value is ever copied into this layer;
the chain re-joins through verified reads (§10).

## 7. Determinism (normative)

The projection CONTENT (state, disposition, reasons, detail, counters, validation
refs, field projections) is a pure function of (the verified P5.1 records content,
the rule declarations content, the verified normalization content). Identity
scalars (`domain_state_id` uuid4 hex, `created_at`) are bookkeeping, separated
from content — SPEC-WP51-VAL §7 analog. INV-S-1:1 makes the identity unique so no
mutable duplicate can drift: a replay returns the existing record explicitly and
never creates a second one. Re-projection after pipeline state changed uses a NEW
ruleset_version (different fingerprint → different record; history immutable).

## 8. Outcomes (exhaustive — never silent)

project_domain_state(normalization_id, ruleset_id, ruleset_version, rule_keys) →
exactly one of:
  DomainStateProjected(record, validation_refs, field_projections, review_item|None)
  DomainStateAlreadyExists(domain_state_id, …)                  — INV-S-1:1 replay
  DomainStateSourceIntegrityFailure(normalization_id, reason)   — a P5.1 record /
                            rule declaration failed its verified read or
                            fingerprint check
  DomainStateSourceRefused(normalization_id, detail)            — unknown
                            normalization / no P5.1 records / incomplete or extra
                            evaluation vs the declared keys
  DomainStateSourceUnavailable(normalization_id, issue_report)  — no state
                            computable
  DomainStateStorageUnavailable(detail)                         — nothing
                            recordable (zero residue)

read_domain_state(domain_state_id) → exactly one of:
  DomainStateReadSuccess(record, validation_refs, field_projections, review|None,
                         review_status|None, verified_at)
  DomainStateReadIntegrityFailure(domain_state_id, reason, verified_at)
  DomainStateReadRefused(domain_state_id, detail)
  DomainStateReadVerificationUnavailable(domain_state_id, issue_report)

read_review_item(review_id) → exactly one of:
  ReviewItemReadSuccess(item, events, status, verified_at)
  ReviewItemReadIntegrityFailure(review_id, reason, verified_at)
  ReviewItemReadRefused(review_id, detail)
  ReviewItemReadVerificationUnavailable(review_id, issue_report)

append_review_event(review_id, event_type, note, actor) → exactly one of:
  ReviewEventAppended(event, status)
  ReviewEventRefused(review_id, detail)      — unknown type / already CLOSED /
                            chain-verify failure / unknown item
  ReviewEventUnavailable(review_id, issue_report)

trace_domain_state(domain_state_id) → exactly one of:
  DomainStateTraceSuccess(chain)      — every link re-verified in this walk
  DomainStateTraceIntegrityFailure(domain_state_id, link, reason)
                            — link ∈ domain_state|validation|normalization|
                              extraction|binding|document|capture
  DomainStateTraceRefused(domain_state_id, detail)
  DomainStateTraceVerificationUnavailable(domain_state_id, issue_report)

## 9. Persistence & invariants (same store pattern as P1–P5.1)

- OD-S1 storage: stdlib sqlite3, ONE separate embedded DB file; `synchronous=FULL`;
  idempotent schema; explicit BEGIN IMMEDIATE / COMMIT.
- OD-S2 atomic commit: state record + validation refs + field projections + review
  item (if REVIEW) in ONE transaction — zero residue on any failure, by
  construction. Events commit in their own single-purpose transactions.
- OD-S3 INV-S-1:1: at most one state record per (normalization_id,
  ruleset_fingerprint) — in-transaction check + UNIQUE index backstop.
  INV-R-1:1: at most one REVIEW item per domain_state_id — UNIQUE index backstop.
- OD-S4 ids/clock: domain_state_id / review_id / event_id = uuid4 hex; single
  layer clock (UTC ISO-8601).
- OD-S5 integrity anchors: `record_fingerprint` = sha256-v1 over the canonical
  serialization of record scalars + validation refs (ord order) + field
  projections (field_name order); `item_fingerprint` over item scalars;
  `event_fingerprint` over event scalars + `prev_event_fingerprint` (hash chain
  — history tamper-evident as a chain, not just per row); all verified inside
  every read (VOR).
- OD-S6 storage gates: SQL CHECKs — `domain_state IN ('VALID','INVALID',
  'DEFERRED','UNRESOLVED')`; `disposition IN ('CLEAR','REVIEW','REJECT')`;
  `domain_state = 'VALID' → disposition = 'CLEAR'`; `domain_state IN
  ('UNRESOLVED','DEFERRED') → disposition = 'REVIEW'`; field-projection shape
  (RESOLVED ↔ origin + pointer consistency; UNRESOLVED ↔ reason + NULL pointers);
  `event_type IN ('ANNOTATE','CLOSE')`; partial UNIQUE index enforcing at most
  one CLOSE per review item; defensive Python-side commit refusal.
- OD-S7 no update/delete: state records, refs, projections, review items and
  events are immutable once committed; no UPDATE or DELETE path exists in this
  store; queue lifecycle is append-only event history with derived status.

## 10. Provenance / traceability chain (normative — pointers, verified reads)

    Domain State Record (domain_state_id)
        ↓ ruleset_fingerprint + validation refs (rule outcomes consumed verbatim)
    P5.1 Validation Records (validation_ids) — each walked through
        trace_validation: validation → rule fingerprint → inputs →
        [WP-4.2 sub-chain for DERIVED inputs] → normalization → extraction →
        binding → Document/Page/span → Capture S1
    Field Projection Rows (declared fields; RESOLVED pointers → normalization
        field_seq | derivation_id; UNRESOLVED rows anchored at the scope record)
        ↓ verified normalization read (WP-4.1 VOR)
    Normalization Record → Extraction → Binding → Document/Page/span
        ↓ capture linkage (capture_id + capture_s1 carried and equality-checked)
    Capture S1

`trace_domain_state` re-verifies EVERY link inside one call. P5.1 provenance is
consumed through its own verified trace (never bypassed, never destroyed); no
chain is cut or replaced; REVIEW items inherit the anchors of their state record.

## 11. Delegated implementation details (declared per D-09)

- OD-S8 transition priority: the fixed T1 > T2 > T3 > T4 > T5 order (§3) — the
  frozen sources anchor each route but do not order co-occurring outcomes; any
  fixed order is deterministic and auditable; this one is declared here.
- OD-S9 decisive vs tolerance INVALID split: reason families {absent,
  present-not-usable, mismatch} → REJECT (T1) vs {mismatch-beyond-tolerance,
  mismatch-after-rounding} → REVIEW (T2). D-08 scopes its REVIEW path to
  tolerance/rounding mismatches; the remaining INVALID reasons are decisive
  violations with no uncertainty to hold.
- OD-S10 ambiguous ≠ UNRESOLVED: ambiguous slots stay rule-DEFERRED (T4) and the
  field projects RESOLVED with candidate_count — D-01's UNRESOLVED meaning is
  preserved verbatim; association remains the Canonicalization Gate's decision.
- OD-S11 RESOLVED backfill: fields declared by the ruleset that no P5.1 slot
  resolved are checked against the verified normalization read (lowest field_seq,
  candidate count recorded) — value-level D-01 projection, never re-deciding
  association or statuses.
- OD-S12 ruleset fingerprint: sha256-v1 over the ruleset identity (ruleset_id,
  ruleset_version) + the ordered declared (rule_id, rule_version,
  rule_fingerprint-from-record) — anchors the exact projected evaluation; a NEW
  ruleset_version is a DIFFERENT validation key (SPEC §7); declaration drift
  (registry fingerprint ≠ record fingerprint) is an integrity failure.
- OD-S13 event hash chain: per-item `prev_event_fingerprint` chaining verified on
  every read and every append — history tamper-evident as a chain.
- OD-S14 no forward dependency on P6: nothing here implements or previews the
  Canonicalization Gate; VALID/CLEAR records carry only the explicit statement
  that no REVIEW/REJECT action exists in this layer.

## 12. AC mapping (verification in Acceptance Register)

- AC-5.2.1 State machine: deterministic, declared-priority projection of verified
  P5.1 outcomes onto the VERBATIM frozen vocabulary (VALID | INVALID | DEFERRED |
  UNRESOLVED + REVIEW/REJECT dispositions per AD-04); every transition explicit,
  auditable, testable; no extra or renamed states.
- AC-5.2.2 UNRESOLVED: field-level, created ONLY per the D-01 order and meaning,
  reason/status-bearing, provenance-preserving, traceable; ambiguous slots never
  UNRESOLVED; never auto-resolved.
- AC-5.2.3 REVIEW queue: durable, deterministic, idempotent (INV-R-1:1), duplicate
  controlled, reason- and provenance-carrying, Verify-on-Read, append-only
  hash-chained lifecycle with derived status, no UPDATE/DELETE, restart-safe,
  tamper-evident.
- AC-5.2.4 Boundary & integration: complete provenance chain machine-checkable to
  Capture S1 (through P5.1's whole-chain walks); no Canonicalization behavior; no
  semantic resolution; no product/customer matching; no Canonical Invoice
  creation; Frozen P1–P5.1 untouched (full regression green).

## 13. Test expectations (behavior, not line coverage)

Mandated axes (dispatch): VALID mapping; INVALID mapping; DEFERRED mapping;
UNRESOLVED creation per contract; exact frozen vocabulary; state transition
validity; invalid transition rejection; REVIEW creation; REVIEW idempotency;
REVIEW persistence; duplicate prevention; provenance preservation; Verify-on-Read;
tamper detection; restart recovery; no automatic semantic resolution; no
product/customer matching; no Canonical Invoice creation; integration with P5.1;
full regression.
