# SPEC-WP42-DER — DERIVED Provenance & Exact Derivation Mechanism Contract v1.0-MVP

```text
Spec ID:      SPEC-WP42-DER | Version: 1.0-MVP | Date: 2026-10-06
Status:       IMPLEMENTATION CONTRACT (T-4.2.1) — produced inline per TM/PO implementation
              dispatch 2026-10-06 ("WP-4.2 — BUILD, not another design report")
Authority:    REG-WPR §WP-4.2 (rescoped 2026-10-05, PO-approved) is the scope of record;
              this spec converts that scope into the binding implementation contract.
Frozen basis: D-01 (provenance vocabulary + resolution order EXTRACTED → DERIVED →
              UNRESOLVED) | D-08 (rounding R2 → WP-5.1) | D-09 (governance of delegated
              decisions) | AS-01 (pipeline position: ... → Normalization → [this
              mechanism] → Canonicalization Gate → ...) | SPEC-WP41-NORM v1.0-MVP
              (FROZEN 2026-10-05) | SPEC-WP32-EVB | SPEC-WP31-EXT | WP-2.1/WP-2.2 |
              WP-1.1 (S1 capability).
```

## 1. Purpose and scope

WP-4.2 delivers ONE mechanism: a deterministic, exact-arithmetic derivation engine that
produces `DERIVED` values from `NORMALIZED` inputs, with complete provenance and
traceability, persisted under the project store pattern. It is the D-01 `DERIVED` label's
ONLY producer in the pipeline.

In scope (mirror of REG-WPR §WP-4.2 "Scope"):
1. DERIVED provenance model (D-01 verbatim; storage-level CHECK).
2. Declarative, versioned Formula Registry (data, never hidden code).
3. Derivation engine over NORMALIZED values (exact decimal/rational arithmetic; no
   float; no rounding).
4. Explicit, exhaustive outcomes — every non-execution is a declared refusal, never
   silent, never an invented value.
5. Pointer-based traceability derived → inputs → normalization → extraction → binding →
   Document/Page/span → Capture S1.
6. Persistence per the project store pattern (separate SQLite file, synchronous=FULL,
   atomic commit, INV-D-1:1, no UPDATE/DELETE, verified read with sha256-v1).
7. Behavioral boundary tests (refusal matrix, determinism, tamper, full Frozen
   regression).

Out of scope (FORBIDDEN — unchanged from the registered scope): line-item grouping /
association discovery; general `unit_amount = total / quantity` derivation (association
is P6, non-exact division + rounding is D-08/WP-5.1); tax rate/rounding/discount/markup
or any fiscal logic; currency conversion; product/customer matching; fuzzy/semantic
anything; totals-consistency verdicts; date arithmetic; cross-document derivation;
business-rule inference; creating/resolving `UNRESOLVED`; creating Sale/Invoice/Digital
Invoice; Inventory/KPI mutation; any behavior change to Frozen WP-1.1/WP-2.1/WP-2.2/
WP-3.1/WP-3.2/WP-4.1; forward dependency on P5/P6 artifacts.

## 2. Input path (normative — mirrors SPEC-WP41-NORM §2)

The verified normalization read (WP-4.1 `read_normalization`) is the ONLY sanctioned
value path. The mechanism never reads normalization/extraction/document/capture stores
in parallel, never re-reads raw artifacts, and never accepts values from any other
source.

Evidence-bearing-ness (REG-WPR scope condition 2) is enforced at derive time through the
frozen WP-3.2 verified binding read of the source extraction — read-only; a source
extraction without a healthy five-link binding is refused (see §8 outcomes). The binder
consumes nothing from this layer.

Engine independence: the mechanism imports NO extraction engine and knows nothing about
engines beyond the relayed record scalars; identical NORMALIZED inputs derive identically
regardless of which engine produced them.

## 3. Formula Registry (declarative, versioned, fingerprinted)

A formula is DATA — a declaration, auditable end-to-end, never executable code:

- `formula_id`            stable identity (e.g. "kandoo-der-total-gross-from-net-tax")
- `formula_version`       version string; a new version is a DIFFERENT derivation key
- `output_field_name`     engine-vocabulary name of the produced field
- `inputs`                ordered slots: (slot_name, field_name) — field_name in the
                          source record's engine vocabulary
