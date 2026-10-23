# Decisions and assumptions

## Assumptions

The following conservative assumptions complete unspecified E-01 details. They
are limited to the Canonical Invoice v0 schema/validator; they do not change the
frozen contracts or extraction implementation.

1. **Version and modes.** The wire value for the contract version is the string
   `"0"`. Mode `A` means native Kandoo issuance; mode `B` means capture
   alongside an existing POS. Routing results are not lifecycle states.
2. **Identifiers.** Invoice, display, operation, device, store, and template
   identifiers are opaque non-empty strings; v0 does not prescribe their
   internal formats. The printed POS invoice number remains a separate,
   optional `header.invoice_number` value.
3. **Public token.** `public_token` is unpadded base64url and at least 22
   characters (at least 128 random bits from a compliant producer). The schema
   verifies only encoding shape and length; token generation and entropy are
   producer responsibilities.
4. **Phone.** A non-empty phone string and `phone_status` are required. Statuses
   are the lowercase values `claimed` and `verified`. Both are valid invoice
   states; this contract does not assert phone ownership or normalize to a
   particular national format.
5. **Integer amounts and quantity.** The pre-existing `unit_price`,
   `line_total`, `subtotal`, `extra_amounts`, and `payable` amounts are
   non-negative integer rials; quantity is a positive whole number. Floats,
   decimal strings, fractional quantities, and implicit toman/rial conversion
   are not accepted. E-01b's optional tax/discount line amounts are integers;
   `rounding` is integer-or-null. These fields are structural only; no sign,
   arithmetic, tax, discount, or rounding rule is applied. `extra_amounts` uses
   arbitrary named non-negative
   integer-rial values; producers send `{}` and `attention_cells: []` explicitly
   when empty because validators do not apply JSON Schema `default` annotations.
   No subtotal/payable arithmetic equation is imposed because accounting
   semantics remain unspecified.
6. **Per-field provenance.** The canonical labels are `native`, `captured`,
   `derived`, `untrusted`, and `unavailable`. Provenance mirrors customer,
   line-item, summary, and header fields; extra-amount keys and line-item
   indexes must match exactly. Platform-assigned invoice identifiers and
   `customer.phone_status` are labeled `native`.
7. **Unit price.** In mode A, a native Kandoo value may be labeled `native`. In
   mode B, a printed unit price is `captured`; a non-printed unit price must be
   explicitly supplied by an upstream derivation and labeled `derived`. The
   E-01 validator never computes a price. If the value cannot be supported
   without guessing, do not promote it to `VALIDATED`/`ISSUED`.
8. **Header fields.** `header` is present, but its printed fields are optional.
   Omitted/null values are labeled `unavailable`; present printed date, time,
   and invoice number values are labeled `untrusted`. `captured_at`, when
   present, is an ISO 8601 timestamp with an explicit UTC offset from Probe and
   is labeled `derived`; it is not a printed invoice date.
9. **Provenance metadata.** The keys `image_sha256`, `template_library_id`,
   and `engine_version` are required in the provenance object but may be null
   when not applicable. A populated image hash is lower-case SHA-256 hex; image
   bytes are not part of this schema and no transfer is performed.
10. **Lifecycle history.** `state_history` is the complete contiguous path from
    `DRAFT`; the current state equals its last target (or `DRAFT` for empty
    history). Each transition carries its own operation and device identifiers.
    The only edges are DRAFT→EXTRACTED→VALIDATED→ISSUED, then ISSUED→REVOKED or
    ISSUED→SUPERSEDED. The two terminal states do not transition further.
11. **Issue gate.** `VALIDATED` and later states cannot have unresolved
    attention cells or required values marked `untrusted`/`unavailable`.
    Optional printed header values may remain untrusted/unavailable. A claimed
    phone is valid and does not by itself block issuance. These checks are
    contract validation only; they do not implement customer locks or SMS.
