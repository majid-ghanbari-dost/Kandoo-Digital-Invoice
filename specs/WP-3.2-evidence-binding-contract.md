# SPEC-WP32-EVB — Extraction Evidence Binding Contract v1.0-MVP

```text
Register ID:  SPEC-WP32-EVB | Version: 1.0-MVP | Date: 2026-10-01 | Owner: Technical Manager
Produced:     inline (T-3.2.1) per TM dispatch 2026-10-01 — "WP-3.2 را بدون Design/Review جدید اجرا کن"
Authority:    D-01 (provenance) | D-02/D-03 (untouched) | D-09 (delegated details declared) |
              AS-01 (flow position) | WP-2.2 (Evidence = the frozen consumer-side source) |
              WP-3.1 §8 (WP-3.2 consumes extraction_ids_for_document + spans)
```

## 1. Scope

`Verified extraction record → durable, tamper-evident Extraction Evidence Binding →
per-field provable traceability to Document/Page + source span + Capture + Reconstruction
Evidence`. NOTHING else. The binding layer NEVER modifies Capture (WP-1.1), Reconstruction
(WP-2.1), or the Reconstruction Evidence log (WP-2.2 — consumed strictly read-only through
its own verified read). Bindings carry structural facts only (ids, fingerprints, offsets,
names, timestamps) — never values, never interpreted data, nothing from
Normalization/Canonicalization/Validation (P4+).

## 2. What one binding is

For ONE extraction record (`extraction_id`), a binding durably records:
- extraction anchor: `extraction_id` + its `record_fingerprint` (+ algorithm id) as verified
  at binding time;
- document/capture anchor: `document_id`, `capture_id`, `capture_s1` (+ algorithm id) —
  copied verbatim from the verified extraction read, cross-checked against a FRESH verified
  document read;
- reconstruction-evidence anchor: `seq` + `record_hash` of the document's
  DOCUMENT_COMPLETED evidence record (read through `EvidenceStore.read_document_evidence`,
  which verifies the whole chain inside that read) — the cryptographic cross-log link;
- per-field source positions: for EVERY field, in field_seq order, a COMPLETE 0..N-1 tiling:
  `field_name, page_index, byte_start, byte_end, page_fingerprint` (byte offsets INSIDE the
  page; the page→artifact ranges stay owned by the WP-2.2 evidence payload).
- The binding is itself tamper-evident: `binding_fingerprint` (sha256-v1 via the reused
  capture S1 capability) over the canonical record+entries bytes, a global hash chain
  (`prev_binding_hash → binding_hash`, genesis 64×"0"), and a log-head anchor (truncation
  guard) — the WP-2.2 evidence pattern, new layer, zero touch on the frozen log.

## 3. Binding input path (normative — no parallel reading, ever)

`bind_extraction(extraction_id)` — every step fail-closed, explicit outcomes, nothing
persisted unless ALL steps pass:
1. Extraction verified read (`ExtractionService.read_extraction`) → must be
   `ExtractionReadSuccess`.
2. Fresh document verified read (`ReconstructionService.read_document`) → must be
   `DocumentReadSuccess` and agree with the extraction/binding linkage
   (document_id/capture_id/capture_s1/page_count).
3. Reconstruction evidence read (`EvidenceStore.read_document_evidence`) → must be
   `EvidenceReadSuccess` containing the DOCUMENT_COMPLETED record (anchor source).
4. Span-fidelity verification: durable page slice `[byte_start, byte_end)` strict-decoded
   with the field's `value_encoding` equals `value_verbatim`; page fingerprint match;
   complete tiling. (The values come ONLY from the fingerprint-anchored extraction record;
   the pages come ONLY from the verified read — no parallel raw-artifact path.)
5. Atomic append with INV-B-1:1 (at most one binding per extraction_id — in-transaction
   check + UNIQUE backstop); replay → explicit `BindingAlreadyExists` (same binding_id).

