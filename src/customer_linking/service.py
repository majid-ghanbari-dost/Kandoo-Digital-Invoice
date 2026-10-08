"""Deterministic Customer Linking service — WP-9.1 MVP implementation.

Binding basis: SPEC-WP91-CUSTLINK §2/§3/§4/§5/§6. The entry point and
orchestration layer: every `link` call consumes the WP-6.2 verified read
(`CanonicalAssemblyService.read_assembled_invoice`) VERBATIM — never
bypassed, never re-implemented, never triggered for upstream execution —
and maps the outcome deterministically onto the linking ladder L1–L6:

  L1  P6.2 read refused / integrity failure / verification unavailable →
      fail-closed passthrough, zero durable residue (details verbatim)
  L2  malformed declaration → refused (zero residue)
  L3  declared field not found / ambiguous → refused (never auto-resolution)
  L4  replay (existing durable outcome for the declaration) → verified
      verbatim return, ZERO new rows — replay never re-decides (OD-CL4)
  L5  exact customer lookup: 1 → LINKED (to the EXISTING customer — D-06);
      0 → UNRESOLVED (no-customer-identity); ≥2 → fail-closed integrity
      failure (OD-CL5)
  L6  atomic commit; collision on the UNIQUE declaration key → re-read the
      winner and return the replay outcome (read-only)

D-06/DEF3 — STRUCTURAL NO-AUTO-CREATE (OD-CL2): the ONLY write path into
the customer register is `register_customer_identity`, which carries no
capture/invoice parameter. The link ladder has NO creation branch: its only
write is the append-only link row. A capture containing customer-looking
data can never produce a customer — only a deterministic link attempt.

Verified reads (§6): own-row VOR + re-verification of the linked invoice
through the P6.2 verified read + pointer re-join + customer identity
re-verification + the LIVE byte-identity re-proof. A tampered or drifting
row at ANY level withholds content — this layer never serves an unverified
fact.
"""
from __future__ import annotations

from typing import List, Optional

import uuid

from capture import S1Service

from canonical_assembly import (
    AssemblyReadIntegrityFailure,
    AssemblyReadRefused,
    AssemblyReadSuccess,
    AssemblyReadVerificationUnavailable,
    CanonicalAssemblyService,
)

from .model import (
    LINK_OUTCOME_LINKED,
    LINK_OUTCOME_UNRESOLVED,
    NOTE_VERIFY_FAILED,
    REFUSE_DECLARATION_MALFORMED,
    REFUSE_FIELD_AMBIGUOUS,
    REFUSE_FIELD_NOT_FOUND,
    UNRESOLVED_NO_CUSTOMER_IDENTITY,
    CustomerIdentityDuplicate,
    CustomerIdentityNotFound,
    CustomerIdentityRecord,
    CustomerLinkingPersistenceUnavailable,
    CustomerIdentityRegistered,
    CustomerIdentityReplay,
    CustomerLinked,
    LinkDuplicate,
    LinkNotFound,
    CustomerLinkInputIntegrityFailure,
    CustomerLinkReadIntegrityFailure,
    CustomerLinkReadRefused,
    CustomerLinkReadSuccess,
    CustomerLinkReadVerificationUnavailable,
    CustomerLinkRecord,
    CustomerLinkReplay,
    CustomerLinkRequestRefused,
    CustomerLinkStorageUnavailable,
    CustomerLinkUnresolved,
    CustomerReadIntegrityFailure,
    CustomerReadRefused,
    CustomerReadSuccess,
    CustomerReadVerificationUnavailable,
    CustomerRegistrationRefused,
    CustomerStorageUnavailable,
    utc_now_iso,
)
from .store import (
    CustomerLinkingStore,
    canonical_customer_identity_bytes,
    canonical_link_bytes,
)


