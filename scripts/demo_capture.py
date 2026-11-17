"""Run the packaged extractor on a local capture folder and emit a demo envelope.

Owner data is written only to a caller-selected output directory outside this
repository. No output from this script is uploaded or included in Git by CI.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
V1_1_SCHEMA = ROOT / "docs" / "schemas" / "v1-1" / "issued-invoice-v1-1.schema.json"
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


class DemoInputError(ValueError):
    pass


def _repo_relative(path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def _load_json(path: Path, description: str) -> Any:
    try:
        return json.loads(path.expanduser().read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DemoInputError(f"cannot read {description} as UTF-8 JSON: {exc}") from exc


def _validate_v1_1_recorded_fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DemoInputError("v1.1 recorded fields must be a JSON object")
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - install guidance
        raise DemoInputError("jsonschema is required to validate v1.1 recorded fields") from exc
    schema = _load_json(V1_1_SCHEMA, "Canonical Invoice v1.1 schema")
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise DemoInputError(f"invalid v1.1 recorded fields at {location}: {first.message}")
    return value


def _validate_demo_envelope(value: dict[str, Any]) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:  # pragma: no cover - install guidance
        raise DemoInputError("jsonschema is required to validate the demo result") from exc
    schema = _load_json(ROOT / "schemas" / "o15" / "capture-demo-v1.schema.json", "capture-demo-v1 schema")
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise DemoInputError(f"invalid capture-demo-v1 at {location}: {first.message}")


def _command_prefix(executable: Path | None) -> list[str]:
    if executable is not None:
        path = executable.expanduser().resolve(strict=True)
        if not path.is_file():
            raise DemoInputError(f"--exe is not a file: {path}")
        return [str(path)]
    return [sys.executable, "-m", "image_extraction_adapter.cli"]


def _decode_diagnostic(data: bytes) -> str:
    """Normalize platform-native subprocess line endings for stable JSON output."""
    decoded = data.decode("utf-8", errors="replace")
    normalized = decoded.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def _run_cli(
    executable: Path | None,
    arguments: list[str],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[bytes]:
    prefix = _command_prefix(executable)
    environment = os.environ.copy()
    if executable is None:
        existing = environment.get("PYTHONPATH", "")
        additions = [str(ROOT / "src"), str(ROOT / "scripts")]
        environment["PYTHONPATH"] = os.pathsep.join([*additions, *([existing] if existing else [])])
    return subprocess.run(
        [*prefix, *arguments],
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local capture folder; emit Canonical v0 only when the extractor can validate a candidate."
    )
    parser.add_argument("--capture-folder", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True, help="new output directory outside the repository")
    parser.add_argument("--context", type=Path, help="producer-supplied Canonical v0 context; supports one-page folders only")
    parser.add_argument(
        "--v1-1-recorded-fields",
        type=Path,
        help="optional producer-recorded v1.1 extension fields; validated and passed through, never derived",
    )
    parser.add_argument("--e05-bank", type=Path, help="optional approved local E-05 bank")
    parser.add_argument("--templates", type=Path, help="optional local Glyph template bank")
    parser.add_argument("--drift-baseline", type=Path, help="optional matching drift baseline")
    parser.add_argument("--exe", type=Path, help="optional path to the Windows one-folder executable")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    output_dir = args.out_dir.expanduser().resolve(strict=False)
    if _repo_relative(output_dir):
        print("error: --out-dir must be outside the repository to keep owner data local", file=sys.stderr)
        return 30
    if output_dir.exists():
        print("error: --out-dir already exists; choose a new directory to avoid overwriting local evidence", file=sys.stderr)
        return 30
    if not output_dir.parent.is_dir():
        print("error: --out-dir parent directory must already exist", file=sys.stderr)
        return 30

    try:
        from image_extraction_adapter.capture_folder import inspect_capture_folder

        capture = inspect_capture_folder(args.capture_folder)
        v1_1 = (
            _validate_v1_1_recorded_fields(_load_json(args.v1_1_recorded_fields, "v1.1 recorded fields"))
            if args.v1_1_recorded_fields is not None
            else None
        )
        exe = args.exe
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 30

    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix=".kandoo-demo-", dir=output_dir.parent))
        result_path = staging / "capture-folder-result.json"
        command = ["extract", "--capture-folder", str(args.capture_folder.expanduser()), "--out", str(result_path)]
        if args.e05_bank is not None:
            command.extend(("--e05-bank", str(args.e05_bank.expanduser())))
        if args.templates is not None:
            command.extend(("--templates", str(args.templates.expanduser())))
        if args.drift_baseline is not None:
            command.extend(("--drift-baseline", str(args.drift_baseline.expanduser())))
        capture_process = _run_cli(exe, command, cwd=ROOT)
        if not result_path.is_file():
            if capture_process.stderr:
                sys.stderr.buffer.write(capture_process.stderr)
            print("error: extractor did not write the capture-folder result", file=sys.stderr)
            return 30
        capture_result = _load_json(result_path, "capture-folder result")

        canonical: dict[str, Any] | None = None
        canonical_code: int | None = None
        canonical_note: str | None = None
        if args.context is not None:
            if len(capture.pages) != 1:
                canonical_note = "Canonical v0 context is not applied to multi-page folders; no invoice was assembled."
            else:
                image_path = capture.pages[0].path
                canonical_process = _run_cli(
                    exe,
                    [
                        "extract",
                        "--image",
                        str(image_path),
                        "--context",
                        str(args.context.expanduser()),
                    ],
                    cwd=ROOT,
                )
                canonical_code = canonical_process.returncode
                if canonical_process.stdout.strip():
                    try:
                        candidate = json.loads(canonical_process.stdout.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise DemoInputError(f"extractor emitted invalid Canonical JSON: {exc}") from exc
                    from image_extraction_adapter.canonical_invoice import validate_canonical_invoice

                    valid, validation_errors = validate_canonical_invoice(candidate)
                    if not valid:
                        raise DemoInputError(f"extractor emitted invalid Canonical Invoice v0: {validation_errors}")
                    canonical = candidate
                elif canonical_process.stderr:
                    canonical_note = _decode_diagnostic(canonical_process.stderr)

        status = capture_result.get("status", "ERROR")
        verdict = capture_result.get("verdict", "REJECT")
        envelope: dict[str, Any] = {
            "demo_version": "o15.capture-demo.v1",
            "capture_status": status,
            "capture_verdict": verdict,
            "page_count": len(capture.pages),
            "canonical_invoice_v0": canonical,
            "canonical_exit_code": canonical_code,
            "canonical_note": canonical_note,
            "issued_invoice_v1_1_recorded_fields": v1_1,
        }
        _validate_demo_envelope(envelope)
        payload = (json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        (staging / "demo-output.json").write_bytes(payload)
        (staging / "capture-folder-result.json").write_bytes(
            (json.dumps(capture_result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        )
        # A missing Canonical candidate is a REVIEW outcome, not fabricated data.
        if capture_process.returncode not in {0, 10, 20}:
            return 30
        staging.rename(output_dir)
        sys.stdout.buffer.write(payload)
        sys.stdout.flush()
        return 0 if canonical is not None else (10 if status != "BLOCKED" else 20)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 30
    finally:
        if staging is not None and staging.exists():
            import shutil

            shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