- `expression`            a tree over the declared ops: ADD | SUB | MUL | DIV, whose
                          leaves are input-slot references ONLY (v1 has no literals)

Construction-time validation (fail-closed): ops whitelisted; DIV arity exactly 2;
ADD/SUB/MUL arity ≥ 2; every leaf names a declared slot; every declared slot is used;
`output_field_name` non-empty and not equal to any input field_name (a formula that
would shadow a read value is malformed by construction); names non-empty. Any violation
raises `DerivationFormulaError` at registration — a malformed formula can never enter
the registry, therefore never execute.

Registry: constructor-injected mapping keyed by `(formula_id, formula_version)` — two
versions of one formula coexist as distinct derivation keys. The MVP reference registry
(`ReferenceDerivationFormulasV1`) ships EXACTLY ONE formula — the dispatch's allowed
MVP example:

    formula_id = "kandoo-der-total-gross-from-net-tax", version = "1"
    total.gross = ADD(total.net, tax.amount)

No `unit_amount` formula is shipped (test-enforced).

Formula fingerprint: `formula_fingerprint` = sha256-v1 over the canonical serialization
of the declaration (id, version, output field, inputs in declared order, expression tree
in declared order) — length-prefixed chunks, reused S1 capability. The same declaration
always yields the same fingerprint; every derivation record stores the fingerprint of
the exact formula version that produced it.

## 4. Exact arithmetic semantics (normative)

- Internal representation: exact rationals (stdlib `fractions.Fraction`), constructed
  ONLY from canonical decimal STRINGS of NORMALIZED fields. A float value never exists
  anywhere in this mechanism; conversion from float is structurally impossible (the
  parser accepts only the canonical decimal grammar and returns None otherwise).
- Input gate: each resolved input's `normalized_value` must match the canonical decimal
  grammar `^-?(0|[1-9][0-9]*)(\.[0-9]+)?$` (the WP-4.1 decimal-kind output); a violation
  is a defensive failure → explicit refusal (fail-closed), never parsed leniently.
- ADD / SUB / MUL: exact by construction.
- DIV: executed ONLY when the quotient is a terminating decimal (denominator of the
  reduced rational has no prime factor other than 2 and 5). A non-terminating quotient →
  explicit refusal (`non-exact-result`) — it is NEVER rounded (D-08/WP-5.1 boundary).
- Output value: the EXACT decimal expansion of the result — no exponent notation, no
  rounding, no trailing-zero padding; trailing zeros of the exact expansion are stripped
  (value-preserving, deterministic); sign kept iff value ≠ 0. This is a declared
  canonical form, not a formatting decision: the same exact result always yields the
  same string.
- Note: ADD/SUB/MUL over finite decimals always terminate; only DIV can refuse. The
  mechanism carries the refusal path for DIV only, but the declared semantics hold for
  every op: a result that is not exactly representable as a decimal string can never be
  produced.

## 5. Outcome vocabulary (explicit, exhaustive — never silent)

Derivation-layer outcome vocabulary (mechanism level):

| Term | Kind | Meaning |
|---|---|---|
| `DERIVED` | provenance label (persisted) | D-01 label on the derivation OUTPUT: not read from the artifact; computed from evidence-bound NORMALIZED inputs by a declared, versioned formula with exact arithmetic. The ONLY provenance value this layer produces. |
| `NOT_DERIVABLE` / mechanism DEFERRED | ephemeral refusal outcome (never persisted as a value) | The formula could not execute exactly under the declared gates (input missing / input ambiguous / output present / non-exact result). No value is produced, nothing is inferred, nothing is persisted. Carries a stable reason code. |
| `UNRESOLVED` | NOT IN THIS LAYER | D-01 label owned by P5 (Validation) per the register resolution order. This mechanism never creates, assigns, infers, or resolves UNRESOLVED — structurally enforced (§9 storage gate + §13 tests). |

Semantic clarification (normative — relation to WP-4.1):
- WP-4.1 `DEFERRED` is a NORMALIZATION-LAYER FIELD status: the declared grammar could not
  safely transform one read value.
- WP-4.2 `NOT_DERIVABLE`/mechanism-DEFERRED is a DERIVATION-LAYER OUTCOME: a declared
  formula could not execute exactly over the present NORMALIZED inputs.
