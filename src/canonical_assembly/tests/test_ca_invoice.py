"""WP-6.2 issued Canonical Invoice tests — invoice_id issuance semantics,
immutability, tamper matrix, invariants (SPEC §5 C5/§7/§8; dispatch §13 axes
3, 6, 7, 12, 13, 14, 17, 20)."""
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
    AssemblyAlreadyAssembled,
    AssemblyCompleted,
    AssemblyReadIntegrityFailure,
    AssemblyReadSuccess,
    CUSTOMER_REF_REASON,
    PROVENANCE_DERIVED,
    PROVENANCE_EXTRACTED,
    ORIGINS,
)
from canonicalization import CanonicalizationAccepted  # noqa: E402


def admitted(stack, **kwargs):
    outcome = stack.build_accepted_lines_admission(
        unique_line_pages(), **kwargs)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    return outcome


def assembled(stack, **kwargs):
    outcome = admitted(stack, **kwargs)
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted), asm
    return asm


# ---------------------------------------------------------------------------
# Axis 6 / 7: invoice_id issuance — deterministic, unique, collision-safe
# ---------------------------------------------------------------------------

def test_invoice_id_is_the_kandoo_issued_admission_identity_verbatim(stack):
    outcome = admitted(stack)
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    # OD-A1: consumed VERBATIM — the same value, not a different formula
    assert asm.invoice.invoice_id == \
        outcome.canonical_invoice.canonical_invoice_id
    assert asm.invoice.identity_fingerprint == \
        outcome.canonical_invoice.identity_fingerprint


def test_invoice_id_is_unique_across_distinct_admissions(stack):
    ids = set()
    for _ in range(3):
        asm = assembled(stack)
        ids.add(asm.invoice.invoice_id)
    assert len(ids) == 3


def test_invoice_id_replay_returns_the_same_identity(stack):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    first = stack.assembly.assemble(invoice_id, LINE_BINDING)
    second = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(first, AssemblyCompleted)
    assert isinstance(second, AssemblyAlreadyAssembled)
    assert first.invoice.invoice_id == second.invoice.invoice_id == invoice_id


def test_issued_invoice_is_source_independent_no_source_schema_columns(stack):
    """D-04: the issued record carries the frozen origin enum + pointers —
    never a source-schema column."""
    asm = assembled(stack)
    record = asm.invoice
    assert record.origin in ORIGINS
    scalars = set(record.__dict__.keys()) if hasattr(record, "__dict__") \
        else set(record.__dataclass_fields__.keys())
    for forbidden in ("source_ref", "holoo_id", "pos_ref", "raw_row",
                      "source_table"):
        assert forbidden not in scalars


# ---------------------------------------------------------------------------
# Axis 3 / 20: exact assembly + invariant enforcement
# ---------------------------------------------------------------------------

def test_exact_field_assembly_byte_identity_and_counts(stack):
    asm = assembled(stack)
    # the DERIVED total.gross rides the inventory with DERIVED provenance
    derived = [f for f in asm.fields if f.provenance == PROVENANCE_DERIVED]
    extracted = [f for f in asm.fields
                 if f.provenance == PROVENANCE_EXTRACTED]
    assert len(derived) == 1 and derived[0].field_name == "total.gross"
    assert len(extracted) == asm.invoice.field_count - 1
    # integrity counters match the durable content exactly
    assert asm.invoice.field_count == len(asm.fields)
    assert asm.invoice.line_count == len(asm.lines)
    # canonical_seq is gap-free and ordered
    assert [f.canonical_seq for f in asm.fields] == \
        list(range(len(asm.fields)))


def test_header_anchors_carry_the_frozen_d02_roles_with_values(stack):
    asm = assembled(stack)
    roles = [a.role for a in asm.header_anchors]
    assert roles == ["INVOICE_NUMBER", "INVOICE_DATE", "INVOICE_TOTAL"]
    values = {a.role: a.canonical_value for a in asm.header_anchors}
    assert all(v for v in values.values())      # nothing empty, nothing invented


