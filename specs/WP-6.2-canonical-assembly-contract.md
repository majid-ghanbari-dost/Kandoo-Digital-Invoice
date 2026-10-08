# SPEC-WP62-CANASM — Canonical Assembly + invoice_id Issuance Contract v1.0-MVP

```text
Spec ID:      SPEC-WP62-CANASM | Version: 1.0-MVP | Date: 2026-10-08
Status:       IMPLEMENTATION CONTRACT (T-6.2.1) — produced inline per TM/PO
              implementation dispatch 2026-10-08 ("WP-6.2 — Canonical Assembly
              + invoice_id Issuance — BUILD, not design-only").
Authority:    REG-WPR Phase Index P6 row (WP-6.2 Canonical Assembly + invoice_id
              Issuance) + PO implementation dispatch 2026-10-08 is the scope of
              record; this spec converts that scope into the binding
              implementation contract.
Frozen basis: D-02 (three-identity model: Canonical Identity invoice_id is
              issued ONLY by Kandoo; the External Document Identity S2 triad and
              the gate-resolved identity_fingerprint are consumed, never
              re-decided) | D-03 (idempotency vocabulary: replay never
              re-decides/never duplicates; no new idempotency definition) | D-01
              (provenance vocabulary EXTRACTED | DERIVED | UNRESOLVED — relayed
              verbatim; this layer creates NO UNRESOLVED) | D-04 (no
              source-schema dependence in the Canonical layer) | D-06 (customer:
              auto-create forbidden; deterministic linking is WP-9.1 — the
              canonical customer reference is recorded ABSENT here) | D-08/D-09
              (no rounding here; delegated details declared OD-A1..A10) | AD-02
              (domain boundaries — assembly stays inside the Canonical Invoice
              domain) | AD-03 (no inventory effect) | AS-02 (native flow has no
              capture pipeline — this WP consumes P6.1 admissions, which only
              exist for capture-pipeline origins in the implemented pipeline) |
              AS-03 (no state redefinition or invention at WP level) | AS-04
              (Canonical Invoice field list / invariants / provenance model must
              be QUOTED, not rewritten) | AD-04/CL-1 (verbatim-vocabulary
              discipline, no paraphrase) | AS-01 (pipeline position) |
              SPEC-WP61-CANGATE (the upstream boundary — its admission records,
              verified reads, whole-chain trace and OD-G8 handover are the
              binding input contract of this WP) | SPEC-WP52-VSM |
              SPEC-WP51-VAL | SPEC-WP42-DER | SPEC-WP41-NORM | SPEC-WP32-EVB |
              WP-2.1/WP-2.2 | WP-1.1 (S1).
Baseline note (MNT-1): the physical Canonical Invoice v1 / Master Architecture
              documents are not yet committed (kandoo/baseline/ pending); the
              Decision Register + implementation dispatch are the valid
              self-contained representation (pre-registered, not a STOP cause).
              Per AS-04 the assembly therefore quotes ONLY vocabularies that
              exist in frozen sources: the D-02 identity roles, the dispatch §5
              content areas, the frozen origin enum, the D-01 provenance
              vocabulary. NO canonical field renaming, NO new state vocabulary,
              NO invented invariant: where the dispatch demands content the
              upstream contract does not carry (line structure, customer
              reference), the mechanism is a DECLARED input (OD-A4) or an
              explicit ABSENT (OD-A9) — never a guess.
Upstream:     P1 → P2 → P3 → P3.2 → P4.1 → P4.2 → P5.1 → P5.2 → P6.1 →
              **P6.2** (consumes ONLY the P6.1 Canonical Invoice ADMISSION
              record of an ACCEPTED gate decision, through the P6.1 verified
              read + the P6.1 whole-chain trace — consumed, never bypassed;
              consumes the verified WP-4.1 normalization read and the verified
              WP-4.2 derivation reads as the only sanctioned value-level fact
              paths — never triggers any upstream execution).
Downstream:   Canonical Invoice domain consumers (Digital Invoice lifecycle is
              WP-10.x — FORBIDDEN here).
```

## 1. Purpose and scope

