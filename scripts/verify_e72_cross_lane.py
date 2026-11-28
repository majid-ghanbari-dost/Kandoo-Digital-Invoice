"""E-72 cross-lane acceptance verification — PY-B backlog item 1 (PM-36).

Executes the exact validation semantics of the frozen C# consumer
``src/Kandoo.Core/CanonicalInvoiceConsumer.cs`` (repo majid-ghanbari-dost/Kandoo,
main @ 45d5fba6f8b7cfcac2900919f7eef685782e26d4, blob 5f06ec05318c2932c5114d0078b335df29b50b0b,
705 lines, unchanged since the PHP round-2 verdict) rule-by-rule against the
flat-root E-72 round-3 vectors, and proves byte-profile unity with the U7-v1
canonical JSON profile pinned by ``docs/vectors/canonical-vectors-v1.json``
(57 vectors, C-66) on the C# repo.

This script is a line-faithful Python port used as acceptance evidence. It
does NOT modify the frozen C# consumer, the E-11 schema, or any PHP contract.
The emitted record is the acceptance evidence published to
``docs/vectors/`` on the Kandoo repo; a lane countersignature may follow but
is not claimed here. Everything referenced is synthetic/fictional.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIR = ROOT / "tests" / "golden" / "e72"
E11_BASE_SCHEMA = Path("contracts") / "canonical_invoice_v0.schema.json"

FROZEN_SOURCES = {
    "csharp_consumer": {
        "repo": "majid-ghanbari-dost/Kandoo",
        "path": "src/Kandoo.Core/CanonicalInvoiceConsumer.cs",
        "main_commit": "45d5fba6f8b7cfcac2900919f7eef685782e26d4",
        "blob": "5f06ec05318c2932c5114d0078b335df29b50b0b",
    },
    "e11_schema": {
        "path": "contracts/canonical_invoice_v0.schema.json",
        "sha256": "bd917eb0d0b66f2c260d181a5058e5a44eb9d749ab99c015352e914caf891e88",
    },
    "u7_profile_vectors": {
        "repo": "majid-ghanbari-dost/Kandoo",
        "path": "docs/vectors/canonical-vectors-v1.json",
        "blob": "b6c1698d363f5df0262c08a2da0d2caf43f98da5",
        "pinned_copy": "tests/golden/e72/u7-canonical-vectors-v1.json",
    },
}

# --- U7-v1 canonical JSON profile (derived from and verified against all 57
# pinned vectors: V1-V12, C00-C1F, X1-X13). Compact UTF-8; object keys sorted
# by code point (= unsigned UTF-8 order); arrays keep order; integers only;
# non-ASCII literal; every C0 control (0x00-0x1F) and DEL (0x7F) escaped as
# \\u00XX with UPPERCASE hex (no short escapes); " and \\ escaped; / literal. ---


def u7_string(value: str) -> str:
    out = ['"']
    for character in value:
        code = ord(character)
        if character == '"':
            out.append('\\"')
        elif character == "\\":
            out.append("\\\\")
        elif code < 0x20 or code == 0x7F:
            out.append("\\u%04X" % code)
        else:
            out.append(character)
    out.append('"')
    return "".join(out)


def u7_serialize(document: Any) -> bytes:
    """Serialize one JSON value under the pinned U7-v1 profile."""
    if isinstance(document, dict):
        body = ",".join(
            u7_string(key) + ":" + u7_serialize(document[key]).decode("utf-8")
            for key in sorted(document)
        )
        return ("{" + body + "}").encode("utf-8")
    if isinstance(document, list):
        body = ",".join(u7_serialize(item).decode("utf-8") for item in document)
        return ("[" + body + "]").encode("utf-8")
    if isinstance(document, bool):
        return (b"true" if document else b"false")
    if document is None:
        return b"null"
    if isinstance(document, int):
        return str(document).encode("utf-8")
    if isinstance(document, str):
        return u7_string(document).encode("utf-8")
    raise ValueError(f"U7-v1 does not serialize type {type(document).__name__}")


# --- Strict-JSON plumbing mirroring JsonDocumentOptions (no trailing commas,
# no comments, duplicate keys rejected) plus raw number tokens for
# IsIntegerToken / GetInt64 semantics. ---


class _IntToken(int):
    raw = ""


class _FloatToken(float):
    raw = ""


def _make_int_token(raw: str) -> _IntToken:
    token = _IntToken(raw)
    token.raw = raw
    return token


def _make_float_token(raw: str) -> _FloatToken:
    token = _FloatToken(raw)
    token.raw = raw
    return token


def _reject_constant(name: str) -> None:
    raise ValueError(f"invalid JSON constant: {name}")


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError("Duplicate JSON object keys are forbidden.")
        seen.add(key)
        result[key] = value
    return result


def parse_strict_json(text: str) -> Any:
    """Parse with the frozen consumer's strictness (JsonDocumentOptions)."""
    return json.loads(
        text,
        parse_constant=_reject_constant,
        parse_int=_make_int_token,
        parse_float=_make_float_token,
        object_pairs_hook=_no_duplicate_object,
    )


