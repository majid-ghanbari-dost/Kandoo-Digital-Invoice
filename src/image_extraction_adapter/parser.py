"""English/Persian OCR parsers for labeled text and spatial invoice tables.

`parse_invoice_text` consumes OCR labels and delimited/labeled item blocks
without image coordinates. `parse_invoice_geometry` consumes word boxes for a
fail-closed spatial fallback. Neither function guesses missing values or
recalculates invoice amounts.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from .model import FieldAssessment, OCRResult, OCRWord


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


@dataclass(frozen=True)
class SpatialParseResult:
    """Partial box-based parse; every uncertain or missing value is REVIEW."""

    assessments: tuple["FieldAssessment", ...]
    column_boundaries: tuple[float, ...]
    row_bands: tuple[tuple[float, float], ...]
    reasons: tuple[str, ...]

    @property
    def field_values(self) -> tuple[tuple[str, str], ...]:
        return tuple((item.field_name, item.raw_value) for item in self.assessments)

    @property
    def review_count(self) -> int:
        return sum(item.status == "REVIEW" for item in self.assessments)


def _bbox(words: Sequence["OCRWord"]) -> tuple[int, int, int, int] | None:
    if not words:
        return None
    left = min(word.left for word in words)
    top = min(word.top for word in words)
    right = max(word.right for word in words)
    bottom = max(word.bottom for word in words)
    return left, top, right - left, bottom - top


def _box_text(words: Sequence["OCRWord"]) -> str:
    return " ".join(
        word.text.strip()
        for word in sorted(words, key=lambda word: (-word.center_x, word.top))
        if word.text.strip()
    )


def _box_confidence(words: Sequence["OCRWord"]) -> float | None:
    scores = [word.confidence for word in words if word.text.strip()]
    return min(scores) if scores else None


def _assessment(
    field_name: str,
    words: Sequence["OCRWord"],
    *,
    minimum_confidence: float,
    reason: str | None = None,
    numeric_pattern: re.Pattern[str] | None = None,
) -> "FieldAssessment":
    raw_value = _box_text(words)
    confidence = _box_confidence(words)
    reasons = [reason] if reason else []
    if not raw_value:
        reasons.append("no OCR word recognized in the field region")
    if confidence is None:
        reasons.append("field has no word confidence score")
    elif confidence < minimum_confidence:
        reasons.append(
            f"minimum field confidence {confidence:.2f} is below "
            f"{minimum_confidence:.2f}")
    if numeric_pattern is not None and raw_value:
        normalized = _normalize_text(raw_value).strip()
        if not numeric_pattern.fullmatch(normalized):
            reasons.append("raw OCR value does not match the declared numeric format")
    return FieldAssessment(
        field_name=field_name,
        raw_value=raw_value,
        status="REVIEW" if reasons else "EXTRACTED",
        confidence=confidence,
        bbox=_bbox(words),
        reason="; ".join(dict.fromkeys(reasons)) or None,
    )


def _cluster_rule_boxes(
    words: Sequence["OCRWord"], *, image_height: int
) -> tuple[list["OCRWord"], list["OCRWord"]]:
    minimum_height = max(80, int(image_height * 0.12))
    candidates = [
        word for word in words
        if not word.text.strip() and 0 < word.width <= 18 and word.height >= minimum_height
    ]
    interior = [
        word for word in candidates
        if word.top >= image_height * 0.08 and word.height < image_height * 0.90
    ]
    outer = [
        word for word in candidates
        if word.height >= image_height * 0.90
    ]
    return interior, outer


def _column_geometry(
    words: Sequence["OCRWord"], *, image_width: int, image_height: int
) -> tuple[tuple[float, ...], tuple[float, float], str | None]:
    interior, outer = _cluster_rule_boxes(words, image_height=image_height)
    # The target receipt table has three internal vertical rules, defining the
    # amount, quantity, item-name, and row-number columns. Group duplicates
    # within a 12px band because TSV boxes can cover neighboring rule pixels.
    centers: list[float] = []
    for word in sorted(interior, key=lambda item: item.center_x):
        if not centers or abs(word.center_x - centers[-1]) > 12:
            centers.append(word.center_x)
        else:
            centers[-1] = (centers[-1] + word.center_x) / 2
    if len(centers) != 3:
        return (), (0.0, 0.0), (
            f"expected 3 internal table rules, found {len(centers)} long TSV boxes")

    left_candidates = [
        word.center_x for word in outer
        if 0 < word.center_x < centers[0]
    ]
    right_candidates = [
        word.center_x for word in outer
        if centers[-1] < word.center_x < image_width
    ]
    if not left_candidates or not right_candidates:
        return tuple(centers), (0.0, 0.0), "table outer rules were not detected"

    bounds = (
        max(left_candidates),
        *centers,
        min(right_candidates),
    )
    table_top = max(word.top for word in interior)
    table_bottom = min(word.bottom for word in interior)
    if table_bottom <= table_top:
        return tuple(bounds), (0.0, 0.0), "internal table rules have no shared Y span"
    return tuple(bounds), (float(table_top), float(table_bottom)), None


def _column_words(
    words: Sequence["OCRWord"],
    *,
    x_left: float,
    x_right: float,
    y_top: float,
    y_bottom: float,
    edge_margin: float = 8,
) -> list["OCRWord"]:
    return [
        word for word in words
        if word.text.strip()
        and x_left + edge_margin <= word.center_x <= x_right - edge_margin
        and y_top <= word.center_y <= y_bottom
    ]


def _row_anchors(
    words: Sequence["OCRWord"],
    *,
    bounds: Sequence[float],
    table_span: tuple[float, float],
) -> tuple[list[tuple[int, "OCRWord"]], list[str]]:
    table_top, table_bottom = table_span
    candidates: list[tuple[int, "OCRWord"]] = []
    for word in words:
        if not (
            bounds[-2] + 8 <= word.center_x <= bounds[-1] - 8
            and table_top <= word.center_y <= table_bottom
        ):
            continue
        raw = _normalize_text(word.text).strip()
        if re.fullmatch(r"[0-9]{1,2}", raw):
            candidates.append((int(raw), word))

    candidates.sort(key=lambda item: item[1].center_y)
    first_index = next(
        (index for index, (value, _) in enumerate(candidates) if value == 1), None)
    if first_index is None:
        return [], ["no row-number token '1' was found in the rightmost table column"]

    anchors = [candidates[first_index]]
    issues: list[str] = []
    expected = 2
    previous_y = anchors[0][1].center_y
    for value, word in candidates[first_index + 1:]:
        if word.center_y <= previous_y:
            continue
        if value == expected:
            anchors.append((value, word))
            previous_y = word.center_y
            expected += 1
        elif value > expected:
            issues.append(f"row sequence {expected} is missing before {value}")
            break
    if len(anchors) < 2:
        issues.append("only one increasing row-number anchor was recognized")
    return anchors, issues


def _bands_from_anchors(
    anchors: Sequence[tuple[int, "OCRWord"]], table_span: tuple[float, float]
) -> tuple[tuple[float, float], ...]:
    centers = [word.center_y for _, word in anchors]
    top_limit, bottom_limit = table_span
    bands: list[tuple[float, float]] = []
    for index, center in enumerate(centers):
        if index == 0:
            upper = center - (centers[index + 1] - center) / 2
        else:
            upper = (centers[index - 1] + center) / 2
        if index == len(centers) - 1:
            lower = center + (center - centers[index - 1]) / 2
        else:
            lower = (center + centers[index + 1]) / 2
        bands.append((max(top_limit, upper), min(bottom_limit, lower)))
    return tuple(bands)


def _labeled_value_words(
    words: Sequence["OCRWord"], labels: set[str], *, y_tolerance: float = 32
) -> tuple[list["OCRWord"], list["OCRWord"]]:
    label_words = [
        word for word in words
        if _normalize_text(word.text).strip().strip(":：,.;") in labels
    ]
    if not label_words:
        return [], []
    label_y = sum(word.center_y for word in label_words) / len(label_words)
    same_line_labels = [
        word for word in label_words if abs(word.center_y - label_y) <= y_tolerance
    ]
    line_words = [
        word for word in words if abs(word.center_y - label_y) <= y_tolerance
    ]
    label_left = min(word.left for word in same_line_labels)
    value_words = [
        word for word in line_words
        if word.center_x < label_left - 5
        and re.search(r"[0-9]", _normalize_text(word.text))
    ]
    return same_line_labels, value_words


def parse_invoice_geometry(
    ocr: "OCRResult", *, minimum_confidence: float
) -> SpatialParseResult:
    """Extract spatially aligned receipt cells and preserve uncertain OCR raw.

    Long whitespace TSV boxes identify the receipt's vertical table rules.
    Numbered cells in the rightmost column anchor item rows; the remaining
    cells are assigned right-to-left as item name, quantity, and amount. This
    routine is deliberately partial and never repairs or calculates a value.
    """
    words = ocr.words
    assessments: list[FieldAssessment] = []
    reasons: list[str] = []
    bounds: tuple[float, ...] = ()
    row_bands: tuple[tuple[float, float], ...] = ()
    table_span = (0.0, 0.0)

    if not words or ocr.image_width <= 0 or ocr.image_height <= 0:
        reason = "OCR backend returned no usable spatial word data"
        return SpatialParseResult((), (), (), (reason,))

    bounds, table_span, geometry_error = _column_geometry(
        words, image_width=ocr.image_width, image_height=ocr.image_height)
    if geometry_error:
        reasons.append(geometry_error)

    # The labeled header makes the receipt number spatially identifiable even
    # when the date has no label and is in a local calendar format.
    invoice_label = [
        word for word in words
        if _normalize_text(word.text).strip().strip(":：") in {"شماره", "فاکتور", "صورتحساب"}
    ]
    invoice_number_words: list["OCRWord"] = []
    if invoice_label:
        label_y = sum(word.center_y for word in invoice_label) / len(invoice_label)
        same_line = [
            word for word in invoice_label if abs(word.center_y - label_y) <= 28
        ]
        left_edge = min(word.left for word in same_line)
        candidates = [
            word for word in words
            if abs(word.center_y - label_y) <= 28
            and word.center_x < left_edge - 5
            and re.fullmatch(r"[0-9]+", _normalize_text(word.text).strip())
        ]
        if candidates:
            invoice_number_words = [max(candidates, key=lambda word: word.center_x)]
    assessments.append(_assessment(
        "invoice.number", invoice_number_words,
        minimum_confidence=minimum_confidence,
        numeric_pattern=re.compile(r"[0-9]+"),
        reason=None if invoice_number_words else "invoice number is not adjacent to its label",
    ))

    date_words = [
        word for word in words
        if word.center_y < ocr.image_height * 0.4
        and re.fullmatch(
            r"[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,2}",
            _normalize_text(word.text).strip(),
        )
    ]
    assessments.append(_assessment(
        "invoice.date", date_words,
        minimum_confidence=minimum_confidence,
        reason="unlabeled dot-separated date; calendar conversion is not declared",
    ))

    payable_labels, payable_words = _labeled_value_words(
        words, {"مبلغ", "قابل", "پرداخت"})
    assessments.append(_assessment(
        "invoice.payable", payable_words,
        minimum_confidence=minimum_confidence,
        reason=None if payable_labels else "payable label was not recognized",
        numeric_pattern=re.compile(r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?"),
    ))

    tax_labels, tax_words = _labeled_value_words(
        words, {"مالیات", "بر", "ارزش", "افزوده"})
    assessments.append(_assessment(
        "tax.amount", tax_words,
        minimum_confidence=minimum_confidence,
        numeric_pattern=re.compile(r"[0-9]+(?:\.[0-9]{2})?"),
        reason=None if tax_labels else "tax label was not recognized",
    ))

    net_labels, net_words = _labeled_value_words(words, {"جمع", "کل"})
    assessments.append(_assessment(
        "total.net", net_words,
        minimum_confidence=minimum_confidence,
        numeric_pattern=re.compile(r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?"),
        reason=None if net_labels and net_words else
        "no overall net amount was recognized beside a net-total label",
    ))

    # The charges label is not part of the frozen canonical contract; it is
    # retained for operator review only.
    charges_labels, charges_words = _labeled_value_words(words, {"عوارض"})
    assessments.append(_assessment(
        "charges.amount", charges_words,
        minimum_confidence=minimum_confidence,
        numeric_pattern=re.compile(r"[0-9]+(?:\.[0-9]{2})?"),
        reason=None if charges_labels else "charges label was not recognized",
    ))

    if bounds and table_span[1] > table_span[0]:
        anchors, anchor_issues = _row_anchors(
            words, bounds=bounds, table_span=table_span)
        reasons.extend(anchor_issues)
        row_bands = _bands_from_anchors(anchors, table_span) if len(anchors) >= 2 else ()
        for (row_number, anchor), band in zip(anchors, row_bands):
            sequence_assessment = _assessment(
                f"line.{row_number - 1}.sequence", [anchor],
                minimum_confidence=minimum_confidence,
                numeric_pattern=re.compile(r"[0-9]{1,2}"),
            )
            assessments.append(sequence_assessment)
            row_index = row_number - 1
            desc_words = _column_words(
                words, x_left=bounds[2], x_right=bounds[3],
                y_top=band[0], y_bottom=band[1])
            qty_words = _column_words(
                words, x_left=bounds[1], x_right=bounds[2],
                y_top=band[0], y_bottom=band[1])
            amount_words = _column_words(
                words, x_left=bounds[0], x_right=bounds[1],
                y_top=band[0], y_bottom=band[1])

            assessments.append(_assessment(
                f"line.{row_index}.description", desc_words,
                minimum_confidence=minimum_confidence,
            ))
            assessments.append(_assessment(
                f"line.{row_index}.quantity", qty_words,
                minimum_confidence=minimum_confidence,
                numeric_pattern=re.compile(r"[0-9]+(?:\.[0-9]+)?"),
            ))
            assessments.append(_assessment(
                f"line.{row_index}.total", amount_words,
                minimum_confidence=minimum_confidence,
                numeric_pattern=re.compile(r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?"),
            ))
            assessments.append(_assessment(
                f"line.{row_index}.unit_price", [],
                minimum_confidence=minimum_confidence,
                reason="no unit-price column was recognized in the receipt table",
            ))
    elif not bounds:
        reasons.append("no table columns could be assigned from TSV geometry")

    field_reviews = [item.field_name for item in assessments if item.status == "REVIEW"]
    if field_reviews:
        reasons.append("fields require review: " + ", ".join(field_reviews))
    return SpatialParseResult(
        assessments=tuple(assessments),
        column_boundaries=bounds,
        row_bands=row_bands,
        reasons=tuple(reasons),
    )
