"""Shared helpers for the WP-6.2 canonical-assembly tests (unique module name
— safe for combined collection with the capture/reconstruction/extraction/
normalization/derivation/validation/validation_domain/canonicalization
suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → canonical_assembly → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CG_TESTS = SRC / "canonicalization" / "tests"
if str(CG_TESTS) not in sys.path:
    sys.path.insert(0, str(CG_TESTS))

from cg_helpers import (  # noqa: E402  (P6.1 helpers reused verbatim)
    BINDING as IDENTITY_BINDING,
    CanonicalizationStack,
    unique_identity_pages,
)
from canonical_assembly import (  # noqa: E402
    AssemblyCompleted,
    CanonicalAssemblyService,
    CanonicalAssemblyStore,
    ORIGIN_HOLOO_CAPTURE,
)
from capture import S1Service  # noqa: E402

# Line-structured corpus — the identity fields ride alongside DECLARED line
# fields (engine-vocabulary names relayed verbatim; text-kind fallback in the
# frozen ruleset profile — assembly performs NO numeric interpretation).
PAGE_LINES_OK = [
    b"invoice.number=INV-CA-2026-001\ninvoice.date=2026-10-08\n"
    b"total.net=1180.00\ntax.amount=94.40\n"
    b"line.0.quantity=2\nline.0.unit_price=500.00\nline.0.total=1000.00\n"
    b"line.1.quantity=3\nline.1.unit_price=60.00\nline.1.total=180.00\n",
]

# Declared line structure — line keys deliberately declared OUT of order in a
# dict to prove the assembly ordering is explicit (sorted), never dict-order.
LINE_BINDING = {
    1: {"LINE_QUANTITY": "line.1.quantity",
        "LINE_UNIT_PRICE": "line.1.unit_price",
        "LINE_TOTAL": "line.1.total"},
    0: {"LINE_QUANTITY": "line.0.quantity",
        "LINE_UNIT_PRICE": "line.0.unit_price",
        "LINE_TOTAL": "line.0.total"},
}

# An ambiguous declared field: two usable NORMALIZED rows → the whole request
# is refused (never auto-resolution).
PAGE_LINE_AMBIGUOUS = [
    b"invoice.number=INV-CA-AMBIG-1\ninvoice.date=2026-10-08\n"
    b"total.net=500.00\ntax.amount=40\n"
    b"line.0.quantity=2\nline.0.quantity=9\n"
    b"line.0.unit_price=250.00\nline.0.total=500.00\n",
]

# A partially-absent line: quantity present, unit_price/total absent → the
# line is assembled with explicitly ABSENT roles (no invention).
PAGE_LINE_PARTIAL = [
    b"invoice.number=INV-CA-PARTIAL-1\ninvoice.date=2026-10-08\n"
    b"total.net=700.00\ntax.amount=56\n"
    b"line.0.quantity=7\n"
    b"line.1.quantity=1\nline.1.unit_price=700.00\nline.1.total=700.00\n",
]

# An all-absent line: NOTHING usable for any role → the line is REJECTED
# (explicit, never stored).
PAGE_LINE_EMPTY = [
    b"invoice.number=INV-CA-EMPTY-1\ninvoice.date=2026-10-08\n"
    b"total.net=700.00\ntax.amount=56\n"
    b"line.1.quantity=1\nline.1.unit_price=700.00\nline.1.total=700.00\n",
]

EMPTY_LINE_BINDING = {
    0: {"LINE_QUANTITY": "line.0.quantity",
        "LINE_UNIT_PRICE": "line.0.unit_price",
        "LINE_TOTAL": "line.0.total"},
    1: {"LINE_QUANTITY": "line.1.quantity",
        "LINE_UNIT_PRICE": "line.1.unit_price",
        "LINE_TOTAL": "line.1.total"},
}

_PAGE_SEQ = {"n": 0}


def unique_line_pages(qty="2", unit="500.00", total="1000.00",
                      net="1180.00", tax="94.40",
                      qty2="3", unit2="60.00", total2="180.00"):
    """Distinct line-structured pages (unique invoice number, TWO declared
    lines matching LINE_BINDING) — each call produces a different capture S1,
    so multiple admissions coexist in one test."""
    _PAGE_SEQ["n"] += 1
    n = _PAGE_SEQ["n"]
    return [f"invoice.number=INV-CA-SEQ-{n:04d}\ninvoice.date=2026-10-08\n"
            f"total.net={net}\ntax.amount={tax}\n"
            f"line.0.quantity={qty}\nline.0.unit_price={unit}\n"
            f"line.0.total={total}\n"
            f"line.1.quantity={qty2}\nline.1.unit_price={unit2}\n"
            f"line.1.total={total2}\n".encode("utf-8")]


class CanonicalAssemblyStack(CanonicalizationStack):
    """The P6.1 composition PLUS the WP-6.2 assembly store/service — the
    WP-6.2 stack under test. All test-declared probe rules are pre-registered
    by the parent stack."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db,
                 norm_db, deriv_db, val_db, vsm_db, gate_db, assembly_db,
                 with_evidence=True, engines=None, rules=None,
                 extra_rules=(), formulas=None, norm_rulesets=None):
        super().__init__(capture_db, recon_db, extraction_db, binding_db,
                         norm_db, deriv_db, val_db, vsm_db, gate_db,
                         with_evidence=with_evidence, engines=engines,
                         rules=rules, extra_rules=extra_rules,
                         formulas=formulas, norm_rulesets=norm_rulesets)
        self.assembly_db = assembly_db
        self.assembly_store = CanonicalAssemblyStore(assembly_db, S1Service())
        self.assembly = CanonicalAssemblyService(
            self.assembly_store, self.gate, self.norm, self.deriv,
            S1Service())

    # -- pipeline helpers --------------------------------------------------

    def build_accepted_lines_admission(self, parts=None, label="ca-test",
                                       binding=None, ruleset_id="kandoo-ca-rules",
                                       origin=ORIGIN_HOLOO_CAPTURE):
        """Full happy path: capture → … → P6.1 gate decision over the
        line-structured corpus (or any declared parts). Returns the gate
        outcome for the projected domain state."""
        state_parts = PAGE_LINES_OK if parts is None else parts
        nid = self.build_derived(state_parts, label=label)
        self.validate_all_reference(nid)
        projection = self.project(nid, list(self.REF_KEYS_DEFAULT),
                                  ruleset_id=ruleset_id,
                                  ruleset_version="1")
        outcome = self.gate.canonicalize(
            projection.record.domain_state_id, origin,
            IDENTITY_BINDING if binding is None else binding)
        return outcome

    def assemble_ok(self, canonical_invoice_id, line_binding=LINE_BINDING):
        outcome = self.assembly.assemble(canonical_invoice_id, line_binding)
        assert isinstance(outcome, AssemblyCompleted), outcome
        return outcome

    def close(self):
        self.assembly_store.close()
        super().close()


# The default reference-projection keys (reused from the P5.1 helpers via the
# parent stack's module import surface).
from cg_helpers import REF_KEYS as _REF_KEYS  # noqa: E402
CanonicalAssemblyStack.REF_KEYS_DEFAULT = _REF_KEYS
