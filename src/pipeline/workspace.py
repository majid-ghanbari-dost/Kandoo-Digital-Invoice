"""Owned durable reference workspace; stdlib + frozen public services only.

Validation declarations must be provided explicitly. No calibration defaults,
threshold approval, digital lifecycle, customer/inventory store or network I/O.
"""
from __future__ import annotations

from pathlib import Path
from contextlib import ExitStack

from canonical_assembly import CanonicalAssemblyService, CanonicalAssemblyStore
from normalization import ReferenceNormalizationRulesV1
from .service import PipelineService

from capture import CaptureService, CaptureStore, S1Service
from reconstruction import (
    EvidenceStore,
    ReconstructionService,
    ReconstructionStore,
)
from extraction import (
    ExtractionService,
    ExtractionStore,
    ReferenceDelimitedEngine,
    ExtractionBindingStore,
    ExtractionEvidenceBinder,
)
from normalization import NormalizationService, NormalizationStore
from derivation import (
    DerivationFormulaRegistry,
    DerivationService,
    DerivationStore,
)
from validation import (
    ValidationRuleRegistry,
    ValidationService,
    ValidationStore,
)
from validation_domain import ValidationDomainService, ValidationDomainStore
from canonicalization import CanonicalizationGateService, \
    CanonicalizationGateStore


class PipelineWorkspace:
    """Use as a context manager. One synchronous caller per instance.

    The directory must be application-owned (not an untrusted customer path).
    Reopen with the SAME declarations; frozen version/replay rules still apply.
    Existing stores are never deleted/reset. Recovery of incomplete low-level
    store writes remains the existing capture/reconstruction recovery API's job.
    """
    def __init__(self, directory: Path, *, validation_rules):
        rules = dict(validation_rules)
        if not rules:
            raise ValueError("validation_rules must be explicitly declared and nonempty")
        s1 = S1Service()
        # Validate declarations before creating files.
        ValidationRuleRegistry(rules, s1)
        self._resources = ExitStack()
        self._closed = False
        try:
            workspace = Path(directory)
            workspace.mkdir(parents=True, exist_ok=True)
            self._build(workspace, s1, rules)
        except BaseException:
            self.close()
            raise

    def _own(self, store):
        self._resources.callback(store.close)
        return store

    def _build(self, workspace, s1, rules):
        self.capture_store = self._own(CaptureStore(workspace / "capture.db"))
        self.capture = CaptureService(self.capture_store, s1)
        self.recon_store = self._own(ReconstructionStore(workspace / "recon.db"))
        self.evidence_store = self._own(EvidenceStore(
            str(workspace / "recon.evidence.db"), s1))
        self.recon = ReconstructionService(
            self.recon_store, self.capture, s1, evidence=self.evidence_store)
        self.extraction_store = self._own(ExtractionStore(workspace / "extraction.db", s1))
        self.extraction = ExtractionService(
            self.extraction_store, self.recon,
            {"reference-delimited-v1": ReferenceDelimitedEngine()}, s1)
        self.binding_store = self._own(ExtractionBindingStore(workspace / "binding.db", s1))
        self.binder = ExtractionEvidenceBinder(
            self.binding_store, self.extraction, self.recon,
            self.evidence_store, s1)
        self.norm_store = self._own(NormalizationStore(workspace / "norm.db", s1))
        self.norm = NormalizationService(
            self.norm_store, self.extraction,
            {"kandoo-norm-v1": ReferenceNormalizationRulesV1()}, s1)
        self.deriv_store = self._own(DerivationStore(workspace / "deriv.db", s1))
        self.dregistry = DerivationFormulaRegistry(
            dict(self._reference_formulas()), s1)
        self.deriv = DerivationService(
            self.deriv_store, self.norm, self.extraction, self.binder,
            self.recon, self.dregistry, s1)
        self.val_store = self._own(ValidationStore(workspace / "val.db", s1))
        self.vregistry = ValidationRuleRegistry(rules, s1)
        self.val = ValidationService(
            self.val_store, self.norm, self.extraction, self.binder,
            self.recon, self.deriv, self.vregistry, s1)
        self.vsm_store = self._own(ValidationDomainStore(workspace / "vsm.db", s1))
        self.vsm = ValidationDomainService(
            self.vsm_store, self.val, self.vregistry, self.norm,
            self.extraction, self.binder, self.recon, s1)
        self.gate_store = self._own(CanonicalizationGateStore(workspace / "gate.db", s1))
        self.gate = CanonicalizationGateService(
            self.gate_store, self.vsm, self.norm, s1)

        self.assembly_store = self._own(CanonicalAssemblyStore(
            workspace / "assembly.db", s1))
        self.assembly = CanonicalAssemblyService(
            self.assembly_store, self.gate, self.norm, self.deriv, s1)
        self.pipeline = PipelineService(self, self.vregistry.keys())

    @staticmethod
    def _reference_formulas():
        from derivation import ReferenceDerivationFormulasV1
        return ReferenceDerivationFormulasV1()

    def require_open(self):
        if self._closed:
            raise RuntimeError("pipeline workspace is closed")

    def __enter__(self):
        self.require_open()
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if not self._closed:
            self._closed = True
            self._resources.close()
