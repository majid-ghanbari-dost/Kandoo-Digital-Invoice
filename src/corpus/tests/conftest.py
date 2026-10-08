"""Shared fixtures for the WP-12.1 corpus test suite (co-located per Task
Register). Everything here is SYNTHETIC pilot material (SPEC-WP121 §2.1)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent          # tests → corpus → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1Service        # noqa: E402
from corpus import (                 # noqa: E402
    MARKING_SYNTHETIC,
    ORIGIN_SYNTHETIC,
    CorpusAssemblyService,
    CorpusStore,
)


@pytest.fixture()
def s1():
    return S1Service()


@pytest.fixture()
def corpus_db(tmp_path):
    return tmp_path / "corpus.db"


@pytest.fixture()
def store(corpus_db, s1):
    with CorpusStore(corpus_db, s1) as s:
        yield s


@pytest.fixture()
def service(store, s1):
    return CorpusAssemblyService(store, s1)
