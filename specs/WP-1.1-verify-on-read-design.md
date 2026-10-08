# WP-1.1 — Verify-on-Read / Integrity Verification — Architecture Design (T-1.1.4)

```text
Design ID:     DES-WP11-T114-VOR | Version: 1.0 | Date: 2026-10-01 | Status: FINAL APPROVED / FROZEN (TM approval, 2026-10-01 — content unchanged from reviewed PROPOSED v1.0)
Task:          T-1.1.4 — Integrity Verification on Read (design step; Architecture Review / Pre-Freeze)
Authority:     SPEC-WP11-CRC — Capture Record Contract v1.1 (FINAL FREEZE APPROVED)
               DES-WP11-T112-STORE — Durable Local Capture Store Design v0.2 (FINAL APPROVED)
               DES-WP11-T113-S1 — S1 Fingerprint & Capture-Level Idempotency Design v1.0 (FINAL APPROVED per dispatch)
               Locked Decisions D-02, D-03, D-09 (kandoo/registers/decision-register.md)
               G1 Architecture Approval: PASS | G2 Work Package Approval for WP-1.1: APPROVED
Binding for:   T-1.1.4 implementation dispatch (after TM approval); composition boundaries stated for
               T-1.1.2 (consumed), T-1.1.3 (consumed), T-1.1.5 (parallel consumer of the same capability).
Change Control: فقط از مسیر STOP Protocol → Issue Report → TM Review → PO Decision (D-09)
Constraints:   No product code | No schema/migration | No API design | No storage-technology selection |
               No S1 redesign — the T-1.1.3 contract is the basis | MVP discipline — no complexity without a concrete requirement.
Missing Input: kandoo/baseline/ still empty (OI-1 / MNT-1 / RSK-2) — Decision Register remains interim SSOT;
               zero guessing. Non-blocking (pre-existing, tracked).
Note:          The T-1.1.3 file header still reads "PROPOSED v1.0"; its FINAL APPROVED status is recorded by the
               dispatching authority in this mission. That file was deliberately not modified (outside task scope).
```

---

## 0. Normative Basis (what this design consumes, verbatim)

| Source | Used for |
|---|---|
| Contract v1.1 §4 r3 | post-`COMPLETED` content immutability; any byte change = integrity breach (detected via §10) |
| Contract v1.1 §5 (F-02, F-03) | stored `s1` + the record's own `s1_algorithm_id`, immutable after attach, never null on `COMPLETED` |
| Contract v1.1 §5 (F-07, F-08) | `integrity_status` = result of the **last verification execution**; `integrity_verified_at` rewritten at every verification |
| Contract v1.1 §6 (class 3) | F-07/F-08 mutable **only by verification** — no other writer may touch them |
| Contract v1.1 §7 r1 | completion gate: first verification `VALID` precedes `COMPLETED` ⇒ a `COMPLETED` record is never `UNVERIFIED` |
| Contract v1.1 §7 r4/r5 | `COMPLETED` terminal; integrity axis evolves independently; no re-open, no deletion |
| Contract v1.1 §8 (prop 4) | S1 comparison valid only within one `s1_algorithm_id` |
| Contract v1.1 §10 | verify operation definition; verdict set {`VALID`, `FAILED`, `UNVERIFIED`(transient only)}; verify-on-read rules 1–5; timing/caching delegated to §16 |
| Contract v1.1 §11 | recovery; no external re-fetch, ever |
| Contract v1.1 §13 | INV-C4, INV-C5, INV-C9 (and the rest) inherited as binding |
| Contract v1.1 §14 r3/r5 | mismatch/unreadable → `FAILED` with reason, no auto-repair; `FAILED`-hit ≠ dedup success |
| Contract v1.1 §15 / WP & Acceptance Registers | AC-1.1.5 — verify-on-read, owner T-1.1.4, evidence = corruption-injection test report |
| Contract v1.1 §16 | delegations: verification timing/caching; logging; clock source |
| Store v0.2 §1 items 6–7, §2, §3, §5, §6 (F5), §6.1, §8 (I-1, I-3), §10, §14 (OD-7, OD-8), INV-S3, G-1, A-6 | store capabilities consumed: byte-exact read, record read, restricted verification-outcome write, mutability/state enforcement, completion gate, D-1/D-2 settlement context |
| S1 Design v1.0 §1 item 2, §2, §6 note 1, §8 (F2), §9 (F1), §12, §13 | verification compute capability (recompute + compare); NO-VERDICT conditions (unknown id, capability failure); `VALID ⇄ FAILED` evolution via verification; T-1.1.4 named as future wiring consumer |
| Task Register T-1.1.4 | objective, scope, inputs (Store + S1 service), out of scope (no auto-repair, no retention, no S1-service change) |
| D-02 / D-03 / D-09 | identity model (no downstream identity in outputs); idempotency definition untouched; delegation governance |

