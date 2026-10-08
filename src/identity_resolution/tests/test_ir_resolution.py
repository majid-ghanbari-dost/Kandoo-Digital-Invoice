"""WP-7.1 resolution-state tests — S2 establishment, CAPTURE_SCOPED routes,
candidate evidence preservation, request validation (SPEC §5/§3; dispatch
§11 cases C/D/E partial, §12 missing/two-candidate axes)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ir_helpers import (  # noqa: E402
    BINDING,
    BINDING_TOTAL_VIA_VAT,
    IdentityDefiniteDuplicate,
    IdentityReplay,
    IdentityResolutionRecorded,
    IdentityRequestRefused,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    absent_total_role_pages,
    ambiguous_date_pages,
    ambiguous_number_pages,
    ambiguous_total_role_pages,
    decisive_invalid_state,
    deferred_state,
    no_number_pages,
    unresolved_state,
    unique_ir_pages,
)

from identity_resolution import (  # noqa: E402
    CAPTURE_SCOPED_REASONS,
    IDENTITY_ROLES,
    IDENTITY_SCOPE_CAPTURE_SCOPED,
    IDENTITY_SCOPE_S2,
    IDENTITY_SOURCE_S2,
    ORIGINS,
    SCOPE_REASON_D03_CONFLICTING,
    SCOPE_REASON_D03_INCOMPLETE,
    SCOPE_REASON_D03_UNDETERMINED,
    SCOPE_REASON_S2_NOT_ATTEMPTED,
)


def _recorded(stack, parts=None, binding=None, origin=ORIGIN_HOLOO_CAPTURE,
              label="ir-res"):
    _, projection = stack.build_valid_identity_state(parts=parts,
                                                     label=label)
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     origin,
                                     BINDING if binding is None else binding)
    assert isinstance(outcome, IdentityResolutionRecorded), outcome
    return outcome


# ---------------------------------------------------------------------------
# S2 establishment (the frozen triad, verified)
# ---------------------------------------------------------------------------

def test_valid_clear_state_resolves_s2(stack):
    outcome = _recorded(stack, label="ir-res-s2")
    assert outcome.record.identity_scope == IDENTITY_SCOPE_S2
    assert outcome.record.identity_source == IDENTITY_SOURCE_S2
    assert outcome.record.identity_fingerprint != ""
    assert outcome.record.scope_reason == ""


def test_s2_record_role_rows_shape(stack):
    outcome = _recorded(stack, label="ir-res-roles")
    assert len(outcome.role_rows) == 3
    assert [r.role for r in outcome.role_rows] == list(IDENTITY_ROLES)
    for row in outcome.role_rows:
        assert row.candidate_count == 1
        assert len(row.field_seqs) == 1
        assert row.resolved_field_seq == row.field_seqs[0]
        assert row.source_field_name == BINDING[row.role]
        assert row.resolution_id == outcome.record.resolution_id


def test_s2_fingerprint_is_sha256_v1_hex(stack):
    outcome = _recorded(stack, label="ir-res-fp")
    fp = outcome.record.identity_fingerprint
    assert len(fp) == 64
    assert fp == fp.lower()
    int(fp, 16)  # hex


def test_record_carries_the_s1_leg_verbatim(stack):
    _, projection = stack.build_valid_identity_state(label="ir-res-s1")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.capture_s1 == projection.record.capture_s1
    assert (outcome.record.capture_s1_algorithm_id
            == projection.record.capture_s1_algorithm_id)


def test_record_anchors_the_full_verified_chain(stack):
    _, projection = stack.build_valid_identity_state(label="ir-res-anchors")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
    r = outcome.record
    assert r.domain_state_id == projection.record.domain_state_id
    assert r.normalization_id == projection.record.normalization_id
    assert r.extraction_id == projection.record.extraction_id
    assert r.document_id == projection.record.document_id
    assert r.capture_id == projection.record.capture_id


def test_declared_origin_recorded_verbatim(stack):
    for origin in (ORIGIN_HOLOO_CAPTURE, ORIGIN_OTHER_POS_CAPTURE):
        outcome = _recorded(stack, origin=origin,
                            label=f"ir-res-origin-{origin}")
        assert outcome.record.declared_origin == origin


def test_resolved_pointers_rejoin_the_verified_read_byte_identical(stack):
    parts = unique_ir_pages()
    outcome = _recorded(stack, parts=parts, label="ir-res-rejoin")
    read = stack.norm.read_normalization(outcome.record.normalization_id)
    by_seq = {f.field_seq: f for f in read.fields}
    expected = {"INVOICE_NUMBER": parts[0].split(b"=")[1].split(b"\n")[0]
                .decode(),
                "INVOICE_DATE": "2026-10-08",
                "INVOICE_TOTAL": "1000.00"}
    for row in outcome.role_rows:
        field = by_seq[row.resolved_field_seq]
        assert field.source_field_name == row.source_field_name
        assert field.normalized_value == expected[row.role]


# ---------------------------------------------------------------------------
# CAPTURE_SCOPED via the S2 attempt (R1a — incomplete / conflicting /
# undetermined; reason codes relayed verbatim from the frozen primitive)
# ---------------------------------------------------------------------------

def test_missing_invoice_number_is_incomplete(stack):
    outcome = _recorded(stack, parts=no_number_pages(),
                        label="ir-res-nonum")
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.scope_reason == SCOPE_REASON_D03_INCOMPLETE
    assert outcome.record.identity_fingerprint == ""


def test_missing_invoice_date_is_incomplete(stack):
    parts = [b"invoice.number=INV-IR-NODATE\n"
             b"total.net=500.00\ntax.amount=40\n"]
    outcome = _recorded(stack, parts=parts, label="ir-res-nodate")
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.scope_reason == SCOPE_REASON_D03_INCOMPLETE


def test_missing_invoice_total_role_is_incomplete(stack):
    outcome = _recorded(stack, parts=absent_total_role_pages(),
                        binding=BINDING_TOTAL_VIA_VAT,
                        label="ir-res-nototal")
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.scope_reason == SCOPE_REASON_D03_INCOMPLETE
    total_row = [r for r in outcome.role_rows
                 if r.role == "INVOICE_TOTAL"][0]
    assert total_row.candidate_count == 0
    assert total_row.field_seqs == ()
    assert total_row.resolved_field_seq is None


def test_two_invoice_number_candidates_conflicting(stack):
    outcome = _recorded(stack, parts=ambiguous_number_pages(),
                        label="ir-res-ambignum")
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.scope_reason == SCOPE_REASON_D03_CONFLICTING


def test_two_date_candidates_conflicting(stack):
    outcome = _recorded(stack, parts=ambiguous_date_pages(),
                        label="ir-res-ambigdate")
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.scope_reason == SCOPE_REASON_D03_CONFLICTING


def test_two_total_role_candidates_conflicting(stack):
    outcome = _recorded(stack, parts=ambiguous_total_role_pages(),
                        binding=BINDING_TOTAL_VIA_VAT,
                        label="ir-res-ambigtotal")
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.scope_reason == SCOPE_REASON_D03_CONFLICTING


def test_conflicting_candidate_evidence_is_preserved_never_selected(stack):
    outcome = _recorded(stack, parts=ambiguous_number_pages(),
                        label="ir-res-ambigevid")
    number_row = [r for r in outcome.role_rows
                  if r.role == "INVOICE_NUMBER"][0]
    assert number_row.candidate_count == 2
    assert len(number_row.field_seqs) == 2
    assert number_row.resolved_field_seq is None
    read = stack.norm.read_normalization(outcome.record.normalization_id)
    seqs = {f.field_seq for f in read.fields
            if f.source_field_name == "invoice.number"
            and f.status.value == "NORMALIZED"}
    assert set(number_row.field_seqs) == seqs


def test_no_binding_is_undetermined_not_a_guess(stack):
    _, projection = stack.build_valid_identity_state(label="ir-res-nobind")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, None)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.scope_reason == SCOPE_REASON_D03_UNDETERMINED
    assert outcome.role_rows == ()


def test_empty_binding_equals_no_binding(stack):
    _, projection = stack.build_valid_identity_state(label="ir-res-emptyb")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, {})
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.scope_reason == SCOPE_REASON_D03_UNDETERMINED
    assert outcome.record.binding_declaration_fingerprint == ""


# ---------------------------------------------------------------------------
# CAPTURE_SCOPED via the state gate (R1b — no value consumption)
# ---------------------------------------------------------------------------

def test_decisive_invalid_state_is_capture_scoped(stack):
    _, projection = decisive_invalid_state(stack, label="ir-res-decisive")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.scope_reason == SCOPE_REASON_S2_NOT_ATTEMPTED
    assert outcome.role_rows == ()


def test_tolerance_invalid_review_state_is_capture_scoped(stack):
    from ir_helpers import tolerance_invalid_state
    _, projection = tolerance_invalid_state(stack, label="ir-res-tol")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.scope_reason == SCOPE_REASON_S2_NOT_ATTEMPTED


def test_deferred_review_state_is_capture_scoped(stack):
    _, projection = deferred_state(stack, label="ir-res-def")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.scope_reason == SCOPE_REASON_S2_NOT_ATTEMPTED


def test_unresolved_review_state_is_capture_scoped(stack):
    _, projection = unresolved_state(stack, label="ir-res-unres")
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.scope_reason == SCOPE_REASON_S2_NOT_ATTEMPTED


def test_non_valid_state_never_reads_normalization_values(stack):
    class _SpyNorm:
        def __init__(self, inner):
            self._inner = inner
            self.read_calls = 0

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def read_normalization(self, nid):
            self.read_calls += 1
            return self._inner.read_normalization(nid)

    spy = _SpyNorm(stack.norm)
    stack.identity._normalization = spy
    try:
        _, projection = decisive_invalid_state(stack,
                                               label="ir-res-spy")
        outcome = stack.identity.resolve(projection.record.domain_state_id,
                                         ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, IdentityResolutionRecorded)
        assert spy.read_calls == 0
    finally:
        stack.identity._normalization = spy._inner


# ---------------------------------------------------------------------------
# Request validation (V4 — binding is fail-closed, never repaired)
# ---------------------------------------------------------------------------

def test_partial_binding_refused(stack):
    _, projection = stack.build_valid_identity_state(label="ir-res-partial")
    bad = {"INVOICE_NUMBER": "invoice.number",
           "INVOICE_DATE": "invoice.date"}
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, bad)
    assert isinstance(outcome, IdentityRequestRefused), outcome
    assert "binding" in outcome.detail


def test_binding_with_unknown_role_refused(stack):
    _, projection = stack.build_valid_identity_state(label="ir-res-unkrole")
    bad = {"INVOICE_NUMBER": "invoice.number",
           "INVOICE_DATE": "invoice.date",
           "INVOICE_TOTAL": "total.net",
           "EXTRA_ROLE": "seller.vat"}
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, bad)
    assert isinstance(outcome, IdentityRequestRefused), outcome


def test_binding_with_duplicate_targets_refused(stack):
    _, projection = stack.build_valid_identity_state(label="ir-restarget")
    bad = {"INVOICE_NUMBER": "invoice.number",
           "INVOICE_DATE": "invoice.number",
           "INVOICE_TOTAL": "total.net"}
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, bad)
    assert isinstance(outcome, IdentityRequestRefused), outcome


def test_binding_with_non_string_target_refused(stack):
    _, projection = stack.build_valid_identity_state(label="ir-res-nonstr")
    bad = {"INVOICE_NUMBER": "invoice.number",
           "INVOICE_DATE": "invoice.date",
           "INVOICE_TOTAL": 42}
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, bad)
    assert isinstance(outcome, IdentityRequestRefused), outcome


def test_malformed_binding_leaves_zero_residue(stack):
    _, projection = stack.build_valid_identity_state(label="ir-res-resid")
    bad = {"INVOICE_NUMBER": "invoice.number"}
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, bad)
    assert isinstance(outcome, IdentityRequestRefused), outcome
    assert stack.identity_store.list_resolutions() == []


# ---------------------------------------------------------------------------
# Vocabulary sanity (frozen, verbatim)
# ---------------------------------------------------------------------------

def test_scope_reason_vocabulary_is_frozen_plus_one():
    assert CAPTURE_SCOPED_REASONS == (
        "d03-incomplete-document-identity",
        "d03-conflicting-document-identity",
        "d03-document-identity-undetermined",
        "s2-not-attempted-state-not-valid")


def test_origin_vocabulary_verbatim():
    assert ORIGINS == ("KANDOO_SALE", "HOLOO_CAPTURE",
                       "OTHER_POS_CAPTURE")
