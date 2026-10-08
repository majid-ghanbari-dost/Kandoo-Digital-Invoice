# kandoo/src/capture — WP-1.1 Capture Layer (MVP implementation)

Implementation of the four frozen documents (binding, verbatim):

| Component | File | Implements |
|---|---|---|
| Domain model + outcomes | `model.py` | Contract v1.1 §5–§7, §14 (14-field record, lifecycle, explicit outcomes) |
| S1 capability | `s1.py` | S1 Design v1.0 §3–§5 (SHA-256, `sha256-v1`, NO-VERDICT semantics) |
| Durable store | `store.py` | Store Design v0.2 (R-1/R-2, UAC P1–P6, §6.1 D-1/D-2, restricted writer, completion gate, COMPLETED-restricted lookup) |
| Orchestration | `service.py` | S1 §6 ingest flow + VOR §3–§7 read path (V-3, R-V1, write-before-outcome) |
| Startup recovery | `recovery.py` | Contract §11 / Store §5 (scan → settle, idempotent, INV-C6) |

Entry-point smoke check (no pytest needed): `python3 src/run_smoke.py [db_path]` (from repo root).

## Run the tests

```bash
cd kandoo/src
python3 -m pytest capture/tests/ -v
```

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

## Delegated implementation decisions (declared per D-09 / §16)

- Storage: embedded single-file SQLite (durable, local, no network service — OD-1/OD-4, `synchronous=FULL`)
- UAC mechanism: `BEGIN IMMEDIATE` + in-transaction uniqueness check + partial UNIQUE index backstop (OD-5, realizes P1–P6)
- `capture_id` = uuid4 hex (OD-3); `artifact_ref` = `capture-content:v1:<uuid4hex>` opaque locator into the `artifact_content` table (OD-2)
- S1 = SHA-256 full digest, lowercase hex, `sha256-v1` (OD-S1/OD-S2)
- Aggregation (entry point): 8-byte big-endian length-prefixed concatenation in list order — deterministic (v1.1-C3)
- Clock: one layer clock, UTC ISO-8601 (OD-8/OD-V2)
- Verification timing: every content-delivering read verifies inside the read; no caching (R-V1)
- Duplicate-attempt logging / FAILED-reason audit log: not implemented (optional per §16 — OD-6/OD-S3/OD-V1)

---

# kandoo/src/reconstruction — WP-2.1 Reconstruction + WP-2.2 Evidence (MVP implementation)

## WP-2.1 — Page Ordering & Artifact Reconstruction (SPEC-WP21-RC v1.0-MVP)

| Component | File | Implements |
|---|---|---|
| Domain model + outcomes | `model.py` | Contract §2–§7 (Document/Page fields, lifecycle, explicit outcomes) |
| Page derivation | `pages.py` | Contract §5 (mechanical framing parse — content-blind, deterministic) |
| Durable Document/Page store | `store.py` | Contract §2–§4 (record-first, UAC INV-R-1:1, settlement, D-1/D-2 analogs) |
| Orchestration | `service.py` | Contract §2–§7 (verified capture read → build → first verification → completion; VOR-pattern document read) |
| Startup recovery | `recovery.py` | Contract §4/§8 (zero-ACTIVE settlement, document-internal verification) |

## WP-2.2 — Reconstruction Evidence (SPEC-WP22-REC v1.0-MVP)

| Component | File | Implements |
|---|---|---|
| Evidence store + chain + spans | `evidence.py` | Contract §2–§6 (append-only log, sha256-v1 record fingerprints, tamper-evident hash chain + head anchor, page→source byte spans, verified evidence read, verify_chain) |
| Non-intrusive emission | `service.py`, `recovery.py` (optional `evidence=` param) | Contract §7 (document-scoped events: DOCUMENT_COMPLETED / DOCUMENT_SETTLED_FAILED / VERIFIED_READ / RECOVERY_SETTLED; failures → issue surfacing, never behavior change) |

Entry-point smoke checks (no pytest needed):
- `python3 src/run_smoke.py [base]` — WP-1.1 capture MVP path
- `python3 src/run_smoke_reconstruction.py [base]` — WP-2.1 capture → document → ordered pages → verified read
- `python3 src/run_smoke_evidence.py [base]` — WP-2.2 evidence path (spans, chain, tamper detection)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest capture/tests/ reconstruction/tests/ -v
```

## Delegated implementation decisions (WP-2.2, declared per D-09)

- OD-E1: evidence log = separate embedded SQLite file (append-only; `synchronous=FULL`; no UPDATE/DELETE path)
- OD-E2: fixed document-scoped event vocabulary (4 types); payload keys whitelisted per type
- OD-E3: record_fingerprint = sha256-v1 over canonical record bytes (reused capture S1 capability);
  record_hash chains to the previous record (genesis `0`×64); `evidence_head` anchor written in the
  same append transaction detects truncation/forgery of the log tail
- OD-E4: page→source byte spans derived deterministically from DURABLE state only
  (`spans_from_durable`): aggregate format (`document_fingerprint == capture_s1`) → 8-byte framing
  offsets; fallback → single full-coverage span
- OD-E5: evidence recording never alters Reconstruction outcomes; every failure surfaces via
  `service.issue_reports()` / `report.issues` — never silently
- OD-E6: single reconstruction-layer clock reused (`model.utc_now_iso`)

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/extraction — WP-3.1 Engine-Agnostic Extraction Pipeline (MVP implementation)

## WP-3.1 — Extraction (SPEC-WP31-EXT v1.0-MVP)

| Component | File | Implements |
|---|---|---|
| Domain model + outcomes | `model.py` | Contract §2/§4 (Provenance D-01 vocabulary, SourceSpan, ExtractedField, ExtractionRecord, ExtractionInput, exhaustive explicit outcomes) |
| Engine abstraction + reference engine | `engine.py` | Contract §3 (ExtractionEngine ABC — replaceable seam per D-09; ReferenceDelimitedEngine: deterministic `key=value` grammar over strict UTF-8) |
| Durable extraction store | `store.py` | Contract §5 (separate SQLite file, atomic record+fields commit — zero residue, INV-X-1:1 UNIQUE triple, record_fingerprint, no UPDATE/DELETE path) |
| Orchestration | `service.py` | Contract §2/§3/§6 (verified document read → ExtractionInput → engine → contract validation C2–C5 fail-closed → commit; VOR-pattern read_extraction; document-scoped enumeration) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_extraction.py [base]` — WP-3.1 Document/Page → Extraction-ready input → Extracted structured data (spans, idempotency, restart, explicit failures)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest capture/tests/ reconstruction/tests/ extraction/tests/ -v
```

## Delegated implementation decisions (WP-3.1, declared per D-09)

- OD-X1: extraction store = separate embedded SQLite file (`synchronous=FULL`; no network dependency)
- OD-X2: record + fields commit in ONE atomic transaction → zero residue by construction; no startup recovery sweep needed (no ACTIVE state exists)
- OD-X3: INV-X-1:1 — at most one record per (document_id, engine_id, engine_schema_version); in-transaction check + UNIQUE index backstop; different engine/schema = separate record (engine agnosticism)
- OD-X4: extraction_id = uuid4 hex
- OD-X5: record_fingerprint = sha256-v1 over canonical_extraction_bytes (reused capture S1 capability); recomputed inside every read (VOR pattern — tampered rows never deliver)
- OD-X6: storage-level CHECK — provenance can only be 'EXTRACTED' in this layer (D-01 vocabulary reserved; DERIVED/UNRESOLVED never engine outputs)
- OD-X7: single extraction-layer clock (`model.utc_now_iso`)
- OD-X8: no UPDATE/DELETE path exists — extraction records are immutable once committed
- Engine contract C1–C5 enforced by the pipeline BEFORE persistence: determinism (tested), EXTRACTED-only provenance, span/page fidelity (index range + offsets + fingerprint), verbatim binding (span bytes strict-decoded == value), explicit failure surfacing
- ReferenceDelimitedEngine is an MVP executability choice, NOT a product engine selection (D-09); production OCR/VLM/adapter engines plug into the same ABC

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/extraction (WP-3.2) — Extraction Evidence Binding (MVP implementation)

## WP-3.2 — Evidence Binding (SPEC-WP32-EVB v1.0-MVP)

| Component | File | Implements |
|---|---|---|
| Binding model + outcomes | `binding_model.py` | Contract §5 (BindingFieldEntry — structural only, ExtractionBindingRecord — full anchor set, BindingLink vocabulary, exhaustive bind/read outcomes, BindingChainReport) |
| Durable binding store | `binding.py` | Contract §2/§6 (separate SQLite file, append-only, atomic binding+entries commit, INV-B-1:1 UNIQUE extraction_id, binding_fingerprint sha256-v1, global hash chain + head anchor, chain verification primitives, no UPDATE/DELETE path) |
| Binder orchestration | `binding.py` | Contract §3/§4 (bind_extraction: whole-chain verification → atomic append; read_binding: VOR over ALL five links with coarse link attribution, content-free failures; document-scoped enumeration; whole-log audit; Issue-Report surface) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_binding.py [base]` — WP-3.2 Extraction → Evidence Binding (provable walk, idempotency, restart, forgery/tamper matrix)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest capture/tests/ reconstruction/tests/ extraction/tests/ -v
```

## Delegated implementation decisions (WP-3.2, declared per D-09)

- OD-B1: binding store = separate embedded SQLite file (`synchronous=FULL`; append-only; no UPDATE/DELETE path)
- OD-B2: binding_hash = sha256("ext-binding-chain:v1" + prev_binding_hash + "\n" + binding_fingerprint); genesis `0`×64; head-anchor table written in the same append transaction detects truncation/tail deletion
- OD-B3: binding_id = uuid4 hex; seq = log position with lastrowid coherence guard
- OD-B4: binding_fingerprint = sha256-v1 over canonical_binding_bytes (record scalars + entries in field_seq order); recomputed inside every verified read
- OD-B5: INV-B-1:1 — at most one binding per extraction_id; in-transaction check + UNIQUE backstop; replay = explicit BindingAlreadyExists
- OD-B6: single extraction-layer clock reused (`model.utc_now_iso`)
- OD-B7: content-free bindings — entries carry positions/fingerprints/names ONLY (no value_verbatim/value_encoding anywhere); span fidelity is proven by joining the two verified reads (extraction + document)
- read_binding verifies ALL five links inside the read — binding log (head+chain+fingerprint), extraction record (+ anchored fingerprint equality), fresh document verified read (+ linkage), reconstruction evidence anchor (seq/record_hash equality), span fidelity (entry↔field↔page slice decode); failures carry one coarse BindingLink and NEVER deliver entries
- Zero modification of WP-1.1 / WP-2.1 / WP-2.2 / WP-3.1 code: the binder composes their public verified-read interfaces only (additive `__init__` exports)

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/normalization (WP-4.1) — Normalization Rules (MVP implementation)

## WP-4.1 — Normalization (SPEC-WP41-NORM v1.0-MVP — **FROZEN 2026-10-05**)

| Component | File | Implements |
|---|---|---|
| Domain model + statuses + outcomes | `model.py` | Contract §4/§5 (NormalizationStatus NORMALIZED/DEFERRED/REJECTED + reason codes, NormalizedField, NormalizationRecord, exhaustive explicit outcomes) |
| Ruleset seam + reference ruleset | `rules.py` | Contract §3 (NormalizationRuleSet ABC — replaceable seam per D-09; ReferenceNormalizationRulesV1: control gate → NFC → trim → kind rule; kinds text/decimal/date via declared kind_profile with text fallback; canonical decimal STRINGS — never float; precision preserved; ambiguity → DEFER, never guessed) |
| Durable normalization store | `store.py` | Contract §7 (separate SQLite file, atomic record+fields commit — zero residue, INV-N-1:1 UNIQUE triple, record_fingerprint, storage CHECK gates OD-N6, no UPDATE/DELETE path) |
| Orchestration | `service.py` | Contract §2/§6/§7/§8 (verified extraction read is the ONLY input path → ruleset → TOTAL positional mapping → atomic commit; VOR-pattern read_normalization; extraction-scoped enumeration; issue surfacing) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_normalization.py [base]` — WP-4.1 Extraction → Normalization → verified reload (provenance walk to Capture S1, idempotency, DEFERRED/REJECTED, restart, tamper)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest capture/tests/ reconstruction/tests/ extraction/tests/ normalization/tests/ -v
```

## Delegated implementation decisions (WP-4.1, declared per D-09)

- OD-N1: normalization store = separate embedded SQLite file (`synchronous=FULL`; no network dependency)
- OD-N2: record + fields commit in ONE atomic transaction → zero residue by construction; no startup recovery sweep needed (no ACTIVE state exists)
- OD-N3: INV-N-1:1 — at most one record per (extraction_id, ruleset_id, ruleset_version); in-transaction check + UNIQUE index backstop; different ruleset/version = separate record (rule extensibility without rewriting history)
- OD-N4: normalization_id = uuid4 hex; single normalization-layer clock (`model.utc_now_iso`); identity scalars are separated from content determinism (SPEC §6)
- OD-N5: record_fingerprint = sha256-v1 over canonical_normalization_bytes (reused capture S1 capability); recomputed inside every read (VOR pattern — tampered rows never deliver)
- OD-N6: storage-level CHECK gates — source_provenance = 'EXTRACTED' only (D-01 relayed verbatim; DERIVED/UNRESOLVED never produced here); status vocabulary; normalized_value NULL iff status ≠ NORMALIZED; reason_code NULL iff status = NORMALIZED; defensive Python-side commit refusal
- OD-N7: no UPDATE/DELETE path exists — normalization records are immutable once committed
- OD-N8: ReferenceNormalizationRulesV1 (`kandoo-norm-v1` version `1`) is an MVP executability choice, NOT a business-rule decision; new rulesets plug into the same seam with a new version id
- Numeric grammar (declared): integers canonicalized (leading zeros stripped, sign iff non-zero); single-separator decimals with thousands-ambiguity guard (e.g. `1.234`, `12,345` → DEFER); complete European/English thousands groupings; fraction digits preserved verbatim (no rounding, no float); currency symbols and malformed shapes → DEFER, never guessed
- Provenance/traceability: every NormalizedField points at its source via (extraction_id, field_seq); span/byte data is NOT duplicated (WP-3.2 binding anchors it — join verified reads, never copy)
- Pre-freeze boundary clarification (2026-10-05, SPEC §4.1/§4.2): `DEFERRED` is a NORMALIZATION-LAYER outcome only — the declared grammar cannot safely transform the value, so no interpretation happens and nothing is invented; `DEFERRED ≠ UNRESOLVED` and WP-4.1 never creates, assigns, infers, or resolves `UNRESOLVED` (status vocabulary is exactly three values; provenance is storage-gated to `EXTRACTED`). WP-4.1 performs NO DERIVED computation: no `unit_amount` calculation from other fields, no semantic arithmetic between fields, no inference of missing business values (DERIVED stays in WP-4.2). Test-proven in `test_norm_freeze_boundary.py` (8 tests)

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/derivation (WP-4.2) — DERIVED Provenance & Exact Derivation Mechanism (MVP implementation)

## WP-4.2 — Derivation (SPEC-WP42-DER v1.0-MVP — implemented 2026-10-06)

| Component | File | Implements |
|---|---|---|
| Domain model + outcomes | `model.py` | Contract §5/§6/§8 (output_provenance DERIVED-only, refusal reason codes input-missing/input-ambiguous/output-present/non-exact-result, DerivationRecord + DerivationInputRef pointer rows, exhaustive derive/read/trace outcomes) |
| Exact arithmetic engine | `arithmetic.py` | Contract §4 (canonical decimal string → exact rational via fractions.Fraction — never float; ADD/SUB/MUL exact; DIV only when the quotient terminates, else NonExactResult — never rounded, D-08; minimal exact decimal expansion output) |
| Formula registry (data, not code) | `formulas.py` | Contract §3 (DerivationFormula — declarative declaration; fail-closed construction validation: whitelisted ops, arity, declared-slot leaves, no shadowing output, no literals/callables; canonical_formula_bytes + formula_fingerprint sha256-v1; DerivationFormulaRegistry keyed (formula_id, version); ReferenceDerivationFormulasV1 ships exactly one formula: total.gross = ADD(total.net, tax.amount)) |
| Durable derivation store | `store.py` | Contract §9 (separate SQLite file, synchronous=FULL, atomic record+input-refs commit — zero residue, INV-D-1:1 UNIQUE (normalization_id, formula_id, formula_version), record_fingerprint sha256-v1, CHECK output_provenance='DERIVED' only, no UPDATE/DELETE path) |
| Orchestration | `service.py` | Contract §2/§5/§8/§10 (verified normalization read is the ONLY value path + healthy WP-3.2 binding fail-closed → singleton slot resolution over NORMALIZED fields only → output-present gate → exact arithmetic → atomic commit; VOR read_derivation; trace_derivation re-verifies every link in one call; issue surfacing) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_derivation.py [base]` — WP-4.2 Normalize → DERIVED (exact, declared formula) → whole-chain trace to Capture S1 → refusals → restart → tamper → vocabulary sweep

