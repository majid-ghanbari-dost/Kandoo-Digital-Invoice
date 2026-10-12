"""No policy defaults, no deferred side effects, strict declarations/ownership."""
import ast
from pathlib import Path

import pytest

from pipeline import PipelineWorkspace
import pipeline.workspace as workspace_module


@pytest.mark.parametrize("field,value", [
    ("declared_origin", "KANDOO_SALE"), ("declared_origin", "invented"),
    ("identity_binding", {"invented": "invoice.number"}),
    ("line_binding", {True: {}}), ("line_binding", {0: {}}),
    ("ruleset_id", ""), ("ruleset_version", " "), ("source_label", None),
])
def test_malformed_declaration_has_no_capture_residue(workspace, pages, declaration, field, value):
    declaration[field] = value
    with pytest.raises(ValueError):
        workspace.pipeline.process(pages, **declaration)
    assert workspace.capture_store._conn.execute(
        "SELECT COUNT(*) FROM capture_records").fetchone()[0] == 0


@pytest.mark.parametrize("pages", [[], b"raw bytes", [12], ["string"], [bytearray(b"a")]])
def test_invalid_page_shape_has_no_capture_residue(workspace, declaration, pages):
    with pytest.raises(ValueError):
        workspace.pipeline.process(pages, **declaration)
    assert workspace.capture_store._conn.execute(
        "SELECT COUNT(*) FROM capture_records").fetchone()[0] == 0


def test_validation_declarations_required_before_file_creation(tmp_path):
    with pytest.raises(TypeError):
        PipelineWorkspace(tmp_path / "missing")
    with pytest.raises(ValueError):
        PipelineWorkspace(tmp_path / "empty", validation_rules={})
    with pytest.raises(Exception):
        PipelineWorkspace(tmp_path / "bad", validation_rules={"bad": object()})
    assert list(tmp_path.iterdir()) == []


def test_constructor_failure_closes_already_opened_stores(tmp_path, rules, monkeypatch):
    stores = []
    original = workspace_module.CaptureStore
    def capture(*args):
        store = original(*args)
        stores.append(store)
        return store
    def broken(*args):
        raise OSError("injected store-open failure")
    monkeypatch.setattr(workspace_module, "CaptureStore", capture)
    monkeypatch.setattr(workspace_module, "ReconstructionStore", broken)
    with pytest.raises(OSError, match="injected store-open failure"):
        PipelineWorkspace(tmp_path, validation_rules=rules)
    import sqlite3
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        stores[0]._conn.execute("SELECT 1")


def test_close_idempotent_and_closed_workspace_refuses_work(workspace, pages, declaration):
    workspace.close()
    workspace.close()
    with pytest.raises(RuntimeError, match="closed"):
        workspace.pipeline.process(pages, **declaration)


def test_no_digital_customer_product_or_purge_store_created(tmp_path, workspace, pages, declaration):
    workspace.pipeline.process(pages, **declaration)
    assert {p.name for p in tmp_path.glob("*.db")} == {
        "capture.db", "recon.db", "recon.evidence.db", "extraction.db", "binding.db",
        "norm.db", "deriv.db", "val.db", "vsm.db", "gate.db", "assembly.db"}


def test_production_import_boundary_and_no_sql_cli_or_new_identity():
    root = Path(workspace_module.__file__).parent
    allowed = {"__future__", "pathlib", "contextlib", "dataclasses", "typing",
               "capture", "reconstruction", "extraction", "normalization",
               "derivation", "validation", "validation_domain",
               "canonicalization", "canonical_assembly"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name.split(".")[0] in allowed for a in node.names)
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module.split(".")[0] in allowed
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"execute", "executemany", "unlink", "rmtree",
                                         "issue", "request_purge", "open_digital_invoice"}
        assert not (root / "__main__.py").exists()
