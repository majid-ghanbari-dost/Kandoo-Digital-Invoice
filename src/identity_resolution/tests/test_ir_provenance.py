"""WP-7.1 provenance tests — whole-chain verification consumed-not-bypassed,
pointer discipline, broken-provenance fail-closed, evidence re-join
(SPEC §9; dispatch §12 tampered/broken provenance axes)."""
import sqlite3
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ir_helpers import (  # noqa: E402
    BINDING,
    BINDING_TOTAL_VIA_VAT,
    IdentityInputIntegrityFailure,
    IdentityResolutionRecorded,
    ORIGIN_HOLOO_CAPTURE,
    absent_total_role_pages,
    ambiguous_number_pages,
    unique_ir_pages,
)

from identity_resolution import (  # noqa: E402
    IDENTITY_SCOPE_CAPTURE_SCOPED,
    IDENTITY_SCOPE_S2,
)


def _resolve(stack, state_id, binding=None):
    return stack.identity.resolve(state_id, ORIGIN_HOLOO_CAPTURE,
                                  BINDING if binding is None else binding)


# ---------------------------------------------------------------------------
# The chain — every resolution re-verifies the whole upstream chain first
# ---------------------------------------------------------------------------

def test_resolve_consumes_the_whole_chain_walk(stack):
    """Spy: trace_domain_state runs on EVERY resolve — provenance is
    verified, never assumed."""
    calls = {"trace": 0}
    inner = stack.vsm

    class SpyVSM:
        def __getattr__(self, name):
            return getattr(inner, name)

        def trace_domain_state(self, state_id):
            calls["trace"] += 1
            return inner.trace_domain_state(state_id)

    stack.identity._domain = SpyVSM()
    try:
        _, projection = stack.build_valid_identity_state(label="ir-prov-spy")
        outcome = _resolve(stack, projection.record.domain_state_id)
        assert isinstance(outcome, IdentityResolutionRecorded)
        assert calls["trace"] == 1
    finally:
        stack.identity._domain = inner


def test_resolution_anchors_equal_the_verified_state(stack):
    _, projection = stack.build_valid_identity_state(label="ir-prov-anchor")
    head = stack.vsm.read_domain_state(projection.record.domain_state_id)
    outcome = _resolve(stack, projection.record.domain_state_id)
    r = outcome.record
    assert r.capture_s1 == head.record.capture_s1
    assert r.capture_id == head.record.capture_id
    assert r.document_id == head.record.document_id
    assert r.extraction_id == head.record.extraction_id
    assert r.normalization_id == head.record.normalization_id
    assert r.domain_state_id == head.record.domain_state_id


def test_provenance_anchors_survive_on_capture_scoped_outcomes(stack):
    _, projection = stack.build_valid_identity_state(
        parts=absent_total_role_pages(), label="ir-prov-cs")
    outcome = _resolve(stack, projection.record.domain_state_id,
                       binding=BINDING_TOTAL_VIA_VAT)
    assert isinstance(outcome, IdentityResolutionRecorded)
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    r = outcome.record
    assert all([r.capture_s1, r.capture_id, r.document_id, r.extraction_id,
                r.normalization_id, r.domain_state_id])


# ---------------------------------------------------------------------------
# Broken provenance — FAIL CLOSED, zero residue
# ---------------------------------------------------------------------------

def test_tampered_upstream_record_breaks_the_resolution(stack):
    """A tampered normalization record breaks the P5.2 whole-chain walk →
    the resolution fails closed with zero durable residue."""
    _, projection = stack.build_valid_identity_state(label="ir-prov-broken")
    conn = sqlite3.connect(str(stack.norm_db))
    try:
        conn.execute("UPDATE normalization_records SET record_fingerprint "
                     "= '0' WHERE normalization_id = ?",
                     (projection.record.normalization_id,))
        conn.commit()
    finally:
        conn.close()
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityInputIntegrityFailure), outcome
    assert "provenance" in outcome.reason or "verification" in \
        outcome.reason
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM identity_resolutions").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_tampered_state_record_breaks_v1(stack):
    """A tampered domain-state row fails the verified READ itself (V1) —
    no resolution, explicit integrity failure."""
    _, projection = stack.build_valid_identity_state(label="ir-prov-v1")
    conn = sqlite3.connect(str(stack.vsm_db))
    try:
        conn.execute("UPDATE domain_state_records SET record_fingerprint "
                     "= '0' WHERE domain_state_id = ?",
                     (projection.record.domain_state_id,))
        conn.commit()
    finally:
        conn.close()
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityInputIntegrityFailure), outcome


