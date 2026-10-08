# SPEC-WP81-PMATCH — Product Exact Match (Product Candidate) Contract v1.0-MVP

```text
Spec ID:      SPEC-WP81-PMATCH | Version: 1.0-MVP | Date: 2026-10-08
Status:       IMPLEMENTATION CONTRACT (T-8.1.1) — produced inline per the
              Mission dispatch 2026-10-08 ("PRODUCT IDENTITY & CUSTOMER
              LINKING" — Phase A: WP-8.1 Exact Match).
Authority:    REG-WPR Phase Index P8 row (WP-8.1 Exact Match) + the Mission
              dispatch 2026-10-08 is the scope of record; this spec converts
              that scope into the binding implementation contract, derived
              ONLY from established frozen decisions, existing contracts, and
              downstream/upstream references (no invented product requirement).
Frozen basis: D-05 (Product Matching contractual output = `Exact Match /
              Candidate Generation / Candidate Approval / Catalog Identity`;
              EXACT MATCH ONLY WITH A DEFINITIVE VALID IDENTIFIER; fuzzy
              matching and occurrence-based promotion are implementation-level
              policy — NONE is implemented here; this WP implements exactly
              the first output and nothing else) | D-09 (no new architectural
              decision; delegated details declared OD-PM1..PM8) | AD-02
              (Product Candidate is its own domain; cross-domain access only
              through the destination domain's contract) | AS-02 (native flow
              Product → Sale → Invoice — catalog products PRECEDE invoices;
              no capture-derived product creation) | AS-04/AD-04/CL-1
              (verbatim-vocabulary discipline — quote, never paraphrase,
              never invent) | D-01 (provenance vocabulary relayed verbatim;
              no UNRESOLVED is created by THIS layer's matching decision
              vocabulary — the stable outcome word UNRESOLVED below is a
              Product-Candidate-domain match fact, not a P5 field status) |
              AS-03 (no state invention) | AD-03 (no inventory effect) |
              D-06/DEF3 analog discipline for products (no capture-derived
              catalog mutation — structural, see OD-PM2).
Baseline note (MNT-1): the physical Master Architecture / Canonical Invoice v1
              documents are not committed; the Decision Register + this
              Mission dispatch are the valid self-contained representation
              (pre-registered, not a STOP cause). Where the dispatch demands
              content no upstream contract carries (a product-identifier
              field role, a catalog), the mechanism is a DECLARED input or an
              explicitly scoped minimal register (OD-PM2/OD-PM3/OD-PM6) —
              NEVER a guess.
Upstream:     P1 → … → P6.1 → P6.2 → **P8.1**. The ONLY value/admission path
              is the WP-6.2 verified read (`CanonicalAssemblyService.
              read_assembled_invoice`) — consumed, never bypassed, never
              triggered; this layer never reads any upstream store directly
              and never executes any pipeline stage.
Downstream:   Product Candidate domain consumers. WP-8.2 (Candidate
              Generation & Approval) is NOT part of this Mission and is NOT
              pre-built here: no candidate row, no confidence, no approval
              state, no fuzzy surface exists in this layer.
```

## 1. Purpose and scope

WP-8.1 implements the FIRST output of the frozen D-05 four-part Product
Matching contract — **Exact Match** — as a durable, auditable,
deterministic Product Candidate domain fact, plus the minimal
**Catalog Identity register** it requires (OD-PM2). The rule implemented is
exactly the frozen rule: an Exact Match exists ONLY where a declared product
reference carries a definitive valid identifier AND the catalog register
holds exactly one catalog identity for that identifier (byte-identical,
under the declared identifier kind). Everything else stays unresolved:
**ambiguity remains ambiguity** — no candidate is generated, no confidence is
computed, no approval is simulated, no fuzzy/semantic/AI/heuristic matching
of ANY kind exists in this layer (Mission dispatch; D-05).

- **Catalog identity** — a registered catalog product identity: the minimal
  Product-side register surface (identifier kind + identifier value + bookkeeping)
  required by D-05's `Catalog Identity` output. Population is EXPLICIT
  declared registration ONLY (AS-02 native flow — products exist before
  invoices); the registration API carries no capture/invoice/document
  parameter, so capture-derived or automatic catalog mutation is structurally
  absent (OD-PM2).
- **Exact match** — a declared product reference on an issued Canonical
  Invoice (P6.2) whose declared identifier value byte-matches exactly one
  catalog identity under the declared identifier kind. The match outcome is
  ONE immutable, append-only Product Candidate record (INV-PM-1:1 per
  declared reference), pointing at the catalog identity — the D-05 Catalog
  Identity output — with full live re-verification on every read.
- **Unresolved reference** — a declared reference with NO catalog identity
  for its identifier: a durable, auditable UNRESOLVED match fact with a
  stable reason (`no-catalog-identity`). It is a fact about the moment of
  matching, never rewritten by later registrations (append-only; replay
  never re-decides — OD-PM4).

