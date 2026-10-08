"""Durable Document/Page Store — WP-2.1 MVP implementation (T-2.1.2 scope).

Binding basis: SPEC-WP21-RC v1.0-MVP over the frozen WP-1.1 pattern (same governance,
new layer — the capture store is NOT modified; AD-02 layer boundary).

Delegated implementation details declared here per D-09 (each satisfies its constraint):
  OD-R1 storage mechanism : Python stdlib sqlite3, one SEPARATE embedded local DB file
                            (durable, local, zero network dependency); synchronous=FULL;
                            idempotent schema at initialization; isolation_level=None →
                            explicit BEGIN IMMEDIATE / COMMIT.
  OD-R2 ids               : document_id = uuid4 hex; page_ref = "recon-page:v1:<uuid4hex>".
  OD-R3 durability        : SQLite journaling with synchronous=FULL; record-first (ACTIVE
                            document before page persist) so interruptions leave recoverable
                            residue; D-1 analog = synchronous settlement on definitive page
                            persist error; D-2 analog = StorageUnavailable when no verdict is
                            durably recordable.
  OD-R4 INV-R-1:1 UAC     : BEGIN IMMEDIATE atomic decision + uniqueness check INSIDE the
                            same transaction + explicit loser outcome + fail-closed on
                            storage errors + partial UNIQUE index backstop
                            (uq_completed_capture: at most one COMPLETED document per
                            capture_id) — the same mechanism shape as capture INV-C3.
  OD-R5 page ordering     : pages keyed (document_id, page_index); page_index 0-based,
                            contiguous; read order = ORDER BY page_index.
  OD-R6 clock             : single reconstruction-layer clock (model.utc_now_iso).
  OD-R7 ACTIVE enumeration: partial index on document_state='ACTIVE'.

The store stores fingerprints as opaque strings and never interprets content semantics;
page bytes are persisted verbatim (byte-exact retrieval, no update/delete path exists).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .model import (
    NOTE_PAGE_PERSIST_FAILED,
    DocumentCreationFailed,
    DocumentIntegrity,
    DocumentNotFound,
    DocumentRecord,
    DocumentState,
    CompletionGateUnmet,
    IllegalFieldWrite,
    IllegalTransition,
    ExplicitPersistenceFailure,
    PageContentMissing,
    PageRecord,
    ReconstructionLayerError,
    StorageUnavailable,
    UAC_GRANTED,
    UAC_UNIQUENESS_CONFLICT,
    utc_now_iso,
)

_PAGE_REF_PREFIX = "recon-page:v1:"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reconstruction_documents (
    document_id             TEXT PRIMARY KEY,
    capture_id              TEXT NOT NULL,
    capture_s1              TEXT NOT NULL,
    capture_s1_algorithm_id TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    document_state          TEXT NOT NULL
        CHECK (document_state IN ('ACTIVE', 'COMPLETED', 'FAILED_INCOMPLETE')),
    integrity_status        TEXT NOT NULL
        CHECK (integrity_status IN ('UNVERIFIED', 'VALID', 'FAILED')),
    integrity_verified_at   TEXT,
    page_count              INTEGER,
    document_fingerprint    TEXT,
    fingerprint_algorithm_id TEXT,
    settlement_note         TEXT,
    -- INV-R-C1: COMPLETED carries the full structure/anchor field set
    CHECK (document_state <> 'COMPLETED' OR (
        page_count IS NOT NULL AND document_fingerprint IS NOT NULL
        AND fingerprint_algorithm_id IS NOT NULL)),
    -- FAILED_INCOMPLETE is settled explicitly, integrity FAILED pinned
    CHECK (document_state <> 'FAILED_INCOMPLETE' OR (
        settlement_note IS NOT NULL AND integrity_status = 'FAILED')),
    -- settlement_note is meaningless on COMPLETED and stays empty
    CHECK (document_state <> 'COMPLETED' OR settlement_note IS NULL),
    -- a COMPLETED document is never UNVERIFIED
    CHECK (NOT (document_state = 'COMPLETED' AND integrity_status = 'UNVERIFIED'))
);

CREATE TABLE IF NOT EXISTS document_pages (
    document_id              TEXT NOT NULL,
    page_index               INTEGER NOT NULL,
    page_ref                 TEXT NOT NULL,
    content                  BLOB NOT NULL,
    byte_len                 INTEGER NOT NULL,
    page_fingerprint         TEXT NOT NULL,
    fingerprint_algorithm_id TEXT NOT NULL,
    PRIMARY KEY (document_id, page_index)
);

-- INV-R-1:1 storage-level backstop: at most one COMPLETED document per capture_id,
-- enforced by SQLite itself, under any concurrency, on any path.
CREATE UNIQUE INDEX IF NOT EXISTS uq_completed_capture
    ON reconstruction_documents (capture_id) WHERE document_state = 'COMPLETED';

-- OD-R7: complete ACTIVE enumeration
CREATE INDEX IF NOT EXISTS ix_active_documents
    ON reconstruction_documents (document_id) WHERE document_state = 'ACTIVE';
"""