No contract rule and no sibling-design rule is restated differently here. Where this document adds a rule, it is labeled **R-V\*** (design rule, proposed) or **OD-V\*** (open/delegated decision) and does not modify any frozen document. This design introduces **no new lifecycle state, no new integrity state, no new record field, and no new idempotency definition** (D-03).

---

## 1. Responsibility Boundary

**T-1.1.4 owns (full responsibility):**

1. **Read-path verification wiring** — *when* verification executes on the read path (§4): inside every content-delivering evidence read, and nowhere else on this path.
2. **The read outcome contract** — *what* the caller receives and what is never presented (§6).
3. **FAILED marking on the read path** — recording computed verdicts through the store's restricted writer, with the ordering rule (§7).
4. **The exhaustive behavior matrix per integrity state** (§5) and the read-path failure/crash posture (§9).
5. **The MVP verification-timing posture** (R-V1: every-read verification, no caching) — declared under §16's delegation with the contractual guarantee preserved.

**T-1.1.4 does NOT own:**

- **S1 computation and its contract** (T-1.1.3) — consumed, never re-implemented, never altered. The S1 contract (P-S1-1..7), the algorithm choice, and `s1_algorithm_id` semantics are frozen inputs of this design ("S1 را دوباره طراحی نکن").
- **Durable storage mechanics, record/artifact durability, UAC** (T-1.1.2) — consumed via primitives; no bypass path exists in this design.
- **First verification at ingest (V-1)** — wiring belongs to the T-1.1.3 ingest flow over Store Steps 0–4; the completion gate belongs to the store.
- **Recovery settlement verification (V-2)** — wiring belongs to T-1.1.5 (Store §5).
- **Startup scan/settlement orchestration** (T-1.1.5) | **retention/purge** (DEF4, WP-1.3) | **auto-repair** (forbidden outright: §10 r4, §14 r3, Task Out of Scope) | OCR/VLM/Reconstruction/Cloud/Holoo/Digital Invoice (out of scope) | external-document or canonical identity (D-02 — never created, inferred, or interpreted).

**Concept separation:**

| Concern | Owner | T-1.1.4 role |
|---|---|---|
| S1 algorithm contract + compute capability | **T-1.1.3** | consumes |
| Verification computation (recompute + compare) | **T-1.1.3** | consumes; owns the *wiring* on the read path only |
| First verification at ingest (V-1) | T-1.1.3 flow / store gate | none |
| Recovery settlement verification (V-2) | **T-1.1.5** | none |
| Read-path verification (V-3) | **T-1.1.4** | full |
| Verdict persistence (F-07/F-08) | T-1.1.2 restricted-writer primitive | triggers it; never writes anything else |
| Content durability / byte-exact read | **T-1.1.2** | consumes |
| Read outcome contract | **T-1.1.4** | full |
| Lifecycle transitions / UAC | **T-1.1.2** | none — the read path performs no lifecycle transition |

**Boundary vs T-1.1.2 (explicit):** the store provides byte-exact content access, record reads, the restricted verification-outcome write, and mutability/state enforcement (INV-S3). T-1.1.4 decides when the read path verifies and what the caller sees; it never writes any field outside F-07/F-08 and never requests a lifecycle transition. The store's I-1 (no rewrite path for `COMPLETED` content) is the backdrop that makes read-time recomputation meaningful: any observed mismatch implies mutation that bypassed the store.

**Boundary vs T-1.1.3 (explicit):** T-1.1.3 owns *how* S1 is computed (algorithm contract, ids, verdict computation); T-1.1.4 owns *when/where* on the read path and *what the caller receives*. T-1.1.4 adds no algorithm, no id, no comparison rule, no S1 semantics. The NO-VERDICT signal (unknown id / capability failure) is consumed exactly as defined by T-1.1.3 §8 F2 / §9 F1 — not redefined here.

**Boundary vs T-1.1.5 (explicit):** recovery is a separate verification consumer with its own wiring (Store §5). T-1.1.4 introduces no startup behavior; the read path is orthogonal to recovery (a `COMPLETED` record needs no startup repair — §9).

---

## 2. Inputs and Outputs

Contract-level roles only (no API/signature design — D-09).

**Inputs:**

| Input | Content | Source | Anchor |
|---|---|---|---|
| Evidence read demand | target `capture_id` (a `COMPLETED` record) | capture-layer consumer | §10; Task Objective |
| Record fields | stored `s1` (F-02), `s1_algorithm_id` (F-03), `capture_state`, `integrity_status` | store record read | §5; Store §1 item 6 |
| Byte-exact content | artifact bytes via `artifact_ref` | store byte-exact read | Store §1 item 6; §10 |
| Verification verdicts | one of O-1..O-4 (§3 below) | T-1.1.3 capability | §10; S1 §2 |

