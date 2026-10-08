"""Deterministic Identity Resolution — WP-6.1 MVP implementation.

Binding basis: SPEC-WP61-CANGATE §5 (OD-G2..OD-G5, OD-G10 delegated details
declared here). This module is PURE decision logic over verified inputs — no
persistence, no I/O, no clock, no randomness. The same verified inputs ALWAYS
yield the same identity resolution (SPEC §6 determinism analog).

D-02 mechanics implemented (verbatim, exact only):
  - The External Document Identity is DETERMINISTIC iff the frozen S2 triad
    (invoice number + date + total) is fully extracted AND verified —
    OD-G3's criterion: exactly one usable NORMALIZED row per bound role in the
    verified WP-4.1 read, under a P5.2 VALID/CLEAR state (enforced by the
    caller — G3 is reachable only there).
  - Otherwise the identity is explicitly CAPTURE_SCOPED (D-02's third class).
  - The adapter-issued document id path (D-02's first deterministic path) is
    RESERVED (OD-G5): no producer exists in the implemented pipeline (D-04
    post-freeze); nothing is invented to fill it.

D-03 mechanics (the caller routes on this outcome):
  - incomplete / conflicting identity → REVIEW (never guessed, never merged)
  - multiple candidates → DO NOT AUTO-RESOLVE (dispatch §6)

The resolver NEVER sees unverified values, NEVER stores raw pipeline values,
and NEVER matches fuzzily: the only comparison anchor it produces is the
deterministic identity fingerprint (sha256-v1 over declared_origin + the three
canonical values in role order — OD-G4), the S2 analog of Capture S1.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

from capture import S1Service

from normalization.model import NormalizedField

from .model import (
    IDENTITY_CLASS_CAPTURE_SCOPED,
    IDENTITY_CLASS_DETERMINISTIC,
    IDENTITY_ROLES,
    IDENTITY_SOURCE_S2,
    REASON_D03_CONFLICTING_IDENTITY,
    REASON_D03_INCOMPLETE_IDENTITY,
    REASON_D03_UNDETERMINED_IDENTITY,
    IdentityResolution,
    RoleResolution,
)


def _chunk(value) -> bytes:
    """Deterministic length-prefixed encoding of one canonical element (same
    encoding as every other layer)."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bool):                          # guard: bool before int
        raise TypeError("bool is not a canonical element")
    elif isinstance(value, int):
        raw = str(value).encode("ascii")
    else:
        raise TypeError(f"unsupported canonical element: {type(value)!r}")
    return len(raw).to_bytes(8, "big") + raw


def validate_binding(binding) -> Optional[Dict[str, str]]:
    """Validate the declared identity-field binding (SPEC §3).

    Returns the normalized role → field_name dict, or None when the binding is
    absent/empty (OD-G10: None and {} are the same declaration). Raises
    ValueError with a stable detail on any malformed binding — the caller
    refuses the request (fail-closed, never 'repaired')."""
    if binding is None:
        return None
    if not isinstance(binding, Mapping):
        raise ValueError("identity_field_binding must be a mapping of "
                         "INVOICE_NUMBER|INVOICE_DATE|INVOICE_TOTAL → source "
                         "field name")
    if len(binding) == 0:
        return None
    if set(binding.keys()) != set(IDENTITY_ROLES):
        raise ValueError(
            "identity_field_binding must declare exactly the three frozen "
            "D-02 roles INVOICE_NUMBER, INVOICE_DATE, INVOICE_TOTAL (got: "
            + ", ".join(sorted(map(str, binding.keys()))) + ")")
    normalized: Dict[str, str] = {}
    for role in IDENTITY_ROLES:
        target = binding[role]
        if not isinstance(target, str) or not target:
            raise ValueError(f"identity role {role} must be bound to a "
                             f"non-empty source field name")
        normalized[role] = target
    if len(set(normalized.values())) != len(normalized):
        raise ValueError("identity roles must be bound to DISTINCT source "
                         "field names — a shared target is an ambiguous "
                         "declaration")
    return normalized


