# WP-1.2 HARDENING REPORT — S1 Fingerprint & Integrity (Edge Matrix, Agility, Limitations)

```text
Report ID:   HARD-RPT-WP12
Version:     1.0
Date:        2026-10-09
Prepared by: Technical Implementation Agent (Mission «CONTINUE FORWARD BEYOND
             BLOCKED P12 DECISIONS» — the registered decompose + execution of
             REG-WPR WP-1.2)
Binding basis: SPEC-WP12-S1H v1.0-MVP (specs/WP-1.2-s1-hardening-contract.md)
             over REG-WPR WP-1.2 + FROZEN D-02/D-03/D-09 + FROZEN WP-1.1
             designs (Contract v1.1, Store v0.2, S1 v1.0, VOR v1.0)
Status:      EVIDENCE — records observed frozen behavior; ratifies nothing,
             patches nothing, changes no frozen decision.
```

## 1. Executive result

The declared edge-input matrix (SPEC-WP12-S1H §4, classes E1..E11) was
executed against the FROZEN WP-1.1 S1/integrity layer. Every required
property of SPEC §5 (DETERMINISTIC, CONTENT-SENSITIVE, TYPE-EXACT,
EXPLICIT-OUTCOME, ID-BOUND) held on every applicable cell — **no GAP was
found; no frozen file was modified** (OD-SH-F satisfied: proof, not patch).
One entry-point observation (cell E7×ingest, §2.3 below) is recorded
verbatim for TM/PO as a documented limitation of the orchestrator boundary —
it is fail-fast with zero residue and involves no silent acceptance, so it
is NOT a silent-failure gap; it is reported because the typed refusal
vocabulary lives at the capability boundary rather than the orchestrator
entry.

## 2. Matrix results (per class — every cell OBSERVED-PASS)

| Class | Required properties | Observed frozen behavior (recorded) | Cell |
|---|---|---|---|
| E1 EMPTY | DETERMINISTIC, EXPLICIT-OUTCOME | 0-byte digest deterministic ×2 (e3b0c442…b855, sha256-v1); ingest(b"") → IngestCompleted; read → ReadSuccess(content=b"", VALID); re-ingest → IngestDuplicateAtCapture (explicit, no new record) | PASS |
| E2 SINGLE-BYTE | DETERMINISTIC | all 256 one-byte inputs → 256 distinct digests; ×2 identical each | PASS |
| E3 LARGE (4 MiB) | DETERMINISTIC, CONTENT-SENSITIVE, EXPLICIT-OUTCOME | ×2 identical; ingest+read roundtrip VALID (content byte-exact); single-byte mutation at first/last/middle/high-bit → different S1; verify(mutated) → FAILED | PASS |
| E4 MULTILINGUAL | DETERMINISTIC, CONTENT-SENSITIVE | Persian/RTL, CJK, combining marks + ZWJ: ×2 identical; any single-byte change (incl. multibyte sequences) → different S1; roundtrip VALID; one-grapheme append → new record (distinct S1) | PASS |
| E5 BINARY MAGIC | DETERMINISTIC, EXPLICIT-OUTCOME | all 6 declared sniff prefixes + raw binary: sniff hint mechanical per prefix (7 distinct hints incl. UNKNOWN); sniff never affects S1; roundtrip VALID | PASS |
| E6 BOUNDARY MUTATIONS | CONTENT-SENSITIVE, EXPLICIT-OUTCOME | first/last/middle-byte XOR and high-bit XOR (OD-SH-C) on Persian+CJK and 4 MiB bodies → all mutations change S1; verify → FAILED (explicit mismatch); tampered stored content → ReadIntegrityFailure(READ_REASON_MISMATCH), content never carried, integrity_status truthfully flipped to FAILED (no auto-repair) | PASS |
| E7 TYPE EXACTNESS | TYPE-EXACT, EXPLICIT-OUTCOME | bytes/bytearray/memoryview → identical digest; str/int/None/list/dict/float at compute → S1ComputationFailure (typed); at verify → NO_VERDICT with reason (never a guessed verdict, never a crash leak); see §2.3 for the ingest-entry observation | PASS (with §2.3 observation) |
| E8 HOSTILE S1 FIELDS | ID-BOUND, EXPLICIT-OUTCOME | wrong-length ("0"*64, "z"*64, truncated, extended, empty) → FAILED (mismatch); unknown/empty/uppercase-mimicking ids ("sha999-v42", "md5-v1", "", "SHA256-V1") → NO_VERDICT "unknown s1_algorithm_id: …" | PASS |
| E9 INGEST-LEVEL FAIL-CLOSED | EXPLICIT-OUTCOME | injected compute outage → IngestSettledFailure(NOTE_S1_COMPUTATION_FAILED), record settled FAILED_INCOMPLETE (pinned), ZERO COMPLETED residue (S1 never attached); honest re-ingest after capability restore → IngestCompleted; the failed attempt remains retained evidence | PASS |
| E10 STORE-DEFECT PROBES | EXPLICIT-OUTCOME, ID-BOUND | direct-SQL forged COMPLETED row with unknown s1_algorithm_id → ReadVerificationUnavailable (O-4) + Issue-Report surfaced, integrity fields untouched (INV-V8 analog); tampered content row → ReadIntegrityFailure + truthful FAILED write; impossible state (COMPLETED with NULL S1) refused by the storage CHECK (sqlite3.IntegrityError) | PASS |
| E11 FRAMING EDGES | DETERMINISTIC, EXPLICIT-OUTCOME | aggregate([]) == b""; aggregate([b""]) == 8-byte prefix only; framing unambiguous ([b"ab",b"c"] ≠ [b"a",b"bc"] ≠ [b"abc"]); order sensitivity holds; framed aggregates ingest deterministically (×2 → duplicate recognized explicitly) | PASS |