## Run the tests

```bash
cd kandoo/src
python3 -m pytest capture/tests/ reconstruction/tests/ extraction/tests/ normalization/tests/ derivation/tests/ validation/tests/ -v
```

## Delegated implementation decisions (WP-4.2, declared per D-09)

- OD-D1: derivation store = separate embedded SQLite file (`synchronous=FULL`; no network dependency)
- OD-D2: record + input pointer rows commit in ONE atomic transaction → zero residue by construction
- OD-D3: INV-D-1:1 — at most one derivation per (normalization_id, formula_id, formula_version); in-transaction check + UNIQUE index backstop; a different formula VERSION is a DIFFERENT record (version extensibility without rewriting history)
- OD-D4: derivation_id = uuid4 hex; single derivation-layer clock (`model.utc_now_iso`)
- OD-D5: record_fingerprint = sha256-v1 over canonical_derivation_bytes (record scalars + input refs in input_slot order); recomputed inside every read (VOR — tampered rows never deliver)
- OD-D6: storage-level CHECK gates — `output_provenance = 'DERIVED'` is the ONLY storable label (D-01: UNRESOLVED can never be stored here — P5 territory); `input_count >= 1`; defensive Python-side commit refusal for pointer rows leaving the source normalization record
- OD-D7: no UPDATE/DELETE path exists — derivation records are immutable once committed
- OD-D8 (exact arithmetic): stdlib `fractions.Fraction` constructed ONLY from canonical decimal strings (never from float — the parser accepts only the declared grammar); ADD/SUB/MUL always exact; DIV executed only when the reduced denominator is 2^a·5^b (terminating decimal), otherwise explicit `non-exact-result` refusal — rounding is WP-5.1 territory (D-08); output = exact minimal expansion (trailing zeros stripped value-preservingly, sign iff non-zero, no exponent notation)
- OD-D9 (reference registry): `ReferenceDerivationFormulasV1` ships EXACTLY ONE declared formula — `kandoo-der-total-gross-from-net-tax` v1: `total.gross = ADD(total.net, tax.amount)` — an MVP executability choice, NOT a business-rule decision; NO unit_amount formula is shipped (association = P6; rounding = WP-5.1); P6 can later instantiate line-scoped declared formulas through the same seam without rework
- OD-D10 (engine independence): zero engine imports and zero engine-symbol coupling (AST-proven); the seam consumes verified NormalizationReadSuccess only
- Provenance/traceability: input rows are POINTERS (source_normalization_id + field_seq + source_extraction_id) — input VALUES are never copied; `trace_derivation` re-verifies every link (derivation → normalization → extraction → binding → Document/Page/span → Capture S1) inside one call through frozen verified reads
- Outcome vocabulary (SPEC §5): DERIVED (persisted D-01 label) | NOT_DERIVABLE / mechanism-DEFERRED (ephemeral refusal with reason code — nothing persisted, no value, never UNRESOLVED) — WP-4.1's DEFERRED is a field status, WP-4.2's is a formula-application outcome; both are explicit non-productions and neither is UNRESOLVED

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/validation (WP-5.1) — R1/R2 Validation Engine (MVP implementation)

## WP-5.1 — Validation (SPEC-WP51-VAL v1.0-MVP — implemented 2026-10-07)

