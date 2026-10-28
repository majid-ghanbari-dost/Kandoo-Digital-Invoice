# N-05: versioned ProductCandidate and NameSuggestion examples

**Status:** implementation complete; four real-fixture examples and schema are committed with this task. These are prototype records only, not a catalog identity or an acceptance of any OCR result.

## Contract boundary

N-05 adds `schemas/n05/product_candidate_v1.schema.json`, versioned as `n05.product-candidate.v1`. It formalizes a single `ProductCandidate` example with its N-02 source version, source fixture, optional `NameSuggestion` records, crop provenance, and dated price observations. The nested candidate retains the N-02 fields and their meanings; N-05 does not revise `n02.product-candidates.v1`, the N-02 golden, the N-04 output contract, `contracts/`, or `adapter.py`.

The schema makes the following rules explicit:

- A suggestion carries ordered `lines`, a newline-joined `suggested_name`, a 0–100 confidence value (or `null`), `engine`, `engine_version`, and `model_version`.
- Every suggestion has a crop ID, repository-relative crop file, and SHA-256 reference. Tests verify that this crop matches the candidate's reference crop and its current bytes.
- `accepted` is constrained to `false`. A suggestion cannot be auto-accepted by this contract; confidence is diagnostic, not calibrated.
- When suggestions are enabled, the candidate has at least one suggestion. When disabled, the suggestion array is empty.
- A price observation requires an explicit ISO date, a positive `unit_price_rials`, invoice ID, and source crop ID. Its date source is the offset-aware Probe `captured_at` timestamp passed to N-02 (or recorded in `header.captured_at`); invoice-image dates are not read.

## Real-fixture goldens

The examples are under `tests/fixtures/real/n05-goldens/`, with one selected reference candidate for each of the four canonical fixtures. Candidate quantities, cluster IDs, occurrence counts, invoice IDs, and price observations come from the existing deterministic N-02 builder. Suggestions use only the recorded **unprocessed ParisaOCR** `segments` and `confidence` in `docs/n01-name-reading.json`; the generator does not run OCR and does not use the N-01 `reference_name` field.

| Fixture | Selected crop | Recorded suggestion lines | Confidence | Notes |
| --- | --- | --- | ---: | --- |
| 29 | `29_row0` | `ریسه تم` | 99.8 | One occurrence |
| 31 | `31_row0` | `دستمال سفره تم` | 100.0 | Existing N-02 cluster also contains `32_row0`; its two occurrences are preserved |
| 32 | `32_row1` | `سطل شن بازی کوچک` | 100.0 | One occurrence |
| 33 | `33_row10` | `پیش دستی کاغذی` / `ماتایی تم` | 98.65 | Two lines are kept as two lines and joined with a newline |

All examples identify `ParisaOCR` version `0.7.2` and model `parisaocr-fa-0.1`. The displayed strings are OCR suggestions, not verified product names. N-01/N-04 evaluation references remain provisional and owner-unconfirmed; these records make no accuracy claim and remain unaccepted.

The four canonical fixtures have `header.captured_at: null`, and the N-05 golden generator does not receive a Probe timestamp; accordingly every committed N-05 example has `price_observations: []`. No dates or price trends have been invented. The N-02 dated-path golden separately exercises the capture-time path with a clearly synthetic sentinel. The N-05 schema test also validates an explicitly synthetic dated observation; it is not evidence from a fixture. Price integers remain as supplied by the Canonical test fixtures; no rial/toman conversion is performed.

## Idempotency and reproduction

`scripts/generate_n05_candidate_goldens.py` rebuilds the N-02 candidates from the canonical inputs, joins the pinned N-01 OCR records for the four selected crops, hashes the existing N-02 crop files, and emits stable UTF-8 JSON with sorted keys, fixed indentation, and a final newline. It requires no OCR runtime or network access.

The N-05 test builds the examples twice from the same repository inputs, compares both serialized byte streams, and then compares them with all four committed golden files. This establishes same-input/same-output idempotency for this pinned golden-generation path. It does **not** claim that live OCR inference is byte-identical across different hardware, package environments, or model runtimes.

With the project's Python test dependencies installed:

```bash
PYTHONPATH=src python scripts/generate_n05_candidate_goldens.py
PYTHONPATH=src python -m pytest -q tests/test_n05_product_candidate_contract.py
```

The contract, provenance, confidence bounds, non-acceptance rule, two-line preservation, explicit-date requirement, real crop hashes, and idempotency are covered by `tests/test_n05_product_candidate_contract.py`.
