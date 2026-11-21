# E-06 — Store Onboarding Verdict

## 1. Overview

E-06 is a fail-closed decision layer for invoices processed during a new store's
onboarding and after its template bank is locked. It runs **after E-05 has
matched a supplied layout observation** and after E-02 has assembled a candidate
Canonical Invoice. E-06 does not perform OCR, change invoice values, train a
bank, or issue an invoice.

Inputs are the E-05 `TemplateMatch` and component scores, extraction confidence,
raw numeric text attached to the layout observation, the candidate Canonical
Invoice, the v0 structural/semantic validation result, store onboarding count,
bank-lock state, D14 signed-agreement evidence, and (for acceptance) an audited
store-owner verification. An explicitly declared incomplete field list is
reviewed before Canonical validation; a complete but invalid Canonical object
is rejected.

Output is `ACCEPT`, `REVIEW`, or `REJECT` plus one or more stable machine-readable
reason codes. The E-05 bank must also contain the explicit onboarding
`currency_unit` (`rial` or `toman`). A missing or unsupported value keeps a
candidate in REVIEW; E-06 never guesses a unit or converts an amount. The result
is advisory and non-mutating. **ACCEPT is never based on template score alone**:
the owner-verification record is required because the available E-05 scores are
training-set resubstitution and OCR confidence is not a proof of correctness.

## 2. Decision thresholds

The default thresholds are configurable in `src/e06_onboarding_verdict/thresholds.py`:

| Effective confidence | Base result | Meaning |
| ---: | --- | --- |
| `>= 0.95` | Eligible to continue through the hard gates; not an automatic ACCEPT | Strongest band, chosen conservatively given E-05's resubstitution-only evidence. |
| `0.80` to `< 0.95` | `REVIEW` | Plausible but insufficiently supported; a human must resolve it. |
| `< 0.80` | `REJECT` with `NO_MATCH` | Evidence is too weak to use this layout/extraction for onboarding. |

The effective confidence is the **minimum**, not an average, of the E-05 match
score, extraction confidence, and required E-05 layout-component scores. A strong
signal cannot compensate for a weak one. Missing confidence, a missing template,
or an explicitly partial candidate is not converted to zero; it returns
`REVIEW`, since absence of evidence is not proof that an invoice is wrong.

The 0.95 accept-eligibility threshold is intentionally above E-05's default
0.85 match threshold. In addition, threshold passage is insufficient without
valid structure, exact numeric checks, the onboarding and D14 gates, no
unresolved attention data, a locked bank, and the complete owner-verification
audit described below. These cutoffs are conservative starting assumptions,
not statistically calibrated production error rates.

## 3. Multi-signal decision (defense in depth)

E-06 consumes E-05's scoring rather than recomputing geometry. It evaluates all
available gates and never silently repairs or normalizes an input. Before a
candidate can become eligible for acceptance, the bank's `currency_unit` must
be exactly `rial` or `toman`; old banks without the field and banks with invalid
values remain reviewable but cannot pass this gate. No numeric values are
scaled, multiplied, or otherwise converted.

1. **Template match:** use E-05's best `TemplateMatch`, score, matched flag, and
   `component_scores`. A score below 0.80 is `REJECT/NO_MATCH`; a score from
   0.80 to below 0.95 cannot be accepted.
2. **Layout similarity:** use E-05's `columns`, `row_rhythm`, `table_anchor`,
   and `payable_anchor` components. The weakest required layout component
   participates in the effective minimum. A new or ambiguous layout is REVIEW
   unless the score is below the reject threshold.
3. **Canonical structure:** run `validate_canonical_invoice()` on complete
   objects. A schema/semantic failure is `REJECT/SCHEMA_INVALID`. An extraction
   explicitly reported as partial is `REVIEW/PARTIAL_MATCH`, not mislabeled as
   a corrupted complete invoice. A `DRAFT` object is not acceptance-ready.
4. **Numeric consistency:** require integer quantities, exact correspondence
   between the raw Persian numeric strings and the Canonical quantity/total/
   payable values, `unit_price * quantity == line_total`,
   `sum(line_total) == summary.subtotal`, and
   `summary.subtotal == summary.payable`. Non-zero extra amounts, tax/discount
   lines, or rounding are unsupported and keep the candidate in
   `REVIEW/ACCOUNTING_ADJUSTMENT_UNSUPPORTED`; E-06 does not infer their
   semantics. A known disagreement with the required arithmetic or raw values is
   `REJECT/NUMS_INCONSISTENT`; unreadable or missing raw numeric text is REVIEW.
   E-06 never repairs totals.
5. **Kit digit coverage:** for E-03 known-answer onboarding-kit invoices, count
   the literal Persian digits `۲` and `۶` in the raw numeric-cell text. Each
   must occur at least five times in each kit invoice, matching the approved
   kit specification. Missing coverage is REVIEW, not an arithmetic correction
   or an ordinary-production invoice rejection. This is a kit-qualification
   witness, not a requirement that every later customer invoice contain those
   digits.
