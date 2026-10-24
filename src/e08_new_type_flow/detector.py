"""E-08 new-type detection using the existing E-05 and E-06 APIs."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any

from e05_template_bank import LayoutObservation, TemplateBank, TemplateMatch, parse_labeled_integer
from e05_template_bank.confidence import score_bank
from e06_onboarding_verdict import ReasonCode, Verdict, VerdictResult, evaluate_verdict

from .audit import AuditEventType, AuditTrail
from .candidate import CandidateRegistry, CandidateState, TemplateCandidate


class DetectionKind(str, Enum):
    NEW_TYPE = "NEW_TYPE"
    CORRUPTED = "CORRUPTED"
    EXISTING_TYPE = "EXISTING_TYPE"
    INDETERMINATE = "INDETERMINATE"
    ONBOARDING_IN_PROGRESS = "ONBOARDING_IN_PROGRESS"
    BANK_NOT_LOCKED = "BANK_NOT_LOCKED"
    CANDIDATE_BLOCKED = "CANDIDATE_BLOCKED"
    CANDIDATE_TERMINAL = "CANDIDATE_TERMINAL"


class NumericEvidenceStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class DetectionResult:
    kind: DetectionKind
    store_id: str
    invoice_id: str | None
    verdict_result: VerdictResult
    match_scores: tuple[tuple[str, float], ...]
    best_match: TemplateMatch | None
    candidate: TemplateCandidate | None
    audit_trail: AuditTrail
    support_escalation_required: bool
    details: tuple[str, ...] = ()

    @property
    def verdict(self) -> Verdict:
        return self.verdict_result.verdict

    @property
    def reason_codes(self) -> tuple[ReasonCode, ...]:
        return self.verdict_result.reason_codes

    @property
    def reason_code_strings(self) -> tuple[str, ...]:
        return self.verdict_result.reason_code_strings

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "store_id": self.store_id,
            "invoice_id": self.invoice_id,
            "verdict": self.verdict.value,
            "reason_codes": list(self.reason_code_strings),
            "match_scores": {template_id: score for template_id, score in self.match_scores},
            "best_match": self.best_match.to_dict() if self.best_match is not None else None,
            "candidate": self.candidate.to_dict() if self.candidate is not None else None,
            "support_escalation_required": self.support_escalation_required,
            "details": list(self.details),
        }


def _e06_result(
    invoice: Mapping[str, Any] | None,
    bank: TemplateBank | None,
    observation: LayoutObservation | None,
    extraction_confidence: float | None,
    *,
    accepted_invoice_count: int,
    bank_locked: bool,
    d14_agreement_signed: bool,
) -> VerdictResult:
    """Call E-06; on an unexpected runtime/API result, fail closed to REVIEW."""
    try:
        result = evaluate_verdict(
            invoice,
            bank,
            observation,
            extraction_confidence,
            processed_invoice_count=accepted_invoice_count,
            template_bank_locked=bank_locked,
            d14_agreement_signed=d14_agreement_signed,
            require_kit_digit_coverage=False,
        )
        if not isinstance(result, VerdictResult):
            raise TypeError("E-06 returned an incompatible result shape")
        if (
            not isinstance(result.verdict, Verdict)
            or not isinstance(result.reason_codes, tuple)
            or not result.reason_codes
            or any(not isinstance(code, ReasonCode) for code in result.reason_codes)
            or not isinstance(result.details, tuple)
            or any(not isinstance(detail, str) for detail in result.details)
            or (result.template_match is not None and not isinstance(result.template_match, TemplateMatch))
            or type(result.owner_acceptance_eligible) is not bool
        ):
            raise TypeError("E-06 VerdictResult fields changed shape")
        return result
    except Exception as exc:
        return VerdictResult(
            verdict=Verdict.REVIEW,
            reason_codes=(ReasonCode.NEW_LAYOUT,),
            confidence_score=None,
            template_match=None,
            details=(f"E-06 API/runtime unavailable; held for review ({type(exc).__name__})",),
        )


def _score_bank(
    bank: TemplateBank,
    observation: LayoutObservation,
) -> tuple[tuple[TemplateMatch, ...], tuple[tuple[str, float], ...]]:
    if not isinstance(bank, TemplateBank) or not isinstance(observation, LayoutObservation):
        raise TypeError("E-05 inputs have an incompatible type")
    matches = score_bank(bank.templates, observation, threshold=bank.confidence_threshold)
    if not isinstance(matches, tuple) or len(matches) != len(bank.templates) or not matches:
        raise TypeError("E-05 score_bank returned an incompatible result shape")
    if any(not isinstance(match, TemplateMatch) for match in matches):
        raise TypeError("E-05 score_bank returned a non-TemplateMatch value")
    scores: list[tuple[str, float]] = []
    for match in matches:
        score = float(match.confidence_score)
        if not match.template_id or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("E-05 returned an invalid template score")
        if not isinstance(match.component_scores, Mapping):
            raise TypeError("E-05 TemplateMatch.component_scores changed shape")
        scores.append((match.template_id, score))
    if len({name for name, _ in scores}) != len(scores):
        raise ValueError("E-05 returned duplicate template IDs")
    return matches, tuple(scores)


def _numeric_evidence_status(
    invoice: Mapping[str, Any],
    observation: LayoutObservation,
    e06_result: VerdictResult,
) -> NumericEvidenceStatus:
    """Check evidence coverage; E-06 owns numeric value comparison/verdicts."""
    if ReasonCode.NUMS_INCONSISTENT in e06_result.reason_codes:
        return NumericEvidenceStatus.MISMATCH
    raw_values = observation.values_as_dict()
    line_items = invoice.get("line_items")
    summary = invoice.get("summary")
    if not isinstance(line_items, list) or not line_items or not isinstance(summary, Mapping):
        return NumericEvidenceStatus.INCOMPLETE
    required_fields: list[str] = []
    for index, item in enumerate(line_items):
        if not isinstance(item, Mapping):
            return NumericEvidenceStatus.INCOMPLETE
        required_fields.extend((f"line.{index}.quantity", f"line.{index}.total"))
    required_fields.append("invoice.payable")
    for field_name in required_fields:
        raw_value = raw_values.get(field_name)
        if not isinstance(raw_value, str) or not raw_value:
            return NumericEvidenceStatus.INCOMPLETE
        try:
            parse_labeled_integer(raw_value)
        except (TypeError, ValueError):
            return NumericEvidenceStatus.INCOMPLETE
    return NumericEvidenceStatus.MATCH


def _new_type_review(
    full_result: VerdictResult,
    no_template_result: VerdictResult,
    best_match: TemplateMatch,
    extra_details: tuple[str, ...] = (),
    *,
    numeric_evidence_verified: bool = False,
) -> VerdictResult:
    """Convert only E-06's low-template NO_MATCH into the E-08 new-type REVIEW."""
    codes: list[ReasonCode] = []
    for code in (*full_result.reason_codes, *no_template_result.reason_codes, ReasonCode.NEW_LAYOUT):
        if code is ReasonCode.NO_MATCH or (numeric_evidence_verified and code is ReasonCode.PARTIAL_MATCH):
            continue
        if code not in codes:
            codes.append(code)
    details = tuple(dict.fromkeys((*full_result.details, *no_template_result.details, *extra_details)))
    return VerdictResult(
        verdict=Verdict.REVIEW,
        reason_codes=tuple(codes),
        confidence_score=full_result.confidence_score,
        template_match=best_match,
        details=details,
        owner_acceptance_eligible=False,
    )


