"""Capture-layer domain model — WP-1.1 implementation.

Derived strictly from the four frozen documents:
  SPEC-WP11-CRC        — Capture Record Contract v1.1 (FINAL FREEZE APPROVED)
  DES-WP11-T112-STORE  — Durable Local Capture Store Design v0.2 (FINAL APPROVED)
  DES-WP11-T113-S1     — S1 Fingerprint & Capture-Level Idempotency Design v1.0 (FINAL APPROVED)
  DES-WP11-T114-VOR    — Verify-on-Read / Integrity Verification Design v1.0 (FINAL APPROVED / FROZEN)

The Capture Record carries exactly the 14 contract fields (F-01..F-13, F-15 — F-14 is
retired by v1.1-C1; the Extensibility Reservation forbids any new field). No downstream /
canonical / external-document datum exists anywhere in this model (INV-C7, INV-C8, D-02).

Every outcome type below is explicit: a silent result does not exist in this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations (Contract §5 F-06 / F-07 — exactly the frozen state sets)
# ---------------------------------------------------------------------------

class CaptureState(str, Enum):
    """Contract §7 lifecycle: ACTIVE | COMPLETED | FAILED_INCOMPLETE (both terminals)."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED_INCOMPLETE = "FAILED_INCOMPLETE"


class IntegrityStatus(str, Enum):
    """Contract §10 verdict set: UNVERIFIED is transient-only (pre-first-verification)."""
    UNVERIFIED = "UNVERIFIED"
    VALID = "VALID"
    FAILED = "FAILED"


# Explicit unknown values (Contract §6 — no guessed values, ever)
SOURCE_LABEL_UNDECLARED = "UNDECLARED"   # §14 r6: entry point gave no label
FORMAT_HINT_UNKNOWN = "UNKNOWN"          # §14 r7: not mechanically determinable


# ---------------------------------------------------------------------------
# Settlement-note vocabulary (Store §5 step c / §6.1; S1 §9; Contract §11/§14)
# ---------------------------------------------------------------------------

NOTE_S1_COMPUTATION_FAILED = "s1 computation failed"                    # S1 §9 F1; §14 r2
NOTE_CONTENT_PERSIST_FAILED = "content persist failed"                  # Store §6.1 D-1
NOTE_S1_MISSING = "s1 missing"                                          # Store §5 (W3)
NOTE_CONTENT_MISSING = "content missing/unreadable"                     # Store §5 (W2); §14 r3
NOTE_VERIFY_FAILED = "verify FAILED"                                    # S1 §9 F5; Store §5
NOTE_PERSISTENCE_INCOMPLETE = "persistence incomplete"                  # Store §5 vocabulary
NOTE_UNIQUENESS_CONFLICT = (
    "uniqueness conflict: a COMPLETED record with the same "
    "(s1, s1_algorithm_id) exists"                                      # Store §5 / §9.1 P3
)
NOTE_VERIFICATION_UNAVAILABLE = (
    "verification unavailable (no verdict computable)"                  # Store §5 note; S1 §9 F2
)

# Read-outcome reason codes (VOR §6 — coarse, no content interpretation)
READ_REASON_MISMATCH = "mismatch"
READ_REASON_UNREADABLE = "content unreadable/missing"


