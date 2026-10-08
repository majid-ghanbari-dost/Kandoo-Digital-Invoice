"""Corpus domain model — WP-12.1 (SPEC-WP121-CORPUS).

The Pilot corpus layer: clearly-marked SYNTHETIC pilot input material with
declared ground-truth labels. This package is NOT a production domain layer —
no production package may import it (SPEC §2.3); its only sanctioned consumer
is the WP-12.2 calibration layer and this WP's own tests/smoke.

Determinism discipline: no clock, no randomness, no environment in any
VALUE — the whole package is clock-free (OD-CA-J): corpus material is
content-addressed pilot input and has no operational clock semantics.
Entropy is derived exclusively through the capture S1 service (the
project's single hash capability) — no direct digest use anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Vocabulary (SPEC §3) — exact literals, fail-closed everywhere
# ---------------------------------------------------------------------------

ORIGIN_SYNTHETIC = "SYNTHETIC_PILOT_FIXTURE"
CORPUS_ORIGINS = (ORIGIN_SYNTHETIC,)

MARKING_SYNTHETIC = "SYNTHETIC-PILOT-FIXTURE — NOT PRODUCTION DATA"
CORPUS_MARKINGS = (MARKING_SYNTHETIC,)

LABEL_KIND_VALUE = "VALUE"          # expected normalized value present
LABEL_KIND_ABSENT = "ABSENT"        # the field is expected to be absent
LABEL_KINDS = (LABEL_KIND_VALUE, LABEL_KIND_ABSENT)

LABEL_PROVENANCE_DECLARED = "DECLARED-GROUND-TRUTH"

# Declared bound (OD-CA-F) — assembly-weight guard.
MAX_ENTRIES = 10000

# Canonical serialization tags (SPEC §5)
ENTRY_TAG = b"kandoo-corpus-entry-v1"
MANIFEST_TAG = b"kandoo-corpus-manifest-v1"

FINGERPRINT_ALGORITHM_ID = "sha256-v1"   # via the capture S1 service only


# ---------------------------------------------------------------------------
# Typed failures (SPEC §8 — every anomaly explicit, nothing guessed)
# ---------------------------------------------------------------------------

class CorpusLayerError(Exception):
    """Base class for every explicit corpus-layer failure."""


class CorpusInputRefused(CorpusLayerError):
    """Declared inputs are malformed/unknown/out-of-bounds — nothing generated."""


class CorpusTemplateUnknown(CorpusInputRefused):
    """The requested template_id is not a registered declared generator."""


class CorpusDuplicateVersion(CorpusLayerError):
    """A stored corpus version's rows disagree with a re-assembly under the
    same content address — fail-closed integrity refusal (never repaired)."""


class CorpusStorageUnavailable(CorpusLayerError):
    """The corpus store could not be opened/committed — nothing is presented."""


class CorpusNotFound(CorpusLayerError):
    """No corpus version under the requested content address."""


class CorpusReadIntegrityFailure(CorpusLayerError):
    """Stored bytes no longer match the committed fingerprint — the corpus is
    WITHHELD (never partially delivered, never silently repaired)."""


class CorpusReadRefused(CorpusLayerError):
    """Read refused for a structural reason (shape/constraint violation)."""


class CorpusVerificationUnavailable(CorpusLayerError):
    """No verdict computable (unknown fingerprint algorithm id — version skew)."""


# ---------------------------------------------------------------------------
# Declarations and durable shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CorpusLabel:
    """One declared ground-truth label over an engine-vocabulary field name.

    kind VALUE: expected_value is the canonical normalized form the pipeline
    must reproduce. kind ABSENT: expected_value is None and the field is
    expected NOT to appear downstream (measured, not guessed).
    """
    field_name: str
    kind: str                       # LABEL_KIND_VALUE | LABEL_KIND_ABSENT
    expected_value: Optional[str]   # canonical form; None iff ABSENT
    label_provenance: str = LABEL_PROVENANCE_DECLARED


@dataclass(frozen=True)
class CorpusEntry:
    """One durable corpus entry — pages + labels under explicit provenance."""
    corpus_version_id: str          # = the manifest fingerprint (content address)
    ordinal: int
    template_id: str
    entry_seed: int
    origin_role: str
    marking: str
    parts: Tuple[bytes, ...]        # raw page parts (pipeline-ingestible shape)
    labels: Tuple[CorpusLabel, ...] # sorted by field_name (canonical order)
    entry_fingerprint: str
    fingerprint_algorithm_id: str


@dataclass(frozen=True)
class CorpusManifest:
    """One durable corpus version — the content-addressed manifest."""
    corpus_version_id: str          # = manifest fingerprint (hex)
    template_id: str
    seed_base: int
    entry_count: int
    origin_role: str
    marking: str
    entries_blob: str               # deterministic "ordinal:fingerprint" ledger
    manifest_fingerprint: str
    fingerprint_algorithm_id: str


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CorpusAssembled:
    """Fresh assembly committed (one atomic transaction)."""
    manifest: CorpusManifest
    entries: Tuple[CorpusEntry, ...]


@dataclass(frozen=True)
class CorpusReplay:
    """The same content address already exists and every row byte-matches the
    re-assembly — verbatim replay, ZERO new rows (D-03 discipline)."""
    manifest: CorpusManifest
    entries: Tuple[CorpusEntry, ...]


@dataclass(frozen=True)
class CorpusReadSuccess:
    """Verified read: manifest VOR + every entry VOR + manifest fingerprint
    recomputed over the read entries + count agreement. Clock-free (OD-CA-J):
    no read-timestamp field exists — a verified read is a STATE, not an event."""
    manifest: CorpusManifest
    entries: Tuple[CorpusEntry, ...]
