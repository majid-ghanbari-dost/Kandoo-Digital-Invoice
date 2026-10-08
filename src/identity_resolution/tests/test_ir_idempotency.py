"""WP-7.1 idempotency tests — dispatch §11 cases A–F, replay recognition,
declaration-drift refusal, restart durability of the replay path, and the
canonical-serialization boundary (SPEC §4 R0/R2, §6; D-02/D-03)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ir_helpers import (  # noqa: E402
    BINDING,
    REF_KEYS,
    IdentityDefiniteDuplicate,
    IdentityReplay,
    IdentityRequestRefused,
    IdentityResolutionRecorded,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
    no_number_pages,
    one_char_diff_pages,
    twin_pages,
    third_order_pages,
    unique_ir_pages,
    whitespace_pages,
    no_whitespace_pages,
)

from identity_resolution import (  # noqa: E402
    IDENTITY_SCOPE_CAPTURE_SCOPED,
    IDENTITY_SCOPE_S2,
)


def _resolve(stack, state_id, origin=ORIGIN_HOLOO_CAPTURE, binding=None):
    return stack.identity.resolve(state_id, origin,
                                  BINDING if binding is None else binding)


# ---------------------------------------------------------------------------
# Case A — exact S1 replay: one identity, one durable resolution, zero
# duplicates
# ---------------------------------------------------------------------------

def test_case_a_same_state_resolved_twice_is_replay(stack):
    _, projection = stack.build_valid_identity_state(label="ir-idem-a1")
    first = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(first, IdentityResolutionRecorded)
    second = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(second, IdentityReplay)
    assert second.record == first.record
    assert second.role_rows == first.role_rows
    assert second.observation is None


def test_case_a_replay_commits_zero_rows(stack):
    _, projection = stack.build_valid_identity_state(label="ir-idem-a2")
    assert isinstance(_resolve(stack, projection.record.domain_state_id),
                      IdentityResolutionRecorded)
    before = len(stack.identity_store.list_resolutions())
    for _ in range(4):
        assert isinstance(_resolve(stack, projection.record.domain_state_id),
                          IdentityReplay)
    assert len(stack.identity_store.list_resolutions()) == before == 1


def test_case_a_replay_recognized_across_domain_states(stack):
    """The SAME capture re-projected under a new ruleset identity yields a
    DIFFERENT domain_state_id over the SAME capture_s1 — the S1 key still
    recognizes the replay (no second identity may be created)."""
    nid, projection = stack.build_valid_identity_state(label="ir-idem-a3")
    assert isinstance(_resolve(stack, projection.record.domain_state_id),
                      IdentityResolutionRecorded)
    reprojected = stack.project(nid, REF_KEYS,
                                ruleset_id="kandoo-ir-rules-b",
                                ruleset_version="1")
    assert (reprojected.record.domain_state_id
            != projection.record.domain_state_id)
    assert reprojected.record.capture_s1 == projection.record.capture_s1
    outcome = _resolve(stack, reprojected.record.domain_state_id)
    assert isinstance(outcome, IdentityReplay)


def test_case_a_replay_survives_process_restart(make_stack):
    stack = make_stack()
    try:
        _, projection = stack.build_valid_identity_state(label="ir-idem-a4")
        first = _resolve(stack, projection.record.domain_state_id)
        assert isinstance(first, IdentityResolutionRecorded)
    finally:
        stack.close()
    reopened = make_stack()
    try:
        outcome = _resolve(reopened, projection.record.domain_state_id)
        assert isinstance(outcome, IdentityReplay)
        assert outcome.record == first.record
        read = reopened.identity.read_resolution(first.record.resolution_id)
        assert type(read).__name__ == "IdentityReadSuccess"
    finally:
        reopened.close()


def test_replay_is_verified_not_blind(stack):
    """A replay is served only from a VERIFIED durable row (tampered row →
    fail closed, never a replay)."""
    _, projection = stack.build_valid_identity_state(label="ir-idem-tamper")
    first = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(first, IdentityResolutionRecorded)
    import sqlite3
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        conn.execute("UPDATE identity_resolutions SET declared_origin = "
                     "'OTHER_POS_CAPTURE' WHERE resolution_id = ?",
                     (first.record.resolution_id,))
        conn.commit()
    finally:
        conn.close()
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert type(outcome).__name__ == "IdentityInputIntegrityFailure"


# ---------------------------------------------------------------------------
# Case B — same exact S2 document, different captures → definite duplicate,
# ONE document identity
# ---------------------------------------------------------------------------

def test_case_b_twin_capture_is_definite_duplicate(stack):
    _, first_projection = stack.build_valid_identity_state(
        label="ir-idem-b1")
    first = _resolve(stack, first_projection.record.domain_state_id)
    assert isinstance(first, IdentityResolutionRecorded)
    _, twin_projection = stack.build_valid_identity_state(
        parts=twin_pages(), label="ir-idem-b1-twin")
    assert (twin_projection.record.capture_s1
            != first_projection.record.capture_s1)
    outcome = _resolve(stack, twin_projection.record.domain_state_id)
    assert isinstance(outcome, IdentityDefiniteDuplicate)
    assert (outcome.original_resolution.resolution_id
            == first.record.resolution_id)
    assert outcome.observation.identity_fingerprint \
        == first.record.identity_fingerprint
    assert outcome.observation.original_capture_s1 \
        == first.record.capture_s1
    assert outcome.observation.duplicate_capture_s1 \
        == twin_projection.record.capture_s1


def test_case_b_third_capture_also_duplicates_to_the_original(stack):
    _, p1 = stack.build_valid_identity_state(label="ir-idem-b2-1")
    assert isinstance(_resolve(stack, p1.record.domain_state_id),
                      IdentityResolutionRecorded)
    _, p2 = stack.build_valid_identity_state(parts=twin_pages(),
                                             label="ir-idem-b2-2")
    assert isinstance(_resolve(stack, p2.record.domain_state_id),
                      IdentityDefiniteDuplicate)
    _, p3 = stack.build_valid_identity_state(parts=third_order_pages(),
                                             label="ir-idem-b2-3")
    outcome = _resolve(stack, p3.record.domain_state_id)
    assert isinstance(outcome, IdentityDefiniteDuplicate)
    read = stack.identity.read_resolution(outcome.record.resolution_id)
    assert type(read).__name__ == "IdentityReadSuccess"
    assert read.observation is not None


def test_case_b_exactly_one_document_identity_exists(stack):
    _, p1 = stack.build_valid_identity_state(label="ir-idem-b3-1")
    _resolve(stack, p1.record.domain_state_id)
    _, p2 = stack.build_valid_identity_state(parts=twin_pages(),
                                             label="ir-idem-b3-2")
    _resolve(stack, p2.record.domain_state_id)
    _, p3 = stack.build_valid_identity_state(parts=third_order_pages(),
                                             label="ir-idem-b3-3")
    _resolve(stack, p3.record.domain_state_id)
    resolutions = stack.identity_store.list_resolutions()
    assert len(resolutions) == 3
    fingerprints = {r.identity_fingerprint for r in resolutions}
    assert len(fingerprints) == 1          # ONE document identity
    assert all(r.identity_scope == IDENTITY_SCOPE_S2 for r in resolutions)


def test_duplicate_observation_is_unique_per_resolution(stack):
    _, p1 = stack.build_valid_identity_state(label="ir-idem-b4-1")
    first = _resolve(stack, p1.record.domain_state_id)
    _, p2 = stack.build_valid_identity_state(parts=twin_pages(),
                                             label="ir-idem-b4-2")
    dup = _resolve(stack, p2.record.domain_state_id)
    assert isinstance(dup, IdentityDefiniteDuplicate)
    # a replay of the duplicate resolution returns the SAME observation,
    # never a second one (INV-IR-DUP:1)
    replay = _resolve(stack, p2.record.domain_state_id)
    assert isinstance(replay, IdentityReplay)
    assert replay.observation is not None
    assert replay.observation.resolution_id == dup.record.resolution_id
    assert (replay.observation.original_resolution_id
            == first.record.resolution_id)


# ---------------------------------------------------------------------------
# Case C / F — different document → different identity, never a duplicate
# ---------------------------------------------------------------------------

def test_case_c_different_document_resolves_to_different_identity(stack):
    _, p1 = stack.build_valid_identity_state(label="ir-idem-c1")
    first = _resolve(stack, p1.record.domain_state_id)
    _, p2 = stack.build_valid_identity_state(label="ir-idem-c2")
    second = _resolve(stack, p2.record.domain_state_id)
    assert isinstance(second, IdentityResolutionRecorded)
    assert (second.record.identity_fingerprint
            != first.record.identity_fingerprint)
    assert second.observation is None


def test_case_f_one_character_difference_is_not_a_duplicate(stack):
    """Case F: the exact value differs in ONE character → a DIFFERENT
    document identity — no fuzzy equivalence exists."""
    _, p1 = stack.build_valid_identity_state(label="ir-idem-f1")
    first = _resolve(stack, p1.record.domain_state_id)
    assert isinstance(first, IdentityResolutionRecorded)
    _, p2 = stack.build_valid_identity_state(parts=one_char_diff_pages(),
                                             label="ir-idem-f2")
    outcome = _resolve(stack, p2.record.domain_state_id)
    assert isinstance(outcome, IdentityResolutionRecorded), outcome
    assert (outcome.record.identity_fingerprint
            != first.record.identity_fingerprint)
    assert outcome.observation is None


def test_changed_origin_scopes_the_identity(stack):
    """The declared origin rides the frozen fingerprint — the same values
    under a different origin are a DIFFERENT identity (never compared)."""
    _, p1 = stack.build_valid_identity_state(label="ir-idem-o1")
    first = _resolve(stack, p1.record.domain_state_id,
                     origin=ORIGIN_HOLOO_CAPTURE)
    _, p2 = stack.build_valid_identity_state(parts=twin_pages(),
                                             label="ir-idem-o2")
    outcome = _resolve(stack, p2.record.domain_state_id,
                       origin=ORIGIN_OTHER_POS_CAPTURE)
    assert isinstance(outcome, IdentityResolutionRecorded), outcome
    assert (outcome.record.identity_fingerprint
            != first.record.identity_fingerprint)
    assert outcome.observation is None


# ---------------------------------------------------------------------------
# Case D / E — incomplete → CAPTURE_SCOPED; ambiguous → no auto-selection
# ---------------------------------------------------------------------------

def test_case_d_incomplete_s2_is_capture_scoped(stack):
    _, projection = stack.build_valid_identity_state(
        parts=no_number_pages(), label="ir-idem-d")
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    assert outcome.record.identity_fingerprint == ""
    # a CAPTURE_SCOPED outcome is durable and replayable like any other
    again = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(again, IdentityReplay)
    assert again.record == outcome.record


def test_case_e_ambiguous_candidates_never_selected(stack):
    _, p1 = stack.build_valid_identity_state(label="ir-idem-e1")
    _resolve(stack, p1.record.domain_state_id)
    _, p2 = stack.build_valid_identity_state(parts=one_char_diff_pages(),
                                             label="ir-idem-e2")
    _resolve(stack, p2.record.domain_state_id)
    from ir_helpers import ambiguous_number_pages
    _, p3 = stack.build_valid_identity_state(parts=ambiguous_number_pages(),
                                             label="ir-idem-e3")
    outcome = _resolve(stack, p3.record.domain_state_id)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    number_row = [r for r in outcome.role_rows
                  if r.role == "INVOICE_NUMBER"][0]
    assert number_row.candidate_count == 2
    assert number_row.resolved_field_seq is None


# ---------------------------------------------------------------------------
# Whitespace / canonical-serialization boundary (per the FROZEN contract)
# ---------------------------------------------------------------------------

def test_whitespace_boundary_follows_the_frozen_normalization(stack):
    """Raw bytes differ only by trailing whitespace inside one exact value;
    the frozen WP-4.1 normalization owns the canonical value, so the
    identities coincide (identity equality follows the frozen canonical
    values, never raw bytes)."""
    _, pws = stack.build_valid_identity_state(parts=whitespace_pages(),
                                              label="ir-idem-ws")
    ws = _resolve(stack, pws.record.domain_state_id)
    assert isinstance(ws, IdentityResolutionRecorded)
    _, pnws = stack.build_valid_identity_state(parts=no_whitespace_pages(),
                                               label="ir-idem-nws")
    nws = _resolve(stack, pnws.record.domain_state_id)
    assert type(nws).__name__ in ("IdentityResolutionRecorded",
                                  "IdentityDefiniteDuplicate")
    assert (nws.record.identity_fingerprint
            == ws.record.identity_fingerprint)


def test_declaration_fingerprint_is_order_independent_and_collision_safe():
    from capture import S1Service
    from identity_resolution import (binding_declaration_bytes,
                                     binding_declaration_fingerprint)
    s1 = S1Service()
    b1 = {"INVOICE_NUMBER": "invoice.number", "INVOICE_DATE": "invoice.date",
          "INVOICE_TOTAL": "total.net"}
    b2 = {"INVOICE_TOTAL": "total.net", "INVOICE_NUMBER": "invoice.number",
          "INVOICE_DATE": "invoice.date"}
    assert (binding_declaration_fingerprint(b1, s1)
            == binding_declaration_fingerprint(b2, s1))
    # naive concatenation would collide; the canonical serialization cannot
    c1 = {"INVOICE_NUMBER": "ab", "INVOICE_DATE": "c",
          "INVOICE_TOTAL": "t"}
    c2 = {"INVOICE_NUMBER": "a", "INVOICE_DATE": "bc",
          "INVOICE_TOTAL": "t"}
    assert (binding_declaration_fingerprint(c1, s1)
            != binding_declaration_fingerprint(c2, s1))
    assert binding_declaration_bytes(None) == b""
    assert binding_declaration_bytes({}) == b""
    assert (binding_declaration_fingerprint(None, s1) == "")


# ---------------------------------------------------------------------------
# Replay declaration drift — no silent reshape, no second identity
# ---------------------------------------------------------------------------

def test_replay_with_different_origin_is_refused_as_drift(stack):
    _, projection = stack.build_valid_identity_state(label="ir-idem-dr1")
    assert isinstance(_resolve(stack, projection.record.domain_state_id),
                      IdentityResolutionRecorded)
    outcome = _resolve(stack, projection.record.domain_state_id,
                       origin=ORIGIN_OTHER_POS_CAPTURE)
    assert isinstance(outcome, IdentityRequestRefused), outcome
    assert "drift" in outcome.detail or "different declared request" \
        in outcome.detail
    assert len(stack.identity_store.list_resolutions()) == 1


def test_replay_with_different_binding_is_refused_as_drift(stack):
    _, projection = stack.build_valid_identity_state(label="ir-idem-dr2")
    assert isinstance(_resolve(stack, projection.record.domain_state_id),
                      IdentityResolutionRecorded)
    other = {"INVOICE_NUMBER": "invoice.number",
             "INVOICE_DATE": "invoice.date",
             "INVOICE_TOTAL": "seller.vat"}
    outcome = _resolve(stack, projection.record.domain_state_id,
                       binding=other)
    assert isinstance(outcome, IdentityRequestRefused), outcome
    assert len(stack.identity_store.list_resolutions()) == 1


def test_drift_refusal_then_original_request_still_replays(stack):
    _, projection = stack.build_valid_identity_state(label="ir-idem-dr3")
    first = stack.identity.resolve(projection.record.domain_state_id,
                                   ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(first, IdentityResolutionRecorded)
    drifted = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, None)
    assert isinstance(drifted, IdentityRequestRefused)
    again = stack.identity.resolve(projection.record.domain_state_id,
                                   ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(again, IdentityReplay)
    assert again.record == first.record