# --- Faithful port of CanonicalInvoiceConsumer validation. Error codes and
# fail-fast ordering mirror the C# source; line cites refer to the blob above. ---


class ConsumerError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code} | {message}")
        self.code = code
        self.message = message


def _error(code: str, message: str) -> ConsumerError:
    return ConsumerError(code, message)


# CanonicalInvoiceErrorCodes (lines 8-18)
INVALID_JSON = "INVALID_JSON"
REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
QUANTITY_NOT_INTEGER = "QUANTITY_MILLIS_NOT_INTEGER"
AMOUNT_NOT_INTEGER = "AMOUNT_NOT_INTEGER"
AMOUNT_NEGATIVE = "AMOUNT_NEGATIVE"
NON_INTEGER_NUMBER = "NON_INTEGER_JSON_NUMBER"
DISPLAY_NUMBER_BEFORE_ISSUE = "DISPLAY_NUMBER_BEFORE_ISSUE"
ISSUED_HASH_MISMATCH = "ISSUED_CONTENT_HASH_MISMATCH"
INVALID_UTF16 = "INVALID_UTF16"

ROOT_REQUIRED = [
    "schema_version", "mode", "invoice_id", "display_number", "operation_id",
    "device_id", "public_token", "store_id", "customer", "state", "state_history",
    "line_items", "summary", "attention_cells", "header", "provenance",
]  # lines 53-58
ROOT_ALLOWED = set(ROOT_REQUIRED) | {"issued_content_sha256"}  # line 60
STATES = {"DRAFT", "EXTRACTED", "VALIDATED", "ISSUED", "REVOKED", "SUPERSEDED"}  # line 61
PROVENANCE_LABELS = {
    "native", "captured", "derived", "untrusted", "unavailable", "operator_confirmed",
}  # line 62


def _is_integer_token(raw: str) -> bool:  # lines 466-483
    if not raw or raw == "-0" or "." in raw or "e" in raw or "E" in raw or raw.startswith("+"):
        return False
    index = 1 if raw[0] == "-" else 0
    if index >= len(raw) or (raw[index] == "0" and len(raw) - index > 1):
        return False
    return all("0" <= character <= "9" for character in raw[index:])


def _validate_unicode(value: str) -> None:  # lines 610-627
    index = 0
    while index < len(value):
        current = value[index]
        code = ord(current)
        if 0xD800 <= code <= 0xDBFF:
            if index + 1 >= len(value) or not 0xDC00 <= ord(value[index + 1]) <= 0xDFFF:
                raise _error(INVALID_UTF16, "Lone UTF-16 surrogates are forbidden.")
            index += 1
        elif 0xDC00 <= code <= 0xDFFF:
            raise _error(INVALID_UTF16, "Lone UTF-16 surrogates are forbidden.")
        index += 1


