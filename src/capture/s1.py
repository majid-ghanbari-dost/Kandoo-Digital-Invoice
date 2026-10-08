"""S1 Fingerprint & verification compute capability — T-1.1.3 implementation.

Binding basis: DES-WP11-T113-S1 v1.0 (FINAL APPROVED) over Contract v1.1 §8/§10.

Properties realized (S1 §3.1, P-S1-1..P-S1-7):
  P-S1-1 deterministic        — pure function of the byte sequence (no time/random/env)
  P-S1-2 content-sensitive    — SHA-256 full 256-bit digest, NO truncation
  P-S1-3 input exactness      — the exact artifact bytes; no preprocessing of any kind
  P-S1-4 output canonicity    — fixed-length lowercase hex (environment-independent)
  P-S1-5 environment independence — no parameters, no configuration surface
  P-S1-6 single-algorithm binding — every value carries exactly one s1_algorithm_id;
        comparisons valid only within equal ids (§8 prop 4)
  P-S1-7 aggregation-determinism interface — consumes the already-aggregated byte
        sequence; aggregation determinism binds the entry point (CaptureService.aggregate)

Algorithm choice (delegated detail, declared per D-09 — S1 §5 recommendation adopted):
  SHA-256 over the exact byte sequence, full digest, canonical lowercase hex,
  s1_algorithm_id literal = "sha256-v1".

NO-VERDICT semantics (S1 §8 F2 / §9 F1, consumed verbatim by the read path and recovery):
  an unknown/unsupported s1_algorithm_id or a capability failure yields NO verdict —
  never a guessed VALID, never a fabricated FAILED.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional, Union

from .model import S1ComputationFailure

S1_ALGORITHM_ID = "sha256-v1"


@dataclass(frozen=True)
class S1Value:
    """The immutable attach payload for F-02/F-03 (one value, exactly one id — INV-F3)."""
    s1: str
    s1_algorithm_id: str


@dataclass(frozen=True)
class Verdict:
    """Exhaustive verification outcomes (VOR §3 O-1..O-4 minus the read-path's O-3,
    which is raised by the content-read step before compute):
      VALID | FAILED | NO_VERDICT"""
    outcome: str                       # "VALID" | "FAILED" | "NO_VERDICT"
    reason: Optional[str] = None


class S1Service:
    """The single verification-compute capability of the capture layer (S1 §1 item 2).
    Consumed by: ingest first verification (V-1), recovery settlement (V-2), and the
    read path (V-3). It computes and compares only — it never writes and never delivers."""

    def __init__(
        self,
        algorithm_id: str = S1_ALGORITHM_ID,
        supported_ids: Optional[Iterable[str]] = None,
    ) -> None:
        self._algorithm_id = algorithm_id
        self._supported: FrozenSet[str] = frozenset(supported_ids) if supported_ids is not None else frozenset({algorithm_id})

    @property
    def algorithm_id(self) -> str:
        return self._algorithm_id

    @property
    def supported_ids(self) -> FrozenSet[str]:
        return self._supported

    def compute(self, content: bytes) -> S1Value:
        """S1 over the exact artifact bytes (P-S1-3). Failure → S1ComputationFailure
        (S1 §9 F1 path — the caller settles explicitly, never silently)."""
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise S1ComputationFailure("s1 input must be a byte sequence")
        try:
            digest = hashlib.sha256(bytes(content)).hexdigest()  # full digest, lowercase hex
        except Exception as exc:  # capability failure — surfaced, never guessed around
            raise S1ComputationFailure(f"s1 computation failed: {exc}") from exc
        return S1Value(s1=digest, s1_algorithm_id=self._algorithm_id)

    def verify(self, content: bytes, s1: str, s1_algorithm_id: str) -> Verdict:
        """Recompute with the record's OWN s1_algorithm_id and compare — byte-value
        equality, valid only within the equal id (§8 prop 4; VOR INV-V4).
        Comparison-only capability: never writes, never delivers (VOR §3)."""
        if s1_algorithm_id not in self._supported:
            # S1 §8 F2: unknown/unsupported id → NO-VERDICT (version skew surfaced upstream)
            return Verdict("NO_VERDICT", f"unknown s1_algorithm_id: {s1_algorithm_id}")
        if not isinstance(content, (bytes, bytearray, memoryview)):
            return Verdict("NO_VERDICT", "verification capability failure: input is not bytes")
        try:
            recomputed = hashlib.sha256(bytes(content)).hexdigest()
        except Exception as exc:
            return Verdict("NO_VERDICT", f"verification capability failure: {exc}")
        if recomputed == s1:
            return Verdict("VALID", None)
        return Verdict("FAILED", "mismatch")
