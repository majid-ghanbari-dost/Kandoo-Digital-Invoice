from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from image_extraction_adapter.capture_folder import (
    extract_capture_folder,
    inspect_capture_folder,
)
from image_extraction_adapter.cli import main


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REAL_FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "real"
ALLOWED_KINDS = {"quantity", "line_total", "payable"}


class CaptureFolderAdapterTests(unittest.TestCase):
    def _write_capture(
        self,
        folder: Path,
        pages: dict[str, str] | None = None,
        *,
        spl: bool = True,
        report: bool = True,
    ) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        if spl:
            (folder / "capture-job.spl").write_bytes(b"SYNTHETIC SPL TEST ARTIFACT\x00\x01")
        if report:
            (folder / "Report.txt").write_text(
                "SYNTHETIC KandooPrintProbe Report\nPageCount=1\n",
                encoding="utf-8",
            )
        for output_name, fixture_name in (pages or {"page1.png": "29.png"}).items():
            shutil.copyfile(REAL_FIXTURES / fixture_name, folder / output_name)
        return folder

    def test_happy_path_runs_e02_e05_and_fail_closed_e06(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-happy-") as temp:
            folder = self._write_capture(Path(temp) / "capture")
            result = extract_capture_folder(folder)

        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["verdict"], "REVIEW")
        self.assertEqual(result["e06"]["verdict"], "REVIEW")
        self.assertEqual(len(result["pages"]), 1)
        page = result["pages"][0]
        self.assertEqual(page["file"], "page1.png")
        self.assertEqual(page["e02"]["layout_status"], "OK")
        self.assertEqual(page["e05"]["status"], "MATCH")
        self.assertEqual(page["e05"]["resubstitution_source_fixture"], "29")
        self.assertFalse(page["e05"]["independent_evidence"])
        self.assertEqual(set(result["numeric_candidates"]), ALLOWED_KINDS)
        self.assertEqual(result["accuracy"]["status"], "NOT_SCORED")
        self.assertEqual(set(result["accuracy"]["fields"]), ALLOWED_KINDS)
        self.assertEqual(result["captured_at"], None)
        self.assertEqual(result["e05_bank"]["currency_unit"], None)
        self.assertEqual(result["e05_bank"]["currency_unit_status"], "UNCONFIRMED")
        self.assertIn("CURRENCY_UNIT_UNCONFIRMED", result["e06"]["reason_codes"])
        self.assertTrue(result["numeric_candidates"]["quantity"])
        self.assertTrue(result["numeric_candidates"]["line_total"])
        self.assertTrue(result["numeric_candidates"]["payable"])
        self.assertTrue(
            all(
                candidate["kind"] in ALLOWED_KINDS
                for candidate in page["numeric_candidates"]
            )
        )
        self.assertIn("product-name mapping", " ".join(result["e06"]["details"]))

    def test_missing_spl_is_an_explicit_error_not_a_page_skip(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-no-spl-") as temp:
            folder = self._write_capture(Path(temp) / "capture", spl=False)
            result = extract_capture_folder(folder)

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["verdict"], "REJECT")
        self.assertEqual(result["errors"][0]["code"], "MISSING_SPL")
        self.assertEqual(result["pages"], [])

    def test_missing_png_is_an_explicit_error(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-no-png-") as temp:
            folder = self._write_capture(Path(temp) / "capture", pages={}, report=True)
            for path in folder.glob("*.png"):
                path.unlink()
            result = extract_capture_folder(folder)

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["verdict"], "REJECT")
        self.assertEqual(result["errors"][0]["code"], "MISSING_PNG")
        self.assertEqual(result["pages"], [])

    def test_multiple_pages_are_natural_ordered_and_one_invoice(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-multipage-") as temp:
            folder = self._write_capture(
                Path(temp) / "capture",
                {"page10.png": "31.png", "page2.png": "29.png"},
            )
            result = extract_capture_folder(folder)

        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual([page["file"] for page in result["pages"]], ["page2.png", "page10.png"])
        self.assertEqual([page["page_index"] for page in result["pages"]], [1, 2])
        invoice_lines = result["invoice_candidates"]["line_items"]
        self.assertEqual([line["source_page_index"] for line in invoice_lines], [1, 1, 1, 1, 2, 2, 2])
        self.assertEqual([line["line_index"] for line in invoice_lines], list(range(7)))
        self.assertEqual(len(result["invoice_candidates"]["payable_candidates"]), 2)
        self.assertIn("not silently summed", result["invoice_candidates"]["note"])

    def test_unknown_extra_files_are_tolerated_and_reported(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-extra-") as temp:
            folder = self._write_capture(
                Path(temp) / "capture", {"page1.png": "32.png"}
            )
            (folder / "operator-note.bin").write_bytes(b"extra")
            result = extract_capture_folder(folder)

        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["artifacts"]["extra_files"], ["operator-note.bin"])

    def test_fixture_33_resubstitution_remains_review(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-review-") as temp:
            folder = self._write_capture(
                Path(temp) / "capture", {"page1.png": "33.png"}
            )
            result = extract_capture_folder(folder)

        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["verdict"], "REVIEW")
        self.assertEqual(result["pages"][0]["e02"]["status"], "AUTO_CANDIDATE")
        self.assertEqual(result["pages"][0]["e05"]["status"], "MATCH")
        self.assertEqual(result["pages"][0]["e05"]["resubstitution_source_fixture"], "33")
        self.assertFalse(result["pages"][0]["e05"]["independent_evidence"])

    def test_missing_report_is_explicit_error(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-no-report-") as temp:
            folder = self._write_capture(Path(temp) / "capture", report=False)
            result = extract_capture_folder(folder)

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["errors"][0]["code"], "MISSING_REPORT")

    def test_corrupt_png_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-corrupt-png-") as temp:
            folder = self._write_capture(Path(temp) / "capture", pages={})
            (folder / "page2.png").write_bytes(b"not a PNG")
            result = extract_capture_folder(folder)

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["errors"][0]["code"], "INVALID_PNG")
        self.assertEqual(result["pages"], [])

    def test_inspector_accepts_case_insensitive_extensions_and_report_name(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-case-") as temp:
            folder = self._write_capture(Path(temp) / "capture", pages={"PAGE1.PNG": "29.png"})
            (folder / "capture-job.spl").rename(folder / "capture-job.SPL")
            (folder / "Report.txt").rename(folder / "REPORT.TXT")
            capture = inspect_capture_folder(folder)

        self.assertEqual(capture.spl_path.name, "capture-job.SPL")
        self.assertEqual(capture.report_path.name, "REPORT.TXT")
        self.assertEqual(capture.pages[0].path.name, "PAGE1.PNG")

    def test_cli_emits_json_and_human_summary(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-cli-") as temp:
            folder = self._write_capture(Path(temp) / "capture")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(["extract", "--capture-folder", str(folder)])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 10)
        self.assertEqual(payload["verdict"], "REVIEW")
        self.assertIn("REVIEW", stderr.getvalue())
        self.assertIn("E-06", stderr.getvalue())

    def test_cli_passes_probe_capture_timestamp_through_capture_folder_mode(self):
        timestamp = "2026-10-26T11:12:13+03:30"
        with tempfile.TemporaryDirectory(prefix="e12-capture-captured-at-") as temp:
            folder = self._write_capture(Path(temp) / "capture")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main([
                    "extract",
                    "--capture-folder",
                    str(folder),
                    "--captured-at",
                    timestamp,
                ])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 10)
        self.assertEqual(payload["captured_at"], timestamp)
        self.assertEqual(payload["status"], "REVIEW")

    def test_cli_rejects_capture_timestamp_without_explicit_offset(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-invalid-timestamp-") as temp:
            folder = self._write_capture(Path(temp) / "capture")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main([
                    "extract",
                    "--capture-folder",
                    str(folder),
                    "--captured-at",
                    "2026-10-26T11:12:13",
                ])

        self.assertEqual(exit_code, 30)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("--captured-at", stderr.getvalue())

    def test_cli_writes_error_json_to_out_and_keeps_summary_on_stderr(self):
        with tempfile.TemporaryDirectory(prefix="e12-capture-out-") as temp:
            folder = self._write_capture(Path(temp) / "capture", spl=False)
            output_path = Path(temp) / "result.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main([
                    "extract",
                    "--capture-folder",
                    str(folder),
                    "--out",
                    str(output_path),
                ])
            output = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 30)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(output["errors"][0]["code"], "MISSING_SPL")
        self.assertIn("ERROR / REJECT", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
