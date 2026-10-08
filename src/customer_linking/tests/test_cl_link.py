"""WP-9.1 deterministic-linking behavior tests — the established
deterministic rule implemented exactly: declared reference + byte-exact
single customer identity → LINKED; zero → durable UNRESOLVED and NEVER a
created customer (D-06/DEF3); replay verbatim; ambiguity never
auto-resolved (SPEC §4/§5; OD-CL4/CL5/CL6/CL7)."""
from cl_helpers import (
    CL_FIELD,
    CL_KIND,
    CL_VALUE,
    PAGE_CUSTOMERS_OK,
    CustomerLinkingStack,
    unique_customer_pages,
)
from customer_linking import (
    CustomerLinked,
    CustomerLinkReplay,
    CustomerLinkUnresolved,
    UNRESOLVED_NO_CUSTOMER_IDENTITY,
)


def _invoice_with_customers(stack, parts=None, label="cl-link"):
    assembled, invoice_id = stack.assemble_customers_invoice(
        parts=parts, label=label)
    return assembled, invoice_id


def test_deterministic_link_happy_path_points_at_the_existing_customer(stack):
    stack.register(CL_KIND, CL_VALUE)
    assembled, invoice_id = _invoice_with_customers(stack)
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinked), outcome
    record = outcome.record
    assert record.invoice_id == invoice_id
    assert record.declared_field_name == CL_FIELD
    assert record.identifier_kind == CL_KIND
    assert record.link_outcome == "LINKED"
    assert record.unresolved_reason == ""
    assert record.customer_identity_id \
        == outcome.customer_identity.customer_identity_id
    # pointer discipline: the value is NOT in the durable row (OD-CL6)
    assert CL_VALUE not in str(sorted(vars(record).items()))
    # the linked read is the verified P6.2 read
    assert outcome.invoice_read.invoice.invoice_id == invoice_id


def test_unregistered_customer_is_durable_unresolved_and_never_created(stack):
    """D-06/DEF3: the invoice carries a customer-looking value with no
    existing customer → the outcome is UNRESOLVED — the register stays
    EMPTY (no auto-create, structurally)."""
    _, invoice_id = _invoice_with_customers(stack)
    outcome = stack.customers_svc.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinkUnresolved), outcome
    assert outcome.record.link_outcome == "UNRESOLVED"
    assert outcome.record.customer_identity_id == ""
    assert outcome.reason == UNRESOLVED_NO_CUSTOMER_IDENTITY
    assert outcome.record.unresolved_reason == UNRESOLVED_NO_CUSTOMER_IDENTITY
    assert len(stack.customers_svc.links()) == 1  # auditable append-only fact
    assert len(stack.customers_svc.customers()) == 0  # NO customer was created


def test_linking_never_grows_the_register_no_matter_the_outcome(stack):
    """Every ladder outcome (LINKED / UNRESOLVED / replay / refusal) has
    exactly ONE possible write: the link row. The customer register only
    ever changes through explicit registration."""
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_a = _invoice_with_customers(stack)
    _, invoice_b = _invoice_with_customers(stack,
                                           parts=unique_customer_pages(
                                               customer_line=CL_FIELD +
                                               "=CUST-UNKNOWN-9"),
                                           label="cl-never-create")
    before = len(stack.customers_svc.customers())
    stack.link(invoice_a, CL_FIELD, CL_KIND)                       # LINKED
    stack.customers_svc.link(invoice_b, CL_FIELD, CL_KIND)         # UNRESOLVED
    stack.link(invoice_a, CL_FIELD, CL_KIND)                       # replay
    stack.customers_svc.link(invoice_b, "no.such.field", CL_KIND)  # refusal
    assert len(stack.customers_svc.customers()) == before


