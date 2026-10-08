"""Canonical Assembly + invoice_id Issuance service — WP-6.2 MVP.

Binding basis: SPEC-WP62-CANASM §2/§3/§4/§5/§6/§7/§8/§9. The entry point and
orchestration layer: P6.1 ACCEPTED admissions + declared line structures →
fail-closed verification (A1..A6) → deterministic canonical assembly → the
durable issued Canonical Invoice (invoice_id consumed VERBATIM from the
admission — OD-A1).

Fail-closed ordering (SPEC §4): input verification (A1 verified P6.1
admission read → A2 consumed whole-chain trace → A3 ACCEPTED-only → A4
declaration validation → A5 verified upstream value reads → A6 identity-anchor
consistency) precedes EVERY assembly; replay (OD-A8) precedes assembly; the
commit is atomic (OD-C2). No outcome is ever silent; no refusal leaves
residue; no upstream layer is ever executed (spy-proven).
"""
from __future__ import annotations

from typing import List, Mapping, Optional, Tuple

from capture import S1Service
from canonicalization import (
    CanonicalInvoiceReadIntegrityFailure,
    CanonicalInvoiceReadRefused,
    CanonicalInvoiceReadSuccess,
    CanonicalInvoiceReadVerificationUnavailable,
    CanonicalInvoiceTraceIntegrityFailure,
    CanonicalInvoiceTraceRefused,
    CanonicalInvoiceTraceSuccess,
    CanonicalInvoiceTraceVerificationUnavailable,
    CanonicalizationGateService,
    DECISION_ACCEPTED,
)
from derivation import (
    DerivationReadIntegrityFailure,
    DerivationReadRefused,
    DerivationReadSuccess,
    DerivationReadVerificationUnavailable,
    DerivationService,
)
from normalization import (
    NormalizationReadIntegrityFailure,
    NormalizationReadRefused,
    NormalizationReadSuccess,
    NormalizationReadVerificationUnavailable,
    NormalizationService,
)

from .assembly import (
    assemble_fields,
    assemble_header_anchors,
    assemble_lines,
    declaration_bytes,
    identity_anchor_payload,
    validate_line_binding,
)
from .model import (
    CUSTOMER_REF_REASON,
    NOTE_VERIFY_FAILED,
    REJECT_DECLARATION_CONFLICT,
    REJECT_DECLARATION_MALFORMED,
    REFUSE_NO_ADMISSION,
    AssemblyAlreadyAssembled,
    AssemblyCompleted,
    AssemblyInputIntegrityFailure,
    AssemblyReadIntegrityFailure,
    AssemblyReadRefused,
    AssemblyReadSuccess,
    AssemblyReadVerificationUnavailable,
    AssemblyRequestRefused,
    AssemblyStorageUnavailable,
    AssemblyTraceIntegrityFailure,
    AssemblyTraceRefused,
    AssemblyTraceSuccess,
    AssemblyTraceVerificationUnavailable,
    CanonicalFieldEntry,
    CanonicalHeaderAnchor,
    CanonicalLineField,
    CanonicalLineRecord,
    CanonicalAssemblyPersistenceUnavailable,
    IssuedCanonicalInvoiceRecord,
    IssuedInvoiceDuplicate,
    IssuedInvoiceNotFound,
    RejectedLine,
    utc_now_iso,
)
from .store import CanonicalAssemblyStore, canonical_invoice_bytes


