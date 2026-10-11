"""Capture Consistency & Orphan Report — WP-1.3 mechanics-only (read-only by construction).

Binding basis: SPEC-WP13-RETR v1.0-MVP (§8) over the frozen WP-1.1 invariants
(INV-C1 / INV-C3 / INV-C6 / INV-C9) and the WP-1.3 retention gate.

WHAT IT IS
    A deterministic, structural audit report over a capture database (and, when
    supplied, the WP-1.3 retention journal): orphaned content, unrecovered residue,
    invariant violations, unparseable timestamps, foreign fingerprint algorithm ids,
    duplicate COMPLETED keys, orphan journal decisions, and the retention-candidate
    summary under an INJECTED policy + INJECTED evaluation time.

WHAT IT NEVER DOES
    * It never repairs, settles, deletes or rewrites anything. It does not even open
      the database writable: the connection is opened with SQLite ``mode=ro``, so a
      write through this module is impossible at the storage layer (AC-1.3.4 proof).
    * It never reads artifact CONTENT bytes. Presence/absence is established from
      durable index state only (the report stays cheap and cannot leak content).
    * It never invents a policy value: with no injected policy the retention section is
      reported as ``NOT_EVALUATED`` — never as "0 candidates", which would read like a
      verdict (DEF4 boundary).
    * It never uses a clock. ``evaluation_time`` is an input; the report is a pure
      function of (database state, policy, evaluation_time) — the same inputs yield a
      byte-identical canonical text and fingerprint.

Delegated implementation details (SPEC-WP13-RETR §10):
    OD-RT-F  access via a read-only SQLite URI over the frozen schema; zero DDL, zero
             DML, no schema coupling beyond column names the frozen store declares.
             The path is percent-encoded (holoo_spike ``read_only_uri`` idiom), so
             ``?``/``#``/``%`` inside a legal path can neither redirect the URI to
             another file nor omit ``mode=ro``.
    OD-RT-H  findings are ordered by (code, capture_id) and serialized as canonical
             JSON; volatile values (uuids, absolute paths, wall clock) never appear —
             determinism is therefore testable by re-running in fresh processes.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from .retention import (
    DEF4_PENDING_LABEL,
    RETENTION_BASES,
    RETENTION_OUTCOME_DATA_ANOMALY,
    RETENTION_OUTCOME_ELIGIBLE,
    RETENTION_OUTCOME_INTEGRITY_DEFERRED,
    RETENTION_OUTCOME_NOT_ELIGIBLE,
    RETENTION_OUTCOME_PURGE_GATE_BLOCKED,
    RETENTION_OUTCOME_STATE_REFUSED,
    RetentionIllegalInput,
    RetentionPolicy,
    evaluate_retention,
    is_aware_iso,
)
from .s1 import S1_ALGORITHM_ID, S1Service

REPORT_KIND = "kandoo-capture-consistency-report"
REPORT_SCHEMA_VERSION = "v1"

# Finding codes (fixed vocabulary — coarse, structural, no interpretation)
F_ORPHAN_CONTENT_UNREFERENCED = "ORPHAN_CONTENT_UNREFERENCED"
F_ORPHAN_RECORD_CONTENT_MISSING = "ORPHAN_RECORD_CONTENT_MISSING"
F_UNRESOLVED_ACTIVE_LEFTOVER = "UNRESOLVED_ACTIVE_LEFTOVER"
F_INVARIANT_INV_C1 = "INVARIANT_VIOLATION_INV_C1"
F_INVARIANT_INV_C9 = "INVARIANT_VIOLATION_INV_C9"
F_INTEGRITY_UNVERIFIED_ON_COMPLETED = "INTEGRITY_UNVERIFIED_ON_COMPLETED"
F_TIMESTAMP_UNPARSEABLE = "TIMESTAMP_UNPARSEABLE"
F_FOREIGN_FINGERPRINT_ALGORITHM = "FOREIGN_FINGERPRINT_ALGORITHM"
F_DUPLICATE_COMPLETED_KEY = "DUPLICATE_COMPLETED_S1_KEY"
F_RETENTION_POLICY_UNDECLARED = "RETENTION_POLICY_UNDECLARED"
F_JOURNAL_ORPHAN_DECISION = "JOURNAL_ORPHAN_DECISION"
F_JOURNAL_CHAIN_BROKEN = "JOURNAL_CHAIN_BROKEN"
F_JOURNAL_PURGE_REFUSAL_PRESENT = "JOURNAL_PURGE_REFUSAL_PRESENT"

NOT_EVALUATED = "NOT_EVALUATED"


class ConsistencyStorageUnavailable(Exception):
    """The report could not be computed (storage unreachable / schema absent)."""


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def to_canonical_dict(self) -> dict:
        return {"code": self.code, "subject": self.subject, "detail": self.detail}


@dataclass(frozen=True)
class ConsistencyReport:
    """The deterministic report carrier: canonical text + self-anchor fingerprint."""
    findings: List[Finding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    canonical_text: str = ""
    report_fingerprint: str = ""
    report_algorithm_id: str = S1_ALGORITHM_ID

    def codes(self) -> List[str]:
        return [f.code for f in self.findings]

    def subjects(self, code: str) -> List[str]:
        return [f.subject for f in self.findings if f.code == code]

    def to_canonical_dict(self) -> dict:
        return {"kind": REPORT_KIND, "schema_version": REPORT_SCHEMA_VERSION,
                "summary": self.summary,
                "findings": [f.to_canonical_dict() for f in self.findings]}


def _open_read_only(db_path: str) -> sqlite3.Connection:
    """OD-RT-F: a read-only connection over a URI-ENCODED path.

    The path is percent-encoded exactly like the established read-only idiom in
    ``src/holoo_spike/store.py`` (``read_only_uri``), so URI metacharacters in a
    legal filesystem path (``?``, ``#``, ``%``) can neither redirect the URI to a
    different file nor be parsed as a query string — which would silently omit
    ``mode=ro``. Any write attempt through the returned connection is a storage
    error, so the report's non-mutation property does not rest on convention.
    """
    try:
        uri = "file:" + quote(str(Path(db_path).resolve().as_posix()), safe="/") + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        raise ConsistencyStorageUnavailable(f"could not open capture db read-only: {exc}") from exc


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.Error as exc:
        raise ConsistencyStorageUnavailable(f"consistency query failed: {exc}") from exc


def build_consistency_report(capture_db_path, *, policy: Optional[RetentionPolicy] = None,
                             evaluation_time: Optional[str] = None,
                             journal_db_path=None, s1: Optional[S1Service] = None) -> ConsistencyReport:
    """Audit one capture database (plus the optional retention journal database).

    Every argument that could change the answer is explicit: no clock is read, no
    policy value is invented, and no storage is written.
    """
    s1 = s1 or S1Service()
    conn = _open_read_only(str(capture_db_path))
    findings: List[Finding] = []
    try:
        records = _rows(conn, "SELECT * FROM capture_records ORDER BY capture_id")
        content_refs = {r["content_ref"] for r in
                        _rows(conn, "SELECT content_ref FROM artifact_content")}
    except ConsistencyStorageUnavailable:
        conn.close()
        raise
    conn.close()

    referenced = set()
    counts = {"records_total": len(records), "COMPLETED": 0, "ACTIVE": 0,
              "FAILED_INCOMPLETE": 0}

    for row in records:
        cid = row["capture_id"]
        state = row["capture_state"]
        counts[state] = counts.get(state, 0) + 1

        if row["artifact_ref"] is not None:
            referenced.add(row["artifact_ref"])

        # residue / lifecycle (INV-C6 territory — reported, never settled here)
        if state == "ACTIVE":
            findings.append(Finding(
                F_UNRESOLVED_ACTIVE_LEFTOVER, cid,
                "record is ACTIVE: startup recovery owns settlement; this report never settles"))

        # INV-C1: COMPLETED carries the full identity/evidence field set
        if state == "COMPLETED":
            missing = [name for name in ("s1", "s1_algorithm_id", "artifact_ref",
                                        "artifact_size_bytes") if row[name] is None]
            if missing:
                findings.append(Finding(
                    F_INVARIANT_INV_C1, cid,
                    f"COMPLETED record is missing {sorted(missing)} (completion gate breach)"))
            if row["integrity_status"] == "UNVERIFIED":
                findings.append(Finding(
                    F_INTEGRITY_UNVERIFIED_ON_COMPLETED, cid,
                    "COMPLETED record is UNVERIFIED — a verdict was never recorded"))

        # INV-C9: FAILED_INCOMPLETE carries a note and a pinned FAILED integrity
        if state == "FAILED_INCOMPLETE":
            if not row["settlement_note"] or row["integrity_status"] != "FAILED":
                findings.append(Finding(
                    F_INVARIANT_INV_C9, cid,
                    f"FAILED_INCOMPLETE record has settlement_note={row['settlement_note']!r} "
                    f"and integrity_status={row['integrity_status']!r} (both are mandatory "
                    f"and pinned at settlement)"))

        # orphan record → content
        if row["artifact_ref"] is not None and row["artifact_ref"] not in content_refs:
            findings.append(Finding(
                F_ORPHAN_RECORD_CONTENT_MISSING, cid,
                "record binds an artifact_ref with no durable content row"))

        # timestamp mechanics
        for field_name in ("created_at", "received_at"):
            if not is_aware_iso(row[field_name]):
                findings.append(Finding(
                    F_TIMESTAMP_UNPARSEABLE, cid,
                    f"{field_name}={row[field_name]!r} is not an ISO-8601 instant with an "
                    f"explicit offset"))

        # foreign fingerprint id → NO-VERDICT class, surfaced for review
        if state == "COMPLETED" and row["s1_algorithm_id"] and \
                row["s1_algorithm_id"] != S1_ALGORITHM_ID:
            findings.append(Finding(
                F_FOREIGN_FINGERPRINT_ALGORITHM, cid,
                f"s1_algorithm_id={row['s1_algorithm_id']!r} is foreign to the frozen "
                f"{S1_ALGORITHM_ID} binding — no verdict is computed"))

    # orphan content → unreferenced bytes
    for ref in sorted(content_refs - referenced):
        findings.append(Finding(
            F_ORPHAN_CONTENT_UNREFERENCED, ref,
            "durable content row is referenced by no capture record (orphan artifact)"))

    # duplicate COMPLETED key (INV-C3 backstop — must be impossible; verified, not assumed)
    dupes = _dup_completed_keys(capture_db_path)
    for (key_s1, key_alg), ids in dupes:
        findings.append(Finding(
            F_DUPLICATE_COMPLETED_KEY, ids[0],
            f"{len(ids)} COMPLETED records share (s1={key_s1[:16]}…, s1_algorithm_id={key_alg}) "
            f"— ids: {ids}"))

    # retention section — honest absence when no policy was injected
    retention_summary = _evaluate_retention_section(records, policy, evaluation_time, findings)

    # journal cross-checks
    journal_summary = _audit_journal(journal_db_path, {r["capture_id"] for r in records}, findings)

    findings.sort(key=lambda f: (f.code, f.subject))

    summary = {
        "kind": REPORT_KIND,
        "schema_version": REPORT_SCHEMA_VERSION,
        "counts": counts,
        "finding_counts": _tally(findings),
        "findings_total": len(findings),
        "retention": retention_summary,
        "journal": journal_summary,
        "policy_status_label": DEF4_PENDING_LABEL,
        "report_scope_note": "structural audit only; no content read, no repair, no deletion",
    }
    text = canonical_report_text(summary, findings)
    fingerprint = s1.compute(text.encode("utf-8")).s1
    return ConsistencyReport(findings=findings, summary=summary, canonical_text=text,
                             report_fingerprint=fingerprint,
                             report_algorithm_id=s1.algorithm_id)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _tally(findings: List[Finding]) -> dict:
    out: dict = {}
    for finding in findings:
        out[finding.code] = out.get(finding.code, 0) + 1
    return out


def _dup_completed_keys(capture_db_path: str):
    conn = _open_read_only(str(capture_db_path))
    try:
        rows = _rows(conn, """SELECT s1, s1_algorithm_id, GROUP_CONCAT(capture_id) AS ids
                              FROM capture_records WHERE capture_state = 'COMPLETED'
                              GROUP BY s1, s1_algorithm_id HAVING COUNT(*) > 1""")
    finally:
        conn.close()
    out = []
    for row in rows:
        out.append(((row["s1"], row["s1_algorithm_id"]), sorted(row["ids"].split(","))))
    return out


def _evaluate_retention_section(records, policy, evaluation_time, findings) -> dict:
    """Candidate counting under an injected policy. Absent policy = NOT_EVALUATED."""
    if policy is None:
        findings.append(Finding(
            F_RETENTION_POLICY_UNDECLARED, "-",
            "retention candidates were not evaluated: no policy was injected and DEF4 has "
            "no ratified values (0 would be a false verdict)"))
        return {
            "status": DEF4_PENDING_LABEL,
            "policy_id": None,
            "evaluation_time": evaluation_time,
            "candidates": NOT_EVALUATED,
            "not_eligible": NOT_EVALUATED,
            "refused": NOT_EVALUATED,
        }

    tally = {RETENTION_OUTCOME_ELIGIBLE: 0, "refused": 0, "not_eligible": 0, "other": 0}
    candidates: List[str] = []
    for row in records:
        decision = evaluate_retention(_RecordView(row), policy=policy,
                                       evaluation_time=evaluation_time)
        if decision.outcome == RETENTION_OUTCOME_ELIGIBLE:
            tally[RETENTION_OUTCOME_ELIGIBLE] += 1
            candidates.append(row["capture_id"])
        elif decision.outcome == RETENTION_OUTCOME_NOT_ELIGIBLE:
            tally["not_eligible"] += 1
        elif decision.outcome in (RETENTION_OUTCOME_STATE_REFUSED,
                                  RETENTION_OUTCOME_INTEGRITY_DEFERRED,
                                  RETENTION_OUTCOME_DATA_ANOMALY):
            tally["refused"] += 1
        else:
            tally["other"] += 1
    return {
        "status": DEF4_PENDING_LABEL,
        "policy_id": policy.policy_id,
        "evaluation_time": evaluation_time,
        "basis": policy.basis,
        "cutoff_seconds": policy.cutoff_seconds,
        "privacy_marking": policy.privacy_marking,
        "candidates": tally[RETENTION_OUTCOME_ELIGIBLE],
        "candidate_capture_ids": sorted(candidates),
        "not_eligible": tally["not_eligible"],
        "refused": tally["refused"],
        "other": tally["other"],
        "note": "candidate reporting is an inventory of candidates; no purge was "
                "requested or executed by this report",
    }


def _audit_journal(journal_db_path, known_capture_ids: set, findings: List[Finding]) -> dict:
    if journal_db_path is None:
        return {"status": "NOT_SUPPLIED", "decisions": NOT_EVALUATED,
                "chain_ok": NOT_EVALUATED, "orphans": NOT_EVALUATED}
    conn = _open_read_only(str(journal_db_path))
    try:
        rows = _rows(conn, "SELECT * FROM retention_decisions ORDER BY seq")
        anchors = _rows(conn, "SELECT * FROM retention_journal_anchor ORDER BY anchor_seq")
    except ConsistencyStorageUnavailable:
        conn.close()
        raise
    conn.close()

    anchor_by_seq = {int(a["anchor_seq"]): a["last_hash"] for a in anchors}
    orphans = 0
    purge_refusals = 0
    anchor_broken = len(anchors) != len(rows)
    for row in rows:
        if row["capture_id"] is not None and row["capture_id"] not in known_capture_ids:
            orphans += 1
            findings.append(Finding(
                F_JOURNAL_ORPHAN_DECISION, f"seq:{int(row['seq'])}",
                f"journal decision references capture_id={row['capture_id']!r}, which is "
                f"absent from the capture database (orphan decision)"))
        if row["outcome"] == RETENTION_OUTCOME_PURGE_GATE_BLOCKED:
            purge_refusals += 1
        expected = anchor_by_seq.get(int(row["seq"]))
        if expected is None or expected != row["record_hash"]:
            anchor_broken = True
            findings.append(Finding(
                F_JOURNAL_CHAIN_BROKEN, f"seq:{int(row['seq'])}",
                "journal anchor is missing or disagrees with the log row "
                "(truncation / rewrite)"))
    if anchor_broken and not any(f.code == F_JOURNAL_CHAIN_BROKEN for f in findings):
        findings.append(Finding(
            F_JOURNAL_CHAIN_BROKEN, "-",
            f"anchor count {len(anchors)} does not match decision count {len(rows)}"))
    if purge_refusals:
        findings.append(Finding(
            F_JOURNAL_PURGE_REFUSAL_PRESENT, f"count:{purge_refusals}",
            "purge requests were recorded as BLOCKED by the gate (audit trail present; "
            "no deletion executed)"))
    return {
        "status": "OK" if not anchor_broken else "CHAIN_SUSPECT",
        "decisions": len(rows),
        "anchors": len(anchors),
        "chain_ok": not anchor_broken,
        "orphans": orphans,
        "purge_refusals_recorded": purge_refusals,
    }


class _RecordView:
    """Read-only attribute view over a raw capture row, shaped for the evaluator.

    It carries exactly the fields the retention gate may observe (identity, state,
    integrity, the two timestamps) — no content, no downstream datum (INV-C7).
    """

    __slots__ = ("capture_id", "capture_state", "integrity_status", "created_at",
                 "received_at", "s1", "s1_algorithm_id")

    def __init__(self, row: sqlite3.Row) -> None:
        self.capture_id = row["capture_id"]
        self.capture_state = row["capture_state"]
        self.integrity_status = row["integrity_status"]
        self.created_at = row["created_at"]
        self.received_at = row["received_at"]
        self.s1 = row["s1"]
        self.s1_algorithm_id = row["s1_algorithm_id"]


def canonical_report_text(summary: dict, findings: List[Finding]) -> str:
    """The canonical bytes whose fingerprint anchors the report (OD-RT-H)."""
    return json.dumps(
        {"kind": REPORT_KIND, "schema_version": REPORT_SCHEMA_VERSION,
         "summary": summary,
         "findings": [f.to_canonical_dict() for f in findings]},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# Re-exported for consumers that must not import the gate module separately.
__all__ = [
    "REPORT_KIND", "REPORT_SCHEMA_VERSION", "NOT_EVALUATED", "DEF4_PENDING_LABEL",
    "RETENTION_BASES", "ConsistencyReport", "ConsistencyStorageUnavailable",
    "Finding", "build_consistency_report", "canonical_report_text",
    "RetentionPolicy", "RetentionIllegalInput",
]
