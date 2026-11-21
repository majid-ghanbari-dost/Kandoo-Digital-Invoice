# Canonical Invoice v0

## 1. Overview

Canonical Invoice v0 is the storage-neutral Python-side contract for an invoice
in either Kandoo mode. It is the proposed data boundary between local Python
extraction and the future platform implementation. Its JSON Schema is
[`schemas/canonical_invoice_v0.json`](../schemas/canonical_invoice_v0.json); the
structural, provenance, lifecycle, and issued-content checks are implemented in
`src/image_extraction_adapter/canonical_invoice.py`.

This deliverable defines a contract and validator only. It does **not** connect
the extraction adapter to issuance, change a frozen contract, issue invoices,
convert OCR text, or implement E-02/C# behavior.

## 2. Field reference

| Name | Type | Required | Provenance | Description |
| --- | --- | --- | --- | --- |
| `schema_version` | string | Yes | Platform metadata | Contract version; fixed to `"0"`. |
| `mode` | enum `A` / `B` | Yes | Platform metadata | Native Kandoo issuance / capture alongside an existing POS. |
| `invoice_id` | string | Yes | `native` | Internal invoice identity; opaque and unique within its owner. |
| `display_number` | string | Yes | `native` | Kandoo display identifier; distinct from the printed POS number. Allocation is outside E-01. |
| `operation_id` | string | Yes | `native` | Producer-supplied operation identity. |
| `device_id` | string | Yes | `native` | Producer-supplied device identity. |
| `public_token` | string | Yes | `native` | Unpadded base64url token, at least 22 characters; producers must generate at least 128 random bits. |
| `store_id` | string | Yes | `native` | Opaque store identity. |
| `customer` | object | Yes | Per-field below | Required customer data container. |
| `customer.phone` | non-empty string | Yes | `native` or `captured` | Phone value; v0 does not normalize it. |
| `customer.phone_status` | enum `claimed` / `verified` | Yes | `native` | Platform verification status; claimed is permitted and is not proof of ownership. |
| `state` | lifecycle enum | Yes | Platform metadata | One of the six states below; not an extraction outcome. |
| `state_history` | array of transition objects | Yes | Event metadata | Complete ordered transition path from DRAFT; each event carries `operation_id` and `device_id`. |
| `line_items` | non-empty array | Yes | Per-field below | Invoice line records; at least one item. |
| `line_items[].product_name` | non-empty string | Yes | `native`, `captured`, `derived`, or `untrusted` | Product description/name; unavailable required line values are rejected. |
| `line_items[].quantity` | positive integer | Yes | `native`, `captured`, `derived`, or `untrusted` | Whole-number quantity; fractional quantities are rejected. |
| `line_items[].unit_price` | non-negative integer rials | Yes | Mode A: `native`; mode B: `captured` if printed, otherwise `derived` | Validator checks the label but never calculates or repairs the value. |
| `line_items[].line_total` | non-negative integer rials | Yes | `native`, `captured`, `derived`, or `untrusted` | Exact line amount in rials. |
| `summary.subtotal` | non-negative integer rials | Yes | Per-field provenance label | Summary amount; no arithmetic equation is imposed by v0. |
| `summary.extra_amounts` | object of non-negative integer rials | Yes | Per-key provenance labels | Named adjustments; send `{}` when empty. |
| `summary.payable` | non-negative integer rials | Yes | Per-field provenance label | Amount payable in rials. |
| `summary.tax_lines` | optional array of `{label: string, amount: integer rials, provenance: v0 label}` | No | Per-entry provenance | Default annotation `[]`; reserved structure only, not computed or business-validated in MVP. |
| `summary.discount_lines` | optional array of `{label: string, amount: integer rials, provenance: v0 label}` | No | Per-entry provenance | Default annotation `[]`; reserved structure only, not computed or business-validated in MVP. |
| `summary.rounding` | optional integer or null | No | No separate provenance field specified | Default annotation `null`; no rounding behavior in MVP. |
| `attention_cells` | array of `{field, raw_value, reason}` | Yes | Review evidence | Send `[]` when no unresolved cells exist. Must be empty at VALIDATED or later. |
| `header` | object | Yes | Per-field below | Container is required; its printed/capture properties are optional. |
| `header.captured_at` | nullable ISO 8601 timestamp | No | `derived` when present; otherwise `unavailable` | Probe capture time; a present timestamp must carry an offset. |
| `header.printed_date` | nullable string | No | `untrusted` when present; otherwise `unavailable` | Raw printed date; not an ordering authority. |
| `header.printed_time` | nullable string | No | `untrusted` when present; otherwise `unavailable` | Raw printed time. |
| `header.invoice_number` | nullable string | No | `untrusted` when present; otherwise `unavailable` | External printed number; distinct from `display_number`. |
| `provenance.image_sha256` | nullable lower-case SHA-256 hex | Yes | Provenance metadata | Hash only; no image bytes are stored or sent by this contract. |
| `provenance.template_library_id` | nullable string | Yes | Provenance metadata | Template-library identity, if applicable. |
| `provenance.engine_version` | nullable string | Yes | Provenance metadata | Extraction-engine version, if applicable. |
| `provenance.fields` | mirrored provenance object | Yes | Labels per contract | Mirrors customer, each line, subtotal/extra_amounts/payable, and header; tax/discount provenance is carried per entry. |
| `issued_content_sha256` | lower-case SHA-256 hex | Conditional | `derived` integrity metadata | Required at ISSUED and retained by REVOKED/SUPERSEDED; absent before ISSUED. |

