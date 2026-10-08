"""Extraction Evidence Binding — durable store + binder service (WP-3.2 MVP).

Binding basis: SPEC-WP32-EVB v1.0-MVP over the frozen WP-2.2 evidence pattern (same
governance, NEW layer — the reconstruction evidence log, capture store and reconstruction
store are consumed read-only through their own sanctioned interfaces and are NEVER
modified; the WP-3.1 extraction service is consumed through its public verified read).

Delegated implementation details declared here per D-09:
  OD-B1 storage mechanism : Python stdlib sqlite3, one SEPARATE embedded local DB file
                            (durable, local, zero network dependency); synchronous=FULL;
                            idempotent schema at initialization; isolation_level=None →
                            explicit BEGIN IMMEDIATE / COMMIT; append-only — no UPDATE
                            or DELETE path exists in code or API.
  OD-B2 tamper evidence   : binding_hash = sha256("ext-binding-chain:v1" +
                            prev_binding_hash + "\n" + binding_fingerprint); genesis
                            prev = 64 × "0"; appends serialized by BEGIN IMMEDIATE; a
                            log-head anchor (last_seq/last_hash) is written inside the
                            SAME append transaction so tail deletion is detected.
  OD-B3 ids               : binding_id = uuid4 hex; seq = log position (AUTOINCREMENT,
                            lastrowid coherence guard on every append).
  OD-B4 integrity anchor  : binding_fingerprint = sha256-v1 (reused capture S1
                            capability) over the canonical "ext-binding:v1" serialization
                            of the record scalars + all field entries in field_seq
                            order — recomputed on every verified read.
  OD-B5 INV-B-1:1         : at most one binding per extraction_id — in-transaction
                            uniqueness check + UNIQUE index backstop; replay is an
                            explicit outcome, never a silent no-op.
  OD-B6 clock             : reuses the single extraction-layer clock
                            (extraction.model.utc_now_iso) — no second clock.
  OD-B7 content-free      : field entries carry positions/fingerprints/names ONLY; no
                            value_verbatim/value_encoding ever enters a binding (values
                            live in the fingerprint-anchored extraction record; span
                            fidelity is proven by joining the two verified reads).

The binder verifies the WHOLE chain before it will bind or deliver:
  extraction verified read → fresh document verified read → reconstruction evidence
  verified read (DOCUMENT_COMPLETED anchor) → per-field span fidelity → atomic append;
  read_binding re-verifies every link INSIDE the read and attributes any failure to one
  coarse BindingLink, never delivering entries on a failed verdict.
"""
from __future__ import annotations

import sqlite3
import uuid
from typing import List, Optional, Sequence, Tuple

from capture import S1ComputationFailure, S1Service
from reconstruction import (
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadSuccess,
    DocumentReadVerificationUnavailable,
    EV_DOCUMENT_COMPLETED,
    EvidenceReadIntegrityFailure,
    EvidenceReadRefused,
    EvidenceReadSuccess,
    EvidenceReadVerificationUnavailable,
    EvidenceStore,
    PageView,
    ReconstructionService,
)

from .model import (
    ExtractedField,
    ExtractionReadIntegrityFailure,
    ExtractionReadRefused,
    ExtractionReadSuccess,
    ExtractionReadVerificationUnavailable,
    ExtractionRecord,
    utc_now_iso,
)
from .service import ExtractionService
from .binding_model import (
    BindingAlreadyExists,
    BindingChainReport,
    BindingCompleted,
    BindingDuplicate,
    BindingFieldEntry,
    BindingLink,
    BindingNotFound,
    BindingPersistenceUnavailable,
    BindingReadIntegrityFailure,
    BindingReadRefused,
    BindingReadSuccess,
    BindingReadVerificationUnavailable,
    BindingRef,
    BindingSourceIntegrityFailure,
    BindingSourceRefused,
    BindingSourceUnavailable,
    BindingStorageUnavailable,
    ExtractionBindingRecord,
)

