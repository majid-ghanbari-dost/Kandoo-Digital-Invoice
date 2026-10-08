"""Shared helpers for the WP-5.1 validation tests (unique module name — safe for
combined collection with the capture/reconstruction/extraction/normalization/
derivation suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → validation → src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capture import CaptureService, CaptureStore, IngestCompleted, S1Service  # noqa: E402
from reconstruction import (  # noqa: E402
    EvidenceStore,
    ReconstructCompleted,
    ReconstructionService,
    ReconstructionStore,
)
from extraction import (  # noqa: E402
    BindingCompleted,
    ExtractionCompleted,
    ExtractionEngine,
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
)
from normalization import (  # noqa: E402
    NormalizationCompleted,
    NormalizationService,
    NormalizationStore,
    ReferenceNormalizationRulesV1,
)
from derivation import (  # noqa: E402
    DerivationCompleted,
    DerivationFormulaRegistry,
    DerivationService,
    DerivationStore,
    ReferenceDerivationFormulasV1,
)
from validation import (  # noqa: E402
    RuleExprOp,
    RuleInput,
    RuleSlotRef,
    ValidationCompleted,
    ValidationRule,
    ValidationRuleRegistry,
    ValidationService,
    ValidationStore,
    ReferenceValidationRulesV1,
)

# D-08 calibration parameters used across the suite (injected — never hardcoded in
# the engine; these values are the test deployment's declared parameters).
TOLERANCE = "0.02"
PRECISION = 2
MODE = "HALF_UP"

# Test corpus — key=value pages (the declared reference-engine grammar).
PAGE_OK = [b"invoice.number=VAL-2026-001\ntotal.net=1000.00\ntax.amount=80\n"]
PAGE_EU = [b"total.net=1.234,56\ntax.amount=196,80\n"]        # European grouping inputs
PAGE_MISSING_TAX = [b"total.net=1000.00\n"]                   # tax.amount slot absent
PAGE_ABSENT_FIELD = [b"invoice.number=VAL-2026-002\nseller.name=K GmbH\n"]
PAGE_DEFERRED_INPUT = [b"total.net=1000.00\ntax.amount=1.2.3\n"]     # malformed → DEFERRED
PAGE_REJECTED_INPUT = [b"total.net=1000.00\ntax.amount=bad\x00x\n"]  # control char → REJECTED
PAGE_AMBIGUOUS = [b"total.net=100.00\ntotal.net=200.00\ntax.amount=8\n"]
PAGE_TEXTY_RULESET = [b"total.net=1,234.56\ntax.amount=80\n"]  # text-kind ruleset keeps commas
PAGE_OK_ALT = [b"tax.amount=80\ninvoice.number=VAL-2026-001\ntotal.net=1000.00\n"]
# ^ reordered bytes: distinct capture (D-03), identical NORMALIZED content

FORMULA = "kandoo-der-total-gross-from-net-tax"
R_PRESENT = "kandoo-val-total-net-present"
R_CONSIST = "kandoo-val-total-gross-consistency"
R_TOLERANCE = "kandoo-val-total-gross-tolerance"
R_ROUNDED = "kandoo-val-total-gross-rounded"


def ingest_pages(capture_service: CaptureService, parts, label="val-test") -> str:
    """Ingest an aggregated artifact and return the COMPLETED capture_id."""
    content = CaptureService.aggregate(parts)
    outcome = capture_service.ingest(content, source_label=label)
    assert isinstance(outcome, IngestCompleted), outcome
    return outcome.capture_id


def reference_rules(**overrides):
    """The declared reference rules with the suite's injected D-08 parameters."""
    kwargs = {"tolerance": TOLERANCE, "precision": PRECISION, "mode": MODE}
    kwargs.update(overrides)
    return ReferenceValidationRulesV1(**kwargs)