In scope:
1. **Catalog identity register** — explicit, idempotent, append-only
   registration of catalog identities; UNIQUE(identifier_kind,
   identifier_value) backstop makes a definitive identifier map to exactly
   one catalog identity by construction (OD-PM5).
2. **Exact match service** — declared-reference resolution against the P6.2
   verified read + the deterministic exact-match decision + atomic durable
   commit (§4/§5).
3. **Verified match reads** — own-row VOR + re-verification of the linked
   invoice through the P6.2 verified read + pointer re-join + catalog
   identity re-verification + the LIVE byte-identity re-proof (§6).
4. **Register queries** — `matches_of(invoice_id)`, `catalog()` (§6).
5. **Persistence** per the project store pattern (§7/§8).
6. Behavioral + structural boundary tests (delegation/pointer discipline,
   adversarial matrix, durability, concurrency, AST probes, frozen-layer
   protection).

Out of scope (FORBIDDEN — dispatch): candidate generation, candidate
approval, confidence scores/thresholds, occurrence-based promotion, fuzzy/
semantic/AI matching of ANY kind (D-05 reserves them as implementation-level
policy under later WPs; this Mission forbids inventing them); barcode
semantics (checksums, format grammars, kind enumerations — none is
established; identifier kinds are DECLARED opaque strings, OD-PM3);
canonicalization re-decision; identity resolution (P7.1); customer anything
(WP-9.1); REVIEW queue operations; invoice/canonical-record mutation (P6.2
rows are immutable — this layer only ADDS its own register rows); product
creation from capture or enrichment (structurally absent — OD-PM2); catalog
merge/dedup/pricing/stock (no product-management feature — AD-03, DEF1);
any change to any frozen layer P1–P7.2; upstream execution; Holoo parser;
Cloud sync; UI; mobile.

## 2. Input path (normative)

The ONLY invoice/value input path is the WP-6.2 public verified read
(`CanonicalAssemblyService.read_assembled_invoice(invoice_id)`) — consumed
VERBATIM inside every `match` call. The matching service never reads any
upstream store directly, never reads raw artifacts, never re-computes an
identity or content fingerprint of any upstream record (beyond its own
record-integrity anchors, §8), never executes any pipeline stage, and never
accepts invoice facts from any source other than the P6.2 outcome objects.

The catalog register is the ONLY other input, populated exclusively by the
explicit `register_catalog_identity` API — never by any capture/pipeline path.

## 3. Request contract (normative)

`match(invoice_id, declared_field_name, identifier_kind)` — ONE declared
product reference on ONE issued Canonical Invoice:

- `invoice_id` — the P6.2 issued invoice identifier (the D-02 Canonical
  Identity, consumed verbatim; no identifier is validated beyond
  non-emptiness — existence and integrity are established by the P6.2
  verified read, fail-closed).
- `declared_field_name` — the engine-vocabulary field name of the canonical
  field carrying the product identifier (DECLARED, never discovered — the
  OD-A4 discipline). Resolution requires EXACTLY ONE canonical field entry
  with that name in the invoice's verified field inventory: 0 → request
  refused (`declared-field-not-found`); ≥2 → request refused
  (`declared-field-ambiguous`) — picking one would be auto-resolution
  (forbidden; P6.2 §6 L1 / P6.1 discipline). Both D-01 provenances
  (EXTRACTED | DERIVED) are verified P6.2 content and equally resolvable
  (OD-PM6).
- `identifier_kind` — the DECLARED opaque identifier vocabulary label
  (verbatim, compared byte-exactly; no enumeration, no semantics — OD-PM3).

There is no second request vocabulary, no options, no override switches.

`register_catalog_identity(identifier_kind, identifier_value)` — ONE
explicit catalog registration. Both arguments must be non-empty; the content
is stored verbatim (no trimming, no case folding, no re-normalization — P4.1
is the sole normalizer and this layer performs none). Re-registering the
same (kind, value) returns the existing catalog identity VERBATIM
(idempotent replay — no second row).

## 4. Matching ladder (normative — fail-closed, ordered)

The match service performs exactly ONE P6.2 verified read per call and maps
the outcome deterministically:

