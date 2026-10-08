"""Provenance preservation / whole-chain traceability tests — WP-5.2
(SPEC-WP52-VSM §10/§13).

The chain: P5.2 outcome → P5.1 validation records (their OWN whole-chain walks,
including WP-4.2 sub-chains) → normalization → extraction → binding →
Document/Page/span → Capture S1. Every link re-verified inside one call; no
chain is cut or replaced.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import sqlite3  # noqa: E402

from validation_domain import (  # noqa: E402
    DomainStateTraceIntegrityFailure,
    DomainStateTraceRefused,
    DomainStateTraceSuccess,
)

from vsm_helpers import (  # noqa: E402
    PAGE_MISSING_TAX,
    PAGE_OK,
    R_TOLERANCE,
)

REF_KEYS_FULL = [("kandoo-val-total-net-present", "1"),
                 ("kandoo-val-total-gross-consistency", "1"),
                 ("kandoo-val-total-gross-tolerance", "1"),
                 ("kandoo-val-total-gross-rounded", "1")]


class TestWholeChainTrace:
    def test_valid_state_traces_to_capture_s1(self, stack):
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS_FULL)
        walk = stack.vsm.trace_domain_state(projected.record.domain_state_id)
        assert isinstance(walk, DomainStateTraceSuccess)
        text = "\n".join(walk.chain)
        assert walk.chain[0].startswith("domain_state: VALID/CLEAR")
        assert "capture: OK" in text
        assert "normalization: OK" in text
        assert "extraction: OK" in text
        assert "binding: OK" in text
        assert "document: OK" in text
        # every consumed P5.1 record contributes its whole-chain sub-walk
        assert text.count("WP-5.1 whole-chain re-verified in this walk") == 4

    def test_unresolved_state_traces_to_capture_s1(self, stack):
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")])
        walk = stack.vsm.trace_domain_state(projected.record.domain_state_id)
        assert isinstance(walk, DomainStateTraceSuccess)
        text = "\n".join(walk.chain)
        assert walk.chain[0].startswith("domain_state: UNRESOLVED/REVIEW")
        assert "capture: OK" in text
        assert "unresolved=2" in text

    def test_trace_is_repeatable_without_side_effects(self, stack):
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS_FULL)
        state_id = projected.record.domain_state_id
        first = stack.vsm.trace_domain_state(state_id)
        second = stack.vsm.trace_domain_state(state_id)
        assert isinstance(first, DomainStateTraceSuccess)
        assert isinstance(second, DomainStateTraceSuccess)
        assert first.chain == second.chain
        # repeatable replay: the projection still reads clean
        read = stack.vsm.read_domain_state(state_id)
        assert type(read).__name__ == "DomainStateReadSuccess"

    def test_derived_field_projection_inherits_p42_provenance(self, stack):
        """total.gross is DERIVED — its P5.1 sub-walk consumes the WP-4.2 chain
        (provenance consumed, never bypassed)."""
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS_FULL)
        fields = {r.field_name: r for r in projected.field_projections}
        assert fields["total.gross"].origin_relayed == "DERIVED"
        walk = stack.vsm.trace_domain_state(projected.record.domain_state_id)
        assert isinstance(walk, DomainStateTraceSuccess)


class TestChainBreakDetection:
    def test_tampered_upstream_breaks_the_walk(self, stack):
        """Tamper the DOCUMENT page content → the WP-5.1 sub-chain fails → the
        domain-state walk reports the validation link."""
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS_FULL)
        state_id = projected.record.domain_state_id

        # tamper a page in the reconstruction store (outside any API)
        conn = sqlite3.connect(str(stack.recon_db))
        try:
            conn.execute("UPDATE document_pages SET content = ?",
                         (b"tampered bytes",))
            conn.commit()
        finally:
            conn.close()

        walk = stack.vsm.trace_domain_state(state_id)
        assert isinstance(walk, DomainStateTraceIntegrityFailure)
        assert walk.link in ("validation", "normalization", "extraction",
                             "binding", "document")

    def test_capture_linkage_drift_detected(self, stack):
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS_FULL)
        state_id = projected.record.domain_state_id
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            conn.execute("UPDATE domain_state_records SET capture_s1 = '0' * 64 "
                         "WHERE domain_state_id = ?", (state_id,))
            conn.commit()
        finally:
            conn.close()
        walk = stack.vsm.trace_domain_state(state_id)
        assert isinstance(walk, DomainStateTraceIntegrityFailure)

    def test_unknown_state_trace_refused(self, stack):
        outcome = stack.vsm.trace_domain_state("ghost")
        assert isinstance(outcome, DomainStateTraceRefused)


class TestPointerDiscipline:
    def test_no_pipeline_values_in_domain_tables(self, stack):
        """Pointer pattern: the P5.2 store carries NO normalized/derived VALUES
        — only ids, fingerprints, names, counts, and statuses."""
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        stack.project(nid, REF_KEYS_FULL)
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            rows = conn.execute(
                "SELECT state_detail, state_reason FROM domain_state_records"
            ).fetchall()
            for detail, _ in rows:
                assert "1000.00" not in detail     # corpus value never copied
                assert "1080" not in detail
            field_rows = conn.execute(
                "SELECT field_name, projection_status, origin_relayed, "
                "source_field_seq, source_derivation_id FROM domain_state_fields"
            ).fetchall()
            for name, status, origin, seq, deriv in field_rows:
                assert name in ("total.net", "total.gross", "tax.amount")
                assert status in ("RESOLVED", "UNRESOLVED")
        finally:
            conn.close()

    def test_validation_refs_point_at_real_p51_records(self, stack):
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        projected = stack.project(nid, REF_KEYS_FULL)
        for ref in projected.validation_refs:
            read = stack.val.read_validation(ref.validation_id)
            assert type(read).__name__ == "ValidationReadSuccess"
            assert read.record.rule_id == ref.rule_id
            assert read.record.rule_fingerprint == ref.rule_fingerprint
