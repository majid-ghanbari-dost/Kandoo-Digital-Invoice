from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from e05_template_bank import (
    LayoutObservation,
    TemplateBank,
    TemplateMatch,
    build_template_bank,
    load_training_observations,
)
from e06_onboarding_verdict import (
    ManualOverride,
    ReasonCode,
    Verdict,
    evaluate_verdict,
    required_owner_verification_fields,
)
from image_extraction_adapter.canonical_invoice import validate_canonical_invoice


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REAL_FIXTURE_DIR = REPOSITORY_ROOT / "tests" / "fixtures" / "real"
CANONICAL_DIR = REAL_FIXTURE_DIR / "canonical"
LABELS_PATH = REAL_FIXTURE_DIR / "labels.json"
ONBOARDING_DIR = REAL_FIXTURE_DIR / "onboarding"
SOURCE_IDS = ("29", "31", "32", "33")


@pytest.fixture(scope="module")
def bank() -> TemplateBank:
    return build_template_bank(CANONICAL_DIR, LABELS_PATH)


@pytest.fixture(scope="module")
def observations() -> tuple[LayoutObservation, ...]:
    return load_training_observations(CANONICAL_DIR, LABELS_PATH)


def load_canonical(source_id: str) -> dict:
    return json.loads(
        (CANONICAL_DIR / f"canonical-{source_id}.json").read_text(encoding="utf-8")
    )


