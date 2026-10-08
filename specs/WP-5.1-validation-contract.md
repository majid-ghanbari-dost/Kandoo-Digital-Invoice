# SPEC-WP51-VAL — R1/R2 Validation Engine Contract v1.0-MVP

```text
Spec ID:      SPEC-WP51-VAL | Version: 1.0-MVP | Date: 2026-10-07
Status:       IMPLEMENTATION CONTRACT (T-5.1.1) — produced inline per TM/PO implementation
              dispatch 2026-10-07 ("WP-5.1 — R1/R2 Validation Engine — BUILD, not scope")
Authority:    REG-WPR Phase Index P5 row (WP-5.1 R1/R2 Engine) + PO implementation
              dispatch 2026-10-07 is the scope of record; this spec converts that scope
              into the binding implementation contract.
Frozen basis: D-01 (provenance vocabulary + resolution order EXTRACTED → DERIVED →
              UNRESOLVED; UNRESOLVED owned by P5 domain layer — never invented here) |
              D-08 (R2 rounding: tolerance is a CALIBRATION PARAMETER — parameterized,
              no fixed value; unresolved mismatch → REVIEW path) | D-07 (thresholds are
              calibration placeholders, never engineering targets) | D-09 (delegated
              implementation details declared) | AD-02 (domain boundary: Validation) |
              AD-04 (Validation output model REVIEW/REJECT + field-level UNRESOLVED →
              REVIEW is WP-5.2 territory; verbatim Canonical-Invoice-v1 vocabulary
              required there) | AS-01 (pipeline position) | AS-03 (Validation State
              Machine = WP-5.2, verbatim frozen states; this WP defines NO invoice
              states) | SPEC-WP42-DER | SPEC-WP41-NORM (FROZEN) | SPEC-WP32-EVB |
              SPEC-WP31-EXT | WP-2.1/WP-2.2 | WP-1.1 (S1 capability).
Upstream:     P3 → P4.1 → P4.2 → **P5.1** (per dispatch; the engine consumes verified
              NORMALIZED values and verified DERIVED values). Canonicalization (P6)
              remains downstream and untouched.
Downstream:   P5.1 → WP-5.2 Validation State Machine (REVIEW/REJECT/success mapping) →
              Canonicalization / P6 consumers.
```

## 1. Purpose and scope

WP-5.1 delivers ONE engine: a deterministic, rule-driven validation layer that applies
declared **R1** (structural/consistency) and **R2** (parametric / rounding) validation
rules over the pipeline's current output values, producing explicit, auditable,
provenance-preserving rule outcomes. It produces VERDICTS — never new business values.

In scope:
1. Declarative, versioned, fingerprinted Rule Registry (data, never hidden code) with
   rule kinds **R1** and **R2**.
2. R1 rule types (v1): `presence` (a declared field must exist as a usable value) and
   `exact-consistency` (declared exact equality between a target field and an exact
   expression over other fields — the totals-consistency verdict assigned to
   Validation by SPEC-WP42-DER §1 out-of-scope note).
3. R2 rule types (v1): `tolerated-equality` (parametric tolerance comparison per D-08)
   and `rounded-equality` (explicit parametric rounding comparison per D-08).
4. Exact-arithmetic rounding (D-08): explicit, deterministic, versioned/parameterized,
   float-free, auditable, reproducible. NO implicit rounding anywhere.
5. Explicit, exhaustive rule outcomes: `VALID | INVALID | DEFERRED` — every non-decision
   is a declared DEFERRED with a stable reason, never silent, never invented.
6. Persistence per the project store pattern (separate SQLite file, synchronous=FULL,
   atomic commit, INV-V-1:1, no UPDATE/DELETE, verified read with sha256-v1).
7. Provenance preservation: validation results carry input POINTERS and never destroy
   or override WP-4.1/WP-4.2 provenance; whole-chain traceability walk.
8. Behavioral boundary tests (refusal matrix, determinism, tamper, full Frozen
   regression).

