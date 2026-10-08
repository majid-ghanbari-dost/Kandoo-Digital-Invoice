"""Shared helpers for the WP-10.1 digital-invoice lifecycle tests (unique
module name — safe for combined collection with all prior suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → digital_invoice → src
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
from digital_invoice import (  # noqa: E402
    DigitalInvoiceLifecycleService,
    DigitalInvoiceLifecycleService as _Svc,  # noqa: F401 (alias stability)
    DigitalInvoiceOpenReplay,
    DigitalInvoiceOpened,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceStore,
    LifecycleAdvanced,
    LifecycleReplay,
)
from capture import S1Service  # noqa: E402

# Line-structured corpus (the P6.2 LINE_BINDING declaration fits verbatim).
PAGE_DI_OK = [
    b"invoice.number=INV-DI-2026-001\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n"
    b"line.1.quantity=3\nline.1.unit_price=60.00\nline.1.total=180.00\n",
]

_DI_SEQ = {"n": 0}


def unique_di_pages():
    """Distinct pages (unique invoice number) — each call produces a
    different capture S1, so multiple invoices coexist in one test."""
    _DI_SEQ["n"] += 1
    n = _DI_SEQ["n"]
    return [f"invoice.number=INV-DI-SEQ-{n:04d}\ninvoice.date=2026-10-08\n"
            f"total.net=1180.00\ntax.amount=94.40\n"
            f"line.0.quantity=2\nline.0.unit_price=500.00\n"
            f"line.0.total=1000.00\n".encode("utf-8")]


class DigitalInvoiceStack(CanonicalAssemblyStack):
    """The P6.2 composition PLUS the WP-10.1 lifecycle store/service — the
    WP-10.1 stack under test. All assembly machinery is the VERBATIM P6.2
    stack (the lifecycle layer consumes it, never bypasses it)."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db,
                 norm_db, deriv_db, val_db, vsm_db, gate_db, assembly_db,
                 digital_db, with_evidence=True, engines=None, rules=None,
                 extra_rules=(), formulas=None, norm_rulesets=None):
        super().__init__(capture_db, recon_db, extraction_db, binding_db,
                         norm_db, deriv_db, val_db, vsm_db, gate_db,
                         assembly_db, with_evidence=with_evidence,
                         engines=engines, rules=rules, extra_rules=extra_rules,
                         formulas=formulas, norm_rulesets=norm_rulesets)
        self.digital_db = digital_db
        self._dis1 = S1Service()
        self.digital_store = DigitalInvoiceStore(digital_db, self._dis1)
        self.di = DigitalInvoiceLifecycleService(
            self.digital_store, self.assembly, self._dis1)

    # -- pipeline helpers --------------------------------------------------

    def assemble_di_invoice(self, parts=None, label="di-test",
                            binding=None):
        """Full happy path: capture → … → P6.1 ACCEPTED admission → P6.2
        issued invoice. Returns (assembly_outcome, invoice_id)."""
        state_parts = PAGE_DI_OK if parts is None else parts
        gate_outcome = self.build_accepted_lines_admission(
            parts=state_parts, label=label)
        assert isinstance(gate_outcome, CanonicalizationAccepted), gate_outcome
        invoice_id = gate_outcome.canonical_invoice.canonical_invoice_id
        assembled = self.assemble_ok(invoice_id)
        return assembled, invoice_id

    def open_ok(self, invoice_id):
        outcome = self.di.open_digital_invoice(invoice_id)
        assert isinstance(outcome, DigitalInvoiceOpened), outcome
        return outcome

    def advance_ok(self, invoice_id, act, *args, **kwargs):
        outcome = getattr(self.di, act)(invoice_id, *args, **kwargs)
        assert isinstance(outcome, (LifecycleAdvanced, LifecycleReplay)), \
            outcome
        return outcome

    def read_ok(self, invoice_id):
        read = self.di.read_digital_invoice(invoice_id)
        assert isinstance(read, DigitalInvoiceReadSuccess), read
        return read

    def close(self):
        self.digital_store.close()
        super().close()


__all__ = [
    "CanonicalAssemblyStack", "DigitalInvoiceStack",
    "DigitalInvoiceStore", "DigitalInvoiceLifecycleService",
    "LINE_BINDING", "unique_di_pages", "PAGE_DI_OK",
    "AssemblyReadSuccess", "CanonicalizationAccepted",
    "DigitalInvoiceOpened", "DigitalInvoiceOpenReplay",
    "DigitalInvoiceReadSuccess", "LifecycleAdvanced", "LifecycleReplay",
]
