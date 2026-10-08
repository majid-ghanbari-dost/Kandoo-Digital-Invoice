"""WP-8.1 durability tests — restart safety, the tamper matrix (own row /
hash-consistent forged row / linked invoice / linked catalog identity),
zero-residue forced failure, concurrency (INV-PM-1:1 race), and
deployment-order determinism (SPEC §6/§7; OD-PM1/PM4/PM5)."""
import sqlite3
import threading

import pytest

from pc_helpers import (
    PC_FIELD_0,
    PC_KIND,
    PAGE_PRODUCTS_OK,
    ProductCandidateStack,
    unique_product_pages,
)
from product_candidate import (
    CatalogReadSuccess,
    ProductCandidateService,
    ProductCandidateStore,
    ProductExactMatched,
    ProductMatchReadSuccess,
    ProductMatchReplay,
    ProductReferenceUnresolved,
)
from capture import S1Service


# ---------------------------------------------------------------------------
# Restart durability
# ---------------------------------------------------------------------------

def test_matches_survive_restart_and_reverify(stack, make_stack):
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-restart")
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductExactMatched)
    stack.close()
    reopened = make_stack()
    try:
        read = reopened.products.read_match_by_id(outcome.record.match_id)
        assert isinstance(read, ProductMatchReadSuccess), read
        assert read.record == outcome.record
        assert read.catalog_identity == outcome.catalog_identity
        replay = reopened.match(invoice_id, PC_FIELD_0, PC_KIND)
        assert isinstance(replay, ProductMatchReplay)   # replay, not re-decide
        assert replay.record == outcome.record
    finally:
        reopened.close()


def test_unresolved_facts_survive_restart(stack, make_stack):
    _, invoice_id = stack.assemble_products_invoice(label="pm-restart-unres")
    outcome = stack.products.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(outcome, ProductReferenceUnresolved)
    stack.close()
    reopened = make_stack()
    try:
        read = reopened.products.read_match_by_id(outcome.record.match_id)
        assert isinstance(read, ProductMatchReadSuccess), read
        assert read.record.match_outcome == "UNRESOLVED"
        assert read.catalog_identity is None
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# Tamper matrix — every tampered layer withholds content
# ---------------------------------------------------------------------------

