"""Canonical Invoice v0 schema validation and lifecycle helpers.

The JSON Schema contains the structural contract. This module adds the
cross-field provenance, lifecycle, and issued-content immutability checks that
JSON Schema cannot express by itself. It deliberately does not transform OCR
text, repair values, or issue an invoice.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "0"
LIFECYCLE_STATES = frozenset(
    {"DRAFT", "EXTRACTED", "VALIDATED", "ISSUED", "REVOKED", "SUPERSEDED"}
)
POST_ISSUANCE_STATES = frozenset({"ISSUED", "REVOKED", "SUPERSEDED"})
VALIDATED_OR_LATER_STATES = frozenset(
    {"VALIDATED", "ISSUED", "REVOKED", "SUPERSEDED"}
)
PROVENANCE_LABELS = frozenset(
    {"native", "captured", "derived", "untrusted", "unavailable"}
)

# Lifecycle state/history and the fingerprint are intentionally excluded: state
# transitions must remain possible, while the issued business content is fixed.
IMMUTABLE_CONTENT_FIELDS = (
    "schema_version",
    "mode",
    "invoice_id",
    "display_number",
    "operation_id",
    "device_id",
    "public_token",
    "store_id",
    "customer",
    "line_items",
    "summary",
    "attention_cells",
    "header",
    "provenance",
)

_ALLOWED_TRANSITIONS = {
    ("DRAFT", "EXTRACTED"),
    ("EXTRACTED", "VALIDATED"),
    ("VALIDATED", "ISSUED"),
    ("ISSUED", "REVOKED"),
    ("ISSUED", "SUPERSEDED"),
}

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "canonical_invoice_v0.json"


@lru_cache(maxsize=1)
def _schema_validator():
    """Load and compile the repository's Draft 2020-12 schema once."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - installation guidance path
        raise RuntimeError(
            "Canonical Invoice validation requires jsonschema>=4.18,<5"
        ) from exc

    with _SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """Return whether one lifecycle edge is permitted by Canonical Invoice v0."""
    if not isinstance(from_state, str) or not isinstance(to_state, str):
        return False
    return (from_state, to_state) in _ALLOWED_TRANSITIONS


def _utf16_sort_key(value: str) -> bytes:
    try:
        return value.encode("utf-16-be")
    except UnicodeEncodeError as exc:
        raise ValueError("JSON strings and object keys must not contain lone surrogates") from exc


def _canonical_json_bytes(value: Any) -> bytes:
    """Serialize the v0 hash profile: compact UTF-8 JSON, integer-only numbers.

    Object keys are ordered lexicographically by UTF-16 code units (the ordering
    used by RFC 8785/JCS). Non-ASCII characters are emitted as UTF-8; JSON
    control characters, quotes, and backslashes use standard JSON escapes. The
    contract forbids floats, avoiding cross-runtime floating-point ambiguity.
    """
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if type(value) is int:
        return str(value).encode("ascii")
    if isinstance(value, float):
        raise ValueError("floating-point values are forbidden in Canonical Invoice v0")
    if isinstance(value, str):
        try:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        except UnicodeEncodeError as exc:
            raise ValueError("JSON strings must not contain lone surrogates") from exc
    if isinstance(value, list):
        return b"[" + b",".join(_canonical_json_bytes(item) for item in value) + b"]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        keys = sorted(value, key=_utf16_sort_key)
        entries = []
        for key in keys:
            encoded_key = _canonical_json_bytes(key)
            encoded_value = _canonical_json_bytes(value[key])
            entries.append(encoded_key + b":" + encoded_value)
        return b"{" + b",".join(entries) + b"}"
    raise ValueError(f"unsupported value for canonical JSON: {type(value).__name__}")


def compute_issued_content_sha256(data: Mapping[str, Any]) -> str:
    """Return the SHA-256 digest of the immutable v0 content projection.

    ``state``, ``state_history``, and ``issued_content_sha256`` are not hashed.
    All required content fields are included, including provenance and attention
    cells. Callers should validate the record before storing the returned digest.
    """
    if not isinstance(data, Mapping):
        raise TypeError("data must be a mapping")
    projection = {
        key: data[key] for key in IMMUTABLE_CONTENT_FIELDS if key in data
    }
    return hashlib.sha256(_canonical_json_bytes(projection)).hexdigest()


def _error_path(path: Any) -> str:
    parts = [str(part) for part in path]
    return ".".join(parts) if parts else "$"


def _format_schema_error(error: Any) -> str:
    return f"{_error_path(error.absolute_path)}: {error.message}"


