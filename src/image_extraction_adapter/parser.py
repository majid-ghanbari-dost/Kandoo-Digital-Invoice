"""Coordinate-free English/Persian OCR text parser for declared invoice labels.

The parser consumes OCR text labels and either a recognized delimited header or
labeled item blocks. It never uses image coordinates, silently guesses missing
values, or recalculates invoice amounts.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Sequence


class InvoiceTextParseError(ValueError):
    """OCR text is incomplete or ambiguous for the configured invoice grammar."""


@dataclass(frozen=True)
class ParsedImageInvoice:
    fields: tuple[tuple[str, str], ...]
    key_value_page: bytes
    line_count: int


_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_BIDI_CONTROLS = "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
_MONEY_VALUE = r"([0-9]+(?:,[0-9]{3})*\.[0-9]{2})"
_QUANTITY_VALUE = r"([0-9]+(?:\.[0-9]+)?)"

_INVOICE_NUMBER_PATTERNS = (
    re.compile(
        r"\bINVOICE[ \t]*(?:NO\.?|NUMBER)[ \t]*[:#][ \t]*([A-Z0-9][A-Z0-9-]*)\b",
        re.IGNORECASE,
    ),
    re.compile(r"شماره[ \t]*(?:فاکتور|صورتحساب)[ \t]*[:#：][ \t]*([A-Z0-9][A-Z0-9-]*)", re.IGNORECASE),
)
_DATE_PATTERNS = (
    re.compile(r"\bDATE[ \t]*[:：][ \t]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b", re.IGNORECASE),
    re.compile(r"تاریخ[ \t]*[:：][ \t]*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})"),
)
_NET_PATTERNS = (
    re.compile(rf"(?:\bNET[ \t]+TOTAL\b|جمع[ \t]*کل|مبلغ[ \t]*کل)[ \t]*[:：]?[ \t]*{_MONEY_VALUE}", re.IGNORECASE),
    re.compile(rf"{_MONEY_VALUE}[ \t]*[:：]?[ \t]*(?:\bNET[ \t]+TOTAL\b|جمع[ \t]*کل|مبلغ[ \t]*کل)", re.IGNORECASE),
)
_TAX_PATTERNS = (
    re.compile(rf"(?:\bTAX\b|مالیات(?:[ \t]+بر[ \t]+ارزش[ \t]+افزوده)?)[ \t]*[:：]?[ \t]*{_MONEY_VALUE}", re.IGNORECASE),
    re.compile(rf"{_MONEY_VALUE}[ \t]*[:：]?[ \t]*(?:\bTAX\b|مالیات(?:[ \t]+بر[ \t]+ارزش[ \t]+افزوده)?)", re.IGNORECASE),
)
_PAYABLE_PATTERNS = (
    re.compile(rf"(?:\bAMOUNT[ \t]+DUE\b|مبلغ[ \t]+قابل[ \t]+پرداخت|قابل[ \t]+پرداخت)[ \t]*[:：]?[ \t]*{_MONEY_VALUE}", re.IGNORECASE),
    re.compile(rf"{_MONEY_VALUE}[ \t]*[:：]?[ \t]*(?:\bAMOUNT[ \t]+DUE\b|مبلغ[ \t]+قابل[ \t]+پرداخت|قابل[ \t]+پرداخت)", re.IGNORECASE),
)

_DESCRIPTION_PATTERNS = (
    re.compile(r"^(?:ITEM|شرح\s*کالا|کالا)\s*[:：]\s*(.+)$", re.IGNORECASE),
    re.compile(r"^(.+?)\s+(?:ITEM)\s*[:：]?$", re.IGNORECASE),
)
_QUANTITY_PATTERNS = (
    re.compile(rf"(?:\bQUANTITY\b|تعداد)\s*[:：]?\s*{_QUANTITY_VALUE}", re.IGNORECASE),
    re.compile(rf"{_QUANTITY_VALUE}\s*[:：]?\s*(?:\bQUANTITY\b|تعداد)", re.IGNORECASE),
)
_UNIT_PRICE_PATTERNS = (
    re.compile(rf"(?:\bUNIT\s+PRICE\b|قیمت\s+واحد)\s*[:：]?\s*{_MONEY_VALUE}", re.IGNORECASE),
    re.compile(rf"{_MONEY_VALUE}\s*[:：]?\s*(?:\bUNIT\s+PRICE\b|قیمت\s+واحد)", re.IGNORECASE),
)
_LINE_TOTAL_PATTERNS = (
    re.compile(rf"(?:\bLINE\s+TOTAL\b|جمع\s+ردیف)\s*[:：]?\s*{_MONEY_VALUE}", re.IGNORECASE),
    re.compile(rf"{_MONEY_VALUE}\s*[:：]?\s*(?:\bLINE\s+TOTAL\b|جمع\s+ردیف)", re.IGNORECASE),
)
_SUMMARY_MARKER = re.compile(
    r"(?:\bNET\s+TOTAL\b|جمع\s*کل|مبلغ\s*کل|\bTAX\b|مالیات|\bAMOUNT\s+DUE\b|قابل\s+پرداخت)",
    re.IGNORECASE,
)


def _normalize_text(text: str) -> str:
    """Normalize bidirectional controls, Arabic/Persian forms and digits."""
    value = unicodedata.normalize("NFKC", text)
    value = value.translate(_DIGIT_TRANSLATION)
    value = value.replace("٫", ".").replace("٬", ",")
    value = value.replace("ي", "ی").replace("ك", "ک")
    value = value.translate({ord(char): None for char in _BIDI_CONTROLS})
    return value


def _single_match(patterns: Sequence[re.Pattern[str]], text: str, label: str) -> str:
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(match.group(1).strip() for match in pattern.finditer(text))
    if len(matches) != 1:
        raise InvoiceTextParseError(
            f"expected exactly one {label}, OCR yielded {len(matches)}")
    return matches[0]


def _money(value: str, label: str) -> str:
    normalized = _normalize_text(value).replace(",", "")
    if not re.fullmatch(r"[0-9]+\.[0-9]{2}", normalized):
        raise InvoiceTextParseError(f"{label} is not a declared decimal amount")
    return normalized


def _quantity(value: str) -> str:
    normalized = _normalize_text(value)
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", normalized):
        raise InvoiceTextParseError("quantity is not a declared numeric value")
    return normalized


def _iso_date(value: str) -> str:
    normalized = _normalize_text(value).replace("/", "-")
    try:
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", normalized):
            year, month, day = (int(part) for part in normalized.split("-"))
        else:
            day, month, year = (int(part) for part in normalized.split("-"))
        return date(year, month, day).isoformat()
    except (ValueError, TypeError) as exc:
        raise InvoiceTextParseError("invoice date is not a valid Gregorian calendar date") from exc


def _match_value(patterns: Sequence[re.Pattern[str]], line: str) -> str | None:
    matches = [match.group(1).strip() for pattern in patterns for match in pattern.finditer(line)]
    if len(matches) > 1:
        raise InvoiceTextParseError("an item field is ambiguous in OCR text")
    return matches[0] if matches else None


def _description(line: str) -> str | None:
    normalized = re.sub(r"\s+", " ", _normalize_text(line)).strip()
    for pattern in _DESCRIPTION_PATTERNS:
        match = pattern.fullmatch(normalized)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" \t:：")
            if value:
                return value
    return None


def _labeled_item_rows(lines: list[str]) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    current: dict[str, str] | None = None

    def finish_current() -> None:
        nonlocal current
        if current is None:
            return
        required = ("description", "quantity", "unit_price", "line_total")
        missing = [field for field in required if not current.get(field)]
        if missing:
            raise InvoiceTextParseError(
                "an item block is missing labeled fields: " + ", ".join(missing))
        rows.append((
            current["description"],
            _quantity(current["quantity"]),
            _money(current["unit_price"], "unit price"),
            _money(current["line_total"], "line total"),
        ))
        current = None

    in_items = False
    for source_line in lines:
        line = re.sub(r"\s+", " ", _normalize_text(source_line)).strip()
        if not line:
            continue
        if _DATE_PATTERNS[0].search(line) or _DATE_PATTERNS[1].search(line):
            in_items = True
            continue
        if not in_items:
            continue
        if _SUMMARY_MARKER.search(line):
            finish_current()
            break

        description = _description(line)
        if description is not None:
            finish_current()
            current = {"description": description}
            continue
        if current is None:
            continue

        for key, patterns in (
            ("quantity", _QUANTITY_PATTERNS),
            ("unit_price", _UNIT_PRICE_PATTERNS),
            ("line_total", _LINE_TOTAL_PATTERNS),
        ):
            value = _match_value(patterns, line)
            if value is not None:
                if current.get(key):
                    raise InvoiceTextParseError(f"item block has duplicate {key} values")
                current[key] = value
                break

    finish_current()
    if not rows:
        raise InvoiceTextParseError("no labeled item blocks were recognized")
    return rows


def _header_roles(line: str) -> tuple[str, ...] | None:
    parts = [part.strip() for part in line.split("|")]
    if len(parts) != 4:
        return None
    roles: list[str] = []
    for raw in parts:
        part = _normalize_text(raw).casefold()
        if "item" in part or "شرح" in part or "کالا" in part:
            role = "description"
        elif "quantity" in part or "تعداد" in part:
            role = "quantity"
        elif "unit price" in part or ("قیمت" in part and "واحد" in part):
            role = "unit_price"
        elif "line total" in part or ("جمع" in part and "ردیف" in part):
            role = "line_total"
        else:
            return None
        roles.append(role)
    if len(set(roles)) != 4:
        return None
    return tuple(roles)


def _pipe_table_rows(lines: list[str]) -> list[tuple[str, str, str, str]] | None:
    header_index = next(
        (index for index, line in enumerate(lines) if _header_roles(line) is not None),
        None,
    )
    if header_index is None:
        return None
    roles = _header_roles(lines[header_index])
    assert roles is not None
    rows: list[tuple[str, str, str, str]] = []
    for source_line in lines[header_index + 1:]:
        line = re.sub(r"\s+", " ", _normalize_text(source_line)).strip()
        if not line:
            continue
        if _SUMMARY_MARKER.search(line):
            break
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != len(roles):
            raise InvoiceTextParseError(
                "a pipe-delimited row has a different column count from its header")
        values = dict(zip(roles, parts))
        description = values["description"].strip()
        if not description:
            raise InvoiceTextParseError("an OCR item row has a missing description")
        rows.append((
            description,
            _quantity(values["quantity"]),
            _money(values["unit_price"], "unit price"),
            _money(values["line_total"], "line total"),
        ))
    if not rows:
        raise InvoiceTextParseError("no item rows were recognized after the table header")
    return rows


def parse_invoice_text(text: str) -> ParsedImageInvoice:
    """Parse English or Persian labeled OCR text into deterministic UTF-8 fields."""
    if not isinstance(text, str) or not text.strip():
        raise InvoiceTextParseError("OCR returned no text")
    normalized = _normalize_text(text)

    invoice_number = _single_match(_INVOICE_NUMBER_PATTERNS, normalized, "invoice number")
    raw_date = _single_match(_DATE_PATTERNS, normalized, "invoice date")
    invoice_date = _iso_date(raw_date)
    net_total = _money(_single_match(_NET_PATTERNS, normalized, "net total"), "net total")
    tax_amount = _money(_single_match(_TAX_PATTERNS, normalized, "tax amount"), "tax amount")
    payable = _money(_single_match(_PAYABLE_PATTERNS, normalized, "amount due"), "amount due")

    lines = normalized.splitlines()
    rows = _pipe_table_rows(lines)
    if rows is None:
        rows = _labeled_item_rows(lines)

    fields: list[tuple[str, str]] = [
        ("invoice.number", invoice_number),
        ("invoice.date", invoice_date),
        ("total.net", net_total),
        ("tax.amount", tax_amount),
        ("invoice.payable", payable),
    ]
    for index, (description, quantity, unit_price, line_total) in enumerate(rows):
        fields.extend((
            (f"line.{index}.description", description),
            (f"line.{index}.quantity", quantity),
            (f"line.{index}.unit_price", unit_price),
            (f"line.{index}.total", line_total),
        ))

    page_text = "".join(f"{name}={value}\n" for name, value in fields)
    return ParsedImageInvoice(tuple(fields), page_text.encode("utf-8"), len(rows))
