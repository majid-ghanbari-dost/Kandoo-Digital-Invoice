# Image Extraction Pipeline v0 (E-02)

## Purpose and boundary

`src/image_extraction_adapter/pipeline_v0.py` is a new, local image pipeline
that is separate from the existing flat-text adapter. It combines:

1. safe projection-based table layout detection;
2. Glyph numeric-cell recognition for row quantity, row total, and invoice
   payable;
3. the existing arithmetic gate (`sum(line totals) + extra_amounts == payable`);
4. product-description crop fingerprints and fixed-threshold dHash clusters;
5. image/template provenance, operator-attention cells, and optional
   Canonical Invoice v0 assembly.

The module does not call the flat-text parser, Tesseract, an issuance API, or a
network service. Image reads are local. Runtime results retain a SHA-256 and
crop metadata, not image bytes. The existing frozen `adapter.py`,
`preprocessing.py`, `glyph_classifier.py`, `canonical_invoice.py`,
schema, and `src/templates.json` are not changed by E-02.

Routing statuses (`AUTO_CANDIDATE`, `REVIEW`, and `REJECT`) are pipeline
outcomes, not Canonical Invoice lifecycle states. An `AUTO_CANDIDATE` is not
validated or issued.

## Runtime flow

`extract_pipeline_v0(image, templates_path=..., captured_at=...,
canonical_context=..., evaluation=False)` performs these steps:

1. Load the Glyph bank and compute its SHA-256 identity.
2. If `evaluation=True`, refuse before image OCR when the input matches a
   template source by path or SHA-256. The guard also resolves the known legacy
   `glyph-classifier-build-13-rows03-08.png` crop to its sibling full source
   `13.png`; see [template provenance check](templates-provenance-check.md).
3. Read the local image, calculate its SHA-256, and call
   `detect_layout_safe()`. `BLOCKED` maps to `REJECT`; incomplete/uncertain
   layout maps to `REVIEW` with a `layout_uncertain` reason. No OCR is run for
   those outcomes.
4. Locate payable from the detected geometry. The search starts below the last
   table row, excludes the short divider below the table, groups connected
   components by a row-height-scaled horizontal gap, and accepts only a clearly
   widest, un-clipped text group. The search region is relative to detected
   columns and median row height; it does not read labels or use fixed page
   coordinates. Ambiguous/missing payable geometry stays missing, causing the
   existing gate to fail closed.
5. Call `GlyphClassifierOCR.recognize_spatial_cells()` with its normal gate
   enabled, then explicitly rerun `apply_arithmetic_gate()` to retain a gate
   report with the result. The existing Glyph classifier defaults are
   unchanged: minimum confidence 60, distance 0.25, margin 0.15, and the
   existing glyph-width check. `extra_amounts=0` is used for these fixtures;
   this must not be applied to receipts with unmodelled VAT/levies.
6. Crop descriptions with `crop_spatial_cells()` and reuse the existing
   offline T3 normalization/dHash/Hamming helpers. Hamming threshold is fixed
   at 1 from the earlier name-cluster report; no threshold sweep or OCR-name
   transcription runs in this pipeline. Each crop emits a `name_cluster_id`
   sidecar value.
7. Return attention evidence for every non-EXTRACTED numeric cell, `?`, missing
   payable region, or failed description crop. No value is repaired or promoted
   by the arithmetic gate; that gate only downgrades.

### Integer-Rial handling

The new module defines a small local `to_rials()` equivalent rather than
importing the legacy adapter (which also imports the flat-text parser). It
accepts Persian digits and grouping commas and returns an integer. Decimal
fractions, signs, malformed amount formats, and other characters return
`None`; no rounding, truncation, or toman/rial guessing occurs. The arithmetic
gate's strict amount parser remains the final numeric-format check.

### Status map

| Condition | Pipeline status | Behavior |
|---|---|---|
| Layout is `BLOCKED`, local image cannot be read, or Glyph cannot run | `REJECT` | Stop; do not issue or create an invoice lifecycle transition. |
| Layout is uncertain, any cell is `REVIEW`, any `?` appears, dHash crop coverage fails, payable is missing, or the arithmetic gate fails | `REVIEW` | Preserve raw values/reasons and attention cells. |
| Every emitted numeric cell is `EXTRACTED`, description crops are fingerprinted, and the arithmetic gate passes | `AUTO_CANDIDATE` | Extraction candidate only; it is not a Canonical Invoice validation or issuance decision. |

## Description clusters and the frozen v0 schema

The dHash output identifies visual clusters; it does not produce human-readable
product names or a product-master match. Cluster data is returned in the
pipeline result's `description_clusters` sidecar. Canonical Invoice v0 has
`additionalProperties: false`, requires `line_items[].product_name`, and has no
`name_cluster_id` field. E-02 therefore does not alter the frozen schema and
does not put a hash token into `product_name`.

To assemble a Canonical Invoice candidate, the caller must supply an explicit
`canonical_context` containing the mode, platform identifiers, public token,
customer information and one human-readable product name plus v0 provenance
label per detected row. E-02 does not generate identifiers/tokens, infer a
customer phone/status, or invent product names. Without that context,
`canonical_invoice` is `null` and `canonical_blockers` explain what is missing.

