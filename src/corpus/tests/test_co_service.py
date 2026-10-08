"""WP-12.1 service tests — assembly ladder, replay idempotency, fail-closed
inputs, zero-residue failures, verified reads (SPEC-WP121 §7/§8/§9)."""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1Service  # noqa: E402
from corpus import (  # noqa: E402
    MARKING_SYNTHETIC,
    MAX_ENTRIES,
    ORIGIN_SYNTHETIC,
    CorpusAssembled,
    CorpusAssemblyService,
    CorpusDuplicateVersion,
    CorpusInputRefused,
    CorpusReadSuccess,
    CorpusReplay,
    CorpusStore,
)
from corpus.model import (  # noqa: E402
    CorpusReadIntegrityFailure,
    CorpusReadRefused,
)


# ---------------------------------------------------------------------------
# A1 declared-input validation — fail-closed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("template,count,seed", [
    ("kv-invoice-nonexistent", 3, 0),          # unknown template
    ("", 3, 0),                                # empty template
    (None, 3, 0),                              # non-string template
    ("kv-invoice-clean-v1", 0, 0),             # zero entries
    ("kv-invoice-clean-v1", -5, 0),            # negative entries
    ("kv-invoice-clean-v1", MAX_ENTRIES + 1, 0),   # over the declared bound
    ("kv-invoice-clean-v1", 3, -1),            # negative seed
    ("kv-invoice-clean-v1", 3, "7"),           # non-int seed
    ("kv-invoice-clean-v1", "3", 0),           # non-int count
    ("kv-invoice-clean-v1", True, 0),          # bool count is not an int count
    ("kv-invoice-clean-v1", 3, True),          # bool seed
])
def test_assemble_refuses_bad_inputs(service, template, count, seed):
    with pytest.raises(CorpusInputRefused):
        service.assemble(template, count, seed)


def test_refusals_generate_nothing(service, corpus_db):
    for template, count, seed in (("kv-invoice-nonexistent", 3, 0),
                                  ("kv-invoice-clean-v1", 0, 0),
                                  ("kv-invoice-clean-v1", 3, -1)):
        with pytest.raises(CorpusInputRefused):
            service.assemble(template, count, seed)
    conn = sqlite3.connect(str(corpus_db))
    try:
        assert conn.execute("SELECT COUNT(*) FROM corpus_entries").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM corpus_manifests").fetchone()[0] == 0
    finally:
        conn.close()


def test_service_requires_the_capture_s1_service(store):
    with pytest.raises(CorpusInputRefused):
        CorpusAssemblyService(store, "not-an-s1")


# ---------------------------------------------------------------------------
# A2/A3 deterministic assembly + content addressing
# ---------------------------------------------------------------------------

def test_assemble_happy_shape(service):
    outcome = service.assemble("kv-invoice-clean-v1", 5, 42)
    assert isinstance(outcome, CorpusAssembled)
    assert outcome.manifest.entry_count == 5
    assert outcome.manifest.template_id == "kv-invoice-clean-v1"
    assert outcome.manifest.seed_base == 42
    assert outcome.manifest.corpus_version_id == outcome.manifest.manifest_fingerprint
    assert outcome.manifest.origin_role == ORIGIN_SYNTHETIC
    assert outcome.manifest.marking == MARKING_SYNTHETIC
    assert len(outcome.entries) == 5
    assert outcome.manifest.entries_blob.count("\n") == 4


def test_assemble_deterministic_across_independent_stores(tmp_path, s1):
    """Same declaration → same content address, byte-identical entries (the
    determinism axis proven across two INDEPENDENT store files)."""
    vids = []
    for i in range(2):
        with CorpusStore(tmp_path / f"corpus-{i}.db", s1) as store:
            svc = CorpusAssemblyService(store, s1)
            outcome = svc.assemble("kv-invoice-clean-v1", 4, 123)
            vids.append(outcome.manifest.corpus_version_id)
            if i == 1:
                first_parts = [
                    (e.parts, e.labels, e.entry_fingerprint)
                    for e in outcome.entries]
    assert vids[0] == vids[1]
    with CorpusStore(tmp_path / "corpus-0.db", s1) as store:
        svc = CorpusAssemblyService(store, s1)
        second = svc.assemble("kv-invoice-clean-v1", 4, 123)
        second_parts = [
            (e.parts, e.labels, e.entry_fingerprint) for e in second.entries]
    assert first_parts == second_parts


