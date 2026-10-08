"""WP-8.1 exact-match behavior tests — the frozen D-05 rule implemented
exactly: declared reference + byte-exact single catalog identity →
EXACT_MATCHED; zero → durable UNRESOLVED; replay verbatim; ambiguity never
auto-resolved (SPEC §4/§5; OD-PM4/PM5/PM6/PM7)."""
from pc_helpers import (
    CatalogIdentityRegistered,
    PC_FIELD_0,
    PC_FIELD_1,
    PC_KIND,
    PAGE_PRODUCTS_OK,
    ProductCandidateStack,
    unique_product_pages,
)
from product_candidate import (
    ProductExactMatched,
    ProductMatchReplay,
    ProductReferenceUnresolved,
    UNRESOLVED_NO_CATALOG_IDENTITY,
)


def _invoice_with_products(stack, parts=None, label="pm-match"):
    assembled, invoice_id = stack.assemble_products_invoice(
        parts=parts, label=label)
    return assembled, invoice_id


def test_exact_match_happy_path_points_at_the_catalog_identity(stack):
    stack.register("SKU", "SKU-A-001")
    assembled, invoice_id = _invoice_with_products(stack)
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductExactMatched), outcome
    record = outcome.record
    assert record.invoice_id == invoice_id
    assert record.declared_field_name == PC_FIELD_0
    assert record.identifier_kind == PC_KIND
    assert record.match_outcome == "EXACT_MATCHED"
    assert record.unresolved_reason == ""
    assert record.catalog_identity_id \
        == outcome.catalog_identity.catalog_identity_id
    # pointer discipline: the value is NOT in the durable row (OD-PM6)
    assert "SKU-A-001" not in str(sorted(vars(record).items()))
    # the linked read is the verified P6.2 read
    assert outcome.invoice_read.invoice.invoice_id == invoice_id


def test_unregistered_identifier_is_durable_unresolved(stack):
    assembled, invoice_id = _invoice_with_products(stack)
    outcome = stack.products.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductReferenceUnresolved), outcome
    assert outcome.record.match_outcome == "UNRESOLVED"
    assert outcome.record.catalog_identity_id == ""
    assert outcome.reason == UNRESOLVED_NO_CATALOG_IDENTITY
    assert outcome.record.unresolved_reason == UNRESOLVED_NO_CATALOG_IDENTITY
    assert len(stack.products.matches()) == 1     # auditable append-only fact


def test_zero_rows_for_an_unknown_kind_is_unresolved_not_a_guess(stack):
    stack.register("EAN", "SKU-A-001")     # registered under a DIFFERENT kind
    assembled, invoice_id = _invoice_with_products(stack)
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductReferenceUnresolved), outcome


def test_replay_returns_the_existing_outcome_verbatim_zero_new_rows(stack):
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = _invoice_with_products(stack)
    first = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    before = len(stack.products.matches())
    replay = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(replay, ProductMatchReplay), replay
    assert replay.record == first.record
    assert len(stack.products.matches()) == before          # ZERO new rows
    # the replayed catalog identity re-verifies to the same identity
    assert replay.catalog_identity == first.catalog_identity


def test_unresolved_replay_never_re_decides_after_later_registration(stack):
    """OD-PM4: the durable UNRESOLVED fact states what was true at match
    time; a later catalog registration never rewrites it (no UPDATE, no
    re-decision)."""
    _, invoice_id = _invoice_with_products(stack)
    first = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(first, ProductReferenceUnresolved)
    stack.register("SKU", "SKU-A-001")                     # catalog grows
    replay = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(replay, ProductMatchReplay), replay
    assert replay.record == first.record
    assert replay.record.match_outcome == "UNRESOLVED"


