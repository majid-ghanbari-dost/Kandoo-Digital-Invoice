"""Corpus assembly service — WP-12.1 (SPEC-WP121-CORPUS §7).

The assembly ladder (A1..A5): declared-input validation → deterministic
generation → content addressing → idempotent persistence (replay verbatim,
ZERO new rows — D-03 discipline) → verified read. Fail-closed everywhere;
a forced failure mid-assembly leaves ZERO rows (the whole-version
transaction is the residue gate).

The service ratifies nothing, measures nothing, and touches nothing outside
its own corpus store. Its only capability import is the capture S1 service
(the project's single hash capability — no second hash).
"""
from __future__ import annotations

from typing import Tuple

from capture import S1Service

from . import generator as gen
from .model import (
    CORPUS_ORIGINS,
    CORPUS_MARKINGS,
    MAX_ENTRIES,
    CorpusAssembled,
    CorpusDuplicateVersion,
    CorpusEntry,
    CorpusInputRefused,
    CorpusManifest,
    CorpusReadRefused,
    CorpusReplay,
    CorpusStorageUnavailable,
)
from .store import CorpusStore


def _validate_declared_inputs(template_id: str, entry_count: int,
                              seed_base: int) -> None:
    if not isinstance(template_id, str) or not template_id:
        raise CorpusInputRefused("template_id must be a non-empty string")
    if template_id not in gen.GENERATORS:
        raise CorpusInputRefused(
            f"unknown corpus template_id: {template_id!r} "
            f"(declared: {', '.join(sorted(gen.GENERATORS))})")
    if isinstance(entry_count, bool) or not isinstance(entry_count, int) \
            or entry_count < 1 or entry_count > MAX_ENTRIES:
        raise CorpusInputRefused(
            f"entry_count must be an int in 1..{MAX_ENTRIES}, got "
            f"{entry_count!r}")
    if isinstance(seed_base, bool) or not isinstance(seed_base, int) \
            or seed_base < 0:
        raise CorpusInputRefused(
            f"seed_base must be a non-negative int, got {seed_base!r}")


def _build_entry(s1: S1Service, corpus_version_id: str, template_id: str,
                 seed_base: int, entry_count: int, ordinal: int) -> CorpusEntry:
    parts, labels, entry_seed = gen.generate_entry(
        s1, template_id, seed_base, entry_count, ordinal)
    origin_role, marking = gen.origin_and_marking()
    fingerprint = s1.compute(gen.entry_canonical_bytes(
        template_id=template_id,
        entry_seed=entry_seed,
        ordinal=ordinal,
        parts=parts,
        labels=labels,
        origin_role=origin_role,
        marking=marking,
    ))
    return CorpusEntry(
        corpus_version_id=corpus_version_id,
        ordinal=ordinal,
        template_id=template_id,
        entry_seed=entry_seed,
        origin_role=origin_role,
        marking=marking,
        parts=parts,
        labels=labels,
        entry_fingerprint=fingerprint.s1,
        fingerprint_algorithm_id=fingerprint.s1_algorithm_id,
    )


def _ledger_lines(entries: Tuple[CorpusEntry, ...]) -> str:
    return "\n".join(
        f"{entry.ordinal}:{entry.entry_fingerprint}" for entry in entries)


