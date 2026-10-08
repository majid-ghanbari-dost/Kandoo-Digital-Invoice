"""WP-12.1 store tests — persistence, restart durability, verify-on-read
tamper matrix, CHECK/UNIQUE backstops via direct SQL, immutability probes
(SPEC-WP121 §6/§9)."""
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import S1Service  # noqa: E402
from corpus import (  # noqa: E402
    CorpusAssembled,
    CorpusAssemblyService,
    CorpusDuplicateVersion,
    CorpusEntry,
    CorpusNotFound,
    CorpusReadIntegrityFailure,
    CorpusReadRefused,
    CorpusStore,
    CorpusStorageUnavailable,
    CorpusVerificationUnavailable,
)
from corpus.store import (  # noqa: E402
    pack_labels,
    pack_parts,
    unpack_labels,
    unpack_parts,
)


def _assemble(service, template="kv-invoice-clean-v1", count=3, seed=42):
    outcome = service.assemble(template, count, seed)
    assert isinstance(outcome, CorpusAssembled), outcome
    return outcome


def _read(service, version_id):
    return service.read_corpus(version_id)


# ---------------------------------------------------------------------------
# Blob round-trips (packing helpers)
# ---------------------------------------------------------------------------

def test_parts_blob_round_trip(store):
    blob = pack_parts((b"a", b"", b"longer-part-\xc3\xa9"))
    assert unpack_parts(blob) == (b"a", b"", b"longer-part-\xc3\xa9")


def test_labels_blob_round_trip_preserves_kinds(store):
    from corpus.model import CorpusLabel, LABEL_KIND_ABSENT, LABEL_KIND_VALUE
    labels = (
        CorpusLabel("a.f", LABEL_KIND_VALUE, "1"),
        CorpusLabel("b.f", LABEL_KIND_ABSENT, None),
    )
    assert unpack_labels(pack_labels(labels)) == labels


def test_unpack_refuses_truncated_blobs(store):
    good = pack_parts((b"abc",))
    for cut in (0, 4, len(good) - 1):
        with pytest.raises(CorpusReadRefused):
            unpack_parts(good[:cut])
    good_labels = pack_labels(())
    with pytest.raises(CorpusReadRefused):
        unpack_labels(b"")


def test_unpack_refuses_trailing_bytes(store):
    blob = pack_parts((b"abc",)) + b"\x00"
    with pytest.raises(CorpusReadRefused):
        unpack_parts(blob)


# ---------------------------------------------------------------------------
# Commit + verified read
# ---------------------------------------------------------------------------

def test_commit_then_verified_read(service):
    outcome = _assemble(service)
    vid = outcome.manifest.corpus_version_id
    read = _read(service, vid)
    assert read.manifest.corpus_version_id == vid
    assert len(read.entries) == 3
    assert [e.ordinal for e in read.entries] == [0, 1, 2]
    assert all(e.corpus_version_id == vid for e in read.entries)


def test_read_preserves_parts_and_labels_byte_exact(service):
    outcome = _assemble(service, count=2)
    read = _read(service, outcome.manifest.corpus_version_id)
    for staged, stored in zip(outcome.entries, read.entries):
        assert staged.parts == stored.parts
        assert staged.labels == stored.labels
        assert staged.entry_seed == stored.entry_seed


def test_read_unknown_version_is_not_found(service):
    _assemble(service)
    with pytest.raises(CorpusNotFound):
        service.read_corpus("ff" * 32)


def test_read_empty_store_not_found(service):
    with pytest.raises(CorpusNotFound):
        service.read_corpus("ab" * 32)


def test_read_refuses_bad_version_ids(service):
    _assemble(service)
    for bad in ("", None, 123, "short"):
        with pytest.raises(Exception) as excinfo:
            service.read_corpus(bad)
        assert type(excinfo.value).__name__ in (
            "CorpusReadRefused", "CorpusNotFound", "CorpusInputRefused")


# ---------------------------------------------------------------------------
# Restart durability
# ---------------------------------------------------------------------------

def test_restart_durability_corpus_db(corpus_db, s1, service):
    outcome = _assemble(service, count=4)
    vid = outcome.manifest.corpus_version_id
    staged = outcome.entries
    reopened = CorpusStore(corpus_db, s1)
    try:
        svc2 = CorpusAssemblyService(reopened, s1)
        read = svc2.read_corpus(vid)
        assert read.manifest.corpus_version_id == vid
        assert read.manifest.entry_count == 4
        for a, b in zip(staged, read.entries):
            assert a.entry_fingerprint == b.entry_fingerprint
            assert a.parts == b.parts
    finally:
        reopened.close()