12. **Immutability fingerprint.** At `ISSUED`, SHA-256 covers the immutable
    content projection listed in `docs/canonical-invoice-v0.md`; state,
    transition history, and the digest itself are excluded so lifecycle
    transitions preserve the fingerprint. The digest is a tamper-evident
    consistency check, not a signature, WORM guarantee, or protection against a
    privileged writer replacing both content and digest.
13. **Serialization profile.** The hash input is compact UTF-8 JSON, sorted by
    UTF-16 key order, with preserved array order, integer-only numeric values,
    literal UTF-8 non-ASCII text, and standard JSON escapes for controls,
    quotes, and backslashes. Lone surrogates and floats are rejected. A
    downstream implementation must reproduce this profile exactly.
14. **Adapter outcome mapping.** `ImageExtractionReady` maps to an `AUTO`
    candidate, `ImageExtractionReviewRequired` to `REVIEW`, and
    `ImageExtractionBlocked` to `REJECT`. These are routing outcomes, not new
    invoice states; `REJECT` does not require a Canonical Invoice record. A
    ready extraction never auto-issues.
15. **Extraction amount conversion.** Existing adapter monetary strings may
    include decimal fractions and quantities may be fractional. E-01 does not
    infer that these are integer rials or truncate/round them. A separately
    approved, explicit conversion rule is required; unresolved values stay in
    review. `adapter.py` and `glyph_classifier.py` remain untouched.
16. **Validator dependency.** `canonical_invoice.py` uses
    `jsonschema>=4.18,<5` for Draft 2020-12 structural validation; lifecycle,
    provenance mirroring, exact-float rejection, and immutability are custom
    semantic checks. The repository's image tests also use Pillow 13.0.0;
    Tesseract is not needed for the unit-test command.
17. **Open questions retained under Assumptions.** The E-01 choices do not
    settle lossless conversion of adapter decimal strings/fractional quantities,
    platform allocation and restore rules for IDs/display numbers/tokens,
    arithmetic semantics for subtotal/tax/discount/payable, phone-verification
    authority/normalization, C# conformance to the JSON/hash profile, privileged
    storage protection beyond a content hash, or the owner-approved D14
    customer wording. Keep unresolved values in REVIEW and obtain owner/design
    decisions before implementing those behaviors.
18. **E-02 pipeline boundary.** `pipeline_v0.py` is a separate local pipeline;
    it does not call the flat-text parser, Tesseract, a network service, or the
    issuance adapter. Its local integer-Rial converter mirrors the strict
    `to_rials` behavior without a direct `adapter.py` dependency or parser
    call. Image bytes and crops are read locally but not retained; image-level
    provenance is SHA-256
    alongside numeric/crop metadata. Runtime extraction does not upload or
    persist invoice images.
19. **Safe layout and payable crop.** `detect_layout_safe()` is the layout
    authority. The payable text box is located from detected table geometry and
    connected components below the last row; if no unique, un-clipped amount
    cluster is found, payable remains missing and the arithmetic gate routes to
    REVIEW. The geometric locator has been checked against the four supplied
    fixtures only; it is not a claim of general-store layout coverage.
20. **Glyph policy.** E-02 uses the existing Glyph confidence default of 60 and
    existing distance/margin settings unchanged. `extra_amounts` remains zero
    for this fixture set; receipts with tax/levies not represented in the
    detected line totals must not be accepted under that assumption. Integer
    Rial conversion is strict; decimal strings are not rounded or truncated.
21. **Description clusters.** E-02 reuses the existing offline dHash
    normalization and the previously reported fixed Hamming threshold of 1.
    A `name_cluster_id` is visual sidecar evidence, not a transcription or
    product-master identity. The frozen Canonical Invoice v0 schema has no
    `name_cluster_id`; E-02 does not add one or place a hash token in
    `product_name`.