def sub_expression_rule(rule_id="test-consistency-sub-probe", version="1"):
    """A test-declared R1 probe whose expression deliberately differs from the
    derivation formula (SUB instead of ADD) — the engine's genuine-mismatch probe:
    it compares values honestly and must report INVALID, never rubber-stamp."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R1",
        rule_type="exact-consistency",
        inputs=(
            RuleInput(slot_name="target", field_name="total.gross", origin="derived"),
            RuleInput(slot_name="net", field_name="total.net", origin="normalized"),
            RuleInput(slot_name="tax", field_name="tax.amount", origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("SUB", (RuleSlotRef("net"), RuleSlotRef("tax"))),
    )


class AltEngine(ExtractionEngine):
    """Minimal second engine — proves the validation engine is engine-independent
    (identical NORMALIZED inputs validate identically from ANY engine; no engine
    module is imported by the validation layer)."""

    def __init__(self, engine_id="alt-val-engine-v1", schema_version="1"):
        self._engine_id = engine_id
        self._schema_version = schema_version

    @property
    def engine_id(self) -> str:
        return self._engine_id

    @property
    def schema_version(self) -> str:
        return self._schema_version

    def extract_pages(self, pages):
        from extraction import ExtractedField, Provenance, SourceSpan
        fields = []
        seq = 0
        for page in pages:
            content = bytes(page.content)
            start = 0
            while True:
                nl = content.find(b"\n", start)
                line_end = len(content) if nl == -1 else nl
                if line_end > start:
                    eq = content.find(b"=", start, line_end)
                    if eq > start:
                        fields.append(ExtractedField(
                            field_seq=seq,
                            field_name=content[start:eq].decode("utf-8"),
                            value_verbatim=content[eq + 1:line_end].decode("utf-8"),
                            value_encoding="utf-8",
                            provenance=Provenance.EXTRACTED,
                            span=SourceSpan(page.page_index, eq + 1, line_end,
                                            page.page_fingerprint),
                        ))
                        seq += 1
                if nl == -1:
                    break
                start = nl + 1
        return fields


def quotient_rule(rule_id="test-neutral-quotient-rule", version="1",
                  rule_type="rounded-equality", precision=2, mode="HALF_UP",
                  tolerance=None,
                  target_field="q.target", target_origin="derived",
                  numerator="a", denominator="b"):
    """A test-declared rule over NEUTRAL field names exercising DIV inside the
    expression (mechanism capability probe — NOT unit_amount, which is never
    shipped or inferred here any more than in WP-4.2)."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R2",
        rule_type=rule_type,
        inputs=(
            RuleInput(slot_name="target", field_name=target_field,
                      origin=target_origin),
            RuleInput(slot_name="x", field_name=numerator, origin="normalized"),
            RuleInput(slot_name="y", field_name=denominator, origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("DIV", (RuleSlotRef("x"), RuleSlotRef("y"))),
        rounding_precision=precision if rule_type == "rounded-equality" else None,
        rounding_mode=mode if rule_type == "rounded-equality" else None,
        tolerance=tolerance if rule_type == "tolerated-equality" else None,
    )


def presence_rule(rule_id="test-presence-probe", version="1",
                  field_name="seller.vat", origin="normalized"):
    """A test-declared R1 presence probe over an arbitrary field/origin."""
    return ValidationRule(
        rule_id=rule_id,
        rule_version=version,
        rule_kind="R1",
        rule_type="presence",
        inputs=(RuleInput(slot_name="field", field_name=field_name, origin=origin),),
        target_slot=None,
        expression=None,
    )


def swapped_rule(version="2"):
    """Version 2 of the reference consistency rule: declarationally distinct
    (swapped operand order), same semantics — proves version-keyed distinct
    validations."""
    return ValidationRule(
        rule_id=R_CONSIST,
        rule_version=version,
        rule_kind="R1",
        rule_type="exact-consistency",
        inputs=(
            RuleInput(slot_name="target", field_name="total.gross", origin="derived"),
            RuleInput(slot_name="tax", field_name="tax.amount", origin="normalized"),
            RuleInput(slot_name="net", field_name="total.net", origin="normalized"),
        ),
        target_slot="target",
        expression=RuleExprOp("ADD", (RuleSlotRef("tax"), RuleSlotRef("net"))),
    )


class ValidationStack:
    """One opened capture+reconstruction(+evidence)+extraction+binding+normalization
    +derivation+validation stack sharing the same DB files — the WP-5.1 composition
    under test."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db, norm_db,
                 deriv_db, val_db, with_evidence=True, engines=None, rules=None,
                 extra_rules=(), formulas=None, norm_rulesets=None):
        self.capture_db = capture_db
        self.recon_db = recon_db
        self.extraction_db = extraction_db
        self.binding_db = binding_db
        self.norm_db = norm_db
        self.deriv_db = deriv_db
        self.val_db = val_db
        self.capture_store = CaptureStore(capture_db)
        self.capture = CaptureService(self.capture_store, S1Service())
        self.recon_store = ReconstructionStore(recon_db)
        self.evidence_store = EvidenceStore(str(recon_db) + ".evidence.db", S1Service()) \
            if with_evidence else None
        self.recon = ReconstructionService(self.recon_store, self.capture, S1Service(),
                                           evidence=self.evidence_store)
        self.extraction_store = ExtractionStore(extraction_db, S1Service())
        self.extraction = ExtractionService(
            self.extraction_store, self.recon,
            engines if engines is not None else
            {"reference-delimited-v1": ReferenceDelimitedEngine()}, S1Service())
        from extraction import ExtractionBindingStore, ExtractionEvidenceBinder
        self.binding_store = ExtractionBindingStore(binding_db, S1Service())
        self.binder = ExtractionEvidenceBinder(
            self.binding_store, self.extraction, self.recon, self.evidence_store,
            S1Service())
        self.norm_store = NormalizationStore(norm_db, S1Service())
        self.norm = NormalizationService(
            self.norm_store, self.extraction,
            norm_rulesets if norm_rulesets is not None else
            {"kandoo-norm-v1": ReferenceNormalizationRulesV1()}, S1Service())
        self.deriv_store = DerivationStore(deriv_db, S1Service())
        registry_formulas = dict(
            formulas if formulas is not None else ReferenceDerivationFormulasV1())
        self.dregistry = DerivationFormulaRegistry(registry_formulas, S1Service())
        self.deriv = DerivationService(
            self.deriv_store, self.norm, self.extraction, self.binder, self.recon,
            self.dregistry, S1Service())
        self.val_store = ValidationStore(val_db, S1Service())
        rule_map = dict(rules if rules is not None else reference_rules())
        for extra in extra_rules:
            rule_map[(extra.rule_id, extra.rule_version)] = extra
        self.vregistry = ValidationRuleRegistry(rule_map, S1Service())
        self.val = ValidationService(
            self.val_store, self.norm, self.extraction, self.binder, self.recon,
            self.deriv, self.vregistry, S1Service())

    def build_document(self, parts=None, label="val-test") -> str:
        """Ingest → reconstruct → return the COMPLETED document_id."""
        parts = PAGE_OK if parts is None else parts
        capture_id = ingest_pages(self.capture, parts, label)
        built = self.recon.reconstruct(capture_id)
        assert isinstance(built, ReconstructCompleted), built
        return built.document.document_id

    def build_extract_normalize(self, parts=None, engine_id="reference-delimited-v1",
                                label="val-test",
                                ruleset_id="kandoo-norm-v1") -> str:
        """Ingest → reconstruct → extract → bind → normalize → normalization_id."""
        document_id = self.build_document(parts, label)
        done = self.extraction.extract(document_id, engine_id)
        assert isinstance(done, ExtractionCompleted), done
        extraction_id = done.extraction.extraction_id
        bound = self.binder.bind_extraction(extraction_id)
        assert isinstance(bound, BindingCompleted), bound
        normed = self.norm.normalize(extraction_id, ruleset_id)
        assert isinstance(normed, NormalizationCompleted), normed
        return normed.record.normalization_id

    def build_derive_validate_ready(self, parts=None, label="val-test") -> str:
        """Full happy path up to a DERIVED total.gross → normalization_id."""
        normalization_id = self.build_extract_normalize(parts, label=label)
        outcome = self.deriv.derive(normalization_id, FORMULA, "1")
        assert isinstance(outcome, DerivationCompleted), outcome
        return normalization_id

    def validate_ok(self, normalization_id, rule_id=R_PRESENT, version="1"):
        outcome = self.val.validate(normalization_id, rule_id, version)
        assert isinstance(outcome, ValidationCompleted), outcome
        return outcome

    def close(self):
        self.val_store.close()
        self.deriv_store.close()
        self.norm_store.close()
        self.binding_store.close()
        self.extraction_store.close()
        if self.evidence_store is not None:
            self.evidence_store.close()
        self.recon_store.close()
        self.capture_store.close()


def extended_service(stack, *rules):
    """A ValidationService over the SAME stores with the reference rules PLUS the
    given probe rules registered — used by per-test rule probes."""
    from capture import S1Service
    from validation import ValidationRuleRegistry, ValidationService
    rule_map = {**(reference_rules())}
    for rule in rules:
        rule_map[(rule.rule_id, rule.rule_version)] = rule
    registry = ValidationRuleRegistry(rule_map, S1Service())
    return ValidationService(stack.val_store, stack.norm, stack.extraction,
                             stack.binder, stack.recon, stack.deriv, registry,
                             S1Service())
