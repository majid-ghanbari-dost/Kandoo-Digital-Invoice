"""WP-6.2 boundary tests — structural AST proofs + frozen-layer protection
(SPEC §1/§12; dispatch §13 axes 25, 26 + forbidden-scope and vocabulary
sweeps)."""
import ast
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LAYER_DIR = SRC / "canonical_assembly"
LAYER_FILES = sorted(LAYER_DIR.glob("*.py"))

from ca_helpers import (  # noqa: E402
    LINE_BINDING,
    CanonicalAssemblyStack,
    unique_line_pages,
)
from canonical_assembly import (  # noqa: E402
    AssemblyCompleted,
    AssemblyRequestRefused,
    ORIGINS,
    PROVENANCES,
    HEADER_ROLES,
    LINE_ROLES,
    ORIGIN_KANDOO_SALE,
    ORIGIN_HOLOO_CAPTURE,
    ORIGIN_OTHER_POS_CAPTURE,
)
from canonicalization import CanonicalizationAccepted  # noqa: E402


# ---------------------------------------------------------------------------
# Axis 25: structural proof — no UPDATE / no DELETE in the layer
# ---------------------------------------------------------------------------

def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _strings_in(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def test_no_update_or_delete_statement_anywhere_in_the_layer():
    for path in LAYER_FILES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value.strip().upper()
                assert not value.startswith("UPDATE "), \
                    f"{path.name}: UPDATE statement present"
                assert not value.startswith("DELETE FROM "), \
                    f"{path.name}: DELETE statement present"
                assert not value.startswith("DROP "), \
                    f"{path.name}: DROP statement present"


def test_no_mutation_method_names_in_the_layer():
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                lowered = node.name.lower()
                for forbidden in ("update", "delete", "mutate", "amend",
                                  "rewrite", "drop_"):
                    assert not lowered.startswith(forbidden), \
                        f"{path.name}: function {node.name!r} looks like a " \
                        f"mutation path"


def test_no_identifier_minting_no_randomness_no_float_no_exec():
    """OD-A1/OD-A2: no uuid/random in this layer (the invoice_id is consumed
    verbatim from the P6.1 admission); no float arithmetic, no eval/exec
    (project-wide discipline)."""
    forbidden_modules = {"uuid", "random", "secrets", "eval", "exec",
                         "pickle", "ctypes", "subprocess", "socket",
                         "http", "urllib"}
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert node.names[0].name.split(".")[0] not in forbidden_modules, \
                    f"{path.name}: forbidden import {node.names[0].name}"
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in forbidden_modules, \
                    f"{path.name}: forbidden import-from {node.module}"
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, float):
                    pytest.fail(f"{path.name}: float literal {node.value}")


def test_import_allowlist_project_layers_only():
    allowed_roots = {"__future__", "dataclasses", "typing", "datetime",
                     "sqlite3", "capture", "normalization", "derivation",
                     "validation", "validation_domain", "canonicalization",
                     "canonical_assembly"}
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                root = node.names[0].name.split(".")[0]
                assert root in allowed_roots, \
                    f"{path.name}: import outside the allowlist: {root}"
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                root = (node.module or "").split(".")[0]
                assert root in allowed_roots, \
                    f"{path.name}: import-from outside the allowlist: {root}"


