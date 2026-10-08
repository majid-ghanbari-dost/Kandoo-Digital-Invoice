"""WP-9.1 boundary tests — structural AST proofs, pointer discipline, the
declared-input surface, the STRUCTURAL no-auto-create proof (D-06/DEF3),
frozen vocabulary, frozen-layer protection, and the UNIQUE backstops
(SPEC §1/§7; OD-CL1..CL8)."""
import ast
import inspect
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LAYER_DIR = SRC / "customer_linking"
LAYER_FILES = sorted(LAYER_DIR.glob("*.py"))

from cl_helpers import (  # noqa: E402
    CL_FIELD,
    CL_KIND,
    CL_VALUE,
    CustomerLinkingStack,
)
from customer_linking import (  # noqa: E402
    DURABLE_LINK_OUTCOMES,
    DURABLE_UNRESOLVED_REASONS,
    PROVENANCES,
    CustomerLinkingService,
    CustomerLinkingStore,
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
                                  "rewrite", "drop_", "merge_", "rescind",
                                  "dedup"):
                    assert not lowered.startswith(forbidden), \
                        f"{path.name}: function {node.name!r} looks like a " \
                        f"mutation/merge path"


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
        "            customer_identity_id=uuid.uuid4().hex,",
        "            link_id=uuid.uuid4().hex,",
    ], uuid_lines
    store_source = (LAYER_DIR / "store.py").read_text(encoding="utf-8")
    assert "uuid" not in store_source


def test_import_allowlist_project_layers_only():
    """The linking layer may import the project layers it consumes — and it
    consumes ONLY canonical_assembly (plus capture for the S1 hashing
    capability). No canonicalization / identity_resolution / product_candidate
    import: their semantics never leak in (OD-CL8)."""
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
    project S1 service (OD-CL1)."""
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
    for name in ("store.py", "service.py"):
        source = (LAYER_DIR / name).read_text(encoding="utf-8")
        assert "sha256(" not in source


def test_no_auto_create_symbols_or_enrichment_or_merge_surface():
    """D-06/DEF3/OD-CL7: NO creation/enrichment/merge/best-match/fuzzy
    surface exists — not as a symbol, not as a path."""
    forbidden = ("auto_create", "autocreate", "create_customer",
                 "customer_create", "merge", "dedup", "enrich", "fuzzy",
                 "similarity", "levenshtein", "difflib", "confidence",
                 "approv", "semantic", "score", "threshold", "best_match",
                 "ocr", "heuristic", "occurrence", "promot", "ml_", "ai_",
                 "neural", "rank_")
    for path in LAYER_FILES:
        for ident in _identifiers_in(_tree(path)):
            for token in forbidden:
                assert token not in ident, \
                    f"{path.name}: forbidden identifier {ident!r} " \
                    f"(contains {token!r})"


def test_no_barcode_grammar_or_checksum_symbols():
    """OD-CL3: identifier kinds/values are DECLARED opaque strings — no
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


