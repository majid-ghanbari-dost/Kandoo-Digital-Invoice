"""Inspect a local capture queue without printing IDs, paths, values, or hashes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from image_extraction_adapter.capture_folder import inspect_capture_batch


EXIT_READY = 0
EXIT_REVIEW = 10
EXIT_ERROR = 30


def inspect(root: Path) -> dict[str, Any]:
    items = inspect_capture_batch(root)
    output = [
        {
            "ordinal": item.ordinal,
            "status": item.status,
            "problem_codes": sorted({problem.code for problem in item.problems}),
        }
        for item in items
    ]
    return {
        "result_version": "capture-batch-inspection-v1",
        "job_count": len(items),
        "ready_count": sum(item["status"] == "READY" for item in output),
        "review_count": sum(item["status"] == "REVIEW" for item in output),
        "items": output,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-root", type=Path, required=True, metavar="LOCAL_DIR")
    args = parser.parse_args(argv)
    try:
        report = inspect(args.capture_root)
        payload = json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        sys.stdout.write(payload)
        sys.stdout.flush()
    except Exception as exc:
        message = f"Capture batch inspection FAILED: {type(exc).__name__}: {exc}"
        annotation = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Capture batch inspection::{annotation}")
        print(message, file=sys.stderr)
        return EXIT_ERROR
    return EXIT_READY if report["review_count"] == 0 else EXIT_REVIEW


if __name__ == "__main__":
    raise SystemExit(main())
