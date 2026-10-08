"""WP-3.2 durability — restart safety, whole-log chain audit (tail deletion / forgery),
zero-residue on refused binds, and exactness of concurrent appends (AC-3.2.4)."""
from pathlib import Path
import sys
import threading

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extraction import (
    BindingCompleted,
    BindingReadSuccess,
    ExtractionEvidenceBinder,
    ExtractionBindingStore,
)
from capture import CaptureService, CaptureStore, S1Service
from reconstruction import (
    EvidenceStore,
    ReconstructionService,
    ReconstructionStore,
)


def test_restart_preserves_bindings_and_reverifies_everything(binding_stack):
    extraction_id = binding_stack.build_and_extract()
    outcome = binding_stack.binder.bind_extraction(extraction_id)
    assert isinstance(outcome, BindingCompleted)
    binding_id = outcome.binding.binding_id
    document_id = outcome.binding.document_id

    binding_stack.close()                      # full cold restart of every store

    # reopen the same DB files fresh
    capture_store = CaptureStore(binding_stack.capture_db)
    capture = CaptureService(capture_store, S1Service())
    recon_store = ReconstructionStore(binding_stack.recon_db)
    evidence = EvidenceStore(str(binding_stack.recon_db) + ".evidence.db", S1Service())
    recon = ReconstructionService(recon_store, capture, S1Service(), evidence=evidence)
    from extraction import ExtractionService, ExtractionStore, ReferenceDelimitedEngine
    extraction_store = ExtractionStore(binding_stack.extraction_db, S1Service())
    extraction = ExtractionService(extraction_store, recon,
                                   {"reference-delimited-v1": ReferenceDelimitedEngine()},
                                   S1Service())
    binding_store = ExtractionBindingStore(binding_stack.binding_db, S1Service())
    binder = ExtractionEvidenceBinder(binding_store, extraction, recon, evidence,
                                      S1Service())
    try:
        read = binder.read_binding(extraction_id)
        assert isinstance(read, BindingReadSuccess), read
        assert read.binding.binding_id == binding_id
        assert len(read.entries) == read.binding.field_binding_count
        refs = binder.bindings_for_document(document_id)
        assert len(refs) == 1 and refs[0].binding_id == binding_id
        report = binder.verify_chain()
        assert report.valid and report.records == 1
    finally:
        binding_store.close()
        extraction_store.close()
        evidence.close()
        recon_store.close()
        capture_store.close()


def test_chain_audit_detects_tail_deletion(binding_stack):
    x1 = binding_stack.build_and_extract([b"a=1\n"], label="d1")
    x2 = binding_stack.build_and_extract([b"b=2\n"], label="d2")
    assert binding_stack.binder.bind_extraction(x1).binding.seq == 1
    assert binding_stack.binder.bind_extraction(x2).binding.seq == 2
    assert binding_stack.binder.verify_chain().valid

    binding_stack.binding_store._conn.execute(
        "DELETE FROM extraction_bindings WHERE seq = 2")
    binding_stack.binding_store._conn.execute(
        "DELETE FROM extraction_binding_fields WHERE binding_id NOT IN "
        "(SELECT binding_id FROM extraction_bindings)")
    report = binding_stack.binder.verify_chain()
    assert not report.valid
    assert report.failure_seq == 2 or report.reason     # truncation surfaced


def test_chain_audit_detects_mid_log_forgery(binding_stack):
    x1 = binding_stack.build_and_extract([b"a=1\n"], label="d1")
    x2 = binding_stack.build_and_extract([b"b=2\n"], label="d2")
    assert binding_stack.binder.bind_extraction(x1).binding.seq == 1
    assert binding_stack.binder.bind_extraction(x2).binding.seq == 2
    binding_stack.binding_store._conn.execute(
        "UPDATE extraction_bindings SET recon_evidence_record_hash = "
        "'f' * 64 WHERE seq = 1")
    report = binding_stack.binder.verify_chain()
    assert not report.valid
    assert report.failure_seq == 1


