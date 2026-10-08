"""WP-7.2 service tests — the F1–F6 ladder: WP-7.1 consumption (spy-proven),
refusal passthrough matrix with zero residue, F5 backfill determinism, the
exhaustive outcome mapping, queries, and the public read surface
(SPEC §2/§4/§6; OD-DF-C/D/E/G/H)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from df_helpers import (  # noqa: E402
    BINDING,
    REF_KEYS,
    IdentityDefiniteDuplicate,
    IdentityReadSuccess,
    IdentityReplay,
    IdentityResolutionRecorded,
    IdentityRequestRefused,
    FlowDuplicateRecognized,
    FlowIdentityEstablished,
    FlowInputIntegrityFailure,
    FlowReadRefused,
    FlowReadSuccess,
    FlowReprintRecognized,
    FlowRequestRefused,
    FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_KANDOO_SALE,
    ORIGIN_OTHER_POS_CAPTURE,
    decisive_invalid_state,
    tolerance_invalid_state,
    deferred_state,
    twin_pages,
    unique_ir_pages,
)


def _project(stack, nid, keys=None, ruleset_id="kandoo-ir-rules"):
    return stack.project(nid, keys or REF_KEYS, ruleset_id=ruleset_id,
                         ruleset_version="1")


# ---------------------------------------------------------------------------
# F1 — refusal passthrough with zero durable residue
# ---------------------------------------------------------------------------

def test_unknown_state_refused_without_any_durable_row(stack):
    outcome = stack.flows.handle("no-such-state", ORIGIN_HOLOO_CAPTURE,
                                 BINDING)
    assert isinstance(outcome, FlowRequestRefused)
    assert outcome.domain_state_id is None
    assert len(stack.flow_store.list_dispositions()) == 0
    assert len(stack.identity_store.list_resolutions()) == 0


def test_native_flow_origin_refused_verbatim(stack):
    nid, projection = stack.build_valid_identity_state(label="df-svc-native")
    outcome = stack.flows.handle(projection.record.domain_state_id,
                                 ORIGIN_KANDOO_SALE, BINDING)
    assert isinstance(outcome, FlowRequestRefused)
    assert "native-flow origin" in outcome.detail
    assert len(stack.flow_store.list_dispositions()) == 0


def test_malformed_binding_refused_verbatim(stack):
    nid, projection = stack.build_valid_identity_state(label="df-svc-bind")
    state_id = projection.record.domain_state_id
    cases = (
        ({"INVOICE_NUMBER": "invoice.number"},
         "must declare exactly the three frozen D-02 roles"),
        ({"INVOICE_NUMBER": "invoice.number",
          "INVOICE_DATE": "invoice.date",
          "INVOICE_TOTAL": "invoice.date"},
         "must be bound to DISTINCT source field names"),
        ({"NUMBER": "invoice.number", "DATE": "invoice.date",
          "TOTAL": "total.net"},
         "must declare exactly the three frozen D-02 roles"),
    )
    for bad, expected in cases:
        outcome = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, bad)
        assert isinstance(outcome, FlowRequestRefused)
        assert expected in outcome.detail
    assert len(stack.flow_store.list_dispositions()) == 0


def test_non_valid_state_is_established_capture_scoped_without_values(
        stack):
    """R1b semantics consumed at flow level: a DECISIVE INVALID state →
    CAPTURE_SCOPED resolution (s2-not-attempted) → IDENTITY_ESTABLISHED
    disposition with no fingerprint — and no duplicate claim ever."""
    nid, projection = decisive_invalid_state(
        stack, parts=unique_ir_pages(), label="df-svc-invalid")
    outcome = stack.flows.handle(projection.record.domain_state_id,
                                 ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, FlowIdentityEstablished)
    assert outcome.record.identity_scope == "CAPTURE_SCOPED"
    assert outcome.disposition.identity_fingerprint == ""
    assert outcome.disposition.original_resolution_id == ""


def test_tolerance_and_deferred_and_unresolved_states_map_established(
        stack):
    for builder, label in ((tolerance_invalid_state, "df-svc-tol"),
                           (deferred_state, "df-svc-def")):
        nid, projection = builder(stack, label=label)
        outcome = stack.flows.handle(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, FlowIdentityEstablished), label
        assert outcome.record.identity_scope == "CAPTURE_SCOPED", label


# ---------------------------------------------------------------------------
# Delegation proof — the flow layer consumes WP-7.1, never bypasses it
# ---------------------------------------------------------------------------

def test_flow_service_delegates_resolution_to_wp71_spy_proven(stack):
    """The flow layer's ONLY identity path is WP-7.1's resolve: the spy
    records the consumption; no identity decision happens without it."""
    calls = []
    inner = stack.identity

    class SpyIdentity:
        def __getattr__(self, name):
            return getattr(inner, name)

        def resolve(self, *a, **k):
            calls.append("resolve")
            return inner.resolve(*a, **k)

        def read_resolution(self, *a, **k):
            calls.append("read_resolution")
            return inner.read_resolution(*a, **k)

    stack.flows._identity = SpyIdentity()
    try:
        nid, projection = stack.build_valid_identity_state(label="df-svc-spy")
        calls.clear()
        outcome = stack.flows.handle(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, FlowIdentityEstablished)
        assert calls.count("resolve") == 1
        # the reprint path re-enters WP-7.1 (resolve → IdentityReplay) and
        # re-verifies the disposition's linked facts (read_resolution)
        calls.clear()
        reprint = stack.flows.handle(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(reprint, FlowReprintRecognized)
        assert calls.count("resolve") == 1
        assert calls.count("read_resolution") >= 1
    finally:
        stack.flows._identity = inner


def test_handle_is_idempotent_over_repeated_calls(stack):
    nid, projection = stack.build_valid_identity_state(label="df-svc-idem")
    state_id = projection.record.domain_state_id
    first = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(first, FlowIdentityEstablished)
    results = [stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
               for _ in range(4)]
    assert all(isinstance(r, FlowReprintRecognized) for r in results)
    assert all(r.disposition == first.disposition for r in results)
    assert len(stack.flow_store.list_dispositions()) == 1
    assert len(stack.identity_store.list_resolutions()) == 1


# ---------------------------------------------------------------------------
# F5 — first flow-layer sighting of pre-existing resolutions (backfill)
# ---------------------------------------------------------------------------

def test_backfill_for_a_plain_resolution_is_deterministic(stack):
    """A resolution committed while the flow layer was 'not deployed' is
    dispositioned at its first flow-layer sighting — with exactly the
    content a first sighting would have committed (OD-DF-E)."""
    nid, projection = stack.build_valid_identity_state(label="df-svc-bf1")
    state_id = projection.record.domain_state_id
    resolved = stack.identity.resolve(state_id, ORIGIN_HOLOO_CAPTURE,
                                      BINDING)
    assert isinstance(resolved, IdentityResolutionRecorded)
    assert len(stack.identity_store.list_resolutions()) == 1
    assert len(stack.flow_store.list_dispositions()) == 0

    outcome = stack.flows.handle(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, FlowReprintRecognized)
    assert len(stack.flow_store.list_dispositions()) == 1
    assert outcome.disposition.flow_outcome == "IDENTITY_ESTABLISHED"
    assert outcome.disposition.resolution_id \
        == resolved.record.resolution_id
    assert outcome.disposition.original_resolution_id == ""


def test_backfill_for_a_duplicate_resolution_is_duplicate_recognized(stack):
    """Same as above for the duplicate shape: the pre-existing resolution
    carries an observation → the derived disposition is
    DUPLICATE_RECOGNIZED with the observation's original."""
    first, _ = stack.establish(label="df-svc-bf2")
    twin_state_id, twin_observation, twin_record = None, None, None
    twin = stack.handle_new(parts=twin_pages(),
                            label="df-svc-bf2-twin")
    assert isinstance(twin, FlowDuplicateRecognized)
    twin_state_id = twin.record.domain_state_id
    twin_observation = twin.observation
    twin_record = twin.record
    # wipe the flow store only (TEST-ONLY reset — simulates pre-flow-layer
    # identity facts; the identity store stays untouched)
    import sqlite3
    conn = sqlite3.connect(str(stack.flows_db))
    try:
        conn.execute("DELETE FROM flow_dispositions")
        conn.commit()
    finally:
        conn.close()
    assert len(stack.flow_store.list_dispositions()) == 0

    outcome = stack.flows.handle(twin_state_id, ORIGIN_HOLOO_CAPTURE,
                                 BINDING)
    assert isinstance(outcome, FlowReprintRecognized)
    assert outcome.disposition.flow_outcome \
        == FLOW_OUTCOME_DUPLICATE_RECOGNIZED
    assert outcome.disposition.resolution_id == twin_record.resolution_id
    assert outcome.disposition.original_resolution_id \
        == first.record.resolution_id
    assert outcome.disposition.duplicate_observation_id \
        == twin_observation.observation_id


def test_read_disposition_by_unknown_ids_are_explicit_refusals(stack):
    assert isinstance(stack.flows.read_disposition("nope"), FlowReadRefused)
    assert isinstance(stack.flows.read_disposition_by_id("nope"),
                      FlowReadRefused)


def test_read_disposition_by_capture_returns_verified_view(stack):
    outcome, _ = stack.establish(label="df-svc-read")
    read = stack.flows.read_disposition(outcome.disposition.capture_s1)
    assert isinstance(read, FlowReadSuccess)
    assert read.disposition == outcome.disposition
    assert read.original_resolution is None
    assert read.observation is None


def test_issue_reports_surface_is_available(stack):
    stack.flows.handle("no-such-state", ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(stack.flows.issue_reports, list)
