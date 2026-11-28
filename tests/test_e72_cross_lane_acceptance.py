"""CI-permanent acceptance gate for the E-72 cross-lane record (PY-B, PM-36).

Pins (a) the Python U7-v1 port against all 57 C-66 pinned canonical vectors,
(b) the frozen-consumer rule trace on both flat-root E-72 round-3 vectors,
(c) the rejection probes with the exact frozen error codes, and (d) byte
stability of the published acceptance record. All vectors are synthetic.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from verify_e72_cross_lane import (  # noqa: E402
    CONSUMER_RULE_GROUPS,
    ConsumerError,
    consume_for_review,
    parse_strict_json,
    u7_serialize,
    verify_cross_lane,
)

VECTOR_DIR = ROOT / "tests" / "golden" / "e72"
U7_VECTORS_PATH = VECTOR_DIR / "u7-canonical-vectors-v1.json"
RECORD_PATH = VECTOR_DIR / "cross-lane-acceptance.json"


def test_u7_port_reproduces_all_57_pinned_csharp_vectors():
    source = json.loads(U7_VECTORS_PATH.read_bytes().decode("utf-8"))
    assert source["vectors"] and len(source["vectors"]) == 57
    for vector in source["vectors"]:
        document = parse_strict_json(vector["input_json"])
        canonical = u7_serialize(document)
        assert canonical.hex() == vector["canonical_hex"], vector["id"]
        assert hashlib.sha256(canonical).hexdigest() == vector["sha256"], vector["id"]


def test_u7_profile_edge_rules():
    # C0 controls and DEL: uppercase \\u00XX, never short escapes or raw bytes.
    assert u7_serialize({"x": "\b\f\n\r\t\x1f\x7f"}) == (
        b'{"x":"\\u0008\\u000C\\u000A\\u000D\\u0009\\u001F\\u007F"}'
    )
    # Non-ASCII literal; slash literal; quote/backslash escaped.
    assert u7_serialize({"\u06a9": "/"}) == '{"\u06a9":"/"}'.encode("utf-8")
    assert u7_serialize({"q": "\"\\"}) == b'{"q":"\\"\\\\"}'
    # Key order: code point / unsigned UTF-8 (NOT locale order).
    assert u7_serialize({"z": 0, "a": 1, "\u0643": 2, "\u06a9": 3}) == (
        '{"a":1,"z":0,"\u0643":2,"\u06a9":3}'.encode("utf-8")
    )


def test_r3_vectors_pass_every_frozen_consumer_rule_group():
    for name in (
        "canonical-invoice-v1-2-draft-vector.json",
        "canonical-invoice-v1-2-draft-vector-r3.json",
    ):
        text = (VECTOR_DIR / name).read_bytes().decode("utf-8")
        trace = verify_cross_lane(ROOT)  # full record raises on any rule failure
        vector_record = next(item for item in record_vectors(trace) if item["file"] == name)
        assert set(vector_record["consumer_rules"]) == {rule for rule, _ in CONSUMER_RULE_GROUPS}
        assert all(status == "PASS" for status in vector_record["consumer_rules"].values())
        assert vector_record["u7_profile_match"] is True


def record_vectors(record: dict) -> list[dict]:
    return record["vectors"]


def test_acceptance_record_is_byte_stable_and_verdict_is_scoped():
    record = verify_cross_lane(ROOT)
    assert record["verdict"] == "ACCEPT"
    assert "NOT a lane countersignature" in record["verdict_scope"]
    assert record["synthetic_only"] is True
    assert record["u7_profile_replay"]["matched"] == 57
    assert record["u7_profile_replay"]["mismatches"] == []
    # Published golden must match the regenerated record byte-for-byte.
    golden = json.loads(RECORD_PATH.read_bytes().decode("utf-8"))
    assert json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=False) + "\n" == (
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    )


def test_wrapper_root_rejected_with_decision_29_error_line():
    try:
        consume_for_review('{"base_invoice": {}, "synthetic_only": true, "v1_2_draft_addendum": {}, "vector_id": "x"}')
    except ConsumerError as exc:
        assert exc.code == "SCHEMA_VALIDATION_FAILED"
        assert exc.message == "Unexpected field: base_invoice."
    else:
        raise AssertionError("wrapper root was not rejected")


def test_probes_keep_frozen_error_codes():
    record = verify_cross_lane(ROOT)
    codes = {probe["probe"]: probe["observed_error_code"] for probe in record["negative_probes"]}
    assert codes["wrapper_root_base_invoice"] == "SCHEMA_VALIDATION_FAILED"
    assert codes["empty_root_missing_fields"] == "REQUIRED_FIELD_MISSING"
    assert codes["line_item_quantity_alias"] == "SCHEMA_VALIDATION_FAILED"
    assert codes["display_number_before_issue"] == "DISPLAY_NUMBER_BEFORE_ISSUE"
    assert codes["issued_hash_on_draft"] == "SCHEMA_VALIDATION_FAILED"
    assert codes["float_subtotal"] == "AMOUNT_NOT_INTEGER"
    assert codes["short_public_token"] == "SCHEMA_VALIDATION_FAILED"
    for probe in record["negative_probes"]:
        assert probe["result"] == "REJECTED_AS_FROZEN"
