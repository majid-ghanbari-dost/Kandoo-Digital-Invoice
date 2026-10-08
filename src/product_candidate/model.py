"""Product Exact Match domain model — WP-8.1 MVP implementation.

Binding basis: SPEC-WP81-PMATCH (all sections; OD-PM1..PM8 declared across
store.py / service.py).

Vocabulary discipline (AS-03/AS-04/AD-04/CL-1 + SPEC §5 — verbatim, no
paraphrase, no invention):
  - The match outcome vocabulary (OD-PM7, delegated per D-09): the DURABLE
    outcome is EXACT_MATCHED | UNRESOLVED. This is a Product Candidate
    domain match fact — NOT a P5 field status and NOT a canonicalization
    state; no synonym of any frozen word is introduced. "UNRESOLVED" here is
    the D-05-conformant absence of an exact match (ambiguity remains
    ambiguity), never a P5 UNRESOLVED field value (which this layer never
    creates, reads, or resolves).
  - Provenance labels are D-01's vocabulary VERBATIM: EXTRACTED | DERIVED —
    relayed from the verified P6.2 canonical field, never decided here.
  - Identifier kinds/values are DECLARED opaque strings (OD-PM3): stored and
    compared verbatim; NO enumeration, NO barcode semantics, NO format
    grammar, NO checksum, NO normalization.
  - invoice_id is the D-02 Canonical Identity issued at P6.1 — consumed
    VERBATIM (no identifier is minted in this layer).

Pointer discipline (OD-PM6 / OD-IR-J precedent): the durable match row
carries declarations, pointers and counts — NEVER the invoice's identifier
value. The value lives in the verified P6.2 canonical field (re-joined live
on every read) and in the catalog register's own registered content.

This module is dataclasses + vocabularies + exceptions + explicit outcome
types ONLY — no I/O, no persistence, no clock, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Vocabularies (declared per D-09 — see module docstring)
# ---------------------------------------------------------------------------

MATCH_OUTCOME_EXACT_MATCHED = "EXACT_MATCHED"
MATCH_OUTCOME_UNRESOLVED = "UNRESOLVED"

# Storage CHECK mirror (§5): the durable outcome vocabulary is exactly these
# two; there is no candidate/approval/confidence outcome of any kind.
DURABLE_MATCH_OUTCOMES = (MATCH_OUTCOME_EXACT_MATCHED,
                          MATCH_OUTCOME_UNRESOLVED)

UNRESOLVED_NO_CATALOG_IDENTITY = "no-catalog-identity"

# The only UNRESOLVED reason reachable in this WP (storage CHECK pins it —
# any future reason requires a contract change; fail-closed by design).
DURABLE_UNRESOLVED_REASONS = (UNRESOLVED_NO_CATALOG_IDENTITY,)

PROVENANCE_EXTRACTED = "EXTRACTED"
PROVENANCE_DERIVED = "DERIVED"
PROVENANCES = (PROVENANCE_EXTRACTED, PROVENANCE_DERIVED)

# Stable request-refusal codes (§3/§4 — zero durable residue)
REFUSE_DECLARATION_MALFORMED = "declaration-malformed"
REFUSE_FIELD_NOT_FOUND = "declared-field-not-found"
REFUSE_FIELD_AMBIGUOUS = "declared-field-ambiguous"

# Verify-on-Read failure note (same vocabulary as the other layers)
NOTE_VERIFY_FAILED = "verify FAILED"


def utc_now_iso() -> str:
    """Single layer clock (OD-PM1) — UTC ISO-8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Durable records — exact field sets (structurally enforced by boundary tests)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CatalogIdentityRecord:
    """One registered catalog product identity (OD-PM2) — the minimal
    Product-side register surface required by D-05's `Catalog Identity`
    output. Created ONLY by the explicit registration API (which carries no
    capture/invoice parameter — no capture-derived catalog mutation is
    possible). Immutable once committed. identifier_kind / identifier_value
    are stored VERBATIM (OD-PM3)."""
    catalog_identity_id: str
    identifier_kind: str
    identifier_value: str
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class ProductMatchRecord:
    """Durable exact-match fact for ONE declared product reference on ONE
    issued Canonical Invoice (INV-PM-1:1 per
    (invoice_id, declared_field_name, identifier_kind) — UNIQUE backstop).

    All invoice semantics ride the LINKED P6.2 verified read (invoice_id):
    this record copies the anchor pointers for self-description and
    cross-store verification — it decides nothing and stores NO identifier
    value (OD-PM6). Immutable once committed. Content determinism is
    separated from bookkeeping: match_id / created_at are bookkeeping; the
    match fact is a pure function of the invoice's verified content and the
    catalog register at first-match time (OD-PM4)."""
    match_id: str
    invoice_id: str                      # the linked P6.2 issued invoice
    capture_s1: str                      # copied anchor (cross-checked on read)
    capture_s1_algorithm_id: str
    declared_field_name: str
    canonical_seq: int                   # pointer into the verified field
                                         # inventory (stable, gap-free)
    provenance: str                      # D-01 label of the resolved field
    identifier_kind: str
    match_outcome: str                   # EXACT_MATCHED | UNRESOLVED
                                         # (storage CHECK)
    catalog_identity_id: str             # '' iff UNRESOLVED
    unresolved_reason: str               # '' iff EXACT_MATCHED; stable code
    created_at: str
    record_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class ProductCandidateLayerError(Exception):
    """Base class for the product-candidate layer."""


