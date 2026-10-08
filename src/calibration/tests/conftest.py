"""Shared fixtures for the WP-12.2 calibration test suite. Corpus material
comes from the WP-12.1 SYNTHETIC templates (SPEC-WP121 §2.1) — clearly-marked
pilot input only."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1Service           # noqa: E402
from corpus import (                    # noqa: E402
    CorpusAssemblyService,
    CorpusReadSuccess,
    CorpusStore,
)
from calibration import (               # noqa: E402
    CalibrationRunService,
    RunConfig,
)


@pytest.fixture()
def s1():
    return S1Service()


@pytest.fixture()
def corpus_service(tmp_path, s1):
    with CorpusStore(tmp_path / "corpus.db", s1) as store:
        yield CorpusAssemblyService(store, s1)


@pytest.fixture()
def clean_corpus(corpus_service):
    """A clean-template corpus — the ACCEPTED path."""
    outcome = corpus_service.assemble("kv-invoice-clean-v1", 3, 11)
    read = corpus_service.read_corpus(outcome.manifest.corpus_version_id)
    assert isinstance(read, CorpusReadSuccess)
    return outcome.manifest, read


@pytest.fixture()
def rounding_corpus(corpus_service):
    """A rounding-probe corpus — the D-08 sweep surface."""
    outcome = corpus_service.assemble("kv-invoice-rounding-probe-v1", 6, 22)
    read = corpus_service.read_corpus(outcome.manifest.corpus_version_id)
    return outcome.manifest, read


@pytest.fixture()
def review_corpus(corpus_service):
    """A review-probe corpus — the uncertainty path + ABSENT labels."""
    outcome = corpus_service.assemble("kv-invoice-review-probe-v1", 2, 33)
    read = corpus_service.read_corpus(outcome.manifest.corpus_version_id)
    return outcome.manifest, read


@pytest.fixture()
def run_service(tmp_path, s1):
    def factory(name="ws"):
        return CalibrationRunService(tmp_path / name, s1)
    return factory


@pytest.fixture()
def run_config():
    def factory(manifest):
        return RunConfig(corpus_version_id=manifest.corpus_version_id)
    return factory
