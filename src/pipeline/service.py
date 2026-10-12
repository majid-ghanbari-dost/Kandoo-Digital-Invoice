"""Additive capture-to-canonical composition; no SQL or domain decisions.

Uses the reference engine/ruleset/formula already exercised by the frozen
smokes. Validation rules and all source bindings are caller declarations.
No CLI, policy defaults, review resolution or Digital Invoice lifecycle acts.
"""
from capture import (CaptureService, IngestCompleted, IngestDuplicateAtCapture,
                     ReadSuccess)
from reconstruction import ReconstructCompleted, ReconstructAlreadyExists
from extraction import (ExtractionCompleted, ExtractionAlreadyExists,
                        BindingCompleted, BindingAlreadyExists)
from normalization import NormalizationCompleted, NormalizationAlreadyExists
from derivation import (DerivationCompleted, DerivationAlreadyExists,
                        DerivationDeferred)
from validation import ValidationCompleted, ValidationAlreadyExists
from validation_domain import DomainStateProjected, DomainStateAlreadyExists
from canonicalization import (
    CAPTURE_PIPELINE_ORIGINS, DECISION_ACCEPTED, validate_binding,
    CanonicalizationAccepted, CanonicalizationAlreadyDecided,
    CanonicalizationRoutedToReview, CanonicalizationRejected,
    CanonicalizationAlreadyCanonicalized, GateDecisionReadSuccess,
)
from canonical_assembly import (
    validate_line_binding, AssemblyCompleted, AssemblyAlreadyAssembled,
    AssemblyReadSuccess, AssemblyTraceSuccess,
)
from .model import (StageOutcome, PipelineCompleted, PipelineStopped,
                    PipelineExecutionError)


class _Stop(Exception):
    def __init__(self, stage, outcome):
        self.stage, self.outcome = stage, outcome


class PipelineService:
    """Sequential, synchronous execution over one workspace's public services.

    Re-submit the same ordered pages/declarations to resume a durable prefix.
    No cross-store transaction, rollback, new dedup key or identity is invented.
    """
    def __init__(self, services, validation_keys):
        self._services = services
        self._validation_keys = tuple(validation_keys)

    def process(self, pages, *, source_label, declared_origin,
                identity_binding, line_binding, ruleset_id, ruleset_version):
        """Return PipelineCompleted or PipelineStopped with verbatim outcomes.

        Invalid declarations raise ValueError before ingest. Unexpected runtime
        exceptions raise PipelineExecutionError with their original cause.
        REVIEW/REJECT/ALREADY_CANONICALIZED are terminal for THIS call only;
        they are not converted to ACCEPTED or routed to assembly.
        """
        self._services.require_open()
        if declared_origin not in CAPTURE_PIPELINE_ORIGINS:
            raise ValueError("declared_origin must be a frozen capture-pipeline origin")
        identity = validate_binding(identity_binding)
        lines = validate_line_binding(line_binding)
        if any(not isinstance(v, str) or not v.strip()
               for v in (source_label, ruleset_id, ruleset_version)):
            raise ValueError("source_label and ruleset id/version must be nonblank strings")
        # Do not silently convert integers/strings to bytes via bytes(value).
        if isinstance(pages, (bytes, bytearray, str)):
            raise ValueError("pages must be an ordered iterable of bytes")
        pages = tuple(pages)
        if not pages or any(not isinstance(page, bytes) for page in pages):
            raise ValueError("pages must contain at least one bytes page")
        content = CaptureService.aggregate(pages)
        steps = []
        capture_id = None
        stage = "capture"
        s = self._services

        def run(name, fn, accepted, *args, **kwargs):
            nonlocal stage
            stage = name
            outcome = fn(*args, **kwargs)
            steps.append(StageOutcome(name, outcome))
            if not isinstance(outcome, accepted):
                raise _Stop(name, outcome)
            return outcome

        try:
            result = run("capture", s.capture.ingest,
                         (IngestCompleted, IngestDuplicateAtCapture),
                         content, source_label=source_label)
            capture_id = (result.capture_id if isinstance(result, IngestCompleted)
                          else result.existing_capture_id)
            # Reconstruction replay may return its durable document before
            # reading capture content. Explicit VOR is required on EVERY run.
            run("capture_read", s.capture.read_evidence, ReadSuccess, capture_id)
            result = run("reconstruct", s.recon.reconstruct,
                         (ReconstructCompleted, ReconstructAlreadyExists), capture_id)
            document_id = (result.document.document_id
                           if isinstance(result, ReconstructCompleted)
                           else result.document_id)
            result = run("extract", s.extraction.extract,
                         (ExtractionCompleted, ExtractionAlreadyExists),
                         document_id, "reference-delimited-v1")
            extraction_id = (result.extraction.extraction_id
                             if isinstance(result, ExtractionCompleted)
                             else result.extraction_id)
            run("bind", s.binder.bind_extraction,
                (BindingCompleted, BindingAlreadyExists), extraction_id)
            result = run("normalize", s.norm.normalize,
                         (NormalizationCompleted, NormalizationAlreadyExists),
                         extraction_id, "kandoo-norm-v1")
            normalization_id = (result.record.normalization_id
                                if isinstance(result, NormalizationCompleted)
                                else result.normalization_id)
            # NOT_DERIVABLE is not an infrastructure/integrity failure. Let
            # frozen validation/domain/gate decide the missing-value outcome.
            run("derive", s.deriv.derive,
                (DerivationCompleted, DerivationAlreadyExists, DerivationDeferred),
                normalization_id, "kandoo-der-total-gross-from-net-tax", "1")
            for rule_id, version in self._validation_keys:
                run("validate", s.val.validate,
                    (ValidationCompleted, ValidationAlreadyExists),
                    normalization_id, rule_id, version)
            result = run("project", s.vsm.project_domain_state,
                         (DomainStateProjected, DomainStateAlreadyExists),
                         normalization_id, ruleset_id, ruleset_version,
                         list(self._validation_keys))
            state_id = (result.record.domain_state_id
                        if isinstance(result, DomainStateProjected)
                        else result.domain_state_id)
            gate = run("gate", s.gate.canonicalize,
                       (CanonicalizationAccepted, CanonicalizationAlreadyDecided,
                        CanonicalizationRoutedToReview, CanonicalizationRejected,
                        CanonicalizationAlreadyCanonicalized),
                       state_id, declared_origin, identity)
            # Even a replay's decision is re-read through VOR before routing.
            decision = run("gate_read", s.gate.read_gate_decision,
                           GateDecisionReadSuccess, gate.decision.decision_id)
            if decision.record.decision != DECISION_ACCEPTED:
                raise _Stop("gate", gate)
            invoice_id = decision.record.canonical_invoice_id
            run("assemble", s.assembly.assemble,
                (AssemblyCompleted, AssemblyAlreadyAssembled), invoice_id, lines)
            invoice = run("invoice_read", s.assembly.read_assembled_invoice,
                          AssemblyReadSuccess, invoice_id)
            trace = run("invoice_trace", s.assembly.trace_assembled_invoice,
                        AssemblyTraceSuccess, invoice_id)
            return PipelineCompleted(capture_id, invoice, trace, tuple(steps))
        except _Stop as stop:
            return PipelineStopped(stop.stage, stop.outcome, capture_id, tuple(steps))
        except Exception as exc:
            raise PipelineExecutionError(stage, capture_id, steps) from exc
