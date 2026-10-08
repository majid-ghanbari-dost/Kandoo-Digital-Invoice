# SPEC-WP91-CUSTLINK — Deterministic Customer Linking Contract v1.0-MVP

```text
Spec ID:      SPEC-WP91-CUSTLINK | Version: 1.0-MVP | Date: 2026-10-08
Status:       IMPLEMENTATION CONTRACT (T-9.1.1) — produced inline per the
              Mission dispatch 2026-10-08 ("PRODUCT IDENTITY & CUSTOMER
              LINKING" — Phase C: WP-9.1 Deterministic Customer Linking).
Authority:    REG-WPR Phase Index P9 row (WP-9.1 Deterministic Customer
              Linking) + the Mission dispatch 2026-10-08 is the scope of
              record; this spec converts that scope into the binding
              implementation contract, derived ONLY from established frozen
              decisions, existing contracts, and downstream/upstream
              references (no invented product requirement).
Frozen basis: D-06 (in External Capture: AUTO-CREATE CUSTOMER IS FORBIDDEN;
              only deterministic link to an EXISTING Customer is allowed;
              future enrichments are outside the Freeze — WP-9.1 builds
              ONLY the linking; any customer-creation logic from the
              capture/enrichment path is Subject to the STOP Protocol) |
              DEF3 (automatic customer creation DEFERRED to PO — merge/dedup
              models too; deterministic link first, enrich later) | D-09
              (no new architectural decision; delegated details declared
              OD-CL1..CL8) | AD-02 (Customer Linkage is its own domain;
              cross-domain access only through the destination domain's
              contract) | AS-02 (native flow precedes capture consumption —
              customers exist before invoices link to them) | AS-04/AD-04/
              CL-1 (verbatim-vocabulary discipline) | D-01 (provenance
              relayed verbatim) | AS-03 (no state invention) | AD-03 (no
              inventory effect) | D-05 (the project's established
              deterministic-matching semantics: definitive-identifier exact
              matching — applied here as the ONLY deterministic link rule) |
              SPEC-WP62-CANASM OD-A9 (the canonical customer reference is
              recorded ABSENT with the stable reason
              `deferred-wp9.1-d06-no-deterministic-link` — THIS WP is the
              named consumer; the link is an ADDITIVE domain record, the
              frozen canonical invoice is never mutated).
Baseline note (MNT-1): the physical Master Architecture / Canonical Invoice v1
              documents are not committed; the Decision Register + this
              Mission dispatch are the valid self-contained representation
              (pre-registered, not a STOP cause). Where the dispatch demands
              content no upstream contract carries (a customer-identifier
              field role, a customer register), the mechanism is a DECLARED
              input or an explicitly scoped minimal register (OD-CL2/CL3/
              CL6) — NEVER a guess.
Upstream:     P1 → … → P6.1 → P6.2 → **P9.1**. The ONLY value/admission path
              is the WP-6.2 verified read (`CanonicalAssemblyService.
              read_assembled_invoice`) — consumed, never bypassed, never
              triggered; this layer never reads any upstream store directly
              and never executes any pipeline stage.
Downstream:   Customer Linkage domain consumers. Customer ENRICHMENT (Holoo,
              WP-11.x) and any merge/dedup policy (DEF3) are NOT part of
              this WP and are NOT pre-built here.
```

## 1. Purpose and scope

WP-9.1 implements **Deterministic Customer Linking**: ONE immutable,
append-only, auditable link fact per declared customer reference on an
issued Canonical Invoice (P6.2), connecting that invoice to an EXISTING
registered customer identity — or, when no existing customer matches, a
durable UNRESOLVED fact. The linking rule is exactly the project's
established deterministic-matching semantics (D-05/D-03/P6.1 discipline):
a **definitive valid identifier matched byte-exactly against exactly one
registered customer identity** under the declared identifier kind.

- **No auto-create — structurally (D-06/DEF3):** the Customer Identity
  register is populated EXCLUSIVELY by the explicit registration API, which
  carries no capture/invoice/document parameter. The link service has no
  creation path at all: its only outcomes are LINKED and UNRESOLVED. A
  capture containing customer-looking data can therefore never create a
  customer — it can only attempt a deterministic link against customers
  that already exist (OD-CL2).
- **Deterministic + auditable:** every link attempt produces exactly one
  immutable row (INV-CL-1:1 per declared reference, UNIQUE backstop);
  replay returns the existing outcome verbatim and never re-decides
  (OD-CL4); every read re-verifies the whole chain live (§6).
