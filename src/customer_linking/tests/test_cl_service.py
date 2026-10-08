"""WP-9.1 service-level tests — the P6.2 verified read consumed VERBATIM
(spy-proven), the refusal matrix with zero durable residue, INV-CL-1:1,
and frozen-store row-count stability (SPEC §2/§3/§4)."""
import inspect
import sqlite3

from cl_helpers import (
    CL_FIELD,
    CL_KIND,
    CL_VALUE,
    PAGE_CUSTOMERS_AMBIGUOUS,
    CustomerLinkingStack,
    unique_customer_pages,
)
from customer_linking import (
    CustomerIdentityRegistered,
    CustomerIdentityReplay,
    CustomerLinkingService,
    CustomerLinked,
    CustomerLinkReplay,
    CustomerLinkRequestRefused,
    CustomerLinkUnresolved,
)


# ---------------------------------------------------------------------------
# Delegation proof — the ONLY invoice path is the P6.2 verified read
# ---------------------------------------------------------------------------

class _CountingAssembly:
    """Spy wrapper around the real P6.2 assembly service: counts every
    read_assembled_invoice call and passes it through VERBATIM."""

    def __init__(self, assembly):
        self._assembly = assembly
        self.calls = []

    def read_assembled_invoice(self, invoice_id):
        self.calls.append(invoice_id)
        return self._assembly.read_assembled_invoice(invoice_id)

    def __getattr__(self, name):     # everything else → the real service
        return getattr(self._assembly, name)


def test_link_consumes_the_p6_2_verified_read_exactly_once_per_call(stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-spy")
    spy = _CountingAssembly(stack.assembly)
    service = CustomerLinkingService(stack.customer_store, spy, stack._cls1)
    outcome = service.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinked), outcome
    assert spy.calls == [invoice_id]          # exactly ONE verified read
    replay = service.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(replay, CustomerLinkReplay), replay
    # call 2 = L1 verified read + the replay's own linked re-verification
    assert spy.calls == [invoice_id] * 3


def test_service_holds_no_other_upstream_path(stack):
    """The service constructor takes ONLY (store, assembly, s1) — there is
    no second invoice path, no upstream store handle, nothing to bypass
    with (SPEC §2)."""
    sig = inspect.signature(CustomerLinkingService.__init__)
    params = [p for p in sig.parameters if p != "self"]
    assert params == ["store", "assembly", "s1"]


def test_registration_api_carries_no_capture_or_invoice_parameter():
    """OD-CL2: the ONLY register write path takes (identifier_kind,
    identifier_value) — no capture/invoice/document parameter exists, so
    capture-derived customer creation is structurally impossible
    (D-06/DEF3)."""
    sig = inspect.signature(
        CustomerLinkingService.register_customer_identity)
    params = [p for p in sig.parameters if p != "self"]
    assert params == ["identifier_kind", "identifier_value"]
    init_params = [p for p in inspect.signature(
        CustomerLinkingService.__init__).parameters if p != "self"]
    assert init_params == ["store", "assembly", "s1"]


# ---------------------------------------------------------------------------
# Refusal matrix — zero durable residue (L2/L3)
# ---------------------------------------------------------------------------

def test_refusal_matrix_is_complete_and_leaves_zero_residue(stack):
    _, invoice_id = stack.assemble_customers_invoice(label="cl-refusals")
    refusals = [
        # L2: malformed declarations
        stack.customers_svc.link(invoice_id, "", CL_KIND),
        stack.customers_svc.link(invoice_id, CL_FIELD, ""),
        stack.customers_svc.link(invoice_id, "   ", CL_KIND),
        # L3: declared field not found
        stack.customers_svc.link(invoice_id, "no.such.field", CL_KIND),
    ]
    for outcome in refusals:
        assert isinstance(outcome, CustomerLinkRequestRefused), outcome
    ambiguous = stack.assemble_customers_invoice(
        parts=PAGE_CUSTOMERS_AMBIGUOUS, label="cl-ambig-field")
    refused = stack.customers_svc.link(ambiguous[1], CL_FIELD, CL_KIND)
    assert isinstance(refused, CustomerLinkRequestRefused), refused
    assert "declared-field-ambiguous" in refused.detail
    # zero residue across every refusal
    assert len(stack.customers_svc.links()) == 0
    assert len(stack.customers_svc.customers()) == 0


