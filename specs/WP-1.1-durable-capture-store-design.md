# WP-1.1 — Durable Local Capture Store — Architecture Proposal (T-1.1.2)

```text
Proposal ID:   DES-WP11-T112-STORE | Version: 0.2 | Date: 2026-10-01 | Status: PROPOSED — revised per TM review (Issues 1–2 resolved); READY FOR TECHNICAL MANAGER FINAL REVIEW
Revision:      v0.2 — two TM-mandated corrections (R1 deterministic persistence-failure settlement; R2 INV-C3 concurrency-safe uniqueness guarantee) + related tightenings. No new lifecycle state; no storage technology selected; no Frozen Decision reopened.
Task:          T-1.1.2 — Durable Local Capture Store (design step; Architecture Review / Pre-Freeze)
Authority:     SPEC-WP11-CRC — Capture Record Contract v1.1 (FINAL FREEZE APPROVED by TM Final Contract Review)
               Locked Decisions D-02, D-03, D-09 (kandoo/registers/decision-register.md)
               G1 Architecture Approval: PASS | G2 Work Package Approval for WP-1.1: APPROVED
Binding for:   T-1.1.2 implementation dispatch (after TM approval); integration boundaries stated for T-1.1.3/T-1.1.4/T-1.1.5.
Change Control: فقط از مسیر STOP Protocol → Issue Report → TM Review → PO Decision (D-09)
Constraints:   No product code | No migration | No executable schema | No storage-technology selection | No API design.
Missing Input: kandoo/baseline/ خالی است (MNT-1 / RSK-2 / OI-1) — Decision Register remains interim SSOT; zero guessing.
```

---

## 0. Normative Basis (what this design consumes, verbatim)

This proposal is derived exclusively from:

| Source | Used for |
|---|---|
| Contract v1.1 §3–§6 | Record/Artifact definition; 14-field set; Provable-Data Rule; mutability classes |
| Contract v1.1 §7 | Lifecycle `ACTIVE \| COMPLETED \| FAILED_INCOMPLETE`; 6 transition rules; orthogonal integrity axis |
| Contract v1.1 §8 | S1 = Capture Identity; deterministic + content-sensitive; algorithm delegated, recorded via `s1_algorithm_id` |
| Contract v1.1 §9 | Idempotency: key = S1; lookup restricted to `COMPLETED`; FAILED-hit ≠ dedup success |
| Contract v1.1 §10 | verify operation; verify-on-read; definitive verdict on every content read |
| Contract v1.1 §11 | Startup scan; settlement rule; idempotent recovery; no external retry |
| Contract v1.1 §13 | INV-C1..C10 — all inherited as binding constraints on the store |
| Contract v1.1 §14 | 9 failure modes — mandatory store behavior |
| Contract v1.1 §16 | 8 delegation items with mandatory constraints |
| D-02 / D-03 / D-09 | Identity model; idempotency definition; freeze governance |
| WP-1.1 / Task Register | AC-1.1.1, AC-1.1.6 (primary), AC-1.1.7 (support); T-1.1.2 Out of Scope |

No contract rule is restated differently here; where this document adds a rule, it is labeled **R-* (design rule, proposed)** or **OD-* (open/delegated decision)** and does not modify the contract.

---

## 1. Responsibility Boundary

**T-1.1.2 owns (full responsibility):**

1. **Capture Record durability** — persistent local storage of the 14-field record (v1.1 §5); creation, §7 state transitions, §6-restricted field updates.
2. **Artifact durability** — persistent local storage of the artifact byte sequence exactly as delivered by the capture entry point (post-aggregation input, per §4 and v1.1-C3).
3. **Record↔artifact atomic binding** — `artifact_ref` (§4 rule 4) with write-ahead ordering (design rule R-2, §7 below).
4. **Transition & settlement mechanics** — store primitives that execute §7 transitions and §11 settlements atomically, idempotently, and — for every transition that can produce `COMPLETED` — uniqueness-atomically (UAC, §9.1).
5. **Persistence failure handling** — §14 rows 1, 2, 4, 8 behaviors with the deterministic settlement rule of §6.1.
6. **Retrieval support** — byte-exact content read via `artifact_ref`; record read by `capture_id`; lookup capability by (`s1`, `s1_algorithm_id`) restricted to `COMPLETED` (§9 support); enumeration of `ACTIVE` leftovers (§11 support).
7. **Verification support** — faithful content access + restricted write path for `integrity_status`/`integrity_verified_at` (§6 class 3) + enforcement of the §7 rule 1 completion gate.

**T-1.1.2 does NOT own:**

- S1 computation (T-1.1.3 — §8) | Idempotency decision procedure & duplicate response semantics (T-1.1.3 — §9) | Verify-on-read read-path wiring (T-1.1.4 — §10 read semantics) | Scan+settlement orchestration (T-1.1.5 — §11 execution) | Retention/privacy (DEF4 / WP-1.3) | Crash-matrix hardening beyond contract minimum (WP-1.3) | Anything downstream, cloud, Holoo (D-04), API/UI (D-09).

**Concept separation (mission-required):**

| Concern | Owner | Store's role (T-1.1.2) |
|---|---|---|
| Capture Record durability | **T-1.1.2** | full |
| Artifact durability | **T-1.1.2** | full |
| S1 calculation | T-1.1.3 | none — stores opaque `s1` value + `s1_algorithm_id` label |
| S1 lookup / idempotency decision | T-1.1.3 | provides lookup capability on `COMPLETED` only; enforces uniqueness-atomic completion (UAC, §9.1); never decides hit/miss/response |
| Integrity verification (compute) | T-1.1.3 | none — receives verdicts as restricted writes |
| Verify-on-read enforcement | T-1.1.4 | provides content fidelity + verdict recording primitives |
| Downstream processing | later WPs (P2+) | none — no physical lineage field exists (v1.1-C1) |

