# Label-derived Canonical Invoice v0 fixtures

These four Canonical Invoice objects are **synthesized from operator-confirmed
numeric labels**, not emitted by `pipeline_v0.py` or the E-02 CLI. Their raw
numeric ground truth and spatial measurements come from the sibling
`../labels.json` records for invoices 29, 31, 32, and 33. The per-image hashes
and per-fixture provenance marker are recorded in `synthesis-manifest.json`.

The JSON objects themselves remain strict Canonical Invoice v0 instances; no
out-of-schema synthesis property was added. The sidecar uses
`"synthesized_from_labels": true` for each fixture because the frozen v0 schema
rejects unknown properties. The manifest also lists each synthetic context
field and the documented context-example source; the details below explain why
those values must not be mistaken for invoice ground truth.

## Provenance and synthetic context

`labels.json` does not contain producer-owned platform IDs, customer context, or
product names. To construct schema-valid test instances, those required fields
use the explicitly synthetic context pattern documented in `docs/cli-contract.md`.
Identifiers are `e05-synth-*`; the documentation-example phone and public
token are not production values; and product names are `Example product N`
placeholders. This context is synthetic in **every** fixture; it is not
extracted invoice data and must never be used in a live POS, customer, or
issuance flow. Phone and product-name placeholders are marked `untrusted` and
listed in `attention_cells`. Schema-required platform identifiers/statuses
carry the v0-required `native` provenance label, but their synthetic nature is
explicitly recorded here and in the manifest.

Numeric data preserve the label values exactly: `quantity` is the existing v0
integer field (not `quantity_millis`), line totals are copied from the labels,
and unit prices are derived only by exact integer division. Subtotals are the
sum of the labeled line totals. Invoice 31's payable is derived in accordance
with its label note; the other payable values are copied from the labels. No
extra charges are inferred.

## Fixture states

- `canonical-29.json`, `canonical-31.json`, and `canonical-32.json` have
  `EXTRACTED` Canonical fixture state corresponding to E-07's
  `AUTO_CANDIDATE` routing result. The state is a synthetic contract projection,
  **not** evidence that the E-02 pipeline emitted these objects.
- `canonical-33.json` is included as `DRAFT`, as directed, because its E-07
  result was `REVIEW`. The Canonical schema has no `REVIEW` lifecycle state;
  this fixture must not be described as accepted or pipeline-extracted.

## Files and revalidation

- `canonical-{29,31,32,33}.json` — strict Canonical Invoice v0 objects.
- `synthesis-manifest.json` — machine-readable `synthesized_from_labels` marker,
  source image hashes, E-07 routing context, and fixture states.
- `../labels.json` — operator-confirmed source values and geometry.

The E-05 tests validate each object with the existing v0 schema/semantic
validator and compare its numeric fields back to the labels. When the six
owner-authorized E-03-kit scans are available, produce genuine CLI/pipeline
outputs where caller context exists and cross-validate those outputs against
these label-derived fixtures. Keep synthetic fixtures distinct from those
future pipeline outputs and from any Holoo accuracy claim.