**Outputs:**

- **Read outcomes** (§6): success = content + definitive verdict `VALID` + `capture_id`; integrity failure = verdict `FAILED` + reason + `capture_id`, **never content**; refusal and NO-VERDICT outcomes as specified.
- **Restricted verification-outcome writes** (F-07, F-08) issued through the store within the same read (§7) — the only writes this path ever performs.
- **Surfaced defects**: Issue-Report escalation for NO-VERDICT conditions (version skew, capability failure) — never silent (§14).

**Never an output:** content without a definitive verdict computed in the same read; `UNVERIFIED` as a final verdict; corrupted (`FAILED`) bytes under any label; any external-document identity, canonical identity, or downstream-domain datum (D-02, INV-C7); any lifecycle transition; any field write outside F-07/F-08.

---

## 3. The Verify Operation (shared semantics, consumed on the read path)

Definition (Contract §10, verbatim basis): **verify(record)** = recompute S1 over the content of `artifact_ref` with the algorithm `s1_algorithm_id` and compare with the stored `s1`.

One **verification execution** (contract-level act; executor = T-1.1.3 capability):

- Inputs handed to the executor: the stored `s1`, the record's own `s1_algorithm_id`, and the byte-exact content read from the store via `artifact_ref`.
- The executor computes and compares only; it never writes and never delivers. Recording and delivery are the wiring layer's acts (§7).

**Exhaustive outcomes (no fifth case exists):**

| # | Outcome | Condition | Contract anchor |
|---|---|---|---|
| O-1 | `VALID` | content readable ∧ recomputed S1 = stored `s1` (comparison only within the equal `s1_algorithm_id`, §8 prop 4) | §10 |
| O-2 | `FAILED` (mismatch) | content readable ∧ recomputed ≠ stored | §10; §14 r3; INV-C4 |
| O-3 | `FAILED` (unreadable) | content missing or not byte-exactly readable | §10 («محتوای ناخوانا/موجود نبودن محتوا — با دلیل»); §14 r3; Store F5 |
| O-4 | **NO-VERDICT** | verification cannot execute at all: unknown/unsupported `s1_algorithm_id` (version skew) or compute-capability failure | S1 §8 F2; S1 §9 F1; Store A-6 |

Two structural notes:

1. **NO-VERDICT is not FAILED.** `FAILED` is a computed verdict *about content*; NO-VERDICT is the absence of any computable verdict (a process/capability condition). Writing `FAILED` without an executed verification would fabricate an integrity result — forbidden by the Provable-Data Rule and §6 class 3 (F-07 is filled only by verification results). This distinction drives §5, §7, and §9.
2. **No separate size gate.** F-13 (`artifact_size_bytes`) is declared by the Contract as a *test aid* for truncation detection; the read path adds no size-check branch — any truncation changes S1 and is subsumed by O-2. (MVP minimality; F-13 integrity relevance.)

**Aggregation note (multi-file):** the store persists exactly the byte sequence delivered at ingest (single handoff — S1 §6 R-S1-1); the recompute input is therefore the same aggregated sequence under the same id (§4 r5, v1.1-C3). T-1.1.4 owns nothing about aggregation.

---

## 4. When Verification Runs (mission Q1)

**Closed list of verification wiring points in the MVP — exactly three, no others:**

| # | Wiring point | Record state | Wiring owner | Verdict consumer | Anchor |
|---|---|---|---|---|---|
| V-1 | First verification at ingest | `ACTIVE` (pre-completion) | T-1.1.3 ingest flow over Store Steps 0–4 | Store completion gate (§7 r1) | Store §3 Step 3; S1 §6 |
| V-2 | Verification inside recovery settlement | `ACTIVE` leftovers | **T-1.1.5** | Store §5 step (b) settlement | Store §5; Contract §11 |
| V-3 | **Read-path verification** | `COMPLETED` | **T-1.1.4 (this task)** | read outcome + restricted write | §10; AC-1.1.5 |

**Explicitly absent in the MVP** (no concrete requirement — MVP rule): background/scheduled re-verification scans of `COMPLETED` records; cross-record content comparison; any verification trigger other than V-1/V-2/V-3. Adding any of these later is an architecture-level change going through Change Control, not an extension of this design.

**R-V1 (proposed design rule — every-read verification, no caching):** *every content-delivering evidence read executes a verification inside that read, before any content is delivered; verdicts are not cached between reads in the MVP.* Justification:

