"""Verify source/frozen CLI bytes against the O15 synthetic cross-platform golden."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path("tests/fixtures/o15/capture-folder")
E05_BANK = Path("tests/fixtures/o15/e05-bank-synthetic.json")
CONTEXT = Path("tests/fixtures/o15/canonical-context-synthetic.json")
V1_1_FIELDS = Path("tests/fixtures/o15/issued-invoice-v1-1-fields-synthetic.json")
GOLDEN_DIR = ROOT / "tests" / "golden" / "o15"


def _load_json(path: Path):
    return json.loads(path.read_bytes().decode("utf-8"))


def _validate_json(document: object, schema_path: Path) -> None:
    from jsonschema import Draft202012Validator

    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)


def _run_extractor(executable: Path | None, args: list[str], temp_dir: Path) -> subprocess.CompletedProcess[bytes]:
    if executable is None:
        prefix = [sys.executable, "-m", "image_extraction_adapter.cli"]
    else:
        resolved = executable.expanduser().resolve(strict=True)
        prefix = [str(resolved)]
    environment = os.environ.copy()
    if executable is None:
        additions = [str(ROOT / "src"), str(ROOT / "scripts")]
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join([*additions, *([existing] if existing else [])])
    return subprocess.run(
        [*prefix, *args],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _assert_bytes(label: str, actual: bytes, expected_path: Path) -> None:
    expected = expected_path.read_bytes()
    if actual != expected:
        actual_hash = hashlib.sha256(actual).hexdigest()
        expected_hash = hashlib.sha256(expected).hexdigest()
        actual_text = actual.decode("utf-8", errors="replace").splitlines()
        expected_text = expected.decode("utf-8", errors="replace").splitlines()
        diff = "\n".join(difflib.unified_diff(
            expected_text, actual_text, fromfile="golden", tofile="actual", lineterm=""
        ))
        if len(diff) > 6000:
            diff = diff[:6000] + "\n[diff truncated]"
        raise AssertionError(
            f"{label} differs from the pinned golden: actual {actual_hash} ({len(actual)} bytes), "
            f"expected {expected_hash} ({len(expected)} bytes)\n{diff}"
        )


def verify(executable: Path | None) -> None:
    manifest = _load_json(GOLDEN_DIR / "manifest.json")
    if manifest.get("schema_version") != "o15.e60-golden-manifest.v1":
        raise AssertionError("unsupported E-60 golden manifest")
    for relative, expected_hash in manifest.get("files", {}).items():
        actual_hash = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise AssertionError(f"pinned input/golden hash mismatch for {relative}")

    with tempfile.TemporaryDirectory(prefix="o15-e60-verify-") as raw_temp:
        temp_dir = Path(raw_temp)
        result_path = temp_dir / "capture-folder-result.json"
        capture = _run_extractor(
            executable,
            [
                "extract",
                "--capture-folder",
                FIXTURE.as_posix(),
                "--e05-bank",
                E05_BANK.as_posix(),
                "--out",
                str(result_path),
            ],
            temp_dir,
        )
        if capture.returncode != manifest["capture_exit_code"]:
            raise AssertionError(
                f"capture CLI exit: {capture.returncode}; expected {manifest['capture_exit_code']}; "
                f"stderr={capture.stderr.decode('utf-8', errors='replace')}"
            )
        if capture.stdout:
            raise AssertionError("--out capture invocation must leave stdout empty")
        result_bytes = result_path.read_bytes()
        if result_bytes.startswith(b"\xef\xbb\xbf") or b"\r" in result_bytes or not result_bytes.endswith(b"\n"):
            raise AssertionError("capture JSON must be UTF-8 without BOM, LF-only, and end in LF")
        result = json.loads(result_bytes.decode("utf-8"))
        _validate_json(result, ROOT / "schemas" / "extraction-bridge" / "v1" / "capture-folder-result.schema.json")
        _assert_bytes("capture-folder-result-v1", result_bytes, GOLDEN_DIR / "capture-folder-result-v1.json")

        demo_dir = temp_dir / "demo-output"
        demo_command = [
            sys.executable,
            str(ROOT / "scripts" / "demo_capture.py"),
            "--capture-folder",
            FIXTURE.as_posix(),
            "--out-dir",
            str(demo_dir),
            "--context",
            CONTEXT.as_posix(),
            "--v1-1-recorded-fields",
            V1_1_FIELDS.as_posix(),
            "--e05-bank",
            E05_BANK.as_posix(),
        ]
        if executable is not None:
            demo_command.extend(("--exe", str(executable.expanduser().resolve(strict=True))))
        environment = os.environ.copy()
        additions = [str(ROOT / "src"), str(ROOT / "scripts")]
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join([*additions, *([existing] if existing else [])])
        demo = subprocess.run(
            demo_command,
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if demo.returncode != manifest["demo_exit_code"]:
            raise AssertionError(
                f"demo script exit: {demo.returncode}; expected {manifest['demo_exit_code']}; "
                f"stderr={demo.stderr.decode('utf-8', errors='replace')}"
            )
        demo_bytes = demo.stdout
        if demo_bytes.startswith(b"\xef\xbb\xbf") or b"\r" in demo_bytes or not demo_bytes.endswith(b"\n"):
            raise AssertionError("demo JSON must be UTF-8 without BOM, LF-only, and end in LF")
        demo_document = json.loads(demo_bytes.decode("utf-8"))
        _validate_json(demo_document, ROOT / "schemas" / "o15" / "capture-demo-v1.schema.json")
        _assert_bytes("capture-demo-v1", demo_bytes, GOLDEN_DIR / "demo-output-v1.json")
        if not (demo_dir / "capture-folder-result.json").is_file():
            raise AssertionError("demo must retain the detailed local capture result beside its JSON output")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, help="optional frozen Windows kandoo-extract.exe")
    args = parser.parse_args(argv)
    try:
        verify(args.exe)
    except Exception as exc:
        message = f"E-60 verification FAILED: {type(exc).__name__}: {exc}"
        # Surface the deterministic synthetic diagnostic in the check annotation
        # as well as stderr so the failure is inspectable without raw logs.
        annotation = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=E-60 verification::{annotation}")
        print(message, file=sys.stderr)
        return 1
    print("E-60 verification PASS: source/frozen CLI outputs match the pinned synthetic golden bytes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
