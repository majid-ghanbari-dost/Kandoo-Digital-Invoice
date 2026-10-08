# SPEC-WP72-DUPFLOW — Reprint & Duplicate Flows Contract v1.0-MVP

```text
Spec ID:      SPEC-WP72-DUPFLOW | Version: 1.0-MVP | Date: 2026-10-08
Status:       IMPLEMENTATION CONTRACT (T-7.2.1) — produced inline per TM/PO
              implementation dispatch 2026-10-08 ("WP-7.2 — Reprint &
              Duplicate Flows — reconnaissance then BUILD")
Authority:    REG-WPR Phase Index P7 row (WP-7.2 Reprint & Duplicate Flows —
              PLANNED) + the PO implementation dispatch 2026-10-08 is the
              scope of record; this spec converts that scope into the
              binding implementation contract and instantiates the WP
              section in REG-WPR per the standard template.
Frozen basis: D-02 (three-identity model VERBATIM — S1 capture identity /
              S2 external document identity / Canonical Identity owned by
              P6.1/P6.2) | D-03 (idempotency: S1 → capture idempotency; S2
              complete+exact → definite document-level duplicate;
              incomplete/conflicting → REVIEW; CAPTURE_SCOPED = only
              capture-level deduplication guaranteed; NO new idempotency
              definition) | D-01 (UNRESOLVED never created outside P5.2) |
              D-04 | D-09 (delegated details declared) | AD-01 | AD-02 |
              AD-04/CL-1 (verbatim vocabulary) | AS-01 | AS-02 | AS-03 (no
              state invention or renaming) | AS-04 |
              SPEC-WP71-IDRES (the durable identity layer this WP CONSUMES
              VERBATIM — resolve / read_resolution / read_resolution_by_
              capture; no identity logic is re-implemented, re-decided, or
              forked here) | SPEC-WP61-CANGATE (the Gate remains the sole
              canonicalization authority — G4 ALREADY_CANONICALIZED and G5
              REJECTED decisions are P6.1's, untouched and unrepeated) |
              SPEC-WP62-CANASM | SPEC-WP52-VSM | WP-1.1 (S1 sha256-v1).
Baseline note (MNT-1): the physical Canonical Invoice v1 / Master
              Architecture documents remain uncommitted (kandoo/baseline/
              pending); the Decision Register + the dispatch are the valid
              self-contained representation (pre-registered, not a STOP
              cause).
Upstream:     P1 → P2 → P3 → P3.2 → P4.1 → P4.2 → P5.1 → P5.2 → WP-7.1
              (durable identity resolutions) — this WP consumes ONLY the
              WP-7.1 public service surface. It NEVER executes any upstream
              layer itself, NEVER resolves identity on its own, and NEVER
              re-decides canonicalization.
Downstream:   future operational consumers (P10 Digital Invoice lifecycle
              and any WP that must ask "is this capture a reprint or a
              duplicate, and of what original?") consume the durable flow
              dispositions; P6.1/P6.2 canonical authorities are untouched.
```

## 1. Purpose and scope

WP-7.2 delivers ONE deterministic Reprint & Duplicate Flows service: the
operational decision layer that turns WP-7.1's durable identity facts into
explicit, auditable flow outcomes. For every capture artifact that reaches
the identity layer, the flow service commits exactly ONE durable disposition
record (INV-DF-1:1) classifying the capture's identity journey:

- **Reprint flow** — the SAME capture artifact is presented again (same
  `capture_s1`). WP-7.1's replay recognition (R0) is consumed VERBATIM: the
  existing resolution is returned verbatim, read-only, after its own VOR
  verification; ZERO new identity rows; ZERO new disposition rows. A drifted
  declaration on replay is refused exactly as WP-7.1 refuses it
  (`replay-declaration-drift` — propagated, never reshaped).
