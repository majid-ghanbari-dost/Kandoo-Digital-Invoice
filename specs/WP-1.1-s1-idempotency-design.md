# WP-1.1 — S1 Fingerprint & Capture-Level Idempotency Lookup Service — Architecture Design (T-1.1.3)

```text
Design ID:     DES-WP11-T113-S1 | Version: 1.0 | Date: 2026-10-01 | Status: PROPOSED — READY FOR TECHNICAL MANAGER FINAL REVIEW
Task:          T-1.1.3 — S1 Fingerprint & Idempotency Lookup Service (design step; Architecture Review / Pre-Freeze)
Authority:     SPEC-WP11-CRC — Capture Record Contract v1.1 (FINAL FREEZE APPROVED)
               DES-WP11-T112-STORE — Durable Local Capture Store Design v0.2 (FINAL APPROVED)
               Locked Decisions D-02, D-03, D-09 (kandoo/registers/decision-register.md)
               G1 Architecture Approval: PASS | G2 Work Package Approval for WP-1.1: APPROVED
Binding for:   T-1.1.3 implementation dispatch (after TM approval); composition boundaries stated for T-1.1.2 (consumed), T-1.1.4/T-1.1.5 (future consumers).
Change Control: فقط از مسیر STOP Protocol → Issue Report → TM Review → PO Decision (D-09)
Constraints:   No product code | No schema/migration | No API design | No storage-technology selection | MVP discipline — no complexity without a concrete requirement.
Missing Input: kandoo/baseline/ still empty (OI-1 / MNT-1 / RSK-2) — Decision Register remains interim SSOT; zero guessing. Non-blocking (pre-existing, tracked).
```

---

## 0. Normative Basis (what this design consumes, verbatim)

| Source | Used for |
|---|---|
| Contract v1.1 §5 (F-02, F-03) | `s1` = content fingerprint value, immutable after attach, never null on `COMPLETED`; `s1_algorithm_id` = immutable algorithm/version label |
| Contract v1.1 §8 | S1 = Capture Identity (D-02); properties: deterministic, content-sensitive; algorithm delegated (§16) and recorded via `s1_algorithm_id`; comparison valid only within one `s1_algorithm_id`; v1.1-C3 aggregation determinism |
| Contract v1.1 §9 | Idempotency contract: key = S1; lookup restricted to `COMPLETED`; three mandatory branches; INV-C3; D-03 — no new idempotency definition |
| Contract v1.1 §10 | verify operation: recompute S1 over stored content with the record's own `s1_algorithm_id` |
| Contract v1.1 §13 | INV-C1, INV-C2, INV-C3, INV-C7, INV-C8, INV-C10 — inherited as binding |
| Contract v1.1 §14 | r2 (S1 compute failure), r5 (hit-on-FAILED), r9 (S1 collision) — mandatory behaviors |
| Contract v1.1 §16 | S1 algorithm = delegated implementation detail; SHA-256 named as an *example option, not a decision* |
| Store Design v0.2 §1, §2, §3, §9, §9.1, §11, §12, §13, §14 | Store capabilities consumed: `COMPLETED`-restricted lookup, UAC (P1–P6), S1 attach (Step 2), first verification (Step 3), completion gate (Step 4), settlement primitives, INV-S9/S10, AC-T112-9/10 |
| D-02 / D-03 / D-09 | Three-identity model (S1 = Capture Identity only); S1 = sole capture-level idempotency key; delegation governance |
| WP / Task / Acceptance Registers | AC-1.1.2, AC-1.1.3, AC-1.1.4 owned by T-1.1.3; T-1.1.3 dependencies = T-1.1.1 (DONE) + T-1.1.2 integration; Out of Scope: S2/document-level dedup, semantic interpretation, extraction |

No contract rule or store-design rule is restated differently here. Where this document adds a rule, it is labeled **R-S1-* (design rule, proposed)** or **OD-S* (open/delegated decision)** and does not modify any frozen document.

---

## 1. Responsibility Boundary

**T-1.1.3 owns (full responsibility):**

