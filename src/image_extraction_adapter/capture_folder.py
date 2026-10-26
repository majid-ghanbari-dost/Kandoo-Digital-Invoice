"""Capture-folder adapter for KandooPrintProbe SPL/PNG/Report.txt outputs.

The adapter validates the capture envelope, runs the existing E-02 image
pipeline for every ordered PNG page, produces E-05 layout matches, and asks E-06
for a fail-closed invoice verdict. It never invents Canonical Invoice identity,
customer, or product-name data; without those producer inputs, E-06 must remain
REVIEW. Capture-folder errors and blocked page processing never become silent
page skips.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from e05_template_bank import (
    LayoutObservation,
    TemplateBank,
    build_template_bank,
    load_template_bank,
    match_observation,
)
from e06_onboarding_verdict import Verdict, evaluate_verdict
from image_extraction_adapter.pipeline_v0 import (
    DEFAULT_TEMPLATE_BANK_PATH,
    REPOSITORY_ROOT,
    detect_payable_bbox,
    extract_pipeline_v0,
)
from image_extraction_adapter.preprocessing import detect_layout_safe


RESULT_VERSION = "capture-folder-result-v1"
REAL_FIXTURE_DIR = REPOSITORY_ROOT / "tests" / "fixtures" / "real"
DEFAULT_E05_CANONICAL_DIR = REAL_FIXTURE_DIR / "canonical"
DEFAULT_E05_LABELS_PATH = REAL_FIXTURE_DIR / "labels.json"
SCORING_FIELDS = ("quantity", "line_total", "payable")
_QUANTITY_FIELD = re.compile(r"^line\.(\d+)\.quantity$")
_LINE_TOTAL_FIELD = re.compile(r"^line\.(\d+)\.total$")


@dataclass(frozen=True)
class CaptureProblem:
    code: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict[str, str]:
        value = {"code": self.code, "message": self.message}
        if self.path is not None:
            value["path"] = self.path
        return value


@dataclass(frozen=True)
class CapturePage:
    path: Path
    page_index: int
    width: int
    height: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index,
            "file": self.path.name,
            "width": self.width,
            "height": self.height,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class CaptureFolder:
    path: Path
    spl_path: Path
    spl_size: int
    spl_sha256: str
    report_path: Path
    report_size: int
    report_sha256: str
    report_line_count: int
    pages: tuple[CapturePage, ...]
    extra_files: tuple[str, ...]

    def artifacts_dict(self) -> dict[str, Any]:
        return {
            "spl": {
                "file": self.spl_path.name,
                "bytes": self.spl_size,
                "sha256": self.spl_sha256,
            },
            "report": {
                "file": self.report_path.name,
                "bytes": self.report_size,
                "lines": self.report_line_count,
                "sha256": self.report_sha256,
            },
            "pages": [page.to_dict() for page in self.pages],
            "extra_files": list(self.extra_files),
            "page_order": "natural, case-insensitive filename order",
        }


class CaptureFolderValidationError(ValueError):
    def __init__(self, folder: Path, problems: tuple[CaptureProblem, ...]):
        super().__init__("capture folder failed artifact validation")
        self.folder = folder
        self.problems = problems


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _natural_sort_key(path: Path) -> tuple[Any, ...]:
    parts = re.split(r"(\d+)", path.name.casefold())
    key = tuple((0, int(part)) if part.isdigit() else (1, part) for part in parts)
    return (*key, (2, path.name))


def _is_safe_regular_file(path: Path, root: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        return path.resolve(strict=True).parent == root.resolve(strict=True)
    except OSError:
        return False


def _inspect_png(path: Path, root: Path) -> tuple[int, int, str]:
    if not _is_safe_regular_file(path, root):
        raise ValueError("PNG must be a regular file directly inside the capture folder")
    if path.stat().st_size <= 0:
        raise ValueError("PNG file is empty")
    try:
        from PIL import Image

        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError(f"file decodes as {image.format!r}, not PNG")
            width, height = image.size
            image.verify()
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"PNG cannot be decoded: {type(exc).__name__}: {exc}") from exc
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive")
    return width, height, _sha256_file(path)


def inspect_capture_folder(folder: str | Path) -> CaptureFolder:
    """Validate the required envelope and return pages in deterministic order.

    Required files are one non-empty ``*.spl``, one readable non-empty
    ``Report.txt``, and at least one decodable ``*.png``. Extensions and the
    report filename are matched case-insensitively. Multiple SPL or Report
    files are ambiguous and fail closed. Unknown sibling files are tolerated
    and listed in ``extra_files``.
    """
    requested = Path(folder).expanduser()
    try:
        root = requested.resolve(strict=True)
    except OSError as exc:
        raise CaptureFolderValidationError(
            requested,
            (CaptureProblem("CAPTURE_FOLDER_NOT_FOUND", str(exc), str(requested)),),
        ) from exc
    if not root.is_dir():
        raise CaptureFolderValidationError(
            root,
            (CaptureProblem("CAPTURE_FOLDER_NOT_DIRECTORY", "capture path is not a directory", str(root)),),
        )
    try:
        children = tuple(root.iterdir())
    except OSError as exc:
        raise CaptureFolderValidationError(
            root,
            (CaptureProblem("CAPTURE_FOLDER_UNREADABLE", str(exc), str(root)),),
        ) from exc

    files = tuple(path for path in children if path.is_file() or path.is_symlink())
    spl_files = tuple(sorted((path for path in files if path.suffix.casefold() == ".spl"), key=_natural_sort_key))
    png_files = tuple(sorted((path for path in files if path.suffix.casefold() == ".png"), key=_natural_sort_key))
    report_files = tuple(sorted((path for path in files if path.name.casefold() == "report.txt"), key=_natural_sort_key))
    required_paths = set(spl_files) | set(png_files) | set(report_files)
    extras = tuple(path.name for path in sorted(files, key=_natural_sort_key) if path not in required_paths)
    problems: list[CaptureProblem] = []

    if not spl_files:
        problems.append(CaptureProblem("MISSING_SPL", "required spooled print file (*.spl) is missing", str(root)))
    elif len(spl_files) > 1:
        problems.append(CaptureProblem("AMBIGUOUS_SPL", "expected exactly one SPL file", str(root)))

    if not png_files:
        problems.append(CaptureProblem("MISSING_PNG", "at least one rendered page (*.png) is required", str(root)))

    if not report_files:
        problems.append(CaptureProblem("MISSING_REPORT", "required Report.txt is missing", str(root)))
    elif len(report_files) > 1:
        problems.append(CaptureProblem("AMBIGUOUS_REPORT", "expected exactly one Report.txt", str(root)))

    if problems:
        raise CaptureFolderValidationError(root, tuple(problems))

    spl_path = spl_files[0]
    if not _is_safe_regular_file(spl_path, root):
        problems.append(CaptureProblem("INVALID_SPL", "SPL must be a regular file directly inside the capture folder", spl_path.name))
    elif spl_path.stat().st_size <= 0:
        problems.append(CaptureProblem("EMPTY_SPL", "SPL file is empty", spl_path.name))

    report_path = report_files[0]
    report_bytes = b""
    report_text = ""
    if not _is_safe_regular_file(report_path, root):
        problems.append(CaptureProblem("INVALID_REPORT", "Report.txt must be a regular file directly inside the capture folder", report_path.name))
    else:
        report_readable = True
        try:
            report_bytes = report_path.read_bytes()
            report_text = report_bytes.decode("utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            report_readable = False
            problems.append(CaptureProblem("INVALID_REPORT", f"Report.txt is unreadable UTF-8 text: {exc}", report_path.name))
        if report_readable and not report_text.strip():
            problems.append(CaptureProblem("EMPTY_REPORT", "Report.txt contains no report text", report_path.name))

    inspected_pages: list[CapturePage] = []
    for index, png_path in enumerate(png_files, start=1):
        try:
            width, height, digest = _inspect_png(png_path, root)
        except (OSError, ValueError) as exc:
            problems.append(CaptureProblem("INVALID_PNG", str(exc), png_path.name))
            continue
        inspected_pages.append(CapturePage(png_path, index, width, height, digest))

    if problems:
        raise CaptureFolderValidationError(root, tuple(problems))

    assert spl_path.stat().st_size > 0
    return CaptureFolder(
        path=root,
        spl_path=spl_path,
        spl_size=spl_path.stat().st_size,
        spl_sha256=_sha256_file(spl_path),
        report_path=report_path,
        report_size=len(report_bytes),
        report_sha256=hashlib.sha256(report_bytes).hexdigest(),
        report_line_count=len(report_text.splitlines()),
        pages=tuple(inspected_pages),
        extra_files=extras,
    )


@lru_cache(maxsize=1)
def _default_e05_bank() -> TemplateBank:
    """Build the repository's existing fixture-derived E-05 bank once.

    This default is useful for the local adapter and synthetic tests. It is not
    independent or calibrated real-capture evidence; production callers should
    provide their approved, locked bank with ``e05_bank_path``.
    """
    return build_template_bank(DEFAULT_E05_CANONICAL_DIR, DEFAULT_E05_LABELS_PATH)


def _fixture_source_hashes() -> dict[str, str]:
    try:
        labels = json.loads(DEFAULT_E05_LABELS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    sources: dict[str, str] = {}
    for entry in labels.get("invoices", []):
        source_id = str(entry.get("id", ""))
        relative_path = entry.get("path")
        if not source_id or not isinstance(relative_path, str):
            continue
        path = (REAL_FIXTURE_DIR / relative_path).resolve()
        if path.is_file():
            sources[_sha256_file(path)] = source_id
    return sources


def _numeric_candidate(cell: Any, page_index: int) -> dict[str, Any] | None:
    quantity = _QUANTITY_FIELD.fullmatch(cell.field_name)
    line_total = _LINE_TOTAL_FIELD.fullmatch(cell.field_name)
    if quantity is not None:
        kind = "quantity"
        line_index = int(quantity.group(1))
    elif line_total is not None:
        kind = "line_total"
        line_index = int(line_total.group(1))
    elif cell.field_name == "invoice.payable":
        kind = "payable"
        line_index = None
    else:
        return None
    return {
        "page_index": page_index,
        "kind": kind,
        "field_name": cell.field_name,
        "line_index": line_index,
        "raw_value": cell.raw_value,
        "status": cell.status,
        "confidence": cell.confidence,
        "reason": cell.reason,
    }


def _min_extraction_confidence(pages: list[dict[str, Any]]) -> float | None:
    confidence_values: list[float] = []
    for page in pages:
        for value in page["numeric_candidates"]:
            confidence = value.get("confidence")
            if value["status"] != "EXTRACTED" or confidence is None:
                continue
            try:
                normalized = float(confidence)
            except (TypeError, ValueError, OverflowError):
                continue
            if normalized > 1:
                normalized /= 100.0
            if 0 <= normalized <= 1:
                confidence_values.append(normalized)
    return min(confidence_values) if confidence_values else None


def _page_observation(
    page: CapturePage,
    pipeline_result: Any,
) -> tuple[LayoutObservation | None, str]:
    try:
        from PIL import Image

        with Image.open(page.path) as image:
            image.load()
            rgb = image.convert("RGB")
        try:
            safety = detect_layout_safe(rgb)
            if safety.status != "OK" or safety.geometry is None:
                return None, f"layout not safe for E-05: {safety.status}: {safety.reason}"
            payable_bbox = detect_payable_bbox(rgb, safety.geometry)
            if payable_bbox is None:
                return None, "E-05 requires an unambiguous payable box; none was detected"
            values = tuple(
                (cell.field_name, cell.raw_value)
                for cell in pipeline_result.cell_results
                if cell.status == "EXTRACTED"
                and (
                    _QUANTITY_FIELD.fullmatch(cell.field_name)
                    or _LINE_TOTAL_FIELD.fullmatch(cell.field_name)
                    or cell.field_name == "invoice.payable"
                )
            )
            observation = LayoutObservation(
                source_id=f"capture-page-{page.page_index:04d}-{page.sha256[:12]}",
                image_width=rgb.width,
                image_height=rgb.height,
                column_boundaries=tuple(safety.geometry.column_boundaries),
                row_bands=tuple(tuple(band) for band in safety.geometry.row_bands),
                payable_bbox=tuple(payable_bbox),
                field_values=values,
            )
            return observation, "ready"
        finally:
            rgb.close()
    except Exception as exc:
        return None, f"E-05 observation could not be built: {type(exc).__name__}: {exc}"


def _error_result(
    folder: str | Path,
    problems: tuple[CaptureProblem, ...],
    *,
    captured_at: str | None = None,
) -> dict[str, Any]:
    return {
        "result_version": RESULT_VERSION,
        "status": "ERROR",
        "verdict": Verdict.REJECT.value,
        "verdict_source": "capture-artifact-validation",
        "capture_folder": str(Path(folder).expanduser()),
        "captured_at": captured_at,
        "errors": [problem.to_dict() for problem in problems],
        "scoring_fields": list(SCORING_FIELDS),
        "accuracy": {
            "status": "NOT_SCORED",
            "expected_values_available": False,
            "fields": list(SCORING_FIELDS),
            "reason": "capture folders do not carry expected-value labels",
        },
        "pages": [],
        "numeric_candidates": {name: [] for name in SCORING_FIELDS},
        "e06": None,
    }


def extract_capture_folder(
    folder: str | Path,
    *,
    templates_path: str | Path = DEFAULT_TEMPLATE_BANK_PATH,
    e05_bank_path: str | Path | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Run E-02, E-05, and fail-closed E-06 on one capture folder.

    The result is JSON-serializable. It never produces ACCEPT because the
    capture-folder contract does not contain producer-owned Canonical Invoice
    context (identities, customer and product-name mapping). This missing
    context is surfaced as an E-06 REVIEW rather than invented. An optional
    offset-aware ``captured_at`` value is passed to E-02 and retained in the
    result; Probe ``Report.txt`` content itself is not parsed.
    """
    try:
        capture = inspect_capture_folder(folder)
    except CaptureFolderValidationError as exc:
        return _error_result(exc.folder, exc.problems, captured_at=captured_at)

    bank: TemplateBank | None = None
    bank_error: str | None = None
    try:
        bank = load_template_bank(e05_bank_path) if e05_bank_path else _default_e05_bank()
    except Exception as exc:
        bank_error = f"{type(exc).__name__}: {exc}"

    training_hashes = _fixture_source_hashes()
    page_results: list[dict[str, Any]] = []
    observations: list[LayoutObservation] = []
    blocked_pages: list[int] = []
    for page in capture.pages:
        try:
            pipeline = extract_pipeline_v0(
                page.path,
                templates_path=templates_path,
                captured_at=captured_at,
            )
        except Exception as exc:
            page_results.append({
                **page.to_dict(),
                "status": "BLOCKED",
                "error": {"code": "E02_PIPELINE_ERROR", "message": f"{type(exc).__name__}: {exc}"},
                "numeric_candidates": [],
                "e02": None,
                "e05": {"status": "NOT_EVALUATED", "reason": "E-02 did not produce a page result"},
            })
            blocked_pages.append(page.page_index)
            continue

        numeric_candidates = [
            candidate
            for cell in pipeline.cell_results
            if (candidate := _numeric_candidate(cell, page.page_index)) is not None
        ]
        e05_result: dict[str, Any]
        observation, observation_reason = _page_observation(page, pipeline)
        if bank_error is not None:
            e05_result = {"status": "NOT_EVALUATED", "reason": f"E-05 bank unavailable: {bank_error}"}
        elif bank is None:
            e05_result = {"status": "NOT_EVALUATED", "reason": "E-05 bank unavailable"}
        elif observation is None:
            e05_result = {"status": "NOT_EVALUATED", "reason": observation_reason}
        else:
            observations.append(observation)
            try:
                match = match_observation(bank, observation)
                e05_result = {
                    "status": "MATCH" if match.matched else "NO_MATCH",
                    "confidence_score": match.confidence_score,
                    "matched": match.matched,
                    "template_id": match.template_id,
                    "component_scores": match.component_scores,
                    "reasons": list(match.reasons),
                    "numeric_evidence_present": match.numeric_evidence_present,
                }
            except Exception as exc:
                e05_result = {
                    "status": "NOT_EVALUATED",
                    "reason": f"E-05 match failed closed: {type(exc).__name__}: {exc}",
                }

        source_fixture = training_hashes.get(page.sha256)
        if source_fixture is not None:
            e05_result["resubstitution_source_fixture"] = source_fixture
            e05_result["independent_evidence"] = False

        page_status = "BLOCKED" if pipeline.status == "REJECT" else pipeline.status
        if page_status == "BLOCKED":
            blocked_pages.append(page.page_index)
        page_results.append({
            **page.to_dict(),
            "status": page_status,
            "e02": {
                "status": pipeline.status,
                "reason": pipeline.reason,
                "layout_status": pipeline.layout_status,
                "layout_reason": pipeline.layout_reason,
                "row_count": pipeline.row_count,
                "canonical_blockers": list(pipeline.canonical_blockers),
            },
            "e05": e05_result,
            "numeric_candidates": numeric_candidates,
        })

    first_observation = observations[0] if observations else None
    try:
        e06_result = evaluate_verdict(
            None,
            bank,
            first_observation,
            _min_extraction_confidence(page_results),
            processed_invoice_count=0,
            template_bank_locked=False,
            d14_agreement_signed=False,
            missing_fields=(
                "producer-supplied Canonical Invoice identity and customer context",
                "human-readable product-name mapping",
            ),
            require_kit_digit_coverage=False,
        ).to_dict()
    except Exception as exc:
        e06_result = {
            "verdict": Verdict.REVIEW.value,
            "reason_codes": ["NEW_LAYOUT"],
            "details": [f"E-06 evaluation failed closed: {type(exc).__name__}: {exc}"],
            "template_match": None,
        }

    numeric_candidates: dict[str, list[dict[str, Any]]] = {
        name: [] for name in SCORING_FIELDS
    }
    invoice_lines: list[dict[str, Any]] = []
    next_line_index = 0
    for page in page_results:
        local_values: dict[int, dict[str, dict[str, Any]]] = {}
        for candidate in page["numeric_candidates"]:
            kind = candidate["kind"]
            numeric_candidates[kind].append(candidate)
            if kind in {"quantity", "line_total"} and candidate["line_index"] is not None:
                local_values.setdefault(candidate["line_index"], {})[kind] = candidate
        e02 = page.get("e02") or {}
        row_count = e02.get("row_count")
        if not isinstance(row_count, int) or row_count < 0:
            row_count = max(local_values, default=-1) + 1
        for local_index in range(row_count):
            fields = local_values.get(local_index, {})
            invoice_lines.append({
                "line_index": next_line_index,
                "source_page_index": page["page_index"],
                "source_line_index": local_index,
                "quantity": fields.get("quantity"),
                "line_total": fields.get("line_total"),
            })
            next_line_index += 1

    has_blocked_pages = bool(blocked_pages)
    overall_verdict = (
        Verdict.REJECT.value if has_blocked_pages else e06_result.get("verdict", Verdict.REVIEW.value)
    )
    if has_blocked_pages:
        status = "BLOCKED"
    elif overall_verdict == Verdict.REJECT.value:
        status = Verdict.REJECT.value
    else:
        status = overall_verdict
    currency_unit = getattr(bank, "currency_unit", None) if bank is not None else None
    currency_unit_confirmed = (
        type(currency_unit) is str and currency_unit in ("rial", "toman")
    )
    return {
        "result_version": RESULT_VERSION,
        "status": status,
        "verdict": overall_verdict,
        "verdict_source": "E-06 with E-02 block override" if has_blocked_pages else "E-06",
        "capture_folder": str(capture.path),
        "captured_at": captured_at,
        "artifacts": capture.artifacts_dict(),
        "scoring_fields": list(SCORING_FIELDS),
        "accuracy": {
            "status": "NOT_SCORED",
            "expected_values_available": False,
            "fields": list(SCORING_FIELDS),
            "reason": "capture folders do not carry expected-value labels",
        },
        "invoice_candidates": {
            "line_items": invoice_lines,
            "payable_candidates": numeric_candidates["payable"],
            "note": "Page rows are concatenated in natural page order. Payable is not silently summed or selected across pages.",
        },
        "numeric_candidates": numeric_candidates,
        "pages": page_results,
        "e05_bank": {
            "status": "AVAILABLE" if bank is not None else "UNAVAILABLE",
            "currency_unit": currency_unit,
            "currency_unit_status": (
                "UNAVAILABLE"
                if bank is None
                else "CONFIRMED" if currency_unit_confirmed else "UNCONFIRMED"
            ),
            "template_count": len(bank.templates) if bank is not None else 0,
            "source_invoice_ids": sorted({
                source_id
                for template in (bank.templates if bank is not None else ())
                for source_id in template.source_invoice_ids
            }),
            "error": bank_error,
            "independent_validation": False if e05_bank_path is None else None,
        },
        "e06": e06_result,
        "blocked_pages": blocked_pages,
        "errors": [],
    }


def status_exit_code(result: dict[str, Any]) -> int:
    """Map adapter outcomes to the existing extraction CLI process codes."""
    if result.get("status") == "ERROR":
        return 30
    if result.get("status") == "BLOCKED" or result.get("verdict") == Verdict.REJECT.value:
        return 20
    if result.get("verdict") == Verdict.REVIEW.value:
        return 10
    return 0
