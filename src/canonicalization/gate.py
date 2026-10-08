"""Deterministic Gate Decision Engine — WP-6.1 MVP implementation.

Binding basis: SPEC-WP61-CANGATE §4 (OD-G1 delegated detail declared here).
This module is PURE decision logic over verified inputs — no persistence, no
I/O, no clock, no randomness. The same verified inputs ALWAYS yield the same
route (SPEC §6 determinism analog).

Decision table (declared priority, first match wins — OD-G1; every route is
anchored to a frozen source, see SPEC §4):

    G1  disposition REJECT                          → REJECTED / upstream-decisive-invalid
                                                      (AD-04; OD-S9 split)
    G2  disposition REVIEW                          → REVIEW / P5.2 state_reason
                                                      relayed VERBATIM (D-08/D-01/D-03)
    G3  VALID/CLEAR + CAPTURE_SCOPED identity       → REVIEW / D-03 identity reason
    G4  VALID/CLEAR + DETERMINISTIC + capture_s1    → ALREADY_CANONICALIZED
        already canonicalized                         (D-02 S1 idempotency; D-03)
    G5  VALID/CLEAR + DETERMINISTIC + identity fp   → REJECTED /
        already canonicalized (different capture)     d03-definite-document-duplicate
                                                      (D-03: S2 complete+exact)
    G6  else                                        → ACCEPTED /
                                                      all-frozen-conditions-met

G0 (a decision already exists for the domain state) is enforced by the
service/store INV-D-1:1 mechanics BEFORE any route evaluation — a replay
returns the existing decision verbatim and never re-decides (D-03 idempotency).

The engine never re-decides any P5.2 outcome, never resolves identity
ambiguity, never invents a decision outside the declared vocabulary, and never
sees a raw pipeline value — only outcomes, reasons, pointers, fingerprints, and
declared metadata.
"""
from __future__ import annotations

from typing import Optional, Sequence

from validation_domain import (
    DISPOSITION_CLEAR,
    DISPOSITION_REJECT,
    DISPOSITION_REVIEW,
    DOMAIN_STATE_VALID,
)

from .model import (
    DECISION_ACCEPTED,
    DECISION_ALREADY_CANONICALIZED,
    DECISION_REJECTED,
    DECISION_REVIEW,
    IDENTITY_CLASS_CAPTURE_SCOPED,
    IDENTITY_CLASS_DETERMINISTIC,
    REASON_ALL_FROZEN_CONDITIONS_MET,
    REASON_D02_CAPTURE_REPLAY,
    REASON_D03_DEFINITE_DUPLICATE,
    REASON_UPSTREAM_DECISIVE_INVALID,
    GateDecisionRecord,
    IdentityResolution,
)


class GateRoute:
    """The pure route outcome: decision kind + stable reason + audit detail."""
    __slots__ = ("decision", "reason", "detail")

    def __init__(self, decision: str, reason: str, detail: str) -> None:
        self.decision = decision
        self.reason = reason
        self.detail = detail


def state_summary(record) -> str:
    """Coarse audit summary of the consumed P5.2 state (metadata only)."""
    return (f"state={record.domain_state}/{record.disposition} "
            f"reason={record.state_reason} "
            f"ruleset={record.ruleset_id}/{record.ruleset_version} "
            f"rules={record.rule_count}")