1. **S1 algorithm contract** — the binding property set (§3), input domain and exclusions (§3), output representation requirements (§3), and the `s1_algorithm_id` semantics (§4).
2. **S1 calculation** — (a) at ingest: compute S1 over the exact delivered byte sequence (§6 step 2); (b) as a reusable capability: recompute S1 over stored content with a record's own `s1_algorithm_id`, consumed by the store's first verification (§7 r1 gate, Store Step 3), by recovery settlement (§11 via Store §5), and later by T-1.1.4's verify-on-read wiring.
3. **`s1_algorithm_id` identification** — which label denotes which algorithm + version + output encoding; versioning discipline (§4).
4. **Capture-level duplicate decision** — the three-branch §9 decision and nothing beyond it (§6).
5. **Lookup orchestration** — query the store, interpret the result strictly per §9, and issue the resulting directive (duplicate response / integrity-failure path / create-and-continue).

**T-1.1.3 does NOT own:**

- Durable storage mechanics, record storage, artifact storage (T-1.1.2) — **T-1.1.3 holds no storage of its own**; every persistent effect goes through the store.
- UAC enforcement (T-1.1.2 §9.1) — consumed, never re-implemented, never bypassed.
- OCR/VLM, Reconstruction, Identity Resolution, Digital Invoice, Inventory, Holoo, Cloud Sync (D-02/D-04, AD-02/AD-03) — strictly absent.
- External Document Identity (S2 / adapter id / `CAPTURE_SCOPED`) and Canonical Invoice Identity (`invoice_id`, P6 only) — never created, stored, inferred, or interpreted here.
- Verify-on-read read-path enforcement (T-1.1.4), startup scan + settlement orchestration (T-1.1.5), retention (DEF4/WP-1.3), aggregation of multi-file submissions (entry point, §4 r5).

**Concept separation:**

| Concern | Owner | T-1.1.3 role |
|---|---|---|
| S1 algorithm contract | **T-1.1.3** | full |
| S1 computation (ingest + verification recompute capability) | **T-1.1.3** | full |
| `s1_algorithm_id` identification | **T-1.1.3** | full |
| Capture-level duplicate decision & lookup orchestration | **T-1.1.3** | full |
| Lookup capability (query over stored records) | T-1.1.2 | consumes the `COMPLETED`-restricted query; never re-implements |
| UAC / uniqueness enforcement | T-1.1.2 | consumes via the completion directive; INV-C3 correctness = store's INV-S10 |
| Record & artifact durability | T-1.1.2 | none |
| Verify-on-read enforcement | T-1.1.4 | provides the compute capability only |
| Startup scan / settlement orchestration | T-1.1.5 | provides the compute capability only |
| External/Canonical identity | Identity Resolution (P6/P7) | strictly none (D-02) |

**Boundary vs T-1.1.2 (explicit):** the store answers the query "which `COMPLETED` records carry (s1, s1_algorithm_id)?" and enforces uniqueness-atomic completion. T-1.1.3 decides what the answer *means* under §9 (duplicate-at-capture / integrity-failure path / miss → new record) and issues directives. The store treats the key as opaque bytes; T-1.1.3 gives it its algorithm meaning — but **both** treat it as capture-level identity only. Neither party derives document identity from a match (D-02: document identity = downstream).

**Boundary vs T-1.1.4 / T-1.1.5 (explicit):** they orchestrate *when* verification runs (read-path wiring; recovery scan); T-1.1.3 owns *how* S1 is computed. T-1.1.3 ships the capability; it does not wire or schedule it.

---

## 2. Inputs and Outputs

Contract-level roles only (no API/signature design — D-09).

**Inputs:**

| Input | Content | Source | Anchor |
|---|---|---|---|
| Final aggregated byte sequence | the exact bytes to fingerprint | capture entry point (single handoff; the same byte sequence is handed to the store) | §4, §8, v1.1-C3 |
| Lookup result | `COMPLETED` records matching (s1, s1_algorithm_id), each with its `integrity_status` | T-1.1.2 store (`COMPLETED`-restricted query) | §9 step 2; Store §1 item 6 |
| Completion outcome | granted, or explicit uniqueness-conflict rejection | T-1.1.2 store (UAC) | Store §9.1 P1/P3 |
| Verification demand | stored content + record's own `s1_algorithm_id` → recompute and compare | store (Step 3 / recovery §5) / T-1.1.4 (later) | §10 |