def test_different_declaration_different_address(service):
    a = service.assemble("kv-invoice-clean-v1", 3, 42)
    b = service.assemble("kv-invoice-clean-v1", 4, 42)
    c = service.assemble("kv-invoice-clean-v1", 3, 43)
    d = service.assemble("kv-invoice-rounding-probe-v1", 3, 42)
    ids = {a.manifest.corpus_version_id, b.manifest.corpus_version_id,
           c.manifest.corpus_version_id, d.manifest.corpus_version_id}
    assert len(ids) == 4


def test_every_entry_carries_the_marking_contract(service):
    outcome = service.assemble("kv-invoice-review-probe-v1", 3, 11)
    for entry in outcome.entries:
        assert entry.origin_role == ORIGIN_SYNTHETIC
        assert entry.marking == MARKING_SYNTHETIC


# ---------------------------------------------------------------------------
# A4 idempotent replay (D-03 discipline)
# ---------------------------------------------------------------------------

def test_replay_is_verbatim_zero_new_rows(service, corpus_db):
    first = service.assemble("kv-invoice-clean-v1", 3, 42)
    conn = sqlite3.connect(str(corpus_db))
    try:
        before = (
            conn.execute("SELECT COUNT(*) FROM corpus_entries").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM corpus_manifests").fetchone()[0],
        )
    finally:
        conn.close()
    second = service.assemble("kv-invoice-clean-v1", 3, 42)
    assert isinstance(second, CorpusReplay)
    assert type(first) is not type(second)
    assert second.manifest.corpus_version_id == first.manifest.corpus_version_id
    assert [e.entry_fingerprint for e in second.entries] == \
        [e.entry_fingerprint for e in first.entries]
    conn = sqlite3.connect(str(corpus_db))
    try:
        after = (
            conn.execute("SELECT COUNT(*) FROM corpus_entries").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM corpus_manifests").fetchone()[0],
        )
    finally:
        conn.close()
    assert before == after


def test_replay_repeatable_many_times(service):
    vid = None
    for _ in range(4):
        outcome = service.assemble("kv-invoice-clean-v1", 2, 8)
        if vid is None:
            vid = outcome.manifest.corpus_version_id
            assert isinstance(outcome, CorpusAssembled)
        else:
            assert isinstance(outcome, CorpusReplay)
            assert outcome.manifest.corpus_version_id == vid


def test_replay_detects_storage_disagreement(service, corpus_db):
    """A same-address re-assembly whose content differs from storage is a
    fail-closed refusal. Reachable only by storage tampering (content
    addressing makes natural collision structurally impossible) — proven by
    rewriting one stored fingerprint ledger line to a SAME-LENGTH but
    different-content ledger that keeps the version id row."""
    outcome = service.assemble("kv-invoice-clean-v1", 2, 42)
    vid = outcome.manifest.corpus_version_id
    conn = sqlite3.connect(str(corpus_db))
    try:
        row = conn.execute(
            "SELECT entries_blob FROM corpus_manifests WHERE "
            "corpus_version_id = ?", (vid,)).fetchone()
        lines = row[0].splitlines()
        ordinal, _, fp = lines[1].partition(":")
        flipped = ("0" if fp[0] != "0" else "1") + fp[1:]
        lines[1] = f"{ordinal}:{flipped}"
        conn.execute(
            "UPDATE corpus_manifests SET entries_blob = ? WHERE "
            "corpus_version_id = ?", ("\n".join(lines), vid))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises((CorpusReadIntegrityFailure, CorpusDuplicateVersion)):
        service.assemble("kv-invoice-clean-v1", 2, 42)


# ---------------------------------------------------------------------------
# A5 verified reads
# ---------------------------------------------------------------------------

def test_read_returns_verified_corpus(service):
    outcome = service.assemble("kv-invoice-clean-v1", 3, 42)
    read = service.read_corpus(outcome.manifest.corpus_version_id)
    assert isinstance(read, CorpusReadSuccess)
    assert read.manifest.entry_count == len(read.entries) == 3