**Boundary vs T-1.1.3 (explicit):** the store answers the query "which COMPLETED records carry (s1, s1_algorithm_id)?" T-1.1.3 decides what that answer *means* (duplicate-at-capture, explicit integrity-failure path, or miss → new record). The store never auto-skips, auto-merges, or auto-rejects. For INV-C3 concurrency the split is explicit (v0.2): **T-1.1.2 provides the storage-level invariant/enforcement capability** (UAC, §9.1); **T-1.1.3 owns the idempotency decision and orchestration** on top of it; the store treats (`s1`, `s1_algorithm_id`) as opaque values and **never interprets S1 semantically**.

**Boundary vs T-1.1.5 (explicit):** the store guarantees that leftover `ACTIVE` records are enumerable and that settlement transitions are safe and idempotent primitives. T-1.1.5 owns the startup orchestration that calls them.

---

## 2. Inputs and Outputs

Contract-level roles only (no API/signature design — D-09).

**Inputs:**

| Input | Fields / Content | Source | Contract anchor |
|---|---|---|---|
| Ingest initiation | final aggregated byte sequence (aggregation + its determinism owned by entry point) | capture entry point | §4, §16, v1.1-C3 |
| Capture event metadata | `received_at` (F-09), `source_label` (F-10, or `UNDECLARED`), `capture_entry_metadata` (F-12, verbatim), `artifact_format_hint` (F-11, optional mechanical, or `UNKNOWN`) | capture entry point | §5 |
| S1 attach | opaque `s1` value + `s1_algorithm_id` | T-1.1.3 | §8, F-02, F-03 |
| Verification outcome write | verdict ∈ {`VALID`, `FAILED`} + timestamp | T-1.1.3 (compute) / T-1.1.4 (wiring) | §10, §6 class 3 |
| Transition directive | completion bundle per §7 rule 1; settlement directive per §11 (with `settlement_note`) | ingest flow / recovery (T-1.1.5) | §7, §11 |
| Queries | by `capture_id`; by (`s1`, `s1_algorithm_id`) restricted to `COMPLETED`; enumerate `ACTIVE` | T-1.1.3 / T-1.1.4 / T-1.1.5 | §9, §11 |

**Outputs:**

- Durable Capture Record (14 fields, v1.1) bound to its artifact via `artifact_ref`.
- Byte-exact artifact content retrieval via `artifact_ref` (any state where content exists).
- Deterministic lookup results; `ACTIVE` scan results.
- Persistence outcome: success or an explicit §14 failure mode — never a silent drop, never a partial-valid record; every persistence failure follows the deterministic settlement rule (§6.1).
- Completion-transition outcome (v0.2): `COMPLETED` granted atomically, or an explicit uniqueness-conflict rejection (UAC, §9.1) — never an ambiguous or conditional grant.

---

## 3. Persistence Lifecycle

Reference ordering (mechanism-free; concrete ordering mechanics are OD-4):

```text
[ingest accepted]
  Step 0  record created in ACTIVE  (R-1: record-first)
  Step 1  artifact content persisted durably, byte-exact; artifact_size_bytes finalized (F-13)
  Step 2  s1 + s1_algorithm_id attached (from T-1.1.3)
  Step 3  first verification executed → verdict VALID | FAILED   (T-1.1.3/T-1.1.4)
  Step 4  ACTIVE → COMPLETED  iff  content durable ∧ s1 attached ∧ verdict = VALID   (§7 rule 1)
[any failure / crash at any step]  →  startup settlement per §11 → COMPLETED | FAILED_INCOMPLETE
```

- **R-1 (record-first, proposed design rule):** the `ACTIVE` record is created before artifact content persist. Rationale: every ingest the store observes leaves a settleable record trail; §14 row 1 ("از دست‌رفتن بی‌صدا ممنوع") and §11 completeness become enforceable inside the store. If record creation itself fails, nothing is persisted and the ingest ends in explicit failure — no store residue.
- **R-2 (write-ahead completion, proposed design rule):** content durability strictly precedes the `COMPLETED` transition. A crash can therefore never produce a `COMPLETED` record whose content is not already durable — the class of "COMPLETED but unreadable" is excluded by construction, not by after-the-fact detection.
- **Persistence failure after the record exists (v0.2)** is governed by the deterministic settlement rule (§6.1): definitive persist errors settle synchronously to `FAILED_INCOMPLETE`; `ACTIVE` residue arises only when no verdict can be durably recorded (interruption / settlement-write failure) and is settled by startup recovery. `ACTIVE` is never a design-chosen post-failure parking state.
- Post-`COMPLETED`: `integrity_status`/`integrity_verified_at` continue to evolve independently via verification only (§7 rule 4, §6 class 3); content and `artifact_ref ↔ S1` binding are immutable (§4 rule 3).
- `FAILED_INCOMPLETE`: terminal; requires `settlement_note`; `integrity_status = FAILED` pinned at settlement (v1.1-C2); retained, never presented valid, never silently deleted (INV-C9).
- No deletion, no re-open (§7 rule 5). Retention hooks: none in this phase (DEF4 / WP-1.3) — the design must simply not preclude them.

---

## 4. Crash/Restart Behavior

