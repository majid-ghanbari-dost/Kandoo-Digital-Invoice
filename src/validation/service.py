"""Validation service — verified pipeline values → declared R1/R2 rules → explicit,
durable, auditable verdicts (WP-5.1 MVP).

Binding basis: SPEC-WP51-VAL §2/§4/§5/§8/§10; SPEC-WP42-DER §2 analog (verified reads
are the ONLY sanctioned value paths — NORMALIZED via frozen WP-4.1, DERIVED via the
WP-4.2 service; this service never touches any store directly and never re-reads raw
artifacts); D-01 (UNRESOLVED never created/assigned/inferred/resolved here); D-08
(R2 tolerance/rounding parametric, injected, no fixed values; mismatch → REVIEW is a
WP-5.2 mapping, not implemented here); D-09 (registry is a constructor-injected seam).

  validate(normalization_id, rule_id, rule_version):
    registry lookup → verified normalization read (VOR path, frozen WP-4.1 service) →
    verified evidence-binding read (frozen WP-3.2, read-only — evidence gate) →
    INV-V-1:1 pre-check → declared-slot resolution (NORMALIZED singleton via WP-4.1
    fields; DERIVED singleton via WP-4.2 verified reads; missing/ambiguous → explicit
    durable DEFERRED) → exact evaluation per declared rule type (R1 exact only;
    R2 tolerated or explicitly rounded — never implicitly) → atomic durable commit.

  read_validation(validation_id):
    VOR-pattern verified read — record fingerprint recomputed over the durable rows
    INSIDE the read; content delivered only on the same-read VALID verdict.

  trace_validation(validation_id):
    whole-chain provenance walk (SPEC §10) — every link re-verified inside the walk;
    DERIVED inputs are walked through the WP-4.2 service's own whole-chain trace, so
    P4.2 provenance is consumed, never bypassed and never destroyed.

The service owns orchestration only; every durable effect goes through the store; every
fingerprint goes through the reused capture S1 capability (sha256-v1). No canonical
mapping, no association decision, no business datum, no new value is produced anywhere.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Dict, List, Optional, Tuple

from capture import S1Service
from derivation import (
    DerivationReadIntegrityFailure,
    DerivationReadRefused,
    DerivationReadSuccess,
    DerivationReadVerificationUnavailable,
    DerivationService,
    DerivationTraceSuccess,
)
from derivation.arithmetic import NonExactResult, evaluate, is_terminating_decimal, \
    parse_canonical_decimal, to_exact_decimal_string
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
    ExtractionEvidenceBinder,
)
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

from .model import (
    NOTE_VERIFY_FAILED,
    OUTCOME_DEFERRED,
    OUTCOME_INVALID,
    OUTCOME_VALID,
    REASON_ABSENT,
    REASON_AMBIGUOUS_INPUT,
    REASON_EXACT_MATCH,
    REASON_INSUFFICIENT_INPUT,
    REASON_MISMATCH,
    REASON_MISMATCH_AFTER_ROUNDING,
    REASON_MISMATCH_BEYOND_TOLERANCE,
    REASON_NON_EXACT_INTERMEDIATE,
    REASON_PRESENT_NOT_USABLE,
    REASON_ROUNDED_MATCH,
    REASON_WITHIN_TOLERANCE,
    VALUE_ORIGIN_DERIVED,
    VALUE_ORIGIN_NORMALIZED,
    ValidationAlreadyExists,
    ValidationCompleted,
    ValidationDuplicate,
    ValidationInputRef,
    ValidationNotFound,
    ValidationPersistenceUnavailable,
    ValidationReadIntegrityFailure,
    ValidationReadRefused,
    ValidationReadSuccess,
    ValidationReadVerificationUnavailable,
    ValidationRuleNotRegistered,
    ValidationSourceIntegrityFailure,
    ValidationSourceRefused,
    ValidationSourceUnavailable,
    ValidationStorageUnavailable,
    ValidationTraceIntegrityFailure,
    ValidationTraceRefused,
    ValidationTraceSuccess,
    ValidationTraceVerificationUnavailable,
    utc_now_iso,
)
from .rounding import exact_value_string, round_exact, to_fixed_decimal_string
from .rules import RuleExprOp, RuleSlotRef, ValidationRule
from .store import ValidationStore, canonical_validation_bytes


class _DerivedSourceFailure(Exception):
    """Internal control-flow signal: a referenced derivation source failed its
    verified read while resolving a DERIVED slot. Converted by validate() into the
    explicit ValidationSourceIntegrityFailure / ValidationSourceUnavailable outcome
    (fail-closed — never swallowed, never treated as a rule verdict)."""

    def __init__(self, kind: str, reason: str) -> None:
        super().__init__(reason)
        self.kind = kind            # "integrity" | "unavailable"
        self.reason = reason


class ValidationService:
    """The R1/R2 validation entry point: verified pipeline values → declared rules →
    durable explicit verdicts with complete provenance."""

    def __init__(self, store: ValidationStore, normalization: NormalizationService,
                 extraction: ExtractionService, binder: ExtractionEvidenceBinder,
                 reconstruction: ReconstructionService, derivations: DerivationService,
                 registry, s1: S1Service) -> None:
        self._store = store
        self._normalization = normalization
        self._extraction = extraction
        self._binder = binder
        self._reconstruction = reconstruction
        self._derivations = derivations
        self._registry = registry
        self._s1 = s1
        self._issues: List[str] = []   # Issue-Report surface — operator-facing, in-memory (MVP)

    # ------------------------------------------------------------------
    # Validate — verified sources → declared rule → durable verdict (SPEC §2, §5, §8)
    # ------------------------------------------------------------------

    def validate(self, normalization_id: str, rule_id: str,
                 rule_version: str) -> object:
        """Evaluate one declared rule version over one verified validation scope.
        Outcome is exactly one explicit type — never silent:
          ValidationCompleted | ValidationAlreadyExists (INV-V-1:1 replay) |
          ValidationRuleNotRegistered | ValidationSourceIntegrityFailure |
          ValidationSourceRefused | ValidationSourceUnavailable |
          ValidationStorageUnavailable. The rule verdict itself (VALID / INVALID /
          DEFERRED) travels INSIDE ValidationCompleted — a DEFERRED rule outcome is a
          completed, durably recorded evaluation (SPEC §5), never a silent refusal.
        """
        rule = self._registry.get(rule_id, rule_version)
        if rule is None:
            return ValidationRuleNotRegistered(normalization_id, rule_id, rule_version)

        # Step 1: verified source read — the ONLY sanctioned NORMALIZED value path
        # (VOR: verdict computed inside the read; FAILED never delivers content).
        read = self._normalization.read_normalization(normalization_id)
        if isinstance(read, NormalizationReadIntegrityFailure):
            return ValidationSourceIntegrityFailure(normalization_id, read.reason)
        if isinstance(read, NormalizationReadRefused):
            return ValidationSourceRefused(normalization_id,
                                           "no such normalization record")
        if isinstance(read, NormalizationReadVerificationUnavailable):
            self._issues.append(
                f"validation on {normalization_id}: {read.issue_report}")
            return ValidationSourceUnavailable(normalization_id, read.issue_report)
        norm_record, norm_fields = read.record, read.fields

        # Step 2: evidence gate — the source extraction must hold a healthy WP-3.2
        # binding (frozen verified read; read-only; fail-closed).
        binding = self._binder.read_binding(norm_record.extraction_id)
        if isinstance(binding, BindingReadIntegrityFailure):
            return ValidationSourceIntegrityFailure(
                normalization_id,
                f"evidence binding verify FAILED at link '{binding.link.value}': "
                f"{binding.reason}")
        if isinstance(binding, BindingReadRefused):
            return ValidationSourceRefused(
                normalization_id,
                "no healthy evidence binding for the source extraction — refused "
                "(fail-closed)")
        if isinstance(binding, BindingReadVerificationUnavailable):
            self._issues.append(
                f"validation on {normalization_id}: {binding.issue_report}")
            return ValidationSourceUnavailable(normalization_id, binding.issue_report)

        # Step 3: INV-V-1:1 pre-check (the atomic commit backstops races — UAC-lite).
        existing = self._store.find_by_triple(normalization_id, rule_id, rule_version)
        if existing is not None:
            return ValidationAlreadyExists(existing, normalization_id, rule_id,
                                           rule_version)

        # Step 4: declared evaluation per rule type (SPEC §4/§5) → verdict payload.
        # A referenced derivation source that fails its verified read is a layer
        # failure (fail-closed) — surfaced explicitly, never a rule verdict.
        try:
            verdict = self._evaluate_rule(rule, normalization_id, norm_record,
                                          norm_fields)
        except _DerivedSourceFailure as exc:
            if exc.kind == "integrity":
                return ValidationSourceIntegrityFailure(normalization_id, exc.reason)
            self._issues.append(f"validation on {normalization_id}: {exc.reason}")
            return ValidationSourceUnavailable(normalization_id, exc.reason)
        (
            outcome, reason, detail, rounding_applied,
            rounding_precision, rounding_mode,
            rounding_input_value, rounding_output_value, refs,
        ) = verdict

        # Step 5: durable input POINTERS + atomic commit (record + refs in one txn).
        try:
            saved = self._store.commit_validation(
                normalization_id=normalization_id,
                extraction_id=norm_record.extraction_id,
                document_id=norm_record.document_id,
                capture_id=norm_record.capture_id,
                capture_s1=norm_record.capture_s1,
                capture_s1_algorithm_id=norm_record.capture_s1_algorithm_id,
                ruleset_id=norm_record.ruleset_id,
                ruleset_version=norm_record.ruleset_version,
                rule_id=rule_id,
                rule_version=rule_version,
                rule_kind=rule.rule_kind,
                rule_type=rule.rule_type,
                rule_fingerprint=self._registry.fingerprint_of(rule_id,
                                                               rule_version) or "",
                rule_fingerprint_algorithm_id="sha256-v1",
                outcome=outcome,
                outcome_reason=reason,
                outcome_detail=detail,
                rounding_applied=rounding_applied,
                rounding_precision=rounding_precision,
                rounding_mode=rounding_mode,
                rounding_input_value=rounding_input_value,
                rounding_output_value=rounding_output_value,
                inputs=refs,
            )
        except ValidationDuplicate as exc:
            return ValidationAlreadyExists(exc.validation_id, normalization_id,
                                           rule_id, rule_version)
        except ValidationPersistenceUnavailable as exc:
            # OD-V2: atomic commit → zero residue in every persistence failure.
            return ValidationStorageUnavailable(str(exc))
        return ValidationCompleted(saved, tuple(refs))

    # ------------------------------------------------------------------
    # Declared evaluation (SPEC §4/§5 — pure decision logic, no persistence)
    # ------------------------------------------------------------------

    def _evaluate_rule(self, rule: ValidationRule, normalization_id: str,
                       norm_record, norm_fields) -> Tuple[
            str, str, str, int, Optional[int], Optional[str], Optional[str],
            Optional[str], List[ValidationInputRef]]:
        """Evaluate the declared rule → (outcome, reason, detail, rounding_applied,
        rounding_precision, rounding_mode, rounding_input_value,
        rounding_output_value, input_refs)."""
        if rule.rule_type == "presence":
            return self._evaluate_presence(rule, normalization_id, norm_record,
                                           norm_fields)
        return self._evaluate_comparison(rule, normalization_id, norm_record,
                                         norm_fields)

    # -- R1 presence -------------------------------------------------------

    def _evaluate_presence(self, rule: ValidationRule, normalization_id: str,
                           norm_record, norm_fields) -> Tuple[
            str, str, str, int, Optional[int], Optional[str], Optional[str],
            Optional[str], List[ValidationInputRef]]:
        slot = rule.inputs[0]
        if slot.origin == "normalized":
            candidates = sorted(
                (f for f in norm_fields
                 if f.source_field_name == slot.field_name
                 and f.status is NormalizationStatus.NORMALIZED),
                key=lambda f: f.field_seq)
            if candidates:
                field = candidates[0]
                detail = (f"field '{slot.field_name}' present as NORMALIZED "
                          f"({len(candidates)} candidate(s))")
                return (OUTCOME_VALID, REASON_EXACT_MATCH, detail, 0, None, None,
                        None, None,
                        [self._normalized_ref(0, slot, normalization_id,
                                              norm_record, field)])
            present_other = [f for f in norm_fields
                             if f.source_field_name == slot.field_name]
            if present_other:
                statuses = ", ".join(sorted({f.status.value for f in present_other}))
                detail = (f"field '{slot.field_name}' present in the source record "
                          f"but with no usable value (status: {statuses}) — a value "
                          f"outside the declared grammar never validates")
                return (OUTCOME_INVALID, REASON_PRESENT_NOT_USABLE, detail, 0,
                        None, None, None, None, [])
            detail = (f"field '{slot.field_name}' absent from the source "
                      f"normalization record")
            return (OUTCOME_INVALID, REASON_ABSENT, detail, 0, None, None, None,
                    None, [])
        # origin == "derived"
        candidates, failure = self._derivation_candidates(normalization_id,
                                                          slot.field_name)
        if failure is not None:
            raise _DerivedSourceFailure(failure[0], failure[1])
        if candidates:
            derivation_id, _, extraction_id = candidates[0]
            detail = (f"DERIVED output '{slot.field_name}' present "
                      f"({len(candidates)} derivation record(s))")
            ref = ValidationInputRef(
                input_slot=0, slot_name=slot.slot_name,
                field_name=slot.field_name, value_origin=VALUE_ORIGIN_DERIVED,
                source_normalization_id=normalization_id,
                source_extraction_id=extraction_id,
                source_field_seq=None, source_derivation_id=derivation_id)
            return (OUTCOME_VALID, REASON_EXACT_MATCH, detail, 0, None, None, None,
                    None, [ref])
        detail = (f"no derivation record produces '{slot.field_name}' — validation "
                  f"never triggers derivation; run the declared derivation first")
        return (OUTCOME_INVALID, REASON_ABSENT, detail, 0, None, None, None, None, [])

    # -- comparison rules ----------------------------------------------------

    def _evaluate_comparison(self, rule: ValidationRule, normalization_id: str,
                             norm_record, norm_fields) -> Tuple[
            str, str, str, int, Optional[int], Optional[str], Optional[str],
            Optional[str], List[ValidationInputRef]]:
        """Shared machinery for exact-consistency / tolerated-equality /
        rounded-equality: resolve every declared slot, then compare under the
        declared semantics (SPEC §4). Unresolved slots → durable DEFERRED with the
        resolved pointers kept (audit-visible partial evidence)."""
        resolved: Dict[str, Fraction] = {}
        refs: List[ValidationInputRef] = []
        missing: List[str] = []
        ambiguous: List[str] = []

        for slot_index, slot in enumerate(rule.inputs):
            if slot.origin == "normalized":
                candidates = [f for f in norm_fields
                              if f.source_field_name == slot.field_name
                              and f.status is NormalizationStatus.NORMALIZED]
                if len(candidates) == 1:
                    field = candidates[0]
                    parsed = parse_canonical_decimal(field.normalized_value or "")
                    if parsed is None:
                        missing.append(
                            f"slot '{slot.slot_name}' ({slot.field_name}): normalized "
                            f"value is outside the declared canonical decimal grammar "
                            f"— refused, never parsed leniently")
                        continue
                    resolved[slot.slot_name] = parsed
                    refs.append(self._normalized_ref(slot_index, slot,
                                                     normalization_id, norm_record,
                                                     field))
                    continue
                if len(candidates) == 0:
                    present = [f for f in norm_fields
                               if f.source_field_name == slot.field_name]
                    if present:
                        statuses = ", ".join(sorted(
                            {f.status.value for f in present}))
                        missing.append(
                            f"slot '{slot.slot_name}' ({slot.field_name}): "
                            f"{len(present)} field(s) exist but none is NORMALIZED "
                            f"(status: {statuses}) — insufficient information")
                    else:
                        missing.append(
                            f"slot '{slot.slot_name}' ({slot.field_name}): no such "
                            f"field in the source normalization record")
                    continue
                ambiguous.append(
                    f"slot '{slot.slot_name}' ({slot.field_name}): "
                    f"{len(candidates)} NORMALIZED candidates (field_seqs "
                    f"{sorted(f.field_seq for f in candidates)}) — association "
                    f"decisions belong to the Canonicalization Gate")
                continue

            # origin == "derived"
            candidates, failure = self._derivation_candidates(normalization_id,
                                                              slot.field_name)
            if failure is not None:
                raise _DerivedSourceFailure(failure[0], failure[1])
            if len(candidates) == 1:
                derivation_id, value, extraction_id = candidates[0]
                parsed = parse_canonical_decimal(value or "")
                if parsed is None:
                    missing.append(
                        f"slot '{slot.slot_name}' ({slot.field_name}): DERIVED value "
                        f"is outside the declared canonical decimal grammar — "
                        f"refused, never parsed leniently")
                    continue
                resolved[slot.slot_name] = parsed
                refs.append(ValidationInputRef(
                    input_slot=slot_index, slot_name=slot.slot_name,
                    field_name=slot.field_name, value_origin=VALUE_ORIGIN_DERIVED,
                    source_normalization_id=normalization_id,
                    source_extraction_id=extraction_id,
                    source_field_seq=None, source_derivation_id=derivation_id))
                continue
            if len(candidates) == 0:
                missing.append(
                    f"slot '{slot.slot_name}' ({slot.field_name}): no derivation "
                    f"record produces this field — validation never triggers "
                    f"derivation; run the declared derivation first")
                continue
            ambiguous.append(
                f"slot '{slot.slot_name}' ({slot.field_name}): {len(candidates)} "
                f"derivation records produce this field "
                f"({', '.join(d for d, _, _ in candidates)}) — association "
                f"decisions belong to the Canonicalization Gate")

        if missing or ambiguous:
            # Durable DEFERRED: the non-decision itself is the auditable result.
            reason = REASON_AMBIGUOUS_INPUT if ambiguous else REASON_INSUFFICIENT_INPUT
            detail = "; ".join(ambiguous + missing)
            return (OUTCOME_DEFERRED, reason, detail, 0, None, None, None, None,
                    refs)

        target = resolved[rule.target_slot]
        if rule.rule_type == "rounded-equality":
            # The declared R2 rounded type is the ONLY exact-context exception:
            # non-terminating intermediates are acceptable HERE and only here —
            # they get rounded explicitly at the declared (precision, mode).
            expression_value = self._evaluate_exact(rule.expression, resolved,
                                                    allow_non_terminating=True)
        else:
            try:
                expression_value = self._evaluate_exact(rule.expression, resolved,
                                                        allow_non_terminating=False)
            except NonExactResult as exc:
                return (OUTCOME_DEFERRED, REASON_NON_EXACT_INTERMEDIATE,
                        f"expression has no exact decimal value ({exc}) — an exact "
                        f"context never rounds implicitly", 0, None, None, None,
                        None, refs)
        exact_expr = exact_value_string(expression_value)
        exact_target = to_exact_decimal_string(target)

        if rule.rule_type == "exact-consistency":
            if expression_value == target:
                return (OUTCOME_VALID, REASON_EXACT_MATCH,
                        f"{rule.target_slot} == expression exactly "
                        f"({exact_target})", 0, None, None, None, None, refs)
            return (OUTCOME_INVALID, REASON_MISMATCH,
                    f"exact mismatch: target {rule.target_slot}={exact_target} vs "
                    f"expression={exact_expr}", 0, None, None, None, None, refs)

        if rule.rule_type == "tolerated-equality":
            diff = abs(expression_value - target)
            if diff == 0:
                return (OUTCOME_VALID, REASON_EXACT_MATCH,
                        f"exact match ({exact_target}) — tolerance not consumed",
                        0, None, None, None, None, refs)
            diff_str = to_exact_decimal_string(diff)
            if diff <= parse_canonical_decimal(rule.tolerance):
                return (OUTCOME_VALID, REASON_WITHIN_TOLERANCE,
                        f"|expression − target| = {diff_str} ≤ declared tolerance "
                        f"{rule.tolerance}", 0, None, None, None, None, refs)
            return (OUTCOME_INVALID, REASON_MISMATCH_BEYOND_TOLERANCE,
                    f"|expression − target| = {diff_str} > declared tolerance "
                    f"{rule.tolerance} (feeds the REVIEW path downstream per D-08 "
                    f"— mapping is WP-5.2)", 0, None, None, None, None, refs)

        # rounded-equality — the D-08 parametric rounding (explicit, auditable)
        if expression_value == target:
            return (OUTCOME_VALID, REASON_EXACT_MATCH,
                    f"exact match ({exact_target}) — exact value preserved, no "
                    f"rounding applied", 0, None, None, None, None, refs)
        rounded = round_exact(expression_value, rule.rounding_precision,
                              rule.rounding_mode)
        rounded_str = to_fixed_decimal_string(rounded, rule.rounding_precision)
        if rounded == target:
            return (OUTCOME_VALID, REASON_ROUNDED_MATCH,
                    f"expression {exact_expr} rounded at precision "
                    f"{rule.rounding_precision}/{rule.rounding_mode} → "
                    f"{rounded_str} == target", 1, rule.rounding_precision,
                    rule.rounding_mode, exact_expr, rounded_str, refs)
        return (OUTCOME_INVALID, REASON_MISMATCH_AFTER_ROUNDING,
                f"mismatch after declared rounding: target "
                f"{rule.target_slot}={exact_target} vs rounded expression "
                f"{rounded_str}", 1, rule.rounding_precision, rule.rounding_mode,
                exact_expr, rounded_str, refs)

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalized_ref(slot_index: int, slot, normalization_id: str,
                        norm_record, field) -> ValidationInputRef:
        return ValidationInputRef(
            input_slot=slot_index, slot_name=slot.slot_name,
            field_name=slot.field_name, value_origin=VALUE_ORIGIN_NORMALIZED,
            source_normalization_id=normalization_id,
            source_extraction_id=norm_record.extraction_id,
            source_field_seq=field.field_seq, source_derivation_id=None)

    def _derivation_candidates(self, normalization_id: str, field_name: str) -> \
            Tuple[List[Tuple[str, str, str]], Optional[Tuple[str, str]]]:
        """All verified derivation outputs of one normalization record that produce
        field_name — via WP-4.2 verified reads ONLY (OD-V11). Returns
        ([(derivation_id, output_value, extraction_id)], None) on success or
        ([], ("integrity"|"unavailable", reason)) on a failed source read."""
        candidates: List[Tuple[str, str, str]] = []
        for derivation_id in self._derivations.derivations_for_normalization(
                normalization_id):
            read = self._derivations.read_derivation(derivation_id)
            if isinstance(read, DerivationReadSuccess):
                if read.record.output_field_name == field_name:
                    candidates.append((derivation_id, read.record.output_value,
                                       read.record.extraction_id))
                continue
            if isinstance(read, DerivationReadIntegrityFailure):
                return [], ("integrity",
                            f"referenced derivation {derivation_id} failed its "
                            f"verified read: {read.reason}")
            if isinstance(read, DerivationReadRefused):
                return [], ("unavailable",
                            f"referenced derivation {derivation_id} refused: "
                            f"{read.detail}")
            # DerivationReadVerificationUnavailable
            return [], ("unavailable", read.issue_report)
        return candidates, None

    @staticmethod
    def _evaluate_exact(node: object, values: Dict[str, Fraction],
                        allow_non_terminating: bool) -> Fraction:
        """Evaluate the declared expression tree over exact operands (pure recursion
        over declaration data — there is no code to execute here, by construction).

        ADD/SUB/MUL reuse the WP-4.2 exact ops verbatim. DIV is handled locally so
        the termination policy is a CALLER decision: exact contexts (R1,
        tolerated-equality) refuse a non-terminating quotient (NonExactResult —
        never rounded implicitly); the declared rounded-equality type accepts it
        (explicit rounding is its purpose — SPEC §4)."""
        if isinstance(node, RuleSlotRef):
            return values[node.slot_name]
        if isinstance(node, RuleExprOp):
            operands = tuple(
                ValidationService._evaluate_exact(child, values,
                                                  allow_non_terminating)
                for child in node.args)
            if node.op == "DIV":
                if len(operands) != 2:
                    raise ValueError("DIV arity must be exactly 2")
                quotient = operands[0] / operands[1]     # exact rational division
                if not allow_non_terminating \
                        and not is_terminating_decimal(quotient):
                    raise NonExactResult(
                        "quotient is not a terminating decimal — refused, "
                        "never rounded")
                return quotient
            return evaluate(node.op, operands)
        raise TypeError(f"non-declaration payload inside expression: {type(node)!r}")

    # ------------------------------------------------------------------
    # Verified read — VOR pattern bound to validation records (SPEC §8)
    # ------------------------------------------------------------------

    def read_validation(self, validation_id: str) -> object:
        """Read a validation record with a definitive integrity verdict computed
        INSIDE the read. Every outcome explicit: ValidationReadSuccess |
        ValidationReadIntegrityFailure (stored content NEVER delivered) |
        ValidationReadRefused (unknown id) | ValidationReadVerificationUnavailable
        (no verdict computable; Issue-Report)."""
        try:
            record = self._store.get_record(validation_id)
        except ValidationNotFound:
            return ValidationReadRefused(None, "no such validation record")
        try:
            inputs = self._store.get_inputs(validation_id)
        except ValidationNotFound:                     # pragma: no cover - defensive
            self._issues.append(f"validation {validation_id}: input rows vanished")
            return ValidationReadVerificationUnavailable(
                validation_id, "input rows missing — Issue Report required")

        if len(inputs) != record.input_count:
            issue = (f"durable input set inconsistent "
                     f"(input_count={record.input_count}, rows={len(inputs)})")
            self._issues.append(f"validation {validation_id}: {issue}")
            return ValidationReadVerificationUnavailable(
                validation_id, issue + " — Issue Report required")

        recomputed = canonical_validation_bytes(record, inputs)
        verdict = self._s1.verify(recomputed, record.record_fingerprint,
                                  record.fingerprint_algorithm_id)
        if verdict.outcome == "NO_VERDICT":
            issue = (f"record verification unavailable: "
                     f"{verdict.reason or 'capability failure'}")
            self._issues.append(f"validation {validation_id}: {issue}")
            return ValidationReadVerificationUnavailable(
                validation_id, issue + " — Issue Report required")
        if verdict.outcome == "FAILED":
            return ValidationReadIntegrityFailure(validation_id, NOTE_VERIFY_FAILED,
                                                  utc_now_iso())
        return ValidationReadSuccess(record, tuple(inputs), utc_now_iso())

    # ------------------------------------------------------------------
    # Traceability walk — validation → rule → inputs → (derivation sub-chain) →
    # normalization → extraction → binding → document/page/span → Capture S1
    # (SPEC §10; pointers only, everything re-verified)
    # ------------------------------------------------------------------

    def trace_validation(self, validation_id: str) -> object:
        """Walk the full provenance chain with verified reads on EVERY link inside
        this one call. DERIVED inputs are walked through the WP-4.2 service's own
        whole-chain trace (P4.2 provenance consumed, never bypassed). Deliverable:
        ordered coarse link verdicts (no source values copied)."""
        head = self.read_validation(validation_id)
        if isinstance(head, ValidationReadIntegrityFailure):
            return ValidationTraceIntegrityFailure(validation_id, "validation",
                                                   head.reason)
        if isinstance(head, ValidationReadRefused):
            return ValidationTraceRefused(validation_id, head.detail)
        if isinstance(head, ValidationReadVerificationUnavailable):
            self._issues.append(f"trace {validation_id}: {head.issue_report}")
            return ValidationTraceVerificationUnavailable(validation_id,
                                                          head.issue_report)
        record, input_refs = head.record, head.inputs

        chain: List[str] = [
            f"validation: {record.outcome} rule={record.rule_id}/"
            f"{record.rule_version} kind={record.rule_kind} type={record.rule_type} "
            f"rule_fp={record.rule_fingerprint[:12]}… reason={record.outcome_reason}"
            + (f" rounding={record.rounding_precision}/"
               f"{record.rounding_mode} in={record.rounding_input_value} "
               f"out={record.rounding_output_value} (audit)"
               if record.rounding_applied else ""),
        ]

        if {ref.source_normalization_id for ref in input_refs} != \
                {record.normalization_id}:
            return ValidationTraceIntegrityFailure(
                validation_id, "validation",
                "input pointers leave the scope normalization record — chain refused")
        if {ref.source_extraction_id for ref in input_refs} != {record.extraction_id}:
            return ValidationTraceIntegrityFailure(
                validation_id, "validation",
                "input pointers leave the scope extraction record — chain refused")

        # link: derivation sub-chains (DERIVED inputs — walked through WP-4.2)
        for ref in input_refs:
            if ref.value_origin != VALUE_ORIGIN_DERIVED:
                continue
            sub = self._derivations.trace_derivation(ref.source_derivation_id)
            if isinstance(sub, DerivationTraceSuccess):
                chain.append(
                    f"input[{ref.input_slot}] {ref.slot_name}={ref.field_name}: "
                    f"DERIVED via derivation {ref.source_derivation_id[:12]}… — "
                    f"WP-4.2 whole-chain re-verified in this walk")
                continue
            link = getattr(sub, "link", "derivation")
            reason = getattr(sub, "reason",
                             getattr(sub, "detail",
                                     getattr(sub, "issue_report", "unknown")))
            if type(sub).__name__ == "DerivationTraceVerificationUnavailable":
                self._issues.append(f"trace {validation_id}: {reason}")
                return ValidationTraceVerificationUnavailable(validation_id, reason)
            return ValidationTraceIntegrityFailure(
                validation_id, "derivation",
                f"derivation sub-chain failed at link '{link}': {reason}")

        # link: normalization (WP-4.1 verified read)
        norm_read = self._normalization.read_normalization(record.normalization_id)
        if isinstance(norm_read, NormalizationReadIntegrityFailure):
            return ValidationTraceIntegrityFailure(validation_id, "normalization",
                                                   norm_read.reason)
        if isinstance(norm_read, NormalizationReadRefused):
            return ValidationTraceRefused(validation_id,
                                          "normalization record missing")
        if isinstance(norm_read, NormalizationReadVerificationUnavailable):
            self._issues.append(f"trace {validation_id}: {norm_read.issue_report}")
            return ValidationTraceVerificationUnavailable(validation_id,
                                                          norm_read.issue_report)
        norm_record, norm_fields = norm_read.record, norm_read.fields
        if norm_record.extraction_id != record.extraction_id:
            return ValidationTraceIntegrityFailure(validation_id, "normalization",
                                                   "extraction linkage drift")
        chain.append(
            f"normalization: OK ruleset={norm_record.ruleset_id}/"
            f"{norm_record.ruleset_version} fields={norm_record.field_count}")

        # link: extraction (WP-3.1 verified read)
        ext_read = self._extraction.read_extraction(record.extraction_id)
        if isinstance(ext_read, ExtractionReadIntegrityFailure):
            return ValidationTraceIntegrityFailure(validation_id, "extraction",
                                                   ext_read.reason)
        if isinstance(ext_read, ExtractionReadRefused):
            return ValidationTraceRefused(validation_id, "extraction record missing")
        if isinstance(ext_read, ExtractionReadVerificationUnavailable):
            self._issues.append(f"trace {validation_id}: {ext_read.issue_report}")
            return ValidationTraceVerificationUnavailable(validation_id,
                                                          ext_read.issue_report)
        extracted_by_seq = {f.field_seq: f for f in ext_read.fields}
        chain.append(
            f"extraction: OK engine={ext_read.extraction.engine_id}/"
            f"{ext_read.extraction.engine_schema_version} "
            f"fields={ext_read.extraction.field_count}")

        # link: evidence binding (WP-3.2 verified read — five links, fresh)
        binding_read = self._binder.read_binding(record.extraction_id)
        if isinstance(binding_read, BindingReadIntegrityFailure):
            return ValidationTraceIntegrityFailure(
                validation_id, "binding",
                f"link '{binding_read.link.value}': {binding_read.reason}")
        if isinstance(binding_read, BindingReadRefused):
            return ValidationTraceRefused(validation_id, "evidence binding missing")
        if isinstance(binding_read, BindingReadVerificationUnavailable):
            self._issues.append(f"trace {validation_id}: {binding_read.issue_report}")
            return ValidationTraceVerificationUnavailable(validation_id,
                                                          binding_read.issue_report)
        entries_by_seq = {e.field_seq: e for e in binding_read.entries}
        chain.append(
            f"binding: OK binding_id={binding_read.binding.binding_id[:12]}… "
            f"entries={binding_read.binding.field_binding_count}")

        # link: document/page/span (WP-2.1 verified read; span slice decodes to verbatim)
        doc_read = self._reconstruction.read_document(record.document_id)
        if isinstance(doc_read, DocumentReadIntegrityFailure):
            return ValidationTraceIntegrityFailure(validation_id, "document",
                                                   doc_read.reason)
        if isinstance(doc_read, DocumentReadRefused):
            return ValidationTraceRefused(validation_id, "document record missing")
        if isinstance(doc_read, DocumentReadVerificationUnavailable):
            self._issues.append(f"trace {validation_id}: {doc_read.issue_report}")
            return ValidationTraceVerificationUnavailable(validation_id,
                                                          doc_read.issue_report)
        chain.append(
            f"document: OK pages={len(doc_read.pages)} "
            f"capture_s1={doc_read.capture_s1[:12]}…")

        for ref in input_refs:
            if ref.value_origin != VALUE_ORIGIN_NORMALIZED:
                continue
            field = next((f for f in norm_fields
                          if f.field_seq == ref.source_field_seq), None)
            if field is None or field.status is not NormalizationStatus.NORMALIZED \
                    or field.source_field_name != ref.field_name:
                return ValidationTraceIntegrityFailure(
                    validation_id, "normalization",
                    f"input slot '{ref.slot_name}' points at field_seq "
                    f"{ref.source_field_seq} which is not a NORMALIZED "
                    f"'{ref.field_name}' — chain refused")
            extracted = extracted_by_seq.get(ref.source_field_seq)
            if extracted is None or extracted.value_verbatim is None:
                return ValidationTraceIntegrityFailure(
                    validation_id, "extraction",
                    f"field_seq {ref.source_field_seq} missing from the extraction "
                    f"record")
            entry = entries_by_seq.get(ref.source_field_seq)
            if entry is None or entry.page_index >= len(doc_read.pages):
                return ValidationTraceIntegrityFailure(
                    validation_id, "binding",
                    f"field_seq {ref.source_field_seq} has no valid binding entry")
            page = doc_read.pages[entry.page_index]
            if entry.page_fingerprint != page.page_fingerprint:
                return ValidationTraceIntegrityFailure(
                    validation_id, "document",
                    f"page fingerprint drift at field_seq {ref.source_field_seq}")
            verbatim = bytes(page.content)[entry.byte_start:entry.byte_end] \
                .decode(extracted.value_encoding)
            if verbatim != extracted.value_verbatim:
                return ValidationTraceIntegrityFailure(
                    validation_id, "document",
                    f"span slice no longer decodes to the verbatim value "
                    f"(field_seq {ref.source_field_seq})")
            chain.append(
                f"input[{ref.input_slot}] {ref.slot_name}={ref.field_name} "
                f"(NORMALIZED): normalization field_seq={ref.source_field_seq} → "
                f"extraction verbatim → page {entry.page_index} "
                f"[{entry.byte_start},{entry.byte_end}) → OK")

        # link: capture S1 (linkage carried by the record and re-checked here)
        if doc_read.capture_id != record.capture_id \
                or doc_read.capture_s1 != record.capture_s1:
            return ValidationTraceIntegrityFailure(validation_id, "validation",
                                                   "capture linkage drift")
        chain.append(
            f"capture: OK capture_id={record.capture_id[:12]}… "
            f"s1={record.capture_s1[:12]}… ({record.capture_s1_algorithm_id})")
        return ValidationTraceSuccess(validation_id, tuple(chain))

    # ------------------------------------------------------------------
    # Traceability enumeration (normalization-scoped; WP-5.2 consumer)
    # ------------------------------------------------------------------

    def validations_for_normalization(self, normalization_id: str) -> Tuple[str, ...]:
        """All validation records for a normalization — deterministic order."""
        return tuple(self._store.find_for_normalization(normalization_id))

    # ------------------------------------------------------------------
    # Issue-report surface (minimal MVP hook, VOR §2 analog)
    # ------------------------------------------------------------------

    def issue_reports(self) -> list:
        """Accumulated Issue-Report items surfaced by this service instance."""
        return list(self._issues)