def resolve_identity(binding: Optional[Mapping[str, str]],
                     normalized_fields: Sequence[NormalizedField],
                     declared_origin: str,
                     s1: S1Service) -> IdentityResolution:
    """Resolve the External Document Identity per D-02/D-03 (SPEC §5).

    normalized_fields: the fields of the VERIFIED WP-4.1 normalization read
    (the only sanctioned value-level fact path). declared_origin: the frozen
    origin declared on the request — the source-system scope component of the
    identity fingerprint (OD-G4). s1: the fingerprint capability service.

    The resolution is a pure function of (binding, fields content,
    declared_origin). Raw values are consumed ONLY here, inside the
    fingerprint — never returned, never stored."""
    normalized_binding = validate_binding(binding)
    if normalized_binding is None:
        # OD-G10: no document identity attempted → explicitly undetermined
        # (D-03: CAPTURE_SCOPED → document-dedup ambiguity → REVIEW)
        return IdentityResolution(
            identity_class=IDENTITY_CLASS_CAPTURE_SCOPED,
            identity_source="",
            identity_fingerprint="",
            reason=REASON_D03_UNDETERMINED_IDENTITY,
            role_resolutions=(),
            pointer_specs=())

    role_resolutions: Tuple[RoleResolution, ...] = tuple(
        _resolve_role(role, normalized_binding[role], normalized_fields)
        for role in IDENTITY_ROLES)

    # OD-G2: a usable identity value is a NORMALIZED row with a non-empty
    # normalized_value; 0 usable → incomplete, ≥2 → conflicting (D-03 ناقص /
    # متعارض → REVIEW; never guessed, never merged).
    usable_values: Dict[str, str] = {}
    for rr in role_resolutions:
        if rr.candidate_count == 0:
            return IdentityResolution(
                identity_class=IDENTITY_CLASS_CAPTURE_SCOPED,
                identity_source="",
                identity_fingerprint="",
                reason=REASON_D03_INCOMPLETE_IDENTITY,
                role_resolutions=role_resolutions,
                pointer_specs=())
        if rr.candidate_count > 1:
            return IdentityResolution(
                identity_class=IDENTITY_CLASS_CAPTURE_SCOPED,
                identity_source="",
                identity_fingerprint="",
                reason=REASON_D03_CONFLICTING_IDENTITY,
                role_resolutions=role_resolutions,
                pointer_specs=())
        usable_values[rr.role] = _single_value(
            normalized_binding[rr.role], rr.field_seqs[0], normalized_fields)

    # D-02's second deterministic path (OD-G3): the S2 triad, fully extracted
    # (single NORMALIZED row per role) and verified (VALID/CLEAR state — the
    # caller's guarantee).
    fingerprint_payload = b"".join(
        [_chunk(declared_origin)]
        + [_chunk(usable_values[role]) for role in IDENTITY_ROLES])
    fp = s1.compute(fingerprint_payload)
    pointer_specs: Tuple[Dict[str, object], ...] = tuple(
        {"role": rr.role,
         "source_field_name": normalized_binding[rr.role],
         "field_seq": rr.field_seqs[0]}
        for rr in role_resolutions)
    return IdentityResolution(
        identity_class=IDENTITY_CLASS_DETERMINISTIC,
        identity_source=IDENTITY_SOURCE_S2,
        identity_fingerprint=fp.s1,
        reason="",
        role_resolutions=role_resolutions,
        pointer_specs=pointer_specs)


def _resolve_role(role: str, field_name: str,
                  normalized_fields: Sequence[NormalizedField]) \
        -> RoleResolution:
    """Count usable NORMALIZED candidates for one bound role (order-stable by
    field_seq)."""
    seqs = tuple(sorted(
        f.field_seq for f in normalized_fields
        if f.source_field_name == field_name
        and f.status == "NORMALIZED"
        and f.normalized_value is not None
        and f.normalized_value != ""))
    return RoleResolution(role=role, source_field_name=field_name,
                          candidate_count=len(seqs), field_seqs=seqs)


def _single_value(field_name: str, field_seq: int,
                  normalized_fields: Sequence[NormalizedField]) \
        -> str:
    """Fetch the single usable value for one role — consumed only inside the
    fingerprint computation (pointer discipline: never returned outward)."""
    for f in normalized_fields:
        if (f.source_field_name == field_name and f.field_seq == field_seq
                and f.status == "NORMALIZED"):
            return f.normalized_value or ""
    raise ValueError(f"identity value vanished for {field_name}/{field_seq} "
                     f"— verified read changed under resolution")
