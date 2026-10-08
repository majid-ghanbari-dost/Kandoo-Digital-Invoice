# SPEC-WP61-CANGATE — Canonicalization Gate Contract v1.0-MVP

```text
Spec ID:      SPEC-WP61-CANGATE | Version: 1.0-MVP | Date: 2026-10-07
Status:       IMPLEMENTATION CONTRACT (T-6.1.1) — produced inline per TM/PO
              implementation dispatch 2026-10-07 ("WP-6.1 — Canonicalization
              Gate — BUILD, not design-only")
Authority:    REG-WPR Phase Index P6 row (WP-6.1 Canonicalization Gate) + PO
              implementation dispatch 2026-10-07 is the scope of record; this
              spec converts that scope into the binding implementation contract.
Frozen basis: D-02 (three-identity model: Capture Identity S1 = capture-level
              idempotency key; External Document Identity — deterministic iff
              the source yields a deterministic document id OR invoice number +
              date + total are fully extracted AND verified (S2); otherwise
              explicitly CAPTURE_SCOPED; Canonical Identity invoice_id issued
              only by Kandoo; Identity Resolution executes at the
              Canonicalization point) | D-03 (idempotency: S1 → capture
              idempotency; S2 complete+exact → definite document-level
              duplicate; incomplete/conflicting → REVIEW; CAPTURE_SCOPED → only
              capture-level dedup guaranteed, document-duplicate detection
              under ambiguity → REVIEW; no new idempotency definition) | AD-04
              (Validation output model REVIEW/REJECT; verbatim-vocabulary
              discipline, CL-1 no paraphrase) | AS-03 (no state redefinition or
              invention at WP level) | AS-04 (Canonical Invoice field list /
              invariants / provenance model must be QUOTED, not rewritten — the
              physical document is pending (MNT-1), so this WP defines ONLY the
              admission-level record the dispatch mandates and defers the full
              canonical field list to the assembly WP) | AS-01 (pipeline
              position; identity resolution at the Gate boundary) | AS-02
              (native flow has no capture pipeline) | D-01 (UNRESOLVED is
              field-level and created ONLY in P5.2 — the Gate never creates it)
              | D-08 (unresolved mismatch → REVIEW) | D-09 (delegated details
              declared) | D-04 (no source-schema dependence in the Canonical
              layer) | AD-01 (both source flows converge at Canonicalization)
              | AD-02 (domain boundaries) | AD-03 (no inventory effect) |
              SPEC-WP52-VSM (FROZEN upstream — the layer consumed here) |
              SPEC-WP51-VAL | SPEC-WP42-DER | SPEC-WP41-NORM | SPEC-WP32-EVB |
              WP-2.1/WP-2.2 | WP-1.1 (S1).
Baseline note (MNT-1): the physical Canonical Invoice v1 / Master Architecture
              documents are not yet committed (kandoo/baseline/ pending); the
              Decision Register + implementation dispatch are the valid
              self-contained representation (pre-registered, not a STOP cause).
              The origin vocabulary is taken VERBATIM from the dispatch:
              KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE — no other origin
              exists in this layer. The gate-decision vocabulary is taken
              VERBATIM from the dispatch §14 paths (accepted for canonicalization
              / rejected / review / already canonicalized + idempotent replay),
              mapped onto the frozen AD-04 routing vocabulary (REVIEW / REJECT
              semantics). "unresolved" as a dispatch path is realized as
              ROUTING: unresolved inputs route to REVIEW per D-01 — the Gate
              never creates an UNRESOLVED state (P5.2 is its only legal creator).
Upstream:     P1 → P2 → P3 → P3.2 → P4.1 → P4.2 → P5.1 → P5.2 → **P6.1**
              (consumes VERIFIED P5.2 domain-state records through the P5.2
              verified read + the P5.2 whole-chain trace; consumes the verified
              WP-4.1 normalization read as the only sanctioned value-level fact
              path — never triggers any upstream execution).
Downstream:   Canonical Invoice domain (WP-6.2 Canonical Assembly + formal
              invoice_id issuance operates on the admission record created
              here).
```

## 1. Purpose and scope

