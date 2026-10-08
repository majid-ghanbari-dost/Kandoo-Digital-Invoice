"""Reprint & Duplicate Flows durable store — WP-7.2 MVP implementation.

Binding basis: SPEC-WP72-DUPFLOW §7/§8 (OD-DF1..DF7). The project store
pattern, unchanged: stdlib sqlite3, ONE separate embedded DB file
(`duplicate-flows.db`), synchronous=FULL, idempotent schema, explicit
BEGIN IMMEDIATE / COMMIT, atomic single-row commit (zero residue on any
failure), immutable rows (no UPDATE / no DELETE — AST-proven), sha256-v1
record fingerprints computed through the project S1 service (no hashlib in
this layer — OD-DF5/OD-DF-C), Verify-on-Read support via canonical bytes,
SQL CHECK gates + defensive Python-side refusals mirroring every CHECK
(OD-DF6), UNIQUE(capture_s1) as the INV-DF-1:1 backstop (OD-DF3),
restart-safe.

The store knows NOTHING about identity semantics: it persists what the
service derived from WP-7.1 outcomes and enforces the §7 shapes.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from capture import S1ComputationFailure, S1Service

from .model import (
    DURABLE_FLOW_OUTCOMES,
    FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
    FLOW_OUTCOME_IDENTITY_ESTABLISHED,
    LINKED_IDENTITY_SCOPES,
    ORIGINS,
    DispositionDuplicate,
    DispositionNotFound,
    FlowDispositionRecord,
    FlowPersistenceUnavailable,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS flow_dispositions (
    disposition_id            TEXT PRIMARY KEY,
    capture_s1                TEXT NOT NULL UNIQUE,
    capture_s1_algorithm_id   TEXT NOT NULL,
    capture_id                TEXT NOT NULL,
    document_id               TEXT NOT NULL,
    resolution_id             TEXT NOT NULL,
    original_resolution_id    TEXT NOT NULL,
    duplicate_observation_id  TEXT NOT NULL,
    declared_origin           TEXT NOT NULL,
    flow_outcome              TEXT NOT NULL,
    identity_scope            TEXT NOT NULL,
    identity_fingerprint      TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    record_fingerprint        TEXT NOT NULL,
    fingerprint_algorithm_id  TEXT NOT NULL,
    -- OD-DF6: outcome/reference shape + scope/fingerprint consistency gates
    CHECK (flow_outcome IN ('IDENTITY_ESTABLISHED', 'DUPLICATE_RECOGNIZED')),
    CHECK (declared_origin IN ('KANDOO_SALE', 'HOLOO_CAPTURE',
                               'OTHER_POS_CAPTURE')),
    CHECK (identity_scope IN ('S2', 'CAPTURE_SCOPED')),
    CHECK (flow_outcome != 'IDENTITY_ESTABLISHED'
           OR (original_resolution_id = ''
               AND duplicate_observation_id = '')),
    CHECK (flow_outcome != 'DUPLICATE_RECOGNIZED'
           OR (original_resolution_id != ''
               AND duplicate_observation_id != '')),
    CHECK (identity_scope != 'S2' OR identity_fingerprint != ''),
    CHECK (identity_scope != 'CAPTURE_SCOPED'
           OR identity_fingerprint = '')
)
"""


def canonical_disposition_bytes(record: FlowDispositionRecord) -> bytes:
    """Deterministic serialization of the disposition scalars — the VOR
    anchor payload (OD-DF5). Field order is fixed by the dataclass; no
    mapping iteration anywhere."""
    parts = [
        b"flow-disposition-v1",
        record.disposition_id.encode("utf-8"),
        record.capture_s1.encode("utf-8"),
        record.capture_s1_algorithm_id.encode("utf-8"),
        record.capture_id.encode("utf-8"),
        record.document_id.encode("utf-8"),
        record.resolution_id.encode("utf-8"),
        record.original_resolution_id.encode("utf-8"),
        record.duplicate_observation_id.encode("utf-8"),
        record.declared_origin.encode("utf-8"),
        record.flow_outcome.encode("utf-8"),
        record.identity_scope.encode("utf-8"),
        record.identity_fingerprint.encode("utf-8"),
        record.created_at.encode("utf-8"),
    ]
    return b"\x1f".join(parts)


