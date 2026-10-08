"""WP-8.1 boundary tests — structural AST proofs, pointer discipline, the
declared-input surface, frozen vocabulary, frozen-layer protection, and the
UNIQUE backstops (SPEC §1/§7; OD-PM1..PM8)."""
import ast
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LAYER_DIR = SRC / "product_candidate"
LAYER_FILES = sorted(LAYER_DIR.glob("*.py"))

from pc_helpers import (  # noqa: E402
    PC_FIELD_0,
    PC_KIND,
    ProductCandidateStack,
)
from product_candidate import (  # noqa: E402
    DURABLE_MATCH_OUTCOMES,
    DURABLE_UNRESOLVED_REASONS,
    PROVENANCES,
    ProductCandidateStore,
)


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _strings_in(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _identifiers_in(tree):
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
                                  "rewrite", "drop_", "merge_", "rescind"):
                    assert not lowered.startswith(forbidden), \
                        f"{path.name}: function {node.name!r} looks like a " \
                        f"mutation path"


def test_no_randomness_no_exec_no_float_literals():
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
    uuid_files = [p.name for p in LAYER_FILES
                  if any(isinstance(n, ast.Import) and
                         n.names[0].name == "uuid"
                         for n in ast.walk(_tree(p)))]
    assert uuid_files == ["service.py"]
    service_source = (LAYER_DIR / "service.py").read_text(encoding="utf-8")
    assert "uuid.uuid4().hex" in service_source
    # uuid appears ONLY as `..._id=uuid.uuid4().hex` bookkeeping seeds —
    # never inside any fingerprint payload (those ride the S1 capability
    # in store.py, where uuid does not appear at all).
    uuid_lines = [ln for ln in service_source.splitlines() if "uuid" in ln]
    assert uuid_lines == [
        "import uuid",
        "            catalog_identity_id=uuid.uuid4().hex,",
        "            match_id=uuid.uuid4().hex,",
    ], uuid_lines
    store_source = (LAYER_DIR / "store.py").read_text(encoding="utf-8")
    assert "uuid" not in store_source


def test_import_allowlist_project_layers_only():
    """The matching layer may import the project layers it consumes — and it
    consumes ONLY canonical_assembly (plus capture for the S1 hashing
    capability). No canonicalization / identity_resolution / duplicate_flows
    import: their semantics never leak in (OD-PM8)."""
    allowed_roots = {"__future__", "dataclasses", "typing", "datetime",
                     "sqlite3", "uuid", "capture", "canonical_assembly"}
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


def test_no_hashlib_and_no_identity_formula_in_the_layer():
    """The only hashing in this layer is the record-integrity anchor via the
    project S1 service (OD-PM1); no identity/canonicalization formula of any
    kind exists here."""
    for path in LAYER_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert node.names[0].name != "hashlib", \
                    f"{path.name}: hashlib import — record anchors ride " \
                    f"the S1 capability, not local hashing"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "") != "hashlib", \
                    f"{path.name}: hashlib import-from"
    store_source = (LAYER_DIR / "store.py").read_text(encoding="utf-8")
    assert "sha256(" not in store_source
    assert "sha256(" not in (LAYER_DIR / "service.py").read_text(
        encoding="utf-8")


def test_no_fuzzy_or_semantic_or_candidate_or_customer_symbols():
    """D-05/OD-PM7 + Mission dispatch: NO fuzzy/semantic/AI/confidence/
    approval/candidate-generation/customer surface exists — not as a symbol,
    not as a path. ('candidate' as a plain local noun for lookup rows is
    deliberately absent too: the exact lookup names its rows `candidates`
    NOWHERE — the store returns rows, the service counts them.)"""
    forbidden = ("fuzzy", "similarity", "levenshtein", "difflib",
                 "confidence", "approv", "semantic", "score", "threshold",
                 "auto_create", "autocreate", "ocr", "heuristic",
                 "customer", "occurrence", "promot", "ml_", "ai_",
                 "neural", "rank_")
    for path in LAYER_FILES:
        for ident in _identifiers_in(_tree(path)):
            for token in forbidden:
                assert token not in ident, \
                    f"{path.name}: forbidden identifier {ident!r} " \
                    f"(contains {token!r})"


