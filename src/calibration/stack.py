"""Calibration workspace stack — WP-12.2 (SPEC-WP122-CAL §2.4/§10 OD-CR-B).

Wires the FROZEN pipeline services exactly as the frozen compositions do —
the constructor arguments below are VERBATIM from the frozen layers'
declared compositions. This module owns NO behavior of its own: it opens
workspace-scoped stores, composes the frozen services, and closes them.

Nothing here opens a production path: every store lives under the
workspace directory the caller provides (SPEC §2.2). No test-helper import
anywhere — this wiring is self-contained production code (AST-swept).
"""
from __future__ import annotations

from pathlib import Path

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


class CalibrationStack:
    """One calibration workspace's full frozen-pipeline composition."""

    def __init__(self, workspace: Path, s1: S1Service, *,
                 reference_rules: dict, norm_ruleset) -> None:
        self._s1 = s1
        workspace.mkdir(parents=True, exist_ok=True)
        self.capture_store = CaptureStore(workspace / "capture.db")
        self.capture = CaptureService(self.capture_store, s1)
        self.recon_store = ReconstructionStore(workspace / "recon.db")
        self.evidence_store = EvidenceStore(
            str(workspace / "recon.evidence.db"), s1)
        self.recon = ReconstructionService(
            self.recon_store, self.capture, s1, evidence=self.evidence_store)
        self.extraction_store = ExtractionStore(workspace / "extraction.db", s1)
        self.extraction = ExtractionService(
            self.extraction_store, self.recon,
            {"reference-delimited-v1": ReferenceDelimitedEngine()}, s1)
        self.binding_store = ExtractionBindingStore(workspace / "binding.db", s1)
        self.binder = ExtractionEvidenceBinder(
            self.binding_store, self.extraction, self.recon,
            self.evidence_store, s1)
        self.norm_store = NormalizationStore(workspace / "norm.db", s1)
        self.norm = NormalizationService(
            self.norm_store, self.extraction,
            {"kandoo-norm-v1": norm_ruleset}, s1)
        self.deriv_store = DerivationStore(workspace / "deriv.db", s1)
        self.dregistry = DerivationFormulaRegistry(
            dict(self._reference_formulas()), s1)
        self.deriv = DerivationService(
            self.deriv_store, self.norm, self.extraction, self.binder,
            self.recon, self.dregistry, s1)
        self.val_store = ValidationStore(workspace / "val.db", s1)
        self.vregistry = ValidationRuleRegistry(dict(reference_rules), s1)
        self.val = ValidationService(
            self.val_store, self.norm, self.extraction, self.binder,
            self.recon, self.deriv, self.vregistry, s1)
        self.vsm_store = ValidationDomainStore(workspace / "vsm.db", s1)
        self.vsm = ValidationDomainService(
            self.vsm_store, self.val, self.vregistry, self.norm,
            self.extraction, self.binder, self.recon, s1)
        self.gate_store = CanonicalizationGateStore(workspace / "gate.db", s1)
        self.gate = CanonicalizationGateService(
            self.gate_store, self.vsm, self.norm, s1)

    @staticmethod
    def _reference_formulas():
        from derivation import ReferenceDerivationFormulasV1
        return ReferenceDerivationFormulasV1()

    def __enter__(self) -> "CalibrationStack":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        for store in (self.gate_store, self.vsm_store, self.val_store,
                      self.deriv_store, self.norm_store, self.binding_store,
                      self.extraction_store, self.evidence_store,
                      self.recon_store, self.capture_store):
            try:
                store.close()
            except Exception:
                pass
