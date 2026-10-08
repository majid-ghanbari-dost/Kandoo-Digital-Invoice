"""Shared helpers for the WP-8.1 product-candidate tests (unique module name
— safe for combined collection with all prior suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → product_candidate → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CA_TESTS = SRC / "canonical_assembly" / "tests"
if str(CA_TESTS) not in sys.path:
    sys.path.insert(0, str(CA_TESTS))

from ca_helpers import (  # noqa: E402  (P6.2 helpers reused verbatim)
    LINE_BINDING,
    PAGE_LINES_OK,
    CanonicalAssemblyStack,
    unique_line_pages,
)
from canonical_assembly import (  # noqa: E402
    AssemblyCompleted,
    AssemblyReadSuccess,
)
from canonicalization import (  # noqa: E402
    CanonicalizationAccepted,
)
from product_candidate import (  # noqa: E402
    CatalogIdentityReplay,
    CatalogIdentityRegistered,
    CatalogReadSuccess,
    ProductCandidateService,
    ProductCandidateStore,
    ProductExactMatched,
    ProductMatchReadSuccess,
    ProductMatchReplay,
    ProductMatchRequestRefused,
    ProductMatchInputIntegrityFailure,
    ProductReferenceUnresolved,
)
from capture import S1Service  # noqa: E402

# Line-structured corpus WITH product-identifier fields — the product codes
# ride as canonical fields (engine-vocabulary names relayed verbatim by P6.2;
# this layer declares them, never discovers them). No barcode semantics are
# implemented anywhere: 'SKU' below is an OPAQUE declared kind label
# (OD-PM3), and the values are plain declared strings.
PAGE_PRODUCTS_OK = [
    b"invoice.number=INV-PC-2026-001\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n"
    b"line.0.product_code=SKU-A-001\n"
    b"line.1.quantity=3\nline.1.unit_price=60.00\nline.1.total=180.00\n"
    b"line.1.product_code=SKU-B-002\n",
]

PAGE_PRODUCTS_AMBIGUOUS = [
    b"invoice.number=INV-PC-AMBIG-1\ninvoice.date=2026-10-08\n"
    b"total.net=500.00\ntax.amount=40\n"
    b"line.0.quantity=2\nline.0.unit_price=250.00\nline.0.total=500.00\n"
    b"line.0.product_code=SKU-X-1\nline.0.product_code=SKU-X-2\n",
]

PC_FIELD_0 = "line.0.product_code"
PC_FIELD_1 = "line.1.product_code"
PC_KIND = "SKU"

_PC_SEQ = {"n": 0}


def unique_product_pages(codes=(PC_FIELD_0 + "=SKU-A-001",
                                PC_FIELD_1 + "=SKU-B-002"),
                         qty="2", unit="500.00", total="1000.00",
                         qty2="3", unit2="60.00", total2="180.00"):
    """Distinct product-bearing pages (unique invoice number, TWO declared
    lines) — each call produces a different capture S1, so multiple invoices
    coexist in one test. `codes` are raw `field=value` page lines."""
    _PC_SEQ["n"] += 1
    n = _PC_SEQ["n"]
    body = "".join(f"{code}\n" for code in codes)
    return [f"invoice.number=INV-PC-SEQ-{n:04d}\ninvoice.date=2026-10-08\n"
            f"total.net=1180.00\ntax.amount=94.40\n"
            f"line.0.quantity={qty}\nline.0.unit_price={unit}\n"
            f"line.0.total={total}\n"
            f"line.1.quantity={qty2}\nline.1.unit_price={unit2}\n"
            f"line.1.total={total2}\n{body}".encode("utf-8")]


class ProductCandidateStack(CanonicalAssemblyStack):
    """The P6.2 composition PLUS the WP-8.1 product store/service — the
    WP-8.1 stack under test. All assembly machinery is the VERBATIM P6.2
    stack (the matching layer consumes it, never bypasses it)."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db,
                 norm_db, deriv_db, val_db, vsm_db, gate_db, assembly_db,
                 product_db, with_evidence=True, engines=None, rules=None,
                 extra_rules=(), formulas=None, norm_rulesets=None):
        super().__init__(capture_db, recon_db, extraction_db, binding_db,
                         norm_db, deriv_db, val_db, vsm_db, gate_db,
                         assembly_db, with_evidence=with_evidence,
                         engines=engines, rules=rules, extra_rules=extra_rules,
                         formulas=formulas, norm_rulesets=norm_rulesets)
        self.product_db = product_db
        self._pcs1 = S1Service()
        self.product_store = ProductCandidateStore(product_db, self._pcs1)
        self.products = ProductCandidateService(
            self.product_store, self.assembly, self._pcs1)

    # -- pipeline helpers --------------------------------------------------

    def assemble_products_invoice(self, parts=None, label="pc-test",
                                  binding=None):
        """Full happy path: capture → … → P6.1 ACCEPTED admission → P6.2
        issued invoice over the product corpus (or any declared parts).
        Returns (assembly_outcome, invoice_id)."""
        state_parts = PAGE_PRODUCTS_OK if parts is None else parts
        gate_outcome = self.build_accepted_lines_admission(
            parts=state_parts, label=label)
        assert isinstance(gate_outcome, CanonicalizationAccepted), gate_outcome
        invoice_id = gate_outcome.canonical_invoice.canonical_invoice_id
        assembled = self.assemble_ok(invoice_id)
        return assembled, invoice_id

    def register(self, kind=PC_KIND, value="SKU-A-001"):
        outcome = self.products.register_catalog_identity(kind, value)
        assert isinstance(outcome, (CatalogIdentityRegistered,
                                    CatalogIdentityReplay)), outcome
        return outcome

    def match(self, invoice_id, field_name=PC_FIELD_0, kind=PC_KIND):
        outcome = self.products.match(invoice_id, field_name, kind)
        assert isinstance(outcome, (ProductExactMatched,
                                    ProductReferenceUnresolved,
                                    ProductMatchReplay)), outcome
        return outcome

    def read_invoice(self, invoice_id):
        read = self.assembly.read_assembled_invoice(invoice_id)
        assert isinstance(read, AssemblyReadSuccess), read
        return read

    def close(self):
        self.product_store.close()
        super().close()


__all__ = [
    "CanonicalAssemblyStack", "ProductCandidateStack",
    "ProductCandidateStore", "ProductCandidateService",
    "LINE_BINDING", "PAGE_LINES_OK", "unique_line_pages",
    "PAGE_PRODUCTS_OK", "PAGE_PRODUCTS_AMBIGUOUS", "unique_product_pages",
    "PC_FIELD_0", "PC_FIELD_1", "PC_KIND",
    "AssemblyCompleted", "AssemblyReadSuccess", "CanonicalizationAccepted",
    "CatalogIdentityRegistered", "CatalogIdentityReplay",
    "CatalogReadSuccess", "ProductExactMatched",
    "ProductReferenceUnresolved", "ProductMatchReplay",
    "ProductMatchRequestRefused", "ProductMatchInputIntegrityFailure",
    "ProductMatchReadSuccess",
]