def _scan_for_floats(value: Any, path: str = "$-") -> list[str]:
    errors: list[str] = []
    if isinstance(value, float):
        errors.append(f"{path}: floating-point values are forbidden; use integer rials")
    elif isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_scan_for_floats(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_scan_for_floats(item, f"{path}[{index}]"))
    return errors


def _optional_accounting_field_errors(summary: Any) -> list[str]:
    """Type-check the optional E-01b accounting placeholders without interpreting them."""
    if not isinstance(summary, dict):
        return []  # The JSON Schema reports an invalid summary shape.

    errors: list[str] = []
    for field_name in ("tax_lines", "discount_lines"):
        if field_name not in summary:
            continue
        lines = summary[field_name]
        if not isinstance(lines, list):
            errors.append(f"summary.{field_name}: must be an array")
            continue
        for index, line in enumerate(lines):
            path = f"summary.{field_name}[{index}]"
            if not isinstance(line, dict):
                errors.append(f"{path}: must be an object")
                continue
            for required_name in ("label", "amount", "provenance"):
                if required_name not in line:
                    errors.append(f"{path}.{required_name}: is required")
            if "label" in line and not isinstance(line["label"], str):
                errors.append(f"{path}.label: must be a string")
            if "amount" in line and type(line["amount"]) is not int:
                errors.append(f"{path}.amount: must be an integer number of rials")
            if "provenance" in line:
                label = line["provenance"]
                if not isinstance(label, str) or label not in PROVENANCE_LABELS:
                    errors.append(
                        f"{path}.provenance: must be one of the v0 provenance labels"
                    )

    if "rounding" in summary:
        rounding = summary["rounding"]
        if rounding is not None and type(rounding) is not int:
            errors.append("summary.rounding: must be an integer or null")

    return errors