- **Duplicate flow** — a DIFFERENT capture resolves to the SAME exact S2
  fingerprint (D-03 definite duplicate). The disposition points at the
  deterministic original resolution and at the WP-7.1 duplicate observation:
  ONE document identity, made operationally addressable (the durable
  duplicate register), never merged, never suppressed.
- **First sighting** — a capture whose resolution is newly recorded
  (S2 established or CAPTURE_SCOPED) commits its IDENTITY_ESTABLISHED
  disposition. A CAPTURE_SCOPED capture is a first sighting WITHOUT a
  document identity: no duplicate claim is ever made from an unresolved
  identity (D-03: only capture-level deduplication is guaranteed — the flow
  layer adds no guessing on top).

Relationship to WP-7.1 (normative): the flow layer contains NO identity
logic of its own. The S1/S2/CAPTURE_SCOPED resolution, the replay
recognition, the exact-duplicate detection, the fingerprint formula, and
every refusal live in WP-7.1 and are consumed through its public service —
consumed, never bypassed, never re-implemented (spy-proven). What WP-7.2
adds is the durable operational disposition P7.1 deliberately did not own:
one auditable per-capture flow fact, the reprint recognition outcome, and
the durable duplicate register keyed by the original resolution.

In scope:
1. **Flow dispositions** — ONE immutable disposition per capture_s1 with
   outcome vocabulary `IDENTITY_ESTABLISHED | DUPLICATE_RECOGNIZED`
   (commit-time) and the reprint recognition as the read-only call outcome
   (`REPRINT_RECOGNIZED` — never durable) (§4/§5).
2. **Flow service** — verified delegation to WP-7.1 `resolve` + the
   deterministic outcome mapping + fail-closed passthrough (§4).
3. **Verified flow reads** — VOR on the disposition row + re-verification of
   every LINKED identity record through the WP-7.1 verified reads
   (resolution, original resolution, observation) + cross-store structural
   gates (§6).
4. **Duplicate register queries** — `duplicates_of(original_resolution_id)`
   over the durable dispositions (§6).
5. **Persistence** per the project store pattern (§7/§8).
6. Behavioral + structural boundary tests (delegation proof, adversarial
   matrix, durability, concurrency, AST probes, frozen-layer protection).

Out of scope (FORBIDDEN — dispatch): canonicalization re-decision of ANY
kind (P6.1 owns ACCEPTED/REJECTED/REVIEW/ALREADY_CANONICALIZED); Canonical
Assembly or invoice_id handling (P6.2); REVIEW queue operations or review
resolution (P5.2/P6.1 own their queues; the flow layer never closes,
reopens, or annotates review items); new identity scopes, new idempotency
definitions, or any synonym of the frozen vocabulary (D-03/AS-03); any
change to any frozen layer P1–P7.1 (purely additive WP); merging, deleting,
or reshaping resolutions or observations; reprint event logging beyond the
one durable disposition per capture (the recognition is read-only by
design — no speculative event log); product/customer matching; OCR/AI/
fuzzy/heuristic matching of ANY kind; upstream execution; Holoo parser;
Cloud sync; UI; mobile.

## 2. Input path (normative)

The ONLY input path is the WP-7.1 public service surface
(`IdentityResolutionService.resolve` and its verified reads), consumed
VERBATIM inside every `handle` call. The flow service never reads any
upstream store directly, never reads raw artifacts, never computes or
re-computes an identity fingerprint (beyond its own record-integrity
anchors, §8), never executes any pipeline stage, and never accepts identity
facts from any source other than the WP-7.1 outcome objects.

Scope of one flow request = ONE WP-7.1 `resolve` request
(`domain_state_id`, `declared_origin`, optional `identity_field_binding`)
— the request contract of SPEC-WP71-IDRES §3 applies VERBATIM (frozen
origin vocabulary; AS-02 native-flow refusal; binding validation). The flow
layer validates nothing itself and repairs nothing: every refusal of the
identity layer passes through fail-closed with zero durable residue.

## 3. Request contract (normative)