- **Ambiguity remains ambiguity:** zero registered customers for the
  declared identifier → UNRESOLVED(`no-customer-identity`) — durable,
  auditable, never rewritten by later registrations. No guess, no
  best-match, no creation (OD-CL7).

In scope:
1. **Customer identity register** — explicit, idempotent, append-only
   registration of existing customers' identities; UNIQUE(identifier_kind,
   identifier_value) backstop keeps a definitive identifier mapped to
   exactly one customer identity by construction (OD-CL5).
2. **Linking service** — declared-reference resolution against the P6.2
   verified read + the deterministic exact lookup + atomic durable commit
   (§4/§5).
3. **Verified link reads** — own-row VOR + re-verification of the linked
   invoice through the P6.2 verified read + pointer re-join + customer
   identity re-verification + the LIVE byte-identity re-proof (§6).
4. **Register queries** — `links_of(invoice_id)`, `customers()` (§6).
5. **Persistence** per the project store pattern (§7/§8).
6. Behavioral + structural boundary tests (no-creation proof, pointer
   discipline, adversarial matrix, durability, concurrency, AST probes,
   frozen-layer protection).

Out of scope (FORBIDDEN — dispatch): automatic customer creation from
capture or enrichment of ANY kind (D-06/DEF3 — structurally absent, OD-CL2);
customer merge/dedup models (DEF3 — PO territory); customer enrichment
(D-06 — outside the Freeze; WP-11.x); fuzzy/semantic/AI/heuristic/best-effort
matching of ANY kind (the ONLY link rule is the exact definitive-identifier
rule; ambiguous references stay UNRESOLVED); barcode semantics (no grammar,
no checksum — identifier kinds are DECLARED opaque strings, OD-CL3);
canonicalization re-decision; document identity (P7.1); product matching
(WP-8.1); REVIEW queue operations; invoice/canonical-record mutation (P6.2
rows are immutable — this layer only ADDS its own register rows; the OD-A9
absence stands as the assembly-time fact); any change to any frozen layer
P1–P8.1; upstream execution; Holoo parser; Cloud sync; UI; mobile.

## 2. Input path (normative)

The ONLY invoice/value input path is the WP-6.2 public verified read
(`CanonicalAssemblyService.read_assembled_invoice(invoice_id)`) — consumed
VERBATIM inside every `link` call. The linking service never reads any
upstream store directly, never reads raw artifacts, never re-computes an
identity or content fingerprint of any upstream record (beyond its own
record-integrity anchors, §8), never executes any pipeline stage, and never
accepts invoice facts from any source other than the P6.2 outcome objects.

The customer register is the ONLY other input, populated exclusively by the
explicit `register_customer_identity` API — never by any capture/pipeline
path (structural no-auto-create, OD-CL2).

## 3. Request contract (normative)

`link(invoice_id, declared_field_name, identifier_kind)` — ONE declared
customer reference on ONE issued Canonical Invoice:

- `invoice_id` — the P6.2 issued invoice identifier (the D-02 Canonical
  Identity, consumed verbatim; existence and integrity are established by
  the P6.2 verified read, fail-closed).
- `declared_field_name` — the engine-vocabulary field name of the canonical
  field carrying the customer identifier (DECLARED, never discovered — the
  OD-A4 discipline). Resolution requires EXACTLY ONE canonical field entry
  with that name in the invoice's verified field inventory: 0 → request
  refused (`declared-field-not-found`); ≥2 → request refused
  (`declared-field-ambiguous`) — picking one would be auto-resolution
  (forbidden). Both D-01 provenances (EXTRACTED | DERIVED) are verified
  P6.2 content and equally resolvable (OD-CL6).
- `identifier_kind` — the DECLARED opaque identifier vocabulary label
  (verbatim, compared byte-exactly; no enumeration, no semantics — OD-CL3).

There is no second request vocabulary, no options, no override switches.

`register_customer_identity(identifier_kind, identifier_value)` — ONE
explicit registration of an EXISTING customer's identity (the native
Customer-domain surface). Both arguments must be non-empty; the content is
stored verbatim (no trimming, no case folding, no re-normalization — P4.1
is the sole normalizer). Re-registering the same (kind, value) returns the
existing customer identity VERBATIM (idempotent replay — no second row).

## 4. Linking ladder (normative — fail-closed, ordered)

The link service performs exactly ONE P6.2 verified read per call and maps
the outcome deterministically:

| # | Step | Action |
|---|---|---|
| L1 | P6.2 verified read | `read_assembled_invoice(invoice_id)` — any non-success → fail-closed passthrough with ZERO durable residue (details verbatim). |
| L2 | Declaration validation | empty `declared_field_name` / `identifier_kind` → `CustomerLinkRequestRefused` (`declaration-malformed`), zero residue. |
| L3 | Declared-reference resolution | exactly one canonical field entry with `declared_field_name` → the reference (value + pointer + provenance); 0 → refused `declared-field-not-found`; ≥2 → refused `declared-field-ambiguous`. |
| L4 | Replay check | an existing link row for (invoice_id, declared_field_name, identifier_kind) → the existing outcome is re-verified through §6 and returned VERBATIM (`CustomerLinkReplay`) — ZERO new rows; replay never re-decides (OD-CL4). |
| L5 | Exact customer lookup | byte-exact lookup of (identifier_kind, canonical_value): 1 row → `LINKED` (to that EXISTING customer identity — D-06); 0 rows → `UNRESOLVED` (`no-customer-identity`); ≥2 rows → fail-closed `CustomerLinkInputIntegrityFailure` (structurally prevented by the UNIQUE register discipline; if ever observed it is store corruption, never a link decision). |
| L6 | Atomic commit | ONE immutable link row (outcome + anchors + pointer + customer reference), atomic single-row commit; commit collision on the UNIQUE declaration key → re-read the winner and return `CustomerLinkReplay` (read-only). |

Every refusal/integrity/storage outcome leaves ZERO durable residue.
NO outcome of the ladder ever creates, updates, or deletes a customer —
the ladder's write surface is exactly ONE append-only link row.

## 5. Durable link record (normative)

ONE immutable row per (invoice_id, declared_field_name, identifier_kind) —
INV-CL-1:1 (UNIQUE backstop):

- Anchors (copied verbatim from the verified P6.2 read): `invoice_id`,
  `capture_s1`, `capture_s1_algorithm_id`.
- Reference pointer (pointer discipline — NEVER the value, OD-CL6):
  `declared_field_name`, `canonical_seq`, `provenance` (D-01 label relayed).
- Linking declaration: `identifier_kind`.
- Outcome: `LINKED` (with `customer_identity_id` set, `unresolved_reason`
  empty) | `UNRESOLVED` (with `unresolved_reason` `no-customer-identity`,
  `customer_identity_id` empty) — storage CHECK gates both shapes; no third
  outcome exists.
- Bookkeeping: `link_id` (uuid — bookkeeping only), `created_at`,
  `record_fingerprint` (sha256-v1 via the project S1 service — no hashlib),
  `fingerprint_algorithm_id`.

The identifier VALUE is never stored in the link row (pointer discipline):
the invoice side is re-joined live from the verified P6.2 read; the customer
register stores the identifier as ITS OWN registered content.

## 6. Verified reads (normative)

`read_link_by_id`, `read_customer_identity` — definitive integrity verdict
computed INSIDE the read; a row that cannot be fully re-verified is
withheld, never served:

1. Own-row VOR (FAILED → integrity failure; NO-VERDICT → verification
   unavailable + Issue Report).
2. Linked invoice re-verification — the P6.2 verified read must succeed;
   anchor drift or pointer drift → withheld.
3. For LINKED: the linked customer identity re-verifies (own VOR) and the
   link is RE-PROVEN LIVE: customer identifier_kind == declared kind AND
   customer identifier_value == the invoice's re-joined canonical value
   (byte-identity). Any disagreement → withheld.
4. For UNRESOLVED: outcome shape re-checked. The historical absence fact is
   NOT re-decided against the grown register (OD-CL4): the record states
   what was true at link time; a later registration never rewrites it.

Register queries (listing discipline): `links_of(invoice_id)`, `customers()`.

## 7. Persistence (normative — the project pattern, unchanged)

ONE separate embedded SQLite file (`customer-linking.db`), stdlib sqlite3,
`PRAGMA synchronous=FULL`, idempotent schema, explicit `BEGIN IMMEDIATE` /
`COMMIT`, atomic single-row commit (zero residue on any failure), immutable
rows (no UPDATE / no DELETE — AST-proven), sha256-v1 record fingerprints
through the project S1 service (no hashlib in this layer), Verify-on-Read
support via canonical bytes, SQL CHECK gates + defensive Python-side
refusals mirroring every CHECK, UNIQUE backstops (customers:
(identifier_kind, identifier_value); links:
(invoice_id, declared_field_name, identifier_kind)), restart-safe.

## 8. Delegated implementation decisions (declared per D-09)

