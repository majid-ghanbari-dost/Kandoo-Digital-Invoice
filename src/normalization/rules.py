"""Deterministic normalization rule set — WP-4.1 MVP (SPEC-WP41-NORM §3).

The ruleset is the replaceable seam of the normalization layer (D-09-safe, exactly like
the P3 engine seam): the service receives it constructor-injected, knows nothing about
its internals, and NO engine module is imported here — normalization is engine-independent
by construction (the seam consumes ExtractedField values only).

ReferenceNormalizationRulesV1 implements the declared MVP grammar:
  order: control gate (R-N0) → NFC (R-N1) → trim (R-N2) → empty (R-N3) → kind rule
  kinds: text (R-T1) | decimal (R-D1) | date (R-DT1); unknown field names → text fallback.
All functions are PURE — no time, no locale, no randomness, no environment (SPEC §6).
Monetary/quantity values are canonical decimal STRINGS — floating point is never used.
Fraction digits are preserved verbatim (no rounding, no trailing-zero trimming).
"""
from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from datetime import date
from typing import Mapping, Optional, Tuple

from extraction import ExtractedField, Provenance

from .model import (
    REASON_CONTROL_CHARACTER,
    REASON_EMPTY_VALUE,
    REASON_NOT_IN_DECLARED_GRAMMAR,
    NormalizationStatus,
    NormalizedField,
)

# Rule ids recorded in rules_applied (declared, stable)
RULE_NFC = "nfc"
RULE_TRIM = "trim"
RULE_NUMBER = "number-canonical"
RULE_DATE = "date-iso"

_TEXT_RULES = f"{RULE_NFC},{RULE_TRIM}"
_NUMBER_RULES = f"{RULE_NFC},{RULE_TRIM},{RULE_NUMBER}"
_DATE_RULES = f"{RULE_NFC},{RULE_TRIM},{RULE_DATE}"

# Declared control gate: Unicode category Cc, EXCEPT structural whitespace \t \n \r
_CTRL_ALLOWED = frozenset("\t\n\r")

_INT_RE = re.compile(r"^[+-]?[0-9]+$")
_SINGLE_SEP_RE = re.compile(r"^([+-]?)([0-9]+)([.,])([0-9]+)$")
_EURO_RE = re.compile(r"^([+-]?)([0-9]{1,3}(?:\.[0-9]{3})+)(?:,([0-9]+))?$")
_ENG_RE = re.compile(r"^([+-]?)([0-9]{1,3}(?:,[0-9]{3})+)(?:\.([0-9]+))?$")
_ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class NormalizationRuleSet(ABC):
    """Replaceable ruleset seam of the normalization layer (SPEC §3)."""

    @property
    @abstractmethod
    def ruleset_id(self) -> str:
        """Stable ruleset identity — part of the INV-N-1:1 uniqueness triple."""

    @property
    @abstractmethod
    def ruleset_version(self) -> str:
        """Version of the declared grammar — part of the triple; future rules = new version."""

    @abstractmethod
    def normalize_field(self, field: ExtractedField) -> NormalizedField:
        """Apply the declared deterministic chain to ONE extracted field. Pure function."""


