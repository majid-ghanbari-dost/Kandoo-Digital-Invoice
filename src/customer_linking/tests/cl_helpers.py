"""Shared helpers for the WP-9.1 customer-linking tests (unique module name
— safe for combined collection with all prior suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → customer_linking → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CA_TESTS = SRC / "canonical_assembly" / "tests"
if str(CA_TESTS) not in sys.path:
    sys.path.insert(0, str(CA_TESTS))

from ca_helpers import (  # noqa: E402  (P6.2 helpers reused verbatim)
    LINE_BINDING,
    CanonicalAssemblyStack,
)
from canonical_assembly import (  # noqa: E402
    AssemblyReadSuccess,
)
from canonicalization import (  # noqa: E402
    CanonicalizationAccepted,
)
from customer_linking import (  # noqa: E402
    CustomerIdentityReplay,
    CustomerIdentityRegistered,
    CustomerLinkingService,
    CustomerLinkingStore,
    CustomerLinkReadSuccess,
    CustomerLinkReplay,
    CustomerLinkRequestRefused,
    CustomerLinked,
    CustomerReadSuccess,
    CustomerLinkUnresolved,
)
from capture import S1Service  # noqa: E402

# Line-structured corpus WITH customer-identifier fields — the customer codes
# ride as canonical fields (engine-vocabulary names relayed verbatim by P6.2;
# this layer declares them, never discovers them). No phone/email/barcode
# semantics are implemented anywhere: the kinds below are OPAQUE declared
# labels (OD-CL3), and the values are plain declared strings.
PAGE_CUSTOMERS_OK = [
    b"invoice.number=INV-CL-2026-001\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"customer.code=CUST-A-001\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n",
]

PAGE_CUSTOMERS_AMBIGUOUS = [
    b"invoice.number=INV-CL-AMBIG-1\ninvoice.date=2026-10-08\n"
    b"total.net=500.00\ntax.amount=40\n"
    b"customer.code=CUST-X-1\ncustomer.code=CUST-X-2\n"
    b"line.0.quantity=2\nline.0.unit_price=250.00\nline.0.total=500.00\n",
]

CL_FIELD = "customer.code"
CL_KIND = "CUST-CODE"
CL_VALUE = "CUST-A-001"

_CL_SEQ = {"n": 0}


def unique_customer_pages(customer_line=CL_FIELD + "=" + CL_VALUE):
    """Distinct customer-bearing pages (unique invoice number) — each call
    produces a different capture S1, so multiple invoices coexist in one
    test. `customer_line` is a raw `field=value` page line."""
    _CL_SEQ["n"] += 1
    n = _CL_SEQ["n"]
    return [f"invoice.number=INV-CL-SEQ-{n:04d}\ninvoice.date=2026-10-08\n"
            f"total.net=1180.00\ntax.amount=94.40\n"
            f"{customer_line}\n"
            f"line.0.quantity=2\nline.0.unit_price=500.00\n"
            f"line.0.total=1000.00\n".encode("utf-8")]


class CustomerLinkingStack(CanonicalAssemblyStack):
    """The P6.2 composition PLUS the WP-9.1 customer store/service — the
    WP-9.1 stack under test. All assembly machinery is the VERBATIM P6.2
    stack (the linking layer consumes it, never bypasses it)."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db,
                 norm_db, deriv_db, val_db, vsm_db, gate_db, assembly_db,
                 customer_db, with_evidence=True, engines=None, rules=None,
                 extra_rules=(), formulas=None, norm_rulesets=None):
        super().__init__(capture_db, recon_db, extraction_db, binding_db,
                         norm_db, deriv_db, val_db, vsm_db, gate_db,
                         assembly_db, with_evidence=with_evidence,
                         engines=engines, rules=rules, extra_rules=extra_rules,
                         formulas=formulas, norm_rulesets=norm_rulesets)
        self.customer_db = customer_db
        self._cls1 = S1Service()
        self.customer_store = CustomerLinkingStore(customer_db, self._cls1)
        self.customers_svc = CustomerLinkingService(
            self.customer_store, self.assembly, self._cls1)

    # -- pipeline helpers --------------------------------------------------

    def assemble_customers_invoice(self, parts=None, label="cl-test",
                                   binding=None):
        """Full happy path: capture → … → P6.1 ACCEPTED admission → P6.2
        issued invoice over the customer corpus (or any declared parts).
        Returns (assembly_outcome, invoice_id)."""
        state_parts = PAGE_CUSTOMERS_OK if parts is None else parts
        gate_outcome = self.build_accepted_lines_admission(
            parts=state_parts, label=label)
        assert isinstance(gate_outcome, CanonicalizationAccepted), gate_outcome
        invoice_id = gate_outcome.canonical_invoice.canonical_invoice_id
        assembled = self.assemble_ok(invoice_id)
        return assembled, invoice_id

    def register(self, kind=CL_KIND, value=CL_VALUE):
        outcome = self.customers_svc.register_customer_identity(kind, value)
        assert isinstance(outcome, (CustomerIdentityRegistered,
                                    CustomerIdentityReplay)), outcome
        return outcome

    def link(self, invoice_id, field_name=CL_FIELD, kind=CL_KIND):
        outcome = self.customers_svc.link(invoice_id, field_name, kind)
        assert isinstance(outcome, (CustomerLinked,
                                    CustomerLinkUnresolved,
                                    CustomerLinkReplay)), outcome
        return outcome

    def read_invoice(self, invoice_id):
        read = self.assembly.read_assembled_invoice(invoice_id)
        assert isinstance(read, AssemblyReadSuccess), read
        return read

    def close(self):
        self.customer_store.close()
        super().close()


__all__ = [
    "CanonicalAssemblyStack", "CustomerLinkingStack",
    "CustomerLinkingStore", "CustomerLinkingService",
    "LINE_BINDING", "unique_customer_pages",
    "PAGE_CUSTOMERS_OK", "PAGE_CUSTOMERS_AMBIGUOUS",
    "CL_FIELD", "CL_KIND", "CL_VALUE",
    "AssemblyReadSuccess", "CanonicalizationAccepted",
    "CustomerIdentityRegistered", "CustomerIdentityReplay",
    "CustomerReadSuccess", "CustomerLinked", "CustomerLinkUnresolved",
    "CustomerLinkReplay", "CustomerLinkRequestRefused",
    "CustomerLinkReadSuccess",
]