# ---------------------------------------------------------------------------
# Single layer clock (Contract §16 delegation; Store OD-8 / VOR OD-V2 — one clock,
# implemented at most once layer-wide)
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    """UTC ISO-8601 timestamp with explicit timezone — logical consistency within the layer."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Capture Record — the 14 contract fields (Contract §5), immutable snapshot
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CaptureRecord:
    capture_id: str                        # F-01
    s1: Optional[str]                      # F-02 (never null on COMPLETED — INV-C1)
    s1_algorithm_id: Optional[str]         # F-03 (never null on COMPLETED — INV-C1)
    artifact_ref: Optional[str]            # F-04 (never null on COMPLETED — INV-C1)
    created_at: str                        # F-05
    capture_state: CaptureState            # F-06
    integrity_status: IntegrityStatus      # F-07
    integrity_verified_at: Optional[str]   # F-08 (null until first verification)
    received_at: str                       # F-09
    source_label: str                      # F-10 (UNDECLARED if not announced)
    artifact_format_hint: str              # F-11 (UNKNOWN if not determinable)
    capture_entry_metadata: str            # F-12 (verbatim JSON text; "{}" = not provided)
    artifact_size_bytes: Optional[int]     # F-13 (finalized at content persist)
    settlement_note: Optional[str]         # F-15 (mandatory on FAILED_INCOMPLETE; empty on COMPLETED)


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly (Contract §14; Store F1–F9)
# ---------------------------------------------------------------------------

class CaptureLayerError(Exception):
    """Base class for all explicit capture-layer failures."""


class RecordCreationFailed(CaptureLayerError):
    """Store F2: record-creation persist failure — nothing persisted, no residue (R-1)."""


class RecordNotFound(CaptureLayerError):
    """The referenced capture_id does not exist in the store."""


class IllegalTransition(CaptureLayerError):
    """Store F9: a §7-illegal lifecycle transition was demanded (store-enforced, not convention)."""


class IllegalFieldWrite(CaptureLayerError):
    """Store F9: a write outside the §6 mutability classes was demanded (store-enforced)."""


class CompletionGateUnmet(CaptureLayerError):
    """Store §3 Step 4 / §7 r1: completion preconditions not satisfied (fail-closed, P4)."""


class ContentMissing(CaptureLayerError):
    """Content of an artifact_ref is missing / not byte-exactly readable (→ O-3 / Store F5)."""


class StorageUnavailable(CaptureLayerError):
    """D-2 class: no verdict is durably recordable (fail-closed; residue settles at recovery)."""


class S1ComputationFailure(CaptureLayerError):
    """S1 §9 F1: S1 computation cannot complete (ingest cannot complete; §14 r2)."""


class ExplicitPersistenceFailure(CaptureLayerError):
    """D-1 class: a definitive persist error was settled synchronously to FAILED_INCOMPLETE
    (+ settlement_note + integrity_status=FAILED) before this was raised."""

    def __init__(self, capture_id: str, settlement_note: str, detail: str = "") -> None:
        super().__init__(detail or f"definitive persistence failure; settled synchronously: {settlement_note}")
        self.capture_id = capture_id
        self.settlement_note = settlement_note


# ---------------------------------------------------------------------------
# UAC completion outcomes (Store §9.1 — explicit loser outcome, P3)
# ---------------------------------------------------------------------------

UAC_GRANTED = "UAC_GRANTED"
UAC_UNIQUENESS_CONFLICT = "UAC_UNIQUENESS_CONFLICT"


# ---------------------------------------------------------------------------
# Ingest outcomes (S1 §6 three-branch decision + Store §3/§6.1 — exhaustive)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IngestCompleted:
    """§9 miss branch, completion granted through UAC."""
    capture_id: str
    record: CaptureRecord


@dataclass(frozen=True)
class IngestDuplicateAtCapture:
    """§9 step 2a: hit on a COMPLETED, integrity-VALID record — no second record created."""
    existing_capture_id: str
    s1: str
    s1_algorithm_id: str


@dataclass(frozen=True)
class IngestIntegrityFailureHit:
    """§9 step 2b / §14 r5: hit on a COMPLETED, integrity-FAILED record — explicit
    integrity-failure path; NEVER a dedup success; no new record."""
    existing_capture_id: str
    s1: str
    s1_algorithm_id: str


@dataclass(frozen=True)
class IngestSettledFailure:
    """D-1 synchronous settlement to FAILED_INCOMPLETE (+ note + integrity FAILED).
    Retained evidence of a failed ingest — never silent (§14)."""
    capture_id: Optional[str]
    settlement_note: str
    detail: str


@dataclass(frozen=True)
class IngestUniquenessConflict:
    """Store §9.1 P3 / S1 §9 F4: this ingest lost the atomic uniqueness decision;
    its own record settled FAILED_INCOMPLETE with the uniqueness-conflict note."""
    capture_id: str
    settlement_note: str


@dataclass(frozen=True)
class IngestStorageUnavailable:
    """D-2: no verdict durably recordable — record remains ACTIVE solely as recoverable
    residue, guaranteed to be settled by the next startup recovery (Store §6.1)."""
    detail: str


# ---------------------------------------------------------------------------
# Read outcomes (VOR §5/§6 — exhaustive; no silent broken read exists)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReadSuccess:
    """Content delivered ONLY together with the definitive VALID verdict computed in the
    same read over the same bytes (VOR INV-V1)."""
    capture_id: str
    content: bytes
    verdict: str                       # always "VALID" on this outcome
    s1: str
    s1_algorithm_id: str
    integrity_verified_at: str         # the F-08 value written in this read


@dataclass(frozen=True)
class ReadIntegrityFailure:
    """Definitive FAILED verdict + coarse reason; content is NEVER carried on this
    outcome — not under any label (VOR §6 never-list item 3)."""
    capture_id: str
    reason: str                        # READ_REASON_MISMATCH | READ_REASON_UNREADABLE
    verified_at: str                   # the F-08 value written in this read
    issue_report: Optional[str] = None


@dataclass(frozen=True)
class ReadRefused:
    """Non-COMPLETED target (VOR §5 scope rule / INV-V6): no content, no verdict,
    no state change. Also used for unknown capture_id."""
    capture_id: Optional[str]
    capture_state: Optional[str]       # capture-layer process state — Provable-Data-legal
    detail: str


@dataclass(frozen=True)
class ReadVerificationUnavailable:
    """O-4 NO-VERDICT (VOR §3): verification could not execute (unknown id / capability
    failure) — no integrity write (INV-V8), no content, Issue-Report surfacing."""
    capture_id: str
    issue_report: str