class ReferenceNormalizationRulesV1(NormalizationRuleSet):
    """Reference ruleset (MVP executability choice, NOT a business-rule decision — OD-N8).

    kind_profile maps field_name → SYNTAX kind (date | decimal | text). It declares HOW to
    standardize the string — never WHAT the value means; unknown names fall back to `text`
    (declared fallback). No canonical field mapping happens anywhere (P6 boundary).
    """

    def __init__(self, ruleset_id: str = "kandoo-norm-v1",
                 ruleset_version: str = "1",
                 kind_profile: Optional[Mapping[str, str]] = None) -> None:
        self._ruleset_id = ruleset_id
        self._ruleset_version = ruleset_version
        self._kind_profile: Mapping[str, str] = dict(kind_profile or _DEFAULT_PROFILE)

    @property
    def ruleset_id(self) -> str:
        return self._ruleset_id

    @property
    def ruleset_version(self) -> str:
        return self._ruleset_version

    @property
    def kind_profile(self) -> Mapping[str, str]:
        return dict(self._kind_profile)

    # -- the deterministic per-field pipeline (SPEC §3 order) ----------------

    def normalize_field(self, field: ExtractedField) -> NormalizedField:
        value = field.value_verbatim
        seq = field.field_seq
        name = field.field_name

        # R-N0 control gate (before any transformation — corruption is not laundered)
        if any(unicodedata.category(ch) == "Cc" and ch not in _CTRL_ALLOWED
               for ch in value):
            return self._outcome(seq, name, field.provenance,
                                 NormalizationStatus.REJECTED, None, "",
                                 REASON_CONTROL_CHARACTER)

        # R-N1 NFC → R-N2 trim (declared order; internal whitespace untouched)
        v = unicodedata.normalize("NFC", value).strip()

        # R-N3 empty / whitespace-only → DEFERRED (nothing invented)
        if v == "":
            return self._outcome(seq, name, field.provenance,
                                 NormalizationStatus.DEFERRED, None, "",
                                 REASON_EMPTY_VALUE)

        kind = self._kind_profile.get(name, "text")
        if kind == "text":
            return self._outcome(seq, name, field.provenance,
                                 NormalizationStatus.NORMALIZED, v, _TEXT_RULES, None)
        if kind == "decimal":
            out = self._normalize_decimal(v)
            if out is None:
                return self._outcome(seq, name, field.provenance,
                                     NormalizationStatus.DEFERRED, None, "",
                                     REASON_NOT_IN_DECLARED_GRAMMAR)
            return self._outcome(seq, name, field.provenance,
                                 NormalizationStatus.NORMALIZED, out, _NUMBER_RULES, None)
        if kind == "date":
            out = self._normalize_date(v)
            if out is None:
                return self._outcome(seq, name, field.provenance,
                                     NormalizationStatus.DEFERRED, None, "",
                                     REASON_NOT_IN_DECLARED_GRAMMAR)
            return self._outcome(seq, name, field.provenance,
                                 NormalizationStatus.NORMALIZED, out, _DATE_RULES, None)
        # Unknown kind value in the profile — treat as declared-config error → DEFER
        # (fail-closed: never guess a meaning for an unregistered kind)
        return self._outcome(seq, name, field.provenance,
                             NormalizationStatus.DEFERRED, None, "",
                             REASON_NOT_IN_DECLARED_GRAMMAR)

    # -- rule bodies (pure functions) -----------------------------------------

    @staticmethod
    def _normalize_decimal(v: str) -> Optional[str]:
        """R-D1: canonical decimal STRING or None (outside declared grammar).

        Precision-preserving: fraction digits are carried verbatim; no rounding; no
        trailing-zero trimming; no float ever constructed. Sign kept iff value ≠ 0.
        """
        sign = ""
        body = v
        if body[0] in "+-":
            sign = "-" if body[0] == "-" else ""
            body = body[1:]

        if _INT_RE.match(body):                                   # 1. pure integer
            return _signed(sign, _canonical_int_str(body))

        m = _SINGLE_SEP_RE.match(body)                            # 2. single separator
        if m:
            s, int_part, sep, frac = m.group(1), m.group(2), m.group(3), m.group(4)
            # thousands-ambiguous shape (e.g. "1.234", "12,345") → DEFER, never guess
            if len(int_part) <= 3 and len(frac) == 3 and not int_part.startswith("0"):
                return None
            if s == "-":
                sign = "-"
            return _signed(sign, f"{_canonical_int_str(int_part)}.{frac}")

        m = _EURO_RE.match(body)                                  # 3. European grouping
        if m:
            s, grouped, frac = m.group(1), m.group(2), m.group(3)
            if s == "-":
                sign = "-"
            int_part = grouped.replace(".", "")
            out = int_part if frac is None else f"{int_part}.{frac}"
            return _signed(sign, out)

        m = _ENG_RE.match(body)                                   # 4. English grouping
        if m:
            s, grouped, frac = m.group(1), m.group(2), m.group(3)
            if s == "-":
                sign = "-"
            int_part = grouped.replace(",", "")
            out = int_part if frac is None else f"{int_part}.{frac}"
            return _signed(sign, out)

        return None                                               # 5. outside grammar

    @staticmethod
    def _normalize_date(v: str) -> Optional[str]:
        """R-DT1: strict ISO YYYY-MM-DD + calendar validity; value passes unchanged.
        No locale parsing, no conversion, no arithmetic."""
        if not _ISO_DATE_RE.match(v):
            return None
        try:
            date.fromisoformat(v)
        except ValueError:
            return None
        return v

    @staticmethod
    def _outcome(seq: int, name: str, provenance: Provenance,
                 status: NormalizationStatus, value: Optional[str],
                 rules: str, reason: Optional[str]) -> NormalizedField:
        return NormalizedField(
            field_seq=seq,
            source_field_name=name,
            source_provenance=provenance.value,     # D-01 relayed verbatim (EXTRACTED here)
            status=status,
            normalized_value=value,
            rules_applied=rules,
            reason_code=reason,
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _canonical_int_str(digits: str) -> str:
    """Strip leading zeros of a pure-digit string ("007" → "7", "000" → "0")."""
    stripped = digits.lstrip("0")
    return stripped if stripped else "0"


def _signed(sign: str, canonical: str) -> str:
    """Sign kept iff the numeric value is non-zero ('-0' / '-0.000' → unsigned)."""
    if sign != "-":
        return canonical
    if all(ch == "0" for ch in canonical.replace(".", "")):
        return canonical
    return "-" + canonical


# Declared MVP kind profile (SYNTAX only — see SPEC §3; extensible data, not code paths)
_DEFAULT_PROFILE: Mapping[str, str] = {
    "invoice.date": "date",
    "total.gross": "decimal",
    "total.net": "decimal",
    "tax.amount": "decimal",
    "unit_amount": "decimal",
    "quantity": "decimal",
    # text is also the declared fallback for every unlisted field name
}