def _semantic_errors(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []

    errors: list[str] = []
    errors.extend(_scan_for_floats(data))
    errors.extend(_optional_accounting_field_errors(data.get("summary")))

    # A transition log is a complete ordered path, not a list of independent
    # labels. It starts in DRAFT and its final state must match the snapshot.
    history = data.get("state_history")
    state = data.get("state")
    if isinstance(history, list) and isinstance(state, str) and state in LIFECYCLE_STATES:
        current = "DRAFT"
        for index, event in enumerate(history):
            if not isinstance(event, dict):
                continue  # The JSON Schema reports the shape error.
            from_state = event.get("from_state")
            to_state = event.get("to_state")
            if from_state != current:
                errors.append(
                    f"state_history[{index}].from_state: expected {current!r} "
                    "to preserve one contiguous history"
                )
            if not is_valid_transition(from_state, to_state):
                errors.append(
                    f"state_history[{index}]: transition {from_state!r} -> "
                    f"{to_state!r} is not allowed"
                )
            if isinstance(to_state, str) and to_state in LIFECYCLE_STATES:
                current = to_state
        if state != current:
            errors.append(
                f"state: {state!r} does not match the final state_history state {current!r}"
            )

    provenance = data.get("provenance")
    fields = provenance.get("fields") if isinstance(provenance, dict) else None
    if isinstance(fields, dict):
        # Provenance follows the invoice shape, including dynamic extra-amount
        # names and line-item indexes. A missing mirror is not silently filled.
        items = data.get("line_items")
        item_provenance = fields.get("line_items")
        if isinstance(items, list) and isinstance(item_provenance, list):
            if len(items) != len(item_provenance):
                errors.append(
                    "provenance.fields.line_items: must have one provenance record "
                    "per line item"
                )
            for index, (item, labels) in enumerate(zip(items, item_provenance)):
                if not isinstance(item, dict) or not isinstance(labels, dict):
                    continue
                unit_label = labels.get("unit_price")
                allowed_unit_labels = {"captured", "derived"}
                if data.get("mode") == "A":
                    # Native POS pricing is a source in mode A; mode B must mark
                    # printed prices captured and non-printed prices derived.
                    allowed_unit_labels.add("native")
                if not isinstance(unit_label, str) or unit_label not in allowed_unit_labels:
                    errors.append(
                        f"provenance.fields.line_items[{index}].unit_price: "
                        "must be 'native' in mode A, 'captured' when printed, "
                        "or 'derived' otherwise"
                    )
                for field_name in ("product_name", "quantity", "line_total"):
                    if labels.get(field_name) == "unavailable":
                        errors.append(
                            f"provenance.fields.line_items[{index}].{field_name}: "
                            "a required line-item value cannot be unavailable"
                        )

        summary = data.get("summary")
        summary_labels = fields.get("summary")
        if isinstance(summary, dict) and isinstance(summary_labels, dict):
            amounts = summary.get("extra_amounts")
            amount_labels = summary_labels.get("extra_amounts")
            if isinstance(amounts, dict) and isinstance(amount_labels, dict):
                if set(amounts) != set(amount_labels):
                    errors.append(
                        "provenance.fields.summary.extra_amounts: keys must match "
                        "summary.extra_amounts exactly"
                    )
                for amount_name, label in amount_labels.items():
                    if label == "unavailable":
                        errors.append(
                            "provenance.fields.summary.extra_amounts."
                            f"{amount_name}: a present amount cannot be unavailable"
                        )
            for amount_name in ("subtotal", "payable"):
                if summary_labels.get(amount_name) == "unavailable":
                    errors.append(
                        f"provenance.fields.summary.{amount_name}: "
                        "a required summary value cannot be unavailable"
                    )

        header = data.get("header")
        header_labels = fields.get("header")
        if isinstance(header, dict) and isinstance(header_labels, dict):
            captured_at = header.get("captured_at")
            captured_at_label = header_labels.get("captured_at")
            if captured_at is None:
                if captured_at_label != "unavailable":
                    errors.append(
                        "provenance.fields.header.captured_at: must be 'unavailable' "
                        "when header.captured_at is absent or null"
                    )
            else:
                if captured_at_label != "derived":
                    errors.append(
                        "provenance.fields.header.captured_at: must be 'derived' "
                        "for a Probe capture timestamp"
                    )
                if not isinstance(captured_at, str):
                    errors.append(
                        "header.captured_at: must be an ISO 8601 timestamp with a UTC offset"
                    )
                else:
                    try:
                        parsed_timestamp = datetime.fromisoformat(
                            captured_at[:-1] + "+00:00"
                            if captured_at.endswith("Z")
                            else captured_at
                        )
                        if parsed_timestamp.tzinfo is None:
                            errors.append(
                                "header.captured_at: timestamp must include a UTC offset"
                            )
                    except (TypeError, ValueError):
                        errors.append(
                            "header.captured_at: must be an ISO 8601 timestamp with a UTC offset"
                        )

            for header_name in ("printed_date", "printed_time", "invoice_number"):
                value = header.get(header_name)
                label = header_labels.get(header_name)
                expected = "unavailable" if value is None else "untrusted"
                if label != expected:
                    errors.append(
                        f"provenance.fields.header.{header_name}: must be {expected!r} "
                        f"when its value is {'absent or null' if value is None else 'present'}"
                    )

        # These identifiers are assigned by the Kandoo/platform boundary in v0;
        # printed receipt identifiers live separately under header.invoice_number.
        for field_name in (
            "invoice_id",
            "display_number",
            "operation_id",
            "device_id",
            "public_token",
            "store_id",
        ):
            if fields.get(field_name) != "native":
                errors.append(
                    f"provenance.fields.{field_name}: must be 'native'"
                )
        customer_labels = fields.get("customer")
        if isinstance(customer_labels, dict) and customer_labels.get("phone_status") != "native":
            errors.append("provenance.fields.customer.phone_status: must be 'native'")
        if isinstance(customer_labels, dict) and customer_labels.get("phone") == "unavailable":
            errors.append("provenance.fields.customer.phone: required phone cannot be unavailable")

    if isinstance(state, str) and state in VALIDATED_OR_LATER_STATES:
        attention_cells = data.get("attention_cells")
        if isinstance(attention_cells, list) and attention_cells:
            errors.append(
                f"attention_cells: must be empty in state {state!r}; unresolved cells require review"
            )
        if isinstance(fields, dict):
            # A validated/issued record cannot promote an explicitly untrusted
            # required value into trusted content. Optional printed headers stay
            # marked untrusted and do not by themselves block issuance.
            required_labels: list[tuple[str, Any]] = []
            for name in ("invoice_id", "display_number", "operation_id", "device_id", "public_token", "store_id"):
                required_labels.append((f"provenance.fields.{name}", fields.get(name)))
            customer_labels = fields.get("customer")
            if isinstance(customer_labels, dict):
                required_labels.append(("provenance.fields.customer.phone", customer_labels.get("phone")))
            item_labels = fields.get("line_items")
            if isinstance(item_labels, list):
                for index, labels in enumerate(item_labels):
                    if isinstance(labels, dict):
                        for name in ("product_name", "quantity", "unit_price", "line_total"):
                            required_labels.append(
                                (f"provenance.fields.line_items[{index}].{name}", labels.get(name))
                            )
            summary_labels = fields.get("summary")
            if isinstance(summary_labels, dict):
                for name in ("subtotal", "payable"):
                    required_labels.append(
                        (f"provenance.fields.summary.{name}", summary_labels.get(name))
                    )
                extra_labels = summary_labels.get("extra_amounts")
                if isinstance(extra_labels, dict):
                    required_labels.extend(
                        (f"provenance.fields.summary.extra_amounts.{key}", label)
                        for key, label in extra_labels.items()
                    )
            for path, label in required_labels:
                if isinstance(label, str) and label in {"untrusted", "unavailable"}:
                    errors.append(
                        f"{path}: {label!r} required values cannot reach VALIDATED or later"
                    )

    # Check the digest for ISSUED and its two terminal successors. The same
    # fingerprint is retained across revocation/supersession.
    if (
        isinstance(state, str)
        and state in POST_ISSUANCE_STATES
        and isinstance(data.get("issued_content_sha256"), str)
    ):
        try:
            expected_digest = compute_issued_content_sha256(data)
        except (TypeError, ValueError) as exc:
            errors.append(f"issued_content_sha256: cannot hash immutable content: {exc}")
        else:
            if data["issued_content_sha256"] != expected_digest:
                errors.append(
                    "issued_content_sha256: does not match immutable invoice content"
                )
    elif (
        (not isinstance(state, str) or state not in POST_ISSUANCE_STATES)
        and "issued_content_sha256" in data
    ):
        errors.append("issued_content_sha256: is only permitted at ISSUED or later")

    return errors


def validate_canonical_invoice(data: Any) -> tuple[bool, list[str]]:
    """Validate a Canonical Invoice v0 value without modifying it.

    Returns ``(is_valid, errors)``. Schema errors are structural; additional
    errors enforce exact integer values, mirrored provenance, lifecycle order,
    header provenance rules, and the immutable-content digest.
    """
    try:
        validator = _schema_validator()
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        return False, [f"schema: unable to load Canonical Invoice v0 schema: {exc}"]

    errors = [_format_schema_error(error) for error in validator.iter_errors(data)]
    errors.extend(_semantic_errors(data))
    errors = sorted(set(errors))
    return not errors, errors


def is_issuable(data: Any) -> bool:
    """Return true only for a valid, immutable invoice in state ``ISSUED``."""
    valid, _errors = validate_canonical_invoice(data)
    if not valid or not isinstance(data, dict) or data.get("state") != "ISSUED":
        return False
    # Keep the issuance gate explicit even though the schema requires these
    # fields; callers can safely use it as the documented contract boundary.
    return all(
        data.get(field_name) not in (None, "")
        for field_name in (
            "invoice_id",
            "display_number",
            "operation_id",
            "device_id",
            "public_token",
            "store_id",
        )
    ) and isinstance(data.get("customer"), dict) and bool(
        data["customer"].get("phone")
    ) and bool(data.get("line_items")) and isinstance(data.get("summary"), dict)


def get_provenance_label(field_name: str) -> str:
    """Return the v0 default provenance policy for a known field path.

    This function describes a default, not an individual invoice's recorded
    label. In particular, unit_price is ``derived`` by default but may be
    ``captured`` when it is explicitly printed; inspect provenance.fields for
    the actual record label. Unknown paths return ``unavailable``.
    """
    if not isinstance(field_name, str):
        return "unavailable"
    name = field_name.strip()
    if not name:
        return "unavailable"

    native_fields = {
        "invoice_id",
        "display_number",
        "operation_id",
        "device_id",
        "public_token",
        "store_id",
        "customer.phone_status",
    }
    if name in native_fields:
        return "native"
    if name in {"header.captured_at", "captured_at", "unit_price"}:
        return "derived"
    if name in {
        "header.printed_date",
        "header.printed_time",
        "header.invoice_number",
        "printed_date",
        "printed_time",
        "invoice_number",
        "invoice.number",
        "invoice.date",
    }:
        return "untrusted"
    if name == "customer.phone":
        return "captured"
    if re.fullmatch(r"(?:line|line_items)(?:\.\d+)?\.unit_price", name):
        return "derived"
    if name in {"product_name", "description", "quantity", "line_total", "total"}:
        return "captured"
    if re.fullmatch(
        r"(?:line|line_items)(?:\.\d+)?\.(?:product_name|description|quantity|line_total|total)",
        name,
    ):
        return "captured"
    if name in {
        "summary.subtotal",
        "summary.payable",
        "summary.extra_amounts",
        "total.net",
        "tax.amount",
        "invoice.payable",
    }:
        return "captured"
    return "unavailable"