`handle(domain_state_id, declared_origin, identity_field_binding=None)` —
the arguments are exactly WP-7.1's `resolve` arguments, passed through
untouched. There is no second request vocabulary, no flow-level options,
no override switches.

## 4. Flow ladder (normative — fail-closed, ordered)

The flow service performs exactly ONE identity resolution per call — WP-7.1's
`resolve` — and maps the outcome deterministically:

| # | WP-7.1 outcome | Flow action | Call outcome | Frozen anchor |
|---|---|---|---|---|
| F1 | `IdentityRequestRefused` / `IdentityInputIntegrityFailure` / `IdentityStorageUnavailable` | NONE — pass through fail-closed, zero durable residue | `FlowRequestRefused` / `FlowInputIntegrityFailure` / `FlowStorageUnavailable` (detail propagated verbatim) | SPEC-WP71 §4 (V1–V4 refusals); D-03 fail-closed discipline |
| F2 | `IdentityResolutionRecorded` | commit ONE disposition `IDENTITY_ESTABLISHED` anchored to the new resolution (scope/fingerprint copied from the verified resolution record; `original_resolution_id=''`) | `FlowIdentityEstablished` (disposition + resolution + role rows) | D-02 (S2 established or CAPTURE_SCOPED — the capture's first durable sighting) |
| F3 | `IdentityDefiniteDuplicate` | commit ONE disposition `DUPLICATE_RECOGNIZED` anchored to the new resolution + `original_resolution_id` + the WP-7.1 observation id | `FlowDuplicateRecognized` (disposition + record + original + observation + role rows) | D-03 (S2 complete+exact → definite document-level duplicate; ONE document identity) |
| F4 | `IdentityReplay` — a disposition already exists for this capture_s1 | NONE — the existing disposition is returned VERBATIM after its full verified read (own VOR + linked-resolution re-verification + structural gates); ZERO new rows | `FlowReprintRecognized` (disposition + replayed record + role rows + observation iff any + verified_at) | D-02 S1 idempotency; SPEC-WP71 R0 (replay recognition consumed, not re-implemented) |
| F5 | `IdentityReplay` — NO disposition yet (first flow-layer sighting of an already-resolved capture) | commit ONE disposition derived deterministically from the REPLAYED resolution's own durable shape (observation present → `DUPLICATE_RECOGNIZED` with the observation's original; else `IDENTITY_ESTABLISHED`) — the same content a first sighting would have committed | `FlowReprintRecognized` | D-03 (the disposition is a pure function of durable facts — deployment-order independent) |
| F6 | commit-time collision (`DispositionDuplicate` — UNIQUE(capture_s1) backstop or in-txn check) | NONE — re-read the winning disposition (verified) and return it | `FlowReprintRecognized` | concurrency safety; DB uniqueness as the final backstop (never Python-only) |

Exhaustive call ladder (never silent): `handle` → FlowIdentityEstablished |
FlowDuplicateRecognized | FlowReprintRecognized | FlowRequestRefused |
FlowInputIntegrityFailure | FlowStorageUnavailable.

## 5. Dispositions (normative — the per-capture flow fact)

The durable record carries the capture's flow classification explicitly:

- **IDENTITY_ESTABLISHED** — the capture's resolution is the FIRST durable
  resolution of its identity (S2 established or CAPTURE_SCOPED):
  `original_resolution_id=''`, `duplicate_observation_id=''`. A
  CAPTURE_SCOPED resolution is ALWAYS IDENTITY_ESTABLISHED at flow level —
  no document identity exists to be duplicated, and inventing one is
  forbidden (D-03/D-02).
- **DUPLICATE_RECOGNIZED** — the capture's resolution carries a WP-7.1
  duplicate observation: `original_resolution_id` = the deterministic
  original (OD-IR-E semantics consumed verbatim), `duplicate_observation_id`
  = the observation id. The later capture never becomes a second document
  identity; the disposition is the operationally addressable pointer to the
  original.