With complete context and exact integer-Rial values, the pipeline constructs a
v0 invoice in state `EXTRACTED` and runs `validate_canonical_invoice()`.
Quantities/totals/payable retain `captured` provenance when extracted; uncertain
values are `untrusted`; `unit_price` is derived only when integer division is
exact. If a price would require rounding, no canonical candidate is emitted.
`captured_at`, when supplied, must be ISO 8601 with a UTC offset and is marked
`derived`. Printed date/time/number are left `null` and `unavailable`. No
transition to `VALIDATED` or `ISSUED` is implemented.

## Operator corrections

`apply_operator_correction(result, corrections)` accepts only emitted quantity,
total, or payable fields. Corrections must be strict integer quantities or
integer-Rial values. Each accepted correction appears in
`operator_confirmed_fields` and `operator_confirmed_values`; the original OCR
text is retained in `operator_original_values`, and confidence is cleared
because the prior classifier confidence does not describe a human correction.
The arithmetic gate is rerun over the corrected result.

The frozen v0 provenance enum does not contain `operator_confirmed`, so the
operator-confirmation marker remains adapter-local metadata. Corrections are
never written to a Glyph bank by this function. `bank_update_eligible` is true
only when every supplied correction is valid and the rerun gate passes; this
is not an automatic bank update. A failed gate leaves the result in REVIEW and
not eligible.

## Default template bank

Run from the repository root:

```sh
PYTHONPATH=src /tmp/kandoo-t2-venv/bin/python scripts/build_default_template_bank.py
```

The builder creates `src/templates_bank_default.json` from all four local,
operator-confirmed fixture images. It records relative image paths, full-image
SHA-256 hashes and the fields trained per source. Invoice #31's payable label
is `DERIVED_FROM_ARITHMETIC`; that payable is excluded from glyph training and
is not represented as an independent visual label. All four images still
appear in bank provenance because each contributes other numeric cells.

The default bank is not a leave-one-out test bank. `evaluation=True` refuses
any of its four source images by source path or hash. LOO builds an in-memory
bank from the other three images for each held-out fixture. Do not use the
all-four default bank to claim performance on these four images.

## Four-fold leave-one-invoice-out result

The experiment used the pipeline's automatic layout/payable locator and a fresh
three-image template set for each fold. No per-fold bank includes the held-out
fixture. Glyph confidence/distance/margin thresholds were not changed. The
comparison counts an EXTRACTED value as wrong only when it disagrees with an
independent operator-confirmed label; #31 payable is excluded because its label
was derived from arithmetic. Canonical context was deliberately omitted from
the experiment, so no fold created an invoice record.

| Held-out invoice | Numeric cells | EXTRACTED | REVIEW | Gate | Independent EXTRACTED label comparisons | EXTRACTED-but-wrong | Outcome |
|---:|---:|---:|---:|---|---:|---:|---|
| 29 | 9 | 9 | 0 | Pass | 9 | 0 | AUTO_CANDIDATE |
| 31 | 7 | 7 | 0 | Pass | 6 | 0 | AUTO_CANDIDATE; payable label excluded from independent comparison |
| 32 | 11 | 11 | 0 | Pass | 11 | 0 | AUTO_CANDIDATE |
| 33 | 27 | 9 | 18 | Fail: `line.3.total` contains `?` | 9 | 0 | REVIEW |
| **Total** | **54** | **36** | **18** | **3/4 pass** | **35** | **0** | **3 AUTO_CANDIDATE, 1 REVIEW, 0 REJECT** |

The acceptance check found **zero EXTRACTED-but-wrong values** among the
independently compared fields. This is a result on four fixtures, not a
performance promise or generalization claim. The #31 payable value is not an
independent visual ground truth; it was correctly excluded from direct
comparison and payable glyph training, although the extracted value still
passed the arithmetic gate. Invoice #33 remains REVIEW because one malformed
line total prevents the arithmetic gate from passing; the gate downgrades amount
cells but never repairs them.

The dHash implementation keeps the prior fixed threshold 1. Existing tests
assert that the previously mapped repeated-description crops retain the same
cluster IDs; this is not new product-name transcription or product-master
accuracy evidence.

## Test commands and scope

Targeted pipeline tests:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /tmp/kandoo-t2-venv/bin/python -m unittest discover -s tests -p 'test_pipeline_v0.py' -v
```

Full suite:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /tmp/kandoo-t2-venv/bin/python -m pytest -q
```

Verification result: **1,784 passed, 0 failed, 0 skipped, 69 subtests**, with
422 deprecation warnings in 197.38 seconds. The warnings are from the frozen
preprocessing module's Pillow `Image.getdata()` use and an existing preprocessing
test; E-02 did not modify that file. The sandbox venv lacked pytest, so pytest
9.1.1 was installed only into `/tmp/kandoo-t2-venv`; no project dependency file
was changed. The suite includes local real-image layout and LOO tests. No
Tesseract executable, OCR network, or invoice upload is part of E-02. This
pipeline makes no claim about invoice persistence, restore, concurrency, DRAFT
idempotency, SEC-1 access control, second-factor recovery, SMS, or issuance.
