"""Canonical Assembly + invoice_id Issuance domain model — WP-6.2 MVP.

Binding basis: SPEC-WP62-CANASM (all sections; OD-A1..A10 delegated details
declared in assembly.py / store.py / service.py).

Vocabulary discipline (AS-03/AS-04/AD-04/CL-1 — verbatim, no paraphrase, no
invention):
  - Origins are the frozen dispatch set VERBATIM (quoted from the P6.1
    admission records): KANDOO_SALE | HOLOO_CAPTURE | OTHER_POS_CAPTURE.
  - Provenance labels are D-01's vocabulary VERBATIM: EXTRACTED | DERIVED.
    UNRESOLVED is NEVER created here (D-01 — P5 territory).
  - Header anchor roles are the frozen D-02 identity roles VERBATIM:
    INVOICE_NUMBER | INVOICE_DATE | INVOICE_TOTAL.
  - Line field roles transliterate the dispatch §5 line content areas
    (quantities / unit prices / totals) as a DECLARED field-role vocabulary
    (OD-A4 — not a state vocabulary): LINE_QUANTITY | LINE_UNIT_PRICE |
    LINE_TOTAL.
  - invoice_id is the D-02 Canonical Identity, Kandoo-issued at the P6.1 Gate
    (OD-G8) — consumed VERBATIM here (OD-A1). No identifier is minted in this
    layer; no uuid/random exists anywhere in this package (AST-proven).

This module is dataclasses + vocabularies + exceptions + explicit outcome
types ONLY — no I/O, no persistence, no clock, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Frozen vocabularies (verbatim — see module docstring)
# ---------------------------------------------------------------------------

ORIGIN_KANDOO_SALE = "KANDOO_SALE"
ORIGIN_HOLOO_CAPTURE = "HOLOO_CAPTURE"
ORIGIN_OTHER_POS_CAPTURE = "OTHER_POS_CAPTURE"
ORIGINS = (ORIGIN_KANDOO_SALE, ORIGIN_HOLOO_CAPTURE, ORIGIN_OTHER_POS_CAPTURE)

PROVENANCE_EXTRACTED = "EXTRACTED"
PROVENANCE_DERIVED = "DERIVED"
PROVENANCES = (PROVENANCE_EXTRACTED, PROVENANCE_DERIVED)

# The frozen D-02 identity roles — the canonical header anchors (OD-A2).
ROLE_INVOICE_NUMBER = "INVOICE_NUMBER"
ROLE_INVOICE_DATE = "INVOICE_DATE"
ROLE_INVOICE_TOTAL = "INVOICE_TOTAL"
HEADER_ROLES = (ROLE_INVOICE_NUMBER, ROLE_INVOICE_DATE, ROLE_INVOICE_TOTAL)

# Declared line field roles (OD-A4 — dispatch §5 quantities/unit prices/totals).
ROLE_LINE_QUANTITY = "LINE_QUANTITY"
ROLE_LINE_UNIT_PRICE = "LINE_UNIT_PRICE"
ROLE_LINE_TOTAL = "LINE_TOTAL"
LINE_ROLES = (ROLE_LINE_QUANTITY, ROLE_LINE_UNIT_PRICE, ROLE_LINE_TOTAL)

# Stable reason codes (SPEC §4/§5/§6/§7 — every refusal/explicit state anchored)
ABSENT_REASON_UPSTREAM = "absent-upstream"                 # OD-A5: 0 usable rows
REJECT_EMPTY_LINE = "empty-line-rejected"                  # OD-A5: all roles absent
REJECT_DECLARED_FIELD_AMBIGUOUS = "declared-field-ambiguous"   # OD-A5: >=2 rows
REJECT_DECLARATION_MALFORMED = "assembly-declaration-malformed"  # §3
REJECT_DECLARATION_CONFLICT = "assembly-declaration-conflict"    # OD-A8 replay drift
REFUSE_NO_ADMISSION = "no-p6.1-accepted-admission"         # §4 A1/A3
CUSTOMER_REF_REASON = "deferred-wp9.1-d06-no-deterministic-link"  # OD-A9 (D-06)

# Verify-on-Read failure note (same vocabulary as the other layers)
NOTE_VERIFY_FAILED = "verify FAILED"


def utc_now_iso() -> str:
    """Single layer clock (OD-C4) — UTC ISO-8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Durable records — exact field sets (structurally enforced by boundary tests)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IssuedCanonicalInvoiceRecord:
    """The durable Canonical Invoice (SPEC §5 C5 / §7).

    invoice_id IS the P6.1 Kandoo-issued canonical_invoice_id, consumed
    verbatim (OD-A1; D-02 third identity; OD-G8 handover) — this layer mints
    NO identifier. Immutable once committed (OD-C7). The upstream anchor set
    is copied verbatim from the admission record; the content anchors
    (field_count/line_count/declaration_fingerprint/record_fingerprint) make
    the assembled content tamper-evident."""
    invoice_id: str                      # == admission canonical_invoice_id
    admission_decision_id: str           # UNIQUE backstop of INV-AI-1:1
    domain_state_id: str
    normalization_id: str
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    origin: str                          # frozen origins only (storage CHECK)
    identity_class: str                  # from the admission, verbatim
    identity_source: str                 # from the admission, verbatim
    identity_fingerprint: str            # from the admission, verbatim
    customer_reference: Optional[str]    # OD-A9: always None in this WP
    customer_reference_reason: str       # OD-A9 stable reason
    declaration_fingerprint: str         # sha256-v1 over the declaration
    field_count: int
    line_count: int
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class CanonicalHeaderAnchor:
    """One canonical header anchor (SPEC §5 C4) — value + pointer."""
    invoice_id: str
    role: str                            # frozen D-02 roles (storage CHECK)
    canonical_value: str                 # re-joined verified value (verbatim)
    source_field_name: str
    normalization_id: str
    field_seq: int


