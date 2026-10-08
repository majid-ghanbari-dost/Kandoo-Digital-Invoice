"""WP-7.2 duplicate-flow tests — D-03 definite duplicates at flow level:
the deterministic original, the durable duplicate register, the exact-only
boundary (Case F / whitespace), and the CAPTURE_SCOPED never-duplicate
discipline (SPEC §4 F3, §5, §6; dispatch axes)."""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from df_helpers import (  # noqa: E402
    BINDING,
    FlowDuplicateRecognized,
    FlowIdentityEstablished,
    FlowReadSuccess,
    FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
    FLOW_OUTCOME_IDENTITY_ESTABLISHED,
    ORIGIN_HOLOO_CAPTURE,
    BINDING_TOTAL_VIA_VAT,
    no_number_pages,
    unique_no_number_pages,
    one_char_diff_pages,
    third_order_pages,
    twin_pages,
    unique_ir_pages,
    whitespace_pages,
    no_whitespace_pages,
    absent_total_role_pages,
)


# ---------------------------------------------------------------------------
# F3 — definite duplicates point at ONE deterministic original
# ---------------------------------------------------------------------------

def test_twin_capture_is_duplicate_recognized_pointing_at_the_original(
        stack):
    first, _ = stack.establish(label="df-dup-b1")
    assert isinstance(first, FlowIdentityEstablished)

    twin = stack.handle_new(parts=twin_pages(), label="df-dup-b1-twin")
    assert isinstance(twin, FlowDuplicateRecognized)
    assert twin.disposition.flow_outcome == FLOW_OUTCOME_DUPLICATE_RECOGNIZED
    assert twin.disposition.original_resolution_id \
        == first.record.resolution_id
    assert twin.disposition.duplicate_observation_id \
        == twin.observation.observation_id
    assert twin.disposition.identity_fingerprint \
        == first.record.identity_fingerprint
    assert twin.disposition.capture_s1 != first.disposition.capture_s1
    # two dispositions, ONE document identity (the original untouched)
    assert len(stack.flow_store.list_dispositions()) == 2
    assert len(stack.identity_store.list_resolutions()) == 2


def test_third_order_capture_resolves_to_the_same_original(stack):
    first, _ = stack.establish(label="df-dup-b2")
    twin = stack.handle_new(parts=twin_pages(), label="df-dup-b2-twin")
    third = stack.handle_new(parts=third_order_pages(),
                             label="df-dup-b2-third")
    assert isinstance(third, FlowDuplicateRecognized)
    assert third.disposition.original_resolution_id \
        == first.record.resolution_id
    assert twin.disposition.original_resolution_id \
        == first.record.resolution_id
    register = stack.flows.duplicates_of(first.record.resolution_id)
    assert len(register) == 2
    assert {d.disposition_id for d in register} == {
        twin.disposition.disposition_id, third.disposition.disposition_id}


def test_duplicate_disposition_read_reverifies_original_and_observation(
        stack):
    first, _ = stack.establish(label="df-dup-b3")
    twin = stack.handle_new(parts=twin_pages(), label="df-dup-b3-twin")
    read = stack.flows.read_disposition_by_id(
        twin.disposition.disposition_id)
    assert isinstance(read, FlowReadSuccess)
    assert read.disposition == twin.disposition
    assert read.original_resolution.resolution_id \
        == first.record.resolution_id
    assert read.observation.observation_id \
        == twin.disposition.duplicate_observation_id
    assert read.record.resolution_id == twin.record.resolution_id


def test_duplicates_of_an_unchallenged_original_is_empty(stack):
    stack.establish(label="df-dup-empty")
    other = stack.handle_new(label="df-dup-empty2")
    assert isinstance(other, FlowIdentityEstablished)
    assert stack.flows.duplicates_of(other.record.resolution_id) == []


# ---------------------------------------------------------------------------
# Exact-only boundary — one character / whitespace / changed values are NOT
# duplicates (Case F + the frozen canonical-serialization boundary)
# ---------------------------------------------------------------------------

