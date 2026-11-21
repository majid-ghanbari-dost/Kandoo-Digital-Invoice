# E-06 dry-run — local-fixture proxy report

> **Scope gap:** this checkout contains the four E-03-kit-v2 Markdown value guides and `expected-values.json`, but no rendered v2 PNG/SPL captures. The 16-run image pipeline below therefore uses the four existing repository images `tests/fixtures/real/{29,31,32,33}.png` and their operator-confirmed `labels.json` values. These are legacy real fixtures, **not** the four E-03-kit-v2 pages, and the run does not validate v2's new expected-value set or Hello SPL→PNG rendering.

- Base HEAD: `554c48d2b4cd745160b8c2dd27558bd2f8249cda`
- Generated at (UTC): `2026-10-24T07:24:16+00:00`
- Rotation operation: Pillow `Image.rotate(angle, expand=True)`; positive angles are counter-clockwise.
- Runtime libraries: Pillow 13.0.0; jsonschema 4.26.0 (installed only under the temporary `/tmp` runtime for this run; no repository dependency files changed).
- Focused regression tests: 32 passed and 4 subtests passed across E-05, E-06, and the E-03-kit-v2 value/coverage tests.
- Pipeline per run: E-02/Glyph leave-one-fixture-out image extraction → E-05 layout-template match where geometry and payable box exist → E-06 verdict. E-06 is invoked once for every rotation, including blocked/no-layout cases.
- Accuracy fields counted: quantity, line total, payable only. Unit price, subtotal, product name, and other values are not compared as extraction ground truth.
- The source labels for fixture 31 mark its payable as derived from confirmed line totals; that payable is compared to the derived sum, not an independent visual transcription.
- E-05's bank is the repository's label-derived bank from all four fixtures. Its matching observations are resubstitution evidence, and E-06 reports that limitation. E-02/Glyph uses leave-one-out templates (the held-out fixture is excluded from each OCR fold).
- `require_kit_digit_coverage` is disabled for these substitute fixtures because they are not the E-03-kit-v2 pages. The report does not assert kit-specific coverage or onboarding acceptance.

## Fixture × rotation verdict matrix

E-06 verdict is the decision result; E-02 and E-05 columns show the upstream outcome used for that row. Counts are expected numeric fields for that fixture/rotation.

