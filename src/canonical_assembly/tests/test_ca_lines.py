"""WP-6.2 canonical line tests — declared structure, deterministic ordering,
absence/rejection semantics (SPEC §6; dispatch §13 axes 4, 5, 18, 21, 22,
23)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ca_helpers import (  # noqa: E402
    EMPTY_LINE_BINDING,
    LINE_BINDING,
    PAGE_LINE_EMPTY,
    PAGE_LINE_PARTIAL,
    PAGE_LINES_OK,
    CanonicalAssemblyStack,
)
from canonical_assembly import (  # noqa: E402
    ABSENT_REASON_UPSTREAM,
    AssemblyAlreadyAssembled,
    AssemblyCompleted,
    LINE_ROLES,
    REJECT_EMPTY_LINE,
)
from canonicalization import CanonicalizationAccepted  # noqa: E402

TWO_LINE_BINDING = {
    0: {"LINE_QUANTITY": "line.0.quantity",
        "LINE_UNIT_PRICE": "line.0.unit_price",
        "LINE_TOTAL": "line.0.total"},
    1: {"LINE_QUANTITY": "line.1.quantity",
        "LINE_UNIT_PRICE": "line.1.unit_price",
        "LINE_TOTAL": "line.1.total"},
}


def admitted(stack, parts, label, binding=None):
    outcome = stack.build_accepted_lines_admission(parts, label=label,
                                                   binding=binding)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    return outcome


# ---------------------------------------------------------------------------
# Axis 4 / 5 / 21: line assembly — exact, ordered, multiple
# ---------------------------------------------------------------------------

def test_two_declared_lines_assemble_with_exact_values(stack):
    outcome = admitted(stack, PAGE_LINES_OK, "ca-lines-ok")
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, TWO_LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    assert asm.invoice.line_count == 2
    assert asm.rejected_lines == ()
    by_line = {}
    for lf in asm.line_fields:
        by_line.setdefault(lf.line_seq, {})[lf.role] = lf
    assert by_line[0]["LINE_QUANTITY"].canonical_value == "2"
    assert by_line[0]["LINE_UNIT_PRICE"].canonical_value == "500.00"
    assert by_line[0]["LINE_TOTAL"].canonical_value == "1000.00"
    assert by_line[1]["LINE_QUANTITY"].canonical_value == "3"
    assert by_line[1]["LINE_UNIT_PRICE"].canonical_value == "60.00"
    assert by_line[1]["LINE_TOTAL"].canonical_value == "180.00"
    # every present line field carries its verified pointer
    for lf in asm.line_fields:
        assert lf.present == 1
        assert lf.source_field_name.startswith("line.")
        assert lf.normalization_id == outcome.canonical_invoice.normalization_id
        assert lf.field_seq is not None


def test_line_ordering_is_deterministic_ascending_declared_key(stack):
    outcome = admitted(stack, PAGE_LINES_OK, "ca-lines-order")
    # declare keys OUT of order — the durable order is still ascending
    scrambled = {1: TWO_LINE_BINDING[1], 0: TWO_LINE_BINDING[0]}
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, scrambled)
    assert isinstance(asm, AssemblyCompleted)
    assert [l.line_seq for l in asm.lines] == [0, 1]
    seqs = [lf.line_seq for lf in asm.line_fields]
    assert seqs == sorted(seqs)
    # replay yields the identical durable line set
    replay = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, TWO_LINE_BINDING)
    assert isinstance(replay, AssemblyAlreadyAssembled)
    assert replay.line_fields == asm.line_fields


def test_line_ordering_never_depends_on_dict_iteration(stack):
    """A scrambled-dict declaration of the SAME structure carries the same
    declaration fingerprint (sorted explicitly, never dict-order) — the
    replay therefore returns the identical durable line set."""
    outcome = admitted(stack, PAGE_LINES_OK, "ca-lines-dict")
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    a = stack.assembly.assemble(invoice_id, TWO_LINE_BINDING)
    scrambled = {1: TWO_LINE_BINDING[1], 0: TWO_LINE_BINDING[0]}
    b = stack.assembly.assemble(invoice_id, scrambled)
    assert isinstance(a, AssemblyCompleted)
    assert isinstance(b, AssemblyAlreadyAssembled)
    assert [(l.line_seq,) for l in b.lines] == [(0,), (1,)]
    assert b.line_fields == a.line_fields


# ---------------------------------------------------------------------------
# Axis 18: missing optional data — explicit absence, never invention
# ---------------------------------------------------------------------------

def test_partially_absent_line_roles_are_recorded_absent(stack):
    outcome = admitted(stack, PAGE_LINE_PARTIAL, "ca-lines-partial")
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, TWO_LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    assert asm.invoice.line_count == 2
    line0 = {lf.role: lf for lf in asm.line_fields if lf.line_seq == 0}
    assert line0["LINE_QUANTITY"].present == 1
    assert line0["LINE_QUANTITY"].canonical_value == "7"
    assert line0["LINE_UNIT_PRICE"].present == 0
    assert line0["LINE_UNIT_PRICE"].canonical_value is None
    assert line0["LINE_TOTAL"].present == 0
    # line 1 is fully present
    line1 = {lf.role: lf for lf in asm.line_fields if lf.line_seq == 1}
    assert all(lf.present == 1 for lf in line1.values())


# ---------------------------------------------------------------------------
# Axis 22: empty/invalid line rejection
# ---------------------------------------------------------------------------

def test_all_absent_line_is_rejected_explicitly_never_stored(stack):
    outcome = admitted(stack, PAGE_LINE_EMPTY, "ca-lines-empty")
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, TWO_LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    # line 0 declared but nothing usable → explicit rejection
    assert [(r.line_seq, r.reason) for r in asm.rejected_lines] == \
        [(0, REJECT_EMPTY_LINE)]
    # only line 1 lives on the durable invoice
    assert asm.invoice.line_count == 1
    assert [l.line_seq for l in asm.lines] == [1]
    assert all(lf.line_seq == 1 for lf in asm.line_fields)


def test_rejected_line_does_not_break_replay(stack):
    outcome = admitted(stack, PAGE_LINE_EMPTY, "ca-lines-empty-replay")
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    first = stack.assembly.assemble(invoice_id, TWO_LINE_BINDING)
    second = stack.assembly.assemble(invoice_id, TWO_LINE_BINDING)
    assert isinstance(first, AssemblyCompleted)
    assert isinstance(second, AssemblyAlreadyAssembled)


# ---------------------------------------------------------------------------
# Axis 23: duplicate line handling — malformed declarations refused
# ---------------------------------------------------------------------------

def test_duplicate_target_across_lines_is_refused(stack):
    outcome = admitted(stack, PAGE_LINES_OK, "ca-lines-dup-target")
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    refused = stack.assembly.assemble(invoice_id, {
        0: {"LINE_QUANTITY": "line.0.quantity",
            "LINE_UNIT_PRICE": "line.0.unit_price",
            "LINE_TOTAL": "line.0.total"},
        1: {"LINE_QUANTITY": "line.0.total",       # already bound on line 0
            "LINE_UNIT_PRICE": "line.1.unit_price",
            "LINE_TOTAL": "line.1.total"}})
    assert type(refused).__name__ == "AssemblyRequestRefused"
    assert "bound more than once" in refused.detail


def test_line_binding_to_identity_field_is_verbatim_not_guessed(stack):
    """A line role MAY bind the identity field — the value is relayed
    verbatim with its pointer (no ambiguity: exactly one usable row)."""
    outcome = admitted(stack, PAGE_LINES_OK, "ca-lines-identity-bind")
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    asm = stack.assembly.assemble(invoice_id, {
        0: {"LINE_QUANTITY": "line.0.quantity",
            "LINE_UNIT_PRICE": "line.0.unit_price",
            "LINE_TOTAL": "total.net"}})           # the INVOICE_TOTAL field
    assert isinstance(asm, AssemblyCompleted)
    total_role = {lf.role: lf for lf in asm.line_fields
                  if lf.line_seq == 0}["LINE_TOTAL"]
    assert total_role.canonical_value == "1180.00"
    anchor = {a.role: a for a in asm.header_anchors}["INVOICE_TOTAL"]
    assert anchor.canonical_value == "1180.00"     # verbatim, consistent


# ---------------------------------------------------------------------------
# Zero-line invoices: an absent declaration is explicit, deterministic
# ---------------------------------------------------------------------------

def test_absent_declaration_yields_zero_lines_explicitly(stack):
    from ca_helpers import unique_line_pages
    outcome = admitted(stack, unique_line_pages(), "ca-lines-none")
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, None)
    assert isinstance(asm, AssemblyCompleted)
    assert asm.invoice.line_count == 0
    assert asm.lines == () and asm.line_fields == ()
    assert asm.invoice.field_count > 0             # fields still assemble
    read = stack.assembly.read_assembled_invoice(asm.invoice.invoice_id)
    assert type(read).__name__ == "AssemblyReadSuccess"