class CorpusAssemblyService:
    """Deterministic, fail-closed corpus assembly over the declared templates."""

    def __init__(self, store: CorpusStore, s1: S1Service) -> None:
        if not isinstance(s1, S1Service):
            raise CorpusInputRefused(
                "corpus assembly requires the capture S1Service — no second "
                "hash capability exists in this layer")
        self._store = store
        self._s1 = s1

    # ------------------------------------------------------------------
    # Assembly (SPEC §7 A1..A4)
    # ------------------------------------------------------------------

    def assemble(self, template_id: str, entry_count: int, seed_base: int) \
            -> object:
        """Assemble (or verbatim-replay) one corpus version. Returns
        CorpusAssembled (fresh, one atomic txn) or CorpusReplay (existing,
        byte-identical, zero new rows). Every refusal is typed."""
        _validate_declared_inputs(template_id, entry_count, seed_base)

        # A3 content addressing needs the entry fingerprints first (A2/A3)
        fingerprints: list = []
        staged: list = []
        for ordinal in range(entry_count):
            entry = _build_entry(self._s1, "", template_id, seed_base,
                                 entry_count, ordinal)
            staged.append(entry)
            fingerprints.append((ordinal, entry.entry_fingerprint))

        manifest_fp = self._s1.compute(gen.manifest_canonical_bytes(
            template_id=template_id,
            seed_base=seed_base,
            entry_count=entry_count,
            entry_fingerprints=fingerprints,
            origin_role=gen.origin_and_marking()[0],
            marking=gen.origin_and_marking()[1],
        ))
        corpus_version_id = manifest_fp.s1
        entries = tuple(
            CorpusEntry(
                corpus_version_id=corpus_version_id,
                ordinal=entry.ordinal,
                template_id=entry.template_id,
                entry_seed=entry.entry_seed,
                origin_role=entry.origin_role,
                marking=entry.marking,
                parts=entry.parts,
                labels=entry.labels,
                entry_fingerprint=entry.entry_fingerprint,
                fingerprint_algorithm_id=entry.fingerprint_algorithm_id,
            ) for entry in staged)
        manifest = CorpusManifest(
            corpus_version_id=corpus_version_id,
            template_id=template_id,
            seed_base=seed_base,
            entry_count=entry_count,
            origin_role=gen.origin_and_marking()[0],
            marking=gen.origin_and_marking()[1],
            entries_blob=_ledger_lines(entries),
            manifest_fingerprint=manifest_fp.s1,
            fingerprint_algorithm_id=manifest_fp.s1_algorithm_id,
        )

        # A4 idempotent persistence — content-addressed replay discipline.
        # The replay path runs the FULL verified read (manifest VOR + every
        # entry VOR + ledger agreement) BEFORE the byte-identity comparison —
        # tampered storage is a refusal, never a replay.
        if self._store.manifest_exists(corpus_version_id):
            stored_read = self.read_corpus(corpus_version_id)
            stored = [(e.ordinal, e.entry_fingerprint)
                      for e in stored_read.entries]
            expected = [(e.ordinal, e.entry_fingerprint) for e in entries]
            if stored != expected:
                raise CorpusDuplicateVersion(
                    f"stored corpus {corpus_version_id!r} disagrees with the "
                    f"re-assembly under the same content address — refusing "
                    f"(fail-closed; never repaired)")
            return CorpusReplay(manifest=stored_read.manifest,
                                entries=stored_read.entries)

        self._store.commit_corpus_version(manifest, entries)
        return CorpusAssembled(manifest=manifest, entries=entries)

    # ------------------------------------------------------------------
    # Verified read (SPEC §7 A5)
    # ------------------------------------------------------------------

    def read_corpus(self, corpus_version_id: str):
        """Verified read: manifest VOR + every entry VOR + manifest
        fingerprint recomputed over the read entries + count agreement. Any
        anomaly withholds the corpus explicitly (typed failure)."""
        if not isinstance(corpus_version_id, str) or not corpus_version_id:
            raise CorpusReadRefused("corpus_version_id must be a non-empty string")
        manifest = self._store.read_manifest(corpus_version_id)
        entries = self._store.read_entries(
            corpus_version_id, manifest.entry_count)
        recomputed = self._s1.compute(gen.manifest_canonical_bytes(
            template_id=manifest.template_id,
            seed_base=manifest.seed_base,
            entry_count=manifest.entry_count,
            entry_fingerprints=[(e.ordinal, e.entry_fingerprint) for e in entries],
            origin_role=manifest.origin_role,
            marking=manifest.marking,
        ))
        if recomputed.s1 != manifest.manifest_fingerprint:
            raise CorpusReadRefused(
                "manifest fingerprint does not agree with the stored entries")
        return self._verified(manifest, entries)

    def _verified(self, manifest: CorpusManifest, entries) -> object:
        from .model import CorpusReadSuccess
        return CorpusReadSuccess(manifest=manifest, entries=entries)

    # ------------------------------------------------------------------
    # Marking contract mirrors (defensive Python-side gates — OD-DI6 analog)
    # ------------------------------------------------------------------

    @staticmethod
    def allowed_origins() -> Tuple[str, ...]:
        return CORPUS_ORIGINS

    @staticmethod
    def allowed_markings() -> Tuple[str, ...]:
        return CORPUS_MARKINGS