def _disposition_from_row(row: sqlite3.Row) -> FlowDispositionRecord:
    return FlowDispositionRecord(
        disposition_id=row["disposition_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        capture_id=row["capture_id"],
        document_id=row["document_id"],
        resolution_id=row["resolution_id"],
        original_resolution_id=row["original_resolution_id"],
        duplicate_observation_id=row["duplicate_observation_id"],
        declared_origin=row["declared_origin"],
        flow_outcome=row["flow_outcome"],
        identity_scope=row["identity_scope"],
        identity_fingerprint=row["identity_fingerprint"],
        created_at=row["created_at"],
        record_fingerprint=row["record_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


class FlowDispositionStore:
    """Durable, immutable flow-disposition store (OD-DF1..DF7)."""

    def __init__(self, db_path, s1: S1Service) -> None:
        self._s1 = s1
        try:
            self._conn = sqlite3.connect(str(db_path), isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.executescript(_SCHEMA)
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_fd_capture_s1 "
                "ON flow_dispositions(capture_s1)")
        except sqlite3.Error as exc:
            raise FlowPersistenceUnavailable(
                f"store unavailable: {exc}") from exc

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "FlowDispositionStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Commit (single row — atomic by construction, OD-DF2)
    # ------------------------------------------------------------------

    def commit_disposition(self, record: FlowDispositionRecord) \
            -> FlowDispositionRecord:
        """Commit ONE disposition. Raises:
          DispositionDuplicate             — INV-DF-1:1 already present
          FlowPersistenceUnavailable       — nothing recordable (txn rolled
                                             back, zero residue)
        """
        self._validate_commit_shape(record)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._find_by_capture_in_txn(record.capture_s1)
                if existing is not None:
                    self._conn.execute("ROLLBACK")
                    raise DispositionDuplicate(existing.disposition_id)
                try:
                    fp = self._s1.compute(canonical_disposition_bytes(record))
                except S1ComputationFailure as exc:
                    raise FlowPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = FlowDispositionRecord(
                    **{**record.__dict__,
                       "record_fingerprint": fp.s1,
                       "fingerprint_algorithm_id": fp.s1_algorithm_id})
                self._conn.execute(
                    "INSERT INTO flow_dispositions ("
                    "disposition_id, capture_s1, capture_s1_algorithm_id, "
                    "capture_id, document_id, resolution_id, "
                    "original_resolution_id, duplicate_observation_id, "
                    "declared_origin, flow_outcome, identity_scope, "
                    "identity_fingerprint, created_at, record_fingerprint, "
                    "fingerprint_algorithm_id) VALUES (?,?,?,?,?,?,?,?,?"
                    ",?,?,?,?,?,?)",
                    (final.disposition_id, final.capture_s1,
                     final.capture_s1_algorithm_id, final.capture_id,
                     final.document_id, final.resolution_id,
                     final.original_resolution_id,
                     final.duplicate_observation_id, final.declared_origin,
                     final.flow_outcome, final.identity_scope,
                     final.identity_fingerprint, final.created_at,
                     final.record_fingerprint, final.fingerprint_algorithm_id))
                self._conn.execute("COMMIT")
                return final
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
        except sqlite3.Error as exc:
            raise FlowPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc

    def _validate_commit_shape(self, record: FlowDispositionRecord) -> None:
        """Defensive Python-side refusals mirroring every SQL CHECK (OD-DF6)
        — a malformed commit never reaches the transaction."""
        if record.flow_outcome not in DURABLE_FLOW_OUTCOMES:
            raise FlowPersistenceUnavailable(
                "commit refused: flow_outcome "
                f"{record.flow_outcome!r} is not a durable outcome "
                "(REPRINT_RECOGNIZED is a call outcome only)")
        if record.declared_origin not in ORIGINS:
            raise FlowPersistenceUnavailable(
                f"commit refused: declared_origin {record.declared_origin!r} "
                "is outside the frozen origin vocabulary")
        if record.identity_scope not in LINKED_IDENTITY_SCOPES:
            raise FlowPersistenceUnavailable(
                f"commit refused: identity_scope "
                f"{record.identity_scope!r} is outside the linked frozen "
                "scope vocabulary")
        if record.flow_outcome == FLOW_OUTCOME_IDENTITY_ESTABLISHED:
            if (record.original_resolution_id != ""
                    or record.duplicate_observation_id != ""):
                raise FlowPersistenceUnavailable(
                    "commit refused: IDENTITY_ESTABLISHED with duplicate "
                    "references")
        else:
            if (record.original_resolution_id == ""
                    or record.duplicate_observation_id == ""):
                raise FlowPersistenceUnavailable(
                    "commit refused: DUPLICATE_RECOGNIZED without the "
                    "original/observation references")
        if record.identity_scope == "S2":
            if record.identity_fingerprint == "":
                raise FlowPersistenceUnavailable(
                    "commit refused: S2 scope with an empty fingerprint")
        else:
            if record.identity_fingerprint != "":
                raise FlowPersistenceUnavailable(
                    "commit refused: CAPTURE_SCOPED scope with a "
                    "fingerprint")
        for field in ("disposition_id", "capture_s1",
                      "capture_s1_algorithm_id", "capture_id", "document_id",
                      "resolution_id", "created_at"):
            if not getattr(record, field):
                raise FlowPersistenceUnavailable(
                    f"commit refused: empty required field {field!r}")

    # ------------------------------------------------------------------
    # Reads (raw rows — verified views live in the service, SPEC §6)
    # ------------------------------------------------------------------

    def get_disposition(self, disposition_id: str) -> FlowDispositionRecord:
        try:
            row = self._conn.execute(
                "SELECT * FROM flow_dispositions WHERE disposition_id = ?",
                (disposition_id,)).fetchone()
        except sqlite3.Error as exc:
            raise FlowPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        if row is None:
            raise DispositionNotFound(disposition_id)
        return _disposition_from_row(row)

    def find_disposition_by_capture(self, capture_s1: str) \
            -> Optional[FlowDispositionRecord]:
        try:
            row = self._conn.execute(
                "SELECT * FROM flow_dispositions WHERE capture_s1 = ?",
                (capture_s1,)).fetchone()
        except sqlite3.Error as exc:
            raise FlowPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return _disposition_from_row(row) if row is not None else None

    def _find_by_capture_in_txn(self, capture_s1: str) \
            -> Optional[FlowDispositionRecord]:
        row = self._conn.execute(
            "SELECT * FROM flow_dispositions WHERE capture_s1 = ?",
            (capture_s1,)).fetchone()
        return _disposition_from_row(row) if row is not None else None

    def find_dispositions_by_original(self, original_resolution_id: str) \
            -> List[FlowDispositionRecord]:
        """The durable duplicate register (OD-DF-H): every committed
        DUPLICATE_RECOGNIZED disposition anchored to that original — raw
        records; consumers verify through the service read paths."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM flow_dispositions "
                "WHERE original_resolution_id = ? AND flow_outcome = ? "
                "ORDER BY created_at, disposition_id",
                (original_resolution_id,
                 FLOW_OUTCOME_DUPLICATE_RECOGNIZED)).fetchall()
        except sqlite3.Error as exc:
            raise FlowPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_disposition_from_row(row) for row in rows]

    def list_dispositions(self) -> List[FlowDispositionRecord]:
        try:
            rows = self._conn.execute(
                "SELECT * FROM flow_dispositions "
                "ORDER BY created_at, disposition_id").fetchall()
        except sqlite3.Error as exc:
            raise FlowPersistenceUnavailable(
                f"persistence unavailable: {exc}") from exc
        return [_disposition_from_row(row) for row in rows]
