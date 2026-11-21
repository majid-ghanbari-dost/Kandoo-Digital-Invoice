# E-02 Template Provenance and Leakage Check

## Result

`src/templates_bank_default.json` is a new Glyph bank built from all four local
fixtures. Its source-image provenance is:

| Fixture | Relative path | SHA-256 | Training use |
|---:|---|---|---|
| 29 | `tests/fixtures/real/29.png` | `61d6d16594ca35d622099ad5c453292d0279127ee65744ce784952b3a781586a` | Row quantities/totals and payable |
| 31 | `tests/fixtures/real/31.png` | `8ea9e20ca3c7161d14bcc719154e0be27bcaaaf5c4b9e5a26818e4b0c1908a10` | Row quantities/totals; payable excluded because its label is `DERIVED_FROM_ARITHMETIC` |
| 32 | `tests/fixtures/real/32.png` | `c6389f078c9a487b06620c01f80f86477ffa7d291cab24d3c9639fc72fd5e68e` | Row quantities/totals and payable |
| 33 | `tests/fixtures/real/33.png` | `2ffe4a33b54a513dc8df9a0eac22ac514f9ebf7aae89958ee11d0fa00cc67e80` | Row quantities/totals and payable |

The builder verified the top-level fixture label status is
`OPERATOR_CONFIRMED`, found safe geometry for each image, and records one source
entry per full fixture. It used 53 labelled numeric cells. All 53 cells
segmented successfully; #31 payable was deliberately excluded from both
training fields and payable-specific template data. The bank contains no image
bytes.

The current generated default-bank file SHA-256 is
`b42688770113faaba9e4024e3af66fa4eed2cb039d184daff6429e0cef047931`.
Rebuild it with:

```sh
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python scripts/build_default_template_bank.py
```

The output is for runtime use on other images. Because all four evaluation
fixtures contribute templates, evaluation against any of them is refused.
`extract_pipeline_v0(..., evaluation=True)` checks source path and image SHA
before Glyph recognition. Fold evaluation builds each bank in memory from the
other three fixtures, verifies the held-out image does not appear in provenance,
and does not use the all-four default bank.

## Legacy `src/templates.json` check

The frozen legacy bank was inspected without editing or overwriting it. Its
current SHA-256 is `c55857af5c83708d780cec94c5f0fbbbb5dba58de1576232ce55d3d8090a1b45`.

| Legacy provenance path | Recorded source SHA-256 | Match to fixture | Evaluation consequence |
|---|---|---|---|
| `../deliveries/image-extraction-ocr/holo_row_detection.png` | `61d6d16594ca35d622099ad5c453292d0279127ee65744ce784952b3a781586a` | Fixture #29 exactly | Refuse #29 by source hash/path |
| `../deliveries/image-extraction-ocr/5.png` | `c6389f078c9a487b06620c01f80f86477ffa7d291cab24d3c9639fc72fd5e68e` | Fixture #32 exactly | Refuse #32 by source hash/path |
| `../deliveries/image-extraction-ocr/glyph-classifier-build-13-rows03-08.png` | `1c8acc27c71b4937850f4e248d9fcff602404d5e8ce448cc2e9d3621238e815d` | Derived crop, not a full-fixture hash; its sibling `13.png` is fixture #33 (`2ffe4a33…`) | Refuse #33 through the known crop-parent lineage |

Fixture #31 is not present in the legacy bank provenance. The new default bank
includes it, so the four fold-specific banks—not either all-fixture bank—are
the only evaluation banks used for the E-02 leave-one-out results.

The legacy file was protected by the builder's destination guard and remained
byte-for-byte unchanged during the build/test checks. E-02 added
`src/templates_bank_default.json`; it did not replace `src/templates.json`.

## LOO template isolation

For held-out image `i`, the evaluator calls the same template builder with only
the other three fixture entries. Each fold's Glyph provenance contains those
three source paths and SHA-256 values. Before recognition,
`assert_no_template_leakage()` checks for either a path match or a digest match.
Missing/unusable provenance fails closed with `TemplateProvenanceError`.

Observed E-02 fold summary:

| Held-out | Training sources | Source overlap refused? | Outcome | EXTRACTED-but-wrong |
|---:|---|---|---|---:|
| 29 | 31, 32, 33 | No | AUTO_CANDIDATE; gate passed | 0 |
| 31 | 29, 32, 33 | No | AUTO_CANDIDATE; gate passed | 0 |
| 32 | 29, 31, 33 | No | AUTO_CANDIDATE; gate passed | 0 |
| 33 | 29, 31, 32 | No | REVIEW; gate failed on `line.3.total` | 0 |

For #31, payable is excluded from direct ground-truth comparisons because its
label is derived from arithmetic. The reported zero is limited to independently
labelled cells that were EXTRACTED; it is not an independent visual
certification of that payable value.

## Data handling

All image reads and hashing occur in the local process. The builder writes only
the numeric template JSON and source paths/hashes; it does not copy images to a
parent repository or upload them. The pipeline does not persist invoice output
or implement store/restore, concurrency, access-control, SMS, or issuance
behavior.
