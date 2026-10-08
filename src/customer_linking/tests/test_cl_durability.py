"""WP-9.1 durability tests — restart safety, the tamper matrix (own row /
hash-consistent forged row / linked invoice / linked customer identity),
zero-residue forced failure, concurrency (INV-CL-1:1 race), and
deployment-order determinism (SPEC §6/§7; OD-CL1/CL4/CL5)."""
import sqlite3
import threading

from cl_helpers import (
    CL_FIELD,
    CL_KIND,
    CL_VALUE,
    PAGE_CUSTOMERS_OK,
    CustomerLinkingStack,
    unique_customer_pages,
)
from customer_linking import (
    CustomerLinkingService,
    CustomerLinkingStore,
    CustomerLinked,
    CustomerLinkReadSuccess,
    CustomerLinkReplay,
    CustomerLinkUnresolved,
)
from capture import S1Service


# ---------------------------------------------------------------------------
# Restart durability
# ---------------------------------------------------------------------------

def test_links_survive_restart_and_reverify(stack, make_stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-restart")
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinked)
    stack.close()
    reopened = make_stack()
    try:
        read = reopened.customers_svc.read_link_by_id(outcome.record.link_id)
        assert isinstance(read, CustomerLinkReadSuccess), read
        assert read.record == outcome.record
        assert read.customer_identity == outcome.customer_identity
        replay = reopened.link(invoice_id, CL_FIELD, CL_KIND)
        assert isinstance(replay, CustomerLinkReplay)   # replay, not re-decide
        assert replay.record == outcome.record
    finally:
        reopened.close()


def test_unresolved_facts_survive_restart(stack, make_stack):
    _, invoice_id = stack.assemble_customers_invoice(label="cl-restart-unres")
    outcome = stack.customers_svc.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(outcome, CustomerLinkUnresolved)
    stack.close()
    reopened = make_stack()
    try:
        read = reopened.customers_svc.read_link_by_id(outcome.record.link_id)
        assert isinstance(read, CustomerLinkReadSuccess), read
        assert read.record.link_outcome == "UNRESOLVED"
        assert read.customer_identity is None
    finally:
        reopened.close()


# ---------------------------------------------------------------------------
# Tamper matrix — every tampered layer withholds content
# ---------------------------------------------------------------------------

