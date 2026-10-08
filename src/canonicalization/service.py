"""Canonicalization Gate service — WP-6.1 MVP implementation.

Binding basis: SPEC-WP61-CANGATE §2/§3/§4/§6/§7/§8/§9. The entry point and
orchestration layer: verified P5.2 domain states + verified WP-4.1 reads +
declared requests → explicit gate decisions → (only when every frozen
condition holds) the durable Canonical Invoice admission record.

Fail-closed ordering (SPEC §4): input verification (V1 verified P5.2 read →
V2 whole-chain trace → V3 origin validation → V4 binding validation) precedes
EVERY decision; replay (G0) precedes routing (G1..G6); the admission commits
atomically (OD-C2). No outcome is ever silent; no refusal leaves residue; no
upstream layer is ever executed (spy-proven).
"""
from __future__ import annotations

from typing import List, Mapping, Optional

from capture import S1Service
from normalization import (
    NormalizationReadIntegrityFailure,
    NormalizationReadRefused,
    NormalizationReadSuccess,
    NormalizationReadVerificationUnavailable,
    NormalizationService,
)
from normalization.model import NormalizationStatus
from validation_domain import (
    DomainStateReadIntegrityFailure,
    DomainStateReadRefused,
    DomainStateReadSuccess,
    DomainStateReadVerificationUnavailable,
    DomainStateTraceIntegrityFailure,
    DomainStateTraceRefused,
    DomainStateTraceSuccess,
    DomainStateTraceVerificationUnavailable,
    ValidationDomainService,
)

from .gate import route_decision, validate_route
from .identity import resolve_identity, validate_binding
from .model import (
    DECISION_ACCEPTED,
    DECISION_REVIEW,
    EVENT_TYPES,
    IDENTITY_CLASS_UNROUTED,
    IdentityResolution,
    NOTE_VERIFY_FAILED,
    REVIEW_STATUS_CLOSED,
    CanonicalIdentityPointer,
    CanonicalInvoiceReadIntegrityFailure,
    CanonicalInvoiceReadRefused,
    CanonicalInvoiceReadSuccess,
    CanonicalInvoiceReadVerificationUnavailable,
    CanonicalInvoiceNotFound,
    CanonicalInvoiceRecord,
    CanonicalInvoiceTraceIntegrityFailure,
    CanonicalInvoiceTraceRefused,
    CanonicalInvoiceTraceSuccess,
    CanonicalInvoiceTraceVerificationUnavailable,
    CanonicalizationAccepted,
    CanonicalizationAlreadyCanonicalized,
    CanonicalizationAlreadyDecided,
    CanonicalizationInputIntegrityFailure,
    CanonicalizationPersistenceUnavailable,
    CanonicalizationRejected,
    CanonicalizationRequestRefused,
    CanonicalizationRoutedToReview,
    CanonicalizationStorageUnavailable,
    GateDecisionDuplicate,
    GateDecisionNotFound,
    GateDecisionReadIntegrityFailure,
    GateDecisionReadRefused,
    GateDecisionReadSuccess,
    GateDecisionReadVerificationUnavailable,
    GateDecisionRecord,
    GateEventAppended,
    GateEventRefused,
    GateEventUnavailable,
    GateReviewItem,
    GateReviewItemNotFound,
    GateReviewItemReadIntegrityFailure,
    GateReviewItemReadRefused,
    GateReviewItemReadSuccess,
    GateReviewItemReadVerificationUnavailable,
    GateReviewEvent,
    utc_now_iso,
)
from .store import (
    CanonicalizationGateStore,
    canonical_decision_bytes,
    canonical_invoice_bytes,
    canonical_item_bytes,
    canonical_event_bytes,
)

import uuid


