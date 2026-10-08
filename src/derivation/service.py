"""Derivation service — verified Normalization output → declared formula → exact DERIVED
value (WP-4.2 MVP).

Binding basis: SPEC-WP42-DER §2/§5/§8/§10; SPEC-WP41-NORM §2 analog (the verified
normalization read is the ONLY sanctioned value path — this service never touches any
store directly and never re-reads raw artifacts); D-01 (DERIVED produced verbatim;
UNRESOLVED never created/assigned/inferred/resolved); D-08 (no rounding — a non-exact
result is refused, never rounded); D-09 (registry is a constructor-injected seam).

  derive(normalization_id, formula_id, formula_version):
    registry lookup → verified normalization read (VOR path, frozen WP-4.1 service) →
    verified evidence-binding read (frozen WP-3.2, read-only — evidence-bearing-ness) →
    INV-D-1:1 pre-check → declared-slot resolution (singleton; ambiguity/missing →
    explicit DEFERRED) → output-present gate → exact arithmetic (non-terminating DIV →
    explicit DEFERRED, never rounded) → atomic durable commit.

  read_derivation(derivation_id):
    VOR-pattern verified read — record fingerprint recomputed over the durable rows
    INSIDE the read; content delivered only on the same-read VALID verdict.

  trace_derivation(derivation_id):
    whole-chain provenance walk (SPEC §10) — every link re-verified inside the walk
    through frozen verified reads; pointers and verdicts only, never copied values.

The service owns orchestration only; every durable effect goes through the store; every
fingerprint goes through the reused capture S1 capability (sha256-v1). No canonical
mapping, no association decision, no business datum is produced anywhere.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from capture import S1Service
from extraction import (
    BindingReadIntegrityFailure,
    BindingReadRefused,
    BindingReadSuccess,
    BindingReadVerificationUnavailable,
    ExtractionReadIntegrityFailure,
    ExtractionReadRefused,
    ExtractionReadSuccess,
    ExtractionReadVerificationUnavailable,
    ExtractionService,
    ExtractionBindingStore,
    ExtractionEvidenceBinder,
)
from fractions import Fraction

from normalization import (
    NormalizationReadIntegrityFailure,
    NormalizationReadRefused,
    NormalizationReadSuccess,
    NormalizationReadVerificationUnavailable,
    NormalizationService,
    NormalizationStatus,
)
from reconstruction import (
    DocumentReadIntegrityFailure,
    DocumentReadRefused,
    DocumentReadSuccess,
    DocumentReadVerificationUnavailable,
    ReconstructionService,
)

from .arithmetic import NonExactResult, evaluate, parse_canonical_decimal, \
    to_exact_decimal_string
from .formulas import FormulaInputRef, FormulaOp
from .model import (
    NOTE_VERIFY_FAILED,
    REASON_INPUT_AMBIGUOUS,
    REASON_INPUT_MISSING,
    REASON_NON_EXACT_RESULT,
    REASON_OUTPUT_PRESENT,
    DerivationAlreadyExists,
    DerivationCompleted,
    DerivationDeferred,
    DerivationDuplicate,
    DerivationFormulaNotRegistered,
    DerivationInputRef,
    DerivationNotFound,
    DerivationPersistenceUnavailable,
    DerivationReadIntegrityFailure,
    DerivationReadRefused,
    DerivationReadSuccess,
    DerivationReadVerificationUnavailable,
    DerivationRecord,
    DerivationSourceIntegrityFailure,
    DerivationSourceRefused,
    DerivationSourceUnavailable,
    DerivationStorageUnavailable,
    DerivationTraceIntegrityFailure,
    DerivationTraceRefused,
    DerivationTraceSuccess,
    DerivationTraceVerificationUnavailable,
    utc_now_iso,
)
from .formulas import DerivationFormulaRegistry
from .store import DerivationStore, canonical_derivation_bytes


class DerivationService:
    """The derivation entry point: verified NORMALIZED inputs → declared formula →
    durable exact DERIVED value with complete provenance."""

    def __init__(self, store: DerivationStore, normalization: NormalizationService,
                 extraction: ExtractionService, binder: ExtractionEvidenceBinder,
                 reconstruction: ReconstructionService,
                 registry: DerivationFormulaRegistry, s1: S1Service) -> None:
        self._store = store
        self._normalization = normalization
        self._extraction = extraction
        self._binder = binder
        self._reconstruction = reconstruction
        self._registry = registry
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Derive — verified normalization → declared formula → durable (SPEC §2, §5, §8)
    # ------------------------------------------------------------------

    def derive(self, normalization_id: str, formula_id: str,
               formula_version: str) -> object:
        """Derive one exact value from one verified normalization with one registered
        formula version. Outcome is exactly one explicit type — never silent:
          DerivationCompleted | DerivationAlreadyExists (INV-D-1:1 replay) |
          DerivationFormulaNotRegistered | DerivationDeferred (NOT_DERIVABLE — nothing
          persisted) | DerivationSourceIntegrityFailure | DerivationSourceRefused |
          DerivationSourceUnavailable | DerivationStorageUnavailable.
        """
        formula = self._registry.get(formula_id, formula_version)
        if formula is None:
            return DerivationFormulaNotRegistered(normalization_id, formula_id,
                                                  formula_version)

        # Step 1: verified source read — the ONLY sanctioned value path (VOR: verdict
        # computed inside the read; FAILED never delivers content).
        read = self._normalization.read_normalization(normalization_id)
        if isinstance(read, NormalizationReadIntegrityFailure):
            return DerivationSourceIntegrityFailure(normalization_id, read.reason)
        if isinstance(read, NormalizationReadRefused):
            return DerivationSourceRefused(normalization_id,
                                           "no such normalization record")
        if isinstance(read, NormalizationReadVerificationUnavailable):
            self._issues.append(
                f"derivation on {normalization_id}: {read.issue_report}")
            return DerivationSourceUnavailable(normalization_id, read.issue_report)
        norm_record, norm_fields = read.record, read.fields

        # Step 2: evidence-bearing-ness — the source extraction must hold a healthy
        # WP-3.2 binding (frozen verified read; read-only; fail-closed).
        binding = self._binder.read_binding(norm_record.extraction_id)
        if isinstance(binding, BindingReadIntegrityFailure):
            return DerivationSourceIntegrityFailure(
                normalization_id,
                f"evidence binding verify FAILED at link '{binding.link.value}': "
                f"{binding.reason}")
        if isinstance(binding, BindingReadRefused):
            return DerivationSourceRefused(
                normalization_id,
                "no healthy evidence binding for the source extraction — refused "
                "(fail-closed)")
        if isinstance(binding, BindingReadVerificationUnavailable):
            self._issues.append(
                f"derivation on {normalization_id}: {binding.issue_report}")
            return DerivationSourceUnavailable(normalization_id, binding.issue_report)

        # Step 3: INV-D-1:1 pre-check (the atomic commit backstops races — UAC-lite).
        existing = self._store.find_by_triple(normalization_id, formula_id,
                                              formula_version)
        if existing is not None:
            return DerivationAlreadyExists(existing, normalization_id, formula_id,
                                           formula_version)

        # Step 4: declared-slot resolution — singleton per slot, NORMALIZED only
        # (SPEC §5: DEFERRED/REJECTED fields are never candidates; >1 candidates is
        # ambiguity, never an association decision).
        resolved: Dict[str, object] = {}
        for slot_index, slot in enumerate(formula.inputs):
            candidates = [f for f in norm_fields
                          if f.source_field_name == slot.field_name
                          and f.status is NormalizationStatus.NORMALIZED]
            if len(candidates) == 1:
                resolved[slot.slot_name] = candidates[0]
                continue
            if len(candidates) == 0:
                present = [f for f in norm_fields
                           if f.source_field_name == slot.field_name]
                if present:
                    detail = (f"slot '{slot.slot_name}' ({slot.field_name}): "
                              f"{len(present)} field(s) exist but none is NORMALIZED "
                              f"(status: {', '.join(sorted({f.status.value for f in present}))}) "
                              f"— a value outside the declared grammar never feeds arithmetic")
                else:
                    detail = (f"slot '{slot.slot_name}' ({slot.field_name}): no such "
                              f"field in the source normalization record")
                return DerivationDeferred(normalization_id, formula_id, formula_version,
                                          REASON_INPUT_MISSING, detail)
            return DerivationDeferred(normalization_id, formula_id, formula_version,
                                      REASON_INPUT_AMBIGUOUS,
                                      f"slot '{slot.slot_name}' ({slot.field_name}): "
                                      f"{len(candidates)} NORMALIZED candidates "
                                      f"(field_seqs {sorted(f.field_seq for f in candidates)}) — "
                                      f"association decisions belong to the Canonicalization Gate")

        # Step 5: output-present gate — a derived value must never shadow a read field
        # (any status), and must never paper over a field whose normalization failed.
        clashing = [f for f in norm_fields
                    if f.source_field_name == formula.output_field_name]
        if clashing:
            statuses = ", ".join(sorted({f.status.value for f in clashing}))
            return DerivationDeferred(normalization_id, formula_id, formula_version,
                                      REASON_OUTPUT_PRESENT,
                                      f"output field '{formula.output_field_name}' already "
                                      f"carried by the source record ({statuses}) — derived "
                                      f"values never shadow read fields")

        # Step 6: exact arithmetic over canonical decimal strings (SPEC §4) — a
        # non-canonical NORMALIZED value is refused fail-closed (never parsed
        # leniently); a non-terminating DIV is refused (never rounded, D-08).
        values: Dict[str, Fraction] = {}
        for slot in formula.inputs:
            field = resolved[slot.slot_name]
            parsed = parse_canonical_decimal(field.normalized_value or "")
            if parsed is None:
                return DerivationDeferred(normalization_id, formula_id, formula_version,
                                          REASON_INPUT_MISSING,
                                          f"slot '{slot.slot_name}' ({slot.field_name}): "
                                          f"normalized value is outside the declared "
                                          f"canonical decimal grammar — refused, never "
                                          f"parsed leniently")
            values[slot.slot_name] = parsed
        try:
            exact = self._evaluate(formula.expression, values)
        except NonExactResult as exc:
            return DerivationDeferred(normalization_id, formula_id, formula_version,
                                      REASON_NON_EXACT_RESULT, str(exc))
        output_value = to_exact_decimal_string(exact)

        # Step 7: durable input POINTERS + atomic commit (record + refs in one txn).
        refs = tuple(
            DerivationInputRef(
                input_slot=slot_index,
                slot_name=slot.slot_name,
                field_name=slot.field_name,
                source_normalization_id=normalization_id,
                field_seq=resolved[slot.slot_name].field_seq,
                source_extraction_id=norm_record.extraction_id,
            )
            for slot_index, slot in enumerate(formula.inputs)
        )
        try:
            saved = self._store.commit_derivation(
                normalization_id=normalization_id,
                extraction_id=norm_record.extraction_id,
                document_id=norm_record.document_id,
                capture_id=norm_record.capture_id,
                capture_s1=norm_record.capture_s1,
                capture_s1_algorithm_id=norm_record.capture_s1_algorithm_id,
                ruleset_id=norm_record.ruleset_id,
                ruleset_version=norm_record.ruleset_version,
                formula_id=formula_id,
                formula_version=formula_version,
                formula_fingerprint=self._registry.fingerprint_of(formula_id,
                                                                  formula_version) or "",
                formula_fingerprint_algorithm_id="sha256-v1",
                output_field_name=formula.output_field_name,
                output_value=output_value,
                inputs=refs,
            )
        except DerivationDuplicate as exc:
            return DerivationAlreadyExists(exc.derivation_id, normalization_id,
                                           formula_id, formula_version)
        except DerivationPersistenceUnavailable as exc:
            # OD-D2: atomic commit → zero residue in every persistence failure.
            return DerivationStorageUnavailable(str(exc))
        return DerivationCompleted(saved, refs)

    @staticmethod
    def _evaluate(node: object, values: Dict[str, Fraction]) -> Fraction:
        """Evaluate the declared expression tree over exact operands (pure recursion
        over declaration data — there is no code to execute here, by construction)."""
        if isinstance(node, FormulaInputRef):
            return values[node.slot_name]
        if isinstance(node, FormulaOp):
            return evaluate(node.op, tuple(
                DerivationService._evaluate(child, values) for child in node.args))
        raise TypeError(f"non-declaration payload inside expression: {type(node)!r}")

    # ------------------------------------------------------------------
    # Verified read — VOR pattern bound to derivation records (SPEC §8)
    # ------------------------------------------------------------------

    def read_derivation(self, derivation_id: str) -> object:
        """Read a derivation record with a definitive integrity verdict computed INSIDE
        the read. Every outcome explicit: DerivationReadSuccess |
        DerivationReadIntegrityFailure (stored content NEVER delivered) |
        DerivationReadRefused (unknown id) | DerivationReadVerificationUnavailable
        (no verdict computable; Issue-Report)."""
        try:
            record = self._store.get_record(derivation_id)
        except DerivationNotFound:
            return DerivationReadRefused(None, "no such derivation record")
        try:
            inputs = self._store.get_inputs(derivation_id)
        except DerivationNotFound:                     # pragma: no cover - defensive
            self._issues.append(f"derivation {derivation_id}: input rows vanished")
            return DerivationReadVerificationUnavailable(
                derivation_id, "input rows missing — Issue Report required")

        if len(inputs) != record.input_count:
            issue = (f"durable input set inconsistent "
                     f"(input_count={record.input_count}, rows={len(inputs)})")
            self._issues.append(f"derivation {derivation_id}: {issue}")
            return DerivationReadVerificationUnavailable(
                derivation_id, issue + " — Issue Report required")

        recomputed = canonical_derivation_bytes(record, inputs)
        verdict = self._s1.verify(recomputed, record.record_fingerprint,
                                  record.fingerprint_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            issue = (f"record verification unavailable: "
                     f"{verdict.reason or 'capability failure'}")
            self._issues.append(f"derivation {derivation_id}: {issue}")
            return DerivationReadVerificationUnavailable(
                derivation_id, issue + " — Issue Report required")
        if verdict.outcome == "FAILED":
            return DerivationReadIntegrityFailure(derivation_id, NOTE_VERIFY_FAILED,
                                                  utc_now_iso())
        return DerivationReadSuccess(record, tuple(inputs), utc_now_iso())

    # ------------------------------------------------------------------
    # Traceability walk — derivation → normalization → extraction → binding →
    # document/page/span → Capture S1 (SPEC §10; pointers only, everything re-verified)
    # ------------------------------------------------------------------

    def trace_derivation(self, derivation_id: str) -> object:
        """Walk the full provenance chain with verified reads on EVERY link inside this
        one call. Deliverable: ordered coarse link verdicts (no source values copied)."""
        head = self.read_derivation(derivation_id)
        if isinstance(head, DerivationReadIntegrityFailure):
            return DerivationTraceIntegrityFailure(derivation_id, "derivation",
                                                   head.reason)
        if isinstance(head, DerivationReadRefused):
            return DerivationTraceRefused(derivation_id, head.detail)
        if isinstance(head, DerivationReadVerificationUnavailable):
            self._issues.append(f"trace {derivation_id}: {head.issue_report}")
            return DerivationTraceVerificationUnavailable(derivation_id,
                                                          head.issue_report)
        record, input_refs = head.record, head.inputs

        chain: List[str] = [
            f"derivation: DERIVED {record.output_field_name}={record.output_value} "
            f"formula={record.formula_id}/{record.formula_version} "
            f"formula_fp={record.formula_fingerprint[:12]}… inputs={record.input_count} "
            f"provenance={record.output_provenance}",
        ]

        norm_ids = {ref.source_normalization_id for ref in input_refs}
        if norm_ids != {record.normalization_id}:
            return DerivationTraceIntegrityFailure(
                derivation_id, "derivation",
                "input pointers leave the source normalization record "
                "(cross-record input) — chain refused")
        if {ref.source_extraction_id for ref in input_refs} != {record.extraction_id}:
            return DerivationTraceIntegrityFailure(
                derivation_id, "derivation",
                "input pointers leave the source extraction record — chain refused")

        # link: normalization (WP-4.1 verified read)
        norm_read = self._normalization.read_normalization(record.normalization_id)
        if isinstance(norm_read, NormalizationReadIntegrityFailure):
            return DerivationTraceIntegrityFailure(derivation_id, "normalization",
                                                   norm_read.reason)
        if isinstance(norm_read, NormalizationReadRefused):
            return DerivationTraceRefused(derivation_id, "normalization record missing")
        if isinstance(norm_read, NormalizationReadVerificationUnavailable):
            self._issues.append(f"trace {derivation_id}: {norm_read.issue_report}")
            return DerivationTraceVerificationUnavailable(derivation_id,
                                                          norm_read.issue_report)
        norm_record, norm_fields = norm_read.record, norm_read.fields
        if norm_record.extraction_id != record.extraction_id:
            return DerivationTraceIntegrityFailure(derivation_id, "normalization",
                                                   "extraction linkage drift")
        chain.append(
            f"normalization: OK ruleset={norm_record.ruleset_id}/"
            f"{norm_record.ruleset_version} fields={norm_record.field_count}")

        # link: extraction (WP-3.1 verified read)
        ext_read = self._extraction.read_extraction(record.extraction_id)
        if isinstance(ext_read, ExtractionReadIntegrityFailure):
            return DerivationTraceIntegrityFailure(derivation_id, "extraction",
                                                   ext_read.reason)
        if isinstance(ext_read, ExtractionReadRefused):
            return DerivationTraceRefused(derivation_id, "extraction record missing")
        if isinstance(ext_read, ExtractionReadVerificationUnavailable):
            self._issues.append(f"trace {derivation_id}: {ext_read.issue_report}")
            return DerivationTraceVerificationUnavailable(derivation_id,
                                                          ext_read.issue_report)
        extracted_by_seq = {f.field_seq: f for f in ext_read.fields}
        chain.append(
            f"extraction: OK engine={ext_read.extraction.engine_id}/"
            f"{ext_read.extraction.engine_schema_version} "
            f"fields={ext_read.extraction.field_count}")

        # link: evidence binding (WP-3.2 verified read — five links, fresh)
        binding_read = self._binder.read_binding(record.extraction_id)
        if isinstance(binding_read, BindingReadIntegrityFailure):
            return DerivationTraceIntegrityFailure(
                derivation_id, "binding",
                f"link '{binding_read.link.value}': {binding_read.reason}")
        if isinstance(binding_read, BindingReadRefused):
            return DerivationTraceRefused(derivation_id, "evidence binding missing")
        if isinstance(binding_read, BindingReadVerificationUnavailable):
            self._issues.append(f"trace {derivation_id}: {binding_read.issue_report}")
            return DerivationTraceVerificationUnavailable(derivation_id,
                                                          binding_read.issue_report)
        entries_by_seq = {e.field_seq: e for e in binding_read.entries}
        chain.append(
            f"binding: OK binding_id={binding_read.binding.binding_id[:12]}… "
            f"entries={binding_read.binding.field_binding_count}")

        # link: document/page/span (WP-2.1 verified read; span slice decodes to verbatim)
        doc_read = self._reconstruction.read_document(record.document_id)
        if isinstance(doc_read, DocumentReadIntegrityFailure):
            return DerivationTraceIntegrityFailure(derivation_id, "document",
                                                   doc_read.reason)
        if isinstance(doc_read, DocumentReadRefused):
            return DerivationTraceRefused(derivation_id, "document record missing")
        if isinstance(doc_read, DocumentReadVerificationUnavailable):
            self._issues.append(f"trace {derivation_id}: {doc_read.issue_report}")
            return DerivationTraceVerificationUnavailable(derivation_id,
                                                          doc_read.issue_report)
        chain.append(
            f"document: OK pages={len(doc_read.pages)} "
            f"capture_s1={doc_read.capture_s1[:12]}…")

        for ref in input_refs:
            field = next((f for f in norm_fields if f.field_seq == ref.field_seq), None)
            if field is None or field.status is not NormalizationStatus.NORMALIZED \
                    or field.source_field_name != ref.field_name:
                return DerivationTraceIntegrityFailure(
                    derivation_id, "normalization",
                    f"input slot '{ref.slot_name}' points at field_seq {ref.field_seq} "
                    f"which is not a NORMALIZED '{ref.field_name}' — chain refused")
            extracted = extracted_by_seq.get(ref.field_seq)
            if extracted is None or extracted.value_verbatim is None:
                return DerivationTraceIntegrityFailure(
                    derivation_id, "extraction",
                    f"field_seq {ref.field_seq} missing from the extraction record")
            entry = entries_by_seq.get(ref.field_seq)
            if entry is None or entry.page_index >= len(doc_read.pages):
                return DerivationTraceIntegrityFailure(
                    derivation_id, "binding",
                    f"field_seq {ref.field_seq} has no valid binding entry")
            page = doc_read.pages[entry.page_index]
            if entry.page_fingerprint != page.page_fingerprint:
                return DerivationTraceIntegrityFailure(
                    derivation_id, "document",
                    f"page fingerprint drift at field_seq {ref.field_seq}")
            verbatim = bytes(page.content)[entry.byte_start:entry.byte_end] \
                .decode(extracted.value_encoding)
            if verbatim != extracted.value_verbatim:
                return DerivationTraceIntegrityFailure(
                    derivation_id, "document",
                    f"span slice no longer decodes to the verbatim value "
                    f"(field_seq {ref.field_seq})")
            chain.append(
                f"input[{ref.input_slot}] {ref.slot_name}={ref.field_name}: "
                f"normalization field_seq={ref.field_seq} → extraction verbatim → "
                f"page {entry.page_index} [{entry.byte_start},{entry.byte_end}) → OK")

        # link: capture S1 (linkage carried by the record and re-checked here)
        if doc_read.capture_id != record.capture_id \
                or doc_read.capture_s1 != record.capture_s1:
            return DerivationTraceIntegrityFailure(derivation_id, "derivation",
                                                   "capture linkage drift")
        chain.append(
            f"capture: OK capture_id={record.capture_id[:12]}… "
            f"s1={record.capture_s1[:12]}… ({record.capture_s1_algorithm_id})")
        return DerivationTraceSuccess(derivation_id, tuple(chain))

    # ------------------------------------------------------------------
    # Traceability enumeration (normalization-scoped; Canonicalization consumer)
    # ------------------------------------------------------------------

    def derivations_for_normalization(self, normalization_id: str) -> Tuple[str, ...]:
        """All derivation records for a normalization — deterministic order."""
        return tuple(self._store.find_for_normalization(normalization_id))

    # ------------------------------------------------------------------
    # Issue-report surface (minimal MVP hook, VOR §2 analog)
    # ------------------------------------------------------------------

    def issue_reports(self) -> list:
        """Accumulated Issue-Report items surfaced by this service instance."""
        return list(self._issues)
