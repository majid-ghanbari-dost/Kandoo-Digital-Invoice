"""Focused tests for the isolated aggregate smoke runner."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import run_smoke_all


def test_discovery_is_sorted_and_excludes_the_aggregate_runner():
    runners = run_smoke_all.discover_smoke_runners()
    names = [runner.name for runner in runners]

    assert names == sorted(names)
    assert "run_smoke_all.py" not in names
    assert "run_smoke.py" in names
    assert "run_smoke_issuance.py" in names
    assert len(names) >= 22


def test_each_runner_gets_the_same_interpreter_and_an_isolated_temp_path(
        tmp_path: Path, monkeypatch, capsys):
    runners = (tmp_path / "run_smoke_alpha.py", tmp_path / "run_smoke_beta.py")
    for runner in runners:
        runner.write_text("# test stub\n", encoding="utf-8")

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(run_smoke_all.subprocess, "run", fake_run)
    status = run_smoke_all.run_smoke_suite(
        runners,
        source_dir=tmp_path,
        python_executable=sys.executable,
    )

    assert status == 0
    assert len(calls) == 2
    workspaces = []
    for (command, kwargs), runner in zip(calls, runners):
        assert command[:3] == [sys.executable, "-B", str(runner.resolve())]
        workspaces.append(command[3])
        assert kwargs["cwd"] == str(tmp_path.resolve())
        assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        assert kwargs["timeout"] == run_smoke_all._RUNNER_TIMEOUT_SECONDS

    assert len(set(workspaces)) == 2
    assert all(Path(path).parent.name.startswith("kandoo-smoke-suite-")
               for path in workspaces)
    assert "SMOKE SUITE RESULT — 2/2 passed; 0 failed" in capsys.readouterr().out


def test_failure_is_reported_but_later_smokes_still_run(tmp_path: Path,
                                                         monkeypatch, capsys):
    runners = (tmp_path / "run_smoke_bad.py", tmp_path / "run_smoke_good.py")
    calls = []
    results = iter((
        SimpleNamespace(returncode=7, stdout="assertion output\n",
                        stderr="failure detail\n"),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
    ))

    def fake_run(command, **kwargs):
        calls.append(command)
        return next(results)

    monkeypatch.setattr(run_smoke_all.subprocess, "run", fake_run)
    status = run_smoke_all.run_smoke_suite(
        runners,
        source_dir=tmp_path,
        python_executable=sys.executable,
    )

    output = capsys.readouterr().out
    assert status == 1
    assert len(calls) == 2
    assert "run_smoke_bad.py: exit 7" in output
    assert "assertion output" in output
    assert "failure detail" in output
    assert "SMOKE SUITE RESULT — 1/2 passed; 1 failed" in output


def test_empty_discovery_fails_instead_of_claiming_a_green_smoke():
    assert run_smoke_all.run_smoke_suite((), source_dir=Path(".")) == 2
