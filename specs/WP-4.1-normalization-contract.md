# SPEC-WP41-NORM — Normalization Contract v1.0-MVP

```text
Register ID:  SPEC-WP41-NORM | Version: 1.0-MVP | Date: 2026-10-01 | Owner: Technical Manager
Produced:     inline (T-4.1.1) per TM dispatch 2026-10-01 — P4 implementation mission, no new
              Design/Review stage; decomposition minimal and inline; Build → Test → Fix → Done.
Authority:    D-01 (provenance vocabulary EXTRACTED | DERIVED | UNRESOLVED — untouched) |
              D-02/D-03 (untouched) | D-09 (no engine selection; implementation choices declared) |
              AS-01 (flow position: Extraction → **Normalization** → Canonicalization Gate) |
              SPEC-WP31-EXT §2 (the verified extraction read is the ONLY input path) |
              SPEC-WP32-EVB (binding consumed strictly read-only; guarantees never weakened)
Clarification: pre-freeze correction 2026-10-05 (WP-4.1-FREEZE-CORR) — adds §4.1 (DEFERRED
              is a NORMALIZATION-LAYER outcome; DEFERRED ≠ UNRESOLVED; WP-4.1 never creates,
              assigns, infers, or resolves UNRESOLVED) and §4.2 (DERIVED boundary: no DERIVED
              computation, no unit_amount calculation, no semantic arithmetic, no inference of
              missing business values). NO rule, grammar, status value, mapping, persistence,
              or determinism behavior was changed — behavior is identical to 2026-10-01.
```

## 1. Purpose and scope

`verified Extraction output → Normalized structured data`. NOTHING else.

Normalization is a deterministic transformation layer between Extraction engines and the
future Canonicalization Gate. It makes extracted values structurally stable and comparable
(whitespace, Unicode form, numeric representation) WITHOUT taking any identity or business
decision. Every normalized value stays machine-checkably traceable to its source extracted
field and — through WP-3.2 Evidence Binding — to Document/Page + source span + Capture S1.

**Non-goals (normative):** canonical field mapping, product/customer/invoice identity,
fuzzy or semantic matching, Sale/Invoice/Digital Invoice creation, Inventory effects, tax or
business rules, currency invention/conversion, OCR/VLM/external AI calls, frontend/UI.
`DERIVED` provenance values (WP-4.2) are NOT produced here; `UNRESOLVED` (later domain /
validation / canonicalization layers) is not produced here — see §4.1/§4.2. No value is ever
silently "fixed": anything outside the declared grammar gets an explicit per-field status.

## 2. Input path (normative — mirrors SPEC-WP31-EXT §2)

The ONLY sanctioned input is `ExtractionService.read_extraction(extraction_id)` returning
`ExtractionReadSuccess` (same-read VALID verdict). This layer never reads extraction/
document/capture stores in parallel and never re-derives anything upstream. Exhaustive
source outcomes map 1:1:
`ExtractionReadIntegrityFailure → NormalizationSourceIntegrityFailure` |
`ExtractionReadRefused → NormalizationSourceRefused` |
`ExtractionReadVerificationUnavailable → NormalizationSourceUnavailable` (Issue-Report surfaced).
Engine independence: this layer imports NO engine module and receives no PageView/span bytes;
the ruleset seam is constructor-injected exactly like the P3 engine seam.

## 3. Normalization rule set (versioned, declarative, extensible)

A ruleset is a replaceable seam (`NormalizationRuleSet`: `ruleset_id`, `ruleset_version`,
`kind_profile`, `normalize_field(field) -> NormalizedField`). `ReferenceNormalizationRulesV1`
(`kandoo-norm-v1`, version `1`) is the MVP reference — declared data, not hidden magic:

- **Pipeline order per field (deterministic):** control-character gate → NFC → trim → kind rule.
- **R-N0 control gate:** any character of Unicode category `Cc` except `\t\n\r` anywhere in the
  value → status `REJECTED`, reason `control-character` (corruption marker; normalizing it
  would launder corrupted data).
