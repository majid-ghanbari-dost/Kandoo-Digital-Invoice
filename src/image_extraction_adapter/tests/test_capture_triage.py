from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from image_extraction_adapter import capture_triage


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
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
