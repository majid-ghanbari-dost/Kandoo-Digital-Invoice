# SPEC-WP12-S1H — WP-1.2 S1 Fingerprint & Integrity (Hardening) Contract

```text
Spec ID:     SPEC-WP12-S1H
Version:     1.0-MVP
Date:        2026-10-09
Status:      ACTIVE — binding for WP-1.2 implementation (the registered
             decompose step: WP-1.1 acceptance CLOSED + G3 PASS 2026-10-01)
Authority:   REG-WPR WP-1.2 «S1 Fingerprint & Integrity (Hardening)»
             («DEFINED — decompose after WP-1.1 acceptance»; deliverables:
             hardening report + edge tests + Acceptance Register update)
             + Mission dispatch «CONTINUE FORWARD BEYOND BLOCKED P12
               DECISIONS» (PO, 2026-10-09) — the earliest forward
             implementation step per register/dependency order
             + Decision Register D-02 (S1 = capture_content_fingerprint,
               FROZEN), D-03 (S1 → Capture Idempotency, FROZEN), D-09
             + FROZEN WP-1.1 designs (binding, verbatim):
               Contract v1.1 | Store Design v0.2 | S1 Design v1.0 | VOR v1.0
Upstream:    CLOSED WP-1.1 deliverables (src/capture: model/s1/store/service/
             recovery — the S1 & integrity layer under hardening)
Downstream:  WP-1.3 Retention & Recovery (Completion) — policy values stay
             DEF4-blocked; this WP changes nothing it consumes.
```

## §1 Purpose

WP-1.2 is the registered HARDENING step of the P1 capture foundation: it
executes and records the DECLARED edge-input matrix over the frozen S1
fingerprint and integrity layer, adds the negative/boundary test surface,
produces the algorithm-agility report and the documented S1 limitations, and
closes the registered ACs with evidence in the Acceptance Register.

Hardening here is PROOF + RECORD, not redesign. The frozen WP-1.1 layer
already declares the required edge properties (S1 Design §3.1 P-S1-1..P-S1-7,
NO-VERDICT semantics, VOR R-V1 every-read verification, Store fail-closed
settlement); this WP's matrix puts every declared edge class in front of the
frozen behavior and records the observed outcome. The registered
deliverables are (1) the hardening report, (2) the edge tests, (3) the
Acceptance Register update — there is NO production-code deliverable. A
matrix cell that violates a required property is a hardening GAP: it is
reported as an Architecture Issue (D-09 path) and is never patched silently
inside this WP.

## §2 Normative boundaries (absolute)

1. NO S1 REDEFINITION. The S1 definition is FROZEN (D-02): SHA-256 over the
   exact artifact bytes, full digest, canonical lowercase hex, id
   "sha256-v1". This WP changes no definition, no algorithm binding, no
   capability surface. There is NO second hash anywhere (project-wide rule —
   corpus/calibration consume S1 exclusively).
2. ADDITIVE-ONLY. Zero modification to any existing file. Deliverables are
   new files only: this spec, the dedicated edge suite, the smoke runner,
   the hardening report, and register/README updates. Existing frozen files
   remain byte-identical (git-diff proof at commit time).
3. NO POLICY INVENTION. The suite observes the frozen layer's explicit
   outcomes (which ingest/read outcomes are produced, what is pinned where).
   It introduces NO dedup semantics (D-03/P7 stay frozen), NO retention
   policy (DEF4/WP-1.3), NO acceptance/rejection policy for any edge class
   beyond what the frozen designs already declare.
4. NO EXTERNAL ENGINE. stdlib `hashlib` only (P-S1-5 environment
   independence; the declared ODBC/OCR-style engine choices are out of scope
   everywhere in P1).
5. FAIL-CLOSED OBSERVATION. Every anomaly in the matrix must land in the
   frozen layer's EXISTING typed outcomes: S1ComputationFailure, Verdict
   VALID/FAILED/NO_VERDICT, the typed ingest outcomes
   (IngestSettledFailure/IngestStorageUnavailable/…), the typed read
   outcomes (ReadIntegrityFailure/ReadRefused/ReadVerificationUnavailable),
   or the store's typed refusals. Any silent path (guessed VALID, silent
   repair, silent skip) is a GAP → Architecture Issue.
6. TEST/REPORT SURFACE ONLY. The matrix, the smoke runner, and the report
   are evidence surface. They import the frozen layer, never the reverse;
   nothing downstream may import the hardening surface.