WP-6.2 delivers ONE deterministic Canonical Assembly + invoice_id Issuance
mechanism: it consumes a P6.1 ACCEPTED admission record and builds the REAL
Canonical Invoice — canonical header anchors, canonical field inventory with
provenance pointers, declared canonical line items, and the formally issued
invoice_id — as durable, immutable, provenance-anchored, tamper-evident
records. P6.1 decided THAT data may enter the Canonical Invoice domain; P6.2
builds the invoice itself. It never re-decides canonicalization, never routes
REVIEW/REJECTED/ALREADY_CANONICALIZED admissions anywhere (they have no
admission record and no invoice is ever built for them), never resolves
identity ambiguity, never performs cross-field arithmetic, never invents a
value that is not in a verified upstream read, and never executes any upstream
layer.

P6.1 boundary (normative, dispatch §4): the ONLY valid input is the P6.1
admission of an ACCEPTED decision (INV-CI-1:1 record). For REVIEW / REJECTED /
ALREADY_CANONICALIZED no Canonical Invoice is created — the explicit outcome is
a request refusal naming the gate decision state, with zero durable residue.

In scope:
1. **Fail-closed input verification ladder** (A1..A6, §4) — verified P6.1
   admission read, consumed P6.1 whole-chain trace, ACCEPTED-only admission,
   declaration validation, verified upstream value reads, identity-anchor
   consistency.
2. **Canonical assembly engine** — pure, deterministic (§5/§6): canonical field
   inventory (EXTRACTED + DERIVED, verbatim values, provenance relayed),
   declared line items, header anchors re-joined from the admission's identity
   pointers.
3. **invoice_id Issuance** (§7) — the formal issuance workflow over the
   Kandoo-issued identity: invoice_id = the admission's canonical_invoice_id,
   consumed VERBATIM (OD-A1; D-02 third identity; OD-G8 handover). No UUID is
   minted in this layer (AST-proven) and no different identity formula is
   built.
4. **Immutable persistence** per the project store pattern (separate SQLite
   file, synchronous=FULL, atomic commit, immutable history, Verify-on-Read,
   sha256-v1 fingerprints, CHECK gates, UNIQUE backstops, no UPDATE/DELETE,
   restart-safe, tamper detection) (§8).
5. **Provenance/trace** — trace_assembled_invoice walks assembled invoice →
   admission → gate decision → P5.2 whole-chain (→ Capture S1) + re-joins EVERY
   canonical field pointer against verified reads (§9). Broken provenance fails
   closed.
6. Behavioral + structural boundary tests (dispatch §13 axes, §12).

Out of scope (FORBIDDEN — boundary of this WP): inventory mutation; KPI
mutation; accounting posting; tax filing; Holoo mutation; customer auto-create
(D-06); product fuzzy/semantic matching of ANY kind; AI matching; OCR; any
change to reconstruction, extraction, normalization, validation rules, or any
frozen layer P1–P6.1; re-deciding or re-routing canonicalization; REVIEW
queue lifecycle (P6.1 owns it); Digital Invoice issuance/lifecycle (WP-10.x);
cross-field arithmetic (totals recomputation — R1/R2 territory of P5.1);
canonical field renaming (AS-04 quote discipline); currency/tax interpretation.

## 2. Input path (normative)

The P6.1 verified read (`CanonicalizationGateService.read_canonical_invoice`,
VOR) is the ONLY sanctioned path to an admission record. The P6.1 whole-chain
trace (`trace_canonical_invoice`) is the ONLY sanctioned chain verification —
consumed, never bypassed, never re-implemented: it re-verifies the gate
decision, the P5.2 whole-chain walk (through WP-5.1 sub-walks incl. WP-4.2 down
to Capture S1) and the identity pointer re-join inside one call. The verified
WP-4.1 normalization read is the ONLY sanctioned path for canonical field
values; the verified WP-4.2 derivation reads (via `derivations_for_normalization`
+ `read_derivation`) are the ONLY sanctioned path for DERIVED values. This
layer never reads stores in parallel, never reads raw artifacts, never accepts
values from any other source, and NEVER triggers validation, projection,
derivation, or normalization itself (behaviorally proven by spy tests).

