# WP-2.1 — Reconstruction Contract (MVP, implementation-bound)

```text
Doc ID:     SPEC-WP21-RC | Version: 1.0-MVP | Date: 2026-10-01
Produced:   INLINE within the WP-2.1-IMPL implementation dispatch (TM instruction 2026-10-01:
            «Contract حداقلی را در حین کار مشخص کن» — no separate/long contract phase).
Basis:      D-02 | D-03 | D-09 | AS-01 | Contract v1.1 §5 Extensibility Reservation | WP-2.1 register (6 AC)
Scope:      Capture Artifact → Document/Page Structure → Extraction-ready Input. NOTHING else.
```

## 1. Boundary (normative)

Reconstruction consumes **verified captures** and produces a durable, ordered **Document/Page structure**.
It performs **no OCR/VLM, no extraction, no normalization, no S2/identity resolution, no document-level
dedup (P7), no canonical invoice datum**. The layer's model contains no field capable of holding an
extracted or interpreted value (structurally enforced — see §3, §7). Page derivation reads **only the
frozen aggregation length framing** (WP-1.1 `CaptureService.aggregate`, 8-byte big-endian, list order);
page bytes are **verbatim slices** of the capture artifact. Content meaning is never inspected.

## 2. Identity & linkage (traceability — AC-2.1.1 / AC-2.1.6)

- `document_id` — opaque local id (uuid4 hex). **Not** an external/canonical identity (D-02: document
  identity resolution is P7; untouched here).
- Every document binds exactly one source capture: `capture_id` + `capture_s1` + `capture_s1_algorithm_id`
  (verbatim from the verified read). This is the downstream link reserved by Contract v1.1 §5.
- Invariant **INV-R-1:1** — at most one `COMPLETED` document per `capture_id` (AC-2.1.1 «یک Document»),
  enforced UAC-style (atomic decision + partial UNIQUE index backstop + explicit loser outcome).
  This is the 1:1 binding invariant — **not** a new idempotency definition (D-03 untouched).

## 3. Fields

`DocumentRecord` (12): `document_id, capture_id, capture_s1, capture_s1_algorithm_id, created_at,
document_state, integrity_status, integrity_verified_at, page_count, document_fingerprint,
fingerprint_algorithm_id, settlement_note`.
`PageRecord/PageView`: `page_index` (0-based, contiguous), `content` (bytes), `byte_len`,
`page_fingerprint`, `fingerprint_algorithm_id` (`sha256-v1`, computed by the reused capture S1 capability).
No other fields exist. `settlement_note` is mandatory on `FAILED_INCOMPLETE`, empty on `COMPLETED`.

## 4. Lifecycle & settlement (minimal — WP-1.1 pattern)

`ACTIVE | COMPLETED | FAILED_INCOMPLETE` (terminals never change); integrity `UNVERIFIED → VALID|FAILED`;
record-first (`ACTIVE` document before page persist) so interruptions leave recoverable residue;
deterministic settlement (`D-1` analog: definitive persist error → synchronous FAILED settlement);
startup recovery settles every `ACTIVE` leftover to exactly one terminal state (complete-if-internally-valid,
else failed-with-cause), idempotently, ending with **zero ACTIVE**.

## 5. Page derivation & ordering (AC-2.1.2 — declared delegated detail)

Mechanical, content-blind parse of the **frozen aggregation framing**: the artifact is parsed as a chain
of 8-byte BE length-prefixed parts that must consume the byte sequence **exactly**; each part = one page,
in list order. Artifacts that do not parse totally (including the empty artifact) become **one page**
holding the full artifact bytes. Rule is a pure function of bytes → **deterministic and reproducible**;
no semantic heuristic of any kind (D-07 untouched). Canonical reassembly of a document = the same frozen
framing join applied to its ordered page contents.

## 6. Integrity & verified read (AC-2.1.4 — VOR pattern)

Anchors: per-page `page_fingerprint` (SHA-256 of page bytes) and document-level `document_fingerprint`
(SHA-256 over the canonical reassembly of ordered page contents; equals `capture_s1` whenever the source
artifact is in aggregate format). Read = every-read verification, no caching; restricted verdict write
completes **before** the outcome; content is delivered **only** on the same-read `VALID` verdict.
Exhaustive outcomes: `DocumentReadSuccess` (ordered `PageView`s + verdict) | `DocumentReadIntegrityFailure`
(coarse reason, **never** content) | `DocumentReadRefused` (non-COMPLETED / unknown id) |
`DocumentReadVerificationUnavailable` (no verdict computable — Issue-Report surfacing).

## 7. Reconstruction/Extraction boundary (AC-2.1.3)

Extraction (P3) receives `DocumentReadSuccess`: ordered raw page bytes + indices + fingerprints + capture
linkage — nothing else. No parsed/interpreted/extracted datum exists anywhere in this layer's model, store,
or outcomes (structural test enforces exact field sets and store columns).

## 8. Recovery scope

Recovery verifies **document-internal** integrity only (pages vs fingerprints, reassembly vs document
fingerprint, page-count contiguity). It does not re-read the Capture store (the capture layer owns its own
recovery; cross-layer availability stays decoupled). Capture linkage fields always permit downstream
cross-checks.

## 9. AC mapping

| AC | Contract element |
|---|---|
| AC-2.1.1 | §2 linkage + INV-R-1:1, §4 durable lifecycle, restart durability |
| AC-2.1.2 | §5 derivation rule (pure, deterministic, no heuristic) |
| AC-2.1.3 | §1/§7 structural no-extraction boundary + page→capture linkage |
| AC-2.1.4 | §6 verified read (VOR pattern) |
| AC-2.1.5 | §4 record-first + startup recovery settlement |
| AC-2.1.6 | §2/§3 traceability fields (document_id, capture_id/S1, timestamps) |

## 10. Deferred (explicitly out of this MVP)

Per-page read endpoint, format-aware pagination (PDF page objects etc. — needs engine selection, Frozen),
document-level dedup/S2 (P7), retention/purge (WP-1.3/DEF4), any extraction datum.
