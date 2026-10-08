"""Shared helpers for the extraction-layer tests (unique module name — safe for
combined collection with the capture/reconstruction suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → extraction → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import CaptureService, CaptureStore, IngestCompleted, S1Service  # noqa: E402
from reconstruction import (  # noqa: E402
    ReconstructCompleted,
    ReconstructionService,
    ReconstructionStore,
)
from extraction import (  # noqa: E402
    ExtractionEngine,
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
)

# Test corpus — key=value pages (the declared reference-engine grammar).
PAGE_TEXTS = [
    b"invoice.number=INV-2024-001\ninvoice.date=2026-10-01\n",
    b"seller.name=Acme GmbH\ntotal.gross=129.90\ncurrency.label=EUR\n",
    b"notes=*\n",
]


def ingest_pages(capture_service: CaptureService, parts, label="ext-test") -> str:
    """Ingest an aggregated artifact and return the COMPLETED capture_id."""
    content = CaptureService.aggregate(parts)
    outcome = capture_service.ingest(content, source_label=label)
    assert isinstance(outcome, IngestCompleted), outcome
    return outcome.capture_id


class ExtractionStack:
    """One opened capture+reconstruction+extraction stack sharing the same DB files."""

    def __init__(self, capture_db, recon_db, extraction_db):
        self.capture_db = capture_db
        self.recon_db = recon_db
        self.extraction_db = extraction_db
        self.capture_store = CaptureStore(capture_db)
        self.capture = CaptureService(self.capture_store, S1Service())
        self.recon_store = ReconstructionStore(recon_db)
        self.recon = ReconstructionService(self.recon_store, self.capture, S1Service())
        self.extraction_store = ExtractionStore(extraction_db, S1Service())
        self.extraction = ExtractionService(
            self.extraction_store, self.recon,
            {"reference-delimited-v1": ReferenceDelimitedEngine()},
            S1Service())

    def build_document(self, parts=None, label="ext-test") -> str:
        """Ingest → reconstruct → return the COMPLETED document_id."""
        parts = PAGE_TEXTS if parts is None else parts
        capture_id = ingest_pages(self.capture, parts, label)
        built = self.recon.reconstruct(capture_id)
        assert isinstance(built, ReconstructCompleted), built
        return built.document.document_id

    def close(self):
        self.extraction_store.close()
        self.recon_store.close()
        self.capture_store.close()


class StubEngine(ExtractionEngine):
    """Test engine — configurable output; used to prove the pipeline is engine-agnostic
    and that engine-contract violations fail closed."""

    def __init__(self, engine_id="stub-alt-v1", schema_version="1", fields=None,
                 error=None):
        self._engine_id = engine_id
        self._schema_version = schema_version
        self._fields = fields if fields is not None else []
        self._error = error

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def extract_pages(self, pages):
        if self._error is not None:
            raise self._error
        return list(self._fields)