## 3. Request contract (normative)

`assemble(canonical_invoice_id, line_binding=None)`:

- `canonical_invoice_id` — REQUIRED. The admission record identifier of a P6.1
  ACCEPTED decision. Nothing else is accepted.
- `line_binding` — OPTIONAL DECLARED line structure (OD-A4): a mapping of
  integer line keys (>= 0) to role mappings `LINE_QUANTITY | LINE_UNIT_PRICE |
  LINE_TOTAL → source field name` (engine-vocabulary names relayed by
  normalization; the assembler performs NO line discovery, NO grouping, NO
  canonical field mapping — AS-04). Well-formedness (else
  `AssemblyRequestRefused`, zero residue): keys are ints >= 0; every line
  declares EXACTLY the three roles; every target is a non-empty string; the
  same source field name is never bound twice across the whole declaration
  (globally distinct); the same line key never repeats. `None` and `{}` are
  the same declaration (an invoice with zero declared lines — line_count=0,
  explicit). The declaration is DECLARED INPUT: recorded via its deterministic
  declaration_fingerprint on the issued invoice, never "corrected" by the
  assembler.

## 4. Input verification ladder (normative — fail-closed, ordered, BEFORE any assembly)

- A1  verified P6.1 admission read — unknown id → `AssemblyRequestRefused`
      (naming the gate state vocabulary as the reason no invoice can exist);
      integrity failure → `AssemblyInputIntegrityFailure`; verification
      unavailable → `AssemblyInputIntegrityFailure` (Issue Report).
- A2  P6.1 whole-chain trace (`trace_canonical_invoice`) must succeed —
      consumed, never bypassed; any broken link →
      `AssemblyInputIntegrityFailure` (no broken link silently accepted).
- A3  the linked gate decision must be ACCEPTED (enforced structurally by the
      P6.1 read — a REVIEW/REJECTED/ALREADY_CANONICALIZED decision has no
      admission; any attempt → `AssemblyRequestRefused`).
- A4  declaration validation (§3) → `AssemblyRequestRefused`.
- A5  verified WP-4.1 normalization read + verified WP-4.2 derivation reads —
      any failure → `AssemblyInputIntegrityFailure` (no assembly on unverified
      values).
- A6  identity-anchor consistency (OD-A6): the three identity pointer rows of
      the admission re-join exactly one usable NORMALIZED row each in the
      current verified read; the P6.1 OD-G4 fingerprint serialization over
      (declared_origin, the three re-joined values in role order) MUST equal
      the admission's identity_fingerprint — any mismatch →
      `AssemblyInputIntegrityFailure` (the assembled invoice's header is
      machine-checked against the identity the Gate resolved; same formula,
      never a different one).

## 5. Canonical field assembly (normative — dispatch §5, no guessing)

- C1  Canonical field inventory: EVERY usable NORMALIZED row of the verified
      read becomes ONE canonical field, in ascending field_seq order
      (deterministic; the row order of the verified read, never dict/set
      iteration). Every verified P4.2 DERIVED output for the same
      normalization_id becomes ONE canonical field, after the EXTRACTED
      fields, in (output_field_name, formula_id, formula_version,
      derivation_id) order. The canonical sequence index (canonical_seq) is
      the assembly-order position — stable, gap-free.
- C2  Values are VERBATIM: canonical_value is byte-identical to the verified
      upstream value. No default, no fallback, no coercion, no rounding, no
      arithmetic, no canonical renaming — field_name is the engine vocabulary
      relayed verbatim (AS-04 quote discipline).
- C3  Provenance is relayed VERBATIM per D-01: 'EXTRACTED' for normalization
      rows, 'DERIVED' for P4.2 outputs. UNRESOLVED is never created here
      (D-01 — P5 territory). Each canonical field carries its provenance
      POINTER: (source_normalization_id, source_field_seq) for EXTRACTED,
      (source_derivation_id) for DERIVED — re-joinable through verified reads.
