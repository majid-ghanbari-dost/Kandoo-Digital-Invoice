"""Deterministic Validation State Machine — WP-5.2 MVP implementation.

Binding basis: SPEC-WP52-VSM §3/§4/§7/§12 (OD-S8..OD-S12 delegated details are
declared here). This module is PURE decision logic over verified inputs — no
persistence, no I/O, no clock, no randomness. The same verified inputs ALWAYS
yield the same projection content (SPEC §7).

Transition table (declared priority, first match wins — OD-S8; every route is
anchored to a frozen source, see SPEC §3):

    T1  any INVALID(absent | present-not-usable | mismatch)      → INVALID / REJECT
    T2  any INVALID(mismatch-beyond-tolerance |                  → INVALID / REVIEW
                mismatch-after-rounding)                           (D-08)
    T3  any field projection UNRESOLVED (D-01 order exhausted)   → UNRESOLVED / REVIEW
    T4  any rule outcome DEFERRED                                → DEFERRED / REVIEW
    T5  else                                                     → VALID / CLEAR

The machine never re-decides any P5.1 outcome, never resolves UNRESOLVED, never
invents a state outside the frozen vocabulary, and never sees a value — only
outcomes, reasons, pointers, and declared field names.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from capture import S1Service

from .model import (
    DECISIVE_INVALID_REASONS,
    DISPOSITION_CLEAR,
    DISPOSITION_REJECT,
    DISPOSITION_REVIEW,
    DOMAIN_STATE_DEFERRED,
    DOMAIN_STATE_INVALID,
    DOMAIN_STATE_UNRESOLVED,
    DOMAIN_STATE_VALID,
    ORIGIN_RELAY_DERIVED,
    ORIGIN_RELAY_NORMALIZED,
    PROJECTION_RESOLVED,
    PROJECTION_UNRESOLVED,
    REASON_ALL_RULES_VALID,
    REASON_D01_UNRESOLVED_REVIEW,
    REASON_D08_MISMATCH_REVIEW,
    REASON_DECISIVE_INVALID,
    REASON_VALIDATION_DEFERRED_REVIEW,
    TOLERANCE_INVALID_REASONS,
    UNRESOLVED_REASON_D01,
    DomainStateRecord,
    FieldProjectionRow,
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


def canonical_ruleset_bytes(ruleset_id: str, ruleset_version: str,
                            ordered_keys: Sequence[Tuple[str, str]],
                            fingerprints: Sequence[str]) -> bytes:
    """Canonical serialization fingerprinted as the ruleset fingerprint (OD-S12):
    the ruleset identity (id, version) + the ordered declared
    (rule_id, rule_version, rule_fingerprint-from-record) triples. The same
    declared evaluation under the SAME ruleset identity ALWAYS yields the same
    fingerprint; a different identity, order, or rule version yields a different
    one (SPEC §7 — a NEW ruleset_version is a DIFFERENT validation key)."""
    if len(ordered_keys) != len(fingerprints):
        raise ValueError("ruleset keys/fingerprints length mismatch")
    parts: List[bytes] = [_chunk(ruleset_id), _chunk(ruleset_version),
                          _chunk(len(ordered_keys))]
    for (rule_id, rule_version), rule_fp in zip(ordered_keys, fingerprints):
        parts += [_chunk(rule_id), _chunk(rule_version), _chunk(rule_fp)]
    return b"".join(parts)


def ruleset_fingerprint(ruleset_id: str, ruleset_version: str,
                        ordered_keys: Sequence[Tuple[str, str]],
                        fingerprints: Sequence[str], s1: S1Service) -> Tuple[str, str]:
    """sha256-v1 ruleset fingerprint (OD-S12). Returns (fingerprint, algorithm)."""
    anchor = s1.compute(canonical_ruleset_bytes(ruleset_id, ruleset_version,
                                                ordered_keys, fingerprints))
    return anchor.s1, anchor.s1_algorithm_id


def project_fields(domain_state_id: str, declared_fields: Sequence[str],
                   normalization_id: str, extraction_id: str,
                   slot_facts: Sequence[dict],
                   normalized_backfill: Dict[str, Tuple[int, int]],
                   unresolved_notes: Optional[Dict[str, str]] = None) \
        -> Tuple[Tuple[FieldProjectionRow, ...], int]:
    """D-01 value-level projection for EVERY declared field (SPEC §4; OD-S10/
    OD-S11). Returns (rows sorted by field_name, unresolved_count).

    slot_facts — one dict per P5.1 input relayed by the service:
      {field_name, value_origin ('NORMALIZED'|'DERIVED'), source_field_seq,
       source_derivation_id}
    normalized_backfill — per declared field with NO relayed slot:
      (lowest_field_seq, candidate_count) from the verified normalization read.
    unresolved_notes — optional per-field verbatim observation relayed into the
      UNRESOLVED detail (e.g. observed upstream statuses) — relayed, never
      re-decided.

    Determinism: NORMALIZED origin preferred over DERIVED (D-01 order); within an
    origin the lowest source_field_seq / lexicographically-first derivation id
    wins; candidates counted across all relayed slots of the winning origin.
    """
    by_field: Dict[str, List[dict]] = {}
    for fact in slot_facts:
        by_field.setdefault(fact["field_name"], []).append(fact)

    rows: List[FieldProjectionRow] = []
    unresolved = 0
    for field_name in sorted(declared_fields):
        facts = by_field.get(field_name, ())
        normalized = [f for f in facts
                      if f["value_origin"] == ORIGIN_RELAY_NORMALIZED]
        derived = [f for f in facts if f["value_origin"] == ORIGIN_RELAY_DERIVED]
        if normalized:
            chosen = min(normalized, key=lambda f: f["source_field_seq"])
            rows.append(FieldProjectionRow(
                domain_state_id=domain_state_id,
                field_name=field_name,
                projection_status=PROJECTION_RESOLVED,
                origin_relayed=ORIGIN_RELAY_NORMALIZED,
                candidate_count=len(normalized),
                source_normalization_id=normalization_id,
                source_extraction_id=extraction_id,
                source_field_seq=chosen["source_field_seq"],
                source_derivation_id=None,
                unresolved_reason=None,
                detail=f"usable NORMALIZED value (D-01 order step 1); "
                       f"{len(normalized)} resolved slot(s) relayed",
            ))
            continue
        if derived:
            chosen = min(derived, key=lambda f: f["source_derivation_id"])
            rows.append(FieldProjectionRow(
                domain_state_id=domain_state_id,
                field_name=field_name,
                projection_status=PROJECTION_RESOLVED,
                origin_relayed=ORIGIN_RELAY_DERIVED,
                candidate_count=len(derived),
                source_normalization_id=normalization_id,
                source_extraction_id=extraction_id,
                source_field_seq=None,
                source_derivation_id=chosen["source_derivation_id"],
                unresolved_reason=None,
                detail=f"usable DERIVED value (D-01 order step 2); "
                       f"{len(derived)} resolved slot(s) relayed",
            ))
            continue
        backfill = normalized_backfill.get(field_name)
        if backfill is not None:
            field_seq, count = backfill
            rows.append(FieldProjectionRow(
                domain_state_id=domain_state_id,
                field_name=field_name,
                projection_status=PROJECTION_RESOLVED,
                origin_relayed=ORIGIN_RELAY_NORMALIZED,
                candidate_count=count,
                source_normalization_id=normalization_id,
                source_extraction_id=extraction_id,
                source_field_seq=field_seq,
                source_derivation_id=None,
                unresolved_reason=None,
                detail=f"usable NORMALIZED value present in the verified "
                       f"normalization read (D-01 order step 1; {count} "
                       f"candidate(s) — association belongs to the "
                       f"Canonicalization Gate)",
            ))
            continue
        unresolved += 1
        note = (unresolved_notes or {}).get(field_name)
        detail = ("no usable EXTRACTED value and no DERIVED value in the "
                  "verified sources — D-01 resolution order exhausted "
                  "(field-level; never auto-resolved here)")
        if note:
            detail += f" [{note}]"
        rows.append(FieldProjectionRow(
            domain_state_id=domain_state_id,
            field_name=field_name,
            projection_status=PROJECTION_UNRESOLVED,
            origin_relayed=None,
            candidate_count=0,
            source_normalization_id=normalization_id,
            source_extraction_id=extraction_id,
            source_field_seq=None,
            source_derivation_id=None,
            unresolved_reason=UNRESOLVED_REASON_D01,
            detail=detail,
        ))
    return tuple(rows), unresolved


def derive_state(records: Sequence[dict], unresolved_count: int) -> Tuple[str, str, str, str]:
    """The transition function (SPEC §3 — declared priority, first match wins).

    records — one dict per consumed P5.1 record:
      {rule_id, rule_version, outcome, outcome_reason, outcome_detail}
    Returns (domain_state, disposition, state_reason, state_detail).

    The state_detail relays every contributing rule outcome AND the contributing
    P5.1 detail text verbatim — the projection is auditable end to end. Nothing
    is re-decided: outcomes are consumed verbatim.
    """
    outcome_lines = [
        f"{r['rule_id']}/{r['rule_version']} → {r['outcome']}"
        f"({r['outcome_reason']})" for r in records
    ]

    decisive = [r for r in records
                if r["outcome"] == "INVALID"
                and r["outcome_reason"] in DECISIVE_INVALID_REASONS]
    if decisive:
        detail = ("decisive rule violation(s): "
                  + "; ".join(f"{r['rule_id']}/{r['rule_version']} "
                              f"reason={r['outcome_reason']} — {r['outcome_detail']}"
                              for r in decisive)
                  + " || outcomes: " + ", ".join(outcome_lines))
        return (DOMAIN_STATE_INVALID, DISPOSITION_REJECT, REASON_DECISIVE_INVALID,
                detail)

    tolerance = [r for r in records
                 if r["outcome"] == "INVALID"
                 and r["outcome_reason"] in TOLERANCE_INVALID_REASONS]
    if tolerance:
        detail = ("D-08 unresolved mismatch — routed to REVIEW: "
                  + "; ".join(f"{r['rule_id']}/{r['rule_version']} "
                              f"reason={r['outcome_reason']} — {r['outcome_detail']}"
                              for r in tolerance)
                  + " || outcomes: " + ", ".join(outcome_lines))
        return (DOMAIN_STATE_INVALID, DISPOSITION_REVIEW,
                REASON_D08_MISMATCH_REVIEW, detail)

    if unresolved_count > 0:
        detail = (f"{unresolved_count} declared field(s) UNRESOLVED — D-01 "
                  f"resolution order exhausted (field-level, never auto-resolved "
                  f"here) || outcomes: " + ", ".join(outcome_lines))
        return (DOMAIN_STATE_UNRESOLVED, DISPOSITION_REVIEW,
                REASON_D01_UNRESOLVED_REVIEW, detail)

    deferred = [r for r in records if r["outcome"] == "DEFERRED"]
    if deferred:
        detail = ("validation uncertainty — routed to REVIEW: "
                  + "; ".join(f"{r['rule_id']}/{r['rule_version']} "
                              f"reason={r['outcome_reason']} — {r['outcome_detail']}"
                              for r in deferred)
                  + " || outcomes: " + ", ".join(outcome_lines))
        return (DOMAIN_STATE_DEFERRED, DISPOSITION_REVIEW,
                REASON_VALIDATION_DEFERRED_REVIEW, detail)

    detail = ("all declared rules hold; no field-level UNRESOLVED — no REVIEW/"
              "REJECT action exists in this layer (the Canonicalization Gate "
              "remains the next downstream authority) || outcomes: "
              + ", ".join(outcome_lines))
    return (DOMAIN_STATE_VALID, DISPOSITION_CLEAR, REASON_ALL_RULES_VALID, detail)


def build_state_record(domain_state_id: str, normalization_id: str,
                       extraction_id: str, document_id: str, capture_id: str,
                       capture_s1: str, capture_s1_algorithm_id: str,
                       ruleset_id: str, ruleset_version: str,
                       ruleset_fingerprint: str,
                       ruleset_fingerprint_algorithm_id: str,
                       domain_state: str, disposition: str, state_reason: str,
                       state_detail: str, rule_count: int, valid_count: int,
                       invalid_count: int, deferred_count: int,
                       unresolved_count: int, created_at: str) -> DomainStateRecord:
    """Assemble the durable header (fingerprint anchored by the store)."""
    return DomainStateRecord(
        domain_state_id=domain_state_id,
        normalization_id=normalization_id,
        extraction_id=extraction_id,
        document_id=document_id,
        capture_id=capture_id,
        capture_s1=capture_s1,
        capture_s1_algorithm_id=capture_s1_algorithm_id,
        ruleset_id=ruleset_id,
        ruleset_version=ruleset_version,
        ruleset_fingerprint=ruleset_fingerprint,
        ruleset_fingerprint_algorithm_id=ruleset_fingerprint_algorithm_id,
        domain_state=domain_state,
        disposition=disposition,
        state_reason=state_reason,
        state_detail=state_detail,
        rule_count=rule_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        deferred_count=deferred_count,
        unresolved_count=unresolved_count,
        created_at=created_at,
        record_fingerprint="",
        fingerprint_algorithm_id="",
    )
