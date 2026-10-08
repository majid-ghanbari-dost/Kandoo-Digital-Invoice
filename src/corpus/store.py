"""Corpus durable store — WP-12.1 (SPEC-WP121-CORPUS §6).

The project store pattern, adapted to content-addressed pilot material:
stdlib sqlite3, ONE separate embedded DB file (`corpus.db`), synchronous=FULL,
explicit BEGIN IMMEDIATE / COMMIT, atomic whole-version commit (all entries +
manifest or NOTHING — zero residue on any failure), immutable rows (no mutation
path — AST-proven), sha256-v1 fingerprints computed through the
project S1 service (the single hash capability — no second hash here), verify-on-read via canonical
bytes rebuilt from the stored columns, SQL CHECK gates + defensive
Python-side refusals mirroring every CHECK, UNIQUE(corpus_version_id,
ordinal) + UNIQUE(entry_fingerprint) backstops, restart-safe.

CLOCK-FREE (OD-CA-J): no clock column, no time import — corpus material
is content-addressed pilot input with no operational clock semantics.

The store knows NOTHING about upstream semantics: it persists what the
service assembled from the declared templates and enforces the SPEC §6
shapes. It is a PILOT store — never a production domain store, never opened
by any production package.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional, Tuple

from capture import S1Service

from .generator import (
    entry_canonical_bytes,
    manifest_canonical_bytes,
)
from .model import (
    CORPUS_ORIGINS,
    CORPUS_MARKINGS,
    LABEL_KINDS,
    CorpusDuplicateVersion,
    CorpusEntry,
    CorpusLabel,
    CorpusManifest,
    CorpusNotFound,
    CorpusReadIntegrityFailure,
    CorpusReadRefused,
    CorpusStorageUnavailable,
    CorpusVerificationUnavailable,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_entries (
    corpus_version_id         TEXT NOT NULL,
    ordinal                   INTEGER NOT NULL CHECK (ordinal >= 0),
    template_id               TEXT NOT NULL,
    entry_seed                INTEGER NOT NULL CHECK (entry_seed >= 0),
    origin_role               TEXT NOT NULL
        CHECK (origin_role IN ('SYNTHETIC_PILOT_FIXTURE')),
    marking                   TEXT NOT NULL
        CHECK (marking = 'SYNTHETIC-PILOT-FIXTURE — NOT PRODUCTION DATA'),
    parts_blob                BLOB NOT NULL,
    labels_blob               BLOB NOT NULL,
    parts_total_bytes         INTEGER NOT NULL CHECK (parts_total_bytes >= 0),
    entry_fingerprint         TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL
        CHECK (fingerprint_algorithm_id = 'sha256-v1'),
    UNIQUE (corpus_version_id, ordinal),
    UNIQUE (entry_fingerprint)
);

CREATE TABLE IF NOT EXISTS corpus_manifests (
    corpus_version_id         TEXT PRIMARY KEY,
    template_id               TEXT NOT NULL,
    seed_base                 INTEGER NOT NULL CHECK (seed_base >= 0),
    entry_count               INTEGER NOT NULL CHECK (entry_count >= 1),
    origin_role               TEXT NOT NULL
        CHECK (origin_role IN ('SYNTHETIC_PILOT_FIXTURE')),
    marking                   TEXT NOT NULL
        CHECK (marking = 'SYNTHETIC-PILOT-FIXTURE — NOT PRODUCTION DATA'),
    entries_blob              TEXT NOT NULL,
    manifest_fingerprint      TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL
        CHECK (fingerprint_algorithm_id = 'sha256-v1')
);
"""


# ---------------------------------------------------------------------------
# Label blob packing (byte-format identical to the canonical entry segment)
# ---------------------------------------------------------------------------

def _lp(payload: bytes) -> bytes:
    return len(payload).to_bytes(8, "big") + payload


def _read_lp(blob: bytes, offset: int) -> Tuple[bytes, int]:
    if offset + 8 > len(blob):
        raise CorpusReadRefused("truncated length prefix in stored blob")
    n = int.from_bytes(blob[offset:offset + 8], "big")
    end = offset + 8 + n
    if end > len(blob):
        raise CorpusReadRefused("truncated payload in stored blob")
    return blob[offset + 8:end], end


