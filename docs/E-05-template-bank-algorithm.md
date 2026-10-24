# E-05 — Invoice Template Bank Algorithm

## 1. Purpose, scope, and safety boundary

E-05 turns the four operator-confirmed E-07 label records (invoice IDs 29, 31,
32, and 33) into one reusable **layout and numeric-format template**. The
training values are checked against the synthesized Canonical Invoice v0
fixtures under `tests/fixtures/real/canonical/` and the spatial labels in
`tests/fixtures/real/labels.json`.

The bank is an advisory matcher. It does not read pixels, run OCR, synthesize
producer context, calculate or repair invoice amounts, change Canonical Invoice
state, or route a production invoice to AUTO. The caller supplies a
`LayoutObservation` produced by the existing layout/OCR components. A high
layout confidence is not invoice acceptance, financial validation, or a claim
of general accuracy. See the provenance limits in section 9 and ASM-34 in
`docs/DECISIONS.md`.

## 2. Learned template structure

The four source images share one column layout. Horizontal coordinates and
anchors are divided by image width, so the template is scale-relative:

| Learned region | Approximate normalized x interval | Meaning |
| --- | ---: | --- |
| `line.total` | 0.2014–0.4236 | Printed line total / amount |
| `line.quantity` | 0.4236–0.5087 | Printed integer quantity |
| `line.description` | 0.5087–0.8455 | Description cell; not transcribed by E-05 |
| `line.sequence` | 0.8455–0.9149 | Sequence/number cell; retained as geometry only |
| `invoice.payable` | Learned from each payable bbox | Separate payable amount below the final row |

The right-to-left cell mapping follows `preprocessing.crop_spatial_cells()`:

total → quantity → description → sequence.

The row profile stores the median row height and pitch, row-height variation,
first-row top anchor, observed row-count envelope, and payable-to-last-row gap.
The four observed row counts are 4, 3, 5, and 13; the bank therefore records a
supported range of 3–13 and the exact known counts. Row field y positions
include the existing crop's 8-pixel top and 3-pixel bottom insets, expressed as
fractions of a row band. The payable bbox remains in image-width units. The
unit-price column is not present in this layout and is not learned; in these
fixtures `unit_price` is an exact derived value from `line_total / quantity`.

The raw numeric formatting profile learns all Persian digits `۰`–`۹`, comma as
the amount thousands separator, groups of three, and ungrouped quantity text.
The template stores the field geometry, source IDs, known row counts, supported
row-count range, normalized anchors, digit alphabet, separator, and group size.
It does not memorize exact line totals or payables.

## 3. Training and bank construction

`build_template_bank(canonical_dir, labels_path)` performs these steps:

1. Load `synthesis-manifest.json` and require the sidecar marker
   `synthesized_from_labels: true` for every listed invoice. The marker is not
   injected into Canonical JSON because the v0 schema is strict.
2. Load `labels.json`; require its status to be `OPERATOR_CONFIRMED` and map
   labels by source ID.
3. Load each Canonical Invoice fixture and run the existing v0 schema and
   semantic validator. Require integer v0 `quantity` (never C#
   `quantity_millis`), the same number of rows as the labels, exact quantity
   and line-total agreement, exact-integer unit-price derivation, and a payable
   and subtotal that agree with the label values.
4. Verify the source-image SHA-256 against both the manifest and the Canonical
   provenance metadata. Images are read only to verify their hashes; no image
   decoding or OCR is performed here.
5. Convert label geometry into `LayoutObservation` values. Cluster observations
   when their normalized column boundaries, row height, table top, and payable
   gap are within the implementation's layout-cluster tolerances. Row count is
   allowed to vary within a cluster. These four observations form one cluster.
6. Aggregate the cluster into a `LayoutTemplate`. `TemplateBank.to_dict()` and
   `save_template_bank()` provide a stable JSON serialization for reuse;
   `load_template_bank()` restores it.

Any missing marker, label, canonical file, image, synthetic-context declaration,
or source-image hash agreement, as well as any invalid schema object, numeric
disagreement, or geometry, fails the build rather than silently training on
incomplete data.

## 4. Matching a new observation

The matching API accepts a `LayoutObservation` containing image dimensions,
five detected column boundaries, ordered row bands, a payable bounding box,
and optional raw numeric OCR strings. The caller is responsible for obtaining
those observations; this package does not call `detect_layout_safe()`, perform
OCR, or open an image. Integration can adapt the existing E-02 layout result to
this input without changing the detector.

For each candidate template, the matcher computes normalized column, row-count,
row-rhythm, table-top, payable-anchor, and (when supplied) numeric-format
scores. Exact invoice amounts, quantities, and prices are not compared against
the training invoices. Raw numeric text is checked for the learned glyph
alphabet and grouping style only. If numeric values are omitted, a geometry-only
match is possible and the result explicitly reports that numeric formatting was
not evaluated. If values are supplied but are malformed or lack a quantity,
line-total, or payable witness, the candidate is not matched.

The best-scoring template is returned as `TemplateMatch`, including its score,
component scores, matched flag, source IDs, and reasons. The matching call does
not mutate the observation or bank.

## 5. Confidence formula and fail-closed criteria

