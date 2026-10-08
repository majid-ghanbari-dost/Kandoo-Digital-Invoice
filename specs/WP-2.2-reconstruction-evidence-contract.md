# WP-2.2 — Reconstruction Evidence Contract (MVP, implementation-bound)

```text
Doc ID:     SPEC-WP22-REC | Version: 1.0-MVP | Date: 2026-10-01
Produced:   INLINE within the WP-2.2-IMPL implementation dispatch (TM instruction 2026-10-01:
            «بدون ایجاد فاز طراحی/Review جدید — ساخت واقعی» — no separate design/review phase).
Basis:      D-02 | D-03 | D-09 | AS-01 | SPEC-WP21-RC v1.0-MVP (frozen WP-2.1 behavior) |
            WP-2.2 register row (Phase Index: «WP-2.2 Reconstruction Evidence»)
Scope:      Reconstruction Evidence = durable, tamper-evident, STRUCTURAL proof of the
            Reconstruction stage. NOTHING else. No OCR/VLM/extraction/normalization/S2/dedup.
```

## 1. Boundary (normative)

Evidence records what the Reconstruction layer actually did, as **structural facts only**:
ids, fingerprints, source byte ranges, counts, coarse reason codes, timestamps. An evidence
record contains **no artifact/page content** and **no extracted/interpreted datum** — the
payload builders accept only fixed key sets (§3), structurally enforcing AC-2.2.4. Evidence
is **additive**: it never changes, blocks, or replaces any frozen WP-2.1 behavior (§7).

## 2. Identity & linkage

Every evidence event binds exactly one durable reconstruction document:
`document_id` (local, WP-2.1) + `capture_id` (verbatim traceability link, Contract v1.1 §5).
Fingerprints carried in payloads (`capture_s1`, `page_fingerprint`, `document_fingerprint`)
are verbatim durable values — reuse of the sha256-v1 capability (S1), no new algorithm.
Evidence identity itself = the `(seq)` position in the append-only log + `record_hash`.

## 3. Event vocabulary (fixed) & record shape

| event_type | emitted by | payload keys (exact set) |
|---|---|---|
| `DOCUMENT_COMPLETED` | service, after UAC grant in reconstruct | `capture_s1, page_count, document_fingerprint, fingerprint_algorithm_id, derivation_id, page_spans` |
| `DOCUMENT_SETTLED_FAILED` | service, on D-1 sync settlement / UAC-loser settlement | `settlement_note` |
| `VERIFIED_READ` | service, after every document-read verdict | `verdict` (+`reason` on FAILED, +`state` on REFUSED of an existing document) |
| `RECOVERY_SETTLED` | recovery, after every leftover settlement | `final_state, settlement_note, page_spans` |

`derivation_id` = `"recon-derivation:framing-v1"` (the frozen WP-2.1 mechanical rule).
`page_spans[i]` = `{page_index, byte_start, byte_end}` (+`page_fingerprint` on
DOCUMENT_COMPLETED). Payload text = canonical JSON (sorted keys, compact separators).

Durable record columns: `seq (PK, AUTOINCREMENT), document_id, capture_id, event_type
(CHECK vocabulary), payload, created_at, fingerprint_algorithm_id, record_fingerprint,
prev_record_hash, record_hash (UNIQUE)`. No content column exists.

Scope rule: evidence is **document-scoped**. Outcomes that create nothing (source-side
refusals, unknown-id reads) and duplicate attempts (AlreadyExists) produce **no** event —
no fabricated document evidence; attempt-level audit is deferred (§10).

## 4. Chain integrity (tamper evidence)

- `record_fingerprint` = sha256-v1 over the domain-separated canonical record bytes
  (`recon-evidence:v1` + seq, document_id, capture_id, event_type, payload, created_at,
  prev_record_hash) — computed through the reused capture `S1Service` capability.
- `record_hash` = sha256-v1 over `recon-evidence-chain:v1` + `prev_record_hash` +
  `record_fingerprint`; genesis `prev_record_hash` = 64 × `"0"`.
- Appends are serialized by `BEGIN IMMEDIATE` reading the chain tail inside the same
  transaction → the chain is exact under concurrency.
- **Truncation guard**: a `evidence_head` anchor (last_seq + last_hash) is written inside
  the SAME append transaction as the new tail record; every verified read and
  `verify_chain()` checks the anchor against the actual log tail — a deleted tail row,
  a deleted head, or any truncation fails explicitly (pure hash chains alone cannot see
  tail truncation; the anchor closes that gap).
- **No update/delete path exists** (code or API) — the log is append-only.

## 5. Page → source byte-range binding (AC-2.2.2)

Spans are derived **deterministically from durable state only** (`spans_from_durable`),
never from in-memory computation:
- aggregate-format artifact (`document_fingerprint == capture_s1` — byte-identical by the
  frozen WP-2.1 tiling gate): 8-byte framing offsets, first part at offset 8;
- fallback single-page document: one span `(0, byte_len)` covering the whole artifact.

This makes the evidence **self-consistent with the durable store** and independently
verifiable against the source artifact (slice `artifact[start:end]` == durable page bytes).

## 6. Verified evidence read (VOR pattern — AC-2.2.3)

`read_document_evidence(document_id)` re-verifies, inside the read: every record
fingerprint (recomputed from stored fields) and every chain link from genesis up to the
document's last `seq`. Exhaustive outcomes: `EvidenceReadSuccess` (ordered events) |
`EvidenceReadIntegrityFailure` (coarse reason + failing seq; **records never delivered**) |
`EvidenceReadRefused` (no evidence for this id) | `EvidenceReadVerificationUnavailable`
(storage failure; Issue-Report). `verify_chain()` audits the whole log.

## 7. Non-intrusive integration (AC-2.2.5)

`ReconstructionService(..., evidence=None)` and
`run_reconstruction_recovery(store, s1, evidence=None)` — optional wiring; `None` reproduces
the frozen WP-2.1 behavior exactly. With evidence wired: outcomes are unchanged; an evidence
write failure surfaces in `service.issue_reports()` / `report.issues` and never propagates.
Recovery completeness stays defined by document settlement only (evidence never blocks it).

## 8. Storage (delegated — OD-E1)

Separate embedded SQLite DB file (durable, local, no network), `synchronous=FULL`,
explicit `BEGIN IMMEDIATE`; idempotent schema; vocabulary `CHECK` at SQL level as backstop.

## 9. AC mapping

| AC | Contract element |
|---|---|
| AC-2.2.1 | §2 linkage + §3 record shape + §8 durable separate store (restart survival) |
| AC-2.2.2 | §5 spans rule + §3 DOCUMENT_COMPLETED page_spans (+page fingerprints) |
| AC-2.2.3 | §4 chain + §6 verified evidence read (no silent broken evidence) |
| AC-2.2.4 | §1/§3 fixed payload key sets; no content field anywhere |
| AC-2.2.5 | §7 non-intrusive recorder + issue surfacing; WP-2.1 regression stays green |
| AC-2.2.6 | §3 fixed vocabulary over the real lifecycle + append-only seq order |

## 10. Deferred (explicitly out of this MVP)

Attempt-level audit for outcomes that create nothing (source refusals / AlreadyExists /
D-2 residue with no document), per-page evidence read endpoints, evidence retention/purge
(WP-1.3 / DEF4 owns retention values), cross-layer (capture) evidence, any extraction datum.