- **R-N1 nfc:** `unicodedata.normalize("NFC", value)` — deterministic Unicode standardization.
- **R-N2 trim:** strip leading/trailing Unicode whitespace (incl. NBSP U+00A0). Internal
  whitespace is NEVER touched (no semantic rewriting).
- **R-N3 empty:** value empty after trim → `DEFERRED`, reason `empty-value` (missing/absent
  fields simply have no normalized counterpart — nothing is invented; whitespace-only is a
  special case of empty).
- **Kind selection:** `kind_profile[field_name]`, fallback `text` for unknown names (declared
  fallback, not a guess). Profile v1 (SYNTAX kind only — no meaning decision):
  `date`: invoice.date | `decimal`: total.gross, total.net, tax.amount, unit_amount, quantity |
  `text`: everything else (invoice.number, seller.name, buyer.name, currency.label, notes, …).
- **R-T1 text:** nfc + trim. Identity/encoding of identifiers untouched (no case folding,
  no leading-zero change).
- **R-D1 decimal (monetary + quantity — one grammar, precision-preserving):** after nfc+trim,
  accept ONLY the declared grammar, output a canonical decimal STRING (never float):
    1. `^[+-]?[0-9]+$` → canonical integer string (`int()` round-trip; `+` dropped;
       leading zeros stripped; `-0` → `0`).
    2. single separator `.` or `,` between digit groups → decimal point `.` — BUT if the shape
       is thousands-ambiguous (integer part 1–3 digits not starting with `0`, fraction exactly
       3 digits — e.g. `1.234`, `12,345`) → `DEFERRED`, reason `not-in-declared-grammar`.
    3. complete thousands grouping: European `[0-9]{1,3}(\.[0-9]{3})+(,[0-9]+)?` or English
       `[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?` → remove group separators, decimal separator → `.`.
    4. anything else (currency symbols, `.5`, `5.`, `1.2.3`, internal whitespace) → `DEFERRED`,
       reason `not-in-declared-grammar`.
  Fraction digits are preserved VERBATIM (no rounding, no trailing-zero trimming — monetary
  precision is not silently altered). Sign kept iff numeric value ≠ 0.
- **R-DT1 date:** nfc+trim, then strict `YYYY-MM-DD` + calendar validity (`date.fromisoformat`)
  → value unchanged; anything else → `DEFERRED` `not-in-declared-grammar`. No locale parsing,
  no calendar conversion, no date arithmetic.
- `rules_applied` records the applied chain verbatim (`nfc,trim` / `nfc,trim,number-canonical`
  / `nfc,trim,date-iso`); empty for DEFERRED/REJECTED.

## 4. Per-field status vocabulary (explicit, exhaustive)

`NORMALIZED` (normalized_value present, reason_code NULL) |
`DEFERRED` (declared grammar does not cover the value; normalized_value NULL) |
`REJECTED` (structural corruption marker; normalized_value NULL).
Mapping is TOTAL and positional: every extracted field yields exactly one normalized field at
the same field_seq — no silent skips, no fabrication. Field counts in the record
(normalized_count + deferred_count + rejected_count == field_count) make this checkable.

### 4.1 DEFERRED — semantic clarification (normative, pre-freeze 2026-10-05)

`DEFERRED` is a **normalization-layer outcome and nothing else**:

> The Normalization layer cannot safely transform the extracted value into its normalized
> representation under the currently declared normalization grammar/rules, so it deliberately
> performs no interpretation and passes the situation forward without inventing a value.

Declared examples (non-exhaustive):
- ambiguous numeric formatting (e.g. `1.234`, `12,345` — thousands-ambiguous shapes);
- malformed numeric representation (e.g. `1.2.3`, `12 EUR`, `.5`);
- unsupported date representation (e.g. `01.10.2026`, `2026/10/01`, calendar-invalid dates);
- empty / whitespace-only value where normalization cannot produce a value.

**`DEFERRED ≠ UNRESOLVED` (normative):**

- `DEFERRED` MUST NOT imply any business-level unresolved status. It carries NO domain,
  identity, validation, or workflow meaning — it states only "not transformable under the
  currently declared grammar; no value invented; passed forward as-is".