- C4  Canonical header anchors (OD-A2): the three frozen D-02 identity roles
      INVOICE_NUMBER | INVOICE_DATE | INVOICE_TOTAL, re-joined from the
      admission's identity pointer rows (role → source_field_name/field_seq)
      with their canonical values — the header of the invoice. These are the
      only frozen header vocabulary; nothing else is promoted to "header" by
      guessing.
- C5  Canonical invoice metadata: origin (the admission's frozen origin,
      verbatim), identity_class/identity_source/identity_fingerprint (the
      admission's, verbatim), the full upstream anchor set (decision_id,
      domain_state_id, normalization_id, extraction_id, document_id,
      capture_id, capture_s1), field_count/line_count integrity counters, the
      declaration_fingerprint, and the issuance timestamp (bookkeeping).
- C6  Canonical customer reference (OD-A9): recorded explicitly ABSENT with a
      stable reason (`deferred-wp9.1-d06-no-deterministic-link`) — D-06
      forbids auto-create and no frozen mapping declares a customer field at
      this WP; nothing is invented.

## 6. Line assembly (normative — dispatch §6, declared structure only)

- L1  Every declared (line_key, role) resolves against the verified read:
      exactly one usable NORMALIZED row with that source_field_name → the line
      field is assembled (value verbatim + pointer); zero usable rows → the
      role is recorded ABSENT (no value invented, no default — dispatch §5);
      two or more usable rows → the WHOLE request is refused fail-closed
      (`AssemblyRequestRefused`, `declared-field-ambiguous`) — assembling
      would require picking a candidate, which is auto-resolution (forbidden;
      dispatch §6 / P6.1 §5 discipline).
- L2  A line whose three roles are ALL absent is REJECTED: it is not part of
      the invoice, and the rejection is explicit in the assembly outcome
      (`empty-line-rejected`, with the line key) — never a silent drop.
- L3  Line ordering: lines are stored and enumerated in ascending declared
      line_key order; within a line, roles in the fixed frozen order
      LINE_QUANTITY, LINE_UNIT_PRICE, LINE_TOTAL. Ordering NEVER depends on
      dict/set iteration order (sorted explicitly; AST/behavior-tested).
- L4  Every line field is traceable: (invoice_id, line_seq, role) → pointer →
      verified normalization row → … → Capture S1 (§9).
- L5  Quantities, unit prices and totals ride the lines VERBATIM from the
      verified read. Assembly performs NO arithmetic: no line sums, no
      cross-checks between line totals and the header total (that is P5.1
      R1/R2 territory, already consumed upstream — re-doing it here would be
      new semantics; OD-A7). "Totals consistency" is enforced as byte-identity
      between the assembled record and its verified sources (C2) + the A6
      identity-anchor check on the INVOICE_TOTAL header anchor.

## 7. invoice_id Issuance (normative — dispatch §7, D-02/OD-G8)

