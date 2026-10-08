"""Extraction service — Document/Page → Extraction-ready input → Extracted structured
data (WP-3.1 MVP, T-3.1.2 scope).

Binding basis: SPEC-WP31-EXT v1.0-MVP; WP-2.1 §7 boundary (the verified document read is
the ONLY sanctioned input path — no parallel re-interpretation of raw artifacts, ever);
D-01 (provenance), D-03 (no document-level dedup here — field sequences are never
deduplicated), D-09 (engine-agnostic; the engine is a constructor-injected seam).

  extract(document_id, engine_id):
    registry lookup → verified document read (VOR path, frozen WP-2.1 service) →
    ExtractionInput (explicit extraction-ready projection) → engine.extract_pages →
    engine-contract validation (C2–C5) → field_seq assignment → atomic durable commit
    (INV-X-1:1).

  read_extraction(extraction_id):
    VOR-pattern verified read — record fingerprint recomputed over the durable rows
    INSIDE the read; content delivered only on the same-read VALID verdict.

The service owns orchestration only; every durable effect goes through the store; every
fingerprint computation goes through the reused capture S1 capability (sha256-v1).
No normalization/canonicalization/validation-policy datum is produced anywhere — values
are verbatim, positioned, EXTRACTED-labeled.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from capture import S1Service
from reconstruction import (
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadSuccess,
    DocumentReadVerificationUnavailable,
    PageView,
    ReconstructionService,
)

from .engine import ExtractionEngine, ExtractionEngineError
from .model import (
    NOTE_VERIFY_FAILED,
    NOTE_VERIFICATION_UNAVAILABLE,
    ExtractedField,
    ExtractionAlreadyExists,
    ExtractionCompleted,
    ExtractionDuplicate,
    ExtractionEngineContractViolation,
    ExtractionEngineFailed,
    ExtractionEngineNotRegistered,
    ExtractionInput,
    ExtractionNotFound,
    ExtractionPersistenceUnavailable,
    ExtractionReadIntegrityFailure,
    ExtractionReadRefused,
    ExtractionReadSuccess,
    ExtractionReadVerificationUnavailable,
    ExtractionSourceIntegrityFailure,
    ExtractionSourceRefused,
    ExtractionSourceUnavailable,
    ExtractionStorageUnavailable,
    Provenance,
    SourceSpan,
    utc_now_iso,
)
from .store import ExtractionStore, canonical_extraction_bytes


class ExtractionService:
    """The extraction entry point: verified Document → engine → durable structured data."""

    def __init__(self, store: ExtractionStore, reconstruction: ReconstructionService,
                 engines: Mapping[str, ExtractionEngine], s1: S1Service) -> None:
        self._store = store
        self._reconstruction = reconstruction
        self._engines: Dict[str, ExtractionEngine] = dict(engines)
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Extract — verified document → engine → validated → durable (SPEC §2–§5)
    # ------------------------------------------------------------------

    def extract(self, document_id: str, engine_id: str) -> object:
        """Run one engine over one verified document.

        Outcome is exactly one explicit type — never silent:
          ExtractionCompleted | ExtractionAlreadyExists (INV-X-1:1 replay) |
          ExtractionSourceIntegrityFailure | ExtractionSourceRefused |
          ExtractionSourceUnavailable (nothing created — source-side outcomes) |
          ExtractionEngineNotRegistered | ExtractionEngineFailed |
          ExtractionEngineContractViolation | ExtractionStorageUnavailable.
        """
        engine = self._engines.get(engine_id)
        if engine is None:
            return ExtractionEngineNotRegistered(document_id, engine_id)

        # Step 1: verified source read — the ONLY sanctioned path into document content
        # (VOR: verdict computed inside the read; FAILED never delivers content).
        read = self._reconstruction.read_document(document_id)
        if isinstance(read, DocumentReadIntegrityFailure):
            return ExtractionSourceIntegrityFailure(document_id, read.reason)
        if isinstance(read, DocumentReadRefused):
            return ExtractionSourceRefused(read.document_id, read.document_state,
                                           read.detail)
        if isinstance(read, DocumentReadVerificationUnavailable):
            self._issues.append(f"extraction on {document_id}: {read.issue_report}")
            return ExtractionSourceUnavailable(document_id, read.issue_report)
        assert isinstance(read, DocumentReadSuccess)      # exhaustive by construction

        # Step 2: extraction-ready input — explicit projection of the verified read
        # (traceability travels WITH the run; pages stay content+structure only).
        extraction_input = ExtractionInput(
            document_id=read.document_id,
            capture_id=read.capture_id,
            capture_s1=read.capture_s1,
            capture_s1_algorithm_id=read.capture_s1_algorithm_id,
            page_count=read.page_count,
            pages=read.pages,
        )

        # Step 3: INV-X-1:1 pre-check (the atomic commit backstops races — UAC-lite).
        existing = self._store.find_by_triple(document_id, engine.engine_id,
                                              engine.schema_version)
        if existing is not None:
            return ExtractionAlreadyExists(existing, document_id,
                                           engine.engine_id, engine.schema_version)

        # Step 4: run the engine — every failure surfaces explicitly, nothing persists.
        try:
            raw_fields = engine.extract_pages(extraction_input.pages)
        except ExtractionEngineError as exc:
            return ExtractionEngineFailed(document_id, engine.engine_id, str(exc))
        except Exception as exc:                          # defensive: never crash the pipeline
            return ExtractionEngineFailed(document_id, engine.engine_id,
                                          f"unexpected engine failure: {exc}")

        # Step 5: engine-contract validation (C2–C5) — fail-closed BEFORE persistence.
        validated = self._validate_and_seq(raw_fields, extraction_input.pages,
                                           engine.engine_id, document_id)
        if isinstance(validated, ExtractionEngineContractViolation):
            return validated
        fields = validated

        # Step 6: atomic durable commit (record + fields in one transaction).
        try:
            record = self._store.commit_extraction(
                document_id=document_id,
                capture_id=extraction_input.capture_id,
                capture_s1=extraction_input.capture_s1,
                capture_s1_algorithm_id=extraction_input.capture_s1_algorithm_id,
                engine_id=engine.engine_id,
                engine_schema_version=engine.schema_version,
                page_count=extraction_input.page_count,
                fields=fields,
            )
        except ExtractionDuplicate as exc:
            return ExtractionAlreadyExists(exc.extraction_id, document_id,
                                           engine.engine_id, engine.schema_version)
        except ExtractionPersistenceUnavailable as exc:
            # OD-X2: atomic commit → zero residue in every persistence failure; the
            # D-1/D-2 distinction collapses into "nothing recordable" for this layer.
            return ExtractionStorageUnavailable(str(exc))
        return ExtractionCompleted(record, tuple(fields))

    # ------------------------------------------------------------------
    # Engine-contract validation (C2–C5) + deterministic field_seq assignment
    # ------------------------------------------------------------------

    def _validate_and_seq(self, raw_fields: object, pages: Sequence[PageView],
                          engine_id: str,
                          document_id: str) -> object:
        """List[ExtractedField] on success, ExtractionEngineContractViolation on any
        contract breach (fail-closed; nothing persists)."""
        if not isinstance(raw_fields, (list, tuple)) or not all(
                isinstance(f, ExtractedField) for f in raw_fields):
            return ExtractionEngineContractViolation(
                document_id, engine_id, "engine output is not a sequence of ExtractedField")
        validated: List[ExtractedField] = []
        for seq, field in enumerate(raw_fields):
            detail = self._validate_field(field, pages)
            if detail is not None:
                return ExtractionEngineContractViolation(document_id, engine_id,
                                                         f"field {seq}: {detail}")
            validated.append(replace(field, field_seq=seq))   # pipeline owns the order
        return validated

    @staticmethod
    def _validate_field(field: ExtractedField, pages: Sequence[PageView]) -> Optional[str]:
        """Return None iff the field satisfies the engine contract; else the reason."""
        if field.provenance != Provenance.EXTRACTED:                       # C2
            return f"provenance must be EXTRACTED (got {field.provenance.value})"
        if not isinstance(field.field_name, str) or not field.field_name:
            return "field_name must be a non-empty string"
        if not isinstance(field.value_verbatim, str):
            return "value_verbatim must be a string"
        if not isinstance(field.value_encoding, str) or not field.value_encoding:
            return "value_encoding must be a non-empty string"
        span = field.span
        if not isinstance(span, SourceSpan):
            return "span must be a SourceSpan"
        idx = span.page_index
        if isinstance(idx, bool) or not isinstance(idx, int):
            return "span.page_index must be an integer"
        if not (0 <= idx < len(pages)):
            return f"span.page_index {idx} out of range (pages={len(pages)})"       # C3
        page = pages[idx]
        if span.page_fingerprint != page.page_fingerprint:                 # C3
            return "span.page_fingerprint does not match the claimed page"
        if not (0 <= span.byte_start <= span.byte_end <= page.byte_len):   # C3
            return (f"span offsets [{span.byte_start},{span.byte_end}) out of bounds "
                    f"for page {idx} (byte_len={page.byte_len})")
        content = bytes(page.content)
        try:                                                               # C4 verbatim binding
            span_value = content[span.byte_start:span.byte_end].decode(
                field.value_encoding)
        except LookupError:
            return f"unknown value_encoding: {field.value_encoding}"
        except UnicodeDecodeError:
            return "span bytes are not decodable with the declared value_encoding"
        if span_value != field.value_verbatim:
            return "value_verbatim is not the verbatim decoding of its span bytes"
        return None

    # ------------------------------------------------------------------
    # Verified read — VOR pattern bound to extraction records (SPEC §6)
    # ------------------------------------------------------------------

    def read_extraction(self, extraction_id: str) -> object:
        """Read an extraction record with a definitive integrity verdict computed INSIDE
        the read. Every outcome explicit: ExtractionReadSuccess | ExtractionReadIntegrity
        Failure (stored content NEVER delivered) | ExtractionReadRefused (unknown id) |
        ExtractionReadVerificationUnavailable (no verdict computable; Issue-Report)."""
        try:
            record = self._store.get_record(extraction_id)
        except ExtractionNotFound:
            return ExtractionReadRefused(None, "no such extraction record")
        try:
            fields = self._store.get_fields(extraction_id)
        except ExtractionNotFound:                        # pragma: no cover - defensive
            self._issues.append(f"extraction {extraction_id}: field rows vanished")
            return ExtractionReadVerificationUnavailable(
                extraction_id, "field rows missing — Issue Report required")

        if len(fields) != record.field_count:
            issue = (f"durable field set inconsistent "
                     f"(field_count={record.field_count}, rows={len(fields)})")
            self._issues.append(f"extraction {extraction_id}: {issue}")
            return ExtractionReadVerificationUnavailable(extraction_id,
                                                         issue + " — Issue Report required")

        recomputed = canonical_extraction_bytes(record, fields)
        verdict = self._s1.verify(recomputed, record.record_fingerprint,
                                  record.fingerprint_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            issue = (f"record verification unavailable: "
                     f"{verdict.reason or 'capability failure'}")
            self._issues.append(f"extraction {extraction_id}: {issue}")
            return ExtractionReadVerificationUnavailable(extraction_id,
                                                         issue + " — Issue Report required")
        if verdict.outcome == "FAILED":
            return ExtractionReadIntegrityFailure(extraction_id, NOTE_VERIFY_FAILED,
                                                  utc_now_iso())
        return ExtractionReadSuccess(record, tuple(fields), utc_now_iso())

    # ------------------------------------------------------------------
    # Traceability enumeration (document-scoped; consumed by WP-3.2 binding)
    # ------------------------------------------------------------------

    def extraction_ids_for_document(self, document_id: str) -> Tuple[str, ...]:
        """All extraction records for a document — deterministic order."""
        return tuple(self._store.find_for_document(document_id))

    # ------------------------------------------------------------------
    # Issue-report surface (minimal MVP hook, VOR §2 analog)
    # ------------------------------------------------------------------

    def issue_reports(self) -> list:
        """Accumulated Issue-Report items surfaced by this service instance."""
        return list(self._issues)