class CatalogIdentityNotFound(ProductCandidateLayerError):
    pass


class CatalogIdentityDuplicate(ProductCandidateLayerError):
    """The UNIQUE (identifier_kind, identifier_value) backstop hit inside the
    commit transaction — the existing catalog identity wins, never a second
    row for a definitive identifier."""
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class MatchNotFound(ProductCandidateLayerError):
    pass


class MatchDuplicate(ProductCandidateLayerError):
    """INV-PM-1:1 hit inside the commit transaction (in-txn check or UNIQUE
    backstop) — the existing match outcome wins, never a second fact."""
    def __init__(self, existing_id: str) -> None:
        super().__init__(existing_id)
        self.existing_id = existing_id


class ProductCandidatePersistenceUnavailable(ProductCandidateLayerError):
    pass


# ---------------------------------------------------------------------------
# Explicit outcome types — register_catalog_identity (SPEC §3, exhaustive)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CatalogIdentityRegistered:
    """A NEW catalog identity was registered (first sighting)."""
    catalog_identity: CatalogIdentityRecord


@dataclass(frozen=True)
class CatalogIdentityReplay:
    """Idempotent re-registration of the same (kind, value): the existing
    catalog identity returned VERBATIM — no new rows (OD-PM2)."""
    catalog_identity: CatalogIdentityRecord


@dataclass(frozen=True)
class CatalogRegistrationRefused:
    """Request-level refusal with ZERO durable residue (§3: empty kind or
    value)."""
    detail: str


@dataclass(frozen=True)
class CatalogStorageUnavailable:
    """Catalog persistence failure — the transaction rolled back, zero
    residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — match() (SPEC §4, exhaustive, never silent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductExactMatched:
    """The declared reference byte-matched EXACTLY ONE catalog identity under
    the declared kind (M5) — the D-05 Exact Match → Catalog Identity output,
    committed durably."""
    record: ProductMatchRecord
    invoice_read: object                 # AssemblyReadSuccess (linked)
    catalog_identity: CatalogIdentityRecord


@dataclass(frozen=True)
class ProductReferenceUnresolved:
    """NO catalog identity exists for the declared identifier (M5) — a
    durable, auditable UNRESOLVED fact. Ambiguity remains ambiguity: no
    candidate is generated, nothing is guessed (OD-PM7)."""
    record: ProductMatchRecord
    invoice_read: object                 # AssemblyReadSuccess (linked)
    reason: str


@dataclass(frozen=True)
class ProductMatchReplay:
    """The declared reference was already matched (M4/M6): the existing
    outcome returned VERBATIM after its full verified read — ZERO new rows;
    replay never re-decides (OD-PM4)."""
    record: ProductMatchRecord
    invoice_read: object                 # AssemblyReadSuccess (linked)
    catalog_identity: Optional[object]   # set iff EXACT_MATCHED
    verified_at: str


@dataclass(frozen=True)
class ProductMatchRequestRefused:
    """Request-level refusal (M2/M3) with ZERO durable residue: malformed
    declaration, declared field not found, or declared field ambiguous
    (never auto-resolution)."""
    invoice_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class ProductMatchInputIntegrityFailure:
    """Fail-closed input verification (M1): the linked P6.2 read refused /
    failed / unverifiable (propagated verbatim), or the catalog lookup
    observed an impossible ≥2 state (store corruption — never a match
    decision, OD-PM5). Zero durable residue."""
    invoice_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class ProductMatchStorageUnavailable:
    """Match persistence failure — the transaction rolled back, zero
    residue."""
    detail: str


# ---------------------------------------------------------------------------
# Explicit outcome types — verified reads (SPEC §6)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductMatchReadSuccess:
    """Verified match read: the match row verified (own VOR), the linked
    invoice re-verified through the P6.2 verified read with the pointer
    re-joined, and — iff EXACT_MATCHED — the linked catalog identity
    re-verified with the match RE-PROVEN LIVE (byte-identity of the
    invoice's canonical value and the catalog identifier value)."""
    record: ProductMatchRecord
    invoice_read: object                 # AssemblyReadSuccess (re-verified)
    catalog_identity: Optional[object]   # re-verified iff EXACT_MATCHED
    verified_at: str


@dataclass(frozen=True)
class CatalogReadSuccess:
    """Verified catalog identity read (own VOR)."""
    catalog_identity: CatalogIdentityRecord
    verified_at: str


@dataclass(frozen=True)
class ProductMatchReadIntegrityFailure:
    match_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class ProductMatchReadRefused:
    match_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class ProductMatchReadVerificationUnavailable:
    match_id: Optional[str]
    issue_report: str


@dataclass(frozen=True)
class CatalogReadIntegrityFailure:
    catalog_identity_id: Optional[str]
    reason: str
    verified_at: str


@dataclass(frozen=True)
class CatalogReadRefused:
    catalog_identity_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class CatalogReadVerificationUnavailable:
    catalog_identity_id: Optional[str]
    issue_report: str
