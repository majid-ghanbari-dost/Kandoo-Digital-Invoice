# SPEC-WP31-EXT — Extraction Contract v1.0-MVP

```text
Register ID:  SPEC-WP31-EXT | Version: 1.0-MVP | Date: 2026-10-01 | Owner: Technical Manager
Produced:     inline (T-3.1.1) per TM dispatch 2026-10-01 — "وارد P3 شو؛ بدون فاز طراحی/Review جدید"
Authority:    D-01 (provenance) | D-02/D-03 (untouched) | D-09 (no engine selection) |
              AS-01 (flow position) | WP-2.1 §7 boundary (Extraction receives DocumentReadSuccess)
```

## 1. Scope

`verified Document/Page → Extraction-ready input → Extracted structured data`. NOTHING else.
No normalization, no canonicalization, no validation policy, no S2/identity resolution, no
document-level dedup (D-03 — field sequences are never deduplicated), no OCR/VLM selection
(D-09 — the engine is a replaceable seam, not a product choice), no canonical field mapping
(P4+ territory: every value is stored VERBATIM).

## 2. Input path (normative — WP-2.1 §7)

The ONLY sanctioned input is `ReconstructionService.read_document(document_id)` returning
`DocumentReadSuccess` (same-read VALID verdict). The layer never reads capture artifacts in
parallel and never re-derives pages. Exhaustive source outcomes are mapped 1:1:
`DocumentReadIntegrityFailure → ExtractionSourceIntegrityFailure` |
`DocumentReadRefused → ExtractionSourceRefused` |
`DocumentReadVerificationUnavailable → ExtractionSourceUnavailable` (Issue-Report surfaced).
`ExtractionInput` is the explicit extraction-ready projection: document/capture traceability
+ ordered `PageView`s. Engines receive pages only (content + structure; never the linkage).

## 3. Engine abstraction (replaceable seam)

`ExtractionEngine` (ABC): `engine_id`, `schema_version`, `extract_pages(pages) -> fields`.
Pipeline-enforced engine contract, fail-closed BEFORE persistence:
C1 deterministic | C2 every field `provenance == EXTRACTED` | C3 span names a page the engine
was given (index in range, offsets within `byte_len`, fingerprint equals the claimed page's) |
C4 verbatim binding — strict-decoding the span bytes with `value_encoding` reproduces
`value_verbatim` | C5 explicit failure via `ExtractionEngineError` (unexpected exceptions are
surfaced as `ExtractionEngineFailed` — never swallowed).
`ReferenceDelimitedEngine` (`reference-delimited-v1`, schema "1") is ONE concrete reference
engine (deterministic `key=value` line grammar over strict UTF-8; declared grammar, no key
charset guessing) so the pipeline is executable in MVP; it is swappable without pipeline change.
No production engine (OCR/VLM/adapter) is selected here (D-09).

## 4. Extracted data model (exact field sets — structural test enforced)

- `SourceSpan(page_index, byte_start, byte_end, page_fingerprint)` — position inside ONE durable page.
- `ExtractedField(field_seq, field_name, value_verbatim, value_encoding, provenance, span)`.
- `ExtractionRecord(extraction_id, document_id, capture_id, capture_s1,
  capture_s1_algorithm_id, engine_id, engine_schema_version, page_count, field_count,
  created_at, record_fingerprint, fingerprint_algorithm_id)` — full Document AND Capture traceability.
- `Provenance = EXTRACTED | DERIVED | UNRESOLVED` (D-01 §2.A vocabulary verbatim). This layer
  produces/stores EXTRACTED only (storage-level CHECK); DERIVED is WP-4.2, UNRESOLVED is P4/P5.

## 5. Durability & INV-X-1:1

Store = separate embedded SQLite file (`synchronous=FULL`, no UPDATE/DELETE path). Record +
fields commit in ONE atomic transaction → zero-residue by construction (no ACTIVE state, no
recovery sweep needed). Uniqueness INV-X-1:1: at most one record per
`(document_id, engine_id, engine_schema_version)` — in-transaction check + UNIQUE index
backstop; replay returns `ExtractionAlreadyExists` with the existing id. A different engine or
schema version is a separate record (engine agnosticism; no engine ranking).

## 6. Verified extraction read (VOR pattern)

`read_extraction(extraction_id)` recomputes `record_fingerprint` (sha256-v1 via the reused
capture S1 capability) over the canonical serialization of the durable rows INSIDE the read.
Exhaustive outcomes: `ExtractionReadSuccess` (record + fields + fresh verdict) |
`ExtractionReadIntegrityFailure` (stored content NEVER delivered) | `ExtractionReadRefused`
(unknown id) | `ExtractionReadVerificationUnavailable` (no verdict computable; Issue-Report).

## 7. AC mapping

| AC | Contract element |
|---|---|
| AC-3.1.1 | §2 input path + §4 record traceability + §5 durability/restart |
| AC-3.1.2 | §3 engine abstraction + validation + explicit unknown-engine outcome |
| AC-3.1.3 | §4 spans + C4 verbatim binding (byte-exact slice decode == value) |
| AC-3.1.4 | §5 INV-X-1:1 + separate-record rule |
| AC-3.1.5 | §6 verified read + §2/§3 exhaustive explicit outcomes |
| AC-3.1.6 | §1 boundary + §4 provenance gate + frozen-layer regression green |

## 8. Deferred (explicitly out of this MVP)

Engine selection for production formats (OCR/VLM/adapters — D-09), document-level field
aggregation/joins, DERIVED computation (WP-4.2), normalization rules (WP-4.1), canonical field
mapping (P6 quotes AS-04 verbatim), extraction evidence binding (WP-3.2 consumes
`extraction_ids_for_document` + spans), retention values (DEF4).