| Fixture image | Rotation | E-02 extraction | E-05 layout match | E-06 verdict | CORRECT | NOT-EXTRACTED | EXTRACTED-but-wrong |
|---|---:|---|---|---|---:|---:|---:|
| `29.png` | 0° | AUTO_CANDIDATE / OK/4 | MATCH (0.999) | REJECT (`STRUCTURE_VALID, NUMS_CONSISTENT, SELF_MATCH_RESUBSTITUTION, ATTENTION_REQUIRED, ONBOARDING_WARMUP, TEMPLATE_BANK_UNLOCKED, D14_AGREEMENT_REQUIRED, TEMPLATE_MATCH_HIGH, LAYOUT_SIMILARITY_HIGH, NO_MATCH`) | 9 | 0 | 0 |
| `29.png` | 90° | REJECT / BLOCKED | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 9 | 0 |
| `29.png` | 180° | REVIEW / OK/5 | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 9 | 0 |
| `29.png` | 270° | REJECT / BLOCKED | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 9 | 0 |
| `31.png` | 0° | AUTO_CANDIDATE / OK/3 | MATCH (0.996) | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, SELF_MATCH_RESUBSTITUTION, ATTENTION_REQUIRED, ONBOARDING_WARMUP, TEMPLATE_BANK_UNLOCKED, D14_AGREEMENT_REQUIRED, TEMPLATE_MATCH_HIGH, EXTRACTION_CONFIDENCE_HIGH, LAYOUT_SIMILARITY_HIGH`) | 7 | 0 | 0 |
| `31.png` | 90° | REJECT / BLOCKED | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 7 | 0 |
| `31.png` | 180° | REVIEW / OK/4 | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 7 | 0 |
| `31.png` | 270° | REJECT / BLOCKED | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 7 | 0 |
| `32.png` | 0° | AUTO_CANDIDATE / OK/5 | MATCH (0.997) | REJECT (`STRUCTURE_VALID, NUMS_CONSISTENT, SELF_MATCH_RESUBSTITUTION, ATTENTION_REQUIRED, ONBOARDING_WARMUP, TEMPLATE_BANK_UNLOCKED, D14_AGREEMENT_REQUIRED, TEMPLATE_MATCH_HIGH, LAYOUT_SIMILARITY_HIGH, NO_MATCH`) | 11 | 0 | 0 |
| `32.png` | 90° | REJECT / BLOCKED | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 11 | 0 |
| `32.png` | 180° | REVIEW / OK/6 | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 11 | 0 |
| `32.png` | 270° | REJECT / BLOCKED | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 11 | 0 |
| `33.png` | 0° | REVIEW / OK/13 | NO_MATCH (0.792) | REJECT (`STRUCTURE_VALID, CANONICAL_STATE_NOT_READY, NUMS_CONSISTENT, PARTIAL_MATCH, SELF_MATCH_RESUBSTITUTION, ATTENTION_REQUIRED, ONBOARDING_WARMUP, TEMPLATE_BANK_UNLOCKED, D14_AGREEMENT_REQUIRED, NO_MATCH`) | 9 | 18 | 0 |
| `33.png` | 90° | REJECT / BLOCKED | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, CANONICAL_STATE_NOT_READY, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 27 | 0 |
| `33.png` | 180° | REVIEW / OK/14 | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, CANONICAL_STATE_NOT_READY, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 27 | 0 |
| `33.png` | 270° | REJECT / BLOCKED | NOT_EVALUATED | REVIEW (`STRUCTURE_VALID, CANONICAL_STATE_NOT_READY, NUMS_CONSISTENT, NEW_LAYOUT`) | 0 | 27 | 0 |

## Aggregate counts

- CORRECT: **36**
- NOT-EXTRACTED (missing, REVIEW, or BLOCKED): **180**
- EXTRACTED-but-wrong: **0** (hard requirement: zero; **PASS on this proxy fixture set**)
- Total scored numeric expectations: **216**

## Gaps and interpretation

1. The actual v2 Hello print pages have no SPL/PNG artifacts in the repository. The result above is a proxy run on existing fixtures, not a substitute claim that the v2 kit pages were extracted. To close this gap, provide the four actual Hello Windows SPL captures, their KandooPrintProbe PNG conversions, and adjacent `Report.txt` metadata, then rerun against `docs/E-03-kit-v2/expected-values.json`.
2. The four legacy image fixtures are not a one-to-one match for v2 page content; they have 4, 3, 5, and 13 rows, while the authored v2 pages have four item rows each. Therefore, the proxy's expected numeric labels come from `tests/fixtures/real/labels.json`, limited to the allowed three field classes; they are not the v2 expected-values strings.
3. E-05 was trained from label-derived Canonical fixtures for these same four source images. E-06 therefore identifies self-match/resubstitution and cannot treat these as independent validation or acceptance evidence. Several E-06 outcomes are REVIEW/REJECT due to the existing confidence, warm-up, or layout gates even where extracted numeric cells are correct.
4. The 90°/270° software rotations fail closed at layout detection; the 180° rotations retain uncertain layout but yield no EXTRACTED numeric values. These are synthetic digital rotations, not physical printer/scan variance.
5. No unit-price/subtotal value is included in the extraction correctness counts. E-06 receives the repository's existing Canonical fixture (which contains schema-required synthetic/derived context) solely so its established schema and arithmetic gates can run; those extra fields are not part of CORRECT/NOT-EXTRACTED scoring.

## Reproduction

```sh
PYTHONPATH=src python scripts/run_e06_dry_run.py
```

The runner aborts immediately and does not write this report if any value is EXTRACTED-but-wrong. Temporary rotated PNGs are created under the system temporary directory and are not committed.

## E-06 verdict details

Verdict totals: ACCEPT=0, REVIEW=13, REJECT=3.
- `29` at 0°: Extraction confidence is below the 0.80 reject threshold
- `32` at 0°: Extraction confidence is below the 0.80 reject threshold
- `33` at 0°: E-05 match or required layout component is below the 0.80 reject threshold
