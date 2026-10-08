"""Boundary behavior tests — WP-5.2 (SPEC-WP52-VSM §1/§11/§13).

Structural proofs: no float, no eval/exec/arbitrary code, no engine coupling,
no Canonicalization behavior, no business-semantic inference, no automatic
semantic resolution, no product/customer matching, no Canonical Invoice
creation, exact frozen vocabulary in storage — and the frozen layers survive
domain-state traffic byte-identically.
"""
import ast
import importlib
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validation_domain import (  # noqa: E402
    DomainStateReadSuccess,
    DomainStateTraceSuccess,
)

from vsm_helpers import (  # noqa: E402
    PAGE_MISSING_TAX,
    PAGE_OK,
    R_TOLERANCE,
)

VSM_PACKAGE = SRC / "validation_domain"

ALLOWED_LOCAL_ROOTS = {"capture", "reconstruction", "extraction", "normalization",
                       "derivation", "validation", "validation_domain"}

# Canonical Invoice / business creation vocabulary that must appear NOWHERE in
# this layer's code (structural no-creation proof).
FORBIDDEN_SYMBOLS = ("canonicalinvoice", "sale(", "digitalinvoice", "issuance",
                     "inventory", "productmatch", "customermatch", "fuzzymatch")


def iter_vsm_modules():
    for path in sorted(VSM_PACKAGE.glob("*.py")):
        yield path


