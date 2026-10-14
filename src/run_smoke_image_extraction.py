"""Synthetic raster OCR -> actual Digital Issuance smoke.

Requires optional tesserocr/Pillow plus traineddata supplied out-of-repository.
This fixture is explicitly synthetic and is not a Holoo invoice.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from digital_invoice import (  # noqa: E402
    DigitalInvoiceOpened,
    DigitalInvoiceReadSuccess,
    DigitalInvoiceTraceSuccess,
    LifecycleAdvanced,
    STATE_DRAFT,
    STATE_EXTRACTED,
    STATE_ISSUED,
    STATE_VALIDATED,
)
from image_extraction_adapter import (  # noqa: E402
    ImageExtractionAdapter,
    ImageExtractionBlocked,
    ImageExtractionReviewRequired,
    ImageIssuanceSubmission,
    TesseractOCR,
)
from issuance import DigitalIssuanceWorkspace  # noqa: E402
from validation import ReferenceValidationRulesV1  # noqa: E402

FIXTURE = (Path(__file__).resolve().parent
           / "image_extraction_adapter" / "tests" / "fixtures"
           / "synthetic_invoice.png")
EXPECTED = {
    "invoice.number": "SYNTH-IMG-001",
    "invoice.date": "2026-10-14",
    "total.net": "1000.00",
    "tax.amount": "80.00",
    "invoice.payable": "1080.00",
    "line.0.description": "Synthetic Widget",
    "line.0.quantity": "2",
    "line.0.unit_price": "500.00",
    "line.0.total": "1000.00",
}
DECLARATION = {
    "source_label": "synthetic-image-ocr-smoke",
    "declared_origin": "HOLOO_CAPTURE",  # test declaration; no Holoo data
    "identity_binding": {
        "INVOICE_NUMBER": "invoice.number",
        "INVOICE_DATE": "invoice.date",
        "INVOICE_TOTAL": "invoice.payable",
    },
    "line_binding": {
        0: {
            "LINE_QUANTITY": "line.0.quantity",
            "LINE_UNIT_PRICE": "line.0.unit_price",
            "LINE_TOTAL": "line.0.total",
        }
    },
    "ruleset_id": "synthetic-image-ocr-smoke-declared",
    "ruleset_version": "1",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tessdata-dir", type=Path, required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--minimum-confidence", type=float, required=True)
    parser.add_argument("--image", type=Path, default=FIXTURE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    adapter = ImageExtractionAdapter(
        TesseractOCR(tessdata_dir=args.tessdata_dir, language=args.language),
        minimum_word_confidence=args.minimum_confidence,
    )

    with tempfile.TemporaryDirectory(prefix="kandoo-image-ocr-smoke-") as temp:
        rules = dict(ReferenceValidationRulesV1(
            tolerance="0.02", precision=2, mode="HALF_UP"))
        with DigitalIssuanceWorkspace(Path(temp) / "workspace",
                                      validation_rules=rules) as workspace:
            outcome = adapter.submit_image(
                args.image,
                workspace.service,
                **DECLARATION,
            )
            print("fixture=SYNTHETIC; not a Holoo/Spooler image")
            if isinstance(outcome, ImageExtractionBlocked):
                print(f"ocr.status=BLOCKED reason={outcome.reason}")
                return 2
            if isinstance(outcome, ImageExtractionReviewRequired):
                print("ocr.status=REVIEW_REQUIRED (adapter hold; no submit)")
                print(f"source_image.sha256={outcome.source_image_sha256}")
                print(f"ocr.engine={outcome.ocr.engine}")
                print(f"ocr.language={outcome.ocr.language}")
                print(f"ocr.minimum_confidence={outcome.ocr.minimum_confidence}")
                print(f"review.reason={outcome.reason}")
                print("issuance.submit=NOT_CALLED")
                print("digital_invoice=NONE")
                return 0
            if not isinstance(outcome, ImageIssuanceSubmission):
                print(f"unexpected adapter outcome: {type(outcome).__name__}")
                return 2

            extraction = outcome.extraction
            ocr = extraction.ocr
            print("fixture.label=Synthetic")
            print(f"source_image.sha256={extraction.source_image_sha256}")
            print(f"ocr.engine={ocr.engine}")
            print(f"ocr.language={ocr.language}")
            print(f"ocr.word_count={len(ocr.word_confidences)}")
            print(f"ocr.mean_confidence={ocr.mean_confidence:.2f}")
            print(f"ocr.minimum_confidence={ocr.minimum_confidence:.2f}")
            print("ocr.raw_text.begin")
            print(ocr.text.rstrip())
            print("ocr.raw_text.end")

            actual = dict(extraction.field_values)
            print("ocr.value_comparison=")
            mismatches = []
            for field, expected in EXPECTED.items():
                observed = actual.get(field)
                equal = observed == expected
                print(f"  {field}: expected={expected!r} actual={observed!r} "
                      f"match={equal}")
                if not equal:
                    mismatches.append(field)
            if mismatches:
                print("pipeline.submit=already called; Digital Invoice will not be issued")
                return 1

            submission = outcome.submission
            print(f"issuance.submit.completed={submission.completed}")
            print(f"pipeline.result={type(submission.pipeline).__name__}")
            if not submission.completed:
                print(f"pipeline.stop.stage={submission.pipeline.stage}")
                print(f"pipeline.stop.outcome={type(submission.pipeline.outcome).__name__}")
                print("digital_invoice=NONE")
                return 0

            pipeline = submission.pipeline
            invoice_id = submission.invoice_id
            print("pipeline.outcomes=" + ", ".join(
                f"{step.stage}:{type(step.outcome).__name__}"
                for step in pipeline.steps))
            for step in pipeline.steps:
                if step.stage == "validate" and hasattr(step.outcome, "record"):
                    record = step.outcome.record
                    print(f"validation.{record.rule_id}={record.outcome} "
                          f"({record.outcome_reason})")
                elif step.stage == "project" and hasattr(step.outcome, "record"):
                    record = step.outcome.record
                    print(f"validation_domain={record.domain_state}/"
                          f"{record.disposition} valid={record.valid_count} "
                          f"invalid={record.invalid_count} "
                          f"deferred={record.deferred_count}")
                elif step.stage == "gate_read" and hasattr(step.outcome, "record"):
                    print(f"canonicalization.decision={step.outcome.record.decision}")

            invoice_read = pipeline.invoice
            print(f"canonical_invoice_id={invoice_id}")
            print(f"canonical.field_count={invoice_read.invoice.field_count}")
            print(f"canonical.line_count={invoice_read.invoice.line_count}")
            print("canonical.fields=")
            for field in invoice_read.fields:
                print(f"  {field.field_name}={field.canonical_value} "
                      f"[{field.provenance}]")
            print("canonical.line_fields=")
            for line_field in invoice_read.line_fields:
                print(f"  line.{line_field.line_seq}.{line_field.role}="
                      f"{line_field.canonical_value}")

            opened = workspace.service.open_digital_invoice(invoice_id)
            assert isinstance(opened, DigitalInvoiceOpened), opened
            draft = workspace.service.status(invoice_id)
            assert draft.current_state == STATE_DRAFT, draft
            print(f"lifecycle.open_digital_invoice={draft.current_state}")
            for act, expected_state in (
                (workspace.service.mark_extracted, STATE_EXTRACTED),
                (workspace.service.mark_validated, STATE_VALIDATED),
                (workspace.service.issue, STATE_ISSUED),
            ):
                result = act(invoice_id, "synthetic OCR smoke; explicit act")
                assert isinstance(result, LifecycleAdvanced), result
                assert result.current_state == expected_state, result
                print(f"lifecycle.{act.__name__}={result.current_state}")

            status = workspace.service.status(invoice_id)
            assert isinstance(status.outcome, DigitalInvoiceReadSuccess), status
            assert status.verified and status.current_state == STATE_ISSUED, status
            trace = workspace.service.trace(invoice_id)
            assert isinstance(trace, DigitalInvoiceTraceSuccess), trace
            print(f"digital_invoice_id={status.digital_invoice_id}")
            print(f"digital_invoice.state={status.current_state}")
            print(f"digital_invoice.verified={status.verified}")
            print(f"digital_invoice.trace={type(trace).__name__} "
                  f"links={len(trace.chain)}")
            print("IMAGE OCR E2E SMOKE OK — synthetic fixture only")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
