# N-07: deterministic ProductCandidate name work-list

## Scope and output

`scripts/run_n07_name_worklist.py` creates `name-worklist.json` plus one PNG per `ProductCandidate` under `crops/` in the requested output directory. Each work item carries the existing N-02 candidate fields, crop-image path/SHA-256, `NameConfirmation`, and an optional N-04 suggestion array. The default build leaves every `confirmed_name` empty and performs no OCR.

```bash
PYTHONPATH=src:scripts python scripts/run_n07_name_worklist.py \
  --repo-root . --output-dir /tmp/kandoo-name-worklist
```

The output validates against `schemas/n07/name_worklist_v1.schema.json`; its `candidate` uses the `ProductCandidate` definition in `schemas/n05/product_candidate_v1.schema.json`. The N-05 schema now includes the `NameConfirmation` definition and all four N-05 goldens validate against it.

## Confirmation reuse

`confirmation_reuse_key` is the stable `name_crop_cluster_id`. An optional `n07.name-confirmations.v1` file supplies human-confirmed names by exact cluster ID:

```json
{
  "schema_version": "n07.name-confirmations.v1",
  "confirmations": [
    {
      "name_crop_cluster_id": "name-dhash-0123456789abcdef",
      "confirmed_name": "Operator-confirmed product name"
    }
  ]
}
```

Pass it with `--confirmations <file>`. A matching exact cluster reuses the same name deterministically on a later run/invoice; a different cluster never inherits it. The work-list does not infer or fill a name from OCR. The source fixture examples remain unconfirmed.

## Near-threshold safety

N-07 deliberately differs from the older N-02 similarity grouping: work-list candidates are grouped by **exact normalized dHash equality only**. For the existing N-02 threshold of one bit, two distinct hashes at Hamming distance exactly one are emitted as separate work items and both receive `confirmation_status: REVIEW`, `review_required: true`, and reason `NEAR_THRESHOLD_CLUSTER`. Their IDs remain separate; the work-list neither merges nor transfers confirmation between them. A human may review the pair, but this task implements no automatic merge/accept action.

This policy applies to the name-confirmation work-list only; it does not modify the E-02 extraction pipeline or the N-02 golden.

## Optional N-04 suggestion

`--suggest-names` explicitly enables the optional ParisaOCR runtime and is rejected if the `parisaocr` package is not installed. Without that flag, the builder does not instantiate the OCR engine, and every `name_suggestions` array remains empty. If enabled, suggestions retain N-04 provenance and `accepted: false`; they never populate `confirmed_name`.

## Verification and evidence boundary

`tests/test_n07_name_worklist.py` covers schema validation, generated crop files and hashes, empty default confirmations, byte-identical reruns, exact-cluster confirmation reuse after a later occurrence, one-bit near-threshold review without merging, optional N-04 suggestion behavior, and the OCR-free default CLI. `tests/test_n05_product_candidate_contract.py` validates the four updated N-05 golden examples and their `NameConfirmation` records.

The current work-list is demonstrated on repository fixture images 29/31/32/33 and their label-derived Canonical examples. Those synthetic/prototype records are not a live catalog, owner-confirmed product identity, or production OCR validation. Near-threshold behavior is covered with an explicitly synthetic one-bit hash pair. No file under frozen `contracts/` or `src/image_extraction_adapter/adapter.py` is changed.
