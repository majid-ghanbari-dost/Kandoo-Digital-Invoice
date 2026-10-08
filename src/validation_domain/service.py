"""Validation-domain service — verified P5.1 outcomes → deterministic frozen-
vocabulary states + durable REVIEW queue (WP-5.2 MVP).

Binding basis: SPEC-WP52-VSM §2/§3/§4/§5/§8/§10; SPEC-WP51-VAL analog (verified
reads are the ONLY sanctioned input paths — P5.1 rule outcomes via the validation
service's VOR read, NORMALIZED field facts via the frozen WP-4.1 read, rule
declarations via the frozen WP-5.1 registry; this service never touches any store
directly and never re-reads raw artifacts); D-01 (UNRESOLVED created HERE, field-
level, strictly per the resolution order — never auto-resolved); D-08 (mismatch →
REVIEW); D-03 (ambiguous/conflicting → REVIEW); D-09 (delegated details declared:
OD-S1..OD-S14); AD-04 (REVIEW/REJECT output model); AS-03 (verbatim frozen
vocabulary — no state invented, renamed, or added).

  project_domain_state(normalization_id, ruleset_id, ruleset_version, rule_keys):
    verified normalization read (fail-closed) → verified reads of ALL P5.1 records
    for the normalization → completeness gate (declared keys == evaluated set) →
    declaration fingerprint check (drift = integrity failure) → ruleset
    fingerprint (OD-S12) → INV-S-1:1 pre-check → field-level D-01 projection (§4)
    → transition function (§3) → atomic commit (state record + refs + field rows
    + REVIEW item iff disposition REVIEW).

  read_domain_state / read_review_item:
    VOR-pattern verified reads — fingerprints recomputed over the durable rows
    INSIDE the read; content delivered only on the same-read VALID verdict;
    review status derived from the append-only event history.

  append_review_event:
    explicit external lifecycle act (ANNOTATE | CLOSE) recorded append-only with
    hash-chain verification and terminality enforcement — never a semantic
    resolution.

  trace_domain_state:
    whole-chain provenance walk (SPEC §10) — every P5.1 ref walked through the
    WP-5.1 whole-chain trace (P4.2 sub-chains consumed, never bypassed); tail
    re-verified down to Capture S1.

The service owns orchestration only; every durable effect goes through the store;
every fingerprint goes through the reused capture S1 capability (sha256-v1). No
canonical mapping, no association decision, no business datum, no new value, no
semantic resolution anywhere.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from capture import S1Service
from extraction import (
    BindingReadIntegrityFailure,
    BindingReadRefused,
    BindingReadSuccess,
    BindingReadVerificationUnavailable,
    ExtractionReadIntegrityFailure,
    ExtractionReadRefused,
    ExtractionReadSuccess,
    ExtractionReadVerificationUnavailable,
    ExtractionService,
    ExtractionEvidenceBinder,
)
from normalization import (
    NormalizationReadIntegrityFailure,
    NormalizationReadRefused,
    NormalizationReadSuccess,
    NormalizationReadVerificationUnavailable,
    NormalizationService,
    NormalizationStatus,
)
from reconstruction import (
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadSuccess,
    DocumentReadVerificationUnavailable,
    ReconstructionService,
)
from validation import (
    ValidationReadIntegrityFailure,
    ValidationReadRefused,
    ValidationReadSuccess,
    ValidationReadVerificationUnavailable,
    ValidationService,
    ValidationTraceIntegrityFailure,
    ValidationTraceRefused,
    ValidationTraceSuccess,
    ValidationTraceVerificationUnavailable,
)

from .machine import (
    build_state_record,
    derive_state,
    project_fields,
    ruleset_fingerprint,
)
from .model import (
    DISPOSITION_REVIEW,
    DOMAIN_STATE_INVALID,
    EVENT_TYPES,
    NOTE_VERIFY_FAILED,
    PROJECTION_RESOLVED,
    REVIEW_STATUS_CLOSED,
    REVIEW_STATUS_OPEN,
    DomainStateAlreadyExists,
    DomainStateDuplicate,
    DomainStateNotFound,
    DomainStatePersistenceUnavailable,
    DomainStateProjected,
    DomainStateReadIntegrityFailure,
    DomainStateReadRefused,
    DomainStateReadSuccess,
    DomainStateReadVerificationUnavailable,
    DomainStateRecord,
    DomainStateSourceIntegrityFailure,
    DomainStateSourceRefused,
    DomainStateSourceUnavailable,
    DomainStateStorageUnavailable,
    DomainStateTraceIntegrityFailure,
    DomainStateTraceRefused,
    DomainStateTraceSuccess,
    DomainStateTraceVerificationUnavailable,
    FieldProjectionRow,
    ReviewEventAppended,
    ReviewEventRefused,
    ReviewEventUnavailable,
    ReviewItemReadIntegrityFailure,
    ReviewItemReadRefused,
    ReviewItemReadSuccess,
    ReviewItemReadVerificationUnavailable,
    ReviewQueueEvent,
    ReviewQueueItem,
    StateValidationRef,
    utc_now_iso,
)
from .store import (
    ValidationDomainStore,
    canonical_event_bytes,
    canonical_item_bytes,
    canonical_state_bytes,
)

import uuid


class ValidationDomainService:
    """The WP-5.2 entry point: verified P5.1 evaluations → frozen-vocabulary
    domain states + durable REVIEW queue with complete provenance."""

    def __init__(self, store: ValidationDomainStore,
                 validation: ValidationService, registry,
                 normalization: NormalizationService,
                 extraction: ExtractionService,
                 binder: ExtractionEvidenceBinder,
                 reconstruction: ReconstructionService,
                 s1: S1Service) -> None:
        self._store = store
        self._validation = validation
        self._registry = registry
        self._normalization = normalization
        self._extraction = extraction
        self._binder = binder
        self._reconstruction = reconstruction
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Projection — verified P5.1 outcomes → frozen state → durable record
    # ------------------------------------------------------------------

    def project_domain_state(self, normalization_id: str, ruleset_id: str,
                             ruleset_version: str,
                             rule_keys: Sequence[Tuple[str, str]]) -> object:
        """Project one COMPLETE declared ruleset evaluation onto the frozen
        vocabulary. Outcome is exactly one explicit type — never silent:
          DomainStateProjected | DomainStateAlreadyExists (INV-S-1:1 replay) |
          DomainStateSourceIntegrityFailure | DomainStateSourceRefused |
          DomainStateSourceUnavailable | DomainStateStorageUnavailable.
        """
        if not rule_keys:
            return DomainStateSourceRefused(
                normalization_id,
                "empty ruleset declaration — a state is never projected from an "
                "empty evaluation")
        if len(set(rule_keys)) != len(rule_keys):
            return DomainStateSourceRefused(
                normalization_id,
                "duplicate rule keys in the ruleset declaration — each "
                "(rule_id, rule_version) is declared exactly once")

        # Step 1: verified normalization read — the ONLY sanctioned NORMALIZED
        # fact path (VOR: verdict computed inside the read; FAILED never
        # delivers content).
        read = self._normalization.read_normalization(normalization_id)
        if isinstance(read, NormalizationReadIntegrityFailure):
            return DomainStateSourceIntegrityFailure(normalization_id, read.reason)
        if isinstance(read, NormalizationReadRefused):
            return DomainStateSourceRefused(normalization_id,
                                            "no such normalization record")
        if isinstance(read, NormalizationReadVerificationUnavailable):
            self._issues.append(
                f"domain projection on {normalization_id}: {read.issue_report}")
            return DomainStateSourceUnavailable(normalization_id, read.issue_report)
        norm_record, norm_fields = read.record, read.fields

        # Step 2: verified reads of ALL P5.1 records for this normalization.
        existing_ids = self._validation.validations_for_normalization(normalization_id)
        if not existing_ids:
            return DomainStateSourceRefused(
                normalization_id,
                "no P5.1 validation records exist for this normalization — run "
                "the declared evaluation first (this layer never triggers "
                "validation)")
        consumed: List[Tuple[object, dict]] = []
        for vid in existing_ids:
            vread = self._validation.read_validation(vid)
            if isinstance(vread, ValidationReadIntegrityFailure):
                return DomainStateSourceIntegrityFailure(
                    normalization_id,
                    f"P5.1 validation {vid} failed its verified read: "
                    f"{vread.reason}")
            if isinstance(vread, ValidationReadRefused):
                return DomainStateSourceIntegrityFailure(
                    normalization_id,
                    f"P5.1 validation {vid} refused: {vread.detail}")
            if isinstance(vread, ValidationReadVerificationUnavailable):
                self._issues.append(
                    f"domain projection on {normalization_id}: "
                    f"{vread.issue_report}")
                return DomainStateSourceUnavailable(normalization_id,
                                                    vread.issue_report)
            record = vread.record
            consumed.append((record, {
                "rule_id": record.rule_id,
                "rule_version": record.rule_version,
                "outcome": record.outcome,
                "outcome_reason": record.outcome_reason,
                "outcome_detail": record.outcome_detail,
                "rule_kind": record.rule_kind,
                "rule_fingerprint": record.rule_fingerprint,
                "validation_id": record.validation_id,
                "inputs": tuple(vread.inputs),
            }))

        # Step 3: completeness gate — declared keys must EXACTLY equal the
        # evaluated set (missing keys AND extra records both refuse; SPEC §2).
        evaluated = {(c["rule_id"], c["rule_version"]) for _, c in consumed}
        declared = set(rule_keys)
        missing = [k for k in rule_keys if k not in evaluated]
        extra = sorted(evaluated - declared)
        if missing or extra:
            detail = []
            if missing:
                detail.append("declared but not evaluated: " + ", ".join(
                    f"{rid}/{rver}" for rid, rver in missing))
            if extra:
                detail.append("evaluated but not declared: " + ", ".join(
                    f"{rid}/{rver}" for rid, rver in extra))
            return DomainStateSourceRefused(
                normalization_id,
                "incomplete ruleset evaluation — a state is never projected from "
                "partial facts (" + "; ".join(detail) + ")")

        # Step 4: declaration fingerprint check — the registry declaration that
        # produced each record must be the exact fingerprinted version consumed.
        ordered: List[dict] = []
        for key in rule_keys:
            record, capsule = next(
                (rec, cap) for rec, cap in consumed
                if (cap["rule_id"], cap["rule_version"]) == key)
            declaration = self._registry.get(key[0], key[1])
            if declaration is None:
                return DomainStateSourceIntegrityFailure(
                    normalization_id,
                    f"rule {key[0]}/{key[1]} is not in the registry — declaration "
                    f"unavailable for projection")
            registry_fp = self._registry.fingerprint_of(key[0], key[1])
            if registry_fp != capsule["rule_fingerprint"]:
                return DomainStateSourceIntegrityFailure(
                    normalization_id,
                    f"rule declaration drift for {key[0]}/{key[1]}: registry "
                    f"fingerprint does not match the fingerprint anchored in the "
                    f"P5.1 record")
            ordered.append(capsule)

        # Step 5: scope consistency — every consumed record anchors the SAME
        # normalization scope (P5.1 copies these from the normalization record).
        anchors = {(c["validation_id"],
                    (rec.extraction_id, rec.document_id, rec.capture_id,
                     rec.capture_s1, rec.capture_s1_algorithm_id))
                   for rec, c in consumed}
        scoped = {a[1] for a in anchors}
        if len(scoped) != 1:
            return DomainStateSourceIntegrityFailure(
                normalization_id,
                "consumed P5.1 records disagree on the scope anchors "
                "(extraction/document/capture) — projection refused")
        extraction_id, document_id, capture_id, capture_s1, s1_alg = scoped.pop()

        # Step 6: ruleset fingerprint over the ruleset identity + the ordered
        # declared evaluation (OD-S12) + INV-S-1:1 pre-check (the atomic commit
        # backstops races).
        rs_fp, rs_alg = ruleset_fingerprint(
            ruleset_id, ruleset_version, rule_keys,
            [c["rule_fingerprint"] for c in ordered], self._s1)
        existing_state = self._store.find_by_pair(normalization_id, rs_fp)
        if existing_state is not None:
            return DomainStateAlreadyExists(existing_state, normalization_id,
                                            ruleset_id, ruleset_version)

        # Step 7: field-level D-01 projection (SPEC §4) — slot facts relayed from
        # the consumed records' input refs, backfill from the verified read.
        slot_facts: List[dict] = []
        for capsule in ordered:
            for ref in capsule["inputs"]:
                slot_facts.append({
                    "field_name": ref.field_name,
                    "value_origin": ref.value_origin,
                    "source_field_seq": ref.source_field_seq,
                    "source_derivation_id": ref.source_derivation_id,
                })
        declared_fields: List[str] = []
        for capsule in ordered:
            declaration = self._registry.get(capsule["rule_id"],
                                             capsule["rule_version"])
            for slot in declaration.inputs:
                if slot.field_name not in declared_fields:
                    declared_fields.append(slot.field_name)
        normalized_rows = [f for f in norm_fields
                           if f.status is NormalizationStatus.NORMALIZED]
        by_name: Dict[str, List[object]] = {}
        for f in normalized_rows:
            by_name.setdefault(f.source_field_name, []).append(f)
        all_rows_by_name: Dict[str, List[object]] = {}
        for f in norm_fields:
            all_rows_by_name.setdefault(f.source_field_name, []).append(f)
        backfill: Dict[str, Tuple[int, int]] = {}
        unresolved_notes: Dict[str, str] = {}
        slotted = {fact["field_name"] for fact in slot_facts}
        for field_name in declared_fields:
            if field_name in slotted:
                continue
            candidates = by_name.get(field_name, [])
            if candidates:
                lowest = min(f.field_seq for f in candidates)
                backfill[field_name] = (lowest, len(candidates))
                continue
            present = all_rows_by_name.get(field_name, [])
            if present:
                statuses = ", ".join(sorted({f.status.value for f in present}))
                unresolved_notes[field_name] = (
                    f"present in the source record but with no usable value "
                    f"(upstream status: {statuses})")

        domain_state_id = uuid.uuid4().hex
        field_rows, unresolved_count = project_fields(
            domain_state_id, declared_fields, normalization_id, extraction_id,
            slot_facts, backfill, unresolved_notes)

        # Step 8: the transition function (SPEC §3 — declared priority).
        domain_state, disposition, state_reason, state_detail = derive_state(
            [dict(rule_id=c["rule_id"], rule_version=c["rule_version"],
                  outcome=c["outcome"], outcome_reason=c["outcome_reason"],
                  outcome_detail=c["outcome_detail"])
             for c in ordered],
            unresolved_count)
        valid_count = sum(1 for c in ordered if c["outcome"] == "VALID")
        invalid_count = sum(1 for c in ordered if c["outcome"] == "INVALID")
        deferred_count = sum(1 for c in ordered if c["outcome"] == "DEFERRED")

        record = build_state_record(
            domain_state_id=domain_state_id,
            normalization_id=normalization_id,
            extraction_id=extraction_id,
            document_id=document_id,
            capture_id=capture_id,
            capture_s1=capture_s1,
            capture_s1_algorithm_id=s1_alg,
            ruleset_id=ruleset_id,
            ruleset_version=ruleset_version,
            ruleset_fingerprint=rs_fp,
            ruleset_fingerprint_algorithm_id=rs_alg,
            domain_state=domain_state,
            disposition=disposition,
            state_reason=state_reason,
            state_detail=state_detail,
            rule_count=len(ordered),
            valid_count=valid_count,
            invalid_count=invalid_count,
            deferred_count=deferred_count,
            unresolved_count=unresolved_count,
            created_at=utc_now_iso(),
        )
        refs = tuple(
            StateValidationRef(
                domain_state_id=domain_state_id,
                ord_slot=slot,
                validation_id=capsule["validation_id"],
                rule_id=capsule["rule_id"],
                rule_version=capsule["rule_version"],
                rule_kind=capsule["rule_kind"],
                rule_fingerprint=capsule["rule_fingerprint"],
                outcome=capsule["outcome"],
                outcome_reason=capsule["outcome_reason"],
            )
            for slot, capsule in enumerate(ordered))

        # Step 9: REVIEW item iff disposition REVIEW (INV-R-1:1 — SPEC §5).
        review_item: Optional[ReviewQueueItem] = None
        if disposition == DISPOSITION_REVIEW:
            review_item = ReviewQueueItem(
                review_id=uuid.uuid4().hex,
                domain_state_id=domain_state_id,
                normalization_id=normalization_id,
                extraction_id=extraction_id,
                document_id=document_id,
                capture_id=capture_id,
                capture_s1=capture_s1,
                ruleset_id=ruleset_id,
                ruleset_version=ruleset_version,
                ruleset_fingerprint=rs_fp,
                domain_state=domain_state,
                review_reason=state_reason,
                review_detail=state_detail,
                created_at=utc_now_iso(),
                item_fingerprint="",
                fingerprint_algorithm_id="",
            )

        # Step 10: atomic durable commit (record + refs + fields + item).
        try:
            saved = self._store.commit_projection(record, refs, field_rows,
                                                  review_item)
        except DomainStateDuplicate as exc:
            return DomainStateAlreadyExists(exc.domain_state_id, normalization_id,
                                            ruleset_id, ruleset_version)
        except DomainStatePersistenceUnavailable as exc:
            # OD-S2: atomic commit → zero residue in every persistence failure.
            return DomainStateStorageUnavailable(str(exc))
        return DomainStateProjected(saved, refs, field_rows, review_item)

    # ------------------------------------------------------------------
    # Verified reads — VOR pattern (SPEC §8)
    # ------------------------------------------------------------------

    def read_domain_state(self, domain_state_id: str) -> object:
        """Read a projection with a definitive integrity verdict computed INSIDE
        the read (record + refs + fields; the review item and its derived status
        ride along when present)."""
        try:
            record = self._store.get_record(domain_state_id)
        except DomainStateNotFound:
            return DomainStateReadRefused(None, "no such domain state record")
        refs = self._store.get_refs(domain_state_id)
        fields = self._store.get_fields(domain_state_id)
        if len(refs) != record.rule_count:
            issue = (f"durable validation-ref set inconsistent "
                     f"(rule_count={record.rule_count}, rows={len(refs)})")
            self._issues.append(f"domain state {domain_state_id}: {issue}")
            return DomainStateReadVerificationUnavailable(
                domain_state_id, issue + " — Issue Report required")
        recomputed = canonical_state_bytes(record, refs, fields)
        verdict = self._s1.verify(recomputed, record.record_fingerprint,
                                  record.fingerprint_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            issue = (f"record verification unavailable: "
                     f"{verdict.reason or 'capability failure'}")
            self._issues.append(f"domain state {domain_state_id}: {issue}")
            return DomainStateReadVerificationUnavailable(
                domain_state_id, issue + " — Issue Report required")
        if verdict.outcome == "FAILED":
            return DomainStateReadIntegrityFailure(domain_state_id,
                                                   NOTE_VERIFY_FAILED,
                                                   utc_now_iso())
        item = self._store.get_review_item(domain_state_id)
        review_status: Optional[str] = None
        if item is not None:
            item_read = self.read_review_item(item.review_id)
            if not isinstance(item_read, ReviewItemReadSuccess):
                issue = (f"review item verification failed: "
                         f"{type(item_read).__name__}")
                self._issues.append(f"domain state {domain_state_id}: {issue}")
                return DomainStateReadVerificationUnavailable(
                    domain_state_id, issue + " — Issue Report required")
            review_status = item_read.status
        return DomainStateReadSuccess(record, tuple(refs), tuple(fields), item,
                                      review_status, utc_now_iso())

    def read_review_item(self, review_id: str) -> object:
        """Read a REVIEW item + full event history + derived status with the
        integrity verdict computed INSIDE the read (item fingerprint + the
        per-item event hash chain, OD-S13)."""
        try:
            item = self._store.get_item_by_review_id(review_id)
        except DomainStateNotFound:
            return ReviewItemReadRefused(None, "no such review item")
        recomputed = canonical_item_bytes(item)
        verdict = self._s1.verify(recomputed, item.item_fingerprint,
                                  item.fingerprint_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            issue = (f"item verification unavailable: "
                     f"{verdict.reason or 'capability failure'}")
            self._issues.append(f"review {review_id}: {issue}")
            return ReviewItemReadVerificationUnavailable(
                review_id, issue + " — Issue Report required")
        if verdict.outcome == "FAILED":
            return ReviewItemReadIntegrityFailure(review_id, NOTE_VERIFY_FAILED,
                                                  utc_now_iso())
        events = self._store.get_events(review_id)
        prev_fp = ""
        for event in events:
            chain_ok = (event.prev_event_fingerprint == prev_fp)
            echain = self._s1.verify(canonical_event_bytes(event),
                                     event.event_fingerprint,
                                     event.fingerprint_algorithm_id)
            if echain.outcome == "NO_VERDICT":
                issue = (f"event verification unavailable: "
                         f"{echain.reason or 'capability failure'}")
                self._issues.append(f"review {review_id}: {issue}")
                return ReviewItemReadVerificationUnavailable(
                    review_id, issue + " — Issue Report required")
            if echain.outcome == "FAILED" or not chain_ok:
                return ReviewItemReadIntegrityFailure(
                    review_id,
                    f"event chain verify FAILED at seq {event.event_seq}",
                    utc_now_iso())
            prev_fp = event.event_fingerprint
        status = REVIEW_STATUS_CLOSED if self._store.has_close_event(review_id) \
            else REVIEW_STATUS_OPEN
        return ReviewItemReadSuccess(item, tuple(events), status, utc_now_iso())

    # ------------------------------------------------------------------
    # REVIEW lifecycle — append-only, terminal CLOSE, never a resolver (§5)
    # ------------------------------------------------------------------

    def append_review_event(self, review_id: str, event_type: str, note: str,
                            actor: str) -> object:
        """Record one explicit external lifecycle act on a REVIEW item.
        Outcome is exactly one explicit type:
          ReviewEventAppended | ReviewEventRefused | ReviewEventUnavailable.
        The event records that an external actor annotated/closed the item — the
        decision itself lives outside this layer (the queue is NOT a semantic
        resolver). CLOSE is terminal: any event after it is refused.
        """
        if event_type not in EVENT_TYPES:
            return ReviewEventRefused(
                review_id,
                f"unknown event type {event_type!r} — the declared lifecycle "
                f"vocabulary is ANNOTATE | CLOSE")
        if not actor:
            return ReviewEventRefused(review_id,
                                      "an event actor is required (opaque "
                                      "string, recorded verbatim)")
        item_read = self.read_review_item(review_id)
        if isinstance(item_read, ReviewItemReadRefused):
            return ReviewEventRefused(review_id, item_read.detail)
        if isinstance(item_read, ReviewItemReadIntegrityFailure):
            return ReviewEventRefused(
                review_id,
                f"item failed its verified read — event refused: "
                f"{item_read.reason}")
        if isinstance(item_read, ReviewItemReadVerificationUnavailable):
            self._issues.append(f"review {review_id}: "
                                f"{item_read.issue_report}")
            return ReviewEventUnavailable(review_id, item_read.issue_report)
        if item_read.status == REVIEW_STATUS_CLOSED:
            return ReviewEventRefused(
                review_id,
                "item is CLOSED — the lifecycle is terminal; history is "
                "append-only and never rewritten")
        # fail-closed: the parent projection must still verify — a broken state
        # record freezes the queue item (no event may ride on broken provenance)
        parent = self.read_domain_state(item_read.item.domain_state_id)
        if isinstance(parent, DomainStateReadIntegrityFailure):
            return ReviewEventRefused(
                review_id,
                f"parent projection failed its verified read — event refused: "
                f"{parent.reason}")
        if isinstance(parent, DomainStateReadVerificationUnavailable):
            self._issues.append(f"review {review_id}: {parent.issue_report}")
            return ReviewEventUnavailable(review_id, parent.issue_report)
        events = item_read.events
        event = ReviewQueueEvent(
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
        except DomainStatePersistenceUnavailable as exc:
            return ReviewEventUnavailable(review_id, str(exc))
        status = REVIEW_STATUS_CLOSED if saved.event_type == "CLOSE" \
            else REVIEW_STATUS_OPEN
        return ReviewEventAppended(saved, status)

    # ------------------------------------------------------------------
    # Traceability walk — domain state → P5.1 whole-chain sub-walks →
    # normalization → extraction → binding → document/page/span → Capture S1
    # (SPEC §10; pointers only, everything re-verified)
    # ------------------------------------------------------------------

    def trace_domain_state(self, domain_state_id: str) -> object:
        """Walk the full provenance chain with verified reads on EVERY link
        inside this one call. Every consumed P5.1 record is walked through the
        WP-5.1 whole-chain trace (P4.2 sub-chains consumed, never bypassed).
        Deliverable: ordered coarse link verdicts (no source values copied)."""
        head = self.read_domain_state(domain_state_id)
        if isinstance(head, DomainStateReadIntegrityFailure):
            return DomainStateTraceIntegrityFailure(domain_state_id,
                                                    "domain_state", head.reason)
        if isinstance(head, DomainStateReadRefused):
            return DomainStateTraceRefused(domain_state_id, head.detail)
        if isinstance(head, DomainStateReadVerificationUnavailable):
            self._issues.append(f"trace {domain_state_id}: {head.issue_report}")
            return DomainStateTraceVerificationUnavailable(domain_state_id,
                                                           head.issue_report)
        record, refs, fields = head.record, head.validation_refs, \
            head.field_projections

        chain: List[str] = [
            f"domain_state: {record.domain_state}/{record.disposition} "
            f"reason={record.state_reason} ruleset={record.ruleset_id}/"
            f"{record.ruleset_version} ruleset_fp="
            f"{record.ruleset_fingerprint[:12]}… rules={record.rule_count} "
            f"unresolved_fields={record.unresolved_count}",
        ]

        # link: every consumed P5.1 record — its OWN whole chain (incl. WP-4.2)
        for ref in refs:
            walk = self._validation.trace_validation(ref.validation_id)
            if isinstance(walk, ValidationTraceSuccess):
                chain.append(
                    f"validation[{ref.ord_slot}] {ref.rule_id}/{ref.rule_version} "
                    f"→ {ref.outcome}({ref.outcome_reason}): WP-5.1 whole-chain "
                    f"re-verified in this walk")
                continue
            link = getattr(walk, "link", "validation")
            reason = getattr(walk, "reason",
                             getattr(walk, "detail",
                                     getattr(walk, "issue_report", "unknown")))
            if type(walk).__name__ == "ValidationTraceVerificationUnavailable":
                self._issues.append(f"trace {domain_state_id}: {reason}")
                return DomainStateTraceVerificationUnavailable(domain_state_id,
                                                               reason)
            return DomainStateTraceIntegrityFailure(
                domain_state_id, "validation",
                f"P5.1 sub-chain for {ref.rule_id}/{ref.rule_version} failed at "
                f"link '{link}': {reason}")

        # link: field projections — RESOLVED pointers must hit real fields
        norm_read = self._normalization.read_normalization(record.normalization_id)
        if isinstance(norm_read, NormalizationReadIntegrityFailure):
            return DomainStateTraceIntegrityFailure(domain_state_id,
                                                    "normalization",
                                                    norm_read.reason)
        if isinstance(norm_read, NormalizationReadRefused):
            return DomainStateTraceRefused(domain_state_id,
                                           "normalization record missing")
        if isinstance(norm_read, NormalizationReadVerificationUnavailable):
            self._issues.append(f"trace {domain_state_id}: "
                                f"{norm_read.issue_report}")
            return DomainStateTraceVerificationUnavailable(domain_state_id,
                                                           norm_read.issue_report)
        norm_record, norm_fields = norm_read.record, norm_read.fields
        if norm_record.extraction_id != record.extraction_id:
            return DomainStateTraceIntegrityFailure(domain_state_id,
                                                    "normalization",
                                                    "extraction linkage drift")
        normalized_by_seq = {f.field_seq: f for f in norm_fields}
        for row in fields:
            if row.projection_status == PROJECTION_RESOLVED \
                    and row.origin_relayed == "NORMALIZED":
                field = normalized_by_seq.get(row.source_field_seq)
                if field is None or field.source_field_name != row.field_name \
                        or field.status is not NormalizationStatus.NORMALIZED:
                    return DomainStateTraceIntegrityFailure(
                        domain_state_id, "normalization",
                        f"projection row '{row.field_name}' points at field_seq "
                        f"{row.source_field_seq} which is not a NORMALIZED "
                        f"'{row.field_name}' — chain refused")
        chain.append(
            f"normalization: OK ruleset={norm_record.ruleset_id}/"
            f"{norm_record.ruleset_version} fields={norm_record.field_count} "
            f"projected={len(fields)} unresolved={record.unresolved_count}")

        # link: extraction (WP-3.1 verified read)
        ext_read = self._extraction.read_extraction(record.extraction_id)
        if isinstance(ext_read, ExtractionReadIntegrityFailure):
            return DomainStateTraceIntegrityFailure(domain_state_id, "extraction",
                                                    ext_read.reason)
        if isinstance(ext_read, ExtractionReadRefused):
            return DomainStateTraceRefused(domain_state_id,
                                           "extraction record missing")
        if isinstance(ext_read, ExtractionReadVerificationUnavailable):
            self._issues.append(f"trace {domain_state_id}: "
                                f"{ext_read.issue_report}")
            return DomainStateTraceVerificationUnavailable(domain_state_id,
                                                           ext_read.issue_report)
        chain.append(
            f"extraction: OK engine={ext_read.extraction.engine_id}/"
            f"{ext_read.extraction.engine_schema_version} "
            f"fields={ext_read.extraction.field_count}")

        # link: evidence binding (WP-3.2 verified read)
        binding_read = self._binder.read_binding(record.extraction_id)
        if isinstance(binding_read, BindingReadIntegrityFailure):
            return DomainStateTraceIntegrityFailure(
                domain_state_id, "binding",
                f"link '{binding_read.link.value}': {binding_read.reason}")
        if isinstance(binding_read, BindingReadRefused):
            return DomainStateTraceRefused(domain_state_id,
                                           "evidence binding missing")
        if isinstance(binding_read, BindingReadVerificationUnavailable):
            self._issues.append(f"trace {domain_state_id}: "
                                f"{binding_read.issue_report}")
            return DomainStateTraceVerificationUnavailable(domain_state_id,
                                                           binding_read.issue_report)
        chain.append(
            f"binding: OK binding_id={binding_read.binding.binding_id[:12]}… "
            f"entries={binding_read.binding.field_binding_count}")

        # link: document/page/span (WP-2.1 verified read)
        doc_read = self._reconstruction.read_document(record.document_id)
        if isinstance(doc_read, DocumentReadIntegrityFailure):
            return DomainStateTraceIntegrityFailure(domain_state_id, "document",
                                                    doc_read.reason)
        if isinstance(doc_read, DocumentReadRefused):
            return DomainStateTraceRefused(domain_state_id,
                                           "document record missing")
        if isinstance(doc_read, DocumentReadVerificationUnavailable):
            self._issues.append(f"trace {domain_state_id}: "
                                f"{doc_read.issue_report}")
            return DomainStateTraceVerificationUnavailable(domain_state_id,
                                                           doc_read.issue_report)
        chain.append(
            f"document: OK pages={len(doc_read.pages)} "
            f"capture_s1={doc_read.capture_s1[:12]}…")

        # link: capture S1 (linkage carried by the record and re-checked here)
        if doc_read.capture_id != record.capture_id \
                or doc_read.capture_s1 != record.capture_s1:
            return DomainStateTraceIntegrityFailure(domain_state_id,
                                                    "capture",
                                                    "capture linkage drift")
        chain.append(
            f"capture: OK capture_id={record.capture_id[:12]}… "
            f"s1={record.capture_s1[:12]}… ({record.capture_s1_algorithm_id})")
        return DomainStateTraceSuccess(domain_state_id, tuple(chain))

    # ------------------------------------------------------------------
    # Traceability enumeration + issue surface
    # ------------------------------------------------------------------

    def domain_states_for_normalization(self, normalization_id: str) -> Tuple[str, ...]:
        """All domain_state_ids for a normalization — deterministic order."""
        return tuple(self._store.states_for_normalization(normalization_id))

    def list_review_items(self) -> Tuple[str, ...]:
        """All REVIEW item ids — deterministic order (creation order)."""
        return tuple(self._store.list_review_ids())

    def issue_reports(self) -> list:
        """Accumulated Issue-Report items surfaced by this service instance."""
        return list(self._issues)
