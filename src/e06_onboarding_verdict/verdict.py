"""Fail-closed E-06 onboarding verdicts consuming the E-05 template bank."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any

from e05_template_bank import (
    LayoutObservation,
    TemplateBank,
    TemplateMatch,
    match_observation,
    parse_labeled_integer,
)
from e05_template_bank.confidence import score_bank
from image_extraction_adapter.canonical_invoice import validate_canonical_invoice

from .reason_codes import ReasonCode, Verdict
from .thresholds import DEFAULT_THRESHOLDS, VerdictThresholds


@dataclass(frozen=True)
class ManualOverride:
    """Store-owner review action with fields needed for an audit record.

    E-06 validates the record's shape. The caller must authenticate the owner,
    verify any signature, and persist the audit event durably.
    """

    target: Verdict
    actor_id: str
    actor_role: str
    audit_id: str
    reason: str
    occurred_at: str
    verified_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.target, Verdict):
            object.__setattr__(self, "target", Verdict(self.target))
        object.__setattr__(self, "verified_fields", tuple(sorted(set(self.verified_fields))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target.value,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "audit_id": self.audit_id,
            "reason": self.reason,
            "occurred_at": self.occurred_at,
            "verified_fields": list(self.verified_fields),
        }


@dataclass(frozen=True)
class VerdictResult:
    verdict: Verdict
    reason_codes: tuple[ReasonCode, ...]
    confidence_score: float | None
    template_match: TemplateMatch | None
    details: tuple[str, ...] = ()
    audit_record: Mapping[str, Any] | None = None
    owner_acceptance_eligible: bool = False

    @property
    def reason_code_strings(self) -> tuple[str, ...]:
        return tuple(code.value for code in self.reason_codes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reason_codes": list(self.reason_code_strings),
            "confidence_score": self.confidence_score,
            "template_match": self.template_match.to_dict() if self.template_match else None,
            "details": list(self.details),
            "audit_record": dict(self.audit_record) if self.audit_record else None,
            "owner_acceptance_eligible": self.owner_acceptance_eligible,
        }


def required_owner_verification_fields(invoice: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the visible business fields an owner must confirm to ACCEPT."""
    fields = {"customer.phone", "summary.subtotal", "summary.payable"}
    line_items = invoice.get("line_items", [])
    if isinstance(line_items, (list, tuple)):
        for index, _item in enumerate(line_items):
            fields.update(
                {
                    f"line_items[{index}].product_name",
                    f"line_items[{index}].quantity",
                    f"line_items[{index}].unit_price",
                    f"line_items[{index}].line_total",
                }
            )
    summary = invoice.get("summary", {})
    if not isinstance(summary, Mapping):
        summary = {}
    extra_amounts = summary.get("extra_amounts", {})
    if isinstance(extra_amounts, Mapping):
        for amount_name in extra_amounts:
            fields.add(f"summary.extra_amounts.{amount_name}")
    for collection in ("tax_lines", "discount_lines"):
        lines = summary.get(collection, [])
        if isinstance(lines, (list, tuple)):
            for index, _line in enumerate(lines):
                fields.add(f"summary.{collection}[{index}]")
    header = invoice.get("header", {})
    if not isinstance(header, Mapping):
        header = {}
    for field_name in ("printed_date", "printed_time", "invoice_number"):
        if header.get(field_name) is not None:
            fields.add(f"header.{field_name}")
    return tuple(sorted(fields))


def _result(
    verdict: Verdict,
    reason_codes: Sequence[ReasonCode],
    *,
    confidence_score: float | None = None,
    template_match: TemplateMatch | None = None,
    details: Sequence[str] = (),
    audit_record: Mapping[str, Any] | None = None,
    owner_acceptance_eligible: bool = False,
) -> VerdictResult:
    ordered_codes = tuple(dict.fromkeys(reason_codes))
    return VerdictResult(
        verdict=verdict,
        reason_codes=ordered_codes,
        confidence_score=confidence_score,
        template_match=template_match,
        details=tuple(details),
        audit_record=audit_record,
        owner_acceptance_eligible=owner_acceptance_eligible,
    )