def test_customer_reference_is_explicitly_absent_per_d06(stack):
    asm = assembled(stack)
    assert asm.invoice.customer_reference is None
    assert asm.invoice.customer_reference_reason == CUSTOMER_REF_REASON


def test_totals_consistency_is_byte_identity_not_recomputation(stack):
    """The header INVOICE_TOTAL anchor is byte-identical to the value the
    Gate fingerprinted; assembly performs no arithmetic (the fingerprint
    equality IS the consistency check — OD-A6/A7)."""
    outcome = admitted(stack)
    asm = stack.assembly.assemble(
        outcome.canonical_invoice.canonical_invoice_id, LINE_BINDING)
    anchor = {a.role: a for a in asm.header_anchors}["INVOICE_TOTAL"]
    assert anchor.canonical_value == "1180.00"
    # the identity anchor of the issued invoice matches the admission's —
    # the Gate-resolved identity and the assembled header agree
    assert asm.invoice.identity_fingerprint == \
        outcome.canonical_invoice.identity_fingerprint


# ---------------------------------------------------------------------------
# Axis 13 / 14: immutable invoice + immutable lines (behavior)
# ---------------------------------------------------------------------------

def test_no_mutation_path_exists_after_issuance(stack):
    asm = assembled(stack)
    store = stack.assembly_store
    for forbidden in ("update", "delete", "mutate", "amend", "rewrite"):
        for name in dir(store):
            assert forbidden not in name.lower(), \
                f"store exposes a mutation path: {name}"
    # the issued record is a frozen dataclass
    with pytest.raises(Exception):
        asm.invoice.origin = "KANDOO_SALE"


