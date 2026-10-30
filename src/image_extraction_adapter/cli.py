"""Command-line bridge from local E-02 extraction to Canonical Invoice v0.

Producer-owned Canonical Invoice context is supplied through a UTF-8 JSON file;
this CLI never invents platform identifiers, customer data, or product names.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .canonical_invoice import validate_canonical_invoice
from .capture_folder import extract_capture_folder, status_exit_code
from .multi_evidence import evaluate_multi_evidence
from .onboarding_cli import OnboardingCLIError, add_onboard_subcommands, run_onboard
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
        description="Run local E-02 extraction or adapt a KandooPrintProbe capture folder.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract = subparsers.add_parser(
        "extract",
        help="extract one image or adapt a local capture folder",
        description="Extract one image or run the E-02/E-05/E-06 capture-folder adapter.",
    )
    source = extract.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, metavar="PATH")
    source.add_argument(
        "--capture-folder",
        type=Path,
        metavar="PATH",
        help="KandooPrintProbe folder containing SPL, one or more PNG pages, and Report.txt",
    )
    extract.add_argument(
        "--context",
        type=Path,
        metavar="PATH",
        help="UTF-8 JSON object with producer-supplied canonical_context fields (required with --image)",
    )
    extract.add_argument(
        "--out",
        type=Path,
        metavar="PATH",
        help="write the capture-folder result JSON to PATH instead of stdout",
    )
    extract.add_argument(
        "--e05-bank",
        type=Path,
        metavar="PATH",
        help="optional approved E-05 layout bank; default uses the repository's fixture-derived bank",
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
    extract.add_argument(
        "--drift-baseline",
        type=Path,
        metavar="PATH",
        help="DR-1 onboarding glyph-distance baseline; defaults by Glyph template-bank path",
    )
    extract.add_argument(
        "--drift-report",
        type=Path,
        metavar="PATH",
        help="write the image-mode DR-1 distance record to a JSON sidecar",
    )
    extract.add_argument(
        "--multi-evidence",
        action="store_true",
        help="require all six local evidence witnesses before AUTO_CANDIDATE",
    )
    add_onboard_subcommands(subparsers)
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
        context = json.loads(path.read_bytes().decode("utf-8"))
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


def _capture_human_summary(result: dict[str, Any]) -> str:
    status = str(result.get("status", "ERROR"))
    verdict = str(result.get("verdict", "REJECT"))
    pages = result.get("pages", [])
    artifacts = result.get("artifacts", {})
    numeric = result.get("numeric_candidates", {})
    candidate_count = sum(len(numeric.get(name, [])) for name in ("quantity", "line_total", "payable"))
    e05_matches = sum(page.get("e05", {}).get("status") == "MATCH" for page in pages)
    lines = [
        f"{status} / {verdict}: {len(pages)} page(s); {candidate_count} numeric candidate(s); "
        f"E-05 matches {e05_matches}/{len(pages)}."
    ]
    if artifacts.get("extra_files"):
        lines.append(f"Ignored extra files: {', '.join(artifacts['extra_files'])}")
    for error in result.get("errors", []):
        lines.append(f"{error.get('code', 'ERROR')}: {error.get('message', '')}")
    for page in pages:
        if page.get("error"):
            lines.append(
                f"Page {page.get('page_index')}: {page['error'].get('code')}: "
                f"{page['error'].get('message')}"
            )
        else:
            e02 = page.get("e02")
            if isinstance(e02, dict) and e02.get("reason"):
                lines.append(f"Page {page.get('page_index')} E-02: {e02['reason']}")
    e06 = result.get("e06")
    if isinstance(e06, dict):
        reasons = ", ".join(e06.get("reason_codes", []))
        if reasons:
            lines.append(f"E-06: {e06.get('verdict', 'REVIEW')} ({reasons})")
    return "\n".join(lines)


def _write_capture_result(result: dict[str, Any], output_path: Path | None) -> bool:
    payload = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if output_path is None:
        stdout_buffer = getattr(sys.stdout, "buffer", None)
        if stdout_buffer is not None:
            stdout_buffer.write(payload)
            stdout_buffer.flush()
        else:  # Supports in-process tests redirecting stdout to StringIO.
            sys.stdout.write(payload.decode("utf-8"))
            sys.stdout.flush()
        return True

    target = output_path.expanduser().absolute()
    parent = target.parent
    if not parent.is_dir():
        raise OSError(f"output parent directory does not exist: {parent}")

    capture_root_text = result.get("capture_folder")
    if isinstance(capture_root_text, str):
        capture_root = Path(capture_root_text).resolve(strict=False)
        if capture_root.is_dir():
            for candidate in capture_root.iterdir():
                if not (candidate.is_file() or candidate.is_symlink()):
                    continue
                if (
                    candidate.suffix.casefold() in {".spl", ".png"}
                    or candidate.name.casefold() == "report.txt"
                ) and candidate.resolve(strict=False) == target.resolve(strict=False):
                    raise OSError("--out must not overwrite a required capture artifact")

    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=parent
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, target)
        return True
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _run_capture_folder(args: argparse.Namespace) -> int:
    if args.context is not None or args.multi_evidence or args.drift_report is not None:
        result = {
            "result_version": "capture-folder-result-v1",
            "status": "ERROR",
            "verdict": "REJECT",
            "verdict_source": "cli-option-validation",
            "capture_folder": str(args.capture_folder),
            "errors": [{
                "code": "UNSUPPORTED_CAPTURE_OPTION",
                "message": "--context, --multi-evidence, and --drift-report are not used by --capture-folder mode",
            }],
            "scoring_fields": ["quantity", "line_total", "payable"],
            "accuracy": {
                "status": "NOT_SCORED",
                "expected_values_available": False,
                "fields": ["quantity", "line_total", "payable"],
                "reason": "capture folders do not carry expected-value labels",
            },
            "pages": [],
            "numeric_candidates": {name: [] for name in ("quantity", "line_total", "payable")},
            "e06": None,
        }
    else:
        _validate_captured_at(args.captured_at)
        try:
            result = extract_capture_folder(
                args.capture_folder,
                templates_path=args.templates,
                e05_bank_path=args.e05_bank,
                captured_at=args.captured_at,
                drift_baseline_path=args.drift_baseline,
            )
        except Exception as exc:
            result = {
                "result_version": "capture-folder-result-v1",
                "status": "ERROR",
                "verdict": "REJECT",
                "verdict_source": "capture-adapter-exception",
                "capture_folder": str(args.capture_folder),
                "errors": [{
                    "code": "CAPTURE_ADAPTER_ERROR",
                    "message": f"{type(exc).__name__}: {exc}",
                }],
                "scoring_fields": ["quantity", "line_total", "payable"],
                "accuracy": {
                    "status": "NOT_SCORED",
                    "expected_values_available": False,
                    "fields": ["quantity", "line_total", "payable"],
                    "reason": "capture folders do not carry expected-value labels",
                },
                "pages": [],
                "numeric_candidates": {
                    name: [] for name in ("quantity", "line_total", "payable")
                },
                "e06": None,
            }

    requested_capture_path = args.capture_folder.expanduser()
    if not requested_capture_path.is_absolute():
        # Relative invocations are recorded as supplied (with POSIX separators)
        # so a golden invocation has the same JSON bytes on every platform.
        result["capture_folder"] = requested_capture_path.as_posix()

    try:
        _write_capture_result(result, args.out)
    except (OSError, TypeError, ValueError) as exc:
        result = {
            **result,
            "status": "ERROR",
            "verdict": "REJECT",
            "verdict_source": "capture-result-output",
            "errors": [
                *result.get("errors", []),
                {"code": "OUTPUT_WRITE_FAILED", "message": f"{type(exc).__name__}: {exc}"},
            ],
        }
        try:
            _write_capture_result(result, None)
        except Exception as fallback_exc:  # pragma: no cover - broken stdout
            print(f"ERROR / REJECT: could not emit result JSON: {fallback_exc}", file=sys.stderr)
            return EXIT_ERROR
        print(_capture_human_summary(result), file=sys.stderr)
        return EXIT_ERROR

    print(_capture_human_summary(result), file=sys.stderr)
    return status_exit_code(result)


def _run_extract(args: argparse.Namespace) -> int:
    if args.capture_folder is not None:
        return _run_capture_folder(args)
    if args.context is None:
        raise _CLIInputError("--context is required when using --image")
    if args.out is not None or args.e05_bank is not None:
        raise _CLIInputError("--out and --e05-bank are only supported with --capture-folder")
    if args.drift_report is not None and not args.drift_report.expanduser().parent.is_dir():
        raise _CLIInputError("--drift-report parent directory must already exist")
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
        drift_baseline_path=args.drift_baseline,
    )
    glyph_drift = getattr(result, "glyph_drift", None)
    if args.drift_report is not None:
        drift_record = glyph_drift
        if drift_record is None:
            drift_record = {
                "status": "NOT_EVALUATED",
                "reason": "glyph extraction did not produce per-symbol readings",
                "baseline_id": None,
                "template_library_id": None,
                "mean_distance_by_symbol": {},
                "triggered_symbols": [],
                "diagnostics": ["glyph extraction did not produce per-symbol readings"],
                "pipeline_status": result.status,
            }
        versioned_drift_record = {
            "schema_version": "e28.glyph-drift-report.v1",
            **dict(drift_record),
        }
        target = args.drift_report.expanduser().absolute()
        _write_capture_result(versioned_drift_record, target)

    if result.status == "REJECT":
        print("REJECT: extraction is blocked; no Canonical Invoice was emitted.", file=sys.stderr)
        for detail in _pipeline_diagnostics(result):
            print(f"  {detail}", file=sys.stderr)
        return EXIT_BLOCKED

    if result.status not in {"AUTO_CANDIDATE", "REVIEW"}:
        raise RuntimeError(f"pipeline returned unsupported status: {result.status!r}")

    effective_status = result.status
    if args.multi_evidence:
        evidence = evaluate_multi_evidence(
            result.cell_results,
            result.arithmetic_gate,
            result,
        )
        if not evidence.all_pass:
            print(
                "multi-evidence: REVIEW; failed witnesses: "
                + ", ".join(evidence.reasons),
                file=sys.stderr,
            )
            for name in evidence.reasons:
                detail = evidence.witnesses[name]["detail"]
                print(f"  {name}: {detail}", file=sys.stderr)
            if result.status == "AUTO_CANDIDATE":
                effective_status = "REVIEW"

    invoice = result.canonical_invoice
    if invoice is None:
        details = _pipeline_diagnostics(result)
        if effective_status == "REVIEW":
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
    return EXIT_READY if effective_status == "AUTO_CANDIDATE" else EXIT_REVIEW


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its documented process exit code."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except _ArgumentParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        if args.command == "extract":
            return _run_extract(args)
        if args.command == "onboard":
            return run_onboard(args)
        raise _CLIInputError(f"unsupported command: {args.command!r}")
    except (_CLIInputError, OnboardingCLIError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:
        print(f"internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