def _valid_override_audit(override: ManualOverride) -> bool:
    required_text = (
        override.actor_id,
        override.audit_id,
        override.reason,
        override.occurred_at,
    )
    if override.actor_role != "store_owner" or any(
        not isinstance(value, str) or not value.strip() for value in required_text
    ):
        return False
    try:
        timestamp = datetime.fromisoformat(override.occurred_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return timestamp.tzinfo is not None and timestamp.utcoffset() is not None


def _apply_manual_override(
    base: VerdictResult,
    override: ManualOverride | None,
    *,
    required_fields: tuple[str, ...],
) -> VerdictResult:
    if override is None:
        return base
    if not isinstance(override, ManualOverride) or not _valid_override_audit(override):
        if base.verdict is Verdict.REJECT:
            return _result(
                Verdict.REJECT,
                (*base.reason_codes, ReasonCode.MANUAL_OVERRIDE_INVALID),
                confidence_score=base.confidence_score,
                template_match=base.template_match,
                details=(*base.details, "Manual override audit is incomplete or invalid."),
                owner_acceptance_eligible=base.owner_acceptance_eligible,
            )
        return _result(
            Verdict.REVIEW,
            (*base.reason_codes, ReasonCode.MANUAL_OVERRIDE_INVALID),
            confidence_score=base.confidence_score,
            template_match=base.template_match,
            details=(*base.details, "Manual override audit is incomplete or invalid."),
            owner_acceptance_eligible=base.owner_acceptance_eligible,
        )

    audit = override.to_dict()
    if override.target is Verdict.ACCEPT:
        has_complete_field_review = set(required_fields) <= set(override.verified_fields)
        can_promote = (
            base.verdict is Verdict.REVIEW
            and base.owner_acceptance_eligible
            and has_complete_field_review
        )
        if can_promote:
            codes = [
                code
                for code in base.reason_codes
                if code is not ReasonCode.OWNER_VERIFICATION_REQUIRED
            ]
            codes.append(ReasonCode.OWNER_VERIFICATION_AUDITED)
            return _result(
                Verdict.ACCEPT,
                codes,
                confidence_score=base.confidence_score,
                template_match=base.template_match,
                details=(*base.details, "Store-owner field verification was recorded."),
                audit_record=audit,
            )
        blocked_verdict = Verdict.REJECT if base.verdict is Verdict.REJECT else Verdict.REVIEW
        return _result(
            blocked_verdict,
            (*base.reason_codes, ReasonCode.MANUAL_OVERRIDE_BLOCKED),
            confidence_score=base.confidence_score,
            template_match=base.template_match,
            details=(*base.details, "Owner override cannot bypass an unmet E-06 gate."),
            audit_record=audit,
            owner_acceptance_eligible=base.owner_acceptance_eligible,
        )

    severity = {Verdict.ACCEPT: 0, Verdict.REVIEW: 1, Verdict.REJECT: 2}
    if severity[override.target] < severity[base.verdict]:
        return _result(
            base.verdict,
            (*base.reason_codes, ReasonCode.MANUAL_OVERRIDE_BLOCKED),
            confidence_score=base.confidence_score,
            template_match=base.template_match,
            details=(*base.details, "Owner override cannot downgrade a hard failure."),
            audit_record=audit,
            owner_acceptance_eligible=base.owner_acceptance_eligible,
        )
    applied_code = (
        ReasonCode.MANUAL_OWNER_REJECTED
        if override.target is Verdict.REJECT
        else ReasonCode.MANUAL_OVERRIDE_APPLIED
    )
    return _result(
        override.target,
        (*base.reason_codes, applied_code),
        confidence_score=base.confidence_score,
        template_match=base.template_match,
        details=(*base.details, "Store-owner override was recorded."),
        audit_record=audit,
        owner_acceptance_eligible=False,
    )


def _has_unresolved_required_data(invoice: Mapping[str, Any]) -> bool:
    if invoice.get("attention_cells"):
        return True
    provenance = invoice.get("provenance", {}).get("fields", {})
    customer_provenance = provenance.get("customer", {})
    if customer_provenance.get("phone") in {"untrusted", "unavailable"}:
        return True
    if invoice.get("customer", {}).get("phone") in {None, ""}:
        return True
    line_provenance = provenance.get("line_items", [])
    for index, item in enumerate(invoice.get("line_items", [])):
        item_labels = line_provenance[index] if index < len(line_provenance) else {}
        for field_name in ("product_name", "quantity", "unit_price", "line_total"):
            if item_labels.get(field_name) in {"untrusted", "unavailable"}:
                return True
    summary_labels = provenance.get("summary", {})
    for field_name in ("subtotal", "payable"):
        if summary_labels.get(field_name) in {"untrusted", "unavailable"}:
            return True
    return False


def _numeric_internal_consistency(invoice: Mapping[str, Any]) -> bool:
    line_items = invoice.get("line_items", [])
    if not line_items:
        return False
    line_sum = 0
    for item in line_items:
        quantity = item.get("quantity")
        line_total = item.get("line_total")
        unit_price = item.get("unit_price")
        if any(type(value) is not int or value < 0 for value in (line_total, unit_price)):
            return False
        if type(quantity) is not int or quantity <= 0:
            return False
        if unit_price * quantity != line_total:
            return False
        line_sum += line_total
    summary = invoice.get("summary", {})
    return (
        summary.get("subtotal") == line_sum
        and summary.get("payable") == line_sum
    )


def _has_unmodeled_adjustments(invoice: Mapping[str, Any]) -> bool:
    """Detect non-zero accounting fields whose semantics E-06 does not apply."""
    summary = invoice.get("summary", {})
    extra_amounts = summary.get("extra_amounts", {})
    if any(amount != 0 for amount in extra_amounts.values()):
        return True
    for adjustment_type in ("tax_lines", "discount_lines"):
        if any(line.get("amount") != 0 for line in summary.get(adjustment_type, [])):
            return True
    return summary.get("rounding") not in (None, 0)


def _raw_numeric_comparison(
    invoice: Mapping[str, Any],
    observation: LayoutObservation,
) -> tuple[bool, bool, bool, tuple[str, ...]]:
    """Return (complete, agrees, has_disagreement, diagnostics) for raw OCR."""
    values = observation.values_as_dict()
    missing_or_unreadable: list[str] = []
    disagreements: list[str] = []
    for index, item in enumerate(invoice.get("line_items", [])):
        for raw_field, canonical_field in (
            (f"line.{index}.quantity", "quantity"),
            (f"line.{index}.total", "line_total"),
        ):
            if raw_field not in values:
                missing_or_unreadable.append(raw_field)
                continue
            try:
                parsed = parse_labeled_integer(values[raw_field])
            except (TypeError, ValueError):
                missing_or_unreadable.append(raw_field)
                continue
            if parsed != item.get(canonical_field):
                disagreements.append(raw_field)

    payable_key = "invoice.payable"
    if payable_key not in values:
        missing_or_unreadable.append(payable_key)
    else:
        try:
            parsed_payable = parse_labeled_integer(values[payable_key])
        except (TypeError, ValueError):
            missing_or_unreadable.append(payable_key)
        else:
            if parsed_payable != invoice.get("summary", {}).get("payable"):
                disagreements.append(payable_key)
    diagnostics = tuple(
        [f"Missing or unreadable raw numeric fields: {', '.join(missing_or_unreadable)}"]
        if missing_or_unreadable
        else []
    ) + tuple(
        [f"Raw numeric values disagree with Canonical fields: {', '.join(disagreements)}"]
        if disagreements
        else []
    )
    return (
        not missing_or_unreadable,
        not disagreements and not missing_or_unreadable,
        bool(disagreements),
        diagnostics,
    )


def _digit_coverage(
    observation: LayoutObservation,
    thresholds: VerdictThresholds,
) -> tuple[bool, dict[str, int]]:
    numeric_text = "".join(
        text
        for field_name, text in observation.field_values
        if field_name == "invoice.payable"
        or field_name.endswith(".quantity")
        or field_name.endswith(".total")
    )
    counts = {digit: numeric_text.count(digit) for digit in thresholds.kit_required_digits}
    return (
        all(count >= thresholds.min_kit_digit_occurrences for count in counts.values()),
        counts,
    )


def _required_component_scores(
    template_match: TemplateMatch,
    thresholds: VerdictThresholds,
) -> tuple[dict[str, float] | None, tuple[str, ...]]:
    try:
        scores = template_match.component_scores
        if not isinstance(scores, Mapping):
            return None, ("E-05 component_scores is not a mapping",)
        normalized = {str(key): float(value) for key, value in scores.items()}
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None, ("E-05 TemplateMatch component-score API is incompatible",)
    for name in thresholds.required_layout_components:
        if name not in normalized:
            return None, (f"E-05 component score {name!r} is missing",)
        if not math.isfinite(normalized[name]) or not 0 <= normalized[name] <= 1:
            return None, (f"E-05 component score {name!r} is invalid",)
    return normalized, ()


_CURRENCY_UNIT_REVIEW_DETAIL = (
    "Template-bank currency_unit is missing or unsupported; E-06 never guesses or converts amounts."
)


def _currency_unit_confirmed(template_bank: TemplateBank | None) -> bool:
    if template_bank is None:
        return False
    currency_unit = getattr(template_bank, "currency_unit", None)
    return type(currency_unit) is str and currency_unit in ("rial", "toman")


def _schema_validation(invoice: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    try:
        valid, errors = validate_canonical_invoice(dict(invoice))
    except Exception as exc:  # Fail closed if the validator itself cannot run.
        return False, (f"Canonical validator raised {type(exc).__name__}",)
    return bool(valid), tuple(str(error) for error in errors)


def evaluate_verdict(
    invoice: Mapping[str, Any] | None,
    template_bank: TemplateBank | None,
    observation: LayoutObservation | None,
    extraction_confidence: float | None,
    *,
    processed_invoice_count: int = 0,
    template_bank_locked: bool = False,
    d14_agreement_signed: bool = False,
    missing_fields: Sequence[str] = (),
    require_kit_digit_coverage: bool | None = None,
    manual_override: ManualOverride | None = None,
    thresholds: VerdictThresholds = DEFAULT_THRESHOLDS,
) -> VerdictResult:
    """Evaluate one invoice without mutating inputs or the E-05 bank.

    ``processed_invoice_count`` is the number of onboarding invoices reviewed
    before the current candidate. The first N candidates are always REVIEW.
    Explicit ``missing_fields`` routes an incomplete extraction to REVIEW before
    Canonical validation; a complete but contract-invalid object is rejected.
    """
    if not isinstance(thresholds, VerdictThresholds):
        raise TypeError("thresholds must be VerdictThresholds")
    currency_unit_confirmed = _currency_unit_confirmed(template_bank)
    if type(processed_invoice_count) is not int or processed_invoice_count < 0:
        reasons = [ReasonCode.ONBOARDING_WARMUP]
        details = ["processed_invoice_count must be a non-negative integer"]
        if template_bank is not None and not currency_unit_confirmed:
            reasons.append(ReasonCode.CURRENCY_UNIT_UNCONFIRMED)
            details.append(_CURRENCY_UNIT_REVIEW_DETAIL)
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                reasons,
                details=details,
            ),
            manual_override,
            required_fields=(),
        )

    if missing_fields or invoice is None:
        missing = tuple(sorted({str(field) for field in missing_fields if str(field)}))
        reasons = [ReasonCode.PARTIAL_MATCH]
        details = [
            f"Missing fields: {', '.join(missing)}" if missing else "Invoice candidate is absent"
        ]
        if template_bank is None or observation is None:
            reasons.append(ReasonCode.NEW_LAYOUT)
        if template_bank is not None and not currency_unit_confirmed:
            reasons.append(ReasonCode.CURRENCY_UNIT_UNCONFIRMED)
            details.append(_CURRENCY_UNIT_REVIEW_DETAIL)
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                reasons,
                details=details,
            ),
            manual_override,
            required_fields=(),
        )

    if not isinstance(invoice, Mapping):
        return _apply_manual_override(
            _result(Verdict.REJECT, (ReasonCode.SCHEMA_INVALID,), details=("Invoice is not a JSON object",)),
            manual_override,
            required_fields=(),
        )

    schema_valid, schema_errors = _schema_validation(invoice)
    if not schema_valid:
        return _apply_manual_override(
            _result(
                Verdict.REJECT,
                (ReasonCode.SCHEMA_INVALID,),
                details=schema_errors,
            ),
            manual_override,
            required_fields=required_owner_verification_fields(invoice),
        )

    positive_reasons: list[ReasonCode] = [ReasonCode.STRUCTURE_VALID]
    if invoice.get("state") != "EXTRACTED":
        positive_reasons.append(ReasonCode.CANONICAL_STATE_NOT_READY)
    if not _numeric_internal_consistency(invoice):
        return _apply_manual_override(
            _result(
                Verdict.REJECT,
                (*positive_reasons, ReasonCode.NUMS_INCONSISTENT),
                details=("Canonical line totals, unit prices, subtotal, and payable do not reconcile",),
            ),
            manual_override,
            required_fields=required_owner_verification_fields(invoice),
        )
    positive_reasons.append(ReasonCode.NUMS_CONSISTENT)

    if template_bank is None or observation is None:
        reasons = [*positive_reasons, ReasonCode.NEW_LAYOUT]
        details = ["No E-05 template bank or layout observation is available"]
        if template_bank is not None and not currency_unit_confirmed:
            reasons.append(ReasonCode.CURRENCY_UNIT_UNCONFIRMED)
            details.append(_CURRENCY_UNIT_REVIEW_DETAIL)
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                reasons,
                details=details,
            ),
            manual_override,
            required_fields=required_owner_verification_fields(invoice),
        )

    if not currency_unit_confirmed:
        positive_reasons.append(ReasonCode.CURRENCY_UNIT_UNCONFIRMED)

    try:
        template_match = match_observation(template_bank, observation)
        if not isinstance(template_match, TemplateMatch):
            raise TypeError("E-05 match_observation returned an unexpected type")
        if len(template_bank.templates) > 1:
            ranked = score_bank(
                template_bank.templates,
                observation,
                threshold=template_bank.confidence_threshold,
            )
            if not ranked or any(not isinstance(match, TemplateMatch) for match in ranked):
                raise TypeError("E-05 score_bank returned an unexpected shape")
        else:
            ranked = (template_match,)
    except (AttributeError, TypeError, ValueError) as exc:
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                (*positive_reasons, ReasonCode.NEW_LAYOUT),
                details=(f"E-05 API/layout result unavailable: {type(exc).__name__}",),
            ),
            manual_override,
            required_fields=required_owner_verification_fields(invoice),
        )

    try:
        template_score = float(template_match.confidence_score)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                (*positive_reasons, ReasonCode.NEW_LAYOUT),
                details=("E-05 TemplateMatch confidence_score is unavailable",),
                template_match=template_match,
            ),
            manual_override,
            required_fields=required_owner_verification_fields(invoice),
        )
    if not math.isfinite(template_score) or not 0 <= template_score <= 1:
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                (*positive_reasons, ReasonCode.NEW_LAYOUT),
                details=("E-05 TemplateMatch confidence_score is outside [0, 1]",),
                template_match=template_match,
            ),
            manual_override,
            required_fields=required_owner_verification_fields(invoice),
        )

    component_scores, component_errors = _required_component_scores(template_match, thresholds)
    if component_scores is None:
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                (*positive_reasons, ReasonCode.NEW_LAYOUT),
                confidence_score=template_score,
                template_match=template_match,
                details=component_errors,
            ),
            manual_override,
            required_fields=required_owner_verification_fields(invoice),
        )

    raw_complete, raw_agrees, raw_has_disagreement, raw_diagnostics = _raw_numeric_comparison(
        invoice, observation
    )
    if raw_has_disagreement:
        return _apply_manual_override(
            _result(
                Verdict.REJECT,
                (*positive_reasons, ReasonCode.NUMS_INCONSISTENT),
                confidence_score=template_score,
                template_match=template_match,
                details=raw_diagnostics,
            ),
            manual_override,
            required_fields=required_owner_verification_fields(invoice),
        )
    if not raw_complete or not raw_agrees:
        positive_reasons.append(ReasonCode.PARTIAL_MATCH)
    else:
        positive_reasons.append(ReasonCode.NUMS_CONSISTENT)

    unmodeled_adjustments = _has_unmodeled_adjustments(invoice)
    if unmodeled_adjustments:
        positive_reasons.append(ReasonCode.ACCOUNTING_ADJUSTMENT_UNSUPPORTED)

    extraction_score: float | None
    if extraction_confidence is None:
        extraction_score = None
    else:
        try:
            extraction_score = float(extraction_confidence)
        except (TypeError, ValueError, OverflowError):
            extraction_score = None
        if extraction_score is not None and (
            not math.isfinite(extraction_score) or not 0 <= extraction_score <= 1
        ):
            extraction_score = None

    layout_score = min(component_scores[name] for name in thresholds.required_layout_components)
    confidence_signals = [template_score, layout_score]
    if extraction_score is not None:
        confidence_signals.append(extraction_score)
    effective_confidence = min(confidence_signals)
    required_fields = required_owner_verification_fields(invoice)

    # Collect all applicable non-confidence gates before returning a low-score
    # REVIEW so the caller sees the full onboarding state, not only one symptom.
    if len(ranked) > 1:
        top_score = float(ranked[0].confidence_score)
        second_score = float(ranked[1].confidence_score)
        if top_score - second_score < thresholds.template_ambiguity_margin:
            positive_reasons.append(ReasonCode.MULTI_TEMPLATE_AMBIGUOUS)

    if observation.source_id in template_match.source_invoice_ids:
        positive_reasons.append(ReasonCode.SELF_MATCH_RESUBSTITUTION)
        self_match_detail = "Observation is one of the bank's training sources; resubstitution cannot qualify onboarding acceptance"
    else:
        self_match_detail = ""

    coverage_required = (
        processed_invoice_count < thresholds.onboarding_invoice_count
        if require_kit_digit_coverage is None
        else require_kit_digit_coverage
    )
    if coverage_required:
        coverage_passed, digit_counts = _digit_coverage(observation, thresholds)
        positive_reasons.append(
            ReasonCode.DIGIT_COVERAGE_VALID
            if coverage_passed
            else ReasonCode.DIGIT_COVERAGE_INSUFFICIENT
        )
    else:
        coverage_passed = True
        digit_counts = {}

    if _has_unresolved_required_data(invoice):
        positive_reasons.append(ReasonCode.ATTENTION_REQUIRED)
    if processed_invoice_count < thresholds.onboarding_invoice_count:
        positive_reasons.append(ReasonCode.ONBOARDING_WARMUP)
    else:
        positive_reasons.append(ReasonCode.ONBOARDING_COMPLETE)
    positive_reasons.append(
        ReasonCode.TEMPLATE_BANK_LOCKED
        if template_bank_locked
        else ReasonCode.TEMPLATE_BANK_UNLOCKED
    )
    positive_reasons.append(
        ReasonCode.D14_AGREEMENT_SIGNED
        if d14_agreement_signed is True
        else ReasonCode.D14_AGREEMENT_REQUIRED
    )
    if template_score >= thresholds.accept_confidence:
        positive_reasons.append(ReasonCode.TEMPLATE_MATCH_HIGH)
    if extraction_score is not None and extraction_score >= thresholds.accept_confidence:
        positive_reasons.append(ReasonCode.EXTRACTION_CONFIDENCE_HIGH)
    if layout_score >= thresholds.accept_confidence:
        positive_reasons.append(ReasonCode.LAYOUT_SIMILARITY_HIGH)
    if not bool(template_match.matched):
        positive_reasons.append(ReasonCode.PARTIAL_MATCH)

    if template_score < thresholds.review_confidence or layout_score < thresholds.review_confidence:
        return _apply_manual_override(
            _result(
                Verdict.REJECT,
                (*positive_reasons, ReasonCode.NO_MATCH),
                confidence_score=effective_confidence,
                template_match=template_match,
                details=("E-05 match or required layout component is below the 0.80 reject threshold",),
            ),
            manual_override,
            required_fields=required_fields,
        )
    if extraction_score is not None and extraction_score < thresholds.review_confidence:
        return _apply_manual_override(
            _result(
                Verdict.REJECT,
                (*positive_reasons, ReasonCode.NO_MATCH),
                confidence_score=effective_confidence,
                template_match=template_match,
                details=("Extraction confidence is below the 0.80 reject threshold",),
            ),
            manual_override,
            required_fields=required_fields,
        )
    if effective_confidence < thresholds.accept_confidence:
        code = ReasonCode.LOW_CONFIDENCE
        review_details = ["Effective confidence is below the 0.95 acceptance-eligibility threshold"]
        if ReasonCode.CURRENCY_UNIT_UNCONFIRMED in positive_reasons:
            review_details.append(_CURRENCY_UNIT_REVIEW_DETAIL)
        if self_match_detail:
            review_details.append(self_match_detail)
        if coverage_required and not coverage_passed:
            review_details.append(f"Kit digit counts: {digit_counts}")
        if unmodeled_adjustments:
            review_details.append("Non-zero accounting adjustments are not interpreted by E-06")
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                (*positive_reasons, code),
                confidence_score=effective_confidence,
                template_match=template_match,
                details=review_details,
            ),
            manual_override,
            required_fields=required_fields,
        )
    if extraction_score is None:
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                (*positive_reasons, ReasonCode.LOW_CONFIDENCE),
                confidence_score=effective_confidence,
                template_match=template_match,
                details=("Extraction confidence is missing or invalid",),
            ),
            manual_override,
            required_fields=required_fields,
        )
    if not bool(template_match.matched):
        return _apply_manual_override(
            _result(
                Verdict.REVIEW,
                (*positive_reasons, ReasonCode.PARTIAL_MATCH),
                confidence_score=effective_confidence,
                template_match=template_match,
                details=("E-05 marked the candidate unmatched despite its aggregate score",),
            ),
            manual_override,
            required_fields=required_fields,
        )

    blockers = {
        ReasonCode.PARTIAL_MATCH,
        ReasonCode.ACCOUNTING_ADJUSTMENT_UNSUPPORTED,
        ReasonCode.CURRENCY_UNIT_UNCONFIRMED,
        ReasonCode.SELF_MATCH_RESUBSTITUTION,
        ReasonCode.MULTI_TEMPLATE_AMBIGUOUS,
        ReasonCode.ATTENTION_REQUIRED,
        ReasonCode.CANONICAL_STATE_NOT_READY,
        ReasonCode.DIGIT_COVERAGE_INSUFFICIENT,
        ReasonCode.ONBOARDING_WARMUP,
        ReasonCode.TEMPLATE_BANK_UNLOCKED,
        ReasonCode.D14_AGREEMENT_REQUIRED,
    }
    if blockers.intersection(positive_reasons):
        review_result = _result(
            Verdict.REVIEW,
            positive_reasons,
            confidence_score=effective_confidence,
            template_match=template_match,
            details=tuple(
                item
                for item in (
                    _CURRENCY_UNIT_REVIEW_DETAIL
                    if ReasonCode.CURRENCY_UNIT_UNCONFIRMED in positive_reasons
                    else "",
                    self_match_detail,
                    f"Kit digit counts: {digit_counts}" if coverage_required and not coverage_passed else "",
                    "Non-zero accounting adjustments are not interpreted by E-06" if unmodeled_adjustments else "",
                )
                if item
            ),
        )
        return _apply_manual_override(
            review_result,
            manual_override,
            required_fields=required_fields,
        )

    positive_reasons.append(ReasonCode.OWNER_VERIFICATION_REQUIRED)
    eligible = _result(
        Verdict.REVIEW,
        positive_reasons,
        confidence_score=effective_confidence,
        template_match=template_match,
        details=(self_match_detail,) if self_match_detail else (),
        owner_acceptance_eligible=True,
    )
    return _apply_manual_override(
        eligible,
        manual_override,
        required_fields=required_fields,
    )