def pack_labels(labels: Tuple[CorpusLabel, ...]) -> bytes:
    out = bytearray()
    out += len(labels).to_bytes(8, "big")
    for label in labels:                       # caller passes canonical order
        out += _lp(label.field_name.encode("utf-8"))
        out += b"\x01" if label.kind == "ABSENT" else b"\x00"
        out += _lp((label.expected_value or "").encode("utf-8"))
        out += _lp(label.label_provenance.encode("utf-8"))
    return bytes(out)


def unpack_labels(blob: bytes) -> Tuple[CorpusLabel, ...]:
    if len(blob) < 8:
        raise CorpusReadRefused("truncated label blob")
    count = int.from_bytes(blob[0:8], "big")
    offset = 8
    labels: List[CorpusLabel] = []
    for _ in range(count):
        name_raw, offset = _read_lp(blob, offset)
        if offset >= len(blob):
            raise CorpusReadRefused("truncated label kind byte")
        kind_byte = blob[offset]
        offset += 1
        value_raw, offset = _read_lp(blob, offset)
        prov_raw, offset = _read_lp(blob, offset)
        kind = "ABSENT" if kind_byte == 1 else "VALUE"
        if kind not in LABEL_KINDS:
            raise CorpusReadRefused(f"unknown stored label kind byte: {kind_byte!r}")
        expected = value_raw.decode("utf-8") if kind == "VALUE" else None
        labels.append(CorpusLabel(
            field_name=name_raw.decode("utf-8"),
            kind=kind,
            expected_value=expected,
            label_provenance=prov_raw.decode("utf-8"),
        ))
    if offset != len(blob):
        raise CorpusReadRefused("trailing bytes in stored label blob")
    return tuple(labels)


def pack_parts(parts: Tuple[bytes, ...]) -> bytes:
    out = bytearray()
    out += len(parts).to_bytes(8, "big")
    for part in parts:
        out += _lp(part)
    return bytes(out)


def unpack_parts(blob: bytes) -> Tuple[bytes, ...]:
    if len(blob) < 8:
        raise CorpusReadRefused("truncated parts blob")
    count = int.from_bytes(blob[0:8], "big")
    offset = 8
    parts: List[bytes] = []
    for _ in range(count):
        part, offset = _read_lp(blob, offset)
        parts.append(part)
    if offset != len(blob):
        raise CorpusReadRefused("trailing bytes in stored parts blob")
    return tuple(parts)


# ---------------------------------------------------------------------------
# Row reconstruction + VOR anchors
# ---------------------------------------------------------------------------

def _entry_anchor(entry: CorpusEntry) -> bytes:
    """The canonical bytes a stored entry's fingerprint commits to (rebuilt
    from the stored columns — byte-identity proves column integrity)."""
    return entry_canonical_bytes(
        template_id=entry.template_id,
        entry_seed=entry.entry_seed,
        ordinal=entry.ordinal,
        parts=entry.parts,
        labels=entry.labels,
        origin_role=entry.origin_role,
        marking=entry.marking,
    )


def _manifest_anchor(manifest: CorpusManifest) -> bytes:
    """The canonical bytes a stored manifest's fingerprint commits to. The
    entries ledger is REBUILT from the stored ledger string (deterministic
    `ordinal:fingerprint` lines) — a tampered ledger cannot verify."""
    pairs: List[Tuple[int, str]] = []
    for line in manifest.entries_blob.splitlines():
        line = line.strip()
        if not line:
            continue
        ordinal_str, _, fingerprint = line.partition(":")
        if not ordinal_str.isdigit() or len(fingerprint) != 64:
            raise CorpusReadRefused("malformed stored manifest ledger line")
        pairs.append((int(ordinal_str), fingerprint))
    return manifest_canonical_bytes(
        template_id=manifest.template_id,
        seed_base=manifest.seed_base,
        entry_count=manifest.entry_count,
        entry_fingerprints=pairs,
        origin_role=manifest.origin_role,
        marking=manifest.marking,
    )


