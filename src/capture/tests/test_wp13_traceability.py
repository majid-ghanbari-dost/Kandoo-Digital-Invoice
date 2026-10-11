"""WP-1.3 AC-1.3.4 (traceability half) — registered ACs ↔ named tests ↔ DEF4 boundary.

This module makes the AC↔evidence link mechanical instead of documentary: the AC table in
SPEC-WP13-RETR §9 is parsed, and every test name it cites must exist in this suite. If a
test is renamed or dropped, the contract's own table fails the build — a register cannot
drift away from the evidence it claims.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = REPO_ROOT / "specs" / "WP-1.3-retention-recovery-contract.md"
ACCEPTANCE_REGISTER = REPO_ROOT / "registers" / "acceptance-register.md"
DEFERRED_REGISTER = REPO_ROOT / "registers" / "deferred-decision-register.md"
WP13_TEST_FILES = ("test_wp13_retention.py", "test_wp13_journal.py",
                   "test_wp13_purge_gate.py", "test_wp13_consistency.py",
                   "test_wp13_recovery_matrix.py", "test_wp13_traceability.py")
WP13_MODULES = ("retention.py", "retention_journal.py", "consistency.py")
AC_IDS = ("AC-1.3.1", "AC-1.3.2", "AC-1.3.3", "AC-1.3.4")


def _suite_source() -> str:
    return "\n".join((TESTS_DIR / name).read_text(encoding="utf-8") for name in WP13_TEST_FILES)


def _ac_table_rows() -> dict:
    """The §9 AC table: {AC id: cited `test_*` names}."""
    text = CONTRACT.read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not re.fullmatch(r"AC-1\.3\.\d", cells[0]):
            continue
        names = set()
        for cell in cells:
            names.update(re.findall(r"`(test_[a-z0-9_]+)`", cell))
        rows[cells[0]] = names
    return rows


@pytest.mark.parametrize("ac_id", AC_IDS)
def test_ac_is_registered_in_the_acceptance_register(ac_id):
    text = ACCEPTANCE_REGISTER.read_text(encoding="utf-8")
    row = next((line for line in text.splitlines() if f"| {ac_id} |" in line), None)
    assert row is not None, f"{ac_id} is not registered in REG-AR"
    assert f"| WP-1.3 |" in row
    assert "| PASS |" in row or "| PENDING |" in row, f"{ac_id} has no verdict"


@pytest.mark.parametrize("ac_id", AC_IDS)
def test_ac_is_bound_to_named_tests_that_exist(ac_id):
    rows = _ac_table_rows()
    assert ac_id in rows, f"{ac_id} missing from the SPEC-WP13-RETR §9 AC table"
    cited = rows[ac_id]
    assert len(cited) >= 2, f"{ac_id} cites {len(cited)} test(s); ≥2 required"
    suite = _suite_source()
    for name in sorted(cited):
        assert f"def {name}(" in suite, f"{ac_id} cites {name}, which does not exist"


def test_every_ac_is_covered_and_no_citation_is_dangling():
    rows = _ac_table_rows()
    assert set(rows) == set(AC_IDS)
    assert set().union(*rows.values()) <= {
        m.group(1) for m in re.finditer(r"\ndef (test_[a-z0-9_]+)\(", _suite_source())}


def test_wp13_modules_declare_no_numeric_policy_constant():
    """A module-level number could only be a policy value — so none may exist.

    (Strings/False/frozensets are vocabulary; an int/float at module level in the
    retention layer would be an invented DEF4 value.)
    """
    capture_dir = TESTS_DIR.parent
    for name in WP13_MODULES:
        tree = ast.parse((capture_dir / name).read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        value = node.value
                        numeric = (isinstance(value, ast.Constant)
                                   and isinstance(value.value, (int, float))
                                   and not isinstance(value.value, bool))
                        assert not numeric, (
                            f"{name}: module-level numeric constant {target.id!r} = "
                            f"{value.value!r} would be a policy value")


def test_def4_stays_deferred_and_deferred_registers_are_untouched():
    """This WP may not open DEF4: the register must still read DEFERRED, and the
    contract must state the blockage in its own words."""
    deferred = DEFERRED_REGISTER.read_text(encoding="utf-8")
    row = next(line for line in deferred.splitlines() if line.startswith("| DEF4 |"))
    assert "DEFERRED" in row
    assert "WP-1.3" in row                       # blocked area still names this WP
    contract = CONTRACT.read_text(encoding="utf-8")
    for token in ("DEF4", "DEFERRED", "no values", "policy values"):
        assert token in contract, token
    assert "WP-1.3 delivered mechanics only" in contract


def test_purge_language_never_becomes_an_execution_surface():
    """Vocabulary discipline: the modules speak of blocking/reporting, never of doing."""
    capture_dir = TESTS_DIR.parent
    for name in WP13_MODULES:
        source = (capture_dir / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        forbidden = {d for d in defined if re.search(
            r"(^|_)(delete|erase|destroy|shred|wipe|vacuum|remove|drop|truncate|execute)", d, re.I)}
        assert forbidden == set(), (name, forbidden)


def test_smoke_runner_exists_and_is_cold_start(tmp_path):
    runner = REPO_ROOT / "src" / "run_smoke_retention_recovery.py"
    assert runner.exists()
    source = runner.read_text(encoding="utf-8")
    assert "shutil.rmtree(BASE)" in source                    # cold start by construction
    assert "SMOKE OK" in source
    assert "DEF4" in source
    steps = len(re.findall(r"\n\s*step\(True, ", source))
    assert steps == 8, f"expected the 8 registered cold-start steps, found {steps}"


def test_register_updates_record_this_wp_only_where_it_should():
    """The WP Register must carry a WP-1.3 implementation record; the DEF4 row and the
    Decision Register must NOT have been rewritten to make this WP pass."""
    wpr = (REPO_ROOT / "registers" / "work-package-register.md").read_text(encoding="utf-8")
    section = wpr.split("## WP-1.3", 1)[1].split("\n## ", 1)[0]
    assert "IMPLEMENTED" in section and "DEF4" in section
    decision = (REPO_ROOT / "registers" / "decision-register.md").read_text(encoding="utf-8")
    assert decision.count("| FROZEN |") == len([l for l in decision.splitlines()
                                                if l.startswith("| D-") or l.startswith("| AD-")
                                                or l.startswith("| AS-")])
    assert "WP-1.3" not in decision, "the Decision Register must not be edited by this WP"