22. **Canonical context is caller-owned.** Mode, invoice/display/operation/
    device/store IDs, public token, customer phone/status, and human-readable
    product names are not inferred from the numeric OCR or dHash output. They
    must be explicitly supplied by the producer in `canonical_context`. Without
    that context, the pipeline returns numeric evidence and canonical blockers,
    not fabricated identity/customer/name data. A constructed record remains
    `EXTRACTED`; E-02 never validates, issues, or advances invoice lifecycle.
23. **Operator corrections.** Corrected fields/values are recorded in
    adapter-local `operator_confirmed_*` metadata because the frozen v0
    provenance enum does not include `operator_confirmed`. Corrections rerun
    the arithmetic gate. E-02 never writes corrected glyphs into a template
    bank; it marks a correction bank-eligible only when all supplied corrections
    are strict and the rerun gate passes. Eligibility is not an automatic bank
    update.
24. **Template provenance and evaluation.** The new default bank records all
    four fixture paths and hashes; it is for runtime use on other images and is
    refused for evaluation against any of its sources. Each LOO fold builds a
    fresh in-memory bank from the other three fixtures. The legacy
    `src/templates.json` is not used for LOO; its known sources include full
    fixtures #29 and #32 and a derived crop from #33, so evaluation also treats
    #33 as a source through that crop's local parent lineage.
25. **Ground-truth qualification.** Fixture #31's payable label is marked
    `DERIVED_FROM_ARITHMETIC`; it is not used as a payable glyph training label
    and is excluded from independent per-cell wrong-value comparisons. Its
    extracted payable still must pass the arithmetic gate. Zero observed
    EXTRACTED-but-wrong values means zero mismatches among independently
    operator-confirmed labels that the pipeline marked EXTRACTED; it is not an
    independent visual certification of #31 payable.
26. **No operational guarantees added.** E-02 does not implement invoice
    persistence, store/restore, concurrency, DRAFT idempotency, SEC-1 access
    control, second-factor recovery, SMS delivery, or issuance. It makes no
    restore/security/concurrency guarantee; any later claim in those areas must
    be backed by a failing test and the existing E-00b decisions remain in
    force.
27. **E-01b accounting placeholders.** `summary.tax_lines` and
    `summary.discount_lines` are optional arrays; each entry requires a string
    label, integer amount in rials, and one of the existing provenance labels.
    `summary.rounding` is optional integer-or-null and has no separate
    provenance property in the E-01b schema. The schema's `default` annotations
    are `[]`, `[]`, and `null`; canonical validation remains non-mutating and
    does not materialize them. These fields reserve structure for ACC-0, which
    remains parked; E-01b applies only structural type checks and performs no
    accounting computation, sign/rule validation, or arithmetic.
28. **E-09 CLI producer context and output.** `cli.py` requires a UTF-8 JSON
    `--context` file containing caller-owned `canonical_context`; it never
    fabricates identifiers, customer data, or product names. Successful AUTO or
    REVIEW output is the validated Canonical Invoice object itself, with the
    process exit code carrying the pipeline status (not a new schema property).
    REJECT has no Canonical Invoice and therefore returns 20 with stderr details
    and empty stdout. A REVIEW result without an assemblable Canonical candidate
    returns 10 with stderr details and empty stdout; it is not wrapped in a
    non-contract JSON envelope. CLI failures return 30. The command uses local
    files only and does not require Tesseract or perform network operations.
29. **E-03-kit scope precedence (task-specific).** The current E-03-kit request
    (2026-10-23) prescribes two learning invoices and two exam invoices, with
    short/long variants, and requires Persian glyphs `۲` and `۶` at least five
    times in each invoice. The older Known-Answer summary in
    `docs/PROJECT_STATE.md` says three learning plus one exam and at least five
    occurrences of every symbol `۰`–`۹` and comma. For this print kit, follow
    the newer explicit task specification and do not claim that it supersedes
    or satisfies the broader historical coverage. Until the owner confirms
    whether that older coverage remains an E-05/E-06 acceptance requirement,
    broader symbol coverage is unresolved and must not be reported as passed.
    All names, items, and amounts in the kit are synthetic; none may be entered
    into live sales or inventory data.
