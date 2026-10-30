from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from image_extraction_adapter.pipeline_v0 import extract_pipeline_v0


ROOT = Path(__file__).resolve().parents[1]
UNKNOWN_LAYOUT_FIXTURE = ROOT / "tests" / "fixtures" / "real" / "29.png"


def test_unknown_layout_routes_to_review_without_extracted_candidate() -> None:
    unknown_layout = SimpleNamespace(
        status="REVIEW",
        geometry=None,
        row_count=None,
        reason="unknown/unregistered table layout",
    )
    context = {
        "mode": "B",
        "invoice_id": "e31-synthetic-unknown-layout",
        "display_number": "E31-UNKNOWN",
        "operation_id": "e31-synthetic-operation",
        "device_id": "e31-synthetic-device",
        "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
        "store_id": "e31-synthetic-store",
        "customer": {
            "phone": "+15551234567",
            "phone_status": "claimed",
            "phone_provenance": "captured",
        },
        "product_names": [
            "Synthetic unknown layout item 1",
            "Synthetic unknown layout item 2",
            "Synthetic unknown layout item 3",
            "Synthetic unknown layout item 4",
        ],
        "product_name_provenance": ["untrusted"] * 4,
    }

    with patch(
        "image_extraction_adapter.pipeline_v0.detect_layout_safe",
        return_value=unknown_layout,
    ):
        result = extract_pipeline_v0(UNKNOWN_LAYOUT_FIXTURE, canonical_context=context)

    assert result.status == "REVIEW"
    assert result.layout_status == "REVIEW"
    assert result.canonical_invoice is None
    assert result.canonical_valid is None
    assert result.cell_results == ()
    assert result.status != "AUTO_CANDIDATE"