def test_reissued_content_cannot_drift_after_issuance(stack):
    outcome = admitted(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    first = stack.assembly.assemble(invoice_id, LINE_BINDING)
    read_before = stack.assembly.read_assembled_invoice(invoice_id)
    second = stack.assembly.assemble(invoice_id, LINE_BINDING)
    read_after = stack.assembly.read_assembled_invoice(invoice_id)
    assert isinstance(first, AssemblyCompleted)
    assert isinstance(second, AssemblyAlreadyAssembled)
    assert isinstance(read_before, AssemblyReadSuccess)
    assert isinstance(read_after, AssemblyReadSuccess)
    assert read_before.fields == read_after.fields
    assert read_before.line_fields == read_after.line_fields


# ---------------------------------------------------------------------------
# Axis 12: tamper detection matrix (direct SQL on the assembly store)
# ---------------------------------------------------------------------------

def _tamper(stack, sql, params):
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def test_tampered_invoice_scalar_is_detected(stack):
    asm = assembled(stack)
    _tamper(stack, "UPDATE canonical_invoices SET origin = 'KANDOO_SALE' "
                   "WHERE invoice_id = ?", (asm.invoice.invoice_id,))
    read = stack.assembly.read_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(read, AssemblyReadIntegrityFailure), read
    assert "verify FAILED" in read.reason


def test_tampered_field_value_is_detected(stack):
    asm = assembled(stack)
    _tamper(stack, "UPDATE canonical_fields SET canonical_value = '999.99' "
                   "WHERE invoice_id = ? AND canonical_seq = 0",
            (asm.invoice.invoice_id,))
    read = stack.assembly.read_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(read, AssemblyReadIntegrityFailure), read


def test_tampered_line_value_is_detected(stack):
    asm = assembled(stack)
    _tamper(stack, "UPDATE canonical_line_fields SET canonical_value = '1' "
                   "WHERE invoice_id = ? AND line_seq = 0 AND role = "
                   "'LINE_QUANTITY'", (asm.invoice.invoice_id,))
    read = stack.assembly.read_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(read, AssemblyReadIntegrityFailure), read


def test_tampered_anchor_value_is_detected(stack):
    asm = assembled(stack)
    _tamper(stack, "UPDATE canonical_header_anchors SET canonical_value = "
                   "'X' WHERE invoice_id = ? AND role = 'INVOICE_DATE'",
            (asm.invoice.invoice_id,))
    read = stack.assembly.read_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(read, AssemblyReadIntegrityFailure), read


def test_deleted_field_row_is_detected_as_inconsistent_set(stack):
    asm = assembled(stack)
    _tamper(stack, "DELETE FROM canonical_fields WHERE invoice_id = ? AND "
                   "canonical_seq = 0", (asm.invoice.invoice_id,))
    read = stack.assembly.read_assembled_invoice(asm.invoice.invoice_id)
    assert type(read).__name__ == "AssemblyReadVerificationUnavailable", read


def test_untampered_invoice_reads_clean(stack):
    asm = assembled(stack)
    read = stack.assembly.read_assembled_invoice(asm.invoice.invoice_id)
    assert isinstance(read, AssemblyReadSuccess)


# ---------------------------------------------------------------------------
# Storage-level CHECK/UNIQUE gates (OD-C3/OD-C6 backstops)
# ---------------------------------------------------------------------------

def test_unique_backstop_on_admission_decision_id(stack):
    asm = assembled(stack)
    record = asm.invoice
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO canonical_invoices (invoice_id, "
                "admission_decision_id, domain_state_id, normalization_id, "
                "extraction_id, document_id, capture_id, capture_s1, "
                "capture_s1_algorithm_id, origin, identity_class, "
                "identity_source, identity_fingerprint, customer_reference, "
                "customer_reference_reason, declaration_fingerprint, "
                "field_count, line_count, created_at, record_fingerprint, "
                "fingerprint_algorithm_id) VALUES ('other-id', ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, 1, 0, 'x', 'x', 'x')",
                (record.admission_decision_id, record.domain_state_id,
                 record.normalization_id, record.extraction_id,
                 record.document_id, record.capture_id, record.capture_s1,
                 record.capture_s1_algorithm_id, record.origin,
                 record.identity_class, record.identity_source,
                 record.identity_fingerprint, CUSTOMER_REF_REASON,
                 record.declaration_fingerprint))
    finally:
        conn.close()


def test_check_gate_refuses_origin_outside_frozen_vocabulary(stack):
    asm = assembled(stack)
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE canonical_invoices SET origin = 'SOME_POS' "
                "WHERE invoice_id = ?", (asm.invoice.invoice_id,))
    finally:
        conn.close()


def test_check_gate_refuses_inconsistent_provenance_pointers(stack):
    asm = assembled(stack)
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE canonical_fields SET provenance = 'DERIVED' "
                "WHERE invoice_id = ? AND canonical_seq = 0",
                (asm.invoice.invoice_id,))
    finally:
        conn.close()


def test_check_gate_refuses_value_on_absent_line_role(stack):
    from ca_helpers import PAGE_LINE_PARTIAL
    outcome = stack.build_accepted_lines_admission(
        PAGE_LINE_PARTIAL, label="ca-absent-gate")
    assert isinstance(outcome, CanonicalizationAccepted)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    asm = stack.assembly.assemble(invoice_id, {
        0: {"LINE_QUANTITY": "line.0.quantity",
            "LINE_UNIT_PRICE": "line.0.unit_price",
            "LINE_TOTAL": "line.0.total"},
        1: {"LINE_QUANTITY": "line.1.quantity",
            "LINE_UNIT_PRICE": "line.1.unit_price",
            "LINE_TOTAL": "line.1.total"}})
    assert isinstance(asm, AssemblyCompleted)
    absent = [lf for lf in asm.line_fields if not lf.present]
    assert len(absent) == 2                     # line 0: price + total absent
    conn = sqlite3.connect(str(stack.assembly_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE canonical_line_fields SET canonical_value = '5' "
                "WHERE invoice_id = ? AND present = 0",
                (asm.invoice.invoice_id,))
    finally:
        conn.close()