Each component is bounded to `[0, 1]`; geometric scores fall linearly with
distance to their documented tolerance and clamp at zero. The default weighted
score is:

```text
C = 0.24 columns
  + 0.18 row_count
  + 0.18 row_rhythm
  + 0.11 table_anchor
  + 0.11 payable_anchor
  + 0.18 numeric_format
```

The sum is divided by the active component weights. If the caller supplies no
numeric values, the numeric-format weight is omitted and the result is explicitly
geometry-only. Row rhythm averages row-height, row-pitch, and row-height
coefficient-of-variation similarity. Payable-anchor similarity averages the
gap, left position, width, and height comparisons. Numeric-format validation
requires the learned digit glyphs, ungrouped quantities, and grouped amounts.

The default match threshold is **0.85**. In addition, matching fails closed if
the row count is outside the learned 3–13 range, column geometry has zero
similarity, or supplied numeric evidence is incomplete/invalid. These values
are initial implementation assumptions, not calibrated production thresholds.
The bank cannot promote the caller's invoice state or issue an invoice.

## 6. Verification and test plan

Focused tests live in `src/e05_template_bank/tests/test_template_bank.py` and
run with:

```bash
python -m pytest src/e05_template_bank/tests/
```

The test suite verifies all four Canonical objects against the existing v0
validator; sidecar provenance markers and source-to-canonical numeric equality;
one-cluster construction; learned columns, digits, and grouping; high-confidence
matches for each training fixture; geometry rejection; unknown-script rejection;
out-of-range row-count rejection; matching of new amounts with the same format;
geometry-only evidence disclosure; and bank serialization round-trip.

On the recorded fixture self-match run, scores were 0.998544 (29), 0.995653
(31), 0.997350 (32), and 0.971928 (33). Invoice 33's wider payable bbox lowers
its anchor component, but the match remains above the threshold. These are
**resubstitution scores on the four training observations**, not an independent
accuracy result or a generalization estimate. A production evaluation must use
separate invoices not present in the bank.

## 7. Relationship to E-03-kit-v2 capture evidence and E-02

The earlier E-03-kit-v1 plan for six phone-scanned pages is obsolete; its
archived documents must not be printed or used. The active E-03-kit-v2 evidence
set is four fabricated Hello pages (three learning and one exam), each printed
from the actual Hello Windows application and captured by KandooPrintProbe as
SPL, converted to PNG, and accompanied by `Report.txt`. No v2 Windows print
job has been captured or verified in Arena. These four v2 captures, when
provided by the owner, are a separate future evidence set; do not count or
recreate the obsolete v1 phone scans. Run the existing local E-02 pipeline on
the v2 PNGs with explicitly synthetic test context, preserve its
AUTO/REVIEW/REJECT result, and compare output with the v2 expected values. Keep
those outputs separate from these label-derived Canonical fixtures. Do not
treat synthetic identifiers, phone, product names, or fixture lifecycle state
as caller context.

New observations may be scored against the bank as layout evidence, but the
score cannot bypass E-02's numeric-cell and arithmetic gates, Canonical
validation, or human review. Operator corrections must not silently retrain or
rewrite the bank. Any calibration or bank update needs its own held-out
validation and authorization.

## 8. Open questions and follow-up

- Calibrate the 0.85 threshold using independent, owner-authorized scans and
  measure false matches as well as missed matches; do not tune on the four
  training fixtures alone.
- Decide whether layouts outside the current 3–13 row envelope should be
  matched as REVIEW candidates or require a new template cluster.
- Evaluate changes in print scale, crop margins, image rotation, compression,
  store/model variants, column shifts, and payable placement before widening
  the compatibility tolerances.
- Confirm how to handle amount glyphs or separators not represented in the
  learned alphabet; the current numeric-format component fails closed on an
  unseen script or separator.
- Product names, phone data, and other producer context remain outside this
  bank. They need genuine caller-supplied context; the template does not infer
  them.
- Decide whether future bank updates should be manually reviewed snapshots,
  versioned per store, or built from a broader authorized training set. The
  current code only builds and serializes an explicit caller-requested bank.

## 9. Provenance, lifecycle, and limits

`tests/fixtures/real/canonical/README.md` and `synthesis-manifest.json` explain
that the four Canonical objects are synthesized from operator-confirmed labels
and are not E-02 pipeline output. Required context absent from labels follows
the synthetic example in `docs/cli-contract.md`; it is explicitly identified
as synthetic. Phone and product-name placeholders are `untrusted` and remain in
`attention_cells`. The strict v0 Canonical JSON itself contains no extra
synthesis property.

Invoices 29, 31, and 32 are represented with Canonical fixture state
`EXTRACTED`, reflecting their E-07 `AUTO_CANDIDATE` routing context; this does
not assert that E-02 emitted the objects. Invoice 33 is included as `DRAFT`
because its E-07 result was `REVIEW`; Canonical v0 has no `REVIEW` lifecycle
state. No fixture is `VALIDATED` or `ISSUED`, and none may be used for a live
sale or as independent model evaluation. Exact integer quantity is retained;
`quantity_millis` is out of scope. Related assumptions are recorded as ASM-30
through ASM-34 in `docs/DECISIONS.md`.
