"""Shared helpers for the WP-4.2 derivation tests (unique module name — safe for
combined collection with the capture/reconstruction/extraction/normalization suites)."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent          # tests → derivation → src
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
    DerivationFormula,
    FormulaInput,
    FormulaInputRef,
    FormulaOp,
    ReferenceDerivationFormulasV1,
)

# Test corpus — key=value pages (the declared reference-engine grammar).
PAGE_OK = [b"invoice.number=INV-2026-001\ntotal.net=1000.00\ntax.amount=80\n"]
PAGE_EU = [b"total.net=1.234,56\ntax.amount=196,80\n"]        # European grouping inputs
PAGE_MISSING = [b"total.net=1000.00\n"]                       # no tax.amount slot
PAGE_AMBIGUOUS = [b"total.net=100.00\ntotal.net=200.00\ntax.amount=8\n"]
PAGE_DEFERRED_INPUT = [b"total.net=1000.00\ntax.amount=1.2.3\n"]     # malformed → DEFERRED
PAGE_REJECTED_INPUT = [b"total.net=1000.00\ntax.amount=bad\x00x\n"]  # control char → REJECTED
PAGE_OUTPUT_PRESENT = [b"total.net=1000.00\ntax.amount=80\ntotal.gross=999\n"]
PAGE_TEXTY = [b"total.net=1000.00\ntax.amount=eighty\n"]      # tax kind=decimal → DEFERRED
PAGE_OK_ALT = [b"tax.amount=80\ninvoice.number=INV-2026-001\ntotal.net=1000.00\n"]
# ^ reordered bytes: distinct capture (D-03), identical NORMALIZED content
PAGE_TEXTY_RULESET = [b"total.net=1,234.56\ntax.amount=80\n"]  # text-kind ruleset keeps commas


def ingest_pages(capture_service: CaptureService, parts, label="deriv-test") -> str:
    """Ingest an aggregated artifact and return the COMPLETED capture_id."""
    content = CaptureService.aggregate(parts)
    outcome = capture_service.ingest(content, source_label=label)
    assert isinstance(outcome, IngestCompleted), outcome
    return outcome.capture_id


class AltEngine(ExtractionEngine):
    """Minimal second engine — proves the derivation mechanism is engine-independent
    (identical NORMALIZED inputs derive identically from ANY engine; no engine module
    is imported by the derivation layer)."""

    def __init__(self, engine_id="alt-der-engine-v1", schema_version="1"):
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


def quotient_formula(formula_id="test-neutral-quotient", version="1",
                     output_field="q.result", numerator="a", denominator="b"):
    """A test-declared exact-division formula over NEUTRAL field names (mechanism
    capability probe — NOT unit_amount, which is never shipped or inferred)."""
    return DerivationFormula(
        formula_id=formula_id,
        formula_version=version,
        output_field_name=output_field,
        inputs=(FormulaInput(slot_name="x", field_name=numerator),
                FormulaInput(slot_name="y", field_name=denominator)),
        expression=FormulaOp("DIV", (FormulaInputRef("x"), FormulaInputRef("y"))),
    )


def net_minus_tax_formula(formula_id="test-net-minus-tax", version="1"):
    """A second declared formula over the SAME corpus (SUB) — proves two distinct
    formulas coexist on one normalization record."""
    return DerivationFormula(
        formula_id=formula_id,
        formula_version=version,
        output_field_name="test.net-minus-tax",
        inputs=(FormulaInput(slot_name="net", field_name="total.net"),
                FormulaInput(slot_name="tax", field_name="tax.amount")),
        expression=FormulaOp("SUB", (FormulaInputRef("net"), FormulaInputRef("tax"))),
    )


def doubled_formula(formula_id="kandoo-der-total-gross-from-net-tax", version="2"):
    """Version 2 of the reference formula: declarationally distinct (swapped operand
    order), same semantics — proves version-keyed distinct derivations."""
    return DerivationFormula(
        formula_id=formula_id,
        formula_version=version,
        output_field_name="total.gross",
        inputs=(FormulaInput(slot_name="tax", field_name="tax.amount"),
                FormulaInput(slot_name="net", field_name="total.net")),
        expression=FormulaOp("ADD", (FormulaInputRef("tax"), FormulaInputRef("net"))),
    )


class DerivationStack:
    """One opened capture+reconstruction(+evidence)+extraction+binding+normalization
    +derivation stack sharing the same DB files — the WP-4.2 composition under test."""

    def __init__(self, capture_db, recon_db, extraction_db, binding_db, norm_db,
                 deriv_db, with_evidence=True, engines=None, formulas=None,
                 extra_formulas=(), norm_rulesets=None):
        self.capture_db = capture_db
        self.recon_db = recon_db
        self.extraction_db = extraction_db
        self.binding_db = binding_db
        self.norm_db = norm_db
        self.deriv_db = deriv_db
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
            {"reference-delimited-v1": ReferenceDelimitedEngine(),
             "alt-der-engine-v1": AltEngine()},
            S1Service())
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
        for extra in extra_formulas:
            registry_formulas[(extra.formula_id, extra.formula_version)] = extra
        self.registry = DerivationFormulaRegistry(registry_formulas, S1Service())
        self.deriv = DerivationService(
            self.deriv_store, self.norm, self.extraction, self.binder, self.recon,
            self.registry, S1Service())

    def build_document(self, parts=None, label="deriv-test") -> str:
        """Ingest → reconstruct → return the COMPLETED document_id."""
        parts = PAGE_OK if parts is None else parts
        capture_id = ingest_pages(self.capture, parts, label)
        built = self.recon.reconstruct(capture_id)
        assert isinstance(built, ReconstructCompleted), built
        return built.document.document_id

    def build_extract_normalize(self, parts=None, engine_id="reference-delimited-v1",
                                label="deriv-test",
                                ruleset_id="kandoo-norm-v1") -> str:
        """Ingest → reconstruct → extract → bind → normalize → return
        (extraction_id, normalization_id)."""
        document_id = self.build_document(parts, label)
        done = self.extraction.extract(document_id, engine_id)
        assert isinstance(done, ExtractionCompleted), done
        extraction_id = done.extraction.extraction_id
        bound = self.binder.bind_extraction(extraction_id)
        assert isinstance(bound, BindingCompleted), bound
        normed = self.norm.normalize(extraction_id, ruleset_id)
        assert isinstance(normed, NormalizationCompleted), normed
        return extraction_id, normed.record.normalization_id

    def derive_ok(self, parts=None, formula_id="kandoo-der-total-gross-from-net-tax",
                  formula_version="1", engine_id="reference-delimited-v1"):
        """Full happy path → (DerivationCompleted, normalization_id)."""
        _, normalization_id = self.build_extract_normalize(parts, engine_id)
        outcome = self.deriv.derive(normalization_id, formula_id, formula_version)
        assert isinstance(outcome, DerivationCompleted), outcome
        return outcome, normalization_id

    def close(self):
        self.deriv_store.close()
        self.norm_store.close()
        self.binding_store.close()
        self.extraction_store.close()
        if self.evidence_store is not None:
            self.evidence_store.close()
        self.recon_store.close()
        self.capture_store.close()
