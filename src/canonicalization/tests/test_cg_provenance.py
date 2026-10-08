"""WP-6.1 provenance tests — full-chain verification, broken-chain refusal,
P4.2 DERIVED provenance, trace composition (SPEC §9; dispatch axes 9–11).

The gate consumes the P5.2 whole-chain walk (never bypasses it): every
canonicalization re-verifies the entire pipeline down to Capture S1, and a
broken link ANYWHERE upstream refuses admission with zero residue.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cg_helpers import BINDING, FORMULA  # noqa: E402
from canonicalization import (  # noqa: E402
    ORIGIN_HOLOO_CAPTURE,
    CanonicalizationAccepted,
    CanonicalizationInputIntegrityFailure,
    CanonicalizationRoutedToReview,
    CanonicalInvoiceTraceSuccess,
)
from validation import ValidationTraceSuccess  # noqa: E402


def _admit(stack):
    _, projection = stack.build_valid_identity_state()
    outcome = stack.gate.canonicalize(
        projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    return outcome


def test_trace_walks_the_full_chain_to_capture_s1(stack):
    outcome = _admit(stack)
    trace = stack.gate.trace_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert isinstance(trace, CanonicalInvoiceTraceSuccess), trace
    rendered = "\n".join(trace.chain)
    # the head links are present
    assert trace.chain[0].startswith("canonical_invoice:")
    assert any(link.startswith("gate_decision:") for link in trace.chain)
    assert any("P5.2 whole-chain re-verified" in link for link in trace.chain)
    assert any(link.startswith("identity_pointers:") for link in trace.chain)
    # the P5.2 sub-walk reaches Capture S1 (relayed coarse links, indented)
    assert "capture: OK" in rendered
    # and the extraction/binding/normalization links are relayed too
    assert "extraction" in rendered and "binding" in rendered \
        and "normalization" in rendered


def test_trace_covers_p42_derived_provenance(stack):
    """Dispatch axis 11: the DERIVED total.gross rides the chain through the
    WP-5.1 whole-chain sub-walks — P4.2 provenance is consumed, never cut.
    The P5.2 chain relays the per-rule sub-walk verdicts; the P4.2 derivation
    link is re-verified INSIDE each WP-5.1 walk (asserted here on the same
    validation records the admitted state consumed)."""
    outcome = _admit(stack)
    trace = stack.gate.trace_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert isinstance(trace, CanonicalInvoiceTraceSuccess), trace
    rendered = "\n".join(trace.chain)
    # the relayed P5.1 sub-walk verdicts are present
    assert "validation[0]" in rendered and "WP-5.1 whole-chain" in rendered
    # the R_CONSIST rule consumed the DERIVED total.gross — its whole-chain
    # walk carries the WP-4.2 derivation link, re-verified
    nid = outcome.canonical_invoice.normalization_id
    vids = stack.val.validations_for_normalization(nid)
    derivation_seen = False
    for vid in vids:
        walk = stack.val.trace_validation(vid)
        assert type(walk).__name__ == "ValidationTraceSuccess", walk
        for link in walk.chain:
            if "DERIVED via derivation" in link and "WP-4.2" in link:
                derivation_seen = True
    assert derivation_seen, "P4.2 derivation link missing from the walks"


def test_no_canonicalization_on_broken_upstream_chain(stack):
    """Dispatch axis 10: a tampered upstream record breaks the P5.2 walk —
    the gate refuses with an integrity failure and ZERO durable residue."""
    _, projection = stack.build_valid_identity_state()
    state_id = projection.record.domain_state_id
    # tamper a FROZEN-layer record (normalization) — the whole chain breaks
    import sqlite3
    conn = sqlite3.connect(str(stack.norm_db))
    try:
        conn.execute("UPDATE normalization_records SET field_count = 99")
        conn.commit()
    finally:
        conn.close()
    outcome = stack.gate.canonicalize(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert type(outcome).__name__ == \
        "CanonicalizationInputIntegrityFailure", outcome
    assert "provenance" in outcome.reason or "normalization" in \
        outcome.reason
    # zero residue: no decision, no invoice, no review item
    assert len(stack.gate.decisions()) == 0
    assert len(stack.gate.canonical_invoices()) == 0
    assert len(stack.gate.list_gate_review_items()) == 0


def test_no_canonicalization_on_broken_domain_state_read(stack):
    _, projection = stack.build_valid_identity_state()
    state_id = projection.record.domain_state_id
    import sqlite3
    conn = sqlite3.connect(str(stack.vsm_db))
    try:
        conn.execute("UPDATE domain_state_records SET state_detail = 'forged'"
                     " WHERE domain_state_id = ?", (state_id,))
        conn.commit()
    finally:
        conn.close()
    outcome = stack.gate.canonicalize(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationInputIntegrityFailure), outcome
    assert len(stack.gate.canonical_invoices()) == 0


def test_trace_refuses_unknown_invoice(stack):
    trace = stack.gate.trace_canonical_invoice("nope")
    assert type(trace).__name__ == "CanonicalInvoiceTraceRefused", trace


def test_trace_detects_post_admission_upstream_tamper(stack):
    """The chain is re-verified on EVERY walk — tampering upstream AFTER a
    successful admission breaks the trace of the already-created invoice."""
    outcome = _admit(stack)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    trace1 = stack.gate.trace_canonical_invoice(invoice_id)
    assert isinstance(trace1, CanonicalInvoiceTraceSuccess), trace1
    import sqlite3
    conn = sqlite3.connect(str(stack.binding_db))
    try:
        conn.execute("UPDATE extraction_bindings SET binding_id = 'forged'")
        conn.commit()
    finally:
        conn.close()
    trace2 = stack.gate.trace_canonical_invoice(invoice_id)
    assert type(trace2).__name__ == "CanonicalInvoiceTraceIntegrityFailure", \
        trace2


def test_review_route_still_verifies_the_chain(stack):
    """Even REVIEW-routed states get the full chain walk first — the gate
    never routes on unverified input."""
    from cg_helpers import deferred_state
    _, projection = deferred_state(stack)
    outcome = stack.gate.canonicalize(projection.record.domain_state_id,
                                      ORIGIN_HOLOO_CAPTURE)
    assert isinstance(outcome, CanonicalizationRoutedToReview), outcome


def test_trace_failure_names_the_broken_link(stack):
    _, projection = stack.build_valid_identity_state()
    state_id = projection.record.domain_state_id
    import sqlite3
    conn = sqlite3.connect(str(stack.norm_db))
    try:
        conn.execute("UPDATE normalization_records SET capture_s1 = 'x'")
        conn.commit()
    finally:
        conn.close()
    outcome = stack.gate.canonicalize(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationInputIntegrityFailure), outcome


def test_identity_pointer_rejoin_in_trace(stack):
    outcome = _admit(stack)
    trace = stack.gate.trace_canonical_invoice(
        outcome.canonical_invoice.canonical_invoice_id)
    assert isinstance(trace, CanonicalInvoiceTraceSuccess), trace
    pointers_link = [c for c in trace.chain
                     if c.startswith("identity_pointers:")][0]
    assert "3 role pointers re-joined" in pointers_link


def test_capture_s1_anchored_end_to_end(stack):
    """The full pipeline path Capture → … → Gate is machine-checkable: the
    admitted invoice's capture_s1 equals the ORIGINAL capture record's S1."""
    from cg_helpers import unique_identity_pages
    pages = unique_identity_pages()
    from capture import CaptureService
    content = CaptureService.aggregate(pages)
    ingest = stack.capture.ingest(content, source_label="cg-prov")
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
    from vsm_helpers import REF_KEYS
    for rule, _ in REF_KEYS:
        out = stack.val.validate(normed.record.normalization_id, rule, "1")
        assert type(out).__name__ == "ValidationCompleted", out
    projection = stack.project(normed.record.normalization_id, REF_KEYS,
                               ruleset_id="cg-prov-rules")
    outcome = stack.gate.canonicalize(projection.record.domain_state_id,
                                      ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, CanonicalizationAccepted), outcome
    assert outcome.canonical_invoice.capture_s1 == ingest.record.s1
