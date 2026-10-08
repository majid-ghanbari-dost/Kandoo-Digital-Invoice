"""Cold-start smoke check — WP-12.1 Corpus Assembly (18th smoke).

Runs the dispatched corpus path WITHOUT pytest on a fresh, cold-start
directory: assemble → determinism/replay → verified read → distinct
declarations → marking sweep → tamper withhold → restart → fail-closed
inputs.

Usage: python3 kandoo/src/run_smoke_corpus.py /tmp/kandoo-smoke-corpus
"""
import shutil
import sqlite3
import sys
from pathlib import Path

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/kandoo-smoke-corpus")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture import S1Service  # noqa: E402
from corpus import (  # noqa: E402
    MARKING_SYNTHETIC,
    ORIGIN_SYNTHETIC,
    CorpusAssembled,
    CorpusAssemblyService,
    CorpusInputRefused,
    CorpusReadIntegrityFailure,
    CorpusReadSuccess,
    CorpusReplay,
    CorpusStore,
)


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)          # cold start — stale state never reused
    BASE.mkdir(parents=True, exist_ok=True)
    s1 = S1Service()

    # 1. assemble (fresh store) — clean template, 4 entries
    store = CorpusStore(BASE / "corpus.db", s1)
    service = CorpusAssemblyService(store, s1)
    outcome = service.assemble("kv-invoice-clean-v1", 4, 2026)
    assert isinstance(outcome, CorpusAssembled), outcome
    vid = outcome.manifest.corpus_version_id
    assert vid == outcome.manifest.manifest_fingerprint
    print(f"1. assemble    -> CorpusAssembled version={vid[:16]}… "
          f"entries={len(outcome.entries)}")

    # 2. replay — verbatim, zero new rows
    replay = service.assemble("kv-invoice-clean-v1", 4, 2026)
    assert isinstance(replay, CorpusReplay), replay
    assert replay.manifest.corpus_version_id == vid
    assert [e.entry_fingerprint for e in replay.entries] == \
        [e.entry_fingerprint for e in outcome.entries]
    conn = sqlite3.connect(str(BASE / "corpus.db"))
    try:
        total = conn.execute("SELECT COUNT(*) FROM corpus_entries").fetchone()[0]
    finally:
        conn.close()
    assert total == 4, f"replay grew the store: {total} rows"
    print(f"2. replay      -> CorpusReplay verbatim; store rows={total} (zero new)")

    # 3. verified read — manifest VOR + every entry VOR + marking contract
    read = service.read_corpus(vid)
    assert isinstance(read, CorpusReadSuccess), read
    assert all(e.origin_role == ORIGIN_SYNTHETIC for e in read.entries)
    assert all(e.marking == MARKING_SYNTHETIC for e in read.entries)
    assert all(e.parts and e.labels for e in read.entries)
    print(f"3. read        -> CorpusReadSuccess verified; marking contract "
          f"OK on {len(read.entries)} entries")

    # 4. distinct declarations → distinct content addresses
    other = service.assemble("kv-invoice-clean-v1", 4, 2027)
    assert other.manifest.corpus_version_id != vid
    rprobe = service.assemble("kv-invoice-rounding-probe-v1", 2, 2026)
    assert rprobe.manifest.corpus_version_id not in (vid,)
    print("4. declarations -> distinct content addresses per declaration")

    # 5. determinism across independent stores — byte-identical entries
    store2 = CorpusStore(BASE / "corpus-2.db", s1)
    service2 = CorpusAssemblyService(store2, s1)
    twin = service2.assemble("kv-invoice-clean-v1", 4, 2026)
    assert twin.manifest.corpus_version_id == vid
    assert [e.parts for e in twin.entries] == [e.parts for e in read.entries]
    assert [e.labels for e in twin.entries] == [e.labels for e in read.entries]
    store2.close()
    print("5. determinism -> independent store reproduces the SAME corpus")

    # 6. tamper withhold — a flipped part byte is WITHHELD, never delivered
    conn = sqlite3.connect(str(BASE / "corpus.db"))
    try:
        rowid = conn.execute(
            "SELECT rowid, parts_blob FROM corpus_entries "
            "WHERE corpus_version_id = ? ORDER BY ordinal LIMIT 1",
            (vid,)).fetchone()
        blob = bytearray(rowid[1])
        blob[-1] ^= 0x01
        conn.execute("UPDATE corpus_entries SET parts_blob = ? WHERE rowid = ?",
                     (bytes(blob), rowid[0]))
        conn.commit()
    finally:
        conn.close()
    try:
        service.read_corpus(vid)
        raise AssertionError("tampered corpus was delivered")
    except CorpusReadIntegrityFailure:
        pass
    print("6. tamper      -> CorpusReadIntegrityFailure (corpus withheld)")

    # 7. restart — reopen the store; the UNTAMPERED other version reads fine
    store.close()
    store3 = CorpusStore(BASE / "corpus.db", s1)
    service3 = CorpusAssemblyService(store3, s1)
    read_other = service3.read_corpus(other.manifest.corpus_version_id)
    assert len(read_other.entries) == 4
    print("7. restart     -> reopened store verifies the intact version")

    # 8. fail-closed inputs — unknown template / bad bounds refused
    for args in (("kv-invoice-nonexistent", 3, 0),
                 ("kv-invoice-clean-v1", 0, 0),
                 ("kv-invoice-clean-v1", 3, -1)):
        try:
            service3.assemble(*args)
            raise AssertionError(f"bad input accepted: {args}")
        except CorpusInputRefused:
            pass
    store3.close()
    print("8. fail-closed -> bad declarations refused (typed)")

    print("SMOKE OK — corpus assembly path works end-to-end (cold start)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