30. **ASM-30 E-04.5 label-derived numeric construction.** The four Canonical
    Invoice v0 fixtures in `tests/fixtures/real/canonical/` take integer
    `quantity` and line-total values directly from operator-confirmed
    `labels.json`. Unit price is synthesized only by exact integer division;
    subtotal is the sum of line totals. Invoice 31 payable is derived in line
    with its label note; the other payable values are copied from labels. No
    rounding, extra amount, or `quantity_millis` conversion is introduced.
31. **ASM-31 synthetic required context.** Fields absent from labels use the
    explicitly synthetic context pattern in `docs/cli-contract.md`. Platform
    IDs, token, customer phone/status, and product names remain synthetic and
    are not production data. Phone and placeholder product names are `untrusted`
    and remain in `attention_cells`. Where the frozen v0 validator requires
    platform identifiers/status to carry `native` provenance, that schema
    requirement does not make these synthetic fixture values real or issuable.
32. **ASM-32 synthesis provenance lives in a sidecar.**
    `synthesized_from_labels: true` is recorded in
    `tests/fixtures/real/canonical/synthesis-manifest.json` and documented in
    its README, not added to Canonical Invoice JSON. The frozen v0 schema
    rejects out-of-schema properties; the manifest additionally records source
    image hashes and each fixture's E-07 routing context.
33. **ASM-33 fixture lifecycle projection.** Invoices 29, 31, and 32 are
    represented as `EXTRACTED` test objects corresponding to E-07
    `AUTO_CANDIDATE`; they are not pipeline-emitted outputs. Invoice 33 is
    `DRAFT` because its E-07 fold result was `REVIEW`, as explicitly directed.
    Canonical v0 has no `REVIEW` state. None of these fixtures is `VALIDATED` or
    `ISSUED`.
34. **ASM-34 E-05 template confidence is advisory.** The Python template bank
    clusters label-supplied spatial geometry and records observed Persian digit
    and comma-grouping format; it does not call OCR or image extraction. Its
    default 0.85 weighted match threshold and four-source self-match scores are
    resubstitution evidence only, not calibrated confidence, independent
    accuracy, or an AUTO/issuance decision. New layouts and thresholds require
    held-out owner-authorized validation.
35. **ASM-35 E-06 confidence bands are fail-closed.** The effective confidence
    is the minimum of E-05's match score, extraction confidence, and required
    E-05 layout-component scores; evidence is not averaged to mask a weak
    signal. Scores `>= 0.95` are only eligible for later acceptance gates,
    scores `[0.80, 0.95)` require REVIEW, and scores `< 0.80` REJECT as
    `NO_MATCH`. Missing template/evidence or an explicitly partial invoice
    remains REVIEW because absence is not proof of a wrong invoice.
36. **ASM-36 onboarding warm-up and D14 gate.** Ordinary onboarding candidates
    for a new store (N=4, matching E-03-kit) remain REVIEW during warm-up; a
    clearly invalid object or known numeric corruption still REJECTS, and no
    automatic acceptance or online bank updates occur. Later invoices are
    eligible for evaluation only against an explicitly locked per-store bank.
    E-06 also requires caller-verified evidence that the D14 store agreement
    was digitally signed; legal wording itself remains owner/lawyer-controlled.
37. **ASM-37 stable verdict reasons.** E-06 returns ACCEPT/REVIEW/REJECT with
    one or more stable machine-readable reason codes. A complete object that
    fails Canonical validation is REJECT/`SCHEMA_INVALID`; a candidate
    explicitly marked partial is REVIEW/`PARTIAL_MATCH`. Known numeric
    disagreement is REJECT/`NUMS_INCONSISTENT`; incomplete evidence and new or
    ambiguous layouts remain REVIEW. Hard failures cannot be overridden by a
    later positive signal.