- I1  The issued invoice_id IS the admission's `canonical_invoice_id` — the
      Kandoo-issued D-02 Canonical Identity, already computed at the Gate
      (OD-G8 explicitly hands it to this WP). It is consumed VERBATIM: same
      value, no different formula, no re-derivation (dispatch §7: "if part of
      the identity was already computed in P6.1, do not build a different
      formula").
- I2  No identity is minted in this layer: zero uuid/random usage (AST-proven).
      The random-UUID-by-identity-substitution forbidden by the dispatch is
      structurally impossible here — the identifier was Kandoo-issued at the
      Gate per the frozen D-02 model and the accepted P6.1 contract.
- I3  Properties: unique (PRIMARY KEY = invoice_id; uuid4-hex collision space
      of the Gate), stable/immutable (no UPDATE/DELETE path), idempotent
      (replay returns the same invoice — I4), source-independent (the record
      carries the frozen origin enum + verified canonical values + pointers —
      D-04), collision-safe (INV-AI-1:1 + storage backstops).
- I4  Idempotent issuance / replay: a second `assemble` for the same admission
      with the SAME declaration (same declaration_fingerprint) returns
      `AssemblyAlreadyAssembled` — the existing invoice, verbatim, read-only,
      no new rows (D-03: replay never re-decides/duplicates). The same
      admission with a DIFFERENT declaration → `AssemblyRequestRefused`
      (`assembly-declaration-conflict`): no second invoice, no silent reshape
      (OD-A8). A duplicate canonicalization attempt (dispatch §8) can
      therefore never produce a second Canonical Invoice, a second line set,
      a second identity, or a second provenance chain.
- I5  Content determinism: the assembled CONTENT (values, order, counts,
      pointers) is a pure function of (the verified upstream content, the
      admission record, the declaration) — proven by rebuild tests across
      fresh stacks; ids/clock are bookkeeping (project-wide pattern).

## 8. Persistence & invariants (same store pattern as P1–P6.1)

- OD-C1 storage: stdlib sqlite3, ONE separate embedded DB file
  (`canonical-assembly.db` pattern); `synchronous=FULL`; idempotent schema;
  explicit BEGIN IMMEDIATE / COMMIT.
- OD-C2 atomic commit: the issued invoice + header anchors + canonical fields
  + line records + line fields commit in ONE transaction — zero residue on any
  failure, by construction (assembly and issuance are atomic; no
  half-assembled state ever persists).
- OD-C3 invariants: INV-AI-1:1 at most ONE issued invoice per admission
  (in-transaction check + UNIQUE backstop on admission_decision_id + PRIMARY
  KEY invoice_id); every issued invoice links exactly its admission (verified
  on every read); header anchors exactly 3 (frozen roles, UNIQUE(invoice_id,
  role)); field rows exactly field_count; line rows exactly line_count.
- OD-C4 ids/clock: NO new ids are minted (invoice_id consumed); created_at =
  single layer clock (UTC ISO-8601).
- OD-C5 integrity anchors: `record_fingerprint` = sha256-v1 over the invoice
  scalars + header anchors (role order) + canonical fields (canonical_seq
  order) + lines/line-fields (line order); `field rows` and `line rows` ride
  inside it; `declaration_fingerprint` over the canonical declaration
  serialization; all verified inside every read (VOR).
- OD-C6 storage gates: SQL CHECKs — origin vocabulary (frozen enum);
  provenance vocabulary (EXTRACTED|DERIVED); header role vocabulary; line role
  vocabulary; EXTRACTED ↔ pointer columns / DERIVED ↔ derivation pointer
  consistency; absent line fields carry NULL value; defensive Python-side
  commit refusals mirroring every CHECK.
- OD-C7 no update/delete: issued invoices, header anchors, canonical fields,
  lines and line fields are immutable once committed; no UPDATE or DELETE path
  exists in this store (AST-proven).

Outcome ladders (exhaustive — never silent), P6.1 §8 analog:
`assemble` → AssemblyCompleted | AssemblyAlreadyAssembled |
AssemblyInputIntegrityFailure | AssemblyRequestRefused |
AssemblyStorageUnavailable. `read_assembled_invoice` → …ReadSuccess |
…ReadIntegrityFailure | …ReadRefused | …ReadVerificationUnavailable.
`trace_assembled_invoice` → AssemblyTraceSuccess |
AssemblyTraceIntegrityFailure | AssemblyTraceRefused |
AssemblyTraceVerificationUnavailable.

## 9. Provenance / traceability chain (normative — pointers, verified reads)

    Canonical Invoice (issued, invoice_id)
        ↓ record_fingerprint + INV-AI-1:1
    P6.1 Canonical Invoice admission record (canonical_invoice_id)
        ↓ verified read + trace_canonical_invoice (consumed, never bypassed)
    Gate Decision Record → P5.2 Domain State → P5.1 → P4.2 (if applicable)
        → P4.1 → P3 Extraction → P3.2 Binding → Capture S1
    Canonical fields/lines → verified normalization/derivation re-joins
        (value byte-identity re-checked inside the walk)

`trace_assembled_invoice` re-verifies EVERY link inside one call: the issued
invoice (VOR), the admission + its whole-chain walk (consumed, never
bypassed), and the pointer re-join + byte-identity of every canonical field
and line field. No chain is cut or replaced; the issued invoice adds ONE head
link onto the intact P6.1 chain.

## 10. Delegated implementation details (declared per D-09)

- OD-A1 invoice_id semantics: consumed verbatim from the admission
  (§7 I1/I2) — the D-02 Canonical Identity, Kandoo-issued at the Gate
  (OD-G8); no new identifier, no different formula, no uuid/random in this
  layer.
- OD-A2 header anchors: the three D-02 identity roles (§5 C4).
- OD-A3 canonical field inventory: every usable NORMALIZED row + every
  verified P4.2 DERIVED output of the SAME normalization_id (§5 C1/C3);
  engine vocabulary relayed verbatim (AS-04); ordering declared in C1.
- OD-A4 line structure is DECLARED input (§3/§6): the assembler never
  discovers or groups lines; role labels LINE_QUANTITY | LINE_UNIT_PRICE |
  LINE_TOTAL transliterate the dispatch §5 line content areas (quantities /
  unit prices / totals) — a declared field-role vocabulary, not a new state
  vocabulary.
- OD-A5 ambiguity/absence at line fields: >=2 usable rows → request refused
  (`declared-field-ambiguous`); 0 usable → role absent (`absent-upstream`);
  all-absent line → rejected from the invoice (`empty-line-rejected`,
  explicit in the outcome) (§6 L1/L2).
- OD-A6 identity-anchor consistency check (§4 A6): P6.1's OD-G4 serialization
  quoted exactly (declared_origin + the three role-order values,
  sha256-v1) — verification, not re-decision.
- OD-A7 no arithmetic: assembly never computes across fields (§6 L5);
  byte-identity + A6 are the consistency mechanisms.
- OD-A8 replay discipline: same declaration → AlreadyAssembled; different
  declaration → refusal `assembly-declaration-conflict` (§7 I4).
- OD-A9 customer reference: explicitly ABSENT,
  `deferred-wp9.1-d06-no-deterministic-link` (§5 C6; D-06).
- OD-A10 DERIVED inclusion: only from verified P4.2 reads of the SAME
  normalization_id; labeled DERIVED verbatim (§5 C1/C3).

## 11. AC mapping (verification in Acceptance Register)

- AC-6.2.1 Boundary: only P6.1 ACCEPTED admissions are consumed through
  verified reads + the whole-chain trace; non-ACCEPTED states never produce an
  invoice; P6.1 is consumed, never bypassed (spy + row-count proofs); no
  re-decision, no re-routing.
- AC-6.2.2 Assembly: exact canonical fields (byte-identity, provenance
  relayed, deterministic order), declared lines (deterministic ordering,
  absent/empty/ambiguous handling per OD-A5), header anchors from the
  admission pointers, customer reference explicitly absent; no invented
  values (behavioral + structural).
- AC-6.2.3 Issuance: invoice_id = the Kandoo-issued admission identity,
  verbatim; unique, immutable, collision-safe; idempotent replay returns the
  same invoice; duplicate canonicalization fail-closed; atomic assembly +
  issuance (zero residue).
- AC-6.2.4 Persistence & provenance: project store pattern (SQLite FULL,
  atomic, immutable, VOR, sha256-v1, CHECK/UNIQUE gates, restart-safe,
  tamper-evident); whole-chain trace machine-checkable to Capture S1 with
  every field pointer re-joined; Frozen P1–P6.1 untouched (full regression
  green).

## 12. Test expectations (behavior, not line coverage)

Mandated axes (dispatch §13): ACCEPTED admission → invoice; non-ACCEPTED →
no invoice; exact field assembly; line assembly; deterministic line ordering;
invoice_id deterministic; invoice_id uniqueness; invoice_id replay; duplicate
admission; atomic commit; restart durability; tamper detection; immutable
invoice; immutable lines; provenance completeness; broken provenance
rejection; origin preservation; missing optional data; no invented data;
totals/invariant enforcement; multiple lines; empty/invalid line rejection;
duplicate line handling; concurrent/repeated issuance; structural proof of no
UPDATE/DELETE; structural proof that P6.1 is consumed rather than bypassed;
end-to-end Capture → … → P6.2 → Canonical Invoice.
