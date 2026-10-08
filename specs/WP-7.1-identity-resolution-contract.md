# SPEC-WP71-IDRES — Identity Resolution Contract v1.0-MVP

```text
Spec ID:      SPEC-WP71-IDRES | Version: 1.0-MVP | Date: 2026-10-08
Status:       IMPLEMENTATION CONTRACT (T-7.1.1) — produced inline per TM/PO
              implementation dispatch 2026-10-08 ("WP-7.1 — Identity
              Resolution — S1 / S2 / CAPTURE_SCOPED — BUILD, not design-only")
Authority:    REG-WPR Phase Index P7 row (WP-7.1 Identity Resolution
              S1/S2/CAPTURE_SCOPED) + PO implementation dispatch 2026-10-08 is
              the scope of record; this spec converts that scope into the
              binding implementation contract.
Frozen basis: D-02 (three-identity model VERBATIM: (1) Capture Identity
              S1 = capture_content_fingerprint = the capture-level idempotency
              key; (2) External Document Identity — deterministic iff fully
              extracted AND verified invoice number + date + total (S2),
              otherwise explicitly CAPTURE_SCOPED; (3) Canonical Identity
              invoice_id issued ONLY by Kandoo — P6.1/P6.2; Identity Resolution
              executes at the Canonicalization point) | D-03 (idempotency:
              S1 → capture idempotency; S2 complete+exact → definite
              document-level duplicate; incomplete/conflicting → REVIEW;
              CAPTURE_SCOPED = only capture-level deduplication guaranteed;
              NO new idempotency definition) | D-01 (UNRESOLVED is field-level,
              created ONLY in P5.2 — this layer never creates it) | D-04 (no
              source-schema dependence) | D-08 | D-09 (delegated details
              declared) | AD-01 | AD-02 | AD-04/CL-1 (verbatim vocabulary, no
              paraphrase) | AS-01 (pipeline position — identity resolution at
              the Canonicalization Gate boundary, MRR CL-3) | AS-02 (native
              flow has no capture pipeline) | AS-03 (no state redefinition or
              invention) | AS-04 (quote Frozen sources, never rewrite) |
              SPEC-WP61-CANGATE (the identity foundation this WP REUSES —
              resolve_identity / validate_binding / the OD-G4 fingerprint —
              consumed VERBATIM, never forked, never re-formulated) |
              SPEC-WP52-VSM | SPEC-WP41-NORM | WP-1.1 (S1 sha256-v1).
Baseline note (MNT-1): the physical Canonical Invoice v1 / Master Architecture
              documents remain uncommitted (kandoo/baseline/ pending); the
              Decision Register + the dispatch are the valid self-contained
              representation (pre-registered, not a STOP cause).
Upstream:     P1 → P2 → P3 → P3.2 → P4.1 → P4.2 → P5.1 → P5.2 → (P6.1/P6.2
              own Canonicalization/Assembly) — this WP consumes VERIFIED P5.2
              domain-state records through the P5.2 verified read + the P5.2
              whole-chain trace, and the verified WP-4.1 normalization read as
              the only sanctioned value-level fact path. It NEVER triggers any
              upstream execution and NEVER re-decides canonicalization.
Downstream:   WP-7.2 (Reprint & Duplicate Flows) and any future consumer of
              durable identity resolutions; the Gate (P6.1) remains the sole
              canonicalization authority — this WP strengthens and
              operationalizes the identity foundation, it does not bypass or
              replace it.
```

## 1. Purpose and scope

WP-7.1 delivers ONE deterministic Identity Resolution service: the durable,
operational identity layer for documents entering the canonical pipeline. It
makes the frozen D-02 identity model executable as a first-class concern with
its own immutable persistence: for every request it re-verifies the complete
upstream provenance chain, recognizes capture-level replays (S1 idempotency),
resolves the External Document Identity exactly per D-02 (S2 triad or explicit
CAPTURE_SCOPED), detects definite document duplicates exactly (D-03), and
records every outcome as an immutable, provenance-anchored, fingerprint-locked
resolution record. It never guesses, never matches fuzzily, never resolves
ambiguity automatically, never mutates any upstream layer, and never executes
any upstream code.

