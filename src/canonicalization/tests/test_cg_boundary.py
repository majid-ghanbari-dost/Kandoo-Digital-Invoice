"""WP-6.1 boundary tests — structural + behavioral probes (SPEC §1/§10/§12;
dispatch axes 19, 20, 24, 25 + malformed input).

Structural proofs: no float, no eval/exec/arbitrary code, allowlisted imports
only, no UPDATE/DELETE anywhere in the store, no fuzzy/similarity libraries,
no product/customer/business matching, no downstream business mutation.
Behavioral proofs: no accidental P5.2/upstream execution (spy-proven), frozen
layers survive gate traffic byte-identically, exact frozen vocabularies in
storage, malformed input refused.
"""
import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cg_helpers import (  # noqa: E402
    BINDING,
    deferred_state,
    decisive_invalid_state,
    tolerance_invalid_state,
    unresolved_state,
)
from canonicalization import (  # noqa: E402
    DECISIONS,
    DECISION_REASONS,
    ORIGINS,
    ORIGIN_HOLOO_CAPTURE,
    CanonicalizationAccepted,
    CanonicalizationRequestRefused,
    CanonicalizationRoutedToReview,
)

CG_PACKAGE = SRC / "canonicalization"

ALLOWED_LOCAL_ROOTS = {"capture", "reconstruction", "extraction",
                       "normalization", "derivation", "validation",
                       "validation_domain", "canonicalization"}
ALLOWED_STDLIB = {"__future__", "dataclasses", "datetime", "sqlite3", "sys",
                  "typing", "uuid"}

# Matching / resolution machinery that must appear NOWHERE in this layer
# (structural no-fuzzy / no-business-matching proof). The gate creates
# Canonical Invoices by design — invoice symbols are NOT forbidden here.
FORBIDDEN_SYMBOLS = ("fuzzywuzzy", "rapidfuzz", "levenshtein", "difflib",
                     "similarity", "sequencematcher", "match_product",
                     "match_customer", "productmatch", "customermatch",
                     "create_sale", "sale(", "create_inventory",
                     "inventory_mut", "kpi_mut", "convert_currency",
                     "issue_digital_invoice", "auto_resolve",
                     "infer_product", "guess_identity", "ocr")


def iter_cg_modules():
    for path in sorted(CG_PACKAGE.glob("*.py")):
        yield path


