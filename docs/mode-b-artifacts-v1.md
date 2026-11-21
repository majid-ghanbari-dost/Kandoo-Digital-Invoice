# Windows Mode B artifacts — v1 (E-16)

This package defines four UTF-8 JSON files that a Windows Mode B client may
store and transfer: an E-05 template bank, an E-06 onboarding verdict, a
layout/font fingerprint, and an E-08 new-type candidate. It is a
language-independent storage/wire contract. It does **not** change the frozen
Canonical Invoice contract under `contracts/`, and none of these artifacts is
a Canonical Invoice or an invoice-issuance instruction.

## Package inventory

All schemas use JSON Schema Draft 2020-12, local `$defs` only, and a
version-specific URN `$id`. The examples and their SHA-256 manifest are in
[`schemas/mode-b/v1/examples/`](../schemas/mode-b/v1/examples/).

| Artifact | Schema | Required top-level body | Existing Python representation |
|---|---|---|---|
| `template-bank.json` | [`template-bank.schema.json`](../schemas/mode-b/v1/template-bank.schema.json) | `template_bank` | `TemplateBank.to_dict()` from E-05 |
| `onboarding-verdict.json` | [`onboarding-verdict.schema.json`](../schemas/mode-b/v1/onboarding-verdict.schema.json) | `evaluation_context`, `result` | `VerdictResult.to_dict()` from E-06 |
| `layout-font-fingerprint.json` | [`layout-font-fingerprint.schema.json`](../schemas/mode-b/v1/layout-font-fingerprint.schema.json) | layout signature, numeric format, `glyph_profile` | E-08 `TemplateCandidate` signature plus E-02 `GlyphTemplateSet.to_json_dict()` feature profiles |
| `new-type-candidate.json` | [`new-type-candidate.schema.json`](../schemas/mode-b/v1/new-type-candidate.schema.json) | `candidate` | `TemplateCandidate.to_dict()` from E-08 |

Every artifact carries an exact `artifact_type`, string `artifact_version` of
`"1"`, and `mode` of `"B"`. The artifact type is a discriminator, not a
localized display label. Top-level `store_id` scopes the record; where a body
also contains `store_id`, consumers **must** require it to equal the envelope
value. Store IDs and invoice IDs are opaque strings and must not be inferred
from another field.

The `examples/manifest.json` lists each example's schema, generating API,
purpose, and SHA-256 over the exact stored UTF-8 bytes (including the terminal
LF). Regenerate the examples with:

```sh
PYTHONPATH=src python scripts/generate_mode_b_artifact_goldens.py
```

The examples are deterministic, synthetic/test-only records built from the
existing labeled fixtures and canonical test fixtures. They use explicit
`e05-synth-*` IDs and placeholders; they are not a real store's bank, an
owner-approved onboarding result, or evidence of Windows interoperability.
The layout/font fingerprint contains learned glyph feature arrays from the
existing leave-one-fixture-out Glyph builder; machine-local image paths are
intentionally omitted, while source invoice IDs and image hashes are retained.

## Encoding and version rules

- Encode as UTF-8 JSON without a BOM. JSON member order and insignificant
  whitespace do not affect schema validity. The checked-in examples use sorted
  keys, two-space indentation, and one terminal LF for stable review.
- Use JSON numbers for scores and geometry. Do not encode numbers as localized
  strings, use comma decimals, or apply locale-specific date formatting.
  Geometry ratios are unitless; they are not pixels unless the field name
  explicitly says otherwise.
- Timestamps use RFC 3339 / ISO 8601 `date-time` strings with an explicit UTC
  offset (`Z` is valid). Consumers validate the format and reject naive local
  timestamps.
- Schema validation is necessary but not sufficient. Consumers also enforce
  cross-field invariants noted below, verify file hashes against the exact
  received bytes, and bind the artifacts to an authenticated store/account.
  SHA-256 is a content digest, not a signature or proof of origin.
- Unknown artifact types, artifact versions, enum values, or structurally
  incompatible files fail closed and are held for review; do not silently
  reinterpret them as v1. The v1 shape is frozen: a structural change requires
  a new versioned schema path and artifact version.

## 1. Template bank

`template_bank` is the E-05 `TemplateBank.to_dict()` object. It contains the
algorithm version, confidence threshold, and one or more normalized layout
templates. A template describes row-count ranges, normalized column boundaries,
row rhythm, payable placement, field positions, and observed numeric-format
cues. It does not contain the original invoice images or raw invoice values.