WP-6.1 delivers ONE deterministic Canonicalization Gate: the first real boundary
through which validated data ENTERS the Canonical Invoice domain. The gate
consumes a verified P5.2 domain-state record, re-verifies its complete upstream
provenance chain, resolves the External Document Identity strictly per D-02,
applies the D-03 idempotency/duplicate decision table, and — only when EVERY
frozen condition holds — creates the durable, immutable, provenance-anchored
Canonical Invoice admission record. Every other input fails closed into the
frozen routing vocabulary. The gate is a DECISION boundary and a MECHANISM: it
never resolves semantics, never matches fuzzily, never interprets tax or
currency, never mutates any business domain, and never executes any upstream
layer.

Validation ≠ Canonicalization (the dispatch's architectural distinction, kept
verbatim): a P5.2 `VALID/CLEAR` state is NECESSARY but NOT SUFFICIENT for
canonicalization — the gate independently owns identity resolution, duplicate
detection, and admission. Identity ambiguity never auto-resolves; missing
identity is never invented; a provenance failure is never best-efforted.

In scope:
1. **Gate decision engine** — pure, deterministic, declared-priority routing of
   verified P5.2 states onto the dispatch §14 decision paths (§4).
2. **Identity Resolution** — External Document Identity exactly per D-02's
   deterministic paths; CAPTURE_SCOPED otherwise; declared identity-field
   binding; exact matching only (§5).
3. **Canonical Invoice admission record** — source-independent, provenance-
   anchored, origin-bearing, deterministic, immutable (§6). Full canonical
   field/line ASSEMBLY and formal invoice_id issuance workflow remain WP-6.2.
4. **Gate REVIEW queue** — durable, deterministic, traceable, idempotent,
   reason- and provenance-carrying, append-only hash-chained lifecycle (§7);
   holds CANONICALIZATION-stage uncertainty (identity nondeterminism), exactly
   the uncertainty class P5.2's queue contract anticipated.
5. **Persistence** per the project store pattern (separate SQLite file,
   synchronous=FULL, atomic commit, immutable history, deterministic
   fingerprints, Verify-on-Read, no UPDATE/DELETE, tamper detection) (§8).
6. **Provenance preservation** — full-chain traceability from the Canonical
   Invoice admission record to Capture S1 through the P5.2 whole-chain walk
   (§9); no broken link is ever silently accepted.
7. Behavioral + structural boundary tests (refusal matrix, determinism, tamper,
   restart, frozen-layer regression, AST probes).

Out of scope (FORBIDDEN — boundary of this WP): inventory mutation; Sale
creation outside the frozen native flow; KPI mutation; customer auto-create;
product fuzzy/semantic matching; product matching of ANY kind (the identity
resolved here is DOCUMENT identity per D-02/D-03, not product/customer
identity); tax interpretation; currency conversion; accounting interpretation;
AI-based identity resolution; invoice OCR; any change to reconstruction,
extraction, normalization, validation rules, or any frozen layer P1–P5.2;
Canonical Assembly of line/field content (WP-6.2); formal invoice_id issuance
workflow (WP-6.2); resolving or auto-closing REVIEW items semantically;
re-running, re-projecting, or mutating P5.2 states.

## 2. Input path (normative)

The P5.2 verified read (`read_domain_state`, VOR) is the ONLY sanctioned path
to a domain-state record. The P5.2 whole-chain trace (`trace_domain_state`) is
the ONLY sanctioned chain verification — consumed, never bypassed, never
re-implemented: it re-verifies every link through P5.1's whole-chain sub-walks
(P4.2 sub-chains consumed, never bypassed) down to Capture S1 inside one call.
The verified WP-4.1 normalization read is the ONLY sanctioned path for identity
field values (counts + canonical values of NORMALIZED rows). The gate never
reads stores in parallel, never reads raw artifacts, never accepts values from
any other source, and NEVER triggers validation, projection, derivation, or
normalization itself (behaviorally proven by spy tests).

Scope of one gate request = ONE P5.2 domain-state record + its declared request
(declared_origin, optional identity_field_binding). The request is immutable
input: recorded verbatim on the decision, never "corrected" by the gate.

## 3. Request contract (normative)

`canonicalize(domain_state_id, declared_origin, identity_field_binding=None)`:

- `declared_origin` — REQUIRED, one of the frozen origins VERBATIM:
  `KANDOO_CAPTURE`-family values only from the dispatch set
  `HOLOO_CAPTURE | OTHER_POS_CAPTURE` may ride a capture-pipeline request.
  `KANDOO_SALE` is the native-flow origin (AS-02: Product → Sale → Invoice —
  no capture, no P5.2 state); a KANDOO_SALE declaration on a P5.2-sourced
  request is a category error and is REFUSED
  (`origin-native-flow-not-consumable-here`, declared delegated detail OD-G7 —
  fail-closed, auditable; AD-01's two-flow convergence is realized at the
  Canonicalization phase, the native path entering through its own flow).
  Any other value is refused (`origin-outside-frozen-vocabulary`).
