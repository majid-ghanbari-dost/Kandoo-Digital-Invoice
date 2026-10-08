"""WP-3.2 boundary — structural-only payload (OD-B7), no write path to frozen layers,
exact model field sets, and no UPDATE/DELETE anywhere in the binding API (AC-3.2.4)."""
from dataclasses import fields as dataclass_fields
from inspect import isfunction, ismethod
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extraction import (
    BindingCompleted,
    BindingFieldEntry,
    BindingReadSuccess,
    ExtractionBindingRecord,
    canonical_binding_bytes,
)

ENTRY_FIELDS = {"field_seq", "field_name", "page_index", "byte_start", "byte_end",
                "page_fingerprint"}
RECORD_FIELDS = {"binding_id", "seq", "extraction_id", "document_id", "capture_id",
                 "capture_s1", "capture_s1_algorithm_id",
                 "extraction_record_fingerprint",
                 "extraction_fingerprint_algorithm_id", "recon_evidence_seq",
                 "recon_evidence_record_hash", "field_binding_count", "created_at",
                 "binding_fingerprint", "binding_fingerprint_algorithm_id",
                 "prev_binding_hash", "binding_hash"}

BINDING_DB_COLUMNS = {
    "extraction_bindings": {"seq", "binding_id", "extraction_id", "document_id",
                            "capture_id", "capture_s1", "capture_s1_algorithm_id",
                            "extraction_record_fingerprint",
                            "extraction_fingerprint_algorithm_id", "recon_evidence_seq",
                            "recon_evidence_record_hash", "field_binding_count",
                            "created_at", "binding_fingerprint",
                            "binding_fingerprint_algorithm_id", "prev_binding_hash",
                            "binding_hash"},
    "extraction_binding_fields": {"binding_id", "field_seq", "field_name", "page_index",
                                  "byte_start", "byte_end", "page_fingerprint"},
}


def _bind(binding_stack, parts=None):
    extraction_id = binding_stack.build_and_extract(parts)
    outcome = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(outcome, BindingCompleted), outcome
    return extraction_id, outcome


def test_binding_record_field_sets_are_exact():
    assert {f.name for f in dataclass_fields(ExtractionBindingRecord)} == RECORD_FIELDS
    assert {f.name for f in dataclass_fields(BindingFieldEntry)} == ENTRY_FIELDS


def test_binding_payload_carries_no_values(binding_stack):
    """OD-B7: no extracted value ever enters the binding record, its entries, the
    canonical bytes, or the durable DB rows. (Values chosen to never collide with
    timestamps/ids/fingerprints substrings.)"""
    values = ["INV-2024-001", "Acme GmbH", "129.90", "EUR", "Zz-Value-Marker"]
    parts = [b"invoice.number=INV-2024-001\nseller.name=Acme GmbH\n",
             b"total.gross=129.90\ncurrency.code=EUR\nnote=Zz-Value-Marker\n"]
    extraction_id, done = _bind(binding_stack, parts)
    b = done.binding
    # dataclasses: the only free-text field is the engine's key vocabulary
    for entry in done.entries:
        payload = vars(entry).copy()
        payload.pop("field_name")          # the engine-declared KEY — not a value
        for v in values:
            assert v not in map(str, payload.values()), (entry, v)
    # canonical fingerprinted bytes contain none of the values
    canonical = canonical_binding_bytes(b, done.entries)
    for v in values:
        assert v.encode("utf-8") not in canonical
    # durable rows contain none of the values
    rows = binding_stack.binding_store._conn.execute(
        "SELECT * FROM extraction_binding_fields").fetchall()
    for row in rows:
        for v in values:
            assert v not in str(tuple(row))
    rows = binding_stack.binding_store._conn.execute(
        "SELECT * FROM extraction_bindings").fetchall()
    for row in rows:
        for v in values:
            assert v not in str(tuple(row))


def test_binding_store_schema_has_no_value_column(binding_stack):
    for table, expected in BINDING_DB_COLUMNS.items():
        cols = {r["name"] for r in binding_stack.binding_store._conn.execute(
            f"PRAGMA table_info({table})").fetchall()}
        assert cols == expected, (table, cols)


def test_read_success_outcome_shape_is_exact(binding_stack):
    extraction_id, done = _bind(binding_stack)
    read = binding_stack.binder.read_binding(extraction_id)
    assert isinstance(read, BindingReadSuccess)
    assert {f.name for f in dataclass_fields(read)} == {"binding", "entries",
                                                        "verified_at"}


def test_no_update_or_delete_path_in_binding_api():
    """The append-only discipline is structural: no public update/delete/drop/truncate
    method exists on the store or the binder."""
    from extraction import ExtractionBindingStore, ExtractionEvidenceBinder
    forbidden = ("update", "delete", "drop", "truncate", "rewrite", "amend")
    for cls in (ExtractionBindingStore, ExtractionEvidenceBinder):
        for name in dir(cls):
            if name.startswith("_"):
                continue
            attr = getattr(cls, name)
            if (isfunction(attr) or ismethod(attr)):
                lowered = name.lower()
                assert not any(f in lowered for f in forbidden), (cls.__name__, name)


def test_binding_operations_leave_frozen_layers_verified(binding_stack):
    """After binds + reads, every frozen layer still verifies through its OWN sanctioned
    path — the binding layer wrote nothing anywhere but its own store file."""
    parts = [b"invoice.number=INV-2024-001\n", b"seller.name=Acme GmbH\n"]
    extraction_id, done = _bind(binding_stack, parts)
    document_id = done.binding.document_id
    capture_id = done.binding.capture_id
    # more binding traffic: reads, replay, enumeration
    assert isinstance(binding_stack.binder.read_binding(extraction_id),
                      BindingReadSuccess)
    binding_stack.binder.bindings_for_document(document_id)
    binding_stack.binder.verify_chain()
    # frozen layers verify through their own VOR paths:
    from capture import ReadSuccess as CaptureReadSuccess
    from reconstruction import DocumentReadSuccess
    assert isinstance(binding_stack.recon.read_document(document_id),
                      DocumentReadSuccess)                     # WP-2.1
    assert binding_stack.evidence_store.verify_chain().valid   # WP-2.2
    assert isinstance(binding_stack.capture.read_evidence(capture_id),
                      CaptureReadSuccess)                      # WP-1.1
    from extraction import BindingAlreadyExists, ExtractionReadSuccess
    replay = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(replay, BindingAlreadyExists)            # INV-B-1:1 holds
    assert isinstance(binding_stack.extraction.read_extraction(extraction_id),
                      ExtractionReadSuccess)                   # WP-3.1
