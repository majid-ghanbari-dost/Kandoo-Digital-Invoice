"""Shared fixtures/helpers for the WP-1.3 Retention & Recovery test suite.

Injected instants are CONSTANTS here (test-side), never defaults in the production
modules: AC-1.3.4 requires that a verdict only exists when the caller supplies the
evaluation instant. The capture store's own created_at is the wall clock, so every
eligibility probe measures age from ``received_at`` (explicitly supplied to ingest).
"""
from __future__ import annotations

import itertools
import sqlite3
from pathlib import Path

from capture import CaptureService, CaptureStore, S1Service
from capture.retention import RETENTION_BASIS_RECEIVED_AT, RetentionPolicy

# Fixed instants (no wall-clock dependence anywhere in this suite)
RECEIVED_AT = "2026-09-01T00:00:00+00:00"
EVAL_TIME = "2026-10-11T00:00:00+00:00"
AGE_FROM_RECEIVED_AT = 3_456_000          # 40 days, asserted against the evaluator

# Test-side policy VALUES (they live here precisely because production must not own them)
POLICY_ID = "TEST-POLICY-1"
PRIVACY_MARKING = "TEST-PRIVACY-CLASS-A"


def policy(*, cutoff_seconds: int = 1_000, candidate_reporting: bool = True,
           basis: str = RETENTION_BASIS_RECEIVED_AT, policy_id: str = POLICY_ID,
           privacy_marking: str = PRIVACY_MARKING) -> RetentionPolicy:
    return RetentionPolicy(
        policy_id=policy_id, basis=basis, cutoff_seconds=cutoff_seconds,
        privacy_marking=privacy_marking, candidate_reporting=candidate_reporting)


def ingest_completed(service: CaptureService, content: bytes = b"invoice.number=WP13-1\n"):
    """Drive the frozen ingest to a COMPLETED record with an explicit received_at."""
    outcome = service.ingest(content, received_at=RECEIVED_AT)
    assert type(outcome).__name__ == "IngestCompleted", outcome
    return outcome.capture_id


# ---------------------------------------------------------------------------
# Storage-defect fixture: the frozen column layout WITHOUT the CHECK constraints
# and unique indexes. A row that the frozen store refuses to write can still exist
# on disk if the file is rewritten out-of-band — which is exactly the condition the
# consistency report must detect (and never repair).
# ---------------------------------------------------------------------------

_RELAXED_SCHEMA = """
CREATE TABLE capture_records (
    capture_id TEXT PRIMARY KEY,
    s1 TEXT, s1_algorithm_id TEXT, artifact_ref TEXT,
    created_at TEXT NOT NULL,
    capture_state TEXT NOT NULL,
    integrity_status TEXT NOT NULL,
    integrity_verified_at TEXT,
    received_at TEXT NOT NULL,
    source_label TEXT NOT NULL,
    artifact_format_hint TEXT NOT NULL,
    capture_entry_metadata TEXT NOT NULL,
    artifact_size_bytes INTEGER,
    settlement_note TEXT
);
CREATE TABLE artifact_content (content_ref TEXT PRIMARY KEY, content BLOB NOT NULL);
"""

_COLUMNS = ("capture_id", "s1", "s1_algorithm_id", "artifact_ref", "created_at",
            "capture_state", "integrity_status", "integrity_verified_at", "received_at",
            "source_label", "artifact_format_hint", "capture_entry_metadata",
            "artifact_size_bytes", "settlement_note")

_BASE_ROW = {
    "s1": "a" * 64, "s1_algorithm_id": "sha256-v1", "artifact_ref": "capture-content:v1:base",
    "created_at": "2026-09-01T00:00:00+00:00", "capture_state": "COMPLETED",
    "integrity_status": "VALID", "integrity_verified_at": "2026-09-01T00:00:01+00:00",
    "received_at": "2026-09-01T00:00:00+00:00", "source_label": "wp13-fixture",
    "artifact_format_hint": "UNKNOWN", "capture_entry_metadata": "{}",
    "artifact_size_bytes": 7, "settlement_note": None,
}


def relaxed_capture_db(path, *, rows: int = 0) -> Path:
    """Create a defect-capable capture database (relaxed schema) and return its path."""
    conn = sqlite3.connect(str(path))
    conn.executescript(_RELAXED_SCHEMA)
    for i in range(rows):
        insert_relaxed_row(conn, capture_id=f"relaxed-{i:04d}",
                           artifact_ref=f"capture-content:v1:relaxed-{i:04d}",
                           s1=f"{i:x}" * 64)
    conn.commit()
    conn.close()
    return Path(path)


_forged_row_counter = itertools.count(1)


def insert_relaxed_row(conn, *, with_content: bool = True, **overrides) -> str:
    fields = dict(_BASE_ROW)
    fields.update({k: v for k, v in overrides.items() if k in _COLUMNS})
    if "capture_id" not in fields:
        # deterministic, process-independent id (no hash() — its seed is randomized)
        fields["capture_id"] = f"forged-{next(_forged_row_counter):06d}"
    columns = ", ".join(_COLUMNS)
    placeholders = ", ".join("?" for _ in _COLUMNS)
    conn.execute(
        f"INSERT INTO capture_records ({columns}) VALUES ({placeholders})",
        tuple(fields[c] for c in _COLUMNS))
    if with_content and fields["artifact_ref"] is not None:
        conn.execute("INSERT OR IGNORE INTO artifact_content (content_ref, content) VALUES (?, ?)",
                     (fields["artifact_ref"],
                      sqlite3.Binary(b"x" * int(fields["artifact_size_bytes"] or 0))))
    conn.commit()
    return fields["capture_id"]