1. §10 r1/r3 — the definitive verdict must be bound to the bytes delivered at that read.
2. AC-1.1.5's threat model — the corruption verify-on-read must detect is mutation that **bypasses the store** (out-of-store tampering). In-store immutability (Store I-1) cannot observe it; only an at-read recompute can. A cached verdict would be blind to exactly the case AC-1.1.5 tests.
3. Local MVP scale — one recompute per read is ordinary resource usage (the S1 §5 recommendation rationale applies unchanged).

§16 explicitly delegates verification timing/caching (Store OD-7). R-V1 is the **MVP resolution of that delegation for the read path**, declared here under D-09: any future caching variant must preserve the definitive-verdict-at-read guarantee and INV-V1/V2, and would be declared in an implementation task report. Nothing in this design precludes it; nothing in the MVP implements it.

---

## 5. Read-Path Behavior per Integrity State (mission Q3)

**Scope rule (evidence read path):** the read path serves `capture_state = COMPLETED` records only.

- F-06 / §7 — only `COMPLETED` records are eligible for valid-evidence delivery.
- `ACTIVE` = unresolved: its content may become evidence only after settlement (V-1/V-2 decide that); presenting it would risk partial-valid presentation (§14).
- `FAILED_INCOMPLETE` = terminal, never presented valid (§7 r3, INV-C9); its `integrity_status = FAILED` is pinned and unchanged by any later verification (§10 r5). The read path therefore never verifies it at all — it refuses.
- Reads targeting non-`COMPLETED` records → **explicit refusal outcome**: no content, no verdict, no state change (§6).
- Note: V-2 (recovery) *does* execute verification against `ACTIVE` content — that is recovery's own wiring, not the read path (§4). No conflict: verify-on-read governs evidence delivery; §11 governs settlement.

**Behavior matrix (`COMPLETED` records; precondition: INV-C1 fields present — `s1`, `artifact_ref` never null on `COMPLETED`):**

| `integrity_status` before read | Verification at this read (R-V1) | Read behavior |
|---|---|---|
| `UNVERIFIED` | — | **unreachable**: the store's completion gate (§7 r1; Store §10) guarantees a `COMPLETED` record is never `UNVERIFIED`. If ever observed, it is a store-defect condition → explicit read failure + Issue Report — never a verdict, never content. |
| `VALID` | O-1 `VALID` | deliver content + verdict `VALID`; restricted write F-07 = `VALID`, F-08 = now (truthful latest result; F-08 is rewritten at every verification). |
| `VALID` | O-2/O-3 `FAILED` | restricted write F-07 = `FAILED`, F-08 = now — **before** the failure outcome is returned (§7); deliver **no content**; explicit integrity-failure outcome with reason. Record remains `COMPLETED`. |
| `VALID` | O-4 NO-VERDICT | no integrity-field write; deliver **no content**; explicit read-failure outcome (verification unavailable) + Issue-Report surfacing. |
| `FAILED` | O-1 `VALID` | deliver content + verdict `VALID`; restricted write F-07 = `VALID`, F-08 = now. Rationale: F-07 means "result of the last verification" and §6 class 3 makes F-07/F-08 mutable only by verification; bidirectional `VALID ⇄ FAILED` evolution via verification executions is already established (S1 §6 note 1). **This is not auto-repair**: content is untouched (Store I-1); the corruption *situation* is still resolved only via Issue Report (§10 r4); recording a truthfully computed verdict is not a repair act. |
| `FAILED` | O-2/O-3 `FAILED` | stable re-failure: restricted write F-07 = `FAILED`, F-08 = now; no content; explicit integrity-failure outcome with reason. |
| `FAILED` | O-4 NO-VERDICT | no integrity-field write; no content; explicit read-failure outcome + Issue-Report surfacing (F-07 keeps its last truthfully recorded value). |

**Additional rules:**

1. Every delivered content byte is accompanied by the verdict computed in that same read over those same bytes (§10 r1; INV-V1).
2. No silent broken read exists in any row: every non-delivering row is an explicit outcome (§10 r2).
3. **Concurrency note (MVP):** concurrent reads each verify their own content read; identical concurrent restricted writes of the same verdict are benign; no lifecycle transition is involved, so UAC is out of scope here. No read-serialization machinery is introduced.
4. No lock or held state between reads: each read is self-contained (verify → write → deliver/withhold).

---

## 6. Read Outcome Contract (mission Q4)

**Returned — success (verdict `VALID`):**

| Item | Notes |
|---|---|
| content | byte-exact artifact bytes as read from the store (§4 r3) |
| verdict | definitive `VALID`, computed in this read |
| `capture_id` | handle for traceability (F-01) |
| record context (optional, per consumer need) | `s1`, `s1_algorithm_id`, `integrity_verified_at` — available from the record-read capability (Store §1 item 6); never fabricated here |

**Returned — integrity failure (verdict `FAILED`):**