### Reserved for Future Accounting Module

E-01b reserves the optional `summary.tax_lines`, `summary.discount_lines`, and
`summary.rounding` fields for ACC-0. ACC-0 is **PARKED** and is not part of the
MVP. The schema annotates absent fields with defaults `[]`, `[]`, and `null`,
respectively. `validate_canonical_invoice()` remains non-mutating: omission is
valid, but validation does not materialize those defaults in the input.

When present, each tax/discount entry must have a string `label`, integer `amount`
in rials, and a `provenance` value from the existing v0 label set. `rounding`
must be an integer or `null`. E-01b checks only structure and types; it does not
compute tax, discounts, or rounding, validate tax/discount rules, or reconcile
these fields with subtotal/payable. No separate provenance property for
`rounding` is defined in this increment.

Before ACC-0 starts, it requires a tax/accounting expert review, a market and
competitor analysis, and a legal review of the responsibility change.

## 3. State machine

```text
DRAFT -> EXTRACTED -> VALIDATED -> ISSUED -> REVOKED
                                      `----> SUPERSEDED
```

The last two transitions are alternatives from ISSUED; REVOKED and SUPERSEDED
are terminal. `state_history` must be the contiguous complete path from DRAFT
and its final target must equal `state`. DRAFT has an empty history. The
validator checks every edge rather than accepting a state label by itself.

## 4. Provenance policy

- `schema_version` is the string `"0"`; `mode` is `"A"` (native Kandoo) or
  `"B"` (capture alongside an existing POS).
- Kandoo `invoice_id`, `display_number`, `operation_id`, `device_id`,
  `public_token`, and `store_id` are non-empty strings. The public token is
  unpadded base64url with at least 22 characters; producers must generate at
  least 128 random bits. The schema checks shape and length, not entropy.
- `customer.phone` is required and non-empty. `phone_status` is `claimed` or
  `verified`; claimed is a valid status, not proof of ownership. v0 does not
  normalize phone numbers.
- `line_items` contains at least one item. `quantity` is a positive integer.
  The existing `unit_price`, `line_total`, `subtotal`, `extra_amounts`, and
  `payable` amounts are non-negative integer rials. E-01b's optional
  `tax_lines[].amount`, `discount_lines[].amount`, and `rounding` are type-checked
  only (integer, integer, and integer-or-null); no sign or accounting rule is
  applied to these reserved fields. Floating-point monetary values, decimal
  strings, and implicit currency conversion are not accepted. `extra_amounts`
  is an object of named integer-rial amounts; use `{}` when there are none. Send
  `attention_cells: []` when there are no unresolved cells. Although the schema
  carries JSON Schema `default` annotations, validation does not insert defaults.
- `provenance.fields` mirrors customer, line items, `subtotal`, `extra_amounts`,
  `payable`, and header. Each line item has a matching provenance object; the
  `extra_amounts` provenance keys must match the amount keys. E-01b tax and
  discount entries carry their own provenance label; `rounding` has no separate
  provenance property. Labels are `native`, `captured`, `derived`, `untrusted`,
  or `unavailable`. A missing required provenance value is an error; the
  validator never fills one in.
- In mode A, a Kandoo-native `unit_price` may be labeled `native`. In mode B,
  label a printed unit price `captured`; otherwise label a value explicitly
  supplied by an upstream derivation `derived`. This validator does not
  calculate a unit price. A value that cannot be supplied without guessing
  stays in review and is not promoted into a valid issued invoice.
- `header` is always an object, but its printed fields are optional. Omit a
  missing value or set it to `null`, and label it `unavailable`. Present
  `printed_date`, `printed_time`, and `invoice_number` values are labeled
  `untrusted`; they are not identity or ordering authorities. The Kandoo
  `display_number` is a separate field. If `captured_at` is present, it must be
  an ISO 8601 timestamp with a UTC offset supplied by Probe and its label is
  `derived`; otherwise its label is `unavailable`.
- `provenance.image_sha256`, `template_library_id`, and `engine_version` are
  present as metadata keys. Values may be `null` when not applicable. The
  schema stores no image bytes and performs no upload or network operation.

The validator does not assert that subtotal equals the sum of line totals or
that payable equals subtotal plus `extra_amounts`. E-01b reserves tax/discount
line arrays and an optional rounding value but does not define their arithmetic
or accounting semantics. The validator does not compute totals including tax or
discount, apply rounding, or validate tax/discount rules. Any arithmetic or
extraction uncertainty must be handled by the upstream review gate; v0 never
repairs values.

### Issued-content validation details

The six lifecycle states and only allowed edges are:

```text
DRAFT -> EXTRACTED -> VALIDATED -> ISSUED -> REVOKED
                                      `----> SUPERSEDED
```

