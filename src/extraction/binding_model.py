"""Extraction Evidence Binding — domain model (WP-3.2 MVP implementation).

Binding basis:
  SPEC-WP32-EVB  Extraction Evidence Binding Contract v1.0-MVP (inline per TM dispatch
                 2026-10-01 — direct real build, no separate design/review phase)
  D-01 (provenance vocabulary untouched) | D-02/D-03 (untouched) | D-09 (delegated
  details declared in binding.py) | AS-01 flow position
  WP-2.2 evidence (read-only consumer) | WP-3.1 extraction record + spans (the bound
  artifact) | WP-2.1 verified document read (the only source re-read path)

Boundary (normative): a binding is STRUCTURAL PROOF — ids, fingerprints, offsets, names,
timestamps. It never carries a value, never interprets content, and never introduces data
from Normalization/Canonicalization/Validation (P4+). Capture (WP-1.1), Reconstruction
(WP-2.1) and the Reconstruction Evidence log (WP-2.2) are consumed read-only through their
own sanctioned interfaces and are never modified by this layer.

Every outcome type is explicit; a silent result does not exist in this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Failure-link vocabulary — WHERE a verified read / bind broke (coarse, no content)
# ---------------------------------------------------------------------------

class BindingLink(str, Enum):
    """Which link of the provable chain failed verification.

    binding    — the binding log itself (fingerprint/chain/head/tiling defect)
    extraction — the bound extraction record (missing, tampered, or unanchorable)
    document   — the source document verified read (missing, tampered, linkage drift)
    evidence   — the reconstruction evidence anchor (missing, tampered, anchor drift)
    span       — a field's source span (entry/field mismatch or slice-decode mismatch)
    """
    BINDING = "binding"
    EXTRACTION = "extraction"
    DOCUMENT = "document"
    EVIDENCE = "evidence"
    SPAN = "span"


# ---------------------------------------------------------------------------
# Records — exact field sets (structurally enforced by the boundary test)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BindingFieldEntry:
    """Per-field structural source anchor — WHERE one extracted value came from.

    Positions are byte offsets INSIDE the durable page named by page_index; the
    page→source-artifact ranges remain owned by the WP-2.2 DOCUMENT_COMPLETED payload.
    There is deliberately NO value field here: values live in the fingerprint-anchored
    extraction record (OD-B7); fidelity is proven by joining the two stores.
    """
    field_seq: int
    field_name: str
    page_index: int
    byte_start: int
    byte_end: int
    page_fingerprint: str


@dataclass(frozen=True)
class ExtractionBindingRecord:
    """Durable binding record — the provable link extraction ↔ evidence ↔ source.

    seq is the append-only log position; prev_binding_hash/binding_hash form the global
    tamper-evident chain (OD-B2). recon_evidence_seq/recon_evidence_record_hash anchor
    the document's DOCUMENT_COMPLETED evidence record as verified at binding time.
    """
    binding_id: str
    seq: int
    extraction_id: str
    document_id: str
    capture_id: str
    capture_s1: str
    capture_s1_algorithm_id: str
    extraction_record_fingerprint: str
    extraction_fingerprint_algorithm_id: str
    recon_evidence_seq: int
    recon_evidence_record_hash: str
    field_binding_count: int
    created_at: str
    binding_fingerprint: str
    binding_fingerprint_algorithm_id: str
    prev_binding_hash: str
    binding_hash: str


@dataclass(frozen=True)
class BindingRef:
    """Document-scoped lookup result — which extraction has which binding."""
    extraction_id: str
    binding_id: str
    created_at: str


# ---------------------------------------------------------------------------
# Exceptions — every failure surfaces explicitly
# ---------------------------------------------------------------------------

class BindingLayerError(Exception):
    """Base class for all explicit binding-layer failures."""


class BindingNotFound(BindingLayerError):
    """No binding exists for the referenced extraction_id."""

    def __init__(self, extraction_id: str) -> None:
        super().__init__(f"no binding for extraction: {extraction_id}")
        self.extraction_id = extraction_id


class BindingDuplicate(BindingLayerError):
    """INV-B-1:1 — a binding for this extraction_id already exists. Raised inside the
    atomic commit; the service surfaces it as an explicit AlreadyExists outcome carrying
    the existing binding_id."""

    def __init__(self, binding_id: str) -> None:
        super().__init__(f"binding already exists: {binding_id}")
        self.binding_id = binding_id


class BindingPersistenceUnavailable(BindingLayerError):
    """D-2 analog: no binding durably committed (atomic txn rolled back — zero residue).
    Never a silent partial write."""


# ---------------------------------------------------------------------------
# Bind outcomes (exhaustive — consumed from verified extraction records only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BindingCompleted:
    """Whole chain verified at bind time; binding + per-field entries durably committed
    in one atomic transaction."""
    binding: ExtractionBindingRecord
    entries: Tuple[BindingFieldEntry, ...]


@dataclass(frozen=True)
class BindingAlreadyExists:
    """INV-B-1:1 replay: this extraction was already bound. Explicit, never a silent
    no-op; no second binding is created."""
    binding_id: str
    extraction_id: str


@dataclass(frozen=True)
class BindingSourceIntegrityFailure:
    """A source link failed its verified read or fidelity check — nothing bound, nothing
    persisted. The binding's existence IS the proof; it is only created when every link
    verifies."""
    link: BindingLink
    detail: str


@dataclass(frozen=True)
class BindingSourceRefused:
    """A source link explicitly refused (missing record / wrong state) — nothing bound."""
    link: BindingLink
    detail: str


@dataclass(frozen=True)
class BindingSourceUnavailable:
    """A source link could not be verified (no verdict computable; Issue-Report) —
    nothing bound, fail-closed."""
    link: BindingLink
    issue_report: str


@dataclass(frozen=True)
class BindingStorageUnavailable:
    """D-2 analog: the binding is not durably recordable — nothing persisted, zero
    residue in the binding store."""
    detail: str


# ---------------------------------------------------------------------------
# Read outcomes (VOR pattern — exhaustive; no silent broken read exists)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BindingReadSuccess:
    """Binding + per-field entries delivered ONLY together with a same-read VALID verdict
    over EVERY link (binding log, extraction, document, evidence, spans)."""
    binding: ExtractionBindingRecord
    entries: Tuple[BindingFieldEntry, ...]
    verified_at: str


@dataclass(frozen=True)
class BindingReadIntegrityFailure:
    """Definitive integrity failure at ONE coarse link (tamper, deletion, forgery, or
    drift); the binding and its entries are NEVER delivered on this outcome."""
    link: BindingLink
    reason: str
    failure_seq: Optional[int]          # log position, when the failure is in the log
    verified_at: str


@dataclass(frozen=True)
class BindingReadRefused:
    """No binding exists for the requested extraction_id — no fabrication, no verdict."""
    extraction_id: Optional[str]
    detail: str


@dataclass(frozen=True)
class BindingReadVerificationUnavailable:
    """No verdict computable for the binding read (e.g. unknown fingerprint algorithm) —
    nothing delivered, Issue-Report surfacing."""
    extraction_id: str
    issue_report: str


# ---------------------------------------------------------------------------
# Whole-log audit (tests, smoke, operators)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BindingChainReport:
    """Whole-log audit result (verify_chain)."""
    valid: bool
    records: int
    last_seq: Optional[int]
    failure_seq: Optional[int] = None
    reason: Optional[str] = None
