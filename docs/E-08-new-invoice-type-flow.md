# E-08 — New Invoice Type Flow

## 1. Overview

A **new invoice type** is a potentially valid invoice from an already-onboarded
store whose layout or observed field/numeric format is materially different
from every locked template in that store's E-05 bank. A changed paper size,
column arrangement, language/number alphabet, optional field set, or receipt
section may produce this condition. E-08 does not decide that a low score alone
proves a new type.

The flow is eligible only after the store has completed the initial E-06
onboarding (at least four owner-accepted invoices) and its per-store template
bank is locked. It triggers when E-05's best score is **below that bank's
configured match threshold** (0.85 by default). Inputs are the locked bank, an
E-05 `LayoutObservation` derived from the scan, the complete Canonical Invoice
v0 candidate, extraction confidence, store/onboarding context, and the current
append-only audit trail.

For a supported new type the output is `REVIEW` with E-06's `NEW_LAYOUT` reason,
a separate `PROPOSED` template candidate, an appended detection event, and an
escalation flag if the unresolved-detection threshold is met. A known structural
or numeric hard failure remains `REJECT` and creates no candidate. E-08 never
modifies the production bank, silently changes an invoice, or issues one.

## 2. Detection — new type versus corrupted invoice

E-08 calls E-05 `score_bank()` for all templates and records every score. It
uses the bank's configured threshold and does not implement a second layout
matcher. The **low-score signal is only a type-change hypothesis**; it is not
sufficient by itself to create a candidate.

A candidate may be proposed only when all of the following are true:

1. The store has at least four previously owner-accepted onboarding invoices
   and the current per-store bank is locked.
2. The best E-05 score is below the bank threshold.
3. E-06 validates the complete Canonical v0 object, its internal numeric
   arithmetic (`unit_price × quantity`, line totals, subtotal, and payable), and
   any observed raw-value disagreements. E-06 remains the sole numeric verdict
   authority.
4. The raw quantity, line-total, and payable observation fields are present and
   parseable using E-05's existing labeled-integer parser. Missing or unreadable
   evidence remains REVIEW; E-08 does not independently compare numeric values
   or rewrite the observation or Canonical Invoice.

A Canonical/schema failure or an E-06 `SCHEMA_INVALID` / `NUMS_INCONSISTENT`
result identifies a **corrupted or invalid invoice**, not a new type: return
`REJECT`, do not create a candidate, and audit the event. A low score with
missing/unreadable raw numeric evidence is uncertain: return `REVIEW`, create no
candidate, and preserve E-06's reason codes. E-06's `NO_MATCH` alone is not
called corruption; for a structurally and numerically sound low-score invoice,
E-08 asks E-06 for the no-template `REVIEW/NEW_LAYOUT` outcome rather than
letting the old-template threshold reject a possible new type. E-06 remains the
verdict authority. A missing or incompatible E-05/E-06 API fails closed to
`REVIEW` with no candidate.

This separation prevents a damaged total or malformed object from being
re-labelled as a new template, while avoiding a false REJECT for a valid layout
that is simply not represented in the existing bank.

## 3. Default verdict and human review

The default verdict for a detected new type is **REVIEW**, never ACCEPT or
REJECT solely because the layout score is low. A new type may be valid, but no
approved template exists yet. The E-06 `NEW_LAYOUT` reason is retained along with integrity and gate reasons.
E-08 translates only the old-bank `NO_MATCH` into the new-type REVIEW; it drops
`PARTIAL_MATCH` only after E-06 reports no raw numeric disagreement and E-05's
parser confirms all required raw values are present and readable. Missing
evidence and all unrelated blockers remain REVIEW.

A store owner or authorized support reviewer must inspect the invoice and the
candidate before approving or rejecting the candidate. Candidate approval is
not invoice acceptance and does not bypass E-06 numeric, D14, provenance, or
owner-verification gates. Unreadable data, unsupported accounting adjustments,
or unresolved errors remain REVIEW. No automatic correction, online template
learning, or production-bank mutation is permitted.

## 4. Template candidate creation and lifecycle

A qualifying new type produces a **candidate**, not a production template. The
candidate is kept in a store-scoped candidate registry separate from the
immutable production `TemplateBank`. It records:

- a deterministic candidate ID derived from the store and normalized layout
  signature;
- normalized page/column/row/payable geometry and generic column field
  positions (semantic mapping remains subject to human review);
- observed numeric glyphs, separators, and grouping descriptors, not raw
  customer data or image pixels;
