"""Versioned, explicit column-role profiles and fail-closed line witnesses (E-24).

The registry is a declarative contract for already-observed ordered cells. It
does not detect a profile from image pixels, reorder columns, run OCR, convert
currency, or repair values. A caller must name a registered profile and supply
cells in that profile's declared left-to-right order.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

REGISTRY_SCHEMA_VERSION = "e24.layout-profile-registry.v1"
DEFAULT_LAYOUT_PROFILE_REGISTRY_PATH = Path(__file__).with_name(
    "layout_profiles_v1.json"
)

ProfileStatus = Literal["EXTRACTED", "REVIEW", "BLOCKED"]
_READABLE_DIRECTIONS = {"left_to_right", "right_to_left"}
_COLUMN_ROLE_KINDS = {
    "description": "text",
    "quantity": "positive_integer",
    "unit_price": "integer_amount",
    "discount_percent": "percentage",
    "discounted_price": "integer_amount",
    "line_total": "integer_amount",
    "consumer_price": "integer_amount",
    "row_number": "positive_integer",
}
_WITNESS_PRICE_ROLES = {"unit_price", "discounted_price"}
_DISCOUNT_POLICIES = {"none", "exact_if_present"}
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


@dataclass(frozen=True)
class ProfileColumn:
    """One role at one explicit left-to-right position in a layout profile."""

    role: str
    required: bool
    value_kind: str
    multiline: bool = False

    def __post_init__(self) -> None:
        if self.role not in _COLUMN_ROLE_KINDS:
            raise ValueError(f"unsupported layout column role: {self.role!r}")
        if self.value_kind != _COLUMN_ROLE_KINDS[self.role]:
            raise ValueError(
                f"{self.role} must use value_kind {_COLUMN_ROLE_KINDS[self.role]!r}"
            )
        if type(self.required) is not bool or type(self.multiline) is not bool:
            raise ValueError("column required and multiline flags must be booleans")
        if self.multiline and self.role != "description":
            raise ValueError("only a description column can be multiline")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "required": self.required,
            "value_kind": self.value_kind,
            "multiline": self.multiline,
        }


@dataclass(frozen=True)
class LayoutProfile:
    """Declared column order and arithmetic semantics for one known layout."""

    profile_id: str
    table_reading_direction: str
    columns_left_to_right: tuple[ProfileColumn, ...]
    line_total_unit_price_role: str | None
    discount_policy: str = "none"

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")
        if self.table_reading_direction not in _READABLE_DIRECTIONS:
            raise ValueError("table_reading_direction must be left_to_right or right_to_left")
        columns = tuple(self.columns_left_to_right)
        if not columns:
            raise ValueError("a layout profile must declare at least one column")
        if len({column.role for column in columns}) != len(columns):
            raise ValueError("a layout profile cannot declare duplicate column roles")
        roles = {column.role for column in columns}
        if not {"description", "quantity", "line_total"}.issubset(roles):
            raise ValueError("a layout profile must declare description, quantity, and line_total")
        if self.line_total_unit_price_role is not None:
            if self.line_total_unit_price_role not in _WITNESS_PRICE_ROLES:
                raise ValueError("line_total_unit_price_role must be unit_price, discounted_price, or None")
            if self.line_total_unit_price_role not in roles:
                raise ValueError("the declared line-total price role must be a profile column")
        if self.discount_policy not in _DISCOUNT_POLICIES:
            raise ValueError("unsupported discount policy")
        if self.discount_policy == "exact_if_present" and not {
            "unit_price", "discount_percent", "discounted_price"
        }.issubset(roles):
            raise ValueError(
                "exact_if_present profiles must declare unit_price, discount_percent, "
                "and discounted_price columns"
            )
        object.__setattr__(self, "columns_left_to_right", columns)

    @property
    def column_roles(self) -> tuple[str, ...]:
        return tuple(column.role for column in self.columns_left_to_right)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "table_reading_direction": self.table_reading_direction,
            "column_order": "left_to_right",
            "columns_left_to_right": [
                column.to_dict() for column in self.columns_left_to_right
            ],
            "line_total_unit_price_role": self.line_total_unit_price_role,
            "discount_policy": self.discount_policy,
        }


@dataclass(frozen=True)
class LayoutProfileRegistry:
    """Immutable set of profiles; selection is exact-ID only, never fuzzy."""

    schema_version: str
    profiles: tuple[LayoutProfile, ...]

    def __post_init__(self) -> None:
        if self.schema_version != REGISTRY_SCHEMA_VERSION:
            raise ValueError("unsupported layout-profile registry version")
        profiles = tuple(self.profiles)
        if not profiles:
            raise ValueError("layout-profile registry must not be empty")
        identifiers = [profile.profile_id for profile in profiles]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("layout-profile IDs must be unique")
        object.__setattr__(self, "profiles", profiles)

    def get(self, profile_id: str) -> LayoutProfile | None:
        if not isinstance(profile_id, str):
            return None
        return next(
            (profile for profile in self.profiles if profile.profile_id == profile_id),
            None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profiles": [profile.to_dict() for profile in self.profiles],
        }


@dataclass(frozen=True)
class ProfileCell:
    """One supplied cell value and its explicit strike-through annotation."""

    value: Any
    crossed_out: bool = False

    def __post_init__(self) -> None:
        if type(self.crossed_out) is not bool:
            raise ValueError("crossed_out must be a boolean")


@dataclass(frozen=True)
class ProfileRowResult:
    """Fail-closed result of applying one explicitly selected profile to a row."""

    profile_id: str | None
    status: ProfileStatus
    reason_code: str
    reason: str
    column_roles: tuple[str, ...] = ()
    fields: Mapping[str, Any] = field(default_factory=dict)
    witnesses: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "column_roles": list(self.column_roles),
            "fields": _json_safe(self.fields),
            "witnesses": _json_safe(self.witnesses),
        }


def _profile_from_dict(value: Mapping[str, Any]) -> LayoutProfile:
    if not isinstance(value, Mapping):
        raise ValueError("each layout profile must be a JSON object")
    expected_keys = {
        "profile_id",
        "table_reading_direction",
        "column_order",
        "columns_left_to_right",
        "line_total_unit_price_role",
        "discount_policy",
    }
    if set(value) != expected_keys:
        raise ValueError("layout profile has unknown or missing fields")
    if value.get("column_order") != "left_to_right":
        raise ValueError("layout profiles must declare column_order=left_to_right")
    raw_columns = value["columns_left_to_right"]
    if not isinstance(raw_columns, list):
        raise ValueError("columns_left_to_right must be a list")
    columns_list: list[ProfileColumn] = []
    for item in raw_columns:
        if not isinstance(item, Mapping):
            raise ValueError("each layout column must be a JSON object")
        allowed_column_keys = {"role", "required", "value_kind", "multiline"}
        required_column_keys = {"role", "required", "value_kind"}
        if not required_column_keys.issubset(item) or set(item) - allowed_column_keys:
            raise ValueError("layout column has unknown or missing fields")
        columns_list.append(
            ProfileColumn(
                role=item["role"],
                required=item["required"],
                value_kind=item["value_kind"],
                multiline=item.get("multiline", False),
            )
        )
    columns = tuple(columns_list)
    return LayoutProfile(
        profile_id=value["profile_id"],
        table_reading_direction=value["table_reading_direction"],
        columns_left_to_right=columns,
        line_total_unit_price_role=value.get("line_total_unit_price_role"),
        discount_policy=value.get("discount_policy", "none"),
    )


def load_layout_profile_registry(
    path: Path | str = DEFAULT_LAYOUT_PROFILE_REGISTRY_PATH,
) -> LayoutProfileRegistry:
    """Load the checked-in registry without selecting a profile heuristically."""
    registry_path = Path(path)
    try:
        document = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load layout-profile registry: {exc}") from exc
    if not isinstance(document, Mapping):
        raise ValueError("layout-profile registry must be a JSON object")
    if set(document) != {"schema_version", "profiles"}:
        raise ValueError("layout-profile registry has unknown or missing top-level fields")
    if not isinstance(document["profiles"], list):
        raise ValueError("layout-profile registry profiles must be a list")
    profiles = tuple(_profile_from_dict(item) for item in document["profiles"])
    return LayoutProfileRegistry(document["schema_version"], profiles)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def _review(
    profile_id: str | None,
    reason_code: str,
    reason: str,
    *,
    column_roles: tuple[str, ...] = (),
    fields: Mapping[str, Any] | None = None,
    witnesses: Mapping[str, Any] | None = None,
) -> ProfileRowResult:
    return ProfileRowResult(
        profile_id=profile_id,
        status="REVIEW",
        reason_code=reason_code,
        reason=reason,
        column_roles=column_roles,
        fields=dict(fields or {}),
        witnesses=dict(witnesses or {}),
    )


def _cell(value: Any) -> ProfileCell:
    if isinstance(value, ProfileCell):
        return value
    if isinstance(value, Mapping) and ("value" in value or "crossed_out" in value):
        extra = set(value) - {"value", "crossed_out"}
        if extra:
            raise ValueError("profile cell object has unknown fields")
        return ProfileCell(value.get("value"), value.get("crossed_out", False))
    return ProfileCell(value)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _translate_number_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).translate(_DIGIT_TRANSLATION)
    return normalized.replace("٬", ",").replace("٫", ".").strip()


def _parse_integer_amount(value: Any, role: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{role} must be an integer amount, not a boolean")
    text = str(value).strip() if isinstance(value, (int, str)) else ""
    text = _translate_number_text(text)
    if not (
        re.fullmatch(r"[0-9]+", text)
        or re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+", text)
    ):
        raise ValueError(
            f"{role} must be a non-negative integer amount without rounding "
            "or malformed grouping"
        )
    try:
        return int(text.replace(",", ""))
    except ValueError as exc:  # pragma: no cover - guarded by the regular expression
        raise ValueError(f"{role} is not a valid integer amount") from exc


def _parse_positive_integer(value: Any, role: str) -> int:
    parsed = _parse_integer_amount(value, role)
    if parsed <= 0:
        raise ValueError(f"{role} must be a positive integer")
    return parsed


def _parse_percent(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("discount_percent must be a number from 0 to 100")
    text = str(value).strip() if isinstance(value, (int, float, Decimal, str)) else ""
    text = _translate_number_text(text)
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text):
        raise ValueError("discount_percent must be a declared decimal from 0 to 100")
    try:
        percent = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("discount_percent is not a valid decimal") from exc
    if not percent.is_finite() or not Decimal(0) <= percent <= Decimal(100):
        raise ValueError("discount_percent must be finite and between 0 and 100")
    return percent


def _description_lines(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_lines = value.splitlines() or [value]
    elif isinstance(value, (list, tuple)):
        raw_lines = list(value)
    else:
        raise ValueError("description must be text or an ordered list of text lines")
    if any(not isinstance(line, str) for line in raw_lines):
        raise ValueError("description lines must all be text")
    lines = tuple(line.strip() for line in raw_lines if line.strip())
    if not lines:
        raise ValueError("description is missing")
    return lines


def evaluate_profile_row(
    profile_id: str,
    ordered_values: Sequence[Any],
    *,
    currency_unit: str | None,
    observed_column_roles: Sequence[str] | None = None,
    registry: LayoutProfileRegistry | None = None,
) -> ProfileRowResult:
    """Apply one declared profile to one row, returning REVIEW on ambiguity.

    ``ordered_values`` must contain one value for each profile column in its
    declared left-to-right order. ``currency_unit`` is an explicit caller
    declaration (``rial`` or ``toman``); this function never guesses or converts
    between the two. Unknown IDs, extra/missing/reordered columns, incomplete
    discount evidence, and a failed quantity-price-total witness are REVIEW.
    """
    active_registry = registry or load_layout_profile_registry()
    profile = active_registry.get(profile_id)
    if profile is None:
        return _review(
            profile_id if isinstance(profile_id, str) else None,
            "UNKNOWN_LAYOUT_PROFILE",
            "No exact registered layout profile was supplied; profile guessing is disabled.",
        )

    roles = profile.column_roles
    if observed_column_roles is not None:
        observed_roles = tuple(observed_column_roles)
        if observed_roles != roles:
            return _review(
                profile.profile_id,
                "COLUMN_ORDER_MISMATCH",
                "Observed column roles/order do not exactly match the selected profile.",
                column_roles=roles,
            )
    if isinstance(ordered_values, (str, bytes, Mapping)):
        return _review(
            profile.profile_id,
            "ORDERED_CELLS_REQUIRED",
            "Cells must be supplied as an ordered sequence, not an unordered mapping or text blob.",
            column_roles=roles,
        )
    try:
        values = tuple(ordered_values)
    except TypeError:
        return _review(
            profile.profile_id,
            "ORDERED_CELLS_REQUIRED",
            "Cells must be supplied as an ordered sequence.",
            column_roles=roles,
        )
    if len(values) != len(profile.columns_left_to_right):
        return _review(
            profile.profile_id,
            "COLUMN_COUNT_MISMATCH",
            f"Profile requires {len(profile.columns_left_to_right)} ordered columns; "
            f"received {len(values)}. Extra or missing columns are not ignored.",
            column_roles=roles,
        )

    if currency_unit is None:
        return _review(
            profile.profile_id,
            "CURRENCY_UNIT_UNCONFIRMED",
            "An explicit rial/toman unit is required before amount witnesses can pass.",
            column_roles=roles,
        )
    if not isinstance(currency_unit, str) or currency_unit not in {"rial", "toman"}:
        return _review(
            profile.profile_id,
            "CURRENCY_UNIT_UNSUPPORTED",
            "Currency unit must be explicitly declared as 'rial' or 'toman'.",
            column_roles=roles,
        )

    try:
        cells = {
            column.role: _cell(value)
            for column, value in zip(profile.columns_left_to_right, values)
        }
    except (TypeError, ValueError) as exc:
        return _review(
            profile.profile_id,
            "CELL_VALUE_INVALID",
            str(exc),
            column_roles=roles,
        )

    missing = [
        column.role for column in profile.columns_left_to_right
        if column.required and _is_empty(cells[column.role].value)
    ]
    if missing:
        return _review(
            profile.profile_id,
            "REQUIRED_COLUMN_MISSING",
            "Required profile columns are blank: " + ", ".join(missing),
            column_roles=roles,
        )

    try:
        description_column = next(
            column for column in profile.columns_left_to_right
            if column.role == "description"
        )
        description_lines = _description_lines(cells["description"].value)
        if len(description_lines) > 1 and not description_column.multiline:
            raise ValueError("profile does not declare multiline descriptions")
        quantity = _parse_positive_integer(cells["quantity"].value, "quantity")
        line_total = _parse_integer_amount(cells["line_total"].value, "line_total")
        if line_total <= 0:
            raise ValueError("line_total must be a positive integer amount")
        row_number: int | None = None
        if "row_number" in cells and not _is_empty(cells["row_number"].value):
            row_number = _parse_positive_integer(cells["row_number"].value, "row_number")

        parsed_amounts: dict[str, int | None] = {}
        for role in ("unit_price", "discounted_price"):
            parsed_amounts[role] = (
                None if role not in cells or _is_empty(cells[role].value)
                else _parse_integer_amount(cells[role].value, role)
            )
            if parsed_amounts[role] is not None and parsed_amounts[role] <= 0:
                raise ValueError(f"{role} must be a positive integer amount")
        discount_percent = (
            None if "discount_percent" not in cells
            or _is_empty(cells["discount_percent"].value)
            else _parse_percent(cells["discount_percent"].value)
        )
    except (StopIteration, ValueError) as exc:
        return _review(
            profile.profile_id,
            "CELL_VALUE_INVALID",
            str(exc),
            column_roles=roles,
        )

    witnesses: dict[str, Any] = {}
    if profile.discount_policy == "exact_if_present":
        unit_price = parsed_amounts.get("unit_price")
        discounted_price = parsed_amounts.get("discounted_price")
        has_unit_price = unit_price is not None
        has_discount_percent = discount_percent is not None
        if has_unit_price != has_discount_percent:
            return _review(
                profile.profile_id,
                "DISCOUNT_EVIDENCE_INCOMPLETE",
                "A pre-discount unit_price and discount_percent must either both be present "
                "or both be absent.",
                column_roles=roles,
            )
        if has_unit_price and has_discount_percent:
            assert unit_price is not None and discounted_price is not None
            if cells["unit_price"].crossed_out:
                return _review(
                    profile.profile_id,
                    "DISCOUNT_INPUT_CROSSED_OUT",
                    "A crossed-out pre-discount unit_price cannot witness discount arithmetic.",
                    column_roles=roles,
                )
            expected_discounted = Decimal(unit_price) * (
                Decimal(100) - discount_percent
            ) / Decimal(100)
            discount_passed = expected_discounted == Decimal(discounted_price)
            witnesses["discount_percent"] = {
                "passed": discount_passed,
                "unit_price": unit_price,
                "discount_percent": discount_percent,
                "expected_discounted_price": expected_discounted,
                "observed_discounted_price": discounted_price,
                "rounding_allowed": False,
            }
            if not discount_passed:
                return _review(
                    profile.profile_id,
                    "DISCOUNT_WITNESS_FAILED",
                    "discounted_price does not exactly match unit_price and discount_percent; "
                    "no rounding or repair is permitted.",
                    column_roles=roles,
                    fields={"discount_percent": discount_percent},
                    witnesses=witnesses,
                )

    price_role = profile.line_total_unit_price_role
    if price_role is None:
        return _review(
            profile.profile_id,
            "UNIT_PRICE_ROLE_UNDECLARED",
            "This profile has no explicit per-unit price role; line_total is not divided by quantity.",
            column_roles=roles,
            witnesses=witnesses,
        )
    if price_role not in cells or _is_empty(cells[price_role].value):
        return _review(
            profile.profile_id,
            "UNIT_PRICE_MISSING",
            f"The profile's declared witness price role {price_role!r} is missing.",
            column_roles=roles,
            witnesses=witnesses,
        )
    if cells[price_role].crossed_out:
        return _review(
            profile.profile_id,
            "WITNESS_PRICE_CROSSED_OUT",
            "A crossed-out value cannot witness the line total.",
            column_roles=roles,
            witnesses=witnesses,
        )
    unit_price_for_witness = parsed_amounts.get(price_role)
    if unit_price_for_witness is None:
        return _review(
            profile.profile_id,
            "UNIT_PRICE_MISSING",
            f"The profile's declared witness price role {price_role!r} is unavailable.",
            column_roles=roles,
            witnesses=witnesses,
        )

    expected_line_total = quantity * unit_price_for_witness
    total_passed = expected_line_total == line_total
    witnesses["quantity_x_unit_price_equals_line_total"] = {
        "passed": total_passed,
        "quantity": quantity,
        "unit_price_role": price_role,
        "unit_price": unit_price_for_witness,
        "expected_line_total": expected_line_total,
        "observed_line_total": line_total,
        "currency_unit": currency_unit,
    }
    if not total_passed:
        return _review(
            profile.profile_id,
            "LINE_TOTAL_WITNESS_FAILED",
            "quantity multiplied by the profile-declared per-unit price does not equal line_total.",
            column_roles=roles,
            witnesses=witnesses,
        )

    fields: dict[str, Any] = {
        "description_lines": list(description_lines),
        "description": "\n".join(description_lines),
        "quantity": quantity,
        "unit_price": parsed_amounts.get("unit_price"),
        "discount_percent": discount_percent,
        "discounted_price": parsed_amounts.get("discounted_price"),
        "line_total": line_total,
        "line_total_unit_price_role": price_role,
        "currency_unit": currency_unit,
    }
    if row_number is not None:
        fields["row_number"] = row_number
    if "consumer_price" in cells:
        raw_consumer = cells["consumer_price"].value
        fields["consumer_price"] = (
            None if _is_empty(raw_consumer) else str(raw_consumer)
        )
        fields["consumer_price_crossed_out"] = cells["consumer_price"].crossed_out
    return ProfileRowResult(
        profile_id=profile.profile_id,
        status="EXTRACTED",
        reason_code="PROFILE_AND_WITNESSES_PASSED",
        reason="Exact profile roles and declared arithmetic witnesses passed; no value was inferred.",
        column_roles=roles,
        fields=fields,
        witnesses=witnesses,
    )


def serialize_profile_output(value: Mapping[str, Any]) -> str:
    """Canonical UTF-8/LF JSON representation for profile evaluation output."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
