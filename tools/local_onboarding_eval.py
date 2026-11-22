#!/usr/bin/env python3
"""Owner-run, local-only aggregate evaluation for E-70/E-73.

The tool reads KandooPrintProbe capture folders and operator-confirmed numeric
labels locally. It never writes or prints invoice values, OCR text, names, phone
numbers, paths, job IDs, timestamps, images, or hashes. The only file it writes
is an aggregate JSON summary below the repository's git-ignored ``.owner-local``
directory.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from image_extraction_adapter.capture_folder import (  # noqa: E402
    CaptureBatchItem,
    CaptureFolder,
    extract_capture_folder,
    inspect_capture_batch,
)
from image_extraction_adapter.glyph_classifier import (  # noqa: E402
    normalize_label_text,
    parse_amount_text,
)

SUMMARY_NAME = "local-onboarding-eval-summary.local.json"
EXPECTED_NAME = "expected-fields.local.json"
EXPECTED_SCHEMA = "o16.owner-confirmed-numeric-fields.v1"
SUMMARY_SCHEMA = "o16.local-onboarding-eval-summary.v1"
MAX_EXPECTED_BYTES = 1_048_576
_QUANTITY = re.compile(r"^line\.(\d+)\.quantity$")
_LINE_TOTAL = re.compile(r"^line\.(\d+)\.total$")
_ALLOWED_ISSUES = frozenset({
    "AMBIGUOUS_REPORT",
    "AMBIGUOUS_SPL",
    "CAPTURE_FOLDER_NOT_DIRECTORY",
    "CAPTURE_FOLDER_NOT_FOUND",
    "CAPTURE_FOLDER_UNREADABLE",
    "DUPLICATE_JOB_ID",
    "DUPLICATE_REPORT_FIELD",
    "EMPTY_CAPTURE_BATCH",
    "EMPTY_JOB",
    "EMPTY_PNG",
    "EMPTY_REPORT",
    "EMPTY_SPL",
    "INVALID_CAPTURED_AT",
    "INVALID_JOB_ID",
    "INVALID_PAGE_COUNT",
    "INVALID_PNG",
    "INVALID_REPORT",
    "INVALID_SPL",
    "INVALID_SPL_SHA256",
    "JOB_IN_WRONG_FOLDER",
    "MISSING_JOB_ID",
    "MISSING_PNG",
    "MISSING_REPORT",
    "MISSING_SPL",
    "PAGE_COUNT_MISMATCH",
    "SPL_HASH_MISMATCH",
})


class EvaluationInputError(ValueError):
    """An input problem whose message is intentionally safe to discard."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise EvaluationInputError("INVALID_ARGUMENTS")