def route_decision(state_record,
                   identity: Optional[IdentityResolution],
                   capture_invoice_exists: bool,
                   identity_invoice_exists: bool,
                   upstream_review_id: Optional[str]) -> GateRoute:
    """Evaluate the declared decision table (G1..G6 — SPEC §4).

    state_record: the VERIFIED P5.2 DomainStateRecord (V1/V2 already passed).
    identity: the IdentityResolution over verified reads (None only for the
    non-VALID routes, which never reach identity resolution).
    capture_invoice_exists: a canonical invoice already exists for the same
    capture_s1 (the G4 predicate — the D-02 S1 idempotency key).
    identity_invoice_exists: a canonical invoice already exists with the same
    identity_fingerprint from a different capture (the G5 predicate — D-03's
    exact S2 duplicate check).
    upstream_review_id: the P5.2 review item reference when the state carries
    one (G2 referencing, OD-G9 — never duplicated).
    """
    detail_parts = [f"upstream[{state_summary(state_record)}]"]

    # G1 — decisive upstream invalidity (AD-04 REJECT; OD-S9 split)
    if state_record.disposition == DISPOSITION_REJECT:
        detail_parts.append(f"upstream state_reason relayed: "
                            f"{state_record.state_reason}")
        return GateRoute(
            decision=DECISION_REJECTED,
            reason=REASON_UPSTREAM_DECISIVE_INVALID,
            detail="; ".join(detail_parts))

    # G2 — upstream-held uncertainty (D-08 / D-01 / T4; relayed VERBATIM, the
    # P5.2 queue item is REFERENCED, never duplicated — OD-G9)
    if state_record.disposition == DISPOSITION_REVIEW:
        detail_parts.append(
            f"upstream uncertainty held in the P5.2 REVIEW queue; "
            f"upstream_review_id="
            f"{upstream_review_id if upstream_review_id else 'none'}")
        return GateRoute(
            decision=DECISION_REVIEW,
            reason=state_record.state_reason,     # verbatim relay (CL-1)
            detail="; ".join(detail_parts))

    # VALID/CLEAR from here — the frozen storage CHECKs make any other
    # (state, disposition) combination unreachable; defensive refusal anyway.
    if state_record.domain_state != DOMAIN_STATE_VALID \
            or state_record.disposition != DISPOSITION_CLEAR:
        raise ValueError(
            "unreachable state/disposition combination passed verification — "
            "refusing (fail-closed)")

    if identity is None:
        raise ValueError("identity resolution is required for a VALID/CLEAR "
                         "state — refusing (fail-closed)")
    detail_parts.append(
        f"identity={identity.identity_class or 'unrouted'} "
        f"source={identity.identity_source or 'none'} "
        f"roles=" + ",".join(
            f"{rr.role}:{rr.source_field_name}x{rr.candidate_count}"
            for rr in identity.role_resolutions))

    # G3 — identity nondeterminism (D-03 ناقص/متعارض/ambiguity → REVIEW;
    # dispatch §6: multiple candidates are NEVER auto-resolved)
    if identity.identity_class == IDENTITY_CLASS_CAPTURE_SCOPED:
        detail_parts.append(
            "document identity is CAPTURE_SCOPED (D-02) — only capture-level "
            "deduplication is guaranteed (D-03); document-duplicate ambiguity "
            "routes REVIEW")
        return GateRoute(
            decision=DECISION_REVIEW,
            reason=identity.reason,
            detail="; ".join(detail_parts))

    if identity.identity_class != IDENTITY_CLASS_DETERMINISTIC:
        raise ValueError("unreachable identity class — refusing (fail-closed)")

    # G4 — the D-02 capture-level idempotency key (S1): the same capture
    # artifact can never produce a second canonical invoice
    if capture_invoice_exists:
        detail_parts.append(
            "a canonical invoice already exists for this capture_s1 — "
            "idempotent replay (D-02 S1; D-03 capture idempotency)")
        return GateRoute(
            decision=DECISION_ALREADY_CANONICALIZED,
            reason=REASON_D02_CAPTURE_REPLAY,
            detail="; ".join(detail_parts))

    # G5 — D-03's definite document-level duplicate (S2 complete + exact):
    # decisive, not uncertainty — no REVIEW, no second invoice
    if identity_invoice_exists:
        detail_parts.append(
            "a canonical invoice with the same identity fingerprint already "
            "exists from a different capture — definite document-level "
            "duplicate (D-03: S2 complete and exact)")
        return GateRoute(
            decision=DECISION_REJECTED,
            reason=REASON_D03_DEFINITE_DUPLICATE,
            detail="; ".join(detail_parts))

    # G6 — every frozen condition holds
    detail_parts.append(
        "all frozen conditions met: verified state (VALID/CLEAR), whole-chain "
        "provenance re-verified, deterministic identity (S2), no capture "
        "replay, no document duplicate")
    return GateRoute(
        decision=DECISION_ACCEPTED,
        reason=REASON_ALL_FROZEN_CONDITIONS_MET,
        detail="; ".join(detail_parts))


def validate_route(record: GateDecisionRecord) -> None:
    """Defensive content-consistency check over a decision about to be committed
    (mirrors the storage CHECKs — OD-C6). Raises ValueError on any drift."""
    if record.decision not in (DECISION_ACCEPTED, DECISION_REJECTED,
                               DECISION_REVIEW,
                               DECISION_ALREADY_CANONICALIZED):
        raise ValueError(f"decision {record.decision!r} is outside the "
                         f"declared vocabulary")
    if (record.decision == DECISION_ACCEPTED) != \
            (record.canonical_invoice_id is not None):
        raise ValueError("ACCEPTED decisions carry exactly one canonical "
                         "invoice; no other decision carries one")
    if record.declared_origin not in ("HOLOO_CAPTURE", "OTHER_POS_CAPTURE"):
        raise ValueError("declared_origin must be a capture-pipeline origin "
                         "(OD-G6)")
    if record.decision == DECISION_REVIEW \
            and record.decision_reason not in (
                "d08-mismatch-review", "d01-unresolved-review",
                "validation-deferred-review",
                "d03-incomplete-document-identity",
                "d03-conflicting-document-identity",
                "d03-document-identity-undetermined"):
        raise ValueError(f"REVIEW reason {record.decision_reason!r} is outside "
                         f"the declared vocabulary")
    if record.decision == DECISION_REJECTED \
            and record.decision_reason not in (
                REASON_UPSTREAM_DECISIVE_INVALID,
                REASON_D03_DEFINITE_DUPLICATE):
        raise ValueError(f"REJECTED reason {record.decision_reason!r} is "
                         f"outside the declared vocabulary")
    if record.decision == DECISION_ALREADY_CANONICALIZED \
            and record.decision_reason != REASON_D02_CAPTURE_REPLAY:
        raise ValueError("ALREADY_CANONICALIZED carries exactly the D-02 "
                         "capture-replay reason")
    if record.decision == DECISION_ACCEPTED \
            and record.decision_reason != REASON_ALL_FROZEN_CONDITIONS_MET:
        raise ValueError("ACCEPTED carries exactly the "
                         "all-frozen-conditions-met reason")
    if record.identity_class not in ("", IDENTITY_CLASS_DETERMINISTIC,
                                     IDENTITY_CLASS_CAPTURE_SCOPED):
        raise ValueError("identity_class outside the declared vocabulary")
    if record.identity_class == "" and record.identity_fingerprint != "":
        raise ValueError("an unrouted decision carries no identity "
                         "fingerprint")
    if record.decision == DECISION_REVIEW \
            and record.identity_class == IDENTITY_CLASS_DETERMINISTIC:
        raise ValueError("a DETERMINISTIC identity never routes REVIEW")


def route_summary(routes: Sequence[GateRoute]) -> str:
    """Stable rendering used by tests/audit (declarative, ordered)."""
    return " | ".join(f"{r.decision}/{r.reason}" for r in routes)