6. **Confidence and provenance:** both extraction and E-05/layout evidence must
   reach the confidence band. Any unresolved `attention_cells`, required
   `untrusted`/`unavailable` value, or incomplete evidence keeps the result in
   REVIEW.
7. **Onboarding and legal gates:** all first four onboarding invoices are
   REVIEW. After those four, the store's bank must be explicitly locked and the
   D14 signed-agreement gate must be confirmed. Missing either keeps REVIEW.
8. **Owner verification:** only a complete, audited store-owner review of the
   required invoice fields can move an otherwise fully eligible post-onboarding
   invoice from REVIEW to ACCEPT. The module checks the audit record's shape
   and field coverage; authentication, signature verification, and durable
   audit storage belong to the caller. Without this confirmation the automatic
   result remains REVIEW. This is the conservative control against false
   positives while OCR accuracy is uncalibrated.

Thus no single signal or confidence average can produce ACCEPT. Structural or
known numeric corruption is rejected; uncertain, incomplete, novel, or
unverified data are held for review.

## 4. Onboarding flow — first N invoices

Use **N = 4**, matching the four-document E-03 onboarding kit. The caller passes
`processed_invoice_count`, the number of already reviewed onboarding invoices
before the current candidate.

- For counts 0–3, each onboarding/kit candidate is held in REVIEW, even if a
  retrospective E-05 match is high. A clearly invalid complete object or known
  numeric corruption still REJECTS; the warm-up rule never masks a hard failure.
  No automatic acceptance or online template update occurs during this phase.
  The owner/operator reviews the known-answer kit and records confirmed values.
- After four invoices have been processed, the onboarding workflow may lock an
  immutable per-store template-bank snapshot, including the explicitly selected
  currency unit. `processed_invoice_count >= 4` alone is not evidence that the
  bank is locked; the caller must set the explicit locked state after its review
  procedure succeeds.
- Subsequent invoices are evaluated against that locked bank. A changed or
  unlocked bank returns REVIEW; E-06 never silently learns from a production
  invoice. Even after N, score thresholds do not bypass the D14 gate or the
  per-invoice owner-verification requirement for ACCEPT.

**D14 legal gate:** the caller must attest that the store agreement was accepted
with a digital signature. `docs/PROJECT_STATE.md` records legal status and
customer-facing wording as owner-controlled; the proposed wording requires
owner/lawyer approval. E-06 introduces no legal copy and defaults to REVIEW
when signed-agreement evidence is absent. A signature check must be supplied by
the agreement subsystem, not inferred from an invoice or template match.

## 5. Reason codes

Every result contains stable string codes (possibly several), plus diagnostic
details kept separate from the machine-readable codes. Review results include
all known onboarding blockers; hard failures are reported immediately and are
never hidden by a later passing signal.

| Verdict | Code | Fires when |
| --- | --- | --- |
| ACCEPT | `TEMPLATE_MATCH_HIGH` | E-05 aggregate template-match score is at least 0.95. |
| ACCEPT | `STRUCTURE_VALID` | Canonical v0 schema and semantic validation pass. |
| ACCEPT | `NUMS_CONSISTENT` | Raw numeric strings match canonical integers and arithmetic reconciles. |
| ACCEPT | `EXTRACTION_CONFIDENCE_HIGH` | Extraction confidence is at least 0.95. |
| ACCEPT | `LAYOUT_SIMILARITY_HIGH` | Required E-05 layout components meet the accept band. |
| ACCEPT | `DIGIT_COVERAGE_VALID` | The E-03 kit coverage check passes when applicable. |
| ACCEPT | `ONBOARDING_COMPLETE` | Four onboarding invoices have already been processed. |
| ACCEPT | `TEMPLATE_BANK_LOCKED` | The caller confirms the per-store bank is locked. |
| ACCEPT | `D14_AGREEMENT_SIGNED` | The signed agreement gate is confirmed by its authority. |
| ACCEPT | `OWNER_VERIFICATION_AUDITED` | A store-owner audit verifies every required field for this invoice. |
| REVIEW | `LOW_CONFIDENCE` | Effective confidence is from 0.80 to below 0.95, or a confidence value is missing. |
| REVIEW | `ACCOUNTING_ADJUSTMENT_UNSUPPORTED` | Non-zero extra/tax/discount/rounding data needs accounting semantics E-06 does not model. |
| REVIEW | `CURRENCY_UNIT_UNCONFIRMED` | The bank's `currency_unit` is missing or not exactly `rial`/`toman`; no guess or conversion is made. |
| REVIEW | `PARTIAL_MATCH` | Candidate/observations are incomplete or a declared extraction field is missing. |
| REVIEW | `NEW_LAYOUT` | No usable template is present, or the candidate appears to use an unfamiliar layout. |
| REVIEW | `MULTI_TEMPLATE_AMBIGUOUS` | The top two E-05 template scores differ by less than the configured ambiguity margin. |
| REVIEW | `SELF_MATCH_RESUBSTITUTION` | The observation is one of the bank's own training sources, so its score cannot qualify onboarding acceptance. |
| REVIEW | `ONBOARDING_WARMUP` | The current invoice is among the first four. |
| REVIEW | `TEMPLATE_BANK_UNLOCKED` | The onboarding count is complete but the bank is not locked. |
| REVIEW | `D14_AGREEMENT_REQUIRED` | Signed-agreement evidence is missing or false. |
| REVIEW | `DIGIT_COVERAGE_INSUFFICIENT` | A required E-03 kit invoice has fewer than five `۲`s or `۶`s. |
| REVIEW | `ATTENTION_REQUIRED` | Unresolved attention or untrusted required values remain. |
| REVIEW | `CANONICAL_STATE_NOT_READY` | The candidate is still DRAFT or otherwise not EXTRACTED. |
| REVIEW | `OWNER_VERIFICATION_REQUIRED` | All automated gates pass but the required audited owner check is absent. |
| REVIEW/REJECT | `MANUAL_OVERRIDE_BLOCKED` | An override attempts to bypass a hard gate or promote an ineligible result. |
| REVIEW/REJECT | `MANUAL_OVERRIDE_INVALID` | Override audit fields are missing or malformed. |
| REVIEW | `MANUAL_OVERRIDE_APPLIED` | A valid owner override recorded a review action. |
| REJECT | `MANUAL_OWNER_REJECTED` | The store owner explicitly rejected a candidate and the action was audited. |
| REJECT | `SCHEMA_INVALID` | A complete candidate fails Canonical v0 structural/semantic validation. |
| REJECT | `NUMS_INCONSISTENT` | Parsed raw numeric evidence disagrees with canonical values or arithmetic. |
| REJECT | `NO_MATCH` | E-05 match, required layout, or extraction confidence is below 0.80. |