- **REPRINT_RECOGNIZED** — call outcome ONLY (F4/F5/F6): the capture was
  already dispositioned; the existing disposition returns verbatim, read-
  only. It is NEVER committed (storage CHECK forbids it) — a reprint is a
  recognition event, not a new fact about the capture.

Vocabulary discipline (AS-03/AD-04/CL-1): the flow layer introduces NO
identity scope, NO state name, and NO idempotency definition. `S1 / S2 /
CAPTURE_SCOPED` appear ONLY as the linked resolution's own frozen fields
(copied for self-description, cross-checked on every read). The
`IDENTITY_ESTABLISHED | DUPLICATE_RECOGNIZED` disposition vocabulary and the
`REPRINT_RECOGNIZED` call outcome are this WP's delegated flow vocabulary
(D-09, OD-DF-B) — flow facts, not identity states.

## 6. Verified flow reads + the durable duplicate register (normative)

`read_disposition(capture_s1)` / `read_disposition_by_id(disposition_id)` —
definitive integrity verdict computed INSIDE the read:

1. Own-row VOR (sha256-v1 record fingerprint — tampered rows withhold
   content, never served).
2. LINKED re-verification: the referenced WP-7.1 resolution MUST verify
   through `read_resolution` (VOR + structural gates of WP-7.1). A broken
   or tampered identity fact withholds the disposition
   (`FlowReadIntegrityFailure` / `FlowReadVerificationUnavailable`) — the
   flow layer never serves a disposition whose identity facts no longer
   verify.
3. Cross-store structural gates: disposition.capture_s1 / capture_id /
   document_id / resolution_id / identity_scope / identity_fingerprint MUST
   equal the linked resolution's; outcome shape gates (§5): 
   `DUPLICATE_RECOGNIZED` ⇔ `original_resolution_id≠''` AND the original
   resolution verifies AND the linked resolution carries the observation AND
   observation ids/references agree; `IDENTITY_ESTABLISHED` ⇔
   `original_resolution_id=''` AND no observation on the linked resolution.

`duplicates_of(original_resolution_id)` — the durable duplicate register:
every disposition with outcome `DUPLICATE_RECOGNIZED` anchored to that
original (raw records, mirroring WP-7.1's `list_resolutions` listing
discipline; consumers verify through `read_disposition_by_id`). The
original's identity is never re-computed — the register is a query over
committed dispositions.

## 7. Durable records (normative — exact field sets)

- `flow_dispositions` (immutable, INV-DF-1:1 — at most ONE per capture_s1):
  `disposition_id` (uuid4 hex — bookkeeping), `capture_s1` (UNIQUE),
  `capture_s1_algorithm_id`, `capture_id`, `document_id`,
  `resolution_id`, `original_resolution_id`, `duplicate_observation_id`,
  `declared_origin` (CHECK ∈ frozen origins), `flow_outcome`
  (CHECK ∈ IDENTITY_ESTABLISHED|DUPLICATE_RECOGNIZED),
  `identity_scope` (CHECK ∈ S2|CAPTURE_SCOPED), `identity_fingerprint`,
  `created_at`, `record_fingerprint`, `fingerprint_algorithm_id`.
  Storage CHECKs: `flow_outcome='IDENTITY_ESTABLISHED'` ⇔
  `original_resolution_id=''` ∧ `duplicate_observation_id=''`;
  `flow_outcome='DUPLICATE_RECOGNIZED'` ⇔ `original_resolution_id≠''` ∧
  `duplicate_observation_id≠''`; `identity_scope='S2'` ⇔
  `identity_fingerprint≠''`; `identity_scope='CAPTURE_SCOPED'` ⇔
  `identity_fingerprint=''`; `REPRINT_RECOGNIZED` is NEVER storable.

## 8. Persistence & invariants (same store pattern as P1–P7.1)

- OD-DF1 storage: stdlib sqlite3, ONE separate embedded DB file
  (`duplicate-flows.db`); `synchronous=FULL`; idempotent schema; explicit
  BEGIN IMMEDIATE / COMMIT.
