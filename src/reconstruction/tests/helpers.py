"""Shared helpers for the reconstruction-layer tests (unique module name — safe for
combined collection with the capture suite under pytest rootdir mode)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → reconstruction → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import CaptureService, CaptureStore, IngestCompleted, S1Service  # noqa: E402
from reconstruction import ReconstructionService, ReconstructionStore         # noqa: E402


def ingest_parts(capture_service: CaptureService, parts, label="test") -> str:
    """Ingest an aggregated artifact and return the COMPLETED capture_id."""
    content = CaptureService.aggregate(parts)
    outcome = capture_service.ingest(content, source_label=label)
    assert isinstance(outcome, IngestCompleted), outcome
    return outcome.capture_id


class Stack:
    """One opened capture+reconstruction stack sharing the same DB files."""

    def __init__(self, capture_db, recon_db):
        self.capture_db = capture_db
        self.recon_db = recon_db
        self.capture_store = CaptureStore(capture_db)
        self.capture = CaptureService(self.capture_store, S1Service())
        self.recon_store = ReconstructionStore(recon_db)
        self.recon = ReconstructionService(self.recon_store, self.capture, S1Service())

    def close(self):
        self.recon_store.close()
        self.capture_store.close()