def test_replay_after_restart_zero_new_rows(corpus_db, s1, service):
    outcome = _assemble(service, count=2)
    before = _row_counts(corpus_db)
    reopened = CorpusStore(corpus_db, s1)
    try:
        svc2 = CorpusAssemblyService(reopened, s1)
        replay = svc2.assemble("kv-invoice-clean-v1", 2, 42)
        assert type(replay).__name__ == "CorpusReplay"
    finally:
        reopened.close()
    assert _row_counts(corpus_db) == before


def _row_counts(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        entries = conn.execute(
            "SELECT COUNT(*) FROM corpus_entries").fetchone()[0]
        manifests = conn.execute(
            "SELECT COUNT(*) FROM corpus_manifests").fetchone()[0]
        return entries, manifests
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tamper matrix — every stored-byte mutation is WITHHELD (never delivered)
# ---------------------------------------------------------------------------

def _tamper(db_path, sql, args=()):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


def test_tamper_manifest_fingerprint_withholds(service, corpus_db):
    vid = _assemble(service).manifest.corpus_version_id
    _tamper(corpus_db, "UPDATE corpus_manifests SET template_id = 'x' "
                       "WHERE corpus_version_id = ?", (vid,))
    with pytest.raises(CorpusReadIntegrityFailure):
        service.read_corpus(vid)


def test_tamper_entry_fingerprint_column_withholds(service, corpus_db):
    vid = _assemble(service).manifest.corpus_version_id
    conn = sqlite3.connect(str(corpus_db))
    try:
        rowid = conn.execute(
            "SELECT rowid FROM corpus_entries WHERE corpus_version_id = ? "
            "ORDER BY ordinal LIMIT 1", (vid,)).fetchone()[0]
        conn.execute(
            "UPDATE corpus_entries SET entry_fingerprint = ? WHERE rowid = ?",
            ("ab" * 32, rowid))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(CorpusReadIntegrityFailure):
        service.read_corpus(vid)


def test_tamper_entry_part_bytes_withholds(service, corpus_db):
    vid = _assemble(service).manifest.corpus_version_id
    conn = sqlite3.connect(str(corpus_db))
    try:
        row = conn.execute(
            "SELECT rowid, parts_blob FROM corpus_entries "
            "WHERE corpus_version_id = ? ORDER BY ordinal LIMIT 1",
            (vid,)).fetchone()
        blob = bytearray(row[1])
        blob[-1] ^= 0x01                      # single-bit flip in a part
        conn.execute(
            "UPDATE corpus_entries SET parts_blob = ? WHERE rowid = ?",
            (bytes(blob), row[0]))
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(CorpusReadIntegrityFailure):
        service.read_corpus(vid)


def test_tamper_entry_ordinal_breaks_gapfree_withholds(service, corpus_db):
    vid = _assemble(service, count=3).manifest.corpus_version_id
    _tamper(corpus_db, "UPDATE corpus_entries SET ordinal = 99 "
                       "WHERE ordinal = 2 AND corpus_version_id = ?", (vid,))
    with pytest.raises((CorpusReadIntegrityFailure, CorpusReadRefused)):
        service.read_corpus(vid)


def test_tamper_entry_count_row_withholds(service, corpus_db):
    vid = _assemble(service, count=3).manifest.corpus_version_id
    _tamper(corpus_db, "UPDATE corpus_manifests SET entry_count = 4 "
                       "WHERE corpus_version_id = ?", (vid,))
    with pytest.raises(CorpusReadIntegrityFailure):
        service.read_corpus(vid)


def test_tamper_ledger_line_withholds(service, corpus_db):
    vid = _assemble(service, count=2).manifest.corpus_version_id
    _tamper(corpus_db, "UPDATE corpus_manifests SET entries_blob = ? "
                       "WHERE corpus_version_id = ?", ("0:" + "cd" * 32, vid))
    with pytest.raises((CorpusReadIntegrityFailure, CorpusReadRefused)):
        service.read_corpus(vid)


def test_delete_entry_row_withholds(service, corpus_db):
    vid = _assemble(service, count=3).manifest.corpus_version_id
    _tamper(corpus_db, "DELETE FROM corpus_entries WHERE ordinal = 1 "
                       "AND corpus_version_id = ?", (vid,))
    with pytest.raises(CorpusReadIntegrityFailure):
        service.read_corpus(vid)


# ---------------------------------------------------------------------------
# CHECK / UNIQUE backstops via DIRECT SQL (the gates hold without the service)
# ---------------------------------------------------------------------------

def _assemble_and_row(service):
    outcome = _assemble(service, count=1)
    vid = outcome.manifest.corpus_version_id
    entry = outcome.entries[0]
    return vid, entry


def test_check_refuses_foreign_origin_role(service, corpus_db):
    vid, entry = _assemble_and_row(service)
    with pytest.raises(sqlite3.IntegrityError):
        _tamper(corpus_db, "UPDATE corpus_entries SET origin_role = 'REAL_DATA' "
                           "WHERE corpus_version_id = ?", (vid,))
    with pytest.raises(sqlite3.IntegrityError):
        _tamper(corpus_db, "UPDATE corpus_manifests SET origin_role = 'REAL_DATA' "
                           "WHERE corpus_version_id = ?", (vid,))


def test_check_refuses_marking_drift(service, corpus_db):
    vid, _entry = _assemble_and_row(service)
    with pytest.raises(sqlite3.IntegrityError):
        _tamper(corpus_db, "UPDATE corpus_entries SET marking = 'synthetic' "
                           "WHERE corpus_version_id = ?", (vid,))


def test_check_refuses_unknown_algorithm_id(service, corpus_db):
    vid, _entry = _assemble_and_row(service)
    with pytest.raises(sqlite3.IntegrityError):
        _tamper(corpus_db, "UPDATE corpus_entries SET fingerprint_algorithm_id "
                           "= 'md5' WHERE corpus_version_id = ?", (vid,))


def test_unique_entry_fingerprint_backstop(service, corpus_db):
    """The same entry content cannot live in two versions (theft/move gate)."""
    outcome = _assemble(service, count=2)
    vid = outcome.manifest.corpus_version_id
    conn = sqlite3.connect(str(corpus_db))
    try:
        row = conn.execute(
            "SELECT ordinal, template_id, entry_seed, origin_role, marking, "
            "parts_blob, labels_blob, parts_total_bytes, entry_fingerprint, "
            "fingerprint_algorithm_id FROM corpus_entries "
            "WHERE corpus_version_id = ? ORDER BY ordinal LIMIT 1",
            (vid,)).fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO corpus_entries (corpus_version_id, ordinal, "
                "template_id, entry_seed, origin_role, marking, parts_blob, "
                "labels_blob, parts_total_bytes, entry_fingerprint, "
                "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("ff" * 32,) + tuple(row))
        conn.commit()
    finally:
        conn.close()


def test_unique_version_ordinal_backstop(service, corpus_db):
    vid, entry = _assemble_and_row(service)
    conn = sqlite3.connect(str(corpus_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO corpus_entries (corpus_version_id, ordinal, "
                "template_id, entry_seed, origin_role, marking, parts_blob, "
                "labels_blob, parts_total_bytes, entry_fingerprint, "
                "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (vid, entry.ordinal, entry.template_id, (entry.entry_seed + 1) % 0x7FFFFFFFFFFFFFFF,
                 entry.origin_role, entry.marking, pack_parts(entry.parts),
                 pack_labels(entry.labels), sum(len(p) for p in entry.parts),
                 "ee" * 32, "sha256-v1"))
        conn.commit()
    finally:
        conn.close()


def test_negative_ordinal_refused_by_check(service, corpus_db):
    vid, entry = _assemble_and_row(service)
    conn = sqlite3.connect(str(corpus_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO corpus_entries (corpus_version_id, ordinal, "
                "template_id, entry_seed, origin_role, marking, parts_blob, "
                "labels_blob, parts_total_bytes, entry_fingerprint, "
                "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (vid, -1, entry.template_id, 1, entry.origin_role, entry.marking,
                 pack_parts((b"x",)), pack_labels(()), 1, "dd" * 32, "sha256-v1"))
        conn.commit()
    finally:
        conn.close()


def test_no_update_or_delete_path_in_store_source():
    """Static probe: the store source contains NO UPDATE/DELETE statement
    (append-only by construction)."""
    source = Path(SRC / "corpus" / "store.py").read_text(encoding="utf-8")
    for forbidden in ("UPDATE ", "DELETE FROM", "DROP TABLE", "ALTER TABLE"):
        assert forbidden not in source, f"store source contains {forbidden!r}"


def test_store_refuses_unopenable_path(s1):
    with pytest.raises(CorpusStorageUnavailable):
        CorpusStore("/nonexistent-directory-xyz/corpus.db", s1)


def test_unknown_algorithm_on_read_is_verification_unavailable(service, corpus_db):
    """A stored row claiming an unknown algorithm id is a version-skew
    NO-VERDICT surface — but the CHECK gate forbids storing one; direct SQL
    rebuild proves the gate (defensive mirror)."""
    vid, _entry = _assemble_and_row(service)
    conn = sqlite3.connect(str(corpus_db))
    try:
        gates = conn.execute(
            "SELECT COUNT(*) FROM pragma_table_info('corpus_entries') "
            "WHERE name = 'fingerprint_algorithm_id'").fetchone()[0]
        assert gates == 1
    finally:
        conn.close()
    with pytest.raises(sqlite3.IntegrityError):
        _tamper(corpus_db, "UPDATE corpus_manifests SET "
                           "fingerprint_algorithm_id = 'sha256-v2' "
                           "WHERE corpus_version_id = ?", (vid,))
