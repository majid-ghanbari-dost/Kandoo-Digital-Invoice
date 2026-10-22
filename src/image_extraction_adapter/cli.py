"""Command-line bridge from local E-02 extraction to Canonical Invoice v0.

Producer-owned Canonical Invoice context is supplied through a UTF-8 JSON file;
this CLI never invents platform identifiers, customer data, or product names.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .canonical_invoice import validate_canonical_invoice
from .pipeline_v0 import DEFAULT_TEMPLATE_BANK_PATH, extract_pipeline_v0

EXIT_READY = 0
EXIT_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_ERROR = 30


class _ArgumentParseError(Exception):
    """Raised instead of argparse's default exit code 2."""


class _CLIInputError(Exception):
    """Raised for invalid user-supplied paths, timestamps, or context JSON."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentParseError(message)


def _build_parser() -> _ArgumentParser:
    parser = _ArgumentParser(
        prog="python -m image_extraction_adapter.cli",
        description="Run local E-02 extraction and emit a Canonical Invoice v0 candidate.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract = subparsers.add_parser(
        "extract",
        help="extract one local image",
        description="Extract one image and emit its schema-valid Canonical Invoice candidate.",
    )
    extract.add_argument("--image", type=Path, required=True, metavar="PATH")
    extract.add_argument(
        "--context",
        type=Path,
        required=True,
        metavar="PATH",
        help="UTF-8 JSON object with producer-supplied canonical_context fields",
    )
    extract.add_argument(
        "--captured-at",
        metavar="ISO",
        help="optional ISO 8601 capture timestamp with an explicit UTC offset",
    )
    extract.add_argument(
        "--templates",
        type=Path,
        default=DEFAULT_TEMPLATE_BANK_PATH,
        metavar="PATH",
        help=f"local Glyph template bank (default: {DEFAULT_TEMPLATE_BANK_PATH})",
    )
    return parser


def _validate_captured_at(value: str | None) -> None:
    if value is None:
        return
    if not value.strip():
        raise _CLIInputError("--captured-at must be a non-empty ISO 8601 datetime")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise _CLIInputError(
            "--captured-at must be an ISO 8601 datetime with a UTC offset"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _CLIInputError("--captured-at must include an explicit UTC offset")


def _require_file(path: Path, option_name: str) -> None:
    if not path.is_file():
        raise _CLIInputError(f"{option_name} file does not exist or is not a file: {path}")


def _load_context(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as context_file:
            context = json.load(context_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _CLIInputError(f"could not read --context JSON from {path}: {exc}") from exc
    if not isinstance(context, dict):
        raise _CLIInputError("--context JSON must be an object containing canonical_context fields")
    return context


def _write_canonical_json(invoice: dict[str, Any]) -> None:
    payload = json.dumps(invoice, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    encoded = payload.encode("utf-8")
    stdout_buffer = getattr(sys.stdout, "buffer", None)
    if stdout_buffer is not None:
        stdout_buffer.write(encoded)
        stdout_buffer.flush()
    else:  # Supports in-process tests redirecting stdout to StringIO.
        sys.stdout.write(payload)
        sys.stdout.flush()


def _pipeline_diagnostics(result: Any) -> list[str]:
    details = [str(result.reason)] if result.reason else []
    details.extend(str(item) for item in result.canonical_blockers)
    details.extend(str(item) for item in result.canonical_errors)
    return details


def _run_extract(args: argparse.Namespace) -> int:
    _require_file(args.image, "--image")
    _require_file(args.templates, "--templates")
    _require_file(args.context, "--context")
    _validate_captured_at(args.captured_at)
    canonical_context = _load_context(args.context)

    result = extract_pipeline_v0(
        args.image,
        templates_path=args.templates,
        captured_at=args.captured_at,
        canonical_context=canonical_context,
    )

    if result.status == "REJECT":
        print("REJECT: extraction is blocked; no Canonical Invoice was emitted.", file=sys.stderr)
        for detail in _pipeline_diagnostics(result):
            print(f"  {detail}", file=sys.stderr)
        return EXIT_BLOCKED

    if result.status not in {"AUTO_CANDIDATE", "REVIEW"}:
        raise RuntimeError(f"pipeline returned unsupported status: {result.status!r}")

    invoice = result.canonical_invoice
    if invoice is None:
        details = _pipeline_diagnostics(result)
        if result.status == "REVIEW":
            print(
                "REVIEW: no schema-valid Canonical Invoice candidate is available; stdout is empty.",
                file=sys.stderr,
            )
            for detail in details:
                print(f"  {detail}", file=sys.stderr)
            return EXIT_REVIEW
        raise RuntimeError(
            "pipeline returned AUTO_CANDIDATE without a Canonical Invoice candidate"
        )

    valid, errors = validate_canonical_invoice(invoice)
    if not valid:
        print("Canonical Invoice v0 validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return EXIT_ERROR

    _write_canonical_json(invoice)
    return EXIT_READY if result.status == "AUTO_CANDIDATE" else EXIT_REVIEW


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its documented process exit code."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except _ArgumentParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        if args.command != "extract":
            raise _CLIInputError(f"unsupported command: {args.command!r}")
        return _run_extract(args)
    except _CLIInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:
        print(f"internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
