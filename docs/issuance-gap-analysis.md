# E-04 — Invoice issuance gap analysis (read-only)

**Audit baseline:** `f84f2eb827a408e1560e90dc392ba983b251cfdf`

**Audit date:** 2026-10-21

**Scope:** Existing issuance and directly supporting code compared with the Board v4 decisions in `docs/PROJECT_STATE.md`.
**Change boundary:** This audit changes no source code, adapter, frozen contract, or runtime behavior. This report is the only intended repository deliverable.

**Conservative assessment rule:** E-01 / Canonical Invoice v0 is not present in this checkout. Therefore v0 compatibility is marked **unverified**, not assumed. No schema mapping, legal wording, lock timeout, or other unapproved product decision is inferred. The lifecycle terminal outcomes are read according to the existing WP-10.1 contract: `REVOKED` and `SUPERSEDED` are alternative terminal outcomes from `ISSUED`, not consecutive states.

## 1. Inventory

| Area | Files and evidence reviewed | Audit role / scope boundary |
|---|---|---|
| Board v4 baseline | `docs/PROJECT_STATE.md:236-295` | Board v4 D1-D14 as recorded (D14 copy still awaits owner approval), local-first principle, and open owner items. Primary comparison baseline. |
| Issuance composition | `src/issuance/{__init__.py,model.py,service.py,workspace.py,README.md}` | Application-facing composition of the capture-to-canonical pipeline and the Digital Invoice lifecycle. |
| Canonical Invoice assembly | `src/canonical_assembly/{model.py,assembly.py,service.py,store.py,__init__.py}` | Existing P6.2 record, field/line provenance pointers, persistence, verification, and trace. This is WP-6.2 v1.0-MVP, not E-01/v0. |
| Digital Invoice lifecycle | `src/digital_invoice/{model.py,service.py,store.py,__init__.py}` | Six-state lifecycle, explicit acts, lifecycle event log, SQLite persistence, verified reads, and trace. |
| Upstream review gate | `src/validation_domain/{model.py,machine.py,service.py,store.py,__init__.py}` | `VALID`/`INVALID`/`DEFERRED`/`UNRESOLVED` and `CLEAR`/`REVIEW`/`REJECT` routing. These are not Digital Invoice lifecycle states. |
| Capture-to-canonical pipeline | `src/pipeline/{model.py,service.py,workspace.py,__init__.py,README.md}` | Sequential reference Python pipeline and locally owned SQLite workspace. It does not provide a hub, product UI, or multi-store transaction. |
| Origin / canonicalization gate | `src/canonicalization/model.py`, `src/canonicalization/service.py` | Source of the permitted capture origins; distinguishes the current external capture path from a native Kandoo sale path. |
| Image adapter boundary | `src/image_extraction_adapter/adapter.py`, its README, and `deliveries/image-extraction-ocr/cell-preprocessing-issuance-guard.log` | Optional/experimental image-to-transcript adapter. The log records a REVIEW result with zero issuance submit calls; it is one fail-closed run, not a general accuracy or security certification. `adapter.py` was not changed. |
| Focused tests | `src/issuance/tests/`, `src/digital_invoice/tests/`, `src/canonical_assembly/tests/`, `src/validation_domain/tests/`, `src/pipeline/tests/`, and `src/image_extraction_adapter/tests/` | Reviewed relevant lifecycle, replay, boundary, provenance, tamper, local concurrency, and extraction-review tests. See Section 2. |
| Smoke runners | `src/run_smoke_issuance.py`, `src/run_smoke_digital_invoice.py`, `src/run_smoke_canonical_assembly.py` | Synthetic integration harnesses; not production service surfaces. The composed issuance runner contains eight explicit checks. |
| Contracts and implementation reports | `specs/WP-10.1-digital-invoice-lifecycle-contract.md`, `specs/WP-6.2-canonical-assembly-contract.md`, `specs/ISSUE-4-issuance-composition-report.md`, `specs/ISSUE-4-pipeline-implementation-report.md` | Normative scope and historical delivery/test claims. WP-10.1 explicitly excludes display and delivery work; WP-6.2 is a v1.0-MVP implementation contract. |
| Historical delivery packages | `deliveries/issue-4-issuance/`, `deliveries/issue-4-replacement/`, `deliveries/issue-4-smoke-suite/`, `deliveries/issue-5/` | READMEs, manifests, evidence, and archive member lists were reviewed as historical context. ZIPs were listed but not extracted or run. Their test claims belong to their recorded source commits, not this audit baseline. |
| E-01/v0 artifact search | `docs/`, `specs/`, and `src/` | No Canonical Invoice v0 / E-01 schema artifact was located in these paths. The available canonical contract is `SPEC-WP62-CANASM`, version 1.0-MVP. |

