"""Shared helpers for the WP-4.1 normalization tests (unique module name — safe for
combined collection with the capture/reconstruction/extraction suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → normalization → src
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
    ExtractionCompleted,
    ExtractionEngine,
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
)
from normalization import (  # noqa: E402
    NormalizationService,
    NormalizationStore,
    ReferenceNormalizationRulesV1,
)

# Test corpus — key=value pages (the declared reference-engine grammar). Deliberately
# exercises every status path: NFC/trim, decimal (comma + ambiguity), ISO date,
# currency label (text), and a whitespace-only value.
PAGE_TEXTS = [
    b"invoice.number=  INV-2024-001 \ninvoice.date=2026-10-01\n",
    b"seller.name=Caf\xc3\xa9 GmbH\ntotal.gross=1.234,56\ncurrency.label=EUR\n",
    b"quantity= 12,345 \nnotes=   \n",
]


def ingest_pages(capture_service: CaptureService, parts, label="norm-test") -> str:
    """Ingest an aggregated artifact and return the COMPLETED capture_id."""
    content = CaptureService.aggregate(parts)
    outcome = capture_service.ingest(content, source_label=label)
    assert isinstance(outcome, IngestCompleted), outcome
    return outcome.capture_id


class StubEngine(ExtractionEngine):
    """Minimal second engine — proves normalization is engine-independent (same values
    coming from ANY engine normalize identically; no engine module is imported by the
    normalization layer)."""

    def __init__(self, engine_id="stub-alt-v1", schema_version="1"):
        self._engine_id = engine_id
        self._schema_version = schema_version

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def extract_pages(self, pages):
        from extraction import ExtractedField, Provenance, SourceSpan
        fields = []
        seq = 0
        for page in pages:
            content = bytes(page.content)
            start = 0
            while True:
                nl = content.find(b"\n", start)
                line_end = len(content) if nl == -1 else nl
                if line_end > start:
                    eq = content.find(b"=", start, line_end)
                    if eq > start:
                        fields.append(ExtractedField(
                            field_seq=seq,
                            field_name=content[start:eq].decode("utf-8"),
                            value_verbatim=content[eq + 1:line_end].decode("utf-8"),
                            value_encoding="utf-8",
                            provenance=Provenance.EXTRACTED,
                            span=SourceSpan(page.page_index, eq + 1, line_end,
                                            page.page_fingerprint),
                        ))
                        seq += 1
                if nl == -1:
                    break
                start = nl + 1
        return fields


class NormalizationStack:
    """One opened capture+reconstruction(+evidence)+extraction+binding+normalization
    stack sharing the same DB files — the WP-4.1 composition under test."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db, norm_db,
                 with_evidence=True, engines=None):
        self.capture_db = capture_db
        self.recon_db = recon_db
        self.extraction_db = extraction_db
        self.binding_db = binding_db
        self.norm_db = norm_db
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
            engines if engines is not None else
            {"reference-delimited-v1": ReferenceDelimitedEngine(), "stub-alt-v1": StubEngine()},
            S1Service())
        from extraction import ExtractionBindingStore, ExtractionEvidenceBinder
        self.binding_store = ExtractionBindingStore(binding_db, S1Service())
        self.binder = ExtractionEvidenceBinder(
            self.binding_store, self.extraction, self.recon, self.evidence_store,
            S1Service())
        self.norm_store = NormalizationStore(norm_db, S1Service())
        self.norm = NormalizationService(
            self.norm_store, self.extraction,
            {"kandoo-norm-v1": ReferenceNormalizationRulesV1()}, S1Service())

    def build_document(self, parts=None, label="norm-test") -> str:
        """Ingest → reconstruct → return the COMPLETED document_id."""
        parts = PAGE_TEXTS if parts is None else parts
        capture_id = ingest_pages(self.capture, parts, label)
        built = self.recon.reconstruct(capture_id)
        assert isinstance(built, ReconstructCompleted), built
        return built.document.document_id

    def build_and_extract(self, parts=None, engine_id="reference-delimited-v1",
                          label="norm-test") -> str:
        """Ingest → reconstruct → extract → return the extraction_id."""
        document_id = self.build_document(parts, label)
        done = self.extraction.extract(document_id, engine_id)
        assert isinstance(done, ExtractionCompleted), done
        return done.extraction.extraction_id

    def close(self):
        self.norm_store.close()
        self.binding_store.close()
        self.extraction_store.close()
        if self.evidence_store is not None:
            self.evidence_store.close()
        self.recon_store.close()
        self.capture_store.close()