def test_second_declared_reference_on_the_same_invoice_appends(stack):
    stack.register("SKU", "SKU-A-001")
    stack.register("SKU", "SKU-B-002")
    _, invoice_id = _invoice_with_products(stack)
    first = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    second = stack.match(invoice_id, PC_FIELD_1, PC_KIND)
    assert isinstance(first, ProductExactMatched)
    assert isinstance(second, ProductExactMatched)
    assert first.record.match_id != second.record.match_id
    assert len(stack.products.matches_of(invoice_id)) == 2


def test_derived_canonical_field_is_an_equally_valid_reference(stack):
    """OD-PM6: both D-01 provenances are verified P6.2 content. The DERIVED
    total.gross field is declared as the reference and matches its
    registered catalog identity (registered from the LIVE verified value —
    no format guessing in tests)."""
    assembled, invoice_id = _invoice_with_products(stack)
    gross = next(f for f in assembled.fields
                 if f.field_name == "total.gross")
    assert gross.provenance == "DERIVED"
    stack.register("AMT", gross.canonical_value)
    outcome = stack.match(invoice_id, "total.gross", "AMT")
    assert isinstance(outcome, ProductExactMatched), outcome
    assert outcome.record.provenance == "DERIVED"
    assert outcome.record.canonical_seq == gross.canonical_seq


def test_two_independent_invoices_match_independently(stack):
    stack.register("SKU", "SKU-A-001")
    _, invoice_a = _invoice_with_products(stack, label="pm-inv-a")
    _, invoice_b = _invoice_with_products(
        stack, parts=unique_product_pages(), label="pm-inv-b")
    outcome_a = stack.match(invoice_a, PC_FIELD_0, PC_KIND)
    outcome_b = stack.match(invoice_b, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome_a, ProductExactMatched)
    assert isinstance(outcome_b, ProductExactMatched)
    assert outcome_a.record.match_id != outcome_b.record.match_id
    assert outcome_a.record.catalog_identity_id \
        == outcome_b.record.catalog_identity_id   # same catalog identity
    assert len(stack.products.matches()) == 2


def test_match_record_anchors_agree_with_the_verified_invoice(stack):
    stack.register("SKU", "SKU-A-001")
    assembled, invoice_id = _invoice_with_products(stack)
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    record = outcome.record
    assert record.capture_s1 == assembled.invoice.capture_s1
    assert record.capture_s1_algorithm_id \
        == assembled.invoice.capture_s1_algorithm_id
    field_seq = {f.field_name: f.canonical_seq for f in assembled.fields}
    assert record.canonical_seq == field_seq[PC_FIELD_0]
    assert record.provenance == "EXTRACTED"


def test_product_corpus_pages_are_distinct_captures(stack):
    """Each unique_product_pages() call is a DIFFERENT capture (fresh S1) —
    the corpus cannot silently reuse captures (frozen idempotency)."""
    _, a = _invoice_with_products(stack, parts=unique_product_pages(),
                                  label="pm-distinct-a")
    _, b = _invoice_with_products(stack, parts=unique_product_pages(),
                                  label="pm-distinct-b")
    assert a != b
    assembled_a = stack.read_invoice(a)
    assembled_b = stack.read_invoice(b)
    assert assembled_a.invoice.capture_s1 != assembled_b.invoice.capture_s1


def test_byte_distinct_value_never_matches_verbatim_value(stack):
    """Exact matching is byte-identity (OD-PM3): 'sku-a-001' is a DIFFERENT
    identifier from 'SKU-A-001' — no case folding, no fuzzy tolerance (the
    frozen P4.1 grammar — NFC + trim — preserves case; this layer performs
    NO normalization of its own)."""
    stack.register("SKU", "SKU-A-001")
    pages = unique_product_pages(codes=(PC_FIELD_0 + "=sku-a-001",
                                        PC_FIELD_1 + "=SKU-B-002"))
    _, invoice_id = _invoice_with_products(stack, parts=pages,
                                           label="pm-case")
    outcome = stack.products.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductReferenceUnresolved), outcome