- `UNRESOLVED` is a D-01 provenance label belonging to LATER domain / validation /
  canonicalization layers (per D-01 §2.A the resolution order `EXTRACTED → DERIVED →
  UNRESOLVED` terminates downstream — e.g. Validation may take an Invoice to `REVIEW`);
  it is NOT part of the normalization status vocabulary and has no producer in WP-4.1.
- **WP-4.1 MUST NOT create, assign, infer, or resolve `UNRESOLVED`** — not as a status, not
  as a provenance label, not as a reason code, not as any other datum. This is structurally
  enforced: the status vocabulary is exhaustive at exactly three values (§4), the D-01
  relay is storage-gated to `EXTRACTED` only (§5, OD-N6), and both gates are test-proven.

### 4.2 DERIVED boundary (normative, pre-freeze 2026-10-05)

WP-4.1 does NOT compute DERIVED values:

- WP-4.1 does not calculate `DERIVED` provenance values — DERIVED computation is WP-4.2
  territory and stays outside WP-4.1.
- WP-4.1 does not calculate `unit_amount` from other fields, or from anything else.
- WP-4.1 performs NO semantic arithmetic between fields (no sums, products, ratios, tax or
  rounding computations — no cross-field calculation exists in this layer).
- WP-4.1 does not infer missing business values (a field absent from the extraction yields
  NO normalized field — the mapping is TOTAL and positional, never creative).

`unit_amount` appears in the kind profile ONLY as a declared SYNTAX kind (the decimal
grammar of §3): its normalized value is the grammar form of its OWN verbatim input, or an
explicit DEFERRED — never a semantic computation from `quantity`/`line totals`/any other
field. The mapping total (field_count equality) makes any invented field detectable.

## 5. Data model (exact field sets — structural test enforced)

- `NormalizedField(field_seq, source_field_name, source_provenance, status, normalized_value,
  rules_applied, reason_code)`.
- `NormalizationRecord(normalization_id, extraction_id, document_id, capture_id, capture_s1,
  capture_s1_algorithm_id, engine_id, engine_schema_version, ruleset_id, ruleset_version,
  field_count, normalized_count, deferred_count, rejected_count, created_at,
  record_fingerprint, fingerprint_algorithm_id)`.
- Provenance: `source_provenance` relays the extracted field's D-01 label VERBATIM (always
  `EXTRACTED` in this layer — storage-level CHECK; DERIVED/UNRESOLVED never produced here).
- Traceability: `(extraction_id, field_seq)` is the machine-checkable pointer to the source
  extracted field; span/byte data is NOT duplicated (WP-3.2 binding already anchors it —
  join verified reads, never copy). No raw artifacts, no image data, no engine-internal
  structures in the normalized model.

## 6. Determinism (normative)

Rule functions are pure: same input bytes + same ruleset version → same normalized content,
always (no time, no locale, no randomness, no environment). Content determinism is separated
from record identity exactly like P3: `normalization_id` (uuid4) and `created_at` (layer
clock) are integrity/bookkeeping scalars, NOT part of rule determinism; INV-N-1:1 guarantees
the same (extraction_id, ruleset_id, ruleset_version) is never normalized twice, so no
mutable duplicate can drift.

## 7. Persistence & INV-N-1:1 (same store pattern as P3)

Store = separate embedded SQLite file (`synchronous=FULL`, `BEGIN IMMEDIATE`, no UPDATE/DELETE
path — immutable historical records). Record + fields commit in ONE atomic transaction →
zero residue by construction. Uniqueness INV-N-1:1: at most one record per
`(extraction_id, ruleset_id, ruleset_version)` — in-transaction check + UNIQUE index backstop;
replay returns `NormalizationAlreadyExists` with the existing id. A different ruleset or
version is a SEPARATE record (rule extensibility without rewriting history).
Verified read (VOR pattern): `record_fingerprint` = sha256-v1 (reused capture S1 capability)
over `canonical_normalization_bytes` (record scalars + fields in field_seq order), recomputed
INSIDE every read; content delivered only on the same-read VALID verdict. Exhaustive read
outcomes: `NormalizationReadSuccess | NormalizationReadIntegrityFailure |
NormalizationReadRefused | NormalizationReadVerificationUnavailable`.