def test_tampered_match_row_is_withheld_never_served(stack):
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-tamper-own")
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    conn = sqlite3.connect(str(stack.product_db))
    try:
        conn.execute("UPDATE product_matches SET declared_field_name = "
                     "'line.9.product_code' WHERE match_id = ?",
                     (outcome.record.match_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.products.read_match_by_id(outcome.record.match_id)
    assert type(read).__name__ == "ProductMatchReadIntegrityFailure", read


def test_tampered_outcome_flip_is_withheld(stack):
    """Flipping EXACT_MATCHED → UNRESOLVED breaks the hash AND the shape
    gates — the row is never served either way."""
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-tamper-flip")
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    conn = sqlite3.connect(str(stack.product_db))
    try:
        # a realistic adversary edits the whole shape (the CHECK gates alone
        # would refuse a half-flip — proven separately by direct-SQL probes)
        conn.execute("UPDATE product_matches SET match_outcome = "
                     "'UNRESOLVED', catalog_identity_id = '', "
                     "unresolved_reason = 'no-catalog-identity' "
                     "WHERE match_id = ?", (outcome.record.match_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.products.read_match_by_id(outcome.record.match_id)
    assert type(read).__name__ == "ProductMatchReadIntegrityFailure", read


def test_hash_consistent_forged_row_is_caught_by_structural_gates(stack):
    """The strongest adversary: a row re-fingerprinted AFTER editing — own
    VOR passes but the cross-store gates (invoice anchor / pointer re-join /
    live byte-identity) withhold it."""
    from product_candidate.store import canonical_match_bytes
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-forge")
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    record = outcome.record
    forged_id = "forged-match-id"
    conn = sqlite3.connect(str(stack.product_db))
    try:
        conn.execute("DELETE FROM product_matches WHERE match_id = ?",
                     (record.match_id,))
        conn.execute(
            "INSERT INTO product_matches (match_id, invoice_id, capture_s1,"
            " capture_s1_algorithm_id, declared_field_name, canonical_seq,"
            " provenance, identifier_kind, match_outcome, "
            "catalog_identity_id, unresolved_reason, created_at, "
            "record_fingerprint, fingerprint_algorithm_id) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (forged_id, record.invoice_id, "forged-s1", "sha256-v1",
             record.declared_field_name, record.canonical_seq,
             record.provenance, record.identifier_kind, "EXACT_MATCHED",
             record.catalog_identity_id, "", record.created_at, "", ""))
        conn.commit()
    finally:
        conn.close()
    # re-fingerprint the forged row with the REAL S1 service (own VOR passes)
    from product_candidate.model import ProductMatchRecord
    row = sqlite3.connect(str(stack.product_db))
    try:
        got = row.execute("SELECT * FROM product_matches WHERE match_id = ?",
                          (forged_id,)).fetchone()
        cols = [d[0] for d in row.execute(
            "SELECT * FROM product_matches LIMIT 1").description]
        forged = ProductMatchRecord(**dict(zip(cols, got)))
        fp = S1Service().compute(canonical_match_bytes(forged))
        row.execute("UPDATE product_matches SET record_fingerprint = ?, "
                    "fingerprint_algorithm_id = ? WHERE match_id = ?",
                    (fp.s1, fp.s1_algorithm_id, forged_id))
        row.commit()
    finally:
        row.close()
    read = stack.products.read_match_by_id(forged_id)
    assert type(read).__name__ == "ProductMatchReadVerificationUnavailable", \
        read
    assert any("anchor" in issue or "re-join" in issue
               for issue in stack.products.issue_reports)


def test_tampered_linked_invoice_withholds_the_match(stack):
    """The linked P6.2 invoice is tampered → the match read withholds
    (fail-closed linked re-verification), while the match row itself stays
    hash-intact."""
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-tamper-inv")
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        conn.execute("UPDATE canonical_invoices SET capture_s1 = 'forged-s1' "
                     "WHERE invoice_id = ?", (invoice_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.products.read_match_by_id(outcome.record.match_id)
    assert type(read).__name__ in ("ProductMatchReadVerificationUnavailable",
                                   "ProductMatchReadIntegrityFailure"), read


def test_tampered_linked_catalog_identity_withholds_the_match(stack):
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-tamper-cat")
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    conn = sqlite3.connect(str(stack.product_db))
    try:
        conn.execute("UPDATE catalog_identities SET identifier_value = "
                     "'tampered' WHERE catalog_identity_id = ?",
                     (outcome.record.catalog_identity_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.products.read_match_by_id(outcome.record.match_id)
    assert type(read).__name__ in ("ProductMatchReadIntegrityFailure",
                                   "ProductMatchReadVerificationUnavailable"), \
        read


def test_tampered_invoice_value_breaks_the_live_byte_identity(stack):
    """Editing the canonical FIELD value (not the anchors) → the LIVE
    byte-identity re-proof fails → withheld."""
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-tamper-val")
    outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        conn.execute("UPDATE canonical_fields SET canonical_value = "
                     "'SKU-TAMPERED' WHERE invoice_id = ? AND canonical_seq "
                     "= ?", (invoice_id, outcome.record.canonical_seq))
        conn.commit()
    finally:
        conn.close()
    read = stack.products.read_match_by_id(outcome.record.match_id)
    # the invoice's own VOR catches the edit (its fingerprint covers fields)
    assert type(read).__name__ in ("ProductMatchReadVerificationUnavailable",
                                   "ProductMatchReadIntegrityFailure"), read


# ---------------------------------------------------------------------------
# Zero residue under forced failure
# ---------------------------------------------------------------------------

def test_forced_storage_failure_leaves_zero_residue(stack, monkeypatch):
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-forced")
    original = stack.product_store.commit_match

    def boom(_record):
        from product_candidate import ProductCandidatePersistenceUnavailable
        raise ProductCandidatePersistenceUnavailable("forced failure")

    monkeypatch.setattr(stack.product_store, "commit_match", boom)
    outcome = stack.products.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert type(outcome).__name__ == "ProductMatchStorageUnavailable", outcome
    monkeypatch.setattr(stack.product_store, "commit_match", original)
    # zero residue — the next attempt is a FIRST match, not a replay
    retry = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    assert isinstance(retry, ProductExactMatched)
    assert len(stack.products.matches()) == 1


def test_fingerprint_capability_failure_is_explicit_zero_residue(
        stack, monkeypatch):
    from capture import S1ComputationFailure
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-fpcap")

    def boom(_bytes):
        raise S1ComputationFailure("forced capability loss")

    original = stack.product_store._s1.compute
    monkeypatch.setattr(stack.product_store._s1, "compute", boom)
    outcome = stack.products.match(invoice_id, PC_FIELD_0, PC_KIND)
    monkeypatch.setattr(stack.product_store._s1, "compute", original)
    assert type(outcome).__name__ == "ProductMatchStorageUnavailable", outcome
    assert len(stack.products.matches()) == 0


# ---------------------------------------------------------------------------
# Concurrency — INV-PM-1:1 with the UNIQUE backstop (never Python-only)
#
# Project precedent (WP-7.1/WP-7.2 build records): full-stack thread races
# expose the FROZEN layers' own concurrent-read behavior — out of this WP's
# boundary. The race here uses thread-local product stores + an inert
# assembly stub holding a PRE-READ verified outcome, so ONLY the match
# layer is raced.
# ---------------------------------------------------------------------------

class _StubAssembly:
    """Inert assembly service: returns the PRE-READ verified outcome (never
    touches a store)."""

    def __init__(self, invoice_read):
        self._invoice_read = invoice_read

    def read_assembled_invoice(self, invoice_id):
        from canonical_assembly import AssemblyReadRefused
        if self._invoice_read.invoice.invoice_id != invoice_id:
            return AssemblyReadRefused(invoice_id, "stub: unknown invoice")
        return self._invoice_read


def test_eight_thread_same_declaration_race_yields_one_match(stack):
    stack.register("SKU", "SKU-A-001")
    assembled, invoice_id = stack.assemble_products_invoice(
        label="pm-race")
    pre_read = stack.assembly.read_assembled_invoice(invoice_id)
    assert len(stack.products.matches()) == 0   # the race is over the ONE row
    product_db = stack.product_db
    results = []
    errors = []
    barrier = threading.Barrier(8)

    def worker():
        s1 = S1Service()
        store = ProductCandidateStore(product_db, s1)
        service = ProductCandidateService(store, _StubAssembly(pre_read), s1)
        try:
            barrier.wait()
            results.append(service.match(invoice_id, PC_FIELD_0, PC_KIND))
        except Exception as exc:      # pragma: no cover
            errors.append(repr(exc))
        finally:
            store.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    matched = [r for r in results if isinstance(r, ProductExactMatched)]
    replays = [r for r in results if isinstance(r, ProductMatchReplay)]
    assert len(matched) == 1
    assert len(replays) == 7
    winner = matched[0].record
    assert all(r.record == winner for r in replays)
    assert len(stack.products.matches()) == 1


# ---------------------------------------------------------------------------
# Deployment-order determinism
# ---------------------------------------------------------------------------

def test_deployment_order_determinism_of_the_durable_match(tmp_path):
    """The SAME scenario executed in two cold, independent environments
    yields the SAME durable match content (every non-bookkeeping scalar) —
    the match fact is a pure function of the verified content (OD-PM4)."""
    results = []
    for run in range(2):
        base = tmp_path / f"run-{run}"
        base.mkdir()
        stack = ProductCandidateStack(
            base / "capture.db", base / "recon.db", base / "extraction.db",
            base / "bindings.db", base / "norm.db", base / "deriv.db",
            base / "val.db", base / "vsm.db", base / "gate.db",
            base / "assembly.db", base / "product.db")
        try:
            stack.register("SKU", "SKU-A-001")
            catalog = stack.products.catalog()
            # the corpus is BYTE-IDENTICAL across the two cold runs — the
            # determinism claim is about the same content, not unique content
            _, invoice_id = stack.assemble_products_invoice(
                parts=PAGE_PRODUCTS_OK, label="pm-det")
            outcome = stack.match(invoice_id, PC_FIELD_0, PC_KIND)
            read = stack.products.read_match_by_id(outcome.record.match_id)
            assert isinstance(read, ProductMatchReadSuccess)
            results.append({
                "catalog": [(c.identifier_kind, c.identifier_value)
                            for c in catalog],
                "semantic": (outcome.record.declared_field_name,
                             outcome.record.canonical_seq,
                             outcome.record.provenance,
                             outcome.record.identifier_kind,
                             outcome.record.match_outcome,
                             outcome.record.unresolved_reason),
                "invoice_id": invoice_id,
                "capture_s1": outcome.record.capture_s1,
                "catalog_value": read.catalog_identity.identifier_value,
            })
        finally:
            stack.close()
    assert results[0]["catalog"] == results[1]["catalog"]
    assert results[0]["semantic"] == results[1]["semantic"]
    assert results[0]["invoice_id"] != results[1]["invoice_id"]  # fresh Kandoo
    assert results[0]["capture_s1"] == results[1]["capture_s1"]  # same bytes
    assert results[0]["catalog_value"] == results[1]["catalog_value"]
