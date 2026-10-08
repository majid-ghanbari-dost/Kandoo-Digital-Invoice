"""WP-6.2 canonical assembly engine tests — pure, deterministic (SPEC §3/§5/
§6; dispatch §13 axes 3, 5, 19, 22, 23 + declaration mechanics)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ca_helpers import LINE_BINDING, PAGE_LINES_OK  # noqa: E402
from canonical_assembly import (  # noqa: E402
    HEADER_ROLES,
    LINE_ROLES,
    REJECT_DECLARED_FIELD_AMBIGUOUS,
    ROLE_INVOICE_DATE,
    ROLE_INVOICE_NUMBER,
    ROLE_INVOICE_TOTAL,
    declaration_bytes,
    identity_anchor_payload,
    resolve_declared_field,
    validate_line_binding,
    assemble_header_anchors,
    assemble_fields,
    assemble_lines,
)
from capture import S1Service  # noqa: E402
from normalization.model import NormalizationStatus  # noqa: E402
from normalization.model import NormalizedField  # noqa: E402


def norm_field(seq, name, value, status="NORMALIZED"):
    return NormalizedField(
        field_seq=seq, source_field_name=name, source_provenance="EXTRACTED",
        status=NormalizationStatus(status)
        if isinstance(status, str) else status,
        normalized_value=value if status == "NORMALIZED" else None,
        rules_applied="nfc,trim" if status == "NORMALIZED" else "",
        reason_code=None if status == "NORMALIZED" else "not-in-declared-grammar")


# ---------------------------------------------------------------------------
# Declaration validation (SPEC §3 — OD-A4)
# ---------------------------------------------------------------------------

def test_declaration_none_and_empty_are_the_same():
    assert validate_line_binding(None) is None
    assert validate_line_binding({}) is None
    assert declaration_bytes(None) == declaration_bytes({})


def test_declaration_normalizes_and_sorts_line_keys():
    normalized = validate_line_binding(LINE_BINDING)
    assert sorted(normalized.keys()) == [0, 1]
    for key, roles in normalized.items():
        assert set(roles.keys()) == set(LINE_ROLES)


def test_declaration_rejects_non_mapping():
    with pytest.raises(ValueError):
        validate_line_binding("lines")


def test_declaration_rejects_partial_roles():
    with pytest.raises(ValueError):
        validate_line_binding({0: {"LINE_QUANTITY": "q"}})


def test_declaration_rejects_unknown_roles():
    with pytest.raises(ValueError):
        validate_line_binding({0: {"LINE_QUANTITY": "q",
                                   "LINE_UNIT_PRICE": "u",
                                   "LINE_TOTAL": "t",
                                   "LINE_EXTRA": "x"}})


def test_declaration_rejects_non_integer_keys():
    with pytest.raises(ValueError):
        validate_line_binding({"0": {"LINE_QUANTITY": "q",
                                     "LINE_UNIT_PRICE": "u",
                                     "LINE_TOTAL": "t"}})
    with pytest.raises(ValueError):
        validate_line_binding({-1: {"LINE_QUANTITY": "q",
                                    "LINE_UNIT_PRICE": "u",
                                    "LINE_TOTAL": "t"}})


def test_declaration_rejects_empty_and_non_string_targets():
    with pytest.raises(ValueError):
        validate_line_binding({0: {"LINE_QUANTITY": "",
                                   "LINE_UNIT_PRICE": "u",
                                   "LINE_TOTAL": "t"}})
    with pytest.raises(ValueError):
        validate_line_binding({0: {"LINE_QUANTITY": 7,
                                   "LINE_UNIT_PRICE": "u",
                                   "LINE_TOTAL": "t"}})


def test_declaration_rejects_duplicate_targets_within_line():
    with pytest.raises(ValueError):
        validate_line_binding({0: {"LINE_QUANTITY": "x",
                                   "LINE_UNIT_PRICE": "x",
                                   "LINE_TOTAL": "t"}})


def test_declaration_rejects_duplicate_targets_across_lines():
    with pytest.raises(ValueError):
        validate_line_binding({
            0: {"LINE_QUANTITY": "x", "LINE_UNIT_PRICE": "u0",
                "LINE_TOTAL": "t0"},
            1: {"LINE_QUANTITY": "x", "LINE_UNIT_PRICE": "u1",
                "LINE_TOTAL": "t1"}})


def test_declaration_rejects_bool_line_keys_int_collision():
    # bool keys are rejected BEFORE int-collapsing (True == 1 in dicts) —
    # duplicate/aliased line keys can never enter the declaration silently
    with pytest.raises(ValueError):
        validate_line_binding({True: {"LINE_QUANTITY": "q",
                                      "LINE_UNIT_PRICE": "u",
                                      "LINE_TOTAL": "t"}})
    with pytest.raises(ValueError):
        validate_line_binding({-1: {"LINE_QUANTITY": "q",
                                    "LINE_UNIT_PRICE": "u",
                                    "LINE_TOTAL": "t"}})


def test_declaration_fingerprint_is_deterministic_and_order_stable():
    s1 = S1Service()
    a = declaration_bytes(LINE_BINDING)
    b = declaration_bytes({0: LINE_BINDING[0], 1: LINE_BINDING[1]})
    assert a == b
    fp1 = s1.compute(a)
    fp2 = s1.compute(b)
    assert fp1.s1 == fp2.s1 and fp1.s1_algorithm_id == "sha256-v1"


# ---------------------------------------------------------------------------
# Declared field resolution (SPEC §6 L1 — OD-A5)
# ---------------------------------------------------------------------------

def test_resolve_one_usable_row():
    fields = [norm_field(0, "q", "2"), norm_field(1, "u", "500.00")]
    r = resolve_declared_field("q", fields)
    assert r.candidate_count == 1 and r.value == "2" and r.field_seq == 0


def test_resolve_zero_usable_rows_is_absent_not_invented():
    fields = [norm_field(0, "u", "500.00")]
    r = resolve_declared_field("missing", fields)
    assert r.candidate_count == 0 and r.value is None


def test_resolve_ignores_empty_and_non_normalized_rows():
    fields = [norm_field(0, "q", ""),                # empty → not usable
              norm_field(1, "q", None, "DEFERRED"),  # DEFERRED → not usable
              norm_field(2, "q", "ok")]
    r = resolve_declared_field("q", fields)
    assert r.candidate_count == 1 and r.value == "ok" and r.field_seq == 2


def test_resolve_counts_multiple_candidates_for_ambiguity_refusal():
    fields = [norm_field(0, "q", "2"), norm_field(1, "q", "9")]
    r = resolve_declared_field("q", fields)
    assert r.candidate_count == 2 and r.value is None


# ---------------------------------------------------------------------------
# Field inventory (SPEC §5 C1/C2/C3 — OD-A3/OD-A10)
# ---------------------------------------------------------------------------

class _StubDerivationRead:
    class record:                                   # noqa: N801 (stub shape)
        output_field_name = "total.gross"
        output_value = "1274.4"
        formula_id = "f"
        formula_version = "1"
        derivation_id = "d-1"


def test_field_inventory_extracted_then_derived_in_declared_order():
    fields = [
        norm_field(3, "tax.amount", "94.40"),
        norm_field(0, "invoice.number", "INV-1"),
        norm_field(1, "invoice.date", "2026-10-08"),
        norm_field(2, "total.net", "1180.00"),
        norm_field(4, "skipped.deferred", None, "DEFERRED"),
    ]
    entries = assemble_fields("inv-1", "norm-1", fields,
                              [_StubDerivationRead()])
    assert [e.canonical_seq for e in entries] == list(range(5))
    assert [e.field_name for e in entries[:4]] == [
        "invoice.number", "invoice.date", "total.net", "tax.amount"]
    assert all(e.provenance == "EXTRACTED" for e in entries[:4])
    assert entries[0].source_normalization_id == "norm-1"
    assert entries[0].source_field_seq == 0
    last = entries[4]
    assert last.provenance == "DERIVED"
    assert last.field_name == "total.gross"
    assert last.canonical_value == "1274.4"
    assert last.source_derivation_id == "d-1"
    assert last.source_field_seq is None
    assert last.source_normalization_id == ""


def test_field_inventory_values_are_verbatim_no_renaming_no_defaults():
    fields = [norm_field(0, "engine.vocabulary_1", "raw,Value-x")]
    (entry,) = assemble_fields("inv-1", "norm-1", fields, [])
    assert entry.field_name == "engine.vocabulary_1"   # relayed verbatim
    assert entry.canonical_value == "raw,Value-x"      # byte-identical


# ---------------------------------------------------------------------------
# Header anchors + identity anchor payload (SPEC §5 C4, §4 A6 — OD-A2/OD-A6)
# ---------------------------------------------------------------------------

class _StubPointer:
    def __init__(self, role, name, seq):
        self.role, self.source_field_name = role, name
        self.normalization_id, self.field_seq = "norm-1", seq


def test_header_anchors_rejoin_in_frozen_role_order():
    fields = [norm_field(0, "invoice.number", "INV-1"),
              norm_field(1, "invoice.date", "2026-10-08"),
              norm_field(2, "total.net", "1180.00")]
    pointers = [_StubPointer("INVOICE_TOTAL", "total.net", 2),
                _StubPointer("INVOICE_NUMBER", "invoice.number", 0),
                _StubPointer("INVOICE_DATE", "invoice.date", 1)]
    anchors = assemble_header_anchors("inv-1", pointers, fields)
    assert [a.role for a in anchors] == list(HEADER_ROLES)
    assert anchors[0].canonical_value == "INV-1"
    assert anchors[1].canonical_value == "2026-10-08"
    assert anchors[2].canonical_value == "1180.00"
    assert all(a.invoice_id == "inv-1" for a in anchors)


def test_header_anchors_fail_closed_on_dangling_pointer():
    fields = [norm_field(0, "invoice.number", "INV-1")]
    pointers = [_StubPointer("INVOICE_NUMBER", "invoice.number", 0),
                _StubPointer("INVOICE_DATE", "invoice.date", 1),
                _StubPointer("INVOICE_TOTAL", "total.net", 2)]
    with pytest.raises(ValueError):
        assemble_header_anchors("inv-1", pointers, fields)


def test_identity_anchor_payload_quotes_the_p61_od_g4_serialization():
    fields = [norm_field(0, "invoice.number", "INV-1"),
              norm_field(1, "invoice.date", "2026-10-08"),
              norm_field(2, "total.net", "1180.00")]
    pointers = [_StubPointer("INVOICE_NUMBER", "invoice.number", 0),
                _StubPointer("INVOICE_DATE", "invoice.date", 1),
                _StubPointer("INVOICE_TOTAL", "total.net", 2)]
    anchors = assemble_header_anchors("inv-1", pointers, fields)
    payload = identity_anchor_payload("HOLOO_CAPTURE", anchors)
    # The SAME payload P6.1's identity.py serializes for the S2 fingerprint:
    from canonicalization.identity import _chunk  # the exact OD-G4 encoding
    expected = b"".join([_chunk("HOLOO_CAPTURE"), _chunk("INV-1"),
                         _chunk("2026-10-08"), _chunk("1180.00")])
    assert payload == expected
    assert S1Service().compute(payload).s1 != ""
    # scope: the declared origin is part of the anchor (source-system scope)
    other = identity_anchor_payload("OTHER_POS_CAPTURE", anchors)
    assert other != payload


# ---------------------------------------------------------------------------
# Line assembly (SPEC §6 — OD-A4/OD-A5)
# ---------------------------------------------------------------------------

def test_line_assembly_orders_by_declared_key_not_dict_order():
    reversed_binding = {1: LINE_BINDING[1], 0: LINE_BINDING[0]}
    fields = [
        norm_field(0, "invoice.number", "INV-1"),
        norm_field(4, "line.0.quantity", "2"),
        norm_field(5, "line.0.unit_price", "500.00"),
        norm_field(6, "line.0.total", "1000.00"),
        norm_field(7, "line.1.quantity", "3"),
        norm_field(8, "line.1.unit_price", "60.00"),
        norm_field(9, "line.1.total", "180.00"),
    ]
    lines, line_fields, rejected = assemble_lines(
        "inv-1", "norm-1", validate_line_binding(reversed_binding), fields)
    assert [l.line_seq for l in lines] == [0, 1]        # ascending, explicit
    assert rejected == ()
    by_line = {}
    for lf in line_fields:
        by_line.setdefault(lf.line_seq, []).append((lf.role, lf.present,
                                                    lf.canonical_value))
    assert [r for r, _, _ in by_line[0]] == list(LINE_ROLES)
    assert by_line[0][0] == ("LINE_QUANTITY", 1, "2")
    assert by_line[1][2] == ("LINE_TOTAL", 1, "180.00")


def test_line_assembly_records_absent_roles_without_inventing():
    fields = [norm_field(4, "line.0.quantity", "7")]
    lines, line_fields, rejected = assemble_lines(
        "inv-1", "norm-1", validate_line_binding({
            0: {"LINE_QUANTITY": "line.0.quantity",
                "LINE_UNIT_PRICE": "line.0.unit_price",
                "LINE_TOTAL": "line.0.total"}}), fields)
    assert len(lines) == 1 and rejected == ()
    present = [lf for lf in line_fields if lf.present == 1]
    absent = [lf for lf in line_fields if lf.present == 0]
    assert len(present) == 1 and present[0].canonical_value == "7"
    assert len(absent) == 2
    assert all(a.canonical_value is None and a.source_field_name == ""
               and a.normalization_id == "" and a.field_seq is None
               for a in absent)


def test_line_assembly_rejects_all_absent_line_explicitly():
    fields = [norm_field(7, "line.1.quantity", "1")]
    lines, line_fields, rejected = assemble_lines(
        "inv-1", "norm-1", validate_line_binding({
            0: {"LINE_QUANTITY": "line.0.quantity",
                "LINE_UNIT_PRICE": "line.0.unit_price",
                "LINE_TOTAL": "line.0.total"},
            1: {"LINE_QUANTITY": "line.1.quantity",
                "LINE_UNIT_PRICE": "line.1.unit_price",
                "LINE_TOTAL": "line.1.total"}}), fields)
    assert [l.line_seq for l in lines] == [1]
    assert [(r.line_seq, r.reason) for r in rejected] == \
        [(0, "empty-line-rejected")]
    assert all(lf.line_seq == 1 for lf in line_fields)


def test_line_assembly_ambiguity_raises_for_whole_request_refusal():
    fields = [norm_field(0, "line.0.quantity", "2"),
              norm_field(1, "line.0.quantity", "9")]
    with pytest.raises(ValueError) as exc:
        assemble_lines("inv-1", "norm-1", validate_line_binding({
            0: {"LINE_QUANTITY": "line.0.quantity",
                "LINE_UNIT_PRICE": "line.0.unit_price",
                "LINE_TOTAL": "line.0.total"}}), fields)
    assert REJECT_DECLARED_FIELD_AMBIGUOUS in str(exc.value)


def test_line_assembly_empty_declaration_yields_no_lines():
    lines, line_fields, rejected = assemble_lines(
        "inv-1", "norm-1", None, [norm_field(0, "q", "2")])
    assert lines == () and line_fields == () and rejected == ()
