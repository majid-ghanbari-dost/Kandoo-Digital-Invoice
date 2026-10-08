"""Service-level integration, determinism, and refusal tests — WP-5.2
(SPEC-WP52-VSM §2/§7/§8/§13).

Integration with P5.1 over REAL frozen-layer traffic, content determinism
(honoring D-03 via reordered-bytes corpora), replay semantics, and the explicit
refusal matrix (integrity / unavailable / unknown / drift).
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation import ValidationCompleted  # noqa: E402
from validation import ValidationRule as _VRule  # noqa: E402  (type reference)
from validation_domain import (  # noqa: E402
    DomainStateReadRefused,
    DomainStateReadSuccess,
    DomainStateSourceIntegrityFailure,
    DomainStateSourceRefused,
)

from vsm_helpers import (  # noqa: E402
    PAGE_ALT_OK,
    PAGE_OK,
    R_CONSIST,
    R_PRESENT,
    R_ROUNDED,
    R_TOLERANCE,
    REF_KEYS,
)


def _content_fingerprint(record):
    """Content scalars only — identity bookkeeping (ids, created_at) excluded
    per SPEC §7."""
    return (
        record.normalization_id, record.domain_state, record.disposition,
        record.state_reason, record.state_detail, record.ruleset_id,
        record.ruleset_version, record.ruleset_fingerprint,
        record.rule_count, record.valid_count, record.invalid_count,
        record.deferred_count, record.unresolved_count,
    )


class TestDeterminism:
    def test_reordered_bytes_corpus_projects_identical_content(self, stack):
        """D-03-honoring determinism probe: byte-identical content cannot be
        captured twice, so content-determinism is proven via a reordered-bytes
        corpus (distinct capture, identical NORMALIZED content) → identical
        projection content."""
        nid_a = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid_a)
        a = stack.project(nid_a, REF_KEYS).record

        nid_b = stack.build_derived(PAGE_ALT_OK, label="vsm-det-2")
        stack.validate_all_reference(nid_b)
        b = stack.project(nid_b, REF_KEYS,
                          ruleset_id="kandoo-vsm-rules").record
        assert nid_a != nid_b
        assert a.domain_state == b.domain_state == "VALID"
        assert a.disposition == b.disposition == "CLEAR"
        assert a.state_reason == b.state_reason
        assert a.state_detail == b.state_detail
        assert a.ruleset_fingerprint == b.ruleset_fingerprint
        assert a.rule_count == b.rule_count
        assert a.unresolved_count == b.unresolved_count == 0

    def test_projection_order_is_declared_order(self, stack):
        """A different declared order is a DIFFERENT ruleset identity — both
        projections succeed independently with different fingerprints."""
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        forward = stack.project(nid, REF_KEYS,
                                ruleset_id="kandoo-vsm-order-f")
        backward = stack.project(nid, list(reversed(REF_KEYS)),
                                 ruleset_id="kandoo-vsm-order-b")
        assert forward.record.ruleset_fingerprint != \
            backward.record.ruleset_fingerprint
        assert forward.record.domain_state == backward.record.domain_state

    def test_replay_is_explicit_not_silent(self, stack):
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        first = stack.project(nid, REF_KEYS)
        replay = stack.vsm.project_domain_state(nid, "kandoo-vsm-rules", "1",
                                                list(REF_KEYS))
        assert type(replay).__name__ == "DomainStateAlreadyExists"
        assert replay.domain_state_id == first.record.domain_state_id


class TestIntegrationWithP51:
    def test_consumes_real_p51_records_with_derived_inputs(self, stack):
        """The full P5.1 surface: R1 presence + R1 consistency over a DERIVED
        target + R2 tolerance/rounded — consumed verbatim into the projection."""
        nid = stack.build_derived(PAGE_OK)
        records = stack.validate_all_reference(nid)
        assert {r.outcome for r in records} == {"VALID"}
        projected = stack.project(nid, REF_KEYS)
        ref_outcomes = {ref.rule_id: (ref.outcome, ref.outcome_reason)
                        for ref in projected.validation_refs}
        assert ref_outcomes[R_CONSIST] == ("VALID", "exact-match")
        assert ref_outcomes[R_TOLERANCE] == ("VALID", "exact-match")
        assert ref_outcomes[R_ROUNDED] == ("VALID", "exact-match")
        for ref in projected.validation_refs:
            assert ref.rule_kind in ("R1", "R2")
            assert len(ref.rule_fingerprint) == 64

    def test_only_verified_p51_reads_are_used(self, stack, monkeypatch):
        """The service MUST go through the P5.1 verified read — prove it by
        watching that read_validation is invoked for every record."""
        nid = stack.build_derived()
        stack.validate_all_reference(nid)
        calls = []
        original = stack.val.read_validation

        def spy(vid):
            calls.append(vid)
            return original(vid)

        monkeypatch.setattr(stack.val, "read_validation", spy)
        stack.project(nid, REF_KEYS)
        assert len(calls) == 4

    def test_engine_independence(self, make_stack):
        """Identical NORMALIZED semantics project identically regardless of
        which engine produced them (no engine module is imported by this layer;
        corpora differ in bytes to honor D-03 on the shared capture store)."""
        from val_helpers import AltEngine
        s1 = make_stack()
        try:
            nid_ref = s1.build_extract_normalize(
                PAGE_OK, engine_id="reference-delimited-v1",
                label="vsm-eng-1")
            s1.deriv.derive(nid_ref, "kandoo-der-total-gross-from-net-tax", "1")
            s1.validate_all_reference(nid_ref)
            a = s1.project(nid_ref, REF_KEYS).record
        finally:
            s1.close()

        s2 = make_stack(engines={"alt-vsm-engine": AltEngine()})
        try:
            nid_alt = s2.build_extract_normalize(
                PAGE_ALT_OK, engine_id="alt-vsm-engine", label="vsm-eng-2")
            s2.deriv.derive(nid_alt, "kandoo-der-total-gross-from-net-tax", "1")
            s2.validate_all_reference(nid_alt)
            b = s2.project(nid_alt, REF_KEYS).record
            assert a.domain_state == b.domain_state
            assert a.state_reason == b.state_reason
            assert a.state_detail == b.state_detail
            assert a.ruleset_fingerprint == b.ruleset_fingerprint
        finally:
            s2.close()

    def test_derived_target_without_derivation_defers_not_fabricates(self, stack):
        """P5.2 never triggers derivation: a ruleset whose DERIVED target has no
        derivation record refuses nothing — it projects honestly (UNRESOLVED
        field + DEFERRED rule)."""
        nid = stack.build_normalization(PAGE_ALT_OK)   # NO derivation run
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-noderive")
        assert projected.record.domain_state == "UNRESOLVED"
        fields = {r.field_name: r for r in projected.field_projections}
        assert fields["total.gross"].projection_status == "UNRESOLVED"


class TestRefusals:
    def test_unknown_normalization_refused(self, stack):
        outcome = stack.vsm.project_domain_state(
            "ghost", "rs", "1", [(R_PRESENT, "1")])
        assert isinstance(outcome, DomainStateSourceRefused)
        assert "no such normalization" in outcome.detail

    def test_unknown_state_read_refused(self, stack):
        outcome = stack.vsm.read_domain_state("ghost")
        assert isinstance(outcome, DomainStateReadRefused)

    def test_declaration_drift_is_integrity_failure(self, make_stack):
        """A registry whose declaration fingerprint differs from the fingerprint
        anchored in the P5.1 record = declaration drift → integrity failure.
        The second stack reopens the SAME stores with a swapped declaration
        under the same (rule_id, version)."""
        from val_helpers import reference_rules, swapped_rule
        s1 = make_stack()
        try:
            nid = s1.build_derived()
            outcome = s1.val.validate(nid, R_CONSIST, "1")
            assert isinstance(outcome, ValidationCompleted)
        finally:
            s1.close()

        tampered_map = {**reference_rules(),
                        (R_CONSIST, "1"): swapped_rule("1")}
        s2 = make_stack(rules=tampered_map)
        try:
            outcome = s2.vsm.project_domain_state(
                nid, "kandoo-vsm-drift", "1", [(R_CONSIST, "1")])
            assert isinstance(outcome, DomainStateSourceIntegrityFailure)
            assert "drift" in outcome.reason
        finally:
            s2.close()

    def test_projection_refused_after_p51_integrity_break(self, make_stack):
        """If a P5.1 record fails VOR (tampered), any projection refuses with an
        integrity failure — no state is ever projected from broken sources."""
        s1 = make_stack()
        try:
            nid = s1.build_derived()
            outcome = s1.val.validate(nid, R_PRESENT, "1")
            assert isinstance(outcome, ValidationCompleted)
        finally:
            s1.close()

        # tamper with the P5.1 store content directly (outside the API — there
        # is no UPDATE/DELETE path in any layer)
        import sqlite3
        db_path = None
        s2 = make_stack()
        try:
            db_path = str(s2.val_db)
        finally:
            s2.close()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE validation_records SET outcome_detail = 'tampered' "
            "WHERE normalization_id = ?", (nid,))
        conn.commit()
        conn.close()

        s3 = make_stack()
        try:
            outcome = s3.vsm.project_domain_state(
                nid, "kandoo-vsm-after", "1", [(R_PRESENT, "1")])
            assert isinstance(outcome, DomainStateSourceIntegrityFailure)
            assert "verified read" in outcome.reason
        finally:
            s3.close()
