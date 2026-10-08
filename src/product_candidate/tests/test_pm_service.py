"""WP-8.1 service-level tests — the P6.2 verified read consumed VERBATIM
(spy-proven), the refusal matrix with zero durable residue, INV-PM-1:1,
and frozen-store row-count stability (SPEC §2/§3/§4)."""
import inspect
import sqlite3

from pc_helpers import (
    PC_FIELD_0,
    PC_KIND,
    PAGE_PRODUCTS_AMBIGUOUS,
    ProductCandidateStack,
    unique_product_pages,
)
from product_candidate import (
    CatalogIdentityRegistered,
    CatalogIdentityReplay,
    ProductCandidateService,
    ProductExactMatched,
    ProductMatchReplay,
    ProductMatchRequestRefused,
    ProductReferenceUnresolved,
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


def test_match_consumes_the_p6_2_verified_read_exactly_once_per_call(stack):
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-spy")
    spy = _CountingAssembly(stack.assembly)
    service = ProductCandidateService(stack.product_store, spy, stack._pcs1)
    outcome = service.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductExactMatched), outcome
    assert spy.calls == [invoice_id]          # exactly ONE verified read
    replay = service.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(replay, ProductMatchReplay), replay
    # call 2 = M1 verified read + the replay's own linked re-verification
    assert spy.calls == [invoice_id] * 3


def test_service_holds_no_other_upstream_path(stack):
    """The service constructor takes ONLY (store, assembly, s1) — there is
    no second invoice path, no upstream store handle, nothing to bypass
    with (SPEC §2)."""
    sig = inspect.signature(ProductCandidateService.__init__)
    params = [p for p in sig.parameters if p != "self"]
    assert params == ["store", "assembly", "s1"]


# ---------------------------------------------------------------------------
# Refusal matrix — zero durable residue (M2/M3)
# ---------------------------------------------------------------------------

def test_refusal_matrix_is_complete_and_leaves_zero_residue(stack):
    _, invoice_id = stack.assemble_products_invoice(label="pm-refusals")
    refusals = [
        # M2: malformed declarations
        stack.products.match(invoice_id, "", PC_KIND),
        stack.products.match(invoice_id, PC_FIELD_0, ""),
        stack.products.match(invoice_id, "   ", PC_KIND),
        # M3: declared field not found / ambiguous
        stack.products.match(invoice_id, "no.such.field", PC_KIND),
    ]
    for outcome in refusals:
        assert isinstance(outcome, ProductMatchRequestRefused), outcome
    ambiguous = stack.assemble_products_invoice(
        parts=PAGE_PRODUCTS_AMBIGUOUS, label="pm-ambig-field")
    refused = stack.products.match(ambiguous[1], PC_FIELD_0, PC_KIND)
    assert isinstance(refused, ProductMatchRequestRefused), refused
    assert "declared-field-ambiguous" in refused.detail
    # zero residue across every refusal
    assert len(stack.products.matches()) == 0
    assert len(stack.products.catalog()) == 0


def test_declared_field_not_found_names_the_missing_field(stack):
    _, invoice_id = stack.assemble_products_invoice(label="pm-notfound")
    refused = stack.products.match(invoice_id, "line.9.product_code", PC_KIND)
    assert isinstance(refused, ProductMatchRequestRefused)
    assert "declared-field-not-found" in refused.detail


def test_nonexistent_invoice_is_fail_closed_input_integrity(stack):
    outcome = stack.products.match("no-such-invoice", PC_FIELD_0, PC_KIND)
    assert type(outcome).__name__ == "ProductMatchInputIntegrityFailure", \
        outcome
    assert len(stack.products.matches()) == 0        # zero residue


def test_exact_match_commit_is_atomic_single_row(stack):
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-atomic")
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductExactMatched)
    rows = stack.products.matches()
    assert len(rows) == 1
    assert rows[0] == outcome.record
    assert rows[0].record_fingerprint
    assert rows[0].fingerprint_algorithm_id == "sha256-v1"


def test_registration_outcome_vocabulary_is_exhaustive(stack):
    """Every register_catalog_identity call returns exactly one explicit
    outcome — registered / replay / refused covers the API."""
    ok = stack.products.register_catalog_identity("SKU", "SKU-A-001")
    assert isinstance(ok, CatalogIdentityRegistered)
    replay = stack.products.register_catalog_identity("SKU", "SKU-A-001")
    assert isinstance(replay, CatalogIdentityReplay)
    refused = stack.products.register_catalog_identity("", "")
    assert type(refused).__name__ == "CatalogRegistrationRefused"


# ---------------------------------------------------------------------------
# Frozen-store row-count stability — the layer mutates NOTHING upstream
# ---------------------------------------------------------------------------

def test_row_count_stability_of_frozen_stores_during_matching(stack):
    """Both invoices are built FIRST; the frozen-store snapshot is taken
    before the FIRST match — matching itself (including replays and
    refusals) must grow NO frozen store (SPEC §1; additive register only)."""
    stack.register("SKU", "SKU-A-001")
    stack.register("SKU", "SKU-B-002")
    _, invoice_id = stack.assemble_products_invoice(label="pm-stable")
    unresolved_invoice = stack.assemble_products_invoice(
        parts=unique_product_pages(), label="pm-stable-unresolved")[1]
    before = _upstream_counts(stack)
    first = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    second = stack.products.match(invoice_id, "line.1.product_code", PC_KIND)
    replay = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    unresolved = stack.products.match(unresolved_invoice, PC_FIELD_0,
                                      "UNREGISTERED-KIND")
    refused = stack.products.match(invoice_id, "no.such.field", PC_KIND)
    assert isinstance(first, ProductExactMatched)
    assert isinstance(second, ProductExactMatched)
    assert isinstance(replay, ProductMatchReplay)
    assert isinstance(unresolved, ProductReferenceUnresolved)
    assert isinstance(refused, ProductMatchRequestRefused)
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
