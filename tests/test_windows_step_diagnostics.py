from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "windows_step_diagnostics.py"


def test_failure_diagnostics_are_bounded_and_written_to_stdout_and_summary(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    env = os.environ.copy()
    env["GITHUB_STEP_SUMMARY"] = str(summary)
    command = [
        sys.executable,
        str(WRAPPER),
        "--step-name",
        "Windows tests - example",
        "--",
        sys.executable,
        "-c",
        "import sys; [print(f'ERROR assertion {i}', file=sys.stderr) for i in range(25)]; sys.exit(23)",
    ]

    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, check=False)

    assert result.returncode == 23
    stdout = result.stdout.decode("utf-8")
    summary_text = summary.read_bytes().decode("utf-8")
    for text in (stdout, summary_text):
        assert "Windows tests - example" in text
        assert "Exit code: `23`" in text
        assert "[stderr] ERROR assertion 0" in text
        assert "[stderr] ERROR assertion 19" in text
        assert "first 20 of 25 matching lines" in text
        assert "[stderr] ERROR assertion 20" not in text
        assert "[stderr] ERROR assertion 24" not in text

    assert "ERROR assertion 24" in result.stderr.decode("utf-8")


def test_stdout_diff_diagnostics_are_bounded_and_written_to_summary(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    env = os.environ.copy()
    env["GITHUB_STEP_SUMMARY"] = str(summary)
    command = [
        sys.executable,
        str(WRAPPER),
        "--step-name",
        "Build Windows bundle",
        "--",
        sys.executable,
        "-c",
        "import sys; [print(f'diff: expected value {i}') for i in range(23)]; sys.exit(7)",
    ]

    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, check=False)

    assert result.returncode == 7
    stdout = result.stdout.decode("utf-8")
    summary_text = summary.read_bytes().decode("utf-8")
    for text in (stdout, summary_text):
        assert "Build Windows bundle" in text
        assert "Exit code: `7`" in text
        assert "[stdout] diff: expected value 0" in text
        assert "[stdout] diff: expected value 19" in text
        assert "first 20 of 23 matching lines" in text
        assert "[stdout] diff: expected value 20" not in text
        assert "[stdout] diff: expected value 22" not in text


def test_success_does_not_emit_failure_summary(tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    env = os.environ.copy()
    env["GITHUB_STEP_SUMMARY"] = str(summary)
    command = [
        sys.executable,
        str(WRAPPER),
        "--step-name",
        "Windows tests - success",
        "--",
        sys.executable,
        "-c",
        "print('pytest passed')",
    ]

    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, check=False)

    assert result.returncode == 0
    assert result.stdout.decode("utf-8") == "pytest passed\n"
    assert result.stderr == b""
    assert not summary.exists()