Out of scope (FORBIDDEN — boundary of this WP): Canonicalization behavior of any kind
(canonical field mapping, line grouping/association, product/customer/invoice-identity
matching, semantic/fuzzy anything); creating Sale/Invoice/Digital Invoice; Digital
Invoice issuance; Inventory/KPI mutation; business entity creation; tax-rate logic,
discount/markup interpretation, currency conversion, date arithmetic; cross-document
validation; automatic resolution of domain `UNRESOLVED`; creation/assignment/inference
of `UNRESOLVED`; implementing the Validation State Machine or REVIEW queue (WP-5.2);
redefining or adding invoice states (AS-03); modifying Frozen P1/P2/P3/P4.1/P4.2.

## 2. Input path (normative — mirrors SPEC-WP42-DER §2)

The verified normalization read (WP-4.1 `read_normalization`) is the ONLY sanctioned
path for NORMALIZED values. The verified derivation read (WP-4.2 `read_derivation`,
via the derivation service) is the ONLY sanctioned path for DERIVED values. The engine
never reads stores in parallel, never re-reads raw artifacts, and never accepts values
from any other source.

Evidence-bearing-ness is enforced fail-closed: the source extraction must hold a
healthy WP-3.2 verified binding (read-only) before any rule evaluation.

Engine independence: the engine imports NO extraction engine and no Canonicalization
component; identical inputs validate identically regardless of which engine produced
them.

Validation scope = ONE normalization record (its NORMALIZED fields) + the derivation
records that hang off that same normalization record (their DERIVED outputs). Nothing
outside this scope is ever consulted (no cross-document, no cross-record inputs).

## 3. Rule Registry (declarative, versioned, fingerprinted)

A rule is DATA — a declaration, auditable end-to-end, never executable code:

- `rule_id`            stable identity (e.g. "kandoo-val-total-gross-consistency")
- `rule_version`       version string; a new version is a DIFFERENT validation key
- `rule_kind`          `R1` (structural/consistency) | `R2` (parametric/rounding)
- `rule_type`          R1: `presence` | `exact-consistency`
                       R2: `tolerated-equality` | `rounded-equality`
- `inputs`             ordered declared slots: (slot_name, field_name, origin) where
                       origin ∈ {`normalized`, `derived`} — field_name in the source
                       record's engine vocabulary (no canonical mapping happens here)
- `target_slot`        for comparison types: the declared slot whose value is the
                       comparison target
- `expression`         for comparison types: a tree over declared slot references with
                       the SAME closed op vocabulary as WP-4.2 (ADD | SUB | MUL | DIV);
                       leaves are declared slot references ONLY — no literals
- `tolerance`          for `tolerated-equality` ONLY: canonical decimal string ≥ 0 —
                       a CALIBRATION PARAMETER injected at construction (D-08: no fixed
                       value may be hardcoded); part of the rule fingerprint
- `rounding_precision`, `rounding_mode`
                       for `rounded-equality` ONLY: precision int ≥ 0; mode in the
                       declared whitelist HALF_UP | HALF_EVEN | FLOOR | CEILING | DOWN

Construction-time validation (fail-closed): kind/type pairing enforced (R1 can never
carry tolerance or rounding parameters — storage-gated too); comparison types require
target_slot + expression; expression leaves must name declared slots; every declared
slot must be used (in the expression or as target); DIV arity exactly 2; ADD/SUB/MUL
arity ≥ 2; tolerance canonical decimal ≥ 0; precision ≥ 0; mode whitelisted; names
non-empty; no literals, no callables, no code. Any violation raises
`ValidationRuleError` at registration — a malformed rule can never enter the registry,
therefore never execute. The engine also verifies at registration that NO rule ships
with a hardcoded tolerance default (parameters are constructor-injected).

