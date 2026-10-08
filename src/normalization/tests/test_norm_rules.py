"""Rule-level unit tests — the declared deterministic grammar (SPEC-WP41-NORM §3).

Behavior tests: each declared rule is exercised with accepted and rejected inputs;
monetary values stay strings (never float); precision is preserved; nothing is guessed.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest                                                   # noqa: E402

from extraction import ExtractedField, Provenance, SourceSpan   # noqa: E402
from normalization import (                                     # noqa: E402
    REASON_CONTROL_CHARACTER,
    REASON_EMPTY_VALUE,
    REASON_NOT_IN_DECLARED_GRAMMAR,
    NormalizationStatus,
    ReferenceNormalizationRulesV1,
)

SPAN = SourceSpan(0, 0, 1, "fp")


def field(name, value, seq=0):
    return ExtractedField(seq, name, value, "utf-8", Provenance.EXTRACTED, SPAN)


def norm(name, value, ruleset=None):
    return (ruleset or ReferenceNormalizationRulesV1()).normalize_field(field(name, value))


# ---------------------------------------------------------------- text (R-T1, R-N1, R-N2)

def test_trim_strips_leading_and_trailing_whitespace_only():
    out = norm("seller.name", "  Acme GmbH \t")
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "Acme GmbH"          # edges stripped...
    assert out.rules_applied == "nfc,trim"


def test_internal_whitespace_is_never_touched():
    out = norm("seller.name", "Acme   GmbH\t Industries")
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "Acme   GmbH\t Industries"   # internal preserved verbatim


def test_nfc_normalization_is_applied_deterministically():
    out = norm("seller.name", "e\u0301" )               # combining acute → NFC precomposed é
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "é"


def test_unicode_whitespace_including_nbsp_is_trimmed():
    out = norm("seller.name", "\u00a0Acme\u00a0")
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "Acme"


def test_identifier_leading_zeros_are_preserved_for_text_fields():
    out = norm("invoice.number", "007-2026")
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "007-2026"           # no numeric interpretation of text


def test_unknown_field_name_falls_back_to_text_rules():
    out = norm("engine.specific.tempfield", "  hello  ")
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "hello"              # declared fallback — not a guess


# ---------------------------------------------------------------- empty / whitespace-only

def test_empty_value_is_deferred_not_invented():
    out = norm("notes", "")
    assert out.status is NormalizationStatus.DEFERRED
    assert out.normalized_value is None
    assert out.reason_code == REASON_EMPTY_VALUE


def test_whitespace_only_value_is_deferred():
    out = norm("notes", " \t\u00a0 ")
    assert out.status is NormalizationStatus.DEFERRED
    assert out.reason_code == REASON_EMPTY_VALUE


# ---------------------------------------------------------------- numbers (R-D1)

@pytest.mark.parametrize("raw,canonical", [
    ("42", "42"),                       # pure integer
    ("+42", "42"),                      # explicit plus dropped
    ("-42", "-42"),                     # negative preserved
    ("-0", "0"),                        # negative zero collapses
    ("007", "7"),                       # leading zeros stripped (typed numeric only)
    ("129.90", "129.90"),               # plain decimal — precision preserved
    ("0.500", "0.500"),                 # trailing zero NOT trimmed
    ("12,345.67", "12345.67"),          # English grouping
    ("1,234,567.89", "1234567.89"),     # multi-group English
    ("1.234,56", "1234.56"),            # European grouping with decimals
    ("1.234.567", "1234567"),           # multi-group European
    ("12.345,6", "12345.6"),            # European grouping, 1 frac digit
    ("0,5", "0.5"),                     # decimal comma
    ("1234.567", "1234.567"),           # 4-digit integer part → unambiguous decimal
])
def test_numeric_grammar_accepts_and_canonicalizes(raw, canonical):
    out = norm("total.gross", raw)
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == canonical
    assert out.rules_applied == "nfc,trim,number-canonical"


@pytest.mark.parametrize("raw", [
    "1.234",            # thousands-shape ambiguity (1234 vs 1.234)
    "12,345",           # same, comma variant
    "1.2.3",            # malformed multi-separator
    "12 EUR",           # currency symbol — never stripped, never converted
    "1 234",            # space-grouped without declared pattern
    ".5",               # no integer part
    "5.",               # no fraction digits
    "",                 # empty (covered by empty rule but must not normalize)
    "12x5",             # garbage
])
def test_malformed_or_ambiguous_numeric_input_is_deferred_never_guessed(raw):
    out = norm("total.gross", raw)
    if raw == "":
        assert out.status is NormalizationStatus.DEFERRED
        assert out.reason_code == REASON_EMPTY_VALUE
    else:
        assert out.status is NormalizationStatus.DEFERRED
        assert out.reason_code == REASON_NOT_IN_DECLARED_GRAMMAR
        assert out.normalized_value is None
        assert out.rules_applied == ""


def test_monetary_values_are_stored_as_strings_never_float():
    out = norm("total.gross", "129.90")
    assert isinstance(out.normalized_value, str)
    assert out.normalized_value == "129.90"             # exact precision, bit-for-bit


def test_negative_nonzero_decimal_keeps_sign():
    out = norm("total.gross", "-0012,50")
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "-12.50"


def test_decimal_quantities_preserve_fractional_part():
    out = norm("quantity", "2,5")                       # quantity is NOT forced to integer
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "2.5"


# ---------------------------------------------------------------- dates (R-DT1)

def test_iso_date_passes_unchanged():
    out = norm("invoice.date", " 2026-10-01 ")
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.normalized_value == "2026-10-01"
    assert out.rules_applied == "nfc,trim,date-iso"


@pytest.mark.parametrize("raw", ["01.10.2026", "2026/10/01", "2026-13-01",
                                 "2026-02-30", "not-a-date"])
def test_non_iso_or_invalid_dates_are_deferred(raw):
    out = norm("invoice.date", raw)
    assert out.status is NormalizationStatus.DEFERRED
    assert out.reason_code == REASON_NOT_IN_DECLARED_GRAMMAR


# ---------------------------------------------------------------- control gate (R-N0)

def test_control_character_anywhere_is_rejected():
    out = norm("seller.name", "Acme\x00GmbH")
    assert out.status is NormalizationStatus.REJECTED
    assert out.reason_code == REASON_CONTROL_CHARACTER
    assert out.normalized_value is None


def test_control_character_in_numeric_field_is_rejected_before_grammar():
    out = norm("total.gross", "12\x1b5")
    assert out.status is NormalizationStatus.REJECTED
    assert out.reason_code == REASON_CONTROL_CHARACTER


def test_structural_whitespace_controls_are_not_rejected():
    out = norm("seller.name", "line one\nline two")
    assert out.status is NormalizationStatus.NORMALIZED     # \n is declared-allowed
    assert out.normalized_value == "line one\nline two"


# ---------------------------------------------------------------- provenance + bookkeeping

def test_provenance_is_relayed_verbatim_and_field_seq_mirrored():
    rs = ReferenceNormalizationRulesV1()
    src = ExtractedField(7, "total.gross", "129.90", "utf-8",
                         Provenance.EXTRACTED, SPAN)
    out = rs.normalize_field(src)
    assert out.field_seq == 7
    assert out.source_field_name == "total.gross"
    assert out.source_provenance == "EXTRACTED"            # D-01 vocabulary relayed
    assert out.status is NormalizationStatus.NORMALIZED
    assert out.reason_code is None


def test_ruleset_identity_and_profile_are_declared():
    rs = ReferenceNormalizationRulesV1()
    assert rs.ruleset_id == "kandoo-norm-v1"
    assert rs.ruleset_version == "1"
    profile = rs.kind_profile
    assert profile["total.gross"] == "decimal"
    assert profile["invoice.date"] == "date"
    assert "seller.name" not in profile                    # falls back to text — declared


def test_custom_ruleset_identity_is_honored():
    rs = ReferenceNormalizationRulesV1(ruleset_id="kandoo-norm-v2", ruleset_version="2")
    assert (rs.ruleset_id, rs.ruleset_version) == ("kandoo-norm-v2", "2")


# ---------------------------------------------------------------- purity / determinism

def test_rule_functions_are_pure_same_input_same_output():
    rs = ReferenceNormalizationRulesV1()
    a = rs.normalize_field(field("total.gross", " 1.234,56 "))
    b = rs.normalize_field(field("total.gross", " 1.234,56 "))
    assert a == b
    assert a.normalized_value == "1234.56"