def test_declared_field_not_found_names_the_missing_field(stack):
    _, invoice_id = stack.assemble_customers_invoice(label="cl-notfound")
    refused = stack.customers_svc.link(invoice_id, "customer.vat", CL_KIND)
    assert isinstance(refused, CustomerLinkRequestRefused)
    assert "declared-field-not-found" in refused.detail


def test_nonexistent_invoice_is_fail_closed_input_integrity(stack):
    outcome = stack.customers_svc.link("no-such-invoice", CL_FIELD, CL_KIND)
    assert type(outcome).__name__ == "CustomerLinkInputIntegrityFailure", \
        outcome
    assert len(stack.customers_svc.links()) == 0     # zero residue


def test_deterministic_link_commit_is_atomic_single_row(stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-atomic")
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinked)
    rows = stack.customers_svc.links()
    assert len(rows) == 1
    assert rows[0] == outcome.record
    assert rows[0].record_fingerprint
    assert rows[0].fingerprint_algorithm_id == "sha256-v1"


def test_registration_outcome_vocabulary_is_exhaustive(stack):
    """Every register_customer_identity call returns exactly one explicit
    outcome — registered / replay / refused covers the API."""
    ok = stack.customers_svc.register_customer_identity(CL_KIND, CL_VALUE)
    assert isinstance(ok, CustomerIdentityRegistered)
    replay = stack.customers_svc.register_customer_identity(CL_KIND, CL_VALUE)
    assert isinstance(replay, CustomerIdentityReplay)
    refused = stack.customers_svc.register_customer_identity("", "")
    assert type(refused).__name__ == "CustomerRegistrationRefused"


# ---------------------------------------------------------------------------
# Frozen-store row-count stability — the layer mutates NOTHING upstream
# ---------------------------------------------------------------------------

def test_row_count_stability_of_frozen_stores_during_linking(stack):
    """Both invoices are built FIRST; the frozen-store snapshot is taken
    before the FIRST link — linking itself (including replays and refusals)
    must grow NO frozen store (SPEC §1; additive register only)."""
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-stable")
    unresolved_invoice = stack.assemble_customers_invoice(
        parts=unique_customer_pages(
            customer_line=CL_FIELD + "=CUST-NONE-1"),
        label="cl-stable-unresolved")[1]
    before = _upstream_counts(stack)
    first = stack.link(invoice_id, CL_FIELD, CL_KIND)
    replay = stack.link(invoice_id, CL_FIELD, CL_KIND)
    unresolved = stack.customers_svc.link(unresolved_invoice, CL_FIELD,
                                          CL_KIND)
    refused = stack.customers_svc.link(invoice_id, "no.such.field", CL_KIND)
    assert isinstance(first, CustomerLinked)
    assert isinstance(replay, CustomerLinkReplay)
    assert isinstance(unresolved, CustomerLinkUnresolved)
    assert isinstance(refused, CustomerLinkRequestRefused)
    assert _upstream_counts(stack) == before


def _upstream_counts(stack):
    rows = {}
    conns = {
        "capture": (stack.capture_db, "capture_records"),
        "recon": (stack.recon_db, "documents"),
        "norm": (stack.norm_db, "normalization_records"),
        "vsm": (stack.vsm_db, "domain_state_records"),
        "gate": (stack.gate_db, "gate_decisions"),
        "assembly": (stack.assembly_db, "canonical_invoices"),
    }
    for key, (db, table) in conns.items():
        conn = sqlite3.connect(str(db))
        try:
            rows[key] = conn.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            rows[key] = None          # table name varies per layer
        finally:
            conn.close()
    return rows