def test_tampered_link_row_is_withheld_never_served(stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-tamper-own")
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    conn = sqlite3.connect(str(stack.customer_db))
    try:
        conn.execute("UPDATE customer_links SET declared_field_name = "
                     "'customer.forged' WHERE link_id = ?",
                     (outcome.record.link_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.customers_svc.read_link_by_id(outcome.record.link_id)
    assert type(read).__name__ == "CustomerLinkReadIntegrityFailure", read


def test_tampered_outcome_flip_is_withheld(stack):
    """A realistic adversary edits the whole shape — the hash breaks and the
    row is withheld (the CHECK gates alone refuse half-flips; proven
    separately by direct-SQL probes)."""
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-tamper-flip")
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    conn = sqlite3.connect(str(stack.customer_db))
    try:
        conn.execute("UPDATE customer_links SET link_outcome = "
                     "'UNRESOLVED', customer_identity_id = '', "
                     "unresolved_reason = 'no-customer-identity' "
                     "WHERE link_id = ?", (outcome.record.link_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.customers_svc.read_link_by_id(outcome.record.link_id)
    assert type(read).__name__ == "CustomerLinkReadIntegrityFailure", read


def test_hash_consistent_forged_row_is_caught_by_structural_gates(stack):
    """The strongest adversary: a row re-fingerprinted AFTER editing — own
    VOR passes but the cross-store gates (invoice anchor / pointer re-join /
    live byte-identity) withhold it."""
    from customer_linking.store import canonical_link_bytes
    from customer_linking.model import CustomerLinkRecord
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-forge")
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    record = outcome.record
    forged_id = "forged-link-id"
    conn = sqlite3.connect(str(stack.customer_db))
    try:
        conn.execute("DELETE FROM customer_links WHERE link_id = ?",
                     (record.link_id,))
        conn.execute(
            "INSERT INTO customer_links (link_id, invoice_id, capture_s1,"
            " capture_s1_algorithm_id, declared_field_name, canonical_seq,"
            " provenance, identifier_kind, link_outcome, "
            "customer_identity_id, unresolved_reason, created_at, "
            "record_fingerprint, fingerprint_algorithm_id) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (forged_id, record.invoice_id, "forged-s1", "sha256-v1",
             record.declared_field_name, record.canonical_seq,
             record.provenance, record.identifier_kind, "LINKED",
             record.customer_identity_id, "", record.created_at, "", ""))
        conn.commit()
    finally:
        conn.close()
    # re-fingerprint the forged row with the REAL S1 service (own VOR passes)
    row = sqlite3.connect(str(stack.customer_db))
    try:
        got = row.execute("SELECT * FROM customer_links WHERE link_id = ?",
                          (forged_id,)).fetchone()
        cols = [d[0] for d in row.execute(
            "SELECT * FROM customer_links LIMIT 1").description]
        forged = CustomerLinkRecord(**dict(zip(cols, got)))
        fp = S1Service().compute(canonical_link_bytes(forged))
        row.execute("UPDATE customer_links SET record_fingerprint = ?, "
                    "fingerprint_algorithm_id = ? WHERE link_id = ?",
                    (fp.s1, fp.s1_algorithm_id, forged_id))
        row.commit()
    finally:
        row.close()
    read = stack.customers_svc.read_link_by_id(forged_id)
    assert type(read).__name__ == "CustomerLinkReadVerificationUnavailable", \
        read
    assert any("anchor" in issue or "re-join" in issue
               for issue in stack.customers_svc.issue_reports)


def test_tampered_linked_invoice_withholds_the_link(stack):
    """The linked P6.2 invoice is tampered → the link read withholds
    (fail-closed linked re-verification), while the link row itself stays
    hash-intact."""
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-tamper-inv")
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        conn.execute("UPDATE canonical_invoices SET capture_s1 = "
                     "'forged-s1' WHERE invoice_id = ?", (invoice_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.customers_svc.read_link_by_id(outcome.record.link_id)
    assert type(read).__name__ in ("CustomerLinkReadVerificationUnavailable",
                                   "CustomerLinkReadIntegrityFailure"), read


def test_tampered_linked_customer_identity_withholds_the_link(stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-tamper-cust")
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    conn = sqlite3.connect(str(stack.customer_db))
    try:
        conn.execute("UPDATE customer_identities SET identifier_value = "
                     "'tampered' WHERE customer_identity_id = ?",
                     (outcome.record.customer_identity_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.customers_svc.read_link_by_id(outcome.record.link_id)
    assert type(read).__name__ in ("CustomerLinkReadIntegrityFailure",
                                   "CustomerLinkReadVerificationUnavailable"), \
        read


def test_tampered_invoice_value_breaks_the_live_byte_identity(stack):
    """Editing the canonical FIELD value (not the anchors) → the LIVE
    byte-identity re-proof fails → withheld."""
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-tamper-val")
    outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        conn.execute("UPDATE canonical_fields SET canonical_value = "
                     "'CUST-TAMPERED' WHERE invoice_id = ? AND canonical_seq"
                     " = ?", (invoice_id, outcome.record.canonical_seq))
        conn.commit()
    finally:
        conn.close()
    read = stack.customers_svc.read_link_by_id(outcome.record.link_id)
    # the invoice's own VOR catches the edit (its fingerprint covers fields)
    assert type(read).__name__ in ("CustomerLinkReadVerificationUnavailable",
                                   "CustomerLinkReadIntegrityFailure"), read


# ---------------------------------------------------------------------------
# Zero residue under forced failure
# ---------------------------------------------------------------------------

def test_forced_storage_failure_leaves_zero_residue(stack, monkeypatch):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-forced")
    original = stack.customer_store.commit_link

    def boom(_record):
        from customer_linking import CustomerLinkingPersistenceUnavailable
        raise CustomerLinkingPersistenceUnavailable("forced failure")

    monkeypatch.setattr(stack.customer_store, "commit_link", boom)
    outcome = stack.customers_svc.link(invoice_id, CL_FIELD, CL_KIND)
    assert type(outcome).__name__ == "CustomerLinkStorageUnavailable", outcome
    monkeypatch.setattr(stack.customer_store, "commit_link", original)
    # zero residue — the next attempt is a FIRST link, not a replay
    retry = stack.link(invoice_id, CL_FIELD, CL_KIND)
    assert isinstance(retry, CustomerLinked)
    assert len(stack.customers_svc.links()) == 1


def test_fingerprint_capability_failure_is_explicit_zero_residue(
        stack, monkeypatch):
    from capture import S1ComputationFailure
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-fpcap")

    def boom(_bytes):
        raise S1ComputationFailure("forced capability loss")

    monkeypatch.setattr(stack.customer_store._s1, "compute", boom)
    outcome = stack.customers_svc.link(invoice_id, CL_FIELD, CL_KIND)
    monkeypatch.setattr(stack.customer_store._s1, "compute",
                        S1Service().compute)
    assert type(outcome).__name__ == "CustomerLinkStorageUnavailable", outcome
    assert len(stack.customers_svc.links()) == 0


# ---------------------------------------------------------------------------
# Concurrency — INV-CL-1:1 with the UNIQUE backstop (never Python-only)
#
# Project precedent (WP-7.1/WP-7.2/WP-8.1 build records): full-stack thread
# races expose the FROZEN layers' own concurrent-read behavior — out of this
# WP's boundary. The race here uses thread-local customer stores + an inert
# assembly stub holding a PRE-READ verified outcome, so ONLY the link layer
# is raced.
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


def test_eight_thread_same_declaration_race_yields_one_link(stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-race")
    pre_read = stack.assembly.read_assembled_invoice(invoice_id)
    assert len(stack.customers_svc.links()) == 0  # the race is over the ONE row
    customer_db = stack.customer_db
    results = []
    errors = []
    barrier = threading.Barrier(8)

    def worker():
        s1 = S1Service()
        store = CustomerLinkingStore(customer_db, s1)
        service = CustomerLinkingService(store, _StubAssembly(pre_read), s1)
        try:
            barrier.wait()
            results.append(service.link(invoice_id, CL_FIELD, CL_KIND))
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
    linked = [r for r in results if isinstance(r, CustomerLinked)]
    replays = [r for r in results if isinstance(r, CustomerLinkReplay)]
    assert len(linked) == 1
    assert len(replays) == 7
    winner = linked[0].record
    assert all(r.record == winner for r in replays)
    assert len(stack.customers_svc.links()) == 1


# ---------------------------------------------------------------------------
# Deployment-order determinism
# ---------------------------------------------------------------------------

def test_deployment_order_determinism_of_the_durable_link(tmp_path):
    """The SAME scenario executed in two cold, independent environments
    yields the SAME durable link content (every non-bookkeeping scalar) —
    the link fact is a pure function of the verified content (OD-CL4)."""
    results = []
    for run in range(2):
        base = tmp_path / f"run-{run}"
        base.mkdir()
        stack = CustomerLinkingStack(
            base / "capture.db", base / "recon.db", base / "extraction.db",
            base / "bindings.db", base / "norm.db", base / "deriv.db",
            base / "val.db", base / "vsm.db", base / "gate.db",
            base / "assembly.db", base / "customer.db")
        try:
            stack.register(CL_KIND, CL_VALUE)
            customers = stack.customers_svc.customers()
            # the corpus is BYTE-IDENTICAL across the two cold runs — the
            # determinism claim is about the same content, not unique content
            _, invoice_id = stack.assemble_customers_invoice(
                parts=PAGE_CUSTOMERS_OK, label="cl-det")
            outcome = stack.link(invoice_id, CL_FIELD, CL_KIND)
            read = stack.customers_svc.read_link_by_id(outcome.record.link_id)
            assert isinstance(read, CustomerLinkReadSuccess)
            results.append({
                "customers": [(c.identifier_kind, c.identifier_value)
                              for c in customers],
                "semantic": (outcome.record.declared_field_name,
                             outcome.record.canonical_seq,
                             outcome.record.provenance,
                             outcome.record.identifier_kind,
                             outcome.record.link_outcome,
                             outcome.record.unresolved_reason),
                "invoice_id": invoice_id,
                "capture_s1": outcome.record.capture_s1,
                "customer_value": read.customer_identity.identifier_value,
            })
        finally:
            stack.close()
    assert results[0]["customers"] == results[1]["customers"]
    assert results[0]["semantic"] == results[1]["semantic"]
    assert results[0]["invoice_id"] != results[1]["invoice_id"]  # fresh Kandoo
    assert results[0]["capture_s1"] == results[1]["capture_s1"]  # same bytes
    assert results[0]["customer_value"] == results[1]["customer_value"]
