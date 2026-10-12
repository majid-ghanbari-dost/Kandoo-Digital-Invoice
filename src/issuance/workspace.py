"""Owned durable workspace for the complete frozen external flow (AS-01).

ONE application-owned directory owns the eleven existing pipeline stores PLUS
the WP-10.1 Digital Invoice store. Nothing is re-implemented: the pipeline
composition and the Digital Invoice lifecycle service are consumed verbatim,
over the SAME durable stores they already own.

Boundary (normative): this layer adds NO lifecycle state, act, transition,
policy value, identifier, dedup rule, receipt/presentation surface, customer or
product semantics, inventory effect, scheduler or automatic behavior. In
particular it never opens, advances, revokes or supersedes anything by itself:
every Digital Invoice movement requires an explicit caller act.
"""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

from capture import S1Service
from digital_invoice import DigitalInvoiceLifecycleService, DigitalInvoiceStore
from pipeline import PipelineWorkspace

from .service import IssuanceService

# The twelfth store: WP-10.1's own durable file, verbatim layer name.
DIGITAL_INVOICE_DB = "digital-invoice.db"


class DigitalIssuanceWorkspace:
    """Use as a context manager. One synchronous caller per instance.

    `validation_rules` is MANDATORY and is passed through to the pipeline
    workspace verbatim — this layer declares no tolerance, precision, rounding
    mode or any other policy value. The directory must be application-owned.
    Existing stores are never deleted, reset or migrated. Opening an existing
    workspace is non-destructive; `close()` is idempotent.
    """
    def __init__(self, directory, *, validation_rules):
        self._resources = ExitStack()
        self._closed = False
        try:
            workspace = Path(directory)
            # Raises BEFORE creating any file when the declarations are absent,
            # empty or not usable (verbatim pipeline workspace behavior).
            self.pipeline_workspace = PipelineWorkspace(
                workspace, validation_rules=validation_rules)
            self._resources.callback(self.pipeline_workspace.close)
            s1 = S1Service()
            self.digital_invoice_store = DigitalInvoiceStore(
                workspace / DIGITAL_INVOICE_DB, s1)
            self._resources.callback(self.digital_invoice_store.close)
            # The lifecycle layer's ONLY invoice path is the SAME P6.2 service
            # this workspace's pipeline assembles into (consumed, never
            # bypassed): the provenance guarantee is structural, not promised.
            self.digital_invoice = DigitalInvoiceLifecycleService(
                self.digital_invoice_store, self.pipeline_workspace.assembly,
                s1)
            self.service = IssuanceService(self)
        except BaseException:
            self.close()
            raise

    def require_open(self):
        if self._closed:
            raise RuntimeError("issuance workspace is closed")

    def __enter__(self):
        self.require_open()
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if not self._closed:
            self._closed = True
            self._resources.close()
