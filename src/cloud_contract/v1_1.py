"""Pure v1.1 invoice-contract validation and projection preflight.

The checkout does not contain the Cloud HTTP or database implementation. This
module provides a small Python reference boundary for the delivered v1.1
schemas/addendum: it identifies invoices only by the explicit marker, validates
the recorded extension fields without mutating input, and returns a complete
batch preflight plan before a caller may project anything.

It deliberately does not implement entry/batch hashing, an HTTP server, or a
storage transaction. A Cloud adapter must keep using the frozen hash profile
and apply a returned plan only inside its all-or-nothing ingest transaction.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Literal


INVOICE_SCHEMA_VERSION_FIELD = "invoice_schema_version"
LEGACY_INVOICE_SCHEMA_VERSION = "1.0"
V1_1_INVOICE_SCHEMA_VERSION = "1.1"
V1_1_INVOICE_FIELDS = (
    "customer_name",
    "payments",
    "currency_unit",
    "remaining_balance",
)
MAX_SIGNED_INT64 = (1 << 63) - 1

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "schemas"
    / "v1-1"
    / "issued-invoice-v1-1.schema.json"
)


class InvoiceV1_1ValidationError(ValueError):
    """Invalid explicit v1.1 marker/content; maps to the addendum's 400 error."""

    http_status = 400
    error_code = "VALIDATION_ERROR"
    retry_action = "FIX_REQUEST"

    def __init__(
        self,
        field_paths: Iterable[str],
        *,
        entry_index: int | None = None,
    ) -> None:
        self.field_paths = tuple(sorted(set(field_paths)))
        self.entry_index = entry_index
        # Do not interpolate recorded field values into an error message.
        super().__init__("Invalid v1.1 invoice schema marker or recorded content.")


@dataclass(frozen=True)
class InvoiceValidation:
    """A validated invoice version and its verbatim recorded v1.1 fields.

    ``recorded_fields`` contains only properties that were present in the
    source invoice. An absent property is not defaulted; an explicit JSON null
    remains present with value ``None``. The version marker is intentionally
    not part of the public projection fields.
    """

    schema_version: Literal["1.0", "1.1"]
    recorded_fields: Mapping[str, Any]


@dataclass(frozen=True)
class InvoiceEntryValidation:
    """The v1.1 preflight result for one entry, preserving batch order."""

    entry_index: int
    invoice: InvoiceValidation | None


def _schema_validator():
    """Load and compile the pinned issued-invoice Draft 2020-12 schema."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - installation guidance path
        raise RuntimeError(
            "v1.1 invoice validation requires jsonschema>=4.18,<5"
        ) from exc

    schema = json.loads(_SCHEMA_PATH.read_bytes().decode("utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def _issued_invoice_validator():
    return _schema_validator()


def _json_path(parts: Iterable[Any]) -> str:
    result = "$"
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}"
    return result


def _integer_profile_errors(invoice: Mapping[str, Any]) -> list[str]:
    """Enforce the contract's signed-64-bit integer profile for v1.1 amounts."""
    errors: list[str] = []

    if "remaining_balance" in invoice:
        amount = invoice["remaining_balance"]
        if amount is not None and (
            type(amount) is not int or amount < 0 or amount > MAX_SIGNED_INT64
        ):
            errors.append("$.remaining_balance")

    payments = invoice.get("payments")
    if isinstance(payments, list):
        for index, payment in enumerate(payments):
            if not isinstance(payment, dict) or "amount" not in payment:
                continue  # The pinned schema reports the object/required error.
            amount = payment["amount"]
            if (
                type(amount) is not int
                or amount < 0
                or amount > MAX_SIGNED_INT64
            ):
                errors.append(f"$.payments[{index}].amount")

    return errors


def validate_issued_invoice(invoice: Any, *, entry_index: int | None = None) -> InvoiceValidation:
    """Validate an invoice using marker-only version detection.

    Marker absence means legacy v1.0, even if one or more of the v1.1 field
    names are present. In that case the extension fields are ignored and are
    neither validated nor projected. If the marker is present, its only
    accepted value is the exact string ``"1.1"``; the four fields are then
    validated against the pinned issued-invoice schema and the strict integer
    profile. No field is inferred, filled, converted, or recomputed.
    """
    if not isinstance(invoice, dict):
        raise InvoiceV1_1ValidationError(("$",), entry_index=entry_index)

    if INVOICE_SCHEMA_VERSION_FIELD not in invoice:
        return InvoiceValidation(LEGACY_INVOICE_SCHEMA_VERSION, {})

    if type(invoice[INVOICE_SCHEMA_VERSION_FIELD]) is not str or (
        invoice[INVOICE_SCHEMA_VERSION_FIELD] != V1_1_INVOICE_SCHEMA_VERSION
    ):
        raise InvoiceV1_1ValidationError(
            (f"$.{INVOICE_SCHEMA_VERSION_FIELD}",), entry_index=entry_index
        )

    validator = _issued_invoice_validator()
    field_paths = [
        _json_path(error.absolute_path) for error in validator.iter_errors(invoice)
    ]
    field_paths.extend(_integer_profile_errors(invoice))
    if field_paths:
        raise InvoiceV1_1ValidationError(field_paths, entry_index=entry_index)

    recorded_fields = {
        field_name: deepcopy(invoice[field_name])
        for field_name in V1_1_INVOICE_FIELDS
        if field_name in invoice
    }
    return InvoiceValidation(V1_1_INVOICE_SCHEMA_VERSION, recorded_fields)


def _snapshot_invoice(entry: Any) -> dict[str, Any] | None:
    """Return only the invoice at the addendum's exact snapshot path."""
    if not isinstance(entry, dict):
        return None
    snapshot = entry.get("response_snapshot")
    if not isinstance(snapshot, dict):
        return None
    response = snapshot.get("response")
    if not isinstance(response, dict):
        return None
    invoice = response.get("invoice")
    return invoice if isinstance(invoice, dict) else None


def preflight_v1_1_batch(entries: Iterable[Any]) -> tuple[InvoiceEntryValidation, ...]:
    """Validate every marked v1.1 invoice before returning any projection plan.

    This function is side-effect-free. It never edits the 16-field log entry or
    ``response_snapshot`` (both remain covered by the existing entry hash and
    batch fingerprint). A caller should persist/project only after this full
    function returns successfully, and must retain the frozen transaction,
    hash, and projection-failure behavior for the rest of ingest.

    Entries without an invoice object at
    ``response_snapshot.response.invoice`` are left to the existing envelope
    and projection rules. Legacy invoices with no marker are reported as v1.0
    and yield no v1.1 fields, regardless of field presence.
    """
    if isinstance(entries, (str, bytes, bytearray)) or not isinstance(entries, Iterable):
        raise TypeError("entries must be an iterable of log-entry objects")

    validations: list[InvoiceEntryValidation] = []
    for index, entry in enumerate(entries):
        invoice = _snapshot_invoice(entry)
        if invoice is None:
            validations.append(InvoiceEntryValidation(index, None))
            continue
        validation = validate_issued_invoice(invoice, entry_index=index)
        validations.append(InvoiceEntryValidation(index, validation))

    return tuple(validations)
