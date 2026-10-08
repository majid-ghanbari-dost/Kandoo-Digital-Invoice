"""WP-4.2 exact-arithmetic tests — no-float proof, exactness, declared refusal of
non-terminating division, canonical output form (SPEC-WP42-DER §4)."""
import sys
from fractions import Fraction
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from derivation.arithmetic import (          # noqa: E402
    NonExactResult,
    evaluate,
    is_terminating_decimal,
    parse_canonical_decimal,
    to_exact_decimal_string,
)


class TestParse:
    def test_parse_is_exact_rational_never_float(self):
        v = parse_canonical_decimal("0.1")
        assert isinstance(v, Fraction) and not isinstance(v, float)
        assert v == Fraction(1, 10)

    def test_parse_canonical_shapes(self):
        assert parse_canonical_decimal("1234.56") == Fraction(61728, 50)
        assert parse_canonical_decimal("-12.5") == Fraction(-25, 2)
        assert parse_canonical_decimal("80") == Fraction(80)
        assert parse_canonical_decimal("0") == Fraction(0)
        assert parse_canonical_decimal("0.05") == Fraction(1, 20)

    def test_parse_refuses_everything_outside_the_canonical_grammar(self):
        for bad in ("1.2.3", "1,234.56", "01.5", "+5", "1e5", " 1", "1 ", "",
                    "abc", "1.", ".5", "--1", "0x10", "١٢٣"):
            assert parse_canonical_decimal(bad) is None, bad

    def test_parse_refuses_non_string_types(self):
        for bad in (None, 5, 0.1, Fraction(1, 2), b"1.5"):
            assert parse_canonical_decimal(bad) is None


class TestExactOps:
    def test_add_is_exact_where_float_would_drift(self):
        # float 0.1 + 0.2 == 0.30000000000000004 — exact arithmetic must yield 0.3
        result = evaluate("ADD", (parse_canonical_decimal("0.1"),
                                  parse_canonical_decimal("0.2")))
        assert to_exact_decimal_string(result) == "0.3"

    def test_add_preserves_full_precision_beyond_float53(self):
        big = "100000000000000000000000000000.01"        # > 2^53 significance
        result = evaluate("ADD", (parse_canonical_decimal(big),
                                  parse_canonical_decimal("0.01")))
        assert to_exact_decimal_string(result) == \
            "100000000000000000000000000000.02"

    def test_sub_is_exact_and_signed(self):
        result = evaluate("SUB", (parse_canonical_decimal("10.5"),
                                  parse_canonical_decimal("20.25")))
        assert to_exact_decimal_string(result) == "-9.75"

    def test_mul_is_exact_over_many_digits(self):
        result = evaluate("MUL", (parse_canonical_decimal("12345678901234567890.5"),
                                  parse_canonical_decimal("98765432109876543210.5")))
        # exact integer product, asserted digit-by-digit against the true value
        expected = Fraction("12345678901234567890.5") * Fraction("98765432109876543210.5")
        assert result == expected
        assert to_exact_decimal_string(result) == to_exact_decimal_string(expected)

    def test_div_exact_terminating_quotient_is_allowed(self):
        result = evaluate("DIV", (Fraction(100), Fraction(4)))
        assert to_exact_decimal_string(result) == "25"

    def test_div_non_terminating_quotient_is_refused_never_rounded(self):
        with pytest.raises(NonExactResult):
            evaluate("DIV", (Fraction(1), Fraction(3)))
        with pytest.raises(NonExactResult):
            evaluate("DIV", (Fraction(1000), Fraction(6)))      # 166.6̄

    def test_div_by_zero_is_refused(self):
        with pytest.raises(Exception):
            evaluate("DIV", (Fraction(1), Fraction(0)))

    def test_undeclared_op_is_refused(self):
        with pytest.raises(ValueError):
            evaluate("POW", (Fraction(2), Fraction(3)))


class TestTerminating:
    def test_terminating_classification(self):
        assert is_terminating_decimal(Fraction(1, 2)) is True
        assert is_terminating_decimal(Fraction(1, 8)) is True
        assert is_terminating_decimal(Fraction(1, 10)) is True
        assert is_terminating_decimal(Fraction(3, 1)) is True
        assert is_terminating_decimal(Fraction(1, 3)) is False
        assert is_terminating_decimal(Fraction(1, 6)) is False
        assert is_terminating_decimal(Fraction(1, 7)) is False


class TestCanonicalOutput:
    def test_minimal_exact_expansion(self):
        assert to_exact_decimal_string(Fraction(1080)) == "1080"          # no .00 padding
        assert to_exact_decimal_string(Fraction(108, 10)) == "10.8"       # trailing 0 stripped
        assert to_exact_decimal_string(Fraction(3, 10)) == "0.3"
        assert to_exact_decimal_string(Fraction(-39, 4)) == "-9.75"
        assert to_exact_decimal_string(Fraction(0)) == "0"                # never "-0"

    def test_output_is_round_trip_stable(self):
        for text in ("0.3", "1080", "-9.75", "1234.56", "0.05"):
            back = parse_canonical_decimal(text)
            assert back is not None
            assert to_exact_decimal_string(back) == text

    def test_same_exact_result_always_yields_same_string(self):
        a = evaluate("ADD", (parse_canonical_decimal("1.50"),
                             parse_canonical_decimal("2.50")))
        b = evaluate("ADD", (parse_canonical_decimal("2"),
                             parse_canonical_decimal("2")))
        assert to_exact_decimal_string(a) == to_exact_decimal_string(b) == "4"
