"""Durable Identity Resolution store — WP-7.1 MVP implementation.

Binding basis: SPEC-WP71-IDRES §7/§8 (OD-IR1..OD-IR7). Same store pattern as
P1–P6.2: stdlib sqlite3, ONE separate embedded DB file, synchronous=FULL,
idempotent schema, explicit BEGIN IMMEDIATE / COMMIT, atomic multi-record
commit, in-transaction uniqueness checks + UNIQUE index backstops, sha256-v1
fingerprints over canonical byte serializations, Verify-on-Read raw access.

NO UPDATE and NO DELETE path exists in this store (OD-IR7; AST-proven by the
boundary tests). Nothing is interpreted here — no identity decision, no
scope decision, no duplicate judgment: only deterministic persistence
mechanics. The identity formula itself lives in the frozen P6.1 primitive
(OD-IR-G); this store only anchors the records that carry its outcomes.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional, Sequence

from capture import S1ComputationFailure, S1Service

from .model import (
    CAPTURE_SCOPED_REASONS,
    IDENTITY_ROLES,
    IDENTITY_SCOPES,
    IDENTITY_SCOPE_CAPTURE_SCOPED,
    IDENTITY_SCOPE_S2,
    IDENTITY_SOURCES,
    IDENTITY_SOURCE_S2,
    ORIGINS,
    IdentityDuplicateObservation,
    IdentityPersistenceUnavailable,
    IdentityResolutionRecord,
    IdentityRoleCandidateRow,
    ResolutionDuplicate,
    ResolutionNotFound,
    parse_field_seqs,
    serialize_field_seqs,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_resolutions (
    resolution_id              TEXT PRIMARY KEY,
    capture_s1                 TEXT NOT NULL,
    capture_s1_algorithm_id    TEXT NOT NULL,
    capture_id                 TEXT NOT NULL,
    document_id                TEXT NOT NULL,
    extraction_id              TEXT NOT NULL,
    normalization_id           TEXT NOT NULL,
    domain_state_id            TEXT NOT NULL,
    declared_origin            TEXT NOT NULL
                               CHECK (declared_origin IN
                                      ('KANDOO_SALE','HOLOO_CAPTURE',
                                       'OTHER_POS_CAPTURE')),
    binding_declaration_fingerprint TEXT NOT NULL,
    identity_scope             TEXT NOT NULL
                               CHECK (identity_scope IN ('S2',
                                                         'CAPTURE_SCOPED')),
    identity_source            TEXT NOT NULL
                               CHECK (identity_source IN
                                      ('','S2_EXTRACTED_VERIFIED')),
    identity_fingerprint       TEXT NOT NULL,
    scope_reason               TEXT NOT NULL,
    created_at                 TEXT NOT NULL,
    record_fingerprint         TEXT NOT NULL,
    fingerprint_algorithm_id   TEXT NOT NULL,
    -- OD-IR6: scope/source/fingerprint/reason consistency gates
    CHECK (identity_scope = 'S2'
           OR (identity_scope = 'CAPTURE_SCOPED'
               AND identity_fingerprint = ''
               AND identity_source = ''
               AND scope_reason IN
                   ('d03-incomplete-document-identity',
                    'd03-conflicting-document-identity',
                    'd03-document-identity-undetermined',
                    's2-not-attempted-state-not-valid'))),
    CHECK (identity_scope != 'S2'
           OR (identity_fingerprint != ''
               AND identity_source = 'S2_EXTRACTED_VERIFIED'
               AND scope_reason = ''))
);

-- OD-IR3: INV-IR-S1:1 storage backstop — at most ONE durable resolution per
-- capture artifact (D-02: S1 = the capture-level idempotency key; D-03:
-- S1 → capture idempotency; dispatch §7: no second identity may be created)
CREATE UNIQUE INDEX IF NOT EXISTS uq_identity_resolution_capture
    ON identity_resolutions (capture_s1);
-- deterministic duplicate-original selection + replay lookups
CREATE INDEX IF NOT EXISTS ix_identity_resolution_fingerprint
    ON identity_resolutions (identity_fingerprint, created_at, resolution_id);

CREATE TABLE IF NOT EXISTS identity_role_candidates (
    resolution_id          TEXT NOT NULL REFERENCES
                           identity_resolutions(resolution_id),
    role                   TEXT NOT NULL
                           CHECK (role IN ('INVOICE_NUMBER','INVOICE_DATE',
                                           'INVOICE_TOTAL')),
    source_field_name      TEXT NOT NULL,
    candidate_count        INTEGER NOT NULL CHECK (candidate_count >= 0),
    field_seqs             TEXT NOT NULL,
    resolved_field_seq     INTEGER,
    PRIMARY KEY (resolution_id, role),
    -- a resolved pointer can only exist for a single-candidate role
    CHECK (resolved_field_seq IS NULL OR candidate_count = 1),
    -- a zero-candidate role carries no field_seq evidence
    CHECK (candidate_count > 0 OR field_seqs = '')
);

CREATE TABLE IF NOT EXISTS identity_duplicate_observations (
    observation_id           TEXT NOT NULL UNIQUE,
    resolution_id            TEXT NOT NULL REFERENCES
                             identity_resolutions(resolution_id),
    original_resolution_id   TEXT NOT NULL,
    identity_fingerprint     TEXT NOT NULL,
    original_capture_s1      TEXT NOT NULL,
    duplicate_capture_s1     TEXT NOT NULL,
    created_at               TEXT NOT NULL,
    observation_fingerprint  TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL,
    -- a definite duplicate is BY DEFINITION a different capture (D-03)
    CHECK (original_capture_s1 != duplicate_capture_s1)
);

-- OD-IR3: INV-IR-DUP:1 storage backstop — at most ONE duplicate observation
-- per resolution (the duplicate fact is decided inside the resolution's own
-- atomic commit; history is never rewritten)
CREATE UNIQUE INDEX IF NOT EXISTS uq_identity_dup_observation_resolution
    ON identity_duplicate_observations (resolution_id);
"""


