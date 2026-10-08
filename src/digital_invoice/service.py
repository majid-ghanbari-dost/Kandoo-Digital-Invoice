"""Digital Invoice Lifecycle service — WP-10.1 MVP implementation.

Binding basis: SPEC-WP101-DILIFE §2/§3/§4/§5/§6/§9. The entry point and
orchestration layer: every call consumes the WP-6.2 verified read
(`read_assembled_invoice`) and the WP-6.2 whole-chain trace
(`trace_assembled_invoice`) VERBATIM — never bypassed, never re-implemented,
never triggered for upstream execution (spy-proven) — and either records ONE
explicit lifecycle fact or refuses with ZERO durable residue.

Open ladder (SPEC §4):
  O1  P6.2 verified read — refused → RequestRefused (details verbatim);
      integrity/unavailable → InputIntegrityFailure (fail-closed)
  O2  P6.2 whole-chain trace — consumed, never bypassed; any broken link →
      InputIntegrityFailure
  O3  replay (INV-DI-1:1) → OpenReplay verbatim, ZERO new rows (D-03)
  O4  atomic commit; UNIQUE(invoice_id) collision → re-read the winner →
      OpenReplay (read-only; never a second fact)

Lifecycle acts (SPEC §5): mark_extracted / mark_validated / issue / revoke /
supersede — explicit, fail-closed, idempotent at the target state. Every act
re-verifies the linked P6.2 chain LIVE at act time (the §6 verified read of
the Digital Invoice itself, which includes the P6.2 re-verification). The
current state decides: advance (exact predecessor) / replay (exact target) /
refuse (everything else — no skip, no backward, no terminal exit). NOTHING
is automatic.

Verified reads (§6): own-row VOR → event-chain integrity (per-invoice
gap-free seq, chain closure, matrix shape) → linked P6.2 re-verification +
anchor cross-checks → SUPERSEDE replacement re-verification (one level
deep). A tampered row, a broken chain, a drifted anchor, or a failing
upstream chain withholds content — this layer never serves an unverified
fact.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import uuid

from capture import S1Service

from canonical_assembly import (
    AssemblyReadIntegrityFailure,
    AssemblyReadRefused,
    AssemblyReadSuccess,
    AssemblyReadVerificationUnavailable,
    AssemblyTraceIntegrityFailure,
    AssemblyTraceRefused,
    AssemblyTraceSuccess,
    AssemblyTraceVerificationUnavailable,
    CanonicalAssemblyService,
)

from .model import (
    EVENT_ISSUE,
    EVENT_MARK_EXTRACTED,
    EVENT_MARK_VALIDATED,
    EVENT_REVOKE,
    EVENT_SUPERSEDE,
    NOTE_VERIFY_FAILED,
    REFUSE_MALFORMED,
    REFUSE_NO_DIGITAL_INVOICE,
    REFUSE_REPLACEMENT_NOT_ISSUED,
    REFUSE_SUPERSEDE_CONFLICT,
    REFUSE_SUPERSEDE_SELF,
    REFUSE_TRANSITION_UNAVAILABLE,
    STATE_DRAFT,
    STATE_EXTRACTED,
    STATE_ISSUED,
    STATE_REVOKED,
    STATE_SUPERSEDED,
    STATE_VALIDATED,
    TERMINAL_STATES,
    DigitalInvoiceDuplicate,
    DigitalInvoiceInputIntegrityFailure,
    DigitalInvoiceNotFound,
    DigitalInvoiceOpenReplay,
    DigitalInvoiceOpened,
    DigitalInvoicePersistenceUnavailable,
    DigitalInvoiceReadIntegrityFailure,
    DigitalInvoiceReadRefused,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceReadVerificationUnavailable,
    DigitalInvoiceRecord,
    DigitalInvoiceRequestRefused,
    DigitalInvoiceStorageUnavailable,
    DigitalInvoiceTraceIntegrityFailure,
    DigitalInvoiceTraceRefused,
    DigitalInvoiceTraceSuccess,
    DigitalInvoiceTraceVerificationUnavailable,
    LifecycleAdvanced,
    LifecycleEventDuplicate,
    LifecycleEventRecord,
    LifecycleInputIntegrityFailure,
    LifecycleReplay,
    LifecycleRequestRefused,
    LifecycleStorageUnavailable,
    predecessor_of,
    project_current_state,
    utc_now_iso,
)
from .store import (
    DigitalInvoiceStore,
    canonical_digital_invoice_bytes,
    canonical_event_bytes,
)


class DigitalInvoiceLifecycleService:
    """The WP-10.1 entry point: issued Canonical Invoices (P6.2) → durable,
    append-only, auditable Digital Invoice lifecycle facts over the frozen
    vocabulary (AS-03 — nothing automatic, nothing invented)."""

    def __init__(self, store: DigitalInvoiceStore,
                 assembly: CanonicalAssemblyService,
                 s1: S1Service) -> None:
        self._store = store
        self._assembly = assembly
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Entry — open (SPEC §4)
    # ------------------------------------------------------------------

    def open_digital_invoice(self, invoice_id: str) -> object:
        """Open ONE Digital Invoice for ONE issued Canonical Invoice. The
        invoice path is the P6.2 verified read + whole-chain trace —
        consumed VERBATIM. Exactly one explicit outcome — never silent:
          DigitalInvoiceOpened | DigitalInvoiceOpenReplay |
          DigitalInvoiceRequestRefused | DigitalInvoiceInputIntegrityFailure
          | DigitalInvoiceStorageUnavailable.
        """
        # -- O1: the ONLY invoice path — the P6.2 verified read ------------
        invoice_read = self._assembly.read_assembled_invoice(invoice_id)
        if isinstance(invoice_read, AssemblyReadRefused):
            return DigitalInvoiceRequestRefused(
                invoice_id, f"no issued Canonical Invoice behind "
                            f"{invoice_id!r}: {invoice_read.detail} — only "
                            f"an issued P6.2 invoice can carry a Digital "
                            f"Invoice (AS-01: the capture path entered the "
                            f"domain through the Canonicalization Gate)")
        if isinstance(invoice_read, AssemblyReadIntegrityFailure):
            return DigitalInvoiceInputIntegrityFailure(
                invoice_id, invoice_read.reason)
        if isinstance(invoice_read, AssemblyReadVerificationUnavailable):
            self._issues.append(f"open {invoice_id}: "
                                f"{invoice_read.issue_report}")
            return DigitalInvoiceInputIntegrityFailure(
                invoice_id, invoice_read.issue_report
                + " — Issue Report required")

        # -- O2: the P6.2 whole-chain trace (consumed, never bypassed) -----
        walk = self._assembly.trace_assembled_invoice(invoice_id)
        if isinstance(walk, AssemblyTraceRefused):
            return DigitalInvoiceInputIntegrityFailure(
                invoice_id, f"provenance walk refused: {walk.detail}")
        if isinstance(walk, AssemblyTraceIntegrityFailure):
            return DigitalInvoiceInputIntegrityFailure(
                invoice_id,
                f"broken provenance chain at link '{walk.link}': "
                f"{walk.reason}")
        if isinstance(walk, AssemblyTraceVerificationUnavailable):
            self._issues.append(f"open {invoice_id}: {walk.issue_report}")
            return DigitalInvoiceInputIntegrityFailure(
                invoice_id,
                f"provenance verification unavailable: {walk.issue_report}")

        # -- O3: replay (INV-DI-1:1) — the existing fact wins --------------
        existing = self._store.find_invoice(invoice_id)
        if existing is not None:
            verified = self.read_digital_invoice_by_id(
                existing.digital_invoice_id)
            if isinstance(verified, DigitalInvoiceReadIntegrityFailure):
                return DigitalInvoiceInputIntegrityFailure(
                    invoice_id,
                    f"existing Digital Invoice failed verification: "
                    f"{verified.reason}")
            if isinstance(verified, DigitalInvoiceReadVerificationUnavailable):
                self._issues.append(f"open {invoice_id}: "
                                    f"{verified.issue_report}")
                return DigitalInvoiceInputIntegrityFailure(
                    invoice_id, verified.issue_report
                    + " — Issue Report required")
            if isinstance(verified, DigitalInvoiceReadRefused):
                return DigitalInvoiceInputIntegrityFailure(
                    invoice_id,
                    f"existing Digital Invoice unreadable: "
                    f"{verified.detail}")
            return DigitalInvoiceOpenReplay(
                verified.record, verified.current_state,
                verified.invoice_read, utc_now_iso())

        # -- O4: atomic commit of the creation row (state DRAFT) -----------
        record = DigitalInvoiceRecord(
            digital_invoice_id=uuid.uuid4().hex,
            invoice_id=invoice_read.invoice.invoice_id,
            capture_s1=invoice_read.invoice.capture_s1,
            capture_s1_algorithm_id=invoice_read.invoice
            .capture_s1_algorithm_id,
            capture_id=invoice_read.invoice.capture_id,
            document_id=invoice_read.invoice.document_id,
            origin=invoice_read.invoice.origin,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="")
        try:
            saved = self._store.commit_digital_invoice(record)
        except DigitalInvoiceDuplicate:
            # A concurrent call won the INV-DI-1:1 race — this call is,
            # factually, the replay (read-only; never a second fact).
            winner = self._store.find_invoice(invoice_id)
            if winner is None:
                return DigitalInvoiceStorageUnavailable(
                    "commit collision reported but no Digital Invoice found "
                    "— inconsistent store state")
            verified = self.read_digital_invoice_by_id(
                winner.digital_invoice_id)
            if not isinstance(verified, DigitalInvoiceReadSuccess):
                return DigitalInvoiceInputIntegrityFailure(
                    invoice_id,
                    "concurrent Digital Invoice failed verification")
            return DigitalInvoiceOpenReplay(
                verified.record, verified.current_state,
                verified.invoice_read, utc_now_iso())
        except DigitalInvoicePersistenceUnavailable as exc:
            return DigitalInvoiceStorageUnavailable(str(exc))

        return DigitalInvoiceOpened(saved, invoice_read, utc_now_iso())

    # ------------------------------------------------------------------
    # Lifecycle acts (SPEC §5) — one shared core, five explicit wrappers
    # ------------------------------------------------------------------

    def mark_extracted(self, invoice_id: str, reason_note: str = "") -> object:
        """DRAFT → EXTRACTED (SPEC §5.2 E1)."""
        return self._act(invoice_id, EVENT_MARK_EXTRACTED,
                         STATE_EXTRACTED, "", reason_note)

    def mark_validated(self, invoice_id: str, reason_note: str = "") -> object:
        """EXTRACTED → VALIDATED (SPEC §5.2 E2)."""
        return self._act(invoice_id, EVENT_MARK_VALIDATED,
                         STATE_VALIDATED, "", reason_note)

    def issue(self, invoice_id: str, reason_note: str = "") -> object:
        """VALIDATED → ISSUED (SPEC §5.2 E3) — the OPERATIONAL issuance act
        of the Digital Invoice (the identity was already issued by Kandoo at
        the Gate; D-02 — no identifier is minted here)."""
        return self._act(invoice_id, EVENT_ISSUE, STATE_ISSUED,
                         "", reason_note)

    def revoke(self, invoice_id: str, reason_note: str = "") -> object:
        """ISSUED → REVOKED, terminal (SPEC §5.2 E4)."""
        return self._act(invoice_id, EVENT_REVOKE, STATE_REVOKED,
                         "", reason_note)

    def supersede(self, invoice_id: str, replacement_invoice_id: str,
                  reason_note: str = "") -> object:
        """ISSUED → SUPERSEDED, terminal — replaced by ANOTHER Digital
        Invoice named by its invoice_id (SPEC §5.2 E5 / §5.4)."""
        return self._act(invoice_id, EVENT_SUPERSEDE, STATE_SUPERSEDED,
                         replacement_invoice_id, reason_note)

    def _act(self, invoice_id: str, event_type: str, target_state: str,
             replacement_invoice_id: str, reason_note: str) -> object:
        """The shared fail-closed act core (SPEC §5.3 A1–A4 / §5.4)."""
        # -- A0: declaration shape (zero residue on any refusal) -----------
        if not invoice_id or not isinstance(invoice_id, str):
            return LifecycleRequestRefused(
                None, f"{REFUSE_MALFORMED}: invoice_id must be a non-empty "
                      f"string")
        if not isinstance(reason_note, str):
            return LifecycleRequestRefused(
                invoice_id, f"{REFUSE_MALFORMED}: reason_note must be a "
                            f"string (declared opaque — recorded verbatim)")
        if event_type == EVENT_SUPERSEDE:
            if not replacement_invoice_id or not isinstance(
                    replacement_invoice_id, str):
                return LifecycleRequestRefused(
                    invoice_id,
                    f"{REFUSE_MALFORMED}: supersede requires the "
                    f"replacement_invoice_id (non-empty string)")
            if replacement_invoice_id == invoice_id:
                return LifecycleRequestRefused(
                    invoice_id,
                    f"{REFUSE_SUPERSEDE_SELF}: a Digital Invoice cannot "
                    f"replace itself")

        # -- A1: the Digital Invoice must exist ----------------------------
        existing = self._store.find_invoice(invoice_id)
        if existing is None:
            return LifecycleRequestRefused(
                invoice_id, f"{REFUSE_NO_DIGITAL_INVOICE}: no Digital "
                            f"Invoice exists for {invoice_id!r} — open one "
                            f"first (SPEC §4)")

        # -- A2: the full verified read of the Digital Invoice (own VOR +
        #      event chain + LIVE P6.2 re-verification) --------------------
        verified = self.read_digital_invoice_by_id(
            existing.digital_invoice_id)
        if isinstance(verified, DigitalInvoiceReadIntegrityFailure):
            return LifecycleInputIntegrityFailure(
                invoice_id, verified.reason)
        if isinstance(verified, DigitalInvoiceReadVerificationUnavailable):
            self._issues.append(f"act {invoice_id}: {verified.issue_report}")
            return LifecycleInputIntegrityFailure(
                invoice_id, verified.issue_report + " — Issue Report required")
        if isinstance(verified, DigitalInvoiceReadRefused):
            return LifecycleInputIntegrityFailure(
                invoice_id, f"existing Digital Invoice unreadable: "
                            f"{verified.detail}")

        current = verified.current_state

        # -- A3: the state decision (advance / replay / refuse) ------------
        if current == target_state:
            # Replay of the already-recorded fact (D-03 — never re-decides).
            # SUPERSEDE additionally requires the declared replacement to
            # byte-match the recorded one (OD-DI-H — never reshaped).
            if event_type == EVENT_SUPERSEDE:
                recorded = [e.replacement_invoice_id
                            for e in verified.events
                            if e.event_type == EVENT_SUPERSEDE]
                if not recorded or recorded[-1] != replacement_invoice_id:
                    return LifecycleRequestRefused(
                        invoice_id,
                        f"{REFUSE_SUPERSEDE_CONFLICT}: this Digital Invoice "
                        f"is already SUPERSEDED by a different replacement — "
                        f"the recorded fact is never reshaped (OD-DI-H)")
            return LifecycleReplay(
                verified.record, current, verified.events,
                verified.invoice_read, utc_now_iso())

        predecessor = predecessor_of(target_state)
        if current != predecessor:
            if current in TERMINAL_STATES:
                detail = (f"current state is the terminal {current} — no "
                          f"transition leaves a terminal state (SPEC §5.2 "
                          f"terminal discipline)")
            else:
                detail = (f"transition {event_type} is unavailable from the "
                          f"current state {current}: the unique legal "
                          f"predecessor of {target_state} is {predecessor} "
                          f"— no skip, no backward, no exit (SPEC §5.2)")
            return LifecycleRequestRefused(
                invoice_id, f"{REFUSE_TRANSITION_UNAVAILABLE}: {detail}")

        # -- A4 (supersede only): the replacement verification ladder ------
        if event_type == EVENT_SUPERSEDE:
            refusal = self._verify_replacement(replacement_invoice_id)
            if refusal is not None:
                return refusal

        # -- A5: atomic commit of ONE event row (per-invoice max+1) --------
        event = LifecycleEventRecord(
            event_id=uuid.uuid4().hex,
            digital_invoice_id=existing.digital_invoice_id,
            invoice_id=existing.invoice_id,
            event_seq=self._store.next_event_seq(existing.digital_invoice_id),
            event_type=event_type,
            from_state=current,
            to_state=target_state,
            replacement_invoice_id=replacement_invoice_id
            if event_type == EVENT_SUPERSEDE else "",
            reason_note=reason_note,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="")
        try:
            saved = self._store.commit_event(event)
        except LifecycleEventDuplicate:
            # A concurrent act won the per-invoice seq race. From any state
            # only ONE transition is legal — but ISSUED has TWO terminal
            # acts (REVOKE / SUPERSEDE), so the winner may be the opposing
            # terminal act: re-project honestly and answer from the LIVE
            # state (never reshape the outcome).
            re_verified = self.read_digital_invoice_by_id(
                existing.digital_invoice_id)
            if not isinstance(re_verified, DigitalInvoiceReadSuccess):
                return LifecycleInputIntegrityFailure(
                    invoice_id, "concurrent act winner failed verification")
            if re_verified.current_state == target_state:
                if event_type == EVENT_SUPERSEDE:
                    recorded = [e.replacement_invoice_id
                                for e in re_verified.events
                                if e.event_type == EVENT_SUPERSEDE]
                    if not recorded \
                            or recorded[-1] != replacement_invoice_id:
                        return LifecycleRequestRefused(
                            invoice_id,
                            f"{REFUSE_SUPERSEDE_CONFLICT}: the concurrent "
                            f"winner superseded this Digital Invoice with a "
                            f"different replacement — the recorded fact is "
                            f"never reshaped (OD-DI-H)")
                return LifecycleReplay(
                    re_verified.record, re_verified.current_state,
                    re_verified.events, re_verified.invoice_read,
                    utc_now_iso())
            return LifecycleRequestRefused(
                invoice_id,
                f"{REFUSE_TRANSITION_UNAVAILABLE}: a concurrent act moved "
                f"the state to {re_verified.current_state} — the transition "
                f"{event_type} is no longer available (SPEC §5.2)")
        except DigitalInvoicePersistenceUnavailable as exc:
            return LifecycleStorageUnavailable(str(exc))

        return LifecycleAdvanced(saved, verified.record, target_state,
                                 verified.invoice_read, utc_now_iso())

    def _verify_replacement(self, replacement_invoice_id: str) \
            -> Optional[LifecycleRequestRefused]:
        """§5.4: the replacement must exist, verify, be ISSUED, and differ
        from the source (the source check happened at A0; the ISSUED check
        makes supersession cycles structurally impossible)."""
        replacement = self._store.find_invoice(replacement_invoice_id)
        if replacement is None:
            return LifecycleRequestRefused(
                None, f"{REFUSE_REPLACEMENT_NOT_ISSUED}: no Digital Invoice "
                      f"exists for the replacement {replacement_invoice_id!r} "
                      f"— a supersession names an EXISTING Digital Invoice "
                      f"(SPEC §5.4)")
        verified = self.read_digital_invoice_by_id(
            replacement.digital_invoice_id)
        if isinstance(verified, DigitalInvoiceReadIntegrityFailure):
            return LifecycleRequestRefused(
                replacement_invoice_id,
                "the replacement Digital Invoice failed verification: "
                f"{verified.reason}")
        if isinstance(verified, DigitalInvoiceReadVerificationUnavailable):
            self._issues.append(f"supersede replacement "
                                f"{replacement_invoice_id}: "
                                f"{verified.issue_report}")
            return LifecycleRequestRefused(
                replacement_invoice_id,
                "the replacement Digital Invoice could not be verified: "
                f"{verified.issue_report} — Issue Report required")
        if isinstance(verified, DigitalInvoiceReadRefused):
            return LifecycleRequestRefused(
                replacement_invoice_id,
                "the replacement Digital Invoice is unreadable: "
                f"{verified.detail}")
        if verified.current_state != STATE_ISSUED:
            return LifecycleRequestRefused(
                replacement_invoice_id,
                f"{REFUSE_REPLACEMENT_NOT_ISSUED}: the replacement is in "
                f"state {verified.current_state} — only an ISSUED Digital "
                f"Invoice can replace another (SPEC §5.4; this also makes "
                f"supersession cycles structurally impossible)")
        return None

    # ------------------------------------------------------------------
    # Verified reads (VOR + chain + linked re-verification — SPEC §6)
    # ------------------------------------------------------------------

    def _verify(self, payload: bytes, fingerprint: str, algorithm_id: str) \
            -> Optional[str]:
        """Returns None when VERIFIED; a refusal reason string otherwise
        ('verify FAILED' distinguishes tamper from capability loss)."""
        verdict = self._s1.verify(payload, fingerprint, algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            return f"verification unavailable: " \
                   f"{verdict.reason or 'capability failure'}"
        if verdict.outcome == "FAILED":
            return NOTE_VERIFY_FAILED
        return None

    def read_digital_invoice(self, invoice_id: str) -> object:
        """Verified read by the Canonical Identity (invoice_id)."""
        try:
            record = self._store.find_invoice(invoice_id)
        except DigitalInvoicePersistenceUnavailable as exc:
            return DigitalInvoiceReadVerificationUnavailable(
                None, f"{exc} — Issue Report required")
        if record is None:
            return DigitalInvoiceReadRefused(
                None, "no Digital Invoice exists for this invoice_id")
        return self._verified_read(record)

    def read_digital_invoice_by_id(self, digital_invoice_id: str) -> object:
        """Verified read by the bookkeeping row id."""
        try:
            record = self._store.get_invoice(digital_invoice_id)
        except DigitalInvoiceNotFound:
            return DigitalInvoiceReadRefused(None, "no such Digital Invoice")
        except DigitalInvoicePersistenceUnavailable as exc:
            return DigitalInvoiceReadVerificationUnavailable(
                None, f"{exc} — Issue Report required")
        return self._verified_read(record)

    def _verified_read(self, record: DigitalInvoiceRecord) -> object:
        # 1. own-row VOR (tampered rows withhold content — never served)
        problem = self._verify(canonical_digital_invoice_bytes(record),
                               record.record_fingerprint,
                               record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return DigitalInvoiceReadIntegrityFailure(
                    record.digital_invoice_id, problem, utc_now_iso())
            self._issues.append(f"digital invoice "
                                f"{record.digital_invoice_id}: {problem}")
            return DigitalInvoiceReadVerificationUnavailable(
                record.digital_invoice_id,
                problem + " — Issue Report required")

        # 2. the event chain: every row's VOR + gap-free ascending seq +
        #    chain closure + matrix shape (fail-closed on ANY defect)
        try:
            events = tuple(self._store.events_of(record.digital_invoice_id))
        except DigitalInvoicePersistenceUnavailable as exc:
            return DigitalInvoiceReadVerificationUnavailable(
                record.digital_invoice_id,
                f"{exc} — Issue Report required")
        chain_problem = self._chain_problem(record, events)
        if chain_problem is not None:
            if NOTE_VERIFY_FAILED in chain_problem:
                return DigitalInvoiceReadIntegrityFailure(
                    record.digital_invoice_id, chain_problem,
                    utc_now_iso())
            self._issues.append(f"digital invoice "
                                f"{record.digital_invoice_id}: "
                                f"{chain_problem}")
            return DigitalInvoiceReadVerificationUnavailable(
                record.digital_invoice_id,
                chain_problem + " — Issue Report required")
        current = project_current_state(events)

        # 3. the linked P6.2 invoice MUST verify + anchors must agree
        invoice_read = self._assembly.read_assembled_invoice(record.invoice_id)
        if isinstance(invoice_read, AssemblyReadIntegrityFailure):
            return DigitalInvoiceReadIntegrityFailure(
                record.digital_invoice_id,
                f"linked invoice failed verification: "
                f"{invoice_read.reason}", utc_now_iso())
        if isinstance(invoice_read, AssemblyReadVerificationUnavailable):
            self._issues.append(f"digital invoice "
                                f"{record.digital_invoice_id}: "
                                f"{invoice_read.issue_report}")
            return DigitalInvoiceReadVerificationUnavailable(
                record.digital_invoice_id,
                invoice_read.issue_report + " — Issue Report required")
        if isinstance(invoice_read, AssemblyReadRefused):
            return DigitalInvoiceReadIntegrityFailure(
                record.digital_invoice_id,
                f"linked invoice unreadable: {invoice_read.detail}",
                utc_now_iso())
        if record.invoice_id != invoice_read.invoice.invoice_id \
                or record.capture_s1 != invoice_read.invoice.capture_s1 \
                or record.capture_s1_algorithm_id \
                != invoice_read.invoice.capture_s1_algorithm_id \
                or record.capture_id != invoice_read.invoice.capture_id \
                or record.document_id != invoice_read.invoice.document_id \
                or record.origin != invoice_read.invoice.origin:
            self._issues.append(f"digital invoice "
                                f"{record.digital_invoice_id}: anchor drift")
            return DigitalInvoiceReadVerificationUnavailable(
                record.digital_invoice_id,
                "durable anchor set inconsistent: the copied anchors do not "
                "equal the verified P6.2 record — Issue Report required")

        # 4. SUPERSEDE events re-verify their replacement ONE level deep
        for event in events:
            if event.event_type != EVENT_SUPERSEDE:
                continue
            replacement_problem = self._replacement_problem(
                record, event)
            if replacement_problem is not None:
                if NOTE_VERIFY_FAILED in replacement_problem:
                    return DigitalInvoiceReadIntegrityFailure(
                        record.digital_invoice_id, replacement_problem,
                        utc_now_iso())
                self._issues.append(f"digital invoice "
                                    f"{record.digital_invoice_id}: "
                                    f"{replacement_problem}")
                return DigitalInvoiceReadVerificationUnavailable(
                    record.digital_invoice_id,
                    replacement_problem + " — Issue Report required")

        return DigitalInvoiceReadSuccess(record, current, events,
                                         invoice_read, utc_now_iso())

    def _chain_problem(self, record: DigitalInvoiceRecord,
                       events: Tuple[LifecycleEventRecord, ...]) \
            -> Optional[str]:
        """The event-chain integrity walk (§6 step 2): per-row VOR, gap-free
        per-invoice seq from 0, chain closure from DRAFT, matrix shape, and
        the copied invoice_id agreement. Returns None or a reason string."""
        from .model import is_legal_transition
        for idx, event in enumerate(events):
            problem = self._verify(canonical_event_bytes(event),
                                   event.record_fingerprint,
                                   event.fingerprint_algorithm_id)
            if problem is not None:
                return f"event seq {event.event_seq}: {problem}"
            if event.event_seq != idx:
                return (f"event chain gap: expected per-invoice seq {idx}, "
                        f"found {event.event_seq}")
            if event.digital_invoice_id != record.digital_invoice_id \
                    or event.invoice_id != record.invoice_id:
                return (f"event seq {event.event_seq}: copied anchor drift "
                        f"(digital_invoice_id/invoice_id)")
            if not is_legal_transition(event.event_type, event.from_state,
                                       event.to_state):
                return (f"event seq {event.event_seq}: "
                        f"({event.event_type}, {event.from_state}, "
                        f"{event.to_state}) is outside the frozen "
                        f"transition matrix")
            expected_from = STATE_DRAFT if idx == 0 else events[idx - 1].to_state
            if event.from_state != expected_from:
                return (f"event chain broken at seq {event.event_seq}: "
                        f"from_state {event.from_state} does not continue "
                        f"the chain (expected {expected_from})")
            if event.event_type == EVENT_SUPERSEDE:
                if not event.replacement_invoice_id:
                    return (f"event seq {event.event_seq}: SUPERSEDE "
                            f"without the replacement pointer")
            elif event.replacement_invoice_id:
                return (f"event seq {event.event_seq}: non-SUPERSEDE event "
                        f"with a replacement pointer")
        return None

    def _replacement_problem(self, record: DigitalInvoiceRecord,
                             event: LifecycleEventRecord) -> Optional[str]:
        """§6 step 4 — one-level-deep replacement re-verification: the
        replacement exists and its own full verified read succeeds (own VOR
        + event-chain integrity + linked P6.2 re-verification). NO state
        condition at read time: the ISSUED precondition is an ACT-time rule
        (§5.4); the replacement's own subsequent lifecycle (e.g. being
        superseded again in a correction chain, or revoked) is its own
        durable fact and never withholds the source's recorded history
        (determinism — a read must not depend on WHEN it happens)."""
        try:
            replacement = self._store.find_invoice(
                event.replacement_invoice_id)
        except DigitalInvoicePersistenceUnavailable as exc:
            return f"replacement lookup unavailable: {exc}"
        if replacement is None:
            return (f"SUPERSEDE seq {event.event_seq}: the replacement "
                    f"{event.replacement_invoice_id!r} does not exist")
        verified = self.read_digital_invoice_by_id(
            replacement.digital_invoice_id)
        if isinstance(verified, DigitalInvoiceReadIntegrityFailure):
            return (f"SUPERSEDE seq {event.event_seq}: the replacement "
                    f"failed verification: {verified.reason}")
        if isinstance(verified, DigitalInvoiceReadVerificationUnavailable):
            return (f"SUPERSEDE seq {event.event_seq}: the replacement "
                    f"could not be verified: {verified.issue_report}")
        if isinstance(verified, DigitalInvoiceReadRefused):
            return (f"SUPERSEDE seq {event.event_seq}: the replacement is "
                    f"unreadable: {verified.detail}")
        return None

    # ------------------------------------------------------------------
    # Trace (SPEC §6/§9) — ONE head link onto the intact P6.2 chain
    # ------------------------------------------------------------------

    def trace_digital_invoice(self, invoice_id: str) -> object:
        """Walk the lifecycle chain + the full P6.2 provenance chain with
        verified reads on EVERY link inside this one call. Deliverable:
        ordered coarse link verdicts (no source values copied)."""
        head = self.read_digital_invoice(invoice_id)
        if isinstance(head, DigitalInvoiceReadIntegrityFailure):
            return DigitalInvoiceTraceIntegrityFailure(
                invoice_id, "digital_invoice", head.reason)
        if isinstance(head, DigitalInvoiceReadRefused):
            return DigitalInvoiceTraceRefused(invoice_id, head.detail)
        if isinstance(head, DigitalInvoiceReadVerificationUnavailable):
            self._issues.append(f"trace {invoice_id}: {head.issue_report}")
            return DigitalInvoiceTraceVerificationUnavailable(
                invoice_id, head.issue_report)
        record = head.record

        chain: List[str] = [
            f"digital_invoice: {record.digital_invoice_id[:12]}… "
            f"invoice_id={record.invoice_id[:12]}… origin={record.origin} "
            f"current_state={head.current_state} "
            f"events={len(head.events)}",
        ]
        for event in head.events:
            line = (f"  ↳ seq {event.event_seq}: {event.event_type} "
                    f"{event.from_state} → {event.to_state}")
            if event.event_type == EVENT_SUPERSEDE:
                line += (f" (replacement "
                         f"{event.replacement_invoice_id[:12]}…)")
            chain.append(line)

        walk = self._assembly.trace_assembled_invoice(record.invoice_id)
        if isinstance(walk, AssemblyTraceIntegrityFailure):
            return DigitalInvoiceTraceIntegrityFailure(
                invoice_id, "canonical_invoice",
                f"link '{walk.link}': {walk.reason}")
        if isinstance(walk, AssemblyTraceRefused):
            return DigitalInvoiceTraceRefused(
                invoice_id, f"P6.2 walk refused: {walk.detail}")
        if isinstance(walk, AssemblyTraceVerificationUnavailable):
            self._issues.append(f"trace {invoice_id}: {walk.issue_report}")
            return DigitalInvoiceTraceVerificationUnavailable(
                invoice_id, walk.issue_report)
        chain.append(
            "canonical_invoice: the P6.2 whole-chain re-verified in this "
            f"walk ({len(walk.chain)} links, through the P6.1 admission and "
            "the P5.2 whole-chain walk to Capture S1)")
        chain.extend(f"  ↳ {link}" for link in walk.chain)

        return DigitalInvoiceTraceSuccess(record.invoice_id,
                                          record.digital_invoice_id,
                                          head.current_state, tuple(chain),
                                          utc_now_iso())

    # ------------------------------------------------------------------
    # Listing helpers (tests / smoke / operator tooling — OD-DI-K)
    # ------------------------------------------------------------------

    def digital_invoices(self) -> List[DigitalInvoiceRecord]:
        """All committed creation rows (raw records, listing discipline)."""
        return self._store.list_invoices()

    def lifecycle_events(self, invoice_id: Optional[str] = None) \
            -> List[LifecycleEventRecord]:
        """The durable event chain — all events, or one invoice's (raw
        records, listing discipline)."""
        if invoice_id is None:
            return self._store.list_events()
        return self._store.find_events_by_invoice(invoice_id)

    @property
    def issue_reports(self) -> list:
        return list(self._issues)