def test_no_barcode_grammar_or_checksum_symbols():
    """OD-PM3: identifier kinds/values are DECLARED opaque strings — no
    enumeration, no format grammar, no checksum, no normalization."""
    forbidden = ("ean_checksum", "upc", "gs1", "check_digit", "checksum",
                 "isbn", "gtin", "modulo", "luhn", "regex", "re_match",
                 "pattern", "grammar", "normalize_identifier",
                 "fold_case", "casefold")
    for path in LAYER_FILES:
        for ident in _identifiers_in(_tree(path)):
            for token in forbidden:
                assert token not in ident, \
                    f"{path.name}: forbidden identifier {ident!r} " \
                    f"(contains {token!r})"


def test_no_canonicalization_or_review_or_customer_semantics():
    """OD-PM8: no gate/canonicalization/REVIEW vocabulary is decided or
    annotated here, no customer anything (WP-9.1), and no foreign table is
    referenced by SQL."""
    own_tables = {"catalog_identities", "product_matches"}
    forbidden_tables = {"gate_decisions", "canonical_invoices",
                        "canonical_identity_pointers", "gate_review_items",
                        "domain_state_records", "normalization_records",
                        "extraction_records", "extraction_bindings",
                        "capture_records", "validation_records",
                        "identity_resolutions",
                        "identity_duplicate_observations",
                        "identity_role_candidates", "customer_identities",
                        "customer_links", "flow_dispositions"}
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


def test_vocabulary_constants_are_verbatim():
    assert DURABLE_MATCH_OUTCOMES == ("EXACT_MATCHED", "UNRESOLVED")
    assert DURABLE_UNRESOLVED_REASONS == ("no-catalog-identity",)
    assert PROVENANCES == ("EXTRACTED", "DERIVED")


def test_storage_schema_enforces_pointer_discipline_and_outcome_shape():
    """OD-PM6: the match row carries NO value column (the identifier value
    lives in the verified P6.2 read and in the catalog's own registered
    content); the CHECK gates pin the outcome shapes and the stable
    UNRESOLVED reason."""
    from product_candidate import store as store_module
    schema = store_module._SCHEMA
    assert "canonical_value" not in schema.split(
        "CREATE TABLE IF NOT EXISTS product_matches")[1].split(")")[0]
    assert "identifier_value" not in schema.split(
        "CREATE TABLE IF NOT EXISTS product_matches")[1].split(")")[0]
    assert "no-catalog-identity" in schema
    assert "identifier_value" in schema.split(
        "CREATE TABLE IF NOT EXISTS catalog_identities")[1].split(")")[0]


def test_public_surface_has_no_decision_or_mutation_verbs():
    import product_candidate as pkg
    for name in pkg.__all__:
        lowered = name.lower()
        # NB: UNRESOLVED is this layer's own declared D-05 outcome word
        # (SPEC §5 / OD-PM7) — the verb "resolve" is therefore not a forbidden
        # substring; every actual decision/mutation verb is.
        for token in ("canonicalize", "admit", "route", "decide", "update",
                      "delete", "issue", "assemble", "close_review",
                      "generate", "approve", "score", "replay_", "_replay"):
            assert token not in lowered, \
                f"public surface exposes a decision/mutation verb: {name}"


def test_registration_api_carries_no_capture_or_invoice_parameter():
    """OD-PM2: the ONLY catalog write path takes (identifier_kind,
    identifier_value) — no capture/invoice/document parameter exists, so
    capture-derived catalog mutation is structurally impossible."""
    import inspect
    from product_candidate import ProductCandidateService
    sig = inspect.signature(
        ProductCandidateService.register_catalog_identity)
    params = [p for p in sig.parameters if p != "self"]
    assert params == ["identifier_kind", "identifier_value"]
    # and the service holds no capture/reconstruction/extraction handle at all
    init_params = [p for p in inspect.signature(
        ProductCandidateService.__init__).parameters if p != "self"]
    assert init_params == ["store", "assembly", "s1"]


# ---------------------------------------------------------------------------
# Behavioral boundary — adversarial inputs stay refused / unresolved
# ---------------------------------------------------------------------------