**Verification evidence:** Ran the required command against the audited source baseline:

```text
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m unittest discover -s src -p 'test_*.py' -v
Ran 46 tests in 1.412s
OK
```

All 46 discovered `unittest` cases passed. The run emitted Pillow `getdata` deprecation warnings only. The venv was recreated because `/tmp/kandoo-t2-venv` was absent at audit time and installed with Pillow 13.0.0. Tesseract is not installed; no real-Tesseract smoke run was attempted. This result is the specifically requested unittest run, not a claim that pytest-style suites or real OCR were run at E-04.

## 2. Per-file analysis

| File / group | Finding relevant to Board v4 |
|---|---|
| `src/issuance/__init__.py:1-34` | Describes additive composition and explicitly excludes presentation/delivery, customer/product semantics, inventory, adapter mapping, and automatic behavior. This is a deliberate narrow boundary, not evidence that those Board v4 capabilities exist. |
| `src/issuance/model.py:1-57` | Contains result/projection dataclasses only. It introduces no domain state, operation identifier, device identifier, phone lock, or display number. |
| `src/issuance/service.py:27-177` | `submit()` delegates to the pipeline and does not open or advance a Digital Invoice. Open, lifecycle acts, reads, and listing helpers are explicit delegations. No Board v4 hub or per-phone coordination is added here. |
| `src/issuance/workspace.py:1-77` | Owns the eleven pipeline SQLite stores plus `digital-invoice.db`, wires the lifecycle service to the same P6.2 assembly service, and documents one synchronous caller per workspace instance. There is no process lock, network/hub, cloud replication, or customer presentation layer. |
| `src/issuance/README.md:84-114` | Confirms the trusted local application boundary and lists no transport authentication, encryption, process lock, tenancy, or customer delivery surface. It says only the synthetic reference-format path is verified. |
| `src/issuance/tests/test_issuance_flow.py` | Covers the composed happy path, no automatic open, replay/restart, REVIEW stop, refusal, terminal actions, tamper withholding, and whole-chain trace. These tests do not exercise Board v4 multi-device behavior. |
| `src/issuance/tests/test_issuance_boundary.py` | Pins the declared module/import surface, single assembly binding, explicit declarations, blocked purge, and no guessed unknown outcomes. It protects the current narrow composition rather than implementing new Board behavior. |
| `src/digital_invoice/model.py:8-18,38-89,128-163` | Defines `DRAFT`, `EXTRACTED`, `VALIDATED`, `ISSUED`, `REVOKED`, and `SUPERSEDED`; the legal matrix has five transitions. The last two are mutually exclusive terminal alternatives from `ISSUED`. `digital_invoice_id` and `event_id` are bookkeeping UUIDs; the record has no `operation_id`, `device_id`, phone, or display-number field. |
| `src/digital_invoice/__init__.py` | Re-exports the WP-10.1 model, store, service, states, and outcomes. It adds no hub, phone-lock, numbering, or cross-device behavior. |
| `src/digital_invoice/service.py:126-229,235-410,467-650` | Opens only from a verified P6.2 read plus whole-chain trace; all state changes are explicit and re-verify linked content. It supports replay, terminal acts, verified reads, and fail-closed trace. It implements invoice lifecycle behavior, not inventory events or a distributed operation protocol. |
| `src/digital_invoice/store.py:51-114,186-333` | Uses SQLite, `synchronous=FULL`, `BEGIN IMMEDIATE`, unique invoice/event-sequence backstops, transition CHECKs, atomic writes, and compare-and-swap checks for event sequence and prior state. Store APIs are append-only. This is local database concurrency control, not hub replication or a privileged-storage immutability boundary. |
| `src/digital_invoice/tests/test_di_durability.py` | Includes forced commit failure, restart/replay, direct-SQL uniqueness, and eight-thread races for open, progression, and revoke-vs-supersede. These establish tested local SQLite behavior only; they do not establish D10 inventory semantics or D13 devices/LAN/cloud behavior. |
| `src/digital_invoice/tests/test_di_lifecycle.py` and `test_di_open.py` | Exercise legal/illegal transitions, replay, terminal behavior, P6.2 tamper refusal, and opening constraints. The test suite confirms lifecycle immutability through the service boundary, not a customer-facing legal statement. |
| `src/digital_invoice/tests/test_di_service.py` | Exercises verify-on-read, chain/anchor tampering, direct SQL CHECK refusals, and P6.2 consumption. The test comments also identify the direct-database boundary: deleting the last event can leave a valid shorter prefix. Do not describe the SQLite ledger as WORM or tamper-proof. |
| `src/canonical_assembly/model.py:78-159` | `IssuedCanonicalInvoiceRecord` consumes the P6.1 `invoice_id` verbatim. `CanonicalFieldEntry` records `EXTRACTED`/`DERIVED` provenance and source pointers; line fields carry source pointers or explicit absent markers. These structures provide a useful mapping basis, but not a v0 compatibility proof. |
| `src/canonical_assembly/__init__.py` | Re-exports the P6.2 records, vocabulary, store, service, and outcomes. The export surface is not a language-neutral v0 schema. |
| `src/canonical_assembly/assembly.py` | Deterministically assembles verified field values, header anchors, and declared line fields without guessing. It is a Python implementation engine, not a language-neutral E-01 serialization/API definition. |
| `src/canonical_assembly/service.py:109-170,342-440` | Consumes the verified P6.1 admission and trace, verifies the issued record on reads, and re-joins field/line pointers during trace. This is strong within the existing P6.2 chain. |
| `src/canonical_assembly/store.py:1-13,314-400` | Commits canonical invoice, anchors, fields, and lines atomically; uses uniqueness checks and fingerprints; has no application UPDATE/DELETE path. SQLite remains directly accessible to a privileged local writer, with VOR providing tamper evidence/withholding rather than access control. |
| `src/canonical_assembly/tests/test_ca_invoice.py`, `test_ca_provenance.py`, `test_ca_durability.py`, `test_ca_boundary.py` | Cover immutable service behavior, field/line pointer integrity, VOR, replay, commit failure, and a local duplicate race. They do not compare a Python record against a Canonical Invoice v0/C# implementation. |
| `src/validation_domain/model.py` | Defines the separate `VALID`/`INVALID`/`DEFERRED`/`UNRESOLVED` domain-state vocabulary and `CLEAR`/`REVIEW`/`REJECT` dispositions. These are not Digital Invoice lifecycle states. |
| `src/validation_domain/machine.py` | Applies the deterministic projection rules; uncertainty and unresolved inputs route to REVIEW, while decisive invalidity can route to REJECT. It does not assign a phone lock or product lifecycle state. |
| `src/validation_domain/service.py` | Persists and verifies the projected upstream domain state and REVIEW queue outcomes. It is an upstream validation gate, not an inventory ledger or per-device coordinator. |
| `src/validation_domain/store.py` | Persists domain/review records and append-only review events locally. Its event history is not the D10 inventory event ledger. |
| `src/pipeline/__init__.py` | Re-exports the pipeline service, workspace, and outcome types; it does not add product modes or a network boundary. |
| `src/pipeline/model.py` | Exposes typed pipeline completion/stop outcomes; `PipelineCompleted` is an execution result, not a Board v4 product mode or lifecycle state. |
| `src/pipeline/service.py:36-69` | Runs the capture-to-canonical stages sequentially. It accepts `HOLOO_CAPTURE` and `OTHER_POS_CAPTURE` through `CAPTURE_PIPELINE_ORIGINS`; no native Kandoo-sale issuance composition or explicit A/B selector is present. |
| `src/pipeline/workspace.py:44-116` | Owns the local stage stores and composes the pipeline services. It documents one synchronous caller per workspace and does not provide a hub, replication, or a cross-store atomic transaction. |
| `src/pipeline/README.md:80-93` | Documents the one-caller, trusted-local limits and explicitly excludes a Digital Invoice delivery UI. |
| `src/canonicalization/model.py:38-59` | Lists the wider origin vocabulary but separately defines capture-pipeline origins as only `HOLOO_CAPTURE` and `OTHER_POS_CAPTURE`; `KANDOO_SALE` is therefore not a current native mode. |
| `src/canonicalization/service.py:164-173` | Enforces the restricted capture-pipeline origin set. An origin enum member does not establish an operational second mode. |
| `src/image_extraction_adapter/adapter.py:470-574` | Performs local image extraction and calls `IssuanceService.submit()` only for a validated `ImageExtractionReady`; it passes the deterministic OCR key/value page, not the original image, to Capture. REVIEW/BLOCKED outcomes stop before submission. No adapter change was made. This legacy/experimental path does not define the product's canonical contract. |
| `deliveries/image-extraction-ocr/cell-preprocessing-issuance-guard.log` | Records `ImageExtractionReviewRequired`, 31 cell variants, `IssuanceService.submit_calls=0`, and no Digital Invoice for the captured run. Treat this as a single fail-closed example, not a general extracted-but-wrong rate or an end-to-end product claim. |
| `src/run_smoke_issuance.py` | An eight-step synthetic cold-start harness covering explicit acts, replay/restart, REVIEW refusal, terminal states, tamper withholding, and composition boundaries. It is verification scaffolding, not an application or distributed acceptance test. |
| `src/run_smoke_digital_invoice.py` | A synthetic WP-10.1 lifecycle runner. It exercises the current lifecycle layer, not D10 inventory events or D13 multi-device replication. |
| `src/run_smoke_canonical_assembly.py` | A synthetic WP-6.2 assembly/provenance runner. It does not establish Canonical Invoice v0 or C# conformance. |
| `docs/PROJECT_STATE.md:236-295` | Records Board v4 and keeps D14 wording and several deployment choices open for owner action. In particular, the legal-status wording is not yet owner-approved. |
| `specs/WP-10.1-digital-invoice-lifecycle-contract.md:66-123,183-220,351-378` | Normatively defines the lifecycle and explicitly defers display-format/delivery-channel work. Its terminal transition semantics match the existing service. |
| `specs/WP-6.2-canonical-assembly-contract.md:1-110` | Is explicitly version 1.0-MVP and records that the physical Canonical Invoice v1/Master Architecture baseline is not committed. It is not the absent E-01 Canonical Invoice v0 contract. |
| `specs/ISSUE-4-issuance-composition-report.md` and `deliveries/issue-4-issuance/README.md` | Report historical tests at source commit `93e1c6e8…` (29 focused, 1,683 regression, 22 smoke runners). These claims are tied to that earlier commit and must not be presented as E-04 execution evidence. |