`state_history` is the complete ordered transition path from `DRAFT` to the
current `state`. Each event includes its own non-empty `operation_id` and
`device_id`. `DRAFT` has an empty history. The terminal states `REVOKED` and
`SUPERSEDED` are alternatives and have no outgoing transition.

`validate_canonical_invoice(data)` returns `(is_valid, errors)` without
modifying `data`. Besides JSON Schema validation, it checks history continuity,
field/provenance alignment, header label/value rules, exact integer values,
and the issued-content digest. `is_valid_transition(from_state, to_state)`
exposes the transition table.

`is_issuable(data)` is true only for a valid invoice in state `ISSUED` with the
required invoice, customer, line-item, and summary content present. Claimed and
verified phone statuses are both valid. Unresolved `attention_cells` and
required values labeled `untrusted` or `unavailable` block `VALIDATED` and later
states; optional printed header values may remain marked `untrusted` or
`unavailable`. No unresolved attention cell is silently cleared.

An `ISSUED` invoice must include `issued_content_sha256`. The SHA-256 digest is
computed over this immutable-content projection, in UTF-8:

```text
schema_version, mode, invoice_id, display_number, operation_id, device_id,
public_token, store_id, customer, line_items, summary, attention_cells, header,
provenance
```

The projection excludes `state`, `state_history`, and
`issued_content_sha256`, so a legal transition to `REVOKED` or `SUPERSEDED`
retains the same digest. Serialization is compact JSON with no insignificant
whitespace; object keys are recursively ordered by UTF-16 code units; arrays
retain order; integers use base-10 notation; non-ASCII characters are emitted
as UTF-8; JSON control characters, quotes, and backslashes use standard JSON
escapes. Floating-point values and lone surrogates are forbidden. The digest is
an integrity check, not a signature or privileged-storage/WORM guarantee; a
writer able to replace both content and digest can rewrite the record.