def _entry_from_row(row: sqlite3.Row) -> CorpusEntry:
    parts = unpack_parts(bytes(row["parts_blob"]))
    if sum(len(p) for p in parts) != row["parts_total_bytes"]:
        raise CorpusReadRefused("stored parts_total_bytes disagrees with parts")
    return CorpusEntry(
        corpus_version_id=row["corpus_version_id"],
        ordinal=row["ordinal"],
        template_id=row["template_id"],
        entry_seed=row["entry_seed"],
        origin_role=row["origin_role"],
        marking=row["marking"],
        parts=parts,
        labels=unpack_labels(bytes(row["labels_blob"])),
        entry_fingerprint=row["entry_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _manifest_from_row(row: sqlite3.Row) -> CorpusManifest:
    return CorpusManifest(
        corpus_version_id=row["corpus_version_id"],
        template_id=row["template_id"],
        seed_base=row["seed_base"],
        entry_count=row["entry_count"],
        origin_role=row["origin_role"],
        marking=row["marking"],
        entries_blob=row["entries_blob"],
        manifest_fingerprint=row["manifest_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


class CorpusStore:
    """Durable, append-only, content-addressed corpus store (SPEC §6)."""

    def __init__(self, db_path, s1: S1Service) -> None:
        self._s1 = s1
        try:
            self._conn = sqlite3.connect(str(db_path), isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.executescript(_SCHEMA)
        except sqlite3.Error as exc:
            raise CorpusStorageUnavailable(f"store unavailable: {exc}") from exc

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "CorpusStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Commit (whole version — one atomic transaction, SPEC §6/§7 A4)
    # ------------------------------------------------------------------

    def commit_corpus_version(self, manifest: CorpusManifest,
                              entries: Tuple[CorpusEntry, ...]) -> None:
        """Insert manifest + ALL entries in ONE transaction. Raises:
          CorpusDuplicateVersion             — version already present
          CorpusReadRefused                  — CHECK/UNIQUE backstop fired
          CorpusStorageUnavailable           — nothing recordable (rollback)
        """
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "INSERT INTO corpus_manifests "
                    "(corpus_version_id, template_id, seed_base, entry_count, "
                    " origin_role, marking, entries_blob, manifest_fingerprint, "
                    " fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (manifest.corpus_version_id, manifest.template_id,
                     manifest.seed_base, manifest.entry_count, manifest.origin_role,
                     manifest.marking, manifest.entries_blob,
                     manifest.manifest_fingerprint,
                     manifest.fingerprint_algorithm_id))
                for entry in entries:
                    self._conn.execute(
                        "INSERT INTO corpus_entries "
                        "(corpus_version_id, ordinal, template_id, entry_seed, "
                        " origin_role, marking, parts_blob, labels_blob, "
                        " parts_total_bytes, entry_fingerprint, "
                        " fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (entry.corpus_version_id, entry.ordinal, entry.template_id,
                         entry.entry_seed, entry.origin_role, entry.marking,
                         pack_parts(entry.parts), pack_labels(entry.labels),
                         sum(len(p) for p in entry.parts),
                         entry.entry_fingerprint,
                         entry.fingerprint_algorithm_id))
                self._conn.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                self._conn.execute("ROLLBACK")
                raise self._integrity_refusal(manifest, exc) from exc
            except sqlite3.Error:
                self._conn.execute("ROLLBACK")
                raise
        except sqlite3.Error as exc:
            raise CorpusStorageUnavailable(
                f"corpus version commit failed: {exc}") from exc

    def _integrity_refusal(self, manifest: CorpusManifest,
                           exc: sqlite3.IntegrityError):
        """Map a storage-level integrity error to its typed refusal — the
        UNIQUE/CHECK backstops must surface as explicit failures, never as
        silent drops."""
        try:
            exists = self.manifest_exists(manifest.corpus_version_id)
        except CorpusStorageUnavailable:
            exists = False
        if exists:
            return CorpusDuplicateVersion(
                f"corpus version {manifest.corpus_version_id!r} already stored "
                f"(content addressing collided — refusing: {exc})")
        return CorpusReadRefused(f"corpus row refused by storage gates: {exc}")

    # ------------------------------------------------------------------
    # Reads (verify-on-read — VOR on every row, SPEC §7 A5)
    # ------------------------------------------------------------------

    def manifest_exists(self, corpus_version_id: str) -> bool:
        try:
            row = self._conn.execute(
                "SELECT 1 FROM corpus_manifests WHERE corpus_version_id = ?",
                (corpus_version_id,)).fetchone()
        except sqlite3.Error as exc:
            raise CorpusStorageUnavailable(f"manifest lookup failed: {exc}") from exc
        return row is not None

    def read_manifest(self, corpus_version_id: str) -> CorpusManifest:
        """VOR-verified manifest read — fingerprint recomputed from the row."""
        try:
            row = self._conn.execute(
                "SELECT * FROM corpus_manifests WHERE corpus_version_id = ?",
                (corpus_version_id,)).fetchone()
        except sqlite3.Error as exc:
            raise CorpusStorageUnavailable(f"manifest read failed: {exc}") from exc
        if row is None:
            raise CorpusNotFound(
                f"no corpus version under {corpus_version_id!r}")
        manifest = _manifest_from_row(row)
        if manifest.fingerprint_algorithm_id != "sha256-v1":
            raise CorpusVerificationUnavailable(
                f"unknown fingerprint algorithm id: "
                f"{manifest.fingerprint_algorithm_id!r}")
        recomputed = self._s1.compute(_manifest_anchor(manifest))
        if recomputed.s1 != manifest.manifest_fingerprint:
            raise CorpusReadIntegrityFailure(
                f"manifest fingerprint mismatch under {corpus_version_id!r} "
                f"(reason: {recomputed.s1_algorithm_id})")
        if manifest.corpus_version_id != manifest.manifest_fingerprint:
            raise CorpusReadIntegrityFailure(
                "stored version id is not the content address of its own "
                "manifest (content addressing violated)")
        return manifest

    def read_entries(self, corpus_version_id: str, expected_count: int) \
            -> Tuple[CorpusEntry, ...]:
        """VOR-verified entry read in ordinal order — one tampered row
        withholds the WHOLE corpus (never a partial delivery)."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM corpus_entries WHERE corpus_version_id = ? "
                "ORDER BY ordinal ASC", (corpus_version_id,)).fetchall()
        except sqlite3.Error as exc:
            raise CorpusStorageUnavailable(f"entries read failed: {exc}") from exc
        if len(rows) != expected_count:
            raise CorpusReadIntegrityFailure(
                f"entry count mismatch under {corpus_version_id!r}: stored "
                f"{len(rows)} != manifest {expected_count}")
        entries: List[CorpusEntry] = []
        for position, row in enumerate(rows):
            entry = _entry_from_row(row)
            if entry.ordinal != position:
                raise CorpusReadRefused(
                    f"entry ordinals not gap-free at position {position}")
            if entry.corpus_version_id != corpus_version_id:
                raise CorpusReadRefused("entry row carries a foreign version id")
            if entry.origin_role not in CORPUS_ORIGINS \
                    or entry.marking not in CORPUS_MARKINGS:
                raise CorpusReadRefused("entry row violates the marking contract")
            recomputed = self._s1.compute(_entry_anchor(entry))
            if recomputed.s1 != entry.entry_fingerprint:
                raise CorpusReadIntegrityFailure(
                    f"entry fingerprint mismatch (ordinal {entry.ordinal}) "
                    f"under {corpus_version_id!r}")
            entries.append(entry)
        return tuple(entries)

    # ------------------------------------------------------------------
    # Replay support (byte-identity of an existing version — SPEC §7 A4)
    # ------------------------------------------------------------------

    def stored_entry_fingerprints(self, corpus_version_id: str) \
            -> List[Tuple[int, str]]:
        try:
            rows = self._conn.execute(
                "SELECT ordinal, entry_fingerprint FROM corpus_entries "
                "WHERE corpus_version_id = ? ORDER BY ordinal ASC",
                (corpus_version_id,)).fetchall()
        except sqlite3.Error as exc:
            raise CorpusStorageUnavailable(f"fingerprint listing failed: {exc}") from exc
        return [(row["ordinal"], row["entry_fingerprint"]) for row in rows]


# CORPUS-ORIGIN/MARKING import kept as re-export for defensive mirrors
_ = (CORPUS_ORIGINS, CORPUS_MARKINGS)