def test_the_link_ladder_has_no_customer_creation_branch():
    """D-06 structural proof at the code level: service.py contains NO
    reference to the customer_identities table and NO INSERT of any kind —
    the ladder's ONLY write is the append-only link row through
    commit_link; the register's ONLY write is the explicit registration
    through commit_customer_identity. No code path connects an invoice to
    a customer row."""
    service_source = (LAYER_DIR / "service.py").read_text(encoding="utf-8")
    assert "customer_identities" not in service_source
    assert "INSERT INTO" not in service_source
    store_tree = _tree(LAYER_DIR / "store.py")
    inserts = set()
    for node in ast.walk(store_tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.strip().upper()
            if value.startswith("INSERT INTO "):
                inserts.add(value.split("(")[0].strip())
    assert inserts == {
        "INSERT INTO CUSTOMER_IDENTITIES",
        "INSERT INTO CUSTOMER_LINKS",
    }, inserts
    # and the two INSERTs live on the two explicitly separated commit paths
    store_source = (LAYER_DIR / "store.py").read_text(encoding="utf-8")
    commit_customer = store_source.split("def commit_customer_identity")[1] \
        .split("def _validate_customer_shape")[0]
    commit_link = store_source.split("def commit_link")[1] \
        .split("def _validate_link_shape")[0]
    assert "INSERT INTO customer_identities" in commit_customer
    assert "INSERT INTO customer_links" not in commit_customer
    assert "INSERT INTO customer_links" in commit_link
    assert "INSERT INTO customer_identities" not in commit_link


def test_no_canonicalization_or_review_or_product_semantics():
    """OD-CL8: no gate/canonicalization/REVIEW vocabulary is decided or
    annotated here, no product anything (WP-8.1), and no foreign table is
    referenced by SQL."""
    own_tables = {"customer_identities", "customer_links"}
    forbidden_tables = {"gate_decisions", "canonical_invoices",
                        "canonical_identity_pointers", "gate_review_items",
                        "domain_state_records", "normalization_records",
                        "extraction_records", "extraction_bindings",
                        "capture_records", "validation_records",
                        "identity_resolutions",
                        "identity_duplicate_observations",
                        "identity_role_candidates", "catalog_identities",
                        "product_matches", "flow_dispositions"}
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
    assert DURABLE_LINK_OUTCOMES == ("LINKED", "UNRESOLVED")
    assert DURABLE_UNRESOLVED_REASONS == ("no-customer-identity",)
    assert PROVENANCES == ("EXTRACTED", "DERIVED")


def test_storage_schema_enforces_pointer_discipline_and_outcome_shape():
    """OD-CL6: the link row carries NO value column (the identifier value
    lives in the verified P6.2 read and in the register's own registered
    content); the CHECK gates pin the outcome shapes and the stable
    UNRESOLVED reason."""
    from customer_linking import store as store_module
    schema = store_module._SCHEMA
    match_table = schema.split(
        "CREATE TABLE IF NOT EXISTS customer_links")[1].split(");")[0]
    assert "canonical_value" not in match_table
    assert "identifier_value" not in match_table
    assert "no-customer-identity" in schema
    customer_table = schema.split(
        "CREATE TABLE IF NOT EXISTS customer_identities")[1].split(");")[0]
    assert "identifier_value" in customer_table


def test_public_surface_has_no_decision_or_creation_verbs():
    import customer_linking as pkg
    for name in pkg.__all__:
        lowered = name.lower()
        # NB: UNRESOLVED is this layer's own declared D-06 outcome word
        # (OD-CL7); every actual decision/mutation/creation verb is forbidden.
        for token in ("canonicalize", "admit", "route", "decide", "update",
                      "delete", "issue", "assemble", "close_review",
                      "generate", "approve", "score", "create", "merge",
                      "enrich"):
            assert token not in lowered, \
                f"public surface exposes a decision/creation verb: {name}"


# ---------------------------------------------------------------------------
# Behavioral boundary — adversarial inputs stay refused / unresolved
# ---------------------------------------------------------------------------

def test_unique_declaration_backstop_is_a_real_database_constraint(stack):
    stack.register(CL_KIND, CL_VALUE)
    _, invoice_id = stack.assemble_customers_invoice(label="cl-bnd-uniq")
    stack.link(invoice_id, CL_FIELD, CL_KIND)
    conn = sqlite3.connect(str(stack.customer_db))
    try:
        try:
            conn.execute(
                "INSERT INTO customer_links (link_id, invoice_id, "
                "capture_s1, capture_s1_algorithm_id, declared_field_name, "
                "canonical_seq, provenance, identifier_kind, link_outcome, "
                "customer_identity_id, unresolved_reason, created_at, "
                "record_fingerprint, fingerprint_algorithm_id) VALUES "
                "('forged', ?, 's1', 'a', ?, 0, 'EXTRACTED', ?, "
                "'LINKED', 'cust', '', 't', 'fp', 'alg')",
                (invoice_id, CL_FIELD, CL_KIND))
            conn.commit()
            raise AssertionError("UNIQUE declaration backstop missing")
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()
    assert len(stack.customers_svc.links()) == 1


def test_check_gates_refuse_bad_outcome_shapes_via_direct_sql(stack):
    _, invoice_id = stack.assemble_customers_invoice(label="cl-bnd-checks")
    base = ("INSERT INTO customer_links (link_id, invoice_id, capture_s1,"
            " capture_s1_algorithm_id, declared_field_name, canonical_seq,"
            " provenance, identifier_kind, link_outcome, "
            "customer_identity_id, unresolved_reason, created_at, "
            "record_fingerprint, fingerprint_algorithm_id) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    bad_rows = [
        # a third outcome — no creation/merge surface exists (OD-CL7)
        ("m1", invoice_id, "s1", "a", CL_FIELD, 0, "EXTRACTED", CL_KIND,
         "AUTO_CREATED", "", "", "t", "fp", "a"),
        # LINKED without a customer reference
        ("m2", invoice_id, "s1", "a", CL_FIELD, 0, "EXTRACTED", CL_KIND,
         "LINKED", "", "", "t", "fp", "a"),
        # UNRESOLVED with a customer reference
        ("m3", invoice_id, "s1", "a", CL_FIELD, 0, "EXTRACTED", CL_KIND,
         "UNRESOLVED", "cust", "no-customer-identity", "t", "fp", "a"),
        # UNRESOLVED with an unknown reason
        ("m4", invoice_id, "s1", "a", CL_FIELD, 0, "EXTRACTED", CL_KIND,
         "UNRESOLVED", "", "made-up-reason", "t", "fp", "a"),
        # a provenance outside the D-01 vocabulary
        ("m5", invoice_id, "s1", "a", CL_FIELD, 0, "GUESSED", CL_KIND,
         "UNRESOLVED", "", "no-customer-identity", "t", "fp", "a"),
        # a negative pointer
        ("m6", invoice_id, "s1", "a", CL_FIELD, -1, "EXTRACTED", CL_KIND,
         "UNRESOLVED", "", "no-customer-identity", "t", "fp", "a"),
    ]
    conn = sqlite3.connect(str(stack.customer_db))
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
    assert len(stack.customers_svc.links()) == 0


def test_malformed_store_shape_commit_is_refused_in_python_too(stack):
    """Defensive Python-side refusals mirror every SQL CHECK (OD-CL1) — a
    malformed commit never reaches the transaction."""
    from customer_linking.model import CustomerLinkRecord
    record = CustomerLinkRecord(
        link_id="m", invoice_id="i", capture_s1="s1",
        capture_s1_algorithm_id="a", declared_field_name="f",
        canonical_seq=0, provenance="EXTRACTED", identifier_kind="k",
        link_outcome="AUTO_CREATED", customer_identity_id="",
        unresolved_reason="", created_at="t", record_fingerprint="",
        fingerprint_algorithm_id="")
    with pytest.raises(Exception):
        stack.customer_store.commit_link(record)
    assert len(stack.customers_svc.links()) == 0


def test_register_is_unreachable_from_the_pipeline_surface(stack):
    """D-06/DEF3 structural proof at the API level: the service exposes no
    method that accepts capture/document/extraction parameters, and the
    register write path takes only the two declared identifier arguments
    (cross-checked with the AST probe above)."""
    public = [n for n, _ in inspect.getmembers(
        CustomerLinkingService, predicate=inspect.isfunction)
        if not n.startswith("_")]
    assert sorted(public) == ["customers", "link", "links", "links_of",
                              "read_customer_identity", "read_link_by_id",
                              "register_customer_identity"]
    assert len(stack.customers_svc.customers()) == 0   # nothing pre-seeded