def _gated_review(full_result: VerdictResult, *, low_match: bool, detail: str) -> VerdictResult:
    """Keep eligible-looking but not-yet-onboarded inputs at REVIEW, never ACCEPT/REJECT."""
    codes = [code for code in full_result.reason_codes if code is not ReasonCode.NO_MATCH]
    if low_match and ReasonCode.NEW_LAYOUT not in codes:
        codes.append(ReasonCode.NEW_LAYOUT)
    return VerdictResult(
        verdict=Verdict.REVIEW,
        reason_codes=tuple(codes),
        confidence_score=full_result.confidence_score,
        template_match=full_result.template_match,
        details=tuple(dict.fromkeys((*full_result.details, detail))),
        owner_acceptance_eligible=False,
    )


def _event_type(kind: DetectionKind) -> AuditEventType:
    return {
        DetectionKind.NEW_TYPE: AuditEventType.NEW_TYPE_DETECTED,
        DetectionKind.CANDIDATE_BLOCKED: AuditEventType.NEW_TYPE_DETECTED,
        DetectionKind.CANDIDATE_TERMINAL: AuditEventType.NEW_TYPE_DETECTED,
        DetectionKind.CORRUPTED: AuditEventType.CORRUPTED_INVOICE_DETECTED,
        DetectionKind.EXISTING_TYPE: AuditEventType.EXISTING_TYPE_EVALUATED,
    }.get(kind, AuditEventType.INDETERMINATE_DETECTION)


