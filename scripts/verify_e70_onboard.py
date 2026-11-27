"""Synthetic smoke test for the frozen E-70 operator-onboarding command."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from image_extraction_adapter.operator_labels import build_operator_label_template
from image_extraction_adapter.preprocessing import crop_spatial_cells
from image_extraction_adapter.review_evidence import ReviewPageSource, write_review_evidence
from image_extraction_adapter.synthetic_layouts import render_synthetic_invoice


def _spatial(invoice: Any) -> SimpleNamespace:
    x, y, width, height = invoice.observation.payable_bbox
    return SimpleNamespace(
        column_boundaries=invoice.observation.column_boundaries,
        row_bands=invoice.observation.row_bands,
        assessments=(SimpleNamespace(
            field_name="invoice.payable",
            bbox=(int(x), int(y), int(width), int(height)),
            status=None,
        ),),
    )


def _make_synthetic_sample(root: Path) -> tuple[Path, Path, Path]:
    capture = root / "capture"
    capture.mkdir()
    invoice = render_synthetic_invoice(
        capture / "page1.png",
        layout_id="layout-1",
        invoice_index=0,
    )
    (capture / "capture.spl").write_bytes(b"SYNTHETIC E70 smoke only\n")
    (capture / "Report.txt").write_text(
        "Spool job ID: synthetic-e70-bundle-smoke\nPage count: 1\n",
        encoding="utf-8",
        newline="\n",
    )

    from PIL import Image

    with Image.open(invoice.image_path) as opened:
        opened.load()
        page_image = opened.convert("RGB")
    try:
        crops = crop_spatial_cells(
            page_image,
            _spatial(invoice),
            include_descriptions=False,
            include_payable=True,
        )
        cell_results = tuple(
            SimpleNamespace(
                field_name=crop.field_name,
                raw_value=invoice.expected_values[crop.field_name],
                confidence=99.0,
                status="EXTRACTED",
                reason="Synthetic E-70 bundle smoke value.",
                bbox=crop.bbox,
            )
            for crop in crops
            if crop.numeric and crop.field_name in invoice.expected_values
        )
    finally:
        page_image.close()
        for crop in crops:
            crop.image.close()

    evidence_dir = write_review_evidence(
        root / "review-evidence",
        (ReviewPageSource(
            page_index=1,
            image_path=invoice.image_path,
            pipeline_status="REVIEW",
            layout_status="OK",
            layout_reason="Synthetic E-70 smoke geometry.",
            pipeline_reason="Synthetic E-70 smoke; no product decision is made.",
            cell_results=cell_results,
        ),),
    )
    labels_path = build_operator_label_template(evidence_dir)
    labels = json.loads(labels_path.read_bytes().decode("utf-8"))
    for entry in labels["entries"]:
        entry["read_correctly"] = True
        entry["corrected_value"] = None
    labels_path.write_text(
        json.dumps(labels, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return capture, evidence_dir, labels_path


def verify(executable: Path | None = None) -> None:
    environment = os.environ.copy()
    if executable is None:
        additions = [str(ROOT / "src"), str(ROOT / "scripts")]
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(
            [*additions, *([existing] if existing else [])]
        )
        command_prefix = [sys.executable, "-m", "image_extraction_adapter.cli"]
        label = "source"
    else:
        exe = executable.expanduser().resolve(strict=True)
        if not exe.is_file():
            raise FileNotFoundError("frozen executable path is not a file")
        command_prefix = [str(exe)]
        label = "frozen"
    with tempfile.TemporaryDirectory(prefix="e70-onboard-smoke-") as raw_temp:
        root = Path(raw_temp)
        capture, evidence, labels = _make_synthetic_sample(root)
        output = root / "local-baseline"
        result = subprocess.run(
            [
                *command_prefix,
                "onboard",
                "learn",
                "--sample", str(capture), str(evidence), str(labels),
                "--store-id", "synthetic-e70-smoke-store",
                "--currency-unit", "rial",
                "--output-dir", str(output),
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace")[-4000:]
            raise AssertionError(
                f"{label} E-70 onboarding command returned {result.returncode}; stderr={detail}"
            )
        required = {
            "glyph-templates.local.json",
            "e05-template-bank.local.json",
            "e70-onboarding-summary.local.json",
        }
        if {path.name for path in output.iterdir()} != required:
            raise AssertionError("frozen E-70 onboarding did not write all three local artifacts")
        summary = json.loads((output / "e70-onboarding-summary.local.json").read_bytes())
        if (
            summary.get("online_learning") is not False
            or summary.get("confirmed_label_count") != 5
            or summary.get("uncertain_label_count") != 0
            or summary.get("layout_observation_count") != 1
            or summary.get("layout_review_page_count") != 0
        ):
            raise AssertionError("frozen E-70 summary did not match the synthetic smoke case")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, help="optional frozen Windows one-folder executable")
    args = parser.parse_args(argv)
    mode = "frozen" if args.exe is not None else "source"
    try:
        verify(args.exe)
    except Exception as exc:
        message = f"E-70 {mode} smoke FAILED: {type(exc).__name__}: {exc}"
        annotation = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=E-70 onboarding smoke::{annotation}")
        print(message, file=sys.stderr)
        return 1
    print(f"E-70 {mode} smoke PASS: synthetic operator-confirmed labels produced local E-02/E-05 baselines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