7. IDENTITY BOUNDARY RESTATED. S1 is the CAPTURE content fingerprint
   (D-02). Document-level identity (S2 / CAPTURE_SCOPED) and duplicate
   semantics belong to P7 and stay outside this WP's scope; the limitations
   report must restate this boundary to prevent future misuse.

## §3 Vocabulary

```text
Edge class      — one declared family of adversarial/boundary inputs (§4)
Matrix cell     — (edge class × required property) executed against the
                  frozen behavior; outcome = OBSERVED-PASS or GAP
Required props: DETERMINISTIC       — same input ×2 → identical (S1, id)
                CONTENT-SENSITIVE   — declared mutations → different S1
                TYPE-EXACT          — byte-sequence types accepted; others
                                      → explicit typed refusal
                EXPLICIT-OUTCOME    — every anomaly lands in a typed outcome;
                                      no silent path, no guessed VALID
                ID-BOUND            — comparisons valid only within the equal
                                      s1_algorithm_id (P-S1-6)
Outcome mark    — every matrix cell is recorded OBSERVED-PASS or GAP in the
                  hardening report (no cell may be omitted)
```

## §4 The declared edge-input matrix

```text
E1  EMPTY          — the 0-byte sequence (a legitimate byte sequence with a
                     deterministic S1; no policy judgment is introduced)
E2  SINGLE-BYTE    — exactly one byte (multiple byte values)
E3  LARGE          — ≥ 4 MiB (OD-SH-B), incl. a full 0..255 byte alphabet
                     repeated; compute + ingest/read roundtrip + mutation
E4  MULTILINGUAL   — UTF-8 multibyte: Persian/RTL text, CJK, combining
                     marks, ZWJ sequences; grapheme-level mutation changes
                     the S1 (CONTENT-SENSITIVE at the byte level)
E5  BINARY MAGIC   — each declared sniff prefix (%PDF-, PNG, JPEG, GIF8,
                     ZIP, GZIP) + high-entropy binary; sniff stays
                     mechanical (F-11) and never affects S1
E6  BOUNDARY       — single-byte mutations at declared positions: first
     MUTATIONS       byte, last byte, middle byte, high-bit flip (OD-SH-C);
                     every mutation → different S1; verify → FAILED
E7  TYPE EXACTNESS — bytes/bytearray/memoryview → identical digest; str /
                     int / None / list / dict → compute raises
                     S1ComputationFailure; verify → NO_VERDICT (never a
                     guessed verdict, never a crash leak)
E8  HOSTILE S1     — wrong-length digest, non-hex digest, correct-length
     FIELDS          wrong-value digest → FAILED (mismatch); unknown /
                     empty s1_algorithm_id → NO_VERDICT with reason
E9  INGEST-LEVEL   — capability failure injected at compute time →
     FAIL-CLOSED     IngestSettledFailure with the frozen note, record
                     settled FAILED_INCOMPLETE (pinned), ZERO COMPLETED
                     residue; honest re-ingest after capability restore
E10 STORE-DEFECT   — direct-SQL forged rows (test surface): COMPLETED row
     PROBES          with unknown s1_algorithm_id → ReadVerificationUnavailable
                     + Issue-Report surfacing; COMPLETED row with tampered
                     content → ReadIntegrityFailure + truthful FAILED write
                     (no auto-repair); CHECK-refused impossible states
                     (e.g. COMPLETED without S1) via direct SQL
E11 FRAMING EDGES  — CaptureService.aggregate: empty parts list → empty
                     bytes; empty part → length-prefix only; framing is
                     unambiguous (no concatenation collisions); large-part
                     framing; determinism ×2
```

## §5 Required properties per class

Every declared class is executed with the required properties of §3 that
apply to it (each cell recorded):

```text
DETERMINISTIC     — required on ALL classes (E1..E11)
CONTENT-SENSITIVE — required on E3, E4, E6 (declared mutations)
TYPE-EXACT        — required on E7 (and E1..E6 accept only byte types)
EXPLICIT-OUTCOME  — required on ALL classes (no silent path anywhere)
ID-BOUND          — required on E8 + the agility surface (§6)
```

The observed outcomes themselves (e.g. empty content ingests to COMPLETED
under the frozen rules — content-addressed, no policy forbids it) are
RECORDED, not judged: this WP adds no acceptance policy for any class.

## §6 Algorithm agility (declared surface — frozen binding)

The agility seam is the ALREADY-DECLARED S1Service constructor surface
(`algorithm_id`, `supported_ids` — P-S1-6). The hardening report documents:

1. The FROZEN binding: every production path uses the default `sha256-v1`;
   the constant S1_ALGORITHM_ID is the single declared id.