**Outputs:**

- S1 value + `s1_algorithm_id` — the attach payload recorded by the store as F-02/F-03 (immutable after attach).
- Duplicate decision outcome, exactly one of: **duplicate-at-capture** (existing `capture_id` + duplicate marker) | **explicit integrity-failure outcome** | **proceed-new** (store creates the `ACTIVE` record; ingest continues).
- Verification verdicts (`VALID`/`FAILED` with reason) — computed by the T-1.1.3 capability, recorded by the store as restricted writes (§6 class 3).
- Explicit failure outcomes per §8 (failure matrix) — never a silent result, never an inferred identity.

**Never an output:** any record or artifact written by T-1.1.3 itself; any external-document identifier; any canonical identifier; any downstream-domain datum (INV-C7 analog, INV-F6).

---

## 3. S1 Contract

### 3.1 Required properties (binding on any algorithm — answers TM Q1, Q4)

| ID | Property | Anchor |
|---|---|---|
| P-S1-1 | **Deterministic** — `compute(B, A)` returns the identical S1 value on every execution, in any process, after any restart, at any time | §8 prop 1; INV-C2 |
| P-S1-2 | **Content-sensitive** — any single-byte change to B yields a different S1 (practically: collision-resistant; verified by mutation test, AC-1.1.2) | §8 prop 2; INV-C2 |
| P-S1-3 | **Input exactness** — the input is exactly the artifact byte sequence; no preprocessing of any kind: no normalization, no transcoding, no trimming, no re-encoding, no metadata mixing | §8 ("ورودی S1 فقط بایت‌های محتوای artifact است") |
| P-S1-4 | **Output canonicity** — fixed-length output in one canonical, environment-independent encoding (no locale/endianness ambiguity in the recorded form) | F-02; reproducibility |
| P-S1-5 | **Environment independence** — no time, no randomness, no hardware variance, no secret enters the computation | §8; reproducibility |
| P-S1-6 | **Single-algorithm binding** — every S1 value is bound to exactly one `s1_algorithm_id`; all comparisons (lookup, verification) occur only within equal ids | §8 prop 4; F-03 |
| P-S1-7 | **Aggregation-determinism interface** — for multi-file submissions T-1.1.3 consumes the *already-aggregated* byte sequence; the duty "same ordered set/content → same S1 under the same id" binds the **entry point's** aggregation (non-negotiable there); T-1.1.3 neither owns nor repairs it | §4 r5; §16; v1.1-C3 |

### 3.2 Input domain — included / excluded (answers TM Q2)

- **Included:** the exact bytes of the final aggregated artifact instance — nothing more, nothing less.
- **Excluded:** `received_at` (F-09) | `source_label` (F-10) | `capture_entry_metadata` (F-12) | `artifact_format_hint` (F-11) | `capture_id`, `created_at` | storage location / `artifact_ref` | integrity or lifecycle state | any content interpretation (no OCR/extraction/canonicalization) | filesystem names/timestamps of source files — **unless** the entry point's aggregation deliberately embeds them into the byte sequence, in which case they are simply part of B and the entry point's determinism duty (P-S1-7) applies; T-1.1.3 does not distinguish them.

Rationale: S1 is the identity of the *received artifact instance*. Any excluded item above is either provenance (recorded in its own fields), process state, or interpretation — none of it is content. Mixing any of it into S1 would break determinism (P-S1-1) or fabricate identity beyond D-02.

---

## 4. `s1_algorithm_id` Contract (answers TM Q3)

