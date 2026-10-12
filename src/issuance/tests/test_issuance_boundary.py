"""Boundary proofs for the composed issuance surface: declarations, ownership,
missing deferred surfaces, no SQL/CLI/secret, and no new vocabulary."""
import ast
import sqlite3
from pathlib import Path

import pytest

import issuance
import issuance.workspace as workspace_module
from capture.retention import PURGE_EXECUTION_ALLOWED, request_purge
from issuance import DigitalIssuanceWorkspace
from digital_invoice import (
    DigitalInvoiceOpened,
    LIFECYCLE_STATES,
    ORIGINS,
    STATE_DRAFT,
)

ROOT = Path(issuance.__file__).parent
PRODUCTION_MODULES = ("__init__.py", "model.py", "service.py", "workspace.py")

ALLOWED_IMPORT_ROOTS = {"__future__", "pathlib", "contextlib", "dataclasses",
                        "typing", "capture", "digital_invoice", "pipeline"}
FORBIDDEN_ATTRIBUTES = {"execute", "executemany", "executescript", "unlink",
                        "rmtree", "remove", "request_purge", "popen", "system",
                        "spawn", "check_output", "purge", "delete"}
FORBIDDEN_IDENTIFIERS = {"sqlite3", "hashlib", "random", "uuid", "subprocess",
                         "argparse", "os", "sys", "socket", "requests",
                         "tolerance", "precision", "retention", "purge",
                         "receipt", "render", "print", "spool", "email",
                         "sms", "share", "inventory", "sale", "role",
                         "permission", "login", "password", "token",
                         "schedule", "timer", "thread", "cron", "clock"}
FROZEN_LITERALS = set(LIFECYCLE_STATES) | set(ORIGINS) | {
    "MARK_EXTRACTED", "MARK_VALIDATED", "ISSUE", "REVOKE", "SUPERSEDE",
    "SELECT", "INSERT", "UPDATE", "DELETE", "PRAGMA", "CREATE", "DROP",
    "HALF_UP", "0.02", "__main__",
}


def production_sources():
    for name in PRODUCTION_MODULES:
        path = ROOT / name
        assert path.exists(), f"missing production module {name}"
        yield path, path.read_text()