A first invoice with no bank is REVIEW (`NEW_LAYOUT`), not REJECT: there is no
basis to call it wrong. A missing declared field is REVIEW; a complete object
that violates the contract is REJECT. The distinction is deliberate.

## 6. Relationship to E-05

E-05 remains the sole layout matcher. E-06 imports `TemplateBank`,
`LayoutObservation`, `TemplateMatch`, `match_observation()`, and E-05's
`score_bank()` for mixed-template ambiguity checks. It reads the returned
`confidence_score`, `matched`, `template_id`, and `component_scores`; it does
not implement another column, row, payable, or digit-format matcher. If the E-05
API or component shape is unavailable, E-06 must fail closed to REVIEW rather
than substitute a local matcher.

E-05's default match threshold is 0.85; E-06's 0.95 acceptance-eligibility
threshold is stricter. The E-05 scores for invoices 29/31/32/33 (0.998544,
0.995653, 0.997350, 0.971928) are resubstitution scores on the bank's own
training fixtures. They are not independent validation. Production scores are
expected to be lower; high self-match scores do not waive the four-invoice
warm-up, numeric evidence, legal gate, or owner verification.

## 7. Edge cases

- **First invoice / no template:** always REVIEW with `NEW_LAYOUT`; no score is
  fabricated and no empty bank is treated as a zero-confidence rejection.
- **Missing/invalid currency unit:** REVIEW with
  `CURRENCY_UNIT_UNCONFIRMED`, even when all layout and amount checks pass. Do
  not guess rial/toman from digits, labels, or magnitudes, and do not convert.
- **Mixed templates:** use E-05 `score_bank()`; if the top two results are
  separated by less than the configured margin, REVIEW with
  `MULTI_TEMPLATE_AMBIGUOUS`. Do not guess a template or update the bank.
- **Bank open versus locked:** first-four learning mode is REVIEW-only. After
  N=4, an unlocked bank still returns REVIEW. Only an explicitly locked
  snapshot is evaluated for later invoices.
- **Manual owner override:** a valid, timestamped audit may downgrade an
  ACCEPT to REVIEW/REJECT. Promotion from REVIEW to ACCEPT is allowed only when
  every machine gate already passes, onboarding is complete, D14 is signed,
  and the owner verification explicitly covers every required field. An owner
  cannot override a schema failure, numeric disagreement, below-0.80 score, or
  first-four warm-up. The caller remains responsible for authenticating the
  owner and persisting the audit record.

## 8. Open questions for E-08

- When a genuinely new invoice type appears, should it start a new per-store
  template cluster, or remain REVIEW until an authorized onboarding batch is
  completed?
- How are bank snapshots reviewed, versioned, rolled back, and retired? The
  current policy forbids online adaptation; E-08 must define a controlled
  template-evolution path.
- When should repeated REVIEW outcomes, low scores, or ambiguous templates
  escalate to store support, and what evidence must be attached?
- What independent sample size and error-rate bound are sufficient to revisit
  the 0.95/0.80 thresholds or the manual-verification requirement?
- Who verifies D14 signature authority and the signed agreement's current
  version? E-06 only receives the caller's boolean attestation.
- Should digit-2/digit-6 coverage remain limited to E-03 kit qualification, or
  should a future owner-approved calibration protocol replace it for production
  invoices? Do not generalize the kit-only counts without that decision.
