import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipeline import PipelineWorkspace
from validation import ReferenceValidationRulesV1


@pytest.fixture
def rules():
    # Test-only declarations, NOT deployment defaults or ratified thresholds.
    return dict(ReferenceValidationRulesV1(tolerance="0.02", precision=2, mode="HALF_UP"))


@pytest.fixture
def declaration():
    return dict(
        source_label="synthetic-pipeline-test", declared_origin="HOLOO_CAPTURE",
        identity_binding={"INVOICE_NUMBER": "invoice.number",
                          "INVOICE_DATE": "invoice.date", "INVOICE_TOTAL": "total.net"},
        line_binding={0: {"LINE_QUANTITY": "line.0.quantity",
                          "LINE_UNIT_PRICE": "line.0.unit_price",
                          "LINE_TOTAL": "line.0.total"}},
        ruleset_id="pipeline-test-declared", ruleset_version="1",
    )


@pytest.fixture
def pages():
    return [b"invoice.number=PIPE-001\ninvoice.date=2026-10-01\n"
            b"total.net=1000.00\ntax.amount=80\n"
            b"line.0.quantity=2\nline.0.unit_price=500\nline.0.total=1000\n"]


@pytest.fixture
def workspace(tmp_path, rules):
    with PipelineWorkspace(tmp_path, validation_rules=rules) as workspace:
        yield workspace
