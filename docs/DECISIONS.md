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
5. **Integer amounts and quantity.** Every monetary value is a non-negative
   integer number of rials; quantity is a positive whole number. Negative
   adjustments, fractional quantities, float values, rounding, and implicit
   toman/rial or decimal-string conversion are not accepted. `extra_amounts`
   uses arbitrary named non-negative integer-rial values; producers send `{}`
   and `attention_cells: []` explicitly when empty because validators do not
   apply JSON Schema `default` annotations. No subtotal/payable arithmetic
   equation is imposed because tax, discount, and
   adjustment semantics were not specified.
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
