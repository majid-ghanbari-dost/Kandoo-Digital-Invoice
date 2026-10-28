"""Separate, human-gated template-candidate records for E-08."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
import hashlib
import json
from threading import RLock
from typing import Any

from e05_template_bank import LayoutObservation


class CandidateState(str, Enum):
    PROPOSED = "PROPOSED"
    REVIEWED = "REVIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class CandidateTransitionError(ValueError):
    """Raised when a candidate lifecycle transition is not permitted."""


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO-8601 string with a UTC offset") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed


def _round(values: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(round(float(value), 6) for value in values)


def _layout_signature(observation: LayoutObservation) -> tuple[tuple[str, tuple[float, ...]], ...]:
    width = float(observation.image_width)
    row_heights = tuple((bottom - top) / width for top, bottom in observation.row_bands)
    row_centers = tuple((top + bottom) / 2 / width for top, bottom in observation.row_bands)
    row_pitches = tuple(right - left for left, right in zip(row_centers, row_centers[1:]))
    return (
        ("page_aspect_ratio", _round((observation.image_width / observation.image_height,))),
        ("normalized_column_boundaries", _round(observation.normalized_column_boundaries)),
        ("row_heights_over_width", _round(row_heights)),
        ("row_pitches_over_width", _round(row_pitches)),
        ("table_top_over_width", _round((observation.table_top_over_width,))),
        ("payable_gap_over_width", _round((observation.payable_gap_over_width,))),
        ("payable_bbox_over_width", _round(observation.payable_bbox_over_width)),
    )


def _field_positions(observation: LayoutObservation) -> tuple[tuple[str, tuple[float, ...]], ...]:
    columns = observation.normalized_column_boundaries
    positions = [
        (f"column_{index}", _round((columns[index], columns[index + 1])))
        for index in range(len(columns) - 1)
    ]
    positions.append(("payable_bbox_over_width", _round(observation.payable_bbox_over_width)))
    return tuple(positions)


def _numeric_patterns(
    observation: LayoutObservation,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[int, ...], tuple[str, ...]]:
    numeric_values = tuple(
        (field_name, text)
        for field_name, text in observation.field_values
        if field_name == "invoice.payable"
        or field_name.endswith(".quantity")
        or field_name.endswith(".total")
    )
    digits = tuple(sorted({character for _, text in numeric_values for character in text if character.isdigit()}))
    separators = tuple(
        sorted(
            {
                character
                for _, text in numeric_values
                for character in text
                if not character.isdigit() and not character.isspace()
            }
        )
    )
    group_sizes = tuple(
        sorted(
            {
                len(group)
                for field_name, text in numeric_values
                if field_name == "invoice.payable" or field_name.endswith(".total")
                for separator in separators
                for group in text.split(separator)[1:]
            }
        )
    )
    field_names = tuple(sorted(field_name for field_name, _ in numeric_values))
    return digits, separators, group_sizes, field_names


@dataclass(frozen=True)
class TemplateCandidate:
    candidate_id: str
    store_id: str
    layout_signature: tuple[tuple[str, tuple[float, ...]], ...]
    field_positions: tuple[tuple[str, tuple[float, ...]], ...]
    numeric_digit_alphabet: tuple[str, ...]
    numeric_separators: tuple[str, ...]
    numeric_group_sizes: tuple[int, ...]
    observed_numeric_fields: tuple[str, ...]
    source_invoice_ids: tuple[str, ...]
    proposed_at: str
    state: CandidateState = CandidateState.PROPOSED
    reviewer_id: str | None = None
    reviewed_at: str | None = None
    review_reason: str | None = None
    decision_by: str | None = None
    decided_at: str | None = None
    decision_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, CandidateState):
            object.__setattr__(self, "state", CandidateState(self.state))
        _timestamp(self.proposed_at)
        if (
            not isinstance(self.candidate_id, str)
            or not self.candidate_id.strip()
            or not isinstance(self.store_id, str)
            or not self.store_id.strip()
        ):
            raise ValueError("candidate_id and store_id are required")
        if (
            not isinstance(self.source_invoice_ids, tuple)
            or not self.source_invoice_ids
            or any(not isinstance(value, str) or not value.strip() for value in self.source_invoice_ids)
            or len(set(self.source_invoice_ids)) != len(self.source_invoice_ids)
        ):
            raise ValueError("source_invoice_ids must contain unique non-empty IDs")
        if self.state is CandidateState.PROPOSED:
            if any(
                value is not None
                for value in (
                    self.reviewer_id,
                    self.reviewed_at,
                    self.review_reason,
                    self.decision_by,
                    self.decided_at,
                    self.decision_reason,
                )
            ):
                raise ValueError("a PROPOSED candidate cannot contain review or decision fields")
        elif self.state is CandidateState.REVIEWED:
            if (
                not isinstance(self.reviewer_id, str)
                or not self.reviewer_id.strip()
                or not isinstance(self.review_reason, str)
                or not self.review_reason.strip()
            ):
                raise ValueError("a REVIEWED candidate requires reviewer, timestamp, and review reason")
            _timestamp(self.reviewed_at)
            if self.decision_by is not None or self.decided_at is not None or self.decision_reason is not None:
                raise ValueError("a REVIEWED candidate cannot contain a terminal decision")
        else:
            if (
                not isinstance(self.reviewer_id, str)
                or not self.reviewer_id.strip()
                or not isinstance(self.review_reason, str)
                or not self.review_reason.strip()
                or not isinstance(self.decision_by, str)
                or not self.decision_by.strip()
            ):
                raise ValueError("a decided candidate requires review and decision audit fields")
            _timestamp(self.reviewed_at)
            _timestamp(self.decided_at)
            if not isinstance(self.decision_reason, str) or not self.decision_reason.strip():
                raise ValueError("a decided candidate requires a decision reason")

    @classmethod
    def propose(
        cls,
        store_id: str,
        invoice_id: str,
        observation: LayoutObservation,
        proposed_at: str,
    ) -> "TemplateCandidate":
        """Create a deterministic candidate from geometry and format descriptors only."""
        if not isinstance(store_id, str) or not store_id.strip():
            raise ValueError("store_id must be non-empty")
        if not isinstance(invoice_id, str) or not invoice_id.strip():
            raise ValueError("invoice_id must be non-empty")
        _timestamp(proposed_at)
        signature = _layout_signature(observation)
        positions = _field_positions(observation)
        digits, separators, group_sizes, field_names = _numeric_patterns(observation)
        fingerprint = {
            "store_id": store_id,
            "layout_signature": {name: values for name, values in signature},
            "numeric_digit_alphabet": digits,
            "numeric_separators": separators,
            "numeric_group_sizes": group_sizes,
        }
        encoded = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        candidate_id = "e08-candidate-" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]
        return cls(
            candidate_id=candidate_id,
            store_id=store_id,
            layout_signature=signature,
            field_positions=positions,
            numeric_digit_alphabet=digits,
            numeric_separators=separators,
            numeric_group_sizes=group_sizes,
            observed_numeric_fields=field_names,
            source_invoice_ids=(invoice_id,),
            proposed_at=proposed_at,
        )

    def add_source_invoice(self, invoice_id: str) -> "TemplateCandidate":
        if not isinstance(invoice_id, str) or not invoice_id.strip():
            raise ValueError("invoice_id must be non-empty")
        if invoice_id in self.source_invoice_ids:
            return self
        return replace(self, source_invoice_ids=tuple(sorted((*self.source_invoice_ids, invoice_id))))

    def mark_reviewed(self, reviewer_id: str, reviewed_at: str, reason: str) -> "TemplateCandidate":
        if self.state is not CandidateState.PROPOSED:
            raise CandidateTransitionError("only PROPOSED candidates may transition to REVIEWED")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise ValueError("reviewer_id must be non-empty")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("review reason must be non-empty")
        _timestamp(reviewed_at)
        return replace(
            self,
            state=CandidateState.REVIEWED,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
            review_reason=reason,
        )

    def accept(self, reviewer_id: str, decided_at: str, reason: str) -> "TemplateCandidate":
        return self._decide(CandidateState.ACCEPTED, reviewer_id, decided_at, reason)

    def reject(self, reviewer_id: str, decided_at: str, reason: str) -> "TemplateCandidate":
        return self._decide(CandidateState.REJECTED, reviewer_id, decided_at, reason)

    def _decide(
        self,
        state: CandidateState,
        reviewer_id: str,
        decided_at: str,
        reason: str,
    ) -> "TemplateCandidate":
        if self.state is not CandidateState.REVIEWED:
            raise CandidateTransitionError("only REVIEWED candidates may be ACCEPTED or REJECTED")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise ValueError("reviewer_id must be non-empty")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("decision reason must be non-empty")
        _timestamp(decided_at)
        return replace(
            self,
            state=state,
            decision_by=reviewer_id,
            decided_at=decided_at,
            decision_reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "store_id": self.store_id,
            "layout_signature": {name: list(values) for name, values in self.layout_signature},
            "field_positions": {name: list(values) for name, values in self.field_positions},
            "numeric_digit_alphabet": list(self.numeric_digit_alphabet),
            "numeric_separators": list(self.numeric_separators),
            "numeric_group_sizes": list(self.numeric_group_sizes),
            "observed_numeric_fields": list(self.observed_numeric_fields),
            "source_invoice_ids": list(self.source_invoice_ids),
            "proposed_at": self.proposed_at,
            "state": self.state.value,
            "reviewer_id": self.reviewer_id,
            "reviewed_at": self.reviewed_at,
            "review_reason": self.review_reason,
            "decision_by": self.decision_by,
            "decided_at": self.decided_at,
            "decision_reason": self.decision_reason,
        }


class CandidateRegistry:
    """In-memory candidate registry, deliberately separate from TemplateBank."""

    def __init__(self) -> None:
        self._candidates: dict[str, TemplateCandidate] = {}
        self._lock = RLock()

    @property
    def candidates(self) -> tuple[TemplateCandidate, ...]:
        with self._lock:
            return tuple(self._candidates[key] for key in sorted(self._candidates))

    def get(self, candidate_id: str) -> TemplateCandidate | None:
        with self._lock:
            return self._candidates.get(candidate_id)

    def unresolved_for_store(self, store_id: str) -> tuple[TemplateCandidate, ...]:
        with self._lock:
            return tuple(
                candidate
                for candidate in self._candidates.values()
                if candidate.store_id == store_id
                and candidate.state in {CandidateState.PROPOSED, CandidateState.REVIEWED}
            )

    def propose_or_reuse(
        self,
        candidate: TemplateCandidate,
    ) -> tuple[TemplateCandidate | None, str]:
        if candidate.state is not CandidateState.PROPOSED:
            raise CandidateTransitionError("only PROPOSED candidates may enter the registry")
        with self._lock:
            existing = self._candidates.get(candidate.candidate_id)
            if existing is not None:
                if existing.state in {CandidateState.PROPOSED, CandidateState.REVIEWED}:
                    updated = existing
                    for invoice_id in candidate.source_invoice_ids:
                        updated = updated.add_source_invoice(invoice_id)
                    self._candidates[updated.candidate_id] = updated
                    return updated, "reused"
                return existing, "terminal"

            if any(
                item.store_id == candidate.store_id
                and item.state in {CandidateState.PROPOSED, CandidateState.REVIEWED}
                for item in self._candidates.values()
            ):
                return None, "blocked_by_unresolved_candidate"
            self._candidates[candidate.candidate_id] = candidate
            return candidate, "created"

    def update(self, candidate: TemplateCandidate) -> None:
        with self._lock:
            self._update_locked(candidate)

    def _update_locked(self, candidate: TemplateCandidate) -> None:
        existing = self._candidates.get(candidate.candidate_id)
        if existing is None:
            raise KeyError(candidate.candidate_id)
        immutable_fields = (
            "candidate_id",
            "store_id",
            "layout_signature",
            "field_positions",
            "numeric_digit_alphabet",
            "numeric_separators",
            "numeric_group_sizes",
            "observed_numeric_fields",
            "proposed_at",
        )
        if any(getattr(existing, field) != getattr(candidate, field) for field in immutable_fields):
            raise ValueError("candidate identity, evidence, and proposal time are immutable")
        if not set(existing.source_invoice_ids) <= set(candidate.source_invoice_ids):
            raise ValueError("candidate source invoice IDs are append-only")
        allowed = {
            CandidateState.PROPOSED: {CandidateState.PROPOSED, CandidateState.REVIEWED},
            CandidateState.REVIEWED: {CandidateState.REVIEWED, CandidateState.ACCEPTED, CandidateState.REJECTED},
            CandidateState.ACCEPTED: {CandidateState.ACCEPTED},
            CandidateState.REJECTED: {CandidateState.REJECTED},
        }
        if candidate.state not in allowed[existing.state]:
            raise CandidateTransitionError("candidate registry cannot reverse a terminal lifecycle transition")
        if existing.state in {CandidateState.ACCEPTED, CandidateState.REJECTED}:
            if candidate != existing:
                raise CandidateTransitionError("terminal candidates are immutable")
        elif existing.state is CandidateState.PROPOSED and candidate.state is CandidateState.PROPOSED:
            if any(
                getattr(existing, field) != getattr(candidate, field)
                for field in (
                    "reviewer_id",
                    "reviewed_at",
                    "review_reason",
                    "decision_by",
                    "decided_at",
                    "decision_reason",
                )
            ):
                raise CandidateTransitionError("review fields may only be set by the PROPOSED to REVIEWED transition")
        elif existing.state is CandidateState.REVIEWED:
            if (existing.reviewer_id, existing.reviewed_at, existing.review_reason) != (
                candidate.reviewer_id,
                candidate.reviewed_at,
                candidate.review_reason,
            ):
                raise CandidateTransitionError("the original candidate review record is immutable")
            if candidate.state is CandidateState.REVIEWED and (
                existing.decision_by,
                existing.decided_at,
                existing.decision_reason,
            ) != (candidate.decision_by, candidate.decided_at, candidate.decision_reason):
                raise CandidateTransitionError("decision fields may only be set by a terminal transition")
        self._candidates[candidate.candidate_id] = candidate