## 3. Board v4 gap table

**Status key:** **MATCH** = implemented within the audited boundary; **PARTIAL** = a narrower related mechanism exists; **GAP** = the requested capability is absent; **UNVERIFIED** = no controlling contract exists to determine compatibility.

| Board v4 requirement | Status | Existing evidence and gap |
|---|---|---|
| E-01 Canonical Invoice v0 compatibility / D2 language-independent contract | **UNVERIFIED** (structural overlap only) | No v0/E-01 artifact was located under `docs/`, `specs/`, or `src/`. The existing P6.2 v1.0-MVP has fields, anchors, lines, provenance pointers, and deterministic fingerprints, but the current Python dataclasses/SQLite schema do not prove conformance to a language-independent v0 contract or a C# implementation. Do not claim compatibility or silently map versions. |
| Per-field provenance | **PARTIAL** | Canonical fields use `EXTRACTED`/`DERIVED` labels and source pointers; line fields carry normalization/field pointers or explicit absence. P6.2 trace re-joins those pointers. Structural compatibility with v0 remains unverified, and no cross-language golden-vector test was found. |
| Lifecycle and ISSUED immutability | **MATCH, with storage caveat** | WP-10.1 implements the six labels and five legal transitions. The invoice content is not rewritten by lifecycle acts; events append and `REVOKED`/`SUPERSEDED` are alternative terminal outcomes from `ISSUED`. Store APIs have no update/delete path and VOR withholds detected tampering. This is not WORM storage: a privileged SQLite writer can alter history, and a deleted last event can leave a valid prefix. |
| D1 — two operating modes | **GAP** | There is no A/B mode selector or two-mode product flow. The current pipeline accepts external `HOLOO_CAPTURE` and `OTHER_POS_CAPTURE`; `KANDOO_SALE` is not accepted by that capture pipeline, and no native Kandoo-sale issuance composition is present. An origin enum is not implementation of both modes. |
| D10 — inventory event ledger, base-version conflicts, immutable issued invoice, `operation_id`, `device_id` | **PARTIAL** | The existing Digital Invoice event ledger records lifecycle acts, and local SQLite compare-and-swap tests pass. There is no inventory/product/price/spec event ledger or base-version conflict flow. `operation_id` and `device_id` are absent; random `event_id`/`digital_invoice_id` values are bookkeeping identifiers, not substitutes. The issued canonical content is immutable through application APIs, subject to the storage caveat above. |
| D11 — per-phone invoice lock | **GAP** | No phone identifier or lock record/API exists. “One synchronous caller per workspace” is an application-use limitation, not a per-phone lock; no competing-phone lock race or lock-release behavior is implemented. |
| D12 — internal unique id plus sequential display number from hub | **PARTIAL** | A canonical `invoice_id` exists and `digital_invoice_id` is a bookkeeping UUID. There is no hub-generated sequential display number. The `INVOICE_NUMBER` header anchor is taken from the source invoice identity; it is not a Kandoo customer-facing sequence. |
| D13 — multi-device from day one | **GAP** | The composition is a local directory of SQLite stores and documents one synchronous caller per workspace. There is no hub/LAN/cloud replication or multi-device protocol. Eight-thread tests exercise local SQLite races, not separate devices, network partitions, or restore/replay across replicas. |
| D14 — legal status UNKNOWN and owner-approved customer-page wording | **GAP in issuance scope; release gate** | No customer page or delivery/presentation surface exists in this composition, and there is no owner-approved disclaimer enforcement. `docs/PROJECT_STATE.md` records the proposed wording as needing owner approval. Do not invent or publish legal wording from this audit. |