class CanonicalAssemblyService:
    """The WP-6.2 entry point: P6.1 ACCEPTED admissions → deterministic
    canonical assembly → issued Canonical Invoices with complete provenance."""

    def __init__(self, store: CanonicalAssemblyStore,
                 gate: CanonicalizationGateService,
                 normalization: NormalizationService,
                 derivation: DerivationService,
                 s1: S1Service) -> None:
        self._store = store
        self._gate = gate
        self._normalization = normalization
        self._derivation = derivation
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # The Assembly — assemble (SPEC §3/§4/§5/§6/§7)
    # ------------------------------------------------------------------

    def assemble(self, canonical_invoice_id: str,
                 line_binding: Optional[Mapping[object, object]] = None
                 ) -> object:
        """Assemble the Canonical Invoice for ONE P6.1 ACCEPTED admission and
        issue it. Outcome is exactly one explicit type — never silent:
          AssemblyCompleted | AssemblyAlreadyAssembled |
          AssemblyInputIntegrityFailure | AssemblyRequestRefused |
          AssemblyStorageUnavailable.
        """
        # -- A1: verified P6.1 admission read (fail-closed — no assembly on
        # unverified input)
        admission = self._gate.read_canonical_invoice(canonical_invoice_id)
        if isinstance(admission, CanonicalInvoiceReadRefused):
            return AssemblyRequestRefused(
                canonical_invoice_id,
                f"{REFUSE_NO_ADMISSION}: {admission.detail} — only the "
                f"ACCEPTED decision of the P6.1 Gate has an admission record "
                f"and only that admission can be assembled (REJECTED / "
                f"REVIEW / ALREADY_CANONICALIZED never produce an invoice)")
        if isinstance(admission, CanonicalInvoiceReadIntegrityFailure):
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id, admission.reason)
        if isinstance(admission, CanonicalInvoiceReadVerificationUnavailable):
            self._issues.append(f"assemble {canonical_invoice_id}: "
                                f"{admission.issue_report}")
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id, admission.issue_report)

        admission_record = admission.record
        decision = admission.decision
        if decision.decision != DECISION_ACCEPTED:
            # A3 — structurally unreachable through the P6.1 read (it already
            # enforces the ACCEPTED linkage); defensive fail-closure anyway.
            return AssemblyRequestRefused(
                canonical_invoice_id,
                f"{REFUSE_NO_ADMISSION}: linked gate decision is "
                f"{decision.decision} — only ACCEPTED admissions assemble")

        # -- A2: P6.1 whole-chain provenance verification (consumed through
        # the P6.1 trace — never bypassed; no broken link silently accepted)
        walk = self._gate.trace_canonical_invoice(canonical_invoice_id)
        if isinstance(walk, CanonicalInvoiceTraceRefused):
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id, f"provenance walk refused: "
                                      f"{walk.detail}")
        if isinstance(walk, CanonicalInvoiceTraceIntegrityFailure):
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id,
                f"broken provenance chain at link '{walk.link}': "
                f"{walk.reason}")
        if isinstance(walk, CanonicalInvoiceTraceVerificationUnavailable):
            self._issues.append(f"assemble {canonical_invoice_id}: "
                                f"{walk.issue_report}")
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id,
                f"provenance verification unavailable: {walk.issue_report}")

        # -- Replay gate (OD-A8: replay never re-assembles — D-03)
        existing = self._store.find_invoice_by_admission(
            decision.decision_id)
        if existing is not None:
            problem = self._verify_invoice(existing.invoice_id)
            if problem is not None:
                if problem == NOTE_VERIFY_FAILED:
                    return AssemblyInputIntegrityFailure(
                        canonical_invoice_id,
                        f"existing issued invoice {problem}")
                self._issues.append(f"assemble {canonical_invoice_id}: "
                                    f"{problem}")
                return AssemblyInputIntegrityFailure(
                    canonical_invoice_id,
                    problem + " — Issue Report required")
            try:
                declaration_fp = self._s1.compute(
                    declaration_bytes(line_binding)).s1
            except Exception as exc:
                return AssemblyRequestRefused(
                    canonical_invoice_id,
                    f"declaration fingerprint failure: {exc}")
            if existing.declaration_fingerprint != declaration_fp:
                return AssemblyRequestRefused(
                    canonical_invoice_id,
                    f"{REJECT_DECLARATION_CONFLICT}: an invoice is already "
                    f"issued for this admission under a different declared "
                    f"line structure — no second invoice, no silent reshape "
                    f"(OD-A8)")
            return self._already_assembled(existing)

        # -- A4: declaration validation (fail-closed, never 'repaired')
        try:
            normalized_binding = validate_line_binding(line_binding)
        except ValueError as exc:
            return AssemblyRequestRefused(
                canonical_invoice_id,
                f"{REJECT_DECLARATION_MALFORMED}: {exc}")
        try:
            declaration_fp = self._s1.compute(
                declaration_bytes(line_binding)).s1
        except Exception as exc:
            return AssemblyRequestRefused(
                canonical_invoice_id,
                f"declaration fingerprint failure: {exc}")

        # -- A5: verified upstream value reads (the only sanctioned paths)
        norm_read = self._normalization.read_normalization(
            admission_record.normalization_id)
        if isinstance(norm_read, NormalizationReadIntegrityFailure):
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id,
                f"normalization read failed verification: {norm_read.reason}")
        if isinstance(norm_read, NormalizationReadRefused):
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id,
                f"normalization read refused: {norm_read.detail}")
        if isinstance(norm_read, NormalizationReadVerificationUnavailable):
            self._issues.append(f"assemble {canonical_invoice_id}: "
                                f"{norm_read.issue_report}")
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id, norm_read.issue_report)
        normalized_fields = norm_read.fields

        derived_outputs: List[object] = []
        for derivation_id in self._derivation.derivations_for_normalization(
                admission_record.normalization_id):
            d_read = self._derivation.read_derivation(derivation_id)
            if isinstance(d_read, DerivationReadIntegrityFailure):
                return AssemblyInputIntegrityFailure(
                    canonical_invoice_id,
                    f"derivation read failed verification: {d_read.reason}")
            if isinstance(d_read, DerivationReadRefused):
                return AssemblyInputIntegrityFailure(
                    canonical_invoice_id,
                    f"derivation read refused: {d_read.detail}")
            if isinstance(d_read, DerivationReadVerificationUnavailable):
                self._issues.append(f"assemble {canonical_invoice_id}: "
                                    f"{d_read.issue_report}")
                return AssemblyInputIntegrityFailure(
                    canonical_invoice_id, d_read.issue_report)
            derived_outputs.append(d_read)

        # -- A6: identity-anchor consistency (OD-A6 — the P6.1 OD-G4 formula,
        # quoted exactly; verification, not re-decision)
        try:
            anchors = assemble_header_anchors(
                canonical_invoice_id, admission.identity_pointers,
                normalized_fields)
        except ValueError as exc:
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id, str(exc))
        try:
            recomputed = self._s1.compute(identity_anchor_payload(
                decision.declared_origin, anchors))
        except Exception as exc:
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id,
                f"identity anchor computation failure: {exc}")
        if recomputed.s1 != admission_record.identity_fingerprint:
            return AssemblyInputIntegrityFailure(
                canonical_invoice_id,
                "identity anchor mismatch: the re-joined header values do "
                "not reproduce the admission's identity_fingerprint (the "
                "Gate-resolved identity and the verified read disagree)")

        # -- Canonical assembly (pure, deterministic — SPEC §5/§6)
        fields = assemble_fields(canonical_invoice_id,
                                 admission_record.normalization_id,
                                 normalized_fields, derived_outputs)
        try:
            lines, line_fields, rejected = assemble_lines(
                canonical_invoice_id, admission_record.normalization_id,
                normalized_binding, normalized_fields)
        except ValueError as exc:
            return AssemblyRequestRefused(canonical_invoice_id, f"{exc}")

        invoice = IssuedCanonicalInvoiceRecord(
            invoice_id=canonical_invoice_id,          # OD-A1: consumed verbatim
            admission_decision_id=decision.decision_id,
            domain_state_id=admission_record.domain_state_id,
            normalization_id=admission_record.normalization_id,
            extraction_id=admission_record.extraction_id,
            document_id=admission_record.document_id,
            capture_id=admission_record.capture_id,
            capture_s1=admission_record.capture_s1,
            capture_s1_algorithm_id=admission_record.capture_s1_algorithm_id,
            origin=admission_record.origin,
            identity_class=admission_record.identity_class,
            identity_source=admission_record.identity_source,
            identity_fingerprint=admission_record.identity_fingerprint,
            customer_reference=None,                  # OD-A9 (D-06)
            customer_reference_reason=CUSTOMER_REF_REASON,
            declaration_fingerprint=declaration_fp,
            field_count=len(fields),
            line_count=len(lines),
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="",
        )

        # -- Atomic commit (OD-C2: assembly + issuance in ONE transaction)
        try:
            saved = self._store.commit_invoice(invoice, anchors, fields,
                                               lines, line_fields)
        except CanonicalAssemblyPersistenceUnavailable as exc:
            return AssemblyStorageUnavailable(str(exc))
        except IssuedInvoiceDuplicate as exc:
            prior = self._store.get_invoice(exc.existing_id)
            return self._already_assembled(prior)

        return AssemblyCompleted(
            invoice=saved,
            header_anchors=tuple(self._store.get_anchors(saved.invoice_id)),
            fields=tuple(self._store.get_fields(saved.invoice_id)),
            lines=tuple(self._store.get_lines(saved.invoice_id)),
            line_fields=tuple(
                self._store.get_line_fields(saved.invoice_id)),
            rejected_lines=tuple(rejected),
        )

    def _already_assembled(self, existing) -> AssemblyAlreadyAssembled:
        return AssemblyAlreadyAssembled(
            invoice=existing,
            header_anchors=tuple(
                self._store.get_anchors(existing.invoice_id)),
            fields=tuple(self._store.get_fields(existing.invoice_id)),
            lines=tuple(self._store.get_lines(existing.invoice_id)),
            line_fields=tuple(
                self._store.get_line_fields(existing.invoice_id)),
        )

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

    def _verify_invoice(self, invoice_id: str) -> Optional[str]:
        """Full VOR of one issued invoice: scalars + anchors + fields + lines
        + line fields against the committed record_fingerprint (OD-C5)."""
        try:
            record = self._store.get_invoice(invoice_id)
        except IssuedInvoiceNotFound:
            return None
        anchors = self._store.get_anchors(invoice_id)
        fields = self._store.get_fields(invoice_id)
        lines = self._store.get_lines(invoice_id)
        line_fields = self._store.get_line_fields(invoice_id)
        if len(fields) != record.field_count \
                or len(lines) != record.line_count:
            return (f"durable content set inconsistent "
                    f"(fields={len(fields)}/{record.field_count}, "
                    f"lines={len(lines)}/{record.line_count})")
        return self._verify(
            canonical_invoice_bytes(record, anchors, fields, lines,
                                    line_fields),
            record.record_fingerprint, record.fingerprint_algorithm_id)

    def read_assembled_invoice(self, invoice_id: str) -> object:
        """Read an issued Canonical Invoice with a definitive integrity
        verdict computed INSIDE the read (scalars + anchors + fields + lines
        + line fields — the whole content set)."""
        try:
            record = self._store.get_invoice(invoice_id)
        except IssuedInvoiceNotFound:
            return AssemblyReadRefused(None, "no such issued invoice")
        anchors = self._store.get_anchors(invoice_id)
        fields = self._store.get_fields(invoice_id)
        lines = self._store.get_lines(invoice_id)
        line_fields = self._store.get_line_fields(invoice_id)
        if len(anchors) != 3:
            issue = (f"durable header anchor set inconsistent "
                     f"(rows={len(anchors)}, expected 3)")
            self._issues.append(f"issued invoice {invoice_id}: {issue}")
            return AssemblyReadVerificationUnavailable(
                invoice_id, issue + " — Issue Report required")
        if len(fields) != record.field_count \
                or len(lines) != record.line_count:
            issue = (f"durable content set inconsistent "
                     f"(fields={len(fields)}/{record.field_count}, "
                     f"lines={len(lines)}/{record.line_count})")
            self._issues.append(f"issued invoice {invoice_id}: {issue}")
            return AssemblyReadVerificationUnavailable(
                invoice_id, issue + " — Issue Report required")
        problem = self._verify(
            canonical_invoice_bytes(record, anchors, fields, lines,
                                    line_fields),
            record.record_fingerprint, record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return AssemblyReadIntegrityFailure(
                    invoice_id, problem, utc_now_iso())
            self._issues.append(f"issued invoice {invoice_id}: {problem}")
            return AssemblyReadVerificationUnavailable(
                invoice_id, problem + " — Issue Report required")
        return AssemblyReadSuccess(record, tuple(anchors), tuple(fields),
                                   tuple(lines), tuple(line_fields),
                                   utc_now_iso())

    # ------------------------------------------------------------------
    # Traceability walk — issued invoice → P6.1 admission → gate decision
    # → P5.2 whole-chain (→ … → Capture S1) + pointer/value re-join (SPEC §9)
    # ------------------------------------------------------------------

    def trace_assembled_invoice(self, invoice_id: str) -> object:
        """Walk the full provenance chain with verified reads on EVERY link
        inside this one call. The P6.1 trace is consumed, never bypassed.
        Every canonical field and line field pointer is re-joined against the
        verified reads and byte-checked. Deliverable: ordered coarse link
        verdicts (no source values copied)."""
        head = self.read_assembled_invoice(invoice_id)
        if isinstance(head, AssemblyReadIntegrityFailure):
            return AssemblyTraceIntegrityFailure(
                invoice_id, "issued_invoice", head.reason)
        if isinstance(head, AssemblyReadRefused):
            return AssemblyTraceRefused(invoice_id, head.detail)
        if isinstance(head, AssemblyReadVerificationUnavailable):
            self._issues.append(f"trace {invoice_id}: {head.issue_report}")
            return AssemblyTraceVerificationUnavailable(
                invoice_id, head.issue_report)
        record = head.invoice

        chain: List[str] = [
            f"issued_invoice: {record.invoice_id[:12]}… "
            f"origin={record.origin} fields={record.field_count} "
            f"lines={record.line_count} declaration_fp="
            f"{record.declaration_fingerprint[:12]}…",
        ]

        # link: P6.1 admission + its whole-chain walk — consumed, never bypassed
        admission = self._gate.read_canonical_invoice(record.invoice_id)
        if isinstance(admission, CanonicalInvoiceReadIntegrityFailure):
            return AssemblyTraceIntegrityFailure(
                invoice_id, "admission", admission.reason)
        if isinstance(admission, CanonicalInvoiceReadRefused):
            return AssemblyTraceRefused(
                invoice_id, f"admission read refused: {admission.detail}")
        if isinstance(admission, CanonicalInvoiceReadVerificationUnavailable):
            self._issues.append(f"trace {invoice_id}: "
                                f"{admission.issue_report}")
            return AssemblyTraceVerificationUnavailable(
                invoice_id, admission.issue_report)
        if admission.decision.decision_id != record.admission_decision_id \
                or admission.decision.decision != DECISION_ACCEPTED:
            issue = ("admission linkage inconsistent: the issued invoice's "
                     "admission_decision_id does not match its ACCEPTED "
                     "gate decision (INV-AI-1:1)")
            self._issues.append(f"trace {invoice_id}: {issue}")
            return AssemblyTraceVerificationUnavailable(
                invoice_id, issue + " — Issue Report required")
        chain.append(
            f"admission: P6.1 ACCEPTED decision "
            f"{record.admission_decision_id[:12]}… "
            f"(verified in this walk)")

        walk = self._gate.trace_canonical_invoice(record.invoice_id)
        if isinstance(walk, CanonicalInvoiceTraceIntegrityFailure):
            return AssemblyTraceIntegrityFailure(
                invoice_id, "domain_state",
                f"link '{walk.link}': {walk.reason}")
        if isinstance(walk, CanonicalInvoiceTraceRefused):
            return AssemblyTraceRefused(
                invoice_id, f"P6.1 walk refused: {walk.detail}")
        if isinstance(walk, CanonicalInvoiceTraceVerificationUnavailable):
            self._issues.append(f"trace {invoice_id}: {walk.issue_report}")
            return AssemblyTraceVerificationUnavailable(
                invoice_id, walk.issue_report)
        chain.append(
            f"domain_state: P6.1 whole-chain re-verified in this walk "
            f"({len(walk.chain)} links, through the P5.2 whole-chain walk "
            f"to Capture S1)")
        chain.extend(f"  ↳ {link}" for link in walk.chain)

        # link: canonical field pointers re-join + byte-identity (OD-C5/A6)
        norm_read = self._normalization.read_normalization(
            record.normalization_id)
        if isinstance(norm_read, NormalizationReadIntegrityFailure):
            return AssemblyTraceIntegrityFailure(
                invoice_id, "fields", norm_read.reason)
        if isinstance(norm_read, NormalizationReadRefused):
            return AssemblyTraceRefused(
                invoice_id,
                f"normalization read refused: {norm_read.detail}")
        if isinstance(norm_read, NormalizationReadVerificationUnavailable):
            self._issues.append(f"trace {invoice_id}: "
                                f"{norm_read.issue_report}")
            return AssemblyTraceVerificationUnavailable(
                invoice_id, norm_read.issue_report)
        norm_by_key = {(f.source_field_name, f.field_seq): f
                       for f in norm_read.fields}
        for f in head.fields:
            if f.provenance == "EXTRACTED":
                row = norm_by_key.get((f.field_name, f.source_field_seq))
                if row is None or row.normalized_value != f.canonical_value:
                    return AssemblyTraceIntegrityFailure(
                        invoice_id, "fields",
                        f"field {f.canonical_seq} → "
                        f"{f.field_name}/{f.source_field_seq} does not "
                        f"re-join a NORMALIZED row with a byte-identical "
                        f"value in the verified read")
        deriv_by_id = {}
        for derivation_id in self._derivation.derivations_for_normalization(
                record.normalization_id):
            d_read = self._derivation.read_derivation(derivation_id)
            if isinstance(d_read, DerivationReadSuccess):
                deriv_by_id[d_read.record.derivation_id] = d_read.record
        for f in head.fields:
            if f.provenance == "DERIVED":
                d = deriv_by_id.get(f.source_derivation_id)
                if d is None or d.output_value != f.canonical_value \
                        or d.output_field_name != f.field_name:
                    return AssemblyTraceIntegrityFailure(
                        invoice_id, "fields",
                        f"field {f.canonical_seq} → derivation "
                        f"{f.source_derivation_id} does not re-join with a "
                        f"byte-identical value in the verified read")
        chain.append(
            f"fields: {record.field_count} canonical fields re-joined their "
            f"verified upstream rows with byte-identical values")

        # link: line fields re-join + byte-identity
        for lf in head.line_fields:
            if lf.present:
                row = norm_by_key.get((lf.source_field_name, lf.field_seq))
                if row is None or row.normalized_value != lf.canonical_value:
                    return AssemblyTraceIntegrityFailure(
                        invoice_id, "lines",
                        f"line {lf.line_seq} role {lf.role} → "
                        f"{lf.source_field_name}/{lf.field_seq} does not "
                        f"re-join a NORMALIZED row with a byte-identical "
                        f"value in the verified read")
        chain.append(
            f"lines: {record.line_count} canonical lines re-joined their "
            f"declared verified rows with byte-identical values")

        return AssemblyTraceSuccess(invoice_id, tuple(chain),
                                    utc_now_iso())

    # ------------------------------------------------------------------
    # Listing helpers (tests / smoke / operator tooling)
    # ------------------------------------------------------------------

    def issued_invoices(self) -> List[IssuedCanonicalInvoiceRecord]:
        return self._store.list_invoices()

    def issue_reports(self) -> list:
        return list(self._issues)
