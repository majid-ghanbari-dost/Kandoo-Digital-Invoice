from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from image_extraction_adapter import capture_triage


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))
from prepare_e27_capture_smoke import prepare_e27_capture_folders  # noqa: E402

SYNTHETIC_FOLDER = (
    REPOSITORY_ROOT
    / "docs"
    / "extraction-bridge"
    / "golden-pack"
    / "v1"
    / "fixtures"
    / "capture-folder"
)
SYNTHETIC_RESULT = (
    REPOSITORY_ROOT
    / "docs"
    / "extraction-bridge"
    / "golden-pack"
    / "v1"
    / "expected"
    / "extract-capture-folder-29.json"
)

E27_CASES = {
    "corrupt-spl": (
        "SPL_HASH_MISMATCH",
        "Data problem: the SPL bytes do not match the digest recorded in Report.txt.",
        ("page1.png",),
    ),
    "empty-job": (
        "EMPTY_JOB",
        "Data problem: Report.txt declares a job with zero pages.",
        ("page1.png",),
    ),
    "duplicate-job-id": (
        "DUPLICATE_JOB_ID",
        "Data problem: Report.txt contains more than one spool-job ID.",
        ("page1.png",),
    ),
    "two-png-page-count-mismatch": (
        "PAGE_COUNT_MISMATCH",
        "Data problem: the page count in Report.txt does not match the PNG pages present.",
        ("page1.png", "page2.png"),
    ),
}


def _expected_e27_report(png_names: tuple[str, ...], problem: str) -> str:
    png_text = ", ".join(f'"{name}"' for name in png_names)
    lines = [
        "Capture-folder triage",
        "Report language: English (follows this repository's CLI and documentation convention).",
        "",
        "What is present",
        '- SPL entries (1): "capture-job.spl"',
        f"- PNG pages ({len(png_names)}): {png_text}",
        '- Report.txt entries (1): "Report.txt"',
        "- Other entries (0): none",
        "- SPL contents are inventoried only; this tool does not interpret the spool format.",
        "",
        "Pipeline decisions",
        "- Capture intake: BLOCKED — one or more required artifact checks rejected the folder.",
        f"  - Report.txt checks: {problem}",
        "- Image extraction (E-02): NOT RUN — artifact intake did not produce a decoded PNG page.",
        "- Layout matching (E-05): NOT RUN — no page reached layout matching.",
        "- Final decision (E-06): NOT RUN — intake stopped before final routing.",
        "",
        "- Accuracy: NOT SCORED — the capture-folder input does not include expected-value labels.",
        "Overall result: BLOCKED / REJECTED (E-30 exit code 20).",
    ]
    return "\n".join(lines) + "\n"


class CaptureTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(SYNTHETIC_RESULT.read_bytes().decode("utf-8"))

    def test_report_explains_repository_synthetic_folder_stages(self) -> None:
        report = capture_triage.format_report(SYNTHETIC_FOLDER, self.result)

        self.assertIn("Report language: English", report)
        self.assertIn('SPL entries (1): "capture-job.spl"', report)
        self.assertIn('PNG pages (1): "page1.png"', report)
        self.assertIn('Report.txt entries (1): "Report.txt"', report)
        self.assertIn("Image extraction (E-02)", report)
        self.assertIn("CANDIDATE", report)
        self.assertIn("Layout matching (E-05)", report)
        self.assertIn("MATCH", report)
        self.assertIn("not independent evidence", report)
        self.assertIn("Final decision (E-06): REVIEW", report)
        self.assertIn("E-30 exit code 10", report)
        self.assertIn("Accuracy: NOT SCORED", report)
        self.assertNotIn(str(REPOSITORY_ROOT), report)
        self.assertNotIn("\r", report)
        self.assertTrue(report.endswith("\n"))
        binary_stream = io.BytesIO()
        capture_triage._write_utf8(SimpleNamespace(buffer=binary_stream), report)
        self.assertEqual(binary_stream.getvalue(), report.encode("utf-8"))
        self.assertNotIn(b"\r", binary_stream.getvalue())

    def test_missing_pil_is_reported_as_environment_not_corrupt_data(self) -> None:
        result = {
            "status": "BLOCKED",
            "verdict": "REVIEW",
            "errors": [{
                "code": "INVALID_PNG",
                "message": "PNG cannot be decoded: ModuleNotFoundError: No module named 'PIL'",
                "path": "page1.png",
            }],
            "pages": [],
            "e06": None,
        }
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(capture_triage, "extract_capture_folder", return_value=result):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = capture_triage.main(["--capture-folder", str(SYNTHETIC_FOLDER)])

        report = stdout.getvalue()
        self.assertEqual(exit_code, 20)
        self.assertIn("Environment issue", report)
        self.assertIn("ModuleNotFoundError: No module named 'PIL'", report)
        self.assertIn("not a finding that the file is corrupt", report)
        self.assertIn("Image extraction (E-02): NOT RUN", report)
        self.assertIn("Layout matching (E-05): NOT RUN", report)
        self.assertIn("Final decision (E-06): NOT RUN", report)
        self.assertIn("Overall result: BLOCKED — environment limitation", report)
        self.assertIn("E-30 exit code 20", report)
        self.assertEqual(stderr.getvalue(), "")

    def test_cli_runs_only_the_committed_synthetic_capture_folder(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = capture_triage.main(["--capture-folder", str(SYNTHETIC_FOLDER)])

        report = stdout.getvalue()
        self.assertIn('SPL entries (1): "capture-job.spl"', report)
        self.assertIn('PNG pages (1): "page1.png"', report)
        self.assertIn("Overall result:", report)
        self.assertNotIn(str(REPOSITORY_ROOT), report)
        self.assertNotIn("\\", report)
        self.assertEqual(stderr.getvalue(), "")
        if capture_triage.PIL_MISSING in report:
            self.assertEqual(exit_code, 20)
            self.assertIn("Environment issue", report)
            self.assertIn("not a finding that the file is corrupt", report)
        else:
            self.assertEqual(exit_code, 10)
            self.assertIn("Image extraction (E-02),", report)
            self.assertIn("Layout matching (E-05),", report)
            self.assertIn("Final decision (E-06): REVIEW", report)

    def test_e27_data_failures_have_byte_stable_reports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e35-capture-cases-") as temp_name:
            generated = prepare_e27_capture_folders(REPOSITORY_ROOT, Path(temp_name))
            failure_cases = {item["case"]: item for item in generated["failures"]}
            self.assertTrue(set(E27_CASES) <= set(failure_cases))

            for case_name, (expected_code, expected_reason, png_names) in E27_CASES.items():
                with self.subTest(case=case_name):
                    failure = failure_cases[case_name]
                    self.assertEqual(failure["expected_error_code"], expected_code)
                    folder = Path(failure["folder"])
                    result = capture_triage.extract_capture_folder(folder)
                    self.assertEqual(capture_triage.status_exit_code(result), 20)
                    error_codes = {item["code"] for item in result.get("errors", [])}
                    self.assertIn(expected_code, error_codes)

                    # The local sandbox may lack Pillow. Remove only its known
                    # decoder error so the fixture report matches the CI result
                    # where the workflow installs Pillow; preserve E-27 data errors.
                    stable_errors = [
                        item
                        for item in result.get("errors", [])
                        if not (
                            item.get("code") == "INVALID_PNG"
                            and capture_triage.PIL_MISSING in str(item.get("message", ""))
                        )
                    ]
                    stable_result = {**result, "errors": stable_errors}
                    expected = _expected_e27_report(png_names, expected_reason).encode("utf-8")
                    outputs: list[bytes] = []
                    for folder_argument in (str(folder), folder.as_posix()):
                        stdout = io.StringIO()
                        with patch.object(
                            capture_triage,
                            "extract_capture_folder",
                            return_value=stable_result,
                        ):
                            with contextlib.redirect_stdout(stdout):
                                exit_code = capture_triage.main([
                                    "--capture-folder",
                                    folder_argument,
                                ])
                        output = stdout.getvalue().encode("utf-8")
                        self.assertEqual(exit_code, 20)
                        self.assertEqual(output, expected)
                        self.assertNotIn(str(temp_name).encode("utf-8"), output)
                        self.assertNotIn(b"\r", output)
                        outputs.append(output)
                    self.assertEqual(outputs[0], outputs[1])

    def test_invalid_invocation_uses_e30_input_error_exit_code(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = capture_triage.main([])

        self.assertEqual(exit_code, 30)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Input error:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