class TestStructuralAsts:
    @pytest.mark.parametrize("path", list(iter_cg_modules()))
    def test_zero_float_literals(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                pytest.fail(f"float literal {node.value!r} in {path.name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "float":
                pytest.fail(f"float() call in {path.name}")

    @pytest.mark.parametrize("path", list(iter_cg_modules()))
    def test_no_eval_exec_compile_import(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id in ("eval", "exec", "compile",
                                         "__import__"):
                pytest.fail(f"dynamic code execution ({node.func.id}) in "
                            f"{path.name}")

    @pytest.mark.parametrize("path", list(iter_cg_modules()))
    def test_imports_stay_on_declared_allowlist(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                    and node.module:
                names = [node.module.split(".")[0]]
            for root in names:
                if root not in (ALLOWED_LOCAL_ROOTS | ALLOWED_STDLIB):
                    pytest.fail(f"non-allowlisted import {root!r} in "
                                f"{path.name}")

    def test_no_forbidden_business_symbols_anywhere_in_package(self):
        for path in iter_cg_modules():
            text = path.read_text(encoding="utf-8").lower()
            for symbol in FORBIDDEN_SYMBOLS:
                assert symbol not in text, \
                    f"forbidden symbol {symbol!r} in {path.name}"

    def test_store_has_no_update_or_delete_statements(self):
        """OD-C7: no UPDATE and no DELETE SQL statement exists anywhere in
        the store — the durable history is immutable by construction."""
        store_text = (CG_PACKAGE / "store.py").read_text(encoding="utf-8")
        tree = ast.parse(store_text)
        sql_strings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                sql_strings.append(node.value.upper())
        assert sql_strings, "store SQL probe found no statements"
        for sql in sql_strings:
            assert not sql.lstrip().startswith("UPDATE"), \
                "UPDATE statement found in store.py"
            assert not sql.lstrip().startswith("DELETE"), \
                "DELETE statement found in store.py"
            assert " ON CONFLICT" not in sql and "REPLACE INTO" not in sql

    def test_service_public_surface_has_no_resolver_apis(self):
        from canonicalization import CanonicalizationGateService
        public = {name for name in dir(CanonicalizationGateService)
                  if not name.startswith("_")}
        banned = {"resolve_unresolved", "match_product", "match_customer",
                  "create_sale", "issue_digital_invoice", "group_lines",
                  "convert_currency", "auto_resolve", "run_validation",
                  "project_domain_state", "normalize", "derive"}
        assert not (public & banned), public & banned


class TestNoAccidentalUpstreamExecution:
    def test_canonicalize_never_executes_upstream_layers(self, stack,
                                                         monkeypatch):
        """Dispatch axis 24: the gate consumes verified reads only —
        validate/normalize/derive/project are NEVER called (spy-proven)."""
        _, projection = stack.build_valid_identity_state()

        def forbidden(name):
            def _boom(*args, **kwargs):
                raise AssertionError(f"gate executed upstream {name}()")
            return _boom

        monkeypatch.setattr(stack.val, "validate", forbidden("validate"))
        monkeypatch.setattr(stack.norm, "normalize", forbidden("normalize"))
        monkeypatch.setattr(stack.deriv, "derive", forbidden("derive"))
        monkeypatch.setattr(stack.vsm, "project_domain_state",
                            forbidden("project_domain_state"))
        outcome = stack.gate.canonicalize(
            projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, CanonicalizationAccepted), outcome

    def test_replay_never_executes_upstream_layers(self, stack, monkeypatch):
        _, projection = stack.build_valid_identity_state()
        stack.gate.canonicalize(projection.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE, BINDING)

        def forbidden(name):
            def _boom(*args, **kwargs):
                raise AssertionError(f"gate executed upstream {name}()")
            return _boom

        monkeypatch.setattr(stack.val, "validate", forbidden("validate"))
        monkeypatch.setattr(stack.norm, "normalize", forbidden("normalize"))
        monkeypatch.setattr(stack.deriv, "derive", forbidden("derive"))
        monkeypatch.setattr(stack.vsm, "project_domain_state",
                            forbidden("project_domain_state"))
        replay = stack.gate.canonicalize(
            projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
        assert type(replay).__name__ == "CanonicalizationAlreadyDecided"


class TestFrozenLayerProtection:
    def test_gate_traffic_never_inserts_or_deletes_frozen_rows(self, stack):
        """Dispatch axis 20: gate traffic (canonicalize + trace + reads +
        review events) creates and destroys NO frozen-layer record. (The
        frozen layers' own VOR write-on-read — e.g. P1's F-08 verification
        timestamp — is THEIR designed behavior inside a chain walk, never a
        gate write; row counts are the layer-agnostic mutation proof.)"""
        def row_counts():
            import sqlite3
            counts = {}
            targets = [
                (stack.capture_db, "capture_records"),
                (stack.recon_db, "reconstruction_documents"),
                (stack.extraction_db, "extraction_records"),
                (stack.binding_db, "extraction_bindings"),
                (stack.norm_db, "normalization_records"),
                (stack.deriv_db, "derivation_records"),
                (stack.val_db, "validation_records"),
                (stack.vsm_db, "domain_state_records"),
                (stack.vsm_db, "review_queue_items"),
            ]
            for db, table in targets:
                conn = sqlite3.connect(str(db))
                try:
                    counts[f"{db.name}:{table}"] = conn.execute(
                        f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                finally:
                    conn.close()
            return counts

        _, projection = stack.build_valid_identity_state()
        state_id = projection.record.domain_state_id
        before = row_counts()
        outcome = stack.gate.canonicalize(state_id, ORIGIN_HOLOO_CAPTURE,
                                          BINDING)
        assert isinstance(outcome, CanonicalizationAccepted), outcome
        stack.gate.trace_canonical_invoice(
            outcome.canonical_invoice.canonical_invoice_id)
        stack.gate.read_gate_decision(outcome.decision.decision_id)
        stack.gate.canonicalize(state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
        after = row_counts()
        assert before == after

    def test_gate_writes_only_into_its_own_store(self, stack):
        """The gate store's tables live only in the gate DB — the P5.2 DB has
        no gate tables, and vice versa."""
        outcome = None
        _, projection = stack.build_valid_identity_state()
        outcome = stack.gate.canonicalize(
            projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, CanonicalizationAccepted), outcome
        import sqlite3
        vsm_conn = sqlite3.connect(str(stack.vsm_db))
        gate_conn = sqlite3.connect(str(stack.gate_db))
        try:
            vsm_tables = {r[0] for r in vsm_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
            gate_tables = {r[0] for r in gate_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            vsm_conn.close()
            gate_conn.close()
        assert "gate_decisions" not in vsm_tables
        assert "canonical_invoices" not in vsm_tables
        assert "domain_state_records" not in gate_tables


class TestFrozenVocabularySweep:
    def test_store_never_holds_invented_decisions_or_origins(self, stack):
        _, valid = stack.build_valid_identity_state()
        stack.gate.canonicalize(valid.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE, BINDING)
        _, invalid = decisive_invalid_state(stack)
        stack.gate.canonicalize(invalid.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE)
        _, defer = deferred_state(stack)
        stack.gate.canonicalize(defer.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE)
        _, unres = unresolved_state(stack)
        stack.gate.canonicalize(unres.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE)
        _, tol = tolerance_invalid_state(stack)
        stack.gate.canonicalize(tol.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE)
        import sqlite3
        conn = sqlite3.connect(str(stack.gate_db))
        try:
            decisions = {r[0] for r in conn.execute(
                "SELECT DISTINCT decision FROM gate_decisions")}
            origins = {r[0] for r in conn.execute(
                "SELECT DISTINCT declared_origin FROM gate_decisions")} | \
                {r[0] for r in conn.execute(
                    "SELECT DISTINCT origin FROM canonical_invoices")}
            identity_classes = {r[0] for r in conn.execute(
                "SELECT DISTINCT identity_class FROM gate_decisions")}
            events = {r[0] for r in conn.execute(
                "SELECT DISTINCT event_type FROM gate_review_events")}
            pointers = {r[0] for r in conn.execute(
                "SELECT DISTINCT role FROM canonical_identity_pointers")}
        finally:
            conn.close()
        assert decisions <= set(DECISIONS)
        assert origins <= set(ORIGINS)
        assert identity_classes <= {"", "DETERMINISTIC", "CAPTURE_SCOPED"}
        assert events <= {"ANNOTATE", "CLOSE"}
        assert pointers == {"INVOICE_NUMBER", "INVOICE_DATE",
                            "INVOICE_TOTAL"}

    def test_decision_reasons_come_only_from_declared_codes(self, stack):
        _, valid = stack.build_valid_identity_state()
        stack.gate.canonicalize(valid.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE, BINDING)
        _, invalid = decisive_invalid_state(stack)
        stack.gate.canonicalize(invalid.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE)
        _, tol = tolerance_invalid_state(stack)
        stack.gate.canonicalize(tol.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE)
        _, unres = unresolved_state(stack)
        stack.gate.canonicalize(unres.record.domain_state_id,
                                ORIGIN_HOLOO_CAPTURE)
        import sqlite3
        conn = sqlite3.connect(str(stack.gate_db))
        try:
            reasons = {r[0] for r in conn.execute(
                "SELECT DISTINCT decision_reason FROM gate_decisions")}
        finally:
            conn.close()
        assert reasons <= set(DECISION_REASONS)


class TestMalformedInput:
    def test_none_state_id_is_refused(self, stack):
        outcome = stack.gate.canonicalize(None, ORIGIN_HOLOO_CAPTURE, BINDING)
        assert type(outcome).__name__ == "CanonicalizationRequestRefused", \
            outcome

    def test_none_origin_is_refused(self, stack):
        _, projection = stack.build_valid_identity_state()
        outcome = stack.gate.canonicalize(
            projection.record.domain_state_id, None, BINDING)
        assert type(outcome).__name__ == "CanonicalizationRequestRefused", \
            outcome

    def test_integer_origin_is_refused(self, stack):
        _, projection = stack.build_valid_identity_state()
        outcome = stack.gate.canonicalize(
            projection.record.domain_state_id, 42, BINDING)
        assert type(outcome).__name__ == "CanonicalizationRequestRefused", \
            outcome

    def test_binding_with_list_value_is_refused(self, stack):
        _, projection = stack.build_valid_identity_state()
        outcome = stack.gate.canonicalize(
            projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE,
            {"INVOICE_NUMBER": ["a"], "INVOICE_DATE": "b",
             "INVOICE_TOTAL": "c"})
        assert type(outcome).__name__ == "CanonicalizationRequestRefused", \
            outcome

    def test_refusals_leave_zero_residue(self, stack):
        before = len(stack.gate.decisions())
        stack.gate.canonicalize(None, ORIGIN_HOLOO_CAPTURE, BINDING)
        stack.gate.canonicalize("ghost", "NOT_AN_ORIGIN", BINDING)
        _, projection = stack.build_valid_identity_state()
        stack.gate.canonicalize(projection.record.domain_state_id,
                                "KANDOO_SALE", BINDING)
        assert len(stack.gate.decisions()) == before
        assert len(stack.gate.canonical_invoices()) == 0
        assert stack.gate.issue_reports() == []


class TestReviewBoundary:
    def test_gate_review_queue_never_resolves_anything(self, stack):
        """The queue holds uncertainty; nothing in the lifecycle changes the
        gate decision, the P5.2 state, or creates an invoice."""
        _, projection = stack.build_valid_identity_state()
        outcome = stack.gate.canonicalize(
            projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
        assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
        review_id = outcome.review_item.review_id
        stack.gate.append_gate_review_event(review_id, "ANNOTATE",
                                            "inspected", "op-1")
        closed = stack.gate.append_gate_review_event(review_id, "CLOSE",
                                                     "handled", "supervisor")
        assert type(closed).__name__ == "GateEventAppended", closed
        # the decision is unchanged; no invoice appeared
        dread = stack.gate.read_gate_decision(outcome.decision.decision_id)
        assert type(dread).__name__ == "GateDecisionReadSuccess"
        assert dread.record.decision == "REVIEW"
        assert len(stack.gate.canonical_invoices()) == 0

    def test_unknown_event_type_refused(self, stack):
        from cg_helpers import deferred_state
        _, projection = deferred_state(stack)
        outcome = stack.gate.canonicalize(
            projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE)
        assert isinstance(outcome, CanonicalizationRoutedToReview), outcome
        refused = stack.gate.append_gate_review_event(
            outcome.review_item.review_id, "RESOLVE", "auto", "bot")
        assert type(refused).__name__ == "GateEventRefused", refused