Relationship to P6.1 (normative): the exact S2 identity machinery — the frozen
triad criterion, the OD-G4 fingerprint serialization (sha256-v1 over
declared_origin + the three canonical values in role order), and the binding
validation — is REUSED from `canonicalization.identity` VERBATIM. This WP
defines no second formula, no fork, no parallel vocabulary. What it adds is
the durable operational layer P6.1 deliberately did not own: standalone
identity resolution records with S1-replay recognition, exact-duplicate
observations, and preserved candidate evidence for the Gate/review concern.

In scope:
1. **Resolution states** — explicit, deterministic distinction of S1 / S2 /
   CAPTURE_SCOPED (§5).
2. **Resolver (pure)** — binding-declaration canonicalization + the state-gated
   delegation to the frozen P6.1 primitive (§4/§5).
3. **Duplicate handling** — D-03 definite-duplicate detection by exact
   fingerprint equality across different captures, recorded as an explicit
   append-only observation; never a second document identity (§6).
4. **Persistence** per the project store pattern (separate SQLite file,
   synchronous=FULL, atomic commit, immutable records, Verify-on-Read,
   sha256-v1, CHECK + UNIQUE gates, no UPDATE/DELETE, tamper detection,
   restart safety) (§8).
5. **Provenance preservation** — every resolution carries the verified anchor
   set down to Capture S1 through the P5.2 whole-chain walk, consumed never
   bypassed (§9).
6. Behavioral + structural boundary tests (idempotency matrix A–F, adversarial
   matrix, concurrency, AST probes, frozen-layer protection).

Out of scope (FORBIDDEN — dispatch §14): Product Recognition; Customer
auto-creation; Customer fuzzy matching; OCR; AI matching; inventory; sales;
Digital Invoice lifecycle; Holoo parser; Cloud synchronization; UI; mobile
application; any change to any frozen layer P1–P6.2 (P6.1's gate behavior is
untouched — purely additive WP); canonicalization re-decision; Canonical
Assembly; invoice_id minting; resolving or auto-closing REVIEW items;
semantic matching of ANY kind; new idempotency definitions (D-03).

## 2. Input path (normative)

The P5.2 verified read (`read_domain_state`, VOR) is the ONLY sanctioned path
to a domain-state record. The P5.2 whole-chain trace (`trace_domain_state`) is
the ONLY sanctioned chain verification — consumed, never bypassed, never
re-implemented: it re-verifies every link (P5.1 whole-chain sub-walks incl.
P4.2 DERIVED sub-chains) down to Capture S1 inside one call. The verified
WP-4.1 normalization read (`read_normalization`, VOR) is the ONLY sanctioned
path for identity field values — consumed ONLY when the state is VALID/CLEAR
(values of a non-VALID state are not verified and are never even read). The
service never reads stores in parallel, never reads raw artifacts, never
accepts values from any other source, and NEVER triggers validation,
projection, derivation, normalization, binding, extraction, reconstruction,
or ingestion itself (behaviorally spy-proven).

Scope of one resolution request = ONE P5.2 domain-state record + its declared
request (declared_origin, optional identity_field_binding). The request is
immutable input: recorded verbatim (origin; binding as its deterministic
declaration fingerprint), never "corrected" by this layer.

## 3. Request contract (normative)

`resolve(domain_state_id, declared_origin, identity_field_binding=None)`:

- `declared_origin` — REQUIRED, one of the frozen origins VERBATIM:
  `KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE`. Only capture-pipeline
  origins (`HOLOO_CAPTURE | OTHER_POS_CAPTURE`) may ride a P5.2-sourced
  request; `KANDOO_SALE` is the native-flow origin (AS-02: no capture, no
  P5.2 state) and is REFUSED (`origin-native-flow-not-consumable-here` —
  same category-error discipline as P6.1 V3/OD-G6). Any other value is
  refused (`origin-outside-frozen-vocabulary`).
- `identity_field_binding` — OPTIONAL declared mapping from the THREE frozen
  D-02 roles `INVOICE_NUMBER | INVOICE_DATE | INVOICE_TOTAL` to distinct
  source field names. Validation is REUSED from P6.1 `validate_binding`
  verbatim: either ALL THREE roles bound to distinct names, or absent/None.
  Partial bindings, unknown roles, duplicate targets, non-string targets →
  REFUSED (`binding-malformed`). `None` and `{}` are the same declaration
  (OD-G10 analog). The declaration is fingerprinted (OD-IR-B) and the
  fingerprint — never the raw mapping — rides the durable record.

## 4. Verification ladder + resolution table (normative — fail-closed, ordered)

Input verification precedes EVERY resolution; failures are explicit outcomes
with ZERO durable residue:

- V1  verified read of the domain state — refusal → `IdentityRequestRefused`;
      integrity/verification failure → `IdentityInputIntegrityFailure` (no
      resolution is ever cut on unverified input, even if a prior resolution
      exists).
- V2  `trace_domain_state` must succeed — any broken link →
      `IdentityInputIntegrityFailure` (broken provenance FAIL CLOSED; no
      resolution on an unverifiable chain).
- V3  declared origin validation (§3) → `IdentityRequestRefused`.
- V4  binding validation (§3) → `IdentityRequestRefused`.

Resolution routes (over the VERIFIED state; stable codes):

| # | Condition | Outcome | Detail | Frozen anchor |
|---|---|---|---|---|
| R0 | a durable resolution already exists for this `capture_s1` | `IdentityReplay` — the existing resolution returned verbatim, read-only, after its own VOR verification; zero new rows | declaration match = same `declared_origin` AND same `binding_declaration_fingerprint`; a replay with a drifted declaration → `IdentityRequestRefused` (`replay-declaration-drift`) — never a silent reshape; a tampered existing record → `IdentityInputIntegrityFailure` (never replay from a tampered row) | D-02 (S1 = capture-level idempotency key); D-03 (S1 → capture idempotency); dispatch §7 S1 ("no second identity may be created") |
| R1a | state `VALID/CLEAR` | S2 attempt: verified WP-4.1 read → the frozen P6.1 primitive `resolve_identity` → scope `S2` (fingerprint + source `S2_EXTRACTED_VERIFIED`) or `CAPTURE_SCOPED` (`d03-incomplete-document-identity` \| `d03-conflicting-document-identity` \| `d03-document-identity-undetermined`) | the only value consumption path; ≥2 candidates in a role → CAPTURE_SCOPED with the candidate evidence PRESERVED — never auto-selected (dispatch §8; D-01: ambiguity is a Gate/review concern, never UNRESOLVED) | D-02 second deterministic path (OD-G3 criterion); dispatch §5 |
| R1b | state NOT VALID/CLEAR (INVALID/REJECT, INVALID/REVIEW, DEFERRED/REVIEW, UNRESOLVED/REVIEW) | scope `CAPTURE_SCOPED` (`s2-not-attempted-state-not-valid`) — recorded WITHOUT any value consumption (no normalization read is even performed) | the evidence available in this capture does not establish a verified S2 identity — exactly the dispatch §7 CAPTURE_SCOPED definition; NOT a guess, NOT an UNRESOLVED (D-01) | D-02 (identity values must be fully extracted AND verified); OD-IR-C |
| R2 | R1a produced a fingerprint AND an earlier resolution from a DIFFERENT capture carries the same fingerprint | the new resolution commits WITH an append-only `identity_duplicate_observations` row referencing the original resolution — `IdentityDefiniteDuplicate` | one document identity; the later capture never becomes a second one; the original = earliest (created_at, resolution_id) among same-fingerprint resolutions from other captures (OD-IR-E); exact fingerprint equality is the ONLY comparison | D-03 (S2 complete + exact → definite document-level duplicate); dispatch §7 S2 |
| R3 | otherwise | commit the resolution (+ role candidate rows) atomically → `IdentityResolutionRecorded` | resolution + role rows + observation (iff R2) in ONE transaction; UNIQUE(capture_s1) backstop; in-transaction duplicate → replay mapping (concurrency-safe) | D-02/D-03; project store pattern |

## 5. Resolution states (normative — the S1 / S2 / CAPTURE_SCOPED distinction)

The durable record carries all D-02 identities explicitly:

- **S1 — Capture Identity** (always present): `capture_s1` +
  `capture_s1_algorithm_id`, taken ONLY from the verified P5.2 state record
  whose whole chain was re-verified (V2) down to Capture S1. S1 is the
  idempotency key of this layer: UNIQUE(capture_s1) — one capture artifact,
  ONE durable resolution, ever (R0). The S1 behavior is the replay
  recognition of R0 (`IdentityReplay`).
- **S2 — External Document Identity, established**: `identity_scope='S2'` +
  `identity_fingerprint` (the P6.1 OD-G4 sha256-v1 serialization — REUSED,
  not reformulated) + `identity_source='S2_EXTRACTED_VERIFIED'` + exactly
  three role candidate rows each with `candidate_count=1` and
  `resolved_field_seq` set (the pointer evidence re-joinable through the
  verified WP-4.1 read). Established ONLY when the frozen triad is fully
  extracted (exactly one usable NORMALIZED row per bound role) AND verified
  (VALID/CLEAR state) — OD-G3 verbatim.
