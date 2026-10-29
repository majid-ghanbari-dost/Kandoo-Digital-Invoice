"""E-05/E-06/E-08 command wrappers with E-16 v1 artifact boundaries.

The ordinary build path only trains from E-05's provenance-checked,
operator-confirmed labels/canonical pairs. The explicitly named E-20 option is
reserved for synthetic mechanics checks and never marks those values as
operator-confirmed.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

from e05_template_bank import (
    LayoutObservation,
    TemplateBank,
    build_template_bank,
    parse_labeled_integer,
)
from e06_onboarding_verdict import (
    ManualOverride,
    Verdict,
    evaluate_verdict,
)
from e08_new_type_flow import CandidateRegistry, detect_invoice_type


EXIT_READY = 0
EXIT_REVIEW = 10
EXIT_BLOCKED = 20
EXIT_ERROR = 30
E20_STORE_ID = "synthetic-second-store"


class OnboardingCLIError(Exception):
    """A user-facing onboarding CLI input, schema, or artifact-write error."""


def add_onboard_subcommands(subparsers: Any) -> None:
    """Add the ``onboard`` command tree to the extraction CLI parser."""
    onboard = subparsers.add_parser(
        "onboard",
        help="build a Mode B template bank, evaluate a verdict, or propose a new type",
        description=(
            "Local E-05/E-06/E-08 onboarding commands. Artifacts use the frozen "
            "schemas/mode-b/v1 E-16 contracts."
        ),
    )
    commands = onboard.add_subparsers(dest="onboard_command", required=True)

    build = commands.add_parser(
        "build",
        help="build an E-16 template-bank artifact from capture labels",
        description=(
            "Build an E-05 template bank from a capture root, operator-confirmed labels, "
            "and their validated Canonical v0 sidecar. An explicit E-20-only synthetic "
            "path is available for mechanics tests."
        ),
    )
    source = build.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--capture-root",
        type=Path,
        metavar="DIR",
        help="root containing the PNG files referenced by --labels (paths must stay inside it)",
    )
    source.add_argument(
        "--synthetic-e20-report",
        type=Path,
        metavar="JSON",
        help="test-only E-20 report; requires --synthetic-e20-values and the fixed synthetic store ID",
    )
    build.add_argument("--synthetic-e20-values", type=Path, metavar="JSON")
    build.add_argument("--canonical-dir", type=Path, metavar="DIR")
    build.add_argument("--labels", type=Path, metavar="JSON")
    build.add_argument("--store-id", required=True, help="opaque store ID; never inferred")
    build.add_argument(
        "--currency-unit",
        required=True,
        choices=("rial", "toman"),
        help="explicit onboarding unit; no inference or conversion is performed",
    )
    build.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.85,
        help="E-05 layout-match threshold (default: 0.85)",
    )
    build.add_argument("--created-at", help="optional ISO 8601 timestamp with an explicit UTC offset")
    build.add_argument("--output", type=Path, required=True, metavar="PATH")

    verdict = commands.add_parser(
        "verdict",
        help="evaluate one onboarding invoice with E-06",
        description="Write an E-16 onboarding-verdict artifact tied to the exact E-16 bank bytes.",
    )
    verdict.add_argument("--template-bank", "--bank", dest="template_bank", type=Path, required=True)
    verdict.add_argument("--store-id", required=True, help="must equal the bank artifact store ID")
    verdict.add_argument("--invoice-id", required=True, help="opaque invoice ID; must match --invoice when supplied")
    verdict.add_argument("--invoice", type=Path, metavar="JSON", help="Canonical Invoice v0; omit only for an absent candidate")
    verdict.add_argument("--observation", type=Path, metavar="JSON", help="E-05 LayoutObservation JSON")
    verdict.add_argument("--processed-invoice-count", type=int, required=True)
    bank_state = verdict.add_mutually_exclusive_group(required=True)
    bank_state.add_argument("--template-bank-locked", dest="template_bank_locked", action="store_true")
    bank_state.add_argument("--template-bank-unlocked", dest="template_bank_locked", action="store_false")
    d14_state = verdict.add_mutually_exclusive_group(required=True)
    d14_state.add_argument("--d14-agreement-signed", dest="d14_agreement_signed", action="store_true")
    d14_state.add_argument("--d14-agreement-required", dest="d14_agreement_signed", action="store_false")
    coverage = verdict.add_mutually_exclusive_group(required=True)
    coverage.add_argument("--require-kit-digit-coverage", dest="require_kit_digit_coverage", action="store_true")
    coverage.add_argument("--no-require-kit-digit-coverage", dest="require_kit_digit_coverage", action="store_false")
    verdict.add_argument("--extraction-confidence", type=float, help="optional confidence in [0, 1]")
    verdict.add_argument("--missing-field", action="append", default=[], metavar="FIELD")
    verdict.add_argument("--manual-override", type=Path, metavar="JSON", help="caller-supplied E-06 owner-review audit shape")
    verdict.add_argument("--evaluated-at", help="optional ISO 8601 timestamp with an explicit UTC offset")
    verdict.add_argument("--output", type=Path, required=True, metavar="PATH")
    verdict.set_defaults(
        template_bank_locked=None,
        d14_agreement_signed=None,
        require_kit_digit_coverage=None,
    )

    register = commands.add_parser(
        "register-type",
        help="run E-08 detection and export a proposed E-16 new-type candidate",
        description=(
            "Run E-08 against a locked E-05 bank. A candidate remains PROPOSED and separate "
            "from the active bank; no bank mutation or durable audit storage occurs."
        ),
    )
    register.add_argument("--template-bank", "--bank", dest="template_bank", type=Path, required=True)
    register.add_argument("--store-id", required=True, help="must equal the bank and Canonical store IDs")
    register.add_argument("--invoice-id", required=True, help="must equal Canonical Invoice v0 invoice_id")
    register.add_argument("--invoice", type=Path, required=True, metavar="JSON")
    register.add_argument("--observation", type=Path, required=True, metavar="JSON")
    register.add_argument("--accepted-invoice-count", type=int, required=True)
    register_bank_state = register.add_mutually_exclusive_group(required=True)
    register_bank_state.add_argument("--template-bank-locked", dest="template_bank_locked", action="store_true")
    register_bank_state.add_argument("--template-bank-unlocked", dest="template_bank_locked", action="store_false")
    register_d14_state = register.add_mutually_exclusive_group(required=True)
    register_d14_state.add_argument("--d14-agreement-signed", dest="d14_agreement_signed", action="store_true")
    register_d14_state.add_argument("--d14-agreement-required", dest="d14_agreement_signed", action="store_false")
    register.add_argument("--extraction-confidence", type=float, help="optional confidence in [0, 1]")
    register.add_argument("--detected-at", help="optional E-08 timestamp with an explicit UTC offset")
    register.add_argument("--exported-at", help="optional artifact timestamp with an explicit UTC offset")
    register.add_argument("--output", type=Path, required=True, metavar="PATH")
    register.set_defaults(template_bank_locked=None, d14_agreement_signed=None)


def _repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _schemas_dir() -> Path:
    return _repo_root() / "schemas" / "mode-b" / "v1"


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON numeric constant {value!r} is not allowed")


def _read_json(path: Path, description: str) -> Any:
    try:
        encoded = path.expanduser().read_bytes()
    except OSError as exc:
        raise OnboardingCLIError(f"cannot read {description} file {path}: {exc}") from exc
    try:
        text = encoded.decode("utf-8")
        return json.loads(text, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise OnboardingCLIError(f"invalid UTF-8 JSON in {description} file {path}: {exc}") from exc


def _require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OnboardingCLIError(f"{description} must be a JSON object")
    return value


def _opaque_id(value: Any, description: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise OnboardingCLIError(f"{description} must be a non-empty opaque string of at most 256 characters")
    return value


def _timestamp(value: str | None, description: str) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if not isinstance(value, str) or not value.strip():
        raise OnboardingCLIError(f"{description} must be a non-empty ISO 8601 timestamp with an explicit UTC offset")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OnboardingCLIError(
            f"{description} must be an ISO 8601 timestamp with an explicit UTC offset"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OnboardingCLIError(f"{description} must include an explicit UTC offset")
    return value


def _confidence(value: float | None, description: str) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise OnboardingCLIError(f"{description} must be finite and in [0, 1]")
    return value


def _validate_artifact(artifact: Mapping[str, Any], schema_name: str) -> None:
    schema_path = _schemas_dir() / schema_name
    schema_value = _require_object(_read_json(schema_path, f"E-16 schema {schema_name}"), f"E-16 schema {schema_name}")
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:
        raise OnboardingCLIError(
            "E-16 output validation requires jsonschema>=4.18,<5; install it before running onboard commands"
        ) from exc
    try:
        Draft202012Validator.check_schema(schema_value)
        validator = Draft202012Validator(schema_value, format_checker=FormatChecker())
        errors = sorted(
            validator.iter_errors(dict(artifact)),
            key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
        )
    except Exception as exc:
        raise OnboardingCLIError(f"could not validate E-16 schema {schema_name}: {type(exc).__name__}: {exc}") from exc
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise OnboardingCLIError(
            f"output does not satisfy schemas/mode-b/v1/{schema_name} at {location}: {first.message}"
        )


def _output_path(path: Path, source_paths: tuple[Path, ...]) -> Path:
    target = path.expanduser().absolute()
    target_resolved = target.resolve(strict=False)
    for source in source_paths:
        source_resolved = source.expanduser().resolve(strict=False)
        if target_resolved == source_resolved:
            raise OnboardingCLIError(f"--output must not overwrite an input file: {source}")
    if target.exists():
        raise OnboardingCLIError(f"--output already exists; choose a new artifact path: {target}")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OnboardingCLIError(f"cannot create output directory {target.parent}: {exc}") from exc
    return target


def _write_artifact(artifact: Mapping[str, Any], schema_name: str, target: Path) -> None:
    _validate_artifact(artifact, schema_name)
    payload = json.dumps(
        dict(artifact),
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if target.exists():
            raise OnboardingCLIError(f"--output already exists; choose a new artifact path: {target}")
        os.replace(temporary_path, target)
        temporary_path = None
    except OnboardingCLIError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise OnboardingCLIError(f"could not write E-16 artifact {target}: {type(exc).__name__}: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _validate_capture_root(labels_path: Path, capture_root: Path) -> dict[str, Any]:
    labels_file = labels_path.expanduser().resolve(strict=True)
    root = capture_root.expanduser().resolve(strict=True)
    if not labels_file.is_file():
        raise OnboardingCLIError(f"--labels is not a file: {labels_file}")
    if not root.is_dir():
        raise OnboardingCLIError(f"--capture-root is not a directory: {root}")
    labels = _require_object(_read_json(labels_file, "labels"), "labels.json")
    if labels.get("label_status") != "OPERATOR_CONFIRMED":
        raise OnboardingCLIError("E-05 training requires labels.json label_status=OPERATOR_CONFIRMED")
    records = labels.get("invoices")
    if not isinstance(records, list) or not records:
        raise OnboardingCLIError("labels.json must contain a non-empty invoices array")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise OnboardingCLIError(f"labels.json invoices[{index}] must be an object")
        relative = record.get("path")
        if not isinstance(relative, str) or not relative.strip():
            raise OnboardingCLIError(f"labels.json invoices[{index}].path must be a non-empty relative path")
        image = (labels_file.parent / relative).resolve(strict=False)
        try:
            image.relative_to(root)
        except ValueError as exc:
            raise OnboardingCLIError(
                f"label image path escapes --capture-root for source {record.get('id', index)!r}: {image}"
            ) from exc
        if image.suffix.casefold() != ".png":
            raise OnboardingCLIError(f"label source image must be PNG: {image}")
        if not image.is_file():
            raise OnboardingCLIError(f"label source image is missing: {image}")
    return labels


def _verify_training_store(canonical_dir: Path, store_id: str) -> None:
    directory = canonical_dir.expanduser().resolve(strict=True)
    manifest = _require_object(_read_json(directory / "synthesis-manifest.json", "E-05 synthesis manifest"), "synthesis manifest")
    invoices = manifest.get("invoices")
    if not isinstance(invoices, list) or not invoices:
        raise OnboardingCLIError("E-05 synthesis manifest must contain a non-empty invoices array")
    for index, record in enumerate(invoices):
        if not isinstance(record, dict):
            raise OnboardingCLIError(f"synthesis manifest invoices[{index}] must be an object")
        filename = record.get("canonical_file")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise OnboardingCLIError(f"unsafe canonical_file in synthesis manifest invoices[{index}]")
        invoice = _require_object(_read_json(directory / filename, f"Canonical fixture {filename}"), filename)
        if invoice.get("store_id") != store_id:
            raise OnboardingCLIError(
                f"Canonical fixture {filename} store_id does not match explicit --store-id"
            )


def _load_e20_helpers() -> Any:
    try:
        return importlib.import_module("synthetic_thermal_invoice")
    except ModuleNotFoundError as original:
        scripts_dir = _repo_root() / "scripts"
        if scripts_dir.is_dir() and str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        try:
            return importlib.import_module("synthetic_thermal_invoice")
        except ModuleNotFoundError as exc:
            raise OnboardingCLIError(
                "E-20 synthetic mechanics helper is unavailable; use the ordinary operator-confirmed build path"
            ) from (exc if exc.name != "synthetic_thermal_invoice" else original)


def build_e20_observations(report_path: Path, expected_values_path: Path) -> dict[str, LayoutObservation]:
    """Reconstruct E-20's already-measured observations from its report and E-03 answer key.

    Geometry comes from the recorded E-20 pixel detector output; row bands use
    the constants from the same E-20 renderer. This function is for synthetic
    tests only and is not an alternative to E-05's production provenance checks.
    """
    report = _require_object(_read_json(report_path, "E-20 report"), "E-20 report")
    expected = _require_object(_read_json(expected_values_path, "E-03 expected values"), "E-03 expected values")
    if report.get("task") != "E-20" or report.get("synthetic_only") is not True or report.get("status") != "PASS":
        raise OnboardingCLIError("--synthetic-e20-report must be a passing synthetic-only E-20 report")
    pages = report.get("pages")
    if not isinstance(pages, list):
        raise OnboardingCLIError("E-20 report pages must be an array")
    page_by_id: dict[str, dict[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict):
            raise OnboardingCLIError("E-20 report pages must contain objects")
        page_id = page.get("page_id")
        if not isinstance(page_id, str) or not page_id.strip() or page_id in page_by_id:
            raise OnboardingCLIError("E-20 report page IDs must be non-empty and unique")
        page_by_id[page_id] = page

    helper = _load_e20_helpers()
    observations: dict[str, LayoutObservation] = {}
    for page_id in helper.PAGE_IDS:
        page = page_by_id.get(page_id)
        values = expected.get(page_id)
        expected_role = "exam" if page_id == "exam" else "learning"
        if page is None or not isinstance(values, dict):
            raise OnboardingCLIError(f"E-20 report or E-03 answer key is missing {page_id}")
        if page.get("role") != expected_role or page.get("detected_layout_status") != "OK":
            raise OnboardingCLIError(f"E-20 page {page_id} has an unexpected role or unsafe detected layout")
        row_count = page.get("detected_row_count")
        quantities = values.get("quantities")
        totals = values.get("line_totals")
        if (
            type(row_count) is not int
            or not isinstance(quantities, list)
            or not isinstance(totals, list)
            or len(quantities) != row_count
            or len(totals) != row_count
            or not isinstance(values.get("payable"), str)
        ):
            raise OnboardingCLIError(f"E-20 report and E-03 values disagree for {page_id}")
        try:
            numeric_quantities = [parse_labeled_integer(value) for value in quantities]
            numeric_totals = [parse_labeled_integer(value) for value in totals]
            numeric_payable = parse_labeled_integer(values["payable"])
        except (TypeError, ValueError) as exc:
            raise OnboardingCLIError(f"E-03 values are not valid labeled integers for {page_id}: {exc}") from exc
        if (
            any(quantity <= 0 for quantity in numeric_quantities)
            or any(total % quantity for quantity, total in zip(numeric_quantities, numeric_totals, strict=True))
            or sum(numeric_totals) != numeric_payable
        ):
            raise OnboardingCLIError(f"E-03 values fail exact arithmetic checks for {page_id}")
        width, height = page.get("width"), page.get("height")
        columns = page.get("detected_column_boundaries")
        payable = page.get("detected_payable_bbox")
        if (
            type(width) is not int
            or type(height) is not int
            or not isinstance(columns, list)
            or len(columns) != 5
            or not isinstance(payable, list)
            or len(payable) != 4
        ):
            raise OnboardingCLIError(f"E-20 page {page_id} has incomplete geometry")
        first_row_top = float(helper.TABLE_TOP + helper.HEADER_HEIGHT)
        row_bands = tuple(
            (
                first_row_top + index * float(helper.ROW_HEIGHT),
                first_row_top + (index + 1) * float(helper.ROW_HEIGHT),
            )
            for index in range(row_count)
        )
        if row_bands[-1][1] > height:
            raise OnboardingCLIError(f"E-20 row bands exceed page bounds for {page_id}")
        field_values = {
            **{f"line.{index}.quantity": str(value) for index, value in enumerate(quantities)},
            **{f"line.{index}.total": str(value) for index, value in enumerate(totals)},
            "invoice.payable": str(values["payable"]),
        }
        observations[page_id] = LayoutObservation(
            source_id=page_id,
            image_width=width,
            image_height=height,
            column_boundaries=tuple(float(value) for value in columns),
            row_bands=row_bands,
            payable_bbox=tuple(float(value) for value in payable),
            field_values=field_values,
        )
    acceptance = report.get("acceptance")
    e05_report = report.get("e05")
    if not isinstance(acceptance, dict) or acceptance.get("passed") is not True:
        raise OnboardingCLIError("E-20 report acceptance block is not passing")
    if (
        not isinstance(e05_report, dict)
        or e05_report.get("learning_source_ids") != ["learning-1", "learning-2", "learning-3"]
        or acceptance.get("e05_exam_observation_matched") is not True
    ):
        raise OnboardingCLIError("E-20 report does not contain the expected E-05 learning/exam result")
    return observations


def build_e20_pipeline_observation(report_path: Path, expected_values_path: Path) -> LayoutObservation:
    """Return the E-20 held-out exam's actual raw pipeline readings."""
    expected_observations = build_e20_observations(report_path, expected_values_path)
    report = _require_object(_read_json(report_path, "E-20 report"), "E-20 report")
    page = expected_observations["exam"]
    pipeline = report.get("pipeline_exam")
    if not isinstance(pipeline, dict) or not isinstance(pipeline.get("cells"), list):
        raise OnboardingCLIError("E-20 report has no pipeline_exam cells")
    raw_values: dict[str, str] = {}
    for cell in pipeline["cells"]:
        if not isinstance(cell, dict):
            raise OnboardingCLIError("E-20 pipeline_exam cells must contain objects")
        field_name = cell.get("field")
        raw_value = cell.get("raw_value")
        if not isinstance(field_name, str) or field_name in raw_values or not isinstance(raw_value, str):
            raise OnboardingCLIError("E-20 pipeline_exam raw cell values are incomplete or duplicated")
        raw_values[field_name] = raw_value
    return LayoutObservation(
        source_id="exam-pipeline-readings",
        image_width=page.image_width,
        image_height=page.image_height,
        column_boundaries=page.column_boundaries,
        row_bands=page.row_bands,
        payable_bbox=page.payable_bbox,
        field_values=raw_values,
    )