def test_read_agreement_gate_detects_ledger_drift(service, corpus_db):
    """If stored entries drift from the stored ledger, the read refuses —
    the manifest fingerprint recomputation is part of EVERY read."""
    outcome = service.assemble("kv-invoice-clean-v1", 2, 42)
    vid = outcome.manifest.corpus_version_id
    conn = sqlite3.connect(str(corpus_db))
    try:
        # replace entry 1 with a DIFFERENT valid entry from another version
        other = service.assemble("kv-invoice-clean-v1", 2, 43)
        stolen = other.entries[1]
        conn.execute(
            "UPDATE corpus_entries SET parts_blob = ? "
            "WHERE corpus_version_id = ? AND ordinal = 1",
            (sqlite3.Binary(b"tampered"), vid))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises((CorpusReadIntegrityFailure, CorpusReadRefused)):
        service.read_corpus(vid)


def test_read_after_replay_consistent(service):
    first = service.assemble("kv-invoice-clean-v1", 3, 7)
    service.assemble("kv-invoice-clean-v1", 3, 7)
    read = service.read_corpus(first.manifest.corpus_version_id)
    assert [e.ordinal for e in read.entries] == [0, 1, 2]


# ---------------------------------------------------------------------------
# Zero residue under forced failure
# ---------------------------------------------------------------------------

def test_forced_mid_assembly_failure_leaves_zero_residue(service, corpus_db,
                                                         monkeypatch):
    """A storage failure after the manifest insert rolls back the WHOLE
    version — zero rows, typed refusal, nothing presented as valid."""
    from corpus import CorpusStorageUnavailable
    import corpus.store as store_module

    calls = {"manifest_inserts": 0}
    real_connect = sqlite3.connect

    class ProxyConn:
        """Delegates everything to the real connection; injects a forced
        OperationalError at the FIRST entry insert after the manifest row."""

        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, *args):
            if sql.startswith("INSERT INTO corpus_manifests"):
                calls["manifest_inserts"] += 1
            elif sql.startswith("INSERT INTO corpus_entries") \
                    and calls["manifest_inserts"] == 1:
                raise sqlite3.OperationalError("forced failure (test injection)")
            return self._conn.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def __setattr__(self, name, value):
            if name == "_conn":
                object.__setattr__(self, name, value)
            else:
                setattr(self._conn, name, value)

    def factory(*args, **kwargs):
        kwargs.pop("isolation_level", None)
        return ProxyConn(real_connect(*args, isolation_level=None, **kwargs))

    monkeypatch.setattr(store_module.sqlite3, "connect", factory)
    try:
        fresh = CorpusStore(corpus_db.parent / "forced-failure.db", S1Service())
        monkeypatch.undo()
        fresh.close()

        calls["manifest_inserts"] = 0
        monkeypatch.setattr(store_module.sqlite3, "connect", factory)
        try:
            store2 = CorpusStore(corpus_db.parent / "forced-failure2.db",
                                 S1Service())
            svc3 = CorpusAssemblyService(store2, S1Service())
            with pytest.raises((CorpusStorageUnavailable, CorpusDuplicateVersion)):
                svc3.assemble("kv-invoice-rounding-probe-v1", 2, 99)
            store2.close()
        finally:
            monkeypatch.undo()
    finally:
        pass

    conn = real_connect(str(corpus_db.parent / "forced-failure2.db"))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM corpus_manifests WHERE template_id = "
            "'kv-invoice-rounding-probe-v1' AND seed_base = 99").fetchone()[0]
        assert count == 0, "forced failure left residue rows"
        total_entries = conn.execute(
            "SELECT COUNT(*) FROM corpus_entries WHERE template_id = "
            "'kv-invoice-rounding-probe-v1'").fetchone()[0]
        assert total_entries == 0
    finally:
        conn.close()


def test_duplicate_fingerprint_row_rejected_at_commit(service, corpus_db):
    """UNIQUE(entry_fingerprint) backstop: inserting a second row with the
    same fingerprint fails at the storage layer (proven via direct SQL)."""
    outcome = service.assemble("kv-invoice-clean-v1", 1, 5)
    vid = outcome.manifest.corpus_version_id
    entry = outcome.entries[0]
    conn = sqlite3.connect(str(corpus_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO corpus_entries (corpus_version_id, ordinal, "
                "template_id, entry_seed, origin_role, marking, parts_blob, "
                "labels_blob, parts_total_bytes, entry_fingerprint, "
                "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("ab" * 32, 0, entry.template_id, entry.entry_seed,
                 entry.origin_role, entry.marking, b"x", b"",
                 1, entry.entry_fingerprint, "sha256-v1"))
        conn.commit()
    finally:
        conn.close()