## 4. Verified binding read (VOR pattern)

`read_binding(extraction_id)` recomputes EVERYTHING inside the read; content-free on any
failure (entries are never delivered on a FAILED verdict):
1. binding log: head anchor agrees; chain verified genesis → this binding; record
   fingerprint recomputed over durable rows (any tamper → failure link `binding`);
2. extraction link: verified extraction read + anchored `record_fingerprint` equality
   (a vanished/broken bound extraction is an integrity failure, link `extraction`);
3. document link: fresh verified document read + linkage equality (link `document`);
4. evidence link: verified evidence read + DOCUMENT_COMPLETED `seq`/`record_hash` equality
   (link `evidence`);
5. span link: entry↔field structural equality + slice-decode equals verbatim (link `span`).
Outcomes (exhaustive): `BindingReadSuccess` | `BindingReadIntegrityFailure` (coarse link
attribution) | `BindingReadRefused` (no binding for this extraction) |
`BindingReadVerificationUnavailable` (no verdict computable; Issue-Report).

## 5. Data model (exact field sets — structurally tested)

- `BindingFieldEntry(field_seq, field_name, page_index, byte_start, byte_end,
  page_fingerprint)` — structural only; no value field exists.
- `ExtractionBindingRecord(binding_id, seq, extraction_id, document_id, capture_id,
  capture_s1, capture_s1_algorithm_id, extraction_record_fingerprint,
  extraction_fingerprint_algorithm_id, recon_evidence_seq, recon_evidence_record_hash,
  field_binding_count, created_at, binding_fingerprint, binding_fingerprint_algorithm_id,
  prev_binding_hash, binding_hash)`.
- `BindingRef(extraction_id, binding_id, created_at)`; `BindingLink` vocabulary:
  `binding | extraction | document | evidence | span`.

## 6. Delegated implementation details (declared per D-09)

OD-B1 storage: stdlib sqlite3, one SEPARATE embedded DB file; synchronous=FULL;
isolation_level=None → explicit BEGIN IMMEDIATE; append-only — no UPDATE/DELETE path.
OD-B2 chain: `binding_hash = sha256("ext-binding-chain:v1" + prev_binding_hash + "\n" +
binding_fingerprint)`; genesis 64×"0"; appends serialized by BEGIN IMMEDIATE; head-anchor
table guards truncation (WP-2.2 pattern).
OD-B3 ids: `binding_id = uuid4 hex`; `seq` = log position (AUTOINCREMENT, coherence guard).
OD-B4 integrity anchor: `binding_fingerprint` = sha256-v1 (reused S1Service) over
`"ext-binding:v1"`-domain canonical bytes of the record scalars + all entries in
field_seq order — verified on every read.
OD-B5 INV-B-1:1: at most one binding per `extraction_id`; replay explicit.
OD-B6 clock: reuses the extraction-layer clock (`extraction.model.utc_now_iso`).
OD-B7 content-free bindings: entries carry positions/fingerprints/names ONLY; values stay
in the fingerprint-anchored extraction record; fidelity is proven by joining the two
stores inside verification (no duplication, no second content path).

## 7. AC mapping

| AC | Contract element |
|---|---|
| AC-3.2.1 | §3 whole-chain bind (fail-closed, explicit outcomes) + §6 OD-B5 replay |
| AC-3.2.2 | §2 per-field anchors + §5 model (field→page/span→document→capture→evidence walk) |
| AC-3.2.3 | §4 VOR verified binding read + span fidelity + link attribution |
| AC-3.2.4 | §6 durability/chain/head + frozen-layer regression green + §1 boundary |

## 8. Deferred (explicitly out of this MVP)

Automatic binding hooks inside `ExtractionService.extract` (binding is an explicit,
separately-composable step — WP-3.1 behavior stays bit-identical), normalization/canonical
evidence (P4+), DERIVED-field provenance evidence (WP-4.2), retention values (DEF4).