def _inside(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _overlaps(left: Path, right: Path) -> bool:
    return _inside(left, right) or _inside(right, left)


def _require_external_capture_root(value: str | Path, repository_root: Path) -> Path:
    requested = Path(value).expanduser()
    if requested.is_symlink():
        raise EvaluationInputError("UNSAFE_CAPTURE_ROOT")
    try:
        root = requested.resolve(strict=True)
        repo = repository_root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise EvaluationInputError("UNAVAILABLE_CAPTURE_ROOT") from exc
    if not root.is_dir() or _overlaps(root, repo):
        raise EvaluationInputError("UNSAFE_CAPTURE_ROOT")
    return root


def _no_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        result[key] = value
    return result


def _reject_nonstandard_json(value: str) -> None:
    raise EvaluationInputError("INVALID_EXPECTED_FIELDS")


def _normalise_expected(field_name: str, value: Any) -> tuple[str, int, str]:
    if not isinstance(value, str):
        raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
    normalized = normalize_label_text(value)
    quantity_match = _QUANTITY.fullmatch(field_name)
    if quantity_match is not None:
        if not normalized or not all("۰" <= character <= "۹" for character in normalized):
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        numeric_value = int(normalized.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        if numeric_value <= 0:
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        return normalized, numeric_value, "quantity"

    total_match = _LINE_TOTAL.fullmatch(field_name)
    if total_match is not None:
        numeric_value = parse_amount_text(normalized)
        if numeric_value is None:
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        return normalized, numeric_value, "line_total"

    if field_name == "invoice.payable":
        numeric_value = parse_amount_text(normalized)
        if numeric_value is None:
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        return normalized, numeric_value, "payable"
    raise EvaluationInputError("INVALID_EXPECTED_FIELDS")


def _load_expected_fields(
    job_path: Path,
    *,
    page_count: int,
) -> dict[tuple[int, str], tuple[int, str]]:
    path = job_path / EXPECTED_NAME
    if path.is_symlink() or not path.is_file():
        raise EvaluationInputError("MISSING_EXPECTED_FIELDS")
    try:
        if path.stat().st_size > MAX_EXPECTED_BYTES:
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        document = json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=_no_duplicate_object_keys,
            parse_constant=_reject_nonstandard_json,
        )
    except EvaluationInputError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise EvaluationInputError("INVALID_EXPECTED_FIELDS") from exc

    if not isinstance(document, dict) or set(document) != {"schema_version", "pages"}:
        raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
    if document.get("schema_version") != EXPECTED_SCHEMA:
        raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
    pages = document.get("pages")
    if not isinstance(pages, list) or not pages:
        raise EvaluationInputError("INVALID_EXPECTED_FIELDS")

    parsed: dict[tuple[int, str], tuple[int, str]] = {}
    for page in pages:
        if not isinstance(page, dict) or set(page) != {"page_index", "fields"}:
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        page_index = page.get("page_index")
        fields = page.get("fields")
        if type(page_index) is not int or not 1 <= page_index <= page_count:
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        if not isinstance(fields, dict) or not fields:
            raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
        for field_name, raw_expected in fields.items():
            if not isinstance(field_name, str):
                raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
            _normalized, expected_value, category = _normalise_expected(field_name, raw_expected)
            key = (page_index, field_name)
            if key in parsed:
                raise EvaluationInputError("INVALID_EXPECTED_FIELDS")
            parsed[key] = (expected_value, category)
    return parsed


def _empty_summary() -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA,
        "outcome": "NOT_SCORED",
        "capture_batch": {
            "folders_seen": 0,
            "intake_ready": 0,
            "held_for_review": 0,
        },
        "operator_labels": {
            "valid": 0,
            "missing": 0,
            "invalid": 0,
        },
        "evaluation": {
            "jobs_evaluated": 0,
            "jobs_not_evaluated": 0,
            "extraction_errors": 0,
        },
        "fields": {
            "quantity": {"expected": 0, "pass": 0, "fail": 0, "review": 0, "missing": 0},
            "line_total": {"expected": 0, "pass": 0, "fail": 0, "review": 0, "missing": 0},
            "payable": {"expected": 0, "pass": 0, "fail": 0, "review": 0, "missing": 0},
        },
        "capture_issue_counts": {},
    }


def _candidate_index(result: Any) -> dict[tuple[int, str], list[dict[str, Any]]]:
    indexed: dict[tuple[int, str], list[dict[str, Any]]] = {}
    if not isinstance(result, dict):
        return indexed
    candidates = result.get("numeric_candidates")
    if not isinstance(candidates, dict):
        return indexed
    for category in ("quantity", "line_total", "payable"):
        values = candidates.get(category)
        if not isinstance(values, list):
            continue
        for candidate in values:
            if not isinstance(candidate, dict):
                continue
            page_index = candidate.get("page_index")
            field_name = candidate.get("field_name")
            if type(page_index) is not int or not isinstance(field_name, str):
                continue
            indexed.setdefault((page_index, field_name), []).append(candidate)
    return indexed


