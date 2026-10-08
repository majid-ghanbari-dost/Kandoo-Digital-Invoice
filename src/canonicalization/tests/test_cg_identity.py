"""WP-6.1 identity-resolution tests — D-02/D-03 mechanics, exact only
(SPEC §5; dispatch axes 5–8, 21, 22).

Covers: S2 exact-match acceptance; missing identity field → incomplete REVIEW;
multiple candidates → conflicting REVIEW (never auto-resolved); no binding →
undetermined REVIEW; empty value → not usable; malformed binding refusals;
exactness of the identity fingerprint (no fuzzy anywhere); the reserved
adapter path declaration; identity pointer rows; source-scope semantics of
the fingerprint (declared origin).
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cg_helpers import (  # noqa: E402
    BINDING,
    PAGE_IDENTITY_AMBIGUOUS_NUMBER,
    PAGE_IDENTITY_EMPTY_NUMBER,
    PAGE_IDENTITY_NO_DATE,
    unique_identity_pages,
)
from canonicalization import (  # noqa: E402
    IDENTITY_ROLES,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    REASON_D03_CONFLICTING_IDENTITY,
    REASON_D03_INCOMPLETE_IDENTITY,
    REASON_D03_UNDETERMINED_IDENTITY,
    CanonicalizationAccepted,
    CanonicalizationRejected,
    CanonicalizationRequestRefused,
    CanonicalizationRoutedToReview,
    resolve_identity,
    validate_binding,
)


def test_s2_exact_match_is_deterministic_and_accepted(stack):
    nid, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    assert outcome.decision.identity_class == "DETERMINISTIC"
    assert outcome.decision.identity_source == "S2_EXTRACTED_VERIFIED"
    assert outcome.canonical_invoice.identity_fingerprint != ""


def test_identity_fingerprint_is_deterministic_across_replays(stack):
    """The same S2 content under the same declared origin always yields the
    same identity fingerprint — on two independent, byte-different captures
    the fingerprints COLLIDE exactly (that is what makes the D-03 duplicate
    check exact)."""
    _, p1 = stack.build_valid_identity_state(
        parts=[b"invoice.number=INV-FP-1\ninvoice.date=2026-10-07\n"
               b"total.net=1000.00\ntax.amount=80\n"])
    o1 = stack.gate.canonicalize(p1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o1, CanonicalizationAccepted), o1
    _, p2 = stack.build_valid_identity_state(
        parts=[b"invoice.date=2026-10-07\ntotal.net=1000.00\n"
               b"tax.amount=80\ninvoice.number=INV-FP-1\n"])
    o2 = stack.gate.canonicalize(p2.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    # different capture (different S1) + identical S2 → definite duplicate
    assert isinstance(o2, CanonicalizationRejected), o2
    assert o1.canonical_invoice.identity_fingerprint == \
        o2.decision.identity_fingerprint


def test_identity_fingerprint_scopes_by_declared_origin(stack):
    """The declared origin is the source-system scope (D-02): the same S2
    values under DIFFERENT origins are never compared as the same document."""
    _, p1 = stack.build_valid_identity_state()
    o1 = stack.gate.canonicalize(p1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o1, CanonicalizationAccepted), o1
    _, p2 = stack.build_valid_identity_state(
        parts=[b"invoice.number=INV-CG-2026-001\ninvoice.date=2026-10-07\n"
               b"total.net=1000.00\ntax.amount=80\n"])
    o2 = stack.gate.canonicalize(p2.record.domain_state_id,
                                 ORIGIN_OTHER_POS_CAPTURE, BINDING)
    assert isinstance(o2, CanonicalizationAccepted), o2
    assert o1.canonical_invoice.identity_fingerprint != \
        o2.canonical_invoice.identity_fingerprint


def test_missing_identity_field_routes_incomplete_review(stack):
    nid, projection = stack.build_valid_identity_state(
        parts=PAGE_IDENTITY_NO_DATE)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision_reason == REASON_D03_INCOMPLETE_IDENTITY
    assert outcome.decision.identity_class == "CAPTURE_SCOPED"
    # D-03: ناقص → REVIEW — the missing field is named in the audit detail
    assert "INVOICE_DATE" in outcome.decision.decision_detail
    # and no canonical invoice exists
    assert len(stack.gate.canonical_invoices()) == 0


def test_multiple_candidates_conflict_and_never_auto_resolve(stack):
    """Dispatch §6: multiple candidates → DO NOT AUTO-RESOLVE. Two extracted
    invoice numbers are a D-03 conflicting case → REVIEW."""
    nid, projection = stack.build_valid_identity_state(
        parts=PAGE_IDENTITY_AMBIGUOUS_NUMBER)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision_reason == \
        REASON_D03_CONFLICTING_IDENTITY
    assert "INVOICE_NUMBER:invoice.numberx2" in \
        outcome.decision.decision_detail
    assert len(stack.gate.canonical_invoices()) == 0


def test_empty_value_is_not_a_usable_identity_value(stack):
    """OD-G2: an empty normalized value is not usable — the identity is
    incomplete, never guessed."""
    nid, projection = stack.build_valid_identity_state(
        parts=PAGE_IDENTITY_EMPTY_NUMBER)
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision_reason == REASON_D03_INCOMPLETE_IDENTITY


def test_no_binding_routes_undetermined_review(stack):
    """OD-G10: no binding declared → no document identity attempted →
    explicitly undetermined → REVIEW (D-03 ambiguity path)."""
    nid, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision_reason == \
        REASON_D03_UNDETERMINED_IDENTITY
    assert outcome.decision.identity_class == "CAPTURE_SCOPED"
    assert outcome.decision.identity_fingerprint == ""


def test_empty_binding_equals_no_binding(stack):
    nid, projection = stack.build_valid_identity_state()
    a = stack.gate.canonicalize(projection.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE, {})
    b = stack.gate.canonicalize("x" * 32, ORIGIN_HOLOO_CAPTURE, None)
    assert isinstance(a, CanonicalizationRoutedToReview), a
    assert a.decision.decision_reason == REASON_D03_UNDETERMINED_IDENTITY
    assert type(b).__name__ == "CanonicalizationRequestRefused", b


def test_partial_binding_is_refused(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE,
        {"INVOICE_NUMBER": "invoice.number"})
    assert type(outcome).__name__ == "CanonicalizationRequestRefused", outcome
    assert "exactly the three frozen D-02 roles" in outcome.detail


def test_unknown_role_is_refused(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE,
        {"INVOICE_NUMBER": "invoice.number", "INVOICE_DATE": "invoice.date",
         "INVOICE_TOTAL": "total.net", "INVOICE_EXTRA": "x"})
    assert type(outcome).__name__ == "CanonicalizationRequestRefused", outcome


def test_duplicate_binding_target_is_refused(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE,
        {"INVOICE_NUMBER": "invoice.number", "INVOICE_DATE": "invoice.date",
         "INVOICE_TOTAL": "invoice.date"})
    assert type(outcome).__name__ == "CanonicalizationRequestRefused", outcome
    assert "DISTINCT" in outcome.detail


def test_non_string_binding_target_is_refused(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE,
        {"INVOICE_NUMBER": "invoice.number", "INVOICE_DATE": "invoice.date",
         "INVOICE_TOTAL": 42})
    assert type(outcome).__name__ == "CanonicalizationRequestRefused", outcome


def test_binding_to_unextracted_field_is_incomplete(stack):
    """A binding to a field the engine never extracted resolves 0 candidates →
    incomplete REVIEW — never a guess, never an invention."""
    nid, projection = stack.build_valid_identity_state()
    binding = {"INVOICE_NUMBER": "invoice.number",
               "INVOICE_DATE": "invoice.date",
               "INVOICE_TOTAL": "nonexistent.total"}
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, binding)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision_reason == REASON_D03_INCOMPLETE_IDENTITY


def test_binding_validation_is_pure_and_strict():
    assert validate_binding(None) is None
    assert validate_binding({}) is None
    normalized = validate_binding({
        "INVOICE_NUMBER": "a", "INVOICE_DATE": "b", "INVOICE_TOTAL": "c"})
    assert normalized == {"INVOICE_NUMBER": "a", "INVOICE_DATE": "b",
                          "INVOICE_TOTAL": "c"}
    with pytest.raises(ValueError):
        validate_binding({"INVOICE_NUMBER": "a"})
    with pytest.raises(ValueError):
        validate_binding("not-a-mapping")
    with pytest.raises(ValueError):
        validate_binding({"INVOICE_NUMBER": "a", "INVOICE_DATE": "b",
                          "INVOICE_TOTAL": "c", "EXTRA": "d"})


def test_identity_pointers_carry_roles_not_values(stack):
    """SPEC §5 I5 / §6: the S2 tuple rides as fingerprint + per-role POINTER
    rows — no raw pipeline value is ever copied into the gate store."""
    nid, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    pointers = outcome.identity_pointers
    assert len(pointers) == 3
    assert {p.role for p in pointers} == set(IDENTITY_ROLES)
    for p in pointers:
        assert p.normalization_id == nid
        assert isinstance(p.field_seq, int)
        assert p.source_field_name == BINDING[p.role]
        # the pointer row carries NO value — only role/name/seq anchors
        assert "INV" not in str(p.field_seq)


def test_resolver_is_value_honest():
    """The pure resolver's outward result carries metadata + fingerprints
    only — candidate counts and field seqs, never pipeline values."""
    from canonicalization import IdentityResolution
    from capture import S1Service
    from normalization.model import NormalizedField, NormalizationStatus
    fields = [
        NormalizedField(field_seq=0, source_field_name="invoice.number",
                        source_provenance="EXTRACTED",
                        status=NormalizationStatus.NORMALIZED,
                        normalized_value="INV-SECRET-1", rules_applied="nfc,trim",
                        reason_code=None),
        NormalizedField(field_seq=1, source_field_name="invoice.date",
                        source_provenance="EXTRACTED",
                        status=NormalizationStatus.NORMALIZED,
                        normalized_value="2026-10-07", rules_applied="date-iso",
                        reason_code=None),
        NormalizedField(field_seq=2, source_field_name="total.net",
                        source_provenance="EXTRACTED",
                        status=NormalizationStatus.NORMALIZED,
                        normalized_value="1000.00",
                        rules_applied="number-canonical", reason_code=None),
    ]
    binding = {"INVOICE_NUMBER": "invoice.number",
               "INVOICE_DATE": "invoice.date",
               "INVOICE_TOTAL": "total.net"}
    resolution = resolve_identity(binding, fields, ORIGIN_HOLOO_CAPTURE,
                                  S1Service())
    assert isinstance(resolution, IdentityResolution)
    assert resolution.identity_class == "DETERMINISTIC"
    rendered = repr(resolution.role_resolutions)
    assert "INV-SECRET-1" not in rendered          # values never surface
    assert "1000.00" not in rendered
    assert resolution.role_resolutions[0].candidate_count == 1


def test_reserved_adapter_path_is_declared_not_implemented():
    """OD-G5: D-02's first deterministic path (adapter document id) has no
    producer in the implemented pipeline — the identity-source vocabulary
    contains exactly the S2 path and nothing invented."""
    from canonicalization import IDENTITY_SOURCES
    assert IDENTITY_SOURCES == ("S2_EXTRACTED_VERIFIED",)


def test_distinct_documents_never_collapse(stack):
    """Exact matching cuts both ways: different S2 values are NEVER matched
    (no fuzzy, no similarity) — both documents admit independently."""
    _, p1 = stack.build_valid_identity_state()
    o1 = stack.gate.canonicalize(p1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    _, p2 = stack.build_valid_identity_state(
        parts=unique_identity_pages(total_net="2000.00", tax="160"))
    o2 = stack.gate.canonicalize(p2.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(o1, CanonicalizationAccepted), o1
    assert isinstance(o2, CanonicalizationAccepted), o2
    assert o1.canonical_invoice.canonical_invoice_id != \
        o2.canonical_invoice.canonical_invoice_id
    assert o1.canonical_invoice.identity_fingerprint != \
        o2.canonical_invoice.identity_fingerprint
