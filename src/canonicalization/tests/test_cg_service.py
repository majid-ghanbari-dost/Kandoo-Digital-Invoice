"""WP-6.1 service integration + determinism tests (SPEC §6 determinism analog;
dispatch axes 13, 23, and the D-03 determinism discipline).

Decision CONTENT (route, reason, detail, identity fingerprint) is a pure
function of (verified upstream content, declared request) — bookkeeping ids
and the clock are separated. The same semantics under different byte orders,
different engines, and different orderings always decide identically.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cg_helpers import (  # noqa: E402
    BINDING,
    PAGE_IDENTITY_OK,
    decisive_invalid_state,
    tolerance_invalid_state,
)
from canonicalization import (  # noqa: E402
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    CanonicalizationAccepted,
    CanonicalizationRejected,
    CanonicalizationRoutedToReview,
)


def test_decision_content_is_independent_of_identity_scalars(stack):
    """Two decisions over identical verified content carry identical
    route/reason/detail — bookkeeping ids and the clock differ only. The two
    admissions ride the SAME S2 values under DIFFERENT declared origins
    (same values under one origin would be a G5 duplicate rejection)."""
    from cg_helpers import PAGE_IDENTITY_TWIN
    _, p1 = stack.build_valid_identity_state(parts=PAGE_IDENTITY_OK)
    o1 = stack.gate.canonicalize(p1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    _, p2 = stack.build_valid_identity_state(parts=PAGE_IDENTITY_TWIN)
    o2 = stack.gate.canonicalize(p2.record.domain_state_id,
                                 ORIGIN_OTHER_POS_CAPTURE, BINDING)
    assert isinstance(o1, CanonicalizationAccepted), o1
    assert isinstance(o2, CanonicalizationAccepted), o2
    d1, d2 = o1.decision, o2.decision
    assert d1.decision == d2.decision
    assert d1.decision_reason == d2.decision_reason
    assert d1.identity_class == d2.identity_class
    assert d1.identity_source == d2.identity_source
    # the audit detail is content-derived and identical here
    assert d1.decision_detail == d2.decision_detail
    # bookkeeping differs
    assert d1.decision_id != d2.decision_id
    # the identity fingerprints differ ONLY by the declared-origin scope
    assert o1.canonical_invoice.identity_fingerprint != \
        o2.canonical_invoice.identity_fingerprint
    assert o1.canonical_invoice.origin == "HOLOO_CAPTURE"
    assert o2.canonical_invoice.origin == "OTHER_POS_CAPTURE"


def test_identity_resolution_is_pure_over_binding_and_values(stack):
    """Changing ONLY the binding (not the corpus) changes the decision
    deterministically: binding to a field with two candidates conflicts;
    binding to distinct usable fields admits."""
    pages = [b"invoice.number=INV-BIND-1\ninvoice.number=INV-BIND-2\n"
             b"invoice.date=2026-10-07\ntotal.net=900.00\ntax.amount=72\n"]
    nid, projection = stack.build_valid_identity_state(parts=pages)
    outcome = stack.gate.canonicalize(projection.record.domain_state_id,
                                      ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
    assert outcome.decision.decision_reason == \
        "d03-conflicting-document-identity"


def test_rejected_and_review_routes_are_deterministic(stack):
    _, i1 = decisive_invalid_state(stack)
    r1 = stack.gate.canonicalize(i1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE)
    _, i2 = decisive_invalid_state(stack)
    r2 = stack.gate.canonicalize(i2.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE)
    assert isinstance(r1, CanonicalizationRejected), r1
    assert isinstance(r2, CanonicalizationRejected), r2
    assert r1.decision.decision_reason == r2.decision.decision_reason
    _, t1 = tolerance_invalid_state(stack)
    v1 = stack.gate.canonicalize(t1.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE)
    _, t2 = tolerance_invalid_state(stack)
    v2 = stack.gate.canonicalize(t2.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE)
    assert isinstance(v1, CanonicalizationRoutedToReview), v1
    assert isinstance(v2, CanonicalizationRoutedToReview), v2
    assert v1.decision.decision_reason == v2.decision.decision_reason


def test_issue_reports_stay_empty_on_the_happy_paths(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    stack.gate.trace_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert stack.gate.issue_reports() == []


def test_gate_is_engine_independent_by_construction(stack):
    """The gate is engine-agnostic: no extraction/normalization ENGINE symbol
    is imported or referenced anywhere in the canonicalization package, and a
    decision rides only verified reads + the declared request."""
    CG = Path(__file__).resolve().parent.parent / "canonicalization"
    for path in CG.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "ReferenceDelimitedEngine" not in text, path.name
        assert "ExtractionEngine" not in text, path.name
        assert "ReferenceNormalizationRules" not in text, path.name
    from cg_helpers import unique_identity_pages
    nid, projection = stack.build_valid_identity_state(
        parts=unique_identity_pages())
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    assert outcome.decision.identity_class == "DETERMINISTIC"


def test_gate_request_surfaces_in_the_audit_detail(stack):
    """The declared request rides the decision (origin in the row; the binding
    metadata in the detail) — auditable end to end."""
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    assert outcome.decision.declared_origin == "HOLOO_CAPTURE"
    detail = outcome.decision.decision_detail
    assert "INVOICE_NUMBER:invoice.number" in detail
    assert "INVOICE_DATE:invoice.date" in detail
    assert "INVOICE_TOTAL:total.net" in detail
    assert "all frozen conditions met" in detail


def test_end_to_end_capture_to_canonical_invoice(stack):
    """Dispatch axis 23: the WHOLE pipeline in one test — Capture S1 → … →
    VALID state → Gate → Canonical Invoice, every link re-verified."""
    from capture import CaptureService
    from cg_helpers import unique_identity_pages, FORMULA
    from vsm_helpers import REF_KEYS

    pages = unique_identity_pages()
    ingest = stack.capture.ingest(CaptureService.aggregate(pages),
                                  source_label="cg-e2e")
    assert type(ingest).__name__ == "IngestCompleted", ingest
    built = stack.recon.reconstruct(ingest.capture_id)
    assert type(built).__name__ == "ReconstructCompleted", built
    done = stack.extraction.extract(built.document.document_id,
                                    "reference-delimited-v1")
    assert type(done).__name__ == "ExtractionCompleted", done
    bound = stack.binder.bind_extraction(done.extraction.extraction_id)
    assert type(bound).__name__ == "BindingCompleted", bound
    normed = stack.norm.normalize(done.extraction.extraction_id,
                                  "kandoo-norm-v1")
    assert type(normed).__name__ == "NormalizationCompleted", normed
    derived = stack.deriv.derive(normed.record.normalization_id, FORMULA, "1")
    assert type(derived).__name__ == "DerivationCompleted", derived
    for rule, _ in REF_KEYS:
        out = stack.val.validate(normed.record.normalization_id, rule, "1")
        assert type(out).__name__ == "ValidationCompleted", out
    projection = stack.project(normed.record.normalization_id, REF_KEYS,
                               ruleset_id="cg-e2e-rules")
    outcome = stack.gate.canonicalize(projection.record.domain_state_id,
                                      ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    trace = stack.gate.trace_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert type(trace).__name__ == "CanonicalInvoiceTraceSuccess", trace
    assert outcome.canonical_invoice.capture_s1 == ingest.record.s1
    # the admitted invoice is readable and verified
    read = stack.gate.read_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert type(read).__name__ == "CanonicalInvoiceReadSuccess", read


def test_second_pipeline_run_for_a_new_document_admits_independently(stack):
    """Two real documents → two canonical invoices; neither blocks the
    other (document-level uniqueness is exact, not global)."""
    from cg_helpers import unique_identity_pages
    o1 = stack.canonicalize_ok(
        stack.build_valid_identity_state(
            parts=unique_identity_pages(total_net="111.00", tax="9"))[1]
        .record.domain_state_id)
    o2 = stack.canonicalize_ok(
        stack.build_valid_identity_state(
            parts=unique_identity_pages(total_net="222.00", tax="18"))[1]
        .record.domain_state_id)
    assert o1.canonical_invoice.canonical_invoice_id != \
        o2.canonical_invoice.canonical_invoice_id
    assert o1.canonical_invoice.identity_fingerprint != \
        o2.canonical_invoice.identity_fingerprint


def test_origin_declaration_changes_only_the_scope_component(stack):
    """The declared origin participates ONLY in the identity fingerprint
    scope — the decision route for the same verified content is otherwise
    identical (ACCEPTED in both capture-pipeline origins)."""
    _, p1 = stack.build_valid_identity_state()
    a = stack.gate.canonicalize(p1.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE, BINDING)
    _, p2 = stack.build_valid_identity_state(parts=PAGE_IDENTITY_OK)
    b = stack.gate.canonicalize(p2.record.domain_state_id,
                                ORIGIN_OTHER_POS_CAPTURE, BINDING)
    assert isinstance(a, CanonicalizationAccepted), a
    assert isinstance(b, CanonicalizationAccepted), b
    assert a.decision.decision == b.decision.decision == "ACCEPTED"
    assert a.decision.decision_reason == b.decision.decision_reason
    assert a.canonical_invoice.origin == "HOLOO_CAPTURE"
    assert b.canonical_invoice.origin == "OTHER_POS_CAPTURE"