class CanonicalizationGateService:
    """The WP-6.1 entry point: verified P5.2 domain states → deterministic
    gate decisions → Canonical Invoice admission records + a durable gate
    REVIEW queue with complete provenance."""

    def __init__(self, store: CanonicalizationGateStore,
                 domain: ValidationDomainService,
                 normalization: NormalizationService,
                 s1: S1Service) -> None:
        self._store = store
        self._domain = domain
        self._normalization = normalization
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # The Gate — canonicalize (SPEC §3/§4)
    # ------------------------------------------------------------------

    def canonicalize(self, domain_state_id: str, declared_origin: str,
                     identity_field_binding: Optional[Mapping[str, str]] = None,
                     ) -> object:
        """Gate one verified P5.2 domain state into the Canonical Invoice
        domain. Outcome is exactly one explicit type — never silent:
          CanonicalizationAccepted | CanonicalizationRejected |
          CanonicalizationRoutedToReview | CanonicalizationAlreadyCanonicalized |
          CanonicalizationAlreadyDecided |
          CanonicalizationInputIntegrityFailure |
          CanonicalizationRequestRefused | CanonicalizationStorageUnavailable.
        """
        # -- V1: verified P5.2 read (fail-closed — no decision on unverified
        # input, even if a prior decision exists)
        head = self._domain.read_domain_state(domain_state_id)
        if isinstance(head, DomainStateReadRefused):
            return CanonicalizationRequestRefused(
                domain_state_id,
                f"no such domain state record: {head.detail}")
        if isinstance(head, DomainStateReadIntegrityFailure):
            return CanonicalizationInputIntegrityFailure(
                domain_state_id, head.reason)
        if isinstance(head, DomainStateReadVerificationUnavailable):
            self._issues.append(f"canonicalize {domain_state_id}: "
                                f"{head.issue_report}")
            return CanonicalizationInputIntegrityFailure(
                domain_state_id, head.issue_report)
        state_record = head.record

        # -- V2: whole-chain provenance verification (consumed through the
        # P5.2 trace — never bypassed; no broken link silently accepted)
        walk = self._domain.trace_domain_state(domain_state_id)
        if isinstance(walk, DomainStateTraceRefused):
            return CanonicalizationInputIntegrityFailure(
                domain_state_id, f"provenance walk refused: {walk.detail}")
        if isinstance(walk, DomainStateTraceIntegrityFailure):
            return CanonicalizationInputIntegrityFailure(
                domain_state_id,
                f"broken provenance chain at link '{walk.link}': {walk.reason}")
        if isinstance(walk, DomainStateTraceVerificationUnavailable):
            self._issues.append(f"canonicalize {domain_state_id}: "
                                f"{walk.issue_report}")
            return CanonicalizationInputIntegrityFailure(
                domain_state_id,
                f"provenance verification unavailable: {walk.issue_report}")

        # -- V3: declared origin validation (frozen vocabulary; OD-G6)
        from .model import ORIGINS, CAPTURE_PIPELINE_ORIGINS, \
            REFUSE_ORIGIN_UNKNOWN, REFUSE_ORIGIN_NATIVE_FLOW
        if declared_origin not in ORIGINS:
            return CanonicalizationRequestRefused(
                domain_state_id,
                f"declared_origin {declared_origin!r} is outside the frozen "
                f"origin vocabulary "
                f"(KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE)")
        if declared_origin not in CAPTURE_PIPELINE_ORIGINS:
            return CanonicalizationRequestRefused(
                domain_state_id,
                f"declared_origin {declared_origin!r} is the native-flow "
                f"origin (AS-02: no capture pipeline, no P5.2 state) — not "
                f"consumable from a P5.2-sourced request")

        # -- V4: declared binding validation (fail-closed, never 'repaired')
        try:
            validate_binding(identity_field_binding)
        except ValueError as exc:
            return CanonicalizationRequestRefused(
                domain_state_id, f"{exc}")

        # -- G0: replay — an existing decision for this state returns verbatim
        # (read-only; D-03 idempotency: a replay never re-decides)
        existing = self._store.find_decision_by_state(domain_state_id)
        if existing is not None:
            return CanonicalizationAlreadyDecided(existing)

        upstream_review_id = head.review_item.review_id \
            if head.review_item is not None else None

        # -- Routing (G1..G6) over verified facts only
        identity = None
        if state_record.domain_state == "VALID":
            resolved = self._resolve_identity_verified(
                state_record, declared_origin, identity_field_binding)
            if not isinstance(resolved, IdentityResolution):
                return resolved       # verified-read or binding refusal
            identity = resolved

        capture_invoice = self._store.get_invoice_by_capture(
            state_record.capture_s1)
        identity_invoice = None
        if identity is not None and identity.identity_fingerprint:
            identity_invoice = self._store.get_invoice_by_identity(
                identity.identity_fingerprint)
        route = route_decision(
            state_record, identity,
            capture_invoice_exists=capture_invoice is not None,
            identity_invoice_exists=identity_invoice is not None,
            upstream_review_id=upstream_review_id)

        decision = GateDecisionRecord(
            decision_id=uuid.uuid4().hex,
            domain_state_id=state_record.domain_state_id,
            normalization_id=state_record.normalization_id,
            extraction_id=state_record.extraction_id,
            document_id=state_record.document_id,
            capture_id=state_record.capture_id,
            capture_s1=state_record.capture_s1,
            capture_s1_algorithm_id=state_record.capture_s1_algorithm_id,
            declared_origin=declared_origin,
            decision=route.decision,
            decision_reason=route.reason,
            decision_detail=route.detail,
            identity_class=identity.identity_class
            if identity is not None else IDENTITY_CLASS_UNROUTED,
            identity_source=identity.identity_source
            if identity is not None else "",
            identity_fingerprint=identity.identity_fingerprint
            if identity is not None else "",
            canonical_invoice_id=None,
            upstream_review_id=upstream_review_id,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="",
        )

        invoice: Optional[CanonicalInvoiceRecord] = None
        pointers: List[CanonicalIdentityPointer] = []
        review_item: Optional[GateReviewItem] = None
        if route.decision == DECISION_ACCEPTED:
            invoice_id = uuid.uuid4().hex
            decision = GateDecisionRecord(
                **{**decision.__dict__, "canonical_invoice_id": invoice_id})
            invoice = CanonicalInvoiceRecord(
                canonical_invoice_id=invoice_id,
                decision_id=decision.decision_id,
                domain_state_id=state_record.domain_state_id,
                normalization_id=state_record.normalization_id,
                extraction_id=state_record.extraction_id,
                document_id=state_record.document_id,
                capture_id=state_record.capture_id,
                capture_s1=state_record.capture_s1,
                capture_s1_algorithm_id=state_record.capture_s1_algorithm_id,
                origin=declared_origin,
                identity_class=identity.identity_class,
                identity_source=identity.identity_source,
                identity_fingerprint=identity.identity_fingerprint,
                created_at=utc_now_iso(),
                record_fingerprint="",
                fingerprint_algorithm_id="",
            )
            pointers = [
                CanonicalIdentityPointer(
                    canonical_invoice_id=invoice_id,
                    role=spec["role"],
                    source_field_name=spec["source_field_name"],
                    normalization_id=state_record.normalization_id,
                    field_seq=spec["field_seq"])
                for spec in identity.pointer_specs]
        elif route.decision == DECISION_REVIEW:
            review_item = GateReviewItem(
                review_id=uuid.uuid4().hex,
                decision_id=decision.decision_id,
                domain_state_id=state_record.domain_state_id,
                normalization_id=state_record.normalization_id,
                extraction_id=state_record.extraction_id,
                document_id=state_record.document_id,
                capture_id=state_record.capture_id,
                capture_s1=state_record.capture_s1,
                review_reason=route.reason,
                review_detail=route.detail,
                created_at=utc_now_iso(),
                item_fingerprint="",
                fingerprint_algorithm_id="",
            )

        try:
            validate_route(decision)
            saved = self._store.commit_decision(decision, invoice, pointers,
                                                review_item)
        except GateDecisionDuplicate as exc:
            prior = self._store.get_decision(exc.existing_id)
            return CanonicalizationAlreadyDecided(prior)
        except CanonicalizationPersistenceUnavailable as exc:
            return CanonicalizationStorageUnavailable(str(exc))

        if route.decision == DECISION_ACCEPTED:
            saved_invoice = self._store.get_invoice_by_decision(
                saved.decision_id)
            saved_pointers = self._store.get_pointers(invoice_id)
            return CanonicalizationAccepted(saved, saved_invoice,
                                            tuple(saved_pointers))
        if route.decision == DECISION_REVIEW:
            saved_item = self._store.get_review_item_by_decision(
                saved.decision_id)
            return CanonicalizationRoutedToReview(saved, saved_item)
        if route.decision == "REJECTED":
            return CanonicalizationRejected(saved)
        # ALREADY_CANONICALIZED — return the pre-existing invoice
        existing_invoice = self._store.get_invoice_by_capture(
            state_record.capture_s1)
        return CanonicalizationAlreadyCanonicalized(saved, existing_invoice)

    def _resolve_identity_verified(self, state_record,
                                   declared_origin: str,
                                   identity_field_binding) -> object:
        """Identity resolution over VERIFIED reads only (SPEC §5). A verified
        normalization read is the only sanctioned value-level fact path; any
        read failure fails the whole request closed (no identity is ever
        resolved from unverified facts)."""
        norm_read = self._normalization.read_normalization(
            state_record.normalization_id)
        if isinstance(norm_read, NormalizationReadIntegrityFailure):
            return CanonicalizationInputIntegrityFailure(
                state_record.domain_state_id,
                f"normalization read failed verification: {norm_read.reason}")
        if isinstance(norm_read, NormalizationReadRefused):
            return CanonicalizationInputIntegrityFailure(
                state_record.domain_state_id,
                f"normalization read refused: {norm_read.detail}")
        if isinstance(norm_read, NormalizationReadVerificationUnavailable):
            self._issues.append(
                f"canonicalize {state_record.domain_state_id}: "
                f"{norm_read.issue_report}")
            return CanonicalizationInputIntegrityFailure(
                state_record.domain_state_id, norm_read.issue_report)
        assert isinstance(norm_read, NormalizationReadSuccess)
        try:
            return resolve_identity(identity_field_binding, norm_read.fields,
                                    declared_origin, self._s1)
        except ValueError as exc:
            return CanonicalizationRequestRefused(
                state_record.domain_state_id, str(exc))

    # ------------------------------------------------------------------
    # Verified reads (VOR — SPEC §8)
    # ------------------------------------------------------------------

    def _verify(self, payload: bytes, fingerprint: str, algorithm_id: str) \
            -> Optional[str]:
        """Returns None when VERIFIED; a refusal reason string otherwise
        ('FAILED' distinguishes tamper from capability loss)."""
        verdict = self._s1.verify(payload, fingerprint, algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            return f"verification unavailable: " \
                   f"{verdict.reason or 'capability failure'}"
        if verdict.outcome == "FAILED":
            return NOTE_VERIFY_FAILED
        return None

    def read_gate_decision(self, decision_id: str) -> object:
        """Read a gate decision with a definitive integrity verdict computed
        INSIDE the read (decision + its rides: invoice/pointers or review
        item + derived status)."""
        try:
            record = self._store.get_decision(decision_id)
        except GateDecisionNotFound:
            return GateDecisionReadRefused(None, "no such gate decision")
        problem = self._verify(canonical_decision_bytes(record),
                               record.record_fingerprint,
                               record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return GateDecisionReadIntegrityFailure(
                    decision_id, problem, utc_now_iso())
            self._issues.append(f"gate decision {decision_id}: {problem}")
            return GateDecisionReadVerificationUnavailable(
                decision_id, problem + " — Issue Report required")
        invoice: Optional[CanonicalInvoiceRecord] = None
        pointers = ()
        if record.decision == DECISION_ACCEPTED:
            invoice = self._store.get_invoice_by_decision(decision_id)
            if invoice is None:
                issue = ("durable admission set inconsistent: an ACCEPTED "
                         "decision without its canonical invoice (INV-CI-1:1)")
                self._issues.append(f"gate decision {decision_id}: {issue}")
                return GateDecisionReadVerificationUnavailable(
                    decision_id, issue + " — Issue Report required")
            pointers = tuple(self._store.get_pointers(
                invoice.canonical_invoice_id))
            iproblem = self._verify(
                canonical_invoice_bytes(invoice, pointers),
                invoice.record_fingerprint, invoice.fingerprint_algorithm_id)
            if iproblem is not None:
                if iproblem == NOTE_VERIFY_FAILED:
                    return GateDecisionReadIntegrityFailure(
                        decision_id,
                        f"linked canonical invoice {iproblem}",
                        utc_now_iso())
                self._issues.append(
                    f"gate decision {decision_id}: {iproblem}")
                return GateDecisionReadVerificationUnavailable(
                    decision_id, iproblem + " — Issue Report required")
        item: Optional[GateReviewItem] = None
        review_status: Optional[str] = None
        if record.decision == DECISION_REVIEW:
            item = self._store.get_review_item_by_decision(decision_id)
            if item is None:
                issue = ("durable review set inconsistent: a REVIEW decision "
                         "without its queue item (INV-GR-1:1)")
                self._issues.append(f"gate decision {decision_id}: {issue}")
                return GateDecisionReadVerificationUnavailable(
                    decision_id, issue + " — Issue Report required")
            item_read = self.read_gate_review_item(item.review_id)
            if isinstance(item_read, GateReviewItemReadRefused):
                return GateDecisionReadVerificationUnavailable(
                    decision_id, item_read.detail + " — Issue Report required")
            if isinstance(item_read, GateReviewItemReadIntegrityFailure):
                return GateDecisionReadIntegrityFailure(
                    decision_id,
                    f"linked review item failed verification: "
                    f"{item_read.reason}", utc_now_iso())
            if isinstance(item_read, GateReviewItemReadVerificationUnavailable):
                self._issues.append(f"gate decision {decision_id}: "
                                    f"{item_read.issue_report}")
                return GateDecisionReadVerificationUnavailable(
                    decision_id, item_read.issue_report +
                    " — Issue Report required")
            review_status = item_read.status
        return GateDecisionReadSuccess(record, invoice, pointers, item,
                                       review_status, utc_now_iso())

    def read_canonical_invoice(self, canonical_invoice_id: str) -> object:
        """Read a Canonical Invoice admission record with a definitive
        integrity verdict computed INSIDE the read (invoice + pointers + the
        linked decision's verified read)."""
        try:
            record = self._store.get_invoice(canonical_invoice_id)
        except CanonicalInvoiceNotFound:
            return CanonicalInvoiceReadRefused(
                None, "no such canonical invoice")
        pointers = tuple(self._store.get_pointers(canonical_invoice_id))
        problem = self._verify(canonical_invoice_bytes(record, pointers),
                               record.record_fingerprint,
                               record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return CanonicalInvoiceReadIntegrityFailure(
                    canonical_invoice_id, problem, utc_now_iso())
            self._issues.append(f"canonical invoice {canonical_invoice_id}: "
                                f"{problem}")
            return CanonicalInvoiceReadVerificationUnavailable(
                canonical_invoice_id, problem + " — Issue Report required")
        if len(pointers) != 3:
            issue = (f"durable identity pointer set inconsistent "
                     f"(rows={len(pointers)}, expected 3)")
            self._issues.append(f"canonical invoice {canonical_invoice_id}: "
                                f"{issue}")
            return CanonicalInvoiceReadVerificationUnavailable(
                canonical_invoice_id, issue + " — Issue Report required")
        try:
            decision = self._store.get_decision(record.decision_id)
        except GateDecisionNotFound:
            issue = "linked gate decision is missing (INV-CI-1:1)"
            self._issues.append(f"canonical invoice {canonical_invoice_id}: "
                                f"{issue}")
            return CanonicalInvoiceReadVerificationUnavailable(
                canonical_invoice_id, issue + " — Issue Report required")
        dproblem = self._verify(canonical_decision_bytes(decision),
                                decision.record_fingerprint,
                                decision.fingerprint_algorithm_id)
        if dproblem is not None:
            if dproblem == NOTE_VERIFY_FAILED:
                return CanonicalInvoiceReadIntegrityFailure(
                    canonical_invoice_id,
                    f"linked decision {dproblem}", utc_now_iso())
            self._issues.append(f"canonical invoice {canonical_invoice_id}: "
                                f"{dproblem}")
            return CanonicalInvoiceReadVerificationUnavailable(
                canonical_invoice_id, dproblem + " — Issue Report required")
        if decision.decision != DECISION_ACCEPTED or \
                decision.canonical_invoice_id != canonical_invoice_id:
            issue = "linked decision is not the ACCEPTED decision of this " \
                    "invoice (INV-CI-1:1)"
            self._issues.append(f"canonical invoice {canonical_invoice_id}: "
                                f"{issue}")
            return CanonicalInvoiceReadVerificationUnavailable(
                canonical_invoice_id, issue + " — Issue Report required")
        return CanonicalInvoiceReadSuccess(record, pointers, decision,
                                           utc_now_iso())

    def read_gate_review_item(self, review_id: str) -> object:
        """Read a gate REVIEW item + full event history + derived status with
        the integrity verdict computed INSIDE the read (item fingerprint +
        the per-item event hash chain)."""
        try:
            item = self._store.get_item_by_review_id(review_id)
        except GateReviewItemNotFound:
            return GateReviewItemReadRefused(None, "no such review item")
        problem = self._verify(canonical_item_bytes(item),
                               item.item_fingerprint,
                               item.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return GateReviewItemReadIntegrityFailure(
                    review_id, problem, utc_now_iso())
            self._issues.append(f"gate review {review_id}: {problem}")
            return GateReviewItemReadVerificationUnavailable(
                review_id, problem + " — Issue Report required")
        events = self._store.get_events(review_id)
        prev_fp = ""
        for event in events:
            chain_ok = (event.prev_event_fingerprint == prev_fp)
            eproblem = self._verify(canonical_event_bytes(event),
                                    event.event_fingerprint,
                                    event.fingerprint_algorithm_id)
            if eproblem is not None:
                if eproblem == NOTE_VERIFY_FAILED:
                    return GateReviewItemReadIntegrityFailure(
                        review_id,
                        f"event chain verify FAILED at seq {event.event_seq}",
                        utc_now_iso())
                self._issues.append(f"gate review {review_id}: {eproblem}")
                return GateReviewItemReadVerificationUnavailable(
                    review_id, eproblem + " — Issue Report required")
            if not chain_ok:
                return GateReviewItemReadIntegrityFailure(
                    review_id,
                    f"event chain broken at seq {event.event_seq}",
                    utc_now_iso())
            prev_fp = event.event_fingerprint
        status = REVIEW_STATUS_CLOSED if self._store.has_close_event(review_id) \
            else "OPEN"
        return GateReviewItemReadSuccess(item, tuple(events), status,
                                         utc_now_iso())

    # ------------------------------------------------------------------
    # Gate REVIEW lifecycle — append-only, terminal CLOSE, never a resolver
    # ------------------------------------------------------------------

    def append_gate_review_event(self, review_id: str, event_type: str,
                                 note: str, actor: str) -> object:
        """Record one explicit external lifecycle act on a gate REVIEW item.
        Outcome is exactly one explicit type:
          GateEventAppended | GateEventRefused | GateEventUnavailable.
        The event records that an external actor annotated/closed the item —
        the decision itself lives outside this layer (the queue is NOT a
        semantic resolver). CLOSE is terminal."""
        if event_type not in EVENT_TYPES:
            return GateEventRefused(
                review_id,
                f"unknown event type {event_type!r} — the declared lifecycle "
                f"vocabulary is ANNOTATE | CLOSE")
        if not actor:
            return GateEventRefused(review_id,
                                    "an event actor is required (opaque "
                                    "string, recorded verbatim)")
        item_read = self.read_gate_review_item(review_id)
        if isinstance(item_read, GateReviewItemReadRefused):
            return GateEventRefused(review_id, item_read.detail)
        if isinstance(item_read, GateReviewItemReadIntegrityFailure):
            return GateEventRefused(
                review_id,
                f"item failed its verified read — event refused: "
                f"{item_read.reason}")
        if isinstance(item_read, GateReviewItemReadVerificationUnavailable):
            self._issues.append(f"gate review {review_id}: "
                                f"{item_read.issue_report}")
            return GateEventUnavailable(review_id, item_read.issue_report)
        if item_read.status == REVIEW_STATUS_CLOSED:
            return GateEventRefused(
                review_id,
                "item is CLOSED — the lifecycle is terminal; history is "
                "append-only and never rewritten")
        # fail-closed: the parent decision AND the parent's P5.2 state must
        # still verify — broken provenance freezes the queue item
        parent = self.read_gate_decision(item_read.item.decision_id)
        if isinstance(parent, GateDecisionReadIntegrityFailure):
            return GateEventRefused(
                review_id,
                f"parent decision failed its verified read — event refused: "
                f"{parent.reason}")
        if isinstance(parent, GateDecisionReadVerificationUnavailable):
            self._issues.append(f"gate review {review_id}: "
                                f"{parent.issue_report}")
            return GateEventUnavailable(review_id, parent.issue_report)
        parent_state = self._domain.read_domain_state(
            item_read.item.domain_state_id)
        if isinstance(parent_state, DomainStateReadIntegrityFailure):
            return GateEventRefused(
                review_id,
                f"parent P5.2 state failed its verified read — event "
                f"refused: {parent_state.reason}")
        if isinstance(parent_state, DomainStateReadVerificationUnavailable):
            self._issues.append(f"gate review {review_id}: "
                                f"{parent_state.issue_report}")
            return GateEventUnavailable(review_id, parent_state.issue_report)
        events = item_read.events
        event = GateReviewEvent(
            event_id=uuid.uuid4().hex,
            review_id=review_id,
            event_seq=len(events),
            event_type=event_type,
            event_note=note,
            event_actor=actor,
            created_at=utc_now_iso(),
            prev_event_fingerprint=self._store.chain_tail(review_id) or "",
            event_fingerprint="",
            fingerprint_algorithm_id="",
        )
        try:
            saved = self._store.append_event(event)
        except CanonicalizationPersistenceUnavailable as exc:
            return GateEventUnavailable(review_id, str(exc))
        status = REVIEW_STATUS_CLOSED if saved.event_type == "CLOSE" \
            else "OPEN"
        return GateEventAppended(saved, status)

    # ------------------------------------------------------------------
    # Traceability walk — canonical invoice → gate decision → P5.2
    # whole-chain (→ … → Capture S1) + identity pointer re-join (SPEC §9)
    # ------------------------------------------------------------------

    def trace_canonical_invoice(self, canonical_invoice_id: str) -> object:
        """Walk the full provenance chain with verified reads on EVERY link
        inside this one call. The P5.2 whole-chain trace is consumed, never
        bypassed. Deliverable: ordered coarse link verdicts (no source values
        copied)."""
        head = self.read_canonical_invoice(canonical_invoice_id)
        if isinstance(head, CanonicalInvoiceReadIntegrityFailure):
            return CanonicalInvoiceTraceIntegrityFailure(
                canonical_invoice_id, "canonical_invoice", head.reason)
        if isinstance(head, CanonicalInvoiceReadRefused):
            return CanonicalInvoiceTraceRefused(canonical_invoice_id,
                                                head.detail)
        if isinstance(head, CanonicalInvoiceReadVerificationUnavailable):
            self._issues.append(f"trace {canonical_invoice_id}: "
                                f"{head.issue_report}")
            return CanonicalInvoiceTraceVerificationUnavailable(
                canonical_invoice_id, head.issue_report)
        record, pointers, decision = head.record, head.identity_pointers, \
            head.decision

        chain: List[str] = [
            f"canonical_invoice: {record.canonical_invoice_id[:12]}… "
            f"origin={record.origin} identity={record.identity_class}/"
            f"{record.identity_source} fp="
            f"{record.identity_fingerprint[:12]}…",
        ]

        # link: gate decision (verified inside the invoice read; walk explicitly)
        dhead = self.read_gate_decision(decision.decision_id)
        if isinstance(dhead, GateDecisionReadIntegrityFailure):
            return CanonicalInvoiceTraceIntegrityFailure(
                canonical_invoice_id, "gate_decision", dhead.reason)
        if isinstance(dhead, GateDecisionReadVerificationUnavailable):
            self._issues.append(f"trace {canonical_invoice_id}: "
                                f"{dhead.issue_report}")
            return CanonicalInvoiceTraceVerificationUnavailable(
                canonical_invoice_id, dhead.issue_report)
        chain.append(
            f"gate_decision: {decision.decision}/{decision.decision_reason} "
            f"origin={decision.declared_origin} "
            f"(verified in this walk)")

        # link: the P5.2 whole-chain sub-walk — consumed, never bypassed
        walk = self._domain.trace_domain_state(decision.domain_state_id)
        if isinstance(walk, DomainStateTraceIntegrityFailure):
            return CanonicalInvoiceTraceIntegrityFailure(
                canonical_invoice_id, "domain_state",
                f"link '{walk.link}': {walk.reason}")
        if isinstance(walk, DomainStateTraceRefused):
            return CanonicalInvoiceTraceRefused(
                canonical_invoice_id,
                f"P5.2 walk refused: {walk.detail}")
        if isinstance(walk, DomainStateTraceVerificationUnavailable):
            self._issues.append(f"trace {canonical_invoice_id}: "
                                f"{walk.issue_report}")
            return CanonicalInvoiceTraceVerificationUnavailable(
                canonical_invoice_id, walk.issue_report)
        chain.append(
            f"domain_state: P5.2 whole-chain re-verified in this walk "
            f"({len(walk.chain)} links, through WP-5.1 sub-walks incl. WP-4.2 "
            f"to Capture S1)")
        chain.extend(f"  ↳ {link}" for link in walk.chain)

        # link: identity pointer re-join through the verified normalization read
        norm_read = self._normalization.read_normalization(
            record.normalization_id)
        if isinstance(norm_read, NormalizationReadIntegrityFailure):
            return CanonicalInvoiceTraceIntegrityFailure(
                canonical_invoice_id, "identity_pointers", norm_read.reason)
        if isinstance(norm_read, NormalizationReadRefused):
            return CanonicalInvoiceTraceRefused(
                canonical_invoice_id,
                f"normalization read refused: {norm_read.detail}")
        if isinstance(norm_read, NormalizationReadVerificationUnavailable):
            self._issues.append(f"trace {canonical_invoice_id}: "
                                f"{norm_read.issue_report}")
            return CanonicalInvoiceTraceVerificationUnavailable(
                canonical_invoice_id, norm_read.issue_report)
        by_key = {(f.source_field_name, f.field_seq): f
                  for f in norm_read.fields}
        for p in pointers:
            f = by_key.get((p.source_field_name, p.field_seq))
            if f is None or f.status != NormalizationStatus.NORMALIZED:
                return CanonicalInvoiceTraceIntegrityFailure(
                    canonical_invoice_id, "identity_pointers",
                    f"pointer {p.role} → {p.source_field_name}/"
                    f"{p.field_seq} does not re-join a NORMALIZED row in the "
                    f"verified read")
        chain.append(
            f"identity_pointers: {len(pointers)} role pointers re-joined "
            f"NORMALIZED rows in the verified read")

        return CanonicalInvoiceTraceSuccess(canonical_invoice_id,
                                            tuple(chain), utc_now_iso())

    # ------------------------------------------------------------------
    # Listing helpers (tests / smoke / operator tooling)
    # ------------------------------------------------------------------

    def canonical_invoices(self) -> List[CanonicalInvoiceRecord]:
        rows = self._store._conn.execute(
            "SELECT * FROM canonical_invoices ORDER BY created_at, "
            "canonical_invoice_id").fetchall()
        from .store import _invoice_from_row
        return [_invoice_from_row(r) for r in rows]

    def decisions(self) -> List[GateDecisionRecord]:
        return self._store.list_decisions()

    def list_gate_review_items(self) -> List[GateReviewItem]:
        return self._store.list_review_items()

    def issue_reports(self) -> list:
        return list(self._issues)
