"""WP-12.1 boundary tests — AST/static probes, import allowlist, no
production dependency on the corpus, marking/clock/vocabulary discipline
(SPEC-WP121 §2/§9)."""
import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PROD_FILES = sorted((SRC / "corpus").glob("*.py"))

ALLOWED_LOCAL_IMPORTS = {"capture", "corpus"}     # stdlib + capture + self
FORBIDDEN_MODULES = {"random", "hashlib", "time", "datetime", "secrets",
                     "uuid", "os", "subprocess", "socket", "http", "urllib"}
FORBIDDEN_IDENTIFIERS = {"eval", "exec", "compile", "__import__",
                         "open", "system", "popen"}
FORBIDDEN_SQL = ("UPDATE ", "DELETE FROM", "DROP TABLE", "ALTER TABLE",
                 "REPLACE INTO", "VACUUM", "ATTACH", "DETACH")

# Domain vocabulary that must NEVER appear in the corpus production package
# (pilot material carries no Sale/Customer/Inventory/Digital-Invoice
# semantics — DEF1/D-06/DEF3/AD-03/AS-02).
FORBIDDEN_VOCABULARY = (
    "canonicalize", "digital_invoice", "DigitalInvoice",
    "CanonicalInvoice", "REVIEW_QUEUE", "review_queue",
    "auto_create", "auto-create", "customer_create", "create_customer",
)


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                and node.module:
            names.add(node.module.split(".")[0])
    return names


# ---------------------------------------------------------------------------
# Import discipline (SPEC §2.2 — stdlib + capture only)
# ---------------------------------------------------------------------------

def test_production_import_allowlist():
    allowed_stdlib = {
        "dataclasses", "typing", "__future__", "sqlite3",
    }
    for path in PROD_FILES:
        tree = _tree(path)
        for name in _imported_names(tree):
            assert name in allowed_stdlib | ALLOWED_LOCAL_IMPORTS, (
                f"{path.name} imports non-allowlisted module: {name}")


def test_production_forbidden_modules_absent():
    for path in PROD_FILES:
        tree = _tree(path)
        found = _imported_names(tree)
        for forbidden in FORBIDDEN_MODULES:
            assert forbidden not in found, (
                f"{path.name} imports forbidden module: {forbidden}")


def test_production_has_no_hashlib_second_hash():
    """The corpus layer hashes ONLY through the capture S1 service."""
    for path in PROD_FILES:
        source = path.read_text(encoding="utf-8")
        assert "hashlib" not in source, f"{path.name} mentions hashlib"
        assert "sha256(" not in source, f"{path.name} hashes directly"


def test_production_forbidden_identifiers_absent():
    for path in PROD_FILES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_IDENTIFIERS:
                raise AssertionError(
                    f"{path.name} uses forbidden identifier: {node.id}")
            if isinstance(node, ast.Attribute) and node.attr in (
                    "system", "popen"):
                raise AssertionError(
                    f"{path.name} uses forbidden attribute: {node.attr}")


# ---------------------------------------------------------------------------
# Clock-free discipline (OD-CA-J)
# ---------------------------------------------------------------------------

def test_production_is_clock_free():
    for path in PROD_FILES:
        source = path.read_text(encoding="utf-8")
        for token in ("datetime", "time.time", "now(", "utcnow", "created_at",
                      "time()", "perf_counter"):
            assert token not in source, (
                f"{path.name} carries clock vocabulary: {token}")


# ---------------------------------------------------------------------------
# Append-only SQL discipline (SPEC §2.7)
# ---------------------------------------------------------------------------

def test_store_sql_is_append_only():
    store_source = (SRC / "corpus" / "store.py").read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_SQL:
        assert forbidden not in store_source, (
            f"store.py contains forbidden SQL: {forbidden!r}")


def test_no_file_writes_anywhere_in_production():
    """The package never opens/writes files itself — only its SQLite store
    (via the sqlite3 module) touches disk, at the caller-provided path."""
    for path in PROD_FILES:
        source = path.read_text(encoding="utf-8")
        for token in ("write_text", "write_bytes", "open(", "mkdir",
                      "unlink", "rename", "shutil"):
            assert token not in source, (
                f"{path.name} performs file I/O: {token}")


# ---------------------------------------------------------------------------
# No production package imports corpus (SPEC §2.3 — the dependency sweep)
# ---------------------------------------------------------------------------

def test_no_production_package_imports_corpus():
    """Every OTHER production package is swept: none may import `corpus`.
    The ONLY sanctioned consumer is the calibration layer (whose own boundary
    tests pin its allowlist) and this WP's tests/smoke."""
    calibration_allowed = (SRC / "calibration").exists()
    for package_dir in sorted(p for p in SRC.iterdir() if p.is_dir()):
        if package_dir.name == "corpus":
            continue
        if not (package_dir / "__init__.py").exists():
            continue          # non-package dirs (test folders) are not imports
        if package_dir.name == "calibration" and calibration_allowed:
            continue          # its boundary test pins the corpus import
        for py in package_dir.glob("*.py"):
            if py.name.startswith("run_smoke"):
                continue
            tree = _tree(py)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        assert root != "corpus", (
                            f"{package_dir.name}/{py.name} imports corpus")
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    root = (node.module or "").split(".")[0]
                    assert root != "corpus", (
                        f"{package_dir.name}/{py.name} imports corpus")


def test_run_smoke_runners_never_import_corpus_outside_corpus_suite():
    """Prior smoke runners (frozen surface) never gained a corpus import.
    Sanctioned consumers: the corpus smoke AND the calibration smoke (the
    WP-12.2 layer is the one declared corpus consumer — SPEC §2.3)."""
    sanctioned = {"run_smoke_corpus.py", "run_smoke_calibration.py"}
    for smoke in sorted(SRC.glob("run_smoke*.py")):
        if smoke.name in sanctioned:
            continue
        source = smoke.read_text(encoding="utf-8")
        assert "import corpus" not in source and "from corpus" not in source, (
            f"{smoke.name} imports the corpus layer")


# ---------------------------------------------------------------------------
# Vocabulary discipline (no domain semantics in pilot material)
# ---------------------------------------------------------------------------

def test_production_vocabulary_sweep():
    for path in PROD_FILES:
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_VOCABULARY:
            assert token not in source, (
                f"{path.name} carries forbidden domain vocabulary: {token}")


def test_marking_is_an_exact_literal_in_the_model():
    model_source = (SRC / "corpus" / "model.py").read_text(encoding="utf-8")
    assert "SYNTHETIC-PILOT-FIXTURE — NOT PRODUCTION DATA" in model_source
    assert "SYNTHETIC_PILOT_FIXTURE" in model_source


# ---------------------------------------------------------------------------
# Template/date discipline (OD-CA-G — flake-window avoidance)
# ---------------------------------------------------------------------------

def test_template_date_avoids_the_documented_flake_window():
    gen_source = (SRC / "corpus" / "generator.py").read_text(encoding="utf-8")
    assert 'TEMPLATE_DATE = "2026-06-15"' in gen_source
    assert "2026-10-08" not in gen_source