def _chunk(value) -> bytes:
    """Deterministic length-prefixed encoding of one canonical element (same
    encoding as every other layer)."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bool):                          # guard: bool before int
        raise TypeError("bool is not a canonical element")
    elif isinstance(value, int):
        raw = str(value).encode("ascii")
    else:
        raise TypeError(f"unsupported canonical element: {type(value)!r}")
    return len(raw).to_bytes(8, "big") + raw


def canonical_resolution_bytes(record: IdentityResolutionRecord,
                               role_rows: Sequence[
                                   IdentityRoleCandidateRow]) -> bytes:
    """Canonical serialization fingerprinted by OD-IR5 (record scalars + the
    role candidate rows in FROZEN role order — independent of row order)."""
    by_role = {row.role: row for row in role_rows}
    parts = [
        _chunk(record.resolution_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.capture_id),
        _chunk(record.document_id),
        _chunk(record.extraction_id),
        _chunk(record.normalization_id),
        _chunk(record.domain_state_id),
        _chunk(record.declared_origin),
        _chunk(record.binding_declaration_fingerprint),
        _chunk(record.identity_scope),
        _chunk(record.identity_source),
        _chunk(record.identity_fingerprint),
        _chunk(record.scope_reason),
        _chunk(record.created_at),
    ]
    for role in IDENTITY_ROLES:
        row = by_role.get(role)
        if row is None:
            continue
        parts += [
            _chunk(row.role),
            _chunk(row.source_field_name),
            _chunk(row.candidate_count),
            _chunk(serialize_field_seqs(row.field_seqs)),
            _chunk(row.resolved_field_seq
                   if row.resolved_field_seq is not None else -1),
        ]
    return b"".join(parts)


def canonical_observation_bytes(obs: IdentityDuplicateObservation) -> bytes:
    """Canonical serialization fingerprinted by OD-IR5 (observation scalars)."""
    return b"".join([
        _chunk(obs.observation_id),
        _chunk(obs.resolution_id),
        _chunk(obs.original_resolution_id),
        _chunk(obs.identity_fingerprint),
        _chunk(obs.original_capture_s1),
        _chunk(obs.duplicate_capture_s1),
        _chunk(obs.created_at),
    ])


def _resolution_from_row(row: sqlite3.Row) -> IdentityResolutionRecord:
    return IdentityResolutionRecord(
        resolution_id=row["resolution_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        capture_id=row["capture_id"],
        document_id=row["document_id"],
        extraction_id=row["extraction_id"],
        normalization_id=row["normalization_id"],
        domain_state_id=row["domain_state_id"],
        declared_origin=row["declared_origin"],
        binding_declaration_fingerprint=row[
            "binding_declaration_fingerprint"],
        identity_scope=row["identity_scope"],
        identity_source=row["identity_source"],
        identity_fingerprint=row["identity_fingerprint"],
        scope_reason=row["scope_reason"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _role_row_from_row(row: sqlite3.Row) -> IdentityRoleCandidateRow:
    return IdentityRoleCandidateRow(
        resolution_id=row["resolution_id"],
        role=row["role"],
        source_field_name=row["source_field_name"],
        candidate_count=row["candidate_count"],
        field_seqs=parse_field_seqs(row["field_seqs"]),
        resolved_field_seq=row["resolved_field_seq"],
    )


def _observation_from_row(row: sqlite3.Row) -> IdentityDuplicateObservation:
    return IdentityDuplicateObservation(
        observation_id=row["observation_id"],
        resolution_id=row["resolution_id"],
        original_resolution_id=row["original_resolution_id"],
        identity_fingerprint=row["identity_fingerprint"],
        original_capture_s1=row["original_capture_s1"],
        duplicate_capture_s1=row["duplicate_capture_s1"],
        created_at=row["created_at"],
        observation_fingerprint=row["observation_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


def _role_rows_in_role_order(
        rows: Sequence[IdentityRoleCandidateRow],
        resolution_id: str) -> List[IdentityRoleCandidateRow]:
    """Rebuild role rows with the resolution_id anchor + frozen role order
    (deterministic, independent of retrieval order)."""
    by_role = {row.role: row for row in rows}
    return [IdentityRoleCandidateRow(
        resolution_id=resolution_id,
        role=role,
        source_field_name=by_role[role].source_field_name,
        candidate_count=by_role[role].candidate_count,
        field_seqs=tuple(by_role[role].field_seqs),
        resolved_field_seq=by_role[role].resolved_field_seq)
        for role in IDENTITY_ROLES if role in by_role]


class IdentityResolutionStore:
    """Durable local store for identity resolutions + role candidate rows +
    duplicate observations.

    Owns: atomic resolution commit (OD-IR2), INV-IR-S1:1 / INV-IR-DUP:1
    backstops (OD-IR3), fingerprint anchoring (OD-IR5), deterministic
    retrieval, verified-read raw access. Nothing else — no identity decision,
    no scope decision, no duplicate judgment, no update, no delete."""

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        self._conn = sqlite3.connect(self._db_path, timeout=30,
                                     isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-IR1: durability
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "IdentityResolutionStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- write path: atomic resolution commit (OD-IR2) ----------------------

    def commit_resolution(self, record: IdentityResolutionRecord,
                          role_rows: Sequence[IdentityRoleCandidateRow],
                          observation: Optional[
                              IdentityDuplicateObservation]) \
            -> IdentityResolutionRecord:
        """Commit the resolution + its role candidate rows + (iff a definite
        duplicate was detected by the service) the observation — atomically.

        Raises:
          ResolutionDuplicate               — INV-IR-S1:1 already present
          IdentityPersistenceUnavailable    — nothing recordable (txn rolled
                                              back, zero residue)
        """
        self._validate_commit_shape(record, role_rows, observation)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_by_capture_in_txn(record.capture_s1)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise ResolutionDuplicate(existing.resolution_id)
                if observation is not None:
                    original = self._get_in_txn(
                        observation.original_resolution_id)
                    if original is None:
                        self._conn.execute("ROLLBACK")
                        raise IdentityPersistenceUnavailable(
                            "commit refused: the duplicate observation "
                            "references a resolution that does not exist")
                    if (original.identity_fingerprint
                            != observation.identity_fingerprint):
                        self._conn.execute("ROLLBACK")
                        raise IdentityPersistenceUnavailable(
                            "commit refused: the duplicate observation "
                            "fingerprint disagrees with the original "
                            "resolution")
                try:
                    rfp = self._s1.compute(
                        canonical_resolution_bytes(record, role_rows))
                except S1ComputationFailure as exc:
                    raise IdentityPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = IdentityResolutionRecord(
                    **{**record.__dict__,
                       "record_fingerprint": rfp.s1,
                       "fingerprint_algorithm_id": rfp.s1_algorithm_id})
                self._insert_resolution(final)
                self._insert_role_rows(role_rows)
                if observation is not None:
                    try:
                        ofp = self._s1.compute(
                            canonical_observation_bytes(observation))
                    except S1ComputationFailure as exc:
                        raise IdentityPersistenceUnavailable(
                            f"fingerprint capability failure: {exc}") from exc
                    final_obs = IdentityDuplicateObservation(
                        **{**observation.__dict__,
                           "observation_fingerprint": ofp.s1,
                           "fingerprint_algorithm_id": ofp.s1_algorithm_id})
                    self._insert_observation(final_obs)
                self._conn.execute("COMMIT")
                return final
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except sqlite3.Error as exc:
            raise IdentityPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _validate_commit_shape(self, record, role_rows, observation) -> None:
        """Defensive Python-side refusals mirroring every SQL CHECK (OD-IR6)
        — a malformed commit never reaches the transaction."""
        if record.identity_scope not in IDENTITY_SCOPES:
            raise IdentityPersistenceUnavailable(
                f"commit refused: identity_scope {record.identity_scope!r} "
                f"is outside the declared vocabulary")
        if record.identity_source not in IDENTITY_SOURCES:
            raise IdentityPersistenceUnavailable(
                f"commit refused: identity_source "
                f"{record.identity_source!r} is outside the declared "
                f"vocabulary")
        if record.declared_origin not in ORIGINS:
            raise IdentityPersistenceUnavailable(
                f"commit refused: declared_origin "
                f"{record.declared_origin!r} is outside the frozen origin "
                f"vocabulary")
        if record.identity_scope == IDENTITY_SCOPE_S2:
            if (not record.identity_fingerprint
                    or record.identity_source != IDENTITY_SOURCE_S2
                    or record.scope_reason != ""):
                raise IdentityPersistenceUnavailable(
                    "commit refused: an S2 resolution carries the "
                    "fingerprint, the verified source, and no scope reason")
            if len(role_rows) != 3:
                raise IdentityPersistenceUnavailable(
                    "commit refused: an S2 resolution carries exactly three "
                    "role candidate rows (the frozen D-02 roles)")
            for row in role_rows:
                if (row.candidate_count != 1
                        or row.resolved_field_seq is None
                        or len(row.field_seqs) != 1):
                    raise IdentityPersistenceUnavailable(
                        "commit refused: an S2 role candidate row resolves "
                        "exactly one candidate")
        else:
            if (record.identity_fingerprint != ""
                    or record.identity_source != ""
                    or record.scope_reason not in CAPTURE_SCOPED_REASONS):
                raise IdentityPersistenceUnavailable(
                    "commit refused: a CAPTURE_SCOPED resolution has no "
                    "fingerprint, no source, and a stable scope reason")
            if any(row.resolved_field_seq is not None
                   for row in role_rows):
                raise IdentityPersistenceUnavailable(
                    "commit refused: a CAPTURE_SCOPED resolution never "
                    "resolves a role candidate")
        if len(role_rows) > 3:
            raise IdentityPersistenceUnavailable(
                "commit refused: at most the three frozen D-02 role rows "
                "exist")
        by_role = {row.role for row in role_rows}
        if len(by_role) != len(role_rows):
            raise IdentityPersistenceUnavailable(
                "commit refused: duplicate role candidate rows")
        for row in role_rows:
            if row.role not in IDENTITY_ROLES:
                raise IdentityPersistenceUnavailable(
                    f"commit refused: role {row.role!r} is outside the "
                    f"frozen D-02 role vocabulary")
            if row.candidate_count != len(row.field_seqs):
                raise IdentityPersistenceUnavailable(
                    "commit refused: candidate_count disagrees with the "
                    "field_seq evidence")
            if row.candidate_count == 0 and row.field_seqs != ():
                raise IdentityPersistenceUnavailable(
                    "commit refused: a zero-candidate role carries no "
                    "field_seq evidence")
        if observation is not None:
            if (observation.resolution_id != record.resolution_id
                    or observation.identity_fingerprint
                    != record.identity_fingerprint):
                raise IdentityPersistenceUnavailable(
                    "commit refused: the observation must ride its own S2 "
                    "resolution and fingerprint")
            if (observation.original_capture_s1 == record.capture_s1
                    or observation.duplicate_capture_s1
                    != record.capture_s1):
                raise IdentityPersistenceUnavailable(
                    "commit refused: a definite duplicate observation "
                    "references a DIFFERENT original capture (D-03)")

    def _insert_resolution(self, record: IdentityResolutionRecord) -> None:
        self._conn.execute(
            """INSERT INTO identity_resolutions (
                   resolution_id, capture_s1, capture_s1_algorithm_id,
                   capture_id, document_id, extraction_id, normalization_id,
                   domain_state_id, declared_origin,
                   binding_declaration_fingerprint, identity_scope,
                   identity_source, identity_fingerprint, scope_reason,
                   created_at, record_fingerprint, fingerprint_algorithm_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record.resolution_id, record.capture_s1,
             record.capture_s1_algorithm_id, record.capture_id,
             record.document_id, record.extraction_id,
             record.normalization_id, record.domain_state_id,
             record.declared_origin, record.binding_declaration_fingerprint,
             record.identity_scope, record.identity_source,
             record.identity_fingerprint, record.scope_reason,
             record.created_at, record.record_fingerprint,
             record.fingerprint_algorithm_id))

    def _insert_role_rows(
            self, role_rows: Sequence[IdentityRoleCandidateRow]) -> None:
        self._conn.executemany(
            """INSERT INTO identity_role_candidates (
                   resolution_id, role, source_field_name, candidate_count,
                   field_seqs, resolved_field_seq)
               VALUES (?,?,?,?,?,?)""",
            [(row.resolution_id, row.role, row.source_field_name,
              row.candidate_count, serialize_field_seqs(row.field_seqs),
              row.resolved_field_seq) for row in role_rows])

    def _insert_observation(
            self, obs: IdentityDuplicateObservation) -> None:
        self._conn.execute(
            """INSERT INTO identity_duplicate_observations (
                   observation_id, resolution_id, original_resolution_id,
                   identity_fingerprint, original_capture_s1,
                   duplicate_capture_s1, created_at,
                   observation_fingerprint, fingerprint_algorithm_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (obs.observation_id, obs.resolution_id,
             obs.original_resolution_id, obs.identity_fingerprint,
             obs.original_capture_s1, obs.duplicate_capture_s1,
             obs.created_at, obs.observation_fingerprint,
             obs.fingerprint_algorithm_id))

    # -- read path: deterministic retrieval + verified-read raw access ------

    def get_resolution(self, resolution_id: str) \
            -> IdentityResolutionRecord:
        row = self._conn.execute(
            "SELECT * FROM identity_resolutions WHERE resolution_id = ?",
            (resolution_id,)).fetchone()
        if row is None:
            raise ResolutionNotFound(resolution_id)
        return _resolution_from_row(row)

    def _get_in_txn(self, resolution_id: str) \
            -> Optional[IdentityResolutionRecord]:
        row = self._conn.execute(
            "SELECT * FROM identity_resolutions WHERE resolution_id = ?",
            (resolution_id,)).fetchone()
        return _resolution_from_row(row) if row is not None else None

    def find_resolution_by_capture(self, capture_s1: str) \
            -> Optional[IdentityResolutionRecord]:
        return self._find_by_capture_in_txn(capture_s1)

    def _find_by_capture_in_txn(self, capture_s1: str) \
            -> Optional[IdentityResolutionRecord]:
        row = self._conn.execute(
            "SELECT * FROM identity_resolutions WHERE capture_s1 = ?",
            (capture_s1,)).fetchone()
        return _resolution_from_row(row) if row is not None else None

    def find_resolutions_by_identity(self, identity_fingerprint: str) \
            -> List[IdentityResolutionRecord]:
        """All resolutions carrying one document identity — deterministic
        order (created_at, resolution_id) so the ORIGINAL of a duplicate set
        is a pure function of the durable content (OD-IR-E)."""
        rows = self._conn.execute(
            """SELECT * FROM identity_resolutions
               WHERE identity_fingerprint = ?
               ORDER BY created_at, resolution_id""",
            (identity_fingerprint,)).fetchall()
        return [_resolution_from_row(r) for r in rows]

    def get_role_rows(self, resolution_id: str) \
            -> List[IdentityRoleCandidateRow]:
        rows = self._conn.execute(
            """SELECT * FROM identity_role_candidates
               WHERE resolution_id = ?""",
            (resolution_id,)).fetchall()
        return _role_rows_in_role_order(
            [_role_row_from_row(r) for r in rows], resolution_id)

    def get_observation(self, resolution_id: str) \
            -> Optional[IdentityDuplicateObservation]:
        row = self._conn.execute(
            """SELECT * FROM identity_duplicate_observations
               WHERE resolution_id = ?""",
            (resolution_id,)).fetchone()
        return _observation_from_row(row) if row is not None else None

    def list_resolutions(self) -> List[IdentityResolutionRecord]:
        rows = self._conn.execute(
            """SELECT * FROM identity_resolutions
               ORDER BY created_at, resolution_id""").fetchall()
        return [_resolution_from_row(r) for r in rows]
