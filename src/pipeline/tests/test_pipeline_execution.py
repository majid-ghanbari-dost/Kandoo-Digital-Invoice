"""Real-store acceptance, replay/resume, fail-closure and provenance evidence."""
from dataclasses import replace
import sqlite3

import pytest

from pipeline import (PipelineWorkspace, PipelineCompleted, PipelineStopped,
                      PipelineExecutionError)
from capture import IngestDuplicateAtCapture
from derivation import DerivationDeferred
from canonicalization import (CanonicalizationAlreadyDecided,
                              CanonicalizationRoutedToReview,
                              CanonicalizationRejected,
                              CanonicalizationAlreadyCanonicalized)
from canonical_assembly import AssemblyAlreadyAssembled, AssemblyRequestRefused
from validation import RuleExprOp, RuleSlotRef


def entity_counts(path):
    """Read audits can append evidence; business/stage entities must not grow."""
    counts = {}
    for db in path.glob("*.db"):
        if db.name == "recon.evidence.db":
            continue
        with sqlite3.connect(db) as connection:
            for (table,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"):
                counts[(db.name, table)] = connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    return counts


def test_cold_start_real_canonical_invoice(workspace, pages, declaration):
    result = workspace.pipeline.process(pages, **declaration)
    assert isinstance(result, PipelineCompleted), result
    invoice = result.invoice.invoice
    assert invoice.invoice_id == result.trace.invoice_id
    assert invoice.line_count == 1
    assert invoice.customer_reference is None
    assert result.trace.chain
    assert {f.provenance for f in result.invoice.fields} == {"EXTRACTED", "DERIVED"}
    assert [step.stage for step in result.steps] == [
        "capture", "capture_read", "reconstruct", "extract", "bind", "normalize", "derive",
        "validate", "validate", "validate", "validate", "project", "gate",
        "gate_read", "assemble", "invoice_read", "invoice_trace"]


def test_replay_and_restart_keep_identity_and_entity_counts(tmp_path, rules, pages, declaration):
    with PipelineWorkspace(tmp_path, validation_rules=rules) as workspace:
        first = workspace.pipeline.process(pages, **declaration)
        assert isinstance(first, PipelineCompleted)
        before = entity_counts(tmp_path)
        again = workspace.pipeline.process(pages, **declaration)
        assert isinstance(again, PipelineCompleted)
        assert again.invoice.invoice == first.invoice.invoice
        assert entity_counts(tmp_path) == before
    with PipelineWorkspace(tmp_path, validation_rules=rules) as reopened:
        result = reopened.pipeline.process(pages, **declaration)
        assert isinstance(result, PipelineCompleted)
        assert result.capture_id == first.capture_id
        assert result.invoice.invoice == first.invoice.invoice
        assert isinstance(result.steps[0].outcome, IngestDuplicateAtCapture)
        assert any(isinstance(s.outcome, CanonicalizationAlreadyDecided) for s in result.steps)
        assert any(isinstance(s.outcome, AssemblyAlreadyAssembled) for s in result.steps)
        assert entity_counts(tmp_path) == before


@pytest.mark.parametrize("remove", [b"tax.amount=80\n", b"invoice.date=2026-10-01\n"])
def test_review_never_assembles_and_replays(workspace, pages, declaration, remove):
    pages = [pages[0].replace(remove, b"")]
    for attempt in range(2):
        result = workspace.pipeline.process(pages, **declaration)
        assert isinstance(result, PipelineStopped)
        assert result.stage == "gate"
        assert result.outcome.decision.decision == "REVIEW"
        assert isinstance(result.outcome, (CanonicalizationRoutedToReview,
                                           CanonicalizationAlreadyDecided))
        assert not workspace.assembly.issued_invoices()
        if remove.startswith(b"tax"):
            assert any(isinstance(s.outcome, DerivationDeferred) for s in result.steps)
    assert len(workspace.gate.list_gate_review_items()) == 1


def test_reject_is_verbatim_and_never_assembles(tmp_path, rules, pages, declaration):
    # Existing R1 declaration API; test-only SUB probe, not a new business rule.
    key = ("kandoo-val-total-gross-consistency", "1")
    rules[key] = replace(rules[key], expression=RuleExprOp(
        "SUB", (RuleSlotRef("net"), RuleSlotRef("tax"))))
    with PipelineWorkspace(tmp_path, validation_rules=rules) as workspace:
        result = workspace.pipeline.process(pages, **declaration)
        assert isinstance(result, PipelineStopped)
        assert isinstance(result.outcome, CanonicalizationRejected)
        assert result.outcome.decision.decision == "REJECTED"
        assert not workspace.assembly.issued_invoices()
        assert not workspace.gate.canonical_invoices()


def test_different_capture_same_identity_is_not_a_second_invoice(workspace, pages, declaration):
    first = workspace.pipeline.process(pages, **declaration)
    reordered = [b"\n".join(reversed(pages[0].splitlines())) + b"\n"]
    result = workspace.pipeline.process(reordered, **declaration)
    assert isinstance(first, PipelineCompleted)
    assert isinstance(result, PipelineStopped)
    assert isinstance(result.outcome, CanonicalizationRejected)
    assert result.outcome.decision.decision_reason == "d03-definite-document-duplicate"
    assert result.capture_id != first.capture_id
    assert len(workspace.assembly.issued_invoices()) == 1


def test_line_declaration_drift_does_not_reshape_invoice(workspace, pages, declaration):
    first = workspace.pipeline.process(pages, **declaration)
    assert isinstance(first, PipelineCompleted)
    declaration["line_binding"] = None
    result = workspace.pipeline.process(pages, **declaration)
    assert isinstance(result, PipelineStopped) and result.stage == "assemble"
    assert isinstance(result.outcome, AssemblyRequestRefused)
    assert "assembly-declaration-conflict" in result.outcome.detail
    assert workspace.assembly.issued_invoices()[0] == first.invoice.invoice


@pytest.mark.parametrize("point", ["extract", "assemble"])
def test_interrupted_prefix_resumes_after_restart(tmp_path, rules, pages, declaration, monkeypatch, point):
    with PipelineWorkspace(tmp_path, validation_rules=rules) as workspace:
        service = workspace.extraction if point == "extract" else workspace.assembly
        original = getattr(service, point)
        def fail(*args, **kwargs):
            raise OSError("injected interruption")
        monkeypatch.setattr(service, point, fail)
        with pytest.raises(PipelineExecutionError) as error:
            workspace.pipeline.process(pages, **declaration)
        assert error.value.stage == point
        assert isinstance(error.value.__cause__, OSError)
        capture_id = error.value.capture_id
        assert capture_id
        assert not workspace.assembly.issued_invoices()
        monkeypatch.setattr(service, point, original)
    with PipelineWorkspace(tmp_path, validation_rules=rules) as reopened:
        result = reopened.pipeline.process(pages, **declaration)
        assert isinstance(result, PipelineCompleted)
        assert result.capture_id == capture_id
        assert len(reopened.assembly.issued_invoices()) == 1


def test_binary_page_fails_at_reference_extraction(workspace, declaration):
    result = workspace.pipeline.process([b"\xff\xfe"], **declaration)
    assert isinstance(result, PipelineStopped) and result.stage == "extract"
    assert type(result.outcome).__name__ == "ExtractionEngineFailed"
    assert not workspace.assembly.issued_invoices()


@pytest.mark.parametrize("db,sql", [
    ("capture.db", "UPDATE artifact_content SET content = X'00'"),
    ("gate.db", "UPDATE gate_decisions SET decision_detail = 'forged'"),
    ("assembly.db", "UPDATE canonical_invoices SET document_id = 'forged'"),
])
def test_tamper_is_withheld_on_replay(tmp_path, workspace, pages, declaration, db, sql):
    first = workspace.pipeline.process(pages, **declaration)
    assert isinstance(first, PipelineCompleted)
    with sqlite3.connect(tmp_path / db) as connection:
        connection.execute(sql)
    result = workspace.pipeline.process(pages, **declaration)
    assert isinstance(result, PipelineStopped), result
    assert "Integrity" in type(result.outcome).__name__, result


@pytest.mark.parametrize("attr,method,stage", [
    ("capture", "ingest", "capture"),
    ("capture", "read_evidence", "capture_read"),
    ("recon", "reconstruct", "reconstruct"),
    ("extraction", "extract", "extract"),
    ("binder", "bind_extraction", "bind"),
    ("norm", "normalize", "normalize"),
    ("deriv", "derive", "derive"),
    ("val", "validate", "validate"),
    ("vsm", "project_domain_state", "project"),
    ("gate", "canonicalize", "gate"),
    ("gate", "read_gate_decision", "gate_read"),
    ("assembly", "assemble", "assemble"),
    ("assembly", "read_assembled_invoice", "invoice_read"),
    ("assembly", "trace_assembled_invoice", "invoice_trace"),
])
def test_unknown_outcome_stops_without_executing_later_stages(
        workspace, pages, declaration, monkeypatch, attr, method, stage):
    sentinel = object()
    monkeypatch.setattr(getattr(workspace, attr), method, lambda *a, **kw: sentinel)
    result = workspace.pipeline.process(pages, **declaration)
    assert isinstance(result, PipelineStopped)
    assert result.stage == stage and result.outcome is sentinel
    assert result.steps[-1].stage == stage
    assert sum(s.outcome is sentinel for s in result.steps) == 1
    if stage not in ("invoice_read", "invoice_trace"):
        assert not workspace.assembly.issued_invoices()


def test_new_projection_same_capture_stops_already_canonicalized(workspace, pages, declaration):
    first = workspace.pipeline.process(pages, **declaration)
    assert isinstance(first, PipelineCompleted)
    declaration["ruleset_version"] = "2"
    result = workspace.pipeline.process(pages, **declaration)
    assert isinstance(result, PipelineStopped)
    assert result.stage == "gate"
    assert isinstance(result.outcome, CanonicalizationAlreadyCanonicalized)
    assert result.outcome.existing_canonical_invoice.canonical_invoice_id == first.trace.invoice_id
    assert len(workspace.assembly.issued_invoices()) == 1


def test_ordered_multipage_input_and_explicit_absent_lines(workspace, pages, declaration):
    lines = pages[0].splitlines(keepends=True)
    declaration["line_binding"] = None
    result = workspace.pipeline.process([b"".join(lines[:2]), b"".join(lines[2:])], **declaration)
    assert isinstance(result, PipelineCompleted)
    assert result.invoice.invoice.line_count == 0
    assert result.invoice.lines == ()
    assert len(result.invoice.fields) > 0


def test_retry_after_final_verification_failure_does_not_duplicate(workspace, pages, declaration, monkeypatch):
    original = workspace.assembly.trace_assembled_invoice
    sentinel = object()
    monkeypatch.setattr(workspace.assembly, "trace_assembled_invoice", lambda *args: sentinel)
    stopped = workspace.pipeline.process(pages, **declaration)
    assert isinstance(stopped, PipelineStopped) and stopped.outcome is sentinel
    durable_invoice = workspace.assembly.issued_invoices()[0]
    monkeypatch.setattr(workspace.assembly, "trace_assembled_invoice", original)
    completed = workspace.pipeline.process(pages, **declaration)
    assert isinstance(completed, PipelineCompleted)
    assert completed.invoice.invoice == durable_invoice
    assert len(workspace.assembly.issued_invoices()) == 1
