"""Immutable, hash-chained audit events for E-08 detection and review."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import math
from typing import Any
from uuid import uuid4

from e06_onboarding_verdict import Verdict


GENESIS_HASH = "0" * 64


class AuditEventType(str, Enum):
    NEW_TYPE_DETECTED = "NEW_TYPE_DETECTED"
    CORRUPTED_INVOICE_DETECTED = "CORRUPTED_INVOICE_DETECTED"
    EXISTING_TYPE_EVALUATED = "EXISTING_TYPE_EVALUATED"
    INDETERMINATE_DETECTION = "INDETERMINATE_DETECTION"
    CANDIDATE_REVIEWED = "CANDIDATE_REVIEWED"
    CANDIDATE_ACCEPTED = "CANDIDATE_ACCEPTED"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
    MINI_ONBOARDING_INVOICE_REVIEWED = "MINI_ONBOARDING_INVOICE_REVIEWED"
    MINI_ONBOARDING_LOCKED = "MINI_ONBOARDING_LOCKED"


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601 with a UTC offset") from exc
    else:
        raise ValueError("timestamp must be an ISO-8601 string or aware datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: str | datetime) -> str:
    return _parse_timestamp(value).isoformat().replace("+00:00", "Z")


def _value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: AuditEventType
    store_id: str
    occurred_at: str
    invoice_id: str | None
    match_scores: tuple[tuple[str, float], ...]
    candidate_id: str | None
    verdict: str | None
    reason_codes: tuple[str, ...]
    verified_fields: tuple[str, ...]
    detection_kind: str | None
    reviewer_id: str | None
    review_reason: str | None
    candidate_decision: str | None
    bank_snapshot_id: str | None
    previous_hash: str
    entry_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, AuditEventType):
            object.__setattr__(self, "event_type", AuditEventType(self.event_type))
        _parse_timestamp(self.occurred_at)
        if (
            not isinstance(self.event_id, str)
            or not self.event_id.strip()
            or not isinstance(self.store_id, str)
            or not self.store_id.strip()
        ):
            raise ValueError("event_id and store_id are required")
        if not isinstance(self.match_scores, tuple) or any(
            not isinstance(name, str) or not name or not math.isfinite(score) or not 0 <= score <= 1
            for name, score in self.match_scores
        ):
            raise ValueError("match_scores must be a tuple of named scores in [0, 1]")
        if not isinstance(self.reason_codes, tuple) or any(not isinstance(code, str) for code in self.reason_codes):
            raise ValueError("reason_codes must be a tuple of strings")
        if not isinstance(self.verified_fields, tuple) or any(
            not isinstance(field, str) or not field.strip() for field in self.verified_fields
        ):
            raise ValueError("verified_fields must be a tuple of non-empty strings")
        if self.candidate_decision not in {None, "ACCEPT", "REJECT"}:
            raise ValueError("candidate_decision must be ACCEPT or REJECT")
        if self.bank_snapshot_id is not None and (
            not isinstance(self.bank_snapshot_id, str) or not self.bank_snapshot_id.strip()
        ):
            raise ValueError("bank_snapshot_id must be a non-empty string when present")
        if not isinstance(self.previous_hash, str) or not isinstance(self.entry_hash, str):
            raise ValueError("audit hashes must be strings")

    def payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "store_id": self.store_id,
            "occurred_at": self.occurred_at,
            "invoice_id": self.invoice_id,
            "match_scores": [[name, score] for name, score in self.match_scores],
            "candidate_id": self.candidate_id,
            "verdict": self.verdict,
            "reason_codes": list(self.reason_codes),
            "verified_fields": list(self.verified_fields),
            "detection_kind": self.detection_kind,
            "reviewer_id": self.reviewer_id,
            "review_reason": self.review_reason,
            "candidate_decision": self.candidate_decision,
            "bank_snapshot_id": self.bank_snapshot_id,
            "previous_hash": self.previous_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "entry_hash": self.entry_hash}


@dataclass(frozen=True)
class AuditTrail:
    """Append-only in-memory trail; persistence must use durable append semantics."""

    entries: tuple[AuditEvent, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple) or any(not isinstance(entry, AuditEvent) for entry in self.entries):
            raise ValueError("entries must be an immutable tuple of AuditEvent records")

    def append(
        self,
        *,
        event_type: AuditEventType,
        store_id: str,
        occurred_at: str | datetime,
        invoice_id: str | None = None,
        match_scores: tuple[tuple[str, float], ...] | dict[str, float] = (),
        candidate_id: str | None = None,
        verdict: Verdict | str | None = None,
        reason_codes: tuple[str, ...] | list[str] = (),
        verified_fields: tuple[str, ...] | list[str] = (),
        detection_kind: str | None = None,
        reviewer_id: str | None = None,
        review_reason: str | None = None,
        candidate_decision: str | None = None,
        bank_snapshot_id: str | None = None,
        event_id: str | None = None,
    ) -> "AuditTrail":
        if not isinstance(store_id, str) or not store_id.strip():
            raise ValueError("store_id must be non-empty")
        if bank_snapshot_id is not None and (
            not isinstance(bank_snapshot_id, str) or not bank_snapshot_id.strip()
        ):
            raise ValueError("bank_snapshot_id must be a non-empty string when provided")
        existing_ids = {entry.event_id for entry in self.entries}
        new_event_id = event_id or uuid4().hex
        if new_event_id in existing_ids:
            raise ValueError("event_id already exists in this audit trail")
        scores = match_scores.items() if isinstance(match_scores, dict) else match_scores
        normalized_scores = tuple(sorted((str(name), float(score)) for name, score in scores))
        if any(not name or not math.isfinite(score) or not 0 <= score <= 1 for name, score in normalized_scores):
            raise ValueError("match scores must be named finite values in [0, 1]")
        normalized_verdict = _value(verdict) if verdict is not None else None
        normalized_detection_kind = _value(detection_kind) if detection_kind is not None else None
        normalized_codes = tuple(str(_value(code)) for code in reason_codes)
        if any(not isinstance(field, str) or not field.strip() for field in verified_fields):
            raise ValueError("verified_fields must contain non-empty strings")
        normalized_verified_fields = tuple(sorted({field.strip() for field in verified_fields}))
        previous_hash = self.entries[-1].entry_hash if self.entries else GENESIS_HASH
        timestamp = _timestamp_text(occurred_at)
        fields = {
            "event_id": new_event_id,
            "event_type": _value(event_type),
            "store_id": store_id,
            "occurred_at": timestamp,
            "invoice_id": invoice_id,
            "match_scores": [[name, score] for name, score in normalized_scores],
            "candidate_id": candidate_id,
            "verdict": normalized_verdict,
            "reason_codes": list(normalized_codes),
            "verified_fields": list(normalized_verified_fields),
            "detection_kind": normalized_detection_kind,
            "reviewer_id": reviewer_id,
            "review_reason": review_reason,
            "candidate_decision": candidate_decision,
            "bank_snapshot_id": bank_snapshot_id,
            "previous_hash": previous_hash,
        }
        encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        entry_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        entry = AuditEvent(
            event_id=new_event_id,
            event_type=AuditEventType(_value(event_type)),
            store_id=store_id,
            occurred_at=timestamp,
            invoice_id=invoice_id,
            match_scores=normalized_scores,
            candidate_id=candidate_id,
            verdict=normalized_verdict,
            reason_codes=normalized_codes,
            verified_fields=normalized_verified_fields,
            detection_kind=normalized_detection_kind,
            reviewer_id=reviewer_id,
            review_reason=review_reason,
            candidate_decision=candidate_decision,
            bank_snapshot_id=bank_snapshot_id,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        return AuditTrail((*self.entries, entry))

    def verify(self) -> bool:
        previous_hash = GENESIS_HASH
        seen_ids: set[str] = set()
        for entry in self.entries:
            if entry.event_id in seen_ids or entry.previous_hash != previous_hash:
                return False
            seen_ids.add(entry.event_id)
            encoded = json.dumps(entry.payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            expected_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            if entry.entry_hash != expected_hash:
                return False
            previous_hash = entry.entry_hash
        return True

    def escalation_required(
        self,
        store_id: str,
        as_of: str | datetime,
        *,
        threshold: int = 3,
        window: timedelta = timedelta(hours=24),
    ) -> bool:
        if type(threshold) is not int or threshold < 1:
            raise ValueError("threshold must be a positive integer")
        if not isinstance(window, timedelta) or window.total_seconds() <= 0:
            raise ValueError("window must be a positive timedelta")
        end = _parse_timestamp(as_of)
        start = end - window
        resolved_candidates = {
            entry.candidate_id
            for entry in self.entries
            if entry.store_id == store_id
            and entry.candidate_id is not None
            and entry.event_type in {AuditEventType.CANDIDATE_ACCEPTED, AuditEventType.CANDIDATE_REJECTED}
            and _parse_timestamp(entry.occurred_at) <= end
        }
        unresolved_invoice_ids: set[str] = set()
        for entry in self.entries:
            event_time = _parse_timestamp(entry.occurred_at)
            if (
                entry.store_id == store_id
                and entry.event_type is AuditEventType.NEW_TYPE_DETECTED
                and entry.invoice_id is not None
                and start <= event_time <= end
                and (entry.candidate_id is None or entry.candidate_id not in resolved_candidates)
            ):
                unresolved_invoice_ids.add(entry.invoice_id)
        return len(unresolved_invoice_ids) >= threshold


def append_candidate_transition(
    trail: AuditTrail,
    *,
    store_id: str,
    candidate_id: str,
    reviewer_id: str,
    occurred_at: str | datetime,
    review_reason: str,
    decision: str | None = None,
) -> AuditTrail:
    """Append, never edit, a human review or terminal candidate decision."""
    if (
        not isinstance(candidate_id, str)
        or not candidate_id.strip()
        or not isinstance(reviewer_id, str)
        or not reviewer_id.strip()
        or not isinstance(review_reason, str)
        or not review_reason.strip()
    ):
        raise ValueError("candidate_id, reviewer_id, and review_reason are required")
    if decision is None:
        event_type = AuditEventType.CANDIDATE_REVIEWED
    elif decision == "ACCEPT":
        event_type = AuditEventType.CANDIDATE_ACCEPTED
    elif decision == "REJECT":
        event_type = AuditEventType.CANDIDATE_REJECTED
    else:
        raise ValueError("decision must be ACCEPT, REJECT, or None")
    return trail.append(
        event_type=event_type,
        store_id=store_id,
        occurred_at=occurred_at,
        candidate_id=candidate_id,
        reviewer_id=reviewer_id,
        review_reason=review_reason,
        candidate_decision=decision,
        detection_kind="CANDIDATE_LIFECYCLE",
    )


def append_mini_onboarding_review(
    trail: AuditTrail,
    *,
    store_id: str,
    candidate_id: str,
    invoice_id: str,
    reviewer_id: str,
    occurred_at: str | datetime,
    review_reason: str,
    reason_codes: tuple[str, ...] | list[str],
    verified_fields: tuple[str, ...] | list[str],
) -> AuditTrail:
    """Append an individual N=4 invoice review without changing its detection event."""
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (candidate_id, invoice_id, reviewer_id, review_reason)
    ):
        raise ValueError("candidate_id, invoice_id, reviewer_id, and review_reason are required")
    if not verified_fields:
        raise ValueError("verified_fields are required for a mini-onboarding review")
    return trail.append(
        event_type=AuditEventType.MINI_ONBOARDING_INVOICE_REVIEWED,
        store_id=store_id,
        occurred_at=occurred_at,
        invoice_id=invoice_id,
        candidate_id=candidate_id,
        verdict=Verdict.REVIEW,
        reason_codes=reason_codes,
        verified_fields=verified_fields,
        detection_kind="MINI_ONBOARDING_INVOICE",
        reviewer_id=reviewer_id,
        review_reason=review_reason,
    )


def append_mini_onboarding_lock(
    trail: AuditTrail,
    *,
    store_id: str,
    candidate_id: str,
    bank_snapshot_id: str,
    locked_by: str,
    locked_at: str | datetime,
) -> AuditTrail:
    """Append the explicit E-05 snapshot-lock action after N=4 is complete."""
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (candidate_id, bank_snapshot_id, locked_by)
    ):
        raise ValueError("candidate_id, bank_snapshot_id, and locked_by are required")
    return trail.append(
        event_type=AuditEventType.MINI_ONBOARDING_LOCKED,
        store_id=store_id,
        occurred_at=locked_at,
        candidate_id=candidate_id,
        reviewer_id=locked_by,
        review_reason="N=4 mini-onboarding bank snapshot explicitly locked",
        detection_kind="MINI_ONBOARDING_LOCKED",
        bank_snapshot_id=bank_snapshot_id,
    )
