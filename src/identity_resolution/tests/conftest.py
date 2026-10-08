"""Shared fixtures for the identity-resolution test suite (co-located per
Task Register)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent          # tests → identity_resolution → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ir_helpers import IdentityResolutionStack               # noqa: E402


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
def val_db(tmp_path):
    return tmp_path / "validation.db"


@pytest.fixture()
def vsm_db(tmp_path):
    return tmp_path / "validation-domain.db"


@pytest.fixture()
def identity_db(tmp_path):
    return tmp_path / "identity-resolution.db"


@pytest.fixture()
def make_stack(capture_db, recon_db, extraction_db, binding_db, norm_db,
               deriv_db, val_db, vsm_db, identity_db):
    """Factory for (re)opening a full WP-7.1 stack — used for restart
    simulations."""
    def _make(**kwargs):
        return IdentityResolutionStack(capture_db, recon_db, extraction_db,
                                       binding_db, norm_db, deriv_db, val_db,
                                       vsm_db, identity_db, **kwargs)
    return _make


@pytest.fixture()
def stack(make_stack):
    s = make_stack()
    yield s
    s.close()
