"""Shared fixtures for the reconstruction-layer test suite (co-located per Task Register)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent          # tests → reconstruction → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from helpers import Stack                                    # noqa: E402


@pytest.fixture()
def capture_db(tmp_path):
    return tmp_path / "capture.db"


@pytest.fixture()
def recon_db(tmp_path):
    return tmp_path / "reconstruction.db"


@pytest.fixture()
def make_stack(capture_db, recon_db):
    """Factory for (re)opening a stack — used for restart simulations."""
    def _make():
        return Stack(capture_db, recon_db)
    return _make


@pytest.fixture()
def stack(make_stack):
    s = make_stack()
    yield s
    s.close()