| Component | File | Implements |
|---|---|---|
| Domain model + outcomes | `model.py` | Contract §3/§5/§6/§8 (rule kinds R1/R2; outcomes VALID/INVALID/DEFERRED only; reason codes; ValidationRecord + ValidationInputRef pointer rows; exhaustive validate/read/trace outcomes; NO invoice states — WP-5.2 territory) |
| Exact rounding primitives | `rounding.py` | Contract §4 (round_exact over exact rationals — never float; declared modes HALF_UP/HALF_EVEN/FLOOR/CEILING/DOWN; to_fixed_decimal_string emits EXACTLY `precision` digits; exact_value_string: terminating → minimal expansion, non-terminating → canonical "p/q" for the audit input) |
| Rule registry (data, not code) | `rules.py` | Contract §3 (ValidationRule declarative; fail-closed registration: kind/type pairing, R1 can never carry tolerance/rounding, declared-slot leaves only, no literals/callables, tolerance canonical ≥ 0 injected, precision/mode whitelisted and injected; canonical_rule_bytes + rule_fingerprint sha256-v1; ValidationRuleRegistry keyed (rule_id, version); ReferenceValidationRulesV1 ships exactly four rules with REQUIRED injected D-08 parameters) |
| Durable validation store | `store.py` | Contract §9 (separate SQLite file, synchronous=FULL, atomic record+input-refs commit — zero residue, INV-V-1:1 UNIQUE (normalization_id, rule_id, rule_version), record_fingerprint sha256-v1 incl. rounding fields, CHECK outcome IN (VALID,INVALID,DEFERRED), CHECK R1 → rounding_applied=0, CHECK rounding-fields all-NULL/all-NOT-NULL, pointer-shape consistency per origin, no UPDATE/DELETE path) |
| Orchestration | `service.py` | Contract §2/§4/§5/§8/§10 (verified normalization read is the ONLY NORMALIZED path + WP-4.2 service reads the ONLY DERIVED path + healthy WP-3.2 binding fail-closed → declared-slot resolution (singleton; missing/ambiguous → durable DEFERRED) → exact evaluation per rule type (non-exact intermediate: DEFERRED in exact contexts, explicitly rounded ONLY in rounded-equality) → atomic commit; VOR read_validation; trace_validation re-verifies every link incl. the WP-4.2 whole-chain sub-walk for DERIVED inputs; issue surfacing) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_validation.py [base]` — WP-5.1 frozen path → WP-4.2 derive → R1 presence + R1 exact-consistency → R2 tolerated + R2 rounded → whole-chain trace (incl. WP-4.2 sub-chain) → DEFERRED/INVALID probes → restart → tamper → vocabulary sweep

## Run the tests

```bash
cd kandoo/src
python3 -m pytest validation/tests/ -v          # WP-5.1 suite (172)
python3 -m pytest capture/tests/ reconstruction/tests/ extraction/tests/ normalization/tests/ derivation/tests/ validation/tests/ -v   # full regression (565)
```

## Delegated implementation decisions (WP-5.1, declared per D-09)

- OD-V1: validation store = separate embedded SQLite file (`synchronous=FULL`; same governance as P1–P4.2 stores)
- OD-V2: record + input pointer rows commit in ONE atomic transaction → zero residue by construction
- OD-V3: INV-V-1:1 — at most one validation per (normalization_id, rule_id, rule_version); in-transaction check + UNIQUE index backstop; a different rule VERSION is a DIFFERENT record; re-evaluation after pipeline state changed = new rule_version (history immutable)
- OD-V4: validation_id = uuid4 hex; single validation-layer clock (`model.utc_now_iso`)
- OD-V5: record_fingerprint = sha256-v1 over canonical_validation_bytes (record scalars incl. rounding fields + input refs in input_slot order); recomputed inside every read (VOR — tampered rows never deliver content)
- OD-V6: storage-level CHECK gates — outcome IN ('VALID','INVALID','DEFERRED') ONLY (D-01: UNRESOLVED can never be stored here — P5 domain layer); rule_kind IN ('R1','R2'); R1 → rounding_applied = 0 (R1 can never round); rounding fields all-NULL iff rounding_applied = 0, all-NOT-NULL iff = 1; pointer rows origin-consistent (NORMALIZED → source_field_seq NOT NULL, DERIVED → source_derivation_id NOT NULL)
- OD-V7: no UPDATE/DELETE path exists — validation records are immutable once committed
- OD-V8 (exact-arithmetic reuse): `derivation.arithmetic` (parse/evaluate/exact formatter) is reused verbatim as the lower-layer capability of the same pipeline — ONE canonical decimal grammar, ONE parser, zero divergence; DIV termination policy is a CALLER decision (`allow_non_terminating`): exact contexts (R1, tolerated-equality) refuse non-terminating quotients (DEFERRED `non-exact-intermediate` — never implicitly rounded), the declared rounded-equality type accepts them (explicit rounding is its purpose); rounding itself is implemented LOCALLY over exact rationals (pure integer arithmetic, five declared modes)
- OD-V9 (reference registry): `ReferenceValidationRulesV1(tolerance, precision, mode)` ships EXACTLY FOUR declared rules — kandoo-val-total-net-present v1 (R1 presence) | kandoo-val-total-gross-consistency v1 (R1: total.gross == ADD(total.net, tax.amount)) | kandoo-val-total-gross-tolerance v1 (R2 tolerated) | kandoo-val-total-gross-rounded v1 (R2 rounded) — an MVP executability choice, NOT a business-rule decision; ALL R2 parameters are REQUIRED constructor arguments (D-08: calibration parameters are injected per deployment, nothing hardcoded) and are part of the rule fingerprint; NO unit_amount rule is shipped
- OD-V10 (engine independence + no Canonicalization): zero engine imports and zero engine-symbol coupling (AST-proven); rule declarations reference engine-vocabulary field names verbatim — no canonical field mapping; association/ambiguity is never resolved here (durable DEFERRED, detail names the Canonicalization Gate); scope = ONE normalization record + the derivation records hanging off it (no cross-document/cross-record)
- OD-V11 (DERIVED-input resolution): via the WP-4.2 service verified reads only (`derivations_for_normalization` + `read_derivation`); a tampered referenced derivation → ValidationSourceIntegrityFailure; multiple derivations of one output field → DEFERRED (ambiguous-input) — never a silent pick
- Rounding audit (D-08, normative): every applied rounding persists rule_id, rule_version, precision, mode, input (exact value; "p/q" canonical when non-terminating), output (fixed `precision`-digit form) INSIDE the ValidationRecord — reproducible by recomputation; the rounding output is an AUDIT artifact of the comparison, NEVER a pipeline value (no output-value column exists in the schema; it never enters normalization/derivation stores)
- Outcome vocabulary (SPEC §5): VALID | INVALID | DEFERRED — durable, auditable rule outcomes; DEFERRED is a decision OF non-decision (insufficient-input | ambiguous-input | non-exact-intermediate), durably recorded with resolved input pointers; DEFERRED ≠ UNRESOLVED; UNRESOLVED is owned by the P5 domain layer (D-01) and is never created/assigned/inferred/resolved here; NO invoice states (REVIEW/REJECT/success) are defined here — the Validation State Machine is WP-5.2 (AS-03/AD-04); the INVALID/DEFERRED → REVIEW mapping is recorded downstream guidance only (D-08), not implemented

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

# kandoo/src/validation_domain (WP-5.2) — Validation State Machine + REVIEW Queue (MVP implementation)

## WP-5.2 — Validation Domain (SPEC-WP52-VSM v1.0-MVP — implemented 2026-10-07)

| Component | Module | Contract reference |
|---|---|---|
| Frozen vocabulary + records + outcomes | `model.py` | Contract §3/§5/§6/§8 (DOMAIN_STATE VALID/INVALID/DEFERRED/UNRESOLVED verbatim; DISPOSITION CLEAR/REVIEW/REJECT per AD-04; DomainStateRecord, StateValidationRef, FieldProjectionRow, ReviewQueueItem, ReviewQueueEvent; exhaustive outcome types) |
| Deterministic state machine | `machine.py` | Contract §3/§4/§7 (transition function T1..T5 declared priority; D-01 field-level projection RESOLVED/UNRESOLVED; ruleset fingerprint OD-S12; pure function — same inputs → same content) |
| Durable store | `store.py` | Contract §9 (separate SQLite, synchronous=FULL, atomic commit OD-S2, INV-S-1:1 + INV-R-1:1 with UNIQUE backstops, fingerprint anchors OD-S5, CHECK gates OD-S6 incl. at most one CLOSE per item, hash-chained events OD-S13, no UPDATE/DELETE OD-S7) |
| Orchestration | `service.py` | Contract §2/§5/§8/§10 (project_domain_state: verified P5.1 reads ONLY + completeness gate + declaration fingerprint check + field-level D-01 projection + transition function + atomic commit; read VOR; append_review_event fail-closed with terminal CLOSE; trace_domain_state walks every P5.1 whole-chain sub-walk → normalization → extraction → binding → document → Capture S1) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_validation_domain.py [base]` — frozen pipeline → WP-5.1 evaluation → VALID/CLEAR projection + trace → D-01 UNRESOLVED creation → UNRESOLVED/REVIEW + queue item → replay idempotency → REVIEW lifecycle (annotate/close/post-close refused) → determinism → restart recovery → tamper detection → frozen-layer survival sweep (8 steps)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest validation_domain/tests/ -v   # WP-5.2 suite (125)
python3 -m pytest capture/tests/ reconstruction/tests/ extraction/tests/ normalization/tests/ derivation/tests/ validation/tests/ validation_domain/tests/ -v   # full regression (690)
```

## Delegated implementation decisions (WP-5.2, declared per D-09)

- OD-S1: domain store = separate embedded SQLite file (`synchronous=FULL`; same governance as P1–P5.1 stores)
- OD-S2: state record + validation refs + field projections + REVIEW item (iff REVIEW) commit in ONE atomic transaction → zero residue by construction; events commit in their own single-purpose transactions
- OD-S3: INV-S-1:1 (one projection per normalization_id + ruleset_fingerprint) and INV-R-1:1 (one REVIEW item per domain_state_id) — in-transaction checks + UNIQUE index backstops
- OD-S4: domain_state_id / review_id / event_id = uuid4 hex; single layer clock (`model.utc_now_iso`)
- OD-S5: record_fingerprint over record scalars + validation refs (ord order) + field projections (field_name order); item_fingerprint over item scalars; event_fingerprint over event scalars + previous event fingerprint (per-item hash chain); all recomputed inside every read (VOR — tampered rows never deliver content)
- OD-S6: storage CHECK gates — domain_state IN ('VALID','INVALID','DEFERRED','UNRESOLVED') ONLY; disposition IN ('CLEAR','REVIEW','REJECT'); VALID → CLEAR; UNRESOLVED/DEFERRED → REVIEW; field-projection shape per status (RESOLVED ↔ origin + pointer consistency; UNRESOLVED ↔ d01-no-valid-method + NULL pointers); event_type IN ('ANNOTATE','CLOSE'); partial UNIQUE index — at most ONE CLOSE per review item; defensive Python-side commit refusals (VALID+item, UNRESOLVED without REVIEW, UNRESOLVED rows with any other reason)
- OD-S7: no UPDATE/DELETE path exists anywhere in the layer (AST-proven); queue lifecycle = append-only event history with status DERIVED from history (OPEN / CLOSED) — history is never overwritten
- OD-S8 (transition priority): fixed declared order T1 decisive-INVALID/REJECT > T2 D-08-mismatch-INVALID/REVIEW > T3 field-UNRESOLVED/REVIEW > T4 rule-DEFERRED/REVIEW > T5 VALID/CLEAR — the frozen sources anchor each route but do not order co-occurring outcomes; any fixed order is deterministic and auditable; this one is declared in the contract
- OD-S9 (decisive vs tolerance split): P5.1 reasons {absent, present-not-usable, mismatch} → REJECT (decisive violation, no uncertainty to hold); {mismatch-beyond-tolerance, mismatch-after-rounding} → REVIEW (D-08: عدم تطابق حل‌نشده → REVIEW; SPEC-WP51-VAL §4 "feeds the REVIEW path downstream per D-08")
- OD-S10 (ambiguous ≠ UNRESOLVED): ambiguous slots stay rule-DEFERRED (association belongs to the Canonicalization Gate); the field projects RESOLVED with candidate_count — D-01's UNRESOLVED meaning ("در نبود روش معتبر") is preserved VERBATIM
- OD-S11 (RESOLVED backfill): declared fields that no P5.1 slot resolved are checked against the verified normalization read (lowest field_seq, candidate count recorded, upstream statuses relayed verbatim into UNRESOLVED details) — value-level D-01 projection, never re-deciding association or statuses
- OD-S12 (ruleset fingerprint): sha256-v1 over ruleset identity (ruleset_id, ruleset_version) + ordered (rule_id, rule_version, rule_fingerprint-from-record) — a NEW ruleset_version is a DIFFERENT validation key; declaration drift (registry fingerprint ≠ record fingerprint) is an integrity failure
- OD-S13 (event hash chain): per-item prev_event_fingerprint chaining verified on every read and every append — history tamper-evident as a sequence, not just per row
- OD-S14 (no P6 dependency): nothing implements or previews the Canonicalization Gate; VALID/CLEAR records carry only the explicit statement that no REVIEW/REJECT action exists in this layer; event appends are fail-closed on the parent projection's verified read (a broken projection freezes its queue item)

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

## WP-6.1 — Canonicalization Gate (SPEC-WP61-CANGATE v1.0-MVP — implemented 2026-10-07)

The FIRST real boundary of data entering the Canonical Invoice domain. Consumes
verified P5.2 domain states, re-verifies the whole upstream provenance chain
(through the P5.2 walk — consumed, never bypassed), resolves the External
Document Identity strictly per D-02, applies the D-03 idempotency/duplicate
table, and only when EVERY frozen condition holds creates the durable,
immutable Canonical Invoice admission record. Validation ≠ Canonicalization:
VALID/CLEAR is necessary but NOT sufficient.

| Component | Module | Contract reference |
|---|---|---|
| Vocabulary + records + outcomes | `model.py` | Contract §3/§4/§6/§8 (decisions ACCEPTED/REJECTED/REVIEW/ALREADY_CANONICALIZED verbatim from dispatch §14; origins KANDOO_SALE/HOLOO_CAPTURE/OTHER_POS_CAPTURE verbatim from dispatch §7; identity classes DETERMINISTIC/CAPTURE_SCOPED per D-02; GateDecisionRecord, CanonicalInvoiceRecord, CanonicalIdentityPointer, GateReviewItem, GateReviewEvent; exhaustive outcome types) |
| Identity resolution (pure) | `identity.py` | Contract §5 (D-02 mechanics: S2 triad fully extracted + verified → DETERMINISTIC via S2_EXTRACTED_VERIFIED; otherwise CAPTURE_SCOPED; adapter-doc-id path RESERVED OD-G5; candidate counting 0/1/≥2 → incomplete/usable/conflicting per D-03; identity_fingerprint sha256-v1 over declared_origin + canonical values — exact matching ONLY; pointer specs — never raw values) |
| Gate decision engine (pure) | `gate.py` | Contract §4 (declared priority G1..G6 — decisive-INVALID → REJECTED; REVIEW-disposition → REVIEW with verbatim state_reason relay + upstream reference; CAPTURE_SCOPED → REVIEW; capture-S1 replay → ALREADY_CANONICALIZED (D-02); exact S2 duplicate → REJECTED (D-03); else ACCEPTED; defensive content checks) |
| Durable store | `store.py` | Contract §8 (separate SQLite `canonicalization-gate.db`, synchronous=FULL, atomic commit OD-C2 — decision + invoice + pointers + review item; INV-D-1:1 + INV-CI-1:1 + INV-GR-1:1 + UNIQUE(capture_s1) + UNIQUE(identity_fingerprint) backstops OD-C3; sha256-v1 anchors OD-C5; CHECK gates OD-C6 incl. ACCEPTED↔invoice linkage + reason codes + single CLOSE; hash-chained events; no UPDATE/DELETE OD-C7) |
| Orchestration | `service.py` | Contract §2/§3/§4/§7/§8/§9 (canonicalize: V1 verified P5.2 read → V2 whole-chain trace → V3 origin validation → V4 binding validation → G0 replay → G1..G6 → atomic commit; read VOR ×3; append_gate_review_event fail-closed with terminal CLOSE + parent-integrity gate; trace_canonical_invoice: invoice → decision → P5.2 whole-chain walk → identity pointer re-join) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_canonicalization.py [base]` — frozen pipeline → VALID/CLEAR state → gate ACCEPTED + canonical invoice + full-chain trace → D-03 conflicting identity → REVIEW + gate queue item → definite document duplicate → decisive REJECTED → double idempotency (state replay + capture replay) → gate REVIEW lifecycle (annotate/close/post-close refused) → restart recovery → tamper detection → frozen-layer survival sweep + vocabulary sweep (8 steps)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest canonicalization/tests/ -v   # WP-6.1 suite (112)
python3 -m pytest capture/tests/ reconstruction/tests/ extraction/tests/ normalization/tests/ derivation/tests/ validation/tests/ validation_domain/tests/ canonicalization/tests/ -v   # full regression (802)
```

## Delegated implementation decisions (WP-6.1, declared per D-09)

- OD-C1: gate store = separate embedded SQLite file (`synchronous=FULL`; same governance as P1–P5.2 stores)
- OD-C2: decision + canonical invoice (iff ACCEPTED) + identity pointers + gate REVIEW item (iff REVIEW) commit in ONE atomic transaction → zero residue by construction; events commit in their own single-purpose transactions
- OD-C3: INV-D-1:1 (one decision per domain_state_id — replay returns the existing decision verbatim, never re-decides), INV-CI-1:1 (one invoice per ACCEPTED decision), INV-GR-1:1 (one gate review item per REVIEW decision), UNIQUE(capture_s1) — the D-02 capture-level idempotency backstop, UNIQUE(identity_fingerprint) — the D-03 document-duplicate backstop; in-transaction checks + UNIQUE index backstops
- OD-C4: decision_id / canonical_invoice_id / review_id / event_id = uuid4 hex; single layer clock (`model.utc_now_iso`)
- OD-C5: decision_fingerprint over decision scalars; invoice_fingerprint over invoice scalars + pointer rows (role order); item_fingerprint over item scalars; event_fingerprint over event scalars + previous event fingerprint (per-item hash chain); all recomputed inside every read (VOR — tampered rows never deliver content)
- OD-C6: storage CHECK gates — decision IN ('ACCEPTED','REJECTED','REVIEW','ALREADY_CANONICALIZED') ONLY; declared_origin/origin IN ('KANDOO_SALE','HOLOO_CAPTURE','OTHER_POS_CAPTURE') ONLY; identity_class IN ('','DETERMINISTIC','CAPTURE_SCOPED'); ACCEPTED ↔ canonical_invoice_id NOT NULL (exactly one invoice per acceptance; no other decision carries one); REVIEW/REJECTED/ALREADY_CANONICALIZED reason codes exactly the declared sets; admission rows DETERMINISTIC-only; event_type IN ('ANNOTATE','CLOSE'); partial UNIQUE — at most ONE CLOSE per item; defensive Python-side commit refusals mirroring every CHECK
- OD-C7: no UPDATE/DELETE path exists anywhere in the layer (AST-proven); review lifecycle = append-only event history with status DERIVED from history (OPEN / CLOSED)
- OD-G1 (route priority): fixed declared order G1 decisive-REJECT > G2 upstream-REVIEW > G3 identity-CAPTURE_SCOPED > G4 capture-replay > G5 document-duplicate > G6 ACCEPT — the frozen sources anchor each route but do not order co-occurring conditions; any fixed order is deterministic and auditable; this one is declared in the contract
- OD-G2 (usable identity value): a NORMALIZED row with a non-empty normalized_value; empty strings are not usable identity values (never guessed around)
- OD-G3 (S2 verification criterion): exactly one usable NORMALIZED row per bound role in the verified WP-4.1 read + the P5.2 state VALID/CLEAR over that normalization — D-02's "کاملاً استخراج و تأیید شده" made machine-checkable
- OD-G4 (identity fingerprint scope): sha256-v1 over (declared_origin, the three canonical values in role order) — the declared origin is the source-system scope (D-02: identity IN the source system); exact equality of fingerprints is the ONLY duplicate comparison
- OD-G5 (adapter path RESERVED): D-02's first deterministic path (adapter-issued document id) has NO producer in the implemented pipeline (D-04 adapter is post-freeze work); it is declared reserved, never simulated — nothing is invented to fill it
- OD-G6/G7 (KANDOO_SALE refusal): the native flow (AS-02: Product → Sale → Invoice) has no capture pipeline and no P5.2 state; a KANDOO_SALE origin on a P5.2-sourced request is refused `origin-native-flow-not-consumable-here` (fail-closed, auditable; AD-01's two-flow convergence is realized at the Canonicalization phase, the native path entering through its own flow)
- OD-G8 (admission vs assembly): the P6.1 record is the ADMISSION-level Canonical Invoice (canonical_invoice_id is Kandoo-issued per D-02); WP-6.2 owns the full canonical field/line ASSEMBLY and the formal invoice_id issuance workflow; the AS-04 canonical FIELD LIST transfer happens there under the quote discipline when the baseline document is committed (MNT-1)
- OD-G9 (G2 referencing): the gate decision stores upstream_review_id and never duplicates an upstream-held queue item; the gate queue holds canonicalization-stage uncertainty (G3) and the durable audit decisions for all routes
- OD-G10 (empty binding): identity_field_binding=None and {} are the same declaration — no document identity attempted → G3 d03-document-identity-undetermined (D-03 ambiguity → REVIEW)

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

# kandoo/src/canonical_assembly (WP-6.2) — Canonical Assembly + invoice_id Issuance (MVP implementation)

## WP-6.2 — Canonical Assembly + invoice_id Issuance (SPEC-WP62-CANASM v1.0-MVP — implemented 2026-10-08)

Builds the REAL Canonical Invoice from P6.1 ACCEPTED admissions: consumes the
admission ONLY through the P6.1 verified read + whole-chain trace (consumed,
never bypassed), assembles the canonical field inventory (verified values
VERBATIM, D-01 provenance EXTRACTED | DERIVED relayed, pointers re-joinable),
the three D-02 header anchors, DECLARED canonical line items, and issues the
formal invoice_id = the Kandoo-issued canonical_invoice_id consumed VERBATIM
(OD-A1 — no identifier is minted here). REVIEW / REJECTED /
ALREADY_CANONICALIZED never produce an invoice. No canonicalization decision
is ever re-made; no value is invented; no cross-field arithmetic exists.

| Component | Module | Contract reference |
|---|---|---|
| Vocabulary + records + outcomes | `model.py` | Contract §3/§5/§6/§7/§8 (origins frozen enum verbatim; provenance D-01 EXTRACTED/DERIVED verbatim; header roles = D-02 identity roles; line roles LINE_QUANTITY/LINE_UNIT_PRICE/LINE_TOTAL declared per OD-A4; IssuedCanonicalInvoiceRecord/CanonicalHeaderAnchor/CanonicalFieldEntry/CanonicalLineField/CanonicalLineRecord/RejectedLine; exhaustive outcome types) |
| Assembly engine (pure) | `assembly.py` | Contract §3/§4(A4/A6)/§5/§6/§7 (validate_line_binding — declared structure, globally distinct targets, int keys ≥ 0; declaration_bytes — key-sorted canonical serialization; resolve_declared_field — 0/1/≥2 usable rows; assemble_fields — EXTRACTED by field_seq then DERIVED deterministic, values VERBATIM, pointers; assemble_header_anchors — re-join the admission's identity pointers, fail-closed on dangling; identity_anchor_payload — P6.1 OD-G4 serialization QUOTED exactly (A6); assemble_lines — ambiguity raises (never auto-resolution), absence explicit, empty lines rejected, ascending declared key) |
| Durable store | `store.py` | Contract §8 (separate SQLite `canonical-assembly.db`, synchronous=FULL, atomic commit OD-C2 — invoice + anchors + fields + lines + line fields in ONE transaction; INV-AI-1:1 + UNIQUE(identity_fingerprint) backstops OD-C3; sha256-v1 anchors over the whole content set OD-C5; CHECK gates OD-C6 — origin enum, provenance↔pointer, present↔value, counters; no UPDATE/DELETE OD-C7) |
| Orchestration | `service.py` | Contract §2/§4/§5/§6/§7/§8/§9 (assemble: A1 verified P6.1 admission read → A2 consumed whole-chain trace → A3 ACCEPTED-only → A4 declaration validation → A5 verified WP-4.1/WP-4.2 value reads → replay gate OD-A8 → A6 identity-anchor consistency → pure assembly → atomic commit; read VOR over the whole content set; trace_assembled_invoice: issued invoice → admission → P6.1 whole-chain walk → byte-identity re-join of every field/line pointer) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_canonical_assembly.py [base]` — frozen pipeline → gate ACCEPTED → canonical assembly with Kandoo-issued invoice_id (verbatim) + EXTRACTED/DERIVED inventory + 2 declared lines + full-chain trace → gate REVIEW → NO invoice (refused) → idempotent replay + declaration-drift refusal → restart recovery → line tamper detection → frozen-layer survival + vocabulary sweep (6 steps)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest canonical_assembly/tests/ -v   # WP-6.2 suite (100)
python3 -m pytest capture/tests/ reconstruction/tests/ extraction/tests/ normalization/tests/ derivation/tests/ validation/tests/ validation_domain/tests/ canonicalization/tests/ canonical_assembly/tests/ identity_resolution/tests/ duplicate_flows/tests/ product_candidate/tests/ customer_linking/tests/ -v   # full regression (1184 collected — 1183 PASSED + 1 pre-existing date-sensitive flake in the frozen WP-7.1 suite, documented in REG-AR)
```

## Delegated implementation decisions (WP-6.2, declared per D-09)

- OD-A1 (invoice_id semantics): the issued invoice_id IS the P6.1
  canonical_invoice_id — the D-02 Canonical Identity, Kandoo-issued at the Gate
  (OD-G8 explicitly hands issuance formalization to this WP); consumed VERBATIM:
  same value, no different formula, zero uuid/random in this layer (AST-proven)
  — a random UUID can never substitute identity logic here because no identifier
  is generated at all
- OD-A2 (header anchors): the three frozen D-02 identity roles
  (INVOICE_NUMBER | INVOICE_DATE | INVOICE_TOTAL) re-joined from the admission's
  identity pointer rows through the verified WP-4.1 read — the only frozen
  header vocabulary; nothing else is promoted to "header" by guessing
- OD-A3 (canonical field inventory): every usable NORMALIZED row (ascending
  field_seq) + every verified P4.2 DERIVED output of the SAME normalization_id
  (deterministic (name, formula, version, id) order); values VERBATIM; field
  names relayed verbatim (AS-04 quote discipline — no canonical renaming);
  provenance relayed per D-01; UNRESOLVED never created here
- OD-A4 (line structure DECLARED): the assembler never discovers/groups lines —
  the request declares line_key → {LINE_QUANTITY | LINE_UNIT_PRICE |
  LINE_TOTAL → source field name}; role labels transliterate the dispatch §5
  content areas (quantities / unit prices / totals); exactly the three roles per
  line; targets globally distinct; keys int ≥ 0 (bool keys refused — True==1
  collision); None/{} = zero declared lines
- OD-A5 (ambiguity/absence): ≥2 usable rows for a declared field → the WHOLE
  request is refused (`declared-field-ambiguous` — assembling would require
  picking a candidate, i.e. auto-resolution); 0 usable rows → the role is
  recorded ABSENT (`absent-upstream`, value NULL, pointer empty — never
  invented); a line with all three roles absent is REJECTED
  (`empty-line-rejected`, explicit in the outcome, never stored)
- OD-A6 (identity-anchor consistency): P6.1's OD-G4 serialization is QUOTED
  exactly (declared_origin + the three role-order values, sha256-v1) and
  compared against the admission's identity_fingerprint on EVERY assembly —
  verification of consistency with the Gate-resolved identity, never a
  different formula, never a re-decision
- OD-A7 (no arithmetic): assembly never computes across fields — no line sums,
  no total recomputation (R1/R2 semantics remain in P5.1); consistency is
  byte-identity with verified sources + the A6 anchor check
- OD-A8 (replay discipline): same admission + same declaration_fingerprint →
  AssemblyAlreadyAssembled (existing record verbatim, no new rows — D-03);
  same admission + different declaration → AssemblyRequestRefused
  (`assembly-declaration-conflict`) — no second invoice, no silent reshape
- OD-A9 (customer reference): explicitly ABSENT with
  `deferred-wp9.1-d06-no-deterministic-link` — D-06 forbids auto-create and no
  frozen mapping declares a customer field at this WP; nothing is invented
- OD-A10 (DERIVED inclusion): only from verified P4.2 reads of the SAME
  normalization_id (derivations_for_normalization + read_derivation, VOR),
  labeled DERIVED verbatim with derivation_id pointers

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

# kandoo/src/identity_resolution (WP-7.1) — Identity Resolution S1 / S2 / CAPTURE_SCOPED (MVP implementation)

## WP-7.1 — Identity Resolution (SPEC-WP71-IDRES v1.0-MVP — implemented 2026-10-08)

The durable, operational identity foundation for documents entering the
canonical pipeline. Every resolution re-verifies the complete upstream
provenance chain (P5.2 whole-chain walk down to Capture S1 — consumed, never
bypassed), recognizes capture-level replays (S1 idempotency: ONE durable
resolution per capture_s1, ever), resolves the External Document Identity
exactly per D-02 — the frozen triad via the P6.1 primitive
`canonicalization.identity.resolve_identity` consumed VERBATIM (no new
formula, no fork) — or records the explicit CAPTURE_SCOPED outcome with a
stable reason and preserved candidate evidence. Definite duplicates (D-03)
are detected by exact fingerprint equality across DIFFERENT captures and
recorded as append-only observations referencing the original resolution.
Ambiguity (≥2 candidates) is NEVER auto-selected and NEVER converted to
UNRESOLVED (D-01 — P5.2 is its only legal creator). No invoice_id is minted,
held, or referenced here (P6.1/P6.2 own the Canonical Identity); the P6.1
Gate remains the sole canonicalization authority.

| Component | Module | Contract reference |
|---|---|---|
| Vocabulary + records + outcomes | `model.py` | Contract §5/§7/§8 (scopes S2/CAPTURE_SCOPED verbatim; source S2_EXTRACTED_VERIFIED; roles = D-02 triad; origins frozen enum; scope reasons = the three P6.1 D-03 codes verbatim + s2-not-attempted-state-not-valid; IdentityResolutionRecord/IdentityRoleCandidateRow/IdentityDuplicateObservation; exhaustive outcome ladders) |
| Resolution engine (pure) | `resolver.py` | Contract §4/§5 (validate_declared_origin — frozen vocabulary + AS-02 native-flow refusal; binding_declaration_bytes/fingerprint — key-sorted canonical serialization, '' = no declaration; resolve_document_identity — state gate (non-VALID/CLEAR → CAPTURE_SCOPED with ZERO value consumption) then delegation to the frozen P6.1 primitive with reason codes relayed verbatim and candidate evidence preserved) |
| Durable store | `store.py` | Contract §7/§8 (separate SQLite `identity-resolution.db`, synchronous=FULL, atomic commit OD-IR2 — resolution + role rows + observation in ONE transaction; INV-IR-S1:1 UNIQUE(capture_s1) + INV-IR-DUP:1 UNIQUE(resolution_id) backstops OD-IR3; sha256-v1 anchors over record + role rows in frozen role order OD-IR5; CHECK gates OD-IR6 — scope/source/fingerprint/reason consistency, origin/role vocabulary, candidate shapes; no UPDATE/DELETE OD-IR7) |
| Orchestration | `service.py` | Contract §2/§3/§4/§6/§8/§9 (resolve: V1 verified P5.2 read → V2 whole-chain trace → V3 origin validation → V4 binding validation → R0 S1 replay recognition (verified-not-blind, declaration-drift refusal) → R1 S2 attempt (VALID/CLEAR only, verified WP-4.1 read) → R2 exact duplicate detection (deterministic earliest original OD-IR-E) → R3 atomic commit; read_resolution / read_resolution_by_capture with VOR + durable-set structural gates) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_identity_resolution.py [base]` — frozen pipeline → VALID/CLEAR state → S2 resolution recorded + verified read → S1 replay (same state + re-projection → Replay verbatim, one resolution) → D-03 definite duplicate (twin capture → observation, ONE document identity) → CAPTURE_SCOPED (ambiguity preserved / incomplete) → declaration-drift refusal → restart recovery → forged-row tamper detection → frozen-layer survival + vocabulary sweep (8 steps)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest identity_resolution/tests/ -v   # WP-7.1 suite (108)
```

## Delegated implementation decisions (WP-7.1, declared per D-09)

- OD-IR-A (module shape): `src/identity_resolution/` = model/resolver/store/
  service + tests/ + the dedicated smoke runner — the dispatch's
  `<identity-resolution-module>` in the project's existing naming convention
- OD-IR-B (declaration anchor): binding_declaration_fingerprint = sha256-v1
  over the key-sorted role→field serialization (order-of-declaration
  independent, length-prefixed — collision-safe); '' when absent (None and {}
  identical — OD-G10 analog)
- OD-IR-C (non-VALID states): CAPTURE_SCOPED with
  `s2-not-attempted-state-not-valid`, committed WITHOUT any value consumption
  — the resolver never even receives unverified values
- OD-IR-D (reason codes): the three P6.1 D-03 codes reused VERBATIM + exactly
  one new code for the R1b route
- OD-IR-E (duplicate original): earliest (created_at, resolution_id) among
  same-fingerprint resolutions from OTHER captures — deterministic under
  concurrency
- OD-IR-F (replay discipline): declaration match = same declared_origin AND
  same binding_declaration_fingerprint; otherwise
  `replay-declaration-drift` refusal — no second identity, no silent reshape
  (P6.2 OD-A8 discipline)
- OD-IR-G (formula reuse): resolve_identity / validate_binding imported from
  `canonicalization.identity` — the frozen P6.1 primitives are the ONLY
  formula source; no hashlib anywhere in the layer (AST-proven); uuid is
  confined to bookkeeping ids (resolution_id/observation_id) while the
  identity itself is always the deterministic sha256-v1 fingerprint
- OD-IR-H (scope vocabulary): identity_scope ∈ {S2, CAPTURE_SCOPED} exactly;
  S1 is the capture_s1 leg + the R0 behavior; no synonymous scope/status
- OD-IR-I (Canonical Identity boundary): no invoice_id minted/stored/
  referenced; no invoice columns exist in this store; P6.1/P6.2 remain the
  sole owners
- OD-IR-J (candidate evidence): role candidate rows recorded for S2
  resolutions AND CAPTURE_SCOPED incomplete/conflicting outcomes (counts +
  ascending field_seqs + bound names) — ambiguity stays a Gate/review concern
  with full evidence, never auto-resolved, never UNRESOLVED

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

# kandoo/src/duplicate_flows (WP-7.2) — Reprint & Duplicate Flows (MVP implementation)

## WP-7.2 — Reprint & Duplicate Flows (SPEC-WP72-DUPFLOW v1.0-MVP — implemented 2026-10-08)

The operational flow layer over WP-7.1's durable identity resolutions. Every
capture artifact gets exactly ONE durable, auditable flow disposition
(INV-DF-1:1): the first sighting commits IDENTITY_ESTABLISHED (S2
established or CAPTURE_SCOPED — a capture-scoped capture is never a
duplicate and never guessed into one, D-03); re-presenting the SAME capture
is reprint recognition — the existing disposition returns verbatim,
read-only, with ZERO new rows (WP-7.1's R0 replay recognition consumed
VERBATIM; declaration drift refused exactly as WP-7.1 refuses it); a
DIFFERENT capture resolving to the SAME exact S2 fingerprint commits
DUPLICATE_RECOGNIZED pointing at the deterministic original and the WP-7.1
observation — one document identity, operationally addressable through the
durable duplicate register (`duplicates_of`). The layer contains NO identity
logic (WP-7.1's resolve is the only identity engine — consumed, never
bypassed, spy-proven), NO canonicalization decision (P6.1 remains the sole
authority), NO invoice_id handling (P6.2), and NO REVIEW operations. Every
flow read re-verifies its own row (VOR) AND every linked identity fact
through the WP-7.1 verified reads + cross-store structural gates — tampered
or drifting rows are withheld, never served.

| Component | Module | Contract reference |
|---|---|---|
| Vocabulary + record + outcomes | `model.py` | Contract §4/§5/§6 (durable outcomes IDENTITY_ESTABLISHED \| DUPLICATE_RECOGNIZED; REPRINT_RECOGNIZED = call outcome only, never storable; FlowDispositionRecord; exhaustive handle/read ladders) |
| Durable store | `store.py` | Contract §7/§8 (separate SQLite `duplicate-flows.db`, synchronous=FULL, atomic single-row commit, UNIQUE(capture_s1) backstop of INV-DF-1:1, CHECK gates — outcome/reference shape + scope/fingerprint consistency, sha256-v1 anchors via the project S1 service (no hashlib), no UPDATE/DELETE) |
| Orchestration | `service.py` | Contract §2/§3/§4/§6/§9 (handle: F1 fail-closed passthrough → F2/F3 commit mapped from the WP-7.1 outcome → F4 reprint recognition verbatim → F5 deterministic backfill from durable facts (OD-DF-E) → F6 collision maps to the winner; read_disposition / read_disposition_by_id: own VOR + linked re-verification (resolution, original, observation) + cross-store structural gates; duplicates_of / dispositions register queries) |

Entry-point smoke check (no pytest needed):
- `python3 src/run_smoke_duplicate_flows.py [base]` — frozen pipeline → first sighting IDENTITY_ESTABLISHED (S2) + verified read → reprint recognition verbatim (same state + re-projection; zero new rows) → D-03 definite duplicates (twin + third-order → ONE original + the durable register) → CAPTURE_SCOPED never a duplicate → declaration-drift refusal verbatim → restart recovery → forged-row tamper withheld → frozen-layer survival + vocabulary sweep (8 steps)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest duplicate_flows/tests/ -v   # WP-7.2 suite (58)
```