def test_zero_residue_after_refused_bind(binding_stack):
    extraction_id = binding_stack.build_and_extract()
    binding_stack.extraction_store._conn.execute(
        "UPDATE extraction_fields SET value_verbatim = 'BROKEN' "
        "WHERE extraction_id = ?", (extraction_id,))
    outcome = binding_stack.binder.bind_extraction(extraction_id)
    assert type(outcome).__name__ == "BindingSourceIntegrityFailure"
    conn = binding_stack.binding_store._conn
    assert conn.execute("SELECT COUNT(*) AS n FROM extraction_bindings").fetchone()["n"] == 0
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM extraction_binding_fields").fetchone()["n"] == 0
    report = binding_stack.binder.verify_chain()
    assert report.valid and report.records == 0          # empty log is the valid state


def test_concurrent_bind_appends_are_exact(binding_stack):
    """8 threads, independent connections, 8 pre-extracted extractions: the log ends
    with seqs 1..8 contiguous and the chain verifies — BEGIN IMMEDIATE serialization."""
    from extraction import ExtractionCompleted, ReferenceDelimitedEngine
    pairs = []
    for i in range(4):
        doc = binding_stack.build_document(
            [f"doc{i}.field=doc{i}-value\n".encode(), b"seller.name=Shared GmbH\n"],
            label=f"conc-{i}")
        pairs.append(doc)
    # 8 distinct (doc, engine) extraction records: 4 docs × 2 engines, single-threaded
    binding_stack.extraction._engines["alt-delimited-v1"] = \
        ReferenceDelimitedEngine(engine_id="alt-delimited-v1")
    ids = []
    for doc in pairs:
        for engine_id in ("reference-delimited-v1", "alt-delimited-v1"):
            done = binding_stack.extraction.extract(doc, engine_id)
            assert isinstance(done, ExtractionCompleted), done
            ids.append((doc, engine_id, done.extraction.extraction_id))
    assert len(ids) == 8 and len({i[2] for i in ids}) == 8

    n = 8
    barrier = threading.Barrier(n)
    outcomes = [None] * n
    errors = []

    def worker(i):
        try:
            # independent connections per caller (house concurrency pattern)
            cstore = CaptureStore(binding_stack.capture_db)
            rstore = ReconstructionStore(binding_stack.recon_db)
            evidence = EvidenceStore(str(binding_stack.recon_db) + ".evidence.db",
                                     S1Service())
            recon = ReconstructionService(rstore, CaptureService(cstore, S1Service()),
                                          S1Service(), evidence=evidence)
            from extraction import ExtractionService, ExtractionStore, \
                ReferenceDelimitedEngine
            estore = ExtractionStore(binding_stack.extraction_db, S1Service())
            esvc = ExtractionService(estore, recon,
                                     {"reference-delimited-v1":
                                      ReferenceDelimitedEngine(),
                                      "alt-delimited-v1":
                                      ReferenceDelimitedEngine(engine_id="alt-delimited-v1")},
                                     S1Service())
            bstore = ExtractionBindingStore(binding_stack.binding_db, S1Service())
            binder = ExtractionEvidenceBinder(bstore, esvc, recon, evidence, S1Service())
            try:
                barrier.wait(timeout=30)
                outcomes[i] = binder.bind_extraction(ids[i][2])
            finally:
                bstore.close()
                estore.close()
                evidence.close()
                rstore.close()
                cstore.close()
        except Exception as exc:                    # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)

    assert errors == [], f"worker errors: {errors}"
    assert all(isinstance(o, BindingCompleted) for o in outcomes), outcomes
    report = binding_stack.binder.verify_chain()
    assert report.valid, report
    assert report.records == 8 and report.last_seq == 8
    seqs = [r.seq for r in binding_stack.binding_store.find_for_document(pairs[0])]
    assert seqs == sorted(seqs)                     # deterministic per-document order