- OD-DF2 atomic commit: the disposition is a single-row transaction — zero
  residue on any failure, by construction.
- OD-DF3 invariants: INV-DF-1:1 at most one disposition per capture_s1
  (in-transaction check + UNIQUE backstop — the flow fact of a capture is
  decided once, ever).
- OD-DF4 ids/clock: disposition_id = uuid4 hex — bookkeeping only; all
  identity semantics ride the linked WP-7.1 fingerprints; single layer
  clock (UTC ISO-8601).
- OD-DF5 integrity anchor: `record_fingerprint` = sha256-v1 over the
  disposition scalars (computed via the project S1 service — no hashlib in
  the layer), verified INSIDE every read (VOR).
- OD-DF6 storage gates: SQL CHECKs (§7) + defensive Python-side commit
  refusals mirroring every CHECK.
- OD-DF7 no update/delete: disposition rows are immutable once committed;
  no UPDATE or DELETE path exists in this store (AST-proven); restart-safe;
  tamper-evident.

## 9. Provenance / traceability chain (normative — pointers, verified reads)

    Flow Disposition (disposition_id)
        ↓ capture_s1 / capture_id / document_id / resolution_id
    WP-7.1 Identity Resolution (resolution_id) — re-verified inside every
        flow read through read_resolution (VOR + WP-7.1 structural gates)
        ↓ identity_duplicate_observations (iff DUPLICATE_RECOGNIZED)
          original_resolution_id → the original resolution (also
          re-verified inside the flow read)
    … continuing down the WP-7.1 anchor set to Capture S1 (owned by WP-7.1's
      V2 whole-chain walk — consumed at resolution time, never repeated
      here)

The disposition adds ONE head link onto the intact WP-7.1 identity fact; it
stores NO raw pipeline value (pointer discipline) — the identity semantics
ride the linked fingerprints. A tampered disposition row, a tampered linked
resolution, or a broken link → the flow read withholds content
(fail-closed, never served).

## 10. Delegated implementation details (declared per D-09)

- OD-DF-A module shape: `src/duplicate_flows/` = model.py (vocabularies,
  records, outcomes) + store.py (persistence) + service.py (orchestration)
  + `__init__.py` + tests/; smoke runner `run_smoke_duplicate_flows.py`.
  There is NO resolver.py: the layer contains no pure identity logic to
  isolate — classification is a deterministic mapping of WP-7.1 outcome
  types (F1–F6), implemented inside the service and covered by the test
  matrix.
- OD-DF-B flow vocabulary: `IDENTITY_ESTABLISHED | DUPLICATE_RECOGNIZED`
  (durable) + `REPRINT_RECOGNIZED` (call outcome only) — the minimal
  delegated flow vocabulary; no synonym of any frozen state; no new
  identity scope (§5).
- OD-DF-C consumption discipline: WP-7.1's `resolve` is the ONLY identity
  engine; the flow layer imports nothing from `identity_resolution.resolver`
  and contains no fingerprint computation beyond OD-DF5 (AST-proven: no
  hashlib, no formula, no import of the P6.1 primitive).
- OD-DF-D linked verification depth: every flow read re-verifies the linked
  resolution AND, for DUPLICATE_RECOGNIZED, the original resolution and the
  observation — through the WP-7.1 verified reads (never blind pointers).
- OD-DF-E disposition determinism: the disposition content is a pure
  function of the linked durable facts (F5) — committing it at first
  sighting or at first flow-layer sighting yields byte-identical content
  apart from bookkeeping (created_at/disposition_id).
- OD-DF-F reprint semantics: reprints are recognized read-only; the durable
  trail is the ONE disposition per capture (no reprint event log, no
  counter, no mutable field — D-03's "one identity, ever" mirrored at flow
  level).
- OD-DF-G refusal passthrough: WP-7.1 refusal/integrity details propagate
  VERBATIM (including `replay-declaration-drift`) — the flow layer never
  reformulates a refusal reason and never converts a refusal into a
  disposition.