- the source invoice reference, proposal timestamp, and current lifecycle state.

The lifecycle is strictly:

```text
PROPOSED → REVIEWED → ACCEPTED
                    ↘ REJECTED
```

The detector creates the candidate in `PROPOSED`. A human review action must
supply reviewer identity, timestamp, and reason to move it to `REVIEWED`; only a
reviewed candidate can be accepted or rejected. Direct `PROPOSED → ACCEPTED` or
`PROPOSED → REJECTED` transitions are invalid. A rejected candidate is never
reused as a production template. An accepted candidate starts the separate
four-invoice mini-onboarding cycle; it is still not inserted into the bank at
that point.

## 5. Mini-onboarding for an accepted new type

Each human-accepted candidate starts **N = 4** mini-onboarding invoices of that
type. This preserves the E-06 sample-size policy despite the store's earlier
onboarding: confidence from the original layout does not validate a different
layout. All four new-type invoices remain `REVIEW`; each must be individually
checked and recorded with an owner/support reviewer, timestamp, and verified
field coverage. Only an E-08 `REVIEW` result derived from E-05/E-06, with an
E-05 match plus positive E-06 structure/numeric-integrity reasons and no
unresolved hard gates, may count.
Duplicate invoice IDs, missing audit data, non-REVIEW results, or invoices with
known hard failures do not count toward N.

After four distinct, reviewed invoices, the tracker reports `READY_TO_LOCK`.
The authorized caller must build and lock a versioned per-store E-05 snapshot
from approved evidence, then record its snapshot ID and locking reviewer. E-08
does not mutate or append to the live E-05 bank itself; snapshot creation,
versioning, durable persistence, rollback, and atomic bank replacement require
the caller's controlled E-05 integration. Until that explicit lock succeeds,
new-type invoices remain REVIEW.

## 6. Append-only audit trail

Every detection is appended, including new-type, corrupted, existing-type, and
indeterminate outcomes. The event records store ID, UTC detection timestamp,
invoice reference, scores against all current templates, candidate ID if one
was created or reused, final E-06 verdict and reason codes, reviewer identity
when present, and the candidate decision (ACCEPT/REJECT) when resolved.

The Python audit value object is immutable and hash-chained: a new event refers
to the previous event hash, and verification detects mutation, interior
removal/re-ordering, or duplicate event IDs relative to a known chain. Detecting
truncation or replacement of the stored tail requires an external hash anchor or
WORM-capable persistence. Candidate lifecycle, mini-onboarding, and resolution
events are appended rather than editing an earlier detection. Durable
append-only storage, access control, retention, and database transactionality
are caller responsibilities. D10 from the separate C# project is a conceptual
event-ledger reference only; no parent-repository code is used or copied.

## 7. Escalation

If **three distinct invoices** from one store are detected as new types within a
rolling 24-hour window and their candidate remains unresolved, E-08 sets
`support_escalation_required`. `REVIEWED` alone is not resolution; candidate
`ACCEPTED` or `REJECTED` is. The audit trail supplies the window and unresolved
status; timestamps must include a UTC offset.

This task only exposes the support-escalation flag and evidence. It does not
create a support ticket, notify staff, or call an external service. P-08/P-09/
P-10 integration remains a future C# scope; no network operations are added.

## 8. Open questions and conservative decisions

- **How many candidates may coexist per store?** ASM-45 permits one unresolved
  candidate per store. Repeated detections with the same signature reuse it;
  a different signature stays REVIEW and is audited without creating a second
  candidate until the first is accepted or rejected. No candidates are merged.
- **Could mini-onboarding use fewer than four invoices?** Not in E-08. ASM-43
  keeps N=4 until independent, owner-authorized evidence supports a separate
  decision; the original template's resubstitution scores do not justify a
  shorter cycle.
- **Two new types appear at once:** keep each invoice REVIEW, do not combine
  signatures, and queue the second type while the store's first candidate is
  unresolved. The audit trail records each event; the unresolved-count rule
  may escalate it.
- **A new type appears during initial onboarding:** E-08 does not run before
  four initial invoices have been owner-accepted and the bank locked. Route the
  invoice through E-06; keep it REVIEW and do not create a candidate. This
  prevents the new-type path from weakening E-06's warm-up gate.
- **Bank promotion and support tickets:** their persistent implementation,
  permissions, rollback, and failure recovery remain explicit integration
  work. E-08 only returns a ready-to-lock signal and a support placeholder.
