#!/usr/bin/env python3
"""Run one Windows CI command and publish bounded diagnostics on failure.

The command's stdout and stderr remain visible in the step log. On failure,
this wrapper also emits the step name, return code, and at most 20 error/diff
lines to stdout and (when available) GITHUB_STEP_SUMMARY.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
MAX_DIAGNOSTIC_LINES = 20
_ERROR_OR_DIFF = re.compile(
    r"(?i)(\berror\b|\bfail(?:ed|ure)?\b|\bexception\b|\btraceback\b|"
    r"\bassert(?:ion)?\b|\bmismatch\b|\bdiff\b)"
)


def _diagnostic_lines(stdout: bytes, stderr: bytes) -> tuple[list[str], int]:
    candidates: list[str] = []
    all_lines: list[str] = []
    for channel, payload in (("stderr", stderr), ("stdout", stdout)):
        decoded = payload.decode("utf-8", errors="replace")
        for line in decoded.splitlines():
            tagged = f"[{channel}] {line}"
            all_lines.append(tagged)
            if _ERROR_OR_DIFF.search(line):
                candidates.append(tagged)
    selected = candidates if candidates else all_lines
    return selected[:MAX_DIAGNOSTIC_LINES], len(selected)


def _format_failure(step_name: str, returncode: int, stdout: bytes, stderr: bytes) -> str:
    lines, total = _diagnostic_lines(stdout, stderr)
    detail = lines or ["[no output captured]"]
    rendered = [
        f"### Windows step failure: {step_name}",
        "",
        f"- Step name: `{step_name}`",
        f"- Exit code: `{returncode}`",
        f"- Error/diff lines: first {min(total, MAX_DIAGNOSTIC_LINES)} of {total} matching lines"
        if total > MAX_DIAGNOSTIC_LINES
        else f"- Error/diff lines: {total}",
        "",
        "```text",
        *detail,
        "```",
    ]
    return "\n".join(rendered) + "\n"


def run_command(step_name: str, command: Sequence[str]) -> int:
    if not command:
        raise ValueError("a command is required after --")
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except OSError as exc:
        stdout = b""
        stderr = f"{type(exc).__name__}: {exc}".encode("utf-8", errors="replace")
        returncode = 127

    sys.stdout.buffer.write(stdout)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(stderr)
    sys.stderr.buffer.flush()

    if returncode == 0:
        return 0

    diagnostic = _format_failure(step_name, returncode, stdout, stderr)
    sys.stdout.buffer.write(diagnostic.encode("utf-8"))
    sys.stdout.buffer.flush()

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with Path(summary_path).open("ab") as summary:
                summary.write(b"\n" + diagnostic.encode("utf-8"))
        except OSError as exc:
            warning = f"Could not append Windows failure diagnostics to step summary: {exc}\n"
            sys.stdout.buffer.write(warning.encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()
    return returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step-name", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    return run_command(args.step_name, command)


if __name__ == "__main__":
    raise SystemExit(main())