def test_e05_api_is_importable_and_returns_expected_match_shape(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    from e05_template_bank import TemplateMatch, match_observation

    match = match_observation(bank, observations[0])
    assert isinstance(match, TemplateMatch)
    assert isinstance(match.confidence_score, float)
    assert isinstance(match.component_scores, dict)
    assert {"columns", "row_rhythm", "table_anchor", "payable_anchor"} <= set(
        match.component_scores
    )


def test_all_four_label_derived_invoices_are_matched_but_reviewed_during_warmup(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    assert tuple(observation.source_id for observation in observations) == SOURCE_IDS
    for index, observation in enumerate(observations):
        invoice = load_canonical(observation.source_id)
        result = evaluate_verdict(
            invoice,
            bank,
            observation,
            0.99,
            processed_invoice_count=index,
            template_bank_locked=False,
            d14_agreement_signed=False,
            require_kit_digit_coverage=False,  # these are not the E-03 kit documents
        )
        assert result.template_match is not None
        assert result.template_match.matched is True
        assert result.verdict is Verdict.REVIEW
        assert ReasonCode.ONBOARDING_WARMUP in result.reason_codes
        assert ReasonCode.SELF_MATCH_RESUBSTITUTION in result.reason_codes
        assert ReasonCode.DIGIT_COVERAGE_INSUFFICIENT not in result.reason_codes
        assert result.template_match.confidence_score >= 0.80
        assert result.verdict is not Verdict.ACCEPT
        if observation.source_id == "33":
            assert invoice["state"] == "DRAFT"
            assert result.confidence_score is not None
            assert 0.80 <= result.confidence_score < 0.95
            assert ReasonCode.LOW_CONFIDENCE in result.reason_codes
            assert ReasonCode.CANONICAL_STATE_NOT_READY in result.reason_codes


def test_kit_digit_coverage_is_scoped_and_fails_closed_when_required(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invoice = load_canonical("29")
    result = evaluate_verdict(
        invoice,
        bank,
        observations[0],
        0.99,
        processed_invoice_count=0,
        template_bank_locked=False,
        d14_agreement_signed=False,
        require_kit_digit_coverage=True,
    )
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.DIGIT_COVERAGE_INSUFFICIENT in result.reason_codes
    assert any("Kit digit counts" in detail for detail in result.details)


def test_bad_invoice_fixture_is_rejected_for_numeric_inconsistency(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    bad_invoice = json.loads((ONBOARDING_DIR / "bad-invoice.json").read_text(encoding="utf-8"))
    provenance = json.loads(
        (ONBOARDING_DIR / "bad-invoice.provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["synthetic"] is True
    assert provenance["test_only"] is True
    assert provenance["production_data"] is False
    valid, errors = validate_canonical_invoice(bad_invoice)
    assert valid, errors  # structurally valid, intentionally arithmetically wrong

    result = evaluate_verdict(
        bad_invoice,
        bank,
        observations[0],
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
    )
    assert result.verdict is Verdict.REJECT
    assert ReasonCode.NUMS_INCONSISTENT in result.reason_codes


def test_nonzero_unmodeled_accounting_adjustment_remains_review(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invoice = load_canonical("29")
    invoice["summary"]["extra_amounts"]["unmodeled_surcharge"] = 1
    invoice["provenance"]["fields"]["summary"]["extra_amounts"][
        "unmodeled_surcharge"
    ] = "captured"
    valid, errors = validate_canonical_invoice(invoice)
    assert valid, errors

    result = evaluate_verdict(
        invoice,
        bank,
        observations[0],
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
    )
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.ACCOUNTING_ADJUSTMENT_UNSUPPORTED in result.reason_codes
    assert ReasonCode.NUMS_INCONSISTENT not in result.reason_codes


def test_partial_invoice_fixture_returns_review(
    bank: TemplateBank,
) -> None:
    partial = json.loads((ONBOARDING_DIR / "partial-invoice.json").read_text(encoding="utf-8"))
    result = evaluate_verdict(
        partial["invoice_fragment"],
        bank,
        None,
        None,
        processed_invoice_count=0,
        missing_fields=partial["missing_fields"],
    )
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.PARTIAL_MATCH in result.reason_codes


def test_invalid_complete_canonical_object_is_rejected(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invalid = load_canonical("29")
    invalid["unexpected"] = "not allowed by Canonical Invoice v0"
    result = evaluate_verdict(
        invalid,
        bank,
        observations[0],
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
    )
    assert result.verdict is Verdict.REJECT
    assert ReasonCode.SCHEMA_INVALID in result.reason_codes


def test_compensating_raw_numeric_errors_are_rejected_even_when_sum_matches(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invoice = load_canonical("29")
    invoice["line_items"][0]["line_total"] += 1000
    invoice["line_items"][0]["unit_price"] += 1000
    invoice["line_items"][1]["line_total"] -= 1000
    invoice["line_items"][1]["unit_price"] -= 1000
    assert sum(item["line_total"] for item in invoice["line_items"]) == invoice["summary"]["payable"]
    valid, errors = validate_canonical_invoice(invoice)
    assert valid, errors

    result = evaluate_verdict(
        invoice,
        bank,
        observations[0],
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
    )
    assert result.verdict is Verdict.REJECT
    assert ReasonCode.NUMS_INCONSISTENT in result.reason_codes


def test_first_invoice_without_a_template_is_always_review() -> None:
    result = evaluate_verdict(
        load_canonical("29"),
        None,
        None,
        0.99,
        processed_invoice_count=0,
    )
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.NEW_LAYOUT in result.reason_codes


def test_below_080_match_cannot_be_accepted(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invoice = load_canonical("29")
    poor_layout = replace(
        observations[0],
        source_id="new-low-score-invoice",
        column_boundaries=(116.0, 200.0, 350.0, 470.0, 527.0),
    )
    owner = ManualOverride(
        target=Verdict.ACCEPT,
        actor_id="owner-test-id",
        actor_role="store_owner",
        audit_id="audit-low-score",
        reason="A request must not bypass the low-score gate.",
        occurred_at="2026-10-23T10:00:00Z",
        verified_fields=required_owner_verification_fields(invoice),
    )
    result = evaluate_verdict(
        invoice,
        bank,
        poor_layout,
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
        manual_override=owner,
    )
    assert result.confidence_score is not None and result.confidence_score < 0.80
    assert result.verdict is Verdict.REJECT
    assert ReasonCode.NO_MATCH in result.reason_codes
    assert ReasonCode.MANUAL_OVERRIDE_BLOCKED in result.reason_codes


def test_exact_080_boundary_is_review_not_reject(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    match = TemplateMatch(
        template_id=bank.templates[0].template_id,
        confidence_score=0.80,
        matched=True,
        source_invoice_ids=(),
        components=tuple(
            (name, 0.80)
            for name in ("columns", "row_rhythm", "table_anchor", "payable_anchor")
        ),
        reasons=("test threshold boundary",),
        numeric_evidence_present=True,
    )
    monkeypatch.setattr(
        "e06_onboarding_verdict.verdict.match_observation",
        lambda _bank, _observation: match,
    )
    result = evaluate_verdict(
        load_canonical("29"),
        bank,
        observations[0],
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
    )
    assert result.confidence_score == pytest.approx(0.80)
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.LOW_CONFIDENCE in result.reason_codes
    assert ReasonCode.NO_MATCH not in result.reason_codes


def test_exact_095_boundary_advances_to_later_gates(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice, observation, _owner = make_post_onboarding_candidate(bank, observations)
    match = TemplateMatch(
        template_id=bank.templates[0].template_id,
        confidence_score=0.95,
        matched=True,
        source_invoice_ids=(),
        components=tuple(
            (name, 0.95)
            for name in ("columns", "row_rhythm", "table_anchor", "payable_anchor")
        ),
        reasons=("test threshold boundary",),
        numeric_evidence_present=True,
    )
    monkeypatch.setattr(
        "e06_onboarding_verdict.verdict.match_observation",
        lambda _bank, _observation: match,
    )
    result = evaluate_verdict(
        invoice,
        bank,
        observation,
        0.95,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
    )
    assert result.confidence_score == pytest.approx(0.95)
    assert result.verdict is Verdict.REVIEW
    assert result.owner_acceptance_eligible is True
    assert ReasonCode.OWNER_VERIFICATION_REQUIRED in result.reason_codes
    assert ReasonCode.LOW_CONFIDENCE not in result.reason_codes
    assert ReasonCode.NO_MATCH not in result.reason_codes


def make_post_onboarding_candidate(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> tuple[dict, LayoutObservation, ManualOverride]:
    """Build in-memory synthetic evidence to exercise the fully gated ACCEPT path."""
    invoice = copy.deepcopy(load_canonical("29"))
    invoice["invoice_id"] = "e06-test-new-invoice"
    invoice["display_number"] = "E06-TEST-NEW"
    invoice["operation_id"] = "e06-test-operation"
    invoice["device_id"] = "e06-test-device"
    invoice["store_id"] = "e06-test-store"
    invoice["customer"]["phone"] = "+15550001111"
    invoice["attention_cells"] = []
    invoice["provenance"]["image_sha256"] = None
    invoice["provenance"]["fields"]["customer"]["phone"] = "captured"

    for index, item in enumerate(invoice["line_items"]):
        item["product_name"] = f"Verified test item {index + 1}"
        item["quantity"] = 26
        item["unit_price"] = 10101
        item["line_total"] = 262626
        invoice["provenance"]["fields"]["line_items"][index].update(
            {
                "product_name": "captured",
                "quantity": "captured",
                "unit_price": "derived",
                "line_total": "captured",
            }
        )
    invoice["summary"]["subtotal"] = 1_050_504
    invoice["summary"]["payable"] = 1_050_504
    invoice["provenance"]["fields"]["summary"]["subtotal"] = "derived"
    invoice["provenance"]["fields"]["summary"]["payable"] = "captured"

    raw_values = {}
    for index in range(len(invoice["line_items"])):
        raw_values[f"line.{index}.quantity"] = "۲۶"
        raw_values[f"line.{index}.total"] = "۲۶۲,۶۲۶"
    raw_values["invoice.payable"] = "۱,۰۵۰,۵۰۴"
    observation = replace(
        observations[0],
        source_id="e06-test-new-invoice-layout",
        field_values=raw_values,
    )

    valid, errors = validate_canonical_invoice(invoice)
    assert valid, errors
    owner = ManualOverride(
        target=Verdict.ACCEPT,
        actor_id="owner-test-id",
        actor_role="store_owner",
        audit_id="audit-e06-accept-test",
        reason="Verified every visible field against the test scan.",
        occurred_at="2026-10-23T10:00:00Z",
        verified_fields=required_owner_verification_fields(invoice),
    )
    return invoice, observation, owner


def test_accept_requires_all_gates_and_audited_owner_verification(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invoice, observation, owner = make_post_onboarding_candidate(bank, observations)
    required_fields = set(required_owner_verification_fields(invoice))
    assert "summary.subtotal" in required_fields
    assert "summary.payable" in required_fields
    assert "line_items[0].unit_price" in required_fields
    common = {
        "processed_invoice_count": 4,
        "template_bank_locked": True,
        "d14_agreement_signed": True,
        "require_kit_digit_coverage": True,
    }

    without_owner = evaluate_verdict(invoice, bank, observation, 0.99, **common)
    assert without_owner.verdict is Verdict.REVIEW
    assert ReasonCode.OWNER_VERIFICATION_REQUIRED in without_owner.reason_codes

    accepted = evaluate_verdict(
        invoice,
        bank,
        observation,
        0.99,
        manual_override=owner,
        **common,
    )
    assert accepted.verdict is Verdict.ACCEPT
    assert {
        ReasonCode.TEMPLATE_MATCH_HIGH,
        ReasonCode.STRUCTURE_VALID,
        ReasonCode.NUMS_CONSISTENT,
        ReasonCode.OWNER_VERIFICATION_AUDITED,
    } <= set(accepted.reason_codes)
    assert accepted.audit_record is not None
    assert accepted.audit_record["audit_id"] == owner.audit_id
    serialized = accepted.to_dict()
    assert serialized["verdict"] == "ACCEPT"
    assert serialized["template_match"] is not None
    assert set(serialized["template_match"]) == {
        "template_id",
        "confidence_score",
        "matched",
        "source_invoice_ids",
        "components",
        "reasons",
        "numeric_evidence_present",
    }
    assert serialized["template_match"]["matched"] is True


def test_owner_cannot_override_the_first_four_review_only_gate(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invoice, observation, owner = make_post_onboarding_candidate(bank, observations)
    result = evaluate_verdict(
        invoice,
        bank,
        observation,
        0.99,
        processed_invoice_count=0,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=True,
        manual_override=owner,
    )
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.ONBOARDING_WARMUP in result.reason_codes
    assert ReasonCode.MANUAL_OVERRIDE_BLOCKED in result.reason_codes


def test_unlocked_bank_and_missing_d14_keep_candidate_in_review(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invoice, observation, _owner = make_post_onboarding_candidate(bank, observations)
    unlocked = evaluate_verdict(
        invoice,
        bank,
        observation,
        0.99,
        processed_invoice_count=4,
        template_bank_locked=False,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
    )
    assert unlocked.verdict is Verdict.REVIEW
    assert ReasonCode.TEMPLATE_BANK_UNLOCKED in unlocked.reason_codes

    unsigned = evaluate_verdict(
        invoice,
        bank,
        observation,
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=False,
        require_kit_digit_coverage=False,
    )
    assert unsigned.verdict is Verdict.REVIEW
    assert ReasonCode.D14_AGREEMENT_REQUIRED in unsigned.reason_codes


def test_multiple_near_equal_templates_return_review(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    duplicate = replace(bank.templates[0], template_id="e05-layout-duplicate")
    mixed_bank = replace(bank, templates=(bank.templates[0], duplicate))
    invoice = load_canonical("29")
    observation = replace(observations[0], source_id="new-mixed-template-invoice")
    result = evaluate_verdict(
        invoice,
        mixed_bank,
        observation,
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
    )
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.MULTI_TEMPLATE_AMBIGUOUS in result.reason_codes


def test_synthetic_context_and_attention_cells_block_acceptance(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    invoice = load_canonical("29")
    result = evaluate_verdict(
        invoice,
        bank,
        replace(observations[0], source_id="new-attention-invoice"),
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
    )
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.ATTENTION_REQUIRED in result.reason_codes


def test_manual_accept_override_cannot_promote_a_rejected_bad_invoice(
    bank: TemplateBank,
    observations: tuple[LayoutObservation, ...],
) -> None:
    bad_invoice = json.loads((ONBOARDING_DIR / "bad-invoice.json").read_text(encoding="utf-8"))
    owner = ManualOverride(
        target=Verdict.ACCEPT,
        actor_id="owner-test-id",
        actor_role="store_owner",
        audit_id="audit-hard-reject",
        reason="Attempted override of an arithmetic failure.",
        occurred_at="2026-10-23T10:00:00Z",
        verified_fields=required_owner_verification_fields(bad_invoice),
    )
    result = evaluate_verdict(
        bad_invoice,
        bank,
        observations[0],
        0.99,
        processed_invoice_count=4,
        template_bank_locked=True,
        d14_agreement_signed=True,
        require_kit_digit_coverage=False,
        manual_override=owner,
    )
    assert result.verdict is Verdict.REJECT
    assert ReasonCode.NUMS_INCONSISTENT in result.reason_codes
    assert ReasonCode.MANUAL_OVERRIDE_BLOCKED in result.reason_codes
