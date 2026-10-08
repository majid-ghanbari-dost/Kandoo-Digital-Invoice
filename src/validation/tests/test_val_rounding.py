"""Rounding engine behavior tests — WP-5.1 (SPEC-WP51-VAL §4, D-08).

Exactness, explicit precision, declared mode semantics, no-float guarantee, and
reproducibility — the D-08 parametric rounding primitive.
"""
import sys
from pathlib import Path
from fractions import Fraction

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import (
    ROUNDING_MODES,
    RoundingModeError,
    round_exact,
    to_fixed_decimal_string,
)


class TestModeSemantics:
    def test_mode_vocabulary_is_declared_and_closed(self):
        assert ROUNDING_MODES == ("HALF_UP", "HALF_EVEN", "FLOOR", "CEILING", "DOWN")

    def test_half_up_ties_away_from_zero(self):
        assert round_exact(Fraction("2.5"), 0, "HALF_UP") == Fraction(3)
        assert round_exact(Fraction("-2.5"), 0, "HALF_UP") == Fraction(-3)
        assert round_exact(Fraction("2.675"), 2, "HALF_UP") == Fraction("2.68")

    def test_half_even_ties_to_nearest_even(self):
        assert round_exact(Fraction("2.5"), 0, "HALF_EVEN") == Fraction(2)
        assert round_exact(Fraction("3.5"), 0, "HALF_EVEN") == Fraction(4)
        # 2.685 scaled → 268.5 — exact tie onto an even unit → stays 268
        assert round_exact(Fraction("2.685"), 2, "HALF_EVEN") == Fraction("2.68")
        assert round_exact(Fraction("2.675"), 2, "HALF_EVEN") == Fraction("2.68")

    def test_half_up_vs_half_even_genuinely_differ_on_ties(self):
        value = Fraction("2.685")
        assert to_fixed_decimal_string(round_exact(value, 2, "HALF_UP"), 2) == "2.69"
        assert to_fixed_decimal_string(round_exact(value, 2, "HALF_EVEN"), 2) == \
            "2.68"

    def test_floor_toward_negative_infinity(self):
        assert round_exact(Fraction("2.9"), 0, "FLOOR") == Fraction(2)
        assert round_exact(Fraction("-2.1"), 0, "FLOOR") == Fraction(-3)
        assert round_exact(Fraction("-2.0"), 0, "FLOOR") == Fraction(-2)

    def test_ceiling_toward_positive_infinity(self):
        assert round_exact(Fraction("2.1"), 0, "CEILING") == Fraction(3)
        assert round_exact(Fraction("-2.9"), 0, "CEILING") == Fraction(-2)
        assert round_exact(Fraction("-2.0"), 0, "CEILING") == Fraction(-2)

    def test_down_toward_zero(self):
        assert round_exact(Fraction("2.9"), 0, "DOWN") == Fraction(2)
        assert round_exact(Fraction("-2.9"), 0, "DOWN") == Fraction(-2)

    def test_non_tie_modes_never_round_a_half_tie_implicitly_away(self):
        """FLOOR/CEILING/DOWN are directional, not tie-aware: the same value rounds
        differently under each declared mode — mode choice is explicit."""
        value = Fraction("2.5")
        assert round_exact(value, 0, "FLOOR") == Fraction(2)
        assert round_exact(value, 0, "CEILING") == Fraction(3)
        assert round_exact(value, 0, "DOWN") == Fraction(2)
        assert round_exact(value, 0, "HALF_UP") == Fraction(3)
        assert round_exact(value, 0, "HALF_EVEN") == Fraction(2)


class TestExactnessAndNoFloat:
    def test_classic_float_artifact_is_exact_here(self):
        """0.615 * 100 = 61.49999999999999... in IEEE-754; exactly 61.5 in
        rationals → HALF_UP gives 0.62 with NO float artifact."""
        assert to_fixed_decimal_string(round_exact(Fraction("0.615"), 2,
                                                   "HALF_UP"), 2) == "0.62"
        assert to_fixed_decimal_string(round_exact(Fraction("1.005"), 2,
                                                   "HALF_UP"), 2) == "1.01"

    def test_non_terminating_operand_rounds_deterministically(self):
        """Rounding an exact rational is well-defined even for 1/3 — the declared
        R2 rounded-equality purpose."""
        assert to_fixed_decimal_string(round_exact(Fraction(1, 3), 2, "HALF_UP"),
                                       2) == "0.33"
        assert to_fixed_decimal_string(round_exact(Fraction(2, 3), 2, "HALF_UP"),
                                       2) == "0.67"
        assert to_fixed_decimal_string(round_exact(Fraction(-1, 3), 2, "HALF_UP"),
                                       2) == "-0.33"

    def test_beyond_float53_precision_survives(self):
        big = Fraction(2 ** 60) + Fraction(1, 10 ** 25)
        rounded = round_exact(big, 25, "HALF_UP")
        assert to_fixed_decimal_string(rounded, 25).endswith("0000000000000000000000001")

    def test_result_is_always_exact_multiple_of_ten_pow_minus_precision(self):
        value = Fraction(10 ** 30 + 7, 10 ** 29)        # 10.0000000000000000000000000007
        for mode in ROUNDING_MODES:
            rounded = round_exact(value, 3, mode)
            assert (rounded * (10 ** 3)).denominator == 1

    def test_unknown_mode_refused(self):
        with pytest.raises(RoundingModeError):
            round_exact(Fraction(1), 2, "ROUND_HALF_UP")

    @pytest.mark.parametrize("bad", [-1, "2", 2.5, True, None])
    def test_invalid_precision_refused(self, bad):
        with pytest.raises(RoundingModeError):
            round_exact(Fraction(1), bad, "HALF_UP")
        with pytest.raises(RoundingModeError):
            to_fixed_decimal_string(Fraction(1), bad)


class TestFixedOutputForm:
    def test_precision_is_explicit_in_the_output(self):
        assert to_fixed_decimal_string(round_exact(Fraction(1080), 2, "HALF_UP"),
                                       2) == "1080.00"
        assert to_fixed_decimal_string(round_exact(Fraction("0.5"), 3,
                                                   "HALF_UP"), 3) == "0.500"
        assert to_fixed_decimal_string(round_exact(Fraction(7), 0, "HALF_UP"),
                                       0) == "7"

    def test_negative_zero_never_emitted(self):
        assert to_fixed_decimal_string(round_exact(Fraction(-1, 10 ** 6), 2,
                                                   "DOWN"), 2) == "0.00"

    def test_reproducibility_same_inputs_same_output(self):
        value = Fraction("1234.5675")
        for mode in ROUNDING_MODES:
            first = to_fixed_decimal_string(round_exact(value, 3, mode), 3)
            for _ in range(3):
                assert to_fixed_decimal_string(round_exact(value, 3, mode), 3) == \
                    first

    def test_non_rounded_value_is_preserved_verbatim_when_acceptable(self):
        """An exact value acceptable without rounding keeps its exact value (the
        service path asserts rounding_applied = 0 there; here the primitive itself
        is value-preserving on already-exact operands)."""
        assert round_exact(Fraction("1080"), 2, "HALF_UP") == Fraction("1080")
        assert to_fixed_decimal_string(Fraction("1080"), 2) == "1080.00"

    def test_fixed_formatter_refuses_non_rounded_operands(self):
        with pytest.raises(ValueError):
            to_fixed_decimal_string(Fraction(1, 3), 2)