## Delegated implementation decisions (WP-7.2, declared per D-09)

- OD-DF-A (module shape): `src/duplicate_flows/` = model/store/service +
  tests/ + the dedicated smoke runner; NO resolver.py — the layer holds no
  identity logic to isolate (classification is a deterministic mapping of
  WP-7.1 outcome types)
- OD-DF-B (flow vocabulary): durable = IDENTITY_ESTABLISHED |
  DUPLICATE_RECOGNIZED; REPRINT_RECOGNIZED = call outcome only (storage
  CHECK forbids it) — flow facts, not identity states; no synonym of any
  frozen word, no new scope
- OD-DF-C (consumption discipline): WP-7.1's resolve is the ONLY identity
  engine; no import of identity_resolution.resolver or the P6.1 primitive;
  no hashlib (record anchors ride the project S1 service) — AST-proven
- OD-DF-D (linked verification depth): every flow read re-verifies the
  linked resolution AND, for duplicates, the original + observation —
  through the WP-7.1 verified reads (never blind pointers)
- OD-DF-E (disposition determinism): the disposition is a pure function of
  the linked durable facts — first sighting vs first flow-layer sighting
  yield identical content apart from bookkeeping
- OD-DF-F (reprint semantics): reprints are recognized read-only; the
  durable trail is the ONE disposition per capture — no event log, no
  counter, no mutable field
