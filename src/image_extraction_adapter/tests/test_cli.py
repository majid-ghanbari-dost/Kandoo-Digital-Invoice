from __future__ import annotations

import contextlib
import http.client
import io
import json
import shutil
import socket
import subprocess
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from image_extraction_adapter.canonical_invoice import validate_canonical_invoice
from image_extraction_adapter.cli import main
from image_extraction_adapter.pipeline_v0 import DEFAULT_TEMPLATE_BANK_PATH


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "real"


class ExtractionCLITests(unittest.TestCase):
    def _context(self, row_count: int = 4) -> dict:
        return {
            "mode": "B",
            "invoice_id": "cli-test-invoice",
            "display_number": "CLI-000029",
            "operation_id": "cli-test-operation",
            "device_id": "cli-test-device",
            "public_token": "QWJjZGVmZ2hpamtsbW5vcHFyc3R1dg",
            "store_id": "cli-test-store",
            "customer": {
                "phone": "+15551234567",
                "phone_status": "claimed",
                "phone_provenance": "captured",
            },
            "product_names": [f"کالای آزمایشی {index}" for index in range(row_count)],
            "product_name_provenance": ["captured"] * row_count,
        }

    def _write_context(self, directory: str, row_count: int = 4) -> Path:
        context_path = Path(directory) / "canonical-context.json"
        context_path.write_text(
            json.dumps(self._context(row_count), ensure_ascii=False),
            encoding="utf-8",
        )
        return context_path

    def _arguments(
        self,
        context_path: Path,
        *,
        image_path: Path | None = None,
        captured_at: str | None = None,
        templates_path: Path | None = None,
    ) -> list[str]:
        args = [
            "extract",
            "--image",
            str(image_path or (FIXTURES / "29.png")),
            "--context",
            str(context_path),
        ]
        if captured_at is not None:
            args.extend(("--captured-at", captured_at))
        if templates_path is not None:
            args.extend(("--templates", str(templates_path)))
        return args

    def _run_cli(self, args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(args)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def _assert_valid_canonical_json(self, output: str) -> dict:
        self.assertTrue(output.strip(), "expected Canonical JSON on stdout")
        invoice = json.loads(output)
        valid, errors = validate_canonical_invoice(invoice)
        self.assertTrue(valid, errors)
        return invoice

    def test_successful_extraction_exit_0_outputs_canonical_json(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-") as temp:
            context_path = self._write_context(temp)
            code, stdout, stderr = self._run_cli(self._arguments(context_path))

        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, "")
        invoice = self._assert_valid_canonical_json(stdout)
        self.assertEqual(invoice["state"], "EXTRACTED")
        self.assertIn("کالای آزمایشی", stdout)
        self.assertTrue(invoice["provenance"]["template_library_id"])

    def test_drift_report_sidecar_records_per_symbol_means_without_polluting_stdout(self):
        with tempfile.TemporaryDirectory(prefix="e28-cli-drift-report-") as temp:
            context_path = self._write_context(temp)
            report_path = Path(temp) / "glyph-drift.json"
            args = [
                *self._arguments(context_path),
                "--drift-report",
                str(report_path),
            ]
            code, stdout, stderr = self._run_cli(args)
            report_bytes = report_path.read_bytes()
            report = json.loads(report_bytes.decode("utf-8"))

        self.assertEqual(code, 0, stderr)
        self.assertEqual(stderr, "")
        self._assert_valid_canonical_json(stdout)
        self.assertEqual(report["schema_version"], "e28.glyph-drift-report.v1")
        self.assertNotIn(b"\r", report_bytes)
        self.assertTrue(report_bytes.endswith(b"\n"))
        self.assertEqual(report["status"], "CLEAR")
        self.assertTrue(report["mean_distance_by_symbol"])
        self.assertTrue(all(
            item["glyph_count"] > 0
            for item in report["mean_distance_by_symbol"].values()
        ))

    def test_review_case_exit_10_outputs_valid_canonical_json(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-review-") as temp:
            context_path = self._write_context(temp)
            with patch(
                "image_extraction_adapter.pipeline_v0.cluster_description_crops",
                return_value=(),
            ):
                code, stdout, stderr = self._run_cli(self._arguments(context_path))

        self.assertEqual(code, 10, stderr)
        invoice = self._assert_valid_canonical_json(stdout)
        self.assertEqual(invoice["state"], "EXTRACTED")
        self.assertTrue(invoice["attention_cells"])

    def test_review_without_candidate_returns_10_without_invalid_json(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-review-empty-") as temp:
            context_path = self._write_context(temp)
            with (
                patch(
                    "image_extraction_adapter.pipeline_v0._pipeline_status",
                    return_value="REVIEW",
                ),
                patch(
                    "image_extraction_adapter.pipeline_v0._build_canonical_invoice",
                    return_value=(None, ["test review has no complete candidate"]),
                ),
            ):
                code, stdout, stderr = self._run_cli(self._arguments(context_path))

        self.assertEqual(code, 10)
        self.assertEqual(stdout, "")
        self.assertIn("REVIEW", stderr)
        self.assertIn("no complete candidate", stderr)

    def test_blocked_case_exit_20_uses_stderr_and_no_stdout(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-blocked-") as temp:
            context_path = self._write_context(temp)
            corrupt_image = Path(temp) / "corrupt.png"
            corrupt_image.write_bytes(b"not a PNG image")
            code, stdout, stderr = self._run_cli(
                self._arguments(context_path, image_path=corrupt_image)
            )

        self.assertEqual(code, 20)
        self.assertEqual(stdout, "")
        self.assertIn("REJECT", stderr)
        self.assertIn("blocked", stderr.lower())

    def test_missing_image_argument_returns_30_to_stderr(self):
        code, stdout, stderr = self._run_cli(["extract"])
        self.assertEqual(code, 30)
        self.assertEqual(stdout, "")
        self.assertIn("--image", stderr)

    def test_nonexistent_image_returns_30_to_stderr(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-missing-image-") as temp:
            context_path = self._write_context(temp)
            missing_image = Path(temp) / "missing.png"
            code, stdout, stderr = self._run_cli(
                self._arguments(context_path, image_path=missing_image)
            )
        self.assertEqual(code, 30)
        self.assertEqual(stdout, "")
        self.assertIn("--image", stderr)
        self.assertIn("does not exist", stderr)

    def test_missing_context_argument_returns_30(self):
        code, stdout, stderr = self._run_cli(["extract", "--image", str(FIXTURES / "29.png")])
        self.assertEqual(code, 30)
        self.assertEqual(stdout, "")
        self.assertIn("--context", stderr)

    def test_nonexistent_context_file_returns_30(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-missing-context-") as temp:
            context_path = Path(temp) / "missing-context.json"
            code, stdout, stderr = self._run_cli(self._arguments(context_path))
        self.assertEqual(code, 30)
        self.assertEqual(stdout, "")
        self.assertIn("--context", stderr)

    def test_invalid_context_json_returns_30(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-invalid-context-") as temp:
            context_path = Path(temp) / "invalid-context.json"
            context_path.write_text("{invalid", encoding="utf-8")
            code, stdout, stderr = self._run_cli(self._arguments(context_path))
        self.assertEqual(code, 30)
        self.assertEqual(stdout, "")
        self.assertIn("context JSON", stderr)

    def test_valid_captured_at_is_included_in_canonical_output(self):
        timestamp = "2026-10-22T09:30:00Z"
        with tempfile.TemporaryDirectory(prefix="e09-cli-time-") as temp:
            context_path = self._write_context(temp)
            code, stdout, stderr = self._run_cli(
                self._arguments(context_path, captured_at=timestamp)
            )
        self.assertEqual(code, 0, stderr)
        invoice = self._assert_valid_canonical_json(stdout)
        self.assertEqual(invoice["header"]["captured_at"], timestamp)
        self.assertEqual(
            invoice["provenance"]["fields"]["header"]["captured_at"], "derived"
        )

    def test_captured_at_is_optional(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-no-time-") as temp:
            context_path = self._write_context(temp)
            code, stdout, stderr = self._run_cli(self._arguments(context_path))
        self.assertEqual(code, 0, stderr)
        invoice = self._assert_valid_canonical_json(stdout)
        self.assertIsNone(invoice["header"]["captured_at"])
        self.assertEqual(
            invoice["provenance"]["fields"]["header"]["captured_at"], "unavailable"
        )

    def test_invalid_captured_at_returns_30_to_stderr(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-bad-time-") as temp:
            context_path = self._write_context(temp)
            code, stdout, stderr = self._run_cli(
                self._arguments(context_path, captured_at="not-a-timestamp")
            )
        self.assertEqual(code, 30)
        self.assertEqual(stdout, "")
        self.assertIn("--captured-at", stderr)

    def test_default_templates_path_is_used(self):
        self.assertTrue(DEFAULT_TEMPLATE_BANK_PATH.is_file())
        with tempfile.TemporaryDirectory(prefix="e09-cli-default-bank-") as temp:
            context_path = self._write_context(temp)
            code, stdout, stderr = self._run_cli(self._arguments(context_path))
        self.assertEqual(code, 0, stderr)
        invoice = self._assert_valid_canonical_json(stdout)
        self.assertTrue(invoice["provenance"]["template_library_id"])

    def test_custom_templates_path_is_used(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-custom-bank-") as temp:
            context_path = self._write_context(temp)
            custom_bank = Path(temp) / "templates.json"
            shutil.copyfile(DEFAULT_TEMPLATE_BANK_PATH, custom_bank)
            code, stdout, stderr = self._run_cli(
                self._arguments(context_path, templates_path=custom_bank)
            )
        self.assertEqual(code, 0, stderr)
        self._assert_valid_canonical_json(stdout)

    def test_nonexistent_templates_path_returns_30(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-missing-bank-") as temp:
            context_path = self._write_context(temp)
            missing_bank = Path(temp) / "missing-templates.json"
            code, stdout, stderr = self._run_cli(
                self._arguments(context_path, templates_path=missing_bank)
            )
        self.assertEqual(code, 30)
        self.assertEqual(stdout, "")
        self.assertIn("--templates", stderr)

    def test_internal_exception_is_logged_to_stderr_only(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-exception-") as temp:
            context_path = self._write_context(temp)
            with patch(
                "image_extraction_adapter.cli.extract_pipeline_v0",
                side_effect=RuntimeError("synthetic pipeline failure"),
            ):
                code, stdout, stderr = self._run_cli(self._arguments(context_path))
        self.assertEqual(code, 30)
        self.assertEqual(stdout, "")
        self.assertIn("synthetic pipeline failure", stderr)
        self.assertIn("Traceback", stderr)

    def test_cli_does_not_require_tesseract(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-no-tesseract-") as temp:
            context_path = self._write_context(temp)
            with (
                patch("shutil.which", return_value=None),
                patch("subprocess.run") as run_process,
            ):
                code, stdout, stderr = self._run_cli(self._arguments(context_path))
        self.assertEqual(code, 0, stderr)
        self._assert_valid_canonical_json(stdout)
        run_process.assert_not_called()

    def test_cli_makes_no_network_calls(self):
        with tempfile.TemporaryDirectory(prefix="e09-cli-offline-") as temp:
            context_path = self._write_context(temp)
            with (
                patch("socket.create_connection", side_effect=AssertionError("network call")) as socket_call,
                patch("urllib.request.urlopen", side_effect=AssertionError("network call")) as urlopen_call,
                patch("http.client.HTTPConnection.connect", side_effect=AssertionError("network call")) as http_call,
            ):
                code, stdout, stderr = self._run_cli(self._arguments(context_path))
        self.assertEqual(code, 0, stderr)
        self._assert_valid_canonical_json(stdout)
        socket_call.assert_not_called()
        urlopen_call.assert_not_called()
        http_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
