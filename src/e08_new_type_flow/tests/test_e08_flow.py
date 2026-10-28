from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from e05_template_bank import LayoutObservation, build_template_bank, load_training_observations
from e05_template_bank.confidence import score_bank
from e06_onboarding_verdict import (
    ReasonCode,
    Verdict,
    required_owner_verification_fields,
)
from image_extraction_adapter.canonical_invoice import validate_canonical_invoice

from e08_new_type_flow import (
    AuditEventType,
    AuditTrail,
    CandidateRegistry,
    CandidateState,
    CandidateTransitionError,
    DetectionKind,
    MiniOnboardingState,
    TemplateCandidate,
    accept_candidate_and_start_mini_onboarding,
    append_candidate_transition,
    append_mini_onboarding_lock,
    append_mini_onboarding_review,
    detect_invoice_type,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "real" / "new_type"
CANONICAL_DIR = ROOT / "tests" / "fixtures" / "real" / "canonical"
LABELS_PATH = ROOT / "tests" / "fixtures" / "real" / "labels.json"
NOW = "2026-10-23T12:00:00Z"


@pytest.fixture(scope="module")
def e05_context():
    bank = build_template_bank(CANONICAL_DIR, LABELS_PATH, currency_unit="rial")
    observations = load_training_observations(CANONICAL_DIR, LABELS_PATH)
    existing_layout = next(observation for observation in observations if observation.source_id == "29")
    new_meta = json.loads((FIXTURE_DIR / "new-type-invoice.meta.json").read_text(encoding="utf-8"))
    new_observation = LayoutObservation.from_dict(new_meta["layout_observation"])
    return bank, existing_layout, new_observation


def _invoice(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _detect(
    invoice: dict,
    observation: LayoutObservation,
    bank,
    *,
    registry: CandidateRegistry | None = None,
    trail: AuditTrail | None = None,
    detected_at: str = NOW,
    accepted_invoice_count: int = 4,
    template_bank_locked: bool = True,
    d14_agreement_signed: bool = True,
):
    return detect_invoice_type(
        invoice,
        bank,
        observation,
        0.99,
        store_id=invoice["store_id"],
        accepted_invoice_count=accepted_invoice_count,
        template_bank_locked=template_bank_locked,
        d14_agreement_signed=d14_agreement_signed,
        detected_at=detected_at,
        audit_trail=trail,
        candidate_registry=registry,
    )


def test_synthetic_fixtures_have_test_only_provenance():
    for stem in ("new-type-invoice", "corrupted-invoice"):
        metadata = json.loads((FIXTURE_DIR / f"{stem}.meta.json").read_text(encoding="utf-8"))
        invoice = _invoice(stem)
        assert metadata["synthetic"] is True
        assert metadata["test_only"] is True
        assert metadata["production_data"] is False
        assert metadata["canonical_file"] == f"{stem}.json"
        assert validate_canonical_invoice(invoice) == (True, [])


def test_valid_new_type_is_reviewed_proposed_audited_and_not_added_to_bank(e05_context):
    bank, _existing_layout, observation = e05_context
    invoice = _invoice("new-type-invoice")
    registry = CandidateRegistry()
    original_template_ids = tuple(template.template_id for template in bank.templates)

    result = _detect(invoice, observation, bank, registry=registry, trail=AuditTrail())

    assert result.kind is DetectionKind.NEW_TYPE
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.NEW_LAYOUT in result.reason_codes
    assert ReasonCode.NUMS_CONSISTENT in result.reason_codes
    assert ReasonCode.PARTIAL_MATCH not in result.reason_codes
    assert result.verdict_result.owner_acceptance_eligible is False
    assert result.candidate is not None
    assert result.candidate.state is CandidateState.PROPOSED
    assert result.candidate.source_invoice_ids == (invoice["invoice_id"],)
    assert registry.get(result.candidate.candidate_id) == result.candidate
    assert result.match_scores
    assert all(score < bank.confidence_threshold for _, score in result.match_scores)
    assert result.audit_trail.verify()
    assert len(result.audit_trail.entries) == 1
    event = result.audit_trail.entries[0]
    assert event.event_type is AuditEventType.NEW_TYPE_DETECTED
    assert event.invoice_id == invoice["invoice_id"]
    assert event.candidate_id == result.candidate.candidate_id
    assert event.verdict == Verdict.REVIEW.value
    assert tuple(name for name, _ in event.match_scores) == tuple(name for name, _ in result.match_scores)
    assert tuple(template.template_id for template in bank.templates) == original_template_ids


def test_corrupted_invoice_is_rejected_and_never_becomes_candidate(e05_context):
    bank, existing_layout, _new_observation = e05_context
    invoice = _invoice("corrupted-invoice")
    observation = replace(existing_layout, source_id="e08-corrupted-test-observation")
    registry = CandidateRegistry()

    result = _detect(invoice, observation, bank, registry=registry, trail=AuditTrail())

    assert result.kind is DetectionKind.CORRUPTED
    assert result.verdict is Verdict.REJECT
    assert ReasonCode.NUMS_INCONSISTENT in result.reason_codes
    assert result.candidate is None
    assert registry.candidates == ()
    assert len(result.audit_trail.entries) == 1
    event = result.audit_trail.entries[0]
    assert event.event_type is AuditEventType.CORRUPTED_INVOICE_DETECTED
    assert event.invoice_id == invoice["invoice_id"]
    assert event.verdict == Verdict.REJECT.value
    assert result.audit_trail.verify()


def test_e05_runtime_failure_fails_closed_to_review_without_candidate(e05_context, monkeypatch):
    bank, _existing_layout, observation = e05_context
    invoice = _invoice("new-type-invoice")
    registry = CandidateRegistry()

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("synthetic E-05 failure")

    monkeypatch.setattr("e08_new_type_flow.detector.score_bank", unavailable)
    result = _detect(invoice, observation, bank, registry=registry, trail=AuditTrail())

    assert result.kind is DetectionKind.INDETERMINATE
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.NEW_LAYOUT in result.reason_codes
    assert result.candidate is None
    assert registry.candidates == ()
    assert result.audit_trail.entries[0].event_type is AuditEventType.INDETERMINATE_DETECTION
    assert result.audit_trail.verify()


def test_e06_runtime_failure_fails_closed_to_review_without_candidate(e05_context, monkeypatch):
    bank, _existing_layout, observation = e05_context
    invoice = _invoice("new-type-invoice")
    registry = CandidateRegistry()

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("synthetic E-06 failure")

    monkeypatch.setattr("e08_new_type_flow.detector.evaluate_verdict", unavailable)
    result = _detect(invoice, observation, bank, registry=registry, trail=AuditTrail())

    assert result.kind is DetectionKind.INDETERMINATE
    assert result.verdict is Verdict.REVIEW
    assert ReasonCode.NEW_LAYOUT in result.reason_codes
    assert result.candidate is None
    assert registry.candidates == ()
    assert result.audit_trail.verify()


def test_candidate_gates_and_missing_numeric_evidence_fail_closed_to_review(e05_context):
    bank, _existing_layout, observation = e05_context
    invoice = _invoice("new-type-invoice")

    onboarding_result = _detect(
        invoice,
        observation,
        bank,
        accepted_invoice_count=3,
        trail=AuditTrail(),
    )
    assert onboarding_result.kind is DetectionKind.ONBOARDING_IN_PROGRESS
    assert onboarding_result.verdict is Verdict.REVIEW
    assert ReasonCode.NEW_LAYOUT in onboarding_result.reason_codes
    assert onboarding_result.candidate is None

    d14_result = _detect(
        invoice,
        observation,
        bank,
        d14_agreement_signed=False,
        trail=AuditTrail(),
    )
    assert d14_result.kind is DetectionKind.INDETERMINATE
    assert d14_result.verdict is Verdict.REVIEW
    assert d14_result.candidate is None

    incomplete_observation = replace(
        observation,
        source_id="e08-incomplete-raw-evidence",
        field_values=tuple(
            (field_name, value)
            for field_name, value in observation.field_values
            if field_name != "line.1.total"
        ),
    )
    incomplete_result = _detect(
        invoice,
        incomplete_observation,
        bank,
        trail=AuditTrail(),
    )
    assert incomplete_result.kind is DetectionKind.INDETERMINATE
    assert incomplete_result.verdict is Verdict.REVIEW
    assert incomplete_result.candidate is None


def test_different_signature_waits_while_one_candidate_is_unresolved(e05_context):
    bank, _existing_layout, observation = e05_context
    registry = CandidateRegistry()
    first_invoice = _invoice("new-type-invoice")
    first = _detect(first_invoice, observation, bank, registry=registry, trail=AuditTrail())

    second_invoice = copy.deepcopy(first_invoice)
    second_invoice["invoice_id"] = "e08-synthetic-second-layout-invoice"
    second_observation = replace(
        observation,
        source_id="e08-second-layout-signature",
        column_boundaries=(91, 320, 480, 900, 1120),
    )
    second = _detect(
        second_invoice,
        second_observation,
        bank,
        registry=registry,
        trail=first.audit_trail,
        detected_at="2026-10-23T12:05:00Z",
    )

    assert first.kind is DetectionKind.NEW_TYPE
    assert second.kind is DetectionKind.CANDIDATE_BLOCKED
    assert second.verdict is Verdict.REVIEW
    assert second.candidate is None
    assert len(registry.unresolved_for_store(first_invoice["store_id"])) == 1
    assert second.audit_trail.entries[-1].event_type is AuditEventType.NEW_TYPE_DETECTED
    assert second.audit_trail.entries[-1].invoice_id == second_invoice["invoice_id"]
    assert second.audit_trail.verify()


def test_three_distinct_unresolved_new_type_detections_escalate_in_24_hours(e05_context):
    bank, _existing_layout, observation = e05_context
    registry = CandidateRegistry()
    trail = AuditTrail()
    results = []

    for index, minute in enumerate((0, 7, 18), start=1):
        invoice = copy.deepcopy(_invoice("new-type-invoice"))
        invoice["invoice_id"] = f"e08-synthetic-repeat-{index}"
        result = _detect(
            invoice,
            observation,
            bank,
            registry=registry,
            trail=trail,
            detected_at=f"2026-10-23T12:{minute:02d}:00Z",
        )
        results.append(result)
        trail = result.audit_trail

    assert [result.support_escalation_required for result in results] == [False, False, True]
    assert len({event.invoice_id for event in trail.entries}) == 3
    assert len({event.candidate_id for event in trail.entries}) == 1
    assert trail.escalation_required("e05-synth-store", "2026-10-23T12:19:00Z")
    assert trail.verify()

    reviewed = append_candidate_transition(
        trail,
        store_id="e05-synth-store",
        candidate_id=results[-1].candidate.candidate_id,
        reviewer_id="synthetic-reviewer",
        occurred_at="2026-10-23T12:19:30Z",
        review_reason="Synthetic review is not a terminal resolution",
    )
    assert reviewed.escalation_required("e05-synth-store", "2026-10-23T12:19:45Z")
    resolved = append_candidate_transition(
        reviewed,
        store_id="e05-synth-store",
        candidate_id=results[-1].candidate.candidate_id,
        reviewer_id="synthetic-reviewer",
        occurred_at="2026-10-23T12:20:00Z",
        review_reason="Synthetic test resolution",
        decision="REJECT",
    )
    assert resolved.entries[-1].event_type is AuditEventType.CANDIDATE_REJECTED
    assert not resolved.escalation_required("e05-synth-store", "2026-10-23T12:21:00Z")
    assert resolved.verify()


def test_candidate_lifecycle_is_monotonic_and_separate_from_production_bank(e05_context):
    bank, _existing_layout, observation = e05_context
    invoice = _invoice("new-type-invoice")
    candidate = TemplateCandidate.propose(
        invoice["store_id"], invoice["invoice_id"], observation, NOW
    )
    registry = CandidateRegistry()
    stored, disposition = registry.propose_or_reuse(candidate)
    assert disposition == "created"
    assert stored == candidate

    repeated = TemplateCandidate.propose(
        invoice["store_id"], "e08-synthetic-second-source", observation, "2026-10-23T12:01:00Z"
    )
    reused, disposition = registry.propose_or_reuse(repeated)
    assert disposition == "reused"
    assert reused.candidate_id == candidate.candidate_id
    assert set(reused.source_invoice_ids) == {invoice["invoice_id"], "e08-synthetic-second-source"}

    with pytest.raises(CandidateTransitionError):
        candidate.accept("synthetic-reviewer", "2026-10-23T12:02:00Z", "skip review")

    reviewed = reused.mark_reviewed(
        "synthetic-reviewer", "2026-10-23T12:02:00Z", "Synthetic layout review"
    )
    registry.update(reviewed)
    accepted, mini = accept_candidate_and_start_mini_onboarding(
        reviewed,
        "synthetic-reviewer",
        "2026-10-23T12:03:00Z",
        "Owner confirmed the candidate layout",
    )
    registry.update(accepted)
    assert accepted.state is CandidateState.ACCEPTED
    assert mini.candidate_id == accepted.candidate_id
    assert mini.state is MiniOnboardingState.COLLECTING
    assert registry.unresolved_for_store(invoice["store_id"]) == ()
    assert tuple(template.template_id for template in bank.templates) == ("e05-layout-01",)

    terminal, disposition = registry.propose_or_reuse(repeated)
    assert disposition == "terminal"
    assert terminal.state is CandidateState.ACCEPTED


def test_candidate_reviews_and_mini_onboarding_require_four_review_verdicts(e05_context):
    bank, _existing_layout, observation = e05_context
    source = _invoice("new-type-invoice")
    proposed = TemplateCandidate.propose(source["store_id"], source["invoice_id"], observation, NOW)
    registry = CandidateRegistry()
    registry.propose_or_reuse(proposed)
    reviewed = proposed.mark_reviewed(
        "synthetic-reviewer", "2026-10-23T12:01:00Z", "Synthetic candidate review"
    )
    registry.update(reviewed)
    accepted, mini = accept_candidate_and_start_mini_onboarding(
        reviewed,
        "synthetic-reviewer",
        "2026-10-23T12:02:00Z",
        "Synthetic owner acceptance for test coverage",
    )
    registry.update(accepted)
    required_fields = required_owner_verification_fields(source)
    trail = AuditTrail()
    trail = append_candidate_transition(
        trail,
        store_id=source["store_id"],
        candidate_id=accepted.candidate_id,
        reviewer_id="synthetic-reviewer",
        occurred_at="2026-10-23T12:01:00Z",
        review_reason="Synthetic review recorded",
    )
    trail = append_candidate_transition(
        trail,
        store_id=source["store_id"],
        candidate_id=accepted.candidate_id,
        reviewer_id="synthetic-reviewer",
        occurred_at="2026-10-23T12:02:00Z",
        review_reason="Synthetic owner acceptance recorded",
        decision="ACCEPT",
    )

    for index in range(4):
        invoice = copy.deepcopy(source)
        invoice["invoice_id"] = f"e08-mini-synthetic-{index + 1}"
        invoice["display_number"] = f"E08-MINI-{index + 1}"
        invoice["operation_id"] = f"e08-mini-operation-{index + 1}"
        invoice["device_id"] = f"e08-mini-device-{index + 1}"
        invoice["public_token"] = f"RTA8MiniInvoiceToken_2026_{index + 1}"
        for transition in invoice["state_history"]:
            transition["operation_id"] = f"e08-mini-transition-{index + 1}"
            transition["device_id"] = f"e08-mini-device-{index + 1}"
        review_time = f"2026-10-23T12:{index + 3:02d}:00Z"
        detection = _detect(
            invoice,
            observation,
            bank,
            registry=registry,
            trail=trail,
            detected_at=review_time,
        )
        trail = detection.audit_trail
        verdict_result = detection.verdict_result
        assert detection.verdict is Verdict.REVIEW
        assert verdict_result.template_match is not None
        if index == 0:
            mismatched_invoice = copy.deepcopy(invoice)
            mismatched_invoice["invoice_id"] = "e08-mini-wrong-detection-invoice"
            with pytest.raises(ValueError, match="identify this invoice"):
                mini.record_reviewed_invoice(
                    mismatched_invoice,
                    detection,
                    reviewer_id="synthetic-reviewer",
                    reviewed_at=review_time,
                    verified_fields=required_fields,
                )
            hard_failure = replace(verdict_result, reason_codes=(ReasonCode.SCHEMA_INVALID,))
            failed_detection = replace(detection, verdict_result=hard_failure)
            with pytest.raises(ValueError, match="hard failures"):
                mini.record_reviewed_invoice(
                    invoice,
                    failed_detection,
                    reviewer_id="synthetic-reviewer",
                    reviewed_at="2026-10-23T12:03:00Z",
                    verified_fields=required_fields,
                )
        reviewer_id = f"synthetic-reviewer-{index + 1}"
        mini = mini.record_reviewed_invoice(
            invoice,
            detection,
            reviewer_id=reviewer_id,
            reviewed_at=review_time,
            verified_fields=required_fields,
        )
        trail = append_mini_onboarding_review(
            trail,
            store_id=source["store_id"],
            candidate_id=accepted.candidate_id,
            invoice_id=invoice["invoice_id"],
            reviewer_id=reviewer_id,
            occurred_at=review_time,
            review_reason="Synthetic owner verified required fields",
            reason_codes=tuple(code.value for code in verdict_result.reason_codes),
            verified_fields=required_fields,
        )
        assert mini.state is (
            MiniOnboardingState.READY_TO_LOCK if index == 3 else MiniOnboardingState.COLLECTING
        )

    assert mini.remaining_count == 0
    assert mini.completed_invoice_ids == tuple(f"e08-mini-synthetic-{n}" for n in range(1, 5))
    with pytest.raises(ValueError, match="exactly four reviewed invoices"):
        # The test's pre-final snapshot has fewer than N=4 reviews.
        accept_candidate_and_start_mini_onboarding(
            reviewed,
            "synthetic-reviewer",
            "2026-10-23T12:10:00Z",
            "This is a candidate transition, not a bank lock",
        )[1].lock_bank_snapshot(
            "synthetic-snapshot-too-early",
            locked_by="synthetic-reviewer",
            locked_at="2026-10-23T12:11:00Z",
        )

    locked = mini.lock_bank_snapshot(
        "synthetic-candidate-bank-snapshot-1",
        locked_by="synthetic-reviewer",
        locked_at="2026-10-23T12:15:00Z",
    )
    trail = append_mini_onboarding_lock(
        trail,
        store_id=source["store_id"],
        candidate_id=accepted.candidate_id,
        bank_snapshot_id=locked.bank_snapshot_id,
        locked_by=locked.locked_by,
        locked_at=locked.locked_at,
    )
    assert locked.state is MiniOnboardingState.LOCKED
    assert locked.bank_snapshot_id == "synthetic-candidate-bank-snapshot-1"
    assert trail.verify()
    assert [event.event_type for event in trail.entries] == [
        AuditEventType.CANDIDATE_REVIEWED,
        AuditEventType.CANDIDATE_ACCEPTED,
        *[
            event_type
            for _index in range(4)
            for event_type in (
                AuditEventType.NEW_TYPE_DETECTED,
                AuditEventType.MINI_ONBOARDING_INVOICE_REVIEWED,
            )
        ],
        AuditEventType.MINI_ONBOARDING_LOCKED,
    ]
    assert trail.entries[-1].bank_snapshot_id == "synthetic-candidate-bank-snapshot-1"
    assert trail.entries[3].verified_fields == tuple(sorted(required_fields))


def test_audit_hash_chain_detects_mutation_and_counts_unique_unresolved_invoices():
    trail = AuditTrail()
    for index in range(3):
        trail = trail.append(
            event_type=AuditEventType.NEW_TYPE_DETECTED,
            store_id="e08-synthetic-store",
            occurred_at=f"2026-10-23T{9 + index:02d}:00:00Z",
            invoice_id=f"e08-invoice-{index + 1}",
            match_scores={"e05-layout-01": 0.1},
            candidate_id="e08-candidate-unresolved",
            verdict=Verdict.REVIEW,
            reason_codes=(ReasonCode.NEW_LAYOUT,),
            detection_kind=DetectionKind.NEW_TYPE,
        )
    assert trail.escalation_required("e08-synthetic-store", "2026-10-23T12:00:00Z")
    assert not trail.escalation_required(
        "e08-synthetic-store",
        "2026-10-24T12:00:00Z",
        window=timedelta(hours=24),
    )
    assert trail.verify()

    tampered_event = replace(trail.entries[1], review_reason="tampered after append")
    tampered = AuditTrail((trail.entries[0], tampered_event, trail.entries[2]))
    assert not tampered.verify()


def test_audit_helper_requires_reviewer_reason_and_valid_candidate_decision():
    with pytest.raises(ValueError, match="review_reason"):
        append_candidate_transition(
            AuditTrail(),
            store_id="e08-synthetic-store",
            candidate_id="e08-candidate-id",
            reviewer_id="synthetic-reviewer",
            occurred_at=NOW,
            review_reason="",
        )
    with pytest.raises(ValueError, match="decision"):
        append_candidate_transition(
            AuditTrail(),
            store_id="e08-synthetic-store",
            candidate_id="e08-candidate-id",
            reviewer_id="synthetic-reviewer",
            occurred_at=NOW,
            review_reason="Synthetic reason",
            decision="MAYBE",
        )