## 5. Status mapping

Adapter outcomes are routing outcomes, **not** additional invoice lifecycle
states:

| Existing adapter outcome | v0 routing result | Effect |
| --- | --- | --- |
| `ImageExtractionReady` | `AUTO` candidate | May be considered for the ordinary validation path. It does not issue or advance an invoice automatically. |
| `ImageExtractionReviewRequired` | `REVIEW` | Hold for review; preserve uncertainty in attention/provenance data. Do not issue. |
| `ImageExtractionBlocked` | `REJECT` | Stop. No Canonical Invoice v0 record is required for a blocked extraction. |

A `Ready` result is not itself state `ISSUED`; the state machine remains the
only issuance lifecycle. The current extraction adapter exposes monetary text
as strings (often with decimal fractions) and can expose fractional quantities.
This contract performs no conversion from those values to integer rials or
whole quantities. An upstream conversion rule must be explicit and lossless;
otherwise route to `REVIEW`. No adapter, glyph-classifier, threshold, or OCR
behavior is changed here.

## 6. Valid examples

The following are synthetic contract examples, not OCR-accuracy evidence and
not production identifiers.

### Mode A: native Kandoo extraction result

```json
{
  "schema_version": "0",
  "mode": "A",
  "invoice_id": "inv-a-0007",
  "display_number": "2026-000007",
  "operation_id": "op-create-0007",
  "device_id": "device-01",
  "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
  "store_id": "store-01",
  "customer": {"phone": "+15551234567", "phone_status": "claimed"},
  "state": "EXTRACTED",
  "state_history": [
    {"from_state": "DRAFT", "to_state": "EXTRACTED", "operation_id": "op-transition-1", "device_id": "device-01"}
  ],
  "line_items": [
    {"product_name": "Synthetic Widget", "quantity": 2, "unit_price": 500, "line_total": 1000}
  ],
  "summary": {"subtotal": 1000, "extra_amounts": {"tax": 80}, "payable": 1080},
  "attention_cells": [],
  "header": {
    "captured_at": "2026-10-22T09:30:00Z",
    "printed_date": null,
    "printed_time": null,
    "invoice_number": null
  },
  "provenance": {
    "image_sha256": null,
    "template_library_id": null,
    "engine_version": null,
    "fields": {
      "invoice_id": "native",
      "display_number": "native",
      "operation_id": "native",
      "device_id": "native",
      "public_token": "native",
      "store_id": "native",
      "customer": {"phone": "native", "phone_status": "native"},
      "line_items": [
        {"product_name": "native", "quantity": "native", "unit_price": "native", "line_total": "native"}
      ],
      "summary": {
        "subtotal": "native",
        "extra_amounts": {"tax": "native"},
        "payable": "native"
      },
      "header": {
        "captured_at": "derived",
        "printed_date": "unavailable",
        "printed_time": "unavailable",
        "invoice_number": "unavailable"
      }
    }
  }
}
```

### Mode B: captured alongside an existing POS

This synthetic extraction-result example has a derived unit price, an
untrusted external receipt number, an unavailable printed date, and a Probe
capture timestamp. It is still only `EXTRACTED`, not issued.