class CustomerLinkingService:
    """The WP-9.1 entry point: issued Canonical Invoices (P6.2) + the
    explicit customer register → deterministic, auditable, append-only
    link facts (D-06 — to EXISTING customers only; never a creation)."""

    def __init__(self, store: CustomerLinkingStore,
                 assembly: CanonicalAssemblyService,
                 s1: S1Service) -> None:
        self._store = store
        self._assembly = assembly
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Customer registration (SPEC §3 — explicit, idempotent, OD-CL2)
    # ------------------------------------------------------------------

    def register_customer_identity(self, identifier_kind: str,
                                   identifier_value: str) -> object:
        """Register ONE EXISTING customer's identity (explicit declared
        registration ONLY — the API carries no capture/invoice parameter,
        so no capture-derived customer creation is possible, D-06/DEF3/
        OD-CL2). Exactly one explicit outcome — never silent:
          CustomerIdentityRegistered | CustomerIdentityReplay |
          CustomerRegistrationRefused | CustomerStorageUnavailable.
        """
        if not identifier_kind or not identifier_value:
            return CustomerRegistrationRefused(
                "customer registration refused: identifier_kind and "
                "identifier_value must be non-empty (declared verbatim, "
                "no defaults — OD-CL3)")
        record = CustomerIdentityRecord(
            customer_identity_id=uuid.uuid4().hex,
            identifier_kind=identifier_kind,
            identifier_value=identifier_value,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="")
        try:
            saved = self._store.commit_customer_identity(record)
        except CustomerIdentityDuplicate:
            existing = self._store.find_customer_identity(
                identifier_kind, identifier_value)
            if len(existing) != 1:
                return CustomerStorageUnavailable(
                    "registration collision reported but the existing "
                    "customer identity is not uniquely readable — "
                    "inconsistent store state")
            verified = self.read_customer_identity(
                existing[0].customer_identity_id)
            if not isinstance(verified, CustomerReadSuccess):
                return CustomerStorageUnavailable(
                    "existing customer identity failed verification")
            return CustomerIdentityReplay(verified.customer_identity)
        except CustomerLinkingPersistenceUnavailable as exc:
            return CustomerStorageUnavailable(str(exc))
        return CustomerIdentityRegistered(saved)

    # ------------------------------------------------------------------
    # The linking ladder — link (SPEC §4)
    # ------------------------------------------------------------------

    def link(self, invoice_id: str, declared_field_name: str,
             identifier_kind: str) -> object:
        """Link ONE declared customer reference on ONE issued Canonical
        Invoice to an EXISTING customer — deterministically, auditably, or
        not at all. Exactly one explicit outcome — never silent:
          CustomerLinked | CustomerLinkUnresolved | CustomerLinkReplay |
          CustomerLinkRequestRefused | CustomerLinkInputIntegrityFailure |
          CustomerLinkStorageUnavailable.
        The invoice content is the P6.2 verified read — consumed VERBATIM.
        """
        # -- L1: the ONLY invoice path — the P6.2 verified read ------------
        invoice_read = self._assembly.read_assembled_invoice(invoice_id)
        if isinstance(invoice_read, AssemblyReadRefused):
            return CustomerLinkInputIntegrityFailure(
                invoice_id, f"linked invoice read refused: "
                            f"{invoice_read.detail}")
        if isinstance(invoice_read, AssemblyReadIntegrityFailure):
            return CustomerLinkInputIntegrityFailure(
                invoice_id,
                f"linked invoice failed verification: {invoice_read.reason}")
        if isinstance(invoice_read, AssemblyReadVerificationUnavailable):
            self._issues.append(f"link {invoice_id}: "
                                f"{invoice_read.issue_report}")
            return CustomerLinkInputIntegrityFailure(
                invoice_id, invoice_read.issue_report
                + " — Issue Report required")
        if not isinstance(invoice_read, AssemblyReadSuccess):
            # Unreachable by construction (the P6.2 read ladder is
            # exhaustive) — kept fail-closed against contract drift.
            return CustomerLinkInputIntegrityFailure(
                invoice_id,
                f"unmapped assembly read outcome "
                f"{type(invoice_read).__name__} — fail-closed")

        # -- L2: declaration validation ------------------------------------
        if not declared_field_name or not identifier_kind:
            return CustomerLinkRequestRefused(
                invoice_id,
                f"{REFUSE_DECLARATION_MALFORMED}: declared_field_name and "
                "identifier_kind must be non-empty")

        # -- L3: declared-reference resolution (exactly-one rule) ----------
        field_entry = self._resolve_declared_field(
            invoice_read, declared_field_name)
        if isinstance(field_entry, CustomerLinkRequestRefused):
            return field_entry

        # -- L4: replay — the existing durable outcome wins ----------------
        existing = self._store.find_link_by_declaration(
            invoice_id, declared_field_name, identifier_kind)
        if existing is not None:
            verified = self.read_link_by_id(existing.link_id)
            if isinstance(verified, CustomerLinkReadIntegrityFailure):
                return CustomerLinkInputIntegrityFailure(
                    invoice_id,
                    f"existing link failed verification: {verified.reason}")
            if isinstance(verified, CustomerLinkReadVerificationUnavailable):
                self._issues.append(f"link {invoice_id}: "
                                    f"{verified.issue_report}")
                return CustomerLinkInputIntegrityFailure(
                    invoice_id, verified.issue_report
                    + " — Issue Report required")
            if isinstance(verified, CustomerLinkReadRefused):
                return CustomerLinkInputIntegrityFailure(
                    invoice_id,
                    f"existing link unreadable: {verified.detail}")
            return CustomerLinkReplay(
                verified.record, verified.invoice_read,
                verified.customer_identity, utc_now_iso())

        # -- L5: the exact customer lookup (count-based, OD-CL5) -----------
        # The identifier value is read LIVE from the verified P6.2 canonical
        # field entry — never stored in this layer (OD-CL6).
        candidates = self._store.find_customer_identity(
            identifier_kind, field_entry.canonical_value)
        if len(candidates) > 1:
            # Structurally prevented by the register's UNIQUE discipline —
            # if ever observed it is store corruption, never a link
            # decision (OD-CL5).
            return CustomerLinkInputIntegrityFailure(
                invoice_id,
                "customer lookup ambiguous: a definitive identifier mapped "
                f"to {len(candidates)} customer identities — store "
                "corruption suspected, no link decision made")

        customer_identity = None
        if len(candidates) == 1:
            verified = self.read_customer_identity(
                candidates[0].customer_identity_id)
            if not isinstance(verified, CustomerReadSuccess):
                return CustomerLinkInputIntegrityFailure(
                    invoice_id,
                    "matched customer identity failed verification")
            customer_identity = verified.customer_identity
            outcome, customer_ref, reason = (
                LINK_OUTCOME_LINKED,
                customer_identity.customer_identity_id, "")
        else:
            outcome, customer_ref, reason = (
                LINK_OUTCOME_UNRESOLVED, "",
                UNRESOLVED_NO_CUSTOMER_IDENTITY)

        # -- L6: atomic commit (INV-CL-1:1) ---------------------------------
        record = CustomerLinkRecord(
            link_id=uuid.uuid4().hex,
            invoice_id=invoice_read.invoice.invoice_id,
            capture_s1=invoice_read.invoice.capture_s1,
            capture_s1_algorithm_id=invoice_read.invoice
            .capture_s1_algorithm_id,
            declared_field_name=declared_field_name,
            canonical_seq=field_entry.canonical_seq,
            provenance=field_entry.provenance,
            identifier_kind=identifier_kind,
            link_outcome=outcome,
            customer_identity_id=customer_ref,
            unresolved_reason=reason,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="")
        try:
            saved = self._store.commit_link(record)
        except LinkDuplicate:
            # A concurrent call won the INV-CL-1:1 race — this call is,
            # factually, the replay (read-only; never a second fact).
            winner = self._store.find_link_by_declaration(
                invoice_id, declared_field_name, identifier_kind)
            if winner is None:
                return CustomerLinkStorageUnavailable(
                    "commit collision reported but no link found — "
                    "inconsistent store state")
            verified = self.read_link_by_id(winner.link_id)
            if not isinstance(verified, CustomerLinkReadSuccess):
                return CustomerLinkInputIntegrityFailure(
                    invoice_id,
                    "concurrent link outcome failed verification")
            return CustomerLinkReplay(
                verified.record, verified.invoice_read,
                verified.customer_identity, utc_now_iso())
        except CustomerLinkingPersistenceUnavailable as exc:
            return CustomerLinkStorageUnavailable(str(exc))

        if outcome == LINK_OUTCOME_LINKED:
            return CustomerLinked(saved, invoice_read, customer_identity)
        return CustomerLinkUnresolved(saved, invoice_read, reason)

    # ------------------------------------------------------------------
    # Declared-reference resolution helper (L3 — exactly-one rule, OD-CL6)
    # ------------------------------------------------------------------

    def _resolve_declared_field(self, invoice_read, declared_field_name: str):
        """Resolve the declared field name against the verified canonical
        field inventory: EXACTLY ONE entry with that name — 0 → refused
        (declared-field-not-found), ≥2 → refused (declared-field-ambiguous);
        picking one would be auto-resolution (forbidden — OD-CL6)."""
        hits = [f for f in invoice_read.fields
                if f.field_name == declared_field_name]
        if len(hits) == 0:
            return CustomerLinkRequestRefused(
                invoice_read.invoice.invoice_id,
                f"{REFUSE_FIELD_NOT_FOUND}: no canonical field named "
                f"{declared_field_name!r} in the verified read")
        if len(hits) > 1:
            return CustomerLinkRequestRefused(
                invoice_read.invoice.invoice_id,
                f"{REFUSE_FIELD_AMBIGUOUS}: {len(hits)} canonical fields "
                f"named {declared_field_name!r} — assembling would require "
                "picking a candidate, which is auto-resolution (forbidden)")
        return hits[0]

    # ------------------------------------------------------------------
    # Verified reads (VOR + linked re-verification — SPEC §6)
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

    def read_link_by_id(self, link_id: str) -> object:
        """Verified link read (SPEC §6): own-row VOR → linked P6.2 invoice
        re-verification + pointer re-join → linked customer identity
        re-verification + the LIVE byte-identity re-proof (iff LINKED) →
        cross-store structural gates."""
        try:
            record = self._store.get_link(link_id)
        except LinkNotFound:
            return CustomerLinkReadRefused(None, "no such customer link")
        return self._verified_link_read(record)

    def read_customer_identity(self, customer_identity_id: str) -> object:
        """Verified customer identity read (own VOR)."""
        try:
            record = self._store.get_customer_identity(customer_identity_id)
        except CustomerIdentityNotFound:
            return CustomerReadRefused(None, "no such customer identity")
        problem = self._verify(
            canonical_customer_identity_bytes(record),
            record.record_fingerprint, record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return CustomerReadIntegrityFailure(
                    record.customer_identity_id, problem, utc_now_iso())
            self._issues.append(f"customer identity "
                                f"{record.customer_identity_id}: {problem}")
            return CustomerReadVerificationUnavailable(
                record.customer_identity_id,
                problem + " — Issue Report required")
        return CustomerReadSuccess(record, utc_now_iso())

    def _invoice_fact(self, record: CustomerLinkRecord):
        """Re-verify the LINKED invoice through the P6.2 verified read and
        re-join the declared pointer (never blind pointers). Returns
        (invoice_read, field_entry, None) or (None, None, failure-outcome).
        """
        invoice_read = self._assembly.read_assembled_invoice(
            record.invoice_id)
        if isinstance(invoice_read, AssemblyReadIntegrityFailure):
            return None, None, CustomerLinkReadIntegrityFailure(
                record.link_id,
                f"linked invoice {invoice_read.reason}", utc_now_iso())
        if isinstance(invoice_read, AssemblyReadVerificationUnavailable):
            self._issues.append(f"customer link {record.link_id}: "
                                f"{invoice_read.issue_report}")
            return None, None, CustomerLinkReadVerificationUnavailable(
                record.link_id,
                invoice_read.issue_report + " — Issue Report required")
        if isinstance(invoice_read, AssemblyReadRefused):
            return None, None, CustomerLinkReadIntegrityFailure(
                record.link_id,
                f"linked invoice unreadable: {invoice_read.detail}",
                utc_now_iso())
        if not isinstance(invoice_read, AssemblyReadSuccess):
            return None, None, CustomerLinkReadIntegrityFailure(
                record.link_id,
                f"unmapped assembly read outcome "
                f"{type(invoice_read).__name__}", utc_now_iso())
        # pointer re-join: the stored pointer must still hit EXACTLY the
        # declared field inside the verified inventory (fail-closed)
        if record.canonical_seq < 0 \
                or record.canonical_seq >= len(invoice_read.fields):
            return None, None, CustomerLinkReadVerificationUnavailable(
                record.link_id,
                "pointer re-join failed: canonical_seq out of range — "
                "Issue Report required")
        field_entry = invoice_read.fields[record.canonical_seq]
        if field_entry.field_name != record.declared_field_name \
                or field_entry.provenance != record.provenance:
            return None, None, CustomerLinkReadVerificationUnavailable(
                record.link_id,
                "pointer re-join failed: the stored reference pointer does "
                "not re-join the declared field — Issue Report required")
        return invoice_read, field_entry, None

    def _customer_fact(self, record: CustomerLinkRecord):
        """Re-verify the LINKED customer identity (iff LINKED) through its
        own verified read (never blind pointers). Returns
        (customer_identity_or_None, None) or (None, failure-outcome)."""
        verified = self.read_customer_identity(record.customer_identity_id)
        if isinstance(verified, CustomerReadIntegrityFailure):
            return None, CustomerLinkReadIntegrityFailure(
                record.link_id,
                f"linked customer identity {verified.reason}",
                utc_now_iso())
        if isinstance(verified, CustomerReadVerificationUnavailable):
            self._issues.append(f"customer link {record.link_id}: "
                                f"{verified.issue_report}")
            return None, CustomerLinkReadVerificationUnavailable(
                record.link_id,
                verified.issue_report + " — Issue Report required")
        if isinstance(verified, CustomerReadRefused):
            return None, CustomerLinkReadIntegrityFailure(
                record.link_id,
                f"linked customer identity unreadable: {verified.detail}",
                utc_now_iso())
        return verified.customer_identity, None

    def _verified_link_read(self, record: CustomerLinkRecord) -> object:
        # 1. own-row VOR (tampered rows withhold content — never served)
        problem = self._verify(canonical_link_bytes(record),
                               record.record_fingerprint,
                               record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return CustomerLinkReadIntegrityFailure(
                    record.link_id, problem, utc_now_iso())
            self._issues.append(
                f"customer link {record.link_id}: {problem}")
            return CustomerLinkReadVerificationUnavailable(
                record.link_id, problem + " — Issue Report required")

        # 2. shape gate (fail-closed — a half-written row cannot pass)
        if record.link_outcome == LINK_OUTCOME_LINKED:
            if not record.customer_identity_id or record.unresolved_reason:
                return CustomerLinkReadVerificationUnavailable(
                    record.link_id,
                    "outcome shape inconsistent: LINKED without a customer "
                    "reference — Issue Report required")
        else:
            if record.customer_identity_id \
                    or record.unresolved_reason \
                    != UNRESOLVED_NO_CUSTOMER_IDENTITY:
                return CustomerLinkReadVerificationUnavailable(
                    record.link_id,
                    "outcome shape inconsistent: UNRESOLVED shape invalid — "
                    "Issue Report required")

        # 3. the linked invoice MUST verify through P6.2 + pointer re-join
        invoice_read, field_entry, failure = self._invoice_fact(record)
        if failure is not None:
            return failure

        # 4. anchor cross-check (the copied anchors must agree — a forged
        #    or half-written row cannot satisfy them)
        if record.invoice_id != invoice_read.invoice.invoice_id \
                or record.capture_s1 != invoice_read.invoice.capture_s1 \
                or record.capture_s1_algorithm_id \
                != invoice_read.invoice.capture_s1_algorithm_id:
            self._issues.append(
                f"customer link {record.link_id}: anchor drift")
            return CustomerLinkReadVerificationUnavailable(
                record.link_id,
                "durable link set inconsistent: invoice anchor drift — "
                "Issue Report required")

        # 5. LINKED re-proves the link LIVE (OD-CL4/§6): the linked customer
        #    identity verifies AND its registered identifier is the
        #    byte-identical value of the invoice's re-joined field.
        customer_identity = None
        if record.link_outcome == LINK_OUTCOME_LINKED:
            customer_identity, failure = self._customer_fact(record)
            if failure is not None:
                return failure
            if customer_identity.identifier_kind != record.identifier_kind:
                return CustomerLinkReadIntegrityFailure(
                    record.link_id,
                    "durable link set inconsistent: identifier_kind drift",
                    utc_now_iso())
            if customer_identity.identifier_value \
                    != field_entry.canonical_value:
                return CustomerLinkReadIntegrityFailure(
                    record.link_id,
                    "durable link set inconsistent: the registered "
                    "identifier value does not byte-match the invoice's "
                    "canonical value",
                    utc_now_iso())

        return CustomerLinkReadSuccess(record, invoice_read,
                                       customer_identity, utc_now_iso())

    # ------------------------------------------------------------------
    # Register queries (listing discipline — §6)
    # ------------------------------------------------------------------

    def links_of(self, invoice_id: str) -> List[CustomerLinkRecord]:
        """The durable link register for one invoice: every committed link
        row anchored to it (raw records; verify through read_link_by_id)."""
        return self._store.find_links_by_invoice(invoice_id)

    def links(self) -> List[CustomerLinkRecord]:
        """All committed link rows (raw records, listing discipline)."""
        return self._store.list_links()

    def customers(self) -> List[CustomerIdentityRecord]:
        """The full customer register (raw records, listing discipline)."""
        return self._store.list_customers()

    @property
    def issue_reports(self) -> list:
        return list(self._issues)
