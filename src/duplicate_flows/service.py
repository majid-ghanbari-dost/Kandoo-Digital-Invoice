"""Reprint & Duplicate Flows service — WP-7.2 MVP implementation.

Binding basis: SPEC-WP72-DUPFLOW §2/§3/§4/§5/§6/§9. The entry point and
orchestration layer: every `handle` call performs exactly ONE identity
resolution — WP-7.1's `IdentityResolutionService.resolve`, consumed
VERBATIM (never bypassed, never re-implemented — OD-DF-C) — and maps the
outcome deterministically onto the flow ladder F1–F6:

  F1  WP-7.1 refusal / integrity failure / storage failure → pass through
      fail-closed, zero durable residue (details verbatim — OD-DF-G)
  F2  IdentityResolutionRecorded   → IDENTITY_ESTABLISHED disposition
  F3  IdentityDefiniteDuplicate    → DUPLICATE_RECOGNIZED disposition
      (original + observation anchored — ONE document identity)
  F4  IdentityReplay + existing disposition → FlowReprintRecognized
      (verbatim, read-only, ZERO new rows)
  F5  IdentityReplay + no disposition yet → commit the disposition derived
      deterministically from the replayed resolution's own durable shape,
      then FlowReprintRecognized (OD-DF-E: deployment-order independent)
  F6  commit collision (INV-DF-1:1 backstop) → re-read the winner and
      return FlowReprintRecognized

Verified reads (§6): own-row VOR + re-verification of EVERY linked
identity fact through the WP-7.1 verified reads (resolution; original +
observation iff duplicate) + cross-store structural gates. A tampered or
disagreeing row at ANY level withholds content — the flow layer never
serves, and never trusted blindly, an unverified identity fact.
"""
from __future__ import annotations

from typing import List, Optional

import uuid

from capture import S1Service

from identity_resolution import (
    IdentityDefiniteDuplicate,
    IdentityReadIntegrityFailure,
    IdentityReadRefused,
    IdentityReadSuccess,
    IdentityReadVerificationUnavailable,
    IdentityResolutionRecorded,
    IdentityResolutionService,
    IdentityReplay,
    IdentityRequestRefused,
    IdentityStorageUnavailable,
    IdentityInputIntegrityFailure,
)

from .model import (
    FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
    FLOW_OUTCOME_IDENTITY_ESTABLISHED,
    DispositionDuplicate,
    DispositionNotFound,
    FlowDispositionRecord,
    FlowDuplicateRecognized,
    FlowIdentityEstablished,
    FlowInputIntegrityFailure,
    FlowPersistenceUnavailable,
    FlowReadIntegrityFailure,
    FlowReadRefused,
    FlowReadSuccess,
    FlowReadVerificationUnavailable,
    FlowReprintRecognized,
    FlowRequestRefused,
    FlowStorageUnavailable,
    utc_now_iso,
)
from .store import (
    FlowDispositionStore,
    canonical_disposition_bytes,
)


