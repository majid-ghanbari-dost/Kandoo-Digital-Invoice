"""WP-6.2 provenance/trace tests — whole-chain walkability, broken-chain
fail-closure, pointer re-join with byte-identity (SPEC §9; dispatch §13 axes
15, 16)."""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ca_helpers import (  # noqa: E402
    LINE_BINDING,
    CanonicalAssemblyStack,
    unique_line_pages,
)
from canonical_assembly import (  # noqa: E402
    AssemblyCompleted,
    AssemblyInputIntegrityFailure,
    AssemblyTraceIntegrityFailure,
    AssemblyTraceSuccess,
)
from canonicalization import CanonicalizationAccepted  # noqa: E402


def assembled(stack, label="ca-prov"):
    outcome = stack.build_accepted_lines_admission(unique_line_pages(),
                                                   label=label)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted), asm
    return asm, outcome


# ---------------------------------------------------------------------------
# Axis 15: provenance completeness — every link, machine-checked
# ---------------------------------------------------------------------------

def test_trace_walks_the_full_chain_to_capture_s1(stack):
    asm, admission_outcome = assembled(stack)
    tr = stack.assembly.trace_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(tr, AssemblyTraceSuccess), tr
    text = "\n".join(tr.chain)
    # head link: the issued invoice itself
    assert tr.chain[0].startswith("issued_invoice:")
    # the P6.1 admission + decision links
    assert any("admission: P6.1 ACCEPTED decision" in link
               for link in tr.chain)
    # the consumed P6.1 whole-chain walk (→ P5.2 → … → Capture S1)
    assert any("domain_state: P6.1 whole-chain re-verified" in link
               for link in tr.chain)
    assert any("capture: OK" in link or "Capture S1" in link
               for link in tr.chain)
    # the field + line re-join links
    assert any("fields:" in link and "byte-identical" in link
               for link in tr.chain)
    assert any("lines:" in link and "byte-identical" in link
               for link in tr.chain)


def test_trace_reaches_the_original_capture_identity(stack):
    asm, admission_outcome = assembled(stack)
    tr = stack.assembly.trace_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(tr, AssemblyTraceSuccess)
    # the issued invoice carries the SAME capture anchor the Gate admitted
    assert asm.invoice.capture_s1 == \
        admission_outcome.canonical_invoice.capture_s1
    assert asm.invoice.domain_state_id == \
        admission_outcome.canonical_invoice.domain_state_id


def test_read_delivers_fields_and_lines_only_with_verified_verdict(stack):
    asm, _ = assembled(stack)
    read = stack.assembly.read_assembled_invoice(asm.invoice.invoice_id)
    assert type(read).__name__ == "AssemblyReadSuccess"
    assert len(read.fields) == asm.invoice.field_count
    assert len(read.lines) == asm.invoice.line_count
    assert len(read.header_anchors) == 3


# ---------------------------------------------------------------------------
# Axis 16: broken provenance → FAIL CLOSED (no partial assembly, no silent
# acceptance)
# ---------------------------------------------------------------------------

def test_tampered_normalization_value_breaks_assembly_fail_closed(stack):
    """The verified read is the only value path — tampering its stored
    content fails VOR and the assembly never proceeds."""
    asm, admission_outcome = assembled(stack)
    # a SECOND admission over a fresh pipeline — then tamper ITS
    # normalization row before assembling
    outcome2 = stack.build_accepted_lines_admission(unique_line_pages(),
                                                    label="ca-prov-broken")
    assert isinstance(outcome2, CanonicalizationAccepted)
    invoice_id2 = outcome2.canonical_invoice.canonical_invoice_id
    norm_id = outcome2.canonical_invoice.normalization_id
    conn = sqlite3.connect(str(stack.norm_db))
    try:
        conn.execute("UPDATE normalization_fields SET normalized_value = "
                     "'TAMPERED' WHERE normalization_id = ? AND "
                     "normalized_value != ''", (norm_id,))
        conn.commit()
    finally:
        conn.close()
    result = stack.assembly.assemble(invoice_id2, LINE_BINDING)
    assert isinstance(result, AssemblyInputIntegrityFailure), result
    # the FIRST invoice is untouched and still traces clean
    tr = stack.assembly.trace_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(tr, AssemblyTraceSuccess)


def test_tampered_upstream_record_breaks_the_consumed_p61_walk(stack):
    """The P6.1 whole-chain trace is consumed, never bypassed — tampering a
    frozen upstream record (WP-3.2 binding) breaks the walk and the assembly
    fails closed (the same failure mode the P6.1 suite pins)."""
    outcome = stack.build_accepted_lines_admission(unique_line_pages(),
                                                   label="ca-prov-capture")
    assert isinstance(outcome, CanonicalizationAccepted)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    conn = sqlite3.connect(str(stack.binding_db))
    try:
        conn.execute("UPDATE extraction_bindings SET binding_id = 'forged'")
        conn.commit()
    finally:
        conn.close()
    result = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(result, AssemblyInputIntegrityFailure), result
    assert "provenance" in result.reason or "verify" in result.reason


def test_trace_detects_tampered_issued_invoice(stack):
    asm, _ = assembled(stack)
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        conn.execute("UPDATE canonical_invoices SET origin = "
                     "'OTHER_POS_CAPTURE' WHERE invoice_id = ?",
                     (asm.invoice.invoice_id,))
        conn.commit()
    finally:
        conn.close()
    tr = stack.assembly.trace_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(tr, AssemblyTraceIntegrityFailure), tr
    assert tr.link == "issued_invoice"


def test_trace_detects_drifted_field_value(stack):
    asm, _ = assembled(stack)
    # tamper BOTH the canonical field value AND the record fingerprint is
    # impossible without recomputation — tampering the value alone is caught
    # inside the read (VOR) before the re-join
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        conn.execute("UPDATE canonical_fields SET canonical_value = 'x' "
                     "WHERE invoice_id = ? AND canonical_seq = 1",
                     (asm.invoice.invoice_id,))
        conn.commit()
    finally:
        conn.close()
    tr = stack.assembly.trace_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(tr, AssemblyTraceIntegrityFailure), tr


def test_trace_refused_for_unknown_invoice(stack):
    tr = stack.assembly.trace_assembled_invoice("no-such-invoice")
    assert type(tr).__name__ == "AssemblyTraceRefused"


# ---------------------------------------------------------------------------
# Pointer re-join integrity: DERIVED fields re-join P4.2 verified reads
# ---------------------------------------------------------------------------

def test_derived_field_pointer_rejoins_the_verified_derivation_read(stack):
    asm, _ = assembled(stack)
    derived = [f for f in asm.fields
               if f.provenance == "DERIVED"]
    assert len(derived) == 1
    entry = derived[0]
    d_read = stack.deriv.read_derivation(entry.source_derivation_id)
    assert type(d_read).__name__ == "DerivationReadSuccess"
    assert d_read.record.output_value == entry.canonical_value
    assert d_read.record.output_field_name == entry.field_name