def _identifiers_in(tree):
    """All code identifiers (names, attributes, function defs) — docstrings
    legitimately DECLARE the boundaries (e.g. 'NO fuzzy matching'), so the
    sweep runs over identifiers, not prose."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.arg)):
            name = node.id if hasattr(node, "id") else getattr(
                node, "attr", None) or getattr(node, "name", None)
            if name:
                yield name.lower()


def test_no_fuzzy_or_semantic_or_business_matching_symbols():
    forbidden = ("fuzzy", "similarity", "levenshtein", "difflib",
                 "match_product", "product_match", "customer_match",
                 "auto_create", "ocr", "semantic", "tax_rate",
                 "currency_convert", "exchange_rate", "posting",
                 "inventory", "kpi")
    for path in LAYER_FILES:
        tree = _tree(path)
        for ident in _identifiers_in(tree):
            for token in forbidden:
                assert token not in ident, \
                    f"{path.name}: forbidden identifier {ident!r} " \
                    f"(contains {token!r})"


def test_no_direct_sql_against_the_gate_or_upstream_stores():
    """The assembly store touches ONLY its own tables — the P6.1 gate store
    and the frozen upstream stores are consumed through their services."""
    own_tables = {"canonical_invoices", "canonical_header_anchors",
                  "canonical_fields", "canonical_lines",
                  "canonical_line_fields"}
    forbidden_tables = {"gate_decisions", "gate_review_items",
                        "gate_review_events", "canonical_identity_pointers",
                        "normalization_records", "extraction_records",
                        "extraction_bindings", "capture_records",
                        "domain_states", "validation_records"}
    for path in LAYER_FILES:
        tree = _tree(path)
        for value in _strings_in(tree):
            for table in forbidden_tables:
                assert table not in value, \
                    f"{path.name}: direct reference to upstream table " \
                    f"{table!r}"
        # the schema script creates exactly the five own tables
        if path.name == "store.py":
            tokens = set()
            for v in _strings_in(_tree(path)):
                tokens.update(v.replace("(", " ").replace(",", " ")
                              .split())
            assert own_tables.issubset(tokens)
            assert tokens & {"gate_decisions", "gate_review_items",
                             "normalization_records"} == set()


def test_vocabulary_constants_are_verbatim():
    assert ORIGINS == ("KANDOO_SALE", "HOLOO_CAPTURE", "OTHER_POS_CAPTURE")
    assert PROVENANCES == ("EXTRACTED", "DERIVED")
    assert HEADER_ROLES == ("INVOICE_NUMBER", "INVOICE_DATE",
                            "INVOICE_TOTAL")
    assert LINE_ROLES == ("LINE_QUANTITY", "LINE_UNIT_PRICE", "LINE_TOTAL")


# ---------------------------------------------------------------------------
# Axis 26: P6.1 consumed, never bypassed — behavioral + structural
# ---------------------------------------------------------------------------

def test_assembly_service_consumes_the_gate_service_object():
    """Structural: the service is constructed WITH the P6.1 service — no
    re-implementation of admission decisions exists."""
    import inspect
    from canonical_assembly.service import CanonicalAssemblyService
    source = inspect.getsource(CanonicalAssemblyService)
    assert "read_canonical_invoice" in source
    assert "trace_canonical_invoice" in source
    assert "canonicalize" not in source.replace(
        "trace_canonical_invoice", "").replace(
        "read_canonical_invoice", ""), \
        "the assembly service must never call gate.canonicalize"


def test_no_admission_record_no_assembly_path(stack):
    """No canonicalization decision is ever re-made here: the ONLY entry is
    an existing admission record."""
    assert not hasattr(stack.assembly, "canonicalize")
    methods = {m for m in dir(stack.assembly) if not m.startswith("_")}
    assert methods == {"assemble", "issued_invoices", "issue_reports",
                       "read_assembled_invoice", "trace_assembled_invoice"}


def test_row_count_stability_of_frozen_stores_during_assembly(stack):
    """Assembly mutates NOTHING upstream — frozen-store row counts are
    stable across the assemble call."""
    outcome = stack.build_accepted_lines_admission(unique_line_pages(),
                                                   label="ca-boundary")
    assert isinstance(outcome, CanonicalizationAccepted)
    invoice_id = outcome.canonical_invoice.canonical_invoice_id

    def counts():
        rows = {}
        conns = {
            "capture": (stack.capture_db, "capture_records"),
            "norm": (stack.norm_db, "normalization_records"),
            "deriv": (stack.deriv_db, "derivation_records"),
            "gate": (stack.gate_db, "canonical_invoices"),
            "gate_d": (stack.gate_db, "gate_decisions"),
        }
        for key, (db, table) in conns.items():
            conn = sqlite3.connect(str(db))
            try:
                rows[key] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            finally:
                conn.close()
        return rows

    before = counts()
    asm = stack.assembly.assemble(invoice_id, LINE_BINDING)
    assert isinstance(asm, AssemblyCompleted)
    after = counts()
    assert before == after


def test_derivation_tables_stable_and_no_new_derivation_created(stack):
    outcome = stack.build_accepted_lines_admission(unique_line_pages(),
                                                   label="ca-boundary-2")
    invoice_id = outcome.canonical_invoice.canonical_invoice_id
    before = stack.deriv.derivations_for_normalization(
        outcome.canonical_invoice.normalization_id)
    stack.assembly.assemble(invoice_id, LINE_BINDING)
    after = stack.deriv.derivations_for_normalization(
        outcome.canonical_invoice.normalization_id)
    assert before == after


# ---------------------------------------------------------------------------
# Malformed input / defensive refusals (dispatch axis: malformed input)
# ---------------------------------------------------------------------------

def test_assemble_refuses_none_and_empty_admission_ids(stack):
    stack.build_accepted_lines_admission(unique_line_pages(),
                                         label="ca-boundary-3")
    for bad in (None, "", 123):
        refused = stack.assembly.assemble(bad, LINE_BINDING)
        assert isinstance(refused, AssemblyRequestRefused), (bad, refused)


def test_assembly_module_has_no_public_state_mutation_surface():
    import canonical_assembly as pkg
    for name in pkg.__all__:
        assert not any(tok in name.lower() for tok in
                       ("update", "delete", "mutate", "canonicalize",
                        "admit", "route", "decide")), \
            f"public surface exposes a decision/mutation verb: {name}"
