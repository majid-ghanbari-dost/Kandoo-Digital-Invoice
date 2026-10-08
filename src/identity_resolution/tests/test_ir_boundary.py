"""WP-7.1 boundary tests — structural AST proofs, frozen vocabulary,
frozen-layer protection, consumed-not-bypassed discipline (SPEC §1/§12;
dispatch §12 structural axes)."""
import ast
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LAYER_DIR = SRC / "identity_resolution"
LAYER_FILES = sorted(LAYER_DIR.glob("*.py"))

from ir_helpers import (  # noqa: E402
    BINDING,
    IdentityResolutionRecorded,
    ORIGIN_HOLOO_CAPTURE,
    unique_ir_pages,
)

from identity_resolution import (  # noqa: E402
    CAPTURE_SCOPED_REASONS,
    IDENTITY_ROLES,
    IDENTITY_SCOPES,
    IDENTITY_SOURCES,
    ORIGINS,
)


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _strings_in(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _identifiers_in(tree):
    """All code identifiers — docstrings legitimately DECLARE the boundaries
    (e.g. 'NO fuzzy matching'), so the sweep runs over identifiers, not
    prose."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.arg)):
            name = node.id if hasattr(node, "id") else getattr(
                node, "attr", None) or getattr(node, "name", None)
            if name:
                yield name.lower()


# ---------------------------------------------------------------------------
# Structural proof — no UPDATE / DELETE / DROP in the layer
# ---------------------------------------------------------------------------

def test_no_update_delete_or_drop_statement_anywhere_in_the_layer():
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
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lowered = node.name.lower()
                for forbidden in ("update", "delete", "mutate", "amend",
                                  "rewrite", "drop_"):
                    assert not lowered.startswith(forbidden), \
                        f"{path.name}: function {node.name!r} looks like a " \
                        f"mutation path"


def test_no_randomness_no_exec_no_float_literals():
    """uuid is ALLOWED for bookkeeping ids ONLY (P6.1 OD-IR4/OD-C4 pattern);
    the identity itself is always the deterministic sha256-v1 fingerprint —
    proven behaviorally in test_ir_service.py."""
    forbidden_modules = {"random", "secrets", "eval", "exec", "pickle",
                         "ctypes", "subprocess", "socket", "http", "urllib"}
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                root = node.names[0].name.split(".")[0]
                assert root not in forbidden_modules, \
                    f"{path.name}: forbidden import {root}"
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in forbidden_modules, \
                    f"{path.name}: forbidden import-from {root}"
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, float):
                    pytest.fail(f"{path.name}: float literal {node.value}")


def test_uuid_is_confined_to_bookkeeping_id_assignment():
    """uuid appears only in service.py, only assigned to resolution_id /
    observation_id (bookkeeping) — never to a fingerprint field."""
    uuid_files = [p.name for p in LAYER_FILES
                  if any(isinstance(n, ast.Import) and
                         n.names[0].name == "uuid"
                         for n in ast.walk(_tree(p)))]
    assert uuid_files == ["service.py"]
    service_source = (LAYER_DIR / "service.py").read_text(encoding="utf-8")
    assert "uuid.uuid4().hex" in service_source
    for anchored in ("identity_fingerprint=uuid", "fingerprint=uuid"):
        assert anchored not in service_source


def test_import_allowlist_project_layers_only():
    allowed_roots = {"__future__", "dataclasses", "typing", "datetime",
                     "sqlite3", "uuid", "capture", "normalization",
                     "derivation", "validation", "validation_domain",
                     "canonicalization", "identity_resolution"}
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


def test_no_fuzzy_or_semantic_or_business_matching_symbols():
    forbidden = ("fuzzy", "similarity", "levenshtein", "difflib",
                 "match_product", "product_match", "customer_match",
                 "auto_create", "ocr", "semantic", "tax_rate",
                 "currency_convert", "exchange_rate", "posting",
                 "inventory", "kpi", "heuristic")
    for path in LAYER_FILES:
        tree = _tree(path)
        for ident in _identifiers_in(tree):
            for token in forbidden:
                assert token not in ident, \
                    f"{path.name}: forbidden identifier {ident!r} " \
                    f"(contains {token!r})"


def test_identity_formula_is_reused_not_reimplemented():
    """OD-IR-G: the frozen P6.1 primitive is the ONLY identity formula —
    resolver.py delegates to it; the layer defines no fingerprint of the S2
    values itself."""
    from identity_resolution import resolver
    import inspect
    source = inspect.getsource(resolver)
    assert "resolve_identity" in source
    assert "canonicalization.identity import resolve_identity" in source
    # no local sha256/hashing of identity values anywhere in the layer
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert node.names[0].name != "hashlib", \
                    f"{path.name}: hashlib import — fingerprints must ride " \
                    f"the S1 capability, not local hashing"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "") != "hashlib", \
                    f"{path.name}: hashlib import-from"


def test_no_direct_sql_against_upstream_or_gate_tables():
    own_tables = {"identity_resolutions", "identity_role_candidates",
                  "identity_duplicate_observations"}
    forbidden_tables = {"gate_decisions", "canonical_invoices",
                        "canonical_identity_pointers", "gate_review_items",
                        "domain_state_records", "normalization_records",
                        "extraction_records", "extraction_bindings",
                        "capture_records", "validation_records"}
    for path in LAYER_FILES:
        for value in _strings_in(_tree(path)):
            for table in forbidden_tables:
                assert table not in value, \
                    f"{path.name}: direct reference to foreign table " \
                    f"{table!r}"
    store_tokens = set()
    for v in _strings_in(_tree(LAYER_DIR / "store.py")):
        store_tokens.update(v.replace("(", " ").replace(",", " ").split())
    assert own_tables.issubset(store_tokens)


def test_no_invoice_identity_in_this_layer():
    """OD-IR-I: the Canonical Identity (invoice_id) is P6.1/P6.2 property —
    no invoice columns, no minting surface."""
    for value in _strings_in(_tree(LAYER_DIR / "store.py")):
        assert "invoice_id" not in value
        assert "canonical_invoice" not in value
    for ident in _identifiers_in(_tree(LAYER_DIR / "service.py")):
        assert "invoice" not in ident
    service = {m for m in dir(__import__(
        "identity_resolution.service", fromlist=["x"])
        .IdentityResolutionService) if not m.startswith("_")}
    assert service == {"resolve", "read_resolution",
                       "read_resolution_by_capture"}


def test_vocabulary_constants_are_verbatim():
    assert IDENTITY_SCOPES == ("S2", "CAPTURE_SCOPED")
    assert IDENTITY_SOURCES == ("", "S2_EXTRACTED_VERIFIED")
    assert IDENTITY_ROLES == ("INVOICE_NUMBER", "INVOICE_DATE",
                              "INVOICE_TOTAL")
    assert ORIGINS == ("KANDOO_SALE", "HOLOO_CAPTURE",
                       "OTHER_POS_CAPTURE")
    assert CAPTURE_SCOPED_REASONS == (
        "d03-incomplete-document-identity",
        "d03-conflicting-document-identity",
        "d03-document-identity-undetermined",
        "s2-not-attempted-state-not-valid")


def test_public_surface_has_no_decision_or_mutation_verbs():
    import identity_resolution as pkg
    for name in pkg.__all__:
        lowered = name.lower()
        for token in ("canonicalize", "admit", "route", "decide", "update",
                      "delete", "issue", "assemble"):
            assert token not in lowered, \
                f"public surface exposes a decision/mutation verb: {name}"


# ---------------------------------------------------------------------------
# Frozen-layer protection — the layer mutates NOTHING upstream
# ---------------------------------------------------------------------------

def test_row_count_stability_of_frozen_stores_during_resolve(stack):
    _, projection = stack.build_valid_identity_state(label="ir-boundary-rc")
    head = stack.vsm.read_domain_state(projection.record.domain_state_id)

    def counts():
        rows = {}
        conns = {
            "capture": (stack.capture_db, "capture_records"),
            "recon": (stack.recon_db, "documents"),
            "norm": (stack.norm_db, "normalization_records"),
            "deriv": (stack.deriv_db, "derivation_records"),
            "vsm": (stack.vsm_db, "domain_state_records"),
        }
        for key, (db, table) in conns.items():
            conn = sqlite3.connect(str(db))
            try:
                rows[key] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                rows[key] = None          # table name varies per layer
            finally:
                conn.close()
        return rows

    before = counts()
    outcome = stack.identity.resolve(projection.record.domain_state_id,
                                     ORIGIN_HOLOO_CAPTURE, BINDING)
    assert isinstance(outcome, IdentityResolutionRecorded)
    # a replay too — the frozen stores stay untouched either way
    stack.identity.resolve(projection.record.domain_state_id,
                           ORIGIN_HOLOO_CAPTURE, BINDING)
    assert counts() == before
    assert head.record.capture_s1 == projection.record.capture_s1


def test_spy_zero_upstream_execution_during_resolve(stack):
    """resolve() NEVER executes any upstream layer — only the verified read
    + the trace + (for VALID states) the verified normalization read."""
    calls = []
    inner_vsm, inner_norm = stack.vsm, stack.norm

    class SpyVSM:
        def __getattr__(self, name):
            return getattr(inner_vsm, name)

        def project_domain_state(self, *a, **k):
            calls.append("project_domain_state")
            return inner_vsm.project_domain_state(*a, **k)

    class SpyNorm:
        def __getattr__(self, name):
            return getattr(inner_norm, name)

        def normalize(self, *a, **k):
            calls.append("normalize")
            return inner_norm.normalize(*a, **k)

        def read_normalization(self, *a, **k):
            calls.append("read_normalization")
            return inner_norm.read_normalization(*a, **k)

    stack.identity._domain = SpyVSM()
    stack.identity._normalization = SpyNorm()
    try:
        _, projection = stack.build_valid_identity_state(
            label="ir-boundary-spy")
        calls.clear()
        outcome = stack.identity.resolve(projection.record.domain_state_id,
                                         ORIGIN_HOLOO_CAPTURE, BINDING)
        assert isinstance(outcome, IdentityResolutionRecorded)
        assert calls == ["read_normalization"]          # read-only value path
        calls.clear()
        stack.identity.resolve(projection.record.domain_state_id,
                               ORIGIN_HOLOO_CAPTURE, BINDING)
        assert calls == []                              # replay: zero reads
    finally:
        stack.identity._domain = inner_vsm
        stack.identity._normalization = inner_norm


def test_identity_fingerprint_is_content_deterministic_across_stacks(
        make_stack, tmp_path):
    """The SAME verified inputs yield the SAME identity fingerprint on two
    independent stacks — bookkeeping ids differ, the identity never does."""
    fingerprints = []
    parts = unique_ir_pages()          # ONE document, replayed on both stacks
    for run in range(2):
        base = tmp_path / f"run{run}"
        base.mkdir()
        stack = IdentityResolutionStackForBoundary(base)
        try:
            _, projection = stack.build_valid_identity_state(
                parts=parts, label=f"ir-boundary-det-{run}")
            outcome = stack.identity.resolve(
                projection.record.domain_state_id, ORIGIN_HOLOO_CAPTURE,
                BINDING)
            assert isinstance(outcome, IdentityResolutionRecorded)
            fingerprints.append((outcome.record.identity_fingerprint,
                                 outcome.record.resolution_id))
        finally:
            stack.close()
    assert fingerprints[0][0] == fingerprints[1][0]   # same identity
    assert fingerprints[0][1] != fingerprints[1][1]   # bookkeeping differs


def IdentityResolutionStackForBoundary(base):   # noqa: N802 (local factory)
    from ir_helpers import IdentityResolutionStack
    return IdentityResolutionStack(
        base / "capture.db", base / "recon.db", base / "extraction.db",
        base / "bindings.db", base / "norm.db", base / "deriv.db",
        base / "val.db", base / "vsm.db", base / "identity.db")
