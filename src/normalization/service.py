"""Normalization service — verified Extraction output → Normalized structured data
(WP-4.1 MVP, T-4.1.2 scope).

Binding basis: SPEC-WP41-NORM §2/§6/§7/§8; SPEC-WP31-EXT §2 analog (the verified
extraction read is the ONLY sanctioned input path — this service never touches the
extraction/document/capture stores directly and never re-reads raw artifacts); D-01
(provenance relayed verbatim — never re-decided); D-03 analog (nothing is deduplicated —
the field mapping is TOTAL and positional); D-09 (rulesets are constructor-injected seams).

  normalize(extraction_id, ruleset_id):
    registry lookup → verified extraction read (VOR path, frozen WP-3.1 service) →
    INV-N-1:1 pre-check → per-field deterministic ruleset application (TOTAL positional
    mapping; explicit statuses) → atomic durable commit.

  read_normalization(normalization_id):
    VOR-pattern verified read — record fingerprint recomputed over the durable rows
    INSIDE the read; content delivered only on the same-read VALID verdict.

The service owns orchestration only; every durable effect goes through the store; every
fingerprint computation goes through the reused capture S1 capability (sha256-v1).
No canonicalization/identity/business datum is produced anywhere.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Tuple

from capture import S1Service
from extraction import (
    ExtractionReadIntegrityFailure,
    ExtractionReadRefused,
    ExtractionReadSuccess,
    ExtractionReadVerificationUnavailable,
    ExtractionService,
)

from .model import (
    NOTE_VERIFY_FAILED,
    NOTE_VERIFICATION_UNAVAILABLE,
    NormalizationAlreadyExists,
    NormalizationCompleted,
    NormalizationDuplicate,
    NormalizedField,
    NormalizationNotFound,
    NormalizationPersistenceUnavailable,
    NormalizationReadIntegrityFailure,
    NormalizationReadRefused,
    NormalizationReadSuccess,
    NormalizationReadVerificationUnavailable,
    NormalizationRulesetNotRegistered,
    NormalizationSourceIntegrityFailure,
    NormalizationSourceRefused,
    NormalizationSourceUnavailable,
    NormalizationStorageUnavailable,
    NormalizationRecord,
    utc_now_iso,
)
from .rules import NormalizationRuleSet
from .store import NormalizationStore, canonical_normalization_bytes


class NormalizationService:
    """The normalization entry point: verified Extraction → ruleset → durable normalized data."""

    def __init__(self, store: NormalizationStore, extraction: ExtractionService,
                 rulesets: Mapping[str, NormalizationRuleSet],
                 s1: S1Service) -> None:
        self._store = store
        self._extraction = extraction
        self._rulesets: Dict[str, NormalizationRuleSet] = dict(rulesets)
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Normalize — verified extraction → ruleset → durable (SPEC §2, §6, §7)
    # ------------------------------------------------------------------

    def normalize(self, extraction_id: str, ruleset_id: str) -> object:
        """Normalize one verified extraction with one registered ruleset.

        Outcome is exactly one explicit type — never silent:
          NormalizationCompleted | NormalizationAlreadyExists (INV-N-1:1 replay) |
          NormalizationSourceIntegrityFailure | NormalizationSourceRefused |
          NormalizationSourceUnavailable (nothing created — source-side outcomes) |
          NormalizationRulesetNotRegistered | NormalizationStorageUnavailable.
        """
        ruleset = self._rulesets.get(ruleset_id)
        if ruleset is None:
            return NormalizationRulesetNotRegistered(extraction_id, ruleset_id)

        # Step 1: verified source read — the ONLY sanctioned path into extraction content
        # (VOR: verdict computed inside the read; FAILED never delivers content).
        read = self._extraction.read_extraction(extraction_id)
        if isinstance(read, ExtractionReadIntegrityFailure):
            return NormalizationSourceIntegrityFailure(extraction_id, read.reason)
        if isinstance(read, ExtractionReadRefused):
            return NormalizationSourceRefused(read.extraction_id, read.detail)
        if isinstance(read, ExtractionReadVerificationUnavailable):
            self._issues.append(
                f"normalization on {extraction_id}: {read.issue_report}")
            return NormalizationSourceUnavailable(extraction_id, read.issue_report)
        assert isinstance(read, ExtractionReadSuccess)    # exhaustive by construction

        # Step 2: INV-N-1:1 pre-check (the atomic commit backstops races — UAC-lite).
        existing = self._store.find_by_triple(extraction_id, ruleset.ruleset_id,
                                              ruleset.ruleset_version)
        if existing is not None:
            return NormalizationAlreadyExists(existing, extraction_id,
                                              ruleset.ruleset_id,
                                              ruleset.ruleset_version)

        # Step 3: deterministic per-field application — TOTAL positional mapping
        # (every extracted field yields exactly one normalized field; nothing skipped,
        # nothing invented; statuses/reasons per SPEC §4).
        fields: Tuple[NormalizedField, ...] = tuple(
            ruleset.normalize_field(f) for f in read.fields)

        # Step 4: atomic durable commit (record + fields in one transaction).
        record = read.extraction          # ExtractionReadSuccess.extraction (frozen shape)
        try:
            saved = self._store.commit_normalization(
                extraction_id=extraction_id,
                document_id=record.document_id,
                capture_id=record.capture_id,
                capture_s1=record.capture_s1,
                capture_s1_algorithm_id=record.capture_s1_algorithm_id,
                engine_id=record.engine_id,
                engine_schema_version=record.engine_schema_version,
                ruleset_id=ruleset.ruleset_id,
                ruleset_version=ruleset.ruleset_version,
                fields=fields,
            )
        except NormalizationDuplicate as exc:
            return NormalizationAlreadyExists(exc.normalization_id, extraction_id,
                                              ruleset.ruleset_id, ruleset.ruleset_version)
        except NormalizationPersistenceUnavailable as exc:
            # OD-N2: atomic commit → zero residue in every persistence failure.
            return NormalizationStorageUnavailable(str(exc))
        return NormalizationCompleted(saved, fields)

    # ------------------------------------------------------------------
    # Verified read — VOR pattern bound to normalization records (SPEC §7)
    # ------------------------------------------------------------------

    def read_normalization(self, normalization_id: str) -> object:
        """Read a normalization record with a definitive integrity verdict computed INSIDE
        the read. Every outcome explicit: NormalizationReadSuccess |
        NormalizationReadIntegrityFailure (stored content NEVER delivered) |
        NormalizationReadRefused (unknown id) | NormalizationReadVerificationUnavailable
        (no verdict computable; Issue-Report)."""
        try:
            record = self._store.get_record(normalization_id)
        except NormalizationNotFound:
            return NormalizationReadRefused(None, "no such normalization record")
        try:
            fields = self._store.get_fields(normalization_id)
        except NormalizationNotFound:                     # pragma: no cover - defensive
            self._issues.append(f"normalization {normalization_id}: field rows vanished")
            return NormalizationReadVerificationUnavailable(
                normalization_id, "field rows missing — Issue Report required")

        if len(fields) != record.field_count:
            issue = (f"durable field set inconsistent "
                     f"(field_count={record.field_count}, rows={len(fields)})")
            self._issues.append(f"normalization {normalization_id}: {issue}")
            return NormalizationReadVerificationUnavailable(
                normalization_id, issue + " — Issue Report required")

        recomputed = canonical_normalization_bytes(record, fields)
        verdict = self._s1.verify(recomputed, record.record_fingerprint,
                                  record.fingerprint_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            issue = (f"record verification unavailable: "
                     f"{verdict.reason or 'capability failure'}")
            self._issues.append(f"normalization {normalization_id}: {issue}")
            return NormalizationReadVerificationUnavailable(
                normalization_id, issue + " — Issue Report required")
        if verdict.outcome == "FAILED":
            return NormalizationReadIntegrityFailure(normalization_id, NOTE_VERIFY_FAILED,
                                                     utc_now_iso())
        return NormalizationReadSuccess(record, tuple(fields), utc_now_iso())

    # ------------------------------------------------------------------
    # Traceability enumeration (extraction-scoped; Canonicalization consumer)
    # ------------------------------------------------------------------

    def normalization_ids_for_extraction(self, extraction_id: str) -> Tuple[str, ...]:
        """All normalization records for an extraction — deterministic order."""
        return tuple(self._store.find_for_extraction(extraction_id))

    # ------------------------------------------------------------------
    # Issue-report surface (minimal MVP hook, VOR §2 analog)
    # ------------------------------------------------------------------

    def issue_reports(self) -> list:
        """Accumulated Issue-Report items surfaced by this service instance."""
        return list(self._issues)
