"""Explicit parametric rounding over EXACT rationals — WP-5.1 R2 core (SPEC §4).

Normative semantics (D-08 / OD-V8-adjacent, declared here):
  - the operand is an EXACT rational (fractions.Fraction) — a float never exists in
    this module (no float literal, no float() call, no implicit conversion); rounding
    an exact rational at a declared precision is well-defined and reproducible, even
    for non-terminating operands (e.g. 1/3 @ 2, HALF_UP → 0.33) — that is the whole
    point of the declared R2 rounded-equality rule type;
  - modes (declared whitelist, closed):
      HALF_UP   ties away from zero
      HALF_EVEN ties to nearest even
      FLOOR     toward negative infinity
      CEILING   toward positive infinity
      DOWN      toward zero (truncation)
  - output form: to_fixed_decimal_string emits EXACTLY `precision` fraction digits —
    explicit precision, never stripped, never exponent notation; same
    (value, precision, mode) ALWAYS yields the same string;
  - NO implicit rounding exists anywhere in this layer: every rounding carries its
    (rule_id, rule_version, precision, mode, input, output) audit record (SPEC §4),
    and exact values acceptable without rounding are preserved verbatim.

All functions are PURE — no time, no locale, no randomness, no environment (SPEC §6).
"""
from __future__ import annotations

from fractions import Fraction
from typing import Tuple

from derivation.arithmetic import is_terminating_decimal, to_exact_decimal_string

# Declared rounding-mode vocabulary (closed — anything else can never execute)
ROUNDING_MODES: Tuple[str, ...] = ("HALF_UP", "HALF_EVEN", "FLOOR", "CEILING", "DOWN")


class RoundingModeError(Exception):
    """Raised for a mode outside the declared whitelist (defensive — the registry
    whitelist makes this unreachable through the service)."""


def _sign_quotient_remainder(value: Fraction) -> Tuple[int, int, int]:
    """Split an exact rational into (sign, integer magnitude quotient, remainder)
    over denominator d: |value| = q + r/d with 0 <= r < d."""
    n, d = value.numerator, value.denominator
    sign = -1 if n < 0 else 1
    q, r = divmod(abs(n), d)
    return sign, q, r


def round_exact(value: Fraction, precision: int, mode: str) -> Fraction:
    """Round an exact rational to `precision` fraction digits under the declared
    mode. Exact by construction: only integer arithmetic over numerator/denominator
    — the result is always an exact multiple of 10^-precision."""
    if mode not in ROUNDING_MODES:
        raise RoundingModeError(f"undeclared rounding mode: {mode!r} "
                                f"(declared vocabulary: {', '.join(ROUNDING_MODES)})")
    if not isinstance(precision, int) or isinstance(precision, bool) or precision < 0:
        raise RoundingModeError("precision must be a non-negative integer")
    scaled = value * (Fraction(10) ** precision)      # exact
    sign, q, r = _sign_quotient_remainder(scaled)
    d = scaled.denominator

    if mode == "DOWN":
        unit = q                                       # toward zero — magnitude floor
    elif mode == "FLOOR":
        unit = q if sign > 0 or r == 0 else q + 1      # toward −∞
    elif mode == "CEILING":
        unit = q if sign < 0 or r == 0 else q + 1      # toward +∞
    elif mode == "HALF_UP":
        unit = q + 1 if 2 * r >= d else q              # ties away from zero
    else:                                              # HALF_EVEN
        if 2 * r > d:
            unit = q + 1
        elif 2 * r < d:
            unit = q
        else:                                          # exact tie → nearest even
            unit = q if q % 2 == 0 else q + 1
    return Fraction(sign * unit, 10 ** precision)


def exact_value_string(value: Fraction) -> str:
    """Faithful deterministic string of an EXACT rational (the rounding audit
    input, SPEC §4): a terminating decimal yields its minimal exact decimal
    expansion; a non-terminating rational has NO finite decimal expansion, so its
    exact value is recorded as the canonical reduced fraction string "p/q"
    (denominator > 0) — the same rational always yields the same string, and
    Fraction(p/q-string) reproduces the rounding output exactly."""
    if is_terminating_decimal(value):
        return to_exact_decimal_string(value)
    num, den = value.numerator, value.denominator
    return f"{num}/{den}"          # Fraction is always reduced; den > 0 by design


def to_fixed_decimal_string(value: Fraction, precision: int) -> str:
    """Exact rational that is a multiple of 10^-precision → fixed-point decimal
    string with EXACTLY `precision` fraction digits (explicit precision form).

    round_exact results always satisfy the precondition. Sign is kept iff the
    value is non-zero ('-0' can never be emitted)."""
    if not isinstance(precision, int) or isinstance(precision, bool) or precision < 0:
        raise RoundingModeError("precision must be a non-negative integer")
    num, den = value.numerator, value.denominator
    scaled_num = num * (10 ** precision)
    if scaled_num % den != 0:
        raise ValueError(
            "value is not an exact multiple of 10^-precision — "
            "to_fixed_decimal_string accepts only round_exact results")
    units = scaled_num // den
    negative = units < 0
    units = abs(units)
    int_part, frac_part = divmod(units, 10 ** precision)
    if precision == 0:
        body = str(int_part)
    else:
        body = f"{int_part}.{str(frac_part).zfill(precision)}"
    if negative and units != 0:
        return "-" + body
    return body