- OD-DF-G (refusal passthrough): WP-7.1 refusal/integrity details propagate
  VERBATIM (incl. replay-declaration-drift); a refusal is never converted
  into a disposition
- OD-DF-H (listing discipline): duplicates_of / dispositions return raw
  records (WP-7.1 list_resolutions analog); verified views go through the
  read paths
- OD-DF-I (Canonical Identity boundary): no invoice_id, no canonical
  reference, no P6.1/P6.2 read exists here
- OD-DF-J (review boundary): no REVIEW queue item is created, read, closed,
  or annotated; CAPTURE_SCOPED/ambiguity routing remains the P6.1/P5.2
  concern

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/product_candidate (WP-8.1) — Product Exact Match (MVP implementation)

## WP-8.1 — Product Exact Match (SPEC-WP81-PMATCH v1.0-MVP — implemented 2026-10-08)

The Product Candidate domain's D-05 `Exact Match` output, plus the minimal
Catalog Identity register it requires. Consumes ONLY the WP-6.2 verified read
(`read_assembled_invoice` — consumed, never bypassed) and the explicit
catalog register; produces ONE durable immutable match fact per declared
product reference (INV-PM-1:1 per (invoice_id, declared_field_name,
identifier_kind) with a UNIQUE backstop).

| Component | File | Implements |
|---|---|---|
| Domain model + outcomes | `model.py` | SPEC §3/§5/§6 (records, vocabularies, explicit outcome types — never silent) |
| Durable store | `store.py` | SPEC §7 (project store pattern: product-candidate.db, synchronous=FULL, atomic single-row commit, immutable, CHECK+UNIQUE gates, VOR bytes) |
| Orchestration | `service.py` | SPEC §4 matching ladder M1–M6 (P6.2 verified read verbatim → declaration validation → exactly-one declared-reference resolution → replay-verbatim → count-based exact lookup → atomic commit) + verified reads §6 (own VOR + linked invoice re-verification + pointer re-join + catalog re-verification + LIVE byte-identity re-proof) |

