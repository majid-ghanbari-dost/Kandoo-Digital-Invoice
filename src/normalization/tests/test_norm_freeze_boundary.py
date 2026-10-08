"""Pre-freeze boundary tests — DEFERRED / UNRESOLVED / DERIVED semantics
(SPEC-WP41-NORM §4.1 / §4.2, added by the 2026-10-05 freeze correction).

These tests PROVE the clarified WP-4.1 boundary without changing any behavior:

  1. DEFERRED is a NORMALIZATION-LAYER outcome — "cannot safely transform under the
     currently declared grammar → no interpretation, nothing invented, passed forward".
     It is NEVER the later domain/validation/canonicalization concept UNRESOLVED.
  2. WP-4.1 never creates, assigns, infers, or resolves UNRESOLVED — not as a status,
     not as a provenance label, not as a reason code, not as a durable datum.
  3. WP-4.1 performs no DERIVED computation: no unit_amount calculation from other
     fields, no semantic arithmetic between fields, no inference of missing values.
  4. The existing deterministic normalization behavior is UNCHANGED by the
     clarification (declared-grammar outputs identical to the 2026-10-01 baseline).

Behavior tests only — no line-coverage claims.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import sqlite3                                                  # noqa: E402
import pytest                                                   # noqa: E402

from extraction import ExtractedField, Provenance, SourceSpan  # noqa: E402
from normalization import (                                     # noqa: E402
    REASON_EMPTY_VALUE,
    REASON_NOT_IN_DECLARED_GRAMMAR,
    NormalizationCompleted,
    NormalizationReadSuccess,
    NormalizationStatus,
    ReferenceNormalizationRulesV1,
)

SPAN = SourceSpan(0, 0, 1, "fp")


def field(name, value, seq=0):
    return ExtractedField(seq, name, value, "utf-8", Provenance.EXTRACTED, SPAN)


def norm(name, value, ruleset=None):
    return (ruleset or ReferenceNormalizationRulesV1()).normalize_field(field(name, value))


def assert_deferred_not_unresolved(out, reason):
    """The DEFERRED ≠ UNRESOLVED contract at field level (SPEC §4.1)."""
    assert out.status is NormalizationStatus.DEFERRED          # normalization-layer outcome
    assert out.reason_code == reason                           # declared, stable reason
    assert out.normalized_value is None                        # nothing invented
    assert out.rules_applied == ""                             # no transformation applied
    assert out.source_provenance == "EXTRACTED"                # D-01 relayed verbatim
    # UNRESOLVED must not appear anywhere in this outcome:
    assert out.status.value != "UNRESOLVED"                    # ...not as the status
    assert "UNRESOLVED" not in {s.value for s in NormalizationStatus}   # ...not in the vocab
    assert "unresolved" not in (out.reason_code or "").lower() # ...not as a reason code


# ------------------------------------------------------------------ 1–3: DEFERRED ≠ UNRESOLVED

def test_ambiguous_numeric_is_deferred_not_unresolved():
    """'1.234' is thousands-ambiguous under the declared grammar → normalization-level
    DEFERRED. UNRESOLVED (a later domain/validation concept) is NOT produced."""
    assert_deferred_not_unresolved(norm("total.gross", "1.234"),
                                   REASON_NOT_IN_DECLARED_GRAMMAR)
    assert_deferred_not_unresolved(norm("unit_amount", "12,345"),
                                   REASON_NOT_IN_DECLARED_GRAMMAR)


def test_malformed_numeric_is_deferred_not_unresolved():
    """Malformed numeric representations → DEFERRED (nothing guessed, nothing repaired);
    never an UNRESOLVED datum."""
    for raw in ("1.2.3", "12 EUR", ".5", "12x5"):
        assert_deferred_not_unresolved(norm("total.gross", raw),
                                       REASON_NOT_IN_DECLARED_GRAMMAR)


def test_unsupported_date_is_deferred_not_unresolved():
    """Unsupported date representations (non-ISO shape, calendar-invalid) → DEFERRED;
    no locale parsing, no repair — and never UNRESOLVED."""
    for raw in ("01.10.2026", "2026/10/01", "2026-13-01", "2026-02-30"):
        assert_deferred_not_unresolved(norm("invoice.date", raw),
                                       REASON_NOT_IN_DECLARED_GRAMMAR)


def test_empty_and_whitespace_only_is_normalization_level_deferred():
    """Empty / whitespace-only input → the DECLARED normalization-level deferred behavior
    (reason empty-value): no value invented, no interpretation, no business meaning —
    and never UNRESOLVED."""
    for raw in ("", "   ", " \t\u00a0 "):
        assert_deferred_not_unresolved(norm("notes", raw), REASON_EMPTY_VALUE)
        assert_deferred_not_unresolved(norm("seller.name", raw), REASON_EMPTY_VALUE)


# ------------------------------------------------------------------ 4: UNRESOLVED datum sweep

def test_no_unresolved_datum_anywhere_in_durable_record(stack):
    """A corpus containing ambiguous + malformed + bad-date + empty values normalizes to a
    durable record that carries NO UNRESOLVED datum anywhere — not in the status
    vocabulary, not in any field status, not in any provenance label, not in any durable
    row (read path and raw store both checked)."""
    parts = [b"total.gross=1.234\nunit_amount=1.2.3\ninvoice.date=01.10.2026\n"
             b"notes=   \nseller.name=Acme\n"]
    extraction_id = stack.build_and_extract(parts)
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)

    # TOTAL positional mapping with explicit counts (4 deferred, 1 normalized, 0 rejected)
    assert done.record.field_count == len(done.fields) == 5
    assert done.record.deferred_count == 4
    assert done.record.normalized_count == 1
    assert done.record.rejected_count == 0

    # No UNRESOLVED anywhere at the object level
    assert "UNRESOLVED" not in {s.value for s in NormalizationStatus}
    for f in done.fields:
        assert f.status.value in {"NORMALIZED", "DEFERRED", "REJECTED"}
        assert f.status.value != "UNRESOLVED"
        assert f.source_provenance == "EXTRACTED"
        assert (f.reason_code or "").lower() != "unresolved"

    # No UNRESOLVED anywhere at the durable level (verified read + raw rows)
    nr = stack.norm.read_normalization(done.record.normalization_id)
    assert isinstance(nr, NormalizationReadSuccess)
    rows = stack.norm_store._conn.execute(
        """SELECT status, source_provenance, reason_code
             FROM normalization_fields WHERE normalization_id = ?""",
        (done.record.normalization_id,)).fetchall()
    assert len(rows) == 5
    for r in rows:
        assert r["status"] in ("NORMALIZED", "DEFERRED", "REJECTED")
        assert r["source_provenance"] == "EXTRACTED"
        assert (r["reason_code"] or "").lower() != "unresolved"


# ------------------------------------------------------------------ 5: no DERIVED computation

def test_wp41_never_produces_derived_values(stack):
    """WP-4.1 does not calculate DERIVED values (WP-4.2 territory): every normalized field
    relays the source D-01 label EXTRACTED verbatim; the layer never re-labels; the store
    STRUCTURALLY refuses DERIVED (and UNRESOLVED) provenance rows."""
    extraction_id = stack.build_and_extract()
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)
    assert {f.source_provenance for f in done.fields} == {"EXTRACTED"}
    assert "DERIVED" not in {f.source_provenance for f in done.fields}
    assert "UNRESOLVED" not in {f.source_provenance for f in done.fields}

    # Verified read delivers the same EXTRACTED-only provenance
    nr = stack.norm.read_normalization(done.record.normalization_id)
    assert isinstance(nr, NormalizationReadSuccess)
    assert {f.source_provenance for f in nr.fields} == {"EXTRACTED"}

    # Storage gate: non-EXTRACTED provenance cannot even be stored (DERIVED / UNRESOLVED)
    with pytest.raises(sqlite3.IntegrityError):
        stack.norm_store._conn.execute(
            """INSERT INTO normalization_fields (normalization_id, field_seq,
                   source_field_name, source_provenance, status, normalized_value,
                   rules_applied, reason_code)
               VALUES ('ghost-derived', 0, 'x', 'DERIVED', 'NORMALIZED', '5',
                       'nfc,trim', NULL)""")
    with pytest.raises(sqlite3.IntegrityError):
        stack.norm_store._conn.execute(
            """INSERT INTO normalization_fields (normalization_id, field_seq,
                   source_field_name, source_provenance, status, normalized_value,
                   rules_applied, reason_code)
               VALUES ('ghost-unresolved', 0, 'x', 'UNRESOLVED', 'NORMALIZED', '5',
                       'nfc,trim', NULL)""")


# ------------------------------------------------------------------ 6: no unit_amount arithmetic

def test_wp41_does_not_calculate_unit_amount_from_other_fields(stack):
    """WP-4.1 performs NO semantic arithmetic: with quantity=4 and total.net=100.00
    extracted, a unit_amount extracted as '25' normalizes to the grammar form of its OWN
    input ('25') — NOT '25.00' (100/4), NOT any other computed value. No extra field is
    invented, and a unit_amount absent from the extraction yields no normalized field."""
    parts = [b"quantity=4\ntotal.net=100.00\nunit_amount=25\n"]
    extraction_id = stack.build_and_extract(parts)
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)

    # TOTAL positional mapping: exactly the extracted fields, in order — nothing added
    assert [f.source_field_name for f in done.fields] == \
        ["quantity", "total.net", "unit_amount"]
    assert done.record.field_count == len(done.fields) == 3

    by_name = {f.source_field_name: f for f in done.fields}
    # unit_amount value comes from its own verbatim input through the declared grammar…
    ua = by_name["unit_amount"]
    assert ua.status is NormalizationStatus.NORMALIZED
    assert ua.normalized_value == "25"
    assert ua.rules_applied == "nfc,trim,number-canonical"
    # …and is NEVER the arithmetic result of the other fields (100.00 / 4 = 25.00)
    assert ua.normalized_value != "25.00"
    assert ua.normalized_value != "25.0"
    # the other fields are transformed independently (no cross-field calculation)
    assert by_name["quantity"].normalized_value == "4"
    assert by_name["total.net"].normalized_value == "100.00"

    # Missing-field non-inference: a document WITHOUT unit_amount produces NO unit_amount
    parts2 = [b"quantity=4\ntotal.net=100.00\n"]
    extraction_id2 = stack.build_and_extract(parts2, label="norm-no-ua")
    done2 = stack.norm.normalize(extraction_id2, "kandoo-norm-v1")
    assert isinstance(done2, NormalizationCompleted)
    assert [f.source_field_name for f in done2.fields] == ["quantity", "total.net"]
    assert not any(f.source_field_name == "unit_amount" for f in done2.fields)


# ------------------------------------------------------------------ 7: behavior unchanged

def test_existing_deterministic_normalization_behavior_unchanged(stack):
    """Freeze-correction regression guard: the declared grammar produces exactly the same
    canonical outputs as the 2026-10-01 baseline (no rule, status, mapping, precision, or
    determinism change), end-to-end through the service and the verified read."""
    parts = [b"total.gross= 1.234,56 \ntotal.net=129.90\nquantity=2,5\n"
             b"invoice.date= 2026-10-01 \nseller.name= Caf\xc3\xa9 GmbH \n"]
    extraction_id = stack.build_and_extract(parts)
    done = stack.norm.normalize(extraction_id, "kandoo-norm-v1")
    assert isinstance(done, NormalizationCompleted)

    expected = {
        "total.gross": "1234.56",        # European grouping → canonical decimal STRING
        "total.net": "129.90",           # precision preserved verbatim (no float)
        "quantity": "2.5",               # fractional quantity preserved
        "invoice.date": "2026-10-01",    # ISO date passes unchanged
        "seller.name": "Café GmbH",      # NFC + trim, internal value untouched
    }
    expected_rules = {
        "total.gross": "nfc,trim,number-canonical",
        "total.net": "nfc,trim,number-canonical",
        "quantity": "nfc,trim,number-canonical",
        "invoice.date": "nfc,trim,date-iso",
        "seller.name": "nfc,trim",
    }
    assert {f.source_field_name for f in done.fields} == set(expected)
    for f in done.fields:
        assert f.status is NormalizationStatus.NORMALIZED
        assert f.normalized_value == expected[f.source_field_name]
        assert f.rules_applied == expected_rules[f.source_field_name]
        assert f.source_provenance == "EXTRACTED"

    # The durable verified read delivers the identical deterministic content
    nr = stack.norm.read_normalization(done.record.normalization_id)
    assert isinstance(nr, NormalizationReadSuccess)
    assert {f.source_field_name: f.normalized_value for f in nr.fields} == expected