## 4. Risk table

| ID / severity | Risk if the current implementation is treated as Board v4-ready | Evidence / trigger | Conservative control |
|---|---|---|---|
| R1 — **High** | Current P6.2 records may be integrated as if they were the future Canonical Invoice v0, creating incompatible field, serialization, or migration assumptions. | E-01/v0 artifact absent; available contract is WP-6.2 v1.0-MVP. | Mark compatibility unknown; define E-01 and cross-language conformance before relying on persisted P6.2 data as a v0 API. |
| R2 — **High** | Multiple devices could create conflicting or duplicate work because local transaction correctness is mistaken for a distributed event/operation protocol. | No `operation_id`/`device_id`, inventory ledger, hub, replication, or base-version conflict handling. Thread tests are local. | Do not enable multi-device writes until D10/D13 protocol and failing distributed/concurrency/restore tests exist. |
| R3 — **High** | Two devices associated with the same phone could start or issue concurrent invoices despite D11. | No phone identity or per-phone lock. | Keep the per-phone workflow out of production until lock acquisition, conflict, release, timeout, disconnect, and race behavior are specified and tested. Do not assume the proposed timeout is approved. |
| R4 — **High** | Users could receive an absent, duplicated, or misleading display number if `invoice_id` or a supplier invoice number is repurposed as the hub sequence. | No display-number field/allocator; current `INVOICE_NUMBER` is a source anchor. | Keep identity and presentation numbering separate; require hub allocation, uniqueness, and recovery tests before displaying a Kandoo number. |
| R5 — **High (release gate)** | Customer-facing output could imply an unapproved legal/tax status. | D14 explicitly says legal status is UNKNOWN and the wording needs owner approval; no customer page exists here. | Do not release a customer page until the owner approves the exact copy and the page is tested to display it. This audit makes no legal conclusion. |
| R6 — **Medium** | “Immutable” or “tamper-proof” could be overstated, despite local VOR and append-only service APIs. | SQLite is a local file, not WORM/access control; the Digital Invoice service tests document that deleting the last event can leave a valid prefix. | Describe the current guarantee as application-level append-only plus tamper-evident verification/withholding. Do not claim privileged-writer resistance without a separate security design and failing tests. |
| R7 — **Medium** | Synthetic OCR or a single REVIEW log could be mistaken for real-world extraction accuracy or a downstream issuance safety proof. | Adapter README limits the layout assumptions; Tesseract is unavailable here; the guard log is one case. | Keep uncertainty in REVIEW; make no threshold tuning or automatic correction. If extracted-but-wrong is observed above zero, freeze downstream and report it before proceeding. |

