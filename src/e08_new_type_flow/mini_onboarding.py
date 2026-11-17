"""N=4 review-only onboarding cycle for an accepted E-08 candidate."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from e05_template_bank import TemplateMatch
from e06_onboarding_verdict import ReasonCode, Verdict, VerdictResult, required_owner_verification_fields

from .candidate import CandidateState, TemplateCandidate, _timestamp
from .detector import DetectionKind, DetectionResult


class MiniOnboardingState(str, Enum):
    COLLECTING = "COLLECTING"
    READY_TO_LOCK = "READY_TO_LOCK"
    LOCKED = "LOCKED"


@dataclass(frozen=True)
class MiniInvoiceReview:
    invoice_id: str
    reviewer_id: str
    reviewed_at: str
    reason_codes: tuple[str, ...]
    verified_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.invoice_id, str)
            or not self.invoice_id.strip()
            or not isinstance(self.reviewer_id, str)
            or not self.reviewer_id.strip()
        ):
            raise ValueError("invoice_id and reviewer_id are required")
        if (
            not isinstance(self.reason_codes, tuple)
            or not self.reason_codes
            or any(not isinstance(code, str) for code in self.reason_codes)
        ):
            raise ValueError("reason_codes must be a tuple of strings")
        if not isinstance(self.verified_fields, tuple) or not self.verified_fields or any(
            not isinstance(field, str) or not field.strip() for field in self.verified_fields
        ):
            raise ValueError("verified_fields must be a tuple of non-empty field names")
        _timestamp(self.reviewed_at)


@dataclass(frozen=True)
class MiniOnboarding:
    candidate_id: str
    store_id: str
    required_count: int = 4
    reviews: tuple[MiniInvoiceReview, ...] = ()
    state: MiniOnboardingState = MiniOnboardingState.COLLECTING
    bank_snapshot_id: str | None = None
    locked_by: str | None = None
    locked_at: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.candidate_id, str)
            or not self.candidate_id.strip()
            or not isinstance(self.store_id, str)
            or not self.store_id.strip()
        ):
            raise ValueError("candidate_id and store_id are required")
        if not isinstance(self.reviews, tuple) or any(
            not isinstance(review, MiniInvoiceReview) for review in self.reviews
        ):
            raise ValueError("reviews must be a tuple of MiniInvoiceReview records")
        if type(self.required_count) is not int or self.required_count != 4:
            raise ValueError("E-08 mini-onboarding requires exactly four invoices")
        if not isinstance(self.state, MiniOnboardingState):
            object.__setattr__(self, "state", MiniOnboardingState(self.state))
        invoice_ids = [review.invoice_id for review in self.reviews]
        if len(invoice_ids) != len(set(invoice_ids)):
            raise ValueError("mini-onboarding invoice IDs must be unique")
        if len(self.reviews) > self.required_count:
            raise ValueError("mini-onboarding cannot exceed its required invoice count")
        if self.state is MiniOnboardingState.COLLECTING and len(self.reviews) >= self.required_count:
            raise ValueError("a complete mini-onboarding must be READY_TO_LOCK or LOCKED")
        if self.state in {MiniOnboardingState.READY_TO_LOCK, MiniOnboardingState.LOCKED} and len(self.reviews) != self.required_count:
            raise ValueError("mini-onboarding can complete only after four reviewed invoices")
        if self.state is MiniOnboardingState.LOCKED:
            if (
                not isinstance(self.bank_snapshot_id, str)
                or not self.bank_snapshot_id.strip()
                or not isinstance(self.locked_by, str)
                or not self.locked_by.strip()
            ):
                raise ValueError("LOCKED mini-onboarding requires a snapshot ID and lock audit")
            _timestamp(self.locked_at)
        elif any(value is not None for value in (self.bank_snapshot_id, self.locked_by, self.locked_at)):
            raise ValueError("bank snapshot fields may be set only after mini-onboarding is LOCKED")

    @classmethod
    def start(cls, candidate: TemplateCandidate) -> "MiniOnboarding":
        if candidate.state is not CandidateState.ACCEPTED:
            raise ValueError("mini-onboarding starts only after a candidate is ACCEPTED")
        return cls(candidate_id=candidate.candidate_id, store_id=candidate.store_id)

    @property
    def completed_invoice_ids(self) -> tuple[str, ...]:
        return tuple(review.invoice_id for review in self.reviews)

    @property
    def remaining_count(self) -> int:
        return self.required_count - len(self.reviews)

    def record_reviewed_invoice(
        self,
        invoice: Mapping[str, Any],
        detection: DetectionResult,
        *,
        reviewer_id: str,
        reviewed_at: str,
        verified_fields: Sequence[str],
    ) -> "MiniOnboarding":
        if self.state is not MiniOnboardingState.COLLECTING:
            raise ValueError("mini-onboarding no longer accepts invoices")
        if not isinstance(invoice, Mapping) or not isinstance(detection, DetectionResult):
            raise TypeError("a Canonical mapping and E-08 DetectionResult are required")
        if detection.kind is not DetectionKind.NEW_TYPE:
            raise ValueError("only a matching new-type detection can count toward this candidate")
        if (
            detection.store_id != self.store_id
            or detection.invoice_id != invoice.get("invoice_id")
        ):
            raise ValueError("the E-08 detection must identify this invoice and candidate store")
        if (
            detection.candidate is None
            or detection.candidate.candidate_id != self.candidate_id
            or detection.candidate.store_id != self.store_id
            or detection.candidate.state is not CandidateState.ACCEPTED
        ):
            raise ValueError("the accepted candidate must match the detected invoice type")
        verdict_result = detection.verdict_result
        if not isinstance(verdict_result, VerdictResult):
            raise TypeError("E-08 DetectionResult must carry an E-06 VerdictResult")
        if verdict_result.verdict is not Verdict.REVIEW:
            raise ValueError("all new-type mini-onboarding invoices must remain REVIEW")
        if not isinstance(verdict_result.reason_codes, tuple) or any(
            not isinstance(code, ReasonCode) for code in verdict_result.reason_codes
        ):
            raise TypeError("E-06 reason_codes API shape is incompatible")
        if not isinstance(verdict_result.template_match, TemplateMatch):
            raise ValueError("an E-05 template match is required for mini-onboarding evidence")
        reason_codes = set(verdict_result.reason_codes)
        blocking_reasons = {
            ReasonCode.SCHEMA_INVALID,
            ReasonCode.NUMS_INCONSISTENT,
            ReasonCode.NO_MATCH,
            ReasonCode.PARTIAL_MATCH,
            ReasonCode.LOW_CONFIDENCE,
            ReasonCode.ATTENTION_REQUIRED,
            ReasonCode.CANONICAL_STATE_NOT_READY,
            ReasonCode.ACCOUNTING_ADJUSTMENT_UNSUPPORTED,
            ReasonCode.D14_AGREEMENT_REQUIRED,
            ReasonCode.MULTI_TEMPLATE_AMBIGUOUS,
            ReasonCode.SELF_MATCH_RESUBSTITUTION,
            ReasonCode.DIGIT_COVERAGE_INSUFFICIENT,
            ReasonCode.ONBOARDING_WARMUP,
            ReasonCode.TEMPLATE_BANK_UNLOCKED,
            ReasonCode.MANUAL_OWNER_REJECTED,
            ReasonCode.MANUAL_OVERRIDE_BLOCKED,
            ReasonCode.MANUAL_OVERRIDE_INVALID,
            ReasonCode.MANUAL_OVERRIDE_APPLIED,
        }
        if blocking_reasons.intersection(reason_codes):
            raise ValueError("E-06 hard failures or unresolved gates prevent counting this mini-onboarding invoice")
        if not {ReasonCode.STRUCTURE_VALID, ReasonCode.NUMS_CONSISTENT} <= reason_codes:
            raise ValueError("E-06 must confirm structure and numeric consistency before counting")
        invoice_id = invoice.get("invoice_id")
        if not isinstance(invoice_id, str) or not invoice_id.strip():
            raise ValueError("a Canonical invoice_id is required")
        if invoice.get("store_id") != self.store_id:
            raise ValueError("mini-onboarding invoices must belong to the candidate store")
        if invoice_id in self.completed_invoice_ids:
            raise ValueError("an invoice can count only once")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise ValueError("reviewer_id must be non-empty")
        _timestamp(reviewed_at)
        required_fields = set(required_owner_verification_fields(invoice))
        supplied_fields = {str(field) for field in verified_fields}
        if not required_fields or not required_fields <= supplied_fields:
            raise ValueError("the reviewer must verify every required invoice field")
        review = MiniInvoiceReview(
            invoice_id=invoice_id,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
            reason_codes=tuple(code.value for code in verdict_result.reason_codes),
            verified_fields=tuple(sorted(supplied_fields)),
        )
        reviews = (*self.reviews, review)
        new_state = (
            MiniOnboardingState.READY_TO_LOCK
            if len(reviews) == self.required_count
            else MiniOnboardingState.COLLECTING
        )
        return replace(self, reviews=reviews, state=new_state)

    def lock_bank_snapshot(
        self,
        bank_snapshot_id: str,
        *,
        locked_by: str,
        locked_at: str,
    ) -> "MiniOnboarding":
        if self.state is not MiniOnboardingState.READY_TO_LOCK:
            raise ValueError("exactly four reviewed invoices are required before locking")
        if not isinstance(bank_snapshot_id, str) or not bank_snapshot_id.strip():
            raise ValueError("bank_snapshot_id must be non-empty")
        if not isinstance(locked_by, str) or not locked_by.strip():
            raise ValueError("locked_by must be non-empty")
        _timestamp(locked_at)
        return replace(
            self,
            state=MiniOnboardingState.LOCKED,
            bank_snapshot_id=bank_snapshot_id,
            locked_by=locked_by,
            locked_at=locked_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "store_id": self.store_id,
            "required_count": self.required_count,
            "reviews": [
                {
                    "invoice_id": review.invoice_id,
                    "reviewer_id": review.reviewer_id,
                    "reviewed_at": review.reviewed_at,
                    "reason_codes": list(review.reason_codes),
                    "verified_fields": list(review.verified_fields),
                }
                for review in self.reviews
            ],
            "state": self.state.value,
            "bank_snapshot_id": self.bank_snapshot_id,
            "locked_by": self.locked_by,
            "locked_at": self.locked_at,
        }


def accept_candidate_and_start_mini_onboarding(
    candidate: TemplateCandidate,
    reviewer_id: str,
    decided_at: str,
    reason: str,
) -> tuple[TemplateCandidate, MiniOnboarding]:
    """Apply the human ACCEPT transition and start its separate N=4 cycle."""
    accepted = candidate.accept(reviewer_id, decided_at, reason)
    return accepted, MiniOnboarding.start(accepted)
