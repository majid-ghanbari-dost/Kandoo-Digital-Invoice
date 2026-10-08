"""Identity Resolution service — WP-7.1 MVP implementation.

Binding basis: SPEC-WP71-IDRES §2/§3/§4/§5/§6/§8/§9. The entry point and
orchestration layer: verified P5.2 domain states + verified WP-4.1 reads +
declared requests → deterministic identity resolutions → durable, immutable,
provenance-anchored resolution records with exact duplicate observations.

Fail-closed ordering (SPEC §4): input verification (V1 verified P5.2 read →
V2 whole-chain trace → V3 origin validation → V4 binding validation) precedes
EVERY resolution; S1 replay recognition (R0) precedes the S2 attempt (R1);
the exact-duplicate check (R2) and the atomic commit (R3) complete the
ladder. No outcome is ever silent; no refusal leaves residue; no upstream
layer is ever executed (spy-proven); no identity formula lives here beyond
the record-integrity anchors (the frozen P6.1 primitive is the only formula
source — OD-IR-G).
"""
from __future__ import annotations

from typing import List, Mapping, Optional, Tuple

import uuid

from capture import S1Service

from normalization import (
    NormalizationReadIntegrityFailure,
    NormalizationReadRefused,
    NormalizationReadSuccess,
    NormalizationReadVerificationUnavailable,
    NormalizationService,
)
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

from .model import (
    DISPOSITION_CLEAR,
    IDENTITY_ROLES,
    IDENTITY_SCOPE_CAPTURE_SCOPED,
    IDENTITY_SCOPE_S2,
    NOTE_VERIFY_FAILED,
    REFUSE_BINDING_MALFORMED,
    REFUSE_NO_SUCH_STATE,
    REFUSE_ORIGIN_NATIVE_FLOW,
    REFUSE_ORIGIN_UNKNOWN,
    REFUSE_REPLAY_DECLARATION_DRIFT,
    STATE_VALID,
    IdentityDefiniteDuplicate,
    IdentityDuplicateObservation,
    IdentityInputIntegrityFailure,
    IdentityPersistenceUnavailable,
    IdentityReadIntegrityFailure,
    IdentityReadRefused,
    IdentityReadSuccess,
    IdentityReadVerificationUnavailable,
    IdentityResolutionRecord,
    IdentityResolutionRecorded,
    IdentityReplay,
    IdentityRequestRefused,
    IdentityRoleCandidateRow,
    IdentityStorageUnavailable,
    ResolutionDuplicate,
    ResolutionNotFound,
    utc_now_iso,
)
from .resolver import (
    binding_declaration_fingerprint,
    resolve_document_identity,
    validate_declared_origin,
)
from .store import (
    IdentityResolutionStore,
    canonical_observation_bytes,
    canonical_resolution_bytes,
)