Registry: constructor-injected mapping keyed by `(rule_id, rule_version)` — two
versions of one rule coexist as distinct validation keys and produce DISTINCT durable
records. Rule fingerprint: `rule_fingerprint` = sha256-v1 over the canonical
serialization of the declaration (id, version, kind, type, target, tolerance, rounding
parameters, inputs in declared order, expression tree in declared order). The same
declaration always yields the same fingerprint; every validation record stores the
fingerprint of the exact rule version that produced it.

Reference registry `ReferenceValidationRulesV1(tolerance, precision, mode)` ships
EXACTLY FOUR MVP rules (an executability choice, NOT a business-rule decision — new
rules plug in as declared data with a new (id, version); ALL R2 parameters are
required constructor arguments — nothing is hardcoded, per D-08):

    R1 presence            kandoo-val-total-net-present      v1: total.net usable
    R1 exact-consistency   kandoo-val-total-gross-consistency v1:
                              target total.gross == ADD(total.net, tax.amount)
    R2 tolerated-equality  kandoo-val-total-gross-tolerance   v1:
                              |ADD(total.net, tax.amount) − total.gross| ≤ tolerance
    R2 rounded-equality    kandoo-val-total-gross-rounded     v1:
                              ROUND(ADD(total.net, tax.amount), precision, mode)
                              == total.gross

## 4. Exact arithmetic and rounding semantics (normative)

- Value grammar and parsing are REUSED verbatim from the WP-4.2 mechanism
  (`derivation.arithmetic`): canonical decimal strings parsed into exact rationals
  (`fractions.Fraction`); a float never exists anywhere in this engine; non-canonical
  values are refused fail-closed, never parsed leniently (defensive — WP-4.1 already
  guarantees the grammar on NORMALIZED output).
- R1 `exact-consistency`: equality is EXACT rational equality. A non-terminating DIV
  inside the expression has no exact decimal value → the rule cannot decide → DEFERRED
  (`non-exact-intermediate`). Rounding is NEVER applied to make R1 pass (R1 has no
  rounding parameters — structurally enforced).
- R2 `tolerated-equality`: diff = |expression − target| computed EXACTLY. diff == 0 →
  VALID (`exact-match` — the exact value is preserved, no tolerance consumed). diff ≤
  declared tolerance → VALID (`within-tolerance`; diff and tolerance recorded in the
  detail). diff > tolerance → INVALID (`mismatch-beyond-tolerance`; feeds the REVIEW
  path downstream per D-08 — the mapping itself is WP-5.2). A declared tolerance never
  licenses implicit rounding; non-exact intermediates → DEFERRED.