### 2.3 Recorded observation — cell E7×ingest (orchestrator entry)

A caller-side type violation (non-bytes content) at the ingest entry point
fails FAST via the interpreter's own loud `TypeError`/`AttributeError`
raised by the mechanical format sniff (F-11), which precedes the S1 compute
step in the frozen orchestration. The crash happens BEFORE any store call:
**zero residue** (no record row, no content row, nothing settled — proven by
the suite). The TYPED refusal (S1ComputationFailure / NO_VERDICT) lives at
the S1 capability boundary, exactly where the frozen S1 Design §9 declares
it; the frozen designs do not declare an orchestrator-level typed outcome
for caller-side type violations. Recorded for TM/PO: IF a typed ingest-entry
refusal for non-byte types is ever wanted, it is a one-line guard in the
frozen `service.py` — which this additive WP deliberately did NOT touch
(additive-only; any change to frozen P1 files requires an explicit TM/PO
decision). Until then the entry point is fail-fast + zero-residue, which
satisfies fail-closed (nothing silent, nothing partial).

## 3. Algorithm agility report (SPEC §6)

1. Frozen binding: the single declared algorithm id is `S1_ALGORITHM_ID ==
   "sha256-v1"`; every production path uses the default S1Service
   construction; NO second hash exists anywhere in the project (the corpus
   and calibration layers consume this same S1 capability).
2. The declared agility seam is the S1Service constructor surface
   (`algorithm_id`, `supported_ids` — P-S1-6), exercised by the suite/smoke
   with a DECLARED future id ("sha256-v2-future"): values computed under
   different ids are never comparable — cross-id verify → NO_VERDICT with
   reason; same-id verify → VALID. At the storage level, uniqueness (INV-S10)
   and COMPLETED-restricted lookup are keyed on the PAIR
   (s1, s1_algorithm_id): the same digest string under two different declared
   ids completes exactly once per pair (proven).
3. Upgrade path (documentation only — NO implementation shipped): a future
   algorithm = (a) a NEW declared id on the existing seam, (b) an explicit
   capability decision by TM/PO (D-09: implementation detail must not invent
   architecture), (c) migration semantics for records under the old id
   (their (s1, id) pairs remain valid; comparisons stay id-bound). Dual-hash
   / hash- agility as a runtime feature is NOT part of the MVP and requires
   a PO decision before any work.

## 4. S1 limitations (SPEC §7 — stated verbatim-honest)

1. S1 is a CONTENT fingerprint, not a document identity: document-level
   identity is D-02's three-identity model (S1 / S2 / CAPTURE_SCOPED);
   duplicate/reprint semantics live in D-03/P7 — never in S1 alone.
2. Collision resistance is computational (SHA-256), not absolute; S1
   equality is treated as content equality WITHIN the declared id as a
   frozen design assumption (S1 Design v1.0).
3. S1 validates nothing about format or semantics; the sniff hint (F-11) is
   mechanical classification, never interpretation, and never feeds S1.
4. S1 provides integrity, not authenticity or confidentiality: no signature,
   no encryption, no origin proof beyond the captured bytes themselves.
5. The empty byte sequence is a legitimate S1 input (deterministic digest);
   no policy judgment is attached to it at this layer. Size is unbounded by
   S1 itself — bounded only by storage and declared design limits.
6. NO-VERDICT is a first-class outcome (unknown ids, capability failures):
   a verdict is never guessed; callers settle conservatively (frozen
   F1/F2 semantics — S1ComputationFailure / conservative settlement).
7. Aggregation determinism binds at the entry point
   (CaptureService.aggregate, v1.1-C3): S1 consumes the already-aggregated
   byte sequence; framing is length-prefixed and unambiguous.

## 5. Evidence pointers

| Evidence | Location | Result |
|---|---|---|
| Dedicated hardening suite (E1..E11 + agility + hygiene) | kandoo/src/capture/tests/test_s1_hardening.py | 36/36 PASSED ×3 independent runs (2026-10-09) |
| 20th smoke (cold-start, 8 steps) | kandoo/src/run_smoke_s1_hardening.py | SMOKE OK (×2 cold starts) |
| Full regression (all suites) | packaging live evidence + mission report | see mission final report (known WP-7.1 date-sensitive flake separated) |
| Frozen-file integrity | git diff at commit time | existing files byte-identical; additive-only (spec + suite + smoke + report + registers + README) |
| Hardening contract | kandoo/specs/WP-1.2-s1-hardening-contract.md | SPEC-WP12-S1H v1.0-MVP |