def docstring_nodes(tree):
    """Every Constant that is a module/class/function docstring."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                found.add(id(body[0].value))
    return found


def test_production_inventory_is_exactly_the_declared_surface():
    assert {path.name for path in ROOT.glob("*.py")} == set(PRODUCTION_MODULES)
    assert not (ROOT / "__main__.py").exists()
    assert set(issuance.__all__) == {
        "DigitalIssuanceWorkspace", "IssuanceService", "IssuanceSubmission",
        "DigitalInvoiceStatus", "DIGITAL_INVOICE_DB"}
    assert not [name for name in dir(issuance) if name.startswith("STATE_")]


def test_imports_stay_inside_the_declared_allowlist():
    for path, text in production_sources():
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert node.names, path
                for alias in node.names:
                    assert alias.name.split(".")[0] in ALLOWED_IMPORT_ROOTS, \
                        f"{path.name}: {alias.name}"
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module.split(".")[0] in ALLOWED_IMPORT_ROOTS, \
                    f"{path.name}: {node.module}"


def test_no_sql_process_policy_or_deferred_identifier_anywhere():
    for path, text in production_sources():
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in FORBIDDEN_ATTRIBUTES, \
                    f"{path.name}: attribute {node.attr}"
            if isinstance(node, ast.Name):
                assert node.id not in FORBIDDEN_IDENTIFIERS, \
                    f"{path.name}: name {node.id}"
            if isinstance(node, ast.keyword) and node.arg is not None:
                assert node.arg not in FORBIDDEN_IDENTIFIERS, \
                    f"{path.name}: keyword {node.arg}"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert node.name not in FORBIDDEN_IDENTIFIERS, \
                    f"{path.name}: function {node.name}"
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) \
                    else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        assert target.id not in FORBIDDEN_IDENTIFIERS, \
                            f"{path.name}: assignment to {target.id}"


def test_no_frozen_vocabulary_literal_outside_a_docstring():
    for path, text in production_sources():
        tree = ast.parse(text)
        docstrings = docstring_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in docstrings:
                assert node.value.strip().upper() not in FROZEN_LITERALS, \
                    f"{path.name}: frozen literal {node.value!r}"
                for token in FROZEN_LITERALS:
                    assert token not in node.value, \
                        f"{path.name}: {token!r} inside {node.value!r}"
            if isinstance(node, ast.Constant) \
                    and isinstance(node.value, float):
                raise AssertionError(
                    f"{path.name}: floating policy-like literal {node.value}")
        assert "0.02" not in text and "HALF_UP" not in text


def test_workspace_requires_explicit_declarations_before_creating_files(tmp_path):
    with pytest.raises(TypeError):
        DigitalIssuanceWorkspace(tmp_path / "missing")
    with pytest.raises(ValueError):
        DigitalIssuanceWorkspace(tmp_path / "empty", validation_rules={})
    with pytest.raises(Exception):
        DigitalIssuanceWorkspace(tmp_path / "bad",
                                 validation_rules={"bad": object()})
    assert list(tmp_path.iterdir()) == []


def test_workspace_owns_exactly_the_frozen_stores(workspace, tmp_path,
                                                  unique_pages, declaration):
    expected = {"capture.db", "recon.db", "recon.evidence.db",
                "extraction.db", "binding.db", "norm.db", "deriv.db",
                "val.db", "vsm.db", "gate.db", "assembly.db",
                "digital-invoice.db"}
    assert {p.name for p in tmp_path.iterdir()} == expected
    invoice_id = workspace.service.submit(unique_pages(), **declaration).invoice_id
    assert isinstance(workspace.service.open_digital_invoice(invoice_id),
                      DigitalInvoiceOpened)
    assert {p.name for p in tmp_path.iterdir()} == expected
    assert not [p for p in tmp_path.iterdir() if p.is_dir()]


def test_lifecycle_layer_reads_the_same_assembly_store_it_was_composed_with(
        workspace):
    assert workspace.digital_invoice._assembly \
        is workspace.pipeline_workspace.assembly


def test_close_is_idempotent_and_closed_workspace_refuses_work(
        workspace, unique_pages, declaration):
    workspace.close()
    workspace.close()
    with pytest.raises(RuntimeError, match="closed"):
        workspace.service.submit(unique_pages(), **declaration)
    with pytest.raises(RuntimeError, match="closed"):
        workspace.service.awaiting_digital_invoice()


def test_constructor_failure_closes_already_opened_stores(tmp_path, rules,
                                                          monkeypatch):
    opened = []
    original = workspace_module.PipelineWorkspace

    def pipeline(*args, **kwargs):
        workspace = original(*args, **kwargs)
        opened.append(workspace)
        return workspace

    def broken(*args, **kwargs):
        raise OSError("injected digital-invoice store failure")

    monkeypatch.setattr(workspace_module, "PipelineWorkspace", pipeline)
    monkeypatch.setattr(workspace_module, "DigitalInvoiceStore", broken)
    with pytest.raises(OSError, match="injected digital-invoice store failure"):
        DigitalIssuanceWorkspace(tmp_path, validation_rules=rules)
    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].capture_store._conn.execute("SELECT 1")
    assert not (tmp_path / "digital-invoice.db").exists()


def test_physical_purge_stays_blocked_and_out_of_the_composed_surface(workspace):
    assert PURGE_EXECUTION_ALLOWED is False
    decision = request_purge("any-capture-id", authorization=object())
    assert decision.executed is False and decision.rows_affected == 0
    assert not hasattr(workspace.service, "request_purge")
    assert not hasattr(workspace, "request_purge")
    assert not hasattr(workspace.digital_invoice, "request_purge")


def test_unknown_frozen_outcome_is_refused_not_guessed(workspace, monkeypatch):
    monkeypatch.setattr(workspace.digital_invoice, "read_digital_invoice",
                        lambda invoice_id: object())
    with pytest.raises(TypeError, match="refuses to guess"):
        workspace.service.status("whatever")


def test_reads_and_listings_never_grow_business_entities(
        workspace, tmp_path, unique_pages, declaration):
    def counts():
        result = {}
        for db in sorted(tmp_path.glob("*.db")):
            if db.name == "recon.evidence.db":
                continue
            with sqlite3.connect(db) as connection:
                for (table,) in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"):
                    result[(db.name, table)] = connection.execute(
                        f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        return result

    invoice_id = workspace.service.submit(unique_pages(), **declaration).invoice_id
    assert isinstance(workspace.service.open_digital_invoice(invoice_id),
                      DigitalInvoiceOpened)
    before = counts()
    for _ in range(2):
        workspace.service.status(invoice_id)
        workspace.service.read(invoice_id)
        workspace.service.trace(invoice_id)
        workspace.service.issued_canonical_invoices()
        workspace.service.opened_digital_invoices()
        workspace.service.awaiting_digital_invoice()
    assert counts() == before


def test_state_of_a_fresh_digital_invoice_is_the_frozen_draft(
        workspace, unique_pages, declaration):
    invoice_id = workspace.service.submit(unique_pages(), **declaration).invoice_id
    assert isinstance(workspace.service.open_digital_invoice(invoice_id),
                      DigitalInvoiceOpened)
    status = workspace.service.status(invoice_id)
    assert status.verified is True
    assert status.current_state == STATE_DRAFT
    assert status.current_state in LIFECYCLE_STATES