## 5. Recommendations table

These are future-scope recommendations only; none is implemented by E-04. Estimates are indicative T-shirt sizes, not commitments.

| Target | Recommendation | Rationale / guardrail | Estimate |
|---|---|---|---|
| E-01 Canonical Invoice v0 | **BUILD NEW** language-independent v0 contract and conformance fixtures; specify field/provenance semantics, stable serialization/versioning, and Python/C# golden vectors. Separately map current WP-6.2 v1.0-MVP to it. | It is unsafe to infer compatibility from similarly shaped Python records. Keep frozen contracts unchanged unless explicitly authorized. | XL |
| D1 modes | **BUILD NEW** explicit mode boundary and acceptance cases for both “Kandoo is the store software” and “Kandoo runs beside other software.” | Do not treat the existing `KANDOO_SALE` enum member as a working native-sales path or coerce one mode into the other. | L |
| D10 + D13 hub protocol | **BUILD NEW** a separately specified hub/event protocol with `operation_id`, `device_id`, inventory event semantics, base-version conflict outcomes, offline/replication rules, and restore behavior. Add failing tests for duplicate delivery, concurrent edits, partitions, replay, and restore before making reliability claims. | Local SQLite CAS and thread races are useful foundations but do not establish distributed consistency. | XL |
| D11 phone lock | **BUILD NEW** a hub-owned per-phone lock after phone/device identity and lifecycle semantics are approved; test same-phone contention, expiry, disconnect, cancellation, and release races. | No timeout is selected here; owner decision remains necessary. | L |
| D12 display numbering | **BUILD NEW** hub-issued sequential display-number allocation as a field distinct from canonical `invoice_id` and the supplier’s `INVOICE_NUMBER`. Test uniqueness and restart/restore behavior. | Prevents identity and customer-facing numbering from being conflated. | M |
| D14 customer disclosure | **BUILD NEW** a page-release gate using only owner-approved wording, with tests that block publication when the decision/copy is missing. | The current proposed phrase remains unapproved; do not create legal copy in code or in this audit. | S (engineering gate; owner approval is not estimated) |
| Existing `src/digital_invoice/` and `src/canonical_assembly/` | **KEEP** as the current local lifecycle/provenance implementation and reference until E-01 and migration decisions are approved. Any later bridge belongs in a separately authorized increment; do not retrofit Board features into frozen WP-6.2/WP-10.1 behavior by assumption. | Preserves tested behavior while avoiding a false v0-equivalence claim. | — |
| `src/issuance/` and `src/pipeline/` | **MODIFY later**, only after E-01 and the hub/mode contracts exist, to add an explicit application boundary for the selected architecture. Keep today’s explicit-act/fail-closed behavior; no automatic state progression. | Current composition is intentionally local and synchronous. | L–XL, dependent on design |
| `src/image_extraction_adapter/adapter.py` | **KEEP FROZEN** for E-04; preserve REVIEW/BLOCKED holds and transcript-only submission. No threshold tuning, auto-correction, or image transfer is proposed. | The adapter boundary is read-only in this task; its guard log is limited evidence. | — |