class TestNoFloatAndNoArbitraryCode:
    @pytest.mark.parametrize("path", list(iter_vsm_modules()))
    def test_zero_float_literals(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                pytest.fail(f"float literal {node.value!r} in {path.name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "float":
                pytest.fail(f"float() call in {path.name}")

    @pytest.mark.parametrize("path", list(iter_vsm_modules()))
    def test_no_eval_exec_compile_import(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id in ("eval", "exec", "compile", "__import__"):
                pytest.fail(f"dynamic code execution ({node.func.id}) in "
                            f"{path.name}")

    @pytest.mark.parametrize("path", list(iter_vsm_modules()))
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
                if root not in (ALLOWED_LOCAL_ROOTS | {
                        "__future__", "dataclasses", "datetime", "sqlite3",
                        "sys", "typing", "uuid"}):
                    pytest.fail(f"non-allowlisted import {root!r} in {path.name}")

    def test_no_forbidden_business_symbols_anywhere_in_package(self):
        for path in iter_vsm_modules():
            text = path.read_text(encoding="utf-8").lower()
            for symbol in FORBIDDEN_SYMBOLS:
                assert symbol not in text, \
                    f"forbidden symbol {symbol!r} in {path.name}"


class TestFrozenVocabularySweep:
    def test_store_never_holds_invented_states(self, stack):
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        stack.project(nid, [(R_TOLERANCE, "1")], ruleset_id="kandoo-vsm-sweep")
        import sqlite3
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            states = {r[0] for r in conn.execute(
                "SELECT DISTINCT domain_state FROM domain_state_records")}
            dispositions = {r[0] for r in conn.execute(
                "SELECT DISTINCT disposition FROM domain_state_records")}
            projections = {r[0] for r in conn.execute(
                "SELECT DISTINCT projection_status FROM domain_state_fields")}
            events = {r[0] for r in conn.execute(
                "SELECT DISTINCT event_type FROM review_queue_events")}
        finally:
            conn.close()
        assert states <= {"VALID", "INVALID", "DEFERRED", "UNRESOLVED"}
        assert dispositions <= {"CLEAR", "REVIEW", "REJECT"}
        assert projections <= {"RESOLVED", "UNRESOLVED"}
        assert events <= {"ANNOTATE", "CLOSE"}

    def test_review_reasons_come_only_from_route_codes(self, stack):
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        stack.project(nid, [(R_TOLERANCE, "1")], ruleset_id="kandoo-vsm-sweep2")
        import sqlite3
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            reasons = {r[0] for r in conn.execute(
                "SELECT DISTINCT review_reason FROM review_queue_items")}
        finally:
            conn.close()
        assert reasons <= {"d08-mismatch-review", "d01-unresolved-review",
                           "validation-deferred-review"}


class TestNoSemanticResolution:
    def test_unresolved_projection_is_never_auto_resolved(self, stack):
        """An UNRESOLVED projection stays UNRESOLVED through any number of
        reads/traces; the queue has no resolver path at all."""
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-nores")
        state_id = projected.record.domain_state_id
        for _ in range(3):
            read = stack.vsm.read_domain_state(state_id)
            assert type(read).__name__ == "DomainStateReadSuccess"
            assert read.record.domain_state == "UNRESOLVED"
            assert read.review_status == "OPEN"
        walk = stack.vsm.trace_domain_state(state_id)
        assert isinstance(walk, DomainStateTraceSuccess)

    def test_ambiguous_input_never_silently_picks(self, stack):
        """With two candidates, the projection records candidate_count=2 — it
        NEVER picks one and NEVER creates a resolved pointer for the pair."""
        from vsm_helpers import PAGE_AMBIGUOUS
        nid = stack.build_normalization(PAGE_AMBIGUOUS)
        stack.val.validate(nid, "vsm-probe-tolerance-ambiguous", "1")
        projected = stack.project(nid, [("vsm-probe-tolerance-ambiguous", "1")],
                                  ruleset_id="kandoo-vsm-amb-nopick")
        fields = {r.field_name: r for r in projected.field_projections}
        row = fields["total.net"]
        assert row.candidate_count == 2
        assert row.detail.count("Canonicalization Gate") >= 1

    def test_service_exposes_no_resolution_api(self):
        """The public surface has no resolve/match/canonicalize method."""
        from validation_domain import ValidationDomainService
        public = {name for name in dir(ValidationDomainService)
                  if not name.startswith("_")}
        banned = {"resolve", "resolve_unresolved", "match_product",
                  "match_customer", "canonicalize", "create_invoice",
                  "create_sale", "issue_digital_invoice", "group_lines",
                  "convert_currency"}
        assert not (public & banned), public & banned


class TestNoCanonicalizationBehavior:
    def test_projection_never_maps_or_invents_field_names(self, stack):
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        projected = stack.project(nid, [(R_TOLERANCE, "1")],
                                  ruleset_id="kandoo-vsm-nomap")
        # projected fields == exactly the DECLARED ruleset fields — no more
        declared = {"total.net", "tax.amount", "total.gross"}
        projected_names = {r.field_name for r in projected.field_projections}
        assert projected_names == declared

    def test_projection_triggers_no_upstream_execution(self, stack, monkeypatch):
        """The projection MUST NOT call validate/derive/normalize — it only
        reads. Spy on the upstream execution entry points."""
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")

        calls = []
        for obj, name in ((stack.val, "validate"), (stack.deriv, "derive"),
                          (stack.norm, "normalize")):
            def spy(*args, _name=name, _orig=getattr(obj, name), **kwargs):
                calls.append(_name)
                return _orig(*args, **kwargs)
            monkeypatch.setattr(obj, name, spy)
        stack.project(nid, [(R_TOLERANCE, "1")], ruleset_id="kandoo-vsm-idle")
        assert calls == []

    def test_no_canonical_invoice_identity_created(self, stack):
        """Nothing in the domain store resembles an invoice identity: no
        invoice_id column, no canonical id — only pointers to upstream ids."""
        nid = stack.build_normalization(PAGE_MISSING_TAX)
        stack.val.validate(nid, R_TOLERANCE, "1")
        stack.project(nid, [(R_TOLERANCE, "1")], ruleset_id="kandoo-vsm-noid")
        import sqlite3
        conn = sqlite3.connect(str(stack.vsm_db))
        try:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})")]
                assert not any("invoice" in c.lower() for c in cols), \
                    f"{table} carries an invoice-like column: {cols}"
        finally:
            conn.close()


class TestFrozenLayerSurvival:
    REF_KEYS_FULL = [("kandoo-val-total-net-present", "1"),
                     ("kandoo-val-total-gross-consistency", "1"),
                     ("kandoo-val-total-gross-tolerance", "1"),
                     ("kandoo-val-total-gross-rounded", "1")]

    def test_frozen_layers_survive_domain_traffic(self, stack):
        """After projection + REVIEW traffic: capture replay, verified reads,
        extraction verbatim, binding, declared-grammar outputs, derivation
        replay, P5.1 replay — all intact."""
        from capture import CaptureService, IngestCompleted
        from derivation import DerivationCompleted
        from extraction import BindingReadSuccess
        from validation import ValidationAlreadyExists

        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        stack.project(nid, self.REF_KEYS_FULL)
        review = stack.vsm.list_review_items()

        # capture idempotency intact
        outcome = stack.capture.ingest(CaptureService.aggregate(PAGE_OK),
                                       source_label="survival")
        assert isinstance(outcome, IngestCompleted) or \
            type(outcome).__name__ == "IngestDuplicateAtCapture"
        # normalization verified read intact
        read = stack.norm.read_normalization(nid)
        assert type(read).__name__ == "NormalizationReadSuccess"
        # P5.1 replay intact
        replay = stack.val.validate(nid, "kandoo-val-total-net-present", "1")
        assert isinstance(replay, ValidationAlreadyExists)
        # derivation replay intact
        again = stack.deriv.derive(nid, "kandoo-der-total-gross-from-net-tax",
                                   "1")
        assert isinstance(again, DerivationCompleted) or \
            type(again).__name__ == "DerivationAlreadyExists"
        # binding verified read intact
        ext_read = stack.extraction.read_extraction(
            stack.norm.read_normalization(nid).record.extraction_id)
        bound = stack.binder.read_binding(ext_read.extraction.extraction_id)
        assert type(bound).__name__ == "BindingReadSuccess"

    def test_no_upstream_store_mutation_from_projection(self, stack):
        """Byte-level: projecting does not touch any upstream DB file."""
        import hashlib
        nid = stack.build_derived(PAGE_OK)
        stack.validate_all_reference(nid)
        digests_before = {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in self._survival_paths(stack)
        }
        stack.project(nid, self.REF_KEYS_FULL,
                      ruleset_id="kandoo-vsm-bytes")
        digests_after = {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in digests_before
        }
        assert digests_before == digests_after

    @staticmethod
    def _survival_paths(stack):
        paths = [stack.capture_db, stack.recon_db, stack.extraction_db,
                 stack.binding_db, stack.norm_db, stack.deriv_db, stack.val_db]
        evidence = Path(str(stack.recon_db) + ".evidence.db")
        if evidence.exists():
            paths.append(evidence)
        return [Path(p) for p in paths]

    def test_no_engine_symbol_coupling(self):
        """No engine module symbol is imported anywhere in this layer."""
        for path in iter_vsm_modules():
            text = path.read_text(encoding="utf-8")
            assert "ReferenceDelimitedEngine" not in text, path.name
            assert "ExtractionEngine" not in text, path.name
            assert "import extraction.engine" not in text, path.name
