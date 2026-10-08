"""WP-6.2 assembly service tests — fail-closed ladder, replay, outcomes,
spy-proven upstream non-execution (SPEC §2/§3/§4/§7; dispatch §13 axes 1, 2,
9, 24, 26 + e2e axis 27)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ca_helpers import (  # noqa: E402
    LINE_BINDING,
    PAGE_LINE_AMBIGUOUS,
    PAGE_LINES_OK,
    CanonicalAssemblyStack,
    unique_line_pages,
)
from canonical_assembly import (  # noqa: E402
    AssemblyAlreadyAssembled,
    AssemblyCompleted,
    AssemblyInputIntegrityFailure,
    AssemblyReadRefused,
    AssemblyReadSuccess,
    AssemblyRequestRefused,
    ORIGIN_HOLOO_CAPTURE,
)
from canonicalization import (  # noqa: E402
    CanonicalizationAccepted,
    CanonicalizationRejected,
    CanonicalizationRoutedToReview,
    ORIGIN_OTHER_POS_CAPTURE,
)


def admitted(stack, parts=None, label="ca-svc"):
    outcome = stack.build_accepted_lines_admission(
        parts if parts is not None else unique_line_pages(), label=label)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    return outcome


# ---------------------------------------------------------------------------
# Axis 1 / 27: ACCEPTED admission → Canonical Invoice (end-to-end)
# ---------------------------------------------------------------------------

def test_accepted_admission_assembles_the_real_invoice(stack):
    outcome = admitted(stack)
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    # the real invoice: anchors + inventory + lines, all present
    assert len(asm.header_anchors) == 3
    assert asm.invoice.field_count == len(asm.fields) > 0
    assert asm.invoice.line_count == len(asm.lines) == 2
    assert len(asm.line_fields) == 6
    read = stack.assembly.read_assembled_invoice(
        asm.invoice.invoice_id)
    assert isinstance(read, AssemblyReadSuccess)


def test_end_to_end_capture_to_issued_canonical_invoice(stack):
    """Capture → Reconstruction → Extraction → Binding → Normalization →
    DERIVED → Validation → P5.2 → P6.1 → P6.2 → Canonical Invoice."""
    outcome = admitted(stack)
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    tr = stack.assembly.trace_assembled_invoice(asm.invoice.invoice_id)
    assert type(tr).__name__ == "AssemblyTraceSuccess"
    # the chain reaches Capture S1 through the consumed P6.1/P5.2 walks
    assert any("capture: OK" in link or "Capture S1" in link
               for link in tr.chain)


# ---------------------------------------------------------------------------
# Axis 2: non-ACCEPTED → no invoice (P6.1 boundary, SPEC §1)
# ---------------------------------------------------------------------------

def test_review_decision_never_produces_an_invoice(stack):
    # ambiguous IDENTITY (two invoice.number rows) → the GATE routes REVIEW
    # (G3) — no admission record exists, so nothing can ever be assembled
    from cg_helpers import unique_identity_pages
    pages = unique_identity_pages() + [b"line.0.quantity=2\n"]
    parts = [pages[0] + b"invoice.number=INV-DUP-SECOND\n"]
    outcome = stack.build_accepted_lines_admission(
        parts, label="ca-review",
        binding={"INVOICE_NUMBER": "invoice.number",
                 "INVOICE_DATE": "invoice.date",
                 "INVOICE_TOTAL": "total.net"})
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    # no admission record exists — every assemble attempt fails closed
    for candidate in (outcome.decision.decision_id,
                      outcome.decision.domain_state_id,
                      "fabricated-admission-id"):
        refused = stack.assembly.assemble(candidate, LINE_BINDING)
        assert isinstance(refused, AssemblyRequestRefused), refused
    assert stack.assembly.issued_invoices() == []


def test_rejected_decision_never_produces_an_invoice(stack):
    from cg_helpers import decisive_invalid_state
    nid, projection = decisive_invalid_state(
        stack, unique_line_pages(), label="ca-rejected")
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRejected), outcome
    refused = stack.assembly.assemble(
        outcome.decision.decision_id, LINE_BINDING)
    assert isinstance(refused, AssemblyRequestRefused)
    assert "ACCEPTED" in refused.detail
    assert stack.assembly.issued_invoices() == []


def test_unknown_admission_id_is_refused_with_zero_residue(stack):
    outcome = admitted(stack)
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    refused = stack.assembly.assemble("not-a-real-admission-id", LINE_BINDING)
    assert isinstance(refused, AssemblyRequestRefused)
    assert len(stack.assembly.issued_invoices()) == 1   # the real one intact
    assert all(i.invoice_id != "not-a-real-admission-id"
               for i in stack.assembly.issued_invoices())


# ---------------------------------------------------------------------------
# Axis 9 / 24: duplicate admission + repeated issuance (idempotent)
# ---------------------------------------------------------------------------

def test_duplicate_admission_replays_the_same_invoice(stack):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    first = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(first, AssemblyCompleted)
    second = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(second, AssemblyAlreadyAssembled)
    assert second.invoice.invoice_id == first.invoice.invoice_id
    assert second.invoice.record_fingerprint == \
        first.invoice.record_fingerprint
    assert len(stack.assembly.issued_invoices()) == 1


def test_repeated_issuance_across_independent_service_instances(stack, make_stack):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    # a second, independent assembly service over the SAME durable store
    second_service = make_stack().assembly
    try:
        first = stack.assembly.assemble(invoice_id, LINE_BINDING)
        assert isinstance(first, AssemblyCompleted)
        replay = second_service.assemble(invoice_id, LINE_BINDING)
        assert isinstance(replay, AssemblyAlreadyAssembled)
        assert len(second_service.issued_invoices()) == 1
    finally:
        second_service._store.close()


def test_replay_with_different_declaration_is_refused_fail_closed(stack):
    """OD-A8: declaration drift on replay → explicit refusal, no second
    invoice, no silent reshape."""
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    first = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(first, AssemblyCompleted)
    drifted = stack.assembly.assemble(invoice_id, None)
    assert isinstance(drifted, AssemblyRequestRefused)
    assert "assembly-declaration-conflict" in drifted.detail
    assert len(stack.assembly.issued_invoices()) == 1
    # the same declaration still replays cleanly after the refusal
    still = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(still, AssemblyAlreadyAssembled)


# ---------------------------------------------------------------------------
# Axis 26: P6.1 is consumed, never bypassed (spy + upstream non-execution)
# ---------------------------------------------------------------------------

def test_p61_is_consumed_not_bypassed_by_the_assembly(stack, monkeypatch):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    calls = {"read": 0, "trace": 0}
    real_read = stack.gate.read_canonical_invoice
    real_trace = stack.gate.trace_canonical_invoice

    def spy_read(invoice_id_):
        calls["read"] += 1
        return real_read(invoice_id_)

    def spy_trace(invoice_id_):
        calls["trace"] += 1
        return real_trace(invoice_id_)

    monkeypatch.setattr(stack.gate, "read_canonical_invoice", spy_read)
    monkeypatch.setattr(stack.gate, "trace_canonical_invoice", spy_trace)
    asm = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    assert calls["read"] >= 1 and calls["trace"] >= 1   # consumed


def test_no_upstream_layer_is_ever_executed_by_assembly(stack, monkeypatch):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id

    def _forbidden(*args, **kwargs):
        raise AssertionError("assembly executed an upstream layer")

    monkeypatch.setattr(stack.vsm, "project_domain_state", _forbidden)
    monkeypatch.setattr(stack.val, "validate", _forbidden)
    monkeypatch.setattr(stack.norm, "normalize", _forbidden)
    monkeypatch.setattr(stack.deriv, "derive", _forbidden)
    monkeypatch.setattr(stack.extraction, "extract", _forbidden)
    monkeypatch.setattr(stack.recon, "reconstruct", _forbidden)
    asm = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)


# ---------------------------------------------------------------------------
# Axis 19: no invented data — assembled values ⊆ verified upstream values
# ---------------------------------------------------------------------------

def test_every_assembled_value_is_byte_identical_to_verified_upstream(stack):
    outcome = admitted(stack)
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    norm_read = stack.norm.read_normalization(
        outcome.canonical_invoice.normalization_id)
    assert type(norm_read).__name__ == "NormalizationReadSuccess"
    upstream = {(f.source_field_name, f.field_seq): f.normalized_value
                for f in norm_read.fields}
    for f in asm.fields:
        if f.provenance == "EXTRACTED":
            assert upstream[(f.field_name, f.source_field_seq)] == \
                f.canonical_value
    for lf in asm.line_fields:
        if lf.present:
            assert upstream[(lf.source_field_name, lf.field_seq)] == \
                lf.canonical_value
    # absent roles carry nothing
    for lf in asm.line_fields:
        if not lf.present:
            assert lf.canonical_value is None


def test_declared_field_ambiguity_refuses_the_whole_request(stack):
    """OD-A5: >=2 usable rows for a declared field → refuse, never pick."""
    outcome = stack.build_accepted_lines_admission(
        PAGE_LINE_AMBIGUOUS, label="ca-ambig")
    assert isinstance(outcome, CanonicalizationAccepted)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    refused = stack.assembly.assemble(invoice_id, {
        0: {"LINE_QUANTITY": "line.0.quantity",
            "LINE_UNIT_PRICE": "line.0.unit_price",
            "LINE_TOTAL": "line.0.total"}})
    assert isinstance(refused, AssemblyRequestRefused)
    assert "declared-field-ambiguous" in refused.detail
    assert stack.assembly.issued_invoices() == []     # zero residue


def test_assembly_refusal_on_malformed_declaration_leaves_no_residue(stack):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    for malformed in ({0: {"LINE_QUANTITY": "q"}},
                      {"zero": {"LINE_QUANTITY": "q", "LINE_UNIT_PRICE": "u",
                                "LINE_TOTAL": "t"}},
                      {0: {"LINE_QUANTITY": "q", "LINE_UNIT_PRICE": "q",
                           "LINE_TOTAL": "t"}}):
        refused = stack.assembly.assemble(invoice_id, malformed)
        assert isinstance(refused, AssemblyRequestRefused)
    # the admission is untouched — a corrected declaration still assembles
    asm = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)


# ---------------------------------------------------------------------------
# Origin preservation through assembly (axis 17)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("origin", [ORIGIN_HOLOO_CAPTURE,
                                    ORIGIN_OTHER_POS_CAPTURE])
def test_origin_is_preserved_from_declaration_through_issuance(stack, origin):
    outcome = stack.build_accepted_lines_admission(
        unique_line_pages(), label=f"ca-origin-{origin}", origin=origin)
    assert isinstance(outcome, CanonicalizationAccepted)
    assert outcome.canonical_invoice.origin == origin
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    assert asm.invoice.origin == origin


# ---------------------------------------------------------------------------
# Content determinism (SPEC §7 I5): fresh stacks, same verified inputs →
# byte-identical issued content
# ---------------------------------------------------------------------------

def test_issued_content_is_a_pure_function_of_verified_inputs(tmp_path):
    from ca_helpers import CanonicalAssemblyStack
    fingerprints = []
    invoices = []
    for i in range(2):
        base = tmp_path / f"det-{i}"
        base.mkdir(parents=True, exist_ok=True)
        s = CanonicalAssemblyStack(
            base / "capture.db", base / "recon.db", base / "extraction.db",
            base / "binding.db", base / "norm.db", base / "deriv.db",
            base / "val.db", base / "vsm.db", base / "gate.db",
            base / "assembly.db")
        try:
            outcome = s.build_accepted_lines_admission(
                PAGE_LINES_OK, label=f"ca-det-{i}")
            assert isinstance(outcome, CanonicalizationAccepted)
            asm = s.assembly.assemble(
                outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
            assert isinstance(asm, AssemblyCompleted)
            # compare the CONTENT set: values, order, counts, pointers,
            # identity — everything except bookkeeping (created_at / ids)
            content = ([(f.canonical_seq, f.provenance, f.field_name,
                         f.canonical_value, f.source_field_seq)
                        for f in asm.fields],
                       [(lf.line_seq, lf.role, lf.present, lf.canonical_value)
                        for lf in asm.line_fields],
                       [(a.role, a.canonical_value, a.field_seq)
                        for a in asm.header_anchors],
                       asm.invoice.field_count, asm.invoice.line_count,
                       asm.invoice.identity_fingerprint, asm.invoice.origin)
            fingerprints.append(content)
            invoices.append(asm.invoice.invoice_id)
        finally:
            s.close()
    assert fingerprints[0] == fingerprints[1]
    assert invoices[0] != invoices[1]   # distinct admissions, distinct ids


# ---------------------------------------------------------------------------
# A6 identity-anchor mismatch → fail closed (pure-engine + boundary behavior)
# ---------------------------------------------------------------------------

def test_identity_anchor_mismatch_is_detected_fail_closed(stack):
    """Tampering the Gate's identity pointer rows breaks the P6.1 verified
    read FIRST (A1) — the assembly never proceeds on unverified input; the
    pure-engine level pins the A6 mechanics itself."""
    import sqlite3
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    conn = sqlite3.connect(str(stack.gate_db))
    try:
        conn.execute("UPDATE canonical_identity_pointers SET field_seq = 0 "
                     "WHERE canonical_invoice_id = ? AND role = "
                     "'INVOICE_TOTAL'", (invoice_id,))
        conn.commit()
    finally:
        conn.close()
    outcome2 = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(outcome2, AssemblyInputIntegrityFailure), outcome2