| Item | Notes |
|---|---|
| verdict | definitive `FAILED` |
| reason | coarse reason code: `mismatch` \| `content unreadable/missing` (§10 «با دلیل»; no content interpretation enters the reason) |
| `capture_id` | F-01 |
| verdict timestamp | the F-08 value written in this read |
| content | **absent — never delivered, under any label** (§10 r2) |

**Returned — refusal (non-`COMPLETED` target):** explicit refusal outcome including the record's `capture_state` (capture-layer process state — Provable-Data-legal); no content; no verdict; no state change.

**Returned — NO-VERDICT:** explicit read-failure outcome (verification unavailable); no content; no verdict; no integrity claim; Issue-Report surfacing.

**Never returned / never performed (any case):**

1. `UNVERIFIED` as a final read verdict (§10 r3).
2. Content without a definitive verdict computed in the same read (§10 r1) — no streaming-before-verdict, no partial content.
3. Corrupted (`FAILED`) bytes — not even labeled "for debugging"; diagnosis is an operator/Issue-Report concern, not an evidence-path concern (MVP fixed posture; §10 r2/r4).
4. Any external-document identity, canonical invoice identity, or downstream-domain datum (D-02; INV-C7) — the read outcome speaks only capture-layer facts.
5. Any lifecycle transition, deletion, content rewrite, or re-fetch from external sources (§7 r5; §10 r4; §11 r5).
6. Any write outside F-07/F-08 (§6 class 3; Store INV-S3).
7. Any silent outcome: every demand ends in a defined, explicit outcome (§14).

---

## 7. The FAILED Marking Path (mission Q5)

How a read-path verification failure makes the record reach `integrity_status = FAILED`:

1. The verification execution inside the read yields O-2 (mismatch) or O-3 (unreadable/missing).
2. The wiring immediately issues a **restricted verification-outcome write** through the store: F-07 = `FAILED`, F-08 = verdict time (Store §1 item 7; §6 class 3). The store enforces mutability legality (INV-S3; Store F9 rejects anything else). This is the **only write** the read path ever performs.
3. **Ordering rule:** the verdict write completes **before** the failure outcome is returned to the caller — a `FAILED` verdict is never only-in-memory (§10 r4 «ثبت می‌شود» is mandatory). In the `VALID` case the outcome (verdict + content) is likewise assembled only after the write; delivery never precedes recording (see §9 for crash interleavings).
4. **No lifecycle change:** `capture_state` remains `COMPLETED` (§7 r4 — the integrity axis is orthogonal; §7 r5 — `COMPLETED` is terminal, `FAILED_INCOMPLETE` is unreachable from `COMPLETED`, nothing is deleted or re-opened). The record remains retained evidence of the capture event, now marked integrity-`FAILED`.
5. **Reason handling:** the 14-field record has **no field** for a `COMPLETED`-record failure reason — F-15 (`settlement_note`) is settlement-scoped and meaningless for `COMPLETED` (§5 F-15), and introducing any new field is forbidden (Extensibility Reservation, §5). The Contract's «با دلیل» requirement (§10) is satisfied by carrying the reason in the read outcome (§6) plus optional audit logging — a delegated implementation detail (§16 logging pattern), declared as OD-V1. No schema change, no new field, no contract modification.
6. **Other `FAILED` paths (listed for completeness, not owned here):**
   - Ingest first verification `FAILED` (O-2/O-3 at V-1) → completion gate unmet → `FAILED_INCOMPLETE` settlement with pinned `FAILED` (T-1.1.3 flow §6; Store §6.1; §7 r2).
   - Recovery verification `FAILED` (V-2) → `FAILED_INCOMPLETE` settlement with pinned `FAILED` (T-1.1.5; Store §5 step c).
   - `FAILED_INCOMPLETE`'s pinned `FAILED` is never modified by the read path or by any later verification (§10 r5; §5 of this design refuses these records outright).
7. **No repair, ever:** no auto-repair, no delete, no content rewrite, no re-fetch — the resolution path for real corruption is exclusively Issue Report (§10 r4; §14 r3; Task Out of Scope).

---

## 8. Interaction with T-1.1.2 and T-1.1.3 (mission Q6)

**Consumed from T-1.1.2 (store) — capability, never re-implemented, never bypassed:**

| Capability | Use on the read path | Anchor |
|---|---|---|
| byte-exact content read via `artifact_ref` | the verification input; the delivered content | Store §1 item 6; §10 |
| record read by `capture_id` | fetch `s1`, `s1_algorithm_id`, `capture_state`, `integrity_status` | Store §1 item 6 |
| restricted verification-outcome write | the only write the read path performs (F-07/F-08) | Store §1 item 7; §6 class 3 |
| mutability/state enforcement | backstop: illegal writes rejected | Store INV-S3, F9 |
| durability + I-1 content immutability | the backdrop that makes read-time mismatch meaningful (any mismatch ⇒ out-of-store mutation) | Store G-1, I-1 |