Coordinates in `normalized_column_boundaries` are x/image-width ratios. E-05
field positions retain their explicit `y_reference`: `row_fraction` means a
fraction of a detected row band; `page_over_width` means y/image-width. The
`*_over_width` properties are ratios, not page pixels. Consumers must check
that boundary values are strictly increasing, row-count minimum does not
exceed row-count maximum, and each field has start coordinates below its end
coordinates; JSON Schema cannot compare arbitrary sibling values.

The confidence threshold is E-05 layout-match configuration only. It is not an
E-06 verdict threshold and does not authorize invoice acceptance. When an E-06
verdict refers to a bank, `template_bank_sha256` is SHA-256 over the exact bytes
of the referenced `template-bank.json` file; do not parse and reserialize the
file before checking that digest.

## 2. Onboarding verdict

`result` is the E-06 `VerdictResult.to_dict()` shape: `verdict`, stable
`reason_codes`, optional confidence and template match, diagnostic `details`,
optional owner-override audit, and `owner_acceptance_eligible`. The schema
enumerates the reason codes currently emitted by E-06. `reason_codes` are the
machine-readable interface; `details` and template `reasons` are opaque
human-readable diagnostics that may be localized and must not be parsed for
control flow.

`evaluation_context` records the decision inputs that are not all repeated in
the result: prior processed-invoice count, whether the bank was locked, D14
agreement state, kit digit-coverage policy, extraction confidence, and any
explicit missing fields. The outer bank digest ties the decision to a specific
stored bank snapshot. Consumers must check that envelope `store_id` and
`invoice_id` match the record being reviewed.

`ACCEPT` is only this onboarding verdict; it is not a Canonical Invoice
lifecycle transition, not owner authentication, and not permission to issue.
The existing owner-verification and Mode B operational controls remain in
force. The schema checks the shape of an override audit record; it cannot
verify a signature or that the actor actually owns the store.

## 3. Layout/font fingerprint

The artifact carries the E-08 normalized `layout_signature`, `field_positions`,
numeric digit repertoire, separators, grouping sizes, and observed numeric
field names. It also carries `glyph_profile`, based on the existing Glyph
`GlyphTemplateSet` feature data:

- `format_version` is the Glyph template format version (currently integer
  `1`), and `grid` is `[10, 14]`.
- Each profile (`row` or `payable`) contains labeled glyphs. `geometry` is
  `(width / reference-height, height / reference-height, top / reference-height,
  bottom / reference-height)`. `grid` is the 140 row-major cell-occupancy
  fractions, with y rows first and x cells second; each value is in `[0, 1]`.
- `training_sources` retains opaque invoice IDs and source-image SHA-256 values,
  not workstation paths. The feature arrays and source hashes are evidence; they
  are not a signed model or a claim that a specific installed typeface was
  identified.

“Font fingerprint” here means a measured numeric-glyph profile. It does not
contain a font-family name, operating-system font ID, printer model, or a
cryptographic identity for a physical font. `fingerprint_id` reuses the E-08
candidate ID for the layout/numeric signature; it does not hash the separate
Glyph feature arrays. To detect file changes, hash the exact whole
`layout-font-fingerprint.json` bytes. The fingerprint is diagnostic and
onboarding evidence only; it must not silently update the active template bank.

## 4. New-type candidate

`candidate` is the E-08 `TemplateCandidate.to_dict()` lifecycle record. A newly
created candidate is `PROPOSED`; subsequent allowed states are `REVIEWED`,
`ACCEPTED`, or `REJECTED`, with reviewer and decision audit fields appropriate
to the state. The schema checks required shape and timestamp fields. The client
must also enforce that outer and inner `store_id` match, candidate identity and
source evidence are immutable, source invoice IDs are append-only, and terminal
states cannot be reversed.

A candidate is separate from the active template bank. `PROPOSED` and
`REVIEWED` candidates are not templates, must not be used for extraction
matching, and must not be promoted without the existing E-08 human review and
onboarding gates. This artifact is a candidate snapshot, not the append-only
E-08 audit trail; persist and transfer audit events using a separately
protected append-only mechanism.

## Validation

Run the schema and golden regression tests from the repository root with
`pytest`, `jsonschema>=4.18,<5`, and the repository's normal Python test
prerequisites installed:

```sh
PYTHONPATH=src python -m pytest -q tests/test_mode_b_artifacts_v1.py
```

The test checks all four schemas, validates the generated examples with
Draft 2020-12 and date-time format checking, verifies the manifest hashes, and
regenerates the examples into a temporary directory to prove byte stability.
JSON Schema does not perform the cross-file hash check or the semantic
cross-field checks called out above; those are consumer responsibilities.