def test_replay_returns_the_existing_outcome_verbatim_zero_new_rows(stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = _invoice_with_customers(stack)
    first = stack.link(invoice_id, CL_FIELD, CL_KIND)
    before = len(stack.customers_svc.links())
    replay = stack.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(replay, CustomerLinkReplay), replay
    assert replay.record == first.record
    assert len(stack.customers_svc.links()) == before          # ZERO new rows
    assert replay.customer_identity == first.customer_identity


def test_unresolved_replay_never_re_decides_after_later_registration(stack):
    """OD-CL4: the durable UNRESOLVED fact states what was true at link
    time; a later customer registration never rewrites it (no UPDATE, no
    re-decision, no retroactive linking)."""
    _, invoice_id = _invoice_with_customers(stack)
    first = stack.customers_svc.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(first, CustomerLinkUnresolved)
    stack.register(CL_KIND, CL_VALUE)                    # register grows
    replay = stack.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(replay, CustomerLinkReplay), replay
    assert replay.record == first.record
    assert replay.record.link_outcome == "UNRESOLVED"


def test_second_declared_reference_on_the_same_invoice_appends(stack):
    stack.register(CL_KIND, CL_VALUE)
    stack.register("CUST-ALT", CL_VALUE)
    _, invoice_id = _invoice_with_customers(stack)
    first = stack.link(invoice_id, CL_FIELD, CL_KIND)
    second = stack.link(invoice_id, CL_FIELD, "CUST-ALT")
    assert isinstance(first, CustomerLinked)
    assert isinstance(second, CustomerLinked)
    assert first.record.link_id != second.record.link_id
    assert len(stack.customers_svc.links_of(invoice_id)) == 2


def test_derived_canonical_field_is_an_equally_valid_reference(stack):
    """OD-CL6: both D-01 provenances are verified P6.2 content."""
    assembled, invoice_id = _invoice_with_customers(stack)
    gross = next(f for f in assembled.fields
                 if f.field_name == "total.gross")
    assert gross.provenance == "DERIVED"
    stack.register("AMT", gross.canonical_value)
    outcome = stack.link(invoice_id, "total.gross", "AMT")
    assert isinstance(outcome, CustomerLinked), outcome
    assert outcome.record.provenance == "DERIVED"
    assert outcome.record.canonical_seq == gross.canonical_seq


def test_two_independent_invoices_link_independently(stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_a = _invoice_with_customers(
        stack, parts=unique_customer_pages(), label="cl-inv-a")
    _, invoice_b = _invoice_with_customers(
        stack, parts=unique_customer_pages(), label="cl-inv-b")
    outcome_a = stack.link(invoice_a, CL_FIELD, CL_KIND)
    outcome_b = stack.link(invoice_b, CL_FIELD, CL_KIND)
    assert isinstance(outcome_a, CustomerLinked)
    assert isinstance(outcome_b, CustomerLinked)
    assert outcome_a.record.link_id != outcome_b.record.link_id
    assert outcome_a.record.customer_identity_id \
        == outcome_b.record.customer_identity_id   # same existing customer
    assert len(stack.customers_svc.links()) == 2


def test_match_record_anchors_agree_with_the_verified_invoice(stack):
    stack.register(CL_KIND, CL_VALUE)
    assembled, invoice_id = _invoice_with_customers(stack)
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    record = outcome.record
    assert record.capture_s1 == assembled.invoice.capture_s1
    assert record.capture_s1_algorithm_id \
        == assembled.invoice.capture_s1_algorithm_id
    field_seq = {f.field_name: f.canonical_seq for f in assembled.fields}
    assert record.canonical_seq == field_seq[CL_FIELD]
    assert record.provenance == "EXTRACTED"


def test_byte_distinct_value_never_matches_verbatim_value(stack):
    """Exact matching is byte-identity (OD-CL3): 'cust-a-001' is a DIFFERENT
    identifier from 'CUST-A-001' — no case folding, no fuzzy tolerance."""
    stack.register(CL_KIND, CL_VALUE)
    pages = unique_customer_pages(customer_line=CL_FIELD + "=cust-a-001")
    _, invoice_id = _invoice_with_customers(stack, parts=pages,
                                            label="cl-case")
    outcome = stack.customers_svc.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinkUnresolved), outcome
    assert len(stack.customers_svc.customers()) == 1   # nothing invented


def test_zero_rows_for_an_unknown_kind_is_unresolved_not_a_guess(stack):
    stack.register("NATIONAL-ID", CL_VALUE)   # registered under a DIFFERENT kind
    _, invoice_id = _invoice_with_customers(stack)
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinkUnresolved), outcome
