# N-02 — Deterministic ProductCandidate Prototype

**Status:** prototype only; not a production catalog, confirmed product identity, or issuance input.

## Deliverables

- Builder: [`scripts/run_n02_product_candidates.py`](../scripts/run_n02_product_candidates.py)
- JSON Schema: [`schemas/product_candidate_prototype_v1.json`](../schemas/product_candidate_prototype_v1.json)
- Default golden output from all four canonical fixtures: [`tests/fixtures/real/canonical/product-candidates.golden.json`](../tests/fixtures/real/canonical/product-candidates.golden.json)
- Dated-path golden using an explicitly synthetic Probe timestamp: [`tests/fixtures/real/canonical/product-candidates-captured-at.golden.json`](../tests/fixtures/real/canonical/product-candidates-captured-at.golden.json)
- Reference crop PNGs: [`tests/fixtures/real/n02-reference-crops/`](../tests/fixtures/real/n02-reference-crops/)
- Tests: [`tests/test_n02_product_candidates.py`](../tests/test_n02_product_candidates.py)

## Output and aggregation

The golden contains **22 candidates** for **25 line-item occurrences**. Each record has a stable dHash cluster ID, one representative crop file, occurrence count, integer quantity sum, contributing crop IDs, dated unit-price observations, and sorted invoice IDs. Candidate identity is keyed by the existing `name-dhash-*` cluster ID; aggregation uses a mapping keyed by that ID, so another occurrence with the same ID updates its one record rather than appending a duplicate. Re-running the same inputs serializes byte-identical JSON.

The three repeated visual groups from the earlier provisional crop mapping are represented by these records. That visual mapping is provisional and not owner-confirmed; the output contains no product-name text:

| Source crop IDs | Cluster ID | Occurrences | Quantity sum | Invoice IDs | Reference crop |
|---|---|---:|---:|---|---|
| `31_row0`, `32_row0` | `name-dhash-a828a9ad26245a5a` | 2 | 2 | `e05-synth-invoice-31`, `e05-synth-invoice-32` | `31_row0.png` |
| `31_row1`, `32_row3` | `name-dhash-b4e5b4346e6ecddd` | 2 | 2 | `e05-synth-invoice-31`, `e05-synth-invoice-32` | `31_row1.png` |
| `31_row2`, `33_row1` | `name-dhash-95b496c726a66969` | 2 | 11 | `e05-synth-invoice-31`, `e05-synth-invoice-33` | `31_row2.png` |

For each candidate, the reference is the source crop with the lowest numeric `(fixture ID, row index)` pair. These PNGs are the original geometric description-cell crops (with the repository's fixed table insets), not OCR text or resized classifier outputs. The selected reference file is persisted in the golden record.

## Inputs, dates, and boundaries

- Numeric quantities and unit prices are read from the four label-derived Canonical Invoice v0 fixtures. The line-item order is joined to the matching real-image description crops after the existing projection geometry checks verify row counts and bands.
- The crop-cluster ID is produced by the existing local `cluster_description_crops` dHash implementation at threshold 1. All 25 real crop rows are retained: three paired clusters and 19 singletons.
- Canonical fixture `product_name` values are synthetic placeholders and are deliberately never read. The candidate records contain no product names or categories. The `e05-synth-*` invoice identifiers are also fixture-only IDs.
- The only accepted date source is the offset-aware Probe `captured_at` timestamp. The N-02 builder accepts `--captured-at` (an explicit batch override) or uses each canonical fixture's `header.captured_at`; it never reads `header.printed_date`, invoice-image text, file timestamps, or the current date. The date is the calendar date in the timestamp's stated offset. The four source fixtures have `captured_at: null`, so the default golden has empty observation arrays. **No dates are inferred.**
- The dated-path golden uses the clearly synthetic sentinel `2099-01-02T03:04:05+03:30` and demonstrates 25 dated observations over the same four canonical fixtures. It is a deterministic code-path test, not real Probe evidence or an actual capture date. Each record retains its integer rials amount from the canonical test fixture; the currency unit is not guessed or converted.
- The four canonical objects were synthesized from operator-confirmed numeric labels; they were not emitted by `pipeline_v0`. The 33 fixture is a DRAFT projection of an E-07 REVIEW result. These candidate aggregates are fixture evidence only, not operational catalog data.

## Determinism and validation

- Candidates sort by cluster ID; crop IDs sort by numeric fixture and row; invoice IDs and price observations have fixed sort keys. Duplicate source crop contributions are rejected.
- The test suite checks the JSON Schema, exact default and explicitly dated golden bytes, repeated crop groups, all reference files, absence of text names/categories, missing-date handling, offset-aware timestamp validation, and that a synthetic added invoice contribution updates one existing candidate. The added-invoice/date case is in-memory test data only.
- This is an aggregate prototype. It does not alter the existing `src/product_candidate` exact-match layer, introduce catalog approval, or infer names.

## Reproduction

```sh
PYTHONPATH=src python scripts/run_n02_product_candidates.py \
  --output-json /tmp/n02-product-candidates.json
# Optional: pass the offset-aware timestamp supplied by Probe explicitly.
PYTHONPATH=src python scripts/run_n02_product_candidates.py \
  --captured-at '2026-10-26T14:20:00+03:30' \
  --output-json /tmp/n02-product-candidates-dated.json
PYTHONPATH=src python -m pytest -q tests/test_n02_product_candidates.py
```
