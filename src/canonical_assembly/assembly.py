"""Deterministic Canonical Assembly engine — WP-6.2 MVP implementation.

Binding basis: SPEC-WP62-CANASM §3/§4(A4/A6)/§5/§6/§7 (OD-A2..A7, OD-A9, OD-A10
delegated details declared here). This module is PURE decision logic over
verified inputs — no persistence, no I/O, no clock, no randomness. The same
verified inputs ALWAYS yield the same assembled content (SPEC §7 I5).

Assembly mechanics (verbatim, no invention):
  - Canonical field inventory: every usable NORMALIZED row of the verified
    WP-4.1 read (ascending field_seq) + every verified P4.2 DERIVED output of
    the same normalization (deterministic order) — values VERBATIM, provenance
    labels D-01 VERBATIM, pointers re-joinable (OD-A3/OD-A10).
  - Header anchors: the three frozen D-02 identity roles, re-joined from the
    admission's identity pointer rows (OD-A2).
  - Lines: DECLARED structure only (OD-A4) — the assembler never discovers or
    groups lines. Ambiguous declared field (>=2 usable rows) → refusal
    (never auto-resolution); 0 usable rows → explicit ABSENT; all-absent line
    → explicit rejection (OD-A5).
  - Identity-anchor consistency (OD-A6): P6.1's OD-G4 fingerprint
    serialization is QUOTED exactly — _chunk(declared_origin) + the three
    role-order values — and compared against the admission's
    identity_fingerprint (verification, not re-decision).
  - NO arithmetic across fields (OD-A7): byte-identity and the anchor check
    are the only consistency mechanisms; totals semantics stay in P5.1.

The engine never sees unverified values, never renames a field (AS-04 quote
discipline), never creates UNRESOLVED (D-01), and never guesses a value that
is not in a verified upstream read.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from capture import S1Service

from normalization.model import NormalizedField

from .model import (
    ABSENT_REASON_UPSTREAM,
    HEADER_ROLES,
    LINE_ROLES,
    PROVENANCE_DERIVED,
    PROVENANCE_EXTRACTED,
    REJECT_DECLARATION_MALFORMED,
    REJECT_DECLARED_FIELD_AMBIGUOUS,
    REJECT_EMPTY_LINE,
    ROLE_INVOICE_DATE,
    ROLE_INVOICE_NUMBER,
    ROLE_INVOICE_TOTAL,
    CanonicalFieldEntry,
    CanonicalHeaderAnchor,
    CanonicalLineField,
    CanonicalLineRecord,
    RejectedLine,
)


def _chunk(value) -> bytes:
    """Deterministic length-prefixed encoding of one canonical element (the
    SAME encoding as every other layer, incl. P6.1's OD-G4 serialization)."""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bool):                          # guard: bool before int
        raise TypeError("bool is not a canonical element")
    elif isinstance(value, int):
        raw = str(value).encode("ascii")
    else:
        raise TypeError(f"unsupported canonical element: {type(value)!r}")
    return len(raw).to_bytes(8, "big") + raw


# ---------------------------------------------------------------------------
# Declaration validation + fingerprint (SPEC §3 — OD-A4)
# ---------------------------------------------------------------------------

def validate_line_binding(line_binding) -> Optional[Dict[int, Dict[str, str]]]:
    """Validate the DECLARED line structure (SPEC §3). Returns the normalized
    {line_key: {role: field_name}} dict (line keys ascending), or None when
    the declaration is absent/empty (an invoice with zero declared lines).
    Raises ValueError with a stable detail on any malformed declaration — the
    caller refuses the request (fail-closed, never 'repaired')."""
    if line_binding is None:
        return None
    if not isinstance(line_binding, Mapping):
        raise ValueError("line_binding must be a mapping of integer line "
                         "keys → {LINE_QUANTITY|LINE_UNIT_PRICE|LINE_TOTAL "
                         "→ source field name}")
    if len(line_binding) == 0:
        return None
    seen_fields: Dict[str, int] = {}
    normalized: Dict[int, Dict[str, str]] = {}
    for key in line_binding.keys():
        if isinstance(key, bool) or not isinstance(key, int) or key < 0:
            raise ValueError("line keys must be integers >= 0 (got: "
                             f"{key!r})")
    for key in sorted(line_binding.keys()):
        roles = line_binding[key]
        if not isinstance(roles, Mapping):
            raise ValueError(f"line {key} must declare a mapping of the "
                             "three frozen line roles → source field names")
        if set(roles.keys()) != set(LINE_ROLES):
            raise ValueError(f"line {key} must declare exactly the three "
                             "line roles LINE_QUANTITY, LINE_UNIT_PRICE, "
                             "LINE_TOTAL (got: "
                             + ", ".join(sorted(map(str, roles.keys())))
                             + ")")
        line_map: Dict[str, str] = {}
        for role in LINE_ROLES:
            target = roles[role]
            if not isinstance(target, str) or not target:
                raise ValueError(f"line {key} role {role} must be bound to "
                                 f"a non-empty source field name")
            if target in seen_fields:
                raise ValueError(f"source field name {target!r} is bound "
                                 f"more than once (lines {seen_fields[target]} "
                                 f"and {key}) — a shared target is an "
                                 f"ambiguous declaration")
            seen_fields[target] = key
            line_map[role] = target
        normalized[key] = line_map
    return normalized


def declaration_bytes(line_binding) -> bytes:
    """Canonical serialization of the validated declaration (OD-C5) — the
    declaration_fingerprint payload. Absent/empty and None serialize the
    same (OD-G10 analog: they are the same declaration)."""
    normalized = validate_line_binding(line_binding)
    parts: List[bytes] = [_chunk(str(len(normalized or {})))]
    for key in sorted((normalized or {}).keys()):
        parts.append(_chunk(str(key)))
        for role in LINE_ROLES:
            parts.append(_chunk(role))
            parts.append(_chunk(normalized[key][role]))
    return b"".join(parts)


# ---------------------------------------------------------------------------
# Verified value lookups (SPEC §5 C1 / §6 L1)
# ---------------------------------------------------------------------------

def _usable_normalized(field_name: str,
                       normalized_fields: Sequence[NormalizedField]) \
        -> List[NormalizedField]:
    """Usable NORMALIZED rows for one declared field name (OD-G2 analog:
    status NORMALIZED + non-empty normalized_value), order-stable by
    field_seq."""
    return sorted(
        (f for f in normalized_fields
         if f.source_field_name == field_name
         and f.status == "NORMALIZED"
         and f.normalized_value is not None
         and f.normalized_value != ""),
        key=lambda f: f.field_seq)


@dataclass(frozen=True)
class DeclaredFieldResolution:
    """Resolution of one declared field name against the verified read."""
    field_name: str
    candidate_count: int
    value: Optional[str]                 # set iff candidate_count == 1
    field_seq: Optional[int]             # set iff candidate_count == 1


def resolve_declared_field(field_name: str,
                           normalized_fields: Sequence[NormalizedField]) \
        -> DeclaredFieldResolution:
    """Resolve one declared field name (SPEC §6 L1): 0 usable → absent;
    1 usable → value; >=2 usable → ambiguous (the caller refuses — assembling
    would require picking a candidate, i.e. auto-resolution)."""
    usable = _usable_normalized(field_name, normalized_fields)
    if len(usable) == 1:
        return DeclaredFieldResolution(
            field_name=field_name, candidate_count=1,
            value=usable[0].normalized_value or "",
            field_seq=usable[0].field_seq)
    return DeclaredFieldResolution(
        field_name=field_name, candidate_count=len(usable),
        value=None, field_seq=None)


# ---------------------------------------------------------------------------
# Assembly content (SPEC §5 C1..C4, §6, §4 A6)
# ---------------------------------------------------------------------------

def assemble_fields(invoice_id: str, normalization_id: str,
                    normalized_fields: Sequence[NormalizedField],
                    derived_outputs: Sequence) -> Tuple[CanonicalFieldEntry, ...]:
    """The canonical field inventory (SPEC §5 C1/C2/C3): EXTRACTED rows in
    ascending field_seq order, then DERIVED outputs in
    (output_field_name, formula_id, formula_version, derivation_id) order —
    values VERBATIM, provenance D-01 VERBATIM, pointers re-joinable."""
    entries: List[CanonicalFieldEntry] = []
    seq = 0
    for f in sorted(
            (x for x in normalized_fields
             if x.status == "NORMALIZED"
             and x.normalized_value is not None
             and x.normalized_value != ""),
            key=lambda x: x.field_seq):
        entries.append(CanonicalFieldEntry(
            invoice_id=invoice_id,
            canonical_seq=seq,
            provenance=PROVENANCE_EXTRACTED,
            field_name=f.source_field_name,
            canonical_value=f.normalized_value or "",
            source_normalization_id=normalization_id,
            source_field_seq=f.field_seq,
            source_derivation_id=""))
        seq += 1
    for d in sorted(
            derived_outputs,
            key=lambda d: (d.record.output_field_name,
                           d.record.formula_id, d.record.formula_version,
                           d.record.derivation_id)):
        entries.append(CanonicalFieldEntry(
            invoice_id=invoice_id,
            canonical_seq=seq,
            provenance=PROVENANCE_DERIVED,
            field_name=d.record.output_field_name,
            canonical_value=d.record.output_value,
            source_normalization_id="",
            source_field_seq=None,
            source_derivation_id=d.record.derivation_id))
        seq += 1
    return tuple(entries)


def assemble_header_anchors(invoice_id: str,
                            identity_pointers,
                            normalized_fields: Sequence[NormalizedField]) \
        -> Tuple[CanonicalHeaderAnchor, ...]:
    """The canonical header anchors (SPEC §5 C4 / OD-A2): the three frozen
    D-02 roles, re-joined from the admission's identity pointer rows through
    the verified read. Raises ValueError on any pointer that does not re-join
    exactly one usable NORMALIZED row (the caller turns this into the A6
    integrity failure — fail-closed, never guessed)."""
    by_key = {(f.source_field_name, f.field_seq): f
              for f in normalized_fields}
    anchors: List[CanonicalHeaderAnchor] = []
    for role in HEADER_ROLES:
        pointer = next((p for p in identity_pointers if p.role == role), None)
        if pointer is None:
            raise ValueError(
                f"admission identity pointer for role {role} is missing — "
                f"fail-closed (the Gate always stores three pointers)")
        f = by_key.get((pointer.source_field_name, pointer.field_seq))
        if f is None or f.status != "NORMALIZED" or not f.normalized_value:
            raise ValueError(
                f"identity pointer {role} → "
                f"{pointer.source_field_name}/{pointer.field_seq} does not "
                f"re-join a usable NORMALIZED row in the verified read")
        anchors.append(CanonicalHeaderAnchor(
            invoice_id=invoice_id,
            role=role,
            canonical_value=f.normalized_value or "",
            source_field_name=pointer.source_field_name,
            normalization_id=pointer.normalization_id,
            field_seq=pointer.field_seq))
    return tuple(anchors)


def identity_anchor_payload(declared_origin: str,
                            header_anchors: Sequence[CanonicalHeaderAnchor]) \
        -> bytes:
    """P6.1's OD-G4 serialization, QUOTED exactly (OD-A6): declared_origin +
    the three canonical values in role order. Comparing the sha256-v1 of this
    payload against the admission's identity_fingerprint machine-checks the
    assembled header against the identity the Gate resolved — the SAME
    formula, never a different one."""
    by_role = {a.role: a.canonical_value for a in header_anchors}
    return b"".join(
        [_chunk(declared_origin)]
        + [_chunk(by_role[ROLE_INVOICE_NUMBER]),
           _chunk(by_role[ROLE_INVOICE_DATE]),
           _chunk(by_role[ROLE_INVOICE_TOTAL])])


def assemble_lines(invoice_id: str,
                   normalization_id: str,
                   normalized_line_binding: Optional[Dict[int, Dict[str, str]]],
                   normalized_fields: Sequence[NormalizedField]) \
        -> Tuple[Tuple[CanonicalLineRecord, ...],
                 Tuple[CanonicalLineField, ...],
                 Tuple[RejectedLine, ...]]:
    """Declared line assembly (SPEC §6 — OD-A4/OD-A5). Returns (lines,
    line_fields, rejected_lines). Ambiguity raises ValueError (the caller
    refuses the whole request — never auto-resolution)."""
    if not normalized_line_binding:
        return (), (), ()
    lines: List[CanonicalLineRecord] = []
    line_fields: List[CanonicalLineField] = []
    rejected: List[RejectedLine] = []
    for key in sorted(normalized_line_binding.keys()):
        roles = normalized_line_binding[key]
        resolutions: Dict[str, DeclaredFieldResolution] = {}
        for role in LINE_ROLES:
            resolution = resolve_declared_field(roles[role],
                                                normalized_fields)
            if resolution.candidate_count > 1:
                raise ValueError(
                    f"{REJECT_DECLARED_FIELD_AMBIGUOUS}: line {key} role "
                    f"{role} declares {roles[role]!r} with "
                    f"{resolution.candidate_count} usable NORMALIZED rows — "
                    f"assembling would require picking a candidate "
                    f"(auto-resolution is forbidden)")
            resolutions[role] = resolution
        if all(resolutions[role].candidate_count == 0 for role in LINE_ROLES):
            # OD-A5: an all-absent line is REJECTED — explicit, never stored,
            # never silently dropped.
            rejected.append(RejectedLine(line_seq=key,
                                         reason=REJECT_EMPTY_LINE))
            continue
        lines.append(CanonicalLineRecord(invoice_id=invoice_id, line_seq=key))
        for role in LINE_ROLES:
            resolution = resolutions[role]
            if resolution.candidate_count == 0:
                line_fields.append(CanonicalLineField(
                    invoice_id=invoice_id, line_seq=key, role=role,
                    present=0, canonical_value=None,
                    source_field_name="", normalization_id="",
                    field_seq=None))
            else:
                line_fields.append(CanonicalLineField(
                    invoice_id=invoice_id, line_seq=key, role=role,
                    present=1, canonical_value=resolution.value,
                    source_field_name=resolution.field_name,
                    normalization_id=normalization_id,
                    field_seq=resolution.field_seq))
    return tuple(lines), tuple(line_fields), tuple(rejected)