- **Semantics:** an immutable label that uniquely denotes the triple (algorithm, version, output encoding). Any change to any element of that triple ⇒ a **new** id (version bump). The same id denotes the same computation forever; two values under the same id are comparable, values under different ids are never compared (§8 prop 4).
- **Mandatory constraints:** non-empty whenever `s1` is present (INV-C1); immutable after attach (F-03); scopes every lookup and every verification (the record's own id is always used, §10); scopes INV-C3 — the uniqueness key is the **pair** (s1, s1_algorithm_id) (Store §9.1 P2).
- **Registry posture (MVP):** no registry service is designed. The set of executable ids is the small, versioned set embedded in the service itself. Verification/recovery can only produce verdicts for ids the service knows; an unknown id settles conservatively (§8, F2) and is surfaced. This suffices because MVP ships exactly one algorithm; a future second algorithm needs only a new id plus retained compute capability for prior ids — **no architecture change** (the pair-key model absorbs it, INV-C3 per id).
- **Literal format:** implementation choice (**OD-S2**) under the constraints above. Illustrative only: `sha256-v1`.

---

## 5. Algorithm Recommendation (answers TM "Technology")

**Architecture requirement (binding, algorithm-agnostic):** any S1 algorithm candidate MUST satisfy P-S1-1..P-S1-7; MUST be a standard, public, platform-independent specification (reproducible across processes/machines without hidden parameters); MUST provide collision resistance adequate for a content identity key; MUST be computable synchronously at ingest on a local machine within ordinary resource bounds; MUST carry no dependency that violates the local-only MVP posture (no network service, per Store G-4).

**Implementation choice (recommended minimum — declarable and replaceable at implementation dispatch, OD-S1):**

> **SHA-256 over the exact artifact byte sequence; full 256-bit digest; canonical lowercase-hex output; `s1_algorithm_id` literal of the form `sha256-v1`.**

Rationale: ubiquitous and hardware-accelerated; platform-independent with zero ambiguity; collision resistance appropriate for a capture identity key; no dependencies, no parameters, no configuration surface — the minimum that satisfies every property. Explicit notes: (i) **full digest, no truncation** — truncation would weaken the content-sensitivity margin (P-S1-2) with no MVP benefit; (ii) single pass over the bytes — no caching structures, no incremental/rolling/Merkle variants; (iii) per §16, SHA-256 is named by the Contract as an *example option*; this design *recommends* it as an implementation choice and does not freeze it — any candidate satisfying P-S1-1..7 is architecture-equivalent, because the (s1, s1_algorithm_id) key model isolates the choice and INV-C3 is enforced per id.

**MVP exclusions (explicitly not designed — no concrete requirement exists):** algorithm negotiation, multi-algorithm parallelism, algorithm registry service, distributed/probabilistic dedup structures, cross-record content-comparison collision detection, any S2/document-level notion, any persistence inside T-1.1.3.

---

## 6. Capture-Level Idempotency Flow (answers TM Q6, Q7)

Mandatory procedure — the sequential case — composed with the store lifecycle (Store Design §3):

```text
[ingest initiated]
 1. receive final aggregated byte sequence B
    (same byte sequence is handed to the store — single handoff, design rule R-S1-1)
 2. (s1, A) ← compute(B, current_algorithm_id)            [failure → §8 F1 path]
 3. lookup ← store: query COMPLETED by (s1, A)             [storage capability only]
    ┌─ hit ∧ integrity_status ≠ FAILED   (= VALID; see note 1)
    │     → duplicate-at-capture: NO second record is created;
    │       outcome = existing capture_id + duplicate marker       (§9 step 2a; logging = OD-S3)
    ├─ hit ∧ integrity_status = FAILED
    │     → explicit integrity-failure outcome (§9 step 2b; §14 r5);
    │       NO dedup success, NO new record, never silent
    └─ no hit
          → store: create ACTIVE record (record-first, Store R-1) + attach (s1, A)   [Store Steps 0/2]
          → first verification (compute capability = T-1.1.3)                        [Store Step 3]
               verdict FAILED → settle FAILED_INCOMPLETE (note: verify FAILED) + explicit failure (§7 r2, §10)
          → completion directive via store UAC                                        [Store Step 4]
               granted            → COMPLETED; ingest success
               uniqueness-conflict → settle THIS record FAILED_INCOMPLETE
                 (settlement_note: uniqueness conflict — a COMPLETED record with the same
                  (s1, s1_algorithm_id) exists) + explicit conflict outcome          (Store §9.1 P3; §7 r2)
[crash / interruption anywhere]
  → store D-1/D-2 settlement rules + §11 startup settlement (orchestration = T-1.1.5);
    recovery recompute uses the T-1.1.3 capability with the record's own A          (Store §5, §6.1)
```

**Notes:**

1. `COMPLETED` records are never `UNVERIFIED` (the store enforces the §7 r1 completion gate before `COMPLETED`; integrity then evolves only `VALID ⇄ FAILED` via verification). Therefore branch 1's "≠ FAILED" is exactly `VALID` — **no third sub-case exists**.
2. `FAILED_INCOMPLETE` and `ACTIVE` records never match the lookup (scope = `COMPLETED` only, §9 step 2). A re-ingest of content identical to a previously **failed** capture is a legal new attempt: INV-C3 constrains `COMPLETED` records only, and the failed record remains retained evidence (INV-C9).
3. **R-S1-1 (single handoff, proposed design rule):** S1 is computed over exactly the byte sequence delivered to the store — one handoff, no independent re-read of any source, no second byte path. By construction, "S1 of the submitted bytes" and "S1 of the stored content" are the same quantity, so first verification (§10) *re-proves* identity rather than re-defining it.
4. T-1.1.3 never auto-skips, auto-merges, or auto-rejects beyond these contract branches; the duplicate decision is exactly §9's three branches — **no new idempotency definition** (D-03).

---

## 7. Interaction with T-1.1.2 — UAC Preservation (answers TM Q8)

**Division of labor (restated as binding composition):**

| Act | Owner | Mechanism |
|---|---|---|
| Lookup query over stored records | T-1.1.2 provides, T-1.1.3 consumes | `COMPLETED`-restricted query (§9 step 2) |
| Idempotency **decision** (hit/miss routing) | **T-1.1.3** | §6 three-branch procedure |
| INV-C3 **enforcement** | **T-1.1.2** | UAC P1–P6; store invariant INV-S10 |
| Uniqueness-atomic `ACTIVE → COMPLETED` | T-1.1.2 | UAC primitive; every COMPLETED-producing path (P5) |
| Settlement of UAC losers / failures | T-1.1.2 primitives, triggered by T-1.1.3 directives (ingest flow) or T-1.1.5 (recovery) | §7 r2; Store §6.1 |

**Rules of composition:**

1. T-1.1.3 **never re-implements** uniqueness detection (no local caches, no pre-filtering, no secondary indexes, no Bloom filters) — the store's UAC is the single enforcement point (fail-closed P4).
2. T-1.1.3's lookup is **advisory for the decision**; UAC is the **correctness backstop**. Lookup timing cannot create a violation: two concurrent identical ingests may both miss the lookup and both create `ACTIVE` records (contract-legal — INV-C3 constrains `COMPLETED` only); UAC P1/P2 grants exactly one completion, and the loser receives P3's explicit uniqueness-conflict outcome, which T-1.1.3 settles per §6. **Correctness is independent of lookup timing by construction.**
3. T-1.1.3 issues the completion directive **only** through the store's UAC primitive; no bypass path exists in this design.
4. The S1 attach (Store Step 2), first verification (Store Step 3), and recovery recompute (Store §5 step b) consume the T-1.1.3 capability; the store owns recording, gating, and durability at every point.

---

## 8. Collision Semantics (answers TM Q5)

- **Position:** with the recommended cryptographic algorithm (§5), two distinct byte sequences producing the same S1 under the same `s1_algorithm_id` is practically negligible but not logically impossible. The Contract already fixes the disposition — T-1.1.3 has no discretion here.
- **Mandatory disposition:** observation of an S1 collision (different contents, same S1 within one id) → **Issue Report via STOP Protocol**; never a forced reject, merge, or skip of the second record (§14 r9). The store's F7 behavior and T-1.1.3's are the same disposition at their respective layers.
- **MVP scope note:** no collision-*detection* machinery (cross-record content comparison) is designed. No contract clause requires it; adding it would violate the MVP rule. Detection remains emergent (e.g., a future verification anomaly) and is handled by the fixed disposition above.
- **Risk reference:** RSK-3 (algorithm choice quality affects false hit/miss) — owned here via the §5 property constraints and the AC-1.1.2 tests; the store is unaffected (opaque `s1`).

---

## 9. Failure Matrix (answers TM Q9)

| # | Failure | Required T-1.1.3 behavior | Contract / Store anchor |
|---|---|---|---|
| F1 | S1 computation cannot complete (digest capability failure; input unavailable at compute point) | ingest cannot complete → the record settles `FAILED_INCOMPLETE` + `settlement_note` (s1 computation failed) + `integrity_status = FAILED`; **no `COMPLETED` record without S1 exists** (INV-C1); explicit failure surfaced | §14 r2; §7 r2; Store §6.1 D-1 |
| F2 | Unknown/unsupported `s1_algorithm_id` encountered at verification or recovery (version skew) | no verdict is computable → conservative settlement `FAILED_INCOMPLETE` (never `COMPLETED`); surface via Issue Report (STOP Protocol) — indicates upgrade/version-skew defect | §10; §11; Store §5 note; Store §6.1 |
| F3 | Lookup hit ∧ `integrity_status = FAILED` | explicit integrity-failure outcome; **never dedup success**; no new record; never silent | §9 step 2b; §14 r5; INV-F7 |
| F4 | UAC uniqueness-conflict on completion (concurrent identical ingest lost the atomic decision) | settle this record `FAILED_INCOMPLETE` (note: uniqueness conflict) + explicit conflict outcome to the caller; never a second `COMPLETED`; never silent | Store §9.1 P3; §7 r2; Store §6.1 |
| F5 | First verification verdict = `FAILED` | completion gate unmet (§7 r1) → synchronous settlement `FAILED_INCOMPLETE` (note: verify FAILED) + explicit failure; record retained as evidence | §7 r1/r2; §10 |
| F6 | S1 collision observed (different contents, same S1, same id) | Issue Report via STOP Protocol; no merge/reject/skip | §14 r9; §8 above |
| F7 | Determinism violation observed (same (B, A) yielding different S1 across runs) | STOP Protocol issue report; implementation dispatch blocked until resolved — this is a defect against INV-C2/P-S1-1, not a runtime branch | §8 prop 1; INV-C2 |

---

## 10. Invariants

Service-level invariants (INV-F series) — all contract invariants are additionally inherited as binding (in particular INV-C1, INV-C2, INV-C3, INV-C7, INV-C8, INV-C10), as are the store invariants INV-S9/INV-S10 by composition:

| ID | Invariant | Verifiable with |
|---|---|---|
| INV-F1 | For any fixed byte sequence B and algorithm id A, `compute(B, A)` returns the identical S1 on every execution, across restarts and processes | property test, cross-restart reproducibility test (INV-C2, AC-1.1.2) |
| INV-F2 | Any single-byte change to B changes the returned S1 | mutation test (INV-C2, AC-1.1.2) |
| INV-F3 | Every S1 produced is accompanied by exactly one `s1_algorithm_id`, and the pair is attached immutably to the record | record inspection (F-02/F-03, INV-C1) |
| INV-F4 | Duplicate-decision lookups consider `COMPLETED` records only; `ACTIVE` and `FAILED_INCOMPLETE` records never produce a hit | lookup scope test (§9 step 2) |
| INV-F5 | T-1.1.3 never creates a second `COMPLETED` record for an existing (s1, s1_algorithm_id): all completions route exclusively through the store's UAC primitive | concurrent duplicate-submission test (INV-C3; Store INV-S10, AC-T112-10) |
| INV-F6 | No T-1.1.3 output carries external-document identity, canonical invoice identity, or any downstream-domain datum | inspection (D-02, INV-C7 analog) |
| INV-F7 | A lookup hit on an integrity-`FAILED` record never produces a dedup-success outcome | duplicate-after-FAILED test (§9, §14 r5) |

---

## 11. Acceptance Criteria (T-1.1.3 level)

Executable only at implementation; evidence registered per the Acceptance Register chain. WP ACs AC-1.1.2/1.1.3/1.1.4 (owner: T-1.1.3) remain PENDING — no fabrication.

| ID | Criterion | Maps to |
|---|---|---|
| AC-T113-1 | Property test: ≥2 identical inputs → identical S1 across repeated runs and restarts; mutation test: single-byte flip → different S1 | AC-1.1.2; INV-F1/F2; INV-C2 |
| AC-T113-2 | Every stored record carries exactly one S1 value + non-empty `s1_algorithm_id`; lookup by (s1, s1_algorithm_id) returns a deterministic result (repeated queries → identical answers) | AC-1.1.3; INV-F3/F4; INV-C1 |
| AC-T113-3 | Duplicate submission test: re-submitting identical content returns the existing `capture_id` + duplicate marker; no second `COMPLETED` record exists for the key | AC-1.1.4; §9 step 2a; INV-C3 |
| AC-T113-4 | Re-capture after the matching `COMPLETED` record became integrity-`FAILED` → explicit integrity-failure outcome; never dedup success | §9 step 2b; §14 r5; INV-F7 |
| AC-T113-5 | Lookup scope test: `ACTIVE` and `FAILED_INCOMPLETE` records never match; a re-ingest after a `FAILED_INCOMPLETE` settlement of identical content proceeds as a legal new attempt | §9 step 2; INV-F4 |
| AC-T113-6 | Concurrency test: N concurrent ingests of identical content → at most one `COMPLETED`; every loser receives an explicit uniqueness-conflict outcome and settles with a uniqueness-conflict note | Store §9.1 (UAC); INV-F5; Store AC-T112-10 (AC-1.1.4 support) |
| AC-T113-7 | Boundary inspection: no T-1.1.3 output contains external-document identity, canonical identity, or downstream-domain data; algorithm choice + `s1_algorithm_id` literals declared in the implementation task report | INV-F6; D-02; §16 (DoD) |

---

## 12. Dependencies

| On | Nature | Detail |
|---|---|---|
| T-1.1.1 | build-time, satisfied | Contract v1.1 FINAL FREEZE APPROVED — sole normative source for S1 semantics (§8), idempotency (§9), verification (§10); this design modifies nothing in it |
| T-1.1.2 | build-time design, satisfied (v0.2 FINAL APPROVED) + runtime composition | consumed capabilities: `COMPLETED`-restricted lookup, UAC (P1–P6), record creation (R-1), S1 attach (Step 2), verdict recording (restricted writer), settlement primitives (§6.1); Task Register line "T-1.1.1 (DONE) \| integration with T-1.1.2" — confirmed |
| Capture entry point | runtime interface | delivers the final aggregated byte sequence; owns aggregation determinism (§4 r5, v1.1-C3) — consumed, not owned, per P-S1-7 |
| T-1.1.4 | future runtime composition | verify-on-read wiring consumes the compute capability; not designed here |
| T-1.1.5 | future runtime composition | recovery orchestration consumes the compute capability (Store §5 step b); not designed here |
| Task Register | consistent | T-1.1.3 Out of Scope honored: no S2/document-level dedup, no semantic interpretation, no extraction, no S1 redefinition, no Holoo |

---

## 13. Open Decisions / Delegations (answers TM Q11)

Every item below is an **implementation-level decision, not an architecture decision** (D-09, §16); each must be declared in the T-1.1.3 implementation task report under "Delegated Implementation Detail Decisions".

| ID | Item | Mandatory constraints |
|---|---|---|
| OD-S1 | Concrete S1 algorithm + output encoding | MUST satisfy P-S1-1..P-S1-7; §5 recommendation is the default candidate; final choice + literal declared in the task report (§16: examples like SHA-256 are options, not decisions) |
| OD-S2 | `s1_algorithm_id` literal format | immutable meaning; version bump on any algorithm/version/encoding change; non-empty; comparison-scoping per §8 prop 4 |
| OD-S3 | Duplicate-attempt logging | optional (§16); must not violate INV-C3; shared scope with Store OD-6 — implemented at most once, not twice |

**Blocking open decisions: none.** Every question raised by the TM mission is resolved above at the architecture level; the remaining items are implementation details with binding constraints, per D-09.

---

## 14. Risks and Unresolved Ambiguities

| ID | Item | Type | Disposition |
|---|---|---|---|
| R-1 | Version skew: records written by a future algorithm id that a later installation cannot execute | Risk (future-facing) | MVP ships one algorithm; rule: any future algorithm addition must retain compute capability for all previously issued ids, or accept conservative `FAILED_INCOMPLETE` settlements (§9 F2) + Issue Report. No architecture change needed (pair-key model absorbs it) |
| R-2 | S1 collision probability | Negligible (cryptographic recommendation) | Fixed contract disposition (§14 r9 / §8 above); no detection machinery in MVP |
| R-3 | OI-1 / RSK-2: Baseline documents not yet committed to `kandoo/baseline/` | Tracked (pre-existing) | Non-blocking; STOP Protocol applies if a contradiction surfaces after commit |
| R-4 | Aggregation determinism (v1.1-C3) depends on the capture entry point, not on T-1.1.3 | Interface risk | Locked by Contract on the entry point (§16); if violated, duplicate recognition degrades at capture level — surfaced by later property tests; resolution path = Issue Report (STOP), never silent handling in T-1.1.3 |

None of the above blocks this design; none requires reopening a Frozen Decision.

---

## 15. Answers to the 11 TM Questions (cross-reference)

| # | Question | Answer location |
|---|---|---|
| 1 | Required properties of S1 | §3.1 (P-S1-1..P-S1-7) |
| 2 | Included/excluded from S1 input | §3.2 |
| 3 | `s1_algorithm_id` contract | §4 |
| 4 | Determinism requirements | §3.1 (P-S1-1, P-S1-4, P-S1-5); INV-F1; AC-T113-1 |
| 5 | Collision semantics | §8 |
| 6 | Lookup semantics | §6 step 3; §1 (capability vs decision); INV-F4 |
| 7 | Duplicate handling (three cases) | §6 branches + notes 1–2 (hit+VALID → duplicate-at-capture; hit+FAILED → explicit integrity-failure path; miss → create-and-continue) |
| 8 | Interaction with T-1.1.2 UAC | §7 (decision vs enforcement split; concurrency story; no bypass) |
| 9 | Failure cases | §9 (F1–F7) |
| 10 | Minimum acceptance tests | §11 (AC-T113-1..7) |
| 11 | Genuinely blocking open decisions | §13 — none |

---

## Closing Verification (document-level, no execution)

| Check | Result |
|---|---|
| Derived exclusively from Contract v1.1 + Store Design v0.2 + Registers; no frozen rule redefined, weakened, or bypassed | PASS |
| MVP discipline: no speculative algorithms, no registry/distributed/probabilistic machinery, no persistence inside T-1.1.3, no complexity without a concrete requirement | PASS |
| INV-C3 preserved: decision (T-1.1.3) / enforcement (T-1.1.2 UAC) split explicit; no bypass path; concurrency correctness independent of lookup timing | PASS |
| No external-document or canonical identity created, stored, or interpreted (D-02) | PASS |
| Algorithm recommendation distinguished from architecture requirement; §16 honored (SHA-256 = option, not frozen decision) | PASS |
| No storage technology / schema / migration / API / product code produced | PASS |
| Responsibility boundaries vs T-1.1.2 / T-1.1.4 / T-1.1.5 explicit; no task's responsibilities moved | PASS |
| All 11 TM questions answered; deliverable sections complete (boundary, S1 contract, algorithm recommendation, idempotency flow, failure matrix, invariants, acceptance criteria, dependencies, open decisions) | PASS |

```text
Change Log: v1.0 — 2026-10-01 — initial architecture design by T-1.1.3 design step (no code, no schema, no migration, no storage-technology selection).
Status: PROPOSED — READY FOR TECHNICAL MANAGER FINAL REVIEW; becomes binding design for T-1.1.3 implementation upon approval.
```