- Both are explicit refusals that produce NO value; NEITHER is `UNRESOLVED`; `DEFERRED ≠
  UNRESOLVED` (SPEC-WP41-NORM §4.1) extends verbatim to this layer. A derivation refusal
  NEVER invents a value, NEVER falls back to a read value, and NEVER downgrades or
  upgrades any upstream status.

Reason codes (stable, coarse): `input-missing` | `input-ambiguous` | `output-present` |
`non-exact-result`.

Input resolution gates (declared, per REG-WPR computability rule 1):
- A slot resolves to the fields of the ONE source normalization record whose
  `source_field_name` equals the slot's `field_name` AND whose status is `NORMALIZED`.
- Exactly one candidate → the input. Zero candidates → `input-missing` (DEFERRED
  fields are not candidates — a value the grammar could not transform never feeds
  arithmetic). More than one → `input-ambiguous` (no association decision is made here).
- Output-present gate: if ANY field of the source record (any status) already carries
  the `output_field_name`, the derivation is refused (`output-present`) — a derived
  value must never shadow or overwrite a read field, and must never paper over a field
  whose normalization failed.

## 6. Data model (exact field sets — structural test enforced)

`DerivationRecord` (durable header):
`derivation_id`, `normalization_id`, `extraction_id`, `document_id`, `capture_id`,
`capture_s1`, `capture_s1_algorithm_id`, `ruleset_id`, `ruleset_version`,
`formula_id`, `formula_version`, `formula_fingerprint`,
`formula_fingerprint_algorithm_id`, `output_field_name`, `output_provenance`
(always "DERIVED" — storage CHECK), `output_value` (canonical decimal string),
`input_count`, `created_at`, `record_fingerprint`, `fingerprint_algorithm_id`.

`DerivationInputRef` (durable pointer row — NO VALUE, by design):
`input_slot` (0-based declaration order), `slot_name`, `field_name`,
`source_normalization_id`, `field_seq`, `source_extraction_id`.

The pointer pattern is normative: input VALUES are never copied into this layer; the
chain is re-joined through verified reads (§10). `input_count` equals the number of
declared slots (all slots resolve on success — otherwise the derivation is refused).

## 7. Determinism (normative)

The derivation CONTENT (output_value, formula identity, input pointers) is a pure
function of (source normalization content, formula declaration). Identity scalars
(`derivation_id` uuid4 hex, `created_at`) are bookkeeping, separated from content —
SPEC §6 analog. INV-D-1:1 makes the identity unique so no mutable duplicate can drift:
a replay returns the existing record explicitly and never creates a second one.

## 8. Outcomes (exhaustive — never silent)

derive(normalization_id, formula_id, formula_version) → exactly one of:
  DerivationCompleted(record, inputs)                        — committed atomically
  DerivationAlreadyExists(derivation_id, …)                  — INV-D-1:1 replay
  DerivationFormulaNotRegistered(formula_id, formula_version)
  DerivationDeferred(reason_code, detail, normalization_id)  — NOT_DERIVABLE, nothing persisted
  DerivationSourceIntegrityFailure(normalization_id, reason) — source VOR FAILED (normalization or binding)
  DerivationSourceRefused(normalization_id, detail)          — unknown normalization / no healthy binding
  DerivationSourceUnavailable(normalization_id, issue_report)— no verdict computable (Issue-Report)
  DerivationStorageUnavailable(detail)                       — nothing recordable (zero residue)

read_derivation(derivation_id) → exactly one of:
  DerivationReadSuccess(record, inputs, verified_at)
  DerivationReadIntegrityFailure(derivation_id, reason, verified_at)   — content withheld
  DerivationReadRefused(derivation_id, detail)
  DerivationReadVerificationUnavailable(derivation_id, issue_report)

trace_derivation(derivation_id) → exactly one of:
  DerivationTraceSuccess(chain)                              — every link re-verified in this read
  DerivationTraceIntegrityFailure(link, reason)              — link ∈ derivation|normalization|extraction|binding|document
  DerivationTraceRefused(derivation_id, detail)
  DerivationTraceVerificationUnavailable(derivation_id, issue_report)

## 9. Persistence & INV-D-1:1 (same store pattern as P3/P4.1)

- OD-D1 storage: stdlib sqlite3, ONE separate embedded DB file; `synchronous=FULL`;
  idempotent schema; explicit BEGIN IMMEDIATE / COMMIT.
