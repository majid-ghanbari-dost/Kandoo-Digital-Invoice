"""Cold-start smoke check for WP-3.2 — runs the evidence-binding path end-to-end
without pytest.

  Capture → Reconstruction (+ WP-2.2 evidence) → verified Read → Extraction
  → Evidence Binding (whole chain verified at bind time)
  → per-field provable walk: field → page span + fingerprint → artifact span → capture S1
  → restart → verified binding read → tamper matrix (forgery / binding / extraction)

Usage: python3 kandoo/src/run_smoke_binding.py /tmp/kandoo-binding-smoke
Creates per-scenario DB file sets: <base>-a-*.db (happy path), <base>-b/c/d-*.db
(tamper scenarios).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import (  # noqa: E402
    CaptureService,
    CaptureStore,
    S1Service,
)

from reconstruction import (  # noqa: E402
    DocumentReadSuccess,
    EV_DOCUMENT_COMPLETED,
    EvidenceReadSuccess,
    EvidenceStore,
    ReconstructCompleted,
    ReconstructionService,
    ReconstructionStore,
    reassemble,
)

from extraction import (  # noqa: E402
    BindingAlreadyExists,
    BindingCompleted,
    BindingLink,
    BindingReadIntegrityFailure,
    BindingReadRefused,
    BindingReadSuccess,
    ExtractionBindingStore,
    ExtractionCompleted,
    ExtractionEvidenceBinder,
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
)

PAGES = [
    b"invoice.number=SMOKE-2026-77\ninvoice.date=2026-10-01\n",
    b"seller.name=Kandoo GmbH\ntotal.gross=129.90\n",
]


class Stack:
    """One opened capture+reconstruction(+evidence)+extraction+binding stack."""

    def __init__(self, base: str):
        self.capture_db = f"{base}-capture.db"
        self.recon_db = f"{base}-recon.db"
        self.evidence_db = f"{base}-evidence.db"
        self.extraction_db = f"{base}-extraction.db"
        self.bindings_db = f"{base}-bindings.db"
        self.reopen()

    def reopen(self):
        self.cstore = CaptureStore(self.capture_db)
        self.cap = CaptureService(self.cstore, S1Service())
        self.rstore = ReconstructionStore(self.recon_db)
        self.estore_ev = EvidenceStore(self.evidence_db, S1Service())
        self.recon = ReconstructionService(self.rstore, self.cap, S1Service(),
                                           evidence=self.estore_ev)
        self.xstore = ExtractionStore(self.extraction_db, S1Service())
        self.ext = ExtractionService(
            self.xstore, self.recon,
            {"reference-delimited-v1": ReferenceDelimitedEngine()}, S1Service())
        self.bstore = ExtractionBindingStore(self.bindings_db, S1Service())
        self.binder = ExtractionEvidenceBinder(
            self.bstore, self.ext, self.recon, self.estore_ev, S1Service())

    def build_and_extract(self, pages, label):
        capture_id = self.cap.ingest(CaptureService.aggregate(pages),
                                     source_label=label).capture_id
        built = self.recon.reconstruct(capture_id)
        assert isinstance(built, ReconstructCompleted), built
        done = self.ext.extract(built.document.document_id, "reference-delimited-v1")
        assert isinstance(done, ExtractionCompleted), done
        return built.document.document_id, done.extraction.extraction_id

    def close(self):
        self.bstore.close()
        self.xstore.close()
        self.estore_ev.close()
        self.rstore.close()
        self.cstore.close()


def main(base: str) -> int:
    # ------------------------------------------------------------------
    # Scenario A — happy path: bind, walk, idempotency, restart, audit
    # ------------------------------------------------------------------
    stack = Stack(f"{base}-a")
    document_id, extraction_id = stack.build_and_extract(PAGES, "smoke-binding")
    print(f"1. extract     -> ExtractionCompleted: 4 verbatim fields "
          f"(extraction_id={extraction_id[:12]}…, document COMPLETED + verified)")

    outcome = stack.binder.bind_extraction(extraction_id)
    assert isinstance(outcome, BindingCompleted), outcome
    b, entries = outcome.binding, outcome.entries
    rec = stack.ext.read_extraction(extraction_id).extraction
    assert b.extraction_record_fingerprint == rec.record_fingerprint
    ev = stack.estore_ev.read_document_evidence(document_id)
    assert isinstance(ev, EvidenceReadSuccess)
    completed = [e for e in ev.events if e.event_type == EV_DOCUMENT_COMPLETED][0]
    assert (b.recon_evidence_seq, b.recon_evidence_record_hash) == \
        (completed.seq, completed.record_hash)
    print(f"2. bind        -> BindingCompleted: whole chain verified at bind time "
          f"(binding_id={b.binding_id[:12]}…, evidence anchor seq={b.recon_evidence_seq})")

    durable_pages = {p.page_index: p for p in stack.rstore.get_pages(document_id)}
    ev_spans = {s["page_index"]: s for s in completed.payload["page_spans"]}
    fields = {f.field_seq: f for f in stack.ext.read_extraction(extraction_id).fields}
    cap_record = stack.cstore.get_record(b.capture_id)
    artifact_bytes = stack.cstore.get_content(cap_record.artifact_ref)
    for entry in entries:
        field = fields[entry.field_seq]
        page = durable_pages[entry.page_index]
        assert bytes(page.content)[entry.byte_start:entry.byte_end].decode(
            field.value_encoding) == field.value_verbatim
        ev_span = ev_spans[entry.page_index]
        assert ev_span["page_fingerprint"] == entry.page_fingerprint
        assert bytes(artifact_bytes)[ev_span["byte_start"]:ev_span["byte_end"]] \
            == bytes(page.content)
    assert b.capture_s1 == completed.payload["capture_s1"]
    first = entries[0]
    print(f"3. walk        -> field 0 ('{first.field_name}' = "
          f"'{fields[first.field_seq].value_verbatim}') proven to page "
          f"{first.page_index} bytes [{first.byte_start},{first.byte_end}) → artifact "
          f"span → capture S1 — all 4 entries machine-checked")

    replay = stack.binder.bind_extraction(extraction_id)
    assert isinstance(replay, BindingAlreadyExists) and \
        replay.binding_id == b.binding_id
    assert stack.binder.bindings_for_document(document_id)[0].binding_id == b.binding_id
    assert isinstance(stack.binder.read_binding("never-bound"), BindingReadRefused)
    print("4. idempotency -> replay returns the SAME binding_id (INV-B-1:1); "
          "unbound extraction reads back refused; enumeration exact")

    stack.close()
    stack.reopen()                                   # full cold restart of every store
    read = stack.binder.read_binding(extraction_id)
    assert isinstance(read, BindingReadSuccess), read
    assert len(read.entries) == b.field_binding_count == 4
    assert stack.binder.verify_chain().valid
    print(f"5. restart     -> binding durable; verified read re-verifies ALL five links "
          f"(verified_at={read.verified_at[:19]}…)")
    stack.close()

    # ------------------------------------------------------------------
    # Scenario B — coherent page forgery (span gate)
    # ------------------------------------------------------------------
    stack = Stack(f"{base}-b")
    document_id, extraction_id = stack.build_and_extract(
        [b"invoice.number=SMOKE-B-0001\n"], "smoke-forgery")
    assert isinstance(stack.binder.bind_extraction(extraction_id), BindingCompleted)
    s1 = S1Service()
    forged = b"invoice.number=EVIL-999999\n"
    stack.rstore._conn.execute(
        "UPDATE document_pages SET content = ?, byte_len = ?, page_fingerprint = ? "
        "WHERE document_id = ? AND page_index = 0",
        (forged, len(forged), s1.compute(forged).s1, document_id))
    pages = stack.rstore.get_pages(document_id)
    stack.rstore._conn.execute(
        "UPDATE reconstruction_documents SET document_fingerprint = ? "
        "WHERE document_id = ?",
        (s1.compute(reassemble(p.content for p in pages)).s1, document_id))
    assert isinstance(stack.recon.read_document(document_id), DocumentReadSuccess)
    outcome = stack.binder.read_binding(extraction_id)
    assert isinstance(outcome, BindingReadIntegrityFailure) and \
        outcome.link == BindingLink.SPAN, outcome
    print("6. forgery     -> coherently forged page passes the frozen verified read, "
          "binding read fails at the SPAN link, nothing delivered")
    stack.close()

    # ------------------------------------------------------------------
    # Scenario C — binding-store tamper
    # ------------------------------------------------------------------
    stack = Stack(f"{base}-c")
    document_id, extraction_id = stack.build_and_extract(
        [b"invoice.number=SMOKE-C-0002\n"], "smoke-bind-tamper")
    assert isinstance(stack.binder.bind_extraction(extraction_id), BindingCompleted)
    stack.bstore._conn.execute(
        "UPDATE extraction_binding_fields SET byte_end = byte_end - 1 "
        "WHERE field_seq = 0")
    outcome = stack.binder.read_binding(extraction_id)
    assert isinstance(outcome, BindingReadIntegrityFailure) and \
        outcome.link == BindingLink.BINDING, outcome
    print("7. tamper(a)   -> binding entry mutated, read fails at the BINDING link "
          "(fingerprint mismatch recomputed inside the read)")
    stack.close()

    # ------------------------------------------------------------------
    # Scenario D — bound-extraction tamper after binding
    # ------------------------------------------------------------------
    stack = Stack(f"{base}-d")
    document_id, extraction_id = stack.build_and_extract(
        [b"invoice.number=SMOKE-D-0003\nseller.name=Delta GmbH\n"], "smoke-ext-tamper")
    assert isinstance(stack.binder.bind_extraction(extraction_id), BindingCompleted)
    stack.xstore._conn.execute(
        "UPDATE extraction_fields SET value_verbatim = 'SMOKE-TAMPERED' "
        "WHERE extraction_id = ? AND field_seq = 0", (extraction_id,))
    outcome = stack.binder.read_binding(extraction_id)
    assert isinstance(outcome, BindingReadIntegrityFailure) and \
        outcome.link == BindingLink.EXTRACTION, outcome
    print("8. tamper(b)   -> bound extraction value mutated AFTER binding, read fails "
          "at the EXTRACTION link (the binding makes the tamper provable)")
    stack.close()

    print("SMOKE OK — Extraction → Evidence Binding is real, durable, tamper-evident, "
          "and per-field traceable to Document/Page + source span + Capture + Evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-binding-smoke"))