class DuplicateFlowService:
    """The WP-7.2 entry point: WP-7.1 durable identity outcomes →
    deterministic, auditable reprint & duplicate flow dispositions."""

    def __init__(self, store: FlowDispositionStore,
                 identity: IdentityResolutionService,
                 s1: S1Service) -> None:
        self._store = store
        self._identity = identity
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # The flow ladder — handle (SPEC §4)
    # ------------------------------------------------------------------

    def handle(self, domain_state_id: str, declared_origin: str,
               identity_field_binding=None) -> object:
        """Handle ONE capture's identity journey at flow level. Exactly one
        explicit outcome — never silent:
          FlowIdentityEstablished | FlowDuplicateRecognized |
          FlowReprintRecognized | FlowRequestRefused |
          FlowInputIntegrityFailure | FlowStorageUnavailable.
        The identity resolution itself is WP-7.1's — consumed VERBATIM.
        """
        outcome = self._identity.resolve(domain_state_id, declared_origin,
                                         identity_field_binding)

        # -- F1: fail-closed passthrough (zero durable residue) ----------
        if isinstance(outcome, IdentityRequestRefused):
            return FlowRequestRefused(outcome.domain_state_id, outcome.detail)
        if isinstance(outcome, IdentityInputIntegrityFailure):
            return FlowInputIntegrityFailure(outcome.domain_state_id,
                                             outcome.reason)
        if isinstance(outcome, IdentityStorageUnavailable):
            return FlowStorageUnavailable(outcome.detail)

        # -- F2: first sighting — IDENTITY_ESTABLISHED --------------------
        if isinstance(outcome, IdentityResolutionRecorded):
            record = outcome.record
            disposition = self._build_disposition(
                record, FLOW_OUTCOME_IDENTITY_ESTABLISHED,
                original_resolution_id="", duplicate_observation_id="")
            saved = self._commit(disposition, domain_state_id)
            if isinstance(saved, FlowReprintRecognized):
                # F6: a concurrent first call won the INV-DF-1:1 race —
                # this call is, factually, the reprint recognition.
                return saved
            if isinstance(saved, (FlowInputIntegrityFailure,
                                  FlowStorageUnavailable)):
                return saved
            return FlowIdentityEstablished(saved, record, outcome.role_rows)

        # -- F3: definite duplicate — DUPLICATE_RECOGNIZED ----------------
        if isinstance(outcome, IdentityDefiniteDuplicate):
            record = outcome.record
            disposition = self._build_disposition(
                record, FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
                original_resolution_id=outcome.original_resolution
                .resolution_id,
                duplicate_observation_id=outcome.observation.observation_id)
            saved = self._commit(disposition, domain_state_id)
            if isinstance(saved, FlowReprintRecognized):
                return saved
            if isinstance(saved, (FlowInputIntegrityFailure,
                                  FlowStorageUnavailable)):
                return saved
            return FlowDuplicateRecognized(
                saved, record, outcome.original_resolution,
                outcome.observation, outcome.role_rows)

        # -- F4/F5: replay — the reprint recognition ----------------------
        if isinstance(outcome, IdentityReplay):
            record = outcome.record
            existing = self._store.find_disposition_by_capture(
                record.capture_s1)
            if existing is None:
                # F5: first flow-layer sighting of an already-resolved
                # capture — the disposition is a pure function of the
                # durable facts (OD-DF-E), so committing it now yields the
                # same content a first sighting would have committed.
                built = self._disposition_from_resolution(record)
                if isinstance(built, FlowInputIntegrityFailure):
                    return built
                saved = self._commit(built, domain_state_id)
                if isinstance(saved, (FlowInputIntegrityFailure,
                                      FlowStorageUnavailable)):
                    return saved
                existing = saved
            else:
                verified = self.read_disposition_by_id(
                    existing.disposition_id)
                if isinstance(verified, FlowReadIntegrityFailure):
                    return FlowInputIntegrityFailure(
                        domain_state_id,
                        f"existing disposition failed verification: "
                        f"{verified.reason}")
                if isinstance(verified, FlowReadVerificationUnavailable):
                    self._issues.append(
                        f"handle {domain_state_id}: "
                        f"{verified.issue_report}")
                    return FlowInputIntegrityFailure(
                        domain_state_id, verified.issue_report)
                if isinstance(verified, FlowReadRefused):
                    return FlowInputIntegrityFailure(
                        domain_state_id,
                        f"existing disposition unreadable: "
                        f"{verified.detail}")
            return FlowReprintRecognized(
                existing, record, outcome.role_rows, outcome.observation,
                utc_now_iso())

        # Unreachable by construction (WP-7.1's ladder is exhaustive) —
        # kept fail-closed so a future WP-7.1 outcome type can NEVER be
        # silently mapped onto a flow fact.
        return FlowInputIntegrityFailure(
            domain_state_id,
            f"unmapped identity outcome {type(outcome).__name__} — "
            f"fail-closed (the flow ladder is exhaustive over the WP-7.1 "
            f"contract; this indicates a contract drift)")

    # ------------------------------------------------------------------
    # Disposition construction + commit helpers
    # ------------------------------------------------------------------

    def _build_disposition(self, record, flow_outcome: str,
                           original_resolution_id: str,
                           duplicate_observation_id: str) \
            -> FlowDispositionRecord:
        """Anchor the disposition to the WP-7.1 resolution record — the
        scope/fingerprint are COPIED from the verified record for
        self-description (cross-checked on every read, SPEC §6/§9)."""
        return FlowDispositionRecord(
            disposition_id=uuid.uuid4().hex,
            capture_s1=record.capture_s1,
            capture_s1_algorithm_id=record.capture_s1_algorithm_id,
            capture_id=record.capture_id,
            document_id=record.document_id,
            resolution_id=record.resolution_id,
            original_resolution_id=original_resolution_id,
            duplicate_observation_id=duplicate_observation_id,
            declared_origin=record.declared_origin,
            flow_outcome=flow_outcome,
            identity_scope=record.identity_scope,
            identity_fingerprint=record.identity_fingerprint,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="")

    def _disposition_from_resolution(self, record) \
            -> FlowDispositionRecord:
        """F5: derive the disposition from the replayed resolution's own
        durable shape (observation present → DUPLICATE_RECOGNIZED; else
        IDENTITY_ESTABLISHED). The caller's replay outcome already carries
        the verified observation — but the derivation uses the record's
        shape re-read through the verified path (never blind)."""
        verified = self._identity.read_resolution(record.resolution_id)
        if isinstance(verified, IdentityReadIntegrityFailure):
            return FlowInputIntegrityFailure(
                None, f"linked resolution failed verification: "
                      f"{verified.reason}")
        if isinstance(verified, IdentityReadVerificationUnavailable):
            self._issues.append(f"handle (replay): "
                                f"{verified.issue_report}")
            return FlowInputIntegrityFailure(None, verified.issue_report)
        if isinstance(verified, IdentityReadRefused):
            return FlowInputIntegrityFailure(
                None, f"linked resolution unreadable: {verified.detail}")
        observation = verified.observation
        if observation is not None:
            return self._build_disposition(
                record, FLOW_OUTCOME_DUPLICATE_RECOGNIZED,
                original_resolution_id=observation.original_resolution_id,
                duplicate_observation_id=observation.observation_id)
        return self._build_disposition(
            record, FLOW_OUTCOME_IDENTITY_ESTABLISHED,
            original_resolution_id="", duplicate_observation_id="")

    def _commit(self, disposition: FlowDispositionRecord,
                domain_state_id: Optional[str]):
        """Commit with the INV-DF-1:1 collision mapped to the reprint
        recognition (F6); storage failures surfaced explicitly."""
        try:
            return self._store.commit_disposition(disposition)
        except DispositionDuplicate:
            existing = self._store.find_disposition_by_capture(
                disposition.capture_s1)
            if existing is None:
                return FlowStorageUnavailable(
                    "commit collision reported but no disposition found — "
                    "inconsistent store state")
            verified = self.read_disposition_by_id(existing.disposition_id)
            if not isinstance(verified, FlowReadSuccess):
                return FlowInputIntegrityFailure(
                    domain_state_id,
                    "concurrent disposition failed verification")
            return FlowReprintRecognized(
                verified.disposition, verified.record, verified.role_rows,
                verified.observation, utc_now_iso())
        except FlowPersistenceUnavailable as exc:
            return FlowStorageUnavailable(str(exc))

    # ------------------------------------------------------------------
    # Verified reads (VOR + linked re-verification — SPEC §6)
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
            return "verify FAILED"
        return None

    def read_disposition_by_id(self, disposition_id: str) -> object:
        """Verified flow read (SPEC §6): own-row VOR → linked WP-7.1
        re-verification → cross-store structural gates."""
        try:
            record = self._store.get_disposition(disposition_id)
        except DispositionNotFound:
            return FlowReadRefused(None, "no such flow disposition")
        return self._verified_read(record)

    def read_disposition(self, capture_s1: str) -> object:
        """Verified flow read by the capture's S1 anchor."""
        record = self._store.find_disposition_by_capture(capture_s1)
        if record is None:
            return FlowReadRefused(
                None, "no flow disposition for this capture_s1")
        return self._verified_read(record)

    def _identity_fact(self, resolution_id: str, anchor: str):
        """Re-verify ONE linked identity fact through the WP-7.1 verified
        read (OD-DF-D — never blind pointers). Returns (record, role_rows,
        observation, None) or (None, None, None, problem-outcome)."""
        read = self._identity.read_resolution(resolution_id)
        if isinstance(read, IdentityReadIntegrityFailure):
            return None, None, None, FlowReadIntegrityFailure(
                anchor, f"linked resolution {read.reason}", utc_now_iso())
        if isinstance(read, IdentityReadVerificationUnavailable):
            self._issues.append(f"flow disposition {anchor}: "
                                f"{read.issue_report}")
            return None, None, None, FlowReadVerificationUnavailable(
                anchor, read.issue_report + " — Issue Report required")
        if isinstance(read, IdentityReadRefused):
            return None, None, None, FlowReadIntegrityFailure(
                anchor, f"linked resolution unreadable: {read.detail}",
                utc_now_iso())
        return read.record, read.role_rows, read.observation, None

    def _verified_read(self, record: FlowDispositionRecord) -> object:
        # 1. own-row VOR (tampered rows withhold content — never served)
        problem = self._verify(canonical_disposition_bytes(record),
                               record.record_fingerprint,
                               record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == "verify FAILED":
                return FlowReadIntegrityFailure(
                    record.disposition_id, problem, utc_now_iso())
            self._issues.append(f"flow disposition "
                                f"{record.disposition_id}: {problem}")
            return FlowReadVerificationUnavailable(
                record.disposition_id, problem + " — Issue Report required")

        # 2. the linked resolution MUST verify through WP-7.1
        resolution, role_rows, observation, failure = self._identity_fact(
            record.resolution_id, record.disposition_id)
        if failure is not None:
            return failure

        # 3. cross-store structural gates (a forged or half-written row
        #    cannot satisfy them — SPEC §6 step 3)
        structural = self._structural_check(record, resolution, observation)
        if structural is not None:
            self._issues.append(f"flow disposition "
                                f"{record.disposition_id}: {structural}")
            return FlowReadVerificationUnavailable(
                record.disposition_id, structural + " — Issue Report required")

        # 4. duplicates re-verify the original as well (OD-DF-D)
        original = None
        if record.flow_outcome == FLOW_OUTCOME_DUPLICATE_RECOGNIZED:
            original, _, _, failure = self._identity_fact(
                record.original_resolution_id, record.disposition_id)
            if failure is not None:
                return failure
            if original.resolution_id != record.original_resolution_id:
                return FlowReadIntegrityFailure(
                    record.disposition_id,
                    "original resolution reference drifted", utc_now_iso())

        return FlowReadSuccess(record, resolution, tuple(role_rows),
                               observation, original, utc_now_iso())

    def _structural_check(self, record: FlowDispositionRecord,
                          resolution, observation) -> Optional[str]:
        """Cross-store consistency beyond the hash anchor (SPEC §6): the
        disposition's anchors MUST agree with the linked resolution's
        durable facts, and the outcome shape MUST match the evidence."""
        if record.resolution_id != resolution.resolution_id:
            return "durable flow set inconsistent: resolution_id drift"
        if record.capture_s1 != resolution.capture_s1:
            return "durable flow set inconsistent: capture_s1 drift"
        if record.capture_id != resolution.capture_id:
            return "durable flow set inconsistent: capture_id drift"
        if record.document_id != resolution.document_id:
            return "durable flow set inconsistent: document_id drift"
        if record.identity_scope != resolution.identity_scope:
            return "durable flow set inconsistent: identity_scope drift"
        if record.identity_fingerprint != resolution.identity_fingerprint:
            return "durable flow set inconsistent: identity_fingerprint drift"
        if record.declared_origin != resolution.declared_origin:
            return "durable flow set inconsistent: declared_origin drift"
        if record.flow_outcome == FLOW_OUTCOME_IDENTITY_ESTABLISHED:
            if observation is not None:
                return ("durable flow set inconsistent: IDENTITY_"
                        "ESTABLISHED over a resolution carrying a duplicate "
                        "observation")
        else:
            if observation is None:
                return ("durable flow set inconsistent: DUPLICATE_"
                        "RECOGNIZED without the linked observation")
            if (observation.observation_id
                    != record.duplicate_observation_id
                    or observation.resolution_id != record.resolution_id
                    or observation.original_resolution_id
                    != record.original_resolution_id):
                return ("durable flow set inconsistent: observation "
                        "references disagree")
        return None

    # ------------------------------------------------------------------
    # Durable duplicate register (OD-DF-H)
    # ------------------------------------------------------------------

    def duplicates_of(self, original_resolution_id: str) \
            -> List[FlowDispositionRecord]:
        """The durable duplicate register: every DUPLICATE_RECOGNIZED
        disposition anchored to that original (raw records, listing
        discipline; verify through read_disposition_by_id)."""
        return self._store.find_dispositions_by_original(
            original_resolution_id)

    def dispositions(self) -> List[FlowDispositionRecord]:
        """All committed dispositions (raw records, listing discipline)."""
        return self._store.list_dispositions()

    @property
    def issue_reports(self) -> list:
        return list(self._issues)