- **CAPTURE_SCOPED — no established document identity**:
  `identity_scope='CAPTURE_SCOPED'` + EMPTY fingerprint + EMPTY source + a
  stable `scope_reason` (`d03-incomplete-document-identity` |
  `d03-conflicting-document-identity` | `d03-document-identity-undetermined`
  | `s2-not-attempted-state-not-valid`). CAPTURE_SCOPED is NOT permission to
  guess: no value, candidate, or default is ever invented to fill a role
  (dispatch §7). Per D-03 it means exactly "only capture-level deduplication
  is guaranteed"; document-duplicate handling under ambiguity remains a
  Canonicalization Gate / review concern — the candidate evidence rows
  preserve WHAT was seen (counts + pointers), never a selection.

Vocabulary discipline (AS-03/AD-04/CL-1 + dispatch §15): the identity scopes
are exactly `S2 | CAPTURE_SCOPED`; `S1` is the capture leg itself
(`capture_s1`) and its R0 idempotency behavior — no fourth scope, no synonym
status, no renaming. `UNRESOLVED` is NEVER created here (D-01 — P5.2 is its
only legal creator). The Canonical Identity (`invoice_id`) is NOT minted,
held, or referenced by this layer (OD-IR-I — P6.1/P6.2 own it).

## 6. Duplicate handling (normative — D-03, exact only)

A definite document duplicate exists ONLY when two DIFFERENT captures resolve
to the SAME `identity_fingerprint` (exact equality of the frozen OD-G4
serialization — which scopes by declared_origin, so cross-origin collisions
cannot exist). The first (earliest) resolution is the original; every later
capture resolving to the same fingerprint commits its own resolution row (its
S1 leg is real and immutable) PLUS one observation row referencing the
original — the D-03 fact made durable and auditable. The layer NEVER:
merges rows, deletes the later capture's record, scores similarity, compares
values field-by-field beyond the exact fingerprint, or suppresses the
duplicate observation. Fingerprint equality across captures with different
declared origins is impossible by construction (origin rides the fingerprint)
and is treated as a durable-set inconsistency (read-path structural gate).

## 7. Durable records (normative — exact field sets)

- `identity_resolutions` (immutable, INV-IR-S1:1 — at most ONE per capture_s1):
  `resolution_id` (uuid4 hex — bookkeeping), `capture_s1` (UNIQUE),
  `capture_s1_algorithm_id`, `capture_id`, `document_id`, `extraction_id`,
  `normalization_id`, `domain_state_id` (the verified anchor set, §9),
  `declared_origin` (CHECK ∈ frozen origins), `binding_declaration_fingerprint`
  ('' = no declaration), `identity_scope` (CHECK ∈ S2|CAPTURE_SCOPED),
  `identity_source` (CHECK ∈ ''|S2_EXTRACTED_VERIFIED), `identity_fingerprint`,
  `scope_reason`, `created_at`, `record_fingerprint`, `fingerprint_algorithm_id`.
  Storage CHECKs: scope='S2' ⇔ fingerprint≠'' ∧ source='S2_EXTRACTED_VERIFIED'
  ∧ scope_reason=''; scope='CAPTURE_SCOPED' ⇔ fingerprint='' ∧ source=''.
- `identity_role_candidates` (≤3 rows per resolution, frozen roles only,
  candidate evidence — declarations and counts, NEVER values):
  `resolution_id`, `role` (CHECK ∈ INVOICE_NUMBER|INVOICE_DATE|INVOICE_TOTAL),
  `source_field_name`, `candidate_count` (CHECK ≥ 0), `field_seqs`
  (deterministic ascending serialization), `resolved_field_seq` (NULL unless
  scope='S2'; CHECK: set ⇒ candidate_count=1), PRIMARY KEY(resolution_id, role).