Crash windows under the reference ordering (each maps to a §11-settleable end state):

| Window | Crash point | Residue at restart | Settlement (§11) |
|---|---|---|---|
| W1 | before record creation | none (ingest not observable by store) | — (entry point owns user-facing error) |
| W2 | after record creation, before/during content persist | `ACTIVE` record, missing/partial content | `FAILED_INCOMPLETE` + note (content missing/unreadable) + `integrity_status = FAILED` |
| W3 | content durable, before S1 attach | `ACTIVE` record, readable content, no `s1` | `FAILED_INCOMPLETE` + note (s1 missing) — identity not provable, so completion precondition unmet (§7 rule 1) |
| W4 | S1 attached, before first verification | `ACTIVE` record, content + `s1` present, no verdict | run verification; completion executes through the UAC primitive (§9.1): `VALID` ∧ uniqueness-satisfied ⇒ `COMPLETED`; otherwise `FAILED_INCOMPLETE` + note |
| W5 | after `COMPLETED` | durable record + content | none — restart read is transparent (AC-1.1.6) |

Guarantees across all windows:

1. Startup enumeration of `ACTIVE` leftovers is always possible (store guarantee); orchestration = T-1.1.5. INV-C6 is **binding, not aspirational** (v0.2): recovery processing is complete *iff* zero `ACTIVE` records remain (see §6.1 point 4).
2. Settlement has exactly two endings, both explicit and retained (§11; v1.1-C2).
3. Recovery is idempotent — repeated runs change nothing (§11 rule 4).
4. No re-fetch from external sources, ever (§11 rule 5).
5. No third "inconsistent presentation" state exists: any content byte in the store is bound to a record (R-1) and any record is in a defined state or gets settled.
6. Post-failure determinism (v0.2): every persistence failure after record creation follows exactly one deterministic settlement path — D-1 synchronous `FAILED_INCOMPLETE`, or D-2 residue settled at startup recovery (§6.1). No design-chosen `ACTIVE` parking state exists.

---

## 5. Recovery Algorithm (contract level)

Orchestration belongs to T-1.1.5; the algorithm is fixed by §11 and restated here for boundary clarity:

```text
scan:        R ← all records with capture_state = ACTIVE
for each R (order-independent; results are per-record):
  a. content ← read(artifact_ref) if artifact_ref present
  b. if content readable ∧ s1 attached ∧ verify(content, s1, s1_algorithm_id) = VALID
        ∧ uniqueness precondition holds: no other COMPLETED record exists with the
          same (s1, s1_algorithm_id)        [checked atomically — UAC, §9.1]
        → transition R to COMPLETED (+ integrity VALID, integrity_verified_at)
  c. else
        → transition R to FAILED_INCOMPLETE
          + settlement_note ∈ {content missing/unreadable | s1 missing | verify FAILED | persistence incomplete | uniqueness conflict: a COMPLETED record with the same (s1, s1_algorithm_id) exists}
          + integrity_status = FAILED   (v1.1-C2 pin, at settlement moment)
post:        no record remains ACTIVE (INV-C6); every settlement explicit + retained (INV-C9)
idempotence: transitions are terminal-state writes; re-running the scan is a no-op
forbidden:   any re-fetch/retry toward external sources (§11 rule 5)
```

Note: step (b) requires the verification capability to be present at recovery time — by composition, T-1.1.3's S1 service (see §13). If verification cannot yield a verdict, the only contract-legal ending is `FAILED_INCOMPLETE` (conservative), never `COMPLETED`. The uniqueness precondition added to step (b) (v0.2) reconciles §11 r2 with the always-binding INV-C3: without it, recovery itself could mint a second `COMPLETED` record for a key. This is an **additive tightening, not a weakening of §11** — §11 r2 grants completion only when a *contract-legal* completion is possible, and a completion that would violate INV-C3 is not contract-legal.

---

## 6. Failure Matrix

| # | Failure | Required store behavior | Contract anchor |
|---|---|---|---|
| F1 | Content persist failure (IO / space / permission) | **Deterministic two-class settlement (§6.1, v0.2):** **D-1** — definitive persist error returned to the live store ⇒ record settles **synchronously** to `FAILED_INCOMPLETE` + cause-specific `settlement_note` + `integrity_status = FAILED`; explicit failure surfaced; **never left `ACTIVE` by this class**. **D-2** — verdict not durably recordable (interruption / settlement-write failure) ⇒ record remains `ACTIVE` solely as recoverable residue, settled by the next startup recovery (§5). **No partial-valid record; no design-chosen `ACTIVE` parking state; no silent loss.** | §14 r1/r8; §7 r2; §6.1 |
| F2 | Record-creation persist failure | nothing persisted; ingest ends in explicit failure at the store boundary; no content-only residue (R-1) | §14 r1 |
| F3 | Crash mid-content-write | partial bytes exist but are bound to an `ACTIVE` record (R-1) → settled `FAILED_INCOMPLETE`; partial bytes never presented as evidence | §14 r4, §11 |
| F4 | Crash between stages W2–W4 | per §4 table — always a §11-settleable end; settlement executes through the UAC primitive (§9.1) | §11, §9.1 |
| F5 | Read failure (content missing/corrupt) on retrieval or verification | verdict `FAILED` **with reason**; never a silent broken read; no auto-repair, no delete, no content rewrite; resolution path = Issue Report only | §10, §14 r3 |
| F6 | Duplicate lookup hit on integrity-`FAILED` record | store returns the record faithfully; T-1.1.3 routes it to the explicit integrity-failure path — never dedup success | §9, §14 r5 |
| F7 | S1 collision observation (different contents, same S1) | store performs **no** merge/reject/skip; report as issue via STOP Protocol | §14 r9 |
| F8 | Space exhaustion / storage access loss | D-1 class definitive error (§6.1): synchronous `FAILED_INCOMPLETE` settlement when any durable write is still possible; if storage is wholly unavailable, D-2 residue + explicit store-unavailable failure state (recovery is **not** reported complete; §6.1 point 4); no record can be observed as valid; never silent | §14 r8; §6.1 |
| F9 | Field-update violation (write outside §6 mutability class / illegal transition) | rejected by the store — mutability classes and §7 transitions are store-enforced, not convention | §6, §7 |

