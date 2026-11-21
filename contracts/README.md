# Canonical Invoice v0 — E-11 consumer package

This directory is the cross-repository publication package for the C# consumer.
The schema version carried by invoices is the string `"0"`; the schema also
contains `x-contract-version: "v0"`. Validate the instance against
[`canonical_invoice_v0.schema.json`](canonical_invoice_v0.schema.json), then
perform the semantic hash check described below. The schema is Draft 2020-12
and every `$ref` is local to that file.

## Append-only publication rule

`stable-e-11` publishes the files in this directory as one immutable package.
Do not edit or replace a published v0 file after tagging. A later contract
change requires a new task and a new versioned path/tag; it must not silently
rewrite v0. Golden instances and their manifest are part of the published
surface, not disposable test data.

## E-01 reuse and the documented contract gap

E-01's schema, semantic validator, lifecycle rules, and canonical hash helper
were already present and tagged before E-11. The original files under
`schemas/` and `src/image_extraction_adapter/canonical_invoice.py` remain
unchanged by this publication. E-11 reuses E-01's immutable-content projection
and byte-serialization/hash implementation.

The E-11 task supplied two binding cross-repository rules that conflict with
the historical E-01 schema: ASM-22 requires `quantity_millis` as signed
integer-thousandths, while E-01 had a positive whole-number `quantity`; and a
Kandoo `display_number` is allocated only at ISSUE, while E-01 required it in
pre-ISSUE records. This is a real schema gap, not a silent edit. Therefore the
new publication path is authoritative for cross-repository v0 consumption and
contains only these documented contract adjustments; the already-tagged E-01
files are retained as historical artifacts. Do not use the old `schemas/`
copy as the C# wire schema for this E-11 publication.

No new accounting equation, currency conversion, rounding rule, or identifier
allocation algorithm is added here. Other fields and lifecycle structure retain
the E-01 v0 shape unless the schema expresses the two adjustments above.

## Rules in force

### Quantity: `quantity_millis` (ASM-22)

Each line item has a required JSON integer `quantity_millis`. It is a signed
integer count of thousandths of a unit: `1000` means `1.000`, `1250` means
`1.250`, and `-250` means `-0.250`. The schema intentionally has no `minimum`
or `maximum`, so the wire contract does not silently forbid a sign or invent a
range. JSON floating-point values and decimal strings are not the encoding;
consumers must reject them. In particular, JSON Schema's abstract `integer`
type may accept a lexical value such as `1250.0`; a strict parser/semantic gate
must reject decimal or exponent-form tokens rather than relying on the schema
alone. The E-11 tests exercise this distinction. No conversion, truncation, or
rounding is performed by this contract. The mirrored provenance property is
also named `quantity_millis`.

### Display number allocation

`display_number` is `null` and its provenance is `unavailable` in `DRAFT`,
`EXTRACTED`, and `VALIDATED`. It becomes a non-empty native string at `ISSUED`
and is retained unchanged by `REVOKED` and `SUPERSEDED`. Allocation occurs at
ISSUE, not draft creation. The printed POS identifier, when present, remains a
separate `header.invoice_number` field and is not a Kandoo display number.

### Canonical JSON and issued-content hash

The hash algorithm is the E-01 `compute_issued_content_sha256` profile. To
calculate `issued_content_sha256` at ISSUE:

1. Construct the immutable-content projection from exactly these top-level
   fields when present: `schema_version`, `mode`, `invoice_id`,
   `display_number`, `operation_id`, `device_id`, `public_token`, `store_id`,
   `customer`, `line_items`, `summary`, `attention_cells`, `header`, and
   `provenance`. The `quantity_millis` field is inside `line_items` and is
   therefore covered. `state`, `state_history`, and
   `issued_content_sha256` are excluded.
2. Serialize the projection as compact JSON with **no whitespace**, recursively
   sorting object keys by ordinal UTF-16 code units. Preserve array order. Use
   base-10 integer notation only (no floats, exponent notation, leading plus,
   or negative zero); emit non-ASCII characters literally as UTF-8; use standard
   JSON escapes for control characters, quotation marks, and backslashes; do not
   escape `/` or ordinary non-ASCII characters. Reject lone UTF-16 surrogates.
   Emit UTF-8 without a BOM and without a terminal newline for the hash input.
3. Set `issued_content_sha256` to lower-case hexadecimal SHA-256 of those exact
   bytes (64 hex characters).

Do not hash the whole invoice file: lifecycle state/history and the digest field
itself are deliberately excluded, so a valid transition to `REVOKED` or
`SUPERSEDED` retains the issued-content hash. The hash is an integrity check,
not a signature or protection against a privileged writer replacing both
content and digest. A consumer must compare the supplied digest with the
recomputed digest and reject a mismatch; JSON Schema alone cannot perform this
check.

The golden `.json` files use the same canonical object serialization and have
exactly one terminal LF for repository file stability. Their `file_sha256`
entries in the manifest cover the stored bytes, including that LF; the
`issued_content_sha256` values cover only the immutable projection, with no LF.

## Golden inventory

[`goldens/manifest.json`](goldens/manifest.json) is authoritative for expected
verdicts, file hashes, expected issued-content digests, and coverage notes.
It contains **4 VALID** and **3 INVALID** synthetic cases:

| Golden | Expected | Coverage |
| --- | --- | --- |
| `goldens/valid/draft_mode_b_null_display_number.json` | VALID | Mode B draft, null/unallocated display number, `quantity_millis=1250`, UTF-8 Persian product text. |
| `goldens/valid/draft_mode_b_negative_quantity_millis.json` | VALID | Mode B draft with signed `quantity_millis=-250`; zero-valued line/summary amounts keep the example self-consistent without adding an accounting rule. |
| `goldens/valid/issued_mode_a.json` | VALID | Mode A issued record, ISSUE-time display number, native provenance, correct issued-content hash. |
| `goldens/valid/revoked_mode_b_retains_issue_hash.json` | VALID | Mode B revoked terminal record; display number and issued-content hash persist after ISSUE. |
| `goldens/invalid/issued_hash_mismatch.json` | INVALID — `ISSUED_CONTENT_HASH_MISMATCH` | Structurally valid ISSUED instance with an incorrect SHA-256; mirrors the C# CLOUD-007 hash-mismatch rejection path. |
| `goldens/invalid/display_number_before_issue.json` | INVALID — `DISPLAY_NUMBER_BEFORE_ISSUE` | Rejects pre-ISSUE display-number allocation. |
| `goldens/invalid/quantity_millis_string.json` | INVALID — `QUANTITY_MILLIS_NOT_INTEGER` | Rejects a decimal quantity encoded as a string instead of a JSON integer. |

All values are synthetic and fixed; there is no customer, sale, stock movement,
or live identifier data. The hash-mismatch golden is deliberately invalid and
must not be normalized or repaired by the consumer.

## Verification

Run the E-11 publication and E-01 regression tests from the repository root
with `jsonschema>=4.18,<5` and `pytest` installed:

```sh
PYTHONPATH=src python -m pytest -q \
  tests/test_e11_contract_package.py \
  src/image_extraction_adapter/tests/test_canonical_invoice_v0.py
```

The E-11 test checks schema self-containment/version, canonical byte stability,
manifest SHA-256 values, expected validation verdicts, signed quantity
encoding, display-number timing, and the issued-content hash rejection case.
The existing E-01 tests are retained and run unchanged.