def _build_e20_bank(report_path: Path, expected_values_path: Path, currency_unit: str, threshold: float) -> TemplateBank:
    if currency_unit not in {"rial", "toman"}:
        raise OnboardingCLIError("--currency-unit must be explicitly set to rial or toman")
    observations = build_e20_observations(report_path, expected_values_path)
    helper = _load_e20_helpers()
    learning_ids = ("learning-1", "learning-2", "learning-3")
    bank = helper.build_synthetic_e05_bank(tuple(observations[page_id] for page_id in learning_ids))
    if not isinstance(bank, TemplateBank):
        raise OnboardingCLIError("E-20 synthetic helper returned an incompatible E-05 bank")
    return TemplateBank(
        templates=bank.templates,
        confidence_threshold=threshold,
        algorithm_version=bank.algorithm_version,
        currency_unit=currency_unit,
    )


def _validate_synthetic_e20_source_args(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.synthetic_e20_values is None:
        raise OnboardingCLIError("--synthetic-e20-values is required with --synthetic-e20-report")
    if args.canonical_dir is not None or args.labels is not None:
        raise OnboardingCLIError("--canonical-dir and --labels are only used with --capture-root")
    if args.store_id != E20_STORE_ID:
        raise OnboardingCLIError(f"E-20 synthetic store ID must be explicitly supplied as {E20_STORE_ID!r}")
    return args.synthetic_e20_report, args.synthetic_e20_values


def _run_build(args: argparse.Namespace) -> int:
    store_id = _opaque_id(args.store_id, "--store-id")
    if not math.isfinite(args.confidence_threshold) or not 0 < args.confidence_threshold <= 1:
        raise OnboardingCLIError("--confidence-threshold must be finite and in (0, 1]")
    if args.capture_root is not None:
        if args.canonical_dir is None or args.labels is None:
            raise OnboardingCLIError("--canonical-dir and --labels are required with --capture-root")
        if args.synthetic_e20_values is not None:
            raise OnboardingCLIError("--synthetic-e20-values is only used with --synthetic-e20-report")
        labels = _validate_capture_root(args.labels, args.capture_root)
        if labels.get("label_status") != "OPERATOR_CONFIRMED":
            raise OnboardingCLIError("E-05 build requires operator-confirmed labels")
        _verify_training_store(args.canonical_dir, store_id)
        bank = build_template_bank(
            args.canonical_dir,
            args.labels,
            confidence_threshold=args.confidence_threshold,
            currency_unit=args.currency_unit,
        )
        inputs = (args.capture_root, args.canonical_dir, args.labels)
        mode = "operator-confirmed capture labels"
    else:
        report_path, values_path = _validate_synthetic_e20_source_args(args)
        bank = _build_e20_bank(
            report_path,
            values_path,
            args.currency_unit,
            args.confidence_threshold,
        )
        inputs = (report_path, values_path)
        mode = "E-20 synthetic mechanics fixture"
    created_at = _timestamp(args.created_at, "--created-at")
    artifact = {
        "artifact_type": "kandoo.mode-b.template-bank",
        "artifact_version": "1",
        "mode": "B",
        "store_id": store_id,
        "created_at": created_at,
        "template_bank": bank.to_dict(),
    }
    target = _output_path(args.output, inputs)
    _write_artifact(artifact, "template-bank.schema.json", target)
    print(f"WROTE {target} ({mode}; templates={len(bank.templates)})", file=sys.stderr)
    return EXIT_READY


def _load_bank_artifact(path: Path, explicit_store_id: str) -> tuple[dict[str, Any], TemplateBank, bytes]:
    raw = path.expanduser().read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise OnboardingCLIError(f"invalid UTF-8 JSON in E-16 template-bank file {path}: {exc}") from exc
    artifact = _require_object(payload, "E-16 template-bank artifact")
    _validate_artifact(artifact, "template-bank.schema.json")
    store_id = _opaque_id(artifact.get("store_id"), "template-bank store_id")
    if store_id != explicit_store_id:
        raise OnboardingCLIError("explicit --store-id does not match template-bank store_id")
    try:
        bank = TemplateBank.from_dict(_require_object(artifact.get("template_bank"), "template_bank"))
    except (TypeError, ValueError, KeyError) as exc:
        raise OnboardingCLIError(f"E-16 template bank could not be loaded by E-05: {exc}") from exc
    return artifact, bank, raw


def _load_optional_invoice(path: Path | None, explicit_store_id: str, explicit_invoice_id: str) -> dict[str, Any] | None:
    if path is None:
        return None
    invoice = _require_object(_read_json(path, "Canonical Invoice v0"), "Canonical Invoice v0")
    if invoice.get("store_id") != explicit_store_id:
        raise OnboardingCLIError("Canonical Invoice v0 store_id does not match explicit --store-id")
    if invoice.get("invoice_id") != explicit_invoice_id:
        raise OnboardingCLIError("Canonical Invoice v0 invoice_id does not match explicit --invoice-id")
    return invoice


def _load_observation(path: Path | None) -> LayoutObservation | None:
    if path is None:
        return None
    value = _require_object(_read_json(path, "E-05 LayoutObservation"), "E-05 LayoutObservation")
    try:
        return LayoutObservation.from_dict(value)
    except (TypeError, ValueError, KeyError) as exc:
        raise OnboardingCLIError(f"invalid E-05 LayoutObservation: {exc}") from exc


def _manual_override(path: Path | None) -> ManualOverride | None:
    if path is None:
        return None
    value = _require_object(_read_json(path, "E-06 manual override"), "E-06 manual override")
    required = {
        "target",
        "actor_id",
        "actor_role",
        "audit_id",
        "reason",
        "occurred_at",
        "verified_fields",
    }
    if set(value) != required:
        raise OnboardingCLIError(f"manual override JSON must contain exactly: {', '.join(sorted(required))}")
    if value.get("actor_role") != "store_owner":
        raise OnboardingCLIError("manual override actor_role must be 'store_owner' for E-16 v1")
    if not isinstance(value.get("reason"), str) or not value["reason"].strip():
        raise OnboardingCLIError("manual override reason must be a non-empty string")
    verified = value.get("verified_fields")
    if not isinstance(verified, list) or any(not isinstance(field, str) or not field.strip() for field in verified):
        raise OnboardingCLIError("manual override verified_fields must be an array of non-empty strings")
    if len(set(verified)) != len(verified):
        raise OnboardingCLIError("manual override verified_fields must be unique")
    occurred_at = value["occurred_at"]
    if not isinstance(occurred_at, str) or not occurred_at.strip():
        raise OnboardingCLIError("manual override occurred_at must be an explicit ISO 8601 timestamp")
    try:
        return ManualOverride(
            target=Verdict(value["target"]),
            actor_id=_opaque_id(value["actor_id"], "manual override actor_id"),
            actor_role=value["actor_role"],
            audit_id=_opaque_id(value["audit_id"], "manual override audit_id"),
            reason=value["reason"],
            occurred_at=_timestamp(occurred_at, "manual override occurred_at"),
            verified_fields=tuple(verified),
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise OnboardingCLIError(f"invalid E-06 manual override: {exc}") from exc


def _exit_for_verdict(verdict: Verdict) -> int:
    return {
        Verdict.ACCEPT: EXIT_READY,
        Verdict.REVIEW: EXIT_REVIEW,
        Verdict.REJECT: EXIT_BLOCKED,
    }[verdict]


def _run_verdict(args: argparse.Namespace) -> int:
    store_id = _opaque_id(args.store_id, "--store-id")
    invoice_id = _opaque_id(args.invoice_id, "--invoice-id")
    bank_artifact, bank, bank_bytes = _load_bank_artifact(args.template_bank, store_id)
    invoice = _load_optional_invoice(args.invoice, store_id, invoice_id)
    observation = _load_observation(args.observation)
    confidence = _confidence(args.extraction_confidence, "--extraction-confidence")
    if type(args.processed_invoice_count) is not int or args.processed_invoice_count < 0:
        raise OnboardingCLIError("--processed-invoice-count must be a non-negative integer")
    if args.template_bank_locked is None or args.d14_agreement_signed is None or args.require_kit_digit_coverage is None:
        raise OnboardingCLIError("bank-lock, D14, and kit-coverage states must be explicitly specified")
    missing_fields = sorted(set(args.missing_field))
    if any(not isinstance(field, str) or not field.strip() for field in missing_fields):
        raise OnboardingCLIError("--missing-field values must be non-empty")
    override = _manual_override(args.manual_override)
    result = evaluate_verdict(
        invoice,
        bank,
        observation,
        confidence,
        processed_invoice_count=args.processed_invoice_count,
        template_bank_locked=args.template_bank_locked,
        d14_agreement_signed=args.d14_agreement_signed,
        missing_fields=missing_fields,
        require_kit_digit_coverage=args.require_kit_digit_coverage,
        manual_override=override,
    )
    evaluated_at = _timestamp(args.evaluated_at, "--evaluated-at")
    artifact = {
        "artifact_type": "kandoo.mode-b.onboarding-verdict",
        "artifact_version": "1",
        "mode": "B",
        "store_id": store_id,
        "invoice_id": invoice_id,
        "evaluated_at": evaluated_at,
        "template_bank_sha256": hashlib.sha256(bank_bytes).hexdigest(),
        "evaluation_context": {
            "processed_invoice_count": args.processed_invoice_count,
            "template_bank_locked": args.template_bank_locked,
            "d14_agreement_signed": args.d14_agreement_signed,
            "require_kit_digit_coverage": args.require_kit_digit_coverage,
            "extraction_confidence": confidence,
            "missing_fields": missing_fields,
        },
        "result": result.to_dict(),
    }
    input_paths = (args.template_bank, *(path for path in (args.invoice, args.observation, args.manual_override) if path is not None))
    target = _output_path(args.output, input_paths)
    _write_artifact(artifact, "onboarding-verdict.schema.json", target)
    print(f"{result.verdict.value} {target} ({', '.join(result.reason_code_strings)})", file=sys.stderr)
    return _exit_for_verdict(result.verdict)


def _run_register_type(args: argparse.Namespace) -> int:
    store_id = _opaque_id(args.store_id, "--store-id")
    invoice_id = _opaque_id(args.invoice_id, "--invoice-id")
    _bank_artifact, bank, _bank_bytes = _load_bank_artifact(args.template_bank, store_id)
    invoice = _load_optional_invoice(args.invoice, store_id, invoice_id)
    if invoice is None:  # argparse requires --invoice; retain the invariant at the implementation boundary.
        raise OnboardingCLIError("--invoice is required for register-type")
    observation = _load_observation(args.observation)
    if observation is None:
        raise OnboardingCLIError("--observation is required for register-type")
    confidence = _confidence(args.extraction_confidence, "--extraction-confidence")
    if type(args.accepted_invoice_count) is not int or args.accepted_invoice_count < 0:
        raise OnboardingCLIError("--accepted-invoice-count must be a non-negative integer")
    if args.template_bank_locked is None or args.d14_agreement_signed is None:
        raise OnboardingCLIError("bank-lock and D14 states must be explicitly specified")
    detected_at = _timestamp(args.detected_at, "--detected-at")
    detection = detect_invoice_type(
        invoice,
        bank,
        observation,
        confidence,
        store_id=store_id,
        accepted_invoice_count=args.accepted_invoice_count,
        template_bank_locked=args.template_bank_locked,
        d14_agreement_signed=args.d14_agreement_signed,
        detected_at=detected_at,
        candidate_registry=CandidateRegistry(),
    )
    target = _output_path(
        args.output,
        (args.template_bank, args.invoice, args.observation),
    )
    if detection.candidate is None:
        print(
            f"{detection.kind.value} {detection.verdict.value}; no E-16 candidate was created "
            f"({', '.join(detection.reason_code_strings)})",
            file=sys.stderr,
        )
        return _exit_for_verdict(detection.verdict)
    if detection.candidate.store_id != store_id:
        raise OnboardingCLIError("E-08 candidate store_id does not match the explicit store scope")
    exported_at = _timestamp(args.exported_at, "--exported-at")
    artifact = {
        "artifact_type": "kandoo.mode-b.new-type-candidate",
        "artifact_version": "1",
        "mode": "B",
        "store_id": store_id,
        "exported_at": exported_at,
        "candidate": detection.candidate.to_dict(),
    }
    _write_artifact(artifact, "new-type-candidate.schema.json", target)
    print(
        f"{detection.kind.value} {detection.verdict.value} {target} "
        f"(candidate={detection.candidate.candidate_id}; state={detection.candidate.state.value}; audit_trail=not_persisted)",
        file=sys.stderr,
    )
    return _exit_for_verdict(detection.verdict)


def run_onboard(args: argparse.Namespace) -> int:
    """Run one onboarding command and return its stable process exit code."""
    try:
        if args.onboard_command == "build":
            return _run_build(args)
        if args.onboard_command == "verdict":
            return _run_verdict(args)
        if args.onboard_command == "register-type":
            return _run_register_type(args)
        raise OnboardingCLIError(f"unsupported onboard command: {args.onboard_command!r}")
    except OnboardingCLIError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError, ImportError) as exc:
        raise OnboardingCLIError(f"{type(exc).__name__}: {exc}") from exc
