from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from image_extraction_adapter.cli import main as cli_main
from demo_capture import main as demo_main


def test_cli_help_is_a_successful_stable_command():
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        with pytest.raises(SystemExit) as exit_info:
            cli_main(["--help"])
    assert exit_info.value.code == 0
    assert "extract" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_cli_invalid_arguments_use_exit_30_and_stderr_only():
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main(["extract"])
    assert code == 30
    assert stdout.getvalue() == ""
    assert "--image" in stderr.getvalue() or "--capture-folder" in stderr.getvalue()


def test_pinned_demo_keeps_v0_and_v1_1_separate_and_does_not_invent_candidate():
    demo = json.loads((ROOT / "tests/golden/o15/demo-output-v1.json").read_text(encoding="utf-8"))
    assert demo["demo_version"] == "o15.capture-demo.v1"
    assert demo["canonical_invoice_v0"] is None
    assert demo["issued_invoice_v1_1_recorded_fields"]["customer_name"] == "Synthetic customer"
    assert demo["issued_invoice_v1_1_recorded_fields"]["payments"][0]["type"] == "cash"


def test_synthetic_e60_inputs_are_explicitly_labeled():
    manifest = json.loads((ROOT / "tests/golden/o15/manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic_only"] is True
    report = (ROOT / "tests/fixtures/o15/capture-folder/Report.txt").read_text(encoding="utf-8")
    assert "SYNTHETIC" in report
    assert "o15-synthetic" in report


def test_demo_refuses_to_write_owner_output_inside_repository():
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = demo_main([
            "--capture-folder", str(ROOT / "tests/fixtures/o15/capture-folder"),
            "--out-dir", str(ROOT / "local-captures" / "test-run"),
        ])
    assert code == 30
    assert stdout.getvalue() == ""
    assert "outside the repository" in stderr.getvalue()