@dataclass(frozen=True)
class _Row:
    """Internal raw row access inside transactions (state as text)."""
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    created_at: str
    document_state: str
    integrity_status: str
    integrity_verified_at: Optional[str]
    page_count: Optional[int]
    document_fingerprint: Optional[str]
    fingerprint_algorithm_id: Optional[str]
    settlement_note: Optional[str]


def _record_from_row(row: sqlite3.Row) -> DocumentRecord:
    return DocumentRecord(
        document_id=row["document_id"],
        capture_id=row["capture_id"],
        capture_s1=row["capture_s1"],
        capture_s1_algorithm_id=row["capture_s1_algorithm_id"],
        created_at=row["created_at"],
        document_state=DocumentState(row["document_state"]),
        integrity_status=DocumentIntegrity(row["integrity_status"]),
        integrity_verified_at=row["integrity_verified_at"],
        page_count=row["page_count"],
        document_fingerprint=row["document_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
        settlement_note=row["settlement_note"],
    )


def _page_from_row(row: sqlite3.Row) -> PageRecord:
    return PageRecord(
        document_id=row["document_id"],
        page_index=row["page_index"],
        page_ref=row["page_ref"],
        content=bytes(row["content"]),
        byte_len=row["byte_len"],
        page_fingerprint=row["page_fingerprint"],
        fingerprint_algorithm_id=row["fingerprint_algorithm_id"],
    )


class ReconstructionStore:
    """Durable local store for Documents + ordered page bytes (T-2.1.2 scope).

    Owns: document durability, verbatim page durability, document↔pages binding,
    lifecycle transition mechanics, deterministic settlement, the INV-R-1:1 completion
    primitive, COMPLETED-restricted capture lookup, ACTIVE enumeration, restricted
    verification-outcome writes, and the completion gate. Nothing else.
    """

    def __init__(self, db_path) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, timeout=30.0, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        self._conn.execute("PRAGMA synchronous = FULL")   # OD-R3: durability over speed
        self._conn.executescript(_SCHEMA)

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "ReconstructionStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- internal helpers ----------------------------------------------------

    def _safe_rollback(self) -> None:
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _fetch_raw(self, document_id: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM reconstruction_documents WHERE document_id = ?", (document_id,)
        ).fetchone()

    def _page_indices(self, document_id: str) -> List[int]:
        rows = self._conn.execute(
            "SELECT page_index FROM document_pages WHERE document_id = ? ORDER BY page_index",
            (document_id,),
        ).fetchall()
        return [r["page_index"] for r in rows]

    # ------------------------------------------------------------------
    # Record-first (OD-R3) — ACTIVE document before any page persist
    # ------------------------------------------------------------------

    def create_active_document(
        self,
        capture_id: str,
        capture_s1: str,
        capture_s1_algorithm_id: str,
        document_fingerprint: str,
        fingerprint_algorithm_id: str,
    ) -> DocumentRecord:
        """Create the ACTIVE document with the full traceability binding + integrity
        anchor BEFORE any page persist (record-first). Traceability fields are verbatim
        from the verified capture read — no guessing anywhere."""
        from uuid import uuid4
        if not capture_id or not capture_s1 or not capture_s1_algorithm_id \
                or not document_fingerprint or not fingerprint_algorithm_id:
            # Traceability binding is verbatim-but-mandatory: empty fields are an illegal
            # write attempt (mirrors the capture store's INV-C1 attach gate).
            raise IllegalFieldWrite(
                "capture_id, capture_s1, capture_s1_algorithm_id, document_fingerprint and "
                "fingerprint_algorithm_id must be non-empty (INV-R-C1)")
        document_id = uuid4().hex
        created_at = utc_now_iso()
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                """INSERT INTO reconstruction_documents (
                       document_id, capture_id, capture_s1, capture_s1_algorithm_id,
                       created_at, document_state, integrity_status, integrity_verified_at,
                       page_count, document_fingerprint, fingerprint_algorithm_id, settlement_note)
                   VALUES (?, ?, ?, ?, ?, 'ACTIVE', 'UNVERIFIED', NULL, NULL, ?, ?, NULL)""",
                (document_id, capture_id, capture_s1, capture_s1_algorithm_id,
                 created_at, document_fingerprint, fingerprint_algorithm_id),
            )
            self._conn.execute("COMMIT")
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise DocumentCreationFailed(
                f"document creation failed (nothing persisted): {exc}") from exc
        return self.get_document(document_id)

    # ------------------------------------------------------------------
    # Verbatim page persist — one atomic txn for the whole page set
    # ------------------------------------------------------------------

    def persist_pages(
        self,
        document_id: str,
        pages: Sequence[Tuple[bytes, str, str]],
    ) -> None:
        """Persist ordered page bytes verbatim + per-page fingerprints, atomically with
        the page_count finalization. ACTIVE-only, one-time.

        `pages` = ordered (content, page_fingerprint, fingerprint_algorithm_id) tuples.
        Definitive persist error → D-1 analog: synchronous settlement, then explicit raise.
        """
        from uuid import uuid4
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_raw(document_id)
            if row is None:
                raise DocumentNotFound(f"no such document: {document_id}")
            if row["document_state"] != DocumentState.ACTIVE.value:
                raise IllegalTransition(
                    f"page persist requires ACTIVE; document is {row['document_state']}")
            if row["page_count"] is not None:
                raise IllegalFieldWrite(
                    "pages already persisted (one-time binding; page set is immutable)")
            for index, (content, page_fp, fp_id) in enumerate(pages):
                if not page_fp or not fp_id:
                    raise IllegalFieldWrite(
                        f"page {index}: fingerprint and algorithm id are mandatory")
                data = bytes(content)
                self._conn.execute(
                    """INSERT INTO document_pages (
                           document_id, page_index, page_ref, content, byte_len,
                           page_fingerprint, fingerprint_algorithm_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (document_id, index, _PAGE_REF_PREFIX + uuid4().hex,
                     sqlite3.Binary(data), len(data), page_fp, fp_id),
                )
            self._conn.execute(
                "UPDATE reconstruction_documents SET page_count = ? WHERE document_id = ?",
                (len(pages), document_id),
            )
            self._conn.execute("COMMIT")
        except ReconstructionLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            # D-1 analog: definitive persist error returned to the live store →
            # synchronous settlement inside the same attempt; never left ACTIVE.
            try:
                self.settle_failed(document_id, NOTE_PAGE_PERSIST_FAILED)
            except ReconstructionLayerError as settle_exc:
                raise StorageUnavailable(
                    f"page persist failed and the D-1 settlement write also failed "
                    f"(D-2 residue; startup recovery will settle): {settle_exc}") from settle_exc
            raise ExplicitPersistenceFailure(
                document_id, NOTE_PAGE_PERSIST_FAILED,
                f"page persist failed; settled FAILED_INCOMPLETE synchronously: {exc}") from exc

    # ------------------------------------------------------------------
    # Restricted verification-outcome writer (the ONLY writer of integrity fields)
    # ------------------------------------------------------------------

    def record_verification(self, document_id: str, verdict: str, verified_at: str) -> None:
        """Record an executed verification result (document-level verdict).
        verdict must be VALID | FAILED — UNVERIFIED is never a verification result.
        FAILED_INCOMPLETE documents are rejected: their FAILED is pinned at settlement."""
        if verdict not in ("VALID", "FAILED"):
            raise IllegalFieldWrite(
                f"illegal verification verdict {verdict!r}: only VALID | FAILED are writable")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_raw(document_id)
            if row is None:
                raise DocumentNotFound(f"no such document: {document_id}")
            if row["document_state"] == DocumentState.FAILED_INCOMPLETE.value:
                raise IllegalTransition(
                    "integrity fields of a settled FAILED_INCOMPLETE document are pinned "
                    "— verification may not rewrite them")
            self._conn.execute(
                "UPDATE reconstruction_documents SET integrity_status = ?, integrity_verified_at = ? "
                "WHERE document_id = ?",
                (verdict, verified_at, document_id),
            )
            self._conn.execute("COMMIT")
        except ReconstructionLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise StorageUnavailable(
                f"verification-outcome write failed (D-2 residue): {exc}") from exc

    # ------------------------------------------------------------------
    # INV-R-1:1 completion primitive (UAC shape — the ONLY completion path)
    # ------------------------------------------------------------------

    def complete_document(self, document_id: str) -> str:
        """ACTIVE → COMPLETED, uniqueness-atomically (INV-R-1:1).

        Completion gate (fail-closed): ACTIVE; page_count finalized AND matches the
        durable page rows with contiguous 0..n-1 indices; document_fingerprint present;
        first verification VALID; no other COMPLETED document for the same capture_id.

        Returns UAC_GRANTED or UAC_UNIQUENESS_CONFLICT (explicit loser outcome — the
        document is left untouched; settlement is the caller's directive).
        """
        try:
            self._conn.execute("BEGIN IMMEDIATE")              # atomic decision point
            row = self._fetch_raw(document_id)
            if row is None:
                raise DocumentNotFound(f"no such document: {document_id}")
            if row["document_state"] != DocumentState.ACTIVE.value:
                raise IllegalTransition(
                    f"completion requires ACTIVE; document is {row['document_state']} "
                    "(terminal states never change)")
            if row["page_count"] is None:
                raise CompletionGateUnmet("pages not persisted (record-first completion gate)")
            if not row["document_fingerprint"] or not row["fingerprint_algorithm_id"]:
                raise CompletionGateUnmet("document fingerprint anchor missing")
            if row["integrity_status"] != DocumentIntegrity.VALID.value:
                raise CompletionGateUnmet(
                    f"first verification not VALID (integrity_status={row['integrity_status']})")
            indices = self._page_indices(document_id)
            if indices != list(range(row["page_count"])):
                raise CompletionGateUnmet(
                    f"durable page set inconsistent (page_count={row['page_count']}, "
                    f"indices={indices[:8]}{'…' if len(indices) > 8 else ''})")
            dup = self._conn.execute(
                """SELECT document_id FROM reconstruction_documents
                   WHERE capture_id = ? AND document_state = 'COMPLETED' AND document_id <> ?""",
                (row["capture_id"], document_id),
            ).fetchone()
            if dup is not None:
                self._safe_rollback()
                return UAC_UNIQUENESS_CONFLICT                 # explicit loser
            self._conn.execute(
                "UPDATE reconstruction_documents SET document_state = 'COMPLETED' "
                "WHERE document_id = ?",
                (document_id,),
            )
            self._conn.execute("COMMIT")
            return UAC_GRANTED
        except sqlite3.IntegrityError:
            # Backstop: the partial unique index fired — an explicit conflict, never a crash.
            self._safe_rollback()
            return UAC_UNIQUENESS_CONFLICT
        except ReconstructionLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise StorageUnavailable(                    # fail-closed, never tentative
                f"completion could not execute (never granted tentatively): {exc}") from exc

    # ------------------------------------------------------------------
    # Settlement — ACTIVE → FAILED_INCOMPLETE (terminals never change)
    # ------------------------------------------------------------------

    def settle_failed(self, document_id: str, settlement_note: str) -> None:
        """Settle an ACTIVE leftover to FAILED_INCOMPLETE with a mandatory
        settlement_note and integrity_status = FAILED pinned at the settlement moment."""
        if not settlement_note:
            raise IllegalFieldWrite("settlement_note is mandatory")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_raw(document_id)
            if row is None:
                raise DocumentNotFound(f"no such document: {document_id}")
            if row["document_state"] != DocumentState.ACTIVE.value:
                raise IllegalTransition(
                    f"settlement requires ACTIVE; document is {row['document_state']} "
                    "(terminal states never change)")
            self._conn.execute(
                """UPDATE reconstruction_documents
                   SET document_state = 'FAILED_INCOMPLETE', integrity_status = 'FAILED',
                       settlement_note = ?
                   WHERE document_id = ?""",
                (settlement_note, document_id),
            )
            self._conn.execute("COMMIT")
        except ReconstructionLayerError:
            self._safe_rollback()
            raise
        except sqlite3.Error as exc:
            self._safe_rollback()
            raise StorageUnavailable(f"settlement write failed (D-2 residue): {exc}") from exc

    # ------------------------------------------------------------------
    # Read capabilities
    # ------------------------------------------------------------------

    def get_document(self, document_id: str) -> DocumentRecord:
        row = self._fetch_raw(document_id)
        if row is None:
            raise DocumentNotFound(f"no such document: {document_id}")
        return _record_from_row(row)

    def get_pages(self, document_id: str) -> List[PageRecord]:
        """Ordered durable pages (page_index ascending). Raises DocumentNotFound for an
        unknown document; an existing document with zero pages yields []."""
        if self._fetch_raw(document_id) is None:
            raise DocumentNotFound(f"no such document: {document_id}")
        rows = self._conn.execute(
            "SELECT * FROM document_pages WHERE document_id = ? ORDER BY page_index",
            (document_id,),
        ).fetchall()
        return [_page_from_row(r) for r in rows]

    def get_page_content(self, page_ref: str) -> bytes:
        """Byte-exact page content read via page_ref (verification input)."""
        row = self._conn.execute(
            "SELECT content FROM document_pages WHERE page_ref = ?", (page_ref,)
        ).fetchone()
        if row is None:
            raise PageContentMissing(f"no durable content for page_ref: {page_ref}")
        return bytes(row["content"])

    def find_completed_for_capture(self, capture_id: str) -> Optional[DocumentRecord]:
        """The COMPLETED document bound to a capture (INV-R-1:1 ⇒ at most one; the
        partial UNIQUE index is the storage backstop). Deterministic order."""
        row = self._conn.execute(
            """SELECT * FROM reconstruction_documents
               WHERE capture_id = ? AND document_state = 'COMPLETED'
               ORDER BY document_id LIMIT 1""",
            (capture_id,),
        ).fetchone()
        return _record_from_row(row) if row is not None else None

    def enumerate_active(self) -> List[DocumentRecord]:
        """Complete enumeration of ACTIVE leftovers (OD-R7)."""
        rows = self._conn.execute(
            """SELECT * FROM reconstruction_documents WHERE document_state = 'ACTIVE'
               ORDER BY created_at, document_id"""
        ).fetchall()
        return [_record_from_row(r) for r in rows]

    def count_for_capture(self, capture_id: str) -> Tuple[int, int]:
        """Test/inspection helper: (count of COMPLETED, count of all) for one capture."""
        completed = self._conn.execute(
            """SELECT COUNT(*) AS n FROM reconstruction_documents
               WHERE capture_id = ? AND document_state = 'COMPLETED'""",
            (capture_id,),
        ).fetchone()["n"]
        total = self._conn.execute(
            "SELECT COUNT(*) AS n FROM reconstruction_documents WHERE capture_id = ?",
            (capture_id,),
        ).fetchone()["n"]
        return completed, total
