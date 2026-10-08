"""Exact decimal-string arithmetic — WP-4.2 derivation engine core (SPEC-WP42-DER §4).

Normative semantics (OD-D8):
  - internal representation is the EXACT rational (stdlib fractions.Fraction),
    constructed ONLY from canonical decimal STRINGS — a float never exists anywhere in
    this module (no float literal, no float() call, no implicit conversion); the parser
    accepts only the declared canonical grammar and returns None otherwise, so
    conversion from float is structurally impossible.
  - ADD / SUB / MUL are exact by construction.
  - DIV executes only when the quotient is a TERMINATING decimal (reduced denominator
    has no prime factor other than 2 and 5); a non-terminating quotient is reported as
    non-exact and is NEVER rounded (D-08/WP-5.1 boundary — rounding is out of this WP).
  - the emitted result is the exact decimal expansion: no exponent notation, no
    rounding, no padding; trailing zeros of the exact expansion are stripped
    (value-preserving, deterministic); sign kept iff value ≠ 0.

All functions are PURE — no time, no locale, no randomness, no environment.
"""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Optional, Tuple

# Canonical decimal STRING grammar (the WP-4.1 decimal-kind output shape):
#   optional '-', integer part without leading zeros ("0" allowed), optional
#   fraction part of >= 1 digits. Anything else is refused (fail-closed).
_CANONICAL_DECIMAL_RE = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")

# Declared op vocabulary (closed — anything else can never execute)
OPS = ("ADD", "SUB", "MUL", "DIV")


class NonExactResult(Exception):
    """Raised by DIV when the exact quotient is not a terminating decimal — the
    engine surfaces it as a declared refusal (non-exact-result), never a rounding."""


def parse_canonical_decimal(value: str) -> Optional[Fraction]:
    """Canonical decimal string → exact rational, or None outside the declared grammar.

    Exact by construction: Fraction(str) parses decimal notation into an integer ratio
    without ever building a float ("1234.56" → 61728/50 exactly).
    """
    if not isinstance(value, str) or not _CANONICAL_DECIMAL_RE.match(value):
        return None
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError):        # defensive: regex already excludes these
        return None


def is_terminating_decimal(value: Fraction) -> bool:
    """True iff the reduced rational's denominator has no prime factor other than 2/5."""
    d = value.denominator
    d //= d & -d                                   # strip all factors of 2
    while d % 5 == 0:
        d //= 5
    return d == 1


def evaluate(op: str, operands: Tuple[Fraction, ...]) -> Fraction:
    """Apply one declared op to exact operands. Raises NonExactResult for a
    non-terminating DIV; ValueError for an undeclared op (defensive — the registry
    whitelist makes this unreachable through the service)."""
    if op == "ADD":
        result = operands[0]
        for v in operands[1:]:
            result += v
        return result
    if op == "SUB":
        result = operands[0]
        for v in operands[1:]:
            result -= v
        return result
    if op == "MUL":
        result = operands[0]
        for v in operands[1:]:
            result *= v
        return result
    if op == "DIV":
        if len(operands) != 2:
            raise ValueError("DIV arity must be exactly 2")
        result = operands[0] / operands[1]         # exact rational division
        if not is_terminating_decimal(result):
            raise NonExactResult(
                "quotient is not a terminating decimal — refused, never rounded")
        return result
    raise ValueError(f"undeclared arithmetic op: {op!r}")


def to_exact_decimal_string(value: Fraction) -> str:
    """Exact rational (terminating decimal) → canonical decimal string (SPEC §4).

    Minimal exact expansion: trailing zeros of the fraction part are stripped (a
    value-preserving operation, NOT rounding); integer results carry no fraction
    part; sign is kept iff the value is non-zero ('-0' can never be emitted).
    """
    num, den = value.numerator, value.denominator
    negative = num < 0
    num, den = abs(num), den

    # den divides a power of ten (guaranteed for terminating decimals): the number of
    # exact fraction digits needed is max(#factors of 2, #factors of 5) in den.
    twos = 0
    d = den
    while d % 2 == 0:
        d //= 2
        twos += 1
    fives = 0
    d = den
    while d % 5 == 0:
        d //= 5
        fives += 1
    scale = max(twos, fives)

    scaled = num * (10 ** scale) // den            # exact: den | 10**scale
    int_part, frac_part = divmod(scaled, 10 ** scale)
    if frac_part == 0:
        body = str(int_part)
    else:
        frac_str = str(frac_part).zfill(scale).rstrip("0")
        body = f"{int_part}.{frac_str}"
    if negative and any(ch != "0" for ch in body.replace(".", "")):
        return "-" + body
    return body