def _validate_json_tree(value: Any, path: str, depth: int = 0) -> None:
    """ValidateJsonTree (lines 394-440) + JsonDocumentOptions.MaxDepth=128."""
    if depth > 128:
        raise _error(INVALID_JSON, "Maximum JSON depth exceeded.")
    if isinstance(value, dict):
        for key, child in value.items():
            _validate_unicode(key)
            _validate_json_tree(child, f"{path}/{key}", depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_tree(child, f"{path}/{index}", depth + 1)
    elif isinstance(value, (_IntToken, _FloatToken)):
        raw = value.raw
        if not _is_integer_token(raw):
            if path.endswith("/quantity_millis"):
                code = QUANTITY_NOT_INTEGER
            elif "amount" in path or path.endswith(("/unit_price", "/line_total", "/subtotal", "/payable", "/rounding")):
                code = AMOUNT_NOT_INTEGER
            else:
                code = NON_INTEGER_NUMBER
            raise _error(code, "Only base-10 JSON integer number tokens are accepted.")
        if isinstance(value, _IntToken) and not (-(2**63) <= int(value) < 2**63):
            raise _error(AMOUNT_NOT_INTEGER, "number must be a JSON integer.")  # TryGetInt64
    elif isinstance(value, str):
        _validate_unicode(value)


def _require(obj: Any, name: str) -> Any:  # lines 510-517
    if not isinstance(obj, dict) or name not in obj:
        raise _error(REQUIRED_FIELD_MISSING, f"Required field is missing: {name}.")
    return obj[name]


def _require_string(obj: Any, name: str) -> str:
    return _require_string_value(_require(obj, name), name)


def _require_string_value(value: Any, name: str) -> str:  # lines 519-527
    if not isinstance(value, str) or not value:
        raise _error(SCHEMA_VALIDATION_FAILED, f"{name} must be a non-empty string.")
    return value


def _require_nullable_string(obj: Any, name: str) -> None:  # lines 548-557
    value = _require(obj, name)
    if value is not None:
        _require_string_value(value, name)


def _require_string_token(value: Any, name: str) -> str:  # lines 529-537
    if not isinstance(value, str):
        raise _error(SCHEMA_VALIDATION_FAILED, f"{name} must be a string.")
    return value


def _require_object(value: Any) -> dict:  # lines 559-564
    if not isinstance(value, dict):
        raise _error(SCHEMA_VALIDATION_FAILED, "Expected a JSON object.")
    return value


def _require_array(value: Any) -> list:  # lines 566-571
    if not isinstance(value, list):
        raise _error(SCHEMA_VALIDATION_FAILED, "Expected a JSON array.")
    return value


def _reject_unknown(obj: Any, allowed: set[str] | tuple[str, ...]) -> None:  # lines 573-582
    for name in obj:
        if name not in set(allowed):
            raise _error(SCHEMA_VALIDATION_FAILED, f"Unexpected field: {name}.")


def _require_state(obj: Any, name: str) -> str:  # lines 485-493
    state = _require_string(obj, name)
    if state not in STATES:
        raise _error(SCHEMA_VALIDATION_FAILED, "Invalid lifecycle state.")
    return state


def _require_label(obj: Any, name: str) -> None:  # lines 495-503
    label = _require_string_value(_require(obj, name), name)
    if label not in PROVENANCE_LABELS:
        raise _error(SCHEMA_VALIDATION_FAILED, "Invalid provenance label.")


def _require_integer(obj: Any, name: str, code: str, non_negative: bool) -> int:  # lines 442-463
    value = _require(obj, name)
    raw = getattr(value, "raw", None)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or raw is None or not _is_integer_token(raw):
        raise _error(code, f"{name} must be a JSON integer.")
    result = int(value)
    if not (-(2**63) <= result < 2**63):
        raise _error(code, f"{name} must be a JSON integer.")
    if non_negative and result < 0:
        raise _error(AMOUNT_NEGATIVE, f"{name} must not be negative.")
    return result


def _require_integer_value(value: Any, code: str, non_negative: bool, name: str) -> int:
    raw = getattr(value, "raw", None)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or raw is None or not _is_integer_token(raw):
        raise _error(code, f"{name} must be a JSON integer.")
    result = int(value)
    if not (-(2**63) <= result < 2**63):
        raise _error(code, f"{name} must be a JSON integer.")
    if non_negative and result < 0:
        raise _error(AMOUNT_NEGATIVE, f"{name} must not be negative.")
    return result


def _validate_public_token(token: str) -> None:  # lines 584-590
    if len(token) < 22 or any(
        not (character.isascii() and (character.isalnum() or character in "_-"))
        for character in token
    ):
        raise _error(
            SCHEMA_VALIDATION_FAILED,
            "public_token must be an unpadded base64url token of at least 22 characters.",
        )


def _validate_hash(value: str) -> None:  # lines 592-598
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise _error(SCHEMA_VALIDATION_FAILED, "Expected a lowercase SHA-256 hexadecimal digest.")


def _validate_customer(customer: Any) -> None:  # lines 175-185
    _require_object(customer)
    _reject_unknown(customer, {"phone", "phone_status"})
    _require_string(customer, "phone")
    status = _require_string(customer, "phone_status")
    if status not in {"claimed", "verified"}:
        raise _error(SCHEMA_VALIDATION_FAILED, "Invalid customer phone_status.")


def _validate_state_history(history: Any, current_state: str) -> None:  # lines 187-207
    _require_array(history)
    last = None
    for transition in history:
        _require_object(transition)
        _reject_unknown(transition, {"from_state", "to_state", "operation_id", "device_id"})
        _require_state(transition, "from_state")
        _require_state(transition, "to_state")
        _require_string(transition, "operation_id")
        _require_string(transition, "device_id")
        last = transition
    if last is not None and _require_string(last, "to_state") != current_state:
        raise _error(SCHEMA_VALIDATION_FAILED, "state_history must terminate at state.")


def _validate_line_items(items: Any) -> None:  # lines 209-228
    _require_array(items)
    if len(items) == 0:
        raise _error(SCHEMA_VALIDATION_FAILED, "line_items must not be empty.")
    for item in items:
        _require_object(item)
        _reject_unknown(item, {"product_name", "quantity_millis", "unit_price", "line_total"})
        _require_string(item, "product_name")
        _require_integer(item, "quantity_millis", QUANTITY_NOT_INTEGER, False)
        _require_integer(item, "unit_price", AMOUNT_NOT_INTEGER, True)
        _require_integer(item, "line_total", AMOUNT_NOT_INTEGER, True)


def _validate_optional_amount_lines(summary: Any, name: str) -> None:  # lines 250-272
    if name not in summary:
        return
    lines = _require_array(summary[name])
    for line in lines:
        _require_object(line)
        _reject_unknown(line, {"label", "amount", "provenance"})
        label = _require(line, "label")
        if not isinstance(label, str):
            raise _error(SCHEMA_VALIDATION_FAILED, "Amount-line labels must be strings.")
        _require_integer(line, "amount", AMOUNT_NOT_INTEGER, False)
        _require_label(line, "provenance")


def _validate_summary(summary: Any) -> None:  # lines 230-248
    _require_object(summary)
    _reject_unknown(summary, {"subtotal", "extra_amounts", "payable", "tax_lines", "discount_lines", "rounding"})
    _require_integer(summary, "subtotal", AMOUNT_NOT_INTEGER, True)
    _require_integer(summary, "payable", AMOUNT_NOT_INTEGER, True)
    extras = _require(summary, "extra_amounts")
    _require_object(extras)
    for extra_value in extras.values():
        _require_integer_value(extra_value, AMOUNT_NOT_INTEGER, True, "extra_amounts")
    _validate_optional_amount_lines(summary, "tax_lines")
    _validate_optional_amount_lines(summary, "discount_lines")
    if "rounding" in summary and summary["rounding"] is not None:
        _require_integer_value(summary["rounding"], AMOUNT_NOT_INTEGER, False, "rounding")


def _validate_attention_cells(cells: Any, state: str) -> None:  # lines 274-296
    _require_array(cells)
    if state in {"VALIDATED", "ISSUED", "REVOKED", "SUPERSEDED"} and len(cells) != 0:
        raise _error(
            SCHEMA_VALIDATION_FAILED,
            "Issued records cannot retain unresolved attention_cells.",
        )
    for cell in cells:
        _require_object(cell)
        _reject_unknown(cell, {"field", "raw_value", "reason"})
        _require_string(cell, "field")
        raw_value = _require(cell, "raw_value")
        if not isinstance(raw_value, str):
            raise _error(SCHEMA_VALIDATION_FAILED, "attention_cells.raw_value must be a string.")
        _require_string(cell, "reason")


def _validate_header(header: Any) -> None:  # lines 298-311
    _require_object(header)
    _reject_unknown(header, {"captured_at", "printed_date", "printed_time", "invoice_number"})
    for name, value in header.items():
        if value is not None:
            _require_string_token(value, name)


def _validate_provenance(provenance: Any) -> dict:  # lines 313-375
    _require_object(provenance)
    _reject_unknown(provenance, {"image_sha256", "template_library_id", "engine_version", "fields"})
    for name in ("image_sha256", "template_library_id", "engine_version", "fields"):
        _require(provenance, name)
    image = provenance["image_sha256"]
    if image is not None:
        _validate_hash(_require_string_value(image, "image_sha256"))
    _require_nullable_string(provenance, "template_library_id")
    _require_nullable_string(provenance, "engine_version")
    fields = _require(provenance, "fields")
    _require_object(fields)
    field_names = (
        "invoice_id", "display_number", "operation_id", "device_id", "public_token",
        "store_id", "customer", "line_items", "summary", "header",
    )
    _reject_unknown(fields, set(field_names))
    for name in field_names:
        _require(fields, name)
    for name in field_names[:6]:
        _require_label(fields, name)
    customer = fields["customer"]
    _require_object(customer)
    _reject_unknown(customer, {"phone", "phone_status"})
    _require_label(customer, "phone")
    _require_label(customer, "phone_status")
    items = _require_array(fields["line_items"])
    if len(items) == 0:
        raise _error(SCHEMA_VALIDATION_FAILED, "Provenance line_items must not be empty.")
    for item in items:
        _require_object(item)
        _reject_unknown(item, {"product_name", "quantity_millis", "unit_price", "line_total"})
        for name in ("product_name", "quantity_millis", "unit_price", "line_total"):
            _require_label(item, name)
    summary = fields["summary"]
    _require_object(summary)
    _reject_unknown(summary, {"subtotal", "extra_amounts", "payable"})
    _require_label(summary, "subtotal")
    _require_label(summary, "payable")
    extras = _require(summary, "extra_amounts")
    _require_object(extras)
    for extra_value in extras.values():
        _require_label_value(extra_value, "extra_amounts")
    header = fields["header"]
    _require_object(header)
    _reject_unknown(header, {"captured_at", "printed_date", "printed_time", "invoice_number"})
    for name in ("captured_at", "printed_date", "printed_time", "invoice_number"):
        _require_label(header, name)
    return fields


def _require_label_value(value: Any, name: str) -> None:
    label = _require_string_value(value, name)
    if label not in PROVENANCE_LABELS:
        raise _error(SCHEMA_VALIDATION_FAILED, "Invalid provenance label.")


def _validate_lifecycle(root: dict, state: str, provenance_fields: dict) -> None:  # lines 143-173
    display = _require(root, "display_number")
    pre_issue = state in {"DRAFT", "EXTRACTED", "VALIDATED"}
    display_provenance = _require_string(provenance_fields, "display_number")
    if pre_issue:
        if display is not None or display_provenance != "unavailable":
            raise _error(DISPLAY_NUMBER_BEFORE_ISSUE, "display_number is unavailable before ISSUE.")
        if "issued_content_sha256" in root:
            raise _error(
                SCHEMA_VALIDATION_FAILED,
                "Pre-ISSUE records cannot carry an issued-content hash.",
            )
        return
    if not isinstance(display, str) or not display or display_provenance != "native":
        raise _error(
            SCHEMA_VALIDATION_FAILED,
            "Issued and terminal records require a native display_number.",
        )
    supplied = _require_string(root, "issued_content_sha256")
    _validate_hash(supplied)
    # ComputeIssuedHash projection (lines 639-682): 14 projection fields,
    # keys sorted by ordinal, compact writer, raw number tokens. DRAFT vectors
    # never reach this branch; ISSUED vectors are checked by the golden suite.
    projection_names = [
        "schema_version", "mode", "invoice_id", "display_number", "operation_id",
        "device_id", "public_token", "store_id", "customer", "line_items", "summary",
        "attention_cells", "header", "provenance",
    ]
    projection: dict[str, Any] = {}
    for name in projection_names:
        if name in root:
            projection[name] = root[name]
    computed = hashlib.sha256(u7_serialize(projection)).hexdigest()
    if supplied != computed:
        raise _error(ISSUED_HASH_MISMATCH, "The issued-content hash does not match the immutable projection.")


# Ordered rule groups with the frozen source lines they port. Each group runs
# fail-fast like the C# validator; the record marks every group PASS.
CONSUMER_RULE_GROUPS: list[tuple[str, str]] = [
    ("json_tree", "ValidateJsonTree + JsonDocumentOptions: strict JSON, no duplicate keys, valid UTF-16, integer-only number tokens (lines 65-78, 394-440)"),
    ("root_shape", "RejectUnknown(RootAllowed) + 16 RootRequired fields (lines 53-60, 109-115)"),
    ("schema_version", 'RequireString == "0" (line 117)'),
    ("mode", 'mode in {"A","B"} (lines 123-127)'),
    ("identifiers", "invoice_id/operation_id/device_id/store_id non-empty strings (lines 129-132)"),
    ("public_token", "unpadded base64url, length >= 22 (line 133, 584-590)"),
    ("state", "state in States (line 134, 485-493)"),
    ("customer", "phone + phone_status in {claimed, verified} (line 135, 175-185)"),
    ("state_history", "transition shape + last to_state == state (line 136, 187-207)"),
    ("line_items", "non-empty; product_name/quantity_millis/unit_price/line_total (line 137, 209-228)"),
    ("summary", "subtotal/payable/extra_amounts (+ optional amount lines, rounding) (line 138, 230-272)"),
    ("attention_cells", "array shape; empty when VALIDATED/ISSUED/terminal (line 139, 274-296)"),
    ("header", "captured_at/printed_date/printed_time/invoice_number null-or-string (line 140, 298-311)"),
    ("provenance", "image_sha256/template_library_id/engine_version/fields + labels (line 141, 313-375)"),
    ("lifecycle", "DRAFT: display_number null + unavailable provenance + no issued hash (line 142, 143-173)"),
]


def consume_for_review(json_text: str) -> dict[str, Any]:
    """Port of CanonicalInvoiceConsumer.ConsumeForReview (lines 64-106).

    Raises ConsumerError with the frozen error code and message on any
    violation; returns the mapped review projection on success.
    """
    try:
        root = parse_strict_json(json_text)
    except (json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ConsumerError):
            raise
        raise _error(INVALID_JSON, "The Canonical Invoice is not valid strict JSON.") from exc
    if not isinstance(root, dict):
        raise _error(SCHEMA_VALIDATION_FAILED, "The Canonical Invoice root must be an object.")
    _validate_json_tree(root, "$")
    _reject_unknown(root, ROOT_ALLOWED)  # fail-fast first step of ValidateRoot
    for name in ROOT_REQUIRED:
        _require(root, name)
    if _require_string(root, "schema_version") != "0":
        raise _error(SCHEMA_VALIDATION_FAILED, "Unsupported Canonical Invoice schema_version.")
    mode = _require_string(root, "mode")
    if mode not in {"A", "B"}:
        raise _error(SCHEMA_VALIDATION_FAILED, "mode must be A or B.")
    _require_string(root, "invoice_id")
    _require_string(root, "operation_id")
    _require_string(root, "device_id")
    _require_string(root, "store_id")
    _validate_public_token(_require_string(root, "public_token"))
    state = _require_state(root, "state")
    _validate_customer(_require(root, "customer"))
    _validate_state_history(_require(root, "state_history"), state)
    _validate_line_items(_require(root, "line_items"))
    _validate_summary(_require(root, "summary"))
    _validate_attention_cells(_require(root, "attention_cells"), state)
    _validate_header(_require(root, "header"))
    provenance_fields = _validate_provenance(_require(root, "provenance"))
    _validate_lifecycle(root, state, provenance_fields)
    items = root["line_items"]
    return {
        "queue_status": "REVIEW",
        "invoice_id": root["invoice_id"],
        "store_id": root["store_id"],
        "source_state": root["state"],
        "display_number": root["display_number"],
        "payable": int(root["summary"]["payable"]),
        "line_item_count": len(items),
    }


def _rule_group_trace(json_text: str) -> dict[str, str]:
    """Run the consumer port; every ordered rule group is marked PASS when the
    document is accepted (fail-fast semantics: a violation raises before the
    later groups run)."""
    consume_for_review(json_text)
    return {name: "PASS" for name, _ in CONSUMER_RULE_GROUPS}


# Negative probes: each must be rejected with the exact frozen error code.
# The wrapper probe reproduces Decision 29's decisive error line verbatim.
NEGATIVE_PROBES: list[tuple[str, str, str]] = [
    (
        "wrapper_root_base_invoice",
        '{"base_invoice": {}, "synthetic_only": true, "v1_2_draft_addendum": {}, "vector_id": "x"}',
        SCHEMA_VALIDATION_FAILED,
    ),
    ("missing_required_root_field", "{}", REQUIRED_FIELD_MISSING),
    ("quantity_alias", "", SCHEMA_VALIDATION_FAILED),  # filled from the live vector at runtime
    ("display_before_issue", "", DISPLAY_NUMBER_BEFORE_ISSUE),
    ("issued_hash_on_draft", "", SCHEMA_VALIDATION_FAILED),
    ("float_amount", "", AMOUNT_NOT_INTEGER),
    ("short_public_token", "", SCHEMA_VALIDATION_FAILED),
]


def _probe_rejections(vector_document: dict) -> list[dict[str, Any]]:
    import copy

    results: list[dict[str, Any]] = []

    def run(name: str, document: Any, expected_code: str, expected_message: str | None = None) -> None:
        text = json.dumps(document, ensure_ascii=False, allow_nan=False)
        try:
            consume_for_review(text)
        except ConsumerError as exc:
            if exc.code != expected_code:
                raise AssertionError(
                    f"probe {name}: expected {expected_code}, got {exc.code}"
                ) from exc
            if expected_message is not None and expected_message not in exc.message:
                raise AssertionError(
                    f"probe {name}: message {exc.message!r} lacks {expected_message!r}"
                ) from exc
            results.append({
                "probe": name,
                "expected_error_code": expected_code,
                "observed_error_code": exc.code,
                "observed_message": exc.message,
                "result": "REJECTED_AS_FROZEN",
            })
            return
        raise AssertionError(f"probe {name}: unexpectedly accepted")

    run(
        "wrapper_root_base_invoice",
        {"base_invoice": {}, "synthetic_only": True, "v1_2_draft_addendum": {}, "vector_id": "x"},
        SCHEMA_VALIDATION_FAILED,
        "Unexpected field: base_invoice.",
    )
    run("empty_root_missing_fields", {}, REQUIRED_FIELD_MISSING, "Required field is missing: schema_version.")

    alias = copy.deepcopy(vector_document)
    alias_item = alias["line_items"][0]
    alias_item.pop("quantity_millis")
    alias_item["quantity"] = 1
    alias["provenance"]["fields"]["line_items"][0].pop("quantity_millis")
    alias["provenance"]["fields"]["line_items"][0]["quantity"] = "captured"
    run("line_item_quantity_alias", alias, SCHEMA_VALIDATION_FAILED, "Unexpected field: quantity.")

    display = copy.deepcopy(vector_document)
    display["display_number"] = "SYN-E72-001"
    display["provenance"]["fields"]["display_number"] = "native"
    run("display_number_before_issue", display, DISPLAY_NUMBER_BEFORE_ISSUE, "display_number is unavailable before ISSUE.")

    hashed = copy.deepcopy(vector_document)
    hashed["issued_content_sha256"] = "0" * 64
    run("issued_hash_on_draft", hashed, SCHEMA_VALIDATION_FAILED, "Pre-ISSUE records cannot carry an issued-content hash.")

    floating = copy.deepcopy(vector_document)
    floating["summary"]["subtotal"] = _make_float_token("1.5")
    floating["summary"]["subtotal"].raw = "1.5"
    # ValidateJsonTree runs before ValidateSummary (fail-fast order), so the
    # float is rejected in the tree walk with the amount-path error code.
    run("float_subtotal", floating, AMOUNT_NOT_INTEGER, "Only base-10 JSON integer number tokens are accepted.")

    token = copy.deepcopy(vector_document)
    token["public_token"] = "short"
    run("short_public_token", token, SCHEMA_VALIDATION_FAILED, "public_token")

    return results


def verify_cross_lane(root: Path = ROOT) -> dict[str, Any]:
    vector_dir = root / "tests" / "golden" / "e72"
    manifest = json.loads((vector_dir / "manifest.json").read_bytes().decode("utf-8"))

    # U7 profile replay: the pinned port must reproduce all 57 C-66 vectors.
    u7_source = json.loads((vector_dir / "u7-canonical-vectors-v1.json").read_bytes().decode("utf-8"))
    u7_mismatches: list[str] = []
    for vector in u7_source["vectors"]:
        document = parse_strict_json(vector["input_json"])
        canonical = u7_serialize(document)
        actual_hex = canonical.hex()
        actual_sha = hashlib.sha256(canonical).hexdigest()
        if actual_hex != vector["canonical_hex"] or actual_sha != vector["sha256"]:
            u7_mismatches.append(vector["id"])
    if u7_mismatches:
        raise AssertionError(f"U7 profile replay failed for: {', '.join(u7_mismatches)}")

    vector_records: list[dict[str, Any]] = []
    documents: dict[str, dict] = {}
    for entry in manifest["vectors"]:
        filename = entry["file"]
        raw = (vector_dir / filename).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry["sha256"] or len(raw) != entry["bytes"]:
            raise AssertionError(f"manifest pin mismatch: {filename}")
        document = parse_strict_json(raw.decode("utf-8"))
        documents[filename] = document
        u7_bytes = u7_serialize(document)
        vector_records.append({
            "file": filename,
            "bytes": len(raw),
            "sha256": digest,
            "u7_profile_match": u7_bytes == raw,
            "consumer_rules": _rule_group_trace(raw.decode("utf-8")),
            "review_projection": consume_for_review(raw.decode("utf-8")),
        })
        if u7_bytes != raw:
            raise AssertionError(f"U7 profile mismatch for pinned vector: {filename}")

    baseline = documents[manifest["vectors"][0]["file"]]
    return {
        "schema_version": "e72.cross-lane-acceptance.v1",
        "task": "E-72 vectors accepted by C# and PHP (docs/BACKLOG.md PY-A/PY-B item 3, TASKS/PY-B.md item 1)",
        "recorded_by": "PY-B agent session (arena/b8ba8d2e-kandoo-digital-invoice)",
        "recorded_at": "2026-11-28",
        "synthetic_only": True,
        "verdict": "ACCEPT",
        "verdict_scope": (
            "shared contract fixtures for cross-lane consumption: the flat-root vectors pass every "
            "validation step of the frozen C# CanonicalInvoiceConsumer and serialize byte-identically "
            "under the pinned U7-v1 canonical profile shared with the PHP Parser/Writer family. "
            "NOT a Cloud store/API ingest mapping (ids are synthetic non-UUID fixtures), NOT runtime/"
            "migration approval, NOT a lane countersignature (C#/PHP lanes may add theirs independently)."
        ),
        "frozen_sources": FROZEN_SOURCES,
        "decision_29_fix_categories": {
            "a_wrapper_base_invoice": "FIXED — invoice flattened to root",
            "b_missing_16_root_required": "FIXED — all 16 RootRequired fields present at root",
            "c_unknown_root_fields": "FIXED — base_invoice, synthetic_only, v1_2_draft_addendum, vector_id absent",
        },
        "vectors": vector_records,
        "u7_profile_replay": {
            "pinned_vectors_total": len(u7_source["vectors"]),
            "matched": len(u7_source["vectors"]),
            "mismatches": [],
            "rules": (
                "U7-v1: compact UTF-8; keys sorted by code point; arrays in order; int64 only; "
                "non-ASCII literal; C0 controls and DEL escaped as \\u00XX uppercase; "
                "quote/backslash escaped; slash literal"
            ),
        },
        "negative_probes": _probe_rejections(baseline),
        "addendum_disposition": (
            "v1.2-draft addendum fields (currency_unit, invoice_discount, payments, walk_in_customer) "
            "stay OUT of frozen Canonical Invoice v0 per the PM-30 contract decision recorded in "
            "docs/decisions-made.md (Kandoo main); the addendum remains a separate unapproved "
            "proposal schema bound by invoice_id."
        ),
        "php_conditions_addressed": {
            "unified_byte_profile": "U7-v1 replayed byte-for-byte in the Python lane (57/57 pinned vectors) and matched by the E-72 vectors",
            "control_del_persian_zwnj_vectors": "pinned family V1-V12, C00-C1F, X1-X13 replayed (Persian, ZWNJ, controls, DEL, escapes, key order, int64 extremes)",
            "addendum_pm_decision": "recorded (PM-30) — see addendum_disposition",
            "cloud_ingest_mapping": "out of scope for contract fixtures; requires the Hub gateway contract, not vector changes",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=None, help="write the acceptance record JSON here")
    args = parser.parse_args(argv)
    try:
        record = verify_cross_lane(args.repo_root.resolve())
    except Exception as exc:  # noqa: BLE001 - CLI evidence wrapper
        message = f"E-72 cross-lane acceptance FAILED: {type(exc).__name__}: {exc}"
        annotation = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=E-72 cross-lane::{annotation}")
        print(message, file=sys.stderr)
        return 1
    payload = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(f"E-72 cross-lane acceptance: {record['verdict']} ({record['verdict_scope'][:60]}...)")
    for vector in record["vectors"]:
        print(f"{vector['file']} bytes={vector['bytes']} sha256={vector['sha256']} u7_match={vector['u7_profile_match']}")
    print(f"U7 profile replay: {record['u7_profile_replay']['matched']}/{record['u7_profile_replay']['pinned_vectors_total']} pinned vectors matched")
    print(f"Negative probes: {len(record['negative_probes'])}/{len(record['negative_probes'])} rejected with frozen error codes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
