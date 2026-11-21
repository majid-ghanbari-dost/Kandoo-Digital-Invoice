"""Run every project smoke runner against isolated temporary workspaces.

Usage (from the repository root or ``src``)::

    python3 src/run_smoke_all.py

This is a developer verification tool, not a product CLI. Each existing
``run_smoke*.py`` runner receives its own fresh path, preventing fixed default
/tmp paths from leaking state between runs or touching application data.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence


_THIS_FILE = Path(__file__).resolve()
_RUNNER_TIMEOUT_SECONDS = 120


def discover_smoke_runners(source_dir: Path | None = None) -> tuple[Path, ...]:
    """Return the top-level smoke scripts in stable filename order."""
    root = Path(source_dir).resolve() if source_dir is not None else _THIS_FILE.parent
    return tuple(
        path.resolve()
        for path in sorted(root.glob("run_smoke*.py"))
        if path.name != _THIS_FILE.name
    )


def _print_failure(name: str, reason: str, stdout: str = "",
                   stderr: str = "") -> None:
    print(f"  FAIL {name}: {reason}")
    if stdout:
        print("  stdout:")
        print(stdout.rstrip())
    if stderr:
        print("  stderr:")
        print(stderr.rstrip())


def run_smoke_suite(runners: Sequence[Path], *, source_dir: Path,
                    python_executable: str | None = None) -> int:
    """Execute smoke scripts in isolated directories; return a process status.

    All runners are attempted even if one fails, so a single invocation gives
    a complete, useful failure summary. Each child has a bounded runtime and
    bytecode writes disabled so the repository remains clean.
    """
    if not runners:
        print("SMOKE SUITE FAIL — no run_smoke*.py runners were discovered")
        return 2

    root = Path(source_dir).resolve()
    python = python_executable or sys.executable
    child_env = os.environ.copy()
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    passed = 0
    failed = 0
    print(f"Kandoo smoke suite — {len(runners)} runners; Python {sys.version.split()[0]}")

    with tempfile.TemporaryDirectory(prefix="kandoo-smoke-suite-") as temporary_root:
        for index, runner in enumerate(runners, start=1):
            script = Path(runner).resolve()
            workspace = Path(temporary_root) / f"{index:02d}-{script.stem}"
            command = [python, "-B", str(script), str(workspace)]
            print(f"[{index}/{len(runners)}] {script.name}", flush=True)
            try:
                result = subprocess.run(
                    command,
                    cwd=str(root),
                    env=child_env,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=_RUNNER_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as exc:
                failed += 1
                stdout = (
                    exc.stdout.decode(errors="replace")
                    if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                )
                stderr = (
                    exc.stderr.decode(errors="replace")
                    if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                )
                _print_failure(
                    script.name,
                    f"timed out after {_RUNNER_TIMEOUT_SECONDS} seconds",
                    stdout,
                    stderr,
                )
            except OSError as exc:
                failed += 1
                _print_failure(script.name, f"could not start runner: {exc}")
            else:
                if result.returncode == 0:
                    passed += 1
                    print(f"  PASS (exit 0)")
                else:
                    failed += 1
                    _print_failure(
                        script.name,
                        f"exit {result.returncode}",
                        result.stdout,
                        result.stderr,
                    )

    print(f"SMOKE SUITE RESULT — {passed}/{len(runners)} passed; {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    root = _THIS_FILE.parent
    return run_smoke_suite(
        discover_smoke_runners(root),
        source_dir=root,
        python_executable=sys.executable,
    )


if __name__ == "__main__":
    raise SystemExit(main())