Entry-point smoke check (no pytest needed):
`python3 src/run_smoke_product_matching.py [base]` (from repo root).

- `python3 src/run_smoke_product_matching.py [base]` — explicit catalog registration → frozen pipeline → issued P6.2 invoice → byte-exact EXACT_MATCHED pointing at the catalog identity (+ LIVE byte-identity re-proof on read) → replay verbatim (zero new rows) + second declared reference appends → unregistered identifier → durable UNRESOLVED that a later registration never rewrites → declared-field refusals with zero residue → restart recovery → forged-row tamper withheld → byte-identity discipline (case-different identifier never matches) → frozen-layer survival + vocabulary sweep (8 steps)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest product_candidate/tests/ -v   # WP-8.1 suite (57)
```

## Delegated implementation decisions (WP-8.1, declared per D-09)

- OD-PM1 (persistence): the project store pattern unchanged — ONE SQLite file
  (product-candidate.db), synchronous=FULL, atomic single-row commit,
  immutable (no UPDATE/DELETE — AST-proven), sha256-v1 record fingerprints via
  the project S1 service (no hashlib), CHECK gates mirrored by defensive
  Python-side refusals, UNIQUE backstops, restart-safe
- OD-PM2 (catalog register scope): the minimal Product-side surface required by
  D-05's `Catalog Identity` output, implemented here because no other registered
  WP provides it; population = explicit declared registration ONLY (the API
  carries no capture/invoice parameter — capture-derived catalog mutation is
  structurally impossible; AS-02 native flow: products precede invoices)
- OD-PM3 (identifier vocabulary): DECLARED opaque (kind, value) strings —
  stored and compared verbatim (byte-exact); NO enumeration, NO barcode
  semantics, NO format grammar, NO checksum, NO normalization in this layer
- OD-PM4 (INV-PM-1:1 + replay): ONE match outcome per declared reference with
  a UNIQUE backstop; replay returns the existing outcome VERBATIM and never
  re-decides; a later registration never rewrites history (a genuinely new
  matching decision over grown catalog state is WP-8.2 territory — declared
  known limitation)
- OD-PM5 (definitiveness): the register enforces it by construction
  (UNIQUE(kind, value)); the match-time lookup is still count-based (0/1/≥2)
  and ≥2 fails closed — the rule survives future register evolution
- OD-PM6 (declared reference): field-name declaration resolved against the P6.2
  canonical field inventory with the exactly-one rule (0 → declared-field-
  not-found; ≥2 → declared-field-ambiguous — never auto-resolution); both D-01
  provenances resolvable; stored pointer = (declared_field_name, canonical_seq,
  provenance) — NEVER the value (pointer discipline, OD-IR-J analog)
- OD-PM7 (no matching intelligence): no candidate generation / approval /
  confidence / fuzzy / semantic / AI / occurrence-based mechanism exists;
  UNRESOLVED is durable and auditable; ambiguity remains ambiguity
- OD-PM8 (boundary): no canonicalization / identity-resolution / customer /
  REVIEW / invoice-mutation vocabulary or logic; no upstream execution; uuid
  bookkeeping only (AST-proven); import allowlist = capture + canonical_assembly
  + stdlib

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/customer_linking (WP-9.1) — Deterministic Customer Linking (MVP implementation)

## WP-9.1 — Deterministic Customer Linking (SPEC-WP91-CUSTLINK v1.0-MVP — implemented 2026-10-08)

The Customer Linkage domain per the frozen D-06 decision: deterministic,
auditable link to an EXISTING customer ONLY — auto-create is structurally
absent. Consumes ONLY the WP-6.2 verified read (`read_assembled_invoice` —
consumed, never bypassed) and the explicit Customer Identity register;
produces ONE durable immutable link fact per declared customer reference
(INV-CL-1:1 per (invoice_id, declared_field_name, identifier_kind) with a
UNIQUE backstop). The ONLY link rule is the project's established
deterministic-matching semantics (D-05/P6.1): a definitive valid identifier
matched byte-exactly against exactly one registered customer identity.

| Component | File | Implements |
|---|---|---|
| Domain model + outcomes | `model.py` | SPEC §3/§5/§6 (records, vocabularies, explicit outcome types — never silent) |
| Durable store | `store.py` | SPEC §7 (project store pattern: customer-linking.db, synchronous=FULL, atomic single-row commit, immutable, CHECK+UNIQUE gates, VOR bytes) |
| Orchestration | `service.py` | SPEC §4 linking ladder L1–L6 (P6.2 verified read verbatim → declaration validation → exactly-one declared-reference resolution → replay-verbatim → count-based exact lookup → atomic commit — NO creation branch) + verified reads §6 (own VOR + linked invoice re-verification + pointer re-join + customer re-verification + LIVE byte-identity re-proof) |

Entry-point smoke check (no pytest needed):
`python3 src/run_smoke_customer_linking.py [base]` (from repo root).

- `python3 src/run_smoke_customer_linking.py [base]` — explicit registration of an EXISTING customer → frozen pipeline → issued P6.2 invoice → deterministic byte-exact LINKED (+ LIVE byte-identity re-proof on read) → replay verbatim (zero new rows) → customer-looking data with NO existing customer → durable UNRESOLVED with the register EMPTY (no auto-create — D-06/DEF3, structural) and the fact never rewritten by a later registration → declared-field refusals with zero residue → restart recovery → forged-row tamper withheld → byte-identity discipline → frozen-layer survival + vocabulary sweep (8 steps)

## Run the tests

```bash
cd kandoo/src
python3 -m pytest customer_linking/tests/ -v   # WP-9.1 suite (59)
```

## Delegated implementation decisions (WP-9.1, declared per D-09)

- OD-CL1 (persistence): the project store pattern unchanged — ONE SQLite file
  (customer-linking.db), synchronous=FULL, atomic single-row commit, immutable
  (no UPDATE/DELETE — AST-proven), sha256-v1 record fingerprints via the
  project S1 service (no hashlib), CHECK gates mirrored by defensive
  Python-side refusals, UNIQUE backstops, restart-safe
- OD-CL2 (no auto-create, structurally): the register's ONLY write path is
  the explicit registration API (no capture/invoice parameter); the link
  ladder's ONLY write is the append-only link row — NO code path connects a
  capture or an invoice to a customer row (AST: zero INSERT in service.py;
  exactly two separated INSERTs in store.py on the two commit paths;
  behavioral: no outcome ever grows the register); merge/dedup/enrichment
  absent (DEF3/D-06 — PO territory)
- OD-CL3 (identifier vocabulary): DECLARED opaque (kind, value) strings —
  stored and compared verbatim (byte-exact); NO enumeration, NO barcode
  semantics, NO grammar, NO checksum, NO normalization in this layer
- OD-CL4 (INV-CL-1:1 + replay): ONE link outcome per declared reference with
  a UNIQUE backstop; replay returns the existing outcome VERBATIM and never
  re-decides; a later registration never rewrites history (declared known
  limitation — a genuinely new linking decision over grown register state
  belongs to a future dispatch)
- OD-CL5 (definitiveness): the register enforces it by construction
  (UNIQUE(kind, value)); the link-time lookup is still count-based (0/1/≥2)
  and ≥2 fails closed — the rule survives future register evolution
- OD-CL6 (declared reference): field-name declaration resolved against the
  P6.2 canonical field inventory with the exactly-one rule (0 →
  declared-field-not-found; ≥2 → declared-field-ambiguous — never
  auto-resolution); both D-01 provenances resolvable; stored pointer =
  (declared_field_name, canonical_seq, provenance) — NEVER the value
  (pointer discipline, OD-IR-J analog)
- OD-CL7 (the ONLY link rule): the exact definitive-identifier rule — the
  project's established deterministic-matching semantics (D-05/P6.1); NO
  fuzzy/semantic/AI/best-match/threshold mechanism; UNRESOLVED is durable
  and auditable; ambiguity remains ambiguity
- OD-CL8 (boundary): no canonicalization / document-identity / product /
  REVIEW / invoice-mutation vocabulary or logic; the frozen canonical
  invoice's OD-A9 assembly-time absence stands untouched (this layer's
  output is the additive link register); no upstream execution; uuid
  bookkeeping only (AST-proven); import allowlist = capture +
  canonical_assembly + stdlib

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/digital_invoice — WP-10.1 Digital Invoice Lifecycle (MVP implementation)

Implementation of SPEC-WP101-DILIFE v1.0-MVP (binding). The layer attaches ONE
durable, append-only, tamper-evident lifecycle register (INV-DI-1:1) to each
issued Canonical Invoice (P6.2) and records its progression through the frozen
vocabulary VERBATIM (AS-03):

    DRAFT → EXTRACTED → VALIDATED → ISSUED → REVOKED | SUPERSEDED

| Component | File | Implements |
|---|---|---|
| Vocabularies + matrix + projection | `model.py` | SPEC §5 (frozen six states verbatim; delegated act vocabulary MARK_EXTRACTED \| MARK_VALIDATED \| ISSUE \| REVOKE \| SUPERSEDE; TRANSITIONS = the five legal rows; pure helpers `is_legal_transition` / `predecessor_of` / `expected_outgoing` / `project_current_state`; records + exhaustive outcomes) |
| Durable store | `store.py` | SPEC §7/§8 (digital_invoices + digital_invoice_events; synchronous=FULL; atomic single-row commits; the §5.2 matrix DB-CHECK-enforced; CAS append — in-txn `seq == len(chain)` AND live current state == from_state; UNIQUE(invoice_id) INV-DI-1:1 backstop; UNIQUE(digital_invoice_id, event_seq); sha256-v1 via the project S1 service; NO UPDATE/DELETE) |
| Orchestration | `service.py` | SPEC §4/§5/§6/§9 (open ladder O1–O4 consuming the P6.2 verified read + whole-chain trace VERBATIM; explicit acts with A1–A5 — advance only from the exact predecessor, replay only at the exact target, honest refusals elsewhere; supersede act-time replacement ladder + byte-match replay discipline; verified reads = own VOR + event-chain integrity + live P6.2 re-verification + anchor cross-checks + one-level replacement re-verification; trace = ONE head link onto the intact P6.2 chain) |

Entry-point smoke check (no pytest needed, 16th smoke):
`python3 src/run_smoke_digital_invoice.py [base]` (8-step cold-start).

## Run the tests

```bash
cd kandoo/src
python3 -m pytest digital_invoice/tests/ -v   # WP-10.1 suite (54)
```

## Delegated implementation decisions (WP-10.1, declared per D-09)

- OD-DI-A (module shape): `src/digital_invoice/` = model/store/service/__init__
  + tests; smoke `run_smoke_digital_invoice.py`; NO separate machine.py — the
  transition matrix is five declarative rows in model.py
- OD-DI-B (entry discipline): the ONLY entry is the P6.2 issued Canonical
  Invoice through the verified read + whole-chain trace (spy-proven); the
  native chain (AS-02: Product → Sale → Invoice → Digital Invoice) is NOT
  simulated or pre-built — no Sale semantics anywhere (AST sweep); DEF1
  stands (external capture never creates a Sale)
- OD-DI-C (act vocabulary): MARK_EXTRACTED | MARK_VALIDATED | ISSUE |
  REVOKE | SUPERSEDE — act names recording transitions, not states
- OD-DI-D (transition matrix): the minimal deterministic reading of the
  frozen ordered vocabulary — linear progression + terminal acts from
  ISSUED only; terminal means terminal; no backward/skip/exit; DB
  CHECK-enforced + Python-mirrored
- OD-DI-E (DRAFT representation): DRAFT is the implicit state of a freshly
  opened Digital Invoice (no genesis event; empty chain ⇔ DRAFT)
- OD-DI-F (reason_note): optional DECLARED opaque string, recorded verbatim,
  never interpreted — audit-trail bookkeeping only
- OD-DI-G (supersede pointer): the replacement is named by its invoice_id,
  stored as a pointer, verified at act time (exists + own verified read +
  ISSUED + ≠ source); cycles structurally impossible (terminal discipline)
- OD-DI-H (supersede replay): replay at SUPERSEDED requires the declared
  replacement to byte-match the recorded one — never reshaped (OD-A8 analog)
- OD-DI-I (linked verification depth): reads re-verify the linked P6.2
  invoice (always) and the supersede replacement (one level deep:
  existence + own verified read). The replacement's CURRENT state is NOT a
  read-time gate — the ISSUED rule is §5.4's ACT-time precondition; a read
  must never depend on WHEN it happens (determinism; correction chains
  a→b→c stay readable)
- OD-DI-J (pointer discipline): NO canonical invoice value is ever stored —
  the copied anchor set (capture_s1, capture_s1_algorithm_id, capture_id,
  document_id, origin) is self-description, cross-checked on every read;
  all content is re-read LIVE through the P6.2 verified read; no
  currency/tax/presentation surface (IRR is quoted frozen Canonical Invoice
  v1 vocabulary, not implemented here — AS-04)
- OD-DI-K (listing discipline): `digital_invoices()` / `lifecycle_events()`
  return raw records; verified views go through the read paths
- OD-DI3 (CAS append): every event commits as an in-transaction
  compare-and-swap — the caller's seq must equal the live chain length and
  the live projected state must still equal the event's from_state; a
  stale-state append can NEVER persist (proven under the 8-thread advance
  race and the REVOKE-vs-SUPERSEDE race)

Python 3.12+, stdlib only (sqlite3 included) — zero external dependencies.

---

# kandoo/src/holoo_spike — WP-11.1 Holoo DB Spike (READ-ONLY, MVP implementation)

Implementation of SPEC-WP111-HDS v1.0-MVP (binding, verbatim). A spike
instrument, not a pipeline stage — D-04: the spike ONLY REPORTS; nothing it
reads ever enters the Kandoo domain.

| Component | File | Implements |
|---|---|---|
| Vocabulary + failures + report + encoder | `model.py` | SPEC §3/§5/§9/§10/§11 (5 report-only roles, 4 typed failures, `HolooSelection` edge-validated, deterministic `HolooSpikeReport.to_json_bytes`, type-tagged `encode_value`) |
| Read-only source layer | `store.py` | SPEC §6/§7/§8 (L1 `mode=ro` URI, L2 `PRAGMA query_only=ON`, L3 token-level read-guard allowlist, whitelisted-PRAGMA introspection, count/project with safe identifier quoting) |
| Orchestration | `service.py` | SPEC §5/§6/§10 (S1-hashed open/close byte proofs, declared-mapping fail-closed validation, honest per-selection refusals, deterministic report — no wall-clock) |

Entry-point smoke check (no pytest needed):
`python3 src/run_smoke_holoo_spike.py /tmp/kandoo-hs-smoke` — 8-step cold-start
(17th smoke): SYNTHETIC fixture → spike run → determinism → no-mutation byte
proofs → engine-level write refusals → guard-level refusals → fail-closed
mapping refusal → report JSON written by the RUNNER (the package never writes).

## Run the tests

```bash
cd kandoo/src
python3 -m pytest holoo_spike/tests/ -v
```

## Delegated implementation decisions (declared per D-09 — SPEC §13)

- OD-HS-A: MVP source = local SQLite file (offline-safe, stdlib-only); live-engine adapters deferred (WP-11.2 / PO)
- OD-HS-B: `mode=ro` URI via `urllib.parse.quote`; `isolation_level=None` (reads only)
- OD-HS-C: conservative runtime guard — SELECT or whitelisted read-PRAGMA only; comments/multi-statement/set-forms refused
- OD-HS-D: source hashing exclusively via capture `S1Service` (`sha256-v1`) — no second hash capability
- OD-HS-E: report carries NO wall-clock time (determinism first; runners log time outside the report)
- OD-HS-F: default per-selection cap 5,000 rows; truncation is loud (`truncated` + COUNT)
- OD-HS-G: role vocabulary = the fixed five report labels; unknown role refused at construction
- OD-HS-H: identifier quoting double-quote + doubling; NUL/>256-char identifiers refused
- OD-HS-I: internal `sqlite_%` objects excluded from the mapping namespace, counted in the report
- OD-HS-J: the package is disk-clean; `to_json_bytes()` is pure; writing is the runner's act
- OD-HS-K: the SYNTHETIC fixture builder lives under `tests/` (contains CREATE/INSERT by necessity) and is NEVER imported by the production package (AST-swept dependency direction)

**Boundary:** read-only ladder L1–L5 (SPEC §6); no Sale (DEF1), no customer
auto-create (D-06/DEF3), no inventory/accounting mutation (AD-03), no domain
entry of extracted values (D-04 — the only sanctioned path toward Canonical is
the full External Flow, AS-01, which is WP-11.2+/PO decision space); WP-11.2
(Adapter/Enrichment) is DEFERRED — field mapping/source authority/sync
semantics/write-back are PO/TM decisions (DEF6 precedent).

---

# kandoo/src/corpus — WP-12.1 Corpus Assembly (P12 Pilot layer, MVP implementation)

Implementation of SPEC-WP121-CORPUS (binding, additive-only).

| Component | File | Implements |
|---|---|---|
| Model + outcomes | `model.py` | SPEC §2/§3 (exact marking/origin/label-kind vocabulary), §8 (8 typed failures), durable shapes + outcomes |
| Deterministic generators | `generator.py` | SPEC §4/§5 (three declared templates, S1-digest entropy — no random/hashlib/time, LP-8byte canonical serialization, integer-cents arithmetic, EURO variant with canonical labels) |
| Durable store | `store.py` | SPEC §6 (content-addressed versions, whole-version atomic txn, append-only, VOR via canonical rebuild, CHECK/UNIQUE gates, clock-free — OD-CA-J) |
| Assembly service | `service.py` | SPEC §7 (A1..A5 ladder, VOR-complete replay path, typed refusals, zero residue) |

**Layer status: PILOT MATERIAL — not a production dependency.** No production
package may import `corpus` (AST-swept); the only sanctioned consumer is the
WP-12.2 calibration layer. The corpus ratifies nothing and feeds no domain
store (D-07/D-08 placeholders untouched).

## Run the tests

```bash
cd kandoo/src
python3 -m pytest corpus/tests/ -v
python3 run_smoke_corpus.py /tmp/kandoo-smoke-corpus
```

## Delegated implementation decisions (declared per D-09 — SPEC §10)

- OD-CA-B entropy: iterated S1 digests over counter-tagged strings (no `random`)
- OD-CA-C amounts: integer cents; declared rate 8/100; HALF_UP; canonical strings
- OD-CA-D identity: content-addressed (the manifest fingerprint IS the version id)
- OD-CA-F bound: entry_count ≤ 10000 (declared assembly-weight guard)
- OD-CA-G template date: fixed 2026-06-15 (away from the documented flake window)
- OD-CA-J the whole package is clock-free (no clock column, no time import)

---

# kandoo/src/calibration — WP-12.2 Calibration Runs (P12 Pilot layer, MVP implementation)

Implementation of SPEC-WP122-CAL (binding, additive-only).

| Component | File | Implements |
|---|---|---|
| Model + report | `model.py` | SPEC §3/§5/§6/§7 (RunConfig echo, observation shapes, deterministic canonical-JSON report — counts only, no wall-clock/uuid/paths) |
| Workspace stack | `stack.py` | SPEC §2.4/OD-CR-B (the FROZEN pipeline services composed VERBATIM — capture→…→gate — inside the workspace; zero behavior of its own) |
| Run service | `runner.py` | SPEC §4/§6/§8 (pre-flight refusals, one run per workspace, M1..M9 measured path, field classification, the D-08 candidate sweep, aggregation counts) |

**Layer status: MEASUREMENT INSTRUMENT — report only.** The report is
decision input for WP-12.3 (PO/G4); no threshold is ratified, evaluated as
pass/fail, or changed. The run touches nothing outside its workspace; the
corpus store is read-only in effect (byte-stability proven).

## Run the tests

```bash
cd kandoo/src
python3 -m pytest calibration/tests/ -v
python3 run_smoke_calibration.py /tmp/kandoo-smoke-cal
```

## Delegated implementation decisions (declared per D-09 — SPEC §10)

- OD-CR-B stack wiring replicates the frozen compositions verbatim (no test-helper imports)
- OD-CR-C source_label literal `calibration`; OD-CR-D sub-workspace per candidate (`candidate-<index>`)
- OD-CR-E one run per workspace (run-manifest.db + typed refusal)
- OD-CR-F report JSON: sorted keys, stable separators, no volatile scalars

---

# kandoo/src/capture — WP-1.2 S1 Fingerprint & Integrity (HARDENING layer)

WP-1.2 (registered decompose: SPEC-WP12-S1H v1.0-MVP) is a PROOF + RECORD
layer over the frozen WP-1.1 capture foundation — **zero production-code
change** (OD-SH-F: any observed gap becomes an Architecture Issue, never an
in-mission patch).

| Deliverable | File | Content |
|---|---|---|
| Hardening contract | `specs/WP-1.2-s1-hardening-contract.md` | SPEC-WP12-S1H §1..§11 (declared edge matrix E1..E11, required properties, agility/limitations obligations, OD-SH-A..F) |
| Edge-matrix suite | `capture/tests/test_s1_hardening.py` | 36 tests: E1 empty … E11 framing + algorithm agility + AST hygiene probe (additive file; co-located per Task Register pattern) |
| Hardening report | `specs/WP-1.2-hardening-report.md` | HARD-RPT-WP12: per-cell matrix results, agility report, S1 limitations (7 items), the recorded ingest-entry observation |
| 20th smoke | `run_smoke_s1_hardening.py` | 8-step cold-start: determinism → sensitivity/framing → type/hostile → roundtrips → fail-closed → store-defects → agility → binding recap |

**Layer status: TEST/REPORT SURFACE ONLY.** The suite imports the frozen
layer, never the reverse; no downstream package may import the hardening
surface. Observed frozen behavior is recorded (including the fail-fast,
zero-residue behavior for non-byte input at the ingest entry — the typed
refusal lives at the S1 capability boundary per the frozen designs; recorded
in HARD-RPT-WP12 §2.3 for TM/PO).

## Run the tests

```bash
cd kandoo/src
python3 -m pytest capture/tests/test_s1_hardening.py -v
python3 run_smoke_s1_hardening.py /tmp/kandoo-smoke-s1h
```

## Delegated implementation decisions (declared per D-09 — SPEC §10)

- OD-SH-A suite co-located in `capture/tests/` (pure test addition)
- OD-SH-B large class = 4 MiB; OD-SH-C mutations = XOR first/last/mid/high-bit
- OD-SH-D 20th smoke, cold-start, stdlib-only
- OD-SH-E report at `specs/WP-1.2-hardening-report.md`
- OD-SH-F zero production-code change — proof, not patch