## 8. Outcomes (exhaustive — never silent)

`NormalizationCompleted | NormalizationAlreadyExists | NormalizationSourceIntegrityFailure |
NormalizationSourceRefused | NormalizationSourceUnavailable | NormalizationRulesetNotRegistered
| NormalizationStorageUnavailable` — plus the four read outcomes above.

## 9. Delegated implementation details (declared per D-09 — OD-N1..OD-N8)

- **OD-N1** storage: stdlib sqlite3, one SEPARATE embedded local DB file; `synchronous=FULL`;
  `isolation_level=None` → explicit `BEGIN IMMEDIATE`/`COMMIT`; idempotent schema.
- **OD-N2** atomic commit: record + fields in one transaction; any failure → ROLLBACK, zero
  residue; no ACTIVE state, no recovery sweep.
- **OD-N3** INV-N-1:1: in-transaction check + UNIQUE index `uq_normalization_extraction_ruleset`.
- **OD-N4** ids: `normalization_id` = uuid4 hex; clock = single layer clock (`utc_now_iso`).
- **OD-N5** integrity anchor: `record_fingerprint` = sha256-v1 over `canonical_normalization_bytes`
  (reuse of `S1Service`); verified on every read.
- **OD-N6** storage gates: SQL CHECKs — `source_provenance = 'EXTRACTED'`;
  `status ∈ {NORMALIZED, DEFERRED, REJECTED}`; `normalized_value` NULL iff status ≠ NORMALIZED;
  `reason_code` NULL iff status = NORMALIZED; plus defensive Python-side commit refusal.
- **OD-N7** no UPDATE/DELETE path exists anywhere in the store API.
- **OD-N8** `ReferenceNormalizationRulesV1` is the MVP reference ruleset (executability
  choice), NOT a business-rule decision; new rule versions plug into the same seam.

## 10. AC mapping (verification in Acceptance Register)

| AC | Requirement | Spec section |
|---|---|---|
| AC-4.1.1 | Deterministic total per-field normalization; explicit statuses/reasons; provenance relayed EXTRACTED-only; same input+version → identical content | §3, §4, §5, §6 |
| AC-4.1.2 | Machine-checkable traceability normalized → extracted → (WP-3.2 binding) → Document/Page/span → Capture S1; binding/evidence guarantees unchanged | §2, §5 |
| AC-4.1.3 | Durable store per §7 (atomic, INV-N-1:1, replay explicit, no UPDATE/DELETE, VOR verified read, restart-safe, zero residue) | §7 |
| AC-4.1.4 | Boundary (no canonicalization/identity/business datum; engine-independent) + full Frozen regression green | §1, §2, §9 |

## 11. Test expectations (behavior, not line coverage)

whitespace/NFC normalization | empty + whitespace-only | missing-field non-invention |
integer/decimal/thousands matrix (incl. ambiguous → DEFER) | malformed numeric → DEFER |
decimal quantities preserved | monetary precision preserved (string storage, no float) |
deterministic output + repeated normalization (INV-N-1:1 replay) | source-engine independence
(stub-engine equivalence) | provenance preservation | evidence-linkage preservation (binding
still verifies after normalization) | invalid input (tampered source → explicit failure, zero
residue) | persistence/reload across restart | full P1/P2/P3 regression.
Pre-freeze boundary tests (2026-10-05, §4.1/§4.2): ambiguous numeric → DEFERRED not
UNRESOLVED | malformed numeric → DEFERRED not UNRESOLVED | unsupported date → DEFERRED not
UNRESOLVED | empty/whitespace-only → declared normalization-level deferred behavior |
no DERIVED provenance produced (incl. storage-gate refusal of DERIVED/UNRESOLVED rows) |
no unit_amount arithmetic / no invented field | declared-grammar outputs unchanged.
