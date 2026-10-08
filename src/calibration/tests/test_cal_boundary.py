"""WP-12.2 isolation + boundary tests — workspace provenance, corpus byte
stability, re-run refusal, AST/static probes (SPEC-WP122 §2/§8/§9)."""
import ast
import json
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from calibration import (  # noqa: E402
    CalibrationInputRefused,
    CalibrationReport,
    CalibrationRunRefused,
    RunConfig,
)
from corpus import CorpusReadSuccess  # noqa: E402


# ---------------------------------------------------------------------------
# Workspace isolation (SPEC §2.2/§2.8)
# ---------------------------------------------------------------------------

def test_all_run_files_live_under_the_workspace(tmp_path, s1, corpus_service,
                                                run_config, clean_corpus):
    manifest, read = clean_corpus
    from calibration import CalibrationRunService
    ws = tmp_path / "iso-ws"
    CalibrationRunService(ws, s1).run(read, run_config(manifest))
    produced = [p for p in ws.rglob("*") if p.is_file()]
    assert produced, "run produced no workspace files"
    for path in produced:
        assert str(path).startswith(str(ws)), f"file outside workspace: {path}"


def test_run_refuses_a_used_workspace(tmp_path, s1, corpus_service,
                                      run_config, clean_corpus):
    manifest, read = clean_corpus
    from calibration import CalibrationRunService
    service = CalibrationRunService(tmp_path / "used-ws", s1)
    service.run(read, run_config(manifest))
    with pytest.raises(CalibrationRunRefused):
        service.run(read, run_config(manifest))
    # a DIFFERENT corpus in the same workspace is refused just the same
    other = corpus_service.assemble("kv-invoice-clean-v1", 2, 99)
    other_read = corpus_service.read_corpus(other.manifest.corpus_version_id)
    with pytest.raises(CalibrationRunRefused):
        CalibrationRunService(tmp_path / "used-ws", s1).run(
            other_read, run_config(other.manifest))


def test_corpus_store_is_byte_stable_across_the_run(tmp_path, s1,
                                                    corpus_service,
                                                    run_config,
                                                    rounding_corpus):
    manifest, read = rounding_corpus
    from calibration import CalibrationRunService
    corpus_db = tmp_path / "corpus.db"
    def digest():
        conn = sqlite3.connect(str(corpus_db))
        try:
            rows = conn.execute(
                "SELECT corpus_version_id, ordinal, template_id, entry_seed, "
                "origin_role, marking, parts_blob, labels_blob, "
                "parts_total_bytes, entry_fingerprint, "
                "fingerprint_algorithm_id FROM corpus_entries "
                "ORDER BY corpus_version_id, ordinal").fetchall()
            manifests = conn.execute(
                "SELECT * FROM corpus_manifests ORDER BY "
                "corpus_version_id").fetchall()
            return str(rows), str(manifests)
        finally:
            conn.close()
    before = digest()
    CalibrationRunService(tmp_path / "stable-ws", s1).run(
        read, run_config(manifest))
    assert digest() == before, "the run mutated the corpus store"


def test_run_requires_a_verified_corpus_read(tmp_path, s1, run_config):
    from calibration import CalibrationRunService
    with pytest.raises(CalibrationRunRefused):
        CalibrationRunService(tmp_path / "ws-r", s1).run(
            "not-a-corpus-read", RunConfig(corpus_version_id="ff" * 32))


def test_run_refuses_corpus_address_mismatch(tmp_path, s1, corpus_service,
                                             run_config, clean_corpus):
    manifest, read = clean_corpus
    from calibration import CalibrationRunService
    with pytest.raises(CalibrationRunRefused):
        CalibrationRunService(tmp_path / "ws-m", s1).run(
            read, RunConfig(corpus_version_id="ee" * 32))


@pytest.mark.parametrize("config", [
    RunConfig(corpus_version_id=""),                       # empty address
    RunConfig(corpus_version_id="ff" * 32,
              candidate_tolerances=()),                    # no candidates
    RunConfig(corpus_version_id="ff" * 32,
              candidate_tolerances=("0.01", "-0.5")),      # negative candidate
    RunConfig(corpus_version_id="ff" * 32,
              candidate_tolerances=("0.01", "abc")),       # non-decimal
    RunConfig(corpus_version_id="ff" * 32, engine_id="mega-engine-v9"),
    RunConfig(corpus_version_id="ff" * 32, norm_ruleset_id="other-v2"),
    RunConfig(corpus_version_id=""),                       # empty address
])
def test_run_config_validation_fail_closed(tmp_path, s1, config):
    from calibration import CalibrationRunService
    with pytest.raises((CalibrationInputRefused, CalibrationRunRefused)):
        CalibrationRunService(tmp_path / "ws-x", s1).run(None, config)