### 6.1 Deterministic Persistence-Failure Settlement (TM Review Issue 1, v0.2)

Contract §14 r1 deliberately allows two endings for an ingest-time persistence failure after the record exists («...یا در `ACTIVE` برای recovery می‌ماند یا با `FAILED_INCOMPLETE` + note تسویه می‌شود»). Leaving that choice open is non-deterministic. This design fixes the choice with an exhaustive two-class rule. **No new lifecycle state is introduced** — only the three §7 states are used, and every `FAILED_INCOMPLETE` ending satisfies §7 r2 + v1.1-C2 (`settlement_note` + `integrity_status = FAILED` pinned at settlement).

**Classification rule (exhaustive — no third class):**

| Class | Condition | Deterministic settlement |
|---|---|---|
| **D-1 — definitive persist error** | A persistence operation **returns a definitive failure verdict to the live store** (I/O error, permission denied, space exhaustion, device error). | The store settles **synchronously, inside the same ingest attempt**: `ACTIVE → FAILED_INCOMPLETE` + cause-specific `settlement_note` + `integrity_status = FAILED` (anchor: §7 r2 «خطای ingest رخ داده»; §14 r1/r8), then surfaces the explicit failure to the ingest caller. **The record is never left `ACTIVE` by this class.** |
| **D-2 — unverdictable interruption** | The store **cannot durably record any verdict**. Exactly two sub-conditions: (a) process crash/termination before or during any ingest step after record creation (the persistence call never returned a verdict); (b) the D-1 settlement write itself fails or is interrupted. | The record remains `ACTIVE` **solely as recoverable residue** — never as a design-chosen parking/waiting state — and is guaranteed to be enumerated and settled by the §11 startup scan (§5 algorithm). |

**Answers to the four review points:**

1. **Which failure conditions may leave a record temporarily `ACTIVE`:** only Class D-2. Every definitive persist error observable by a live store is D-1 and settles synchronously. Internal local-write retry between the two classes (how often, how) is a delegated detail (OD-4); the architecture-level outcome set is exactly {synchronously settled (D-1), residue settled at recovery (D-2)} — both deterministic, both contract-legal.
2. **When the record becomes `FAILED_INCOMPLETE`:** D-1 — immediately, within the failing ingest attempt. D-2 — at the next startup recovery, as a deterministic function of the durable state the scan finds (§5): content durable ∧ readable ∧ `s1` attached ∧ verification `VALID` ∧ uniqueness satisfied → `COMPLETED`; otherwise → `FAILED_INCOMPLETE` + `settlement_note` + `integrity_status = FAILED`.
3. **If the process crashes before settlement:** the crash is itself a D-2 condition. Residue = one `ACTIVE` record; nothing is lost silently; the next startup scan settles it (idempotently, §11 r4). Until settlement, the record is never presented as valid evidence and never presented as resolved.
4. **No indefinite `ACTIVE` after recovery — confirmed:** recovery processing is complete **if and only if** the scan enumerates zero `ACTIVE` records (INV-C6; store INV-S6 — binding, not aspirational). If storage unavailability prevents settlement writes, the store does **not** report recovery complete: it enters an explicit store-unavailable failure state, surfaces the error (STOP Protocol for operators), and performs no read or presentation of unresolved records. Therefore no *completed* recovery ever coexists with `ACTIVE` residue, and no unresolved `ACTIVE` record is ever presented as valid (INV-C9).

---

## 7. Durability Guarantees

| ID | Guarantee | Testable via |
|---|---|---|
| G-1 | A `COMPLETED` record implies: content durable + byte-exact readable + `s1` attached + first verification `VALID` — preserved across restart | AC-1.1.1, AC-1.1.6 tests |
| G-2 | Write-ahead completion (R-2): `COMPLETED` is unreachable while content is not yet durable | crash-injection across W2–W4 |
| G-3 | Every record in any state survives process termination/restart and is readable afterwards | AC-1.1.1 restart test |
| G-4 | Local-only durability: no network-service dependency; no cloud replication (out of scope) | inspection (§16 storage constraints) |
| G-5 | Every persist failure ends in an explicit failure mode — no silent loss | §14 test matrix |

**Durability boundary:** the store guarantees survival across process crash/termination and graceful restart. **Failure boundary:** corruption or loss at the storage-device level is *detected* (verification → `FAILED`) and *surfaced*, never repaired or hidden; repair is out of scope (§10 rule 4).

---

## 8. Immutability Guarantees

