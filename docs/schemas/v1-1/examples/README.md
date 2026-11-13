# E-40 v1.1 issued-invoice synthetic goldens

All files in this directory are synthetic contract examples. They are extension-only `response_snapshot.response.invoice` objects for the additive v1.1 recorded fields; they are not real invoices and do not reconstruct the frozen v0 invoice schema. `issued-invoice-v1-1-full.json` demonstrates recorded values only: no relationship is asserted between `payments` and `remaining_balance`. The minimal and explicit-null examples demonstrate the optional-field distinction.

`manifest.json` pins exact UTF-8/LF byte sizes and SHA-256 digests. `tests/test_e40_v1_1_golden_examples.py` checks each digest and validates every example against the already-pinned issued-invoice v1.1 schema. The same test runs on Ubuntu and Windows so each platform checks the same byte pins.

No full `PublicInvoiceView` golden is supplied: the v1.0 base schema referenced by the public-view schema is absent from this checkout. Do not invent or synthesize that base schema. E-40 also records, but does not add to v1.1, the Holoo cheque and invoice-level-discount gaps.