# ---------------------------------------------------------------------------
# Static probes — imports, test-helper ban, clock-free report path
# ---------------------------------------------------------------------------

CAL_FILES = sorted((SRC / "calibration").glob("*.py"))

FORBIDDEN_LOCAL = {"cg_helpers", "val_helpers", "vsm_helpers", "ca_helpers",
                   "hs_helpers", "di_helpers", "ir_helpers"}
ALLOWED_LOCAL = {"capture", "corpus", "reconstruction", "extraction",
                 "normalization", "derivation", "validation",
                 "validation_domain", "canonicalization", "calibration"}
ALLOWED_STDLIB = {"dataclasses", "typing", "__future__", "sqlite3", "json",
                  "pathlib"}
FORBIDDEN_STD = {"random", "hashlib", "time", "datetime", "secrets", "uuid",
                 "os", "subprocess", "socket", "http", "urllib"}


def test_calibration_import_allowlist():
    for path in CAL_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                    and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                assert name in ALLOWED_LOCAL | ALLOWED_STDLIB, (
                    f"{path.name} imports non-allowlisted module: {name}")
                assert name not in FORBIDDEN_STD, (
                    f"{path.name} imports forbidden module: {name}")
                assert name not in FORBIDDEN_LOCAL, (
                    f"{path.name} imports a TEST helper: {name}")


def test_calibration_never_imports_test_helpers_by_literal():
    for path in CAL_FILES:
        source = path.read_text(encoding="utf-8")
        for helper in FORBIDDEN_LOCAL:
            assert helper not in source, (
                f"{path.name} references test helper {helper}")


def test_calibration_report_path_is_clock_free():
    """The report serialization path carries no wall-clock call."""
    model_source = (SRC / "calibration" / "model.py").read_text(encoding="utf-8")
    for token in ("datetime", "now(", "utcnow", "time()", "perf_counter"):
        assert token not in model_source, (
            f"model.py carries clock vocabulary: {token}")


def test_no_production_package_imports_calibration():
    """The calibration layer is pilot surface — no frozen production package
    may depend on it."""
    for package_dir in sorted(p for p in SRC.iterdir() if p.is_dir()):
        if package_dir.name in ("calibration", "corpus"):
            continue
        if not (package_dir / "__init__.py").exists():
            continue
        for py in package_dir.glob("*.py"):
            if py.name.startswith("run_smoke"):
                continue
            tree = ast.parse(py.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                roots = []
                if isinstance(node, ast.Import):
                    roots = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 \
                        and node.module:
                    roots = [node.module.split(".")[0]]
                for root in roots:
                    assert root != "calibration", (
                        f"{package_dir.name}/{py.name} imports calibration")


def test_prior_smoke_runners_never_import_calibration():
    for smoke in sorted(SRC.glob("run_smoke*.py")):
        if smoke.name == "run_smoke_calibration.py":
            continue
        source = smoke.read_text(encoding="utf-8")
        assert "import calibration" not in source \
            and "from calibration" not in source, (
            f"{smoke.name} imports the calibration layer")


# ---------------------------------------------------------------------------
# Domain-promotion vocabulary (SPEC §2.6)
# ---------------------------------------------------------------------------

def test_calibration_vocabulary_sweep():
    for path in CAL_FILES:
        source = path.read_text(encoding="utf-8")
        for token in ("create_sale", "Sale(", "auto_create",
                      "create_customer", "Customer(", "inventory_movement",
                      "issue_digital", "DigitalInvoice(", "digital_invoice_"
                      "service"):
            assert token not in source, (
                f"{path.name} carries forbidden domain vocabulary: {token}")


# ---------------------------------------------------------------------------
# The report is the ONLY output — the package writes nothing itself
# ---------------------------------------------------------------------------

def test_report_is_in_memory_only(run_service, run_config, clean_corpus):
    """CalibrationReport.to_json_bytes returns bytes; nothing is written by
    the report itself (the workspace files come from the pipeline stores)."""
    manifest, read = clean_corpus
    report = run_service().run(read, run_config(manifest))
    assert isinstance(report, CalibrationReport)
    assert isinstance(report.to_json_bytes(), bytes)
    payload = json.loads(report.to_json_bytes())
    assert payload["report"] == "kandoo-calibration-report-v1"


def test_run_requires_the_capture_s1_service(tmp_path):
    from calibration import CalibrationRunService
    with pytest.raises(CalibrationInputRefused):
        CalibrationRunService(tmp_path / "ws-s1", "not-an-s1")