def test_unique_declaration_backstop_is_a_real_database_constraint(stack):
    stack.register("SKU", "SKU-A-001")
    _, invoice_id = stack.assemble_products_invoice(label="pm-bnd-uniq")
    stack.match(invoice_id, PC_FIELD_0, PC_KIND)
    conn = sqlite3.connect(str(stack.product_db))
    try:
        try:
            conn.execute(
                "INSERT INTO product_matches (match_id, invoice_id, "
                "capture_s1, capture_s1_algorithm_id, declared_field_name, "
                "canonical_seq, provenance, identifier_kind, match_outcome, "
                "catalog_identity_id, unresolved_reason, created_at, "
                "record_fingerprint, fingerprint_algorithm_id) VALUES "
                "('forged', ?, 's1', 'a', ?, 0, 'EXTRACTED', ?, "
                "'EXACT_MATCHED', 'cat', '', 't', 'fp', 'alg')",
                (invoice_id, PC_FIELD_0, PC_KIND))
            conn.commit()
            raise AssertionError("UNIQUE declaration backstop missing")
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()
    assert len(stack.products.matches()) == 1


def test_check_gates_refuse_bad_outcome_shapes_via_direct_sql(stack):
    _, invoice_id = stack.assemble_products_invoice(label="pm-bnd-checks")
    base = ("INSERT INTO product_matches (match_id, invoice_id, capture_s1,"
            " capture_s1_algorithm_id, declared_field_name, canonical_seq,"
            " provenance, identifier_kind, match_outcome, "
            "catalog_identity_id, unresolved_reason, created_at, "
            "record_fingerprint, fingerprint_algorithm_id) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    bad_rows = [
        # a third outcome — no candidate/approval surface exists (OD-PM7)
        ("m1", invoice_id, "s1", "a", PC_FIELD_0, 0, "EXTRACTED", PC_KIND,
         "CANDIDATE_GENERATED", "", "", "t", "fp", "a"),
        # EXACT_MATCHED without a catalog reference
        ("m2", invoice_id, "s1", "a", PC_FIELD_0, 0, "EXTRACTED", PC_KIND,
         "EXACT_MATCHED", "", "", "t", "fp", "a"),
        # UNRESOLVED with a catalog reference
        ("m3", invoice_id, "s1", "a", PC_FIELD_0, 0, "EXTRACTED", PC_KIND,
         "UNRESOLVED", "cat", "no-catalog-identity", "t", "fp", "a"),
        # UNRESOLVED with an unknown reason
        ("m4", invoice_id, "s1", "a", PC_FIELD_0, 0, "EXTRACTED", PC_KIND,
         "UNRESOLVED", "", "made-up-reason", "t", "fp", "a"),
        # a provenance outside the D-01 vocabulary
        ("m5", invoice_id, "s1", "a", PC_FIELD_0, 0, "GUESSED", PC_KIND,
         "UNRESOLVED", "", "no-catalog-identity", "t", "fp", "a"),
        # a negative pointer
        ("m6", invoice_id, "s1", "a", PC_FIELD_0, -1, "EXTRACTED", PC_KIND,
         "UNRESOLVED", "", "no-catalog-identity", "t", "fp", "a"),
    ]
    conn = sqlite3.connect(str(stack.product_db))
    try:
        for row in bad_rows:
            try:
                conn.execute(base, row)
                conn.commit()
                raise AssertionError(f"CHECK gate missing: {row[8]}/{row[9]}"
                                     f"/{row[10]}")
            except sqlite3.IntegrityError:
                pass
    finally:
        conn.close()
    assert len(stack.products.matches()) == 0


def test_malformed_store_shape_commit_is_refused_in_python_too(stack):
    """Defensive Python-side refusals mirror every SQL CHECK (OD-PM1) — a
    malformed commit never reaches the transaction."""
    from product_candidate.model import ProductMatchRecord
    record = ProductMatchRecord(
        match_id="m", invoice_id="i", capture_s1="s1",
        capture_s1_algorithm_id="a", declared_field_name="f",
        canonical_seq=0, provenance="EXTRACTED", identifier_kind="k",
        match_outcome="CANDIDATE_GENERATED", catalog_identity_id="",
        unresolved_reason="", created_at="t", record_fingerprint="",
        fingerprint_algorithm_id="")
    with pytest.raises(Exception):
        stack.product_store.commit_match(record)
    assert len(stack.products.matches()) == 0
