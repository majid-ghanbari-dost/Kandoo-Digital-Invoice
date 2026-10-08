"""Shared helpers for the WP-2.2 evidence tests (unique module name — safe for combined
collection with the capture + WP-2.1 suites under pytest rootdir mode)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → reconstruction → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import CaptureService, CaptureStore, S1Service  # noqa: E402
from reconstruction import (  # noqa: E402
    EvidenceStore,
    ReconstructCompleted,
    ReconstructionService,
    ReconstructionStore,
)
from helpers import ingest_parts  # reuse the WP-2.1 helper (same directory)


class EvidenceStack:
    """One opened capture+reconstruction+evidence stack sharing the same DB files."""

    def __init__(self, capture_db, recon_db, evidence_db):
        self.capture_db = capture_db
        self.recon_db = recon_db
        self.evidence_db = evidence_db
        self.capture_store = CaptureStore(capture_db)
        self.capture = CaptureService(self.capture_store, S1Service())
        self.recon_store = ReconstructionStore(recon_db)
        self.evidence_store = EvidenceStore(evidence_db, S1Service())
        self.recon = ReconstructionService(self.recon_store, self.capture, S1Service(),
                                           evidence=self.evidence_store)

    def close(self):
        self.recon_store.close()
        self.capture_store.close()
        self.evidence_store.close()

    def reopen(self):
        """Close and reopen all three stores on the SAME files — restart simulation."""
        self.close()
        self.__init__(self.capture_db, self.recon_db, self.evidence_db)


def build_completed(stack, parts, label="ev-test"):
    """Ingest an aggregated artifact, reconstruct it, return (capture_id, document_id)."""
    capture_id = ingest_parts(stack.capture, parts, label)
    outcome = stack.recon.reconstruct(capture_id)
    assert isinstance(outcome, ReconstructCompleted), outcome
    return capture_id, outcome.document.document_id
