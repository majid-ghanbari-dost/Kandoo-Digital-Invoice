#!/usr/bin/env python3
"""Append a UTF-8 report file to the GitHub Actions step summary as bytes."""
from __future__ import annotations

import os
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: append_report_to_summary.py REPORT.md", file=sys.stderr)
        return 2
    summary_name = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_name:
        raise RuntimeError("GITHUB_STEP_SUMMARY is not set")
    payload = Path(sys.argv[1]).read_bytes()
    with Path(summary_name).open("ab") as summary:
        summary.write(b"\n" + payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
