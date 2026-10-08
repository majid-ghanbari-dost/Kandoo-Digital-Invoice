"""Pure identity resolution engine — WP-7.1 MVP implementation.

Binding basis: SPEC-WP71-IDRES §4/§5 (OD-IR-B, OD-IR-C, OD-IR-D, OD-IR-G).
This module is PURE decision logic over verified inputs — no persistence, no
I/O, no clock, no randomness. The same verified inputs ALWAYS yield the same
resolution (content determinism; bookkeeping ids live elsewhere).

Reuse discipline (OD-IR-G — the frozen P6.1 primitives are the ONLY formula
source): the S2 triad criterion, the candidate counting, and the OD-G4
fingerprint serialization come from `canonicalization.identity.resolve_identity`
consumed VERBATIM — no second formula, no fork, no parallel vocabulary. What
this engine adds is exactly the WP-7.1 scope decision around that primitive:

  - the S1 leg is carried by the caller's verified state record (capture_s1)
    and never recomputed here;
  - a state that is not VALID/CLEAR yields CAPTURE_SCOPED
    (s2-not-attempted-state-not-valid) WITHOUT any value consumption — the
    resolver never even receives unverified values (OD-IR-C);
  - a VALID/CLEAR state delegates to the frozen primitive and maps the P6.1
    outcome onto the durable scope vocabulary (S2 | CAPTURE_SCOPED) —
    reason codes relayed verbatim (OD-IR-D).

The resolver NEVER sees unverified values, NEVER returns raw pipeline values
(counts + pointers only), and NEVER matches fuzzily.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence

from capture import S1Service

from canonicalization.identity import resolve_identity, validate_binding
from canonicalization.model import (
    IDENTITY_CLASS_CAPTURE_SCOPED,
    IDENTITY_CLASS_DETERMINISTIC,
    IDENTITY_SOURCE_S2,
)

from normalization.model import NormalizedField

from .model import (
    CAPTURE_PIPELINE_ORIGINS,
    DISPOSITION_CLEAR,
    IDENTITY_ROLES,
    IDENTITY_SCOPE_CAPTURE_SCOPED,
    IDENTITY_SCOPE_S2,
    ORIGINS,
    SCOPE_REASON_D03_CONFLICTING,
    SCOPE_REASON_D03_INCOMPLETE,
    SCOPE_REASON_D03_UNDETERMINED,
    SCOPE_REASON_S2_NOT_ATTEMPTED,
    STATE_VALID,
    RoleCandidateSpec,
    IdentityScopeDecision,
)

# P6.1 D-03 reason code → identical WP-7.1 scope-reason code (relayed
# verbatim, OD-IR-D — the vocabularies are the same frozen codes).
_P61_REASON_TO_SCOPE_REASON = {
    "d03-incomplete-document-identity": SCOPE_REASON_D03_INCOMPLETE,
    "d03-conflicting-document-identity": SCOPE_REASON_D03_CONFLICTING,
    "d03-document-identity-undetermined": SCOPE_REASON_D03_UNDETERMINED,
}


def validate_declared_origin(declared_origin: str) -> Optional[str]:
    """Validate the declared origin (SPEC §3 V3). Returns a refusal code or
    None when the origin is consumable. Frozen vocabulary verbatim; the
    native-flow origin is a category error on a P5.2-sourced request
    (AS-02 — same discipline as P6.1 V3/OD-G6)."""
    if declared_origin not in ORIGINS:
        return "origin-outside-frozen-vocabulary"
    if declared_origin not in CAPTURE_PIPELINE_ORIGINS:
        return "origin-native-flow-not-consumable-here"
    return None


def binding_declaration_bytes(
        binding: Optional[Mapping[str, str]]) -> bytes:
    """Canonical serialization of the declared binding (OD-IR-B): key-sorted
    role→field pairs, length-prefixed via the layer encoding — independent of
    the declaration's dict order. An absent binding (None or {}) serializes
    to b"" (OD-G10 analog: None and {} are the same declaration)."""
    if binding is None or len(binding) == 0:
        return b""
    parts = []
    for role in sorted(binding):
        parts.append(role.encode("utf-8"))
        parts.append(str(binding[role]).encode("utf-8"))
    payload = b"\x00".join(parts)
    return b"binding-v1\x00" + payload


def binding_declaration_fingerprint(
        binding: Optional[Mapping[str, str]], s1: S1Service) -> str:
    """The durable declaration anchor (OD-IR-B): sha256-v1 over the canonical
    declaration bytes; '' when no declaration exists."""
    payload = binding_declaration_bytes(binding)
    if payload == b"":
        return ""
    return s1.compute(payload).s1


def _role_specs_from_pointer_specs(
        pointer_specs: Sequence[Mapping[str, object]],
        normalized_binding: Mapping[str, str]) -> tuple:
    """Build the S2 role evidence (candidate_count=1 per role, the resolved
    pointer set) from the frozen primitive's pointer specs."""
    by_role = {spec["role"]: spec for spec in pointer_specs}
    specs = []
    for role in IDENTITY_ROLES:
        spec = by_role[role]
        field_name = normalized_binding[role]
        specs.append(RoleCandidateSpec(
            role=role,
            source_field_name=str(spec["source_field_name"])
            if spec["source_field_name"] is not None else field_name,
            candidate_count=1,
            field_seqs=(int(spec["field_seq"]),),
            resolved_field_seq=int(spec["field_seq"])))
    return tuple(specs)


