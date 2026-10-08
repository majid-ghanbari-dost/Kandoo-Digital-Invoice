"""Shared fixtures for the derivation-layer test suite (co-located per Task Register)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent          # tests → derivation → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from deriv_helpers import DerivationStack                     # noqa: E402


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
def norm_db(tmp_path):
    return tmp_path / "normalization.db"


@pytest.fixture()
def deriv_db(tmp_path):
    return tmp_path / "derivation.db"


@pytest.fixture()
def make_stack(capture_db, recon_db, extraction_db, binding_db, norm_db, deriv_db):
    """Factory for (re)opening a full WP-4.2 stack — used for restart simulations."""
    def _make(**kwargs):
        return DerivationStack(capture_db, recon_db, extraction_db, binding_db,
                               norm_db, deriv_db, **kwargs)
    return _make


@pytest.fixture()
def stack(make_stack):
    s = make_stack()
    yield s
    s.close()
