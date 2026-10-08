"""Shared fixtures for the holoo_spike test suite (co-located per Task
Register). The synthetic fixture DB + the DECLARED mapping used across the
suite live here (SPEC §5 — the mapping is always operator-declared)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent          # tests → holoo_spike → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hs_helpers import build_synthetic_holoo_like_db        # noqa: E402

from capture import S1Service                               # noqa: E402
from holoo_spike import (                                   # noqa: E402
    HolooSelection,
    ROLE_CUSTOMER,
    ROLE_INVOICE_HEADER,
    ROLE_INVOICE_LINES,
    ROLE_OTHER,
    ROLE_PRODUCT,
)


@pytest.fixture()
def source_db(tmp_path):
    """Fresh SYNTHETIC Holoo-shaped source (deterministic content)."""
    return build_synthetic_holoo_like_db(tmp_path / "holoo-fixture.db")


@pytest.fixture()
def source_dir(source_db):
    """The source's parent dir — used by no-side-files proofs."""
    return source_db.parent


@pytest.fixture()
def declared_mapping():
    """A representative declared mapping over the synthetic schema (§5)."""
    return [
        HolooSelection(
            name="invoice_headers",
            role=ROLE_INVOICE_HEADER,
            table="InvoiceHead",
            columns=("InvoiceID", "InvoiceNo", "InvoiceDate",
                     "CustomerRef", "TotalAmount", "Note"),
            order_by=("InvoiceID",),
        ),
        HolooSelection(
            name="invoice_lines",
            role=ROLE_INVOICE_LINES,
            table="InvoiceRows",
            columns=("RowID", "InvoiceID", "ProductCode",
                     "Quantity", "UnitPrice", "LineNote"),
            order_by=("RowID",),
        ),
        HolooSelection(
            name="customers",
            role=ROLE_CUSTOMER,
            table="Customers",
            columns=("CustomerID", "CustomerName", "Phone"),
            order_by=("CustomerID",),
        ),
        HolooSelection(
            name="products",
            role=ROLE_PRODUCT,
            table="Products",
            columns=("ProductCode", "ProductName", "Price", "Preview"),
            order_by=("ProductCode",),
        ),
        HolooSelection(
            name="archive_notes",
            role=ROLE_OTHER,
            table="Archive Notes",
            columns=("NoteID", "NoteText"),
            order_by=("NoteID",),
        ),
    ]


@pytest.fixture()
def s1():
    return S1Service()