38. **ASM-38 human confirmation required for ACCEPT.** Because E-05's current
    scores are resubstitution evidence and OCR confidence is not proof of
    truth, E-06 does not auto-accept a new invoice. ACCEPT requires all
    machine-checkable gates plus a timestamped store-owner audit confirming
    every required invoice field. The library validates audit completeness;
    authentication and durable audit storage remain the caller's
    responsibility. Overrides may downgrade but cannot bypass a hard gate.
39. **ASM-39 E-03 digit coverage is kit-scoped.** For each E-03 known-answer
    onboarding-kit invoice, Persian `۲` and `۶` must each appear at least five
    times in the observed numeric-cell text. Failure keeps the kit invoice in
    REVIEW. This synthetic coverage witness is not imposed on ordinary
    post-onboarding invoices unless a future decision requires it.
40. **ASM-40 E-06 mixed-template and raw-number gates.** For a bank with
    multiple templates, a best-to-runner-up E-05 score difference below 0.03
    is ambiguous and remains REVIEW; the margin is configurable, not calibrated.
    Before ACCEPT, raw Persian numeric observations must parse exactly to the
    Canonical quantities, line totals, and payable, each unit price multiplied
    by quantity must equal its line total, and the sum of line totals must equal
    both subtotal and payable. Non-zero extra amounts, tax/discount lines, or
    rounding remain REVIEW/`ACCOUNTING_ADJUSTMENT_UNSUPPORTED`; E-06 does not
    guess their meaning. A direct disagreement with the required sum/raw-value
    checks remains REJECT/`NUMS_INCONSISTENT`.
41. **ASM-41 E-08 new-type detection is gated by integrity and onboarding.**
    Only a store with at least four previously owner-accepted onboarding
    invoices and a locked bank may create a new-type candidate. Detection uses
    E-05 `score_bank()` and its configured threshold; a below-threshold score
    is only a hypothesis. Canonical validation and E-06 numeric arithmetic
    must pass, and all observed quantities, line totals, and payable must parse
    and match Canonical values. Schema/numeric hard failures remain
    REJECT/`SCHEMA_INVALID` or `NUMS_INCONSISTENT`; missing or unreadable
    evidence remains REVIEW without a candidate. A qualifying new type is
    REVIEW/`NEW_LAYOUT`, never automatically accepted.
42. **ASM-42 candidates are separate, human-gated records.** E-08 template
    candidates are stored outside the production E-05 bank and begin PROPOSED.
    Only PROPOSED→REVIEWED→ACCEPTED/REJECTED is allowed, with reviewer,
    timestamp, and reason recorded. Candidate approval alone never mutates the
    bank; rejected candidates are not promoted.
43. **ASM-43 new-type mini-onboarding remains N=4.** A human-accepted candidate
    starts a distinct four-invoice cycle. Every cycle invoice remains REVIEW
    and counts only once after required fields are reviewed and audited. Four
    valid records produce READY_TO_LOCK; the caller must create and explicitly
    lock a versioned E-05 bank snapshot before any use in production.
44. **ASM-44 escalation placeholder is three unresolved detections in 24h.**
    Three distinct invoice detections for one store within a rolling 24-hour
    window set a support-escalation flag while their candidate is unresolved.
    REVIEWED is not terminal; ACCEPTED or REJECTED resolves the candidate.
    E-08 does not create tickets or contact support.
45. **ASM-45 serialize unresolved candidates per store.** At most one
    PROPOSED/REVIEWED candidate may be active for a store. Repeated detections
    of its same signature reuse the record; a different signature remains
    REVIEW, is logged, and waits until the active candidate is resolved rather
    than creating or merging a concurrent candidate. E-08 does not create
    candidates while the store remains in initial E-06 onboarding; those
    invoices stay on the E-06 review path until N=4 owner-accepted invoices
    and a locked bank are established.
