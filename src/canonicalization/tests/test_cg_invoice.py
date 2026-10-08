"""WP-6.1 Canonical Invoice admission-record tests — source independence,
origin preservation, immutability, deterministic fingerprints, INV-CI-1:1
(SPEC §6; dispatch axes 16–18, 13).

Covers: origin preserved verbatim from the declared request (frozen enum);
source independence (no raw pipeline values stored — pointer + fingerprint
pattern); immutability (no UPDATE/DELETE path exists in the store; direct-SQL
tamper is detected); deterministic fingerprint over record + pointers; the
admission invariants (one invoice per ACCEPTED decision, capture-level and
document-level UNIQUE backstops).
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cg_helpers import BINDING, unique_identity_pages  # noqa: E402
from canonicalization import (  # noqa: E402
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    ORIGINS,
    CanonicalizationAccepted,
    CanonicalizationRequestRefused,
)


def _admit(stack, origin=ORIGIN_HOLOO_CAPTURE, parts=None):
    _, projection = stack.build_valid_identity_state(parts=parts)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, origin, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    return outcome


def test_origin_is_preserved_verbatim(stack):
    outcome = _admit(stack, ORIGIN_HOLOO_CAPTURE)
    assert outcome.canonical_invoice.origin == "HOLOO_CAPTURE"
    assert outcome.decision.declared_origin == "HOLOO_CAPTURE"
    read = stack.gate.read_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert type(read).__name__ == "CanonicalInvoiceReadSuccess", read
    assert read.record.origin == "HOLOO_CAPTURE"


def test_other_pos_origin_is_preserved(stack):
    outcome = _admit(stack, ORIGIN_OTHER_POS_CAPTURE)
    assert outcome.canonical_invoice.origin == "OTHER_POS_CAPTURE"


def test_origin_vocabulary_is_exactly_the_frozen_set():
    assert ORIGINS == ("KANDOO_SALE", "HOLOO_CAPTURE", "OTHER_POS_CAPTURE")


def test_kandoo_sale_origin_is_refused_on_capture_pipeline_input(stack):
    """OD-G6/OD-G7: the native flow (AS-02) has no P5.2 state — a KANDOO_SALE
    declaration on a capture-pipeline request is a fail-closed refusal."""
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, "KANDOO_SALE", BINDING)
    assert type(outcome).__name__ == "CanonicalizationRequestRefused", outcome
    assert "native-flow" in outcome.detail


def test_unknown_origin_is_refused(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, "MY_NEW_ORIGIN", BINDING)
    assert type(outcome).__name__ == "CanonicalizationRequestRefused", outcome


def test_canonical_invoice_is_source_independent(stack):
    """D-04 / SPEC §6: the admission record carries origin + upstream
    POINTERS only — no source-schema columns, no raw pipeline values."""
    outcome = _admit(stack)
    record = outcome.canonical_invoice
    fields = set(record.__dataclass_fields__.keys())
    forbidden = {"invoice_number", "invoice_date", "invoice_total",
                 "customer_name", "product_code", "line_items", "total",
                 "source_schema", "raw_content"}
    assert fields & forbidden == set()
    expected_anchors = {"canonical_invoice_id", "decision_id",
                        "domain_state_id", "normalization_id",
                        "extraction_id", "document_id", "capture_id",
                        "capture_s1", "origin", "identity_class",
                        "identity_source", "identity_fingerprint",
                        "created_at", "record_fingerprint",
                        "fingerprint_algorithm_id"}
    assert expected_anchors <= fields
    # the durable row carries no plaintext S2 tuple either
    import sqlite3
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        row = conn.execute(
            "SELECT * FROM canonical_invoices WHERE canonical_invoice_id = ?",
            (record.canonical_invoice_id,)).fetchone()
        columns = [d[0] for d in conn.execute(
            "SELECT * FROM canonical_invoices LIMIT 1").description]
    finally:
        conn.close()
    for value in row:
        assert not isinstance(value, bytes)     # no raw content blobs
    assert "invoice_number" not in columns
    assert "raw" not in " ".join(columns)


def test_canonical_invoice_fingerprint_is_deterministic(stack):
    """The record fingerprint is a pure function of the record content + its
    pointer rows (bookkeeping ids aside) — recomputation matches exactly."""
    from canonicalization import canonical_invoice_bytes
    from capture import S1Service
    outcome = _admit(stack)
    read = stack.gate.read_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    recomputed = S1Service().compute(
        canonical_invoice_bytes(read.record, read.identity_pointers))
    assert recomputed.s1 == read.record.record_fingerprint
    assert recomputed.s1 == outcome.canonical_invoice.record_fingerprint


def test_admission_record_is_immutable_no_update_delete_path(stack):
    """OD-C7: the store exposes NO update/delete path at all — the durable
    history cannot be rewritten through the API."""
    store_api = [m for m in dir(stack.gate_store) if not m.startswith("_")]
    assert not any("update" in m or "delete" in m or "mutate" in m
                   for m in store_api)
    # and the only write paths are the atomic commit + append-only event
    assert "commit_decision" in store_api
    assert "append_event" in store_api
    # no public invoice-creation API exists outside the gate transaction
    assert not any("create" in m for m in store_api)


def test_direct_sql_tamper_is_detected_on_read(stack):
    """A forged invoice row is withheld with a definitive integrity failure —
    Verify-on-Read (tamper detection, dispatch axis 12)."""
    outcome = _admit(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    import sqlite3
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        conn.execute("UPDATE canonical_invoices SET origin = 'KANDOO_SALE' "
                     "WHERE canonical_invoice_id = ?", (invoice_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.gate.read_canonical_invoice(invoice_id)
    assert type(read).__name__ == "CanonicalInvoiceReadIntegrityFailure", read
    assert read.reason == "verify FAILED"


def test_pointer_row_tamper_is_detected(stack):
    outcome = _admit(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    import sqlite3
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        conn.execute("UPDATE canonical_identity_pointers SET field_seq = 99 "
                     "WHERE canonical_invoice_id = ?", (invoice_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.gate.read_canonical_invoice(invoice_id)
    assert type(read).__name__ == "CanonicalInvoiceReadIntegrityFailure", read


def test_decision_tamper_breaks_the_invoice_read(stack):
    """The invoice read verifies its linked decision — a forged decision row
    poisons the admission read (fail-closed, VOR)."""
    outcome = _admit(stack)
    import sqlite3
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        conn.execute("UPDATE gate_decisions SET decision_detail = 'forged' "
                     "WHERE decision_id = ?",
                     (outcome.decision.decision_id,))
        conn.commit()
    finally:
        conn.close()
    read = stack.gate.read_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert type(read).__name__ == "CanonicalInvoiceReadIntegrityFailure", read
    assert "linked decision" in read.reason


def test_no_canonicalization_without_the_gate(stack):
    """Dispatch §15 (final): no canonicalization succeeds without the Gate —
    the ONLY write path that creates a canonical invoice is the gate's atomic
    commit_decision, reachable only through the service; a bare store cannot
    mint an invoice, and no invoice exists without an ACCEPTED decision."""
    import sqlite3
    # 1. the store API surface has no separate invoice-creation entry point
    store_api = [m for m in dir(stack.gate_store) if not m.startswith("_")]
    assert "commit_decision" in store_api
    assert not any(m.startswith("insert") or "create" in m
                   for m in store_api)
    # 2. every durable invoice row is 1:1 with an ACCEPTED decision row
    outcome = _admit(stack)
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        invoices = conn.execute(
            "SELECT COUNT(*) FROM canonical_invoices").fetchone()[0]
        accepted = conn.execute(
            "SELECT COUNT(*) FROM gate_decisions WHERE decision = 'ACCEPTED'"
        ).fetchone()[0]
        linked = conn.execute(
            """SELECT COUNT(*) FROM canonical_invoices c
               JOIN gate_decisions d ON c.decision_id = d.decision_id
               WHERE d.decision = 'ACCEPTED'
               AND d.canonical_invoice_id = c.canonical_invoice_id"""
        ).fetchone()[0]
    finally:
        conn.close()
    assert invoices == accepted == linked == 1


def test_invoice_requires_three_identity_pointer_rows(stack):
    outcome = _admit(stack)
    import sqlite3
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM canonical_identity_pointers "
            "WHERE canonical_invoice_id = ?",
            (outcome.canonical_invoice.canonical_invoice_id,)).fetchone()[0]
    finally:
        conn.close()
    assert n == 3


def test_read_refuses_unknown_invoice_and_decision(stack):
    assert type(stack.gate.read_canonical_invoice("nope")).__name__ == \
        "CanonicalInvoiceReadRefused"
    assert type(stack.gate.read_gate_decision("nope")).__name__ == \
        "GateDecisionReadRefused"


def test_admission_anchors_match_the_upstream_state(stack):
    """The admission record's upstream anchor set equals the verified P5.2
    state's anchors — the chain is carried, not rebuilt."""
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    inv = outcome.canonical_invoice
    state = projection.record
    assert inv.domain_state_id == state.domain_state_id
    assert inv.normalization_id == state.normalization_id
    assert inv.extraction_id == state.extraction_id
    assert inv.document_id == state.document_id
    assert inv.capture_id == state.capture_id
    assert inv.capture_s1 == state.capture_s1
    assert inv.capture_s1_algorithm_id == state.capture_s1_algorithm_id