- `identity_duplicate_observations` (append-only, INV-IR-DUP:1 — at most ONE
  per resolution): `observation_id`, `resolution_id` (UNIQUE — the LATER
  capture's resolution), `original_resolution_id`, `identity_fingerprint`,
  `original_capture_s1`, `duplicate_capture_s1` (CHECK: ≠ original),
  `created_at`, `observation_fingerprint`, `fingerprint_algorithm_id`.

## 8. Persistence & invariants (same store pattern as P1–P6.2)

- OD-IR1 storage: stdlib sqlite3, ONE separate embedded DB file
  (`identity-resolution.db` pattern); `synchronous=FULL`; idempotent schema;
  explicit BEGIN IMMEDIATE / COMMIT.
- OD-IR2 atomic commit: resolution + role candidate rows + duplicate
  observation (iff R2) in ONE transaction — zero residue on any failure, by
  construction.
- OD-IR3 invariants: INV-IR-S1:1 at most one resolution per capture_s1
  (in-transaction check + UNIQUE backstop — D-02/D-03 "no second identity");
  INV-IR-DUP:1 at most one duplicate observation per resolution (UNIQUE
  backstop); role rows ≤ 3 in the frozen roles; observation CHECK
  (different captures).
- OD-IR4 ids/clock: resolution_id / observation_id = uuid4 hex — bookkeeping
  only; the identity itself is ALWAYS the deterministic sha256-v1 fingerprint,
  never a random value (behaviorally proven: same verified inputs across two
  independent stacks → same fingerprint, different bookkeeping ids); single
  layer clock (UTC ISO-8601).
- OD-IR5 integrity anchors: `record_fingerprint` = sha256-v1 over the record
  scalars + the role candidate rows in frozen role order;
  `observation_fingerprint` over the observation scalars; both verified
  INSIDE every read (VOR — tamper withholds content).
- OD-IR6 storage gates: SQL CHECKs — scope/source/fingerprint/reason
  consistency; origin vocabulary; role vocabulary; candidate_count ≥ 0;
  observation capture difference; defensive Python-side commit refusals
  mirroring every CHECK.
- OD-IR7 no update/delete: resolution, role candidate, and observation rows
  are immutable once committed; no UPDATE or DELETE path exists in this store
  (AST-proven); restart-safe; tamper-evident.

Outcome ladders (exhaustive — never silent), P6.1 §8 analog:
`resolve` → IdentityResolutionRecorded | IdentityDefiniteDuplicate |
IdentityReplay | IdentityRequestRefused | IdentityInputIntegrityFailure |
IdentityStorageUnavailable. `read_resolution` / `read_resolution_by_capture`
→ IdentityReadSuccess | IdentityReadIntegrityFailure | IdentityReadRefused |
IdentityReadVerificationUnavailable.

## 9. Provenance / traceability chain (normative — pointers, verified reads)

    Identity Resolution Record (resolution_id)
        ↓ verified anchor set (capture_s1/capture_id/document_id/
          extraction_id/normalization_id/domain_state_id)
    P5.2 Domain State Record — walked through trace_domain_state (V2):
        validation refs → WP-5.1 whole-chain sub-walks (incl. WP-4.2 DERIVED
        sub-chains) → normalization → extraction → binding →
        Document/Page/span → Capture S1
    Role candidate rows → verified WP-4.1 read re-join
        (role, source_field_name, field_seq — byte-identity check)

Every resolution is committed ONLY after the whole chain re-verifies (V2);
the record adds ONE head link onto the intact P5.2 chain. No raw pipeline
value is ever stored (pointer discipline — P6.1 §5 I5 analog): the S2 tuple
rides as its fingerprint + role candidate rows. A broken link at ANY layer →
`IdentityInputIntegrityFailure`, zero residue. A tampered durable row →
`IdentityReadIntegrityFailure` (content withheld, never served).

## 10. Delegated implementation details (declared per D-09)

- OD-IR-A module shape: `src/identity_resolution/` = model.py (vocabularies,
  records, outcomes) + resolver.py (pure) + store.py (persistence) +
  service.py (orchestration) + `__init__.py` + tests/; smoke runner
  `run_smoke_identity_resolution.py`.
- OD-IR-B binding declaration fingerprint: sha256-v1 over the canonical
  key-sorted serialization of the role→field mapping (order-of-declaration
  independent); '' when the binding is absent (None and {} identical —
  OD-G10 analog).
- OD-IR-C non-VALID states: scope CAPTURE_SCOPED with reason
  `s2-not-attempted-state-not-valid`, committed WITHOUT reading any
  normalization value (the resolver never sees unverified values; R1b).
- OD-IR-D reason codes: the three P6.1 D-03 codes reused VERBATIM
  (`d03-incomplete-document-identity`, `d03-conflicting-document-identity`,
  `d03-document-identity-undetermined`) + exactly one new code
  (`s2-not-attempted-state-not-valid`) for the R1b route.
- OD-IR-E duplicate original selection: earliest (created_at, resolution_id)
  among same-fingerprint resolutions from OTHER captures — deterministic
  under concurrency (R2).
- OD-IR-F replay declaration match: same declared_origin AND same
  binding_declaration_fingerprint; otherwise `replay-declaration-drift`
  refusal (P6.2 OD-A8 discipline — no second identity, no silent reshape).
- OD-IR-G identity machinery reuse: `resolve_identity` / `validate_binding`
  imported from `canonicalization.identity` — the frozen P6.1 primitives are
  the ONLY formula source; this layer contains no fingerprint computation of
  its own beyond record-integrity anchors (OD-IR5) and the OD-IR-B
  declaration fingerprint.
- OD-IR-H scope vocabulary: identity_scope ∈ {S2, CAPTURE_SCOPED} exactly;
  S1 is the capture_s1 leg + the R0 behavior; no synonymous scope/status is
  introduced (dispatch §15).
- OD-IR-I Canonical Identity boundary: no invoice_id is minted, stored, or
  referenced; no canonical-invoice columns exist in this store; P6.1/P6.2
  remain the sole owners.
- OD-IR-J candidate evidence preservation: role candidate rows are recorded
  for S2 resolutions AND for CAPTURE_SCOPED incomplete/conflicting outcomes
  (counts + field_seqs + bound names) — ambiguity stays a Gate/review
  concern with full evidence, never auto-resolved, never converted to
  UNRESOLVED (dispatch §8, D-01).

## 11. AC mapping (verification in Acceptance Register)

- AC-7.1.1 Resolution states: deterministic, exact-only resolution around
  S1/S2/CAPTURE_SCOPED with the distinction explicit and durable; S2 only
  via the frozen P6.1 primitive over verified reads; CAPTURE_SCOPED explicit
  with stable reasons; ambiguity never auto-selected and never UNRESOLVED;
  no invented values.
- AC-7.1.2 Idempotency & duplicates: dispatch cases A–F exact (S1 replay →
  one identity/one resolution/zero duplicates; same S2 different captures →
  definite duplicate + one document identity; different S2 → different
  identity; incomplete → CAPTURE_SCOPED; ambiguous → no automatic selection;
  changed value → NOT duplicate); replay after restart; concurrent
  submissions → UNIQUE backstop + in-transaction checks; declaration-drift
  refusal.
- AC-7.1.3 Persistence: project store pattern complete (SQLite FULL, atomic
  commit, immutable records, VOR, sha256-v1, CHECK/UNIQUE gates, tamper
  detection, restart safety, no UPDATE/DELETE — AST-proven, zero residue on
  partial failure).
- AC-7.1.4 Boundary & integration: full provenance chain machine-checkable
  to Capture S1 (P5.2 whole-chain walk consumed-not-bypassed, spy-proven);
  broken/tampered provenance fails closed; frozen P1–P6.2 byte-untouched
  (full regression green); no fuzzy/heuristic/AI matching (AST-proven); no
  upstream execution; no invoice minting.

## 12. Test expectations (behavior, not line coverage)

Mandated axes (dispatch §11–§13): Case A exact S1 replay (same capture
repeatedly — one identity, one durable resolution, zero duplicates); Case B
same exact S2 document from different captures (one document identity,
subsequent captures → definite duplicate handling); Case C different S2
document (different identity); Case D incomplete S2 (CAPTURE_SCOPED); Case E
ambiguous candidate set (no automatic selection); Case F changed/
non-identical exact value (NOT duplicate). Adversarial: missing invoice
number / date / total; two invoice-number / date / total candidates; tampered
provenance; broken provenance pointer; replay after process restart;
duplicate concurrent submission; same S2 values from different captures;
one-character exact-value difference; whitespace/canonical-serialization
boundary per the frozen contract; invalid origin; invalid state; forged
database row; corrupted hash; duplicate identity insertion; partial
transaction failure — every failure fails closed. Concurrency: same identity
≠ multiple identities with DB uniqueness as the final backstop (never
Python-only). Structural: AST zero UPDATE/DELETE/DROP; import allowlist;
forbidden-symbol sweep (fuzzy/similarity/heuristic/AI/OCR/...); vocabulary
sweeps; frozen-store row-count stability; spy-proven zero upstream execution;
no invoice columns; uuid/random never substitutes identity logic.