2. ID-bound comparison semantics: a value computed under one declared id is
   comparable ONLY within the equal id; cross-id verify → NO_VERDICT
   (version skew surfaced, never guessed); store uniqueness (INV-S10) and
   lookup (COMPLETED-restricted) are keyed on the PAIR (s1, s1_algorithm_id).
3. The upgrade path (documentation only, no implementation): a future
   algorithm = a NEW declared id on this same seam + an explicit capability
   decision (PO/TM) + migration semantics for records under the old id.
   NO second algorithm ships in the MVP; no dual-hash anywhere.

## §7 S1 limitations (documentation obligations)

The hardening report MUST state, verbatim-honest (no marketing):

1. S1 is a CONTENT fingerprint, NOT a document identity: document-level
   identity is D-02's three-identity model (S1 / S2 / CAPTURE_SCOPED);
   duplicate/reprint semantics live in D-03/P7 — never in S1 alone.
2. Collision resistance is computational (SHA-256), not absolute; equality
   of S1 values is treated as content equality WITHIN the declared id as a
   design assumption inherited from the frozen S1 Design.
3. S1 validates NOTHING about format or semantics; sniffing (F-11) is a
   mechanical hint, never an interpretation, and never feeds S1.
4. S1 provides integrity, NOT authenticity or confidentiality: no signature,
   no encryption, no origin proof beyond the captured bytes themselves.
5. The empty byte sequence is a legitimate S1 input (deterministic digest);
   size is unbounded by S1 itself — bounded only by storage/design limits.
6. NO-VERDICT is a first-class outcome: unknown ids / capability failures
   yield NO verdict rather than a guessed one; callers settle conservatively
   (frozen F1/F2 semantics).
7. Aggregation determinism binds at the entry point (CaptureService.aggregate,
   v1.1-C3): S1 consumes the already-aggregated byte sequence.

## §8 Failure semantics (of the hardening itself)

A matrix cell that cannot be executed, or whose observed behavior violates
its required property, is a GAP: recorded as such in the report and raised
as an Architecture Issue (D-09) — it is NEVER patched, silenced, or
reclassified inside this WP. The suite contains no bare asserts, no silent
passes; every negative test names the typed outcome it demands.

## §9 Testing obligations (binding)

Dedicated suite `kandoo/src/capture/tests/test_s1_hardening.py` (OD-SH-A):
every declared class E1..E11, every required property, typed-outcome
assertions throughout (happy/edge/negative), no test-helper imports by
production code, vocabulary sweep (no Sale/Customer/Inventory/DigitalInvoice
semantics), no network/non-stdlib. The suite runs ≥ 2 independent repeats.
Smoke runner `run_smoke_s1_hardening.py` (OD-SH-D; 20th smoke; cold-start,
8 steps, no pytest). Full regression across ALL suites + the additive-only
frozen-integrity proof (existing files byte-identical). Flake separation:
the known pre-existing WP-7.1 date-sensitive flake is reported separately,
never silently.

## §10 Delegated implementation decisions (declared per D-09)

```text
OD-SH-A suite location: kandoo/src/capture/tests/test_s1_hardening.py —
        co-located with the capture suite (Task Register pattern); a PURE
        test addition (no existing file touched).
OD-SH-B large-class size: 4 MiB declared (crosses internal buffering; CI-fast).
OD-SH-C mutation positions: first byte / last byte / middle byte / high-bit
        flip — declared, reproducible.
OD-SH-D smoke runner: kandoo/src/run_smoke_s1_hardening.py — 20th smoke,
        8-step cold-start, stdlib-only, prints SMOKE OK.
OD-SH-E hardening report: kandoo/specs/WP-1.2-hardening-report.md — the
        registered «گزارش hardening» deliverable (matrix results per cell,
        agility report §6, limitations §7, evidence pointers).
OD-SH-F zero production-code change: the suite PROVES the frozen layer; any
        GAP becomes an Architecture Issue — no in-mission patch (§1/§8).
```

## §11 Out of scope (FORBIDDEN — boundary of WP-1.2)

Changing the S1 definition or algorithm binding (D-02 — FROZEN) | any
document-level dedup policy or new idempotency definition (D-03 — FROZEN,
P7) | retention/purge mechanics or policy values (WP-1.3 / DEF4) | choosing
an external engine (OCR/VLM/DB/engine — Frozen D-09) | modifying ANY
existing file (additive-only WP) | downstream/canonical/external-document
semantics in any output (INV-C7) | network/drivers/non-stdlib | threshold
or calibration semantics (P12 territory) | reopening any frozen decision
without a direct contradiction.