def test_one_character_difference_is_established_never_duplicate(stack):
    first, _ = stack.establish(label="df-dup-f1")
    changed = stack.handle_new(parts=one_char_diff_pages(),
                               label="df-dup-f1-changed")
    assert isinstance(changed, FlowIdentityEstablished)
    assert changed.disposition.flow_outcome \
        == FLOW_OUTCOME_IDENTITY_ESTABLISHED
    assert changed.record.identity_fingerprint \
        != first.record.identity_fingerprint
    assert stack.flows.duplicates_of(first.record.resolution_id) == []


def test_whitespace_boundary_follows_the_frozen_normalization(stack):
    """The frozen normalization owns value canonicalization: trailing
    whitespace pages and clean pages with the same canonical values are the
    SAME exact identity at flow level (the fingerprint rides the verified
    WP-4.1 canonical values — never raw bytes)."""
    ws, _ = stack.establish(parts=whitespace_pages(), label="df-dup-ws")
    clean = stack.handle_new(parts=no_whitespace_pages(),
                             label="df-dup-ws-clean")
    assert isinstance(ws, FlowIdentityEstablished)
    assert isinstance(clean, FlowDuplicateRecognized)
    assert clean.disposition.original_resolution_id \
        == ws.record.resolution_id


def test_fuzzy_equivalence_is_impossible_by_construction(stack):
    """No similarity scoring exists: two identities either match exactly
    (fingerprint equality) or they do not — there is no third outcome and
    no partial match surface."""
    a, _ = stack.establish(label="df-dup-fuzzy-a")
    b = stack.handle_new(label="df-dup-fuzzy-b")
    assert isinstance(b, FlowIdentityEstablished)
    assert a.record.identity_fingerprint != b.record.identity_fingerprint
    assert stack.flows.duplicates_of(a.record.resolution_id) == []
    assert stack.flows.duplicates_of(b.record.resolution_id) == []


# ---------------------------------------------------------------------------
# CAPTURE_SCOPED captures — never duplicates, never guessed (Case D/E)
# ---------------------------------------------------------------------------

def test_incomplete_identity_capture_is_established_capture_scoped(stack):
    """invoice.number empty → the role has no usable value → CAPTURE_SCOPED;
    the flow disposition is IDENTITY_ESTABLISHED with NO fingerprint and NO
    duplicate claim (D-03: only capture-level dedup is guaranteed)."""
    outcome = stack.handle_new(parts=no_number_pages(), label="df-dup-d1")
    assert isinstance(outcome, FlowIdentityEstablished)
    assert outcome.record.identity_scope == "CAPTURE_SCOPED"
    assert outcome.disposition.identity_fingerprint == ""
    assert outcome.disposition.flow_outcome \
        == FLOW_OUTCOME_IDENTITY_ESTABLISHED
    assert outcome.disposition.original_resolution_id == ""


def test_absent_total_role_is_established_never_duplicate(stack):
    outcome = stack.handle_new(parts=absent_total_role_pages(),
                               label="df-dup-d2",
                               binding=BINDING_TOTAL_VIA_VAT)
    assert isinstance(outcome, FlowIdentityEstablished)
    assert outcome.record.identity_scope == "CAPTURE_SCOPED"


def test_two_capture_scoped_captures_are_never_duplicates(stack):
    """Two CAPTURE_SCOPED captures have NO document identity — a duplicate
    claim between them is impossible and MUST NOT be invented (D-03)."""
    a = stack.handle_new(parts=unique_no_number_pages(),
                         label="df-dup-cs-a")
    b = stack.handle_new(parts=unique_no_number_pages(),
                         label="df-dup-cs-b")
    assert isinstance(a, FlowIdentityEstablished)
    assert isinstance(b, FlowIdentityEstablished)
    assert stack.flows.duplicates_of(a.record.resolution_id) == []
    assert stack.flows.duplicates_of(b.record.resolution_id) == []