def _actual_integer(field_name: str, value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    normalized = normalize_label_text(value)
    if _QUANTITY.fullmatch(field_name):
        if not normalized or not all("۰" <= character <= "۹" for character in normalized):
            return None
        numeric_value = int(normalized.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        return numeric_value if numeric_value > 0 else None
    return parse_amount_text(normalized)


def _record_field_result(
    summary: dict[str, Any],
    expected: dict[tuple[int, str], tuple[int, str]],
    result: Any,
    *,
    extraction_failed: bool,
) -> None:
    candidates = _candidate_index(result)
    for key, (expected_value, category) in expected.items():
        counts = summary["fields"][category]
        counts["expected"] += 1
        found = candidates.get(key, [])
        if extraction_failed or len(found) > 1:
            counts["review"] += 1
            continue
        if not found:
            counts["missing"] += 1
            continue
        candidate = found[0]
        if candidate.get("status") != "EXTRACTED":
            counts["review"] += 1
            continue
        actual_value = _actual_integer(key[1], candidate.get("raw_value"))
        if actual_value is None or actual_value != expected_value:
            counts["fail"] += 1
        else:
            counts["pass"] += 1


def _issue_code(value: Any) -> str:
    if isinstance(value, str) and value in _ALLOWED_ISSUES:
        return value
    return "OTHER_CAPTURE_ISSUE"


def evaluate_capture_batch(
    capture_root: str | Path,
    *,
    repository_root: str | Path = ROOT,
    extractor: Callable[[str | Path], Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a local batch and return aggregate counts only.

    ``extractor`` is injectable for synthetic tests; production uses the normal
    E-02/E-05/E-06 capture-folder adapter.
    """
    root = _require_external_capture_root(capture_root, Path(repository_root))
    try:
        entries = tuple(root.iterdir())
        items = inspect_capture_batch(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise EvaluationInputError("UNAVAILABLE_CAPTURE_ROOT") from exc

    summary = _empty_summary()
    summary["capture_batch"]["folders_seen"] = sum(
        entry.is_dir() and not entry.is_symlink() for entry in entries
    )
    summary["capture_batch"]["intake_ready"] = sum(item.status == "READY" for item in items)
    summary["capture_batch"]["held_for_review"] = sum(item.status != "READY" for item in items)
    issues: Counter[str] = Counter()
    for item in items:
        issues.update(_issue_code(problem.code) for problem in item.problems)
    summary["capture_issue_counts"] = dict(sorted(issues.items()))

    run_extractor = extractor or extract_capture_folder
    for item in items:
        capture = item.capture
        if item.status != "READY" or capture is None:
            summary["evaluation"]["jobs_not_evaluated"] += 1
            continue

        try:
            expected = _load_expected_fields(capture.path, page_count=len(capture.pages))
        except EvaluationInputError as exc:
            summary["operator_labels"]["missing" if str(exc) == "MISSING_EXPECTED_FIELDS" else "invalid"] += 1
            summary["evaluation"]["jobs_not_evaluated"] += 1
            continue

        summary["operator_labels"]["valid"] += 1
        summary["evaluation"]["jobs_evaluated"] += 1
        result: Any = None
        extraction_failed = False
        try:
            result = run_extractor(capture.path)
            if not isinstance(result, dict) or result.get("status") in {"ERROR", "BLOCKED"}:
                extraction_failed = True
                summary["evaluation"]["extraction_errors"] += 1
        except Exception:
            # Do not relay exception text: filesystem paths or OCR content may
            # appear in third-party exception messages.
            extraction_failed = True
            summary["evaluation"]["extraction_errors"] += 1
        _record_field_result(summary, expected, result, extraction_failed=extraction_failed)

    expected_count = sum(field["expected"] for field in summary["fields"].values())
    fail_count = sum(field["fail"] for field in summary["fields"].values())
    unresolved_count = sum(field["review"] + field["missing"] for field in summary["fields"].values())
    has_intake_issues = bool(summary["capture_batch"]["held_for_review"])
    has_label_issues = bool(summary["operator_labels"]["missing"] or summary["operator_labels"]["invalid"])
    if expected_count == 0:
        outcome = "NOT_SCORED"
    elif fail_count:
        outcome = "FAIL"
    elif unresolved_count or has_intake_issues or has_label_issues:
        outcome = "REVIEW"
    else:
        outcome = "PASS"
    summary["outcome"] = outcome
    return summary


def _summary_path(value: str | Path | None, repository_root: Path) -> Path:
    repo = repository_root.resolve(strict=True)
    owner_output_requested = repo / ".owner-local"
    if owner_output_requested.is_symlink():
        raise EvaluationInputError("UNSAFE_SUMMARY_PATH")
    owner_output = owner_output_requested.resolve(strict=False)
    if owner_output.exists() and not owner_output.is_dir():
        raise EvaluationInputError("UNSAFE_SUMMARY_PATH")
    target = (
        Path(value).expanduser().resolve(strict=False)
        if value is not None
        else owner_output / SUMMARY_NAME
    )
    if target.name != SUMMARY_NAME or not _inside(target, owner_output):
        raise EvaluationInputError("UNSAFE_SUMMARY_PATH")
    return target


def write_aggregate_summary(
    summary: dict[str, Any],
    *,
    output_path: str | Path | None = None,
    repository_root: str | Path = ROOT,
) -> Path:
    repo = Path(repository_root).expanduser().resolve(strict=True)
    target = _summary_path(output_path, repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".local-onboarding-eval.", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return target


def render_aggregate_summary(summary: dict[str, Any]) -> str:
    batch = summary["capture_batch"]
    labels = summary["operator_labels"]
    evaluation = summary["evaluation"]
    lines = [
        "Local E-70/E-73 evaluation (aggregate counts only)",
        f"Outcome: {summary['outcome']}",
        f"Capture folders: seen={batch['folders_seen']} ready={batch['intake_ready']} review={batch['held_for_review']}",
        f"Operator labels: valid={labels['valid']} missing={labels['missing']} invalid={labels['invalid']}",
        f"Jobs: evaluated={evaluation['jobs_evaluated']} not_evaluated={evaluation['jobs_not_evaluated']} extraction_errors={evaluation['extraction_errors']}",
        "Field counts (expected / pass / fail / review / missing):",
    ]
    for field_name in ("quantity", "line_total", "payable"):
        field = summary["fields"][field_name]
        lines.append(
            f"  {field_name}: {field['expected']} / {field['pass']} / {field['fail']} / {field['review']} / {field['missing']}"
        )
    issue_counts = summary["capture_issue_counts"]
    nonzero_issues = ", ".join(f"{code}={count}" for code, count in issue_counts.items() if count)
    lines.append(f"Capture issue codes: {nonzero_issues if nonzero_issues else 'none'}")
    lines.append(f"Aggregate summary file: {SUMMARY_NAME} (git-ignored)")
    return "\n".join(lines)


def _build_parser() -> _ArgumentParser:
    parser = _ArgumentParser(
        description="Evaluate local capture folders against operator-confirmed numeric fields; emit aggregate counts only."
    )
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--summary-out", type=Path, help="optional path under the repository's .owner-local directory")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    repository_root: str | Path = ROOT,
    extractor: Callable[[str | Path], Any] | None = None,
) -> int:
    try:
        args = _build_parser().parse_args(argv)
        summary = evaluate_capture_batch(
            args.capture_root,
            repository_root=repository_root,
            extractor=extractor,
        )
        write_aggregate_summary(
            summary,
            output_path=args.summary_out,
            repository_root=repository_root,
        )
    except EvaluationInputError:
        print("Local E-70/E-73 evaluation could not run (check arguments, local folders, and numeric labels).", file=sys.stderr)
        return 30
    except Exception:
        # Never print arbitrary exception strings or a traceback: they may
        # include owner paths or text read from a private capture.
        print("Local E-70/E-73 evaluation could not complete; no private details were emitted.", file=sys.stderr)
        return 30

    print(render_aggregate_summary(summary))
    return 0 if summary["outcome"] == "PASS" else 10


if __name__ == "__main__":
    raise SystemExit(main())
