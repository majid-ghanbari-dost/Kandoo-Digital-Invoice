from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from image_extraction_adapter.cli import main
from image_extraction_adapter.glyph_classifier import (
    DEFAULT_MAX_DISTANCE,
    DEFAULT_MIN_MARGIN,
)
from image_extraction_adapter.multi_evidence import evaluate_multi_evidence
from image_extraction_adapter.pipeline_v0 import DEFAULT_TEMPLATE_BANK_PATH


ROOT = Path(__file__).resolve().parents[3]
IMAGE = ROOT / "tests" / "fixtures" / "real" / "29.png"


@dataclass(frozen=True)
class _GlyphScore:
    distance: float
    margin: float


@dataclass(frozen=True)
class _Cell:
    field_name: str
    raw_value: str
    status: str = "EXTRACTED"
    reason: str | None = None
    glyph_readings: tuple[_GlyphScore, ...] = ()


def _readings(value: str) -> tuple[_GlyphScore, ...]:
    return tuple(
        _GlyphScore(distance=0.10, margin=0.20)
        for character in value
        if character != "," and character != "?"
    )


def _valid_cells() -> tuple[_Cell, ...]:
    values = (
        ("line.0.total", "۱,۴۵۰,۰۰۰"),
        ("line.0.quantity", "۱"),
        ("line.1.total", "۴,۸۷۰,۰۰۰"),
        ("line.1.quantity", "۱"),
        ("line.2.total", "۵۷۰,۰۰۰"),
        ("line.2.quantity", "۱"),
        ("line.3.total", "۵۷۰,۰۰۰"),
        ("line.3.quantity", "۱"),
        ("invoice.payable", "۷,۴۶۰,۰۰۰"),
    )
    return tuple(
        _Cell(field, value, glyph_readings=_readings(value))
        for field, value in values
    )


def _gate(passed: bool = True):
    return SimpleNamespace(passed=passed, reason=None if passed else "injected failure")


def _layout(row_count: int = 4):
    return SimpleNamespace(row_count=row_count)


