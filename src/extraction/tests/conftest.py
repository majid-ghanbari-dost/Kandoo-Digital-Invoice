"""Shared fixtures for the extraction-layer test suite (co-located per Task Register)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent          # tests → extraction → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ext_helpers import ExtractionStack                      # noqa: E402
from binding_helpers import BindingStack                     # noqa: E402


@pytest.fixture()
def capture_db(tmp_path):
    return tmp_path / "capture.db"


@pytest.fixture()
def recon_db(tmp_path):
    return tmp_path / "reconstruction.db"


@pytest.fixture()
def extraction_db(tmp_path):
    return tmp_path / "extraction.db"


@pytest.fixture()
def binding_db(tmp_path):
    return tmp_path / "extraction-bindings.db"


@pytest.fixture()
def make_stack(capture_db, recon_db, extraction_db):
    """Factory for (re)opening a stack — used for restart simulations."""
    def _make():
        return ExtractionStack(capture_db, recon_db, extraction_db)
    return _make


@pytest.fixture()
def stack(make_stack):
    s = make_stack()
    yield s
    s.close()


@pytest.fixture()
def make_binding_stack(capture_db, recon_db, extraction_db, binding_db):
    """Factory for (re)opening a WP-3.2 binding stack — used for restart simulations."""
    def _make(with_evidence=True):
        return BindingStack(capture_db, recon_db, extraction_db, binding_db,
                            with_evidence=with_evidence)
    return _make


@pytest.fixture()
def binding_stack(make_binding_stack):
    s = make_binding_stack()
    yield s
    s.close()