## 6. Top-five priority order

Ordered by architecture dependency and implementation critical path, not by permission to bypass later release gates. D14 remains a hard prerequisite before any customer-facing page goes live, even though it is listed fifth here.

| Priority | Work | Why this order | Estimate |
|---:|---|---|---|
| 1 | E-01 Canonical Invoice v0 contract and D1 two-mode boundary | Defines the language-neutral data contract and the two product paths before either is bound to the current P6.2 schema. | XL |
| 2 | D10 + D13 operation/event and hub multi-device protocol | Establishes operation/device identity, inventory conflict semantics, hub ownership, and replica/restore rules required before concurrent devices can write. | XL |
| 3 | D11 per-phone invoice lock | Depends on the device/phone identity and hub coordination in priority 2; prevents conflicting same-phone work. | L |
| 4 | D12 hub sequential display number | Depends on the hub transaction/restore model; keep it separate from canonical and supplier identities. | M |
| 5 | D14 owner-approved customer disclosure gate | No page exists in this code; secure exact owner approval and enforce it before the first customer-facing release. | S for the engineering gate; approval effort unknown |

## 7. Conclusion

The current repository contains a substantial, tested **local Python composition** for capture-to-P6.2 canonical assembly and an explicit, append-only Digital Invoice lifecycle. Its lifecycle matrix, verified reads, field/line provenance pointers, local idempotent replay, and SQLite concurrency backstops are real capabilities. They do not make it a Board v4 store product or establish Canonical Invoice v0 compatibility.

The principal blockers are the absent E-01/v0 contract, the missing two-mode product boundary, D10/D13 hub and multi-device semantics, the D11 phone lock, and D12 hub display numbering. D14 wording remains owner-controlled and must gate any future customer page. Current app-level immutability is tamper-evident but is not a privileged-storage security guarantee. The image adapter’s recorded REVIEW hold is bounded evidence only; no accuracy claim or automatic repair is made.

No implementation code or `adapter.py` was modified, no frozen contract was edited, and no decision about the missing v0 schema or legal wording was inferred. The prescribed unittest command passed 46/46 cases; no real-Tesseract run or distributed-device test is claimed. Until the prerequisite contracts and failing tests exist, the safe conclusion is **do not claim Board v4 readiness or Canonical Invoice v0 compatibility**.