class IdentityResolutionService:
    """The WP-7.1 entry point: verified P5.2 states → deterministic S1/S2/
    CAPTURE_SCOPED resolutions → durable identity records with exact D-03
    duplicate handling and complete provenance."""

    def __init__(self, store: IdentityResolutionStore,
                 domain: ValidationDomainService,
                 normalization: NormalizationService,
                 s1: S1Service) -> None:
        self._store = store
        self._domain = domain
        self._normalization = normalization
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Resolution — resolve (SPEC §4)
    # ------------------------------------------------------------------

    def resolve(self, domain_state_id: str, declared_origin: str,
                identity_field_binding: Optional[Mapping[str, str]] = None,
                ) -> object:
        """Resolve the identity of ONE verified P5.2 domain state's capture
        artifact. Outcome is exactly one explicit type — never silent:
          IdentityResolutionRecorded | IdentityDefiniteDuplicate |
          IdentityReplay | IdentityRequestRefused |
          IdentityInputIntegrityFailure | IdentityStorageUnavailable.
        """
        # -- V1: verified P5.2 read (fail-closed — no resolution on
        # unverified input, even if a prior resolution exists)
        head = self._domain.read_domain_state(domain_state_id)
        if isinstance(head, DomainStateReadRefused):
            return IdentityRequestRefused(
                None, f"{REFUSE_NO_SUCH_STATE}: {head.detail}")
        if isinstance(head, DomainStateReadIntegrityFailure):
            return IdentityInputIntegrityFailure(None, head.reason)
        if isinstance(head, DomainStateReadVerificationUnavailable):
            self._issues.append(f"resolve {domain_state_id}: "
                                f"{head.issue_report}")
            return IdentityInputIntegrityFailure(None, head.issue_report)
        state_record = head.record

        # -- V2: whole-chain provenance verification (consumed through the
        # P5.2 trace — never bypassed; no broken link silently accepted)
        walk = self._domain.trace_domain_state(domain_state_id)
        if isinstance(walk, DomainStateTraceRefused):
            return IdentityInputIntegrityFailure(
                domain_state_id, f"provenance walk refused: {walk.detail}")
        if isinstance(walk, DomainStateTraceIntegrityFailure):
            return IdentityInputIntegrityFailure(
                domain_state_id,
                f"broken provenance chain at link '{walk.link}': "
                f"{walk.reason}")
        if isinstance(walk, DomainStateTraceVerificationUnavailable):
            self._issues.append(f"resolve {domain_state_id}: "
                                f"{walk.issue_report}")
            return IdentityInputIntegrityFailure(
                domain_state_id,
                f"provenance verification unavailable: {walk.issue_report}")

        # -- V3: declared origin validation (frozen vocabulary; AS-02)
        origin_problem = validate_declared_origin(declared_origin)
        if origin_problem == REFUSE_ORIGIN_UNKNOWN:
            return IdentityRequestRefused(
                domain_state_id,
                f"declared_origin {declared_origin!r} is outside the frozen "
                f"origin vocabulary "
                f"(KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE)")
        if origin_problem == REFUSE_ORIGIN_NATIVE_FLOW:
            return IdentityRequestRefused(
                domain_state_id,
                f"declared_origin {declared_origin!r} is the native-flow "
                f"origin (AS-02: no capture pipeline, no P5.2 state) — not "
                f"consumable from a P5.2-sourced request")

        # -- V4: declared binding validation (fail-closed, never 'repaired')
        try:
            declaration_fp = binding_declaration_fingerprint(
                identity_field_binding, self._s1)
        except ValueError as exc:
            return IdentityRequestRefused(
                domain_state_id, f"{REFUSE_BINDING_MALFORMED}: {exc}")

        # -- R0: S1 replay recognition — an existing resolution for this
        # capture_s1 returns verbatim (read-only; D-02/D-03 idempotency: a
        # replay never creates a second identity). The replayed record must
        # first VERIFY (never replay from a tampered row) and its declared
        # request must match (drift → refusal, never a silent reshape).
        existing = self._store.find_resolution_by_capture(
            state_record.capture_s1)
        if existing is not None:
            verified = self.read_resolution(existing.resolution_id)
            if isinstance(verified, IdentityReadIntegrityFailure):
                return IdentityInputIntegrityFailure(
                    domain_state_id,
                    f"existing resolution failed verification: "
                    f"{verified.reason}")
            if isinstance(verified, IdentityReadVerificationUnavailable):
                self._issues.append(f"resolve {domain_state_id}: "
                                    f"{verified.issue_report}")
                return IdentityInputIntegrityFailure(
                    domain_state_id, verified.issue_report)
            if isinstance(verified, IdentityReadRefused):
                return IdentityInputIntegrityFailure(
                    domain_state_id,
                    f"existing resolution unreadable: {verified.detail}")
            prior = verified.record
            if (prior.declared_origin != declared_origin
                    or prior.binding_declaration_fingerprint
                    != declaration_fp):
                return IdentityRequestRefused(
                    domain_state_id,
                    f"{REFUSE_REPLAY_DECLARATION_DRIFT}: the identity of "
                    f"capture {state_record.capture_s1} was already "
                    f"resolved under a different declared request")
            return IdentityReplay(prior, verified.role_rows,
                                  verified.observation, utc_now_iso())

        # -- R1: the scope attempt (VALID/CLEAR → the frozen P6.1 primitive
        # over the verified WP-4.1 read; otherwise CAPTURE_SCOPED with NO
        # value consumption)
        normalized_fields = None
        if (state_record.domain_state == STATE_VALID
                and state_record.disposition == DISPOSITION_CLEAR):
            norm_read = self._normalization.read_normalization(
                state_record.normalization_id)
            if isinstance(norm_read, NormalizationReadIntegrityFailure):
                return IdentityInputIntegrityFailure(
                    domain_state_id,
                    f"normalization read failed verification: "
                    f"{norm_read.reason}")
            if isinstance(norm_read, NormalizationReadRefused):
                return IdentityInputIntegrityFailure(
                    domain_state_id,
                    f"normalization read refused: {norm_read.detail}")
            if isinstance(norm_read, NormalizationReadVerificationUnavailable):
                self._issues.append(f"resolve {domain_state_id}: "
                                    f"{norm_read.issue_report}")
                return IdentityInputIntegrityFailure(
                    domain_state_id, norm_read.issue_report)
            assert isinstance(norm_read, NormalizationReadSuccess)
            normalized_fields = norm_read.fields
        try:
            decision = resolve_document_identity(
                state_record, declared_origin, identity_field_binding,
                normalized_fields, self._s1)
        except ValueError as exc:
            return IdentityRequestRefused(domain_state_id, f"{exc}")

        # -- R2: exact duplicate detection (D-03) — the ONLY comparison is
        # fingerprint equality across DIFFERENT captures (origin rides the
        # fingerprint, so cross-origin collisions cannot exist).
        observation: Optional[IdentityDuplicateObservation] = None
        original: Optional[IdentityResolutionRecord] = None
        if decision.identity_fingerprint:
            candidates = [
                r for r in self._store.find_resolutions_by_identity(
                    decision.identity_fingerprint)
                if r.capture_s1 != state_record.capture_s1]
            if candidates:
                original = candidates[0]      # deterministic earliest (OD-IR-E)
                observation = IdentityDuplicateObservation(
                    observation_id=uuid.uuid4().hex,
                    resolution_id="",         # anchored below, at commit
                    original_resolution_id=original.resolution_id,
                    identity_fingerprint=decision.identity_fingerprint,
                    original_capture_s1=original.capture_s1,
                    duplicate_capture_s1=state_record.capture_s1,
                    created_at=utc_now_iso(),
                    observation_fingerprint="",
                    fingerprint_algorithm_id="")

        # -- R3: atomic commit (resolution + role rows + observation iff
        # duplicate) — zero residue on any failure; a concurrent duplicate
        # commit maps back to the replay outcome (INV-IR-S1:1 backstop).
        record = IdentityResolutionRecord(
            resolution_id=uuid.uuid4().hex,
            capture_s1=state_record.capture_s1,
            capture_s1_algorithm_id=state_record.capture_s1_algorithm_id,
            capture_id=state_record.capture_id,
            document_id=state_record.document_id,
            extraction_id=state_record.extraction_id,
            normalization_id=state_record.normalization_id,
            domain_state_id=state_record.domain_state_id,
            declared_origin=declared_origin,
            binding_declaration_fingerprint=declaration_fp,
            identity_scope=decision.identity_scope,
            identity_source=decision.identity_source,
            identity_fingerprint=decision.identity_fingerprint,
            scope_reason=decision.scope_reason,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="",
        )
        role_rows = self._build_role_rows(record, decision)
        if observation is not None:
            observation = IdentityDuplicateObservation(
                **{**observation.__dict__,
                   "resolution_id": record.resolution_id})
        try:
            saved = self._store.commit_resolution(record, role_rows,
                                                  observation)
        except ResolutionDuplicate as exc:
            raced = self._store.get_resolution(exc.existing_id)
            if (raced.declared_origin != declared_origin
                    or raced.binding_declaration_fingerprint
                    != declaration_fp):
                return IdentityRequestRefused(
                    domain_state_id,
                    f"{REFUSE_REPLAY_DECLARATION_DRIFT}: the identity of "
                    f"capture {state_record.capture_s1} was already "
                    f"resolved under a different declared request")
            verified = self.read_resolution(raced.resolution_id)
            if not isinstance(verified, IdentityReadSuccess):
                return IdentityInputIntegrityFailure(
                    domain_state_id,
                    "concurrent resolution failed verification")
            return IdentityReplay(verified.record, verified.role_rows,
                                  verified.observation, utc_now_iso())
        except IdentityPersistenceUnavailable as exc:
            return IdentityStorageUnavailable(str(exc))

        saved_rows = self._store.get_role_rows(saved.resolution_id)
        saved_obs = self._store.get_observation(saved.resolution_id)
        if saved_obs is not None:
            assert original is not None
            return IdentityDefiniteDuplicate(saved, original, saved_obs,
                                             tuple(saved_rows))
        return IdentityResolutionRecorded(saved, tuple(saved_rows), None)

    def _build_role_rows(self, record: IdentityResolutionRecord,
                         decision) -> Tuple[IdentityRoleCandidateRow, ...]:
        """Materialize the role candidate evidence rows in FROZEN role order
        (declarations + counts + pointers — never values)."""
        by_role = {spec.role: spec for spec in decision.role_specs}
        rows = []
        for role in IDENTITY_ROLES:
            spec = by_role.get(role)
            if spec is None:
                continue
            rows.append(IdentityRoleCandidateRow(
                resolution_id=record.resolution_id,
                role=role,
                source_field_name=spec.source_field_name,
                candidate_count=spec.candidate_count,
                field_seqs=tuple(sorted(spec.field_seqs)),
                resolved_field_seq=spec.resolved_field_seq))
        return tuple(rows)

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

    def _structural_check(self, record: IdentityResolutionRecord,
                          role_rows, observation) -> Optional[str]:
        """Durable-set consistency beyond the hash anchor (OD-IR5/OD-IR6):
        scope/role/observation shapes that a forged or half-written row
        cannot satisfy."""
        if record.identity_scope == IDENTITY_SCOPE_S2:
            if (not record.identity_fingerprint
                    or record.identity_source == ""
                    or record.scope_reason != ""
                    or len(role_rows) != 3):
                return ("durable resolution set inconsistent: S2 scope "
                        "without the fingerprint/source/three-role shape")
            if any(row.resolved_field_seq is None
                   or row.candidate_count != 1 for row in role_rows):
                return ("durable resolution set inconsistent: S2 role rows "
                        "without single-candidate resolution pointers")
        else:
            if (record.identity_fingerprint != ""
                    or record.identity_source != ""
                    or len(role_rows) > 3):
                return ("durable resolution set inconsistent: CAPTURE_SCOPED "
                        "scope with fingerprint/source/role rows")
            if any(row.resolved_field_seq is not None
                   for row in role_rows):
                return ("durable resolution set inconsistent: CAPTURE_SCOPED "
                        "scope with resolved role pointers")
        if observation is not None:
            if (record.identity_scope != IDENTITY_SCOPE_S2
                    or observation.resolution_id != record.resolution_id
                    or observation.identity_fingerprint
                    != record.identity_fingerprint
                    or observation.duplicate_capture_s1 != record.capture_s1
                    or observation.original_capture_s1
                    == record.capture_s1):
                return ("durable duplicate-observation set inconsistent")
        return None

    def read_resolution(self, resolution_id: str) -> object:
        """Read a resolution with a definitive integrity verdict computed
        INSIDE the read (record + role rows + observation iff present)."""
        try:
            record = self._store.get_resolution(resolution_id)
        except ResolutionNotFound:
            return IdentityReadRefused(None, "no such identity resolution")
        return self._verified_read(record)

    def read_resolution_by_capture(self, capture_s1: str) -> object:
        """Read a resolution by its S1 capture anchor."""
        record = self._store.find_resolution_by_capture(capture_s1)
        if record is None:
            return IdentityReadRefused(
                None, "no identity resolution for this capture_s1")
        return self._verified_read(record)

    def _verified_read(self, record: IdentityResolutionRecord) -> object:
        role_rows = tuple(self._store.get_role_rows(record.resolution_id))
        observation = self._store.get_observation(record.resolution_id)
        problem = self._verify(
            canonical_resolution_bytes(record, role_rows),
            record.record_fingerprint, record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return IdentityReadIntegrityFailure(
                    record.resolution_id, problem, utc_now_iso())
            self._issues.append(f"identity resolution "
                                f"{record.resolution_id}: {problem}")
            return IdentityReadVerificationUnavailable(
                record.resolution_id, problem + " — Issue Report required")
        if observation is not None:
            oproblem = self._verify(
                canonical_observation_bytes(observation),
                observation.observation_fingerprint,
                observation.fingerprint_algorithm_id)
            if oproblem is not None:
                if oproblem == NOTE_VERIFY_FAILED:
                    return IdentityReadIntegrityFailure(
                        record.resolution_id,
                        f"linked duplicate observation {oproblem}",
                        utc_now_iso())
                self._issues.append(
                    f"identity resolution {record.resolution_id}: {oproblem}")
                return IdentityReadVerificationUnavailable(
                    record.resolution_id,
                    oproblem + " — Issue Report required")
        structural = self._structural_check(record, role_rows, observation)
        if structural is not None:
            self._issues.append(f"identity resolution "
                                f"{record.resolution_id}: {structural}")
            return IdentityReadVerificationUnavailable(
                record.resolution_id, structural + " — Issue Report required")
        return IdentityReadSuccess(record, role_rows, observation,
                                   utc_now_iso())