| ID | Guarantee | Contract anchor |
|---|---|---|
| I-1 | Post-`COMPLETED` artifact content is byte-immutable through the store: no rewrite, no repair, no delete path exists | §4 r3, §10 r4, INV-C4 |
| I-2 | `artifact_ref ↔ S1` binding is immutable post-`COMPLETED` | §4 r3 |
| I-3 | Field mutability classes (§6) are store-enforced: creation-time fields immutable; F-06 only via §7 transitions; F-07/F-08 only via verification; F-15 only at settlement | §6 |
| I-4 | `FAILED_INCOMPLETE`: terminal, retained, never presented valid, `integrity_status = FAILED` pinned | v1.1-C2, INV-C9 |
| I-5 | The store's record structure contains **no physical downstream-lineage field**; extension only via change control (D-09) | v1.1-C1 (Extensibility Reservation) |

---

## 9. Interaction with S1 / Idempotency

- The store treats `s1` as an **opaque value** and `s1_algorithm_id` as its label; it never computes, compares semantics of, or interprets fingerprints (T-1.1.3's domain, §8).
- The store provides **lookup capability restricted to `capture_state = COMPLETED`** (§9 procedure step 2) and **enforces the INV-C3 guarantee unconditionally** (v0.2): at most one `COMPLETED` record per (`s1`, `s1_algorithm_id`), under any concurrency, via the UAC property (§9.1).
- Enforcement mechanism for INV-C3 = **OD-5** (delegated), but any delegated mechanism must realize the full UAC property set P1–P6 (§9.1); the guarantee itself is mandatory, unconditional, and testable. Correctness no longer relies on any single-writer assumption (v0.2; see A-2).
- The idempotency **decision** — hit-with-non-FAILED → duplicate-at-capture response (existing `capture_id` + duplicate marker); hit-with-`FAILED` → explicit integrity-failure path; miss → new `ACTIVE` record — is T-1.1.3's §9 orchestration. The store provides results and primitives only; it never auto-skips creation or auto-merges records.
- Logging of duplicate ingestion attempts = optional (§16) — **OD-6**.

### 9.1 INV-C3 Concurrency-Safety Guarantee — Uniqueness-Atomic Completion, UAC (TM Review Issue 2, v0.2)

**Mandatory architecture-level guarantee:** the Durable Local Capture Store **MUST provide a concurrency-safe mechanism such that two concurrent capture attempts with the same (`s1`, `s1_algorithm_id`) cannot both become `COMPLETED`.** INV-C3 is a binding contract invariant; the store enforces it **unconditionally** — regardless of caller discipline, number of concurrent callers, or scheduling. No single-writer/serialized-access assumption is load-bearing (no Frozen Decision establishes one; see A-2).

The guarantee is specified **abstractly (technology-free)**. Its concrete mechanism is delegated (OD-5) and must realize **all** of the following properties:

| # | Property (abstract) | Meaning |
|---|---|---|
| P1 | **Atomic decision point** | The `ACTIVE → COMPLETED` transition is one indivisible store operation that (i) establishes non-existence of any `COMPLETED` record with the same (`s1`, `s1_algorithm_id`) and (ii) commits the completion — with no observable interleaving between (i) and (ii) for any concurrent operation. |
| P2 | **Uniqueness under concurrency** | For every key K = (`s1`, `s1_algorithm_id`), at most one record is **ever** transitioned to `COMPLETED` with K, whatever the number, timing, or interleaving of concurrent attempts. INV-C3 holds by enforcement, not by convention. |
| P3 | **Explicit loser outcome** | A completion that loses the atomic decision is rejected with an explicit **uniqueness-conflict** outcome; the losing record never becomes `COMPLETED`. Its settlement follows §7 r2: synchronously via a settlement directive (note: uniqueness conflict), or as D-2 residue (§6.1) settled at startup recovery. Never silent, never merged, never dropped (INV-C9). |
| P4 | **Fail-closed** | If the store cannot execute the atomic decision (e.g., storage unavailable), the completion fails explicitly; completion is never granted tentatively or optimistically. |
| P5 | **Uniform enforcement** | Every path that can produce `COMPLETED` — ingest-time completion (§7 r1) and recovery settlement (§11 r2 via §5 step b) — executes through the same uniqueness-atomic primitive; no side path exists. |
| P6 | **Key opacity** | The key is compared as opaque byte values within an equal `s1_algorithm_id` label; the store derives **no semantic identity** («same document») from a match (D-02: document-level identity belongs to Identity Resolution, P6/P7 — outside Capture). |

**Consequences that keep Contract §9 exactly intact:**

- Two concurrent ingest attempts whose §9 lookups both miss may legitimately create **two transient `ACTIVE` records** carrying the same key — contract-legal, because INV-C3 constrains `COMPLETED` records only. UAC (P1–P2) then guarantees at most one of them completes; the loser receives P3's explicit outcome and settles `FAILED_INCOMPLETE` (or is D-2 residue). §9's decision procedure is untouched; UAC is the storage-level backstop that makes it sound under races.
- The store still never auto-skips, auto-merges, or auto-rejects at the idempotency-decision level — **uniqueness enforcement and the idempotency decision are different acts** (see boundary below).

**Responsibility boundary (restated for this guarantee):**

| Party | Role regarding INV-C3 |
|---|---|
| **T-1.1.2 (this store)** | Provides and enforces the UAC capability at the storage level (P1–P6); rejects non-unique completions with an explicit outcome; treats (`s1`, `s1_algorithm_id`) as opaque values — byte-value comparison for uniqueness only, **no semantic interpretation of S1**. |
| **T-1.1.3** | Owns the idempotency decision and §9 orchestration: computes S1, performs the lookup through the store's `COMPLETED`-restricted query, routes duplicate-at-capture / explicit integrity-failure path / new-record; consumes UAC as the correctness backstop under concurrency. |

---

## 10. Interaction with Integrity Verification

- Prerequisite the store guarantees: **byte-exact content read** via `artifact_ref` — the input of the verify operation (§10: recompute S1 over stored content with `s1_algorithm_id`).
- The store accepts verification outcome writes (`VALID`/`FAILED` + `integrity_verified_at`) as a **restricted writer** (§6 class 3); `UNVERIFIED` exists only as the pre-first-verification state.
- The store **enforces the completion gate**: `ACTIVE → COMPLETED` requires first verification = `VALID` (§7 rule 1); consequently a `COMPLETED` record is never `UNVERIFIED`.
- Verify-on-read **enforcement** (every content-delivering read carries a definitive verdict; `UNVERIFIED` never final; `FAILED` never presented as healthy) = T-1.1.4, wired over store primitives.
- Verification timing/caching between reads = delegated (§16, **OD-7**) — but the "definitive verdict at read time" guarantee is contractual and non-delegable.
- `FAILED_INCOMPLETE` records: `integrity_status = FAILED` is pinned at settlement and unchanged by later re-verification (§10 rule 5, v1.1-C2).

---

## 11. Required Invariants

Store-level invariants (INV-S series) — all contract invariants INV-C1..C10 are additionally inherited as binding:

| ID | Invariant | Verifiable with |
|---|---|---|
| INV-S1 | Every `COMPLETED` record's `artifact_ref` resolves to byte-exact, readable content — across restarts | restart + read tests (AC-1.1.1/1.1.6) |
| INV-S2 | (R-2) No record reaches `COMPLETED` unless its content was already durable at transition time | crash injection W2–W4 |
| INV-S3 | All field mutations conform to §6 mutability classes; all state transitions conform to §7 | audit/inspection + negative tests |
| INV-S4 | (R-1) Record creation precedes content persist — every content byte the store holds is bound to a record; no unbound residue exists by construction | interruption injection |
| INV-S5 | No store path deletes or overwrites `COMPLETED` content or creation-time identity fields | inspection (§10 r4, §6) |
| INV-S6 | After startup recovery completes, zero records remain in `ACTIVE` (store primitives + T-1.1.5 orchestration) | restart + interruption tests (INV-C6) |
| INV-S7 | The store exposes no field, index, or mechanism carrying downstream-domain data (extraction/canonical/product/customer/sale/inventory) | inspection (INV-C7, v1.1-C1) |
| INV-S8 | Every `FAILED_INCOMPLETE` carries `settlement_note` and `integrity_status = FAILED` | interruption tests (INV-C9, v1.1-C2) |
| INV-S9 | (§6.1, v0.2) Persistence-failure settlement is deterministic: a definitive persist error returned to a live store settles synchronously to `FAILED_INCOMPLETE` (+ note + `integrity_status = FAILED`); only an unverdictable interruption (D-2) may leave `ACTIVE` residue; every residue is settled by the next completed startup recovery — no design-chosen `ACTIVE` parking state exists | fault-injection: error-return + crash + settlement-write-failure tests (INV-C6, INV-C9) |
| INV-S10 | (§9.1, v0.2) Completion is uniqueness-atomic (UAC): for every (`s1`, `s1_algorithm_id`), at most one record is ever transitioned to `COMPLETED` through any path (ingest or recovery), regardless of concurrency; rejected completions yield an explicit uniqueness-conflict outcome, never a second `COMPLETED` | concurrent duplicate-submission test (INV-C3, base AC-1.1.4) |

---

## 12. Acceptance Criteria (T-1.1.2 level)

Executable only at implementation; evidence will be registered per the Acceptance Register chain. WP ACs remain PENDING now — no fabrication.

| ID | Criterion | Maps to |
|---|---|---|
| AC-T112-1 | A new artifact ingest creates a record with unique `capture_id`, durably stored locally, retrievable after restart | AC-1.1.1 |
| AC-T112-2 | After process termination/restart, all pre-restart records are readable and integrity-valid | AC-1.1.6 |
| AC-T112-3 | Interruption injection settles every leftover to exactly one terminal state with `settlement_note` + `integrity_status = FAILED`; no partial-valid record is ever presented | AC-1.1.7 (support) |
| AC-T112-4 | Recovery is idempotent: repeated scan/settle runs produce zero state change | §11 r4 |
| AC-T112-5 | Post-`COMPLETED` mutation attempts are rejected; induced corruption surfaces as explicit `FAILED` on the verification path | INV-C4, §10 |
| AC-T112-6 | Record↔artifact atomicity: no crash window yields an observable `COMPLETED`-without-readable-content state | INV-S1, INV-S2 |
| AC-T112-7 | (`s1`, `s1_algorithm_id`) lookup on `COMPLETED` returns deterministic results; `FAILED`/`FAILED_INCOMPLETE` records are excluded from the dedup-success support path | §9, AC-1.1.3/1.1.4 (support) |
| AC-T112-8 | Record structure inspection shows exactly the 14 contract fields; Provable-Data Rule holds for every field | INV-C7, INV-C8, INV-S7, AC-1.1.8 |
| AC-T112-9 | Fault injection (v0.2): definitive persist errors settle synchronously (`FAILED_INCOMPLETE` + `settlement_note` + `integrity_status = FAILED`); crash injection at any ingest step settles at startup; after completed recovery, zero `ACTIVE` records remain | §6.1, INV-S9, INV-C6, INV-C9 (AC-1.1.7 support) |
| AC-T112-10 | Concurrency test (v0.2): N concurrent ingest attempts with identical content and `s1_algorithm_id` produce at most one `COMPLETED` record; every loser receives an explicit uniqueness-conflict outcome and never becomes `COMPLETED`; (`s1`, `s1_algorithm_id`) lookup remains deterministic | §9.1, INV-S10, INV-C3 (AC-1.1.4 support) |

---

## 13. Dependencies

| On | Nature | Detail |
|---|---|---|
| T-1.1.1 | build-time, satisfied | Contract v1.1 FINAL FREEZE APPROVED — sole normative source; this design modifies nothing in it |
| T-1.1.3 | runtime composition (not build-order) | verification verdicts for the completion gate (§7 r1) and recovery settlement (§11); S1 values for attach; lookup consumer. The store is S1-algorithm-agnostic (`s1` is opaque) — T-1.1.2's deliverable does **not** wait on the algorithm choice. Consumes the store's UAC enforcement capability (§9.1) as the INV-C3 correctness backstop — the idempotency decision itself remains T-1.1.3's |
| T-1.1.5 | runtime composition | owns scan+settlement orchestration; consumes store primitives (enumerate `ACTIVE`, read content, safe/idempotent transitions) |
| WP-1.3 | future | retention mechanics (DEF4) + crash-matrix hardening; design must not preclude either (no deletion defined now; debris cleanup deferred) |
| Task Register | consistent | T-1.1.2 dependency line = "T-1.1.1 (DONE)" — confirmed |

---

## 14. Open Decisions / Delegations

Every item below is an **implementation-level decision, not an architecture decision** (D-09, §16). Each must be declared in the T-1.1.2 implementation task report under "Delegated Implementation Detail Decisions" and must satisfy the stated constraints.

| ID | Item | Mandatory constraints |
|---|---|---|
| OD-1 | Storage mechanism + structure (embedded DB / filesystem / other) | durable, local, no network-service dependency; compatible with §7/§11; satisfies R-1, R-2; no schema/migration executed before implementation dispatch approval |
| OD-2 | `artifact_ref` scheme + content layout | opaque to all consumers; stable after `COMPLETED`; byte-exact retrieval |
| OD-3 | `capture_id` generation scheme | uniqueness within Capture-layer scope |
| OD-4 | Durability mechanics (fsync strategy, journaling, etc.) | must realize write-ahead ordering (R-2) across the agreed restart model |
| OD-5 | Concrete mechanism realizing UAC (which transactional/conditional-write/lock/uniqueness primitive — naming deferred to implementation) | must realize **all** P1–P6 of §9.1 (atomic decision point; uniqueness under concurrency; explicit loser outcome; fail-closed; uniform enforcement across ingest and recovery paths; key opacity); guarantee itself non-negotiable; no correctness reliance on single-writer access (v0.2) |
| OD-6 | Duplicate-attempt logging | optional; must not violate INV-C3 |
| OD-7 | Verification timing/caching | must preserve definitive-verdict-at-read (§10) |
| OD-8 | Clock source for F-05/F-08/F-09 | logical consistency within the layer (§16) |
| OD-9 | `ACTIVE`-enumeration implementation (index vs. scan) | completeness of enumeration is mandatory (§11 r1) |

**Design rules proposed for TM confirmation (not delegations):**

| ID | Rule | Rationale |
|---|---|---|
| R-1 | Record-first ordering (record created in `ACTIVE` before content persist) | closes the silent-loss gap of §14 r1 inside the store; makes §11 complete |
| R-2 | Write-ahead completion (content durable before `COMPLETED`) | excludes "COMPLETED but unreadable" by construction |

Neither R-1 nor R-2 contradicts any frozen rule; both tighten the store toward existing contract guarantees.

---

## 15. Risks and Unresolved Ambiguities

| ID | Item | Type | Disposition |
|---|---|---|---|
| A-1 | Interruption test model for AC-1.1.6/1.1.7: process termination (kill) vs. machine power-loss | Ambiguity | Recommendation: WP-1.1 minimum = process termination + graceful restart; power-loss durability hardening → WP-1.3. Does not require reopening any Frozen Decision; TM to confirm at review |
| A-2 | Concurrency: simultaneous ingests of identical content could both miss lookup and both reach `COMPLETED`, violating INV-C3; concurrent writers could race §7 transitions | Risk — **architecture-level resolution delivered in v0.2 (TM Review Issue 2)** | Correctness no longer rests on any single-writer assumption (no Frozen Decision establishes one). The store mandates the UAC property (§9.1, INV-S10): INV-C3 holds unconditionally under any concurrency, including concurrent recovery settlement. Residual exposure is confined to performance/throughput under contention = delegated implementation concern (OD-5); multi-writer throughput optimization may be added later without reopening architecture. TM to confirm |
| A-3 | OI-1 / RSK-2: Baseline documents still not committed to `kandoo/baseline/`; contract built from Decision Register as interim SSOT | Tracked (pre-existing) | Non-blocking for this design; STOP Protocol applies if a contradiction surfaces after commit |
| A-4 | RSK-3: S1 algorithm choice quality affects false hit/miss | Risk (owned by T-1.1.3) | Store is agnostic (opaque `s1`); no action in T-1.1.2 |
| A-5 | Partial-write debris (crash mid-content-write) | Note | Never presented as evidence; cleanup = retention domain (DEF4 / WP-1.3) — no cleanup in this phase |
| A-6 | Recovery settlement requires a verification verdict; without the S1 service the only contract-legal ending is `FAILED_INCOMPLETE` | Note | By design (conservative); resolved by composition with T-1.1.3/T-1.1.5 |

None of the above blocks this proposal; none requires reopening a Frozen Decision.

---

## Appendix A — Contract-Strength Audit (TM Additional Check, performed in v0.2)

Scope: INV-C3, INV-C6, INV-C9, §7 lifecycle, §9 idempotency, §11 recovery, §14 failure semantics of Contract v1.1. Method: line-by-line reconciliation of every statement in this document against the frozen contract text. Result: **no statement weakens any MUST/SHALL; the two conditional/imprecise formulations flagged by the TM were found and strengthened, and one additional gap was found and closed (recovery uniqueness precondition).**

| Contract anchor | v0.1 finding | v0.2 action | Verdict |
|---|---|---|---|
| INV-C3 | §9 said the store "must **support** the INV-C3 guarantee"; A-2 conditioned safety on an informal single-writer assumption (not established by any Frozen Decision) | UAC guarantee (§9.1, P1–P6); INV-S10; §5 recovery uniqueness precondition; AC-T112-10; A-2 rewritten — single-writer reliance removed; OD-5 constrained to P1–P6 | Strengthened |
| INV-C6 | §4 phrased zero-`ACTIVE` as an "INV-C6 **target**" | §4 guarantee 1 + §6.1 point 4: recovery processing complete *iff* zero `ACTIVE`; storage-unavailable path fails explicitly instead of claiming recovery | Strengthened |
| INV-C9 | Compliant (§3, §4, I-4, INV-S8) | §6.1 extends the same pinning (`settlement_note` + `integrity_status = FAILED`) to the new synchronous D-1 settlement path; uniqueness-conflict losers also settle with note + FAILED | Compliant, extended |
| §7 lifecycle | Compliant; no new state | §6.1 uses only the three §7 states; synchronous settlement anchored to §7 r2 («خطای ingest رخ داده»); **no new lifecycle state introduced** | Compliant |
| §9 idempotency | Compliant on decision ownership (T-1.1.3) | §9.1 restates the boundary: decision stays with T-1.1.3; store provides enforcement capability only; two transient `ACTIVE` duplicates clarified contract-legal (INV-C3 constrains `COMPLETED` only); store performs byte-value uniqueness comparison only — no semantic interpretation of S1 | Strengthened (boundary explicit) |
| §11 recovery | §5 step (b) omitted the uniqueness precondition — recovery itself could have minted a second `COMPLETED` for a key | Step (b) gains the atomic uniqueness precondition (UAC); `settlement_note` vocabulary gains the uniqueness-conflict reason — additive tightening, not a weakening of §11 | Strengthened |
| §14 failure semantics | F1 left the §14 r1 two-ending choice ambiguous ("stays ACTIVE or settles FAILED_INCOMPLETE") | F1/F8 rewritten to the deterministic D-1/D-2 rule (§6.1); F4 annotated with UAC; all nine §14 rows re-checked for conformance | Deterministic |

No other weakening statement exists. All remaining MUST/SHALL-bearing statements (G-1..G-5, I-1..I-5, INV-S1..S10, AC-T112-1..10, R-1/R-2, OD-1..OD-9 constraints) were re-audited in the same pass and found conformant with Contract v1.1.

---

## Closing Verification (document-level, no execution)

| Check | Result |
|---|---|
| Derived exclusively from Contract v1.1 + Decision Register + WP/Task registers | PASS |
| No contract rule redefined, weakened, or bypassed | PASS |
| No storage technology / schema / API / algorithm selected | PASS |
| R-1/R-2 and all INV-S* are additive tightenings within contract bounds | PASS |
| T-1.1.2 / T-1.1.3 / T-1.1.4 / T-1.1.5 responsibilities explicitly separated | PASS |
| All 15 mission-required analysis sections present | PASS |
| TM Review Issue 1 resolved (v0.2): deterministic persistence-failure settlement (§6.1); no new lifecycle state; every `FAILED_INCOMPLETE` with `settlement_note` + `integrity_status = FAILED`; no indefinite `ACTIVE` after completed recovery | PASS |
| TM Review Issue 2 resolved (v0.2): UAC concurrency-safe uniqueness guarantee (§9.1) specified abstractly; no storage technology / index / ORM / transaction / locking selected; T-1.1.2 = enforcement capability, T-1.1.3 = idempotency decision; store does not interpret S1 semantically | PASS |
| TM Additional Check: contract-strength audit vs INV-C3/C6/C9, §7, §9, §11, §14 — no MUST/SHALL weakened (Appendix A) | PASS |

```text
Change Log: v0.1 — 2026-10-01 — initial design proposal by T-1.1.2 design step (no code, no schema, no migration)
            v0.2 — 2026-10-01 — TM review corrections (T-1.1.2-CORR): R1 deterministic persistence-failure settlement (§6.1 new; F1/F4/F8 rewritten; §3 bullet; §4 guarantees 1/6; INV-S9; AC-T112-9) | R2 INV-C3 concurrency-safe Uniqueness-Atomic Completion guarantee (§9.1 new; §5 recovery uniqueness precondition; OD-5 rewritten; INV-S10; AC-T112-10; §1/§2/§13 boundary wording; A-2 rewritten — single-writer reliance removed) | Appendix A contract-strength audit (TM additional check).
            No new lifecycle state introduced | No storage technology / index type / ORM / transaction implementation / locking technology selected | No product code / schema / migration / API created | No Frozen Decision reopened.
Status: PROPOSED (v0.2) — READY FOR TECHNICAL MANAGER FINAL REVIEW; becomes binding design for T-1.1.2 implementation upon approval.
```