_NOTE_VERIFY_FAILED = "verify FAILED"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS extraction_bindings (
    seq                              INTEGER PRIMARY KEY AUTOINCREMENT,
    binding_id                       TEXT NOT NULL UNIQUE,
    extraction_id                    TEXT NOT NULL UNIQUE,
    document_id                      TEXT NOT NULL,
    capture_id                       TEXT NOT NULL,
    capture_s1                       TEXT NOT NULL,
    capture_s1_algorithm_id          TEXT NOT NULL,
    extraction_record_fingerprint    TEXT NOT NULL,
    extraction_fingerprint_algorithm_id TEXT NOT NULL,
    recon_evidence_seq               INTEGER NOT NULL CHECK (recon_evidence_seq >= 1),
    recon_evidence_record_hash       TEXT NOT NULL,
    field_binding_count              INTEGER NOT NULL CHECK (field_binding_count >= 0),
    created_at                       TEXT NOT NULL,
    binding_fingerprint              TEXT NOT NULL,
    binding_fingerprint_algorithm_id TEXT NOT NULL,
    prev_binding_hash                TEXT NOT NULL,
    binding_hash                     TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS ix_binding_document
    ON extraction_bindings (document_id);

CREATE TABLE IF NOT EXISTS extraction_binding_fields (
    binding_id       TEXT NOT NULL REFERENCES extraction_bindings(binding_id),
    field_seq        INTEGER NOT NULL CHECK (field_seq >= 0),
    field_name       TEXT NOT NULL,
    page_index       INTEGER NOT NULL CHECK (page_index >= 0),
    byte_start       INTEGER NOT NULL CHECK (byte_start >= 0),
    byte_end         INTEGER NOT NULL CHECK (byte_end >= byte_start),
    page_fingerprint TEXT NOT NULL,
    PRIMARY KEY (binding_id, field_seq)
);

-- Log-head anchor (truncation guard) — written inside the SAME append transaction as
-- the new tail record (WP-2.2 evidence pattern): a deleted tail row or head row leaves
-- this anchor disagreeing with the log, detected on every verified read and audit.
CREATE TABLE IF NOT EXISTS binding_head (
    id        INTEGER PRIMARY KEY CHECK (id = 1),
    last_seq  INTEGER NOT NULL,
    last_hash TEXT NOT NULL
);
"""

GENESIS_HASH = "0" * 64
BINDING_DOMAIN = b"ext-binding:v1\n"
BINDING_CHAIN_DOMAIN = b"ext-binding-chain:v1\n"


def _chunk(value) -> bytes:
    """Deterministic length-prefixed encoding of one canonical element (house pattern)."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bool):                          # guard: bool before int
        raise TypeError("bool is not a canonical element")
    elif isinstance(value, int):
        raw = str(value).encode("ascii")
    else:
        raise TypeError(f"unsupported canonical element: {type(value)!r}")
    return len(raw).to_bytes(8, "big") + raw


def canonical_binding_bytes(record: ExtractionBindingRecord,
                            entries: Sequence[BindingFieldEntry]) -> bytes:
    """Canonical serialization fingerprinted by OD-B4 (deterministic, total).

    Order is fixed: record scalars (including seq and prev_binding_hash), then the field
    entries in field_seq order. The same (record, entries) ALWAYS yields the same bytes —
    the verified read recomputes exactly this over the durable rows.
    """
    parts: List[bytes] = [
        _chunk(record.seq),
        _chunk(record.binding_id),
        _chunk(record.extraction_id),
        _chunk(record.document_id),
        _chunk(record.capture_id),
        _chunk(record.capture_s1),
        _chunk(record.capture_s1_algorithm_id),
        _chunk(record.extraction_record_fingerprint),
        _chunk(record.extraction_fingerprint_algorithm_id),
        _chunk(record.recon_evidence_seq),
        _chunk(record.recon_evidence_record_hash),
        _chunk(record.field_binding_count),
        _chunk(record.created_at),
        _chunk(record.prev_binding_hash),
    ]
    for e in entries:
        parts += [
            _chunk(e.field_seq),
            _chunk(e.field_name),
            _chunk(e.page_index),
            _chunk(e.byte_start),
            _chunk(e.byte_end),
            _chunk(e.page_fingerprint),
        ]
    return BINDING_DOMAIN + b"".join(parts)


def _chain_bytes(prev_hash: str, fingerprint: str) -> bytes:
    """The exact bytes anchored by binding_hash — binds each record to its predecessor."""
    return BINDING_CHAIN_DOMAIN + prev_hash.encode("ascii") + b"\n" \
        + fingerprint.encode("ascii")


def _record_from_row(row: sqlite3.Row) -> ExtractionBindingRecord:
    return ExtractionBindingRecord(
        binding_id=row["binding_id"],
        seq=row["seq"],
        extraction_id=row["extraction_id"],
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        extraction_record_fingerprint=row["extraction_record_fingerprint"],
        extraction_fingerprint_algorithm_id=row["extraction_fingerprint_algorithm_id"],
        recon_evidence_seq=row["recon_evidence_seq"],
        recon_evidence_record_hash=row["recon_evidence_record_hash"],
        field_binding_count=row["field_binding_count"],
        created_at=row["created_at"],
        binding_fingerprint=row["binding_fingerprint"],
        binding_fingerprint_algorithm_id=row["binding_fingerprint_algorithm_id"],
        prev_binding_hash=row["prev_binding_hash"],
        binding_hash=row["binding_hash"],
    )


def _entry_from_row(row: sqlite3.Row) -> BindingFieldEntry:
    return BindingFieldEntry(
        field_seq=row["field_seq"],
        field_name=row["field_name"],
        page_index=row["page_index"],
        byte_start=row["byte_start"],
        byte_end=row["byte_end"],
        page_fingerprint=row["page_fingerprint"],
    )


# ---------------------------------------------------------------------------
# Store — append-only, tamper-evident binding log
# ---------------------------------------------------------------------------

class ExtractionBindingStore:
    """Durable local store for extraction evidence bindings.

    Owns: atomic binding+entries append, INV-B-1:1 uniqueness mechanics, fingerprint
    anchoring inputs, the global hash chain, chain/head verification primitives, and
    deterministic retrieval. Nothing else — no update, no delete, no content.
    """

    def __init__(self, db_path, s1: S1Service) -> None:
        self._db_path = str(db_path)
        self._s1 = s1
        self._conn = sqlite3.connect(self._db_path, timeout=30.0, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-B1: durability over speed
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "ExtractionBindingStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _safe_rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    # -- write path (single atomic transaction — OD-B1/OD-B2/OD-B5) ---------

    def commit_binding(self, *, extraction_id: str, document_id: str, capture_id: str,
                       capture_s1: str, capture_s1_algorithm_id: str,
                       extraction_record_fingerprint: str,
                       extraction_fingerprint_algorithm_id: str,
                       recon_evidence_seq: int, recon_evidence_record_hash: str,
                       entries: Sequence[BindingFieldEntry]) -> ExtractionBindingRecord:
        """Append binding + entries atomically. Raises:
          BindingDuplicate                — INV-B-1:1 extraction_id already bound
          BindingPersistenceUnavailable   — nothing recordable (txn rolled back)
        """
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._conn.execute(
                    "SELECT binding_id FROM extraction_bindings WHERE extraction_id = ?",
                    (extraction_id,)).fetchone()
                if existing is not None:
                    self._safe_rollback()
                    raise BindingDuplicate(existing["binding_id"])
                binding_id = uuid.uuid4().hex
                created_at = utc_now_iso()              # OD-B6: the single layer clock
                tail = self._conn.execute(
                    "SELECT seq, binding_hash FROM extraction_bindings "
                    "ORDER BY seq DESC LIMIT 1").fetchone()
                seq = (tail["seq"] + 1) if tail is not None else 1
                prev_hash = tail["binding_hash"] if tail is not None else GENESIS_HASH
                draft = ExtractionBindingRecord(
                    binding_id=binding_id, seq=seq, extraction_id=extraction_id,
                    document_id=document_id, capture_id=capture_id, capture_s1=capture_s1,
                    capture_s1_algorithm_id=capture_s1_algorithm_id,
                    extraction_record_fingerprint=extraction_record_fingerprint,
                    extraction_fingerprint_algorithm_id=extraction_fingerprint_algorithm_id,
                    recon_evidence_seq=recon_evidence_seq,
                    recon_evidence_record_hash=recon_evidence_record_hash,
                    field_binding_count=len(entries), created_at=created_at,
                    binding_fingerprint="", binding_fingerprint_algorithm_id="",
                    prev_binding_hash=prev_hash, binding_hash="")
                try:
                    fingerprint = self._s1.compute(
                        canonical_binding_bytes(draft, entries))
                except S1ComputationFailure as exc:
                    self._safe_rollback()
                    raise BindingPersistenceUnavailable(
                        f"fingerprint capability failure: {exc}") from exc
                final = ExtractionBindingRecord(
                    **{**draft.__dict__,
                       "binding_fingerprint": fingerprint.s1,
                       "binding_fingerprint_algorithm_id": fingerprint.s1_algorithm_id})
                binding_hash = self._s1.compute(_chain_bytes(prev_hash, fingerprint.s1)).s1
                final = ExtractionBindingRecord(
                    **{**final.__dict__, "binding_hash": binding_hash})
                cursor = self._conn.execute(
                    """INSERT INTO extraction_bindings (
                           binding_id, extraction_id, document_id, capture_id, capture_s1,
                           capture_s1_algorithm_id, extraction_record_fingerprint,
                           extraction_fingerprint_algorithm_id, recon_evidence_seq,
                           recon_evidence_record_hash, field_binding_count, created_at,
                           binding_fingerprint, binding_fingerprint_algorithm_id,
                           prev_binding_hash, binding_hash)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (final.binding_id, final.extraction_id, final.document_id,
                     final.capture_id, final.capture_s1, final.capture_s1_algorithm_id,
                     final.extraction_record_fingerprint,
                     final.extraction_fingerprint_algorithm_id, final.recon_evidence_seq,
                     final.recon_evidence_record_hash, final.field_binding_count,
                     final.created_at, final.binding_fingerprint,
                     final.binding_fingerprint_algorithm_id, final.prev_binding_hash,
                     final.binding_hash))
                if cursor.lastrowid != seq:             # seq/coherence guard (OD-B3)
                    self._safe_rollback()
                    raise BindingPersistenceUnavailable(
                        "binding seq anomaly; nothing appended")
                self._conn.executemany(
                    """INSERT INTO extraction_binding_fields (
                           binding_id, field_seq, field_name, page_index, byte_start,
                           byte_end, page_fingerprint)
                       VALUES (?,?,?,?,?,?,?)""",
                    [(final.binding_id, e.field_seq, e.field_name, e.page_index,
                      e.byte_start, e.byte_end, e.page_fingerprint) for e in entries])
                self._conn.execute(
                    """INSERT INTO binding_head (id, last_seq, last_hash) VALUES (1, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET last_seq = excluded.last_seq,
                                                     last_hash = excluded.last_hash""",
                    (seq, binding_hash))
                self._conn.execute("COMMIT")
                return final
            except (BindingDuplicate, BindingPersistenceUnavailable):
                raise                                   # already rolled back above
            except Exception:
                self._safe_rollback()                   # atomicity: nothing persisted
                raise
        except (BindingDuplicate, BindingPersistenceUnavailable):
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise BindingPersistenceUnavailable(f"binding commit failed: {exc}") from exc

    # -- read path (raw, verified-read-orchestrated by the service) ---------

    def get_binding(self, extraction_id: str) -> ExtractionBindingRecord:
        row = self._conn.execute(
            "SELECT * FROM extraction_bindings WHERE extraction_id = ?",
            (extraction_id,)).fetchone()
        if row is None:
            raise BindingNotFound(extraction_id)
        return _record_from_row(row)

    def find_by_extraction(self, extraction_id: str) -> Optional[ExtractionBindingRecord]:
        row = self._conn.execute(
            "SELECT * FROM extraction_bindings WHERE extraction_id = ?",
            (extraction_id,)).fetchone()
        return None if row is None else _record_from_row(row)

    def get_entries(self, binding_id: str) -> List[BindingFieldEntry]:
        rows = self._conn.execute(
            "SELECT * FROM extraction_binding_fields WHERE binding_id = ? "
            "ORDER BY field_seq", (binding_id,)).fetchall()
        return [_entry_from_row(r) for r in rows]

    def find_for_document(self, document_id: str) -> List[ExtractionBindingRecord]:
        """All bindings for a document — deterministic order (seq)."""
        rows = self._conn.execute(
            "SELECT * FROM extraction_bindings WHERE document_id = ? ORDER BY seq",
            (document_id,)).fetchall()
        return [_record_from_row(r) for r in rows]

    # -- chain verification primitives (shared by read + audit) -------------

    def head_agrees_with_log(self) -> Tuple[bool, Optional[int], Optional[str]]:
        """Truncation guard: the head anchor must match the actual log tail.
        An empty log (no rows, no head) is the only valid anchor-free state."""
        head = self._conn.execute(
            "SELECT last_seq, last_hash FROM binding_head WHERE id = 1").fetchone()
        stats = self._conn.execute(
            "SELECT COUNT(*) AS n, MAX(seq) AS m FROM extraction_bindings").fetchone()
        if head is None:
            if stats["n"]:
                return False, None, "head anchor missing while binding records exist"
            return True, None, None                     # valid empty log
        if head["last_seq"] != stats["m"]:
            return False, head["last_seq"], (
                f"binding log truncated or forged: head anchor says last_seq="
                f"{head['last_seq']} but the log's highest seq is {stats['m']}")
        tail = self._conn.execute(
            "SELECT binding_hash FROM extraction_bindings WHERE seq = ?",
            (head["last_seq"],)).fetchone()
        if tail is None or tail["binding_hash"] != head["last_hash"]:
            return False, head["last_seq"], "head anchor does not match the log tail record"
        return True, None, None

    def verify_chain_prefix(self, upto_seq: Optional[int]
                             ) -> Tuple[bool, Optional[int], Optional[str]]:
        """Re-verify every binding fingerprint (incl. its entries) and every chain link
        for seq ≤ upto_seq. Returns (ok, failure_seq, reason)."""
        if upto_seq is None:
            rows = self._conn.execute(
                "SELECT * FROM extraction_bindings ORDER BY seq").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM extraction_bindings WHERE seq <= ? ORDER BY seq",
                (upto_seq,)).fetchall()
        prev_hash = GENESIS_HASH
        prev_seq = 0
        for row in rows:
            if row["seq"] != prev_seq + 1:
                return False, row["seq"], f"sequence gap before seq {row['seq']}"
            record = _record_from_row(row)
            entries = self.get_entries(row["binding_id"])
            expected_fp = self._s1.compute(canonical_binding_bytes(record, entries)).s1
            if expected_fp != row["binding_fingerprint"]:
                return False, row["seq"], \
                    f"binding fingerprint mismatch at seq {row['seq']}"
            if row["prev_binding_hash"] != prev_hash:
                return False, row["seq"], f"chain link broken at seq {row['seq']}"
            expected_hash = self._s1.compute(
                _chain_bytes(prev_hash, row["binding_fingerprint"])).s1
            if expected_hash != row["binding_hash"]:
                return False, row["seq"], f"binding hash mismatch at seq {row['seq']}"
            prev_hash = row["binding_hash"]
            prev_seq = row["seq"]
        return True, None, None

    def verify_chain(self) -> BindingChainReport:
        """Verify every record and every chain link over the whole log (incl. the
        truncation guard against the head anchor)."""
        try:
            ok, failure_seq, reason = self.head_agrees_with_log()
            if not ok:
                stats = self._conn.execute(
                    "SELECT COUNT(*) AS n, MAX(seq) AS m FROM extraction_bindings"
                ).fetchone()
                return BindingChainReport(valid=False, records=stats["n"],
                                          last_seq=stats["m"], failure_seq=failure_seq,
                                          reason=reason)
            ok, failure_seq, reason = self.verify_chain_prefix(None)
            stats = self._conn.execute(
                "SELECT COUNT(*) AS n, MAX(seq) AS m FROM extraction_bindings").fetchone()
            return BindingChainReport(valid=ok, records=stats["n"], last_seq=stats["m"],
                                      failure_seq=failure_seq, reason=reason)
        except sqlite3.Error as exc:
            return BindingChainReport(valid=False, records=0, last_seq=None,
                                      failure_seq=None,
                                      reason=f"chain audit could not execute: {exc}")


# ---------------------------------------------------------------------------
# Binder service — the provable-chain orchestrator
# ---------------------------------------------------------------------------

class ExtractionEvidenceBinder:
    """Binds verified extraction records into durable, tamper-evident evidence and
    delivers them only through a fully re-verified read.

    Composed strictly from sanctioned interfaces: ExtractionService (verified extraction
    read + enumeration), ReconstructionService (fresh verified document read),
    EvidenceStore (verified reconstruction-evidence read — the DOCUMENT_COMPLETED
    anchor). It never writes to any of them and never reads raw artifacts in parallel.
    """

    def __init__(self, store: ExtractionBindingStore, extraction: ExtractionService,
                 reconstruction: ReconstructionService, evidence: EvidenceStore,
                 s1: S1Service) -> None:
        self._store = store
        self._extraction = extraction
        self._reconstruction = reconstruction
        self._evidence = evidence
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory

    # ------------------------------------------------------------------
    # Bind — whole-chain verification → atomic append (SPEC §3)
    # ------------------------------------------------------------------

    def bind_extraction(self, extraction_id: str) -> object:
        """Bind one verified extraction record. Outcome is exactly one explicit type:
          BindingCompleted | BindingAlreadyExists (INV-B-1:1 replay) |
          BindingSourceIntegrityFailure | BindingSourceRefused |
          BindingSourceUnavailable | BindingStorageUnavailable.
        """
        # Link 1: the bound artifact must itself verify (VOR read, same-read verdict).
        er = self._extraction.read_extraction(extraction_id)
        if isinstance(er, ExtractionReadRefused):
            return BindingSourceRefused(BindingLink.EXTRACTION,
                                        f"extraction refused: {er.detail}")
        if isinstance(er, ExtractionReadIntegrityFailure):
            return BindingSourceIntegrityFailure(
                BindingLink.EXTRACTION, f"extraction read FAILED: {er.reason}")
        if isinstance(er, ExtractionReadVerificationUnavailable):
            self._issues.append(f"bind {extraction_id}: extraction verification "
                                f"unavailable: {er.issue_report}")
            return BindingSourceUnavailable(BindingLink.EXTRACTION, er.issue_report)
        record: ExtractionRecord = er.extraction
        fields: Tuple[ExtractedField, ...] = er.fields

        # Link 2: the source document must verify FRESH, right now (no stale verdicts).
        dr = self._reconstruction.read_document(record.document_id)
        if isinstance(dr, DocumentReadIntegrityFailure):
            return BindingSourceIntegrityFailure(
                BindingLink.DOCUMENT, f"document read FAILED: {dr.reason}")
        if isinstance(dr, DocumentReadRefused):
            return BindingSourceRefused(
                BindingLink.DOCUMENT,
                f"document refused (state={dr.document_state}): {dr.detail}")
        if isinstance(dr, DocumentReadVerificationUnavailable):
            self._issues.append(f"bind {extraction_id}: document verification "
                                f"unavailable: {dr.issue_report}")
            return BindingSourceUnavailable(BindingLink.DOCUMENT, dr.issue_report)
        if (dr.document_id, dr.capture_id, dr.capture_s1, dr.page_count) != (
                record.document_id, record.capture_id, record.capture_s1,
                record.page_count):
            return BindingSourceIntegrityFailure(
                BindingLink.DOCUMENT,
                "extraction linkage disagrees with the current verified document read")

        # Link 3: the reconstruction evidence anchor must verify (chain read).
        if self._evidence is None:
            return BindingSourceRefused(
                BindingLink.EVIDENCE,
                "no reconstruction evidence store is wired; the DOCUMENT_COMPLETED "
                "anchor cannot be obtained and no binding is fabricated")
        ev = self._evidence.read_document_evidence(record.document_id)
        if isinstance(ev, EvidenceReadRefused):
            return BindingSourceRefused(
                BindingLink.EVIDENCE, f"reconstruction evidence refused: {ev.detail}")
        if isinstance(ev, EvidenceReadIntegrityFailure):
            return BindingSourceIntegrityFailure(
                BindingLink.EVIDENCE, f"reconstruction evidence FAILED: {ev.reason}")
        if isinstance(ev, EvidenceReadVerificationUnavailable):
            self._issues.append(f"bind {extraction_id}: evidence verification "
                                f"unavailable: {ev.issue_report}")
            return BindingSourceUnavailable(BindingLink.EVIDENCE, ev.issue_report)
        completed = [e for e in ev.events if e.event_type == EV_DOCUMENT_COMPLETED]
        if not completed:
            return BindingSourceRefused(
                BindingLink.EVIDENCE, "no DOCUMENT_COMPLETED evidence record exists")
        anchor = completed[-1]                  # deterministic: the newest completion

        # Link 4: per-field span fidelity + complete tiling (fail-closed).
        entries, detail = self._verify_spans(record, fields, dr)
        if detail is not None:
            return BindingSourceIntegrityFailure(BindingLink.SPAN, detail)

        # Atomic append with INV-B-1:1 (UNIQUE backstop + in-txn check).
        try:
            binding = self._store.commit_binding(
                extraction_id=record.extraction_id,
                document_id=record.document_id,
                capture_id=record.capture_id,
                capture_s1=record.capture_s1,
                capture_s1_algorithm_id=record.capture_s1_algorithm_id,
                extraction_record_fingerprint=record.record_fingerprint,
                extraction_fingerprint_algorithm_id=record.fingerprint_algorithm_id,
                recon_evidence_seq=anchor.seq,
                recon_evidence_record_hash=anchor.record_hash,
                entries=entries)
        except BindingDuplicate as exc:
            return BindingAlreadyExists(exc.binding_id, record.extraction_id)
        except BindingPersistenceUnavailable as exc:
            return BindingStorageUnavailable(str(exc))
        return BindingCompleted(binding, tuple(entries))

    # ------------------------------------------------------------------
    # Verified binding read — VOR over EVERY link (SPEC §4)
    # ------------------------------------------------------------------

    def read_binding(self, extraction_id: str) -> object:
        """Read one binding with a same-read VALID verdict over the whole provable
        chain. Outcomes: BindingReadSuccess | BindingReadIntegrityFailure (coarse link,
        entries NEVER delivered) | BindingReadRefused | BindingReadVerificationUnavailable.
        """
        now = utc_now_iso()
        # Link 1a: log coherence FIRST — a truncated/forged log must never masquerade
        # as "never bound" (the head anchor is checked before any refusal is possible).
        ok, failure_seq, reason = self._store.head_agrees_with_log()
        if not ok:
            return BindingReadIntegrityFailure(BindingLink.BINDING,
                                               reason or "head anchor mismatch",
                                               failure_seq, now)
        try:
            binding = self._store.get_binding(extraction_id)
        except BindingNotFound:
            return BindingReadRefused(extraction_id, "no binding exists for this extraction")
        entries = self._store.get_entries(binding.binding_id)

        # Link 1: the binding log itself (chain prefix + record fingerprint).
        ok, failure_seq, reason = self._store.verify_chain_prefix(binding.seq)
        if not ok:
            return BindingReadIntegrityFailure(BindingLink.BINDING,
                                               reason or "chain broken", failure_seq, now)
        if len(entries) != binding.field_binding_count:
            issue = (f"durable entry set inconsistent (field_binding_count="
                     f"{binding.field_binding_count}, rows={len(entries)})")
            self._issues.append(f"binding {binding.binding_id}: {issue}")
            return BindingReadVerificationUnavailable(binding.binding_id,
                                                      issue + " — Issue Report required")
        recomputed = canonical_binding_bytes(binding, entries)
        verdict = self._s1.verify(recomputed, binding.binding_fingerprint,
                                  binding.binding_fingerprint_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            issue = (f"binding verification unavailable: "
                     f"{verdict.reason or 'capability failure'}")
            self._issues.append(f"binding {binding.binding_id}: {issue}")
            return BindingReadVerificationUnavailable(binding.binding_id,
                                                      issue + " — Issue Report required")
        if verdict.outcome == "FAILED":
            return BindingReadIntegrityFailure(BindingLink.BINDING, _NOTE_VERIFY_FAILED,
                                               binding.seq, now)

        # Link 2: the bound extraction record.
        er = self._extraction.read_extraction(extraction_id)
        if isinstance(er, ExtractionReadRefused):
            return BindingReadIntegrityFailure(
                BindingLink.EXTRACTION,
                f"bound extraction is missing or refused: {er.detail}", None, now)
        if isinstance(er, ExtractionReadIntegrityFailure):
            return BindingReadIntegrityFailure(
                BindingLink.EXTRACTION, f"bound extraction FAILED: {er.reason}", None, now)
        if isinstance(er, ExtractionReadVerificationUnavailable):
            self._issues.append(f"binding {binding.binding_id}: extraction verification "
                                f"unavailable: {er.issue_report}")
            return BindingReadVerificationUnavailable(binding.binding_id,
                                                      er.issue_report
                                                      + " — Issue Report required")
        if (er.extraction.record_fingerprint != binding.extraction_record_fingerprint
                or (er.extraction.fingerprint_algorithm_id
                    != binding.extraction_fingerprint_algorithm_id)):
            return BindingReadIntegrityFailure(
                BindingLink.EXTRACTION,
                "extraction fingerprint no longer matches the anchored value", None, now)

        # Link 3: the source document (fresh verified read + linkage equality).
        dr = self._reconstruction.read_document(binding.document_id)
        if isinstance(dr, DocumentReadIntegrityFailure):
            return BindingReadIntegrityFailure(
                BindingLink.DOCUMENT, f"document read FAILED: {dr.reason}", None, now)
        if isinstance(dr, DocumentReadRefused):
            return BindingReadIntegrityFailure(
                BindingLink.DOCUMENT,
                f"bound document is missing or refused (state={dr.document_state})",
                None, now)
        if isinstance(dr, DocumentReadVerificationUnavailable):
            self._issues.append(f"binding {binding.binding_id}: document verification "
                                f"unavailable: {dr.issue_report}")
            return BindingReadVerificationUnavailable(binding.binding_id,
                                                      dr.issue_report
                                                      + " — Issue Report required")
        if (dr.document_id, dr.capture_id, dr.capture_s1) != (
                binding.document_id, binding.capture_id, binding.capture_s1):
            return BindingReadIntegrityFailure(
                BindingLink.DOCUMENT,
                "document linkage no longer matches the binding", None, now)

        # Link 4: the reconstruction evidence anchor.
        if self._evidence is None:
            return BindingReadIntegrityFailure(
                BindingLink.EVIDENCE,
                "no reconstruction evidence store is wired; the anchored evidence "
                "cannot be re-verified", None, now)
        ev = self._evidence.read_document_evidence(binding.document_id)
        if isinstance(ev, EvidenceReadRefused):
            return BindingReadIntegrityFailure(
                BindingLink.EVIDENCE,
                f"anchored reconstruction evidence is missing: {ev.detail}", None, now)
        if isinstance(ev, EvidenceReadIntegrityFailure):
            return BindingReadIntegrityFailure(
                BindingLink.EVIDENCE,
                f"anchored reconstruction evidence FAILED: {ev.reason}", None, now)
        if isinstance(ev, EvidenceReadVerificationUnavailable):
            self._issues.append(f"binding {binding.binding_id}: evidence verification "
                                f"unavailable: {ev.issue_report}")
            return BindingReadVerificationUnavailable(binding.binding_id,
                                                      ev.issue_report
                                                      + " — Issue Report required")
        completed = [e for e in ev.events if e.event_type == EV_DOCUMENT_COMPLETED]
        anchor = completed[-1] if completed else None
        if anchor is None or anchor.seq != binding.recon_evidence_seq \
                or anchor.record_hash != binding.recon_evidence_record_hash:
            return BindingReadIntegrityFailure(
                BindingLink.EVIDENCE,
                "reconstruction evidence anchor no longer matches the binding",
                None, now)

        # Link 5: span fidelity — entries vs extraction fields vs verified pages.
        detail = self._verify_entry_fidelity(binding, entries, er.fields, dr)
        if detail is not None:
            return BindingReadIntegrityFailure(BindingLink.SPAN, detail, None, now)

        return BindingReadSuccess(binding, tuple(entries), now)

    # ------------------------------------------------------------------
    # Enumeration + audit
    # ------------------------------------------------------------------

    def bindings_for_document(self, document_id: str) -> Tuple[BindingRef, ...]:
        """All bindings for a document — deterministic order (consumes
        extraction_ids_for_document through the extraction service; only EXISTING
        bindings are listed — a bound-less extraction is simply absent, never fabricated)."""
        refs: List[BindingRef] = []
        for extraction_id in self._extraction.extraction_ids_for_document(document_id):
            binding = self._store.find_by_extraction(extraction_id)
            if binding is not None:
                refs.append(BindingRef(extraction_id, binding.binding_id,
                                       binding.created_at))
        return tuple(refs)

    def verify_chain(self) -> BindingChainReport:
        """Whole-log audit (every record + every chain link + head anchor)."""
        return self._store.verify_chain()

    def issue_reports(self) -> list:
        """Accumulated Issue-Report items surfaced by this binder instance."""
        return list(self._issues)

    # ------------------------------------------------------------------
    # Span-fidelity cores (shared logic, fail-closed)
    # ------------------------------------------------------------------

    def _verify_spans(self, record: ExtractionRecord,
                      fields: Sequence[ExtractedField],
                      dr: DocumentReadSuccess) -> Tuple[Optional[List[BindingFieldEntry]],
                                                        Optional[str]]:
        """Bind-time gate: fields tile 0..N-1, every span names its page, page
        fingerprints match, and the durable slice decodes to the verbatim value.
        Returns (entries, None) or (None, failure detail)."""
        if len(fields) != record.field_count:
            return None, (f"extraction field set inconsistent "
                          f"(field_count={record.field_count}, rows={len(fields)})")
        pages = {p.page_index: p for p in dr.pages}
        entries: List[BindingFieldEntry] = []
        for i, field in enumerate(fields):
            if field.field_seq != i:
                return None, f"field tiling broken at position {i}"
            page = pages.get(field.span.page_index)
            if page is None:
                return None, f"field {i}: page {field.span.page_index} does not exist"
            if page.page_fingerprint != field.span.page_fingerprint:
                return None, f"field {i}: page fingerprint does not match the source page"
            if not (0 <= field.span.byte_start <= field.span.byte_end <= page.byte_len):
                return None, (f"field {i}: span "
                              f"[{field.span.byte_start},{field.span.byte_end}) out of "
                              f"bounds for page {field.span.page_index}")
            try:
                decoded = bytes(page.content)[field.span.byte_start:
                                              field.span.byte_end].decode(
                                                  field.value_encoding)
            except LookupError:
                return None, f"field {i}: unknown value_encoding {field.value_encoding}"
            except UnicodeDecodeError:
                return None, (f"field {i}: span bytes are not decodable with the "
                              f"declared value_encoding")
            if decoded != field.value_verbatim:
                return None, (f"field {i}: span bytes no longer decode to the extracted "
                              f"value (source drift or forgery)")
            entries.append(BindingFieldEntry(
                field_seq=field.field_seq, field_name=field.field_name,
                page_index=field.span.page_index, byte_start=field.span.byte_start,
                byte_end=field.span.byte_end,
                page_fingerprint=field.span.page_fingerprint))
        return entries, None

    def _verify_entry_fidelity(self, binding: ExtractionBindingRecord,
                               entries: Sequence[BindingFieldEntry],
                               fields: Sequence[ExtractedField],
                               dr: DocumentReadSuccess) -> Optional[str]:
        """Read-time gate: entries tile 0..N-1, mirror the extraction fields exactly,
        and every span still slices its verified page to the extracted value."""
        if len(entries) != binding.field_binding_count or len(entries) != len(fields):
            return "binding entry set does not tile the extraction field set"
        pages = {p.page_index: p for p in dr.pages}
        for i, (entry, field) in enumerate(zip(entries, fields)):
            if entry.field_seq != i or field.field_seq != i:
                return f"tiling broken at position {i}"
            if (entry.field_name != field.field_name
                    or entry.page_index != field.span.page_index
                    or entry.byte_start != field.span.byte_start
                    or entry.byte_end != field.span.byte_end
                    or entry.page_fingerprint != field.span.page_fingerprint):
                return f"entry {i} does not match the extraction field"
            page = pages.get(entry.page_index)
            if page is None:
                return f"entry {i}: page {entry.page_index} does not exist"
            if page.page_fingerprint != entry.page_fingerprint:
                return f"entry {i}: page fingerprint does not match the verified page"
            if not (0 <= entry.byte_start <= entry.byte_end <= page.byte_len):
                return (f"entry {i}: span [{entry.byte_start},{entry.byte_end}) out of "
                        f"bounds for page {entry.page_index}")
            try:
                decoded = bytes(page.content)[entry.byte_start:entry.byte_end].decode(
                    field.value_encoding)
            except LookupError:
                return f"entry {i}: unknown value_encoding {field.value_encoding}"
            except UnicodeDecodeError:
                return (f"entry {i}: span bytes are not decodable with the declared "
                        f"value_encoding")
            if decoded != field.value_verbatim:
                return (f"entry {i}: span bytes no longer decode to the extracted value "
                        f"(source drift or forgery)")
        return None
