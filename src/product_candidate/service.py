"""Product Exact Match service — WP-8.1 MVP implementation.

Binding basis: SPEC-WP81-PMATCH §2/§3/§4/§5/§6. The entry point and
orchestration layer: every `match` call consumes the WP-6.2 verified read
(`CanonicalAssemblyService.read_assembled_invoice`) VERBATIM — never
bypassed, never re-implemented, never triggered for upstream execution —
and maps the outcome deterministically onto the matching ladder M1–M6:

  M1  P6.2 read refused / integrity failure / verification unavailable →
      fail-closed passthrough, zero durable residue (details verbatim)
  M2  malformed declaration → refused (zero residue)
  M3  declared field not found / ambiguous → refused (never auto-resolution)
  M4  replay (existing durable outcome for the declaration) → verified
      verbatim return, ZERO new rows — replay never re-decides (OD-PM4)
  M5  exact catalog lookup: 1 → EXACT_MATCHED; 0 → UNRESOLVED
      (no-catalog-identity); ≥2 → fail-closed integrity failure (OD-PM5)
  M6  atomic commit; collision on the UNIQUE declaration key → re-read the
      winner and return the replay outcome (read-only)

Verified reads (§6): own-row VOR + re-verification of the linked invoice
through the P6.2 verified read + pointer re-join + catalog identity
re-verification + the LIVE byte-identity re-proof. A tampered or drifting
row at ANY level withholds content — this layer never serves an unverified
fact.

NO matching intelligence exists here beyond the frozen exact rule (D-05):
no fuzzy, no semantic, no AI, no confidence, no candidate generation, no
approval (OD-PM7). Ambiguity remains ambiguity.
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
    MATCH_OUTCOME_EXACT_MATCHED,
    MATCH_OUTCOME_UNRESOLVED,
    NOTE_VERIFY_FAILED,
    REFUSE_DECLARATION_MALFORMED,
    REFUSE_FIELD_AMBIGUOUS,
    REFUSE_FIELD_NOT_FOUND,
    UNRESOLVED_NO_CATALOG_IDENTITY,
    CatalogIdentityDuplicate,
    CatalogIdentityNotFound,
    CatalogIdentityRecord,
    CatalogReadIntegrityFailure,
    CatalogReadRefused,
    CatalogReadSuccess,
    CatalogReadVerificationUnavailable,
    CatalogRegistrationRefused,
    CatalogStorageUnavailable,
    CatalogIdentityRegistered,
    CatalogIdentityReplay,
    MatchDuplicate,
    MatchNotFound,
    ProductCandidatePersistenceUnavailable,
    ProductExactMatched,
    ProductMatchInputIntegrityFailure,
    ProductMatchReadIntegrityFailure,
    ProductMatchReadRefused,
    ProductMatchReadSuccess,
    ProductMatchReadVerificationUnavailable,
    ProductMatchRecord,
    ProductMatchReplay,
    ProductMatchRequestRefused,
    ProductMatchStorageUnavailable,
    ProductReferenceUnresolved,
    utc_now_iso,
)
from .store import (
    ProductCandidateStore,
    canonical_catalog_identity_bytes,
    canonical_match_bytes,
)


class ProductCandidateService:
    """The WP-8.1 entry point: issued Canonical Invoices (P6.2) + the
    explicit catalog register → deterministic, auditable exact-match facts
    (D-05 Exact Match — and nothing else)."""

    def __init__(self, store: ProductCandidateStore,
                 assembly: CanonicalAssemblyService,
                 s1: S1Service) -> None:
        self._store = store
        self._assembly = assembly
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Catalog registration (SPEC §3 — explicit, idempotent, OD-PM2)
    # ------------------------------------------------------------------

    def register_catalog_identity(self, identifier_kind: str,
                                  identifier_value: str) -> object:
        """Register ONE catalog identity (explicit declared registration
        ONLY — the API carries no capture/invoice parameter, so no
        capture-derived catalog mutation is possible, OD-PM2). Exactly one
        explicit outcome — never silent:
          CatalogIdentityRegistered | CatalogIdentityReplay |
          CatalogRegistrationRefused | CatalogStorageUnavailable.
        """
        if not identifier_kind or not identifier_value:
            return CatalogRegistrationRefused(
                "catalog registration refused: identifier_kind and "
                "identifier_value must be non-empty (declared verbatim, "
                "no defaults — OD-PM3)")
        record = CatalogIdentityRecord(
            catalog_identity_id=uuid.uuid4().hex,
            identifier_kind=identifier_kind,
            identifier_value=identifier_value,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="")
        try:
            saved = self._store.commit_catalog_identity(record)
        except CatalogIdentityDuplicate:
            existing = self._store.find_catalog_identity(
                identifier_kind, identifier_value)
            if len(existing) != 1:
                return CatalogStorageUnavailable(
                    "registration collision reported but the existing "
                    "catalog identity is not uniquely readable — "
                    "inconsistent store state")
            verified = self.read_catalog_identity(
                existing[0].catalog_identity_id)
            if not isinstance(verified, CatalogReadSuccess):
                return CatalogStorageUnavailable(
                    "existing catalog identity failed verification")
            return CatalogIdentityReplay(verified.catalog_identity)
        except ProductCandidatePersistenceUnavailable as exc:
            return CatalogStorageUnavailable(str(exc))
        return CatalogIdentityRegistered(saved)

    # ------------------------------------------------------------------
    # The matching ladder — match (SPEC §4)
    # ------------------------------------------------------------------

    def match(self, invoice_id: str, declared_field_name: str,
              identifier_kind: str) -> object:
        """Match ONE declared product reference on ONE issued Canonical
        Invoice. Exactly one explicit outcome — never silent:
          ProductExactMatched | ProductReferenceUnresolved |
          ProductMatchReplay | ProductMatchRequestRefused |
          ProductMatchInputIntegrityFailure | ProductMatchStorageUnavailable.
        The invoice content is the P6.2 verified read — consumed VERBATIM.
        """
        # -- M1: the ONLY invoice path — the P6.2 verified read ------------
        invoice_read = self._assembly.read_assembled_invoice(invoice_id)
        if isinstance(invoice_read, AssemblyReadRefused):
            return ProductMatchInputIntegrityFailure(
                invoice_id, f"linked invoice read refused: "
                            f"{invoice_read.detail}")
        if isinstance(invoice_read, AssemblyReadIntegrityFailure):
            return ProductMatchInputIntegrityFailure(
                invoice_id,
                f"linked invoice failed verification: {invoice_read.reason}")
        if isinstance(invoice_read, AssemblyReadVerificationUnavailable):
            self._issues.append(f"match {invoice_id}: "
                                f"{invoice_read.issue_report}")
            return ProductMatchInputIntegrityFailure(
                invoice_id, invoice_read.issue_report
                + " — Issue Report required")
        if not isinstance(invoice_read, AssemblyReadSuccess):
            # Unreachable by construction (the P6.2 read ladder is
            # exhaustive) — kept fail-closed against contract drift.
            return ProductMatchInputIntegrityFailure(
                invoice_id,
                f"unmapped assembly read outcome "
                f"{type(invoice_read).__name__} — fail-closed")

        # -- M2: declaration validation ------------------------------------
        if not declared_field_name or not identifier_kind:
            return ProductMatchRequestRefused(
                invoice_id,
                f"{REFUSE_DECLARATION_MALFORMED}: declared_field_name and "
                "identifier_kind must be non-empty")

        # -- M3: declared-reference resolution (exactly-one rule) ----------
        field_entry = self._resolve_declared_field(
            invoice_read, declared_field_name)
        if isinstance(field_entry, ProductMatchRequestRefused):
            return field_entry

        # -- M4: replay — the existing durable outcome wins ----------------
        existing = self._store.find_match_by_declaration(
            invoice_id, declared_field_name, identifier_kind)
        if existing is not None:
            verified = self.read_match_by_id(existing.match_id)
            if isinstance(verified, ProductMatchReadIntegrityFailure):
                return ProductMatchInputIntegrityFailure(
                    invoice_id,
                    f"existing match failed verification: {verified.reason}")
            if isinstance(verified, ProductMatchReadVerificationUnavailable):
                self._issues.append(f"match {invoice_id}: "
                                    f"{verified.issue_report}")
                return ProductMatchInputIntegrityFailure(
                    invoice_id, verified.issue_report
                    + " — Issue Report required")
            if isinstance(verified, ProductMatchReadRefused):
                return ProductMatchInputIntegrityFailure(
                    invoice_id,
                    f"existing match unreadable: {verified.detail}")
            return ProductMatchReplay(
                verified.record, verified.invoice_read,
                verified.catalog_identity, utc_now_iso())

        # -- M5: the exact catalog lookup (count-based, OD-PM5) ------------
        # The identifier value is read LIVE from the verified P6.2 canonical
        # field entry — never stored in this layer (OD-PM6).
        candidates = self._store.find_catalog_identity(
            identifier_kind, field_entry.canonical_value)
        if len(candidates) > 1:
            # Structurally prevented by the register's UNIQUE discipline —
            # if ever observed it is store corruption, never a match
            # decision (OD-PM5).
            return ProductMatchInputIntegrityFailure(
                invoice_id,
                "catalog lookup ambiguous: a definitive identifier mapped "
                f"to {len(candidates)} catalog identities — store "
                "corruption suspected, no match decision made")

        catalog_identity = None
        if len(candidates) == 1:
            verified = self.read_catalog_identity(
                candidates[0].catalog_identity_id)
            if not isinstance(verified, CatalogReadSuccess):
                return ProductMatchInputIntegrityFailure(
                    invoice_id,
                    "matched catalog identity failed verification")
            catalog_identity = verified.catalog_identity
            outcome, catalog_ref, reason = (
                MATCH_OUTCOME_EXACT_MATCHED,
                catalog_identity.catalog_identity_id, "")
        else:
            outcome, catalog_ref, reason = (
                MATCH_OUTCOME_UNRESOLVED, "",
                UNRESOLVED_NO_CATALOG_IDENTITY)

        # -- M6: atomic commit (INV-PM-1:1) ---------------------------------
        record = ProductMatchRecord(
            match_id=uuid.uuid4().hex,
            invoice_id=invoice_read.invoice.invoice_id,
            capture_s1=invoice_read.invoice.capture_s1,
            capture_s1_algorithm_id=invoice_read.invoice
            .capture_s1_algorithm_id,
            declared_field_name=declared_field_name,
            canonical_seq=field_entry.canonical_seq,
            provenance=field_entry.provenance,
            identifier_kind=identifier_kind,
            match_outcome=outcome,
            catalog_identity_id=catalog_ref,
            unresolved_reason=reason,
            created_at=utc_now_iso(),
            record_fingerprint="",
            fingerprint_algorithm_id="")
        try:
            saved = self._store.commit_match(record)
        except MatchDuplicate:
            # A concurrent call won the INV-PM-1:1 race — this call is,
            # factually, the replay (read-only; never a second fact).
            winner = self._store.find_match_by_declaration(
                invoice_id, declared_field_name, identifier_kind)
            if winner is None:
                return ProductMatchStorageUnavailable(
                    "commit collision reported but no match found — "
                    "inconsistent store state")
            verified = self.read_match_by_id(winner.match_id)
            if not isinstance(verified, ProductMatchReadSuccess):
                return ProductMatchInputIntegrityFailure(
                    invoice_id,
                    "concurrent match outcome failed verification")
            return ProductMatchReplay(
                verified.record, verified.invoice_read,
                verified.catalog_identity, utc_now_iso())
        except ProductCandidatePersistenceUnavailable as exc:
            return ProductMatchStorageUnavailable(str(exc))

        if outcome == MATCH_OUTCOME_EXACT_MATCHED:
            return ProductExactMatched(saved, invoice_read, catalog_identity)
        return ProductReferenceUnresolved(saved, invoice_read, reason)

    # ------------------------------------------------------------------
    # Declared-reference resolution helper (M3 — exactly-one rule, OD-PM6)
    # ------------------------------------------------------------------

    def _resolve_declared_field(self, invoice_read, declared_field_name: str):
        """Resolve the declared field name against the verified canonical
        field inventory: EXACTLY ONE entry with that name — 0 → refused
        (declared-field-not-found), ≥2 → refused (declared-field-ambiguous);
        picking one would be auto-resolution (forbidden — OD-PM6)."""
        hits = [f for f in invoice_read.fields
                if f.field_name == declared_field_name]
        if len(hits) == 0:
            return ProductMatchRequestRefused(
                invoice_read.invoice.invoice_id,
                f"{REFUSE_FIELD_NOT_FOUND}: no canonical field named "
                f"{declared_field_name!r} in the verified read")
        if len(hits) > 1:
            return ProductMatchRequestRefused(
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

    def read_match_by_id(self, match_id: str) -> object:
        """Verified match read (SPEC §6): own-row VOR → linked P6.2 invoice
        re-verification + pointer re-join → linked catalog identity
        re-verification + the LIVE byte-identity re-proof (iff
        EXACT_MATCHED) → cross-store structural gates."""
        try:
            record = self._store.get_match(match_id)
        except MatchNotFound:
            return ProductMatchReadRefused(None, "no such product match")
        return self._verified_match_read(record)

    def read_catalog_identity(self, catalog_identity_id: str) -> object:
        """Verified catalog identity read (own VOR)."""
        try:
            record = self._store.get_catalog_identity(catalog_identity_id)
        except CatalogIdentityNotFound:
            return CatalogReadRefused(None, "no such catalog identity")
        problem = self._verify(
            canonical_catalog_identity_bytes(record),
            record.record_fingerprint, record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return CatalogReadIntegrityFailure(
                    record.catalog_identity_id, problem, utc_now_iso())
            self._issues.append(f"catalog identity "
                                f"{record.catalog_identity_id}: {problem}")
            return CatalogReadVerificationUnavailable(
                record.catalog_identity_id,
                problem + " — Issue Report required")
        return CatalogReadSuccess(record, utc_now_iso())

    def _invoice_fact(self, record: ProductMatchRecord):
        """Re-verify the LINKED invoice through the P6.2 verified read and
        re-join the declared pointer (never blind pointers). Returns
        (invoice_read, field_entry, None) or (None, None, failure-outcome).
        """
        invoice_read = self._assembly.read_assembled_invoice(
            record.invoice_id)
        if isinstance(invoice_read, AssemblyReadIntegrityFailure):
            return None, None, ProductMatchReadIntegrityFailure(
                record.match_id,
                f"linked invoice {invoice_read.reason}", utc_now_iso())
        if isinstance(invoice_read, AssemblyReadVerificationUnavailable):
            self._issues.append(f"product match {record.match_id}: "
                                f"{invoice_read.issue_report}")
            return None, None, ProductMatchReadVerificationUnavailable(
                record.match_id,
                invoice_read.issue_report + " — Issue Report required")
        if isinstance(invoice_read, AssemblyReadRefused):
            return None, None, ProductMatchReadIntegrityFailure(
                record.match_id,
                f"linked invoice unreadable: {invoice_read.detail}",
                utc_now_iso())
        if not isinstance(invoice_read, AssemblyReadSuccess):
            return None, None, ProductMatchReadIntegrityFailure(
                record.match_id,
                f"unmapped assembly read outcome "
                f"{type(invoice_read).__name__}", utc_now_iso())
        # pointer re-join: the stored pointer must still hit EXACTLY the
        # declared field inside the verified inventory (fail-closed)
        if record.canonical_seq < 0 \
                or record.canonical_seq >= len(invoice_read.fields):
            return None, None, ProductMatchReadVerificationUnavailable(
                record.match_id,
                "pointer re-join failed: canonical_seq out of range — "
                "Issue Report required")
        field_entry = invoice_read.fields[record.canonical_seq]
        if field_entry.field_name != record.declared_field_name \
                or field_entry.provenance != record.provenance:
            return None, None, ProductMatchReadVerificationUnavailable(
                record.match_id,
                "pointer re-join failed: the stored reference pointer does "
                "not re-join the declared field — Issue Report required")
        return invoice_read, field_entry, None

    def _catalog_fact(self, record: ProductMatchRecord):
        """Re-verify the LINKED catalog identity (iff EXACT_MATCHED) through
        its own verified read (never blind pointers). Returns
        (catalog_identity_or_None, None) or (None, failure-outcome)."""
        verified = self.read_catalog_identity(record.catalog_identity_id)
        if isinstance(verified, CatalogReadIntegrityFailure):
            return None, ProductMatchReadIntegrityFailure(
                record.match_id,
                f"linked catalog identity {verified.reason}",
                utc_now_iso())
        if isinstance(verified, CatalogReadVerificationUnavailable):
            self._issues.append(f"product match {record.match_id}: "
                                f"{verified.issue_report}")
            return None, ProductMatchReadVerificationUnavailable(
                record.match_id,
                verified.issue_report + " — Issue Report required")
        if isinstance(verified, CatalogReadRefused):
            return None, ProductMatchReadIntegrityFailure(
                record.match_id,
                f"linked catalog identity unreadable: {verified.detail}",
                utc_now_iso())
        return verified.catalog_identity, None

    def _verified_match_read(self, record: ProductMatchRecord) -> object:
        # 1. own-row VOR (tampered rows withhold content — never served)
        problem = self._verify(canonical_match_bytes(record),
                               record.record_fingerprint,
                               record.fingerprint_algorithm_id)
        if problem is not None:
            if problem == NOTE_VERIFY_FAILED:
                return ProductMatchReadIntegrityFailure(
                    record.match_id, problem, utc_now_iso())
            self._issues.append(
                f"product match {record.match_id}: {problem}")
            return ProductMatchReadVerificationUnavailable(
                record.match_id, problem + " — Issue Report required")

        # 2. shape gate (fail-closed — a half-written row cannot pass)
        if record.match_outcome == MATCH_OUTCOME_EXACT_MATCHED:
            if not record.catalog_identity_id or record.unresolved_reason:
                return ProductMatchReadVerificationUnavailable(
                    record.match_id,
                    "outcome shape inconsistent: EXACT_MATCHED without a "
                    "catalog reference — Issue Report required")
        else:
            if record.catalog_identity_id \
                    or record.unresolved_reason \
                    != UNRESOLVED_NO_CATALOG_IDENTITY:
                return ProductMatchReadVerificationUnavailable(
                    record.match_id,
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
                f"product match {record.match_id}: anchor drift")
            return ProductMatchReadVerificationUnavailable(
                record.match_id,
                "durable match set inconsistent: invoice anchor drift — "
                "Issue Report required")

        # 5. EXACT_MATCHED re-proves the match LIVE (OD-PM4/§6): the linked
        #    catalog identity verifies AND its registered identifier is the
        #    byte-identical value of the invoice's re-joined field.
        catalog_identity = None
        if record.match_outcome == MATCH_OUTCOME_EXACT_MATCHED:
            catalog_identity, failure = self._catalog_fact(record)
            if failure is not None:
                return failure
            if catalog_identity.identifier_kind != record.identifier_kind:
                return ProductMatchReadIntegrityFailure(
                    record.match_id,
                    "durable match set inconsistent: identifier_kind drift",
                    utc_now_iso())
            if catalog_identity.identifier_value \
                    != field_entry.canonical_value:
                return ProductMatchReadIntegrityFailure(
                    record.match_id,
                    "durable match set inconsistent: the registered "
                    "identifier value does not byte-match the invoice's "
                    "canonical value",
                    utc_now_iso())

        return ProductMatchReadSuccess(record, invoice_read,
                                       catalog_identity, utc_now_iso())

    # ------------------------------------------------------------------
    # Register queries (listing discipline — §6)
    # ------------------------------------------------------------------

    def matches_of(self, invoice_id: str) -> List[ProductMatchRecord]:
        """The durable match register for one invoice: every committed match
        row anchored to it (raw records; verify through read_match_by_id)."""
        return self._store.find_matches_by_invoice(invoice_id)

    def matches(self) -> List[ProductMatchRecord]:
        """All committed match rows (raw records, listing discipline)."""
        return self._store.list_matches()

    def catalog(self) -> List[CatalogIdentityRecord]:
        """The full catalog register (raw records, listing discipline)."""
        return self._store.list_catalog()

    @property
    def issue_reports(self) -> list:
        return list(self._issues)