```json
{
  "schema_version": "0",
  "mode": "B",
  "invoice_id": "inv-b-0007",
  "display_number": "2026-000007",
  "operation_id": "op-create-0007",
  "device_id": "device-01",
  "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
  "store_id": "store-01",
  "customer": {"phone": "+15551234567", "phone_status": "claimed"},
  "state": "EXTRACTED",
  "state_history": [
    {"from_state": "DRAFT", "to_state": "EXTRACTED", "operation_id": "op-transition-1", "device_id": "device-01"}
  ],
  "line_items": [
    {"product_name": "Synthetic Widget", "quantity": 2, "unit_price": 500, "line_total": 1000}
  ],
  "summary": {"subtotal": 1000, "extra_amounts": {"tax": 80}, "payable": 1080},
  "attention_cells": [],
  "header": {
    "captured_at": "2026-10-22T09:30:00Z",
    "printed_date": null,
    "printed_time": null,
    "invoice_number": "POS-0042"
  },
  "provenance": {
    "image_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "template_library_id": "synthetic-template-v0",
    "engine_version": "synthetic-engine-0.1",
    "fields": {
      "invoice_id": "native",
      "display_number": "native",
      "operation_id": "native",
      "device_id": "native",
      "public_token": "native",
      "store_id": "native",
      "customer": {"phone": "captured", "phone_status": "native"},
      "line_items": [
        {"product_name": "captured", "quantity": "captured", "unit_price": "derived", "line_total": "captured"}
      ],
      "summary": {
        "subtotal": "captured",
        "extra_amounts": {"tax": "captured"},
        "payable": "captured"
      },
      "header": {
        "captured_at": "derived",
        "printed_date": "unavailable",
        "printed_time": "unavailable",
        "invoice_number": "untrusted"
      }
    }
  }
}
```

A printed unit price in mode B changes only its provenance label from
`"derived"` to `"captured"`. A verified customer changes
`customer.phone_status` to `"verified"`; the phone status field's provenance
remains `"native"`. A valid review-held extraction can include, for example:

```json
"attention_cells": [
  {"field": "line.0.product_name", "raw_value": "Synthetic Widge?", "reason": "operator confirmation required"}
]
```

That attention-cell example must remain in `EXTRACTED` (or earlier) and cannot
be promoted to `VALIDATED` until the ambiguity is resolved through an explicit
review process.

## 7. Invalid examples

Each case fails validation; none is repaired automatically:

- `"payable": 1080.50`, a decimal string such as `"1080.50"`, a float in any
  field, a negative amount, or a fractional/zero quantity.
- Missing `invoice_id`, `operation_id`, `device_id`, `customer.phone`, a line
  field, summary field, provenance metadata key, or required provenance label.
- `customer.phone_status: "unknown"` or a provenance label outside the five
  v0 labels.
- A reserved tax/discount line missing `label`, `amount`, or `provenance`, a
  non-integer line amount, or a `rounding` value that is neither integer nor
  `null`.
- A mode B `unit_price` labeled `untrusted`/`unavailable`, or mismatched
  provenance-array length / extra-amount keys.
- A non-null `printed_date` labeled `unavailable`, a null printed date labeled
  `untrusted`, or a `captured_at` value not labeled `derived` / lacking an
  offset.
- A direct `DRAFT -> ISSUED` history entry, a discontinuous history, or a
  snapshot state that does not equal the history's final state.
- Any non-empty `attention_cells` at `VALIDATED` or later.
- An issued invoice changed after its digest is computed (for example, changing
  `line_total`, customer phone, summary payable, or provenance) without a
  matching issued-content digest. Changing content and recomputing the hash is
  not a cryptographic signature and is outside this validator's authority.

## 8. Python extraction to C# platform bridge

The JSON object is the language-neutral seam: Python extraction may produce a
candidate field set, while the platform owns Kandoo identifiers, customer
status, lifecycle events, and issuance. E-01 does not directly cast the current
adapter result into this schema.

The existing adapter exposes `ImageExtractionReady.field_values` as
`(field_name, string_value)` pairs. These are semantic mapping candidates, not
an approved conversion or proof that a value is integer rials:

| Existing adapter field | Canonical candidate | Boundary note |
| --- | --- | --- |
| `invoice.number` | `header.invoice_number` | Keep as untrusted printed identity; do not use as `display_number`. |
| `invoice.date` | `header.printed_date` | Keep untrusted; preserve raw value. |
| `total.net` | `summary.subtotal` | Source is currently a numeric string; only accept after explicit, lossless integer-rial interpretation. |
| `tax.amount` | `summary.extra_amounts.tax` | Same explicit integer-rial conversion requirement. |
| `invoice.payable` | `summary.payable` | Same explicit integer-rial conversion requirement. |
| `line.i.description` | `line_items[i].product_name` | Preserve field order/index mapping and provenance. |
| `line.i.quantity` | `line_items[i].quantity` | Current parser may return a string and can represent fractional quantity; v0 accepts only positive integers. |
| `line.i.unit_price` | `line_items[i].unit_price` | Printed → `captured`; otherwise only an explicitly provided upstream derivation → `derived`. |
| `line.i.total` | `line_items[i].line_total` | Current parser exposes numeric text; do not round or truncate. |

`invoice_id`, `display_number`, `operation_id`, `device_id`, `public_token`,
`store_id`, `customer.phone`, and `customer.phone_status` are not supplied by
those OCR field names; the appropriate platform/producer must provide them.
`header.captured_at` is Probe capture metadata, not a printed invoice date.
When a source value is decimal-formatted or cannot be proven to represent an
integer number of rials, keep it in `REVIEW`; E-01 does not normalize digits,
round, infer currency, reconcile totals, or repair extraction.

A future C# consumer should validate the same JSON Schema and reproduce the
cross-field rules and canonical SHA-256 profile in this document. The synthetic
examples and known-answer digest test provide starting fixtures, but a true
Python/C# conformance suite and C# implementation are still future work. Images
remain local: the contract carries a hash only, not image bytes or a transport
operation.

## 9. Relationship to the E-04 audit

[`docs/issuance-gap-analysis.md`](issuance-gap-analysis.md) recorded that no
E-01/Canonical Invoice v0 artifact existed at its audit baseline and therefore
marked v0 compatibility **unverified**. This commit adds the missing v0 JSON
Schema, Python validator, examples, and tests. It does not establish that the
existing WP-6.2/P6.2 v1.0-MVP records conform to v0, add a migration, or prove
C# interoperability.

The E-04 findings about local issuance behavior also remain scoped: its local
lifecycle and append-only service APIs are not a distributed hub, per-phone
lock, sequential display-number allocator, or WORM/privileged-storage boundary.
The E-01 digest detects stale content against the stored fingerprint but does
not prevent a privileged writer from replacing both content and digest. E-01
adds required identifiers as data fields; it does not implement their hub
allocation, a native-vs-capture product flow, E-02 integration, or D14 legal
wording/owner approval.

## 10. Open questions

The following are deliberately not decided by the v0 schema; current
conservative assumptions are recorded in [`docs/DECISIONS.md`](DECISIONS.md)
under **Assumptions**:

- What approved, lossless rule maps the adapter's decimal-formatted monetary
  strings and possible fractional quantities to integer rials and whole
  quantities? Until decided, such values remain REVIEW.
- Which platform service creates `invoice_id`, `display_number`,
  `operation_id`, `device_id`, and the random `public_token`, and what are the
  lifecycle/restore rules for those identifiers?
- What are the business meanings and arithmetic relationships of `subtotal`,
  `extra_amounts`, `tax_lines`, `discount_lines`, `rounding`, and `payable`?
  ACC-0 remains parked; E-01b does not calculate or validate these relationships.
- What authority and evidence moves a phone from `claimed` to `verified`, and
  which phone normalization rules, if any, will a product mode use?
- Which C# implementation will share the schema, provenance checks, hash
  serializer, and golden vectors with Python? E-01 makes no cross-language
  conformance claim.
- Is the SHA-256 digest sufficient for the deployment threat model, or will a
  later increment require signatures, access controls, or WORM storage?
- D14 customer-facing legal/tax wording still requires owner approval as noted
  by E-04; it is outside this invoice data contract.

## Running tests

The validator uses `jsonschema` 4.x. The existing image-adapter suite also
requires Pillow; Tesseract is not required for these unit tests.

```bash
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m unittest discover -s src -p 'test_*.py' -v
```