def test_upstream_tamper_after_resolution_blocks_even_the_replay(stack):
    """Fail-closed ordering: V1/V2 run BEFORE the S1 replay recognition — a
    chain broken AFTER a resolution never replays from it."""
    _, projection = stack.build_valid_identity_state(label="ir-prov-late")
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityResolutionRecorded)
    conn = sqlite3.connect(str(stack.norm_db))
    try:
        conn.execute("UPDATE normalization_records SET record_fingerprint "
                     "= '0' WHERE normalization_id = ?",
                     (projection.record.normalization_id,))
        conn.commit()
    finally:
        conn.close()
    outcome2 = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome2, IdentityInputIntegrityFailure), outcome2


def test_refused_resolution_of_unknown_state_has_zero_residue(stack):
    outcome = _resolve(stack, "no-such-state")
    assert type(outcome).__name__ == "IdentityRequestRefused", outcome
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM identity_resolutions").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


# ---------------------------------------------------------------------------
# Pointer discipline — no raw pipeline values are ever stored
# ---------------------------------------------------------------------------

def test_no_raw_pipeline_values_are_stored(stack):
    parts = unique_ir_pages()
    _, projection = stack.build_valid_identity_state(parts=parts,
                                                     label="ir-prov-ptr")
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert isinstance(outcome, IdentityResolutionRecorded)
    number = parts[0].split(b"=")[1].split(b"\n")[0].decode()
    conn = sqlite3.connect(str(stack.identity_db))
    try:
        dumped = ""
        for (table,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"):
            for row in conn.execute(f"SELECT * FROM {table}"):
                dumped += " | ".join(str(v) for v in row)
    finally:
        conn.close()
    for secret in (number, "2026-10-08", "1000.00"):
        assert secret not in dumped, secret


def test_resolved_pointers_rejoin_the_verified_read(stack):
    parts = unique_ir_pages()
    _, projection = stack.build_valid_identity_state(parts=parts,
                                                     label="ir-prov-rejoin")
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert outcome.record.identity_scope == IDENTITY_SCOPE_S2
    read = stack.norm.read_normalization(outcome.record.normalization_id)
    by_seq = {f.field_seq: f for f in read.fields}
    number = parts[0].split(b"=")[1].split(b"\n")[0].decode()
    expectations = {"INVOICE_NUMBER": number,
                    "INVOICE_DATE": "2026-10-08",
                    "INVOICE_TOTAL": "1000.00"}
    for row in outcome.role_rows:
        field = by_seq[row.resolved_field_seq]
        assert field.normalized_value == expectations[row.role]
        assert field.source_field_name == row.source_field_name
        assert field.status.value == "NORMALIZED"


def test_candidate_evidence_points_at_real_rows(stack):
    """Ambiguity evidence is re-joinable: the preserved field_seqs point at
    REAL NORMALIZED rows of the verified read."""
    _, projection = stack.build_valid_identity_state(
        parts=ambiguous_number_pages(), label="ir-prov-ambig")
    outcome = _resolve(stack, projection.record.domain_state_id)
    assert outcome.record.identity_scope == IDENTITY_SCOPE_CAPTURE_SCOPED
    read = stack.norm.read_normalization(outcome.record.normalization_id)
    for row in outcome.role_rows:
        if row.role == "INVOICE_NUMBER":
            assert row.candidate_count == 2
            observed = {f.normalized_value for f in read.fields
                        if f.field_seq in row.field_seqs}
            assert observed == {"INV-AMBIG-A", "INV-AMBIG-B"}


def test_normalization_id_anchors_the_value_read(stack):
    """The record's normalization_id re-joins the verified read — the only
    sanctioned value path (never a copy, never a cache)."""
    parts = unique_ir_pages()
    _, projection = stack.build_valid_identity_state(parts=parts,
                                                     label="ir-prov-nid")
    outcome = _resolve(stack, projection.record.domain_state_id)
    read = stack.norm.read_normalization(outcome.record.normalization_id)
    assert type(read).__name__ == "NormalizationReadSuccess"
    assert {f.source_field_name for f in read.fields} >= \
        {"invoice.number", "invoice.date", "total.net"}
