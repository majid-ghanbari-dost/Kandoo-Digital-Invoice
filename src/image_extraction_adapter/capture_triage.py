"""Plain-language triage for a local SPL/PNG/Report.txt capture folder.

The E-30 CLI and result schema remain the machine contract. This module formats
that result for operators without changing its exit-code mapping.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence, TextIO

from .capture_folder import extract_capture_folder, status_exit_code


REPORT_LANGUAGE = "English"
PIL_MISSING = "ModuleNotFoundError: No module named 'PIL'"
EXIT_READY = 0
EXIT_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_ERROR = 30


class _ArgumentError(Exception):
    """Raised instead of argparse's default exit code 2."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _ArgumentError(message)


def _natural_name_key(name: str) -> tuple[Any, ...]:
    parts = re.split(r"(\d+)", name.casefold())
    key = tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)
    return (*key, (2, name))


def _entry_record(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink():
            return {"name": path.name, "kind": "symbolic link", "size": None}
        if path.is_file():
            return {"name": path.name, "kind": "file", "size": path.stat().st_size}
        if path.is_dir():
            return {"name": path.name, "kind": "directory", "size": None}
    except OSError:
        return {"name": path.name, "kind": "unreadable entry", "size": None}
    return {"name": path.name, "kind": "other entry", "size": None}


def _inventory(folder: str | Path) -> dict[str, Any]:
    requested = Path(folder).expanduser()
    try:
        if not requested.exists():
            return {"state": "not-found", "spl": [], "png": [], "report": [], "other": []}
        if not requested.is_dir():
            return {"state": "not-directory", "spl": [], "png": [], "report": [], "other": []}
        children = tuple(requested.iterdir())
    except (OSError, RuntimeError):
        return {"state": "unreadable", "spl": [], "png": [], "report": [], "other": []}

    records = [_entry_record(path) for path in children]
    records.sort(key=lambda item: _natural_name_key(item["name"]))
    file_records = [item for item in records if item["kind"] in {"file", "symbolic link"}]
    spl = [item for item in file_records if Path(item["name"]).suffix.casefold() == ".spl"]
    png = [item for item in file_records if Path(item["name"]).suffix.casefold() == ".png"]
    report = [item for item in file_records if item["name"].casefold() == "report.txt"]
    required_names = {item["name"] for item in (*spl, *png, *report)}
    other = [item for item in records if item["name"] not in required_names]
    return {"state": "listed", "spl": spl, "png": png, "report": report, "other": other}


def _format_entries(label: str, entries: list[dict[str, Any]]) -> str:
    if not entries:
        contents = "none"
    else:
        rendered: list[str] = []
        for item in entries:
            name = json.dumps(item["name"], ensure_ascii=False)
            detail = f" ({item['size']} bytes)" if item.get("size") is not None else ""
            if item.get("kind") not in {None, "file"}:
                detail += f" [{item['kind']}]"
            rendered.append(f"{name}{detail}")
        contents = ", ".join(rendered)
    return f"- {label} ({len(entries)}): {contents}"


def _is_pil_missing(value: Any) -> bool:
    if isinstance(value, str):
        return PIL_MISSING in value
    if isinstance(value, dict):
        return any(_is_pil_missing(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_is_pil_missing(child) for child in value)
    return False


def _problem_stage(code: str) -> str:
    if code.startswith("CAPTURE_FOLDER_"):
        return "Folder access"
    if code in {"MISSING_SPL", "AMBIGUOUS_SPL", "EMPTY_SPL", "INVALID_SPL"}:
        return "SPL intake"
    if code in {"MISSING_PNG", "INVALID_PNG"}:
        return "PNG validation"
    if code in {
        "MISSING_REPORT",
        "AMBIGUOUS_REPORT",
        "INVALID_REPORT",
        "EMPTY_REPORT",
        "DUPLICATE_JOB_ID",
        "DUPLICATE_REPORT_FIELD",
        "INVALID_JOB_ID",
        "INVALID_CAPTURED_AT",
        "INVALID_PAGE_COUNT",
        "EMPTY_JOB",
        "PAGE_COUNT_MISMATCH",
        "INVALID_SPL_SHA256",
        "SPL_HASH_MISMATCH",
        "CAPTURED_AT_MISMATCH",
    }:
        return "Report.txt checks"
    return "Capture intake"


def _problem_explanation(error: dict[str, Any]) -> str:
    code = str(error.get("code", "CAPTURE_VALIDATION_ERROR"))
    message = str(error.get("message", ""))
    if PIL_MISSING in message:
        return (
            "Environment issue: PNG decoding could not run because the required dependency is missing: "
            f"{PIL_MISSING}. The PNG contents were not decoded, so this is not a finding that the file is corrupt."
        )
    if "ModuleNotFoundError:" in message or "ImportError:" in message:
        dependency_error = next(
            (line for line in message.splitlines() if "ModuleNotFoundError:" in line or "ImportError:" in line),
            "required image-decoding dependency unavailable",
        )
        return f"Environment issue: a required dependency is unavailable: {dependency_error}."
    if code == "INVALID_PNG":
        if any(token in message for token in ("PermissionError", "Permission denied", "Access is denied")):
            return "Environment issue: the PNG could not be read because file access was denied."
        if any(token in message for token in ("UnidentifiedImageError", "not PNG", "PNG file is empty", "not a regular file")):
            return "Data problem: the PNG is empty, malformed, or not a regular PNG file."
        if "PNG cannot be decoded:" in message:
            return "Data problem: the available PNG decoder rejected the page contents."
        return "PNG validation did not pass; the report cannot classify the cause more specifically."

    explanations = {
        "CAPTURE_FOLDER_NOT_FOUND": "The capture folder could not be found.",
        "CAPTURE_FOLDER_NOT_DIRECTORY": "The supplied path is not a folder.",
        "CAPTURE_FOLDER_UNREADABLE": "The capture folder could not be listed.",
        "MISSING_SPL": "Data problem: no SPL file is present; exactly one is required.",
        "AMBIGUOUS_SPL": "Data problem: more than one SPL file is present; exactly one is required.",
        "EMPTY_SPL": "Data problem: the SPL file is empty.",
        "INVALID_SPL": "Data problem: the SPL entry is not a readable regular file.",
        "MISSING_PNG": "Data problem: no PNG page is present; at least one is required.",
        "MISSING_REPORT": "Data problem: Report.txt is missing.",
        "AMBIGUOUS_REPORT": "Data problem: more than one Report.txt file is present; exactly one is required.",
        "INVALID_REPORT": "Data problem: Report.txt could not be read as UTF-8 text.",
        "EMPTY_REPORT": "Data problem: Report.txt contains no text.",
        "DUPLICATE_JOB_ID": "Data problem: Report.txt contains more than one spool-job ID.",
        "DUPLICATE_REPORT_FIELD": "Data problem: Report.txt repeats a recognized metadata field.",
        "INVALID_JOB_ID": "Data problem: the spool-job ID in Report.txt is empty or invalid.",
        "INVALID_CAPTURED_AT": "Data problem: the timestamp in Report.txt is not valid ISO 8601 with an explicit offset.",
        "INVALID_PAGE_COUNT": "Data problem: the page count in Report.txt is not a non-negative whole number.",
        "EMPTY_JOB": "Data problem: Report.txt declares a job with zero pages.",
        "PAGE_COUNT_MISMATCH": "Data problem: the page count in Report.txt does not match the PNG pages present.",
        "INVALID_SPL_SHA256": "Data problem: the SPL digest in Report.txt is not a 64-character hexadecimal value.",
        "SPL_HASH_MISMATCH": "Data problem: the SPL bytes do not match the digest recorded in Report.txt.",
        "CAPTURED_AT_MISMATCH": "Data problem: the supplied timestamp conflicts with the timestamp in Report.txt.",
    }
    return explanations.get(code, f"The adapter reported {code.replace('_', ' ').lower()}.")


def _append_inventory(lines: list[str], inventory: dict[str, Any]) -> None:
    lines.append("What is present")
    if inventory["state"] == "not-found":
        lines.append("- Folder contents: unavailable (the folder was not found).")
        return
    if inventory["state"] == "not-directory":
        lines.append("- Folder contents: unavailable (the supplied path is not a folder).")
        return
    if inventory["state"] == "unreadable":
        lines.append("- Folder contents: unavailable (the folder could not be listed).")
        return
    lines.extend((
        _format_entries("SPL entries", inventory["spl"]),
        _format_entries("PNG pages", inventory["png"]),
        _format_entries("Report.txt entries", inventory["report"]),
        _format_entries("Other entries", inventory["other"]),
    ))
    lines.append("- SPL contents are inventoried only; this tool does not interpret the spool format.")


def _append_metadata(lines: list[str], result: dict[str, Any]) -> None:
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, dict):
        return
    metadata = artifacts.get("probe_metadata")
    if not isinstance(metadata, dict):
        return
    job_id = "present" if metadata.get("spool_job_id") is not None else "not supplied"
    timestamp = "present" if metadata.get("captured_at") is not None else "not supplied"
    page_count = metadata.get("page_count")
    page_text = str(page_count) if isinstance(page_count, int) else "not supplied"
    lines.append(
        f"- Recognized report metadata: spool-job ID {job_id}; timestamp {timestamp}; reported page count {page_text}."
    )


def _append_intake(lines: list[str], result: dict[str, Any], inventory: dict[str, Any]) -> bool:
    errors = result.get("errors")
    errors = [item for item in errors if isinstance(item, dict)] if isinstance(errors, list) else []
    if not errors:
        lines.append(
            "- Capture intake: ACCEPTED — the adapter's required artifact and report checks passed."
        )
        _append_metadata(lines, result)
        return True

    pil_errors = [item for item in errors if PIL_MISSING in str(item.get("message", ""))]
    if pil_errors:
        lines.append("- Capture intake: BLOCKED during PNG decoding because of an environment limitation.")
        for error in pil_errors:
            lines.append(f"  - {_problem_explanation(error)}")
        for error in errors:
            if PIL_MISSING not in str(error.get("message", "")):
                stage = _problem_stage(str(error.get("code", "")))
                lines.append(f"  - Additional {stage.lower()} finding: {_problem_explanation(error)}")
        if not inventory.get("png"):
            lines.append("  - No PNG file was confirmed in the folder inventory.")
        return False

    lines.append("- Capture intake: BLOCKED — one or more required artifact checks rejected the folder.")
    grouped: dict[str, list[str]] = {}
    for error in errors:
        stage = _problem_stage(str(error.get("code", "")))
        grouped.setdefault(stage, []).append(_problem_explanation(error))
    for stage in ("Folder access", "SPL intake", "PNG validation", "Report.txt checks", "Capture intake"):
        explanations = grouped.get(stage, [])
        if explanations:
            lines.append(f"  - {stage}: " + " ".join(explanations))
    return False


def _append_e02(lines: list[str], page: dict[str, Any], folder: str | Path) -> None:
    file_name = json.dumps(str(page.get("file", "unnamed page")), ensure_ascii=False)
    e02 = page.get("e02")
    page_error = page.get("error")
    if not isinstance(e02, dict):
        code = page_error.get("code", "E02_NOT_RUN") if isinstance(page_error, dict) else "E02_NOT_RUN"
        explanation = {
            "E02_PIPELINE_ERROR": "the image pipeline could not complete for this page.",
            "E02_NOT_RUN": "the image pipeline did not produce a page result.",
        }.get(str(code), "the image pipeline did not produce a page result.")
        lines.append(f"- Image extraction (E-02), {file_name}: BLOCKED — {explanation}")
        return

    status = str(e02.get("status", "UNKNOWN"))
    if status == "AUTO_CANDIDATE":
        row_count = e02.get("row_count")
        row_text = f"{row_count} row(s)" if isinstance(row_count, int) else "the detected rows"
        detail = f"numeric extraction produced a candidate for {row_text} and the arithmetic check passed."
        lines.append(f"- Image extraction (E-02), {file_name}: CANDIDATE — {detail}")
    elif status == "REVIEW":
        detail = str(e02.get("reason") or "the extraction needs review.")
        detail = _safe_detail(detail, folder)
        lines.append(f"- Image extraction (E-02), {file_name}: REVIEW — {detail}")
    elif status == "REJECT":
        detail = str(e02.get("reason") or "the extraction pipeline blocked this page.")
        detail = _safe_detail(detail, folder)
        lines.append(f"- Image extraction (E-02), {file_name}: BLOCKED — {detail}")
    else:
        lines.append(f"- Image extraction (E-02), {file_name}: {status} — the page did not reach a known extraction outcome.")


def _safe_detail(value: str, folder: str | Path) -> str:
    text = value.replace("\\", "/")
    requested = Path(folder).expanduser()
    candidates = {str(requested), requested.as_posix()}
    try:
        resolved = requested.resolve(strict=False)
        candidates.update((str(resolved), resolved.as_posix()))
    except (OSError, RuntimeError):
        pass
    for candidate in sorted(candidates, key=len, reverse=True):
        if candidate:
            text = text.replace(candidate.replace("\\", "/"), "capture folder")
    return " ".join(text.split())


def _append_e05(lines: list[str], page: dict[str, Any]) -> None:
    file_name = json.dumps(str(page.get("file", "unnamed page")), ensure_ascii=False)
    e05 = page.get("e05")
    if not isinstance(e05, dict):
        lines.append(f"- Layout matching (E-05), {file_name}: NOT EVALUATED — no layout result was produced.")
        return
    status = str(e05.get("status", "NOT_EVALUATED"))
    if status == "MATCH":
        detail = "an existing layout pattern matched; this is a pattern match, not proof of accuracy."
        if e05.get("independent_evidence") is False:
            detail += " The match uses a repository fixture-derived bank and is not independent evidence."
        lines.append(f"- Layout matching (E-05), {file_name}: MATCH — {detail}")
    elif status == "NO_MATCH":
        lines.append(f"- Layout matching (E-05), {file_name}: NO MATCH — no configured layout pattern matched this page.")
    else:
        lines.append(
            f"- Layout matching (E-05), {file_name}: NOT EVALUATED — a safe layout observation or available template bank was not produced."
        )


def _e06_reason(code: str) -> str:
    known = {
        "PARTIAL_MATCH": "The capture folder does not provide the caller-supplied identity, customer context, and product-name mapping required for a final decision.",
        "CURRENCY_UNIT_UNCONFIRMED": "The selected template bank does not confirm a currency unit.",
        "NEW_LAYOUT": "The layout is not established in the selected template bank.",
        "LOW_CONFIDENCE": "The extracted fields did not meet the confidence threshold.",
        "NO_MATCH": "No configured layout matched the extracted page.",
        "SELF_MATCH_RESUBSTITUTION": "This page is part of the repository fixture set used by the development bank; the match is not independent evidence.",
        "ONBOARDING_WARMUP": "The current template bank is not ready for a final decision.",
        "TEMPLATE_BANK_UNLOCKED": "The selected template bank is not locked for a final decision.",
        "DIGIT_COVERAGE_INSUFFICIENT": "The template bank does not cover the required digit evidence.",
        "MULTI_TEMPLATE_AMBIGUOUS": "More than one template remains plausible.",
        "NUMS_INCONSISTENT": "The extracted numeric fields did not pass consistency checks.",
        "ACCOUNTING_ADJUSTMENT_UNSUPPORTED": "The observed adjustment could not be supported by the current checks.",
        "ATTENTION_REQUIRED": "The result requires additional operator review.",
        "CANONICAL_STATE_NOT_READY": "The candidate is not in a state ready for a final decision.",
        "OWNER_VERIFICATION_REQUIRED": "Additional owner verification is required before a final decision.",
    }
    if code in known:
        return known[code]
    return code.replace("_", " ").strip().capitalize() + "."


def _append_e06(lines: list[str], result: dict[str, Any]) -> None:
    e06 = result.get("e06")
    if not isinstance(e06, dict):
        lines.append("- Final decision (E-06): NOT RUN — capture intake stopped before a final decision could be evaluated.")
        return
    verdict = str(e06.get("verdict", "REVIEW"))
    reasons = [str(code) for code in e06.get("reason_codes", []) if code]
    if reasons:
        details = " ".join(_e06_reason(code) for code in reasons)
    else:
        details = "No E-06 reason codes were returned."
    lines.append(f"- Final decision (E-06): {verdict} — {details}")


def _outcome_text(exit_code: int, result: dict[str, Any]) -> str:
    if exit_code == EXIT_BLOCKED and _is_pil_missing(result):
        return "BLOCKED — environment limitation"
    labels = {
        EXIT_READY: "ACCEPTED / READY",
        EXIT_REVIEW: "REVIEW",
        EXIT_BLOCKED: "BLOCKED / REJECTED",
        EXIT_ERROR: "ERROR",
    }
    return labels.get(exit_code, "ERROR")


def format_report(
    folder: str | Path,
    result: dict[str, Any],
    *,
    inventory: dict[str, Any] | None = None,
) -> str:
    """Format one deterministic, plain-language report without absolute paths."""
    inventory = inventory if inventory is not None else _inventory(folder)
    exit_code = status_exit_code(result)
    lines = [
        "Capture-folder triage",
        f"Report language: {REPORT_LANGUAGE} (follows this repository's CLI and documentation convention).",
        "",
    ]
    _append_inventory(lines, inventory)
    lines.append("")
    lines.append("Pipeline decisions")
    intake_accepted = _append_intake(lines, result, inventory)
    pages = result.get("pages")
    pages = [page for page in pages if isinstance(page, dict)] if isinstance(pages, list) else []
    if pages:
        for page in pages:
            _append_e02(lines, page, folder)
            _append_e05(lines, page)
        _append_e06(lines, result)
    elif not intake_accepted:
        lines.append("- Image extraction (E-02): NOT RUN — artifact intake did not produce a decoded PNG page.")
        lines.append("- Layout matching (E-05): NOT RUN — no page reached layout matching.")
        lines.append("- Final decision (E-06): NOT RUN — intake stopped before final routing.")
    else:
        _append_e06(lines, result)
    lines.append("")
    lines.append("- Accuracy: NOT SCORED — the capture-folder input does not include expected-value labels.")
    lines.append(f"Overall result: {_outcome_text(exit_code, result)} (E-30 exit code {exit_code}).")
    return "\n".join(lines) + "\n"


def _write_utf8(stream: TextIO, text: str) -> None:
    payload = text.encode("utf-8")
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(payload)
        buffer.flush()
    else:
        stream.write(text)
        stream.flush()


def _runtime_error_result(exc: Exception, folder: str | Path) -> dict[str, Any]:
    return {
        "result_version": "capture-folder-result-v1",
        "status": "ERROR",
        "verdict": "REJECT",
        "verdict_source": "capture-triage-runtime",
        "capture_folder": str(folder),
        "errors": [{"code": "TRIAGE_RUNTIME_ERROR", "message": f"{type(exc).__name__}: {exc}"}],
        "pages": [],
        "e06": None,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _ArgumentParser(
        prog="python scripts/triage_capture_folder.py",
        description="Print a plain-language triage report for one local capture folder.",
    )
    parser.add_argument(
        "--capture-folder",
        type=Path,
        required=True,
        metavar="PATH",
        help="folder containing SPL, PNG page(s), and Report.txt",
    )
    try:
        args = parser.parse_args(argv)
    except _ArgumentError as exc:
        _write_utf8(sys.stderr, f"Input error: {exc}\n")
        return EXIT_ERROR

    try:
        result = extract_capture_folder(args.capture_folder)
    except Exception as exc:
        result = _runtime_error_result(exc, args.capture_folder)
    report = format_report(args.capture_folder, result)
    try:
        _write_utf8(sys.stdout, report)
    except OSError:
        _write_utf8(sys.stderr, "Output error: could not write the triage report.\n")
        return EXIT_ERROR
    return status_exit_code(result)


if __name__ == "__main__":  # pragma: no cover - exercised by the script wrapper
    raise SystemExit(main())
