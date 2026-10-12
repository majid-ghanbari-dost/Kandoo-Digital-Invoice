"""Product-path caller surface over ONE issued-Canonical-Invoice workspace.

Every method here is a VERBATIM delegation to an existing frozen service on the
workspace's own stores:
  * `submit`  → the composed pipeline service (`pipeline.service`, Issue #4);
  * the lifecycle acts and the verified read/trace → the WP-10.1 service.

This module adds NO act semantics, NO automatic behavior and NO new identity:
what it adds is the single supported entry point, so that the Digital Invoice
layer always sees the very P6.2 store the pipeline assembled into.
"""
from __future__ import annotations

from typing import Tuple

from digital_invoice.model import (
    DigitalInvoiceReadIntegrityFailure,
    DigitalInvoiceReadRefused,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceReadVerificationUnavailable,
)
from pipeline.model import PipelineCompleted

from .model import DigitalInvoiceStatus, IssuanceSubmission


class IssuanceService:
    """Caller API of the composed workspace. Nothing is automatic."""

    def __init__(self, workspace):
        self._workspace = workspace

    # -- submission: the frozen pipeline, verbatim -------------------------

    def submit(self, pages, *, source_label, declared_origin,
               identity_binding, line_binding, ruleset_id,
               ruleset_version) -> IssuanceSubmission:
        """Run the composed capture-to-canonical pipeline and return its
        outcome VERBATIM inside `IssuanceSubmission`.

        Declarations and pages have exactly the pipeline's semantics: invalid
        declarations/shapes raise `ValueError` before any ingest (zero
        residue); REVIEW/REJECT/duplicate outcomes are returned as the
        pipeline's own typed stop — never converted, retried or auto-resolved.
        This call performs NO Digital Invoice action of any kind.
        """
        workspace = self._workspace
        workspace.require_open()
        outcome = workspace.pipeline_workspace.pipeline.process(
            pages,
            source_label=source_label,
            declared_origin=declared_origin,
            identity_binding=identity_binding,
            line_binding=line_binding,
            ruleset_id=ruleset_id,
            ruleset_version=ruleset_version)
        if isinstance(outcome, PipelineCompleted):
            return IssuanceSubmission(
                outcome, outcome.invoice.invoice.invoice_id,
                outcome.capture_id)
        return IssuanceSubmission(outcome, None, outcome.capture_id)

    # -- explicit lifecycle acts: the frozen WP-10.1 acts, verbatim --------

    def open_digital_invoice(self, invoice_id: str) -> object:
        """Open ONE Digital Invoice for ONE issued Canonical Invoice (WP-10.1
        §4) — only through the P6.2 verified read + whole-chain trace. Returns
        the frozen outcome verbatim; replay is idempotent (zero new rows)."""
        self._workspace.require_open()
        return self._workspace.digital_invoice.open_digital_invoice(invoice_id)

    def mark_extracted(self, invoice_id: str, reason_note: str = "") -> object:
        """DRAFT → EXTRACTED (WP-10.1 act) — verbatim, explicit, fail-closed."""
        self._workspace.require_open()
        return self._workspace.digital_invoice.mark_extracted(
            invoice_id, reason_note)

    def mark_validated(self, invoice_id: str, reason_note: str = "") -> object:
        """EXTRACTED → VALIDATED (WP-10.1 act) — verbatim, explicit."""
        self._workspace.require_open()
        return self._workspace.digital_invoice.mark_validated(
            invoice_id, reason_note)

    def issue(self, invoice_id: str, reason_note: str = "") -> object:
        """VALIDATED → ISSUED (WP-10.1 operational issuance act) — verbatim.

        No identifier is minted here and nothing is scheduled or triggered:
        this is ONE explicit caller act on an already-validated Digital
        Invoice, re-verified against the LIVE P6.2 chain at act time.
        """
        self._workspace.require_open()
        return self._workspace.digital_invoice.issue(invoice_id, reason_note)

    def revoke(self, invoice_id: str, reason_note: str = "") -> object:
        """ISSUED → REVOKED, terminal (WP-10.1 act) — verbatim."""
        self._workspace.require_open()
        return self._workspace.digital_invoice.revoke(invoice_id, reason_note)

    def supersede(self, invoice_id: str, replacement_invoice_id: str,
                  reason_note: str = "") -> object:
        """ISSUED → SUPERSEDED, terminal (WP-10.1 act) — verbatim; the
        replacement is verified at act time by the frozen layer."""
        self._workspace.require_open()
        return self._workspace.digital_invoice.supersede(
            invoice_id, replacement_invoice_id, reason_note)

    # -- verified product reads -------------------------------------------

    def read(self, invoice_id: str) -> object:
        """The frozen WP-10.1 verified read, verbatim (own-row VOR + event
        chain + linked P6.2 re-verification)."""
        self._workspace.require_open()
        return self._workspace.digital_invoice.read_digital_invoice(invoice_id)

    def trace(self, invoice_id: str) -> object:
        """The frozen WP-10.1 whole-chain trace, verbatim: the lifecycle chain
        plus the full P6.2 provenance walk down to Capture S1."""
        self._workspace.require_open()
        return self._workspace.digital_invoice.trace_digital_invoice(invoice_id)

    def status(self, invoice_id: str) -> DigitalInvoiceStatus:
        """Compact projection of ONE verified read (`outcome` retained).

        `verified=True` means every link re-verified inside this call. Any
        withholding (tamper, drift, unavailable persistence) yields
        `verified=False` with the outcome's own reason in `detail` — the
        projection never softens or re-labels a frozen outcome, and an unknown
        outcome type raises `TypeError` rather than being guessed.
        """
        outcome = self.read(invoice_id)
        if isinstance(outcome, DigitalInvoiceReadSuccess):
            return DigitalInvoiceStatus(
                invoice_id, outcome, True, True,
                outcome.record.digital_invoice_id, outcome.current_state, "")
        if isinstance(outcome, DigitalInvoiceReadRefused):
            return DigitalInvoiceStatus(
                invoice_id, outcome, False, False, None, None, outcome.detail)
        if isinstance(outcome, DigitalInvoiceReadIntegrityFailure):
            return DigitalInvoiceStatus(
                invoice_id, outcome, True, False, outcome.digital_invoice_id,
                None, outcome.reason)
        if isinstance(outcome, DigitalInvoiceReadVerificationUnavailable):
            return DigitalInvoiceStatus(
                invoice_id, outcome, True, False, outcome.digital_invoice_id,
                None, outcome.issue_report)
        raise TypeError(
            "unknown WP-10.1 read outcome: "
            f"{type(outcome).__name__} — this composition refuses to guess")

    # -- discovery (read-only; existing listing surfaces) -----------------

    def issued_canonical_invoices(self) -> Tuple[object, ...]:
        """All durable Canonical Invoices of this workspace, in the canonical
        assembly listing order (raw listing, OD-A/K pattern)."""
        self._workspace.require_open()
        return tuple(self._workspace.pipeline_workspace.assembly
                     .issued_invoices())

    def opened_digital_invoices(self) -> Tuple[object, ...]:
        """All durable Digital Invoice rows of this workspace (raw listing)."""
        self._workspace.require_open()
        return tuple(self._workspace.digital_invoice.digital_invoices())

    def awaiting_digital_invoice(self) -> Tuple[str, ...]:
        """invoice_ids of issued Canonical Invoices that have NO Digital
        Invoice yet — the deterministic restart-resumption set.

        Read-only and derived from the existing listing surfaces: it decides
        nothing and advances nothing (an application resumes with its own
        explicit acts).
        """
        self._workspace.require_open()
        opened = {record.invoice_id for record
                  in self._workspace.digital_invoice.digital_invoices()}
        return tuple(record.invoice_id
                     for record in self.issued_canonical_invoices()
                     if record.invoice_id not in opened)