**Consumed from T-1.1.3 (S1 service):**

| Capability | Use on the read path | Anchor |
|---|---|---|
| verification compute (recompute with the record's own id + compare within equal id) | O-1/O-2 computation | S1 §1 item 2; S1 §2; Contract §10 |
| NO-VERDICT signaling (unknown id / capability failure) | O-4 → explicit read failure + Issue Report | S1 §8 F2; S1 §9 F1 |
| algorithm/id contract | consumed as-is; no second algorithm, no id semantics added | S1 §3, §4 |

**Not taken over (no responsibility transfer in either direction):**

- First verification wiring (V-1) stays with the T-1.1.3 ingest flow + store gate.
- Recovery verification wiring (V-2) stays with T-1.1.5.
- Idempotency decision and UAC stay with T-1.1.3 / T-1.1.2 — the read path performs no lifecycle transition, so UAC is untouched.
- Storage mechanics, retention (DEF4), and timing/caching beyond R-V1 (OD-7 remains a store-side delegation; R-V1 is the declared MVP read-path posture).
- S1 semantics: this design redesigns nothing (mission constraint honored).

**Composition statement:** T-1.1.3 owns *how* S1 is computed; T-1.1.2 owns *durable effects*; T-1.1.4 owns *when the read path verifies and what the caller sees*. Every verdict that reaches a caller was computed by the T-1.1.3 capability over store-read bytes; every durable effect of that verdict was recorded by the store's restricted writer.

---

## 9. Failure / Crash Cases and Minimal Recovery (mission Q7)

Read-path failure and crash cases (exhaustive for the read path):

| # | Case | Immediate behavior | Durable effect | Recovery behavior | Anchor |
|---|---|---|---|---|---|
| FC-1 | crash before verification completes | no response; nothing delivered | none (no verdict, no state change) | none needed — the next read re-verifies | §10; a read is not a lifecycle act |
| FC-2 | crash after verdict write, before response | caller received nothing | truthful verdict recorded (`VALID` or `FAILED`) | none needed — next read re-verifies | §6 class 3 |
| FC-3 | verdict-write failure (storage unavailable, either verdict) | read fails explicitly; no content | no verdict recorded (no fabricated result) | next successful read re-verifies; store-level recovery = Store §6.1 (D-1/D-2) — not duplicated here | §10 r4; Store §6.1 |
| FC-4 | content unreadable/missing (O-3) | `FAILED` verdict + reason; no content | F-07 = `FAILED`, F-08 = now | content repair never; operator/Issue-Report path only | §10; §14 r3; Store F5 |
| FC-5 | unknown `s1_algorithm_id` (O-4, version skew) | explicit read failure; no content; no write | F-07/F-08 unchanged (last truthful values) | Issue Report (STOP); fix = capability restoration (S1 R-1: retain compute for previously issued ids); no data change | S1 §8 F2; S1 §14 R-1 |
| FC-6 | compute-capability transient failure (O-4) | explicit read failure; no content; no write | none | caller may re-read; no auto-retry loop inside the read in MVP | S1 §9 F1 (analog at read time) |
| FC-7 | concurrent reads of the same record | each read verifies its own content read | benign identical restricted writes | none needed | §6 class 3; §5 note 3 |

**Minimal recovery posture (mission constraint: حداقل):**

- T-1.1.4 introduces **no new recovery machinery**: no new scanner, no scheduler, no repair, no re-fetch, no queue.
- The **integrity axis** self-corrects only by truthful re-verification at the next read (R-V1); the **lifecycle axis** needs nothing from this task: `COMPLETED` records were gated durable at completion (Store R-2, §7 r1) and `ACTIVE` leftovers are T-1.1.5's domain (zero `ACTIVE` after completed recovery, INV-C6).
- Crash windows FC-1/FC-2 leave at most a truthful verdict — never content-without-verdict, never verdict-without-computation. **No read-path residue requires startup cleanup** (Contract §11 applies to lifecycle residue only).

**Rejected-for-MVP (over-engineering guard):** background integrity scanning of `COMPLETED` records; verdict caching between reads; delivering `FAILED` bytes for debugging; a failure-history field or a `FAILED` "latch" on `COMPLETED` records (would violate F-07/F-08 semantics and/or the Extensibility Reservation); a read-path size gate (subsumed by O-2); auto-retry loops.

---

## 10. Invariants (mission Q8)

Service-level invariants (INV-V series). All contract invariants (especially INV-C1, INV-C4, INV-C5, INV-C7, INV-C8, INV-C9, INV-C10) and sibling invariants (Store INV-S3; S1 INV-F1..F7 where applicable) are inherited as binding by composition:

| ID | Invariant | Verifiable with |
|---|---|---|
| INV-V1 | Every content-delivering read outcome carries exactly one definitive verdict ∈ {`VALID`, `FAILED`} computed in that same read over the delivered bytes; `UNVERIFIED` is never a final read verdict | read-behavior test (§10 r1/r3; INV-C5; AC-T114-2) |
| INV-V2 | No read ever delivers content whose verification verdict at that read is `FAILED`; corrupted content is never presented as evidence under any label | corruption-injection test (§10 r2; INV-C4; AC-T114-1) |
| INV-V3 | A `FAILED` verdict at a read ⇒ F-07 = `FAILED` ∧ F-08 recorded via the store's restricted writer within that read, before the failure outcome is returned | read + record-inspection test (§10 r4; §6 class 3; AC-T114-1) |
| INV-V4 | Every read-path verification uses the record's own `s1_algorithm_id` and the T-1.1.3 capability; comparison occurs only within equal ids; no second algorithm or id semantics exists on this path | inspection + version-skew injection (F-03; §8 prop 4; AC-T114-6) |
| INV-V5 | The read path writes only F-07/F-08; it never performs a lifecycle transition, never deletes, never rewrites content, never touches the `artifact_ref ↔ s1` binding | negative-write test (§6 class 3; §7 r4/r5; Store I-1/I-3) |
| INV-V6 | Records with `capture_state ≠ COMPLETED` never deliver content through the read path and are never verified by it; `FAILED_INCOMPLETE`'s pinned `FAILED` is never modified | refusal test (§7 r3; §10 r5; INV-C9; AC-T114-4) |
| INV-V7 | No read outcome carries external-document identity, canonical invoice identity, or any downstream-domain datum | boundary inspection (D-02; INV-C7; AC-T114-7) |
| INV-V8 | No verdict is recorded without an executed verification: NO-VERDICT ⇒ no F-07/F-08 write and an explicit read failure — never a fabricated or defaulted verdict | fault-injection test (Provable-Data Rule; §6 class 3; AC-T114-6) |

---

## 11. Acceptance Criteria (T-1.1.4 level) (mission Q8)

Executable only at implementation; evidence registered per the Acceptance Register chain. WP AC AC-1.1.5 (owner: T-1.1.4) remains PENDING — no fabrication.

| ID | Criterion | Maps to |
|---|---|---|
| AC-T114-1 | Corruption injection: after a post-`COMPLETED` byte flip in stored content, the next read returns an explicit `FAILED` outcome with reason, delivers no content, and the record shows `integrity_status = FAILED` with a fresh `integrity_verified_at` | AC-1.1.5 (fail side); INV-V2/V3; INV-C4; §14 r3 |
| AC-T114-2 | Healthy read: intact content is delivered with verdict `VALID` computed in that read; `integrity_verified_at` is refreshed | AC-1.1.5 (pass side); INV-V1 |
| AC-T114-3 | Unreadable/missing content injection: read outcome = `FAILED` with reason `content unreadable/missing`; no content delivered; record `integrity_status = FAILED` | §10; §14 r3; INV-V3 |
| AC-T114-4 | Refusal test: read demands against `ACTIVE` and `FAILED_INCOMPLETE` records return explicit refusal; no content, no verdict, no state change anywhere | §5 scope rule; INV-V6; §7 r3 |
| AC-T114-5 | Crash injection across read-path windows (FC-1/FC-2/FC-3): no observable content-without-verdict or verdict-without-computation outcome ever exists; subsequent reads re-verify and behave per §5 | INV-V1/V8; §9 |
| AC-T114-6 | Version-skew injection (unknown `s1_algorithm_id`): explicit read failure; no content; F-07/F-08 unchanged; Issue-Report surfacing — never a fabricated `FAILED`, never a `VALID` assumption | INV-V4/V8; S1 §8 F2 |
| AC-T114-7 | Boundary inspection: no read outcome contains downstream/canonical/external identity; the read path's write set is exactly {F-07, F-08}; delegated choices (OD-V1..V3, R-V1 posture) declared in the implementation task report | INV-V5/V7; D-02; §16 (DoD) |

---

## 12. Dependencies

| On | Nature | Detail |
|---|---|---|
| T-1.1.1 | build-time, satisfied | Contract v1.1 FINAL FREEZE APPROVED — sole normative source for §10 read semantics, F-07/F-08, lifecycle; this design modifies nothing in it |
| T-1.1.2 | runtime composition | consumed capabilities: byte-exact content read, record read, restricted verification-outcome write, mutability/state enforcement (Store v0.2 FINAL APPROVED) |
| T-1.1.3 | runtime composition | consumed capability: verification compute + NO-VERDICT signaling (S1 design FINAL APPROVED per dispatch); no S1 semantics redefined here |
| T-1.1.5 | parallel composition (future) | owns recovery wiring (V-2); disjoint from the read path; no shared state beyond the record itself |
| Task Register | consistent | T-1.1.4 Inputs = Store (T-1.1.2) + S1 service (T-1.1.3) — confirmed; Out of Scope honored: no auto-repair, no retention, no reconstruction, no S1-service change |

---

## 13. Open Decisions / Delegations

Every item below is an **implementation-level decision, not an architecture decision** (D-09, §16); each must be declared in the T-1.1.4 implementation task report under "Delegated Implementation Detail Decisions".

| ID | Item | Mandatory constraints |
|---|---|---|
| OD-V1 | FAILED-reason audit logging (optional) | §16 logging pattern; must not introduce record fields or violate INV-V5/V7; if implemented, at most once layer-wide (shared scope with Store OD-6 / S1 OD-S3) |
| OD-V2 | Clock source for F-08 read-path writes | single layer clock shared with Store OD-8 (§16) — implemented at most once; logical time consistency within the layer |
| OD-V3 | Concrete encoding of the read outcome (verdict + reason codes) | contract-level outcome roles fixed in §6; literal encoding = implementation declaration; no API design |

**Design rule proposed for TM confirmation (not a delegation):**

| ID | Rule | Rationale |
|---|---|---|
| R-V1 | Every content-delivering read verifies inside the read; no verdict caching in the MVP | §10 r1/r3 definitive-verdict-at-read; AC-1.1.5 detection-at-next-read; §16 timing/caching remains a delegation whose future exercise must preserve INV-V1/V2 |

**Blocking open decisions: none.** All eight mission questions are resolved at the architecture level above; the remaining items are implementation details with binding constraints per D-09.

---

## 14. Answers to the 8 Mission Questions (cross-reference)

| # | Question | Answer location |
|---|---|---|
| 1 | When must an artifact be verified | §4 (closed list V-1/V-2/V-3; R-V1 every content-delivering read; no background scans) |
| 2 | How verification compares stored S1 with actual artifact content | §3 (recompute over byte-exact stored content with the record's own id via the T-1.1.3 capability; compare within equal id; exhaustive outcomes O-1..O-4) |
| 3 | Exact behavior in `VALID` / `FAILED` / `UNVERIFIED` | §5 (behavior matrix; `UNVERIFIED` unreachable on the read path; refusal scope rule) |
| 4 | What is returned to the caller and what is never presented | §2 outputs; §6 (outcome contract + never-list) |
| 5 | How the record reaches `integrity_status = FAILED` | §7 (restricted-write path, ordering rule, no lifecycle change, reason handling) |
| 6 | Interaction with T-1.1.2 / T-1.1.3 without transferring responsibility | §8 (consumption tables; composition statement) |
| 7 | Failure/crash cases and minimal recovery behavior | §9 (FC-1..FC-7; no new recovery machinery; rejected-for-MVP list) |
| 8 | Acceptance criteria and invariants | §10 (INV-V1..V8); §11 (AC-T114-1..7) |

---

## Closing Verification (document-level, no execution)

| Check | Result |
|---|---|
| Derived exclusively from Contract v1.1 + Store Design v0.2 + S1 Design v1.0 + Registers; no frozen rule redefined, weakened, or bypassed | PASS |
| S1 not redesigned: no algorithm, id, property, or comparison rule added or altered (T-1.1.3 contract consumed as-is) | PASS |
| MVP discipline: no background scanner, no caching, no new fields, no new recovery machinery, no complexity without a concrete requirement | PASS |
| §10 guarantees preserved: definitive verdict at read; `UNVERIFIED` never final; `FAILED` never presented healthy; no auto-repair; no new integrity state | PASS |
| Responsibility boundaries T-1.1.2 / T-1.1.3 / T-1.1.4 / T-1.1.5 explicit; no responsibility transferred in either direction | PASS |
| No product code / schema / migration / API / storage-technology selection produced | PASS |
| All 8 mission questions answered; deliverable sections complete (when, how, state behavior, outcome contract, FAILED path, interaction, failure/crash, invariants + ACs) | PASS |

```text
Change Log: v1.0 — 2026-10-01 — initial architecture design by T-1.1.4 design step (no code, no schema, no migration, no storage-technology selection, no S1 redesign).
            v1.0 — 2026-10-01 — FINAL APPROVED / FROZEN by TM dispatch: status change only; no redesign, no refinement, no new document, no code/schema/migration/implementation.
Status: FINAL APPROVED / FROZEN (TM approval, 2026-10-01) — binding design for T-1.1.4 implementation.
```

