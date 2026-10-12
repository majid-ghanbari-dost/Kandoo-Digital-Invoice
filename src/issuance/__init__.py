"""Kandoo Digital Issuance — additive application composition of the frozen
external flow (Continuation of Issue #4; PR #9 delivered the canonical half).

The frozen AS-01 sequence is

    External POS/Holoo → Capture → Reconstruction → Extraction → Normalization
    → Canonicalization Gate → Validation → Invoice → Digital Invoice

Two production compositions already exist and are consumed here VERBATIM:

| Component | Provides |
|---|---|
| `pipeline` (Issue #4 / PR #9) | capture → … → gate → canonical assembly, verified read + whole-chain trace |
| `digital_invoice` (WP-10.1) | the Digital Invoice lifecycle over an issued Canonical Invoice |

What was missing — and what this package adds — is a single durable, owned,
restart-safe entry point that carries ONE application-owned directory through
BOTH halves, so an ISSUED Digital Invoice is reachable from raw ordered pages
without hand-wiring eleven stores, and so the lifecycle layer structurally
reads the same P6.2 store the pipeline wrote.

Boundaries (normative, unchanged):
- NOTHING is automatic: no automatic open, issuance, revocation or
  supersession, no time- or content-driven transition, no scheduler.
- NO new lifecycle state/act/transition (AS-03 vocabulary transferred
  verbatim), NO new identifier or dedup rule (D-02/D-03), NO canonical content
  stored by this layer (pointer discipline).
- NO receipt/presentation/delivery surface (WP-10.2 / DEF5), NO customer or
  product semantics (D-06/DEF3/WP-8.1/WP-9.1), NO inventory effect (AD-03),
  NO Sale (DEF1), NO adapter/source mapping (DEF6/WP-11.2), NO retention or
  purge surface (DEF4 — physical purge stays blocked), NO access-matrix
  surface (DEF2), NO threshold value (WP-12.3), NO CLI product scope (D-09 —
  still referred to PO/TM).
"""
from .model import DigitalInvoiceStatus, IssuanceSubmission
from .service import IssuanceService
from .workspace import DIGITAL_INVOICE_DB, DigitalIssuanceWorkspace

__all__ = [
    "DigitalIssuanceWorkspace",
    "IssuanceService",
    "IssuanceSubmission",
    "DigitalInvoiceStatus",
    "DIGITAL_INVOICE_DB",
]
