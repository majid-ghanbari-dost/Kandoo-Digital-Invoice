# E-13 verification — E-06 dry-run regression gate

## Result

**Gate: CLOSED GREEN.** The full E-06 dry-run matrix was rerun on the post-E-13 code at HEAD `8c2655bd226b79b81a7b8bd94132257476f5c08e` (tag `stable-e-13`) using:

```sh
PYTHONPATH=/tmp/kandoo-e06-dry-run-deps:src \
  PYTHONDONTWRITEBYTECODE=1 python scripts/run_e06_dry_run.py
```

The runner completed all 16 fixture/rotation combinations (fixtures 29, 31, 32, 33 × rotations 0°, 90°, 180°, 270°). All 16 matrix rows—including the E-02 outcome, E-05 status/score, E-06 verdict/reason string, and numeric counts—were compared byte-for-byte with the matrix in `deliveries/e06-dry-run/report.md`: **16/16 rows identical; no differences**. In particular, fixture 33 at 0° reproduced E-05 `NO_MATCH (0.792)` and E-06 `REJECT`.

The runner writes its output to the reference report path. The pre-run reference was preserved at SHA-256 `f780b8dded4b27131726f5d93d82341ecc0c8bde59f7ed6d1ce1f295872dee90`; after comparison, the original report was restored and its SHA-256 was verified unchanged. Only the generated timestamp and base-HEAD metadata differed in the temporary regenerated report; the complete 16-row matrix was identical.

## Post-E-13 matrix

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

Aggregate numeric counts: **36 CORRECT; 180 NOT-EXTRACTED; 0 EXTRACTED-but-wrong; 216 expected**. E-06 verdict totals: **ACCEPT=0, REVIEW=13, REJECT=3**.

## Fixture 33 cross-path explanation

The E-06 dry-run creates a temporary RGB PNG for each rotation (including 0°) and builds E-02 Glyph templates with `build_templates_for_fold(..., "33")`, excluding fixture 33; the E-12 synthetic-folder test instead copies `33.png` byte-for-byte and calls `extract_pipeline_v0` with the default all-fixture Glyph bank. At 0°, the dry-run E-02 output supplies only nine quantity values—no line totals or payable—so its E-05 observation has `numeric_format=0`, reports missing payable and line-total values, and scores `0.7919275475577959` (`NO_MATCH`, displayed as `0.792`); the adapter observation has line totals and payable with `numeric_format=1`, scoring `0.971927547557796` (`MATCH`). This path-specific E-02 template selection and resulting E-05 input explain the pre-existing cross-path difference; they are unchanged by E-13's pixel-access modernization.

## Full-suite verification

On the same post-E-13 code, the full suite completed with **1,890 passed and 82 subtests passed**, with **zero warnings**. The focused adapter/CLI suite also remains at **29 passed**. No source code was changed for this verification; this report is the evidence artifact.
