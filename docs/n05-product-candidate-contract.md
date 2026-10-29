# N-05 / N-07: ProductCandidate, NameSuggestion, and NameConfirmation

**Status:** implementation complete; four real-fixture examples and schema are committed with this task. These are prototype records only, not a catalog identity or an acceptance of any OCR result.

## Contract boundary

N-05 adds `schemas/n05/product_candidate_v1.schema.json`, versioned as `n05.product-candidate.v1`. N-07 extends that versioned example with a `NameConfirmation` record alongside its N-02 source version, source fixture, optional `NameSuggestion` records, crop provenance, and dated price observations. The nested candidate retains the N-02 fields and their meanings; N-05/N-07 do not revise `n02.product-candidates.v1`, the N-02 golden, the N-04 output contract, `contracts/`, or `adapter.py`.

The schema makes the following rules explicit:

- A suggestion carries ordered `lines`, a newline-joined `suggested_name`, a 0–100 confidence value (or `null`), `engine`, `engine_version`, and `model_version`.
- Every suggestion has a crop ID, repository-relative crop file, and SHA-256 reference. Tests verify that this crop matches the candidate's reference crop and its current bytes.
- `accepted` is constrained to `false`. A suggestion cannot be auto-accepted by this contract; confidence is diagnostic, not calibrated.
- `name_suggestions` is empty by default; the generator does not import or run OCR unless `--suggest-names` is explicitly requested and the optional ParisaOCR runtime is installed. When enabled, every suggestion remains non-accepting.
- `NameConfirmation` carries `confirmed_name`, an explicit `UNCONFIRMED` / `CONFIRMED` / `REVIEW` status, its exact cluster-key provenance, and near-threshold review metadata. Initial work-list/golden records use an empty `confirmed_name`. A confirmation is reusable only for the same stable `name_crop_cluster_id`.
- Near-threshold dHash pairs stay separate; both candidates are marked `REVIEW` with `NEAR_THRESHOLD_CLUSTER`. Similarity cannot merge their clusters or transfer confirmation.
- A price observation requires an explicit ISO date, a positive `unit_price_rials`, invoice ID, and source crop ID. Its date source is the offset-aware Probe `captured_at` timestamp passed to N-02 (or recorded in `header.captured_at`); invoice-image dates are not read.

## Real-fixture goldens

The examples are under `tests/fixtures/real/n05-goldens/`, with one selected reference candidate for each of the four canonical fixtures. Candidate quantities, exact crop-cluster IDs, occurrence counts, invoice IDs, and price observations come from deterministic local inputs. Each committed example has an empty `confirmed_name`, `UNCONFIRMED` status, no review marker, and `name_suggestions: []`; the default generator neither reads saved OCR results nor imports an OCR engine.

| Fixture | Selected crop | Occurrences | `confirmed_name` | Optional suggestion |
| --- | --- | ---: | --- | --- |
| 29 | `29_row0` | 1 | empty | none |
| 31 | `31_row0` | 2 (`32_row0` shares its exact cluster) | empty | none |
| 32 | `32_row1` | 1 | empty | none |
| 33 | `33_row10` | 1 | empty | none |

The previously recorded N-01/N-04 suggestions remain in their separate evidence files and are not copied into the default work-list/goldens. If the optional engine is explicitly enabled, each suggestion still records provenance and remains `accepted: false`; the OCR strings are not verified product names and the provisional N-01/N-04 references remain owner-unconfirmed.

The four canonical fixtures have `header.captured_at: null`, and the N-05 golden generator does not receive a Probe timestamp; accordingly every committed N-05 example has `price_observations: []`. No dates or price trends have been invented. The N-02 dated-path golden separately exercises the capture-time path with a clearly synthetic sentinel. The N-05 schema test also validates an explicitly synthetic dated observation; it is not evidence from a fixture. Price integers remain as supplied by the Canonical test fixtures; no rial/toman conversion is performed.

## Idempotency and reproduction

`scripts/generate_n05_candidate_goldens.py` rebuilds the N-02 candidates from canonical inputs, emits empty `NameConfirmation` records and empty suggestion arrays by default, and writes stable UTF-8 JSON with sorted keys, fixed indentation, and a final newline. `--suggest-names` is opt-in and requires the installed optional ParisaOCR runtime; no OCR package/model is required by the default path.

The N-05 test builds the default examples twice from the same repository inputs, compares both serialized byte streams, and then compares them with all four committed golden files. This establishes same-input/same-output idempotency for the OCR-free path. Optional live OCR inference is not claimed byte-identical across hardware, package environments, or model runtimes.

With the project's Python test dependencies installed:

```bash
PYTHONPATH=src python scripts/generate_n05_candidate_goldens.py
PYTHONPATH=src python -m pytest -q tests/test_n05_product_candidate_contract.py
```

The contract, provenance, confidence bounds, non-acceptance rule, two-line preservation, explicit-date requirement, real crop hashes, and idempotency are covered by `tests/test_n05_product_candidate_contract.py`.