- `identity_field_binding` — OPTIONAL declared mapping from the THREE frozen
  D-02 identity roles `INVOICE_NUMBER | INVOICE_DATE | INVOICE_TOTAL` to source
  field names (the engine-vocabulary names relayed by normalization; the gate
  performs NO canonical field mapping — that is assembly-layer work under
  AS-04's quote discipline). Either ALL THREE roles are bound to distinct field
  names, or the binding is absent/None. Partial bindings, unknown roles,
  duplicate targets, or non-string targets are REFUSED (`binding-malformed`).
  The binding is DECLARED INPUT, recorded verbatim on the decision — the gate
  never guesses which fields carry identity.

## 4. Gate decision table (normative — deterministic, declared priority, first match)

Input verification (fail-closed, ordered, BEFORE any decision; failures are
explicit refusal outcomes with ZERO durable residue — the P5.2 refusal pattern):

- V1  verified read of the domain state — integrity failure →
      `CanonicalizationInputIntegrityFailure` (no decision is ever cut on
      unverified input, even if a prior decision exists).
- V2  `trace_domain_state` must succeed — any broken link →
      `CanonicalizationInputIntegrityFailure` (no broken link silently
      accepted).
- V3  declared origin validation (§3) → `CanonicalizationRequestRefused`.
- V4  binding validation (§3) → `CanonicalizationRequestRefused`.

Decision routes (over the VERIFIED state; stable `decision_reason` codes):

| # | Condition | Decision | Reason | Frozen anchor |
|---|---|---|---|---|
| G0 | a durable gate decision already exists for this domain_state_id | (replay) return the existing decision verbatim — read-only, no new rows | — | D-03 idempotency (replay never re-decides); P5.2 INV-S-1:1 analog |
| G1 | disposition `REJECT` (state INVALID, decisive reasons) | `REJECTED` | `upstream-decisive-invalid` | AD-04 REJECT (decisive, non-recoverable); OD-S9 split |
| G2 | disposition `REVIEW` (INVALID-tolerance / UNRESOLVED / DEFERRED) | `REVIEW` | the P5.2 `state_reason` relayed VERBATIM (`d08-mismatch-review` \| `d01-unresolved-review` \| `validation-deferred-review`) | D-08, D-01, D-03-ambiguous; upstream uncertainty already held in the P5.2 queue — the gate decision REFERENCES it (`upstream_review_id`), never duplicates it |
| G3 | state `VALID/CLEAR` + identity resolution → CAPTURE_SCOPED | `REVIEW` | `d03-incomplete-document-identity` (a bound field has 0 usable NORMALIZED rows) \| `d03-conflicting-document-identity` (a bound field has ≥2) \| `d03-document-identity-undetermined` (no binding declared) | D-03 (ناقص/متعارض → REVIEW; CAPTURE_SCOPED → document-dedup ambiguity → REVIEW); dispatch §6 (multiple candidates → DO NOT AUTO-RESOLVE) |
| G4 | state `VALID/CLEAR` + identity DETERMINISTIC + a canonical invoice already exists for the same `capture_s1` | `ALREADY_CANONICALIZED` | `d02-capture-idempotent-replay` | D-02 (S1 = the capture-level idempotency key); D-03 (S1 → capture idempotency) |
| G5 | state `VALID/CLEAR` + identity DETERMINISTIC + a canonical invoice exists with the same identity fingerprint from a DIFFERENT capture | `REJECTED` | `d03-definite-document-duplicate` | D-03 (S2 complete + exact → definite document-level duplicate — decisive, not uncertainty) |
| G6 | state `VALID/CLEAR` + identity DETERMINISTIC + no duplicate | `ACCEPTED` | `all-frozen-conditions-met` | Dispatch §4.5 (create the Canonical Invoice only when every frozen condition holds) |

Every decision row durably records: the verified input anchors (domain_state_id
… capture_s1), the declared request verbatim, the route, reason, an audit
detail (identity resolution metadata: per-role candidate counts and bound field
names — declarations and counts, never pipeline values), the upstream review
pointer when G2, and the canonical_invoice_id when G6.

Decision vocabulary (dispatch §14 paths, frozen-routing semantics):
`ACCEPTED | REJECTED | REVIEW | ALREADY_CANONICALIZED`. No other decision
exists. UNRESOLVED is NOT a gate decision: the gate never creates the D-01
label (P5.2 is its only legal creator); unresolved inputs route G2.

## 5. Identity Resolution (normative — D-02/D-03 mechanics, exact only)

Pure, deterministic, value-honest: the resolver sees ONLY the verified
normalization read + the declared binding, and emits metadata + fingerprints —
never stores raw pipeline values (pointer discipline, P5.2 §6 analog).

- I1  For each bound role, scan the verified normalization read for rows with
      the bound source_field_name and status NORMALIZED and a non-empty
      normalized_value (empty strings are not usable identity values — declared
      detail OD-G2). Count candidates: 0 → incomplete; ≥2 → conflicting
      (G3); exactly 1 → usable.
- I2  All three roles usable → identity class `DETERMINISTIC`, source
      `S2_EXTRACTED_VERIFIED`: D-02's second deterministic path ("شماره فاکتور
      + تاریخ + جمع اگر کاملاً استخراج و تأیید شده باشند") — fully extracted
      (single NORMALIZED row per role in the verified read) AND verified (the
      P5.2 state over this normalization is VALID/CLEAR — G3 is reachable only
      there). D-02's first deterministic path (adapter-issued document id) has
      NO producer in the implemented pipeline (the D-04 adapter is post-freeze
      work): it is RESERVED, not implemented, declared here — no adapter
      identifier is invented or consumed.
- I3  Otherwise → `CAPTURE_SCOPED` (D-02's explicit third class) → G3 REVIEW.
- I4  Identity fingerprint (`identity_fingerprint`, sha256-v1): the canonical
      serialization of (declared_origin, the three canonical values in role
      order). The declared origin is the source-system scope component (D-02:
      identity is identity IN THE SOURCE SYSTEM; two captures from different
      declared origins are never compared). Exact equality of fingerprints is
      the ONLY duplicate comparison — exact matching exclusively; fuzzy,
      heuristic, similarity, or AI matching of any kind is absent (AST-proven).
- I5  The S2 tuple is NOT stored in plaintext: the gate stores the fingerprint
      + per-role POINTER rows (role, bound field name, normalization_id,
      field_seq) — the values re-join through verified reads. The tuple
      fingerprint is the S2 analog of Capture S1: a deterministic content
      anchor, exactly the D-02/D-03 idempotency vocabulary.

## 6. Canonical Invoice admission record (normative)

Created ONLY inside the G6 transaction, ONLY by the gate service (the store
exposes no separate invoice-creation path — structural test enforced; INV-CI-1:1:
exactly one canonical invoice per ACCEPTED decision, and every canonical invoice
has exactly one ACCEPTED decision). Record:

`canonical_invoice_id` (uuid4 hex — Kandoo-issued per D-02; the WP-6.2
formal issuance workflow operates on this record), `decision_id` (UNIQUE),
`domain_state_id`, `normalization_id`, `extraction_id`, `document_id`,
`capture_id`, `capture_s1` (UNIQUE backstop of G4), `capture_s1_algorithm_id`,
`origin` (CHECK ∈ the three frozen origins), `identity_class`
(CHECK = 'DETERMINISTIC' — an admission without deterministic identity is
unreachable), `identity_source` ('S2_EXTRACTED_VERIFIED'),
`identity_fingerprint` (UNIQUE backstop of G5), `created_at`,
`record_fingerprint` (sha256-v1 over record scalars + identity pointer rows in
role order), `fingerprint_algorithm_id`.

Properties (dispatch §7, all enforced + tested): source-independent (no source
schema columns — origin enum + pointers only, D-04); provenance-bearing (full
upstream anchor set + §9 trace); correct origin (declared, frozen enum, never
invented); upstream references preserved (pointers, re-joined via verified
reads); deterministic (content = pure function of verified inputs + declared
request; ids/clock = bookkeeping, P5.2 §7 analog); immutable/auditable (no
UPDATE/DELETE path exists — OD-S7 analog); built ONLY from verified upstream
data (V1/V2 verification precedes every admission).

## 7. Gate REVIEW queue (normative — a real mechanism, not a list)

Durable queue in the P6.1 store (separate tables, same transactional pattern as
P5.2 §5). EXACTLY one gate review item per `REVIEW` decision (INV-GR-1:1 —
in-transaction + UNIQUE backstop); ACCEPTED / REJECTED /
ALREADY_CANONICALIZED never create items. Every item carries identity anchors
(review_id, decision_id, domain_state_id, normalization_id, extraction_id,
document_id, capture_id, capture_s1), the decision_reason + review_detail
(identity resolution metadata / the verbatim-relayed upstream reason + the
upstream_review_id reference when G2), lifecycle fields, own fingerprint.

Lifecycle: append-only, hash-chained event rows (`ANNOTATE`, `CLOSE`) with
seq-contiguous per item, `prev_event_fingerprint` chaining, opaque actor,
terminal single CLOSE (partial-unique backstop + in-transaction check), status
derived from history on every read — identical mechanics to the P5.2 queue.
The queue is NOT a semantic resolver: it never resolves identity, never
auto-admits, never mutates upstream layers, never infers. Closing is an
explicit external act RECORDED here. Every append is fail-closed: the item AND
its parent decision AND the parent's P5.2 state must verify — broken
provenance freezes the item.

## 8. Persistence & invariants (same store pattern as P1–P5.2)

- OD-C1 storage: stdlib sqlite3, ONE separate embedded DB file
  (`canonicalization-gate.db` pattern); `synchronous=FULL`; idempotent schema;
  explicit BEGIN IMMEDIATE / COMMIT.
- OD-C2 atomic commit: decision + canonical invoice + identity pointers + gate
  review item (if REVIEW) in ONE transaction — zero residue on any failure, by
  construction. Events commit in their own single-purpose transactions.
- OD-C3 invariants: INV-D-1:1 at most one gate decision per domain_state_id
  (in-transaction check + UNIQUE backstop); INV-CI-1:1 one canonical invoice
  per ACCEPTED decision (UNIQUE backstop on decision_id); capture-level
  idempotency UNIQUE(capture_s1) on canonical invoices; document-level
  UNIQUE(identity_fingerprint) backstop behind the G5 check; INV-GR-1:1 one
  gate review item per REVIEW decision (UNIQUE backstop).
- OD-C4 ids/clock: decision_id / canonical_invoice_id / review_id / event_id =
  uuid4 hex; single layer clock (UTC ISO-8601).
- OD-C5 integrity anchors: `decision_fingerprint` = sha256-v1 over decision
  scalars; `invoice_fingerprint` over invoice scalars + pointer rows (role
  order); `item_fingerprint` over item scalars; `event_fingerprint` over event
  scalars + chain link; all verified inside every read (VOR).
- OD-C6 storage gates: SQL CHECKs — decision vocabulary; origin vocabulary;
  identity_class vocabulary; ACCEPTED ↔ canonical_invoice_id NOT NULL; non-
  ACCEPTED → NULL; admission rows DETERMINISTIC-only; event_type vocabulary;
  partial UNIQUE single CLOSE; defensive Python-side commit refusals mirroring
  every CHECK.
- OD-C7 no update/delete: decisions, canonical invoices, pointer rows, review
  items and events are immutable once committed; no UPDATE or DELETE path
  exists in this store (AST-proven).

Outcome ladders (exhaustive — never silent), P5.2 §8 analog:
`canonicalize` → CanonicalizationAccepted | CanonicalizationRejected |
CanonicalizationRoutedToReview | CanonicalizationAlreadyCanonicalized |
CanonicalizationAlreadyDecided | CanonicalizationInputIntegrityFailure |
CanonicalizationRequestRefused | CanonicalizationStorageUnavailable.
`read_canonical_invoice` / `read_gate_decision` / `read_gate_review_item` →
…ReadSuccess | …ReadIntegrityFailure | …ReadRefused |
…ReadVerificationUnavailable. `append_gate_review_event` → GateEventAppended |
GateEventRefused | GateEventUnavailable. `trace_canonical_invoice` →
CanonicalInvoiceTraceSuccess | CanonicalInvoiceTraceIntegrityFailure |
CanonicalInvoiceTraceRefused | CanonicalInvoiceTraceVerificationUnavailable.

## 9. Provenance / traceability chain (normative — pointers, verified reads)

    Canonical Invoice admission record (canonical_invoice_id)
        ↓ decision_fingerprint + INV-CI-1:1
    Gate Decision Record (decision_id)
        ↓ domain_state_id + verified P5.2 read
    P5.2 Domain State Record — walked through trace_domain_state:
        validation refs → WP-5.1 whole-chain sub-walks (incl. WP-4.2 DERIVED
        sub-chains) → normalization → extraction → binding →
        Document/Page/span → Capture S1
    Identity pointer rows → verified normalization read re-join (role order)

`trace_canonical_invoice` re-verifies EVERY link inside one call: the gate
record, the decision, the P5.2 whole-chain walk (consumed, never bypassed), and
the identity pointer re-join. No chain is cut or replaced; the admission record
adds ONE head link onto the intact P5.2 chain.

## 10. Delegated implementation details (declared per D-09)

- OD-G1 decision-route priority: the fixed G0…G6 order (§4) — the frozen
  sources anchor each route but do not order co-occurring conditions; the fixed
  order is deterministic and auditable.
- OD-G2 usable identity value: a NORMALIZED row with a non-empty
  normalized_value; empty strings are not usable identity values.
- OD-G3 verification criterion for S2: single NORMALIZED row per bound role in
  the verified WP-4.1 read + the P5.2 state VALID/CLEAR over that
  normalization.
- OD-G4 identity fingerprint scope: declared_origin + the three canonical
  values in role order (§5 I4).
- OD-G5 adapter-document-id path RESERVED (D-02's first deterministic path):
  no producer exists in the implemented pipeline (D-04 post-freeze); nothing
  is invented to fill it.
- OD-G6 origin refusal for KANDOO_SALE on P5.2-sourced requests (§3; AS-02
  category error, fail-closed).
- OD-G7 KANDOO_SALE refusal reason code: `origin-native-flow-not-consumable-
  here`.
- OD-G8 admission-record id semantics: canonical_invoice_id is Kandoo-issued
  (D-02 third identity); the WP-6.2 formal issuance workflow + canonical
  assembly build upon this record; the AS-04 canonical FIELD LIST transfer
  happens there, under the quote discipline, when the baseline document is
  committed.
- OD-G9 G2 review referencing: the gate decision stores upstream_review_id and
  never creates a duplicate queue item for upstream-held uncertainty; the gate
  queue holds canonicalization-stage uncertainty (G3) and the audit decision
  rows for all routes.
- OD-G10 empty-binding equivalence: identity_field_binding=None and {} are the
  same declaration (no document identity attempted → G3
  d03-document-identity-undetermined).

## 11. AC mapping (verification in Acceptance Register)

- AC-6.1.1 Gate: deterministic, declared-priority, fail-closed routing of
  verified P5.2 states onto the dispatch §14 paths; every decision explicit,
  auditable, testable; no state or decision invented outside the declared
  vocabulary; VALID/CLEAR is necessary but not sufficient (independent
  identity + duplicate admission control).
- AC-6.1.2 Identity: D-02/D-03 mechanics exactly — S2 deterministic path only,
  CAPTURE_SCOPED explicit, incomplete/conflicting/undetermined → REVIEW,
  multiple candidates never auto-resolved, exact matching only, no fuzzy/
  heuristic/AI matching, adapter path reserved-not-invented.
- AC-6.1.3 Canonical Invoice: created only inside the gate transaction, only
  from verified inputs, source-independent, origin-bearing (frozen enum),
  provenance-anchored, deterministic fingerprint, immutable, idempotent
  (capture-level S1 replay + document-level exact duplicate rejection).
- AC-6.1.4 Boundary & integration: full provenance chain machine-checkable to
  Capture S1; no downstream mutation of any business domain; no upstream
  execution; Frozen P1–P5.2 untouched (full regression green).

## 12. Test expectations (behavior, not line coverage)

Mandated axes (dispatch §15): VALID/CLEAR acceptance; INVALID rejection;
DEFERRED handling; UNRESOLVED handling; identity exact-match; identity
no-match→incomplete; identity multiple-candidate; forbidden fuzzy matching;
provenance verification; broken upstream chain; P4.2 derived provenance; tamper
detection; duplicate/idempotent replay; atomicity; restart durability; origin
preservation; canonical invoice immutability; deterministic fingerprint;
forbidden downstream mutations; frozen-layer protection; malformed input;
boundary cases; end-to-end capture → canonicalization; no accidental P5.2
execution/mutation; structural AST checks; and: no canonicalization succeeds
without the Gate.