class MultiEvidenceTests(unittest.TestCase):
    def _evaluate(
        self,
        cells: tuple[_Cell, ...] | None = None,
        *,
        gate_passed: bool = True,
        row_count: int = 4,
    ):
        return evaluate_multi_evidence(
            _valid_cells() if cells is None else cells,
            _gate(gate_passed),
            _layout(row_count),
        )

    def _assert_only_failed(self, witness_name: str, result) -> None:
        self.assertFalse(result.all_pass)
        self.assertEqual(result.status, "REVIEW")
        self.assertEqual(result.reasons, [witness_name])
        self.assertFalse(result.witnesses[witness_name]["passed"])
        for name, witness in result.witnesses.items():
            if name != witness_name:
                self.assertTrue(witness["passed"], (name, witness["detail"]))

    def test_all_six_witnesses_pass(self):
        result = self._evaluate()

        self.assertTrue(result.all_pass)
        self.assertEqual(result.status, "AUTO_CANDIDATE")
        self.assertEqual(result.reasons, [])
        self.assertEqual(
            list(result.witnesses),
            [
                "sum_gate",
                "thousands_pattern",
                "row_count",
                "glyph_distance",
                "glyph_margin",
                "no_question_mark",
            ],
        )
        self.assertTrue(result.witnesses["thousands_pattern"]["passed"])
        self.assertIn("۷,۴۶۰,۰۰۰", [cell.raw_value for cell in _valid_cells()])

    def test_sum_gate_failure_alone_returns_review(self):
        result = self._evaluate(gate_passed=False)
        self._assert_only_failed("sum_gate", result)

    def test_thousands_pattern_valid_and_invalid_groupings(self):
        valid = self._evaluate()
        self.assertTrue(valid.witnesses["thousands_pattern"]["passed"])

        for invalid_value in ("۷۴۶۰۰۰۰", "۷,۴۶,۰۰۰"):
            with self.subTest(value=invalid_value):
                cells = list(_valid_cells())
                index = next(i for i, cell in enumerate(cells)
                             if cell.field_name == "line.0.total")
                cells[index] = replace(
                    cells[index],
                    raw_value=invalid_value,
                    glyph_readings=_readings(invalid_value),
                )
                result = self._evaluate(tuple(cells))
                self._assert_only_failed("thousands_pattern", result)

    def test_short_persian_values_need_no_grouping(self):
        cells = list(_valid_cells())
        cells[1] = replace(cells[1], raw_value="۱۲", glyph_readings=_readings("۱۲"))
        result = self._evaluate(tuple(cells))
        self.assertTrue(result.witnesses["thousands_pattern"]["passed"])

    def test_row_count_mismatch_alone_returns_review(self):
        result = self._evaluate(row_count=5)
        self._assert_only_failed("row_count", result)

    def test_glyph_distance_above_existing_maximum_alone_returns_review(self):
        cells = list(_valid_cells())
        cell_index = next(i for i, cell in enumerate(cells)
                          if cell.field_name == "line.0.total")
        cell = cells[cell_index]
        bad_readings = list(cell.glyph_readings)
        bad_readings[0] = _GlyphScore(
            distance=DEFAULT_MAX_DISTANCE + 0.001,
            margin=DEFAULT_MIN_MARGIN + 0.05,
        )
        cells[cell_index] = replace(cell, glyph_readings=tuple(bad_readings))

        result = self._evaluate(tuple(cells))
        self._assert_only_failed("glyph_distance", result)
        self.assertIn(
            f"{DEFAULT_MAX_DISTANCE:.3f}",
            result.witnesses["glyph_distance"]["detail"],
        )

    def test_glyph_margin_below_existing_minimum_alone_returns_review(self):
        cells = list(_valid_cells())
        cell_index = next(i for i, cell in enumerate(cells)
                          if cell.field_name == "line.0.total")
        cell = cells[cell_index]
        bad_readings = list(cell.glyph_readings)
        bad_readings[0] = _GlyphScore(
            distance=DEFAULT_MAX_DISTANCE - 0.10,
            margin=DEFAULT_MIN_MARGIN - 0.001,
        )
        cells[cell_index] = replace(cell, glyph_readings=tuple(bad_readings))

        result = self._evaluate(tuple(cells))
        self._assert_only_failed("glyph_margin", result)
        self.assertIn(
            f"{DEFAULT_MIN_MARGIN:.3f}",
            result.witnesses["glyph_margin"]["detail"],
        )

    def test_question_mark_fails_its_witness_without_hiding_grouping_result(self):
        cells = list(_valid_cells())
        cell_index = next(i for i, cell in enumerate(cells)
                          if cell.field_name == "line.0.total")
        cells[cell_index] = replace(
            cells[cell_index],
            raw_value="?۴۶۰,۰۰۰",
            glyph_readings=_readings("۴۶۰,۰۰۰"),
        )

        result = self._evaluate(tuple(cells))
        self._assert_only_failed("no_question_mark", result)
        self.assertIn("?۴۶۰,۰۰۰", result.witnesses["no_question_mark"]["detail"])

    def test_compensating_errors_pass_sum_but_fail_glyph_witnesses(self):
        cells = list(_valid_cells())
        first_index = next(i for i, cell in enumerate(cells)
                           if cell.field_name == "line.0.total")
        second_index = next(i for i, cell in enumerate(cells)
                            if cell.field_name == "line.1.total")

        first = replace(cells[first_index], raw_value="۱,۴۵۱,۰۰۰")
        first_scores = list(_readings(first.raw_value))
        first_scores[0] = _GlyphScore(
            distance=DEFAULT_MAX_DISTANCE + 0.01,
            margin=DEFAULT_MIN_MARGIN + 0.05,
        )
        cells[first_index] = replace(first, glyph_readings=tuple(first_scores))

        second = replace(cells[second_index], raw_value="۴,۸۶۹,۰۰۰")
        second_scores = list(_readings(second.raw_value))
        second_scores[0] = _GlyphScore(
            distance=DEFAULT_MAX_DISTANCE - 0.10,
            margin=DEFAULT_MIN_MARGIN - 0.01,
        )
        cells[second_index] = replace(second, glyph_readings=tuple(second_scores))

        # +1,000 and -1,000 cancel, so the arithmetic sum still equals payable.
        self.assertEqual(1_451_000 + 4_869_000 + 570_000 + 570_000, 7_460_000)
        result = self._evaluate(tuple(cells), gate_passed=True)

        self.assertTrue(result.witnesses["sum_gate"]["passed"])
        self.assertFalse(result.witnesses["glyph_distance"]["passed"])
        self.assertFalse(result.witnesses["glyph_margin"]["passed"])
        self.assertEqual(result.status, "REVIEW")
        self.assertEqual(result.reasons, ["glyph_distance", "glyph_margin"])

    def test_extracted_pipeline_cells_certify_existing_distance_and_margin_gate(self):
        # The E-09 PipelineResult keeps CellOCRVariantResult summaries rather
        # than raw glyph floats. An EXTRACTED summary is the classifier's
        # existing hard-threshold certificate; a gate-only downgrade retains it.
        from image_extraction_adapter.model import CellOCRVariantResult

        cells = tuple(
            CellOCRVariantResult(
                field_name=cell.field_name,
                preprocessing="glyph",
                bbox=(0, 0, 1, 1),
                raw_value=cell.raw_value,
                confidence=90.0,
                status="EXTRACTED",
            )
            for cell in _valid_cells()
        )
        result = evaluate_multi_evidence(cells, _gate(), _layout())
        self.assertTrue(result.witnesses["glyph_distance"]["passed"])
        self.assertTrue(result.witnesses["glyph_margin"]["passed"])

    def test_cli_flag_downgrades_candidate_and_default_behavior_is_unchanged(self):
        cells = list(_valid_cells())
        cells[0] = replace(cells[0], raw_value="۷۴۶۰۰۰۰")
        fake_pipeline_result = SimpleNamespace(
            status="AUTO_CANDIDATE",
            reason="",
            canonical_blockers=(),
            canonical_errors=(),
            cell_results=tuple(cells),
            arithmetic_gate=_gate(),
            row_count=4,
            canonical_invoice={"state": "EXTRACTED", "test_only": True},
        )

        with tempfile.TemporaryDirectory(prefix="multi-evidence-cli-") as temp:
            context_path = Path(temp) / "context.json"
            context_path.write_text("{}", encoding="utf-8")
            common_args = [
                "extract",
                "--image",
                str(IMAGE),
                "--context",
                str(context_path),
                "--templates",
                str(DEFAULT_TEMPLATE_BANK_PATH),
            ]

            with (
                patch(
                    "image_extraction_adapter.cli.extract_pipeline_v0",
                    return_value=fake_pipeline_result,
                ),
                patch(
                    "image_extraction_adapter.cli.validate_canonical_invoice",
                    return_value=(True, []),
                ),
            ):
                default_stdout = io.StringIO()
                default_stderr = io.StringIO()
                with contextlib.redirect_stdout(default_stdout), contextlib.redirect_stderr(default_stderr):
                    default_code = main(common_args)

                enabled_stdout = io.StringIO()
                enabled_stderr = io.StringIO()
                with contextlib.redirect_stdout(enabled_stdout), contextlib.redirect_stderr(enabled_stderr):
                    enabled_code = main([*common_args, "--multi-evidence"])

        self.assertEqual(default_code, 0, default_stderr.getvalue())
        self.assertEqual(default_stderr.getvalue(), "")
        self.assertTrue(json.loads(default_stdout.getvalue())["test_only"])
        self.assertEqual(enabled_code, 10)
        self.assertTrue(json.loads(enabled_stdout.getvalue())["test_only"])
        self.assertIn("multi-evidence: REVIEW", enabled_stderr.getvalue())
        self.assertIn("thousands_pattern", enabled_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