- **OD-CL1** Persistence exactly per §7 (project store pattern).
- **OD-CL2** No auto-create, structurally: the customer register's ONLY
  write path is the explicit registration API (no capture/invoice/document
  parameter); the link service's ONLY write is the append-only link row —
  there is no code path from an invoice/capture to a customer row. The
  register represents the minimal Customer-domain surface required by
  D-06's "link to an EXISTING Customer" (customers exist before invoices
  link to them — AS-02 native flow). No merge/dedup/enrichment features
  (DEF3/D-06 — PO territory).
- **OD-CL3** Identifier vocabulary = DECLARED opaque (kind, value) strings,
  stored and compared verbatim (byte-exact). NO enumeration, NO barcode
  semantics, NO grammar, NO checksum, NO normalization — none is
  established, and inventing one is forbidden.
- **OD-CL4** INV-CL-1:1 — ONE link outcome per declared reference, UNIQUE
  backstop; replay returns the existing outcome verbatim and NEVER
  re-decides (D-03 replay discipline analog). The durable outcome is a pure
  function of the invoice's verified content and the register at first-link
  time; a later registration never rewrites history (declared known
  limitation — a genuinely new linking decision over grown register state
  belongs to a future dispatch).
- **OD-CL5** The register enforces definitiveness by construction:
  UNIQUE(identifier_kind, identifier_value). Link-time counting is still
  count-based (0/1/≥2) and ≥2 fails closed.
- **OD-CL6** Declared-reference resolution rides the P6.2 canonical field
  inventory with the exactly-one rule (0 → `declared-field-not-found`, ≥2 →
  `declared-field-ambiguous`). Both D-01 provenances resolvable. Stored
  pointer = (declared_field_name, canonical_seq, provenance) — never the
  value.
- **OD-CL7** The ONLY link rule is the exact definitive-identifier rule —
  the project's established deterministic-matching semantics (D-05/P6.1);
  no fuzzy/semantic/AI/best-match/threshold mechanism exists. Ambiguity
  remains ambiguity: UNRESOLVED is durable and auditable.
- **OD-CL8** No canonicalization / identity-resolution / product /
  REVIEW / invoice-mutation vocabulary or logic; no mutation of any
  upstream record (the OD-A9 `deferred-wp9.1-d06-no-deterministic-link`
  reason on the frozen canonical invoice stands as the assembly-time fact —
  the link register is the WP-9.1 output, additive); no upstream execution;
  uuid bookkeeping only (AST-proven); no hashlib (the project S1 service
  only).

## 9. Acceptance mapping (REG-AR)

| AC | Requirement (summary) | Evidence |
|---|---|---|
| AC-9.1.1 | Customer register: explicit idempotent verbatim-replay registration of EXISTING customers; UNIQUE definitiveness backstop; NO capture path into the register (structural no-auto-create — D-06/DEF3) | test_cl_customers.py + AST/signature probes |
| AC-9.1.2 | Deterministic linking exactly per the established rule: declared reference + byte-exact single customer identity → LINKED; 0 → durable UNRESOLVED(`no-customer-identity`); ambiguity never auto-resolved; no fuzzy/AI/best-match surface anywhere; the ladder can NEVER create a customer (D-06) | test_cl_link.py + AST/no-creation probes |
| AC-9.1.3 | Delegation + persistence: P6.2 verified read consumed VERBATIM (fail-closed; spy-proven); INV-CL-1:1 with UNIQUE backstop + replay-verbatim; project store pattern (FULL/atomic/immutable/VOR/CHECK+UNIQUE/restart-safe; no UPDATE/DELETE; no hashlib — AST) | test_cl_service.py + test_cl_durability.py |
| AC-9.1.4 | Verified reads + boundaries: own VOR + linked invoice re-verification + pointer re-join + customer re-verification + LIVE byte-identity re-proof; tamper matrix withholds; frozen P1–P8.1 byte-untouched (full regression + git diff) | test_cl_boundary.py + test_cl_durability.py + regression |

## 10. Locked decisions

D-06 (binding: auto-create forbidden; deterministic link to an EXISTING
customer ONLY) | DEF3 | D-09 | AD-02 | AD-03 | AS-02 | AS-03 | AS-04/AD-04/
CL-1 | D-01 (provenance relay) | D-05 (the established exact
definitive-identifier matching semantics — the ONLY link rule) |
SPEC-WP62-CANASM (the upstream boundary + OD-A9 — this WP consumes the
verified read and never mutates the frozen canonical invoice) |
SPEC-WP71-IDRES (pointer-discipline precedent OD-IR-J) | SPEC-WP81-PMATCH
(sibling derivation — same discipline, distinct domain, no shared code path)
| MNT-1 baseline note.