| # | Step | Action |
|---|---|---|
| M1 | P6.2 verified read | `read_assembled_invoice(invoice_id)` — any non-success (refused / integrity failure / verification unavailable) → fail-closed passthrough with ZERO durable residue (details verbatim; never reformulated). |
| M2 | Declaration validation | empty `invoice_id` / `declared_field_name` / `identifier_kind` → `ProductMatchRequestRefused` (`declaration-malformed`), zero residue. |
| M3 | Declared-reference resolution | exactly one canonical field entry with `declared_field_name` → the reference (value + pointer + provenance); 0 → refused `declared-field-not-found`; ≥2 → refused `declared-field-ambiguous` (never auto-resolution). |
| M4 | Replay check | an existing match row for (invoice_id, declared_field_name, identifier_kind) → the existing outcome is re-verified through §6 and returned VERBATIM (`ProductMatchReplay`) — ZERO new rows; replay never re-decides (OD-PM4). |
| M5 | Exact catalog lookup | byte-exact lookup of (identifier_kind, canonical_value) in the catalog register: 1 row → `EXACT_MATCHED`; 0 rows → `UNRESOLVED` (`no-catalog-identity`); ≥2 rows → fail-closed `ProductMatchInputIntegrityFailure` (structurally prevented by the UNIQUE register discipline — a definitive identifier maps to exactly one catalog identity by construction; if ever observed it is store corruption, never a match decision). |
| M6 | Atomic commit | ONE immutable match row (outcome + anchors + pointer + catalog reference), atomic single-row commit; commit collision on the UNIQUE declaration key → re-read the winner and return `ProductMatchReplay` (read-only). |

Every refusal/integrity/storage outcome leaves ZERO durable residue.

## 5. Durable match record (normative)

ONE immutable row per (invoice_id, declared_field_name, identifier_kind) —
INV-PM-1:1 (UNIQUE backstop):

- Anchors (copied verbatim from the verified P6.2 read for cross-store
  verification): `invoice_id`, `capture_s1`, `capture_s1_algorithm_id`.
- Reference pointer (pointer discipline — NEVER the value, OD-PM6):
  `declared_field_name`, `canonical_seq` (the stable gap-free assembly-order
  position of the resolved canonical field), `provenance` (the D-01 label of
  the resolved field, relayed verbatim).
- Matching declaration: `identifier_kind`.
- Outcome: `EXACT_MATCHED` (with `catalog_identity_id` set,
  `unresolved_reason` empty) | `UNRESOLVED` (with `unresolved_reason`
  `no-catalog-identity`, `catalog_identity_id` empty) — storage CHECK gates
  both shapes; no third outcome exists.
- Bookkeeping: `match_id` (uuid — bookkeeping only), `created_at`,
  `record_fingerprint` (sha256-v1 over the canonical record bytes via the
  project S1 service — no hashlib in this layer), `fingerprint_algorithm_id`.

The identifier VALUE is never stored in the match row (pointer discipline,
OD-IR-J analog): the invoice side is re-joined live from the verified P6.2
read; the catalog side stores the identifier as its OWN registered content.

## 6. Verified reads (normative)

`read_match_by_id`, `read_catalog_identity` — definitive integrity verdict
computed INSIDE the read; a row that cannot be fully re-verified is
withheld, never served:

1. Own-row VOR (record_fingerprint recomputed and compared; FAILED →
   integrity failure; NO-VERDICT → verification unavailable + Issue Report).
2. Linked invoice re-verification — the P6.2 verified read must succeed;
   anchor drift (capture_s1) or pointer drift (canonical_seq out of range,
   field_name/provenance disagreement) → withheld (verification unavailable
   / integrity failure).
3. For EXACT_MATCHED: the linked catalog identity re-verifies (own VOR) and
   the match is RE-PROVEN LIVE: catalog identifier_kind == declared kind AND
   catalog identifier_value == the invoice's re-joined canonical value
   (byte-identity). Any disagreement → withheld.
4. For UNRESOLVED: outcome shape re-checked (`catalog_identity_id` empty,
   reason `no-catalog-identity`). The historical absence fact is NOT
   re-decided against the grown catalog (OD-PM4): the record states what was
   true at match time; a later registration never rewrites it.

Register queries (listing discipline — raw rows; consumers verify through
the verified reads): `matches_of(invoice_id)`, `catalog()`.

## 7. Persistence (normative — the project pattern, unchanged)

ONE separate embedded SQLite file (`product-candidate.db`), stdlib sqlite3,
`PRAGMA synchronous=FULL`, idempotent schema, explicit `BEGIN IMMEDIATE` /
`COMMIT`, atomic single-row commit (zero residue on any failure), immutable
rows (no UPDATE / no DELETE — AST-proven), sha256-v1 record fingerprints
computed through the project S1 service (no hashlib in this layer),
Verify-on-Read support via canonical bytes, SQL CHECK gates + defensive
Python-side refusals mirroring every CHECK, UNIQUE backstops
(catalog: (identifier_kind, identifier_value); matches:
(invoice_id, declared_field_name, identifier_kind)), restart-safe.

## 8. Delegated implementation decisions (declared per D-09)

- **OD-PM1** Persistence exactly per §7 (project store pattern; single DB
  file; atomic; immutable; CHECK+UNIQUE gates; restart-safe; sha256-v1 via
  the S1 service).
