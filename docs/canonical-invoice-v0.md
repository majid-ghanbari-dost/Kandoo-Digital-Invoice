# Canonical Invoice v0

Canonical Invoice v0 is the storage-neutral Python-side contract for an invoice
in either Kandoo mode. Its JSON Schema is
[`schemas/canonical_invoice_v0.json`](../schemas/canonical_invoice_v0.json); the
structural, provenance, lifecycle, and issued-content checks are implemented in
`src/image_extraction_adapter/canonical_invoice.py`.

This deliverable defines a contract and validator only. It does **not** connect
the extraction adapter to issuance, change a frozen contract, issue invoices,
convert OCR text, or implement E-02/C# behavior.

## Values and provenance

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
  `unit_price`, `line_total`, and all `summary` amounts are non-negative integer
  rials. Floating-point monetary values, decimal strings, rounding, and
  implicit currency conversion are not accepted. `extra_amounts` is an object
  of named integer-rial amounts; use `{}` when there are none. Send
  `attention_cells: []` when there are no unresolved cells. Although the schema
  carries JSON Schema `default` annotations, validation does not insert defaults.
- `provenance.fields` mirrors the invoice's business fields. Each line item has
  a matching provenance object; the `extra_amounts` provenance keys must match
  the amount keys. Labels are `native`, `captured`, `derived`, `untrusted`, or
  `unavailable`. A missing provenance value is an error; the validator never
  fills one in.
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
that payable equals subtotal plus `extra_amounts`. The v0 contract does not
define discounts, tax semantics, rounding, or other adjustment algebra. Any
arithmetic or extraction uncertainty must be handled by the upstream review
gate; v0 never repairs values.

## Lifecycle and issuance

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

## Extraction-status mapping

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

## Examples

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

## Invalid cases

Each case fails validation; none is repaired automatically:

- `"payable": 1080.50`, a decimal string such as `"1080.50"`, a float in any
  field, a negative amount, or a fractional/zero quantity.
- Missing `invoice_id`, `operation_id`, `device_id`, `customer.phone`, a line
  field, summary field, provenance metadata key, or required provenance label.
- `customer.phone_status: "unknown"` or a provenance label outside the five
  v0 labels.
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

## Running tests

The validator uses `jsonschema` 4.x. The existing image-adapter suite also
requires Pillow; Tesseract is not required for these unit tests.

```bash
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python -m unittest discover -s src -p 'test_*.py' -v
```