- R2 `rounded-equality` (the D-08 parametric rounding): if expression == target
  exactly → VALID (`exact-match`, rounding_applied = 0 — "a value acceptable without
  rounding keeps its exact value"). Otherwise the expression value is rounded ONCE,
  explicitly, at the declared (precision, mode); if the rounded value equals the
  target → VALID (`rounded-match`, rounding_applied = 1 with the full rounding record);
  else → INVALID (`mismatch-after-rounding`, rounding record still attached for audit).
  A non-exact intermediate is acceptable HERE and ONLY here — explicit rounding is the
  declared purpose of this rule type (rounding an exact rational at a declared
  precision is well-defined and reproducible).
- Rounding primitive (normative — `round_exact`): value · 10^precision formed exactly;
  integer part and exact remainder compared against the declared mode:
  `HALF_UP` ties away from zero; `HALF_EVEN` ties to nearest even; `FLOOR` toward
  −∞; `CEILING` toward +∞; `DOWN` toward zero. Output emitted by `to_fixed_decimal_string`
  with EXACTLY `precision` fraction digits (explicit precision — never stripped, never
  exponent notation). Same (value, precision, mode) ALWAYS yields the same string.
- Rounding audit record: every applied rounding persists `rule_id, rule_version,
  precision, mode, input (exact value), output (rounded value)` inside the validation
  record — reproducible by recomputation. The rounding output is an AUDIT artifact of
  the comparison; it is NOT a pipeline value: it never enters normalization or
  derivation stores, never becomes a canonical/derived field, and no downstream
  consumer may treat it as one. Validation produces verdicts, not values.

## 5. Outcome vocabulary (explicit, exhaustive — never silent)

Rule-evaluation outcomes (mechanism level, persisted):

| Term | Meaning |
|---|---|
| `VALID` | The declared rule holds under exact evaluation (exact-match / within-tolerance / rounded-match). |
| `INVALID` | The declared rule is violated (absent required field / present-but-unusable / exact mismatch / beyond tolerance / mismatch after declared rounding). The comparison was decidable and failed. |
| `DEFERRED` | Insufficient information to decide (a referenced value missing / present only with a non-usable status / ambiguous — >1 candidate / non-exact intermediate in an exact context). A decision OF non-decision, durably recorded with the resolved input pointers. |
| `UNRESOLVED` | NOT IN THIS LAYER. Domain label owned by the P5 domain layer per D-01 (field-level UNRESOLVED can drive REVIEW per AD-04 — the mapping is WP-5.2). This engine never creates, assigns, infers, or resolves UNRESOLVED — structurally enforced (§9 storage gate + §13 tests). |

Semantic distinctions (normative):
- WP-4.1 `DEFERRED` is a NORMALIZATION-LAYER FIELD status (a value the declared grammar
  could not transform). WP-4.2 NOT_DERIVABLE/mechanism-DEFERRED is an EPHEMERAL
  derivation refusal (no value, nothing persisted). WP-5.1 `DEFERRED` is a DURABLE
  RULE OUTCOME: the rule ran, could not decide, and the non-decision itself is the
  auditable result. All three are explicit refusals/non-decisions; NONE of them is
  `UNRESOLVED`; `DEFERRED ≠ UNRESOLVED` (SPEC-WP41-NORM §4.1) extends verbatim here.
- Rule outcomes are NOT invoice states. The Validation State Machine (REVIEW / REJECT /
  the verbatim success state of Frozen Canonical Invoice v1) is WP-5.2 (AS-03/AD-04);
  this engine defines none of them. Downstream mapping guidance recorded, not
  implemented: INVALID (mismatch) and DEFERRED (insufficient information) are the
  inputs WP-5.2 uses to route REVIEW per D-08/AD-04.
- Provenance labels of upstream values are relayed, never re-decided: this engine
  produces NO provenance labels at all — it never stamps NORMALIZED/EXTRACTED/DERIVED/
  UNRESOLVED onto anything.

Reason codes (stable, coarse): `exact-match` | `within-tolerance` | `rounded-match` |
`absent` | `present-not-usable` | `mismatch` | `mismatch-beyond-tolerance` |
`mismatch-after-rounding` | `insufficient-input` | `ambiguous-input` |
`non-exact-intermediate`.

## 6. Data model (exact field sets — structural test enforced)

`ValidationRecord` (durable header):
`validation_id`, `normalization_id`, `extraction_id`, `document_id`, `capture_id`,
`capture_s1`, `capture_s1_algorithm_id`, `ruleset_id`, `ruleset_version`,
`rule_id`, `rule_version`, `rule_kind`, `rule_type`, `rule_fingerprint`,
`rule_fingerprint_algorithm_id`, `outcome`, `outcome_reason`, `outcome_detail`,
`rounding_applied`, `rounding_precision`, `rounding_mode`, `rounding_input_value`,
`rounding_output_value`, `input_count`, `created_at`, `record_fingerprint`,
`fingerprint_algorithm_id`.

`ValidationInputRef` (durable pointer row — NO VALUE, by design):
`input_slot` (0-based declaration order), `slot_name`, `field_name`, `value_origin`
(`NORMALIZED` | `DERIVED`), `source_normalization_id`, `source_extraction_id`,
`source_field_seq` (NORMALIZED inputs), `source_derivation_id` (DERIVED inputs).

The pointer pattern is normative: input VALUES are never copied into this layer; the
chain is re-joined through verified reads (§10). `input_count` = number of stored
input rows (presence-INVALID and fully-unresolved DEFERRED records may carry 0 rows;
otherwise every resolved slot contributes exactly one row).

## 7. Determinism (normative)

The validation CONTENT (outcome, reason, rounding record, input pointers) is a pure
function of (source normalization content, derivation records content, rule
declaration). Identity scalars (`validation_id` uuid4 hex, `created_at`) are
bookkeeping, separated from content — SPEC §6 analog. INV-V-1:1 makes the identity
unique so no mutable duplicate can drift: a replay returns the existing record
explicitly and never creates a second one. Re-evaluation after pipeline state changed
(e.g. a derivation ran after a DEFERRED validation) uses a NEW rule_version — history
is immutable (no UPDATE/DELETE).

## 8. Outcomes (exhaustive — never silent)

validate(normalization_id, rule_id, rule_version) → exactly one of:
  ValidationCompleted(record, inputs)                         — committed atomically
  ValidationAlreadyExists(validation_id, …)                   — INV-V-1:1 replay
  ValidationRuleNotRegistered(rule_id, rule_version)
  ValidationSourceIntegrityFailure(normalization_id, reason)  — source VOR FAILED
                            (normalization, binding, or a referenced derivation)
  ValidationSourceRefused(normalization_id, detail)           — unknown normalization /
                            no healthy binding
  ValidationSourceUnavailable(normalization_id, issue_report) — no verdict computable
  ValidationStorageUnavailable(detail)                        — nothing recordable
                            (zero residue)

read_validation(validation_id) → exactly one of:
  ValidationReadSuccess(record, inputs, verified_at)
  ValidationReadIntegrityFailure(validation_id, reason, verified_at) — content withheld
  ValidationReadRefused(validation_id, detail)
  ValidationReadVerificationUnavailable(validation_id, issue_report)

trace_validation(validation_id) → exactly one of:
  ValidationTraceSuccess(chain)       — every link re-verified in this walk
  ValidationTraceIntegrityFailure(validation_id, link, reason)
                            — link ∈ validation|normalization|derivation|extraction|binding|document
  ValidationTraceRefused(validation_id, detail)
  ValidationTraceVerificationUnavailable(validation_id, issue_report)

## 9. Persistence & INV-V-1:1 (same store pattern as P1–P4.2)

- OD-V1 storage: stdlib sqlite3, ONE separate embedded DB file; `synchronous=FULL`;
  idempotent schema; explicit BEGIN IMMEDIATE / COMMIT.
- OD-V2 atomic commit: validation record + input-ref rows in ONE transaction — zero
  residue on any failure, by construction.
- OD-V3 INV-V-1:1: at most one validation per (normalization_id, rule_id,
  rule_version) — in-transaction check + UNIQUE index backstop. A different rule
  version is a DIFFERENT record.
- OD-V4 ids/clock: validation_id = uuid4 hex; single layer clock (UTC ISO-8601).
- OD-V5 integrity anchor: record_fingerprint = sha256-v1 over the canonical
  serialization of record scalars + input-ref rows in input_slot order (rounding
  fields included); recomputed inside every read (VOR). The rule fingerprint is
  embedded in the covered scalars.
- OD-V6 storage gates: SQL CHECKs — `outcome IN ('VALID','INVALID','DEFERRED')`
  (UNRESOLVED can never be stored); `rule_kind IN ('R1','R2')`; rounding fields
  all-NULL iff rounding_applied = 0, all-NOT-NULL iff rounding_applied = 1;
  `rule_kind = 'R1' → rounding_applied = 0` (R1 can never round); input rows
  value_origin/field_seq/derivation_id consistency; defensive Python-side commit
  refusal.
- OD-V7 no update/delete: validation results are immutable once committed; no UPDATE
  or DELETE path exists in this store.

## 10. Provenance / traceability chain (normative — pointers, verified reads)

    Validation Record (validation_id)
        ↓ rule_id + rule_version + rule_fingerprint (stored in the record)
    Input References (input rows: slot → normalization field_seq | derivation_id)
        ↓ verified normalization read (WP-4.1 VOR)          [NORMALIZED inputs]
        ↓ verified derivation read + its whole chain (WP-4.2 VOR) [DERIVED inputs]
    Normalization Record / field_seq  →  Extracted field (extraction_id + field_seq)
        ↓ verified extraction read (WP-3.1 VOR)
    Evidence Binding (WP-3.2 verified read: entry for field_seq)
        ↓ verified document read (WP-2.1 VOR)
    Document/Page/span (page_fingerprint + byte offsets; span slice decodes verbatim)
        ↓ capture linkage (capture_id + capture_s1 carried and equality-checked)
    Capture S1

`trace_validation` re-verifies EVERY link inside one call — for DERIVED inputs the
WP-4.2 provenance is consumed through its verified read, never bypassed and never
destroyed. Deliverable: pointers and verdicts only; source values never copied forward.

## 11. Delegated implementation details (declared per D-09)

- OD-V8 exact-arithmetic reuse: `derivation.arithmetic` (parse/evaluate/exact
  formatter) is reused verbatim as the lower-layer capability of the same pipeline —
  one canonical decimal grammar, one parser, zero divergence; rounding is implemented
  LOCALLY in this layer over exact rationals (`rounding.py`, pure functions).
- OD-V9 reference registry: `ReferenceValidationRulesV1` ships the four declared MVP
  rules (§3) with ALL R2 parameters constructor-injected (required arguments — no
  defaults, per D-08); an executability choice, NOT a business-rule decision.
- OD-V10 engine independence + no Canonicalization: zero engine imports; zero
  canonical field mapping; rule declarations reference engine-vocabulary field names
  verbatim; association/ambiguity is never resolved here (DEFERRED, detail names the
  Canonicalization Gate).
- OD-V11 DERIVED-input resolution: via the WP-4.2 service verified reads only
  (`derivations_for_normalization` + `read_derivation`); a tampered referenced
  derivation → ValidationSourceIntegrityFailure; multiple derivations of one output
  field → DEFERRED (ambiguous-input) — no silent pick.

## 12. AC mapping (verification in Acceptance Register)

- AC-5.1.1 R1 engine: declared, versioned, fingerprinted R1 rules (presence +
  exact-consistency) evaluate deterministically over verified inputs; valid/invalid/
  deferred outcomes explicit; inputs provenance-preserving (pointers); no value
  invented.
- AC-5.1.2 R2 engine + parametric rounding (D-08): tolerance/precision/mode are
  injected, versioned parameters (no fixed values); rounding explicit, deterministic,
  float-free, auditable, reproducible; exact values preserved when acceptable without
  rounding; no implicit rounding anywhere.
- AC-5.1.3 Persistence per project pattern: separate SQLite, synchronous=FULL, atomic
  commit, INV-V-1:1 explicit replay, no UPDATE/DELETE, VOR read with sha256-v1,
  restart-safe, tamper → explicit failure without content delivery; outcome storage
  gate (VALID/INVALID/DEFERRED only — UNRESOLVED structurally impossible).
- AC-5.1.4 Boundary & integration: complete provenance chain machine-checkable to
  Capture S1 (including through DERIVED inputs); P4.2 provenance preserved; no
  Canonicalization behavior; no business-semantic inference; no UNRESOLVED; engine
  independence; Frozen P1–P4.2 untouched (full regression green).

## 13. Test expectations (behavior, not line coverage)

Mandated axes (dispatch): R1 valid; R1 invalid; R1 deferred/insufficient-data; R2
valid; rounding exactness; rounding precision; rounding mode; no-float guarantee;
deterministic result; rule version separation; provenance preservation; Verify-on-Read;
tamper detection; idempotent replay; malformed input; missing input; DERIVED input
validation; no business-semantic inference; no Canonicalization behavior; full
regression with all frozen layers.