- **OD-PM2** The Catalog Identity register is the minimal Product-side
  surface required by D-05's `Catalog Identity` output, implemented inside
  this WP because no other registered WP provides it. Population = explicit
  declared registration ONLY; the registration API carries no
  capture/invoice/document parameter → no capture-derived or automatic
  catalog mutation is possible (AS-02 native flow: products precede
  invoices; the D-06/DEF3 no-auto-create discipline applied structurally to
  the catalog side). No product-management features (pricing, stock, merge,
  dedup) — AD-03/DEF1 untouched.
- **OD-PM3** Identifier vocabulary = DECLARED opaque (kind, value) strings,
  stored and compared verbatim (byte-exact). NO kind enumeration, NO barcode
  semantics, NO format grammar, NO checksum, NO normalization — none is
  established by any frozen record, and inventing one is forbidden.
  "Definitive valid identifier" is realized as: declaration structurally
  sound + value present (a NORMALIZED canonical value is non-empty by the
  P4.1 grammar) + exactly one catalog identity under the declared kind.
- **OD-PM4** INV-PM-1:1 — ONE match outcome per declared reference
  (invoice_id, declared_field_name, identifier_kind), UNIQUE backstop;
  replay returns the existing outcome verbatim and NEVER re-decides (the
  D-03 replay discipline applied to the match fact). The durable outcome is
  a pure function of the invoice's verified content and the catalog register
  at first-match time. A later registration does not rewrite history; a
  genuinely new matching decision over grown catalog state is WP-8.2
  territory (known limitation, declared).
- **OD-PM5** The catalog register enforces definitiveness by construction:
  UNIQUE(identifier_kind, identifier_value). Match-time counting is still
  count-based (0/1/≥2) and ≥2 fails closed — the rule survives future
  register evolution without change.
- **OD-PM6** Declared-reference resolution rides the P6.2 canonical field
  inventory: field-name declaration + exactly-one-usable-entry rule (0 →
  `declared-field-not-found`, ≥2 → `declared-field-ambiguous`; never
  auto-resolution). Both D-01 provenances are resolvable verified content.
  Stored pointer = (declared_field_name, canonical_seq, provenance) — never
  the value.
- **OD-PM7** No candidate generation / approval / confidence / fuzzy /
  semantic / AI / occurrence-based mechanism exists in this layer (D-05
  reserves them for later WPs under their own decisions; this Mission
  forbids inventing them). UNRESOLVED is durable and auditable; ambiguity
  remains ambiguity.
- **OD-PM8** No canonicalization / identity-resolution / customer /
  REVIEW / invoice_id vocabulary or logic anywhere in this layer; no
  mutation of any upstream record; no upstream execution; uuid bookkeeping
  only (AST-proven); no hashlib (the project S1 service only).

## 9. Acceptance mapping (REG-AR)

| AC | Requirement (summary) | Evidence |
|---|---|---|
| AC-8.1.1 | Catalog register: explicit idempotent verbatim-replay registration; UNIQUE definitiveness backstop; no capture path into the register (structural) | test_pm_catalog.py + AST/signature probes |
| AC-8.1.2 | Exact match exactly per D-05: declared reference + byte-exact single catalog identity → EXACT_MATCHED pointing at the catalog identity; 0 → durable UNRESOLVED(`no-catalog-identity`); ambiguity never auto-resolved; no fuzzy/AI/confidence/candidate surface anywhere | test_pm_match.py + AST vocabulary sweep |
| AC-8.1.3 | Delegation + persistence: P6.2 verified read consumed VERBATIM (fail-closed passthrough; spy-proven); INV-PM-1:1 with UNIQUE backstop + replay-verbatim; project store pattern (FULL/atomic/immutable/VOR/CHECK+UNIQUE/restart-safe; no UPDATE/DELETE; no hashlib — AST) | test_pm_service.py + test_pm_durability.py |
| AC-8.1.4 | Verified reads + boundaries: own VOR + linked invoice re-verification + pointer re-join + catalog re-verification + LIVE byte-identity re-proof; tamper matrix withholds; frozen P1–P7.2 byte-untouched (full regression + git diff) | test_pm_boundary.py + test_pm_durability.py + regression |

## 10. Locked decisions

D-05 (binding four-part contract; exact match only with a definitive valid
identifier) | D-09 | AD-02 | AD-03 | AS-02 | AS-03 | AS-04/AD-04/CL-1 |
D-01 (provenance relay) | D-06/DEF3 (no-auto-create discipline, applied
structurally per OD-PM2) | SPEC-WP62-CANASM (the upstream boundary — its
verified read is the binding input contract; OD-A9 customer absence is
WP-9.1 territory, not touched here) | SPEC-WP71-IDRES (pointer-discipline
precedent OD-IR-J) | MNT-1 baseline note.