- OD-D2 atomic commit: record + input-ref rows in ONE transaction — zero residue on any
  failure, by construction.
- OD-D3 INV-D-1:1: at most one derivation per (normalization_id, formula_id,
  formula_version) — in-transaction check + UNIQUE index backstop. A different formula
  or version is a DIFFERENT record.
- OD-D4 ids/clock: derivation_id = uuid4 hex; single layer clock (UTC ISO-8601).
- OD-D5 integrity anchor: record_fingerprint = sha256-v1 over the canonical
  serialization of record scalars + input-ref rows in input_slot order; recomputed
  inside every read (VOR). The formula fingerprint is embedded in the covered scalars.
- OD-D6 storage gates: SQL CHECKs — `output_provenance = 'DERIVED'` (D-01: DERIVED is
  the only label producible here; UNRESOLVED can never be stored); `input_count >= 1`;
  input rows `input_slot >= 0`, `field_seq >= 0`; defensive Python-side commit refusal.
- OD-D7 no update/delete: derivations are immutable once committed; no UPDATE or DELETE
  path exists in this store.

## 10. Provenance / traceability chain (normative — pointers, verified reads)

    Derivation Record (derivation_id)
        ↓ formula_id + formula_version + formula_fingerprint (stored in the record)
    Input References (input rows: slot → source_normalization_id + field_seq + source_extraction_id)
        ↓ verified normalization read (WP-4.1 VOR)
    Normalization Record / field_seq  →  Extracted field (extraction_id + field_seq)
        ↓ verified extraction read (WP-3.1 VOR)
    Evidence Binding (WP-3.2 verified read: entry for field_seq)
        ↓ verified document read (WP-2.1 VOR)
    Document/Page/span (page_fingerprint + byte offsets; span slice decodes to the verbatim value)
        ↓ capture linkage (capture_id + capture_s1 carried and equality-checked)
    Capture S1

`trace_derivation` re-verifies EVERY link inside one call and delivers only pointers and
verdicts — it never copies source values forward and never mutates anything.

## 11. Delegated implementation details (declared per D-09)

- OD-D8 exact arithmetic engine: stdlib `fractions.Fraction` over canonical decimal
  strings (chosen over `decimal.Decimal` because Fraction arithmetic is exact without a
  precision context — REG-WPR scope sanctions "decimal string / rational"); canonical
  output formatter as declared in §4.
- OD-D9 reference registry: `ReferenceDerivationFormulasV1` ships the single declared
  MVP formula (§3) — an executability choice, NOT a business-rule decision; new
  formulas plug into the same seam as declared data with a new (id, version).
- OD-D10 engine independence: zero engine imports; the seam consumes NormalizationRecord
  fields only.

## 12. AC mapping (verification in Acceptance Register)

- AC-4.2.1 Deterministic exact derivation: formula registry declarative+versioned+
  fingerprinted; exact arithmetic (no float, no rounding, non-exact DIV refuses);
  MVP example derivable; distinct formula version = distinct derivation.
- AC-4.2.2 Provenance & traceability: pointer model (no value copies), complete chain
  derivation → … → Capture S1 machine-checkable via trace_derivation; verified reads
  end-to-end.
- AC-4.2.3 Persistence per project pattern: separate SQLite, synchronous=FULL, atomic
  commit, INV-D-1:1 explicit replay, no UPDATE/DELETE, VOR read with sha256-v1,
  restart-safe, tamper → explicit failure without content delivery.
- AC-4.2.4 Boundary: DERIVED is the only produced label (no UNRESOLVED — storage-gated);
  refusal matrix explicit and exhaustive; no unit_amount/cross-document/semantic
  derivation; no arbitrary code execution; engine independence; Frozen P1–P4.1
  untouched (full regression green).

## 13. Test expectations (behavior, not line coverage)

Mandated axes (dispatch): successful exact derivation; formula version determinism;
no-float arithmetic; missing input; ambiguous input; invalid/non-NORMALIZED input;
invalid formula; deterministic fingerprint; verify-on-read; tamper detection; idempotent
replay; different formula version → distinct derivation; complete provenance chain; no
UNRESOLVED creation; no semantic unit_amount derivation; no cross-document derivation;
formula cannot execute arbitrary code; P1–P4.1 regression remains green.
