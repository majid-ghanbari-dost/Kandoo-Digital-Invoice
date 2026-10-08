"""Shared test fixtures for the capture-layer test suite (co-located per Task Register)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent   # tests → capture → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import CaptureService, CaptureStore, S1Service  # noqa: E402


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "capture.db"


@pytest.fixture()
def store(db_path):
    s = CaptureStore(db_path)
    yield s
    s.close()


@pytest.fixture()
def service(store):
    return CaptureService(store, S1Service())


@pytest.fixture()
def fresh_service(db_path):
    """A brand-new store+service pair — used for restart simulations."""
    def _make():
        st = CaptureStore(db_path)
        return st, CaptureService(st, S1Service())
    return _make