def _finish(
    *,
    kind: DetectionKind,
    verdict_result: VerdictResult,
    store_id: str,
    invoice_id: str | None,
    detected_at: str,
    match_scores: tuple[tuple[str, float], ...],
    best_match: TemplateMatch | None,
    candidate: TemplateCandidate | None,
    audit_trail: AuditTrail,
    details: tuple[str, ...] = (),
) -> DetectionResult:
    trail = audit_trail.append(
        event_type=_event_type(kind),
        store_id=store_id,
        occurred_at=detected_at,
        invoice_id=invoice_id,
        match_scores=match_scores,
        candidate_id=candidate.candidate_id if candidate is not None else None,
        verdict=verdict_result.verdict,
        reason_codes=verdict_result.reason_codes,
        detection_kind=kind,
    )
    escalation = trail.escalation_required(store_id, detected_at)
    return DetectionResult(
        kind=kind,
        store_id=store_id,
        invoice_id=invoice_id,
        verdict_result=verdict_result,
        match_scores=match_scores,
        best_match=best_match,
        candidate=candidate,
        audit_trail=trail,
        support_escalation_required=escalation,
        details=details,
    )


def detect_invoice_type(
    invoice: Mapping[str, Any] | None,
    template_bank: TemplateBank,
    observation: LayoutObservation,
    extraction_confidence: float | None,
    *,
    store_id: str,
    accepted_invoice_count: int,
    template_bank_locked: bool,
    d14_agreement_signed: bool,
    detected_at: str | None = None,
    audit_trail: AuditTrail | None = None,
    candidate_registry: CandidateRegistry | None = None,
) -> DetectionResult:
    """Classify a post-onboarding scan without changing the production bank."""
    if detected_at is None:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    else:
        if not isinstance(detected_at, str) or not detected_at.strip():
            raise ValueError("detected_at must be a non-empty ISO-8601 string")
        try:
            parsed_timestamp = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("detected_at must be ISO-8601 with a UTC offset") from exc
        if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
            raise ValueError("detected_at must include a UTC offset")
        timestamp = detected_at
    trail = audit_trail or AuditTrail()
    registry = candidate_registry or CandidateRegistry()
    if not isinstance(store_id, str) or not store_id.strip():
        raise ValueError("store_id must be non-empty for auditability")
    invoice_id = invoice.get("invoice_id") if isinstance(invoice, Mapping) else None
    invoice_id = invoice_id if isinstance(invoice_id, str) and invoice_id.strip() else None

    # Always let E-06 classify schema and internal arithmetic failures before
    # interpreting a weak template score as a possible new type.
    full_result = _e06_result(
        invoice,
        template_bank if isinstance(template_bank, TemplateBank) else None,
        observation if isinstance(observation, LayoutObservation) else None,
        extraction_confidence,
        accepted_invoice_count=accepted_invoice_count,
        bank_locked=template_bank_locked,
        d14_agreement_signed=d14_agreement_signed,
    )

    try:
        ranked, match_scores = _score_bank(template_bank, observation)
        best_match = ranked[0]
        best_score = match_scores[0][1]
    except Exception as exc:
        # Shape/import/scoring errors never create a candidate or replace E-06.
        hard_codes = {ReasonCode.SCHEMA_INVALID, ReasonCode.NUMS_INCONSISTENT}
        if full_result.verdict is Verdict.REJECT and hard_codes.intersection(full_result.reason_codes):
            return _finish(
                kind=DetectionKind.CORRUPTED,
                verdict_result=full_result,
                store_id=store_id,
                invoice_id=invoice_id,
                detected_at=timestamp,
                match_scores=(),
                best_match=None,
                candidate=None,
                audit_trail=trail,
                details=("E-06 identified a structural or numeric hard failure; no candidate was created",),
            )
        review_result = _e06_result(
            invoice,
            None,
            None,
            extraction_confidence,
            accepted_invoice_count=accepted_invoice_count,
            bank_locked=template_bank_locked,
            d14_agreement_signed=d14_agreement_signed,
        )
        if review_result.verdict is Verdict.REVIEW:
            fallback_codes = tuple(
                code
                for code in dict.fromkeys(
                    (*full_result.reason_codes, *review_result.reason_codes, ReasonCode.NEW_LAYOUT)
                )
                if code is not ReasonCode.NO_MATCH
            )
            review_result = VerdictResult(
                verdict=Verdict.REVIEW,
                reason_codes=fallback_codes,
                confidence_score=full_result.confidence_score,
                template_match=full_result.template_match,
                details=tuple(
                    dict.fromkeys(
                        (*full_result.details, *review_result.details, f"E-05 API/runtime unavailable ({type(exc).__name__})")
                    )
                ),
                owner_acceptance_eligible=False,
            )
        return _finish(
            kind=DetectionKind.INDETERMINATE,
            verdict_result=review_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=(),
            best_match=None,
            candidate=None,
            audit_trail=trail,
            details=(f"E-05 API/runtime unavailable ({type(exc).__name__})",),
        )

    hard_codes = {ReasonCode.SCHEMA_INVALID, ReasonCode.NUMS_INCONSISTENT}
    if full_result.verdict is Verdict.REJECT and hard_codes.intersection(full_result.reason_codes):
        return _finish(
            kind=DetectionKind.CORRUPTED,
            verdict_result=full_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=("E-06 identified a structural or numeric hard failure; no candidate was created",),
        )

    if type(accepted_invoice_count) is not int or accepted_invoice_count < 4:
        return _finish(
            kind=DetectionKind.ONBOARDING_IN_PROGRESS,
            verdict_result=_gated_review(
                full_result,
                low_match=best_score < template_bank.confidence_threshold,
                detail="E-08 candidate creation is disabled until four initial invoices are owner-accepted",
            ),
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=("E-08 candidate creation is disabled until four initial invoices are owner-accepted",),
        )
    if template_bank_locked is not True:
        return _finish(
            kind=DetectionKind.BANK_NOT_LOCKED,
            verdict_result=_gated_review(
                full_result,
                low_match=best_score < template_bank.confidence_threshold,
                detail="E-08 candidate creation requires a locked per-store bank",
            ),
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=("E-08 candidate creation requires a locked per-store bank",),
        )

    if best_score >= template_bank.confidence_threshold:
        return _finish(
            kind=DetectionKind.EXISTING_TYPE,
            verdict_result=full_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
        )

    no_template_result = _e06_result(
        invoice,
        None,
        None,
        extraction_confidence,
        accepted_invoice_count=accepted_invoice_count,
        bank_locked=True,
        d14_agreement_signed=d14_agreement_signed,
    )
    if no_template_result.verdict is Verdict.REJECT and hard_codes.intersection(no_template_result.reason_codes):
        return _finish(
            kind=DetectionKind.CORRUPTED,
            verdict_result=no_template_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=("E-06 identified a structural or numeric hard failure; no candidate was created",),
        )

    if not isinstance(invoice, Mapping) or invoice.get("store_id") != store_id:
        review_result = _new_type_review(
            full_result,
            no_template_result,
            best_match,
            ("Invoice/store context is absent or inconsistent; no candidate was created",),
        )
        return _finish(
            kind=DetectionKind.INDETERMINATE,
            verdict_result=review_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=("Invoice/store context is absent or inconsistent",),
        )

    numeric_status = _numeric_evidence_status(invoice, observation, full_result)
    if numeric_status is NumericEvidenceStatus.MISMATCH:
        if full_result.verdict is Verdict.REJECT and ReasonCode.NUMS_INCONSISTENT in full_result.reason_codes:
            kind = DetectionKind.CORRUPTED
            result = full_result
            detail = "Raw numeric observations disagree with Canonical values"
        else:
            kind = DetectionKind.INDETERMINATE
            result = _new_type_review(
                full_result,
                no_template_result,
                best_match,
                ("Raw numeric disagreement was not conclusively classified by E-06",),
            )
            detail = "Raw numeric disagreement requires human review; no candidate was created"
        return _finish(
            kind=kind,
            verdict_result=result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=(detail,),
        )
    if numeric_status is NumericEvidenceStatus.INCOMPLETE:
        review_result = _new_type_review(
            full_result,
            no_template_result,
            best_match,
            ("Raw numeric observations are incomplete or unreadable; no candidate was created",),
        )
        return _finish(
            kind=DetectionKind.INDETERMINATE,
            verdict_result=review_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=("Raw numeric observations are incomplete or unreadable",),
        )

    required_review_codes = {
        ReasonCode.ATTENTION_REQUIRED,
        ReasonCode.CANONICAL_STATE_NOT_READY,
        ReasonCode.ACCOUNTING_ADJUSTMENT_UNSUPPORTED,
        ReasonCode.D14_AGREEMENT_REQUIRED,
        ReasonCode.MULTI_TEMPLATE_AMBIGUOUS,
        ReasonCode.SELF_MATCH_RESUBSTITUTION,
    }
    blockers = required_review_codes.intersection(full_result.reason_codes)
    extraction_is_valid = False
    if extraction_confidence is not None:
        try:
            extraction_value = float(extraction_confidence)
            extraction_is_valid = math.isfinite(extraction_value) and 0.80 <= extraction_value <= 1.0
        except (TypeError, ValueError, OverflowError):
            extraction_is_valid = False
    no_template_has_integrity = (
        no_template_result.verdict is Verdict.REVIEW
        and ReasonCode.STRUCTURE_VALID in no_template_result.reason_codes
        and ReasonCode.NUMS_CONSISTENT in no_template_result.reason_codes
    )
    if blockers or not extraction_is_valid or not no_template_has_integrity:
        review_result = _new_type_review(
            full_result,
            no_template_result,
            best_match,
            ("New-type candidate gates are incomplete; retained REVIEW without a candidate",),
            numeric_evidence_verified=True,
        )
        return _finish(
            kind=DetectionKind.INDETERMINATE,
            verdict_result=review_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=("New-type candidate gates are incomplete",),
        )

    proposal_time = timestamp
    proposed = TemplateCandidate.propose(store_id, invoice_id or observation.source_id, observation, proposal_time)
    candidate, disposition = registry.propose_or_reuse(proposed)
    if disposition == "blocked_by_unresolved_candidate":
        review_result = _new_type_review(
            full_result,
            no_template_result,
            best_match,
            ("A different unresolved candidate already exists for this store",),
            numeric_evidence_verified=True,
        )
        return _finish(
            kind=DetectionKind.CANDIDATE_BLOCKED,
            verdict_result=review_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=None,
            audit_trail=trail,
            details=("A different unresolved candidate already exists for this store",),
        )
    if candidate is None or candidate.state is CandidateState.REJECTED:
        review_result = _new_type_review(
            full_result,
            no_template_result,
            best_match,
            ("A previously rejected candidate cannot be proposed again",),
            numeric_evidence_verified=True,
        )
        return _finish(
            kind=DetectionKind.CANDIDATE_TERMINAL,
            verdict_result=review_result,
            store_id=store_id,
            invoice_id=invoice_id,
            detected_at=timestamp,
            match_scores=match_scores,
            best_match=best_match,
            candidate=candidate,
            audit_trail=trail,
            details=("Candidate is terminal and cannot be reused as a production template",),
        )

    review_result = _new_type_review(
        full_result,
        no_template_result,
        best_match,
        (f"New type has no score at or above the {template_bank.confidence_threshold:.3f} bank threshold",),
        numeric_evidence_verified=True,
    )
    return _finish(
        kind=DetectionKind.NEW_TYPE,
        verdict_result=review_result,
        store_id=store_id,
        invoice_id=invoice_id,
        detected_at=timestamp,
        match_scores=match_scores,
        best_match=best_match,
        candidate=candidate,
        audit_trail=trail,
        details=(f"Candidate {candidate.candidate_id} is {disposition}",),
    )