- OD-DF-H listing discipline: `duplicates_of` / `dispositions` return raw
  records (WP-7.1 `list_resolutions` analog); verified views go through the
  read paths.
- OD-DF-I Canonical Identity boundary: no invoice_id, no canonical-invoice
  reference, no P6.1/P6.2 read exists in this layer (the Gate and Assembly
  remain sole owners; flow consumers needing canonical state read P6.1/
  P6.2 themselves).
- OD-DF-J review boundary: no REVIEW queue item is created, read, closed,
  or annotated here; CAPTURE_SCOPED/ambiguity routing remains the P6.1/
  P5.2 concern (D-01/D-03).

## 11. AC mapping (verification in Acceptance Register)

- AC-7.2.1 Reprint flow: re-presenting a capture → `FlowReprintRecognized`
  verbatim — ONE durable resolution, ONE durable disposition, zero new rows
  (WP-7.1 store row-count stability); declaration drift on reprint →
  refusal propagated verbatim; reprint after restart; reprint of a
  duplicate capture returns its DUPLICATE_RECOGNIZED disposition verbatim;
  tampered existing disposition → fail closed (never recognized from a
  tampered row).
- AC-7.2.2 Duplicate flow: same exact S2 from different captures →
  `FlowDuplicateRecognized` pointing at the deterministic original +
  observation; third capture → same ONE original; `duplicates_of` lists
  exactly the duplicates; one-character exact-value difference → NOT a
  duplicate (IDENTITY_ESTABLISHED); CAPTURE_SCOPED captures are NEVER
  duplicates and never guessed into one (Case E/D preserved — no automatic
  selection, no invented identity).
- AC-7.2.3 Delegation + persistence: WP-7.1 `resolve` consumed VERBATIM
  (spy-proven; no identity formula, no hashlib, no P6.1 import — AST);
  project store pattern complete (SQLite FULL, atomic single-row commit,
  immutable, VOR, sha256-v1 via the project S1 service, CHECK/UNIQUE gates,
  tamper detection, restart safety, no UPDATE/DELETE — AST-proven, zero
  residue on forced failure); INV-DF-1:1 with the UNIQUE backstop proven
  under an 8-thread race (one disposition per capture; losers map to the
  winner read-only).
- AC-7.2.4 Boundary & integration: linked-verification gates (tampered/
  broken resolution or original withholds the disposition); cross-store
  structural gates (forged/disagreeing rows fail closed); frozen P1–P7.1
  byte-untouched (full regression green); no REVIEW/canonicalization/
  invoice_id/product/customer semantics anywhere in the layer (AST +
  vocabulary sweeps).

## 12. Test expectations (behavior, not line coverage)

Mandated axes: reprint recognition (verbatim, zero-row, across restarts,
after drift refusal, on duplicate captures, on CAPTURE_SCOPED captures);
duplicate register (twin/third-order → one original; register completeness;
one-char diff NOT duplicate; whitespace/canonical-serialization boundary
per the frozen contract); refusal passthrough matrix (unknown state, bad
origin, native-flow origin, malformed binding, replay declaration drift —
each with zero durable residue); F5 backfill determinism (first flow-layer
sighting of pre-existing resolutions — both shapes); concurrency (8-thread
same-capture race → one disposition; twin-capture race → per-capture
dispositions + one original); durability (forced mid-commit failure → zero
residue; restart; forged row; hash-consistent forged row withheld by
structural gates; CHECK refusals via direct SQL; UNIQUE backstop);
structural/AST probes (zero UPDATE/DELETE/DROP/random/eval/float/hashlib;
import allowlist; forbidden-symbol sweep; vocabulary sweeps — no frozen
synonyms, no REPRINT_RECOGNIZED storage; frozen-store row-count stability;
spy-proven WP-7.1 consumption with zero upstream execution; no
canonicalization/invoice/review semantics).
