"""Shared helpers for the WP-3.2 evidence-binding tests (unique module name — safe for
combined collection with the capture/reconstruction/extraction suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → extraction → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import CaptureService, CaptureStore, IngestCompleted, S1Service  # noqa: E402
from reconstruction import (  # noqa: E402
    EvidenceStore,
    ReconstructCompleted,
    ReconstructionService,
    ReconstructionStore,
)
from extraction import (  # noqa: E402
    ExtractionEvidenceBinder,
    ExtractionBindingStore,
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
)
from ext_helpers import PAGE_TEXTS, ingest_pages  # noqa: E402


class BindingStack:
    """One opened capture+reconstruction(+evidence)+extraction+binding stack sharing the
    same DB files — the WP-3.2 composition under test."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db,
                 with_evidence=True):
        self.capture_db = capture_db
        self.recon_db = recon_db
        self.extraction_db = extraction_db
        self.binding_db = binding_db
        self.capture_store = CaptureStore(capture_db)
        self.capture = CaptureService(self.capture_store, S1Service())
        self.recon_store = ReconstructionStore(recon_db)
        self.evidence_store = EvidenceStore(str(recon_db) + ".evidence.db", S1Service()) \
            if with_evidence else None
        self.recon = ReconstructionService(self.recon_store, self.capture, S1Service(),
                                           evidence=self.evidence_store)
        self.extraction_store = ExtractionStore(extraction_db, S1Service())
        self.extraction = ExtractionService(
            self.extraction_store, self.recon,
            {"reference-delimited-v1": ReferenceDelimitedEngine()},
            S1Service())
        self.binding_store = ExtractionBindingStore(binding_db, S1Service())
        self.binder = ExtractionEvidenceBinder(
            self.binding_store, self.extraction, self.recon, self.evidence_store,
            S1Service())

    def build_document(self, parts=None, label="bind-test") -> str:
        """Ingest → reconstruct → return the COMPLETED document_id."""
        parts = PAGE_TEXTS if parts is None else parts
        capture_id = ingest_pages(self.capture, parts, label)
        built = self.recon.reconstruct(capture_id)
        assert isinstance(built, ReconstructCompleted), built
        return built.document.document_id

    def build_and_extract(self, parts=None, engine_id="reference-delimited-v1",
                          label="bind-test") -> str:
        """Ingest → reconstruct → extract → return the extraction_id."""
        from extraction import ExtractionCompleted                 # local import OK
        document_id = self.build_document(parts, label)
        done = self.extraction.extract(document_id, engine_id)
        assert isinstance(done, ExtractionCompleted), done
        return done.extraction.extraction_id

    def close(self):
        self.binding_store.close()
        self.extraction_store.close()
        if self.evidence_store is not None:
            self.evidence_store.close()
        self.recon_store.close()
        self.capture_store.close()