def resolve_document_identity(state_record,
                              declared_origin: str,
                              binding: Optional[Mapping[str, str]],
                              normalized_fields: Optional[
                                  Sequence[NormalizedField]],
                              s1: S1Service) -> IdentityScopeDecision:
    """Resolve the External Document Identity for ONE verified state record
    (SPEC §4 R1a/R1b). Pure function of (state validity, binding, verified
    fields content, declared_origin).

    state_record: the VERIFIED P5.2 domain-state record (V1/V2 already passed
    in the service ladder). normalized_fields: the VERIFIED WP-4.1 read —
    REQUIRED iff the state is VALID/CLEAR and MUST be None otherwise (the
    resolver refuses to even receive unverified values, OD-IR-C). binding:
    the declared mapping (already validated by the caller; re-validated here
    as defense in depth — a malformed binding raises ValueError).

    Raises ValueError on a malformed binding (the caller refuses the request
    — fail-closed, never 'repaired')."""
    # Defense in depth: the binding declaration is validated even on routes
    # that will not consume values (V4 precedes every route in the ladder).
    normalized_binding = validate_binding(binding)

    if (state_record.domain_state != STATE_VALID
            or state_record.disposition != DISPOSITION_CLEAR):
        # R1b: a non-VALID/CLEAR state carries no verified values — CAPTURE_
        # SCOPED without any value consumption (dispatch §7 CAPTURE_SCOPED
        # definition; NOT a guess, NOT an UNRESOLVED).
        if normalized_fields is not None:
            raise ValueError(
                "verified value read supplied for a non-VALID state — "
                "unverified values must never reach the resolver")
        return IdentityScopeDecision(
            identity_scope=IDENTITY_SCOPE_CAPTURE_SCOPED,
            identity_source="",
            identity_fingerprint="",
            scope_reason=SCOPE_REASON_S2_NOT_ATTEMPTED,
            role_specs=())

    if normalized_fields is None:
        raise ValueError(
            "the verified WP-4.1 read is required for a VALID/CLEAR state")

    # R1a: delegate to the FROZEN P6.1 primitive (OD-G3 criterion + OD-G4
    # fingerprint inside) — the only formula source (OD-IR-G).
    p61 = resolve_identity(normalized_binding, normalized_fields,
                           declared_origin, s1)
    if p61.identity_class == IDENTITY_CLASS_DETERMINISTIC:
        if p61.identity_source != IDENTITY_SOURCE_S2:
            # unreachable with the frozen primitive — fail closed loudly
            raise ValueError(
                f"unexpected identity source from the frozen primitive: "
                f"{p61.identity_source!r}")
        return IdentityScopeDecision(
            identity_scope=IDENTITY_SCOPE_S2,
            identity_source=p61.identity_source,
            identity_fingerprint=p61.identity_fingerprint,
            scope_reason="",
            role_specs=_role_specs_from_pointer_specs(
                p61.pointer_specs, normalized_binding))

    # CAPTURE_SCOPED from the frozen primitive: incomplete / conflicting /
    # undetermined — relay the reason VERBATIM (OD-IR-D) and PRESERVE the
    # candidate evidence (dispatch §8 — never auto-select, never UNRESOLVED).
    reason = _P61_REASON_TO_SCOPE_REASON.get(p61.reason)
    if reason is None or reason != p61.reason:
        raise ValueError(
            f"unexpected scope reason from the frozen primitive: "
            f"{p61.reason!r}")
    specs = []
    for rr in p61.role_resolutions:
        specs.append(RoleCandidateSpec(
            role=rr.role,
            source_field_name=rr.source_field_name,
            candidate_count=rr.candidate_count,
            field_seqs=tuple(rr.field_seqs),
            resolved_field_seq=None))
    return IdentityScopeDecision(
        identity_scope=IDENTITY_SCOPE_CAPTURE_SCOPED,
        identity_source="",
        identity_fingerprint="",
        scope_reason=reason,
        role_specs=tuple(specs))
