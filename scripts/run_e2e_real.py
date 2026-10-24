#!/usr/bin/env python3
"""Run a guarded, local Tesseract/Glyph comparison on the four real fixtures.

No OCR, imports from the application, repository reads, or report creation are
performed until the Tesseract executable is found. The script is intentionally
argument-free and uses only local binaries/files; it makes no network calls.
"""
from __future__ import annotations

import csv
import io
import os
import platform
import re
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TESSERACT_MISSING_MESSAGE = (
    "ERROR: Tesseract is not installed or not on PATH.\n"
    "Please install Tesseract from:\n"
    "https://github.com/UB-Mannheim/tesseract/wiki\n"
    "Then add it to your PATH and re-run this script.\n"
)
LANGUAGE = "fas+eng"
MINIMUM_WORD_CONFIDENCE = 60.0
PSM = 3  # Tesseract AUTO, matching the adapter backend default.
INVOICE_FILES = ("29.png", "31.png", "32.png", "33.png")
NUMERIC_FIELD = re.compile(r"^(?:line\.\d+\.(?:quantity|total)|invoice\.payable)$")


def _venv_python() -> Path | None:
    """Return the requested T2 venv interpreter if it exists on this host."""
    root = Path("/tmp/kandoo-t2-venv")
    candidates = (
        (root / "Scripts" / "python.exe", root / "bin" / "python.exe")
        if os.name == "nt"
        else (root / "bin" / "python",)
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _reexec_in_t2_venv_if_needed() -> None:
    """Use the requested venv after the mandatory Tesseract presence check."""
    interpreter = _venv_python()
    if interpreter is None:
        return
    try:
        if os.path.samefile(interpreter, sys.executable):
            return
    except OSError:
        if interpreter.resolve() == Path(sys.executable).resolve():
            return
    script = Path(__file__).resolve()
    os.execv(str(interpreter), [str(interpreter), str(script), *sys.argv[1:]])


def _missing_tesseract() -> int:
    sys.stderr.write(TESSERACT_MISSING_MESSAGE)
    sys.stderr.flush()
    return 30


def _tesseract_version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    lines = (result.stdout + "\n" + result.stderr).splitlines()
    return next((line.strip() for line in lines if line.strip()), None)


def _parse_tsv_words(tsv: str, OCRWord: Any) -> tuple[Any, ...]:
    """Decode level-5 TSV records into the adapter's image-space word boxes."""
    words = []
    for row in csv.reader(io.StringIO(tsv), delimiter="\t"):
        if len(row) < 12 or row[0].strip().casefold() == "level":
            continue
        try:
            if int(row[0]) != 5:
                continue
            _page, block, paragraph, line, word = (int(value) for value in row[1:6])
            left, top, width, height = (int(value) for value in row[6:10])
            confidence = float(row[10])
        except (TypeError, ValueError):
            continue
        words.append(OCRWord(
            text="\t".join(row[11:]),
            left=left,
            top=top,
            width=width,
            height=height,
            confidence=confidence,
            block_num=block,
            paragraph_num=paragraph,
            line_num=line,
            word_num=word,
        ))
    return tuple(words)


class TesseractCLIBackend:
    """Adapter-compatible full-page backend using the local Tesseract CLI."""

    def __init__(self, executable: str, version: str, OCRResult: Any,
                 OCRWord: Any, Image: Any) -> None:
        self.executable = executable
        self.version = version
        self.OCRResult = OCRResult
        self.OCRWord = OCRWord
        self.Image = Image
        self._cache: dict[Path, Any] = {}

    def _run(self, image_path: Path, *, tsv: bool) -> str:
        command = [
            self.executable,
            str(image_path),
            "stdout",
            "-l",
            LANGUAGE,
            "--psm",
            str(PSM),
        ]
        if tsv:
            command.append("tsv")
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(
                f"Tesseract CLI exited {result.returncode}: {detail or 'no diagnostic output'}")
        if result.stderr.strip():
            print(f"Tesseract diagnostic: {result.stderr.strip()}", file=sys.stderr)
        return result.stdout

    def recognize(self, image_path: Path) -> Any:
        image = Path(image_path).resolve()
        if image in self._cache:
            return self._cache[image]
        if not image.is_file():
            raise FileNotFoundError(f"image file is missing: {image}")
        text = self._run(image, tsv=False)
        tsv = self._run(image, tsv=True)
        words = _parse_tsv_words(tsv, self.OCRWord)
        with self.Image.open(image) as opened:
            opened.load()
            width, height = opened.size
        confidences = tuple(word.confidence for word in words if word.confidence >= 0)
        result = self.OCRResult(
            engine=self.version,
            language=LANGUAGE,
            text=text,
            word_confidences=confidences,
            words=words,
            image_width=width,
            image_height=height,
        )
        self._cache[image] = result
        return result


def _git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=False,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else "UNAVAILABLE"


def _outcome_name(outcome: Any, Ready: Any, ReviewRequired: Any,
                  Blocked: Any) -> str:
    if isinstance(outcome, Ready):
        return "Ready"
    if isinstance(outcome, ReviewRequired):
        return "ReviewRequired"
    if isinstance(outcome, Blocked):
        return "Blocked"
    return type(outcome).__name__


def _review_reason_category(reason: str) -> str:
    lowered = reason.casefold()
    if "tesseract_disagreement_with_glyph_authority" in lowered:
        return "tesseract_disagreement_with_glyph_authority"
    if "flat-text parser blocked:" in lowered or "invoicetextparseerror" in lowered:
        return "InvoiceTextParseError"
    return "other"


def _format_bbox(bbox: Any) -> str:
    return "None" if bbox is None else "[" + ", ".join(str(value) for value in bbox) + "]"


def _run_diagnostics(tesseract: str, tess_version: str) -> tuple[str, int]:
    """Run both adapter modes and return the complete report body and status."""
    output = io.StringIO()
    exit_code = 0
    root = Path(__file__).resolve().parents[1]

    with redirect_stdout(output), redirect_stderr(output):
        try:
            # Prevent the diagnostic run from leaving __pycache__ in the repo.
            sys.dont_write_bytecode = True
            sys.path.insert(0, str(root / "src"))

            import json
            from PIL import Image
            import PIL

            from image_extraction_adapter.adapter import ImageExtractionAdapter
            from image_extraction_adapter.glyph_classifier import (
                GlyphClassifierOCR,
                evaluate_arithmetic_gate,
            )
            from image_extraction_adapter.model import (
                ImageExtractionBlocked,
                ImageExtractionReady,
                ImageExtractionReviewRequired,
                OCRResult,
                OCRWord,
            )
            from image_extraction_adapter.parser import parse_invoice_geometry

            fixture_dir = root / "tests" / "fixtures" / "real"
            labels_path = fixture_dir / "labels.json"
            labels = json.loads(labels_path.read_text(encoding="utf-8"))
            label_by_path = {
                str(entry.get("path", "")): entry
                for entry in labels.get("invoices", [])
            }
            templates_path = root / "src" / "templates.json"
            if not templates_path.is_file():
                raise FileNotFoundError(
                    f"Glyph template file is missing: {templates_path}")
            glyph = GlyphClassifierOCR.from_file(templates_path)
            backend = TesseractCLIBackend(
                tesseract, tess_version, OCRResult, OCRWord, Image)

            print("# B2-3 real-invoice E2E diagnostic")
            print(f"Timestamp (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
            print(f"Tesseract version: {tess_version}")
            print(f"Python version: {platform.python_version()}")
            print(f"Pillow version: {PIL.__version__}")
            print(f"Git HEAD SHA: {_git_head(root)}")
            print(f"Image fixtures: {', '.join(INVOICE_FILES)}")
            print(f"Tesseract language: {LANGUAGE}")
            print(f"Minimum word confidence: {MINIMUM_WORD_CONFIDENCE:.1f}")
            print(f"Glyph templates: {templates_path.relative_to(root)}")
            print("No cloud OCR, VLM, or network service is used.")

            summaries: dict[str, list[tuple[str, str, str]]] = {}
            modes = (
                ("glyph", "glyph"),
                ("tesseract_parse", None),  # None leaves the adapter default intact.
            )
            for mode_name, authority in modes:
                print(f"\n## numeric_authority={mode_name}")
                summaries[mode_name] = []
                for filename in INVOICE_FILES:
                    image_path = fixture_dir / filename
                    label = label_by_path.get(filename, {})
                    reference_bbox = label.get("payable_bbox")
                    print(f"\n### {filename} (invoice {label.get('id', 'unknown')})")
                    print(f"Reference payable bbox: {_format_bbox(reference_bbox)}")
                    try:
                        kwargs = {
                            "ocr_backend": backend,
                            "minimum_word_confidence": MINIMUM_WORD_CONFIDENCE,
                            "numeric_ocr_backend": glyph,
                        }
                        if authority is not None:
                            kwargs["numeric_authority"] = authority
                        adapter = ImageExtractionAdapter(**kwargs)
                        effective_authority = adapter.numeric_authority
                        outcome = adapter.extract(image_path)
                        outcome_name = _outcome_name(
                            outcome,
                            ImageExtractionReady,
                            ImageExtractionReviewRequired,
                            ImageExtractionBlocked,
                        )
                        reason = getattr(outcome, "reason", None)
                        print(f"Outcome: {outcome_name}")
                        print(f"Effective numeric authority: {effective_authority}")
                        print(f"Reason: {reason or 'None'}")

                        fields = getattr(outcome, "field_values", ())
                        numeric_fields = [
                            (name, value) for name, value in fields
                            if NUMERIC_FIELD.fullmatch(name)
                        ]
                        print("Parsed numeric fields:")
                        if numeric_fields:
                            for name, value in numeric_fields:
                                print(f"  {name}={value}")
                        else:
                            print("  (none)")

                        variants = tuple(
                            getattr(outcome, "numeric_ocr_variants", ())
                            or getattr(outcome, "cell_ocr_variants", ())
                        )
                        print("Numeric cell results:")
                        numeric_variants = [
                            item for item in variants
                            if NUMERIC_FIELD.fullmatch(item.field_name)
                        ]
                        if numeric_variants:
                            for item in numeric_variants:
                                print(
                                    f"  {item.field_name}: raw={item.raw_value!r}; "
                                    f"status={item.status}; confidence={item.confidence}; "
                                    f"bbox={_format_bbox(item.bbox)}; reason={item.reason or 'None'}")
                        elif not numeric_fields:
                            print("  (no numeric cell results returned)")

                        ocr = getattr(outcome, "ocr", None)
                        runtime_bbox = None
                        runtime_status = "unavailable"
                        runtime_reason = "OCR result unavailable"
                        if ocr is not None:
                            spatial = parse_invoice_geometry(
                                ocr, minimum_confidence=MINIMUM_WORD_CONFIDENCE)
                            payable_assessment = next(
                                (item for item in spatial.assessments
                                 if item.field_name == "invoice.payable"),
                                None,
                            )
                            if payable_assessment is not None:
                                runtime_bbox = payable_assessment.bbox
                                runtime_status = payable_assessment.status
                                runtime_reason = payable_assessment.reason or "None"
                            else:
                                runtime_reason = "payable assessment not returned"
                        print(
                            "Runtime payable bbox (OCR word boxes): "
                            f"{_format_bbox(runtime_bbox)}; status={runtime_status}; "
                            f"reason={runtime_reason}; reference={_format_bbox(reference_bbox)}")

                        if numeric_variants:
                            gate = evaluate_arithmetic_gate(numeric_variants)
                            gate_status = "PASS" if gate.passed else "FAIL"
                            print(
                                f"Arithmetic gate: {gate_status}; line_sum={gate.line_sum}; "
                                f"payable={gate.payable}; extras={gate.extra_amounts}; "
                                f"reason={gate.reason or 'None'}")
                        else:
                            print("Arithmetic gate: NOT_RUN (no numeric cell variants)")

                        summaries[mode_name].append((filename, outcome_name, reason or ""))
                    except Exception as exc:
                        reason = f"runner_error: {type(exc).__name__}: {exc}"
                        print("Outcome: Blocked")
                        print(f"Reason: {reason}")
                        print("Numeric cell results: unavailable")
                        print(
                            f"Runtime payable bbox (OCR word boxes): unavailable; "
                            f"reference={_format_bbox(reference_bbox)}")
                        print("Arithmetic gate: NOT_RUN")
                        summaries[mode_name].append((filename, "Blocked", reason))
                        exit_code = 1

            print("\n# SUMMARY")
            for mode_name, results in summaries.items():
                counts = Counter(outcome for _, outcome, _ in results)
                print(f"\n## numeric_authority={mode_name}")
                print(f"Ready: {counts.get('Ready', 0)} / 4")
                print(f"REVIEW: {counts.get('ReviewRequired', 0)} / 4")
                print(f"Blocked: {counts.get('Blocked', 0)} / 4")
                review_reasons = Counter(
                    _review_reason_category(reason)
                    for _, outcome, reason in results
                    if outcome == "ReviewRequired"
                )
                print(
                    "REVIEW because tesseract_disagreement_with_glyph_authority: "
                    f"{review_reasons.get('tesseract_disagreement_with_glyph_authority', 0)}")
                print(
                    "REVIEW because InvoiceTextParseError: "
                    f"{review_reasons.get('InvoiceTextParseError', 0)}")
                other_reasons = Counter(
                    reason for _, outcome, reason in results
                    if outcome == "ReviewRequired"
                    and _review_reason_category(reason) == "other"
                )
                print("REVIEW because other reasons:")
                if other_reasons:
                    for reason, count in sorted(other_reasons.items()):
                        print(f"  {count}: {reason}")
                else:
                    print("  (none)")

        except Exception:
            traceback.print_exc(file=output)
            exit_code = 1

    return output.getvalue(), exit_code


def main() -> int:
    # This is deliberately the first runtime check; no application/Pillow imports
    # or repository work happens before confirming Tesseract is on PATH.
    tesseract = shutil.which("tesseract")
    if not tesseract:
        return _missing_tesseract()

    _reexec_in_t2_venv_if_needed()
    version = _tesseract_version(tesseract)
    if version is None:
        return _missing_tesseract()

    report, exit_code = _run_diagnostics(tesseract, version)
    root = Path(__file__).resolve().parents[1]
    report_path = root / "docs" / "e2e-real-report.md"
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8", newline="\n")
    except OSError as exc:
        sys.stdout.write(report)
        sys.stderr.write(f"ERROR: Could not write {report_path}: {exc}\n")
        return 1
    sys.stdout.write(report)
    sys.stdout.flush()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
