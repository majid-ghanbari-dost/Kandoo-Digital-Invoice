"""Text-label/table parser for the declared synthetic invoice layout.

This parser is intentionally text-based: it uses OCR-recognized labels and
pipe-delimited table columns, never image coordinates. It is not claimed to be
a Holoo layout parser; unknown or ambiguous text is refused for review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


class InvoiceTextParseError(ValueError):
    """OCR text is incomplete or ambiguous for the configured invoice grammar."""


@dataclass(frozen=True)
class ParsedImageInvoice:
    fields: tuple[tuple[str, str], ...]
    key_value_page: bytes
    line_count: int


_INVOICE_NUMBER = re.compile(
    r"\bINVOICE\s*(?:NO\.?|NUMBER)\s*[:#]\s*([A-Z0-9][A-Z0-9-]*)\b",
    re.IGNORECASE,
)
_DATE = re.compile(r"\bDATE\s*:\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
_MONEY = r"(?:\$\s*)?([0-9]+(?:,[0-9]{3})*\.[0-9]{2})"
_NET = re.compile(rf"\bNET\s+TOTAL\s*:\s*{_MONEY}", re.IGNORECASE)
_TAX = re.compile(rf"\bTAX\s*:\s*{_MONEY}", re.IGNORECASE)
_PAYABLE = re.compile(rf"\bAMOUNT\s+DUE\s*:\s*{_MONEY}", re.IGNORECASE)
_QUANTITY = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")


def _one_value(pattern: re.Pattern[str], text: str, label: str) -> str:
    matches = [match.group(1).strip() for match in pattern.finditer(text)]
    if len(matches) != 1:
        raise InvoiceTextParseError(
            f"expected exactly one {label}, OCR yielded {len(matches)}")
    return matches[0]


def _money(value: str, label: str) -> str:
    normalized = value.replace(",", "").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]{2}", normalized):
        raise InvoiceTextParseError(f"{label} is not a declared decimal amount")
    return normalized


def _table_header_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        upper = line.upper()
        if all(label in upper for label in
               ("ITEM", "QUANTITY", "UNIT PRICE", "LINE TOTAL")):
            return index
    raise InvoiceTextParseError(
        "OCR did not find the declared ITEM / QUANTITY / UNIT PRICE / LINE TOTAL header")


def _item_rows(lines: list[str], header_index: int) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for line in lines[header_index + 1:]:
        if re.match(r"\s*(?:NET\s+TOTAL|TAX|AMOUNT\s+DUE)\s*:", line, re.IGNORECASE):
            break
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 4:
            raise InvoiceTextParseError(
                "a pipe-delimited line after the table header has an unexpected column count")
        description, quantity, unit_price, line_total = parts
        if not description or not _QUANTITY.fullmatch(quantity):
            raise InvoiceTextParseError("an OCR item row has a missing/ambiguous description or quantity")
        rows.append((
            description,
            quantity,
            _money(unit_price, "unit price"),
            _money(line_total, "line total"),
        ))
    if not rows:
        raise InvoiceTextParseError("no item rows were recognized after the table header")
    return rows


def parse_invoice_text(text: str) -> ParsedImageInvoice:
    """Parse labelled OCR text into deterministic key=value page bytes.

    This schema is a declared MVP example for the synthetic fixture. It does not
    infer values, calculate taxes, convert currencies, or guess missing columns.
    """
    if not isinstance(text, str) or not text.strip():
        raise InvoiceTextParseError("OCR returned no text")

    invoice_number = _one_value(_INVOICE_NUMBER, text, "invoice number")
    invoice_date = _one_value(_DATE, text, "invoice date")
    try:
        date.fromisoformat(invoice_date)
    except ValueError as exc:
        raise InvoiceTextParseError("invoice date is not a valid ISO calendar date") from exc
    net_total = _money(_one_value(_NET, text, "net total"), "net total")
    tax_amount = _money(_one_value(_TAX, text, "tax amount"), "tax amount")
    payable = _money(_one_value(_PAYABLE, text, "amount due"), "amount due")
    lines = text.splitlines()
    rows = _item_rows(lines, _table_header_index(lines))

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