@dataclass(frozen=True)
class CanonicalFieldEntry:
    """One canonical field of the inventory (SPEC §5 C1/C2/C3).

    provenance relays D-01's vocabulary verbatim; the pointer columns re-join
    the verified upstream read: EXTRACTED → (source_normalization_id,
    source_field_seq); DERIVED → source_derivation_id (storage CHECK gates the
    consistency)."""
    invoice_id: str
    canonical_seq: int                   # assembly-order position (gap-free)
    provenance: str                      # EXTRACTED | DERIVED (storage CHECK)
    field_name: str                      # engine vocabulary, relayed verbatim
    canonical_value: str                 # byte-identical to the verified value
    source_normalization_id: str         # EXTRACTED pointer ("" for DERIVED)
    source_field_seq: Optional[int]      # EXTRACTED pointer (None for DERIVED)
    source_derivation_id: str            # DERIVED pointer ("" for EXTRACTED)


@dataclass(frozen=True)
class CanonicalLineField:
    """One declared line field (SPEC §6 L1/L4) — value + pointer, or an
    explicit ABSENT marker (no value is ever invented)."""
    invoice_id: str
    line_seq: int                        # declared line key (ascending order)
    role: str                            # declared line roles (storage CHECK)
    present: int                         # 1 = assembled, 0 = explicitly absent
    canonical_value: Optional[str]       # None iff absent (storage CHECK)
    source_field_name: str               # "" iff absent
    normalization_id: str                # "" iff absent
    field_seq: Optional[int]             # None iff absent


@dataclass(frozen=True)
class CanonicalLineRecord:
    """One assembled canonical line (SPEC §6) — the declared line key is the
    deterministic order; an all-absent declared line is REJECTED (OD-A5) and
    never stored."""
    invoice_id: str
    line_seq: int


@dataclass(frozen=True)
class RejectedLine:
    """An explicitly rejected declared line (SPEC §6 L2) — reported in the
    assembly outcome, never silently dropped, never stored on the invoice."""
    line_seq: int
    reason: str                          # stable code (OD-A5)


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class CanonicalAssemblyLayerError(Exception):
    """Base class for the canonical-assembly layer."""


class IssuedInvoiceNotFound(CanonicalAssemblyLayerError):
    pass


class IssuedInvoiceDuplicate(CanonicalAssemblyLayerError):
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class CanonicalAssemblyPersistenceUnavailable(CanonicalAssemblyLayerError):
    pass


# ---------------------------------------------------------------------------
# Explicit outcome types — assemble() (SPEC §8, exhaustive, never silent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssemblyCompleted:
    """The Canonical Invoice was assembled and issued atomically."""
    invoice: IssuedCanonicalInvoiceRecord
    header_anchors: Tuple[CanonicalHeaderAnchor, ...]
    fields: Tuple[CanonicalFieldEntry, ...]
    lines: Tuple[CanonicalLineRecord, ...]
    line_fields: Tuple[CanonicalLineField, ...]
    rejected_lines: Tuple[RejectedLine, ...]


@dataclass(frozen=True)
class AssemblyAlreadyAssembled:
    """Idempotent replay (OD-A8): the same admission + the same declaration —
    the existing invoice is returned verbatim; no new rows."""
    invoice: IssuedCanonicalInvoiceRecord
    header_anchors: Tuple[CanonicalHeaderAnchor, ...]
    fields: Tuple[CanonicalFieldEntry, ...]
    lines: Tuple[CanonicalLineRecord, ...]
    line_fields: Tuple[CanonicalLineField, ...]


@dataclass(frozen=True)
class AssemblyInputIntegrityFailure:
    """Fail-closed input verification (SPEC §4 A1/A2/A5/A6)."""
    canonical_invoice_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class AssemblyRequestRefused:
    """Request-level refusal with ZERO durable residue (SPEC §3/§4 A3/A4,
    §6 L1, §7 I4)."""
    canonical_invoice_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class AssemblyStorageUnavailable:
    """Nothing recordable — the transaction rolled back, zero residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — reads / trace (SPEC §8)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssemblyReadSuccess:
    invoice: IssuedCanonicalInvoiceRecord
    header_anchors: Tuple[CanonicalHeaderAnchor, ...]
    fields: Tuple[CanonicalFieldEntry, ...]
    lines: Tuple[CanonicalLineRecord, ...]
    line_fields: Tuple[CanonicalLineField, ...]
    verified_at: str


@dataclass(frozen=True)
class AssemblyReadIntegrityFailure:
    invoice_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class AssemblyReadRefused:
    invoice_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class AssemblyReadVerificationUnavailable:
    invoice_id: Optional[str]
    issue_report: str


@dataclass(frozen=True)
class AssemblyTraceSuccess:
    invoice_id: str
    chain: Tuple[str, ...]               # ordered coarse link verdicts
    verified_at: str


@dataclass(frozen=True)
class AssemblyTraceIntegrityFailure:
    invoice_id: str
    link: str                            # issued_invoice|admission|domain_state|fields|lines
    reason: str


@dataclass(frozen=True)
class AssemblyTraceRefused:
    invoice_id: str
    detail: str


@dataclass(frozen=True)
class AssemblyTraceVerificationUnavailable:
    invoice_id: str
    issue_report: str
